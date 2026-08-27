from __future__ import annotations

import os
import base64

import pandas as pd
from dash import ALL, Dash, Input, Output, State, ctx, dcc, html, no_update

from core import BRAND_LOGO_PATH, DASH_DIR, MODEL_PATH, load_bundle, load_senate_map, project_signature, safe_value, status_payload
from figures import (
    PLOTLY_CONFIG,
    house_map_figure,
    house_map_patch,
    national_scenario_figure,
    party_margin,
    projected_margin_color,
    scenario_house_summary,
    scenario_senate_summary,
    senate_color,
    simulation_scatter,
)
from scenario_engine import (
    COMPOSITION_BATTERIES,
    load_scenario_engine,
    normalize_composition_values,
)
from views import render_tab, table_component

app = Dash(
    __name__,
    assets_folder=str(DASH_DIR / "assets"),
    suppress_callback_exceptions=True,
    title="2026 Midterm Forecast — Interactive",
)
server = app.server

INITIAL_SIGNATURE = project_signature()


def brand_logo_src() -> str:
    if not BRAND_LOGO_PATH.exists():
        return ""
    encoded = base64.b64encode(BRAND_LOGO_PATH.read_bytes()).decode("ascii")
    return f"data:image/svg+xml;base64,{encoded}"


def source_chip(signature: str):
    try:
        st = status_payload(signature)
        version = st.get("report_version")
        label = f"v{version}" if isinstance(version, int) and version >= 0 else "latest"
        return [html.Span(className="live-dot"), f"Model {label} · auto-sync"]
    except Exception:
        return [html.Span(className="live-dot warning-dot"), "Waiting for model output"]


app.layout = html.Div([
    dcc.Store(id="data-signature", data=INITIAL_SIGNATURE),
    # Ordered intervention state is global so tab changes cannot detach the
    # sliders from the counterfactual being displayed.
    dcc.Store(
        id="scenario-direct-overrides",
        data={"values": {}, "order": []},
        storage_type="memory",
    ),
    dcc.Interval(
        id="file-watch",
        interval=int(os.environ.get("DASH_FILE_WATCH_MS", "5000")),
        n_intervals=0,
    ),

    html.Div([
        html.Div([
            html.Img(src=brand_logo_src(), className="brand-logo"),
            html.Div([
                html.Div("2026 Forecast Desk", className="brand-name"),
                html.Div("Observatorio de los Estados Unidos · CIEP-UCR", className="brand-sub"),
            ]),
        ], className="brand"),
        html.Div(id="source-status", className="live-chip", children=source_chip(INITIAL_SIGNATURE)),
    ], className="topbar"),

    html.Header([
        html.Div("UNITED STATES · 120TH CONGRESS", className="kicker"),
        html.Div("MIDTERMS 2026", className="title"),
        html.Div("Forecast model · political data science · interactive Dash edition", className="subtitle"),
    ], className="header"),

    html.Div([
        dcc.Tabs(
            id="main-tabs",
            value="overview",
            persistence=True,
            persistence_type="session",
            className="tab-container",
            children=[
            dcc.Tab(label="Overview", value="overview", className="tab", selected_className="tab--selected"),
            dcc.Tab(label="House", value="house", className="tab", selected_className="tab--selected"),
            dcc.Tab(label="Senate", value="senate", className="tab", selected_className="tab--selected"),
            dcc.Tab(label="Probability", value="probability", className="tab", selected_className="tab--selected"),
            dcc.Tab(label="Simulation", value="simulation", className="tab", selected_className="tab--selected"),
            dcc.Tab(label="Context", value="context", className="tab", selected_className="tab--selected"),
            dcc.Tab(label="Validation", value="validation", className="tab", selected_className="tab--selected"),
            dcc.Tab(label="Scenario Lab", value="scenario", className="tab", selected_className="tab--selected"),
            ],
        ),
    ], className="tabs-wrap tabs-wide"),

    html.Main(id="tab-content", children=render_tab("overview", INITIAL_SIGNATURE)),

    html.Footer([
        html.Div("Interactive presentation layer · reads audited model outputs · does not mutate Model.xlsx"),
        html.Div("Forecast model by Juan Ignacio Garbanzo Fallas · Observatorio de los Estados Unidos · CIEP-UCR"),
    ], className="footer"),
])


@app.callback(
    Output("data-signature", "data"),
    Output("source-status", "children"),
    Input("file-watch", "n_intervals"),
    State("data-signature", "data"),
    prevent_initial_call=False,
)
def watch_files(_n, current):
    sig = project_signature()
    # Dash propagates callbacks even when a Store is rewritten with an identical
    # value. Avoid touching the Store unless a rendered data source truly changed;
    # otherwise the active tab and every signature-dependent graph rebuild on each
    # polling interval, resetting controls and producing visible flicker.
    if sig == current:
        return no_update, no_update
    return sig, source_chip(sig)


@app.callback(
    Output("tab-content", "children"),
    Input("main-tabs", "value"),
    Input("data-signature", "data"),
)
def render_active_tab(tab, signature):
    try:
        return render_tab(tab, signature)
    except Exception as exc:
        return html.Section([
            html.Div("Dash data source error", className="section-kicker"),
            html.H2(type(exc).__name__, className="section-title"),
            html.Pre(str(exc), className="error-box"),
            html.P("The notebook/model files were not modified. Fix the missing output or asset and Dash will retry automatically.", className="detail-copy"),
        ], className="section")


# ---------------------------- House explorer ----------------------------
@app.callback(
    Output("house-map", "figure"),
    Output("house-map-legend", "children"),
    Input("house-state", "value"),
    Input("house-rating", "value"),
    Input("house-metric", "value"),
    Input("house-flags", "value"),
    Input("house-district", "value"),
    Input("data-signature", "data"),
)
def update_house_map(state, rating, metric, flags, district, signature):
    house = load_bundle(signature)["house"]
    metric = metric or "rating"
    legends = {
        "rating": [("Safe D", "#073B75"), ("Lean D", "#5B9BD5"), ("Toss-up", "#F4D35E"), ("Lean R", "#DF6670"), ("Safe R", "#7F0000")],
        "probability": [("R win", "#7F0000"), ("Close R", "#F2B5B9"), ("Close D", "#A8D5EC"), ("D win", "#073B75")],
        "margin": [("Larger R margin", "#7F0000"), ("Close R", "#F5C6CA"), ("Close D", "#C7E4F2"), ("Larger D margin", "#073B75")],
        "consensus": [("R consensus", "#C1121F"), ("Mixed", "#F4D35E"), ("D consensus", "#1769AA")],
        "flips": [("D hold", "#0B5CAB"), ("D flip · striped", "repeating-linear-gradient(45deg,#1769AA 0 4px,#D9ECF7 4px 8px)"), ("R flip · striped", "repeating-linear-gradient(45deg,#C1121F 0 4px,#F8D5D8 4px 8px)"), ("R hold", "#C1121F")],
    }
    legend = [html.Span([html.I(style={"background": color}), label]) for label, color in legends[metric]]
    return house_map_figure(house, metric, state or "ALL", rating or "ALL", flags or [], district), legend


@app.callback(
    Output("house-district", "value"),
    Input("house-map", "clickData"),
    State("house-district", "value"),
    prevent_initial_call=True,
)
def select_house_from_map(click_data, current):
    if not click_data or not click_data.get("points"):
        return no_update
    point = click_data["points"][0]
    district = point.get("customdata")
    if isinstance(district, (list, tuple)):
        district = district[0] if district else None
    return district or current or no_update


def house_detail_component(row: pd.Series, metric: str = "rating"):
    district = safe_value(row.get("District ID"))
    label = safe_value(row.get("District Label"))
    rating = safe_value(row.get("Forecast Rating"))
    winner = safe_value(row.get("Projected Winner"))
    dprob = float(row.get("D Win Probability")) if pd.notna(row.get("D Win Probability")) else 50.0
    rprob = float(row.get("R Win Probability")) if pd.notna(row.get("R Win Probability")) else 50.0
    margin = float(row.get("Projected Margin PP")) if pd.notna(row.get("Projected Margin PP")) else 0.0
    rows = [
        ("Projected margin", f"{'D' if margin >= 0 else 'R'}+{abs(margin):.1f} pp"),
        ("Projected flip", safe_value(row.get("Projected Flip"))),
        ("Consensus", safe_value(row.get("All Source Consensus Rating"))),
        ("Core 3", safe_value(row.get("Core3 Consensus Rating"))),
        ("PVI", safe_value(row.get("PVI Raw"))),
        ("Incumbent", safe_value(row.get("Incumbent Name"))),
        ("Incumbent party", safe_value(row.get("Incumbent Party Raw"))),
        ("Open seat", safe_value(row.get("Open Seat"))),
        ("Democratic candidate", safe_value(row.get("Democratic Candidate"))),
        ("Republican candidate", safe_value(row.get("Republican Candidate"))),
        ("Rating coverage", safe_value(row.get("Rating Coverage"))),
        ("Quality flag", safe_value(row.get("Quality Flag"))),
    ]
    dshare, rshare = 50 + margin / 2, 50 - margin / 2
    if metric == "probability":
        hero = [
            html.Div([html.Div([html.Div("D WIN", className="detail-label"), html.Div(f"{dprob:.1f}%", className="detail-number dem")]), html.Div([html.Div("R WIN", className="detail-label"), html.Div(f"{rprob:.1f}%", className="detail-number rep")])], className="detail-pair"),
            html.Div([html.Div(style={"width": f"{dprob:.2f}%"}, className="prob-dem"), html.Div(style={"width": f"{rprob:.2f}%"}, className="prob-rep")], className="prob-track"),
        ]
    elif metric == "margin":
        hero = [html.Div("PROJECTED MARGIN", className="detail-label"), html.Div(party_margin(margin), className=f"detail-number {'dem' if margin >= 0 else 'rep'}"), html.Div(f"D {dshare:.2f}% · R {rshare:.2f}% projected two-party vote", className="scenario-copy")]
    elif metric == "consensus":
        hero = [html.Div("SOURCE CONSENSUS", className="detail-label"), html.Div(safe_value(row.get("All Source Consensus Rating")), className="detail-number")]
    elif metric == "flips":
        hero = [html.Div("HOLD / FLIP", className="detail-label"), html.Div(safe_value(row.get("Projected Flip")), className="detail-number"), html.Div(f"Projected {winner} · {party_margin(margin)}", className="scenario-copy")]
    else:
        hero = [html.Div("MODEL RATING", className="detail-label"), html.Div(rating, className="detail-number")]
    return [
        html.Div("DISTRICT DETAIL", className="detail-kicker"),
        html.H3(f"{district} · {label}", className="detail-title"),
        html.Div(rating, className=f"race-rating {'dem-soft' if winner == 'D' else 'rep-soft'}"),
        *hero,
        html.Hr(className="detail-rule"),
        *[html.Div([html.Div(k, className="detail-label"), html.Div(v, className="detail-text")], className="detail-row") for k,v in rows],
    ]


@app.callback(
    Output("house-detail", "children"),
    Input("house-district", "value"),
    Input("house-metric", "value"),
    Input("data-signature", "data"),
)
def update_house_detail(district, metric, signature):
    house = load_bundle(signature)["house"]
    if not district or house.empty:
        return [html.Div("DISTRICT DETAIL", className="detail-kicker"), html.H3("Select a district", className="detail-title"), html.P("Choose a district in the dropdown or click near the center of a district on the geographic map.", className="detail-copy")]
    rows = house.loc[house["District ID"].astype(str) == str(district)]
    if rows.empty:
        return html.Div("District not found in current HouseRaceDetail export.", className="empty-state")
    return house_detail_component(rows.iloc[0], metric or "rating")


@app.callback(
    Output("house-table-wrap", "children"),
    Input("house-state", "value"),
    Input("house-rating", "value"),
    Input("house-flags", "value"),
    Input("data-signature", "data"),
)
def update_house_table(state, rating, flags, signature):
    h = load_bundle(signature)["house"].copy()
    flags = flags or []
    if state and state != "ALL": h = h[h["State"] == state]
    if rating and rating != "ALL": h = h[h["Forecast Rating"] == rating]
    if "competitive" in flags: h = h[h["Competitive"].fillna(False).astype(bool)]
    if "flips" in flags: h = h[~h["Projected Flip"].fillna("Hold").astype(str).str.lower().eq("hold")]
    if "disagreement" in flags: h = h[h["Model vs Consensus Disagreement"].fillna(False).astype(bool)]
    if "D Win Probability" in h.columns:
        h = h.assign(_close=(pd.to_numeric(h["D Win Probability"], errors="coerce")-50).abs()).sort_values("_close").drop(columns="_close")
    preferred = [
        "District ID","State","Projected Winner","Forecast Rating","Projected Margin PP",
        "D Win Probability","R Win Probability","Projected Flip","All Source Consensus Rating",
        "PVI Raw","Incumbent Name","Democratic Candidate","Republican Candidate"
    ]
    cols = [c for c in preferred if c in h.columns]
    return table_component(h[cols], page_size=15, max_rows=435)


# ---------------------------- Senate explorer ----------------------------
@app.callback(
    Output({"type":"senate-tile","state":ALL}, "style"),
    Output({"type":"senate-status","state":ALL}, "children"),
    Output("senate-map-legend", "children"),
    Input("senate-map-metric", "value"),
    Input("senate-map-selected", "data"),
    Input("data-signature", "data"),
)
def style_senate_map(metric, selected, signature):
    smap = load_senate_map(signature)
    styles, statuses = [], []
    for _, r in smap.iterrows():
        bg = senate_color(r, metric or "forecast")
        dark_text = bg in {"#E5E7EB", "#F4D35E", "#A8D5EC", "#F2B5B9"} or "repeating-linear" in bg
        style = {
            "background": bg,
            "color": "#111827" if dark_text else "white",
        }
        if pd.notna(r.get("Grid Row")): style["gridRow"] = int(r["Grid Row"])
        if pd.notna(r.get("Grid Col")): style["gridColumn"] = int(r["Grid Col"])
        if safe_value(r.get("Tier")) == "Monitored": style["outline"] = "3px solid rgba(139,92,246,.58)"
        if safe_value(r.get("STATE")) == selected:
            style["boxShadow"] = "0 0 0 4px rgba(15,23,42,.28), 0 8px 20px rgba(15,23,42,.18)"
            style["transform"] = "translateY(-2px)"
        styles.append(style)
        tier = safe_value(r.get("Tier")); p = r.get("D Win Probability"); margin = r.get("Projected Margin")
        outcome = safe_value(r.get("Outcome")); rating = safe_value(r.get("Forecast Rating Key"), safe_value(r.get("Forecast Rating")))
        if tier == "None": status = "—"
        elif tier == "Safe" and metric in {"forecast", "probability", "ratings", "margin"}:
            party = "D" if " D" in f" {rating}" or "Democratic" in outcome else "R"
            status = f"SAFE {party}"
        elif metric == "probability" and pd.notna(p):
            party = "D" if float(p) >= 50 else "R"; status = f"{party} {max(float(p),100-float(p)):.0f}%"
        elif metric == "ratings": status = rating.replace(" D", "").replace(" R", "").upper()
        elif metric == "margin" and pd.notna(margin): status = party_margin(margin)
        elif metric == "flips":
            flip = safe_value(r.get("Flip"), ""); party = "D" if "Democratic" in outcome else "R"
            status = f"{flip or party} {'FLIP' if flip else 'HOLD'}"
        else:
            party = "D" if "Democratic" in outcome else "R" if "Republican" in outcome else "—"
            status = f"{party} {'FLIP' if safe_value(r.get('Flip'),'') else 'HOLD'}" if party != "—" else "—"
        statuses.append(status)
    labels = {
        "forecast": [("Republican winner", "#C1121F"), ("Democratic winner", "#0B5CAB"), ("Monitored outline", "#8B5CF6")],
        "probability": [("D numeric probability", "#1769AA"), ("Close D", "#A8D5EC"), ("Close R", "#F2B5B9"), ("R numeric probability", "#C1121F"), ("Safe D · categorical only", "#0B5CAB"), ("Safe R · categorical only", "#C1121F")],
        "ratings": [("Safe/Likely D", "#1769AA"), ("Toss-up", "#F4D35E"), ("Safe/Likely R", "#C1121F")],
        "margin": [("D numeric margin", "#0B5CAB"), ("Close D", "#C7E4F2"), ("Close R", "#F5C6CA"), ("R numeric margin", "#C1121F"), ("Safe D · categorical only", "#0B5CAB"), ("Safe R · categorical only", "#C1121F")],
        "flips": [("D hold", "#0B5CAB"), ("D flip · striped", "repeating-linear-gradient(45deg,#1769AA 0 4px,#D9ECF7 4px 8px)"), ("R flip · striped", "repeating-linear-gradient(45deg,#C1121F 0 4px,#F8D5D8 4px 8px)"), ("R hold", "#C1121F")],
    }
    legend = [html.Span([html.I(style={"background":c}), t]) for t,c in labels.get(metric, labels["forecast"])]
    return styles, statuses, legend


@app.callback(
    Output("senate-map-selected", "data"),
    Output("senate-state", "value"),
    Input({"type":"senate-tile","state":ALL}, "n_clicks"),
    State("senate-map-selected", "data"),
    State("data-signature", "data"),
    prevent_initial_call=True,
)
def store_senate_click(_clicks, current, signature):
    trigger = ctx.triggered_id
    if isinstance(trigger, dict) and trigger.get("type") == "senate-tile":
        state = trigger.get("state")
        monitored = set(load_bundle(signature)["senate"].get("STATE", pd.Series(dtype=str)).astype(str))
        return state, state if state in monitored else no_update
    return current or no_update, no_update


def senate_map_detail(row: pd.Series, metric: str):
    state = safe_value(row.get("STATE")); abbr = safe_value(row.get("ABBR")); tier = safe_value(row.get("Tier"))
    if tier == "None":
        return [html.B(f"{state} ({abbr})"), html.Br(), "No 2026 Senate election"]
    p = row.get("D Win Probability"); margin = row.get("Projected Margin")
    rating = safe_value(row.get("Forecast Rating")); outcome = safe_value(row.get("Outcome"))
    parts = [html.B(f"{state} ({abbr})"), html.Br()]
    dshare = row.get("Projected D 2P"); rshare = row.get("Projected R 2P")
    if tier == "Safe":
        parts.extend([
            html.B(outcome), html.Br(),
            html.Span(rating, className="race-rating"), html.Br(),
            html.B("No numerical official forecast"), html.Br(),
            html.Span(
                "Unmonitored race: no survey/state-model margin, vote share, or probability.",
                className="scenario-copy",
            ),
            html.Br(),
            html.Span(
                f"Scenario Lab proxy only · PVI {safe_value(row.get('PVI'))} · "
                f"previous Senate result {safe_value(row.get('Previous Election'))} · "
                f"50/50 blend {party_margin(row.get('Scenario Baseline Margin PP'))}. "
                "Not an official forecast.",
                className="scenario-copy",
            ),
        ])
        return parts
    if metric == "probability" and p is not None and pd.notna(p):
        parts.extend([html.Span(f"D win {float(p):.1f}%", className="dem"), " · ", html.Span(f"R win {100-float(p):.1f}%", className="rep")])
    elif metric == "ratings": parts.extend([html.B(f"Model rating: {rating}")])
    elif metric == "margin" and margin is not None and pd.notna(margin):
        parts.extend([html.B(f"Projected margin: {party_margin(margin)}"), html.Br()])
        if pd.notna(dshare) and pd.notna(rshare): parts.extend([html.Span(f"Democratic {float(dshare):.2f}%", className="dem"), " · ", html.Span(f"Republican {float(rshare):.2f}%", className="rep")])
    elif metric == "flips": parts.extend([html.B(outcome), html.Br(), rating, " · ", party_margin(margin)])
    else:
        parts.extend([html.B(outcome), html.Br(), rating, " · ", party_margin(margin)])
    return parts


@app.callback(
    Output("senate-map-selection", "children"),
    Input("senate-map-selected", "data"),
    Input("senate-map-metric", "value"),
    Input("data-signature", "data"),
)
def update_senate_map_selection(state, metric, signature):
    if not state:
        return "Click any state tile to inspect its 2026 Senate status. Purple outline = monitored state model."
    smap = load_senate_map(signature)
    rows = smap[smap["STATE"] == state]
    if rows.empty: return state
    return senate_map_detail(rows.iloc[0], metric)


def senate_detail_component(row: pd.Series, metric: str = "forecast"):
    state = safe_value(row.get("STATE")); rating = safe_value(row.get("Forecast Rating")); winner = safe_value(row.get("Projected Winner"))
    incumbent = safe_value(row.get("INCUMBENT")).upper()
    is_flip = winner in {"D", "R"} and incumbent in {"D", "R"} and winner != incumbent
    projected_outcome = (
        f"{'Democratic' if winner == 'D' else 'Republican'} {'Flip' if is_flip else 'Hold'}"
        if winner in {"D", "R"}
        else "No projected winner"
    )
    dprob = float(row.get("D Win Probability")) if pd.notna(row.get("D Win Probability")) else 50
    rprob = float(row.get("R Win Probability")) if pd.notna(row.get("R Win Probability")) else 50
    margin = float(row.get("Adjusted Margin 2P")) if pd.notna(row.get("Adjusted Margin 2P")) else 0
    info = [
        ("Incumbent", safe_value(row.get("INCUMBENT"))),
        ("Consensus rating", safe_value(row.get("Consensus Rating"))),
        ("Polling margin", f"{float(row.get('Poll Margin 2P')):+.2f} pp" if pd.notna(row.get('Poll Margin 2P')) else "—"),
        ("Polling-error correction", f"{float(row.get('Model Polling Error Correction PP')):+.2f} pp" if pd.notna(row.get('Model Polling Error Correction PP')) else "—"),
        ("Fundamentals margin", f"{float(row.get('Fundamentals Margin 2P')):+.2f} pp" if pd.notna(row.get('Fundamentals Margin 2P')) else "—"),
        ("Projected D 2P", f"{float(row.get('Projected D 2P')):.2f}%" if pd.notna(row.get('Projected D 2P')) else "—"),
        ("Projected R 2P", f"{float(row.get('Projected R 2P')):.2f}%" if pd.notna(row.get('Projected R 2P')) else "—"),
        ("Vulnerability", safe_value(row.get("Vulnerability Score"))),
        ("Forecast sigma", f"{float(row.get('Forecast Sigma PP')):.2f} pp" if pd.notna(row.get('Forecast Sigma PP')) else "—"),
        ("Historic MAE", f"{float(row.get('Historic MAE PP')):.2f} pp" if pd.notna(row.get('Historic MAE PP')) else "—"),
    ]
    if metric == "probability":
        hero = [
            html.Div([html.Div([html.Div("D WIN", className="detail-label"), html.Div(f"{dprob:.1f}%", className="detail-number dem")]), html.Div([html.Div("R WIN", className="detail-label"), html.Div(f"{rprob:.1f}%", className="detail-number rep")])], className="detail-pair"),
            html.Div([html.Div(style={"width":f"{dprob:.2f}%"},className="prob-dem"), html.Div(style={"width":f"{rprob:.2f}%"},className="prob-rep")], className="prob-track"),
        ]
    elif metric == "ratings":
        hero = [html.Div("MODEL RATING", className="detail-label"), html.Div(rating, className="detail-number")]
    elif metric == "margin":
        dshare = float(row.get("Projected D 2P")) if pd.notna(row.get("Projected D 2P")) else 50 + margin / 2
        rshare = float(row.get("Projected R 2P")) if pd.notna(row.get("Projected R 2P")) else 50 - margin / 2
        hero = [
            html.Div("PROJECTED MARGIN", className="detail-label"),
            html.Div(party_margin(margin), className=f"detail-number {'dem' if margin >= 0 else 'rep'}"),
            html.Div(f"D {dshare:.2f}% · R {rshare:.2f}% projected two-party vote", className="scenario-copy"),
        ]
    elif metric == "flips":
        hero = [html.Div("HOLD / FLIP", className="detail-label"), html.Div(projected_outcome, className="detail-number"), html.Div(f"{rating} · {party_margin(margin)}", className="scenario-copy")]
    else:
        hero = [html.Div("FORECAST", className="detail-label"), html.Div(projected_outcome, className="detail-number"), html.Div(f"{rating} · {party_margin(margin)}", className="scenario-copy")]
    return [
        html.Div("MONITORED RACE DETAIL", className="detail-kicker"), html.H3(state, className="detail-title"),
        html.Div(rating, className=f"race-rating {'dem-soft' if winner=='D' else 'rep-soft'}"),
        *hero,
        html.Hr(className="detail-rule"),
        *[
            html.Div([
                html.Div(k, className="detail-label"),
                html.Div(
                    v,
                    className=(
                        "detail-text dem" if k == "Projected D 2P"
                        else "detail-text rep" if k == "Projected R 2P"
                        else "detail-text"
                    ),
                ),
            ], className="detail-row")
            for k, v in info
        ],
    ]


@app.callback(
    Output("senate-detail", "children"),
    Input("senate-state", "value"),
    Input("senate-map-metric", "value"),
    Input("data-signature", "data"),
)
def update_senate_detail(state, metric, signature):
    senate = load_bundle(signature)["senate"]
    if senate.empty or not state:
        return html.Div("No monitored Senate race selected.", className="empty-state")
    rows = senate[senate["STATE"] == state]
    if rows.empty: return html.Div("State not present in SenateRaceDetail.", className="empty-state")
    return senate_detail_component(rows.iloc[0], metric or "forecast")


# ---------------------------- Simulation explorer ----------------------------
@app.callback(
    Output("simulation-scatter", "figure"),
    Input("sim-x", "value"), Input("sim-y", "value"), Input("sim-color", "value"), Input("data-signature", "data"),
)
def update_simulation(x, y, color, signature):
    sims = load_bundle(signature)["sheets"]["MonteCarloSample"]
    return simulation_scatter(sims, x, y, None if color == "NONE" else color)


# ---------------------------- Scenario Lab ----------------------------
@app.callback(
    Output({"type":"national-scenario-input", "name":ALL}, "drag_value"),
    Input({"type":"national-scenario-input", "name":ALL}, "drag_value"),
    State({"type":"national-scenario-input", "name":ALL}, "value"),
    State({"type":"national-scenario-input", "name":ALL}, "id"),
    prevent_initial_call=True,
)
def preview_scenario_battery_constraint(drag_values, committed_values, ids):
    """Move battery peers during a drag without running the statistical model."""
    trigger = ctx.triggered_id
    if not isinstance(trigger, dict) or not ids:
        return [no_update] * len(ids or [])
    changed_name = trigger.get("name")
    battery = next(
        (columns for columns in COMPOSITION_BATTERIES.values() if changed_name in columns),
        None,
    )
    if battery is None:
        return [no_update] * len(ids)

    current = {}
    for index, item in enumerate(ids):
        dragged = drag_values[index] if drag_values and index < len(drag_values) else None
        committed = committed_values[index] if committed_values and index < len(committed_values) else 0.0
        current[item["name"]] = float(committed if dragged is None else dragged)
    if sum(current[name] for name in battery) <= 100.0 + 1e-9:
        return [no_update] * len(ids)

    projected = normalize_composition_values(current, changed_name)
    return [
        float(projected[item["name"]]) if item["name"] in battery else no_update
        for item in ids
    ]


@app.callback(
    Output({"type":"national-scenario-input", "name":ALL}, "value"),
    Output("scenario-direct-overrides", "data"),
    Input("scenario-reset", "n_clicks"),
    Input({"type":"national-scenario-input", "name":ALL}, "value"),
    State({"type":"national-scenario-input", "name":ALL}, "id"),
    State("scenario-direct-overrides", "data"),
    prevent_initial_call=False,
)
def reconcile_or_reset_scenario_inputs(_clicks, values, ids, direct_store):
    """Commit one completed slider edit, then reconcile the fourteen units."""
    engine = load_scenario_engine(str(MODEL_PATH), MODEL_PATH.stat().st_mtime_ns)
    baseline = {spec.name: spec.baseline for spec in engine.input_specs}
    if not ids:
        return no_update, no_update
    trigger = ctx.triggered_id
    if trigger == "scenario-reset":
        return [baseline[item["name"]] for item in ids], {"values": {}, "order": []}

    current = {item["name"]: float(value) for item, value in zip(ids, values or [])}
    stored = dict(direct_store or {})
    requested = dict(stored.get("values", {})) if isinstance(stored.get("values", {}), dict) else {}
    order = list(stored.get("order", [])) if isinstance(stored.get("order", []), list) else []
    state = {"values": requested, "order": order}
    expected = engine.predict(state)["reconciled_values"]

    # Initial render may restore persisted values from a previous browser
    # session. Treat only genuine deviations from the baseline as interventions.
    if trigger is None:
        initial_requested = {
            name: value for name, value in current.items()
            if abs(value - baseline[name]) > 1e-8
        }
        if not initial_requested:
            if requested:
                return [baseline[item["name"]] for item in ids], {"values": {}, "order": []}
            return no_update, no_update
        requested = initial_requested
        order = list(initial_requested)
    elif isinstance(trigger, dict):
        # Values returned by this callback re-enter through the Slider inputs.
        # Ignore that echo; only a genuine deviation commits a new edit.
        if all(abs(current[name] - float(expected[name])) < 1e-7 for name in current):
            return no_update, no_update
        name = trigger.get("name")
        if name in baseline:
            value = current[name]
            if abs(value - baseline[name]) <= 1e-8:
                requested.pop(name, None)
                order = [item for item in order if item != name]
            else:
                requested[name] = value
                order = [item for item in order if item != name] + [name]

    state = {"values": requested, "order": order}
    result = engine.predict(state)
    reconciled = result["reconciled_values"]
    ordered = [float(reconciled[item["name"]]) for item in ids]
    return ordered, state


@app.callback(
    Output("scenario-national-summary", "children"),
    Output("scenario-national-graph", "figure"),
    Output("scenario-national-table", "children"),
    Output("scenario-changed-inputs", "children"),
    Output("scenario-house-graph", "figure"),
    Output("scenario-summary", "children"),
    Output({"type":"scenario-senate-tile","state":ALL}, "style"),
    Output({"type":"scenario-senate-status","state":ALL}, "children"),
    Output({"type":"scenario-senate-tooltip","state":ALL}, "children"),
    Output("scenario-senate-summary", "children"),
    Output("scenario-senate-race-table", "children"),
    Output("scenario-model-status", "children"),
    Output("scenario-battery-status", "children"),
    Input("scenario-direct-overrides", "data"),
    Input("data-signature", "data"),
)
def update_scenario(direct_overrides, signature):
    engine = load_scenario_engine(str(MODEL_PATH), MODEL_PATH.stat().st_mtime_ns)
    result = engine.predict(direct_overrides or {})
    baseline = engine.baseline
    current = result["headline"]
    current_smooth = result["smooth_headline"]
    base = baseline["headline"]
    baseline_smooth = baseline["smooth_headline"]
    b = load_bundle(signature)

    current_two_party_d = float(
        current["D Popular Vote (%)"]
        / (current["D Popular Vote (%)"] + current["R Popular Vote (%)"])
        * 100.0
    )
    baseline_two_party_d = float(
        base["D Popular Vote (%)"]
        / (base["D Popular Vote (%)"] + base["R Popular Vote (%)"])
        * 100.0
    )
    popular_share_swing = current_two_party_d - baseline_two_party_d
    popular_margin_swing = 2.0 * popular_share_swing

    # The reconciled popular-vote swing is the geographic pathway.
    # National House/Senate bucket responses remain a diagnostic only because
    # five cycles are not enough to justify letting an unstable residual reverse
    # hundreds of district/race anchors.
    base_house_data, base_house_summary = scenario_house_summary(b["house"], 0.0, 0.0)
    house_data, house_summary = scenario_house_summary(b["house"], popular_share_swing, 0.0)
    house_model_expected_delta = float(current_smooth["D House Expected"] - baseline_smooth["D House Expected"])
    house_geo_expected_delta = float(house_summary["Expected D seats"] - base_house_summary["Expected D seats"])
    house_bucket_diagnostic = house_model_expected_delta - house_geo_expected_delta

    senate_map = load_senate_map(signature)
    production_row = engine.production.iloc[0]
    fixed_non_up_d = int(round(float(production_row["DS before"] - production_row["DSS UP"])))
    base_senate_data, base_senate_summary = scenario_senate_summary(
        senate_map, b["senate"], 0.0, fixed_non_up_d, 0.0
    )
    senate_data, senate_summary = scenario_senate_summary(
        senate_map, b["senate"], popular_margin_swing, fixed_non_up_d, 0.0
    )
    senate_model_expected_delta = float(current_smooth["D Senate Expected"] - baseline_smooth["D Senate Expected"])
    senate_geo_expected_delta = float(senate_summary["Expected D seats"] - base_senate_summary["Expected D seats"])
    senate_bucket_diagnostic = senate_model_expected_delta - senate_geo_expected_delta

    # The Scenario headline must share the official baseline identity. House's
    # production headline is the expected-seat projection rounded to whole seats;
    # median-winner remains a separate diagnostic displayed below.
    house_projected_d = int(round(float(house_summary["Expected D seats"])))
    house_projected_r = 435 - house_projected_d
    base_house_projected_d = int(round(float(base_house_summary["Expected D seats"])))
    base_house_projected_r = 435 - base_house_projected_d
    scenario_headline = {
        **current,
        "D House Seats": house_projected_d,
        "R House Seats": house_projected_r,
        "D Senate Seats": senate_summary["D seats by race winner"],
        "R Senate Seats": senate_summary["R seats by race winner"],
    }
    baseline_headline = {
        **base,
        "D House Seats": base_house_projected_d,
        "R House Seats": base_house_projected_r,
        "D Senate Seats": base_senate_summary["D seats by race winner"],
        "R Senate Seats": base_senate_summary["R seats by race winner"],
    }

    changed = result["changed_inputs"]
    changed_count = int(len(changed))
    pop_components = result.get("popular_vote_components", {})
    premodel_info = result.get("premodel", {})
    house_d_gains = int(((house_data["Official Projected Winner"] == "R") & (house_data["Scenario Winner"] == "D")).sum())
    house_r_gains = int(((house_data["Official Projected Winner"] == "D") & (house_data["Scenario Winner"] == "R")).sum())
    senate_d_gains = int(((senate_data["Official Projected Winner"] == "R") & (senate_data["Scenario Winner"] == "D")).sum())
    senate_r_gains = int(((senate_data["Official Projected Winner"] == "D") & (senate_data["Scenario Winner"] == "R")).sum())
    national_cards = [
        html.Div([html.Div("D popular vote · scenario", className="mini-label"), html.Div(f"{current['D Popular Vote (%)']:.2f}%", className="mini-value dem"), html.Div(f"D–R swing {popular_margin_swing:+.2f} pp", className="mini-note")], className="mini-card"),
        html.Div([html.Div("R popular vote · scenario", className="mini-label"), html.Div(f"{current['R Popular Vote (%)']:.2f}%", className="mini-value rep"), html.Div(f"Other / unallocated {pop_components.get('Other / unallocated (%)', 0.0):.2f}%", className="mini-note")], className="mini-card"),
        html.Div([html.Div("House projected seats · expected-rounded", className="mini-label"), html.Div([html.Span(f"D {scenario_headline['D House Seats']:.0f}", className="dem"), " – ", html.Span(f"R {scenario_headline['R House Seats']:.0f}", className="rep")], className="mini-value"), html.Div(f"Vs official forecast: D gains {house_d_gains} · R gains {house_r_gains}", className="mini-note")], className="mini-card"),
        html.Div([html.Div("Senate race-winner seats", className="mini-label"), html.Div([html.Span(f"D {scenario_headline['D Senate Seats']:.0f}", className="dem"), " – ", html.Span(f"R {scenario_headline['R Senate Seats']:.0f}", className="rep")], className="mini-value"), html.Div(f"Vs official forecast: D gains {senate_d_gains} · R gains {senate_r_gains}", className="mini-note")], className="mini-card"),
    ]

    comparison_rows = []
    for target, scenario_value in result["targets"].items():
        baseline_value = baseline["targets"][target]
        scale = 100.0 if target in {"DPP", "RPP"} else 1.0
        comparison_rows.append({
            "Target": f"{target} (%)" if scale == 100.0 else target,
            "Baseline": baseline_value * scale,
            "Scenario": scenario_value * scale,
            "Change": (scenario_value - baseline_value) * scale,
        })
    comparison = pd.DataFrame(comparison_rows)
    changed_component = (
        table_component(changed, page_size=12, max_rows=31, filter_action="none", sort_action="none", column_selectable=False, compact=True)
        if not changed.empty else html.Div("No inputs differ from the official 2026 row.", className="empty-state")
    )

    house_cards = [
        html.Div([html.Div("D two-party vote change",className="mini-label"),html.Div(f"{popular_share_swing:+.2f} pp",className="mini-value")],className="mini-card"),
        html.Div([html.Div("Median-winner seats",className="mini-label"),html.Div([html.Span(f"D {house_summary['D seats by median winner']:.0f}",className="dem"), " · ", html.Span(f"R {house_summary['R seats by median winner']:.0f}",className="rep")],className="mini-value")],className="mini-card"),
        html.Div([html.Div("Expected D seats",className="mini-label"),html.Div(f"{house_summary['Expected D seats']:.1f}",className="mini-value dem")],className="mini-card"),
        html.Div([html.Div("Expected R seats",className="mini-label"),html.Div(f"{house_summary['Expected R seats']:.1f}",className="mini-value rep")],className="mini-card"),
    ]
    senate_cards = [
        html.Div([html.Div("D–R two-party margin change",className="mini-label"),html.Div(f"{popular_margin_swing:+.2f} pp",className="mini-value")],className="mini-card"),
        html.Div([html.Div("Race-winner seats",className="mini-label"),html.Div([html.Span(f"D {senate_summary['D seats by race winner']:.0f}",className="dem"), " · ", html.Span(f"R {senate_summary['R seats by race winner']:.0f}",className="rep")],className="mini-value")],className="mini-card"),
        html.Div([html.Div("Expected D seats",className="mini-label"),html.Div(f"{senate_summary['Expected D seats']:.1f}",className="mini-value dem")],className="mini-card"),
        html.Div([html.Div("Expected R seats",className="mini-label"),html.Div(f"{senate_summary['Expected R seats']:.1f}",className="mini-value rep"),html.Div("24 Safe races use scenario-only structural proxies",className="mini-note")],className="mini-card"),
    ]

    # Update the shared 50-state Senate tile renderer without replacing the component.
    scenario_lookup = senate_data.set_index("STATE") if not senate_data.empty else pd.DataFrame()
    senate_styles, senate_statuses, senate_tooltips = [], [], []
    for _, row in senate_map.iterrows():
        state = safe_value(row.get("STATE")); tier = safe_value(row.get("Tier"))
        style = {}
        if pd.notna(row.get("Grid Row")): style["gridRow"] = int(row["Grid Row"])
        if pd.notna(row.get("Grid Col")): style["gridColumn"] = int(row["Grid Col"])
        if tier == "None" or scenario_lookup.empty or state not in scenario_lookup.index:
            style.update({"background":"#E5E7EB", "color":"#64748B"})
            status = "—"
            tooltip = [
                html.B(state, className="state-tooltip-title"),
                html.Span("No 2026 Senate election", className="state-tooltip-line"),
            ]
        else:
            sr = scenario_lookup.loc[state]
            if isinstance(sr, pd.DataFrame): sr = sr.iloc[0]
            dprob = float(sr["Scenario D Win Probability"]); winner = safe_value(sr.get("Scenario Winner"))
            rprob = float(sr.get("Scenario R Win Probability", 100.0 - dprob))
            margin = float(sr["Scenario Margin PP"])
            dshare = float(sr.get("Scenario D 2P", 50.0 + margin / 2.0))
            rshare = float(sr.get("Scenario R 2P", 50.0 - margin / 2.0))
            style.update({"background": projected_margin_color(margin), "color":"#111827" if abs(margin) < 3 else "white"})
            if tier == "Monitored": style["outline"] = "3px solid rgba(139,92,246,.58)"
            margin_label = f"D+{margin:.1f}" if margin >= 0 else f"R+{abs(margin):.1f}"
            status = f"{winner} {dshare if winner == 'D' else rshare:.0f}% · {margin_label}"
            scenario_change = safe_value(sr.get("Scenario Change vs Official"), "No change")
            outcome = safe_value(sr.get("Scenario Outcome vs Incumbent"), "—")
            tooltip = [
                html.B(state, className="state-tooltip-title"),
                html.Div([
                    html.Span(f"D {dshare:.1f}%", className="dem"),
                    html.Span(" · "),
                    html.Span(f"R {rshare:.1f}%", className="rep"),
                ], className="state-tooltip-vote"),
                html.Span(f"{winner} wins · {margin_label} · {outcome}", className="state-tooltip-line"),
                html.Span(f"Win probability D {dprob:.1f}% · R {rprob:.1f}%", className="state-tooltip-line"),
                html.Span(f"Official rating: {safe_value(sr.get('Official Forecast Rating'))}", className="state-tooltip-line"),
                html.Span(
                    "No change from official forecast" if scenario_change == "No change" else f"Scenario change: {scenario_change}",
                    className="state-tooltip-change" if scenario_change != "No change" else "state-tooltip-line",
                ),
            ]
            if tier == "Safe":
                tooltip.append(html.Span("Scenario-only structural estimate", className="state-tooltip-caveat"))
        senate_styles.append(style); senate_statuses.append(status); senate_tooltips.append(tooltip)

    # A readable 35-race audit accompanies the map so probability is never the
    # only visible scenario number.  For Safe races every numeric value remains
    # explicitly scenario-only; the official rating itself stays categorical.
    race_table = senate_data.copy()
    if not race_table.empty:
        race_table["Scenario margin"] = race_table["Scenario Margin PP"].map(
            lambda m: f"D+{float(m):.1f}" if float(m) >= 0 else f"R+{abs(float(m)):.1f}"
        )
        race_table = race_table.rename(columns={
            "STATE": "State",
            "Tier": "Official tier",
            "Official Forecast Rating": "Official rating",
            "Scenario Winner": "Scenario winner",
            "Scenario D Win Probability": "D win (%)",
            "Scenario R Win Probability": "R win (%)",
            "Scenario D 2P": "Expected D 2P vote (%)",
            "Scenario R 2P": "Expected R 2P vote (%)",
            "Scenario Outcome vs Incumbent": "Hold / flip",
            "Scenario Change vs Official": "Change vs official",
            "Scenario Baseline Type": "Scenario baseline",
        })
        race_columns = [
            "State", "Official tier", "Official rating", "Scenario winner",
            "D win (%)", "R win (%)", "Scenario margin",
            "Expected D 2P vote (%)", "Expected R 2P vote (%)",
            "Hold / flip", "Change vs official", "Scenario baseline",
        ]
        race_table = race_table[[c for c in race_columns if c in race_table.columns]].copy()
        for col in ["D win (%)", "R win (%)", "Expected D 2P vote (%)", "Expected R 2P vote (%)"]:
            if col in race_table.columns:
                race_table[col] = pd.to_numeric(race_table[col], errors="coerce").round(1)
        if "D win (%)" in race_table.columns:
            race_table["_distance"] = (race_table["D win (%)"] - 50.0).abs()
            race_table = race_table.sort_values(["_distance", "State"]).drop(columns="_distance")
        senate_race_table_component = html.Div([
            html.Div(
                "All 35 scheduled races. Monitored states use the official state-model anchor; Safe-state numbers below are Scenario-Lab-only structural estimates, never official numeric forecasts.",
                className="scenario-copy",
            ),
            table_component(
                race_table, page_size=35, max_rows=35,
                filter_action="none", sort_action="native", column_selectable=False, compact=True,
            ),
        ])
    else:
        senate_race_table_component = html.Div("No Senate scenario rows available.", className="empty-state")

    outside = result["outside_support"]
    if outside.empty:
        baseline_outside_count = 0
        scenario_outside_count = 0
    else:
        changed_mask = outside.get("Changed from baseline", pd.Series(False, index=outside.index)).astype(bool)
        baseline_mask = outside.get("Baseline already outside support", pd.Series(False, index=outside.index)).astype(bool)
        scenario_outside_count = int(changed_mask.sum())
        baseline_outside_count = int((baseline_mask & ~changed_mask).sum())
    if scenario_outside_count:
        support_text = (
            f"Scenario extrapolation: {scenario_outside_count} reconciled control(s) outside the five-cycle range"
            + (f" · 2026 baseline already outside on {baseline_outside_count}" if baseline_outside_count else "")
        )
    elif baseline_outside_count:
        support_text = (
            f"Scenario adds no new historical-range extrapolation · 2026 baseline itself is outside the five-cycle range on {baseline_outside_count} control(s)"
        )
    else:
        support_text = "Within the five-cycle historical support"
    direct_count = sum(1 for row in changed.to_dict("records") if row.get("Source") == "Direct intervention") if not changed.empty else 0
    hard_count = sum(1 for row in changed.to_dict("records") if row.get("Source") == "Hard battery constraint") if not changed.empty else 0
    propagated_count = max(0, changed_count - direct_count - hard_count)
    coherence = result.get("coherence", {})
    caps = result.get("propagation_caps", pd.DataFrame())
    d55_threshold = None
    d55_sheet = b.get("sheets", {}).get("ScenarioSenateRegression", pd.DataFrame())
    if isinstance(d55_sheet, pd.DataFrame) and not d55_sheet.empty and {"Check","Value"}.issubset(d55_sheet.columns):
        d55_row = d55_sheet.loc[d55_sheet["Check"].astype(str).eq("Uniform D-R margin swing required for D55")]
        if not d55_row.empty:
            try: d55_threshold = float(d55_row.iloc[0]["Value"])
            except Exception: d55_threshold = None
    model_status = [
        html.Span("v26 · fourteen-unit premodel · official snapshot preserved", className="method-chip"),
        html.Span(f"Counterfactual displacement {coherence.get('Mahalanobis distance', 0.0):.2f} · {coherence.get('Coherence status','')}", className="method-chip"),
        html.Span(f"Propagation caps {len(caps)} control(s)", className="method-chip warning" if len(caps) else "method-chip ok"),
        html.Span(f"Direct {direct_count} · hard-adjusted {hard_count} · propagated {propagated_count}", className="method-chip"),
        html.Span(f"Joint feedback {result.get('feedback_iterations', 0)} iterations", className="method-chip"),
        html.Span(f"Ledoit–Wolf shrinkage {premodel_info.get('relationship_shrinkage', 0):.3f}", className="method-chip"),
        html.Span(f"Maximum equation leverage {premodel_info.get('maximum_row_leverage', 0):.2f}", className="method-chip"),
        html.Span(f"House bucket diagnostic {house_bucket_diagnostic:+.2f} seats · not applied", className="method-chip"),
        html.Span(f"Senate bucket diagnostic {senate_bucket_diagnostic:+.2f} seats · not applied", className="method-chip"),
        html.Span("Senate Safe: 50% PVI + 50% prior-seat result · Scenario Lab only", className="method-chip"),
        html.Span((f"Senate D55 regression threshold: +{d55_threshold:.2f} pp uniform D-R swing" if d55_threshold is not None else "Senate D55 regression threshold unavailable"), className="method-chip"),
        html.Span("Associational stress test · not causal", className="method-chip"),
        html.Span(support_text, className="method-chip warning" if scenario_outside_count else "method-chip ok"),
    ]
    battery_component = table_component(
        result["battery_status"].round(2), page_size=12, max_rows=20,
        filter_action="none", sort_action="none", column_selectable=False, compact=True,
    )
    return (
        national_cards,
        national_scenario_figure(baseline_headline, scenario_headline),
        table_component(comparison, page_size=15, max_rows=100),
        changed_component,
        house_map_patch(house_data, "margin"), house_cards,
        senate_styles, senate_statuses, senate_tooltips, senate_cards,
        senate_race_table_component,
        model_status,
        battery_component,
    )


if __name__ == "__main__":
    # Set DASH_PORT=8051 (or any other free port) when another local app uses 8050.
    port = int(os.environ.get("DASH_PORT", "8050"))
    debug = os.environ.get("DASH_DEBUG", "0").strip().lower() in {"1", "true", "yes"}
    app.run(debug=debug, port=port)
