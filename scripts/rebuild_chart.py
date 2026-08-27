"""Reconstruye los archivos JSON de app/static/data/R1/ a partir de los CSV
originales en app/data/, sin volver a llamar a la API de FAOSTAT.

Útil cuando solo se necesita regenerar el explorador o el gráfico del
sitio (por ejemplo, después de editar manualmente un CSV) sin gastar una
nueva consulta a la API.

Uso:
    python scripts/rebuild_chart.py
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "app" / "data"
R1_JSON_DIR = BASE_DIR / "app" / "static" / "data" / "R1"

CSV_TO_JSON = {
    "faostat_fs_colombia.csv": "fs.json",
    "faostat_qcl_colombia.csv": "qcl.json",
    "faostat_qcl_basicos_colombia.csv": "qcl_basicos.json",
}

INDICADORES_CHART = {
    "Prevalencia de la subalimentación (%) (promedio de 3 años)": "Subalimentación (%)",
    "Prevalencia de la inseguridad alimentaria moderada o grave en la población total (%) (promedio de 3 años)": "Inseguridad alimentaria moderada o grave (%)",
}


def log(msg: str) -> None:
    print(f"[rebuild_chart] {msg}")


def df_to_json_table(df: pd.DataFrame, path: Path) -> None:
    payload = {"columns": list(df.columns), "rows": df.where(pd.notnull(df), None).values.tolist()}
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False)
    log(f"{path.name}: {len(df)} filas")


def build_fs_chart(fs_df: pd.DataFrame) -> None:
    sub = fs_df[fs_df["Producto"].isin(INDICADORES_CHART.keys())].copy()
    sub["anio_inicio"] = sub["Año"].astype(str).str.slice(0, 4)
    years = sorted(sub["anio_inicio"].unique())

    datasets = []
    for producto, label in INDICADORES_CHART.items():
        serie = sub[sub["Producto"] == producto].set_index("anio_inicio")["Valor"]
        data = []
        for y in years:
            if y in serie.index and pd.notnull(serie[y]):
                data.append(float(serie[y]))
            else:
                data.append(None)
        datasets.append({"label": label, "data": data})

    payload = {"labels": [int(y) for y in years], "datasets": datasets}
    path = R1_JSON_DIR / "faostat_fs_colombia.json"
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False)
    log(f"{path.name} regenerado")


def main() -> None:
    R1_JSON_DIR.mkdir(parents=True, exist_ok=True)
    fs_df = None
    for csv_name, json_name in CSV_TO_JSON.items():
        csv_path = DATA_DIR / csv_name
        if not csv_path.exists():
            log(f"AVISO: no se encontró {csv_path}, se omite.")
            continue
        df = pd.read_csv(csv_path)
        df_to_json_table(df, R1_JSON_DIR / json_name)
        if csv_name == "faostat_fs_colombia.csv":
            fs_df = df

    if fs_df is not None:
        build_fs_chart(fs_df)

    log("Listo.")


if __name__ == "__main__":
    main()
