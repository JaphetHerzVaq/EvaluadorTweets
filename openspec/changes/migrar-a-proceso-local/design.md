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

Restricciones que enmarcan el diseño: Colab se conserva como destino; el traslado es total (todas las etapas, no sólo el motor); el entorno local es Windows con Python 3.14 y `google-adk 1.26.0` / `google-genai 1.66.0` ya instalados; el proyecto todavía no está bajo control de versiones y `apikey.txt` está en el árbol en texto plano.

## Goals / Non-Goals

**Goals:**

- Que un símbolo ausente falle al arrancar el proceso, no a las cuatro horas y 15,000 llamadas.
- Que reanudar una corrida repare los fallos en vez de preservarlos.
- Que la concurrencia declarada sea la concurrencia real.
- Que un error de programación aborte la corrida de inmediato con su traceback, en vez de consumirse en reintentos.
- Recuperar los 7,708 pares ya pagados y recalificar sólo los 2,540 fallidos.
- Que el mismo código corra en local y en Colab, con una sola definición de cada función.
- Conservar íntegra la prosa del cuaderno: las limitaciones conocidas, la justificación de los cortes de período, las notas sobre `nest_asyncio` y ADK. Es documentación ganada con dolor.

**Non-Goals:**

- **No se toca la semántica de la rúbrica ni la plantilla de instrucción.** El 74% de `NO_APLICABLE` sobre los pares sanos (7,586 de 7,708; sólo 122 `OK` = 1.2%) **no** es señal de que la rúbrica no corresponda al corpus: es la regla 1 de `instruccion_para` funcionando como está escrita. La rúbrica define el nivel «0» como ausencia de la dimensión, y la regla 1 ordena responder `aplicable=false, nivel=null` ante un tweet ajeno al criterio. Son dos codificaciones de lo mismo, y la regla gana siempre, dejando el nivel «0» inalcanzable. Resolver esa colisión —y lo que implica para el criterio binario, ver Riesgos— es un cambio propio, de modelado, no de traslado.
- No se cambia el modelo, la temperatura, el presupuesto de razonamiento ni el esquema de salida.
- No se rediseñan las gráficas ni el formato de exportación.
- No se reconstruyen los hilos de las respuestas sin contexto.
- No se introduce base de datos: el checkpoint JSONL y los CSV siguen siendo la frontera entre etapas.

## Decisions

### 1. Paquete importado + cuaderno delgado, no monolito ni `nbconvert`

Se extrae la lógica a `evaluador/` y el `.ipynb` pasa a importarla.

| Alternativa | Por qué no |
|---|---|
| `evaluador.py` monolítico | Concatenar 2,800 líneas conserva el problema de navegación y tira la prosa del cuaderno |
| `nbconvert --execute` / papermill | No arregla nada: el estado oculto y el orden de celdas siguen ahí; sólo automatiza el disparo |
| Sólo portar el motor, dejar el resto en celdas | Descartado por el usuario (traslado total), y dejaría la misma frontera frágil entre celda 22 y 25 |

La resolución de nombres al importar es el punto entero del ejercicio: `from evaluador.scoring import evaluar_payload` revienta en el segundo cero si el símbolo no existe. Es estructuralmente imposible reproducir el fallo de la corrida 20.

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

Es un cambio de comportamiento observable —reanudar sobre un checkpoint con fallos ahora gasta dinero— y por eso va marcado como **BREAKING** en la propuesta. Es también el único camino para desbloquear los 2,540 pares.

La política de deduplicación en lectura pasa de `keep="last"` a *último bueno, si no hay ninguno el último*. Hoy da idéntico resultado (verificado: cero pares afectados), pero una vez que los fallos se reintentan, la secuencia `ERROR → OK` se vuelve común y la regla debe ser explícita.

### 6. El resultado parcial es una excepción, no un retorno

Cuando el `ParallelAgent` devuelve menos claves de estado que criterios pedidos, `_evaluar_fila` hoy construye registros `SIN_RESPUESTA` y **retorna**. Al no haber excepción, el bucle `for intento in range(MAX_INTENTOS)` nunca se activa: los cinco reintentos escritos para este caso jamás corren, y el hueco se escribe como definitivo.

Se lanza una excepción interna con las claves faltantes. El reintento existente la captura y la ruta ya escrita empieza por fin a usarse. Sólo tras agotar los intentos se materializa `SIN_RESPUESTA`, que ahora además será reintentable en la siguiente corrida por la decisión 5.

### 7. Reintento HTTP con techo y ruido

`RETRY_OPTIONS(attempts=5, exp_base=7, initial_delay=1)` con `max_delay=None` —verificado en `google-genai 1.66.0`— produce esperas de 1 s → 7 s → 49 s → **343 s**. Casi seis minutos de silencio son indistinguibles de un cuelgue, y con el reintento externo anidado el peor caso por fila ronda los 34 minutos.

Pasa a base 2, `max_delay` acotado y `jitter` activo, para que los reintentos no se sincronicen entre las llamadas en vuelo.

### 8. Un solo adaptador de entorno, detectado por capacidad

`files.upload()`, `files.download()`, `drive.mount()` e `IPython.display` están repartidos en seis celdas. Pasan a `evaluador/io_.py`, con detección por `importlib.util.find_spec("google.colab")` y no por variable de entorno ni por try/except disperso.

En local, un archivo ausente produce `FileNotFoundError` con la ruta esperada. Hoy produce `ImportError: google.colab`, que manda a diagnosticar el problema equivocado.

### 9. Configuración por perfiles en archivo, no por edición de celda

`config.toml` con perfiles `piloto` y `completo`, seleccionados por bandera. Python 3.11+ trae `tomllib`, así que no añade dependencia.

El síntoma que lo motiva ya ocurrió: el CONFIG declara `CHECKPOINT_PATH = "checkpoint.jsonl"` y en disco hay `checkpoint_piloto.jsonl`. La celda se editó a mano, y esa edición no queda registrada en ninguna parte. Un perfil es reproducible y diffeable; una celda editada no.

La clave de API nunca vive en el archivo de perfiles: se lee de `GOOGLE_API_KEY` o de un archivo ignorado por git.

### 10. `nest_asyncio` desaparece en local

Fuera de Colab no hay bucle corriendo: `asyncio.run()` basta. Con ello se disuelve —no se parchea— la incompatibilidad que la celda 9.6 documenta: *«el cliente `.aio` de google-genai levanta 'Timeout should be used inside a task' bajo nest_asyncio… la misma incompatibilidad afecta a ADK cuando se corre fuera de Colab»*. El adaptador aplica `nest_asyncio` **sólo** cuando detecta Colab.

El rodeo `asyncio.to_thread(_llamar_sync, ...)` de la traducción se conserva sin tocar: funciona al 99.8% sobre 2,562 llamadas y no hay razón para arriesgarlo en este cambio.

### 11. La auditoría del checkpoint es un comando de primera clase

`python -m evaluador auditar <checkpoint>` reporta desglose de estados, pares duplicados, estado final por par, y **discrepancia de criterios frente a `rubrica.json`**. Este último caso ya está presente: el checkpoint trae cuatro criterios (`rubrica_4_saliencia_de_violencia`) y el `rubrica.json` en disco tiene tres.

`correr` rehúsa reanudar sobre un checkpoint cuyos criterios no coincidan con la rúbrica vigente, salvo bandera explícita. Mezclar dos rúbricas en un mismo checkpoint produce un CSV cuyas columnas no significan lo mismo en todas las filas, y eso no se detecta después.

## Risks / Trade-offs

**Reanudar ahora cuesta dinero donde antes era gratis** → Es el objetivo, pero puede sorprender. `correr` reporta cuántos pares va a recalificar y cuánto estima que cuesta **antes** de emitir la primera llamada, respetando la compuerta de confirmación de gasto que ya existe.

**El traslado puede introducir bugs nuevos indistinguibles de los viejos** → Se corre un piloto de 60 filas con el mismo `SEED` antes y después, y se comparan los resultados par a par. El «antes» ya existe: `checkpoint_piloto.jsonl`, 180 registros, 1 solo fallo.

**Python 3.14 con ADK 1.26 es terreno reciente** → Los imports ya se verificaron en este equipo, pero 3.14 está por delante del soporte declarado de ADK. Mitigación: entorno virtual con versiones fijadas, y caída a 3.12 o 3.13 si aparece incompatibilidad. Fijar versión también cierra la brecha con el `>=1.25.0` que declara el cuaderno.

**El cuaderno delgado puede volver a engordar** → Nada impide pegar lógica nueva en una celda, y el incentivo de hacerlo es alto durante una sesión de depuración. Mitigación cultural más que técnica: las celdas quedan cortas y con prosa, de modo que una celda larga se vea fuera de lugar.

**Distribuir el paquete a Colab obliga a resolver la clave primero** → `pip install git+...` requiere repositorio, y hoy `apikey.txt` está en el árbol en texto plano sin `.gitignore` ni `.git`. La extracción de la credencial es prerrequisito del primer commit, no una tarea de limpieza posterior. Alternativa de menor fricción si se quiere diferir el repositorio: subir un `.zip` del paquete a Colab a mano, a costa de que la versión en Colab pueda divergir sin que se note.

**Abortar por cortacircuitos puede matar una corrida larga por una racha desafortunada** → `K` se configura y se registra en el log el motivo exacto del aborto. El checkpoint es append-only con `flush` inmediato, así que lo ya calculado sobrevive y la reanudación continúa desde ahí.

**El criterio binario queda roto y este cambio no lo arregla** → El PDF vigente define cuatro criterios: tres ordinales 0–5 (simpática/emocional, estética, funcional) y uno **binario 0/1**, saliencia de violencia, que detecta presencia del tema sin valencia. Para un detector de presencia, «violencia ausente» es la respuesta sustantiva `0`; la regla 1 la convierte en `aplicable=false`. El criterio sólo puede devolver «fuera de alcance» o `1`, y su nivel `0` es inalcanzable: se pierde la distinción entre *no aplica* y *ausencia medida*. Los datos lo confirman — criterio 4: 3,055 `NO_APLICABLE` contra 36 `OK`. Se declara fuera de alcance para no mezclar traslado con modelado, pero debe atenderse antes de la corrida definitiva.

**La configuración de visualización asume una sola escala para todos los criterios** → `ESCALA_NIVELES = "divergente"` describe una escala de valencia y vale para los criterios 1–3; aplicada al binario no significa nada. `NIVELES_AUSENCIA = "auto"` detecta la etiqueta «0» como ausencia, lo cual es correcto para 1–3 y exactamente inverso para el 4, donde el `0` es un hallazgo. Hoy el problema está latente porque ningún nivel «0» se ha asignado nunca. En cuanto se resuelva la colisión anterior, aparece. Ambos parámetros necesitarán ser por criterio, no globales.

**El éxito técnico del traslado puede leerse como que el pipeline ya está listo** → No lo está. Con la plantilla de instrucción actual, la corrida completa seguirá devolviendo ~1% de calificaciones con nivel asignado, y el criterio binario seguirá sin poder decir `0`.

## Migration Plan

1. **Sacar la credencial y poner el proyecto bajo git.** `.gitignore` antes del primer commit; `apikey.txt` fuera del árbol.
2. **Entorno virtual con versiones fijadas.** Verificar que el pipeline importa y que la prueba de humo pasa.
3. **Trasladar por etapas, de la más barata a la más cara**: `config` → `io_` → `rubrica` → `corpus` → `traduccion` → `scoring` → `export` → `viz`. Tras cada una, el cuaderno debe seguir corriendo importando lo ya trasladado. Nunca hay un momento en que nada funcione.
4. **Piloto «antes»**: 60 filas con `SEED=42` sobre el paquete recién trasladado y el motor **sin** arreglar. Se contrasta contra `checkpoint_piloto.jsonl` para confirmar que el traslado fue fiel.
5. **Aplicar los cuatro arreglos del motor** (decisiones 3 a 7).
6. **Piloto «después»**: mismas 60 filas, checkpoint limpio. Comparación par a par.
7. **Auditar e incorporar `checkpoint (7).jsonl`**, confirmar el reparto 7,708 / 2,540 y la discrepancia de criterios.
8. **Recalificación selectiva** de los 2,540 pares, una vez reconciliada la rúbrica.
9. **Adelgazar el cuaderno** y verificar que corre de principio a fin en una sesión limpia de Colab.

Reversa: el cuaderno original se conserva íntegro hasta completar el paso 9. Mientras tanto sigue siendo ejecutable tal cual, y todos los artefactos de datos mantienen su formato, así que revertir es dejar de usar el paquete.

## Open Questions

- **¿Repositorio propio o `.zip` a Colab?** Determina si el paso 1 bloquea al paso 9. Un repositorio privado es lo que escala; el `.zip` deja de ser viable en cuanto el paquete cambie a menudo.
- ~~¿Se reconcilia la rúbrica a 4 criterios o a 3?~~ **Resuelto.** El PDF ya está actualizado y es la fuente de verdad: cuatro criterios, tres ordinales 0–5 más el binario 0/1 de saliencia de violencia. El `rubrica.json` en disco (tres criterios, escrito antes que el PDF) está obsoleto y se regenera reparseando el PDF. El criterio 4 del checkpoint corresponde al del PDF, así que los 7,708 pares se recuperan completos. Queda una verificación, no una decisión: que los `slug` y las etiquetas del reparseo coincidan con los del checkpoint, ya que el emparejamiento es por `(tweet_id, slug)`.
- **¿Cómo se declara que un criterio es binario y sin valencia?** `rubrica.json` hoy distingue escala numérica de nominal, pero no *tipo* de escala. El binario de presencia no es ni logro ni valencia. Afecta a `ESCALA_NIVELES` y `NIVELES_AUSENCIA`, hoy globales. Probablemente pertenezca al cambio de modelado, pero el esquema de `rubrica.json` que este cambio traslada debería dejar el hueco previsto.
- **¿Cuánto vale `K` en el cortacircuitos?** Demasiado bajo mata corridas sanas; demasiado alto deja pasar otra corrida 21. Un valor inicial conservador y ajustable parece suficiente, pero no hay dato para fijarlo.
- **¿El cuaderno delgado debe poder correr sin el paquete?** Es decir, ¿se acepta que abrir el `.ipynb` en un Colab nuevo requiera un paso de instalación previo? Si no, hay que mantener una celda de arranque que clone o instale, y esa celda vuelve a ser un punto de fallo de orden.
