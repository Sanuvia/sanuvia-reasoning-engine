"""The dashboard page, embedded as a string (no static-file packaging needed).

A professional, engineering-focused review dashboard for the Persistent Reasoning
Core. Every panel is generated exclusively from existing engine outputs (via the
harness API); the browser never talks to the engine directly and duplicates no
reasoning. Deterministic input remains a structured canonical EvidenceRecord.
No product branding, no conversational UI, no AI assistant.
"""

from __future__ import annotations

INDEX_HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Sanuvia PRC — Engineering Review Harness</title>
<style>
  :root { --fg:#0f172a; --muted:#64748b; --line:#e2e8f0; --bg:#f1f5f9; --card:#fff;
          --accent:#0f766e; --a2:#1d4ed8; --pass:#15803d; --warn:#b45309; --fail:#b91c1c; --nav:#0b1220; }
  * { box-sizing:border-box; }
  body { margin:0; font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, sans-serif; color:var(--fg); background:var(--bg); font-size:14px; line-height:1.45; }
  header { background:var(--nav); color:#e5e7eb; padding:10px 16px; position:sticky; top:0; z-index:40; display:flex; gap:10px; align-items:center; flex-wrap:wrap; }
  header h1 { margin:0; font-size:15px; font-weight:600; }
  header .sub { font-size:11px; color:#94a3b8; }
  header .spacer { flex:1; }
  header input { background:#111827; border:1px solid #334155; color:#e5e7eb; border-radius:6px; padding:6px 10px; width:min(300px,42vw); }
  nav.sticky { position:sticky; top:44px; z-index:30; background:#fff; border-bottom:1px solid var(--line); padding:6px 16px; overflow-x:auto; white-space:nowrap; }
  nav.sticky a { color:var(--muted); text-decoration:none; font-size:12px; margin-right:14px; }
  nav.sticky a:hover { color:var(--accent); }
  .wrap { max-width:1180px; margin:0 auto; padding:16px; }
  .card { background:var(--card); border:1px solid var(--line); border-radius:10px; padding:14px 16px; margin:14px 0; box-shadow:0 1px 2px rgba(15,23,42,.04); scroll-margin-top:86px; }
  .card h2 { margin:0 0 10px; font-size:12px; text-transform:uppercase; letter-spacing:.05em; color:var(--muted); border-bottom:1px solid var(--line); padding-bottom:8px; }
  label { display:block; font-size:12px; color:var(--muted); margin:8px 0 2px; }
  input, select, textarea, button { font:inherit; font-size:13px; }
  input, select, textarea { width:100%; padding:6px 8px; border:1px solid var(--line); border-radius:6px; background:#fff; }
  input:disabled { background:#f8fafc; color:var(--muted); }
  textarea { min-height:48px; font-family: ui-monospace, Menlo, monospace; }
  .row { display:grid; grid-template-columns:1fr 1fr 1fr; gap:10px; }
  .row2 { display:grid; grid-template-columns:1fr 1fr; gap:10px; }
  .btns { display:flex; flex-wrap:wrap; gap:8px; margin-top:12px; }
  button { padding:7px 11px; border:1px solid var(--line); border-radius:6px; background:#fff; cursor:pointer; color:var(--fg); }
  button:hover { border-color:#cbd5e1; background:#f8fafc; }
  button.sm { padding:3px 8px; font-size:12px; }
  button.primary { background:var(--accent); color:#fff; border-color:var(--accent); }
  .kpis { display:grid; grid-template-columns:repeat(6,1fr); gap:10px; }
  .kpi { background:#f8fafc; border:1px solid var(--line); border-radius:8px; padding:8px 10px; }
  .kpi b { display:block; font-size:10px; color:var(--muted); font-weight:600; text-transform:uppercase; }
  .kpi span { font-size:15px; font-weight:600; font-family:ui-monospace,Menlo,monospace; }
  table { width:100%; border-collapse:collapse; font-size:12.5px; }
  th, td { text-align:left; padding:5px 7px; border-bottom:1px solid var(--line); vertical-align:top; }
  th { color:var(--muted); font-weight:600; font-size:10.5px; text-transform:uppercase; }
  tr:hover td { background:#f8fafc; }
  code, .mono { font-family: ui-monospace, Menlo, monospace; font-size:12px; }
  .empty { color:var(--muted); font-style:italic; font-size:13px; }
  .bar { background:#e2e8f0; border-radius:4px; height:10px; overflow:hidden; } .bar>span { display:block; height:100%; background:var(--a2); }
  pre { background:#0b1220; color:#e5e7eb; padding:12px; border-radius:8px; overflow:auto; max-height:520px; font-size:12px; }
  details > summary { cursor:pointer; color:var(--muted); font-size:12px; padding:2px 0; }
  .badge { display:inline-block; padding:2px 8px; border-radius:999px; font-size:11px; font-weight:600; }
  .badge.pass,.badge.ran,.badge.added { background:#dcfce7; color:var(--pass); }
  .badge.warn,.badge.pending { background:#fef3c7; color:var(--warn); }
  .badge.fail,.badge.removed { background:#fee2e2; color:var(--fail); }
  .badge.updated { background:#dbeafe; color:var(--a2); }
  .tag { display:inline-block; background:#e0e7ff; color:#3730a3; padding:1px 8px; border-radius:999px; font-size:11px; margin:2px 4px 2px 0; }
  .pipe { display:flex; flex-wrap:wrap; gap:6px; align-items:center; font-size:12px; }
  .pipe .stage { background:#f8fafc; border:1px solid var(--line); border-radius:6px; padding:3px 8px; } .pipe .arrow { color:var(--muted); }
  .node { border:1px solid var(--line); border-radius:8px; padding:8px 10px; margin:4px; min-width:120px; display:inline-block; vertical-align:top; }
  .node b { font-family:ui-monospace,Menlo,monospace; }
  .flow { display:flex; align-items:center; flex-wrap:wrap; }
  .step { border:1px solid var(--line); border-radius:8px; padding:8px 10px; margin:6px 0; }
  .ok { color:var(--pass); font-weight:700; } .no { color:var(--fail); font-weight:700; }
  .mermaid { background:#fff; border:1px solid var(--line); border-radius:8px; padding:8px; overflow:auto; }
  mark { background:#fde68a; padding:0 1px; border-radius:2px; }
  svg.chart { width:100%; height:auto; }
  .legend span { font-size:11px; margin-right:12px; } .legend i { display:inline-block; width:10px; height:10px; border-radius:2px; margin-right:4px; vertical-align:middle; }
  @media (max-width:820px){ .row,.row2{grid-template-columns:1fr;} .kpis{grid-template-columns:1fr 1fr;} }
</style>
</head>
<body>
<header>
  <h1>Sanuvia PRC</h1><span class="sub">Engineering Review Harness · reasoning engine under test</span>
  <span class="spacer"></span>
  <input id="globalSearch" placeholder="Search everywhere ( / )" oninput="highlightAll()"><span id="searchCount" class="sub"></span>
</header>
<nav class="sticky">
  <a href="#sec-tc">Test Cases</a><a href="#sec-form">Evidence</a><a href="#sec-verdict">Verdict</a>
  <a href="#sec-eva">Expected vs Actual</a><a href="#sec-charts">Charts</a><a href="#sec-wm">WM Timeline</a>
  <a href="#sec-rev">Revisions</a><a href="#sec-prov">Provenance</a><a href="#sec-state">State</a>
  <a href="#sec-trace">Trace</a><a href="#sec-graph">Graph</a>
</nav>
<div class="wrap">

  <div class="card">
    <h2>Guided Engineering Review <span class="empty">(walkthrough — not a product tutorial)</span></h2>
    <div class="pipe" id="wizard"></div>
    <div id="progress" style="margin-top:12px"></div>
  </div>

  <div class="card" id="sec-purpose" style="display:none"><h2>Dataset Purpose <span class="empty">(read before running)</span></h2><div id="purpose"></div></div>

  <div class="card" id="sec-result" style="display:none">
    <h2>Engineering Review Result</h2>
    <div class="btns"><button class="primary" onclick="fetchResult()">Compute Final Verdict</button><button onclick="downloadPackage()">Download Complete Engineering Review (.zip)</button></div>
    <div id="result" style="margin-top:10px"></div>
  </div>

  <div class="card" id="sec-tc">
    <h2>Test Cases</h2>
    <label>Active test case — one deterministic reasoning experiment.</label>
    <select id="testcase" onchange="selectCase()"></select>
    <div class="btns">
      <button onclick="newCase()">New</button><button onclick="duplicateCase()">Duplicate</button>
      <button onclick="renameCase()">Rename</button><button onclick="saveCase()">Save</button><span id="saveNote" class="empty"></span>
    </div>
    <details style="margin-top:8px"><summary>Search test cases</summary>
      <div class="row2"><div><input id="search" placeholder="name / evidence / tag" onkeydown="if(event.key==='Enter')doSearch()"></div><div><input id="searchTags" placeholder="tags"></div></div>
      <div class="btns"><button onclick="doSearch()">Search</button></div><div id="searchResults"></div>
    </details>
    <details style="margin-top:6px"><summary>Sample library &amp; official Review Dataset (D1–D12)</summary><div id="samples"><span class="empty">loading…</span></div></details>
    <details style="margin-top:6px"><summary>Import / Export</summary>
      <div class="btns">
        <button onclick="exportTestCase()">Export Test Case (JSON)</button>
        <button onclick="$('importFile').click()">Import Test Case (JSON)</button>
        <input id="importFile" type="file" accept="application/json,.json" style="display:none" onchange="importTestCase(event)">
        <button onclick="exportArtifact('/api/export/trace','markdown','text/markdown')">Trace (.md)</button>
        <button onclick="exportArtifact('/api/export/graph-mermaid','mermaid','text/plain')">Graph (.mmd)</button>
        <button onclick="exportArtifact('/api/export/graph-dot','dot','text/vnd.graphviz')">Graphviz (.dot)</button>
        <button class="primary" onclick="exportArtifact('/api/export/report','markdown','text/markdown')">Review Report (.md)</button>
        <button onclick="downloadPackage()">Complete Review Package (.zip)</button>
      </div>
    </details>
  </div>

  <div class="card" id="sec-form">
    <h2>Add EvidenceRecord <span class="empty">(canonical, structured — no NLU)</span></h2>
    <div class="row">
      <div><label>Evidence ID</label><input id="evid" value="auto (evidence-N)" disabled></div>
      <div><label>Subject ID</label><input id="subject" value="—" disabled></div>
      <div><label>Timestamp / sequence</label><input id="tspos" value="auto (deterministic)" disabled></div>
    </div>
    <label>Observed content (RawObservation)</label><textarea id="content">partner went quiet during a disagreement</textarea>
    <div class="row">
      <div><label>Evidence class</label><select id="evidence_class"><option>behavioural</option><option>narrative</option><option>reflective</option><option>contradictory</option><option>missing</option><option>failed_acquisition</option></select></div>
      <div><label>Source</label><input id="source" value="reflection:session-1"></div>
      <div><label>Classification status</label><input id="cstatus" value="provisional"></div>
    </div>
    <div class="row">
      <div><label>Evidence reliability</label><input id="reliability" type="number" min="0" max="1" step="0.05" value="0.7"></div>
      <div><label>Classification confidence</label><input id="cc" type="number" min="0" max="1" step="0.05" value="0.9"></div>
      <div><label>Provenance confidence</label><input id="pc" type="number" min="0" max="1" step="0.05" value="0.9"></div>
    </div>
    <label>Metadata (<code>key=value</code> per line)</label><textarea id="metadata">channel=written</textarea>
    <label style="margin-top:8px"><b>Structured appraisal</b> — hypotheses this evidence bears on (authored, not extracted)</label>
    <div class="row">
      <div><label>Supports (ids)</label><input id="supports"></div>
      <div><label>Contradicts (ids)</label><input id="contradicts"></div>
      <div><label>Proposals (id | statement | support)</label><textarea id="proposals">H_a | first explanation | 0.4
H_b | second explanation | 0.4</textarea></div>
    </div>
    <div class="btns">
      <button onclick="addEvidence()">Add to Sequence</button><button class="primary" onclick="addAndRun()">Add &amp; Run</button>
      <button onclick="runNext()">Run Next Step</button><button onclick="runAll()">Run Full Sequence</button><button onclick="resetCase()">Reset</button>
    </div>
    <div id="sequence" style="margin-top:12px"></div>
  </div>

  <div class="card" id="sec-verdict"><h2>Reviewer Verdict <span class="empty">(auto-generated — reasoning correctness)</span></h2><div id="verdict"></div></div>
  <div class="card"><h2>Automatic Reasoning Summary <span class="empty">(generated from engine state)</span></h2><div id="rsummary"></div></div>
  <div class="card"><h2>Why did the engine reach this conclusion? <span class="empty">(from engine state — no LLM)</span></h2><div id="explain"></div></div>
  <div class="card" id="sec-eva" style="display:none"><h2>Expected vs Actual <span class="empty">(Review Dataset)</span></h2><div id="eva"></div></div>
  <div class="card"><h2>Engineering Summary</h2><div class="kpis" id="summary"></div></div>

  <div class="card" id="sec-charts">
    <h2>Uncertainty over interactions</h2><div id="uchart"></div>
    <h2 style="margin-top:14px">Hypothesis evolution</h2><div id="hchart"></div>
    <h2 style="margin-top:14px">Prediction lifecycle</h2><div id="plife"></div>
  </div>

  <div class="card" id="sec-wm"><h2>WorldModel Timeline</h2><div id="wmtimeline"></div>
    <h2 style="margin-top:14px">WorldModel Evolution Summary</h2><div id="wmevolution"></div></div>

  <div class="card" id="sec-rev">
    <h2>Revisions by Interaction</h2><div id="revbyi"></div>
    <details style="margin-top:8px"><summary>Reasoning pipeline timeline (per step, expandable)</summary><div id="timeline"></div></details>
  </div>

  <div class="card" id="sec-prov"><h2>Provenance Viewer <span class="empty">(expand an evidence record to trace its chain)</span></h2><div id="provchains"></div></div>

  <div class="card" id="sec-state"><h2>Current State</h2>
    <details open><summary>Evidence (recorded)</summary><div id="evidence"></div></details>
    <details open><summary>Current World Model</summary><div id="worldmodel"></div></details>
    <details open><summary>Active Hypotheses &amp; Support</summary><div id="hypotheses"></div><div id="support"></div></details>
    <details open><summary>Predictions</summary><div id="predictions"></div></details>
    <details open><summary>Inquiry</summary><div id="inquiry"></div></details>
    <details><summary>Revision Ledger</summary><div id="ledger"></div></details>
    <details><summary>Recognition Conditions</summary><div id="recognition"></div></details>
    <details><summary>Tags &amp; Reviewer Notes</summary>
      <div id="tags" style="margin-top:6px"></div>
      <label>Tags (comma-sep)</label><div class="row2"><div><input id="tagInput"></div><div><button onclick="setTags()">Set Tags</button></div></div>
      <div id="notes" style="margin-top:8px"></div>
      <label>Add note</label><div class="row2"><div><input id="noteInput" onkeydown="if(event.key==='Enter')addNote()"></div><div><button onclick="addNote()">Add Note</button></div></div>
    </details>
    <details><summary>Comparison mode (regression)</summary>
      <div class="row2"><div><label>A</label><select id="cmpA"></select></div><div><label>B</label><select id="cmpB"></select></div></div>
      <div class="btns"><button onclick="compareCases()">Compare</button></div><div id="compare"></div>
    </details>
  </div>

  <div class="card" id="sec-trace"><h2>Reasoning Trace</h2>
    <div class="btns"><button onclick="loadTrace(false)">Load (this test case)</button><button onclick="loadTrace(true)">Load Reference</button>
      <button class="sm" onclick="copyTrace()">Copy</button><button class="sm" onclick="downloadTrace()">Download .md</button></div>
    <div id="traceWrap" style="display:none; margin-top:10px"><div class="row2"><div id="traceToc" style="max-height:520px;overflow:auto;border:1px solid var(--line);border-radius:8px;padding:8px;font-size:12px"></div><div id="traceBody" style="max-height:520px;overflow:auto"></div></div></div>
  </div>

  <div class="card" id="sec-graph"><h2>Reasoning Lineage Graph</h2>
    <div class="btns"><button onclick="loadGraph(false)">Load (this test case)</button><button onclick="loadGraph(true)">Load Reference</button></div>
    <div id="graph"></div>
  </div>

  <div class="card"><h2>Exit Test</h2><div class="btns"><button onclick="loadExit()">Run Canonical Exit Test</button></div><div id="exit"><span class="empty">Not run.</span></div></div>
  <div class="card"><h2>Test Case Metadata</h2><div class="kpis" id="meta"></div></div>
</div>

<script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js" onerror="window.__noMermaid=true"></script>
<script>
const $=id=>document.getElementById(id);
const esc=s=>String(s).replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
const csv=s=>s.split(',').map(x=>x.trim()).filter(Boolean);
async function getJSON(u){const r=await fetch(u);return r.json();}
async function postJSON(u,b){const r=await fetch(u,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(b||{})});return r.json();}
function download(fn,t,m){const b=new Blob([t],{type:m||'text/plain'});const u=URL.createObjectURL(b);const a=document.createElement('a');a.href=u;a.download=fn;a.click();URL.revokeObjectURL(u);}
function table(cols,rows){if(!rows.length)return '<p class="empty">none</p>';return '<table><thead><tr>'+cols.map(c=>'<th>'+c+'</th>').join('')+'</tr></thead><tbody>'+rows.map(r=>'<tr>'+r.map(c=>'<td class="mono">'+c+'</td>').join('')+'</tr>').join('')+'</tbody></table>';}
function kpi(list){return list.map(([k,v])=>'<div class="kpi"><b>'+esc(k)+'</b><span>'+esc(v==null?'—':v)+'</span></div>').join('');}
const PALETTE=['#1d4ed8','#b91c1c','#15803d','#7c3aed','#b45309','#0891b2','#be185d','#4d7c0f'];
let STATE=null, TRACE='';

// --- SVG line chart (y in [0,1]) ---
function lineChart(series, n, opts){
  opts=opts||{}; const W=640,H=160,pad=30;
  if(!n) return '<p class="empty">no data</p>';
  const X=i=>pad+(n===1?(W-2*pad)/2:i*(W-2*pad)/(n-1));
  const Y=y=>H-pad-y*(H-2*pad);
  let g='<svg class="chart" viewBox="0 0 '+W+' '+H+'" preserveAspectRatio="xMidYMid meet">';
  // gridlines 0,.5,1
  [0,0.5,1].forEach(t=>{ g+='<line x1="'+pad+'" y1="'+Y(t)+'" x2="'+(W-pad)+'" y2="'+Y(t)+'" stroke="#e2e8f0"/><text x="4" y="'+(Y(t)+4)+'" font-size="10" fill="#94a3b8">'+t.toFixed(1)+'</text>'; });
  series.forEach((s,si)=>{ const col=s.color||PALETTE[si%PALETTE.length]; let d='',started=false;
    s.values.forEach((v,i)=>{ if(v==null){started=false;return;} d+=(started?'L':'M')+X(i)+' '+Y(v)+' '; started=true; });
    g+='<path d="'+d+'" fill="none" stroke="'+col+'" stroke-width="2"/>';
    s.values.forEach((v,i)=>{ if(v==null)return; g+='<circle cx="'+X(i)+'" cy="'+Y(v)+'" r="2.5" fill="'+col+'"/>'; if(opts.labels){ g+='<text x="'+X(i)+'" y="'+(Y(v)-6)+'" font-size="9" fill="'+col+'" text-anchor="middle">'+v+'</text>'; } });
  });
  // x labels
  for(let i=0;i<n;i++){ g+='<text x="'+X(i)+'" y="'+(H-8)+'" font-size="10" fill="#94a3b8" text-anchor="middle">'+(i+1)+'</text>'; }
  g+='</svg>'; return g;
}

function render(s){
  STATE=s;
  const m=s.metadata, su=s.summary;
  $('subject').value=m.subject;
  $('meta').innerHTML=kpi([['Test Case',m.test_case_name],['ID',m.test_case_id],['Subject',m.subject],['Created',(m.created_at||'').slice(0,19)],['Sequence',m.sequence_length],['Backend',m.backend]]);
  $('summary').innerHTML=kpi([['EvidenceRecords',su.evidence_records],['Interactions',su.interactions_executed],['WM versions',su.world_model_versions],['Revisions',su.revision_events],['Active hypotheses',su.active_hypotheses],['Predictions',su.predictions],['Inquiries',su.inquiries],['Uncertainty',su.model_uncertainty==null?'—':su.model_uncertainty],['Engine',su.engine_version.replace('Persistent Reasoning Core ','PRC ')],['Deterministic',su.deterministic?'yes':'no']]);

  const cases=s.test_cases||[];
  $('testcase').innerHTML=cases.map(x=>'<option value="'+x.id+'"'+(x.current?' selected':'')+'>'+esc(x.name)+' — '+x.interactions_run+'/'+x.sequence_length+' run</option>').join('');
  const opts=cases.map(x=>'<option value="'+x.id+'">'+esc(x.name)+'</option>').join(''); $('cmpA').innerHTML=opts; $('cmpB').innerHTML=opts;

  $('sequence').innerHTML=(s.sequence&&s.sequence.length)?table(['#','status','class','reliability','evidence id','content'],s.sequence.map(x=>[x.position,x.ran?'<span class="badge ran">ran</span>':'<span class="badge pending">pending</span>',x.evidence_class,x.reliability,x.evidence_id||'—',esc(x.content)])):'<p class="empty">no evidence yet — Add to Sequence</p>';

  // Verdict
  const v=s.verdict||{overall:'PENDING',checks:[]};
  $('verdict').innerHTML='<div style="margin-bottom:8px">Overall: <span class="badge '+(v.overall==='PASS'?'pass':(v.overall==='FAIL'?'fail':'warn'))+'">'+v.overall+'</span></div>'+
    (v.checks.length?v.checks.map(c=>'<div>'+(c.pass?'<span class="ok">✅</span>':'<span class="no">❌</span>')+' '+esc(c.label)+'</div>').join(''):'<span class="empty">run to evaluate</span>');

  // Expected vs Actual
  const eva=s.expected_vs_actual;
  if(eva&&eva.length){ $('sec-eva').style.display='block';
    let h='';
    eva.forEach(r=>{ h+='<div class="step"><b>Step '+r.step+'</b> '+(r.match?'<span class="badge pass">✅ Match</span>':'<span class="badge fail">❌ Difference</span>')+
      '<table style="margin-top:6px"><thead><tr><th>field</th><th>expected</th><th>actual</th></tr></thead><tbody>'+
      Object.entries(r.fields).map(([f,fd])=>'<tr'+(fd.match?'':' style="background:#fef2f2"')+'><td>'+f+'</td><td class="mono">'+esc(JSON.stringify(fd.expected))+'</td><td class="mono">'+esc(JSON.stringify(fd.actual))+' '+(fd.match?'✅':'❌')+'</td></tr>').join('')+'</tbody></table></div>'; });
    $('eva').innerHTML=h;
  } else { $('sec-eva').style.display='none'; }

  // Charts
  const tl=s.timeline||[];
  $('uchart').innerHTML=lineChart([{values:tl.map(t=>t.uncertainty_after),color:'#0f766e'}], tl.length, {labels:true});
  const he=s.hypothesis_evolution||{steps:0,series:[]};
  $('hchart').innerHTML=(he.series.length? lineChart(he.series.map((x,i)=>({values:x.support,color:PALETTE[i%PALETTE.length]})), he.steps, {}) +
    '<div class="legend" style="margin-top:6px">'+he.series.map((x,i)=>'<span><i style="background:'+PALETTE[i%PALETTE.length]+'"></i>'+esc(x.hypothesis_id)+'</span>').join('')+'</div>' : '<p class="empty">no hypotheses yet</p>');

  // Prediction lifecycle
  const pl=s.prediction_lifecycle||[];
  $('plife').innerHTML=pl.length? pl.map(p=>'<div class="step"><b>'+esc(p.hypothesis_id)+'</b><div class="pipe" style="margin-top:4px">'+
    p.events.map((e,i)=>{const cls=e.event==='created'?'added':(e.event==='invalidated'?'removed':'updated'); return '<span class="badge '+cls+'">'+e.event+(e.likelihood!=null?' L='+e.likelihood:'')+' @'+(e.version||'—')+'</span>'+(i<p.events.length-1?'<span class="arrow">→</span>':'');}).join('')+'</div></div>').join('')
    : '<p class="empty">no predictions</p>';

  // WM timeline
  const wt=s.world_model_timeline||[];
  $('wmtimeline').innerHTML=wt.length? '<div class="flow">'+wt.map((n,i)=>'<div class="node"><b>'+n.version+'</b><br><span class="empty">u='+(n.uncertainty==null?'—':n.uncertainty)+' · h='+n.active_hypotheses.length+' · p='+n.prediction_count+' · i='+n.inquiry_count+'</span></div>'+(i<wt.length-1?'<span class="arrow">→</span>':'')).join('')+'</div>' : '<p class="empty">no versions yet</p>';

  // Revisions by interaction
  const rbi=s.revisions_by_interaction||[];
  $('revbyi').innerHTML=rbi.length? rbi.map(r=>{const st=['Evidence '+(r.evidence.join(', ')||'—')]; r.revisions.forEach(x=>st.push(x.outcome+' '+x.affected)); r.anomalies.forEach(a=>st.push('anomaly:'+a.disposition)); st.push('WorldModel '+(r.version||'hold'));
    return '<div class="step"><b>Interaction '+r.step+'</b><div class="pipe" style="margin-top:4px">'+st.map((x,i)=>'<span class="stage">'+esc(x)+'</span>'+(i<st.length-1?'<span class="arrow">→</span>':'')).join('')+'</div></div>';}).join('') : '<p class="empty">no interactions</p>';

  // Provenance chains
  const ec=s.evidence_chains||[];
  $('provchains').innerHTML=ec.length? ec.map(c=>'<details><summary><b class="mono">'+c.evidence_id+'</b> ('+c.evidence_class+') — '+esc(c.content)+'</summary><div class="pipe" style="margin:6px 0">'+
    ['Evidence '+c.evidence_id, ...(c.revisions.map(r=>r.outcome+' '+r.affected)), 'WorldModel '+(c.versions.join(', ')||'—'), 'Predictions '+(c.predictions.join(', ')||'—'), 'Inquiry '+(c.inquiries.join(', ')||'—')].map((x,i,arr)=>'<span class="stage">'+esc(x)+'</span>'+(i<arr.length-1?'<span class="arrow">→</span>':'')).join('')+'</div></details>').join('') : '<p class="empty">no evidence yet</p>';

  // Pipeline timeline (expandable)
  $('timeline').innerHTML=tl.length? tl.map(t=>'<div class="step"><b>Step '+t.step+'</b> <span class="empty">'+(t.evidence_id||'—')+' · '+(t.world_model_version?('WorldModel '+t.world_model_version):'model holds')+' · u '+(t.uncertainty_before==null?'—':t.uncertainty_before)+'→'+(t.uncertainty_after==null?'—':t.uncertainty_after)+'</span></div>').join('') : '<p class="empty">no steps</p>';

  // Current state panels
  $('evidence').innerHTML=table(['id','class','reliability','status','source','content'],(s.evidence||[]).map(e=>[e.id,e.class,e.reliability,e.classification_status,esc(e.source),esc(e.content)]));
  const w=s.world_model;
  $('worldmodel').innerHTML=w?table(['field','value'],[['version',w.version],['model_uncertainty',w.model_uncertainty],['active_hypotheses',w.active_hypotheses.join(', ')||'—'],['active_predictions',w.active_predictions.join(', ')||'—'],['active_inquiries',w.active_inquiries.join(', ')||'—'],['provenance_record_id',w.provenance_record_id||'—']]):'<p class="empty">no committed model yet</p>';
  $('hypotheses').innerHTML=table(['hypothesis_id','support','statement','supporting','contradicting'],(s.hypotheses||[]).map(h=>[h.hypothesis_id,h.support,esc(h.statement),h.supporting_evidence.join(', ')||'—',h.contradicting_evidence.join(', ')||'—']));
  $('support').innerHTML=(s.hypotheses&&s.hypotheses.length)?s.hypotheses.map(h=>'<div style="margin:6px 0"><div class="mono">'+h.hypothesis_id+' — '+h.support+'</div><div class="bar"><span style="width:'+Math.round(h.support*100)+'%"></span></div></div>').join(''):'';
  $('predictions').innerHTML=table(['id','likelihood','trajectory','from hypotheses'],(s.predictions||[]).map(p=>[p.id,p.likelihood,p.trajectory_kind,p.from_hypotheses.join(', ')]));
  $('inquiry').innerHTML=(s.inquiries&&s.inquiries.length)?s.inquiries.map(i=>'<div class="mono">'+i.id+' · '+i.status+' · u='+i.current_uncertainty+'</div><blockquote class="empty">'+esc(i.statement)+'</blockquote>').join(''):'<p class="empty">none</p>';
  $('ledger').innerHTML=table(['seq','outcome','affected','from→to','evidence'],(s.revision_ledger||[]).map(x=>[x.sequence_no,x.event.outcome,x.event.affected,(x.event.from_version||'∅')+' → '+x.event.to_version,x.event.triggering_evidence.join(', ')]));
  $('recognition').innerHTML=(s.recognition_conditions&&s.recognition_conditions.length)?table(['id','kind','description'],s.recognition_conditions.map(r=>[r.id,r.kind,esc(r.description)])):'<p class="empty">none — detection deferred in Phase 0</p>';
  $('tags').innerHTML=(s.tags&&s.tags.length)?s.tags.map(t=>'<span class="tag">'+esc(t)+'</span>').join(''):'<span class="empty">no tags</span>'; $('tagInput').value=(s.tags||[]).join(', ');
  $('notes').innerHTML=(s.notes&&s.notes.length)?s.notes.map((n,i)=>'<div class="step">'+esc(n)+' <button class="sm" onclick="removeNote('+i+')">remove</button></div>').join(''):'<span class="empty">no notes</span>';
  renderPurpose(s); renderSummaryExplain(s); renderWmEvolution(s.world_model_timeline||[]); renderProgress(s);
  highlightAll();
}

let PROG={trace:false,graph:false};
function renderWizard(){const steps=['Choose a Review Dataset','Run Full Sequence','Review Expected vs Actual','Open Reasoning Trace','Open Reasoning Lineage Graph','Review Verdict','Run Exit Test'];
  $('wizard').innerHTML=steps.map((x,i)=>'<span class="stage">'+(i+1)+'. '+x+'</span>'+(i<steps.length-1?'<span class="arrow">↓</span>':'')).join('');}
function renderProgress(s){const m=s.metadata;
  const loaded=m.sequence_length>0, executed=m.interactions_run>0&&m.interactions_run===m.sequence_length;
  const eva=!!(s.expected_vs_actual&&s.expected_vs_actual.length), exitPassed=m.last_exit_passed===true;
  const items=[['Dataset Loaded',loaded],['Sequence Executed',executed],['Expected vs Actual Reviewed',eva&&executed],['Trace Generated',PROG.trace],['Graph Generated',PROG.graph],['Exit Test Passed',exitPassed],['Review Completed',loaded&&executed&&PROG.trace&&PROG.graph&&exitPassed]];
  $('progress').innerHTML=items.map(([l,ok])=>'<div>'+(ok?'<span class="ok">✔</span>':'<span class="empty">◻</span>')+' '+l+'</div>').join('');}
function renderPurpose(s){const p=s.dataset_purpose; if(!p){$('sec-purpose').style.display='none';return;} $('sec-purpose').style.display='block';
  $('purpose').innerHTML='<div><b>'+esc(s.metadata.test_case_name)+'</b></div>'+
    '<div style="margin-top:6px"><b>Purpose</b><br>'+esc(p.purpose)+'</div>'+
    '<div style="margin-top:6px"><b>Expected behaviour</b><br>'+p.expected_behaviour.map(b=>'<span class="tag">'+esc(b)+'</span>').join('')+'</div>'+
    '<div style="margin-top:6px"><b>Expected reasoning outcome</b><br>'+esc(p.expected_outcome)+'</div>'+
    '<div style="margin-top:6px"><b>Expected Exit Test</b> <span class="badge pass">'+esc(p.expected_exit_test)+'</span></div>';}
function renderSummaryExplain(s){$('rsummary').innerHTML=s.reasoning_summary?'<p>'+esc(s.reasoning_summary)+'</p>':'<p class="empty">run to generate</p>';
  const ew=s.explain_why||[];
  $('explain').innerHTML=ew.length?ew.map(w=>'<div class="step"><b>'+esc(w.hypothesis_id)+'</b> — support '+w.current_support+'<br><span class="empty">'+esc(w.statement)+'</span>'+
    '<div style="margin-top:6px"><b>Supporting evidence</b>: '+(w.supporting_evidence.join(', ')||'—')+' · <b>Contradicting</b>: '+(w.contradicting_evidence.join(', ')||'—')+'</div>'+
    '<div style="margin-top:4px"><b>Support</b>: '+(w.support_progression.join(' → ')||'—')+'</div>'+
    '<div style="margin-top:4px"><b>Reason</b>: '+esc(w.reason)+'</div></div>').join(''):'<p class="empty">run to evaluate</p>';}
function renderWmEvolution(wt){$('wmevolution').innerHTML=wt.length?wt.map((n,i)=>'<div class="step"><b class="mono">'+n.version+'</b> — Hypotheses: '+n.active_hypotheses.length+' · Predictions: '+n.prediction_count+' · Uncertainty: '+(n.uncertainty==null?'—':n.uncertainty)+'</div>'+(i<wt.length-1?'<div class="empty" style="margin-left:14px">↓</div>':'')).join(''):'<p class="empty">no versions yet</p>';}
async function fetchResult(){const d=await getJSON('/api/review-result');$('sec-result').style.display='block';
  $('result').innerHTML='<div style="font-weight:700;margin-bottom:8px">ENGINEERING REVIEW RESULT</div><table><tbody>'+
    [['Dataset',d.dataset],['Overall Result',d.overall],['Expected vs Actual',d.expected_vs_actual],['Reasoning Correct',d.reasoning_correct],['Deterministic',d.deterministic],['Exit Test',d.exit_test],['Ready for Phase 1',d.ready_for_phase_1]]
    .map(([k,v])=>'<tr><td>'+k+'</td><td>'+((v==='PASS'||v==='YES')?'<span class="badge pass">'+v+'</span>':((v==='FAIL'||v==='NO')?'<span class="badge fail">'+v+'</span>':'<span class="mono">'+esc(v)+'</span>'))+'</td></tr>').join('')+'</tbody></table>';
  await refresh();}
async function downloadPackage(){const d=await getJSON('/api/export/package');const bin=atob(d.zip_base64);const arr=new Uint8Array(bin.length);for(let i=0;i<bin.length;i++)arr[i]=bin.charCodeAt(i);download(d.filename,arr,'application/zip');}

async function refresh(){render(await getJSON('/api/state'));}
async function addEvidence(){render(await postJSON('/api/evidence/add',evidenceBody()));}
async function addAndRun(){await postJSON('/api/evidence/add',evidenceBody());render(await postJSON('/api/evidence/run-next'));}
async function runNext(){render(await postJSON('/api/evidence/run-next'));}
async function runAll(){render(await postJSON('/api/run-all'));fetchResult();}
async function resetCase(){render(await postJSON('/api/reset'));$('exit').innerHTML='<span class="empty">Not run.</span>';}
async function newCase(){render(await postJSON('/api/test-cases/new'));}
async function duplicateCase(){render(await postJSON('/api/test-cases/duplicate'));}
async function selectCase(){render(await postJSON('/api/test-cases/select',{test_case_id:$('testcase').value}));}
async function renameCase(){const n=prompt('Rename');if(n)render(await postJSON('/api/test-cases/rename',{name:n}));}
async function saveCase(){await postJSON('/api/test-cases/save');$('saveNote').textContent='saved';}
async function setTags(){render(await postJSON('/api/tags/set',{tags:csv($('tagInput').value)}));}
async function addNote(){const t=$('noteInput').value.trim();if(!t)return;$('noteInput').value='';render(await postJSON('/api/notes/add',{text:t}));}
async function removeNote(i){render(await postJSON('/api/notes/remove',{index:i}));}
async function loadSamples(){const d=await getJSON('/api/samples');$('samples').innerHTML=d.samples.map(x=>'<div class="step"><b>'+esc(x.name)+'</b> <span class="empty">'+x.steps+' steps</span> '+x.tags.map(t=>'<span class="tag">'+esc(t)+'</span>').join('')+' <button class="sm" onclick="loadSample(\''+x.id+'\')">Load</button></div>').join('');}
async function loadSample(id){render(await postJSON('/api/samples/load',{sample_id:id}));}
async function exportTestCase(){const d=await getJSON('/api/export/test-case');download(d.filename,JSON.stringify(d.test_case,null,2),'application/json');}
async function importTestCase(ev){const f=ev.target.files[0];if(!f)return;try{render(await postJSON('/api/import',{test_case:JSON.parse(await f.text())}));}catch(e){alert('Invalid JSON: '+e);}ev.target.value='';}
async function exportArtifact(u,k,m){const d=await getJSON(u);download(d.filename,d[k],m);}
async function doSearch(){const d=await postJSON('/api/search',{query:$('search').value,tags:csv($('searchTags').value)});$('searchResults').innerHTML=d.results.length?d.results.map(r=>'<div class="step" onclick="selectFrom(\''+r.id+'\')"><b>'+esc(r.name)+'</b> '+r.tags.map(t=>'<span class="tag">'+esc(t)+'</span>').join('')+' <span class="empty">'+r.interactions_run+'/'+r.sequence_length+'</span></div>').join(''):'<p class="empty">no matches</p>';}
async function selectFrom(id){render(await postJSON('/api/test-cases/select',{test_case_id:id}));}
async function compareCases(){const d=await postJSON('/api/compare',{a:$('cmpA').value,b:$('cmpB').value});const row=(l,a,b)=>'<tr><td class="mono">'+l+'</td><td class="mono">'+esc(a)+'</td><td class="mono">'+esc(b)+'</td></tr>';
  $('compare').innerHTML='<table><thead><tr><th>field</th><th>'+esc(d.a.name)+'</th><th>'+esc(d.b.name)+'</th></tr></thead><tbody>'+row('Evidence',d.evidence.a.join(', ')||'—',d.evidence.b.join(', ')||'—')+row('Hypotheses',d.hypotheses.a.map(h=>h[0]+'='+h[1]).join(', ')||'—',d.hypotheses.b.map(h=>h[0]+'='+h[1]).join(', ')||'—')+row('Predictions',d.predictions.a.join(', ')||'—',d.predictions.b.join(', ')||'—')+row('Revision count',d.revision_count.a,d.revision_count.b)+row('Uncertainty',d.model_uncertainty.a==null?'—':d.model_uncertainty.a,d.model_uncertainty.b==null?'—':d.model_uncertainty.b)+row('Exit test',d.exit_test.a==null?'—':(d.exit_test.a?'PASS':'FAIL'),d.exit_test.b==null?'—':(d.exit_test.b?'PASS':'FAIL'))+'</tbody></table>';}
function evidenceBody(){const proposals=$('proposals').value.split('\n').map(l=>l.trim()).filter(Boolean).map(l=>{const[id,st,su]=l.split('|').map(x=>(x||'').trim());return{hypothesis_id:id,statement:st||id,initial_support:parseFloat(su||'0.4')};});const metadata=$('metadata').value.split('\n').map(l=>l.trim()).filter(Boolean).map(l=>{const i=l.indexOf('=');return i<0?[l,'']:[l.slice(0,i).trim(),l.slice(i+1).trim()];});return{content:$('content').value,evidence_class:$('evidence_class').value,reliability:parseFloat($('reliability').value),classification_confidence:parseFloat($('cc').value),source:$('source').value,provenance_confidence:parseFloat($('pc').value),classification_status:$('cstatus').value,metadata,supports:csv($('supports').value),contradicts:csv($('contradicts').value),proposals};}

async function loadTrace(ref){const d=await getJSON(ref?'/api/reference-trace':'/api/trace');TRACE=d.markdown;$('traceWrap').style.display='block';PROG.trace=true;if(STATE)renderProgress(STATE);
  const lines=TRACE.split('\n');const sec=[];let cur={t:'(top)',b:[]};for(const ln of lines){const h=ln.match(/^(#{1,3})\s+(.*)/);if(h){sec.push(cur);cur={t:h[2],b:[]};}else cur.b.push(ln);}sec.push(cur);
  $('traceToc').innerHTML='<b>Contents</b>'+sec.map((x,i)=>'<div><a href="#" onclick="jt('+i+');return false">'+esc(x.t)+'</a></div>').join('');
  $('traceBody').innerHTML=sec.map((x,i)=>'<details id="ts-'+i+'" '+(i<3?'open':'')+'><summary>'+esc(x.t)+'</summary><pre>'+hl(x.b.join('\n'))+'</pre></details>').join('');}
function hl(t){return esc(t).replace(/`([^`]+)`/g,'<span style="color:#93c5fd">$1</span>').replace(/\b(wm-\d+|evidence-\d+|rev-\d+|H_[A-Za-z_]+|inq-\d+|pred-\d+)\b/g,'<span style="color:#fca5a5">$1</span>').replace(/\*\*([^*]+)\*\*/g,'<b>$1</b>');}
function jt(i){const el=$('ts-'+i);if(el){el.open=true;el.scrollIntoView({behavior:'smooth'});}}
function copyTrace(){navigator.clipboard&&navigator.clipboard.writeText(TRACE);$('saveNote').textContent='trace copied';}
function downloadTrace(){download('reasoning_trace.md',TRACE,'text/markdown');}

async function loadGraph(ref){const d=await getJSON(ref?'/api/reference-graph':'/api/graph');PROG.graph=true;if(STATE)renderProgress(STATE);const el=$('graph');
  el.innerHTML='<div class="mermaid">'+esc(d.mermaid)+'</div><details><summary>Mermaid source</summary><pre>'+esc(d.mermaid)+'</pre></details><details><summary>DOT source</summary><pre>'+esc(d.dot)+'</pre></details>';
  if(window.mermaid&&!window.__noMermaid){try{window.mermaid.initialize({startOnLoad:false});await window.mermaid.run({nodes:el.querySelectorAll('.mermaid')});}catch(e){el.querySelector('.mermaid').textContent=d.mermaid;}}else{el.querySelector('.mermaid').textContent=d.mermaid;}}
async function loadExit(){const d=await getJSON('/api/exit-test');$('exit').innerHTML='<div>Result: <span class="badge '+(d.passed?'pass':'fail')+'">'+(d.passed?'PASS':'FAIL')+'</span></div>'+d.checks.map(c=>'<div class="step">'+(c.passed?'✅':'❌')+' <b>'+esc(c.name)+'</b><br><span class="empty mono">'+esc(c.detail)+'</span></div>').join('');await refresh();}

const PANELS=['evidence','hypotheses','predictions','inquiry','ledger','worldmodel','recognition','timeline','wmtimeline','revbyi','plife','provchains','eva','verdict','sequence'];
function clearMarks(){PANELS.forEach(id=>{const el=$(id);if(el)el.querySelectorAll('mark').forEach(m=>m.replaceWith(document.createTextNode(m.textContent)));});}
function highlightAll(){const q=$('globalSearch').value.trim();clearMarks();if(!q){$('searchCount').textContent='';return;}const rx=new RegExp(q.replace(/[.*+?^${}()|[\]\\]/g,'\\$&'),'gi');let c=0;
  PANELS.forEach(id=>{const root=$(id);if(!root)return;const w=document.createTreeWalker(root,NodeFilter.SHOW_TEXT,{acceptNode:n=>(n.parentNode&&n.parentNode.nodeName!=='MARK'&&n.nodeValue.trim())?1:2});const ns=[];while(w.nextNode())ns.push(w.currentNode);
    ns.forEach(n=>{if(!rx.test(n.nodeValue))return;rx.lastIndex=0;const f=document.createDocumentFragment();let last=0,mm;while((mm=rx.exec(n.nodeValue))){f.appendChild(document.createTextNode(n.nodeValue.slice(last,mm.index)));const mk=document.createElement('mark');mk.textContent=mm[0];f.appendChild(mk);last=mm.index+mm[0].length;c++;if(mm.index===rx.lastIndex)rx.lastIndex++;}f.appendChild(document.createTextNode(n.nodeValue.slice(last)));n.replaceWith(f);});});
  $('searchCount').textContent=c+' match'+(c===1?'':'es');}

document.addEventListener('keydown',e=>{if(e.target.tagName==='INPUT'||e.target.tagName==='TEXTAREA'){if(e.key==='Escape')e.target.blur();return;}if(e.key==='/'){e.preventDefault();$('globalSearch').focus();}else if(e.key==='n')runNext();else if(e.key==='a')runAll();else if(e.key==='r')resetCase();});
renderWizard(); loadSamples(); refresh();
</script>
</body>
</html>
"""
