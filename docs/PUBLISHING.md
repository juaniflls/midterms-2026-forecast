# Publishing checklist

## Before committing

1. Confirm `Model.xlsx` is the intended release snapshot.
2. Execute the v30 notebook from a fresh kernel through the post-HTML release gate.
3. Do not manually edit the generated report or publication HTML.
4. Run:

```bash
python scripts/validate_repository.py
python dash_app/check_setup.py
python -m compileall -q dash_app
```

5. Launch `python dash_app/app.py` and inspect the autonomous HTML application, Reset, maps, hovers and tables.

## GitHub release

Use the tag `v30.11.1`. The README screenshots illustrate functionality from the included executed snapshot; they are not hard-coded promises about later forecast values.

GitHub's social preview must be uploaded manually in **Settings → General → Social preview** using `assets/social/nucleus42-v30-social-preview.jpg`.

## Render

After the commit is available on the configured branch, allow the Blueprint to redeploy. Confirm `/healthz`, `/`, every HTML navigation section, and the Scenario Lab baseline.

## Never publish

- a partially executed notebook;
- a report and HTML generated from different workbooks;
- credentials or private configuration;
- cached environments, notebook checkpoints, or duplicate macOS metadata files.
