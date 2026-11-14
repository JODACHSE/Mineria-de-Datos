"""Contexto de R6 a partir de data/R6/resultados.json (Orange) y orange/data/youtube/."""
from __future__ import annotations

import csv
import json
from pathlib import Path

MODELO_ELEGIDO = "Random Forest"

# Descripción de cada grupo según su cultivo dominante.
_DESCRIPCION_GRUPO = {
    "Arroz": ("Arroceros de gran escala",
              "Municipios de llanura con mucha área sembrada, casi toda en arroz, y el mayor rendimiento relativo."),
    "Frijol": ("Andinos pequeños de frijol y maíz",
               "Municipios de ladera andina con poca área, mezcla de frijol y maíz y rendimiento por debajo de la mediana."),
    "Maíz": ("Mixtos campesinos de maíz y yuca",
             "El grupo más grande y difuso: maíz, yuca y plátano en el Caribe y la Andina, con la menor tasa de cosecha."),
    "Papa": ("Paperos del altiplano",
             "Municipios andinos casi monocultivo de papa; el grupo más compacto y con rendimiento sobre la mediana."),
    "Plátano": ("Plataneros con alta tasa de cosecha",
                "Plátano como cultivo principal en zonas cafeteras y pacíficas; cosechan el 92 % de lo sembrado."),
}


def _read_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _read_csv(path: Path) -> list[dict]:
    with open(path, encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def _matriz(m: dict) -> dict:
    """Matriz de confusión con totales y tasas por fila."""
    labels, vals = m["matriz"]["etiquetas"], m["matriz"]["valores"]
    filas = []
    for lab, row in zip(labels, vals):
        tot = sum(row)
        filas.append({"real": lab, "valores": row, "total": tot,
                      "pct": [round(100 * v / tot, 1) if tot else 0 for v in row]})
    return {"etiquetas": labels, "filas": filas, "total": sum(r["total"] for r in filas)}


def build_r6_context(r6_dir: Path, youtube_dir: Path, orange_dir: Path) -> dict:
    res = _read_json(r6_dir / "resultados.json")
    prep = _read_json(orange_dir / "data" / "log_preparacion.json")
    sup, clu = res["supervisado"], res["clustering"]

    evaluaciones = sup["evaluaciones"]
    elegido = {k: next(m for m in e["modelos"] if m["modelo"] == MODELO_ELEGIDO) for k, e in evaluaciones.items()}
    mejor = {k: max(e["modelos"], key=lambda m: m["auc"])["modelo"] for k, e in evaluaciones.items()}

    for g in clu["grupos"]:
        dominante = max(g["pct_area"], key=g["pct_area"].get)
        g["dominante"] = dominante
        g["titulo"], g["descripcion"] = _DESCRIPCION_GRUPO.get(dominante, (g["nombre"], ""))
    grupos = clu["grupos"]
    area = sorted(g["area_anual_ha_geo"] for g in grupos)

    videos = _read_csv(youtube_dir / "videos.csv")
    factores = _read_csv(youtube_dir / "factores_por_video.csv")
    limpieza = _read_json(youtube_dir / "log_limpieza.json")
    extraccion = _read_json(youtube_dir / "log_extraccion.json")
    # corpus.csv trae la cabecera de 3 filas de Orange; la columna video es «V01 · título…».
    limpios: dict[str, int] = {}
    for row in _read_csv(youtube_dir / "corpus.csv"):
        codigo = (row.get("video") or "")[:3]
        if codigo.startswith("V0"):
            limpios[codigo] = limpios.get(codigo, 0) + 1
    for i, v in enumerate(videos, start=1):
        v["codigo"] = f"V0{i}"
        v["limpios"] = limpios.get(v["codigo"], 0)

    return {
        "orange_version": res["orange_version"],
        "prep": prep,
        "sup": sup,
        "evaluaciones": evaluaciones,
        "modelo_elegido": MODELO_ELEGIDO,
        "elegido": elegido,
        "mejor_por_evaluacion": mejor,
        "matriz_temporal": _matriz(elegido["temporal"]),
        "matriz_municipio": _matriz(elegido["municipio"]),
        "clu": clu,
        "grupos": grupos,
        "escala_arroz": round(area[-1] / area[0]),
        "videos": videos,
        "factores": factores,
        "limpieza": limpieza,
        "extraccion": extraccion,
        "descartados_youtube": len(extraccion.get("restricciones", [])),
    }
