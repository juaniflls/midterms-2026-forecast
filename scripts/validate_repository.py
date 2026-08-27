from __future__ import annotations

import gzip
import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def check(condition: bool, message: str, failures: list[str]) -> None:
    if condition:
        print(f"PASS  {message}")
    else:
        print(f"FAIL  {message}")
        failures.append(message)


def markdown_targets(document: Path) -> list[str]:
    text = document.read_text(encoding="utf-8")
    markdown = re.findall(r"\[[^]]*\]\((?!https?://|mailto:|#)([^)]+)\)", text)
    html = re.findall(r"(?:src|href)=[\"'](?!https?://|mailto:|#)([^\"']+)[\"']", text)
    return markdown + html


def main() -> None:
    failures: list[str] = []

    required = [
        ROOT / "README.md",
        ROOT / "Model.xlsx",
        ROOT / "Modelo_Midterms_2026_v26_FINAL_EJECUTADO.ipynb",
        ROOT / "Election_Model_2026_Dashboard_v26.html",
        ROOT / "outputs" / "Election_Model_Final_Report_v26.xlsx",
        ROOT / "outputs" / "Model_Sensitivity_Audit_v26.xlsx",
        ROOT / "outputs" / "scenario_state_engine_v26.py",
        ROOT / "assets" / "house_cd120_official.geojson.gz",
        ROOT / "assets" / "house_cd120_albers_paths.json.gz",
        ROOT / "assets" / "social" / "social-preview.png",
        ROOT / "assets" / "readme" / "forecast-tour.gif",
        ROOT / "qa" / "v26_fourteen_unit_scenario_validation.json",
        ROOT / "docs" / "METHODOLOGY.md",
        ROOT / "docs" / "SCENARIO_LAB.md",
        ROOT / "dash_app" / "app.py",
        ROOT / "dash_app" / "check_setup.py",
        ROOT / "dash_app" / "assets" / "dash_v2.css",
        ROOT / "CITATION.cff",
        ROOT / "LICENSE",
    ]
    missing = [str(path.relative_to(ROOT)) for path in required if not path.exists()]
    check(not missing, f"required v26/v26.1 artifacts are present ({missing or 'none missing'})", failures)

    forbidden_names = {".DS_Store", "__pycache__", ".ipynb_checkpoints", ".venv", ".venv-model", "__MACOSX"}
    forbidden = [
        str(path.relative_to(ROOT))
        for path in ROOT.rglob("*")
        if path.name in forbidden_names or path.name.startswith("._")
    ]
    check(not forbidden, f"no cache, environment, checkpoint, or macOS artifacts ({forbidden or 'none'})", failures)
    check(not (ROOT / ".git").exists(), "distribution does not embed Git history", failures)

    oversized = [
        (str(path.relative_to(ROOT)), path.stat().st_size)
        for path in ROOT.rglob("*")
        if path.is_file() and path.stat().st_size > 100 * 1024 * 1024
    ]
    check(not oversized, f"no file exceeds GitHub's 100 MiB limit ({oversized or 'none'})", failures)

    obsolete = sorted(
        [path.name for path in (ROOT / "outputs").glob("Election_Model_Final_Report_v*.xlsx") if path.name != "Election_Model_Final_Report_v26.xlsx"]
        + [path.name for path in (ROOT / "outputs").glob("scenario_state_engine_v*.py") if path.name != "scenario_state_engine_v26.py"]
        + [path.name for path in (ROOT / "outputs").glob("Model_Sensitivity_Audit_v*.xlsx") if path.name != "Model_Sensitivity_Audit_v26.xlsx"]
    )
    check(not obsolete, f"only canonical v26 report, runtime, and sensitivity audit remain ({obsolete or 'none stale'})", failures)

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for phrase in [
        "## Forecast snapshot",
        "## Scenario Lab",
        "## Historical validation design",
        "## Interpretation and limitations",
        "Modelo_Midterms_2026_v26_FINAL_EJECUTADO.ipynb",
        "Election_Model_2026_Dashboard_v26.html",
        "Election_Model_Final_Report_v26.xlsx",
    ]:
        check(phrase in readme, f"README contains {phrase!r}", failures)
    check("Modelo_Midterms_2026_v17" not in readme, "README has no stale v17 notebook reference", failures)

    notebook = read_json(ROOT / "Modelo_Midterms_2026_v26_FINAL_EJECUTADO.ipynb")
    code_cells = [cell for cell in notebook["cells"] if cell.get("cell_type") == "code"]
    errors = [
        output
        for cell in code_cells
        for output in cell.get("outputs", [])
        if output.get("output_type") == "error"
    ]
    check(len(code_cells) == 13, "notebook contains 13 code cells", failures)
    check(all(cell.get("execution_count") is not None for cell in code_cells), "all notebook code cells are executed", failures)
    check(not errors, "executed notebook contains no stored error outputs", failures)

    with gzip.open(ROOT / "assets" / "house_cd120_albers_paths.json.gz", "rt", encoding="utf-8") as handle:
        paths = json.load(handle)
    with gzip.open(ROOT / "assets" / "house_cd120_official.geojson.gz", "rt", encoding="utf-8") as handle:
        geometry = json.load(handle)
    check(len(paths.get("districts", [])) == 435, "processed map contains 435 district paths", failures)
    check(len(paths.get("states", [])) == 50, "processed map contains 50 state outlines", failures)
    check(len(geometry.get("features", [])) == 435, "processed GeoJSON contains 435 districts", failures)

    html = (ROOT / "Election_Model_2026_Dashboard_v26.html").read_text(encoding="utf-8")
    check(html.count('class="house-district"') == 435, "HTML contains 435 House geographic districts", failures)
    check(html.count('class="house-cart-tile"') == 435, "HTML contains 435 House cartogram tiles", failures)
    check(html.count('class="state-tile') == 50, "HTML contains 50 Senate state tiles", failures)
    check("Projected two-party vote share" in html, "HTML distinguishes projected vote from probability", failures)
    check("Scenario Lab" in html, "HTML contains Scenario Lab", failures)
    check('alt="Midterms 2026 model logo"' in html, "HTML embeds the selected visual identity", failures)

    scenario_qa = read_json(ROOT / "qa" / "v26_fourteen_unit_scenario_validation.json")
    check(scenario_qa.get("version") == 26, "Scenario QA identifies model v26", failures)
    check(scenario_qa.get("intervention_units") == 14, "Scenario QA records fourteen intervention units", failures)
    check(scenario_qa.get("composition_batteries") == 12, "Scenario QA records twelve composition batteries", failures)
    check(scenario_qa.get("scenario_controls") == 31, "Scenario QA records 31 controls", failures)
    check(scenario_qa.get("unit_relationship_rows") == 182, "Scenario QA records 182 unit relationships", failures)
    check(scenario_qa.get("control_relationship_rows") == 930, "Scenario QA records 930 control relationships", failures)
    check(abs(float(scenario_qa.get("scenario_baseline_input_identity_max_abs_pp", 1))) < 1e-12, "Scenario input baseline identity is exact", failures)
    check(float(scenario_qa.get("scenario_baseline_target_identity_max_abs", 1)) < 1e-12, "Scenario target baseline identity is exact within floating precision", failures)
    runtime_hash = sha256(ROOT / "outputs" / "scenario_state_engine_v26.py")
    check(runtime_hash == scenario_qa.get("runtime_sha256"), "Scenario runtime hash matches QA manifest", failures)

    release_manifest = read_json(ROOT / "qa" / "release_manifest_v26_1.json")
    manifest_mismatches = [
        relative
        for relative, expected in release_manifest.get("artifacts", {}).items()
        if not (ROOT / relative).is_file() or sha256(ROOT / relative) != expected
    ]
    check(not manifest_mismatches, f"release artifact hashes match the v26.1 manifest ({manifest_mismatches or 'all match'})", failures)

    screenshots = list((ROOT / "assets" / "readme").glob("*.png"))
    check(len(screenshots) == 14, "all fourteen release screenshots are preserved", failures)
    check((ROOT / "assets" / "readme" / "forecast-tour.gif").stat().st_size < 8 * 1024 * 1024, "animated tour is below 8 MiB", failures)
    check((ROOT / "assets" / "social" / "social-preview.png").stat().st_size < 1024 * 1024, "social preview is below 1 MiB", failures)

    broken_links: list[str] = []
    markdown_files = sorted(ROOT.rglob("*.md"))
    for document in markdown_files:
        for target in markdown_targets(document):
            clean_target = target.split("#", 1)[0].strip().strip("<>")
            if not clean_target:
                continue
            candidate = (document.parent / clean_target).resolve()
            try:
                candidate.relative_to(ROOT.resolve())
            except ValueError:
                continue
            if not candidate.exists():
                broken_links.append(f"{document.relative_to(ROOT)}: {target}")
    check(not broken_links, f"local Markdown and HTML links resolve ({broken_links or 'none broken'})", failures)

    print()
    if failures:
        print(f"Repository validation failed: {len(failures)} check(s).")
        raise SystemExit(1)
    print("Repository validation passed.")


if __name__ == "__main__":
    main()
