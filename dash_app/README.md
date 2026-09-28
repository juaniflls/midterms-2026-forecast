# Nucleus 42 Dash application

This is the interactive Render layer for the v30.11 release.

- `All-in-One` embeds the autonomous notebook publication.
- The remaining analytical tabs are native Dash views of `outputs/Election_Model_Final_Report_v30.xlsx`.
- `Scenario Lab` reads the canonical v30.7 payload from the autonomous HTML and preserves the exact official race-first baseline.
- The app is read-only with respect to `Model.xlsx`, the notebook and generated outputs.

Run locally from the repository root:

```bash
pip install -r dash_app/requirements.txt
python dash_app/check_setup.py
python dash_app/app.py
```

Then open `http://127.0.0.1:8050`.
