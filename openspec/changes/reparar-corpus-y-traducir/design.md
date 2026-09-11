## Context

El notebook `evaluador_tweets_rubrica.ipynb` está construido y funciona (49/56 tareas del change `evaluador-tweets-rubrica-colab`). Su celda 9 carga un corpus, la 10 lo submuestrea, la 11 arma el payload y las 12-19 califican contra la rúbrica. La celda 11 ya consume `COL_TRADUCCION` de forma condicional; `CONFIG` ya declara la constante. El enganche existe y no hay que tocarlo.

Lo que cambió es el corpus. `20260910 turistas_seleccionados` (2,562 tweets sobre turistas) reemplaza a `Queries Lugares - TotalQueries.csv` y llegó dañado. El perfilado midió cuatro daños independientes, todos introducidos en la exportación, y determinó que `raw_json` sobrevivió íntegro en las 2,562 filas del `.xlsx`.

Hay además un antecedente de convención: en el corpus anterior, las 626 filas `lang=es` con traducción tienen la traducción **idéntica al original carácter por carácter**. La columna nunca significó "traducción", significó "el texto en español". Este diseño la respeta.

Restricción de fondo: el notebook corre en Colab, se desconecta, y todo lo que dure más de unos minutos tiene que ser reanudable.

## Goals / Non-Goals

**Goals:**

- Recuperar el corpus sin pérdida, con los identificadores reales de 19 dígitos y el texto íntegro en todos los idiomas.
- Llenar la columna `traducción` del corpus completo, una sola vez, y persistirla para que ninguna corrida futura la vuelva a pagar.
- No modificar ninguna celda existente del notebook. Las dos celdas nuevas se insertan antes de §3.
- Que ambos pasos sean idempotentes y se salten solos cuando su salida ya existe.

**Non-Goals:**

- Mejorar la calidad de la calificación. La traducción es para consumo humano; el objeto evaluado sigue siendo el texto original, por la regla 5 de `instruccion_para()`.
- Medir si la traducción cambia el juicio del modelo. Es un experimento válido con el instrumento de §6.3, pero es otro change.
- Reparar el `.csv` dañado. Se regenera desde el `.xlsx`.
- Generalizar la reparación a cualquier corpus roto. Se resuelve este daño concreto, medido, con una salida verificable.

## Decisions

### 1. raw_json como fuente, no las columnas planas

**Alternativa considerada**: reparar las columnas planas in situ, campo por campo.

Se descartó porque tres de los cuatro daños son irreversibles a nivel de columna. Un `id` redondeado por `float64` no se puede "des-redondear"; un texto cortado a 255 caracteres no se puede completar; un salto de línea perdido no se puede inferir. Solo el mojibake es reversible en la columna. `raw_json` no sufrió ninguno de los tres: trae el id como cadena, el texto sin truncar y los saltos intactos.

El hallazgo que inclina la balanza es `_author`: está presente en las 2,562 filas y contiene `id`, `username`, `name`, `description`, `location`, `created_at`, `url`, `verified`, `profile_image_url` y `public_metrics`. Con eso, **todas** las columnas `author_*` también salen del JSON. Solo seis campos dependen de la versión plana, y ninguno de los seis está dañado.

La celda de reparación deja de ser un parche y pasa a ser un lector propio: arma el DataFrame desde el JSON y le pega los seis campos de procedencia.

### 2. El .xlsx es la fuente; el .csv se rechaza

Medido: los dos archivos son la misma exportación fila por fila — mismas 50 columnas en el mismo orden, y `created_at`, `author_username`, `base` y `window_label` coinciden por posición en 2,562/2,562. El `.csv` no aporta nada.

Y su `raw_json` **también** está dañado: 1,257 de 2,562 difieren del `raw_json` del `.xlsx`, y 1,241 de esos traen `?`. Esa sustitución es una pérdida de información, no una transformación.

El rechazo debe ser explícito porque `_leer_tabla` prueba `utf-8`, `utf-8-sig`, `cp1252` y `latin-1` en ese orden, y **`latin-1` nunca falla**: mapea los 256 bytes. Hoy el notebook cargaría el CSV destruido con una advertencia suave sobre acentos y seguiría adelante. Es exactamente el modo de falla silenciosa que hay que cerrar.

### 3. Inversión del mojibake con un mapa byte a byte

**Alternativa considerada**: codificar a cp1252 y decodificar como UTF-8 en un paso, o la biblioteca `ftfy`.

El camino directo falla: el texto mezcla caracteres cp1252 legítimos con puntos de código del rango C1 que cp1252 no define (`\x81`, `\x8d`, `\x9d`) y que el decodificador original dejó pasar crudos. Python se niega a codificarlos.

`ftfy` resolvería el caso, pero agrega una dependencia al notebook por una función de treinta líneas.

La solución es construir el mapa inverso de cp1252 y completarlo con latin-1 para los huecos:

```
INV[c] = byte     si cp1252 define ese byte como c
INV[c] = ord(c)   en cualquier otro caso   ← cubre el rango C1
```

Verificado sobre el corpus: 2,562 de 2,562 reparables cuando se aplica sobre `raw_json.text`. Sobre la columna plana fallaban 6, todas por el truncamiento a 255 que cortaba una secuencia multibyte a la mitad — al tomar el texto del JSON, el problema desaparece.

### 4. Traducción con llamada directa, no con un agente de ADK

El notebook está construido sobre `LlmAgent` + `output_schema` + `ejecutar_agente()`, y un agente traductor heredaría gratis `RETRY_OPTIONS` y el reciclaje de runner. Aun así se elige la llamada directa: el `ParallelAgent` no aporta nada aquí — ese eje paraleliza criterios sobre un tweet, y traducir es una sola tarea por tweet — y montar sesión, runner y estado para una llamada de un turno es andamiaje sin contrapartida.

El costo de la decisión es que hay que reimplementar lo que `correr()` ya tiene. Se reimplementa lo mínimo: semáforo de `asyncio`, reintentos ante 429 y 5xx, y anexado a JSONL. La salida estructurada se pide con `response_schema` en `GenerateContentConfig`, que es el equivalente directo de `output_schema`.

### 5. Por fila, no en lotes

Medido sobre el largo real del corpus (media 126 caracteres, máximo 447):

| | llamadas | costo | riesgo |
|---|---|---|---|
| 1 tweet por llamada | 2,562 | $0.18 | ninguno |
| 20 tweets por llamada | 129 | $0.13 | desalineación, un tweet envenena su lote, checkpoint grueso |

Cinco centavos no pagan el riesgo de desalineación ni la pérdida de granularidad del checkpoint.

### 6. El modelo decide si el texto ya está en español

**Alternativa considerada**: decidirlo con `lang == "es"`.

`lang` no es confiable en este corpus: 64 filas dicen `qme`, 21 `und`, 8 `zxx`, y en el corpus anterior 2,268 filas tenían `lang` vacío siendo inglés evidente. Solo 12 filas de las 2,562 declaran `es`, así que la ruta de copia verbatim es marginal y no justifica optimizarla con una heurística frágil.

El esquema de respuesta lleva tres campos:

```
idioma_detectado   : str    ← contrastable contra lang, gratis
ya_esta_en_espanol : bool   ← decide copia verbatim
traduccion         : str
```

Cuando `ya_esta_en_espanol` es verdadero, la columna recibe **una copia del texto original desde el DataFrame**, no el campo `traduccion` devuelto por el modelo. Así la copia es exacta por construcción y no depende de que el modelo no haya alterado nada.

### 7. Corpus completo, no la muestra

La traducción no depende de la rúbrica ni del modelo de calificación: es una propiedad del corpus. Traducir `SUB` obligaría a retraducir con cada semilla de muestreo distinta, y además `SUB` es una copia (`.sample()` seguido de `reset_index`), de modo que escribir ahí dejaría la columna vacía en el CSV exportado — la celda 24 hace `ancho = df_original.copy()`. Traducir `DF` entero antes del submuestreo evita las dos cosas.

### 8. Checkpoint separado

`checkpoint.jsonl` está indexado por `(tweet_id, slug)` y sus consumidores — `cargar_resultados()`, `distribucion()`, el merge de §7 — iteran sobre `CRITERIOS`. Meter traducciones ahí con un pseudo-slug obligaría a filtrarlas en cada uno. Un `checkpoint_traduccion.jsonl` aparte sigue el patrón que `CKPT_RETEST` y `CKPT_CALIB` ya establecieron.

### 9. text_completo se conserva

En este archivo `text` y `text_completo` son idénticas en las 2,562 filas: la columna "completo" no completa nada. Aun así se conserva y se rellena con el texto bueno, porque `CONFIG` apunta `COL_TEXTO = "text_completo"` y cambiarlo tocaría una celda existente sin ganar nada.

## Risks / Trade-offs

**Los seis campos de procedencia no son verificables** (`base`, `query_utilizado`, `corpus_type`, `window_label`, `is_retweet`, `is_quote`) → No tienen contraparte en `raw_json`. Están medidos sin mojibake y sin truncamiento, y `is_retweet` / `is_quote` son derivables de `referenced_tweets` si alguna vez se duda de ellos.

**La reparación podría introducir un daño nuevo** → El reporte obligatorio de la salida (identificadores corregidos, textos destruncados, mojibake reparado, irreparables) es el control. Además se verifica que el conteo de filas y de identificadores únicos siga siendo 2,562.

**La traducción literal producirá texto ofensivo** → Es deliberado: suavizar el registro destruiría la señal que una rúbrica de percepción de destino quiere medir. Riesgo real: el modelo puede negarse a traducir contenido muy cargado. Esas filas quedan marcadas como fallidas y se cuentan en el reporte, en vez de quedar con una traducción sanitizada que aparente ser buena.

**El modelo puede alterar los @handles o los #hashtags** → Muestreo de verificación tras la corrida, comparando los tokens `@`, `#` y `http` del original y de la traducción. Es una comprobación determinista y barata.

**La llamada directa pierde lo que `correr()` ya resolvió** → Se acepta a cambio de menos andamiaje, con semáforo, reintentos y checkpoint propios. A 2,562 filas la superficie de riesgo es chica.

**Dependencia nueva sin declarar** → `pandas.read_excel` requiere `openpyxl`, que no está en la celda 1 de instalación. Hay que agregarlo o la primera ejecución en un Colab limpio falla.

**El .csv dañado sigue en el directorio** → Mientras exista, alguien lo va a volver a cargar. El rechazo explícito de la celda de reparación es la defensa; borrarlo es decisión del usuario y no la toma este diseño.

## Migration Plan

1. Insertar la celda de reparación antes de la celda 9 y la de traducción justo después.
2. Agregar a `CONFIG` los parámetros de ambos pasos y `openpyxl` a la celda 1.
3. Correr la reparación y revisar el reporte contra el inventario de daño del `proposal.md`.
4. Correr la traducción sobre las 2,562 filas (≈ $0.18) y verificar los tokens preservados sobre una muestra.
5. Apuntar `CSV_PATH` al archivo traducido y seguir con el pipeline existente sin cambios.

Vuelta atrás: ambos pasos solo escriben archivos nuevos. El `.xlsx` de entrada no se toca, y borrar las salidas devuelve el proyecto al estado previo.

## Open Questions

- ¿El `.csv` dañado se borra del directorio, o se conserva junto al reparado con el rechazo explícito como única defensa?
- Las 12 filas `lang=es`: si el modelo determina que alguna **no** está en español pese a la etiqueta, ¿se traduce o se respeta la etiqueta? El diseño actual traduce; conviene revisarlas a mano, son doce.
- ¿Conviene emitir un `lang_detectado` como columna nueva? El dato sale gratis del esquema de respuesta y permitiría medir cuánto miente `lang`, pero agrega una columna 51 que el corpus original no tenía.
