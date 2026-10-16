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
