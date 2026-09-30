"""Pruebas de la etapa 3: página /r3, descargas y consistencia de las iteraciones."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from app import create_app

BASE = Path(__file__).resolve().parent.parent
R3_JSON = BASE / "app" / "static" / "data" / "R3" / "iteraciones.json"


@pytest.fixture
def client():
    app = create_app()
    app.config.update(TESTING=True)
    with app.test_client() as c:
        yield c


def test_r3_ok(client):
    resp = client.get("/r3")
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    assert "Tratamiento ETL" in html
    assert "Informe_Etapa3_Tratamiento_ETL_SSIS.pdf" in html
    assert "EVA-I3" in html and "FAOSTAT-I3" in html


def test_r3_en_entregables_y_menu(client):
    html = client.get("/entregables").data.decode("utf-8")
    assert "Tratamiento ETL con SSIS" in html
    assert "/r3" in html


@pytest.mark.parametrize("nombre", ["Informe_Etapa3_Tratamiento_ETL_SSIS.pdf", "Informe_Etapa3_Tratamiento_ETL_SSIS.docx"])
def test_informe_descargable(client, nombre):
    resp = client.get(f"/static/etapa3/{nombre}")
    assert resp.status_code == 200
    assert len(resp.data) > 10_000


def test_iteraciones_sin_perdidas():
    data = json.loads(R3_JSON.read_text(encoding="utf-8"))
    for paquete in ("eva", "faostat"):
        for it in data[paquete]["iteraciones"].values():
            assert it["recibidos"] == it["aceptados"] + it["total_revision"]
            assert it["sin_explicar"] == 0


def test_iteraciones_monotonas():
    """Cada iteración agrega reglas: los aceptados nunca aumentan."""
    data = json.loads(R3_JSON.read_text(encoding="utf-8"))
    for paquete in ("eva", "faostat"):
        its = data[paquete]["iteraciones"]
        assert its["I1"]["aceptados"] >= its["I2"]["aceptados"] >= its["I3"]["aceptados"]
