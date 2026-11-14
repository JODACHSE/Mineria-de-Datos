/**
 * layout.js — armazón: altura del header (--header-h), estado «scrolled», barra de
 * progreso, scrollspy del índice e índice móvil (offcanvas).
 */
const root = document.documentElement;
const px = (name) => Number.parseFloat(getComputedStyle(root).getPropertyValue(name)) || 0;

function scrollSpy() {
  const toc = document.getElementById("toc");
  if (!toc) return;
  const items = [...toc.querySelectorAll('a[href^="#"]')]
    .map((link) => ({ link, section: document.getElementById(decodeURIComponent(link.hash.slice(1))) }))
    .filter((i) => i.section);
  if (!items.length) return;
  const current = document.querySelector("[data-toc-current]");
  let active = null;
  // La sección elegida en el índice queda marcada mientras siga donde la dejó el ancla.
  let pinned = null, pinArrived = false, pinnedAt = 0;
  const pin = (hash) => {
    const it = items.find((i) => i.link.hash === hash);
    if (it) { pinned = it; pinArrived = false; pinnedAt = performance.now(); }
  };

  const update = () => {
    const top = px("--header-h") + px("--subnav-h");
    // Línea de lectura: bajo el header + 20 % de la ventana.
    const line = top + window.innerHeight * 0.2;
    const atEnd = window.innerHeight + window.scrollY >= root.scrollHeight - 2;
    let next = items[0];
    for (const it of items) {
      if (it.section.getBoundingClientRect().top <= line) next = it;
    }
    if (pinned) {
      const t = pinned.section.getBoundingClientRect().top;
      const parked = t >= -4 && t <= line;
      if (parked) pinArrived = true;
      // Se mantiene durante el scroll suave; al salir de su sitio se suelta.
      const keep = parked || (!pinArrived && performance.now() - pinnedAt < 1500);
      if (keep) next = pinned; else pinned = null;
    }
    if (atEnd && !pinned) next = items.at(-1);
    if (next === active) return;
    active?.link.classList.remove("active");
    active?.link.removeAttribute("aria-current");
    next.link.classList.add("active");
    next.link.setAttribute("aria-current", "location");
    if (current) current.textContent = next.link.textContent.trim();
    const box = next.link.closest(".sidebar");
    if (box && box.scrollHeight > box.clientHeight) {
      const r = next.link.getBoundingClientRect(), b = box.getBoundingClientRect();
      if (r.top < b.top || r.bottom > b.bottom) box.scrollTop += r.top - b.top - b.height / 2;
    }
    active = next;
  };

  let ticking = false;
  const onScroll = () => {
    if (!ticking) { ticking = true; requestAnimationFrame(() => { ticking = false; update(); }); }
  };
  window.addEventListener("scroll", onScroll, { passive: true });
  window.addEventListener("resize", onScroll, { passive: true });
  toc.addEventListener("click", (e) => {
    const link = e.target.closest('a[href^="#"]');
    if (link) { pin(link.hash); onScroll(); }
  });
  window.addEventListener("hashchange", () => { pin(location.hash); onScroll(); });
  pin(location.hash);
  update();
}

function trackHeights() {
  const header = document.getElementById("site-header");
  const subnav = document.getElementById("page-subnav");
  const update = () => {
    if (header) root.style.setProperty("--header-h", `${header.offsetHeight}px`);
    // offsetParent es null si la barra está oculta (escritorio).
    const sub = subnav && subnav.offsetParent !== null ? subnav.offsetHeight + 8 : 0;
    root.style.setProperty("--subnav-h", `${sub}px`);
  };
  update();
  if ("ResizeObserver" in window) {
    const ro = new ResizeObserver(update);
    if (header) ro.observe(header);
    if (subnav) ro.observe(subnav);
  }
  window.addEventListener("resize", update, { passive: true });
}

function trackScroll() {
  const header = document.getElementById("site-header");
  if (!header) return;
  let ticking = false;
  const update = () => {
    ticking = false;
    const y = window.scrollY;
    header.classList.toggle("is-scrolled", y > 4);
    const max = root.scrollHeight - window.innerHeight;
    header.style.setProperty("--progress", max > 0 ? Math.min(1, y / max).toFixed(4) : "0");
  };
  window.addEventListener("scroll", () => {
    if (!ticking) { ticking = true; requestAnimationFrame(update); }
  }, { passive: true });
  update();
}

function mobileToc() {
  const sidebar = document.getElementById("sidebar");
  if (!sidebar || !window.bootstrap) return;
  sidebar.addEventListener("click", (e) => {
    const link = e.target.closest('a[href^="#"]');
    if (!link || !sidebar.classList.contains("show")) return;
    const target = document.getElementById(decodeURIComponent(link.hash.slice(1)));
    if (!target) return;
    e.preventDefault();
    sidebar.addEventListener("hidden.bs.offcanvas", () => {
      target.scrollIntoView({ block: "start" }); // respeta scroll-padding-top
      history.replaceState(null, "", link.hash);
    }, { once: true });
    window.bootstrap.Offcanvas.getOrCreateInstance(sidebar).hide();
  });

  window.matchMedia("(min-width: 992px)").addEventListener("change", (mq) => {
    if (mq.matches) window.bootstrap.Offcanvas.getInstance(sidebar)?.hide();
  });
}

function closeMobileMenuOnNavigate() {
  const menu = document.getElementById("navMenu");
  if (!menu || !window.bootstrap) return;
  window.matchMedia("(min-width: 992px)").addEventListener("change", (mq) => {
    if (mq.matches) window.bootstrap.Offcanvas.getInstance(menu)?.hide();
  });
}

export function initLayout() {
  trackHeights();
  trackScroll();
  scrollSpy();
  mobileToc();
  closeMobileMenuOnNavigate();
}
