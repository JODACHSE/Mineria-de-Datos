/** etapas/r4/poblacional.js — filtros de la dimensión poblacional (lee #page-data). */
(function () {
  const pageData = JSON.parse(document.getElementById("page-data").textContent);
  const TOTAL = pageData.total;
  const CROSS = pageData.cross;

  const selCultivo = document.getElementById("filter-cultivo");
  const selCiclo   = document.getElementById("filter-ciclo");
  const btnReset   = document.getElementById("filter-reset");
  const tbody      = document.getElementById("filter-tbody");
  const elTotal    = document.getElementById("filter-total");
  const elPct      = document.getElementById("filter-pct");
  const elLabel    = document.getElementById("filter-label");

  function fmt(n) { return n.toLocaleString("es-CO"); }

  function applyFilters() {
    const cultFil  = selCultivo.value;
    const cicloFil = selCiclo.value;
    let filtered = 0;

    for (const tr of tbody.querySelectorAll("tr[data-cultivo]")) {
      const cult = tr.dataset.cultivo;
      const nOrig = Number.parseInt(tr.dataset.nOrig, 10);

      if (cultFil && cult !== cultFil) { tr.classList.add("d-none"); continue; }
      tr.classList.remove("d-none");

      let n = cicloFil ? ((CROSS[cult] || {})[cicloFil] || 0) : nOrig;
      const pct = TOTAL > 0 ? (n / TOTAL * 100).toFixed(1) : "0.0";

      const slug = cult.replace(/ /g, "_");
      const elN = document.getElementById("n-" + slug);
      const elP = document.getElementById("pct-" + slug);
      if (elN) elN.textContent = fmt(n);
      if (elP) elP.textContent = pct + " %";
      tr.style.opacity = (cultFil && cult === cultFil) ? "1" : cultFil ? "0.5" : "1";
      filtered += n;
    }

    elTotal.textContent = fmt(filtered);
    elPct.textContent = TOTAL > 0 ? (filtered / TOTAL * 100).toFixed(1) : "0.0";

    const parts = [];
    if (cultFil)  parts.push("Cultivo: " + cultFil);
    if (cicloFil) parts.push("Ciclo: " + cicloFil);
    elLabel.textContent = parts.length ? "Filtro activo: " + parts.join(" · ") : "";
  }

  selCultivo.addEventListener("change", applyFilters);
  selCiclo.addEventListener("change", applyFilters);
  btnReset.addEventListener("click", () => {
    selCultivo.value = "";
    selCiclo.value = "";
    applyFilters();
  });
})();
