/* =========================================================================
 * index.js — comportamiento del sitio
 * Secciones: 1) sonido UI (WebAudio, sin archivos externos)
 *            2) tema claro/oscuro persistente
 *            3) navegación / menú móvil / loader / back-to-top
 *            4) animaciones de entrada (IntersectionObserver)
 *            5) TOC activo en scroll (R1)
 *            6) explorador de datos dinámico (fetch a /api/dataset/<n>)
 *            7) gráfico FAOSTAT (Chart.js)
 *            8) gráfico comparativo de calidad antes/después (R2)
 * ========================================================================= */
(() => {
  "use strict";

  /* ----------------------------------------------------------------- *
   * 1) SONIDOS DE INTERFAZ — sintetizados con Web Audio API.
   *    No dependemos de archivos externos (uisfx.com no es accesible
   *    desde el servidor): generamos clics/tonos cortos en el navegador,
   *    lo que además evita peticiones de red y funciona sin conexión.
   * ----------------------------------------------------------------- */
  const Sound = (() => {
    let ctx = null;
    let enabled = localStorage.getItem("sfx") !== "off";

    function ensureCtx() {
      if (!ctx) {
        const AC = window.AudioContext || window.webkitAudioContext;
        if (AC) ctx = new AC();
      }
      if (ctx && ctx.state === "suspended") ctx.resume();
      return ctx;
    }

    function tone({ freq = 440, duration = 0.08, type = "sine", gain = 0.05, glideTo = null }) {
      if (!enabled) return;
      const c = ensureCtx();
      if (!c) return;
      const osc = c.createOscillator();
      const amp = c.createGain();
      osc.type = type;
      osc.frequency.setValueAtTime(freq, c.currentTime);
      if (glideTo) osc.frequency.exponentialRampToValueAtTime(glideTo, c.currentTime + duration);
      amp.gain.setValueAtTime(gain, c.currentTime);
      amp.gain.exponentialRampToValueAtTime(0.0001, c.currentTime + duration);
      osc.connect(amp).connect(c.destination);
      osc.start();
      osc.stop(c.currentTime + duration + 0.02);
    }

    return {
      click: () => tone({ freq: 620, duration: 0.06, type: "triangle", gain: 0.045, glideTo: 500 }),
      hover: () => tone({ freq: 900, duration: 0.03, type: "sine", gain: 0.02 }),
      toggleOn: () => tone({ freq: 440, duration: 0.09, type: "sine", gain: 0.05, glideTo: 720 }),
      toggleOff: () => tone({ freq: 500, duration: 0.09, type: "sine", gain: 0.05, glideTo: 260 }),
      success: () => tone({ freq: 560, duration: 0.14, type: "sine", gain: 0.05, glideTo: 880 }),
      isEnabled: () => enabled,
      setEnabled(v) {
        enabled = v;
        localStorage.setItem("sfx", v ? "on" : "off");
      },
    };
  })();

  document.addEventListener("click", (e) => {
    const t = e.target.closest("button, a.neu-btn, .icon-btn, a.nav-links__link");
    if (t) Sound.click();
  });
  document.addEventListener(
    "mouseover",
    (e) => {
      if (e.target.closest(".neu, .card, .neu-btn, .icon-btn")) Sound.hover();
    },
    { passive: true }
  );

  const sfxBtn = document.getElementById("sfx-toggle");
  if (sfxBtn) {
    sfxBtn.dataset.sound = Sound.isEnabled() ? "on" : "off";
    sfxBtn.addEventListener("click", () => {
      const next = !Sound.isEnabled();
      Sound.setEnabled(next);
      sfxBtn.dataset.sound = next ? "on" : "off";
      next ? Sound.toggleOn() : Sound.toggleOff();
    });
  }

  /* ----------------------------------------------------------------- *
   * 2) TEMA CLARO / OSCURO
   * ----------------------------------------------------------------- */
  const root = document.documentElement;
  const themeBtn = document.getElementById("theme-toggle");
  const savedTheme =
    localStorage.getItem("theme") ||
    (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
  root.setAttribute("data-theme", savedTheme);

  if (themeBtn) {
    themeBtn.addEventListener("click", () => {
      const current = root.getAttribute("data-theme");
      const next = current === "dark" ? "light" : "dark";
      root.setAttribute("data-theme", next);
      localStorage.setItem("theme", next);
      next === "dark" ? Sound.toggleOff() : Sound.toggleOn();
    });
  }

  /* ----------------------------------------------------------------- *
   * 3) NAV / LOADER / BACK TO TOP
   * ----------------------------------------------------------------- */
  const navToggle = document.getElementById("nav-toggle");
  const navLinks = document.getElementById("nav-links");
  if (navToggle && navLinks) {
    navToggle.addEventListener("click", () => navLinks.classList.toggle("open"));
    // Cierra el menú móvil al elegir un enlace real, pero el toggle de
    // "Etapas" no navega a ningún sitio (href="#"): ese se maneja aparte.
    navLinks.querySelectorAll("a:not(.dropdown-toggle)").forEach((a) =>
      a.addEventListener("click", () => navLinks.classList.remove("open"))
    );
  }

  /* Dropdown "Etapas": se abre con :hover vía CSS (ver styles.css) en
     escritorio; este JS solo cubre el toggle por click/tacto/teclado
     (tablets, lectores de pantalla) y el cierre al hacer clic afuera
     o presionar Escape. */
  const etapasItem = document.getElementById("etapasNavItem");
  const etapasToggle = document.getElementById("etapasDropdown");
  if (etapasItem && etapasToggle) {
    etapasToggle.addEventListener("click", (e) => {
      e.preventDefault();
      const willOpen = !etapasItem.classList.contains("open");
      etapasItem.classList.toggle("open", willOpen);
      etapasToggle.setAttribute("aria-expanded", String(willOpen));
    });
    document.addEventListener("click", (e) => {
      if (!etapasItem.contains(e.target)) {
        etapasItem.classList.remove("open");
        etapasToggle.setAttribute("aria-expanded", "false");
      }
    });
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") {
        etapasItem.classList.remove("open");
        etapasToggle.setAttribute("aria-expanded", "false");
      }
    });
  }

  const loader = document.getElementById("page-loader");
  if (loader) {
    requestAnimationFrame(() => (loader.style.width = "70%"));
    window.addEventListener("load", () => {
      loader.style.width = "100%";
      setTimeout(() => (loader.style.opacity = "0"), 250);
    });
  }

  const backToTop = document.getElementById("back-to-top");
  if (backToTop) {
    window.addEventListener(
      "scroll",
      () => backToTop.classList.toggle("show", window.scrollY > 600),
      { passive: true }
    );
    backToTop.addEventListener("click", () => window.scrollTo({ top: 0, behavior: "smooth" }));
  }

  /* ----------------------------------------------------------------- *
   * 4) SCROLL REVEAL
   * ----------------------------------------------------------------- */
  const revealEls = document.querySelectorAll(".reveal, .reveal-stagger");
  if ("IntersectionObserver" in window && revealEls.length) {
    const io = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add("is-visible");
            io.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.12, rootMargin: "0px 0px -60px 0px" }
    );
    revealEls.forEach((el) => io.observe(el));
  } else {
    revealEls.forEach((el) => el.classList.add("is-visible"));
  }

  /* animar barras de calidad cuando entran en viewport */
  document.querySelectorAll(".quality-bar__fill[data-value]").forEach((bar) => {
    const io2 = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.style.width = entry.target.dataset.value + "%";
          io2.unobserve(entry.target);
        }
      });
    }, { threshold: 0.4 });
    io2.observe(bar);
  });

  /* ----------------------------------------------------------------- *
   * 5) TOC activo en scroll
   * ----------------------------------------------------------------- */
  const tocLinks = document.querySelectorAll(".toc a[href^='#']");
  const sections = [...tocLinks]
    .map((a) => document.querySelector(a.getAttribute("href")))
    .filter(Boolean);
  if (sections.length) {
    const tocObserver = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          const id = "#" + entry.target.id;
          const link = document.querySelector(`.toc a[href='${id}']`);
          if (!link) return;
          if (entry.isIntersecting) {
            tocLinks.forEach((l) => l.classList.remove("active"));
            link.classList.add("active");
          }
        });
      },
      { rootMargin: "-30% 0px -60% 0px", threshold: 0 }
    );
    sections.forEach((s) => tocObserver.observe(s));
  }

  /* ----------------------------------------------------------------- *
   * 6) EXPLORADOR DE DATOS — consulta a la API Flask dinámica.
   *    Soporta cambiar de dataset en caliente (selector), porque cada
   *    dataset trae su propio esquema de columnas (display_columns) que
   *    la API ya resuelve — el JS no necesita conocer FAOSTAT vs EVA.
   * ----------------------------------------------------------------- */
  const explorer = document.getElementById("data-explorer");
  if (explorer) {
    const tbody = explorer.querySelector("tbody");
    const thead = explorer.querySelector("thead tr");
    const metaEl = explorer.querySelector(".explorer__meta");
    const datasetSelect = explorer.querySelector("[data-role='dataset-select']");
    const searchInput = explorer.querySelector("[data-role='search']");
    const productoSelect = explorer.querySelector("[data-role='producto']");
    const elementoSelect = explorer.querySelector("[data-role='elemento']");
    const versionSelect = explorer.querySelector("[data-role='version']");
    const prevBtn = explorer.querySelector("[data-role='prev']");
    const nextBtn = explorer.querySelector("[data-role='next']");
    const pageInfo = explorer.querySelector("[data-role='page-info']");

    let state = {
      dataset: explorer.dataset.dataset,
      version: explorer.dataset.version || "crudo",
      page: 1,
      page_size: 8,
      q: "",
      producto: "",
      elemento: "",
    };
    let debounceTimer = null;

    function renderSkeleton(nCols) {
      tbody.innerHTML = "";
      for (let i = 0; i < state.page_size; i++) {
        const tr = document.createElement("tr");
        tr.className = "skeleton-row";
        tr.innerHTML = Array.from({ length: nCols }).map(() => "<td>xxxxxxxx</td>").join("");
        tbody.appendChild(tr);
      }
    }

    async function loadData() {
      const params = new URLSearchParams({
        page: state.page,
        page_size: state.page_size,
        version: state.version,
      });
      if (state.q) params.set("q", state.q);
      if (state.producto) params.set("producto", state.producto);
      if (state.elemento) params.set("elemento", state.elemento);

      renderSkeleton(thead.children.length || 6);

      try {
        const res = await fetch(`/api/dataset/${state.dataset}?${params.toString()}`);
        const json = await res.json();
        if (json.error) throw new Error(json.error);

        // En la versión "tratado" (R2) se muestran también las columnas de
        // bandera (_flag_*, _outlier_*) como evidencia visible del tratamiento.
        const flagCols = state.version === "tratado" ? json.columns.filter((c) => c.startsWith("_")) : [];
        const cols = json.display_columns.concat(flagCols);
        thead.innerHTML = cols.map((c) => `<th>${c}</th>`).join("");

        const numericCols = new Set(["Valor", "AreaSembrada", "AreaCosechada", "Produccion", "Rendimiento"]);

        if (productoSelect) {
          productoSelect.innerHTML =
            '<option value="">Todos</option>' +
            json.productos_disponibles.map((p) => `<option value="${p}">${p}</option>`).join("");
        }
        if (elementoSelect) {
          elementoSelect.innerHTML =
            '<option value="">Todos</option>' +
            json.elementos_disponibles.map((el) => `<option value="${el}">${el}</option>`).join("");
        }

        tbody.innerHTML = json.rows
          .map((row) => {
            const cells = cols
              .map((c) => {
                const raw = row[c];
                let display = raw ?? "—";
                if (typeof raw === "boolean") display = raw ? "Sí" : "No";
                else if (numericCols.has(c) && typeof raw === "number") display = raw.toLocaleString("es-CO");
                const cls = numericCols.has(c) ? "num" : raw === true ? "flag-on" : "";
                return `<td class="${cls}">${display}</td>`;
              })
              .join("");
            return `<tr>${cells}</tr>`;
          })
          .join("") || `<tr><td colspan="${cols.length}">Sin resultados para este filtro.</td></tr>`;

        metaEl.textContent = `${json.total.toLocaleString("es-CO")} registros encontrados · página ${json.page} de ${json.total_pages}`;
        pageInfo.textContent = `${json.page} / ${json.total_pages}`;
        prevBtn.disabled = json.page <= 1;
        nextBtn.disabled = json.page >= json.total_pages;
      } catch (err) {
        tbody.innerHTML = `<tr><td>No fue posible cargar los datos (${err.message}). Verifica que el servidor Flask esté activo.</td></tr>`;
      }
    }

    datasetSelect?.addEventListener("change", (e) => {
      state.dataset = e.target.value;
      state.page = 1;
      state.q = "";
      state.producto = "";
      state.elemento = "";
      if (searchInput) searchInput.value = "";
      loadData();
    });
    searchInput?.addEventListener("input", (e) => {
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(() => {
        state.q = e.target.value.trim();
        state.page = 1;
        loadData();
      }, 300);
    });
    productoSelect?.addEventListener("change", (e) => {
      state.producto = e.target.value;
      state.page = 1;
      loadData();
    });
    elementoSelect?.addEventListener("change", (e) => {
      state.elemento = e.target.value;
      state.page = 1;
      loadData();
    });
    versionSelect?.addEventListener("change", (e) => {
      state.version = e.target.value;
      state.page = 1;
      loadData();
    });
    prevBtn?.addEventListener("click", () => {
      if (state.page > 1) {
        state.page -= 1;
        loadData();
      }
    });
    nextBtn?.addEventListener("click", () => {
      state.page += 1;
      loadData();
    });

    loadData();
  }

  /* ----------------------------------------------------------------- *
   * 7) GRÁFICO FAOSTAT (Chart.js, cargado vía CDN en base.html)
   * ----------------------------------------------------------------- */
  const chartCanvas = document.getElementById("fs-chart");
  if (chartCanvas && window.Chart && window.__FS_CHART__) {
    const styles = getComputedStyle(document.documentElement);
    const accent = styles.getPropertyValue("--amber-bright").trim();
    const leaf = styles.getPropertyValue("--leaf").trim();
    const textSoft = styles.getPropertyValue("--ink-soft").trim();
    const line = styles.getPropertyValue("--line").trim();

    const payload = window.__FS_CHART__;
    const colors = [accent, leaf];

    new Chart(chartCanvas, {
      type: "line",
      data: {
        labels: payload.labels,
        datasets: payload.datasets.map((ds, i) => ({
          label: ds.label,
          data: ds.data,
          borderColor: colors[i % colors.length],
          backgroundColor: colors[i % colors.length] + "22",
          spanGaps: true,
          tension: 0.35,
          fill: i === 0,
          pointRadius: 0,
          pointHoverRadius: 5,
          borderWidth: 2.4,
        })),
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: "index", intersect: false },
        plugins: {
          legend: {
            labels: { color: textSoft, font: { family: "'Space Mono', monospace", size: 11 } },
          },
          tooltip: {
            backgroundColor: styles.getPropertyValue("--bg-panel-2").trim(),
            titleColor: textSoft,
            bodyColor: textSoft,
            borderColor: line,
            borderWidth: 1,
          },
        },
        scales: {
          x: { ticks: { color: textSoft, maxTicksLimit: 10 }, grid: { color: line } },
          y: { ticks: { color: textSoft }, grid: { color: line } },
        },
      },
    });
  }

  /* ----------------------------------------------------------------- *
   * 7b) GRÁFICO DE INTEGRACIÓN — EVA (municipal, agregado) vs FAOSTAT,
   *     por cultivo, para el último año disponible en window.__INTEGRACION__.
   * ----------------------------------------------------------------- */
  const integracionCanvas = document.getElementById("integracion-chart");
  if (integracionCanvas && window.Chart && window.__INTEGRACION__) {
    const styles2 = getComputedStyle(document.documentElement);
    const amber = styles2.getPropertyValue("--amber-bright").trim();
    const slate = styles2.getPropertyValue("--slate-light") ? styles2.getPropertyValue("--slate-light").trim() : "#8FA3AC";
    const textSoft2 = styles2.getPropertyValue("--ink-soft").trim();
    const line2 = styles2.getPropertyValue("--line").trim();

    const rows = window.__INTEGRACION__.rows; // [Anio, Cultivo, EVA_t, FAOSTAT_t, Diferencia_pct]
    const maxAnio = Math.max(...rows.map((r) => r[0]));
    const lastYearRows = rows.filter((r) => r[0] === maxAnio);

    new Chart(integracionCanvas, {
      type: "bar",
      data: {
        labels: lastYearRows.map((r) => r[1]),
        datasets: [
          { label: `EVA ${maxAnio} (t)`, data: lastYearRows.map((r) => r[2]), backgroundColor: amber },
          { label: `FAOSTAT ${maxAnio} (t)`, data: lastYearRows.map((r) => r[3]), backgroundColor: slate },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { labels: { color: textSoft2, font: { family: "'Space Mono', monospace", size: 11 } } },
          tooltip: {
            backgroundColor: styles2.getPropertyValue("--bg-panel-2").trim(),
            titleColor: textSoft2,
            bodyColor: textSoft2,
            borderColor: line2,
            borderWidth: 1,
          },
        },
        scales: {
          x: { ticks: { color: textSoft2 }, grid: { color: line2 } },
          y: { ticks: { color: textSoft2 }, grid: { color: line2 } },
        },
      },
    });
  }

  /* ----------------------------------------------------------------- *
   * 8) GRÁFICO COMPARATIVO DE CALIDAD ANTES/DESPUÉS (R2)
   *    window.__QUALITY_COMPARE__ = {dataset: {labels:[6 dims], antes:[...], despues:[...]}}
   * ----------------------------------------------------------------- */
  const compareCanvas = document.getElementById("compare-chart");
  if (compareCanvas && window.Chart && window.__QUALITY_COMPARE__) {
    const compareData = window.__QUALITY_COMPARE__;
    const compareSelect = document.getElementById("compare-dataset-select");
    const styles3 = getComputedStyle(document.documentElement);
    const amber3 = styles3.getPropertyValue("--amber-bright").trim();
    const leaf3 = styles3.getPropertyValue("--leaf").trim();
    const textSoft3 = styles3.getPropertyValue("--ink-soft").trim();
    const line3 = styles3.getPropertyValue("--line").trim();

    const cap = (s) => s.charAt(0).toUpperCase() + s.slice(1);
    let compareChart = null;

    function renderCompare(dsKey) {
      const d = compareData[dsKey];
      if (!d) return;
      const cfg = {
        type: "bar",
        data: {
          labels: d.labels.map(cap),
          datasets: [
            { label: "Antes", data: d.antes.map((v) => v ?? 0), backgroundColor: amber3 },
            { label: "Después", data: d.despues.map((v) => v ?? 0), backgroundColor: leaf3 },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { labels: { color: textSoft3, font: { family: "'Space Mono', monospace", size: 11 } } },
            tooltip: {
              backgroundColor: styles3.getPropertyValue("--bg-panel-2").trim(),
              titleColor: textSoft3,
              bodyColor: textSoft3,
              borderColor: line3,
              borderWidth: 1,
              callbacks: {
                label(ctx) {
                  const raw = dsKey && compareData[dsKey] ? compareData[dsKey][ctx.datasetIndex === 0 ? "antes" : "despues"][ctx.dataIndex] : null;
                  return `${ctx.dataset.label}: ${raw === null ? "No aplica" : raw + "%"}`;
                },
              },
            },
          },
          scales: {
            x: { ticks: { color: textSoft3 }, grid: { color: line3 } },
            y: { min: 0, max: 100, ticks: { color: textSoft3 }, grid: { color: line3 } },
          },
        },
      };
      if (compareChart) compareChart.destroy();
      compareChart = new Chart(compareCanvas, cfg);
    }

    const firstKey = compareSelect ? compareSelect.value : Object.keys(compareData)[0];
    renderCompare(firstKey);
    compareSelect?.addEventListener("change", (e) => renderCompare(e.target.value));
  }

  /* set current year in footer, if present */
  const yearEl = document.getElementById("current-year");
  if (yearEl) yearEl.textContent = new Date().getFullYear();
})();
