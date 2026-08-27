# Scenario Lab

Scenario Lab is the interactive counterfactual layer introduced in model v26 and presented in Dash v26.1. It asks how the same forecast responds when selected national conditions change while related inputs remain mathematically feasible and historically coherent.

It does not overwrite the official forecast, train a competing model, or claim that a slider movement causes an electoral outcome.

## Baseline identity

Baseline identity is a hard release contract:

- sliders at the observed snapshot reproduce all 31 official controls;
- the same state reproduces all 42 official targets;
- popular vote returns D 50.93% and R 46.15%;
- House returns D 224 and R 211; and
- Senate returns D 48 and R 52.

`Reset all inputs` must return to this exact state.

## Fourteen intervention units

The 31 national controls are organized into fourteen user-facing units.

| Type | Units |
|---|---|
| Twelve composition batteries | Presidential approval; direction of country; ideology; party identification; partisan lean; Democratic favorability; Republican favorability; economic conditions; economic direction; job market; previous presidential result; expected midterm popular vote |
| Two independent macroeconomic controls | Unemployment; inflation |

Components of a composition battery may sum below 100%, leaving an unallocated or other category, but they may never exceed 100%.

## Hard constraints

- Each composition battery remains at or below 100%.
- A direct edit is preserved whenever it is feasible.
- If same-battery edits conflict, the most recently edited control receives priority.
- Compatible direct interventions in different batteries remain active.
- Unemployment and inflation are independent controls rather than parts of a 100% battery.

The interface previews battery arithmetic while dragging. The full counterfactual pipeline runs when the slider is released.

## Learned historical coherence

After hard constraints are satisfied, the premodel reconciles the other national controls through cross-unit historical associations.

The relationship system uses Ledoit–Wolf covariance shrinkage, leave-one-election-year-out sign reliability, bounded row leverage, damped iterative feedback, and historical-support diagnostics.

There are 182 directed relationships among the fourteen units and 930 directed relationships among the 31 controls. Unsupported relationships may receive a weight near or equal to zero.

Statistical relationships inside one composition battery are fixed at zero. If one component changes because another component was edited, that movement comes from the battery’s hard arithmetic—not from a learned within-battery influence.

## Temporal roots

Present political perceptions cannot rewrite already observed facts. The model therefore prevents downstream perception units from rewriting unemployment, inflation, and the previous presidential election result.

These variables can be directly intervened on by the user, but they are protected from inappropriate backward propagation.

## Counterfactual execution

Every released intervention follows the same sequence:

1. apply the direct edits and their order;
2. enforce the hard constraints;
3. reconcile all fourteen units;
4. build a coherent 31-control snapshot;
5. run the same central 42-target model;
6. calculate the reconciled popular-vote swing;
7. translate that swing across 435 House districts; and
8. translate it across all 35 scheduled Senate elections.

The Dash layer is read-only. It never writes the scenario back into `Model.xlsx`, the notebook, the report, the HTML, or the official forecast.

## House display

The Scenario House map is colored by projected D–R two-party vote margin: blue for a Democratic projected winner, red for a Republican projected winner, lighter shades for closer margins, and darker shades for larger margins.

Yellow is not used as a close-race fill. Win probability remains available in the hover as a separate uncertainty measure.

The hover distinguishes projected D and R vote, projected margin, winner, win probability, rating, incumbent party, electoral hold/flip, and change from the official forecast.

## Senate display

Monitored races use their numerical state-model baseline. Unmonitored Safe races use a structural sensitivity anchor only inside Scenario Lab. The anchor combines Cook PVI and the prior winner-share margin proxy and is clearly labeled as non-official.

The interface distinguishes:

- **Electoral flip:** scenario winner differs from the incumbent party.
- **Scenario change:** scenario winner differs from the official model winner.

The central forecast’s hold/flip label is derived from projected winner versus incumbent party. It is not inherited from an empty or obsolete display field.

## Interpretation

Scenario Lab is best used for disciplined comparisons within or near historical support. It can reveal how the model’s learned architecture and geographic layers respond to a coherent change in the national environment.

It cannot establish that moving one opinion measure would cause voters or seats to move by the displayed amount. Extreme combinations are extrapolations, and a user should inspect the support and constraint diagnostics shown below the maps.

## Regression contracts

- Baseline input and target identity.
- Twelve batteries at or below 100%.
- Last-edit priority within an incompatible battery.
- Persistence of compatible cross-battery interventions.
- 182 unit and 930 control relationship rows.
- Zero within-battery statistical weights.
- Bounded and convergent feedback.
- No geographic direction reversal relative to the reconciled popular-vote swing.
- House 224–211 and Senate 48–52 at reset.
- Approximately +8.44 percentage points of uniform D–R Senate swing to reach D 55 with the current 35 race anchors.
