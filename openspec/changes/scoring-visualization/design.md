## Context

El notebook termina hoy en la exportación: dos CSV y una lista de comprobación. Las verificaciones de §6 dicen si las calificaciones son *consistentes*, no qué *muestran*. La pregunta para la que se armó el corpus —si la percepción de México como destino se movió alrededor de los partidos del mundial en el país— es temporal y comparativa, y ninguna celda actual la aborda.

Los datos disponibles al final del pipeline:

```
TIDY  tweet_id · id_criterio · slug · criterio · aplicable ·
      nivel · puntaje · justificacion · estado · detalle · contexto_incompleto
DF    id · created_at · lang · text_completo · … (50 columnas)
```

`TIDY` no trae fecha ni idioma. Toda gráfica de este change empieza por una unión.

Medidas del corpus que condicionan el diseño: 2,562 tweets, 61 días continuos (2026-06-01 a 2026-07-31), ~42 por día. Por idioma: `en` 2,006, `ja` 417, `qme` 64, `und` 21, `es` 12, `zxx` 8, y doce idiomas más con menos de cinco tweets cada uno.

Con los cortes acordados:

| Período | Rango | Días | Tweets | Por día |
|---|---|---|---|---|
| `PREVIO A MUNDIAL` | may 31 – jun 10 | 11 | 447 | 40.6 |
| `DURANTE MUNDIAL EN MEXICO` | jun 11 – jul 5 | 25 | 1,240 | 49.6 |
| `DESPUES DE PARTIDOS EN MEXICO` | jul 6 – jul 31 | 26 | 875 | 33.7 |

El corte del 6 de julio no es arbitrario: el último partido jugado en territorio mexicano fueron los octavos de final del 5 de julio en el Estadio Azteca. Guadalajara cerró el 26 de junio y Monterrey también terminó en octavos. El torneo siguió hasta el 19 de julio fuera de México, y por eso el tercer período se llama «después de partidos en México» y no «después del mundial».

## Goals / Non-Goals

**Goals:**

- Ver la evolución diaria de cada criterio y la comparación entre los tres períodos.
- Filtrar por idioma sin volver a ejecutar Python.
- Producir un artefacto compartible que sobreviva al cierre del notebook.
- No modificar ninguna celda existente: la sección lee `TIDY` y `DF` y no escribe sobre ellos.

**Non-Goals:**

- Inferencia estadística. No hay pruebas de hipótesis ni intervalos de confianza; las gráficas describen, no concluyen.
- Un tablero con estado persistente o parámetros por URL.
- Analizar el contenido de las justificaciones. Se grafican niveles, no texto.
- Corregir el desbalance de los períodos. 447 contra 1,240 es un hecho del corpus; la proporción lo hace comparable, no lo elimina.

## Decisions

### 1. Pre-agregar en pandas, filtrar en JavaScript

**Alternativa considerada**: `ipywidgets` recalculando en Python en cada cambio de filtro.

Se descartó por tres razones. El tiempo de respuesta pasa de instantáneo a varios cientos de milisegundos con parpadeo del lienzo; `ipywidgets` en Colab es históricamente frágil; y el resultado deja de ser exportable, porque un widget no sobrevive fuera del kernel.

El argumento decisivo es el tamaño. Agregando a `(fecha, criterio, nivel, idioma, estado) → conteo`:

```
61 días × N criterios × ~6 niveles × ~5 idiomas con datos
   ≈ 900·N combinaciones no vacías → con N=5, unas 4,500 filas → ~150 KB
```

Frente a 2,562 × N filas crudas con justificaciones, que serían megabytes que ninguna gráfica usa. Con el agregado embebido, el filtro de idioma y el conmutador de modo son una reducción sobre un arreglo pequeño, en el cliente.

Las combinaciones vacías se omiten en lugar de emitirse como cero: la matriz completa es mayormente hueca, sobre todo en los doce idiomas de cola.

### 2. ECharts por CDN, no `pyecharts`

`pyecharts` daría una API de Python, pero agrega una dependencia y, sobre todo, estorba: el filtro del lado del cliente exige escribir el manejador en JavaScript de todas formas, y hacerlo a través de una abstracción de Python que genera ese JavaScript es más difícil que escribirlo directamente.

La configuración de cada gráfica se arma como un diccionario de Python y se serializa con `json.dumps`. El código JavaScript se limita a los manejadores de los controles y a llamar `setOption`.

### 3. Una sola página, dos destinos

La misma función construye un documento HTML completo. Dentro del notebook se entrega con `IPython.display.HTML`; al disco se escribe tal cual. No hay dos caminos de renderizado que puedan divergir.

Esto resuelve además la limitación de Colab: cada salida de celda vive en un iframe aislado y el `.ipynb` guarda el HTML sin el estado del JavaScript, así que la gráfica deja de ser interactiva al reabrir el notebook hasta reejecutar la celda. El archivo descargable es el artefacto que sí sobrevive.

**Trade-off aceptado**: el HTML depende del CDN. Empotrar ECharts lo haría autosuficiente pero sumaría alrededor de un megabyte a cada archivo y al notebook guardado. Se prefiere el CDN con un mensaje de error explícito cuando la carga falla, en vez de una página en blanco.

### 4. La proporción es el modo por defecto

El volumen diario del corpus no es constante entre períodos: 40.6, 49.6 y 33.7 tuits por día. Comparar conteos absolutos entre períodos mediría cuántos tweets se recogieron, no cómo calificaron. El conteo absoluto queda disponible porque responde otra pregunta legítima —cuánto se habló— pero no es la que el corte por períodos plantea.

### 5. Los estados fuera de escala no se apilan con los niveles

`NO_APLICABLE` y `FUERA_DE_ESCALA` no son grados de logro. El pipeline los separa deliberadamente: el diseño original insiste en que un tweet ajeno al criterio no es un tweet de bajo logro, y colapsarlos envenena cualquier promedio. Apilarlos junto a los niveles reintroduciría en la gráfica la confusión que el modelo de datos evita.

Las proporciones se calculan sobre las calificaciones `OK` y los otros dos estados se reportan como información separada. Consecuencia: un criterio mayormente no aplicable mostrará una distribución de niveles calculada sobre pocos casos, y esa escasez tiene que ser visible.

### 5b. El nivel `0` es ausencia y no se grafica

La rúbrica real, ya parseada, tiene 3 criterios con seis niveles `0`–`5`. Medido en `rubrica.json`, el descriptor del `0` de los tres dice que el tuit **no evalúa nada** de esa dimensión:

```
0  "El tuit no expresa ninguna emoción del emisor hacia México ni su gente"
0  "El tuit no evalúa ningún objeto cultural, gastronómico, histórico…"
0  "El tuit no evalúa ninguna competencia económica, política, institucional…"
```

Los niveles `1`–`5` son una escala de **valencia** —muy negativo, negativo, neutral/mixto, positivo, muy positivo—, no de logro. Apilar el `0` junto a ellos lo pondría en el extremo de "muy negativo", que es justo lo contrario de lo que significa, y hundiría cualquier promedio con tweets que simplemente no hablan del tema.

Por eso el `0` se declara en `CONFIG` como nivel de ausencia y se excluye de las series y del denominador de la proporción, igual que `NO_APLICABLE`.

**Consecuencia**: la rúbrica codifica la ausencia dos veces —como nivel `0` y como `aplicable=false`— y el modelo se repartirá entre ambas de forma impredecible. La visualización las suma en una sola magnitud de ausencia, de modo que esa inconsistencia no se propaga a las gráficas. Arreglarla de raíz exigiría editar `rubrica.json` y volver a calificar, que cuesta otra corrida completa.

### 6. Multi-selección de idioma con el n a la vista

**Alternativa considerada**: un desplegable con los 18 idiomas, o agruparlos en inglés / japonés / otros.

El desplegable crudo invita a filtrar a `fi` o `eu`, que tienen un tweet. La agrupación rígida oculta que `qme` no es un idioma sino el código de contenido multimedia sin texto.

La multi-selección con el total al lado de cada opción deja ver la escasez antes de elegirla, y permite la comparación que interesa —inglés contra japonés— que una agrupación en "otros" impediría. El umbral de advertencia se dispara sobre la selección activa, no sobre cada idioma por separado, porque seleccionar cinco idiomas de cola sí puede sumar una muestra defendible.

### 7. Ausencia de datos, no cero

Un día sin tweets calificados para un criterio no es un día con cero tweets en el nivel más bajo. Representarlo como cero dibujaría una caída que no ocurrió. Las series marcan el hueco.

### 8. Suavizado opcional, apagado por defecto

Con ~42 tweets/día repartidos entre los niveles de un criterio, cada punto vale unos 7 tweets; filtrando a japonés, cerca de 1. La media móvil hace legible la tendencia, pero altera lo que se ve, así que no puede ser el estado inicial: primero se muestra el dato, y el suavizado es una decisión explícita del lector.

### 9. Los períodos viven en CONFIG

Como el resto de los parámetros del notebook. Se declaran como intervalos con límite inferior inclusivo y superior exclusivo —evita que un tweet del 11 de junio caiga en dos períodos— y el último queda abierto. Cambiar las fechas y reejecutar la sección basta; no hay fechas en el código de las gráficas.

### 10. El día se corta en hora de México, no en UTC

`created_at` viene en UTC (`2026-06-03T23:59:50`). México corre en UTC−6. Un tuit publicado a las 19:00 del 10 de junio en Ciudad de México queda registrado como 01:00 del 11 de junio en UTC y, sin conversión, cruzaría a `DURANTE MUNDIAL EN MEXICO` un día antes de tiempo.

Los cortes de período son eventos locales —el partido inaugural en el Azteca, los octavos del 5 de julio— y el público que se quiere medir vive ese calendario. La fecha de agrupación se obtiene convirtiendo a `America/Mexico_City` y tomando la fecha local.

El efecto está medido sobre el corpus y es mayor de lo que sugiere la intuición: **602 tuits, el 23.5%, cambian de día** al convertir. Los totales por período pasan de 437 / 1,230 / 895 en UTC a **447 / 1,240 / 875** en hora de México. No cambia ninguna conclusión gruesa; sí cambia cada número que se publique, así que la zona efectiva se imprime junto al reporte.

Consecuencia sobre el primer corte: el corpus se recolectó por fecha UTC, de modo que al retroceder seis horas trece tuits caen el 31 de mayo local. `PREVIO A MUNDIAL` empieza el **2026-05-31** en lugar del 1 de junio para no dejarlos fuera de todo período — un tuit del 31 de mayo por la tarde es tan «previo al mundial» como uno del 1 de junio, y descartarlo sería un artefacto de la zona horaria, no una decisión de análisis.

La zona vive en `CONFIG` junto a los períodos, porque un corpus de otro país necesitaría otra. Si la conversión falla —una fecha sin huso declarado, un entorno sin base de datos de husos— se asume UTC y se informa, en lugar de abortar.

### 11. El orden de los paneles lo fija la rúbrica

**Alternativa considerada**: ordenar los criterios por magnitud de la diferencia entre períodos, para que lo interesante quede arriba.

Se descartó. Un orden que depende de los datos es selección de hipótesis después de verlas: con 447 tuits en el primer período, el criterio que más se "mueve" es con frecuencia el que menos datos tiene. Poner arriba el mayor salto invita a leerlo como el hallazgo principal cuando puede ser el mayor error de muestreo.

El orden de la rúbrica es estable entre corridas, coincide con el de la celda 20 y no le dice al lector qué debe encontrar.

### 12. Volumen diario como primera gráfica

Es el denominador de todas las demás. El corpus va de 13 tuits el 9 de julio a 98 el 18 de julio, y los períodos promedian 40.6, 49.6 y 33.7 por día. Sin esa serie a la vista, cualquier salto en los conteos absolutos se lee como cambio del fenómeno cuando puede ser cambio del muestreo.

Va apilada por idioma, con las bandas de período marcadas igual que las series de criterio, y encabeza la página. No sale del agregado de niveles sino de un conteo aparte por `(fecha, idioma)`, porque debe incluir también los tuits cuyas calificaciones quedaron `NO_APLICABLE` o fallidas: el volumen es del corpus, no de las calificaciones válidas.

### 13. Filtro de contexto incompleto, apagado por defecto

El pipeline ya marca `contexto_incompleto` con `reply`, `retweet` o `quote` y advierte al modelo de que el texto no es autosuficiente. Esas calificaciones son de menor confianza por construcción, y hoy esa marca viaja hasta `TIDY` sin que nada la consuma.

Se expone como casilla «sólo tuits autosuficientes», apagada al abrir: el estado inicial muestra todo el dato, y excluir es una decisión explícita del lector, igual que el suavizado. Apagarla por defecto también evita que dos personas comparen cifras distintas creyendo que miran lo mismo.

### 14. La escala de niveles es divergente, no categórica

Los niveles 1 a 5 no son categorías ni grados de logro: son **valencia**, de muy negativo a muy positivo, con un centro que significa «ni una cosa ni la otra». Pintarlos con una paleta categórica —un color por nivel, sin relación entre ellos— tiraría la única propiedad que la escala tiene: el orden y el signo.

Se usa una **rampa divergente**: dos matices opuestos con un gris neutro en el centro, un paso por brazo hacia cada extremo. Rojo para el brazo negativo, azul para el positivo, gris `#898781` en el punto medio.

Las rampas no se eligieron a ojo. Cada brazo se validó como rampa ordinal con el validador del sistema de diseño, en modo claro y oscuro:

| Brazo | Pasos (claro → oscuro) | Resultado |
|---|---|---|
| negativo | `#eb8a84` `#d8514c` `#a02020` | monotonía, ΔL y contraste del extremo: pasa en ambos modos |
| positivo | `#86b6ef` `#3987e5` `#1c5cab` | pasa en ambos modos |
| neutro | `#898781` | 3.50:1 en claro, 4.85:1 en oscuro |

Tres pasos por brazo es el techo: con cuatro, el extremo oscuro cae a 1.95:1 sobre la superficie oscura y falla el piso de 2:1. La rampa cubre por tanto hasta siete niveles; con más, se avisa y se recorta en lugar de inventar matices.

El par adyacente gris↔rojo claro queda en ΔE 6.4 bajo simulación de protanopia, dentro de la banda 6–8 que el método permite **sólo con codificación secundaria**. La página la trae por construcción: separador de 2 px del color de la superficie entre segmentos apilados, leyenda siempre presente y vista de tabla.

### 15. El idioma no se pinta de azul

El volumen diario se apila por idioma y vive en la misma página que las series de valencia. Si el idioma usara la paleta categórica por defecto, «inglés» sería azul en el primer panel y «muy positivo» sería azul en todos los demás. Un lector que baja la página arrastra el significado del color.

Los idiomas toman entonces matices que la rampa divergente no usa —naranja, aqua, violeta— asignados por **frecuencia global y fijos**: el primero por volumen se queda con su color aunque el filtro lo deje solo, porque el color sigue a la entidad y no a su posición en la selección. Del cuarto en adelante se pliegan a «Otros» en gris.

El orden de apilado se validó junto con la asignación: gris, naranja, aqua, violeta clarea todos los pisos de separación en ambos modos. El orden importa porque la comprobación es entre bandas vecinas del apilado: con el gris junto al aqua, el par cae a ΔE 5.1 y falla.

## Risks / Trade-offs

**La densidad por idioma no soporta lo que el filtro permite pedir** → `es` tiene 12 tweets en 61 días y doce idiomas tienen menos de cinco. La advertencia por umbral es la mitigación, pero no impide la consulta: un lector decidido puede graficar un idioma con n=1. Se prefiere advertir a prohibir.

**Los períodos están desbalanceados 447 / 1,240 / 875** → La proporción los hace comparables, pero el primer período tiene menos de la mitad de datos que el segundo y la gráfica no lo dice por sí sola. El n de cada período debe estar impreso junto a cada panel.

**Se puede leer causalidad donde solo hay coincidencia temporal** → Un cambio entre períodos puede deberse a qué se consultó, no a qué pasó. Los cuatro lotes de consulta abarcan el rango completo, lo cual ayuda, pero el corpus no es una muestra aleatoria de la conversación. Es una limitación a dejar escrita junto a las gráficas, no un defecto a corregir en el código.

**Dependencia del CDN** → Sin red, la página queda inservible. Mitigado con un mensaje explícito en vez de una página en blanco.

**Las gráficas no sobreviven al guardado del notebook** → Limitación de Colab, no del diseño. Mitigada con el archivo descargable.

**El agregado puede crecer con rúbricas grandes** → El cálculo escala con N criterios × niveles. Con una rúbrica de veinte criterios y ocho niveles el payload se multiplica por ocho respecto del ejemplo. Sigue siendo del orden de un megabyte, aceptable, pero conviene reportar el tamaño del agregado al generarlo.

**Identificadores no confiables** → Si se corre sobre el corpus sin reparar, la unión entre `TIDY` y `DF` es falsa en las 2,562 filas, porque los identificadores pasaron por `float64`. La sección debe correrse después de `reparar-corpus-y-traducir`, y el reporte de huérfanos es la señal de alarma si alguien lo intenta antes.

## Migration Plan

1. Agregar a `CONFIG` la definición de los tres períodos y los parámetros de visualización.
2. Insertar la sección § 8 después de la celda 25 de exportación.
3. Ejecutar sobre una corrida completa del corpus reparado y contrastar los totales por período contra los medidos aquí: 447 / 1,240 / 875.
4. Verificar el archivo HTML generado abriéndolo fuera del notebook.

Vuelta atrás: la sección solo lee y escribe un archivo nuevo. Borrar las celdas y el HTML devuelve el notebook al estado previo.

## Open Questions

Ninguna. Las tres que quedaron abiertas al redactar el diseño se resolvieron antes de implementar y están arriba como decisiones 11, 12 y 13; la zona horaria, que no se había planteado, es la decisión 10.
