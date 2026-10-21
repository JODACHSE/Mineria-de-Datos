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

/** onClick (filtra un <select> por el punto clicado) + onHover (cursor pointer), compartidos
 *  por los gráficos R4 con filtro interactivo. `getLabel(element)` extrae el valor a filtrar. */
function clickFilterHandlers(filterId, getLabel) {
  return {
    onClick(_e, elements) {
      if (!elements.length) return;
      const label = getLabel(elements[0]);
      const sel = document.getElementById(filterId);
      if (sel) { sel.value = sel.value === label ? "" : label; sel.dispatchEvent(new Event("change")); }
    },
    onHover(_e, elements, chart) { chart.canvas.style.cursor = elements.length ? "pointer" : "default"; },
  };
}

/** Barra horizontal (un dataset, leyenda oculta) con filtro al hacer clic — patrón compartido
 *  por los gráficos R4 "top N categorías". */
function horizontalBarWithFilter(canvas, { labels, values, colors, filterId, tooltipLabel, tooltipAfterLabel }) {
  register(canvas, (p) => {
    const base = baseOptions(p);
    return {
      type: "bar",
      data: {
        labels,
        datasets: [{
          label: "Registros",
          data: values,
          backgroundColor: colors,
          borderRadius: 6,
          hoverBorderWidth: 2,
          hoverBorderColor: "#fff",
        }],
      },
      options: {
        ...base,
        indexAxis: "y",
        scales: {
          x: { ...base.scales.x, ticks: { ...base.scales.x.ticks, callback: (v) => v.toLocaleString("es-CO") } },
          y: { ...base.scales.y },
        },
        plugins: {
          ...base.plugins,
          legend: { display: false },
          tooltip: {
            ...base.plugins.tooltip,
            callbacks: tooltipAfterLabel ? { label: tooltipLabel, afterLabel: tooltipAfterLabel } : { label: tooltipLabel },
          },
        },
        ...clickFilterHandlers(filterId, (el) => labels[el.index]),
      },
    };
  });
}

/** Opciones comunes de los gráficos de dona R4 (leyenda abajo, tooltip con callbacks propios). */
function donutOptions(p, cutout, tooltipCallbacks) {
  return {
    responsive: true,
    maintainAspectRatio: false,
    cutout,
    plugins: {
      legend: {
        position: "bottom",
        labels: { color: p.text, font: { family: p.font, size: 12 }, usePointStyle: true, padding: 16 },
      },
      tooltip: {
        backgroundColor: p.tooltipBg, titleColor: p.text, bodyColor: p.text,
        borderColor: p.grid, borderWidth: 1,
        callbacks: tooltipCallbacks,
      },
    },
  };
}

/** Barra apilada (stack) multi-serie — patrón compartido por los gráficos R4 "por semestre". */
function stackedBarChart(canvas, { labels, datasets, colors, borderRadius = 6 }) {
  const fmt = (n) => n.toLocaleString("es-CO");
  register(canvas, (p) => {
    const base = baseOptions(p);
    return {
      type: "bar",
      data: {
        labels,
        datasets: datasets.map((ds, i) => ({
          label: ds.label,
          data: ds.values,
          backgroundColor: colors[i % colors.length],
          borderRadius: i === datasets.length - 1 ? borderRadius : 0,
          stack: "s",
        })),
      },
      options: {
        ...base,
        scales: {
          x: { ...base.scales.x, stacked: true },
          y: { ...base.scales.y, stacked: true, ticks: { ...base.scales.y.ticks, callback: (v) => fmt(v) } },
        },
        plugins: {
          ...base.plugins,
          tooltip: {
            ...base.plugins.tooltip,
            callbacks: { label: (ctx) => ` ${ctx.dataset.label}: ${fmt(ctx.raw)} registros` },
          },
        },
      },
    };
  });
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

// ---- R4 · Dimensión Poblacional ----------------------------------------

const R4_CROP_COLORS = ["#198754", "#0dcaf0", "#ffc107", "#fd7e14", "#6f42c1", "#dc3545"];

function r4CultivosChart(data) {
  const canvas = document.getElementById("chart-cultivos");
  if (!canvas || !data) return;
  const fmt = (n) => n.toLocaleString("es-CO");
  const colors = data.labels.map((_, i) => R4_CROP_COLORS[i % R4_CROP_COLORS.length]);
  horizontalBarWithFilter(canvas, {
    labels: data.labels,
    values: data.values,
    colors,
    filterId: "filter-cultivo",
    tooltipLabel: (ctx) => ` ${fmt(ctx.raw)} registros — ${data.pcts[ctx.dataIndex]} %`,
  });
}

function r4CicloChart(data) {
  const canvas = document.getElementById("chart-ciclo");
  if (!canvas || !data) return;
  const fmt = (n) => n.toLocaleString("es-CO");
  const colors = ["#198754", "#0dcaf0", "#ffc107", "#6c757d"];
  register(canvas, (p) => ({
    type: "doughnut",
    data: {
      labels: data.labels,
      datasets: [{
        data: data.values,
        backgroundColor: colors.slice(0, data.labels.length),
        hoverOffset: 10,
        borderWidth: 3,
        borderColor: p.tooltipBg,
      }],
    },
    options: donutOptions(p, "65%", {
      label: (ctx) => ` ${ctx.label}: ${fmt(ctx.raw)} registros (${data.pcts[ctx.dataIndex]} %)`,
    }),
  }));
}

function r4EstadoChart(data) {
  const canvas = document.getElementById("chart-estado");
  if (!canvas || !data) return;
  const fmt = (n) => n.toLocaleString("es-CO");
  const colors = ["#fd7e14", "#6f42c1", "#dc3545", "#0dcaf0"];
  register(canvas, (p) => ({
    type: "bar",
    data: {
      labels: data.labels,
      datasets: [{
        label: "Registros",
        data: data.values,
        backgroundColor: data.labels.map((_, i) => colors[i % colors.length]),
        borderRadius: 6,
        hoverBorderWidth: 2,
        hoverBorderColor: "#fff",
      }],
    },
    options: {
      ...baseOptions(p),
      plugins: {
        ...baseOptions(p).plugins,
        legend: { display: false },
        tooltip: {
          ...baseOptions(p).plugins.tooltip,
          callbacks: { label: (ctx) => ` ${fmt(ctx.raw)} registros (${data.pcts[ctx.dataIndex]} %)` },
        },
      },
    },
  }));
}

// ---- R4 · Dimensión Territorial ----------------------------------------

const R4_REGION_COLORS = {
  "Andina":    "#198754",
  "Caribe":    "#0dcaf0",
  "Orinoquía": "#fd7e14",
  "Pacífica":  "#0d6efd",
  "Amazonía":  "#6f42c1",
};
const R4_REGION_FALLBACK = "#6c757d";

function r4DeptChart(data) {
  const canvas = document.getElementById("chart-dept");
  if (!canvas || !data) return;
  const fmt = (n) => n.toLocaleString("es-CO");
  // Gradient of greens for the bar color (top = darkest)
  const shade = (i, total) => {
    const t = i / Math.max(total - 1, 1);
    const r = Math.round(25 + t * 80), g = Math.round(135 - t * 60), b = Math.round(84 + t * 30);
    return `rgb(${r},${g},${b})`;
  };
  const colors = data.labels.map((_, i) => shade(i, data.labels.length));
  horizontalBarWithFilter(canvas, {
    labels: data.labels,
    values: data.values,
    colors,
    filterId: "filter-dept",
    tooltipLabel: (ctx) => ` ${fmt(ctx.raw)} registros — ${data.pcts[ctx.dataIndex]} %`,
    tooltipAfterLabel: (ctx) => ` ${data.munis[ctx.dataIndex]} municipios con registros`,
  });
}

function r4RegionChart(data) {
  const canvas = document.getElementById("chart-region");
  if (!canvas || !data) return;
  const fmt = (n) => n.toLocaleString("es-CO");
  const colors = data.labels.map((l) => R4_REGION_COLORS[l] || R4_REGION_FALLBACK);
  register(canvas, (p) => ({
    type: "doughnut",
    data: {
      labels: data.labels,
      datasets: [{
        data: data.values,
        backgroundColor: colors,
        hoverOffset: 12,
        borderWidth: 3,
        borderColor: p.tooltipBg,
      }],
    },
    options: donutOptions(p, "60%", {
      label: (ctx) => ` ${fmt(ctx.raw)} registros (${data.pcts[ctx.dataIndex]} %)`,
      afterLabel: (ctx) => ` ${data.dept_counts[ctx.dataIndex]} departamentos`,
    }),
  }));
}

function r4DensityChart(data) {
  const canvas = document.getElementById("chart-density");
  if (!canvas || !data) return;
  const fmt = (n) => n.toLocaleString("es-CO");
  register(canvas, (p) => {
    const base = baseOptions(p);
    return {
      type: "bar",
      data: {
        labels: data.labels,
        datasets: [
          {
            label: "Registros / municipio",
            data: data.values,
            backgroundColor: "#198754",
            borderRadius: 6,
            yAxisID: "y",
          },
          {
            label: "Municipios únicos",
            data: data.munis,
            backgroundColor: "#0dcaf0",
            borderRadius: 6,
            yAxisID: "y2",
          },
        ],
      },
      options: {
        ...base,
        scales: {
          x: base.scales.x,
          y: { ...base.scales.y, position: "left", title: { display: true, text: "Registros/muni", color: p.text, font: { size: 11 } } },
          y2: { ...base.scales.y, position: "right", grid: { drawOnChartArea: false }, title: { display: true, text: "Municipios", color: p.text, font: { size: 11 } } },
        },
        plugins: {
          ...base.plugins,
          tooltip: {
            ...base.plugins.tooltip,
            callbacks: {
              label: (ctx) => ctx.datasetIndex === 0
                ? ` ${ctx.raw} registros/municipio`
                : ` ${fmt(ctx.raw)} municipios únicos`,
            },
          },
        },
      },
    };
  });
}

// ---- R4 · Dimensión Temporal -------------------------------------------

function r4TrendChart(data) {
  const canvas = document.getElementById("chart-trend");
  if (!canvas || !data) return;
  const fmt = (n) => n.toLocaleString("es-CO");
  register(canvas, (p) => {
    const base = baseOptions(p);
    return {
      type: "bar",
      data: {
        labels: data.labels,
        datasets: [
          {
            type: "bar",
            label: "Registros",
            data: data.values,
            backgroundColor: data.labels.map((_, i) => i === data.values.indexOf(Math.max(...data.values)) ? "#198754" : "#198754aa"),
            borderRadius: 6,
            order: 2,
          },
          {
            type: "line",
            label: "Var. interanual (%)",
            data: data.yoy,
            borderColor: "#ffc107",
            backgroundColor: "#ffc10722",
            pointBackgroundColor: data.yoy.map((v) => v > 0 ? "#198754" : v < 0 ? "#dc3545" : "#6c757d"),
            pointRadius: 5,
            pointHoverRadius: 7,
            tension: 0.3,
            fill: false,
            yAxisID: "y2",
            order: 1,
          },
        ],
      },
      options: {
        ...base,
        scales: {
          x: base.scales.x,
          y:  { ...base.scales.y, position: "left",
                title: { display: true, text: "Registros", color: p.text, font: { size: 11 } } },
          y2: { ...base.scales.y, position: "right", grid: { drawOnChartArea: false },
                title: { display: true, text: "Var. interanual (%)", color: p.text, font: { size: 11 } } },
        },
        plugins: {
          ...base.plugins,
          tooltip: {
            ...base.plugins.tooltip,
            callbacks: {
              label: (ctx) => ctx.datasetIndex === 0
                ? ` ${fmt(ctx.raw)} registros (${data.pcts[ctx.dataIndex]} %)`
                : ` Var. interanual: ${ctx.raw > 0 ? "+" : ""}${ctx.raw} %`,
            },
          },
        },
        ...clickFilterHandlers("filter-year", (el) => data.labels[el.index]),
      },
    };
  });
}

function r4StackedChart(data) {
  const canvas = document.getElementById("chart-stacked");
  if (!canvas || !data) return;
  stackedBarChart(canvas, { labels: data.labels, datasets: data.datasets, colors: ["#198754", "#0dcaf0", "#ffc107"], borderRadius: 6 });
}

function r4CultivoYearChart(data) {
  const canvas = document.getElementById("chart-cultivo-year");
  if (!canvas || !data) return;
  const fmt = (n) => n.toLocaleString("es-CO");
  register(canvas, (p) => ({
    type: "line",
    data: {
      labels: data.labels,
      datasets: data.datasets.map((ds, i) => ({
        label: ds.label,
        data: ds.values,
        borderColor: R4_CROP_COLORS[i % R4_CROP_COLORS.length],
        backgroundColor: R4_CROP_COLORS[i % R4_CROP_COLORS.length] + "22",
        tension: 0.35,
        pointRadius: 4,
        pointHoverRadius: 6,
        borderWidth: 2.5,
      })),
    },
    options: {
      ...baseOptions(p),
      interaction: { mode: "index", intersect: false },
      plugins: {
        ...baseOptions(p).plugins,
        tooltip: {
          ...baseOptions(p).plugins.tooltip,
          callbacks: { label: (ctx) => ` ${ctx.dataset.label}: ${fmt(ctx.raw)} registros` },
        },
      },
    },
  }));
}

// ---- R4 · Dimensión Relacional -----------------------------------------

const R4_REGION_LINE_COLORS = {
  "Andina":     "#198754",
  "Caribe":     "#0dcaf0",
  "Orinoquía":  "#ffc107",
  "Pacífica":   "#6f42c1",
  "Amazonía":   "#fd7e14",
};

function r4RelRegionChart(data) {
  const canvas = document.getElementById("chart-rel-region");
  if (!canvas || !data) return;
  const fmt = (n) => n.toLocaleString("es-CO");
  register(canvas, (p) => {
    const base = baseOptions(p);
    return {
      type: "bar",
      data: {
        labels: data.labels,
        datasets: data.datasets.map((ds, i) => ({
          label: ds.label,
          data: ds.values,
          backgroundColor: R4_CROP_COLORS[i % R4_CROP_COLORS.length],
          borderRadius: 4,
        })),
      },
      options: {
        ...base,
        scales: {
          x: base.scales.x,
          y: { ...base.scales.y, ticks: { ...base.scales.y.ticks, callback: (v) => fmt(v) } },
        },
        plugins: {
          ...base.plugins,
          tooltip: {
            ...base.plugins.tooltip,
            callbacks: { label: (ctx) => ` ${ctx.dataset.label}: ${fmt(ctx.raw)} registros` },
          },
        },
        ...clickFilterHandlers("filter-cultivo", (el) => data.datasets[el.datasetIndex].label),
      },
    };
  });
}

function r4RelSemestreChart(data) {
  const canvas = document.getElementById("chart-rel-semestre");
  if (!canvas || !data) return;
  stackedBarChart(canvas, { labels: data.labels, datasets: data.datasets, colors: ["#198754", "#0dcaf0", "#ffc107"], borderRadius: 4 });
}

function r4RelRegionYearChart(data) {
  const canvas = document.getElementById("chart-rel-region-year");
  if (!canvas || !data) return;
  const fmt = (n) => n.toLocaleString("es-CO");
  register(canvas, (p) => ({
    type: "line",
    data: {
      labels: data.labels,
      datasets: data.datasets.map((ds) => ({
        label: ds.label,
        data: ds.values,
        borderColor: R4_REGION_LINE_COLORS[ds.label] || "#6c757d",
        backgroundColor: (R4_REGION_LINE_COLORS[ds.label] || "#6c757d") + "22",
        tension: 0.35,
        pointRadius: 4,
        pointHoverRadius: 7,
        borderWidth: 2.5,
      })),
    },
    options: {
      ...baseOptions(p),
      interaction: { mode: "index", intersect: false },
      plugins: {
        ...baseOptions(p).plugins,
        tooltip: {
          ...baseOptions(p).plugins.tooltip,
          callbacks: { label: (ctx) => ` ${ctx.dataset.label}: ${fmt(ctx.raw)} registros` },
        },
      },
    },
  }));
}

export function initCharts() {
  if (!window.Chart) return;
  const node = document.getElementById("page-data");
  const data = node ? JSON.parse(node.textContent) : {};
  fsChart(data.fsChart);
  integracionChart(data.integracion);
  compareChart(data.qualityCompare);
  iteracionesChart(data.iteraciones);
  r4CultivosChart(data.cultivos);
  r4CicloChart(data.ciclo);
  r4EstadoChart(data.estado);
  r4DeptChart(data.dept);
  r4RegionChart(data.region);
  r4DensityChart(data.density);
  r4TrendChart(data.trend);
  r4StackedChart(data.stacked);
  r4CultivoYearChart(data.cultivo_year);
  r4RelRegionChart(data.region_cultivo);
  r4RelSemestreChart(data.cultivo_semestre);
  r4RelRegionYearChart(data.region_year);
  document.addEventListener("themechange", () => charts.forEach((redraw) => redraw()));
}
