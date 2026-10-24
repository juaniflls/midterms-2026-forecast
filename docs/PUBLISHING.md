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

5. Confirm the Senate coverage is 15 monitored / 20 structural-only in the workbook, report and HTML. Include South Carolina, Florida and Minnesota in the monitored layer.
6. Launch `python dash_app/app.py` and inspect the autonomous HTML application, Reset, maps, hovers and tables.

## Documentation and screenshot refresh

- Replace `assets/readme/v30-overview.png`, `v30-house.png`, and `v30-senate.png` with exports from the same completed publication.
- Keep Race Card examples and the existing Scenario Lab overview unless their interface changes.
- Use `assets/readme/scenario-historical-environments.png` to illustrate the historical selector and sliders.
- Describe functionality and coverage in the README; avoid hard-coding mutable forecast percentages or seat predictions in its prose.
- Check every notebook link against the actual repository filename.

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

