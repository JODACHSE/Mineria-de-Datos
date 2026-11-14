/** etapas/r6/charts.js — AUC por modelo y silueta por k (R6); se redibujan al cambiar de tema. */
const SERIES = {
  light: ["#2a78d6", "#eb6834", "#1baf7a"],
  dark: ["#3987e5", "#d95926", "#199e70"],
};
const MUTED = { light: "#b4b3ad", dark: "#5e5d58" };

const theme = () => (document.documentElement.getAttribute("data-bs-theme") === "dark" ? "dark" : "light");
const css = (n) => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const fmt = (v, d = 3) => Number(v).toLocaleString("es-CO", { minimumFractionDigits: d, maximumFractionDigits: d });
const charts = [];

function options(extra = {}) {
  const text = css("--bs-secondary-color");
  return {
    responsive: true, maintainAspectRatio: false, animation: { duration: 300 },
    plugins: {
      legend: { position: "bottom", labels: { color: text, usePointStyle: true, boxWidth: 8 } },
      tooltip: { backgroundColor: css("--bs-tertiary-bg"), titleColor: css("--bs-body-color"), bodyColor: css("--bs-body-color"),
                 borderColor: css("--bs-border-color"), borderWidth: 1,
                 callbacks: { label: (c) => ` ${c.dataset.label}: ${fmt(c.raw)}` } },
    },
    scales: {
      x: { ticks: { color: text }, grid: { display: false } },
      y: { ticks: { color: text, callback: (v) => fmt(v, 2) }, grid: { color: css("--bs-border-color-translucent") }, border: { display: false } },
    },
    ...extra,
  };
}

function draw(data) {
  charts.forEach((c) => c.destroy());
  charts.length = 0;
  const pal = SERIES[theme()];

  const evals = Object.values(data.evaluaciones);
  const modelos = evals[0].modelos.map((m) => m.modelo);
  const auc = options();
  auc.scales.y.min = 0.5;
  auc.scales.y.max = 0.85;
  charts.push(new Chart(document.getElementById("r6-auc"), {
    type: "bar", options: auc,
    data: {
      labels: evals.map((e) => e.nombre),
      datasets: modelos.map((m, i) => ({
        label: m, data: evals.map((e) => e.modelos[i].auc), backgroundColor: pal[i],
        borderRadius: 4, borderSkipped: "start", maxBarThickness: 36,
      })),
    },
  }));

  const ks = Object.keys(data.silueta);
  const sil = options();
  sil.plugins.legend.display = false;
  sil.plugins.tooltip.callbacks = { title: (i) => `k = ${i[0].label}`, label: (c) => ` Silueta: ${fmt(c.raw)}` };
  charts.push(new Chart(document.getElementById("r6-silueta"), {
    type: "bar", options: sil,
    data: {
      labels: ks,
      datasets: [{
        label: "Silueta media", data: ks.map((k) => data.silueta[k]),
        backgroundColor: ks.map((k) => (Number(k) === data.k ? pal[0] : MUTED[theme()])),
        borderRadius: 4, borderSkipped: "start", maxBarThickness: 36,
      }],
    },
  }));
}

export function initR6Charts() {
  const node = document.getElementById("r6-data");
  if (!node || !window.Chart) return;
  const data = JSON.parse(node.textContent);
  draw(data);
  document.addEventListener("themechange", () => draw(data));
}
