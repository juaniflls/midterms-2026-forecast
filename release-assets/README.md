# Release assets

Do not commit the distribution ZIP inside the repository.

Current package:
`midterms-2026-forecast_v27.1.0_GITHUB_READY.zip`

Release identity:
`NUCLEUS 42 · v27.1.0`

Validate before publication:
```bash
python3 scripts/validate_repository.py
cd dash_app
python3 check_setup.py --deep
```
