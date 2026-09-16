"""Application factory de la app Flask."""
from flask import Flask, render_template

from .config import Config


def create_app(config_class: type = Config) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_class)

    from .routes.api import api_bp
    from .routes.pages import pages_bp

    app.register_blueprint(pages_bp)
    app.register_blueprint(api_bp)

    @app.context_processor
    def inject_globals():
        from .etapas import ETAPAS

        cfg = app.config
        return {
            "app_name": cfg["APP_NAME"],
            "proyecto_tema": cfg["PROYECTO_TEMA"],
            "proyecto_cobertura": cfg["PROYECTO_COBERTURA"],
            "proyecto_periodo": cfg["PROYECTO_PERIODO"],
            "proyecto_entregable": cfg["PROYECTO_ENTREGABLE"],
            "brand_name": cfg["BRAND_NAME"],
            "brand_tagline": cfg["BRAND_TAGLINE"],
            "universidad_nombre": cfg["UNIVERSIDAD_NOMBRE"],
            "universidad_url": cfg["UNIVERSIDAD_URL"],
            "developers": cfg["DEVELOPERS"],
            "etapas": ETAPAS,
            "github_repo_url": cfg["GITHUB_REPO_URL"],
        }

    @app.template_filter("miles")
    def miles(value):
        """12345 -> '12.345' (separador de miles colombiano)."""
        try:
            return f"{int(value):,}".replace(",", ".")
        except (TypeError, ValueError):
            return value

    @app.errorhandler(404)
    def not_found(_e):
        return render_template("errors/404.html"), 404

    return app
