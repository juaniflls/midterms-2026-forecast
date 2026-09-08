from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from urllib.parse import quote

import pandas as pd
from dash import dash_table, dcc, html

from core import MODEL_PATH, latest_html_path, load_bundle, load_senate_map, safe_value
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


def details_table(title: str, df: pd.DataFrame, *, page_size: int = 12, max_rows: int = 1000, copy: str = ""):
    return html.Details([
        html.Summary([
            html.Span(title, className="audit-details-title"),
            html.Span("Open table", className="audit-details-action"),
        ]),
        html.P(copy, className="audit-details-copy") if copy else None,
        html.Div(table_component(df, page_size=page_size, max_rows=max_rows, compact=True), className="audit-details-body"),
    ], className="audit-details")


def _metric_lookup(df: pd.DataFrame) -> dict[str, Any]:
    if df is None or df.empty or df.shape[1] < 2:
        return {}
    return dict(zip(df.iloc[:, 0].astype(str), df.iloc[:, 1]))


def seat_change_strip(bundle: dict[str, Any], chamber: str):
    s = bundle["sheets"]
    if chamber == "House":
        account = _metric_lookup(s.get("HouseSeatAccounting", pd.DataFrame()))
        d_flips = int(float(account.get("Democratic flips (R→D)", 0)))
        r_flips = int(float(account.get("Republican flips (D→R)", 0)))
        net_d = int(float(account.get("Net Democratic gain", d_flips - r_flips)))
        before_d = int(float(account.get("2024 Baseline Democratic seats", 0)))
        before_r = int(float(account.get("2024 Baseline Republican seats", 0)))
        after_d = int(float(account.get("Official central Democratic seats", 0)))
        after_r = int(float(account.get("Official central Republican seats", 0)))
        baseline_label = "2024 baseline → central"
    else:
        account = _metric_lookup(s.get("SenateSeatAccounting", pd.DataFrame()))
        d_flips = int(float(account.get("Democratic flips (R→D)", 0)))
        r_flips = int(float(account.get("Republican flips (D→R)", 0)))
        net_d = int(float(account.get("Net Democratic gain", d_flips - r_flips)))
        before_d = int(float(account.get("Pre-2026 Democratic seats", 0)))
        before_r = int(float(account.get("Pre-2026 Republican seats", 0)))
        after_d = int(float(account.get("Official central Democratic seats", 0)))
        after_r = int(float(account.get("Official central Republican seats", 0)))
        baseline_label = "Pre-2026 → central"

    net_class = "change-dem" if net_d > 0 else "change-rep" if net_d < 0 else "change-neutral"
    net_party = "D" if net_d > 0 else "R" if net_d < 0 else "EVEN"
    net_value = f"{net_party} +{abs(net_d)}" if net_d else "0"
    return html.Div([
        html.Div([
            html.Div("Democratic flips", className="change-label"),
            html.Div(str(d_flips), className="change-value dem"),
            html.Div("R → D", className="change-note"),
        ], className="change-card change-dem"),
        html.Div([
            html.Div("Republican flips", className="change-label"),
            html.Div(str(r_flips), className="change-value rep"),
            html.Div("D → R", className="change-note"),
        ], className="change-card change-rep"),
        html.Div([
            html.Div("Net seat change", className="change-label"),
            html.Div(net_value, className=f"change-value {'dem' if net_d > 0 else 'rep' if net_d < 0 else ''}"),
            html.Div("Central map vs baseline", className="change-note"),
        ], className=f"change-card {net_class}"),
        html.Div([
            html.Div(baseline_label, className="change-label"),
            html.Div(f"D {before_d}–R {before_r}", className="change-baseline"),
            html.Div(f"→ D {after_d}–R {after_r}", className="change-note strong"),
        ], className="change-card change-baseline-card"),
    ], className="seat-change-strip")


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



def forecast_view(signature: str):
    """Render the exact notebook-authored standalone forecast inside Dash.

    This is intentionally a presentation bridge, not a second implementation of
    the central forecast. The HTML stays at repository root and remains the
    notebook's audited source of truth; Dash serves it locally without duplicating
    the file inside dash_app/.
    """
    html_path = latest_html_path()
    if html_path is None:
        return html.Div([
            html.Section([
                section_header(
                    "OFFICIAL FORECAST",
                    "Notebook forecast HTML not found",
                    "Run Block 8 of the stable v27.1 notebook. Dash will detect the new HTML automatically.",
                ),
                html.Div("Native audited views remain available in the tabs above.", className="empty-state"),
            ], className="section"),
            overview_view(signature),
        ])
    return html.Div([
        html.Div([
            html.Div([
                html.Div("ALL-IN-ONE FORECAST", className="section-kicker"),
                html.Div("Complete audited notebook forecast · one compact surface", className="forecast-frame-title"),
            ]),
            html.Div(html_path.name, className="forecast-frame-source"),
        ], className="forecast-frame-bar"),
        html.Iframe(
            src=f"/forecast-html?sig={quote(signature, safe='')}",
            className="forecast-iframe",
            title="Official v27.1 Midterms 2026 forecast",
        ),
    ], className="forecast-shell")


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
            section_header("Central forecast contract", "One forecast, one coherent map", "The v27.1 centralizer is audited after the race-by-race Monte Carlo: modal chamber total, supported central configuration, and coherent race-level public tuples."),
            html.Div(table_component(s.get("CentralForecastContract", pd.DataFrame()), page_size=12, max_rows=50), className="panel"),
        ], className="section"),
        html.Section([
            section_header("Audit snapshot", "Final uncertainty", "The same final uncertainty export that feeds the audited report."),
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


def _distribution_row(label: str, counts: dict[str, int], unknown_count: int = 0, unknown_label: str = "No source consensus"):
    total = max(1, sum(counts.values()) + int(unknown_count))
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
    if unknown_count:
        segments.append(html.Div(
            str(int(unknown_count)),
            className="control-distribution-segment control-distribution-missing",
            style={"width": f"{100.0 * int(unknown_count) / total:.5f}%", "background": "#D9E1EA", "color": "#526174", "textShadow": "none"},
            title=f"{unknown_label}: {int(unknown_count)}",
        ))
        legend.append(html.Span([
            html.I(style={"background": "#D9E1EA"}),
            f"{unknown_label} {int(unknown_count)}",
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
        source_consensus = house["Source Consensus Rating"]
        rows = [
            _distribution_row(
                "Model forecast",
                _rating_counts(house.get("Forecast Rating", pd.Series(dtype=str))),
            ),
            _distribution_row(
                "Source consensus",
                _rating_counts(source_consensus),
            ),
        ]
        subtitle = f"Official central forecast D {dem_seats} · R {rep_seats} · 435 district-level forecasts"
    else:
        senate_map = load_senate_map(bundle["signature"])
        scheduled = senate_map.loc[senate_map["Tier"].ne("None")]
        rows = [
            _distribution_row(
                "2026 Senate races",
                _rating_counts(scheduled.get("Forecast Rating Key", pd.Series(dtype=str))),
            )
        ]
        subtitle = f"Official central forecast D {dem_seats} · R {rep_seats} · 11 monitored races + fixed/safe seats"

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
    b = load_bundle(signature); s = b["sheets"]; h = b["house"]
    states = sorted(h["State"].dropna().astype(str).unique()) if not h.empty else []
    ratings = [r for r in ["Safe D","Likely D","Lean D","Tilt D","Toss-Up","Tilt R","Lean R","Likely R","Safe R"] if r in set(h.get("Forecast Rating", []))]
    return html.Div([
        html.Section([
            section_header("435 districts", "Explore the House", "Interactive district desk for the same official central forecast. Filter the map, compare the model with the same 435-seat source consensus used by the notebook HTML, inspect flips, and open any district-level forecast."),
            chamber_control_hero(b, "House"),
            seat_change_strip(b, "House"),
            html.Div([
                html.Div([html.Label("State", className="filter-label"), dcc.Dropdown(id="house-state", options=[{"label":"All states","value":"ALL"}]+[{"label":x,"value":x} for x in states], value="ALL", clearable=False, **PERSISTENCE)], className="filter-block"),
                html.Div([html.Label("Forecast rating", className="filter-label"), dcc.Dropdown(id="house-rating", options=[{"label":"All ratings","value":"ALL"}]+[{"label":x,"value":x} for x in ratings], value="ALL", clearable=False, **PERSISTENCE)], className="filter-block"),
                html.Div([html.Label("Map metric", className="filter-label"), dcc.Dropdown(id="house-metric", options=[
                    {"label":"Projected two-party vote","value":"margin"}, {"label":"Win probability","value":"probability"},
                    {"label":"Forecast rating","value":"rating"}, {"label":"Source consensus","value":"consensus"},
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
            html.Div([
                html.Div("House flips — auditable district by district", className="panel-title"),
                html.P("Exact central seat changes versus the canonical 2024 numbered-district baseline.", className="scenario-copy"),
                table_component(s.get("HouseFlipAudit", pd.DataFrame()), page_size=12, max_rows=435, compact=True),
            ], className="panel"),
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
            section_header("Senate battlefield", "Explore the Senate, race by race", "Interactive state desk for the official v27.1 central pattern. Explore the 11 monitored state models, holds/flips and all 35 scheduled elections without changing the forecast."),
            chamber_control_hero(b, "Senate"),
            seat_change_strip(b, "Senate"),
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
            html.Div([
                html.Div([html.Div("Official Senate central accounting", className="panel-title"), table_component(s.get("SenateSeatAccounting", pd.DataFrame()), page_size=22, max_rows=50)], className="panel"),
                html.Div([html.Div("Exact-pattern support", className="panel-title"), table_component(s.get("SenateCentralPatterns", pd.DataFrame()), page_size=12, max_rows=50)], className="panel"),
            ], className="two senate-bottom"),
            html.Div([
                html.Div("Senate flips — official central pattern", className="panel-title"),
                table_component(s.get("SenateModelFlips", pd.DataFrame()), page_size=11, max_rows=35, compact=True),
            ], className="panel"),
        ], className="section"),
    ])


def probability_view(signature: str):
    b = load_bundle(signature); s = b["sheets"]; d = b["dashboard"]
    house_d = float(d.get("House Democratic Control Probability", 0.0))
    house_r = float(d.get("House Republican Control Probability", 0.0))
    senate_d = float(d.get("Senate Democratic Control Probability", 0.0))
    senate_r = float(d.get("Senate Republican Control Probability", 0.0))
    senate_5050 = float(d.get("Senate 50-50 Probability", 0.0))
    runs = int(float(d.get("Monte Carlo Simulations", 0)))

    def odds_row(label, dem_p, rep_p, note=""):
        total = max(dem_p + rep_p, 1e-9)
        dem_w = 100.0 * dem_p / total
        rep_w = 100.0 * rep_p / total
        return html.Div([
            html.Div([
                html.Div(label, className="odds-label"),
                html.Div(note, className="odds-note"),
            ], className="odds-copy"),
            html.Div([
                html.Div(f"D {dem_p:.1f}%", className="odds-number dem"),
                html.Div([
                    html.Div(style={"width": f"{dem_w:.4f}%"}, className="odds-dem"),
                    html.Div(style={"width": f"{rep_w:.4f}%"}, className="odds-rep"),
                ], className="odds-track"),
                html.Div(f"R {rep_p:.1f}%", className="odds-number rep"),
            ], className="odds-bar-row"),
        ], className="odds-row")

    return html.Div([
        html.Section([
            section_header(
                "Probability & risk",
                "How uncertain is the forecast?",
                "One official central map, with the full Monte Carlo uncertainty shown around it. Control odds and intervals are distribution diagnostics — not competing forecasts.",
            ),
            html.Div([
                metric_card("House · D control", f"{house_d:.1f}%", "Probability across all simulations", "dem"),
                metric_card("Senate · R control", f"{senate_r:.1f}%", "50–50 counts as Republican control under the modeled VP assumption", "rep"),
                metric_card("Senate · exact 50–50", f"{senate_5050:.1f}%", "Scenario probability, not a second central forecast", "purple"),
                metric_card("Monte Carlo", f"{runs:,}", "Complete election simulations", "purple"),
            ], className="hero probability-hero"),

            html.Div([
                html.Div("Control odds", className="panel-title"),
                html.P("Direct probability bars avoid mixing the chamber-control distribution with the official central point forecast.", className="panel-copy"),
                odds_row("House control", house_d, house_r, "218 seats required for a House majority"),
                odds_row("Senate control", senate_d, senate_r, "A 50–50 Senate is Republican control under the modeled 2026 VP assumption"),
            ], className="panel probability-odds-panel"),

            html.Div([
                html.Div([
                    html.Div("Close-race risk", className="panel-title"),
                    html.P("How often simulations finish near the chamber-control threshold.", className="panel-copy"),
                    table_component(s["CloseRaceRisk"], page_size=10, compact=True),
                ], className="panel stable-table-panel"),
                html.Div([
                    html.Div("Official forecast & intervals", className="panel-title"),
                    html.P("Central point forecast beside the 90% and 95% Monte Carlo ranges.", className="panel-copy"),
                    table_component(s["PredictionIntervals"], page_size=10, compact=True),
                ], className="panel stable-table-panel"),
            ], className="two stable-grid"),

            html.Div([
                html.Div([
                    html.Div("Chamber margin summary", className="panel-title"),
                    table_component(s["MarginSummary"], page_size=8, compact=True),
                ], className="panel stable-table-panel"),
                html.Div([
                    html.Div("How to read this page", className="panel-title"),
                    html.Div([
                        html.Div([html.B("Central forecast"), html.Span("One coherent official map.")], className="reading-rule"),
                        html.Div([html.B("Control probability"), html.Span("Frequency of control across all simulated elections.")], className="reading-rule"),
                        html.Div([html.B("Intervals"), html.Span("Ranges of possible outcomes, not alternate official forecasts.")], className="reading-rule"),
                    ], className="reading-rules"),
                ], className="panel"),
            ], className="two stable-grid"),
            details_table("Final uncertainty snapshot · full audit table", s["FinalUncertainty"], page_size=18, max_rows=100),
        ], className="section"),
    ])


def simulation_view(signature: str):
    b = load_bundle(signature); s = b["sheets"]; sims = s["MonteCarloSample"]; d = b["dashboard"]
    numeric = sims.select_dtypes("number").columns.tolist() if not sims.empty else []
    categorical = [c for c in sims.columns if c not in numeric] if not sims.empty else []
    x0 = "DPP" if "DPP" in numeric else (numeric[0] if numeric else None)
    y0 = "D House Seats" if "D House Seats" in numeric else (numeric[1] if len(numeric)>1 else x0)
    house_account = _metric_lookup(s.get("HouseSeatAccounting", pd.DataFrame()))
    senate_account = _metric_lookup(s.get("SenateSeatAccounting", pd.DataFrame()))
    return html.Div([
        html.Section([
            section_header(
                "Monte Carlo",
                "Explore simulated election worlds",
                "The full production run contains 50,000 complete elections. This page explores the stored simulation sample; the official central map remains a separate v27.1 modal-conditional object.",
            ),
            html.Div([
                metric_card("Production simulations", f"{int(float(d.get('Monte Carlo Simulations', 0))):,}", "Full audited run", "purple"),
                metric_card("House modal total", f"D {int(float(house_account.get('Official central Democratic seats', 0)))}", f"{int(float(house_account.get('Modal-total simulations', 0))):,} simulations at the modal total", "dem"),
                metric_card("Senate modal total", f"D {int(float(senate_account.get('Official central Democratic seats', 0)))}", f"{float(senate_account.get('50-50 probability (%)', 0)):.1f}% exact 50–50 probability", "rep"),
                metric_card("Stored explorer rows", f"{len(sims):,}", "Cross-variable sample available to this interactive view", "purple"),
            ], className="hero simulation-hero"),

            html.Div([
                html.Div([html.Label("X variable", className="filter-label"), dcc.Dropdown(id="sim-x", options=numeric, value=x0, clearable=False, **PERSISTENCE)], className="filter-block"),
                html.Div([html.Label("Y variable", className="filter-label"), dcc.Dropdown(id="sim-y", options=numeric, value=y0, clearable=False, **PERSISTENCE)], className="filter-block"),
                html.Div([html.Label("Color", className="filter-label"), dcc.Dropdown(id="sim-color", options=[{"label":"None","value":"NONE"}]+[{"label":c,"value":c} for c in categorical], value="House Control" if "House Control" in categorical else "NONE", clearable=False, **PERSISTENCE)], className="filter-block"),
            ], className="filter-grid sim-filter-grid"),

            html.Div([
                html.Div("Cross-variable simulation explorer", className="panel-title"),
                html.P("Change X, Y and color to inspect how national vote, seats and chamber control co-move.", className="panel-copy"),
                html.Div(
                    dcc.Graph(id="simulation-scatter", config=PLOTLY_CONFIG, style={"height":"500px","width":"100%"}),
                    className="graph-shell graph-shell-lg",
                ),
            ], className="panel simulation-main stable-graph-panel"),

            html.Div([
                html.Div([
                    html.Div("House seat distribution", className="panel-title"),
                    html.Div(dcc.Graph(figure=seats_histogram(sims, "House"), config=PLOTLY_CONFIG, style={"height":"360px"}), className="graph-shell"),
                ], className="panel stable-graph-panel"),
                html.Div([
                    html.Div("Senate seat distribution", className="panel-title"),
                    html.Div(dcc.Graph(figure=seats_histogram(sims, "Senate"), config=PLOTLY_CONFIG, style={"height":"360px"}), className="graph-shell"),
                ], className="panel stable-graph-panel"),
            ], className="two stable-grid"),
            details_table("Monte Carlo summary · distribution diagnostics", s["MonteCarloSummary"], page_size=10, max_rows=100),
        ], className="section"),
    ])


def context_view(signature: str):
    b = load_bundle(signature); s = b["sheets"]
    central = s.get("CentralForecastContract", pd.DataFrame())
    central_pass = int(central["Passed"].astype(bool).sum()) if (not central.empty and "Passed" in central.columns) else 0
    central_total = len(central)

    stages = [
        ("1", "National inputs", "Current national conditions and the five historical midterm cycles enter the frozen national model."),
        ("2", "42-target national engine", "The selected production pipeline creates the learned national environment and popular-vote projection."),
        ("3", "House race engine", "All 435 districts are modeled individually from district fundamentals, ratings, polling where available and national context."),
        ("4", "Senate race engine", "The 11 monitored races receive state-level margins, probabilities and uncertainty; 24 Safe races remain categorical officially."),
        ("5", "Joint Monte Carlo", "50,000 complete election worlds preserve common national sensitivity and race-specific uncertainty."),
        ("6", "One central forecast", "The modal chamber total and the most supported coherent map within that total define the single published forecast."),
        ("7", "Probability layer", "Control odds and intervals are calculated from the entire simulation distribution and never overwrite the central map."),
        ("8", "Scenario Lab", "A separate counterfactual engine changes user-controlled inputs, reconciles related variables and reruns downstream geography."),
    ]
    return html.Div([
        html.Section([
            section_header(
                "Methodology",
                "How the forecast is assembled",
                "The production model is a one-way pipeline: national context feeds race engines, complete elections are simulated, and one coherent central map is selected. Scenario Lab remains separate.",
            ),

            html.Div([
                html.Div([
                    html.Div(n, className="flow-step-number"),
                    html.H3(title),
                    html.P(copy),
                ], className="flow-step")
                for n, title, copy in stages
            ], className="methodology-flow methodology-flow-eight"),

            html.Div([
                metric_card("Central contract", f"{central_pass}/{central_total} PASS" if central_total else "—", "Race-level and chamber-level coherence", "purple"),
                metric_card("National targets", "42", "Learned production outputs", "dem"),
                metric_card("House races", "435", "District-level forecasts", "dem"),
                metric_card("Senate 2026", "35", "11 monitored + 24 Safe categorical races", "rep"),
            ], className="hero methodology-hero"),

            html.Div([
                html.Div([
                    html.Div("Production rule", className="panel-title"),
                    html.H3("Forecast first. Diagnostics second.", className="method-card-title"),
                    html.P("The official House and Senate maps are downstream outputs of the race engines and Monte Carlo centralizer. Expected seats, medians, modes of other summaries and validation diagnostics never become competing public forecasts.", className="method-card-copy"),
                ], className="panel method-explainer"),
                html.Div([
                    html.Div("Isolation rule", className="panel-title"),
                    html.H3("No downstream feedback into the model.", className="method-card-title"),
                    html.P("Dash only reads audited outputs. House and Senate final results do not retrain national inputs, and Scenario Lab counterfactuals do not rewrite the frozen official forecast.", className="method-card-copy"),
                ], className="panel method-explainer"),
            ], className="two stable-grid"),

            html.Div([
                details_table("Popular-vote bridge", s["PopularVoteBridge"], page_size=5, max_rows=50, copy="National vote anchor feeding the production environment."),
                details_table("Architecture contract", s["ArchitectureContract"], page_size=10, max_rows=100, copy="One-way module boundaries: what each stage consumes, produces and may feed."),
                details_table("National forecast · all 42 exported targets", s["NationalForecast"], page_size=15, max_rows=500),
                details_table("Module contract", s["ModuleContract"], page_size=10, max_rows=200),
                details_table("Module isolation audit", s["ModuleIsolation"], page_size=10, max_rows=200),
            ], className="details-stack"),
        ], className="section"),
    ])


def validation_view(signature: str):
    b = load_bundle(signature); s = b["sheets"]; d = b["dashboard"]
    consistency = s.get("ConsistencyAudit", pd.DataFrame())
    if not consistency.empty and "Passed" in consistency.columns:
        consistency_pass = int(consistency["Passed"].astype(bool).sum())
        consistency_total = len(consistency)
    else:
        consistency_pass = consistency_total = 0

    return html.Div([
        html.Section([
            section_header(
                "Validation",
                "Historical performance & model diagnostics",
                "Historical tests and publication-level integrity checks are shown first. Deep technical audits remain available below without overwhelming the page.",
            ),
            html.Div([
                metric_card("Consistency audit", f"{consistency_pass}/{consistency_total} PASS" if consistency_total else "—", "Final report integrity checks", "purple"),
                metric_card("House stability", safe_value(d.get("House Diagnostic Stability")), "Diagnostic stability score", "dem"),
                metric_card("Senate stability", safe_value(d.get("Senate Diagnostic Stability")), "Diagnostic stability score", "rep"),
                metric_card("Popular-vote stability", safe_value(d.get("Popular Vote Diagnostic Stability")), "Diagnostic stability score", "purple"),
            ], className="hero validation-hero"),

            html.Div([
                html.Div([
                    html.Div("Time-Machine · House", className="panel-title"),
                    html.P("Held-out historical elections: forecast versus realized House seats.", className="panel-copy"),
                    html.Div(dcc.Graph(figure=time_machine_house_figure(s["TimeMachineScorecard"]), config=PLOTLY_CONFIG, style={"height":"340px"}), className="graph-shell"),
                ], className="panel stable-graph-panel"),
                html.Div([
                    html.Div("Model quality", className="panel-title"),
                    html.P("Production stability, tree disagreement, constraint impact and nested OOF error.", className="panel-copy"),
                    html.Div(dcc.Graph(figure=model_quality_figure(s["ModelQuality"]), config=PLOTLY_CONFIG, style={"height":"340px"}), className="graph-shell"),
                ], className="panel stable-graph-panel"),
            ], className="two stable-grid"),

            html.Div([
                html.Div([
                    html.Div("House district validation", className="panel-title"),
                    html.Div(dcc.Graph(figure=validation_scatter(s["HouseValidationOOF"]), config=PLOTLY_CONFIG, style={"height":"450px"}), className="graph-shell graph-shell-lg"),
                ], className="panel stable-graph-panel"),
                html.Div([
                    html.Div("House validation summary", className="panel-title"),
                    html.P("Held-out district performance and production calibration summary.", className="panel-copy"),
                    table_component(s["HouseValidationSummary"], page_size=12, compact=True),
                ], className="panel stable-table-panel"),
            ], className="two stable-grid"),

            html.Div([
                html.Div([
                    html.Div("Senate state-model validation", className="panel-title"),
                    table_component(s["SenateValidation"], page_size=12, compact=True),
                ], className="panel stable-table-panel"),
                html.Div([
                    html.Div("Popular-vote validation", className="panel-title"),
                    table_component(s["PopularVoteValidation"], page_size=10, max_rows=500, compact=True),
                ], className="panel stable-table-panel"),
            ], className="two stable-grid"),

            html.Div([
                details_table("Final consistency audit", consistency, page_size=18, max_rows=200),
                details_table("Time-Machine scorecard", s["TimeMachineScorecard"], page_size=12, max_rows=500),
                details_table("All 42 held-out targets", s["TimeMachine42Targets"], page_size=15, max_rows=1000),
                details_table("Target-level Time-Machine summary", s["TimeMachineTargetSummary"], page_size=12, max_rows=500),
                details_table("2026 fold stability", s["TargetStability2026"], page_size=12, max_rows=500),
                details_table("House leakage audit", s["HouseLeakageAudit"], page_size=15, max_rows=500),
                details_table("Senate specification summary", s["SenateSpecSummary"], page_size=12, max_rows=500),
                details_table("Full-pipeline sensitivity contract", s["SensitivityContract"], page_size=10, max_rows=100),
                details_table("Named full-pipeline stress tests", s["SensitivityScenarios"], page_size=10, max_rows=100),
                details_table("One-at-a-time sensitivity · 71 features", s["SensitivityOAT"], page_size=15, max_rows=250),
                details_table("71-feature contract", s["FeatureContract71"], page_size=15, max_rows=100),
                details_table("0–100 stress endpoints · 31 controls", s["ScenarioExtremes31"], page_size=15, max_rows=100),
                details_table("Senate race stability", s["SenateRaceStability"], page_size=12, max_rows=500),
                details_table("Pipeline stages", s["PipelineStageSummary"], page_size=12, max_rows=500),
                details_table("Validation contract", s["ValidationStages"], page_size=12, max_rows=500),
                details_table("v27.1 snapshot / Scenario contract", s["NationalPremodelContract"], page_size=10, max_rows=50),
                details_table("v27 relationship regularization", s["NationalPremodelTuning"], page_size=12, max_rows=50),
                details_table("v27 relational engine · within-support sensitivity", s["NationalPremodelSupport31"], page_size=15, max_rows=100),
                details_table("v27 relational engine · 0–100 stress sensitivity", s["NationalPremodelOAT31"], page_size=15, max_rows=100),
                details_table("v27 relational engine · combined scenarios", s["NationalPremodelCombined"], page_size=15, max_rows=100),
                details_table("v27 · 14×14 inter-unit relationship audit", s.get("NationalRelationships14", pd.DataFrame()), page_size=15, max_rows=182),
                details_table("v27 · 31×31 control-level relationship audit", s.get("NationalRelationships31", pd.DataFrame()), page_size=15, max_rows=930),
                details_table("v27 · 42-target counterfactual coherence audit", s.get("Scenario42Coherence", pd.DataFrame()), page_size=15, max_rows=100),
                details_table("v27 · Senate D55 regression contract", s.get("ScenarioSenateRegression", pd.DataFrame()), page_size=10, max_rows=30),
                details_table("v27 · Senate flip thresholds from 35 local anchors", s.get("ScenarioSenateFlipOrder", pd.DataFrame()), page_size=20, max_rows=40),
            ], className="details-stack"),
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
    dashboard = bundle["dashboard"]
    official_house_d = int(float(dashboard["Democratic House Seats"]))
    official_house_r = int(float(dashboard["Republican House Seats"]))
    official_senate_d = int(float(dashboard["Democratic Senate Seats"]))
    official_senate_r = int(float(dashboard["Republican Senate Seats"]))

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
                "COUNTERFACTUAL DATA LAB",
                "Scenario Lab",
                f"Adjust the observed national snapshot, release the slider, and rerun the same v27 counterfactual pipeline across the 42 national targets, all 435 House districts, and all 35 scheduled Senate elections. Reset is exactly the current official central forecast: House D{official_house_d}–R{official_house_r} · Senate D{official_senate_d}–R{official_senate_r}.",
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
                    html.Div("Scenario engine baseline / coherence contract", className="panel-title"),
                    table_component(bundle["sheets"].get("ScenarioEngineContract", pd.DataFrame()), page_size=14, max_rows=60, compact=True),
                ], className="scenario-diagnostic-block"),
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
        "forecast": forecast_view,
        "overview": overview_view,
        "house": house_view,
        "senate": senate_view,
        "probability": probability_view,
        "simulation": simulation_view,
        "context": context_view,
        "validation": validation_view,
        "scenario": scenario_view,
    }.get(tab, overview_view)(signature)
