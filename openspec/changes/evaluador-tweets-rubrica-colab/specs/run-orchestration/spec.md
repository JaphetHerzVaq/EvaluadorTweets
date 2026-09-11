## ADDED Requirements

### Requirement: Autenticación desde el gestor de secretos de Colab

El sistema SHALL leer la clave de API de Gemini desde el gestor de secretos de Colab y MUST NOT contener claves literales en ninguna celda del notebook. El sistema MUST fallar con una instrucción accionable cuando el secreto no esté configurado.

#### Scenario: Secreto configurado
- **WHEN** el usuario tiene la clave registrada en los secretos de Colab y habilitada para el notebook
- **THEN** el sistema la lee, la usa para configurar el cliente y confirma la autenticación sin mostrar el valor de la clave

#### Scenario: Secreto ausente
- **WHEN** el secreto no existe o no está habilitado para el notebook
- **THEN** el sistema falla explicando cómo registrarlo, y no solicita la clave por entrada interactiva ni la imprime

#### Scenario: Clave inválida
- **WHEN** la clave configurada es rechazada por el servicio
- **THEN** el sistema reporta el fallo de autenticación antes de iniciar la corrida

### Requirement: Estimación de costo con confirmación previa

Antes de ejecutar la corrida, el sistema SHALL estimar el número de llamadas, el volumen de tokens y el costo en dólares, calculándolo a partir del número de criterios de la rúbrica cargada y del payload real del subconjunto seleccionado. El sistema MUST requerir una confirmación explícita del usuario antes de proceder.

#### Scenario: Estimación mostrada
- **WHEN** el usuario ejecuta la celda de estimación con una rúbrica y un subconjunto ya cargados
- **THEN** el sistema muestra el número de llamadas, los tokens de entrada y salida estimados y el costo, desglosado por criterio y en total

#### Scenario: Confirmación requerida
- **WHEN** la estimación se muestra
- **THEN** la corrida no comienza hasta que el usuario confirma explícitamente

#### Scenario: Estimación escalada al número de criterios
- **WHEN** la rúbrica cargada tiene un número distinto de criterios
- **THEN** la estimación se recalcula sin intervención, escalando con ese número

### Requirement: Concurrencia controlada sobre las filas

El sistema SHALL procesar las filas del subconjunto mediante un pool asíncrono con un límite de concurrencia configurable, y MUST crear una sesión de ejecución independiente por fila para evitar fuga de estado entre filas.

#### Scenario: Límite de concurrencia respetado
- **WHEN** se configura un límite de concurrencia
- **THEN** el número de filas en vuelo simultáneo nunca lo excede

#### Scenario: Aislamiento entre filas
- **WHEN** se evalúan varias filas concurrentemente
- **THEN** el resultado de una fila no aparece en el estado de otra

#### Scenario: Compatibilidad con el event loop de Colab
- **WHEN** la corrida se ejecuta en una celda de Colab, que ya tiene un event loop activo
- **THEN** la ejecución asíncrona funciona sin conflicto de loops

### Requirement: Reintentos ante errores transitorios

El sistema SHALL reintentar automáticamente las llamadas que fallen por límite de tasa o por errores de servidor, con retroceso exponencial, y MUST registrar la fila como fallida con su motivo cuando los reintentos se agoten.

#### Scenario: Límite de tasa alcanzado
- **WHEN** el servicio responde con un error de límite de tasa
- **THEN** el sistema espera con retroceso exponencial y reintenta hasta el número configurado de intentos

#### Scenario: Reintentos agotados
- **WHEN** una llamada falla tras agotar todos los reintentos
- **THEN** la fila se registra como fallida con el motivo y la corrida continúa con las demás filas

#### Scenario: Respuesta bloqueada por filtros de seguridad
- **WHEN** el modelo rechaza evaluar un tweet por sus filtros de contenido
- **THEN** el sistema registra el bloqueo con su motivo, y ese resultado no se confunde con un nivel bajo ni con una no aplicabilidad

### Requirement: Checkpoint incremental reanudable

El sistema SHALL escribir cada resultado a un archivo de checkpoint en formato JSONL por anexado, identificado por tweet y criterio, inmediatamente al obtenerlo. Al iniciar, el sistema MUST leer el checkpoint existente y omitir las combinaciones de tweet y criterio ya completadas.

#### Scenario: Resultado persistido de inmediato
- **WHEN** un criterio de un tweet termina de evaluarse
- **THEN** su resultado se anexa al checkpoint antes de continuar, sin esperar al final de la corrida

#### Scenario: Reanudación tras desconexión
- **WHEN** la corrida se interrumpe y el usuario vuelve a ejecutar la celda
- **THEN** el sistema omite lo ya completado, reporta cuántos resultados reutiliza y evalúa únicamente lo pendiente

#### Scenario: Corrida ya completa
- **WHEN** el checkpoint contiene todas las combinaciones del subconjunto
- **THEN** el sistema no realiza ninguna llamada al modelo y pasa directamente a la exportación

#### Scenario: Progreso visible
- **WHEN** la corrida avanza
- **THEN** el sistema muestra el progreso, incluyendo filas completadas, pendientes y fallidas
