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
}

if HTML.is_file():
    text = HTML.read_text(encoding="utf-8")
    for anchor in (
        "overview", "house", "senate", "probability", "simulation",
        "context", "validation", "scenario-lab",
    ):
        checks[f"HTML anchor #{anchor}"] = bool(
            re.search(rf"\bid=[\"']{re.escape(anchor)}[\"']", text, re.IGNORECASE)
        )
    checks["v30.8 Scenario Lab engine embedded"] = (
        "v30.8-reciprocal-standing-race-first" in text
    )
    checks["reciprocal standing bridge embedded"] = all(
        marker in text
        for marker in (
            "const approvalTouched=touched.has('Presidential approval')",
            "const directionTouched=touched.has('Direction of country')",
            "conditional_transpose",
        )
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
    source = "\n".join(
        "".join(cell.get("source", [])) for cell in notebook.get("cells", [])
    )
    checks["notebook regenerates v30.8 engine"] = (
        'SCENARIO_ENGINE_VERSION = "v30.8-reciprocal-standing-race-first"' in source
    )
    checks["notebook regenerates reciprocal standing bridge"] = (
        "directionTouched&&!approvalTouched" in source
    )

try:
    sys.path.insert(0, str(ROOT / "dash_app"))
    from app import app

    client = app.test_client()
    root = client.get("/")
    deep_link = client.get("/forecast-html")
    health = client.get("/healthz")
    checks["Render root serves HTML directly"] = (
        root.status_code == 200
        and root.mimetype == "text/html"
        and b"n42ScenarioData" in root.data
    )
    checks["former HTML deep link remains valid"] = deep_link.status_code == 200
    checks["health endpoint passes"] = (
        health.status_code == 200
        and health.get_json().get("application") == "autonomous-html"
    )
except Exception as exc:
    checks[f"Flask publication server ({type(exc).__name__}: {exc})"] = False

failed = [name for name, passed in checks.items() if not passed]
print("NUCLEUS 42 v30.11.1 publication check")
for name, passed in checks.items():
    print(f"[{'PASS' if passed else 'FAIL'}] {name}")

if failed:
    print(f"STATUS: FAIL ({len(failed)} checks)")
    sys.exit(1)

print(f"STATUS: OK ({len(checks)}/{len(checks)} checks)")
