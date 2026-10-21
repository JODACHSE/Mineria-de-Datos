"""Las 8 etapas/entregables del curso.

Cada 'Etapa N' del enunciado del docente corresponde a un entregable
'RN' del proyecto. Hoy solo Etapa 1 / R1 está definida; las demás se
muestran como 'Próximamente' tanto en el dropdown del navbar como en
la página /entregables. Vive en su propio módulo para que app/__init__.py
pueda inyectarla como global de plantilla y esté disponible en TODAS las
páginas, no solo en la de entregables.
"""

ETAPAS = [
    {
        "codigo": "R1",
        "titulo": "Del problema a los datos",
        "resumen": "Problema, preguntas analíticas, fuentes, dataset inicial, diccionario y diagnóstico de calidad.",
        "estado": "completado",
        "url_endpoint": "pages.r1",
    },
    {
        "codigo": "R2",
        "titulo": "Diagnóstico y calidad de los datos",
        "resumen": "Perfilamiento, 6 dimensiones de calidad, inventario de problemas y tratamiento real "
                   "aplicado a los 4 datasets (EVA + FAOSTAT).",
        "estado": "completado",
        "url_endpoint": "pages.r2",
    },
    {
        "codigo": "R3",
        "titulo": "Tratamiento ETL con SSIS",
        "resumen": "Paquetes SSIS EVA y FAOSTAT con staging, reglas de limpieza, rama de revisión, "
                   "tres iteraciones, indicadores y verificación de re-ejecución sin duplicados.",
        "estado": "completado",
        "url_endpoint": "pages.r3",
    },
    {
        "codigo": "R4",
        "titulo": "Conocimiento evidente",
        "resumen": "Cuatro preguntas de análisis exploratorio (poblacional, territorial, temporal "
                   "y multivariada) sobre los datos de producción agrícola EVA, con indicadores, "
                   "visualizaciones, filtros y conocimientos evidentes documentados. Informe "
                   "completo disponible en Power BI.",
        "estado": "completado",
        "url_endpoint": "pages.r4",
    },
] + [
    {
        "codigo": f"R{n}",
        "titulo": "Aún no definido",
        "resumen": "Este entregable todavía no se ha definido. Se documentará en una próxima etapa del curso.",
        "estado": "pendiente",
        "url_endpoint": None,
    }
    for n in range(5, 9)
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
    """Navegación lateral compartida entre las 4 páginas de dimensiones de R4."""
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
