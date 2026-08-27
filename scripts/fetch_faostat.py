"""Descarga reproducible de datos FAOSTAT para Colombia.

Uso:
    python scripts/fetch_faostat.py

Requiere la variable de entorno FAOSTAT_TOKEN (token JWT del Portal para
Desarrolladores de FAOSTAT, https://faostatservices.fao.org). El token
caduca a los 60 minutos: nunca se escribe en el código, solo se lee desde
el entorno (.env).

Este script:
1. Autentica contra la API de FAOSTAT.
2. Descarga los datasets FS (seguridad alimentaria) y QCL (cultivos y
   ganadería) filtrados solo para Colombia (área FAO = 44).
3. Filtra un subconjunto de cultivos básicos de la canasta alimentaria.
4. Guarda el CSV original (sin modificar) en app/data/ y un JSON liviano
   en app/static/data/R1/ para el explorador y los gráficos del sitio.

Cumple el principio de trazabilidad: cualquier persona con su propio
token puede volver a ejecutar este script y obtener los mismos datos.
"""
from __future__ import annotations

import csv
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "app" / "data"
R1_JSON_DIR = BASE_DIR / "app" / "static" / "data" / "R1"

AREA_COLOMBIA = "44"
YEARS = range(2000, 2025)

CULTIVOS_BASICOS = [
    "Maíz", "Arroz", "Papas, patatas", "Plátanos (Verde) y bananos para cocinar",
    "Yuca, fresca", "Frijoles, secos",
]


def log(msg: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
    print(f"[{ts}] {msg}")


def get_client():
    """Crea el cliente de FAOSTAT autenticado con el token del entorno."""
    try:
        import faostat
    except ImportError:
        sys.exit(
            "Falta la librería 'faostat'. Instala las dependencias con:\n"
            "    pip install -r requirements.txt"
        )

    token = os.environ.get("FAOSTAT_TOKEN")
    if not token:
        sys.exit(
            "No se encontró FAOSTAT_TOKEN en el entorno. Copia .env.example a .env "
            "y agrega tu token del Portal para Desarrolladores de FAOSTAT."
        )
    faostat.set_requests_args(token=token, lang="es")
    return faostat


def save_csv(df, filename: str) -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = DATA_DIR / filename
    df.to_csv(path, index=False, encoding="utf-8")
    log(f"CSV guardado: {path} ({len(df)} filas)")
    return path


def save_table_json(df, filename: str) -> Path:
    R1_JSON_DIR.mkdir(parents=True, exist_ok=True)
    path = R1_JSON_DIR / filename
    payload = {"columns": list(df.columns), "rows": df.values.tolist()}
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False)
    log(f"JSON guardado: {path} ({len(df)} filas)")
    return path


def build_fs_chart_json(fs_df, filename: str = "faostat_fs_colombia.json") -> None:
    """Construye el JSON liviano {labels, datasets} que consume Chart.js."""
    import pandas as pd

    indicadores = {
        "Prevalencia de la subalimentación (%) (promedio de 3 años)": "Subalimentación (%)",
        "Prevalencia de la inseguridad alimentaria moderada o grave en la población total (%) (promedio de 3 años)": "Inseguridad alimentaria moderada o grave (%)",
    }
    sub = fs_df[fs_df["Producto"].isin(indicadores.keys())].copy()
    sub["anio_inicio"] = sub["Año"].astype(str).str.slice(0, 4)
    years = sorted(sub["anio_inicio"].unique())

    datasets = []
    for producto, label in indicadores.items():
        serie = sub[sub["Producto"] == producto].set_index("anio_inicio")["Valor"]
        data = [
            (float(serie[y]) if y in serie.index and str(serie[y]) not in ("nan", "") else None)
            for y in years
        ]
        datasets.append({"label": label, "data": data})

    payload = {"labels": [int(y) for y in years], "datasets": datasets}
    path = R1_JSON_DIR / filename
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False)
    log(f"JSON de gráfico guardado: {path}")


def main() -> None:
    faostat = get_client()
    import pandas as pd  # noqa: F401  (asegura dependencia declarada)

    log("Descargando dataset FS (seguridad alimentaria) para Colombia…")
    fs = faostat.get_data_df("FS", pars={"area": AREA_COLOMBIA})
    save_csv(fs, "faostat_fs_colombia.csv")
    save_table_json(fs, "fs.json")
    build_fs_chart_json(fs)

    log("Descargando dataset QCL (cultivos y ganadería) para Colombia…")
    qcl = faostat.get_data_df("QCL", pars={"area": AREA_COLOMBIA, "year": list(YEARS)})
    save_csv(qcl, "faostat_qcl_colombia.csv")
    save_table_json(qcl, "qcl.json")

    log("Filtrando cultivos básicos de la canasta alimentaria…")
    qcl_basicos = qcl[qcl["Producto"].isin(CULTIVOS_BASICOS)].copy()
    save_csv(qcl_basicos, "faostat_qcl_basicos_colombia.csv")
    save_table_json(qcl_basicos, "qcl_basicos.json")

    log("Listo. Ejecuta 'python scripts/rebuild_chart.py' si solo necesitas "
        "regenerar los JSON del sitio a partir de los CSV ya descargados.")


if __name__ == "__main__":
    main()
