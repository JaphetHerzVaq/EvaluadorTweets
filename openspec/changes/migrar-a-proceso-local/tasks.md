## 1. Credencial y control de versiones

- [ ] 1.1 Crear `.gitignore` que excluya la credencial, los CSV y XLSX del corpus, los checkpoints, los artefactos de salida y el entorno virtual
- [ ] 1.2 Mover la clave de `apikey.txt` a variable de entorno o a un archivo ignorado por git, y eliminar `apikey.txt` del árbol del proyecto
- [ ] 1.3 Verificar que ningún archivo rastreable contiene la clave, incluido el `.ipynb`
- [ ] 1.4 Inicializar el repositorio y hacer el primer commit con el cuaderno original íntegro, para tener punto de reversa
- [ ] 1.5 Decidir y registrar en `design.md` si la distribución a Colab será por repositorio o por archivo comprimido (pregunta abierta)

## 2. Entorno y esqueleto del paquete

- [ ] 2.1 Crear entorno virtual y `requirements.txt` con versiones fijadas de `google-adk`, `google-genai`, `pandas` y `openpyxl`
- [ ] 2.2 Verificar que las versiones fijadas importan y que `Gemini(retry_options=...)` sigue siendo un campo válido en la versión elegida
- [ ] 2.3 Registrar la decisión de versión de Python y caer a 3.12 o 3.13 si 3.14 presenta incompatibilidad con ADK
- [ ] 2.4 Crear `pyproject.toml` y el paquete `evaluador/` con los módulos vacíos: `config`, `io_`, `adk`, `rubrica`, `corpus`, `traduccion`, `scoring`, `export`, `viz`, `__main__`
- [ ] 2.5 Verificar que `import evaluador` funciona desde el entorno virtual

## 3. Configuración por perfiles

- [ ] 3.1 Definir el esquema de `config.toml` con los perfiles `piloto` y `completo`, trasladando los parámetros de la celda CONFIG
- [ ] 3.2 Implementar la carga de perfiles con `tomllib` y la selección por bandera
- [ ] 3.3 Trasladar `_validar_periodos` y mantener su validación de solapamiento y orden cronológico
- [ ] 3.4 Implementar la carga de la credencial desde variable de entorno o archivo ignorado, sin imprimir su valor
- [ ] 3.5 Emitir al arrancar cada etapa el reporte de perfil activo y parámetros que determinan gasto y destino
- [ ] 3.6 Verificar que un nombre de perfil inexistente termina con un error que enumera los disponibles
- [ ] 3.7 Verificar que la ausencia de credencial termina con error accionable y sin emitir llamadas

## 4. Adaptador de entorno

- [ ] 4.1 Implementar `io_.py` con la detección única de entorno por disponibilidad de capacidades
- [ ] 4.2 Implementar la obtención de archivos de entrada: error con ruta esperada en local, subida interactiva en el entorno alojado
- [ ] 4.3 Implementar la entrega de salidas: escritura siempre a disco, entrega adicional opcional que no puede hacer fallar la etapa
- [ ] 4.4 Implementar la política de bucle de eventos: parche de reentrada sólo cuando el entorno ya tiene bucle corriendo
- [ ] 4.5 Implementar la presentación de HTML: archivo siempre, visualización incrustada sólo donde el entorno la soporta
- [ ] 4.6 Verificar que ningún módulo del pipeline distinto de `io_.py` importa bibliotecas del entorno alojado

## 5. Traslado de las etapas de preparación

- [ ] 5.1 Trasladar a `adk.py` las utilidades compartidas: construcción del modelo, configuración de generación y ejecución de agente con recolección de estado
- [ ] 5.2 Trasladar a `rubrica.py` el esquema, la carga del PDF, el parseo, la asignación de slugs, la anotación de escala y el resumen
- [ ] 5.3 Regenerar `rubrica.json` desde el PDF vigente y verificar que produce los cuatro criterios: tres ordinales 0–5 y el binario 0/1 de saliencia de violencia
- [ ] 5.4 Verificar que los slugs del `rubrica.json` regenerado coinciden con los presentes en el checkpoint a recuperar
- [ ] 5.5 Trasladar a `corpus.py` la reparación desde `raw_json`, la carga de CSV y Excel, la selección de subconjunto, la detección de contexto incompleto y la construcción del payload
- [ ] 5.6 Trasladar a `traduccion.py` el esquema, la instrucción y el motor de traducción reanudable, conservando sin cambios el rodeo por hilo del cliente síncrono
- [ ] 5.7 Verificar que la reparación y la traducción se saltan solas cuando sus salidas ya existen, sin recalcular ni gastar

## 6. Traslado del motor de corrida, sin arreglos todavía

- [ ] 6.1 Trasladar a `scoring.py` la plantilla de instrucción por criterio, la construcción de los N agentes y la verificación de aislamiento entre criterios
- [ ] 6.2 Trasladar la validación de nivel y la derivación determinista del puntaje desde la rúbrica
- [ ] 6.3 Trasladar la estimación de costo y la compuerta de confirmación de gasto
- [ ] 6.4 Trasladar el motor de corrida con su comportamiento actual intacto, para poder contrastar el traslado por separado de los arreglos
- [ ] 6.5 Verificar que `evaluar_payload` y las demás dependencias entre módulos se resuelven al importar, y que un símbolo mal nombrado impide el arranque

## 7. Piloto de fidelidad del traslado

- [ ] 7.1 Ejecutar un piloto de 60 filas con la semilla original sobre el paquete trasladado, escribiendo a un checkpoint nuevo
- [ ] 7.2 Comparar par a par contra `checkpoint_piloto.jsonl` y documentar cualquier divergencia antes de continuar
- [ ] 7.3 Confirmar que el traslado no alteró la distribución de estados ni el contenido de las justificaciones más allá de la variación esperada del modelo

## 8. Fiabilidad del motor de corrida

- [ ] 8.1 Implementar la clasificación de fallos entre permanentes y transitorios, con los errores de programación como permanentes
- [ ] 8.2 Implementar el aborto inmediato ante fallo estructural, propagando el diagnóstico original con su traza y sin escribir registros de fallo para las filas restantes
- [ ] 8.3 Implementar el manejo de fallos dependientes del dato: se registran en su fila y la corrida continúa
- [ ] 8.4 Implementar el cortacircuitos por fallos consecutivos con umbral configurable, reportando el umbral y los diagnósticos que lo dispararon
- [ ] 8.5 Convertir el resultado parcial en excepción interna que nombre los criterios ausentes, de modo que entre al bucle de reintentos existente
- [ ] 8.6 Materializar el estado de fallo por criterio ausente sólo tras agotar los reintentos
- [ ] 8.7 Invertir el parámetro de concurrencia: configurar llamadas simultáneas y derivar las filas en vuelo como el cociente entero con el número de criterios, con mínimo de una
- [ ] 8.8 Advertir cuando el número de criterios excede el límite de llamadas simultáneas configurado
- [ ] 8.9 Reportar al inicio de cada corrida el límite de llamadas, el número de criterios y las filas en vuelo resultantes
- [ ] 8.10 Reconfigurar el reintento HTTP con base 2, tope máximo de espera y componente aleatorio
- [ ] 8.11 Emitir avance con periodicidad temporal además de por conteo, para distinguir una espera por reintentos de un proceso detenido
- [ ] 8.12 Verificar que los resultados escritos antes de un aborto permanecen íntegros y permiten reanudar
- [ ] 8.13 Probar el aborto estructural introduciendo deliberadamente un símbolo mal nombrado y confirmar que no se escriben registros de fallo
- [ ] 8.14 Probar el cortacircuitos forzando una racha de fallos y confirmar que fallos dispersos no lo disparan

## 9. Recuperación de checkpoint

- [ ] 9.1 Implementar la auditoría que reporta registros, pares distintos, desglose por estado, pares repetidos, estado final por par y diagnósticos predominantes, sin emitir llamadas
- [ ] 9.2 Implementar el conteo y la omisión de líneas ilegibles en la auditoría
- [ ] 9.3 Cambiar la reanudación para considerar completado únicamente el par cuyo registro vigente tenga estado de resultado, tratando la no aplicabilidad como resultado
- [ ] 9.4 Cambiar la deduplicación en lectura a último resultado válido, con caída al último registro escrito cuando no haya ninguno válido
- [ ] 9.5 Implementar la verificación de correspondencia de criterios entre checkpoint y rúbrica vigente, con rechazo de la reanudación ante discrepancia salvo bandera explícita
- [ ] 9.6 Reportar antes de reanudar cuántos pares se recuperan, cuántos se recalifican y el costo estimado, exigiendo confirmación de gasto
- [ ] 9.7 Incorporar `checkpoint (7).jsonl` al proyecto con un nombre estable y auditarlo
- [ ] 9.8 Confirmar sobre la auditoría el reparto esperado de 7,708 pares recuperables y 2,540 a recalificar
- [ ] 9.9 Verificar que una reanudación sobre pares ya resueltos no emite ninguna llamada

## 10. Exportación y visualización

- [ ] 10.1 Trasladar a `export.py` la generación de nombres de columna, el merge al corpus original, la verificación de integridad y la escritura con marca de orden de bytes
- [ ] 10.2 Trasladar a `viz.py` la preparación con fecha local y asignación de período, la agregación y la generación del HTML
- [ ] 10.3 Verificar que el CSV ancho conserva el conteo de filas del corpus y que los identificadores largos no pierden precisión
- [ ] 10.4 Verificar que el HTML generado abre fuera del cuaderno con los filtros funcionando

## 11. Interfaz de línea de comandos

- [ ] 11.1 Implementar `__main__.py` con los subcomandos `reparar`, `traducir`, `rubrica`, `correr`, `exportar`, `graficar` y `auditar`
- [ ] 11.2 Implementar la bandera de selección de perfil y la de confirmación de gasto en los subcomandos que lo requieren
- [ ] 11.3 Verificar que cada etapa falla con error accionable cuando falta su insumo, nombrando la ruta y la etapa que la produce
- [ ] 11.4 Verificar que una etapa con su salida ya presente informa y termina sin recalcular
- [ ] 11.5 Ejecutar el pipeline completo de extremo a extremo en local sobre el perfil `piloto`

## 12. Adelgazamiento del cuaderno

- [ ] 12.1 Sustituir la lógica de las celdas por importaciones del paquete, conservando la prosa explicativa existente
- [ ] 12.2 Añadir la celda de arranque que instala o clona el paquete en el entorno alojado
- [ ] 12.3 Verificar que el cuaderno corre de principio a fin en una sesión limpia de Colab, sin estado residual
- [ ] 12.4 Confirmar que la misma etapa con el mismo perfil produce artefactos equivalentes por línea de comandos y por cuaderno
- [ ] 12.5 Confirmar que ninguna celda redefine lógica del pipeline

## 13. Recalificación y cierre

- [ ] 13.1 Ejecutar el piloto posterior a los arreglos con la misma semilla y comparar par a par contra el piloto de fidelidad
- [ ] 13.2 Recalificar los 2,540 pares fallidos sobre el checkpoint recuperado, con la rúbrica de cuatro criterios ya reconciliada
- [ ] 13.3 Auditar el checkpoint resultante y confirmar que no quedan pares en estado de fallo
- [ ] 13.4 Contrastar el costo real de la recalificación contra la estimación previa
- [ ] 13.5 Exportar y graficar sobre el checkpoint completo, verificando integridad de conteos e identificadores
- [ ] 13.6 Registrar como cambio aparte el problema de modelado pendiente: la colisión entre el nivel «0» de la rúbrica y la regla de aplicabilidad, su efecto destructivo sobre el criterio binario, y la necesidad de que la escala de niveles y los niveles de ausencia dejen de ser parámetros globales
