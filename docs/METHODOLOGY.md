# Nucleus 42 v30 methodology

## Scope

Nucleus 42 forecasts the 2026 national two-party environment, all 435 voting House districts, and all 35 scheduled Senate elections. Chamber totals are reconstructed from race-level winners; they are never imposed as quotas.

## Production sequence

1. `Model.xlsx` is validated as the release input snapshot.
2. The national module estimates 42 political and economic targets with time-aware validation.
3. The House module builds one tuple per district: margin, probability, rating, winner, hold/flip, and source diagnostics.
4. The Senate module evaluates all scheduled races. Monitored states use the selected state specification; structural races remain explicit and auditable.
5. Monte Carlo draws complete elections, preserving cross-race uncertainty, and estimates chamber-control probability.
6. A coherent central configuration is selected and audited independently from the simulation mode.
7. Release gates validate identities, isolation rules, row counts, probabilities, and publication consistency before the report and HTML are exported.

## Validation

Historical elections are treated as held-out future cycles. Model choices are evaluated using out-of-fold errors, calibration and stability diagnostics. Where a challenger fails its preregistered gate, the validated incumbent specification is preserved. Diagnostic stability is a sensitivity score, not an election probability.

## Probability and point forecasts

The race point forecast, race win probability, chamber control probability, expected seats, and the representative central map answer different questions. The dashboard labels them separately. The national popular-vote module is independently validated and is not mechanically derived from chamber seat totals.

## Release contract

The canonical public snapshot consists of:

- `Model.xlsx`
- `NUCLEUS42_v30_11_FINAL_PUBLICATION_RELEASE.ipynb`
- `outputs/Election_Model_Final_Report_v30.xlsx`
- `Election_Model_v30_11_Final_Publication.html`

These files must be regenerated and published together. The Dash layer reads them; it does not retrain or mutate the model.

For intended use and limitations, see [MODEL_CARD.md](../MODEL_CARD.md). For counterfactual behavior, see [SCENARIO_LAB.md](SCENARIO_LAB.md).
