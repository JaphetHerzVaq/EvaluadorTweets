## ADDED Requirements

### Requirement: Carga del CSV de tweets

El notebook SHALL cargar el CSV de tweets desde Google Drive montado o desde subida directa en Colab, leyendo todas las columnas como texto para no alterar identificadores numéricos largos, y MUST reportar el número de filas y columnas cargadas.

#### Scenario: Carga desde Drive
- **WHEN** el usuario indica una ruta de Drive al CSV
- **THEN** el sistema lo carga y reporta las dimensiones del dataframe resultante

#### Scenario: Identificadores preservados
- **WHEN** el CSV contiene columnas de identificadores numéricos largos como `id`, `author_id` o `conversation_id`
- **THEN** esos valores se conservan como texto sin convertirse a notación científica ni perder dígitos

#### Scenario: Columnas requeridas ausentes
- **WHEN** el CSV cargado no contiene la columna de texto del tweet
- **THEN** el sistema falla indicando qué columna falta, sin continuar

### Requirement: Selección configurable del subconjunto a evaluar

El sistema SHALL exponer un parámetro que determine cuántas filas se evalúan y MUST permitir seleccionarlas de forma aleatoria con semilla fija para reproducibilidad. El sistema SHALL permitir además filtrar por columnas del corpus, incluyendo idioma, tipo de consulta y las marcas de retweet y quote.

#### Scenario: Muestra aleatoria reproducible
- **WHEN** el usuario fija un tamaño de muestra y una semilla
- **THEN** el sistema selecciona ese número de filas y dos corridas con la misma semilla seleccionan exactamente las mismas filas

#### Scenario: Corpus completo
- **WHEN** el usuario configura el tamaño de muestra para abarcar todas las filas
- **THEN** el sistema evalúa el corpus completo sin muestrear

#### Scenario: Exclusión de retweets
- **WHEN** el usuario activa el filtro de exclusión de retweets
- **THEN** las filas marcadas como retweet quedan fuera del subconjunto y el sistema reporta cuántas se excluyeron

### Requirement: Construcción del payload de evaluación multilingüe

El sistema SHALL construir para cada fila el texto que se somete a evaluación usando el texto completo del tweet, y MUST añadir la traducción como apoyo cuando la fila la tenga disponible. El texto original MUST incluirse siempre, con independencia del idioma.

#### Scenario: Fila con traducción disponible
- **WHEN** una fila tiene el campo de traducción poblado
- **THEN** el payload contiene el texto original y la traducción, ambos etiquetados de forma distinguible

#### Scenario: Fila sin traducción
- **WHEN** una fila no tiene traducción
- **THEN** el payload contiene únicamente el texto original y no se invoca ninguna traducción automática

#### Scenario: Fila en idioma no latino
- **WHEN** una fila está en japonés, coreano u otra escritura no latina
- **THEN** el texto original se incluye sin transliterar ni normalizar

### Requirement: Marcado de contexto incompleto

El sistema SHALL identificar las filas cuyo texto no es autosuficiente —replies, retweets y quotes— y MUST incluir en el payload una advertencia explícita de contexto incompleto para esos casos, sin intentar reconstruir el hilo de conversación.

#### Scenario: Reply detectado
- **WHEN** una fila tiene poblado el campo de usuario al que responde, o su texto comienza con una mención
- **THEN** el payload incluye una advertencia de que el tweet es una respuesta cuyo contexto previo no está disponible

#### Scenario: Tweet autosuficiente
- **WHEN** una fila no es reply, retweet ni quote
- **THEN** el payload no contiene ninguna advertencia de contexto

#### Scenario: Marca disponible en la salida
- **WHEN** el subconjunto se prepara
- **THEN** la marca de contexto incompleto queda registrada por fila para poder filtrar esas filas en el análisis posterior
