#!/usr/bin/env bash
# Arranque en un solo comando (Linux / macOS): crea .venv, instala y levanta Flask.
cd "$(dirname "$0")"
PYTHON_BIN="${PYTHON_BIN:-python3}"
[[ -d .venv ]] || "$PYTHON_BIN" -m venv .venv || { echo "[ERROR] No se pudo crear .venv"; exit 1; }
# shellcheck disable=SC1091
source .venv/bin/activate
pip install --upgrade pip -q # NOSONAR: --only-binary would break source-only packages (faostat)
pip install -r requirements-dev.txt || { echo "[ERROR] Falló la instalación"; exit 1; } # NOSONAR
[[ -f .env ]] || cp .env.example .env
echo "→ http://127.0.0.1:5000  (Ctrl+C para detener)"
python run.py
