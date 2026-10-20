"""Rebuild legacy Block 4/5 report filenames from the CURRENT validated v30 Final Report.

Presentation/reporting only: never modifies Model.xlsx, model calculations, or Final Report.
All existing individual reports are archived before publishing the current run.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import os
import re
import shutil
import tempfile
import zipfile


def _sha256(path: Path) -> str:
    d = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            d.update(chunk)
    return d.hexdigest()


def export_current_block45_reports(final_report, output_dir=None):
    """Return a manifest of the regenerated independent reports.

    All numerical tables originate from the FINAL report of the same run.
    Never reads the old Block4/Block5 workbooks as data; never touches Model.xlsx.
    """
    import pandas as pd  # already used by the v30 forecasting notebook

    report = Path(final_report).resolve()
    if not report.is_file():
        raise FileNotFoundError(f"The current Final Report is missing: {report}")
    out = Path(output_dir).resolve() if output_dir else report.parent
    out.mkdir(parents=True, exist_ok=True)
    if report.parent != out:
        raise ValueError('Block 4/5 outputs must share the validated Final Report outputs directory.')
    with zipfile.ZipFile(report) as z:
        if z.testzip() is not None:
            raise ValueError('The Final Report is corrupt; auxiliary exports were not published.')
    digest = _sha256(report)
    report_frames: dict[str, object] = {}
    book = pd.ExcelFile(report)
    required = ('RunMetadata', 'FinalProjection', 'FinalSnapshot', 'PopularVote',
                'ControlSummary', 'HouseDistribution', 'SenateDistribution',
                'TargetStability2026', 'Block4_ModelQuality')
    missing = [s for s in required if s not in book.sheet_names]
    if missing:
        raise ValueError('Current Final Report lacks required sheets: '+', '.join(missing))

    def sheet(name, *, required=False):
        if name not in report_frames:
            if name in book.sheet_names:
                report_frames[name] = pd.read_excel(book, sheet_name=name)
            elif required:
                raise ValueError('Required Final Report sheet missing: ' + name)
            else:
                report_frames[name] = pd.DataFrame({
                    'Export status': ['No rows exported in this current run'],
                    'Requested sheet': [name],
                    'Note': ['Not inferred from any previous report'],
                })
        return report_frames[name]

    meta = sheet('RunMetadata', required=True)
    if not {'Field', 'Value'}.issubset(meta.columns):
        raise ValueError('Current Final Report has no Field/Value provenance contract.')
    meta_values = dict(zip(meta['Field'].astype(str), meta['Value'].astype(str)))
    run_id = next((v for k,v in meta_values.items() if k.lower() in ('run id','run_id')), None)
    if not run_id:
        raise ValueError('Current Final Report lacks a Run ID; no auxiliary exports published.')
    safe_run = re.sub(r'[^a-zA-Z0-9_-]+','-',str(run_id))[:72]
    created = datetime.now(timezone.utc).isoformat()
    stability = sheet('TargetStability2026', required=True)
    if 'Fold Standard Deviation' not in stability.columns:
        raise ValueError('Cannot rank current sensitivity: TargetStability2026 has no Fold Standard Deviation.')
    # Both ranks are *sensitivity* diagnostics, not alternative-model comparisons.
    ranked_high = stability.sort_values('Fold Standard Deviation', ascending=False).head(15).copy()
    ranked_low = stability.sort_values('Fold Standard Deviation', ascending=True).head(15).copy()
    model_quality = sheet('Block4_ModelQuality', required=True)
    adjustments = sheet('Block4_Adjustments')
    latest_summary = sheet('FinalSnapshot', required=True)

    single = {
        'Block4_Diagnostics_v12.xlsx': ('CurrentValidationDiagnostics', model_quality),
        'Block4_Diagnostic_Stability_Summary_v12.xlsx': ('CurrentTargetSensitivity', stability),
        'Block4_Largest_Adjustments_v12.xlsx': ('CurrentConstraintAdjustments', adjustments),
        'Block4_Largest_Alternative_Differences_v12.xlsx': ('CurrentSensitivityRanking', ranked_high),
        'Block4_Lowest_Sensitivity_v12.xlsx': ('CurrentLowestSensitivity', ranked_low),
        'Block5_Control_Summary.xlsx': ('ControlSummary', sheet('ControlSummary', required=True)),
        'Block5_Election_Snapshot.xlsx': ('FinalSnapshot', latest_summary),
        'Block5_House_Distribution.xlsx': ('HouseDistribution', sheet('HouseDistribution', required=True)),
        'Block5_Largest_Adjustments.xlsx': ('CurrentConstraintAdjustments', adjustments),
        'Block5_Largest_Disagreements.xlsx': ('CurrentSensitivityRanking', ranked_high),
        'Block5_Least_Stable.xlsx': ('CurrentSensitivityRanking', ranked_high),
        'Block5_Model_Stability_Summary.xlsx': ('CurrentTargetSensitivity', stability),
        'Block5_Most_Stable.xlsx': ('CurrentLowestSensitivity', ranked_low),
        'Block5_Popular_Vote.xlsx': ('PopularVote', sheet('PopularVote', required=True)),
        'Block5_Projection_Reliability.xlsx': ('CurrentHistoricalErrors', model_quality),
        'Block5_Senate_Distribution.xlsx': ('SenateDistribution', sheet('SenateDistribution', required=True)),
    }
    report_tabs = {
        'Snapshot': latest_summary,
        'Popular Vote': sheet('PopularVote'),
        'Control Summary': sheet('ControlSummary'),
        'House Distribution': sheet('HouseDistribution'),
        'Senate Distribution': sheet('SenateDistribution'),
        'Reliability': model_quality,
        'Stability Summary': stability,
        'Largest Adjustments': adjustments,
        'Model Disagreement': ranked_high,
        'Most Stable': ranked_low,
        'Least Stable': ranked_high,
    }
    notes = {
        'Block4_Largest_Alternative_Differences_v12.xlsx':
            'Historical filename retained for familiarity: current data rank Fold Standard Deviation (sensitivity), NOT alternative-model differences.',
        'Block5_Largest_Disagreements.xlsx':
            'Historical filename retained: current data rank Fold Standard Deviation; do NOT interpret as disagreement between fitted models.',
        'Block5_Projection_Reliability.xlsx':
            'Current national cross-validation errors; not calibrated probabilities of correctness.',
        'Block5_Model_Stability_Summary.xlsx':
            'Current target sensitivity; the overall 0–100 diagnostic score remains in FinalSnapshot.',
    }
    entries = list(single)+['Block5_Election_Projection_Report.xlsx']
    rows=[]
    # Stage ALL workbooks, check their internal ZIP integrity, then touch outputs.
    scratch=Path(tempfile.mkdtemp(prefix='n42_block45_stage_'))
    try:
        for filename in entries:
            path=scratch/filename
            frames=report_tabs if filename=='Block5_Election_Projection_Report.xlsx' else {single[filename][0]: single[filename][1]}
            provenance=pd.DataFrame([
                {'Field':'Run ID', 'Value':run_id},
                {'Field':'Final Report', 'Value':report.name},
                {'Field':'Final Report SHA256', 'Value':digest},
                {'Field':'Generated UTC', 'Value':created},
                {'Field':'Input contract', 'Value':'Consolidated Final Report from this run; no archived inputs'},
                {'Field':'Metric clarification', 'Value':notes.get(filename,'Current v30 diagnostic/reporting view')},
            ])
            with pd.ExcelWriter(path,engine='openpyxl') as writer:
                for tab,df in frames.items():
                    # Valid Excel sheet names (<=31 chars); zero rows remain explicit.
                    df.to_excel(writer,sheet_name=tab[:31],index=False)
                meta.to_excel(writer,sheet_name='RunMetadata',index=False)
                provenance.to_excel(writer,sheet_name='ExportProvenance',index=False)
            with zipfile.ZipFile(path) as z:
                if z.testzip(): raise ValueError(f'Corrupt generated report: {filename}')
            rows.append({'File':filename,'Run ID':str(run_id),'Final Report SHA256':digest,
                         'Generated UTC':created,'Tables':'; '.join(frames),'Status':'GENERATED FROM CURRENT FINAL REPORT'})
        archive=out/'archive'/'block45_previous_runs'/('archived_before_'+safe_run)
        # Archive preexisting individual outputs *before* replacing them.
        # On first run this also quarantines historical v12 files left in outputs.
        if any((out/name).is_file() for name in entries):
            archive.mkdir(parents=True,exist_ok=True)
            # Run-ID collisions are safe: suffix if rerunning the same report.
            if any((archive/name).exists() for name in entries):
                archive=archive.parent/('archived_before_'+safe_run+'-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
                archive.mkdir(parents=True,exist_ok=True)
            for name in entries:
                current=out/name
                if current.is_file():
                    shutil.move(str(current),str(archive/name))
        for filename in entries:
            staged_copy=out/('.'+filename+'.staging')
            try:
                shutil.copyfile(scratch/filename,staged_copy)
                os.replace(staged_copy,out/filename)
            finally:
                staged_copy.unlink(missing_ok=True)
        manifest=out/'Block45_Export_Manifest.csv'
        temporary=out/'.Block45_Export_Manifest.csv.staging'
        try:
            pd.DataFrame(rows).to_csv(temporary,index=False)
            os.replace(temporary,manifest)
        finally:
            temporary.unlink(missing_ok=True)
        print(f'BLOQUES 4/5 — {len(entries)} Excel auxiliares regenerados desde Final Report; Run ID: {run_id}')
        print('Final Report SHA256:',digest)
        print('Manifest:',manifest)
        return rows
    finally:
        shutil.rmtree(scratch,ignore_errors=True)
