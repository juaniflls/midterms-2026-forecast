"""Render entry point for the canonical autonomous Nucleus 42 HTML.

The publication HTML is the complete application. Flask only serves the
audited artifact and a small health endpoint; it does not wrap it in a second
navigation shell and it never recalculates the forecast.
"""
from __future__ import annotations

from pathlib import Path

from flask import Flask, jsonify, send_file


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PUBLICATION_HTML = PROJECT_ROOT / "Election_Model_v30_11_Final_Publication.html"

app = Flask(__name__)
server = app


def _publication_response():
    if not PUBLICATION_HTML.is_file():
        return (
            "Publication HTML not found. Run the current publication notebook "
            "through the HTML export block and commit the generated file.",
            404,
        )
    response = send_file(
        PUBLICATION_HTML,
        mimetype="text/html",
        conditional=True,
        max_age=0,
    )
    response.headers["Cache-Control"] = "no-store, max-age=0"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@app.get("/")
def index():
    """Serve the autonomous HTML as the entire public application."""
    return _publication_response()


@app.get("/forecast-html")
def forecast_html():
    """Keep the former deep link working without introducing another shell."""
    return _publication_response()


@app.get("/healthz")
def healthz():
    exists = PUBLICATION_HTML.is_file() and PUBLICATION_HTML.stat().st_size > 0
    return jsonify(
        {
            "status": "ok" if exists else "error",
            "release": "30.11.1",
            "application": "autonomous-html",
            "html": PUBLICATION_HTML.name if exists else None,
        }
    ), (200 if exists else 503)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8050)
