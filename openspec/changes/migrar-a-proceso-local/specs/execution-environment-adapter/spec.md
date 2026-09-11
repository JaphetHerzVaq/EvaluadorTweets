## ADDED Requirements

### Requirement: Detección del entorno de ejecución en un único punto

El sistema SHALL determinar si corre dentro de un cuaderno alojado o como proceso local mediante una sola comprobación de disponibilidad de capacidades, expuesta por un módulo adaptador. Ningún otro módulo del pipeline MUST importar bibliotecas específicas del entorno alojado.

#### Scenario: Ejecución como proceso local

- **WHEN** el paquete se importa en un entorno donde las bibliotecas del cuaderno alojado no están disponibles
- **THEN** el adaptador selecciona el comportamiento local y el resto del pipeline funciona sin referencias al entorno alojado

#### Scenario: Ejecución dentro del cuaderno alojado

- **WHEN** el paquete se importa en un entorno donde esas bibliotecas sí están disponibles
- **THEN** el adaptador selecciona el comportamiento alojado y habilita subida, descarga y montaje de almacenamiento remoto

#### Scenario: Aislamiento de la dependencia

- **WHEN** se inspecciona cualquier módulo del pipeline distinto del adaptador
- **THEN** no contiene importaciones de bibliotecas propias del entorno alojado

### Requirement: La obtención de archivos de entrada respeta la semántica del entorno

El sistema SHALL resolver la obtención de un archivo de entrada a través del adaptador. En el entorno local, un archivo ausente MUST producir un error que nombre la ruta esperada. El sistema MUST NOT presentar un fallo de importación de una biblioteca del entorno alojado como diagnóstico de un archivo faltante.

#### Scenario: Archivo de entrada ausente en local

- **WHEN** se solicita un archivo de entrada que no existe y el entorno es local
- **THEN** el sistema termina con un error que indica la ruta esperada y cómo obtener o generar ese archivo

#### Scenario: Archivo de entrada ausente en el entorno alojado

- **WHEN** se solicita un archivo de entrada que no existe y el entorno es alojado
- **THEN** el adaptador ofrece el mecanismo de subida interactiva propio de ese entorno

### Requirement: La entrega de artefactos de salida respeta la semántica del entorno

El sistema SHALL escribir siempre sus artefactos de salida a disco. La entrega adicional —descarga al equipo del usuario, copia a almacenamiento remoto— MUST ser responsabilidad del adaptador y su indisponibilidad MUST NOT hacer fallar la etapa.

#### Scenario: Escritura en local

- **WHEN** una etapa termina en entorno local
- **THEN** el artefacto queda escrito en la ruta configurada y el sistema reporta esa ruta, sin intentar descargas

#### Scenario: Entrega no disponible

- **WHEN** el mecanismo de entrega adicional falla o no está disponible
- **THEN** la etapa se considera exitosa, el artefacto permanece en disco y el sistema reporta que la entrega adicional no se realizó

### Requirement: La política del bucle de eventos depende del entorno

El sistema SHALL ejecutar sus corrutinas mediante el mecanismo apropiado al entorno. El parche de reentrada del bucle de eventos MUST aplicarse únicamente cuando el entorno ya tiene un bucle en ejecución, y MUST NOT aplicarse en el proceso local.

#### Scenario: Proceso local sin bucle previo

- **WHEN** una etapa asíncrona se ejecuta como proceso local
- **THEN** el sistema la ejecuta con el mecanismo estándar de arranque de bucle y no aplica el parche de reentrada

#### Scenario: Entorno alojado con bucle activo

- **WHEN** una etapa asíncrona se ejecuta dentro de un cuaderno alojado con un bucle ya corriendo
- **THEN** el adaptador aplica el parche de reentrada antes de ejecutar la corrutina

### Requirement: La presentación de resultados visuales depende del entorno

El sistema SHALL generar el artefacto HTML de gráficas en todos los entornos. La visualización incrustada en la sesión MUST ocurrir sólo donde el entorno la soporta, y su ausencia MUST NOT hacer fallar la etapa.

#### Scenario: Graficación en local

- **WHEN** la etapa de graficación se ejecuta como proceso local
- **THEN** el archivo HTML queda escrito y el sistema reporta su ruta, sin intentar incrustar la visualización en la sesión

#### Scenario: Graficación en el entorno alojado

- **WHEN** la etapa de graficación se ejecuta en un cuaderno que soporta visualización incrustada
- **THEN** el sistema escribe el archivo HTML y además muestra la visualización en la sesión
