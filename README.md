# Wololo · Seguridad alimentaria y producción agrícola — Colombia

Proyecto de Minería de Datos de **Wololo** (Universidad de Cundinamarca).
Sitio web en **Flask** que publica los entregables **R1 · Del problema a los
datos** y **R2 · Diagnóstico y calidad de los datos**, con un explorador de
datos y métricas de calidad servidas por una API propia.

**Equipo:** Jonathan David Chavarro Segura ([@JODACHSE](https://github.com/JODACHSE)) ·
Andrés Felipe Rodríguez Correa ([@N3X4N](https://github.com/N3X4N))
**Cobertura:** Colombia (nacional) · **Periodo:** 2000–2024
**Fuentes:** EVA · MinAgricultura/UPRA (48.932 registros municipales) + FAOSTAT · FAO + ENSIN, DANE, World Bank, Our World in Data (contexto)

---

## Características

- **Bootstrap 5.3.8 nativo** — grid, componentes (navbar + offcanvas, dropdown,
  cards, badges, progress, accordion, tabs, toasts, scrollspy) y los **dos temas
  base claro/oscuro** de Bootstrap (`data-bs-theme`). El CSS propio cabe en
  ~50 líneas (`static/css/app.css`): solo motion y ajustes de layout.
- **Full responsive** — probado a 390 px y 1366 px en ambos temas.
- **Sonidos de interfaz** — librería [uisfx](https://www.npmjs.com/package/uisfx)
  (pack `zen`), cargada como módulo ES desde jsDelivr. Sintetiza cada sonido
  en el navegador con Web Audio API a partir de recetas deterministas: no
  hay archivos `.mp3` que alojar ni versionar. Botón de silencio persistente
  (uisfx guarda la preferencia en `localStorage`).
- **Contenido animado** — entrada por scroll, cifras con *count-up*, barras de
  calidad que se llenan al aparecer, transiciones de Bootstrap; respeta
  `prefers-reduced-motion`.
- **Backend dinámico** — filtros y paginación en el servidor
  (`/api/dataset/<nombre>`), calidad recalculada en vivo (`/api/quality`,
  `/api/profile`). Gráficos Chart.js que toman los colores de las variables CSS
  de Bootstrap y se redibujan al cambiar de tema.
- **Arquitectura limpia** — rutas delgadas, lógica en `services/`, plantillas
  por `layouts/` · `components/` · `macros/` · `pages/`, JS en módulos ES sin
  build step.
- **Listo para Render** — `render.yaml`, `Procfile`, `requirements.txt` mínimo
  para producción y `requirements-dev.txt` para scripts y tests.

## Estructura

```
.
├── app/
│   ├── __init__.py          # application factory + filtros Jinja + 404
│   ├── config.py            # configuración y metadatos del proyecto
│   ├── etapas.py            # las 8 etapas / entregables
│   ├── quality.py           # perfilamiento y 6 dimensiones (Python puro)
│   ├── routes/
│   │   ├── pages.py         # blueprint `pages`: /, /r1, /r2, /entregables, /sobre-nosotros
│   │   └── api.py           # blueprint `api`: /api/dataset, /api/quality, /api/profile
│   ├── services/
│   │   ├── datasets.py      # carga y caché de los JSON (R1 crudo / R2 tratado)
│   │   └── reports.py       # contextos de R1 y R2, consultas de la API
│   ├── templates/
│   │   ├── layouts/         # base.html (Bootstrap + temas) · report.html (hero + TOC + scrollspy)
│   │   ├── components/      # navbar, ticker, footer, toc, data_explorer, toast, back_to_top
│   │   ├── macros/ui.html   # stat, section_head, callout, tag, quality_bar, source_card…
│   │   ├── pages/           # home, r1, r2, entregables, about
│   │   └── errors/404.html
│   ├── static/
│   │   ├── css/app.css      # ~50 líneas propias
│   │   ├── js/app.js        # entrada; modules/: sound (uisfx), theme, motion, explorer, charts, notify
│   │   ├── data/R1|R2/      # datasets curados / tratados + log_tratamiento.json
│   │   └── assets/img/
│   └── data/                # CSV originales (trazabilidad)
├── scripts/                 # fetch_faostat, rebuild_chart, process_eva, clean_datasets
├── tests/                   # pytest: rutas, API y calidad
├── .github/workflows/ci.yml # pytest en cada push
├── render.yaml · Procfile · .python-version
├── requirements.txt · requirements-dev.txt
├── setup.sh · setup.bat · .env.example
└── run.py
```

## Puesta en marcha

```bash
./setup.sh        # Linux / macOS      (Windows: setup.bat)
# → http://127.0.0.1:5000
```

Manual:

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env
python run.py
```

### Despliegue en Render

1. Sube el repositorio a GitHub.
2. En Render: **New → Blueprint** y elige el repo; `render.yaml` crea el
   servicio web con `gunicorn run:app`.
3. (Alternativa manual) **New → Web Service**: *Build* `pip install -r
   requirements.txt`, *Start* `gunicorn run:app --workers 1 --threads 4
   --timeout 120 --preload`, variable `FLASK_DEBUG=0`.

`--preload` calcula el contexto de R2 (48.932 filas) una sola vez al arrancar.

## Rutas

| Ruta | Descripción |
|------|-------------|
| `/` | Landing |
| `/r1` · `/r2` | Entregables |
| `/entregables` | Hoja de ruta (8 etapas) |
| `/sobre-nosotros` | Equipo |
| `/api/dataset/<qcl\|qcl_basicos\|fs\|eva_basicos>` | Datos paginados (`q`, `producto`, `elemento`, `anio_min`, `anio_max`, `page`, `page_size`, `version=crudo\|tratado`) |
| `/api/quality/<nombre>` | Diagnóstico R1 |
| `/api/profile/<nombre>?version=` | Perfilamiento + 6 dimensiones (R2) |

## Reproducir los datos

```bash
export FAOSTAT_TOKEN="tu_token"
python scripts/fetch_faostat.py     # descarga FAOSTAT vía API
python scripts/rebuild_chart.py     # JSON de FAOSTAT desde CSV
python scripts/process_eva.py       # limpia EVA + integración EVA↔FAOSTAT (R1)
python scripts/clean_datasets.py    # tratamiento de calidad → data/R2 (R2)
```

## Pruebas

```bash
pytest
```

## Fuentes y licencias

EVA (MinAgricultura/UPRA, datos abiertos) · FAOSTAT (FAO, CC BY-4.0) ·
ENSIN 2015 (ICBF/MinSalud) · DANE (IPC) · World Bank Open Data (CC BY-4.0) ·
Our World in Data (CC BY 4.0). Uso estrictamente académico.
