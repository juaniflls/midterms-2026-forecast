#!/usr/bin/env python3
"""Validate the v30.11.1 publication contract and web package."""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK = ROOT / "NUCLEUS42_v30_11_FINAL_PUBLICATION_RELEASE.ipynb"
HTML = ROOT / "Election_Model_v30_11_Final_Publication.html"
MODEL = ROOT / "Model.xlsx"
REPORT = ROOT / "outputs" / "Election_Model_Final_Report_v30.xlsx"
EXPECTED_SHA256 = {
    NOTEBOOK.name: "1ececba4f905296aebcda99798945a990c4bdcce2ee9a825d34d3858d8936e63",
    HTML.name: "3cc630f2fc59fd2e7ca88a36af7225e0a9c45e3b875897fa3ecf1a8e8b5edb6f",
    MODEL.name: "8418fc64c09ac2c61c25c88442bd8565f4a58d2bf9d1e56cde3da42496d17e12",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


checks: dict[str, bool] = {}
for path in (NOTEBOOK, HTML, MODEL, REPORT):
    checks[f"exists: {path.relative_to(ROOT)}"] = path.is_file() and path.stat().st_size > 0

if all(path.is_file() for path in (NOTEBOOK, HTML, MODEL)):
    for name, expected in EXPECTED_SHA256.items():
        checks[f"immutable SHA-256: {name}"] = sha256(ROOT / name) == expected

if NOTEBOOK.is_file():
    nb = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
    checks["notebook format v4"] = nb.get("nbformat") == 4
    checks["notebook has 18 code cells"] = sum(c.get("cell_type") == "code" for c in nb.get("cells", [])) == 18
    checks["notebook stores no error output"] = not any(
        output.get("output_type") == "error"
        for cell in nb.get("cells", [])
        for output in cell.get("outputs", [])
    )

if HTML.is_file():
    text = HTML.read_text(encoding="utf-8", errors="ignore")
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

for relative in (
    "README.md", "MODEL_CARD.md", "RELEASE_NOTES_v30.11.1.md", "render.yaml",
    "docs/METHODOLOGY.md", "docs/SCENARIO_LAB.md", "docs/DATA_SOURCES.md",
    "docs/WEB_DEPLOYMENT_ZERO_COST.md", "docs/PUBLISHING.md",
    "assets/readme/nucleus42-v30-banner.jpg",
    "assets/social/nucleus42-v30-social-preview.jpg",
):
    checks[f"package file: {relative}"] = (ROOT / relative).is_file()

failed = [name for name, passed in checks.items() if not passed]
print("NUCLEUS 42 v30.11.1 repository validation")
for name, passed in checks.items():
    print(f"[{'PASS' if passed else 'FAIL'}] {name}")
if failed:
    print(f"STATUS: FAIL ({len(failed)} checks)")
    sys.exit(1)
print(f"STATUS: OK ({len(checks)}/{len(checks)} checks)")
