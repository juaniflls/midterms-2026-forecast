"""Offline enrichment. External forecast outputs never enter NUCLEUS predictions."""
from __future__ import annotations
import base64, hashlib, html, json, re, unicodedata, os
from pathlib import Path
import numpy as np
import pandas as pd
from PIL import Image

SOURCE_URL=''  # Per-file original attribution is preserved in data/race_assets/SOURCE_PROVENANCE.md

def clean(value):
    if isinstance(value, dict): return {str(k):clean(v) for k,v in value.items()}
    if isinstance(value, (list,tuple)): return [clean(v) for v in value]
    if isinstance(value, (np.integer,)): return int(value)
    if isinstance(value, (np.floating,float)): return float(value) if np.isfinite(value) else None
    if isinstance(value, (np.bool_,)):return bool(value)
    if value is pd.NA:return None
    return value

def norm(value):
    return re.sub(r'[^a-z0-9]','',unicodedata.normalize('NFKD',str(value)).encode('ascii','ignore').decode().lower())

def records(frame): return clean(frame.replace({np.nan:None}).to_dict('records'))

def number(value, default=None):
    try:return float(value) if np.isfinite(float(value)) else default
    except (ValueError,TypeError):return default

def build_racecards(root:Path, html_path:Path, report_path:Path):
    root=Path(root); ei=root/'data/race_assets'; out=root/'outputs/enrichment'; out.mkdir(parents=True,exist_ok=True)
    def read(name):return pd.read_csv(ei/(name+'.csv'))
    races=read('races').fillna(''); candidates=read('candidates').fillna('')
    metadata=read('candidate_meta').fillna(''); overrides=read('candidate_photo_overrides').fillna('')
    demo=read('demographics'); historical=read('historical'); funds=read('fundraising')
    assert races.race_code.is_unique and demo.district_code.is_unique
    # Display-only candidate polling snapshot from the selected saved workbook.
    # These are provider averages, NOT modeled candidate vote shares and never
    # enter the forecast engine. Only applicable to NE (R/I) and MT (D/R/I).
    poll_snapshot = {}
    workbook_path = Path(os.environ.get('MIDTERMS_MODEL_FILE') or (root/'Model.xlsx'))
    try:
        from openpyxl import load_workbook
        wb = load_workbook(workbook_path, read_only=True, data_only=True)
        sp = wb['Senate Parser']
        for race, refs in {'MT-SEN':{'dem':'M90','rep':'N90','ind':'O90'},
                           'NE-SEN':{'ind':'D13','rep':'E13'}}.items():
            vals={}
            for party,addr in refs.items():
                raw=number(sp[addr].value)
                if raw is not None and 0 <= raw <= 1:vals[party] = round(raw*100, 3)
            if len(vals)==len(refs):poll_snapshot[race]=vals
        wb.close()
    except (OSError, KeyError, ValueError) as exc:
        print(f'[display only] Candidate polling context unavailable: {type(exc).__name__}: {exc}')
    book=pd.ExcelFile(report_path)
    house=pd.read_excel(book,'HouseRaceDetail'); senate=pd.read_excel(book,'SenateRaceDetail')
    assert len(house)==435 and house['District ID'].is_unique
    assert len(senate)==35 and senate['State Abbr'].is_unique
    race_index=races.set_index('race_code'); candidate_index=candidates.set_index('cand_id')
    dem_index=demo.set_index('district_code'); fund_index=funds.set_index('race_code')
    history_index=historical.set_index('code'); photo_audit=[]; enriched=[]; candidate_rows=[]
    dem_columns=[c for c in demo if c not in ['district_code','state','district']]
    # State sums are explicitly derived, not independent state observations.
    state_demo=demo.groupby('state')[dem_columns].sum()
    group_specs=[]
    label_map={'vap_white':'White','vap_hispanic':'Hispanic origin','vap_black':'Black','vap_asian':'Asian','vap_native':'American Indian / Alaska Native','vap_pacific':'Pacific Islander',
               'educ_no_hs':'No high-school diploma','educ_hs':'High-school diploma','educ_some_college':'Some college','educ_associate':'Associate degree','educ_bachelor':'Bachelor degree','educ_master':'Master degree','educ_professional':'Professional degree','educ_doctorate':'Doctorate',
               'age_80_plus':'Age 80+'}
    for col in dem_columns:
        if col=='vap_total':continue
        family='race / origin' if col.startswith('vap_') else ('age' if col.startswith('age_') else ('education' if col.startswith('educ_') else 'household income'))
        label=label_map.get(col,col.replace('age_','Age ').replace('inc_','Income ').replace('_','–'))
        group_specs.append({'key':col,'label':label,'family':family})
    dictionaries=[]
    for path in sorted(ei.glob('*.csv')):
        try:df=pd.read_csv(path,comment='#')
        except pd.errors.ParserError as exc:
            dictionaries.append({'file':path.name,'column':'UNPARSED SOURCE','dtype':'raw archive','non_null':None,'rows':None,'role':'QUARANTINED: malformed CSV; retained unchanged; not a model input','parse_issue':str(exc)})
            continue
        role=('archive: state legislature / outside current forecast' if path.stem.startswith('leg_') else
              'presentation: candidate identity and source metadata' if path.stem in ['races','candidate_meta','candidate_photo_overrides','candidates'] else
              'research/context: source observations; not newly activated as predictors')
        for col in df.columns:
            dictionaries.append({'file':path.name,'column':col,'dtype':str(df[col].dtype),'non_null':int(df[col].notna().sum()),'rows':len(df),'role':role})
    def candidate(code, slot, name, party, cid='', status=''):
        if not name or str(name).startswith('('):return None
        choices=metadata[(metadata.race_code.eq(code)) & metadata.slot.eq(slot) & metadata.name.map(norm).eq(norm(name))]
        ov=overrides[(overrides.race_code.eq(code)) & overrides.slot.eq(slot) & overrides.name.map(norm).eq(norm(name))]
        meta=choices.iloc[-1].to_dict() if len(choices) else {}
        override=ov.iloc[-1].to_dict() if len(ov) else {}
        picture=ei/'photos'/f'{code}-{slot}.jpg'; uri=None; photo_status='not supplied / identity not matched'
        if picture.exists() and (meta or override):
            with Image.open(picture) as im:
                mime=Image.MIME.get(im.format,'image/jpeg')
                im.verify()
            uri='data:'+mime+';base64,'+base64.b64encode(picture.read_bytes()).decode()
            photo_status='source name + race + slot matched'
        fec_id=''
        if cid and cid in candidate_index.index:
            crow=candidate_index.loc[cid]
            if norm(crow['name'])==norm(name):fec_id=str(crow['fec_id'])
        row={'race_code':code,'slot':slot,'name':str(name),'party':str(party),'candidate_id':cid,'fec_id':fec_id,'nomination_status':status,
             'photo_file':str(picture.relative_to(root)) if uri else None,'photo_status':photo_status,
             'photo_source_url':override.get('image_url') or meta.get('image_url') or '',
             'profile_url':override.get('source_page') or meta.get('page_url') or '',
             'description':meta.get('description',''),'photo_note':override.get('note',''),
             'rights_status':'source links retained; individual image licence not established by supplied archive'}
        photo_audit.append(row.copy()); candidate_rows.append(row.copy())
        # The full provenance/identity audit stays in outputs/enrichment/PhotoAudit.csv.
        # Public HTML embeds only fields actually used by the Race Cards.
        return {'slot':slot, 'name':str(name), 'party':str(party), 'image':uri}
    def composition(row):
        if row is None:return {'raw':{},'shares':{},'notes':['No composition record supplied.']}
        raw={c:number(row[c]) for c in dem_columns};shares={}
        for spec in group_specs:
            k=spec['key']
            denominator=raw['vap_total'] if k.startswith('vap_') else sum(v for c,v in raw.items() if c.startswith(k.split('_')[0]+'_') and v is not None)
            shares[k]=raw[k]/denominator if raw[k] is not None and denominator and denominator>0 else None
        return {'raw':raw,'shares':shares,'notes':[
            'Race / origin are separate source categories, can overlap, and are never added into a partition.',
            'Age shares use only supplied 20+ bins. Education shares use recorded attainment counts. Income shares describe households, not voters.',
            'Source vintage and detailed Census universe not supplied per record; shares are descriptive proxies.'
        ]}
    for chamber, frame in [('House',house),('Senate',senate)]:
        for _,row in frame.iterrows():
            state=str(row['State Abbr']); model_code=str(row['District ID']) if chamber=='House' else state+'-SEN'
            code=model_code.replace('-AL','-01') if model_code.endswith('-AL') else model_code
            if code not in race_index.index:raise ValueError('Unmapped race: '+code)
            ext=race_index.loc[code].to_dict(); field=[]
            for slot in ['dem','rep','ind']:
                c=candidate(code,slot,ext.get(slot+'_name',''),ext.get(slot+'_party_label') or ext.get(slot+'_party') or ('IND' if slot=='ind' else slot.upper()),ext.get(slot+'_id',''),ext.get(slot+'_status',''))
                if c: field.append(c)
            if ext.get('same_party') and ext.get('cand2_name'):
                slot='dem2' if ext['same_party']=='DEM' else 'rep2'
                c=candidate(code,slot,ext['cand2_name'],ext['same_party'],ext.get(slot+'_id',''),'source top-two candidate')
                if c:field.append(c)
            baseline_names={'dem':str(row.get('Democratic Candidate','')),'rep':str(row.get('Republican Candidate',''))} if chamber=='House' else {}
            conflicts=[f"{s}: workbook {baseline_names[s]} / enrichment {ext.get(s+'_name','')}" for s in baseline_names if baseline_names[s] not in ['', 'nan'] and norm(baseline_names[s])!=norm(ext.get(s+'_name',''))]
            special=[]
            if ext.get('same_party'):special.append('Same-party top-two: NUCLEUS D/R probabilities are not individual candidate probabilities.')
            if ext.get('rcv'):special.append('Ranked-choice field: party probabilities do not resolve every individual candidate.')
            if ext.get('threeway'):special.append('Independent / three-way field: candidate probabilities are not inferred from D/R probabilities.')
            if conflicts:special.append('Candidate snapshot differs from predictive workbook; labels are context from the newer archive.')
            drow=dem_index.loc[code] if chamber=='House' else state_demo.loc[state]
            hkey=code if chamber=='House' else state
            hist=history_index.loc[hkey].to_dict() if hkey in history_index.index else {}
            financing=fund_index.loc[code].to_dict() if code in fund_index.index else {}
            model={'margin':number(row.get('Projected Margin PP',row.get('Final Margin PP'))),
                   'pD':number(row['D Win Probability']),'pR':number(row['R Win Probability']),
                   'winner':str(row.get('Projected Winner','')),'rating':str(row['Forecast Rating']),
                   'engine':str(row.get('Source Engine','HOUSE COMPOSITE')),'poll_count':number(row.get('VoteHub Poll Count')),
                   'fundamentals_weight':number(row.get('Fundamentals Weight')),'ratings_weight':number(row.get('Ratings Weight')),'polling_weight':number(row.get('Polling Weight')),
                   'pvi':number(row.get('PVI D-Signed')),'incumbent':str(row.get('Incumbent Name','')),
                   'monitored':bool(row.get('Monitored',False))}
            assert model['pD'] is not None and model['pR'] is not None and abs(model['pD']+model['pR']-100)<1e-6
            enriched.append({'id':model_code,'sourceRaceCode':code,'state':state,'chamber':chamber,'label':str(row.get('District Label',row.get('State',code))),
                             'candidates':field,'model':model,'composition':composition(drow),'history':clean(hist),'finance':clean(financing),
                             'field':{k:clean(ext.get(k)) for k in ['same_party','rcv','threeway','ind_caucus','incumbent_party']},'pollSnapshot':poll_snapshot.get(model_code), 'notes':special,'candidate_conflicts':conflicts})
    # Polls are context-only, with matchup matching and per-poll dates. No provider rating enters the engine.
    polls=[]
    all_polls=pd.concat([read('race_polls').assign(input_file='race_polls.csv'),read('manual_race_polls').assign(input_file='manual_race_polls.csv')],ignore_index=True)
    for _,row in all_polls.iterrows():
        code=str(row.get('race_code',''))
        if code not in race_index.index:continue
        ext=race_index.loc[code]
        match=all(norm(row.get(k+'_name',''))==norm(ext.get(k+'_name','')) and norm(row.get(k+'_name','')) for k in ['dem','rep'])
        polls.append({'race':code,'pollster':str(row.get('pollster','')),'date':str(row.get('end_date','')),'n':number(row.get('n')),'dem':number(row.get('dem')),'rep':number(row.get('rep')),'margin':number(row.get('margin')),'dem_name':str(row.get('dem_name','')),'rep_name':str(row.get('rep_name','')),'matchup_match':bool(match),'source_file':str(row['input_file'])})
    polls=pd.DataFrame(polls).drop_duplicates(subset=['race','pollster','date','n','dem','rep','dem_name','rep_name'])
    demo_audit=demo[['district_code','vap_total']].copy()
    demo_audit['category_sum']=demo.filter(regex='^vap_(?!total)').sum(axis=1)
    demo_audit['sum_exceeds_vap']=demo_audit.category_sum.gt(demo_audit.vap_total)
    demo_audit['production_status']='DESCRIPTIVE ONLY — overlapping categories, universe/vintage/geography evidence incomplete'
    inventory=[]
    for path in sorted(ei.iterdir()):
        if not path.is_file():continue
        role=next((d['role'] for d in dictionaries if d['file']==path.name),'source documentation / provider parameters, archived')
        inventory.append({'file':path.name,'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'role':role,'received_date':'2026-10-10','source_observation_date':'not established per file','source_url':SOURCE_URL})
    for name, df in [('CandidateProfiles',pd.DataFrame(candidate_rows)),('PhotoAudit',pd.DataFrame(photo_audit)),('DemographicQuality',demo_audit),('DataDictionary',pd.DataFrame(dictionaries)),('SourceInventory',pd.DataFrame(inventory)),('ExternalPolls',polls),('Demographics',demo),('HistoricalContext',historical),('Fundraising',funds)]:
        df.to_csv(out/f'{name}.csv',index=False)
    flat=[]
    for r in enriched:
        flat.append({'race_code':r['id'],'chamber':r['chamber'],'state':r['state'],'label':r['label'],**{k:v for k,v in r['model'].items()},
                     'candidate_names':' / '.join(c['name'] for c in r['candidates']),'field_notes':' | '.join(r['notes']),'conflict_count':len(r['candidate_conflicts'])})
    pd.DataFrame(flat).to_csv(out/'RaceProfiles.csv',index=False)
    projection=pd.read_excel(book,'FinalProjection')
    fixed_d=int(projection.loc[projection.Chamber.eq('Senate'),'Democratic Seats'].iloc[0])-int((senate['Projected Winner']=='D').sum())
    fixed_r=65-fixed_d
    payload={'races':enriched,'polls':records(polls),'groups':group_specs,'sources':inventory,'fixedD':fixed_d,'fixedR':fixed_r,
             'counts':{'House':435,'Senate':35,'photoMatched':sum(bool(r['photo_file']) for r in photo_audit),'photoMissing':sum(not bool(r['photo_file']) for r in photo_audit),'demographicDistricts':int(len(dem_index)),'demographicCategoryOverlapRows':int(demo_audit.sum_exceeds_vap.sum()),'candidateConflicts':sum(bool(r['candidate_conflicts']) for r in enriched)},
             'dataAsOf':'2026-10-06','enrichmentReceived':'2026-10-10','dataMode':__import__('os').environ.get('NUCLEUS_DATA_MODE','snapshot')}
    # A plain JSON copy excludes embedded pictures; original photos travel in the package.
    lite=clean(payload)
    lite=json.loads(json.dumps(lite))
    for r in lite['races']:
        for c in r['candidates']:c.pop('image',None)
    (out/'racecard_data.json').write_text(json.dumps(lite,ensure_ascii=False,indent=2),encoding='utf-8')
    text=Path(html_path).read_text(encoding='utf-8')
    text=re.sub(r'<!-- N42_(?:V31|RACECARDS)_BEGIN -->.*?<!-- N42_(?:V31|RACECARDS)_END -->','',text,flags=re.S)
    text=re.sub(r'<style id="(?:n42-v31|n42-racecards)-style">.*?</style>','',text,flags=re.S)
    style=(root/'nucleus42_visual/interface.css').read_text()
    interface=(root/'nucleus42_visual/interface.html').read_text()
    script=(root/'nucleus42_visual/interface.js').read_text()
    if text.count('</head>') != 1 or text.count('<footer class="footer">') != 1:
        raise ValueError('HTML base incompatible: missing or duplicate visual insertion anchors.')
    text=text.replace('</head>','<style id="n42-racecards-style">'+style+'</style>\n</head>',1)
    encoded=json.dumps(clean(payload),ensure_ascii=False,separators=(',',':')).replace('</','<\\/')
    addition='<!-- N42_RACECARDS_BEGIN -->'+interface+'\n<script type="application/json" id="n42RaceData">'+encoded+'</script>\n<script>'+script+'</script><!-- N42_RACECARDS_END -->'
    text=text.replace('<footer class="footer">',addition+'\n<footer class="footer">',1)
    Path(html_path).write_text(text,encoding='utf-8')
    checks=[{'check':'House identity coverage','passed':len([r for r in enriched if r['chamber']=='House'])==435},
            {'check':'Senate identity coverage','passed':len([r for r in enriched if r['chamber']=='Senate'])==35},
            {'check':'Unique race keys','passed':len({r['id'] for r in enriched})==470},
            {'check':'Party probability sums','passed':all(abs(r['model']['pD']+r['model']['pR']-100)<1e-6 for r in enriched)},
            {'check':'Finite central margins','passed':all(r['model']['margin'] is not None for r in enriched)},
            {'check':'Demographic zero-shift recovers central totals','passed':int((house['Projected Winner']=='D').sum())==int(projection.loc[projection.Chamber.eq('House'),'Democratic Seats'].iloc[0])},
            {'check':'External forecast output excluded from predictor inputs','passed':not (ei/'output').exists()},
            {'check':'Photos source identity matched or explicit placeholder','passed':all(r['photo_status'] in ['source name + race + slot matched','not supplied / identity not matched'] for r in photo_audit)}]
    audit=pd.DataFrame(checks);audit.to_csv(out/'EnrichmentChecks.csv',index=False)
    if not audit.passed.all():raise AssertionError('n42rc enrichment contract failed')
    print('Complete race-profile enrichment:',json.dumps(payload['counts']))
    print('Forecast outputs preserved. Demographic variables are descriptive / sensitivity inputs, not newly fitted predictors.')
    return audit
