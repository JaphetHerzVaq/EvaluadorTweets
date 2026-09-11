"""El paquete no debe depender de ningún entorno de cuaderno alojado.

Esta prueba existe porque la regresión es silenciosa: un `import nest_asyncio`
o un `from google.colab import files` añadido durante una depuración no rompe
nada hasta que alguien corre el pipeline en una máquina limpia. Verificarlo
una sola vez a mano no sirve; tiene que fallar sola.

Corresponde a las tareas 4.2 y 4.3 de migrar-a-proceso-local, y al requisito
«El paquete no depende de bibliotecas de entornos alojados» de local-execution.
"""

from __future__ import annotations

import ast
import tomllib
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PAQUETE = RAIZ / "evaluador"

# Lo que sólo tiene sentido dentro de un cuaderno alojado.
PROHIBIDOS = {
    "google.colab": "subida, descarga y montaje de almacenamiento propios de Colab",
    "nest_asyncio": "parche de reentrada del bucle de eventos; en local basta asyncio.run()",
    "IPython": "presentación incrustada en la sesión de un cuaderno",
    "ipywidgets": "controles interactivos de cuaderno",
    "google.colab.userdata": "gestor de secretos de Colab",
}


def _modulos_importados(archivo: Path) -> set[str]:
    arbol = ast.parse(archivo.read_text(encoding="utf-8"), filename=str(archivo))
    nombres: set[str] = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            nombres.update(alias.name for alias in nodo.names)
        elif isinstance(nodo, ast.ImportFrom):
            if nodo.module and nodo.level == 0:
                nombres.add(nodo.module)
    return nombres


def _archivos_del_paquete() -> list[Path]:
    return sorted(PAQUETE.rglob("*.py"))


def test_ningun_modulo_importa_entorno_alojado() -> None:
    infracciones: list[str] = []
    for archivo in _archivos_del_paquete():
        for importado in _modulos_importados(archivo):
            for prohibido, motivo in PROHIBIDOS.items():
                if importado == prohibido or importado.startswith(prohibido + "."):
                    infracciones.append(
                        f"{archivo.relative_to(RAIZ)} importa '{importado}' ({motivo})"
                    )
    assert not infracciones, (
        "El paquete debe correr como proceso local:\n  " + "\n  ".join(infracciones)
    )


def test_nest_asyncio_no_es_dependencia_declarada() -> None:
    fijadas = (RAIZ / "requirements.txt").read_text(encoding="utf-8")
    lineas = [
        l.strip() for l in fijadas.splitlines()
        if l.strip() and not l.strip().startswith("#")
    ]
    assert not any("nest" in l.lower() for l in lineas), (
        f"nest_asyncio no debe declararse en requirements.txt: {lineas}"
    )

    proyecto = tomllib.loads((RAIZ / "pyproject.toml").read_text(encoding="utf-8"))
    deps = proyecto["project"]["dependencies"]
    assert not any("nest" in d.lower() for d in deps), (
        f"nest_asyncio no debe declararse en pyproject.toml: {deps}"
    )


def test_nest_asyncio_no_esta_instalado_en_el_entorno() -> None:
    """Si estuviera instalado, un import accidental pasaría las pruebas de
    arriba en esta máquina y fallaría en otra."""
    import importlib.util

    assert importlib.util.find_spec("nest_asyncio") is None, (
        "nest_asyncio está instalado en el entorno virtual. No es dependencia "
        "del proyecto; su presencia permite que un import accidental pase "
        "desapercibido aquí y falle en una máquina limpia."
    )
