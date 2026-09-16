"""Acceso a los datasets curados (JSON estáticos de R1 y R2).

Capa de servicio sin Flask: recibe el directorio base y devuelve dicts ya
parseados. Cachea en memoria porque los JSON son inmutables mientras el
proceso vive (los scripts de `scripts/` son generadores offline).
"""
from __future__ import annotations

import json
from pathlib import Path

from app.quality import DATASETS

_cache: dict[str, dict] = {}


def _read_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _cached(key: str, path: Path) -> dict:
    if key not in _cache:
        _cache[key] = _read_json(path)
    return _cache[key]


def load_raw(name: str, r1_dir: Path) -> dict:
    """Versión CRUDA (R1) de un dataset. Lanza KeyError si no existe."""
    if name not in DATASETS:
        raise KeyError(name)
    return _cached(f"r1:{name}", r1_dir / DATASETS[name])


def load_treated(name: str, r2_dir: Path) -> dict:
    """Versión TRATADA (R2) de un dataset, con columnas de bandera."""
    if name not in DATASETS:
        raise KeyError(name)
    return _cached(f"r2:{name}", r2_dir / DATASETS[name])


def load_dataset(name: str, version: str, r1_dir: Path, r2_dir: Path) -> dict:
    return load_treated(name, r2_dir) if version == "tratado" else load_raw(name, r1_dir)


def load_fs_chart(r1_dir: Path) -> dict:
    return _cached("r1:fs_chart", r1_dir / "faostat_fs_colombia.json")


def load_integracion(r1_dir: Path) -> dict:
    return _cached("r1:integracion", r1_dir / "integracion_eva_faostat.json")


def load_treatment_log(r2_dir: Path) -> dict:
    return _cached("r2:log", r2_dir / "log_tratamiento.json")


def cache_get(key: str):
    return _cache.get(key)


def cache_set(key: str, value) -> None:
    _cache[key] = value
