"""R6 · Cuenta los factores que mencionan los comentarios (diccionario de términos).

Uso: python scripts/R6/factores_comentarios.py
Entrada: orange/data/youtube/corpus.csv · Salida: factores_por_video.csv y factores_log.json
Análisis de contenido, no de sentimiento: no detecta ironía ni negaciones.
"""
from __future__ import annotations

import csv
import json
import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DIR = ROOT / "orange" / "data" / "youtube"

FACTORES = {
    "Intermediarios y acaparadores": ("intermediari", "revended", "acaparad", "mayorista", "molino", "oligopolio", "usurer", "usuran"),
    "Gobierno y política": ("gobierno", "president", "ministr", "petro", "congres", "senador", "politic", "uribe", "duque", "santos"),
    "Importaciones y tratados comerciales": ("tlc", "libre comercio", "importa", "importad", "arancel", "contrabando", "extranjer", "dumping"),
    "Costo de insumos y logística": ("insumo", "abono", "fertiliz", "agroquimic", "monomero", "combustible", "gasolina", "transporte", "peaje", "mano de obra", "flete"),
    "Precio al productor vs. al consumidor": ("precio", "pagan", "pagar", "cobran", "cobrar", "barato", "caro", "carisim"),
    "Subsidios, crédito y apoyo estatal": ("subsid", "credito", "ayuda", "apoyo", "apoyar", "apoyemos"),
    "Clima y plagas": ("climatic", "clima este", "clima fue", "buen clima", "mal clima", "lluvia", "sequia", "plaga", "sogata", "hoja blanca", "fenomeno", "invierno", "verano"),
    "Productividad, calidad y tecnología": ("productiv", "tecnolog", "tecnific", "competitiv", "calidad", "semilla", "modernizar", "modernizacion"),
    "Sobreproducción, oferta y demanda": ("sobreproduc", "oferta", "demanda", "mucha papa", "demasiada", "sobra"),
    "Venta directa y mercados campesinos": ("mercado campesino", "mercados campesinos", "venta directa", "vender directamente", "vendan directamente", "directamente al consumidor", "sin intermediari"),
}


EXACTAS = {"caro", "santos", "duque", "uribe", "petro", "tlc"}  # Palabra completa (evita falsos positivos como «Carolina»).


def patron(t: str) -> re.Pattern:
    return re.compile(r"\b" + re.escape(norm(t)) + (r"\b" if t in EXACTAS else ""))


def norm(t: str) -> str:
    t = unicodedata.normalize("NFD", t.lower())
    return re.sub(r"\s+", " ", "".join(c for c in t if unicodedata.category(c) != "Mn"))


def main() -> None:
    with (DIR / "corpus.csv").open(encoding="utf-8", newline="") as f:
        lector = csv.reader(f)
        cab = next(lector)
        next(lector), next(lector)  # Filas de tipos y roles de Orange.
        filas = [dict(zip(cab, r)) for r in lector]
    for r in filas:
        r["cod"] = r["video"].split(" ")[0]
        r["_t"] = norm(r["texto"])
    videos = sorted({r["cod"] for r in filas})
    n_video = {v: sum(r["cod"] == v for r in filas) for v in videos}

    salida = []
    for factor, terminos in FACTORES.items():
        patrones = [patron(t) for t in terminos]
        hit = [any(p.search(r["_t"]) for p in patrones) for r in filas]
        fila = {"factor": factor, "comentarios": sum(hit), "pct_total": round(100 * sum(hit) / len(filas), 1)}
        for v in videos:
            n = sum(h for h, r in zip(hit, filas) if r["cod"] == v)
            fila[f"{v}_n"], fila[f"{v}_pct"] = n, round(100 * n / n_video[v], 1)
        salida.append(fila)
    salida.sort(key=lambda x: -x["comentarios"])

    with (DIR / "factores_por_video.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(salida[0]))
        w.writeheader()
        w.writerows(salida)
    (DIR / "factores_log.json").write_text(json.dumps({
        "comentarios": len(filas), "por_video": n_video,
        "diccionarios": {k: list(v) for k, v in FACTORES.items()},
        "limite": "Coincidencia de expresiones: no detecta ironía, negación ni sinónimos fuera del diccionario."},
        ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"{len(filas)} comentarios | {n_video}")
    for s in salida:
        print(f"  {s['factor']:<40} {s['comentarios']:>3} ({s['pct_total']:>4}%)  " +
              "  ".join(f"{v}: {s[v + '_pct']:>4}%" for v in videos))


if __name__ == "__main__":
    main()
