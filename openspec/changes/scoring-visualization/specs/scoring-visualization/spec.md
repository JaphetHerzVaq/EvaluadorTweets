## ADDED Requirements

### Requirement: Unión de calificaciones con el corpus
El sistema SHALL unir los resultados de calificación con el corpus por identificador de tweet para obtener la fecha de publicación y el idioma, que los resultados no contienen, y SHALL reportar los resultados cuyo identificador no exista en el corpus sin incorporarlos.

#### Scenario: Unión exitosa
- **WHEN** se preparan los datos de visualización a partir de los resultados y el corpus
- **THEN** cada calificación SHALL quedar asociada a la fecha de publicación y al idioma de su tweet

#### Scenario: Resultado huérfano
- **WHEN** un resultado tiene un identificador que no existe en el corpus
- **THEN** el sistema SHALL excluirlo del agregado e informar cuántos se excluyeron

#### Scenario: Fecha ilegible
- **WHEN** la fecha de publicación de un tweet no se puede interpretar
- **THEN** esa fila SHALL excluirse del agregado temporal y contarse en el reporte

#### Scenario: Cobertura insuficiente
- **WHEN** el número de tweets calificados es tan bajo que la media diaria queda por debajo de un umbral configurable
- **THEN** el sistema SHALL advertir que las series diarias no son interpretables a esa escala, antes de dibujar

### Requirement: Segmentación en períodos configurables
El sistema SHALL asignar cada tweet a exactamente un período, definidos en la configuración como intervalos de fecha con límite inferior inclusivo y límite superior exclusivo, y SHALL mostrar para cada período su rango, su número de días, su número de tweets y su promedio diario.

#### Scenario: Asignación en el límite
- **WHEN** un tweet fue publicado el 2026-06-11
- **THEN** SHALL asignarse a `DURANTE MUNDIAL EN MEXICO` y NO a `PREVIO A MUNDIAL`, porque el límite inferior es inclusivo y el superior exclusivo

#### Scenario: Período final abierto
- **WHEN** un período no declara límite superior
- **THEN** SHALL incluir todos los tweets desde su límite inferior en adelante

#### Scenario: Tweet fuera de todo período
- **WHEN** un tweet cae fuera de todos los intervalos definidos
- **THEN** SHALL quedar excluido de las gráficas por período y contarse en el reporte, sin interrumpir la ejecución

#### Scenario: Períodos redefinidos
- **WHEN** se cambian las fechas de corte en la configuración y se reejecuta la sección
- **THEN** todas las gráficas por período SHALL reflejar los nuevos cortes sin modificar código

### Requirement: Agregación previa al renderizado
El sistema SHALL calcular los conteos agrupados por fecha, criterio, nivel, idioma y estado una sola vez en Python, y SHALL embeber ese agregado en la página, en lugar de embeber las calificaciones individuales.

#### Scenario: Tamaño del payload
- **WHEN** se generan las gráficas para el corpus completo
- **THEN** la página SHALL contener únicamente los conteos agregados, sin justificaciones ni textos de tweets

#### Scenario: Combinaciones vacías
- **WHEN** una combinación de fecha, criterio, nivel e idioma no tiene tweets
- **THEN** SHALL omitirse del agregado en lugar de embeberse como cero

### Requirement: Separación de la ausencia respecto de la escala
El sistema SHALL excluir de las series de niveles tanto las calificaciones con estado `NO_APLICABLE` o `FUERA_DE_ESCALA` como aquellas cuyo nivel esté declarado como **nivel de ausencia** en la configuración, SHALL calcular las proporciones únicamente sobre las calificaciones restantes, y SHALL reportar lo excluido por separado.

La rúbrica de este proyecto codifica la ausencia dentro de la escala: el nivel `0` de los tres criterios significa que el tuit no evalúa nada de esa dimensión. Los niveles `1` a `5` forman una escala de valencia —muy negativo a muy positivo—, no de logro. Graficar el `0` junto a ellos lo colocaría en el extremo de "muy negativo", que es lo contrario de lo que significa.

#### Scenario: Nivel de ausencia excluido de las series
- **WHEN** un criterio tiene en un día 30 calificaciones en niveles 1 a 5 y 12 en el nivel `0`
- **THEN** las series de niveles SHALL mostrar sólo las 30 y las proporciones SHALL calcularse sobre 30, no sobre 42

#### Scenario: Proporción sobre calificaciones válidas
- **WHEN** un criterio tiene calificaciones `OK` y calificaciones `NO_APLICABLE`
- **THEN** las proporciones de nivel SHALL calcularse sólo sobre las `OK` que no estén en un nivel de ausencia

#### Scenario: Ausencia visible como magnitud propia
- **WHEN** se muestra una gráfica de distribución
- **THEN** la proporción de ausencia —nivel de ausencia más no aplicables más fallidas— SHALL quedar visible como información aparte, no apilada junto a los niveles

#### Scenario: Doble codificación de la ausencia
- **WHEN** un mismo tweet sin contenido de la dimensión llega como `aplicable=false` en unas filas y como `nivel=0` en otras
- **THEN** ambas SHALL contarse como ausencia y no como dos categorías distintas

#### Scenario: Rúbrica sin nivel de ausencia
- **WHEN** la configuración no declara ningún nivel de ausencia para un criterio
- **THEN** todos sus niveles SHALL graficarse, sin exclusiones más allá de los estados

### Requirement: Serie diaria por criterio
El sistema SHALL producir, para cada criterio de la rúbrica, una gráfica de la evolución diaria de sus niveles de logro, con los períodos señalados sobre el eje temporal, y SHALL ofrecer un suavizado por media móvil de ventana configurable.

#### Scenario: Una gráfica por criterio
- **WHEN** la rúbrica tiene N criterios
- **THEN** SHALL generarse N series diarias, sin que N aparezca fijo en el código

#### Scenario: Períodos señalados
- **WHEN** se dibuja una serie diaria
- **THEN** los tres períodos SHALL aparecer delimitados sobre el eje temporal y nombrados

#### Scenario: Suavizado activado
- **WHEN** el usuario activa el suavizado con una ventana de 7 días
- **THEN** las series SHALL mostrar la media móvil sin alterar el agregado subyacente

#### Scenario: Día sin datos
- **WHEN** un día no tiene ningún tweet calificado para un criterio
- **THEN** la serie SHALL representar ese día como ausencia de datos y no como cero

### Requirement: Distribución global y por período
El sistema SHALL producir una gráfica de la distribución de niveles por criterio sobre todo el corpus, y la misma distribución repetida para cada período, dispuesta de modo que los períodos se comparen lado a lado.

#### Scenario: Comparación entre períodos
- **WHEN** se muestran las distribuciones por período
- **THEN** los tres SHALL usar la misma escala y el mismo orden de niveles, para que las diferencias sean comparables visualmente

#### Scenario: Orden de los niveles
- **WHEN** se apilan los niveles de un criterio
- **THEN** SHALL ordenarse del más bajo al más alto según la rúbrica, no por frecuencia

### Requirement: Filtro de idioma por multi-selección
El sistema SHALL permitir seleccionar uno o varios idiomas, SHALL mostrar junto a cada opción su número total de tweets, y SHALL advertir cuando la selección activa deje menos tweets que un umbral configurable.

#### Scenario: Selección múltiple
- **WHEN** el usuario selecciona inglés y japonés
- **THEN** todas las gráficas SHALL recalcularse sobre la unión de ambos, sin volver a ejecutar Python

#### Scenario: Selección con muy pocos datos
- **WHEN** el usuario selecciona un idioma con 12 tweets en 61 días
- **THEN** el sistema SHALL mostrar una advertencia de que la serie diaria no es interpretable a esa densidad

#### Scenario: Selección vacía
- **WHEN** el usuario deselecciona todos los idiomas
- **THEN** las gráficas SHALL indicar que no hay datos seleccionados, sin romperse

#### Scenario: Idiomas sin contenido lingüístico
- **WHEN** el corpus trae códigos como `qme`, `und` o `zxx`
- **THEN** SHALL ofrecerse como opciones seleccionables, identificados como códigos sin idioma real

### Requirement: Conmutación entre conteo absoluto y proporción
El sistema SHALL permitir alternar entre conteo absoluto y proporción, y SHALL usar la proporción por defecto en las gráficas que comparan períodos.

#### Scenario: Volumen diario desigual
- **WHEN** se comparan períodos cuyo volumen diario va de 33.7 a 49.6 tuits por día
- **THEN** la vista por defecto SHALL ser la proporción, para que la comparación no refleje la intensidad del muestreo

#### Scenario: Cambio de modo
- **WHEN** el usuario alterna a conteo absoluto
- **THEN** todas las gráficas SHALL actualizarse sin volver a ejecutar Python

### Requirement: Doble salida, en el notebook y como archivo
El sistema SHALL mostrar las gráficas dentro de la salida del notebook y SHALL además escribir un archivo HTML autocontenido, con los mismos datos y controles, que funcione al abrirse fuera del notebook y sea descargable.

#### Scenario: Visualización en el notebook
- **WHEN** se ejecuta la celda de visualización
- **THEN** las gráficas SHALL renderizarse en la salida de la celda con sus filtros operativos

#### Scenario: Archivo independiente
- **WHEN** se abre el HTML generado fuera del notebook
- **THEN** SHALL mostrar las mismas gráficas con el filtro de idioma y el conmutador de modo funcionando, sin requerir el kernel

#### Scenario: Sin conexión al CDN
- **WHEN** la biblioteca de gráficas no se puede cargar desde el CDN
- **THEN** la página SHALL mostrar un mensaje explicando la causa, en lugar de quedar en blanco
