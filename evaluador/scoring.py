"""Motor de calificación: agentes por criterio, validación y corrida.

Traslado de las celdas 12 a 18 del cuaderno.

IMPORTANTE — este módulo se traslada con los defectos del cuaderno INTACTOS,
a propósito. El grupo 7 del cambio `migrar-a-proceso-local` corre un piloto de
fidelidad contra `checkpoint_piloto.jsonl` para comprobar que el traslado no
alteró el comportamiento; sólo después, el grupo 8 aplica los arreglos. Si se
arreglara aquí, un fallo del piloto no distinguiría entre error de traslado y
efecto del arreglo.

Los defectos conocidos, cada uno marcado en su sitio:
  · `claves_completadas` cuenta los fallos como trabajo hecho (tarea 9.3)
  · un resultado parcial retorna en vez de lanzar excepción (tarea 8.5)
  · el semáforo cuenta filas, no llamadas (tarea 8.7)
  · `motivo_fallo` no distingue lo permanente de lo transitorio (tarea 8.1)
"""

from __future__ import annotations

import asyncio
import json
import re
import time
from pathlib import Path

import pandas as pd
from google import genai
from google.adk.runners import InMemoryRunner
from google.genai import types
from pydantic import BaseModel, Field

from .adk import (LlmAgent, ParallelAgent, config_generacion, construir_modelo,
                  ejecutar_agente)
from .config import (ALCANCES, Config, ESTADOS_RESULTADO,
                     estados_a_conservar, exigir_insumo)


# ──────────────────────────────────────────────────────────────────────────
#  Esquema de una calificación
# ──────────────────────────────────────────────────────────────────────────

class Calificacion(BaseModel):
    aplicable: bool = Field(
        description="True si el contenido del tweet tiene relación con lo que este criterio evalúa. "
                    "False si el tweet es ajeno al criterio. OJO: 'aplicable=False' NO es lo mismo "
                    "que el nivel más bajo; un tweet fuera de alcance no es un tweet de bajo logro."
    )
    nivel: str | None = Field(
        default=None,
        description="La etiqueta EXACTA del nivel de logro que refleja el tweet, copiada literalmente "
                    "de la lista de niveles válidos. null si aplicable=False."
    )
    justificacion: str = Field(
        description="Por qué se asigna ese nivel: cita el contenido concreto del tweet y relaciónalo "
                    "con el descriptor del nivel elegido. En ESPAÑOL. Si aplicable=False, explica "
                    "por qué el criterio queda fuera de alcance para este tweet."
    )


# ──────────────────────────────────────────────────────────────────────────
#  Instrucción por criterio
# ──────────────────────────────────────────────────────────────────────────

def instruccion_para(cfg: Config, criterio: dict) -> str:
    """Criterio PRIMERO, tweet AL FINAL: deja el prefijo idéntico entre llamadas
    del mismo criterio, elegible para el caché implícito de Gemini."""
    niveles = "\n".join(
        f"  · «{n['etiqueta']}»"
        + (f" ({n['puntos']} pts)" if n.get("puntos") is not None else "")
        + f": {n['descriptor']}"
        for n in criterio["niveles"]
    )
    etiquetas = " | ".join(f"«{e}»" for e in criterio["etiquetas_validas"])

    return (
        f"Eres evaluador experto del criterio [{criterio['id_criterio']}] "
        f"«{criterio['nombre']}» de una rúbrica de evaluación.\n"
        f"Evalúas UN tweet a la vez, contra ESTE criterio y ningún otro.\n\n"
        f"CONSIGNA DEL CRITERIO:\n{criterio['consigna']}\n\n"
        f"NIVELES DE LOGRO (del más bajo al más alto):\n{niveles}\n\n"
        f"ESCALA VÁLIDA — el campo 'nivel' DEBE ser exactamente una de estas etiquetas, "
        f"copiada literalmente:\n{etiquetas}\n\n"
        f"REGLAS OBLIGATORIAS:\n"
        f"1. APLICABILIDAD PRIMERO. Si el contenido del tweet es ajeno a lo que este criterio "
        f"evalúa, responde aplicable=false, nivel=null, y explica en la justificación por qué "
        f"queda fuera de alcance. NO asignes el nivel más bajo a un tweet que simplemente no "
        f"trata el tema: 'fuera de alcance' y 'bajo logro' son cosas distintas.\n"
        f"2. NO INVENTES. No infieras, no supongas ni des crédito por contenido que no está "
        f"presente en el texto del tweet. Si algo que el criterio requiere no aparece, dilo.\n"
        f"3. CONTEXTO INCOMPLETO. Si el tweet viene marcado con una advertencia de contexto "
        f"incompleto, califica ÚNICAMENTE con el texto disponible, reconoce la limitación en tu "
        f"justificación y NO reconstruyas la conversación faltante.\n"
        f"4. ESCALA CERRADA. El nivel debe ser una de las etiquetas listadas arriba, textual. "
        f"No inventes niveles intermedios ni reformules las etiquetas.\n"
        f"5. IDIOMA. El tweet puede estar en cualquier idioma; evalúalo en su idioma original. "
        f"Tu justificación debe estar SIEMPRE en ESPAÑOL.\n"
        f"6. EXTENSIÓN. La justificación debe tener como máximo {cfg.justificacion_max_palabras} "
        f"palabras. Sé específico y concreto, no genérico. No uses frases de relleno como 'Claro', "
        f"'Entiendo' o 'Voy a evaluar': empieza directo por la evaluación.\n\n"
        f"Devuelve tu respuesta conforme al esquema estructurado solicitado."
    )


# ──────────────────────────────────────────────────────────────────────────
#  Equipo de agentes
# ──────────────────────────────────────────────────────────────────────────

def clave_estado(criterio: dict) -> str:
    return f"cal_{criterio['slug']}"


def construir_equipo(cfg: Config, criterios: list[dict],
                     modelo: str | None = None) -> tuple:
    """Un agente por criterio de la rúbrica. N nunca aparece fijo en el código."""
    agentes = []
    for c in criterios:                      # ← el bucle es todo el agnosticismo
        agentes.append(LlmAgent(
            name=f"Eval_{c['slug']}",
            model=construir_modelo(cfg, modelo),
            instruction=instruccion_para(cfg, c),
            output_schema=Calificacion,
            output_key=clave_estado(c),
            generate_content_config=config_generacion(cfg),
            disallow_transfer_to_parent=True,
            disallow_transfer_to_peers=True,
        ))
    equipo = ParallelAgent(name="EquipoCriteriosParalelo", sub_agents=agentes)
    return equipo, [clave_estado(c) for c in criterios]


def verificar_aislamiento(equipo, criterios: list[dict]) -> None:
    """La instrucción de un agente no debe mencionar los descriptores de los
    otros criterios."""
    if len(criterios) < 2:
        return
    otro = criterios[1]["niveles"][0]["descriptor"][:60]
    if otro in equipo.sub_agents[0].instruction:
        raise RuntimeError(
            "Fuga de aislamiento: un agente ve el descriptor de otro criterio"
        )


# ──────────────────────────────────────────────────────────────────────────
#  Validación
# ──────────────────────────────────────────────────────────────────────────

def _normalizar(s) -> str:
    return re.sub(r"\s+", " ", str(s or "")).strip().strip("«»\"'").lower()


class Validador:
    """El puntaje se deriva de la rúbrica, nunca del modelo."""

    def __init__(self, criterios: list[dict]) -> None:
        self.puntos = {c["slug"]: {n["etiqueta"]: n.get("puntos") for n in c["niveles"]}
                       for c in criterios}
        self.etiquetas = {c["slug"]: set(c["etiquetas_validas"]) for c in criterios}
        self.numerica = {c["slug"]: c["escala_numerica"] for c in criterios}

    def validar(self, slug: str, cruda: dict) -> dict:
        """estado ∈ {OK, NO_APLICABLE, FUERA_DE_ESCALA}"""
        reg = {
            "slug": slug,
            "aplicable": bool(cruda.get("aplicable")),
            "nivel": None,
            "puntaje": None,
            "justificacion": (cruda.get("justificacion") or "").strip(),
            "estado": "OK",
            "detalle": "",
        }
        if not reg["aplicable"]:
            reg["estado"] = "NO_APLICABLE"
            return reg

        nivel_crudo = cruda.get("nivel")
        validas = self.etiquetas[slug]
        # coincidencia exacta, y si no, tolerante a espacios/comillas/mayúsculas
        if nivel_crudo in validas:
            nivel = nivel_crudo
        else:
            candidatos = [e for e in validas if _normalizar(e) == _normalizar(nivel_crudo)]
            nivel = candidatos[0] if candidatos else None

        if nivel is None:
            reg["estado"] = "FUERA_DE_ESCALA"
            reg["detalle"] = f"nivel devuelto {nivel_crudo!r} no está en la escala del criterio"
            return reg

        reg["nivel"] = nivel
        if self.numerica[slug]:
            reg["puntaje"] = self.puntos[slug].get(nivel)   # ← determinista, de la rúbrica
        return reg


# ──────────────────────────────────────────────────────────────────────────
#  Evaluación de un payload
# ──────────────────────────────────────────────────────────────────────────

async def evaluar_payload(runner, payload: str, claves: list[str]) -> dict:
    partes = [types.Part(text=payload),
              types.Part(text="Evalúa el tweet anterior según tu criterio.")]
    return await ejecutar_agente(runner, partes, claves)


async def prueba_de_humo(cfg: Config, sub: pd.DataFrame, criterios: list[dict],
                         idx: int = 0, escribir=print) -> dict:
    equipo, claves = construir_equipo(cfg, criterios)
    verificar_aislamiento(equipo, criterios)
    validador = Validador(criterios)

    fila = sub.iloc[idx]
    runner = InMemoryRunner(agent=equipo, app_name="smoke")
    estado = await evaluar_payload(runner, fila["_payload"], claves)

    escribir(f"TWEET [{fila[cfg.col_id]}] lang={fila.get(cfg.col_lang)} "
             f"contexto={fila['contexto_incompleto'] or 'completo'}")
    escribir(f"  {str(fila[cfg.col_texto])[:220]}\n")
    escribir(f"Resultados recibidos: {len(estado)}/{len(criterios)}\n")

    for c in criterios:
        k = clave_estado(c)
        if k not in estado:
            escribir(f"[{c['id_criterio']}] ❌ sin resultado")
            continue
        reg = validador.validar(c["slug"], estado[k])
        marca = {"OK": "✅", "NO_APLICABLE": "➖", "FUERA_DE_ESCALA": "⚠️"}[reg["estado"]]
        pts = f" ({reg['puntaje']} pts)" if reg["puntaje"] is not None else ""
        escribir(f"{marca} [{c['id_criterio']}] {c['nombre'][:44]}")
        escribir(f"     nivel: {reg['nivel'] or '—'}{pts}   estado: {reg['estado']}")
        escribir(f"     just : {reg['justificacion'][:200]}")
        if reg["detalle"]:
            escribir(f"     ⚠️  {reg['detalle']}")
        escribir("")
    return estado


# ──────────────────────────────────────────────────────────────────────────
#  Estimación de costo
# ──────────────────────────────────────────────────────────────────────────

def estimar_costo(cfg: Config, sub: pd.DataFrame, criterios: list[dict],
                  modelo: str | None = None, muestra_conteo: int = 15,
                  llamadas: int | None = None, escribir=print) -> dict:
    """Estima el gasto de una corrida.

    ``llamadas`` permite estimar sólo el trabajo PENDIENTE en vez de toda la
    selección. Importa: al reanudar sobre un checkpoint con 7,708 pares ya
    resueltos, estimar la selección completa exagera el costo por un factor de
    cuatro, y una compuerta que miente sobre el gasto no sirve para decidir.
    """
    modelo = modelo or cfg.modelo
    if modelo not in cfg.precios:
        escribir(f"⚠️  Sin precio para '{modelo}'. Añádelo a [precios] en config.toml.")
        return {}
    p_in, p_out = cfg.precio_de(modelo)
    cliente = genai.Client()
    n_criterios = len(criterios)

    # Tokens de entrada reales: instrucción del criterio + payload, medidos con la API
    filas_m = sub.sample(n=min(muestra_conteo, len(sub)), random_state=cfg.semilla)
    medidas = []
    for c in criterios:
        instr = instruccion_para(cfg, c)
        for _, f in filas_m.iterrows():
            try:
                r = cliente.models.count_tokens(
                    model=modelo, contents=f"{instr}\n\n{f['_payload']}"
                )
                medidas.append(r.total_tokens)
            except Exception:
                medidas.append(len(instr + f["_payload"]) // 4)   # respaldo heurístico
    tok_in_medio = sum(medidas) / max(len(medidas), 1)

    # Salida: justificación acotada + envoltura JSON del esquema
    tok_out_medio = cfg.justificacion_max_palabras * 1.6 + 40
    if cfg.presupuesto_razonamiento != 0:
        tok_out_medio += 500 if cfg.presupuesto_razonamiento < 0 else cfg.presupuesto_razonamiento

    totales = len(sub) * n_criterios
    llamadas = totales if llamadas is None else llamadas
    t_in, t_out = llamadas * tok_in_medio, llamadas * tok_out_medio
    costo = t_in / 1e6 * p_in + t_out / 1e6 * p_out
    razona = "apagado" if cfg.presupuesto_razonamiento == 0 else cfg.presupuesto_razonamiento

    escribir(f"{'=' * 72}")
    escribir(f"ESTIMACIÓN · {modelo} · razonamiento={razona}")
    escribir(f"{'=' * 72}")
    escribir(f"  filas              {len(sub):,}")
    escribir(f"  criterios (N)      {n_criterios}")
    if llamadas != totales:
        escribir(f"  pares en total     {totales:,}")
        escribir(f"  llamadas a emitir  {llamadas:,}   "
                 f"(el resto se recupera del checkpoint)")
    else:
        escribir(f"  llamadas           {llamadas:,}")
    escribir(f"  tokens entrada     {t_in / 1e6:>8.2f} M  (medido: {tok_in_medio:,.0f}/llamada)")
    escribir(f"  tokens salida      {t_out / 1e6:>8.2f} M  (estimado: {tok_out_medio:,.0f}/llamada)")
    escribir(f"  ─────────────────────────────────")
    escribir(f"  costo entrada      ${t_in / 1e6 * p_in:>8.2f}")
    escribir(f"  costo salida       ${t_out / 1e6 * p_out:>8.2f}   ← la salida domina")
    escribir(f"  COSTO TOTAL        ${costo:>8.2f}")
    escribir(f"  por criterio       ${costo / max(n_criterios, 1):>8.2f}")
    filas_vuelo = cfg.filas_en_vuelo(n_criterios)
    escribir(f"  tiempo aprox.      {llamadas / n_criterios / filas_vuelo * 8 / 60:>8.0f} min "
             f"({cfg.llamadas_simultaneas} llamadas simultáneas = "
             f"{filas_vuelo} filas en vuelo)")
    escribir(f"{'=' * 72}")
    if cfg.presupuesto_razonamiento != 0:
        escribir("  💡 presupuesto_razonamiento=0 reduciría el costo ~2.7×")
    escribir(f"  💡 justificacion_max_palabras={cfg.justificacion_max_palabras} "
             f"es la palanca principal")
    escribir(f"{'=' * 72}")
    return {"llamadas": llamadas, "costo": costo}


# ──────────────────────────────────────────────────────────────────────────
#  Checkpoint
# ──────────────────────────────────────────────────────────────────────────

def claves_completadas(ruta: Path, alcance: str = "fallidos") -> set[tuple[str, str]]:
    """Pares (tweet_id, slug) que NO hay que recalificar bajo este alcance.

    Filtra por estado, que es la corrección central. El cuaderno añadía todo
    registro presente, así que un fallo contaba como trabajo terminado y
    reanudar lo saltaba para siempre: es lo que dejó 2,540 pares congelados
    tras la corrida del NameError, irreparables por reejecución.

    NO_APLICABLE sí es un resultado terminado —es el modelo respondiendo que
    el criterio no aplica, no un fallo— y confundirlo con error dispararía la
    recalificación del 74% del corpus sin motivo.

    Cada par se resuelve por su registro VÁLIDO más reciente; si no tiene
    ninguno, por el último escrito.
    """
    conservar = estados_a_conservar(alcance)
    if not conservar or not ruta.exists():
        return set()

    ultimo: dict[tuple[str, str], str] = {}
    ultimo_bueno: dict[tuple[str, str], str] = {}
    with ruta.open(encoding="utf-8") as fh:
        for linea in fh:
            linea = linea.strip()
            if not linea:
                continue
            try:
                r = json.loads(linea)
            except Exception:
                continue   # línea truncada por una interrupción
            k = (str(r["tweet_id"]), r["slug"])
            estado = r.get("estado")
            ultimo[k] = estado
            if estado in ESTADOS_RESULTADO:
                ultimo_bueno[k] = estado

    return {k for k in ultimo if ultimo_bueno.get(k, ultimo[k]) in conservar}


class Escritor:
    """Escritor por ruta: permite usar checkpoints separados sin que las líneas
    terminen en el archivo equivocado."""

    def __init__(self) -> None:
        self._abiertos: dict[str, object] = {}

    def anexar(self, registros: list[dict], ruta: Path) -> None:
        fh = self._abiertos.get(str(ruta))
        if fh is None or fh.closed:
            # Si una corrida anterior murió a media línea, el archivo no termina
            # en \n. Sin esto, el primer registro nuevo se concatenaría a la
            # línea truncada y se perdería también (JSON inválido).
            if ruta.exists() and ruta.stat().st_size:
                with ruta.open("rb") as prev:
                    prev.seek(-1, 2)
                    cortada = prev.read(1) != b"\n"
                if cortada:
                    with ruta.open("a", encoding="utf-8") as fix:
                        fix.write("\n")
            fh = ruta.open("a", encoding="utf-8")
            self._abiertos[str(ruta)] = fh
        for r in registros:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
        fh.flush()                 # ← inmediato: sobrevive a una interrupción

    def cerrar(self) -> None:
        for fh in self._abiertos.values():
            if not fh.closed:
                fh.close()
        self._abiertos.clear()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.cerrar()
        return False


class FalloEstructural(RuntimeError):
    """Error de programación o de configuración: afecta a TODAS las filas por
    igual, así que la corrida no puede continuar.

    Existe por la corrida del NameError. ``name 'evaluar_payload' is not
    defined`` se clasificaba como 'ERROR', indistinguible de un fallo de red,
    se reintentaba cinco veces con retroceso exponencial —30 s por fila,
    ~4 h en total dormidas en vano— y se escribía al checkpoint como fallo
    permanente. 15,384 registros así.
    """


class ResultadoParcial(RuntimeError):
    """El conjunto de agentes devolvió menos criterios de los pedidos."""

    def __init__(self, faltantes: list[str]) -> None:
        self.faltantes = faltantes
        super().__init__(
            f"el equipo no devolvió estado para {len(faltantes)} criterio(s): "
            + ", ".join(faltantes)
        )


#: Errores que no pueden depender del dato en esta ruta de código. Si ocurren,
#: ocurren para todas las filas.
_ESTRUCTURALES = (NameError, ImportError, AttributeError, TypeError, SyntaxError)

_SENAS_CREDENCIAL = (
    "no api key", "api key not valid", "api_key_invalid",
    "permission_denied", "unauthenticated", "invalid authentication",
)


def es_estructural(exc: Exception) -> bool:
    """Distingue lo que jamás se va a resolver de lo que puede resolverse solo."""
    if isinstance(exc, FalloEstructural):
        return True
    if isinstance(exc, _ESTRUCTURALES):
        return True
    return any(s in str(exc).lower() for s in _SENAS_CREDENCIAL)


def motivo_fallo(exc: Exception) -> str:
    """Clasifica un fallo para el registro del checkpoint.

    'PERMANENTE' y 'BLOQUEADO' no se reintentan; el resto sí.
    """
    if es_estructural(exc):
        return "PERMANENTE"
    t = str(exc).lower()
    if any(k in t for k in ("safety", "blocked", "prohibited", "recitation")):
        return "BLOQUEADO"     # filtro de contenido: NO es nivel bajo ni no-aplicable
    if any(k in t for k in ("429", "rate limit", "resource_exhausted", "quota")):
        return "LIMITE_TASA"
    if any(k in t for k in ("500", "502", "503", "504", "unavailable", "internal")):
        return "ERROR_SERVIDOR"
    if isinstance(exc, (asyncio.TimeoutError, TimeoutError)):
        return "TIEMPO_AGOTADO"
    if isinstance(exc, ResultadoParcial):
        return "SIN_RESPUESTA"
    return "ERROR"


# ──────────────────────────────────────────────────────────────────────────
#  Corrida
# ──────────────────────────────────────────────────────────────────────────

async def _evaluar_fila(cfg: Config, validador: Validador, runner, fila,
                        pendientes: list[str], sem) -> list[dict]:
    """Califica una fila contra sus criterios pendientes.

    Lanza :class:`FalloEstructural` si el error afecta a todas las filas: quien
    llame debe abortar la corrida en vez de seguir escribiendo fallos.
    """
    tweet_id = str(fila[cfg.col_id])
    async with sem:
        ultimo: Exception | None = None
        for intento in range(1, cfg.max_intentos + 1):
            try:
                claves = [f"cal_{s}" for s in pendientes]
                estado = await asyncio.wait_for(
                    evaluar_payload(runner, fila["_payload"], claves),
                    timeout=cfg.timeout_llamada,
                )

                # Un resultado parcial es un FALLO REINTENTABLE, no un
                # resultado. El cuaderno materializaba aquí los registros
                # SIN_RESPUESTA y retornaba; al no lanzar excepción, el bucle
                # de reintentos nunca se activaba y el hueco se escribía como
                # definitivo. El piloto lo reprodujo: 1 de 240.
                faltantes = [s for s in pendientes if f"cal_{s}" not in estado]
                if faltantes:
                    raise ResultadoParcial(faltantes)

                salida = []
                for slug in pendientes:
                    reg = validador.validar(slug, estado[f"cal_{slug}"])
                    reg["tweet_id"] = tweet_id
                    reg["contexto_incompleto"] = fila["contexto_incompleto"]
                    salida.append(reg)
                return salida

            except Exception as exc:
                # Un fallo estructural afecta a todas las filas por igual:
                # reintentarlo es tiempo perdido y registrarlo es dato falso.
                if es_estructural(exc):
                    raise FalloEstructural(
                        f"fallo estructural al evaluar el tuit {tweet_id}: "
                        f"{type(exc).__name__}: {exc}"
                    ) from exc
                ultimo = exc
                if motivo_fallo(exc) == "BLOQUEADO" or intento == cfg.max_intentos:
                    break
                await asyncio.sleep(min(2 ** intento, cfg.retraso_maximo))

        motivo = motivo_fallo(ultimo)
        return [{"tweet_id": tweet_id, "slug": slug, "aplicable": False, "nivel": None,
                 "puntaje": None, "justificacion": "", "estado": motivo,
                 "detalle": str(ultimo)[:300],
                 "contexto_incompleto": fila["contexto_incompleto"]}
                for slug in pendientes]


async def correr(cfg: Config, sub: pd.DataFrame, criterios: list[dict],
                 ruta: Path | None = None, equipo=None, alcance: str | None = None,
                 rubrica: dict | None = None, escribir=print) -> dict:
    """`equipo` permite correr con un ParallelAgent distinto (p.ej. otro modelo
    en la calibración) sin mutar el equipo de producción."""
    ruta = ruta or cfg.checkpoint
    n_criterios = len(criterios)
    validador = Validador(criterios)
    if equipo is None:
        equipo, _ = construir_equipo(cfg, criterios)
        verificar_aislamiento(equipo, criterios)

    alcance = alcance or cfg.alcance_recalificacion
    hechas = claves_completadas(ruta, alcance)
    todos_slugs = [c["slug"] for c in criterios]

    trabajo = []
    for _, fila in sub.iterrows():
        tid = str(fila[cfg.col_id])
        pend = [s for s in todos_slugs if (tid, s) not in hechas]
        if pend:
            trabajo.append((fila, pend))

    total_pendiente = sum(len(p) for _, p in trabajo)
    reusados = len(sub) * n_criterios - total_pendiente
    escribir(f"Checkpoint '{ruta.name}': {reusados:,} resultados reutilizados "
             f"(alcance «{alcance}»)")
    escribir(f"Pendientes: {total_pendiente:,} llamadas en {len(trabajo):,} filas")

    if not trabajo:
        escribir("✅ Nada pendiente: el checkpoint ya cubre todo el subconjunto.")
        return {"ok": 0, "fallidas": 0, "reusados": reusados, "abortada": False}

    # El semáforo cuenta LLAMADAS. Las filas en vuelo se derivan del límite de
    # llamadas y del número de criterios, porque cada fila abanica un agente
    # por criterio: el cuaderno limitaba filas, así que 8 filas con 4 criterios
    # eran 32 peticiones simultáneas sin que nada lo declarara.
    filas_vuelo = cfg.filas_en_vuelo(n_criterios)
    escribir(f"Concurrencia: {cfg.llamadas_simultaneas} llamadas simultáneas ÷ "
             f"{n_criterios} criterios = {filas_vuelo} filas en vuelo "
             f"({filas_vuelo * n_criterios} peticiones)")
    if n_criterios > cfg.llamadas_simultaneas:
        escribir(f"   ⚠️  la rúbrica tiene más criterios ({n_criterios}) que el límite "
                 f"de llamadas ({cfg.llamadas_simultaneas}): se procesa una fila a la "
                 f"vez y el abanico supera el límite configurado")

    if rubrica is not None:
        registrar_huella(ruta, rubrica)

    sem = asyncio.Semaphore(filas_vuelo)
    ok = fallidas = 0
    seguidas = 0            # fallos consecutivos, para el cortacircuitos
    abortada = None
    t0 = time.time()
    ultimo_reporte = t0

    with Escritor() as escritor:
        # Reciclado del runner por bloques: evita acumular sesiones en corridas largas
        for ini in range(0, len(trabajo), cfg.reciclar_cada):
            bloque = trabajo[ini:ini + cfg.reciclar_cada]
            runner = InMemoryRunner(agent=equipo, app_name=f"run_{ini}")

            tareas = [asyncio.ensure_future(
                          _evaluar_fila(cfg, validador, runner, f, p, sem))
                      for f, p in bloque]
            try:
                for fut in asyncio.as_completed(tareas):
                    registros = await fut
                    escritor.anexar(registros, ruta)
                    buenas = sum(r["estado"] in ESTADOS_RESULTADO for r in registros)
                    malas = len(registros) - buenas
                    ok += buenas
                    fallidas += malas

                    # Cortacircuitos: una racha larga de fallos nunca es mala
                    # suerte. En la corrida del NameError, 3,846 filas fallaron
                    # idénticamente una tras otra durante horas y nada paró.
                    seguidas = seguidas + 1 if (malas and not buenas) else 0
                    if seguidas >= cfg.fallos_consecutivos_max:
                        abortada = (
                            f"{seguidas} filas consecutivas fallidas "
                            f"(umbral {cfg.fallos_consecutivos_max}). "
                            f"Último motivo: {registros[0].get('estado')} — "
                            f"{str(registros[0].get('detalle'))[:160]}"
                        )
                        break

                    hechas_n = ok + fallidas
                    ahora = time.time()
                    # Avance por conteo Y por tiempo: durante una racha de
                    # reintentos el conteo no avanza, y sin el reporte temporal
                    # no hay forma de distinguir trabajo de cuelgue.
                    if (hechas_n % 50 == 0 or hechas_n == total_pendiente
                            or ahora - ultimo_reporte >= 30):
                        ultimo_reporte = ahora
                        tasa = hechas_n / max(ahora - t0, 1e-9)
                        rest = (total_pendiente - hechas_n) / max(tasa, 1e-9)
                        escribir(f"  {hechas_n:,}/{total_pendiente:,} · {fallidas:,} fallidas · "
                                 f"{tasa:.1f}/s · faltan ~{rest / 60:.0f} min")
            except FalloEstructural as exc:
                # No se escribe ningún registro de fallo: un error de
                # programación o de credencial no es dato sobre los tuits.
                escribir(f"\n⛔ ABORTADA · fallo estructural\n   {exc}")
                escribir(f"   {ok:,} resultados escritos antes del aborto quedan íntegros "
                         f"y la reanudación continúa desde ahí.")
                raise
            finally:
                for tarea in tareas:
                    if not tarea.done():
                        tarea.cancel()

            del runner   # libera las sesiones del bloque
            if abortada:
                break

    minutos = (time.time() - t0) / 60
    if abortada:
        escribir(f"\n⛔ ABORTADA por cortacircuitos tras {minutos:.1f} min")
        escribir(f"   {abortada}")
        escribir(f"   {ok:,} resultados escritos quedan íntegros; reanudar continúa desde ahí.")
    else:
        escribir(f"\n✅ Corrida terminada en {minutos:.1f} min")
    escribir(f"   {ok:,} calificaciones · {fallidas:,} fallidas · {reusados:,} reutilizadas")
    if fallidas:
        escribir("   ⚠️  los fallos se recalifican solos al reanudar con alcance «fallidos»")
    return {"ok": ok, "fallidas": fallidas, "reusados": reusados,
            "abortada": bool(abortada), "motivo_aborto": abortada}


def cargar_resultados(ruta: Path) -> pd.DataFrame:
    """Si una fila se reevaluó, gana la última escrita.

    DEFECTO TRASLADADO (tarea 9.4): debería ganar el último resultado VÁLIDO,
    no el último a secas. Hoy da igual —verificado: ningún par tuvo un
    resultado bueno pisado por un fallo posterior— pero en cuanto los fallos se
    reintenten la secuencia ERROR → OK se vuelve común y la regla debe ser
    explícita.
    """
    exigir_insumo(ruta, "el checkpoint con los resultados", "correr")
    filas = []
    with ruta.open(encoding="utf-8") as fh:
        for linea in fh:
            linea = linea.strip()
            if linea:
                try:
                    filas.append(json.loads(linea))
                except Exception:
                    continue
    df = pd.DataFrame(filas)
    if df.empty:
        return df
    # Gana el último registro VÁLIDO del par; si no tiene ninguno, el último
    # escrito, para que su diagnóstico quede disponible. Con la reanudación
    # filtrada la secuencia ERROR → OK se vuelve común, así que la regla no
    # puede ser "el último" a secas.
    df["_valido"] = df["estado"].isin(ESTADOS_RESULTADO)
    df = df.sort_values("_valido", kind="stable")
    df = df.drop_duplicates(subset=["tweet_id", "slug"], keep="last")
    return df.drop(columns="_valido")

# ──────────────────────────────────────────────────────────────────────────
#  Auditoría de un checkpoint
# ──────────────────────────────────────────────────────────────────────────

def auditar(ruta: Path, criterios: list[dict] | None = None,
            escribir=print) -> dict:
    """Analiza un checkpoint sin modificarlo y sin emitir llamadas.

    Existe porque el estado de un checkpoint no es evidente: el de la corrida
    dañada tenía 27,748 registros para 10,248 pares, con repeticiones de hasta
    14 veces del mismo par, y 15,384 de esos registros eran el mismo error de
    programación. Nada en el archivo lo decía.
    """
    exigir_insumo(ruta, "el checkpoint a auditar", "correr")

    registros = 0
    ilegibles = 0
    apariciones: dict[tuple[str, str], int] = {}
    ultimo: dict[tuple[str, str], dict] = {}
    ultimo_bueno: dict[tuple[str, str], dict] = {}
    slugs: set[str] = set()

    with ruta.open(encoding="utf-8") as fh:
        for linea in fh:
            linea = linea.strip()
            if not linea:
                continue
            try:
                r = json.loads(linea)
                k = (str(r["tweet_id"]), r["slug"])
            except Exception:
                ilegibles += 1
                continue
            registros += 1
            slugs.add(r["slug"])
            apariciones[k] = apariciones.get(k, 0) + 1
            ultimo[k] = r
            if r.get("estado") in ESTADOS_RESULTADO:
                ultimo_bueno[k] = r

    final = {k: ultimo_bueno.get(k, ultimo[k]) for k in ultimo}
    por_estado: dict[str, int] = {}
    for r in final.values():
        e = r.get("estado", "?")
        por_estado[e] = por_estado.get(e, 0) + 1

    repetidos = sum(1 for n in apariciones.values() if n > 1)
    max_rep = max(apariciones.values(), default=0)
    tuits = len({t for t, _ in ultimo})
    resueltos = sum(n for e, n in por_estado.items() if e in ESTADOS_RESULTADO)
    fallidos = len(final) - resueltos

    escribir(f"{'=' * 72}")
    escribir(f"AUDITORÍA · {ruta.name}")
    escribir(f"{'=' * 72}")
    escribir(f"  registros escritos        {registros:>8,}")
    if ilegibles:
        escribir(f"  líneas ilegibles          {ilegibles:>8,}  (omitidas)")
    escribir(f"  pares tuit×criterio        {len(final):>8,}")
    escribir(f"  tuits distintos            {tuits:>8,}")
    escribir(f"  criterios distintos        {len(slugs):>8,}")
    if repetidos:
        escribir(f"  pares con repeticiones     {repetidos:>8,}  "
                 f"(hasta {max_rep} veces el mismo)")

    escribir(f"\n  estado final de cada par:")
    for e, n in sorted(por_estado.items(), key=lambda x: -x[1]):
        marca = "✅" if e in ESTADOS_RESULTADO else "❌"
        escribir(f"    {marca} {e:<18} {n:>8,}  {n / max(len(final), 1):6.1%}")

    escribir(f"\n  resueltos {resueltos:,} · pendientes de recalificar {fallidos:,}")

    # Diagnósticos predominantes de los fallos
    motivos: dict[str, int] = {}
    for r in final.values():
        if r.get("estado") not in ESTADOS_RESULTADO:
            d = str(r.get("detalle") or "")[:110]
            motivos[d] = motivos.get(d, 0) + 1
    if motivos:
        escribir(f"\n  diagnósticos de fallo más frecuentes:")
        for d, n in sorted(motivos.items(), key=lambda x: -x[1])[:5]:
            escribir(f"    [{n:>6,}] {d or '(sin detalle)'}")

    # Correspondencia con la rúbrica vigente
    discrepancia = None
    if criterios is not None:
        de_rubrica = {c["slug"] for c in criterios}
        solo_ckpt = sorted(slugs - de_rubrica)
        solo_rub = sorted(de_rubrica - slugs)
        escribir(f"\n  correspondencia con la rúbrica vigente:")
        if not solo_ckpt and not solo_rub:
            escribir(f"    ✅ los {len(slugs)} criterios coinciden")
        else:
            if solo_ckpt:
                escribir(f"    ❌ en el checkpoint pero NO en la rúbrica: {solo_ckpt}")
            if solo_rub:
                escribir(f"    ➕ en la rúbrica pero no en el checkpoint: {solo_rub}")
                escribir(f"       implica calificar {len(solo_rub) * tuits:,} pares nuevos")
        discrepancia = {"solo_checkpoint": solo_ckpt, "solo_rubrica": solo_rub}

    escribir(f"{'=' * 72}")
    return {
        "registros": registros, "ilegibles": ilegibles, "pares": len(final),
        "tuits": tuits, "criterios": sorted(slugs), "por_estado": por_estado,
        "repetidos": repetidos, "max_repeticiones": max_rep,
        "resueltos": resueltos, "fallidos": fallidos, "discrepancia": discrepancia,
    }


def ruta_huella(checkpoint: Path) -> Path:
    """Archivo lateral donde se guarda la huella de la rúbrica de una corrida."""
    return checkpoint.with_suffix(checkpoint.suffix + ".rubrica")


def registrar_huella(checkpoint: Path, rubrica: dict) -> None:
    from .rubrica import huella
    ruta_huella(checkpoint).write_text(huella(rubrica), encoding="utf-8")


def verificar_correspondencia(ruta: Path, criterios: list[dict],
                              forzar: bool = False, rubrica: dict | None = None) -> None:
    """Rehúsa reanudar si el checkpoint fue escrito con otra rúbrica.

    Mezclar dos rúbricas en un mismo checkpoint produce un CSV cuyas columnas
    no significan lo mismo en todas las filas, y eso no se detecta después.

    Comprueba dos cosas distintas: que los criterios sean los mismos, y que su
    CONTENIDO no haya cambiado. La segunda importa porque un slug puede
    sobrevivir a una reescritura completa de los descriptores — ocurrió al
    anclar esta rúbrica a México: tres slugs cambiaron y el cuarto no, aunque
    sus descriptores sí.
    """
    if not ruta.exists():
        return

    if rubrica is not None:
        from .rubrica import huella
        lateral = ruta_huella(ruta)
        if lateral.exists():
            previa, actual = lateral.read_text(encoding="utf-8").strip(), huella(rubrica)
            if previa != actual and not forzar:
                raise RuntimeError(
                    f"El checkpoint '{ruta.name}' se escribió con otra versión de la "
                    f"rúbrica.\n"
                    f"  huella registrada: {previa}\n"
                    f"  huella vigente   : {actual}\n"
                    f"Los nombres de los criterios pueden coincidir y aun así los "
                    f"descriptores haber cambiado, que es lo que decide el juicio. "
                    f"Usa un checkpoint nuevo, o pasa forzar=True si sabes lo que haces."
                )
    slugs = set()
    with ruta.open(encoding="utf-8") as fh:
        for linea in fh:
            linea = linea.strip()
            if not linea:
                continue
            try:
                slugs.add(json.loads(linea)["slug"])
            except Exception:
                continue
    if not slugs:
        return

    de_rubrica = {c["slug"] for c in criterios}
    ajenos = sorted(slugs - de_rubrica)
    if ajenos and not forzar:
        raise RuntimeError(
            f"El checkpoint '{ruta.name}' contiene criterios que la rúbrica vigente "
            f"no declara: {ajenos}\n"
            f"  criterios de la rúbrica : {sorted(de_rubrica)}\n"
            f"  criterios del checkpoint: {sorted(slugs)}\n"
            f"Mezclar dos rúbricas produce columnas que no significan lo mismo en "
            f"todas las filas. Usa un checkpoint distinto, o pasa forzar=True si "
            f"sabes lo que haces."
        )


def estimar_recalificacion(ruta: Path, sub: pd.DataFrame, criterios: list[dict],
                           cfg: Config, alcance: str | None = None,
                           escribir=print) -> dict:
    """Cuántos pares se recuperan, cuántos se recalifican y cuánto cuesta.

    Se reporta ANTES de emitir la primera llamada. Los alcances más amplios
    que «fallidos» repiten gasto ya realizado y lo advierten.
    """
    alcance = alcance or cfg.alcance_recalificacion
    hechas = claves_completadas(ruta, alcance)
    total = len(sub) * len(criterios)
    recuperados = 0
    for _, fila in sub.iterrows():
        tid = str(fila[cfg.col_id])
        recuperados += sum(1 for c in criterios if (tid, c["slug"]) in hechas)
    recalificar = total - recuperados

    escribir(f"{'=' * 72}")
    escribir(f"ALCANCE DE RECALIFICACIÓN · «{alcance}»")
    escribir(f"  {ALCANCES[alcance]}")
    escribir(f"{'=' * 72}")
    escribir(f"  pares en la selección      {total:>8,}")
    escribir(f"  se recuperan del checkpoint{recuperados:>8,}  (no se vuelven a pagar)")
    escribir(f"  se recalifican             {recalificar:>8,}")

    if alcance != "fallidos" and recuperados < total:
        escribir(f"\n  ⚠️  este alcance repite gasto ya realizado. Con «fallidos» "
                 f"sólo se\n      recalificaría lo que falló.")
    escribir(f"{'=' * 72}")
    return {"total": total, "recuperados": recuperados, "recalificar": recalificar}
