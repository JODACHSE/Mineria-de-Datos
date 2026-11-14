/** etapas/r4/temporal.js — filtros de la dimensión temporal (lee #page-data). */
(function () {
  const pageData = JSON.parse(document.getElementById("page-data").textContent);
  const TOTAL = pageData.total;
  const CROSS = pageData.cross;

  const selYear     = document.getElementById("filter-year");
  const selSemestre = document.getElementById("filter-semestre");
  const btnReset    = document.getElementById("filter-reset");
  const tbody       = document.getElementById("filter-tbody");
  const elCount     = document.getElementById("filter-count");
  const elTotal     = document.getElementById("filter-total");
  const elPct       = document.getElementById("filter-pct");
  const elLabel     = document.getElementById("filter-label");

  function fmt(n) { return n.toLocaleString("es-CO"); }

  const SEM_KEY = { "Primer semestre": "A", "Segundo semestre": "B", "Anual": "anual" };

  function applyFilters() {
    const yearFil = selYear.value;
    const semFil  = selSemestre.value;

    let filteredN = 0, visibleRows = 0;
    for (const tr of tbody.querySelectorAll("tr[data-year]")) {
      const year = tr.dataset.year;
      const show = !yearFil || year === yearFil;
      tr.classList.toggle("d-none", !show);
      if (show) {
        visibleRows++;
        const row = CROSS[year] || {};
        const n = semFil ? (row[SEM_KEY[semFil]] || 0) : (row.n || 0);
        filteredN += n;
      }
    }

    elCount.textContent = visibleRows;
    elTotal.textContent = fmt(filteredN);
    elPct.textContent   = TOTAL > 0 ? (filteredN / TOTAL * 100).toFixed(1) : "0.0";

    const parts = [];
    if (yearFil) parts.push("Año: " + yearFil);
    if (semFil)  parts.push("Semestre: " + semFil);
    elLabel.textContent = parts.length ? "— Filtro activo: " + parts.join(" · ") : "";
  }

  selYear.addEventListener("change", applyFilters);
  selSemestre.addEventListener("change", applyFilters);
  btnReset.addEventListener("click", () => {
    selYear.value = ""; selSemestre.value = "";
    applyFilters();
  });
})();
