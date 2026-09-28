from __future__ import annotations

import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "Election_Model_v30_11_Final_Publication.html"
NOTEBOOK = ROOT / "NUCLEUS42_v30_11_FINAL_PUBLICATION_RELEASE.ipynb"

checks: dict[str, bool] = {
    "publication HTML exists": HTML.is_file() and HTML.stat().st_size > 1_000_000,
    "executed notebook exists": NOTEBOOK.is_file() and NOTEBOOK.stat().st_size > 100_000,
    "canonical workbook exists": (ROOT / "Model.xlsx").is_file(),
    "Render configuration exists": (ROOT / "render.yaml").is_file(),
    "README banner exists": (ROOT / "assets/readme/nucleus42-v30-banner.jpg").is_file(),
    "GitHub social preview exists": (ROOT / "assets/social/nucleus42-v30-social-preview.jpg").is_file(),
}

if HTML.is_file():
    text = HTML.read_text(encoding="utf-8")
    for anchor in (
        "overview",
        "house",
        "senate",
        "probability",
        "simulation",
        "context",
        "validation",
        "scenario-lab",
    ):
        checks[f"HTML anchor #{anchor}"] = bool(
            re.search(rf"\bid=[\"']{re.escape(anchor)}[\"']", text, re.IGNORECASE)
        )
    checks["v30.7 Scenario Lab engine embedded"] = (
        "v30.7-directed-causal-race-first" in text
    )
    checks["House contains 435-race interface"] = "435 House" in text or "435 districts" in text
    checks["Senate contains 35-race interface"] = "35 Senate" in text or "35 elections" in text

if NOTEBOOK.is_file():
    notebook = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
    checks["notebook format is v4"] = notebook.get("nbformat") == 4
    checks["notebook has 18 code cells"] = sum(
        cell.get("cell_type") == "code" for cell in notebook.get("cells", [])
    ) == 18
    checks["notebook stores no error outputs"] = not any(
        output.get("output_type") == "error"
        for cell in notebook.get("cells", [])
        for output in cell.get("outputs", [])
    )

try:
    from core import MODEL_PATH, load_bundle, load_senate_map, project_signature
    from figures import scenario_house_summary, scenario_senate_summary
    from scenario_engine import ENGINE_VERSION, OFFICIAL_BASELINE_HEADLINE, load_scenario_engine
    from views import render_tab

    signature = project_signature()
    bundle = load_bundle(signature)
    checks["native House source has 435 districts"] = len(bundle["house"]) == 435
    checks["native Senate source has 35 races"] = len(bundle["senate"]) == 35
    for tab in ("forecast", "overview", "house", "senate", "probability", "simulation", "context", "validation", "scenario"):
        checks[f"native tab renders: {tab}"] = render_tab(tab, signature) is not None

    engine = load_scenario_engine(str(MODEL_PATH), MODEL_PATH.stat().st_mtime_ns)
    baseline = engine.predict({})["headline"]
    checks["native Scenario engine is v30.7"] = ENGINE_VERSION == "v30.7-directed-causal-race-first"
    checks["native Scenario baseline matches serialized official"] = all(
        abs(float(baseline[key]) - float(value)) < 1e-9
        for key, value in OFFICIAL_BASELINE_HEADLINE.items()
    )
    _, house_summary = scenario_house_summary(bundle["house"], 0.0, 0.0)
    fixed_non_up_d = int(round(float(engine.production.iloc[0]["DS before"] - engine.production.iloc[0]["DSS UP"])))
    _, senate_summary = scenario_senate_summary(load_senate_map(signature), bundle["senate"], 0.0, fixed_non_up_d, 0.0)
    checks["native Scenario House reset is D230-R205"] = (
        int(house_summary["D seats by median winner"]) == 230
        and int(house_summary["R seats by median winner"]) == 205
    )
    checks["native Scenario Senate reset is D52-R48"] = (
        int(senate_summary["D seats by race winner"]) == 52
        and int(senate_summary["R seats by race winner"]) == 48
    )
except Exception as exc:
    checks[f"native Dash integration ({type(exc).__name__}: {exc})"] = False

failed = [name for name, passed in checks.items() if not passed]
print("NUCLEUS 42 v30.11 publication check")
for name, passed in checks.items():
    print(f"[{'PASS' if passed else 'FAIL'}] {name}")

if failed:
    print(f"STATUS: FAIL ({len(failed)} checks)")
    sys.exit(1)

print(f"STATUS: OK ({len(checks)}/{len(checks)} checks)")
