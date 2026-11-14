/* =============================================================================
   Etapa 3 · Base de datos Wololo_ETL
   04 — Consultas de verificación (evidencias del informe)
   Cambiar las claves de lote según la iteración que se quiera revisar.
============================================================================= */
USE Wololo_ETL;
GO

/* 1. Lotes ejecutados y su estado */
SELECT IdLote, LoteClave, Dataset, Iteracion, Estado, VecesAbierto, FechaApertura, FechaCierre
FROM etl.Lote ORDER BY IdLote;

/* 2. Conciliación EVA: Recibidos = Aceptados + Revisión (SinExplicar debe ser 0) */
SELECT l.LoteClave,
       COUNT(*)                                                       AS Recibidos,
       SUM(CASE WHEN c.IdStg IS NOT NULL THEN 1 ELSE 0 END)           AS Aceptados,
       SUM(CASE WHEN r.IdStg IS NOT NULL THEN 1 ELSE 0 END)           AS Revision,
       SUM(CASE WHEN c.IdStg IS NULL AND r.IdStg IS NULL THEN 1 ELSE 0 END) AS SinExplicar
FROM dbo.stg_EVA s
JOIN etl.Lote l ON l.IdLote = s.IdLote
LEFT JOIN dbo.EVA_Limpios c ON c.IdStg = s.IdStg AND c.IdLote = s.IdLote
LEFT JOIN (SELECT DISTINCT IdLote, IdStg FROM dbo.EVA_Revision) r ON r.IdStg = s.IdStg AND r.IdLote = s.IdLote
GROUP BY l.LoteClave ORDER BY l.LoteClave;

/* 3. Conciliación FAOSTAT (por dataset de origen) */
SELECT l.LoteClave, s.Dataset,
       COUNT(*)                                                       AS Recibidos,
       SUM(CASE WHEN c.IdStg IS NOT NULL THEN 1 ELSE 0 END)           AS Aceptados,
       SUM(CASE WHEN r.IdStg IS NOT NULL THEN 1 ELSE 0 END)           AS Revision,
       SUM(CASE WHEN c.IdStg IS NULL AND r.IdStg IS NULL THEN 1 ELSE 0 END) AS SinExplicar
FROM dbo.stg_FAOSTAT s
JOIN etl.Lote l ON l.IdLote = s.IdLote
LEFT JOIN dbo.FAOSTAT_Limpios c ON c.IdStg = s.IdStg AND c.IdLote = s.IdLote
LEFT JOIN (SELECT DISTINCT IdLote, IdStg FROM dbo.FAOSTAT_Revision) r ON r.IdStg = s.IdStg AND r.IdLote = s.IdLote
GROUP BY l.LoteClave, s.Dataset ORDER BY l.LoteClave, s.Dataset;

/* 4. Registros en revisión por categoría y regla */
SELECT l.LoteClave, 'EVA' AS Paquete, r.Categoria, g.Codigo, COUNT(*) AS Registros
FROM dbo.EVA_Revision r JOIN etl.Lote l ON l.IdLote = r.IdLote LEFT JOIN cat.Regla g ON g.IdRegla = r.IdRegla
GROUP BY l.LoteClave, r.Categoria, g.Codigo
UNION ALL
SELECT l.LoteClave, 'FAOSTAT', r.Categoria, g.Codigo, COUNT(*)
FROM dbo.FAOSTAT_Revision r JOIN etl.Lote l ON l.IdLote = r.IdLote LEFT JOIN cat.Regla g ON g.IdRegla = r.IdRegla
GROUP BY l.LoteClave, r.Categoria, g.Codigo
ORDER BY 1, 2, 5 DESC;

/* 5. Banderas de atípicos y unidades en los aceptados */
SELECT l.LoteClave,
       SUM(CAST(FlagAtipicoAreaSembrada  AS INT)) AS AtipicoAreaSembrada,
       SUM(CAST(FlagAtipicoAreaCosechada AS INT)) AS AtipicoAreaCosechada,
       SUM(CAST(FlagAtipicoProduccion    AS INT)) AS AtipicoProduccion,
       SUM(CAST(FlagAtipicoRendimiento   AS INT)) AS AtipicoRendimiento,
       SUM(CASE WHEN FlagAtipicoAreaSembrada | FlagAtipicoAreaCosechada | FlagAtipicoProduccion | FlagAtipicoRendimiento = 1
                THEN 1 ELSE 0 END)                AS ConAlgunaBandera
FROM dbo.EVA_Limpios c JOIN etl.Lote l ON l.IdLote = c.IdLote
GROUP BY l.LoteClave;

SELECT l.LoteClave, c.Dataset,
       SUM(CAST(FlagAtipicoValor  AS INT)) AS AtipicoValor,
       SUM(CAST(FlagUnidadAtipica AS INT)) AS UnidadDistinta,
       SUM(CASE WHEN c.Valor IS NULL THEN 1 ELSE 0 END) AS ValorNulo
FROM dbo.FAOSTAT_Limpios c JOIN etl.Lote l ON l.IdLote = c.IdLote
GROUP BY l.LoteClave, c.Dataset;

/* 6. Idempotencia: ejecutar el paquete dos veces con la misma clave y comparar */
DECLARE @Clave NVARCHAR(60) = N'EVA-I3';
DECLARE @IdLote INT = (SELECT IdLote FROM etl.Lote WHERE LoteClave = @Clave);

SELECT (SELECT COUNT(*) FROM dbo.stg_EVA      WHERE IdLote = @IdLote) AS Staging,
       (SELECT COUNT(*) FROM dbo.EVA_Limpios  WHERE IdLote = @IdLote) AS Limpios,
       (SELECT COUNT(*) FROM dbo.EVA_Revision WHERE IdLote = @IdLote) AS Revision,
       (SELECT VecesAbierto FROM etl.Lote     WHERE IdLote = @IdLote) AS VecesAbierto;

SELECT CodigoMunicipioDane, CodigoCultivo, DesagregacionCultivo, Anio, Periodo, COUNT(*) AS Repeticiones
FROM dbo.EVA_Limpios WHERE IdLote = @IdLote
GROUP BY CodigoMunicipioDane, CodigoCultivo, DesagregacionCultivo, Anio, Periodo
HAVING COUNT(*) > 1;                                   -- debe devolver 0 filas

SELECT Fecha, Accion, Descripcion, PackageName, SourceName
FROM audit.Log WHERE IdLote = @IdLote ORDER BY IdLog;  -- LOTE_ABIERTO, LOTE_CERRADO, LOTE_REABIERTO, LOTE_CERRADO

/* 7. Ejemplos antes / después */
SELECT TOP 5 s.IdStg, s.Municipio, s.Produccion AS ProduccionOriginal, c.Produccion AS ProduccionLimpia
FROM dbo.stg_EVA s JOIN dbo.EVA_Limpios c ON c.IdStg = s.IdStg
WHERE s.IdLote = @IdLote AND s.Produccion LIKE N'%.%,%';

SELECT TOP 5 IdStg, Categoria, Motivo, CampoAfectado, ValorOriginal
FROM dbo.EVA_Revision WHERE IdLote = @IdLote;

/* 8. Control de longitud de Producto en staging FAOSTAT (ver problema pendiente) */
SELECT Dataset, MAX(LEN(Producto)) AS MaxLargoProducto, SUM(CASE WHEN LEN(Producto) = 50 THEN 1 ELSE 0 END) AS Con50Caracteres
FROM dbo.stg_FAOSTAT GROUP BY Dataset;
