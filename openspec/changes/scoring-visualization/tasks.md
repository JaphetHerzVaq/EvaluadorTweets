## 1. Configuración

- [x] 1.1 Declarar en `CONFIG` los tres períodos como intervalos con límite inferior inclusivo y superior exclusivo, con el último abierto
- [x] 1.2 Declarar los parámetros de visualización: umbral de advertencia por muestra pequeña, ventana de la media móvil, umbral de cobertura diaria mínima y ruta del HTML de salida
- [x] 1.3 Validar al cargar `CONFIG` que los períodos no se solapen y estén ordenados, fallando con un mensaje claro si no
- [x] 1.4 Declarar en `CONFIG` la zona horaria de agrupación diaria y los niveles de ausencia de la rúbrica

## 2. Preparación de datos

- [x] 2.1 Unir `TIDY` con `DF` por `tweet_id` igual a `COL_ID` para incorporar `created_at` y `lang`
- [x] 2.2 Reportar y excluir los resultados cuyo identificador no exista en el corpus
- [x] 2.3 Convertir `created_at` a fecha y excluir las filas cuya fecha no se pueda interpretar, contándolas en el reporte
- [x] 2.3b Convertir `created_at` de UTC a la zona horaria configurada antes de extraer la fecha, asumiendo UTC e informando si la conversión falla
- [x] 2.4 Asignar el período a cada fila según los intervalos de `CONFIG`, dejando fuera y contando las que no caigan en ninguno
- [x] 2.5 Normalizar el idioma vacío a una etiqueta explícita para que sea seleccionable en el filtro
- [x] 2.5b Propagar la marca `contexto_incompleto` al agregado para que el filtro de autosuficiencia pueda aplicarse en el cliente
- [x] 2.6 Advertir cuando la media diaria de tweets calificados quede por debajo del umbral de cobertura, señalando que las series diarias no son interpretables

## 3. Agregación

- [x] 3.1 Agregar los conteos por `(fecha, criterio, nivel, idioma, estado)` omitiendo las combinaciones vacías
- [x] 3.2 Conservar el orden de los niveles de cada criterio tal como los declara la rúbrica, del más bajo al más alto
- [x] 3.3 Separar los estados `NO_APLICABLE` y `FUERA_DE_ESCALA` de las series de niveles, manteniéndolos como conteos aparte
- [x] 3.3b Declarar en `CONFIG` los niveles de ausencia por criterio —en esta rúbrica el `0` de los tres— y excluirlos de las series y del denominador de la proporción
- [x] 3.3c Sumar el nivel de ausencia, los no aplicables y las fallidas en una sola magnitud de ausencia, reportada aparte
- [x] 3.4 Calcular los totales por período: días, tweets y promedio diario
- [x] 3.5 Calcular los totales por idioma para mostrarlos junto a cada opción del filtro
- [x] 3.5b Calcular el volumen diario del corpus por `(fecha, idioma)` aparte del agregado de niveles, incluyendo no aplicables y fallidas
- [x] 3.6 Reportar el tamaño del agregado resultante en filas y en kilobytes serializados
- [x] 3.7 Verificar los totales por período contra los valores medidos en hora de México: 447, 1,240 y 875, que suman las 2,562 filas del corpus

## 4. Serialización a la página

- [x] 4.1 Serializar el agregado a JSON con las claves mínimas necesarias, sin justificaciones ni textos de tweets
- [x] 4.2 Construir la plantilla HTML con la etiqueta de carga de ECharts desde el CDN
- [x] 4.3 Mostrar un mensaje explicativo si la biblioteca no carga, en vez de dejar la página en blanco
- [x] 4.4 Incluir en la página el reporte de contexto: rango de fechas, n por período y n por idioma

## 5. Controles

- [x] 5.1 Multi-selección de idioma con el total de tweets al lado de cada opción
- [x] 5.2 Identificar en la lista los códigos que no son idiomas reales, como `qme`, `und` y `zxx`
- [x] 5.3 Advertir cuando la selección activa deje menos tweets que el umbral configurado
- [x] 5.4 Manejar la selección vacía mostrando un aviso, sin que las gráficas se rompan
- [x] 5.5 Conmutador entre conteo absoluto y proporción, con proporción como estado inicial
- [x] 5.6 Conmutador de suavizado por media móvil, apagado por estado inicial
- [x] 5.6b Casilla «sólo tuits autosuficientes» que excluye replies, retweets y quotes, apagada por estado inicial
- [x] 5.7 Recalcular todas las gráficas en el cliente al cambiar cualquier control, sin volver a ejecutar Python

## 6. Gráficas

- [x] 6.1 Serie diaria apilada por nivel, una por criterio, generada en un bucle sobre la rúbrica sin que N aparezca fijo
- [x] 6.1b Gráfica de volumen diario del corpus apilada por idioma, como primer panel de la página
- [x] 6.1c Ordenar los paneles por criterio según el orden de la rúbrica, nunca por magnitud de la diferencia entre períodos
- [x] 6.2 Marcar los tres períodos sobre el eje temporal de cada serie diaria, nombrados
- [x] 6.3 Representar los días sin datos como ausencia, no como cero
- [x] 6.4 Aplicar la media móvil sobre la serie mostrada sin alterar el agregado subyacente
- [x] 6.5 Distribución global de niveles por criterio, en barras apiladas con un renglón por criterio
- [x] 6.6 Distribución por período, los tres lado a lado, con la misma escala y el mismo orden de niveles
- [x] 6.7 Imprimir el n de cada período junto a su panel
- [x] 6.8 Mostrar la proporción de no aplicables y de fallidas como información separada de los niveles

## 7. Doble salida

- [x] 7.1 Construir el documento HTML una sola vez y usarlo para ambos destinos
- [x] 7.2 Mostrar las gráficas dentro de la salida de la celda con `IPython.display.HTML`
- [x] 7.3 Escribir el archivo HTML autocontenido en la ruta configurada
- [x] 7.4 Ofrecer la descarga desde Colab y escribir también en Drive cuando esté configurado
- [x] 7.5 Documentar en la celda que las gráficas dejan de ser interactivas al reabrir el notebook guardado, y que el archivo es el artefacto que sobrevive

## 8. Validación

- [x] 8.1 Confirmar que ninguna celda existente del notebook fue modificada
- [x] 8.2 Verificar que un tweet del 2026-06-11 cae en `DURANTE MUNDIAL EN MEXICO` y no en `PREVIO A MUNDIAL`
- [x] 8.2b Verificar que un tuit de las 01:00 UTC del 2026-06-11 se agrupa en el 2026-06-10 por la conversión a hora de México
- [x] 8.3 Verificar que cambiar las fechas de corte en `CONFIG` y reejecutar actualiza todas las gráficas por período
- [x] 8.4 Verificar que la proporción de un criterio se calcula sobre las calificaciones `OK` y no sobre el total
- [x] 8.4b Verificar que el nivel `0` no aparece en ninguna serie ni en ninguna barra apilada
- [ ] 8.5 Abrir el HTML generado fuera del notebook y confirmar que el filtro de idioma y el conmutador de modo funcionan
- [x] 8.6 Probar el filtro con una selección de baja densidad y confirmar que aparece la advertencia
- [x] 8.6b Verificar que la casilla de autosuficiencia reduce los conteos y que apagarla los restituye
- [ ] 8.7 Probar con una rúbrica de distinto número de criterios y confirmar que no hay que tocar código
- [x] 8.8 Dejar escrita junto a las gráficas la limitación de que el corpus no es una muestra aleatoria de la conversación y que la coincidencia temporal no implica causalidad
