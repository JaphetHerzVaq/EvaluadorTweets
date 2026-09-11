# Cómo este sistema califica tuits

**Guía para entenderlo sin saber programar.**
Audiencia: estudiantes de primer año. Si sabes qué es una rúbrica de examen, ya sabes el 70% de esto.

---

## 1. La idea en una frase

> Este sistema le pone **calificación a tuits** igual que un maestro le pone calificación a un ensayo: con una **rúbrica**.

La pregunta de investigación es:

> **¿Qué imagen de México se ve en Twitter/X antes, durante y después de los partidos del Mundial 2026 en México?**

Para responderla no basta con contar tuits. Hay que saber **qué dicen**. Y "qué dicen" es subjetivo... a menos que lo midas con reglas fijas. Eso es la rúbrica.

### La analogía del salón

Imagina que tienes **2,631 ensayos** que revisar y contratas a **4 maestros**:

```
                         ┌──────────────────────────────┐
                         │   Un tuit (un "ensayo")      │
                         └──────────────┬───────────────┘
                                        │  se le da una copia a cada uno
            ┌───────────────┬───────────┴───────┬────────────────┐
            ▼               ▼                   ▼                ▼
     ┌────────────┐  ┌────────────┐     ┌────────────┐   ┌────────────┐
     │ Maestro 1  │  │ Maestro 2  │     │ Maestro 3  │   │ Maestro 4  │
     │ EMOCIÓN    │  │ CULTURA    │     │ INSTITUC.  │   │ VIOLENCIA  │
     │            │  │            │     │            │   │            │
     │ ¿siente    │  │ ¿juzga la  │     │ ¿juzga si  │   │ ¿menciona  │
     │ algo hacia │  │ comida, el │     │ México     │   │ inseguri-  │
     │ México?    │  │ arte, el   │     │ organiza   │   │ dad en     │
     │            │  │ paisaje?   │     │ bien?      │   │ México?    │
     └─────┬──────┘  └─────┬──────┘     └─────┬──────┘   └─────┬──────┘
           │               │                  │                │
           ▼               ▼                  ▼                ▼
       nivel 0-5       nivel 0-5          nivel 0-5        nivel 0 ó 1
       + por qué       + por qué          + por qué        + por qué
```

Tres cosas importantes de este dibujo:

1. **Los 4 maestros no se hablan entre ellos.** El maestro de comida no sabe qué puso el de emociones. Esto es a propósito y el código hasta lo verifica (`verificar_aislamiento`). Si se hablaran, se contaminarían: "ah, el otro puso 5, pues yo también".
2. **Trabajan al mismo tiempo** (en paralelo). Por eso 10,524 calificaciones salieron en **34 minutos**.
3. **Cada maestro es en realidad el mismo modelo de IA** (Gemini 2.5 Flash), pero con **instrucciones distintas**. Es como darle a la misma persona cuatro credenciales diferentes y prohibirle recordar las otras.

---

## 2. Las cuatro piezas del sistema

| Pieza | Qué es | Archivo real |
|---|---|---|
| **El corpus** | Los 2,631 tuits que se van a calificar | `turistas_traducido.csv` |
| **La rúbrica** | Las reglas de calificación | `rubrica_tweets.pdf` → `rubrica.json` |
| **El motor** | El programa que junta tuit + rúbrica y pregunta a la IA | [evaluador/scoring.py](evaluador/scoring.py) |
| **El checkpoint** | La libreta donde se anota cada resultado, uno por renglón | `checkpoint_anclada.jsonl` |

> 💡 **Por qué existe el checkpoint:** calificar todo cuesta dinero real (~$7.70 USD) y tarda media hora. Si se cae la luz en el minuto 28, no quieres volver a pagar los primeros 27. El checkpoint se escribe renglón por renglón, y al reanudar el sistema lee lo que ya hay y **sólo repite lo que falló**.

---

## 3. La rúbrica: los 4 criterios

La rúbrica viene de la teoría de **imagen de país** (*country image*). La idea académica es que la imagen que la gente tiene de un país se descompone en tres dimensiones, más una cuarta que interesa específicamente para México.

### 🔵 RÚBRICA 1 — Dimensión simpática / emocional ("atmósfera")

**Pregunta:** ¿El que escribe **siente** algo hacia México o su gente?

No importa si es verdad, no importa si es justo. Importa el **afecto**.

### 🟣 RÚBRICA 2 — Dimensión estética ("imagen cultural")

**Pregunta:** ¿El tuit **juzga** algo cultural de México? Comida, arte, historia, arquitectura, paisaje.

Ojo: aquí no se juzga a las personas, se juzgan **objetos culturales**.

### 🟢 RÚBRICA 3 — Dimensión funcional ("perspectiva política")

**Pregunta:** ¿El tuit **juzga si México funciona**? Instituciones, gobierno, transporte, estadios, logística, operativos, infraestructura.

### 🔴 RÚBRICA 4 — Saliencia de violencia

**Pregunta:** ¿El tuit **menciona** violencia, crimen o inseguridad en México?

Esta es distinta a las otras tres: es un **detector de sí/no**, no una escala de qué tan bueno o malo.

---

## 4. Los niveles: la escala de 0 a 5

Las rúbricas 1, 2 y 3 usan la **misma escala de 6 niveles**. Léela de izquierda a derecha como un termómetro:

```
   0            1            2            3            4            5
   │            │            │            │            │            │
┌──┴──┐  ┌──────┴─────┐ ┌────┴─────┐ ┌────┴────┐ ┌─────┴────┐ ┌─────┴──────┐
│ nada│  │ muy        │ │ algo     │ │ neutral │ │ positivo │ │ fascinación│
│     │  │ negativo   │ │ negativo │ │ o mixto │ │          │ │            │
└─────┘  └────────────┘ └──────────┘ └─────────┘ └──────────┘ └────────────┘
 ausencia  ◄─────────── VALENCIA NEGATIVA ──── centro ──── POSITIVA ───────►
```

⚠️ **Detalle que confunde a todo el mundo la primera vez:** el **0 no es "lo peor"**. El 0 significa *"el tuit no habla de esto"*. Lo peor es el **1**. La escala no es "de malo a bueno" (eso sería una escala de *logro*, como un examen). Es una escala de **valencia**: de odio a amor, con el 0 colgado afuera como "aquí no hay nada que medir".

### Tabla completa, RÚBRICA 1 (emoción hacia México)

| Nivel | Puntos | Significa | Ejemplo de tuit |
|:-:|:-:|---|---|
| **0** | 0 | No expresa emoción hacia México | "Mexico vs Brazil, 8pm, Estadio Azteca" |
| **1** | 1 | Odio, desprecio, hostilidad | "I hate this country" |
| **2** | 2 | Desagrado, decepción, incomodidad | "kind of disappointed with the vibe in Mexico" |
| **3** | 3 | Mixto, tibio, ambivalente | "unos mexicanos amables, otros no" |
| **4** | 4 | Agrado claro, simpatía, calidez | "buena onda la gente mexicana" |
| **5** | 5 | Amor, fascinación, no se quiere ir | "la gente mexicana es la más cálida del mundo" |

### Tabla completa, RÚBRICA 2 (cultura)

| Nivel | Significa | Ejemplo |
|:-:|---|---|
| **0** | No juzga nada cultural mexicano | — |
| **1** | Repulsión | "Mexican food is disgusting garbage" |
| **2** | Crítica moderada | "the tacos in Mexico were kind of bland" |
| **3** | Descriptivo o mezclado | "el mole es interesante, unos platillos geniales, otros muy picosos" |
| **4** | Valoración favorable | "bonita la arquitectura colonial mexicana" |
| **5** | Elogio superlativo | "Mexico has the most breathtaking cuisine on the planet" |

### Tabla completa, RÚBRICA 3 (instituciones)

| Nivel | Significa | Ejemplo |
|:-:|---|---|
| **0** | No juzga desempeño institucional | — |
| **1** | Colapso, incompetencia grave | "total institutional collapse in Mexico, nothing works" |
| **2** | Deficiencia acotada | "los accesos en la sede mexicana fueron un desorden" |
| **3** | Mixto | "el operativo fue enorme pero causó filas larguísimas" |
| **4** | Eficaz | "el operativo mexicano estuvo bien organizado" |
| **5** | Excelencia | "logística impecable, México dio cátedra" |

### RÚBRICA 4 es binaria

| Nivel | Significa |
|:-:|---|
| **0** | El tuit **no** menciona violencia/crimen/inseguridad en México |
| **1** | El tuit **sí** la menciona — *en cualquier tono* |

Lo de "cualquier tono" es clave. Todos estos son **nivel 1**:

- "México es peligrosísimo, no vayan" → miedo
- "¿Es seguro llevar a mis hijos a Monterrey?" → pregunta
- "Todo el mundo dice que México es inseguro y es mentira, me sentí segurísimo" → **desmentido, pero sigue siendo nivel 1**

¿Por qué? Porque el criterio no mide *si hay violencia*. Mide **saliencia**: qué tan presente está el tema en la conversación. Negar algo también es hablar de ello.

---

## 5. MECE: la regla que hace que una rúbrica sirva

**MECE** se lee "mí-si" y viene de consultoría. Son las siglas en inglés de:

> **M**utually **E**xclusive, **C**ollectively **E**xhaustive
> *Mutuamente excluyentes, colectivamente exhaustivos.*

En español de a de veras:

```
   MUTUAMENTE EXCLUYENTES          COLECTIVAMENTE EXHAUSTIVOS
   ───────────────────────         ──────────────────────────
   No se encinan.                  No dejan huecos.
   Cada caso cae en UNA sola       Todo caso cae en ALGUNA
   casilla, nunca en dos.          casilla, nunca en ninguna.

   ✗ MAL: "niños / adultos /       ✗ MAL: "lunes / martes /
      estudiantes"                     miércoles"
      (un estudiante de 19            (¿y el sábado?)
       cae en dos casillas)

   ✓ BIEN: "0-17 / 18-64 / 65+"    ✓ BIEN: "lunes a domingo"
```

### ¿Por qué importa aquí?

Si los niveles de una rúbrica **se encinan**, dos personas (o dos corridas de la IA) califican distinto el mismo tuit y ninguna está equivocada. La medición deja de ser medición.

Si los niveles **dejan huecos**, hay tuits que no caben en ningún nivel, y quien califica se ve obligado a inventar o a forzar.

### Los tres lugares donde el sistema aplica MECE

**① Entre criterios (¿las 4 dimensiones son MECE?)**

Casi. Están pensadas para no encinarse:

| Si el tuit dice… | va a… | porque… |
|---|---|---|
| "me cae bien la gente" | R1 (emoción) | juzga **personas**, con afecto |
| "los tacos están increíbles" | R2 (cultura) | juzga un **objeto cultural** |
| "el metro funcionó perfecto" | R3 (instituciones) | juzga **competencia organizativa** |
| "me robaron en el centro" | R4 (violencia) | menciona **crimen** |

¿Son **exhaustivos**? No, y a propósito. Un tuit puede no tocar ninguna dimensión ("va a llover"). Para eso existe la salida de escape (§6). Pero un mismo tuit **sí puede activar varios criterios a la vez**, y eso está bien: los criterios son *dimensiones paralelas*, no cajones de clasificación. Un tuit puede ser emocionalmente positivo (R1=5) y mencionar violencia (R4=1) al mismo tiempo.

**② Dentro de un criterio (¿los 6 niveles son MECE?)**

Aquí sí se exige exclusividad estricta: un tuit recibe **exactamente un** nivel en R1. El código lo garantiza con una **escala cerrada**: la IA debe copiar literalmente una de las etiquetas `«0» | «1» | «2» | «3» | «4» | «5»`. Si devuelve "4.5" o "alto", el sistema marca el resultado como `FUERA_DE_ESCALA` y lo tira. **No se acepta un nivel inventado.**

**③ El nivel 3 es el pegamento de la exhaustividad**

Fíjate que el nivel 3 dice "neutral, **mixto o ambivalente**". Sin él habría un hueco: ¿dónde pones "me encantó la comida pero odié el tráfico"? El 3 tapa ese hueco. Sin un nivel de "mezcla", ninguna rúbrica de valencia es exhaustiva.

### Dónde el sistema HOY rompe MECE (y está documentado)

Esta es la parte honesta, y probablemente la más útil de aprender.

La ausencia está codificada **dos veces**:

```
        ¿el tuit toca esta dimensión?
                    │
         ┌──────────┴──────────┐
         │  NO                 │  NO
         ▼                     ▼
   ┌───────────┐         ┌───────────┐
   │ nivel «0» │   ¿?    │ aplicable │
   │ de la     │ ◄─────► │  = false  │
   │ rúbrica   │         │           │
   └───────────┘         └───────────┘
        ▲                      ▲
   lo dice el PDF        lo dice la regla 1
   de la rúbrica         de la instrucción

        ⚠️  DOS CASILLAS PARA EL MISMO CASO
            = NO mutuamente excluyentes
            = se rompe MECE
```

**Consecuencia medida** en la corrida anterior: de 7,708 calificaciones, **7,586 salieron como `aplicable=false`** y sólo **12 como nivel «0»**. No es que una codificación ganara limpiamente — es inconsistencia. Esos 12 ceros **no son comparables** con los 7,586.

**Y para la RÚBRICA 4 es peor**, porque ahí el 0 **no** es ausencia: es un **hallazgo**. "Medí y no hay violencia" es una respuesta sustantiva, distinta de "esta pregunta no venía al caso". Al colapsar las dos, el detector pierde justo la mitad de lo que detecta.

Esto ya tiene un cambio propuesto y pendiente: [proposal.md](openspec/changes/anclar-semantica-de-ausencia/proposal.md). **Aplicarlo invalida las calificaciones actuales** y obliga a recalificar todo, porque cambiaría lo que significa cada registro.

> 🎓 **Moraleja de la clase:** MECE no es adorno teórico. Romperlo en el diseño del instrumento te cuesta, literalmente, volver a pagar toda la medición.

---

## 6. La salida de escape: `aplicable = false`

Antes de poner nivel, cada evaluador contesta una pregunta previa:

> **¿Este tuit siquiera trata de lo que yo evalúo?**

Si la respuesta es no, responde `aplicable = false`, **nivel vacío**, y explica por qué.

Ejemplo real del checkpoint:

> **Tuit:** una receta de cocina
> **R1 (emoción):** `aplicable=false` — *"El tweet es una receta de comida y no expresa ninguna emoción del emisor hacia México o su gente."*

**La regla de oro para analizar los datos después:**

> ### ❌ `aplicable=false` **NO** es un cero.
> **Fuera de alcance ≠ bajo logro.**

Si al sacar el promedio metes los "no aplica" como 0, arruinas el resultado. Es como promediar las calificaciones de un examen contando como 0 a los alumnos que **no presentaron**. En los archivos de salida esas celdas quedan **vacías**, no en cero, exactamente para que no se confundan.

---

## 7. El flujo de trabajo completo

```
 ┌───────────────── PREPARACIÓN (ya está hecha, costó dinero) ──────────────────────────┐
 │                                                                                       │
 │   Excel crudo ──▶  REPARAR  ──▶ turistas_reparado.csv                                 │
 │   (2,631 tuits)      │                                                                │
 │                      └─ arregla: acentos rotos (mojibake), IDs de 19 dígitos          │
 │                         redondeados por Excel, textos cortados a 255 caracteres       │
 │                                                                                       │
 │   turistas_reparado.csv ──▶  TRADUCIR  ──▶ turistas_traducido.csv                     │
 │                                  │                                                    │
 │                                  └─ traducción al español SÓLO DE APOYO PARA HUMANOS. │
 │                                     Lo que se califica es el ORIGINAL (regla 5).      │
 └───────────────────────────────────────────────────────────────────────────────────────┘
                                        │
 ┌───────────────── LA RÚBRICA ─────────┼────────────────────────────────────────────────┐
 │                                      │                                                │
 │   rubrica_tweets.pdf ──▶ RUBRICA ──▶ rubrica.json  ◄── artefacto INSPECCIONABLE:      │
 │   (fuente de verdad)                       │           lo puedes abrir y leer ANTES    │
 │                                            │           de gastar un peso               │
 └────────────────────────────────────────────┼───────────────────────────────────────────┘
                                              │
                                              ▼
 ┌───────────────────────────── CALIFICACIÓN ──────────────────────────────────────────┐
 │                                                                                      │
 │   python -m evaluador correr              ──▶ SÓLO ESTIMA EL COSTO. No gasta nada.   │
 │   python -m evaluador correr --confirmar  ──▶ ahora sí califica                      │
 │                                                    │                                 │
 │                                                    ▼                                 │
 │                                        checkpoint_anclada.jsonl                      │
 │                                        (un renglón por cada tuit × criterio)         │
 └───────────────────────────────────────────────────┬──────────────────────────────────┘
                                                     │
                           ┌─────────────────────────┴──────────────────────┐
                           ▼                                                ▼
              python -m evaluador exportar                    python -m evaluador graficar
                           │                                                │
              ┌────────────┴────────────┐                                   ▼
              ▼                         ▼                        graficas_*.html
         CSV "ancho"               CSV "tidy"                    (interactivo, se abre
    1 renglón = 1 tuit        1 renglón = 1 calificación          en el navegador)
    con 4 columnas de nivel   (tuit × criterio)
    → para ver los datos      → para estadística y gráficas
```

### Comandos, en orden

```bash
python -m evaluador --help                    # qué se puede hacer
python -m evaluador auditar                   # revisa un checkpoint. NO gasta.
python -m evaluador correr                    # sólo estima el costo. NO gasta.
python -m evaluador correr --confirmar        # ahora sí: autoriza el gasto
python -m evaluador exportar                  # produce los CSV
python -m evaluador graficar                  # produce el HTML
```

> 🔐 **Diseño defensivo que vale la pena copiar:** `correr` **no emite ni una sola llamada** sin `--confirmar`. Primero mide los tokens reales contra la API, te dice cuánto va a costar, y espera. Un error de dedo no puede gastarte $7 USD.

---

## 8. Qué se le manda exactamente a la IA

Para **cada** tuit y **cada** criterio se arma un mensaje así:

```
┌─ PARTE FIJA (idéntica para todos los tuits de ese criterio) ────────────┐
│                                                                         │
│  Eres evaluador experto del criterio [RÚBRICA 1]                        │
│  «ATMÓSFERA DE MÉXICO: DIMENSIÓN SIMPÁTICA / EMOCIONAL».                │
│  Evalúas UN tweet a la vez, contra ESTE criterio y ningún otro.         │
│                                                                         │
│  NIVELES DE LOGRO: [los 6 descriptores completos]                       │
│  ESCALA VÁLIDA: «0» | «1» | «2» | «3» | «4» | «5»                       │
│                                                                         │
│  REGLAS OBLIGATORIAS:                                                   │
│   1. APLICABILIDAD PRIMERO — si es ajeno al criterio, aplicable=false.  │
│      "Fuera de alcance" y "bajo logro" son cosas distintas.             │
│   2. NO INVENTES — no infieras contenido que no está en el texto.       │
│   3. CONTEXTO INCOMPLETO — si falta el tuit padre, dilo, no lo inventes.│
│   4. ESCALA CERRADA — copia una etiqueta textual, no inventes niveles.  │
│   5. IDIOMA — evalúa en el idioma ORIGINAL; justifica en ESPAÑOL.       │
│   6. EXTENSIÓN — máximo 90 palabras, directo, sin relleno.              │
│                                                                         │
├─ PARTE VARIABLE (el tuit) ──────────────────────────────────────────────┤
│                                                                         │
│  [ADVERTENCIA DE CONTEXTO INCOMPLETO] Este tweet es una RESPUESTA a     │
│  otro tweet que NO está disponible...        ← sólo si aplica           │
│                                                                         │
│  <tweet idioma="ja">                                                    │
│  日本に帰りたくない！                                                      │
│  </tweet>                                                               │
│                                                                         │
│  <traduccion_al_espanol_de_apoyo>                                       │
│  ¡No quiero volver a Japón!                                             │
│  </traduccion_al_espanol_de_apoyo>                                      │
└─────────────────────────────────────────────────────────────────────────┘
```

Ese ejemplo es real: ese tuit recibió **R1 = nivel 5**, con esta justificación del sistema:

> *"La frase «¡No quiero volver a Japón!» indica un deseo intenso de quedarse, lo que se alinea con el nivel de fascinación."*

Dos decisiones de diseño escondidas ahí:

**a) El criterio va PRIMERO, el tuit va AL FINAL.** No es estético. Como el principio del mensaje es idéntico en las 2,631 llamadas de ese criterio, el proveedor lo puede **cachear** y cobra menos. Reordenar el mensaje ahorra dinero.

**b) La temperatura está en 0.0.** La "temperatura" es qué tan creativa se le permite ser a la IA. En 0 es lo más determinista posible: el mismo tuit debería dar el mismo nivel dos veces. Para escribir poesía quieres temperatura alta; para **medir**, la quieres en cero.

---

## 9. Cómo nace un puntaje (el detalle más importante)

Aquí está la parte que separa a este sistema de "nomás preguntarle a ChatGPT":

```
   LA IA DEVUELVE                     EL SISTEMA HACE
   ──────────────                     ───────────────
   aplicable: true          ──▶  ¿es true?  si no → estado NO_APLICABLE, fin
   nivel: "4"               ──▶  ¿"4" está en la escala del criterio?
                                    · sí exacto      → lo toma
                                    · con espacios,
                                      comillas o
                                      mayúsculas     → lo normaliza y lo toma
                                    · no está        → FUERA_DE_ESCALA, se tira
   justificacion: "..."     ──▶  se guarda tal cual
   puntaje: ❌ NO LO PIDE   ──▶  el sistema BUSCA los puntos del nivel "4"
                                 en rubrica.json y encuentra 4.0
```

> ### 🔑 A la IA nunca se le pide el puntaje.
> La IA sólo elige una **etiqueta**. El **número** lo saca el programa de la rúbrica, con una tabla de búsqueda.
>
> ¿Por qué? Porque si la IA devolviera el número, podría devolver "nivel 2, 4 puntos" — incoherente, y nadie se daría cuenta entre 10,000 renglones. Al derivarlo, **es imposible que nivel y puntaje se contradigan**.

Esto es un principio general de diseño: *lo que se puede derivar determinísticamente, no se le pregunta a un modelo probabilístico.*

### Los estados posibles de una calificación

| Estado | Qué pasó | ¿Se vuelve a intentar? |
|---|---|:-:|
| `OK` | Se asignó un nivel válido | No |
| `NO_APLICABLE` | La IA dijo que el criterio no aplica | No |
| `BLOQUEADO` | El proveedor rechazó la respuesta para ese texto | No |
| `FUERA_DE_ESCALA` | La IA inventó un nivel que no existe | Se descarta |
| `ERROR` | Falló la llamada | ✅ Sí |
| `SIN_RESPUESTA` | ADK no devolvió estado para ese criterio | ✅ Sí |
| `TIEMPO_AGOTADO` | Pasaron 120 s sin respuesta | ✅ Sí |

Al reanudar, el sistema **conserva** `OK`, `NO_APLICABLE` y `BLOQUEADO` (los dos primeros ya se pagaron; el tercero no va a cambiar) y **sólo repite** los de abajo. Eso es el alcance `fallidos`, el que viene por defecto.

### `SIN_RESPUESTA` no significa lo que parecía

Durante un buen rato se creyó que `SIN_RESPUESTA` era siempre el filtro de contenido. **Era falso, y costó dos reintentos completos descubrirlo.**

El problema es que ADK no dice por qué falta un criterio: cuando el `ParallelAgent` no emite estado para uno de los cuatro, no lanza ninguna excepción — simplemente esa clave no está. Desde fuera, un bloqueo del proveedor y un fallo interno de ADK se ven idénticos.

Se reintentaron los 56 fallos de la corrida uno a uno, esta vez **sin pasar por ADK**, llamando directo a la API con la misma instrucción y el mismo esquema:

| causa | pares | qué pasó |
|---|---|---|
| fallo de la ruta de ADK | **33** (59%) | la llamada directa **respondió sin problema** |
| `PROHIBITED_CONTENT` | **23** (41%) | bloqueo real: contenido que el proveedor no procesa |

Más de la mitad no tenían nada que ver con el contenido. Es reproducible y determinista: con el tuit afectado, la RÚBRICA 3 no devuelve estado en ADK **ni siquiera corriendo sola**, mientras la llamada directa la resuelve al primer intento.

> **Cómo se llegó al diagnóstico equivocado.** Al verificarlo por primera vez se probó con la RÚBRICA 1 — que no era de las que fallaban. Respondió bien, y ese éxito se leyó como confirmación de que el problema era el contenido. La prueba estaba mirando el caso equivocado.

### El segundo defecto, que el primero tapaba

Al medir el rescate contra lo predicho, los números salieron invertidos: se
esperaban 33 recuperados y salieron 23, con 33 todavía fallando. Esa
discrepancia destapó un bug distinto, y peor.

Cuando el `ParallelAgent` devolvía unos criterios y otros no, el motor lanzaba
la excepción de resultado parcial **descartando los que sí había devuelto**.
El reintento volvía a pedir los cuatro desde cero.

```
  ADK devuelve c1 y c4, falla c2 y c3
        └──▶ ResultadoParcial(["c2","c3"])
                   │
             c1 y c4 se tiran con la excepción   ← respuestas ya pagadas
                   │
             el reintento vuelve a pedir los cuatro
```

Se pagaron esas respuestas dos y tres veces, y al final quedaban sin registro.
Ahora el motor **acumula entre intentos**: lo que se resuelve se guarda, el
reintento persigue sólo lo que falta, y el respaldo directo recibe únicamente
el remanente. Con eso, los 33 pares que llevaban tres corridas «fallando» se
resolvieron a la primera y sin un solo error: ADK siempre los había respondido.

**Qué se hizo con eso.** Ahora, cuando ADK agota sus reintentos para un criterio, el sistema lo intenta una vez por la vía directa:

```
  ADK (los 4 criterios de golpe)
      └─ agota reintentos ──▶ respaldo directo, criterio por criterio
                                  ├── responde       ──▶ OK / NO_APLICABLE
                                  └── block_reason   ──▶ BLOQUEADO, y no se
                                                          reintenta nunca más
```

Recupera el 59% y marca el 41% restante como permanente. Eso último importa: un par bloqueado que se reintenta en cada reanudación es dinero garantizado sin resultado, y ensucia el conteo de fallidas de todas las corridas siguientes.

Los 23 bloqueados son tuits que describen abuso sexual de menores. `PROHIBITED_CONTENT` es el **único** umbral de Gemini que `safety_settings` no permite relajar — se verificó poniendo `BLOCK_NONE` en las cuatro categorías configurables y no cambia nada. No hay forma de calificarlos, ni debería haberla.

---

## 10. Resultados reales de la última corrida

Corrida `anclada`, 11 de septiembre de 2026. **2,631 tuits × 4 criterios = 10,524 calificaciones en 34.2 minutos.**

### Cuánto se pudo calificar

```
NO_APLICABLE  ████████████████████████████████████████████████  10,200  (96.9%)
OK            █                                                     307  ( 2.9%)
BLOQUEADO     ▏                                                      17  ( 0.2%)
```

**Cero pares sin resolver.** La primera pasada dejó 56 fallos; se resolvieron
todos salvo los 17 que el proveedor rechaza de forma permanente. De esos 56:

| | pares | qué eran en realidad |
|---|---|---|
| recuperados al dejar de descartarlos | **33** | ADK **sí** los había resuelto; el motor tiraba esas respuestas |
| rescatados por la llamada directa | **6** | ADK no los resolvía, la API sí |
| bloqueados de verdad | **17** | `PROHIBITED_CONTENT` |

Sólo 17 de 56 eran fallos genuinos. Los otros 39 eran defectos del motor,
descritos abajo.

### RÚBRICA 1 — Emoción hacia México (2,617 pares resueltos)

```
 no aplica  ███████████████████████████████████████████████  2,512  96.0%
 ─────────────────────────────────────────────────────────────────────────
 nivel 0    ▏                                                    3   0.1%
 nivel 1    ███                                                 16   0.6%   😠
 nivel 2    ████                                                21   0.8%   🙁
 nivel 3    ▏                                                    4   0.2%   😐
 nivel 4    ███████                                             35   1.3%   🙂
 nivel 5    █████                                               26   1.0%   😍
```

De los **105 tuits con emoción detectada**: **61 positivos** (niveles 4-5) contra **37 negativos** (niveles 1-2). Balance favorable, pero sobre una base chiquita.

### RÚBRICA 2 — Cultura

```
 no aplica  ███████████████████████████████████████████████  2,546  97.3%
 ─────────────────────────────────────────────────────────────────────────
 nivel 1    █                                                    5   0.2%
 nivel 2    █                                                    5   0.2%
 nivel 3    ████                                                20   0.8%
 nivel 4    ███████                                             32   1.2%
 nivel 5    ██                                                   9   0.3%
```

### RÚBRICA 3 — Instituciones

```
 no aplica  ████████████████████████████████████████████████ 2,594  99.1%
 ─────────────────────────────────────────────────────────────────────────
 nivel 1    ██                                                   8   0.3%
 nivel 2    ███                                                 12   0.5%
 nivel 4    ▏                                                    3   0.1%
```

⚠️ Este criterio se activó **23 veces en 2,617 tuits**. Con ese tamaño no se puede concluir nada. Y el código lo sabe: hay una verificación (`umbral_no_aplicable = 0.50`) que **avisa cuando más de la mitad sale "no aplica"**, porque eso sugiere que la rúbrica no corresponde al corpus.

### RÚBRICA 4 — Violencia

```
 no aplica  ███████████████████████████████████████████████  2,516  96.1%
 ─────────────────────────────────────────────────────────────────────────
 nivel 0    ███████████████                                     79   3.0%   sin violencia
 nivel 1    ████                                                22   0.8%   con violencia
```

Aquí se ve el problema de MECE del §5 en vivo: **2,516 "no aplica" contra 79 "medí y no hay"**. Para un detector binario, ambos deberían ser lo mismo — todo tuit *puede* ser inspeccionado en busca de violencia, así que "no aplica" casi no debería existir. Que exista 2,516 veces es la señal de que la codificación está rota.

### Cómo se leen estos números, honestamente

> El hallazgo central de esta corrida **no es** "los turistas quieren a México".
> Es: **el 96% del corpus no dice nada evaluable sobre la imagen de México.**

Eso puede significar tres cosas distintas, y los datos solos **no distinguen** cuál:

1. Los tuits de verdad hablan de otra cosa (alineaciones, boletos, horarios).
2. La búsqueda que armó el corpus trajo mucho ruido.
3. El instrumento es demasiado estricto y la regla 1 dispara de más (el bug de MECE).

Decidir cuál es trabajo de quien investiga, no del programa.

---

## 11. El "anclaje a México": la lección más cara del proyecto

Esta parte es un caso de estudio buenísimo de **cómo se arruina una medición sin darte cuenta**.

La rúbrica original decía, en su nivel 5:

> *"Emoción fuertemente positiva: amor, encantamiento, atracción máxima, superlativos afectivos."*

Léelo otra vez. **¿Amor hacia qué?** No dice. La rúbrica **nunca nombró a México en sus niveles**. El investigador sabía de qué hablaba; el modelo no.

**Resultado medido sobre la corrida dañada:**

```
 De 122 calificaciones con nivel asignado:
   67 (55%)  eran sobre tuits que NI SIQUIERA MENCIONAN a México.
 ────────────────────────────────────────────────────────────────
 Ejemplos reales de falsos positivos:
   · una entrega de Amazon en Reino Unido  →  puntuada como
                                              "competencia institucional mexicana"
   · un cabaret japonés                    →  puntuado como
                                              "fascinación estética por la
                                               cultura mexicana"

 Sólo 6 de los 20 niveles mencionaban México.
 El criterio con CERO menciones en sus niveles llegó al 84% de falsos positivos.
```

### El arreglo

Reescribir los 20 descriptores para que **cada uno nombre a México**, y agregar al código una verificación automática que revisa la rúbrica antes de gastar:

```toml
anclaje = ["méxico", "mexico", "mexicano", "mexicana",
           "mexicanos", "mexicanas", "mexican"]
```

Hoy la verificación reporta **20/20 niveles anclados**. Si alguien edita la rúbrica y quita el ancla, el sistema avisa **antes** de la corrida, no después.

> 🎓 **Moraleja:** un instrumento de medición tiene que nombrar su objeto de estudio **explícitamente, en cada nivel**. Lo que para ti es obvio por contexto, para quien califica (humano o IA) no existe. Esto aplica igual a una encuesta, a una guía de entrevista o a una rúbrica de tesis.

Y una consecuencia técnica elegante: el sistema calcula una **huella digital del contenido de la rúbrica**. Si cambias la rúbrica e intentas reanudar sobre un checkpoint viejo, **se niega solito** — porque mezclar calificaciones de dos instrumentos distintos produce una columna donde los renglones no significan lo mismo.

---

## 12. Los tres períodos (lo que al final se compara)

Todo esto existe para poder comparar tres momentos:

```
 2026-05-31          2026-06-11              2026-07-06            …
     │                   │                       │
     ├───────────────────┼───────────────────────┼──────────────────▶
     │  PREVIO AL        │  DURANTE EL MUNDIAL   │  DESPUÉS DE LOS
     │  MUNDIAL          │  EN MÉXICO            │  PARTIDOS EN MÉXICO
     │                   │                       │
     └─ 11 días          └─ 25 días              └─ abierto
```

Dos detalles finos que casi nadie piensa y que aquí sí se cuidaron:

- **Los intervalos son `[desde, hasta)`**: el límite de abajo incluye, el de arriba excluye. Así un tuit del 11 de junio cae en **un solo** período, nunca en dos. Esto es MECE aplicado al tiempo.
- **Las fechas se convierten a hora de México.** Twitter guarda todo en UTC. Un tuit de las 19:00 del 10 de junio en CDMX se registra como **01:00 del 11** en UTC. Sin convertir, cruzaría de período un día antes de tiempo — y con ~42 tuits diarios, eso mueve como diez tuits en cada frontera.
- El corte del 6 de julio no es arbitrario: **el último partido en territorio mexicano** fueron los octavos del 5 de julio en el Estadio Azteca. El torneo siguió hasta el 19 de julio, pero ya fuera de México.

---

## 13. Cosas que este sistema NO puede decirte

Ser claro con esto es parte del método, no una disculpa.

| Limitación | Por qué importa |
|---|---|
| **No hay validación humana** | Nadie ha calificado a mano una muestra para comparar. Sin eso, no sabemos si la IA califica *bien*, sólo que califica *consistentemente*. Es el pendiente más grande. |
| **`aplicable=false` no es cero** | Si lo promedias como 0, tu resultado está mal. Las celdas están vacías a propósito. |
| **La ausencia está codificada dos veces** | El bug de MECE del §5. Invalida comparaciones finas y rompe el criterio 4. |
| **Miles de respuestas sin su tuit padre** | Se marcan en la columna `contexto_incompleto` y se le avisa a la IA, pero la conversación no se reconstruye. |
| **0.5% de bloqueos de contenido** | El filtro de seguridad del proveedor rechaza algunas respuestas. Esas filas se reintentan para siempre y nunca se resuelven. |
| **Esto mide lo que se TUITEA, no lo que se PIENSA** | Quien tuitea no es una muestra representativa de nadie. Es un sesgo de plataforma, no un defecto del código. |

---

## 14. Glosario

| Término | En corto |
|---|---|
| **Corpus** | El conjunto de textos que se analiza. Aquí, 2,631 tuits. |
| **Rúbrica** | Tabla de criterios × niveles con descriptores, para calificar igual siempre. |
| **Criterio** | Una dimensión que se califica. Aquí hay 4. |
| **Nivel** | Un escalón dentro de un criterio. Aquí 0-5, o 0/1 en el criterio 4. |
| **Descriptor** | El texto que explica qué tiene que pasar para merecer ese nivel. |
| **Valencia** | Si algo es positivo o negativo. Distinto de *intensidad* y de *logro*. |
| **Saliencia** | Qué tan presente está un tema, independientemente del tono. |
| **MECE** | Sin encimes, sin huecos. |
| **Anclaje** | Que el instrumento nombre explícitamente su objeto de estudio. |
| **Checkpoint** | Bitácora de resultados que permite reanudar sin repetir gasto. |
| **Payload** | El mensaje completo que se le manda a la IA. |
| **Token** | Pedacito de texto (~¾ de palabra). Es la unidad en que se cobra. |
| **Temperatura** | Qué tan creativa se le permite ser a la IA. Aquí 0 = máxima consistencia. |
| **Formato ancho** | 1 renglón por tuit, una columna por criterio. Para mirar. |
| **Formato tidy** | 1 renglón por cada par (tuit, criterio). Para graficar y hacer estadística. |

---

## 15. Las tres ideas para llevarse

1. **Una rúbrica sirve si es MECE.** Sin encimes y sin huecos. Cuando se rompe — como pasa aquí con la ausencia codificada dos veces — el costo es volver a medir todo desde cero.

2. **El instrumento tiene que nombrar su objeto.** "Fascinación" no se puede medir; "fascinación **por México**" sí. 55% de falsos positivos fue el precio de esa omisión.

3. **Que la IA juzgue, que el programa calcule.** La IA elige una etiqueta de una lista cerrada y explica por qué. El puntaje, la validación y la agregación los hace el código, determinísticamente. Así ningún error es silencioso.

---

*Documento generado a partir del código y los datos reales del repositorio: [rubrica.json](rubrica.json), [evaluador/scoring.py](evaluador/scoring.py), [config.toml](config.toml) y `checkpoint_anclada.jsonl` (corrida del 11 de septiembre de 2026).*
