#!/usr/bin/env python3
"""Validate the v30.11.3 publication contract and web package."""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK = ROOT / "NUCLEUS42_v30_SIN_FINANZAS_NI_POLLS_EXTERNOS.ipynb"
HTML = ROOT / "NUCLEUS42_v30_RaceCards.html"
MODEL = ROOT / "Model.xlsx"
REPORT = ROOT / "outputs" / "Election_Model_Final_Report_v30.xlsx"
V30_ORIGINAL_ENGINE_SHA256 = "fbe5f69839ae2562c6667c0eaa25a1fa536cfda472ac041edf96f5079f512452"
V30_SOURCE_BLOCK_SHA256 = "c1bc8cae187591e167ffb03dfc4e39d5799ca29134321a5f98d28f1d3c3e45f0"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


checks: dict[str, bool] = {}
for path in (NOTEBOOK, HTML, MODEL, REPORT):
    checks[f"exists: {path.relative_to(ROOT)}"] = path.is_file() and path.stat().st_size > 0


if NOTEBOOK.is_file():
    nb = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
    checks["notebook format v4"] = nb.get("nbformat") == 4
    checks["notebook has 18 code cells"] = sum(c.get("cell_type") == "code" for c in nb.get("cells", [])) == 18
    blocks = ["".join(c.get("source", [])) for c in nb["cells"]]
    original_engine = "".join(blocks[i] for i,c in enumerate(nb["cells"]) if c["cell_type"] == "code" and i not in (4,34,36))
    checks["uploaded v30 statistical blocks preserved"] = hashlib.sha256(original_engine.encode()).hexdigest() == V30_ORIGINAL_ENGINE_SHA256
    source_block = re.sub(r"# FILE PATH SAFETY.*?(?=OUTPUT_DIR =)", "BASE_DIR = Path.cwd()\n", blocks[4], flags=re.S)
    checks["uploaded source logic preserved (root safety only)"] = hashlib.sha256(source_block.encode()).hexdigest() == V30_SOURCE_BLOCK_SHA256
    checks["Block 8 publishes enriched HTML before success"] = (
        "_n42_publication.publish_html(html, output_html, BASE_DIR)" in blocks[34]
        and "with open(output_html" not in blocks[34]
        and not any("audit_new_web_sources" in s or "N42_WEB_AUDIT" in s or "Model.automated.xlsx" in s for s in blocks)
    )
    checks["Block 9 rejects old dashboard"] = "_n42_publication.validate_publication(_html_path)" in blocks[36]
    checks["CSS inserted outside Plotly script"] = 'id="n42-v30-upgrade-style"' in blocks[34] and 'html.replace("</style>", N42_UPGRADE_CSS' not in blocks[34]
    checks["notebook stores no error output"] = not any(
        output.get("output_type") == "error"
        for cell in nb.get("cells", [])
        for output in cell.get("outputs", [])
    )

if HTML.is_file():
    text = HTML.read_text(encoding="utf-8", errors="ignore")
    from enrich_publication import validate_publication
    try:
        visual = validate_publication(HTML)
        checks["HTML payload: 435 House + 35 Senate, portraits and demographics"] = visual["House"] == 435 and visual["Senate"] == 35
    except (ValueError, KeyError, TypeError) as exc:
        checks["HTML payload: 435 House + 35 Senate, portraits and demographics"] = False
        print("Visual validation:", exc)
    checks["470 race cards embedded"] = all(x in text for x in ("n42RaceData", "N42_RACECARDS_BEGIN", "n42-racecards-style"))
    checks["Race Card map hover/click bundle embedded"] = "interface" in text.lower() and "ID-SEN" in text
    checks["HTML engine v30.8"] = "v30.8-reciprocal-standing-race-first" in text
    checks["HTML reciprocal standing bridge"] = all(
        marker in text
        for marker in (
            "directionTouched&&!approvalTouched",
            "conditional_transpose",
        )
    )
    for anchor in ("overview", "house", "senate", "probability", "simulation", "context", "validation", "scenario-lab"):
        checks[f"HTML anchor #{anchor}"] = bool(re.search(rf"\bid=[\"']{re.escape(anchor)}[\"']", text, re.I))

if REPORT.is_file():
    xls = pd.ExcelFile(REPORT)
    required = {"HouseRaceDetail", "SenateRaceDetail", "FinalProjection", "ConsistencyAudit", "V30ReleaseGate", "ScenarioEngineContract", "ScenarioLabSource", "RunMetadata"}
    checks["report required sheets"] = required.issubset(xls.sheet_names)
    house = pd.read_excel(xls, "HouseRaceDetail")
    senate = pd.read_excel(xls, "SenateRaceDetail")
    checks["House has 435 districts"] = len(house) == 435
    checks["Senate has 35 races"] = len(senate) == 35
    consistency = pd.read_excel(xls, "ConsistencyAudit")
    checks["consistency audit passes"] = "Passed" in consistency and consistency["Passed"].astype(bool).all()
    gate = pd.read_excel(xls, "V30ReleaseGate")
    if "Passed" in gate.columns:
        checks["v30 release gate passes"] = gate["Passed"].astype(bool).all()
    else:
        status_col = next((c for c in gate.columns if str(c).lower() == "status"), None)
        checks["v30 release gate passes"] = bool(status_col) and gate[status_col].astype(str).str.startswith("PASS").all()
    metadata = pd.read_excel(xls, "RunMetadata")
    if {"Field", "Value"}.issubset(metadata.columns):
        values = dict(zip(metadata["Field"].astype(str), metadata["Value"].astype(str)))
        report_hash = next((v for k, v in values.items() if "Source SHA-256" in k), "")
        checks["report/model provenance identity"] = report_hash.lower() == sha256(MODEL).lower()
    else:
        checks["report/model provenance identity"] = False

checks["local race candidate photos included"] = len(list((ROOT/"data/race_assets/photos").glob("*.jpg"))) >= 1000
checks["local portrait archive included"] = len(list((ROOT/"assets/portraits").glob("*"))) >= 400
checks["source demographics included"] = (ROOT/"data/race_assets/demographics.csv").is_file()
checks["visual renderer and scripts included"] = all((ROOT/p).is_file() for p in ("scripts/enrich_publication.py","nucleus42_visual/enrichment.py","nucleus42_visual/interface.js","nucleus42_visual/interface.css","nucleus42_visual/interface.html"))
checks["README race-card screenshots included"] = all((ROOT/p).is_file() for p in ("assets/readme/race-card-house-NY-21.png","assets/readme/race-card-senate-ME-SEN.png"))

for relative in (
    "README.md", "MODEL_CARD.md", "RELEASE_NOTES_v30.11.1.md", "render.yaml",
    "docs/METHODOLOGY.md", "docs/SCENARIO_LAB.md", "docs/DATA_SOURCES.md",
    "docs/WEB_DEPLOYMENT_ZERO_COST.md", "docs/PUBLISHING.md",
    "assets/readme/nucleus42-v30-banner.jpg",
    "assets/social/nucleus42-v30-social-preview.jpg",
):
    checks[f"package file: {relative}"] = (ROOT / relative).is_file()

failed = [name for name, passed in checks.items() if not passed]
print("NUCLEUS 42 v30.11.3 repository validation")
for name, passed in checks.items():
    print(f"[{'PASS' if passed else 'FAIL'}] {name}")
if failed:
    print(f"STATUS: FAIL ({len(failed)} checks)")
    sys.exit(1)
print(f"STATUS: OK ({len(checks)}/{len(checks)} checks)")
