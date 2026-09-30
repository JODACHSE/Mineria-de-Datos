/**
 * charts.js — gráficos Chart.js que toman sus colores de las variables CSS
 * de Bootstrap y se redibujan al cambiar de tema.
 */
const charts = [];

function palette() {
  const s = getComputedStyle(document.documentElement);
  const v = (n) => s.getPropertyValue(n).trim();
  return { success: v("--bs-success"), warning: v("--bs-warning"), info: v("--bs-info"), secondary: v("--bs-secondary"),
           text: v("--bs-secondary-color"), grid: v("--bs-border-color"), tooltipBg: v("--bs-tertiary-bg"), font: v("--bs-font-sans-serif") };
}

function baseOptions(p, extraY = {}) {
  return {
    responsive: true, maintainAspectRatio: false,
    interaction: { mode: "index", intersect: false },
    plugins: {
      legend: { labels: { color: p.text, font: { family: p.font, size: 12 }, usePointStyle: true } },
      tooltip: { backgroundColor: p.tooltipBg, titleColor: p.text, bodyColor: p.text, borderColor: p.grid, borderWidth: 1 },
    },
    scales: {
      x: { ticks: { color: p.text, maxTicksLimit: 10 }, grid: { color: p.grid } },
      y: { ticks: { color: p.text }, grid: { color: p.grid }, ...extraY },
    },
  };
}

/** Registra un gráfico y lo redibuja al cambiar de tema. `build(p)` devuelve la config. */
function register(canvas, build) {
  let chart = new Chart(canvas, build(palette()));
  charts.push(() => { chart.destroy(); chart = new Chart(canvas, build(palette())); });
  return () => chart;
}

function fsChart(data) {
  const canvas = document.getElementById("fs-chart");
  if (!canvas || !data) return;
  register(canvas, (p) => ({
    type: "line",
    data: {
      labels: data.labels,
      datasets: data.datasets.map((ds, i) => ({
        label: ds.label, data: ds.data,
        borderColor: [p.warning, p.success][i % 2], backgroundColor: [p.warning, p.success][i % 2] + "22",
        spanGaps: true, tension: .35, fill: i === 0, pointRadius: 0, pointHoverRadius: 5, borderWidth: 2.4,
      })),
    },
    options: baseOptions(p),
  }));
}

function integracionChart(data) {
  const canvas = document.getElementById("integracion-chart");
  if (!canvas || !data) return;
  const rows = data.rows;
  const year = Math.max(...rows.map((r) => r[0]));
  const last = rows.filter((r) => r[0] === year);
  register(canvas, (p) => ({
    type: "bar",
    data: {
      labels: last.map((r) => r[1]),
      datasets: [
        { label: `EVA ${year} (t)`, data: last.map((r) => r[2]), backgroundColor: p.warning, borderRadius: 4 },
        { label: `FAOSTAT ${year} (t)`, data: last.map((r) => r[3]), backgroundColor: p.success, borderRadius: 4 },
      ],
    },
    options: baseOptions(p),
  }));
}

function compareChart(data) {
  const canvas = document.getElementById("compare-chart");
  const select = document.getElementById("compare-dataset-select");
  if (!canvas || !data) return;
  const cap = (s) => s.charAt(0).toUpperCase() + s.slice(1);
  let key = select ? select.value : Object.keys(data)[0];

  const get = register(canvas, (p) => {
    const d = data[key];
    return {
      type: "bar",
      data: {
        labels: d.labels.map(cap),
        datasets: [
          { label: "Antes", data: d.antes.map((v) => v ?? 0), backgroundColor: p.warning, borderRadius: 4 },
          { label: "Después", data: d.despues.map((v) => v ?? 0), backgroundColor: p.success, borderRadius: 4 },
        ],
      },
      options: {
        ...baseOptions(p, { min: 0, max: 100 }),
        plugins: {
          ...baseOptions(p).plugins,
          tooltip: { ...baseOptions(p).plugins.tooltip, callbacks: { label(ctx) {
            const raw = data[key][ctx.datasetIndex === 0 ? "antes" : "despues"][ctx.dataIndex];
            return `${ctx.dataset.label}: ${raw === null ? "No aplica" : raw + "%"}`;
          } } },
        },
      },
    };
  });

  select?.addEventListener("change", (e) => {
    key = e.target.value;
    const chart = get();
    const d = data[key];
    chart.data.labels = d.labels.map(cap);
    chart.data.datasets[0].data = d.antes.map((v) => v ?? 0);
    chart.data.datasets[1].data = d.despues.map((v) => v ?? 0);
    chart.update();
  });
}

function iteracionesChart(data) {
  const canvas = document.getElementById("iteraciones-chart");
  if (!canvas || !data) return;
  const labels = [...data.labels.map((l) => `EVA ${l}`), ...data.labels.map((l) => `FAOSTAT ${l}`)];
  const acept = [...data.eva.aceptados, ...data.faostat.aceptados];
  const rev = [...data.eva.revision, ...data.faostat.revision];
  const fmt = (n) => n.toLocaleString("es-CO");
  register(canvas, (p) => {
    const base = baseOptions(p);
    return {
      type: "bar",
      data: {
        labels,
        datasets: [
          { label: "Aceptados", data: acept, backgroundColor: p.success, borderRadius: 4, stack: "s" },
          { label: "Enviados a revisión", data: rev, backgroundColor: p.warning, borderRadius: 4, stack: "s" },
        ],
      },
      options: {
        ...base,
        scales: { x: { ...base.scales.x, stacked: true }, y: { ...base.scales.y, stacked: true } },
        plugins: { ...base.plugins, tooltip: { ...base.plugins.tooltip, callbacks: {
          label: (ctx) => `${ctx.dataset.label}: ${fmt(ctx.raw)}`,
        } } },
      },
    };
  });
}

export function initCharts() {
  if (!window.Chart) return;
  const node = document.getElementById("page-data");
  const data = node ? JSON.parse(node.textContent) : {};
  fsChart(data.fsChart);
  integracionChart(data.integracion);
  compareChart(data.qualityCompare);
  iteracionesChart(data.iteraciones);
  document.addEventListener("themechange", () => charts.forEach((redraw) => redraw()));
}
