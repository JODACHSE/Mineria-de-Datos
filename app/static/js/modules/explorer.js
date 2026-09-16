/**
 * explorer.js — explorador de datos paginado contra /api/dataset/<nombre>.
 * El JS no conoce el esquema: la API devuelve `display_columns` por dataset.
 */
import { play } from "./sound.js";
import { notify } from "./notify.js";

const NUMERIC = new Set(["Valor", "AreaSembrada", "AreaCosechada", "Produccion", "Rendimiento"]);
const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

export function initExplorer() {
  const root = document.getElementById("data-explorer");
  if (!root) return;

  const $ = (role) => root.querySelector(`[data-role='${role}']`);
  const thead = root.querySelector("thead tr");
  const tbody = root.querySelector("tbody");
  const meta = $("meta"), pageInfo = $("page-info"), prev = $("prev"), next = $("next");
  const selDataset = $("dataset-select"), selVersion = $("version"), inpSearch = $("search"),
        selProducto = $("producto"), selElemento = $("elemento"), selPageSize = $("page-size");

  const state = { dataset: root.dataset.dataset, version: root.dataset.version || "crudo",
                  page: 1, page_size: 8, q: "", producto: "", elemento: "" };
  let debounce = null;

  function skeleton(nCols) {
    tbody.innerHTML = Array.from({ length: state.page_size }, () =>
      `<tr class="placeholder-glow">${Array.from({ length: nCols }, () => `<td><span class="placeholder col-8"></span></td>`).join("")}</tr>`
    ).join("");
  }

  function fillSelect(select, values) {
    if (!select) return;
    const current = select.value;
    select.innerHTML = `<option value="">Todos</option>` + values.map((v) => `<option value="${esc(v)}">${esc(v)}</option>`).join("");
    select.value = values.includes(current) ? current : "";
  }

  async function load() {
    const params = new URLSearchParams({ page: state.page, page_size: state.page_size, version: state.version });
    if (state.q) params.set("q", state.q);
    if (state.producto) params.set("producto", state.producto);
    if (state.elemento) params.set("elemento", state.elemento);
    skeleton(thead.children.length || 6);

    try {
      const res = await fetch(`/api/dataset/${state.dataset}?${params}`);
      const json = await res.json();
      if (json.error) throw new Error(json.error);

      const flagCols = state.version === "tratado" ? json.columns.filter((c) => c.startsWith("_")) : [];
      const cols = json.display_columns.concat(flagCols);
      thead.innerHTML = cols.map((c) => `<th class="${NUMERIC.has(c) ? "text-end" : ""}">${esc(c)}</th>`).join("");
      fillSelect(selProducto, json.productos_disponibles);
      fillSelect(selElemento, json.elementos_disponibles);

      tbody.innerHTML = json.rows.map((row) => `<tr>${cols.map((c) => {
        const raw = row[c];
        let text = raw ?? "—";
        let cls = "";
        if (typeof raw === "boolean") { text = raw ? "Sí" : "No"; cls = raw ? "text-danger fw-semibold" : "text-body-tertiary"; }
        else if (NUMERIC.has(c) && typeof raw === "number") { text = raw.toLocaleString("es-CO"); cls = "text-end font-monospace"; }
        return `<td class="${cls}">${esc(text)}</td>`;
      }).join("")}</tr>`).join("")
        || `<tr><td colspan="${cols.length}" class="text-center text-body-secondary py-4">Sin resultados para este filtro.</td></tr>`;

      meta.textContent = `${json.total.toLocaleString("es-CO")} registros encontrados · página ${json.page} de ${json.total_pages}`;
      pageInfo.textContent = `${json.page} / ${json.total_pages}`;
      prev.disabled = json.page <= 1;
      next.disabled = json.page >= json.total_pages;
    } catch (err) {
      tbody.innerHTML = `<tr><td class="text-danger">No fue posible cargar los datos (${esc(err.message)}).</td></tr>`;
      notify("No fue posible cargar los datos. Verifica la conexión con el servidor.", "danger");
      play("error");
    }
  }

  const reset = () => { state.page = 1; };
  selDataset?.addEventListener("change", (e) => { state.dataset = e.target.value; Object.assign(state, { q: "", producto: "", elemento: "" }); if (inpSearch) inpSearch.value = ""; reset(); load(); });
  selPageSize?.addEventListener("change", (e) => { state.page_size = Number(e.target.value); reset(); load(); });
  selVersion?.addEventListener("change", (e) => { state.version = e.target.value; reset(); load(); });
  inpSearch?.addEventListener("input", (e) => { clearTimeout(debounce); debounce = setTimeout(() => { state.q = e.target.value.trim(); reset(); load(); }, 300); });
  selProducto?.addEventListener("change", (e) => { state.producto = e.target.value; reset(); load(); });
  selElemento?.addEventListener("change", (e) => { state.elemento = e.target.value; reset(); load(); });
  prev?.addEventListener("click", () => { if (state.page > 1) { state.page--; load(); } });
  next?.addEventListener("click", () => { state.page++; load(); });

  if (selDataset) selDataset.value = state.dataset;
  load();
}
