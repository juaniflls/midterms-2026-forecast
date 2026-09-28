# Scenario Lab v30.7

Scenario Lab is an exploratory counterfactual system. It does not overwrite the official forecast and its output is not a second validated forecast.

## Contract

- Engine: `v30.7-directed-causal-race-first`
- Inputs: 31 controls arranged in 14 intervention units
- Geography: all 435 House districts and all 35 scheduled Senate elections
- Reset: exact official popular vote and race-first chamber baselines
- Composition batteries: bounded at 100%, with the latest edit receiving priority
- Directionality: protected root variables do not receive reverse feedback
- Translation: one reconciled national D–R swing is applied to race-level anchors

## Causal ordering

The engine distinguishes observed fundamentals, perceptions, partisan structure, approval, and polling. Direct edits are fixed first; downstream controls are then reconciled in the serialized causal order. The displayed relationship is a historically regularized association and should not be interpreted as a causal estimate.

## Incumbency

Political and economic conditions are interpreted relative to the presidential incumbent party. Party-specific inputs—such as Democratic or Republican favorability and generic-ballot polling—retain their explicit partisan direction.

## Senate structural races

All 35 scheduled elections are visible. Monitored states use their official race-model anchor. For structurally safe states, numeric Scenario Lab values are scenario-only stress estimates built from the documented structural proxy; they are not official numeric forecasts.

## Web parity

The autonomous HTML owns the serialized Scenario Lab payload. The native Dash Scenario Lab reads that same payload and reconstructs the same baseline, interventions, constraints and race-first translations. The All-in-One tab serves the exact autonomous HTML.

## Interpretation

Extreme slider positions can leave the historical support of the five-cycle training window. The interface reports that displacement. Use Scenario Lab to inspect direction, sensitivity, coherence and flip order—not as evidence that an extreme world is likely.
