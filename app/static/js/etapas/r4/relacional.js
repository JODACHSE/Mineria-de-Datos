/** etapas/r4/relacional.js — filtros de la dimensión relacional (lee #page-data). */
(function () {
  const pageData = JSON.parse(document.getElementById("page-data").textContent);
  const TOTAL = pageData.total;
  const CROSS = pageData.cross;

  const selCultivo = document.getElementById("filter-cultivo");
  const selRegion  = document.getElementById("filter-region");
  const btnReset   = document.getElementById("filter-reset");
  const tbody      = document.getElementById("filter-tbody");
  const elCount    = document.getElementById("filter-count");
  const elTotal    = document.getElementById("filter-total");
  const elPct      = document.getElementById("filter-pct");
  const elLabel    = document.getElementById("filter-label");

  function fmt(n) { return n.toLocaleString("es-CO"); }

  function applyFilters() {
    const cultivoFil = selCultivo.value;
    const regionFil  = selRegion.value;

    let filteredN = 0, visibleRows = 0;
    for (const tr of tbody.querySelectorAll("tr[data-cultivo]")) {
      const cultivo = tr.dataset.cultivo;
      const region  = tr.dataset.region;
      const n       = Number.parseInt(tr.dataset.n, 10);

      const show = (!cultivoFil || cultivo === cultivoFil) && (!regionFil || region === regionFil);
      tr.classList.toggle("d-none", !show);
      if (show) { visibleRows++; filteredN += n; }
    }

    elCount.textContent = visibleRows;
    elTotal.textContent = fmt(filteredN);
    elPct.textContent   = TOTAL > 0 ? (filteredN / TOTAL * 100).toFixed(1) : "0.0";

    const parts = [];
    if (cultivoFil) parts.push("Cultivo: " + cultivoFil);
    if (regionFil)  parts.push("Región: " + regionFil);
    elLabel.textContent = parts.length ? "— Filtro activo: " + parts.join(" · ") : "";
  }

  selCultivo.addEventListener("change", applyFilters);
  selRegion.addEventListener("change", applyFilters);
  btnReset.addEventListener("click", () => {
    selCultivo.value = ""; selRegion.value = "";
    applyFilters();
  });
})();
