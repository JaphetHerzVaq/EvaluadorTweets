## Context

`Ajuste Evaluador` (en `C:\Users\japhe\Ajuste Evaluador`) es un sistema de evaluación por rúbrica construido sobre Google ADK 1.25.0 y Vertex AI. Su arquitectura es:

```
SequentialAgent (FeedbackSystem)
├── ParallelAgent (ParallelFeedbackTeamAgent)          ← 11 criterios en paralelo
│   ├── SequentialAgent (Q1_VotingPipeline)
│   │   ├── ParallelAgent (Q1_VoterPanel)              ← 3 modelos en paralelo
│   │   │   ├── ReviewerAgent gemini-2.5-pro
│   │   │   ├── ReviewerAgent gemini-2.5-flash
│   │   │   └── ReviewerAgent gemini-2.5-flash-lite
│   │   └── Agent (Q1_VoteAggregator) → state["q1_feedback"]
│   └── ... × 11 criterios
└── Agent (ParallelReviewersAggregatorAgent) → state["final_feedback"]
```

Ese sistema procesa **un documento largo** (una transcripción de conversación comercial) por corrida: 11 criterios × 3 votantes = 33 llamadas para un solo documento. La rúbrica vive en un corpus RAG de Vertex AI y cada agente la consulta con una herramienta de retrieval. Los puntajes se extraen del texto libre con una expresión regular sobre `**Puntuación: X.X**`.

El caso presente **invierte la escala**: 14,635 documentos cortos (tweets, media de 359 caracteres) contra una rúbrica de N criterios. Replicar el patrón tal cual daría del orden de 220,000 llamadas para el corpus completo con N=5, lo cual no es ejecutable en Colab ni económicamente razonable.

Restricciones del entorno:

- **Colab**: se desconecta sin aviso; ya tiene un event loop corriendo (ADK es asíncrono); subir 38 MB por el navegador es frágil.
- **Corpus**: 14,635 filas × 52 columnas. Multilingüe (61 % inglés, 12 % español, 10 % japonés, 2,268 filas sin `lang`). La columna `traducción` está llena sólo al 38 %. Las columnas `tipo` y `justificacion` existen y están completamente vacías. Hay 3,505 filas con `conversation_id` y 1,223 con `in_reply_to_user_id`.
- **Rúbrica**: el PDF todavía no existe en el proyecto. `N` y el tipo de escala son desconocidos al momento de diseñar.
- **Credenciales**: el `.env` de `Ajuste Evaluador` tiene `GOOGLE_API_KEY` comentada y explícitamente inutilizada (el código fuerza `api_key=None` para obligar el uso de ADC sobre el proyecto GCP `training-evaluator`). Contiene además claves vivas de OpenAI, Anthropic, Mistral y ElevenLabs en texto plano.

## Goals / Non-Goals

**Goals:**

- Un notebook de Colab autocontenido y ejecutable de principio a fin por alguien que no escribió el código.
- Agnóstico al número de criterios y al tipo de escala de la rúbrica: `N` y las columnas de salida se derivan del PDF en tiempo de ejecución.
- Costo lineal y predecible en `N`, conocido y confirmado antes de gastar.
- Sobrevivir a una desconexión de Colab sin perder trabajo hecho.
- Trazabilidad: cada calificación viene con su justificación y es atribuible a un criterio concreto de la rúbrica.
- Heredar de `Ajuste Evaluador` lo que está probado, descartando lo que no escala.

**Non-Goals:**

- **No** se usa el corpus RAG de Vertex AI. La rúbrica viaja en el prompt.
- **No** se usa voting multi-modelo en producción; sólo como instrumento de calibración.
- **No** se usa Vertex AI ni Application Default Credentials.
- **No** se usa la Batch API en el alcance inicial (ver Decisión 8).
- **No** se genera el reporte agregado global (`final_feedback`) que produce `Ajuste Evaluador`: aquí la unidad de análisis es la fila del CSV, no un informe narrativo.
- **No** se modifican las columnas existentes del CSV original, incluidas `tipo` y `justificacion`.
- **No** se reconstruyen hilos de conversación para dar contexto a los replies (ver Decisión 7).
- **No** se persiste nada en Firestore, a diferencia de `Ajuste Evaluador`.

## Decisions

### 1. La rúbrica se lee del PDF y se normaliza a JSON, sin RAG

Un `RubricParserAgent` recibe el PDF como `types.Part.from_bytes(mime_type="application/pdf")` —patrón ya usado en `main.py:139` de `Ajuste Evaluador`— y devuelve, con salida estructurada, un objeto de criterios y niveles. Ese JSON se materializa en disco y es revisable por un humano antes de lanzar la corrida.

*Alternativa descartada — corpus RAG de Vertex AI (lo que hace `Ajuste Evaluador`)*: exige crear e ingerir un corpus, permisos de IAM y una llamada de retrieval adicional por cada evaluación. A decenas de miles de llamadas, es latencia y costo puro. Además convierte la rúbrica en un recurso remoto opaco, mientras que el JSON local es un artefacto inspeccionable y versionable.

*Consecuencia favorable*: sin herramientas, los agentes de ADK **sí** pueden usar `output_schema` (en ADK son mutuamente excluyentes). La eliminación del RAG habilita la Decisión 3.

### 2. Agnosticismo a N y al tipo de escala

`N = len(rubrica.criterios)`. Los agentes, las columnas de salida y la estimación de costo se generan iterando sobre esa lista. La estructura de nivel es `{etiqueta, puntos?, descriptor}` con `puntos` **opcional**: si la rúbrica no asigna valores numéricos, se omite la columna de puntaje y el nivel nominal es el resultado. La lista de valores válidos se declara explícitamente en el prompt, replicando la táctica de `Ajuste Evaluador` de repetir la escala cerrada (`0.0, 0.2, 0.4, 0.6, 0.8, 1.0`) para impedir que el modelo invente valores intermedios.

*Alternativa descartada — criterios fijos en código*: es lo que hace `Ajuste Evaluador` con `_CRITERIA` y `_CRITERIA_CONTACTO`, y su propia evolución muestra el problema: tuvieron que añadir `CRITERIA_FILE` y `EVALUATOR_PROFILE` para salir de ahí. Empezar por los datos evita esa deuda.

### 3. Salida estructurada con Pydantic, no expresión regular sobre texto libre

Cada agente declara un `output_schema` con `nivel`, `puntaje`, `justificacion` y `aplicable`.

*Alternativa descartada — parseo con regex de `**Puntuación: X.X**`*: es el mecanismo de `Ajuste Evaluador`, y su fragilidad está documentada en su propio código, que necesita un agente árbitro instruido para ignorar valores fuera de escala. Con un documento por corrida, un fallo de parseo se detecta a ojo; con miles de filas, se convierte en pérdida silenciosa de datos.

### 4. `aplicable` es un campo propio, distinto del nivel más bajo

`Ajuste Evaluador` instruye asignar `0.0` cuando el documento no contiene respuesta al criterio. Esa regla es correcta evaluando a una persona que debía responder: no contestar es no saber. Aquí la unidad es un tweet ajeno que nunca intentó responder nada.

```
Criterio: "grado de victimización vivida en primera persona"
Tweet:    "Los mariscos en Tulum están carísimos 😤"

  colapsado en el nivel:  0.0   → contamina promedios y distribuciones
  con campo aplicable:    aplicable=false, nivel=null
```

Se conserva de `Ajuste Evaluador` la instrucción antialucinación (*no inventes, no infieras, no des crédito por contenido que no existe*), pero la salida distingue "bajo logro" de "fuera de alcance".

### 5. El paralelismo opera en dos ejes

```
   pool asyncio (Semaphore, concurrencia configurable)     ← eje de throughput
        │
        ├── fila 1 ──▶ ParallelAgent ──┬── Agente C1       ← eje heredado
        │                              ├── Agente C2         de Ajuste Evaluador
        │                              └── Agente CN
        ├── fila 2 ──▶ ParallelAgent ──┬── ...
        └── fila k ──▶ ...
```

El `ParallelAgent` sobre criterios preserva el aislamiento de prompts de `Ajuste Evaluador`: cada agente ve **sólo su criterio**, lo que evita que un criterio contamine el juicio de otro. El pool `asyncio` sobre filas aporta el throughput que el caso original no necesitaba. Se crea una sesión nueva por fila —`Ajuste Evaluador` ya lo hace deliberadamente para evitar fuga de estado entre trabajos— y el runner se recicla periódicamente para no acumular miles de sesiones en memoria.

*Alternativa descartada — un solo agente que califica todos los criterios en una llamada*: reduce el costo en un factor de N, pero pierde el aislamiento, produce un prompt que crece con la rúbrica y hace que un fallo arruine los N criterios de esa fila a la vez.

*Alternativa descartada — lotes de K tweets por llamada*: divide el costo entre K, pero si el modelo omite o reordena un tweet del lote, las calificaciones se desalinean de las filas de forma difícil de detectar.

### 6. `gemini-2.5-flash` con `thinking_budget=0`

| modelo | entrada / salida por 1M | thinking | costo por criterio (corpus completo) |
|---|---|---|---|
| `gemini-2.5-flash-lite` | $0.10 / $0.40 | apagable | $2.40 |
| **`gemini-2.5-flash`** | **$0.30 / $2.50** | **apagable** | **$11.11** |
| `gemini-3.7-flash` | $0.75 / $3.75 | piso `low` | $39.70 |
| `gemini-3.5-flash` | $1.50 / $9.00 | piso `low` | $91.40 |

La razón de la elección no es sólo el precio de lista, sino que en la familia 2.5 el razonamiento **se puede apagar** (`thinking_budget=0`), mientras que en `gemini-3.7-flash` el mínimo es `low` (`minimal` devuelve error). Los tokens de razonamiento se facturan como salida en todos los modelos, y el costo de esta tarea lo domina la salida; apagar el thinking ahorra por sí solo un factor de 2.7. Calificar un tweet contra un descriptor de rúbrica es clasificación con justificación, no orquestación multipaso.

`temperature=0.0`, frente al `0.2` de `Ajuste Evaluador`, que buscaba diversidad entre votantes. Sin voting, la reproducibilidad vale más: con `temperature=0` y thinking apagado la corrida es casi determinista, lo que hace significativos el checkpoint y el test-retest.

### 7. Los replies se marcan, no se reconstruyen

La primera fila del corpus es literalmente un reply (`@EricHeggie Mexico 🇲🇽 people are...`); hay al menos 1,223 filas con `in_reply_to_user_id`. Calificar un reply aislado es calificar media conversación.

Se añade una marca de contexto incompleto al payload y se advierte al modelo en el prompt, en lugar de reconstruir el hilo desde `conversation_id`. Reconstruir sólo funcionaría si el tweet padre estuviera en el corpus, lo cual generalmente no ocurre. La marca no arregla el problema, pero evita que el modelo alucine el contexto faltante y permite filtrar esas filas en el análisis posterior.

### 8. ADK interactivo ahora; Batch API queda como puerta abierta

| | ADK + ParallelAgent | Batch API |
|---|---|---|
| costo | precio completo | 50 % de descuento |
| forma | interactivo, fila por fila | job asíncrono, espera de horas |
| iteración de prompt | posible | no |
| desconexión de Colab | sobrevive con checkpoint | inmune |
| arquitectura | hereda `Ajuste Evaluador` | la descarta |

A 2,000 tweets el Batch ahorra del orden de cuatro dólares y cuesta el modo interactivo, que es justamente donde se itera el prompt y se revisan las justificaciones. Se implementa ADK interactivo. El diseño mantiene los prompts y el `rubrica.json` desacoplados del mecanismo de ejecución, de modo que una celda de Batch pueda añadirse después sin rediseñar nada si se escala al corpus completo.

### 9. Corrida reanudable por checkpoint, no por transacción

Un archivo JSONL append-only, una línea por `(tweet.id, criterio)` completado. Al arrancar se leen los identificadores ya presentes y se omiten. El notebook es idempotente: volver a ejecutar la celda continúa donde quedó.

*Alternativa descartada — acumular en memoria y escribir al final*: una desconexión a la hora dos pierde todo el trabajo y todo el dinero gastado.

### 10. El prompt pone el criterio primero y el tweet al final

Deja el prefijo idéntico entre todas las llamadas de un mismo criterio, lo que lo hace elegible para el caché implícito de Gemini (activado por defecto en 2.5+, 90 % de descuento en el prefijo).

Con un criterio por prompt el prefijo ronda los 700 tokens, por debajo del mínimo documentado (1,024–2,048 tokens), así que **no se espera acierto de caché**. Se exploró meter la rúbrica completa en el prefijo para cruzar el umbral: gana por márgenes pequeños y sólo en un rango medio de N ($45 frente a $56 con N=5; empate con N=15), a cambio de romper el aislamiento por criterio y de volver el costo no lineal en N. Se descarta por conflicto directo con el Goal de agnosticismo. El orden del prompt se mantiene de todas formas porque no cuesta nada y deja la puerta abierta.

### 11. Codificación `utf-8-sig` en la salida

El problema ya está documentado dentro de `Ajuste Evaluador`: su `criteria/criteria_prod.json` tiene mojibake (`¿Cu�l es la diferencia`), y el nombre de la columna `traducción` del propio CSV llega corrupto según cómo se lea. Con justificaciones en español, el BOM es lo que hace que Excel abra el archivo con los acentos intactos.

### 12. La calidad se mide, no se asume

Producir miles de calificaciones sin contraste no es un resultado, es un archivo. Tres mediciones, todas sobre muestras pequeñas y de costo marginal:

- **Distribución por criterio**: si un criterio concentra el 90 % de las filas en un solo nivel, o no aplica a tweets, o el descriptor se parseó mal del PDF, o el prompt está sesgado. Es la señal más barata y la más temprana.
- **Test-retest**: la misma muestra dos veces. Con `temperature=0` y thinking apagado debería ser casi idéntica; la desviación es el piso de ruido del sistema.
- **Acuerdo inter-modelo**: la misma muestra con `flash` y con `flash-lite`. Aquí es donde el voting de `Ajuste Evaluador` aporta de verdad: como métrica de confianza sobre 100 filas cuesta centavos, mientras que como mecanismo de producción triplicaría el costo sin evidencia de beneficio a este volumen.

## Risks / Trade-offs

- **`N` y el tipo de escala son desconocidos hasta cargar el PDF** → el diseño agnóstico permite construir el notebook sin ese dato; la celda estimadora reporta el costo real en cuanto la rúbrica se carga, antes de gastar.
- **La rúbrica puede no discriminar sobre tweets** (fue concebida para otro tipo de texto) → la corrida de muestra y el histograma por criterio lo revelan con un gasto del orden de un dólar, antes de la corrida completa.
- **El parseo del PDF puede salir mal en silencio** (criterios fusionados, niveles perdidos, descriptores truncados) → el `rubrica.json` es un punto de control humano obligatorio antes de la corrida; el conteo de criterios y de niveles por criterio se imprime para inspección.
- **Justificaciones largas inflan el costo de forma no obvia**: la salida domina el gasto, y `Ajuste Evaluador` instruye explícitamente *"Be thorough — do NOT be overly brief"*, lo que aquí llevaría de $1.51 a cerca de $3.00 por criterio → se acota el largo de la justificación en el prompt y se expone como parámetro.
- **Límites de tasa de la API de AI Studio** con decenas de miles de llamadas → concurrencia configurable más reintentos con retroceso exponencial sobre 429 y 5xx, heredando la configuración de `Ajuste Evaluador` (`attempts=5, exp_base=7`). Una key de tier gratuito no sostiene el corpus completo.
- **El caché implícito probablemente no se active** con un prefijo de ~700 tokens → asumido en la estimación de costo; no se presupuesta ningún ahorro por caché.
- **Colab se desconecta** → checkpoint JSONL append-only e idempotencia al reanudar.
- **Subir 38 MB por el navegador es frágil** → se soporta montar Drive como camino principal, con la subida directa como alternativa.
- **Las claves de otros proveedores en el `.env` de `Ajuste Evaluador`** (OpenAI, Anthropic, Mistral, ElevenLabs, en texto plano) no tienen ninguna función en este diseño → no se copian al notebook; sólo se lee la key de Gemini desde Colab Secrets. Un `.ipynb` guarda todo lo que se escribe en él y se comparte por enlace.
- **Los tweets pueden contener contenido ofensivo** —la muestra inspeccionada lo confirma— y los filtros de seguridad de Gemini pueden rechazar la evaluación → las respuestas bloqueadas se registran con su motivo en lugar de perderse, y no se confunden con un nivel bajo ni con `aplicable=false`.
- **La marca de reply no resuelve la falta de contexto**, sólo la declara → esas filas quedan identificables para excluirlas del análisis; se acepta como limitación conocida.

## Open Questions

- **El PDF de la rúbrica**: no está en el proyecto. Determina `N`, el tipo de escala y el costo real.
- **¿Se califican retweets y quotes o se filtran?** El corpus los marca (`is_retweet`, `is_quote`). Un retweet no es texto del autor.
- **¿Qué subconjunto se evalúa?** El corpus completo son 14,635 filas, pero sólo 1,339 tienen `TIPO_QUERY` poblado. Nota medida: las primeras 2,000 filas tienen el doble de payload que el promedio del corpus (el CSV viene ordenado), por lo que muestrear al azar es más representativo que tomar la cabeza.
- **¿Se construye un gold set anotado a mano?** Del orden de 50 tweets calificados por una persona es lo único que convierte "salieron números" en "salieron números confiables". Requiere tiempo humano, no dinero.
- **¿Quién es el dueño de las columnas vacías `tipo` y `justificacion`?** Este diseño las deja intactas por precaución. Si nadie las reclama, podrían alojar un criterio principal.
