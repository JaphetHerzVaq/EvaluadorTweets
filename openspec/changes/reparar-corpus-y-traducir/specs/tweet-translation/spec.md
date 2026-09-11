## ADDED Requirements

### Requirement: Traducción literal al español
El sistema SHALL traducir el texto de cada tweet al español de forma literal, conservando el registro del original —incluida la vulgaridad, la ironía y los errores ortográficos—, los emojis, los `@handles`, los `#hashtags` y las URL sin traducir, y SHALL NO resumir, adaptar, censurar ni completar el contenido.

#### Scenario: Registro vulgar
- **WHEN** el tweet original dice `Mexico people are Cunts!`
- **THEN** la traducción SHALL conservar la carga ofensiva y NO SHALL sustituirla por un eufemismo

#### Scenario: Menciones, etiquetas y enlaces
- **WHEN** el tweet contiene `@teachbk`, `#VisitMexico` o `https://t.co/lRmxSNFCxt`
- **THEN** esos tokens SHALL aparecer idénticos en la traducción

#### Scenario: Emojis y saltos de línea
- **WHEN** el tweet contiene `🥹🌮` y saltos de línea
- **THEN** la traducción SHALL conservarlos en las posiciones equivalentes

#### Scenario: Texto sin contenido lingüístico
- **WHEN** el tweet solo contiene una URL, una mención o `lang` vale `zxx`
- **THEN** el texto SHALL pasar igualmente por el modelo, que devolverá el contenido tal cual cuando no haya nada que traducir

### Requirement: Detección del español por el modelo
El sistema SHALL delegar en el modelo la decisión de si el texto ya está en español, y SHALL NO decidirlo a partir de la columna `lang`, que en este corpus declara 64 filas `qme`, 21 `und`, 8 `zxx` y valores ausentes.

#### Scenario: El tweet ya está en español
- **WHEN** el modelo determina que el texto ya está en español
- **THEN** la columna de traducción SHALL recibir una copia exacta del texto original, carácter por carácter

#### Scenario: Idioma mal declarado
- **WHEN** `lang` vale `qme`, `und` o está vacío, y el texto está en inglés
- **THEN** el texto SHALL traducirse igual, sin que el valor de `lang` altere la decisión

#### Scenario: Idioma detectado registrado
- **WHEN** el modelo traduce un tweet
- **THEN** el sistema SHALL registrar el idioma que detectó, para poder contrastarlo con `lang`

### Requirement: Cobertura del corpus completo y respeto de lo preexistente
El sistema SHALL procesar el corpus completo una sola vez, no la muestra seleccionada para calificar, y SHALL traducir únicamente las filas cuya columna de traducción esté vacía, dejando intactas las que ya traigan contenido.

#### Scenario: Columna de traducción ausente
- **WHEN** el corpus no tiene la columna de traducción
- **THEN** el sistema SHALL crearla y traducir las filas con texto no vacío

#### Scenario: Fila con traducción preexistente
- **WHEN** una fila ya trae traducción y la retraducción no está activada
- **THEN** el sistema SHALL dejarla intacta y NO SHALL gastar una llamada en ella

#### Scenario: Retraducción solicitada explícitamente
- **WHEN** la opción de retraducir lo existente está activada
- **THEN** el sistema SHALL sobrescribir todas las traducciones, para homogeneizar la procedencia

#### Scenario: Resultado persistido
- **WHEN** termina la traducción del corpus
- **THEN** el sistema SHALL escribir un archivo con la columna llena, en UTF-8 con marca de orden de bytes, para que las corridas posteriores no vuelvan a pagarla

### Requirement: Ejecución por fila, reanudable
El sistema SHALL emitir una llamada directa al modelo por fila, sin agrupar varios tweets en una misma llamada y sin construir un agente de ADK, SHALL limitar la concurrencia, SHALL reintentar ante respuestas 429 y 5xx, y SHALL anexar cada resultado a un checkpoint propio en cuanto lo obtiene.

#### Scenario: Reanudación tras una desconexión
- **WHEN** la celda se reejecuta después de una desconexión con 1,200 de 2,562 filas ya traducidas
- **THEN** el sistema SHALL traducir solo las 1,362 restantes

#### Scenario: Checkpoint separado del de calificación
- **WHEN** se escribe un resultado de traducción
- **THEN** SHALL anexarse a un archivo distinto de `checkpoint.jsonl`, que está indexado por tweet y criterio

#### Scenario: Fallo en una fila
- **WHEN** una fila agota los reintentos
- **THEN** el sistema SHALL dejarla sin traducción, marcarla como fallida y continuar con el resto, informando el total de fallidas al terminar

#### Scenario: Estimación antes de gastar
- **WHEN** se va a lanzar la traducción
- **THEN** el sistema SHALL informar cuántas filas se traducirán y el costo estimado antes de emitir la primera llamada

### Requirement: Independencia del pipeline de calificación
El sistema SHALL dejar sin modificar el comportamiento de calificación: la traducción entra al payload como apoyo opcional, el texto original sigue siendo el objeto evaluado y la instrucción por criterio sigue ordenando evaluar en el idioma original.

#### Scenario: La calificación sigue sobre el original
- **WHEN** se construye el payload de un tweet que ahora tiene traducción
- **THEN** el texto original SHALL seguir presente como el objeto evaluado y la traducción SHALL aparecer marcada como apoyo

#### Scenario: Corpus sin traducir
- **WHEN** se califica un corpus cuya columna de traducción está vacía
- **THEN** el pipeline SHALL funcionar igual que antes de este cambio
