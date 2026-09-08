from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import tempfile
import zipfile
from pathlib import Path

import pyogrio
import shapely
from pyogrio import raw
from shapely.geometry import mapping


VOTING_STATE_FIPS = {
    "01", "02", "04", "05", "06", "08", "09", "10", "12", "13",
    "15", "16", "17", "18", "19", "20", "21", "22", "23", "24",
    "25", "26", "27", "28", "29", "30", "31", "32", "33", "34",
    "35", "36", "37", "38", "39", "40", "41", "42", "44", "45",
    "46", "47", "48", "49", "50", "51", "53", "54", "55", "56",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def extract_gdb(zip_path: Path, destination: Path) -> Path:
    with zipfile.ZipFile(zip_path) as archive:
        for member in archive.infolist():
            resolved = (destination / member.filename).resolve()
            if destination.resolve() not in resolved.parents and resolved != destination.resolve():
                raise RuntimeError(f"Unsafe ZIP member: {member.filename}")
        archive.extractall(destination)
    candidates = sorted(destination.glob("*.gdb"))
    if len(candidates) != 1:
        raise RuntimeError(f"Expected one File Geodatabase, found {len(candidates)}")
    return candidates[0]


def read_cartographic_land_masks(
    cartographic_state_zip: Path,
) -> tuple[dict[str, object], dict[str, object]]:
    """Read Census cartographic state boundaries as an independent land mask.

    TIGER/Line congressional districts contain legally assigned water.  Their
    union therefore fills large parts of the Great Lakes, which makes Michigan
    look like one solid legal-area polygon.  Census cartographic state files
    are shorelined for thematic mapping and provide the appropriate display
    mask without inventing or hand-drawing any coastline.
    """
    layers = pyogrio.list_layers(cartographic_state_zip)
    if len(layers) != 1:
        raise RuntimeError(
            f"Expected one cartographic state layer, found {layers.tolist()}"
        )
    layer = str(layers[0, 0])
    info = pyogrio.read_info(cartographic_state_zip, layer=layer)
    metadata, _, geometry_wkb, fields = raw.read(
        cartographic_state_zip,
        layer=layer,
        columns=["STATEFP", "NAME"],
        read_geometry=True,
    )
    masks: dict[str, object] = {}
    for index, values in enumerate(zip(*fields)):
        record = dict(zip(metadata["fields"], values))
        state_fips = str(record["STATEFP"])
        if state_fips not in VOTING_STATE_FIPS:
            continue
        masks[state_fips] = shapely.make_valid(shapely.from_wkb(geometry_wkb[index]))
    if set(masks) != VOTING_STATE_FIPS:
        missing = sorted(VOTING_STATE_FIPS - set(masks))
        extra = sorted(set(masks) - VOTING_STATE_FIPS)
        raise RuntimeError(
            f"Cartographic state mask mismatch; missing={missing}, extra={extra}"
        )
    details = {
        "cartographic_mask_file": cartographic_state_zip.name,
        "cartographic_mask_sha256": sha256(cartographic_state_zip),
        "cartographic_mask_layer": layer,
        "cartographic_mask_crs": info.get("crs"),
        "cartographic_mask_feature_count": int(info.get("features", 0)),
    }
    return masks, details


def read_official_districts(gdb_path: Path) -> tuple[list[dict[str, object]], dict[str, object]]:
    layers = pyogrio.list_layers(gdb_path)
    if "Congressional_Districts" not in set(layers[:, 0]):
        raise RuntimeError(f"Congressional_Districts missing; layers={layers.tolist()}")
    info = pyogrio.read_info(gdb_path, layer="Congressional_Districts")
    columns = [
        "STATEFP", "CD120FP", "GEOID", "NAMELSAD", "FUNCSTAT",
        "ALAND", "AWATER",
    ]
    metadata, _, geometry_wkb, fields = raw.read(
        gdb_path,
        layer="Congressional_Districts",
        columns=columns,
        read_geometry=True,
    )
    records: list[dict[str, object]] = []
    for index, values in enumerate(zip(*fields)):
        record = dict(zip(metadata["fields"], values))
        state_fips = str(record["STATEFP"])
        district_code = str(record["CD120FP"])
        if state_fips not in VOTING_STATE_FIPS or not district_code.isdigit():
            continue
        record["geometry"] = shapely.from_wkb(geometry_wkb[index])
        records.append(record)
    details = {
        "layer": "Congressional_Districts",
        "crs": info.get("crs"),
        "source_feature_count": int(info.get("features", 0)),
        "source_geometry_type": info.get("geometry_type"),
        "source_fields": list(info.get("fields", [])),
    }
    return records, details


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("gdb_zip", type=Path)
    parser.add_argument("cartographic_state_zip", type=Path)
    parser.add_argument("output_geojson_gz", type=Path)
    parser.add_argument("output_metadata", type=Path)
    parser.add_argument("--tolerance", type=float, default=0.0075)
    args = parser.parse_args()

    args.output_geojson_gz.parent.mkdir(parents=True, exist_ok=True)
    args.output_metadata.parent.mkdir(parents=True, exist_ok=True)

    land_masks, mask_details = read_cartographic_land_masks(
        args.cartographic_state_zip
    )
    with tempfile.TemporaryDirectory(prefix="cd120_gdb_") as temp_directory:
        gdb_path = extract_gdb(args.gdb_zip, Path(temp_directory))
        records, source_details = read_official_districts(gdb_path)

    if len(records) != 435:
        raise RuntimeError(f"Expected 435 voting districts, found {len(records)}")
    if len({str(record["GEOID"]) for record in records}) != 435:
        raise RuntimeError("Official CD120 GEOIDs are not unique")

    features = []
    geometry_validity = []
    vertex_count = 0
    empty_geoids = []
    for record in sorted(records, key=lambda item: str(item["GEOID"])):
        state_fips = str(record["STATEFP"])
        clipped = shapely.make_valid(record["geometry"]).intersection(land_masks[state_fips])
        clipped = shapely.make_valid(clipped)
        simplified = shapely.make_valid(
            shapely.simplify(clipped, tolerance=args.tolerance, preserve_topology=True)
        )
        polygonal = shapely.multipolygons(
            list(shapely.get_parts(simplified))
            if simplified.geom_type in {"Polygon", "MultiPolygon"}
            else [part for part in shapely.get_parts(simplified) if part.geom_type == "Polygon"]
        )
        if shapely.is_empty(polygonal):
            empty_geoids.append(str(record["GEOID"]))
        geometry_validity.append(bool(shapely.is_valid(polygonal)))
        vertex_count += int(shapely.get_num_coordinates(polygonal))
        features.append({
            "type": "Feature",
            "properties": {
                "STATEFP": state_fips,
                "CD120FP": str(record["CD120FP"]),
                "GEOID": str(record["GEOID"]),
                "NAMELSAD": str(record["NAMELSAD"]),
            },
            "geometry": mapping(polygonal),
        })

    if empty_geoids:
        raise RuntimeError(f"Land clipping produced empty districts: {empty_geoids}")
    if not all(geometry_validity):
        raise RuntimeError("Output includes invalid geometries")

    output_geojson = {
        "type": "FeatureCollection",
        "name": "Census_TIGER_Line_2026_CD120_voting_districts_display",
        "crs": {"type": "name", "properties": {"name": "EPSG:4269"}},
        "features": features,
    }
    encoded = json.dumps(output_geojson, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    with args.output_geojson_gz.open("wb") as raw_handle:
        with gzip.GzipFile(
            filename="",
            mode="wb",
            compresslevel=9,
            fileobj=raw_handle,
            mtime=0,
        ) as handle:
            handle.write(encoded)

    metadata = {
        "source_file": args.gdb_zip.name,
        "source_sha256": sha256(args.gdb_zip),
        **source_details,
        **mask_details,
        "voting_district_count": len(features),
        "unique_geoid_count": len({f["properties"]["GEOID"] for f in features}),
        "display_geometry_crs": "EPSG:4269",
        "display_simplification_tolerance_degrees": args.tolerance,
        "display_vertex_count": vertex_count,
        "display_geometries_valid": all(geometry_validity),
        "display_land_treatment": (
            "Official CD120 legal geometry intersected with the independent Census "
            "2025 cartographic state shoreline mask; no coastline or district "
            "boundary is hand-drawn."
        ),
        "geojson_uncompressed_bytes": len(encoded),
        "geojson_gzip_bytes": args.output_geojson_gz.stat().st_size,
    }
    args.output_metadata.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(metadata, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
