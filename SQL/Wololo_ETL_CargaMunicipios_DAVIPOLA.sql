USE Wololo_ETL;
GO

IF OBJECT_ID(N'tempdb..#Divipola') IS NOT NULL DROP TABLE #Divipola;
CREATE TABLE #Divipola
(
    CodigoDepto  NVARCHAR(10),
    NombreDepto  NVARCHAR(100),
    CodigoMpio   NVARCHAR(10),
    NombreMpio   NVARCHAR(100),
    Tipo         NVARCHAR(50),
    Longitud     NVARCHAR(20),
    Latitud      NVARCHAR(20)
);

BULK INSERT #Divipola
FROM 'C:\Users\Jonat\Documents\Github\Mineria-de-Datos\app\data\DIVIPOLA-_Códigos_municipios_20260921.csv'
WITH (
    FORMAT = 'CSV',
    FIRSTROW = 2,
    CODEPAGE = '65001',
    FIELDTERMINATOR = ',',
    ROWTERMINATOR = '0x0a',
    FIELDQUOTE = '"'
);

INSERT cat.Municipio (CodigoMunicipioDane, CodigoDeptoDane, Departamento, Municipio, Fuente)
SELECT DISTINCT
    LTRIM(RTRIM(CodigoMpio)),
    LTRIM(RTRIM(CodigoDepto)),
    LTRIM(RTRIM(NombreDepto)),
    LTRIM(RTRIM(NombreMpio)),
    N'DIVIPOLA - datos.gov.co'
FROM #Divipola AS d
WHERE NOT EXISTS (
    SELECT 1 FROM cat.Municipio m WHERE m.CodigoMunicipioDane = LTRIM(RTRIM(d.CodigoMpio)));

SELECT COUNT(*) AS TotalMunicipios FROM cat.Municipio;