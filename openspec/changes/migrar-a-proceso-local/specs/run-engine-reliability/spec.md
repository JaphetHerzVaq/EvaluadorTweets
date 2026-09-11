## ADDED Requirements

### Requirement: Clasificación de fallos entre permanentes y transitorios

El motor de corrida SHALL clasificar cada excepción como permanente o transitoria antes de decidir si reintenta. Un fallo permanente MUST NOT ser reintentado. Los errores de programación —nombre no definido, atributo inexistente, módulo no importable— MUST clasificarse como permanentes, ya que no dependen del dato y se repetirán idénticos en cada intento.

#### Scenario: Fallo permanente por error de programación

- **WHEN** la evaluación de una fila lanza una excepción por un nombre no definido, un atributo inexistente o un módulo no importable
- **THEN** el motor no la reintenta y la trata como fallo permanente

#### Scenario: Fallo transitorio de servicio

- **WHEN** la evaluación de una fila lanza una excepción de límite de tasa o de error de servidor
- **THEN** el motor la reintenta conforme a la política de reintentos configurada

#### Scenario: Fallo de contenido bloqueado

- **WHEN** la evaluación de una fila falla porque el filtro de contenido del proveedor bloqueó la respuesta
- **THEN** el motor no la reintenta y registra el resultado con un estado distinguible de un nivel bajo y de la no aplicabilidad

### Requirement: Aborto de la corrida ante un fallo estructural

El motor de corrida SHALL abortar la corrida completa al detectar un fallo permanente de tipo estructural, propagando el diagnóstico original sin envolverlo. El motor MUST NOT continuar emitiendo llamadas ni escribiendo registros de fallo al checkpoint después de detectarlo.

#### Scenario: Error de programación durante la corrida

- **WHEN** una fila falla con un error de nombre no definido, atributo inexistente o módulo no importable
- **THEN** el motor aborta la corrida de inmediato, reporta el diagnóstico original con su traza y no escribe registros de fallo para las filas restantes

#### Scenario: Fallo dependiente del dato

- **WHEN** una fila falla por un valor inesperado en sus propios datos y las demás filas no se ven afectadas
- **THEN** el motor registra el fallo de esa fila y continúa con las restantes

### Requirement: Cortacircuitos por fallos consecutivos

El motor de corrida SHALL abortar la corrida cuando un número configurable de filas consecutivas termine en fallo, cualquiera que sea su clasificación. El motor MUST reportar el umbral alcanzado y el diagnóstico de los fallos que lo dispararon.

#### Scenario: Racha de fallos consecutivos

- **WHEN** el número de filas consecutivas terminadas en fallo alcanza el umbral configurado
- **THEN** el motor aborta la corrida e informa el umbral alcanzado y los diagnósticos representativos

#### Scenario: Fallos aislados entre resultados exitosos

- **WHEN** hay fallos dispersos pero nunca se alcanza el umbral de fallos consecutivos
- **THEN** la corrida continúa hasta terminar la selección

#### Scenario: Preservación de lo ya calculado al abortar

- **WHEN** el motor aborta por cualquier causa
- **THEN** los resultados escritos al checkpoint antes del aborto permanecen íntegros y disponibles para reanudar

### Requirement: Un resultado parcial es un fallo reintentable

El motor de corrida SHALL tratar como fallo reintentable toda respuesta en la que el conjunto de agentes devuelva menos claves de estado que criterios solicitados. El motor MUST NOT registrar un resultado ausente como resultado definitivo sin haber agotado antes la política de reintentos.

#### Scenario: Faltan claves de estado en la respuesta

- **WHEN** la evaluación de una fila devuelve resultados para menos criterios de los solicitados
- **THEN** el motor trata la respuesta como fallo, reintenta conforme a la política configurada e identifica en el diagnóstico los criterios ausentes

#### Scenario: Reintentos agotados con claves aún ausentes

- **WHEN** se agota la política de reintentos y siguen faltando claves de estado
- **THEN** el motor registra esos criterios con un estado de fallo distinguible, apto para ser reintentado en una corrida posterior

#### Scenario: Respuesta completa

- **WHEN** la evaluación devuelve resultados para todos los criterios solicitados
- **THEN** el motor los valida y registra sin reintentar

### Requirement: La concurrencia se cuenta sobre las llamadas efectivamente emitidas

El motor de corrida SHALL limitar la concurrencia en función del número de peticiones simultáneas al proveedor, no del número de filas en proceso. Cuando una fila produce una llamada por criterio, el motor MUST derivar el número de filas en vuelo a partir del límite de llamadas y del número de criterios de la rúbrica.

#### Scenario: Derivación del paralelismo de filas

- **WHEN** se configura un límite de llamadas simultáneas y la rúbrica tiene N criterios
- **THEN** el motor procesa como máximo el cociente entero entre ese límite y N filas en vuelo, y nunca menos de una

#### Scenario: Rúbrica con más criterios que el límite de llamadas

- **WHEN** el número de criterios excede el límite de llamadas simultáneas configurado
- **THEN** el motor procesa una fila a la vez y advierte que el abanico de la rúbrica supera el límite configurado

#### Scenario: El abanico efectivo queda declarado

- **WHEN** comienza una corrida
- **THEN** el motor reporta el límite de llamadas simultáneas, el número de criterios y el número resultante de filas en vuelo

### Requirement: La política de reintento HTTP está acotada y desincronizada

El sistema SHALL configurar el reintento del cliente HTTP con un tope máximo de espera y con componente aleatorio. Ninguna espera individual entre reintentos MUST exceder el tope configurado.

#### Scenario: Espera acotada entre reintentos

- **WHEN** una llamada se reintenta repetidamente por un fallo transitorio
- **THEN** ninguna espera individual supera el tope configurado, aun en el último intento

#### Scenario: Reintentos desincronizados

- **WHEN** varias llamadas simultáneas fallan de forma transitoria a la vez
- **THEN** sus esperas incorporan un componente aleatorio que evita que reintenten en el mismo instante

#### Scenario: Visibilidad del progreso durante esperas

- **WHEN** la corrida atraviesa un periodo en el que la mayoría de las llamadas está esperando para reintentar
- **THEN** el sistema emite información de avance que permite distinguir una espera por reintentos de un proceso detenido
