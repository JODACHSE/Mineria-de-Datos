"""Application factory de la app Flask."""
from flask import Flask, render_template, url_for
from flask_wtf import CSRFProtect

from .config import Config

csrf = CSRFProtect()


def create_app(config_class: type = Config) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_class)
    csrf.init_app(app)

    from .routes.api import api_bp
    from .routes.pages import pages_bp

    app.register_blueprint(pages_bp)
    app.register_blueprint(api_bp)

    @app.context_processor
    def inject_globals():
        from .etapas import ETAPAS, R4_TOC_ITEMS, r4_toc_nav

        cfg = app.config

        # Enlace de descarga del .pbix si existe en docs/ (para la sección R4).
        pbix_file = cfg["POWERBI_PBIX_FILE"]
        try:
            pbix_url = (
                url_for("pages.descargar_doc", filename=pbix_file)
                if (cfg["DOCS_DIR"] / pbix_file).exists()
                else ""
            )
        except Exception:
            pbix_url = ""

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
            "powerbi_report_url": cfg["POWERBI_REPORT_URL"],
            "powerbi_pbix_url": pbix_url,
            "powerbi_poblacional_embed_url": cfg["POWERBI_R4_POBLACIONAL_URL"],
            "powerbi_territorial_embed_url": cfg["POWERBI_R4_TERRITORIAL_URL"],
            "powerbi_temporal_embed_url": cfg["POWERBI_R4_TEMPORAL_URL"],
            "powerbi_relacional_embed_url": cfg["POWERBI_R4_RELACIONAL_URL"],
            "r4_toc_nav": r4_toc_nav,
            "R4_TOC_ITEMS": R4_TOC_ITEMS,
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