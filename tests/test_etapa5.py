"""Pruebas de R5: modelo estrella, motor OLAP y vistas."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from app import create_app
from app.config import Config
from app.services import dw, olap


@pytest.fixture(scope="module")
def con():
    dw.ensure(Config.R5_SOURCE_JSON, Config.R5_DB_PATH)
    c = dw.connect(Config.R5_DB_PATH)
    yield c
    c.close()


@pytest.fixture
def client():
    app = create_app()
    app.config.update(TESTING=True)
    with app.test_client() as c:
        yield c


def test_validaciones_superadas(con):
    fallas = [v["nombre"] for v in olap.validations(con, Config.R5_SOURCE_JSON) if not v["ok"]]
    assert fallas == []


def test_roll_up_conserva_totales_aditivos(con):
    municipios = olap.query(con, "municipio", "produccion", limit=100000)
    regiones = olap.query(con, "region", "produccion")
    # Cada fila llega redondeada a toneladas enteras: se tolera ±1 t por miembro.
    assert sum(municipios["row_totals"]) == pytest.approx(regiones["grand_total"], abs=len(municipios["rows"]))
    assert sum(regiones["row_totals"]) == pytest.approx(regiones["grand_total"], abs=5)


def test_medida_no_aditiva_se_recalcula(con):
    q = olap.query(con, "region", "rendimiento")
    nacional = olap.kpis(con, ["produccion", "area_cosechada"])
    assert q["grand_total"] == round(nacional["produccion"] / nacional["area_cosechada"], 2)
    assert q["share_pct"] is None  # no se reparte un cociente en participaciones


def test_slice_y_dice(con):
    papa = olap.kpis(con, ["registros"], {"cultivo": ["Papa"]})["registros"]
    papa_boyaca = olap.kpis(con, ["registros"], {"cultivo": ["Papa"], "departamento": ["Boyacá"]})["registros"]
    assert 0 < papa_boyaca < papa


def test_pivot_mismo_total(con):
    a = olap.query(con, "region", "produccion", "cultivo")
    b = olap.query(con, "cultivo", "produccion", "region")
    assert a["grand_total"] == b["grand_total"]
    i, j = a["rows"].index("Andina"), a["cols"].index("Papa")
    k, m = b["rows"].index("Papa"), b["cols"].index("Andina")
    assert a["cells"][i][j] == b["cells"][k][m]


def test_cero_reportado_no_es_faltante(con):
    # El 0 (no hubo cosecha) es un valor real; el faltante sería NULL.
    nulos = con.execute("SELECT COUNT(*) FROM fact_produccion_agricola WHERE produccion_t IS NULL").fetchone()[0]
    ceros = con.execute("SELECT COUNT(*) FROM fact_produccion_agricola WHERE area_cosechada_ha = 0").fetchone()[0]
    assert nulos == 0 and ceros > 0
    # El rendimiento no cambia al excluir los ceros: su denominador es el área cosechada.
    q = "SELECT SUM(produccion_t) / SUM(area_cosechada_ha) FROM fact_produccion_agricola"
    assert con.execute(q).fetchone()[0] == pytest.approx(
        con.execute(q + " WHERE area_cosechada_ha > 0").fetchone()[0])


def test_relacion_r4_cubre_las_cuatro_vistas():
    from app.services.etapa5 import R4_RELACION, VISTAS
    assert len(R4_RELACION) == 12
    retomadas = {s for r in R4_RELACION if r["profundizar"] for s in r["vistas"]}
    assert retomadas == {v["slug"] for v in VISTAS}
    assert all(r["vistas"] == [] for r in R4_RELACION if not r["profundizar"])


def test_menu_analisis_multidimensional(client):
    html = client.get("/").get_data(as_text=True)
    assert "Análisis multidimensional</a>" in html
    for slug in ("territorial", "temporal", "sistemas", "cosecha"):
        assert f'href="/r5/{slug}"' in html


def test_niveles_fuera_de_lista_blanca(con):
    with pytest.raises(olap.OlapError):
        olap.query(con, "region; DROP TABLE x", "produccion")


@pytest.mark.parametrize("url", ["/r5", "/r5/territorial", "/r5/temporal", "/r5/sistemas", "/r5/cosecha"])
def test_paginas_r5(client, url):
    resp = client.get(url)
    assert resp.status_code == 200
    assert "Análisis multidimensional".encode() in resp.data


def test_api_r5(client):
    resp = client.get("/api/r5/cosecha?rows=departamento&cols=anio&measure=tasa_cosecha&f_cultivo=Arroz&f_region=Caribe")
    data = resp.get_json()
    assert resp.status_code == 200
    assert data["operation"] == "Dice"
    assert len(data["kpis"]) == 3
    assert "Sucre" in data["matrix"]["rows"]
    assert client.get("/api/r5/inexistente").status_code == 404
