## ADDED Requirements

### Requirement: Un agente aislado por criterio

El sistema SHALL construir un agente de Google ADK por cada criterio de la rúbrica cargada, iterando sobre la lista de criterios sin que el número de criterios aparezca fijo en el código. Cada agente MUST recibir en su instrucción únicamente su propio criterio y los descriptores de sus propios niveles, y MUST NOT recibir los descriptores de los demás criterios.

#### Scenario: Agentes generados desde la rúbrica
- **WHEN** se carga una rúbrica con N criterios
- **THEN** el sistema construye exactamente N agentes, uno por criterio, y reporta los nombres generados

#### Scenario: Aislamiento del criterio
- **WHEN** se inspecciona la instrucción de un agente
- **THEN** contiene el descriptor de sus propios niveles y ninguna referencia a los descriptores de otros criterios

#### Scenario: Cambio del número de criterios
- **WHEN** se carga una rúbrica distinta con un número diferente de criterios
- **THEN** el sistema construye el nuevo número de agentes sin requerir modificación de código

### Requirement: Ejecución en paralelo de los criterios

El sistema SHALL agrupar los agentes de criterio en un `ParallelAgent` de ADK, de modo que los N criterios de un mismo tweet se evalúen concurrentemente, y MUST escribir el resultado de cada criterio en una clave de estado propia y distinguible.

#### Scenario: Criterios evaluados concurrentemente
- **WHEN** se evalúa un tweet contra una rúbrica de N criterios
- **THEN** los N agentes se ejecutan en paralelo y el tiempo total se aproxima al del criterio más lento, no a la suma de los N

#### Scenario: Resultados atribuibles
- **WHEN** la evaluación de un tweet termina
- **THEN** cada resultado es recuperable por la clave de estado de su criterio y ningún resultado queda sin atribución

### Requirement: Salida estructurada garantizada

Cada agente de criterio SHALL declarar un esquema de salida estructurada que contenga el nivel asignado, la justificación y un indicador de aplicabilidad, además del puntaje cuando la rúbrica define una escala numérica. El sistema MUST NOT depender de expresiones regulares sobre texto libre para recuperar el nivel o el puntaje.

#### Scenario: Respuesta conforme al esquema
- **WHEN** un agente califica un tweet
- **THEN** el resultado es un objeto con los campos declarados y el nivel pertenece a los niveles definidos para ese criterio

#### Scenario: Nivel fuera de la escala
- **WHEN** el modelo devuelve un nivel que no pertenece a la escala válida del criterio
- **THEN** el sistema registra la fila como fallida con el motivo, y no la trata como una calificación válida

#### Scenario: Escala nominal sin puntaje
- **WHEN** el criterio proviene de una rúbrica de niveles nominales sin valores numéricos
- **THEN** el resultado omite el campo de puntaje y el nivel nominal es el resultado de la calificación

### Requirement: Distinción entre bajo logro y criterio no aplicable

El sistema SHALL producir un indicador de aplicabilidad independiente del nivel. Cuando el contenido del tweet sea ajeno al criterio evaluado, el agente MUST marcar el criterio como no aplicable en lugar de asignar el nivel más bajo de la escala.

#### Scenario: Tweet ajeno al criterio
- **WHEN** un tweet no tiene relación con lo que el criterio evalúa
- **THEN** el resultado marca el criterio como no aplicable, el nivel queda vacío y la justificación explica por qué está fuera de alcance

#### Scenario: Tweet relacionado pero de bajo logro
- **WHEN** un tweet aborda el tema del criterio pero refleja el nivel más bajo de la escala
- **THEN** el resultado marca el criterio como aplicable y asigna el nivel más bajo, no la no aplicabilidad

### Requirement: Justificación acotada y en español

Cada calificación SHALL incluir una justificación redactada en español que referencie el contenido concreto del tweet y el descriptor del nivel asignado. El largo de la justificación MUST estar acotado por un parámetro configurable, porque el costo de la corrida lo domina la salida generada.

#### Scenario: Justificación referenciada al descriptor
- **WHEN** un agente asigna un nivel a un tweet
- **THEN** la justificación cita el contenido del tweet que sustenta la decisión y lo relaciona con el descriptor del nivel elegido

#### Scenario: Justificación en español sobre tweet en otro idioma
- **WHEN** el tweet evaluado está en inglés, japonés u otro idioma
- **THEN** la justificación se redacta en español

#### Scenario: Límite de extensión respetado
- **WHEN** se configura un límite de palabras para la justificación
- **THEN** las justificaciones producidas se mantienen dentro de ese límite

### Requirement: Prohibición de inferir contenido ausente

Los agentes MUST NOT inventar, inferir ni dar crédito por contenido que no está presente en el texto del tweet. Cuando el tweet sea una respuesta marcada como de contexto incompleto, el agente MUST calificar únicamente sobre el texto disponible y declarar la limitación en su justificación.

#### Scenario: Contenido ausente
- **WHEN** el tweet no contiene elementos que el criterio requiere evaluar
- **THEN** el agente lo declara ausente en la justificación y no supone su existencia

#### Scenario: Reply con contexto faltante
- **WHEN** el payload incluye la advertencia de contexto incompleto
- **THEN** la justificación reconoce que el contexto previo no está disponible y no reconstruye la conversación

### Requirement: Configuración determinista del modelo

El sistema SHALL configurar el modelo con temperatura cero y con el presupuesto de razonamiento desactivado, y MUST exponer el identificador del modelo como parámetro de configuración validado antes de la corrida.

#### Scenario: Configuración aplicada
- **WHEN** se construyen los agentes
- **THEN** todos usan el mismo identificador de modelo, temperatura cero y razonamiento desactivado

#### Scenario: Identificador de modelo inválido
- **WHEN** el identificador de modelo configurado no está disponible para la credencial en uso
- **THEN** el sistema falla antes de iniciar la corrida, indicando los modelos disponibles

#### Scenario: Repetición estable
- **WHEN** el mismo tweet se evalúa dos veces con la misma configuración
- **THEN** los niveles asignados coinciden
