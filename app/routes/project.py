"""Blueprint 'project'.

Contiene:
- La landing page del proyecto.
- El entregable R1 ("Del problema a los datos").
- El entregable R2 ("Diagnóstico y calidad de los datos").
- Una pequeña API JSON que sirve los datasets ya curados (FAOSTAT y EVA),
  con filtrado y paginación en el servidor (esto es lo que hace la
  app "dinámica": el explorador de datos de R1.html no lee un JSON
  estático completo, sino que negocia con Flask en cada consulta).

Dos familias de esquema conviven aquí:
- FAOSTAT (fs, qcl, qcl_basicos): formato "largo" -> Área, Producto,
  Elemento, Año, Unidad, Valor.
- EVA (eva_basicos): formato "ancho" y municipal -> Departamento,
  Municipio, Cultivo, Año, con 4 variables numéricas propias
  (AreaSembrada, AreaCosechada, Produccion, Rendimiento).
Por eso compute_quality/api_dataset reciben la configuración de
columnas de cada dataset en vez de asumir un único esquema fijo.

La lógica de calidad (esquemas, perfilamiento, dimensiones) vive en
`app.quality` (Python puro, sin Flask) para poder reutilizarla también
desde `scripts/clean_datasets.py`.
"""
from __future__ import annotations

import json
from pathlib import Path

from flask import Blueprint, current_app, jsonify, render_template, request

from app.quality import (
    DATASET_SCHEMA,
    DATASETS,
    QUALITY_REQUIREMENTS,
    _count_duplicates,
    _rows_as_dicts,
    _to_float,
    build_problem_inventory,
    compute_dimensions,
    compute_quality,
    profile_columns,
)

DIMENSION_LABELS = ["completitud", "exactitud", "consistencia", "unicidad", "validez", "actualidad"]

project_bp = Blueprint("project", __name__)

_cache: dict[str, dict] = {}


def _load_dataset(name: str) -> dict:
    """Carga (con caché en memoria) la versión CRUDA (R1) de un dataset."""
    if name not in DATASETS:
        raise KeyError(name)
    if name in _cache:
        return _cache[name]

    path: Path = current_app.config["R1_JSON_DIR"] / DATASETS[name]
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    _cache[name] = data
    return data


def _load_treated_dataset(name: str) -> dict:
    """Carga (con caché en memoria) la versión TRATADA (R2) de un dataset.

    Generada offline por `scripts/clean_datasets.py` y commiteada en
    `app/static/data/R2/`, siguiendo el mismo patrón que R1 (los scripts
    son generadores offline, no se ejecutan en cada request).
    """
    cache_key = f"r2:{name}"
    if name not in DATASETS:
        raise KeyError(name)
    if cache_key in _cache:
        return _cache[cache_key]

    path: Path = current_app.config["R2_JSON_DIR"] / DATASETS[name]
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    _cache[cache_key] = data
    return data


def _load_treatment_log() -> dict:
    cache_key = "r2:log"
    if cache_key in _cache:
        return _cache[cache_key]
    path: Path = current_app.config["R2_JSON_DIR"] / "log_tratamiento.json"
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    _cache[cache_key] = data
    return data


@project_bp.route("/")
def index():
    """Landing page del proyecto."""
    return render_template("project/index.html")


@project_bp.route("/r1")
def r1():
    """Entregable R1: del problema a los datos."""
    qcl_basicos = _load_dataset("qcl_basicos")
    qcl = _load_dataset("qcl")
    fs = _load_dataset("fs")
    eva_basicos = _load_dataset("eva_basicos")

    quality = {
        "qcl_basicos": compute_quality(qcl_basicos, "qcl_basicos"),
        "qcl": compute_quality(qcl, "qcl"),
        "fs": compute_quality(fs, "fs"),
        "eva_basicos": compute_quality(eva_basicos, "eva_basicos"),
    }

    with open(current_app.config["R1_JSON_DIR"] / "faostat_fs_colombia.json", encoding="utf-8") as fh:
        fs_chart = json.load(fh)

    with open(current_app.config["R1_JSON_DIR"] / "integracion_eva_faostat.json", encoding="utf-8") as fh:
        integracion = json.load(fh)

    # --- Diagnóstico de consistencia específico de EVA (área cosechada
    # no puede superar el área sembrada; es un hallazgo real, no simulado) ---
    eva_rows = _rows_as_dicts(eva_basicos)
    eva_incons_area = sum(
        1 for r in eva_rows
        if _to_float(r.get("AreaCosechada")) is not None
        and _to_float(r.get("AreaSembrada")) is not None
        and _to_float(r.get("AreaCosechada")) > _to_float(r.get("AreaSembrada"))
    )
    eva_departamentos = len({r.get("Departamento") for r in eva_rows if r.get("Departamento")})
    eva_municipios_codigo = len({r.get("CodigoMunicipioDane") for r in eva_rows if r.get("CodigoMunicipioDane")})
    eva_municipios_nombre = len({r.get("Municipio") for r in eva_rows if r.get("Municipio")})

    # Un dato "vivo" para el hero: último valor no nulo de subalimentación
    subalim = fs_chart["datasets"][0]["data"]
    labels = fs_chart["labels"]
    ultimo_valor, ultimo_anio = None, None
    for lbl, val in zip(reversed(labels), reversed(subalim)):
        if val is not None:
            ultimo_valor, ultimo_anio = val, lbl
            break

    return render_template(
        "project/project/R1.html",
        quality=quality,
        fs_chart=fs_chart,
        integracion=integracion,
        ultimo_valor=ultimo_valor,
        ultimo_anio=ultimo_anio,
        n_productos_basicos=quality["qcl_basicos"]["products"],
        n_registros_qcl=quality["qcl"]["total"],
        n_registros_fs=quality["fs"]["total"],
        n_registros_eva=quality["eva_basicos"]["total"],
        eva_departamentos=eva_departamentos,
        eva_municipios_codigo=eva_municipios_codigo,
        eva_municipios_nombre=eva_municipios_nombre,
        eva_incons_area=eva_incons_area,
        eva_incons_area_pct=round(100 * eva_incons_area / len(eva_rows), 2) if eva_rows else 0,
        n_registros_totales=quality["qcl"]["total"] + quality["fs"]["total"] + quality["eva_basicos"]["total"],
    )


@project_bp.route("/r2")
def r2():
    """Entregable R2: diagnóstico y calidad de los datos."""
    with open(current_app.config["R1_JSON_DIR"] / "integracion_eva_faostat.json", encoding="utf-8") as fh:
        integracion = json.load(fh)
    treatment_log = _load_treatment_log()

    resultados = {}
    all_rows_raw = {}
    quality_compare = {}

    for name in DATASETS:
        schema = DATASET_SCHEMA[name]
        crudo = _load_dataset(name)
        tratado = _load_treated_dataset(name)
        rows_crudo = _rows_as_dicts(crudo)
        all_rows_raw[name] = rows_crudo

        kwargs = dict(integracion=integracion) if schema.get("accuracy_check") == "cruce_eva_faostat" else {}
        dimensiones_antes = compute_dimensions(crudo, name, **kwargs)
        dimensiones_despues = compute_dimensions(tratado, name, **kwargs)

        if name != "eva_basicos":
            # "Antes" refleja el método de R1 (llave de unicidad sin 'Unidad');
            # "después" ya usa la llave corregida (ver DATASET_SCHEMA[name]["unique_key_fields"]).
            total = len(rows_crudo)
            dup_antes = _count_duplicates(rows_crudo, schema["key_fields"])
            dimensiones_antes["unicidad"] = round(100 * (total - dup_antes) / total, 2) if total else None

        resultados[name] = dict(
            total=len(rows_crudo),
            total_tratado=len(tratado["rows"]),
            perfil_antes=profile_columns(rows_crudo, crudo["columns"], schema["column_meta"]),
            perfil_despues=profile_columns(_rows_as_dicts(tratado), tratado["columns"], schema["column_meta"]),
            dimensiones_antes=dimensiones_antes,
            dimensiones_despues=dimensiones_despues,
            requisitos=QUALITY_REQUIREMENTS[name],
        )
        quality_compare[name] = dict(
            labels=DIMENSION_LABELS,
            antes=[dimensiones_antes[d] for d in DIMENSION_LABELS],
            despues=[dimensiones_despues[d] for d in DIMENSION_LABELS],
        )

    inventario = build_problem_inventory(all_rows_raw, integracion=integracion)
    n_problemas_alto = sum(1 for p in inventario if p["nivel_impacto"] == "Alto")
    n_problemas_medio = sum(1 for p in inventario if p["nivel_impacto"] == "Medio")
    n_problemas_bajo = sum(1 for p in inventario if p["nivel_impacto"] == "Bajo")

    dataset_labels = {
        "eva_basicos": "EVA — producción municipal",
        "qcl": "FAOSTAT — todos los productos",
        "qcl_basicos": "FAOSTAT — cultivos básicos",
        "fs": "FAOSTAT — seguridad alimentaria",
    }

    return render_template(
        "project/project/R2.html",
        resultados=resultados,
        inventario=inventario,
        n_problemas_alto=n_problemas_alto,
        n_problemas_medio=n_problemas_medio,
        n_problemas_bajo=n_problemas_bajo,
        treatment_log=treatment_log,
        quality_compare=quality_compare,
        dataset_labels=dataset_labels,
        dimension_labels=DIMENSION_LABELS,
    )


@project_bp.route("/api/dataset/<name>")
def api_dataset(name):
    """Sirve un dataset filtrado y paginado en JSON.

    Query params soportados:
    - producto: coincidencia parcial (case-insensitive) sobre el campo
      "producto" del dataset (Producto en FAOSTAT, Cultivo en EVA)
    - elemento: coincidencia exacta sobre el campo "elemento" del dataset
      (Elemento en FAOSTAT, Departamento en EVA)
    - anio_min / anio_max: filtra por año
    - q: búsqueda libre sobre producto y elemento
    - version: "crudo" (default, datos de R1) o "tratado" (datos de R2,
      con las columnas de bandera del tratamiento aplicado)
    - page (default 1), page_size (default 25, máx 200)
    """
    version = request.args.get("version", "crudo")
    try:
        dataset = _load_treated_dataset(name) if version == "tratado" else _load_dataset(name)
    except KeyError:
        return jsonify(error=f"Dataset '{name}' no existe. Usa uno de: {list(DATASETS)}"), 404

    schema = DATASET_SCHEMA[name]
    producto_field = schema["filter_fields"].get("producto")
    elemento_field = schema["filter_fields"].get("elemento")
    year_field = schema["year_field"]

    rows = _rows_as_dicts(dataset)

    producto = request.args.get("producto", "").strip().lower()
    elemento = request.args.get("elemento", "").strip()
    q = request.args.get("q", "").strip().lower()
    anio_min = request.args.get("anio_min", type=int)
    anio_max = request.args.get("anio_max", type=int)

    def year_of(row):
        raw = str(row.get(year_field, ""))[:4]
        return int(raw) if raw.isdigit() else None

    filtered = rows
    if producto and producto_field:
        filtered = [r for r in filtered if producto in str(r.get(producto_field, "")).lower()]
    if elemento and elemento_field:
        filtered = [r for r in filtered if str(r.get(elemento_field, "")) == elemento]
    if q:
        filtered = [
            r for r in filtered
            if (producto_field and q in str(r.get(producto_field, "")).lower())
            or (elemento_field and q in str(r.get(elemento_field, "")).lower())
        ]
    if anio_min is not None:
        filtered = [r for r in filtered if (year_of(r) or 0) >= anio_min]
    if anio_max is not None:
        filtered = [r for r in filtered if (year_of(r) or 9999) <= anio_max]

    page = max(request.args.get("page", 1, type=int), 1)
    page_size = min(max(request.args.get("page_size", 25, type=int), 1), 200)
    start = (page - 1) * page_size
    end = start + page_size
    page_rows = filtered[start:end]

    return jsonify(
        dataset=name,
        columns=dataset["columns"],
        display_columns=schema["display_columns"],
        rows=page_rows,
        total=len(filtered),
        page=page,
        page_size=page_size,
        total_pages=max(1, -(-len(filtered) // page_size)),
        productos_disponibles=sorted({r.get(producto_field, "") for r in rows if producto_field and r.get(producto_field)}) if producto_field else [],
        elementos_disponibles=sorted({r.get(elemento_field, "") for r in rows if elemento_field and r.get(elemento_field)}) if elemento_field else [],
    )


@project_bp.route("/api/quality/<name>")
def api_quality(name):
    """Diagnóstico de calidad recalculado bajo demanda para un dataset."""
    try:
        dataset = _load_dataset(name)
    except KeyError:
        return jsonify(error=f"Dataset '{name}' no existe."), 404
    return jsonify(dataset=name, **compute_quality(dataset, name))


@project_bp.route("/api/profile/<name>")
def api_profile(name):
    """Perfilamiento por columna + las 6 dimensiones de calidad (entregable R2).

    Query params:
    - version: "crudo" (default, R1) o "tratado" (R2, con banderas de tratamiento).
    """
    version = request.args.get("version", "crudo")
    try:
        dataset = _load_treated_dataset(name) if version == "tratado" else _load_dataset(name)
    except KeyError:
        return jsonify(error=f"Dataset '{name}' no existe. Usa uno de: {list(DATASETS)}"), 404

    schema = DATASET_SCHEMA[name]
    rows = _rows_as_dicts(dataset)
    kwargs = {}
    if schema.get("accuracy_check") == "cruce_eva_faostat":
        with open(current_app.config["R1_JSON_DIR"] / "integracion_eva_faostat.json", encoding="utf-8") as fh:
            kwargs["integracion"] = json.load(fh)

    return jsonify(
        dataset=name,
        version=version,
        total=len(rows),
        columns=profile_columns(rows, dataset["columns"], schema["column_meta"]),
        dimensiones=compute_dimensions(dataset, name, **kwargs),
    )
