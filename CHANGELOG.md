# Changelog

All notable public changes to the Midterms 2026 Forecast Model are recorded here. The project uses semantic-style release tags for public packages; methodological explanations remain in the main README and release-specific evidence remains attached to each tag.

## [17.0.0] — 2026-08-22

### Added

- First public, reproducible GitHub release.
- Clean and executed Jupyter notebooks covering the complete eleven-block pipeline.
- Versioned `Model.xlsx` snapshot and a link to the live canonical Google Sheet.
- Self-contained interactive HTML dashboard.
- Official 2026 CD120 House geographic forecast map and 435-district cartogram.
- Auditable processed Census geometry and deterministic map-rebuild scripts.
- Núcleo 42 project identity, favicon, README gallery, and social-preview artwork.
- Repository-level validation, issue templates, contribution guidance, and citation metadata.

### Improved

- Senate projected-margin tooltips now distinguish projected two-party vote share from win probability.
- Party-aware color treatment was added to Senate forecast, rating, projected-margin, and holds-and-flips details.
- Workbook presentation was refined without changing formulas, values, sheet names, merged ranges, or model logic.

### Verified

- Eleven notebook code blocks execute without errors.
- The geographic House display includes 435 unique voting districts and 50 state outlines.
- The dashboard includes 435 House cartogram tiles and 50 Senate state tiles.
- Processed map assets reproduce from the official Census archives.
- The final JavaScript passes syntax validation.

[17.0.0]: https://github.com/juaniflls/midterms-2026-forecast/releases/tag/v17.0.0
