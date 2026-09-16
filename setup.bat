@echo off
REM Arranque en un solo comando (Windows): crea .venv, instala y levanta Flask.
cd /d "%~dp0"
if not exist .venv ( python -m venv .venv || ( echo [ERROR] No se pudo crear .venv & exit /b 1 ) )
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip -q
pip install -r requirements-dev.txt || ( echo [ERROR] Fallo la instalacion & exit /b 1 )
if not exist .env copy .env.example .env >nul
echo → http://127.0.0.1:5000  (Ctrl+C para detener)
python run.py
