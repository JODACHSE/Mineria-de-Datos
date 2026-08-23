"""
rebuild_chart.py — Reconstruye SOLO el JSON del gráfico a partir del CSV ya descargado.
No usa la API ni token: lee app/data/faostat_fs_colombia.csv y reescribe
app/static/data/faostat_fs_colombia.json con un único indicador por línea.

Uso:
    python scripts/rebuild_chart.py
"""
import json
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
CSV = ROOT / "app" / "data" / "faostat_fs_colombia.csv"
OUT = ROOT / "app" / "static" / "data" / "faostat_fs_colombia.json"

IC, YC, VC = "Producto", "Año", "Valor"


def pick(df, contains_all):
    """Selecciona un ÚNICO indicador que cumpla todos los términos."""
    mask = pd.Series(True, index=df.index)
    for kw in contains_all:
        mask &= df[IC].str.lower().str.contains(kw, na=False)
    sub = df[mask]
    if sub[IC].nunique() > 1:                       # si queda más de uno, el más frecuente
        sub = sub[sub[IC] == sub[IC].value_counts().idxmax()]
    sub = sub.dropna(subset=[VC]).copy()
    sub["yr"] = pd.to_numeric(sub[YC].astype(str).str[:4], errors="coerce")
    sub = sub.dropna(subset=["yr"]).sort_values("yr")
    return sub


def align(sub, years):
    m = {int(r["yr"]): round(float(r[VC]), 2) for _, r in sub.iterrows()}
    return [m.get(int(y)) for y in years]


def main():
    if not CSV.exists():
        raise SystemExit(f"No existe {CSV}. Corre antes scripts/fetch_faostat.py.")
    df = pd.read_csv(CSV)
    pou = pick(df, ["prevalencia de la subalimentación", "%"])
    fies = pick(df, ["moderada o grave", "población total", "%"])
    years = sorted(set(pou["yr"]).union(set(fies["yr"])))
    chart = {
        "labels": [int(y) for y in years],
        "datasets": [
            {"label": "Subalimentación (%)", "data": align(pou, years)},
            {"label": "Inseguridad alimentaria moderada o grave (%)", "data": align(fies, years)},
        ],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(chart, f, ensure_ascii=False, indent=2)
    print(f"[ok] Gráfico reconstruido -> {OUT}")
    print(f"     Subalimentación: {len(pou)} puntos | Inseguridad: {len(fies)} puntos")


if __name__ == "__main__":
    main()
