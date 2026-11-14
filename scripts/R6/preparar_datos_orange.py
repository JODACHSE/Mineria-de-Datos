"""R6 · Prepara los CSV de Orange desde el EVA tratado de R2.

Uso: python scripts/R6/preparar_datos_orange.py
Salida (orange/data/): eva_supervisado*.csv (clase alto/bajo y partición 2019–2023 / 2024),
eva_municipios.csv (clustering) y log_preparacion.json.
Los CSV llevan la cabecera de 3 filas de Orange (nombre / tipo / rol).
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "app" / "static" / "data" / "R2" / "eva_basicos.json"
OUT = ROOT / "orange" / "data"

# Departamento -> región (el mismo mapeo de etapa4.py).
REGION = {
    **dict.fromkeys(["Antioquia", "Boyacá", "Caldas", "Cundinamarca", "Huila", "Nariño",
                     "Norte de Santander", "Quindío", "Risaralda", "Santander", "Tolima"], "Andina"),
    **dict.fromkeys(["Atlántico", "Bolívar", "Cesar", "Córdoba", "La Guajira", "Magdalena", "Sucre",
                     "Archipiélago de San Andrés, Providencia y Santa Catalina"], "Caribe"),
    **dict.fromkeys(["Arauca", "Casanare", "Meta", "Vichada"], "Orinoquía"),
    **dict.fromkeys(["Amazonas", "Caquetá", "Guainía", "Guaviare", "Putumayo", "Vaupés"], "Amazonía"),
    **dict.fromkeys(["Cauca", "Chocó", "Valle del Cauca"], "Pacífica"),
}
CULTIVOS = ["Arroz", "Frijol", "Maíz", "Papa", "Plátano", "Yuca"]
ANIO_CORTE = 2023  # El umbral alto/bajo se calcula con 2019–2023; 2024 queda para la prueba.

LOG: list[dict] = []


def paso(nombre: str, antes: int, despues: int, motivo: str) -> None:
    LOG.append({"paso": nombre, "antes": antes, "despues": despues,
                "descartados": antes - despues, "motivo": motivo})


def escribir_orange(df: pd.DataFrame, tipos: dict[str, str], roles: dict[str, str], ruta: Path) -> None:
    """CSV con cabecera de 3 filas: nombres, tipos (c/d/s) y roles (class/meta)."""
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with ruta.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(df.columns)
        w.writerow([tipos[c] for c in df.columns])
        w.writerow([roles.get(c, "") for c in df.columns])
        for fila in df.itertuples(index=False):
            w.writerow(["" if (isinstance(v, float) and np.isnan(v)) else v for v in fila])


def cargar() -> pd.DataFrame:
    raw = json.loads(SRC.read_text(encoding="utf-8"))
    df = pd.DataFrame(raw["rows"], columns=raw["columns"])
    df["Region"] = df["Departamento"].map(REGION).fillna("Otra")
    df["Semestre"] = df["Periodo"].astype(str).str[-1].where(df["Periodo"].astype(str).str[-1].isin(["A", "B"]), "Anual")
    return df


# --- 1) Supervisado ---
def supervisado(df: pd.DataFrame) -> dict:
    n0 = len(df)
    d = df[(df.AreaCosechada > 0) & (df.Produccion > 0) & (df.Rendimiento > 0)]
    paso("Excluir registros sin cosecha", n0, len(d),
         "AreaCosechada, Produccion y Rendimiento son 0 (respuesta negativa): el rendimiento no está definido.")
    n1 = len(d)
    d = d[~d["_flag_area_incoherente"]].copy()
    paso("Excluir área incoherente", n1, len(d),
         "AreaCosechada > AreaSembrada (bandera de R2): AreaSembrada, usada como predictor, no es confiable.")

    umbral = d[d.Anio <= ANIO_CORTE].groupby("Cultivo")["Rendimiento"].median()
    d["RendimientoAlto"] = np.where(d["Rendimiento"] > d["Cultivo"].map(umbral), "Alto", "Bajo")
    d["Log10_AreaSembrada"] = np.log10(d["AreaSembrada"]).round(4)

    # GrupoCV: 10 grupos de municipios completos para la validación «por municipio». Es meta.
    munis = np.array(sorted(d["CodigoMunicipioDane"].unique()))
    np.random.default_rng(42).shuffle(munis)
    grupo = {m: f"G{i % 10}" for i, m in enumerate(munis)}
    d["GrupoCV"] = d["CodigoMunicipioDane"].map(grupo)

    cols = ["CodMunicipio", "Municipio", "GrupoCV", "Cultivo", "DesagregacionCultivo", "Region", "Departamento",
            "Anio", "Semestre", "Log10_AreaSembrada", "RendimientoAlto"]
    out = d.rename(columns={"CodigoMunicipioDane": "CodMunicipio"})[cols]
    tipos = {"CodMunicipio": "s", "Municipio": "s", "GrupoCV": "d", "Cultivo": "d", "DesagregacionCultivo": "d", "Region": "d",
             "Departamento": "d", "Anio": "c", "Semestre": "d", "Log10_AreaSembrada": "c", "RendimientoAlto": "d"}
    roles = {"CodMunicipio": "meta", "Municipio": "meta", "GrupoCV": "meta", "Anio": "meta",
             "RendimientoAlto": "class"}  # Anio es meta: sirve para partir, no para predecir.
    escribir_orange(out, tipos, roles, OUT / "eva_supervisado.csv")
    # Partición temporal: entrenar con el pasado y probar con 2024.
    escribir_orange(out[out.Anio <= ANIO_CORTE], tipos, roles, OUT / "eva_supervisado_entrenamiento_2019_2023.csv")
    escribir_orange(out[out.Anio > ANIO_CORTE], tipos, roles, OUT / "eva_supervisado_prueba_2024.csv")

    bal = out["RendimientoAlto"].value_counts().to_dict()
    return {
        "registros": len(out), "clase": bal,
        "pct_alto": round(100 * bal.get("Alto", 0) / len(out), 2),
        "umbral_t_ha_por_cultivo_2019_2023": {k: round(float(v), 3) for k, v in umbral.items()},
        "registros_2019_2023": int((out.Anio <= ANIO_CORTE).sum()), "registros_2024": int((out.Anio > ANIO_CORTE).sum()),
        "predictoras": [c for c in cols if c not in ("CodMunicipio", "Municipio", "GrupoCV", "Anio", "RendimientoAlto")],
        "excluidas_por_fuga": ["Produccion", "AreaCosechada", "Rendimiento", "_flag_*", "_outlier_iqr_*"],
    }


# --- 2) Clustering: una fila por municipio, sin variables de rendimiento ---
def municipios(df: pd.DataFrame) -> dict:
    n_muni0 = df["CodigoMunicipioDane"].nunique()
    d = df[df.AreaSembrada > 0]
    paso("Municipios con área sembrada > 0", n_muni0, d["CodigoMunicipioDane"].nunique(),
         "Para medir tamaño y mezcla de cultivos se necesita área sembrada positiva.")

    g = d.groupby("CodigoMunicipioDane")
    anual = d.groupby(["CodigoMunicipioDane", "Anio"])["AreaSembrada"].sum().groupby(level=0).mean()
    area_cultivo = d.pivot_table(index="CodigoMunicipioDane", columns="Cultivo", values="AreaSembrada",
                                 aggfunc="sum", fill_value=0).reindex(columns=CULTIVOS, fill_value=0)
    share = area_cultivo.div(area_cultivo.sum(axis=1), axis=0)

    ok = d[~d["_flag_area_incoherente"]].groupby("CodigoMunicipioDane")
    tasa = (ok["AreaCosechada"].sum() / ok["AreaSembrada"].sum()).clip(upper=1.0)

    t = pd.DataFrame({
        "Log10_AreaSembradaAnual": np.log10(anual).round(4),
        "NumCultivos": g["Cultivo"].nunique(),
        "Diversificacion": (1 - (share ** 2).sum(axis=1)).round(4),  # 1 − Herfindahl (0 = monocultivo).
        **{f"PctArea_{c}": (share[c] * 100).round(2) for c in CULTIVOS},
        "TasaCosecha": tasa.round(4),
    })
    antes = len(t)
    t = t.dropna(subset=["TasaCosecha"])
    paso("Municipios con tasa de cosecha calculable", antes, len(t),
         "Sin registros de área coherente no se puede estimar cosechada/sembrada.")

    # Solo para describir los grupos (meta: no entran al k-Means).
    base = d.drop_duplicates("CodigoMunicipioDane").set_index("CodigoMunicipioDane")
    mediana = df[(df.AreaCosechada > 0) & (df.Rendimiento > 0)].groupby("Cultivo")["Rendimiento"].median()
    v = df[(df.AreaCosechada > 0) & (df.Rendimiento > 0)].copy()
    v["RendRel"] = v["Rendimiento"] / v["Cultivo"].map(mediana)
    rend_rel = v.groupby("CodigoMunicipioDane")["RendRel"].median()

    t["Municipio"] = base["Municipio"]
    t["Departamento"] = base["Departamento"]
    t["Region"] = base["Departamento"].map(REGION).fillna("Otra")
    t["NumRegistros"] = g.size()
    t["RendRelMediano_posteriori"] = rend_rel.round(4)
    t = t.reset_index().rename(columns={"CodigoMunicipioDane": "CodMunicipio"})

    feats = ["Log10_AreaSembradaAnual", "NumCultivos", "Diversificacion",
             *[f"PctArea_{c}" for c in CULTIVOS], "TasaCosecha"]
    cols = ["CodMunicipio", "Municipio", "Departamento", "Region", *feats, "NumRegistros", "RendRelMediano_posteriori"]
    t = t[cols]
    tipos = {c: "c" for c in cols}
    tipos.update({"CodMunicipio": "s", "Municipio": "s", "Departamento": "d", "Region": "d"})
    roles = {c: "meta" for c in ["CodMunicipio", "Municipio", "Departamento", "Region",
                                 "NumRegistros", "RendRelMediano_posteriori"]}
    escribir_orange(t, tipos, roles, OUT / "eva_municipios.csv")
    return {"municipios": len(t), "variables_clustering": feats,
            "metas_posteriori": ["Municipio", "Departamento", "Region", "NumRegistros", "RendRelMediano_posteriori"]}


def main() -> None:
    df = cargar()
    res = {"fuente": str(SRC.relative_to(ROOT)), "registros_fuente": len(df)}
    res["supervisado"] = supervisado(df)
    res["clustering"] = municipios(df)
    res["pasos"] = LOG
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "log_preparacion.json").write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(res, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
