## Why

Existe un corpus de 14,635 tweets multilingües sobre percepción de destinos en México (`Queries Lugares - TotalQueries.csv`) y una rúbrica de evaluación en PDF, pero no hay forma de calificar cada tweet contra cada criterio de la rúbrica de manera sistemática, trazable y reproducible. Hoy las columnas `tipo` y `justificacion` del CSV están vacías: el espacio para ese análisis fue reservado pero nunca llenado.

El proyecto `Ajuste Evaluador` ya resolvió el problema análogo —evaluar un documento contra una rúbrica con agentes paralelos de Google ADK— pero para **un documento largo por corrida**. Aquí la escala se invierte: miles de documentos cortos. Se necesita un notebook de Colab que herede la arquitectura probada y la adapte a esa inversión de escala, sin heredar el costo operativo (corpus RAG en Vertex AI, voting de 3 modelos, credenciales ADC de GCP) que a este volumen resulta prohibitivo.

## What Changes

- **Nuevo notebook de Colab** (`.ipynb`) autocontenido que ejecuta el pipeline completo: cargar CSV → cargar PDF de rúbrica → calificar → enriquecer → descargar.
- **Ingesta de rúbrica sin RAG**: el PDF se lee nativamente con Gemini (una sola llamada) y se normaliza a un `rubrica.json` inspeccionable por un humano antes de gastar en la corrida. Reemplaza el corpus RAG de Vertex AI que usa `Ajuste Evaluador`.
- **Agnóstico al número de criterios y al tipo de escala**: `N` se deriva de `len(rubrica.criterios)` en tiempo de ejecución; los agentes, las columnas de salida y la estimación de costo se generan en un bucle. Funciona igual con una escala numérica (0.0–1.0) que con niveles nominales (Logrado / En proceso / Inicial).
- **Calificación con salida estructurada**: `output_schema` de Pydantic en cada agente, en lugar del parseo con expresión regular de `**Puntuación: X.X**` que usa `Ajuste Evaluador`. A miles de filas, el texto libre no es parseable de forma confiable.
- **Campo `aplicable` separado del nivel**: un tweet ajeno al criterio no es "nivel más bajo", es fuera de alcance. Colapsar ambos casos en `0.0` envenena cualquier promedio posterior.
- **Agentes en paralelo en dos ejes**: `ParallelAgent` de ADK sobre los N criterios (hereda el aislamiento de prompts de `Ajuste Evaluador`) y un pool `asyncio` sobre las filas (aporta el throughput que el caso de uso original no necesitaba).
- **Corrida reanudable**: checkpoint JSONL append-only por `tweet.id`, idempotente al reanudar. Colab se desconecta; una corrida de decenas de miles de llamadas no puede ser todo-o-nada.
- **Estimación de costo antes de ejecutar**: celda que calcula `N × costo_unitario` con los tokens reales del subconjunto seleccionado y pide confirmación explícita.
- **Verificaciones de calidad**: histograma de niveles por criterio, test-retest de estabilidad y acuerdo inter-modelo sobre una muestra pequeña. Sin esto se producen miles de calificaciones sin ningún contraste.
- **Exportación enriquecida**: CSV ancho que preserva las 52 columnas originales y añade `{criterio}_nivel`, `{criterio}_puntaje`, `{criterio}_justificacion`, `{criterio}_aplicable`; más un CSV tidy (una fila por tweet × criterio) para análisis. Codificación `utf-8-sig` para que Excel respete los acentos.
- **NO se reutilizan** las columnas vacías `tipo` y `justificacion` del CSV original: se dejan intactas. Dos columnas no alcanzan para N criterios, y sobrescribirlas destruiría un esquema que puede tener otro dueño.
- **NO se usa voting multi-modelo en producción**: se conserva únicamente como instrumento de calibración sobre una muestra. Triplica el costo y su beneficio a este volumen no está demostrado.

## Capabilities

### New Capabilities

- `rubric-ingestion`: Cargar un PDF de rúbrica, extraerlo con Gemini como entrada nativa y normalizarlo a una estructura de criterios y niveles agnóstica al número de criterios y al tipo de escala, revisable por un humano antes de la corrida.
- `tweet-corpus-loading`: Cargar el CSV de tweets (38 MB) desde Drive o subida directa, seleccionar un subconjunto configurable y construir el payload de evaluación multilingüe (texto original más traducción cuando exista), marcando los casos de contexto incompleto como replies, retweets y quotes.
- `parallel-criterion-scoring`: Calificar un tweet contra los N criterios de la rúbrica mediante agentes de Google ADK ejecutados en paralelo, cada uno aislado a su propio criterio, devolviendo nivel, puntaje, justificación y aplicabilidad con salida estructurada garantizada.
- `run-orchestration`: Ejecutar la calificación sobre miles de filas con concurrencia controlada, reintentos ante límites de tasa, checkpoint incremental reanudable y estimación de costo confirmada antes de gastar.
- `scoring-quality-checks`: Medir la confiabilidad de las calificaciones producidas mediante distribución de niveles por criterio, estabilidad en repeticiones y acuerdo entre modelos sobre una muestra de calibración.
- `enriched-csv-export`: Generar el CSV original enriquecido con las columnas de calificación derivadas de la rúbrica, más una variante tidy, y entregarlos descargables desde Colab sin corrupción de caracteres.

### Modified Capabilities

Ninguna. `openspec/specs/` está vacío: este es el primer cambio del proyecto.

## Impact

**Nuevo artefacto**: un notebook `.ipynb` en la raíz del proyecto. No hay código previo en `EvaluadorTweets` que se modifique.

**Datos**: `Queries Lugares - TotalQueries.csv` (14,635 × 52, 38 MB) se lee sin modificarse; la salida son archivos nuevos. Se requiere además un PDF de rúbrica que todavía no está en el proyecto.

**Dependencias externas**: `google-adk` (1.25.0 es la versión validada en `Ajuste Evaluador`), `google-genai`, `pandas`, `nest_asyncio` — instaladas en la primera celda del notebook.

**Servicio y credenciales**: Gemini API de AI Studio con `gemini-2.5-flash` y `thinking_budget=0`. La API key se lee desde Colab Secrets (`userdata.get`). Esto se aparta deliberadamente de `Ajuste Evaluador`, que usa Vertex AI con Application Default Credentials sobre el proyecto `training-evaluator`; la key comentada en su `.env` no es utilizable y ese archivo contiene además claves de otros proveedores en texto plano, que no deben viajar a un notebook compartible.

**Costo**: aproximadamente `N × $1.51` USD para 2,000 tweets y `N × $11.11` para el corpus completo, donde `N` es el número de criterios de la rúbrica. El costo lo domina el output, por lo que el largo de la justificación es la palanca principal. Una corrida con `thinking` activo cuesta 2.7 veces más.

**Herencia de `Ajuste Evaluador`**: se reutilizan como patrón —no como dependencia de código— los criterios definidos como datos en lugar de código, la regla de ausencia de respuesta, la escala de valores cerrada declarada explícitamente en el prompt, la configuración de reintentos ante 429 y 5xx, y la lectura de PDF como `types.Part.from_bytes`.

**Riesgo abierto**: sin el PDF de la rúbrica no se conoce `N` ni el tipo de escala. El diseño agnóstico permite construir el notebook sin ese dato, pero el costo y el tiempo reales sólo se conocen al cargarla.
