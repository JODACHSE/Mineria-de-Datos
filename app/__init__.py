"""Application factory de la app Flask."""
from flask import Flask

from .config import Config


def create_app(config_class: type = Config) -> Flask:
    """Crea y configura la instancia de la aplicación Flask."""
    app = Flask(__name__)
    app.config.from_object(config_class)

    # --- Blueprints -------------------------------------------------
    from .routes.project import project_bp
    from .routes.lessons import lessons_bp

    app.register_blueprint(project_bp)
    app.register_blueprint(lessons_bp)

    # --- Contexto global para plantillas ------------------------------
    @app.context_processor
    def inject_globals():
        from .etapas import ETAPAS
        return {
            "app_name": app.config["APP_NAME"],
            "proyecto_tema": app.config["PROYECTO_TEMA"],
            "proyecto_cobertura": app.config["PROYECTO_COBERTURA"],
            "proyecto_periodo": app.config["PROYECTO_PERIODO"],
            "proyecto_entregable": app.config["PROYECTO_ENTREGABLE"],
            "brand_name": app.config["BRAND_NAME"],
            "brand_tagline": app.config["BRAND_TAGLINE"],
            "brand_year": app.config["BRAND_YEAR"],
            "universidad_nombre": app.config["UNIVERSIDAD_NOMBRE"],
            "universidad_url": app.config["UNIVERSIDAD_URL"],
            "developers": app.config["DEVELOPERS"],
            "etapas": ETAPAS,
            "github_repo_url": app.config["GITHUB_REPO_URL"],
        }

    # --- Manejo de errores ------------------------------------------
    @app.errorhandler(404)
    def not_found(_e):
        from flask import render_template
        return render_template("layouts/base.html", error_404=True), 404

    return app
