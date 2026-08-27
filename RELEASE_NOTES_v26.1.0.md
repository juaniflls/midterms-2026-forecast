# v26.1.0 — Model v26 and Scenario Lab publication

This release publishes the stable v26 forecast together with the v26.1 Dash presentation layer. The official forecast, central 42-target model, fourteen-unit premodel, geographic translators, generated report, runtime, and self-contained HTML all originate from the same frozen `Model.xlsx` snapshot.

## Headline forecast

| Result | Snapshot |
|---|---:|
| Popular vote | D 50.93% · R 46.15% |
| House | D 224 · R 211 |
| House control | Democratic · 74.6% |
| Senate | D 48 · R 52 |
| Senate control | Republican · 77.5% |
| Senate 50–50 | 16.1% |

## Main release feature: Scenario Lab

Scenario Lab begins at the exact official baseline. A released intervention first satisfies the hard arithmetic of its response battery, then reconciles the remaining national state through regularized cross-unit historical associations, reruns the same 42 national targets, and translates the resulting national signal through all 435 House districts and 35 scheduled Senate elections.

The interface exposes twelve composition batteries and two independent macroeconomic controls. Components inside a battery never influence one another statistically. Their joint movement is an algebraic consequence of the 100% ceiling and edit priority. Learned relationships operate only across the fourteen units.

The relationship layer is associational, regularized, baseline-centered, and non-causal. Unsupported relationships may have zero weight. Present political perceptions cannot rewrite unemployment, inflation, or the previous presidential result.

## Dash v26.1

Dash v26.1 is a presentation-only update over the stable v26 model.

- Four headline scenario outcomes appear above the controls.
- The fourteen units are arranged in a compact responsive grid.
- House and Senate scenario maps occupy full-width result sections.
- Projected two-party vote margin controls the House scenario color scale.
- Senate scenario states use structured hovers instead of browser-native title text.
- Central Senate forecast and holds/flips compare projected winner with incumbent party.
- Technical constraints, historical support, propagation, and diagnostics remain available below the maps.

No model coefficient, vote share, probability, official margin, or official seat total was changed by the v26.1 presentation work.

## Safe Senate races

The 24 unmonitored Safe races do not receive an invented official 60–40 result. In the official forecast they remain categorical. Scenario Lab uses clearly labeled structural sensitivity anchors derived from Cook PVI and the previous seat winner-share margin proxy.

## Validation

- 13/13 notebook code cells executed.
- Zero stored notebook error outputs.
- Scenario reset equals the official forecast exactly.
- 14 intervention units and 12 composition batteries.
- 182 directed unit relationships and 930 directed control relationships.
- Zero within-battery statistical weights.
- 435 House districts and 50 state outlines.
- 35 scheduled Senate elections.
- Correct central Senate flips: Maine D, Michigan R, and North Carolina D.
- `dash_app/check_setup.py`: `STATUS: OK`.

## Use

Open the autonomous HTML directly, or install and run the live Dash application:

```bash
cd dash_app
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install --no-cache-dir -r requirements.txt
python3 check_setup.py
python3 app.py
```

Then open `http://127.0.0.1:8050`.

## Interpretation

Forecasts and scenarios are conditional estimates, not guarantees or causal claims. Extreme interventions can move outside historical support. The 42 national target outputs remain part of the audit trail; final scenario chamber seats are determined by the House district and Senate state layers.
