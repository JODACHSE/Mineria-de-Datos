/** notify.js — toasts de Bootstrap para avisos breves (p. ej. errores de red). */
export function notify(message, color = "success") {
  const container = document.getElementById("toast-container");
  if (!container || !window.bootstrap) return;
  const el = document.createElement("div");
  el.className = `toast align-items-center text-bg-${color} border-0`;
  el.setAttribute("role", "status");
  el.innerHTML = `<div class="d-flex"><div class="toast-body"></div>
    <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Cerrar"></button></div>`;
  el.querySelector(".toast-body").textContent = message;
  container.appendChild(el);
  el.addEventListener("hidden.bs.toast", () => el.remove());
  new window.bootstrap.Toast(el, { delay: 3500 }).show();
}
