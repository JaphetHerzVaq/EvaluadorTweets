## 1. Credencial y control de versiones

- [x] 1.1 Crear `.gitignore` que excluya la credencial, los CSV y XLSX del corpus, los checkpoints, los artefactos de salida y el entorno virtual
- [x] 1.2 Mover la clave de `apikey.txt` a variable de entorno o a un archivo ignorado por git, y eliminar `apikey.txt` del árbol del proyecto
- [x] 1.3 Verificar que ningún archivo rastreable contiene la clave, incluido el `.ipynb`
- [x] 1.4 Inicializar el repositorio y hacer el primer commit con el cuaderno original íntegro, para tener punto de reversa
- [x] 1.5 Resuelto: no hay distribución. El usuario descartó Colab como destino; todo corre en local y el cuaderno se conserva como memoria. Registrado en `design.md` y en `proposal.md`

## 2. Entorno y esqueleto del paquete

- [x] 2.1 Crear entorno virtual y `requirements.txt` con versiones fijadas de `google-adk`, `google-genai`, `pandas` y `openpyxl`, sin `nest_asyncio`
- [x] 2.2 Verificar que las versiones fijadas importan y que `Gemini(retry_options=...)` sigue siendo un campo válido en la versión elegida
- [x] 2.3 Registrar la decisión de versión de Python y caer a 3.12 o 3.13 si 3.14 presenta incompatibilidad con ADK
- [x] 2.4 Crear `pyproject.toml` y el paquete `evaluador/` con los módulos vacíos: `config`, `adk`, `rubrica`, `corpus`, `traduccion`, `scoring`, `export`, `viz`, `__main__`
- [x] 2.5 Verificar que `import evaluador` funciona desde el entorno virtual

## 3. Configuración por perfiles

- [x] 3.1 Definir el esquema de `config.toml` con los perfiles `piloto` y `completo`, trasladando los parámetros de la celda CONFIG
- [x] 3.2 Implementar la carga de perfiles con `tomllib` y la selección por bandera
- [x] 3.3 Trasladar `_validar_periodos` y mantener su validación de solapamiento y orden cronológico
- [x] 3.4 Implementar la carga de la credencial desde variable de entorno o archivo ignorado, sin imprimir su valor
- [x] 3.5 Emitir al arrancar cada etapa el reporte de perfil activo y parámetros que determinan gasto y destino
- [x] 3.6 Verificar que un nombre de perfil inexistente termina con un error que enumera los disponibles
- [x] 3.7 Verificar que la ausencia de credencial termina con error accionable y sin emitir llamadas

## 4. Eliminación de las dependencias de entorno alojado

- [x] 4.1 Implementar la utilidad de lectura de insumos que falla con la ruta esperada y la etapa que la produce, sin módulo adaptador
- [x] 4.2 Verificar que ningún módulo del paquete importa bibliotecas de entorno de cuaderno alojado
- [x] 4.3 Verificar que `nest_asyncio` no figura en las dependencias declaradas ni se importa en ningún módulo
- [x] 4.4 Confirmar que las corrutinas se ejecutan con `asyncio.run()` y que la prueba de humo pasa sin parche de reentrada _(bloqueada: requiere `scoring.py`, grupo 6)_
- [x] 4.5 Confirmar que la etapa de graficación escribe el HTML a disco y reporta su ruta, sin intentar visualización incrustada _(bloqueada: requiere `viz.py`, grupo 10)_

## 5. Traslado de las etapas de preparación

- [x] 5.1 Trasladar a `adk.py` las utilidades compartidas: construcción del modelo, configuración de generación y ejecución de agente con recolección de estado
- [x] 5.2 Trasladar a `rubrica.py` el esquema, la carga del PDF, el parseo, la asignación de slugs, la anotación de escala y el resumen
- [x] 5.3 Regenerar `rubrica.json` desde el PDF vigente y verificar que produce los cuatro criterios: tres ordinales 0–5 y el binario 0/1 de saliencia de violencia
- [x] 5.4 Verificar que los slugs del `rubrica.json` regenerado coinciden con los presentes en el checkpoint a recuperar
- [x] 5.5 Trasladar a `corpus.py` la reparación desde `raw_json`, la carga de CSV y Excel, la selección de subconjunto, la detección de contexto incompleto y la construcción del payload
- [x] 5.8 Resuelto de otra forma: el complemento reexportado sigue sin identificadores porque 54 de sus filas nunca vinieron de la API (`origen=corpus_local`, `author_id=csv:*`, `raw_json` vacío). No hay id que recuperar
- [x] 5.9 Implementar `consolidar()` con resolución de llave en tres pasos y llave sintética determinista con prefijo `local:` para las filas sin identificador de origen
- [x] 5.10 Regenerar el consolidado y verificar: 2,631 filas, 2,631 llaves únicas, 2,577 reales y 54 sintéticas, sin duplicados
- [x] 5.11 Verificar que el checkpoint recuperable sigue emparejando sus 2,562 tuits y que el piloto de referencia reproduce 60/60
- [x] 5.12 Verificar que regenerar el consolidado produce llaves sintéticas idénticas, para que no invalide un checkpoint previo
- [x] 5.6 Trasladar a `traduccion.py` el esquema, la instrucción y el motor de traducción reanudable, conservando sin cambios el rodeo por hilo del cliente síncrono
- [x] 5.7 Verificar que la reparación y la traducción se saltan solas cuando sus salidas ya existen, sin recalcular ni gastar

## 6. Traslado del motor de corrida, sin arreglos todavía

- [x] 6.1 Trasladar a `scoring.py` la plantilla de instrucción por criterio, la construcción de los N agentes y la verificación de aislamiento entre criterios
- [x] 6.2 Trasladar la validación de nivel y la derivación determinista del puntaje desde la rúbrica
- [x] 6.3 Trasladar la estimación de costo y la compuerta de confirmación de gasto
- [x] 6.4 Trasladar el motor de corrida con su comportamiento actual intacto, para poder contrastar el traslado por separado de los arreglos
- [x] 6.5 Verificar que `evaluar_payload` y las demás dependencias entre módulos se resuelven al importar, y que un símbolo mal nombrado impide el arranque

## 7. Piloto de fidelidad del traslado

- [x] 7.1 Ejecutar el piloto sobre los 60 tuits exactos de `checkpoint_piloto.jsonl`, seleccionados por lista explícita de identificadores y no por semilla: el corpus creció de 2,562 a 2,631 filas y la misma semilla ya sólo reproduce 1 de los 60
- [x] 7.2 Comparar par a par contra `checkpoint_piloto.jsonl` sobre los 3 criterios comunes y documentar cualquier divergencia antes de continuar (el cuarto criterio, saliencia de violencia, no existía en el piloto original y no es comparable)
- [x] 7.3 Confirmar que el traslado no alteró la distribución de estados ni el contenido de las justificaciones más allá de la variación esperada del modelo

## 8. Fiabilidad del motor de corrida

Medición de referencia del piloto de fidelidad, antes de los arreglos:
240 llamadas en **18.3 min** contra ~1 min estimado, con la tasa cayendo de
6.0/s a 0.2/s al final; y 1 `SIN_RESPUESTA` cementado. Los arreglos de este
grupo deben corregir ambas cosas.


- [x] 8.1 Implementar la clasificación de fallos entre permanentes y transitorios, con los errores de programación como permanentes
- [x] 8.2 Implementar el aborto inmediato ante fallo estructural, propagando el diagnóstico original con su traza y sin escribir registros de fallo para las filas restantes
- [x] 8.3 Implementar el manejo de fallos dependientes del dato: se registran en su fila y la corrida continúa
- [x] 8.4 Implementar el cortacircuitos por fallos consecutivos con umbral configurable, reportando el umbral y los diagnósticos que lo dispararon
- [x] 8.5 Convertir el resultado parcial en excepción interna que nombre los criterios ausentes, de modo que entre al bucle de reintentos existente
- [x] 8.6 Materializar el estado de fallo por criterio ausente sólo tras agotar los reintentos
- [x] 8.7 Invertir el parámetro de concurrencia: configurar llamadas simultáneas y derivar las filas en vuelo como el cociente entero con el número de criterios, con mínimo de una
- [x] 8.8 Advertir cuando el número de criterios excede el límite de llamadas simultáneas configurado
- [x] 8.9 Reportar al inicio de cada corrida el límite de llamadas, el número de criterios y las filas en vuelo resultantes
- [x] 8.10 Reconfigurar el reintento HTTP con base 2, tope máximo de espera y componente aleatorio
- [x] 8.11 Emitir avance con periodicidad temporal además de por conteo, para distinguir una espera por reintentos de un proceso detenido
- [x] 8.12 Verificar que los resultados escritos antes de un aborto permanecen íntegros y permiten reanudar
- [x] 8.13 Probar el aborto estructural introduciendo deliberadamente un símbolo mal nombrado y confirmar que no se escriben registros de fallo
- [x] 8.14 Probar el cortacircuitos forzando una racha de fallos y confirmar que fallos dispersos no lo disparan

## 9. Recuperación de checkpoint

- [x] 9.1 Implementar la auditoría que reporta registros, pares distintos, desglose por estado, pares repetidos, estado final por par y diagnósticos predominantes, sin emitir llamadas
- [x] 9.2 Implementar el conteo y la omisión de líneas ilegibles en la auditoría
- [x] 9.3 Cambiar la reanudación para considerar completado únicamente el par cuyo registro vigente tenga estado de resultado, tratando la no aplicabilidad como resultado
- [x] 9.4 Cambiar la deduplicación en lectura a último resultado válido, con caída al último registro escrito cuando no haya ninguno válido
- [x] 9.5 Implementar la verificación de correspondencia de criterios entre checkpoint y rúbrica vigente, con rechazo de la reanudación ante discrepancia salvo bandera explícita
- [x] 9.6 Reportar antes de reanudar cuántos pares se recuperan, cuántos se recalifican y el costo estimado, exigiendo confirmación de gasto
- [x] 9.10 Implementar los tres alcances de recalificación: `fallidos` (defecto), `sin-nivel` y `todo`, con `todo` ignorando por completo los estados del checkpoint
- [x] 9.11 Hacer que los alcances más amplios que `fallidos` reporten su conteo desglosado y adviertan que repiten gasto ya realizado antes de pedir confirmación
- [x] 9.12 Verificar que recalificar con cualquier alcance no borra registros previos y que la lectura sigue resolviendo cada par por su registro válido más reciente
- [x] 9.7 Incorporar `checkpoint (7).jsonl` al proyecto con un nombre estable y auditarlo
- [x] 9.8 Confirmar sobre la auditoría el reparto esperado de 7,708 pares recuperables y 2,540 a recalificar
- [x] 9.9 Verificar que una reanudación sobre pares ya resueltos no emite ninguna llamada

## 10. Exportación y visualización

- [x] 10.1 Trasladar a `export.py` la generación de nombres de columna, el merge al corpus original, la verificación de integridad y la escritura con marca de orden de bytes
- [x] 10.2 Trasladar a `viz.py` la preparación con fecha local y asignación de período, la agregación y la generación del HTML
- [x] 10.3 Verificar que el CSV ancho conserva el conteo de filas del corpus y que los identificadores largos no pierden precisión
- [x] 10.4 Verificar que el HTML generado abre fuera del cuaderno con los filtros funcionando

## 11. Interfaz de línea de comandos

- [x] 11.1 Implementar `__main__.py` con los subcomandos `reparar`, `traducir`, `rubrica`, `correr`, `exportar`, `graficar` y `auditar`
- [x] 11.2 Implementar la bandera de selección de perfil y la de confirmación de gasto en los subcomandos que lo requieren
- [x] 11.3 Verificar que cada etapa falla con error accionable cuando falta su insumo, nombrando la ruta y la etapa que la produce
- [x] 11.4 Verificar que una etapa con su salida ya presente informa y termina sin recalcular
- [x] 11.5 Ejecutar el pipeline completo de extremo a extremo en local sobre el perfil `piloto`

## 12. Preservación del cuaderno como memoria

- [x] 12.1 Añadir al inicio del cuaderno una celda de encabezado que declare su condición de registro histórico no ejecutable, con la fecha y el commit en que dejó de serlo, y remita al paquete como fuente de verdad
- [x] 12.2 Verificar que el contenido de las demás celdas queda sin alterar respecto al primer commit
- [x] 12.3 Verificar que ninguna etapa del pipeline lee ni importa el cuaderno
- [x] 12.4 Escribir el README que documenta el uso del paquete, para que el cuaderno no siga siendo el sitio donde se busca cómo correr las cosas

## 13. Recalificación y cierre

El plan de recuperación cambió durante la implementación. Al revisar las
calificaciones reales se encontró que 67 de 122 (55%) eran sobre tuits de
otros países, porque sólo 5 de 20 niveles de la rúbrica nombraban a México.
El usuario actualizó el PDF —ahora 20/20— y pidió recalificar todo. Los 7,708
pares «recuperables» quedan obsoletos: se produjeron con otro instrumento.

- [x] 13.7 Implementar `verificar_anclaje()` y conectarlo al CLI antes de la compuerta de gasto
- [x] 13.8 Implementar `huella()` de contenido de la rúbrica y rehusar la reanudación cuando cambia, porque cotejar slugs no basta
- [x] 13.9 Reparsear el PDF anclado y verificar 20/20 niveles con el objeto de estudio nombrado
- [x] 13.12 Implementar el respaldo por llamada directa cuando ADK agota sus reintentos para un criterio, con el `block_reason` del proveedor para marcar `BLOQUEADO`
- [x] 13.13 Dejar de reintentar los pares `BLOQUEADO` en las reanudaciones, y verificar que el conteo de fallidas deja de incluirlos
- [x] 13.14 Rescatar con el respaldo los 33 pares de los 56 que la vía directa sí resuelve
- [x] 13.10 Corrida completa sobre el corpus de 2,631 con la rúbrica anclada, en checkpoint nuevo
- [x] 13.11 Verificar sobre el resultado que la proporción de calificaciones sobre tuits sin mención de México bajó respecto al 55% previo


- [x] 13.1 Ejecutar el piloto posterior a los arreglos con la misma semilla y comparar par a par contra el piloto de fidelidad
- [x] 13.2 Obsoleto: con la rúbrica anclada los 7,708 pares previos ya no son válidos. Se sustituye por 13.10, una corrida completa
- [x] 13.3 Auditar el checkpoint resultante y confirmar que no quedan pares en estado de fallo
- [x] 13.4 Contrastar el costo real de la recalificación contra la estimación previa
- [x] 13.5 Exportar y graficar sobre el checkpoint completo, verificando integridad de conteos e identificadores
- [x] 13.6 Registrado como cambio aparte `anclar-semantica-de-ausencia`: la colisión entre el nivel «0» y la bandera `aplicable`, su efecto destructivo sobre el criterio binario, y la necesidad de tipar la escala por criterio
