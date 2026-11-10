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

/* ---------- Parameters ---------- */
function numericParams() {
  const keys = new Set();
  CASES.forEach(c => Object.entries(c.params || {})
    .forEach(([k, v]) => { if (typeof v === 'number' && isFinite(v)) keys.add(k); }));
  return [...keys].sort();
}
function spearman(x, y) {
  const rank = a => { const idx = [...a.keys()].sort((i, j) => a[i] - a[j]);
    const r = new Array(a.length); let i = 0;
    while (i < idx.length) { let j = i;
      while (j + 1 < idx.length && a[idx[j + 1]] === a[idx[i]]) j++;
      const v = (i + j) / 2 + 1; for (let k = i; k <= j; k++) r[idx[k]] = v; i = j + 1; }
    return r; };
  const rx = rank(x), ry = rank(y), n = x.length;
  const mx = rx.reduce((s, v) => s + v, 0) / n, my = ry.reduce((s, v) => s + v, 0) / n;
  let num = 0, dx = 0, dy = 0;
  for (let i = 0; i < n; i++) { num += (rx[i] - mx) * (ry[i] - my); dx += (rx[i] - mx) ** 2; dy += (ry[i] - my) ** 2; }
  return num / Math.sqrt(dx * dy || 1);
}
function renderParameters() {
  const endpoints = ['FOPT', 'FGPT', 'FWPT', 'FWIT', 'FGIT'];
  $('parameters').innerHTML =
    '<div class="panel"><div class="controls">' +
    '<label>End-point <select id="pa-endpoint">' + endpoints.map(k => `<option>${k}</option>`).join('') + '</select></label>' +
    '<label>Parameter <select id="pa-param"></select></label></div>' +
    '<div class="controls"><div id="pa-tornado" class="plot" style="height:380px"></div>' +
    '<div id="pa-scatter" class="plot" style="height:380px"></div></div></div>' +
    '<div class="panel"><table id="pa-table"></table></div>';
  const params = numericParams();
  $('pa-param').innerHTML = params.map(k => `<option>${esc(k)}</option>`).join('');
  const table = () => {
    const keys = [...new Set(CASES.flatMap(c => Object.keys(c.params || {})))].sort();
    $('pa-table').innerHTML = '<tr><th>case</th>' + keys.map(k => `<th>${esc(k)}</th>`).join('') + '</tr>' +
      CASES.map(c => '<tr><td>' + esc(c.name) + '</td>' +
        keys.map(k => { const v = (c.params || {})[k]; return `<td>${v == null ? '–' : esc(v)}</td>`; }).join('') + '</tr>').join('');
  };
  const draw = () => {
    const end = $('pa-endpoint').value;
    const ys = CASES.map(c => lastVal(c, end));
    const pairs = CASES.map((c, i) => ({ c, y: ys[i] })).filter(p => p.y != null);
    const cors = params.map(p => {
      const xs = pairs.map(pr => pr.c.params[p]);
      const yy = pairs.map(pr => pr.y);
      return xs.every(v => typeof v === 'number') && new Set(xs).size > 1 ? { p, rho: spearman(xs, yy) } : null;
    }).filter(Boolean).sort((a, b) => Math.abs(b.rho) - Math.abs(a.rho));
    Plotly.newPlot('pa-tornado', [{
      type: 'bar', orientation: 'h', x: cors.map(c => c.rho), y: cors.map(c => c.p),
      marker: { color: cors.map(c => c.rho >= 0 ? '#4fc3f7' : '#ef9a9a') },
    }], { ...LAYOUT, title: `Spearman ρ vs ${end}`, yaxis: { ...LAYOUT.yaxis, autorange: 'reversed' } },
      { displayModeBar: false });
    const p = $('pa-param').value;
    Plotly.newPlot('pa-scatter', [{
      x: pairs.map(pr => pr.c.params[p]), y: pairs.map(pr => pr.y),
      mode: 'markers', text: pairs.map(pr => pr.c.name),
      marker: { size: 9, color: '#4fc3f7' },
    }], { ...LAYOUT, xaxis: { ...LAYOUT.xaxis, title: p }, yaxis: { ...LAYOUT.yaxis, title: end } },
      { displayModeBar: false });
    table();
  };
  $('pa-endpoint').onchange = draw; $('pa-param').onchange = draw; draw();
}

/* ---------- RFT ---------- */
function renderRFT() {
  const wells = [...new Set(CASES.flatMap(c => (c.rft || []).map(s => s.well)))].sort();
  if (!wells.length) {
    $('rft').innerHTML = '<div class="panel muted">No RFT data available for these cases ' +
      '(cases run without RFT output, or .RFT files not found next to the summary files).</div>';
    return;
  }
  $('rft').innerHTML =
    '<div class="panel"><div class="controls">' +
    '<label>Well <select id="rft-well">' + wells.map(w => `<option>${esc(w)}</option>`).join('') + '</select></label>' +
    '<label>Date <select id="rft-date"></select></label></div>' +
    '<div class="controls" id="rft-cases"></div><div id="rft-plot" class="plot"></div></div>';
  const datesFor = w => [...new Set(CASES.flatMap(c => (c.rft || [])
    .filter(s => s.well === w).map(s => s.date)))].sort();
  const draw = () => {
    const w = $('rft-well').value, d = $('rft-date').value;
    const traces = [...document.querySelectorAll('.rft-case:checked')].map(cb => CASES[+cb.value])
      .map(c => (c.rft || []).find(s => s.well === w && s.date === d))
      .filter(Boolean).map(s => ({ name: s.well + ' ' + s.date, x: s.pressure, y: s.depth, mode: 'lines+markers' }));
    Plotly.newPlot('rft-plot', traces,
      { ...LAYOUT, yaxis: { ...LAYOUT.yaxis, autorange: 'reversed', title: 'depth' },
        xaxis: { ...LAYOUT.xaxis, title: 'pressure' } }, { responsive: true });
  };
  const refreshDates = () => {
    const w = $('rft-well').value;
    $('rft-date').innerHTML = datesFor(w).map(d => `<option>${d}</option>`).join('');
    $('rft-cases').innerHTML = '<label class="muted">Cases</label>' +
      CASES.map((c, i) => (c.rft || []).some(s => s.well === w) ?
        `<label><input type="checkbox" class="rft-case" value="${i}" checked> ${esc(c.name)}</label>` : '').join('');
    document.querySelectorAll('.rft-case').forEach(cb => cb.onchange = draw);
    draw();
  };
  $('rft-well').onchange = refreshDates; $('rft-date').onchange = draw;
  refreshDates();
}

/* ---------- QC ---------- */
function renderQC() {
  const hasQC = CASES.some(c => c.qc && Object.keys(c.qc).length);
  $('qc').innerHTML = hasQC
    ? '<div class="panel"><table id="qc-table"></table></div>' +
      '<div class="panel"><div id="qc-mb" class="plot"></div></div>' +
      '<div class="panel"><h3 class="muted">FIP by region</h3><div id="qc-fip"></div></div>'
    : '<div class="panel muted">No QC data (.PRT) found for these cases.</div>';
  if (!hasQC) return;
  $('qc-table').innerHTML =
    '<tr><th>case</th><th>MB error max (%)</th><th>timesteps</th><th>CPU (h)</th></tr>' +
    CASES.map(c => `<tr><td>${esc(c.name)}</td><td>${fmt(c.qc.mb_error_max, 2)}</td>` +
      `<td>${c.qc.timesteps ?? '–'}</td><td>${fmt(c.qc.cpu_hours, 3)}</td></tr>`).join('');
  Plotly.newPlot('qc-mb', [{
    type: 'bar', x: CASES.map(c => c.name), y: CASES.map(c => c.qc.mb_error_max ?? null),
    marker: { color: '#ef9a9a' },
  }], { ...LAYOUT, yaxis: { ...LAYOUT.yaxis, title: 'MB error max (%)' } }, { displayModeBar: false });
  const regions = [...new Set(CASES.flatMap(c => Object.keys((c.qc.fip_regions || {}))))].sort();
  $('qc-fip').innerHTML = '<div class="controls"><label>Region <select id="qc-region">' +
    regions.map(r => `<option>${r}</option>`).join('') + '</select></label></div><div id="qc-fip-plot" class="plot"></div>';
  const drawFip = () => {
    const r = $('qc-region').value;
    Plotly.newPlot('qc-fip-plot', ['oil_sm3', 'gas_sm3', 'water_sm3'].map(ph => ({
      type: 'bar', name: ph.replace('_sm3', ''), x: CASES.map(c => c.name),
      y: CASES.map(c => (c.qc.fip_regions || {})[r] ? c.qc.fip_regions[r][ph] ?? 0 : null),
    })), { ...LAYOUT, barmode: 'group', yaxis: { ...LAYOUT.yaxis, title: `region ${r} (SM3)` } },
      { displayModeBar: false });
  };
  $('qc-region').onchange = drawFip; drawFip();
}

/* ---------- boot ---------- */
$('meta').textContent =
  `${CASES.length} cases · generated ${BUNDLE.generated_utc} · source ${BUNDLE.source_folder}`;
renderOverview();
renderTimeSeries();
renderParameters();
renderRFT();
renderQC();
