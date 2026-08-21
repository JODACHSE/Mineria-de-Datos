from flask import Flask

def create_app():
    app = Flask(__name__)

    # Importar y registrar rutas o Blueprints aquí
    from .routes import main_bp
    app.register_blueprint(main_bp)

    return app