# Render deployment

The repository includes `render.yaml` for a single free-plan web service.

## Architecture

- **All-in-One** serves the exact autonomous HTML produced by the notebook.
- Overview, Explore House, Explore Senate, Probability, Simulation, Methodology and Validation are native Dash views sourced from the consolidated v30 report.
- The native Scenario Lab reads the v30.7 payload embedded in the autonomous HTML.
- `/healthz` verifies that the report and publication sources can be resolved.

## Deploy

1. Push the complete release snapshot to the repository's default branch.
2. In Render, create a Blueprint from the repository or reconnect the existing service.
3. Keep the repository root as the service root.
4. Render installs `dash_app/requirements.txt` and starts Gunicorn using `render.yaml`.

No environment secret is required for the published snapshot. A successful local check is:

```bash
pip install -r dash_app/requirements.txt
python dash_app/check_setup.py
python scripts/validate_repository.py
```

The free service may sleep when idle; that affects startup time, not model outputs.
