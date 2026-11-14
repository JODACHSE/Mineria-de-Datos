"""R6 · Limpia los comentarios y genera el corpus para Orange.

Uso: python scripts/R6/preparar_comentarios.py
Entrada: comentarios_crudos.csv y videos.csv · Salida: corpus.csv y log_limpieza.json (orange/data/youtube/)
"""
from __future__ import annotations

import csv
import html
import json
import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DIR = ROOT / "orange" / "data" / "youtube"

URL = re.compile(r"(?:https?://|www\.)\S+", re.I)
CORREO = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
MENCION = re.compile(r"(?<![\w])@[\w.]{2,}")
TELEFONO = re.compile(r"(?<!\d)(?:\+?\d[\d\s().-]{6,}\d)(?!\d)")
MARCA_TIEMPO = re.compile(r"\b\d{1,2}:\d{2}(?::\d{2})?\b")
LETRAS = re.compile(r"[^\W\d_]+", re.UNICODE)

ES = set("""el la los las un una unos unas de del al y o que en por para con sin sobre entre pero como más muy ya
no sí si se me te le les nos lo es son está están ser fue era hay he ha han tiene tienen tengo hacer hace
este esta estos estas ese esa eso esto aquí allá cuando donde porque también así todo todos toda todas
mi mis tu tus su sus nuestro cada solo sólo bien mal mucho mucha muchos muchas poco gracias bueno buena
pueden puede hay colombia gobierno campesinos precio precios""".split())
EN = set("""the a an and or of to in is are was were be been this that these those with for on at by from it its
i you he she we they my your his her our their not no yes but so very just have has had do does did can will
would should could what when where why how all more most""".split())


def sin_tildes(t: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", t) if unicodedata.category(c) != "Mn")


def clave_duplicado(t: str) -> str:
    return " ".join(LETRAS.findall(sin_tildes(t.lower())))


def idioma(t: str) -> str:
    toks = [sin_tildes(w.lower()) for w in LETRAS.findall(t)]
    if not toks:
        return "indeterminado"
    es = sum(w in ES_SIN for w in toks)
    en = sum(w in EN for w in toks)
    return "es" if es >= 1 and es >= en and es / len(toks) >= 0.15 else ("en" if en > es else "otro")


ES_SIN = {sin_tildes(w) for w in ES}


def main() -> None:
    with (DIR / "comentarios_crudos.csv").open(encoding="utf-8", newline="") as f:
        crudos = list(csv.DictReader(f))
    with (DIR / "videos.csv").open(encoding="utf-8", newline="") as f:
        videos = {v["video_id"]: v for v in csv.DictReader(f)}
    corto = {vid: f"V{n:02d}" for n, vid in enumerate(videos, 1)}

    pasos: list[dict] = []

    def paso(nombre: str, antes: int, despues: int, motivo: str) -> None:
        pasos.append({"paso": nombre, "antes": antes, "despues": despues, "descartados": antes - despues, "motivo": motivo})

    filas = crudos
    n0 = len(filas)

    # 1) Vacíos.
    sig = []
    for r in filas:
        t = " ".join(html.unescape(r["texto"] or "").split())
        if t:
            sig.append({**r, "texto": t})
    paso("Registros vacíos", n0, len(sig), "Comentario sin texto o solo espacios.")
    filas = sig

    # 2) Datos personales y ruido: se enmascaran, no se descartan.
    masc = {"enlaces": 0, "correos": 0, "menciones": 0, "telefonos": 0, "marcas_de_tiempo": 0}
    for r in filas:
        t = r["texto"]
        for nombre, rx, marca in (("correos", CORREO, "[correo]"), ("enlaces", URL, "[enlace]"),
                                  ("menciones", MENCION, "[usuario]"), ("telefonos", TELEFONO, "[telefono]"),
                                  ("marcas_de_tiempo", MARCA_TIEMPO, "")):
            t, n = rx.subn(marca, t)
            masc[nombre] += n
        r["texto"] = " ".join(t.split())
    pasos.append({"paso": "Enmascarado de datos personales", "enmascarados": masc,
                  "motivo": "URL, correos, @menciones y teléfonos se sustituyen por marcas para no publicar datos de terceros; "
                            "las marcas de tiempo del video (1:23) se eliminan porque no son opinión."})

    # 3) Irrelevantes: menos de 3 palabras.
    rel = [r for r in filas if len([w for w in LETRAS.findall(r["texto"]) if w.lower() not in {"enlace", "usuario", "correo", "telefono"}]) >= 3]
    paso("Contenido irrelevante", len(filas), len(rel), "Menos de 3 palabras con letras (solo emojis, números, saludos o marcas).")
    filas = rel

    # 4) Duplicados (sin mayúsculas, tildes ni signos).
    vistos, unicos = set(), []
    for r in filas:
        k = clave_duplicado(r["texto"])
        if k and k not in vistos:
            vistos.add(k)
            unicos.append(r)
    paso("Duplicados", len(filas), len(unicos), "Mismo texto (sin mayúsculas, tildes ni signos) repetido, dentro o entre videos; se conserva el primero. Suele ser spam o copia.")
    filas = unicos

    # 5) Idioma (heurística de palabras funcionales).
    for r in filas:
        r["idioma"] = idioma(r["texto"])
    por_idioma: dict[str, int] = {}
    for r in filas:
        por_idioma[r["idioma"]] = por_idioma.get(r["idioma"], 0) + 1
    es = [r for r in filas if r["idioma"] == "es"]
    paso("Idioma distinto del español", len(filas), len(es),
         "El análisis es en español: se descartan los comentarios detectados como otro idioma. " + json.dumps(por_idioma, ensure_ascii=False))
    filas = es

    # --- Salida para Orange ---
    cab = ["texto", "id", "video", "consulta_origen", "fecha", "me_gusta", "respuestas"]
    tipos = ["s", "s", "d", "d", "t", "c", "c"]
    roles = ["meta", "meta", "meta", "meta", "meta", "", ""]
    with (DIR / "corpus.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(cab)
        w.writerow(tipos)
        w.writerow(roles)
        for r in filas:
            v = videos[r["video_id"]]
            w.writerow([r["texto"], r["id"], f"{corto[r['video_id']]} · {v['titulo'][:40]}", v["consulta_origen"],
                        r["fecha"], r["me_gusta"], r["respuestas"]])

    log = {"entrada": n0, "salida": len(filas), "pasos": pasos,
           "videos": {corto[v]: {"video_id": v, "titulo": videos[v]["titulo"]} for v in videos},
           "limites": ["La detección de idioma usa palabras funcionales: puede fallar con comentarios muy cortos o mezclados.",
                       "El enmascarado es por patrones: no garantiza eliminar todo nombre propio escrito en el texto."]}
    (DIR / "log_limpieza.json").write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{n0} comentarios -> {len(filas)} en el corpus. Detalle: {(DIR / 'log_limpieza.json').relative_to(ROOT)}")
    for p in pasos:
        if "descartados" in p:
            print(f"  - {p['paso']}: -{p['descartados']}")


if __name__ == "__main__":
    main()
