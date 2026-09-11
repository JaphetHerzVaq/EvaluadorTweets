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
    """Política de reintento del cliente HTTP.

    ADVERTENCIA — traslado literal del cuaderno, defectuoso a propósito:
    ``exp_base=7`` sin ``max_delay`` produce esperas de 1 s → 7 s → 49 s →
    **343 s**. Casi seis minutos de silencio son indistinguibles de un cuelgue,
    y anidados bajo el reintento externo el peor caso por fila ronda los 34
    minutos. Verificado en google-genai 1.66.0: ``max_delay`` por defecto es
    ``None``, es decir sin tope.

    Se conserva así para que el piloto de fidelidad del grupo 7 compare
    traslado contra traslado. La tarea 8.10 lo cambia a base 2 con tope y
    ruido.
    """
    return types.HttpRetryOptions(
        attempts=cfg.max_intentos,
        exp_base=7,
        initial_delay=1,
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
