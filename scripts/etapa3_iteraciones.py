"""Etapa 3 · Réplica en Python de las reglas de los paquetes SSIS (EVA.dtsx y FAOSTAT.dtsx).

Aplica sobre los CSV originales de `app/data/` exactamente las mismas reglas que
los Data Flow de limpieza de SSIS, iteración por iteración, y guarda los conteos,
indicadores y ejemplos en `app/static/data/R3/iteraciones.json`.

Sirve para dos cosas:
  1. Publicar en la app los resultados de las tres iteraciones (sección Etapa 3).
  2. Contrastar contra la ejecución real de SSIS: los conteos de las tablas
     *_Limpios y *_Revision de cada lote deben coincidir con los de este script.

Uso:
    python scripts/etapa3_iteraciones.py

Reglas por iteración (acumulativas):
  I1  EVA: duplicados (EVA-DUP), conversión numérica (EVA-CONV), municipio DIVIPOLA (EVA-MUN)
      FAO: duplicados (FAO-DUP), conversión del valor (FAO-CNV)
  I2  + dominio negativo (EVA-DOM / FAO-DOM), área cosechada > sembrada (EVA-CONS),
        conversión final de textos/códigos (EVA-CONV / FAO-CNVF)
  I3  + banderas de atípicos IQR (por cultivo en EVA; por dataset + producto|elemento en FAOSTAT)
        + bandera de unidad distinta a la modal (FAOSTAT)
"""
from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DATA = BASE / "app" / "data"
OUT = BASE / "app" / "static" / "data" / "R3" / "iteraciones.json"

EVA_CSV = DATA / "eva_basicos_colombia.csv"
FAO_CSV = {
    "QCL": DATA / "faostat_qcl_colombia.csv",
    "QCLBasicos": DATA / "faostat_qcl_basicos_colombia.csv",
    "FS": DATA / "faostat_fs_colombia.csv",
}

EVA_COLS = ["CodigoDeptoDane", "Departamento", "CodigoMunicipioDane", "Municipio", "GrupoCultivo",
            "Subgrupo", "Cultivo", "DesagregacionCultivo", "Anio", "Periodo", "AreaSembrada",
            "AreaCosechada", "Produccion", "Rendimiento", "CicloCultivo", "EstadoFisico",
            "CodigoCultivo", "NombreCientifico"]
EVA_METRICAS = ["AreaSembrada", "AreaCosechada", "Produccion", "Rendimiento"]
FAO_COLS = ["CodigoAmbito", "Ambito", "CodigoArea", "Area", "CodigoElemento", "Elemento",
            "CodigoProducto", "Producto", "CodigoAnio", "Anio", "Unidad", "Valor"]

# Longitudes de CONV_Tipos_STR_CORTO (EVA) y CONV_CodigosCortos (FAOSTAT)
EVA_LONG_FINAL = {"CodigoMunicipioDane": 5, "Periodo": 5, "CodigoCultivo": 20, "GrupoCultivo": 100,
                  "Subgrupo": 100, "Cultivo": 60, "DesagregacionCultivo": 150, "CicloCultivo": 30,
                  "EstadoFisico": 50, "NombreCientifico": 150, "Municipio": 150}
FAO_LONG_FINAL = {"CodigoAmbito": 10, "CodigoArea": 10, "CodigoElemento": 10, "CodigoProducto": 20,
                  "CodigoAnio": 20}


# ------------------------------------------------------------------ utilidades
def dec(text: str | None) -> Decimal | None:
    if text is None or text == "":
        return None
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def eva_num(text: str) -> Decimal | None:
    """DER_LimpiezaTexto: REPLACE(REPLACE(TRIM(x),".",""),",",".") y luego DT_NUMERIC."""
    return dec(text.strip().replace(".", "").replace(",", "."))


def percentile_cont(values: list[Decimal], p: float) -> float:
    """Igual a PERCENTILE_CONT de SQL Server (interpolación lineal)."""
    v = sorted(float(x) for x in values)
    if not v:
        return None
    pos = p * (len(v) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(v) - 1)
    return v[lo] + (v[hi] - v[lo]) * (pos - lo)


def iqr_limits(values):
    q1, q3 = percentile_cont(values, 0.25), percentile_cont(values, 0.75)
    if q1 is None:
        return None
    r = q3 - q1
    return q1 - 1.5 * r, q3 + 1.5 * r


def pct(a, b):
    return round(100 * a / b, 2) if b else None


def fits_1252(text: str) -> bool:
    try:
        text.encode("cp1252")
        return True
    except UnicodeEncodeError:
        return False


# ------------------------------------------------------------------ EVA
def load_eva():
    with open(EVA_CSV, encoding="utf-8") as fh:
        rd = csv.reader(fh)
        next(rd)
        rows = []
        for i, r in enumerate(rd, start=1):
            d = dict(zip(EVA_COLS, r))
            d["IdStg"] = i
            rows.append(d)
    return rows


def run_eva(rows, iteracion: int) -> dict:
    n = len(rows)
    # límites IQR por cultivo (SQL_CalcularLimitesIQR, sobre todo el staging del lote)
    limites = {}
    if iteracion >= 3:
        por_cultivo = defaultdict(lambda: defaultdict(list))
        for r in rows:
            for m in EVA_METRICAS:
                v = eva_num(r[m])
                if v is not None:
                    por_cultivo[r["Cultivo"].strip()][m].append(v)
        limites = {(c, m): iqr_limits(vals) for c, ms in por_cultivo.items() for m, vals in ms.items()}

    # duplicados (SRC_stg_EVA + CSPL_Duplicados)
    key = lambda r: (r["CodigoMunicipioDane"].strip(), r["CodigoCultivo"].strip(),
                     r["DesagregacionCultivo"].strip(), r["Anio"].strip(), r["Periodo"].strip())
    visto = Counter()
    revision = Counter()
    ejemplos_rev = {}
    aceptados = []
    flags = Counter()
    for r in rows:
        k = key(r)
        visto[k] += 1
        if visto[k] > 1:
            revision["EVA-DUP"] += 1
            ejemplos_rev.setdefault("EVA-DUP", r)
            continue
        nums = {m: eva_num(r[m]) for m in EVA_METRICAS}
        anio_ok = r["Anio"].strip().isdigit()
        if any(v is None for v in nums.values()) or not anio_ok:
            revision["EVA-CONV"] += 1
            ejemplos_rev.setdefault("EVA-CONV", r)
            continue
        cod = r["CodigoMunicipioDane"].strip()
        if not (len(cod) == 5 and cod.isdigit() and cod.startswith(r["CodigoDeptoDane"].strip())):
            revision["EVA-MUN"] += 1
            ejemplos_rev.setdefault("EVA-MUN", r)
            continue
        if iteracion >= 2:
            if any(v < 0 for v in nums.values()):
                revision["EVA-DOM"] += 1
                ejemplos_rev.setdefault("EVA-DOM", r)
                continue
            if nums["AreaCosechada"] > nums["AreaSembrada"]:
                revision["EVA-CONS"] += 1
                ejemplos_rev.setdefault("EVA-CONS", r)
                continue
            if any(len(r[c].strip()) > L for c, L in EVA_LONG_FINAL.items()) or not all(
                    fits_1252(r[c]) for c in ("CodigoMunicipioDane", "Periodo", "CodigoCultivo")):
                revision["EVA-CONVF"] += 1
                continue
        if iteracion >= 3:
            alguno = False
            for m in EVA_METRICAS:
                lim = limites.get((r["Cultivo"].strip(), m))
                if lim and (float(nums[m]) < lim[0] or float(nums[m]) > lim[1]):
                    flags[m] += 1
                    alguno = True
            if alguno:
                flags["alguna"] += 1
        aceptados.append(r)

    total_rev = sum(revision.values())
    return dict(
        recibidos=n, aceptados=len(aceptados), revision=dict(revision), total_revision=total_rev,
        sin_explicar=n - len(aceptados) - total_rev,
        atipicos=dict(flags) if iteracion >= 3 else None,
        ejemplo_consistencia=_eva_ej(ejemplos_rev.get("EVA-CONS")),
    )


def _eva_ej(r):
    if not r:
        return None
    return {k: r[k] for k in ("IdStg", "Departamento", "Municipio", "CodigoMunicipioDane", "Cultivo", "Periodo",
                              "AreaSembrada", "AreaCosechada")}


def eva_original(rows):
    n = len(rows)
    key = Counter((r["CodigoMunicipioDane"].strip(), r["CodigoCultivo"].strip(), r["DesagregacionCultivo"].strip(),
                   r["Anio"].strip(), r["Periodo"].strip()) for r in rows)
    dup = sum(v - 1 for v in key.values() if v > 1)
    conv_ok = sum(1 for r in rows if all(eva_num(r[m]) is not None for m in EVA_METRICAS))
    vacias = sum(1 for r in rows if any(r[m].strip() == "" for m in EVA_METRICAS))
    neg = sum(1 for r in rows if any((eva_num(r[m]) or 0) < 0 for m in EVA_METRICAS))
    inc = sum(1 for r in rows if (eva_num(r["AreaCosechada"]) or 0) > (eva_num(r["AreaSembrada"]) or 0))
    formato_miles = sum(1 for r in rows if any("," in r[m] for m in EVA_METRICAS))
    as_cero = sum(1 for r in rows if eva_num(r["AreaSembrada"]) == 0)
    return dict(recibidos=n, duplicados=dup, convertibles=conv_ok, vacias=vacias, negativos=neg,
                area_incoherente=inc, formato_coma=formato_miles, area_sembrada_cero=as_cero,
                municipios=len({r["CodigoMunicipioDane"] for r in rows}),
                departamentos=len({r["CodigoDeptoDane"] for r in rows}))


def eva_ejemplos(rows):
    """Un dato corregido real (formato numérico) y uno enviado a revisión (EVA-CONS)."""
    corregido = next(r for r in rows if "." in r["Produccion"] and "," in r["Produccion"])
    return dict(
        corregido=dict(IdStg=corregido["IdStg"], campo="Produccion", original=corregido["Produccion"],
                       limpio=str(eva_num(corregido["Produccion"])), municipio=corregido["Municipio"],
                       cultivo=corregido["Cultivo"], periodo=corregido["Periodo"]),
    )


# ------------------------------------------------------------------ FAOSTAT
def load_fao():
    rows = []
    i = 0
    for ds, path in FAO_CSV.items():
        with open(path, encoding="utf-8") as fh:
            rd = csv.reader(fh)
            next(rd)
            for r in rd:
                i += 1
                d = {c: v.strip() for c, v in zip(FAO_COLS, r)}
                d["Dataset"] = ds
                d["IdStg"] = i
                d["ProductoLargo"] = len(d["Producto"]) > 50
                rows.append(d)
    return rows


def run_fao(rows, iteracion: int) -> dict:
    n = len(rows)
    limites, modal = {}, {}
    if iteracion >= 3:
        grupos = defaultdict(list)
        unidades = defaultdict(Counter)
        for r in rows:
            v = dec(r["Valor"])
            if v is not None:
                grupos[(r["Dataset"], r["CodigoProducto"] + "|" + r["CodigoElemento"])].append(v)
            unidades[(r["Dataset"], r["CodigoProducto"], r["CodigoElemento"])][r["Unidad"]] += 1
        limites = {k: iqr_limits(v) for k, v in grupos.items()}
        modal = {k: sorted(c.items(), key=lambda kv: (-kv[1], kv[0].lower()))[0][0] for k, c in unidades.items()}

    visto = Counter()
    revision = Counter()
    ejemplos = {}
    aceptados = 0
    nulos_aceptados = 0
    flags = Counter()
    for r in rows:
        k = (r["Dataset"], r["CodigoArea"], r["CodigoElemento"], r["CodigoProducto"], r["CodigoAnio"], r["Unidad"])
        visto[k] += 1
        if visto[k] > 1:
            revision["FAO-DUP"] += 1
            continue
        texto = r["Valor"] or None                      # NULLIF(LTRIM(RTRIM(Valor)), '')
        valor = dec(texto) if texto is not None else None
        if texto is not None and valor is None:
            revision["FAO-CNV"] += 1
            ejemplos.setdefault("FAO-CNV", r)
            continue
        if iteracion >= 2:
            if valor is not None and valor < 0:
                revision["FAO-DOM"] += 1
                continue
            if any(len(r[c]) > L or not fits_1252(r[c]) for c, L in FAO_LONG_FINAL.items()):
                revision["FAO-CNVF"] += 1
                continue
        if iteracion >= 3:
            lim = limites.get((r["Dataset"], r["CodigoProducto"] + "|" + r["CodigoElemento"]))
            if valor is not None and lim and (float(valor) < lim[0] or float(valor) > lim[1]):
                flags["valor"] += 1
            um = modal.get((r["Dataset"], r["CodigoProducto"], r["CodigoElemento"]))
            if um is not None and r["Unidad"] != um:
                flags["unidad"] += 1
        if valor is None:
            nulos_aceptados += 1
        aceptados += 1

    total_rev = sum(revision.values())
    return dict(
        recibidos=n, aceptados=aceptados, revision=dict(revision), total_revision=total_rev,
        sin_explicar=n - aceptados - total_rev, valor_nulo_aceptado=nulos_aceptados,
        atipicos=dict(flags) if iteracion >= 3 else None,
        por_dataset={ds: sum(1 for r in rows if r["Dataset"] == ds) for ds in FAO_CSV},
        ejemplo_conversion={k: ejemplos["FAO-CNV"][k] for k in ("IdStg", "Dataset", "Producto", "Anio", "Unidad", "Valor")}
        if "FAO-CNV" in ejemplos else None,
    )


def fao_original(rows):
    n = len(rows)
    key = Counter((r["Dataset"], r["CodigoArea"], r["CodigoElemento"], r["CodigoProducto"], r["CodigoAnio"], r["Unidad"])
                  for r in rows)
    key_sin_unidad = Counter((r["Dataset"], r["CodigoArea"], r["CodigoElemento"], r["CodigoProducto"], r["CodigoAnio"])
                             for r in rows)
    nulos = sum(1 for r in rows if r["Valor"] == "")
    conv = sum(1 for r in rows if r["Valor"] != "" and dec(r["Valor"]) is not None)
    neg = sum(1 for r in rows if (dec(r["Valor"]) or 0) < 0)
    unidades = defaultdict(set)
    for r in rows:
        unidades[(r["Dataset"], r["CodigoProducto"], r["CodigoElemento"])].add(r["Unidad"])
    grupos_multi = sum(1 for v in unidades.values() if len(v) > 1)
    grupos_valor = defaultdict(list)
    for r in rows:
        grupos_valor[(r["Dataset"], r["CodigoProducto"] + "|" + r["CodigoElemento"])].append(dec(r["Valor"]))
    grupos_sin_valor = [k for k, v in grupos_valor.items() if all(x is None for x in v)]
    return dict(
        recibidos=n, duplicados=sum(v - 1 for v in key.values() if v > 1),
        duplicados_sin_unidad=sum(v - 1 for v in key_sin_unidad.values() if v > 1),
        nulos=nulos, convertibles=conv, no_convertibles=n - nulos - conv, negativos=neg,
        anio_rango=sum(1 for r in rows if len(r["CodigoAnio"]) == 8),
        grupos_unidad_multiple=grupos_multi,
        producto_mayor_50=sum(1 for r in rows if r["ProductoLargo"]),
        producto_mayor_50_por_dataset=dict(Counter(r["Dataset"] for r in rows if r["ProductoLargo"])),
        grupos_iqr=len(grupos_valor), grupos_sin_valor=len(grupos_sin_valor),
        filas_grupos_sin_valor=sum(len(grupos_valor[k]) for k in grupos_sin_valor),
        por_dataset={ds: sum(1 for r in rows if r["Dataset"] == ds) for ds in FAO_CSV},
    )


# ------------------------------------------------------------------ main
def main():
    eva = load_eva()
    fao = load_fao()
    res = {
        "generado_por": "scripts/etapa3_iteraciones.py",
        "nota": "Réplica en Python de las reglas de EVA.dtsx y FAOSTAT.dtsx sobre los CSV originales. "
                "Los conteos deben coincidir con las tablas *_Limpios y *_Revision de cada lote en SSIS.",
        "eva": {"original": eva_original(eva), "ejemplos": eva_ejemplos(eva),
                "iteraciones": {f"I{i}": run_eva(eva, i) for i in (1, 2, 3)}},
        "faostat": {"original": fao_original(fao),
                    "iteraciones": {f"I{i}": run_fao(fao, i) for i in (1, 2, 3)}},
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
