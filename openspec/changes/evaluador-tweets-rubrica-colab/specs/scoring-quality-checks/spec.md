## ADDED Requirements

### Requirement: Distribución de niveles por criterio

El sistema SHALL mostrar, al terminar una corrida, la distribución de niveles asignados para cada criterio, incluyendo la proporción de filas marcadas como no aplicables y como fallidas. El sistema MUST señalar los criterios cuya distribución se concentra excesivamente en un solo nivel, porque eso indica que el criterio no discrimina sobre este corpus, que el descriptor se parseó mal del PDF o que el prompt está sesgado.

#### Scenario: Distribución mostrada por criterio
- **WHEN** una corrida termina
- **THEN** el sistema muestra para cada criterio el conteo y la proporción de filas en cada nivel, más las no aplicables y las fallidas

#### Scenario: Criterio que no discrimina
- **WHEN** un criterio concentra en un solo nivel una proporción de filas superior a un umbral configurable
- **THEN** el sistema lo señala explícitamente como criterio sin poder discriminante en este corpus

#### Scenario: Criterio mayoritariamente no aplicable
- **WHEN** un criterio resulta no aplicable en la mayoría de las filas
- **THEN** el sistema lo señala, indicando que la rúbrica puede no corresponder a este tipo de texto

### Requirement: Medición de estabilidad por repetición

El sistema SHALL permitir reevaluar una muestra ya calificada y comparar los resultados con la corrida previa, reportando la proporción de niveles coincidentes por criterio. Esta medición MUST ejecutarse sin sobrescribir el checkpoint de la corrida original.

#### Scenario: Repetición sobre muestra ya calificada
- **WHEN** el usuario ejecuta la medición de estabilidad sobre una muestra ya evaluada
- **THEN** el sistema reevalúa esas filas en un checkpoint separado y reporta el acuerdo por criterio frente a la corrida original

#### Scenario: Inestabilidad detectada
- **WHEN** la proporción de coincidencia queda por debajo de un umbral configurable
- **THEN** el sistema lo señala como ruido del sistema por encima de lo esperado para una configuración determinista

#### Scenario: Checkpoint original intacto
- **WHEN** la medición de estabilidad termina
- **THEN** el checkpoint de la corrida original conserva sus resultados sin modificación

### Requirement: Acuerdo entre modelos sobre muestra de calibración

El sistema SHALL permitir evaluar una muestra de calibración con un segundo modelo configurable y reportar el acuerdo de niveles por criterio entre ambos modelos. Esta capacidad MUST operar sobre una muestra acotada y MUST NOT convertirse en el mecanismo de producción.

#### Scenario: Comparación entre dos modelos
- **WHEN** el usuario ejecuta la calibración indicando un segundo modelo
- **THEN** el sistema evalúa la muestra con ambos modelos y reporta el acuerdo por criterio, incluyendo acuerdo exacto y a un nivel de distancia

#### Scenario: Desacuerdo alto en un criterio
- **WHEN** un criterio presenta desacuerdo entre modelos por encima de un umbral
- **THEN** el sistema lo señala como criterio de juicio inestable, candidato a reformular su descriptor

#### Scenario: Corrida de producción sin voting
- **WHEN** se ejecuta la corrida de producción
- **THEN** se usa un solo modelo por criterio y no se invoca la comparación entre modelos

### Requirement: Comparación contra un conjunto anotado a mano

El sistema SHALL aceptar un conjunto de filas con el nivel asignado manualmente por una persona y MUST reportar el acuerdo entre esas anotaciones y las calificaciones del sistema, por criterio.

#### Scenario: Conjunto anotado disponible
- **WHEN** el usuario proporciona un archivo con niveles anotados a mano para un conjunto de tweets
- **THEN** el sistema reporta el acuerdo por criterio entre la anotación humana y la calificación automática

#### Scenario: Conjunto anotado ausente
- **WHEN** no se proporciona ningún conjunto anotado
- **THEN** la comparación se omite y el sistema advierte que las calificaciones no tienen contraste con juicio humano

#### Scenario: Desacuerdos listados para inspección
- **WHEN** existen filas donde la anotación humana y la calificación automática difieren
- **THEN** el sistema lista esas filas con ambos niveles y la justificación generada, para inspección directa
