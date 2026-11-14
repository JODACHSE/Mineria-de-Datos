# 🍊 R6 · Conocimiento oculto con Orange

Aquí están los tres análisis de la etapa 6, hechos en **Orange Data Mining 3.40**:

| # | Flujo | Pregunta que responde |
|:---:|---|---|
| 1 | [`01_supervisado.ows`](flujos/01_supervisado.ows) | ¿El rendimiento de un municipio quedará **por encima o por debajo** de lo normal para su cultivo? |
| 2 | [`02_clustering.ows`](flujos/02_clustering.ows) | ¿Qué **tipos de municipio agrícola** hay según su tamaño, sus cultivos y lo que cosechan? |
| 3 | [`03_comentarios_youtube.ows`](flujos/03_comentarios_youtube.ows) | ¿Qué factores asocia la gente con producir y conseguir alimentos básicos? |

Los resultados se publican en la sección **Conocimiento oculto** del sitio (`/r6`).

```
orange/
├── flujos/      los 3 archivos .ows
└── data/        CSV que leen los flujos (+ log_preparacion.json)
    └── youtube/ videos, corpus limpio, lista de palabras vacías, factores y registros
scripts/R6/      programas que preparan los datos y generan los flujos
```

---

## ▶️ Cómo reproducirlo

1. **Preparar los datos** (desde la raíz del repositorio):
   ```bash
   python scripts/R6/preparar_datos_orange.py
   ```
   Crea los CSV de `orange/data/` a partir del EVA ya limpio de R2. Cada filtro queda anotado, con su conteo y su motivo, en `log_preparacion.json`.
2. **Abrir el flujo** en Orange: *File → Open* y elige un `.ows` de `orange/flujos/`. Las rutas son relativas, así que funciona sin importar dónde clonaste el repositorio.
3. **Comprobar** que *Datos* muestra **39.934 filas** (supervisado) o **1.098** (clustering).
4. **Llevar los resultados al sitio** (opcional), con el Python que trae Orange:
   ```bash
   "%LOCALAPPDATA%/Programs/Orange/python.exe" scripts/R6/resultados_orange.py
   ```
   Recalcula métricas, matrices y grupos y los guarda en `app/static/data/R6/resultados.json`.

> Usa Orange **3.40 o posterior**. Un `.ows` guardado con una versión más nueva puede no abrir bien en una anterior.

---

## 1️⃣ Flujo supervisado

**Idea:** comparar cada registro (municipio × cultivo × semestre) con la **mediana de su cultivo**. Si la supera es «Alto»; si no, «Bajo». Así un cultivo de 17 t/ha (papa) y uno de 1,3 t/ha (fríjol) se miden con la misma regla.

| | |
|---|---|
| **Registros** | 39.934 (47,3 % «Alto»). Se quitaron 2.298 sin cosecha y 6.700 con área cosechada mayor que la sembrada. |
| **Umbral** | Mediana de cada cultivo con datos de 2019–2023, para que el año de prueba (2024) no influya. |
| **Variables que usa** | Cultivo, DesagregacionCultivo, Region, Departamento, Semestre, Log10_AreaSembrada. |
| **Variables que no usa** | Producción, área cosechada y rendimiento: solo se conocen **después** de cosechar (sería hacer trampa). |

**Modelos** (parámetros en [`scripts/R6/params_flujo.py`](../scripts/R6/params_flujo.py)):

| Modelo | Configuración |
|---|---|
| Regresión logística | Ridge (L2), C = 1 |
| Árbol de decisión | Sin árbol binario (Departamento tiene 32 valores), profundidad máx. 12, mín. 20 por hoja, mín. 50 para dividir |
| Random Forest | 100 árboles, mín. 5 para dividir, semilla fija |

**Cómo se evaluaron** (los tres por igual, clase objetivo = **Alto**):
- **Validación cruzada estratificada** de 10 pliegues.
- **Validación por municipio:** en *Test and Score* elige *Cross validation by feature → GrupoCV*. Así el modelo se prueba con municipios que nunca vio.
- **Prueba temporal:** entrenar con 2019–2023 y probar con 2024 (*Test on test data*).

### Resultados esperados

| Evaluación | Modelo | AUC | Exactitud | F1 | Precisión | Recall |
|---|---|---|---|---|---|---|
| CV estratificada | Regresión logística | 0,738 | 0,668 | 0,615 | 0,682 | 0,560 |
| | Árbol | 0,788 | 0,711 | 0,687 | 0,703 | 0,672 |
| | Random Forest | 0,797 | 0,723 | 0,700 | 0,716 | 0,685 |
| CV por municipio | Regresión logística | 0,729 | 0,661 | 0,606 | 0,672 | 0,551 |
| | Árbol | 0,721 | 0,655 | 0,626 | 0,642 | 0,611 |
| | Random Forest | 0,691 | 0,632 | 0,607 | 0,614 | 0,600 |
| 2019–2023 → 2024 | Regresión logística | 0,741 | 0,677 | 0,606 | 0,692 | 0,540 |
| | Árbol | 0,691 | 0,641 | 0,586 | 0,625 | 0,552 |
| | **Random Forest** | **0,805** | **0,729** | **0,697** | **0,720** | **0,676** |

> 💡 En *Test and Score* pon *Evaluation results for target = **Alto***. Con la opción de promedio salen otras cifras (F1 ≈ 0,66 / 0,71 / 0,72).

**En palabras simples:** el Random Forest acierta mejor el año siguiente en municipios que ya conoce (AUC 0,805), porque el rendimiento de un municipio se repite año a año. Con municipios nuevos pierde esa ventaja y la regresión logística queda primera.

---

## 2️⃣ Flujo de clustering

**Idea:** agrupar los **1.098 municipios** por cómo producen, sin mirar su rendimiento.

- **Variables (10):** tamaño (`Log10_AreaSembradaAnual`), número de cultivos, diversificación (1 − Herfindahl), % de área de cada uno de los 6 cultivos y tasa de cosecha.
- **El rendimiento no entra:** `RendRelMediano_posteriori` es solo un metadato para **describir** los grupos después.
- **k-Means:** k de 2 a 10, *Normalize columns*, KMeans++, 10 reinicios y 300 iteraciones como máximo.

**¿Cuántos grupos?** El que tenga mayor silueta:

| k | 2 | 3 | 4 | **5** | 6 | 7 | 8 | 9 | 10 |
|---|---|---|---|---|---|---|---|---|---|
| Silueta | 0,253 | 0,214 | 0,242 | **0,272** | 0,265 | 0,253 | 0,250 | 0,233 | 0,215 |

Se elige **k = 5**. Como la silueta es baja (< 0,3), los grupos se mezclan un poco: léelos como **tendencias**, no como cajas cerradas.

### Los 5 grupos

Orange los numera C1…C5 (ese orden puede cambiar entre versiones). En el informe y en el sitio se llaman G1…G5:

| Orange | Informe | Municipios | Cultivo dominante | Área anual (ha)* | Tasa de cosecha | Rend. relativo** | Silueta |
|:---:|---|---:|---|---:|---:|---:|---:|
| C4 | **G1** · Arroceros de gran escala | 113 | Arroz 70 % | 3.900 | 0,81 | 1,15 | 0,312 |
| C1 | **G2** · Andinos pequeños | 155 | Fríjol 47 %, maíz 27 % | 280 | 0,84 | 0,92 | 0,194 |
| C3 | **G3** · Mixtos campesinos | 392 | Maíz 44 %, yuca 27 % | 710 | 0,82 | 0,98 | 0,144 |
| C2 | **G4** · Paperos del altiplano | 150 | Papa 86 % | 560 | 0,86 | 1,07 | **0,458** |
| C5 | **G5** · Plataneros | 288 | Plátano 73 % | 660 | 0,92 | 0,94 | 0,375 |

<sub>\* Media geométrica. \*\* Rendimiento dividido por la mediana de su cultivo (1 = típico); no se usó para agrupar.</sub>

- **G4 (papa)** es el grupo más compacto; **G3 (mixto)** el más difuso: 17 % de sus municipios encajaría mejor en otro grupo.
- **Grupo × región** (*Mosaic Display*, χ² = 482, p < 0,001): G3 se asocia al Caribe, G1 a la Orinoquía, y G2 y G4 a la región Andina.

> 🔧 *Silhouette Plot* no normaliza por su cuenta. Por eso, entre k-Means y Silhouette, hay un **Preprocess** con *Standardize (μ=0, σ²=1)*. Sin él, los porcentajes de área dominarían y la silueta no sería comparable.

---

## 3️⃣ Flujo de comentarios de YouTube

### Pasos

1. **Clave de la API.** En Google Cloud Console activa *YouTube Data API v3*, crea una clave y guárdala en `.env` como `YOUTUBE_API_KEY=...` (ese archivo no se sube a GitHub).
2. **Extraer:** `python scripts/R6/extraer_comentarios_youtube.py`. Los criterios de búsqueda están en [`youtube_config.json`](../scripts/R6/youtube_config.json).
3. **Limpiar:** `python scripts/R6/preparar_comentarios.py`. Quita vacíos, mensajes muy cortos, duplicados y otros idiomas, y oculta URL, correos, @menciones y teléfonos.
4. **Contar factores:** `python scripts/R6/factores_comentarios.py`.
5. **Abrir** `03_comentarios_youtube.ows` en Orange (necesita el complemento **Text**).

### Qué se encontró (extracción del 9 de noviembre de 2026)

De 25 videos candidatos, solo **3** tenían al menos 30 comentarios:

| Video | Canal | Comentarios limpios |
|---|---|---:|
| [V01 · Crisis por el precio de la papa en Boyacá](https://youtube.com/watch?v=3Qw6pcizxCs) | Noticias Caracol | 67 |
| [V02 · Paro arrocero paraliza 9 departamentos](https://youtube.com/watch?v=SDR0xsgBQrg) | Noticias Caracol | 47 |
| [V03 · ¿Qué está pasando con el arroz en Colombia?](https://youtube.com/watch?v=jd2Oth7H6Ss) | Economía para la pipol | 81 |

**212 comentarios → 195** tras la limpieza. Cuota usada: 504 de 10.000 unidades.

**Factores más mencionados** (% de comentarios):

| Factor | Total | V01 papa | V02 paro | V03 arroz |
|---|---:|---:|---:|---:|
| Gobierno y política | 27,2 % | 31,3 | 48,9 | 11,1 |
| Precio al productor vs. al consumidor | 20,0 % | 25,4 | 8,5 | 22,2 |
| Importaciones y tratados | 14,4 % | 7,5 | 6,4 | 24,7 |
| Subsidios y crédito | 10,8 % | 13,4 | 10,6 | 8,6 |
| Intermediarios | 8,2 % | 17,9 | 4,3 | 2,5 |
| Productividad y tecnología | 8,2 % | 1,5 | 0,0 | 18,5 |
| Insumos y logística | 5,6 % | 9,0 | 4,3 | 3,7 |
| Sobreproducción | 3,6 % | 7,5 | 2,1 | 1,2 |
| Clima y plagas | 2,1 % | 3,0 | 0,0 | 2,5 |
| Venta directa | 1,0 % | 1,5 | 0,0 | 1,2 |

**En palabras simples:** la gente habla de **precios, intermediarios, gobierno e importaciones**, casi nada de clima. El EVA, en cambio, solo mide cuánto se siembra y cuánto rinde. Por ejemplo, los municipios arroceros rinden por encima de lo normal (1,15), así que el reclamo del video del arroz es de **precio**, no de productividad.

<details>
<summary>Configuración del flujo de texto y valores de referencia</summary>

**Recorrido:** Archivo → Corpus → Preprocesar texto → { Nube de palabras, Colocaciones, Temas (LDA), Bolsa de palabras → 3 × Select Rows → Word Enrichment }.

| Widget | Configuración |
|---|---|
| Corpus | Texto: `texto` · Idioma: español |
| Preprocesar texto | Minúsculas y sin URL → tokens `\w+` → filtro (lista `stopwords_es.txt`, sin números ni tokens de 1–2 letras, palabras en ≥ 2 comentarios) → Snowball español |
| Temas | LDA, 4 temas, semilla fija |
| Colocaciones | Bigramas, frecuencia ≥ 2 |
| Word Enrichment | FDR ≤ 0,2 |

- **¿Por qué filtrar antes de normalizar?** Si se recortan primero las palabras a su raíz («com», «tod»), ya no coinciden con la lista de palabras vacías y se cuelan.
- **Las palabras salen como raíces:** `gobiern` = gobierno, `campesin` = campesino, `preci` = precio, `par` = paro, `pap` = papa.
- **Resultados de referencia:** 1.027 tokens y 203 términos. Los más frecuentes: arroz 45, gobiern 41, campesin 35, preci 33.
- **LDA:** coherencia 0,372, baja. Sirve para explorar, no como resultado principal.
- **Palabras que distinguen cada video:** V01 → campesin, pap, intermediari, bult; V02 → par, cumpl, gobiern; V03 → solo «arroz» pasa el filtro FDR.

</details>

### ⚠️ Límites y privacidad

- Son **195 comentarios de 3 videos** (dos del mismo noticiero) y con carga política: describen esos comentarios, **no** a los productores ni a la población.
- El conteo de factores no detecta ironía ni negaciones.
- No se guarda el nombre, el canal ni el identificador de quien comentó. Los comentarios crudos (`comentarios_crudos.csv`) **no** se suben a GitHub.
