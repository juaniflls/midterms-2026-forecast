# 2026 Midterm Forecast — Dash v26.1 presentation

Dash v26.1 is the interactive presentation layer for the notebook-generated
forecast. It does not train an independent model and does not read an older
dashboard as a data source.

The underlying notebook, report, Scenario runtime, and model remain v26. This
presentation update changes layout, labels, map color logic, tooltips, and the
display calculation that classifies Senate holds and flips; it does not change
any forecast probability, vote share, margin, seat estimate, or model weight.

## Presentation changes in v26.1

- Scenario Lab places the four headline outcomes first, followed by a compact
  horizontal grid of the fourteen intervention units and then the full House
  and Senate maps.
- The Scenario House map defaults to projected two-party vote and uses only the
  Democratic/Republican margin scale; close races are no longer yellow.
- Scenario Senate tiles expose a structured hover with projected D/R vote,
  winner, margin, probability, official rating, hold/flip status, and change
  from the official forecast.
- The central House and Senate views include chamber-control probability panels
  above their filters and maps.
- Central Senate `Forecast` and `Holds & flips` classify outcomes by comparing
  the projected winner with the incumbent party.
- Input constraints and technical diagnostics remain available in collapsed
  sections below the Scenario maps.

## Methodological contract

The official forecast uses the observed 2026 snapshot exactly as supplied.
Scenario Lab starts from that same snapshot and adds a counterfactual pipeline:

1. apply the mathematical constraint of the edited response battery;
2. reconcile fourteen intervention units with regularised historical
   associations;
3. construct a coherent 31-control counterfactual snapshot;
4. execute the same central 42-target model;
5. translate the reconciled popular-vote swing through the House district and
   Senate state layers.

Twelve units are mutually exclusive response batteries whose components may
sum below, but never above, 100%. Unemployment and inflation are independent
macroeconomic units. Learned propagation is permitted only between units.
Components inside one battery move relative to each other solely because of the
hard composition constraint.

When direct requests in the same battery conflict, the most recently edited
control receives priority. Compatible interventions in other batteries remain
active. Slider callbacks run on mouse release; the battery projection is shown
immediately and the premodel/42-target/geographic pipeline then updates the full
Scenario Lab state.

The relationship system is associational rather than causal. It uses
Ledoit–Wolf shrinkage, leave-one-election-year-out sign reliability and a
contraction bound. Unsupported relationships may have zero weight. Political
perceptions cannot rewrite unemployment, inflation or the previous presidential
result.

## Authoritative outputs

- The notebook owns the official forecast, report, HTML and Scenario runtime.
- The 42 national targets execute for every scenario and remain available for
  audit.
- House district and Senate state models own the final scenario seat counts.
  National chamber buckets are diagnostic and cannot reverse the geographic
  popular-vote pathway.
- The 24 unmonitored Safe Senate races have no official numerical probability,
  margin or vote share. Scenario Lab uses clearly labelled structural
  sensitivity anchors only; no artificial 60–40 default is used.

## Required files

When `dash_app/` is directly inside the repository root, it reads:

- `../outputs/Election_Model_Final_Report_v26.xlsx`;
- `../Election_Model_2026_Dashboard_v26.html`;
- `../Model.xlsx`;
- `../outputs/scenario_state_engine_v26.py`;
- `../assets/house_cd120_albers_paths.json.gz`;
- `../assets/branding/Midterms_2026_Logo.svg`.

The report SHA-256 must match the current `Model.xlsx`. Dash is read-only with
respect to these sources.

## Run on macOS or VS Code

Run the v26 notebook first from the repository root. Then:

```bash
cd dash_app
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
python3 check_setup.py
python3 app.py
```

Open `http://127.0.0.1:8050`. If the port is occupied:

```bash
DASH_PORT=8051 python3 app.py
```

## Release regression contracts

- Zero intervention reproduces the official 31-input state, all 42 targets,
  popular vote, House 224–211 and Senate 48–52 exactly.
- Twelve composition batteries remain at or below 100%.
- The most recent same-battery edit wins; cross-battery direct edits persist.
- The relationship exports contain 182 directed 14-unit pairs and 930 directed
  31-control pairs, with all within-battery statistical weights equal to zero.
- Geographic response never reverses the sign of the reconciled popular-vote
  swing.
- With the current 35 Senate anchors, D55 requires approximately +8.44 points
  of uniform D–R margin swing and seven additional flips. D55 at baseline is a
  regression failure.
- The Dash package contains no workbook, runtime, HTML, geometry or cache copy.
