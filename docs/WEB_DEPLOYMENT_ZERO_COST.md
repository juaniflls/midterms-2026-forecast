# NUCLEUS 42 — Phase 1: First public web deployment ($0)

This patch does NOT change the forecast model, notebook, Scenario Lab engine,
HTML, Model.xlsx, or generated outputs.

It only prepares the existing stable Dash application to run as a public
Python web service on Render Free.

Files:
- `.python-version` — pins Python 3.12.
- `render.yaml` — declares one free Render web service.
- `dash_app/requirements.txt` — adds Gunicorn, the production web server.

Important:
- Do NOT set Render Root Directory to `dash_app`.
- Keep the repository root as the service root because Dash reads:
  `Model.xlsx`, `outputs/`, shared `assets/`, and the final HTML.
- Auto-deploy is intentionally OFF during Phase 1.
  We first prove that the stable v27.1 site works online.
- After the online test passes, Phase 2 will add the safe Excel -> notebook ->
  audit -> publish automation.
