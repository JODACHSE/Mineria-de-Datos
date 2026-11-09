"""R5 · Transformación y carga del modelo estrella (SQLite).

Lee el EVA tratado en R2 (`app/static/data/R2/eva_basicos.json`), crea las
tablas con `SQL/R5/01_modelo_estrella.sql` y carga las cuatro dimensiones y la
tabla de hechos. Es idempotente: cada ejecución reconstruye la base desde cero.

Se usa desde `scripts/R5/build_star.py` (línea de comandos) y desde la app,
que construye la base al arrancar si todavía no existe. Solo usa la biblioteca
estándar (sqlite3/json): no agrega dependencias a producción.
"""
from __future__ import annotations

import csv
import json
import re
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


def _periodo(codigo: str, anio: int) -> tuple[int, str, str, str]:
    """'2019A' → (20191, 'Semestre A', 'Semestral', 'Ene–Jun'); '' → (20190, 'Anual', 'Anual', 'Ene–Dic')."""
    if codigo.endswith("A"):
        return anio * 10 + 1, "Semestre A", "Semestral", "Ene–Jun"
    if codigo.endswith("B"):
        return anio * 10 + 2, "Semestre B", "Semestral", "Jul–Dic"
    return anio * 10, "Anual", "Anual", "Ene–Dic"


def _trienio(anio: int) -> str:
    return "2019–2021" if anio <= 2021 else "2022–2024"


def _etapa_desagregacion(anio: int) -> str:
    # En 2021 EVA reemplazó "Maíz tecnificado/tradicional" (reportado en fresco) por
    # "Maíz amarillo/blanco tecnificado/tradicional" (reportado en grano seco).
    return "2019–2020 (anterior)" if anio <= 2020 else "2021–2024 (actual)"


def _variedad(desag: str, cultivo: str) -> str:
    d = desag.lower()
    for clave, valor in (("amarillo", "Amarillo"), ("blanco", "Blanco"), ("criolla", "Criolla"),
                         ("todas las variedades", "Todas las variedades")):
        if clave in d:
            return valor
    return "Sin distinguir color" if cultivo == "Maíz" else "No aplica"


def _num_co(v: str | None) -> float | None:
    """'-75,581775' → -75.581775 (DIVIPOLA usa coma decimal)."""
    try:
        return float(v.replace(",", ".")) if v and v.strip() else None
    except ValueError:
        return None


def load_divipola() -> dict[str, dict]:
    """Código DIVIPOLA → tipo de entidad y coordenadas (CSV versionado en app/data/)."""
    path = next(iter(sorted((BASE_DIR / "app" / "data").glob("DIVIPOLA*.csv"))), None)
    if path is None:
        return {}
    with open(path, encoding="utf-8-sig", newline="") as fh:
        reader = csv.reader(fh)
        next(reader, None)
        return {row[2].strip(): {"tipo": row[4].strip() or DESCONOCIDO,
                                 "longitud": _num_co(row[5]), "latitud": _num_co(row[6])}
                for row in reader if len(row) >= 7 and row[2].strip()}


def load_source(r2_json: Path) -> list[dict]:
    with open(r2_json, encoding="utf-8") as fh:
        data = json.load(fh)
    cols = data["columns"]
    return [dict(zip(cols, row)) for row in data["rows"]]


# Sentencias que puede contener el DDL del modelo estrella (SQL/R5/01_modelo_estrella.sql).
_DDL_PERMITIDO = re.compile(
    r"^(PRAGMA\s+foreign_keys\s*=\s*ON"
    r"|DROP\s+TABLE\s+IF\s+EXISTS\s+\w+"
    r"|CREATE\s+(UNIQUE\s+)?(TABLE|INDEX)\s+\w+[\s\S]*)$",
    re.IGNORECASE,
)


def _ddl_statements(path: Path) -> list[str]:
    """Lee el DDL y devuelve sus sentencias, rechazando cualquier otra cosa.

    El archivo se ejecuta sentencia por sentencia y solo si es PRAGMA
    foreign_keys, DROP TABLE IF EXISTS, CREATE TABLE o CREATE INDEX: así un
    archivo alterado no puede inyectar DML ni otras instrucciones.
    """
    sin_comentarios = re.sub(r"--[^\n]*", "", path.read_text(encoding="utf-8"))
    sentencias = [s.strip() for s in sin_comentarios.split(";") if s.strip()]
    for s in sentencias:
        if not _DDL_PERMITIDO.match(s):
            raise ValueError(f"Sentencia no permitida en {path.name}: {s[:60]!r}")
    return sentencias


def build(r2_json: Path, db_path: Path) -> dict:
    """Reconstruye la base estrella y devuelve un resumen de la carga."""
    rows = load_source(r2_json)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = db_path.with_suffix(".tmp")
    if tmp.exists():
        tmp.unlink()

    con = sqlite3.connect(tmp)
    try:
        for sentencia in _ddl_statements(DDL_PATH):
            con.execute(sentencia)

        # ---- dimensiones (miembro 0 = Desconocido) ---------------------
        divipola = load_divipola()
        territorios = {"00000": (0, "00000", DESCONOCIDO, "00", DESCONOCIDO, DESCONOCIDO,
                                 DESCONOCIDO, DESCONOCIDO, None, None)}
        tiempos: dict[str, tuple] = {}
        cultivos = {DESCONOCIDO: [0, DESCONOCIDO, None, DESCONOCIDO, DESCONOCIDO, DESCONOCIDO,
                                  DESCONOCIDO, DESCONOCIDO, DESCONOCIDO, DESCONOCIDO, None, None]}
        cultivos_por_sistema: dict[str, set] = {}

        for r in rows:
            cod_mun = (r.get("CodigoMunicipioDane") or "").strip()
            if cod_mun and cod_mun not in territorios:
                depto = (r.get("Departamento") or "").strip() or DESCONOCIDO
                dv = divipola.get(cod_mun, {})
                territorios[cod_mun] = (
                    len(territorios), cod_mun, (r.get("Municipio") or "").strip() or DESCONOCIDO,
                    (r.get("CodigoDeptoDane") or "").strip() or cod_mun[:2],
                    depto, _REGION_MAP.get(depto, DESCONOCIDO),
                    dv.get("tipo", DESCONOCIDO),
                    # DIVIPOLA asigna el código DDD001 a la capital de cada departamento.
                    "Capital departamental" if cod_mun.endswith("001") else "Resto de municipios",
                    dv.get("latitud"), dv.get("longitud"),
                )

            anio = int(r["Anio"])
            codigo = (r.get("Periodo") or "").strip()
            key, periodo, tipo, meses = _periodo(codigo, anio)
            codigo = codigo or str(anio)
            tiempos.setdefault(codigo, (key, codigo, anio, periodo, tipo, _trienio(anio), meses,
                                        _etapa_desagregacion(anio)))

            desag = (r.get("DesagregacionCultivo") or "").strip()
            cultivo = r.get("Cultivo") or DESCONOCIDO
            if desag and desag not in cultivos:
                cultivos[desag] = [
                    len(cultivos), desag, r.get("CodigoCultivo"), cultivo,
                    r.get("GrupoCultivo") or DESCONOCIDO, r.get("Subgrupo") or DESCONOCIDO,
                    _variedad(desag, cultivo),
                    r.get("CicloCultivo") or DESCONOCIDO, r.get("EstadoFisico") or DESCONOCIDO,
                    r.get("NombreCientifico") or DESCONOCIDO, anio, anio,
                ]
            if desag:  # vigencia: primer y último año con registros
                c = cultivos[desag]
                c[10], c[11] = min(c[10], anio), max(c[11], anio)
                cultivos_por_sistema.setdefault(
                    _SISTEMA_POR_DESAGREGACION.get(desag, DESCONOCIDO), set()).add(cultivo)

        desag_por_sistema: dict[str, list] = {}
        for d, sis in _SISTEMA_POR_DESAGREGACION.items():
            desag_por_sistema.setdefault(sis, []).append(d)
        sistemas = [(*s, ", ".join(sorted(cultivos_por_sistema.get(s[1], []))) or "—",
                     ", ".join(desag_por_sistema.get(s[1], [])) or "—") for s in SISTEMAS]

        con.executemany("INSERT INTO dim_territorio VALUES (?,?,?,?,?,?,?,?,?,?)", territorios.values())
        con.executemany("INSERT INTO dim_tiempo VALUES (?,?,?,?,?,?,?,?)", tiempos.values())
        con.executemany("INSERT INTO dim_cultivo VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", cultivos.values())
        con.executemany("INSERT INTO dim_sistema_productivo VALUES (?,?,?,?,?,?)", sistemas)

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


# ============================================================ diccionario
# Rol de cada atributo: Clave · Nivel de jerarquía · Atributo de análisis (se
# puede usar como columna o filtro en el explorador OLAP) · Descriptivo.
DICCIONARIO = [
    {
        "tabla": "dim_territorio", "nombre": "Territorio", "pregunta": "¿Dónde se produce?",
        "icon": "bi-geo-alt-fill",
        "proposito": "Ubica cada hecho en el municipio que lo reporta y permite agregarlo por departamento y "
                     "región natural, comparar capitales con el resto de municipios y situarlo en el mapa.",
        "grano": "1 fila = 1 municipio con registros en EVA (+ miembro 0 «Desconocido»).",
        "jerarquia": "Región → Departamento → Municipio",
        "fuente": "EVA tratado (códigos y nombres DANE) + DIVIPOLA (tipo y coordenadas) + mapeo región de R4.",
        "scd": "Tipo 1 (se sobrescribe): los límites municipales no cambian en 2019–2024.",
        "atributos": [
            ("territorio_key", "INTEGER", "Clave", "Clave sustituta; 0 = Desconocido.", "Generada en la carga"),
            ("cod_municipio", "TEXT(5)", "Clave", "Código DIVIPOLA del municipio (clave natural, UNIQUE).", "EVA · CodigoMunicipioDane"),
            ("municipio", "TEXT", "Nivel de jerarquía", "Nombre del municipio (nivel más detallado).", "EVA · Municipio"),
            ("cod_departamento", "TEXT(2)", "Descriptivo", "Código DIVIPOLA del departamento.", "EVA · CodigoDeptoDane"),
            ("departamento", "TEXT", "Nivel de jerarquía", "Departamento al que pertenece el municipio.", "EVA · Departamento"),
            ("region", "TEXT", "Nivel de jerarquía", "Región natural (Andina, Caribe, Pacífica, Orinoquía, Amazonía).", "Derivado: mapeo departamento → región (R4)"),
            ("tipo_entidad", "TEXT", "Descriptivo", "Municipio, isla o área no municipalizada.", "DIVIPOLA · Tipo"),
            ("capital", "TEXT", "Atributo de análisis", "«Capital departamental» si el código termina en 001; si no, «Resto de municipios».", "Derivado: convención DIVIPOLA"),
            ("latitud", "REAL", "Descriptivo", "Latitud de la cabecera municipal (grados).", "DIVIPOLA · Latitud"),
            ("longitud", "REAL", "Descriptivo", "Longitud de la cabecera municipal (grados).", "DIVIPOLA · Longitud"),
        ],
    },
    {
        "tabla": "dim_tiempo", "nombre": "Tiempo", "pregunta": "¿Cuándo se produce?",
        "icon": "bi-calendar3",
        "proposito": "Ubica cada hecho en su periodo agrícola y permite comparar periodos equivalentes "
                     "(semestres entre sí, trienios de igual duración) y separar los años anteriores y "
                     "posteriores al cambio de desagregación de EVA.",
        "grano": "1 fila = 1 periodo agrícola: semestre A o B (transitorios) o año (plátano, permanente).",
        "jerarquia": "Trienio → Año → Periodo",
        "fuente": "EVA tratado (Anio, Periodo) + atributos derivados del calendario agrícola.",
        "scd": "Estática: el calendario no cambia.",
        "atributos": [
            ("tiempo_key", "INTEGER", "Clave", "Clave inteligente AAAAP (20191 = 2019A, 20192 = 2019B, 20190 = 2019 anual).", "Generada en la carga"),
            ("periodo_codigo", "TEXT", "Nivel de jerarquía", "Código EVA del periodo: 2019A, 2019B o 2019 (clave natural, UNIQUE).", "EVA · Periodo"),
            ("anio", "INTEGER", "Nivel de jerarquía", "Año calendario.", "EVA · Anio"),
            ("periodo", "TEXT", "Atributo de análisis", "Semestre A, Semestre B o Anual: compara semestres entre años.", "Derivado del código"),
            ("tipo_periodo", "TEXT", "Descriptivo", "Semestral o Anual.", "Derivado del código"),
            ("trienio", "TEXT", "Nivel de jerarquía", "2019–2021 o 2022–2024: periodos equivalentes de tres años.", "Derivado del año"),
            ("meses", "TEXT", "Descriptivo", "Meses que cubre el periodo: Ene–Jun, Jul–Dic o Ene–Dic.", "Derivado: calendario EVA"),
            ("etapa_desagregacion", "TEXT", "Atributo de análisis", "2019–2020 (anterior) o 2021–2024 (actual): antes y después del cambio de desagregación del maíz.", "Derivado del año"),
        ],
    },
    {
        "tabla": "dim_cultivo", "nombre": "Cultivo", "pregunta": "¿Qué se produce?",
        "icon": "bi-flower1",
        "proposito": "Identifica el producto de cada hecho al nivel más fino que reporta EVA y permite "
                     "agregarlo por cultivo y grupo, distinguir variedades y el estado físico en que se "
                     "mide la producción, y saber en qué años estuvo vigente cada desagregación.",
        "grano": "1 fila = 1 desagregación de cultivo de EVA (+ miembro 0 «Desconocido»).",
        "jerarquia": "Grupo → Cultivo → Desagregación",
        "fuente": "EVA tratado (catálogo de cultivos) + atributos derivados del nombre y de los hechos.",
        "scd": "Tipo 1 con vigencia (anio_desde / anio_hasta): las desagregaciones que EVA reemplazó se conservan.",
        "atributos": [
            ("cultivo_key", "INTEGER", "Clave", "Clave sustituta; 0 = Desconocido.", "Generada en la carga"),
            ("desagregacion", "TEXT", "Nivel de jerarquía", "Desagregación EVA (clave natural, UNIQUE).", "EVA · DesagregacionCultivo"),
            ("codigo_cultivo", "INTEGER", "Descriptivo", "Código EVA del cultivo.", "EVA · CodigoCultivo"),
            ("cultivo", "TEXT", "Nivel de jerarquía", "Cultivo básico: maíz, arroz, papa, yuca, plátano o frijol.", "EVA · Cultivo"),
            ("grupo", "TEXT", "Nivel de jerarquía", "Grupo de cultivo (cereales, raíces y tubérculos, leguminosas, frutales).", "EVA · GrupoCultivo"),
            ("subgrupo", "TEXT", "Descriptivo", "Subgrupo EVA (p. ej., «Demás frutales» para el plátano).", "EVA · Subgrupo"),
            ("variedad", "TEXT", "Atributo de análisis", "Amarillo, Blanco, Criolla, Todas las variedades, Sin distinguir color o No aplica.", "Derivado del nombre de la desagregación"),
            ("ciclo", "TEXT", "Descriptivo", "Transitorio o Permanente (explica el periodo anual del plátano).", "EVA · CicloCultivo"),
            ("estado_fisico", "TEXT", "Atributo de análisis", "Estado en que se pesa la producción: En fresco, Grano seco o Paddy.", "EVA · EstadoFisico"),
            ("nombre_cientifico", "TEXT", "Descriptivo", "Nombre científico de la especie.", "EVA · NombreCientifico"),
            ("anio_desde", "INTEGER", "Descriptivo", "Primer año con registros de la desagregación.", "Derivado de los hechos"),
            ("anio_hasta", "INTEGER", "Descriptivo", "Último año con registros (vigencia).", "Derivado de los hechos"),
        ],
    },
    {
        "tabla": "dim_sistema_productivo", "nombre": "Sistema productivo", "pregunta": "¿Cómo y para qué se produce?",
        "icon": "bi-gear-wide-connected",
        "proposito": "Separa el nivel tecnológico (maíz y arroz) y el destino (plátano y yuca), que EVA "
                     "codifica dentro del nombre de la desagregación, para compararlos de forma consistente "
                     "antes y después del cambio de desagregación de 2021.",
        "grano": "1 fila = 1 sistema productivo (+ miembro 0 «Desconocido»).",
        "jerarquia": "Criterio → Sistema",
        "fuente": "Diccionario de la carga: 16 desagregaciones EVA → 7 sistemas.",
        "scd": "Estática: catálogo definido en el ETL.",
        "atributos": [
            ("sistema_key", "INTEGER", "Clave", "Clave sustituta; 0 = Desconocido.", "Generada en la carga"),
            ("sistema", "TEXT", "Nivel de jerarquía", "Tecnificado, Tradicional, Consumo interno, Exportación, Consumo en fresco, Industrial o Sin diferenciar (clave natural).", "Derivado de la desagregación"),
            ("criterio", "TEXT", "Nivel de jerarquía", "Nivel tecnológico, Destino o Sin diferenciar.", "Derivado"),
            ("descripcion", "TEXT", "Descriptivo", "Qué agrupa el sistema.", "Diccionario de la carga"),
            ("cultivos", "TEXT", "Descriptivo", "Cultivos a los que aplica el sistema.", "Derivado de los hechos"),
            ("desagregaciones", "TEXT", "Descriptivo", "Desagregaciones EVA que agrupa.", "Diccionario de la carga"),
        ],
    },
]


def dictionary(con: sqlite3.Connection) -> list[dict]:
    """DICCIONARIO con filas por tabla y, por atributo, nº de valores distintos y ejemplos (sin el miembro 0)."""
    out = []
    for d in DICCIONARIO:
        tabla, pk = d["tabla"], d["atributos"][0][0]
        filas = con.execute(f"SELECT COUNT(*) FROM {tabla} WHERE {pk} <> 0").fetchone()[0]
        attrs = []
        for col, tipo, rol, desc, origen in d["atributos"]:
            n = con.execute(f"SELECT COUNT(DISTINCT {col}) FROM {tabla} WHERE {pk} <> 0").fetchone()[0]
            ej = [r[0] for r in con.execute(
                f"SELECT {col}, COUNT(*) c FROM {tabla} WHERE {pk} <> 0 AND {col} IS NOT NULL "
                f"GROUP BY {col} ORDER BY c DESC, {col} LIMIT 3")]
            attrs.append({"col": col, "tipo": tipo, "rol": rol, "desc": desc, "origen": origen,
                          "distintos": n, "ejemplos": [str(e) for e in ej]})
        out.append({**{k: v for k, v in d.items() if k != "atributos"}, "filas": filas, "atributos": attrs})
    return out
