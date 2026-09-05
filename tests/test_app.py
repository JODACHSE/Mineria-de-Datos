"""Pruebas básicas de humo para las rutas principales de la aplicación."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from app import create_app


@pytest.fixture
def client():
    app = create_app()
    app.config.update(TESTING=True)
    with app.test_client() as c:
        yield c


def test_index_ok(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "SEGURIDAD".encode() in resp.data


def test_r1_ok(client):
    resp = client.get("/r1")
    assert resp.status_code == 200
    assert b"problema" in resp.data.lower()


def test_entregables_ok(client):
    resp = client.get("/entregables")
    assert resp.status_code == 200
    assert b"R8" in resp.data
    assert "Aún no definido".encode("utf-8") in resp.data


def test_about_ok(client):
    resp = client.get("/sobre-nosotros")
    assert resp.status_code == 200
    assert b"JODACHSE" in resp.data
    assert b"N3X4N" in resp.data
    assert "Cundinamarca".encode() in resp.data


def test_api_dataset_qcl_basicos(client):
    resp = client.get("/api/dataset/qcl_basicos")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["dataset"] == "qcl_basicos"
    assert data["total"] > 0
    assert len(data["rows"]) <= data["page_size"]


def test_api_dataset_filters(client):
    resp = client.get("/api/dataset/qcl_basicos?producto=Maíz")
    assert resp.status_code == 200
    data = resp.get_json()
    assert all("maíz" in row.get("Producto", "").lower() for row in data["rows"])


def test_api_dataset_not_found(client):
    resp = client.get("/api/dataset/no-existe")
    assert resp.status_code == 404


def test_api_dataset_eva_basicos(client):
    resp = client.get("/api/dataset/eva_basicos?page=1&page_size=5")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["dataset"] == "eva_basicos"
    assert data["total"] > 10000  # dataset real, no simulado
    assert "Cultivo" in data["display_columns"]
    assert set(data["productos_disponibles"]) == {"Maíz", "Arroz", "Papa", "Plátano", "Yuca", "Frijol"}


def test_api_dataset_eva_filter_producto(client):
    resp = client.get("/api/dataset/eva_basicos?producto=Maíz&page_size=200")
    assert resp.status_code == 200
    data = resp.get_json()
    assert all("maíz" in row.get("Cultivo", "").lower() for row in data["rows"])


def test_api_quality_eva_basicos(client):
    resp = client.get("/api/quality/eva_basicos")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["total"] > 10000
    assert 0 <= data["completeness"] <= 100


def test_api_quality(client):
    resp = client.get("/api/quality/fs")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "completeness" in data
    assert 0 <= data["completeness"] <= 100


def test_404_page(client):
    resp = client.get("/ruta-que-no-existe")
    assert resp.status_code == 404


def test_r2_ok(client):
    resp = client.get("/r2")
    assert resp.status_code == 200
    assert b"calidad" in resp.data.lower()


def test_api_profile_eva_basicos(client):
    resp = client.get("/api/profile/eva_basicos")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["total"] > 10000
    assert len(data["columns"]) == 18
    assert set(data["dimensiones"]) == {
        "completitud", "exactitud", "consistencia", "unicidad", "validez", "actualidad",
    }


def test_api_profile_not_found(client):
    resp = client.get("/api/profile/no-existe")
    assert resp.status_code == 404


def test_api_dataset_version_tratado(client):
    resp = client.get("/api/dataset/eva_basicos?version=tratado&page_size=5")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["total"] <= 48932
    # la version tratada agrega columnas de bandera que la cruda no tiene
    assert any(c.startswith("_flag") or c.startswith("_outlier") for c in data["columns"])


def test_api_quality_sin_regresion_tras_refactor(client):
    """R1 no debe cambiar de comportamiento tras extraer app/quality.py."""
    resp = client.get("/api/quality/eva_basicos")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["total"] > 10000
    assert 0 <= data["completeness"] <= 100
