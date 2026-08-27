from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

import pandas as pd
from dash import dash_table, dcc, html

from core import MODEL_PATH, load_bundle, load_senate_map, safe_value
from figures import (
    PLOTLY_CONFIG,
    RATING_COLORS,
    canonical_rating,
    control_probability_figure,
    house_map_figure,
    model_quality_figure,
    popular_vote_figure,
    senate_color,
    senate_race_figure,
    scenario_house_summary,
    scenario_senate_summary,
    seats_histogram,
    time_machine_house_figure,
    validation_scatter,
)
from scenario_engine import (
    INPUT_GROUPS,
    INTERVENTION_UNITS,
    load_scenario_engine,
)

DEM = "#0B5CAB"
REP = "#C1121F"
PURPLE = "#8B5CF6"

RATING_ORDER = ["Safe D", "Likely D", "Lean D", "Tilt D", "Toss-Up", "Tilt R", "Lean R", "Likely R", "Safe R"]

PERSISTENCE = {
    "persistence": True,
    "persistence_type": "session",
}


def fmt_num(v: Any, digits: int = 1, suffix: str = "") -> str:
    try:
        return f"{float(v):,.{digits}f}{suffix}"
    except (TypeError, ValueError):
        return safe_value(v)


def metric_card(label: str, value: str, note: str = "", accent: str = "purple"):
    return html.Div([
        html.Div(label, className="card-label"),
        html.Div(value, className=f"big {accent}"),
        html.Div(note, className="note") if note else None,
    ], className=f"card card-{accent}")


def section_header(kicker: str, title: str, copy: Optional[str] = None):
    return html.Div([
        html.Div([html.Div(kicker, className="section-kicker"), html.H2(title, className="section-title")]),
        html.Div(copy, className="section-copy") if copy else None,
    ], className="section-heading")


def clean_records(df: pd.DataFrame, max_rows: int = 500) -> list[dict[str, Any]]:
    if df.empty:
        return []
    out = df.head(max_rows).copy()
    out = out.where(pd.notna(out), None)
    for c in out.columns:
        if pd.api.types.is_datetime64_any_dtype(out[c]):
            out[c] = out[c].astype(str)
    return out.to_dict("records")


def table_component(
    df: pd.DataFrame,
    page_size: int = 12,
    max_rows: int = 1000,
    table_id: Optional[str] = None,
    *,
    filter_action: str = "native",
    sort_action: str = "native",
    column_selectable: Any = "single",
    compact: bool = False,
):
    if df.empty:
        return html.Div("No exported rows available for this section.", className="empty-state")
    cols = []
    for c in df.columns:
        numeric = pd.api.types.is_numeric_dtype(df[c])
        cols.append({"name": str(c), "id": str(c), "type": "numeric" if numeric else "text"})
    padding = "6px" if compact else "9px"
    font_size = "10px" if compact else "11px"
    table_kwargs = dict(
        columns=cols,
        data=clean_records(df, max_rows=max_rows),
        page_size=page_size,
        sort_action=sort_action,
        filter_action=filter_action,
        column_selectable=column_selectable,
        style_table={"overflowX": "auto", "maxWidth": "100%"},
        style_header={"backgroundColor": "#F8FAFC", "fontWeight": "850", "border": "1px solid #E2E8F0", "whiteSpace":"normal"},
        style_cell={"fontFamily": "Inter, sans-serif", "fontSize": font_size, "padding": padding, "border": "1px solid #EEF2F7", "textAlign": "left", "minWidth":"80px" if compact else "90px", "maxWidth":"260px", "whiteSpace":"normal"},
        style_data_conditional=[
            {"if": {"filter_query": "{Projected Winner} = D"}, "color": DEM},
            {"if": {"filter_query": "{Projected Winner} = R"}, "color": REP},
        ] if "Projected Winner" in df.columns else [],
    )
    if table_id is not None:
        table_kwargs["id"] = table_id
    return dash_table.DataTable(**table_kwargs)


def balance_card(final_projection: pd.DataFrame, chamber: str):
    if final_projection.empty or "Chamber" not in final_projection.columns:
        return html.Div(className="power-card")
    rows = final_projection.loc[final_projection["Chamber"].astype(str).str.lower() == chamber.lower()]
    if rows.empty:
        return html.Div(className="power-card")
    r = rows.iloc[0]
    dseats = int(float(r["Democratic Seats"]))
    rseats = int(float(r["Republican Seats"]))
    total = max(dseats + rseats, 1)
    control = safe_value(r.get("Projected Control"))
    return html.Div([
        html.Div([
            html.Div(f"{chamber} balance", className="power-title"),
            html.Div([html.Span(className=f"control-dot {'dem-bg' if control == 'Democratic' else 'rep-bg'}"), f"{control} control"], className="control-badge"),
        ], className="power-top"),
        html.Div([
            html.Div([html.Div(str(dseats), className="balance-number dem"), html.Div("Democratic", className="balance-caption")]),
            html.Div([html.Div(str(rseats), className="balance-number rep"), html.Div("Republican", className="balance-caption")]),
        ], className="balance-numbers"),
        html.Div([
            html.Div(style={"width": f"{100*dseats/total:.3f}%"}, className="balance-dem"),
            html.Div(style={"width": f"{100*rseats/total:.3f}%"}, className="balance-rep"),
            html.Div(className="balance-mid"),
        ], className="balance-track"),
        html.Div([html.Span(f"D {dseats}"), html.Span(f"Majority: {'218' if chamber == 'House' else '51'}"), html.Span(f"R {rseats}")], className="balance-foot"),
    ], className="power-card")


def overview_view(signature: str):
    b = load_bundle(signature); s = b["sheets"]; d = b["dashboard"]
    sims = s["MonteCarloSample"]
    final = s["FinalProjection"]
    house_control = safe_value(d.get("House Control"))
    senate_control = safe_value(d.get("Senate Control"))
    return html.Div([
        html.Section([
            section_header("Forecast snapshot", "The national picture", "Live Dash presentation of the notebook's audited outputs. The Dash layer never rewrites Model.xlsx or the notebook."),
            html.Div([
                metric_card("Democratic popular vote", safe_value(d.get("Democratic Popular Vote")), "National projection", "dem"),
                metric_card("Republican popular vote", safe_value(d.get("Republican Popular Vote")), "National projection", "rep"),
                metric_card("House", f"D {safe_value(d.get('Democratic House Seats'))} – R {safe_value(d.get('Republican House Seats'))}", f"{house_control} control", "dem" if house_control == "Democratic" else "rep"),
                metric_card("Senate", f"D {safe_value(d.get('Democratic Senate Seats'))} – R {safe_value(d.get('Republican Senate Seats'))}", f"{senate_control} control", "dem" if senate_control == "Democratic" else "rep"),
            ], className="hero"),
        ], className="section"),
        html.Section([
            section_header("Control", "Balance of power"),
            html.Div([balance_card(final, "House"), balance_card(final, "Senate")], className="power-grid"),
        ], className="section"),
        html.Section([
            section_header("Uncertainty", "Probability & simulation", f"Audited run: {safe_value(d.get('Monte Carlo Simulations'))} simulations. Interactive cross-variable charts use the stored MonteCarloSample."),
            html.Div([
                html.Div(dcc.Graph(figure=control_probability_figure(s["ControlProbability"]), config=PLOTLY_CONFIG), className="panel"),
                html.Div(dcc.Graph(figure=popular_vote_figure(s["PopularVote"]), config=PLOTLY_CONFIG), className="panel"),
            ], className="two"),
            html.Div([
                html.Div(dcc.Graph(figure=seats_histogram(sims, "House"), config=PLOTLY_CONFIG), className="panel"),
                html.Div(dcc.Graph(figure=seats_histogram(sims, "Senate"), config=PLOTLY_CONFIG), className="panel"),
            ], className="two"),
        ], className="section"),
        html.Section([
            section_header("Audit snapshot", "Final uncertainty", "The same final uncertainty export that feeds the static HTML report."),
            html.Div(table_component(s["FinalUncertainty"], page_size=18, max_rows=100), className="panel"),
        ], className="section"),
    ])


def _rating_counts(values: pd.Series) -> dict[str, int]:
    counts = {rating: 0 for rating in RATING_ORDER}
    for value in values.dropna().astype(str):
        rating = canonical_rating(value)
        if rating in counts:
            counts[rating] += 1
    return counts


def _distribution_row(label: str, counts: dict[str, int]):
    total = max(1, sum(counts.values()))
    segments = []
    legend = []
    for rating in RATING_ORDER:
        count = int(counts.get(rating, 0))
        if not count:
            continue
        color = RATING_COLORS[rating]
        segments.append(html.Div(
            str(count),
            className="control-distribution-segment",
            style={"width": f"{100.0 * count / total:.5f}%", "background": color},
            title=f"{rating}: {count}",
        ))
        legend.append(html.Span([
            html.I(style={"background": color}),
            f"{rating} {count}",
        ]))
    return html.Div([
        html.Div(label, className="control-distribution-label"),
        html.Div(segments, className="control-distribution-track"),
        html.Div(legend, className="control-distribution-legend"),
    ], className="control-distribution-row")


def chamber_control_hero(bundle: dict[str, Any], chamber: str):
    dashboard = bundle["dashboard"]
    chamber_key = chamber.title()
    controller = safe_value(dashboard.get(f"{chamber_key} Control"))
    control_party = "Democratic" if controller == "Democratic" else "Republican"
    probability = float(dashboard.get(f"{chamber_key} {control_party} Control Probability", 0.0))
    dem_seats = int(float(dashboard.get(f"Democratic {chamber_key} Seats", 0)))
    rep_seats = int(float(dashboard.get(f"Republican {chamber_key} Seats", 0)))
    party_class = "dem" if control_party == "Democratic" else "rep"

    if chamber_key == "House":
        house = bundle["house"]
        rows = [
            _distribution_row("Model forecast", _rating_counts(house.get("Forecast Rating", pd.Series(dtype=str)))),
            _distribution_row("Source consensus", _rating_counts(house.get("All Source Consensus Rating", pd.Series(dtype=str)))),
        ]
        subtitle = f"Simulation median D {dem_seats} · R {rep_seats} · 435 districts"
    else:
        senate_map = load_senate_map(bundle["signature"])
        scheduled = senate_map.loc[senate_map["Tier"].ne("None")]
        rows = [_distribution_row(
            "2026 Senate races",
            _rating_counts(scheduled.get("Forecast Rating Key", pd.Series(dtype=str))),
        )]
        subtitle = f"Simulation median D {dem_seats} · R {rep_seats} · all 35 scheduled elections"

    return html.Div([
        html.Div(f"Probabilistic {chamber_key} forecast", className="control-hero-kicker"),
        html.Div([
            html.Span(f"{control_party}s ", className=party_class),
            "have a ",
            html.Span(f"{probability:.1f}% chance", className=party_class),
            f" of controlling the {chamber_key}.",
        ], className="control-hero-title"),
        html.Div(subtitle, className="control-hero-subtitle"),
        html.Div(rows, className="control-distribution-grid"),
    ], className=f"control-hero control-hero-{party_class}")


def house_view(signature: str):
    b = load_bundle(signature); h = b["house"]
    states = sorted(h["State"].dropna().astype(str).unique()) if not h.empty else []
    ratings = [r for r in ["Safe D","Likely D","Lean D","Tilt D","Toss-Up","Tilt R","Lean R","Likely R","Safe R"] if r in set(h.get("Forecast Rating", []))]
    return html.Div([
        html.Section([
            section_header("435 districts", "House forecast explorer", "Geographic explorer uses the same standard composite Albers district paths packaged with the notebook. Change the map metric, filter races, and open district-level diagnostics."),
            chamber_control_hero(b, "House"),
            html.Div([
                html.Div([html.Label("State", className="filter-label"), dcc.Dropdown(id="house-state", options=[{"label":"All states","value":"ALL"}]+[{"label":x,"value":x} for x in states], value="ALL", clearable=False, **PERSISTENCE)], className="filter-block"),
                html.Div([html.Label("Forecast rating", className="filter-label"), dcc.Dropdown(id="house-rating", options=[{"label":"All ratings","value":"ALL"}]+[{"label":x,"value":x} for x in ratings], value="ALL", clearable=False, **PERSISTENCE)], className="filter-block"),
                html.Div([html.Label("Map metric", className="filter-label"), dcc.Dropdown(id="house-metric", options=[
                    {"label":"Projected two-party vote","value":"margin"}, {"label":"Win probability","value":"probability"},
                    {"label":"Forecast rating","value":"rating"}, {"label":"All-source consensus","value":"consensus"},
                    {"label":"Holds & flips","value":"flips"}], value="margin", clearable=False, **PERSISTENCE)], className="filter-block"),
                html.Div([html.Label("Race set", className="filter-label"), dcc.Checklist(id="house-flags", options=[
                    {"label":" Competitive only","value":"competitive"}, {"label":" Projected flips only","value":"flips"},
                    {"label":" Model/consensus disagreement","value":"disagreement"}], value=[], className="checklist", **PERSISTENCE)], className="filter-block"),
                html.Div([html.Label("District", className="filter-label"), dcc.Dropdown(id="house-district", options=[{"label":safe_value(r.get("District Label")),"value":safe_value(r.get("District ID"))} for _,r in h.iterrows()], placeholder="Choose or click map", **PERSISTENCE)], className="filter-block filter-wide"),
            ], className="filter-grid house-filter-grid"),
            html.Div(id="house-map-legend", className="map-legend"),
            html.Div([
                html.Div(dcc.Loading(dcc.Graph(id="house-map", config=PLOTLY_CONFIG), type="circle"), className="panel map-panel"),
                html.Div(id="house-detail", className="detail-card"),
            ], className="house-grid"),
            html.Div([html.Div("Filtered district table", className="panel-title"), html.Div(id="house-table-wrap")], className="panel"),
        ], className="section"),
    ])


def _senate_tile(row: pd.Series):
    state = safe_value(row.get("STATE")); abbr = safe_value(row.get("ABBR")); tier = safe_value(row.get("Tier"))
    status = "—" if tier == "None" else "WATCH" if tier == "Monitored" else "SAFE"
    style = {}
    if pd.notna(row.get("Grid Row")): style["gridRow"] = int(row["Grid Row"])
    if pd.notna(row.get("Grid Col")): style["gridColumn"] = int(row["Grid Col"])
    return html.Button([
        html.Span(abbr, className="state-abbr"),
        html.Span(status, id={"type":"senate-status", "state":state}, className="state-status")
    ], id={"type":"senate-tile", "state":state}, n_clicks=0, className="state-tile", style=style, title=state)


def _scenario_senate_tile(row: pd.Series, baseline_row: Optional[pd.Series] = None):
    state = safe_value(row.get("STATE")); abbr = safe_value(row.get("ABBR")); tier = safe_value(row.get("Tier"))
    style = {}
    if pd.notna(row.get("Grid Row")): style["gridRow"] = int(row["Grid Row"])
    if pd.notna(row.get("Grid Col")): style["gridColumn"] = int(row["Grid Col"])
    if tier == "None":
        style.update({"background": "#E5E7EB", "color": "#64748B"})
        status = "—"
        title = f"{state} · No 2026 Senate election"
    else:
        scenario_winner = safe_value(baseline_row.get("Scenario Winner")) if baseline_row is not None else ("D" if "Democratic" in safe_value(row.get("Outcome")) else "R")
        style.update({"background": DEM if scenario_winner == "D" else REP, "color": "white"})
        if tier == "Monitored":
            style["outline"] = "3px solid rgba(139,92,246,.58)"
        status = f"{scenario_winner} SCEN"
        if baseline_row is not None:
            title = (
                f"{state} · Scenario D win {float(baseline_row['Scenario D Win Probability']):.1f}% · "
                f"Scenario margin {float(baseline_row['Scenario Margin PP']):+.1f} pp · "
                f"Official rating {safe_value(baseline_row.get('Official Forecast Rating'))} · "
                f"Baseline {safe_value(baseline_row.get('Scenario Baseline Type'))}"
            )
        else:
            title = state
    return html.Button([
        html.Span(abbr, className="state-abbr"),
        html.Span(status, id={"type":"scenario-senate-status", "state":state}, className="state-status"),
        html.Span(
            title,
            id={"type":"scenario-senate-tooltip", "state":state},
            className="state-rich-tooltip",
        ),
    ], id={"type":"scenario-senate-tile", "state":state}, n_clicks=0, className="state-tile", style=style)


def senate_view(signature: str):
    b = load_bundle(signature); s = b["sheets"]; senate = b["senate"]
    smap = load_senate_map(signature)
    states = senate.sort_values("D Win Probability", key=lambda x:(x-50).abs())["STATE"].astype(str).tolist() if not senate.empty else []
    return html.Div([
        html.Section([
            section_header("Senate battlefield", "The Senate, race by race", "All scheduled states are shown. The 11 monitored races expose state-model probabilities, margins, and vote shares. The 24 unmonitored Safe races retain only a categorical official rating; their numeric views are intentionally blank."),
            chamber_control_hero(b, "Senate"),
            html.Div([
                html.Div([html.Label("Senate map view", className="filter-label"), dcc.Dropdown(id="senate-map-metric", options=[
                    {"label":"Forecast","value":"forecast"}, {"label":"Win probability","value":"probability"},
                    {"label":"Ratings","value":"ratings"}, {"label":"Projected margin","value":"margin"},
                    {"label":"Holds & flips","value":"flips"}], value="forecast", clearable=False, **PERSISTENCE)], className="filter-block"),
                html.Div([html.Label("Monitored race", className="filter-label"), dcc.Dropdown(id="senate-state", options=[{"label":x,"value":x} for x in states], value=states[0] if states else None, clearable=False, **PERSISTENCE)], className="filter-block filter-wide"),
            ], className="filter-grid senate-filter-grid"),
            dcc.Store(id="senate-map-selected", data=None, storage_type="session"),
            html.Div([
                html.Div([
                    html.Div("All 35 regular and special elections", className="panel-title"),
                    html.Div(id="senate-map-legend", className="map-legend"),
                    html.Div([_senate_tile(r) for _,r in smap.iterrows()], id="senate-map-grid", className="state-map-grid"),
                    html.Div(id="senate-map-selection", className="map-selection"),
                    html.P("For transparency, Safe-state detail shows Cook PVI and the previous Senate result used only by Scenario Lab. Those inputs do not create an official forecast margin or probability.", className="scenario-copy"),
                ], className="panel senate-map-panel"),
                html.Div(id="senate-detail", className="detail-card"),
            ], className="senate-map-layout"),
            html.Div([
                html.Div(dcc.Graph(figure=senate_race_figure(senate), config=PLOTLY_CONFIG), className="panel"),
                html.Div([html.Div("Competitive / monitored race table", className="panel-title"), table_component(senate, page_size=11, max_rows=100)], className="panel"),
            ], className="two senate-bottom"),
        ], className="section"),
    ])


def probability_view(signature: str):
    s = load_bundle(signature)["sheets"]
    return html.Div([
        html.Section([
            section_header("Control odds", "Probability", "Control probabilities, close-race risk, chamber margins, and final uncertainty exports."),
            html.Div([
                html.Div(dcc.Graph(figure=control_probability_figure(s["ControlProbability"]), config=PLOTLY_CONFIG), className="panel"),
                html.Div([html.Div("Close-race risk", className="panel-title"), table_component(s["CloseRaceRisk"], page_size=10)], className="panel"),
            ], className="two"),
            html.Div([
                html.Div([html.Div("Prediction intervals", className="panel-title"), table_component(s["PredictionIntervals"], page_size=10)], className="panel"),
                html.Div([html.Div("Margin summary", className="panel-title"), table_component(s["MarginSummary"], page_size=8)], className="panel"),
            ], className="two"),
            html.Div([html.Div("Final uncertainty snapshot", className="panel-title"), table_component(s["FinalUncertainty"], page_size=18)], className="panel"),
        ], className="section"),
    ])


def simulation_view(signature: str):
    s = load_bundle(signature)["sheets"]; sims = s["MonteCarloSample"]
    numeric = sims.select_dtypes("number").columns.tolist() if not sims.empty else []
    categorical = [c for c in sims.columns if c not in numeric] if not sims.empty else []
    x0 = "DPP" if "DPP" in numeric else (numeric[0] if numeric else None)
    y0 = "D House Seats" if "D House Seats" in numeric else (numeric[1] if len(numeric)>1 else x0)
    return html.Div([
        html.Section([
            section_header("Simulation", "Monte Carlo explorer", "Interact with the stored cross-variable simulation sample while preserving the audited 50,000-run headline outputs."),
            html.Div([
                html.Div([html.Label("X variable", className="filter-label"), dcc.Dropdown(id="sim-x", options=numeric, value=x0, clearable=False, **PERSISTENCE)], className="filter-block"),
                html.Div([html.Label("Y variable", className="filter-label"), dcc.Dropdown(id="sim-y", options=numeric, value=y0, clearable=False, **PERSISTENCE)], className="filter-block"),
                html.Div([html.Label("Color", className="filter-label"), dcc.Dropdown(id="sim-color", options=[{"label":"None","value":"NONE"}]+[{"label":c,"value":c} for c in categorical], value="House Control" if "House Control" in categorical else "NONE", clearable=False, **PERSISTENCE)], className="filter-block"),
            ], className="filter-grid sim-filter-grid"),
            html.Div(dcc.Graph(id="simulation-scatter", config=PLOTLY_CONFIG), className="panel"),
            html.Div([
                html.Div(dcc.Graph(figure=seats_histogram(sims, "House"), config=PLOTLY_CONFIG), className="panel"),
                html.Div(dcc.Graph(figure=seats_histogram(sims, "Senate"), config=PLOTLY_CONFIG), className="panel"),
            ], className="two"),
            html.Div([html.Div("Monte Carlo summary", className="panel-title"), table_component(s["MonteCarloSummary"], page_size=10)], className="panel"),
        ], className="section"),
    ])


def context_view(signature: str):
    s = load_bundle(signature)["sheets"]
    return html.Div([
        html.Section([
            section_header("Context & architecture", "How the forecast is assembled", "Official forecast strategy, popular-vote bridge, module boundaries, and target-level output context."),
            html.Div([
                html.Div([html.Div("Popular vote bridge", className="panel-title"), table_component(s["PopularVoteBridge"], page_size=5)], className="panel"),
                html.Div([html.Div("Architecture contract", className="panel-title"), table_component(s["ArchitectureContract"], page_size=10)], className="panel"),
            ], className="two"),
            html.Div([html.Div("National forecast — all exported targets", className="panel-title"), table_component(s["NationalForecast"], page_size=15, max_rows=500)], className="panel"),
            html.Div([
                html.Div([html.Div("Module contract", className="panel-title"), table_component(s["ModuleContract"], page_size=8)], className="panel"),
                html.Div([html.Div("Module isolation audit", className="panel-title"), table_component(s["ModuleIsolation"], page_size=8)], className="panel"),
            ], className="two"),
        ], className="section"),
    ])


def validation_view(signature: str):
    s = load_bundle(signature)["sheets"]
    return html.Div([
        html.Section([
            section_header("Validation", "Historical performance & diagnostics", "Time-Machine election tests, district probability calibration, model quality, leakage audits, and Senate state-model validation."),
            html.Div([
                html.Div(dcc.Graph(figure=time_machine_house_figure(s["TimeMachineScorecard"]), config=PLOTLY_CONFIG), className="panel"),
                html.Div(dcc.Graph(figure=model_quality_figure(s["ModelQuality"]), config=PLOTLY_CONFIG), className="panel"),
            ], className="two"),
            html.Div([
                html.Div(dcc.Graph(figure=validation_scatter(s["HouseValidationOOF"]), config=PLOTLY_CONFIG), className="panel"),
                html.Div([html.Div("House validation summary", className="panel-title"), table_component(s["HouseValidationSummary"], page_size=12)], className="panel"),
            ], className="two"),
            html.Div([
                html.Div([html.Div("Senate validation", className="panel-title"), table_component(s["SenateValidation"], page_size=15)], className="panel"),
                html.Div([html.Div("House leakage audit", className="panel-title"), table_component(s["HouseLeakageAudit"], page_size=15)], className="panel"),
            ], className="two"),
            html.Div([html.Div("Time-Machine scorecard", className="panel-title"), table_component(s["TimeMachineScorecard"], page_size=12, max_rows=500)], className="panel"),
            html.Div([html.Div("All 42 held-out targets", className="panel-title"), table_component(s["TimeMachine42Targets"], page_size=15, max_rows=1000)], className="panel"),
            html.Div([
                html.Div([html.Div("Target-level Time-Machine summary", className="panel-title"), table_component(s["TimeMachineTargetSummary"], page_size=12, max_rows=500)], className="panel"),
                html.Div([html.Div("2026 fold stability", className="panel-title"), table_component(s["TargetStability2026"], page_size=12, max_rows=500)], className="panel"),
            ], className="two"),
            html.Div([
                html.Div([html.Div("Popular-vote validation", className="panel-title"), table_component(s["PopularVoteValidation"], page_size=12, max_rows=500)], className="panel"),
                html.Div([html.Div("Senate specification summary", className="panel-title"), table_component(s["SenateSpecSummary"], page_size=12, max_rows=500)], className="panel"),
            ], className="two"),
            html.Div([
                html.Div([html.Div("Full-pipeline sensitivity contract", className="panel-title"), table_component(s["SensitivityContract"], page_size=10, max_rows=100)], className="panel"),
                html.Div([html.Div("Popular-vote method challenge", className="panel-title"), table_component(s["PopularMethodAudit"], page_size=12, max_rows=100)], className="panel"),
            ], className="two"),
            html.Div([html.Div("Named full-pipeline stress tests", className="panel-title"), table_component(s["SensitivityScenarios"], page_size=10, max_rows=100)], className="panel"),
            html.Div([html.Div("One-at-a-time sensitivity · all 71 model features", className="panel-title"), table_component(s["SensitivityOAT"], page_size=15, max_rows=250)], className="panel"),
            html.Div([
                html.Div([html.Div("71-feature contract", className="panel-title"), table_component(s["FeatureContract71"], page_size=15, max_rows=100)], className="panel"),
                html.Div([html.Div("0–100 stress endpoints · 31 controls", className="panel-title"), table_component(s["ScenarioExtremes31"], page_size=15, max_rows=100)], className="panel"),
            ], className="two"),
            html.Div([
                html.Div([html.Div("Senate race stability", className="panel-title"), table_component(s["SenateRaceStability"], page_size=12, max_rows=500)], className="panel"),
                html.Div([html.Div("Pipeline stages", className="panel-title"), table_component(s["PipelineStageSummary"], page_size=12, max_rows=500)], className="panel"),
            ], className="two"),
            html.Div([html.Div("Validation contract", className="panel-title"), table_component(s["ValidationStages"], page_size=12, max_rows=500)], className="panel"),
            html.Div([
                html.Div([html.Div("v26 snapshot/Scenario contract", className="panel-title"), table_component(s["NationalPremodelContract"], page_size=10, max_rows=50)], className="panel"),
                html.Div([html.Div("v26 relationship regularization", className="panel-title"), table_component(s["NationalPremodelTuning"], page_size=12, max_rows=50)], className="panel"),
            ], className="two"),
            html.Div([html.Div("v26 relational engine · within-support sensitivity (31 × min/max)", className="panel-title"), table_component(s["NationalPremodelSupport31"], page_size=15, max_rows=100)], className="panel"),
            html.Div([html.Div("v26 relational engine · 0–100 stress sensitivity", className="panel-title"), table_component(s["NationalPremodelOAT31"], page_size=15, max_rows=100)], className="panel"),
            html.Div([html.Div("v26 relational engine · combined scenarios", className="panel-title"), table_component(s["NationalPremodelCombined"], page_size=15, max_rows=100)], className="panel"),
            html.Div([html.Div("v26 · 14×14 inter-unit relationship audit", className="panel-title"), table_component(s.get("NationalRelationships14", pd.DataFrame()), page_size=15, max_rows=182)], className="panel"),
            html.Div([html.Div("v26 · 31×31 control-level relationship audit", className="panel-title"), table_component(s.get("NationalRelationships31", pd.DataFrame()), page_size=15, max_rows=930)], className="panel"),
            html.Div([html.Div("v26 · 42-target counterfactual coherence audit", className="panel-title"), table_component(s.get("Scenario42Coherence", pd.DataFrame()), page_size=15, max_rows=100)], className="panel"),
            html.Div([html.Div("v26 · Senate D55 regression contract", className="panel-title"), table_component(s.get("ScenarioSenateRegression", pd.DataFrame()), page_size=10, max_rows=30)], className="panel"),
            html.Div([html.Div("v26 · Senate flip thresholds from 35 local anchors", className="panel-title"), table_component(s.get("ScenarioSenateFlipOrder", pd.DataFrame()), page_size=20, max_rows=40)], className="panel"),
        ], className="section"),
    ])


def scenario_view(signature: str):
    engine = load_scenario_engine(str(MODEL_PATH), MODEL_PATH.stat().st_mtime_ns)
    bundle = load_bundle(signature)
    senate_map = load_senate_map(signature)
    production_row = engine.production.iloc[0]
    fixed_non_up_d = int(round(float(production_row["DS before"] - production_row["DSS UP"])))
    baseline_house_data, _ = scenario_house_summary(bundle["house"], 0.0, 0.0)
    baseline_senate_data, _ = scenario_senate_summary(
        senate_map, bundle["senate"], 0.0, fixed_non_up_d, 0.0
    )
    baseline_senate_lookup = baseline_senate_data.set_index("STATE") if not baseline_senate_data.empty else pd.DataFrame()
    specifications = {spec.name: spec for spec in engine.input_specs}

    def control_card(spec):
        return html.Div([
            html.Div([
                html.Label(spec.label, className="filter-label"),
                html.Span(
                    f"Official {spec.baseline:.1f}% · history {spec.historical_minimum:.1f}–{spec.historical_maximum:.1f}%",
                    className="scenario-baseline",
                ),
            ], className="scenario-slider-heading"),
            dcc.Slider(
                id={"type":"national-scenario-input", "name":spec.name},
                min=0, max=100, step=spec.step,
                value=spec.baseline,
                marks={0: "0", 25: "25", 50: "50", 75: "75", 100: "100"},
                tooltip={"placement":"bottom", "always_visible":False},
                updatemode="mouseup",
            ),
        ], className="scenario-variable")

    by_group = {group: [] for group in INPUT_GROUPS}
    for display_group, display_controls in INPUT_GROUPS.items():
        display_set = set(display_controls)
        for unit, unit_controls in INTERVENTION_UNITS.items():
            controls = [name for name in unit_controls if name in display_set]
            if not controls:
                continue
            mutually_exclusive = len(unit_controls) > 1
            subtitle = (
                "Mutually exclusive response battery · total cannot exceed 100%"
                if mutually_exclusive
                else "Independent macroeconomic control"
            )
            by_group[display_group].append(html.Div([
                html.Div(display_group, className="scenario-battery-group"),
                html.Div([
                    html.Div(unit, className="scenario-battery-title"),
                    html.Div(subtitle, className="scenario-battery-note"),
                ], className="scenario-battery-heading"),
                html.Div(
                    [control_card(specifications[name]) for name in controls],
                    className="scenario-variable-grid",
                ),
            ], className="scenario-battery"))
    groups = [battery for controls in by_group.values() for battery in controls]
    return html.Div([
        html.Section([
            section_header(
                "MODEL-DRIVEN COUNTERFACTUAL",
                "Scenario Lab",
                "Adjust the national snapshot, release the slider, and inspect how the same forecast responds across popular vote, all 435 House districts, and all 35 scheduled Senate elections.",
            ),
            html.Div([
                html.Div("SCENARIO · NEVER OVERWRITES THE OFFICIAL FORECAST", className="scenario-warning"),
                html.Button("Reset all inputs", id="scenario-reset", n_clicks=0, className="scenario-reset"),
            ], className="scenario-warning-row"),
            html.Div(
                id="scenario-national-summary",
                className="scenario-metrics scenario-headline-metrics scenario-outcome-dock",
            ),
            html.Div([
                html.Div([
                    html.Div("Build the counterfactual", className="panel-title"),
                    html.P(
                        "Battery arithmetic is applied while dragging. When the slider is released, the fourteen-unit premodel reconciles the national state and reruns the 42 targets and both geographic translators.",
                        className="scenario-copy",
                    ),
                ], className="scenario-slider-intro"),
                html.Div(groups, className="scenario-slider-grid"),
            ], className="panel scenario-input-panel scenario-slider-board"),
            html.Div(className="scenario-map-grid", children=[
                html.Div([
                    html.Div("HOUSE · 435 DISTRICTS · PROJECTED TWO-PARTY VOTE", className="panel-title"),
                    dcc.Graph(
                        id="scenario-house-graph",
                        figure=house_map_figure(baseline_house_data, "margin", "ALL", "ALL", [], None),
                        config=PLOTLY_CONFIG,
                        className="scenario-house-graph",
                    ),
                ], className="panel scenario-map-panel scenario-house-map-panel"),
                html.Div([
                    html.Div("SENATE · 35 ELECTIONS", className="panel-title"),
                    html.Div(
                        [
                            _scenario_senate_tile(
                                row,
                                baseline_senate_lookup.loc[row["STATE"]]
                                if not baseline_senate_lookup.empty and row["STATE"] in baseline_senate_lookup.index
                                else None,
                            )
                            for _, row in senate_map.iterrows()
                        ],
                        id="scenario-senate-map-grid",
                        className="state-map-grid scenario-state-map-grid",
                    ),
                    html.Div(
                        "Hover any state for projected vote, margin, probability, official rating, and scenario change.",
                        className="map-selection",
                    ),
                ], className="panel scenario-map-panel scenario-senate-map-panel"),
            ]),
            html.Details([
                html.Summary("Methodology, constraints, and model diagnostics"),
                html.Div([
                    html.Div("Input constraints", className="panel-title"),
                    html.P(
                        "Every displayed response battery is bounded at 100%. The latest completed edit receives priority when requests conflict; compatible earlier edits remain active. Cross-battery movements are regularised historical associations, not causal effects.",
                        className="scenario-copy",
                    ),
                    html.Div(id="scenario-battery-status"),
                ], className="scenario-diagnostic-block"),
                html.Div(id="scenario-model-status", className="scenario-method-row"),
                html.Div([
                    html.Div([html.Div("House translator diagnostics", className="panel-title"), html.Div(id="scenario-summary", className="scenario-metrics scenario-map-metrics")]),
                    html.Div([html.Div("Senate translator diagnostics", className="panel-title"), html.Div(id="scenario-senate-summary", className="scenario-metrics scenario-map-metrics")]),
                ], className="two"),
            ], className="panel scenario-diagnostics"),
            html.Details([
                html.Summary("Senate scenario · all 35 races"),
                html.Div(id="scenario-senate-race-table"),
            ], className="panel scenario-diagnostics"),
            html.Details([
                html.Summary("All 42 national outputs and changed inputs"),
                html.Div([
                    html.Div(dcc.Graph(id="scenario-national-graph", config=PLOTLY_CONFIG), className="panel"),
                    html.Div([html.Div("All 42 national outputs · baseline vs scenario", className="panel-title"), html.Div(id="scenario-national-table")], className="panel"),
                ], className="two scenario-detail-grid"),
                html.Div([html.Div("Changed inputs", className="panel-title"), html.Div(id="scenario-changed-inputs")], className="panel"),
            ], className="panel scenario-diagnostics"),
        ], className="section"),
    ])


def render_tab(tab: str, signature: str):
    return {
        "overview": overview_view,
        "house": house_view,
        "senate": senate_view,
        "probability": probability_view,
        "simulation": simulation_view,
        "context": context_view,
        "validation": validation_view,
        "scenario": scenario_view,
    }.get(tab, overview_view)(signature)
