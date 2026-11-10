/* global Plotly */
function $(id) { return document.getElementById(id); }
function esc(s) { return String(s).replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c])); }
function fmt(v, d = 3) { return v == null || isNaN(v) ? '–' : Number(v).toPrecision(d); }

const BUNDLE = JSON.parse($('bundle-data').textContent);
const CASES = BUNDLE.cases;

/* ---------- shared helpers ---------- */
function quantile(a, q) {
  if (!a || !a.length) return null;
  const s = [...a].sort((x, y) => x - y), pos = (s.length - 1) * q,
        lo = Math.floor(pos), hi = Math.ceil(pos);
  return s[lo] + (s[hi] - s[lo]) * (pos - lo);
}
const P10_HIGH = a => quantile(a, 0.9);   // P10 = optimistic (high)
const P50 = a => quantile(a, 0.5);
const P90_LOW = a => quantile(a, 0.1);
function lastVal(c, key) {
  const v = c.vectors[key]; if (!v) return null;
  for (let i = v.data.length - 1; i >= 0; i--) if (v.data[i] != null && !isNaN(v.data[i])) return v.data[i];
  return null;
}
function vectorGroups() {  // FIELD keys, WELL keys grouped by type, others
  const g = { FIELD: [], WELL: {}, OTHER: [] };
  for (const key of Object.keys(CASES[0].vectors)) {
    if (key === 'TIME' || key === 'DATE') continue;
    if (/^F/.test(key)) g.FIELD.push(key);
    else if (/^W[A-Z]+:/.test(key)) { const t = key.split(':')[0]; (g.WELL[t] = g.WELL[t] || []).push(key); }
    else g.OTHER.push(key);
  }
  return g;
}
const LAYOUT = {
  paper_bgcolor: '#1a2027', plot_bgcolor: '#1a2027',
  font: { color: '#e8eaed', size: 12 },
  margin: { l: 60, r: 20, t: 40, b: 40 },
  xaxis: { gridcolor: '#2a323c' }, yaxis: { gridcolor: '#2a323c' },
  legend: { orientation: 'h', y: -0.2 },
};

/* ---------- tabs ---------- */
document.querySelectorAll('#tabs button').forEach(btn => btn.onclick = () => {
  document.querySelectorAll('#tabs button').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  btn.classList.add('active'); $(btn.dataset.tab).classList.add('active');
});

/* ---------- Overview ---------- */
function renderOverview() {
  const rows = CASES.map(c => ({
    name: c.name, realization: c.realization,
    FOPT: lastVal(c, 'FOPT'), FGPT: lastVal(c, 'FGPT'), FWPT: lastVal(c, 'FWPT'),
    FGIT: lastVal(c, 'FGIT'), FWIT: lastVal(c, 'FWIT'),
    FPR: lastVal(c, 'FPR'), mb: c.qc && c.qc.mb_error_max, nts: c.qc && c.qc.timesteps,
  }));
  $('overview').innerHTML =
    '<div class="panel"><table id="ov-table"><thead><tr>' +
    Object.keys(rows[0]).map(h => `<th>${esc(h)}</th>`).join('') +
    '</tr></thead><tbody>' +
    rows.map(r => '<tr>' + Object.keys(r).map(h =>
      (h === 'name' || h === 'realization') ? `<td>${esc(r[h])}</td>`
      : `<td>${r[h] == null ? '–' : fmt(r[h], 4)}</td>`).join('') + '</tr>').join('') +
    '</tbody></table></div>' +
    '<div class="panel"><div class="controls"><label>End-point ' +
    '<select id="ov-endpoint">' + ['FOPT', 'FGPT', 'FWPT', 'FWIT', 'FGIT'].map(k => `<option>${k}</option>`).join('') +
    '</select></label><span class="muted" id="ov-stats"></span></div><div id="ov-rank" class="plot"></div></div>';
  const draw = () => {
    const key = $('ov-endpoint').value;
    const pts = CASES.map(c => ({ name: c.name, v: lastVal(c, key) })).filter(p => p.v != null)
                     .sort((a, b) => a.v - b.v);
    const vals = pts.map(p => p.v);
    $('ov-stats').textContent = vals.length > 1 ?
      `P90 ${fmt(P90_LOW(vals))} · P50 ${fmt(P50(vals))} · P10 ${fmt(P10_HIGH(vals))}` : '';
    Plotly.newPlot('ov-rank', [{
      type: 'bar', orientation: 'h',
      x: pts.map(p => p.v), y: pts.map(p => p.name),
      marker: { color: '#4fc3f7' }, text: pts.map(p => fmt(p.v, 4)), textposition: 'auto',
    }], { ...LAYOUT, yaxis: { ...LAYOUT.yaxis, autorange: 'reversed' },
         xaxis: { ...LAYOUT.xaxis, title: key } }, { displayModeBar: false });
  };
  $('ov-endpoint').onchange = draw; draw();
}

/* ---------- Time Series ---------- */
function renderTimeSeries() {
  const groups = vectorGroups();
  $('timeseries').innerHTML =
    '<div class="panel"><div class="controls">' +
    '<label>Vector <select id="ts-vector"></select></label>' +
    '<label><input type="checkbox" id="ts-log"> log Y</label>' +
    '<label><input type="checkbox" id="ts-date"> dates on X</label>' +
    '<button class="action" id="ts-csv">Export CSV</button></div>' +
    '<div class="controls" id="ts-cases"></div>' +
    '<div id="ts-plot" class="plot"></div></div>';
  const sel = $('ts-vector');
  const opt = k => `<option value="${esc(k)}">${esc(k)}</option>`;
  sel.innerHTML = groups.FIELD.map(opt).join('') +
    Object.keys(groups.WELL).sort().flatMap(t => groups.WELL[t]).map(opt).join('') +
    groups.OTHER.map(opt).join('');
  $('ts-cases').innerHTML = '<label class="muted">Cases</label>' + CASES.map((c, i) =>
    `<label><input type="checkbox" class="ts-case" value="${i}" ${i < 2 ? 'checked' : ''}> ${esc(c.name)}</label>`).join('');
  const draw = () => {
    const key = sel.value, useDate = $('ts-date').checked;
    const traces = [...document.querySelectorAll('.ts-case:checked')].map(cb => CASES[+cb.value])
      .filter(c => c.vectors[key]).map(c => ({
        name: c.name,
        x: useDate ? c.vectors.DATE : c.vectors.TIME,
        y: c.vectors[key].data, mode: 'lines',
      }));
    Plotly.newPlot('ts-plot', traces, {
      ...LAYOUT, yaxis: { ...LAYOUT.yaxis, type: $('ts-log').checked ? 'log' : 'linear' },
      xaxis: { ...LAYOUT.xaxis, title: useDate ? 'date' : 'days' },
    }, { responsive: true });
  };
  ['ts-vector', 'ts-log', 'ts-date'].forEach(id => { $(id).onchange = draw; });
  document.querySelectorAll('.ts-case').forEach(cb => cb.onchange = draw);
  $('ts-csv').onclick = () => {
    const key = sel.value;
    const lines = ['CASE,TIME,DATE,' + key];
    [...document.querySelectorAll('.ts-case:checked')].map(cb => CASES[+cb.value])
      .filter(c => c.vectors[key]).forEach(c =>
        c.vectors.TIME.forEach((t, i) => lines.push([c.name, t, c.vectors.DATE[i], c.vectors[key].data[i]].join(','))));
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob([lines.join('\n')], { type: 'text/csv' }));
    a.download = key.replace(/[^A-Za-z0-9_-]/g, '_') + '.csv'; a.click();
  };
  draw();
}

/* ---------- boot ---------- */
$('meta').textContent =
  `${CASES.length} cases · generated ${BUNDLE.generated_utc} · source ${BUNDLE.source_folder}`;
renderOverview();
renderTimeSeries();
window.DASH = { renderParameters: () => {}, renderRFT: () => {}, renderQC: () => {} };
