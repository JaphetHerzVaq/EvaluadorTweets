"""Exportación del CSV enriquecido y de la variante tidy.

Traslado de las celdas 24 y 25 del cuaderno.

El CSV ancho preserva íntegras las columnas originales del corpus y añade
``{slug}_nivel``, ``{slug}_puntaje``, ``{slug}_justificacion`` y
``{slug}_aplicable`` por criterio. El tidy da una fila por tuit × criterio,
que es la forma cómoda para analizar.

No se reutilizan las columnas vacías ``tipo`` y ``justificacion`` del corpus:
dos columnas no alcanzan para N criterios, y sobrescribirlas destruiría un
esquema que puede tener otro dueño.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .config import Config
from .scoring import cargar_resultados


def nombres_columnas(criterio: dict) -> dict[str, str]:
    s = criterio["slug"]
    cols = {"nivel": f"{s}_nivel", "justificacion": f"{s}_justificacion",
            "aplicable": f"{s}_aplicable"}
    if criterio["escala_numerica"]:
        cols["puntaje"] = f"{s}_puntaje"      # sólo si la rúbrica define puntos
    return cols


def construir_salidas(cfg: Config, df_original: pd.DataFrame, criterios: list[dict],
                      res: pd.DataFrame | None = None,
                      escribir=print) -> tuple[pd.DataFrame, pd.DataFrame]:
    res = res if res is not None else cargar_resultados(cfg.checkpoint)

    # ── Integridad: resultados cuyo tuit no existe en el corpus ──────────
    ids_corpus = set(df_original[cfg.col_id].astype(str))
    huerfanos = sorted(set(res["tweet_id"]) - ids_corpus)
    if huerfanos:
        escribir(f"⚠️  {len(huerfanos)} resultados con tweet_id inexistente en el corpus "
                 f"(no se incorporan): {huerfanos[:5]}")
        res = res[res["tweet_id"].isin(ids_corpus)]

    # ── Ancho ────────────────────────────────────────────────────────────
    ancho = df_original.copy()
    ancho["_k"] = ancho[cfg.col_id].astype(str)
    n_cols = 0
    for c in criterios:
        cols = nombres_columnas(c)
        s = res[res["slug"] == c["slug"]].drop_duplicates(subset=["tweet_id"], keep="last")
        m = s.set_index("tweet_id")
        for campo, nombre in cols.items():
            if campo != "aplicable" and campo not in m.columns:
                ancho[nombre] = pd.NA      # ningún resultado trajo este campo
                n_cols += 1
                continue
            if campo == "aplicable":
                # texto explícito: distingue no evaluada (vacío) de fallida
                serie = m["estado"].map(
                    lambda e: "" if pd.isna(e) else
                              ("SI" if e == "OK" else ("NO" if e == "NO_APLICABLE" else e))
                )
            else:
                serie = m[campo]
            ancho[nombre] = ancho["_k"].map(serie)
            n_cols += 1
    ancho = ancho.drop(columns=["_k"])

    # ── Verificación de conteo de filas ──────────────────────────────────
    if len(ancho) != len(df_original):
        raise RuntimeError(
            f"El merge alteró el número de filas: {len(df_original):,} → {len(ancho):,}. "
            f"Probable duplicación de '{cfg.col_id}'."
        )
    dups = df_original[cfg.col_id].astype(str).duplicated().sum()
    if dups:
        escribir(f"⚠️  {dups:,} '{cfg.col_id}' duplicados en el original: "
                 f"esas filas comparten calificación")

    # ── Tidy ─────────────────────────────────────────────────────────────
    meta = {c["slug"]: (c["id_criterio"], c["nombre"]) for c in criterios}
    tidy = res.copy()
    tidy["id_criterio"] = tidy["slug"].map(lambda s: meta.get(s, ("", ""))[0])
    tidy["criterio"] = tidy["slug"].map(lambda s: meta.get(s, ("", ""))[1])
    tidy = tidy.reindex(columns=["tweet_id", "id_criterio", "slug", "criterio", "aplicable",
                                 "nivel", "puntaje", "justificacion", "estado", "detalle",
                                 "contexto_incompleto"])

    evaluadas = (ancho[nombres_columnas(criterios[0])["nivel"]].notna().sum()
                 if criterios else 0)
    escribir(f"\n✅ Ancho: {len(ancho):,} filas × {len(ancho.columns)} columnas "
             f"({n_cols} añadidas, {len(df_original.columns)} originales intactas)")
    escribir(f"   filas con calificación: {evaluadas:,} · "
             f"sin evaluar (columnas vacías): {len(ancho) - evaluadas:,}")
    escribir(f"✅ Tidy : {len(tidy):,} filas (tuit × criterio)")
    return ancho, tidy


def exportar(cfg: Config, ancho: pd.DataFrame, tidy: pd.DataFrame,
             n_columnas_originales: int, criterios: list[dict],
             escribir=print) -> list[Path]:
    escritos: list[Path] = []
    for df, ruta in ((ancho, cfg.salida_ancho), (tidy, cfg.salida_tidy)):
        ruta.parent.mkdir(parents=True, exist_ok=True)
        # utf-8-sig: el BOM es lo que hace que Excel respete los acentos
        df.to_csv(ruta, index=False, encoding="utf-8-sig")
        escritos.append(ruta)
        escribir(f"✅ {ruta.name}  ({ruta.stat().st_size / 1e6:.1f} MB)")

    verificar_codificacion(cfg, escritos[0], escribir)

    escribir(f"\n{'=' * 66}")
    escribir("RESUMEN DE EXPORTACIÓN")
    escribir(f"  filas          {len(ancho):,}")
    escribir(f"  columnas       {len(ancho.columns)} "
             f"({len(ancho.columns) - n_columnas_originales} añadidas)")
    escribir(f"  criterios      {len(criterios)}")
    escribir(f"  filas tidy     {len(tidy):,}")
    escribir(f"{'=' * 66}")
    return escritos


def verificar_codificacion(cfg: Config, ruta: Path, escribir=print) -> None:
    """Comprobación de ida y vuelta: se relee lo escrito y se busca que los
    acentos y los caracteres no latinos hayan sobrevivido."""
    prueba = pd.read_csv(ruta, dtype=str, nrows=200, encoding="utf-8-sig")

    col_j = next((c for c in prueba.columns if c.endswith("_justificacion")), None)
    if col_j is not None:
        textos = prueba[col_j].dropna().astype(str)
        acentos = textos[textos.str.contains(r"[áéíóúñÁÉÍÓÚÑ¿¡]", na=False)]
        escribir(f"\n   codificación: {len(acentos)} justificaciones con acentos "
                 f"releídas correctamente")
        if len(acentos):
            escribir(f"   muestra: {acentos.iloc[0][:120]}")

    if cfg.col_texto in prueba.columns:
        cjk = prueba[cfg.col_texto].dropna().astype(str)
        cjk = cjk[cjk.str.contains(r"[぀-ヿ一-鿿가-힯]", na=False)]
        if len(cjk):
            escribir(f"   caracteres no latinos preservados: {cjk.iloc[0][:60]}")
