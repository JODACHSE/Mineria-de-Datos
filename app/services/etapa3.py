"""Contexto de la página R3 · Tratamiento ETL con SSIS.

Lee `app/static/data/R3/iteraciones.json` (generado offline por
`scripts/etapa3_iteraciones.py`, que replica las reglas de EVA.dtsx y
FAOSTAT.dtsx) y arma las tablas de la sección Etapa 3.
"""
from __future__ import annotations

import json
from pathlib import Path

INFORME_PDF = "etapa3/Informe_Etapa3_Tratamiento_ETL_SSIS.pdf"
INFORME_DOCX = "etapa3/Informe_Etapa3_Tratamiento_ETL_SSIS.docx"

REGLAS = [
    # (paquete, código, problema, campo, acción, justificación)
    ("EVA", "EVA-DUP", "Duplicados", "Municipio, cultivo, desagregación, año, periodo",
     "Primera ocurrencia a limpios; el resto a revisión", "Una evaluación repetida infla la producción"),
    ("EVA", "—", "Formato numérico es-CO", "Las 4 métricas",
     "Quitar punto de miles y cambiar coma por punto", "Mismo valor, distinta escritura"),
    ("EVA", "EVA-CONV", "Vacíos o no convertibles", "Métricas y año",
     "Revisión con el valor original", "No se imputan valores"),
    ("EVA", "EVA-MUN", "Municipio inexistente", "CodigoMunicipioDane",
     "Lookup DIVIPOLA; sin coincidencia a revisión", "Integridad referencial y nombres oficiales"),
    ("EVA", "EVA-DOM", "Valores negativos", "Las 4 métricas", "Revisión", "No existen áreas ni producción negativas"),
    ("EVA", "EVA-CONS", "Área incoherente", "AreaCosechada > AreaSembrada", "Revisión",
     "No se cosecha más de lo sembrado"),
    ("EVA", "bandera", "Atípicos", "Las 4 métricas, por cultivo", "FlagAtipico* = 1 (se acepta)",
     "Un extremo no siempre es un error"),
    ("FAOSTAT", "FAO-DUP", "Duplicados", "Dataset, área, elemento, producto, año, unidad",
     "Primera ocurrencia a limpios; el resto a revisión", "Evita duplicar la producción anual"),
    ("FAOSTAT", "—", "Año como rango", "CodigoAnio (8 dígitos)", "AnioInicio y AnioFin",
     "Permite filtrar por año"),
    ("FAOSTAT", "FAO-CNV", "Valor no convertible", "Valor", "Revisión con el texto original",
     "No se inventan valores"),
    ("FAOSTAT", "FAO-DOM", "Valor negativo", "Valor", "Revisión", "Fuera de dominio"),
    ("FAOSTAT", "FAO-CNVF", "Código no representable", "Códigos", "Revisión", "Evita errores al insertar"),
    ("FAOSTAT", "bandera", "Unidad distinta / atípico", "Unidad, Valor",
     "FlagUnidadAtipica / FlagAtipicoValor = 1", "Se marca, no se elimina"),
]

AJUSTES = {
    "I1": "Reglas base: staging, limpieza de texto y formato, duplicados, conversión con Redirect row y "
          "municipio contra DIVIPOLA.",
    "I2": "Se agregan CSPL_ReglasDominio (negativos y área incoherente), Redirect row en la conversión final, "
          "DER_TruncarTextos y errores_limpios.csv.",
    "I3": "Se agregan los límites IQR, los Lookups IQR, DER_Banderas y la unidad modal; los Lookups se "
          "parametrizan con vIdLote y se prueba la re-ejecución del mismo lote.",
}

HALLAZGOS = {
    "eva": {
        "I1": "Pasan las 48.932 filas, pero 6.700 (13,69 %) tienen más área cosechada que sembrada.",
        "I2": "Las 6.700 filas incoherentes van a revisión (EVA-CONS); quedan 42.232 aceptadas.",
        "I3": "7.908 filas aceptadas (18,73 %) quedan con al menos una bandera de atípico.",
    },
    "faostat": {
        "I1": "2 valores \"<0.1\" de FS van a revisión; las 280 filas sin valor de QCL pasan con Valor nulo.",
        "I2": "0 negativos y 0 códigos problemáticos: las reglas nuevas no separan filas.",
        "I3": "337 valores atípicos marcados (327 QCL, 7 QCL básicos, 3 FS) y 0 unidades distintas.",
    },
}

DIAGRAMAS = [
    ("etapa3/img/eva_cf.png", "EVA · Control Flow"),
    ("etapa3/img/eva_df_lim.png", "EVA · DFT_Limpieza_EVA"),
    ("etapa3/img/fao_cf.png", "FAOSTAT · Control Flow"),
    ("etapa3/img/fao_df_ext.png", "FAOSTAT · DFT_Extraccion_FAOSTAT"),
    ("etapa3/img/fao_df_lim.png", "FAOSTAT · DFT_Limpieza_FAOSTAT"),
    ("etapa3/img/eva_eh.png", "Event Handler OnError"),
]


def _pct(a, b):
    return round(100 * a / b, 2) if b else None


def load_iteraciones(r3_dir: Path) -> dict:
    with open(r3_dir / "iteraciones.json", encoding="utf-8") as fh:
        return json.load(fh)


def _filas_paquete(data: dict, clave: str) -> list[dict]:
    filas = []
    for it, r in data["iteraciones"].items():
        filas.append(dict(
            iteracion=it,
            lote=f"{clave}-{it}",
            recibidos=r["recibidos"],
            aceptados=r["aceptados"],
            duplicados=r["revision"].get(f"{'EVA' if clave == 'EVA' else 'FAO'}-DUP", 0),
            revision=r["total_revision"],
            revision_detalle=r["revision"],
            sin_explicar=r["sin_explicar"],
            atipicos=r["atipicos"],
            aceptacion=_pct(r["aceptados"], r["recibidos"]),
            ajuste=AJUSTES[it],
            hallazgo=HALLAZGOS["eva" if clave == "EVA" else "faostat"][it],
        ))
    return filas


def build_r3_context(r3_dir: Path, video_url: str = "") -> dict:
    data = load_iteraciones(r3_dir)
    eva, fao = data["eva"], data["faostat"]
    eva_filas = _filas_paquete(eva, "EVA")
    fao_filas = _filas_paquete(fao, "FAOSTAT")
    eva_i3, fao_i3 = eva["iteraciones"]["I3"], fao["iteraciones"]["I3"]

    indicadores = {
        "EVA": [
            ("Consistencia de áreas (AC ≤ AS)", 86.31, [86.31, 100.0, 100.0]),
            ("Conformidad del formato numérico", 0.0, [100.0, 100.0, 100.0]),
            ("Unicidad", 100.0, [100.0, 100.0, 100.0]),
            ("Integridad referencial (DIVIPOLA)", 100.0, [100.0, 100.0, 100.0]),
            ("Tasa de aceptación", None, [100.0, 86.31, 86.31]),
        ],
        "FAOSTAT": [
            ("Validez de formato del valor", 99.98, [100.0, 100.0, 100.0]),
            ("Completitud del valor", 97.40, [97.40, 97.40, 97.40]),
            ("Unicidad", 100.0, [100.0, 100.0, 100.0]),
            ("Consistencia de unidades", None, [None, None, 100.0]),
            ("Tasa de aceptación", None, [99.98, 99.98, 99.98]),
        ],
    }

    chart = {
        "labels": ["I1", "I2", "I3"],
        "eva": {"aceptados": [f["aceptados"] for f in eva_filas], "revision": [f["revision"] for f in eva_filas]},
        "faostat": {"aceptados": [f["aceptados"] for f in fao_filas], "revision": [f["revision"] for f in fao_filas]},
    }

    return dict(
        data=data,
        eva=eva, fao=fao,
        eva_filas=eva_filas, fao_filas=fao_filas,
        eva_i3=eva_i3, fao_i3=fao_i3,
        reglas=REGLAS,
        indicadores=indicadores,
        diagramas=DIAGRAMAS,
        iteraciones_chart=chart,
        informe_pdf=INFORME_PDF,
        informe_docx=INFORME_DOCX,
        video_url=video_url,
        video_embed=_embed(video_url),
    )


def _embed(url: str) -> str:
    """Convierte un enlace de YouTube o Google Drive en URL para <iframe>."""
    if not url:
        return ""
    if "youtube.com/watch?v=" in url:
        return "https://www.youtube.com/embed/" + url.split("v=")[1].split("&")[0]
    if "youtu.be/" in url:
        return "https://www.youtube.com/embed/" + url.rsplit("/", 1)[1].split("?")[0]
    if "drive.google.com/file/d/" in url:
        file_id = url.split("/d/")[1].split("/")[0]
        return f"https://drive.google.com/file/d/{file_id}/preview"
    return url
