"""Preparación, agregación y generación del HTML de gráficas.

Traslado de las celdas 26, 27 y 28 del cuaderno.

La plantilla de ECharts vive en ``plantilla_graficas.html``, al lado de este
módulo. En el cuaderno eran 352 líneas de JavaScript dentro de una cadena de
Python; separarlas hace que cada archivo se pueda leer con las herramientas de
su propio lenguaje.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

from .config import Config, exigir_insumo
from .scoring import cargar_resultados

RUTA_PLANTILLA = Path(__file__).parent / "plantilla_graficas.html"

#: La biblioteca de gráficas viaja DENTRO del HTML, no desde un CDN.
#:
#: El cuaderno la cargaba de cdnjs con una versión que devuelve 404 —la 5.5.1
#: no existe ahí— así que la página mostraba su mensaje de respaldo en vez de
#: las gráficas. En Colab el fallo pasaba desapercibido entre las salidas de
#: las celdas. Embeberla arregla eso y además hace el artefacto autosuficiente:
#: un HTML de análisis debe poder abrirse dentro de dos años, sin red y sin que
#: importe si ese CDN sigue sirviendo esa versión.
RUTA_ECHARTS = Path(__file__).parent / "echarts.min.js"

ETIQUETA_SIN_IDIOMA = "(sin idioma)"

# Códigos que la API devuelve cuando no hay texto del cual inferir idioma.
# No son idiomas, y conviene que quien use el filtro lo sepa antes de elegirlos:
# 'und' indeterminado, 'zxx' sin contenido lingüístico, 'qme'/'qam'/'qct'/'qht'/
# 'qst' marcadores internos de contenido multimedia o mixto, 'art' artificial.
CODIGOS_SIN_IDIOMA = {"und", "zxx", "qme", "qam", "qct", "qht", "qst", "art"}

# ── Paleta ────────────────────────────────────────────────────────────────
# Valencia: divergente rojo↔azul con gris neutro al centro. NO es una escala de
# logro: el 1 es "muy negativo" y el 5 "muy positivo", así que un solo tono
# claro→oscuro mentiría sobre la polaridad. Cada brazo validado como rampa
# ordinal (lightness monótona, separación ≥0.06, extremo claro sobre el fondo).
# Idiomas: categórica nominal, sin azul ni rojo para que no se confundan con
# la valencia.
PALETA_VALENCIA = ["#c62f2e", "#e8716f", "#c3c2b7", "#6da7ec", "#1c5cab"]
PALETA_IDIOMAS = ["#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#4a3aa7", "#898781"]
COLOR_AUSENCIA = "#898781"


# ──────────────────────────────────────────────────────────────────────────
#  Preparación
# ──────────────────────────────────────────────────────────────────────────

def _a_utc(serie: pd.Series) -> pd.Series:
    """El corpus mezcla '2026-06-03T23:59:50' con '2026-07-04 7:02:11'.
    Las marcas sin huso se interpretan como UTC, que es lo que entrega la API."""
    for extra in ({"format": "mixed"}, {"format": "ISO8601"}, {}):
        try:
            return pd.to_datetime(serie, errors="coerce", utc=True, **extra)
        except (ValueError, TypeError):
            continue
    return pd.to_datetime(serie, errors="coerce", utc=True)


def _a_hora_local(dt_utc: pd.Series, zona: str, escribir=print) -> tuple:
    """Devuelve (serie local, zona efectiva). Si la zona no existe en el entorno
    se informa y se sigue en UTC: es preferible una gráfica con el día corrido
    seis horas, dicha en voz alta, que ninguna gráfica."""
    try:
        return dt_utc.dt.tz_convert(zona), zona
    except Exception as exc:
        escribir(f"   ⚠️  no se pudo convertir a '{zona}' ({exc}). "
                 f"Se agrupa en UTC: los cortes de período quedan corridos hasta 6 h.")
        return dt_utc, "UTC"


def asignar_periodo(cfg: Config, fecha_local: pd.Series) -> pd.Series:
    """Intervalos [desde, hasta). El primero que acepta la fecha se la queda, y
    la configuración ya garantizó que no se solapan, así que el orden no decide
    nada."""
    periodo = pd.Series(pd.NA, index=fecha_local.index, dtype="object")
    for p in cfg.periodos:
        dentro = fecha_local >= pd.Timestamp(p.desde)
        if p.hasta is not None:
            dentro &= fecha_local < pd.Timestamp(p.hasta)
        periodo = periodo.mask(dentro & periodo.isna(), p.nombre)
    return periodo


def calificaciones_desde_disco(cfg: Config, criterios: list[dict],
                               escribir=print) -> pd.DataFrame:
    """El CSV tidy si existe; si no, el checkpoint. Permite graficar sin
    reejecutar la corrida."""
    if cfg.salida_tidy.exists():
        return pd.read_csv(cfg.salida_tidy, dtype=str, keep_default_na=False,
                           na_values=[""])
    escribir(f"   ℹ️  '{cfg.salida_tidy.name}' no existe; se reconstruye desde "
             f"'{cfg.checkpoint.name}'.")
    res = cargar_resultados(cfg.checkpoint)
    meta = {c["slug"]: (c["id_criterio"], c["nombre"]) for c in criterios}
    res["id_criterio"] = res["slug"].map(lambda s: meta.get(s, ("", ""))[0])
    res["criterio"] = res["slug"].map(lambda s: meta.get(s, ("", ""))[1])
    return res


def preparar(cfg: Config, tidy: pd.DataFrame, df: pd.DataFrame,
             escribir=print) -> pd.DataFrame:
    """Une calificaciones con corpus y añade fecha local, idioma y período.

    El tidy sale con tweet_id, slug, nivel, estado y poco más: no trae ni fecha
    ni idioma. Toda gráfica empieza por esta unión.
    """
    escribir("=" * 74)
    escribir(f"PREPARACIÓN · {len(tidy):,} calificaciones × {len(df):,} filas de corpus")
    escribir("=" * 74)

    faltan = [c for c in ("tweet_id", "slug", "nivel", "estado") if c not in tidy.columns]
    if faltan:
        raise RuntimeError(f"Las calificaciones no traen {faltan}.")

    cols = [cfg.col_id, "created_at", cfg.col_lang]
    ausentes = [c for c in cols if c not in df.columns]
    if ausentes:
        raise RuntimeError(
            f"El corpus no trae {ausentes}. Sin 'created_at' no hay eje temporal "
            f"y sin '{cfg.col_lang}' no hay filtro de idioma."
        )

    corpus = df[cols].copy()
    corpus[cfg.col_id] = corpus[cfg.col_id].astype(str).str.strip()
    corpus = corpus.drop_duplicates(subset=[cfg.col_id], keep="first")

    viz = tidy.copy()
    viz["tweet_id"] = viz["tweet_id"].astype(str).str.strip()

    # ── Huérfanos: el mismo criterio de integridad que el merge ──────────
    ids_corpus = set(corpus[cfg.col_id])
    fuera = ~viz["tweet_id"].isin(ids_corpus)
    if fuera.any():
        n_ids = viz.loc[fuera, "tweet_id"].nunique()
        escribir(f"   ⚠️  {int(fuera.sum()):,} calificaciones de {n_ids:,} identificadores "
                 f"inexistentes en el corpus — excluidas")
        escribir(f"       ejemplos: {sorted(viz.loc[fuera, 'tweet_id'].unique())[:3]}")
        if n_ids == viz["tweet_id"].nunique():
            escribir("       ⛔ NINGÚN identificador coincide. Es la firma de un corpus "
                     "sin reparar: los de 19 dígitos pasaron por float64 y ya no son "
                     "ellos. Corre la etapa de reparación antes de graficar.")
        viz = viz[~fuera]

    viz = viz.merge(corpus, left_on="tweet_id", right_on=cfg.col_id,
                    how="left", suffixes=("", "_corpus"))

    # ── Fecha: UTC → hora local → día ────────────────────────────────────
    dt_utc = _a_utc(viz["created_at"])
    ilegible = dt_utc.isna()
    if ilegible.any():
        escribir(f"   ⚠️  {int(ilegible.sum()):,} calificaciones con 'created_at' "
                 f"ilegible — excluidas")
        viz, dt_utc = viz[~ilegible], dt_utc[~ilegible]

    dt_local, zona = _a_hora_local(dt_utc, cfg.zona_horaria, escribir)
    viz["fecha"] = dt_local.dt.normalize().dt.tz_localize(None).values
    viz["fecha_str"] = viz["fecha"].dt.strftime("%Y-%m-%d")

    # ── Idioma ───────────────────────────────────────────────────────────
    lang = viz[cfg.col_lang].fillna("").astype(str).str.strip()
    viz["idioma"] = lang.where(lang != "", ETIQUETA_SIN_IDIOMA)

    # ── Autosuficiencia: replies, retweets y quotes no lo son ────────────
    if "contexto_incompleto" not in viz.columns:
        escribir("   ℹ️  sin columna 'contexto_incompleto': todo se cuenta como autosuficiente")
        viz["autosuficiente"] = True
    else:
        viz["autosuficiente"] = (viz["contexto_incompleto"].fillna("")
                                 .astype(str).str.strip() == "")

    # ── Período ──────────────────────────────────────────────────────────
    viz["periodo"] = asignar_periodo(cfg, viz["fecha"])
    sin_periodo = viz["periodo"].isna()
    if sin_periodo.any():
        rango = viz.loc[sin_periodo, "fecha_str"]
        escribir(f"   ⚠️  {int(sin_periodo.sum()):,} calificaciones fuera de todo período "
                 f"({rango.min()} … {rango.max()}) — quedan en la serie diaria, "
                 f"no en los paneles por período")

    # ── Reporte ──────────────────────────────────────────────────────────
    n_tweets = viz["tweet_id"].nunique()
    dias = viz["fecha_str"].nunique()
    por_dia = n_tweets / max(dias, 1)
    n_incompletos = int((~viz["autosuficiente"]).sum())
    escribir(f"\n   {len(viz):,} calificaciones · {n_tweets:,} tuits · {dias} días "
             f"({viz['fecha_str'].min()} … {viz['fecha_str'].max()})")
    escribir(f"   día cortado en {zona} · contexto incompleto: {n_incompletos:,} "
             f"calificaciones ({n_incompletos / max(len(viz), 1):.1%})")

    escribir(f"\n   {'período':<32} {'días':>5} {'tuits':>8} {'por día':>8}")
    for p in cfg.periodos:
        s = viz[viz["periodo"] == p.nombre]
        d, n = s["fecha_str"].nunique(), s["tweet_id"].nunique()
        escribir(f"   {p.nombre:<32} {d:>5} {n:>8,} {n / max(d, 1):>8.1f}")

    if por_dia < cfg.umbral_cobertura_diaria:
        escribir(f"\n   ⚠️  COBERTURA INSUFICIENTE: {por_dia:.1f} tuits calificados por "
                 f"día, bajo el umbral de {cfg.umbral_cobertura_diaria}.")
        escribir("       Repartidos entre los niveles de un criterio, cada punto de la "
                 "serie diaria vale menos de un tuit: lo que se vería es la semilla del "
                 "muestreo, no el fenómeno. Usa el perfil «completo».")
    escribir("=" * 74)
    return viz


# ──────────────────────────────────────────────────────────────────────────
#  Qué nivel significa "ausencia"
# ──────────────────────────────────────────────────────────────────────────
# Esta rúbrica resuelve el problema del nivel 0 con una escala híbrida: el 0 es
# AUSENCIA (el tuit no toca la dimensión) y 1-5 es valencia, de muy negativa a
# muy positiva. El 0 no es ordinalmente contiguo al 1 —pasar de "ausencia" a
# "muy negativo" no es un incremento en la misma latente— así que apilarlo con
# los demás lo pondría en el extremo negativo, que es lo contrario de lo que
# significa. Se separa: valencia por un lado, ausencia por otro.
_NEGACION = re.compile(
    r"\bno\s+(evalúa|evalua|expresa|menciona|contiene|aborda|refiere|toca|hay)\b",
    re.IGNORECASE)


def _detectar_niveles_ausencia(criterio: dict) -> set[str]:
    """Un nivel es de ausencia si su descriptor niega que el tuit toque la
    dimensión. Deliberadamente conservador: si la rúbrica no lo dice así,
    devuelve vacío y todos los niveles se grafican."""
    return {str(n["etiqueta"]) for n in criterio["niveles"]
            if _NEGACION.search(str(n.get("descriptor", ""))[:160])}


def resolver_niveles_ausencia(cfg: Config, criterios: list[dict]) -> dict[str, set[str]]:
    """``niveles_ausencia`` acepta 'auto', vacío, una lista de etiquetas para
    todos, o un mapa {slug: [etiquetas]}."""
    declarado = cfg.niveles_ausencia
    mapa: dict[str, set[str]] = {}
    for c in criterios:
        if declarado == "auto":
            mapa[c["slug"]] = _detectar_niveles_ausencia(c)
        elif not declarado:
            mapa[c["slug"]] = set()
        elif isinstance(declarado, dict):
            mapa[c["slug"]] = {str(x) for x in declarado.get(c["slug"], [])}
        else:
            mapa[c["slug"]] = {str(x) for x in declarado}
    return mapa


def etiqueta_criterio(criterio: dict) -> str:
    """Nombre corto del criterio, para leyendas y ejes.

    Las gráficas usaban el identificador de la rúbrica —«RÚBRICA 1», «RÚBRICA
    2»— que no dice nada: para leer una serie hay que recordar qué mide cada
    número. El nombre completo tampoco sirve, porque no cabe en una leyenda.

    Se deriva del propio nombre del criterio, no de una lista escrita a mano,
    para que siga funcionando si la rúbrica cambia:

        "ATMÓSFERA DE MÉXICO: DIMENSIÓN SIMPÁTICA / EMOCIONAL"  → "Atmósfera"
        "IMAGEN CULTURAL DE MÉXICO: DIMENSIÓN ESTÉTICA"         → "Imagen cultural"
        "PERSPECTIVA POLÍTICA DE MÉXICO: DIMENSIÓN FUNCIONAL"   → "Perspectiva política"
        "SALIENCIA DE VIOLENCIA EN MÉXICO"                      → "Saliencia de violencia"

    Se queda con lo anterior a los dos puntos —donde la rúbrica pone la
    dimensión antes del tecnicismo— y le quita el complemento del país, que es
    el mismo en todos y por tanto no distingue nada.
    """
    nombre = str(criterio.get("nombre") or criterio.get("id_criterio") or "").strip()
    cabeza = nombre.split(":", 1)[0].strip()
    for sufijo in (" DE MÉXICO", " EN MÉXICO", " DE MEXICO", " EN MEXICO",
                   " de México", " en México"):
        if cabeza.upper().endswith(sufijo.upper()):
            cabeza = cabeza[: -len(sufijo)].strip()
            break
    if not cabeza:
        return nombre or "(sin nombre)"
    # Las rúbricas vienen en versales; se deja sólo la inicial en mayúscula.
    return cabeza.capitalize() if cabeza.isupper() else cabeza


# ──────────────────────────────────────────────────────────────────────────
#  Agregación
# ──────────────────────────────────────────────────────────────────────────
# Se agrega ANTES de dibujar y se embebe sólo el agregado: el filtro de idioma
# y el conmutador absoluto/proporción son reducciones sobre un arreglo chico en
# el cliente, no una reejecución de Python. Las combinaciones vacías se omiten:
# la matriz completa (días × criterios × niveles × idiomas) es casi toda hueca.

def agregar(cfg: Config, viz: pd.DataFrame, criterios: list[dict],
            escribir=print) -> dict:
    ausencia = resolver_niveles_ausencia(cfg, criterios)

    v = viz.copy()
    v["nivel"] = v["nivel"].astype(str).str.strip()
    v["estado"] = v["estado"].astype(str).str.strip()
    es_ausencia = v.apply(
        lambda r: r["estado"] == "NO_APLICABLE"
        or (r["estado"] == "OK" and r["nivel"] in ausencia.get(r["slug"], set())),
        axis=1)
    v["clase"] = np.where(
        es_ausencia, "ausencia",
        np.where(v["estado"] == "OK", "valencia", "fallida"))
    v.loc[v["clase"] != "valencia", "nivel"] = ""

    # Conteos por día · criterio · nivel · idioma · autosuficiencia
    agg = (v.groupby(["fecha_str", "slug", "clase", "nivel", "idioma",
                      "autosuficiente"], dropna=False)
             .size().reset_index(name="n"))
    agg = agg[agg["n"] > 0]

    # Volumen del corpus: tuits distintos, no calificaciones
    vol = (v.drop_duplicates(subset=["tweet_id", "fecha_str", "idioma", "autosuficiente"])
             .groupby(["fecha_str", "idioma", "autosuficiente"])
             .size().reset_index(name="n"))

    # Totales por idioma, para mostrarlos junto a cada opción del filtro
    por_idioma = (v.drop_duplicates(subset=["tweet_id"])
                    .groupby("idioma").size().sort_values(ascending=False))

    periodos = []
    for p in cfg.periodos:
        s = v[v["periodo"] == p.nombre]
        d = int(s["fecha_str"].nunique())
        periodos.append({"nombre": p.nombre, "dias": d,
                         "tuits": int(s["tweet_id"].nunique()),
                         "por_dia": round(s["tweet_id"].nunique() / max(d, 1), 1)})

    orden = {c["slug"]: [str(e) for e in c["etiquetas_validas"]] for c in criterios}
    crits = [{"slug": c["slug"], "id": c["id_criterio"], "nombre": c["nombre"],
              "etiqueta": etiqueta_criterio(c),
              "niveles": [e for e in orden[c["slug"]]
                          if e not in ausencia.get(c["slug"], set())],
              "ausencia": sorted(ausencia.get(c["slug"], set()))}
             for c in criterios]

    fechas = sorted(v["fecha_str"].dropna().unique())
    datos = {
        "criterios": crits,
        "fechas": fechas,
        "periodos": periodos,
        "idiomas": [{"codigo": k, "n": int(n),
                     "sin_idioma": k in CODIGOS_SIN_IDIOMA or k == ETIQUETA_SIN_IDIOMA}
                    for k, n in por_idioma.items()],
        "agg": agg.to_dict("records"),
        "volumen": vol.to_dict("records"),
        "umbral_muestra": cfg.umbral_muestra_pequena,
        "ventana": cfg.ventana_suavizado,
        "cortes": [{"nombre": p.nombre, "desde": str(p.desde),
                    "hasta": str(p.hasta) if p.hasta else None} for p in cfg.periodos],
    }

    # ── Reporte ──────────────────────────────────────────────────────────
    bytes_json = len(json.dumps(datos, ensure_ascii=False).encode("utf-8"))
    escribir("=" * 74)
    escribir("AGREGACIÓN")
    escribir("=" * 74)
    for c in crits:
        s = v[v["slug"] == c["slug"]]
        val = int((s["clase"] == "valencia").sum())
        aus = int((s["clase"] == "ausencia").sum())
        fal = int((s["clase"] == "fallida").sum())
        tot = max(len(s), 1)
        escribir(f"\n  [{c['id']}] {c['nombre'][:48]}")
        escribir(f"      valencia {val:>6,} ({val / tot:>5.1%})  ·  "
                 f"ausencia {aus:>6,} ({aus / tot:>5.1%})  ·  fallidas {fal:>4,}")
        if c["ausencia"]:
            escribir(f"      nivel(es) de ausencia detectados: {c['ausencia']} "
                     f"— fuera de las series y del denominador")
        else:
            escribir("      sin nivel de ausencia en la rúbrica: se grafican todos")

    escribir(f"\n  agregado: {len(agg):,} filas · volumen: {len(vol):,} filas")
    escribir(f"  payload serializado: {bytes_json / 1024:.0f} KB")
    escribir(f"  {len(fechas)} días · {len(datos['idiomas'])} idiomas · "
             f"{len(crits)} criterios")
    escribir(f"\n  {'período':<32} {'días':>5} {'tuits':>8} {'por día':>8}")
    for p in periodos:
        escribir(f"  {p['nombre']:<32} {p['dias']:>5} {p['tuits']:>8,} {p['por_dia']:>8.1f}")
    escribir(f"  {'suma':<32} {'':>5} {sum(p['tuits'] for p in periodos):>8,}")
    escribir("=" * 74)
    return datos


# ──────────────────────────────────────────────────────────────────────────
#  HTML
# ──────────────────────────────────────────────────────────────────────────

def construir_html(cfg: Config, datos: dict) -> str:
    plantilla = RUTA_PLANTILLA.read_text(encoding="utf-8")
    biblioteca = exigir_insumo(
        RUTA_ECHARTS, "la biblioteca de gráficas embebida",
        "ninguna: viaja con el paquete").read_text(encoding="utf-8")
    p = datos["periodos"]
    sub = (f"{sum(x['tuits'] for x in p):,} tuits · {len(datos['fechas'])} días · "
           f"{len(datos['criterios'])} criterios · día cortado en {cfg.zona_horaria} · "
           + " · ".join(f"{x['nombre']}: {x['tuits']:,}" for x in p))
    lim = ("El corpus son las líneas de tiempo completas de un conjunto acotado de "
           "cuentas, no una muestra aleatoria de la conversación sobre México. Los "
           "cambios entre períodos son coincidencia temporal, no causalidad, y unas "
           "pocas cuentas aportan buena parte del volumen: un movimiento en la serie "
           "puede ser el humor de una persona.")
    return (plantilla
            .replace("__ECHARTS__", biblioteca)
            .replace("__TITULO__", "Calificaciones por rúbrica")
            .replace("__SUBTITULO__", sub)
            .replace("__LIMITACION__", lim)
            .replace("__VENTANA__", str(cfg.ventana_suavizado))
            .replace("__PAL_VAL__", json.dumps(PALETA_VALENCIA))
            .replace("__PAL_IDIOMA__", json.dumps(PALETA_IDIOMAS))
            .replace("__C_AUS__", COLOR_AUSENCIA)
            .replace("__DATOS__", json.dumps(datos, ensure_ascii=False)))


def publicar(cfg: Config, datos: dict, escribir=print) -> Path:
    """Escribe el HTML a disco y devuelve su ruta.

    El artefacto es el archivo: se abre en el navegador y conserva todos los
    filtros. No hay visualización incrustada porque no hay cuaderno.
    """
    html = construir_html(cfg, datos)
    destino = cfg.salida_html
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(html, encoding="utf-8")
    escribir(f"✅ '{destino.name}'  ({destino.stat().st_size / 1024:.0f} KB)")
    escribir(f"   ábrelo en el navegador: {destino}")
    return destino
