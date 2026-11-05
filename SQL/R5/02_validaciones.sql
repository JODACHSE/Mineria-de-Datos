-- =====================================================================
-- R5 · Validaciones del modelo estrella (SQLite)
-- Ejecutar: sqlite3 app/data/R5/wololo_dw.sqlite < SQL/R5/02_validaciones.sql
-- La app ejecuta las mismas comprobaciones (app/services/olap.py → validations)
-- y además compara con el JSON tratado de R2; se muestran en /r5#validaciones.
-- =====================================================================

-- 1. Unicidad de las claves de las dimensiones (filas = claves = claves naturales)
SELECT 'dim_territorio', COUNT(*), COUNT(DISTINCT territorio_key), COUNT(DISTINCT cod_municipio) FROM dim_territorio;
SELECT 'dim_tiempo', COUNT(*), COUNT(DISTINCT tiempo_key), COUNT(DISTINCT periodo_codigo) FROM dim_tiempo;
SELECT 'dim_cultivo', COUNT(*), COUNT(DISTINCT cultivo_key), COUNT(DISTINCT desagregacion) FROM dim_cultivo;
SELECT 'dim_sistema_productivo', COUNT(*), COUNT(DISTINCT sistema_key), COUNT(DISTINCT sistema) FROM dim_sistema_productivo;

-- 2. Integridad referencial: hechos sin fila en la dimensión (esperado 0)
SELECT 'huerfanos_territorio', COUNT(*) FROM fact_produccion_agricola f
  LEFT JOIN dim_territorio d ON d.territorio_key = f.territorio_key WHERE d.territorio_key IS NULL;
SELECT 'huerfanos_tiempo', COUNT(*) FROM fact_produccion_agricola f
  LEFT JOIN dim_tiempo d ON d.tiempo_key = f.tiempo_key WHERE d.tiempo_key IS NULL;
SELECT 'huerfanos_cultivo', COUNT(*) FROM fact_produccion_agricola f
  LEFT JOIN dim_cultivo d ON d.cultivo_key = f.cultivo_key WHERE d.cultivo_key IS NULL;
SELECT 'huerfanos_sistema', COUNT(*) FROM fact_produccion_agricola f
  LEFT JOIN dim_sistema_productivo d ON d.sistema_key = f.sistema_key WHERE d.sistema_key IS NULL;

-- 3. Duplicados en la granularidad (esperado 0) y filas tras los JOIN (esperado = hechos = 48.932)
SELECT 'duplicados_grano', COUNT(*) FROM (
  SELECT 1 FROM fact_produccion_agricola GROUP BY territorio_key, cultivo_key, tiempo_key HAVING COUNT(*) > 1);
SELECT 'filas_tras_join', COUNT(*) FROM fact_produccion_agricola f
  JOIN dim_territorio t ON t.territorio_key = f.territorio_key
  JOIN dim_tiempo tm ON tm.tiempo_key = f.tiempo_key
  JOIN dim_cultivo c ON c.cultivo_key = f.cultivo_key
  JOIN dim_sistema_productivo s ON s.sistema_key = f.sistema_key;

-- 4. Faltantes y categorías desconocidas
SELECT 'hechos_desconocidos', COUNT(*) FROM fact_produccion_agricola
  WHERE territorio_key = 0 OR cultivo_key = 0 OR sistema_key = 0;
SELECT 'municipios_sin_region', COUNT(*) FROM dim_territorio WHERE region = 'Desconocido' AND territorio_key <> 0;
-- Faltante (NULL = no hay dato) ≠ desconocido (clave 0 = categoría sin identificar) ≠ respuesta negativa (0 reportado)
SELECT 'medidas_faltantes', COUNT(*) FROM fact_produccion_agricola                          -- 0
  WHERE area_sembrada_ha IS NULL OR area_cosechada_ha IS NULL OR produccion_t IS NULL;
SELECT 'area_incoherente', SUM(area_incoherente) FROM fact_produccion_agricola;            -- 6.700 en el origen
SELECT 'area_cosechada_cero', COUNT(*) FROM fact_produccion_agricola WHERE area_cosechada_ha = 0; -- 2.298: sin cosecha reportada

-- 5. Coherencia de conteos y agregaciones (comparar con el JSON tratado)
SELECT 'registros', COUNT(*) FROM fact_produccion_agricola;                                 -- 48.932
SELECT 'produccion_total_t', ROUND(SUM(produccion_t), 2) FROM fact_produccion_agricola;     -- 97.576.401,49
SELECT 'area_sembrada_total_ha', ROUND(SUM(area_sembrada_ha), 2) FROM fact_produccion_agricola; -- 13.339.207,23
SELECT 'municipios_unicos', COUNT(DISTINCT territorio_key) FROM fact_produccion_agricola;    -- 1.098
SELECT 'produccion_maiz_2024_t', ROUND(SUM(f.produccion_t), 2)                              -- 1.345.832,10
  FROM fact_produccion_agricola f
  JOIN dim_cultivo c ON c.cultivo_key = f.cultivo_key
  JOIN dim_tiempo tm ON tm.tiempo_key = f.tiempo_key
  WHERE c.cultivo = 'Maíz' AND tm.anio = 2024;
-- Diferencia explicada: rendimiento ponderado (7,77) vs. promedio simple del campo reportado (5,60)
SELECT 'rendimiento_ponderado', ROUND(SUM(produccion_t) / SUM(area_cosechada_ha), 2),
       'promedio_simple', ROUND(AVG(rendimiento_reportado_t_ha), 2)
  FROM fact_produccion_agricola;
