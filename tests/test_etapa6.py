"""Pruebas de R6: sección «Conocimiento oculto» y resultados reproducidos de Orange."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from app import create_app
from app.config import Config
from app.services.etapa6 import MODELO_ELEGIDO, build_r6_context


@pytest.fixture
def client():
    app = create_app()
    app.config.update(TESTING=True)
    with app.test_client() as c:
        yield c


def test_pagina_r6(client):
    resp = client.get("/r6")
    assert resp.status_code == 200
    html = resp.data.decode()
    assert "Conocimiento oculto" in html
    assert MODELO_ELEGIDO in html
    assert "youtube.com/watch" in html


def test_contexto_r6_coherente():
    ctx = build_r6_context(Config.R6_JSON_DIR, Config.YOUTUBE_DIR, Config.ORANGE_DIR)
    # Tres modelos evaluados bajo los mismos tres esquemas
    assert set(ctx["evaluaciones"]) == {"cv", "municipio", "temporal"}
    assert all(len(e["modelos"]) == 3 for e in ctx["evaluaciones"].values())
    # La matriz de confusión de la prueba 2024 suma los registros de prueba
    assert ctx["matriz_temporal"]["total"] == ctx["sup"]["prueba"]
    # El clustering cubre todos los municipios
    assert sum(g["municipios"] for g in ctx["grupos"]) == ctx["clu"]["municipios"]
    # Los comentarios analizados por video suman el corpus limpio
    assert sum(v["limpios"] for v in ctx["videos"]) == ctx["limpieza"]["salida"]
