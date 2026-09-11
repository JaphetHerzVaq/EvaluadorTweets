## ADDED Requirements

### Requirement: Auditoría de un checkpoint existente

El sistema SHALL ofrecer una operación que analice un checkpoint sin modificarlo y reporte su composición: número de registros, número de pares tweet-criterio distintos, desglose por estado, número de pares con registros repetidos, estado final de cada par y los diagnósticos de fallo más frecuentes. La operación MUST NOT emitir llamadas al modelo.

#### Scenario: Auditoría de un checkpoint con fallos

- **WHEN** se audita un checkpoint que contiene registros exitosos y fallidos
- **THEN** el sistema reporta cuántos pares quedan resueltos, cuántos quedan en fallo y cuáles son los diagnósticos de fallo predominantes, sin emitir llamadas

#### Scenario: Auditoría de un checkpoint con registros repetidos

- **WHEN** un mismo par tweet-criterio aparece varias veces en el checkpoint
- **THEN** el sistema lo contabiliza una sola vez en el estado final y reporta aparte cuántos pares tienen repeticiones

#### Scenario: Líneas ilegibles

- **WHEN** el checkpoint contiene líneas que no son registros válidos, por ejemplo truncadas por una interrupción
- **THEN** el sistema las omite del análisis, reporta cuántas encontró y completa la auditoría

### Requirement: La reanudación distingue un resultado de un fallo

El sistema SHALL considerar completado un par tweet-criterio únicamente cuando su registro vigente tenga un estado de resultado. Un estado de fallo MUST hacer que el par se vuelva a calificar en la siguiente corrida. La no aplicabilidad declarada por el modelo MUST considerarse un resultado, no un fallo.

#### Scenario: Reanudar sobre pares fallidos

- **WHEN** se reanuda una corrida sobre un checkpoint que contiene pares con estado de fallo
- **THEN** esos pares se incluyen en el trabajo pendiente y se vuelven a calificar

#### Scenario: Reanudar sobre pares resueltos

- **WHEN** se reanuda una corrida sobre un checkpoint cuyos pares tienen estado de resultado, incluida la no aplicabilidad
- **THEN** esos pares se omiten del trabajo pendiente y no se vuelve a pagar por ellos

#### Scenario: Reanudación sin trabajo pendiente

- **WHEN** todos los pares de la selección tienen estado de resultado en el checkpoint
- **THEN** el sistema informa que no hay nada pendiente y termina sin emitir llamadas

### Requirement: La lectura de resultados resuelve las repeticiones por último resultado válido

El sistema SHALL resolver los registros repetidos de un mismo par tweet-criterio conservando el último con estado de resultado. Cuando ningún registro del par tenga estado de resultado, el sistema MUST conservar el último registro escrito.

#### Scenario: Par que pasó de fallo a resultado

- **WHEN** un par tiene primero un registro de fallo y después uno de resultado
- **THEN** la lectura conserva el registro de resultado

#### Scenario: Par que tiene un resultado seguido de un fallo

- **WHEN** un par tiene un registro de resultado y después uno de fallo
- **THEN** la lectura conserva el registro de resultado y no lo sustituye por el fallo posterior

#### Scenario: Par sin ningún resultado

- **WHEN** todos los registros de un par tienen estado de fallo
- **THEN** la lectura conserva el último registro escrito, de modo que su diagnóstico quede disponible

### Requirement: Verificación de correspondencia entre el checkpoint y la rúbrica vigente

El sistema SHALL comparar los identificadores de criterio presentes en un checkpoint contra los de la rúbrica vigente antes de reanudar una corrida. Ante una discrepancia, el sistema MUST rehusar la reanudación salvo que se indique explícitamente lo contrario.

#### Scenario: Criterios coincidentes

- **WHEN** los criterios del checkpoint coinciden con los de la rúbrica vigente
- **THEN** la reanudación procede con normalidad

#### Scenario: El checkpoint contiene criterios ausentes en la rúbrica vigente

- **WHEN** el checkpoint contiene identificadores de criterio que la rúbrica vigente no declara
- **THEN** el sistema rehúsa reanudar, enumera los identificadores discrepantes de ambos lados y no emite llamadas

#### Scenario: La rúbrica vigente añade criterios ausentes en el checkpoint

- **WHEN** la rúbrica vigente declara criterios que el checkpoint no contiene
- **THEN** el sistema reporta cuántos pares nuevos implica calificar y los incorpora al trabajo pendiente

### Requirement: Estimación del trabajo y del gasto antes de recalificar

El sistema SHALL reportar, antes de emitir la primera llamada de una reanudación, cuántos pares se recuperan del checkpoint, cuántos se van a recalificar y el costo estimado de esa recalificación. La corrida MUST requerir confirmación explícita del gasto antes de proceder.

#### Scenario: Reanudación con recalificación pendiente

- **WHEN** se reanuda una corrida sobre un checkpoint con pares fallidos
- **THEN** el sistema reporta el número de pares recuperados, el número a recalificar y el costo estimado, y sólo procede tras la confirmación explícita del gasto

#### Scenario: Gasto no confirmado

- **WHEN** se solicita una reanudación que implica recalificar pares y el gasto no ha sido confirmado
- **THEN** el sistema termina sin emitir llamadas e indica cómo confirmarlo
