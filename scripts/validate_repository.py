from __future__ import annotations

import gzip
import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def check(condition: bool, message: str, failures: list[str]) -> None:
    if condition:
        print(f"PASS  {message}")
    else:
        print(f"FAIL  {message}")
        failures.append(message)


def main() -> None:
    failures: list[str] = []
    required = [
        ROOT / "README.md",
        ROOT / "Model.xlsx",
        ROOT / "Modelo_Midterms_2026_v17.ipynb",
        ROOT / "Modelo_Midterms_2026_v17_EXECUTED.ipynb",
        ROOT / "Election_Model_2026_Dashboard_v17.html",
        ROOT / "assets" / "house_cd120_official.geojson.gz",
        ROOT / "assets" / "house_cd120_albers_paths.json.gz",
        ROOT / "assets" / "social" / "social-preview.png",
        ROOT / "outputs" / "Election_Model_Final_Report_v17.xlsx",
        ROOT / "qa" / "package_validation.json",
        ROOT / "CITATION.cff",
        ROOT / "CONTRIBUTING.md",
    ]
    missing = [str(path.relative_to(ROOT)) for path in required if not path.exists()]
    check(not missing, f"required tracked artifacts are present ({', '.join(missing) or 'none missing'})", failures)

    if missing:
        raise SystemExit(1)

    oversized = [
        (path.relative_to(ROOT), path.stat().st_size)
        for path in ROOT.rglob("*")
        if path.is_file() and path.stat().st_size > 100 * 1024 * 1024
    ]
    check(not oversized, f"no tracked file exceeds 100 MiB ({oversized or 'none'})", failures)

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    check(
        "1xw1BG083q41GgdWCJ_oAbqqXQEoec5aqejzXknVqYtg" in readme,
        "README links to the live canonical workbook",
        failures,
    )
    check("## Validation design" in readme, "README documents temporal validation", failures)
    check("## Interpretation and limitations" in readme, "README documents limitations", failures)

    clean = read_json(ROOT / "Modelo_Midterms_2026_v17.ipynb")
    executed = read_json(ROOT / "Modelo_Midterms_2026_v17_EXECUTED.ipynb")
    clean_code = [cell for cell in clean["cells"] if cell.get("cell_type") == "code"]
    executed_code = [cell for cell in executed["cells"] if cell.get("cell_type") == "code"]
    errors = [
        output
        for cell in executed_code
        for output in cell.get("outputs", [])
        if output.get("output_type") == "error"
    ]
    check(len(clean_code) == 11, "clean notebook contains 11 code cells", failures)
    check(all(not cell.get("outputs") for cell in clean_code), "clean notebook has no stored outputs", failures)
    check(len(executed_code) == 11 and not errors, "executed notebook contains 11 error-free code cells", failures)

    with gzip.open(ROOT / "assets" / "house_cd120_albers_paths.json.gz", "rt", encoding="utf-8") as handle:
        paths = json.load(handle)
    with gzip.open(ROOT / "assets" / "house_cd120_official.geojson.gz", "rt", encoding="utf-8") as handle:
        geometry = json.load(handle)
    check(len(paths.get("districts", [])) == 435, "processed map contains 435 district paths", failures)
    check(len(paths.get("states", [])) == 50, "processed map contains 50 state outlines", failures)
    check(len(geometry.get("features", [])) == 435, "processed GeoJSON contains 435 districts", failures)

    html = (ROOT / "Election_Model_2026_Dashboard_v17.html").read_text(encoding="utf-8")
    check(html.count('class="house-district"') == 435, "dashboard contains 435 House geographic districts", failures)
    check(html.count('class="house-cart-tile"') == 435, "dashboard contains 435 House cartogram tiles", failures)
    check(html.count('class="state-tile') == 50, "dashboard contains 50 Senate state tiles", failures)
    check("Projected two-party vote share" in html, "Senate projected-margin view uses vote shares", failures)
    check("senateMarginMarkup" in html, "Senate margin tooltip is party-aware", failures)
    check("senateOutcomeMarkup" in html, "Senate outcome tooltip is party-aware", failures)
    check("senateRatingMarkup" in html, "Senate rating tooltip is party-aware", failures)
    check('alt="Midterms 2026 model logo"' in html, "dashboard embeds the selected identity", failures)

    social = ROOT / "assets" / "social" / "social-preview.png"
    check(social.stat().st_size < 1024 * 1024, "social preview is below 1 MiB", failures)

    qa = read_json(ROOT / "qa" / "package_validation.json")
    check(qa.get("all_passed") is True, "complete release package QA passed", failures)

    markdown_files = [ROOT / "README.md", ROOT / "CHANGELOG.md", ROOT / "CONTRIBUTING.md"]
    local_link_pattern = re.compile(r"\[[^]]+\]\((?!https?://|#|mailto:)([^)]+)\)")
    broken_links: list[str] = []
    for document in markdown_files:
        for target in local_link_pattern.findall(document.read_text(encoding="utf-8")):
            clean_target = target.split("#", 1)[0]
            if clean_target and not (ROOT / clean_target).exists():
                broken_links.append(f"{document.name}: {target}")
    check(not broken_links, f"tracked Markdown links resolve ({broken_links or 'none broken'})", failures)

    print()
    if failures:
        print(f"Repository validation failed: {len(failures)} check(s).")
        raise SystemExit(1)
    print("Repository validation passed.")


if __name__ == "__main__":
    main()
