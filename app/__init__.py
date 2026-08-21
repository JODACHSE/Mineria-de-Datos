from flask import Flask
from app.config import Config

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Registro de Blueprints / Rutas
    from app.routes.lessons import lessons_bp
    from app.routes.project import project_bp

    app.register_blueprint(lessons_bp, url_prefix='/lessons')
    app.register_blueprint(project_bp, url_prefix='/project')

    # Ruta principal / Redirección o Home
    @app.route('/')
    def index():
        from flask import render_template
        return render_template('lessons/index.html')

    return app