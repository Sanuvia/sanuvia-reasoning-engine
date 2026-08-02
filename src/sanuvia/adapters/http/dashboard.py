"""The dashboard page, embedded as a string (no static-file packaging needed).

An internal engineering review dashboard for the Persistent Reasoning Core — not
a product UI. The submission form authors a complete, structured canonical
EvidenceRecord (no free-text parsing). Work is organised into Test Cases with a
sample library, import/export, an engineering summary, a step timeline, review
report, notes, tags, comparison, and search. Responsive for phone review.
"""

from __future__ import annotations

INDEX_HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Sanuvia PRC — Engineering Review Harness</title>
<style>
  :root { --fg:#111827; --muted:#6b7280; --line:#d1d5db; --bg:#f9fafb; --card:#fff;
          --accent:#0f766e; --bar:#1d4ed8; --pass:#15803d; --fail:#b91c1c; }
  * { box-sizing: border-box; }
  body { margin:0; font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
         color:var(--fg); background:var(--bg); font-size:15px; line-height:1.4; }
  header { background:#0b1220; color:#e5e7eb; padding:12px 16px; }
  header h1 { margin:0; font-size:16px; font-weight:600; }
  header p { margin:4px 0 0; font-size:12px; color:#9ca3af; }
  .wrap { max-width:1100px; margin:0 auto; padding:16px; }
  .card { background:var(--card); border:1px solid var(--line); border-radius:8px; padding:12px 14px; margin:12px 0; }
  .card h2 { margin:0 0 8px; font-size:13px; text-transform:uppercase; letter-spacing:.04em;
             color:var(--accent); border-bottom:1px solid var(--line); padding-bottom:6px; }
  label { display:block; font-size:12px; color:var(--muted); margin:8px 0 2px; }
  input, select, textarea, button { font:inherit; font-size:14px; }
  input, select, textarea { width:100%; padding:6px 8px; border:1px solid var(--line); border-radius:6px; background:#fff; }
  input:disabled { background:#f3f4f6; color:var(--muted); }
  textarea { min-height:52px; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
  .row { display:grid; grid-template-columns:1fr 1fr 1fr; gap:10px; }
  .row2 { display:grid; grid-template-columns:1fr 1fr; gap:10px; }
  .btns { display:flex; flex-wrap:wrap; gap:8px; margin-top:12px; }
  button { padding:8px 12px; border:1px solid var(--line); border-radius:6px; background:#fff; cursor:pointer; }
  button.sm { padding:4px 8px; font-size:12px; }
  button.primary { background:var(--accent); color:#fff; border-color:var(--accent); }
  button.warn { background:#fff; color:var(--fail); border-color:var(--fail); }
  .meta { display:grid; grid-template-columns:repeat(4,1fr); gap:8px; }
  .meta div { background:var(--bg); border:1px solid var(--line); border-radius:6px; padding:6px 8px; }
  .meta b { display:block; font-size:11px; color:var(--muted); font-weight:500; text-transform:uppercase; }
  table { width:100%; border-collapse:collapse; font-size:13px; }
  th, td { text-align:left; padding:4px 6px; border-bottom:1px solid var(--line); vertical-align:top; }
  th { color:var(--muted); font-weight:600; font-size:11px; text-transform:uppercase; }
  code, .mono { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size:12.5px; }
  .empty { color:var(--muted); font-style:italic; font-size:13px; }
  .bar { background:#e5e7eb; border-radius:4px; height:12px; overflow:hidden; }
  .bar > span { display:block; height:100%; background:var(--bar); }
  pre { background:#0b1220; color:#e5e7eb; padding:12px; border-radius:8px; overflow:auto; max-height:520px; font-size:12px; }
  details summary { cursor:pointer; color:var(--muted); font-size:12px; margin-top:6px; }
  .pill { display:inline-block; padding:2px 8px; border-radius:999px; font-size:12px; font-weight:600; }
  .pill.pass,.pill.ran { background:#dcfce7; color:var(--pass); }
  .pill.fail { background:#fee2e2; color:var(--fail); }
  .pill.pending { background:#fef9c3; color:#854d0e; }
  .tag { display:inline-block; background:#e0e7ff; color:#3730a3; padding:1px 7px; border-radius:999px; font-size:11px; margin:2px 4px 2px 0; }
  .check { padding:6px 0; border-bottom:1px solid var(--line); }
  .mermaid { background:#fff; border:1px solid var(--line); border-radius:8px; padding:8px; overflow:auto; }
  .step { border:1px solid var(--line); border-radius:6px; padding:6px 8px; margin:4px 0; cursor:pointer; font-size:13px; }
  .step:hover { background:#f0fdfa; }
  .sample { border:1px solid var(--line); border-radius:6px; padding:8px; margin:6px 0; }
  @media (max-width:720px){ .row,.row2{grid-template-columns:1fr;} .meta{grid-template-columns:1fr 1fr;} }
</style>
</head>
<body>
<header>
  <h1>Sanuvia — Persistent Reasoning Core · Engineering Review Harness</h1>
  <p>Validates the reasoning engine in isolation. Input is a structured canonical EvidenceRecord — no free-text parsing, no NLU. Not the Sanuvia product; not the Phase 1 conversation experience.</p>
</header>
<div class="wrap">

  <div class="card">
    <h2>Test Cases</h2>
    <label>Active test case — one deterministic reasoning experiment. Switching refreshes every panel.</label>
    <select id="testcase" onchange="selectCase()"></select>
    <div class="btns">
      <button onclick="newCase()">New</button>
      <button onclick="duplicateCase()">Duplicate</button>
      <button onclick="renameCase()">Rename</button>
      <button onclick="saveCase()">Save</button>
      <span id="saveNote" class="empty"></span>
    </div>
    <div class="row2" style="margin-top:10px">
      <div><label>Search (name, evidence text, hypothesis, tag, date)</label><input id="search" placeholder="e.g. distance" onkeydown="if(event.key==='Enter')doSearch()"></div>
      <div><label>Filter tags (comma-sep)</label><input id="searchTags" placeholder="Regression"></div>
    </div>
    <div class="btns"><button onclick="doSearch()">Search</button></div>
    <div id="searchResults"></div>
  </div>

  <div class="card">
    <h2>Sample Library <span class="empty">(static engineering assets — not engine-generated)</span></h2>
    <div id="samples"><span class="empty">loading…</span></div>
  </div>

  <div class="card">
    <h2>Import / Export</h2>
    <div class="btns">
      <button onclick="exportTestCase()">Export Test Case (JSON)</button>
      <button onclick="$('importFile').click()">Import Test Case (JSON)</button>
      <input id="importFile" type="file" accept="application/json,.json" style="display:none" onchange="importTestCase(event)">
      <button onclick="exportArtifact('/api/export/trace','markdown','text/markdown')">Export Trace (.md)</button>
      <button onclick="exportArtifact('/api/export/graph-mermaid','mermaid','text/plain')">Export Graph (.mmd)</button>
      <button onclick="exportArtifact('/api/export/graph-dot','dot','text/vnd.graphviz')">Export Graphviz (.dot)</button>
      <button onclick="exportArtifact('/api/export/report','markdown','text/markdown')">Export Review Report (.md)</button>
    </div>
  </div>

  <div class="card">
    <h2>Add EvidenceRecord (canonical, structured)</h2>
    <div class="row">
      <div><label>Evidence ID</label><input id="evid" value="auto (evidence-N)" disabled></div>
      <div><label>Subject ID</label><input id="subject" value="—" disabled></div>
      <div><label>Timestamp / sequence position</label><input id="tspos" value="auto (deterministic)" disabled></div>
    </div>
    <label>Observed content (RawObservation)</label>
    <textarea id="content">partner went quiet and changed the subject during a disagreement</textarea>
    <div class="row">
      <div><label>Evidence class</label>
        <select id="evidence_class">
          <option>behavioural</option><option>narrative</option><option>reflective</option>
          <option>contradictory</option><option>missing</option><option>failed_acquisition</option>
        </select></div>
      <div><label>Source</label><input id="source" value="reflection:session-1"></div>
      <div><label>Classification status</label><input id="cstatus" value="provisional"></div>
    </div>
    <div class="row">
      <div><label>Evidence reliability (0–1)</label><input id="reliability" type="number" min="0" max="1" step="0.05" value="0.7"></div>
      <div><label>Classification confidence</label><input id="cc" type="number" min="0" max="1" step="0.05" value="0.9"></div>
      <div><label>Provenance confidence</label><input id="pc" type="number" min="0" max="1" step="0.05" value="0.9"></div>
    </div>
    <label>Metadata (one <code>key=value</code> per line, optional)</label>
    <textarea id="metadata">channel=written</textarea>
    <label style="margin-top:10px"><b>Structured appraisal</b> — which hypotheses this evidence bears on (reviewer-authored, not extracted)</label>
    <div class="row">
      <div><label>Supports (ids, comma-sep)</label><input id="supports" placeholder="H_need_for_reassurance"></div>
      <div><label>Contradicts (ids, comma-sep)</label><input id="contradicts" placeholder=""></div>
      <div><label>Proposals (id | statement | support)</label>
        <textarea id="proposals">H_conflict_avoidance | tends to avoid conflict | 0.4
H_need_for_reassurance | seeks reassurance | 0.4</textarea></div>
    </div>
    <div class="btns">
      <button onclick="addEvidence()">Add to Sequence</button>
      <button class="primary" onclick="addAndRun()">Add &amp; Run</button>
      <button onclick="runNext()">Run Next Step</button>
      <button onclick="runAll()">Run Full Sequence</button>
      <button class="warn" onclick="resetCase()">Reset Test Case</button>
      <button onclick="loadExit()">Run Exit Test</button>
    </div>
  </div>

  <div class="card"><h2>Engineering Summary</h2><div class="meta" id="summary"></div><div id="exitpill" style="margin-top:8px"></div></div>
  <div class="card"><h2>Evidence Sequence</h2><div id="sequence"></div></div>

  <div class="card">
    <h2>Step Timeline <span class="empty" id="viewingStep"></span></h2>
    <div class="btns"><button class="sm" onclick="viewLatest()">Latest</button></div>
    <div id="timeline"></div>
  </div>

  <div class="card">
    <h2>Tags &amp; Reviewer Notes <span class="empty">(review metadata — never sent to the engine)</span></h2>
    <div id="tags"></div>
    <label>Tags (comma-sep)</label>
    <div class="row2"><div><input id="tagInput"></div><div><button onclick="setTags()">Set Tags</button></div></div>
    <div id="notes" style="margin-top:10px"></div>
    <label>Add note</label>
    <div class="row2"><div><input id="noteInput" placeholder="e.g. Unexpected uncertainty increase." onkeydown="if(event.key==='Enter')addNote()"></div><div><button onclick="addNote()">Add Note</button></div></div>
  </div>

  <div class="card">
    <h2>Comparison Mode <span class="empty">(regression review)</span></h2>
    <div class="row2">
      <div><label>Test Case A</label><select id="cmpA"></select></div>
      <div><label>Test Case B</label><select id="cmpB"></select></div>
    </div>
    <div class="btns"><button onclick="compareCases()">Compare</button></div>
    <div id="compare"></div>
  </div>

  <div class="card"><h2>Evidence (recorded)</h2><div id="evidence"></div></div>
  <div class="card"><h2>Current World Model</h2><div id="worldmodel"></div></div>
  <div class="card"><h2>Active Hypotheses</h2><div id="hypotheses"></div></div>
  <div class="card"><h2>Hypothesis Support</h2><div id="support"></div></div>
  <div class="card"><h2>Predictions</h2><div id="predictions"></div></div>
  <div class="card"><h2>Inquiry</h2><div id="inquiry"></div></div>
  <div class="card"><h2>Revision Events (last step)</h2><div id="revevents"></div></div>
  <div class="card"><h2>Revision Ledger</h2><div id="ledger"></div></div>
  <div class="card"><h2>Model Uncertainty</h2><div id="uncertainty"></div></div>
  <div class="card"><h2>Provenance</h2><div id="provenance"></div></div>
  <div class="card"><h2>Recognition Conditions</h2><div id="recognition"></div></div>

  <div class="card">
    <h2>Reasoning Trace <span class="empty">(this test case · reference available)</span></h2>
    <div class="btns"><button onclick="loadTrace(false)">Load Trace (this test case)</button><button onclick="loadTrace(true)">Load Reference Trace</button></div>
    <pre id="trace" style="display:none"></pre>
  </div>
  <div class="card">
    <h2>Reasoning Lineage Graph <span class="empty">(this test case · reference available)</span></h2>
    <div class="btns"><button onclick="loadGraph(false)">Load Graph (this test case)</button><button onclick="loadGraph(true)">Load Reference Graph</button></div>
    <div id="graph"></div>
  </div>
  <div class="card"><h2>Exit Test</h2><div id="exit"><span class="empty">Not run yet.</span></div></div>
  <div class="card"><h2>Test Case Metadata</h2><div class="meta" id="meta"></div></div>

</div>

<script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js" onerror="window.__noMermaid=true"></script>
<script>
const $ = id => document.getElementById(id);
const esc = s => String(s).replace(/[&<>]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
const csv = s => s.split(',').map(x=>x.trim()).filter(Boolean);
async function getJSON(u){ const r = await fetch(u); return r.json(); }
async function postJSON(u,b){ const r = await fetch(u,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(b||{})}); return r.json(); }
function download(fn, text, mime){ const b=new Blob([text],{type:mime||'text/plain'}); const u=URL.createObjectURL(b); const a=document.createElement('a'); a.href=u; a.download=fn; a.click(); URL.revokeObjectURL(u); }

function table(cols, rows){
  if(!rows.length) return '<p class="empty">none</p>';
  return '<table><thead><tr>'+cols.map(c=>'<th>'+c+'</th>').join('')+'</tr></thead><tbody>'+
    rows.map(r=>'<tr>'+r.map(c=>'<td class="mono">'+c+'</td>').join('')+'</tr>').join('')+'</tbody></table>';
}

function evidenceBody(){
  const proposals = $('proposals').value.split('\n').map(l=>l.trim()).filter(Boolean).map(l=>{
    const [id,st,su] = l.split('|').map(x=>(x||'').trim());
    return {hypothesis_id:id, statement:st||id, initial_support: parseFloat(su||'0.4')};
  });
  const metadata = $('metadata').value.split('\n').map(l=>l.trim()).filter(Boolean).map(l=>{
    const i=l.indexOf('='); return i<0 ? [l,''] : [l.slice(0,i).trim(), l.slice(i+1).trim()];
  });
  return { content: $('content').value, evidence_class: $('evidence_class').value,
    reliability: parseFloat($('reliability').value), classification_confidence: parseFloat($('cc').value),
    source: $('source').value, provenance_confidence: parseFloat($('pc').value),
    classification_status: $('cstatus').value, metadata,
    supports: csv($('supports').value), contradicts: csv($('contradicts').value), proposals };
}

function render(s){
  const m = s.metadata;
  $('subject').value = m.subject;
  $('viewingStep').textContent = s.viewing_step ? ('viewing step '+s.viewing_step+' (historical)') : '';
  $('meta').innerHTML = [
    ['Test Case', m.test_case_name+' ('+m.test_case_id+')'],['Subject', m.subject],
    ['Created', m.created_at],['Sequence Length', m.sequence_length],
    ['Interactions Run', m.interactions_run],['WorldModel Version', m.world_model_version||'(none)'],
    ['Backend', m.backend],['Deterministic Mode', m.deterministic_mode]
  ].map(([k,v])=>'<div><b>'+k+'</b><span class="mono">'+esc(v)+'</span></div>').join('');

  const su = s.summary;
  $('summary').innerHTML = [
    ['Test Case', su.test_case_name],['EvidenceRecords', su.evidence_records],
    ['Interactions', su.interactions_executed],['WorldModel Versions', su.world_model_versions],
    ['Revision Events', su.revision_events],['Active Hypotheses', su.active_hypotheses],
    ['Predictions', su.predictions],['Inquiries', su.inquiries],
    ['Model Uncertainty', su.model_uncertainty==null?'—':su.model_uncertainty],
    ['Deterministic', su.deterministic?'yes':'no'],['Backend', su.backend],['Engine', su.engine_version]
  ].map(([k,v])=>'<div><b>'+k+'</b><span class="mono">'+esc(v)+'</span></div>').join('');
  $('exitpill').innerHTML = 'Exit Test: '+(su.exit_test_status==null
    ? '<span class="empty">not run</span>'
    : '<span class="pill '+(su.exit_test_status?'pass':'fail')+'">'+(su.exit_test_status?'PASS':'FAIL')+'</span>');

  const cases = s.test_cases || [];
  $('testcase').innerHTML = cases.map(x=>'<option value="'+x.id+'"'+(x.current?' selected':'')+'>'+
    esc(x.name)+' — '+x.interactions_run+'/'+x.sequence_length+' run</option>').join('');
  const opts = cases.map(x=>'<option value="'+x.id+'">'+esc(x.name)+'</option>').join('');
  $('cmpA').innerHTML = opts; $('cmpB').innerHTML = opts;

  $('sequence').innerHTML = (s.sequence && s.sequence.length)
    ? table(['#','status','class','reliability','evidence id','content'],
        s.sequence.map(x=>[x.position, x.ran?'<span class="pill ran">ran</span>':'<span class="pill pending">pending</span>',
          x.evidence_class, x.reliability, x.evidence_id||'—', esc(x.content)]))
    : '<p class="empty">no evidence added yet — fill the form and click “Add to Sequence”</p>';

  $('timeline').innerHTML = (s.timeline && s.timeline.length)
    ? s.timeline.map(t=>'<div class="step" onclick="viewStep('+t.step+')"><b>Step '+t.step+'</b> · '+
        (t.evidence_id||'—')+' ('+(t.evidence_class||'')+') ↓ '+t.hypotheses_created+' hyp created ↓ '+
        (t.world_model_version?('WorldModel '+t.world_model_version):'model holds')+' ↓ '+
        (t.inquiry?('inquiry '+t.inquiry):'no inquiry')+' ↓ '+t.predictions+' prediction(s) ↓ uncertainty '+
        (t.uncertainty_before==null?'—':t.uncertainty_before)+' → '+(t.uncertainty_after==null?'—':t.uncertainty_after)+'</div>').join('')
    : '<p class="empty">no steps run yet</p>';

  $('tags').innerHTML = (s.tags && s.tags.length) ? s.tags.map(t=>'<span class="tag">'+esc(t)+'</span>').join('') : '<span class="empty">no tags</span>';
  $('tagInput').value = (s.tags||[]).join(', ');
  $('notes').innerHTML = (s.notes && s.notes.length)
    ? s.notes.map((n,i)=>'<div class="step">'+esc(n)+' <button class="sm" onclick="removeNote('+i+')">remove</button></div>').join('')
    : '<span class="empty">no notes</span>';

  $('evidence').innerHTML = table(['id','class','reliability','status','source','content'],
    (s.evidence||[]).map(e=>[e.id, e.class, e.reliability, e.classification_status, esc(e.source), esc(e.content)]));

  const w = s.world_model;
  $('worldmodel').innerHTML = w ? table(['field','value'], [
    ['version', w.version],['model_uncertainty', w.model_uncertainty],['reasoning_system_id', w.reasoning_system_id],
    ['active_hypotheses', w.active_hypotheses.join(', ')||'—'],['active_predictions', w.active_predictions.join(', ')||'—'],
    ['active_inquiries', w.active_inquiries.join(', ')||'—'],['created_by_revision', w.created_by_revision||'—'],
    ['provenance_record_id', w.provenance_record_id||'—']]) : '<p class="empty">no committed model yet</p>';

  $('hypotheses').innerHTML = table(['hypothesis_id','support','statement','supporting','contradicting'],
    (s.hypotheses||[]).map(h=>[h.hypothesis_id, h.support, esc(h.statement), h.supporting_evidence.join(', ')||'—', h.contradicting_evidence.join(', ')||'—']));
  $('support').innerHTML = (s.hypotheses&&s.hypotheses.length) ? s.hypotheses.map(h=>
    '<div style="margin:6px 0"><div class="mono">'+h.hypothesis_id+' — '+h.support+'</div><div class="bar"><span style="width:'+Math.round(h.support*100)+'%"></span></div></div>').join('') : '<p class="empty">none</p>';
  $('predictions').innerHTML = table(['id','likelihood','trajectory','from hypotheses'],
    (s.predictions||[]).map(p=>[p.id, p.likelihood, p.trajectory_kind, p.from_hypotheses.join(', ')]));
  $('inquiry').innerHTML = (s.inquiries&&s.inquiries.length) ? s.inquiries.map(i=>
    '<div class="mono">'+i.id+' · status '+i.status+' · u='+i.current_uncertainty+'</div><blockquote class="empty">'+esc(i.statement)+'</blockquote>').join('') : '<p class="empty">none</p>';
  $('revevents').innerHTML = table(['id','outcome','affected','from→to','evidence'],
    (s.revision_events||[]).map(e=>[e.id, e.outcome, e.affected, (e.from_version||'∅')+' → '+(e.to_version||'—'), e.triggering_evidence.join(', ')]))
    + ((s.anomaly_resolutions&&s.anomaly_resolutions.length) ? '<p class="empty">anomalies: '+s.anomaly_resolutions.map(a=>a.id+' ('+a.disposition+')').join(', ')+'</p>' : '');
  $('ledger').innerHTML = table(['seq','outcome','affected','from→to','evidence'],
    (s.revision_ledger||[]).map(x=>[x.sequence_no, x.event.outcome, x.event.affected, (x.event.from_version||'∅')+' → '+x.event.to_version, x.event.triggering_evidence.join(', ')]));
  $('uncertainty').innerHTML = (s.model_uncertainty==null) ? '<p class="empty">none</p>'
    : '<div class="mono">before: '+(s.uncertainty_before==null?'—':s.uncertainty_before)+' → after: '+s.model_uncertainty+'</div>';
  $('provenance').innerHTML = s.provenance ? table(['field','value'],[['id', s.provenance.id],
    ['traces_to_evidence', s.provenance.traces_to_evidence.join(', ')],['traces_to_revisions', s.provenance.traces_to_revisions.join(', ')]]) : '<p class="empty">none</p>';
  $('recognition').innerHTML = (s.recognition_conditions&&s.recognition_conditions.length)
    ? table(['id','kind','description'], s.recognition_conditions.map(r=>[r.id, r.kind, esc(r.description)]))
    : '<p class="empty">none — Recognition Condition detection is deferred in Phase 0 (data model only)</p>';
}

async function refresh(){ render(await getJSON('/api/state')); }
function resetArtifacts(){ $('trace').style.display='none'; $('graph').innerHTML=''; $('exit').innerHTML='<span class="empty">Not run yet.</span>'; $('saveNote').textContent=''; $('compare').innerHTML=''; }

// evidence / stepping
async function addEvidence(){ render(await postJSON('/api/evidence/add', evidenceBody())); }
async function addAndRun(){ await postJSON('/api/evidence/add', evidenceBody()); render(await postJSON('/api/evidence/run-next')); }
async function runNext(){ render(await postJSON('/api/evidence/run-next')); }
async function runAll(){ render(await postJSON('/api/run-all')); }
async function resetCase(){ render(await postJSON('/api/reset')); resetArtifacts(); }
async function viewStep(n){ render(await postJSON('/api/step', {step:n})); }
async function viewLatest(){ refresh(); }

// test-case management
async function newCase(){ render(await postJSON('/api/test-cases/new')); resetArtifacts(); }
async function duplicateCase(){ render(await postJSON('/api/test-cases/duplicate')); resetArtifacts(); }
async function selectCase(){ render(await postJSON('/api/test-cases/select', {test_case_id: $('testcase').value})); resetArtifacts(); }
async function renameCase(){ const n = prompt('Rename test case'); if(n){ render(await postJSON('/api/test-cases/rename', {name:n})); } }
async function saveCase(){ await postJSON('/api/test-cases/save'); $('saveNote').textContent = 'saved'; }

// notes / tags
async function setTags(){ render(await postJSON('/api/tags/set', {tags: csv($('tagInput').value)})); }
async function addNote(){ const t=$('noteInput').value.trim(); if(!t) return; $('noteInput').value=''; render(await postJSON('/api/notes/add', {text:t})); }
async function removeNote(i){ render(await postJSON('/api/notes/remove', {index:i})); }

// samples
async function loadSamples(){ const d = await getJSON('/api/samples');
  $('samples').innerHTML = d.samples.map(s=>'<div class="sample"><b>'+esc(s.name)+'</b> <span class="empty">'+s.steps+' steps</span><br>'+
    '<span class="empty">'+esc(s.description)+'</span><br>'+(s.tags.map(t=>'<span class="tag">'+esc(t)+'</span>').join(''))+
    '<div class="btns"><button class="sm" onclick="loadSample(\''+s.id+'\')">Load</button></div></div>').join(''); }
async function loadSample(id){ render(await postJSON('/api/samples/load', {sample_id:id})); resetArtifacts(); }

// import / export
async function exportTestCase(){ const d = await getJSON('/api/export/test-case'); download(d.filename, JSON.stringify(d.test_case, null, 2), 'application/json'); }
async function importTestCase(ev){ const f = ev.target.files[0]; if(!f) return; const text = await f.text();
  try { const spec = JSON.parse(text); render(await postJSON('/api/import', {test_case: spec})); resetArtifacts(); }
  catch(e){ alert('Invalid JSON: '+e); } ev.target.value=''; }
async function exportArtifact(url, key, mime){ const d = await getJSON(url); download(d.filename, d[key], mime); }

// comparison
async function compareCases(){
  const d = await postJSON('/api/compare', {a: $('cmpA').value, b: $('cmpB').value});
  const row = (label,a,b)=>'<tr><td class="mono">'+label+'</td><td class="mono">'+esc(a)+'</td><td class="mono">'+esc(b)+'</td></tr>';
  $('compare').innerHTML = '<table><thead><tr><th>field</th><th>'+esc(d.a.name)+'</th><th>'+esc(d.b.name)+'</th></tr></thead><tbody>'+
    row('Evidence', d.evidence.a.join(', ')||'—', d.evidence.b.join(', ')||'—')+
    row('Hypotheses', d.hypotheses.a.map(h=>h[0]+'='+h[1]).join(', ')||'—', d.hypotheses.b.map(h=>h[0]+'='+h[1]).join(', ')||'—')+
    row('Predictions', d.predictions.a.join(', ')||'—', d.predictions.b.join(', ')||'—')+
    row('Revision count', d.revision_count.a, d.revision_count.b)+
    row('Model uncertainty', d.model_uncertainty.a==null?'—':d.model_uncertainty.a, d.model_uncertainty.b==null?'—':d.model_uncertainty.b)+
    row('Exit test', d.exit_test.a==null?'—':(d.exit_test.a?'PASS':'FAIL'), d.exit_test.b==null?'—':(d.exit_test.b?'PASS':'FAIL'))+
    '</tbody></table>';
}

// search
async function doSearch(){ const d = await postJSON('/api/search', {query: $('search').value, tags: csv($('searchTags').value)});
  $('searchResults').innerHTML = d.results.length ? d.results.map(r=>'<div class="step" onclick="selectFromSearch(\''+r.id+'\')"><b>'+esc(r.name)+'</b> '+
    r.tags.map(t=>'<span class="tag">'+esc(t)+'</span>').join('')+' <span class="empty">'+r.interactions_run+'/'+r.sequence_length+' run · '+esc(r.created_at.slice(0,10))+'</span></div>').join('')
    : '<p class="empty">no matches</p>'; }
async function selectFromSearch(id){ render(await postJSON('/api/test-cases/select', {test_case_id:id})); resetArtifacts(); }

// artifacts
async function loadTrace(reference){ const d = await getJSON(reference?'/api/reference-trace':'/api/trace'); $('trace').style.display='block'; $('trace').textContent = d.markdown; }
async function loadGraph(reference){ const d = await getJSON(reference?'/api/reference-graph':'/api/graph'); const el=$('graph');
  el.innerHTML = '<div class="mermaid">'+esc(d.mermaid)+'</div><details><summary>Mermaid source</summary><pre>'+esc(d.mermaid)+'</pre></details><details><summary>Graphviz DOT source</summary><pre>'+esc(d.dot)+'</pre></details>';
  if(window.mermaid && !window.__noMermaid){ try{ window.mermaid.initialize({startOnLoad:false}); await window.mermaid.run({nodes: el.querySelectorAll('.mermaid')}); } catch(e){ el.querySelector('.mermaid').textContent=d.mermaid; } }
  else { el.querySelector('.mermaid').textContent=d.mermaid; } }
async function loadExit(){ const d = await getJSON('/api/exit-test');
  $('exit').innerHTML = '<p>Result: <span class="pill '+(d.passed?'pass':'fail')+'">'+(d.passed?'PASS':'FAIL')+'</span></p>'+
    d.checks.map(c=>'<div class="check"><span class="pill '+(c.passed?'pass':'fail')+'">'+(c.passed?'PASS':'FAIL')+'</span> <b>'+esc(c.name)+'</b><br><span class="empty mono">'+esc(c.detail)+'</span></div>').join('');
  await refresh(); }

loadSamples(); refresh();
</script>
</body>
</html>
"""
