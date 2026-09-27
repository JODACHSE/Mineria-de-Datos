USE Wololo_ETL;
GO

-- 01 · Registro de eventos (audit.Log)
CREATE OR ALTER PROCEDURE audit.usp_RegistrarEvento
    @Accion          VARCHAR(30),
    @Resumen         NVARCHAR(500) = NULL,
    @IdLote          INT           = NULL,
    @Esquema         SYSNAME       = NULL,
    @Tabla           SYSNAME       = NULL,
    @IdRegistro      NVARCHAR(100) = NULL,
    @ValoresAntes    NVARCHAR(MAX) = NULL,
    @ValoresDespues  NVARCHAR(MAX) = NULL,
    @TipoActor       VARCHAR(10)   = NULL,
    @Mecanismo       VARCHAR(15)   = 'PROCEDIMIENTO',
    @Paquete         NVARCHAR(128) = NULL,
    @Tarea           NVARCHAR(128) = NULL,
    @EjecucionGuid   NVARCHAR(50)  = NULL
AS
BEGIN
    SET NOCOUNT ON;

    INSERT audit.Log (Accion, Resumen, ValoresAntes, ValoresDespues, TipoActor, Actor, Mecanismo,
                      Paquete, EjecucionGuid, IdLote, Esquema, Tabla, IdRegistro, Tarea)
    VALUES (@Accion, @Resumen, @ValoresAntes, @ValoresDespues,
            COALESCE(@TipoActor, CASE WHEN COALESCE(@Paquete, CONVERT(NVARCHAR(128), SESSION_CONTEXT(N'Actor'))) IS NOT NULL
                                      THEN 'SSIS' ELSE 'USUARIO' END),
            COALESCE(@Paquete, CONVERT(NVARCHAR(128), SESSION_CONTEXT(N'Actor')), SUSER_SNAME()),
            @Mecanismo, @Paquete, TRY_CONVERT(UNIQUEIDENTIFIER, @EjecucionGuid),
            @IdLote, @Esquema, @Tabla, @IdRegistro, @Tarea);
END;
GO


-- 02 · Abrir lote
CREATE OR ALTER PROCEDURE etl.usp_AbrirLote
    @LoteClave      VARCHAR(60),
    @Dataset        VARCHAR(12),
    @Iteracion      TINYINT,
    @ReglasVersion  VARCHAR(10),
    @Tipo           VARCHAR(10)   = 'REAL',
    @ArchivoOrigen  NVARCHAR(260) = NULL,
    @Paquete        NVARCHAR(128) = NULL,
    @Tarea          NVARCHAR(128) = NULL,
    @EjecucionGuid  NVARCHAR(50)  = NULL,
    @IdLote         INT           OUTPUT
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;

    IF @Paquete IS NOT NULL
        EXEC sys.sp_set_session_context @key = N'Actor', @value = @Paquete;

    SET @IdLote = NULL;

    DECLARE @datasetPrev VARCHAR(12), @iterPrev TINYINT, @reglasPrev VARCHAR(10);

    SELECT @IdLote = IdLote, @datasetPrev = Dataset, @iterPrev = Iteracion, @reglasPrev = ReglasVersion
      FROM etl.Lote
     WHERE LoteClave = @LoteClave;

    IF @IdLote IS NULL
    BEGIN
        INSERT etl.Lote (LoteClave, Dataset, Iteracion, ReglasVersion, Tipo, ArchivoOrigen)
        VALUES (@LoteClave, @Dataset, @Iteracion, @ReglasVersion, @Tipo, @ArchivoOrigen);
        SET @IdLote = SCOPE_IDENTITY();

        DECLARE @jsonNuevo NVARCHAR(MAX) =
            (SELECT @LoteClave AS LoteClave, @Dataset AS Dataset, @Iteracion AS Iteracion,
                    @ReglasVersion AS ReglasVersion, @Tipo AS Tipo, 'ABIERTO' AS Estado
             FOR JSON PATH, WITHOUT_ARRAY_WRAPPER);

        EXEC audit.usp_RegistrarEvento
             @Accion = 'LOTE_ABIERTO', @Resumen = N'Lote abierto por primera vez.',
             @IdLote = @IdLote, @Esquema = N'etl', @Tabla = N'Lote', @IdRegistro = @LoteClave,
             @ValoresDespues = @jsonNuevo, @Paquete = @Paquete, @Tarea = @Tarea, @EjecucionGuid = @EjecucionGuid;
        RETURN;
    END

    IF @datasetPrev <> @Dataset OR @iterPrev <> @Iteracion OR @reglasPrev <> @ReglasVersion
        THROW 51001, N'La LoteClave ya existe con otro Dataset, Iteracion o ReglasVersion. Usa una clave nueva para otra iteración.', 1;

    DECLARE @nEvaL INT, @nEvaR INT, @nFaoL INT, @nFaoR INT, @nLim INT, @nUni INT, @nStgE INT, @nStgF INT;

    BEGIN TRAN;
        DELETE FROM dbo.EVA_Limpios      WHERE IdLote = @IdLote;  SET @nEvaL = @@ROWCOUNT;
        DELETE FROM dbo.EVA_Revision     WHERE IdLote = @IdLote;  SET @nEvaR = @@ROWCOUNT;
        DELETE FROM dbo.FAOSTAT_Limpios  WHERE IdLote = @IdLote;  SET @nFaoL = @@ROWCOUNT;
        DELETE FROM dbo.FAOSTAT_Revision WHERE IdLote = @IdLote;  SET @nFaoR = @@ROWCOUNT;
        DELETE FROM cat.LimiteIQR        WHERE IdLote = @IdLote;  SET @nLim  = @@ROWCOUNT;
        DELETE FROM cat.UnidadReferencia WHERE IdLote = @IdLote;  SET @nUni  = @@ROWCOUNT;
        DELETE FROM dbo.stg_EVA          WHERE IdLote = @IdLote;  SET @nStgE = @@ROWCOUNT;
        DELETE FROM dbo.stg_FAOSTAT      WHERE IdLote = @IdLote;  SET @nStgF = @@ROWCOUNT;

        UPDATE etl.Lote
           SET Estado = 'ABIERTO', Intentos = Intentos + 1, FechaInicio = SYSDATETIME(), FechaFin = NULL,
               FilasRecibidas = NULL, FilasAceptadas = NULL, FilasDuplicadas = NULL, FilasRevision = NULL,
               Tipo = @Tipo, ArchivoOrigen = @ArchivoOrigen, Observaciones = NULL
         WHERE IdLote = @IdLote;

        DECLARE @jsonAntes NVARCHAR(MAX) =
            (SELECT @nStgE AS stg_EVA, @nEvaL AS EVA_Limpios, @nEvaR AS EVA_Revision,
                    @nStgF AS stg_FAOSTAT, @nFaoL AS FAOSTAT_Limpios, @nFaoR AS FAOSTAT_Revision,
                    @nLim AS LimiteIQR, @nUni AS UnidadReferencia
             FOR JSON PATH, WITHOUT_ARRAY_WRAPPER);
        DECLARE @jsonDespues NVARCHAR(MAX) =
            (SELECT 'ABIERTO' AS Estado, Intentos FROM etl.Lote WHERE IdLote = @IdLote
             FOR JSON PATH, WITHOUT_ARRAY_WRAPPER);

        EXEC audit.usp_RegistrarEvento
             @Accion = 'LOTE_REABIERTO',
             @Resumen = N'Lote ya existente: se reemplazó lo cargado (ValoresAntes = filas eliminadas). Sin duplicados.',
             @IdLote = @IdLote, @Esquema = N'etl', @Tabla = N'Lote', @IdRegistro = @LoteClave,
             @ValoresAntes = @jsonAntes, @ValoresDespues = @jsonDespues,
             @Paquete = @Paquete, @Tarea = @Tarea, @EjecucionGuid = @EjecucionGuid;
    COMMIT;
END;
GO


-- 03 · Numerar staging
CREATE OR ALTER PROCEDURE etl.usp_NumerarStaging
    @IdLote INT
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @dataset VARCHAR(12) = (SELECT Dataset FROM etl.Lote WHERE IdLote = @IdLote);

    IF @dataset IS NULL
        THROW 51002, N'El lote no existe.', 1;

    IF @dataset = 'EVA'
    BEGIN
        ;WITH n AS (SELECT NumeroFila, rn = ROW_NUMBER() OVER (ORDER BY IdStg) FROM dbo.stg_EVA WHERE IdLote = @IdLote)
        UPDATE n SET NumeroFila = rn;
    END
    ELSE
    BEGIN
        ;WITH n AS (SELECT NumeroFila, rn = ROW_NUMBER() OVER (ORDER BY IdStg) FROM dbo.stg_FAOSTAT WHERE IdLote = @IdLote)
        UPDATE n SET NumeroFila = rn;
    END
END;
GO


-- 04 · Balance del lote (vista)
CREATE OR ALTER VIEW etl.vw_BalanceLote
AS
SELECT  l.IdLote, l.LoteClave, l.Dataset, l.Iteracion, l.ReglasVersion, l.Tipo, l.Estado, l.Intentos,
        l.FechaInicio, l.FechaFin,
        l.FilasRecibidas, l.FilasAceptadas, l.FilasDuplicadas, l.FilasRevision, l.BalanceOk,
        t.RecibidasTabla, t.AceptadasTabla, t.DuplicadasTabla, t.RevisionTabla,
        CAST(CASE WHEN t.RecibidasTabla = t.AceptadasTabla + t.DuplicadasTabla + t.RevisionTabla THEN 1 ELSE 0 END AS BIT) AS BalanceTablasOk
FROM    etl.Lote AS l
CROSS APPLY (
    SELECT
        RecibidasTabla  = (SELECT COUNT(*) FROM dbo.stg_EVA          s WHERE s.IdLote = l.IdLote)
                        + (SELECT COUNT(*) FROM dbo.stg_FAOSTAT      s WHERE s.IdLote = l.IdLote),
        AceptadasTabla  = (SELECT COUNT(*) FROM dbo.EVA_Limpios      x WHERE x.IdLote = l.IdLote)
                        + (SELECT COUNT(*) FROM dbo.FAOSTAT_Limpios  x WHERE x.IdLote = l.IdLote),
        DuplicadasTabla = (SELECT COUNT(*) FROM dbo.EVA_Revision     x WHERE x.IdLote = l.IdLote AND x.Categoria =  'DUPLICADO')
                        + (SELECT COUNT(*) FROM dbo.FAOSTAT_Revision x WHERE x.IdLote = l.IdLote AND x.Categoria =  'DUPLICADO'),
        RevisionTabla   = (SELECT COUNT(*) FROM dbo.EVA_Revision     x WHERE x.IdLote = l.IdLote AND x.Categoria <> 'DUPLICADO')
                        + (SELECT COUNT(*) FROM dbo.FAOSTAT_Revision x WHERE x.IdLote = l.IdLote AND x.Categoria <> 'DUPLICADO')
) AS t;
GO


-- 05 · Cerrar lote
CREATE OR ALTER PROCEDURE etl.usp_CerrarLote
    @IdLote          INT,
    @FilasRecibidas  INT = NULL,
    @FilasAceptadas  INT = NULL,
    @FilasDuplicadas INT = NULL,
    @FilasRevision   INT = NULL,
    @Paquete         NVARCHAR(128) = NULL,
    @Tarea           NVARCHAR(128) = NULL,
    @EjecucionGuid   NVARCHAR(50)  = NULL
AS
BEGIN
    SET NOCOUNT ON;

    IF NOT EXISTS (SELECT 1 FROM etl.Lote WHERE IdLote = @IdLote)
        THROW 51002, N'El lote no existe.', 1;

    DECLARE @recT INT, @aceT INT, @dupT INT, @revT INT;
    SELECT @recT = RecibidasTabla, @aceT = AceptadasTabla, @dupT = DuplicadasTabla, @revT = RevisionTabla
      FROM etl.vw_BalanceLote WHERE IdLote = @IdLote;

    SET @FilasRecibidas  = COALESCE(@FilasRecibidas,  @recT);
    SET @FilasAceptadas  = COALESCE(@FilasAceptadas,  @aceT);
    SET @FilasDuplicadas = COALESCE(@FilasDuplicadas, @dupT);
    SET @FilasRevision   = COALESCE(@FilasRevision,   @revT);

    DECLARE @obs NVARCHAR(500) = N'';
    IF @FilasRecibidas <> @FilasAceptadas + @FilasDuplicadas + @FilasRevision
        SET @obs += N'BALANCE: recibidas <> aceptadas + duplicadas + revision. ';
    IF @FilasRecibidas <> @recT OR @FilasAceptadas <> @aceT OR @FilasDuplicadas <> @dupT OR @FilasRevision <> @revT
        SET @obs += N'ROWCOUNT_VS_TABLAS: los conteos del paquete no coinciden con las tablas. ';
    IF @recT = 0
        SET @obs += N'STAGING_VACIO: no se cargaron filas. ';

    DECLARE @estado VARCHAR(10) = CASE WHEN @obs = N'' THEN 'CERRADO' ELSE 'FALLIDO' END;

    UPDATE etl.Lote
       SET Estado = @estado, FechaFin = SYSDATETIME(),
           FilasRecibidas = @FilasRecibidas, FilasAceptadas = @FilasAceptadas,
           FilasDuplicadas = @FilasDuplicadas, FilasRevision = @FilasRevision,
           Observaciones = NULLIF(@obs, N'')
     WHERE IdLote = @IdLote;

    DECLARE @json NVARCHAR(MAX) =
        (SELECT @estado AS Estado,
                @FilasRecibidas AS RowCount_Recibidas, @FilasAceptadas AS RowCount_Aceptadas,
                @FilasDuplicadas AS RowCount_Duplicadas, @FilasRevision AS RowCount_Revision,
                @recT AS Tabla_Recibidas, @aceT AS Tabla_Aceptadas, @dupT AS Tabla_Duplicadas, @revT AS Tabla_Revision
         FOR JSON PATH, WITHOUT_ARRAY_WRAPPER);

    DECLARE @accionLog  VARCHAR(30)   = CASE WHEN @estado = 'CERRADO' THEN 'LOTE_CERRADO' ELSE 'LOTE_FALLIDO' END;
    DECLARE @resumenLog NVARCHAR(500) = COALESCE(NULLIF(@obs, N''), N'Balance verificado: recibidas = aceptadas + duplicadas + revisión.');
    DECLARE @idRegistro NVARCHAR(100) = CONVERT(NVARCHAR(100), @IdLote);
    EXEC audit.usp_RegistrarEvento
         @Accion = @accionLog, @Resumen = @resumenLog,
         @IdLote = @IdLote, @Esquema = N'etl', @Tabla = N'Lote', @IdRegistro = @idRegistro,
         @ValoresDespues = @json, @Paquete = @Paquete, @Tarea = @Tarea, @EjecucionGuid = @EjecucionGuid;

    SELECT * FROM etl.vw_BalanceLote WHERE IdLote = @IdLote;
END;
GO