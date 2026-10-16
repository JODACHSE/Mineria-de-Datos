"""Contextos para las páginas de la Etapa 4 (análisis multidimensional).

Cada función `build_r4_dim_*_context` carga los datos ya tratados de R2,
computa las agregaciones necesarias y devuelve un dict listo para la
plantilla. Los datos brutos nunca llegan al template: solo cifras y
estructuras para Chart.js.
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path

from app.quality import _rows_as_dicts, _to_float
from app.services import datasets as ds

_NUMERIC_FIELDS = ("AreaSembrada", "AreaCosechada", "Produccion", "Rendimiento")
_CULTIVOS_ORDER = ["Maíz", "Arroz", "Papa", "Plátano", "Yuca", "Frijol"]

# Mapeo departamento → región geográfica de Colombia
_REGION_MAP: dict[str, str] = {
    "Antioquia": "Andina",
    "Boyacá": "Andina",
    "Caldas": "Andina",
    "Cundinamarca": "Andina",
    "Huila": "Andina",
    "Nariño": "Andina",
    "Norte de Santander": "Andina",
    "Quindío": "Andina",
    "Risaralda": "Andina",
    "Santander": "Andina",
    "Tolima": "Andina",
    "Atlántico": "Caribe",
    "Bolívar": "Caribe",
    "Cesar": "Caribe",
    "Córdoba": "Caribe",
    "La Guajira": "Caribe",
    "Magdalena": "Caribe",
    "Sucre": "Caribe",
    "Archipiélago de San Andrés, Providencia y Santa Catalina": "Caribe",
    "Arauca": "Orinoquía",
    "Casanare": "Orinoquía",
    "Meta": "Orinoquía",
    "Vichada": "Orinoquía",
    "Amazonas": "Amazonía",
    "Caquetá": "Amazonía",
    "Guainía": "Amazonía",
    "Guaviare": "Amazonía",
    "Putumayo": "Amazonía",
    "Vaupés": "Amazonía",
    "Cauca": "Pacífica",
    "Chocó": "Pacífica",
    "Valle del Cauca": "Pacífica",
}
_REGION_ORDER = ["Andina", "Caribe", "Orinoquía", "Pacífica", "Amazonía"]


def _pct(part: int, total: int) -> float:
    return round(part / total * 100, 1) if total else 0.0


def build_r4_dim_poblacional_context(r2_dir: Path) -> dict:
    """Agrega el dataset EVA tratado para la Dimensión Poblacional."""
    raw = ds.load_treated("eva_basicos", r2_dir)
    rows = _rows_as_dicts(raw)
    total = len(rows)

    cultivo_counts: Counter = Counter()
    ciclo_counts: Counter = Counter()
    estado_counts: Counter = Counter()
    completos = 0
    cultivo_completos: Counter = Counter()
    cultivo_faltantes: Counter = Counter()

    for r in rows:
        cultivo = r.get("Cultivo", "Desconocido")
        ciclo = r.get("CicloCultivo") or "Sin dato"
        estado = r.get("EstadoFisico") or "Sin dato"

        cultivo_counts[cultivo] += 1
        ciclo_counts[ciclo] += 1
        estado_counts[estado] += 1

        all_present = all(_to_float(r.get(f)) is not None for f in _NUMERIC_FIELDS)
        if all_present:
            completos += 1
            cultivo_completos[cultivo] += 1
        else:
            cultivo_faltantes[cultivo] += 1

    # ---- indicadores ------------------------------------------------
    top_cultivo = max(cultivo_counts, key=cultivo_counts.get)
    top_count = cultivo_counts[top_cultivo]
    minoritario = min(cultivo_counts, key=cultivo_counts.get)
    completitud_pct = _pct(completos, total)

    # ---- datos para filtros (client-side) ---------------------------
    # Agregación cruzada Cultivo × CicloCultivo para los filtros JS
    cross: dict[str, Counter] = {}
    for r in rows:
        cultivo = r.get("Cultivo", "Desconocido")
        ciclo = r.get("CicloCultivo") or "Sin dato"
        cross.setdefault(cultivo, Counter())[ciclo] += 1

    # ---- chart data -------------------------------------------------
    cultivos_ordered = [c for c in _CULTIVOS_ORDER if c in cultivo_counts]
    cultivos_ordered += [c for c in cultivo_counts if c not in _CULTIVOS_ORDER]

    ciclos_ordered = sorted(ciclo_counts.keys(), key=lambda k: -ciclo_counts[k])
    estados_ordered = sorted(estado_counts.keys(), key=lambda k: -estado_counts[k])

    cultivos_chart = {
        "labels": cultivos_ordered,
        "values": [cultivo_counts[c] for c in cultivos_ordered],
        "pcts": [_pct(cultivo_counts[c], total) for c in cultivos_ordered],
    }
    ciclo_chart = {
        "labels": ciclos_ordered,
        "values": [ciclo_counts[c] for c in ciclos_ordered],
        "pcts": [_pct(ciclo_counts[c], total) for c in ciclos_ordered],
    }
    estado_chart = {
        "labels": estados_ordered,
        "values": [estado_counts[e] for e in estados_ordered],
        "pcts": [_pct(estado_counts[e], total) for e in estados_ordered],
    }

    # Cross data for JS filter: {cultivo: {ciclo: count}}
    cross_serializable = {c: dict(cc) for c, cc in cross.items()}

    return {
        # indicadores
        "total_registros": total,
        "top_cultivo": top_cultivo,
        "top_cultivo_pct": _pct(top_count, total),
        "top_cultivo_n": top_count,
        "minoritario_cultivo": minoritario,
        "minoritario_n": cultivo_counts[minoritario],
        "minoritario_pct": _pct(cultivo_counts[minoritario], total),
        "completitud_pct": completitud_pct,
        "completos_n": completos,
        # cultivos table (para la viz de filtros)
        "cultivos_tabla": [
            {
                "cultivo": c,
                "n": cultivo_counts[c],
                "pct": _pct(cultivo_counts[c], total),
                "completos_pct": _pct(cultivo_completos.get(c, 0), cultivo_counts[c]),
            }
            for c in cultivos_ordered
        ],
        # chart data
        "cultivos_chart": cultivos_chart,
        "ciclo_chart": ciclo_chart,
        "estado_chart": estado_chart,
        "cross_data": cross_serializable,
        # filter options
        "filter_cultivos": cultivos_ordered,
        "filter_ciclos": ciclos_ordered,
    }


def build_r4_dim_territorial_context(r2_dir: Path) -> dict:
    """Agrega el dataset EVA tratado para la Dimensión Territorial."""
    raw = ds.load_treated("eva_basicos", r2_dir)
    rows = _rows_as_dicts(raw)
    total = len(rows)

    dept_counts: Counter = Counter()
    dept_munis: dict[str, set] = {}
    dept_cultivos: dict[str, Counter] = {}

    for r in rows:
        dept = r.get("Departamento") or "Desconocido"
        muni = r.get("CodigoMunicipioDane") or ""
        cultivo = r.get("Cultivo") or "Desconocido"

        dept_counts[dept] += 1
        dept_munis.setdefault(dept, set()).add(muni)
        dept_cultivos.setdefault(dept, Counter())[cultivo] += 1

    total_depts = len(dept_counts)
    total_munis = sum(len(v) for v in dept_munis.values())

    # ---- indicadores ------------------------------------------------
    sorted_depts = sorted(dept_counts.items(), key=lambda x: -x[1])
    top_dept, top_dept_n = sorted_depts[0]
    top_dept_pct = _pct(top_dept_n, total)

    bottom_dept, bottom_dept_n = sorted_depts[-1]
    bottom_dept_pct = _pct(bottom_dept_n, total)

    top5_n = sum(n for _, n in sorted_depts[:5])
    top5_pct = _pct(top5_n, total)

    # ---- region aggregation ----------------------------------------
    region_counts: Counter = Counter()
    region_depts: dict[str, list] = {}
    for dept, n in dept_counts.items():
        region = _REGION_MAP.get(dept, "Otra")
        region_counts[region] += n
        region_depts.setdefault(region, []).append(dept)

    # ---- chart data -------------------------------------------------
    # VIZ-1: top 15 departments (horizontal bar)
    top15 = sorted_depts[:15]
    top15_labels = [d for d, _ in top15]
    top15_values = [n for _, n in top15]
    top15_pcts = [_pct(n, total) for n in top15_values]
    top15_munis = [len(dept_munis.get(d, set())) for d in top15_labels]

    dept_chart = {
        "labels": top15_labels,
        "values": top15_values,
        "pcts": top15_pcts,
        "munis": top15_munis,
    }

    # VIZ-2: by region (doughnut)
    region_ordered = [r for r in _REGION_ORDER if r in region_counts]
    region_ordered += [r for r in region_counts if r not in _REGION_ORDER]
    region_chart = {
        "labels": region_ordered,
        "values": [region_counts[r] for r in region_ordered],
        "pcts": [_pct(region_counts[r], total) for r in region_ordered],
        "dept_counts": [len(region_depts.get(r, [])) for r in region_ordered],
    }

    # VIZ-3: registros por municipio único (density) — top 15 depts
    density_labels = top15_labels
    density_values = [
        round(top15_values[i] / top15_munis[i], 1) if top15_munis[i] else 0
        for i in range(len(top15_labels))
    ]
    density_chart = {
        "labels": density_labels,
        "values": density_values,
        "munis": top15_munis,
        "registros": top15_values,
    }

    # ---- cross data para filtro JS (dept → region, n, munis) --------
    cross_data = {
        d: {
            "n": dept_counts[d],
            "pct": _pct(dept_counts[d], total),
            "munis": len(dept_munis[d]),
            "region": _REGION_MAP.get(d, "Otra"),
            "top_cultivo": max(dept_cultivos[d], key=dept_cultivos[d].get) if dept_cultivos.get(d) else "—",
        }
        for d in dept_counts
    }

    # tabla completa de departamentos ordenada por registros
    depts_tabla = [
        {
            "dept": d,
            "region": _REGION_MAP.get(d, "Otra"),
            "n": n,
            "pct": _pct(n, total),
            "munis": len(dept_munis.get(d, set())),
            "density": round(n / len(dept_munis[d]), 1) if dept_munis.get(d) else 0,
            "top_cultivo": max(dept_cultivos[d], key=dept_cultivos[d].get) if dept_cultivos.get(d) else "—",
        }
        for d, n in sorted_depts
    ]

    return {
        # indicadores
        "total_registros": total,
        "total_depts": total_depts,
        "total_munis": total_munis,
        "top_dept": top_dept,
        "top_dept_n": top_dept_n,
        "top_dept_pct": top_dept_pct,
        "top_dept_munis": len(dept_munis.get(top_dept, set())),
        "bottom_dept": bottom_dept,
        "bottom_dept_n": bottom_dept_n,
        "bottom_dept_pct": bottom_dept_pct,
        "top5_pct": top5_pct,
        "top5_depts": [d for d, _ in sorted_depts[:5]],
        # chart data
        "dept_chart": dept_chart,
        "region_chart": region_chart,
        "density_chart": density_chart,
        # filter options
        "filter_depts": [d for d, _ in sorted_depts],
        "filter_regiones": region_ordered,
        # table
        "depts_tabla": depts_tabla,
        # cross for JS filter
        "cross_data": cross_data,
    }


def build_r4_dim_temporal_context(r2_dir: Path) -> dict:
    """Agrega el dataset EVA tratado para la Dimensión Temporal."""
    raw = ds.load_treated("eva_basicos", r2_dir)
    rows = _rows_as_dicts(raw)
    total = len(rows)

    year_counts: Counter = Counter()
    semestre_counts: Counter = Counter()
    year_semestre: dict[int, Counter] = {}
    cultivo_year: dict[str, Counter] = {}

    for r in rows:
        year = int(r["Anio"])
        periodo = r.get("Periodo") or ""
        if periodo.endswith("A"):
            sem = "Primer semestre"
        elif periodo.endswith("B"):
            sem = "Segundo semestre"
        else:
            sem = "Anual"

        year_counts[year] += 1
        semestre_counts[sem] += 1
        year_semestre.setdefault(year, Counter())[sem] += 1

        cultivo = r.get("Cultivo") or "Desconocido"
        cultivo_year.setdefault(cultivo, Counter())[year] += 1

    years_sorted = sorted(year_counts.keys())
    first_year, last_year = years_sorted[0], years_sorted[-1]

    # ---- indicadores ------------------------------------------------
    top_year = max(year_counts, key=year_counts.get)
    top_year_n = year_counts[top_year]

    yoy: dict[int, float] = {}
    for i in range(1, len(years_sorted)):
        prev = year_counts[years_sorted[i - 1]]
        curr = year_counts[years_sorted[i]]
        yoy[years_sorted[i]] = round((curr - prev) / prev * 100, 1) if prev else 0.0

    growth_total = round((year_counts[last_year] - year_counts[first_year])
                         / year_counts[first_year] * 100, 1)
    max_jump_year = max(yoy, key=yoy.get)
    max_jump_pct = yoy[max_jump_year]

    # ---- chart data -------------------------------------------------
    SEM_LABELS = ["Primer semestre", "Segundo semestre", "Anual"]

    # VIZ-1: tendencia anual (bar + line overlay handled in JS)
    trend_chart = {
        "labels": [str(y) for y in years_sorted],
        "values": [year_counts[y] for y in years_sorted],
        "pcts":   [_pct(year_counts[y], total) for y in years_sorted],
        "yoy":    [yoy.get(y, 0) for y in years_sorted],
    }

    # VIZ-2: apilado año × semestre
    stacked_chart = {
        "labels": [str(y) for y in years_sorted],
        "datasets": [
            {
                "label": sem,
                "values": [year_semestre.get(y, Counter()).get(sem, 0) for y in years_sorted],
            }
            for sem in SEM_LABELS
        ],
    }

    # VIZ-3: líneas por cultivo a lo largo de los años
    cultivos_ordered = [c for c in _CULTIVOS_ORDER if c in cultivo_year]
    cultivo_year_chart = {
        "labels": [str(y) for y in years_sorted],
        "datasets": [
            {
                "label": c,
                "values": [cultivo_year[c].get(y, 0) for y in years_sorted],
            }
            for c in cultivos_ordered
        ],
    }

    # ---- tabla y cross data para filtros ----------------------------
    years_tabla = [
        {
            "year": y,
            "n": year_counts[y],
            "pct": _pct(year_counts[y], total),
            "sem_a": year_semestre.get(y, Counter()).get("Primer semestre", 0),
            "sem_b": year_semestre.get(y, Counter()).get("Segundo semestre", 0),
            "anual": year_semestre.get(y, Counter()).get("Anual", 0),
            "yoy": yoy.get(y),
        }
        for y in years_sorted
    ]
    cross_data = {
        str(y): {
            "n":     year_counts[y],
            "pct":   _pct(year_counts[y], total),
            "A":     year_semestre.get(y, Counter()).get("Primer semestre", 0),
            "B":     year_semestre.get(y, Counter()).get("Segundo semestre", 0),
            "anual": year_semestre.get(y, Counter()).get("Anual", 0),
            "yoy":   yoy.get(y),
        }
        for y in years_sorted
    }

    return {
        # indicadores
        "total_registros": total,
        "total_years": len(years_sorted),
        "first_year": first_year,
        "last_year": last_year,
        "top_year": top_year,
        "top_year_n": top_year_n,
        "top_year_pct": _pct(top_year_n, total),
        "growth_total_pct": growth_total,
        "max_jump_year": max_jump_year,
        "max_jump_pct": max_jump_pct,
        # chart data
        "trend_chart": trend_chart,
        "stacked_chart": stacked_chart,
        "cultivo_year_chart": cultivo_year_chart,
        # filter options
        "filter_years": [str(y) for y in years_sorted],
        "filter_semestres": SEM_LABELS,
        # table + cross
        "years_tabla": years_tabla,
        "cross_data": cross_data,
        # semestre summary for indicators
        "semestre_counts": {k: semestre_counts[k] for k in SEM_LABELS if k in semestre_counts},
    }


def build_r4_dim_relacional_context(r2_dir: Path) -> dict:
    """Agrega el dataset EVA tratado para la Dimensión Relacional y Multivariada."""
    raw = ds.load_treated("eva_basicos", r2_dir)
    rows = _rows_as_dicts(raw)
    total = len(rows)

    SEM_LABELS = ["Primer semestre", "Segundo semestre", "Anual"]

    cultivo_region: dict[str, Counter] = {}
    cultivo_semestre: dict[str, Counter] = {}
    region_year: dict[str, Counter] = {}
    year_set: set[int] = set()

    for r in rows:
        cultivo = r.get("Cultivo") or "Desconocido"
        dept = r.get("Departamento") or ""
        region = _REGION_MAP.get(dept, "Otra")
        year = int(r["Anio"])
        periodo = r.get("Periodo") or ""
        if periodo.endswith("A"):
            sem = "Primer semestre"
        elif periodo.endswith("B"):
            sem = "Segundo semestre"
        else:
            sem = "Anual"

        cultivo_region.setdefault(cultivo, Counter())[region] += 1
        cultivo_semestre.setdefault(cultivo, Counter())[sem] += 1
        region_year.setdefault(region, Counter())[year] += 1
        year_set.add(year)

    cultivos_ordered = [c for c in _CULTIVOS_ORDER if c in cultivo_region]
    years_sorted = sorted(year_set)

    # ---- indicadores ------------------------------------------------
    # IND-1: combinación cultivo×región más frecuente
    top_combo_cultivo, top_combo_region, top_combo_n = max(
        ((c, r, cultivo_region[c][r])
         for c in cultivo_region for r in cultivo_region[c]
         if cultivo_region[c][r] > 0),
        key=lambda x: x[2],
    )
    top_combo_pct = _pct(top_combo_n, total)

    # IND-2: combinaciones activas sobre el máximo posible (6 cultivos × 5 regiones)
    active_combos = sum(
        1 for c in cultivos_ordered for r in _REGION_ORDER
        if cultivo_region.get(c, Counter()).get(r, 0) > 0
    )
    max_combos = len(cultivos_ordered) * len(_REGION_ORDER)

    # IND-3: cultivo más transversal (presente en más regiones)
    transversal_cultivo = max(
        cultivos_ordered,
        key=lambda c: sum(1 for r in _REGION_ORDER if cultivo_region.get(c, Counter()).get(r, 0) > 0),
    )
    transversal_regions = sum(
        1 for r in _REGION_ORDER if cultivo_region.get(transversal_cultivo, Counter()).get(r, 0) > 0
    )

    # ---- chart data -------------------------------------------------
    # VIZ-1: barras agrupadas — región × cultivo (territorial × poblacional)
    region_cultivo_chart = {
        "labels": _REGION_ORDER,
        "datasets": [
            {
                "label": c,
                "values": [cultivo_region.get(c, Counter()).get(r, 0) for r in _REGION_ORDER],
            }
            for c in cultivos_ordered
        ],
    }

    # VIZ-2: barras apiladas — cultivo × semestre (poblacional × temporal)
    cultivo_semestre_chart = {
        "labels": cultivos_ordered,
        "datasets": [
            {
                "label": sem,
                "values": [cultivo_semestre.get(c, Counter()).get(sem, 0) for c in cultivos_ordered],
            }
            for sem in SEM_LABELS
        ],
    }

    # VIZ-3: líneas — año × región (temporal × territorial)
    region_year_chart = {
        "labels": [str(y) for y in years_sorted],
        "datasets": [
            {
                "label": r,
                "values": [region_year.get(r, Counter()).get(y, 0) for y in years_sorted],
            }
            for r in _REGION_ORDER
        ],
    }

    # ---- tabla y cross data -----------------------------------------
    tabla_rows = [
        {
            "cultivo": c,
            "region": r,
            "n": cultivo_region.get(c, Counter()).get(r, 0),
            "pct": _pct(cultivo_region.get(c, Counter()).get(r, 0), total),
        }
        for c in cultivos_ordered
        for r in _REGION_ORDER
        if cultivo_region.get(c, Counter()).get(r, 0) > 0
    ]

    # cross_data[cultivo][region] = n  (for JS filter summaries)
    cross_data = {
        c: {r: cultivo_region.get(c, Counter()).get(r, 0) for r in _REGION_ORDER}
        for c in cultivos_ordered
    }

    return {
        # indicadores
        "total_registros": total,
        "top_combo_cultivo": top_combo_cultivo,
        "top_combo_region": top_combo_region,
        "top_combo_n": top_combo_n,
        "top_combo_pct": top_combo_pct,
        "active_combos": active_combos,
        "max_combos": max_combos,
        "transversal_cultivo": transversal_cultivo,
        "transversal_regions": transversal_regions,
        # chart data
        "region_cultivo_chart": region_cultivo_chart,
        "cultivo_semestre_chart": cultivo_semestre_chart,
        "region_year_chart": region_year_chart,
        # filter options
        "filter_cultivos": cultivos_ordered,
        "filter_regiones": _REGION_ORDER,
        # table + cross
        "tabla_rows": tabla_rows,
        "cross_data": cross_data,
    }
