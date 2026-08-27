# Technical methodology

This document describes the operational architecture of the v26 forecast. It is a methodological guide, not a substitute for the executed notebook, the generated audit workbooks, or the frozen input data.

## Design principles

1. **Temporal honesty.** A held-out election cannot influence model selection, tuning, fitting, or feature construction inside its historical test.
2. **Production/validation separation.** Historical fold forecasts measure transportability; they are never reused as synthetic production observations.
3. **Directional architecture.** National outputs feed House and Senate modules. District and state results do not rewrite the national production fit.
4. **Post-estimation coherence.** Algebraic electoral identities and totals are applied after statistical estimation.
5. **Presentation/model separation.** HTML and Dash read model outputs. They do not mutate the workbook, notebook, report, or scenario runtime.
6. **Explicit uncertainty.** Projected vote, projected margin, win probability, ratings, and stability are distinct quantities.

## Inputs and target structure

`Model.xlsx` is the frozen input snapshot for this release. The live Google Sheet is maintained separately and must be exported under the same filename and schema before a future run.

The national architecture estimates 42 targets. They include the popular-vote environment and the chamber/rating structures consumed by downstream modules. Candidate specifications are compared under temporal validation, after which an independent production model is fit on the legitimate historical observations available for the 2026 forecast.

## Nested temporal validation

Five completed midterms are treated as sealed future elections: 2006, 2010, 2014, 2018, and 2022.

For every outer test:

1. the test election is removed;
2. model family and hyperparameters are selected using only the remaining historical training set;
3. the selected specification forecasts the excluded election; and
4. the prediction is compared with the actual result only after the forecast is complete.

This creates genuinely out-of-sample time-machine tests. The architecture also reports 2026 stability under historical exclusions, but those diagnostic predictions do not enter the production fit.

## National production model

The official forecast consumes the observed 2026 snapshot exactly as supplied. It does not predict or rewrite the national inputs before producing the baseline forecast.

The model evaluates candidate approaches, including historical benchmarks, regularized linear models, tree ensembles, and an expected-vote anchor for the popular-vote component. Regularization is necessary because the number of completed midterms is small relative to the number of candidate predictors and targets.

After estimation, constrained allocation preserves valid totals across the House and Senate target families. These transformations enforce electoral identities; they do not add new historical information.

## House model

The House layer translates the frozen national environment and district-level inputs into forecasts for all 435 voting districts.

Its outputs include projected Democratic and Republican two-party vote, projected D–R margin, win probabilities, model rating, source consensus, district winner, incumbent information, and projected holds and flips.

The official display uses Census 2026 CD120 boundaries. The source geometry is converted into a standard composite Albers USA layout with Alaska and Hawaiʻi insets. No congressional boundary is drawn manually.

## Senate model

The Senate layer runs after the national output is frozen and covers all 35 scheduled 2026 regular and special elections.

Eleven monitored races expose numerical state-model outputs. Twenty-four unmonitored Safe races remain categorical in the official forecast because the model does not have an official numerical estimate for those contests. Scenario Lab can move those races through explicitly labeled structural sensitivity anchors, but those anchors are not presented as official margins or probabilities.

For monitored contests, the model keeps separate raw polling margin, normalized two-party polling margin, historical polling-error correction, projected vote and margin, win probability, ratings, and hold/flip status.

## Simulation and uncertainty

The production dashboard stores 50,000 Monte Carlo simulations. They produce seat distributions, chamber-control probabilities, Senate 50–50 probability, close-race risk, and related uncertainty summaries.

Simulation does not alter the fitted model. It propagates the model’s estimated uncertainty into electoral outcomes.

## Scenario authority

The 42 national targets execute for every Scenario Lab intervention and remain available for audit. Under extreme counterfactuals, some national chamber-bucket responses can be less coherent than the geographic vote pathway because the historical sample is small and extrapolation is difficult.

For that reason, final scenario House and Senate seat counts are governed by the district and state geographic layers. National chamber buckets remain diagnostics and cannot reverse the direction of the reconciled popular-vote signal.

No partisan sign is imposed manually. A future replacement for the central model should be adopted only if it improves historical validation, baseline identity, sensitivity coherence, and geographic consistency together.

## Reproducibility artifacts

- `Modelo_Midterms_2026_v26_FINAL_EJECUTADO.ipynb`: complete executed pipeline.
- `Model.xlsx`: frozen input snapshot.
- `outputs/Election_Model_Final_Report_v26.xlsx`: consolidated report.
- `outputs/Model_Sensitivity_Audit_v26.xlsx`: sensitivity audit.
- `outputs/scenario_state_engine_v26.py`: generated counterfactual runtime.
- `Election_Model_2026_Dashboard_v26.html`: autonomous presentation.
- `dash_app/`: live read-only presentation layer.
- `qa/`: machine-readable validation evidence.

## Limitations

- Five historical midterms provide limited degrees of freedom.
- Relationships between national indicators are associational, not necessarily causal.
- Electoral coalitions and institutional conditions can change between cycles.
- District and state outcomes are correlated.
- Safe-race structural anchors are Scenario Lab sensitivity devices, not official numerical forecasts.
- Extreme counterfactuals can leave historical support.
- Forecasts are conditional on the frozen snapshot and become stale as new evidence arrives.
