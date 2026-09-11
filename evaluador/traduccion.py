"""Traducción del corpus, reanudable por fila.

Traslado de las celdas 9.5 y 9.6 del cuaderno.

La traducción es para CONSUMO HUMANO: el objeto evaluado sigue siendo el texto
original (regla 5 de la instrucción por criterio). Se paga una sola vez sobre
el corpus completo y se persiste en su propio checkpoint; ninguna corrida de
calificación posterior la vuelve a pagar.
"""

from __future__ import annotations

import asyncio
import json
import random
import re
import threading
from collections import Counter
from pathlib import Path

from google import genai
from google.genai import types
from pydantic import BaseModel, Field

from .config import Config


# ──────────────────────────────────────────────────────────────────────────
#  Esquema e instrucción
# ──────────────────────────────────────────────────────────────────────────

class Traduccion(BaseModel):
    idioma_detectado: str = Field(
        description="El idioma del tweet tal como TÚ lo detectas, en español y en una palabra "
                    "(p.ej. 'inglés', 'japonés', 'español'). Si el texto no tiene contenido "
                    "lingüístico —sólo enlaces, menciones o emojis— responde 'sin texto'."
    )
    ya_esta_en_espanol: bool = Field(
        description="True si el texto YA está escrito en español y no requiere traducción. "
                    "No te fíes de ninguna etiqueta externa: decide por el texto que ves."
    )
    traduccion: str = Field(
        description="La traducción al español. Si ya_esta_en_espanol es True, repite el texto "
                    "original sin cambios."
    )


# El registro del original ES el dato: esta rúbrica mide percepción de un destino.
# Suavizar una grosería o pulir una falta de ortografía destruye justo la señal.
INSTRUCCION_TRADUCCION = (
    "Eres un traductor literal al español. Traduces tweets, uno a la vez.\n\n"
    "REGLAS OBLIGATORIAS:\n"
    "1. LITERAL, NO ADAPTADA. Traduce lo que dice, no lo que debería decir. No resumas, "
    "no expandas, no expliques, no completes lo que falte.\n"
    "2. CONSERVA EL REGISTRO. Si el original es vulgar, ofensivo, irónico o está mal escrito, "
    "la traducción debe serlo igual. NO censures, NO suavices, NO corrijas la ortografía. "
    "El tono del original es parte del dato que se va a analizar.\n"
    "3. NO TRADUZCAS: las menciones (@usuario), las etiquetas (#hashtag), las URL ni los "
    "nombres propios. Van idénticos, carácter por carácter.\n"
    "4. CONSERVA los emojis y los saltos de línea en las posiciones equivalentes.\n"
    "5. SI YA ESTÁ EN ESPAÑOL, marca ya_esta_en_espanol=true y repite el texto sin cambios.\n"
    "6. SI NO HAY NADA QUE TRADUCIR —sólo un enlace, una mención o emojis— devuelve el "
    "contenido tal cual y marca el idioma como 'sin texto'.\n"
    "7. No añadas comentarios, notas del traductor ni comillas envolventes. Sólo la traducción.\n\n"
    "Devuelve tu respuesta conforme al esquema estructurado solicitado."
)


# ──────────────────────────────────────────────────────────────────────────
#  Cliente
# ──────────────────────────────────────────────────────────────────────────

_CLIENTE: genai.Client | None = None
_CANDADO_CLIENTE = threading.Lock()


def _cliente() -> genai.Client:
    """Construcción perezosa, protegida por candado.

    Perezosa porque el cuaderno creaba el cliente al ejecutar la celda, cuando
    la credencial ya estaba en el entorno; en un paquete, hacerlo al importar
    haría que ``import evaluador.traduccion`` falle sin credencial y rompería
    hasta las pruebas que sólo verifican que los módulos importan.

    Con candado porque las llamadas corren en hilos (``asyncio.to_thread``) y
    sin él varios construyen un cliente a la vez: el que pierde la carrera se
    queda sin referencias, el recolector lo cierra, y el hilo que ya lo tenía
    en la mano recibe 'Cannot send a request, as the client has been closed'.
    El cuaderno no tenía este problema porque creaba el cliente una sola vez
    al nivel del módulo, antes de cualquier concurrencia.
    """
    global _CLIENTE
    if _CLIENTE is None:
        with _CANDADO_CLIENTE:
            if _CLIENTE is None:          # otro hilo pudo construirlo mientras esperábamos
                _CLIENTE = genai.Client()
    return _CLIENTE


def _config(cfg: Config) -> types.GenerateContentConfig:
    return types.GenerateContentConfig(
        temperature=cfg.temperatura,
        response_mime_type="application/json",
        response_schema=Traduccion,
        system_instruction=INSTRUCCION_TRADUCCION,
        thinking_config=types.ThinkingConfig(thinking_budget=cfg.presupuesto_razonamiento),
    )


def es_transitorio(exc: Exception) -> bool:
    """429 y 5xx se reintentan; un 400 por esquema o un 403 por permisos, no."""
    codigo = getattr(exc, "code", None) or getattr(exc, "status_code", None)
    if isinstance(codigo, int):
        return codigo == 429 or 500 <= codigo < 600
    t = str(exc)
    return any(s in t for s in ("429", "500", "502", "503", "504",
                                "RESOURCE_EXHAUSTED", "UNAVAILABLE", "DEADLINE"))


_SENAS_CREDENCIAL = (
    "no api key", "api key not valid", "api_key_invalid",
    "permission_denied", "unauthenticated", "invalid authentication",
)


class CredencialInvalida(RuntimeError):
    """La credencial falta o no sirve: es estructural, no un fallo de fila."""


class TiempoAgotado(RuntimeError):
    """La llamada no respondió dentro del límite. Se reintenta: suele ser una
    conexión atascada, no un problema del texto."""


class ContenidoBloqueado(RuntimeError):
    """El filtro de contenido impidió la respuesta. No se reintenta: es una
    decisión del proveedor sobre ese texto, no un fallo pasajero."""


def es_fallo_de_credencial(exc: Exception) -> bool:
    t = str(exc).lower()
    return any(s in t for s in _SENAS_CREDENCIAL)


def _llamar_sync(cfg: Config, texto: str):
    return _cliente().models.generate_content(
        model=cfg.modelo_traduccion,
        contents=f"<tweet>\n{texto}\n</tweet>",
        config=_config(cfg),
    )


async def traducir_uno(cfg: Config, texto: str, intentos: int | None = None) -> dict:
    """Usa el cliente SÍNCRONO dentro de un hilo, no el asíncrono.

    Origen del rodeo: el cliente ``.aio`` de google-genai levanta 'Timeout
    should be used inside a task' bajo ``nest_asyncio``, que el cuaderno
    aplicaba para correr corrutinas en Colab. ``aiohttp`` usa ``ceil_timeout``,
    que exige una tarea real y no sobrevive al bucle reentrante.

    En proceso local ya no hay ``nest_asyncio``, así que el cliente asíncrono
    funcionaría. Se conserva el rodeo de todas formas: son 2,557 traducciones
    exitosas de 2,562 (99.8%) con este camino, y cambiarlo dentro de un
    traslado mezclaría dos fuentes de riesgo. ``asyncio.to_thread`` respeta el
    semáforo y la concurrencia igual.
    """
    intentos = intentos or cfg.max_intentos
    ultimo: Exception | None = None
    for n in range(intentos):
        try:
            # Tiempo límite obligatorio. Sin él, una petición que nunca
            # responde retiene su cupo del semáforo de forma indefinida: se
            # observó una fila colgada más de quince minutos sin lanzar nada.
            # En una corrida de miles de llamadas eso no se ve como un error,
            # se ve como que el proceso "va lento", y termina en una sesión
            # abandonada. asyncio.wait_for cancela la espera; el hilo de
            # to_thread sigue vivo hasta que la petición retorne, pero deja de
            # bloquear la corrida.
            r = await asyncio.wait_for(
                asyncio.to_thread(_llamar_sync, cfg, texto),
                timeout=cfg.timeout_llamada,
            )
            # r.text es None cuando el filtro de contenido bloqueó la respuesta.
            # Sin esta comprobación, json.loads(None) levanta un TypeError cuyo
            # mensaje ('the JSON object must be str, bytes or bytearray, not
            # NoneType') no dice nada del motivo real, y además se reintenta
            # cinco veces algo que nunca va a cambiar.
            if r.text is None:
                motivo = getattr(getattr(r, "prompt_feedback", None), "block_reason", None)
                raise ContenidoBloqueado(
                    f"el modelo no devolvió texto"
                    + (f" (motivo: {motivo})" if motivo else "")
                    + "; suele ser el filtro de contenido"
                )
            return json.loads(r.text)
        except ContenidoBloqueado:
            raise
        except (asyncio.TimeoutError, TimeoutError) as exc:
            ultimo = TiempoAgotado(
                f"la llamada superó {cfg.timeout_llamada} s sin responder"
            )
            if n == intentos - 1:
                break
            await asyncio.sleep(min(2 ** n + random.random(), 30))
            continue
        except json.JSONDecodeError as exc:
            # Respuesta cortada a media cadena. Es transitorio: otro intento
            # suele devolver el objeto completo.
            ultimo = exc
            if n == intentos - 1:
                break
            await asyncio.sleep(min(2 ** n + random.random(), 30))
            continue
        except Exception as exc:
            ultimo = exc
            if not es_transitorio(exc) or n == intentos - 1:
                break
            # espera exponencial con ruido, para no sincronizar los reintentos
            await asyncio.sleep(min(2 ** n + random.random(), 30))
    raise ultimo


# ──────────────────────────────────────────────────────────────────────────
#  Checkpoint propio
# ──────────────────────────────────────────────────────────────────────────
# No toca el checkpoint de calificación, que indexa por (tuit, criterio).

def traducciones_hechas(ruta: Path) -> dict[str, dict]:
    if not ruta.exists():
        return {}
    hechas: dict[str, dict] = {}
    with ruta.open(encoding="utf-8") as fh:
        for linea in fh:
            linea = linea.strip()
            if not linea:
                continue
            try:
                r = json.loads(linea)
                hechas[str(r["tweet_id"])] = r
            except Exception:
                continue          # línea truncada por una interrupción
    return hechas


def _anexar(registro: dict, ruta: Path) -> None:
    if ruta.exists() and ruta.stat().st_size:
        with ruta.open("rb") as prev:          # si una corrida murió a media línea,
            prev.seek(-1, 2)                   # el archivo no termina en \n y el
            cortada = prev.read(1) != b"\n"    # registro nuevo se concatenaría
        if cortada:
            with ruta.open("a", encoding="utf-8") as fh:
                fh.write("\n")
    with ruta.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(registro, ensure_ascii=False) + "\n")
        fh.flush()


def estimar_costo(cfg: Config, n: int) -> float:
    if cfg.modelo_traduccion not in cfg.precios:
        return 0.0
    p_in, p_out = cfg.precio_de(cfg.modelo_traduccion)
    tok_in = len(INSTRUCCION_TRADUCCION) // 4 + 110    # instrucción + tweet medio
    tok_out = 130                                      # traducción + envoltura del esquema
    return n * (tok_in / 1e6 * p_in + tok_out / 1e6 * p_out)


# ──────────────────────────────────────────────────────────────────────────
#  Corrida
# ──────────────────────────────────────────────────────────────────────────

async def traducir_corpus(cfg: Config, df, ruta_ckpt: Path | None = None,
                          escribir=print) -> tuple:
    ruta_ckpt = ruta_ckpt or cfg.checkpoint_traduccion

    if cfg.col_traduccion not in df.columns:
        df[cfg.col_traduccion] = ""
        escribir(f"   columna '{cfg.col_traduccion}' creada")

    col = df[cfg.col_traduccion].fillna("").astype(str).str.strip()
    con_texto = df[cfg.col_texto].fillna("").astype(str).str.strip() != ""
    if cfg.retraducir_existentes:
        objetivo = df.index[con_texto]
        escribir("   retraducir_existentes=true: se reescriben todas las traducciones")
    else:
        objetivo = df.index[con_texto & (col == "")]

    hechas = traducciones_hechas(ruta_ckpt)
    # Sólo las OK cuentan como hechas: una fila que falló por un 429 pasajero
    # debe reintentarse en la siguiente corrida, no quedar envenenada para siempre.
    ok = {k for k, v in hechas.items() if v.get("estado") == "OK"}
    pendientes = [i for i in objetivo if str(df.at[i, cfg.col_id]) not in ok]
    reintentos = sum(1 for i in pendientes if str(df.at[i, cfg.col_id]) in hechas)

    escribir(f"\nfilas con texto            {con_texto.sum():>7,}")
    escribir(f"ya traducidas en el corpus {len(df) - len(objetivo) - (~con_texto).sum():>7,}")
    escribir(f"recuperadas del checkpoint {len(objetivo) - len(pendientes):>7,}")
    escribir(f"pendientes de traducir     {len(pendientes):>7,}")
    if reintentos:
        escribir(f"   de ellas, {reintentos:,} fallaron en una corrida previa y se reintentan")
    if pendientes:
        escribir(f"costo estimado             ${estimar_costo(cfg, len(pendientes)):.2f} USD "
                 f"· modelo {cfg.modelo_traduccion}")

    fallidas: list[str] = []
    if pendientes:
        sem = asyncio.Semaphore(cfg.concurrencia_traduccion)
        hecho = 0

        async def una(i):
            nonlocal hecho
            tid = str(df.at[i, cfg.col_id])
            async with sem:
                try:
                    r = await traducir_uno(cfg, str(df.at[i, cfg.col_texto]))
                    reg = {"tweet_id": tid,
                           "idioma_detectado": r.get("idioma_detectado", ""),
                           "ya_esta_en_espanol": bool(r.get("ya_esta_en_espanol")),
                           "traduccion": (r.get("traduccion") or "").strip(),
                           "estado": "OK"}
                except Exception as exc:
                    # Un fallo de credencial afecta a TODAS las filas por igual.
                    # Registrarlo como fallo de fila escribiría un registro basura
                    # por cada tuit pendiente y los dejaría marcados como
                    # intentados. Es la misma forma del NameError que arruinó la
                    # corrida de calificación: estructural disfrazado de dato.
                    if es_fallo_de_credencial(exc):
                        raise CredencialInvalida(
                            f"La credencial falta o no sirve, así que ninguna fila se "
                            f"puede traducir y no se escribe nada al checkpoint.\n"
                            f"  Detalle: {exc}\n"
                            f"  Llama a preparar_entorno_modelo(cfg) antes de traducir."
                        ) from exc
                    estado = "BLOQUEADA" if isinstance(exc, ContenidoBloqueado) else "FALLIDA"
                    reg = {"tweet_id": tid, "idioma_detectado": "", "ya_esta_en_espanol": False,
                           "traduccion": "", "estado": estado, "detalle": str(exc)[:200]}
                    fallidas.append(tid)
                _anexar(reg, ruta_ckpt)
                hechas[tid] = reg
                hecho += 1
                if hecho % 100 == 0 or hecho == len(pendientes):
                    escribir(f"   {hecho:,}/{len(pendientes):,} "
                             f"({hecho / len(pendientes):.0%}) · fallidas {len(fallidas):,}")

        await asyncio.gather(*(una(i) for i in pendientes))

    # ── Volcado al DataFrame ─────────────────────────────────────────────
    # El español se copia VERBATIM desde el corpus, no desde lo que devolvió el
    # modelo: así la copia es exacta por construcción y no depende de que no
    # haya alterado nada.
    n_trad = n_copia = 0
    for i in objetivo:
        reg = hechas.get(str(df.at[i, cfg.col_id]))
        if not reg or reg.get("estado") != "OK":
            continue
        if reg.get("ya_esta_en_espanol"):
            df.at[i, cfg.col_traduccion] = str(df.at[i, cfg.col_texto])
            n_copia += 1
        else:
            df.at[i, cfg.col_traduccion] = reg["traduccion"]
            n_trad += 1

    llenas = (df[cfg.col_traduccion].fillna("").astype(str).str.strip() != "").sum()
    escribir(f"\n{'=' * 66}\nTRADUCCIÓN\n{'=' * 66}")
    escribir(f"  traducidas por el modelo    {n_trad:>7,}")
    escribir(f"  copiadas verbatim (español) {n_copia:>7,}")
    escribir(f"  fallidas                    {len(fallidas):>7,}")
    escribir(f"  columna '{cfg.col_traduccion}' llena en {llenas:,}/{len(df):,} filas")
    return df, fallidas


# ──────────────────────────────────────────────────────────────────────────
#  Verificaciones
# ──────────────────────────────────────────────────────────────────────────

_TOKENS = re.compile(r"https?://\S+|[@#]\w+")


def verificar_tokens(cfg: Config, df, n: int = 60, escribir=print) -> list:
    """Los @handles, #hashtags y URL deben sobrevivir idénticos. Comprobación
    determinista y barata sobre una muestra."""
    m = df[df[cfg.col_traduccion].fillna("").astype(str).str.strip() != ""]
    if m.empty:
        return []
    m = m.sample(n=min(n, len(m)), random_state=cfg.semilla)
    malas = []
    for _, f in m.iterrows():
        o = set(_TOKENS.findall(str(f[cfg.col_texto])))
        t = set(_TOKENS.findall(str(f[cfg.col_traduccion])))
        if o - t:
            malas.append((str(f[cfg.col_id]), sorted(o - t)[:3]))
    escribir(f"\n  tokens preservados: {len(m) - len(malas)}/{len(m)} de la muestra")
    for tid, faltan in malas[:5]:
        escribir(f"     ⚠️  {tid}: faltan {faltan}")
    return malas


ALIAS_IDIOMA = {
    "en": "inglés", "ja": "japonés", "es": "español", "pt": "portugués",
    "fr": "francés", "de": "alemán", "it": "italiano", "ko": "coreano",
    "nl": "neerlandés", "tl": "tagalo", "ht": "criollo haitiano", "th": "tailandés",
}
SIN_IDIOMA = {"qme", "und", "zxx", "qam", "qht", "qst", "art", ""}


def contrastar_idioma(cfg: Config, df, ruta_ckpt: Path | None = None, escribir=print) -> None:
    """La columna 'lang' viene de la API y miente: declara 64 'qme', 21 'und' y
    8 'zxx', que no son idiomas. Contrastarla contra lo que detectó el modelo
    dice cuánto, y es gratis porque el dato ya viaja en el esquema de respuesta."""
    hechas = traducciones_hechas(ruta_ckpt or cfg.checkpoint_traduccion)
    if not hechas:
        return
    filas = []
    for _, f in df.iterrows():
        r = hechas.get(str(f[cfg.col_id]))
        if not r or r.get("estado") != "OK":
            continue
        lang = str(f.get(cfg.col_lang, "") or "").strip().lower()
        det = str(r.get("idioma_detectado", "")).strip().lower()
        filas.append((lang, det))
    if not filas:
        return

    reales = [(l, d) for l, d in filas if l not in SIN_IDIOMA]
    de_acuerdo = sum(1 for l, d in reales if ALIAS_IDIOMA.get(l, l) == d)
    escribir(f"\n{'=' * 66}\nCONTRASTE 'lang' vs idioma detectado\n{'=' * 66}")
    if reales:
        escribir(f"  filas con 'lang' que sí es un idioma: {len(reales):,}")
        escribir(f"  coinciden: {de_acuerdo:,} ({de_acuerdo / len(reales):.1%}) · "
                 f"desacuerdo: {len(reales) - de_acuerdo:,}")

    sin = [(l, d) for l, d in filas if l in SIN_IDIOMA]
    if sin:
        escribir(f"\n  filas cuyo 'lang' NO es un idioma: {len(sin):,}")
        for cod in sorted({l for l, _ in sin}):
            c = Counter(d for l, d in sin if l == cod)
            top = ", ".join(f"{k}:{v}" for k, v in c.most_common(4))
            escribir(f"     '{cod or '(vacío)'}' ({sum(c.values())}) → {top}")

    desac = Counter((l, d) for l, d in reales if ALIAS_IDIOMA.get(l, l) != d)
    if desac:
        escribir("\n  desacuerdos más frecuentes:")
        for (l, d), n in desac.most_common(5):
            escribir(f"     lang='{l}' pero el modelo detectó '{d}'  ({n})")
