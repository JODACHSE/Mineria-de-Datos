"""Lógica de calidad de datos: esquemas, perfilamiento y diagnóstico.

Módulo Python puro (sin dependencia de Flask ni de `current_app`), para
que tanto las rutas (`app/routes/project.py`) como los scripts offline
(`scripts/clean_datasets.py`) puedan reutilizarlo sin necesitar un
contexto de aplicación.

Dos familias de esquema conviven aquí:
- FAOSTAT (fs, qcl, qcl_basicos): formato "largo" -> Área, Producto,
  Elemento, Año, Unidad, Valor.
- EVA (eva_basicos): formato "ancho" y municipal -> Departamento,
  Municipio, Cultivo, Año, con 4 variables numéricas propias
  (AreaSembrada, AreaCosechada, Produccion, Rendimiento).

`compute_quality()` es la función de diagnóstico usada por R1
(`/r1`, `/api/quality/<name>`) y se mantiene **congelada**: mismas
claves de salida, misma lógica, para no introducir regresiones en un
entregable ya completado. El perfilamiento por columna y las 6
dimensiones de calidad de R2 viven en funciones nuevas y separadas
(`profile_columns`, `compute_dimensions`, etc.).
"""
from __future__ import annotations

import re
import statistics
from collections import Counter, defaultdict

# Nombre lógico -> archivo físico dentro de app/static/data/R1
DATASETS = {
    "qcl": "qcl.json",
    "qcl_basicos": "qcl_basicos.json",
    "fs": "fs.json",
    "eva_basicos": "eva_basicos.json",
}

# Metadata de columnas compartida por los 3 datasets FAOSTAT (formato largo).
_FAOSTAT_COLUMN_META = {
    "Área": {"tipo": "categorico", "dominio": {"Colombia"}},
    "Elemento": {"tipo": "categorico"},
    "Producto": {"tipo": "categorico"},
    "Año": {"tipo": "temporal"},
    "Unidad": {"tipo": "categorico"},
    "Valor": {"tipo": "numerico", "rango": (0, None)},
}

_EVA_COLUMN_META = {
    "CodigoDeptoDane": {"tipo": "codigo", "pattern": r"^\d{2}$"},
    "Departamento": {"tipo": "categorico"},
    "CodigoMunicipioDane": {"tipo": "codigo", "pattern": r"^\d{5}$"},
    "Municipio": {"tipo": "texto"},
    "GrupoCultivo": {"tipo": "categorico"},
    "Subgrupo": {"tipo": "categorico"},
    "Cultivo": {"tipo": "categorico", "dominio": {"Maíz", "Arroz", "Papa", "Plátano", "Yuca", "Frijol"}},
    "DesagregacionCultivo": {"tipo": "texto"},
    "Anio": {"tipo": "temporal", "rango": (2019, 2024)},
    "Periodo": {"tipo": "categorico"},
    "AreaSembrada": {"tipo": "numerico", "rango": (0, None)},
    "AreaCosechada": {"tipo": "numerico", "rango": (0, None)},
    "Produccion": {"tipo": "numerico", "rango": (0, None)},
    "Rendimiento": {"tipo": "numerico", "rango": (0, None)},
    "CicloCultivo": {"tipo": "categorico"},
    "EstadoFisico": {"tipo": "categorico"},
    "CodigoCultivo": {"tipo": "codigo"},
    "NombreCientifico": {"tipo": "texto"},
}

# Configuración de columnas por dataset: qué campo es la "clave" para
# detectar duplicados, cuáles son numéricas (para completitud/validez),
# y cuáles son las columnas "categóricas" que la API expone para filtrar
# y que el explorador de datos usa para poblar sus selects.
#
# Además de lo ya usado por R1 (key_fields, numeric_fields, filter_fields,
# year_field, display_columns), R2 añade:
# - column_meta: metadata por columna para el perfilamiento (profile_columns).
# - campos_criticos: columnas que alimentan directamente el análisis
#   (usadas por completitud/validez/nivel de impacto).
# - unique_key_fields: llave de unicidad para R2 (puede ampliar key_fields).
# - consistency_check / accuracy_check: qué regla de negocio usar en
#   compute_dimensions() para las dimensiones "consistencia" y "exactitud".
DATASET_SCHEMA = {
    "qcl": {
        "key_fields": ("Área", "Producto", "Elemento", "Año"),
        "numeric_fields": ("Valor",),
        "filter_fields": {"producto": "Producto", "elemento": "Elemento"},
        "year_field": "Año",
        "display_columns": ["Área", "Producto", "Elemento", "Año", "Unidad", "Valor"],
        "column_meta": _FAOSTAT_COLUMN_META,
        "campos_criticos": ("Valor", "Año", "Producto", "Elemento"),
        "unique_key_fields": ("Área", "Producto", "Elemento", "Unidad", "Año"),
        "consistency_check": "unidad_por_elemento",
        "accuracy_check": "cruce_eva_faostat",
    },
    "qcl_basicos": {
        "key_fields": ("Área", "Producto", "Elemento", "Año"),
        "numeric_fields": ("Valor",),
        "filter_fields": {"producto": "Producto", "elemento": "Elemento"},
        "year_field": "Año",
        "display_columns": ["Área", "Producto", "Elemento", "Año", "Unidad", "Valor"],
        "column_meta": _FAOSTAT_COLUMN_META,
        "campos_criticos": ("Valor", "Año", "Producto", "Elemento"),
        "unique_key_fields": ("Área", "Producto", "Elemento", "Unidad", "Año"),
        "consistency_check": "unidad_por_elemento",
        "accuracy_check": "cruce_eva_faostat",
    },
    "fs": {
        "key_fields": ("Área", "Producto", "Elemento", "Año"),
        "numeric_fields": ("Valor",),
        "filter_fields": {"producto": "Producto", "elemento": "Elemento"},
        "year_field": "Año",
        "display_columns": ["Área", "Producto", "Elemento", "Año", "Unidad", "Valor"],
        "column_meta": _FAOSTAT_COLUMN_META,
        "campos_criticos": ("Valor", "Año", "Producto"),
        "unique_key_fields": ("Área", "Producto", "Elemento", "Unidad", "Año"),
        "consistency_check": "unidad_por_elemento",
        "accuracy_check": "ci_bounds",
    },
    "eva_basicos": {
        "key_fields": ("CodigoMunicipioDane", "Cultivo", "DesagregacionCultivo", "Anio", "Periodo"),
        "numeric_fields": ("AreaSembrada", "AreaCosechada", "Produccion", "Rendimiento"),
        "filter_fields": {"producto": "Cultivo", "elemento": "Departamento"},
        "year_field": "Anio",
        "display_columns": ["Departamento", "Municipio", "Cultivo", "Anio", "Periodo",
                             "AreaSembrada", "AreaCosechada", "Produccion", "Rendimiento"],
        "column_meta": _EVA_COLUMN_META,
        "campos_criticos": ("AreaSembrada", "AreaCosechada", "Produccion", "Rendimiento",
                            "Anio", "Cultivo", "CodigoMunicipioDane"),
        "unique_key_fields": ("CodigoMunicipioDane", "Cultivo", "DesagregacionCultivo", "Anio", "Periodo"),
        "consistency_check": "area_vs_sembrada",
        "accuracy_check": "rendimiento_calculado",
    },
}

# Umbrales de calidad exigidos (punto 2 del enunciado de R2: "requisitos
# de calidad"), definidos según el uso previsto de cada dataset (análisis
# de seguridad alimentaria y producción agrícola para actores de política
# pública: exige datos completos, sin duplicados, dentro de rango y
# razonablemente vigentes; la exactitud/consistencia entre fuentes es
# deseable pero se sabe de antemano que hay divergencias metodológicas
# reales entre EVA y FAOSTAT, por eso el umbral de exactitud es más laxo
# para los datasets FAOSTAT que dependen del cruce con EVA).
QUALITY_REQUIREMENTS = {
    "eva_basicos": {"completitud": 95, "unicidad": 99, "validez": 90, "consistencia": 80, "exactitud": 95, "actualidad": 60},
    "qcl": {"completitud": 90, "unicidad": 99, "validez": 90, "consistencia": 80, "exactitud": 70, "actualidad": 60},
    "qcl_basicos": {"completitud": 95, "unicidad": 99, "validez": 90, "consistencia": 80, "exactitud": 70, "actualidad": 60},
    "fs": {"completitud": 90, "unicidad": 99, "validez": 90, "consistencia": 80, "exactitud": 90, "actualidad": 40},
}

_cache: dict[str, dict] = {}


def _rows_as_dicts(dataset: dict) -> list[dict]:
    cols = dataset["columns"]
    return [dict(zip(cols, row)) for row in dataset["rows"]]


def _to_float(value):
    try:
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return None


def compute_quality(dataset: dict, schema_name: str = "qcl") -> dict:
    """Diagnóstico de calidad calculado en vivo (no precalculado a mano).

    Cubre completitud, unicidad y validez para CUALQUIER dataset
    registrado en DATASET_SCHEMA (no asume un único esquema de columnas).

    NOTA: esta función es la que usa el entregable R1 (ya completado).
    Se mantiene sin cambios de comportamiento; las 6 dimensiones de R2
    viven en `compute_dimensions()`.
    """
    schema = DATASET_SCHEMA[schema_name]
    key_fields = schema["key_fields"]
    numeric_fields = schema["numeric_fields"]

    rows = _rows_as_dicts(dataset)
    total = len(rows)
    if total == 0:
        return dict(total=0, completeness=0, uniqueness=0, validity=0,
                     duplicates=0, negatives=0, missing_valor=0, products=0)

    seen = set()
    duplicates = 0
    missing_numeric = 0
    negatives = 0
    products = set()

    producto_field = schema["filter_fields"].get("producto")

    for r in rows:
        key = tuple(r.get(f) for f in key_fields)
        if key in seen:
            duplicates += 1
        else:
            seen.add(key)

        row_has_missing = False
        for nf in numeric_fields:
            val = r.get(nf)
            if val in (None, "", "NaN"):
                row_has_missing = True
            else:
                fval = _to_float(val)
                if fval is not None and fval < 0:
                    negatives += 1
        if row_has_missing:
            missing_numeric += 1

        if producto_field and r.get(producto_field):
            products.add(r[producto_field])

    completeness = round(100 * (total - missing_numeric) / total, 2)
    uniqueness = round(100 * (total - duplicates) / total, 2)
    validity = round(100 * max(0, total - negatives) / total, 2)

    return dict(
        total=total,
        completeness=completeness,
        uniqueness=uniqueness,
        validity=validity,
        duplicates=duplicates,
        negatives=negatives,
        missing_valor=missing_numeric,
        products=len(products),
    )


# --------------------------------------------------------------------
# R2 · Perfilamiento por columna
# --------------------------------------------------------------------

def _percentile(sorted_vals: list[float], p: float) -> float:
    n = len(sorted_vals)
    if n == 1:
        return sorted_vals[0]
    k = (n - 1) * p
    f, c = int(k), min(int(k) + 1, n - 1)
    return sorted_vals[f] + (sorted_vals[c] - sorted_vals[f]) * (k - f)


def _numeric_stats(sorted_vals: list[float]) -> dict:
    """Estadísticos descriptivos + outliers por rango intercuartílico (1.5×IQR)."""
    n = len(sorted_vals)
    q1, q3 = _percentile(sorted_vals, 0.25), _percentile(sorted_vals, 0.75)
    iqr = q3 - q1
    lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    outliers = sum(1 for v in sorted_vals if v < lo or v > hi)
    return dict(
        minimo=sorted_vals[0],
        maximo=sorted_vals[-1],
        media=round(statistics.mean(sorted_vals), 3),
        mediana=round(statistics.median(sorted_vals), 3),
        desviacion=round(statistics.pstdev(sorted_vals), 3) if n > 1 else 0.0,
        q1=round(q1, 3),
        q3=round(q3, 3),
        outliers_iqr=outliers,
        outliers_iqr_pct=round(100 * outliers / n, 2) if n else 0.0,
    )


def profile_columns(rows: list[dict], columns: list[str], column_meta: dict) -> dict[str, dict]:
    """Perfilamiento por columna en una sola pasada (Python puro).

    Para ~48.932 filas x 18 columnas (el dataset más grande del proyecto)
    esto son ~880k celdas: trivial para CPython en el contexto de una
    petición Flask, por lo que no hace falta pandas ni precálculo offline
    para mantener la filosofía "en vivo" ya usada por R1.
    """
    n = len(rows)
    acc = {c: {"nulos": 0, "counter": Counter(), "numeric": []} for c in columns}

    for r in rows:
        for c in columns:
            v = r.get(c)
            if v in (None, "", "NaN"):
                acc[c]["nulos"] += 1
                continue
            acc[c]["counter"][v] += 1
            if column_meta.get(c, {}).get("tipo") == "numerico":
                fv = _to_float(v)
                if fv is not None:
                    acc[c]["numeric"].append(fv)

    profile = {}
    for c in columns:
        a = acc[c]
        meta = column_meta.get(c, {})
        entry = dict(
            tipo=meta.get("tipo", "desconocido"),
            n_nulos=a["nulos"],
            pct_nulos=round(100 * a["nulos"] / n, 2) if n else 0.0,
            n_unicos=len(a["counter"]),
        )
        if meta.get("tipo") == "numerico" and a["numeric"]:
            entry.update(_numeric_stats(sorted(a["numeric"])))
        else:
            entry["top_valores"] = a["counter"].most_common(5)

        if "dominio" in meta:
            entry["fuera_de_dominio"] = sum(cnt for v, cnt in a["counter"].items() if v not in meta["dominio"])
        if "rango" in meta:
            lo, hi = meta["rango"]
            entry["fuera_de_rango"] = sum(
                cnt for v, cnt in a["counter"].items()
                if (fv := _to_float(v)) is not None and ((lo is not None and fv < lo) or (hi is not None and fv > hi))
            )
        if "pattern" in meta:
            rx = re.compile(meta["pattern"])
            entry["no_conforme_patron"] = sum(cnt for v, cnt in a["counter"].items() if not rx.match(str(v)))
        profile[c] = entry
    return profile


def profile_dataset(dataset: dict, schema_name: str) -> dict[str, dict]:
    """Atajo: perfila un dataset ya cargado (formato {columns, rows})."""
    schema = DATASET_SCHEMA[schema_name]
    rows = _rows_as_dicts(dataset)
    return profile_columns(rows, dataset["columns"], schema["column_meta"])


# --------------------------------------------------------------------
# R2 · Las 6 dimensiones de calidad
# --------------------------------------------------------------------

def _year_of(value, year_field_is_range: bool = False) -> int | None:
    raw = str(value)[:4]
    return int(raw) if raw.isdigit() else None


def _count_duplicates(rows: list[dict], key_fields: tuple[str, ...]) -> int:
    """Cuenta filas duplicadas bajo una llave dada. Reutilizable para comparar
    la unicidad medida con la llave original de R1 (`key_fields`) contra la
    llave corregida de R2 (`unique_key_fields`)."""
    seen = set()
    duplicados = 0
    for r in rows:
        k = tuple(r.get(f) for f in key_fields)
        if k in seen:
            duplicados += 1
        else:
            seen.add(k)
    return duplicados


def _consistencia_unidad_por_elemento(rows: list[dict]) -> tuple[int, int]:
    """Para cada par (Producto, Elemento), toma la Unidad modal y cuenta
    filas que no coinciden.

    Se agrupa por (Producto, Elemento) y NO solo por Elemento: un mismo
    Elemento (p. ej. "Producción") cubre en FAOSTAT tanto cultivos
    (toneladas) como ganadería (cabezas, kg/ha, etc.), así que agrupar
    solo por Elemento generaba cientos de falsos positivos por
    heterogeneidad legítima de producto. Agrupando por (Producto,
    Elemento) el chequeo aísla exactamente el caso real: huevos con
    Producción reportada en 'toneladas' Y en '1000 No.'.
    """
    por_grupo = defaultdict(Counter)
    for r in rows:
        por_grupo[(r.get("Producto"), r.get("Elemento"))][r.get("Unidad")] += 1
    modal = {k: c.most_common(1)[0][0] for k, c in por_grupo.items()}
    n_incons = sum(1 for r in rows if r.get("Unidad") != modal.get((r.get("Producto"), r.get("Elemento"))))
    return n_incons, len(rows)


def _consistencia_area_vs_sembrada(rows: list[dict]) -> tuple[int, int]:
    verificables = [
        r for r in rows
        if _to_float(r.get("AreaCosechada")) is not None and _to_float(r.get("AreaSembrada")) is not None
    ]
    n_incons = sum(
        1 for r in verificables
        if _to_float(r["AreaCosechada"]) > _to_float(r["AreaSembrada"])
    )
    return n_incons, len(verificables)


def _exactitud_rendimiento_calculado(rows: list[dict], tolerancia: float = 0.01) -> tuple[int, int]:
    """EVA: Producción/AreaCosechada vs. Rendimiento reportado (tolerancia relativa 1%)."""
    n_ok, n_verificables = 0, 0
    for r in rows:
        area = _to_float(r.get("AreaCosechada"))
        prod = _to_float(r.get("Produccion"))
        rend = _to_float(r.get("Rendimiento"))
        if not area or prod is None or rend is None:
            continue
        n_verificables += 1
        calculado = prod / area
        base = max(abs(rend), 1e-9)
        if abs(calculado - rend) / base <= tolerancia:
            n_ok += 1
    return n_ok, n_verificables


def _exactitud_cruce_eva_faostat(integracion: dict | None) -> float | None:
    """qcl/qcl_basicos: 100 - promedio(|Diferencia_pct|) de integracion_eva_faostat.json."""
    if not integracion or not integracion.get("rows"):
        return None
    cols = integracion["columns"]
    idx = cols.index("Diferencia_pct")
    diffs = [abs(row[idx]) for row in integracion["rows"] if row[idx] is not None]
    if not diffs:
        return None
    return round(max(0.0, min(100.0, 100 - (sum(diffs) / len(diffs)))), 2)


def _exactitud_ci_bounds(rows: list[dict]) -> tuple[int, int]:
    """fs: donde existan Valor + límites de intervalo de confianza, Lower <= Valor <= Upper."""
    lower_key = "Confidence interval: Lower bound"
    upper_key = "Confidence interval: Upper bound"
    por_grupo = defaultdict(dict)
    for r in rows:
        clave = (r.get("Producto"), r.get("Año"))
        elemento = r.get("Elemento")
        valor = _to_float(r.get("Valor"))
        if elemento in ("Valor", lower_key, upper_key) and valor is not None:
            por_grupo[clave][elemento] = valor

    n_ok, n_verificables = 0, 0
    for medidas in por_grupo.values():
        if "Valor" in medidas and lower_key in medidas and upper_key in medidas:
            n_verificables += 1
            if medidas[lower_key] <= medidas["Valor"] <= medidas[upper_key]:
                n_ok += 1
    return n_ok, n_verificables


def compute_dimensions(dataset: dict, schema_name: str, *, integracion: dict | None = None,
                        hoy_anio: int = 2026) -> dict:
    """Calcula las 6 dimensiones de calidad exigidas por el entregable R2.

    Cada valor es 0-100, o `None` cuando la dimensión "no aplica" (p. ej.
    exactitud en un dataset sin mecanismo de contraste disponible) — nunca
    se inventa un número para rellenar una celda.
    """
    schema = DATASET_SCHEMA[schema_name]
    rows = _rows_as_dicts(dataset)
    total = len(rows)
    if total == 0:
        return dict(completitud=None, exactitud=None, consistencia=None,
                     unicidad=None, validez=None, actualidad=None)

    campos_criticos = schema["campos_criticos"]
    column_meta = schema["column_meta"]

    # --- Completitud: nulos en campos críticos ---
    nulos_criticos = sum(1 for r in rows for f in campos_criticos if r.get(f) in (None, "", "NaN"))
    completitud = round(100 * (1 - nulos_criticos / (total * len(campos_criticos))), 2)

    # --- Unicidad: duplicados bajo unique_key_fields ---
    duplicados = _count_duplicates(rows, schema["unique_key_fields"])
    unicidad = round(100 * (total - duplicados) / total, 2)

    # --- Validez: violaciones de rango/dominio/patrón en campos críticos ---
    filas_invalidas = 0
    for r in rows:
        invalida = False
        for f in campos_criticos:
            meta = column_meta.get(f, {})
            v = r.get(f)
            if v in (None, "", "NaN"):
                continue
            if "rango" in meta:
                fv = _to_float(v)
                lo, hi = meta["rango"]
                if fv is not None and ((lo is not None and fv < lo) or (hi is not None and fv > hi)):
                    invalida = True
                    break
            if "dominio" in meta and v not in meta["dominio"]:
                invalida = True
                break
            if "pattern" in meta and not re.match(meta["pattern"], str(v)):
                invalida = True
                break
        if invalida:
            filas_invalidas += 1
    validez = round(100 * (1 - filas_invalidas / total), 2)

    # --- Consistencia (regla específica por dataset) ---
    check = schema.get("consistency_check")
    if check == "area_vs_sembrada":
        n_incons, n_verif = _consistencia_area_vs_sembrada(rows)
    elif check == "unidad_por_elemento":
        n_incons, n_verif = _consistencia_unidad_por_elemento(rows)
    else:
        n_incons, n_verif = 0, 0
    consistencia = round(100 * (1 - n_incons / n_verif), 2) if n_verif else None

    # --- Exactitud (regla específica por dataset) ---
    accuracy_check = schema.get("accuracy_check")
    if accuracy_check == "rendimiento_calculado":
        n_ok, n_verif_ex = _exactitud_rendimiento_calculado(rows)
        exactitud = round(100 * n_ok / n_verif_ex, 2) if n_verif_ex else None
    elif accuracy_check == "cruce_eva_faostat":
        exactitud = _exactitud_cruce_eva_faostat(integracion)
    elif accuracy_check == "ci_bounds":
        n_ok, n_verif_ex = _exactitud_ci_bounds(rows)
        exactitud = round(100 * n_ok / n_verif_ex, 2) if n_verif_ex else None
    else:
        exactitud = None

    # --- Actualidad: antigüedad del último año disponible respecto a hoy ---
    year_field = schema["year_field"]
    anios = [_year_of(r.get(year_field)) for r in rows]
    anios = [a for a in anios if a is not None]
    ventana = 15 if schema_name == "fs" else 10
    if anios:
        antiguedad = max(0, hoy_anio - max(anios))
        actualidad = round(100 * max(0.0, 1 - antiguedad / ventana), 2)
    else:
        actualidad = None

    return dict(
        completitud=completitud,
        exactitud=exactitud,
        consistencia=consistencia,
        unicidad=unicidad,
        validez=validez,
        actualidad=actualidad,
    )


# --------------------------------------------------------------------
# R2 · Inventario de problemas
# --------------------------------------------------------------------

def nivel_impacto(pct_afectados: float, campo_critico: bool) -> str:
    """Regla determinista y documentada para el "nivel de impacto" del
    inventario de problemas: combina severidad relativa (% de registros
    afectados) con si el campo alimenta directamente el análisis.
    """
    if pct_afectados <= 0:
        return "Ninguno"
    if campo_critico and pct_afectados >= 10:
        return "Alto"
    if campo_critico and pct_afectados >= 2:
        return "Medio"
    if not campo_critico and pct_afectados >= 20:
        return "Medio"
    return "Bajo"


def _iqr_bounds_por_grupo(rows: list[dict], group_fields: tuple[str, ...], value_field: str) -> dict[tuple, tuple[float, float]]:
    """Límites IQR (± 1.5×RIC) de `value_field`, calculados POR GRUPO
    (`group_fields`) en vez de globalmente.

    En los datasets FAOSTAT de formato largo, 'Valor' mezcla en una sola
    columna magnitudes no comparables (producción en toneladas, existencias
    en cabezas, rendimiento en kg/ha, indicadores en %, según el Producto y
    el Elemento de cada fila); calcular un IQR global sobre esa columna
    produciría cientos de "atípicos" que en realidad solo reflejan esa
    heterogeneidad legítima. Agrupando por (Producto, Elemento) — cada
    grupo SÍ comparte unidad — el chequeo vuelve a ser significativo.
    """
    valores_por_grupo: dict[tuple, list[float]] = defaultdict(list)
    for r in rows:
        v = _to_float(r.get(value_field))
        if v is not None:
            valores_por_grupo[tuple(r.get(f) for f in group_fields)].append(v)

    bounds = {}
    for k, vals in valores_por_grupo.items():
        if len(vals) < 4:  # el rango intercuartílico no es significativo con muestras muy pequeñas
            continue
        ordenados = sorted(vals)
        q1, q3 = _percentile(ordenados, 0.25), _percentile(ordenados, 0.75)
        iqr = q3 - q1
        bounds[k] = (q1 - 1.5 * iqr, q3 + 1.5 * iqr)
    return bounds


def _outliers_grupo_iqr(rows: list[dict], group_fields: tuple[str, ...], value_field: str) -> tuple[int, int]:
    """Cuenta outliers de `value_field` usando límites IQR por grupo (ver
    `_iqr_bounds_por_grupo`). Devuelve (n_outliers, n_evaluados) — los
    grupos con menos de 4 valores no se evalúan (RIC no significativo)."""
    bounds = _iqr_bounds_por_grupo(rows, group_fields, value_field)
    n_outliers, n_evaluados = 0, 0
    for r in rows:
        v = _to_float(r.get(value_field))
        if v is None:
            continue
        k = tuple(r.get(f) for f in group_fields)
        if k not in bounds:
            continue
        n_evaluados += 1
        lo, hi = bounds[k]
        if v < lo or v > hi:
            n_outliers += 1
    return n_outliers, n_evaluados


def _hallazgo_duplicados_por_unidad(rows: list[dict], key_fields: tuple[str, ...]) -> tuple[int, int]:
    """Agrupa por `key_fields` SIN 'Unidad' y cuenta cuántos grupos mezclan más
    de una Unidad distinta (p. ej. huevos en toneladas Y en 1000 unidades) —
    esas filas parecían "duplicadas" bajo la llave original de R1.

    Devuelve (n_grupos_ambiguos, n_filas_afectadas).
    """
    grupos: dict[tuple, set] = defaultdict(set)
    miembros: dict[tuple, list] = defaultdict(list)
    for r in rows:
        k = tuple(r.get(f) for f in key_fields)
        grupos[k].add(r.get("Unidad"))
        miembros[k].append(r)

    n_grupos_multi = 0
    n_filas_afectadas = 0
    for k, unidades in grupos.items():
        if len(unidades) > 1:
            n_grupos_multi += 1
            n_filas_afectadas += len(miembros[k])
    return n_grupos_multi, n_filas_afectadas


def build_problem_inventory(all_rows: dict[str, list[dict]], integracion: dict | None = None) -> list[dict]:
    """Inventario de problemas (punto 5 del enunciado de R2).

    `all_rows` = {nombre_dataset: [fila_dict, ...]} ya cargados (Python
    puro, sin depender de Flask). Genera entradas automáticas a partir del
    perfilamiento por columna (nulos, fuera de rango/dominio, valores no
    conformes, outliers) más 3 hallazgos narrativos que requieren
    conocimiento de dominio (área>sembrada en EVA, doble unidad en qcl,
    intervalos de confianza en fs).
    """
    inventario: list[dict] = []
    _id_counter: dict[str, int] = defaultdict(int)

    def _add(dataset, variable, descripcion, n_afectados, total, dimension, evidencia, causa_probable,
              campo_critico=None):
        pct = round(100 * n_afectados / total, 2) if total else 0.0
        if campo_critico is None:
            campo_critico = variable in DATASET_SCHEMA[dataset]["campos_criticos"]
        _id_counter[dataset] += 1
        inventario.append(dict(
            id=f"{dataset}-{_id_counter[dataset]:02d}",
            dataset=dataset,
            variable=variable,
            descripcion=descripcion,
            n_afectados=n_afectados,
            pct_afectados=pct,
            dimension=dimension,
            nivel_impacto=nivel_impacto(pct, campo_critico),
            evidencia=evidencia,
            causa_probable=causa_probable,
        ))

    # Datasets FAOSTAT de formato largo: la columna 'Valor' mezcla productos
    # y elementos con unidades distintas, así que su outlier IQR *global* no
    # es significativo (ver _outliers_grupo_iqr) y se excluye del bucle
    # automático; se reemplaza por un hallazgo narrativo agrupado más abajo.
    faostat_datasets = {n for n, s in DATASET_SCHEMA.items() if s.get("consistency_check") == "unidad_por_elemento"}

    for name, rows in all_rows.items():
        schema = DATASET_SCHEMA[name]
        total = len(rows)
        if total == 0:
            continue
        profile = profile_columns(rows, list(schema["column_meta"].keys()), schema["column_meta"])
        for col, p in profile.items():
            campo_critico = col in schema["campos_criticos"]
            if p["n_nulos"] > 0:
                _add(name, col, f"{p['n_nulos']} valores nulos o vacíos en '{col}'.",
                     p["n_nulos"], total, "Completitud",
                     f"app.quality.profile_columns('{name}')['{col}'].n_nulos",
                     "Ausencia de reporte o de validación de campo obligatorio en la fuente.", campo_critico)
            if p.get("fuera_de_rango", 0) > 0:
                _add(name, col, f"{p['fuera_de_rango']} valores fuera del rango esperado en '{col}'.",
                     p["fuera_de_rango"], total, "Validez",
                     f"app.quality.profile_columns('{name}')['{col}'].fuera_de_rango",
                     "Errores de captura o ausencia de validaciones de rango en el origen.", campo_critico)
            if p.get("fuera_de_dominio", 0) > 0:
                _add(name, col, f"{p['fuera_de_dominio']} valores fuera del dominio permitido en '{col}'.",
                     p["fuera_de_dominio"], total, "Validez",
                     f"app.quality.profile_columns('{name}')['{col}'].fuera_de_dominio",
                     "Variantes de categoría no homologadas o error de digitación.", campo_critico)
            if p.get("no_conforme_patron", 0) > 0:
                _add(name, col, f"{p['no_conforme_patron']} valores que no cumplen el formato esperado en '{col}'.",
                     p["no_conforme_patron"], total, "Validez",
                     f"app.quality.profile_columns('{name}')['{col}'].no_conforme_patron",
                     "Formato inconsistente entre fuentes o entre periodos de carga.", campo_critico)
            if p.get("outliers_iqr", 0) > 0 and not (name in faostat_datasets and col == "Valor"):
                _add(name, col, f"{p['outliers_iqr']} valores atípicos (± 1.5×RIC) en '{col}'.",
                     p["outliers_iqr"], total, "Exactitud",
                     f"app.quality.profile_columns('{name}')['{col}'].outliers_iqr",
                     "Variabilidad real del fenómeno (municipios/productos de gran escala) o error de "
                     "captura puntual — requiere revisión caso a caso, no se elimina automáticamente.",
                     campo_critico)

    if "eva_basicos" in all_rows:
        rows = all_rows["eva_basicos"]
        n_incons, n_verif = _consistencia_area_vs_sembrada(rows)
        if n_verif:
            _add("eva_basicos", "AreaCosechada / AreaSembrada",
                 f"{n_incons} registros reportan área cosechada mayor que el área sembrada en el mismo semestre.",
                 n_incons, n_verif, "Consistencia",
                 "app.quality._consistencia_area_vs_sembrada sobre eva_basicos.json",
                 "Posible re-siembra dentro del mismo semestre o error de reporte municipal "
                 "(autorreporte sin validación cruzada).", campo_critico=True)

    for name in faostat_datasets & all_rows.keys():
        rows = all_rows[name]
        n_grupos_multi, n_filas_afectadas = _hallazgo_duplicados_por_unidad(rows, DATASET_SCHEMA[name]["key_fields"])
        if n_filas_afectadas:
            _add(name, "Producto / Unidad",
                 f"{n_grupos_multi} combinaciones (Área,Producto,Elemento,Año) reportan el mismo indicador en más "
                 f"de una Unidad (p. ej. huevos en 'toneladas' y en '1000 No.'), afectando {n_filas_afectadas} filas; "
                 "la llave de unicidad original de R1 (sin 'Unidad') las contaba como duplicados.",
                 n_filas_afectadas, len(rows), "Unicidad",
                 f"app.quality._hallazgo_duplicados_por_unidad sobre {name}.json",
                 "Definición de llave de unicidad incompleta: no se incluyó 'Unidad' al validar duplicados en R1.",
                 campo_critico=True)

        n_out, n_eval = _outliers_grupo_iqr(rows, ("Producto", "Elemento"), "Valor")
        if n_out:
            _add(name, "Valor (por Producto, Elemento)",
                 f"{n_out} de {n_eval} valores evaluables son atípicos (± 1.5×RIC) dentro de su propia serie "
                 "(Producto, Elemento) — no se calculó globalmente para no mezclar magnitudes distintas "
                 "(toneladas, cabezas, kg/ha, %, etc.).",
                 n_out, n_eval, "Exactitud",
                 f"app.quality._outliers_grupo_iqr sobre {name}.json, agrupado por (Producto, Elemento)",
                 "Variabilidad real de la serie (años atípicos por clima o mercado) o error de captura "
                 "puntual — requiere revisión caso a caso.", campo_critico=True)

    if "fs" in all_rows:
        rows = all_rows["fs"]
        n_ok, n_verif = _exactitud_ci_bounds(rows)
        n_problema = n_verif - n_ok
        if n_verif and n_problema > 0:
            _add("fs", "Valor / Confidence interval",
                 f"{n_problema} de {n_verif} grupos (Producto, Año) con intervalo de confianza reportado no "
                 "cumplen Lower bound ≤ Valor ≤ Upper bound.",
                 n_problema, n_verif, "Exactitud",
                 "app.quality._exactitud_ci_bounds sobre fs.json",
                 "Redondeo o desfase entre la estimación puntual y el intervalo publicado por FAO/SOFI.",
                 campo_critico=True)

    return inventario
