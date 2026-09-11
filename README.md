# EvaluadorTweets

Califica cada tuit de un corpus contra cada criterio de una rúbrica en PDF,
usando agentes paralelos de Google ADK, y devuelve el corpus enriquecido con
nivel, puntaje y justificación por criterio.

Corre como proceso local. El cuaderno `evaluador_tweets_rubrica.ipynb` se
conserva como **registro histórico no ejecutable**: documenta cómo se llegó a
este diseño, pero el comportamiento vigente vive en `evaluador/`.

## Puesta en marcha

```bash
py -3.12 -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
.venv/Scripts/python.exe -m pip install -e .
```

La clave de API se lee de la variable de entorno `GOOGLE_API_KEY` o del
archivo `.env` (excluido por `.gitignore`; ver `.env.example`). Nunca vive en
`config.toml` ni se imprime.

## Etapas

Cada etapa lee sus insumos de disco y escribe su artefacto. Son independientes:
la reparación y la traducción, que ya están hechas y costaron dinero, no se
rehacen por correr la calificación.

```
  xlsx ──▶ reparar ──▶ *_reparado.csv ──┐
                                        ├──▶ traducir ──▶ *_traducido.csv ──┐
  fuente extra ──▶ consolidar ──────────┘                                   │
                                                                            ▼
  rubrica.pdf ──▶ rubrica ──▶ rubrica.json ──────────────────▶ correr ──▶ checkpoint.jsonl
                                                                            │
                                            ┌───────────────────────────────┤
                                            ▼                               ▼
                                    exportar ──▶ csv ancho        graficar ──▶ html
                                             └─▶ csv tidy
```

```bash
python -m evaluador --help
python -m evaluador auditar                      # analiza un checkpoint, sin gastar
python -m evaluador correr                       # sólo estima el costo
python -m evaluador correr --confirmar           # autoriza el gasto
python -m evaluador exportar
python -m evaluador graficar
```

## Perfiles

Los parámetros viven en `config.toml`, en perfiles con nombre. Cambiar de una
pasada de prueba a la corrida completa no requiere editar código.

| perfil | selección | checkpoint |
|---|---|---|
| `piloto` | 60 tuits | `checkpoint_piloto_local.jsonl` |
| `completo` | corpus completo | `checkpoint.jsonl` |
| `recuperacion` | corpus completo | `checkpoint_recuperado.jsonl` |

```bash
python -m evaluador --perfil completo correr --confirmar
```

Cada perfil debe declarar su propio checkpoint: un piloto no puede contaminar
la corrida completa.

## Recuperar una corrida dañada

Reanudar distingue un resultado de un fallo. Un `ERROR` o un `SIN_RESPUESTA`
se recalifica; un `OK` o un `NO_APLICABLE` se conserva y no se vuelve a pagar.

```bash
python -m evaluador auditar "checkpoint (7).jsonl"
python -m evaluador --perfil recuperacion correr --confirmar
```

El alcance de la recalificación se declara con `--alcance`:

| alcance | recalifica | |
|---|---|---|
| `fallidos` | `ERROR`, `SIN_RESPUESTA`, `PERMANENTE` | el defecto; no repite gasto |
| `sin-nivel` | lo anterior más `NO_APLICABLE` | útil si cambió la instrucción |
| `todo` | la selección entera | ignora el checkpoint |

En los tres casos el checkpoint es append-only: no se borra nada, y cada par
se resuelve por su registro válido más reciente.

## Reproducir una corrida anterior

El muestreo por semilla **no** es reproducible si el corpus cambia de tamaño.
Para calificar exactamente los mismos tuits de una corrida previa:

```bash
python -m evaluador correr --ids-de checkpoint_piloto.jsonl --confirmar
```

## Costo

La estimación mide los tokens de entrada reales con la API antes de gastar, y
`correr` no emite ninguna llamada sin `--confirmar`. La palanca principal es
`justificacion_max_palabras`: la salida domina el costo.

## Pruebas

```bash
.venv/Scripts/python.exe -m pytest tests/ -q
```

Ninguna prueba toca la red. Las que más importan no comprueban que el pipeline
califique bien, sino que falle temprano:

- `test_resolucion_al_importar.py` — toda referencia entre módulos se resuelve
  al importar, y todo `cfg.<atributo>` existe en `Config`. Un símbolo o un
  parámetro renombrado impide arrancar, en vez de fallar a las cuatro horas.
- `test_sin_entorno_alojado.py` — ningún módulo importa bibliotecas de cuaderno
  alojado ni parches del bucle de eventos.
- `test_motor_fiable.py` — un error de programación aborta sin escribir fallos;
  una racha de fallos dispara el cortacircuitos; un fallo no queda cementado.

## Limitaciones conocidas

- **`aplicable` no es lo mismo que nivel bajo.** Un tuit ajeno al criterio se
  marca `aplicable=False` con nivel vacío. No lo promedies como cero.
- **La rúbrica codifica la ausencia dos veces.** El nivel «0» y la bandera
  `aplicable=false` dicen lo mismo, y la regla 1 de la instrucción hace que
  gane casi siempre la segunda: sobre 7,708 pares resueltos, 7,586 salieron
  como `aplicable=false` y 12 como nivel «0». Para el criterio binario de
  saliencia de violencia esto es destructivo — «violencia ausente» deja de
  distinguirse de «fuera de alcance». Pendiente de un cambio de modelado.
- **Un bloqueo de contenido llega como `SIN_RESPUESTA`.** ADK no propaga
  excepción cuando el filtro rechaza una respuesta; simplemente no emite
  estado. Esas filas se reintentan en cada reanudación y nunca se resuelven.
  Observado: 0.4% del piloto.
- **Replies sin contexto.** Miles de filas son respuestas cuyo tuit padre no
  está en el corpus. Se marcan en `contexto_incompleto` y se advierte al
  modelo, pero el hilo no se reconstruye.
- **Llaves sintéticas.** Las filas que no vienen de la API (`origen=corpus_local`,
  `raw_json` vacío) reciben una llave `local:` derivada de su contenido. Son
  calificables y trazables, pero no tienen identificador de Twitter.
- **Sin contraste humano.** Hasta que no se cargue un conjunto anotado a mano,
  las calificaciones no tienen validación externa.
