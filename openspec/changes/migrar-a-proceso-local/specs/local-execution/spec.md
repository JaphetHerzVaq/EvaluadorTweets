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

### Requirement: Paridad de comportamiento entre el cuaderno y la línea de comandos

El sistema SHALL mantener una sola definición de cada función del pipeline, residente en el paquete. El cuaderno MUST obtener el comportamiento importando el paquete y MUST NOT redefinir lógica del pipeline en sus celdas.

#### Scenario: Misma entrada por las dos vías

- **WHEN** se ejecuta la misma etapa con el mismo perfil y los mismos insumos desde la línea de comandos y desde el cuaderno
- **THEN** ambos producen artefactos equivalentes, salvo por los mensajes propios de presentación de cada entorno

#### Scenario: El cuaderno conserva su documentación

- **WHEN** se revisa el cuaderno después del traslado
- **THEN** conserva la prosa explicativa existente sobre límites de período, conversión de zona horaria, limitaciones conocidas y el comportamiento del cliente asíncrono
