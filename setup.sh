#!/usr/bin/env bash
# setup.sh — arranque en un solo comando (Linux / macOS)
#
# Uso:
#   chmod +x setup.sh   (solo la primera vez)
#   ./setup.sh
#
# Crea el entorno virtual si no existe, instala/actualiza dependencias
# y levanta el servidor de desarrollo de Flask en http://127.0.0.1:5000

cd "$(dirname "$0")"

PYTHON_BIN="${PYTHON_BIN:-python3}"

if [ ! -d ".venv" ]; then
  echo "→ Creando entorno virtual (.venv)…"
  if ! "$PYTHON_BIN" -m venv .venv; then
    echo ""
    echo "[ERROR] No se pudo crear el entorno virtual. Verifica que Python 3"
    echo "esté instalado (prueba: $PYTHON_BIN --version)."
    exit 1
  fi
fi

# shellcheck disable=SC1091
source .venv/bin/activate

echo "→ Instalando dependencias…"
pip install --upgrade pip -q
if ! pip install -r requirements.txt; then
  echo ""
  echo "[ERROR] La instalación de dependencias falló. Revisa el mensaje de"
  echo "pip arriba antes de continuar. Causas comunes:"
  echo "  - Versión de Python muy nueva/vieja sin wheel precompilado para"
  echo "    alguna librería (prueba con Python 3.11 o 3.12)."
  echo "  - Sin conexión a internet."
  echo "No se iniciará el servidor."
  exit 1
fi

if [ ! -f ".env" ]; then
  echo "→ No se encontró .env, se usarán los valores por defecto de config.py"
fi

echo ""
echo "→ Iniciando servidor Flask…  (Ctrl+C para detener)"
echo "   http://127.0.0.1:5000"
echo ""
python run.py
