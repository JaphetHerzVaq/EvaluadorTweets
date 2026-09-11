"""La interfaz de línea de comandos: argumentos, compuertas y errores.

Ninguna prueba emite llamadas al modelo. Lo que se comprueba es que cada etapa
falle de forma accionable antes de gastar, no que califique bien.

Tareas 11.1 a 11.4 de migrar-a-proceso-local.
"""

from __future__ import annotations

import pytest

from evaluador.__main__ import ETAPAS, _parser, main


ETAPAS_ESPERADAS = {"reparar", "consolidar", "traducir", "rubrica",
                    "correr", "auditar", "exportar", "graficar"}


def test_estan_todas_las_etapas() -> None:
    assert set(ETAPAS) == ETAPAS_ESPERADAS


@pytest.mark.parametrize("etapa", sorted(ETAPAS_ESPERADAS))
def test_cada_etapa_se_puede_invocar(etapa: str) -> None:
    """El analizador acepta la etapa y la asocia a una función."""
    extra = {"consolidar": ["--base", "a.csv", "--extra", "b.csv"]}.get(etapa, [])
    args = _parser().parse_args([etapa, *extra])
    assert args.etapa == etapa
    assert callable(ETAPAS[args.etapa])


def test_correr_exige_confirmar_el_gasto() -> None:
    args = _parser().parse_args(["correr"])
    assert args.confirmar is False, "el gasto nunca debe autorizarse por omisión"


def test_los_alcances_del_cli_son_los_de_la_configuracion() -> None:
    from evaluador.config import ALCANCES

    accion = next(a for a in _parser()._subparsers._group_actions[0].choices["correr"]._actions
                  if a.dest == "alcance")
    assert set(accion.choices) == set(ALCANCES)


def test_perfil_inexistente_termina_con_codigo_de_error(capsys) -> None:
    codigo = main(["--perfil", "no_existe_este_perfil", "auditar"])
    assert codigo == 2
    salida = capsys.readouterr()
    assert "no está definido" in salida.err
    assert "piloto" in salida.err, "debe enumerar los disponibles"


def test_insumo_ausente_termina_con_codigo_de_error(tmp_path, capsys) -> None:
    codigo = main(["--perfil", "piloto", "auditar", str(tmp_path / "no_existe.jsonl")])
    assert codigo == 2
    salida = capsys.readouterr()
    assert "no_existe.jsonl" in salida.err, "debe nombrar la ruta esperada"
    assert "correr" in salida.err, "debe nombrar la etapa que lo produce"
