/**
 * motion.js — contenido animado: entrada por scroll, cifras con count-up y
 * barras de progreso que se llenan al aparecer. Respeta prefers-reduced-motion.
 */
const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

function observe(selector, onEnter, options) {
  const els = document.querySelectorAll(selector);
  if (!els.length) return;
  if (reduced || !("IntersectionObserver" in window)) { els.forEach(onEnter); return; }
  const io = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (!entry.isIntersecting) return;
      onEnter(entry.target);
      io.unobserve(entry.target);
    });
  }, options);
  els.forEach((el) => io.observe(el));
}

function countUp(el) {
  const target = Number(el.dataset.countup);
  if (!Number.isFinite(target)) return;
  const fmt = (n) => Math.round(n).toLocaleString("es-CO");
  if (reduced) { el.textContent = fmt(target); return; }
  const duration = 1100;
  const start = performance.now();
  const tick = (now) => {
    const p = Math.min(1, (now - start) / duration);
    const eased = 1 - Math.pow(1 - p, 3);
    el.textContent = fmt(target * eased);
    if (p < 1) requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
}

export function initMotion() {
  observe(".reveal", (el) => el.classList.add("is-visible"), { threshold: 0.12, rootMargin: "0px 0px -40px 0px" });
  observe("[data-countup]", countUp, { threshold: 0.5 });
  observe(".progress-bar[data-progress]", (bar) => { bar.style.width = bar.dataset.progress + "%"; }, { threshold: 0.4 });

  const backToTop = document.getElementById("back-to-top");
  if (backToTop) {
    window.addEventListener("scroll", () => backToTop.classList.toggle("show", window.scrollY > 600), { passive: true });
    backToTop.addEventListener("click", () => window.scrollTo({ top: 0, behavior: reduced ? "auto" : "smooth" }));
  }

  const year = document.getElementById("current-year");
  if (year) year.textContent = new Date().getFullYear();
}
