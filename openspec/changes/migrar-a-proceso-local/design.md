## Context

El pipeline vive hoy en `evaluador_tweets_rubrica.ipynb`: 40 celdas, ~2,800 líneas, encadenadas por variables globales. Funciona, y la calidad del código es alta — pero el formato tiene un modo de falla que el código no puede prevenir.

La corrida analizada (`checkpoint (7).jsonl`, 27,748 registros) lo documenta con precisión:

```
  corrida  1 │ 2,380 regs │ NO_APLICABLE 2,341 · OK 32 · SIN_RESP 7 │ sana
  ...        │            │                                          │
  corrida 19 │   136 regs │ NO_APLICABLE 136                         │ sana
  ───────────┼────────────┼──────────────────────────────────────────┼─────────
  corrida 20 │ 1,752 regs │ NO_APLIC 1,541 · ERROR 156 · OK 54       │ ◀ CORTE
  corrida 21+│  ...       │ ERROR 100%                               │ NameError
```

Diecinueve corridas sanas sin un solo fallo de red, y después un corte del que no se recupera. Los 15,384 registros `ERROR` tienen todos el mismo detalle: `name 'evaluar_payload' is not defined`. La función se define en la celda 22 y se usa en la celda 25; entre ambas hay una dependencia que el cuaderno no declara ni verifica.

Tres defectos del motor convirtieron ese tropiezo en pérdida permanente:

```
  NameError (determinista)
    ├─▶ _motivo_fallo() lo etiqueta "ERROR", igual que un fallo de red
    ├─▶ MAX_INTENTOS=5 lo reintenta con sleep 2+4+8+16 = 30 s por fila
    └─▶ se escribe al checkpoint; claves_completadas() lo da por HECHO
             └─▶ reanudar lo salta ──▶ 2,540 pares congelados
```

Estado actual del dato: **7,708 pares sanos (75.2%)**, **2,540 cementados (24.8%, ~635 tweets)**. Verificado además que ningún par tuvo un resultado bueno sobrescrito por un fallo posterior, así que la política `drop_duplicates(keep="last")` de `cargar_resultados` no ha destruido nada.

Restricciones que enmarcan el diseño: **todo corre en local y nada vuelve a Colab**; el cuaderno se conserva como memoria del proyecto, no como interfaz ejecutable; el traslado es total (todas las etapas, no sólo el motor); el entorno local es Windows con Python 3.14 y `google-adk 1.26.0` / `google-genai 1.66.0` ya instalados; el proyecto todavía no está bajo control de versiones y `apikey.txt` está en el árbol en texto plano.

La decisión de abandonar Colab como destino simplifica el diseño más de lo que parece: sin dualidad de entorno no hay adaptador que escribir, no hay parche de reentrada del bucle de eventos, no hay subida ni descarga de archivos, y no hay que distribuir el paquete a ninguna parte.

## Goals / Non-Goals

**Goals:**

- Que un símbolo ausente falle al arrancar el proceso, no a las cuatro horas y 15,000 llamadas.
- Que reanudar una corrida repare los fallos en vez de preservarlos.
- Que la concurrencia declarada sea la concurrencia real.
- Que un error de programación aborte la corrida de inmediato con su traceback, en vez de consumirse en reintentos.
- Recuperar los 7,708 pares ya pagados y recalificar sólo los 2,540 fallidos.
- Que exista una sola definición de cada función del pipeline, en el paquete.
- Conservar íntegro el cuaderno como memoria del proyecto: las limitaciones conocidas, la justificación de los cortes de período, las notas sobre `nest_asyncio` y ADK. Es documentación ganada con dolor, y su valor no depende de que siga siendo ejecutable.

**Non-Goals:**

- **No se toca la semántica de la rúbrica ni la plantilla de instrucción.** El 74% de `NO_APLICABLE` sobre los pares sanos (7,586 de 7,708; sólo 122 `OK` = 1.2%) **no** es señal de que la rúbrica no corresponda al corpus: es la regla 1 de `instruccion_para` funcionando como está escrita. La rúbrica define el nivel «0» como ausencia de la dimensión, y la regla 1 ordena responder `aplicable=false, nivel=null` ante un tweet ajeno al criterio. Son dos codificaciones de lo mismo y la regla gana casi siempre: sobre los 7,708 pares resueltos, 7,586 salieron como `aplicable=false` y sólo 12 (0.16%) como nivel «0». Lo que hay no es un colapso limpio sino una inconsistencia, y esos 12 ceros no son comparables con el resto. Resolver esa colisión —y lo que implica para el criterio binario, ver Riesgos— es un cambio propio, de modelado, no de traslado.
- No se cambia el modelo, la temperatura, el presupuesto de razonamiento ni el esquema de salida.
- No se rediseñan las gráficas ni el formato de exportación.
- No se reconstruyen los hilos de las respuestas sin contexto.
- No se introduce base de datos: el checkpoint JSONL y los CSV siguen siendo la frontera entre etapas.

## Decisions

### 1. Paquete ejecutable + cuaderno congelado como memoria, no monolito ni `nbconvert`

Se extrae la lógica a `evaluador/` y el `.ipynb` deja de ejecutarse. No se adelgaza para importar el paquete: se conserva tal cual, como registro de cómo se llegó al diseño actual.

| Alternativa | Por qué no |
|---|---|
| `evaluador.py` monolítico | Concatenar 2,800 líneas conserva el problema de navegación |
| `nbconvert --execute` / papermill | No arregla nada: el estado oculto y el orden de celdas siguen ahí; sólo automatiza el disparo |
| Sólo portar el motor, dejar el resto en celdas | Descartado por el usuario (traslado total), y dejaría la misma frontera frágil entre celda 22 y 25 |
| Cuaderno delgado que importa el paquete | Descartado por el usuario: el cuaderno no debe accionar nada. Mantenerlo ejecutable obligaría a una celda de arranque que instala el paquete, y esa celda vuelve a ser un punto de fallo de orden — el mismo que causó la corrida 20 |

La resolución de nombres al importar es el punto entero del ejercicio: `from evaluador.scoring import evaluar_payload` revienta en el segundo cero si el símbolo no existe. Es estructuralmente imposible reproducir el fallo de la corrida 20.

Que el cuaderno deje de ser ejecutable no lo degrada: lo libera. Ya no tiene que mantenerse sincronizado con el código, y por tanto no puede divergir en silencio. La prosa que contiene —por qué el corte es el 6 de julio, por qué el primer período empieza el 31 de mayo, por qué el cliente asíncrono no sobrevive a `nest_asyncio`— es conocimiento que ningún módulo va a albergar mejor.

### 2. La frontera entre módulos es el artefacto en disco, no la llamada a función

El cuaderno ya está desacoplado por archivos: `turistas_reparado.csv`, `turistas_traducido.csv`, `rubrica.json`, `checkpoint*.jsonl`, los CSV de salida, el HTML. El acoplamiento por globales es casi todo *intra*-etapa.

```
  xlsx ──▶ reparar ──▶ *_reparado.csv ──▶ traducir ──▶ *_traducido.csv ──┐
  pdf  ──▶ rubrica ──▶ rubrica.json ─────────────────────────────────────┤
                                                                         ▼
                                              correr ──▶ checkpoint.jsonl
                                                              │
                                         ┌────────────────────┴──────────┐
                                         ▼                               ▼
                                    exportar ──▶ csv            graficar ──▶ html
```

Se respeta tal cual. Cada subcomando del CLI es una etapa, lee sus insumos de disco y escribe su artefacto. Ventaja concreta: las etapas caras ya hechas (reparación, traducción al 99.8%) no se vuelven a ejecutar ni a validar, y cada una sigue siendo reanudable por separado.

### 3. El semáforo cuenta llamadas; el fan-out se declara, no se descubre

Hoy `asyncio.Semaphore(CONCURRENCIA)` se adquiere por **fila**, y cada fila dispara un `ParallelAgent` que abanica N sub-agentes. Con 4 criterios, `CONCURRENCIA=8` son 32 peticiones en vuelo y nada lo dice.

Se invierte el parámetro: se configura `LLAMADAS_SIMULTANEAS` y las filas se derivan.

```python
filas_en_vuelo = max(1, LLAMADAS_SIMULTANEAS // N_CRITERIOS)
```

Alternativas consideradas:

- **Abandonar `ParallelAgent` y lanzar un runner por criterio**, con semáforo exacto por llamada. Da contabilidad perfecta, pero es el refactor más grande y sacrifica el aislamiento que la celda 20 verifica con un `assert`. No se justifica todavía.
- **Limitador por tokens (TPM)**, que es el techo real en Tier 1. Es lo más correcto para el constraint verdadero, y también lo más complejo. **La evidencia no lo pide**: en 27,748 registros no hay un solo `LIMITE_TASA`, `ERROR_SERVIDOR` ni `BLOQUEADO`, y las diecinueve primeras corridas fueron limpias. Construir un cubo de tokens ahora sería resolver un problema que el dato no muestra. Se deja anotado para cuando aparezca.

La decisión se toma por ser la mínima que **declara** el fan-out real, no por ser la más sofisticada.

### 4. Los fallos deterministas abortan; los transitorios se reintentan

`_motivo_fallo` gana una clase `PERMANENTE`. `NameError`, `ImportError` y `AttributeError` no pueden depender del dato en esta ruta de código: si ocurren, ocurren para todas las filas. Reintentarlos cinco veces con retroceso costó del orden de cuatro horas de sueño inútil.

- **Triada estructural** (`NameError`, `ImportError`, `AttributeError`) → aborta la corrida completa de inmediato, propagando el traceback sin envolverlo.
- **Dependientes del dato** (`KeyError`, `ValueError`, errores de validación) → se registran en la fila y la corrida sigue: una fila rara no debe matar 2,562.
- **Cortacircuitos** como segunda red: si las primeras `K` filas consecutivas fallan todas, se aborta sea cual sea la clase. Cubre el caso que la lista de excepciones no anticipó, que es exactamente lo que pasó esta vez.

Se prefiere abortar sobre continuar porque el checkpoint es append-only y persistente: una corrida que sigue adelante con un error estructural no produce menos dato, produce **dato falso y permanente**.

### 5. Reanudar filtra por estado; el fallo deja de ser trabajo terminado

```python
# antes
hechas.add((str(r["tweet_id"]), r["slug"]))              # todo cuenta

# después
if r.get("estado") in {"OK", "NO_APLICABLE"}:
    hechas.add((str(r["tweet_id"]), r["slug"]))          # sólo lo resuelto
```

`NO_APLICABLE` **sí** es un resultado terminado: es el modelo respondiendo que el criterio no aplica, no un fallo. Confundirlo con error dispararía la recalificación del 74% del corpus y multiplicaría el gasto sin razón.

Dicho eso, hay casos legítimos para recalificar más que los fallos —cambió la instrucción, cambió el modelo, se quiere medir estabilidad— así que el alcance se declara en vez de quedar fijo:

| Alcance | Qué recalifica | Pares hoy | Costo aprox. |
|---|---|---|---|
| `fallidos` (por defecto) | `ERROR` y `SIN_RESPUESTA` | 2,540 | ~$1 |
| `sin-nivel` | lo anterior más `NO_APLICABLE` | 10,126 | ~$4 |
| `todo` | la selección entera, ignorando el checkpoint | 10,248 | ~$4 |

`fallidos` es el único que no repite gasto ya hecho, y por eso es el defecto. Los otros dos reportan el conteo y el costo antes de pedir confirmación, y `todo` advierte explícitamente que está repitiendo trabajo pagado.

La diferencia entre `sin-nivel` y `todo` es pequeña hoy (122 pares `OK`) pero conceptualmente distinta: `sin-nivel` consulta el checkpoint para decidir, `todo` no lo consulta en absoluto. El segundo es el que sirve cuando se sospecha que los resultados previos son inválidos, no que falten.

En los tres casos el checkpoint es append-only: los registros previos no se borran, y la lectura resuelve cada par por su registro válido más reciente. Una recalificación interrumpida a la mitad nunca deja el archivo peor que como estaba.

Es un cambio de comportamiento observable —reanudar sobre un checkpoint con fallos ahora gasta dinero— y por eso va marcado como **BREAKING** en la propuesta. Es también el único camino para desbloquear los 2,540 pares.

La política de deduplicación en lectura pasa de `keep="last"` a *último bueno, si no hay ninguno el último*. Hoy da idéntico resultado (verificado: cero pares afectados), pero una vez que los fallos se reintentan, la secuencia `ERROR → OK` se vuelve común y la regla debe ser explícita.

### 6. El resultado parcial es una excepción, no un retorno

Cuando el `ParallelAgent` devuelve menos claves de estado que criterios pedidos, `_evaluar_fila` hoy construye registros `SIN_RESPUESTA` y **retorna**. Al no haber excepción, el bucle `for intento in range(MAX_INTENTOS)` nunca se activa: los cinco reintentos escritos para este caso jamás corren, y el hueco se escribe como definitivo.

Se lanza una excepción interna con las claves faltantes. El reintento existente la captura y la ruta ya escrita empieza por fin a usarse. Sólo tras agotar los intentos se materializa `SIN_RESPUESTA`, que ahora además será reintentable en la siguiente corrida por la decisión 5.

### 7. Reintento HTTP con techo y ruido

`RETRY_OPTIONS(attempts=5, exp_base=7, initial_delay=1)` con `max_delay=None` —verificado en `google-genai 1.66.0`— produce esperas de 1 s → 7 s → 49 s → **343 s**. Casi seis minutos de silencio son indistinguibles de un cuelgue, y con el reintento externo anidado el peor caso por fila ronda los 34 minutos.

Pasa a base 2, `max_delay` acotado y `jitter` activo, para que los reintentos no se sincronicen entre las llamadas en vuelo.

### 8. Las dependencias del entorno alojado se eliminan, no se abstraen

`files.upload()`, `files.download()`, `drive.mount()` e `IPython.display` están repartidos en seis celdas. **No se trasladan.** En un proceso local no significan nada: los archivos ya están en disco, las salidas se escriben donde se configuró, y el HTML se abre en el navegador.

La alternativa considerada y descartada era un módulo adaptador que detectara el entorno y despachara a una u otra implementación. Tenía sentido mientras Colab siguiera siendo un destino; sin esa dualidad es abstracción sin segundo caso, y añade una capa de indirección que sólo sirve para ocultar dónde se lee un archivo.

Lo que sí sobrevive es el comportamiento que hacía valiosa la abstracción: un archivo de entrada ausente produce un error que nombra la ruta esperada y la etapa que la genera. Hoy produce `ImportError: google.colab`, que manda a diagnosticar el problema equivocado. Eso pasa a ser una utilidad de lectura en `corpus.py` y `rubrica.py`, no un módulo propio.

### 9. Configuración por perfiles en archivo, no por edición de celda

`config.toml` con perfiles `piloto` y `completo`, seleccionados por bandera. Python 3.11+ trae `tomllib`, así que no añade dependencia.

El síntoma que lo motiva ya ocurrió: el CONFIG declara `CHECKPOINT_PATH = "checkpoint.jsonl"` y en disco hay `checkpoint_piloto.jsonl`. La celda se editó a mano, y esa edición no queda registrada en ninguna parte. Un perfil es reproducible y diffeable; una celda editada no.

La clave de API nunca vive en el archivo de perfiles: se lee de `GOOGLE_API_KEY` o de un archivo ignorado por git.

### 10. `nest_asyncio` se elimina de las dependencias

Fuera de un cuaderno no hay bucle corriendo: `asyncio.run()` basta. Con ello se disuelve —no se parchea— la incompatibilidad que la celda 9.6 documenta: *«el cliente `.aio` de google-genai levanta 'Timeout should be used inside a task' bajo nest_asyncio… la misma incompatibilidad afecta a ADK cuando se corre fuera de Colab»*.

Al no quedar ningún entorno con bucle preexistente, el paquete no declara `nest_asyncio` ni condicionalmente. Es la dependencia que se va entera.

El rodeo `asyncio.to_thread(_llamar_sync, ...)` de la traducción se conserva sin tocar: funciona al 99.8% sobre 2,562 llamadas y no hay razón para arriesgarlo en este cambio.

### 11. La auditoría del checkpoint es un comando de primera clase

`python -m evaluador auditar <checkpoint>` reporta desglose de estados, pares duplicados, estado final por par, y **discrepancia de criterios frente a `rubrica.json`**. Este último caso ya está presente: el checkpoint trae cuatro criterios (`rubrica_4_saliencia_de_violencia`) y el `rubrica.json` en disco tiene tres.

`correr` rehúsa reanudar sobre un checkpoint cuyos criterios no coincidan con la rúbrica vigente, salvo bandera explícita. Mezclar dos rúbricas en un mismo checkpoint produce un CSV cuyas columnas no significan lo mismo en todas las filas, y eso no se detecta después.

## Risks / Trade-offs

**El muestreo por semilla no es reproducible si el corpus cambia de tamaño** → Durante el traslado el corpus pasó de 2,562 a 2,631 filas, y `sample(n=60, random_state=42)` devolvió 60 tuits de los que **sólo 1** coincidía con la selección original. El piloto de fidelidad habría comparado conjuntos distintos y la divergencia se habría leído como fallo del traslado. Mitigación implementada: `seleccionar()` acepta una lista explícita de identificadores, y `ids_de_checkpoint()` la extrae de una corrida anterior. La comparación deja de depender del tamaño del corpus.

**El corpus creció con filas cuyo identificador está destruido** → Las 69 filas de `Queries Lugares - complemento.csv` llegaron con el `id` en notación científica de Excel (`2.06E+18`). En 15 se recuperó de `raw_json`; en las **54 restantes el `raw_json` viene vacío** (`id: None`) y el texto no aparece en las 14,635 filas de `TotalQueries` ni tras normalizar y reparar el mojibake. Es el mismo daño que la etapa de reparación existe para revertir, pero esta vez sin fuente de verdad. Esas 54 filas colapsan a 3 cadenas de identificador: calificarlas produciría 3 resultados sobrescritos 17 veces cada uno. Decisión del usuario: **reexportar el complemento desde su origen con la columna `id` como texto**. Hasta entonces quedan fuera de toda corrida. Los 2,577 con identificador válido no están afectados, y los 2,562 tuits del checkpoint recuperable siguen presentes en su totalidad.


**Reanudar ahora cuesta dinero donde antes era gratis** → Es el objetivo, pero puede sorprender. `correr` reporta cuántos pares va a recalificar y cuánto estima que cuesta **antes** de emitir la primera llamada, respetando la compuerta de confirmación de gasto que ya existe.

**El traslado puede introducir bugs nuevos indistinguibles de los viejos** → Se corre un piloto de 60 filas con el mismo `SEED` antes y después, y se comparan los resultados par a par. El «antes» ya existe: `checkpoint_piloto.jsonl`, 180 registros, 1 solo fallo.

**Python 3.14 con ADK 1.26 es terreno reciente** → **Resuelto: se usa Python 3.12.10 en entorno virtual.** El global del equipo es 3.14, donde todo importaba, pero 3.14 está por delante del soporte declarado de ADK y no hay razón para correr una carga de pago sobre esa apuesta. 3.12 conserva `tomllib` en la biblioteca estándar, así que los perfiles no añaden dependencia.

**pandas 3.0 rompe la lectura del corpus** → El global del equipo traía pandas 3.0.1, que cambia el tipo por defecto de las columnas de texto y el manejo de ausentes. Todo el pipeline depende de leer con `dtype=str` y `keep_default_na=False` para que los identificadores de tuit de 19 dígitos no pasen por `float64` y pierdan precisión — el mismo daño que la celda 8.5 existe para reparar. Mitigación: `pandas>=2.2,<3.0` fijado en `requirements.txt`; el entorno virtual quedó en 2.3.3. Migrar a 3.x exigirá revalidar la lectura, no es transparente.

Verificado sobre las versiones fijadas: `retry_options` sigue siendo campo real de `Gemini` en ADK 1.26, y `api_key` / `vertexai` siguen sin serlo, tal como advierte la celda 7 del cuaderno.

**El cuaderno congelado envejece y empieza a mentir** → Al dejar de ejecutarse, nada obliga a que su contenido siga correspondiendo al código. Un lector futuro puede tomar una celda como descripción del comportamiento vigente cuando ya no lo es. Mitigación: una nota al inicio del cuaderno que declare explícitamente su condición de registro histórico, con la fecha y el commit en que dejó de ser ejecutable, y que remita al paquete como fuente de verdad del comportamiento.

**Perder la ejecución en Colab elimina el único entorno de respaldo** → Si el equipo local falla, ya no hay dónde correr el pipeline sin trabajo de reconstrucción. Es una consecuencia aceptada de la decisión: el corpus y los checkpoints ya viven en local, y las corridas largas eran precisamente lo que Colab no sostenía.

**Abortar por cortacircuitos puede matar una corrida larga por una racha desafortunada** → `K` se configura y se registra en el log el motivo exacto del aborto. El checkpoint es append-only con `flush` inmediato, así que lo ya calculado sobrevive y la reanudación continúa desde ahí.

**El criterio binario queda roto y este cambio no lo arregla** → El PDF vigente define cuatro criterios: tres ordinales 0–5 (simpática/emocional, estética, funcional) y uno **binario 0/1**, saliencia de violencia, que detecta presencia del tema sin valencia. Para un detector de presencia, «violencia ausente» es la respuesta sustantiva `0`; la regla 1 la convierte en `aplicable=false`. El criterio sólo puede devolver «fuera de alcance» o `1`, y su nivel `0` es inalcanzable: se pierde la distinción entre *no aplica* y *ausencia medida*. Los datos lo confirman: de los 1,931 pares resueltos del criterio 4, hubo 1,908 `aplicable=false` contra 11 `nivel=0` y 12 `nivel=1` — el detector de presencia respondió su propia pregunta 23 veces. Se declara fuera de alcance para no mezclar traslado con modelado, pero debe atenderse antes de la corrida definitiva.

**La configuración de visualización asume una sola escala para todos los criterios** → `ESCALA_NIVELES = "divergente"` describe una escala de valencia y vale para los criterios 1–3; aplicada al binario no significa nada. `NIVELES_AUSENCIA = "auto"` detecta la etiqueta «0» como ausencia, lo cual es correcto para 1–3 y exactamente inverso para el 4, donde el `0` es un hallazgo. Hoy el problema está casi latente: sobre 7,708 pares resueltos el nivel «0» se asignó 12 veces (0.16%) frente a 7,586 `aplicable=false`. No es un colapso limpio sino una inconsistencia — la misma situación se codifica de dos formas — y esos 12 ceros ya no son comparables con el resto. En cuanto se resuelva la colisión, el problema deja de ser marginal. Ambos parámetros necesitarán ser por criterio, no globales.

**El éxito técnico del traslado puede leerse como que el pipeline ya está listo** → No lo está. Con la plantilla de instrucción actual, la corrida completa seguirá devolviendo ~1% de calificaciones con nivel asignado, y el criterio binario seguirá sin poder decir `0`.

## Migration Plan

1. **Sacar la credencial y poner el proyecto bajo git.** `.gitignore` antes del primer commit; `apikey.txt` fuera del árbol.
2. **Entorno virtual con versiones fijadas.** Verificar que el pipeline importa y que la prueba de humo pasa.
3. **Trasladar por etapas, de la más barata a la más cara**: `config` → `rubrica` → `corpus` → `traduccion` → `scoring` → `export` → `viz`. Cada etapa se verifica contra su artefacto en disco ya existente en cuanto se traslada, de modo que nunca hay un momento en que nada funcione.
4. **Piloto «antes»**: 60 filas con `SEED=42` sobre el paquete recién trasladado y el motor **sin** arreglar. Se contrasta contra `checkpoint_piloto.jsonl` para confirmar que el traslado fue fiel.
5. **Aplicar los cuatro arreglos del motor** (decisiones 3 a 7).
6. **Piloto «después»**: mismas 60 filas, checkpoint limpio. Comparación par a par.
7. **Auditar e incorporar `checkpoint (7).jsonl`**, confirmar el reparto 7,708 / 2,540 y la discrepancia de criterios.
8. **Recalificación selectiva** de los 2,540 pares, una vez reconciliada la rúbrica.
9. **Marcar el cuaderno como registro documental**: nota inicial que declara su condición de memoria histórica, con fecha y commit en que dejó de ser ejecutable, y remisión al paquete como fuente de verdad. El contenido de las celdas no se toca.

Reversa: el cuaderno original queda íntegro en el primer commit, y todos los artefactos de datos mantienen su formato. Revertir es dejar de usar el paquete y volver a ejecutar el cuaderno, que sigue siendo capaz de correr aunque se haya decidido no hacerlo.

## Open Questions

- ~~¿Repositorio propio o `.zip` a Colab?~~ **Resuelto: ninguno.** El usuario descartó Colab como destino. Todo corre en local y el paquete no se distribuye a ninguna parte. El repositorio se conserva por control de versiones, no por distribución.
- ~~¿Se reconcilia la rúbrica a 4 criterios o a 3?~~ **Resuelto.** El PDF ya está actualizado y es la fuente de verdad: cuatro criterios, tres ordinales 0–5 más el binario 0/1 de saliencia de violencia. El `rubrica.json` en disco (tres criterios, escrito antes que el PDF) está obsoleto y se regenera reparseando el PDF. El criterio 4 del checkpoint corresponde al del PDF, así que los 7,708 pares se recuperan completos. Queda una verificación, no una decisión: que los `slug` y las etiquetas del reparseo coincidan con los del checkpoint, ya que el emparejamiento es por `(tweet_id, slug)`.
- **¿Cómo se declara que un criterio es binario y sin valencia?** `rubrica.json` hoy distingue escala numérica de nominal, pero no *tipo* de escala. El binario de presencia no es ni logro ni valencia. Afecta a `ESCALA_NIVELES` y `NIVELES_AUSENCIA`, hoy globales. Probablemente pertenezca al cambio de modelado, pero el esquema de `rubrica.json` que este cambio traslada debería dejar el hueco previsto.
- **¿Cuánto vale `K` en el cortacircuitos?** Demasiado bajo mata corridas sanas; demasiado alto deja pasar otra corrida 21. Un valor inicial conservador y ajustable parece suficiente, pero no hay dato para fijarlo.
- ~~¿El cuaderno delgado debe poder correr sin el paquete?~~ **Resuelto: el cuaderno no se adelgaza.** Deja de ser ejecutable y se conserva íntegro como memoria del proyecto. No hay celda de arranque, y por tanto no hay punto de fallo de orden.
