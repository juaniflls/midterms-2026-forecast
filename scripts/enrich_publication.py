"""Add the full race-card interface to the official v30 publication.

This module changes presentation only. It imports candidate identity, portraits,
descriptive population composition and history from
the packaged source snapshot. It does not alter forecast inputs or results.
"""
from pathlib import Path
import argparse
import importlib.util
import json
import os
import re
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def validate_publication(path):
    """Reject the old dashboard even when its title and file size look valid."""
    text = Path(path).read_text(encoding="utf-8")
    # The published HTML embeds Plotly.js. Checking it must not depend on the
    # separately installed Python plotly package or its exact JS version.
    plotly_header = re.search(
        r"<script\b[^>]*>\s*/\*\*\s*\*\s*plotly\.js v\d+\.\d+\.\d+",
        text,
        flags=re.I,
    )
    if not plotly_header:
        raise ValueError("El HTML no contiene un paquete Plotly.js incrustado.")
    plotly_end = text.find("</script>", plotly_header.end())
    if plotly_end < 0 or plotly_end - plotly_header.start() < 2_000_000:
        raise ValueError("El código de Plotly está incompleto o fue alterado por una inserción HTML.")
    required = ("N42_RACECARDS_BEGIN", "N42_RACECARDS_END",
                'id="n42-racecards-style"', 'id="n42RaceData"')
    if any(text.count(marker) != 1 for marker in required):
        raise ValueError("HTML visual incompleto: faltan Race Cards o hay capas duplicadas.")
    match = re.search(r'<script type="application/json" id="n42RaceData">(.*?)</script>', text, re.S)
    if not match:
        raise ValueError("HTML sin datos de Race Cards.")
    payload = json.loads(match.group(1))
    if "polls" in payload or any("finance" in race for race in payload.get("races", [])):
        raise ValueError("HTML includes removed supplementary data.")
    if any(marker in text for marker in ("Campaign finance", "Supplied polling", "D.polls", "r.finance")):
        raise ValueError("HTML includes removed supplementary sections.")
    races = payload["races"]
    house = [race for race in races if race["chamber"] == "House"]
    senate = [race for race in races if race["chamber"] == "Senate"]
    if len(house) != 435 or len(senate) != 35 or len({race['id'] for race in races}) != 470:
        raise ValueError("HTML debe contener 435 Race Cards House y 35 Senate con claves únicas.")
    counts = payload["counts"]
    if counts["demographicDistricts"] != 435 or counts["photoMatched"] <= 0:
        raise ValueError("HTML sin cobertura demográfica o retratos.")
    photos = sum(bool(candidate.get("image", "")) for race in races for candidate in race["candidates"])
    if photos != counts["photoMatched"]:
        raise ValueError("El número de retratos incrustados no coincide con la auditoría.")
    return {"House": len(house), "Senate": len(senate), "photos": photos,
            "demographicDistricts": counts["demographicDistricts"]}


def enrich_html(path, base_dir=None):
    path = Path(path)
    base = Path(base_dir or path.parent)
    report = base / "outputs" / "Election_Model_Final_Report_v30.xlsx"
    if not report.exists():
        raise FileNotFoundError(f"Required v30 report not found: {report}")

    # Remove the reduced profile layer from an earlier package before applying
    # the complete 470-race interface. The builder itself is idempotent.
    text = path.read_text(encoding="utf-8")
    text = re.sub(
        r"<!-- N42 RACE PROFILES START -->.*?<!-- N42 RACE PROFILES END -->",
        "",
        text,
        flags=re.S,
    )
    path.write_text(text, encoding="utf-8")

    # Load from this project, not a previously imported copy in a Jupyter kernel.
    spec = importlib.util.spec_from_file_location(
        "_n42_current_enrichment", base / "nucleus42_visual/enrichment.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.build_racecards(base, path, report)
    validate_publication(path)
    return path


def publish_html(html, path, base_dir=None):
    """Publish only the fully enriched, validated HTML at Render's canonical path."""
    path = Path(path)
    base = Path(base_dir or path.parent)
    descriptor, staging = tempfile.mkstemp(prefix=".n42-publication-", suffix=".html", dir=path.parent)
    staged = Path(staging)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(html)
        enrich_html(staged, base)
        summary = validate_publication(staged)
        os.replace(staged, path)
    finally:
        staged.unlink(missing_ok=True)
    print("NUCLEUS 42 v30 — HTML VISUAL VERIFICADO:", json.dumps(summary))
    print("HTML final:", path.resolve())
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "html",
        nargs="?",
        type=Path,
        default=Path(__file__).resolve().parents[1]
        / "NUCLEUS42_v30_RaceCards.html",
    )
    args = parser.parse_args()
    print(enrich_html(args.html))
