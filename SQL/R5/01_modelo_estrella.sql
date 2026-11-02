-- =====================================================================
-- R5 · Análisis multidimensional — Modelo estrella (SQLite)
-- Data mart: producción agrícola municipal de cultivos básicos (EVA)
--
-- Granularidad de fact_produccion_agricola:
--   1 fila = 1 municipio × 1 desagregación de cultivo × 1 periodo agrícola
--   (semestre A/B para transitorios, año para permanentes).
--
-- Este script lo ejecuta scripts/R5/build_star.py (app/services/dw.py),
-- que luego carga las tablas desde app/static/data/R2/eva_basicos.json.
-- La clave 0 de cada dimensión es el miembro "Desconocido".
-- =====================================================================
PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS fact_produccion_agricola;
DROP TABLE IF EXISTS dim_territorio;
DROP TABLE IF EXISTS dim_tiempo;
DROP TABLE IF EXISTS dim_cultivo;
DROP TABLE IF EXISTS dim_sistema_productivo;

-- Jerarquía: region → departamento → municipio
CREATE TABLE dim_territorio (
    territorio_key      INTEGER PRIMARY KEY,
    cod_municipio       TEXT    NOT NULL UNIQUE,   -- DIVIPOLA 5 dígitos
    municipio           TEXT    NOT NULL,
    cod_departamento    TEXT    NOT NULL,          -- DIVIPOLA 2 dígitos
    departamento        TEXT    NOT NULL,
    region              TEXT    NOT NULL           -- región natural (Andina, Caribe, …)
);

-- Jerarquía: anio → periodo (semestre A / semestre B / anual)
CREATE TABLE dim_tiempo (
    tiempo_key          INTEGER PRIMARY KEY,       -- AAAAP: 20191 = 2019A, 20192 = 2019B, 20190 = 2019 anual
    periodo_codigo      TEXT    NOT NULL UNIQUE,   -- '2019A', '2019B', '2019'
    anio                INTEGER NOT NULL,
    periodo             TEXT    NOT NULL,          -- 'Semestre A' | 'Semestre B' | 'Anual'
    tipo_periodo        TEXT    NOT NULL,          -- 'Semestral' | 'Anual'
    trienio             TEXT    NOT NULL           -- '2019–2021' | '2022–2024' (periodos equivalentes de 3 años)
);

-- Jerarquía: grupo → cultivo → desagregacion
CREATE TABLE dim_cultivo (
    cultivo_key         INTEGER PRIMARY KEY,
    desagregacion       TEXT    NOT NULL UNIQUE,
    codigo_cultivo      INTEGER,
    cultivo             TEXT    NOT NULL,
    grupo               TEXT    NOT NULL,
    ciclo               TEXT    NOT NULL,          -- 'Transitorio' | 'Permanente'
    estado_fisico       TEXT    NOT NULL,
    nombre_cientifico   TEXT    NOT NULL
);

-- Jerarquía: criterio → sistema
CREATE TABLE dim_sistema_productivo (
    sistema_key         INTEGER PRIMARY KEY,
    sistema             TEXT    NOT NULL UNIQUE,   -- Tecnificado, Tradicional, Exportación, …
    criterio            TEXT    NOT NULL,          -- 'Nivel tecnológico' | 'Destino' | 'Sin diferenciar'
    descripcion         TEXT    NOT NULL
);

CREATE TABLE fact_produccion_agricola (
    hecho_id            INTEGER PRIMARY KEY,
    territorio_key      INTEGER NOT NULL REFERENCES dim_territorio (territorio_key),
    tiempo_key          INTEGER NOT NULL REFERENCES dim_tiempo (tiempo_key),
    cultivo_key         INTEGER NOT NULL REFERENCES dim_cultivo (cultivo_key),
    sistema_key         INTEGER NOT NULL REFERENCES dim_sistema_productivo (sistema_key),
    area_sembrada_ha    REAL    NOT NULL,          -- aditiva
    area_cosechada_ha   REAL    NOT NULL,          -- aditiva
    produccion_t        REAL    NOT NULL,          -- aditiva
    rendimiento_reportado_t_ha REAL,               -- NO aditiva: solo trazabilidad
    area_incoherente    INTEGER NOT NULL DEFAULT 0 -- 1 si cosechada > sembrada (bandera R2)
        CHECK (area_incoherente IN (0, 1)),
    -- La granularidad se garantiza con esta restricción: no puede haber dos
    -- hechos del mismo municipio, desagregación y periodo.
    UNIQUE (territorio_key, cultivo_key, tiempo_key)
);

CREATE INDEX ix_fact_territorio ON fact_produccion_agricola (territorio_key);
CREATE INDEX ix_fact_tiempo     ON fact_produccion_agricola (tiempo_key);
CREATE INDEX ix_fact_cultivo    ON fact_produccion_agricola (cultivo_key);
CREATE INDEX ix_fact_sistema    ON fact_produccion_agricola (sistema_key);
