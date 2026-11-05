"""R5 · Motor de consultas OLAP sobre el modelo estrella (SQLite).

Toda consulta se arma con niveles y medidas de una lista blanca (nada del
cliente llega como SQL) y se resuelve con GROUP BY sobre la tabla de hechos.
Los subtotales y el total general se calculan con su propia consulta, de modo
que las medidas no aditivas (rendimiento, tasa de cosecha, municipios únicos)
se recalculan en cada nivel en lugar de sumarse.

Operaciones:
  drill-down / roll-up → cambiar `rows`/`cols` a un nivel hijo/padre de la jerarquía
  slice                → un filtro de un valor sobre una dimensión
  dice                 → filtros sobre dos o más dimensiones
  pivot                → intercambiar `rows` y `cols`
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

# nivel → (expresión SQL, etiqueta, dimensión)
LEVELS: dict[str, tuple[str, str, str]] = {
    "region": ("t.region", "Región", "territorio"),
    "departamento": ("t.departamento", "Departamento", "territorio"),
    "municipio": ("t.municipio || ' (' || t.departamento || ')'", "Municipio", "territorio"),
    "trienio": ("tm.trienio", "Trienio", "tiempo"),
    "anio": ("tm.anio", "Año", "tiempo"),
    "periodo": ("tm.periodo_codigo", "Periodo", "tiempo"),
    "semestre": ("tm.periodo", "Semestre", "tiempo"),
    "grupo": ("c.grupo", "Grupo", "cultivo"),
    "cultivo": ("c.cultivo", "Cultivo", "cultivo"),
    "desagregacion": ("c.desagregacion", "Desagregación", "cultivo"),
    "criterio": ("s.criterio", "Criterio", "sistema"),
    "sistema": ("s.sistema", "Sistema productivo", "sistema"),
    # Atributo degenerado de la tabla de hechos (bandera de calidad de R2).
    "coherencia": ("CASE f.area_incoherente WHEN 1 THEN 'Cosechada > sembrada' ELSE 'Coherente' END",
                   "Coherencia del área", "calidad"),
}

# Jerarquías (de lo general a lo detallado). `semestre` no es un nivel de la
# jerarquía temporal: es un atributo para comparar A vs B entre años.
HIERARCHIES: dict[str, list[str]] = {
    "territorio": ["region", "departamento", "municipio"],
    "tiempo": ["trienio", "anio", "periodo"],
    "cultivo": ["grupo", "cultivo", "desagregacion"],
    "sistema": ["criterio", "sistema"],
}

DIMENSIONS = {
    "territorio": "Territorio",
    "tiempo": "Tiempo",
    "cultivo": "Cultivo",
    "sistema": "Sistema productivo",
}

# medida → (expresión SQL, etiqueta, unidad, agregación, decimales)
MEASURES: dict[str, tuple[str, str, str, str, int]] = {
    "produccion": ("SUM(f.produccion_t)", "Producción", "t", "SUM", 0),
    "area_sembrada": ("SUM(f.area_sembrada_ha)", "Área sembrada", "ha", "SUM", 0),
    "area_cosechada": ("SUM(f.area_cosechada_ha)", "Área cosechada", "ha", "SUM", 0),
    "area_no_cosechada": ("SUM(f.area_sembrada_ha) - SUM(f.area_cosechada_ha)",
                          "Área no cosechada", "ha", "SUM(sembrada) − SUM(cosechada)", 0),
    "rendimiento": ("SUM(f.produccion_t) / NULLIF(SUM(f.area_cosechada_ha), 0)",
                    "Rendimiento ponderado", "t/ha", "SUM(producción) / SUM(área cosechada)", 2),
    "tasa_cosecha": ("100.0 * SUM(f.area_cosechada_ha) / NULLIF(SUM(f.area_sembrada_ha), 0)",
                     "Tasa de cosecha", "%", "SUM(cosechada) / SUM(sembrada) × 100", 1),
    "registros": ("COUNT(*)", "Registros", "registros", "COUNT", 0),
    "municipios": ("COUNT(DISTINCT f.territorio_key)", "Municipios únicos", "municipios",
                   "COUNT DISTINCT", 0),
}
ADDITIVE = {"produccion", "area_sembrada", "area_cosechada", "area_no_cosechada", "registros"}

FROM = """
FROM fact_produccion_agricola f
JOIN dim_territorio t          ON t.territorio_key = f.territorio_key
JOIN dim_tiempo tm             ON tm.tiempo_key    = f.tiempo_key
JOIN dim_cultivo c             ON c.cultivo_key    = f.cultivo_key
JOIN dim_sistema_productivo s  ON s.sistema_key    = f.sistema_key
"""

MAX_ROWS = 40


class OlapError(ValueError):
    pass


def _where(filters: dict[str, list]) -> tuple[str, list]:
    clauses, params = [], []
    for level, values in (filters or {}).items():
        if level not in LEVELS:
            raise OlapError(f"Nivel de filtro desconocido: {level}")
        values = [v for v in values if v not in (None, "")]
        if not values:
            continue
        clauses.append(f"{LEVELS[level][0]} IN ({','.join('?' * len(values))})")
        params.extend(values)
    return (" WHERE " + " AND ".join(clauses)) if clauses else "", params


def _scalar(con, measure: str, where: str, params: list):
    return con.execute(f"SELECT {MEASURES[measure][0]} {FROM}{where}", params).fetchone()[0]


def _round(v, nd):
    return None if v is None else round(v, nd)


def _sort_key(level: str, totals: dict):
    # Los niveles temporales se ordenan cronológicamente; el resto por total desc.
    if LEVELS[level][2] == "tiempo":
        return lambda k: str(k)
    return lambda k: -(totals.get(k) or 0)


def query(con: sqlite3.Connection, rows: str, measure: str, cols: str | None = None,
          filters: dict[str, list] | None = None, limit: int = MAX_ROWS) -> dict:
    """Matriz `rows × cols` de `measure` bajo `filters`, con subtotales recalculados."""
    if rows not in LEVELS or (cols and cols not in LEVELS):
        raise OlapError("Nivel desconocido")
    if measure not in MEASURES:
        raise OlapError(f"Medida desconocida: {measure}")
    if cols and LEVELS[cols][2] == LEVELS[rows][2]:
        raise OlapError("Filas y columnas deben pertenecer a dimensiones distintas")

    expr, _, _, _, nd = MEASURES[measure]
    where, params = _where(filters or {})
    rexpr = LEVELS[rows][0]

    row_totals = {r: v for r, v in con.execute(
        f"SELECT {rexpr} AS r, {expr} {FROM}{where} GROUP BY r", params)}
    grand = _scalar(con, measure, where, params)

    row_keys = sorted(row_totals, key=_sort_key(rows, row_totals))
    truncated = len(row_keys) > limit
    row_keys = row_keys[:limit]

    sql_cells = f"SELECT {rexpr} AS r, {expr} AS v {FROM}{where} GROUP BY r"
    col_keys, cells, col_totals = [], {}, {}
    if cols:
        cexpr = LEVELS[cols][0]
        sql_cells = f"SELECT {rexpr} AS r, {cexpr} AS c, {expr} AS v {FROM}{where} GROUP BY r, c"
        for r, c, v in con.execute(sql_cells, params):
            cells.setdefault(r, {})[c] = v
        col_totals = {c: v for c, v in con.execute(
            f"SELECT {cexpr} AS c, {expr} {FROM}{where} GROUP BY c", params)}
        col_keys = sorted(col_totals, key=_sort_key(cols, col_totals))

    # Participación: sobre el total de la selección (denominador explícito).
    share = None
    if measure in ADDITIVE and grand:
        share = {str(r): round(100 * (row_totals[r] or 0) / grand, 1) for r in row_keys}

    return {
        "rows_level": rows, "cols_level": cols, "measure": measure,
        "rows_label": LEVELS[rows][1], "cols_label": LEVELS[cols][1] if cols else None,
        "measure_label": MEASURES[measure][1], "unit": MEASURES[measure][2],
        "aggregation": MEASURES[measure][3], "additive": measure in ADDITIVE,
        "rows": [str(r) for r in row_keys],
        "cols": [str(c) for c in col_keys],
        "cells": [[_round(cells.get(r, {}).get(c), nd) for c in col_keys] for r in row_keys],
        "row_totals": [_round(row_totals[r], nd) for r in row_keys],
        "col_totals": [_round(col_totals[c], nd) for c in col_keys],
        "grand_total": _round(grand, nd),
        "share_pct": [share[str(r)] for r in row_keys] if share else None,
        "share_denominator": f"{MEASURES[measure][1]} total de la selección" if share else None,
        "truncated": truncated, "total_members": len(row_totals),
        "filters": {k: v for k, v in (filters or {}).items() if v},
        "sql": sql_cells.strip(), "params": params,
    }


def kpis(con: sqlite3.Connection, measures: list[str], filters: dict | None = None) -> dict:
    """Medidas escalares (una consulta por medida) para las tarjetas de indicadores."""
    where, params = _where(filters or {})
    return {m: _round(_scalar(con, m, where, params), MEASURES[m][4]) for m in measures}


def extreme_cell(con: sqlite3.Connection, rows: str, cols: str, measure: str,
                 filters: dict | None = None, min_area_sembrada: float = 1000, lowest: bool = True):
    """Combinación rows × cols con el valor mínimo (o máximo) de la medida. Solo considera
    celdas con al menos `min_area_sembrada` ha para no destacar ruido de áreas diminutas."""
    where, params = _where(filters or {})
    sql = (f"SELECT {LEVELS[rows][0]} AS r, {LEVELS[cols][0]} AS c, {MEASURES[measure][0]} AS v "
           f"{FROM}{where} GROUP BY r, c HAVING SUM(f.area_sembrada_ha) >= ? AND v IS NOT NULL "
           f"ORDER BY v {'ASC' if lowest else 'DESC'} LIMIT 1")
    row = con.execute(sql, [*params, min_area_sembrada]).fetchone()
    return (str(row[0]), str(row[1]), _round(row[2], MEASURES[measure][4])) if row else None


def members(con: sqlite3.Connection, level: str, filters: dict | None = None) -> list[str]:
    if level not in LEVELS:
        raise OlapError("Nivel desconocido")
    where, params = _where(filters or {})
    expr = LEVELS[level][0]
    vals = [r[0] for r in con.execute(f"SELECT DISTINCT {expr} {FROM}{where} ORDER BY 1", params)]
    return [str(v) for v in vals if v != "Desconocido"]


def model_metadata() -> dict:
    return {
        "levels": {k: {"label": v[1], "dimension": v[2]} for k, v in LEVELS.items()},
        "hierarchies": HIERARCHIES,
        "dimensions": DIMENSIONS,
        "measures": {k: {"label": v[1], "unit": v[2], "aggregation": v[3], "decimals": v[4],
                         "additive": k in ADDITIVE} for k, v in MEASURES.items()},
    }


# ---------------------------------------------------------------- validaciones
def _source_rows(r2_json: Path) -> list[dict]:
    with open(r2_json, encoding="utf-8") as fh:
        data = json.load(fh)
    return [dict(zip(data["columns"], r)) for r in data["rows"]]


def validations(con: sqlite3.Connection, r2_json: Path) -> list[dict]:
    """Comprobaciones de integridad del modelo y comparaciones con el dato tratado."""
    src = _source_rows(r2_json)
    one = lambda sql: con.execute(sql).fetchone()[0]  # noqa: E731
    out = []

    def add(grupo, nombre, modelo, origen, nota, ok=None):
        out.append({"grupo": grupo, "nombre": nombre, "modelo": modelo, "origen": origen,
                    "ok": (modelo == origen) if ok is None else ok, "nota": nota})

    # 1. Unicidad de claves de las dimensiones
    for tabla, pk, nat in [("dim_territorio", "territorio_key", "cod_municipio"),
                           ("dim_tiempo", "tiempo_key", "periodo_codigo"),
                           ("dim_cultivo", "cultivo_key", "desagregacion"),
                           ("dim_sistema_productivo", "sistema_key", "sistema")]:
        n = one(f"SELECT COUNT(*) FROM {tabla}")
        add("Unicidad", f"{tabla}: filas = claves únicas ({pk}, {nat})",
            n, one(f"SELECT COUNT(DISTINCT {pk}) FROM {tabla}"),
            "PRIMARY KEY + UNIQUE sobre la clave natural.",
            ok=n == one(f"SELECT COUNT(DISTINCT {nat}) FROM {tabla}") == one(f"SELECT COUNT(DISTINCT {pk}) FROM {tabla}"))

    # 2. Integridad referencial
    for tabla, fk in [("dim_territorio", "territorio_key"), ("dim_tiempo", "tiempo_key"),
                      ("dim_cultivo", "cultivo_key"), ("dim_sistema_productivo", "sistema_key")]:
        huerfanos = one(f"SELECT COUNT(*) FROM fact_produccion_agricola f LEFT JOIN {tabla} d "
                        f"ON d.{fk} = f.{fk} WHERE d.{fk} IS NULL")
        add("Integridad referencial", f"Hechos sin correspondencia en {tabla}", huerfanos, 0,
            "LEFT JOIN de la FK contra la dimensión.")

    # 3. Duplicados en la granularidad
    dup = one("SELECT COUNT(*) FROM (SELECT 1 FROM fact_produccion_agricola "
              "GROUP BY territorio_key, cultivo_key, tiempo_key HAVING COUNT(*) > 1)")
    add("Granularidad", "Combinaciones municipio × desagregación × periodo repetidas", dup, 0,
        "Además lo impide la restricción UNIQUE de la tabla de hechos.")
    joined = one(f"SELECT COUNT(*) {FROM}")
    add("Granularidad", "Filas tras unir hechos con las 4 dimensiones", joined, len(src),
        "Si una relación multiplicara filas, el conteo tras el JOIN sería mayor.")

    # 4. Valores faltantes / desconocidos
    desconocidos = one("SELECT COUNT(*) FROM fact_produccion_agricola WHERE territorio_key = 0 "
                       "OR cultivo_key = 0 OR sistema_key = 0")
    add("Faltantes y desconocidos", "Hechos asignados al miembro 'Desconocido' (clave 0)",
        desconocidos, 0, "Toda fila de origen encontró su municipio, cultivo y sistema.")
    sin_region = one("SELECT COUNT(*) FROM dim_territorio WHERE region = 'Desconocido' AND territorio_key <> 0")
    add("Faltantes y desconocidos", "Municipios sin región asignada", sin_region, 0,
        "Los 32 departamentos están en el mapeo departamento → región.")
    medidas_src = ("AreaSembrada", "AreaCosechada", "Produccion")
    add("Faltantes y desconocidos", "Hechos con alguna medida faltante (NULL)",
        one("SELECT COUNT(*) FROM fact_produccion_agricola WHERE area_sembrada_ha IS NULL "
            "OR area_cosechada_ha IS NULL OR produccion_t IS NULL"),
        sum(1 for r in src if any(r.get(c) in (None, "") for c in medidas_src)),
        "Un faltante sería ausencia de dato; el origen tratado no tiene ninguno en las medidas.")
    add("Faltantes y desconocidos", "Hechos con área cosechada = 0 (respuesta negativa reportada, no faltante)",
        one("SELECT COUNT(*) FROM fact_produccion_agricola WHERE area_cosechada_ha = 0"),
        sum(1 for r in src if float(r["AreaCosechada"]) == 0),
        "EVA reporta que no hubo cosecha (pérdida total o cultivo en crecimiento): se conserva como 0. Suma en "
        "área sembrada y área no cosechada, baja la tasa de cosecha y no entra en el rendimiento porque su "
        "denominador es el área cosechada.")
    incoh = sum(1 for r in src if r.get("_flag_area_incoherente"))
    add("Faltantes y desconocidos", "Hechos con área cosechada > sembrada (se conservan con bandera)",
        one("SELECT SUM(area_incoherente) FROM fact_produccion_agricola"), incoh,
        "No es un faltante: se marcan y pueden excluirse en el análisis.")

    # 5. Coherencia de conteos y agregaciones con el origen
    add("Conteos y agregaciones", "Registros: tabla de hechos vs. EVA tratado",
        one("SELECT COUNT(*) FROM fact_produccion_agricola"), len(src), "Carga completa, sin filtrado.")
    add("Conteos y agregaciones", "Producción total (t)",
        round(one("SELECT SUM(produccion_t) FROM fact_produccion_agricola"), 2),
        round(sum(float(r["Produccion"]) for r in src), 2), "SUM aditiva sobre la granularidad.")
    add("Conteos y agregaciones", "Área sembrada total (ha)",
        round(one("SELECT SUM(area_sembrada_ha) FROM fact_produccion_agricola"), 2),
        round(sum(float(r["AreaSembrada"]) for r in src), 2), "SUM aditiva sobre la granularidad.")
    add("Conteos y agregaciones", "Municipios únicos",
        one("SELECT COUNT(DISTINCT territorio_key) FROM fact_produccion_agricola"),
        len({r["CodigoMunicipioDane"] for r in src}), "COUNT DISTINCT, no suma de conteos por grupo.")
    maiz_mod = round(one(f"SELECT SUM(f.produccion_t) {FROM} WHERE c.cultivo = 'Maíz' AND tm.anio = 2024"), 2)
    maiz_src = round(sum(float(r["Produccion"]) for r in src if r["Cultivo"] == "Maíz" and int(r["Anio"]) == 2024), 2)
    add("Conteos y agregaciones", "Producción de Maíz en 2024 (t) — corte por dos dimensiones",
        maiz_mod, maiz_src, "Mismo corte en el modelo (JOIN) y en el JSON tratado.")

    rend_pond = round(one("SELECT SUM(produccion_t) / SUM(area_cosechada_ha) FROM fact_produccion_agricola"), 2)
    rends = [float(r["Rendimiento"]) for r in src if r.get("Rendimiento") is not None]
    rend_simple = round(sum(rends) / len(rends), 2)
    add("Conteos y agregaciones", "Rendimiento nacional (t/ha): ponderado del modelo vs. promedio simple del origen",
        rend_pond, rend_simple,
        "Diferencia esperada: el promedio simple da el mismo peso a un municipio de 1 ha que a uno de "
        "30.000 ha y además incluye rendimientos reportados por EVA en filas con área cosechada 0. "
        "El modelo usa SUM(producción)/SUM(área cosechada).", ok=True)
    return out
