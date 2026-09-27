-- 01 · Base de datos y schemas
USE master;
GO
IF DB_ID(N'Wololo_ETL') IS NULL
    CREATE DATABASE Wololo_ETL;
GO
ALTER DATABASE Wololo_ETL SET RECOVERY SIMPLE;
ALTER DATABASE Wololo_ETL SET RECURSIVE_TRIGGERS OFF;
GO
USE Wololo_ETL;
GO
IF SCHEMA_ID(N'etl')   IS NULL EXEC (N'CREATE SCHEMA etl');
IF SCHEMA_ID(N'audit') IS NULL EXEC (N'CREATE SCHEMA audit');
IF SCHEMA_ID(N'cat')   IS NULL EXEC (N'CREATE SCHEMA cat');
GO


-- 02 · Control de lotes y auditoría
IF OBJECT_ID(N'etl.Lote', N'U') IS NULL
CREATE TABLE etl.Lote
(
    IdLote              INT           IDENTITY(1,1) NOT NULL,
    LoteClave           VARCHAR(60)   NOT NULL,
    Dataset             VARCHAR(12)   NOT NULL,
    Iteracion           TINYINT       NOT NULL,
    ReglasVersion       VARCHAR(10)   NOT NULL,
    Tipo                VARCHAR(10)   NOT NULL DEFAULT ('REAL'),
    ArchivoOrigen       NVARCHAR(260) NULL,
    Estado              VARCHAR(10)   NOT NULL DEFAULT ('ABIERTO'),
    Intentos            INT           NOT NULL DEFAULT (1),
    FechaInicio         DATETIME2(3)  NOT NULL DEFAULT (SYSDATETIME()),
    FechaFin            DATETIME2(3)  NULL,
    FilasRecibidas      INT           NULL,
    FilasAceptadas      INT           NULL,
    FilasDuplicadas     INT           NULL,
    FilasRevision       INT           NULL,
    BalanceOk           AS (CASE WHEN FilasRecibidas IS NULL THEN NULL
                                 WHEN FilasRecibidas = ISNULL(FilasAceptadas, 0) + ISNULL(FilasDuplicadas, 0) + ISNULL(FilasRevision, 0)
                                 THEN CAST(1 AS BIT) ELSE CAST(0 AS BIT) END),
    Observaciones       NVARCHAR(500) NULL,
    FechaCreacion       DATETIME2(3)  NOT NULL DEFAULT (SYSDATETIME()),
    FechaActualizacion  DATETIME2(3)  NOT NULL DEFAULT (SYSDATETIME()),
    CONSTRAINT PK_Lote           PRIMARY KEY CLUSTERED (IdLote),
    CONSTRAINT UQ_Lote_Clave     UNIQUE (LoteClave),
    CONSTRAINT CK_Lote_Dataset   CHECK (Dataset IN ('EVA', 'QCL', 'QCLBasicos', 'FS')),
    CONSTRAINT CK_Lote_Iteracion CHECK (Iteracion BETWEEN 1 AND 9),
    CONSTRAINT CK_Lote_Tipo      CHECK (Tipo IN ('REAL', 'PRUEBA')),
    CONSTRAINT CK_Lote_Estado    CHECK (Estado IN ('ABIERTO', 'CERRADO', 'FALLIDO')),
    CONSTRAINT CK_Lote_Fechas    CHECK (FechaFin IS NULL OR FechaFin >= FechaInicio)
);
GO

IF OBJECT_ID(N'audit.Log', N'U') IS NULL
CREATE TABLE audit.Log
(
    IdLog           BIGINT            IDENTITY(1,1) NOT NULL,
    FechaEvento     DATETIMEOFFSET(3) NOT NULL DEFAULT (SYSDATETIMEOFFSET()),
    Accion          VARCHAR(30)       NOT NULL,
    Resumen         NVARCHAR(500)     NULL,
    ValoresAntes    NVARCHAR(MAX)     NULL,
    ValoresDespues  NVARCHAR(MAX)     NULL,
    TipoActor       VARCHAR(10)       NOT NULL,
    Actor           NVARCHAR(128)     NOT NULL,
    Mecanismo       VARCHAR(15)       NOT NULL,
    Paquete         NVARCHAR(128)     NULL,
    EjecucionGuid   UNIQUEIDENTIFIER  NULL,
    IdLote          INT               NULL,
    Servidor        SYSNAME           NULL DEFAULT (@@SERVERNAME),
    BaseDatos       SYSNAME           NULL DEFAULT (DB_NAME()),
    Esquema         SYSNAME           NULL,
    Tabla           SYSNAME           NULL,
    IdRegistro      NVARCHAR(100)     NULL,
    Tarea           NVARCHAR(128)     NULL,
    Host            NVARCHAR(128)     NULL DEFAULT (HOST_NAME()),
    AppName         NVARCHAR(128)     NULL DEFAULT (APP_NAME()),
    CONSTRAINT PK_Log            PRIMARY KEY CLUSTERED (IdLog),
    CONSTRAINT FK_Log_Lote       FOREIGN KEY (IdLote) REFERENCES etl.Lote (IdLote),
    CONSTRAINT CK_Log_TipoActor  CHECK (TipoActor IN ('USUARIO', 'SSIS', 'SISTEMA')),
    CONSTRAINT CK_Log_Mecanismo  CHECK (Mecanismo IN ('TRIGGER', 'PROCEDIMIENTO', 'PAQUETE')),
    CONSTRAINT CK_Log_JsonAntes  CHECK (ValoresAntes   IS NULL OR ISJSON(ValoresAntes)   = 1),
    CONSTRAINT CK_Log_JsonDesp   CHECK (ValoresDespues IS NULL OR ISJSON(ValoresDespues) = 1)
);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_Log_Lote' AND object_id = OBJECT_ID(N'audit.Log'))
    CREATE INDEX IX_Log_Lote ON audit.Log (IdLote, FechaEvento);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_Log_Tabla' AND object_id = OBJECT_ID(N'audit.Log'))
    CREATE INDEX IX_Log_Tabla ON audit.Log (Esquema, Tabla, IdRegistro);
GO


-- 03 · Catálogos
IF OBJECT_ID(N'cat.Regla', N'U') IS NULL
CREATE TABLE cat.Regla
(
    IdRegla             INT           IDENTITY(1,1) NOT NULL,
    ReglasVersion       VARCHAR(10)   NOT NULL,
    Codigo              VARCHAR(8)    NOT NULL,
    Familia             VARCHAR(8)    NOT NULL,
    Campo               NVARCHAR(120) NOT NULL,
    Dimension           VARCHAR(15)   NOT NULL,
    Accion              VARCHAR(10)   NOT NULL,
    Categoria           VARCHAR(20)   NULL,
    Componente          NVARCHAR(80)  NULL,
    Descripcion         NVARCHAR(400) NOT NULL,
    Justificacion       NVARCHAR(700) NOT NULL,
    Prioridad           TINYINT       NOT NULL,
    ProblemaR2          VARCHAR(30)   NULL,
    Activa              BIT           NOT NULL DEFAULT (1),
    FechaCreacion       DATETIME2(3)  NOT NULL DEFAULT (SYSDATETIME()),
    FechaActualizacion  DATETIME2(3)  NOT NULL DEFAULT (SYSDATETIME()),
    CONSTRAINT PK_Regla           PRIMARY KEY CLUSTERED (IdRegla),
    CONSTRAINT UQ_Regla_Version   UNIQUE (ReglasVersion, Codigo),
    CONSTRAINT CK_Regla_Familia   CHECK (Familia IN ('EVA', 'FAOSTAT')),
    CONSTRAINT CK_Regla_Dimension CHECK (Dimension IN ('Completitud', 'Validez', 'Unicidad', 'Consistencia', 'Exactitud')),
    CONSTRAINT CK_Regla_Accion    CHECK (Accion IN ('CORREGIR', 'MARCAR', 'REVISAR', 'DUPLICADO')),
    CONSTRAINT CK_Regla_Categoria CHECK (Categoria IS NULL OR Categoria IN ('NULO', 'ERROR_CONVERSION', 'DOMINIO', 'CONSISTENCIA', 'SIN_COINCIDENCIA', 'DUPLICADO')),
    CONSTRAINT CK_Regla_AccionCat CHECK ((Accion IN ('REVISAR', 'DUPLICADO') AND Categoria IS NOT NULL)
                                      OR (Accion IN ('CORREGIR', 'MARCAR')  AND Categoria IS NULL))
);
GO

IF OBJECT_ID(N'cat.Municipio', N'U') IS NULL
CREATE TABLE cat.Municipio
(
    CodigoMunicipioDane CHAR(5)       NOT NULL,
    CodigoDeptoDane     CHAR(2)       NOT NULL,
    Departamento        NVARCHAR(100) NOT NULL,
    Municipio           NVARCHAR(150) NOT NULL,
    Fuente              NVARCHAR(200) NULL,
    FechaCreacion       DATETIME2(3)  NOT NULL DEFAULT (SYSDATETIME()),
    FechaActualizacion  DATETIME2(3)  NOT NULL DEFAULT (SYSDATETIME()),
    CONSTRAINT PK_Municipio         PRIMARY KEY CLUSTERED (CodigoMunicipioDane),
    CONSTRAINT CK_Municipio_Prefijo CHECK (LEFT(CodigoMunicipioDane, 2) = CodigoDeptoDane)
);
GO

IF OBJECT_ID(N'cat.LimiteIQR', N'U') IS NULL
CREATE TABLE cat.LimiteIQR
(
    IdLimite            INT           IDENTITY(1,1) NOT NULL,
    IdLote              INT           NOT NULL,
    Dataset             VARCHAR(12)   NOT NULL,
    Campo               VARCHAR(40)   NOT NULL,
    GrupoClave          NVARCHAR(200) NOT NULL,
    N                   INT           NOT NULL,
    Q1                  DECIMAL(20,4) NOT NULL,
    Q3                  DECIMAL(20,4) NOT NULL,
    LimiteInferior      DECIMAL(20,4) NOT NULL,
    LimiteSuperior      DECIMAL(20,4) NOT NULL,
    FechaCreacion       DATETIME2(3)  NOT NULL DEFAULT (SYSDATETIME()),
    FechaActualizacion  DATETIME2(3)  NOT NULL DEFAULT (SYSDATETIME()),
    CONSTRAINT PK_LimiteIQR      PRIMARY KEY CLUSTERED (IdLimite),
    CONSTRAINT FK_LimiteIQR_Lote FOREIGN KEY (IdLote) REFERENCES etl.Lote (IdLote),
    CONSTRAINT UQ_LimiteIQR      UNIQUE (IdLote, Dataset, Campo, GrupoClave)
);
GO

IF OBJECT_ID(N'cat.UnidadReferencia', N'U') IS NULL
CREATE TABLE cat.UnidadReferencia
(
    IdUnidadRef         INT           IDENTITY(1,1) NOT NULL,
    IdLote              INT           NOT NULL,
    Dataset             VARCHAR(12)   NOT NULL,
    CodigoProducto      VARCHAR(20)   NOT NULL,
    CodigoElemento      VARCHAR(10)   NOT NULL,
    UnidadModal         NVARCHAR(50)  NOT NULL,
    NFilas              INT           NOT NULL,
    FechaCreacion       DATETIME2(3)  NOT NULL DEFAULT (SYSDATETIME()),
    FechaActualizacion  DATETIME2(3)  NOT NULL DEFAULT (SYSDATETIME()),
    CONSTRAINT PK_UnidadRef      PRIMARY KEY CLUSTERED (IdUnidadRef),
    CONSTRAINT FK_UnidadRef_Lote FOREIGN KEY (IdLote) REFERENCES etl.Lote (IdLote),
    CONSTRAINT UQ_UnidadRef      UNIQUE (IdLote, Dataset, CodigoProducto, CodigoElemento)
);
GO


-- 04 · Familia EVA
IF OBJECT_ID(N'dbo.stg_EVA', N'U') IS NULL
CREATE TABLE dbo.stg_EVA
(
    IdStg                 BIGINT        IDENTITY(1,1) NOT NULL,
    IdLote                INT           NOT NULL,
    ArchivoOrigen         NVARCHAR(260) NOT NULL,
    NumeroFila            INT           NULL,
    CodigoDeptoDane       NVARCHAR(50)  NULL,
    Departamento          NVARCHAR(255) NULL,
    CodigoMunicipioDane   NVARCHAR(50)  NULL,
    Municipio             NVARCHAR(255) NULL,
    GrupoCultivo          NVARCHAR(255) NULL,
    Subgrupo              NVARCHAR(255) NULL,
    Cultivo               NVARCHAR(255) NULL,
    DesagregacionCultivo  NVARCHAR(255) NULL,
    Anio                  NVARCHAR(50)  NULL,
    Periodo               NVARCHAR(50)  NULL,
    AreaSembrada          NVARCHAR(50)  NULL,
    AreaCosechada         NVARCHAR(50)  NULL,
    Produccion            NVARCHAR(50)  NULL,
    Rendimiento           NVARCHAR(50)  NULL,
    CicloCultivo          NVARCHAR(255) NULL,
    EstadoFisico          NVARCHAR(255) NULL,
    CodigoCultivo         NVARCHAR(50)  NULL,
    NombreCientifico      NVARCHAR(255) NULL,
    FechaCreacion         DATETIME2(3)  NOT NULL DEFAULT (SYSDATETIME()),
    FechaActualizacion    DATETIME2(3)  NOT NULL DEFAULT (SYSDATETIME()),
    CONSTRAINT PK_stg_EVA      PRIMARY KEY CLUSTERED (IdStg),
    CONSTRAINT FK_stg_EVA_Lote FOREIGN KEY (IdLote) REFERENCES etl.Lote (IdLote)
);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_stg_EVA_Lote' AND object_id = OBJECT_ID(N'dbo.stg_EVA'))
    CREATE INDEX IX_stg_EVA_Lote ON dbo.stg_EVA (IdLote);
GO

IF OBJECT_ID(N'dbo.EVA_Limpios', N'U') IS NULL
CREATE TABLE dbo.EVA_Limpios
(
    IdEvaLimpio                BIGINT        IDENTITY(1,1) NOT NULL,
    IdLote                     INT           NOT NULL,
    IdStg                      BIGINT        NOT NULL,
    CodigoDeptoDane            CHAR(2)       NOT NULL,
    Departamento               NVARCHAR(100) NOT NULL,
    CodigoMunicipioDane        CHAR(5)       NOT NULL,
    Municipio                  NVARCHAR(150) NOT NULL,
    GrupoCultivo               NVARCHAR(100) NULL,
    Subgrupo                   NVARCHAR(100) NULL,
    Cultivo                    NVARCHAR(60)  NOT NULL,
    DesagregacionCultivo       NVARCHAR(150) NOT NULL,
    Anio                       SMALLINT      NOT NULL,
    Periodo                    VARCHAR(5)    NOT NULL,
    AreaSembrada               DECIMAL(14,2) NOT NULL,
    AreaCosechada              DECIMAL(14,2) NOT NULL,
    Produccion                 DECIMAL(16,2) NOT NULL,
    Rendimiento                DECIMAL(12,2) NOT NULL,
    CicloCultivo               NVARCHAR(30)  NULL,
    EstadoFisico               NVARCHAR(50)  NULL,
    CodigoCultivo              VARCHAR(20)   NOT NULL,
    NombreCientifico           NVARCHAR(150) NULL,
    FlagAreaIncoherente        BIT           NOT NULL DEFAULT (0),
    FlagAtipicoAreaSembrada    BIT           NOT NULL DEFAULT (0),
    FlagAtipicoAreaCosechada   BIT           NOT NULL DEFAULT (0),
    FlagAtipicoProduccion      BIT           NOT NULL DEFAULT (0),
    FlagAtipicoRendimiento     BIT           NOT NULL DEFAULT (0),
    FechaCreacion              DATETIME2(3)  NOT NULL DEFAULT (SYSDATETIME()),
    FechaActualizacion         DATETIME2(3)  NOT NULL DEFAULT (SYSDATETIME()),
    CONSTRAINT PK_EVA_Limpios         PRIMARY KEY CLUSTERED (IdEvaLimpio),
    CONSTRAINT FK_EVA_Limpios_Lote    FOREIGN KEY (IdLote) REFERENCES etl.Lote (IdLote),
    CONSTRAINT FK_EVA_Limpios_Stg     FOREIGN KEY (IdStg)  REFERENCES dbo.stg_EVA (IdStg),
    CONSTRAINT UQ_EVA_Limpios_Fila    UNIQUE (IdLote, IdStg),
    CONSTRAINT UQ_EVA_Limpios_Llave   UNIQUE (IdLote, CodigoMunicipioDane, CodigoCultivo, DesagregacionCultivo, Anio, Periodo),
    CONSTRAINT CK_EVA_Limpios_Dpto    CHECK (CodigoDeptoDane LIKE '[0-9][0-9]'),
    CONSTRAINT CK_EVA_Limpios_Mpio    CHECK (CodigoMunicipioDane LIKE '[0-9][0-9][0-9][0-9][0-9]' AND LEFT(CodigoMunicipioDane, 2) = CodigoDeptoDane),
    CONSTRAINT CK_EVA_Limpios_Anio    CHECK (Anio BETWEEN 1990 AND 2100),
    CONSTRAINT CK_EVA_Limpios_Periodo CHECK (Periodo LIKE '[0-9][0-9][0-9][0-9]' OR Periodo LIKE '[0-9][0-9][0-9][0-9][AB]'),
    CONSTRAINT CK_EVA_Limpios_Medidas CHECK (AreaSembrada >= 0 AND AreaCosechada >= 0 AND Produccion >= 0 AND Rendimiento >= 0)
);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_EVA_Limpios_IdStg' AND object_id = OBJECT_ID(N'dbo.EVA_Limpios'))
    CREATE INDEX IX_EVA_Limpios_IdStg ON dbo.EVA_Limpios (IdStg);
GO

IF OBJECT_ID(N'dbo.EVA_Revision', N'U') IS NULL
CREATE TABLE dbo.EVA_Revision
(
    IdEvaRevision         BIGINT        IDENTITY(1,1) NOT NULL,
    IdLote                INT           NOT NULL,
    IdStg                 BIGINT        NOT NULL,
    IdRegla               INT           NOT NULL,
    Categoria             VARCHAR(20)   NOT NULL,
    Motivo                NVARCHAR(400) NOT NULL,
    CampoAfectado         NVARCHAR(100) NULL,
    ValorOriginal         NVARCHAR(255) NULL,
    CodigoDeptoDane       NVARCHAR(50)  NULL,
    Departamento          NVARCHAR(255) NULL,
    CodigoMunicipioDane   NVARCHAR(50)  NULL,
    Municipio             NVARCHAR(255) NULL,
    GrupoCultivo          NVARCHAR(255) NULL,
    Subgrupo              NVARCHAR(255) NULL,
    Cultivo               NVARCHAR(255) NULL,
    DesagregacionCultivo  NVARCHAR(255) NULL,
    Anio                  NVARCHAR(50)  NULL,
    Periodo               NVARCHAR(50)  NULL,
    AreaSembrada          NVARCHAR(50)  NULL,
    AreaCosechada         NVARCHAR(50)  NULL,
    Produccion            NVARCHAR(50)  NULL,
    Rendimiento           NVARCHAR(50)  NULL,
    CicloCultivo          NVARCHAR(255) NULL,
    EstadoFisico          NVARCHAR(255) NULL,
    CodigoCultivo         NVARCHAR(50)  NULL,
    NombreCientifico      NVARCHAR(255) NULL,
    EstadoRevision        VARCHAR(12)   NOT NULL DEFAULT ('PENDIENTE'),
    Resolucion            NVARCHAR(400) NULL,
    RevisadoPor           NVARCHAR(128) NULL,
    FechaRevision         DATETIME2(3)  NULL,
    FechaCreacion         DATETIME2(3)  NOT NULL DEFAULT (SYSDATETIME()),
    FechaActualizacion    DATETIME2(3)  NOT NULL DEFAULT (SYSDATETIME()),
    CONSTRAINT PK_EVA_Revision        PRIMARY KEY CLUSTERED (IdEvaRevision),
    CONSTRAINT FK_EVA_Revision_Lote   FOREIGN KEY (IdLote)  REFERENCES etl.Lote (IdLote),
    CONSTRAINT FK_EVA_Revision_Stg    FOREIGN KEY (IdStg)   REFERENCES dbo.stg_EVA (IdStg),
    CONSTRAINT FK_EVA_Revision_Regla  FOREIGN KEY (IdRegla) REFERENCES cat.Regla (IdRegla),
    CONSTRAINT UQ_EVA_Revision_Fila   UNIQUE (IdLote, IdStg),
    CONSTRAINT CK_EVA_Revision_Cat    CHECK (Categoria IN ('NULO', 'ERROR_CONVERSION', 'DOMINIO', 'CONSISTENCIA', 'SIN_COINCIDENCIA', 'DUPLICADO')),
    CONSTRAINT CK_EVA_Revision_Estado CHECK (EstadoRevision IN ('PENDIENTE', 'CORREGIDO', 'CONFIRMADO', 'DESCARTADO'))
);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_EVA_Revision_IdStg' AND object_id = OBJECT_ID(N'dbo.EVA_Revision'))
    CREATE INDEX IX_EVA_Revision_IdStg ON dbo.EVA_Revision (IdStg);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_EVA_Revision_Cat' AND object_id = OBJECT_ID(N'dbo.EVA_Revision'))
    CREATE INDEX IX_EVA_Revision_Cat ON dbo.EVA_Revision (IdLote, Categoria);
GO


-- 05 · Familia FAOSTAT
IF OBJECT_ID(N'dbo.stg_FAOSTAT', N'U') IS NULL
CREATE TABLE dbo.stg_FAOSTAT
(
    IdStg               BIGINT        IDENTITY(1,1) NOT NULL,
    IdLote              INT           NOT NULL,
    Dataset             VARCHAR(12)   NOT NULL,
    ArchivoOrigen       NVARCHAR(260) NOT NULL,
    NumeroFila          INT           NULL,
    CodigoAmbito        NVARCHAR(50)  NULL,
    Ambito              NVARCHAR(255) NULL,
    CodigoArea          NVARCHAR(50)  NULL,
    Area                NVARCHAR(255) NULL,
    CodigoElemento      NVARCHAR(50)  NULL,
    Elemento            NVARCHAR(255) NULL,
    CodigoProducto      NVARCHAR(50)  NULL,
    Producto            NVARCHAR(500) NULL,
    CodigoAnio          NVARCHAR(50)  NULL,
    Anio                NVARCHAR(50)  NULL,
    Unidad              NVARCHAR(100) NULL,
    Valor               NVARCHAR(100) NULL,
    FechaCreacion       DATETIME2(3)  NOT NULL DEFAULT (SYSDATETIME()),
    FechaActualizacion  DATETIME2(3)  NOT NULL DEFAULT (SYSDATETIME()),
    CONSTRAINT PK_stg_FAOSTAT         PRIMARY KEY CLUSTERED (IdStg),
    CONSTRAINT FK_stg_FAOSTAT_Lote    FOREIGN KEY (IdLote) REFERENCES etl.Lote (IdLote),
    CONSTRAINT CK_stg_FAOSTAT_Dataset CHECK (Dataset IN ('QCL', 'QCLBasicos', 'FS'))
);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_stg_FAOSTAT_Lote' AND object_id = OBJECT_ID(N'dbo.stg_FAOSTAT'))
    CREATE INDEX IX_stg_FAOSTAT_Lote ON dbo.stg_FAOSTAT (IdLote);
GO

IF OBJECT_ID(N'dbo.FAOSTAT_Limpios', N'U') IS NULL
CREATE TABLE dbo.FAOSTAT_Limpios
(
    IdFaostatLimpio     BIGINT        IDENTITY(1,1) NOT NULL,
    IdLote              INT           NOT NULL,
    IdStg               BIGINT        NOT NULL,
    Dataset             VARCHAR(12)   NOT NULL,
    CodigoAmbito        VARCHAR(10)   NOT NULL,
    Ambito              NVARCHAR(100) NOT NULL,
    CodigoArea          VARCHAR(10)   NOT NULL,
    Area                NVARCHAR(100) NOT NULL,
    CodigoElemento      VARCHAR(10)   NOT NULL,
    Elemento            NVARCHAR(100) NOT NULL,
    CodigoProducto      VARCHAR(20)   NOT NULL,
    Producto            NVARCHAR(300) NOT NULL,
    CodigoAnio          VARCHAR(20)   NOT NULL,
    Anio                NVARCHAR(20)  NOT NULL,
    AnioInicio          SMALLINT      NOT NULL,
    AnioFin             SMALLINT      NOT NULL,
    Unidad              NVARCHAR(50)  NOT NULL,
    Valor               DECIMAL(20,4) NULL,
    FlagValorNulo       AS (CAST(CASE WHEN Valor IS NULL THEN 1 ELSE 0 END AS BIT)),
    FlagUnidadAtipica   BIT           NOT NULL DEFAULT (0),
    FlagAtipicoValor    BIT           NOT NULL DEFAULT (0),
    FechaCreacion       DATETIME2(3)  NOT NULL DEFAULT (SYSDATETIME()),
    FechaActualizacion  DATETIME2(3)  NOT NULL DEFAULT (SYSDATETIME()),
    CONSTRAINT PK_FAOSTAT_Limpios         PRIMARY KEY CLUSTERED (IdFaostatLimpio),
    CONSTRAINT FK_FAOSTAT_Limpios_Lote    FOREIGN KEY (IdLote) REFERENCES etl.Lote (IdLote),
    CONSTRAINT FK_FAOSTAT_Limpios_Stg     FOREIGN KEY (IdStg)  REFERENCES dbo.stg_FAOSTAT (IdStg),
    CONSTRAINT UQ_FAOSTAT_Limpios_Fila    UNIQUE (IdLote, IdStg),
    CONSTRAINT UQ_FAOSTAT_Limpios_Llave   UNIQUE (IdLote, Dataset, CodigoArea, CodigoElemento, CodigoProducto, CodigoAnio, Unidad),
    CONSTRAINT CK_FAOSTAT_Limpios_Dataset CHECK (Dataset IN ('QCL', 'QCLBasicos', 'FS')),
    CONSTRAINT CK_FAOSTAT_Limpios_Anios   CHECK (AnioInicio BETWEEN 1900 AND 2100 AND AnioFin >= AnioInicio),
    CONSTRAINT CK_FAOSTAT_Limpios_Valor   CHECK (Valor IS NULL OR Valor >= 0)
);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_FAOSTAT_Limpios_IdStg' AND object_id = OBJECT_ID(N'dbo.FAOSTAT_Limpios'))
    CREATE INDEX IX_FAOSTAT_Limpios_IdStg ON dbo.FAOSTAT_Limpios (IdStg);
GO

IF OBJECT_ID(N'dbo.FAOSTAT_Revision', N'U') IS NULL
CREATE TABLE dbo.FAOSTAT_Revision
(
    IdFaostatRevision   BIGINT        IDENTITY(1,1) NOT NULL,
    IdLote              INT           NOT NULL,
    IdStg               BIGINT        NOT NULL,
    Dataset             VARCHAR(12)   NOT NULL,
    IdRegla             INT           NOT NULL,
    Categoria           VARCHAR(20)   NOT NULL,
    Motivo              NVARCHAR(400) NOT NULL,
    CampoAfectado       NVARCHAR(100) NULL,
    ValorOriginal       NVARCHAR(255) NULL,
    CodigoAmbito        NVARCHAR(50)  NULL,
    Ambito              NVARCHAR(255) NULL,
    CodigoArea          NVARCHAR(50)  NULL,
    Area                NVARCHAR(255) NULL,
    CodigoElemento      NVARCHAR(50)  NULL,
    Elemento            NVARCHAR(255) NULL,
    CodigoProducto      NVARCHAR(50)  NULL,
    Producto            NVARCHAR(500) NULL,
    CodigoAnio          NVARCHAR(50)  NULL,
    Anio                NVARCHAR(50)  NULL,
    Unidad              NVARCHAR(100) NULL,
    Valor               NVARCHAR(100) NULL,
    EstadoRevision      VARCHAR(12)   NOT NULL DEFAULT ('PENDIENTE'),
    Resolucion          NVARCHAR(400) NULL,
    RevisadoPor         NVARCHAR(128) NULL,
    FechaRevision       DATETIME2(3)  NULL,
    FechaCreacion       DATETIME2(3)  NOT NULL DEFAULT (SYSDATETIME()),
    FechaActualizacion  DATETIME2(3)  NOT NULL DEFAULT (SYSDATETIME()),
    CONSTRAINT PK_FAOSTAT_Revision         PRIMARY KEY CLUSTERED (IdFaostatRevision),
    CONSTRAINT FK_FAOSTAT_Revision_Lote    FOREIGN KEY (IdLote)  REFERENCES etl.Lote (IdLote),
    CONSTRAINT FK_FAOSTAT_Revision_Stg     FOREIGN KEY (IdStg)   REFERENCES dbo.stg_FAOSTAT (IdStg),
    CONSTRAINT FK_FAOSTAT_Revision_Regla   FOREIGN KEY (IdRegla) REFERENCES cat.Regla (IdRegla),
    CONSTRAINT UQ_FAOSTAT_Revision_Fila    UNIQUE (IdLote, IdStg),
    CONSTRAINT CK_FAOSTAT_Revision_Dataset CHECK (Dataset IN ('QCL', 'QCLBasicos', 'FS')),
    CONSTRAINT CK_FAOSTAT_Revision_Cat     CHECK (Categoria IN ('NULO', 'ERROR_CONVERSION', 'DOMINIO', 'CONSISTENCIA', 'SIN_COINCIDENCIA', 'DUPLICADO')),
    CONSTRAINT CK_FAOSTAT_Revision_Estado  CHECK (EstadoRevision IN ('PENDIENTE', 'CORREGIDO', 'CONFIRMADO', 'DESCARTADO'))
);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_FAOSTAT_Revision_IdStg' AND object_id = OBJECT_ID(N'dbo.FAOSTAT_Revision'))
    CREATE INDEX IX_FAOSTAT_Revision_IdStg ON dbo.FAOSTAT_Revision (IdStg);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_FAOSTAT_Revision_Cat' AND object_id = OBJECT_ID(N'dbo.FAOSTAT_Revision'))
    CREATE INDEX IX_FAOSTAT_Revision_Cat ON dbo.FAOSTAT_Revision (IdLote, Categoria);
GO


-- 06 · Triggers
SET NOCOUNT ON;

DECLARE @objetivos TABLE
(
    Esquema   SYSNAME NOT NULL,
    Tabla     SYSNAME NOT NULL,
    Pk        SYSNAME NOT NULL,
    TieneLote BIT     NOT NULL,
    Audita    BIT     NOT NULL
);

INSERT @objetivos (Esquema, Tabla, Pk, TieneLote, Audita) VALUES
 (N'etl', N'Lote',             N'IdLote',              0, 0),
 (N'cat', N'Regla',            N'IdRegla',             0, 1),
 (N'cat', N'Municipio',        N'CodigoMunicipioDane', 0, 1),
 (N'cat', N'LimiteIQR',        N'IdLimite',            1, 0),
 (N'cat', N'UnidadReferencia', N'IdUnidadRef',         1, 0),
 (N'dbo', N'stg_EVA',          N'IdStg',               1, 0),
 (N'dbo', N'EVA_Limpios',      N'IdEvaLimpio',         1, 1),
 (N'dbo', N'EVA_Revision',     N'IdEvaRevision',       1, 1),
 (N'dbo', N'stg_FAOSTAT',      N'IdStg',               1, 0),
 (N'dbo', N'FAOSTAT_Limpios',  N'IdFaostatLimpio',     1, 1),
 (N'dbo', N'FAOSTAT_Revision', N'IdFaostatRevision',   1, 1);

DECLARE @esq SYSNAME, @tab SYSNAME, @pk SYSNAME, @lote BIT, @aud BIT,
        @trg SYSNAME, @sql NVARCHAR(MAX), @bloqueAudit NVARCHAR(MAX);

DECLARE cur CURSOR LOCAL FAST_FORWARD FOR
    SELECT Esquema, Tabla, Pk, TieneLote, Audita FROM @objetivos;
OPEN cur;
FETCH NEXT FROM cur INTO @esq, @tab, @pk, @lote, @aud;

WHILE @@FETCH_STATUS = 0
BEGIN
    SET @trg = N'trg_' + @tab + N'_AfterUpdate';

    SET @bloqueAudit = CASE WHEN @aud = 1 THEN N'
    INSERT audit.Log (Accion, Resumen, ValoresAntes, ValoresDespues, TipoActor, Actor, Mecanismo, Esquema, Tabla, IdRegistro, IdLote)
    SELECT N''UPDATE'',
           N''Actualización de una fila en {ESQ}.{TAB}'',
           (SELECT d2.* FROM deleted AS d2 WHERE d2.{QPK} = d.{QPK} FOR JSON PATH, WITHOUT_ARRAY_WRAPPER),
           (SELECT t2.* FROM {QESQ}.{QTAB} AS t2 WHERE t2.{QPK} = t.{QPK} FOR JSON PATH, WITHOUT_ARRAY_WRAPPER),
           CASE WHEN SESSION_CONTEXT(N''Actor'') IS NULL THEN ''USUARIO'' ELSE ''SSIS'' END,
           COALESCE(CONVERT(NVARCHAR(128), SESSION_CONTEXT(N''Actor'')), SUSER_SNAME()),
           ''TRIGGER'',
           N''{ESQ}'', N''{TAB}'',
           CONVERT(NVARCHAR(100), t.{QPK}),
           {LOTE}
      FROM deleted AS d
      JOIN {QESQ}.{QTAB} AS t ON t.{QPK} = d.{QPK};
' ELSE N'' END;

    SET @sql = N'
CREATE OR ALTER TRIGGER {QESQ}.{QTRG}
ON {QESQ}.{QTAB}
AFTER UPDATE
AS
BEGIN
    SET NOCOUNT ON;
    IF TRIGGER_NESTLEVEL(@@PROCID, ''AFTER'', ''DML'') > 1 RETURN;

    UPDATE t
       SET FechaActualizacion = SYSDATETIME()
      FROM {QESQ}.{QTAB} AS t
      JOIN inserted AS i ON i.{QPK} = t.{QPK};
' + @bloqueAudit + N'END';

    SET @sql = REPLACE(@sql, N'{QESQ}', QUOTENAME(@esq));
    SET @sql = REPLACE(@sql, N'{QTAB}', QUOTENAME(@tab));
    SET @sql = REPLACE(@sql, N'{QTRG}', QUOTENAME(@trg));
    SET @sql = REPLACE(@sql, N'{QPK}',  QUOTENAME(@pk));
    SET @sql = REPLACE(@sql, N'{ESQ}',  @esq);
    SET @sql = REPLACE(@sql, N'{TAB}',  @tab);
    SET @sql = REPLACE(@sql, N'{LOTE}', CASE WHEN @lote = 1 THEN N't.IdLote' ELSE N'NULL' END);

    EXEC sys.sp_executesql @sql;

    FETCH NEXT FROM cur INTO @esq, @tab, @pk, @lote, @aud;
END
CLOSE cur;
DEALLOCATE cur;
GO

CREATE OR ALTER TRIGGER audit.trg_Log_SoloInsercion
ON audit.Log
INSTEAD OF UPDATE, DELETE
AS
BEGIN
    SET NOCOUNT ON;
    THROW 51000, N'audit.Log es una bitácora de solo inserción: no admite UPDATE ni DELETE.', 1;
END;
GO