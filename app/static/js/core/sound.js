/**
 * sound.js — sonidos de interfaz con uisfx (pack «zen»), sintetizados con Web Audio.
 * La librería se sirve desde static/vendor/ (ver su README).
 */
import { createUISFX } from "../../vendor/uisfx-0.4.0/index.js";

const ui = createUISFX({
  pack: "zen",
  volume: 0.7,
  // uisfx guarda pack, volumen y activado en localStorage.
  preferences: { key: "wololo:sound" },
});

// Nombres propios del sitio -> cues de uisfx.
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

export function play(name) {
  ui.play(CUE[name] ?? name);
}

export const isEnabled = () => ui.isEnabled();
export const setEnabled = (value) => ui.setEnabled(value);

// El navegador exige un gesto del usuario antes de sonar: se desbloquea en la primera interacción.
let unlocked = false;
function unlockOnce() {
  if (unlocked) return;
  unlocked = true;
  ui.unlock();
  // Presintetiza los cues para que el primer clic no espere.
  ui.preload(Object.values(CUE));
}

export function initSound() {
  document.addEventListener("pointerdown", unlockOnce, { once: true });
  document.addEventListener("keydown", unlockOnce, { once: true });

  document.addEventListener("click", (e) => {
    if (e.target.closest("button, .btn, .nav-link, .dropdown-item, .page-link")) play("click");
  });

  let lastHover = 0;
  document.addEventListener("pointerover", (e) => {
    if (e.pointerType === "touch") return;
    if (!e.target.closest(".btn, .card, .nav-link, .accordion-button")) return;
    const now = performance.now();
    if (now - lastHover > 120) { play("hover"); lastHover = now; }
  }, { passive: true });

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
