## Why

El notebook produce dos CSV con miles de calificaciones y las verifica estadísticamente (§6: distribución, test-retest, acuerdo inter-modelo), pero no permite **ver** el resultado. La pregunta de investigación que el corpus fue armado para responder —si la percepción de México como destino cambió antes, durante y después de los partidos del mundial en el país— no se contesta con una tabla de distribución global: necesita el eje temporal y necesita separarlo por idioma, porque el corpus mezcla 2,006 tweets en inglés con 417 en japonés y esos dos públicos no tienen por qué moverse igual.

Hoy el único camino es exportar el CSV y armar las gráficas por fuera, lo cual rompe la reproducibilidad que el resto del notebook mantiene y deja el análisis sin registro.

## What Changes

- **Nueva sección § 8 de visualización** en el notebook, después de la exportación, que consume `TIDY` y `DF` sin modificar ninguna celda existente.
- **Unión de resultados con el corpus**: `TIDY` no trae `created_at` ni `lang` —sale con `tweet_id, id_criterio, slug, criterio, aplicable, nivel, puntaje, justificacion, estado, detalle, contexto_incompleto`— así que la celda une por `tweet_id = COL_ID` y reporta los huérfanos, igual que hace el merge de §7.
- **Tres períodos configurables** definidos por fecha en `CONFIG`, con límites cerrado-abierto:

  | Período | Desde (inclusivo) | Hasta (exclusivo) | Días | Tweets | Por día |
  |---|---|---|---|---|---|
  | `PREVIO A MUNDIAL` | 2026-05-31 | 2026-06-11 | 11 | 447 | 40.6 |
  | `DURANTE MUNDIAL EN MEXICO` | 2026-06-11 | 2026-07-06 | 25 | 1,240 | 49.6 |
  | `DESPUES DE PARTIDOS EN MEXICO` | 2026-07-06 | — | 26 | 875 | 33.7 |

- **Gráficas con Apache ECharts cargado por CDN**, construidas serializando la configuración desde Python a JSON e inyectándola con `IPython.display.HTML`. No se agrega `pyecharts` ni ninguna dependencia de Python.
- **Tres familias de gráficas**: serie diaria apilada por nivel (una por criterio, con los tres períodos marcados como bandas), distribución global por criterio, y la misma distribución partida en tres columnas para comparar períodos.
- **Pre-agregación en pandas, filtrado en el cliente**: la celda calcula los conteos por `(fecha, criterio, nivel, idioma, estado)` una sola vez y embebe ese agregado. El filtro de idioma y el cambio absoluto/proporción ocurren en JavaScript, sin volver a Python. Payload estimado ~150 KB contra los megabytes que serían los datos crudos con justificaciones.
- **Filtro de idioma por multi-selección** con el total de cada idioma a la vista y advertencia explícita cuando la selección cae por debajo de un umbral de tweets. Medido: solo `en` (2,006) y `ja` (417) tienen densidad diaria utilizable; `es` tiene 12 tweets en 61 días y hay 12 idiomas con menos de 5.
- **Toggle absoluto / proporción**, con la proporción como opción por defecto para la comparación entre períodos. El volumen diario del corpus varía de 33.7 a 49.6 tuits/día según el período, así que comparar conteos crudos mediría la intensidad del muestreo, no el fenómeno.
- **No aplicables y fallidas fuera de la escala**: `NO_APLICABLE` y `FUERA_DE_ESCALA` no se apilan junto a los niveles de logro. La proporción se calcula sobre las calificaciones `OK` y los otros dos estados se reportan aparte, preservando la distinción que el pipeline ya sostiene: "fuera de alcance" no es "bajo logro".
- **Doble salida**: las gráficas se muestran dentro del Colab y además se escriben en un `.html` autocontenido y descargable, que conserva los filtros funcionando sin necesidad del kernel.
- **Suavizado opcional de la serie diaria** por media móvil, porque con ~42 tweets/día repartidos entre los niveles de un criterio cada punto vale ~7 tweets, y filtrado a japonés vale ~1.

## Capabilities

### New Capabilities

- `scoring-visualization`: Agregar las calificaciones producidas por el pipeline a conteos por fecha, criterio, nivel e idioma; segmentarlas en períodos configurables por fecha; y renderizarlas como gráficas interactivas de Apache ECharts, filtrables por idioma y conmutables entre conteo absoluto y proporción, visibles dentro del notebook y exportables como un archivo HTML autocontenido.

### Modified Capabilities

Ninguna. `openspec/specs/` está vacío. Este cambio solo lee `TIDY` y `DF`; no altera ningún requisito de calificación, exportación ni verificación.

## Impact

**Notebook**: `evaluador_tweets_rubrica.ipynb` gana una sección § 8 al final, después de la celda 25 de exportación. `CONFIG` gana la definición de los períodos y los parámetros de visualización. Ninguna celda existente cambia de comportamiento.

**Dependencias**: ninguna nueva del lado de Python. ECharts se carga por CDN dentro del HTML generado.

**Datos**: solo lectura. Consume `TIDY` y `DF` en memoria, o los CSV ya exportados.

**Prerrequisito de escala**: con `N_MUESTRA = 200` las gráficas no tienen sentido — son 3 tweets por día repartidos entre los criterios. La sección supone una corrida sobre el corpus completo de 2,562 filas y debe advertirlo cuando detecte que la cobertura es menor.

**Prerrequisito de datos**: el corpus debe traer `created_at` legible y un identificador válido con el cual unir. El change `reparar-corpus-y-traducir` es quien lo garantiza: hoy los 2,562 identificadores del archivo están corruptos por `float64`, de modo que la unión entre `TIDY` y `DF` no sería confiable. Esta sección debe correrse sobre el corpus reparado.

**Limitación conocida de Colab**: cada salida de celda vive en un iframe aislado. La gráfica se ve al ejecutar, pero al reabrir el notebook guardado no vuelve a ser interactiva hasta reejecutar la celda. El `.html` descargable existe precisamente para cubrir ese caso.

**Desbalance de los períodos**: 447 / 1,240 / 875 tuits. La comparación entre períodos es legítima en proporción, pero los intervalos de confianza del primer período son visiblemente más anchos y la visualización no debe sugerir lo contrario.
