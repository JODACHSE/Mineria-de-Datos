# R6 · Conocimiento oculto con Orange Data Mining

Carpeta de trabajo de la etapa 6: modelos supervisados y clustering en Orange, y análisis de texto de comentarios de YouTube (complemento Text).

```
orange/
├── data/          CSV generados por scripts/R6/preparar_datos_orange.py (+ log_preparacion.json)
│   └── youtube/   videos.csv · corpus.csv · stopwords_es.txt · factores_por_video.csv · logs
├── flujos/        01_supervisado.ows · 02_clustering.ows · 03_comentarios_youtube.ows
└── README.md      esta guía
scripts/R6/        preparar_datos_orange.py · generar_flujos_orange.py · params_flujo.py
                   extraer_comentarios_youtube.py · preparar_comentarios.py · factores_comentarios.py
                   generar_flujo_texto.py · youtube_config.json
```

## Cómo reproducir

1. `python scripts/R6/preparar_datos_orange.py` regenera los CSV desde `app/static/data/R2/eva_basicos.json` y deja en `orange/data/log_preparacion.json` cada filtro con su conteo y motivo.
2. En Orange: **File → Open** y elegir un `.ows` de `orange/flujos/`. Los widgets *File* usan rutas relativas a la carpeta del `.ows`, por lo que no dependen de dónde esté clonado el repo.
3. Los flujos se generaron y probaron con Orange **3.40** (y abren en versiones posteriores). Un flujo guardado con una versión más nueva puede no abrir bien en una más antigua: el widget *File* arrancaba con el dataset iris.
4. Al abrir un flujo, comprueba en *Datos* o en el pie de *Test and Score* que aparecen 39.934 filas (supervisado) o 1.098 (clustering).

## Flujo 1 · Supervisado

**Pregunta:** ¿el rendimiento de un registro (municipio × sistema productivo × semestre) queda por encima de la mediana de su cultivo? Es clasificación binaria (`RendimientoAlto`: Alto/Bajo) porque se busca ubicar el registro respecto a un referente de su cultivo, y no estimar un valor en t/ha.

- **Datos:** 39.934 registros (47,3 % «Alto»). Se excluyen 2.298 registros sin cosecha y 6.700 con área cosechada > sembrada.
- **Umbral:** mediana de cada cultivo calculada solo con 2019-2023, para que la prueba 2024 no influya en la etiqueta.
- **Predictoras:** `Cultivo`, `DesagregacionCultivo`, `Region`, `Departamento`, `Semestre`, `Log10_AreaSembrada`.
- **Fuera por fuga de información:** `Produccion`, `AreaCosechada` y `Rendimiento` (solo se conocen después de cosechar, y `Rendimiento` = `Produccion` / `AreaCosechada`).
- **Metadatos (no predicen):** `CodMunicipio`, `Municipio`, `Anio`, `GrupoCV`.
- **Modelos** (parámetros en `scripts/R6/params_flujo.py`):

| Widget | Parámetros |
|---|---|
| Logistic Regression | Ridge (L2), C = 1 (valores por defecto) |
| Tree | «Induce binary tree» **desactivado** (con él da error porque `Departamento` tiene 32 valores), profundidad máx. 12, mín. 20 en hojas, mín. 50 para dividir |
| Random Forest | 100 árboles, mín. 5 para dividir, sin límite de profundidad, semilla fija |

- **Evaluación** (mismas condiciones para los tres):
  - *Test and Score · CV*: validación cruzada estratificada de 10 pliegues. Para la **validación por municipio**, cambiar a *Cross validation by feature* y elegir `GrupoCV` (cada municipio queda completo en un solo pliegue).
  - *Test and Score · temporal*: entrenar con `eva_supervisado_entrenamiento_2019_2023.csv` y probar con `eva_supervisado_prueba_2024.csv` (*Test on test data*).
  - En ambos, **clase objetivo = Alto**.

### Valores de referencia (obtenidos con la librería de Orange; deben coincidir con la interfaz)

| Evaluación | Modelo | AUC | CA | F1 | Precisión | Recall |
|---|---|---|---|---|---|---|
| CV estratificada | Regresión logística | 0,738 | 0,668 | 0,615 | 0,682 | 0,560 |
| | Árbol | 0,788 | 0,711 | 0,687 | 0,703 | 0,672 |
| | Random Forest | 0,797 | 0,723 | 0,700 | 0,716 | 0,685 |
| CV por municipio | Regresión logística | 0,729 | 0,661 | 0,606 | 0,672 | 0,551 |
| | Árbol | 0,721 | 0,655 | 0,626 | 0,642 | 0,611 |
| | Random Forest | 0,691 | 0,632 | 0,607 | 0,614 | 0,600 |
| Entrenar 2019-2023 → 2024 | Regresión logística | 0,741 | 0,677 | 0,606 | 0,692 | 0,540 |
| | Árbol | 0,691 | 0,641 | 0,586 | 0,625 | 0,552 |
| | Random Forest | 0,805 | 0,729 | 0,697 | 0,720 | 0,676 |

> **Comprobado en la interfaz de Orange 3.40:** la validación por municipio coincide en todas las columnas y la estratificada en AUC y CA. F1, precisión y recall de la tabla son de la clase **Alto**: en *Test and Score* hay que poner *Evaluation results for target = Alto*; con «(None, show average over classes)» salen promedios de ambas clases (p. ej. F1 0,664 / 0,710 / 0,722).

**Lectura.** Con validación aleatoria gana el Random Forest, pero al dejar municipios completos fuera el orden se invierte y la regresión logística queda primera. Los modelos de árboles aprovechan que un mismo municipio y cultivo reaparecen cada año con áreas parecidas y rendimiento parecido, es decir, reconocen municipios ya vistos. Esa ventaja sirve para anticipar un municipio conocido el año siguiente (prueba 2024), no para generalizar a municipios nuevos. La elección del modelo depende de cuál de los dos usos se priorice.

## Flujo 2 · Clustering de municipios

**Pregunta:** ¿qué tipos de municipio agrícola existen según su tamaño, su mezcla de cultivos y qué parte de lo sembrado se cosecha?

- **Datos:** 1.098 municipios (una fila por municipio).
- **Variables del agrupamiento (10):** `Log10_AreaSembradaAnual`, `NumCultivos`, `Diversificacion` (1 − índice de Herfindahl), `PctArea_` de los 6 cultivos y `TasaCosecha`.
- **No entra ninguna variable de rendimiento.** `RendRelMediano_posteriori` va como metadato y sirve para describir los grupos después.
- **k-Means** (ya configurado en el flujo): *From 2 to 10*, *Normalize columns* (las variables tienen escalas muy distintas), inicialización KMeans++, 10 reinicios y 300 iteraciones como máximo. El widget muestra la silueta de cada k y la usamos para elegir.
- **Silueta por k** (calculada con el propio widget):

| k | 2 | 3 | 4 | **5** | 6 | 7 | 8 | 9 | 10 |
|---|---|---|---|---|---|---|---|---|---|
| silhouette | 0,253 | 0,214 | 0,242 | **0,272** | 0,265 | 0,253 | 0,250 | 0,233 | 0,215 |

  El máximo está en **k = 5**. La silueta es baja en todos los k (< 0,3), lo que indica grupos que se solapan: son tendencias, no segmentos nítidos. Comprueba que en el widget quede seleccionado k = 5 antes de conectar los demás.

- **Perfil de los 5 grupos** (media por grupo; el orden C1…C5 sale del widget y puede cambiar si cambia la versión):

| Grupo | Municipios | Cultivo dominante (% del área) | Área sembrada anual (ha, media geométrica) | Tasa de cosecha | Regiones principales | Rendimiento relativo* |
|---|---|---|---|---|---|---|
| C1 | 155 | Frijol 47 %, maíz 27 % | 280 | 0,84 | Andina 91 % | 0,92 |
| C2 | 150 | Papa 86 % | 560 | 0,86 | Andina 97 % | 1,07 |
| C3 | 392 | Maíz 44 %, yuca 27 %, plátano 16 % | 710 | 0,82 | Caribe 42 %, Andina 37 %, Pacífica 12 % | 0,98 |
| C4 | 113 | Arroz 70 % | 3.900 | 0,81 | Andina 42 %, Orinoquía 27 %, Caribe 25 % | 1,15 |
| C5 | 288 | Plátano 73 % | 660 | 0,92 | Andina 73 %, Pacífica 17 % | 0,94 |

  \* Mediana de `RendRelMediano_posteriori` (rendimiento dividido por la mediana de su cultivo). No entró al agrupamiento; se usa solo para describir los grupos.

- **Calidad de cada grupo** (*Silhouette Plot*, *Grouping = Cluster*). El *Silhouette Plot* no normaliza por su cuenta, y las seis variables `PctArea_*` (escala 0-100) dominarían la distancia y darían una silueta global de 0,42 que no es comparable con la del k-Means. Por eso entre k-Means y *Silhouette* va un widget **Preprocess** con *Normalize Features → Standardize to μ=0, σ²=1* (en Orange 3.40 no existe un widget «Normalize» aparte). Con esa normalización el widget reproduce la medida del k-Means:

| Grupo | C1 | C2 | C3 | C4 | C5 | Global |
|---|---|---|---|---|---|---|
| Silueta media | 0,194 | **0,458** | 0,144 | 0,312 | 0,375 | 0,272 |
| Municipios con silueta < 0 | 8 % | 0 % | **17 %** | 1 % | 0 % | |

  C2 (papa) es el grupo más compacto y C3 (mixto) el más difuso: casi 1 de cada 6 de sus municipios está más cerca de otro grupo que del suyo.

- **Relación grupo × región** (*Mosaic Display*, Cluster × Region, residuos de Pearson; χ² = 482, p < 0,001): C3 se asocia al Caribe (+11,2), C4 a la Orinoquía (+9,7) y C1 y C2 a la región Andina (+4,4 y +5,3). C3 está subrepresentado en la Andina (−6,5).

  Los grupos se separan sobre todo por el cultivo dominante, algo esperable porque la mezcla de cultivos entra como variable. Lo que aportan por encima de eso son la escala (C4, arroz, con un área anual de 5 a 14 veces la de los demás grupos), la tasa de cosecha (0,92 en C5 frente a 0,81–0,86 en el resto) y la localización regional.

## Flujo 3 · Comentarios de YouTube

**Propósito:** identificar qué factores asocian los comentaristas con producir y acceder a alimentos básicos en Colombia (costos de insumos, precios al productor, clima, intermediarios) y contrastarlos con el rendimiento y los grupos de municipios del EVA. Los criterios de búsqueda (consultas, número de videos, mínimo de comentarios, fecha desde) están en `scripts/R6/youtube_config.json`.

1. **Clave de la API.** En Google Cloud Console habilita *YouTube Data API v3*, crea una clave y escríbela en `.env` como `YOUTUBE_API_KEY=...` (el archivo está en `.gitignore`; `.env.example` solo lleva la variable vacía).
2. **Extraer:** `python scripts/R6/extraer_comentarios_youtube.py`. Genera en `orange/data/youtube/` los videos consultados con sus enlaces y la fecha de extracción (`videos.csv`), los comentarios crudos (`comentarios_crudos.csv`) y `log_extraccion.json` con la cuota gastada y las restricciones encontradas (videos con comentarios desactivados, no disponibles o con pocos comentarios; cuota agotada). Una búsqueda cuesta 100 unidades de las 10.000 diarias; leer 100 comentarios cuesta 1.
3. **Limpiar:** `python scripts/R6/preparar_comentarios.py`. Quita vacíos, irrelevantes (menos de 3 palabras) y duplicados, conserva solo español y enmascara URL, correos, @menciones y teléfonos. Deja `corpus.csv` y `log_limpieza.json` con el conteo de cada paso.
4. **Contar factores:** `python scripts/R6/factores_comentarios.py`. Cuenta cuántos comentarios mencionan cada factor (diccionario de términos visible en el script) y deja `factores_por_video.csv` y `factores_log.json`.
5. **Orange:** abre `orange/flujos/03_comentarios_youtube.ows`. Se genera con `python scripts/R6/generar_flujo_texto.py orange/flujos orange/data/youtube` (Python de Orange 3.40 con el complemento Text).

### Qué se extrajo (extracción del 2026-11-09)

Cinco consultas, cinco videos candidatos cada una: 25 videos. Solo 3 tenían al menos 30 comentarios; los otros 22 se descartaron (la mayoría con 0 comentarios devueltos por la API; detalle en `log_extraccion.json`). Cuota usada: 504 de 10.000 unidades.

| Video | Canal | Publicado | Comentarios (API) | Extraídos | Comentarios limpios |
|---|---|---|---|---|---|
| V01 · Campesinos en Boyacá enfrentan crisis por caída en el precio de la papa | Noticias Caracol | 2025-10-26 | 103 | 73 | 67 |
| V02 · Paro arrocero paraliza 9 departamentos | Noticias Caracol | 2025-07-18 | 70 | 50 | 47 |
| V03 · ¿Qué está pasando con el arroz en Colombia? | Economía para la pipol | 2025-03-13 | 160 | 89 | 81 |

Limpieza: 212 comentarios crudos → **195** (1 vacío, 9 con menos de 3 palabras, 0 duplicados, 7 en otro idioma). "Comentarios (API)" incluye respuestas; "Extraídos" son comentarios principales (la API entrega las respuestas aparte y aquí no se extrajeron).

**Límites del corpus (decirlo en el informe).** Son 3 videos: uno de papa y dos de arroz; las consultas sobre maíz e insumos no encontraron videos con comentarios suficientes. Dos de los tres son de un mismo noticiero, y los comentarios de V01 y V02 están muy marcados por la discusión política. Con 195 comentarios cortos (1.027 términos tras filtrar), los resultados describen estos comentarios y no a "los colombianos" ni a los productores.

### Flujo 03 · cómo se arma

`Archivo → Corpus → Preprocesar texto → {Nube de palabras, Colocaciones, Temas (LDA), Bolsa de palabras}`; de la bolsa de palabras salen tres `Select Rows` (video = V01 / V02 / V03) que alimentan tres `Word Enrichment`. `Corpus` también alimenta a `Corpus Viewer` para leer los comentarios.

| Widget | Parámetros |
|---|---|
| Archivo | `orange/data/youtube/corpus.csv` (ruta relativa al `.ows`) |
| Corpus | Texto: solo `texto`. Idioma: español. Título: `id` |
| Preprocesar texto | 1) Transformación: minúsculas y quitar URL. 2) Tokenización: expresión regular `\w+`. 3) Filtrado (antes de normalizar): lista `orange/data/youtube/stopwords_es.txt` (idioma "none"), quitar números, quitar tokens de 1-2 letras, mantener palabras en ≥ 2 comentarios. 4) Normalización: Snowball (español) |
| Bolsa de palabras | Conteo, sin ponderación global ni normalización |
| Temas | LDA, 4 temas (semilla fija: resultado repetible) |
| Colocaciones | Bigramas, frecuencia mínima 2 |
| Word Enrichment | Filtro FDR ≤ 0,2 |

**Por qué el filtrado va antes de normalizar.** El widget permite ordenar los pasos. Si el filtro de palabras vacías va después del *stemming*, las raíces ("com", "tod", "per") ya no coinciden con la lista y se cuelan. La lista `stopwords_es.txt` (755 palabras, con y sin tildes) une la de NLTK y la del paquete `stop-words`, sin palabras con contenido para este tema ("trabajo", "valor", "verdad") y con muletillas de comentarios ("q", "jaja", "pues"). Se incluye en el repo para no depender de descargas ni de rutas del equipo.

**Las palabras salen como raíces** (Snowball no devuelve la palabra completa). Para leerlas: `gobiern` = gobierno(s), `campesin` = campesino(s), `preci` = precio(s), `par` = paro, `pap` = papa, `arrocer` = arrocero(s), `pes` = pesos, `bult` = bulto, `cumpl` = cumplir, `ministr` = ministra/ministro, `intermediari` = intermediario(s), `arrob` = arroba, `graci` = gracias.

### Valores de referencia (obtenidos ejecutando el `.ows` guardado con Orange 3.40 + Text 1.16.3)

- **Preprocesamiento:** 1.027 tokens, 203 términos distintos, 13 comentarios sin ningún término tras filtrar (de 195). Más frecuentes: arroz 45, gobiern 41, campesin 35, preci 33, par 23, product 20, pap 18, compr 16, arrocer 16.
- **Temas (LDA, 4):** perplejidad 45,42; coherencia 0,372.

| Tema | Palabras principales (raíces) | Lectura |
|---|---|---|
| 1 | campesin, gobiern, preci, trabaj, pap, intermediari, camp, problem | Papa: campesino, precio e intermediarios |
| 2 | par, preci, arroz, arrocer, gobiern, colombian, vend, compr | Paro arrocero y precio |
| 3 | arroz, nacional, mil, preci, arrob, par, pes, colombi | Precio del arroz (arroba, pesos) |
| 4 | gobiern, tlc, cos, produccion, graci, señor, product, dios | Mezcla: TLC y gobierno junto a agradecimientos y religión |

  **Cómo leerlo:** la coherencia es baja (con 2 a 8 temas, entre 0,31 y 0,40, sin un máximo claro) y el tema 4 mezcla cosas distintas. Con 195 comentarios cortos LDA no separa temas con nitidez; se usa como apoyo para explorar y no como resultado principal. Se eligió k = 4 porque los temas 1 a 3 coinciden con lo que se ve en los videos y k mayor solo parte esos temas.
- **Palabras que distinguen a cada video** (Word Enrichment, hipergeométrica, FDR ≤ 0,2):
  - V01 (papa): campesin, pap, intermediari, bult, pes, trabaj, mil, cobr, gan (9 palabras).
  - V02 (paro arrocero): par, cumpl, gobiern, puebl, ministr (5).
  - V03 (arroz e importaciones): solo `arroz` pasa el FDR ≤ 0,2. Con p < 0,02 y sin corrección aparecen tlc, barat, arancel, competit y colombian, pero con FDR ≈ 0,33: son una tendencia, no un hallazgo firme.
- **Colocaciones (76 pares con frecuencia ≥ 2; puntaje PMI):** cas nariñ, ofert demand, dej engañ, veng bogot, libr comerci, trat libr, vend direct, vias vias, gobi anterior, mil pes.
  **Cómo leerlas:** el PMI premia pares raros, y aquí casi todos aparecen 2 o 3 veces (`cas nariñ` es un solo comentario citado dos veces). Por frecuencia bruta, lo más repetido son pares de 4 apariciones: mil pes, pobr campesin, par arrocer, arroz colombian, arrob arroz; con 3: trabaj camp, gobiern cambi, apoy campesin, vend car, pap preci, trat libr, libr comerci. Sirven para ilustrar de qué se habla (precio en pesos, "pobre campesino", tratados de libre comercio), no como evidencia estadística. Para ver este orden en Orange, cambia el método de puntuación a *Raw Frequency*.

### Factores mencionados (`factores_por_video.csv`; % de comentarios de cada video)

| Factor | Total | V01 papa | V02 paro | V03 arroz |
|---|---|---|---|---|
| Gobierno y política | 27,2 % | 31,3 | 48,9 | 11,1 |
| Precio al productor vs. al consumidor | 20,0 % | 25,4 | 8,5 | 22,2 |
| Importaciones y tratados comerciales | 14,4 % | 7,5 | 6,4 | 24,7 |
| Subsidios, crédito y apoyo estatal | 10,8 % | 13,4 | 10,6 | 8,6 |
| Intermediarios y acaparadores | 8,2 % | 17,9 | 4,3 | 2,5 |
| Productividad, calidad y tecnología | 8,2 % | 1,5 | 0,0 | 18,5 |
| Costo de insumos y logística | 5,6 % | 9,0 | 4,3 | 3,7 |
| Sobreproducción, oferta y demanda | 3,6 % | 7,5 | 2,1 | 1,2 |
| Clima y plagas | 2,1 % | 3,0 | 0,0 | 2,5 |
| Venta directa y mercados campesinos | 1,0 % | 1,5 | 0,0 | 1,2 |

Es conteo de expresiones, no de opinión: un comentario puede sumar a varios factores y no se detecta ironía ni negación. Los porcentajes de un video con 47 comentarios se mueven mucho con 2 o 3 comentarios más.

### Lectura preliminar frente al EVA (se afina en las conclusiones)

- Los comentarios hablan de **precios, intermediarios, gobierno e importaciones**; el EVA solo mide **qué se siembra y cuánto rinde**. Son dos partes distintas de la cadena: el rendimiento alto no garantiza ingreso si el precio cae o si el intermediario se queda con el margen, que es lo que más aparece en el video de la papa.
- El factor **productividad y tecnología** casi solo aparece en el video de arroz (18,5 %), donde se discute competir con el arroz importado. En el EVA, los municipios arroceros (clúster 4) no salen con rendimiento bajo: su rendimiento relativo a la mediana del cultivo es 1,15. Es coherente con que el reclamo sea de precio y competencia, no de cuánto rinde la tierra; el EVA no tiene precios ni costos, así que no puede confirmarlo.
- **Clima, plagas e insumos** aparecen poco (2 % y 6 %): con este corpus no hay base para decir que el clima explica el rendimiento bajo, que es el tema donde el EVA no tiene variables.

**Privacidad.** No se guarda nombre, canal, foto ni identificador del autor de ningún comentario. `comentarios_crudos.csv` está excluido de Git (`orange/data/youtube/.gitignore`); el corpus limpio contiene texto de terceros, así que conviene decidir antes de publicarlo. Las opiniones corresponden a quienes comentaron en esos videos y no representan a toda la población.

**Dónde está cada cosa:** `scripts/R6/extraer_comentarios_youtube.py`, `preparar_comentarios.py`, `factores_comentarios.py`, `generar_flujo_texto.py`, `youtube_config.json`; datos en `orange/data/youtube/` (`videos.csv`, `corpus.csv`, `stopwords_es.txt`, `factores_por_video.csv` y los logs).
