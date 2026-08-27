from __future__ import annotations

import hashlib
import re
import shutil
import sys
from pathlib import Path

sys.dont_write_bytecode = True

import numpy as np
import pandas as pd

from core import (
    BRAND_LOGO_PATH, DASH_DIR, MODEL_PATH, load_bundle, load_house_paths,
    load_senate_map, project_signature,
)
from figures import scenario_house_summary, scenario_senate_summary
from scenario_engine import (
    COMPOSITION_BATTERIES,
    INTERVENTION_UNITS,
    RUNTIME_PATH,
    load_scenario_engine,
)

EXPECTED_VERSION = 26
sig = project_signature()
bundle = load_bundle(sig)
paths = load_house_paths()
senate_map = load_senate_map(sig)
engine = load_scenario_engine(str(MODEL_PATH), MODEL_PATH.stat().st_mtime_ns)

report_match = re.search(r"_v(\d+)\.xlsx$", bundle["report_path"].name)
html_name = Path(bundle["html_path"]).name if bundle.get("html_path") else ""
html_match = re.search(r"_v(\d+)\.html$", html_name)
report_version = int(report_match.group(1)) if report_match else -1
html_version = int(html_match.group(1)) if html_match else -2

shutil.rmtree(DASH_DIR / "__pycache__", ignore_errors=True)

forbidden = []
for pattern in (
    "Model*.xlsx", "Election_Model_Final_Report*.xlsx", "Election_Model_2026_Dashboard*.html",
    "house_cd120*.gz", "Midterms_2026_Logo.svg", "scenario_state_engine_v26.py",
):
    forbidden.extend(DASH_DIR.glob(pattern))
for name in ("outputs", ".venv", "__pycache__", ".ipynb_checkpoints", "__MACOSX"):
    if (DASH_DIR / name).exists():
        forbidden.append(DASH_DIR / name)

# Snapshot provenance: Scenario Lab must never combine a new Model.xlsx with an old report/runtime.
source_sha = str(bundle["run_metadata"].get("Source SHA-256", "")).strip()
current_sha = hashlib.sha256(MODEL_PATH.read_bytes()).hexdigest() if MODEL_PATH.exists() else ""
model_snapshot_match = bool(source_sha) and source_sha == current_sha
runtime_text = RUNTIME_PATH.read_text(encoding="utf-8") if RUNTIME_PATH.exists() else ""
runtime_safe = "store_precision=False" in runtime_text
runtime_v26 = 'ENGINE_VERSION = "v26"' in runtime_text
core_text = (DASH_DIR / "core.py").read_text(encoding="utf-8")
app_text = (DASH_DIR / "app.py").read_text(encoding="utf-8")
views_text = (DASH_DIR / "views.py").read_text(encoding="utf-8")
css_text = (DASH_DIR / "assets" / "dash_v2.css").read_text(encoding="utf-8")
structured_senate_map = (
    "SENATE_STATE_GRID" in core_text
    and "HTMLParser" not in core_text
    and "parser.feed" not in core_text
)
single_scenario_store = (
    app_text.count('id="scenario-direct-overrides"') == 1
    and 'id="scenario-direct-overrides"' not in views_text
)

# v26.1 is a presentation-only release. These contracts guard the requested
# information hierarchy without changing the v26 model/runtime contract.
scenario_order_ok = all(
    token in views_text
    for token in (
        'id="scenario-national-summary"',
        'className="scenario-slider-grid"',
        'id="scenario-house-graph"',
        'id="scenario-senate-map-grid"',
    )
) and (
    views_text.index('id="scenario-national-summary"')
    < views_text.index('className="scenario-slider-grid"')
    < views_text.index('id="scenario-house-graph"')
    < views_text.index('id="scenario-senate-map-grid"')
)
control_heroes_ok = (
    'chamber_control_hero(b, "House")' in views_text
    and 'chamber_control_hero(b, "Senate")' in views_text
)
scenario_vote_map_ok = (
    'house_map_patch(house_data, "margin")' in app_text
    and 'Scenario D Two-Party Share' in (DASH_DIR / "figures.py").read_text(encoding="utf-8")
    and 'Projected two-party vote' in views_text
)
structured_senate_hover_ok = (
    'Output({"type":"scenario-senate-tooltip","state":ALL}, "children")' in app_text
    and 'className="state-rich-tooltip"' in views_text
    and '.state-rich-tooltip' in css_text
)

# Official headline values from the notebook-produced report.
def _num(value, default=np.nan):
    try:
        return float(str(value).replace("%", "").strip())
    except Exception:
        return float(default)

official_house_d = _num(bundle["dashboard"].get("Democratic House Seats"))
official_house_r = _num(bundle["dashboard"].get("Republican House Seats"))
official_sen_d = _num(bundle["dashboard"].get("Democratic Senate Seats"))
official_sen_r = _num(bundle["dashboard"].get("Republican Senate Seats"))
official_pop_d = _num(bundle["dashboard"].get("Democratic Popular Vote"))
official_pop_r = _num(bundle["dashboard"].get("Republican Popular Vote"))

# Exact zero-intervention identity in national state and 42 targets.
baseline = engine.baseline
baseline_input_identity = max(
    abs(float(baseline["reconciled_values"][spec.name]) - float(spec.baseline))
    for spec in engine.input_specs
)
baseline_target_identity = max(
    abs(float(baseline["targets"][target]) - float(engine.official_baseline_targets[target]))
    for target in engine.official_baseline_targets
)
baseline_changed_none = baseline["changed_inputs"].empty
baseline_pop_identity = (
    abs(float(baseline["headline"]["D Popular Vote (%)"]) - official_pop_d) < 0.01
    and abs(float(baseline["headline"]["R Popular Vote (%)"]) - official_pop_r) < 0.01
)
baseline_chamber_headline_identity = (
    int(baseline["headline"]["D House Seats"]) == int(official_house_d)
    and int(baseline["headline"]["R House Seats"]) == int(official_house_r)
    and int(baseline["headline"]["D Senate Seats"]) == int(official_sen_d)
    and int(baseline["headline"]["R Senate Seats"]) == int(official_sen_r)
)

# Geography: baseline Scenario projection must equal official forecast headline.
_, house_summary = scenario_house_summary(bundle["house"], 0.0, 0.0)
scenario_house_rows, _ = scenario_house_summary(bundle["house"], 0.0, 0.0)
scenario_house_d = int(round(float(house_summary["Expected D seats"])))
scenario_house_r = 435 - scenario_house_d
production_row = engine.production.iloc[0]
fixed_non_up_d = int(round(float(production_row["DS before"] - production_row["DSS UP"])))
_, senate_summary = scenario_senate_summary(
    senate_map, bundle["senate"], 0.0, fixed_non_up_d, 0.0
)
scenario_sen_d = int(round(float(senate_summary["D seats by race winner"])))
scenario_sen_r = int(round(float(senate_summary["R seats by race winner"])))
house_baseline_match = (
    np.isfinite(official_house_d) and np.isfinite(official_house_r)
    and scenario_house_d == int(official_house_d)
    and scenario_house_r == int(official_house_r)
)
senate_baseline_match = (
    np.isfinite(official_sen_d) and np.isfinite(official_sen_r)
    and scenario_sen_d == int(official_sen_d)
    and scenario_sen_r == int(official_sen_r)
)
scenario_house_vote_fields_ok = (
    {"Scenario D Two-Party Share", "Scenario Vote Margin PP", "Scenario Change vs Official"}
    .issubset(scenario_house_rows.columns)
    and np.isfinite(pd.to_numeric(scenario_house_rows["Scenario D Two-Party Share"], errors="coerce")).all()
    and np.allclose(
        pd.to_numeric(scenario_house_rows["Scenario Vote Margin PP"], errors="coerce"),
        pd.to_numeric(bundle["house"]["Projected Margin PP"], errors="coerce"),
        atol=1e-8,
    )
)

# Central Senate forecast/flip views must compare projected winner with the
# incumbent party, not reuse a stale or missing workbook label.
monitored_map = senate_map.loc[senate_map["Tier"].eq("Monitored")].copy()
senate_flip_lookup = monitored_map.set_index("STATE")["Flip"].to_dict()
senate_outcome_lookup = monitored_map.set_index("STATE")["Outcome"].to_dict()
central_senate_flip_logic_ok = (
    senate_flip_lookup.get("Maine") == "D"
    and senate_flip_lookup.get("Michigan") == "R"
    and senate_flip_lookup.get("North Carolina") == "D"
    and senate_outcome_lookup.get("Maine") == "Democratic Flip"
    and senate_outcome_lookup.get("Michigan") == "Republican Flip"
    and int(monitored_map["Flip"].astype(str).ne("").sum()) == 3
)

# Every control must be connected to the same 42-target response model. It does
# not have to move popular vote at both endpoints; neutral dimensions may act on
# chamber buckets or only one side of the learned support.
base_targets = baseline["targets"]
wired = {}
both_endpoint_target_response = {}
geography_direction_ok = {}
base_d = float(baseline["headline"]["D Popular Vote (%)"])
base_r = float(baseline["headline"]["R Popular Vote (%)"])
base_two_party_d = 100.0 * base_d / (base_d + base_r)
for spec in engine.input_specs:
    endpoint_l1 = []
    direction_checks = []
    for endpoint in (0.0, 100.0):
        result = engine.predict({spec.name: endpoint})
        l1 = float(sum(abs(float(result["targets"][k]) - float(base_targets[k])) for k in base_targets))
        endpoint_l1.append(l1)
        d = float(result["headline"]["D Popular Vote (%)"])
        r = float(result["headline"]["R Popular Vote (%)"])
        scenario_two_party_d = 100.0 * d / (d + r)
        share_swing = scenario_two_party_d - base_two_party_d
        _, hs = scenario_house_summary(bundle["house"], share_swing, 0.0)
        _, ss = scenario_senate_summary(
            senate_map, bundle["senate"], 2.0 * share_swing, fixed_non_up_d, 0.0
        )
        house_delta = float(hs["Expected D seats"] - house_summary["Expected D seats"])
        senate_delta = float(ss["Expected D seats"] - senate_summary["Expected D seats"])
        direction_checks.append(
            abs(share_swing) <= 1e-10
            or (house_delta * share_swing >= -1e-8 and senate_delta * share_swing >= -1e-8)
        )
    wired[spec.name] = max(endpoint_l1) > 1e-8
    both_endpoint_target_response[spec.name] = min(endpoint_l1) > 1e-8
    geography_direction_ok[spec.name] = all(direction_checks)

# Combined coherent partisan stress directions, learned rather than hard-coded per slider.
base_margin = float(baseline["headline"]["D-R Popular Margin (pp)"])
r_strength = engine.predict({
    "Presidential Approval": 80, "Right Track": 60, "Conservatives": 55,
    "Rep % Reg": 50, "REP FAVORABLE": 65,
})
d_strength = engine.predict({
    "Presidential Disapproval": 80, "Wrong Track": 70, "Liberals": 45,
    "Dem % Reg": 50, "DEM FAVORABLE": 65,
})
combined_direction_ok = (
    float(r_strength["headline"]["D-R Popular Margin (pp)"]) < base_margin
    and float(d_strength["headline"]["D-R Popular Margin (pp)"]) > base_margin
)

# Sequence semantics: the latest edit controls any infeasible request inside
# its battery, while compatible interventions in other units remain active.
approval_then_disapproval = engine.predict({
    "values": {"Presidential Approval": 50, "Presidential Disapproval": 100},
    "order": ["Presidential Approval", "Presidential Disapproval"],
})
disapproval_then_approval = engine.predict({
    "values": {"Presidential Approval": 50, "Presidential Disapproval": 100},
    "order": ["Presidential Disapproval", "Presidential Approval"],
})
cross_unit_sequence = engine.predict({
    "values": {"Presidential Disapproval": 100, "Right Track": 100},
    "order": ["Presidential Disapproval", "Right Track"],
})
latest_edit_priority_ok = (
    abs(approval_then_disapproval["reconciled_values"]["Presidential Approval"] - 0.0) < 1e-8
    and abs(approval_then_disapproval["reconciled_values"]["Presidential Disapproval"] - 100.0) < 1e-8
    and abs(disapproval_then_approval["reconciled_values"]["Presidential Approval"] - 50.0) < 1e-8
    and abs(disapproval_then_approval["reconciled_values"]["Presidential Disapproval"] - 50.0) < 1e-8
)
cross_unit_priority_ok = (
    abs(cross_unit_sequence["reconciled_values"]["Presidential Disapproval"] - 100.0) < 1e-8
    and abs(cross_unit_sequence["reconciled_values"]["Presidential Approval"] - 0.0) < 1e-8
    and abs(cross_unit_sequence["reconciled_values"]["Right Track"] - 100.0) < 1e-8
    and abs(cross_unit_sequence["reconciled_values"]["Wrong Track"] - 0.0) < 1e-8
)
sequence_batteries_valid = all(
    result["battery_status"]["Valid"].astype(bool).all()
    for result in (approval_then_disapproval, disapproval_then_approval, cross_unit_sequence)
)
relationship_controls = engine.premodel.control_relationship_edges()
within_battery_edges_zero = relationship_controls.loc[
    relationship_controls["Source unit"].eq(relationship_controls["Target unit"])
    & relationship_controls["Regularised weight"].abs().gt(1e-10)
].empty
drag_release_contract = (
    '"drag_value"' in app_text
    and 'updatemode="mouseup"' in views_text
    and "preview_scenario_battery_constraint" in app_text
)

# Safe-race official numeric values remain blank; scenario-only sigma stays calibrated.
safe_rows = senate_map.loc[senate_map["Tier"].eq("Safe")]
safe_numeric_blank = safe_rows[[
    "D Win Probability", "Projected Margin", "Projected D 2P", "Projected R 2P"
]].isna().all().all()
sigma_values = np.unique(np.round(
    np.asarray(bundle["senate_safe_baselines"]["Scenario Probability Sigma PP"], dtype=float), 6
))
sigma_ok = len(sigma_values) == 1 and abs(float(sigma_values[0]) - 5.915187) < 1e-5

# Explicit D55 regression contract from the 35 local anchors.
reg = bundle["sheets"].get("ScenarioSenateRegression", pd.DataFrame())
flip_order = bundle["sheets"].get("ScenarioSenateFlipOrder", pd.DataFrame())
d55_threshold = np.nan
if not reg.empty and {"Check", "Value"}.issubset(reg.columns):
    row = reg.loc[reg["Check"].astype(str).eq("Uniform D-R margin swing required for D55")]
    if not row.empty:
        d55_threshold = _num(row.iloc[0]["Value"])
d55_threshold_ok = np.isfinite(d55_threshold) and 0.0 < d55_threshold < 15.0
if d55_threshold_ok:
    _, d55_summary = scenario_senate_summary(
        senate_map, bundle["senate"], float(d55_threshold) + 1e-6, fixed_non_up_d, 0.0
    )
    d55_translator_ok = int(round(float(d55_summary["D seats by race winner"]))) >= 55
else:
    d55_translator_ok = False
flip_order_ok = (
    not flip_order.empty
    and "Swing to D flip (pp)" in flip_order.columns
    and len(flip_order.loc[pd.to_numeric(flip_order["Swing to D flip (pp)"], errors="coerce").le(d55_threshold + 1e-8)]) == 7
    if d55_threshold_ok else False
)

required_v26_sheets = [
    "NationalPremodelContract", "NationalPremodelTuning", "NationalPremodelLatents",
    "NationalPremodelEdges", "NationalPremodelOAT31", "NationalPremodelSupport31",
    "NationalPremodelCombined", "NationalPremodelExamples", "NationalPremodelProvenance",
    "NationalRelationships31", "NationalRelationships14", "Scenario42Coherence",
    "ScenarioSenateSwingAudit", "ScenarioSenateRegression",
    "ScenarioSenateFlipOrder", "ScenarioEngineContract", "ScenarioLabSource",
]

checks = {
    "report/html are v26": report_version == EXPECTED_VERSION and html_version == EXPECTED_VERSION,
    "Senate map uses structured data, not HTML parsing": structured_senate_map,
    "Scenario state Store survives tab changes": single_scenario_store,
    "Model.xlsx matches notebook snapshot SHA": model_snapshot_match,
    "notebook-exported v26 Scenario runtime exists": RUNTIME_PATH.exists() and runtime_v26,
    "Ledoit-Wolf precision inversion disabled": runtime_safe,
    "435 House rows": len(bundle["house"]) == 435,
    "435 House map paths": len(paths["districts"]) == 435,
    "50 state outlines": len(paths["raw"].get("states", [])) == 50,
    "brand logo shared": BRAND_LOGO_PATH.exists(),
    "11 monitored Senate races": len(bundle["senate"]) == 11,
    "24 Safe structural baselines": len(bundle["senate_safe_baselines"]) == 24,
    "50 Senate state tiles": len(senate_map) == 50,
    "35 Senate elections": int((senate_map["Tier"] != "None").sum()) == 35,
    "Safe official numeric fields blank": bool(safe_numeric_blank),
    "Safe sigma calibrated": bool(sigma_ok),
    "31 Scenario controls": len(engine.input_specs) == 31,
    "14 intervention units and 12 batteries": len(INTERVENTION_UNITS) == 14 and len(COMPOSITION_BATTERIES) == 12,
    "within-battery learned weights are zero": bool(within_battery_edges_zero),
    "battery preview runs during drag; premodel runs on release": bool(drag_release_contract),
    "all 31 controls connected to 42-target response": all(wired.values()),
    "geographic response never reverses popular swing": all(geography_direction_ok.values()),
    "combined partisan stresses directionally coherent": bool(combined_direction_ok),
    "latest edit wins inside an infeasible battery": bool(latest_edit_priority_ok),
    "cross-unit direct interventions remain active": bool(cross_unit_priority_ok),
    "sequence batteries remain at or below 100%": bool(sequence_batteries_valid),
    "Scenario baseline keeps observed 2026 inputs exactly": baseline_input_identity < 1e-8,
    "Scenario baseline keeps official 42 targets exactly": baseline_target_identity < 1e-8,
    "Scenario baseline has no changed inputs": bool(baseline_changed_none),
    "Scenario baseline popular vote equals official": bool(baseline_pop_identity),
    "Scenario runtime chamber headline equals official": bool(baseline_chamber_headline_identity),
    "Scenario House baseline equals official forecast": bool(house_baseline_match),
    "Scenario Senate baseline equals official forecast": bool(senate_baseline_match),
    "Scenario House exposes baseline vote fields exactly": bool(scenario_house_vote_fields_ok),
    "Scenario outcome cards precede sliders and maps": bool(scenario_order_ok),
    "House and Senate control probability heroes present": bool(control_heroes_ok),
    "Scenario House defaults to projected two-party vote": bool(scenario_vote_map_ok),
    "Scenario Senate uses structured rich hover": bool(structured_senate_hover_ok),
    "Central Senate forecast identifies three true flips": bool(central_senate_flip_logic_ok),
    "v26 relationship/audit sheets present": all(name in bundle["sheet_names"] for name in required_v26_sheets),
    "31×31 relationship table has 930 directed rows": len(bundle["sheets"].get("NationalRelationships31", pd.DataFrame())) == 930,
    "14×14 inter-unit table has 182 directed rows": len(bundle["sheets"].get("NationalRelationships14", pd.DataFrame())) == 182,
    "relationship OAT 31×2": len(bundle["sheets"].get("NationalPremodelOAT31", pd.DataFrame())) == 62,
    "within-support 31×2": len(bundle["sheets"].get("NationalPremodelSupport31", pd.DataFrame())) == 62,
    "Senate D55 threshold is finite and non-baseline": bool(d55_threshold_ok),
    "Senate translator reaches D55 only after threshold": bool(d55_translator_ok),
    "D55 threshold requires seven additional flips": bool(flip_order_ok),
    "House median-winner total 435": house_summary["D seats by median winner"] + house_summary["R seats by median winner"] == 435,
    "House expected total 435": abs(house_summary["Expected D seats"] + house_summary["Expected R seats"] - 435) < 1e-8,
    "Senate race-winner total 100": senate_summary["D seats by race winner"] + senate_summary["R seats by race winner"] == 100,
    "Senate expected total 100": abs(senate_summary["Expected D seats"] + senate_summary["Expected R seats"] - 100) < 1e-8,
    "71-feature contract": len(bundle["sheets"]["FeatureContract71"]) == 71,
    "31 extreme-scenario controls ×2": len(bundle["sheets"]["ScenarioExtremes31"]) == 62,
    "no duplicated/prohibited Dash sources": not forbidden,
}

print("Dash v26 setup check")
print("-------------------")
print("Report:", bundle["report_path"].name)
print("HTML:", html_name)
print("Workbook sheets:", len(bundle["sheet_names"]))
print("Source snapshot SHA match:", model_snapshot_match)
print("HouseRaceDetail rows:", len(bundle["house"]))
print("Senate monitored races:", len(bundle["senate"]))
print("Senate Safe structural baselines:", len(bundle["senate_safe_baselines"]))
print("Scenario national inputs:", len(engine.input_specs))
print("Scenario Safe sigma:", float(sigma_values[0]) if len(sigma_values) else "missing")
print("Intervention units:", len(engine.premodel.relationship_edges()[["Source unit"]].drop_duplicates()))
print("Relationship Ledoit-Wolf shrinkage:", round(engine.premodel.relationship_shrinkage, 6))
print("Maximum feedback row leverage:", engine.premodel.MAX_ROW_LEVERAGE)
print("Baseline input identity max delta:", baseline_input_identity)
print("Baseline 42-target identity max delta:", baseline_target_identity)
print("D55 uniform D-R swing threshold:", round(float(d55_threshold), 3) if np.isfinite(d55_threshold) else "missing")
print("Unwired controls:", [name for name, ok in wired.items() if not ok] or "none")
print("One-sided endpoint target response:", [name for name, ok in both_endpoint_target_response.items() if not ok] or "none")
print("Geographic direction reversals:", [name for name, ok in geography_direction_ok.items() if not ok] or "none")
print("Forbidden Dash copies:", [str(p.relative_to(DASH_DIR)) for p in forbidden] or "none")
print(
    "Scenario baseline: House D/R",
    scenario_house_d, scenario_house_r,
    "· Senate D/R", scenario_sen_d, scenario_sen_r,
    "· official House D/R", int(official_house_d), int(official_house_r),
    "· official Senate D/R", int(official_sen_d), int(official_sen_r),
)
print("\nChecks")
for label, passed in checks.items():
    print(f"[{'PASS' if passed else 'FAIL'}] {label}")

ok = all(checks.values())
print("\nSTATUS:", "OK" if ok else "CHECK REQUIRED")
if not ok:
    raise SystemExit(1)
