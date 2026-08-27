from __future__ import annotations

from statistics import NormalDist
from functools import lru_cache
from typing import Any, Optional

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from core import load_house_paths, parse_svg_path, safe_value

DEM = "#0B5CAB"
DEM_DARK = "#073B75"
REP = "#C1121F"
REP_DARK = "#7F0000"
PURPLE = "#8B5CF6"
YELLOW = "#F4D35E"
INK = "#0F172A"
MUTED = "#64748B"
GRID = "#E8EDF4"

PLOTLY_CONFIG = {
    "displaylogo": False,
    "responsive": True,
    "modeBarButtonsToRemove": ["lasso2d", "select2d"],
}



def canonical_rating(value: Any) -> str:
    text = safe_value(value)
    # Senate exports may use party-first labels (e.g. "R Lean") while the
    # HTML presentation uses strength-first labels ("Lean R").
    m = __import__("re").match(r"^([DR])\s+(Safe|Likely|Lean|Tilt)$", text, __import__("re").I)
    if m:
        return f"{m.group(2).title()} {m.group(1).upper()}"
    if text.lower() in {"toss-up", "tossup", "toss up"}:
        return "Toss-Up"
    return text

RATING_COLORS = {
    "Safe D": "#073B75",
    "Likely D": "#1769AA",
    "Lean D": "#5B9BD5",
    "Tilt D": "#A8D5EC",
    "Toss-Up": "#F4D35E",
    "Tossup": "#F4D35E",
    "Tilt R": "#F2B5B9",
    "Lean R": "#DF6670",
    "Likely R": "#C1121F",
    "Safe R": "#7F0000",
}


def theme(fig: go.Figure, height: int = 430, margin: Optional[dict] = None) -> go.Figure:
    fig.update_layout(
        height=height,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif", color=INK, size=12),
        title_font=dict(size=18, color=INK),
        margin=margin or dict(l=45, r=25, t=60, b=45),
        hoverlabel=dict(bgcolor="white", bordercolor="#D8E0EA", font=dict(color=INK)),
        legend=dict(orientation="h", y=1.04, x=0),
    )
    fig.update_xaxes(gridcolor=GRID, zerolinecolor="#CBD5E1")
    fig.update_yaxes(gridcolor=GRID, zerolinecolor="#CBD5E1")
    return fig


def _prob_color(p: float) -> str:
    if pd.isna(p):
        return "#CBD5E1"
    p = float(p)
    if p >= 95: return DEM_DARK
    if p >= 80: return "#1769AA"
    if p >= 65: return "#5B9BD5"
    if p > 50: return "#A8D5EC"
    if p == 50: return "#D8DEE8"
    if p >= 45: return "#F2B5B9"
    if p > 35: return "#EC9FA6"
    if p > 20: return "#DF6670"
    if p > 5: return REP
    return REP_DARK


def _number(value: Any, fallback: float = np.nan) -> float:
    try:
        result = float(value)
        return result if np.isfinite(result) else fallback
    except (TypeError, ValueError):
        return fallback


def party_margin(value: Any) -> str:
    margin = _number(value)
    if not np.isfinite(margin):
        return "—"
    magnitude = abs(margin)
    decimals = 2 if magnitude < 1 else 1
    if margin > 0:
        return f"D+{magnitude:.{decimals}f}"
    if margin < 0:
        return f"R+{magnitude:.{decimals}f}"
    return "EVEN 0.00"


def projected_two_party_shares(margin: Any) -> tuple[float, float]:
    value = _number(margin)
    if not np.isfinite(value):
        return np.nan, np.nan
    return 50.0 + value / 2.0, 50.0 - value / 2.0


def is_projected_flip(value: Any) -> bool:
    text = safe_value(value, "").lower()
    return "→" in text or "flip" in text


def house_hover(row: pd.Series, metric: str) -> str:
    district = safe_value(row.get("District Label"), safe_value(row.get("District ID")))
    rating = safe_value(row.get("Forecast Rating"))
    consensus = safe_value(row.get("All Source Consensus Rating"))
    dprob = _number(row.get("D Win Probability"), 50.0)
    rprob = _number(row.get("R Win Probability"), 100.0 - dprob)
    margin = _number(row.get("Projected Margin PP"), 0.0)
    scenario_share = _number(row.get("Scenario D Two-Party Share"))
    if np.isfinite(scenario_share):
        dshare, rshare = scenario_share, 100.0 - scenario_share
        margin = dshare - rshare
    else:
        dshare, rshare = projected_two_party_shares(margin)
    winner = safe_value(row.get("Projected Winner"))
    flip = safe_value(row.get("Projected Flip"), "Hold")
    if metric == "probability":
        return f"<b>{district}</b><br><span style='color:{DEM}'><b>D win {dprob:.1f}%</b></span> · <span style='color:{REP}'><b>R win {rprob:.1f}%</b></span>"
    if metric == "rating":
        return f"<b>{district}</b><br><b>Model rating: {rating}</b>"
    if metric == "consensus":
        sources = safe_value(row.get("All Source Count"), "—")
        return f"<b>{district}</b><br><b>Source consensus: {consensus}</b><br>{sources} rating sources"
    if metric == "margin":
        scenario_change = safe_value(row.get("Scenario Change vs Official"), "")
        scenario_outcome = safe_value(row.get("Scenario Outcome vs Incumbent"), flip)
        change_line = (
            f"<br>Scenario vs official: <b>{scenario_change}</b>"
            if scenario_change and scenario_change != "No change" else ""
        )
        return (
            f"<b>{district}</b><br>"
            f"<span style='color:{DEM}'><b>D {dshare:.2f}%</b></span> · "
            f"<span style='color:{REP}'><b>R {rshare:.2f}%</b></span>"
            f"<br><b>{winner} wins · {party_margin(margin)}</b> · {scenario_outcome}"
            f"<br>Win probability: D {dprob:.1f}% · R {rprob:.1f}% · {rating}"
            f"{change_line}"
        )
    return f"<b>{district}</b><br><b>{flip}</b> · projected {winner}<br>{rating} · {party_margin(margin)}"


def _margin_color(m: float) -> str:
    if pd.isna(m):
        return "#CBD5E1"
    m = float(m); magnitude = abs(m)
    # Exact ties use a quiet neutral. Every non-zero margin remains party-coded;
    # competitive races are pale red/blue rather than yellow.
    if magnitude < 1e-12: return "#D8DEE8"
    if m > 0:
        if magnitude < 1: return "#C7E4F2"
        if magnitude < 3: return "#9CCCE4"
        if magnitude < 7: return "#5B9BD5"
        if magnitude < 15: return "#1769AA"
        return DEM_DARK
    if magnitude < 1: return "#F5C6CA"
    if magnitude < 3: return "#EC9FA6"
    if magnitude < 7: return "#DF6670"
    if magnitude < 15: return REP
    return REP_DARK


def district_color(row: pd.Series, metric: str) -> str:
    if metric == "probability":
        return _prob_color(row.get("D Win Probability"))
    if metric == "margin":
        return _margin_color(row.get("Projected Margin PP"))
    if metric == "consensus":
        return RATING_COLORS.get(safe_value(row.get("All Source Consensus Rating")), "#CBD5E1")
    if metric == "flips":
        winner = safe_value(row.get("Projected Winner"))
        return DEM if winner == "D" else REP if winner == "R" else "#CBD5E1"
    return RATING_COLORS.get(safe_value(row.get("Forecast Rating")), "#CBD5E1")


def senate_color(row: pd.Series, metric: str) -> str:
    tier = safe_value(row.get("Tier"))
    if tier == "None":
        return "#E5E7EB"
    if tier == "Safe" and metric in {"forecast", "probability", "margin", "ratings"}:
        key = canonical_rating(safe_value(row.get("Forecast Rating Key"), safe_value(row.get("Forecast Rating"))))
        if key.endswith(" D"):
            return RATING_COLORS["Safe D"]
        if key.endswith(" R"):
            return RATING_COLORS["Safe R"]
    if metric == "probability":
        return _prob_color(row.get("D Win Probability"))
    if metric == "margin":
        return _margin_color(row.get("Projected Margin"))
    if metric == "ratings":
        key = safe_value(row.get("Forecast Rating Key"))
        return RATING_COLORS.get(canonical_rating(key), RATING_COLORS.get(canonical_rating(row.get("Forecast Rating")), "#CBD5E1"))
    if metric == "flips":
        flip = safe_value(row.get("Flip"), "")
        if flip == "D":
            return "repeating-linear-gradient(45deg,#1769AA 0 6px,#D9ECF7 6px 12px)"
        if flip == "R":
            return "repeating-linear-gradient(45deg,#C1121F 0 6px,#F8D5D8 6px 12px)"
        outcome = safe_value(row.get("Outcome"))
        return DEM if "Democratic" in outcome else REP if "Republican" in outcome else "#D8DEE8"
    p = row.get("D Win Probability")
    if p is not None and not pd.isna(p):
        if float(p) > 50: return DEM
        if float(p) < 50: return REP
        return "#D8DEE8"
    outcome = safe_value(row.get("Outcome"))
    return DEM if "Democratic" in outcome else REP if "Republican" in outcome else "#D8DEE8"


def projected_margin_color(value: Any) -> str:
    """Public winner-first red/blue scale shared by scenario callbacks."""
    return _margin_color(_number(value))


@lru_cache(maxsize=1)
def _house_plot_geometry() -> dict[str, Any]:
    """Parse the shared SVG geometry once per Dash process."""
    paths = load_house_paths()
    states = []
    for state in paths["raw"].get("states", []):
        xs: list[Optional[float]] = []
        ys: list[Optional[float]] = []
        for ring in parse_svg_path(state.get("d", "")):
            xs.extend([point[0] for point in ring] + [ring[0][0], None])
            ys.extend([point[1] for point in ring] + [ring[0][1], None])
        states.append((xs, ys))
    districts: dict[str, dict[str, Any]] = {}
    for geoid, path_row in paths["districts"].items():
        rings = parse_svg_path(path_row.get("d", ""))
        xs: list[Optional[float]] = []
        ys: list[Optional[float]] = []
        all_points: list[tuple[float, float]] = []
        for ring in rings:
            all_points.extend(ring)
            xs.extend([point[0] for point in ring] + [ring[0][0], None])
            ys.extend([point[1] for point in ring] + [ring[0][1], None])
        districts[geoid] = {
            "x": xs,
            "y": ys,
            "cx": float(np.mean([point[0] for point in all_points])) if all_points else np.nan,
            "cy": float(np.mean([point[1] for point in all_points])) if all_points else np.nan,
        }
    return {
        "states": states,
        "districts": districts,
        "viewBox": paths["raw"].get("viewBox", [0, 0, 960, 510]),
    }


def house_map_patch(house: pd.DataFrame, metric: str = "probability"):
    """Return a Dash Patch that changes data, never House geometry.

    Scenario Lab starts with the official House figure already mounted. Slider
    callbacks update only fills and hover copy, which avoids the white flash from
    rebuilding 485+ traces on every input change.
    """
    from dash import Patch

    geometry = _house_plot_geometry()
    patched = Patch()
    state_trace_count = len(geometry["states"])
    click_hovers: list[str] = []
    for offset, (_, row) in enumerate(house.iterrows()):
        trace_index = state_trace_count + offset
        hover = house_hover(row, metric)
        patched["data"][trace_index]["fillcolor"] = district_color(row, metric)
        patched["data"][trace_index]["opacity"] = 1.0
        patched["data"][trace_index]["hovertemplate"] = hover + "<extra></extra>"
        click_hovers.append(hover)
    click_index = state_trace_count + len(house)
    patched["data"][click_index]["text"] = click_hovers
    patched["layout"]["datarevision"] = f"scenario-{metric}-{float(pd.to_numeric(house.get('D Win Probability'), errors='coerce').sum()):.6f}"
    return patched


def house_map_figure(
    house: pd.DataFrame,
    metric: str = "rating",
    state: str = "ALL",
    rating: str = "ALL",
    flags: Optional[list[str]] = None,
    selected_district: Optional[str] = None,
) -> go.Figure:
    """Render the exact composite Albers paths produced by the notebook package.

    This avoids the GeoJSON/projection matching issue seen in Dash v1 and keeps the
    map fully local/offline. The same shared path asset is used by the audited HTML.
    """
    flags = flags or []
    geometry = _house_plot_geometry()
    df = house.copy()
    if df.empty:
        return theme(go.Figure().add_annotation(text="HouseRaceDetail is empty.", x=.5, y=.5, showarrow=False), height=650)

    matched = pd.Series(True, index=df.index)
    if state != "ALL":
        matched &= df["State"].eq(state)
    if rating != "ALL":
        matched &= df["Forecast Rating"].eq(rating)
    if "competitive" in flags and "Competitive" in df.columns:
        matched &= df["Competitive"].fillna(False).astype(bool)
    if "flips" in flags and "Projected Flip" in df.columns:
        matched &= ~df["Projected Flip"].fillna("Hold").astype(str).str.lower().eq("hold")
    if "disagreement" in flags and "Model vs Consensus Disagreement" in df.columns:
        matched &= df["Model vs Consensus Disagreement"].fillna(False).astype(bool)
    matched_ids = set(df.loc[matched, "District ID"].astype(str))

    fig = go.Figure()
    cent_x: list[float] = []
    cent_y: list[float] = []
    cent_id: list[str] = []
    cent_hover: list[str] = []

    # State boundaries first, underneath districts.
    for xs, ys in geometry["states"]:
        fig.add_trace(go.Scatter(
            x=xs, y=ys, mode="lines", line=dict(color="#B8C2CF", width=.8),
            hoverinfo="skip", showlegend=False,
        ))

    for _, row in df.iterrows():
        geoid = safe_value(row.get("GEOID4"), "")
        shape = geometry["districts"].get(geoid)
        if not shape:
            continue
        xs = shape["x"]
        ys = shape["y"]

        district_id = safe_value(row.get("District ID"))
        is_match = district_id in matched_ids
        selected = district_id == selected_district
        color = district_color(row, metric) if is_match else "#E8EDF3"
        opacity = 1.0 if is_match else .32
        line_color = PURPLE if selected else "#FFFFFF"
        line_width = 2.3 if selected else .38
        hover = house_hover(row, metric)
        trace_kwargs = {}
        if metric == "flips" and is_match and is_projected_flip(row.get("Projected Flip")):
            winner = safe_value(row.get("Projected Winner"))
            light = "#D9ECF7" if winner == "D" else "#F8D5D8"
            trace_kwargs["fillpattern"] = dict(shape="/", fgcolor=light, bgcolor=color, size=7, solidity=.35)
        fig.add_trace(go.Scatter(
            x=xs, y=ys,
            mode="lines",
            fill="toself",
            fillcolor=color,
            opacity=opacity,
            line=dict(color=line_color, width=line_width),
            name=district_id,
            customdata=[district_id] * len(xs),
            hovertemplate=hover + "<extra></extra>",
            hoveron="fills+points",
            showlegend=False,
            **trace_kwargs,
        ))
        if np.isfinite(shape["cx"]) and np.isfinite(shape["cy"]):
            cent_x.append(shape["cx"]); cent_y.append(shape["cy"]); cent_id.append(district_id); cent_hover.append(hover)

    fig.add_trace(go.Scatter(
        x=cent_x, y=cent_y, mode="markers",
        marker=dict(size=12, color="rgba(0,0,0,0.01)", line=dict(width=0)),
        customdata=cent_id,
        text=cent_hover,
        hovertemplate="%{text}<extra></extra>",
        showlegend=False,
        name="district-click-targets",
    ))

    viewbox = geometry["viewBox"]
    x0, y0, width, height = [float(v) for v in viewbox]
    fig.update_xaxes(range=[x0, x0 + width], visible=False, fixedrange=True)
    # SVG y grows downward, so reverse the Plotly y-axis.
    fig.update_yaxes(range=[y0 + height, y0], visible=False, fixedrange=True, scaleanchor="x", scaleratio=1)
    title_map = {
        "rating": "Forecast rating",
        "probability": "Democratic win probability",
        "margin": "Projected D–R margin",
        "consensus": "All-source consensus rating",
        "flips": "Projected holds & flips",
    }
    fig.update_layout(
        title=f"2026 House — {title_map.get(metric, metric)}",
        dragmode=False,
        hovermode="closest",
        uirevision="house-map-v3",
        datarevision=f"{metric}|{state}|{rating}|{','.join(sorted(flags))}|{selected_district or ''}",
    )
    return theme(fig, height=660, margin=dict(l=2, r=2, t=48, b=2))


def control_probability_figure(df: pd.DataFrame) -> go.Figure:
    if df.empty:
        return theme(go.Figure())
    d = df.copy()
    d["Probability (%)"] = pd.to_numeric(d["Probability (%)"], errors="coerce")
    colors = [DEM if "Democratic" in str(o) else REP if "Republican" in str(o) else PURPLE for o in d["Outcome"]]
    fig = go.Figure(go.Bar(
        x=d["Outcome"], y=d["Probability (%)"], marker_color=colors,
        text=[f"{v:.1f}%" for v in d["Probability (%)"]], textposition="outside",
        hovertemplate="%{x}: %{y:.2f}%<extra></extra>",
    ))
    fig.update_layout(title="Probability of chamber control", showlegend=False)
    fig.update_yaxes(title="Probability", range=[0, 100], ticksuffix="%")
    return theme(fig)


def popular_vote_figure(df: pd.DataFrame) -> go.Figure:
    if df.empty:
        return theme(go.Figure())
    d = df.copy()
    ycol = "Share (%)" if "Share (%)" in d.columns else "Share"
    vals = pd.to_numeric(d[ycol], errors="coerce")
    if vals.max() <= 1.5:
        vals = vals * 100
    colors = [DEM if str(p).startswith("D") else REP if str(p).startswith("R") else PURPLE for p in d["Party"]]
    fig = go.Figure(go.Bar(x=d["Party"], y=vals, marker_color=colors, text=[f"{v:.2f}%" for v in vals], textposition="outside"))
    fig.update_layout(title="National popular vote projection", showlegend=False)
    fig.update_yaxes(title="Vote share", ticksuffix="%")
    return theme(fig)


def seats_histogram(sims: pd.DataFrame, chamber: str) -> go.Figure:
    col = f"D {chamber} Seats"
    if sims.empty or col not in sims.columns:
        return theme(go.Figure())
    s = pd.to_numeric(sims[col], errors="coerce").dropna()
    fig = go.Figure(go.Histogram(x=s, nbinsx=max(12, min(45, int(s.nunique()))), marker_color=DEM, opacity=.9))
    majority = 218 if chamber == "House" else 51
    fig.add_vline(x=majority, line_color=INK, line_dash="dash", annotation_text=f"Majority {majority}")
    fig.update_layout(title=f"{chamber} Democratic-seat distribution", bargap=.04)
    fig.update_xaxes(title="Democratic seats")
    fig.update_yaxes(title="Stored simulation draws")
    return theme(fig)


def simulation_scatter(sims: pd.DataFrame, x: str, y: str, color: Optional[str] = None, max_rows: int = 5000) -> go.Figure:
    if sims.empty or x not in sims.columns or y not in sims.columns:
        return theme(go.Figure())
    d = sims[[c for c in [x, y, color] if c and c in sims.columns]].dropna().head(max_rows)
    fig = px.scatter(d, x=x, y=y, color=color if color in d.columns else None, opacity=.38, render_mode="webgl")
    fig.update_layout(title=f"{y} vs {x}")
    return theme(fig, height=500)


def senate_race_figure(senate: pd.DataFrame) -> go.Figure:
    if senate.empty:
        return theme(go.Figure())
    d = senate.copy()
    margin_col = "Adjusted Margin 2P" if "Adjusted Margin 2P" in d.columns else "Model Projected Margin 2P"
    d[margin_col] = pd.to_numeric(d[margin_col], errors="coerce")
    d = d.sort_values(margin_col)
    colors = [DEM if v >= 0 else REP for v in d[margin_col].fillna(0)]
    custom_cols = [c for c in ["Forecast Rating", "D Win Probability", "R Win Probability", "Model Assigned Outcome"] if c in d.columns]
    custom = d[custom_cols] if custom_cols else None
    fig = go.Figure(go.Bar(
        x=d[margin_col], y=d["STATE"], orientation="h", marker_color=colors,
        customdata=custom,
        hovertemplate="<b>%{y}</b><br>Model margin: %{x:+.2f} pp<extra></extra>",
    ))
    fig.add_vline(x=0, line_color=INK, line_width=1.3)
    fig.update_layout(title="Monitored Senate races — model margins", showlegend=False)
    fig.update_xaxes(title="Democratic margin (pp)")
    fig.update_yaxes(title=None)
    return theme(fig, height=max(430, 45 * len(d) + 110), margin=dict(l=115, r=25, t=60, b=45))


def model_quality_figure(df: pd.DataFrame) -> go.Figure:
    if df.empty:
        return theme(go.Figure())
    d = df.copy()
    y = "Diagnostic Stability (0-100)" if "Diagnostic Stability (0-100)" in d.columns else d.select_dtypes("number").columns[0]
    fig = go.Figure(go.Bar(x=d["Group"], y=d[y], marker_color=[DEM, PURPLE, REP][:len(d)], text=[f"{v:.1f}" for v in d[y]], textposition="outside"))
    fig.update_layout(title="Diagnostic stability by model component", showlegend=False)
    fig.update_yaxes(title="Stability (0–100)", range=[0, 100])
    return theme(fig)


def time_machine_house_figure(df: pd.DataFrame) -> go.Figure:
    if df.empty:
        return theme(go.Figure())
    candidates = [
        ("Test Election", "D House Seats Actual", "D House Seats Predicted"),
        ("Election Year", "Actual D House Seats", "Predicted D House Seats"),
    ]
    found = next((t for t in candidates if all(c in df.columns for c in t)), None)
    if not found:
        numeric = df.select_dtypes("number").columns.tolist()
        if len(numeric) < 3:
            return theme(go.Figure())
        found = (numeric[0], numeric[1], numeric[2])
    x, actual, pred = found
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df[x], y=df[actual], mode="lines+markers", name="Actual", line=dict(color=INK, width=3)))
    fig.add_trace(go.Scatter(x=df[x], y=df[pred], mode="lines+markers", name="Predicted", line=dict(color=DEM, width=3, dash="dash")))
    fig.update_layout(title="Time-Machine validation — House seats")
    fig.update_xaxes(title="Held-out election")
    fig.update_yaxes(title="Democratic House seats")
    return theme(fig)


def validation_scatter(df: pd.DataFrame) -> go.Figure:
    if df.empty or not {"Actual D Win", "Predicted D Win Probability"}.issubset(df.columns):
        return theme(go.Figure())
    d = df.copy().dropna(subset=["Actual D Win", "Predicted D Win Probability"])
    # Aggregate into probability bins for a calibration-style plot.
    d["p"] = pd.to_numeric(d["Predicted D Win Probability"], errors="coerce")
    if d["p"].max() > 1.5:
        d["p"] /= 100
    d["bin"] = pd.cut(d["p"], bins=np.linspace(0, 1, 11), include_lowest=True)
    cal = d.groupby("bin", observed=False).agg(pred=("p", "mean"), actual=("Actual D Win", "mean"), n=("Actual D Win", "size")).dropna()
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=cal["pred"]*100, y=cal["actual"]*100, mode="lines+markers", marker=dict(size=np.clip(np.sqrt(cal["n"])*2, 7, 22)), name="Observed"))
    fig.add_trace(go.Scatter(x=[0,100], y=[0,100], mode="lines", line=dict(color="#94A3B8", dash="dash"), name="Perfect calibration"))
    fig.update_layout(title="House probability calibration")
    fig.update_xaxes(title="Predicted D win probability", ticksuffix="%", range=[0,100])
    fig.update_yaxes(title="Observed D win rate", ticksuffix="%", range=[0,100])
    return theme(fig)


def _calibrate_expected_count(probabilities: np.ndarray, target: float) -> tuple[np.ndarray, float]:
    """Apply one bounded common logit shift to reach an expected count target."""
    probabilities = np.clip(np.asarray(probabilities, dtype=float), 1e-6, 1 - 1e-6)
    target = float(np.clip(target, 0.0, len(probabilities)))
    logits = np.log(probabilities / (1.0 - probabilities))
    low, high = -20.0, 20.0
    for _ in range(80):
        middle = (low + high) / 2.0
        expected = float((1.0 / (1.0 + np.exp(-np.clip(logits + middle, -35, 35)))).sum())
        if expected < target:
            low = middle
        else:
            high = middle
    shift = (low + high) / 2.0
    adjusted = 1.0 / (1.0 + np.exp(-np.clip(logits + shift, -35, 35)))
    return adjusted, shift


def _calibrate_share_mean(base_shares: np.ndarray, target_mean: float) -> np.ndarray:
    """Bounded logit shift preserving the complete district ordering."""
    base = np.clip(np.asarray(base_shares, dtype=float), 0.005, 0.995)
    target = float(np.clip(target_mean, 0.005, 0.995))
    logits = np.log(base / (1.0 - base))
    low, high = -30.0, 30.0
    for _ in range(120):
        middle = (low + high) / 2.0
        shares = 1.0 / (1.0 + np.exp(-np.clip(logits + middle, -35.0, 35.0)))
        if float(shares.mean()) < target:
            low = middle
        else:
            high = middle
    return 1.0 / (1.0 + np.exp(-np.clip(logits + (low + high) / 2.0, -35.0, 35.0)))


def _fit_house_scenario_sigma(margins: np.ndarray, probabilities: np.ndarray) -> float:
    """Match the notebook's bounded one-dimensional normal-scale calibration."""
    nd = NormalDist()
    margins = np.asarray(margins, dtype=float)
    probabilities = np.asarray(probabilities, dtype=float)

    def objective(sigma: float) -> float:
        fitted = np.asarray([nd.cdf(float(margin) / sigma) for margin in margins])
        return float(np.mean((fitted - probabilities) ** 2))

    low, high = 1.0, 40.0
    ratio = (5.0 ** 0.5 - 1.0) / 2.0
    left = high - ratio * (high - low)
    right = low + ratio * (high - low)
    for _ in range(90):
        if objective(left) <= objective(right):
            high, right = right, left
            left = high - ratio * (high - low)
        else:
            low, left = left, right
            right = low + ratio * (high - low)
    return float((low + high) / 2.0)


def _scenario_rating(probability_pct: float) -> str:
    probability = float(probability_pct) / 100.0
    advantage = abs(probability - 0.5)
    if advantage < .05:
        return "Toss-Up"
    party = "D" if probability > .5 else "R"
    if advantage < .15:
        return f"Tilt {party}"
    if advantage < .30:
        return f"Lean {party}"
    if advantage < .45:
        return f"Likely {party}"
    return f"Safe {party}"


def scenario_house_summary(
    house: pd.DataFrame,
    swing: float,
    structural_seat_delta: float = 0.0,
) -> tuple[pd.DataFrame, dict[str, float]]:
    """National two-party-share change through all 435 modeled districts.

    ``swing`` is the change in Democratic two-party vote share, never a forced
    seat count. The bounded reconciliation preserves every district's official
    local ordering; winners and expected seats emerge from probabilities.
    """
    d = house.copy()
    official_winner = d["Projected Winner"].astype(str).copy()
    incumbent_party = d.get("Baseline Party Model", d.get("Incumbent Party Raw", pd.Series("", index=d.index))).astype(str)
    nd = NormalDist()
    base_probabilities = np.clip(
        pd.to_numeric(d["D Win Probability"], errors="coerce").to_numpy(float) / 100.0,
        1e-8, 1.0 - 1e-8,
    )
    base_margins = pd.to_numeric(d["Projected Margin PP"], errors="coerce").to_numpy(float)
    base_shares = np.clip((base_margins + 100.0) / 200.0, 0.005, 0.995)
    target_mean = float(np.clip(base_shares.mean() + float(swing) / 100.0, 0.005, 0.995))
    scenario_shares = _calibrate_share_mean(base_shares, target_mean)
    scenario_vote_margins = 200.0 * scenario_shares - 100.0
    sigma = _fit_house_scenario_sigma(base_margins, base_probabilities)
    if abs(float(swing)) < 1e-12:
        probabilities = base_probabilities.copy()
        reconciliation = 0.0
    else:
        probabilities = np.asarray([
            nd.cdf(float(margin) / sigma) for margin in scenario_vote_margins
        ], dtype=float)
        baseline_normal = np.asarray([
            nd.cdf(float(margin) / sigma) for margin in base_margins
        ], dtype=float)
        reconciliation = float(base_probabilities.sum() - baseline_normal.sum())
    pre_structural_expected = float(probabilities.sum())
    probabilities, structural_logit_shift = _calibrate_expected_count(
        probabilities,
        pre_structural_expected + reconciliation + float(structural_seat_delta),
    )
    d["Scenario D Win Probability"] = 100.0 * probabilities
    d["Scenario D Two-Party Share"] = 100.0 * scenario_shares
    d["Scenario Probability-Equivalent Margin PP"] = 7.436 * np.log(
        np.clip(probabilities, 1e-8, 1.0 - 1e-8)
        / np.clip(1.0 - probabilities, 1e-8, 1.0)
    )
    d["Scenario Vote Margin PP"] = scenario_vote_margins
    d["Scenario Winner"] = np.where(d["Scenario D Win Probability"] >= 50, "D", "R")
    d["Official Projected Winner"] = official_winner
    d["Scenario Change vs Official"] = np.where(
        d["Scenario Winner"].eq(official_winner),
        "No change",
        official_winner + "→" + d["Scenario Winner"],
    )
    d["Scenario Outcome vs Incumbent"] = np.where(
        d["Scenario Winner"].eq(incumbent_party),
        np.where(d["Scenario Winner"].eq("D"), "Democratic Hold", "Republican Hold"),
        np.where(d["Scenario Winner"].eq("D"), "Democratic Flip", "Republican Flip"),
    )
    d["D Win Probability"] = d["Scenario D Win Probability"]
    d["R Win Probability"] = 100.0 - d["Scenario D Win Probability"]
    d["Projected Margin PP"] = d["Scenario Vote Margin PP"]
    d["Projected Winner"] = d["Scenario Winner"]
    d["Projected Flip"] = d["Scenario Outcome vs Incumbent"]
    d["Forecast Rating"] = d["Scenario D Win Probability"].map(_scenario_rating)
    summary = {
        "D seats by median winner": float((d["Scenario Winner"] == "D").sum()),
        "R seats by median winner": float((d["Scenario Winner"] == "R").sum()),
        "Expected D seats": float((d["Scenario D Win Probability"] / 100).sum()),
        "Expected R seats": float(len(d) - (d["Scenario D Win Probability"] / 100).sum()),
        "Popular swing pp": float(swing),
        "District-weighted D two-party share": float(100.0 * scenario_shares.mean()),
        "Scenario probability sigma pp": float(sigma),
        "Structural seat delta": float(structural_seat_delta),
        "Structural logit shift": float(structural_logit_shift),
    }
    return d, summary


def scenario_house_close_races_figure(d: pd.DataFrame) -> go.Figure:
    if d.empty:
        return theme(go.Figure())
    s = d.sort_values("Scenario D Win Probability", key=lambda x: (x-50).abs()).head(40).sort_values("Scenario D Win Probability")
    colors = [DEM if p >= 50 else REP for p in s["Scenario D Win Probability"]]
    fig = go.Figure(go.Bar(
        x=s["Scenario D Win Probability"], y=s["District ID"], orientation="h", marker_color=colors,
        customdata=s[["Forecast Rating", "Scenario Margin PP"]],
        hovertemplate="<b>%{y}</b><br>Scenario D win: %{x:.1f}%<br>Scenario margin: %{customdata[1]:+.1f} pp<br>Official rating: %{customdata[0]}<extra></extra>",
    ))
    fig.add_vline(x=50, line_color=INK, line_dash="dash")
    fig.update_layout(title="40 closest House races under exploratory swing")
    fig.update_xaxes(title="Scenario D win probability", range=[0,100], ticksuffix="%")
    return theme(fig, height=760, margin=dict(l=80,r=20,t=60,b=45))


def scenario_senate_summary(
    senate_map: pd.DataFrame,
    senate: pd.DataFrame,
    swing: float,
    fixed_non_up_d: int,
    structural_seat_delta: float = 0.0,
) -> tuple[pd.DataFrame, dict[str, float]]:
    """Translate a coordinated swing across all 35 scheduled Senate elections.

    Monitored races retain their official model anchors. Unmonitored Safe races
    use the notebook-exported PVI/prior-election proxy only inside Scenario Lab;
    their official forecast has no numeric margin, share, or probability.
    """
    d = senate_map.loc[senate_map["Tier"].ne("None")].copy()
    monitored = senate.set_index("STATE") if not senate.empty else pd.DataFrame()
    nd = NormalDist()
    probabilities = []
    baseline_margins = []
    sigmas = []
    ratings = []
    baseline_types = []
    for _, row in d.iterrows():
        state = str(row["STATE"])
        if not monitored.empty and state in monitored.index:
            source = monitored.loc[state]
            if isinstance(source, pd.DataFrame):
                source = source.iloc[0]
            p = float(np.clip(_number(source.get("D Win Probability"), 50.0) / 100.0, 0.001, 0.999))
            margin = _number(source.get("Adjusted Margin 2P"), _number(source.get("Model Projected Margin 2P"), 0.0))
            z = nd.inv_cdf(p)
            sigma = abs(margin / z) if abs(z) > .08 else 6.0
            sigma = float(np.clip(sigma, 2.0, 20.0))
            rating = safe_value(source.get("Forecast Rating"))
            baseline_type = "Official monitored state model"
        else:
            p = float(np.clip(
                _number(row.get("Scenario Baseline D Win Probability")) / 100.0,
                0.001, 0.999,
            ))
            margin = _number(row.get("Scenario Baseline Margin PP"))
            sigma = float(np.clip(
                _number(row.get("Scenario Probability Sigma PP")), 2.0, 20.0
            ))
            if not np.isfinite(p) or not np.isfinite(margin) or not np.isfinite(sigma):
                raise ValueError(f"Missing Scenario-Lab structural baseline for {state}")
            rating = safe_value(row.get("Forecast Rating"))
            baseline_type = "Scenario-only PVI + previous-election proxy"
        p2 = p if abs(float(swing)) < 1e-12 else nd.cdf(nd.inv_cdf(p) + float(swing) / sigma)
        probabilities.append(p2)
        baseline_margins.append(float(margin))
        sigmas.append(float(sigma))
        ratings.append(rating)
        baseline_types.append(baseline_type)
    probabilities = np.asarray(probabilities, dtype=float)
    pre_structural_expected = float(probabilities.sum())
    if abs(float(structural_seat_delta)) > 1e-12:
        probabilities, structural_logit_shift = _calibrate_expected_count(
            probabilities,
            pre_structural_expected + float(structural_seat_delta),
        )
    else:
        structural_logit_shift = 0.0
    scenario_margins = np.asarray([
        sigma * nd.inv_cdf(float(np.clip(probability, 1e-8, 1.0 - 1e-8)))
        for probability, sigma in zip(probabilities, sigmas)
    ])
    d["Scenario D Win Probability"] = 100.0 * probabilities
    d["Scenario Margin PP"] = scenario_margins
    d["Scenario D 2P"] = np.clip(50.0 + scenario_margins / 2.0, 0.0, 100.0)
    d["Scenario R 2P"] = 100.0 - d["Scenario D 2P"]
    d["Scenario R Win Probability"] = 100.0 - d["Scenario D Win Probability"]
    d["Scenario Baseline Margin PP Used"] = baseline_margins
    d["Scenario Probability Sigma PP Used"] = sigmas
    d["Scenario Baseline Type"] = baseline_types
    d["Official Forecast Rating"] = ratings
    d["Scenario Winner"] = np.where(d["Scenario D Win Probability"].ge(50), "D", "R")
    official_winner = d.get("Projected Winner", pd.Series("", index=d.index)).astype(str)
    official_winner = official_winner.where(official_winner.isin(["D", "R"]), np.where(
        d["Outcome"].astype(str).str.contains("Democratic", case=False, na=False), "D", "R"
    ))
    incumbent_party = d.get("Incumbent Party", pd.Series("", index=d.index)).astype(str)
    incumbent_party = incumbent_party.where(incumbent_party.isin(["D", "R"]), official_winner)
    d["Official Projected Winner"] = official_winner
    d["Scenario Change vs Official"] = np.where(
        d["Scenario Winner"].eq(official_winner),
        "No change",
        official_winner + "→" + d["Scenario Winner"],
    )
    d["Scenario Outcome vs Incumbent"] = np.where(
        d["Scenario Winner"].eq(incumbent_party),
        np.where(d["Scenario Winner"].eq("D"), "Democratic Hold", "Republican Hold"),
        np.where(d["Scenario Winner"].eq("D"), "Democratic Flip", "Republican Flip"),
    )
    summary = {
        "D seats by race winner": float(fixed_non_up_d + d["Scenario D Win Probability"].ge(50).sum()),
        "R seats by race winner": float(100 - fixed_non_up_d - d["Scenario D Win Probability"].ge(50).sum()),
        "Expected D seats": float(fixed_non_up_d + probabilities.sum()),
        "Expected R seats": float(100 - fixed_non_up_d - probabilities.sum()),
        "Scheduled elections": float(len(d)),
        "Unmonitored Safe structural proxies": float(d["Tier"].eq("Safe").sum()),
        "Popular swing pp": float(swing),
        "Structural seat delta": float(structural_seat_delta),
        "Structural logit shift": float(structural_logit_shift),
    }
    return d, summary


def scenario_senate_figure(d: pd.DataFrame) -> go.Figure:
    if d.empty:
        return theme(go.Figure())
    ordered = d.sort_values("Scenario D Win Probability")
    colors = [DEM if p >= 50 else REP for p in ordered["Scenario D Win Probability"]]
    fig = go.Figure(go.Bar(
        x=ordered["Scenario D Win Probability"], y=ordered["STATE"], orientation="h",
        marker_color=colors,
        customdata=ordered[["Scenario Margin PP", "Official Forecast Rating", "Scenario Baseline Type"]],
        hovertemplate="<b>%{y}</b><br>Scenario D win: %{x:.1f}%<br>Scenario margin: %{customdata[0]:+.2f} pp<br>Official rating: %{customdata[1]}<br>Baseline: %{customdata[2]}<extra></extra>",
    ))
    fig.add_vline(x=50, line_color=INK, line_dash="dash", annotation_text="50%")
    fig.update_layout(title="All scheduled Senate races under exploratory swing", showlegend=False)
    fig.update_xaxes(title="Scenario D win probability", ticksuffix="%", range=[0,100])
    return theme(fig, height=max(450, 44 * len(ordered) + 120), margin=dict(l=110,r=20,t=60,b=45))


def national_scenario_figure(baseline: dict[str, float], scenario: dict[str, float]) -> go.Figure:
    """Three unit-safe indicators: vote percentage, House seats, Senate seats."""
    metrics = [
        ("D popular vote", "%", baseline["D Popular Vote (%)"], scenario["D Popular Vote (%)"]),
        ("House median-winner D", " seats", baseline["D House Seats"], scenario["D House Seats"]),
        ("Senate race-winner D", " seats", baseline["D Senate Seats"], scenario["D Senate Seats"]),
    ]
    fig = go.Figure()
    domains = [(0.00, 0.31), (0.345, 0.655), (0.69, 1.00)]
    for (label, suffix, base_value, scenario_value), (x0, x1) in zip(metrics, domains):
        fig.add_trace(go.Indicator(
            mode="number+delta",
            value=float(scenario_value),
            number={"suffix": suffix, "font": {"size": 35, "color": INK}, "valueformat": ".2f" if suffix == "%" else ".0f"},
            delta={"reference": float(base_value), "relative": False, "valueformat": "+.2f" if suffix == "%" else "+.0f", "position": "bottom"},
            title={"text": label},
            domain={"x": [x0, x1], "y": [0.08, 0.94]},
        ))
    fig.update_layout(title="Scenario response · units kept separate")
    return theme(fig, height=330, margin=dict(l=15, r=15, t=55, b=15))
