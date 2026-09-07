# Informe técnico — Etapa 2 · Diagnóstico y Calidad de los Datos

**Proyecto:** Wololo · Seguridad alimentaria y producción agrícola en Colombia (2000–2024)
**Equipo:** Jonathan David Chavarro Segura ([@JODACHSE](https://github.com/JODACHSE)) ·
Andrés Felipe Rodríguez Correa ([@N3X4N](https://github.com/N3X4N))
**Rama de trabajo:** `Feature/etapa-2` (desde `main`) · **Entregable en la app:** [`/r2`](../app/templates/project/project/R2.html)
**Fecha:** 2026-09-05

> Este documento incluye las evidencias (tablas, cifras, fórmulas) directamente en el texto,
> calculadas con el código real del repositorio (`app/quality.py`, `scripts/clean_datasets.py`),
> no simuladas. Los recuadros `[CAPTURA: ...]` marcan dónde el equipo debe pegar una captura de
> pantalla de `/r2` antes de entregar el documento final.

---

## 1 · Objetivo

Aplicar perfilamiento, diagnóstico, medición en 6 dimensiones y tratamiento real de calidad de
datos sobre los 4 datasets consolidados en R1, integrar los resultados en la aplicación Flask
(sección **Calidad de Datos**, ruta `/r2`), gestionar el trabajo en una rama propia
(`Feature/etapa-2`) con commits identificables, y documentar el proceso paso a paso.

## 2 · Propósito y alcance de los datos

| Dataset | Fuente | Registros | Nivel | Formato |
|---|---|---:|---|---|
| `eva_basicos` | EVA — MinAgricultura/UPRA | 48.932 | Municipal, 2019–2024 | Ancho (18 columnas) |
| `qcl` | FAOSTAT (todos los productos) | 9.274 | Nacional, 2000–2024 | Largo (Área/Producto/Elemento/Año/Unidad/Valor) |
| `qcl_basicos` | FAOSTAT (6 cultivos básicos) | 374 | Nacional, 2000–2024 | Largo |
| `fs` | FAOSTAT (seguridad alimentaria) | 1.138 | Nacional, 2000–2024 | Largo |

Estos 4 datasets sostienen el análisis de la paradoja *producción creciente vs. inseguridad
alimentaria* en Colombia: se usan para comparar fuentes, agregar por cultivo/año/territorio y
cruzarlas entre sí (ver `/r1#integracion`). Ese uso previsto define los requisitos de calidad de
la sección 3 — identificadores confiables, variables numéricas completas y en rango, categorías
homologadas entre EVA y FAOSTAT, vigencia razonable.

Los 4 datasets se perfilaron, midieron y trataron **por igual** en esta etapa; EVA concentra la
mayoría de los hallazgos por ser el dataset más grande y detallado a nivel municipal.

## 3 · Requisitos de calidad definidos

Umbral mínimo exigido por dimensión y dataset (`app/quality.py::QUALITY_REQUIREMENTS`):

| Dataset | Completitud | Exactitud | Consistencia | Unicidad | Validez | Actualidad |
|---|---:|---:|---:|---:|---:|---:|
| `eva_basicos` | ≥ 95% | ≥ 95% | ≥ 80% | ≥ 99% | ≥ 90% | ≥ 60% |
| `qcl` | ≥ 90% | ≥ 70% | ≥ 80% | ≥ 99% | ≥ 90% | ≥ 60% |
| `qcl_basicos` | ≥ 95% | ≥ 70% | ≥ 80% | ≥ 99% | ≥ 90% | ≥ 60% |
| `fs` | ≥ 90% | ≥ 90% | ≥ 80% | ≥ 99% | ≥ 90% | ≥ 40% |

El umbral de exactitud es más laxo para `qcl`/`qcl_basicos` (70%) porque su métrica de exactitud
se basa en el cruce EVA↔FAOSTAT (sección 7), y R1 ya documentó divergencias metodológicas reales
de entre -21% y +216% entre esas dos fuentes — exigir 90%+ ahí sería negar un hallazgo ya
conocido, no un requisito realista. El umbral de actualidad de `fs` es más bajo (40%) porque los
indicadores de seguridad alimentaria de FAO/SOFI tienen un rezago metodológico típico de 2-3 años
mayor al de las estadísticas de producción.

## 4 · Metodología de perfilamiento

Implementada en `app/quality.py::profile_columns`, calculada **en vivo** (Python puro, sin
precálculo ni pandas en tiempo de ejecución, consistente con la filosofía ya usada en R1) sobre
cada dataset cargado como lista de diccionarios. Por columna calcula: tipo inferido, cantidad y
% de nulos, cardinalidad (valores únicos), y — según el tipo declarado en `column_meta` — mínimo,
máximo, media, mediana, desviación estándar y valores atípicos (± 1.5×rango intercuartílico) para
numéricas, o los 5 valores más frecuentes para categóricas. Cuando la columna tiene un dominio,
rango o patrón esperado definido, también cuenta cuántos valores lo incumplen.

## 5 · Resultados del perfilamiento

### `eva_basicos` (48.932 filas × 18 columnas)

| Campo | Tipo | Nulos | Únicos | Detalle |
|---|---|---:|---:|---|
| CodigoDeptoDane / CodigoMunicipioDane | código | 0 | 32 / 1.096 | 5.854 (11.96%) no conformes al patrón de ancho fijo (ver sección 8) |
| Departamento / Municipio | categórico / texto | 0 | 32 / 1.106 | — |
| GrupoCultivo / Subgrupo / Cultivo | categórico | 0 | 4 / 4 / 6 | Cultivo: Maíz, Arroz, Papa, Plátano, Yuca, Frijol |
| Anio | temporal | 0 | 6 | 2019–2024 |
| Periodo | categórico | 0 | 2 | semestral |
| AreaSembrada | numérico | 0 | — | atípicos: 6.288 (12.85%) |
| AreaCosechada | numérico | 0 | — | atípicos: 6.505 (13.29%) |
| Produccion | numérico | 0 | — | atípicos: 7.368 (15.06%) |
| Rendimiento | numérico | 0 | — | atípicos: 3.342 (6.83%) |
| CicloCultivo / EstadoFisico | categórico | 0 | 2 / 3 | — |
| CodigoCultivo / NombreCientifico | código / texto | 0 | 6 / 6 | — |

### `qcl` (9.274 filas × 6 columnas)

| Campo | Tipo | Nulos | Detalle |
|---|---|---:|---|
| Área | categórico | 0 | único valor: "Colombia" |
| Producto / Elemento | categórico | 0 | múltiples cultivos/especies pecuarias y sus indicadores |
| Año | temporal | 0 | 2000–2024 (algunos como trienio) |
| Unidad | categórico | 0 | toneladas, kg/ha, cabezas, 1000 cabezas, No., 1000 No., … |
| Valor | numérico | 280 (3.02%) | atípicos agrupados por (Producto, Elemento): 327 de 8.994 evaluables (3.64%) |

### `qcl_basicos` (374 filas) y `fs` (1.138 filas)

Mismo esquema que `qcl`. `qcl_basicos`: 0 nulos, atípicos agrupados 7 de 374 (1.87%).
`fs`: 0 nulos, atípicos agrupados 3 de 1.134 evaluables (0.26%); trae además
`Confidence interval: Lower/Upper bound` para varios (Producto, Año), usado en la sección 7 como
mecanismo de exactitud.

## 6 · Las 6 dimensiones de calidad (medidas sobre la versión cruda)

Fórmulas en `app/quality.py::compute_dimensions`. Valores medidos (versión cruda, antes del
tratamiento):

| Dataset | Completitud | Exactitud | Consistencia | Unicidad | Validez | Actualidad |
|---|---:|---:|---:|---:|---:|---:|
| `eva_basicos` | 100% | 99.91% | 86.31% | 100% | **88.04%** | 80% |
| `qcl` | 99.25% | 35.15% | 99.73% | **99.73%** | 100% | 80% |
| `qcl_basicos` | 100% | 35.15% | 100% | 100% | 100% | 80% |
| `fs` | 100% | 100% | 100% | 100% | 100% | 93.33% |

**Cómo se calcula cada una** (con el resultado real de `eva_basicos` como ejemplo salvo que se
indique otro dataset):

- **Completitud** = `100 × (1 − nulos_en_campos_críticos / (n_filas × n_campos_críticos))`. EVA:
  0 nulos en sus 7 campos críticos → 100%.
- **Unicidad** = `100 × (n_filas − duplicados_bajo_llave_de_unicidad) / n_filas`. `qcl` con la
  llave original de R1 (sin `Unidad`): 99.73% (25 combinaciones "duplicadas" que en realidad son
  el mismo indicador en dos unidades — ver sección 9).
- **Validez** = `100 × (1 − filas_con_alguna_violación_de_rango/dominio/patrón_en_campos_críticos / n_filas)`.
  EVA: 88.04%, porque 5.854 filas (11.96%) tienen `CodigoMunicipioDane` sin el cero inicial
  (ver sección 9) — es la única fuente de invalidez detectada en este dataset.
- **Exactitud**: EVA compara `Producción / AreaCosechada` (calculado) vs. `Rendimiento`
  (reportado) con tolerancia relativa 1% → 99.91% de coincidencia. `qcl`/`qcl_basicos`: `100 −
  promedio(|Diferencia_pct|)` del cruce EVA↔FAOSTAT (`integracion_eva_faostat.json`) → 35.15%,
  reflejando las divergencias de -21% a +216% ya documentadas en R1. `fs`: % de grupos
  (Producto, Año) donde `Lower bound ≤ Valor ≤ Upper bound` → 100%.
- **Consistencia**: EVA compara `AreaCosechada` vs. `AreaSembrada` → 86.31% (13.69% de
  incoherencias). FAOSTAT compara la `Unidad` de cada fila contra la modal de su combinación
  (Producto, Elemento) → 99.73% en `qcl` (0.27% de filas con unidad atípica, exactamente el caso
  de los huevos).
- **Actualidad** = `100 × max(0, 1 − antigüedad_años / ventana)`, `antigüedad = 2026 − último_año`.
  EVA/QCL: último año 2024, ventana 10 → 80%. `fs`: ventana 15 (rezago metodológico SOFI) → 93.33%.

## 7 · Inventario de problemas

12 problemas identificados sobre la versión cruda de los 4 datasets. Nivel de impacto según
`app/quality.py::nivel_impacto` (Alto si el campo es crítico y ≥10% de registros afectados;
Medio si es crítico y ≥2%, o no crítico y ≥20%; Bajo en el resto).

| # | Dataset | Variable | Afectados | % | Dimensión | Impacto | Causa probable |
|---|---|---|---:|---:|---|---|---|
| 1 | qcl | Valor | 280 | 3.02% | Completitud | Medio | Ausencia de reporte / validación de campo obligatorio |
| 2 | eva_basicos | CodigoDeptoDane | 5.854 | 11.96% | Validez | Bajo | Formato inconsistente entre pipeline y fuente |
| 3 | eva_basicos | CodigoMunicipioDane | 5.854 | 11.96% | Validez | **Alto** | Conversión automática de tipo (pandas) al construir R1 |
| 4 | eva_basicos | AreaSembrada | 6.288 | 12.85% | Exactitud | Alto | Variabilidad real (municipios/cultivos de gran escala) |
| 5 | eva_basicos | AreaCosechada | 6.505 | 13.29% | Exactitud | Alto | Variabilidad real |
| 6 | eva_basicos | Produccion | 7.368 | 15.06% | Exactitud | Alto | Variabilidad real |
| 7 | eva_basicos | Rendimiento | 3.342 | 6.83% | Exactitud | Medio | Variabilidad real |
| 8 | eva_basicos | AreaCosechada / AreaSembrada | 6.700 | 13.69% | Consistencia | Alto | Re-siembra en el semestre o error de reporte municipal |
| 9 | qcl_basicos | Valor (por Producto/Elemento) | 7 | 1.87% | Exactitud | Bajo | Variabilidad de la serie o error puntual |
| 10 | qcl | Producto / Unidad | 50 | 0.54% | Unicidad | Bajo* | Llave de unicidad incompleta (sin `Unidad`) en R1 |
| 11 | qcl | Valor (por Producto/Elemento) | 327 | 3.64% | Exactitud | Medio | Variabilidad de la serie o error puntual |
| 12 | fs | Valor (por Producto/Elemento) | 3 | 0.26% | Exactitud | Bajo | Variabilidad de la serie o error puntual |

`*` El hallazgo #10 tiene impacto numérico bajo por volumen (0.54% de las filas), pero se destaca
aparte porque **invalida un supuesto de R1**: los "25 duplicados" que R1 reportaba en `qcl` no
eran errores de datos, sino el mismo indicador reportado en dos unidades (huevos en toneladas y
en miles de unidades) bajo una llave de verificación incompleta.

## 8 · Análisis de causas

- **Ausencia de validaciones en el origen:** los 280 nulos de `Valor` en `qcl` son series de
  FAOSTAT que no se midieron ese año; no existe un valor "correcto" que imputar.
- **Autorreporte municipal sin validación cruzada:** el 13.69% de incoherencias área
  cosechada/sembrada en EVA sugiere que ningún control impide que un municipio reporte una
  re-siembra o un error de captura antes de publicarse.
- **Definición de llave de unicidad incompleta (defecto de R1):** las 25 combinaciones de huevos
  en dos unidades se contaban como "duplicados" porque la llave de verificación de R1 no incluía
  `Unidad` — error de diseño de la validación, no del dato.
- **Conversión automática de tipos por la herramienta de procesamiento:** el CSV original de EVA
  sí trae los códigos DANE con cero inicial como texto (p. ej. `"05001"`); al construir
  `eva_basicos.json` en R1, la inferencia automática de tipos de `pandas` los convirtió a entero y
  perdió el cero inicial en los departamentos 01-09, afectando el 11.96% de las filas.
- **Heterogeneidad legítima de fuentes:** FAOSTAT reporta el mismo `Elemento` en unidades
  distintas según si el producto es un cultivo o una especie pecuaria — exige agrupar por
  (Producto, Elemento) al calcular cualquier estadístico sobre `Valor`, algo que R1 no hacía.
- **Falta de actualización:** ningún dataset tiene datos posteriores a 2024; la dimensión
  actualidad lo refleja con una fórmula explícita de antigüedad frente a la fecha de este
  entregable (2026).

## 9 · Integración y homologación

La homologación de nombres de cultivo entre EVA y FAOSTAT ya se resolvió en R1
(`CROP_MAPPING`, en `scripts/process_eva.py`), reutilizada sin cambios por el tratamiento:

| Cultivo (EVA) | Producto (FAOSTAT) |
|---|---|
| Maíz | Maíz |
| Arroz | Arroz |
| Papa | Papas, patatas |
| Plátano | Plátanos (Verde) y bananos para cocinar |
| Yuca | Yuca, fresca |
| Frijol | Frijoles, secos |

R2 añade dos correcciones de esquema adicionales, también de integración/homologación:

- **Llave de unicidad ampliada en FAOSTAT** (`+ Unidad`): homologa el criterio de identidad de
  fila entre datasets que antes lo tenían incompleto.
- **Formato de código DANE homogéneo** (texto de ancho fijo, 2 y 5 dígitos): homologa la
  representación de `CodigoDeptoDane`/`CodigoMunicipioDane` para que sea comparable con
  cualquier otra fuente oficial que use el estándar DANE (ENSIN, DANE-IPC).
- **`AnioNormalizado`** en los 3 datasets FAOSTAT: homologa el formato temporal (año puntual vs.
  trienio) sin destruir el campo `Año` original.

## 10 · Plan de tratamiento y acciones aplicadas

Ejecutado por `scripts/clean_datasets.py`, que lee la versión cruda de R1 y escribe la versión
tratada en `app/static/data/R2/*.json` + `log_tratamiento.json`. **Regla general: ningún registro
se elimina y ningún valor se fabrica** — lo corregible sin ambigüedad se corrige (tipos, llave de
unicidad, fechas); lo demás se marca con una bandera nueva (`_flag_*`, `_outlier_*`) para que el
análisis aguas abajo decida cómo tratarlo.

**27 acciones aplicadas en total** (detalle completo en `log_tratamiento.json`; resumen por tipo):

| Acción | Datasets | Decisión | Registros afectados |
|---|---|---|---:|
| Corrección de la llave de unicidad (+ Unidad) | qcl, qcl_basicos, fs | corrección | 50 / 0 / 0 |
| Tratamiento de valores nulos en 'Valor' | qcl, qcl_basicos, fs | flag / sin acción | 280 / 0 / 0 |
| Estandarización de texto (espacios/casing) | los 4 | sin acción (0 variantes encontradas) | 0 |
| Estandarización de fechas (`AnioNormalizado`) | qcl, qcl_basicos, fs | corrección | 9.274 / 374 / 1.138 |
| Homologación de unidad por (Producto, Elemento) | qcl, qcl_basicos, fs | flag / sin acción | 25 / 0 / 0 |
| Atípicos en 'Valor' (± 1.5×RIC por Producto/Elemento) | qcl, qcl_basicos, fs | flag | 327 / 7 / 3 |
| Eliminación de duplicados | eva_basicos | sin acción (0 encontrados) | 0 |
| Tratamiento de valores nulos | eva_basicos | sin acción (0 encontrados) | 0 |
| **Corrección de tipos de datos (códigos DANE)** | eva_basicos | **corrección** | **5.854** |
| Validación de rangos (AreaCosechada ≤ AreaSembrada) | eva_basicos | flag | 6.700 |
| Atípicos en AreaSembrada / AreaCosechada / Produccion / Rendimiento (± 1.5×RIC) | eva_basicos | flag | 6.288 / 6.505 / 7.368 / 3.342 |

Todas las justificaciones completas quedan en `app/static/data/R2/log_tratamiento.json` y se
muestran también en `/r2#tratamiento`.

## 11 · Comparación antes / después

Como el tratamiento marca en vez de corregir en silencio, la mayoría de las 6 dimensiones no
cambia numéricamente entre la versión cruda y la tratada — es intencional: el objetivo no era
"subir el número" sino volver visibles y trazables problemas que antes no lo eran. Dos excepciones
sí muestran una mejora real y medible, ambas por una corrección concreta y no ambigua:

| Dataset | Dimensión | Antes | Después | Qué cambió |
|---|---|---:|---:|---|
| `qcl` | Unicidad | 99.73% | **100%** | Se corrigió la llave de unicidad (+ `Unidad`) |
| `eva_basicos` | Validez | 88.04% | **100%** | Se corrigieron los códigos DANE (formato de ancho fijo) |

El resto de dimensiones permanece igual antes/después por diseño (política de "flag, no
fabricar"): p. ej. la consistencia de `eva_basicos` sigue en 86.31% porque las 6.700 filas con
área cosechada > sembrada quedan marcadas (`_flag_area_incoherente`) pero no se corrigen — no hay
forma no ambigua de saber cuál campo es el erróneo.

`[CAPTURA: gráfico comparativo antes/después de /r2#comparacion, para cada dataset]`

## 12 · Sección "Calidad de Datos" en la aplicación Flask

Implementada en `/r2` (`app/routes/project.py::r2`, plantilla
`app/templates/project/project/R2.html`), con: propósito del dataset, perfilamiento por columna,
las 6 dimensiones con requisitos y barra de progreso, inventario de problemas, causas,
integración/homologación, plan de tratamiento, comparación antes/después (tabla + gráfico Chart.js
con selector de dataset) y un explorador de datos con alternador crudo/tratado que muestra las
columnas de bandera como evidencia visible. Nuevos endpoints: `/api/profile/<name>` y
`/api/dataset/<name>?version=tratado`.

`[CAPTURA: hero y tabla de contenido de /r2]`
`[CAPTURA: tabla de perfilamiento de eva_basicos en /r2#perfilamiento]`
`[CAPTURA: barras de las 6 dimensiones en /r2#dimensiones]`
`[CAPTURA: tarjetas del inventario de problemas en /r2#problemas]`
`[CAPTURA: explorador de datos con version=tratado, mostrando columnas de bandera]`

## 13 · Gestión del desarrollo

Trabajo realizado en la rama `Feature/etapa-2` (creada desde `main`), con commits identificables
por unidad de trabajo:

1. `refactor: extraer DATASET_SCHEMA/compute_quality a app/quality.py`
2. `feat: perfilamiento, 6 dimensiones y script de tratamiento real (R2)`
3. `fix: agrupar outliers e inconsistencia de unidad por Producto+Elemento`
4. `feat: entregable R2 - rutas, plantilla y gráfico comparativo`
5. `test: cobertura de perfilamiento, dimensiones y rutas de R2`
6. `docs: informe técnico Etapa 2 con evidencias reales` (este documento)
7. `docs: actualizar README con R2`

El *pull request* hacia `main` lo revisa y crea el equipo (no se generó automáticamente); el
despliegue de la versión actualizada también lo gestiona el equipo en su servicio de hosting.

## 14 · Conclusiones y limitaciones

- Los 4 datasets cumplen la mayoría de los requisitos de calidad definidos en la sección 3; las
  excepciones documentadas (validez de EVA antes del tratamiento, exactitud de `qcl`/`qcl_basicos`
  frente al cruce con EVA) tienen causa raíz identificada y, cuando es corregible sin ambigüedad,
  ya fue corregida.
- La exactitud "baja" de `qcl`/`qcl_basicos` (35.15%) no es un error de este entregable: es la
  cuantificación formal de una divergencia metodológica entre EVA y FAOSTAT ya documentada en R1
  (EVA registra producción municipal total; FAOSTAT puede aplicar ajustes o excluir circuitos de
  comercialización). Cualquier análisis posterior debe declarar explícitamente qué fuente usa.
- El tratamiento aplicado es deliberadamente conservador: prioriza dejar trazabilidad (banderas)
  sobre "limpiar" agresivamente datos cuyo valor correcto no se puede determinar sin ambigüedad.
  Esto significa que el modelado de la siguiente etapa deberá decidir explícitamente cómo tratar
  las filas marcadas (excluir, ponderar, o usar tal cual), en vez de heredar una limpieza ya
  hecha silenciosamente.
- Limitación conocida: el perfilamiento y el tratamiento se ejecutan en Python puro sobre listas
  de diccionarios (sin pandas en tiempo de ejecución) para mantener la filosofía "en vivo" del
  proyecto; para datasets sustancialmente más grandes que EVA (48.932 filas) esto podría requerir
  revisarse por rendimiento, aunque en las pruebas realizadas cada cálculo toma bien por debajo
  de un segundo.
