## ADDED Requirements

### Requirement: CSV original enriquecido con columnas por criterio

El sistema SHALL producir un CSV que preserve todas las columnas y filas del archivo original y añada, por cada criterio de la rúbrica, una columna de nivel, una de justificación y una de aplicabilidad, más una columna de puntaje cuando la rúbrica define escala numérica. Los nombres de las columnas añadidas MUST derivarse del identificador de cada criterio.

#### Scenario: Columnas generadas según la rúbrica
- **WHEN** se exporta el resultado de una corrida con una rúbrica de N criterios
- **THEN** el CSV contiene las 52 columnas originales más las columnas de calificación correspondientes a esos N criterios

#### Scenario: Rúbrica de escala nominal
- **WHEN** la rúbrica no define valores numéricos para sus niveles
- **THEN** las columnas de puntaje se omiten y las de nivel contienen la etiqueta nominal

#### Scenario: Columnas originales intactas
- **WHEN** se genera el CSV enriquecido
- **THEN** las columnas originales conservan sus valores sin modificación, incluidas `tipo` y `justificacion`, que permanecen vacías

#### Scenario: Filas no evaluadas
- **WHEN** el subconjunto evaluado es menor que el corpus completo
- **THEN** las filas no evaluadas se conservan en el CSV con las columnas de calificación vacías, distinguibles de una calificación fallida

### Requirement: Salida tidy para análisis

El sistema SHALL producir además un CSV en formato largo con una fila por combinación de tweet y criterio, conteniendo el identificador del tweet, el identificador del criterio, el nivel, el puntaje cuando aplique, la aplicabilidad y la justificación.

#### Scenario: Formato largo generado
- **WHEN** se exportan los resultados
- **THEN** el archivo tidy contiene una fila por cada par de tweet y criterio evaluado

#### Scenario: Trazabilidad al criterio
- **WHEN** se inspecciona una fila del archivo tidy
- **THEN** el criterio evaluado es identificable y corresponde a un criterio de la rúbrica cargada

### Requirement: Integridad del merge con el corpus original

El sistema SHALL unir los resultados al corpus original por el identificador del tweet y MUST verificar que el número de filas del CSV enriquecido sea idéntico al del original, fallando si no lo es.

#### Scenario: Conteo de filas preservado
- **WHEN** el merge termina
- **THEN** el CSV enriquecido tiene exactamente el mismo número de filas que el original

#### Scenario: Duplicación detectada
- **WHEN** el merge produciría filas duplicadas
- **THEN** el sistema falla reportando los identificadores involucrados, en lugar de exportar un archivo inconsistente

#### Scenario: Resultado sin fila correspondiente
- **WHEN** el checkpoint contiene un resultado cuyo identificador de tweet no existe en el corpus original
- **THEN** el sistema lo reporta y no lo incorpora silenciosamente

### Requirement: Codificación segura para hojas de cálculo

Los archivos exportados SHALL escribirse en UTF-8 con marca de orden de bytes, de modo que los acentos y caracteres no latinos se muestren correctamente al abrirlos en una hoja de cálculo.

#### Scenario: Justificaciones con acentos
- **WHEN** se abre el CSV enriquecido en una hoja de cálculo
- **THEN** los acentos de las justificaciones en español se muestran correctamente

#### Scenario: Texto original no latino preservado
- **WHEN** el CSV contiene tweets en japonés o coreano
- **THEN** esos caracteres se conservan legibles en el archivo exportado

### Requirement: Entrega descargable desde Colab

El sistema SHALL ofrecer los archivos generados para descarga directa desde Colab y MUST permitir además escribirlos en Google Drive cuando esté montado.

#### Scenario: Descarga directa
- **WHEN** el usuario ejecuta la celda de descarga
- **THEN** el navegador recibe el CSV enriquecido y el archivo tidy

#### Scenario: Escritura en Drive
- **WHEN** Drive está montado y el usuario indica una ruta de destino
- **THEN** los archivos se escriben en esa ruta y el sistema confirma las rutas resultantes

#### Scenario: Resumen de la exportación
- **WHEN** la exportación termina
- **THEN** el sistema reporta las rutas generadas, el número de filas y el número de columnas añadidas
