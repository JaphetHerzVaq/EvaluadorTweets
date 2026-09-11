## 1. Andamiaje del notebook y autenticación

- [x] 1.1 Crear el archivo `.ipynb` con la secuencia de celdas y una celda inicial de título que explique el flujo de principio a fin
- [x] 1.2 Celda de instalación de dependencias: `google-adk`, `google-genai`, `pandas`, `nest_asyncio`
- [x] 1.3 Celda de parámetros de configuración en un solo lugar: identificador de modelo, temperatura, presupuesto de razonamiento, límite de concurrencia, tamaño de muestra, semilla, límite de palabras de la justificación, rutas de entrada y salida
- [x] 1.4 Leer la clave de Gemini desde el gestor de secretos de Colab, fallando con instrucciones accionables si no existe, sin imprimir nunca el valor
- [x] 1.5 Celda de sondeo que lista los modelos disponibles para la credencial y valida que el identificador configurado exista, fallando antes de cualquier corrida
- [x] 1.6 Resolver el conflicto de event loop de Colab para poder ejecutar ADK asíncrono dentro de una celda

## 2. Ingesta de la rúbrica

- [x] 2.1 Definir el esquema de salida estructurada de la rúbrica: criterios con identificador, nombre, consigna y lista de niveles; cada nivel con etiqueta, descriptor y puntos opcionales
- [x] 2.2 Celda de carga del PDF desde Drive montado o subida directa, rechazando archivos que no sean PDF
- [x] 2.3 Construir el agente de parseo que recibe el PDF como entrada nativa por bytes con tipo MIME `application/pdf` y devuelve la rúbrica normalizada
- [x] 2.4 Derivar identificadores de criterio estables y únicos, con desambiguación determinista ante colisiones
- [x] 2.5 Detectar si la escala es numérica o nominal y exponer la lista de valores válidos por criterio
- [x] 2.6 Materializar `rubrica.json` en disco y mostrar el resumen inspeccionable: número de criterios, niveles por criterio y tipo de escala
- [x] 2.7 Permitir recargar la rúbrica desde el JSON editado a mano sin volver a llamar al modelo
- [x] 2.8 Fallar explícitamente cuando el parseo no detecte ningún criterio

## 3. Carga del corpus y preparación del payload

- [x] 3.1 Celda de carga del CSV desde Drive o subida directa, leyendo todas las columnas como texto y reportando dimensiones
- [x] 3.2 Validar la presencia de las columnas requeridas y fallar nombrando las que falten
- [x] 3.3 Implementar la selección del subconjunto: tamaño configurable, muestreo aleatorio con semilla fija, y filtros por idioma, tipo de consulta, retweet y quote
- [x] 3.4 Construir el payload de evaluación con el texto completo del tweet más la traducción cuando exista, etiquetando ambas partes de forma distinguible
- [x] 3.5 Detectar y marcar las filas de contexto incompleto: replies, retweets y quotes, dejando la marca disponible en la salida
- [x] 3.6 Añadir al payload la advertencia explícita de contexto incompleto sólo en las filas marcadas

## 4. Agentes de calificación por criterio

- [x] 4.1 Definir el esquema de salida estructurada de una calificación: nivel, puntaje opcional, justificación y aplicabilidad
- [x] 4.2 Escribir la plantilla de instrucción por criterio, con el criterio primero y el tweet al final, incorporando la escala cerrada declarada explícitamente, la prohibición de inferir contenido ausente, la regla de justificación en español y el límite de extensión
- [x] 4.3 Construir los agentes iterando sobre los criterios de la rúbrica, sin que el número de criterios aparezca fijo en el código, y verificar que cada instrucción contenga sólo su propio criterio
- [x] 4.4 Agrupar los agentes en un `ParallelAgent` con una clave de estado propia por criterio
- [x] 4.5 Configurar el modelo con temperatura cero y razonamiento desactivado en todos los agentes
- [x] 4.6 Implementar la validación del nivel devuelto contra la escala del criterio, registrando como fallida la fila cuyo nivel quede fuera de escala
- [ ] 4.7 Prueba manual sobre un tweet: verificar que se obtienen N resultados atribuibles, que la justificación está en español y que un tweet ajeno a un criterio se marca como no aplicable en lugar de recibir el nivel más bajo

## 5. Orquestación de la corrida

- [x] 5.1 Implementar la estimación de costo a partir del número de criterios y del payload real del subconjunto, mostrando llamadas, tokens de entrada y salida y costo, desglosado por criterio y total
- [x] 5.2 Requerir confirmación explícita del usuario antes de iniciar la corrida
- [x] 5.3 Implementar el pool asíncrono con límite de concurrencia configurable y una sesión de ejecución independiente por fila
- [x] 5.4 Reciclar el runner periódicamente para no acumular sesiones en memoria durante corridas largas
- [x] 5.5 Configurar reintentos con retroceso exponencial ante límite de tasa y errores de servidor, registrando la fila como fallida con su motivo al agotarse
- [x] 5.6 Registrar las respuestas bloqueadas por filtros de seguridad con su motivo, sin confundirlas con nivel bajo ni con no aplicabilidad
- [x] 5.7 Escribir cada resultado al checkpoint JSONL por anexado, identificado por tweet y criterio, inmediatamente al obtenerlo
- [x] 5.8 Leer el checkpoint al iniciar y omitir las combinaciones ya completadas, reportando cuántos resultados se reutilizan
- [x] 5.9 Saltar directamente a la exportación cuando el checkpoint ya cubra todo el subconjunto
- [x] 5.10 Mostrar progreso durante la corrida: completadas, pendientes y fallidas
- [ ] 5.11 Prueba de reanudación: interrumpir una corrida a mitad, reejecutar la celda y verificar que continúa sin reevaluar lo hecho

## 6. Verificaciones de calidad

- [x] 6.1 Celda de distribución de niveles por criterio, incluyendo proporción de no aplicables y de fallidas
- [x] 6.2 Señalar los criterios que concentran en un solo nivel una proporción superior al umbral configurable, y los que resultan mayoritariamente no aplicables
- [x] 6.3 Celda de test-retest: reevaluar una muestra en un checkpoint separado y reportar el acuerdo de niveles por criterio, dejando intacto el checkpoint original
- [x] 6.4 Celda de acuerdo inter-modelo sobre muestra de calibración, reportando acuerdo exacto y a un nivel de distancia, y señalando los criterios de juicio inestable
- [x] 6.5 Celda de comparación contra un conjunto anotado a mano, listando los desacuerdos con ambos niveles y la justificación generada
- [x] 6.6 Advertir explícitamente cuando no se proporciona conjunto anotado que las calificaciones no tienen contraste con juicio humano

## 7. Exportación

- [x] 7.1 Generar los nombres de columna por criterio a partir de sus identificadores: nivel, justificación, aplicabilidad y puntaje cuando la escala sea numérica
- [x] 7.2 Unir los resultados al corpus original por identificador de tweet, preservando intactas las columnas originales incluidas `tipo` y `justificacion`
- [x] 7.3 Verificar que el conteo de filas del CSV enriquecido coincida con el original, fallando ante duplicación y reportando los resultados cuyo identificador no exista en el corpus
- [x] 7.4 Distinguir en la salida las filas no evaluadas de las calificaciones fallidas
- [x] 7.5 Generar el CSV tidy con una fila por tweet y criterio
- [ ] 7.6 Escribir ambos archivos en UTF-8 con marca de orden de bytes y verificar en una hoja de cálculo que los acentos y los caracteres no latinos se muestran correctamente
- [x] 7.7 Ofrecer descarga directa desde Colab y escritura en Drive, reportando rutas generadas, número de filas y número de columnas añadidas

## 8. Validación de punta a punta

- [ ] 8.1 Corrida completa sobre una muestra pequeña con una rúbrica real, revisando a mano las justificaciones obtenidas
- [ ] 8.2 Contrastar el costo real facturado contra la estimación previa y ajustar el modelo de estimación si difiere
- [ ] 8.3 Verificar que el notebook corre de principio a fin en una sesión limpia de Colab, sin estado residual
- [ ] 8.4 Comprobar que una rúbrica con un número distinto de criterios funciona sin modificar código
- [x] 8.5 Documentar en la primera celda los parámetros, el costo por criterio observado y las limitaciones conocidas, incluida la de los replies sin contexto
