# Release assets

Do not commit the distribution ZIP inside the repository. Upload it separately to the corresponding GitHub Release if a tagged release is created.

Current package:

```text
midterms-2026-forecast_v26.1.0_GITHUB_READY.zip
```

The repository package contains the v26 notebook, frozen workbook, v26 HTML, Dash v26.1, current generated outputs, processed geography, visual assets, documentation, and QA evidence. Raw Census source archives remain external because the legislative geodatabase exceeds GitHub’s regular per-file limit.

Before publication, run:

```bash
python3 scripts/validate_repository.py
cd dash_app
python3 check_setup.py
```
