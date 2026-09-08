from __future__ import annotations

import argparse
import hashlib
import re
from pathlib import Path

import numpy as np
import pandas as pd

from core import (
    DASH_DIR,
    MODEL_PATH,
    HOUSE_PATHS_PATH,
    BRAND_LOGO_PATH,
    latest_report_path,
    latest_html_path,
    load_bundle,
    load_senate_map,
    project_signature,
)
from figures import scenario_house_summary, scenario_senate_summary
from scenario_engine import COMPOSITION_BATTERIES, ENGINE_VERSION, INPUT_GROUPS, INTERVENTION_UNITS, OFFICIAL_BASELINE_HEADLINE, RUNTIME_PATH, load_scenario_engine

EXPECTED_MAJOR = 27
EXPECTED_MINOR = 1

parser = argparse.ArgumentParser(description="Validate the downstream v27.1 Dash / Scenario Lab package.")
parser.add_argument("--deep", action="store_true", help="Run all 31 controls at 0/100 through the geographic translators.")
ARGS = parser.parse_args()
REPORT_RE = re.compile(r"Election_Model_Final_Report_v(\d+)(?:[_\.](\d+))?\.xlsx$", re.I)


def version_tuple(path: Path) -> tuple[int, int]:
    m = REPORT_RE.search(path.name)
    if not m:
        return (-1, -1)
    return int(m.group(1)), int(m.group(2) or 0)


def kv(df: pd.DataFrame) -> dict[str, object]:
    if df.empty or df.shape[1] < 2:
        return {}
    return dict(zip(df.iloc[:, 0].astype(str), df.iloc[:, 1]))


def close(a, b, tol=1e-8):
    return bool(np.isclose(float(a), float(b), atol=tol, rtol=0.0))


signature = project_signature()
bundle = load_bundle(signature)
report = bundle["report_path"]
major, minor = version_tuple(report)
model_sha = hashlib.sha256(MODEL_PATH.read_bytes()).hexdigest() if MODEL_PATH.exists() else ""
run_meta = bundle["run_metadata"]
source_sha = str(run_meta.get("Source SHA-256", "")).strip()

# Official dashboard headline.
d = bundle["dashboard"]
o_house_d = int(float(d["Democratic House Seats"]))
o_house_r = int(float(d["Republican House Seats"]))
o_sen_d = int(float(d["Democratic Senate Seats"]))
o_sen_r = int(float(d["Republican Senate Seats"]))

# Runtime zero-intervention identity.
engine = load_scenario_engine(str(MODEL_PATH), MODEL_PATH.stat().st_mtime_ns)
baseline = engine.predict({})
headline = baseline["headline"]

senate_map = load_senate_map(signature)
production_row = engine.production.iloc[0]
fixed_non_up_d = int(round(float(production_row["DS before"] - production_row["DSS UP"])))
house_zero, house_summary = scenario_house_summary(bundle["house"], 0.0, 0.0)
sen_zero, senate_summary = scenario_senate_summary(
    senate_map, bundle["senate"], 0.0, fixed_non_up_d, 0.0
)
scenario_house_d = int(house_summary["D seats by median winner"])
scenario_sen_d = int(senate_summary["D seats by race winner"])

# Central forecast contract.
central_contract = bundle["sheets"].get("CentralForecastContract", pd.DataFrame())
central_contract_pass = (
    not central_contract.empty
    and "Passed" in central_contract.columns
    and central_contract["Passed"].astype(bool).all()
)

# House modal contract.
house_sim = kv(bundle["sheets"].get("HouseSimulationSummary", pd.DataFrame()))
house_mode_match = (
    int(round(float(house_sim.get("Official Monte Carlo modal Democratic seats", -999)))) == o_house_d
    and int(round(float(house_sim.get("Official Monte Carlo modal Republican seats", -999)))) == o_house_r
)

# Senate modal + exact-pattern contract.
sen_account = kv(bundle["sheets"].get("SenateSeatAccounting", pd.DataFrame()))
sen_patterns = bundle["sheets"].get("SenateCentralPatterns", pd.DataFrame())
selected_pattern_count = 0
if not sen_patterns.empty and "Selected Central Pattern" in sen_patterns.columns:
    selected_pattern_count = int(sen_patterns["Selected Central Pattern"].astype(bool).sum())
senate_account_match = (
    int(round(float(sen_account.get("Official central Democratic seats", -999)))) == o_sen_d
    and int(round(float(sen_account.get("Official central Republican seats", -999)))) == o_sen_r
    and selected_pattern_count == 1
)

# Senate race-level public tuple coherence.
sen = bundle["senate"].copy()
required_sen_cols = {
    "Central Forecast Margin 2P", "Central Forecast Sigma PP",
    "D Win Probability", "R Win Probability", "Projected Winner",
    "Forecast Rating", "Projected D 2P", "Projected R 2P",
    "Marginal D Win Probability", "Marginal R Win Probability",
}
sen_schema_ok = required_sen_cols.issubset(set(sen.columns))
if sen_schema_ok:
    margin = pd.to_numeric(sen["Central Forecast Margin 2P"], errors="coerce")
    dprob = pd.to_numeric(sen["D Win Probability"], errors="coerce")
    rprob = pd.to_numeric(sen["R Win Probability"], errors="coerce")
    d2p = pd.to_numeric(sen["Projected D 2P"], errors="coerce")
    r2p = pd.to_numeric(sen["Projected R 2P"], errors="coerce")
    winners = sen["Projected Winner"].astype(str)
    senate_tuple_ok = bool(
        np.isfinite(margin).all()
        and np.isfinite(dprob).all()
        and np.isfinite(rprob).all()
        and np.isfinite(pd.to_numeric(sen["Central Forecast Sigma PP"], errors="coerce")).all()
        and np.allclose(dprob + rprob, 100.0, atol=0.02)
        and ((margin > 0) == winners.eq("D")).all()
        and ((dprob >= 50) == winners.eq("D")).all()
        and np.allclose(d2p - r2p, margin, atol=0.04)
    )
else:
    senate_tuple_ok = False

# Static source contract: public Senate rendering must use central fields.
source_text = "\n".join(
    (DASH_DIR / name).read_text(encoding="utf-8")
    for name in ["core.py", "app.py", "figures.py", "views.py", "scenario_engine.py"]
)
public_central_source_ok = (
    '"Central Forecast Margin 2P"' in source_text
    and '"Central Forecast Sigma PP"' in source_text
    and "scenario_state_engine_v27.py" in source_text
)

# Exact notebook HTML parity contract. The Forecast tab serves this file 1:1.
html_path = latest_html_path()
expected_html_sections = [
    "Congress at a glance",
    "The House, district by district",
    "Explore all 435 forecasts",
    "House flips — auditable district by district",
    "District cartogram",
    "The Senate, race by race",
    "Control Probability",
    "Monte Carlo Seat Distribution",
    "National Context Indicators",
    "Senate Flips",
    "Time-Machine Historical Validation",
    "Model Quality",
    "Electoral Risk",
    "Final Uncertainty Snapshot",
]
if html_path is not None:
    html_text = html_path.read_text(encoding="utf-8", errors="replace")
    html_sections_ok = all(section in html_text for section in expected_html_sections)
    html_house_total_ok = (
        f">{o_house_d}<" in html_text and f">{o_house_r}<" in html_text
    )
    html_senate_total_ok = (
        f">{o_sen_d}<" in html_text and f">{o_sen_r}<" in html_text
    )
else:
    html_text = ""
    html_sections_ok = html_house_total_ok = html_senate_total_ok = False

# Scenario Lab shape / interaction contract.
scenario_shape_ok = (
    len(engine.input_specs) == 31
    and len(INTERVENTION_UNITS) == 14
    and len(COMPOSITION_BATTERIES) == 12
    and len(baseline["targets"]) == 42
)

# Same-battery newest edit wins only when necessary.
same_battery = engine.predict({
    "values": {"Presidential Approval": 80.0, "Presidential Disapproval": 80.0},
    "order": ["Presidential Approval", "Presidential Disapproval"],
})
same_values = same_battery["reconciled_values"]
same_battery_priority_ok = (
    close(same_values["Presidential Disapproval"], 80.0, 1e-6)
    and close(same_values["Presidential Approval"] + same_values["Presidential Disapproval"], 100.0, 1e-6)
)

# Compatible direct edits in different batteries must persist.
cross_battery = engine.predict({
    "values": {"Presidential Approval": 60.0, "Right Track": 55.0},
    "order": ["Presidential Approval", "Right Track"],
})
cross_values = cross_battery["reconciled_values"]
cross_battery_persistence_ok = (
    close(cross_values["Presidential Approval"], 60.0, 1e-6)
    and close(cross_values["Right Track"], 55.0, 1e-6)
)

# Static UI contract: the visible House Scenario headline must come from the
# district winners on the map, never from rounded expected seat mass.
app_source = (DASH_DIR / "app.py").read_text(encoding="utf-8")
views_source = (DASH_DIR / "views.py").read_text(encoding="utf-8")
core_source = (DASH_DIR / "core.py").read_text(encoding="utf-8")
scenario_headline_source_ok = (
    'house_projected_d = int(round(float(house_summary["D seats by median winner"])))' in app_source
    and 'house_projected_d = int(round(float(house_summary["Expected D seats"])))' not in app_source
    and 'House seats · district winners' in app_source
)
forecast_surface_source_ok = (
    'dcc.Tab(label="All-in-One", value="forecast"' in app_source
    and '@server.route("/forecast-html")' in app_source
    and 'html.Iframe(' in views_source
    and 'Election_Model(?:_2026_Dashboard)?_v' in core_source
)
scenario_tab_source_ok = 'dcc.Tab(label="Scenario Lab", value="scenario"' in app_source
branding_source_ok = (
    'html.Div("Nucleus 42", className="brand-name")' in app_source
    and 'Independent U.S. Election Forecasting System' in app_source
    and 'NUCLEUS 42' in app_source
    and 'Independent U.S. Election Forecasting System' in app_source
)
senate_consensus_removed_ok = "Monitored source consensus" not in views_source
native_explorer_source_ok = (
    'dcc.Tab(label="Explore House", value="house"' in app_source
    and 'dcc.Tab(label="Explore Senate", value="senate"' in app_source
    and 'dcc.Tab(label="Methodology", value="context"' in app_source
    and 'seat_change_strip(b, "House")' in views_source
    and 'seat_change_strip(b, "Senate")' in views_source
)
house_consensus_runtime_ok = (
    "Source Consensus Rating" in bundle["house"].columns
    and len(bundle["house"]) == 435
    and int(bundle["house"]["Source Consensus Rating"].notna().sum()) == 435
    and set(bundle["house"]["Source Consensus Rating"].astype(str)).issubset(
        {"Safe D","Likely D","Lean D","Tilt D","Toss-Up","Tilt R","Lean R","Likely R","Safe R"}
    )
)
house_consensus_matches_notebook_contract = (
    "v27 Rating Consensus Rating" in bundle["house"].columns
    and (
        bundle["house"]["Source Consensus Rating"].astype(str)
        == bundle["house"]["v27 Rating Consensus Rating"].astype(str)
    ).all()
)
house_flip_table_ok = (
    not bundle["sheets"].get("HouseFlipAudit", pd.DataFrame()).empty
    and int((bundle["sheets"]["HouseFlipAudit"]["Projected Flip"] == "R→D").sum()) == int(float(kv(bundle["sheets"]["HouseSeatAccounting"]).get("Democratic flips (R→D)", -1)))
    and int((bundle["sheets"]["HouseFlipAudit"]["Projected Flip"] == "D→R").sum()) == int(float(kv(bundle["sheets"]["HouseSeatAccounting"]).get("Republican flips (D→R)", -1)))
)
senate_flip_table_ok = (
    not bundle["sheets"].get("SenateModelFlips", pd.DataFrame()).empty
    and len(bundle["sheets"]["SenateModelFlips"]) == int(float(d.get("Senate Assigned Flips", -1)))
)

# Optional exhaustive one-at-a-time 0/100 checks: 62 counterfactual runs.
deep_oat_ok = True
deep_oat_runs = 0
deep_oat_failures = []
if ARGS.deep:
    for spec in engine.input_specs:
        for endpoint in (0.0, 100.0):
            test_result = engine.predict({"values": {spec.name: endpoint}, "order": [spec.name]})
            cur = test_result["headline"]
            base_cur = engine.baseline["headline"]
            cur_d2 = cur["D Popular Vote (%)"] / max(cur["D Popular Vote (%)"] + cur["R Popular Vote (%)"], 1e-12) * 100.0
            base_d2 = base_cur["D Popular Vote (%)"] / max(base_cur["D Popular Vote (%)"] + base_cur["R Popular Vote (%)"], 1e-12) * 100.0
            share_swing = cur_d2 - base_d2
            margin_swing = 2.0 * share_swing
            hdata, hsum = scenario_house_summary(bundle["house"], share_swing, 0.0)
            sdata, ssum = scenario_senate_summary(senate_map, bundle["senate"], margin_swing, fixed_non_up_d, 0.0)
            house_margin = pd.to_numeric(hdata["Scenario Vote Margin PP"], errors="coerce")
            house_winner = hdata["Scenario Winner"].astype(str)
            house_prob = pd.to_numeric(hdata["Scenario D Win Probability"], errors="coerce")
            senate_margin = pd.to_numeric(sdata["Scenario Margin PP"], errors="coerce")
            senate_winner = sdata["Scenario Winner"].astype(str)
            senate_prob = pd.to_numeric(sdata["Scenario D Win Probability"], errors="coerce")
            run_ok = bool(
                ((house_margin >= 0) == house_winner.eq("D")).all()
                and ((house_prob >= 50) == house_winner.eq("D")).all()
                and ((senate_margin >= 0) == senate_winner.eq("D")).all()
                and ((senate_prob >= 50) == senate_winner.eq("D")).all()
                and int(hsum["D seats by median winner"] + hsum["R seats by median winner"]) == 435
                and int(ssum["D seats by race winner"] + ssum["R seats by race winner"]) == 100
            )
            deep_oat_runs += 1
            if not run_ok:
                deep_oat_failures.append(f"{spec.name}={endpoint}")
    deep_oat_ok = len(deep_oat_failures) == 0

# The package must remain downstream; no private duplicate data/model artifacts.
forbidden = []
for pattern in ["*.xlsx", "*.xls", "*.ipynb", "scenario_state_engine_v*.py", "house_cd120*.gz", "*.html"]:
    forbidden.extend(DASH_DIR.rglob(pattern))

required_sheets = [
    "Dashboard_Data", "RunMetadata", "FinalProjection", "HouseRaceDetail",
    "SenateRaceDetail", "SenateSafeBaselines", "ControlProbability",
    "MonteCarloSample", "CentralForecastContract", "HouseSimulationSummary",
    "SenateSeatAccounting", "SenateCentralPatterns", "HouseFlipAudit", "SenateModelFlips", "ScenarioEngineContract",
    "ScenarioLabSource", "Scenario42Coherence", "ScenarioSenateSwingAudit",
]

checks = {
    "v27.1 audited report detected": (major, minor) >= (EXPECTED_MAJOR, EXPECTED_MINOR),
    "Model.xlsx exists": MODEL_PATH.exists(),
    "Report source SHA matches Model.xlsx": bool(source_sha and source_sha == model_sha),
    "v27 Scenario runtime exists": RUNTIME_PATH.exists() and ENGINE_VERSION == "v27",
    "House geometry asset exists": HOUSE_PATHS_PATH.exists(),
    "Brand asset exists": BRAND_LOGO_PATH.exists(),
    "Required v27.1 sheets present": all(name in bundle["sheet_names"] for name in required_sheets),
    "HouseRaceDetail has 435 districts": len(bundle["house"]) == 435,
    "SenateRaceDetail has 11 monitored races": len(bundle["senate"]) == 11,
    "SenateSafeBaselines has 24 scenario-only safe races": len(bundle["senate_safe_baselines"]) == 24,
    "Senate map has 50 states / 35 scheduled elections": len(senate_map) == 50 and int(senate_map["Tier"].ne("None").sum()) == 35,
    "CentralForecastContract all PASS": bool(central_contract_pass),
    "House official headline equals Monte Carlo mode": bool(house_mode_match),
    "Senate official headline equals modal accounting / one selected pattern": bool(senate_account_match),
    "Senate public central tuple is coherent": bool(senate_tuple_ok),
    "Runtime official baseline headline equals report": (
        int(OFFICIAL_BASELINE_HEADLINE.get("D House Seats", -1)) == o_house_d
        and int(OFFICIAL_BASELINE_HEADLINE.get("R House Seats", -1)) == o_house_r
        and int(OFFICIAL_BASELINE_HEADLINE.get("D Senate Seats", -1)) == o_sen_d
        and int(OFFICIAL_BASELINE_HEADLINE.get("R Senate Seats", -1)) == o_sen_r
    ),
    "Scenario engine zero-intervention national headline equals report": (
        int(headline["D House Seats"]) == o_house_d
        and int(headline["R House Seats"]) == o_house_r
        and int(headline["D Senate Seats"]) == o_sen_d
        and int(headline["R Senate Seats"]) == o_sen_r
    ),
    "Scenario House geographic reset equals official forecast": scenario_house_d == o_house_d,
    "Scenario Senate geographic reset equals official forecast": scenario_sen_d == o_sen_d,
    "Dash source references v27 central Senate tuple/runtime": bool(public_central_source_ok),
    "Final notebook HTML detected": html_path is not None,
    "Final HTML exposes all required v27.1 visual sections": bool(html_sections_ok),
    "Final HTML contains current House central totals": bool(html_house_total_ok),
    "Final HTML contains current Senate central totals": bool(html_senate_total_ok),
    "Scenario Lab has 31 controls / 14 units / 12 batteries / 42 targets": bool(scenario_shape_ok),
    "Scenario Lab latest-edit battery priority works": bool(same_battery_priority_ok),
    "Scenario Lab compatible cross-battery edits persist": bool(cross_battery_persistence_ok),
    "Scenario visible House headline is district-winner based": bool(scenario_headline_source_ok),
    "All-in-One tab serves exact notebook HTML": bool(forecast_surface_source_ok),
    "Native Explore House/Senate + Methodology tabs are wired": bool(native_explorer_source_ok),
    "House source consensus covers all 435 districts": bool(house_consensus_runtime_ok),
    "House source consensus matches notebook v27 contract exactly": bool(house_consensus_matches_notebook_contract),
    "House flip explorer matches seat accounting": bool(house_flip_table_ok),
    "Senate flip explorer matches dashboard accounting": bool(senate_flip_table_ok),
    "Nucleus 42 independent branding is active": bool(branding_source_ok),
    "Explore Senate does not invent a source-consensus layer": bool(senate_consensus_removed_ok),
    "Scenario Lab tab name restored": bool(scenario_tab_source_ok),
    "Deep 31-control endpoint geography/coherence audit": bool(deep_oat_ok),
    "Dash package contains no duplicated model/report/runtime/html assets": len(forbidden) == 0,
}

print("Dash v27.1 setup check")
print("----------------------")
print("Report:", report.name)
print("Report version:", f"{major}.{minor}")
print("Scenario runtime:", RUNTIME_PATH.name, "·", ENGINE_VERSION)
print("Source snapshot SHA match:", source_sha == model_sha)
print("House central:", f"D{o_house_d}-R{o_house_r}")
print("Senate central:", f"D{o_sen_d}-R{o_sen_r}")
print("House rows:", len(bundle["house"]))
print("Senate monitored / Safe:", len(bundle["senate"]), "/", len(bundle["senate_safe_baselines"]))
print("Scenario reset House D:", scenario_house_d)
print("Scenario reset Senate D:", scenario_sen_d)
print("Selected Senate central patterns:", selected_pattern_count)
print("Final HTML:", html_path.name if html_path else "missing")
print("Scenario controls / units / batteries / targets:", len(engine.input_specs), "/", len(INTERVENTION_UNITS), "/", len(COMPOSITION_BATTERIES), "/", len(baseline["targets"]))
if ARGS.deep:
    print("Deep OAT runs:", deep_oat_runs, "failures:", deep_oat_failures or "none")
print("Forbidden private copies:", [str(p.relative_to(DASH_DIR)) for p in forbidden] or "none")
print("\nChecks")
for label, passed in checks.items():
    print(f"[{'PASS' if passed else 'FAIL'}] {label}")

ok = all(checks.values())
print("\nSTATUS:", "OK" if ok else "CHECK REQUIRED")
if not ok:
    raise SystemExit(1)
