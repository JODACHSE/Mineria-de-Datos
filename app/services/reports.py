"""Construcción de los contextos de R1 y R2 y de las consultas de la API.

Toda la lógica pesada vive aquí; las rutas solo orquestan y renderizan.
"""
from __future__ import annotations

from pathlib import Path

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
from app.services import datasets as ds

DIMENSION_LABELS = ["completitud", "exactitud", "consistencia", "unicidad", "validez", "actualidad"]

DATASET_LABELS = {
    "eva_basicos": "EVA — producción municipal",
    "qcl": "FAOSTAT — todos los productos",
    "qcl_basicos": "FAOSTAT — cultivos básicos",
    "fs": "FAOSTAT — seguridad alimentaria",
}

EXPLORER_OPTIONS = [
    ("eva_basicos", "EVA — cultivos básicos (municipal)"),
    ("qcl_basicos", "FAOSTAT — cultivos básicos (nacional)"),
    ("qcl", "FAOSTAT — todos los productos (nacional)"),
    ("fs", "FAOSTAT — seguridad alimentaria"),
]


# ------------------------------------------------------------------ R1
def build_r1_context(r1_dir: Path) -> dict:
    qcl_basicos = ds.load_raw("qcl_basicos", r1_dir)
    qcl = ds.load_raw("qcl", r1_dir)
    fs = ds.load_raw("fs", r1_dir)
    eva = ds.load_raw("eva_basicos", r1_dir)

    quality = {
        "qcl_basicos": compute_quality(qcl_basicos, "qcl_basicos"),
        "qcl": compute_quality(qcl, "qcl"),
        "fs": compute_quality(fs, "fs"),
        "eva_basicos": compute_quality(eva, "eva_basicos"),
    }
    fs_chart = ds.load_fs_chart(r1_dir)
    integracion = ds.load_integracion(r1_dir)

    eva_rows = _rows_as_dicts(eva)
    eva_incons_area = sum(
        1
        for r in eva_rows
        if _to_float(r.get("AreaCosechada")) is not None
        and _to_float(r.get("AreaSembrada")) is not None
        and _to_float(r.get("AreaCosechada")) > _to_float(r.get("AreaSembrada"))
    )
    eva_departamentos = len({r.get("Departamento") for r in eva_rows if r.get("Departamento")})
    eva_municipios_codigo = len({r.get("CodigoMunicipioDane") for r in eva_rows if r.get("CodigoMunicipioDane")})
    eva_municipios_nombre = len({r.get("Municipio") for r in eva_rows if r.get("Municipio")})

    subalim = fs_chart["datasets"][0]["data"]
    labels = fs_chart["labels"]
    ultimo_valor, ultimo_anio = None, None
    for lbl, val in zip(reversed(labels), reversed(subalim)):
        if val is not None:
            ultimo_valor, ultimo_anio = val, lbl
            break

    n_totales = quality["qcl"]["total"] + quality["fs"]["total"] + quality["eva_basicos"]["total"]

    return dict(
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
        n_registros_totales=n_totales,
        explorer_options=EXPLORER_OPTIONS,
    )


# ------------------------------------------------------------------ R2
def build_r2_context(r1_dir: Path, r2_dir: Path) -> dict:
    """Costoso pero determinista: se calcula una vez por proceso (ver rutas)."""
    integracion = ds.load_integracion(r1_dir)
    treatment_log = ds.load_treatment_log(r2_dir)

    resultados, all_rows_raw, quality_compare = {}, {}, {}

    for name in DATASETS:
        schema = DATASET_SCHEMA[name]
        crudo = ds.load_raw(name, r1_dir)
        tratado = ds.load_treated(name, r2_dir)
        rows_crudo = _rows_as_dicts(crudo)
        all_rows_raw[name] = rows_crudo

        kwargs = dict(integracion=integracion) if schema.get("accuracy_check") == "cruce_eva_faostat" else {}
        dim_antes = compute_dimensions(crudo, name, **kwargs)
        dim_despues = compute_dimensions(tratado, name, **kwargs)

        if name != "eva_basicos":
            # "Antes" refleja el método de R1 (llave de unicidad sin 'Unidad').
            total = len(rows_crudo)
            dup_antes = _count_duplicates(rows_crudo, schema["key_fields"])
            dim_antes["unicidad"] = round(100 * (total - dup_antes) / total, 2) if total else None

        resultados[name] = dict(
            total=len(rows_crudo),
            perfil_antes=profile_columns(rows_crudo, crudo["columns"], schema["column_meta"]),
            dimensiones_antes=dim_antes,
            dimensiones_despues=dim_despues,
            requisitos=QUALITY_REQUIREMENTS[name],
        )
        quality_compare[name] = dict(
            labels=DIMENSION_LABELS,
            antes=[dim_antes[d] for d in DIMENSION_LABELS],
            despues=[dim_despues[d] for d in DIMENSION_LABELS],
        )

    profiles_raw = {name: r["perfil_antes"] for name, r in resultados.items()}
    inventario = build_problem_inventory(all_rows_raw, profiles=profiles_raw, integracion=integracion)

    return dict(
        resultados=resultados,
        inventario=inventario,
        n_problemas_alto=sum(1 for p in inventario if p["nivel_impacto"] == "Alto"),
        n_problemas_medio=sum(1 for p in inventario if p["nivel_impacto"] == "Medio"),
        n_problemas_bajo=sum(1 for p in inventario if p["nivel_impacto"] == "Bajo"),
        treatment_log=treatment_log,
        quality_compare=quality_compare,
        dataset_labels=DATASET_LABELS,
        dimension_labels=DIMENSION_LABELS,
        n_registros_totales=sum(r["total"] for r in resultados.values()),
        explorer_options=EXPLORER_OPTIONS,
    )


# ------------------------------------------------------------------ API
def query_dataset(dataset: dict, name: str, args: dict) -> dict:
    """Filtra y pagina un dataset. `args` es un dict con las query params."""
    schema = DATASET_SCHEMA[name]
    producto_field = schema["filter_fields"].get("producto")
    elemento_field = schema["filter_fields"].get("elemento")
    year_field = schema["year_field"]
    rows = _rows_as_dicts(dataset)

    producto = (args.get("producto") or "").strip().lower()
    elemento = (args.get("elemento") or "").strip()
    q = (args.get("q") or "").strip().lower()
    anio_min = _int_or_none(args.get("anio_min"))
    anio_max = _int_or_none(args.get("anio_max"))

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

    page = max(_int_or_none(args.get("page")) or 1, 1)
    page_size = min(max(_int_or_none(args.get("page_size")) or 25, 1), 200)
    start = (page - 1) * page_size
    page_rows = filtered[start : start + page_size]

    return dict(
        dataset=name,
        columns=dataset["columns"],
        display_columns=schema["display_columns"],
        rows=page_rows,
        total=len(filtered),
        page=page,
        page_size=page_size,
        total_pages=max(1, -(-len(filtered) // page_size)),
        productos_disponibles=sorted({r.get(producto_field, "") for r in rows if r.get(producto_field)}) if producto_field else [],
        elementos_disponibles=sorted({r.get(elemento_field, "") for r in rows if r.get(elemento_field)}) if elemento_field else [],
    )


def profile_dataset(dataset: dict, name: str, version: str, r1_dir: Path) -> dict:
    schema = DATASET_SCHEMA[name]
    rows = _rows_as_dicts(dataset)
    kwargs = {}
    if schema.get("accuracy_check") == "cruce_eva_faostat":
        kwargs["integracion"] = ds.load_integracion(r1_dir)
    return dict(
        dataset=name,
        version=version,
        total=len(rows),
        columns=profile_columns(rows, dataset["columns"], schema["column_meta"]),
        dimensiones=compute_dimensions(dataset, name, **kwargs),
    )


def _int_or_none(value) -> int | None:
    try:
        return int(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None
