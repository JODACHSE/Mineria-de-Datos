"""Blueprint `api`: datasets, calidad y consultas OLAP en JSON."""
from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request

from app.quality import DATASETS, compute_quality
from app.routes import _dirs
from app.services import datasets as ds
from app.services.etapa5 import VISTAS_BY_SLUG, parse_state, vista_query
from app.services.olap import OlapError
from app.services.reports import profile_dataset, query_dataset

api_bp = Blueprint("api", __name__, url_prefix="/api")


def _not_found(name: str):
    return jsonify(error=f"Dataset '{name}' no existe. Usa uno de: {list(DATASETS)}"), 404


@api_bp.route("/dataset/<name>")
def dataset(name):
    """Parámetros: q, producto, elemento, anio_min, anio_max, page, page_size, version=crudo|tratado."""
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


@api_bp.route("/r5/<slug>")
def r5_vista(slug):
    """Consulta OLAP de una vista de R5. Parámetros: rows, cols, measure, f_<nivel>."""
    if slug not in VISTAS_BY_SLUG:
        return jsonify(error=f"Vista '{slug}' no existe. Usa una de: {list(VISTAS_BY_SLUG)}"), 404
    try:
        state = parse_state(slug, request.args)
        return jsonify(state=state, **vista_query(current_app.config["R5_DB_PATH"], slug, state))
    except OlapError as exc:
        return jsonify(error=str(exc)), 400


@api_bp.route("/profile/<name>")
def profile(name):
    version = request.args.get("version", "crudo")
    r1_dir, r2_dir = _dirs()
    try:
        data = ds.load_dataset(name, version, r1_dir, r2_dir)
    except KeyError:
        return _not_found(name)
    return jsonify(profile_dataset(data, name, version, r1_dir))
