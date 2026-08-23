"""
fetch_faostat.py — Descarga reproducible de datos FAOSTAT para Colombia.

Bitácora técnica R1: en vez de descargar CSV a mano, este script deja registrado
EXACTAMENTE qué se pidió a FAOSTAT (dataset, país, indicadores, años), de modo que
cualquiera pueda reproducir la descarga.

Genera:
  app/data/faostat_fs_colombia.csv        -> seguridad alimentaria (dataset FS)
  app/data/faostat_qcl_colombia.csv       -> producción de cultivos básicos (dataset QCL)
  app/static/data/faostat_fs_colombia.json -> serie lista para el gráfico de la página R1

Requisitos:
  pip install faostat pandas
  Cuenta en el Portal para Desarrolladores de FAOSTAT (token o usuario/contraseña).

Uso:
  # opción A: token (caduca a los 60 min)
  export FAOSTAT_TOKEN="mi_token_jwt"
  python scripts/fetch_faostat.py

  # opción B: usuario/contraseña (recupera el token automáticamente)
  export FAOSTAT_USER="mi_usuario"
  export FAOSTAT_PASS="mi_clave"
  python scripts/fetch_faostat.py
"""

import os
import json
from pathlib import Path

import faostat
import pandas as pd

# --- Rutas de salida --------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent          # .../Mineria-de-Datos-main
DATA_DIR = ROOT / "app" / "data"
STATIC_DATA_DIR = ROOT / "app" / "static" / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
STATIC_DATA_DIR.mkdir(parents=True, exist_ok=True)

# --- Parámetros de la consulta (documentados para trazabilidad) -------------
# (el codigo de area se resuelve por nombre con resolve_area_code)
YEARS = list(range(2000, 2025))

# QCL: elementos estándar de FAOSTAT
QCL_ELEMENTS = [5510, 5419]   # 5510 = Producción (t), 5419 = Rendimiento (kg/ha)
# QCL: ítems de cultivos básicos de la canasta alimentaria colombiana
QCL_ITEMS = {
    56:  "Maíz",
    27:  "Arroz",
    116: "Papa",
    125: "Yuca",
    176: "Fríjol seco",
    489: "Plátano",
}


def authenticate():
    """Configura el token de FAOSTAT desde variables de entorno."""
    token = os.getenv("FAOSTAT_TOKEN")
    user = os.getenv("FAOSTAT_USER")
    pwd = os.getenv("FAOSTAT_PASS")
    if token:
        faostat.set_requests_args(token=token, lang="es")
    elif user and pwd:
        faostat.set_requests_args(username=user, password=pwd, lang="es")
    else:
        raise SystemExit(
            "Faltan credenciales. Define FAOSTAT_TOKEN, o FAOSTAT_USER + FAOSTAT_PASS.\n"
            "Consíguelas en el Portal para Desarrolladores de FAOSTAT."
        )
    print("[ok] Autenticado en FAOSTAT (lang=es).")


COLOMBIA_FAO_CODE = "44"   # Código FAO de Colombia (dato fijo)


def resolve_area_code(dataset, name="Colombia"):
    """Devuelve el código FAO de Colombia. Intenta confirmarlo por la API;
    si el endpoint de códigos no responde (p. ej. 403), usa el valor conocido (44)."""
    try:
        areas = faostat.get_par(dataset, "area")  # {etiqueta: codigo}
        for label, code in areas.items():
            if label.strip().lower() == name.lower():
                return code
        for label, code in areas.items():
            if "olombia" in label.lower():
                return code
    except Exception as e:
        print(f"     (no se pudieron consultar los códigos, uso {COLOMBIA_FAO_CODE}: {e})")
    return COLOMBIA_FAO_CODE


def save_explorer_json(df, key):
    """Guarda un dataset como JSON para el explorador del navegador."""
    payload = {
        "columns": [str(c) for c in df.columns],
        "rows": df.fillna("").astype(str).values.tolist(),
    }
    out = STATIC_DATA_DIR / f"{key}.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)
    print(f"[ok] Explorador -> app/static/data/{key}.json ({len(df)} filas)")


def fetch_food_security():
    """Dataset FS: baja toda la serie de Colombia y filtra los indicadores clave."""
    print("[..] Descargando seguridad alimentaria (FS)...")
    col = resolve_area_code("FS")
    print(f"     Código FAO de Colombia (FS): {col}")
    df = faostat.get_data_df(
        "FS",
        pars={"area": col},
        strval=False,
    )
    df.to_csv(DATA_DIR / "faostat_fs_colombia.csv", index=False, encoding="utf-8")
    print(f"[ok] FS guardado: {len(df)} filas -> app/data/faostat_fs_colombia.csv")
    save_explorer_json(df, "fs")

    # Localizar columnas de forma robusta (los nombres llegan en es/en)
    item_col = _find_col(df, ["Item", "Producto", "Indicador"])
    year_col = _find_col(df, ["Year", "Año"])
    val_col = _find_col(df, ["Value", "Valor"])

    def serie(contains_all):
        """Selecciona un ÚNICO indicador que cumpla todos los términos (evita mezclar
        '%', 'millones' y 'kcal' del mismo tema)."""
        mask = pd.Series(True, index=df.index)
        for kw in contains_all:
            mask &= df[item_col].str.lower().str.contains(kw, na=False)
        sub = df[mask]
        if sub[item_col].nunique() > 1:            # si queda más de uno, el más frecuente
            sub = sub[sub[item_col] == sub[item_col].value_counts().idxmax()]
        sub = sub.dropna(subset=[val_col]).copy()
        sub["yr"] = pd.to_numeric(sub[year_col].astype(str).str[:4], errors="coerce")
        sub = sub.dropna(subset=["yr"]).sort_values("yr")
        return sub[["yr", val_col]]

    pou = serie(["prevalencia de la subalimentación", "%"])                    # PoU (%)
    fies = serie(["moderada o grave", "población total", "%"])                 # FIES mod+grave (%)
    print(f"     Indicadores encontrados: subalimentación={len(pou)} pts, FIES={len(fies)} pts")

    years = sorted(set(pou["yr"]).union(set(fies["yr"])))
    chart = {
        "labels": [int(y) for y in years],
        "datasets": [
            {"label": "Subalimentación (%)",
             "data": _align(pou, val_col, years)},
            {"label": "Inseguridad alimentaria moderada o grave (%)",
             "data": _align(fies, val_col, years)},
        ],
    }
    with open(STATIC_DATA_DIR / "faostat_fs_colombia.json", "w", encoding="utf-8") as f:
        json.dump(chart, f, ensure_ascii=False, indent=2)
    print("[ok] JSON del gráfico -> app/static/data/faostat_fs_colombia.json")


def fetch_production():
    """Dataset QCL: baja la producción de Colombia y filtra cultivos básicos por nombre."""
    print("[..] Descargando producción de cultivos (QCL)...")
    col = resolve_area_code("QCL")
    print(f"     Código FAO de Colombia (QCL): {col}")

    df = faostat.get_data_df("QCL", pars={"area": col, "year": YEARS}, strval=False)
    if len(df) == 0:
        print("     (sin resultados con filtro de años; reintento solo por país)")
        df = faostat.get_data_df("QCL", pars={"area": col}, strval=False)
    df.to_csv(DATA_DIR / "faostat_qcl_colombia.csv", index=False, encoding="utf-8")
    print(f"[ok] QCL guardado: {len(df)} filas -> app/data/faostat_qcl_colombia.csv")
    save_explorer_json(df, "qcl")

    # Filtrar cultivos básicos por NOMBRE (no dependemos de códigos de ítem)
    try:
        item_col = _find_col(df, ["Item", "Producto"])
        elem_col = _find_col(df, ["Element", "Elemento"])
        staples = ["maíz", "maiz", "arroz", "papa", "patata", "yuca",
                   "frijol", "fríjol", "plátano", "platano"]
        keep_elem = df[elem_col].str.lower().str.contains(
            "producci|production|rendimiento|yield", na=False)
        keep_item = df[item_col].str.lower().str.contains("|".join(staples), na=False)
        sub = df[keep_elem & keep_item]
        sub.to_csv(DATA_DIR / "faostat_qcl_basicos_colombia.csv",
                   index=False, encoding="utf-8")
        print(f"[ok] QCL cultivos básicos: {len(sub)} filas "
              f"-> app/data/faostat_qcl_basicos_colombia.csv")
        save_explorer_json(sub, "qcl_basicos")
        if len(sub) == 0:
            print(f"     [diag] Elementos disponibles: {sorted(df[elem_col].dropna().unique())}")
            print("     [diag] Ejemplos de cultivos:",
                  sorted(df[item_col].dropna().unique())[:30])
    except Exception as e:
        print(f"     (no se pudo filtrar cultivos básicos: {e})")


def _find_col(df, candidates):
    cols = list(df.columns)
    # 1) coincidencia exacta
    for c in candidates:
        for col in cols:
            if col.strip().lower() == c.lower():
                return col
    # 2) subcadena, evitando columnas de CÓDIGO
    for c in candidates:
        for col in cols:
            lc = col.lower()
            if c.lower() in lc and "code" not in lc and "código" not in lc and "codigo" not in lc:
                return col
    # 3) último recurso: cualquier subcadena
    for c in candidates:
        for col in cols:
            if c.lower() in col.lower():
                return col
    raise KeyError(f"No encontré ninguna columna entre {candidates}. Columnas: {cols}")


def _align(sub, val_col, years):
    m = {int(r["yr"]): round(float(r[val_col]), 2) for _, r in sub.iterrows()}
    return [m.get(int(y)) for y in years]


if __name__ == "__main__":
    authenticate()
    hint_403 = ("\n     -> 403 suele significar TOKEN CADUCADO (duran 60 min). "
                "Saca uno nuevo y define $env:FAOSTAT_TOKEN otra vez.")
    try:
        fetch_food_security()
    except Exception as e:
        print(f"[!!] Error en FS: {e}" + (hint_403 if "403" in str(e) else ""))
    try:
        fetch_production()
    except Exception as e:
        print(f"[!!] Error en QCL: {e}" + (hint_403 if "403" in str(e) else ""))
    print("\nListo. Recarga /project/ en la app para ver el gráfico.")