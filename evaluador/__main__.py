"""Punto de entrada del proceso local: ``python -m evaluador <etapa>``.

Cada etapa lee sus insumos de disco y escribe su artefacto. Son independientes
y reanudables por separado: la reparación y la traducción, que ya están hechas
y costaron dinero, no se vuelven a ejecutar por correr la calificación.

    reparar    xlsx dañado        → corpus reparado
    consolidar base + adicional   → corpus consolidado
    traducir   corpus             → corpus traducido
    rubrica    PDF                → rubrica.json
    correr     corpus + rúbrica   → checkpoint
    auditar    checkpoint         → reporte (no emite llamadas)
    exportar   checkpoint         → CSV ancho + CSV tidy
    graficar   checkpoint         → HTML
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from .config import (ALCANCES, ErrorDeConfiguracion, InsumoAusente,
                     RUTA_CONFIG_POR_DEFECTO, cargar_config, configurar_consola,
                     preparar_entorno_modelo)


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="evaluador",
        description="Califica tuits contra una rúbrica en PDF con agentes paralelos.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--perfil", help="perfil de config.toml (por defecto, el declarado)")
    p.add_argument("--config", default=RUTA_CONFIG_POR_DEFECTO,
                   help=f"archivo de configuración (por defecto {RUTA_CONFIG_POR_DEFECTO})")

    sub = p.add_subparsers(dest="etapa", required=True, metavar="<etapa>")

    sub.add_parser("reparar", help="reconstruye el corpus desde raw_json")

    c = sub.add_parser("consolidar", help="une una fuente adicional al corpus")
    c.add_argument("--base", required=True, help="corpus base")
    c.add_argument("--extra", required=True, help="fuente adicional a incorporar")
    c.add_argument("--destino", help="salida (por defecto, el corpus traducido)")

    sub.add_parser("traducir", help="traduce el corpus, reanudable por fila")

    r = sub.add_parser("rubrica", help="parsea el PDF de la rúbrica")
    r.add_argument("--reparsear", action="store_true",
                   help="rehace el parseo aunque rubrica.json exista (cuesta una llamada)")

    k = sub.add_parser("correr", help="califica el corpus contra la rúbrica")
    k.add_argument("--confirmar", action="store_true",
                   help="autoriza el gasto; sin esto sólo se estima")
    k.add_argument("--alcance", choices=sorted(ALCANCES),
                   help="qué pares recalificar de un checkpoint existente")
    k.add_argument("--ids-de", metavar="CHECKPOINT",
                   help="selecciona exactamente los tuits de otro checkpoint, "
                        "en vez de muestrear (reproduce una corrida anterior)")
    k.add_argument("--forzar-rubrica-distinta", action="store_true",
                   help="permite reanudar aunque los criterios no coincidan")

    a = sub.add_parser("auditar", help="analiza un checkpoint sin modificarlo")
    a.add_argument("checkpoint", nargs="?", help="ruta (por defecto, la del perfil)")

    sub.add_parser("exportar", help="genera el CSV ancho y el tidy")
    sub.add_parser("graficar", help="genera el HTML de gráficas")
    return p


# ──────────────────────────────────────────────────────────────────────────
#  Etapas
# ──────────────────────────────────────────────────────────────────────────

def _rubrica_y_criterios(cfg, reparsear: bool = False):
    from . import rubrica as R
    rub = R.cargar(cfg, forzar_reparseo=reparsear)
    return rub, rub["criterios"]


def _etapa_reparar(cfg, args) -> int:
    from . import corpus as C
    C.reparar(cfg)
    return 0


def _etapa_consolidar(cfg, args) -> int:
    from . import corpus as C
    destino = Path(args.destino) if args.destino else cfg.corpus_traducido
    C.consolidar(cfg, Path(args.base), Path(args.extra), destino)
    return 0


def _etapa_traducir(cfg, args) -> int:
    from . import corpus as C, traduccion as T
    print(preparar_entorno_modelo(cfg))
    df = C.cargar(cfg)
    df, fallidas = asyncio.run(T.traducir_corpus(cfg, df))
    df.to_csv(cfg.corpus_traducido, index=False, encoding="utf-8-sig")
    print(f"\n✅ '{cfg.corpus_traducido.name}'")
    T.verificar_tokens(cfg, df)
    T.contrastar_idioma(cfg, df)
    return 0


def _etapa_rubrica(cfg, args) -> int:
    from . import rubrica as R
    if args.reparsear or not cfg.rubrica_json.exists():
        print(preparar_entorno_modelo(cfg))
    rub, _ = _rubrica_y_criterios(cfg, args.reparsear)
    R.verificar_anclaje(cfg, rub)
    return 0


def _etapa_correr(cfg, args) -> int:
    from . import corpus as C, scoring as S

    from . import rubrica as R

    print(preparar_entorno_modelo(cfg))
    rub, criterios = _rubrica_y_criterios(cfg)

    # Antes de estimar nada: una rúbrica sin anclar produce calificaciones
    # sobre el objeto equivocado, y eso no se detecta después.
    anclaje = R.verificar_anclaje(cfg, rub)
    if anclaje.get("verificado") and anclaje["anclados"] < anclaje["total"]:
        faltan = anclaje["total"] - anclaje["anclados"]
        print(f"\n⚠️  {faltan} de {anclaje['total']} niveles no nombran el "
              f"objeto de estudio.")
        print("    En la corrida anterior eso produjo 67 de 122 calificaciones "
              "(55%) sobre")
        print("    tuits de otros países. Revisa la rúbrica antes de autorizar "
              "el gasto.")

    S.verificar_correspondencia(cfg.checkpoint, criterios,
                                forzar=args.forzar_rubrica_distinta, rubrica=rub)

    df = C.cargar(cfg)
    ids = C.ids_de_checkpoint(Path(args.ids_de)) if args.ids_de else None
    sub = C.anotar_payloads(cfg, C.seleccionar(cfg, df, len(criterios), ids=ids))

    alcance = args.alcance or cfg.alcance_recalificacion
    print()
    plan = S.estimar_recalificacion(cfg.checkpoint, sub, criterios, cfg, alcance)
    if plan["recalificar"] == 0:
        print("\n✅ Nada pendiente con este alcance: no hay gasto que autorizar.")
        return 0
    print()
    S.estimar_costo(cfg, sub, criterios, llamadas=plan["recalificar"])

    if not args.confirmar:
        print("\n⛔ Gasto no autorizado. Revisa la estimación y vuelve a ejecutar "
              "con --confirmar.")
        return 1

    print()
    resumen = asyncio.run(S.correr(cfg, sub, criterios, alcance=alcance,
                                   rubrica=rub))
    return 1 if resumen.get("abortada") else 0


def _etapa_auditar(cfg, args) -> int:
    from . import scoring as S
    ruta = Path(args.checkpoint) if args.checkpoint else cfg.checkpoint
    criterios = None
    if cfg.rubrica_json.exists():
        _, criterios = _rubrica_y_criterios(cfg)
    S.auditar(ruta, criterios)
    return 0


def _etapa_exportar(cfg, args) -> int:
    from . import corpus as C, export as E, scoring as S
    _, criterios = _rubrica_y_criterios(cfg)
    df = C.cargar(cfg)
    res = S.cargar_resultados(cfg.checkpoint)
    ancho, tidy = E.construir_salidas(cfg, df, criterios, res)
    E.exportar(cfg, ancho, tidy, len(df.columns), criterios)
    return 0


def _etapa_graficar(cfg, args) -> int:
    from . import corpus as C, viz as V
    _, criterios = _rubrica_y_criterios(cfg)
    df = C.cargar(cfg)
    tidy = V.calificaciones_desde_disco(cfg, criterios)
    datos = V.agregar(cfg, V.preparar(cfg, tidy, df), criterios)
    V.publicar(cfg, datos)
    return 0


ETAPAS = {
    "reparar": _etapa_reparar,
    "consolidar": _etapa_consolidar,
    "traducir": _etapa_traducir,
    "rubrica": _etapa_rubrica,
    "correr": _etapa_correr,
    "auditar": _etapa_auditar,
    "exportar": _etapa_exportar,
    "graficar": _etapa_graficar,
}


def main(argv: list[str] | None = None) -> int:
    configurar_consola()
    args = _parser().parse_args(argv)

    try:
        cfg = cargar_config(args.perfil, args.config)
    except ErrorDeConfiguracion as exc:
        print(f"⛔ {exc}", file=sys.stderr)
        return 2

    print(cfg.resumen())
    print()

    try:
        return ETAPAS[args.etapa](cfg, args)
    except InsumoAusente as exc:
        print(f"\n⛔ {exc}", file=sys.stderr)
        return 2
    except ErrorDeConfiguracion as exc:
        print(f"\n⛔ {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("\n⏸  Interrumpida. Lo escrito al checkpoint queda íntegro: "
              "reanudar continúa desde ahí.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
