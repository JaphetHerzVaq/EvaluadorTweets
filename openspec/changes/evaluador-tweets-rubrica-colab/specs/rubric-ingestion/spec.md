## ADDED Requirements

### Requirement: Carga del PDF de rúbrica

El notebook SHALL aceptar un documento PDF de rúbrica desde Google Drive montado o desde subida directa en Colab, y MUST pasarlo al modelo como entrada nativa mediante `types.Part.from_bytes` con tipo MIME `application/pdf`, sin depender de bibliotecas de extracción de texto ni de OCR.

#### Scenario: PDF cargado desde subida directa
- **WHEN** el usuario sube un archivo PDF en la celda de carga de rúbrica
- **THEN** el sistema lee sus bytes y confirma el nombre y tamaño del archivo cargado

#### Scenario: Archivo que no es PDF
- **WHEN** el usuario proporciona un archivo cuya extensión no es `.pdf`
- **THEN** el sistema falla con un mensaje que indica que sólo se acepta PDF, sin intentar procesarlo

### Requirement: Normalización de la rúbrica a estructura de criterios

El sistema SHALL extraer del PDF una estructura normalizada de criterios usando salida estructurada, donde cada criterio contiene un identificador, un nombre, la pregunta o consigna de evaluación, y una lista de niveles de logro. Cada nivel MUST contener una etiqueta y un descriptor, y MAY contener un valor numérico de puntos.

#### Scenario: Rúbrica con escala numérica
- **WHEN** el PDF define niveles con valores numéricos asociados
- **THEN** cada nivel del resultado incluye su campo de puntos y el criterio expone la lista de valores válidos de la escala

#### Scenario: Rúbrica con niveles nominales sin puntaje
- **WHEN** el PDF define niveles únicamente por etiqueta, como "Logrado", "En proceso" o "Inicial", sin valores numéricos
- **THEN** los niveles del resultado omiten el campo de puntos y el criterio queda marcado como de escala nominal

#### Scenario: Descriptores preservados íntegros
- **WHEN** la rúbrica se normaliza
- **THEN** el descriptor de cada nivel se conserva completo, sin resumir ni reescribir, porque es el texto contra el que se califica

### Requirement: Punto de control humano antes de la corrida

El sistema SHALL materializar la rúbrica normalizada en un archivo JSON en disco y MUST mostrar un resumen inspeccionable —número de criterios detectados, número de niveles por criterio y tipo de escala— antes de que cualquier calificación se ejecute.

#### Scenario: Resumen mostrado tras el parseo
- **WHEN** la rúbrica termina de normalizarse
- **THEN** el sistema escribe el archivo JSON y muestra el conteo de criterios, los niveles por criterio y el tipo de escala detectado

#### Scenario: Rúbrica sin criterios detectados
- **WHEN** el parseo no identifica ningún criterio en el PDF
- **THEN** el sistema falla con un mensaje explícito y no continúa a la construcción de agentes

#### Scenario: Rúbrica corregida a mano
- **WHEN** el usuario edita el archivo JSON de rúbrica y vuelve a ejecutar la celda de carga
- **THEN** el sistema usa el contenido editado del archivo sin volver a llamar al modelo

### Requirement: Identificadores de criterio estables para nombrar columnas

El sistema SHALL derivar de cada criterio un identificador en formato kebab-case o snake_case, único dentro de la rúbrica y estable entre corridas, apto para usarse como prefijo de nombre de columna.

#### Scenario: Identificadores únicos
- **WHEN** dos criterios de la rúbrica producen el mismo identificador derivado
- **THEN** el sistema los desambigua con un sufijo determinista y reporta la colisión

#### Scenario: Estabilidad entre corridas
- **WHEN** la misma rúbrica se carga dos veces desde el mismo archivo JSON
- **THEN** los identificadores de criterio son idénticos en ambas corridas
