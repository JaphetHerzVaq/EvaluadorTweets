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
from .config import Config


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
                  escribir=print) -> dict:
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

    llamadas = len(sub) * n_criterios
    t_in, t_out = llamadas * tok_in_medio, llamadas * tok_out_medio
    costo = t_in / 1e6 * p_in + t_out / 1e6 * p_out
    razona = "apagado" if cfg.presupuesto_razonamiento == 0 else cfg.presupuesto_razonamiento

    escribir(f"{'=' * 72}")
    escribir(f"ESTIMACIÓN · {modelo} · razonamiento={razona}")
    escribir(f"{'=' * 72}")
    escribir(f"  filas              {len(sub):,}")
    escribir(f"  criterios (N)      {n_criterios}")
    escribir(f"  llamadas           {llamadas:,}")
    escribir(f"  tokens entrada     {t_in / 1e6:>8.2f} M  (medido: {tok_in_medio:,.0f}/llamada)")
    escribir(f"  tokens salida      {t_out / 1e6:>8.2f} M  (estimado: {tok_out_medio:,.0f}/llamada)")
    escribir(f"  ─────────────────────────────────")
    escribir(f"  costo entrada      ${t_in / 1e6 * p_in:>8.2f}")
    escribir(f"  costo salida       ${t_out / 1e6 * p_out:>8.2f}   ← la salida domina")
    escribir(f"  COSTO TOTAL        ${costo:>8.2f}")
    escribir(f"  por criterio       ${costo / max(n_criterios, 1):>8.2f}")
    escribir(f"  tiempo aprox.      {llamadas / cfg.concurrencia * 2 / 60:>8.0f} min "
             f"(concurrencia {cfg.concurrencia})")
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

def claves_completadas(ruta: Path) -> set[tuple[str, str]]:
    """Combinaciones (tweet_id, slug) ya presentes en el checkpoint.

    DEFECTO TRASLADADO (tarea 9.3): no filtra por estado, así que un registro
    de fallo cuenta como trabajo terminado y reanudar lo salta para siempre.
    Es lo que dejó 2,540 pares congelados tras la corrida del NameError.
    """
    if not ruta.exists():
        return set()
    hechas = set()
    with ruta.open(encoding="utf-8") as fh:
        for linea in fh:
            linea = linea.strip()
            if not linea:
                continue
            try:
                r = json.loads(linea)
                hechas.add((str(r["tweet_id"]), r["slug"]))
            except Exception:
                continue   # línea truncada por una interrupción
    return hechas


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


def motivo_fallo(exc: Exception) -> str:
    """DEFECTO TRASLADADO (tarea 8.1): no distingue lo permanente de lo
    transitorio. Un NameError cae en 'ERROR', igual que un fallo de red, y se
    reintenta cinco veces con retroceso exponencial algo que jamás va a
    resolverse."""
    t = str(exc).lower()
    if any(k in t for k in ("safety", "blocked", "prohibited", "recitation")):
        return "BLOQUEADO"     # filtro de contenido: NO es nivel bajo ni no-aplicable
    if any(k in t for k in ("429", "rate limit", "resource_exhausted", "quota")):
        return "LIMITE_TASA"
    if any(k in t for k in ("500", "502", "503", "504", "unavailable", "internal")):
        return "ERROR_SERVIDOR"
    return "ERROR"


# ──────────────────────────────────────────────────────────────────────────
#  Corrida
# ──────────────────────────────────────────────────────────────────────────

async def _evaluar_fila(cfg: Config, validador: Validador, runner, fila,
                        pendientes: list[str], sem) -> list[dict]:
    tweet_id = str(fila[cfg.col_id])
    async with sem:
        ultimo = None
        for intento in range(1, cfg.max_intentos + 1):
            try:
                claves = [f"cal_{s}" for s in pendientes]
                estado = await evaluar_payload(runner, fila["_payload"], claves)
                salida = []
                for slug in pendientes:
                    k = f"cal_{slug}"
                    if k in estado:
                        reg = validador.validar(slug, estado[k])
                    else:
                        # DEFECTO TRASLADADO (tarea 8.5): el resultado parcial
                        # se materializa y se RETORNA. Al no lanzar excepción,
                        # el bucle de reintentos de arriba nunca se activa y el
                        # hueco se escribe como definitivo.
                        reg = {"slug": slug, "aplicable": False, "nivel": None,
                               "puntaje": None, "justificacion": "",
                               "estado": "SIN_RESPUESTA",
                               "detalle": "el agente no devolvió estado"}
                    reg["tweet_id"] = tweet_id
                    reg["contexto_incompleto"] = fila["contexto_incompleto"]
                    salida.append(reg)
                return salida
            except Exception as exc:
                ultimo = exc
                motivo = motivo_fallo(exc)
                if motivo == "BLOQUEADO" or intento == cfg.max_intentos:
                    break
                await asyncio.sleep(min(2 ** intento, 30))   # retroceso exponencial

        motivo = motivo_fallo(ultimo)
        return [{"tweet_id": tweet_id, "slug": slug, "aplicable": False, "nivel": None,
                 "puntaje": None, "justificacion": "", "estado": motivo,
                 "detalle": str(ultimo)[:300],
                 "contexto_incompleto": fila["contexto_incompleto"]}
                for slug in pendientes]


async def correr(cfg: Config, sub: pd.DataFrame, criterios: list[dict],
                 ruta: Path | None = None, equipo=None, escribir=print) -> dict:
    """`equipo` permite correr con un ParallelAgent distinto (p.ej. otro modelo
    en la calibración) sin mutar el equipo de producción."""
    ruta = ruta or cfg.checkpoint
    n_criterios = len(criterios)
    validador = Validador(criterios)
    if equipo is None:
        equipo, _ = construir_equipo(cfg, criterios)
        verificar_aislamiento(equipo, criterios)

    hechas = claves_completadas(ruta)
    todos_slugs = [c["slug"] for c in criterios]

    trabajo = []
    for _, fila in sub.iterrows():
        tid = str(fila[cfg.col_id])
        pend = [s for s in todos_slugs if (tid, s) not in hechas]
        if pend:
            trabajo.append((fila, pend))

    total_pendiente = sum(len(p) for _, p in trabajo)
    reusados = len(sub) * n_criterios - total_pendiente
    escribir(f"Checkpoint '{ruta.name}': {reusados:,} resultados reutilizados")
    escribir(f"Pendientes: {total_pendiente:,} llamadas en {len(trabajo):,} filas")

    if not trabajo:
        escribir("✅ Nada pendiente: el checkpoint ya cubre todo el subconjunto.")
        return {"ok": 0, "fallidas": 0, "reusados": reusados}

    # DEFECTO TRASLADADO (tarea 8.7): el semáforo cuenta FILAS. Cada fila
    # abanica un agente por criterio, así que las peticiones en vuelo son
    # concurrencia × n_criterios — con 4 criterios, 8 filas son 32 peticiones
    # simultáneas y nada lo declara.
    sem = asyncio.Semaphore(cfg.concurrencia)
    ok = fallidas = 0
    t0 = time.time()

    with Escritor() as escritor:
        # Reciclado del runner por bloques: evita acumular sesiones en corridas largas
        for ini in range(0, len(trabajo), cfg.reciclar_cada):
            bloque = trabajo[ini:ini + cfg.reciclar_cada]
            runner = InMemoryRunner(agent=equipo, app_name=f"run_{ini}")

            tareas = [_evaluar_fila(cfg, validador, runner, f, p, sem) for f, p in bloque]
            for fut in asyncio.as_completed(tareas):
                registros = await fut
                escritor.anexar(registros, ruta)
                ok += sum(r["estado"] in ("OK", "NO_APLICABLE") for r in registros)
                fallidas += sum(r["estado"] not in ("OK", "NO_APLICABLE") for r in registros)

                hechas_n = ok + fallidas
                if hechas_n % 50 == 0 or hechas_n == total_pendiente:
                    tasa = hechas_n / max(time.time() - t0, 1e-9)
                    rest = (total_pendiente - hechas_n) / max(tasa, 1e-9)
                    escribir(f"  {hechas_n:,} listas · {fallidas:,} fallidas · "
                             f"{tasa:.1f}/s · faltan ~{rest / 60:.0f} min")

            del runner   # libera las sesiones del bloque

    escribir(f"\n✅ Corrida terminada en {(time.time() - t0) / 60:.1f} min")
    escribir(f"   {ok:,} calificaciones · {fallidas:,} fallidas · {reusados:,} reutilizadas")
    if fallidas:
        escribir("   ⚠️  revisa los estados != OK para ver los motivos")
    return {"ok": ok, "fallidas": fallidas, "reusados": reusados}


def cargar_resultados(ruta: Path) -> pd.DataFrame:
    """Si una fila se reevaluó, gana la última escrita.

    DEFECTO TRASLADADO (tarea 9.4): debería ganar el último resultado VÁLIDO,
    no el último a secas. Hoy da igual —verificado: ningún par tuvo un
    resultado bueno pisado por un fallo posterior— pero en cuanto los fallos se
    reintenten la secuencia ERROR → OK se vuelve común y la regla debe ser
    explícita.
    """
    if not ruta.exists():
        raise FileNotFoundError(f"No existe el checkpoint '{ruta}'.")
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
    return df.drop_duplicates(subset=["tweet_id", "slug"], keep="last")
