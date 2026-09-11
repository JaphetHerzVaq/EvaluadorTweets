## Why

Una corrida real sobre el corpus completo produjo **15,384 registros de fallo de un total de 27,748**, y el detalle de los 15,384 es idéntico: `name 'evaluar_payload' is not defined`. No fue la API — fue estado oculto de Colab. La función vive en la celda 22 (prueba de humo) y la usa la celda 25 (motor de corrida); cuando la celda 22 salió del namespace a media sesión, cada llamada murió sin tocar la red, se reintentó cinco veces con retroceso exponencial, y se escribió al checkpoint como fallo permanente. Diecinueve corridas sanas y después el corte: de ahí en adelante, 100% de error.

El daño es recuperable pero hoy está congelado: **7,708 pares (75.2%) están calificados y sanos**, y **2,540 pares (24.8%, ~635 tweets) quedaron cementados** porque `claves_completadas()` no distingue un registro exitoso de uno fallido y los salta al reanudar. Reejecutar el notebook no repara nada. El notebook, como formato, no puede garantizar que un símbolo exista cuando se le llama; un paquete importado sí.

## What Changes

- **Nuevo paquete `evaluador/`** con la lógica completa del notebook repartida en módulos (`config`, `io_`, `adk`, `rubrica`, `corpus`, `traduccion`, `scoring`, `export`, `viz`). Un símbolo ausente se vuelve `ImportError` al arrancar, no un fallo silencioso a las cuatro horas.
- **CLI por etapas**: `python -m evaluador <etapa>` con `reparar`, `traducir`, `rubrica`, `correr`, `exportar`, `graficar`, `auditar`. Cada etapa lee y escribe los artefactos en disco que el notebook ya produce, por lo que siguen siendo independientes y reanudables.
- **Perfiles de configuración** (`piloto`, `completo`) en archivo, seleccionables por bandera. Hoy cambiar de piloto a corrida completa exige editar la celda CONFIG a mano, que es como `CHECKPOINT_PATH` terminó apuntando a un archivo distinto del declarado.
- **El notebook se conserva** y sigue corriendo en Colab, pero adelgaza: importa el paquete en vez de definir la lógica en celdas. La prosa explicativa —los márgenes de los períodos, la justificación del corte del 6 de julio, las limitaciones conocidas— se queda donde está.
- **Adaptador de entorno**: `files.upload()`, `files.download()`, `drive.mount()` y `IPython.display` dejan de estar repartidos en seis celdas y viven en un solo módulo que detecta si corre en Colab o en local. En local, un archivo ausente produce un error claro en vez de `ImportError: google.colab`.
- **Reanudación que distingue fallo de éxito**: `claves_completadas()` sólo cuenta como hechos los registros con estado `OK` o `NO_APLICABLE`. Los estados de fallo se reintentan en la siguiente corrida. **BREAKING** respecto al comportamiento actual: reanudar sobre un checkpoint con fallos ahora gasta dinero recalificándolos, que es precisamente lo que se necesita.
- **Resultado parcial tratado como fallo reintentable**: cuando el `ParallelAgent` devuelve menos claves de estado que criterios pedidos, el motor lanza excepción en vez de retornar. Hoy retorna, el bucle `MAX_INTENTOS` nunca se activa, y el hueco se escribe como definitivo.
- **Los fallos deterministas no se reintentan**: un `NameError`, `TypeError` o `AttributeError` se clasifica como permanente y aborta la corrida de inmediato con el traceback. Reintentar un error de programación cinco veces con espera exponencial costó del orden de cuatro horas de sueño inútil en la corrida analizada.
- **Concurrencia contada sobre llamadas, no sobre filas**: el semáforo limita peticiones HTTP reales. Hoy limita filas, y cada fila abanica N agentes del `ParallelAgent`, así que el fan-out efectivo es `CONCURRENCIA × N_CRITERIOS` sin que nada lo declare.
- **Reintento HTTP con techo**: `RETRY_OPTIONS` pasa de `exp_base=7` sin `max_delay` (esperas de 1 s → 7 s → 49 s → **343 s**) a base 2 con tope y ruido. Una espera de casi seis minutos es indistinguible de un cuelgue.
- **Auditoría de checkpoint**: comando que reporta el desglose de estados, los pares duplicados, el estado final por par y la discrepancia entre los criterios presentes en el checkpoint y los de `rubrica.json`. El checkpoint analizado trae cuatro criterios y el `rubrica.json` en disco tiene tres.
- **Recalificación selectiva**: reanudar sobre un checkpoint existente recupera los pares buenos y recalifica sólo los fallidos, sin volver a pagar los 7,708 ya resueltos.
- **Se regenera `rubrica.json` desde el PDF vigente**, que ya está actualizado y define cuatro criterios: tres ordinales 0–5 (simpática/emocional, estética, funcional) más uno **binario 0/1**, saliencia de violencia. El `rubrica.json` en disco tiene tres criterios y es anterior al PDF. El cuarto criterio del checkpoint recuperable corresponde al del PDF, de modo que los 7,708 pares se recuperan completos.
- **NO se cambia la plantilla de instrucción ni la semántica de la rúbrica.** El 74% de `NO_APLICABLE` sobre los pares sanos (7,586 de 7,708; sólo 122 `OK`) no indica que la rúbrica no corresponda al corpus: la rúbrica codifica la ausencia como nivel «0» y la regla 1 de `instruccion_para` ordena responder `aplicable=false` ante un tweet ajeno al criterio. Son dos codificaciones de lo mismo y la regla gana siempre, dejando el nivel «0» inalcanzable. Para el criterio binario esto es destructivo —«violencia ausente» deja de poder distinguirse de «fuera de alcance»— y para la visualización deja `ESCALA_NIVELES` y `NIVELES_AUSENCIA`, hoy globales, sin sentido aplicados al cuarto criterio. Es un problema de modelado, real y distinto del traslado, y merece su propio cambio.

## Capabilities

### New Capabilities

- `local-execution`: Ejecutar el pipeline completo como un proceso local por etapas, con una interfaz de línea de comandos y perfiles de configuración en archivo, sin depender de un entorno de cuaderno ni de la ejecución manual de celdas en orden.
- `execution-environment-adapter`: Aislar en un único módulo las operaciones que dependen del entorno de ejecución —subida y descarga de archivos, montaje de almacenamiento remoto, despliegue de HTML en línea— de modo que el mismo código corra en local y en Colab, y que la ausencia de un archivo produzca un error accionable en vez de un fallo de importación.
- `run-engine-reliability`: Garantizar que el motor de corrida distinga fallos permanentes de transitorios, trate un resultado parcial como fallo reintentable, no registre un fallo como trabajo completado, y limite la concurrencia sobre las peticiones efectivamente emitidas.
- `checkpoint-recovery`: Auditar un checkpoint existente, reportar su composición y sus inconsistencias frente a la rúbrica vigente, y reanudar recuperando los resultados válidos ya pagados mientras se recalifican únicamente los pares fallidos.

### Modified Capabilities

Ninguna. `openspec/specs/` está vacío: los cambios `evaluador-tweets-rubrica-colab`, `reparar-corpus-y-traducir` y `scoring-visualization` siguen en curso y sus capacidades aún no se han publicado. En particular, `run-orchestration` —cuyos requisitos este cambio contradice en la reanudación y en la concurrencia— todavía vive dentro de su cambio de origen. Al archivar, `run-engine-reliability` deberá reconciliarse con ella.

## Impact

**Artefactos nuevos**: paquete `evaluador/` en la raíz, `pyproject.toml`, `requirements.txt`, archivo de perfiles de configuración, `.gitignore`.

**Artefactos modificados**: `evaluador_tweets_rubrica.ipynb` pierde ~2,400 líneas de lógica y conserva la prosa y las llamadas. Las 40 celdas se reducen a llamadas al paquete.

**Datos**: ninguno se destruye. `checkpoint (7).jsonl` (27,748 registros, 10 MB, hoy en la carpeta de descargas) se incorpora al proyecto como insumo de recuperación. Los artefactos existentes —`turistas_reparado.csv`, `turistas_traducido.csv`, `rubrica.json`, `checkpoint_traduccion.jsonl`— se siguen leyendo con el mismo formato.

**Credenciales**: `apikey.txt` sale del árbol del proyecto. La clave pasa a leerse de variable de entorno o de un archivo ignorado por control de versiones. El proyecto todavía no está bajo git; conviene resolverlo antes del primer commit y antes de que el paquete se distribuya a Colab.

**Dependencias**: las mismas (`google-adk`, `google-genai`, `pandas`, `openpyxl`), ahora con versión fijada. El entorno local tiene `google-adk 1.26.0` y `google-genai 1.66.0`, mientras que el notebook declara `>=1.25.0` y cita 1.25.0 como versión validada; la diferencia debe resolverse explícitamente. `nest_asyncio` deja de ser necesario fuera de Colab y con ello desaparece la incompatibilidad con el cliente asíncrono de `google-genai` ya documentada en la celda 9.6.

**Distribución a Colab**: para que el notebook delgado funcione en Colab, el paquete debe poder instalarse desde allí. Esto implica un repositorio accesible, y es la razón por la que la extracción de la clave de API no puede posponerse.

**Costo**: recalificar los 2,540 pares fallidos son ~2,540 llamadas. Los 7,708 pares ya resueltos no se vuelven a pagar.
