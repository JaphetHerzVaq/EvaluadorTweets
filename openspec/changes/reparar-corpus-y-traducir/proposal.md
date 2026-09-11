## Why

El archivo `20260910 turistas_seleccionados` (2,562 tweets sobre turistas) llegó con daño en cuatro frentes independientes, todos introducidos al exportarlo: mojibake por leer UTF-8 como cp1252, identificadores de 19 dígitos redondeados por `float64`, 99 textos truncados a 255 caracteres y 458 textos con los saltos de línea colapsados. Calificar este corpus contra la rúbrica produciría resultados sin sentido para las 417 filas en japonés y un checkpoint no reanudable, porque `tweet_id` sería inventado en las 2,562 filas.

Además, el corpus no trae la columna `traducción` que `CONFIG` ya declara (`COL_TRADUCCION`), por lo que los 2,006 tweets en inglés y los 417 en japonés quedan ilegibles para quien deba revisar justificaciones, anotar el gold set de §6.5 o analizar el CSV final.

## What Changes

- **Reconstrucción del corpus desde `raw_json`, no desde las columnas planas.** `raw_json` sobrevivió íntegro en las 2,562 filas y contiene el identificador real, el texto sin truncar y una clave `_author` con todos los campos de autor. Las columnas planas pasan a ser un derivado degradado que se descarta, salvo seis campos de procedencia que no viajan en el JSON.
- **Reparación del mojibake** con la inversión byte a byte de cp1252 (con respaldo latin-1 para los huecos C1 no definidos), aplicada a todo campo de texto tras extraerlo del JSON. Verificado: recupera 2,562 de 2,562.
- **El XLSX es la fuente, no el CSV. BREAKING** respecto de lo acordado antes: el `.csv` sufrió una segunda ronda de daño que sustituyó por `?` los caracteres no representables, incluido dentro de su propio `raw_json` (1,241 filas afectadas). Esa pérdida es irreversible. Como ambos archivos son la misma exportación fila por fila, el CSV bueno se **regenera** desde el XLSX reparado.
- **Nueva celda de traducción** en el notebook: una llamada directa a `google-genai` por fila, sin agente de ADK, que llena la columna `traducción` para el corpus completo una sola vez y la persiste, en lugar de retraducir en cada corrida.
- **Traducción literal, no adaptada**: conserva registro, vulgaridad, emojis, `@handles` y `#hashtags`. En una rúbrica de percepción de destino, suavizar el registro destruye la señal que se quiere medir.
- **Español copiado verbatim**: cuando el tweet ya está en español la columna recibe una copia exacta del texto original, sin llamar al modelo. Es la convención que ya usaba el corpus anterior (`Queries Lugares - TotalQueries.csv`), donde las 626 filas `lang=es` con traducción son idénticas al original carácter por carácter. La decisión la toma el modelo, no la columna `lang`, porque `lang` es poco confiable: trae 64 filas `qme`, 21 `und` y 8 `zxx`.
- **Respeto de traducciones preexistentes**: solo se traducen las filas con la columna vacía. En este archivo son las 2,562, pero la regla deja el paso reutilizable sobre corpus parcialmente traducidos.
- **Checkpoint propio y reanudable** (`checkpoint_traduccion.jsonl`), separado de `checkpoint.jsonl`, que está indexado por `(tweet_id, slug)` y cuyos consumidores iteran sobre `CRITERIOS`.
- **NO se modifica el pipeline de calificación.** La celda 11 ya consume `COL_TRADUCCION` de forma condicional y la regla 5 de `instruccion_para()` ordena evaluar en el idioma original. La traducción entra como apoyo, igual que antes; su propósito aquí es consumo humano y homogeneidad del payload.
- **NO se traduce con lotes de varios tweets por llamada.** Medido sobre el largo real, el lote ahorra ~28% de un costo total de $0.18 USD, a cambio de riesgo de desalineación y granularidad de checkpoint más gruesa.

## Capabilities

### New Capabilities

- `corpus-repair`: Reconstruir un corpus de tweets exportado con daño, tomando `raw_json` como fuente de verdad para identificadores, texto y metadatos de autor; reparar el mojibake de codificación; conservar los campos de procedencia que no viajan en el JSON; y emitir un archivo íntegro en UTF-8 con reporte de qué se reparó y cuánto.
- `tweet-translation`: Llenar una columna de traducción al español para consumo humano sobre el corpus completo, traduciendo literalmente sin adaptar el registro, copiando verbatim los textos que ya están en español, respetando las traducciones preexistentes y persistiendo el resultado de forma reanudable.

### Modified Capabilities

Ninguna. `openspec/specs/` está vacío: el change `evaluador-tweets-rubrica-colab` aún no se archiva, y ninguno de los requisitos que declara cambia aquí. En particular `tweet-corpus-loading` ya contempla "texto original más traducción cuando exista"; este cambio hace que exista, no altera el comportamiento.

## Impact

**Notebook**: `evaluador_tweets_rubrica.ipynb` gana dos celdas nuevas antes de la carga del corpus (§3), y `CONFIG` gana los parámetros de ambos pasos. Las celdas existentes no se modifican.

**Datos de entrada**: `20260910 turistas_seleccionados.xlsx` (2,562 × 50) se lee sin modificarse. `20260910 turistas_seleccionados.csv` queda marcado como no utilizable; el notebook debe rechazarlo explícitamente en vez de aceptarlo, porque el respaldo `latin-1` de `_leer_tabla` nunca falla y hoy lo cargaría con solo una advertencia suave.

**Datos de salida**: dos archivos nuevos, `turistas_reparado.csv` y `turistas_traducido.csv`, ambos UTF-8 con BOM.

**Inventario de daño medido** (XLSX, 2,562 filas):

| Daño | Alcance | Recuperable |
|---|---|---|
| Mojibake UTF-8→cp1252 | 935 en `text`, 444 en `author_description`, 408 en `author_location`, 319 en `author_name` | Sí, 2,562/2,562 |
| Identificadores por `float64` | `id` y `conversation_id` al 100%; `author_id` en 1,174; `in_reply_to_user_id` en 1,302 | Sí, desde `raw_json` |
| Texto truncado a 255 caracteres | 99 filas | Sí, desde `raw_json` |
| Saltos de línea colapsados | 458 en `text`, ~352 en `author_description` | Sí, desde `raw_json` |
| Sustitución por `?` e ids a 6 cifras | Solo el `.csv` (1,241 filas) | **No** |

**Configuración**: `CSV_PATH` pasa a apuntar al archivo reparado. `COL_TEXTO` sigue siendo `text_completo`, que se conserva y se rellena con el texto bueno, aunque en este archivo sea idéntica a `text` en las 2,562 filas.

**Costo**: 2,562 llamadas de traducción con `gemini-2.5-flash-lite`, aproximadamente **$0.18 USD**, pagados una sola vez. La reparación no usa modelo y no cuesta nada.

**Dependencias**: `openpyxl` para leer el XLSX, que `pandas.read_excel` ya requiere y no está en la celda de instalación del notebook.

**Riesgo abierto**: las seis columnas que solo existen en la versión plana (`base`, `query_utilizado`, `corpus_type`, `window_label`, `is_retweet`, `is_quote`) no tienen contraparte en `raw_json` con la cual verificarse. Están medidas como sin mojibake y sin truncamiento, pero se conservan a fe del archivo.
