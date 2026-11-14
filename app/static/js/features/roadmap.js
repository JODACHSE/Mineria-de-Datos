/** roadmap.js — colorea el camino de /entregables al hacer scroll hasta la última etapa publicada. */
const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

export function initRoadmap() {
  const map = document.querySelector("[data-roadmap]");
  if (!map) return;
  const track = map.querySelector(".roadmap-track");
  const stops = [...map.querySelectorAll(".roadmap-stop")];
  const done = stops.filter((s) => s.classList.contains("is-done"));
  if (!track || !stops.length) return;

  const nodeY = (stop) => {
    const r = stop.querySelector(".roadmap-node").getBoundingClientRect();
    return r.top + r.height / 2;
  };

  const update = () => {
    const t = track.getBoundingClientRect();
    if (!t.height) return;
    const limit = done.length ? nodeY(done.at(-1)) - t.top : 0;
    const line = reduced ? Infinity : window.innerHeight * 0.6;
    const walked = Math.max(0, Math.min(line - t.top, limit));
    track.style.setProperty("--roadmap-progress", (walked / t.height).toFixed(4));
    for (const s of done) s.classList.toggle("is-reached", nodeY(s) - t.top <= walked + 1);
  };

  let ticking = false;
  const onScroll = () => {
    if (!ticking) { ticking = true; requestAnimationFrame(() => { ticking = false; update(); }); }
  };
  window.addEventListener("scroll", onScroll, { passive: true });
  window.addEventListener("resize", onScroll, { passive: true });
  update();
}
