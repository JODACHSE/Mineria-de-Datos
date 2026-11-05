# R5 · Modelo multidimensional — diagrama y diccionario

Data mart en estrella sobre el EVA tratado en R2/R3 (`app/static/data/R2/eva_basicos.json`,
48.932 registros, 2019–2024, 1.098 municipios, 32 departamentos, 6 cultivos básicos).
Implementado en **SQLite** (`app/data/R5/wololo_dw.sqlite`, se genera; no se versiona).

Preguntas, ejemplos de operaciones OLAP, conocimientos y resultados de las validaciones:
[`analisis_multidimensional.md`](analisis_multidimensional.md).

- **Unidad de análisis:** la producción de un cultivo básico en un municipio.
- **Granularidad de la tabla de hechos:** 1 municipio × 1 desagregación de cultivo × 1 periodo agrícola
  (semestre A/B para transitorios; año para el plátano, permanente).

## Diagrama

```mermaid
erDiagram
    dim_territorio ||--o{ fact_produccion_agricola : territorio_key
    dim_tiempo ||--o{ fact_produccion_agricola : tiempo_key
    dim_cultivo ||--o{ fact_produccion_agricola : cultivo_key
    dim_sistema_productivo ||--o{ fact_produccion_agricola : sistema_key

    fact_produccion_agricola {
        int hecho_id PK
        int territorio_key FK
        int tiempo_key FK
        int cultivo_key FK
        int sistema_key FK
        real area_sembrada_ha
        real area_cosechada_ha
        real produccion_t
        real rendimiento_reportado_t_ha
        int area_incoherente
    }
    dim_territorio {
        int territorio_key PK
        text cod_municipio UK
        text municipio
        text cod_departamento
        text departamento
        text region
        text tipo_entidad
        text capital
        real latitud
        real longitud
    }
    dim_tiempo {
        int tiempo_key PK
        text periodo_codigo UK
        int anio
        text periodo
        text tipo_periodo
        text trienio
        text meses
        text etapa_desagregacion
    }
    dim_cultivo {
        int cultivo_key PK
        text desagregacion UK
        int codigo_cultivo
        text cultivo
        text grupo
        text subgrupo
        text variedad
        text ciclo
        text estado_fisico
        text nombre_cientifico
        int anio_desde
        int anio_hasta
    }
    dim_sistema_productivo {
        int sistema_key PK
        text sistema UK
        text criterio
        text descripcion
        text cultivos
        text desagregaciones
    }
```

La restricción `UNIQUE (territorio_key, cultivo_key, tiempo_key)` impone la granularidad. Cada
dimensión tiene el miembro `0 = Desconocido` para claves faltantes (hoy ningún hecho lo usa).

Se distinguen tres casos: **faltante** (medida sin dato → `NULL`, ignorado por `SUM`), **categoría desconocida**
(hecho sin municipio/cultivo/sistema identificable → clave `0`) y **respuesta negativa** (EVA reporta 0, p. ej.
área cosechada 0 = no hubo cosecha → se conserva como 0).

## Dimensiones y jerarquías

| Dimensión | Pregunta | Filas | Atributos | Jerarquía | Atributos de análisis | Justificación |
|---|---|---|---|---|---|---|
| `dim_territorio` | ¿Dónde? | 1.098 + Desconocido | 10: cod_municipio, municipio, cod_departamento, departamento, region, tipo_entidad, capital, latitud, longitud | Región → Departamento → Municipio | capital | DIVIPOLA: cada municipio en un departamento; cada departamento en una región natural. Tipo y coordenadas desde el CSV DIVIPOLA (`app/data/`) |
| `dim_tiempo` | ¿Cuándo? | 18 | 8: periodo_codigo, anio, periodo, tipo_periodo, trienio, meses, etapa_desagregacion | Trienio → Año → Periodo | periodo (semestre), etapa_desagregacion | Trienios de igual duración; la etapa separa los años antes y después del cambio de desagregación de 2021 |
| `dim_cultivo` | ¿Qué? | 16 + Desconocido | 12: desagregacion, codigo_cultivo, cultivo, grupo, subgrupo, variedad, ciclo, estado_fisico, nombre_cientifico, anio_desde, anio_hasta | Grupo → Cultivo → Desagregación | variedad, estado_fisico | Cada desagregación EVA pertenece a un cultivo y este a un grupo; la vigencia documenta las desagregaciones reemplazadas |
| `dim_sistema_productivo` | ¿Cómo / para qué? | 7 + Desconocido | 6: sistema, criterio, descripcion, cultivos, desagregaciones | Criterio → Sistema | — | Nivel tecnológico (maíz/arroz), destino (plátano/yuca) o sin diferenciar (papa/frijol) |

El detalle de cada atributo (tipo, rol, descripción, origen, valores distintos y ejemplos) está en
[`analisis_multidimensional.md` § 3](analisis_multidimensional.md#3-diccionario-de-dimensiones) y en `/r5#diccionario`.

**Hallazgo del diseño:** el atributo `estado_fisico` muestra que EVA reporta el maíz «En fresco» en 2019–2020
(desagregaciones *Maíz tecnificado/tradicional*) y en «Grano seco» desde 2021 (*Maíz amarillo/blanco …*), por lo que las
toneladas de maíz de ambas etapas no son del todo comparables (ver limitación de C3).

Mapeo desagregación → sistema: tecnificado = maíz tecnificado (y amarillo/blanco tecnificado), arroz riego,
arroz secano mecanizado; tradicional = maíz tradicional (y amarillo/blanco tradicional), arroz secano manual;
consumo interno / exportación = plátano; consumo en fresco / industrial = yuca; sin diferenciar = papa y frijol.

## Medidas

| Medida | Unidad | Fórmula | Agregación | ¿Se puede sumar? |
|---|---|---|---|---|
| Producción | t | `SUM(produccion_t)` | SUM | Sí, en todas las dimensiones |
| Área sembrada | ha | `SUM(area_sembrada_ha)` | SUM | Sí (al sumar semestres cuenta hectárea-semestre) |
| Área cosechada | ha | `SUM(area_cosechada_ha)` | SUM | Sí |
| Área no cosechada | ha | `SUM(sembrada) − SUM(cosechada)` | diferencia de sumas | Sí (neta) |
| Rendimiento ponderado | t/ha | `SUM(produccion_t) / SUM(area_cosechada_ha)` | cociente | **No**: se recalcula; nunca se promedian rendimientos |
| Tasa de cosecha | % | `100 × SUM(cosechada) / SUM(sembrada)` | cociente | **No**: se recalcula en cada nivel |
| Registros | registros | `COUNT(*)` | COUNT | Sí (conteo de filas, no de entidades) |
| Municipios únicos | municipios | `COUNT(DISTINCT territorio_key)` | COUNT DISTINCT | **No**: los subtotales no se suman |

Las participaciones (%) indican su denominador (total de la selección, de la fila o de la columna).

## Correspondencia de variables y transformaciones

| EVA tratado (R2) | Modelo | Transformación |
|---|---|---|
| CodigoMunicipioDane, Municipio | dim_territorio.cod_municipio, municipio | trim; clave natural → `territorio_key` |
| CodigoDeptoDane, Departamento | dim_territorio.cod_departamento, departamento | sin cambios |
| Departamento | dim_territorio.region | mapeo departamento → región (el de R4) |
| Anio, Periodo | dim_tiempo.anio, periodo_codigo, periodo, tiempo_key | `2019A` → Semestre A (20191), `B` → Semestre B (20192), vacío → Anual (20190) |
| Anio | dim_tiempo.trienio | 2019–2021 / 2022–2024 |
| DesagregacionCultivo, Cultivo, GrupoCultivo, CicloCultivo, EstadoFisico, NombreCientifico, CodigoCultivo | dim_cultivo.* | una fila por desagregación |
| DesagregacionCultivo | dim_sistema_productivo | diccionario 16 → 7 sistemas |
| AreaSembrada, AreaCosechada, Produccion | area_sembrada_ha, area_cosechada_ha, produccion_t | numéricas; faltante → NULL, nunca 0 (no hay faltantes); 0 = respuesta negativa reportada (2.298 hechos sin cosecha) |
| Rendimiento | rendimiento_reportado_t_ha | solo trazabilidad |
| _flag_area_incoherente | area_incoherente | 0/1; atributo degenerado usado como filtro |
| Subgrupo | dim_cultivo.subgrupo | sin cambios |
| DIVIPOLA: Tipo, Latitud, Longitud | dim_territorio.tipo_entidad, latitud, longitud | cruce por código de municipio; coma decimal → punto |
| CodigoMunicipioDane | dim_territorio.capital | código DDD001 → «Capital departamental» |
| Anio, Periodo | dim_tiempo.meses, etapa_desagregacion | A → Ene–Jun, B → Jul–Dic, anual → Ene–Dic; ≤ 2020 → anterior, ≥ 2021 → actual |
| DesagregacionCultivo, Anio | dim_cultivo.variedad, anio_desde, anio_hasta | variedad según el nombre; vigencia = primer y último año con registros |
| _outlier_iqr_* | — | no cargados (atípicos ya tratados en R2) |

## Carga y validación

```bash
python scripts/R5/build_star.py          # crea la base, carga y valida (28 comprobaciones)
python scripts/R5/export_docs.py         # regenera analisis_multidimensional.md desde el modelo
sqlite3 app/data/R5/wololo_dw.sqlite < SQL/R5/02_validaciones.sql
```

La app también construye la base al arrancar si no existe o si el JSON tratado es más reciente
(`app/services/dw.py → ensure`). Scripts: `SQL/R5/01_modelo_estrella.sql` (tablas y relaciones),
`02_validaciones.sql`, `03_consultas_olap.sql` (operaciones y preguntas).

Herramientas: SQLite (incluido en Python, un solo archivo, consultable desde Flask y desplegable en
Render, donde el SQL Server de R3 no está disponible) y Python estándar para el ETL (sin dependencias nuevas).
