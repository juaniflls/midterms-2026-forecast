# NUCLEUS 42 · Model Card

## Identity
**NUCLEUS 42 — Independent U.S. Election Forecasting System**

**Release:** v27.1.0  
**Snapshot:** September 8, 2026  
**Author:** Juan Ignacio Garbanzo Fallas

## Intended use
Electoral analysis, political science research, reproducible forecasting, uncertainty communication, model auditing, and structured counterfactual exploration.

Not intended for voter targeting, individual persuasion, or deterministic claims.

## v27.1 outputs
- Popular vote: D 52.07% · R 45.01% · Other 2.92%
- House: D230 · R205 · D control 92.2%
- Senate: D50 · R50 · R control 57.0%
- Senate exact 50–50: 20.2%
- 50,000 complete-election simulations
- 42 national targets
- 435 House district forecasts
- 35 Senate elections displayed
- 11 monitored Senate numerical race models
- 24 Safe Senate categorical official races

## Central forecast contract
Race engines produce individual distributions. Complete elections are simulated. A modal chamber total is identified. A coherent map within that total becomes the single public central forecast. Full-distribution control probability remains a separate uncertainty statistic.

## Validation
The national architecture is evaluated through sealed midterm tests for 2006, 2010, 2014, 2018, and 2022. Model selection/tuning occur inside each historical training set. Held-out outcomes are used only for evaluation.

## Scenario Lab
31 controls in 14 intervention units, including 12 hard composition batteries. Untouched controls are reconciled through regularized historical relationships before the same downstream national and geographic layers are rerun.

Scenario Lab is associational, not causal.

## Limitations
Limited historical sample, structural change across cycles, correlated geographic errors, sparse House polling, categorical treatment of some Safe Senate races, extrapolation risk in extreme counterfactuals, and staleness as the frozen snapshot ages.
