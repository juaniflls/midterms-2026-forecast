"""National counterfactual engine for the Midterms 2026 v26 dashboard.

The central notebook remains authoritative.  Scenario Lab now inserts a
regularised *national-state reconciliation premodel* before the existing
42-target national model.  Observed historical cycles are never rewritten:
the premodel is used only for counterfactual interventions, where national
inputs are codependent rather than independent sliders.

Architecture
------------
1. Twelve mutually exclusive response batteries and two economic singletons
   form fourteen intervention units.
2. Hard battery constraints are resolved before historical propagation; the
   most recently edited control receives priority when requests conflict.
3. A regularised block relationship system reconciles the fourteen units
   jointly while suppressing within-battery statistical feedback.
4. The reconciled 31-input snapshot is passed to the audited 42-target model.
4. House and Senate geography are moved from the reconciled popular-vote
   swing.  National chamber-bucket responses remain diagnostic and are not
   allowed to reverse the geographic vote pathway.

The layer is associational, deliberately regularised, baseline-centred and
non-causal.  It never writes Model.xlsx, the notebook, HTML or outputs.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer, TransformedTargetRegressor
from sklearn.covariance import LedoitWolf
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.multioutput import MultiOutputRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

ENGINE_VERSION = "v26"

# Replaced by notebook Block 6E after the canonical production forecast exists.
OFFICIAL_BASELINE_TARGETS = {'DPP': 0.5093213701657459, 'RPP': 0.46147862983425414, 'DHouTiltResH (<=1%)': 1.0, 'DHouTiltResLR (<=1%)': 1.0, 'DHouLeanResH  (>1<=5%)': 8.0, 'DHouLeanResLR  (>1<=5%)': 5.0, 'DHouLikResH (>5%<=10%)': 19.0, 'DHouLikResLR (>5%<=10%)': 0.0, 'DHouSafResH (>5%<=10%)': 181.0, 'DHouSafResLR (>10%)': 0.0, 'RHouTiltResH (<=1%)': 4.0, 'RHouTiltResLD (<=1%)': 3.0, 'RHouLeanResH  (>1<=5%)': 14.0, 'RHouLeanResLD  (>1<=5%)': 4.0, 'RHouLikResH (>5%<=10%)': 17.0, 'RHouLikResLD (>5%<=10%)': 4.0, 'RHouSafResH (>10%)': 171.0, 'RHouSafResLD (>10%)': 3.0, 'DSenTiltResH (<=1%)': 1.0, 'DSenTiltResLR (<=1%)': 0.0, 'DSenLeanResH  (>1<=5%)': 1.0, 'DSenLeanResLR  (>1<=5%)': 1.0, 'DSenLikResH (>5%<=10%)': 1.0, 'DSenLikResLR (>5%<=10%)': 0.0, 'DSenSafResH (>10%)': 9.0, 'DSenSafResLR (>10%)': 0.0, 'RSenTiltResH (<=1%)': 1.0, 'RSenTiltResLD (<=1%)': 1.0, 'RSenLeanResH  (>1<=5%)': 1.0, 'RSenLeanResLD  (>1<=5%)': 1.0, 'RSenLikResH (>5%<=10%)': 3.0, 'RSenLikResLD (>5%<=10%)': 0.0, 'RSenSafResH (>10%)': 15.0, 'RSenSafResLD (>10%)': 0.0}
OFFICIAL_BASELINE_HEADLINE = {'D House Seats': 224, 'R House Seats': 211, 'D Senate Seats': 48, 'R Senate Seats': 52}


INPUT_GROUPS: dict[str, list[str]] = {
    "Presidential standing": [
        "Presidential Approval", "Presidential Disapproval",
        "Right Track", "Wrong Track",
    ],
    "Ideology and party identification": [
        "Liberals", "Moderates", "Conservatives",
        "Dem % Reg", "Rep % Reg", "Ind % Reg",
        "Democratic Lean", "Republican Lean",
    ],
    "Party favorability": [
        "DEM FAVORABLE", "DEM UNFAVORABLE",
        "REP FAVORABLE", "REP UNFAVORABLE",
    ],
    "Economic conditions": [
        "Uneyployment", "Inflation", "ECC Excellent", "ECC Good",
        "ECC Only Fair", "ECC Poor", "ECO GBetter", "ECO GWorse",
        "ECO Same", "Job Good Time", "Job Bad Time",
    ],
    "Previous presidential election · historical counterfactual": [
        "D President %", "R President %",
    ],
    "Midterm vote expectation": ["EDPP", "ERPP"],
}

LABELS = {
    "Uneyployment": "Unemployment",
    "Dem % Reg": "Democratic identification",
    "Rep % Reg": "Republican identification",
    "Ind % Reg": "Independent identification",
    "DEM FAVORABLE": "Democratic Party favorable",
    "DEM UNFAVORABLE": "Democratic Party unfavorable",
    "REP FAVORABLE": "Republican Party favorable",
    "REP UNFAVORABLE": "Republican Party unfavorable",
    "ECC Excellent": "Economy: excellent",
    "ECC Good": "Economy: good",
    "ECC Only Fair": "Economy: only fair",
    "ECC Poor": "Economy: poor",
    "ECO GBetter": "Economy getting better",
    "ECO GWorse": "Economy getting worse",
    "ECO Same": "Economy about the same",
    "Job Good Time": "Good time to find a quality job",
    "Job Bad Time": "Bad time to find a quality job",
    "D President %": "Previous presidential result · Democratic vote",
    "R President %": "Previous presidential result · Republican vote",
    "EDPP": "Expected Democratic popular vote",
    "ERPP": "Expected Republican popular vote",
}

PROPORTION_BATTERIES = [
    ["ECC Excellent", "ECC Good", "ECC Only Fair", "ECC Poor"],
    ["ECO GBetter", "ECO GWorse", "ECO Same"],
    ["Job Good Time", "Job Bad Time"],
]

COMPOSITION_BATTERIES: dict[str, list[str]] = {
    "Presidential approval": ["Presidential Approval", "Presidential Disapproval"],
    "Direction of country": ["Right Track", "Wrong Track"],
    "Ideology": ["Liberals", "Moderates", "Conservatives"],
    "Party identification": ["Dem % Reg", "Rep % Reg", "Ind % Reg"],
    "Partisan lean": ["Democratic Lean", "Republican Lean"],
    "Democratic favorability": ["DEM FAVORABLE", "DEM UNFAVORABLE"],
    "Republican favorability": ["REP FAVORABLE", "REP UNFAVORABLE"],
    "Economic conditions": ["ECC Excellent", "ECC Good", "ECC Only Fair", "ECC Poor"],
    "Economic direction": ["ECO GBetter", "ECO GWorse", "ECO Same"],
    "Job market": ["Job Good Time", "Job Bad Time"],
    "Previous presidential election result": ["D President %", "R President %"],
    "Expected midterm popular vote": ["EDPP", "ERPP"],
}

INTERVENTION_UNITS: dict[str, list[str]] = {
    **COMPOSITION_BATTERIES,
    "Unemployment": ["Uneyployment"],
    "Inflation": ["Inflation"],
}

# Preserve the methodological order used in the notebook and dashboard.
INTERVENTION_UNITS = {
    name: INTERVENTION_UNITS[name]
    for name in [
        "Presidential approval", "Direction of country", "Ideology",
        "Party identification", "Partisan lean", "Democratic favorability",
        "Republican favorability", "Unemployment", "Inflation",
        "Economic conditions", "Economic direction", "Job market",
        "Previous presidential election result", "Expected midterm popular vote",
    ]
}
CONTROL_TO_UNIT = {
    control: unit for unit, controls in INTERVENTION_UNITS.items() for control in controls
}
CONTROL_ORDER = [
    control for group in INPUT_GROUPS.values() for control in group
]

# These variables may be intervened on, but present political perceptions do
# not rewrite already observed macroeconomic facts or the previous election.
TEMPORAL_ROOT_UNITS = {
    "Unemployment", "Inflation", "Previous presidential election result",
}


@dataclass(frozen=True)
class ScenarioInput:
    name: str
    label: str
    group: str
    baseline: float
    minimum: float
    maximum: float
    historical_minimum: float
    historical_maximum: float
    step: float = 0.5


def _clean_number(value: Any) -> float:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return np.nan
    if isinstance(value, str):
        value = value.strip().replace("%", "").replace(",", "")
        if value.upper() in {"P", "W", "NAN", "NONE", ""}:
            return np.nan
    return float(pd.to_numeric(value, errors="coerce"))


def _parse_model(path: Path) -> tuple[pd.DataFrame, list[str], list[str], list[str], list[str]]:
    raw = pd.read_excel(path, sheet_name="Model", header=None, dtype=object)
    header_index = next(
        i for i in range(len(raw))
        if "Midterm Year" in raw.iloc[i].astype(str).str.strip().tolist()
    )
    header = raw.iloc[header_index].astype(str).str.strip()
    frame = raw.iloc[header_index + 1:].copy()
    frame.columns = header
    frame = frame[frame["Midterm Year"].notna()].copy()
    frame["Midterm Year"] = frame["Midterm Year"].astype(int)
    row_2026 = frame.loc[frame["Midterm Year"].eq(2026)].iloc[0]
    target_columns = [c for c in frame.columns if str(row_2026[c]).strip().upper() == "P"]
    feature_columns = [c for c in frame.columns if c not in target_columns]
    categorical = [
        c for c in ["Incumbent Party PRES", "Incumbent Party Senate", "Incumbent Party House"]
        if c in feature_columns
    ]
    numeric = [c for c in feature_columns if c not in categorical]
    for column in numeric + target_columns:
        frame[column] = frame[column].map(_clean_number)
    for column in categorical:
        frame[column] = frame[column].astype(str).str.strip()
    for columns in PROPORTION_BATTERIES:
        for index in frame.index:
            values = frame.loc[index, columns].astype(float)
            if float(values.sum()) > 1.5:
                frame.loc[index, columns] = values / 100.0
    frame["DEM NET FAVORABILITY"] = frame["DEM FAVORABLE"] - frame["DEM UNFAVORABLE"]
    frame["REP NET FAVORABILITY"] = frame["REP FAVORABLE"] - frame["REP UNFAVORABLE"]
    return frame, target_columns, feature_columns, categorical, numeric


def _ridge_pipeline(categorical: list[str], numeric: list[str], alpha: float = 10.0) -> Pipeline:
    prep = ColumnTransformer([
        ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False, dtype=np.float64), categorical),
        ("num", Pipeline([
            ("imputer", SimpleImputer(strategy="median")),
            ("scale", StandardScaler()),
        ]), numeric),
    ])
    estimator = TransformedTargetRegressor(
        regressor=MultiOutputRegressor(
            Ridge(alpha=float(alpha), solver="lsqr", max_iter=10_000, tol=1e-8),
            n_jobs=1,
        ),
        transformer=StandardScaler(),
        check_inverse=True,
    )
    return Pipeline([("prep", prep), ("model", estimator)])


def _loss_columns(columns: list[str], party: str) -> list[str]:
    marker = "ResLR" if party == "D" else "ResLD"
    return [column for column in columns if marker in column]


def _hamilton(raw_predictions: Mapping[str, float], columns: list[str], total: float) -> dict[str, int]:
    values = np.asarray([max(float(raw_predictions.get(c, 0.0)), 0.0) for c in columns])
    required = int(round(float(total)))
    if not np.isfinite(values).all() or float(values.sum()) <= 0:
        raise ValueError("Scenario bucket predictions have a non-positive total.")
    quotas = values / values.sum() * required
    allocation = np.floor(quotas).astype(int)
    remainder = required - int(allocation.sum())
    if remainder:
        order = np.argsort(-(quotas - allocation), kind="stable")
        allocation[order[:remainder]] += 1
    return dict(zip(columns, allocation.tolist()))


class NationalStatePremodel:
    """Joint fourteen-unit reconciliation model for the 31 national controls.

    Statistical propagation is permitted only across intervention units. Within
    each response battery, changes are algebraic consequences of the 100-percent
    ceiling and the user's edit order, never learned component-to-component
    effects. Cross-unit weights use Ledoit-Wolf shrinkage, leave-one-cycle-out
    sign stability, and a contraction bound so joint feedback converges.
    """

    MAX_ROW_LEVERAGE = 0.65
    ITERATION_DAMPING = 0.55
    MAX_ITERATIONS = 100
    CONVERGENCE_TOLERANCE = 1e-9

    def __init__(self, train: pd.DataFrame, production: pd.DataFrame):
        self.train = train.copy()
        self.production = production.copy()
        self.base = self.production.iloc[0].copy()
        self.control_names = list(CONTROL_ORDER)
        self.control_index = {name: index for index, name in enumerate(self.control_names)}

        history = self.train[self.control_names].astype(float).copy()
        self.control_history = history.copy()
        self.history_mean = history.mean(axis=0).to_numpy(dtype=float)
        self.history_sd = history.std(axis=0, ddof=0).replace(0.0, 0.01).to_numpy(dtype=float)
        standardized = (
            history.to_numpy(dtype=float) - self.history_mean
        ) / self.history_sd

        covariance_model = LedoitWolf(
            assume_centered=False, store_precision=False
        ).fit(standardized)
        covariance = np.asarray(covariance_model.covariance_, dtype=float)
        variance = np.maximum(np.diag(covariance), 1e-10)
        denominator = np.sqrt(np.outer(variance, variance))
        shrinkage_correlation = np.divide(
            covariance, denominator,
            out=np.zeros_like(covariance), where=denominator > 0,
        )
        np.fill_diagonal(shrinkage_correlation, 0.0)

        reliability = self._leave_one_cycle_out_reliability(standardized)
        weights = shrinkage_correlation * reliability

        # Suppress learned feedback within a response battery. Those peers are
        # reconciled only by the hard composition projector.
        for target, target_name in enumerate(self.control_names):
            target_unit = CONTROL_TO_UNIT[target_name]
            for source_index, source_name in enumerate(self.control_names):
                source_unit = CONTROL_TO_UNIT[source_name]
                if target_unit == source_unit:
                    weights[target, source_index] = 0.0
                if target_unit in TEMPORAL_ROOT_UNITS and target_unit != source_unit:
                    weights[target, source_index] = 0.0

        # Bound every target equation. This makes the feedback system a
        # contraction and prevents cyclic amplification under extreme sliders.
        for target in range(len(self.control_names)):
            row_l1 = float(np.sum(np.abs(weights[target])))
            if row_l1 > self.MAX_ROW_LEVERAGE:
                weights[target] *= self.MAX_ROW_LEVERAGE / row_l1

        self.relationship_weights = np.nan_to_num(
            weights, nan=0.0, posinf=0.0, neginf=0.0
        )
        self.relationship_reliability = reliability
        self.relationship_correlation = shrinkage_correlation
        self.relationship_shrinkage = float(covariance_model.shrinkage_)
        self.latent_shrinkage = self.relationship_shrinkage

        historical_minimum = history.min(axis=0).to_numpy(dtype=float)
        historical_maximum = history.max(axis=0).to_numpy(dtype=float)
        baseline = self.base[self.control_names].astype(float).to_numpy(dtype=float)
        span = np.maximum(historical_maximum - historical_minimum, 0.02)
        self.propagation_low = np.maximum(
            0.0, np.minimum(historical_minimum, baseline) - 0.50 * span
        )
        self.propagation_high = np.minimum(
            1.0, np.maximum(historical_maximum, baseline) + 0.50 * span
        )

    def _leave_one_cycle_out_reliability(self, standardized: np.ndarray) -> np.ndarray:
        """Estimate directional stability without treating five cycles as causal."""
        count = standardized.shape[1]
        full = np.nan_to_num(np.corrcoef(standardized, rowvar=False), nan=0.0)
        folds = []
        if standardized.shape[0] >= 4:
            for hold in range(standardized.shape[0]):
                fold = np.delete(standardized, hold, axis=0)
                folds.append(np.nan_to_num(np.corrcoef(fold, rowvar=False), nan=0.0))
        if not folds:
            return np.zeros((count, count), dtype=float)
        fold_stack = np.stack(folds)
        full_sign = np.sign(full)
        agreement = np.mean(np.sign(fold_stack) == full_sign[None, :, :], axis=0)
        dispersion = np.std(fold_stack, axis=0)
        sign_stability = np.clip((agreement - 0.50) / 0.50, 0.0, 1.0)
        dispersion_penalty = np.clip(1.0 - dispersion, 0.0, 1.0)
        magnitude_gate = np.clip((np.abs(full) - 0.10) / 0.40, 0.0, 1.0)
        reliability = sign_stability * dispersion_penalty * magnitude_gate
        np.fill_diagonal(reliability, 0.0)
        return np.nan_to_num(reliability, nan=0.0, posinf=0.0, neginf=0.0)

    @staticmethod
    def _parse_intervention_state(
        overrides: Mapping[str, Any]
    ) -> tuple[dict[str, float], list[str]]:
        if not isinstance(overrides, Mapping):
            return {}, []
        if isinstance(overrides.get("values"), Mapping):
            raw_values = dict(overrides.get("values", {}))
            raw_order = list(overrides.get("order", raw_values.keys()))
        else:
            raw_values = dict(overrides)
            raw_order = list(raw_values.keys())

        requested = {
            name: float(np.clip(value, 0.0, 100.0))
            for name, value in raw_values.items()
            if name in CONTROL_TO_UNIT and value is not None
        }
        chronological = [name for name in raw_order if name in requested]
        for name in requested:
            if name not in chronological:
                chronological.append(name)
        return requested, chronological

    @staticmethod
    def _latest_unique(order: list[str]) -> list[str]:
        seen: set[str] = set()
        newest_first = []
        for name in reversed(order):
            if name not in seen:
                newest_first.append(name)
                seen.add(name)
        return newest_first

    @classmethod
    def _project_batteries(
        cls,
        row: pd.Series,
        requested: Mapping[str, float],
        order: list[str],
    ) -> tuple[pd.Series, pd.DataFrame]:
        """Project each battery to <=100%, with latest-edit priority."""
        out = row.copy()
        adjustments: list[dict[str, Any]] = []
        newest_first = cls._latest_unique(order)

        for battery, columns in COMPOSITION_BATTERIES.items():
            before = out[columns].astype(float).clip(0.0, 1.0)
            direct = [name for name in newest_first if name in columns and name in requested]
            direct_set = set(direct)
            peers = [name for name in columns if name not in direct_set]
            total_before = float(before.sum())
            if total_before <= 1.0 + 1e-12:
                out.loc[columns] = before
                continue

            direct_sum = float(before[direct].sum()) if direct else 0.0
            if direct_sum > 1.0 + 1e-12:
                remaining = 1.0
                accepted = {name: 0.0 for name in direct}
                # Newest requests consume the feasible budget first.
                for name in direct:
                    accepted[name] = min(float(before[name]), remaining)
                    remaining -= accepted[name]
                for name, value in accepted.items():
                    out[name] = value
                for name in peers:
                    out[name] = 0.0
            else:
                for name in direct:
                    out[name] = float(before[name])
                remaining = max(0.0, 1.0 - direct_sum)
                peer_sum = float(before[peers].sum()) if peers else 0.0
                if peers and peer_sum > remaining + 1e-12:
                    scale = remaining / peer_sum if peer_sum > 1e-12 else 0.0
                    for name in peers:
                        out[name] = float(before[name]) * scale

            after_total = float(out[columns].astype(float).sum())
            for name in columns:
                delta = float(out[name]) - float(before[name])
                if abs(delta) > 1e-12:
                    adjustments.append({
                        "Battery": battery,
                        "Variable": name,
                        "Before (%)": 100.0 * float(before[name]),
                        "After (%)": 100.0 * float(out[name]),
                        "Adjustment (pp)": 100.0 * delta,
                        "Latest direct control": direct[0] if direct else "None",
                        "Battery total before (%)": 100.0 * total_before,
                        "Battery total after (%)": 100.0 * after_total,
                    })

        return out, pd.DataFrame(adjustments)

    def _solve_joint_feedback(
        self,
        source_row: pd.Series,
        touched_units: set[str],
    ) -> tuple[np.ndarray, int, float]:
        baseline = self.base[self.control_names].astype(float).to_numpy(dtype=float)
        source = source_row[self.control_names].astype(float).to_numpy(dtype=float)
        direct_delta = (source - baseline) / self.history_sd

        fixed = np.asarray([
            CONTROL_TO_UNIT[name] in touched_units for name in self.control_names
        ], dtype=bool)
        root = np.asarray([
            CONTROL_TO_UNIT[name] in TEMPORAL_ROOT_UNITS for name in self.control_names
        ], dtype=bool)
        delta = np.zeros(len(self.control_names), dtype=float)
        delta[fixed] = direct_delta[fixed]

        final_change = 0.0
        iteration = 0
        for iteration in range(1, self.MAX_ITERATIONS + 1):
            candidate = self.relationship_weights @ delta
            candidate[fixed] = direct_delta[fixed]
            candidate[root & ~fixed] = 0.0
            updated = (
                self.ITERATION_DAMPING * candidate
                + (1.0 - self.ITERATION_DAMPING) * delta
            )
            updated[fixed] = direct_delta[fixed]
            updated[root & ~fixed] = 0.0
            final_change = float(np.max(np.abs(updated - delta)))
            delta = updated
            if final_change <= self.CONVERGENCE_TOLERANCE:
                break
        return delta, iteration, final_change

    def relationship_edges(self) -> pd.DataFrame:
        """Aggregate regularised control weights into the 14-unit graph."""
        rows = []
        for source_unit, source_controls in INTERVENTION_UNITS.items():
            source_indices = [self.control_index[name] for name in source_controls]
            for target_unit, target_controls in INTERVENTION_UNITS.items():
                if source_unit == target_unit:
                    continue
                target_indices = [self.control_index[name] for name in target_controls]
                block = self.relationship_weights[np.ix_(target_indices, source_indices)]
                reliability = self.relationship_reliability[
                    np.ix_(target_indices, source_indices)
                ]
                rows.append({
                    "Source unit": source_unit,
                    "Target unit": target_unit,
                    "Signed mean weight": float(np.mean(block)),
                    "Absolute weight L1": float(np.sum(np.abs(block))),
                    "Maximum absolute control weight": float(np.max(np.abs(block))),
                    "Mean LOEO reliability": float(np.mean(reliability)),
                    "Nonzero control edges": int(np.sum(np.abs(block) > 1e-10)),
                    "Within-battery statistical feedback": False,
                    "Interpretation": "Regularised association; non-causal",
                })
        return pd.DataFrame(rows).sort_values(
            ["Absolute weight L1", "Source unit", "Target unit"],
            ascending=[False, True, True],
        ).reset_index(drop=True)

    def control_relationship_edges(self) -> pd.DataFrame:
        rows = []
        for source_index, source in enumerate(self.control_names):
            for target_index, target in enumerate(self.control_names):
                if source == target:
                    continue
                rows.append({
                    "Source": source,
                    "Source unit": CONTROL_TO_UNIT[source],
                    "Target": target,
                    "Target unit": CONTROL_TO_UNIT[target],
                    "Regularised weight": float(
                        self.relationship_weights[target_index, source_index]
                    ),
                    "Shrinkage correlation": float(
                        self.relationship_correlation[target_index, source_index]
                    ),
                    "LOEO reliability": float(
                        self.relationship_reliability[target_index, source_index]
                    ),
                    "Permitted": bool(
                        CONTROL_TO_UNIT[source] != CONTROL_TO_UNIT[target]
                        and not (
                            CONTROL_TO_UNIT[target] in TEMPORAL_ROOT_UNITS
                            and CONTROL_TO_UNIT[source] != CONTROL_TO_UNIT[target]
                        )
                    ),
                })
        return pd.DataFrame(rows)

    def coherence_diagnostics(self, row: pd.Series) -> dict[str, float | str]:
        baseline = self.base[self.control_names].astype(float).to_numpy(dtype=float)
        scenario = row[self.control_names].astype(float).to_numpy(dtype=float)
        distance = float(np.sqrt(np.sum(np.square((scenario - baseline) / self.history_sd))))
        if distance <= 1e-8:
            status = "Official 2026 snapshot baseline"
        elif distance <= 3.0:
            status = "Near-baseline counterfactual"
        elif distance <= 7.0:
            status = "Atypical counterfactual"
        else:
            status = "Extreme counterfactual displacement"
        return {
            "Standardized distance": distance,
            "Mahalanobis distance": distance,
            "Mahalanobis squared": distance ** 2,
            "Coherence status": status,
            "Distance metric": "Diagonal standardized distance across 31 controls",
        }

    def reconcile(self, overrides: Mapping[str, Any]) -> dict[str, Any]:
        requested, order = self._parse_intervention_state(overrides)
        if not requested:
            row = self.base.copy()
            values = {name: float(row[name]) * 100.0 for name in self.control_names}
            state = pd.DataFrame([{
                "Unit": CONTROL_TO_UNIT[name], "Control": name,
                "Baseline (%)": values[name], "Scenario (%)": values[name],
                "Change (pp)": 0.0, "State": "Official baseline",
            } for name in self.control_names])
            return {
                "row": row, "values": values, "direct": {}, "direct_order": [],
                "direct_accepted": {}, "propagation": pd.DataFrame(),
                "latent": state, "observed_latents": [], "observed_units": [],
                "coherence": self.coherence_diagnostics(row),
                "propagation_caps": pd.DataFrame(),
                "battery_adjustments": pd.DataFrame(),
                "feedback_iterations": 0, "feedback_residual": 0.0,
            }

        row = self.base.copy()
        for name, value in requested.items():
            row[name] = value / 100.0
        row, first_adjustments = self._project_batteries(row, requested, order)
        touched_units = {CONTROL_TO_UNIT[name] for name in requested}

        delta, iterations, residual = self._solve_joint_feedback(row, touched_units)
        baseline = self.base[self.control_names].astype(float).to_numpy(dtype=float)
        propagated = baseline + delta * self.history_sd
        caps = []
        for index, name in enumerate(self.control_names):
            unit = CONTROL_TO_UNIT[name]
            if unit in touched_units:
                continue
            raw_value = float(propagated[index])
            bounded = float(np.clip(
                raw_value, self.propagation_low[index], self.propagation_high[index]
            ))
            bounded = float(np.clip(bounded, 0.0, 1.0))
            row[name] = bounded
            if abs(raw_value - bounded) > 1e-12:
                caps.append({
                    "Variable": name,
                    "Unbounded (%)": 100.0 * raw_value,
                    "Bounded (%)": 100.0 * bounded,
                    "Adjustment (pp)": 100.0 * (bounded - raw_value),
                })

        row, final_adjustments = self._project_batteries(row, requested, order)
        row["DEM NET FAVORABILITY"] = float(
            row["DEM FAVORABLE"] - row["DEM UNFAVORABLE"]
        )
        row["REP NET FAVORABILITY"] = float(
            row["REP FAVORABLE"] - row["REP UNFAVORABLE"]
        )

        values = {name: float(row[name]) * 100.0 for name in self.control_names}
        baseline_values = {
            name: float(self.base[name]) * 100.0 for name in self.control_names
        }
        accepted = {name: values[name] for name in requested}
        changes = []
        state_rows = []
        for name in self.control_names:
            change = values[name] - baseline_values[name]
            unit = CONTROL_TO_UNIT[name]
            if name in requested:
                source = "Direct intervention"
            elif unit in touched_units:
                source = "Hard battery constraint"
            else:
                source = "Premodel propagation"
            state_rows.append({
                "Unit": unit, "Control": name,
                "Baseline (%)": baseline_values[name],
                "Scenario (%)": values[name], "Change (pp)": change,
                "State": source if abs(change) > 1e-8 else "Unchanged",
            })
            if abs(change) > 1e-8:
                changes.append({
                    "Variable": LABELS.get(name, name),
                    "Internal name": name, "Unit": unit,
                    "Baseline (%)": baseline_values[name],
                    "Requested (%)": requested.get(name, np.nan),
                    "Scenario (%)": values[name], "Change (pp)": change,
                    "Source": source,
                    "Hard-constraint projection (pp)": (
                        values[name] - requested[name] if name in requested else 0.0
                    ),
                })

        adjustments = pd.concat(
            [first_adjustments, final_adjustments], ignore_index=True
        ).drop_duplicates() if not first_adjustments.empty or not final_adjustments.empty else pd.DataFrame()

        return {
            "row": row, "values": values, "direct": requested,
            "direct_order": order, "direct_accepted": accepted,
            "propagation": pd.DataFrame(changes),
            "latent": pd.DataFrame(state_rows),
            "observed_latents": sorted(touched_units),
            "observed_units": sorted(touched_units),
            "coherence": self.coherence_diagnostics(row),
            "propagation_caps": pd.DataFrame(caps),
            "battery_adjustments": adjustments,
            "feedback_iterations": int(iterations),
            "feedback_residual": float(residual),
        }


class NationalScenarioEngine:
    def __init__(self, model_path: Path):
        self.model_path = Path(model_path)
        (self.frame, self.target_columns, self.feature_columns,
         self.categorical, self.numeric) = _parse_model(self.model_path)
        self.train = self.frame.loc[self.frame["Midterm Year"].lt(2026)].copy()
        self.production = self.frame.loc[self.frame["Midterm Year"].eq(2026)].copy()
        self.popular_columns = [c for c in self.target_columns if c in {"DPP", "RPP"}]
        self.house_columns = [c for c in self.target_columns if c.startswith(("DHou", "RHou"))]
        self.senate_columns = [c for c in self.target_columns if c.startswith(("DSen", "RSen"))]
        self.learned_columns = self.popular_columns + self.house_columns + self.senate_columns
        self.model = _ridge_pipeline(self.categorical, self.numeric, alpha=10.0)
        self.model.fit(
            self.train[self.feature_columns],
            self.train[self.learned_columns].to_numpy(dtype=np.float64),
        )
        self.model_baseline_vector = np.asarray(
            self.model.predict(self.production[self.feature_columns]), dtype=float
        )[0]
        self.model_baseline_raw = dict(zip(self.learned_columns, self.model_baseline_vector.tolist()))
        self.official_baseline_targets = {str(k): float(v) for k, v in OFFICIAL_BASELINE_TARGETS.items()}
        missing_official = [c for c in self.learned_columns if c not in self.official_baseline_targets]
        if missing_official:
            raise ValueError(f"Official Scenario baseline is missing targets: {missing_official}")
        self.official_baseline_headline = {str(k): int(v) for k, v in OFFICIAL_BASELINE_HEADLINE.items()}
        baseline_projected = self._project_42(self.official_baseline_targets, self.production.iloc[0])
        self.house_d_seat_calibration = int(
            self.official_baseline_headline["D House Seats"] - baseline_projected["D House After"]
        )
        self.senate_d_seat_calibration = int(
            self.official_baseline_headline["D Senate Seats"] - baseline_projected["D Senate After"]
        )
        historical_other = 1.0 - self.train["DPP"].to_numpy(dtype=float) - self.train["RPP"].to_numpy(dtype=float)
        self.other_vote_share = float(np.clip(np.nanmean(historical_other), 0.0, 0.15))
        self.premodel = NationalStatePremodel(self.train, self.production)
        self.input_specs = self._build_input_specs()
        self.baseline_popular_anchor = self._official_popular_anchor(self.production)
        self.baseline = self.predict({})

    def _build_input_specs(self) -> list[ScenarioInput]:
        row = self.production.iloc[0]
        specs: list[ScenarioInput] = []
        for group, columns in INPUT_GROUPS.items():
            for name in columns:
                baseline = float(row[name]) * 100.0
                historical = self.train[name].astype(float).to_numpy() * 100.0
                specs.append(ScenarioInput(
                    name=name, label=LABELS.get(name, name), group=group,
                    baseline=baseline, minimum=0.0, maximum=100.0,
                    historical_minimum=float(np.nanmin(historical)),
                    historical_maximum=float(np.nanmax(historical)), step=0.5,
                ))
        return specs

    def _official_popular_anchor(self, scenario: pd.DataFrame) -> dict[str, float]:
        d = float(scenario.iloc[0]["EDPP"]); r = float(scenario.iloc[0]["ERPP"])
        if d + r <= 0:
            raise ValueError("EDPP and ERPP must have a positive two-party total.")
        d_two_party = float(np.clip(d / (d + r), 0.0, 1.0))
        allocated = 1.0 - self.other_vote_share
        return {"DPP": allocated * d_two_party, "RPP": allocated * (1.0 - d_two_party), "OTHER": self.other_vote_share}

    def _project_42(self, raw: dict[str, float], row: pd.Series) -> dict[str, float]:
        projected: dict[str, float] = {c: float(np.clip(raw[c], 0.0, 1.0)) for c in self.popular_columns}
        groups = [
            (self.house_columns, "DHou", row["DH Before"]), (self.house_columns, "RHou", row["RH Before"]),
            (self.senate_columns, "DSen", row["DSS UP"]), (self.senate_columns, "RSen", row["RSS UP"]),
        ]
        for all_columns, prefix, total in groups:
            cols = [c for c in all_columns if c.startswith(prefix)]
            projected.update(_hamilton(raw, cols, total))
        dhl = sum(projected[c] for c in _loss_columns([c for c in self.house_columns if c.startswith("DHou")], "D"))
        rhl = sum(projected[c] for c in _loss_columns([c for c in self.house_columns if c.startswith("RHou")], "R"))
        dsl = sum(projected[c] for c in _loss_columns([c for c in self.senate_columns if c.startswith("DSen")], "D"))
        rsl = sum(projected[c] for c in _loss_columns([c for c in self.senate_columns if c.startswith("RSen")], "R"))
        projected.update({
            "D House Seats LOST": int(dhl), "R House Seats Lost": int(rhl),
            "D Senate Seats LOST": int(dsl), "R Senate Seats LOST": int(rsl),
            "D House After": int(row["DH Before"] - dhl + rhl),
            "R House After": int(row["RH Before"] + dhl - rhl),
            "D Senate After": int(row["DS before"] - dsl + rsl),
            "R Senate After": int(row["RS Before"] + dsl - rsl),
        })
        return projected

    @staticmethod
    def _continuous_allocation(raw: Mapping[str, float], columns: list[str], total: float) -> dict[str, float]:
        values = np.asarray([max(float(raw.get(c, 0.0)), 0.0) for c in columns])
        if not np.isfinite(values).all() or float(values.sum()) <= 0.0:
            raise ValueError("Scenario bucket predictions have a non-positive total.")
        quotas = values / values.sum() * float(total)
        return dict(zip(columns, quotas.tolist()))

    def _smooth_headline(self, raw: Mapping[str, float], row: pd.Series) -> dict[str, float]:
        d_house = [c for c in self.house_columns if c.startswith("DHou")]
        r_house = [c for c in self.house_columns if c.startswith("RHou")]
        d_senate = [c for c in self.senate_columns if c.startswith("DSen")]
        r_senate = [c for c in self.senate_columns if c.startswith("RSen")]
        dh = self._continuous_allocation(raw, d_house, row["DH Before"])
        rh = self._continuous_allocation(raw, r_house, row["RH Before"])
        ds = self._continuous_allocation(raw, d_senate, row["DSS UP"])
        rs = self._continuous_allocation(raw, r_senate, row["RSS UP"])
        dhl = sum(dh[c] for c in _loss_columns(d_house, "D")); rhl = sum(rh[c] for c in _loss_columns(r_house, "R"))
        dsl = sum(ds[c] for c in _loss_columns(d_senate, "D")); rsl = sum(rs[c] for c in _loss_columns(r_senate, "R"))
        return {
            "D House Expected": float(row["DH Before"] - dhl + rhl),
            "D Senate Expected": float(row["DS before"] - dsl + rsl),
            "D-Held Senate Loss Pressure": float(dsl),
            "R-Held Senate Loss Pressure": float(rsl),
        }

    def predict(self, overrides: Mapping[str, Any]) -> dict[str, Any]:
        reconciled = self.premodel.reconcile(overrides)
        scenario = self.production.copy()
        for name, value in reconciled["values"].items():
            scenario.loc[:, name] = float(value) / 100.0
        scenario.loc[:, "DEM NET FAVORABILITY"] = scenario["DEM FAVORABLE"] - scenario["DEM UNFAVORABLE"]
        scenario.loc[:, "REP NET FAVORABILITY"] = scenario["REP FAVORABLE"] - scenario["REP UNFAVORABLE"]

        prediction = np.asarray(self.model.predict(scenario[self.feature_columns]), dtype=float)[0]
        model_scenario_raw = dict(zip(self.learned_columns, prediction.tolist()))

        # Central-model delta-on-official baseline. The official snapshot is an
        # exact identity; the fitted Ridge is used only for response gradients.
        raw = {}
        for column in self.learned_columns:
            raw[column] = float(
                self.official_baseline_targets[column]
                + (model_scenario_raw[column] - self.model_baseline_raw[column])
            )

        # Popular vote follows the production-selected ExpectedVoteAnchor. Keep
        # the official Other share fixed and apply only the two-party-share delta
        # implied by the reconciled EDPP/ERPP scenario.
        anchor = self._official_popular_anchor(scenario)
        base_anchor = self.baseline_popular_anchor
        official_d = float(self.official_baseline_targets["DPP"])
        official_r = float(self.official_baseline_targets["RPP"])
        official_allocated = max(official_d + official_r, 1e-12)
        official_d2 = official_d / official_allocated
        anchor_d2 = anchor["DPP"] / max(anchor["DPP"] + anchor["RPP"], 1e-12)
        base_anchor_d2 = base_anchor["DPP"] / max(base_anchor["DPP"] + base_anchor["RPP"], 1e-12)
        scenario_d2 = float(np.clip(official_d2 + (anchor_d2 - base_anchor_d2), 0.0, 1.0))
        raw["DPP"] = official_allocated * scenario_d2
        raw["RPP"] = official_allocated * (1.0 - scenario_d2)

        targets = self._project_42(raw, scenario.iloc[0])
        # The 42 bucket model supplies scenario deltas, while the audited
        # district/state layer owns the official chamber headline. Apply the
        # fixed baseline calibration to preserve exact zero-intervention
        # identity without changing any learned response gradient.
        targets["D House After"] = int(np.clip(
            targets["D House After"] + self.house_d_seat_calibration, 0, 435
        ))
        targets["R House After"] = 435 - targets["D House After"]
        targets["D Senate After"] = int(np.clip(
            targets["D Senate After"] + self.senate_d_seat_calibration, 0, 100
        ))
        targets["R Senate After"] = 100 - targets["D Senate After"]
        smooth_headline = self._smooth_headline(raw, scenario.iloc[0])
        dpp = targets["DPP"] * 100.0; rpp = targets["RPP"] * 100.0

        battery_status = []
        for battery, columns in COMPOSITION_BATTERIES.items():
            total = 100.0 * float(scenario.iloc[0][columns].astype(float).sum())
            battery_status.append({
                "Battery": battery, "Total (%)": total,
                "Unallocated / other (%)": max(0.0, 100.0 - total),
                "Valid": bool(total <= 100.0 + 1e-8),
            })
        spec_by_name = {spec.name: spec for spec in self.input_specs}
        outside_support = []
        for name, value in reconciled["values"].items():
            spec = spec_by_name[name]
            if value < spec.historical_minimum - 1e-9 or value > spec.historical_maximum + 1e-9:
                if name in reconciled["direct"]:
                    source = "Direct intervention"
                elif CONTROL_TO_UNIT[name] in set(reconciled.get("observed_units", [])):
                    source = "Hard battery constraint"
                else:
                    source = "Premodel propagation"
                outside_support.append({
                    "Variable": spec.label, "Scenario (%)": value,
                    "Historical min (%)": spec.historical_minimum,
                    "Historical max (%)": spec.historical_maximum,
                    "Source": source,
                    "Changed from baseline": abs(value - spec.baseline) > 1e-8,
                    "Baseline already outside support": bool(
                        spec.baseline < spec.historical_minimum - 1e-9
                        or spec.baseline > spec.historical_maximum + 1e-9
                    ),
                })
        popular_components = {
            "Anchor D popular vote (%)": 100.0 * raw["DPP"],
            "Anchor R popular vote (%)": 100.0 * raw["RPP"],
            "Other / unallocated (%)": 100.0 * (1.0 - raw["DPP"] - raw["RPP"]),
            "Scenario D-R margin (pp)": dpp - rpp,
            "Reconciled EDPP (%)": float(scenario.iloc[0]["EDPP"]) * 100.0,
            "Reconciled ERPP (%)": float(scenario.iloc[0]["ERPP"]) * 100.0,
        }
        return {
            "targets": targets,
            "smooth_headline": smooth_headline,
            "headline": {
                "D Popular Vote (%)": dpp, "R Popular Vote (%)": rpp,
                "D-R Popular Margin (pp)": dpp - rpp,
                "D House Seats": targets["D House After"], "R House Seats": targets["R House After"],
                "D Senate Seats": targets["D Senate After"], "R Senate Seats": targets["R Senate After"],
            },
            "changed_inputs": reconciled["propagation"],
            "direct_overrides": reconciled["direct"],
            "direct_order": reconciled.get("direct_order", []),
            "direct_accepted": reconciled.get("direct_accepted", reconciled["direct"]),
            "reconciled_values": reconciled["values"],
            "latent_state": reconciled["latent"],
            "coherence": reconciled.get("coherence", {}),
            "propagation_caps": reconciled.get("propagation_caps", pd.DataFrame()),
            "battery_adjustments": reconciled.get("battery_adjustments", pd.DataFrame()),
            "feedback_iterations": reconciled.get("feedback_iterations", 0),
            "feedback_residual": reconciled.get("feedback_residual", 0.0),
            "battery_status": pd.DataFrame(battery_status),
            "outside_support": pd.DataFrame(outside_support),
            "popular_vote_components": popular_components,
            "premodel": {
                "intervention_units": len(INTERVENTION_UNITS),
                "composition_batteries": len(COMPOSITION_BATTERIES),
                "relationship_shrinkage": self.premodel.relationship_shrinkage,
                "maximum_row_leverage": self.premodel.MAX_ROW_LEVERAGE,
                "observed_units": reconciled.get("observed_units", []),
                "coherence": reconciled.get("coherence", {}),
                "baseline_contract": "official 42-target identity + delta response",
            },
        }


def normalize_composition_values(values: Mapping[str, float | None], changed_name: str | None) -> dict[str, float]:
    """UI helper retained for compatibility; values may sum below 100, never above."""
    normalized = {name: float(np.clip(0.0 if value is None else value, 0.0, 100.0)) for name, value in values.items()}
    for columns in COMPOSITION_BATTERIES.values():
        if not all(column in normalized for column in columns):
            continue
        total = sum(normalized[column] for column in columns)
        if total <= 100.0 + 1e-9:
            continue
        anchor = changed_name if changed_name in columns else columns[0]
        peers = [column for column in columns if column != anchor]
        remaining = max(0.0, 100.0 - normalized[anchor])
        peer_total = sum(normalized[column] for column in peers)
        if peer_total <= 1e-12:
            for column in peers:
                normalized[column] = 0.0
        else:
            for column in peers:
                normalized[column] = normalized[column] * remaining / peer_total
    return normalized


@lru_cache(maxsize=2)
def load_scenario_engine(model_path: str, model_mtime_ns: int | None = None) -> NationalScenarioEngine:
    return NationalScenarioEngine(Path(model_path))
