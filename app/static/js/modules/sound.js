/**
 * sound.js — sonidos de interfaz con la librería **uisfx**
 * (https://www.npmjs.com/package/uisfx · https://github.com/romainsimon/uisfx).
 *
 * uisfx no reproduce archivos: sintetiza cada sonido en el navegador con la
 * Web Audio API a partir de "recetas" deterministas (osciladores + ruido),
 * así que no hay .mp3/.ogg que descargar, alojar ni versionar. Usamos el
 * pack **"zen"** — tonos puros, madera seca y un detalle breve de papel —
 * acorde al tono del sitio. Los 78 cues semánticos del paquete (hover,
 * press, toggle-on, open, error, success…) están documentados en
 * https://uisfx.com/.
 *
 * Se importa como módulo ES directamente desde jsDelivr (mismo criterio que
 * Bootstrap y Chart.js en este proyecto: sin paso de build). Zero-dependency,
 * runtime MIT, biblioteca de audio generada CC0-1.0.
 */
import { createUISFX } from "https://cdn.jsdelivr.net/npm/uisfx@0.4.0/dist/index.js";

const ui = createUISFX({
  pack: "zen",
  volume: 0.7,
  // uisfx persiste pack/volumen/activado bajo esta clave de localStorage;
  // no necesitamos gestionar nosotros mismos el "on/off".
  preferences: { key: "wololo:sound" },
});

// Vocabulario propio del sitio -> cue semántico de uisfx. Mantener esta
// capa permite cambiar de pack o de cue sin tocar cada punto de llamada.
const CUE = {
  click: "press",
  hover: "hover",
  toggleOn: "toggle-on",
  toggleOff: "toggle-off",
  open: "open",
  close: "close",
  select: "select",
  success: "success",
  error: "error",
};

/** Reproduce un sonido por nombre propio (o, si no está mapeado, como cue de uisfx directo). */
export function play(name) {
  ui.play(CUE[name] ?? name);
}

export const isEnabled = () => ui.isEnabled();
export const setEnabled = (value) => ui.setEnabled(value);

// El audio del navegador exige un gesto explícito del usuario antes de sonar
// (política de autoplay). Desbloqueamos el AudioContext en la primera
// interacción, tal como recomienda la documentación de uisfx.
let unlocked = false;
function unlockOnce() {
  if (unlocked) return;
  unlocked = true;
  ui.unlock();
  // Pre-sintetiza en segundo plano los cues que usa la interfaz para que
  // el primer clic real no cargue con el coste de generarlos.
  ui.preload(Object.values(CUE));
}

/** Conecta los sonidos a la interacción global y al botón de silencio. */
export function initSound() {
  document.addEventListener("pointerdown", unlockOnce, { once: true });
  document.addEventListener("keydown", unlockOnce, { once: true });

  document.addEventListener("click", (e) => {
    if (e.target.closest("button, .btn, .nav-link, .dropdown-item, .page-link")) play("click");
  });

  let lastHover = 0;
  document.addEventListener("pointerover", (e) => {
    if (e.pointerType === "touch") return; // sin hover táctil, como hace el propio uisfx
    if (!e.target.closest(".btn, .card, .nav-link, .accordion-button")) return;
    const now = performance.now();
    if (now - lastHover > 120) { play("hover"); lastHover = now; }
  }, { passive: true });

  // Eventos de componentes de Bootstrap
  document.addEventListener("show.bs.offcanvas", () => play("open"));
  document.addEventListener("hide.bs.offcanvas", () => play("close"));
  document.addEventListener("show.bs.dropdown", () => play("open"));
  document.addEventListener("show.bs.collapse", () => play("open"));
  document.addEventListener("hide.bs.collapse", () => play("close"));
  document.addEventListener("shown.bs.tab", () => play("select"));

  const btn = document.getElementById("sfx-toggle");
  if (!btn) return;
  const sync = () => {
    btn.dataset.sound = isEnabled() ? "on" : "off";
    btn.setAttribute("aria-pressed", String(isEnabled()));
  };
  sync();
  btn.addEventListener("click", () => {
    setEnabled(!isEnabled());
    sync();
    if (isEnabled()) play("toggleOn");
  });
}
