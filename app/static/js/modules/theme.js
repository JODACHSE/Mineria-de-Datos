/**
 * theme.js — alterna los temas nativos de Bootstrap (data-bs-theme=light|dark)
 * y persiste la elección. El valor inicial ya lo aplica un script inline en
 * layouts/base.html para evitar parpadeo.
 */
import { play } from "./sound.js";

const root = document.documentElement;

export const currentTheme = () => root.getAttribute("data-bs-theme") || "light";

export function setTheme(theme) {
  root.setAttribute("data-bs-theme", theme);
  localStorage.setItem("theme", theme);
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
