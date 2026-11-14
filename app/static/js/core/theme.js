/** theme.js — alterna y guarda el tema claro/oscuro (el inicial lo aplica layouts/base.html). */
import { play } from "./sound.js";

const root = document.documentElement;

export const currentTheme = () => root.getAttribute("data-bs-theme") || "light";

export function setTheme(theme) {
  root.setAttribute("data-bs-theme", theme);
  try { localStorage.setItem("theme", theme); } catch { /* almacenamiento bloqueado */ }
  document.dispatchEvent(new CustomEvent("themechange", { detail: { theme } }));
}

export function initTheme() {
  const btn = document.getElementById("theme-toggle");
  if (!btn) return;
  btn.addEventListener("click", () => {
    const next = currentTheme() === "dark" ? "light" : "dark";
    setTheme(next);
    play(next === "dark" ? "toggleOff" : "toggleOn");
  });
}
