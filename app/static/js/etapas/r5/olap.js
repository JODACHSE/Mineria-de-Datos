/**
 * etapas/r5/olap.js — explorador OLAP de las vistas de R5 contra /api/r5/<vista>.
 * drill-down/roll-up = bajar/subir nivel · slice/dice = filtros · pivot = intercambiar filas y columnas.
 */
import { notify } from "../../core/notify.js";

// Paleta categórica (claro / oscuro), en orden fijo.
const SERIES = {
  light: ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"],
  dark: ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300", "#9085e9", "#e66767"],
};
const OTHER = { light: "#9a9994", dark: "#6f6e69" };

let cfg, meta, state, lastData;
const log = [];
const charts = {};

const $ = (id) => document.getElementById(id);
const theme = () => (document.documentElement.getAttribute("data-bs-theme") === "dark" ? "dark" : "light");
const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

function fmt(v, decimals = 0) {
  if (v === null || v === undefined) return "—";
  return Number(v).toLocaleString("es-CO", { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
}

const dimOf = (level) => meta.levels[level]?.dimension;
const label = (level) => meta.levels[level]?.label ?? level;
const hierarchyOf = (level) => meta.hierarchies[dimOf(level)] || [];
function child(level) { const h = hierarchyOf(level); const i = h.indexOf(level); return i >= 0 ? h[i + 1] : undefined; }
function parent(level) { const h = hierarchyOf(level); const i = h.indexOf(level); return i > 0 ? h[i - 1] : undefined; }

/** Color estable por miembro: depende del orden fijo del nivel, no del ranking. */
function colorFor(level, member, fallbackIndex) {
  const pal = SERIES[theme()];
  const list = level ? cfg.series[level] : null;
  const i = list ? list.indexOf(String(member)) : fallbackIndex;
  return i >= 0 && i < pal.length ? pal[i] : OTHER[theme()];
}

// --- Estado ---
function defaultState() {
  const filters = {};
  for (const f of cfg.config.filters) filters[f.level] = f.default || "";
  return { rows: cfg.config.rows, cols: cfg.config.cols || "", measure: cfg.config.measure,
           filters, drill: [], coherente: false };
}

function effectiveFilters() {
  const out = {};
  for (const [k, v] of Object.entries(state.filters)) if (v) out[k] = v;
  for (const d of state.drill) out[d.level] = d.value;
  if (state.coherente) out.coherencia = "Coherente";
  return out;
}

function toParams() {
  const p = new URLSearchParams({ rows: state.rows, cols: state.cols || "", measure: state.measure });
  for (const [k, v] of Object.entries(effectiveFilters())) p.append(`f_${k}`, v);
  return p;
}

function syncUrl() {
  const p = new URLSearchParams({ rows: state.rows, cols: state.cols || "", measure: state.measure });
  for (const [k, v] of Object.entries(state.filters)) if (v) p.set(`f_${k}`, v);
  if (state.drill.length) p.set("drill", state.drill.map((d) => `${d.level}:${d.value}`).join("|"));
  if (state.coherente) p.set("coh", "1");
  history.replaceState(null, "", `${location.pathname}?${p}${location.hash}`);
}

function stateFromUrl() {
  const q = new URLSearchParams(location.search);
  const ej = q.get("ej");
  if (ej && cfg.ejemplo_ids.includes(ej)) return exampleState(cfg.ejemplo_ids.indexOf(ej));
  if (!q.has("rows")) return null;
  const s = defaultState();
  if (meta.levels[q.get("rows")]) s.rows = q.get("rows");
  s.cols = meta.levels[q.get("cols")] ? q.get("cols") : "";
  if (cfg.medidas.includes(q.get("measure"))) s.measure = q.get("measure");
  for (const f of cfg.config.filters) s.filters[f.level] = q.get(`f_${f.level}`) || "";
  s.drill = (q.get("drill") || "").split("|").filter(Boolean).map((x) => {
    const i = x.indexOf(":"); return { level: x.slice(0, i), value: x.slice(i + 1) };
  }).filter((d) => meta.levels[d.level]);
  s.coherente = q.get("coh") === "1";
  return s;
}

function exampleState(i) {
  const e = cfg.ejemplos[i];
  const s = defaultState();
  for (const f of cfg.config.filters) s.filters[f.level] = (e.filters[f.level] || [""])[0];
  return { ...s, rows: e.rows, cols: e.cols || "", measure: e.measure, drill: e.drill.map((d) => ({ ...d })) };
}

function record(op, detail) {
  log.unshift({ op, detail, at: new Date().toLocaleTimeString("es-CO") });
  if (log.length > 12) log.pop();
}

// --- Operaciones ---
function drillDown(member) {
  const c = child(state.rows);
  if (!c) return;
  if (member !== undefined) {
    state.drill.push({ level: state.rows, value: String(member) });
    record("Drill-down", `${label(state.rows)} = ${member} → ${label(c)}`);
  } else {
    record("Drill-down", `${label(state.rows)} → ${label(c)} (todos los miembros)`);
  }
  state.rows = c;
  void run();
}

function rollUp() {
  const p = parent(state.rows);
  if (!p) return;
  const last = state.drill[state.drill.length - 1];
  if (last && last.level === p) state.drill.pop();
  record("Roll-up", `${label(state.rows)} → ${label(p)}`);
  state.rows = p;
  void run();
}

function jumpTo(level) {
  const h = hierarchyOf(state.rows);
  const from = h.indexOf(state.rows), to = h.indexOf(level);
  if (to === from) return;
  // Al subir se quitan los filtros de drill del nivel destino hacia abajo.
  if (to < from) state.drill = state.drill.filter((d) => dimOf(d.level) !== dimOf(level) || h.indexOf(d.level) < to);
  record(to < from ? "Roll-up" : "Drill-down", `${label(state.rows)} → ${label(level)}`);
  state.rows = level;
  void run();
}

function pivot() {
  if (!state.cols) return;
  record("Pivot", `Filas ${label(state.rows)} ⇄ Columnas ${label(state.cols)}`);
  [state.rows, state.cols] = [state.cols, state.rows];
  void run();
}

// --- Render ---
function renderControls() {
  $("olap-measure").value = state.measure;
  const colsSel = $("olap-cols");
  if (![...colsSel.options].some((o) => o.value === state.cols)) {
    colsSel.add(new Option(label(state.cols), state.cols));
  }
  colsSel.value = state.cols;
  for (const o of colsSel.options) o.disabled = !!o.value && dimOf(o.value) === dimOf(state.rows);
  for (const sel of document.querySelectorAll("[data-olap-filter]")) sel.value = state.filters[sel.dataset.olapFilter] || "";
  if ($("olap-coherente")) $("olap-coherente").checked = state.coherente;

  const ol = $("olap-levels");
  ol.replaceChildren();
  const h = hierarchyOf(state.rows);
  for (const lv of (h.length ? h : [state.rows])) {
    const li = document.createElement("li");
    li.className = "breadcrumb-item" + (lv === state.rows ? " active fw-semibold" : "");
    if (lv === state.rows) { li.textContent = label(lv); li.setAttribute("aria-current", "true"); }
    else {
      const a = document.createElement("a");
      a.href = "#"; a.textContent = label(lv);
      a.addEventListener("click", (e) => { e.preventDefault(); jumpTo(lv); });
      li.appendChild(a);
    }
    ol.appendChild(li);
  }
  $("olap-rollup").disabled = !parent(state.rows);
  $("olap-drill").disabled = !child(state.rows);
  $("olap-pivot").disabled = !state.cols;
}

function renderChips(operation) {
  const box = $("olap-chips");
  box.replaceChildren();
  const eff = effectiveFilters();
  if (!Object.keys(eff).length) { box.textContent = "sin filtros (todo el cubo)"; }
  for (const [k, v] of Object.entries(eff)) {
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className = "badge rounded-pill text-success-emphasis bg-success-subtle border border-success-subtle me-1 mb-1";
    const strong = document.createElement("strong");
    strong.textContent = v;
    const icon = document.createElement("i");
    icon.className = "bi bi-x";
    chip.append(`${label(k)} = `, strong, " ", icon);
    chip.title = "Quitar filtro";
    chip.addEventListener("click", () => {
      const di = state.drill.findIndex((d) => d.level === k);
      if (di >= 0) { state.drill = state.drill.slice(0, di); state.rows = k; record("Roll-up", `Quitar ${label(k)} = ${v}`); }
      else if (k === "coherencia") state.coherente = false;
      else state.filters[k] = "";
      void run();
    });
    box.appendChild(chip);
  }
  const extra = ` · Filas: ${label(state.rows)}` + (state.cols ? ` · Columnas: ${label(state.cols)}` : "");
  box.appendChild(document.createTextNode(extra));
  $("olap-op").textContent = operation;
}

function renderKpis(kpis) {
  const cards = document.querySelectorAll("#olap-kpis .card");
  kpis.forEach((k, i) => {
    const c = cards[i];
    if (!c) return;
    c.querySelector("[data-kpi-label]").textContent = k.label;
    c.querySelector("[data-kpi-value]").textContent = k.value;
    c.querySelector("[data-kpi-unit]").textContent = k.unit || "";
    c.querySelector("[data-kpi-detail]").textContent = k.detail || "";
  });
}

function baseOptions(unit, extra = {}) {
  const text = css("--bs-secondary-color"), grid = css("--bs-border-color-translucent") || css("--bs-border-color");
  return {
    responsive: true, maintainAspectRatio: false, animation: { duration: 300 },
    interaction: { mode: "index", intersect: false },
    plugins: {
      legend: { position: "bottom", labels: { color: text, usePointStyle: true, boxWidth: 8 } },
      tooltip: {
        backgroundColor: css("--bs-tertiary-bg"), titleColor: css("--bs-body-color"), bodyColor: css("--bs-body-color"),
        borderColor: css("--bs-border-color"), borderWidth: 1,
        callbacks: { label: (ctx) => ` ${ctx.dataset.label}: ${fmt(ctx.raw, unit.decimals)} ${unit.unit}` },
      },
    },
    scales: {
      x: { ticks: { color: text, autoSkip: true, maxRotation: 45 }, grid: { display: false } },
      y: { ticks: { color: text, callback: (v) => fmt(v) }, grid: { color: grid }, border: { display: false } },
    },
    ...extra,
  };
}

function draw(id, config) {
  charts[id]?.destroy();
  charts[id] = new Chart($(id), config);
}

const BAR = { borderRadius: 4, borderSkipped: "start", maxBarThickness: 28, borderWidth: 0 };

function renderChart1(m) {
  const mm = meta.measures[m.measure];
  const unit = { unit: m.unit, decimals: mm.decimals };
  const kind = cfg.config.chart1;
  const top = Math.min(m.rows.length, 20);
  const rows = m.rows.slice(0, top);
  let config;
  if (kind === "hbar" || !m.cols.length) {
    const opts = baseOptions(unit, { indexAxis: "y" });
    opts.plugins.legend.display = false;
    opts.scales.x = { ...opts.scales.y, ticks: { ...opts.scales.y.ticks } };
    opts.scales.y = { ticks: { color: css("--bs-secondary-color"), autoSkip: false }, grid: { display: false } };
    opts.interaction = { mode: "nearest", axis: "y", intersect: false };
    if (child(m.rows_level)) {
      opts.onClick = (_e, els) => { if (els.length) drillDown(rows[els[0].index]); };
      opts.onHover = (e, els) => { e.native.target.style.cursor = els.length ? "pointer" : "default"; };
    }
    config = { type: "bar", options: opts, data: { labels: rows, datasets: [{
      label: `${m.measure_label} (${m.unit})`, data: m.row_totals.slice(0, top),
      backgroundColor: SERIES[theme()][0], ...BAR }] } };
  } else {
    const cols = m.cols.slice(0, 8);
    const datasets = cols.map((c, j) => {
      const color = colorFor(m.cols_level, c, j);
      const data = m.cells.slice(0, top).map((r) => r[j]);
      return kind === "lines"
        ? { label: c, data, borderColor: color, backgroundColor: color, borderWidth: 2, pointRadius: 3, pointHoverRadius: 5, spanGaps: false, tension: 0 }
        : { label: c, data, backgroundColor: color, ...BAR };
    });
    config = { type: kind === "lines" ? "line" : "bar", options: baseOptions(unit), data: { labels: rows, datasets } };
  }
  draw("olap-chart1", config);
  const notes = [`${m.measure_label} · ${m.aggregation}`];
  if (m.rows.length > top) notes.push(`primeros ${top} de ${m.total_members} miembros`);
  if (m.cols.length > 8) notes.push(`8 primeras columnas de ${m.cols.length}`);
  $("olap-c1-note").textContent = notes.join(" · ");
}

function renderChart2(c) {
  const unit = { unit: c.unit, decimals: c.unit === "%" || c.unit === "índice" ? 1 : 0 };
  const series = (d, j) => colorFor(c.series_level, d.label, j);
  let config;
  if (c.type === "line") {
    config = { type: "line", options: baseOptions(unit), data: { labels: c.labels, datasets: c.datasets.map((d, j) => ({
      label: d.label, data: d.values, borderColor: series(d, j), backgroundColor: series(d, j),
      borderWidth: 2, pointRadius: 3, pointHoverRadius: 5, tension: 0 })) } };
  } else {
    const opts = baseOptions(unit);
    if (c.type === "stacked") {
      opts.scales.x.stacked = true;
      opts.scales.y = { ...opts.scales.y, stacked: true, max: 100 };
    }
    config = { type: "bar", options: opts, data: { labels: c.labels, datasets: c.datasets.map((d, j) => ({
      label: d.label, data: d.values, backgroundColor: series(d, j), ...BAR,
      ...(c.type === "stacked" ? { borderRadius: 0, borderWidth: { top: 2 }, borderColor: css("--bs-body-bg") } : {}) })) } };
  }
  draw("olap-chart2", config);
  $("olap-c2-note").textContent = c.note || "";
}

function renderMatrix(m) {
  const mm = meta.measures[m.measure];
  const nd = mm.decimals;
  const mode = m.additive ? (document.querySelector("input[name=olap-display]:checked")?.value || "valor") : "valor";
  for (const id of ["disp-fila", "disp-col"]) $(id).disabled = !m.additive || !m.cols.length;
  if (!m.additive || !m.cols.length) $("disp-valor").checked = true;

  const pct = (v, d) => (v === null || v === undefined || !d ? null : (100 * v) / d);
  const show = (v, rTot, cTot) => {
    if (mode === "fila") return pct(v, rTot);
    if (mode === "col") return pct(v, cTot);
    return v;
  };
  const dec = mode === "valor" ? nd : 1;
  const suffix = mode === "valor" ? "" : " %";

  const values = m.cols.length ? m.cells.flat() : m.row_totals;
  // Escala de un tono: desde 0 en medidas aditivas; mín–máx en tasas y cocientes.
  const present = values.filter((v) => v !== null);
  const max = Math.max(...present, 0);
  const min = m.additive ? 0 : Math.min(...present);
  const span = max - min || 1;
  const heat = (v) => (v === null ? "" : `background: color-mix(in srgb, var(--bs-success) ${Math.round(6 + 44 * Math.max(0, v - min) / span)}%, transparent);`);

  const canDrill = !!child(m.rows_level);
  // Solo nodos DOM y textContent: ningún dato del servidor se interpreta como HTML.
  const el = (tag, cls, text, attrs) => {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text !== undefined) n.textContent = text;
    for (const [k, v] of Object.entries(attrs || {})) n.setAttribute(k, v);
    return n;
  };
  const td = (text, cls, style) => el("td", `text-end font-monospace ${cls || ""}`.trim(), text, style ? { style } : undefined);
  const append = (parent, ...kids) => { for (const k of kids) parent.appendChild(k); return parent; };

  const caption = el("caption", "visually-hidden", `Matriz ${m.rows_label} por ${m.cols_label || "total"}`);

  const headRow = append(el("tr"),
    el("th", "", m.rows_label + (m.cols.length ? ` \\ ${m.cols_label}` : ""), { scope: "col" }),
    ...m.cols.map((c) => el("th", "text-end", c, { scope: "col" })),
    el("th", "text-end", "Total", { scope: "col" }));
  if (m.share_pct) headRow.appendChild(el("th", "text-end", "% del total", { scope: "col" }));
  const thead = append(el("thead", "table-light", undefined, { style: "position:sticky;top:0;z-index:1;" }), headRow);

  const tbody = el("tbody");
  m.rows.forEach((r, i) => {
    const th = el("th", "fw-normal", undefined, { scope: "row" });
    if (canDrill) {
      const btn = el("button", "btn btn-link btn-sm p-0 text-start text-decoration-none", undefined, { type: "button" });
      btn.appendChild(el("i", "bi bi-plus-square me-1"));
      btn.appendChild(document.createTextNode(String(r)));
      btn.addEventListener("click", () => drillDown(m.rows[i]));
      th.appendChild(btn);
    } else {
      th.textContent = String(r);
    }
    const tr = append(el("tr"), th);
    m.cols.forEach((_c, j) => {
      const v = m.cells[i][j];
      tr.appendChild(td(`${fmt(show(v, m.row_totals[i], m.col_totals[j]), dec)}${v === null ? "" : suffix}`, "", heat(v)));
    });
    const rt = mode === "fila" ? 100 : mode === "col" ? pct(m.row_totals[i], m.grand_total) : m.row_totals[i];
    tr.appendChild(td(`${fmt(rt, dec)}${suffix}`, "fw-semibold", m.cols.length ? "" : heat(m.row_totals[i])));
    if (m.share_pct) tr.appendChild(td(`${fmt(m.share_pct[i], 1)} %`));
    tbody.appendChild(tr);
  });

  const footRow = append(el("tr", "fw-semibold"), el("th", "", "Total de la selección", { scope: "row" }));
  m.cols.forEach((_c, j) => {
    const v = mode === "col" ? 100 : mode === "fila" ? pct(m.col_totals[j], m.grand_total) : m.col_totals[j];
    footRow.appendChild(td(`${fmt(v, dec)}${suffix}`));
  });
  footRow.appendChild(td(mode === "valor" ? fmt(m.grand_total, nd) : "100,0 %"));
  if (m.share_pct) footRow.appendChild(td("100,0 %"));

  $("olap-matrix").replaceChildren(caption, thead, tbody, append(el("tfoot"), footRow));

  const notes = [`${m.measure_label} en ${m.unit} · agregación: ${m.aggregation}`];
  if (mode === "fila") notes.push("denominador: total de cada fila");
  if (mode === "col") notes.push("denominador: total de cada columna");
  if (m.share_pct) notes.push(`«% del total»: denominador = ${m.share_denominator}`);
  if (!m.additive) notes.push("medida no aditiva: los totales se recalculan, no se suman");
  if (m.truncated) notes.push(`se muestran ${m.rows.length} de ${m.total_members} miembros`);
  $("olap-matrix-note").textContent = notes.join(" · ");

  $("olap-sql").textContent = `${m.sql}\n\n-- parámetros: ${JSON.stringify(m.params)}`;
  const items = log.map((l) => {
    const li = document.createElement("li");
    li.appendChild(el("strong", "", l.op));
    li.appendChild(document.createTextNode(` · ${l.detail} `));
    li.appendChild(el("span", "text-body-secondary", `(${l.at})`));
    return li;
  });
  $("olap-log").replaceChildren(...(items.length ? items : [el("li", "", "Sin operaciones todavía.")]));
}

function renderAll() {
  if (!lastData) return;
  renderChart1(lastData.matrix);
  renderChart2(lastData.chart2);
  renderMatrix(lastData.matrix);
}

// --- Red ---
let seq = 0;
async function run() {
  if (state.cols && dimOf(state.cols) === dimOf(state.rows)) state.cols = "";
  renderControls();
  syncUrl();
  const my = ++seq;
  try {
    const resp = await fetch(`${cfg.api}?${toParams()}`, { headers: { Accept: "application/json" } });
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.error || resp.statusText);
    if (my !== seq) return;
    lastData = data;
    renderChips(log[0] ? `${data.operation} · última operación: ${log[0].op}` : data.operation);
    renderKpis(data.kpis);
    renderAll();
  } catch (err) {
    notify(`No se pudo consultar el modelo: ${err.message}`, "danger");
  }
}

// --- Inicio ---
export function initOlap() {
  const node = $("olap-config");
  if (!node || !window.Chart) return;
  cfg = JSON.parse(node.textContent);
  meta = cfg.meta;
  state = stateFromUrl() || defaultState();

  for (const sel of document.querySelectorAll("[data-olap-filter]")) {
    sel.addEventListener("change", () => {
      state.filters[sel.dataset.olapFilter] = sel.value;
      const dims = new Set(Object.keys(effectiveFilters()).map(dimOf));
      record(dims.size >= 2 ? "Dice" : "Slice", `${label(sel.dataset.olapFilter)} = ${sel.value || "Todos"}`);
      void run();
    });
  }
  $("olap-measure").addEventListener("change", (e) => { state.measure = e.target.value; record("Medida", meta.measures[e.target.value].label); void run(); });
  $("olap-cols").addEventListener("change", (e) => { state.cols = e.target.value; record("Columnas", e.target.value ? label(e.target.value) : "sin columnas"); void run(); });
  $("olap-rollup").addEventListener("click", rollUp);
  $("olap-drill").addEventListener("click", () => drillDown());
  $("olap-pivot").addEventListener("click", pivot);
  $("olap-reset").addEventListener("click", () => { state = defaultState(); log.length = 0; record("Restablecer", "consulta base de la vista"); void run(); });
  $("olap-coherente")?.addEventListener("change", (e) => { state.coherente = e.target.checked; record("Dice", e.target.checked ? "solo filas coherentes" : "todas las filas"); void run(); });
  document.querySelectorAll("input[name=olap-display]").forEach((r) => r.addEventListener("change", () => lastData && renderMatrix(lastData.matrix)));
  document.querySelectorAll("[data-olap-example]").forEach((b) => b.addEventListener("click", () => {
    const i = cfg.ejemplo_ids.indexOf(b.dataset.olapExample);
    state = exampleState(i);
    record(cfg.ejemplo_ops[i], `ejemplo guiado: ${b.textContent.trim()}`);
    void run();
    $("explorador").scrollIntoView({ behavior: "smooth" });
  }));
  document.addEventListener("themechange", renderAll);
  void run();
}
