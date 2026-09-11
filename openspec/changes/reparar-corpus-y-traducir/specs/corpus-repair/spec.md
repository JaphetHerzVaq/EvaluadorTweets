## ADDED Requirements

### Requirement: raw_json como fuente de verdad
El sistema SHALL reconstruir cada fila del corpus a partir del contenido de la columna `raw_json`, y NO a partir de las columnas planas, para todo campo que el JSON contenga: `id`, `author_id`, `conversation_id`, `in_reply_to_user_id`, `created_at`, `lang`, `text`, `entities`, `context_annotations`, `referenced_tweets`, `geo`, `possibly_sensitive`, `reply_settings`, las métricas de `public_metrics` y los campos anidados bajo `_author` y `_place`.

#### Scenario: Identificador redondeado por punto flotante
- **WHEN** la columna `id` de una fila vale `2062323406914350080` y su `raw_json` declara `"id": "2062323406914351181"`
- **THEN** la fila reconstruida SHALL tener `id = "2062323406914351181"` como cadena de 19 dígitos

#### Scenario: Texto truncado en la columna plana
- **WHEN** `text_completo` mide exactamente 255 caracteres y `raw_json.text` mide 296
- **THEN** el texto reconstruido SHALL ser el de `raw_json.text`, de 296 caracteres

#### Scenario: Saltos de línea colapsados
- **WHEN** `raw_json.text` contiene saltos de línea que la columna plana perdió
- **THEN** el texto reconstruido SHALL conservar los saltos de línea del JSON

#### Scenario: Campos de autor
- **WHEN** se reconstruye una fila cuyo `raw_json` trae la clave `_author`
- **THEN** las columnas `author_username`, `author_name`, `author_description`, `author_location`, `author_created_at`, `author_verified`, `author_url`, `author_profile_image_url` y los contadores de autor SHALL derivarse de `_author`

#### Scenario: raw_json ilegible
- **WHEN** el `raw_json` de una fila no parsea como JSON o no declara `id`
- **THEN** el sistema SHALL abortar la reparación e informar el número de fila, sin emitir un archivo parcial

### Requirement: Reparación del mojibake de codificación
El sistema SHALL revertir el daño producido por haber leído UTF-8 como cp1252, mapeando cada carácter a su byte original mediante la inversa de cp1252 y recurriendo a latin-1 para las posiciones que cp1252 no define, y SHALL aplicar esa reparación a todo campo de texto después de extraerlo del JSON.

#### Scenario: Texto en japonés dañado
- **WHEN** el campo contiene `#ãƒ™ã‚¤ãƒ“ãƒ¼ã‚¯ãƒ©ãƒ–ã‚·ã‚¢ã‚¿ãƒ¼`
- **THEN** el campo reparado SHALL contener `#ベイビークラブシアター`

#### Scenario: Texto que no necesita reparación
- **WHEN** el campo es ASCII puro
- **THEN** el campo SHALL quedar idéntico, sin pasar por la conversión

#### Scenario: Comillas tipográficas y emojis
- **WHEN** el campo contiene `arenâ€™t` o `ðŸ¥¹ðŸŒ®`
- **THEN** el campo reparado SHALL contener `aren’t` y `🥹🌮`

#### Scenario: Campo irreparable
- **WHEN** la conversión de un campo falla porque la secuencia de bytes no decodifica como UTF-8
- **THEN** el sistema SHALL conservar el valor crudo, marcar la fila en el reporte y continuar, sin abortar la reparación

### Requirement: Conservación de los campos de procedencia
El sistema SHALL conservar desde las columnas planas los campos que `raw_json` no contiene: `base`, `query_utilizado`, `corpus_type`, `window_label`, `is_retweet` e `is_quote`.

#### Scenario: Campo de procedencia presente
- **WHEN** una fila tiene `base = "Query_Turistas1"` y `raw_json` no declara `base`
- **THEN** la fila reconstruida SHALL conservar `base = "Query_Turistas1"`

#### Scenario: Columna vacía en todo el corpus
- **WHEN** una columna como `origen`, `source`, `withheld`, `tipo` o `justificacion` está vacía en todas las filas
- **THEN** la columna SHALL conservarse en la salida, vacía, sin intentar derivarla del JSON

### Requirement: Rechazo de la fuente irrecuperable
El sistema SHALL leer el corpus desde el archivo `.xlsx` y SHALL rechazar explícitamente el `.csv` equivalente, cuya segunda ronda de daño sustituyó por `?` los caracteres no representables, incluido dentro de su propio `raw_json`.

#### Scenario: Se indica el CSV dañado como entrada
- **WHEN** la ruta de entrada apunta al `.csv` de `turistas_seleccionados`
- **THEN** el sistema SHALL abortar con un mensaje que explique que ese archivo tiene pérdida irreversible y que debe usarse el `.xlsx`

#### Scenario: Detección genérica de pérdida irreversible
- **WHEN** un archivo de entrada contiene `raw_json` con caracteres `?` en posiciones donde se esperaba texto no latino
- **THEN** el sistema SHALL reportar cuántas filas están afectadas antes de abortar

### Requirement: Emisión del corpus reparado con reporte
El sistema SHALL escribir el corpus reconstruido en UTF-8 con marca de orden de bytes, conservando las 50 columnas originales y su orden, y SHALL reportar cuántas filas fueron corregidas por cada tipo de daño.

#### Scenario: Reporte de reparación
- **WHEN** termina la reparación del corpus de 2,562 filas
- **THEN** el reporte SHALL indicar el número de identificadores corregidos, de textos destruncados, de textos con saltos de línea restaurados, de campos con mojibake reparado y de campos irreparables

#### Scenario: Conteo de filas preservado
- **WHEN** el archivo de entrada tiene 2,562 filas
- **THEN** el archivo reparado SHALL tener 2,562 filas y 2,562 identificadores únicos

#### Scenario: Reparación ya aplicada
- **WHEN** el archivo reparado ya existe y su conteo de filas coincide con el de la entrada
- **THEN** el sistema SHALL omitir la reparación e informarlo, en lugar de rehacerla
