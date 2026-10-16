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
