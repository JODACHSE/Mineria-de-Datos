/** etapas/r4/territorial.js — filtros de la dimensión territorial (lee #page-data). */
(function () {
  const pageData = JSON.parse(document.getElementById("page-data").textContent);
  const TOTAL = pageData.total;
  const CROSS = pageData.cross;

  const selDept   = document.getElementById("filter-dept");
  const selRegion = document.getElementById("filter-region");
  const btnReset  = document.getElementById("filter-reset");
  const tbody     = document.getElementById("filter-tbody");
  const elCount   = document.getElementById("filter-count");
  const elTotal   = document.getElementById("filter-total");
  const elPct     = document.getElementById("filter-pct");
  const elLabel   = document.getElementById("filter-label");

  function fmt(n) { return n.toLocaleString("es-CO"); }

  function applyFilters() {
    const deptFil   = selDept.value;
    const regionFil = selRegion.value;

    let filteredN = 0, visibleRows = 0;
    for (const tr of tbody.querySelectorAll("tr[data-dept]")) {
      const dept   = tr.dataset.dept;
      const region = tr.dataset.region;

      const show = (!deptFil || dept === deptFil) && (!regionFil || region === regionFil);
      tr.classList.toggle("d-none", !show);
      if (show) {
        visibleRows++;
        const n = (CROSS[dept] || {}).n || 0;
        filteredN += n;
        tr.style.opacity = (deptFil && dept !== deptFil) ? "0.4" : "1";
      }
    }

    elCount.textContent = visibleRows;
    elTotal.textContent = fmt(filteredN);
    elPct.textContent   = TOTAL > 0 ? (filteredN / TOTAL * 100).toFixed(1) : "0.0";

    const parts = [];
    if (deptFil)   parts.push("Depto: " + deptFil);
    if (regionFil) parts.push("Región: " + regionFil);
    elLabel.textContent = parts.length ? "— Filtro activo: " + parts.join(" · ") : "";
  }

  selDept.addEventListener("change", applyFilters);
  selRegion.addEventListener("change", applyFilters);
  btnReset.addEventListener("click", () => {
    selDept.value = ""; selRegion.value = "";
    applyFilters();
  });
})();
