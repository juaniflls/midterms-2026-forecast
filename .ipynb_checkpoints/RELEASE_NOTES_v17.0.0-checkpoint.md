# v17.0.0 — First Public Release

This is the first public, reproducible release of the **Midterms 2026 Forecast Model**.

The release packages the full electoral data science workflow: 42 national targets, nested temporal validation, an independent production fit, electoral constraints, downstream House and Senate modules, Monte Carlo simulation, stability diagnostics, audit outputs, and a self-contained interactive dashboard.

## Highlights

- Five outer historical examinations: 2006, 2010, 2014, 2018, and 2022.
- 435 official CD120 House districts in both geographic and cartogram views.
- 35 scheduled Senate elections with forecast, ratings, holds-and-flips, projected-margin, and win-probability views.
- Official Census cartography with a reproducible raw-to-display transformation.
- A visually refined `Model.xlsx` workbook with model logic and structure preserved exactly.
- A validated clean notebook, an executed audit copy, and a consolidated final report.
- Núcleo 42 visual identity and publication-ready repository assets.

## Which download should I use?

- **Repository source:** best for reading the README, reviewing code, opening issues, and contributing through pull requests.
- **`Modelo_Midterms_2026_v17_Reproducible_Final.zip`:** best for exact offline reproduction. It includes the raw Census source archives, all generated workbooks, checksums, and the complete QA record.
- **`Model.xlsx`:** a frozen release snapshot. For the latest maintained inputs, use the [live canonical Google Sheet](https://docs.google.com/spreadsheets/d/1xw1BG083q41GgdWCJ_oAbqqXQEoec5aqejzXknVqYtg/edit?usp=sharing).

## Reproduction

1. Extract the complete ZIP without altering the folder structure.
2. Create the Python 3.12 environment from `requirements.txt` or `environment.yml`.
3. Open `Modelo_Midterms_2026_v17.ipynb` in JupyterLab.
4. Select the project kernel and run all cells.
5. Inspect `outputs/`, `qa/`, and `Election_Model_2026_Dashboard_v17.html`.

## Validation summary

The release passed all repository and package checks. The clean notebook contains eleven code cells and no stored output; the executed copy completes without errors; the House map contains 435 district paths, 435 cartogram tiles, and 50 state outlines; the Senate map contains 50 state tiles; and all presentation-only workbook changes preserve the source values, formulas, ranges, and sheet structure.

## Interpretation

Results are probabilistic and data-dependent. A forecast snapshot is not a permanent prediction, a guarantee, or an institutional endorsement. Cite this tagged release when discussing its results so that the data and implementation remain identifiable.
