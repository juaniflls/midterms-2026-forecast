from pathlib import Path
from flask import Flask, send_file, Response

BASE_DIR = Path(__file__).resolve().parent
PREFERRED = BASE_DIR / "Election_Model_v30_Publication.html"

app = Flask(__name__)


def forecast_html() -> Path:
    if PREFERRED.exists():
        return PREFERRED
    candidates = sorted(
        BASE_DIR.glob("Election_Model_v*.html"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        raise FileNotFoundError(
            "No Election_Model_v*.html found. Run the publication notebook and commit the generated HTML."
        )
    return candidates[0]


@app.get("/")
def index():
    path = forecast_html()
    response = send_file(path, mimetype="text/html", conditional=True, max_age=0)
    response.headers["Cache-Control"] = "no-store, max-age=0"
    return response


@app.get("/healthz")
def healthz():
    try:
        path = forecast_html()
        return {"status": "ok", "html": path.name}
    except FileNotFoundError as exc:
        return {"status": "error", "detail": str(exc)}, 503


@app.get("/favicon.ico")
def favicon():
    return Response(status=204)
