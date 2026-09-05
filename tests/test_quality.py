"""Pruebas unitarias de app/quality.py (perfilamiento, dimensiones, inventario).

Sin Flask: importa app.quality directamente y lee los JSON reales del
proyecto (no fixtures sintéticas), consistente con la filosofía "no
simulado" ya usada en tests/test_app.py. Estas pruebas también sirven de
regresión sobre `app/static/data/R2/*.json`, generado por
`scripts/clean_datasets.py`.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.quality import (  # noqa: E402
    DATASET_SCHEMA,
    DATASETS,
    _count_duplicates,
    _hallazgo_duplicados_por_unidad,
    _numeric_stats,
    _rows_as_dicts,
    compute_dimensions,
    nivel_impacto,
    profile_columns,
)

BASE_DIR = Path(__file__).resolve().parent.parent
R1_DIR = BASE_DIR / "app" / "static" / "data" / "R1"
R2_DIR = BASE_DIR / "app" / "static" / "data" / "R2"


def _load(dirpath: Path, name: str) -> dict:
    with open(dirpath / DATASETS[name], encoding="utf-8") as fh:
        return json.load(fh)


def test_numeric_stats_valores_conocidos():
    stats = _numeric_stats([1.0, 2.0, 3.0, 100.0])
    assert stats["minimo"] == 1.0
    assert stats["maximo"] == 100.0
    assert stats["media"] == 26.5
    assert stats["mediana"] == 2.5
    assert stats["outliers_iqr"] == 1  # solo 100 queda fuera de [q1-1.5*RIC, q3+1.5*RIC]


def test_profile_columns_eva_shape():
    crudo = _load(R1_DIR, "eva_basicos")
    schema = DATASET_SCHEMA["eva_basicos"]
    rows = _rows_as_dicts(crudo)
    profile = profile_columns(rows, crudo["columns"], schema["column_meta"])
    assert len(profile) == 18
    assert profile["AreaSembrada"]["tipo"] == "numerico"
    assert "minimo" in profile["AreaSembrada"] and "maximo" in profile["AreaSembrada"]
    assert profile["Cultivo"]["tipo"] == "categorico"
    assert "top_valores" in profile["Cultivo"]


def test_compute_dimensions_rango_valido():
    with open(R1_DIR / "integracion_eva_faostat.json", encoding="utf-8") as fh:
        integracion = json.load(fh)

    for name in DATASETS:
        crudo = _load(R1_DIR, name)
        schema = DATASET_SCHEMA[name]
        kwargs = dict(integracion=integracion) if schema.get("accuracy_check") == "cruce_eva_faostat" else {}
        dims = compute_dimensions(crudo, name, **kwargs)
        assert set(dims) == {"completitud", "exactitud", "consistencia", "unicidad", "validez", "actualidad"}
        for v in dims.values():
            assert v is None or 0 <= v <= 100


def test_nivel_impacto_reproducible():
    assert nivel_impacto(0, True) == "Ninguno"
    assert nivel_impacto(15, True) == "Alto"
    assert nivel_impacto(5, True) == "Medio"
    assert nivel_impacto(1, True) == "Bajo"
    assert nivel_impacto(25, False) == "Medio"
    assert nivel_impacto(1, False) == "Bajo"


def test_hallazgo_duplicados_por_unidad_qcl():
    """Los 'huevos en dos unidades' son 25 combinaciones que afectan 50 filas."""
    crudo = _load(R1_DIR, "qcl")
    rows = _rows_as_dicts(crudo)
    n_grupos, n_filas = _hallazgo_duplicados_por_unidad(rows, DATASET_SCHEMA["qcl"]["key_fields"])
    assert n_grupos == 25
    assert n_filas == 50


def test_tratamiento_no_elimina_filas():
    """scripts/clean_datasets.py nunca elimina registros, solo corrige o marca."""
    for name in DATASETS:
        crudo = _load(R1_DIR, name)
        tratado = _load(R2_DIR, name)
        assert len(tratado["rows"]) == len(crudo["rows"])


def test_tratamiento_corrige_falsos_duplicados_qcl():
    """Bajo la llave corregida (+ Unidad), qcl no debe tener duplicados reales."""
    tratado = _load(R2_DIR, "qcl")
    rows = _rows_as_dicts(tratado)
    n_dup = _count_duplicates(rows, DATASET_SCHEMA["qcl"]["unique_key_fields"])
    assert n_dup == 0


def test_tratamiento_corrige_codigos_dane():
    """Los códigos DANE tratados deben quedar con ancho fijo (2 y 5 dígitos)."""
    tratado = _load(R2_DIR, "eva_basicos")
    rows = _rows_as_dicts(tratado)
    assert all(len(str(r["CodigoMunicipioDane"])) == 5 for r in rows)
    assert all(len(str(r["CodigoDeptoDane"])) == 2 for r in rows)


def test_tratamiento_mejora_validez_eva():
    crudo = _load(R1_DIR, "eva_basicos")
    tratado = _load(R2_DIR, "eva_basicos")
    antes = compute_dimensions(crudo, "eva_basicos")
    despues = compute_dimensions(tratado, "eva_basicos")
    assert despues["validez"] > antes["validez"]
