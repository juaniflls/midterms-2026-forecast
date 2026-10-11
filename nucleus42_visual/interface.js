/* n42rc offline race profiles. All displayed forecast numbers come from the report. */
(()=>{
 'use strict';
 const D=JSON.parse(document.getElementById('n42RaceData').textContent), $=id=>document.getElementById(id), esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])), idx=new Map(D.races.map(r=>[r.id,r]));
 const fmt=(v,n=1)=>Number.isFinite(v)?v.toFixed(n):'Not supplied', margin=v=>Number.isFinite(v)?`${v>=0?'D':'R'} +${Math.abs(v).toFixed(1)}`:'Not estimated', chance=v=>`${fmt(v)}%`;
 const safeLink=u=>{try{const p=new URL(u);return p.protocol==='https:'||p.protocol==='http:'?esc(u):'';}catch{return '';}};
 const portrait=c=>c.image?`<img class="n42rc-avatar" src="${c.image}" alt="${esc(c.name)} · source portrait" loading="lazy">`:`<span class="n42rc-avatar n42rc-initials" aria-label="Portrait not supplied">${esc(c.name.split(/\s+/).map(v=>v[0]).slice(0,2).join(''))}</span>`;
 const partyOf=c=>{const raw=String(c.party||'').toUpperCase();return c.slot==='ind'||raw==='IND'||raw==='INDEPENDENT'?'I':raw==='REP'||raw==='REPUBLICAN'?'R':raw==='DEM'||raw==='DEMOCRATIC'?'D':'O'};
 const partyClass=c=>({D:'n42rc-dem',R:'n42rc-rep',I:'n42rc-ind',O:'n42rc-ind'})[partyOf(c)];
 const displayCandidates=r=>{
  if(r.id==='MT-SEN')return ['dem','rep','ind'].map(k=>r.candidates.find(c=>c.slot===k)).filter(Boolean);
  if(['ID-SEN','NE-SEN','SD-SEN'].includes(r.id))return ['rep','ind'].map(k=>r.candidates.find(c=>c.slot===k)).filter(Boolean);
  const major=r.candidates.filter(c=>['dem','rep','dem2','rep2'].includes(c.slot));return major.slice(0,2);
 };
 const person=c=>`<div class="n42rc-person">${portrait(c)}<div><div class="n42rc-name ${partyClass(c)}"><span class="n42rc-party-tag ${partyClass(c)}">${partyOf(c)}</span> ${esc(c.name)}</div></div></div>`;
 // UI-only correspondence: these source records have no DEM nominee, but do
 // have an independent who faces the Republican. Never change r.model fields.
 const independentVsRepublican=r=>['ID-SEN','NE-SEN','SD-SEN'].includes(r.id)
   && !r.candidates.some(c=>c.slot==='dem')
   && r.candidates.some(c=>c.slot==='rep')&&r.candidates.some(c=>c.slot==='ind');
 const displayedSide=(r,c)=>{
  if(partyOf(c)==='R')return 'R';
  if(partyOf(c)==='D')return 'D';
  if(partyOf(c)==='I'&&independentVsRepublican(r))return 'D';
  return null;
 };
 const hasTwoSidedMatchup=r=>{
  const cs=displayCandidates(r);
  return cs.length===2&&cs.filter(c=>displayedSide(r,c)==='D').length===1
      &&cs.filter(c=>displayedSide(r,c)==='R').length===1;
 };
 const individualModelAvailable=(r,c)=>hasTwoSidedMatchup(r)&&displayedSide(r,c)!==null;
 const candidateProbability=(r,c)=>{
  const side=displayedSide(r,c);
  if(individualModelAvailable(r,c))return chance(side==='D'?r.model.pD:r.model.pR);
  // A three-candidate field needs a separate calibrated three-way model.
  // Even where R=100% to one decimal, do not invent three probabilities.
  return '—';
 };
 const twoPartyShare=(r,c)=>{
  const side=displayedSide(r,c);
  return individualModelAvailable(r,c)&&Number.isFinite(r.model.margin)
     ?chance((100+(side==='D'?1:-1)*r.model.margin)/2):'—';
 };
 const displayRating=r=>independentVsRepublican(r)?String(r.model.rating).replace(/^D(?=\s|$)/,'I'):r.model.rating;
 const displayMargin=r=>independentVsRepublican(r)&&Number.isFinite(r.model.margin)&&r.model.margin>=0
   ?`I +${Math.abs(r.model.margin).toFixed(1)}`:margin(r.model.margin);
 const displayRatingColor=r=>independentVsRepublican(r)&&r.model.winner==='D'?'n42rc-ind':(r.model.winner==='D'?'n42rc-dem':'n42rc-rep');
 const displayMarginColor=r=>independentVsRepublican(r)&&r.model.margin>=0?'n42rc-ind':(r.model.margin>=0?'n42rc-dem':'n42rc-rep');
 const ordinal=n=>{const k=n%100;return n+(k>=11&&k<=13?'th':({1:'st',2:'nd',3:'rd'}[n%10]||'th'));};
 const raceTitle=r=>{
  if(r.chamber==='Senate')return `${r.label} Senate Forecast`;
  const m=String(r.label).match(/^(.*)\s+(\d+)$/);
  if(m)return `${m[1]} ${ordinal(Number(m[2]))} District Forecast`;
  if(/at.?large/i.test(r.label)||r.id.endsWith('-AL'))return `${r.state} At-Large House Forecast`;
  return `${r.label} House Forecast`;
 };
 const observedPct=(r,c)=>{const v=r.pollSnapshot?.[c.slot];return Number.isFinite(v)?chance(v):null;};
 const candidateVoteStat=(r,c)=>{
  if(individualModelAvailable(r,c)&&Number.isFinite(r.model.margin))return ['Implied vote share',twoPartyShare(r,c),independentVsRepublican(r)?'Implied two-side share: independent is displayed in place of the model D side, unchanged mathematically':'Implied two-party share calculated from the model margin; not a multi-party ballot forecast'];
  const v=observedPct(r,c);
  if(v!==null)return ['Observed polling avg.',v,'Saved Senate Parser mean; not NUCLEUS projected vote share'];
  return ['Projected vote share','—','Not modeled for this candidate; do not infer from party probability'];
 };
 const candidateProfile=(r,c)=>{
  const vote=candidateVoteStat(r,c);
  return `<article class="n42rc-profile ${partyClass(c)}">${portrait(c)}<h3 class="${partyClass(c)}"><span class="n42rc-party-tag ${partyClass(c)}">${partyOf(c)}</span> ${esc(c.name)}</h3><div class="n42rc-candidate-stats n42rc-two-metrics"><div title="Existing model-side probability. In R/I contests, the D-side is displayed as I without changing the forecast."><span>Chance of winning</span><b class="${partyClass(c)}">${candidateProbability(r,c)}</b></div><div title="${esc(vote[2])}"><span>${esc(vote[0])}</span><b class="${partyClass(c)}">${vote[1]}</b></div></div></article>`;
 };
 const raceSummary=r=>`<div class="n42rc-race-summary" aria-label="Race-wide central rating and margin"><div><span>Race rating</span><strong class="${displayRatingColor(r)}">${esc(displayRating(r))}</strong></div><div><span>Central race margin</span><strong class="${displayMarginColor(r)}">${displayMargin(r)}</strong></div></div>`;
 
 const bar=r=>{
  const indyAligned=independentVsRepublican(r);
  return `<div class="n42rc-prob"><span class="${indyAligned?'n42rc-prob-ind':''}" style="width:${r.model.pD}%"></span><span style="width:${r.model.pR}%"></span></div><div class="n42rc-prob-caption"><span class="${indyAligned?'n42rc-ind':'n42rc-dem'}">${indyAligned?'I win probability':'D model'} ${chance(r.model.pD)}</span><span class="n42rc-rep">R model ${chance(r.model.pR)}</span></div>`;
 };
 const mainPeople=r=>displayCandidates(r);
 const card=r=>`<button class="n42rc-race" data-n42rc-open="${esc(r.id)}" aria-label="Open ${esc(r.id)} candidate profile"><div class="n42rc-card-head"><div><h3>${esc(r.id)}</h3><div class="n42rc-muted">${esc(r.label)}</div></div><span class="n42rc-chip">${esc(displayRating(r))}</span></div><div class="n42rc-matchup">${mainPeople(r).map(person).join('')}</div>${bar(r)}<div class="n42rc-stage-caption">Central margin ${displayMargin(r)}${r.notes.length?' · field notes available':''}</div></button>`;
 let page=0,filtered=[],activeRace=null;
 for(const s of [...new Set(D.races.map(r=>r.state))].sort())$('n42rcState').insertAdjacentHTML('beforeend',`<option value="${s}">${s}</option>`);
 function render(){
  const q=$('n42rcSearch').value.trim().toLowerCase(),ch=$('n42rcChamber').value,st=$('n42rcState').value,group=$('n42rcGroup').value;
  filtered=D.races.filter(r=>(ch==='all'||r.chamber===ch)&&(st==='all'||r.state===st)&&(!q||`${r.id} ${r.label} ${r.candidates.map(c=>c.name).join(' ')}`.toLowerCase().includes(q))&&(group==='all'||group==='competitive'&&r.model.pD>=20&&r.model.pD<=80||group==='special'&&(r.field.same_party||r.field.rcv||r.field.threeway)||group==='photos'&&r.candidates.some(c=>c.image)));
  const order=$('n42rcOrder').value;filtered.sort((a,b)=>order==='district'?a.id.localeCompare(b.id):order==='dem'?b.model.pD-a.model.pD:Math.abs(a.model.pD-50)-Math.abs(b.model.pD-50));
  const pages=Math.max(1,Math.ceil(filtered.length/12));page=Math.min(page,pages-1);
  $('n42rcRaceGrid').innerHTML=filtered.length?filtered.slice(page*12,page*12+12).map(card).join(''):'<div class="n42rc-empty">No races match these filters.</div>';
  $('n42rcResultCount').textContent=`${filtered.length} of 470 races · ${D.counts.photoMatched} matched portraits in the package`;
  $('n42rcPage').textContent=`Page ${page+1} of ${pages}`;$('n42rcPrev').disabled=page===0;$('n42rcNext').disabled=page>=pages-1;
 }
 for(const id of ['n42rcSearch','n42rcChamber','n42rcState','n42rcGroup','n42rcOrder'])$(id).addEventListener('input',()=>{page=0;render()});
 $('n42rcPrev').addEventListener('click',()=>{page--;render()});$('n42rcNext').addEventListener('click',()=>{page++;render()});
 function csv(rows,name){if(!rows.length)return;const keys=Object.keys(rows[0]),cell=v=>`"${String(v??'').replace(/"/g,'""')}"`,str=[keys.map(cell).join(','),...rows.map(r=>keys.map(k=>cell(r[k])).join(','))].join('\r\n'),url=URL.createObjectURL(new Blob(['\uFEFF'+str],{type:'text/csv;charset=utf-8'})),a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
 $('n42rcExport').addEventListener('click',()=>csv(filtered.map(r=>({race:r.id,chamber:r.chamber,candidates:displayCandidates(r).map(c=>c.name).join(' / '),d_model_win_probability_pct:r.model.pD,r_model_win_probability_pct:r.model.pR,central_margin_pp:r.model.margin,rating:r.model.rating,forecast_input_date:D.dataAsOf,candidate_archive_received:D.enrichmentReceived,field_notes:r.notes.join(' | ')})),'nucleus42-n42rc-filtered-races.csv'));
 function demographicBars(r,family){return D.groups.filter(g=>g.family===family).map(g=>{const v=r.composition.shares[g.key];return `<div><div class="n42rc-bar-label"><span>${esc(g.label)}</span><b>${v===null||v===undefined?'Not supplied':fmt(100*v)+'%'}</b></div><div class="n42rc-track"><i class="n42rc-group-color-${D.groups.filter(x=>x.family===family).findIndex(x=>x.key===g.key)%8}" style="width:${Math.min(100,Math.max(0,100*(v||0)))}%"></i></div></div>`}).join('');}
 function profile(r){
  activeRace=r;
  const profiles=displayCandidates(r).map(c=>candidateProfile(r,c)).join('');
  const line=(l,v)=>`<div class="n42rc-statline"><span>${esc(l)}</span><b>${esc(v)}</b></div>`;
  $('n42rcDialogTitle').textContent=raceTitle(r);
  $('n42rcRaceDetail').innerHTML=`<div class="n42rc-people">${profiles}</div>${raceSummary(r)}${bar(r)}<p class="n42rc-footnote">Forecast inputs ${D.dataAsOf}. ${independentVsRepublican(r)?'Display-only: the model D-side results are labeled Independent (I) for this R/I matchup. The original model is unchanged. Implied vote is a two-side share, not a multi-party ballot estimate.':'Independent three-way outcomes require candidate-specific modeling; any displayed polling averages are observed inputs, not projected votes.'}</p>${r.notes.filter(n=>!(independentVsRepublican(r)&&n.startsWith('Independent / three-way field'))).map(n=>`<div class="n42rc-note">${esc(n)}</div>`).join('')}<div class="n42rc-detail-columns"><div><h3>Forecast methodology</h3>${line('Engine',r.model.engine)}${line('PVI D-signed',fmt(r.model.pvi))}${line('Observed House polls',r.model.poll_count===null?'Not available':fmt(r.model.poll_count,0))}${r.chamber==='House'?line('Component weights',`fundamentals ${fmt((r.model.fundamentals_weight||0)*100)}% / ratings ${fmt((r.model.ratings_weight||0)*100)}% / polls ${fmt((r.model.polling_weight||0)*100)}%`):line('Method class',r.model.monitored?'Monitored polling engine':'Validated structural engine')}<p class="n42rc-footnote">Win probabilities are not vote shares. The displayed D/R margin is a race-level prediction. For conventional two-party contests, displayed vote shares are implied mathematical two-party shares, not all-ballot totals. In R/I matchups without a Democratic nominee, the unchanged model D-side is labeled I in the interface. Three-way candidate probabilities are not separately estimated; observed polling averages are not projected results.</p><h3>Presidential history · supplied geography</h3><div id="n42rcHistoryChart" class="n42rc-spark"></div><p class="n42rc-footnote">Source presidential margins, not NUCLEUS historical forecasts. Boundary comparability has not been independently established for every district.</p></div><div><h3>Population composition</h3><div class="n42rc-tabbar">${['race / origin','age','education','household income'].map((f,i)=>`<button class="n42rc-btn" data-n42rc-family="${esc(f)}" aria-pressed="${i===0}">${esc(f)}</button>`).join('')}</div><div id="n42rcComposition" class="n42rc-bars">${demographicBars(r,'race / origin')}</div><p class="n42rc-footnote">${r.composition.notes.map(esc).join(' ')} ${r.chamber==='Senate'?'State figures are sums of supplied House district counts.':''}</p></div></div>${r.candidate_conflicts.length?`<details><summary>Predictive workbook / enrichment identity differences</summary><p class="n42rc-footnote">${r.candidate_conflicts.map(esc).join('<br>')}</p></details>`:''}`;
  document.querySelectorAll('[data-n42rc-family]').forEach(b=>b.addEventListener('click',()=>{document.querySelectorAll('[data-n42rc-family]').forEach(x=>x.setAttribute('aria-pressed',String(x===b)));$('n42rcComposition').innerHTML=demographicBars(r,b.dataset.n42rcFamily)}));
  if(!$('n42rcRaceDialog').open){const dialog=$('n42rcRaceDialog');if(typeof dialog.showModal==='function')dialog.showModal();else{dialog.setAttribute('open','');dialog.classList.add('n42rc-dialog-fallback');}}
  if(window.Plotly){const years=[2016,2020,2024],vals=years.map(y=>r.history['margin_'+y]);Plotly.newPlot('n42rcHistoryChart',[{x:years,y:vals,type:'scatter',mode:'lines+markers',line:{color:'#7595BA',width:2},marker:{size:7},hovertemplate:'%{x}: D−R %{y:.1f} pp<extra></extra>'}],{margin:{l:35,r:15,t:10,b:30},height:180,paper_bgcolor:'transparent',plot_bgcolor:'transparent',font:{family:'Arial',size:11,color:'#64748B'},xaxis:{tickvals:years},yaxis:{title:'D−R pp',zerolinecolor:'#CBD5E1'}},{displayModeBar:false,responsive:true});}
 }
 document.addEventListener('click',e=>{const b=e.target.closest('[data-n42rc-open]');if(b&&idx.has(b.dataset.n42rcOpen))profile(idx.get(b.dataset.n42rcOpen));});
 const closeDialog=()=>{const dialog=$('n42rcRaceDialog');if(typeof dialog.close==='function')dialog.close();else dialog.removeAttribute('open');dialog.classList.remove('n42rc-dialog-fallback');};
 $('n42rcClose').addEventListener('click',closeDialog);document.addEventListener('keydown',e=>{if(e.key==='Escape'&&$('n42rcRaceDialog').open)closeDialog()});$('n42rcRaceDialog').addEventListener('click',e=>{if(e.target===$('n42rcRaceDialog')){const r=e.target.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)closeDialog();}});
 // Direct entry points from the existing maps; the original map views remain intact.
 for(const node of document.querySelectorAll('.house-district[data-district],.house-cart-tile[data-district]')){const r=idx.get(node.dataset.district);if(!r)continue;node.dataset.n42rcBound='1';node.addEventListener('click',()=>profile(r));node.addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();profile(r)}});node.setAttribute('aria-label',`${node.getAttribute('aria-label')} · ${displayCandidates(r).map(c=>c.name).join(' / ')} · press Enter to open profile`);}
 for(const node of document.querySelectorAll('[data-abbr][data-tier]')){const r=idx.get(node.dataset.abbr+'-SEN');if(r){node.dataset.n42rcBound='1';node.addEventListener('click',()=>profile(r));node.addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();profile(r)}});node.setAttribute('tabindex','0');node.setAttribute('aria-label',`${r.id} · ${displayCandidates(r).map(c=>c.name).join(' / ')} · open profile`);}}
 // Senate candidate desk intentionally removed; map clicks open the profile without scrolling through a redundant table.

 // Dynamic map layers may be rebuilt after a view toggle. Keep map-to-profile working.
 document.addEventListener('click',e=>{
  const target=e.target.closest('.house-district[data-district],.house-cart-tile[data-district],[data-abbr][data-tier]');
  if(!target||target.dataset.n42rcBound==='1')return;
  const id=target.dataset.district||(target.dataset.abbr?target.dataset.abbr+'-SEN':null);
  if(idx.has(id))profile(idx.get(id));
 });
 // The approved v30 map layout and its existing help text remain unchanged.
 // Existing House inspector still receives events from the original v30 script; it is hidden, not deleted.

 // Append profile links to the existing dynamic House/Senate tables after every re-render.
 function enrichRows(root){if(!root)return;root.querySelectorAll('tbody tr').forEach(tr=>{if(tr.querySelector('[data-n42rc-profile-link]'))return;const td=tr.querySelector('td');if(!td)return;const text=td.textContent.trim();let r=idx.get(text);if(!r&&root.id==='senateRaceTable')r=D.races.find(x=>x.chamber==='Senate'&&(text.includes(x.state)||text.includes(x.label)));if(!r)return;const link=document.createElement('button');link.className='n42rc-race-heading-button n42rc-candidate-link';link.dataset.n42rcProfileLink='1';link.dataset.n42rcOpen=r.id;link.textContent=mainPeople(r).map(c=>c.name).join(' / ')+' ↗';td.append(link);});}
 for(const id of ['houseTable','senateRaceTable']){const table=document.getElementById(id);if(table){enrichRows(table);new MutationObserver(()=>enrichRows(table)).observe(table,{childList:true,subtree:true});}}
 for(const link of [['data-lineage','Data']]){const nav=document.querySelector('.nav');if(nav&&!nav.querySelector(`[href="#${link[0]}"]`)){const a=document.createElement('a');a.href='#'+link[0];a.textContent=link[1];nav.append(a);}}
 $('n42rcDownload').addEventListener('click',async()=>{
  if(!activeRace||typeof window.html2canvas!=='function')return;
  const button=$('n42rcDownload');button.disabled=true;
  try{
   const node=$('n42rcRaceDetail'),canvas=await window.html2canvas(node,{backgroundColor:'#F8FAFC',scale:2,useCORS:true,allowTaint:false,logging:false});
   const blob=await new Promise((resolve,reject)=>canvas.toBlob(value=>value?resolve(value):reject(new Error('PNG encoding failed')),'image/png',1));
   const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=`nucleus42-${activeRace.chamber.toLowerCase()}-${activeRace.id}.png`;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);
  }catch(error){console.error(error);alert('The race card could not be exported in this browser.');}
  finally{button.disabled=false;}
 });
 $('n42rcDataSummary').innerHTML=[`470 race profiles`,`${D.counts.photoMatched} matched portraits`,`${D.counts.photoMissing} explicit portrait gaps`,`${D.counts.demographicCategoryOverlapRows} overlapping-category districts`,`${D.counts.candidateConflicts} workbook / candidate snapshot differences`].map(s=>`<span class="n42rc-chip">${s}</span>`).join('');
 $('n42rcSources').innerHTML=D.sources.map(s=>`<tr><td>${esc(s.file)}</td><td>${esc(s.role)}</td><td>Versioned source snapshot; received ${esc(s.received_date)}</td><td><span>Bundled research snapshot</span></td></tr>`).join('');
 render();
})();
