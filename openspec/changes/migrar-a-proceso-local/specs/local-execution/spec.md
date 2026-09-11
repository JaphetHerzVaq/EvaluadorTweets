## ADDED Requirements

### Requirement: Ejecución del pipeline por etapas desde la línea de comandos

El sistema SHALL exponer cada etapa del pipeline como un subcomando invocable desde la línea de comandos: reparación del corpus, traducción, ingesta de la rúbrica, corrida de calificación, exportación, graficación y auditoría de checkpoint. Cada subcomando MUST poder ejecutarse de forma independiente, leyendo sus insumos desde disco y escribiendo su artefacto a disco.

#### Scenario: Ejecución de una etapa aislada

- **WHEN** se invoca el subcomando de exportación y existen en disco el checkpoint y el corpus requeridos
- **THEN** el sistema produce los CSV ancho y tidy sin ejecutar ninguna otra etapa ni emitir llamadas al modelo

#### Scenario: Insumo ausente para una etapa

- **WHEN** se invoca una etapa cuyo artefacto de entrada no existe en disco
- **THEN** el sistema termina con un error que nombra la ruta esperada y la etapa que la produce, sin emitir llamadas al modelo

#### Scenario: Etapa ya completada

- **WHEN** se invoca una etapa cuyo artefacto de salida ya existe y no se solicitó rehacerla
- **THEN** el sistema informa que la salida ya existe y termina sin recalcular ni volver a gastar

### Requirement: Resolución de dependencias en tiempo de importación

El sistema SHALL organizar la lógica en módulos importables, de modo que toda referencia a una función definida en otro módulo se resuelva al importar el paquete. Un símbolo ausente o mal nombrado MUST impedir el arranque del proceso, y MUST NOT poder manifestarse como fallo en tiempo de ejecución después de haber emitido llamadas al modelo.

#### Scenario: Símbolo inexistente referenciado entre módulos

- **WHEN** un módulo importa un nombre que no existe en el módulo de origen
- **THEN** el proceso falla al arrancar con un error de importación que nombra el símbolo y el módulo, antes de leer el corpus y antes de emitir cualquier llamada

#### Scenario: Arranque previo a cualquier gasto

- **WHEN** se invoca la etapa de corrida
- **THEN** el sistema completa la importación de todos los módulos que la etapa usará antes de emitir la primera llamada al modelo

### Requirement: Configuración por perfiles en archivo

El sistema SHALL leer sus parámetros de un archivo de configuración que admita múltiples perfiles con nombre, seleccionables por bandera en la invocación. Cambiar de un perfil de prueba a uno de corrida completa MUST NOT requerir editar código fuente.

#### Scenario: Selección de perfil

- **WHEN** se invoca una etapa indicando el nombre de un perfil definido en el archivo de configuración
- **THEN** el sistema aplica los parámetros de ese perfil, incluidas las rutas de checkpoint y de salida propias del perfil

#### Scenario: Perfil inexistente

- **WHEN** se invoca una etapa con un nombre de perfil que no está definido
- **THEN** el sistema termina con un error que enumera los perfiles disponibles

#### Scenario: Los parámetros efectivos quedan registrados

- **WHEN** una etapa comienza a ejecutarse
- **THEN** el sistema reporta el perfil activo y los parámetros que determinan gasto y destino: modelo, concurrencia, tamaño de la selección y rutas de checkpoint y salida

### Requirement: La credencial no vive en la configuración ni en el árbol del proyecto

El sistema SHALL obtener la clave de API de una variable de entorno o de un archivo excluido del control de versiones. El archivo de perfiles MUST NOT contener la credencial, y el sistema MUST NOT imprimir su valor.

#### Scenario: Credencial disponible en el entorno

- **WHEN** la variable de entorno con la clave está definida y una etapa requiere acceso al modelo
- **THEN** el sistema la usa y reporta únicamente que fue cargada y su longitud, nunca su contenido

#### Scenario: Credencial ausente

- **WHEN** una etapa requiere acceso al modelo y no hay credencial disponible por ningún medio configurado
- **THEN** el sistema termina con un error que indica cómo proveerla, sin emitir llamadas

### Requirement: El cuaderno se conserva como registro documental no ejecutable

El sistema SHALL mantener una sola definición de cada función del pipeline, residente en el paquete. El cuaderno MUST conservarse sin modificaciones en su contenido y MUST dejar de ser un punto de entrada del pipeline. El cuaderno MUST declarar de forma visible su condición de registro histórico y remitir al paquete como fuente de verdad del comportamiento vigente.

#### Scenario: El cuaderno conserva su documentación íntegra

- **WHEN** se revisa el cuaderno después del traslado
- **THEN** conserva sin alteración la prosa explicativa existente sobre límites de período, conversión de zona horaria, limitaciones conocidas y el comportamiento del cliente asíncrono bajo el parche de reentrada

#### Scenario: El cuaderno declara su condición

- **WHEN** alguien abre el cuaderno después del traslado
- **THEN** encuentra al inicio una declaración de que es un registro histórico no ejecutable, con la fecha y la referencia del commit en que dejó de serlo, y la indicación de que el comportamiento vigente reside en el paquete

#### Scenario: El pipeline no depende del cuaderno

- **WHEN** se ejecuta cualquier etapa del pipeline
- **THEN** no se lee ni se importa el cuaderno en ningún momento

### Requirement: El paquete no depende de bibliotecas de entornos alojados

El paquete SHALL ejecutarse íntegramente como proceso local. Ningún módulo MUST importar bibliotecas propias de entornos de cuaderno alojado, ni requerir parches de reentrada del bucle de eventos. Las corrutinas MUST ejecutarse con el mecanismo estándar de arranque de bucle.

#### Scenario: Ausencia de dependencias de entorno alojado

- **WHEN** se inspeccionan las dependencias declaradas y las importaciones de todos los módulos del paquete
- **THEN** no aparece ninguna biblioteca de entorno de cuaderno alojado ni de parcheo del bucle de eventos

#### Scenario: Ejecución de corrutinas

- **WHEN** una etapa asíncrona se ejecuta
- **THEN** el sistema la arranca con el mecanismo estándar, sin aplicar ningún parche de reentrada

#### Scenario: Los artefactos se escriben siempre a disco

- **WHEN** una etapa produce un artefacto de salida
- **THEN** el artefacto queda escrito en la ruta configurada y el sistema reporta esa ruta, sin depender de ningún mecanismo de entrega propio de un entorno alojado
