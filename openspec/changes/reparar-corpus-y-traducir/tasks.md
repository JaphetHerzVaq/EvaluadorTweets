## 1. Preparación

- [x] 1.1 Agregar `openpyxl` a la celda 1 de instalación del notebook
- [x] 1.2 Agregar a `CONFIG` los parámetros de reparación: ruta del XLSX de entrada, ruta del corpus reparado y bandera para forzar la reparación aunque la salida exista
- [x] 1.3 Agregar a `CONFIG` los parámetros de traducción: modelo, ruta del corpus traducido, ruta del checkpoint, concurrencia y bandera de retraducción de lo existente
- [x] 1.4 Apuntar `CSV_PATH` al corpus traducido, dejando `COL_TEXTO` y `COL_TRADUCCION` como están

## 2. Reparación · lectura y rechazo de fuentes

- [x] 2.1 Función que lee el XLSX de entrada con `dtype=str` y `keep_default_na=False`, sin tocar las columnas planas todavía
- [x] 2.2 Rechazar explícitamente el `.csv` de `turistas_seleccionados` con un mensaje que explique la pérdida irreversible y remita al `.xlsx`
- [x] 2.3 Detección genérica de pérdida irreversible: contar filas cuyo `raw_json` contenga `?` donde se esperaba texto no latino, y abortar reportando el total
- [x] 2.4 Abortar sin emitir archivo parcial si algún `raw_json` no parsea o no declara `id`, informando el número de fila

## 3. Reparación · inversión del mojibake

- [x] 3.1 Construir el mapa inverso de cp1252 completado con latin-1 para las posiciones que cp1252 no define
- [x] 3.2 Función `reparar(texto)` que devuelve el texto reconstruido, o el valor crudo cuando la secuencia de bytes no decodifica como UTF-8
- [x] 3.3 Saltar la conversión cuando el campo es ASCII puro
- [x] 3.4 Verificar sobre el corpus que la reparación de `raw_json.text` funciona en las 2,562 filas
- [x] 3.5 Verificar los casos concretos: japonés de la fila 742, comillas tipográficas de la fila 148 y emojis de la fila 2276

## 4. Reparación · reconstrucción desde raw_json

- [x] 4.1 Extraer de `raw_json` los campos de primer nivel: `id`, `author_id`, `conversation_id`, `in_reply_to_user_id`, `created_at`, `lang`, `text`, `possibly_sensitive`, `reply_settings`
- [x] 4.2 Extraer los campos estructurados como texto serializado: `entities`, `context_annotations`, `referenced_tweets`, `geo`
- [x] 4.3 Derivar de `public_metrics` las columnas `like_count`, `retweet_count`, `reply_count`, `quote_count`, `impression_count` y `bookmark_count`
- [x] 4.4 Derivar de `_author` todas las columnas `author_*`, incluidos los contadores de autor
- [x] 4.5 Derivar de `_place` las columnas `place_*` en las filas que la traigan, dejando vacías las demás
- [x] 4.6 Rellenar `text_completo` con el mismo texto reconstruido que `text`
- [x] 4.7 Pegar desde las columnas planas los seis campos de procedencia: `base`, `query_utilizado`, `corpus_type`, `window_label`, `is_retweet`, `is_quote`
- [x] 4.8 Conservar vacías las columnas que lo están en todo el corpus: `origen`, `source`, `withheld`, `place_geo`, `place_contained_within`, `tipo`, `justificacion`
- [x] 4.9 Emitir el DataFrame con las 50 columnas originales en su orden original
- [x] 4.10 Aplicar la reparación de mojibake a todo campo de texto después de extraerlo

## 5. Reparación · salida y verificación

- [x] 5.1 Escribir el corpus reparado en UTF-8 con marca de orden de bytes
- [x] 5.2 Reportar cuántos identificadores se corrigieron, cuántos textos se destruncaron, cuántos recuperaron saltos de línea, cuántos campos se repararon de mojibake y cuántos quedaron irreparables
- [x] 5.3 Verificar que la salida tenga 2,562 filas y 2,562 identificadores únicos de 19 dígitos
- [x] 5.4 Contrastar el reporte contra el inventario de daño del `proposal.md`: 2,562 ids, 99 truncados, 458 con saltos de línea, 935 con mojibake en el texto
- [x] 5.5 Saltar la reparación e informarlo cuando el archivo reparado ya exista y su conteo de filas coincida con el de la entrada

## 6. Traducción · esquema e instrucción

- [x] 6.1 Definir el esquema de respuesta con `idioma_detectado`, `ya_esta_en_espanol` y `traduccion`
- [x] 6.2 Escribir la instrucción de traducción literal: conservar registro y vulgaridad, no resumir, no adaptar, no censurar, no completar
- [x] 6.3 Instruir que se conserven idénticos los `@handles`, los `#hashtags`, las URL, los emojis y los saltos de línea
- [x] 6.4 Instruir que devuelva el contenido tal cual cuando no haya nada que traducir
- [x] 6.5 Construir la llamada directa a `google-genai` con `response_schema` en `GenerateContentConfig`

## 7. Traducción · motor de corrida

- [x] 7.1 Seleccionar las filas a traducir: texto no vacío y columna de traducción vacía, salvo que la retraducción esté activada
- [x] 7.2 Crear la columna de traducción si el corpus no la trae
- [x] 7.3 Pool `asyncio` con semáforo de concurrencia configurable
- [x] 7.4 Reintentos ante respuestas 429 y 5xx con espera exponencial
- [x] 7.5 Anexar cada resultado a `checkpoint_traduccion.jsonl` en cuanto se obtiene, con el identificador real del tweet
- [x] 7.6 Saltar al arranque las filas ya presentes en el checkpoint
- [x] 7.7 Copiar verbatim el texto original desde el DataFrame cuando `ya_esta_en_espanol` sea verdadero, sin usar el campo `traduccion` devuelto por el modelo
- [x] 7.8 Dejar sin traducción y marcar como fallidas las filas que agoten los reintentos, continuando con el resto
- [x] 7.9 Informar cuántas filas se van a traducir y el costo estimado antes de emitir la primera llamada
- [x] 7.10 Reportar al terminar: traducidas, copiadas verbatim, fallidas y saltadas por checkpoint

## 8. Traducción · salida y verificación

- [x] 8.1 Escribir el corpus traducido en UTF-8 con marca de orden de bytes
- [x] 8.2 Verificar sobre una muestra que los tokens `@`, `#` y `http` del original aparecen idénticos en la traducción
- [x] 8.3 Contrastar `idioma_detectado` contra la columna `lang` y reportar la tasa de desacuerdo, en particular sobre las filas `qme`, `und` y `zxx`
- [ ] 8.4 Revisar a mano las 12 filas `lang=es` y confirmar que quedaron como copia verbatim
- [x] 8.5 Revisar a mano una muestra de tweets en japonés y verificar que la traducción corresponde al texto reparado
- [x] 8.6 Saltar la traducción e informarlo cuando el corpus traducido ya exista y no queden filas pendientes

## 9. Validación de punta a punta

- [x] 9.1 Confirmar que las celdas existentes del notebook no se modificaron
- [ ] 9.2 Correr el notebook desde la carga del corpus traducido hasta la prueba de humo y verificar que el payload incluye el bloque de traducción de apoyo
- [ ] 9.3 Verificar que el CSV ancho exportado conserva la columna `traducción` llena en las 2,562 filas
- [ ] 9.4 Verificar que el conteo de filas del CSV enriquecido sigue coincidiendo con el corpus, con los identificadores reales como llave
- [ ] 9.5 Abrir el corpus traducido en una hoja de cálculo y confirmar que el japonés, los acentos y los emojis se ven correctamente
- [ ] 9.6 Comprobar que ambas celdas nuevas se saltan solas al reejecutarlas con las salidas ya presentes
