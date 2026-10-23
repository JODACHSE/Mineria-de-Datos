"""Configuración de la aplicación Flask.

Los valores sensibles se leen desde variables de entorno (.env) y nunca
se escriben directamente en el código, siguiendo el principio de
trazabilidad y buenas prácticas usado también en scripts/fetch_faostat.py.
"""
import os
from pathlib import Path

from app.etapas import ETAPAS

BASE_DIR = Path(__file__).resolve().parent.parent


class Config:
    """Configuración base, válida para desarrollo y producción."""

    APP_NAME = os.environ.get("APP_NAME", "Seguridad Alimentaria & Producción Agrícola")
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-key-cambiar-en-produccion")
    DEBUG = os.environ.get("FLASK_DEBUG", "1") == "1"

    # Metadatos del proyecto académico (se inyectan en las plantillas)
    PROYECTO_TEMA = "Seguridad alimentaria y producción agrícola"
    PROYECTO_COBERTURA = "Colombia (nacional)"
    PROYECTO_PERIODO = "2000 – 2024"
    PROYECTO_ENTREGABLE = next(
        (f"{e['codigo']} · {e['titulo']}" for e in reversed(ETAPAS) if e.get("estado") == "completado"),
        ETAPAS[0]["titulo"],
    )

    # --- Identidad del equipo (Wololo) --------------------------------
    BRAND_NAME = "Wololo"
    BRAND_TAGLINE = "Software Development"
    BRAND_YEAR = "2024"

    UNIVERSIDAD_NOMBRE = "Universidad de Cundinamarca"
    UNIVERSIDAD_URL = "https://www.ucundinamarca.edu.co/"

    # Repositorio público en GitHub. Placeholder: reemplazar por la URL real
    # una vez creado el repositorio (único lugar que hay que tocar; se usa
    # en el botón del navbar y en el footer).
    GITHUB_REPO_URL = os.environ.get("GITHUB_REPO_URL", "https://github.com/JODACHSE/Mineria-de-Datos")

    DEVELOPERS = [
        {
            "nombre": "Jonathan David Chavarro Segura",
            "iniciales": "JC",
            "rol": "Desarrollador",
            "github_user": "JODACHSE",
            "github_url": "https://github.com/JODACHSE",
            "email": "jdchavarro@ucundinamarca.edu.co",
        },
        {
            "nombre": "Andrés Felipe Rodríguez Correa",
            "iniciales": "AR",
            "rol": "Desarrollador",
            "github_user": "N3X4N",
            "github_url": "https://github.com/N3X4N",
            "email": "afrodriguezcorrea@ucundinamarca.edu.co",
        },
    ]

    # Rutas de datos
    DATA_DIR = BASE_DIR / "app" / "data"
    R1_JSON_DIR = BASE_DIR / "app" / "static" / "data" / "R1"
    R2_JSON_DIR = BASE_DIR / "app" / "static" / "data" / "R2"
    R3_JSON_DIR = BASE_DIR / "app" / "static" / "data" / "R3"
    VIDEO_ETAPA3_URL = os.environ.get("VIDEO_ETAPA3_URL", "https://youtu.be/z8omdqE1M5I")

        # Informe de Power BI (Publicar en la web). URL pública del "Publish to web".
    POWERBI_REPORT_URL = os.environ.get("POWERBI_REPORT_URL", "https://app.powerbi.com/view?r=eyJrIjoiY2Y0ZmNhZDAtNjQ5MC00YjNhLTk1OTgtMmIwMmI0YzZlMWU3IiwidCI6IjA3ZGE2N2EwLTFmNDMtNGU4Yy05NzdmLTVmODhiNjQ3MGVlNiIsImMiOjR9")
    POWERBI_EMBED_URL = os.environ.get("POWERBI_EMBED_URL", "https://app.powerbi.com/view?r=eyJrIjoiY2Y0ZmNhZDAtNjQ5MC00YjNhLTk1OTgtMmIwMmI0YzZlMWU3IiwidCI6IjA3ZGE2N2EwLTFmNDMtNGU4Yy05NzdmLTVmODhiNjQ3MGVlNiIsImMiOjR9")
    # Carpeta docs/ (raíz del proyecto) y nombre del .pbix para descargarlo desde la web.
    DOCS_DIR = BASE_DIR / "docs"
    POWERBI_PBIX_FILE = os.environ.get("POWERBI_PBIX_FILE", "EVA_PowerBI_wololo.pbix")