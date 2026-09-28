# Raw Census cartography

Raw source archives are not stored in Git history. The 2026 legislative geodatabase is larger than GitHub's regular 100 MiB per-file limit; both archives are instead included in the complete release bundle and remain available directly from the U.S. Census Bureau.

Download these exact files into this directory:

| File | Official source | SHA-256 used by v17.0.0 |
|---|---|---|
| `tlgdb_2026_us_legislative.gdb.zip` | [Census 2026 legislative geodatabase](https://www2.census.gov/geo/tiger/TGRGDB26/tlgdb_2026_us_legislative.gdb.zip) | `6708d7052ac4c07c32c241f341685572fdf5c38d57a0c3144fab4751e702cfbc` |
| `cb_2025_us_state_500k.zip` | [Census 2025 state cartographic boundaries](https://www2.census.gov/geo/tiger/GENZ2025/shp/cb_2025_us_state_500k.zip) | `9cbfe171dad1555e11770c981d8f4db9e687a65c86f5bdae684eeb487e2e9b80` |

The rebuild script can download them automatically:

```bash
python scripts/rebuild_house_map.py --download-missing
```

It then creates:

- `assets/house_cd120_official.geojson.gz`
- `assets/house_cd120_albers_paths.json.gz`

Transformation details and source hashes are recorded in `metadata/`.
