-- =====================================================================
-- R5 · Consultas de análisis: las cinco operaciones OLAP y las 4 preguntas.
-- Son las mismas que genera app/services/olap.py (la app muestra la SQL
-- ejecutada en cada vista, sección «Consulta SQL ejecutada»).
-- =====================================================================

-- ---------------------------------------------------------------------
-- Vista 1 · Territorial — consulta base Región × Cultivo (producción, t)
SELECT t.region, c.cultivo, SUM(f.produccion_t) AS produccion_t
FROM fact_produccion_agricola f
JOIN dim_territorio t ON t.territorio_key = f.territorio_key
JOIN dim_cultivo c    ON c.cultivo_key    = f.cultivo_key
GROUP BY t.region, c.cultivo;

-- Comparación con R4: % de registros vs. % de producción por región
SELECT t.region,
       ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM fact_produccion_agricola), 1)               AS pct_registros,
       ROUND(100.0 * SUM(f.produccion_t) / (SELECT SUM(produccion_t) FROM fact_produccion_agricola), 1) AS pct_produccion
FROM fact_produccion_agricola f
JOIN dim_territorio t ON t.territorio_key = f.territorio_key
GROUP BY t.region ORDER BY pct_produccion DESC;

-- DRILL-DOWN (Papa): región → departamento (Andina) → municipio (Boyacá)
SELECT t.region, SUM(f.produccion_t) FROM fact_produccion_agricola f
JOIN dim_territorio t ON t.territorio_key = f.territorio_key
JOIN dim_cultivo c ON c.cultivo_key = f.cultivo_key
WHERE c.cultivo = 'Papa' GROUP BY t.region;

SELECT t.departamento, SUM(f.produccion_t) FROM fact_produccion_agricola f
JOIN dim_territorio t ON t.territorio_key = f.territorio_key
JOIN dim_cultivo c ON c.cultivo_key = f.cultivo_key
WHERE c.cultivo = 'Papa' AND t.region = 'Andina' GROUP BY t.departamento ORDER BY 2 DESC;

SELECT t.municipio, SUM(f.produccion_t),
       ROUND(100.0 * SUM(f.produccion_t) / SUM(SUM(f.produccion_t)) OVER (), 1) AS pct_del_departamento
FROM fact_produccion_agricola f
JOIN dim_territorio t ON t.territorio_key = f.territorio_key
JOIN dim_cultivo c ON c.cultivo_key = f.cultivo_key
WHERE c.cultivo = 'Papa' AND t.region = 'Andina' AND t.departamento = 'Boyacá'
GROUP BY t.municipio ORDER BY 2 DESC;

-- PIVOT: la misma matriz con Cultivo en filas y Región en columnas
SELECT c.cultivo, t.region, SUM(f.produccion_t) AS produccion_t
FROM fact_produccion_agricola f
JOIN dim_territorio t ON t.territorio_key = f.territorio_key
JOIN dim_cultivo c    ON c.cultivo_key    = f.cultivo_key
GROUP BY c.cultivo, t.region;

-- ---------------------------------------------------------------------
-- Vista 2 · Temporal — trienios equivalentes por cultivo
SELECT c.cultivo, tm.trienio, SUM(f.produccion_t) AS produccion_t, COUNT(*) AS registros,
       SUM(f.produccion_t) / SUM(f.area_cosechada_ha) AS rendimiento_t_ha
FROM fact_produccion_agricola f
JOIN dim_tiempo tm ON tm.tiempo_key = f.tiempo_key
JOIN dim_cultivo c ON c.cultivo_key = f.cultivo_key
GROUP BY c.cultivo, tm.trienio;

-- Maíz: registros, municipios únicos y producción por año + desagregaciones
SELECT tm.anio, COUNT(*) AS registros, COUNT(DISTINCT f.territorio_key) AS municipios,
       SUM(f.produccion_t) AS produccion_t, COUNT(DISTINCT c.desagregacion) AS desagregaciones
FROM fact_produccion_agricola f
JOIN dim_tiempo tm ON tm.tiempo_key = f.tiempo_key
JOIN dim_cultivo c ON c.cultivo_key = f.cultivo_key
WHERE c.cultivo = 'Maíz' GROUP BY tm.anio;

-- ROLL-UP (Arroz): periodo → año → trienio
SELECT tm.periodo_codigo, SUM(f.produccion_t) FROM fact_produccion_agricola f
JOIN dim_tiempo tm ON tm.tiempo_key = f.tiempo_key JOIN dim_cultivo c ON c.cultivo_key = f.cultivo_key
WHERE c.cultivo = 'Arroz' GROUP BY tm.periodo_codigo;
SELECT tm.anio, SUM(f.produccion_t) FROM fact_produccion_agricola f
JOIN dim_tiempo tm ON tm.tiempo_key = f.tiempo_key JOIN dim_cultivo c ON c.cultivo_key = f.cultivo_key
WHERE c.cultivo = 'Arroz' GROUP BY tm.anio;
SELECT tm.trienio, SUM(f.produccion_t) FROM fact_produccion_agricola f
JOIN dim_tiempo tm ON tm.tiempo_key = f.tiempo_key JOIN dim_cultivo c ON c.cultivo_key = f.cultivo_key
WHERE c.cultivo = 'Arroz' GROUP BY tm.trienio;

-- ---------------------------------------------------------------------
-- Vista 3 · Sistemas — SLICE Cultivo = Maíz: rendimiento por región y sistema
SELECT t.region, s.sistema,
       SUM(f.produccion_t) / NULLIF(SUM(f.area_cosechada_ha), 0) AS rendimiento_t_ha,
       SUM(f.area_cosechada_ha) AS area_cosechada_ha
FROM fact_produccion_agricola f
JOIN dim_territorio t         ON t.territorio_key = f.territorio_key
JOIN dim_cultivo c            ON c.cultivo_key    = f.cultivo_key
JOIN dim_sistema_productivo s ON s.sistema_key    = f.sistema_key
WHERE c.cultivo = 'Maíz'
GROUP BY t.region, s.sistema;

-- ---------------------------------------------------------------------
-- Vista 4 · Cosecha — DICE Cultivo = Arroz × Región = Caribe: tasa por departamento y año
SELECT t.departamento, tm.anio,
       100.0 * SUM(f.area_cosechada_ha) / NULLIF(SUM(f.area_sembrada_ha), 0) AS tasa_cosecha_pct,
       SUM(f.area_sembrada_ha) - SUM(f.area_cosechada_ha)                   AS area_no_cosechada_ha
FROM fact_produccion_agricola f
JOIN dim_territorio t ON t.territorio_key = f.territorio_key
JOIN dim_tiempo tm    ON tm.tiempo_key    = f.tiempo_key
JOIN dim_cultivo c    ON c.cultivo_key    = f.cultivo_key
WHERE c.cultivo = 'Arroz' AND t.region = 'Caribe'
GROUP BY t.departamento, tm.anio;

-- Sensibilidad de calidad: la misma consulta solo con filas coherentes
SELECT t.region, 100.0 * SUM(f.area_cosechada_ha) / SUM(f.area_sembrada_ha) AS tasa_cosecha_pct
FROM fact_produccion_agricola f JOIN dim_territorio t ON t.territorio_key = f.territorio_key
WHERE f.area_incoherente = 0 GROUP BY t.region;
