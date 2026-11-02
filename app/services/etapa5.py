"""Contextos de la Etapa 5 (R5 · Análisis multidimensional).

Las cifras de indicadores, gráficos, matrices y conocimientos salen de
consultas al modelo estrella (`app/services/olap.py`); nada se lee del JSON
de R2 salvo en las validaciones que comparan el modelo con su origen.
"""
from __future__ import annotations

from contextlib import closing
from pathlib import Path

from app.services import dw, olap
from app.services.olap import HIERARCHIES, LEVELS, MEASURES


def fmt(v, nd: int = 0) -> str:
    """Formato colombiano: 12345.6 → '12.345,6'."""
    if v is None:
        return "—"
    s = f"{v:,.{nd}f}"
    return s.replace(",", "§").replace(".", ",").replace("§", ".")


def _pct(part, total, nd=1):
    return round(100 * part / total, nd) if total else None


def _var(new, old, nd=1):
    return round(100 * (new - old) / old, nd) if old else None


def _signed(v, nd=1, suf=" %"):
    return "—" if v is None else ("+" if v > 0 else "") + fmt(v, nd) + suf


_PLURAL = {"region": "Regiones", "departamento": "Departamentos", "municipio": "Municipios"}


def _level_dim(level):
    return LEVELS[level][2] if level in LEVELS else None


# =========================================================== vistas (preguntas)
VISTAS = [
    {
        "slug": "territorial", "num": 1, "icon": "bi-geo-alt-fill", "color": "success",
        "titulo": "Concentración territorial de la producción",
        "pregunta": "¿En qué regiones, departamentos y municipios se concentra la producción (t) de "
                    "cada cultivo básico, y cómo cambia esa concentración al bajar de región a "
                    "departamento y a municipio?",
        "profundiza": "R4 midió la concentración territorial con el conteo de registros (Andina = 59,3 % "
                      "de los registros; top-5 departamentos = 41,5 %). Aquí la medida pasa a ser la "
                      "producción en toneladas y se cruza con el cultivo: un territorio con pocos "
                      "registros puede concentrar mucho volumen, y la concentración se recalcula en "
                      "cada nivel de la jerarquía territorial.",
        "dimensiones": ["Territorio", "Cultivo", "Tiempo (filtro)"],
        "medidas": ["produccion", "registros", "municipios", "area_cosechada"],
        "jerarquias": ["territorio", "cultivo"],
        "config": {
            "rows": "region", "cols": "cultivo", "measure": "produccion",
            "cols_options": ["cultivo", "grupo", "desagregacion", "trienio", "anio", ""],
            "filters": [{"level": "cultivo", "label": "Cultivo"}, {"level": "anio", "label": "Año"}],
            "chart1": "hbar", "chart2": "share_vs_records",
            "chart1_title": "Medida por miembro del nivel de filas (clic = drill-down)",
            "chart2_title": "Participación en producción vs. participación en registros (%)",
        },
        "interpretacion": [
            "Al pasar de registros a toneladas, el mapa productivo cambia: la Andina sigue primera, pero la "
            "Orinoquía pasa del cuarto lugar en registros al segundo en producción, impulsada por arroz y plátano.",
            "Cada drill-down recalcula la participación sobre la producción de la selección: la concentración "
            "aumenta al bajar de nivel (pocas regiones → pocos departamentos → muy pocos municipios), sobre todo "
            "en papa y arroz.",
            "El pivot Cultivo × Región responde a otra pregunta: no qué produce cada región, sino de qué "
            "territorios depende cada cultivo.",
        ],
        "limitacion": "La producción en toneladas mezcla productos con contenido nutricional y precio muy distintos "
                      "(una tonelada de papa no equivale a una de frijol); la concentración mide volumen físico, no "
                      "aporte calórico ni valor económico.",
        "decision": "Focalizar el monitoreo de abastecimiento en los municipios que reúnen el 50 % de la producción de "
                    "cada cultivo (indicador 3 de la vista) en vez de distribuir el seguimiento por número de municipios.",
    },
    {
        "slug": "temporal", "num": 2, "icon": "bi-calendar3", "color": "info",
        "titulo": "Evolución de la producción frente a la evolución de los registros",
        "pregunta": "¿Cómo cambian la producción (t) y el rendimiento (t/ha) de cada cultivo entre "
                    "periodos equivalentes (trienios 2019–2021 y 2022–2024, años y semestres), y "
                    "coincide ese cambio con el crecimiento de registros que mostró R4?",
        "profundiza": "R4 reportó +28,5 % de registros entre 2019 y 2024 y un salto de +19,5 % en 2021. "
                      "Esta vista separa el número de registros de la producción, compara trienios "
                      "de igual duración y baja de año a semestre para ver cambios que el total anual oculta.",
        "dimensiones": ["Tiempo", "Cultivo", "Territorio (filtro)", "Sistema productivo (columnas opcionales)"],
        "medidas": ["produccion", "rendimiento", "registros", "municipios"],
        "jerarquias": ["tiempo", "cultivo"],
        "config": {
            "rows": "anio", "cols": "cultivo", "measure": "produccion",
            "cols_options": ["cultivo", "desagregacion", "sistema", "region", ""],
            "filters": [{"level": "cultivo", "label": "Cultivo"}, {"level": "region", "label": "Región"}],
            "chart1": "lines", "chart2": "index_lines",
            "chart1_title": "Medida por periodo y serie de columnas",
            "chart2_title": "Índice 2019 = 100: producción, registros y municipios",
        },
        "interpretacion": [
            "Entre trienios equivalentes los registros crecen mucho más que la producción: el crecimiento de "
            "R4 refleja sobre todo una mayor desagregación del reporte, no una mayor oferta.",
            "Plátano y yuca crecen en producción; maíz y frijol caen de forma sostenida. Papa y arroz se mantienen estables en el total anual.",
            "El drill-down a periodo muestra cambios de estacionalidad (arroz) que desaparecen en el roll-up a año.",
        ],
        "limitacion": "Seis años (2019–2024) permiten comparar dos trienios pero no separar tendencia de ciclo "
                      "climático; el plátano solo tiene periodo anual y no entra en comparaciones A vs. B.",
        "decision": "Usar toneladas y municipios únicos, y no número de registros, como indicadores de "
                    "seguimiento temporal; revisar por semestre los calendarios de compra y almacenamiento de arroz.",
    },
    {
        "slug": "sistemas", "num": 3, "icon": "bi-gear-wide-connected", "color": "warning",
        "titulo": "Brecha de rendimiento entre sistemas productivos",
        "pregunta": "¿Qué diferencia de rendimiento (t/ha) hay entre los sistemas tecnificado y "
                    "tradicional de maíz y arroz en cada región, y qué parte del área cosechada "
                    "depende del sistema de menor rendimiento?",
        "profundiza": "R4 encontró que el maíz domina la población evaluada (37,8 % de los registros) y "
                      "que el arroz es el menos evaluado, pero no explicó por qué. Cruzar sistema "
                      "productivo, cultivo y territorio muestra que ese predominio corresponde sobre "
                      "todo a maíz tradicional de bajo rendimiento.",
        "dimensiones": ["Sistema productivo", "Cultivo", "Territorio", "Tiempo (filtro)"],
        "medidas": ["rendimiento", "area_cosechada", "produccion", "registros"],
        "jerarquias": ["sistema", "territorio"],
        "config": {
            "rows": "region", "cols": "sistema", "measure": "rendimiento",
            "cols_options": ["sistema", "criterio", "cultivo", "trienio", ""],
            "filters": [{"level": "cultivo", "label": "Cultivo", "default": "Maíz"},
                        {"level": "trienio", "label": "Trienio"}],
            "chart1": "grouped", "chart2": "system_share",
            "chart1_title": "Medida por territorio y sistema productivo",
            "chart2_title": "Composición del área cosechada por sistema (% de la fila)",
        },
        "interpretacion": [
            "En maíz y arroz el sistema tecnificado rinde entre 2 y 3 veces más que el tradicional en todas las regiones; "
            "la brecha se mantiene al cambiar de territorio, así que no es un efecto de una sola región.",
            "El área tradicional se concentra en el Caribe (maíz) y en la Amazonía; la Orinoquía es casi totalmente tecnificada.",
            "Para yuca y plátano la dimensión distingue destino (industrial, exportación, consumo interno), no tecnología.",
        ],
        "limitacion": "EVA solo diferencia el nivel tecnológico en maíz y arroz; para papa y frijol el sistema es "
                      "«Sin diferenciar», por lo que la brecha no puede medirse en esos cultivos.",
        "decision": "Priorizar programas de tecnificación y asistencia técnica en el maíz tradicional del Caribe, "
                    "donde coinciden la mayor área tradicional y el menor rendimiento.",
    },
    {
        "slug": "cosecha", "num": 4, "icon": "bi-cloud-rain-heavy-fill", "color": "danger",
        "titulo": "Área sembrada que no llega a cosecharse",
        "pregunta": "¿Qué combinaciones de territorio, año y cultivo presentan la menor tasa de "
                    "cosecha (área cosechada / área sembrada) y dónde se acumula el área no cosechada?",
        "profundiza": "R4 se limitó a la presencia de registros (cultivo × región × semestre) y no "
                      "usó las áreas. Aquí se miden las pérdidas de área por territorio y año, "
                      "y se distingue un problema persistente de un evento puntual.",
        "dimensiones": ["Territorio", "Tiempo", "Cultivo", "Calidad (atributo degenerado)"],
        "medidas": ["tasa_cosecha", "area_no_cosechada", "area_sembrada"],
        "jerarquias": ["territorio", "tiempo"],
        "config": {
            "rows": "region", "cols": "anio", "measure": "tasa_cosecha",
            "cols_options": ["anio", "trienio", "cultivo", "sistema", ""],
            "filters": [{"level": "cultivo", "label": "Cultivo"}, {"level": "semestre", "label": "Periodo"}],
            "quality_toggle": True,
            "chart1": "hbar", "chart2": "harvest_trend",
            "chart1_title": "Medida por miembro del nivel de filas (clic = drill-down)",
            "chart2_title": "Tasa de cosecha (%) por año en los territorios con más área sembrada",
        },
        "interpretacion": [
            "La tasa nacional de cosecha es alta (≈ 94 %), pero el área no cosechada se concentra en el Caribe "
            "y en maíz, con picos puntuales por año (arroz 2021, maíz 2024).",
            "El drill-down de región a departamento revela que los promedios regionales ocultan caídas fuertes "
            "en departamentos concretos (Sucre, Bolívar, Córdoba).",
            "El filtro de calidad cambia el orden entre regiones: las conclusiones se presentan con ambos criterios.",
        ],
        "limitacion": f"El {fmt(13.7, 1)} % de las filas tiene área cosechada mayor que la sembrada (desfase entre "
                      "semestres de siembra y cosecha). Excluirlas sesga la tasa hacia abajo y conservarlas la sesga "
                      "hacia arriba; la tasa debe leerse como indicador relativo, no como pérdida exacta.",
        "decision": "Activar seguros agropecuarios y alertas de riesgo climático por departamento y año para arroz y "
                    "maíz del Caribe, en vez de medidas nacionales uniformes.",
    },
]
VISTAS_BY_SLUG = {v["slug"]: v for v in VISTAS}

# Ejemplos guiados de las cinco operaciones (se abren en su vista con ?ej=<id>).
EJEMPLOS = [
    {
        "id": "drill-papa", "op": "Drill-down", "vista": "territorial", "icon": "bi-zoom-in",
        "titulo": "Papa: de región a departamento y de departamento a municipio",
        "state": {"rows": "municipio", "cols": "", "measure": "produccion",
                  "filters": {"cultivo": ["Papa"]},
                  "drill": [{"level": "region", "value": "Andina"}, {"level": "departamento", "value": "Boyacá"}]},
        "dimensiones": "Territorio (región → departamento → municipio), Cultivo (slice = Papa).",
        "medidas": "Producción (t, SUM) y participación sobre la producción de la selección.",
        "nivel": "Región → Departamento (Andina) → Municipio (Boyacá).",
    },
    {
        "id": "pivot-region-cultivo", "op": "Pivot", "vista": "territorial", "icon": "bi-arrow-left-right",
        "titulo": "Cultivo × región en lugar de región × cultivo",
        "state": {"rows": "cultivo", "cols": "region", "measure": "produccion", "filters": {}, "drill": []},
        "dimensiones": "Cultivo y Territorio (región).",
        "medidas": "Producción (t); porcentajes de fila (denominador = total del cultivo).",
        "nivel": "Cultivo × Región, sin filtros.",
    },
    {
        "id": "rollup-arroz", "op": "Roll-up", "vista": "temporal", "icon": "bi-zoom-out",
        "titulo": "Arroz: de periodo semestral a año y a trienio",
        "state": {"rows": "periodo", "cols": "", "measure": "produccion",
                  "filters": {"cultivo": ["Arroz"]}, "drill": []},
        "dimensiones": "Tiempo (trienio → año → periodo), Cultivo (slice = Arroz).",
        "medidas": "Producción (t, SUM).",
        "nivel": "Se parte del nivel Periodo y se pulsa Roll-up hasta Año y Trienio.",
    },
    {
        "id": "slice-maiz", "op": "Slice", "vista": "sistemas", "icon": "bi-scissors",
        "titulo": "Corte del cubo en Cultivo = Maíz",
        "state": {"rows": "region", "cols": "sistema", "measure": "rendimiento",
                  "filters": {"cultivo": ["Maíz"]}, "drill": []},
        "dimensiones": "Cultivo (slice), Territorio (región) × Sistema productivo.",
        "medidas": "Rendimiento ponderado (t/ha) = SUM(producción) / SUM(área cosechada).",
        "nivel": "Región × Sistema con Cultivo = Maíz.",
    },
    {
        "id": "dice-arroz-caribe", "op": "Dice", "vista": "cosecha", "icon": "bi-grid-3x3-gap-fill",
        "titulo": "Arroz × Caribe × 2019–2024: tasa de cosecha por departamento y año",
        "state": {"rows": "departamento", "cols": "anio", "measure": "tasa_cosecha",
                  "filters": {"cultivo": ["Arroz"]}, "drill": [{"level": "region", "value": "Caribe"}]},
        "dimensiones": "Cultivo (Arroz) + Territorio (Caribe) como filtros; Departamento × Año.",
        "medidas": "Tasa de cosecha (%) = SUM(cosechada) / SUM(sembrada) × 100.",
        "nivel": "Departamento × Año, filtrado por dos dimensiones.",
    },
]
EJEMPLOS_BY_ID = {e["id"]: e for e in EJEMPLOS}


# ================================================================ API de vistas
def parse_state(slug: str, args) -> dict:
    """Estado de la vista desde los parámetros GET (`rows`, `cols`, `measure`, `f_<nivel>`)."""
    cfg = VISTAS_BY_SLUG[slug]["config"]
    rows = args.get("rows") or cfg["rows"]
    cols = args.get("cols", cfg["cols"]) or None
    measure = args.get("measure") or cfg["measure"]
    filters = {}
    for key in args:
        if key.startswith("f_"):
            level = key[2:]
            vals = [v for v in args.getlist(key) if v]
            if vals:
                filters[level] = vals
    return {"rows": rows, "cols": cols, "measure": measure, "filters": filters}


def vista_query(db_path: Path, slug: str, state: dict) -> dict:
    with closing(dw.connect(db_path)) as con:
        matrix = olap.query(con, state["rows"], state["measure"], state["cols"], state["filters"])
        return {
            "matrix": matrix,
            "kpis": _KPIS[slug](con, state),
            "chart2": _CHART2[slug](con, state),
            "operation": _operation_label(state),
        }


def _operation_label(state: dict) -> str:
    dims = {_level_dim(level) for level in state["filters"]}
    if len(dims) >= 2:
        return "Dice"
    if len(dims) == 1:
        return "Slice"
    return "Consulta base"


# ---------------------------------------------------------------- indicadores
def _kpi(label, value, detail="", unit=""):
    return {"label": label, "value": value, "unit": unit, "detail": detail}


def _concentration(con, rows, filters, measure="produccion"):
    q = olap.query(con, rows, measure, None, filters, limit=100000)
    acc, k = 0, 0
    for v in q["row_totals"]:
        acc += v or 0
        k += 1
        if q["grand_total"] and acc >= q["grand_total"] / 2:
            break
    return q, k


def _kpis_territorial(con, st):
    f = st["filters"]
    rows = st["rows"] if _level_dim(st["rows"]) == "territorio" else "departamento"
    q, k = _concentration(con, rows, f)
    label = LEVELS[rows][1].lower()
    lead = (f"{q['rows'][0]} · {fmt(q['share_pct'][0], 1)} %") if q["rows"] else "—"
    return [
        _kpi("Producción de la selección", fmt(q["grand_total"]), "SUM(producción) con los filtros activos", "t"),
        _kpi(f"Líder por {label}", lead, f"Denominador: producción total de la selección"),
        _kpi(f"{_PLURAL.get(rows, LEVELS[rows][1])} que reúnen el 50 %", f"{k} de {q['total_members']}",
             f"Nº mínimo de miembros del nivel {label} que suman la mitad de la producción"),
    ]


def _kpis_temporal(con, st):
    f = {k: v for k, v in st["filters"].items() if _level_dim(k) != "tiempo"}
    t1 = olap.kpis(con, ["produccion", "registros", "rendimiento"], {**f, "trienio": ["2019–2021"]})
    t2 = olap.kpis(con, ["produccion", "registros", "rendimiento"], {**f, "trienio": ["2022–2024"]})
    return [
        _kpi("Δ producción entre trienios", _signed(_var(t2["produccion"], t1["produccion"])),
             f"2022–2024 ({fmt(t2['produccion'])} t) vs. 2019–2021 ({fmt(t1['produccion'])} t)"),
        _kpi("Δ registros entre trienios", _signed(_var(t2["registros"], t1["registros"])),
             f"{fmt(t2['registros'])} vs. {fmt(t1['registros'])} registros (COUNT)"),
        _kpi("Δ rendimiento ponderado", _signed(
            None if t1["rendimiento"] is None or t2["rendimiento"] is None
            else round(t2["rendimiento"] - t1["rendimiento"], 2), 2, " t/ha"),
             f"{fmt(t2['rendimiento'], 2)} vs. {fmt(t1['rendimiento'], 2)} t/ha (SUM prod / SUM área cosechada)"),
    ]


def _kpis_sistemas(con, st):
    f = {k: v for k, v in st["filters"].items() if _level_dim(k) != "sistema"}
    tec = olap.kpis(con, ["rendimiento", "area_cosechada"], {**f, "sistema": ["Tecnificado"]})
    tra = olap.kpis(con, ["rendimiento", "area_cosechada"], {**f, "sistema": ["Tradicional"]})
    brecha = (f"Brecha: {fmt(tec['rendimiento'] / tra['rendimiento'], 1)}×"
              if tec["rendimiento"] and tra["rendimiento"] else "Sin ambos sistemas en la selección")
    area_tot = (tec["area_cosechada"] or 0) + (tra["area_cosechada"] or 0)
    return [
        _kpi("Rendimiento tecnificado", fmt(tec["rendimiento"], 2), brecha, "t/ha"),
        _kpi("Rendimiento tradicional", fmt(tra["rendimiento"], 2), "SUM(producción) / SUM(área cosechada)", "t/ha"),
        _kpi("Área cosechada en sistema tradicional",
             (fmt(_pct(tra["area_cosechada"] or 0, area_tot), 1) + " %") if area_tot else "—",
             f"Denominador: área tecnificada + tradicional ({fmt(area_tot)} ha)"),
    ]


def _kpis_cosecha(con, st):
    f = st["filters"]
    k = olap.kpis(con, ["tasa_cosecha", "area_no_cosechada", "area_sembrada"], f)
    rows = st["rows"]
    cols = st["cols"] if st["cols"] and _level_dim(st["cols"]) != _level_dim(rows) else (
        "anio" if _level_dim(rows) != "tiempo" else "cultivo")
    worst = olap.extreme_cell(con, rows, cols, "tasa_cosecha", f)
    return [
        _kpi("Tasa de cosecha", fmt(k["tasa_cosecha"], 1) + " %",
             f"SUM(cosechada) / SUM(sembrada) · sembrada = {fmt(k['area_sembrada'])} ha"),
        _kpi("Área no cosechada (neta)", fmt(k["area_no_cosechada"]),
             "SUM(sembrada) − SUM(cosechada)", "ha"),
        _kpi("Combinación con menor tasa", f"{worst[0]} · {worst[1]}: {fmt(worst[2], 1)} %" if worst else "—",
             f"{LEVELS[rows][1]} × {LEVELS[cols][1]} con ≥ 1.000 ha sembradas"),
    ]


_KPIS = {"territorial": _kpis_territorial, "temporal": _kpis_temporal,
         "sistemas": _kpis_sistemas, "cosecha": _kpis_cosecha}


# ------------------------------------------------------------ segunda gráfica
def _chart2_territorial(con, st):
    f, rows = st["filters"], st["rows"]
    prod = olap.query(con, rows, "produccion", None, f, limit=15)
    reg = olap.query(con, rows, "registros", None, f, limit=100000)
    reg_share = dict(zip(reg["rows"], reg["share_pct"] or []))
    return {"type": "bar", "unit": "%", "labels": prod["rows"], "datasets": [
        {"label": "% de la producción", "values": prod["share_pct"] or []},
        {"label": "% de los registros", "values": [reg_share.get(r) for r in prod["rows"]]},
    ], "note": f"Denominadores: producción y registros totales de la selección, por {LEVELS[rows][1].lower()}."}


def _chart2_temporal(con, st):
    f = {k: v for k, v in st["filters"].items() if _level_dim(k) != "tiempo"}
    series = {m: olap.query(con, "anio", m, None, f) for m in ("produccion", "registros", "municipios")}
    labels = series["produccion"]["rows"]
    out = []
    for m, label in (("produccion", "Producción"), ("registros", "Registros"), ("municipios", "Municipios")):
        vals = series[m]["row_totals"]
        base = vals[0] if vals else None
        out.append({"label": label, "values": [round(100 * v / base, 1) if base and v is not None else None for v in vals]})
    return {"type": "line", "unit": "índice", "labels": labels, "datasets": out,
            "note": "Cada serie se divide por su valor de 2019 (= 100) con los mismos filtros."}


def _chart2_sistemas(con, st):
    f = st["filters"]
    terr = next((lv for lv in (st["rows"], st["cols"]) if lv and _level_dim(lv) == "territorio"), "region")
    q = olap.query(con, terr, "area_cosechada", "sistema", f, limit=15)
    datasets = []
    for j, s in enumerate(q["cols"]):
        datasets.append({"label": s, "values": [
            _pct(q["cells"][i][j] or 0, q["row_totals"][i]) for i in range(len(q["rows"]))]})
    return {"type": "stacked", "unit": "%", "labels": q["rows"], "series_level": "sistema", "datasets": datasets,
            "note": f"Denominador: área cosechada total de cada {LEVELS[terr][1].lower()} en la selección."}


def _chart2_cosecha(con, st):
    f = {k: v for k, v in st["filters"].items() if k not in ("anio", "trienio", "periodo")}
    terr = next((lv for lv in (st["rows"], st["cols"]) if lv and _level_dim(lv) == "territorio"), "region")
    top = olap.query(con, terr, "area_sembrada", None, f, limit=5)["rows"]
    q = olap.query(con, "anio", "tasa_cosecha", terr, {**f, terr: top} if top else f)
    return {"type": "line", "unit": "%", "labels": q["rows"], "series_level": terr, "datasets": [
        {"label": c, "values": [row[j] for row in q["cells"]]} for j, c in enumerate(q["cols"])
    ], "note": f"Tasa de cosecha por año de las 5 unidades ({LEVELS[terr][1].lower()}) con mayor área sembrada; "
               "se recalcula con SUM de áreas en cada año, no como promedio de tasas."}


_CHART2 = {"territorial": _chart2_territorial, "temporal": _chart2_temporal,
           "sistemas": _chart2_sistemas, "cosecha": _chart2_cosecha}


# ================================================================ conocimientos
def _conocimientos(con) -> dict[str, list[dict]]:
    Q = olap.query
    K = olap.kpis

    # --- Vista 1 · territorial
    reg = Q(con, "region", "registros")
    prod = Q(con, "region", "produccion")
    rs, ps = dict(zip(reg["rows"], reg["share_pct"])), dict(zip(prod["rows"], prod["share_pct"]))
    arroz = Q(con, "departamento", "produccion", None, {"cultivo": ["Arroz"]})
    platano = Q(con, "departamento", "produccion", None, {"cultivo": ["Plátano"]})
    papa_dep = Q(con, "departamento", "produccion", None, {"cultivo": ["Papa"]})
    papa_top3 = round(sum(papa_dep["share_pct"][:3]), 1)
    papa_mun, k_papa = _concentration(con, "municipio", {"cultivo": ["Papa"]})
    boy = Q(con, "municipio", "produccion", None, {"cultivo": ["Papa"], "departamento": ["Boyacá"]})

    # --- Vista 2 · temporal
    m = {"cultivo": ["Maíz"]}
    mz_reg = Q(con, "anio", "registros", None, m)
    mz_prod = Q(con, "anio", "produccion", None, m)
    mz_mun = Q(con, "anio", "municipios", None, m)
    mz_des = Q(con, "anio", "registros", "desagregacion", m)
    n_des = {y: sum(1 for c in row if c) for y, row in zip(mz_des["rows"], mz_des["cells"])}
    a = {"cultivo": ["Arroz"]}
    ar_per = dict(zip(*[Q(con, "periodo", "produccion", None, a)[k] for k in ("rows", "row_totals")]))
    ar_y = dict(zip(*[Q(con, "anio", "produccion", None, a)[k] for k in ("rows", "row_totals")]))

    # --- Vista 3 · sistemas
    tec = K(con, ["rendimiento", "area_cosechada", "produccion", "registros"], {**m, "sistema": ["Tecnificado"]})
    tra = K(con, ["rendimiento", "area_cosechada", "produccion", "registros"], {**m, "sistema": ["Tradicional"]})
    mz_tot = K(con, ["area_cosechada", "produccion", "registros"], m)
    caribe_tra = K(con, ["rendimiento", "area_cosechada"], {**m, "region": ["Caribe"], "sistema": ["Tradicional"]})
    caribe_tec = K(con, ["rendimiento"], {**m, "region": ["Caribe"], "sistema": ["Tecnificado"]})
    caribe_mz = K(con, ["area_cosechada"], {**m, "region": ["Caribe"]})
    ar_reg = Q(con, "region", "area_cosechada", "sistema", a)
    ar_orin = ar_reg["rows"].index("Orinoquía")
    orin_tec = ar_reg["cells"][ar_orin][ar_reg["cols"].index("Tecnificado")]
    ar_rend = Q(con, "region", "rendimiento", "sistema", a)
    rend = {r: dict(zip(ar_rend["cols"], row)) for r, row in zip(ar_rend["rows"], ar_rend["cells"])}
    ar_tra_car = K(con, ["area_cosechada"], {**a, "region": ["Caribe"], "sistema": ["Tradicional"]})

    # --- Vista 4 · cosecha
    no = Q(con, "region", "area_no_cosechada")
    ns = dict(zip(no["rows"], no["share_pct"]))
    tasa = dict(zip(*[Q(con, "region", "tasa_cosecha")[k] for k in ("rows", "row_totals")]))
    no_coh = Q(con, "region", "area_no_cosechada", None, {"coherencia": ["Coherente"]})
    ns_coh = dict(zip(no_coh["rows"], no_coh["share_pct"]))
    car_dep = Q(con, "departamento", "area_no_cosechada", None, {"region": ["Caribe"]})
    car_mz = K(con, ["area_no_cosechada"], {"region": ["Caribe"], "cultivo": ["Maíz"]})
    ar_t = dict(zip(*[Q(con, "anio", "tasa_cosecha", None, a)[k] for k in ("rows", "row_totals")]))
    ar_no = dict(zip(*[Q(con, "anio", "area_no_cosechada", None, a)[k] for k in ("rows", "row_totals")]))
    suc = Q(con, "anio", "tasa_cosecha", None, {**a, "departamento": ["Sucre"]})
    suc_t = dict(zip(suc["rows"], suc["row_totals"]))
    suc_coh = K(con, ["tasa_cosecha"], {**a, "departamento": ["Sucre"], "anio": ["2021"], "coherencia": ["Coherente"]})

    return {
        "territorial": [
            {
                "n": "C1", "color": "success", "icon": "bi-pin-map-fill",
                "titulo": "La Orinoquía produce cuatro veces más de lo que su número de registros sugiere",
                "pregunta": "¿Coincide la concentración territorial de registros (R4) con la de producción?",
                "variables": "Territorio (región, departamento) × Cultivo; medidas: Registros (COUNT) y Producción (SUM, t), como % del total nacional.",
                "procedimiento": "Consulta base Región × Cultivo; luego slice Cultivo = Arroz y Cultivo = Plátano con drill-down a Departamento.",
                "evidencia": "Gráfica 2 de la vista (participación en producción vs. en registros) y matriz Región × Cultivo.",
                "hallazgo": f"Orinoquía: {fmt(rs['Orinoquía'], 1)} % de los registros pero {fmt(ps['Orinoquía'], 1)} % de la producción "
                            f"nacional ({fmt(prod['row_totals'][prod['rows'].index('Orinoquía')])} t). Andina baja de {fmt(rs['Andina'], 1)} % "
                            f"de registros a {fmt(ps['Andina'], 1)} % de producción. Al bajar a departamento: {arroz['rows'][0]} aporta "
                            f"{fmt(arroz['share_pct'][0], 1)} % del arroz y {platano['rows'][0]} {fmt(platano['share_pct'][0], 1)} % del plátano del país.",
                "interpretacion": "La Orinoquía produce mucho volumen con pocas unidades productivas de gran escala (arroz y plátano). "
                                  "El conocimiento evidente de R4 (predominio andino) describe dónde hay más reportes, no dónde se produce más.",
                "utilidad": "Para la planeación de abastecimiento y logística de acopio, la Orinoquía debe pesar según su volumen y no según el número de municipios.",
                "limitacion": "El volumen no mide el destino del alimento ni el consumo local; no permite concluir sobre disponibilidad de alimentos en la región.",
            },
            {
                "n": "C2", "color": "success", "icon": "bi-diagram-3-fill",
                "titulo": "La papa se concentra más a medida que se baja de nivel territorial",
                "pregunta": "¿Cuántos territorios sostienen la producción de papa en cada nivel de la jerarquía?",
                "variables": "Territorio (región → departamento → municipio) × Cultivo (Papa); medida: Producción (t) y su participación.",
                "procedimiento": "Slice Cultivo = Papa; drill-down Andina → Boyacá → municipios. En cada nivel se recalcula la participación sobre la producción de la selección.",
                "evidencia": "Ejemplo guiado «Drill-down Papa», matriz por municipio e indicador «miembros que reúnen el 50 %».",
                "hallazgo": f"Tres departamentos ({', '.join(papa_dep['rows'][:3])}) suman {fmt(papa_top3, 1)} % de la papa nacional. "
                            f"Solo {k_papa} de {papa_mun['total_members']} municipios productores reúnen la mitad del volumen. En Boyacá, "
                            f"{boy['rows'][0]} aporta {fmt(boy['share_pct'][0], 1)} % de la producción departamental.",
                "interpretacion": "La concentración que en R4 parecía regional (Andina) es en realidad un núcleo de pocos municipios del altiplano. "
                                  "Un evento climático o sanitario local afecta una porción grande de la oferta nacional.",
                "utilidad": "Permite focalizar alertas tempranas, asistencia técnica y monitoreo de precios de papa en un grupo reducido de municipios.",
                "limitacion": "No se dispone de datos de precios ni de comercio intermunicipal para confirmar la dependencia de otros territorios (hipótesis).",
            },
        ],
        "temporal": [
            {
                "n": "C3", "color": "info", "icon": "bi-graph-down-arrow",
                "titulo": "Más registros de maíz no significan más maíz",
                "pregunta": "¿El crecimiento de registros de 2021 que vio R4 refleja un aumento de la producción?",
                "variables": "Tiempo (año) × Cultivo (cultivo → desagregación); medidas: Registros, Municipios únicos (COUNT DISTINCT), Producción (t).",
                "procedimiento": "Slice Cultivo = Maíz; filas = Año; columnas = Desagregación (drill-down en la jerarquía de cultivo); gráfico índice 2019 = 100.",
                "evidencia": "Gráfica 2 (índice de producción, registros y municipios) y matriz Año × Desagregación con Cultivo = Maíz.",
                "hallazgo": f"Registros de maíz: {fmt(mz_reg['row_totals'][0])} (2019) → {fmt(mz_reg['row_totals'][-1])} (2024), "
                            f"{_signed(_var(mz_reg['row_totals'][-1], mz_reg['row_totals'][0]))}; municipios: {fmt(mz_mun['row_totals'][0])} → "
                            f"{fmt(mz_mun['row_totals'][-1])} ({_signed(_var(mz_mun['row_totals'][-1], mz_mun['row_totals'][0]))}); producción: "
                            f"{fmt(mz_prod['row_totals'][0])} t → {fmt(mz_prod['row_totals'][-1])} t ({_signed(_var(mz_prod['row_totals'][-1], mz_prod['row_totals'][0]))}). "
                            f"Las desagregaciones pasan de {n_des['2020']} en 2020 a {n_des['2021']} en 2021.",
                "interpretacion": "El salto de registros de R4 es un cambio de clasificación de EVA (maíz amarillo/blanco), no una expansión del cultivo. "
                                  "En ese mismo periodo la producción de maíz cayó.",
                "utilidad": "Evita usar el número de registros como indicador de oferta; el seguimiento del maíz debe hacerse con toneladas y área.",
                "limitacion": "No se puede atribuir la caída a una causa (importaciones, precios, clima) con estos datos; es una asociación temporal.",
            },
            {
                "n": "C4", "color": "info", "icon": "bi-arrow-down-up",
                "titulo": "El arroz trasladó su cosecha principal del semestre A al B",
                "pregunta": "¿El total anual estable del arroz oculta cambios entre semestres?",
                "variables": "Tiempo (trienio → año → periodo) × Cultivo (Arroz); medida: Producción (t).",
                "procedimiento": "Slice Cultivo = Arroz; drill-down de Año a Periodo y roll-up de vuelta a Año y Trienio (ejemplo guiado).",
                "evidencia": "Matriz y gráfica 1 en el nivel Periodo vs. nivel Año.",
                "hallazgo": f"En 2019 el semestre A aportó {fmt(_pct(ar_per['2019A'], ar_y['2019']), 1)} % del arroz del año "
                            f"({fmt(ar_per['2019A'])} t); en 2024 solo {fmt(_pct(ar_per['2024A'], ar_y['2024']), 1)} % "
                            f"({fmt(ar_per['2024A'])} t). En el nivel Año la producción pasa de {fmt(ar_y['2019'])} t a {fmt(ar_y['2024'])} t "
                            f"({_signed(_var(ar_y['2024'], ar_y['2019']))}).",
                "interpretacion": "El roll-up a año esconde un cambio de calendario productivo: la oferta de arroz se desplazó al segundo semestre. "
                                  "Como hipótesis, puede relacionarse con la disponibilidad de agua o con decisiones de siembra; los datos no lo comprueban.",
                "utilidad": "La programación de almacenamiento y de compras públicas de arroz debe revisarse por semestre, no solo por año.",
                "limitacion": "Los semestres A y B solo son comparables entre sí para cultivos transitorios; el plátano (anual) no entra en esta comparación.",
            },
        ],
        "sistemas": [
            {
                "n": "C5", "color": "warning", "icon": "bi-speedometer2",
                "titulo": "El maíz tradicional ocupa la mayor parte del área con menos de la mitad del rendimiento",
                "pregunta": "¿Qué explica que el maíz domine los registros (R4) y sea solo el 10 % de la producción?",
                "variables": "Sistema productivo × Cultivo (Maíz) × Territorio (región); medidas: Rendimiento ponderado (t/ha), Área cosechada (ha), Producción (t), Registros.",
                "procedimiento": "Slice Cultivo = Maíz; Región × Sistema; luego dice Región = Caribe × Cultivo = Maíz.",
                "evidencia": "Indicadores de la vista con Cultivo = Maíz y matriz Región × Sistema (ejemplo guiado «Slice»).",
                "hallazgo": f"Rendimiento del maíz tecnificado {fmt(tec['rendimiento'], 2)} t/ha vs. tradicional {fmt(tra['rendimiento'], 2)} t/ha "
                            f"({fmt(tec['rendimiento'] / tra['rendimiento'], 1)}×). El tradicional reúne {fmt(_pct(tra['registros'], mz_tot['registros']), 1)} % "
                            f"de los registros y {fmt(_pct(tra['area_cosechada'], mz_tot['area_cosechada']), 1)} % del área cosechada, pero solo "
                            f"{fmt(_pct(tra['produccion'], mz_tot['produccion']), 1)} % de la producción. En el Caribe el tradicional cubre "
                            f"{fmt(_pct(caribe_tra['area_cosechada'], caribe_mz['area_cosechada']), 1)} % del área de maíz con "
                            f"{fmt(caribe_tra['rendimiento'], 2)} t/ha (tecnificado: {fmt(caribe_tec['rendimiento'], 2)} t/ha).",
                "interpretacion": "El predominio del maíz en R4 se debe sobre todo a muchas unidades de maíz tradicional, frecuentemente "
                                  "de autoconsumo y baja productividad. Ese es el segmento donde la seguridad alimentaria es más frágil.",
                "utilidad": "Señala al maíz tradicional del Caribe como prioridad para programas de tecnificación, semillas y extensión rural.",
                "limitacion": "La brecha es una asociación: el rendimiento también depende de suelos y clima; no prueba que tecnificar elimine la diferencia.",
            },
            {
                "n": "C6", "color": "warning", "icon": "bi-droplet-half",
                "titulo": "El arroz de la Orinoquía es casi totalmente tecnificado; el tradicional sobrevive en el Caribe",
                "pregunta": "¿Cómo se reparte el arroz entre sistemas y regiones, y qué rendimiento logra cada combinación?",
                "variables": "Sistema productivo × Territorio (región) × Cultivo (Arroz); medidas: Área cosechada (ha), Rendimiento (t/ha).",
                "procedimiento": "Slice Cultivo = Arroz; pivot de Región × Sistema a Sistema × Región; gráfica 2 con composición del área por sistema.",
                "evidencia": "Gráfica 2 (composición % del área por sistema) y matriz Región × Sistema con Cultivo = Arroz.",
                "hallazgo": f"Orinoquía tiene {fmt(ar_reg['share_pct'][ar_orin], 1)} % del área de arroz cosechada del país y el "
                            f"{fmt(_pct(orin_tec, ar_reg['row_totals'][ar_orin]), 1)} % de ella es tecnificada. El mayor rendimiento está en el arroz "
                            f"tecnificado andino ({fmt(rend['Andina']['Tecnificado'], 2)} t/ha); el arroz tradicional del Caribe "
                            f"({fmt(ar_tra_car['area_cosechada'])} ha) rinde {fmt(rend['Caribe']['Tradicional'], 2)} t/ha.",
                "interpretacion": "El arroz nacional depende de un sistema tecnificado territorialmente concentrado; el arroz tradicional "
                                  "del Caribe responde más a un sistema campesino que a una oferta comercial.",
                "utilidad": "Orienta apoyos diferenciados: infraestructura de riego y secamiento en la Orinoquía; asistencia técnica al arroz tradicional del Caribe.",
                "limitacion": "EVA solo diferencia sistema para maíz y arroz; para papa, frijol, yuca y plátano la comparación no es posible.",
            },
        ],
        "cosecha": [
            {
                "n": "C7", "color": "danger", "icon": "bi-exclamation-octagon-fill",
                "titulo": "El Caribe acumula la mayor área no cosechada, sobre todo en maíz y en Bolívar",
                "pregunta": "¿Dónde se pierde más área sembrada y qué cultivos y departamentos la explican?",
                "variables": "Territorio (región → departamento) × Cultivo × Calidad; medidas: Área no cosechada (ha), Tasa de cosecha (%).",
                "procedimiento": "Región × Cultivo con área no cosechada; drill-down Caribe → Departamento; repetición con el filtro de calidad «solo coherentes».",
                "evidencia": "Matriz Región × Cultivo (medida área no cosechada), gráfica 1 y prueba de sensibilidad con el filtro de calidad.",
                "hallazgo": f"Caribe: {fmt(ns['Caribe'], 1)} % del área no cosechada nacional ({fmt(no['row_totals'][no['rows'].index('Caribe')])} ha) con "
                            f"{fmt(rs['Caribe'], 1)} % de los registros y la menor tasa de cosecha ({fmt(tasa['Caribe'], 1)} %). El maíz aporta "
                            f"{fmt(car_mz['area_no_cosechada'])} ha y {car_dep['rows'][0]} {fmt(car_dep['share_pct'][0], 1)} % del área no cosechada caribeña. "
                            f"Excluyendo filas con área incoherente, el Caribe sigue entre las dos primeras ({fmt(ns_coh['Caribe'], 1)} %), pero la "
                            f"Orinoquía pasa a {fmt(ns_coh['Orinoquía'], 1)} %.",
                "interpretacion": "La pérdida de área en el Caribe es persistente y está ligada al maíz, el cultivo de base campesina de la región. "
                                  "El orden entre regiones depende del tratamiento de las filas incoherentes, por lo que se informa con ambos criterios.",
                "utilidad": "Prioriza seguros agropecuarios y gestión de riesgo climático para el maíz en Bolívar, Córdoba y Sucre.",
                "limitacion": "EVA no registra la causa de la pérdida (sequía, inundación, plagas, abandono); cualquier explicación es una hipótesis.",
            },
            {
                "n": "C8", "color": "danger", "icon": "bi-cloud-lightning-rain-fill",
                "titulo": "2021 fue un año atípico para el arroz del Caribe, con Sucre en el extremo",
                "pregunta": "¿La caída de la tasa de cosecha del arroz es generalizada o se concentra en un año y territorio?",
                "variables": "Tiempo (año) × Territorio (región → departamento) × Cultivo (Arroz); medidas: Tasa de cosecha (%), Área no cosechada (ha).",
                "procedimiento": "Dice Cultivo = Arroz × Región = Caribe; Departamento × Año; comparación con el nivel nacional y con el filtro «solo coherentes».",
                "evidencia": "Ejemplo guiado «Dice Arroz × Caribe», gráfica 2 y celda Sucre × 2021 de la matriz.",
                "hallazgo": f"La tasa nacional de cosecha de arroz pasó de {fmt(ar_t['2019'], 1)} % (2019) a {fmt(ar_t['2021'], 1)} % (2021); "
                            f"el área no cosechada subió de {fmt(ar_no['2019'])} ha a {fmt(ar_no['2021'])} ha. En el Caribe, Sucre "
                            f"registró {fmt(suc_t['2021'], 1)} % en 2021 (vs. {fmt(suc_t['2019'], 1)} % en 2019); el valor se mantiene en "
                            f"{fmt(suc_coh['tasa_cosecha'], 1)} % al excluir filas incoherentes.",
                "interpretacion": "Se trata de un choque puntual y localizado, no de un deterioro continuo. Como hipótesis, coincide con el "
                                  "periodo de lluvias intensas de La Niña 2021, que los datos de EVA no permiten verificar.",
                "utilidad": "Justifica sistemas de alerta y reservas de arroz activables por año y territorio, en lugar de medidas permanentes nacionales.",
                "limitacion": "Con seis años de datos no se puede estimar la frecuencia de estos eventos ni separar el efecto climático del de mercado.",
            },
        ],
    }


# ================================================================== contextos
def _vista_meta(v: dict) -> dict:
    return {
        **v,
        "medidas_info": [{"key": k, "label": MEASURES[k][1], "unit": MEASURES[k][2],
                          "agg": MEASURES[k][3], "additive": k in olap.ADDITIVE} for k in v["medidas"]],
        "jerarquias_info": [{"dim": olap.DIMENSIONS[h], "niveles": [LEVELS[lv][1] for lv in HIERARCHIES[h]]}
                            for h in v["jerarquias"]],
    }


def _cached_conocimientos(db_path: Path, cache) -> dict:
    key = "ctx:r5:conocimientos"
    data = cache.cache_get(key)
    if data is None:
        with closing(dw.connect(db_path)) as con:
            data = _conocimientos(con)
        cache.cache_set(key, data)
    return data


def build_r5_vista_context(db_path: Path, slug: str, cache) -> dict:
    v = VISTAS_BY_SLUG[slug]
    with closing(dw.connect(db_path)) as con:
        filter_options = {f["level"]: olap.members(con, f["level"]) for f in v["config"]["filters"]}
        # Orden fijo de miembros por nivel: el color de una serie sigue a su miembro, no a su rango.
        series_members = {lv: olap.members(con, lv) for lv in LEVELS if lv not in ("municipio", "periodo")}
    return {
        "vista": _vista_meta(v),
        "vistas": VISTAS,
        "conocimientos": _cached_conocimientos(db_path, cache)[slug],
        "ejemplos": [e for e in EJEMPLOS if e["vista"] == slug],
        "filter_options": filter_options,
        "series_members": series_members,
        "olap_meta": olap.model_metadata(),
    }


def build_r5_context(db_path: Path, source_json: Path, cache) -> dict:
    with closing(dw.connect(db_path)) as con:
        validaciones = olap.validations(con, source_json)
        counts = {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in (
            "fact_produccion_agricola", "dim_territorio", "dim_tiempo", "dim_cultivo", "dim_sistema_productivo")}
        resumen = olap.kpis(con, ["registros", "municipios", "produccion", "area_sembrada"])
        incoherentes = con.execute("SELECT SUM(area_incoherente) FROM fact_produccion_agricola").fetchone()[0]
        cosecha_cero = con.execute("SELECT COUNT(*) FROM fact_produccion_agricola WHERE area_cosechada_ha = 0").fetchone()[0]
        depts = con.execute("SELECT COUNT(DISTINCT departamento) FROM dim_territorio WHERE territorio_key <> 0").fetchone()[0]
        anios = con.execute("SELECT MIN(anio), MAX(anio) FROM dim_tiempo").fetchone()
    conocimientos = _cached_conocimientos(db_path, cache)
    return {
        "vistas": [_vista_meta(v) for v in VISTAS],
        "ejemplos": EJEMPLOS,
        "conocimientos_por_vista": conocimientos,
        "validaciones": validaciones,
        "validaciones_ok": sum(1 for x in validaciones if x["ok"]),
        "counts": counts,
        "resumen": resumen,
        "incoherentes": incoherentes,
        "incoherentes_pct": _pct(incoherentes, resumen["registros"]),
        "cosecha_cero": cosecha_cero,
        "total_depts": depts,
        "anio_min": anios[0], "anio_max": anios[1],
        "olap_meta": olap.model_metadata(),
        "levels": LEVELS, "measures": MEASURES, "hierarchies": HIERARCHIES,
    }
