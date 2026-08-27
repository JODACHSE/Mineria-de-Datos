"""Blueprint 'entregables' (definido en lessons.py por la estructura del proyecto).

Contiene dos páginas de apoyo:
- /entregables      -> hoja de ruta con los 8 entregables del curso.
- /sobre-nosotros   -> el equipo Wololo y la afiliación académica.

La lista de etapas vive en app/etapas.py (no aquí) porque el navbar
también la necesita en todas las páginas, vía context_processor.
"""
from flask import Blueprint, current_app, render_template

from ..etapas import ETAPAS, FASES_CRISP

lessons_bp = Blueprint("entregables", __name__)


@lessons_bp.route("/entregables")
def index():
    """Hoja de ruta: los 8 entregables del proyecto."""
    return render_template("entregables/index.html", entregables=ETAPAS, fases=FASES_CRISP)


@lessons_bp.route("/sobre-nosotros")
def about():
    """El equipo Wololo y la afiliación académica."""
    return render_template(
        "entregables/about.html",
        developers=current_app.config["DEVELOPERS"],
        universidad_nombre=current_app.config["UNIVERSIDAD_NOMBRE"],
        universidad_url=current_app.config["UNIVERSIDAD_URL"],
    )
