"""Utilidades compartidas de Google ADK: modelo, configuración y ejecución de agentes.

Traslado de la celda 7 del cuaderno. El cambio de fondo es que los parámetros
llegan por argumento en vez de leerse de variables globales: así un símbolo mal
nombrado revienta al importar y no a las cuatro horas de corrida.
"""

from __future__ import annotations

import uuid

from google.adk.agents import LlmAgent, ParallelAgent          # noqa: F401  (reexportados)
from google.adk.models.google_llm import Gemini
from google.adk.runners import InMemoryRunner
from google.genai import types

from .config import Config


def opciones_reintento(cfg: Config) -> types.HttpRetryOptions:
    """Política de reintento del cliente HTTP: acotada y desincronizada.

    El cuaderno usaba ``exp_base=7`` sin ``max_delay``, lo que produce esperas
    de 1 s → 7 s → 49 s → **343 s**. Verificado en google-genai 1.66.0:
    ``max_delay`` por defecto es ``None``, es decir sin tope. Casi seis minutos
    de silencio son indistinguibles de un cuelgue, y anidados bajo el reintento
    externo el peor caso por fila ronda los 34 minutos.

    Medido en el piloto de fidelidad antes de este cambio: 240 llamadas en
    18.3 min contra ~1 min estimado, con la tasa cayendo de 6.0/s a 0.2/s.

    Base 2 con tope da 1 s → 2 s → 4 s → 8 s, y el ruido evita que las
    llamadas en vuelo reintenten todas en el mismo instante y vuelvan a topar
    el límite a la vez.
    """
    return types.HttpRetryOptions(
        attempts=cfg.max_intentos,
        exp_base=2,
        initial_delay=1,
        max_delay=cfg.retraso_maximo,
        jitter=cfg.ruido_reintento,
        http_status_codes=[429, 500, 502, 503, 504],
    )


def construir_modelo(cfg: Config, modelo: str | None = None) -> Gemini:
    """``retry_options`` SÍ es un campo real de ``Gemini``.

    ``api_key`` / ``vertexai`` / ``project`` NO lo son: se configuran por
    variables de entorno, que es lo que hace
    :func:`evaluador.config.preparar_entorno_modelo`. Verificado en ADK 1.26.
    """
    return Gemini(model=modelo or cfg.modelo, retry_options=opciones_reintento(cfg))


def config_generacion(cfg: Config) -> types.GenerateContentConfig:
    """``temperature`` y ``thinking_config`` van aquí, en
    ``LlmAgent.generate_content_config``. No en el constructor de ``Gemini``,
    que los ignora."""
    return types.GenerateContentConfig(
        temperature=cfg.temperatura,
        thinking_config=types.ThinkingConfig(
            thinking_budget=cfg.presupuesto_razonamiento
        ),
    )


async def ejecutar_agente(runner: InMemoryRunner, partes: list, claves: list[str]) -> dict:
    """Corre el agente del runner con ``partes`` como mensaje y devuelve
    ``{clave_de_estado: valor}`` para las claves pedidas.

    Cada invocación usa una sesión nueva: evita fuga de estado entre filas.
    """
    session_id = f"s_{uuid.uuid4().hex}"
    await runner.session_service.create_session(
        session_id=session_id, user_id="u", app_name=runner.app_name
    )
    recogido: dict = {}
    try:
        async for evento in runner.run_async(
            user_id="u",
            session_id=session_id,
            new_message=types.Content(role="user", parts=partes),
        ):
            delta = getattr(getattr(evento, "actions", None), "state_delta", None)
            if delta:
                for k in claves:
                    if k in delta:
                        recogido[k] = delta[k]
    finally:
        try:
            await runner.session_service.delete_session(
                session_id=session_id, user_id="u", app_name=runner.app_name
            )
        except Exception:
            pass   # no todas las versiones exponen delete_session
    return recogido
