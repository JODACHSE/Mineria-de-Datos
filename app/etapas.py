"""Las 8 etapas/entregables del curso.

Cada 'Etapa N' del enunciado del docente corresponde a un entregable
'RN' del proyecto. Hoy solo Etapa 1 / R1 está definida; las demás se
muestran como 'Próximamente' tanto en el dropdown del navbar como en
la página /entregables. Vive en su propio módulo (no en routes/lessons.py)
para que app/__init__.py pueda inyectarla como global de plantilla y esté
disponible en TODAS las páginas, no solo en la de entregables.
"""

ETAPAS = [
    {
        "codigo": "R1",
        "titulo": "Del problema a los datos",
        "resumen": "Problema, preguntas analíticas, fuentes, dataset inicial, diccionario y diagnóstico de calidad.",
        "estado": "completado",
        "url_endpoint": "project.r1",
    },
    {
        "codigo": "R2",
        "titulo": "Diagnóstico y calidad de los datos",
        "resumen": "Perfilamiento, 6 dimensiones de calidad, inventario de problemas y tratamiento real "
                   "aplicado a los 4 datasets (EVA + FAOSTAT).",
        "estado": "completado",
        "url_endpoint": "project.r2",
    },
] + [
    {
        "codigo": f"R{n}",
        "titulo": "Aún no definido",
        "resumen": "Este entregable todavía no se ha definido. Se documentará en una próxima etapa del curso.",
        "estado": "pendiente",
        "url_endpoint": None,
    }
    for n in range(3, 9)
]

FASES_CRISP = [
    ("Comprensión del negocio", "Delimitar la paradoja producción-vs-inseguridad alimentaria en Colombia."),
    ("Comprensión de los datos", "EVA (municipal) + FAOSTAT (nacional): explorar cobertura, volumen y calidad."),
    ("Preparación de los datos", "Filtrar cultivos básicos, resolver duplicados y unidades, tratar faltantes."),
    ("Modelado", "Clasificación de territorios por riesgo, análisis de variabilidad interanual."),
    ("Evaluación", "Contrastar hallazgos contra el marco de las 4 dimensiones de seguridad alimentaria."),
    ("Despliegue", "Tablero interactivo y reporte para actores de política agropecuaria."),
]
