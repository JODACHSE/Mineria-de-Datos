/* =============================================================================
   Etapa 3 · Base de datos Wololo_ETL
   02 — Procedimientos de control de lotes y auditoría

   Firmas compatibles con las llamadas de los paquetes:
     SQL_Inicio            {call etl.usp_AbrirLote(?,?,?,?,?,?,?,?,?,?)}            (10 parámetros, el último OUTPUT)
     SQL_NumerarStaging    {call etl.usp_NumerarStaging(?)}
     SQL_Fin (EVA)         {call etl.usp_CerrarLote(?, DEFAULT, DEFAULT, DEFAULT, DEFAULT, ?, ?, ?)}
     SQL_Fin (FAOSTAT)     {call etl.usp_CerrarLote(?)}
     EH_LogError           {call audit.usp_RegistrarEvento(?,?,?,DEFAULT×5,?,?,?,?,?)}
============================================================================= */
USE Wololo_ETL;
GO

/* ------------------------------------------------------------ bitácora */
CREATE OR ALTER PROCEDURE audit.usp_RegistrarEvento
    @Accion         NVARCHAR(30),
    @Descripcion    NVARCHAR(2000) = NULL,
    @IdLote         INT            = NULL,
    @Tabla          NVARCHAR(128)  = NULL,
    @IdRegistro     BIGINT         = NULL,
    @ValorAnterior  NVARCHAR(400)  = NULL,
    @ValorNuevo     NVARCHAR(400)  = NULL,
    @Usuario        NVARCHAR(128)  = NULL,
    @TipoActor      NVARCHAR(10)   = N'SSIS',
    @Mecanismo      NVARCHAR(15)   = N'PAQUETE',
    @PackageName    NVARCHAR(128)  = NULL,
    @SourceName     NVARCHAR(128)  = NULL,
    @ExecutionGUID  NVARCHAR(50)   = NULL
AS
BEGIN
    SET NOCOUNT ON;
    INSERT audit.Log (Accion, Descripcion, IdLote, Tabla, IdRegistro, ValorAnterior, ValorNuevo,
                      Usuario, TipoActor, Mecanismo, PackageName, SourceName, ExecutionGUID)
    VALUES (@Accion, @Descripcion, NULLIF(@IdLote, 0), @Tabla, @IdRegistro, @ValorAnterior, @ValorNuevo,
            COALESCE(@Usuario, SUSER_SNAME()), @TipoActor, @Mecanismo, @PackageName, @SourceName, @ExecutionGUID);
END
GO

/* ------------------------------------------------------ apertura de lote
   Idempotencia: si la clave ya existe, se borra en cascada todo lo que ese
   lote cargó (staging, limpios, revisión, límites IQR y unidades) y se reabre
   con el mismo IdLote. Así, repetir el mismo lote no duplica registros.     */
CREATE OR ALTER PROCEDURE etl.usp_AbrirLote
    @LoteClave      NVARCHAR(60),
    @Dataset        NVARCHAR(12),
    @Iteracion      INT,
    @ReglasVersion  NVARCHAR(10),
    @Tipo           NVARCHAR(10),
    @ArchivoOrigen  NVARCHAR(1000),
    @PackageName    NVARCHAR(128) = NULL,
    @TaskName       NVARCHAR(128) = NULL,
    @ExecutionGUID  NVARCHAR(50)  = NULL,
    @IdLote         INT OUTPUT
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;
    BEGIN TRAN;

    SELECT @IdLote = IdLote FROM etl.Lote WITH (UPDLOCK, HOLDLOCK) WHERE LoteClave = @LoteClave;

    IF @IdLote IS NULL
    BEGIN
        INSERT etl.Lote (LoteClave, Dataset, Iteracion, ReglasVersion, Tipo, ArchivoOrigen)
        VALUES (@LoteClave, @Dataset, @Iteracion, @ReglasVersion, @Tipo, @ArchivoOrigen);
        SET @IdLote = SCOPE_IDENTITY();
        COMMIT;
        EXEC audit.usp_RegistrarEvento @Accion = N'LOTE_ABIERTO', @Descripcion = @LoteClave, @IdLote = @IdLote,
             @Mecanismo = N'TAREA', @PackageName = @PackageName, @SourceName = @TaskName, @ExecutionGUID = @ExecutionGUID;
        RETURN;
    END

    DELETE FROM dbo.EVA_Revision      WHERE IdLote = @IdLote;
    DELETE FROM dbo.EVA_Limpios       WHERE IdLote = @IdLote;
    DELETE FROM dbo.stg_EVA           WHERE IdLote = @IdLote;
    DELETE FROM dbo.FAOSTAT_Revision  WHERE IdLote = @IdLote;
    DELETE FROM dbo.FAOSTAT_Limpios   WHERE IdLote = @IdLote;
    DELETE FROM dbo.stg_FAOSTAT       WHERE IdLote = @IdLote;
    DELETE FROM cat.LimiteIQR         WHERE IdLote = @IdLote;
    DELETE FROM cat.UnidadReferencia  WHERE IdLote = @IdLote;

    UPDATE etl.Lote
       SET Estado = N'ABIERTO', FechaApertura = SYSDATETIME(), FechaCierre = NULL,
           Iteracion = @Iteracion, ReglasVersion = @ReglasVersion, Tipo = @Tipo,
           ArchivoOrigen = @ArchivoOrigen, VecesAbierto = VecesAbierto + 1
     WHERE IdLote = @IdLote;
    COMMIT;

    EXEC audit.usp_RegistrarEvento @Accion = N'LOTE_REABIERTO', @Descripcion = @LoteClave, @IdLote = @IdLote,
         @Mecanismo = N'TAREA', @PackageName = @PackageName, @SourceName = @TaskName, @ExecutionGUID = @ExecutionGUID;
END
GO

/* ------------------------------------------ numeración de filas del staging */
CREATE OR ALTER PROCEDURE etl.usp_NumerarStaging
    @IdLote INT
AS
BEGIN
    SET NOCOUNT ON;
    ;WITH e AS (SELECT NumeroFila, ROW_NUMBER() OVER (ORDER BY IdStg) AS rn FROM dbo.stg_EVA WHERE IdLote = @IdLote)
    UPDATE e SET NumeroFila = rn; -- NOSONAR: WHERE clause is inside the CTE definition above

    ;WITH f AS (SELECT NumeroFila, ROW_NUMBER() OVER (PARTITION BY Dataset ORDER BY IdStg) AS rn
                FROM dbo.stg_FAOSTAT WHERE IdLote = @IdLote)
    UPDATE f SET NumeroFila = rn; -- NOSONAR: WHERE clause is inside the CTE definition above
END
GO

/* ---------------------------------------------------------- cierre de lote
   Si se llama desde EH_CerrarLoteFallido (OnError) el lote queda FALLIDO:
   se detecta porque ya existe un ERROR_PAQUETE para ese lote en esta ejecución. */
CREATE OR ALTER PROCEDURE etl.usp_CerrarLote
    @IdLote         INT,
    @Estado         NVARCHAR(12)  = NULL,
    @Mensaje        NVARCHAR(400) = NULL,
    @FilasLimpias   INT           = NULL,
    @FilasRevision  INT           = NULL,
    @PackageName    NVARCHAR(128) = NULL,
    @TaskName       NVARCHAR(128) = NULL,
    @ExecutionGUID  NVARCHAR(50)  = NULL
AS
BEGIN
    SET NOCOUNT ON;
    IF @Estado IS NULL
        SET @Estado = CASE WHEN EXISTS (SELECT 1 FROM audit.Log
                                         WHERE IdLote = @IdLote AND Accion = N'ERROR_PAQUETE'
                                           AND (@ExecutionGUID IS NULL OR ExecutionGUID = @ExecutionGUID)
                                           AND Fecha >= (SELECT FechaApertura FROM etl.Lote WHERE IdLote = @IdLote))
                           THEN N'FALLIDO' ELSE N'CERRADO' END;

    UPDATE etl.Lote SET Estado = @Estado, FechaCierre = SYSDATETIME() WHERE IdLote = @IdLote;

    EXEC audit.usp_RegistrarEvento
         @Accion = CASE WHEN @Estado = N'FALLIDO' THEN N'LOTE_FALLIDO' ELSE N'LOTE_CERRADO' END,
         @Descripcion = @Mensaje, @IdLote = @IdLote, @Mecanismo = N'TAREA',
         @PackageName = @PackageName, @SourceName = @TaskName, @ExecutionGUID = @ExecutionGUID;
END
GO
