## Why

La rúbrica codifica la ausencia **dos veces** y las dos codificaciones compiten.

El nivel «0» de cada criterio significa «el tuit no toca esta dimensión». La regla 1 de la plantilla de instrucción ordena, ante lo mismo, responder `aplicable=false, nivel=null` y prohíbe explícitamente asignar el nivel más bajo. Son dos formas de decir una sola cosa, y no hay nada que arbitre entre ellas.

Medido sobre 7,708 pares resueltos: **7,586 salieron como `aplicable=false` y sólo 12 (0.16%) como nivel «0»**. No es un colapso limpio de una codificación en la otra — es inconsistencia. Esos 12 ceros no son comparables con los 7,586, ni con los 122 que sí recibieron nivel.

Para el cuarto criterio, **saliencia de violencia**, la colisión es destructiva. Es una rúbrica binaria de presencia: `0` significa «violencia ausente» y `1` «violencia presente». Ambas son respuestas sustantivas. Pero la regla 1 convierte el `0` en `aplicable=false`, así que el criterio sólo puede decir «1» o «fuera de alcance», y se pierde la distinción entre *no aplica* y *medí y no hay*. De 1,931 pares resueltos, 1,908 fueron `aplicable=false` contra 11 ceros y 12 unos: el detector respondió su propia pregunta 23 veces.

El efecto llega hasta las gráficas. `niveles_ausencia = "auto"` detecta la etiqueta «0» como ausencia y la saca de las series — correcto para los criterios ordinales 1–3, exactamente inverso para el binario. Verificado en el piloto: las 60 calificaciones del criterio 4 quedaron clasificadas como ausencia y al criterio no le quedó nada que graficar.

## What Changes

- **Decidir una sola codificación de la ausencia** y hacerla explícita en la plantilla de instrucción, en vez de que dos reglas compitan sin árbitro.
- **Distinguir «no aplica» de «ausencia medida»** en los criterios de presencia. Para un detector binario no son lo mismo: el primero es que la pregunta no venía al caso, el segundo es el hallazgo.
- **Tipar la escala de cada criterio** en `rubrica.json`. Hoy se distingue numérica de nominal, pero no *logro* de *valencia* de *presencia binaria*, que es lo que decide cómo se colorea y qué se considera ausencia.
- **Hacer por criterio** `escala_niveles` y `niveles_ausencia`, hoy globales. Una rúbrica que mezcla tres ordinales de valencia con un binario de presencia no admite un solo valor para todos.
- **NO se vuelve a anclar la rúbrica a México**: eso ya se resolvió en `migrar-a-proceso-local`, y la rúbrica vigente marca 20/20 niveles con el objeto de estudio nombrado.

## Capabilities

### New Capabilities

- `rubric-scale-typing`: Declarar el tipo de escala de cada criterio —logro, valencia o presencia binaria— y derivar de él la codificación de la ausencia, la paleta y qué niveles quedan fuera de las series, en vez de aplicar un mismo criterio global a rúbricas heterogéneas.
- `absence-semantics`: Resolver la colisión entre el nivel de ausencia de la rúbrica y la bandera de aplicabilidad, de modo que cada situación tenga una sola codificación y que «no aplica» sea distinguible de «medido y ausente».

### Modified Capabilities

Ninguna todavía: `openspec/specs/` sigue vacío. Al archivar, esto deberá reconciliarse con `parallel-criterion-scoring` y `scoring-visualization`, que hoy viven dentro de sus cambios de origen.

## Impact

**Código**: la plantilla de instrucción en `evaluador/scoring.py`, el esquema y la anotación de `evaluador/rubrica.py`, y la resolución de niveles de ausencia en `evaluador/viz.py`.

**Rúbrica**: probablemente el PDF, si la decisión es eliminar el nivel «0» de los criterios ordinales o redefinirlo. Es el instrumento de investigación y la decisión es de quien investiga, no del código.

**Datos**: **invalida las calificaciones existentes**. Cambiar cómo se codifica la ausencia cambia lo que significa cada registro, así que exige recalificar el corpus completo. La huella de contenido de la rúbrica, implementada en `migrar-a-proceso-local`, hace que reanudar sobre un checkpoint anterior se rehúse solo.

**Costo**: una corrida completa, ~$7.70 sobre el corpus de 2,631 tuits.

**Precedencia**: este cambio debe ir después de que la corrida con la rúbrica anclada termine y se haya revisado su resultado. Sin ese contraste no se sabe cuánto del problema era el anclaje y cuánto es la colisión de ausencia.
