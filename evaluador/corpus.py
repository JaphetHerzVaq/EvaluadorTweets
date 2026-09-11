"""Reparación, carga, selección y construcción del payload de evaluación.

Traslado de las celdas 8.5, 9, 10 y 11 del cuaderno.

La reparación existe porque el .xlsx de origen llega dañado en cuatro frentes:
mojibake (UTF-8 leído como cp1252), identificadores de 19 dígitos redondeados
por float64, 99 textos truncados a 255 caracteres y 458 con los saltos de
línea colapsados. ``raw_json`` sobrevivió íntegro y es la fuente de verdad.
"""

from __future__ import annotations

import codecs
import json
import re
from pathlib import Path

import pandas as pd

from .config import Config, exigir_insumo

# dtype=str preserva los identificadores de 19 dígitos intactos; la cadena
# vacía es el único NA. Sin esto, pandas los pasa por float64 y los redondea:
# es exactamente el daño que esta etapa existe para reparar.
LECTURA = dict(dtype=str, keep_default_na=False, na_values=[""])


# ──────────────────────────────────────────────────────────────────────────
#  Reparación del mojibake
# ──────────────────────────────────────────────────────────────────────────

# Mapa inverso de cp1252, completado con latin-1 en los huecos.
# El daño es UTF-8 leído como cp1252. Revertirlo con .encode("cp1252") falla:
# cp1252 no define 0x81, 0x8D, 0x8F, 0x90 ni 0x9D, y el decodificador original
# dejó pasar esos bytes crudos, así que el texto mezcla caracteres cp1252
# legítimos (€ ™ œ …, todos > U+00FF) con puntos de código del rango C1.
_INV_CP1252: dict[str, int] = {}
for _b in range(256):
    _ch = codecs.decode(bytes([_b]), "cp1252", errors="replace")
    if _ch != "�":
        _INV_CP1252.setdefault(_ch, _b)
for _b in range(256):
    _INV_CP1252.setdefault(chr(_b), _b)      # respaldo latin-1 para el rango C1


def reparar_texto(s: str) -> tuple[str, bool]:
    """Revierte el mojibake. Devuelve ``(texto, se_reparó)``.

    Conserva el crudo en dos casos: cuando el texto ya está sano —trae algún
    carácter que ningún mojibake de cp1252 pudo producir— y cuando los bytes
    no decodifican como UTF-8, que es lo que pasa con un texto cortado a media
    secuencia multibyte.
    """
    if not s or all(ord(c) < 128 for c in s):
        return s, False                      # ASCII puro: nada que revertir
    crudos = bytearray()
    for c in s:
        b = _INV_CP1252.get(c)
        if b is None:
            return s, False                  # carácter ajeno a cp1252: ya está sano
        crudos.append(b)
    try:
        return crudos.decode("utf-8"), True
    except UnicodeDecodeError:
        return s, False                      # irreparable: se conserva el crudo


def _rep(s: str) -> str:
    return reparar_texto(s)[0]


# ──────────────────────────────────────────────────────────────────────────
#  Lectura de la fuente
# ──────────────────────────────────────────────────────────────────────────

def _leer_fuente(ruta: Path) -> pd.DataFrame:
    if ruta.suffix.lower() == ".csv":
        raise RuntimeError(
            f"'{ruta.name}' es CSV y esta reparación necesita el .xlsx.\n"
            "El CSV de este corpus sufrió una segunda ronda de daño que sustituyó "
            "por '?' los caracteres no representables, incluido dentro de su propio "
            "'raw_json' (1,241 filas). Esa pérdida es irreversible: no hay de dónde "
            "recuperar esos bytes.\n"
            "Los dos archivos son la misma exportación fila por fila, así que el CSV "
            "bueno se REGENERA desde el .xlsx. Apunta corpus_fuente_xlsx al .xlsx."
        )
    if ruta.suffix.lower() not in (".xlsx", ".xlsm", ".xls"):
        raise ValueError(f"Se esperaba un Excel. Recibido: '{ruta.suffix or ruta.name}'")

    exigir_insumo(ruta, "el Excel de origen del corpus",
                  "ninguna: es una entrada del proyecto")

    hojas = pd.ExcelFile(ruta).sheet_names
    df = pd.read_excel(ruta, sheet_name=hojas[0], dtype=str, keep_default_na=False)
    if "raw_json" not in df.columns:
        raise RuntimeError(
            "El archivo no trae la columna 'raw_json'. Sin ella no hay nada que "
            "reconstruir: las columnas planas están dañadas de forma irreversible."
        )
    return df


_FIRMA_SUSTITUCION = re.compile(r"[-ÿ]\?|\?[-ÿ]")
_UMBRAL_SUSTITUCION = 0.20


def verificar_perdida_irreversible(serie, escribir=print) -> None:
    """Firma de la sustitución destructiva: un '?' pegado a un carácter de la
    banda 0x80-0xFF. En texto sano el '?' es puntuación y va rodeado de ASCII;
    en el archivo destruido quedó intercalado con los bytes altos del mojibake.
    Medido sobre este corpus: 0.5% de las filas en el .xlsx contra 75.6% en el
    .csv, así que un umbral de proporción separa los dos casos con holgura."""
    n = sum(1 for v in serie if _FIRMA_SUSTITUCION.search(v))
    prop = n / max(len(serie), 1)
    if prop >= _UMBRAL_SUSTITUCION:
        raise RuntimeError(
            f"{n:,} de {len(serie):,} filas ({prop:.1%}) tienen 'raw_json' con la firma "
            "de sustitución por '?' — pérdida irreversible. Este archivo no se puede "
            "reparar; usa el .xlsx original."
        )
    if n:
        escribir(f"   ({n} filas con '?' junto a caracteres altos — dentro de lo esperado)")


# ──────────────────────────────────────────────────────────────────────────
#  Reconstrucción de una fila desde su raw_json
# ──────────────────────────────────────────────────────────────────────────

_PROCEDENCIA = ["base", "query_utilizado", "corpus_type",
                "window_label", "is_retweet", "is_quote"]
_SIEMPRE_VACIAS = ["origen", "source", "withheld", "tipo", "justificacion"]


def _js(v, vacio: str = "") -> str:
    return vacio if v is None else json.dumps(v, ensure_ascii=False, separators=(",", ":"))


def _ts(v) -> str:
    return str(v or "").replace(".000Z", "")   # el formato plano no lleva fracción ni zona


def _s(v) -> str:
    return "" if v is None else str(v)


def fila_desde_json(d: dict, plana) -> dict:
    a = d.get("_author") or {}
    am = a.get("public_metrics") or {}
    pm = d.get("public_metrics") or {}
    p = d.get("_place") or {}
    texto = _rep(_s(d.get("text")))
    fila = {
        "id":                   _s(d.get("id")),
        "author_id":            _s(d.get("author_id")),
        "created_at":           _ts(d.get("created_at")),
        "lang":                 _s(d.get("lang")),
        "text":                 texto,
        "text_completo":        texto,          # en este corpus son la misma cosa
        "conversation_id":      _s(d.get("conversation_id")),
        "in_reply_to_user_id":  _s(d.get("in_reply_to_user_id")),
        "possibly_sensitive":   _s(d.get("possibly_sensitive")),
        "reply_settings":       _s(d.get("reply_settings")),
        "like_count":           _s(pm.get("like_count")),
        "retweet_count":        _s(pm.get("retweet_count")),
        "reply_count":          _s(pm.get("reply_count")),
        "quote_count":          _s(pm.get("quote_count")),
        "impression_count":     _s(pm.get("impression_count")),
        "bookmark_count":       _s(pm.get("bookmark_count")),
        "referenced_tweets":    _rep(_js(d.get("referenced_tweets"), "[]")),
        "context_annotations":  _rep(_js(d.get("context_annotations"), "[]")),
        "entities":             _rep(_js(d.get("entities"))),
        "geo":                  _rep(_js(d.get("geo"))),
        "author_username":          _rep(_s(a.get("username"))),
        "author_name":              _rep(_s(a.get("name"))),
        "author_location":          _rep(_s(a.get("location"))),
        "author_description":       _rep(_s(a.get("description"))),
        "author_created_at":        _ts(a.get("created_at")),
        "author_verified":          _s(a.get("verified")),
        "author_url":               _s(a.get("url")),
        "author_profile_image_url": _s(a.get("profile_image_url")),
        "author_followers_count":   _s(am.get("followers_count")),
        "author_following_count":   _s(am.get("following_count")),
        "author_tweet_count":       _s(am.get("tweet_count")),
        "author_listed_count":      _s(am.get("listed_count")),
        "place_full_name":          _rep(_s(p.get("full_name"))),
        "place_country":            _rep(_s(p.get("country"))),
        "place_country_code":       _s(p.get("country_code")),
        "place_type":               _s(p.get("place_type")),
        "place_geo":                _js(p.get("geo")),
        "place_contained_within":   _js(p.get("contained_within")),
    }
    for c in _PROCEDENCIA:                     # no viajan en el JSON y están intactas
        fila[c] = plana.get(c, "")
    for c in _SIEMPRE_VACIAS:                  # vacías en las 2,562 filas
        fila[c] = plana.get(c, "")
    return fila


# ──────────────────────────────────────────────────────────────────────────
#  Reparación completa
# ──────────────────────────────────────────────────────────────────────────

def reparar(cfg: Config, forzar: bool | None = None, escribir=print) -> pd.DataFrame:
    destino = cfg.corpus_reparado
    forzar = cfg.forzar_reparacion if forzar is None else forzar

    # Si el corpus ya viajó reparado (o reparado y traducido), no hace falta el
    # .xlsx de origen.
    if not forzar:
        for ya in (cfg.corpus_traducido, destino):
            if ya and ya.exists():
                previo = pd.read_csv(ya, low_memory=False, encoding="utf-8-sig", **LECTURA)
                escribir(f"↩️  '{ya.name}' ya está en disco con {len(previo):,} filas — "
                         f"se omite la reparación (no se necesita el .xlsx).")
                escribir("   Pon forzar_reparacion = true para rehacerla desde el origen.")
                return previo

    bruto = _leer_fuente(cfg.corpus_fuente_xlsx)
    escribir(f"✅ Fuente: {cfg.corpus_fuente_xlsx.name} — "
             f"{len(bruto):,} filas × {len(bruto.columns)} columnas")

    if destino.exists() and not forzar:
        previo = pd.read_csv(destino, low_memory=False, encoding="utf-8-sig", **LECTURA)
        if len(previo) == len(bruto):
            escribir(f"↩️  '{destino.name}' ya existe con {len(previo):,} filas — se omite.")
            return previo
        escribir(f"⚠️  '{destino.name}' existe con {len(previo):,} filas y la fuente tiene "
                 f"{len(bruto):,} — se rehace.")

    verificar_perdida_irreversible(bruto["raw_json"], escribir)

    # Parseo previo: si algo no parsea, se aborta sin escribir nada
    docs_crudos = []
    for i, v in enumerate(bruto["raw_json"]):
        try:
            d = json.loads(v)
        except Exception as exc:
            raise RuntimeError(f"Fila {i}: 'raw_json' no parsea como JSON — {exc}") from exc
        if not d.get("id"):
            raise RuntimeError(f"Fila {i}: 'raw_json' no declara 'id'. No se emite archivo parcial.")
        docs_crudos.append(d)

    # Reparar el propio raw_json: deja el archivo de salida uniformemente sano
    # y hace idempotente una segunda pasada sobre el archivo ya reparado.
    sanos = [reparar_texto(v)[0] for v in bruto["raw_json"]]
    docs = [json.loads(c) for c in sanos]

    filas = [fila_desde_json(docs[i], bruto.iloc[i]) for i in range(len(bruto))]
    rep = pd.DataFrame(filas)
    rep["raw_json"] = sanos
    rep = rep.reindex(columns=list(bruto.columns))    # mismo orden que la fuente

    # ── Reporte ──────────────────────────────────────────────────────────
    ids = (rep["id"].astype(str) != bruto["id"].astype(str)).sum()
    convo = (rep["conversation_id"].astype(str) != bruto["conversation_id"].astype(str)).sum()
    aut = (rep["author_id"].astype(str) != bruto["author_id"].astype(str)).sum()
    largo = sum(1 for i in range(len(rep))
                if len(rep["text_completo"].iloc[i]) > len(bruto["text_completo"].iloc[i]))
    saltos = sum(1 for i in range(len(rep))
                 if "\n" in rep["text_completo"].iloc[i]
                 and "\n" not in bruto["text_completo"].iloc[i])
    # El mojibake se cuenta sobre los valores que realmente se escribieron, es
    # decir los extraídos del raw_json crudo — no sobre las columnas planas, que
    # se descartan. Un "irreparable" aquí sí es un campo que quedó crudo.
    moji = irrep = 0
    for d in docs_crudos:
        a = d.get("_author") or {}
        for v in (_s(d.get("text")), _s(a.get("name")),
                  _s(a.get("location")), _s(a.get("description"))):
            _, hubo = reparar_texto(v)
            if hubo:
                moji += 1
            elif v and not all(ord(c) < 128 for c in v):
                irrep += 1

    escribir(f"\n{'=' * 70}\nREPARACIÓN\n{'=' * 70}")
    escribir(f"  identificadores corregidos   id {ids:,} · conversation_id {convo:,} · author_id {aut:,}")
    escribir(f"  textos destruncados          {largo:,}")
    escribir(f"  textos con saltos restaurados{saltos:>6,}")
    escribir(f"  campos con mojibake reparado {moji:,}")
    escribir(f"  campos irreparables          {irrep:,}  (se conserva el crudo)")

    if len(rep) != len(bruto):
        raise RuntimeError(f"Conteo de filas alterado: {len(bruto):,} → {len(rep):,}")
    unicos = rep["id"].nunique()
    escribir(f"\n  filas {len(rep):,} · identificadores únicos {unicos:,} · "
             f"largos {sorted(set(rep['id'].str.len()))}")
    if unicos != len(rep):
        escribir(f"  ⚠️  {len(rep) - unicos:,} identificadores duplicados tras la reparación")

    destino.parent.mkdir(parents=True, exist_ok=True)
    rep.to_csv(destino, index=False, encoding="utf-8-sig")   # el BOM es lo que salva a Excel
    escribir(f"\n✅ '{destino.name}'  ({destino.stat().st_size / 1e6:.1f} MB)")
    return rep


# ──────────────────────────────────────────────────────────────────────────
#  Carga
# ──────────────────────────────────────────────────────────────────────────

def _leer_tabla(p: Path, escribir=print) -> pd.DataFrame:
    """Lee CSV o Excel. Falla con un mensaje claro si el formato no corresponde."""
    ext = p.suffix.lower()

    if ext in (".xlsx", ".xlsm", ".xls"):
        hojas = pd.ExcelFile(p).sheet_names
        escribir(f"   Excel detectado ({ext}) — hojas: {hojas}; se lee '{hojas[0]}'")
        return pd.read_excel(p, sheet_name=hojas[0], **LECTURA)

    if ext in (".csv", ".tsv", ".txt"):
        sep = "\t" if ext == ".tsv" else ","
        for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
            try:
                df = pd.read_csv(p, sep=sep, low_memory=False, encoding=enc, **LECTURA)
            except UnicodeDecodeError:
                continue
            if enc != "utf-8":
                escribir(f"   ⚠️  el archivo no era utf-8; se leyó como {enc} "
                         f"— revisa los acentos antes de calificar")
            return df
        raise RuntimeError(f"No se pudo decodificar '{p.name}' con utf-8, cp1252 ni latin-1.")

    raise ValueError(
        f"Formato no soportado: '{p.suffix or p.name}'. "
        "Se acepta .csv, .tsv, .txt, .xlsx o .xls."
    )


def cargar(cfg: Config, ruta: Path | None = None, escribir=print) -> pd.DataFrame:
    p = ruta or cfg.corpus_a_calificar
    exigir_insumo(p, "el corpus a calificar", "reparar (y opcionalmente traducir)")

    df = _leer_tabla(p, escribir)
    escribir(f"✅ Corpus cargado: {p.name} — {len(df):,} filas × {len(df.columns)} columnas")

    faltantes = [c for c in (cfg.col_id, cfg.col_texto) if c not in df.columns]
    if faltantes:
        raise RuntimeError(
            f"Columnas requeridas ausentes: {faltantes}. "
            f"Columnas disponibles: {list(df.columns)}. "
            f"Ajusta col_id / col_texto en config.toml."
        )
    for opcional in (cfg.col_traduccion, cfg.col_lang):
        if opcional and opcional not in df.columns:
            escribir(f"   ⚠️  columna opcional '{opcional}' ausente — se ignora")

    dup = df[cfg.col_id].duplicated().sum()
    if dup:
        escribir(f"   ⚠️  {dup:,} identificadores duplicados en '{cfg.col_id}' "
                 f"— el merge final los reportará")
    return df


# ──────────────────────────────────────────────────────────────────────────
#  Selección
# ──────────────────────────────────────────────────────────────────────────

def _serie_es_true(serie):
    return serie.fillna("").astype(str).str.strip().str.upper().isin(["TRUE", "1", "SI", "YES"])


def ids_de_checkpoint(ruta: Path) -> set[str]:
    """Identificadores de tuit presentes en un checkpoint.

    Permite reproducir exactamente la selección de una corrida anterior. Es
    necesario porque el muestreo por semilla NO es reproducible si el corpus
    cambia de tamaño: al pasar de 2,562 a 2,631 filas,
    ``sample(n=60, random_state=42)`` devolvió 60 tuits de los que sólo 1
    coincidía con la selección original.
    """
    exigir_insumo(ruta, "el checkpoint de referencia", "correr")
    ids: set[str] = set()
    with ruta.open(encoding="utf-8") as fh:
        for linea in fh:
            linea = linea.strip()
            if not linea:
                continue
            try:
                ids.add(str(json.loads(linea)["tweet_id"]))
            except Exception:
                continue   # línea truncada por una interrupción
    return ids


def seleccionar(cfg: Config, df: pd.DataFrame, n_criterios: int,
                ids: set[str] | None = None, escribir=print) -> pd.DataFrame:
    """Aplica filtros y devuelve el subconjunto a evaluar.

    Si se pasa ``ids``, la selección es exactamente ese conjunto y no se
    aplican ni los filtros ni el muestreo: es el modo que reproduce una
    corrida anterior sin depender del tamaño del corpus.
    """
    sub = df.copy()
    inicial = len(sub)
    trazas: list[str] = []

    if ids is not None:
        presentes = sub[sub[cfg.col_id].isin(ids)]
        ausentes = ids - set(presentes[cfg.col_id])
        escribir(f"Selección por lista explícita: {len(presentes):,} de {len(ids):,} "
                 f"identificadores encontrados en el corpus")
        if ausentes:
            escribir(f"   ⚠️  {len(ausentes):,} identificadores del listado no están "
                     f"en el corpus y se omiten")
        escribir(f"\n{len(presentes):,} filas × {n_criterios} criterios = "
                 f"{len(presentes) * n_criterios:,} llamadas al modelo")
        return presentes.reset_index(drop=True)

    if cfg.excluir_retweets and "is_retweet" in sub.columns:
        marca = _serie_es_true(sub["is_retweet"])
        trazas.append(f"retweets excluidos: {marca.sum():,}")
        sub = sub[~marca]
    if cfg.excluir_quotes and "is_quote" in sub.columns:
        marca = _serie_es_true(sub["is_quote"])
        trazas.append(f"quotes excluidos: {marca.sum():,}")
        sub = sub[~marca]
    if cfg.filtro_lang and cfg.col_lang in sub.columns:
        antes = len(sub)
        sub = sub[sub[cfg.col_lang].isin(cfg.filtro_lang)]
        trazas.append(f"filtro lang {cfg.filtro_lang}: {antes - len(sub):,} fuera")
    if cfg.filtro_tipo_query and "TIPO_QUERY" in sub.columns:
        antes = len(sub)
        sub = sub[sub["TIPO_QUERY"].isin(cfg.filtro_tipo_query)]
        trazas.append(f"filtro TIPO_QUERY {cfg.filtro_tipo_query}: {antes - len(sub):,} fuera")

    # Descartar filas sin texto: no hay nada que calificar
    vacias = sub[cfg.col_texto].fillna("").str.strip().eq("")
    if vacias.any():
        trazas.append(f"sin texto: {vacias.sum():,} fuera")
        sub = sub[~vacias]

    # n_muestra == 0 significa corpus completo (TOML no tiene null)
    if cfg.n_muestra and cfg.n_muestra < len(sub):
        sub = sub.sample(n=cfg.n_muestra, random_state=cfg.semilla)
        trazas.append(f"muestra aleatoria n={cfg.n_muestra} (semilla={cfg.semilla})")

    escribir(f"Subconjunto: {inicial:,} → {len(sub):,} filas")
    for t in trazas:
        escribir(f"   · {t}")
    escribir(f"\n{len(sub):,} filas × {n_criterios} criterios = "
             f"{len(sub) * n_criterios:,} llamadas al modelo")
    return sub.reset_index(drop=True)


# ──────────────────────────────────────────────────────────────────────────
#  Payload
# ──────────────────────────────────────────────────────────────────────────

def _txt(fila, col: str | None) -> str:
    """Lectura segura de una celda.

    CUIDADO: NaN de pandas es TRUTHY, así que ``if fila.get(col):`` da True en
    celdas vacías. Sin esto, las filas de 'in_reply_to_user_id' vacío se
    marcarían todas como reply, y cada fila sin traducción recibiría el
    literal 'nan' como traducción.
    """
    if not col:
        return ""
    v = fila.get(col)
    if v is None or (isinstance(v, float) and v != v) or pd.isna(v):
        return ""
    s = str(v).strip()
    return "" if s.lower() in {"nan", "none", "<na>"} else s


def _es_true(v) -> bool:
    if v is None or (isinstance(v, float) and v != v):
        return False
    return str(v).strip().upper() in {"TRUE", "1", "SI", "YES"}


def detectar_contexto_incompleto(cfg: Config, fila) -> list[str]:
    """Replies, retweets y quotes: su texto no es autosuficiente."""
    marcas = []
    if _txt(fila, "in_reply_to_user_id"):
        marcas.append("reply")
    elif _txt(fila, cfg.col_texto).lstrip().startswith("@"):
        marcas.append("reply")          # heurística: arranca con mención
    if _es_true(fila.get("is_retweet")):
        marcas.append("retweet")
    if _es_true(fila.get("is_quote")):
        marcas.append("quote")
    return marcas


AVISOS = {
    "reply":   "Este tweet es una RESPUESTA a otro tweet que NO está disponible. "
               "Califica sólo con el texto presente y di en tu justificación que el contexto previo falta.",
    "retweet": "Este tweet es un RETWEET: el texto no fue escrito por el autor de la fila.",
    "quote":   "Este tweet CITA otro tweet que NO está disponible.",
}


def construir_payload(cfg: Config, fila) -> tuple[str, list[str]]:
    """Devuelve ``(texto_payload, marcas_de_contexto)``."""
    partes = []
    marcas = detectar_contexto_incompleto(cfg, fila)

    if marcas:
        avisos = " ".join(AVISOS[m] for m in marcas if m in AVISOS)
        partes.append(f"[ADVERTENCIA DE CONTEXTO INCOMPLETO] {avisos}")

    lang = _txt(fila, cfg.col_lang) or "desconocido"
    partes.append(f'<tweet idioma="{lang}">\n{_txt(fila, cfg.col_texto)}\n</tweet>')

    trad = _txt(fila, cfg.col_traduccion)
    if trad:
        partes.append(
            f"<traduccion_al_espanol_de_apoyo>\n{trad}\n"
            f"</traduccion_al_espanol_de_apoyo>"
        )
    # Sin traducción no se invoca ninguna: el modelo es multilingüe.
    return "\n\n".join(partes), marcas


def anotar_payloads(cfg: Config, sub: pd.DataFrame, escribir=print) -> pd.DataFrame:
    """Añade '_payload' y 'contexto_incompleto' al subconjunto."""
    construidos = [construir_payload(cfg, f) for _, f in sub.iterrows()]
    sub = sub.copy()
    sub["_payload"] = [p for p, _ in construidos]
    sub["contexto_incompleto"] = [";".join(m) if m else "" for _, m in construidos]

    n_inc = (sub["contexto_incompleto"] != "").sum()
    n_trad = sum("traduccion_al_espanol" in p for p in sub["_payload"])
    escribir(f"Payloads construidos: {len(sub):,}")
    escribir(f"   con contexto incompleto: {n_inc:,} ({n_inc / max(len(sub), 1):.1%})")
    escribir(f"   con traducción de apoyo: {n_trad:,}")
    return sub
