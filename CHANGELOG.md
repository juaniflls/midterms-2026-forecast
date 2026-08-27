# Changelog

All notable public changes to the Midterms 2026 Forecast Model are recorded here. The project uses semantic-style release tags for public packages; methodological explanations remain in the main README and release-specific evidence remains attached to each tag.

## [26.1.0] — 2026-08-27

### Added

- Model v26 with a fourteen-unit counterfactual premodel, twelve constrained response batteries, two independent macroeconomic controls, and 31 reconciled national inputs.
- Exact Scenario Lab baseline identity across the 31 controls, all 42 targets, popular vote, House, and Senate.
- Dash v26.1 as a read-only, outcome-first interactive presentation layer.
- Scenario House and Senate geographic translation across 435 districts and all 35 scheduled Senate elections.
- Structured Senate scenario hovers and separate electoral-flip versus scenario-change labels.
- Complete v26/v26.1 screenshot gallery and an animated forecast tour.
- Dedicated methodology and Scenario Lab documentation.
- Automated repository and Dash validation on pushes and pull requests.

### Improved

- Scenario Lab controls now use a compact horizontal battery grid beneath the headline outcomes.
- Technical constraints and diagnostics are visually subordinated below the maps.
- House scenario colors now represent projected two-party vote margin with a red/blue scale and no yellow close-race fill.
- Chamber-control probability panels were added above the central House and Senate maps.
- Root documentation, citations, release metadata, output inventory, and run instructions were synchronized with v26/v26.1.

### Fixed

- Senate `Forecast` and `Holds & flips` now classify each race by projected winner versus incumbent party.
- Maine, Michigan, and North Carolina no longer appear as universal holds in the central Dash view.
- Obsolete v17–v25 report copies, v25 runtime, notebook checkpoints, environments, caches, macOS metadata, and embedded Git history were excluded from the public package.
- The old README’s broken v17 notebook, dashboard, report, and release references were replaced with the current canonical files.

### Verified

- Thirteen notebook code cells are executed and contain no stored errors.
- Reset reproduces D 50.93% / R 46.15%, House 224–211, and Senate 48–52.
- The relationship exports contain 182 directed unit pairs and 930 directed control pairs.
- All within-battery statistical weights are zero.
- Processed geography contains 435 House districts and 50 state outlines.
- `dash_app/check_setup.py` reports `STATUS: OK`.

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
[26.1.0]: https://github.com/juaniflls/midterms-2026-forecast
