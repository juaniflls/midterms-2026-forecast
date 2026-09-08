# Publishing NUCLEUS 42 v27.1 to GitHub

The GitHub-ready ZIP excludes `.git`. Keep the existing `.git` directory in your local clone.

## Update
1. Extract `midterms-2026-forecast_v27.1.0_GITHUB_READY.zip`.
2. Copy the extracted folder **contents** into your existing clone.
3. Merge/replace files.
4. Keep your existing `.git`.
5. Do not commit the ZIP itself.

## Validate
```bash
python3 scripts/validate_repository.py

cd dash_app
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt
python3 check_setup.py --deep
```

## Commit
```bash
git status
git add -A
git commit -m "Publish NUCLEUS 42 model v27.1"
git push origin main
```

Suggested tag: `v27.1.0`  
Suggested release title: `NUCLEUS 42 v27.1 — Coherent 2026 Midterms Forecast`

## Post-push
Confirm README images, notebook, HTML, Model.xlsx, final report, Dash, docs, and Actions validation all resolve.
