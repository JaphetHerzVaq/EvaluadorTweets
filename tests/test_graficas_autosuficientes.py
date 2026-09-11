"""El HTML de gráficas no depende de la red.

El cuaderno cargaba ECharts desde cdnjs con una versión —5.5.1— que ese CDN no
sirve: devuelve 404. La página mostraba su mensaje de respaldo en vez de las
gráficas, y en Colab el fallo pasaba desapercibido entre las salidas de las
celdas. Se descubrió al abrir el HTML en un navegador, ya en local.

Embeber la biblioteca arregla eso y hace el artefacto autosuficiente: debe
poder abrirse dentro de dos años, sin conexión, sin que importe qué versiones
siga alojando un CDN de terceros.
"""

from __future__ import annotations

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PLANTILLA = RAIZ / "evaluador" / "plantilla_graficas.html"
BIBLIOTECA = RAIZ / "evaluador" / "echarts.min.js"


def test_la_biblioteca_viaja_con_el_paquete() -> None:
    assert BIBLIOTECA.exists(), f"falta {BIBLIOTECA.name}"
    assert BIBLIOTECA.stat().st_size > 500_000, "el archivo parece truncado"
    assert "echarts" in BIBLIOTECA.read_text(encoding="utf-8", errors="ignore")[:4000].lower()


def test_la_plantilla_no_pide_nada_a_la_red() -> None:
    html = PLANTILLA.read_text(encoding="utf-8")
    externos = re.findall(r'(?:src|href)\s*=\s*["\'](https?:)?//[^"\']+', html)
    assert not externos, (
        "La plantilla carga recursos externos y el HTML dejaría de funcionar sin "
        f"red o si el CDN cambia: {externos}"
    )


def test_el_html_generado_incluye_la_biblioteca() -> None:
    from evaluador.config import cargar_config
    from evaluador import viz as V

    cfg = cargar_config("piloto")
    datos = {"criterios": [], "fechas": [], "periodos": [], "idiomas": [],
             "agg": [], "volumen": [], "umbral_muestra": 100, "ventana": 7,
             "cortes": []}
    html = V.construir_html(cfg, datos)

    assert "__ECHARTS__" not in html, "el marcador quedó sin sustituir"
    assert len(html) > 900_000, "la biblioteca no se embebió"
    assert "cdnjs" not in html and "//cdn" not in html
