"""R5 · Construye el modelo estrella y muestra sus validaciones.

Uso: python scripts/R5/build_star.py
Entrada: app/static/data/R2/eva_basicos.json · Salida: app/data/R5/wololo_dw.sqlite
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from app.config import Config  # noqa: E402
from app.services import dw  # noqa: E402
from app.services.olap import validations  # noqa: E402


def main() -> int:
    resumen = dw.build(Config.R5_SOURCE_JSON, Config.R5_DB_PATH)
    print(f"Base creada en {Config.R5_DB_PATH.relative_to(ROOT)}")
    for k, v in resumen.items():
        print(f"  {k:<24}{v:>8,}".replace(",", "."))

    print("\nValidaciones:")
    con = dw.connect(Config.R5_DB_PATH)
    ok = True
    for v in validations(con, Config.R5_SOURCE_JSON):
        ok &= v["ok"]
        print(f"  [{'OK' if v['ok'] else 'FALLA'}] {v['nombre']}: modelo={v['modelo']} · origen={v['origen']}")
    con.close()
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
