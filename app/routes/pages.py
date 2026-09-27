"""Blueprint `pages`: todas las vistas HTML del sitio."""
from __future__ import annotations

from flask import Blueprint, current_app, render_template

from app.etapas import ETAPAS, FASES_CRISP
from app.services import datasets as ds
from app.services.etapa3 import build_r3_context
from app.services.reports import build_r1_context, build_r2_context

pages_bp = Blueprint("pages", __name__)


def _dirs():
    cfg = current_app.config
    return cfg["R1_JSON_DIR"], cfg["R2_JSON_DIR"]


@pages_bp.route("/")
def index():
    return render_template("pages/home.html")


@pages_bp.route("/r1")
def r1():
    r1_dir, _ = _dirs()
    ctx = ds.cache_get("ctx:r1")
    if ctx is None:
        ctx = build_r1_context(r1_dir)
        ds.cache_set("ctx:r1", ctx)
    return render_template("pages/r1.html", **ctx)


@pages_bp.route("/r2")
def r2():
    r1_dir, r2_dir = _dirs()
    ctx = ds.cache_get("ctx:r2")
    if ctx is None:
        ctx = build_r2_context(r1_dir, r2_dir)
        ds.cache_set("ctx:r2", ctx)
    return render_template("pages/r2.html", **ctx)


@pages_bp.route("/r3")
def r3():
    cfg = current_app.config
    ctx = ds.cache_get("ctx:r3")
    if ctx is None:
        ctx = build_r3_context(cfg["R3_JSON_DIR"], cfg.get("VIDEO_ETAPA3_URL", ""))
        ds.cache_set("ctx:r3", ctx)
    return render_template("pages/r3.html", **ctx)


@pages_bp.route("/entregables")
def entregables():
    return render_template("pages/entregables.html", entregables=ETAPAS, fases=FASES_CRISP)


@pages_bp.route("/sobre-nosotros")
def about():
    return render_template("pages/about.html")
