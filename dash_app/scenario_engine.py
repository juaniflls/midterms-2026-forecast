"""Thin Scenario-Lab runtime loader for Modelo Midterms 2026 v26.

The notebook owns the relationship engine and exports it to
``outputs/scenario_state_engine_v26.py``. Dash is strictly downstream. Before
loading the runtime, this wrapper verifies that the latest v26 report was built
from the same ``Model.xlsx`` snapshot currently present at repository root.
"""
from __future__ import annotations

import hashlib
import importlib.util
import re
import sys
from functools import lru_cache
from pathlib import Path

import pandas as pd

DASH_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = DASH_DIR.parent
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
MODEL_PATH = PROJECT_ROOT / "Model.xlsx"
RUNTIME_PATH = OUTPUTS_DIR / "scenario_state_engine_v26.py"


def _latest_report() -> Path:
    reports = list(OUTPUTS_DIR.glob("Election_Model_Final_Report_v*.xlsx"))
    if not reports:
        raise FileNotFoundError("No audited model report found. Run the v26 notebook first.")
    def key(path: Path):
        m = re.search(r"_v(\d+)\.xlsx$", path.name, re.I)
        return (int(m.group(1)) if m else -1, path.stat().st_mtime_ns)
    return max(reports, key=key)


def _assert_snapshot_sync() -> None:
    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"Missing upstream source: {MODEL_PATH}")
    report = _latest_report()
    with pd.ExcelFile(report) as xls:
        meta = pd.read_excel(xls, sheet_name="RunMetadata")
    if not {"Field", "Value"}.issubset(meta.columns):
        raise RuntimeError("RunMetadata sheet does not expose Field/Value snapshot provenance.")
    mapping = dict(zip(meta["Field"].astype(str), meta["Value"].astype(str)))
    source_sha = mapping.get("Source SHA-256", "").strip()
    current_sha = hashlib.sha256(MODEL_PATH.read_bytes()).hexdigest()
    if not source_sha or source_sha != current_sha:
        raise RuntimeError(
            "Model.xlsx no longer matches the notebook-generated report. "
            "Run the v26 notebook before starting Scenario Lab."
        )


if not RUNTIME_PATH.exists():
    raise FileNotFoundError(
        f"Missing notebook-exported Scenario Lab runtime: {RUNTIME_PATH}. "
        "Run the v26 notebook before starting Dash."
    )
_assert_snapshot_sync()

_spec = importlib.util.spec_from_file_location("midterms_v26_scenario_runtime", RUNTIME_PATH)
if _spec is None or _spec.loader is None:
    raise ImportError(f"Unable to load Scenario Lab runtime from {RUNTIME_PATH}")
_runtime = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _runtime
_spec.loader.exec_module(_runtime)

ENGINE_VERSION = getattr(_runtime, "ENGINE_VERSION", "v26")
INPUT_GROUPS = _runtime.INPUT_GROUPS
LABELS = _runtime.LABELS
COMPOSITION_BATTERIES = _runtime.COMPOSITION_BATTERIES
INTERVENTION_UNITS = _runtime.INTERVENTION_UNITS
CONTROL_TO_UNIT = _runtime.CONTROL_TO_UNIT
ScenarioInput = _runtime.ScenarioInput
NationalStatePremodel = _runtime.NationalStatePremodel
NationalScenarioEngine = _runtime.NationalScenarioEngine
normalize_composition_values = _runtime.normalize_composition_values


@lru_cache(maxsize=2)
def load_scenario_engine(model_path: str, model_mtime_ns: int | None = None):
    _assert_snapshot_sync()
    return _runtime.load_scenario_engine(model_path, model_mtime_ns)
