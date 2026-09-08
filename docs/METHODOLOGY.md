# NUCLEUS 42 · Technical Methodology · v27.1

This document describes the frozen September 8, 2026 release. Exact implementation details live in the executed notebook and generated audit workbooks.

## Production philosophy
NUCLEUS 42 separates four objects:
1. individual race estimates;
2. one official central chamber forecast;
3. full-distribution uncertainty; and
4. Scenario Lab counterfactuals.

Historical validation informs architecture selection, but outer-fold predictions never become production training rows.

## National layer
The national engine produces 42 learned targets from historical and current-cycle inputs. Model families and benchmarks are compared under nested temporal validation, then the 2026 production specification is fitted on legitimate historical observations only.

## House
All 435 districts are modeled individually from district fundamentals, current-cycle PVI/rank, incumbency/open-seat status, candidate history, ratings/source consensus, polling where available, and frozen national context.

2024 baseline: D215 / R220.

Official v27.1 central: D230 / R205.  
Control probability: D92.2%.  
Flips: 23 R→D, 8 D→R, net D+15.

Every Monte Carlo row contains all 435 district outcomes. The public central House map is coherent with the modal chamber total.

## Senate
All 35 scheduled elections are displayed. Eleven monitored races receive numerical state-model outputs; 24 Safe races remain categorical officially.

Official v27.1 central: D50 / R50.  
Republican control probability: 57.0%.  
Exact 50–50 probability: 20.2%.  
Central D flips: North Carolina, Ohio, Maine.

Within the modal chamber total, the most-supported exact monitored-state pattern is selected. The public margin/probability/winner/rating tuple is reconciled to that same central state.

## Monte Carlo
50,000 complete-election simulations generate seat distributions, control probabilities, close-race risk, uncertainty intervals, and central-pattern support. House and Senate random streams are independent.

## Historical validation
Sealed time-machine elections: 2006, 2010, 2014, 2018, 2022. Each held-out election stays unseen during its own model-selection and tuning process.

## Presentation boundary
HTML and Dash consume audited outputs and never write back into Model.xlsx or the central forecast.

## Reproducibility artifacts
- Modelo_Midterms_2026_v27.1_NUCLEUS42_FINAL.ipynb
- Model.xlsx
- Election_Model_v27_1_Coherence_Audit.html
- outputs/Election_Model_Final_Report_v27_1.xlsx
- outputs/Model_Sensitivity_Audit_v27.xlsx
- outputs/scenario_state_engine_v27.py
- dash_app/
- qa/
