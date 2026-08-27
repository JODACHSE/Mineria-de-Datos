"""Limpieza y trazabilidad del dataset EVA (producción municipal).

Uso:
    python scripts/process_eva.py

Este script documenta EXACTAMENTE qué transformaciones se aplicaron al
CSV crudo descargado de datos.gov.co (Evaluaciones Agropecuarias
Municipales – EVA, filtrado a 6 cultivos básicos), para cumplir con el
requisito de trazabilidad: el CSV original nunca se modifica en disco
(queda intacto en app/data/eva_basicos_colombia.csv); este script lee
ese archivo, transforma una copia en memoria y escribe los JSON que
consume la app en app/static/data/R1/.

Transformaciones aplicadas (y solo estas):
1. Conversión de formato numérico colombiano (punto = miles, coma =
   decimal, p. ej. "1.499,40") a float estándar, en las 4 columnas
   numéricas (Área sembrada, Área cosechada, Producción, Rendimiento).
2. Renombrado de columnas a identificadores cortos sin tildes/espacios
   (p. ej. "Código Dane municipio" -> "CodigoMunicipioDane"), manteniendo
   una correspondencia 1:1 documentada en el diccionario de datos de R1.
3. Ninguna fila se elimina ni se imputa: el diagnóstico de calidad (ver
   /r1#calidad) reporta los hallazgos reales (p. ej. área cosechada >
   área sembrada en algunos registros) sin "arreglarlos" todavía — eso
   corresponde a un entregable posterior de limpieza.

Además construye integracion_eva_faostat.json: agrega la producción de
EVA a escala nacional (suma por Cultivo + Año) y la cruza con la
producción nacional de FAOSTAT (QCL) para los mismos 6 cultivos y años,
usando esas dos variables como llave de integración.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
RAW_CSV = BASE_DIR / "app" / "data" / "eva_basicos_colombia.csv"
R1_JSON_DIR = BASE_DIR / "app" / "static" / "data" / "R1"

COLUMN_MAP = {
    "Código Dane departamento": "CodigoDeptoDane",
    "Departamento": "Departamento",
    "Código Dane municipio": "CodigoMunicipioDane",
    "Municipio": "Municipio",
    "Grupo cultivo": "GrupoCultivo",
    "Subgrupo": "Subgrupo",
    "Cultivo": "Cultivo",
    "Desagregación cultivo": "DesagregacionCultivo",
    "Año": "Anio",
    "Periodo": "Periodo",
    "Área sembrada": "AreaSembrada",
    "Área cosechada": "AreaCosechada",
    "Producción": "Produccion",
    "Rendimiento": "Rendimiento",
    "Ciclo del cultivo": "CicloCultivo",
    "Estado físico del cultivo": "EstadoFisico",
    "Código del cultivo": "CodigoCultivo",
    "Nombre científico del cultivo": "NombreCientifico",
}

NUMERIC_COLUMNS_RAW = ["Área sembrada", "Área cosechada", "Producción", "Rendimiento"]

# Cultivo EVA -> nombre exacto del Producto en FAOSTAT (para poder cruzar)
CROP_MAPPING = {
    "Maíz": "Maíz",
    "Arroz": "Arroz",
    "Papa": "Papas, patatas",
    "Plátano": "Plátanos (Verde) y bananos para cocinar",
    "Yuca": "Yuca, fresca",
    "Frijol": "Frijoles, secos",
}


def log(msg: str) -> None:
    print(f"[process_eva] {msg}")


def parse_co_number(series: pd.Series) -> pd.Series:
    """'1.499,40' (formato CO) -> 1499.40 (float)."""
    return pd.to_numeric(
        series.astype(str).str.replace(".", "", regex=False).str.replace(",", ".", regex=False),
        errors="coerce",
    )


def load_and_clean() -> pd.DataFrame:
    if not RAW_CSV.exists():
        raise SystemExit(
            f"No se encontró {RAW_CSV}. Coloca ahí el CSV exportado de "
            "datos.gov.co (Evaluaciones Agropecuarias Municipales – EVA, "
            "filtrado por cultivo) antes de correr este script."
        )
    df = pd.read_csv(RAW_CSV, encoding="utf-8")
    log(f"CSV crudo cargado: {len(df)} filas, {len(df.columns)} columnas")

    for col in NUMERIC_COLUMNS_RAW:
        df[col] = parse_co_number(df[col])

    df = df.rename(columns=COLUMN_MAP)
    log("Columnas convertidas a formato numérico estándar y renombradas")
    return df


def save_eva_json(df: pd.DataFrame) -> None:
    R1_JSON_DIR.mkdir(parents=True, exist_ok=True)
    payload = {"columns": list(df.columns), "rows": df.where(pd.notnull(df), None).values.tolist()}
    path = R1_JSON_DIR / "eva_basicos.json"
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False)
    log(f"{path.name} guardado: {len(df)} filas")


def build_integration_table(eva_df: pd.DataFrame) -> None:
    qcl_path = R1_JSON_DIR / "qcl.json"
    if not qcl_path.exists():
        log("AVISO: no se encontró qcl.json, se omite la tabla de integración.")
        return

    with open(qcl_path, encoding="utf-8") as fh:
        qcl = json.load(fh)
    qcl_df = pd.DataFrame(qcl["rows"], columns=qcl["columns"])

    eva_nat = eva_df.groupby(["Anio", "Cultivo"], as_index=False)["Produccion"].sum()
    eva_nat = eva_nat.rename(columns={"Produccion": "Produccion_EVA_t"})

    inv_mapping = {v: k for k, v in CROP_MAPPING.items()}
    qcl_prod = qcl_df[
        (qcl_df["Elemento"] == "Producción") & (qcl_df["Producto"].isin(CROP_MAPPING.values()))
    ].copy()
    qcl_prod["Cultivo"] = qcl_prod["Producto"].map(inv_mapping)
    qcl_prod["Anio"] = pd.to_numeric(qcl_prod["Año"].astype(str).str.slice(0, 4), errors="coerce")
    qcl_prod["Valor"] = pd.to_numeric(qcl_prod["Valor"], errors="coerce")
    qcl_nat = qcl_prod.groupby(["Anio", "Cultivo"], as_index=False)["Valor"].sum()
    qcl_nat = qcl_nat.rename(columns={"Valor": "Produccion_FAOSTAT_t"})

    merged = pd.merge(eva_nat, qcl_nat, on=["Anio", "Cultivo"], how="inner")
    merged["Diferencia_pct"] = (
        (merged["Produccion_EVA_t"] - merged["Produccion_FAOSTAT_t"]) / merged["Produccion_FAOSTAT_t"] * 100
    ).round(1)
    merged = merged.sort_values(["Cultivo", "Anio"])

    payload = {"columns": list(merged.columns), "rows": merged.where(pd.notnull(merged), None).values.tolist()}
    path = R1_JSON_DIR / "integracion_eva_faostat.json"
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False)
    log(f"{path.name} guardado: {len(merged)} filas de cruce EVA↔FAOSTAT")


def main() -> None:
    df = load_and_clean()
    save_eva_json(df)
    build_integration_table(df)
    log("Listo.")


if __name__ == "__main__":
    main()
