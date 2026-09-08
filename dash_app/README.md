# Midterms 2026 Forecast — Dash v27.1 FINAL

This folder is the downstream interactive presentation layer for the **frozen v27.1 model**. It does not contain private copies of `Model.xlsx`, reports, notebook code, scenario runtime, or the standalone HTML. Those remain at repository root / `outputs/` and are discovered dynamically.

## Tabs

- **Forecast** — serves the exact notebook-generated standalone HTML 1:1 from repository root. This guarantees visual parity with the final audited HTML, including the House geographic map and cartogram, 435-race explorer, House flips, Senate race desk, control probability, Monte Carlo distributions, national context, validation, Model Quality, Electoral Risk, and final uncertainty.
- **Overview / House / Senate / Probability / Simulation / Context / Validation** — native Dash drill-down views backed by the same audited report.
- **Scenario Lab** — counterfactual layer. It has 31 controls organized into 14 intervention units (12 constrained composition batteries + 2 independent macro controls), preserves the 42-target engine, and translates the reconciled national state to all 435 House districts and all 35 scheduled Senate races. It never overwrites the official forecast.

## Critical baseline contract

Scenario Lab reset is read dynamically from the current audited report. The visible House seat headline is the count of the **435 district winners shown on the scenario map**, not rounded expected seat mass. Expected seat mass remains diagnostic-only. Senate reset similarly uses race winners.

## Run

From repository root, keep this directory named `dash_app/` and run:

```bash
cd dash_app
python3 check_setup.py --deep
python3 app.py
```

If dependencies are missing:

```bash
pip install -r requirements.txt
```

The app expects sibling repository assets:

- `../Model.xlsx`
- `../outputs/Election_Model_Final_Report_v27_1.xlsx` (or newer matching v27.x report)
- `../outputs/scenario_state_engine_v27.py`
- `../Election_Model_v27_1_Coherence_Audit.html` (or supported notebook HTML name)
- `../assets/house_cd120_albers_paths.json.gz`
- `../assets/branding/Midterms_2026_Logo.svg`

## Update workflow

1. Update the canonical source workbook.
2. Run the frozen v27.1 notebook completely.
3. Confirm the report, runtime, and standalone HTML were regenerated.
4. Dash detects the new audited outputs automatically.

Do not edit forecast constants in Dash.


## v27.1 Final UI navigation

The native Dash edition now separates the roles of each surface:

- **All-in-One** — exact notebook-authored HTML, served 1:1.
- **Overview** — concise national snapshot.
- **Explore House** — interactive 435-district map, source consensus, flips/net change and district desk.
- **Explore Senate** — interactive 50-state/35-election map, monitored source consensus, flips/net change and race desk.
- **Probability** — control odds, close-race risk and uncertainty intervals.
- **Simulation** — cross-variable Monte Carlo explorer and chamber distributions.
- **Methodology** — readable production pipeline plus collapsible technical contracts.
- **Validation** — historical performance first, deep technical audits collapsed below.
- **Scenario Lab** — unchanged counterfactual engine; official forecast remains frozen.

The final v27.1 report currently exposes House source consensus through `Core3 Consensus Rating`; Dash aliases that field downstream as `Source Consensus Rating` without altering the workbook or forecast.


## Nucleus 42

Public identity: **Nucleus 42 — Independent U.S. Election Forecasting System**.

The final Dash remains downstream of the frozen v27.1 notebook/report/HTML.

Important final display rules:
- House source consensus is exactly the same 435-district v27 consensus used by notebook Block 8.
- Senate does not display a source-consensus layer because the final HTML does not define one.
- House/Senate flip cards use party colors and net-change color follows the direction of the net.
- Probability, Simulation, Methodology and Validation use stable containers intended to prevent Plotly/table overlap.
- Scenario Lab is unchanged.
