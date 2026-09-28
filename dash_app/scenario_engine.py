"""Native Dash adapter for the canonical Nucleus 42 v30 Scenario Lab.

The standalone publication HTML owns the serialized v30.7 directed-causal
scenario contract. This module reads that exact payload and exposes the Python
API used by the native Dash views. All-in-One and the independent Dash Scenario
Lab therefore share one engine without touching the official forecast model.
"""
from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd

DASH_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = DASH_DIR.parent
HTML_PATH = PROJECT_ROOT / "Election_Model_v30_11_Final_Publication.html"
ENGINE_VERSION = "v30.7-directed-causal-race-first"


def _payload() -> dict[str, Any]:
    if not HTML_PATH.exists():
        raise FileNotFoundError(f"Missing canonical v30 publication: {HTML_PATH}")
    text = HTML_PATH.read_text(encoding="utf-8", errors="ignore")
    match = re.search(
        r'<script[^>]*id=["\']n42ScenarioData["\'][^>]*>(.*?)</script>',
        text,
        flags=re.S | re.I,
    )
    if not match:
        raise RuntimeError("The v30 publication does not contain n42ScenarioData.")
    payload = json.loads(match.group(1))
    if payload.get("engineVersion") != ENGINE_VERSION:
        raise RuntimeError(
            f"Scenario contract mismatch: expected {ENGINE_VERSION}, "
            f"found {payload.get('engineVersion')!r}."
        )
    return payload


_PAYLOAD = _payload()
LABELS = {c["name"]: c.get("label", c["name"]) for c in _PAYLOAD["controls"]}
INTERVENTION_UNITS = {unit: list(names) for unit, names in _PAYLOAD["units"].items()}
CONTROL_TO_UNIT = {name: unit for unit, names in INTERVENTION_UNITS.items() for name in names}
COMPOSITION_BATTERIES = {unit: list(names) for unit, names in _PAYLOAD["batteries"].items()}

_GROUP_FOR_UNIT = {
    "Presidential approval": "Presidency & national direction",
    "Direction of country": "Presidency & national direction",
    "Ideology": "Partisanship & ideology",
    "Party identification": "Partisanship & ideology",
    "Partisan lean": "Partisanship & ideology",
    "Democratic favorability": "Party favorability",
    "Republican favorability": "Party favorability",
    "Unemployment": "Economic fundamentals",
    "Inflation": "Economic fundamentals",
    "Economic conditions": "Economic perceptions",
    "Economic direction": "Economic perceptions",
    "Job market": "Economic perceptions",
    "Previous presidential election result": "Electoral anchors & polling",
    "Generic ballot polls": "Electoral anchors & polling",
}
INPUT_GROUPS: dict[str, list[str]] = {}
for _unit, _names in INTERVENTION_UNITS.items():
    INPUT_GROUPS.setdefault(_GROUP_FOR_UNIT.get(_unit, "National context"), []).extend(_names)


@dataclass(frozen=True)
class ScenarioInput:
    name: str
    label: str
    baseline: float
    historical_minimum: float
    historical_maximum: float
    step: float
    unit: str


def _specs() -> list[ScenarioInput]:
    return [ScenarioInput(
        name=c["name"], label=c.get("label", c["name"]),
        baseline=float(c["baseline"]),
        historical_minimum=float(c.get("historicalMin", c["baseline"])),
        historical_maximum=float(c.get("historicalMax", c["baseline"])),
        step=float(c.get("step", 0.1)), unit=c["unit"],
    ) for c in _PAYLOAD["controls"]]


def normalize_composition_values(values: dict[str, float], changed_name: str | None = None):
    """Apply the same latest-edit-priority battery rule used in the HTML."""
    out = {k: float(v) for k, v in values.items()}
    for names in COMPOSITION_BATTERIES.values():
        present = [n for n in names if n in out]
        total = sum(out[n] for n in present)
        if total <= 100.0 + 1e-9 or not present:
            continue
        anchor = changed_name if changed_name in present else present[0]
        out[anchor] = min(out[anchor], 100.0)
        peers = [n for n in present if n != anchor]
        room = max(0.0, 100.0 - out[anchor])
        peer_sum = sum(out[n] for n in peers)
        for name in peers:
            out[name] = out[name] * room / peer_sum if peer_sum > 0 else 0.0
    return out


class NationalStatePremodel:
    """Compatibility marker for downstream imports."""


class NationalScenarioEngine:
    def __init__(self, payload: dict[str, Any]):
        self.payload = payload
        self.input_specs = _specs()
        self._controls = payload["controls"]
        self._index = {c["name"]: i for i, c in enumerate(self._controls)}
        self._baseline_values = [float(c["baseline"]) / 100.0 for c in self._controls]
        self._sds = [max(float(c.get("sd", 0.0001)), 0.0001) for c in self._controls]
        fixed_d = int(payload["official"]["fixedSenateD"])
        self.production = pd.DataFrame([{"DS before": fixed_d, "DSS UP": 0}])
        self.baseline = self.predict({})

    @staticmethod
    def _clamp(value: float, low: float, high: float) -> float:
        return max(low, min(high, value))

    def _project_batteries(self, values, direct, last_changed):
        for names in COMPOSITION_BATTERIES.values():
            indices = [self._index[n] for n in names]
            total = sum(values[i] for i in indices)
            if total <= 1.0 + 1e-10:
                continue
            anchor_name = last_changed if last_changed in names else next((n for n in names if n in direct), None)
            if anchor_name is not None:
                anchor = self._index[anchor_name]
                values[anchor] = min(values[anchor], 1.0)
                peers = [i for i in indices if i != anchor]
                room = max(0.0, 1.0 - values[anchor])
                peer_sum = sum(values[i] for i in peers)
                for i in peers:
                    values[i] = values[i] * room / peer_sum if peer_sum > 0 else 0.0
            else:
                for i in indices:
                    values[i] /= total
        return values

    def _reconcile(self, direct, order):
        if not direct:
            return list(self._baseline_values), 0.0, set()
        values = list(self._baseline_values)
        for name, value in direct.items():
            if name in self._index:
                values[self._index[name]] = float(value) / 100.0
        last_changed = order[-1] if order else next(reversed(direct), None)
        values = self._project_batteries(values, direct, last_changed)
        touched = {CONTROL_TO_UNIT[n] for n in direct if n in CONTROL_TO_UNIT}
        delta = [(v - b) / sd for v, b, sd in zip(values, self._baseline_values, self._sds)]
        fixed = [c["unit"] in touched for c in self._controls]
        state = [delta[i] if fixed[i] else 0.0 for i in range(len(delta))]
        roots = set(self.payload.get("rootUnits", []))
        weights = self.payload["weights"]
        for unit in self.payload.get("causalOrder", list(INTERVENTION_UNITS)):
            for name in INTERVENTION_UNITS.get(unit, []):
                i = self._index[name]
                if fixed[i]:
                    continue
                state[i] = 0.0 if unit in roots else sum(float(w) * state[j] for j, w in enumerate(weights[i]))
        reconciled = []
        for i, (value, c) in enumerate(zip(values, self._controls)):
            reconciled.append(value if fixed[i] else self._clamp(
                self._baseline_values[i] + state[i] * self._sds[i],
                float(c["propagationLow"]) / 100.0,
                float(c["propagationHigh"]) / 100.0,
            ))
        reconciled = self._project_batteries(reconciled, direct, last_changed)
        distance = math.sqrt(sum(((v - b) / sd) ** 2 for v, b, sd in zip(reconciled, self._baseline_values, self._sds)))
        return reconciled, distance, touched

    def _popular_vote(self, values):
        official = self.payload["official"]
        ed, er = values[self._index["EDPP"]], values[self._index["ERPP"]]
        bed, ber = self._baseline_values[self._index["EDPP"]], self._baseline_values[self._index["ERPP"]]
        allocated = float(official["dpp"]) + float(official["rpp"])
        official_d2 = float(official["dpp"]) / allocated
        scenario_d2 = self._clamp(official_d2 + (ed / max(ed + er, 1e-12) - bed / max(bed + ber, 1e-12)), 0.0, 1.0)
        anchor_dpp, anchor_rpp = allocated * scenario_d2, allocated * (1.0 - scenario_d2)
        swing = self._clamp((anchor_dpp - anchor_rpp) - (float(official["dpp"]) - float(official["rpp"])), -25.0, 25.0)
        margin = self._clamp((float(official["dpp"]) - float(official["rpp"])) + swing, -allocated, allocated)
        dpp = (allocated + margin) / 2.0
        return dpp, allocated - dpp, float(official["other"]), swing

    def predict(self, state: dict[str, Any] | None = None):
        state = state or {}
        direct = {str(k): float(v) for k, v in (state.get("values", {}) or {}).items() if k in self._index}
        order = [str(v) for v in (state.get("order", []) or []) if v in self._index]
        values, distance, touched = self._reconcile(direct, order)
        dpp, rpp, other, swing = self._popular_vote(values)
        official = self.payload["official"]
        house_d = sum(float(r["margin"]) + swing >= 0 for r in self.payload["house"])
        senate_d = int(official["fixedSenateD"]) + sum(float(r["margin"]) + swing >= 0 for r in self.payload["senate"])
        headline = {
            "D Popular Vote (%)": dpp, "R Popular Vote (%)": rpp,
            "D House Seats": float(house_d), "R House Seats": float(435 - house_d),
            "D Senate Seats": float(senate_d), "R Senate Seats": float(100 - senate_d),
        }
        smooth = {"D House Expected": float(house_d), "D Senate Expected": float(senate_d)}
        changed_rows, outside_rows = [], []
        for i, c in enumerate(self._controls):
            now, base = values[i] * 100.0, self._baseline_values[i] * 100.0
            changed = abs(now - base) > 0.05
            if changed:
                source = "Direct intervention" if c["name"] in direct else "Hard battery constraint" if c["unit"] in touched else "Directed reconciliation"
                changed_rows.append({"Control": c.get("label", c["name"]), "Unit": c["unit"], "Baseline (%)": base, "Scenario (%)": now, "Change (pp)": now - base, "Source": source})
            low, high = float(c.get("historicalMin", base)), float(c.get("historicalMax", base))
            base_out, now_out = base < low or base > high, now < low or now > high
            if base_out or now_out:
                outside_rows.append({"Control": c.get("label", c["name"]), "Changed from baseline": bool(changed and now_out), "Baseline already outside support": bool(base_out)})
        battery_rows = []
        for unit, names in COMPOSITION_BATTERIES.items():
            total = sum(values[self._index[n]] for n in names) * 100.0
            battery_rows.append({"Battery": unit, "Scenario total (%)": total, "Constraint": "PASS" if total <= 100.000001 else "FAIL"})
        targets = {c["name"]: values[i] * 100.0 for i, c in enumerate(self._controls)}
        targets.update({
            "DPP": dpp / 100.0, "RPP": rpp / 100.0, "Other popular vote": other,
            "National D-R swing": swing, "D House Seats": float(house_d),
            "R House Seats": float(435 - house_d), "D Senate Seats": float(senate_d),
            "R Senate Seats": float(100 - senate_d), "D House Expected": float(house_d),
            "D Senate Expected": float(senate_d), "Counterfactual distance": distance,
        })
        return {
            "reconciled_values": {c["name"]: values[i] * 100.0 for i, c in enumerate(self._controls)},
            "headline": headline, "smooth_headline": smooth, "targets": targets,
            "changed_inputs": pd.DataFrame(changed_rows), "outside_support": pd.DataFrame(outside_rows),
            "battery_status": pd.DataFrame(battery_rows),
            "coherence": {"Mahalanobis distance": distance, "Coherence status": "Official baseline" if distance < 0.01 else "Near baseline" if distance <= 3 else "Atypical" if distance <= 7 else "Extreme"},
            "propagation_caps": pd.DataFrame(), "feedback_iterations": len(self.payload.get("causalOrder", [])),
            "popular_vote_components": {"Other / unallocated (%)": other, "National D-R swing (pp)": swing},
            "premodel": {"relationship_shrinkage": 0.0, "maximum_row_leverage": 0.0},
        }


OFFICIAL_BASELINE_HEADLINE = {
    "D Popular Vote (%)": float(_PAYLOAD["official"]["dpp"]),
    "R Popular Vote (%)": float(_PAYLOAD["official"]["rpp"]),
    "D House Seats": float(_PAYLOAD["official"]["houseD"]),
    "R House Seats": float(_PAYLOAD["official"]["houseR"]),
    "D Senate Seats": float(_PAYLOAD["official"]["senateD"]),
    "R Senate Seats": float(_PAYLOAD["official"]["senateR"]),
}


@lru_cache(maxsize=2)
def load_scenario_engine(model_path: str, model_mtime_ns: int | None = None):
    return NationalScenarioEngine(_PAYLOAD)
