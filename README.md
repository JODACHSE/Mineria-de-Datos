# Wololo · Seguridad alimentaria y producción agrícola — Colombia

Proyecto de Minería de Datos de **Wololo** (Universidad de Cundinamarca).
Sitio web en **Flask** que presenta el entregable **R1 · Del problema a
los datos**: problema y contexto, preguntas analíticas, fuentes, dataset
inicial, diccionario de datos, caracterización, diagnóstico de calidad,
limitaciones y evidencia visual, con un explorador de datos interactivo
respaldado por una API propia; y el entregable **R2 · Diagnóstico y
calidad de los datos**: perfilamiento por columna, las 6 dimensiones de
calidad (completitud, exactitud, consistencia, unicidad, validez,
actualidad) con métricas verificables, inventario de problemas, análisis
de causas, integración/homologación y un tratamiento real (no solo
documentado) aplicado a los 4 datasets, con comparación antes/después.

**Equipo:** Jonathan David Chavarro Segura ([@JODACHSE](https://github.com/JODACHSE)) ·
Andrés Felipe Rodríguez Correa ([@N3X4N](https://github.com/N3X4N))
**Cobertura:** Colombia (nacional) · **Periodo:** 2000–2024
**Fuentes:** EVA · MinAgricultura/UPRA (producción municipal, dataset real de 48.932 registros) + FAOSTAT · FAO (seguridad alimentaria y producción nacional/global) + ENSIN, DANE, World Bank, Our World in Data (contexto)

---

## ✨ Características

- **Backend dinámico**: filtros y paginación de los datasets FAOSTAT se
  resuelven en el servidor (`/api/dataset/<nombre>`), no en un JSON
  estático volcado al navegador.
- **Diagnóstico de calidad en vivo**: completitud, unicidad y validez se
  calculan en cada solicitud (`/api/quality/<nombre>`), no están
  hard-codeados en la plantilla.
- **R2 · Calidad de datos**: perfilamiento por columna y las 6 dimensiones
  de calidad se calculan en vivo (`/api/profile/<nombre>`) sobre la
  versión cruda y la versión tratada de cada dataset
  (`/api/dataset/<nombre>?version=tratado`); el tratamiento real
  (`scripts/clean_datasets.py`) nunca elimina filas ni fabrica valores —
  corrige lo no ambiguo (tipos, llave de unicidad, fechas) y marca el
  resto con banderas (`_flag_*`, `_outlier_*`).
- **Diseño de marca Wololo**: retícula técnica ("instrumento de campo") +
  tarjetas neumórficas, tema claro/oscuro (el oscuro retoma los colores
  exactos del escudo Wololo: verde pino + gris pizarra), tipografía
  Orbitron / Exo 2 / Space Mono.
- **Motion & sonido**: animaciones de entrada por scroll
  (`IntersectionObserver`), ícono de marca con glow animado, y sonidos de
  interfaz **sintetizados con Web Audio API** (clic, hover, toggle) — no
  dependen de archivos de audio externos. El botón de sonido muestra un
  ícono con barra diagonal cuando está muteado.
- **Gráfico interactivo** de la serie histórica de seguridad alimentaria
  (Chart.js) alimentado por `faostat_fs_colombia.json`.

- **Dataset real integrado**: producción agrícola municipal de EVA
  (48.932 registros, 32 departamentos, 6 cultivos básicos, 2019–2024,
  formato numérico colombiano convertido) cruzado con FAOSTAT a nivel
  nacional por cultivo y año — ver `/r1#integracion`.
- **Responsive**, con foco visible por teclado y `prefers-reduced-motion`
  respetado.

## 🧱 Stack

- Flask 3 (blueprints `project` y `lessons`)
- Bootstrap 5.3.8 (solo grid/utilidades — la identidad visual es propia)
- Chart.js 4 (CDN)
- Vanilla JS (sin build step)
- pandas / requests / `faostat` (scripts de adquisición de datos)

## 📁 Estructura

```
Mineria de Datos/
├── app/
│   ├── data/                     # CSV originales (trazabilidad)
│   │   ├── eva_basicos_colombia.csv      # EVA real, sin modificar
│   │   └── faostat_*.csv
│   ├── routes/                   # blueprints: project.py, lessons.py (blueprint 'entregables')
│   ├── quality.py                # esquemas, perfilamiento, 6 dimensiones e inventario (R2)
│   ├── etapas.py                 # las 8 etapas/entregables (global de plantilla)
│   ├── static/
│   │   ├── assets/fonts|img/     # tipografías (CDN) e imágenes
│   │   ├── css/styles.css        # sistema de diseño
│   │   ├── data/R1/*.json        # datasets curados (crudos): fs, qcl, qcl_basicos,
│   │   │                         # eva_basicos, integracion_eva_faostat
│   │   ├── data/R2/*.json        # datasets tratados (con banderas) + log_tratamiento.json
│   │   ├── js/index.js
│   │   └── favicon.ico
│   ├── templates/
│   │   ├── components/           # navbar.html, footer.html
│   │   ├── layouts/base.html
│   │   ├── entregables/          # index.html, about.html
│   │   └── project/
│   │       ├── index.html
│   │       └── project/R1.html, R2.html
│   ├── __init__.py               # application factory
│   └── config.py
├── scripts/
│   ├── fetch_faostat.py          # descarga reproducible vía API
│   ├── rebuild_chart.py          # regenera JSON de FAOSTAT desde los CSV
│   ├── process_eva.py            # limpia y regenera eva_basicos.json + integración (R1)
│   └── clean_datasets.py         # tratamiento real de calidad de los 4 datasets (R2)
├── docs/
│   └── informe-tecnico-etapa2.md # informe técnico de la Etapa 2
├── tests/                        # test_app.py (rutas) + test_quality.py (perfilamiento/dimensiones)
├── setup.sh / setup.bat          # arranque en un solo comando
├── .env / .gitignore
├── requirements.txt
└── run.py
```

## 🚀 Puesta en marcha

### Opción rápida (un solo comando)

```bash
# Linux / macOS
./setup.sh

# Windows (cmd o PowerShell)
setup.bat
```

Cada script crea el entorno virtual `.venv` si no existe, instala las
dependencias de `requirements.txt` y arranca el servidor en
`http://127.0.0.1:5000`.

### Opción manual

```bash
# 1) Crear y activar un entorno virtual
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate

# 2) Instalar dependencias
pip install -r requirements.txt

# 3) Variables de entorno
# el archivo .env ya trae valores por defecto funcionales;
# FAOSTAT_TOKEN solo es necesario si vas a re-descargar datos

# 4) Ejecutar
python run.py
# → http://127.0.0.1:5000
```

## 🔌 Rutas principales

| Ruta | Descripción |
|------|-------------|
| `/` | Landing del proyecto |
| `/r1` | Entregable R1 completo |
| `/r2` | Entregable R2: diagnóstico y calidad de los datos |
| `/entregables` | Hoja de ruta con las 8 etapas del proyecto |
| `/sobre-nosotros` | El equipo Wololo y la afiliación académica |
| `/api/dataset/<qcl\|qcl_basicos\|fs\|eva_basicos>` | Datos paginados/filtrados (JSON) |
| `/api/quality/<qcl\|qcl_basicos\|fs\|eva_basicos>` | Diagnóstico de calidad recalculado (R1) |
| `/api/profile/<qcl\|qcl_basicos\|fs\|eva_basicos>` | Perfilamiento por columna + 6 dimensiones (R2) |

Parámetros soportados por `/api/dataset/<name>`: `q`, `producto`,
`elemento`, `anio_min`, `anio_max`, `page`, `page_size`, y
`version=crudo|tratado` (default `crudo`) para alternar entre la versión
de R1 y la tratada de R2. `/api/profile/<name>` admite el mismo
parámetro `version`.

## 🔁 Reproducir la descarga de datos

```bash
export FAOSTAT_TOKEN="tu_token_jwt"
python scripts/fetch_faostat.py     # descarga completa de FAOSTAT vía API
python scripts/rebuild_chart.py     # o solo regenerar JSON de FAOSTAT desde los CSV
python scripts/process_eva.py       # limpia app/data/eva_basicos_colombia.csv y
                                     # regenera eva_basicos.json + la tabla de
                                     # integración EVA↔FAOSTAT
python scripts/clean_datasets.py    # tratamiento real de calidad (R2): lee
                                     # app/static/data/R1/*.json y escribe
                                     # app/static/data/R2/*.json + log_tratamiento.json
```

El dataset EVA (48.932 registros reales de producción municipal, 6
cultivos básicos, 2019–2024) se descargó manualmente desde el portal
de Datos Abiertos Colombia con un filtro por cultivo aplicado en la
interfaz — la API SODA con parámetros de filtro no era accesible
desde este entorno de desarrollo. El CSV original queda intacto en
`app/data/eva_basicos_colombia.csv`; `scripts/process_eva.py` documenta
exactamente qué transformaciones se le aplicaron (ver comentarios del
script).

## ✅ Pruebas

```bash
pytest
```

## 📚 Fuentes y licencias

- **EVA — Evaluaciones Agropecuarias Municipales** (MinAgricultura/UPRA),
  Datos Abiertos Colombia — datos abiertos, uso libre con atribución.
- **FAOSTAT** (FAO) — CC BY-4.0, atribución a FAO.
- **ENSIN 2015** (ICBF/MinSalud) — publicación institucional de acceso público.
- **DANE** (IPC) — datos abiertos, uso estadístico público.
- **World Bank Open Data** — CC BY-4.0.
- **Our World in Data** — CC BY 4.0.
- Uso estrictamente académico.
