"""R5 · Genera docs/R5/analisis_multidimensional.md desde el modelo estrella.

Uso (desde la raíz del repositorio, después de build_star.py):

    python scripts/R5/export_docs.py

Exporta al repositorio lo mismo que muestra /r5: relación con R4, las cuatro
preguntas, los ejemplos de las operaciones OLAP, los ocho conocimientos (con
cifras calculadas por consulta al modelo) y las validaciones. Así la
documentación no se desincroniza de la aplicación.
"""
import sys
from contextlib import closing
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from app.config import Config  # noqa: E402
from app.services import dw, etapa5, olap  # noqa: E402

OUT = ROOT / "docs" / "R5" / "analisis_multidimensional.md"


def cell(v) -> str:
    return str(v).replace("|", "\\|").replace("\n", " ")


def table(head: list[str], rows: list[list]) -> list[str]:
    out = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    out += ["| " + " | ".join(cell(c) for c in r) + " |" for r in rows]
    return out + [""]


def main() -> int:
    dw.ensure(Config.R5_SOURCE_JSON, Config.R5_DB_PATH)
    with closing(dw.connect(Config.R5_DB_PATH)) as con:
        cob = etapa5._cobertura(con)
        conocimientos = etapa5._conocimientos(con)
        validaciones = olap.validations(con, Config.R5_SOURCE_JSON)
        incoh = con.execute("SELECT SUM(area_incoherente) FROM fact_produccion_agricola").fetchone()[0]
        cero = con.execute("SELECT COUNT(*) FROM fact_produccion_agricola WHERE area_cosechada_ha = 0").fetchone()[0]

    vistas = {v["slug"]: etapa5._vista_meta(v) for v in etapa5.VISTAS}
    f = etapa5.fmt
    L = [
        "# R5 · Análisis multidimensional: preguntas, operaciones y conocimientos",
        "",
        "> Archivo generado por `python scripts/R5/export_docs.py` a partir del modelo estrella; no se edita a mano.",
        "> Diagrama, diccionario y carga del modelo: [`modelo_estrella.md`](modelo_estrella.md).",
        "",
        "## 1. Datos utilizados",
        "",
        f"- **Fuente:** EVA, Evaluaciones Agropecuarias Municipales (MinAgricultura/UPRA, datos.gov.co), "
        f"tratado en R2/R3 (`app/static/data/R2/eva_basicos.json`).",
        f"- **Cobertura:** {cob['anio_min']}–{cob['anio_max']} · {f(cob['municipios'])} municipios de "
        f"{cob['departamentos']} departamentos · 6 cultivos básicos.",
        f"- **Registros utilizados:** {f(cob['hechos'])} (todos los del EVA tratado; no se filtra ninguno).",
        f"- **Limitaciones de calidad:** {f(incoh)} hechos ({f(100 * incoh / cob['hechos'], 1)} %) con área cosechada "
        f"mayor que la sembrada (se conservan con bandera y se pueden excluir); {f(cero)} hechos con área cosechada 0 "
        "(respuesta negativa, no faltante); cambio de desagregación del maíz en 2021; el plátano solo tiene periodo anual.",
        "- **Unidad de análisis:** la producción de un cultivo básico en un municipio.",
        "- **Granularidad de la tabla de hechos:** 1 municipio × 1 desagregación de cultivo × 1 periodo agrícola.",
        "",
        "## 2. Relación con el conocimiento evidente (R4)",
        "",
    ]
    L += table(["Conocimiento evidente (R4)", "¿Profundizar?", "Por qué", "Cómo lo aborda R5", "Análisis"], [
        [f"{r['pagina']} · **{r['titulo']}** — {r['hallazgo']}", "Sí" if r["profundizar"] else "No",
         r["por_que"], r["como"],
         ", ".join(f"{vistas[s]['num']}. {vistas[s]['corto']}" for s in r["vistas"]) or "Diseño del modelo"]
        for r in etapa5.R4_RELACION])

    L += ["## 3. Preguntas de análisis", ""]
    for v in vistas.values():
        L += [
            f"### Análisis {v['num']} · {v['titulo']}  (`/r5/{v['slug']}`)",
            "",
            f"**Pregunta.** {v['pregunta']}",
            "",
            f"**Cómo profundiza R4.** {v['profundiza']}",
            "",
            f"- **Dimensiones:** {', '.join(v['dimensiones'])}",
            "- **Medidas:** " + "; ".join(f"{m['label']} ({m['unit']}, `{m['agg']}`)" for m in v["medidas_info"]),
            "- **Jerarquías:** " + "; ".join(f"{j['dim']}: {' → '.join(j['niveles'])}" for j in v["jerarquias_info"]),
            "",
            "**Interpretación.**",
            "",
            *[f"- {t}" for t in v["interpretacion"]],
            "",
            f"**Limitación.** {v['limitacion']}",
            "",
            f"**Decisión sustentada en los datos.** {v['decision']}",
            "",
        ]

    L += ["## 4. Operaciones multidimensionales (ejemplos aplicados)", ""]
    for e in etapa5.EJEMPLOS:
        v = vistas[e["vista"]]
        L += [
            f"### {e['op']} · {e['titulo']}",
            "",
            f"- **Análisis:** {v['num']}. {v['corto']} · enlace directo: `/r5/{e['vista']}?ej={e['id']}`",
            f"- **Dimensiones:** {e['dimensiones']}",
            f"- **Medidas:** {e['medidas']}",
            f"- **Nivel y filtros:** {e['nivel']}",
            f"- **Procedimiento:** {e['procedimiento']}",
            f"- **Interpretación:** {e['interpretacion']}",
            "",
        ]

    L += ["## 5. Conocimientos multidimensionales", ""]
    for slug, items in conocimientos.items():
        for c in items:
            L += [f"### {c['n']} · {c['titulo']}", "", f"_Análisis {vistas[slug]['num']}: {vistas[slug]['corto']}_", ""]
            L += [f"- **{k}:** {c[key]}" for k, key in (
                ("Pregunta", "pregunta"), ("Dimensiones y medidas", "variables"), ("Procedimiento", "procedimiento"),
                ("Evidencia", "evidencia"), ("Hallazgo", "hallazgo"), ("Interpretación", "interpretacion"),
                ("Utilidad", "utilidad"), ("Limitación", "limitacion"))]
            L.append("")

    L += ["## 6. Validaciones del modelo frente a los datos tratados", ""]
    L += table(["Grupo", "Comprobación", "Modelo", "Origen / esperado", "Resultado", "Nota"], [
        [x["grupo"], x["nombre"], x["modelo"], x["origen"],
         ("Diferencia explicada" if x["modelo"] != x["origen"] else "OK") if x["ok"] else "FALLA", x["nota"]]
        for x in validaciones])

    OUT.write_text("\n".join(L), encoding="utf-8")
    print(f"Escrito {OUT.relative_to(ROOT)} ({len(L)} líneas)")
    return 0 if all(x["ok"] for x in validaciones) else 1


if __name__ == "__main__":
    raise SystemExit(main())
