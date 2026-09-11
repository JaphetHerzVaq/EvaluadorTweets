"""Toda referencia entre módulos se resuelve al importar, no al ejecutar.

Esta es la prueba que justifica el cambio entero.

La corrida analizada produjo 15,384 registros de fallo con un único detalle:
``name 'evaluar_payload' is not defined``. La función se definía en la celda 22
del cuaderno y se usaba en la celda 25; nada declaraba esa dependencia ni la
verificaba. Cuando la celda 22 salió del espacio de nombres a media sesión,
cada llamada murió sin tocar la red, se reintentó cinco veces con retroceso
exponencial y se escribió al checkpoint como fallo permanente. Diecinueve
corridas sanas y después el corte.

En un paquete eso es estructuralmente imposible: ``from .adk import
ejecutar_agente`` revienta al importar si el símbolo no existe. Estas pruebas
lo comprueban en vez de confiar en que así sea.

Corresponde a las tareas 6.5 y 2.5, y al requisito «Resolución de dependencias
en tiempo de importación» de local-execution.
"""

from __future__ import annotations

import ast
import importlib
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
PAQUETE = RAIZ / "evaluador"

MODULOS = sorted(p.stem for p in PAQUETE.glob("*.py") if p.stem != "__init__")


def test_todos_los_modulos_importan() -> None:
    """Sin credencial en el entorno: importar no debe requerir red ni secretos."""
    for nombre in MODULOS:
        importlib.import_module(f"evaluador.{nombre}")


def _importaciones_internas(archivo: Path) -> list[tuple[str, str, int]]:
    """(modulo_origen, simbolo, linea) de cada `from .X import Y` del paquete."""
    arbol = ast.parse(archivo.read_text(encoding="utf-8"), filename=str(archivo))
    fuera = []
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.ImportFrom) and nodo.level == 1 and nodo.module:
            for alias in nodo.names:
                fuera.append((nodo.module, alias.name, nodo.lineno))
    return fuera


def test_cada_simbolo_importado_existe_en_su_origen() -> None:
    """El equivalente exacto del fallo de la corrida 20, comprobado estáticamente."""
    faltantes: list[str] = []
    for archivo in sorted(PAQUETE.glob("*.py")):
        for origen, simbolo, linea in _importaciones_internas(archivo):
            modulo = importlib.import_module(f"evaluador.{origen}")
            if not hasattr(modulo, simbolo):
                faltantes.append(
                    f"{archivo.relative_to(RAIZ)}:{linea} importa '{simbolo}' "
                    f"de '{origen}', que no lo define"
                )
    assert not faltantes, "Símbolos inexistentes:\n  " + "\n  ".join(faltantes)


def test_evaluar_payload_es_alcanzable_desde_el_motor() -> None:
    """El símbolo concreto que rompió la corrida real.

    En el cuaderno vivía en una celda distinta de la que lo usaba. Aquí debe
    estar en el mismo módulo que el motor, o importado explícitamente por él.
    """
    from evaluador import scoring

    assert callable(scoring.evaluar_payload)
    assert callable(scoring._evaluar_fila)
    assert callable(scoring.correr)


def test_un_simbolo_inexistente_rompe_al_importar(tmp_path: Path) -> None:
    """Comprueba el mecanismo, no sólo su resultado: si alguien escribe una
    importación rota, el proceso NO arranca."""
    paquete = tmp_path / "paquete_roto"
    paquete.mkdir()
    (paquete / "__init__.py").write_text("", encoding="utf-8")
    (paquete / "origen.py").write_text("def existe():\n    return 1\n", encoding="utf-8")
    (paquete / "consumidor.py").write_text(
        "from .origen import no_existe\n", encoding="utf-8"
    )

    sys.path.insert(0, str(tmp_path))
    try:
        with pytest.raises(ImportError):
            importlib.import_module("paquete_roto.consumidor")
    finally:
        sys.path.remove(str(tmp_path))
        for m in [k for k in sys.modules if k.startswith("paquete_roto")]:
            del sys.modules[m]


def test_todo_atributo_de_config_usado_existe() -> None:
    """El análogo en tiempo de ejecución de la prueba de importación.

    Un `from .x import y` roto falla al importar, pero `cfg.parametro_viejo`
    no falla hasta que esa línea se ejecuta — que puede ser a mitad de una
    corrida de pago. Ocurrió de verdad durante este traslado: al renombrar
    `concurrencia` por `llamadas_simultaneas`, `estimar_costo` se quedó con la
    referencia vieja y las 39 pruebas siguieron pasando, porque ninguna llegaba
    a esa línea. Lo destapó el primer uso real de la línea de comandos.
    """
    from evaluador.config import Config

    campos = set(Config.__dataclass_fields__)
    metodos = {n for n in dir(Config) if not n.startswith("__")}
    conocidos = campos | metodos

    malos: list[str] = []
    for archivo in sorted(PAQUETE.glob("*.py")):
        arbol = ast.parse(archivo.read_text(encoding="utf-8"), filename=str(archivo))
        for nodo in ast.walk(arbol):
            if (isinstance(nodo, ast.Attribute)
                    and isinstance(nodo.value, ast.Name)
                    and nodo.value.id == "cfg"
                    and nodo.attr not in conocidos):
                malos.append(
                    f"{archivo.relative_to(RAIZ)}:{nodo.lineno} usa "
                    f"cfg.{nodo.attr}, que Config no define"
                )
    assert not malos, "Atributos inexistentes de Config:\n  " + "\n  ".join(malos)
