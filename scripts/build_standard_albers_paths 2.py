from __future__ import annotations

import argparse
import gzip
import json
import math
from pathlib import Path

import numpy as np
import shapely
from shapely.geometry import box, shape


BASE_SCALE = 1070.0
BASE_TRANSLATE = (480.0, 250.0)
VIEWBOX = (0.0, 0.0, 960.0, 510.0)

PROJECTIONS = {
    "lower48": {
        "rotate": 96.0,
        "center": (-0.6, 38.7),
        "parallels": (29.5, 45.5),
        "scale": BASE_SCALE,
        "translate": BASE_TRANSLATE,
        "clip": (-7.0, -5.0, 967.0, 505.0),
    },
    "alaska": {
        "rotate": 154.0,
        "center": (-2.0, 58.5),
        "parallels": (55.0, 65.0),
        "scale": BASE_SCALE * 0.35,
        "translate": (
            BASE_TRANSLATE[0] - 0.307 * BASE_SCALE,
            BASE_TRANSLATE[1] + 0.201 * BASE_SCALE,
        ),
        "clip": (
            BASE_TRANSLATE[0] - 0.425 * BASE_SCALE,
            BASE_TRANSLATE[1] + 0.120 * BASE_SCALE,
            BASE_TRANSLATE[0] - 0.214 * BASE_SCALE,
            BASE_TRANSLATE[1] + 0.234 * BASE_SCALE,
        ),
    },
    "hawaii": {
        "rotate": 157.0,
        "center": (-3.0, 19.9),
        "parallels": (8.0, 18.0),
        "scale": BASE_SCALE,
        "translate": (
            BASE_TRANSLATE[0] - 0.205 * BASE_SCALE,
            BASE_TRANSLATE[1] + 0.212 * BASE_SCALE,
        ),
        "clip": (
            BASE_TRANSLATE[0] - 0.214 * BASE_SCALE,
            BASE_TRANSLATE[1] + 0.166 * BASE_SCALE,
            BASE_TRANSLATE[0] - 0.115 * BASE_SCALE,
            BASE_TRANSLATE[1] + 0.234 * BASE_SCALE,
        ),
    },
}


def projection_key(state_fips: str) -> str:
    if state_fips == "02":
        return "alaska"
    if state_fips == "15":
        return "hawaii"
    return "lower48"


def conic_constants(parallels: tuple[float, float]) -> tuple[float, float, float]:
    phi_0, phi_1 = np.radians(parallels)
    sin_phi_0 = math.sin(phi_0)
    n = (sin_phi_0 + math.sin(phi_1)) / 2.0
    c = 1.0 + sin_phi_0 * (2.0 * n - sin_phi_0)
    r0 = math.sqrt(c) / n
    return n, c, r0


def project_xy(state_fips: str, x, y):
    config = PROJECTIONS[projection_key(state_fips)]
    n, c, r0 = conic_constants(config["parallels"])

    longitude = np.asarray(x, dtype=float)
    latitude = np.asarray(y, dtype=float)
    rotated = np.radians(longitude + config["rotate"])
    rotated = (rotated + math.pi) % (2.0 * math.pi) - math.pi
    phi = np.radians(latitude)
    radius = np.sqrt(np.maximum(c - 2.0 * n * np.sin(phi), 0.0)) / n
    raw_x = radius * np.sin(rotated * n)
    raw_y = r0 - radius * np.cos(rotated * n)

    center_longitude, center_latitude = np.radians(config["center"])
    center_radius = math.sqrt(max(c - 2.0 * n * math.sin(center_latitude), 0.0)) / n
    center_x = center_radius * math.sin(center_longitude * n)
    center_y = r0 - center_radius * math.cos(center_longitude * n)

    screen_x = config["translate"][0] + config["scale"] * (raw_x - center_x)
    screen_y = config["translate"][1] - config["scale"] * (raw_y - center_y)
    return screen_x, screen_y


def project_geometry(geometry, state_fips: str):
    projected = shapely.make_valid(shapely.transform(
        geometry,
        lambda x, y: project_xy(state_fips, x, y),
        interleaved=False,
    ))
    clip_extent = PROJECTIONS[projection_key(state_fips)]["clip"]
    return shapely.make_valid(projected.intersection(box(*clip_extent)))


def ring_path(coordinates) -> str:
    points = np.asarray(coordinates, dtype=float)
    if len(points) < 3:
        return ""
    body = " ".join(f"{x_value:.2f},{y_value:.2f}" for x_value, y_value in points)
    return f"M{body}Z"


def geometry_path(geometry) -> str:
    parts = []
    for polygon in shapely.get_parts(geometry):
        if polygon.geom_type != "Polygon":
            continue
        exterior = ring_path(polygon.exterior.coords)
        if exterior:
            parts.append(exterior)
        for interior in polygon.interiors:
            hole = ring_path(interior.coords)
            if hole:
                parts.append(hole)
    return " ".join(parts)


def write_gzip_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    with path.open("wb") as raw_handle:
        with gzip.GzipFile(
            filename="",
            mode="wb",
            compresslevel=9,
            fileobj=raw_handle,
            mtime=0,
        ) as handle:
            handle.write(encoded)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input_geojson_gz", type=Path)
    parser.add_argument("output_paths_gz", type=Path)
    parser.add_argument("output_metadata", type=Path)
    args = parser.parse_args()

    with gzip.open(args.input_geojson_gz, "rt", encoding="utf-8") as handle:
        geojson = json.load(handle)

    projected_by_state: dict[str, list[object]] = {}
    district_paths = []
    for feature in sorted(geojson["features"], key=lambda item: item["properties"]["GEOID"]):
        properties = feature["properties"]
        state_fips = str(properties["STATEFP"])
        geometry = shapely.make_valid(shape(feature["geometry"]))
        projected = project_geometry(geometry, state_fips)
        path_data = geometry_path(projected)
        if not path_data:
            raise RuntimeError(f"Projection produced an empty path for {properties['GEOID']}")
        projected_by_state.setdefault(state_fips, []).append(projected)
        district_paths.append({
            "GEOID": str(properties["GEOID"]),
            "STATEFP": state_fips,
            "CD120FP": str(properties["CD120FP"]),
            "NAMELSAD": str(properties["NAMELSAD"]),
            "d": path_data,
        })

    state_paths = []
    for state_fips, geometries in sorted(projected_by_state.items()):
        outline = shapely.make_valid(shapely.union_all(geometries))
        state_paths.append({"STATEFP": state_fips, "d": geometry_path(outline)})

    payload = {
        "projection": "D3 standard geoAlbersUsa composite parameters",
        "viewBox": list(VIEWBOX),
        "districts": district_paths,
        "states": state_paths,
        "insets": {
            "alaska": list(PROJECTIONS["alaska"]["clip"]),
            "hawaii": list(PROJECTIONS["hawaii"]["clip"]),
        },
    }
    write_gzip_json(args.output_paths_gz, payload)
    metadata = {
        "projection": payload["projection"],
        "viewBox": payload["viewBox"],
        "district_path_count": len(district_paths),
        "state_outline_count": len(state_paths),
        "alaska_path_chars": len(next(item["d"] for item in district_paths if item["GEOID"] == "0200")),
        "hawaii_path_chars": sum(len(item["d"]) for item in district_paths if item["STATEFP"] == "15"),
        "michigan_path_chars": sum(len(item["d"]) for item in district_paths if item["STATEFP"] == "26"),
        "path_json_gzip_bytes": args.output_paths_gz.stat().st_size,
    }
    args.output_metadata.parent.mkdir(parents=True, exist_ok=True)
    args.output_metadata.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(metadata, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
