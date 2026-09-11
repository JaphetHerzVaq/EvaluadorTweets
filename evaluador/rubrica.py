"""Ingesta del PDF de rúbrica y normalización a rubrica.json.

Traslado de las celdas 5, 6 y 8 del cuaderno. El esquema es agnóstico al
número de criterios y al tipo de escala: N se deriva de la rúbrica en tiempo
de ejecución y nunca aparece fijo en el código.
"""

from __future__ import annotations

import asyncio
import json
import re
import unicodedata
from pathlib import Path

from google.adk.runners import InMemoryRunner
from google.genai import types
from pydantic import BaseModel, Field

from .adk import LlmAgent, config_generacion, construir_modelo, ejecutar_agente
from .config import Config, exigir_insumo


# ──────────────────────────────────────────────────────────────────────────
#  Esquema · agnóstico a N y al tipo de escala
# ──────────────────────────────────────────────────────────────────────────

class Nivel(BaseModel):
    etiqueta: str = Field(
        description="Nombre del nivel tal como aparece en la rúbrica, p.ej. 'Experto', 'Logrado', '0.6 pts'")
    puntos: float | None = Field(
        default=None,
        description="Valor numérico del nivel si la rúbrica lo define; null si la escala es nominal")
    descriptor: str = Field(
        description="Descripción completa y literal del nivel, sin resumir. Es el texto contra el que se califica.")


class Criterio(BaseModel):
    id_criterio: str = Field(
        description="Identificador corto tal como aparece en la rúbrica, p.ej. 'Q1', 'D3', 'C2'. Si no hay, usa un ordinal: '1', '2'.")
    nombre: str = Field(description="Nombre o título del criterio")
    consigna: str = Field(description="La pregunta o consigna de evaluación completa del criterio")
    niveles: list[Nivel] = Field(description="Niveles de logro, ordenados del más bajo al más alto")


class Rubrica(BaseModel):
    criterios: list[Criterio]


INSTRUCCION_PARSER = (
    "Eres un extractor de rúbricas de evaluación. Recibes el PDF de una rúbrica.\n"
    "Tu tarea es transcribir su estructura EXACTA a datos, sin interpretarla ni mejorarla.\n\n"
    "REGLAS OBLIGATORIAS:\n"
    "1. Extrae TODOS los criterios que contenga el documento. No omitas ninguno.\n"
    "2. Transcribe el descriptor de cada nivel COMPLETO y LITERAL. No resumas, no parafrasees, "
    "no acortes. Ese texto es la vara con la que se calificará después.\n"
    "3. Ordena los niveles del MÁS BAJO al MÁS ALTO de logro.\n"
    "4. Si la rúbrica asigna valores numéricos a los niveles, ponlos en 'puntos'. "
    "Si los niveles son sólo nominales (por ejemplo 'Logrado', 'En proceso', 'Inicial'), "
    "deja 'puntos' en null. NO inventes valores numéricos que la rúbrica no declara.\n"
    "5. Usa como 'id_criterio' el identificador que aparezca en el documento "
    "(Q1, D3, C2, Criterio 4...). Si no hay ninguno, usa un ordinal.\n"
    "6. NO inventes criterios ni niveles que no estén en el PDF.\n"
    "7. Conserva el idioma original del documento."
)


# ──────────────────────────────────────────────────────────────────────────
#  Normalización
# ──────────────────────────────────────────────────────────────────────────

def _slug(texto: str, maxlen: int = 28) -> str:
    t = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    t = re.sub(r"[^a-zA-Z0-9]+", "_", t).strip("_").lower()
    return t[:maxlen].rstrip("_") or "crit"


def asignar_slugs(rubrica: dict, avisar=print) -> dict:
    """Identificadores únicos, estables y aptos para nombres de columna.

    El slug es la llave con la que el checkpoint empareja resultados, así que
    cambiarlo invalida un checkpoint existente. Depende de 'id_criterio' y
    'nombre': editarlos a mano en rubrica.json rompe la correspondencia.
    """
    vistos: dict[str, int] = {}
    for i, c in enumerate(rubrica["criterios"], start=1):
        base = _slug(f"{c.get('id_criterio') or i}_{c.get('nombre') or ''}")
        slug = base
        if base in vistos:
            vistos[base] += 1
            slug = f"{base}_{vistos[base]}"
            avisar(f"   ⚠️  colisión de identificador '{base}' → desambiguado como '{slug}'")
        else:
            vistos[base] = 1
        c["slug"] = slug
    return rubrica


def anotar_escala(rubrica: dict) -> dict:
    for c in rubrica["criterios"]:
        puntos = [n.get("puntos") for n in c["niveles"]]
        numerica = len(puntos) > 0 and all(p is not None for p in puntos)
        c["escala_numerica"] = bool(numerica)
        c["etiquetas_validas"] = [n["etiqueta"] for n in c["niveles"]]
        c["puntos_validos"] = [p for p in puntos if p is not None] if numerica else []
    return rubrica


# ──────────────────────────────────────────────────────────────────────────
#  Parseo
# ──────────────────────────────────────────────────────────────────────────

async def parsear_pdf(cfg: Config, pdf_bytes: bytes) -> dict:
    agente = LlmAgent(
        name="RubricParserAgent",
        model=construir_modelo(cfg),
        instruction=INSTRUCCION_PARSER,
        output_schema=Rubrica,
        output_key="rubrica",
        generate_content_config=config_generacion(cfg),
        disallow_transfer_to_parent=True,
        disallow_transfer_to_peers=True,
    )
    runner = InMemoryRunner(agent=agente, app_name="rubric_parser")
    partes = [
        types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf"),
        types.Part(text="Extrae la estructura completa de esta rúbrica."),
    ]
    estado = await ejecutar_agente(runner, partes, ["rubrica"])
    if "rubrica" not in estado:
        raise RuntimeError(
            "El parseo no devolvió ninguna rúbrica. Gemini lee el PDF de forma "
            "nativa y tolera documentos escaneados, así que un fallo aquí suele "
            "ser de credencial, de cuota o de contenido bloqueado, no de formato."
        )
    return estado["rubrica"]


def resumen(rubrica: dict, destino: Path, escribir=print) -> None:
    crits = rubrica["criterios"]
    n_num = sum(c["escala_numerica"] for c in crits)
    escribir(f"\n{'=' * 72}")
    escribir(f"RÚBRICA · {len(crits)} criterios detectados")
    escribir(f"Escala: {n_num} numéricos · {len(crits) - n_num} nominales")
    escribir(f"{'=' * 72}")
    for c in crits:
        tipo = "numérica" if c["escala_numerica"] else "nominal"
        esc = c["puntos_validos"] if c["escala_numerica"] else c["etiquetas_validas"]
        escribir(f"\n[{c['id_criterio']}] {c['nombre']}   ({c['slug']})")
        corte = "…" if len(c["consigna"]) > 100 else ""
        escribir(f"    consigna : {c['consigna'][:100]}{corte}")
        escribir(f"    niveles  : {len(c['niveles'])} · escala {tipo} · {esc}")
        cortos = [n["etiqueta"] for n in c["niveles"] if len(n.get("descriptor", "")) < 25]
        if cortos:
            escribir(f"    ⚠️  descriptores muy cortos en {cortos} — ¿se truncaron al parsear?")
    escribir(f"\n{'=' * 72}")
    escribir(f"👁  REVISA '{destino}' ANTES DE CORRER. Puedes editarlo a mano y volver")
    escribir(f"    a cargarlo: se recarga del archivo sin llamar al modelo.")
    escribir(f"{'=' * 72}\n")


def cargar(cfg: Config, forzar_reparseo: bool = False, escribir=print) -> dict:
    """Devuelve la rúbrica normalizada, del JSON si existe o parseando el PDF.

    El PDF es la fuente de verdad; ``rubrica.json`` es el artefacto revisable
    que se produce de él y que un humano puede corregir a mano antes de gastar.
    """
    ruta = cfg.rubrica_json
    if ruta.exists() and not forzar_reparseo:
        rubrica = json.loads(ruta.read_text(encoding="utf-8"))
        escribir(f"♻️  Rúbrica recargada de '{ruta}' (sin llamar al modelo).")
    else:
        pdf = exigir_insumo(cfg.rubrica_pdf, "el PDF de la rúbrica",
                            "ninguna: es una entrada del proyecto")
        escribir(f"Parseando '{pdf.name}' con {cfg.modelo}…")
        rubrica = asyncio.run(parsear_pdf(cfg, pdf.read_bytes()))
        rubrica = anotar_escala(asignar_slugs(rubrica, escribir))
        ruta.write_text(json.dumps(rubrica, ensure_ascii=False, indent=2), encoding="utf-8")
        escribir(f"✅ Escrito '{ruta}'")

    if not rubrica.get("criterios"):
        raise RuntimeError(f"'{ruta}' no contiene criterios. No se puede continuar.")

    # Reanotar siempre: permite editar el JSON a mano sin recalcular estos campos
    rubrica = anotar_escala(asignar_slugs(rubrica, escribir))
    resumen(rubrica, ruta, escribir)
    return rubrica


def criterios(rubrica: dict) -> list[dict]:
    return rubrica["criterios"]
