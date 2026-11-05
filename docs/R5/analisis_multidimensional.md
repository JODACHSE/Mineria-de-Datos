# R5 · Análisis multidimensional: preguntas, operaciones y conocimientos

> Archivo generado por `python scripts/R5/export_docs.py` a partir del modelo estrella; no se edita a mano.
> Diagrama, diccionario y carga del modelo: [`modelo_estrella.md`](modelo_estrella.md).

## 1. Datos utilizados

- **Fuente:** EVA, Evaluaciones Agropecuarias Municipales (MinAgricultura/UPRA, datos.gov.co), tratado en R2/R3 (`app/static/data/R2/eva_basicos.json`).
- **Cobertura:** 2019–2024 · 1.098 municipios de 32 departamentos · 6 cultivos básicos.
- **Registros utilizados:** 48.932 (todos los del EVA tratado; no se filtra ninguno).
- **Limitaciones de calidad:** 6.700 hechos (13,7 %) con área cosechada mayor que la sembrada (se conservan con bandera y se pueden excluir); 2.298 hechos con área cosechada 0 (respuesta negativa, no faltante); cambio de desagregación del maíz en 2021; el plátano solo tiene periodo anual.
- **Unidad de análisis:** la producción de un cultivo básico en un municipio.
- **Granularidad de la tabla de hechos:** 1 municipio × 1 desagregación de cultivo × 1 periodo agrícola.

## 2. Relación con el conocimiento evidente (R4)

| Conocimiento evidente (R4) | ¿Profundizar? | Por qué | Cómo lo aborda R5 | Análisis |
|---|---|---|---|---|
| Poblacional · **Maíz domina la población evaluada** — Maíz = 37,8 % de los registros (18.490 de 48.932). | Sí | Un registro es una fila municipio × desagregación × periodo, no un volumen: R4 no podía saber si ese dominio se traduce en producción ni con qué sistema productivo se logra. | Cultivo × Tiempo con registros vs. producción (C3) y Cultivo × Sistema × Región con rendimiento (C5). | 2. Evolución de la producción, 3. Brecha entre sistemas productivos |
| Poblacional · **La canasta es casi toda de ciclo transitorio** — Transitorio = 90,1 %; permanente = 9,9 % (solo plátano). | No | Es una propiedad estructural de la canasta que no cambia al cruzar dimensiones. | Se incorpora al diseño: el ciclo es atributo de dim_cultivo y explica que el plátano solo tenga periodo anual en dim_tiempo (queda como miembro «Anual» y no se suma a los semestres A o B). | Diseño del modelo |
| Poblacional · **El arroz es el cultivo menos evaluado** — Arroz = 8,5 % de los registros (4.138). | Sí | Pocos registros pueden esconder un gran volumen concentrado en pocas unidades de gran escala. | Territorio × Cultivo con producción (C1), Región × Sistema con área y rendimiento (C6) y Año × Departamento con tasa de cosecha (C8). | 1. Concentración de la producción, 3. Brecha entre sistemas productivos, 4. Área sembrada no cosechada |
| Territorial · **La mitad de las evaluaciones se concentra en 5 departamentos** — Top-5 departamentos = 41,5 % de los registros. | Sí | La concentración de registros no tiene por qué coincidir con la de producción, y R4 no bajó de departamento a municipio. | Drill-down Región → Departamento → Municipio sobre la producción de cada cultivo (C2). | 1. Concentración de la producción |
| Territorial · **La región Andina domina el registro** — Andina = 59,3 % de los registros; Amazonía = 3,1 %. | Sí | Es un peso en número de filas; falta comparar ese peso con el volumen que produce cada región. | Comparación % de registros vs. % de producción por región y slice por cultivo (C1). | 1. Concentración de la producción |
| Territorial · **Amplia cobertura municipal, con casos extremos** — 1.098 municipios en 32 departamentos; San Andrés con 42 registros. | No | Es un dato de cobertura del conjunto, no un comportamiento que dependa de otra dimensión. | Se conserva como medida Municipios únicos (COUNT DISTINCT) y se usa como contraste en el análisis temporal (¿crecen los registros porque se evalúan más municipios?). | Diseño del modelo |
| Temporal · **El volumen de evaluaciones creció 28,5 %** — De 6.889 registros en 2019 a 8.855 en 2024. | Sí | R4 midió el crecimiento de filas; no sabía si creció la producción ni si se sumaron municipios. | Registros, municipios únicos y producción en trienios equivalentes y por año (C3). | 2. Evolución de la producción |
| Temporal · **El salto ocurrió en 2021; luego se estabilizó** — 2021 = +19,5 % de registros. | Sí | Un salto de registros puede deberse a un cambio de medición o a un choque real; un conteo no distingue entre ambos. | Año × Desagregación del maíz (cambio de 2 a 4 desagregaciones, C3) y Año × Departamento con tasa de cosecha del arroz (C8). | 2. Evolución de la producción, 4. Área sembrada no cosechada |
| Temporal · **Estacionalidad a favor del primer semestre** — Semestre A = 47,0 % vs. semestre B = 43,2 % de los registros. | Sí | Es un agregado de todos los cultivos y años; puede ocultar cultivos que se mueven en sentido contrario. | Drill-down Año → Periodo por cultivo con producción (C4). | 2. Evolución de la producción |
| Relacional · **Solo 52 de 90 ternas están pobladas** — 52 de 90 combinaciones cultivo × región × semestre activas (57,8 %). | Sí | R4 dice qué combinaciones existen, no cuánta área sembrada se pierde en cada una. | Territorio × Tiempo × Cultivo con tasa de cosecha y área no cosechada (C7, C8). | 4. Área sembrada no cosechada |
| Relacional · **La terna líder es Maíz × Andina × Primer semestre** — 5.469 registros (11,2 %). | Sí | El liderazgo es en número de registros; R4 no podía verificar si ese cruce también lidera en volumen ni con qué tecnología se produce. | Slice Cultivo = Maíz con matriz Región × Sistema y rendimiento ponderado (C5). | 3. Brecha entre sistemas productivos |
| Relacional · **El maíz es el cultivo más transversal** — Presente en las 5 regiones; 29 de 30 pares cultivo × región activos. | Sí | Estar presente en todas partes no dice cuánto se produce ni con qué rendimiento. | Cultivo × Sistema × Región: la presencia se explica sobre todo por el maíz tradicional (C5). | 3. Brecha entre sistemas productivos |

## 3. Preguntas de análisis

### Análisis 1 · Concentración territorial de la producción  (`/r5/territorial`)

**Pregunta.** ¿En qué regiones, departamentos y municipios se concentra la producción (t) de cada cultivo básico, y cómo cambia esa concentración al bajar de región a departamento y a municipio?

**Cómo profundiza R4.** R4 midió la concentración territorial con el conteo de registros (Andina = 59,3 % de los registros; top-5 departamentos = 41,5 %). Aquí la medida pasa a ser la producción en toneladas y se cruza con el cultivo: un territorio con pocos registros puede concentrar mucho volumen, y la concentración se recalcula en cada nivel de la jerarquía territorial.

- **Dimensiones:** Territorio, Cultivo, Tiempo (filtro)
- **Medidas:** Producción (t, `SUM`); Registros (registros, `COUNT`); Municipios únicos (municipios, `COUNT DISTINCT`); Área cosechada (ha, `SUM`)
- **Jerarquías:** Territorio: Región → Departamento → Municipio; Cultivo: Grupo → Cultivo → Desagregación

**Interpretación.**

- Al pasar de registros a toneladas, el mapa productivo cambia: la Andina sigue primera, pero la Orinoquía pasa del cuarto lugar en registros al segundo en producción, impulsada por arroz y plátano.
- Cada drill-down recalcula la participación sobre la producción de la selección: la concentración aumenta al bajar de nivel (pocas regiones → pocos departamentos → muy pocos municipios), sobre todo en papa y arroz.
- El pivot Cultivo × Región responde a otra pregunta: no qué produce cada región, sino de qué territorios depende cada cultivo.

**Limitación.** La producción en toneladas mezcla productos con contenido nutricional y precio muy distintos (una tonelada de papa no equivale a una de frijol); la concentración mide volumen físico, no aporte calórico ni valor económico.

**Decisión sustentada en los datos.** Focalizar el monitoreo de abastecimiento en los municipios que reúnen el 50 % de la producción de cada cultivo (indicador 3 de este análisis) en vez de distribuir el seguimiento por número de municipios.

### Análisis 2 · Evolución de la producción frente a la evolución de los registros  (`/r5/temporal`)

**Pregunta.** ¿Cómo cambian la producción (t) y el rendimiento (t/ha) de cada cultivo entre periodos equivalentes (trienios 2019–2021 y 2022–2024, años y semestres), y coincide ese cambio con el crecimiento de registros que mostró R4?

**Cómo profundiza R4.** R4 reportó +28,5 % de registros entre 2019 y 2024 y un salto de +19,5 % en 2021. Este análisis separa el número de registros de la producción, compara trienios de igual duración y baja de año a semestre para ver cambios que el total anual oculta.

- **Dimensiones:** Tiempo, Cultivo, Territorio (filtro), Sistema productivo (columnas opcionales)
- **Medidas:** Producción (t, `SUM`); Rendimiento ponderado (t/ha, `SUM(producción) / SUM(área cosechada)`); Registros (registros, `COUNT`); Municipios únicos (municipios, `COUNT DISTINCT`)
- **Jerarquías:** Tiempo: Trienio → Año → Periodo; Cultivo: Grupo → Cultivo → Desagregación

**Interpretación.**

- Entre trienios equivalentes los registros crecen mucho más que la producción: el crecimiento de R4 refleja sobre todo una mayor desagregación del reporte, no una mayor oferta.
- Plátano y yuca crecen en producción; maíz y frijol caen de forma sostenida. Papa y arroz se mantienen estables en el total anual.
- El drill-down a periodo muestra cambios de estacionalidad (arroz) que desaparecen en el roll-up a año.

**Limitación.** Seis años (2019–2024) permiten comparar dos trienios pero no separar tendencia de ciclo climático; el plátano solo tiene periodo anual y no entra en comparaciones A vs. B.

**Decisión sustentada en los datos.** Usar toneladas y municipios únicos, y no número de registros, como indicadores de seguimiento temporal; revisar por semestre los calendarios de compra y almacenamiento de arroz.

### Análisis 3 · Brecha de rendimiento entre sistemas productivos  (`/r5/sistemas`)

**Pregunta.** ¿Qué diferencia de rendimiento (t/ha) hay entre los sistemas tecnificado y tradicional de maíz y arroz en cada región, y qué parte del área cosechada depende del sistema de menor rendimiento?

**Cómo profundiza R4.** R4 encontró que el maíz domina la población evaluada (37,8 % de los registros) y que el arroz es el menos evaluado, pero no explicó por qué. Cruzar sistema productivo, cultivo y territorio muestra que ese predominio corresponde sobre todo a maíz tradicional de bajo rendimiento.

- **Dimensiones:** Sistema productivo, Cultivo, Territorio, Tiempo (filtro)
- **Medidas:** Rendimiento ponderado (t/ha, `SUM(producción) / SUM(área cosechada)`); Área cosechada (ha, `SUM`); Producción (t, `SUM`); Registros (registros, `COUNT`)
- **Jerarquías:** Sistema productivo: Criterio → Sistema productivo; Territorio: Región → Departamento → Municipio

**Interpretación.**

- En maíz y arroz el sistema tecnificado rinde entre 2 y 3 veces más que el tradicional en todas las regiones; la brecha se mantiene al cambiar de territorio, así que no es un efecto de una sola región.
- El área tradicional se concentra en el Caribe (maíz) y en la Amazonía; la Orinoquía es casi totalmente tecnificada.
- Para yuca y plátano la dimensión distingue destino (industrial, exportación, consumo interno), no tecnología.

**Limitación.** EVA solo diferencia el nivel tecnológico en maíz y arroz; para papa y frijol el sistema es «Sin diferenciar», por lo que la brecha no puede medirse en esos cultivos.

**Decisión sustentada en los datos.** Priorizar programas de tecnificación y asistencia técnica en el maíz tradicional del Caribe, donde coinciden la mayor área tradicional y el menor rendimiento.

### Análisis 4 · Área sembrada que no llega a cosecharse  (`/r5/cosecha`)

**Pregunta.** ¿Qué combinaciones de territorio, año y cultivo presentan la menor tasa de cosecha (área cosechada / área sembrada) y dónde se acumula el área no cosechada?

**Cómo profundiza R4.** R4 se limitó a la presencia de registros (cultivo × región × semestre) y no usó las áreas. Aquí se miden las pérdidas de área por territorio y año, y se distingue un problema persistente de un evento puntual.

- **Dimensiones:** Territorio, Tiempo, Cultivo, Calidad (atributo degenerado)
- **Medidas:** Tasa de cosecha (%, `SUM(cosechada) / SUM(sembrada) × 100`); Área no cosechada (ha, `SUM(sembrada) − SUM(cosechada)`); Área sembrada (ha, `SUM`)
- **Jerarquías:** Territorio: Región → Departamento → Municipio; Tiempo: Trienio → Año → Periodo

**Interpretación.**

- La tasa nacional de cosecha es alta (≈ 94 %), pero el área no cosechada se concentra en el Caribe y en maíz, con picos puntuales por año (arroz 2021, maíz 2024).
- El drill-down de región a departamento revela que los promedios regionales ocultan caídas fuertes en departamentos concretos (Sucre, Bolívar, Córdoba).
- El filtro de calidad cambia el orden entre regiones: las conclusiones se presentan con ambos criterios.

**Limitación.** El 13,7 % de las filas tiene área cosechada mayor que la sembrada (desfase entre semestres de siembra y cosecha). Excluirlas sesga la tasa hacia abajo y conservarlas la sesga hacia arriba; la tasa debe leerse como indicador relativo, no como pérdida exacta.

**Decisión sustentada en los datos.** Activar seguros agropecuarios y alertas de riesgo climático por departamento y año para arroz y maíz del Caribe, en vez de medidas nacionales uniformes.

## 4. Operaciones multidimensionales (ejemplos aplicados)

### Drill-down · Papa: de región a departamento y de departamento a municipio

- **Análisis:** 1. Concentración de la producción · enlace directo: `/r5/territorial?ej=drill-papa`
- **Dimensiones:** Territorio (región → departamento → municipio), Cultivo (slice = Papa).
- **Medidas:** Producción (t, SUM) y participación sobre la producción de la selección.
- **Nivel y filtros:** Región → Departamento (Andina) → Municipio (Boyacá).
- **Procedimiento:** Se parte del nivel Región con el filtro Cultivo = Papa (SUM(producción) agrupado por región). Clic en «Andina» agrega el filtro región = Andina y agrupa por departamento; clic en «Boyacá» agrega departamento = Boyacá y agrupa por municipio. Cada paso es una consulta nueva que recalcula SUM(producción) y el % sobre el total de la selección (no sobre el nivel anterior).
- **Interpretación:** La participación de Boyacá dentro de la papa andina, y la de un municipio dentro de Boyacá, crece en cada paso del drill-down: la producción no se reparte de forma uniforme dentro de la región, sino que se concentra en pocos municipios del altiplano (cifras exactas en el conocimiento C2 de este análisis).

### Pivot · Cultivo × región en lugar de región × cultivo

- **Análisis:** 1. Concentración de la producción · enlace directo: `/r5/territorial?ej=pivot-region-cultivo`
- **Dimensiones:** Cultivo y Territorio (región).
- **Medidas:** Producción (t); porcentajes de fila (denominador = total del cultivo).
- **Nivel y filtros:** Cultivo × Región, sin filtros.
- **Procedimiento:** Se intercambian los ejes de la matriz base Región × Cultivo: ahora las filas son Cultivo y las columnas Región, sin ningún filtro activo. El GROUP BY pasa de (región, cultivo) a (cultivo, región); el total general y cada celda individual no cambian de valor, solo su posición en la matriz.
- **Interpretación:** El pivot no agrega información nueva, pero cambia la pregunta: en vez de «¿qué produce cada región?» se lee «¿de qué territorios depende cada cultivo?». La fila de un cultivo muestra de inmediato qué porcentaje de su producción nacional viene de cada región, algo que en la matriz original había que leer columna por columna.

### Roll-up · Arroz: de periodo semestral a año y a trienio

- **Análisis:** 2. Evolución de la producción · enlace directo: `/r5/temporal?ej=rollup-arroz`
- **Dimensiones:** Tiempo (trienio → año → periodo), Cultivo (slice = Arroz).
- **Medidas:** Producción (t, SUM).
- **Nivel y filtros:** Se parte del nivel Periodo y se pulsa Roll-up hasta Año y Trienio.
- **Procedimiento:** Se parte del nivel Periodo (semestre) con el filtro Cultivo = Arroz y se pulsa Roll-up dos veces: primero se agrupa por Año (se pierde el detalle semestral) y luego por Trienio (se pierde el detalle anual). Cada roll-up es una consulta nueva SUM(producción) agrupada por el nivel padre de la jerarquía temporal, no un reagrupamiento visual de los datos ya traídos.
- **Interpretación:** Al subir de periodo a año, los semestres A y B se suman en un solo total y el desplazamiento de la cosecha de arroz hacia el segundo semestre (conocimiento C4) deja de verse; al subir de año a trienio solo queda visible la tendencia de seis años. El roll-up resume el comportamiento pero oculta el detalle estacional que el drill-down sí revela.

### Slice · Corte del cubo en Cultivo = Maíz

- **Análisis:** 3. Brecha entre sistemas productivos · enlace directo: `/r5/sistemas?ej=slice-maiz`
- **Dimensiones:** Cultivo (slice), Territorio (región) × Sistema productivo.
- **Medidas:** Rendimiento ponderado (t/ha) = SUM(producción) / SUM(área cosechada).
- **Nivel y filtros:** Región × Sistema con Cultivo = Maíz.
- **Procedimiento:** Se aplica un único filtro sobre la dimensión Cultivo (WHERE c.cultivo = 'Maíz'); la matriz resultante cruza Región (filas) y Sistema productivo (columnas) con Rendimiento ponderado, calculado como SUM(producción) / SUM(área cosechada) para cada combinación región × sistema dentro de ese corte.
- **Interpretación:** Al aislar el maíz se ve que el rendimiento tecnificado supera entre 2 y 3 veces al tradicional en todas las regiones (conocimiento C5); sin el slice, esa brecha quedaría diluida entre los demás cultivos, que no distinguen sistema productivo o lo hacen con otro criterio (destino, no tecnología).

### Dice · Arroz × Caribe × 2019–2024: tasa de cosecha por departamento y año

- **Análisis:** 4. Área sembrada no cosechada · enlace directo: `/r5/cosecha?ej=dice-arroz-caribe`
- **Dimensiones:** Cultivo (Arroz) + Territorio (Caribe) como filtros; Departamento × Año.
- **Medidas:** Tasa de cosecha (%) = SUM(cosechada) / SUM(sembrada) × 100.
- **Nivel y filtros:** Departamento × Año, filtrado por dos dimensiones.
- **Procedimiento:** Se combinan dos filtros sobre dimensiones distintas: Cultivo = Arroz y Región = Caribe (WHERE c.cultivo = 'Arroz' AND t.region = 'Caribe'); sobre ese subconjunto se agrupa por Departamento (filas) y Año (columnas) con Tasa de cosecha = 100 × SUM(cosechada) / SUM(sembrada).
- **Interpretación:** El dice aísla justo el subconjunto donde ocurre el choque de 2021: dentro de los departamentos del Caribe, Sucre muestra la caída más fuerte de tasa de cosecha ese año (conocimiento C8), un patrón que no sería visible ni en el promedio nacional de arroz ni en el promedio del Caribe para todos los cultivos.

## 5. Conocimientos multidimensionales

### C1 · La Orinoquía produce cuatro veces más de lo que su número de registros sugiere

_Análisis 1: Concentración de la producción_

- **Pregunta:** ¿Coincide la concentración territorial de registros (R4) con la de producción?
- **Dimensiones y medidas:** Territorio (región, departamento) × Cultivo; medidas: Registros (COUNT) y Producción (SUM, t), como % del total nacional.
- **Procedimiento:** Consulta base Región × Cultivo; luego slice Cultivo = Arroz y Cultivo = Plátano con drill-down a Departamento.
- **Evidencia:** Gráfica 2 del análisis (participación en producción vs. en registros) y matriz Región × Cultivo.
- **Hallazgo:** Orinoquía: 5,9 % de los registros pero 22,7 % de la producción nacional (22.118.225 t). Andina baja de 59,3 % de registros a 49,0 % de producción. Al bajar a departamento: Casanare aporta 29,7 % del arroz y Arauca 18,7 % del plátano del país.
- **Interpretación:** La Orinoquía produce mucho volumen con pocas unidades productivas de gran escala (arroz y plátano). El conocimiento evidente de R4 (predominio andino) describe dónde hay más reportes, no dónde se produce más.
- **Utilidad:** Para la planeación de abastecimiento y logística de acopio, la Orinoquía debe pesar según su volumen y no según el número de municipios.
- **Limitación:** El volumen no mide el destino del alimento ni el consumo local; no permite concluir sobre disponibilidad de alimentos en la región.

### C2 · La papa se concentra más a medida que se baja de nivel territorial

_Análisis 1: Concentración de la producción_

- **Pregunta:** ¿Cuántos territorios sostienen la producción de papa en cada nivel de la jerarquía?
- **Dimensiones y medidas:** Territorio (región → departamento → municipio) × Cultivo (Papa); medida: Producción (t) y su participación.
- **Procedimiento:** Slice Cultivo = Papa; drill-down Andina → Boyacá → municipios. En cada nivel se recalcula la participación sobre la producción de la selección.
- **Evidencia:** Ejemplo guiado «Drill-down Papa», matriz por municipio e indicador «miembros que reúnen el 50 %».
- **Hallazgo:** Tres departamentos (Cundinamarca, Boyacá, Nariño) suman 87,6 % de la papa nacional. Solo 16 de 308 municipios productores reúnen la mitad del volumen. En Boyacá, Siachoque (Boyacá) aporta 14,1 % de la producción departamental.
- **Interpretación:** La concentración que en R4 parecía regional (Andina) es en realidad un núcleo de pocos municipios del altiplano. Un evento climático o sanitario local afecta una porción grande de la oferta nacional.
- **Utilidad:** Permite focalizar alertas tempranas, asistencia técnica y monitoreo de precios de papa en un grupo reducido de municipios.
- **Limitación:** No se dispone de datos de precios ni de comercio intermunicipal para confirmar la dependencia de otros territorios (hipótesis).

### C3 · Más registros de maíz no significan más maíz

_Análisis 2: Evolución de la producción_

- **Pregunta:** ¿El crecimiento de registros de 2021 que vio R4 refleja un aumento de la producción?
- **Dimensiones y medidas:** Tiempo (año) × Cultivo (cultivo → desagregación); medidas: Registros, Municipios únicos (COUNT DISTINCT), Producción (t).
- **Procedimiento:** Slice Cultivo = Maíz; filas = Año; columnas = Desagregación (drill-down en la jerarquía de cultivo); gráfico índice 2019 = 100.
- **Evidencia:** Gráfica 2 (índice de producción, registros y municipios) y matriz Año × Desagregación con Cultivo = Maíz.
- **Hallazgo:** Registros de maíz: 2.107 (2019) → 3.507 (2024), +66,4 %; municipios: 984 → 1.031 (+4,8 %); producción: 1.922.616 t → 1.345.832 t (-30,0 %). Las desagregaciones pasan de 2 en 2020 a 4 en 2021.
- **Interpretación:** El salto de registros de R4 es un cambio de clasificación de EVA (maíz amarillo/blanco), no una expansión del cultivo. En ese mismo periodo la producción de maíz cayó.
- **Utilidad:** Evita usar el número de registros como indicador de oferta; el seguimiento del maíz debe hacerse con toneladas y área.
- **Limitación:** No se puede atribuir la caída a una causa (importaciones, precios, clima) con estos datos; es una asociación temporal.

### C4 · El arroz trasladó su cosecha principal del semestre A al B

_Análisis 2: Evolución de la producción_

- **Pregunta:** ¿El total anual estable del arroz oculta cambios entre semestres?
- **Dimensiones y medidas:** Tiempo (trienio → año → periodo) × Cultivo (Arroz); medida: Producción (t).
- **Procedimiento:** Slice Cultivo = Arroz; drill-down de Año a Periodo y roll-up de vuelta a Año y Trienio (ejemplo guiado).
- **Evidencia:** Matriz y gráfica 1 en el nivel Periodo vs. nivel Año.
- **Hallazgo:** En 2019 el semestre A aportó 61,7 % del arroz del año (2.127.690 t); en 2024 solo 28,1 % (1.040.084 t). En el nivel Año la producción pasa de 3.450.968 t a 3.703.317 t (+7,3 %).
- **Interpretación:** El roll-up a año esconde un cambio de calendario productivo: la oferta de arroz se desplazó al segundo semestre. Como hipótesis, puede relacionarse con la disponibilidad de agua o con decisiones de siembra; los datos no lo comprueban.
- **Utilidad:** La programación de almacenamiento y de compras públicas de arroz debe revisarse por semestre, no solo por año.
- **Limitación:** Los semestres A y B solo son comparables entre sí para cultivos transitorios; el plátano (anual) no entra en esta comparación.

### C5 · El maíz tradicional ocupa la mayor parte del área con menos de la mitad del rendimiento

_Análisis 3: Brecha entre sistemas productivos_

- **Pregunta:** ¿Qué explica que el maíz domine los registros (R4) y sea solo el 10 % de la producción?
- **Dimensiones y medidas:** Sistema productivo × Cultivo (Maíz) × Territorio (región); medidas: Rendimiento ponderado (t/ha), Área cosechada (ha), Producción (t), Registros.
- **Procedimiento:** Slice Cultivo = Maíz; Región × Sistema; luego dice Región = Caribe × Cultivo = Maíz.
- **Evidencia:** Indicadores del análisis con Cultivo = Maíz y matriz Región × Sistema (ejemplo guiado «Slice»).
- **Hallazgo:** Rendimiento del maíz tecnificado 5,08 t/ha vs. tradicional 1,97 t/ha (2,6×). El tradicional reúne 80,1 % de los registros y 61,1 % del área cosechada, pero solo 37,9 % de la producción. En el Caribe el tradicional cubre 73,6 % del área de maíz con 2,03 t/ha (tecnificado: 4,27 t/ha).
- **Interpretación:** El predominio del maíz en R4 se debe sobre todo a muchas unidades de maíz tradicional, frecuentemente de autoconsumo y baja productividad. Ese es el segmento donde la seguridad alimentaria es más frágil.
- **Utilidad:** Señala al maíz tradicional del Caribe como prioridad para programas de tecnificación, semillas y extensión rural.
- **Limitación:** La brecha es una asociación: el rendimiento también depende de suelos y clima; no prueba que tecnificar elimine la diferencia.

### C6 · El arroz de la Orinoquía es casi totalmente tecnificado; el tradicional sobrevive en el Caribe

_Análisis 3: Brecha entre sistemas productivos_

- **Pregunta:** ¿Cómo se reparte el arroz entre sistemas y regiones, y qué rendimiento logra cada combinación?
- **Dimensiones y medidas:** Sistema productivo × Territorio (región) × Cultivo (Arroz); medidas: Área cosechada (ha), Rendimiento (t/ha).
- **Procedimiento:** Slice Cultivo = Arroz; pivot de Región × Sistema a Sistema × Región; gráfica 2 con composición del área por sistema.
- **Evidencia:** Gráfica 2 (composición % del área por sistema) y matriz Región × Sistema con Cultivo = Arroz.
- **Hallazgo:** Orinoquía tiene 45,0 % del área de arroz cosechada del país y el 99,5 % de ella es tecnificada. El mayor rendimiento está en el arroz tecnificado andino (7,07 t/ha); el arroz tradicional del Caribe (221.224 ha) rinde 2,77 t/ha.
- **Interpretación:** El arroz nacional depende de un sistema tecnificado territorialmente concentrado; el arroz tradicional del Caribe responde más a un sistema campesino que a una oferta comercial.
- **Utilidad:** Orienta apoyos diferenciados: infraestructura de riego y secamiento en la Orinoquía; asistencia técnica al arroz tradicional del Caribe.
- **Limitación:** EVA solo diferencia sistema para maíz y arroz; para papa, frijol, yuca y plátano la comparación no es posible.

### C7 · El Caribe acumula la mayor área no cosechada, sobre todo en maíz y en Bolívar

_Análisis 4: Área sembrada no cosechada_

- **Pregunta:** ¿Dónde se pierde más área sembrada y qué cultivos y departamentos la explican?
- **Dimensiones y medidas:** Territorio (región → departamento) × Cultivo × Calidad; medidas: Área no cosechada (ha), Tasa de cosecha (%).
- **Procedimiento:** Región × Cultivo con área no cosechada; drill-down Caribe → Departamento; repetición con el filtro de calidad «solo coherentes».
- **Evidencia:** Matriz Región × Cultivo (medida área no cosechada), gráfica 1 y prueba de sensibilidad con el filtro de calidad.
- **Hallazgo:** Caribe: 37,4 % del área no cosechada nacional (289.202 ha) con 20,5 % de los registros y la menor tasa de cosecha (91,9 %). El maíz aporta 108.717 ha y Bolívar 36,7 % del área no cosechada caribeña. Excluyendo filas con área incoherente, el Caribe sigue entre las dos primeras (31,5 %), pero la Orinoquía pasa a 38,5 %.
- **Interpretación:** La pérdida de área en el Caribe es persistente y está ligada al maíz, el cultivo de base campesina de la región. El orden entre regiones depende del tratamiento de las filas incoherentes, por lo que se informa con ambos criterios.
- **Utilidad:** Prioriza seguros agropecuarios y gestión de riesgo climático para el maíz en Bolívar, Córdoba y Sucre.
- **Limitación:** EVA no registra la causa de la pérdida (sequía, inundación, plagas, abandono); cualquier explicación es una hipótesis.

### C8 · 2021 fue un año atípico para el arroz del Caribe, con Sucre en el extremo

_Análisis 4: Área sembrada no cosechada_

- **Pregunta:** ¿La caída de la tasa de cosecha del arroz es generalizada o se concentra en un año y territorio?
- **Dimensiones y medidas:** Tiempo (año) × Territorio (región → departamento) × Cultivo (Arroz); medidas: Tasa de cosecha (%), Área no cosechada (ha).
- **Procedimiento:** Dice Cultivo = Arroz × Región = Caribe; Departamento × Año; comparación con el nivel nacional y con el filtro «solo coherentes».
- **Evidencia:** Ejemplo guiado «Dice Arroz × Caribe», gráfica 2 y celda Sucre × 2021 de la matriz.
- **Hallazgo:** La tasa nacional de cosecha de arroz pasó de 98,5 % (2019) a 93,0 % (2021); el área no cosechada subió de 9.495 ha a 47.959 ha. En el Caribe, Sucre registró 60,7 % en 2021 (vs. 96,7 % en 2019); el valor se mantiene en 60,7 % al excluir filas incoherentes.
- **Interpretación:** Se trata de un choque puntual y localizado, no de un deterioro continuo. Como hipótesis, coincide con el periodo de lluvias intensas de La Niña 2021, que los datos de EVA no permiten verificar.
- **Utilidad:** Justifica sistemas de alerta y reservas de arroz activables por año y territorio, en lugar de medidas permanentes nacionales.
- **Limitación:** Con seis años de datos no se puede estimar la frecuencia de estos eventos ni separar el efecto climático del de mercado.

## 6. Validaciones del modelo frente a los datos tratados

| Grupo | Comprobación | Modelo | Origen / esperado | Resultado | Nota |
|---|---|---|---|---|---|
| Unicidad | dim_territorio: filas = claves únicas (territorio_key, cod_municipio) | 1099 | 1099 | OK | PRIMARY KEY + UNIQUE sobre la clave natural. |
| Unicidad | dim_tiempo: filas = claves únicas (tiempo_key, periodo_codigo) | 18 | 18 | OK | PRIMARY KEY + UNIQUE sobre la clave natural. |
| Unicidad | dim_cultivo: filas = claves únicas (cultivo_key, desagregacion) | 17 | 17 | OK | PRIMARY KEY + UNIQUE sobre la clave natural. |
| Unicidad | dim_sistema_productivo: filas = claves únicas (sistema_key, sistema) | 8 | 8 | OK | PRIMARY KEY + UNIQUE sobre la clave natural. |
| Integridad referencial | Hechos sin correspondencia en dim_territorio | 0 | 0 | OK | LEFT JOIN de la FK contra la dimensión. |
| Integridad referencial | Hechos sin correspondencia en dim_tiempo | 0 | 0 | OK | LEFT JOIN de la FK contra la dimensión. |
| Integridad referencial | Hechos sin correspondencia en dim_cultivo | 0 | 0 | OK | LEFT JOIN de la FK contra la dimensión. |
| Integridad referencial | Hechos sin correspondencia en dim_sistema_productivo | 0 | 0 | OK | LEFT JOIN de la FK contra la dimensión. |
| Granularidad | Combinaciones municipio × desagregación × periodo repetidas | 0 | 0 | OK | Además lo impide la restricción UNIQUE de la tabla de hechos. |
| Granularidad | Filas tras unir hechos con las 4 dimensiones | 48932 | 48932 | OK | Si una relación multiplicara filas, el conteo tras el JOIN sería mayor. |
| Faltantes y desconocidos | Hechos asignados al miembro 'Desconocido' (clave 0) | 0 | 0 | OK | Toda fila de origen encontró su municipio, cultivo y sistema. |
| Faltantes y desconocidos | Municipios sin región asignada | 0 | 0 | OK | Los 32 departamentos están en el mapeo departamento → región. |
| Faltantes y desconocidos | Hechos con alguna medida faltante (NULL) | 0 | 0 | OK | Un faltante sería ausencia de dato; el origen tratado no tiene ninguno en las medidas. |
| Faltantes y desconocidos | Hechos con área cosechada = 0 (respuesta negativa reportada, no faltante) | 2298 | 2298 | OK | EVA reporta que no hubo cosecha (pérdida total o cultivo en crecimiento): se conserva como 0. Suma en área sembrada y área no cosechada, baja la tasa de cosecha y no entra en el rendimiento porque su denominador es el área cosechada. |
| Faltantes y desconocidos | Hechos con área cosechada > sembrada (se conservan con bandera) | 6700 | 6700 | OK | No es un faltante: se marcan y pueden excluirse en el análisis. |
| Conteos y agregaciones | Registros: tabla de hechos vs. EVA tratado | 48932 | 48932 | OK | Carga completa, sin filtrado. |
| Conteos y agregaciones | Producción total (t) | 97576401.49 | 97576401.49 | OK | SUM aditiva sobre la granularidad. |
| Conteos y agregaciones | Área sembrada total (ha) | 13339207.23 | 13339207.23 | OK | SUM aditiva sobre la granularidad. |
| Conteos y agregaciones | Municipios únicos | 1098 | 1098 | OK | COUNT DISTINCT, no suma de conteos por grupo. |
| Conteos y agregaciones | Producción de Maíz en 2024 (t) — corte por dos dimensiones | 1345832.1 | 1345832.1 | OK | Mismo corte en el modelo (JOIN) y en el JSON tratado. |
| Conteos y agregaciones | Rendimiento nacional (t/ha): ponderado del modelo vs. promedio simple del origen | 7.77 | 5.6 | Diferencia explicada | Diferencia esperada: el promedio simple da el mismo peso a un municipio de 1 ha que a uno de 30.000 ha y además incluye rendimientos reportados por EVA en filas con área cosechada 0. El modelo usa SUM(producción)/SUM(área cosechada). |
