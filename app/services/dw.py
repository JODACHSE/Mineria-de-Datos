"""R5 · Transformación y carga del modelo estrella (SQLite).

Lee el EVA tratado en R2 (`app/static/data/R2/eva_basicos.json`), crea las
tablas con `SQL/R5/01_modelo_estrella.sql` y carga las cuatro dimensiones y la
tabla de hechos. Es idempotente: cada ejecución reconstruye la base desde cero.

Se usa desde `scripts/R5/build_star.py` (línea de comandos) y desde la app,
que construye la base al arrancar si todavía no existe. Solo usa la biblioteca
estándar (sqlite3/json): no agrega dependencias a producción.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from app.services.etapa4 import _REGION_MAP

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DDL_PATH = BASE_DIR / "SQL" / "R5" / "01_modelo_estrella.sql"

DESCONOCIDO = "Desconocido"

# Desagregación EVA → sistema productivo. EVA codifica el sistema dentro del
# nombre de la desagregación; separarlo permite comparar tecnificado vs
# tradicional en maíz y arroz aunque EVA cambie la desagregación (en 2021 el
# maíz pasó de "tecnificado/tradicional" a "amarillo/blanco tecnificado/…").
_SISTEMA_POR_DESAGREGACION = {
    "Arroz riego": "Tecnificado",
    "Arroz secano mecanizado": "Tecnificado",
    "Arroz secano manual": "Tradicional",
    "Maíz tecnificado": "Tecnificado",
    "Maíz amarillo tecnificado": "Tecnificado",
    "Maíz blanco tecnificado": "Tecnificado",
    "Maíz tradicional": "Tradicional",
    "Maíz amarillo tradicional": "Tradicional",
    "Maíz blanco tradicional": "Tradicional",
    "Plátano de exportación": "Exportación",
    "Plátano consumo interno": "Consumo interno",
    "Yuca industrial": "Industrial",
    "Yuca consumo en fresco": "Consumo en fresco",
    "Papa todas las variedades": "Sin diferenciar",
    "Papa criolla": "Sin diferenciar",
    "Frijol": "Sin diferenciar",
}

# (sistema_key, sistema, criterio, descripción)
SISTEMAS = [
    (0, DESCONOCIDO, DESCONOCIDO, "Desagregación sin sistema identificable."),
    (1, "Tecnificado", "Nivel tecnológico", "Maíz tecnificado y arroz de riego o secano mecanizado."),
    (2, "Tradicional", "Nivel tecnológico", "Maíz tradicional y arroz secano manual."),
    (3, "Consumo interno", "Destino", "Plátano para el mercado interno."),
    (4, "Exportación", "Destino", "Plátano de exportación."),
    (5, "Consumo en fresco", "Destino", "Yuca para consumo en fresco."),
    (6, "Industrial", "Destino", "Yuca con destino industrial."),
    (7, "Sin diferenciar", "Sin diferenciar", "Papa y frijol: EVA no distingue sistema ni destino."),
]
_SISTEMA_KEY = {s[1]: s[0] for s in SISTEMAS}


def _periodo(codigo: str, anio: int) -> tuple[int, str, str]:
    """'2019A' → (20191, 'Semestre A', 'Semestral'); '' → (20190, 'Anual', 'Anual')."""
    if codigo.endswith("A"):
        return anio * 10 + 1, "Semestre A", "Semestral"
    if codigo.endswith("B"):
        return anio * 10 + 2, "Semestre B", "Semestral"
    return anio * 10, "Anual", "Anual"


def _trienio(anio: int) -> str:
    return "2019–2021" if anio <= 2021 else "2022–2024"


def load_source(r2_json: Path) -> list[dict]:
    with open(r2_json, encoding="utf-8") as fh:
        data = json.load(fh)
    cols = data["columns"]
    return [dict(zip(cols, row)) for row in data["rows"]]


def build(r2_json: Path, db_path: Path) -> dict:
    """Reconstruye la base estrella y devuelve un resumen de la carga."""
    rows = load_source(r2_json)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = db_path.with_suffix(".tmp")
    if tmp.exists():
        tmp.unlink()

    con = sqlite3.connect(tmp)
    try:
        con.executescript(DDL_PATH.read_text(encoding="utf-8"))

        # ---- dimensiones (miembro 0 = Desconocido) ---------------------
        territorios = {"00000": (0, "00000", DESCONOCIDO, "00", DESCONOCIDO, DESCONOCIDO)}
        tiempos: dict[str, tuple] = {}
        cultivos = {DESCONOCIDO: (0, DESCONOCIDO, None, DESCONOCIDO, DESCONOCIDO,
                                  DESCONOCIDO, DESCONOCIDO, DESCONOCIDO)}

        for r in rows:
            cod_mun = (r.get("CodigoMunicipioDane") or "").strip()
            if cod_mun and cod_mun not in territorios:
                depto = (r.get("Departamento") or "").strip() or DESCONOCIDO
                territorios[cod_mun] = (
                    len(territorios), cod_mun, (r.get("Municipio") or "").strip() or DESCONOCIDO,
                    (r.get("CodigoDeptoDane") or "").strip() or cod_mun[:2],
                    depto, _REGION_MAP.get(depto, DESCONOCIDO),
                )

            anio = int(r["Anio"])
            codigo = (r.get("Periodo") or "").strip()
            key, periodo, tipo = _periodo(codigo, anio)
            codigo = codigo or str(anio)
            tiempos.setdefault(codigo, (key, codigo, anio, periodo, tipo, _trienio(anio)))

            desag = (r.get("DesagregacionCultivo") or "").strip()
            if desag and desag not in cultivos:
                cultivos[desag] = (
                    len(cultivos), desag, r.get("CodigoCultivo"),
                    r.get("Cultivo") or DESCONOCIDO, r.get("GrupoCultivo") or DESCONOCIDO,
                    r.get("CicloCultivo") or DESCONOCIDO, r.get("EstadoFisico") or DESCONOCIDO,
                    r.get("NombreCientifico") or DESCONOCIDO,
                )

        con.executemany("INSERT INTO dim_territorio VALUES (?,?,?,?,?,?)", territorios.values())
        con.executemany("INSERT INTO dim_tiempo VALUES (?,?,?,?,?,?)", tiempos.values())
        con.executemany("INSERT INTO dim_cultivo VALUES (?,?,?,?,?,?,?,?)", cultivos.values())
        con.executemany("INSERT INTO dim_sistema_productivo VALUES (?,?,?,?)", SISTEMAS)

        # ---- hechos (búsqueda de claves sustitutas) ---------------------
        def num(v):
            # Faltante → NULL (no 0): así no se confunde con una respuesta
            # negativa reportada (p. ej., área cosechada 0 = no hubo cosecha).
            return float(v) if v not in (None, "") else None

        facts = []
        for i, r in enumerate(rows, start=1):
            desag = (r.get("DesagregacionCultivo") or "").strip()
            anio = int(r["Anio"])
            codigo = (r.get("Periodo") or "").strip() or str(anio)
            facts.append((
                i,
                territorios.get((r.get("CodigoMunicipioDane") or "").strip(), territorios["00000"])[0],
                tiempos[codigo][0],
                cultivos.get(desag, cultivos[DESCONOCIDO])[0],
                _SISTEMA_KEY.get(_SISTEMA_POR_DESAGREGACION.get(desag, DESCONOCIDO), 0),
                num(r.get("AreaSembrada")), num(r.get("AreaCosechada")), num(r.get("Produccion")),
                r.get("Rendimiento"),
                1 if r.get("_flag_area_incoherente") else 0,
            ))
        con.executemany("INSERT INTO fact_produccion_agricola VALUES (?,?,?,?,?,?,?,?,?,?)", facts)
        con.commit()
    finally:
        con.close()

    tmp.replace(db_path)
    return {
        "origen": len(rows),
        "hechos": len(facts),
        "dim_territorio": len(territorios),
        "dim_tiempo": len(tiempos),
        "dim_cultivo": len(cultivos),
        "dim_sistema_productivo": len(SISTEMAS),
    }


def ensure(r2_json: Path, db_path: Path) -> None:
    """Construye la base si no existe o si el JSON tratado es más reciente."""
    if not db_path.exists() or db_path.stat().st_mtime < r2_json.stat().st_mtime:
        build(r2_json, db_path)


def connect(db_path: Path) -> sqlite3.Connection:
    """Conexión de solo lectura para las consultas de la app."""
    con = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True, check_same_thread=False)
    con.row_factory = sqlite3.Row
    return con
