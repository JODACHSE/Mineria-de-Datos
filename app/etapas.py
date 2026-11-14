"""Las 7 etapas del curso (RN = Etapa N). Fuente única para menú, portada, footer y /entregables.

Una etapa con estado "completado" se publica; las demás aparecen como «Próximamente».
"""

from app.services.etapa5 import VISTAS as R5_VISTAS

# icono: Bootstrap Icons · tono: color de acento 1–6 (--tone-N en tokens.css; 0 = neutro).
ETAPAS = [
    {
        "codigo": "R1",
        "icono": "bi-clipboard-data",
        "tono": 1,
        "titulo": "Del problema a los datos",
        "resumen": "Problema, preguntas analíticas, fuentes, dataset inicial, diccionario y diagnóstico de calidad.",
        "estado": "completado",
        "url_endpoint": "pages.r1",
    },
    {
        "codigo": "R2",
        "icono": "bi-shield-check",
        "tono": 2,
        "titulo": "Diagnóstico y calidad de los datos",
        "resumen": "Perfilamiento, 6 dimensiones de calidad, inventario de problemas y tratamiento real "
                   "aplicado a los 4 datasets (EVA + FAOSTAT).",
        "estado": "completado",
        "url_endpoint": "pages.r2",
    },
    {
        "codigo": "R3",
        "icono": "bi-arrow-repeat",
        "tono": 3,
        "titulo": "Tratamiento ETL con SSIS",
        "resumen": "Paquetes SSIS EVA y FAOSTAT con staging, reglas de limpieza, rama de revisión, "
                   "tres iteraciones, indicadores y verificación de re-ejecución sin duplicados.",
        "estado": "completado",
        "url_endpoint": "pages.r3",
    },
    {
        "codigo": "R4",
        "icono": "bi-bar-chart-line",
        "tono": 4,
        "titulo": "Conocimiento evidente",
        "resumen": "Cuatro preguntas de análisis exploratorio (poblacional, territorial, temporal "
                   "y multivariada) sobre los datos de producción agrícola EVA, con indicadores, "
                   "visualizaciones, filtros y conocimientos evidentes documentados. Informe "
                   "completo disponible en Power BI.",
        "estado": "completado",
        "url_endpoint": "pages.r4",
        "subpaginas": [
            {"label": "Poblacional", "endpoint": "pages.r4", "args": {}},
            {"label": "Territorial", "endpoint": "pages.r4_territorial", "args": {}},
            {"label": "Temporal", "endpoint": "pages.r4_temporal", "args": {}},
            {"label": "Relacional", "endpoint": "pages.r4_relacional", "args": {}},
        ],
    },
    {
        "codigo": "R5",
        "icono": "bi-box",
        "tono": 5,
        "titulo": "Análisis multidimensional",
        "resumen": "Modelo estrella (SQLite) con 4 dimensiones, 8 medidas y 4 jerarquías sobre el EVA "
                   "tratado; cuatro vistas interactivas con drill-down, roll-up, slice, dice y pivot, "
                   "validaciones del modelo y ocho conocimientos multidimensionales.",
        "estado": "completado",
        "url_endpoint": "pages.r5",
        "subpaginas": [
            {"label": v["corto"], "endpoint": "pages.r5_vista", "args": {"slug": v["slug"]}} for v in R5_VISTAS
        ],
    },
    {
        "codigo": "R6",
        "icono": "bi-eye",
        "tono": 6,
        "titulo": "Conocimiento oculto",
        "resumen": "Tres modelos supervisados (regresión logística, árbol y Random Forest) para anticipar "
                   "rendimientos altos, clustering k-Means de municipios y análisis de texto de comentarios "
                   "de YouTube en Orange Data Mining, con conclusiones integradas.",
        "estado": "completado",
        "url_endpoint": "pages.r6",
    },
] + [
    {
        "codigo": f"R{n}",
        "icono": "bi-hourglass-split",
        "tono": 0,
        "titulo": "Aún no definido",
        "resumen": "Este entregable todavía no se ha definido. Se documentará en una próxima etapa del curso.",
        "estado": "pendiente",
        "url_endpoint": None,
    }
    for n in range(7, 8)
]

R4_DIMENSIONES = [
    ("pages.r4", "poblacional", "Poblacional"),
    ("pages.r4_territorial", "territorial", "Territorial"),
    ("pages.r4_temporal", "temporal", "Temporal"),
    ("pages.r4_relacional", "relacional", "Relacional"),
]

R4_TOC_ITEMS = [
    ("descripcion", "Descripción y pregunta"),
    ("variables", "Variables utilizadas"),
    ("indicadores", "Indicadores"),
    ("visualizaciones", "Visualizaciones"),
    ("filtros", "Filtros interactivos"),
    ("interpretaciones", "Interpretaciones"),
    ("conocimientos", "Conocimientos evidentes"),
    ("limite-decision", "Limitación y decisión"),
]


def r4_toc_nav(active):
    """Navegación entre las 4 dimensiones de R4."""
    from flask import url_for

    return [(url_for(endpoint), label, key == active, True) for endpoint, key, label in R4_DIMENSIONES]


FASES_CRISP = [
    ("Comprensión del negocio", "Delimitar la paradoja producción-vs-inseguridad alimentaria en Colombia."),
    ("Comprensión de los datos", "EVA (municipal) + FAOSTAT (nacional): explorar cobertura, volumen y calidad."),
    ("Preparación de los datos", "Filtrar cultivos básicos, resolver duplicados y unidades, tratar faltantes."),
    ("Modelado", "Clasificación de territorios por riesgo, análisis de variabilidad interanual."),
    ("Evaluación", "Contrastar hallazgos contra el marco de las 4 dimensiones de seguridad alimentaria."),
    ("Despliegue", "Tablero interactivo y reporte para actores de política agropecuaria."),
]
