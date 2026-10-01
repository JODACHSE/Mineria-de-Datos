/* =============================================================================
   Etapa 3 · Base de datos Wololo_ETL
   01 — Esquemas y tablas usados por EVA.dtsx y FAOSTAT.dtsx

   Las columnas y tipos de stg_*, *_Limpios y *_Revision se tomaron de los
   metadatos externos (externalMetadataColumns) de los destinos OLE DB de los
   paquetes, para que el mapeo de SSIS coincida sin advertencias.
   Sin usuarios ni contraseñas: la conexión usa autenticación de Windows.
============================================================================= */
IF DB_ID(N'Wololo_ETL') IS NULL
    CREATE DATABASE Wololo_ETL;
GO
USE Wololo_ETL;
GO

IF SCHEMA_ID(N'etl')   IS NULL EXEC(N'CREATE SCHEMA etl');
IF SCHEMA_ID(N'audit') IS NULL EXEC(N'CREATE SCHEMA audit');
IF SCHEMA_ID(N'cat')   IS NULL EXEC(N'CREATE SCHEMA cat');
GO

/* ---------------------------------------------------------------- control */
IF OBJECT_ID(N'etl.Lote') IS NULL
CREATE TABLE etl.Lote (
    IdLote            INT IDENTITY(1,1) PRIMARY KEY,
    LoteClave         NVARCHAR(60)  NOT NULL CONSTRAINT UQ_Lote_Clave UNIQUE,
    Dataset           NVARCHAR(12)  NOT NULL,
    Iteracion         INT           NOT NULL,
    ReglasVersion     NVARCHAR(10)  NOT NULL,
    Tipo              NVARCHAR(10)  NOT NULL CONSTRAINT DF_Lote_Tipo DEFAULT (N'REAL'),
    ArchivoOrigen     NVARCHAR(1000) NULL,
    Estado            NVARCHAR(12)  NOT NULL CONSTRAINT DF_Lote_Estado DEFAULT (N'ABIERTO'),
    FechaApertura     DATETIME2(0)  NOT NULL CONSTRAINT DF_Lote_FApertura DEFAULT (SYSDATETIME()),
    FechaCierre       DATETIME2(0)  NULL,
    VecesAbierto      INT           NOT NULL CONSTRAINT DF_Lote_Veces DEFAULT (1)
);

IF OBJECT_ID(N'audit.Log') IS NULL
CREATE TABLE audit.Log (
    IdLog             BIGINT IDENTITY(1,1) PRIMARY KEY,
    Fecha             DATETIME2(3)  NOT NULL CONSTRAINT DF_Log_Fecha DEFAULT (SYSDATETIME()),
    Accion            NVARCHAR(30)  NOT NULL,          -- LOTE_ABIERTO, LOTE_REABIERTO, LOTE_CERRADO, ERROR_PAQUETE
    Descripcion       NVARCHAR(2000) NULL,
    IdLote            INT           NULL,
    Tabla             NVARCHAR(128) NULL,
    IdRegistro        BIGINT        NULL,
    ValorAnterior     NVARCHAR(400) NULL,
    ValorNuevo        NVARCHAR(400) NULL,
    Usuario           NVARCHAR(128) NOT NULL CONSTRAINT DF_Log_Usuario DEFAULT (SUSER_SNAME()),
    TipoActor         NVARCHAR(10)  NULL,              -- SSIS / USUARIO
    Mecanismo         NVARCHAR(15)  NULL,              -- PAQUETE / TAREA / MANUAL
    PackageName       NVARCHAR(128) NULL,
    SourceName        NVARCHAR(128) NULL,
    ExecutionGUID     NVARCHAR(50)  NULL
);
GO

/* --------------------------------------------------------------- catálogos */
IF OBJECT_ID(N'cat.Municipio') IS NULL
CREATE TABLE cat.Municipio (
    CodigoMunicipioDane CHAR(5)       NOT NULL PRIMARY KEY,   -- CHAR para conservar el cero inicial (05030)
    CodigoDeptoDane     CHAR(2)       NOT NULL,
    Departamento        NVARCHAR(100) NOT NULL,
    Municipio           NVARCHAR(150) NOT NULL
);

IF OBJECT_ID(N'cat.Regla') IS NULL
CREATE TABLE cat.Regla (
    IdRegla        INT IDENTITY(1,1) PRIMARY KEY,
    Familia        NVARCHAR(10)  NOT NULL,          -- EVA / FAOSTAT
    Codigo         NVARCHAR(8)   NOT NULL,
    Categoria      VARCHAR(20)   NOT NULL,
    Descripcion    NVARCHAR(400) NOT NULL,
    Accion         NVARCHAR(200) NOT NULL,
    ReglasVersion  NVARCHAR(10)  NOT NULL,
    Activa         BIT           NOT NULL CONSTRAINT DF_Regla_Activa DEFAULT (1),
    CONSTRAINT UQ_Regla UNIQUE (Familia, Codigo, ReglasVersion)
);

IF OBJECT_ID(N'cat.LimiteIQR') IS NULL
CREATE TABLE cat.LimiteIQR (
    IdLimite        INT IDENTITY(1,1) PRIMARY KEY,
    IdLote          INT            NOT NULL,
    Dataset         VARCHAR(12)    NOT NULL,
    Campo           NVARCHAR(30)   NOT NULL,
    GrupoClave      NVARCHAR(200)  NOT NULL,        -- Cultivo (EVA) o CodigoProducto|CodigoElemento (FAOSTAT)
    N               INT            NULL,
    Q1              DECIMAL(20,4)  NULL,
    Q3              DECIMAL(20,4)  NULL,
    LimiteInferior  DECIMAL(20,4)  NULL,
    LimiteSuperior  DECIMAL(20,4)  NULL
);

IF OBJECT_ID(N'cat.UnidadReferencia') IS NULL
CREATE TABLE cat.UnidadReferencia (
    IdUnidadRef     INT IDENTITY(1,1) PRIMARY KEY,
    IdLote          INT            NOT NULL,
    Dataset         VARCHAR(12)    NOT NULL,
    CodigoProducto  NVARCHAR(20)   NOT NULL,
    CodigoElemento  NVARCHAR(10)   NOT NULL,
    UnidadModal     NVARCHAR(50)   NOT NULL,
    NFilas          INT            NOT NULL
);
GO

/* ------------------------------------------------------------------- EVA */
IF OBJECT_ID(N'dbo.stg_EVA') IS NULL
CREATE TABLE dbo.stg_EVA (
    IdStg                BIGINT IDENTITY(1,1) PRIMARY KEY,
    IdLote               INT            NOT NULL,
    ArchivoOrigen        NVARCHAR(260)  NULL,
    NumeroFila           INT            NULL,
    CodigoDeptoDane      NVARCHAR(50)   NULL,
    Departamento         NVARCHAR(255)  NULL,
    CodigoMunicipioDane  NVARCHAR(50)   NULL,
    Municipio            NVARCHAR(255)  NULL,
    GrupoCultivo         NVARCHAR(255)  NULL,
    Subgrupo             NVARCHAR(255)  NULL,
    Cultivo              NVARCHAR(255)  NULL,
    DesagregacionCultivo NVARCHAR(255)  NULL,
    Anio                 NVARCHAR(50)   NULL,
    Periodo              NVARCHAR(50)   NULL,
    AreaSembrada         NVARCHAR(50)   NULL,
    AreaCosechada        NVARCHAR(50)   NULL,
    Produccion           NVARCHAR(50)   NULL,
    Rendimiento          NVARCHAR(50)   NULL,
    CicloCultivo         NVARCHAR(255)  NULL,
    EstadoFisico         NVARCHAR(255)  NULL,
    CodigoCultivo        NVARCHAR(50)   NULL,
    NombreCientifico     NVARCHAR(255)  NULL,
    FechaCreacion        DATETIME2(0)   NOT NULL CONSTRAINT DF_stgEVA_FC DEFAULT (SYSDATETIME()),
    FechaActualizacion   DATETIME2(0)   NULL
);

IF OBJECT_ID(N'dbo.EVA_Limpios') IS NULL
CREATE TABLE dbo.EVA_Limpios (
    IdEvaLimpio              BIGINT IDENTITY(1,1) PRIMARY KEY,
    IdLote                   INT            NOT NULL,
    IdStg                    BIGINT         NOT NULL,
    CodigoDeptoDane          CHAR(2)        NOT NULL,
    Departamento             NVARCHAR(100)  NOT NULL,
    CodigoMunicipioDane      CHAR(5)        NOT NULL,
    Municipio                NVARCHAR(150)  NOT NULL,
    GrupoCultivo             NVARCHAR(100)  NULL,
    Subgrupo                 NVARCHAR(100)  NULL,
    Cultivo                  NVARCHAR(60)   NOT NULL,
    DesagregacionCultivo     NVARCHAR(150)  NULL,
    Anio                     SMALLINT       NOT NULL,
    Periodo                  CHAR(5)        NOT NULL,
    AreaSembrada             DECIMAL(14,2)  NOT NULL CONSTRAINT CK_EVAL_AS CHECK (AreaSembrada  >= 0),
    AreaCosechada            DECIMAL(14,2)  NOT NULL CONSTRAINT CK_EVAL_AC CHECK (AreaCosechada >= 0),
    Produccion               DECIMAL(16,2)  NOT NULL CONSTRAINT CK_EVAL_PR CHECK (Produccion    >= 0),
    Rendimiento              DECIMAL(12,2)  NOT NULL CONSTRAINT CK_EVAL_RE CHECK (Rendimiento   >= 0),
    CicloCultivo             NVARCHAR(30)   NULL,
    EstadoFisico             NVARCHAR(50)   NULL,
    CodigoCultivo            VARCHAR(20)    NULL,
    NombreCientifico         NVARCHAR(150)  NULL,
    FlagAreaIncoherente      BIT NOT NULL CONSTRAINT DF_EVAL_F0 DEFAULT (0),
    FlagAtipicoAreaSembrada  BIT NOT NULL CONSTRAINT DF_EVAL_F1 DEFAULT (0),
    FlagAtipicoAreaCosechada BIT NOT NULL CONSTRAINT DF_EVAL_F2 DEFAULT (0),
    FlagAtipicoProduccion    BIT NOT NULL CONSTRAINT DF_EVAL_F3 DEFAULT (0),
    FlagAtipicoRendimiento   BIT NOT NULL CONSTRAINT DF_EVAL_F4 DEFAULT (0),
    FechaCreacion            DATETIME2(0)   NOT NULL CONSTRAINT DF_EVAL_FC DEFAULT (SYSDATETIME()),
    FechaActualizacion       DATETIME2(0)   NULL
);

IF OBJECT_ID(N'dbo.EVA_Revision') IS NULL
CREATE TABLE dbo.EVA_Revision (
    IdEvaRevision        BIGINT IDENTITY(1,1) PRIMARY KEY,
    IdLote               INT            NOT NULL,
    IdStg                BIGINT         NOT NULL,
    IdRegla              INT            NULL,
    Categoria            VARCHAR(20)    NOT NULL,
    Motivo               NVARCHAR(400)  NOT NULL,
    CampoAfectado        NVARCHAR(100)  NULL,
    ValorOriginal        NVARCHAR(255)  NULL,
    CodigoDeptoDane      NVARCHAR(50)   NULL,
    Departamento         NVARCHAR(255)  NULL,
    CodigoMunicipioDane  NVARCHAR(50)   NULL,
    Municipio            NVARCHAR(255)  NULL,
    GrupoCultivo         NVARCHAR(255)  NULL,
    Subgrupo             NVARCHAR(255)  NULL,
    Cultivo              NVARCHAR(255)  NULL,
    DesagregacionCultivo NVARCHAR(255)  NULL,
    Anio                 NVARCHAR(50)   NULL,
    Periodo              NVARCHAR(50)   NULL,
    AreaSembrada         NVARCHAR(50)   NULL,
    AreaCosechada        NVARCHAR(50)   NULL,
    Produccion           NVARCHAR(50)   NULL,
    Rendimiento          NVARCHAR(50)   NULL,
    CicloCultivo         NVARCHAR(255)  NULL,
    EstadoFisico         NVARCHAR(255)  NULL,
    CodigoCultivo        NVARCHAR(50)   NULL,
    NombreCientifico     NVARCHAR(255)  NULL,
    EstadoRevision       VARCHAR(12)    NOT NULL CONSTRAINT DF_EVAR_Estado DEFAULT ('PENDIENTE'),
    Resolucion           NVARCHAR(400)  NULL,
    RevisadoPor          NVARCHAR(128)  NULL,
    FechaRevision        DATETIME2(0)   NULL,
    FechaCreacion        DATETIME2(0)   NOT NULL CONSTRAINT DF_EVAR_FC DEFAULT (SYSDATETIME()),
    FechaActualizacion   DATETIME2(0)   NULL
);
GO

/* --------------------------------------------------------------- FAOSTAT */
IF OBJECT_ID(N'dbo.stg_FAOSTAT') IS NULL
CREATE TABLE dbo.stg_FAOSTAT (
    IdStg              BIGINT IDENTITY(1,1) PRIMARY KEY,
    IdLote             INT            NOT NULL,
    Dataset            VARCHAR(12)    NOT NULL,        -- QCL / QCLBasicos / FS
    ArchivoOrigen      NVARCHAR(260)  NULL,
    NumeroFila         INT            NULL,
    CodigoAmbito       NVARCHAR(50)   NULL,
    Ambito             NVARCHAR(255)  NULL,
    CodigoArea         NVARCHAR(50)   NULL,
    Area               NVARCHAR(255)  NULL,
    CodigoElemento     NVARCHAR(50)   NULL,
    Elemento           NVARCHAR(255)  NULL,
    CodigoProducto     NVARCHAR(50)   NULL,
    Producto           NVARCHAR(500)  NULL,
    CodigoAnio         NVARCHAR(50)   NULL,
    Anio               NVARCHAR(50)   NULL,
    Unidad             NVARCHAR(100)  NULL,
    Valor              NVARCHAR(100)  NULL,
    FechaCreacion      DATETIME2(0)   NOT NULL CONSTRAINT DF_stgFAO_FC DEFAULT (SYSDATETIME()),
    FechaActualizacion DATETIME2(0)   NULL
);

IF OBJECT_ID(N'dbo.FAOSTAT_Limpios') IS NULL
CREATE TABLE dbo.FAOSTAT_Limpios (
    IdFaostatLimpio    BIGINT IDENTITY(1,1) PRIMARY KEY,
    IdLote             INT            NOT NULL,
    IdStg              BIGINT         NOT NULL,
    Dataset            VARCHAR(12)    NOT NULL,
    CodigoAmbito       VARCHAR(10)    NULL,
    Ambito             NVARCHAR(100)  NULL,
    CodigoArea         VARCHAR(10)    NULL,
    Area               NVARCHAR(100)  NULL,
    CodigoElemento     VARCHAR(10)    NULL,
    Elemento           NVARCHAR(100)  NULL,
    CodigoProducto     VARCHAR(20)    NULL,
    Producto           NVARCHAR(300)  NULL,
    CodigoAnio         VARCHAR(20)    NULL,
    Anio               NVARCHAR(20)   NULL,
    AnioInicio         SMALLINT       NULL,
    AnioFin            SMALLINT       NULL,
    Unidad             NVARCHAR(50)   NULL,
    Valor              DECIMAL(20,4)  NULL CONSTRAINT CK_FAOL_Valor CHECK (Valor IS NULL OR Valor >= 0),
    FlagValorNulo      AS CAST(CASE WHEN Valor IS NULL THEN 1 ELSE 0 END AS BIT) PERSISTED,
    FlagUnidadAtipica  BIT NOT NULL CONSTRAINT DF_FAOL_F1 DEFAULT (0),
    FlagAtipicoValor   BIT NOT NULL CONSTRAINT DF_FAOL_F2 DEFAULT (0),
    FechaCreacion      DATETIME2(0)   NOT NULL CONSTRAINT DF_FAOL_FC DEFAULT (SYSDATETIME()),
    FechaActualizacion DATETIME2(0)   NULL
);

IF OBJECT_ID(N'dbo.FAOSTAT_Revision') IS NULL
CREATE TABLE dbo.FAOSTAT_Revision (
    IdFaostatRevision  BIGINT IDENTITY(1,1) PRIMARY KEY,
    IdLote             INT            NOT NULL,
    IdStg              BIGINT         NOT NULL,
    Dataset            VARCHAR(12)    NOT NULL,
    IdRegla            INT            NULL,
    Categoria          VARCHAR(20)    NOT NULL,
    Motivo             NVARCHAR(400)  NOT NULL,
    CampoAfectado      NVARCHAR(100)  NULL,
    ValorOriginal      NVARCHAR(255)  NULL,
    CodigoAmbito       NVARCHAR(50)   NULL,
    Ambito             NVARCHAR(255)  NULL,
    CodigoArea         NVARCHAR(50)   NULL,
    Area               NVARCHAR(255)  NULL,
    CodigoElemento     NVARCHAR(50)   NULL,
    Elemento           NVARCHAR(255)  NULL,
    CodigoProducto     NVARCHAR(50)   NULL,
    Producto           NVARCHAR(500)  NULL,
    CodigoAnio         NVARCHAR(50)   NULL,
    Anio               NVARCHAR(50)   NULL,
    Unidad             NVARCHAR(100)  NULL,
    Valor              NVARCHAR(100)  NULL,
    EstadoRevision     VARCHAR(12)    NOT NULL CONSTRAINT DF_FAOR_Estado DEFAULT ('PENDIENTE'),
    Resolucion         NVARCHAR(400)  NULL,
    RevisadoPor        NVARCHAR(128)  NULL,
    FechaRevision      DATETIME2(0)   NULL,
    FechaCreacion      DATETIME2(0)   NOT NULL CONSTRAINT DF_FAOR_FC DEFAULT (SYSDATETIME()),
    FechaActualizacion DATETIME2(0)   NULL
);
GO

/* Índices de apoyo para filtrar por lote */
CREATE INDEX IX_stgEVA_Lote     ON dbo.stg_EVA (IdLote);
CREATE INDEX IX_EVAL_Lote       ON dbo.EVA_Limpios (IdLote);
CREATE INDEX IX_EVAR_Lote       ON dbo.EVA_Revision (IdLote);
CREATE INDEX IX_stgFAO_Lote     ON dbo.stg_FAOSTAT (IdLote);
CREATE INDEX IX_FAOL_Lote       ON dbo.FAOSTAT_Limpios (IdLote);
CREATE INDEX IX_FAOR_Lote       ON dbo.FAOSTAT_Revision (IdLote);
CREATE INDEX IX_LimiteIQR_Lote  ON cat.LimiteIQR (IdLote, Dataset, Campo);
CREATE INDEX IX_UnidadRef_Lote  ON cat.UnidadReferencia (IdLote);
GO
