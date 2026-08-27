@echo off
REM setup.bat — arranque en un solo comando (Windows)
REM
REM Uso: doble clic o "setup.bat" desde la terminal (cmd o PowerShell)
REM
REM Crea el entorno virtual si no existe, instala/actualiza dependencias
REM y levanta el servidor de desarrollo de Flask en http://127.0.0.1:5000

setlocal enabledelayedexpansion
cd /d "%~dp0"

if not exist ".venv" (
    echo Creando entorno virtual .venv...
    python -m venv .venv
    if errorlevel 1 (
        echo.
        echo [ERROR] No se pudo crear el entorno virtual. Verifica que Python
        echo este instalado y disponible en PATH ^(python --version^).
        pause
        exit /b 1
    )
)

call .venv\Scripts\activate.bat

echo Instalando dependencias...
python -m pip install --upgrade pip -q
pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo [ERROR] La instalacion de dependencias fallo. Revisa el mensaje de
    echo pip mas arriba antes de continuar. Causas comunes:
    echo   - Version de Python muy nueva/vieja sin wheel precompilado para
    echo     alguna libreria ^(prueba con Python 3.11 o 3.12^).
    echo   - Sin conexion a internet.
    echo No se iniciara el servidor.
    pause
    exit /b 1
)

if not exist ".env" (
    echo No se encontro .env, se usaran los valores por defecto de config.py
)

echo.
echo Iniciando servidor Flask...  ^(Ctrl+C para detener^)
echo    http://127.0.0.1:5000
echo.
python run.py

pause
