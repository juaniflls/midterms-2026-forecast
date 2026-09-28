# Contributing

Thank you for helping improve Nucleus 42.

## Before opening a change

1. Read the [methodology](docs/METHODOLOGY.md) and [Scenario Lab contract](docs/SCENARIO_LAB.md).
2. Keep the notebook as owner of official forecast outputs.
3. Keep the web application downstream and read-only.
4. Do not mix workbook, notebook, report, or HTML files from different runs.

## Development setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r dash_app/requirements.txt
```

Before submitting:

```bash
python scripts/validate_repository.py
python dash_app/check_setup.py
python -m compileall -q dash_app scripts
```

For model changes, restart the notebook kernel and execute all cells in order. Include the regenerated report, HTML, and release-gate evidence. For documentation or presentation-only changes, state explicitly that model mathematics and forecast outputs are unchanged.

## Pull requests

Describe the analytical reason, files changed, validation performed, and whether the change affects data, model behavior, uncertainty, Scenario Lab, or presentation only. Never commit credentials, private personal data, caches, or notebook checkpoints.

