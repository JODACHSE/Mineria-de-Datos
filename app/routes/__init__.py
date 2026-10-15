"""Blueprints de la aplicación: `pages` (HTML) y `api` (JSON)."""
from flask import current_app


def _dirs():
    cfg = current_app.config
    return cfg["R1_JSON_DIR"], cfg["R2_JSON_DIR"]
