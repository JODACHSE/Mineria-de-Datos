"""R1 · EVA crudo -> JSON de la app, sin alterar el CSV original.

Uso: python scripts/process_eva.py
Entrada: app/data/eva_basicos_colombia.csv · Salida: app/static/data/R1/eva_basicos.json
y integracion_eva_faostat.json (EVA nacional por cultivo y año frente a FAOSTAT).

Solo convierte el formato numérico colombiano ("1.499,40" -> 1499.4) y renombra
columnas; no elimina ni imputa filas (eso es R2).
"""
from __future__ import annotations

import json
from pathlib import Path

import sys

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.quality import CROP_MAPPING  # noqa: E402

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


def log(msg: str) -> None:
    print(f"[process_eva] {msg}")


def parse_co_number(series: pd.Series) -> pd.Series:
    """'1.499,40' -> 1499.40"""
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

    payload = {"columns": list(merged.columns), "rows": merged.where(pd.notnull(merged), None).to_numpy().tolist()}
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
