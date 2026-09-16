"""Blueprint `api`: datasets paginados/filtrados y métricas de calidad en JSON."""
from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request

from app.quality import DATASETS, compute_quality
from app.services import datasets as ds
from app.services.reports import profile_dataset, query_dataset

api_bp = Blueprint("api", __name__, url_prefix="/api")


def _dirs():
    cfg = current_app.config
    return cfg["R1_JSON_DIR"], cfg["R2_JSON_DIR"]


def _not_found(name: str):
    return jsonify(error=f"Dataset '{name}' no existe. Usa uno de: {list(DATASETS)}"), 404


@api_bp.route("/dataset/<name>")
def dataset(name):
    """Params: q, producto, elemento, anio_min, anio_max, page, page_size, version=crudo|tratado."""
    version = request.args.get("version", "crudo")
    r1_dir, r2_dir = _dirs()
    try:
        data = ds.load_dataset(name, version, r1_dir, r2_dir)
    except KeyError:
        return _not_found(name)
    return jsonify(query_dataset(data, name, request.args))


@api_bp.route("/quality/<name>")
def quality(name):
    r1_dir, _ = _dirs()
    try:
        data = ds.load_raw(name, r1_dir)
    except KeyError:
        return _not_found(name)
    return jsonify(dataset=name, **compute_quality(data, name))


@api_bp.route("/profile/<name>")
def profile(name):
    version = request.args.get("version", "crudo")
    r1_dir, r2_dir = _dirs()
    try:
        data = ds.load_dataset(name, version, r1_dir, r2_dir)
    except KeyError:
        return _not_found(name)
    return jsonify(profile_dataset(data, name, version, r1_dir))
