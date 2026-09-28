# Render deployment

The repository includes `render.yaml` for a single free-plan web service.

## Architecture

- `/` serves the exact autonomous HTML produced by the notebook as the complete application.
- The HTML itself contains Overview, House, Senate, Probability, Simulation, Context, Validation and Scenario Lab.
- Scenario Lab reads the embedded v30.8 payload; there is no second native implementation to drift out of sync.
- `/healthz` verifies that the publication HTML is available.

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

The free service may sleep when idle; that affects startup time, not model outputs. The Flask process is only a file server and does not calculate forecasts.
