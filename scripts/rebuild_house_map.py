from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from urllib.request import urlopen


RAW_SOURCES = {
    "tlgdb_2026_us_legislative.gdb.zip": {
        "url": "https://www2.census.gov/geo/tiger/TGRGDB26/tlgdb_2026_us_legislative.gdb.zip",
        "sha256": "6708d7052ac4c07c32c241f341685572fdf5c38d57a0c3144fab4751e702cfbc",
    },
    "cb_2025_us_state_500k.zip": {
        "url": "https://www2.census.gov/geo/tiger/GENZ2025/shp/cb_2025_us_state_500k.zip",
        "sha256": "9cbfe171dad1555e11770c981d8f4db9e687a65c86f5bdae684eeb487e2e9b80",
    },
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def download_verified(path: Path, url: str, expected_sha256: str) -> None:
    """Download one public source atomically and verify its published release hash."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".part")
    print(f"Downloading {url}")
    with urlopen(url) as response, temporary.open("wb") as output:
        for block in iter(lambda: response.read(1024 * 1024), b""):
            output.write(block)
    observed = sha256(temporary)
    if observed != expected_sha256:
        temporary.unlink(missing_ok=True)
        raise ValueError(
            f"Checksum mismatch for {path.name}: expected {expected_sha256}, observed {observed}"
        )
    temporary.replace(path)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Rebuild the auditable House CD120 display assets from the two Census archives."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Package root (defaults to the parent of scripts/).",
    )
    parser.add_argument("--tolerance", type=float, default=0.0025)
    parser.add_argument(
        "--download-missing",
        action="store_true",
        help="Download and verify the two official Census archives when absent.",
    )
    args = parser.parse_args()

    root = args.root.resolve()
    scripts = root / "scripts"
    source_gdb = root / "data" / "raw" / "gis" / "tlgdb_2026_us_legislative.gdb.zip"
    shoreline = root / "data" / "raw" / "gis" / "cb_2025_us_state_500k.zip"
    geojson = root / "assets" / "house_cd120_official.geojson.gz"
    paths = root / "assets" / "house_cd120_albers_paths.json.gz"
    source_metadata = root / "metadata" / "Map_Source_CD120_2026.json"
    projection_metadata = root / "metadata" / "Map_Projection_CD120_2026.json"

    if args.download_missing:
        for path in [source_gdb, shoreline]:
            if not path.exists():
                source = RAW_SOURCES[path.name]
                download_verified(path, source["url"], source["sha256"])

    missing = [str(path) for path in [source_gdb, shoreline] if not path.exists()]
    if missing:
        raise FileNotFoundError(
            "Missing raw Census inputs: "
            + ", ".join(missing)
            + ". Download them manually as documented in data/raw/gis/README.md "
            + "or rerun with --download-missing."
        )

    for path in [source_gdb, shoreline]:
        expected = RAW_SOURCES[path.name]["sha256"]
        observed = sha256(path)
        if observed != expected:
            raise ValueError(
                f"Checksum mismatch for {path.name}: expected {expected}, observed {observed}"
            )

    subprocess.run(
        [
            sys.executable,
            str(scripts / "prepare_official_cd120_geometry.py"),
            str(source_gdb),
            str(shoreline),
            str(geojson),
            str(source_metadata),
            "--tolerance",
            str(args.tolerance),
        ],
        check=True,
    )
    subprocess.run(
        [
            sys.executable,
            str(scripts / "build_standard_albers_paths.py"),
            str(geojson),
            str(paths),
            str(projection_metadata),
        ],
        check=True,
    )

    source_info = json.loads(source_metadata.read_text(encoding="utf-8"))
    projection_info = json.loads(projection_metadata.read_text(encoding="utf-8"))
    result = {
        "districts": source_info["voting_district_count"],
        "states": projection_info["state_outline_count"],
        "geojson_sha256": sha256(geojson),
        "paths_sha256": sha256(paths),
        "tolerance_degrees": args.tolerance,
    }
    if result["districts"] != 435 or result["states"] != 50:
        raise AssertionError(f"Unexpected rebuilt map counts: {result}")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
