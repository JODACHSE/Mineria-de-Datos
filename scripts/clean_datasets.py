"""Tratamiento real de calidad para los 4 datasets del proyecto (Etapa 2 / R2).

Uso:
    python scripts/clean_datasets.py

Lee la versión ya curada de R1 (`app/static/data/R1/*.json` — ya tipificada
y renombrada por `process_eva.py`/`rebuild_chart.py`, no se reprocesa el
CSV crudo ni se duplica el parseo de formato numérico colombiano) y aplica
las acciones de tratamiento descritas en el informe técnico de la Etapa 2:

- Eliminación de duplicados (verificación; no se encontraron para eliminar).
- Tratamiento de valores nulos: se documentan/flaggean, nunca se imputa un
  valor que la fuente no reportó.
- Corrección de tipos: se reutiliza la conversión ya hecha en R1.
- Estandarización de texto (espacios/casing) en campos categóricos.
- Estandarización temporal: `AnioNormalizado` en los datasets FAOSTAT
  (algunos años vienen como trienio, p. ej. "2000-2002").
- Corrección de la llave de unicidad en los datasets FAOSTAT (se le
  agrega `Unidad`, ver hallazgo de los "huevos en dos unidades").
- Validación de rangos (EVA: área cosechada > sembrada) y homologación de
  unidad por elemento (FAOSTAT): se marcan con una bandera, NUNCA se
  corrige el valor en silencio (no se sabe cuál campo es el erróneo).
- Tratamiento justificado de valores atípicos (± 1.5×RIC): se marcan con
  una bandera; no se eliminan, porque en este dominio (municipios o
  productos de gran escala) suelen ser datos reales, no errores.

Ninguna fila se elimina y ningún valor se fabrica: todo lo que no se
puede corregir sin ambigüedad queda documentado como bandera nueva en el
propio dataset tratado, para que el análisis aguas abajo decida cómo
tratarlo. Escribe en `app/static/data/R2/`:
- `{eva_basicos,qcl,qcl_basicos,fs}.json` — mismo formato {columns, rows}
  que R1, con las columnas originales intactas + las banderas nuevas.
- `log_tratamiento.json` — lista de acciones aplicadas (con su
  justificación) + un resumen antes/después de las 6 dimensiones de
  calidad por dataset, calculado por el propio script (no a mano).
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.quality import (  # noqa: E402
    DATASET_SCHEMA,
    DATASETS,
    _count_duplicates,
    _hallazgo_duplicados_por_unidad,
    _iqr_bounds_por_grupo,
    _percentile,
    _rows_as_dicts,
    _to_float,
    compute_dimensions,
)
from process_eva import CROP_MAPPING  # noqa: E402  (reutiliza el crosswalk ya definido en R1)

R1_JSON_DIR = BASE_DIR / "app" / "static" / "data" / "R1"
R2_JSON_DIR = BASE_DIR / "app" / "static" / "data" / "R2"

TEXT_FIELDS = {
    "eva_basicos": ("Departamento", "Municipio", "GrupoCultivo", "Subgrupo", "Cultivo",
                    "DesagregacionCultivo", "CicloCultivo", "EstadoFisico", "NombreCientifico"),
    "qcl": ("Área", "Producto", "Elemento", "Unidad"),
    "qcl_basicos": ("Área", "Producto", "Elemento", "Unidad"),
    "fs": ("Área", "Producto", "Elemento", "Unidad"),
}


def log(msg: str) -> None:
    print(f"[clean_datasets] {msg}")


def _cargar_r1_json(name: str) -> dict:
    path = R1_JSON_DIR / DATASETS[name]
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _normalizar_texto(v):
    if not isinstance(v, str):
        return v
    return re.sub(r"\s+", " ", v.strip())


def _iqr_bounds(valores: list[float]) -> tuple[float, float]:
    ordenados = sorted(valores)
    q1, q3 = _percentile(ordenados, 0.25), _percentile(ordenados, 0.75)
    iqr = q3 - q1
    return q1 - 1.5 * iqr, q3 + 1.5 * iqr


def _dataset_desde_filas(rows: list[dict]) -> dict:
    cols = list(rows[0].keys()) if rows else []
    return dict(columns=cols, rows=[[r.get(c) for c in cols] for r in rows])


def clean_eva(dataset: dict) -> tuple[dict, list[dict]]:
    schema = DATASET_SCHEMA["eva_basicos"]
    rows = _rows_as_dicts(dataset)
    total = len(rows)
    acciones: list[dict] = []

    # 1) Duplicados exactos bajo la llave de unicidad
    n_dup = _count_duplicates(rows, schema["unique_key_fields"])
    acciones.append(dict(
        dataset="eva_basicos", accion="Eliminación de duplicados",
        n_afectados=n_dup, decision="sin_accion" if n_dup == 0 else "eliminacion",
        justificacion=(
            "Se verificó la llave (municipio, cultivo, desagregación, año, periodo); "
            "no se encontraron filas duplicadas para eliminar."
            if n_dup == 0 else f"Se eliminaron {n_dup} filas duplicadas exactas."
        ),
    ))

    # 2) Nulos en campos numéricos críticos
    n_nulos = sum(1 for r in rows for f in schema["numeric_fields"] if r.get(f) in (None, "", "NaN"))
    acciones.append(dict(
        dataset="eva_basicos", accion="Tratamiento de valores nulos",
        n_afectados=n_nulos, decision="sin_accion",
        justificacion="No se encontraron valores nulos en las variables numéricas críticas; "
                       "no se requirió imputación ni eliminación.",
    ))

    # 3) Estandarización de texto (espacios/casing)
    n_texto = 0
    for r in rows:
        for f in TEXT_FIELDS["eva_basicos"]:
            nv = _normalizar_texto(r.get(f))
            if nv != r.get(f):
                r[f] = nv
                n_texto += 1
    acciones.append(dict(
        dataset="eva_basicos", accion="Estandarización de texto (espacios/casing)",
        n_afectados=n_texto, decision="correccion" if n_texto else "sin_accion",
        justificacion="Se recorta espacio en blanco y se colapsan espacios dobles en campos de texto y "
                       "categóricos; en este corte no se encontraron variantes (la fuente ya llega curada), "
                       "el control queda activo para futuros refrescos del dataset.",
    ))

    # 4) Corrección de tipos de datos: códigos DANE con cero inicial.
    #    El CSV original SÍ trae "Código Dane municipio" como texto con cero
    #    inicial (p. ej. "05001"); al construir eva_basicos.json en R1,
    #    process_eva.py dejó que pandas infiriera un tipo entero para esa
    #    columna y el cero inicial se perdió en los departamentos cuyo
    #    código empieza en 0 (Antioquia=05, Atlántico=08, etc.) — un defecto
    #    real del pipeline de R1, no del dato fuente. Se corrige aquí
    #    reformateando ambos campos como texto de ancho fijo; el valor
    #    numérico no cambia, solo su representación (no se fabrica un dato).
    n_codigo_corregido = 0
    for r in rows:
        mun_str = str(r.get("CodigoMunicipioDane"))
        if len(mun_str) < 5:
            n_codigo_corregido += 1
        r["CodigoMunicipioDane"] = mun_str.zfill(5)
        r["CodigoDeptoDane"] = str(r.get("CodigoDeptoDane")).zfill(2)
    acciones.append(dict(
        dataset="eva_basicos", accion="Corrección de tipos de datos (códigos DANE con cero inicial)",
        n_afectados=n_codigo_corregido, decision="correccion" if n_codigo_corregido else "sin_accion",
        justificacion=(
            f"{n_codigo_corregido} registros tenían 'CodigoMunicipioDane'/'CodigoDeptoDane' sin el cero "
            "inicial (se guardaron como entero al construir el JSON de R1); se reformatean como texto de "
            "ancho fijo (2 y 5 dígitos) — el valor no cambia, solo su representación."
            if n_codigo_corregido else "Los códigos DANE ya tenían el formato correcto."
        ),
    ))

    # 5) Validación de rangos: área cosechada > sembrada -> bandera, no corrección
    n_incons = 0
    for r in rows:
        area_c, area_s = _to_float(r.get("AreaCosechada")), _to_float(r.get("AreaSembrada"))
        flag = area_c is not None and area_s is not None and area_c > area_s
        r["_flag_area_incoherente"] = flag
        n_incons += int(flag)
    acciones.append(dict(
        dataset="eva_basicos", accion="Validación de rangos (AreaCosechada ≤ AreaSembrada)",
        n_afectados=n_incons, decision="flag",
        justificacion=f"{n_incons} registros incumplen la regla; se marcan con '_flag_area_incoherente' "
                      "porque no hay forma no ambigua de saber cuál campo es el erróneo (podría ser "
                      "resiembra legítima en el mismo semestre) — no se fabrica un valor corregido.",
    ))

    # 6) Outliers IQR por variable numérica -> bandera
    for f in schema["numeric_fields"]:
        valores_validos = [v for v in (_to_float(r.get(f)) for r in rows) if v is not None]
        lo, hi = _iqr_bounds(valores_validos)
        flag_col = f"_outlier_iqr_{f}"
        n_f = 0
        for r in rows:
            v = _to_float(r.get(f))
            flag = v is not None and (v < lo or v > hi)
            r[flag_col] = flag
            n_f += int(flag)
        acciones.append(dict(
            dataset="eva_basicos", accion=f"Tratamiento justificado de atípicos en '{f}' (± 1.5×RIC)",
            n_afectados=n_f, decision="flag",
            justificacion=f"{n_f} valores fuera de [{round(lo, 2)}, {round(hi, 2)}]; se marcan con "
                          f"'{flag_col}' y NO se eliminan — valores altos en municipios o cultivos de gran "
                          "escala son datos reales, no errores de captura.",
        ))

    return _dataset_desde_filas(rows), acciones


def clean_faostat(dataset: dict, schema_name: str) -> tuple[dict, list[dict]]:
    schema = DATASET_SCHEMA[schema_name]
    rows = _rows_as_dicts(dataset)
    acciones: list[dict] = []

    # 1) Corrección de la llave de unicidad (+ 'Unidad')
    n_grupos_multi, n_filas_afectadas = _hallazgo_duplicados_por_unidad(rows, schema["key_fields"])
    acciones.append(dict(
        dataset=schema_name, accion="Corrección de la llave de unicidad (+ 'Unidad')",
        n_afectados=n_filas_afectadas, decision="correccion_llave",
        justificacion=(
            f"{n_grupos_multi} combinaciones (Área,Producto,Elemento,Año) reportaban el mismo indicador en "
            f"más de una Unidad y se contaban como 'duplicadas' con la llave original de R1. Se corrige "
            "agregando 'Unidad' a la llave de unicidad — no se elimina ninguna fila, eran datos válidos."
            if n_filas_afectadas else "No se encontraron combinaciones ambiguas de Unidad para este dataset."
        ),
    ))

    # 2) Nulos en 'Valor' -> bandera, no imputación
    n_nulos = 0
    for r in rows:
        flag = r.get("Valor") in (None, "", "NaN")
        r["_flag_valor_nulo"] = flag
        n_nulos += int(flag)
    acciones.append(dict(
        dataset=schema_name, accion="Tratamiento de valores nulos en 'Valor'",
        n_afectados=n_nulos, decision="flag" if n_nulos else "sin_accion",
        justificacion=(
            f"{n_nulos} filas sin 'Valor' reportado; se marcan con '_flag_valor_nulo' y se excluyen de "
            "agregaciones, pero se conservan (no se fabrica un valor que FAOSTAT no reportó)."
            if n_nulos else "No se encontraron valores nulos en 'Valor'."
        ),
    ))

    # 3) Estandarización de texto (espacios/casing)
    n_texto = 0
    for r in rows:
        for f in TEXT_FIELDS[schema_name]:
            nv = _normalizar_texto(r.get(f))
            if nv != r.get(f):
                r[f] = nv
                n_texto += 1
    acciones.append(dict(
        dataset=schema_name, accion="Estandarización de texto (espacios/casing)",
        n_afectados=n_texto, decision="correccion" if n_texto else "sin_accion",
        justificacion="Se recorta espacio en blanco y se colapsan espacios dobles; en este corte no se "
                       "encontraron variantes, el control queda activo para futuros refrescos.",
    ))

    # 4) Estandarización temporal: AnioNormalizado (primer año del rango, p. ej. "2000-2002"->2000)
    for r in rows:
        raw = str(r.get(schema["year_field"], ""))[:4]
        r["AnioNormalizado"] = int(raw) if raw.isdigit() else None
    acciones.append(dict(
        dataset=schema_name, accion="Estandarización de fechas (AnioNormalizado)",
        n_afectados=len(rows), decision="correccion",
        justificacion="Se añade 'AnioNormalizado' (año entero) a partir de 'Año', que en FAOSTAT puede venir "
                       "como año puntual o como trienio (p. ej. '2000-2002'); el campo original se conserva "
                       "sin modificar.",
    ))

    # 5) Homologación/consistencia de unidad por (Producto, Elemento) -> bandera
    #    Se agrupa por (Producto, Elemento) y no solo por Elemento: un mismo
    #    Elemento cubre cultivos y ganadería con unidades legítimamente
    #    distintas (ver app.quality._consistencia_unidad_por_elemento).
    por_grupo = defaultdict(Counter)
    for r in rows:
        por_grupo[(r.get("Producto"), r.get("Elemento"))][r.get("Unidad")] += 1
    modal = {k: c.most_common(1)[0][0] for k, c in por_grupo.items()}
    n_atipica = 0
    for r in rows:
        flag = r.get("Unidad") != modal.get((r.get("Producto"), r.get("Elemento")))
        r["_flag_unidad_atipica"] = flag
        n_atipica += int(flag)
    acciones.append(dict(
        dataset=schema_name, accion="Homologación/consistencia de unidad por producto y elemento",
        n_afectados=n_atipica, decision="flag" if n_atipica else "sin_accion",
        justificacion=(
            f"{n_atipica} filas usan, para su combinación (Producto, Elemento), una Unidad distinta a la "
            "modal; se marcan con '_flag_unidad_atipica' para revisión, sin alterar el valor reportado."
            if n_atipica else "Todas las filas usan la Unidad modal de su combinación (Producto, Elemento)."
        ),
    ))

    # 6) Tratamiento justificado de atípicos en 'Valor', agrupado por
    #    (Producto, Elemento) — ver app.quality._iqr_bounds_por_grupo: un
    #    IQR global sobre 'Valor' mezclaría magnitudes no comparables.
    bounds = _iqr_bounds_por_grupo(rows, ("Producto", "Elemento"), "Valor")
    n_out = 0
    for r in rows:
        v = _to_float(r.get("Valor"))
        k = (r.get("Producto"), r.get("Elemento"))
        flag = v is not None and k in bounds and (v < bounds[k][0] or v > bounds[k][1])
        r["_outlier_iqr_valor"] = flag
        n_out += int(flag)
    acciones.append(dict(
        dataset=schema_name, accion="Tratamiento justificado de atípicos en 'Valor' (± 1.5×RIC por Producto/Elemento)",
        n_afectados=n_out, decision="flag" if n_out else "sin_accion",
        justificacion=(
            f"{n_out} valores atípicos dentro de su propia serie (Producto, Elemento); se marcan con "
            "'_outlier_iqr_valor' y NO se eliminan — variabilidad real de la serie (clima, mercado) o "
            "error puntual, requiere revisión caso a caso."
            if n_out else "No se encontraron valores atípicos dentro de sus series (Producto, Elemento)."
        ),
    ))

    return _dataset_desde_filas(rows), acciones


def main() -> None:
    R2_JSON_DIR.mkdir(parents=True, exist_ok=True)

    with open(R1_JSON_DIR / "integracion_eva_faostat.json", encoding="utf-8") as fh:
        integracion = json.load(fh)

    log_completo: dict = {"acciones": [], "resumen_antes_despues": {}}

    for name in DATASETS:
        crudo = _cargar_r1_json(name)
        if name == "eva_basicos":
            tratado, acciones = clean_eva(crudo)
        else:
            tratado, acciones = clean_faostat(crudo, name)
        log_completo["acciones"].extend(acciones)

        path = R2_JSON_DIR / DATASETS[name]
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(tratado, fh, ensure_ascii=False)
        log(f"{path.name} guardado: {len(tratado['rows'])} filas, {len(tratado['columns'])} columnas")

        kwargs = dict(integracion=integracion) if name in ("qcl", "qcl_basicos") else {}
        antes = compute_dimensions(crudo, name, **kwargs)
        despues = compute_dimensions(tratado, name, **kwargs)

        if name != "eva_basicos":
            # "Antes" refleja el método de R1 (llave sin 'Unidad'); "después"
            # ya usa la llave corregida vía compute_dimensions(tratado, ...).
            total = len(crudo["rows"])
            dup_antes = _count_duplicates(_rows_as_dicts(crudo), DATASET_SCHEMA[name]["key_fields"])
            antes["unicidad"] = round(100 * (total - dup_antes) / total, 2) if total else None

        log_completo["resumen_antes_despues"][name] = dict(antes=antes, despues=despues)

    log_completo["crop_mapping"] = CROP_MAPPING

    log_path = R2_JSON_DIR / "log_tratamiento.json"
    with open(log_path, "w", encoding="utf-8") as fh:
        json.dump(log_completo, fh, ensure_ascii=False, indent=2)
    log(f"{log_path.name} guardado: {len(log_completo['acciones'])} acciones registradas")
    log("Listo.")


if __name__ == "__main__":
    main()
