# Scenario Lab — NUCLEUS 42 v30.9

The official v30 forecast, 42-target statistical engine, input workbook, and Monte Carlo remain unchanged. The Scenario Lab is an **exploratory, downstream counterfactual**, not a new probabilistic forecast.

**31 sliders / 14 intervention units:** Controls cover presidential approval, direction of country, ideology, party identification and lean, party favorability, economic indicators and perceptions, the job market, the previous presidential result, and generic-ballot polls. Historical reference ranges are shown beside the controls.

**Historic environments:** A selector beside the scenario CSV download offers 2006, 2010, 2014, 2018, and 2022. All 31 starting control values are read from the `Model` sheet of the unmodified `Model.xlsx`, using each row's `Midterm Year`. This compares the observed conditions of those years applied hypothetically to the **2026** races and candidates. It does **not** predict the election results of those historical years. The 2026 default is preserved; users may edit the controls after selecting a year; `Reset` restores the official 2026 state.

The workbook stores some economic percentages as fractions and others as whole percentage points. Within the three economic composition batteries, the Scenario Lab now normalizes such values **per cell** rather than rescaling entire rows indiscriminately. Any observation exceeding a hard 100% composition constraint is projected to the feasible composition; the UI should not display an impossible battery.

**Race-specific scenario response:** National intervention logic produces a national two-party D−R margin impulse. Each of the 435 House races and 35 Senate races is then adjusted by its own geographical response factor, estimated from matched 2016/2020/2024 presidential vote margins and strongly ridge-shrunk toward a unit national response. House district and Senate state factors are fitted separately. The panel and exported CSV report the **actual per-race applied shift**, not the national impulse. At-large `-AL` IDs map to their `-01` equivalents in the historical source.

**Interface and exports:** The interface identifies the selected historic environment and subsequent manual edits, reports a coherence diagnostic, and updates House and Senate scenario maps. Download the scenario image or race CSV; the CSV includes the actual applied race shift. Reset restores the official 2026 baseline.

**Scientific limitation:** There are only two presidential-election transitions for fitting each local response. These are descriptive sensitivities, not validated causal impacts or a fully trained 470-target counterfactual. A shared national macro impulse can still move all local contests in the same direction: opposite signs are permitted by the formula if supported by evidence, not manufactured for visual variety. Other localized candidate shocks and geographically heterogeneous macro effects cannot be inferred rigorously from the five national midterm rows alone.

**Hard requirements:** At zero interventions the Scenario Lab is identical to the official 2026 popular vote, House and Senate central result. Scenario adjustments never overwrite `Model.xlsx` or the official report and never change Monte Carlo probabilities. Each selected year and manual edit must preserve composition constraints. Render serves the HTML the notebook generates. The Python adapter in `dash_app/scenario_engine.py` reads the same serialized HTML contract.

