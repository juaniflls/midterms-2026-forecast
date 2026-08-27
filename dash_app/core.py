from __future__ import annotations

import gzip
import json
import math
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

import pandas as pd

DASH_DIR = Path(__file__).resolve().parent
# The notebook, Model.xlsx, outputs, and shared assets live at repository root.
# Dash is deliberately downstream and never keeps private source copies.
PROJECT_ROOT = DASH_DIR.parent
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
SHARED_ASSETS_DIR = PROJECT_ROOT / "assets"
MODEL_PATH = PROJECT_ROOT / "Model.xlsx"
HOUSE_PATHS_PATH = SHARED_ASSETS_DIR / "house_cd120_albers_paths.json.gz"
HOUSE_GEOJSON_PATH = SHARED_ASSETS_DIR / "house_cd120_official.geojson.gz"
BRAND_LOGO_PATH = SHARED_ASSETS_DIR / "branding" / "Midterms_2026_Logo.svg"

REPORT_RE = re.compile(r"Election_Model_Final_Report_v(\d+)\.xlsx$", re.I)
HTML_RE = re.compile(r"Election_Model_2026_Dashboard_v(\d+)\.html$", re.I)

# Stable 50-state tile geometry. The Senate map is built from this structural
# table plus workbook sheets; it never scrapes another HTML dashboard.
SENATE_STATE_GRID = [
    ("Alabama", "AL", 6, 7), ("Alaska", "AK", 1, 1),
    ("Arizona", "AZ", 5, 2), ("Arkansas", "AR", 5, 5),
    ("California", "CA", 4, 1), ("Colorado", "CO", 4, 3),
    ("Connecticut", "CT", 4, 11), ("Delaware", "DE", 5, 10),
    ("Florida", "FL", 7, 9), ("Georgia", "GA", 6, 8),
    ("Hawaii", "HI", 7, 1), ("Idaho", "ID", 2, 2),
    ("Illinois", "IL", 3, 6), ("Indiana", "IN", 3, 7),
    ("Iowa", "IA", 3, 5), ("Kansas", "KS", 5, 4),
    ("Kentucky", "KY", 4, 6), ("Louisiana", "LA", 6, 5),
    ("Maine", "ME", 1, 11), ("Maryland", "MD", 4, 9),
    ("Massachusetts", "MA", 3, 11), ("Michigan", "MI", 2, 8),
    ("Minnesota", "MN", 2, 5), ("Mississippi", "MS", 6, 6),
    ("Missouri", "MO", 4, 5), ("Montana", "MT", 2, 3),
    ("Nebraska", "NE", 4, 4), ("Nevada", "NV", 3, 2),
    ("New Hampshire", "NH", 2, 11), ("New Jersey", "NJ", 4, 10),
    ("New Mexico", "NM", 5, 3), ("New York", "NY", 3, 10),
    ("North Carolina", "NC", 5, 8), ("North Dakota", "ND", 2, 4),
    ("Ohio", "OH", 3, 8), ("Oklahoma", "OK", 6, 4),
    ("Oregon", "OR", 3, 1), ("Pennsylvania", "PA", 3, 9),
    ("Rhode Island", "RI", 4, 12), ("South Carolina", "SC", 5, 9),
    ("South Dakota", "SD", 3, 4), ("Tennessee", "TN", 5, 6),
    ("Texas", "TX", 7, 4), ("Utah", "UT", 4, 2),
    ("Vermont", "VT", 2, 10), ("Virginia", "VA", 4, 8),
    ("Washington", "WA", 2, 1), ("West Virginia", "WV", 4, 7),
    ("Wisconsin", "WI", 2, 6), ("Wyoming", "WY", 3, 3),
]


def _version_key(path: Path, regex: re.Pattern[str]) -> tuple[int, int]:
    m = regex.search(path.name)
    version = int(m.group(1)) if m else -1
    try:
        mtime = path.stat().st_mtime_ns
    except FileNotFoundError:
        mtime = 0
    return version, mtime


def latest_report_path() -> Path:
    candidates = list(OUTPUTS_DIR.glob("Election_Model_Final_Report_v*.xlsx"))
    if not candidates:
        raise FileNotFoundError(
            f"No Election_Model_Final_Report_v*.xlsx found in {OUTPUTS_DIR}. "
            "Run the Jupyter model notebook first."
        )
    return max(candidates, key=lambda p: _version_key(p, REPORT_RE))


def latest_html_path() -> Optional[Path]:
    candidates = list(PROJECT_ROOT.glob("Election_Model_2026_Dashboard_v*.html"))
    if not candidates:
        return None
    return max(candidates, key=lambda p: _version_key(p, HTML_RE))


def project_signature() -> str:
    parts: list[str] = []
    try:
        rp = latest_report_path()
        parts.append(f"report:{rp.name}:{rp.stat().st_mtime_ns}:{rp.stat().st_size}")
    except Exception as exc:
        parts.append(f"report:missing:{type(exc).__name__}")
    # The static HTML is a sibling deliverable, not a Dash data source. Excluding
    # it from the signature prevents needless tab rebuilds and map flicker.
    # Model.xlsx is an upstream input, not a rendered Dash data source. Editing it
    # must not invalidate the UI before the production notebook has generated a
    # new audited report. Its presence is still exposed by status_payload().
    if HOUSE_PATHS_PATH.exists():
        parts.append(f"paths:{HOUSE_PATHS_PATH.stat().st_mtime_ns}:{HOUSE_PATHS_PATH.stat().st_size}")
    else:
        parts.append("paths:missing")
    return "|".join(parts)


def _clean(df: pd.DataFrame) -> pd.DataFrame:
    return df.dropna(how="all").reset_index(drop=True)


def _kv(df: pd.DataFrame) -> dict[str, Any]:
    df = _clean(df)
    if df.shape[1] < 2:
        return {}
    return dict(zip(df.iloc[:, 0].astype(str), df.iloc[:, 1]))


def _read_optional(xls: pd.ExcelFile, sheet: str) -> pd.DataFrame:
    if sheet not in xls.sheet_names:
        return pd.DataFrame()
    return _clean(pd.read_excel(xls, sheet_name=sheet))


def _coerce_num(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    for c in cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def _senate_outcome(winner: Any, incumbent: Any) -> tuple[str, str]:
    """Return the authoritative forecast outcome and flip party for one race."""
    winner_party = str(winner).strip().upper()
    incumbent_party = str(incumbent).strip().upper()
    if winner_party not in {"D", "R"}:
        return "No projected winner", ""
    party_name = "Democratic" if winner_party == "D" else "Republican"
    is_flip = incumbent_party in {"D", "R"} and winner_party != incumbent_party
    return f"{party_name} {'Flip' if is_flip else 'Hold'}", winner_party if is_flip else ""


@lru_cache(maxsize=4)
def load_bundle(signature: Optional[str] = None) -> dict[str, Any]:
    # signature is intentionally part of the cache key. A new notebook output file
    # automatically produces a new cache entry without touching the Dash code.
    signature = signature or project_signature()
    report = latest_report_path()
    sheets: dict[str, pd.DataFrame] = {}
    wanted = [
        "Dashboard_Data", "RunMetadata", "ExecutiveSummary", "FinalProjection",
        "FinalSnapshot", "ModelQuality", "ElectionSnapshot", "PopularVote",
        "ControlSummary", "HouseDistribution", "SenateDistribution",
        "SenateAttribution", "SenateModelFlips", "SenateCompetitive",
        "SenateRaceDetail", "SenateSafeBaselines", "SenateHistoricSummary", "SenateRaceSimulation",
        "SenateStateModelCV", "SenateStateModel", "SenateValidation",
        "SenateNestedFolds", "SenateCycleValidation", "SenateSpecSummary",
        "SenateRaceStability", "NationalForecast", "NationalNestedOOF",
        "NationalNestedFolds", "NationalFinalSelection", "NationalOutcomeSummary",
        "TimeMachine42Targets", "TimeMachineScorecard", "TimeMachineTargetSummary",
        "TimeMachine2026Folds", "TimeMachine2026Summary", "TargetStability2026",
        "PipelineStageSummary", "ValidationStages", "ArchitectureContract",
        "PopularVoteValidation", "PopularVoteMethods", "PopularVoteBridge",
        "SensitivityContract", "SensitivityScenarios", "SensitivityOAT",
        "PopularMethodAudit", "FeatureContract71", "ScenarioExtremes31",
        "ModuleIsolation", "ModuleContract", "HouseRaceDetail", "HouseCompetitive",
        "HouseValidationOOF", "HouseValidationFolds", "HouseValidationSummary",
        "HouseSimulationSummary", "HouseFeatureContract", "HouseLeakageAudit",
        "Block4_ModelQuality", "Block4_Adjustments", "Block4_Disagreement",
        "HistoricalErrors", "PredictionIntervals", "PredictionRanges",
        "MonteCarloSummary", "ControlProbability", "CloseRaceRisk", "MarginSummary",
        "Variability", "ElectoralRisk", "FinalUncertainty", "MonteCarloSample",
        "NationalPremodelContract", "NationalPremodelTuning", "NationalPremodelLatents",
        "NationalPremodelEdges", "NationalPremodelOAT31", "NationalPremodelSupport31",
        "NationalPremodelCombined", "NationalPremodelExamples", "NationalPremodelProvenance",
        "NationalRelationships31", "NationalRelationships14", "Scenario42Coherence",
        "ScenarioSenateSwingAudit", "ScenarioSenateRegression",
        "ScenarioSenateFlipOrder", "ScenarioEngineContract", "ScenarioLabSource", "ScenarioLabColumns",
    ]
    # Explicitly close the workbook after materializing the requested sheets.
    # The cache stores DataFrames, never an open Excel reader/file descriptor.
    with pd.ExcelFile(report) as xls:
        sheet_names = list(xls.sheet_names)
        for s in wanted:
            sheets[s] = _read_optional(xls, s)

    house = sheets["HouseRaceDetail"].copy()
    if not house.empty:
        if "GEOID4" in house.columns:
            # Excel stores the 4-digit identifier as an integer; normalize safely.
            house["GEOID4"] = pd.to_numeric(house["GEOID4"], errors="coerce").round().astype("Int64").astype(str).str.zfill(4)
            house["GEOID4"] = house["GEOID4"].replace("<NA>", "")
        house = _coerce_num(house, [
            "Projected Margin PP", "D Win Probability", "R Win Probability",
            "Expected D Seat Contribution", "PVI D-Signed", "All Source Signed Median",
            "Core3 Signed Median", "District Number", "State FIPS", "GEOID",
        ])

    senate = sheets["SenateRaceDetail"].copy()
    if not senate.empty:
        senate = _coerce_num(senate, [
            "D Poll 2P", "R Poll 2P", "Poll Margin 2P",
            "Raw Predicted Polling Error PP", "Error-Corrected Candidate Margin 2P",
            "Fundamentals Margin 2P", "Projected D 2P", "Projected R 2P",
            "Model Polling Error Correction PP", "Model Projected Margin 2P",
            "Adjusted Margin 2P", "D Win Probability", "R Win Probability",
            "Vulnerability Score", "Forecast Sigma PP", "Historic MAE PP",
        ])

    senate_safe_baselines = sheets["SenateSafeBaselines"].copy()
    if not senate_safe_baselines.empty:
        senate_safe_baselines = _coerce_num(senate_safe_baselines, [
            "PVI D-Signed PP", "Previous Election Year",
            "Previous Winner Vote Share",
            "Previous Winner Margin Proxy D-Signed PP",
            "Scenario Baseline Margin PP", "Scenario Baseline D 2P",
            "Scenario Baseline R 2P", "Scenario Baseline D Win Probability",
            "Scenario Probability Sigma PP",
        ])

    dashboard = _kv(sheets["Dashboard_Data"])
    run_metadata = _kv(sheets["RunMetadata"])
    final_uncertainty = _kv(sheets["FinalUncertainty"])

    return {
        "signature": signature,
        "report_path": report,
        "report_version": _version_key(report, REPORT_RE)[0],
        "sheet_names": sheet_names,
        "sheets": sheets,
        "dashboard": dashboard,
        "run_metadata": run_metadata,
        "final_uncertainty": final_uncertainty,
        "house": house,
        "senate": senate,
        "senate_safe_baselines": senate_safe_baselines,
        "html_path": latest_html_path(),
    }


@lru_cache(maxsize=4)
def load_sheet(signature: str, sheet_name: str) -> pd.DataFrame:
    report = latest_report_path()
    with pd.ExcelFile(report) as xls:
        if sheet_name not in xls.sheet_names:
            return pd.DataFrame()
        return _clean(pd.read_excel(xls, sheet_name=sheet_name))


@lru_cache(maxsize=2)
def load_house_paths(paths_mtime: Optional[int] = None) -> dict[str, Any]:
    if not HOUSE_PATHS_PATH.exists():
        raise FileNotFoundError(f"Missing shared map asset: {HOUSE_PATHS_PATH}")
    with gzip.open(HOUSE_PATHS_PATH, "rt", encoding="utf-8") as fh:
        payload = json.load(fh)
    by_geoid = {str(row["GEOID"]).zfill(4): row for row in payload.get("districts", [])}
    return {"raw": payload, "districts": by_geoid}


@lru_cache(maxsize=2)
def load_house_geojson(paths_mtime: Optional[int] = None) -> Optional[dict[str, Any]]:
    if not HOUSE_GEOJSON_PATH.exists():
        return None
    with gzip.open(HOUSE_GEOJSON_PATH, "rt", encoding="utf-8") as fh:
        return json.load(fh)


def parse_svg_path(path_d: str) -> list[list[tuple[float, float]]]:
    """Parse the project's precomputed M x,y ... Z polygon paths.

    The project path asset is deliberately simple: only M and Z commands with
    absolute coordinate pairs. Returning rings lets Plotly render the exact
    notebook/HTML composite Albers geometry without a basemap dependency.
    """
    rings: list[list[tuple[float, float]]] = []
    for segment in re.findall(r"M([^Z]+)Z", path_d):
        nums = re.findall(r"-?\d+(?:\.\d+)?", segment)
        values = [float(v) for v in nums]
        pts = list(zip(values[0::2], values[1::2]))
        if pts:
            rings.append(pts)
    return rings


def _float_attr(value: Optional[str]) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except ValueError:
        return None


@lru_cache(maxsize=4)
def load_senate_map(signature: str) -> pd.DataFrame:
    """Build the 50-state map solely from structured notebook outputs."""
    bundle = load_bundle(signature)
    senate_map = pd.DataFrame(
        SENATE_STATE_GRID, columns=["STATE", "ABBR", "Grid Row", "Grid Col"]
    )
    senate_map["Tier"] = "None"
    senate_map["D Win Probability"] = math.nan
    senate_map["Projected Margin"] = math.nan
    senate_map["Projected D 2P"] = math.nan
    senate_map["Projected R 2P"] = math.nan
    senate_map["Forecast Rating"] = "No 2026 election"
    senate_map["Forecast Rating Key"] = "None"
    senate_map["Outcome"] = "No 2026 Senate election"
    senate_map["Flip"] = ""
    senate_map["Incumbent Party"] = ""
    senate_map["Projected Winner"] = ""

    # The structured workbook is authoritative wherever it has state-level values.
    monitored = bundle["senate"].copy()
    if not monitored.empty and "STATE" in senate_map.columns:
        lookup = monitored.set_index("STATE")
        for idx, row in senate_map.iterrows():
            state = row.get("STATE")
            if state not in lookup.index:
                continue
            src = lookup.loc[state]
            senate_map.at[idx, "D Win Probability"] = src.get("D Win Probability")
            senate_map.at[idx, "Projected Margin"] = src.get("Adjusted Margin 2P")
            senate_map.at[idx, "Projected D 2P"] = src.get("Projected D 2P")
            senate_map.at[idx, "Projected R 2P"] = src.get("Projected R 2P")
            senate_map.at[idx, "Forecast Rating"] = src.get("Forecast Rating")
            senate_map.at[idx, "Forecast Rating Key"] = src.get("Forecast Rating")
            winner = src.get("Projected Winner")
            incumbent = src.get("INCUMBENT")
            outcome, flip = _senate_outcome(winner, incumbent)
            senate_map.at[idx, "Outcome"] = outcome
            senate_map.at[idx, "Flip"] = flip
            senate_map.at[idx, "Incumbent Party"] = incumbent
            senate_map.at[idx, "Projected Winner"] = winner
            senate_map.at[idx, "Tier"] = "Monitored"

    safe_baselines = bundle["senate_safe_baselines"].copy()
    if not safe_baselines.empty and "STATE" in senate_map.columns:
        safe_lookup = safe_baselines.set_index("State")
        safe_columns = [
            "Official Numeric Forecast", "PVI", "PVI D-Signed PP",
            "Previous Election Year", "Previous Election Type",
            "Previous Winner Party", "Previous Winner Vote Share",
            "Previous Election", "Previous Winner Margin Proxy D-Signed PP",
            "Scenario Baseline Margin PP", "Scenario Baseline D 2P",
            "Scenario Baseline R 2P", "Scenario Baseline D Win Probability",
            "Scenario Probability Sigma PP", "Scenario Baseline Method",
            "PVI and ratings source", "Previous Election Source", "Source As Of",
        ]
        for idx, row in senate_map.iterrows():
            state = row.get("STATE")
            if state not in safe_lookup.index:
                continue
            src = safe_lookup.loc[state]
            if isinstance(src, pd.DataFrame):
                src = src.iloc[0]
            # Safe structural inputs are scenario-only. Official numeric fields
            # stay blank: no artificial 60–40 / ±20 / 99–1 forecast is created.
            senate_map.at[idx, "D Win Probability"] = math.nan
            senate_map.at[idx, "Projected Margin"] = math.nan
            senate_map.at[idx, "Projected D 2P"] = math.nan
            senate_map.at[idx, "Projected R 2P"] = math.nan
            senate_map.at[idx, "Tier"] = "Safe"
            party = str(src.get("Official Party", src.get("Previous Winner Party", ""))).upper()
            senate_map.at[idx, "Forecast Rating"] = f"Safe {party} · unmonitored"
            senate_map.at[idx, "Forecast Rating Key"] = f"Safe {party}"
            senate_map.at[idx, "Outcome"] = (
                "Democratic hold" if party == "D" else "Republican hold" if party == "R" else "Safe"
            )
            for column in safe_columns:
                senate_map.at[idx, column] = src.get(column)
    if len(senate_map) != 50:
        raise AssertionError(f"Structured Senate grid has {len(senate_map)} states; expected 50.")
    if int(senate_map["Tier"].ne("None").sum()) != 35:
        raise AssertionError("Structured Senate grid must contain exactly 35 scheduled elections.")
    return senate_map


def status_payload(signature: str) -> dict[str, Any]:
    b = load_bundle(signature)
    report = b["report_path"]
    html_path = b.get("html_path")
    return {
        "signature": signature,
        "report": report.name,
        "report_mtime": report.stat().st_mtime,
        "report_version": b.get("report_version"),
        "html": Path(html_path).name if html_path else None,
        "model_exists": MODEL_PATH.exists(),
        "house_paths_exists": HOUSE_PATHS_PATH.exists(),
        "house_rows": len(b["house"]),
        "senate_monitored_rows": len(b["senate"]),
        "senate_safe_baseline_rows": len(b["senate_safe_baselines"]),
        "sheets": len(b["sheet_names"]),
    }


def safe_value(value: Any, default: str = "—") -> str:
    if value is None:
        return default
    if isinstance(value, float) and math.isnan(value):
        return default
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return default
    return text
