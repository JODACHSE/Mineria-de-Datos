"""Configuración de Flask. Todo valor sensible sale de variables de entorno (.env)."""
import os
import secrets
from pathlib import Path

from app.etapas import ETAPAS

BASE_DIR = Path(__file__).resolve().parent.parent


def _env(name: str, default):
    """Variable de entorno; si no existe o está vacía (p. ej. `X=` en .env) usa el valor por defecto."""
    return os.environ.get(name) or default

# Valor público de .env.example: nunca debe firmar sesiones.
_PLACEHOLDER_SECRET = "dev-key-cambiar-en-produccion"


def _secret_key() -> str:
    """SECRET_KEY del entorno, o una aleatoria por proceso si falta o es la de ejemplo."""
    key = os.environ.get("SECRET_KEY", "")
    return key if key and key != _PLACEHOLDER_SECRET else secrets.token_hex(32)


class Config:

    APP_NAME = _env("APP_NAME", "Seguridad Alimentaria & Producción Agrícola")
    SECRET_KEY = _secret_key()
    # Depuración solo con FLASK_DEBUG=1.
    DEBUG = os.environ.get("FLASK_DEBUG", "0") == "1"

    # Cookies de sesión (token CSRF): sin acceso desde JS y solo por HTTPS fuera de desarrollo.
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = not DEBUG
    MAX_CONTENT_LENGTH = 1 * 1024 * 1024  # La app no recibe archivos.

    # --- Metadatos del proyecto (disponibles en todas las plantillas) ---
    PROYECTO_TEMA = "Seguridad alimentaria y producción agrícola"
    PROYECTO_COBERTURA = "Colombia (nacional)"
    PROYECTO_PERIODO = "2000 – 2024"
    PROYECTO_ENTREGABLE = next(
        (f"{e['codigo']} · {e['titulo']}" for e in reversed(ETAPAS) if e.get("estado") == "completado"),
        ETAPAS[0]["titulo"],
    )

    # --- Equipo ---
    BRAND_NAME = "Wololo"
    BRAND_TAGLINE = "Software Development"
    BRAND_YEAR = "2024"

    UNIVERSIDAD_NOMBRE = "Universidad de Cundinamarca"
    UNIVERSIDAD_URL = "https://www.ucundinamarca.edu.co/"

    GITHUB_REPO_URL = _env("GITHUB_REPO_URL", "https://github.com/JODACHSE/Mineria-de-Datos")

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

    # --- Rutas de datos ---
    DATA_DIR = BASE_DIR / "app" / "data"
    R1_JSON_DIR = BASE_DIR / "app" / "static" / "data" / "R1"
    R2_JSON_DIR = BASE_DIR / "app" / "static" / "data" / "R2"
    R3_JSON_DIR = BASE_DIR / "app" / "static" / "data" / "R3"
    # R5: SQLite generado desde el EVA tratado (se reconstruye al arrancar si falta).
    R5_SOURCE_JSON = R2_JSON_DIR / "eva_basicos.json"
    R5_DB_PATH = Path(_env("R5_DB_PATH", BASE_DIR / "app" / "data" / "R5" / "wololo_dw.sqlite"))
    # R6: resultados de Orange, comentarios de YouTube y entregables.
    R6_JSON_DIR = BASE_DIR / "app" / "static" / "data" / "R6"
    ORANGE_DIR = BASE_DIR / "orange"
    YOUTUBE_DIR = ORANGE_DIR / "data" / "youtube"
    VIDEO_ETAPA6_URL = _env("VIDEO_ETAPA6_URL", "https://youtu.be/kvMEUs-LW4k")
    INFORME_ETAPA6_URL = _env("INFORME_ETAPA6_URL", "")
    INFORME_ETAPA6_PDF = "etapas/r6/Informe_Etapa6_Conocimiento_Oculto.pdf"  # Relativo a app/static/.
    VIDEO_ETAPA3_URL = _env("VIDEO_ETAPA3_URL", "https://youtu.be/z8omdqE1M5I")

        # --- R4 · Power BI ---
        # Informe completo ("Publicar en la web") y una página embebida por dimensión.
    POWERBI_REPORT_URL = _env("POWERBI_REPORT_URL", "https://app.powerbi.com/view?r=eyJrIjoiY2Y0ZmNhZDAtNjQ5MC00YjNhLTk1OTgtMmIwMmI0YzZlMWU3IiwidCI6IjA3ZGE2N2EwLTFmNDMtNGU4Yy05NzdmLTVmODhiNjQ3MGVlNiIsImMiOjR9")
    POWERBI_R4_POBLACIONAL_URL = _env("POWERBI_R4_POBLACIONAL_URL", "https://app.powerbi.com/view?r=eyJrIjoiZTM5YjNiZTktM2NmYy00NTk1LTk3M2UtMTljNzA5MTI1MjBlIiwidCI6IjA3ZGE2N2EwLTFmNDMtNGU4Yy05NzdmLTVmODhiNjQ3MGVlNiIsImMiOjR9&pageName=4429d44521a72f684755")
    POWERBI_R4_TERRITORIAL_URL = _env("POWERBI_R4_TERRITORIAL_URL", "https://app.powerbi.com/view?r=eyJrIjoiZTM5YjNiZTktM2NmYy00NTk1LTk3M2UtMTljNzA5MTI1MjBlIiwidCI6IjA3ZGE2N2EwLTFmNDMtNGU4Yy05NzdmLTVmODhiNjQ3MGVlNiIsImMiOjR9&pageName=933585140258a290e5b5")
    POWERBI_R4_TEMPORAL_URL = _env("POWERBI_R4_TEMPORAL_URL", "https://app.powerbi.com/view?r=eyJrIjoiZTM5YjNiZTktM2NmYy00NTk1LTk3M2UtMTljNzA5MTI1MjBlIiwidCI6IjA3ZGE2N2EwLTFmNDMtNGU4Yy05NzdmLTVmODhiNjQ3MGVlNiIsImMiOjR9&pageName=cc4de66d143540f8e1c4")
    POWERBI_R4_RELACIONAL_URL = _env("POWERBI_R4_RELACIONAL_URL", "https://app.powerbi.com/view?r=eyJrIjoiZTM5YjNiZTktM2NmYy00NTk1LTk3M2UtMTljNzA5MTI1MjBlIiwidCI6IjA3ZGE2N2EwLTFmNDMtNGU4Yy05NzdmLTVmODhiNjQ3MGVlNiIsImMiOjR9&pageName=95f533e177084c73fb5d")
    # El .pbix se descarga desde /docs/<POWERBI_PBIX_FILE>.
    DOCS_DIR = BASE_DIR / "docs"
    POWERBI_PBIX_FILE = _env("POWERBI_PBIX_FILE", "R4/EVA_PowerBI_wololo.pbix")