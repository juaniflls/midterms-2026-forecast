# Nucleus 42 v30 — Model Card

## Summary

Nucleus 42 is a reproducible forecasting system for the 2026 U.S. midterm elections. It estimates the national political environment, all 435 voting House districts, and all 35 scheduled Senate elections; it also produces uncertainty distributions, validation artifacts, and an exploratory Scenario Lab.

**Developer:** Juan Ignacio Garbanzo Fallas  
**Release:** 30.11.0  
**Publication date:** 2026-09-27  
**License:** MIT

## Intended uses

- Research and public communication about election forecasting.
- Exploration of race-level margins, ratings, holds, flips, and chamber uncertainty.
- Reproducible comparison of model outputs across workbook snapshots.
- Counterfactual exploration of coherent national conditions through Scenario Lab.
- Methodological review, teaching, and audit.

## Out-of-scope uses

- Individual voting advice or voter targeting.
- Claims of deterministic election outcomes.
- Treating Scenario Lab output as a newly validated official forecast.
- Inferring individual behavior from aggregate data.
- Replacing official election administration or certified results.

## Inputs and architecture

The versioned `Model.xlsx` workbook contains current-cycle, historical, rating, polling, candidate, and control data. The executed notebook performs schema and provenance checks; national forecasting and nested temporal validation; constraint and sensitivity analysis; House and Senate race-level forecasting; complete-election Monte Carlo simulation; Scenario Lab serialization; report and HTML publication; and post-publication release gating.

## Validation

National and race-level components use time-aware historical evaluation. The release contains out-of-fold diagnostics, probability scores, calibration summaries, feature and leakage contracts, covariance checks, central-forecast contracts, and a final publication gate.

The package validator confirms the expected v30 artifacts, 18 code cells, 435 House rows, 35 Senate rows, HTML anchors, embedded Scenario Lab version, and provenance identity between `Model.xlsx` and the consolidated report.

## Scenario Lab

Scenario Lab contains 31 controls organized into 14 intervention units. It preserves the exact official baseline at zero intervention. Composition batteries are constrained, protected exogenous variables do not receive reverse feedback, and the reconciled national state is translated into a common two-party swing before race-level winners are recomputed.

It is a counterfactual presentation/runtime layer. It does not overwrite the official forecast and does not rerun the full Monte Carlo distribution for every slider movement.

## Important distinctions

- Point forecast is not control probability.
- Projected two-party vote is not win probability.
- Diagnostic stability is not a probability.
- National popular vote is independently modeled; it is not derived from chamber seat totals.
- Central maps are race-first; they are not adjusted to a chamber quota.

## Limitations

Forecasts are conditional on available inputs and modeling assumptions. Error may arise from source staleness, candidate changes, polling nonresponse, correlated geographic shocks, turnout, redistricting, third-party candidacies, structural breaks, and limited historical cycles. Senate races with sparse polling depend more heavily on structural information. Counterfactual relationships are historically informed but cannot represent every possible political regime.

## Human oversight

Source refreshes, mapping overrides, data exclusions, method promotion, and publication remain subject to documented human review. The model supports judgment; it does not eliminate it.

