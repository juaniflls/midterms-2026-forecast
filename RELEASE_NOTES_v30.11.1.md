# Nucleus 42 v30.11.1

Focused Scenario Lab and web-delivery patch. The official forecast, workbook,
race baselines, chamber totals, Monte Carlo outputs and validation report are
unchanged from v30.11.0.

## Scenario Lab

- Engine identifier: `v30.8-reciprocal-standing-race-first`.
- Presidential approval continues to move direction of country through the
  existing historically regularized directed coefficients.
- A direct edit to direction of country now moves presidential approval through
  one bounded transpose pass over those same coefficients.
- Direct edits take priority. If both units are edited, neither is overwritten.
- There is no iterative feedback loop, and Reset remains the exact official
  race-first baseline.

## Web application

- Render now serves the autonomous publication HTML directly at `/`.
- The former `/forecast-html` deep link remains valid.
- The duplicate native Dash navigation and second Nucleus 42 header are no
  longer part of the deployed application.
- `/healthz` reports the HTML-only application state.

## Validation

- Publication setup checks: 24/24 passed.
- Repository contract checks: 37/37 passed.
- JavaScript syntax and both directions of the standing bridge were exercised.
