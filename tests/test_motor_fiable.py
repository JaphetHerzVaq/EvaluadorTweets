"""Los arreglos del motor de corrida, probados sin tocar la red.

Cada prueba corresponde a un defecto que costó dinero real en la corrida
analizada (`checkpoint (7).jsonl`, 27,748 registros, 15,384 fallos idénticos
por un `NameError`).

Tareas 8.12 a 8.14 y 9.3 / 9.4 de migrar-a-proceso-local.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pandas as pd
import pytest

from evaluador import scoring as S
from evaluador.config import ESTADOS_RESULTADO, cargar_config


# ──────────────────────────────────────────────────────────────────────────
#  Utilidades
# ──────────────────────────────────────────────────────────────────────────

def _registro(tid: str, slug: str, estado: str) -> str:
    return json.dumps({"tweet_id": tid, "slug": slug, "estado": estado,
                       "aplicable": estado == "OK", "nivel": "3" if estado == "OK" else None,
                       "puntaje": 3.0 if estado == "OK" else None,
                       "justificacion": "x", "detalle": "",
                       "contexto_incompleto": ""}, ensure_ascii=False)


def _checkpoint(tmp_path: Path, filas: list[tuple[str, str, str]]) -> Path:
    p = tmp_path / "ckpt.jsonl"
    p.write_text("\n".join(_registro(*f) for f in filas) + "\n", encoding="utf-8")
    return p


# ──────────────────────────────────────────────────────────────────────────
#  Clasificación de fallos
# ──────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("exc", [
    NameError("name 'evaluar_payload' is not defined"),
    AttributeError("'NoneType' object has no attribute 'text'"),
    ImportError("cannot import name 'x'"),
    TypeError("unsupported operand"),
    RuntimeError("No API key was provided"),
    RuntimeError("PERMISSION_DENIED"),
])
def test_fallos_estructurales_se_reconocen(exc: Exception) -> None:
    """El NameError de la corrida real entra aquí: no debe reintentarse."""
    assert S.es_estructural(exc)
    assert S.motivo_fallo(exc) == "PERMANENTE"


@pytest.mark.parametrize("exc,motivo", [
    (RuntimeError("429 RESOURCE_EXHAUSTED"), "LIMITE_TASA"),
    (RuntimeError("503 UNAVAILABLE"), "ERROR_SERVIDOR"),
    (RuntimeError("blocked by safety filter"), "BLOQUEADO"),
    (asyncio.TimeoutError(), "TIEMPO_AGOTADO"),
    (S.ResultadoParcial(["a", "b"]), "SIN_RESPUESTA"),
])
def test_fallos_no_estructurales_se_clasifican(exc: Exception, motivo: str) -> None:
    assert not S.es_estructural(exc)
    assert S.motivo_fallo(exc) == motivo


def test_resultado_parcial_nombra_los_criterios_ausentes() -> None:
    exc = S.ResultadoParcial(["rubrica_2_estetica", "rubrica_4_violencia"])
    assert exc.faltantes == ["rubrica_2_estetica", "rubrica_4_violencia"]
    assert "rubrica_2_estetica" in str(exc)


# ──────────────────────────────────────────────────────────────────────────
#  Reanudación: un fallo ya no queda cementado
# ──────────────────────────────────────────────────────────────────────────

def test_reanudar_recalifica_los_fallos(tmp_path: Path) -> None:
    """El defecto que congeló 2,540 pares: un fallo contaba como trabajo hecho."""
    ckpt = _checkpoint(tmp_path, [
        ("t1", "c1", "OK"),
        ("t2", "c1", "NO_APLICABLE"),
        ("t3", "c1", "ERROR"),
        ("t4", "c1", "SIN_RESPUESTA"),
        ("t5", "c1", "PERMANENTE"),
    ])
    hechas = S.claves_completadas(ckpt, "fallidos")
    assert ("t1", "c1") in hechas, "un OK es trabajo terminado"
    assert ("t2", "c1") in hechas, "NO_APLICABLE es un resultado, no un fallo"
    for tid in ("t3", "t4", "t5"):
        assert (tid, "c1") not in hechas, f"{tid} debe recalificarse"


def test_alcance_sin_nivel_recalifica_los_no_aplicables(tmp_path: Path) -> None:
    ckpt = _checkpoint(tmp_path, [
        ("t1", "c1", "OK"),
        ("t2", "c1", "NO_APLICABLE"),
        ("t3", "c1", "ERROR"),
    ])
    hechas = S.claves_completadas(ckpt, "sin-nivel")
    assert hechas == {("t1", "c1")}


def test_alcance_todo_ignora_el_checkpoint(tmp_path: Path) -> None:
    ckpt = _checkpoint(tmp_path, [("t1", "c1", "OK"), ("t2", "c1", "NO_APLICABLE")])
    assert S.claves_completadas(ckpt, "todo") == set()


def test_un_par_reparado_cuenta_como_hecho(tmp_path: Path) -> None:
    """ERROR seguido de OK: el par quedó resuelto y no se vuelve a pagar."""
    ckpt = _checkpoint(tmp_path, [("t1", "c1", "ERROR"), ("t1", "c1", "OK")])
    assert ("t1", "c1") in S.claves_completadas(ckpt, "fallidos")


def test_un_resultado_valido_no_lo_pisa_un_fallo_posterior(tmp_path: Path) -> None:
    """OK seguido de ERROR: gana el OK, no el último escrito."""
    ckpt = _checkpoint(tmp_path, [("t1", "c1", "OK"), ("t1", "c1", "ERROR")])
    assert ("t1", "c1") in S.claves_completadas(ckpt, "fallidos")

    res = S.cargar_resultados(ckpt)
    fila = res[(res.tweet_id == "t1") & (res.slug == "c1")].iloc[0]
    assert fila["estado"] == "OK"


def test_par_sin_ningun_resultado_conserva_su_diagnostico(tmp_path: Path) -> None:
    ckpt = _checkpoint(tmp_path, [("t1", "c1", "ERROR"), ("t1", "c1", "TIEMPO_AGOTADO")])
    res = S.cargar_resultados(ckpt)
    assert len(res) == 1
    assert res.iloc[0]["estado"] == "TIEMPO_AGOTADO"


def test_lineas_ilegibles_no_rompen_la_lectura(tmp_path: Path) -> None:
    p = tmp_path / "ckpt.jsonl"
    p.write_text(_registro("t1", "c1", "OK") + "\n{ truncada a media lin\n"
                 + _registro("t2", "c1", "OK") + "\n", encoding="utf-8")
    assert len(S.claves_completadas(p, "fallidos")) == 2
    assert len(S.cargar_resultados(p)) == 2


# ──────────────────────────────────────────────────────────────────────────
#  Concurrencia declarada
# ──────────────────────────────────────────────────────────────────────────

def test_las_filas_en_vuelo_se_derivan_del_limite_de_llamadas() -> None:
    cfg = cargar_config("piloto")
    for n in (1, 2, 3, 4, 8):
        filas = cfg.filas_en_vuelo(n)
        assert filas * n <= cfg.llamadas_simultaneas, (
            f"con {n} criterios se emitirían {filas * n} peticiones, "
            f"por encima del límite {cfg.llamadas_simultaneas}"
        )


def test_una_rubrica_enorme_no_baja_de_una_fila() -> None:
    cfg = cargar_config("piloto")
    assert cfg.filas_en_vuelo(cfg.llamadas_simultaneas * 10) == 1


# ──────────────────────────────────────────────────────────────────────────
#  Reintento acotado
# ──────────────────────────────────────────────────────────────────────────

def test_el_reintento_http_tiene_tope_y_ruido() -> None:
    """El cuaderno usaba exp_base=7 sin max_delay: esperas de 343 s."""
    from evaluador.adk import opciones_reintento

    cfg = cargar_config("piloto")
    ro = opciones_reintento(cfg)
    assert ro.exp_base == 2, "base 7 produce 1, 7, 49, 343 segundos"
    assert ro.max_delay is not None, "sin tope, una espera puede durar minutos"
    assert ro.max_delay <= 120
    assert ro.jitter, "sin ruido, todas las llamadas reintentan a la vez"

    mayor = ro.initial_delay * (ro.exp_base ** (ro.attempts - 1))
    assert min(mayor, ro.max_delay) <= 120


def test_toda_llamada_tiene_tiempo_limite() -> None:
    cfg = cargar_config("piloto")
    assert cfg.timeout_llamada > 0
    assert cfg.timeout_llamada <= 600


# ──────────────────────────────────────────────────────────────────────────
#  Aborto estructural y cortacircuitos, con el motor real
# ──────────────────────────────────────────────────────────────────────────

CRITERIOS = [
    {"slug": "c1", "id_criterio": "1", "nombre": "uno", "consigna": "x",
     "niveles": [{"etiqueta": "0", "puntos": 0.0, "descriptor": "d" * 80},
                 {"etiqueta": "1", "puntos": 1.0, "descriptor": "e" * 80}],
     "escala_numerica": True, "etiquetas_validas": ["0", "1"], "puntos_validos": [0.0, 1.0]},
    {"slug": "c2", "id_criterio": "2", "nombre": "dos", "consigna": "y",
     "niveles": [{"etiqueta": "0", "puntos": 0.0, "descriptor": "f" * 80},
                 {"etiqueta": "1", "puntos": 1.0, "descriptor": "g" * 80}],
     "escala_numerica": True, "etiquetas_validas": ["0", "1"], "puntos_validos": [0.0, 1.0]},
]


def _sub(n: int) -> pd.DataFrame:
    return pd.DataFrame([{"id": f"t{i}", "_payload": "p", "contexto_incompleto": ""}
                         for i in range(n)])


def test_un_error_de_programacion_aborta_y_no_escribe_fallos(tmp_path: Path, monkeypatch) -> None:
    """El escenario exacto de la corrida 20, reproducido.

    Con el motor del cuaderno esto habría escrito un registro ERROR por cada
    par y los habría dejado cementados. Aquí aborta sin escribir nada.
    """
    async def explota(*a, **k):
        raise NameError("name 'evaluar_payload' is not defined")

    monkeypatch.setattr(S, "evaluar_payload", explota)
    monkeypatch.setattr(S, "construir_equipo", lambda *a, **k: (object(), []))
    monkeypatch.setattr(S, "verificar_aislamiento", lambda *a, **k: None)
    monkeypatch.setattr(S, "InMemoryRunner", lambda **k: object())

    cfg = cargar_config("piloto")
    ckpt = tmp_path / "abortada.jsonl"

    with pytest.raises(S.FalloEstructural) as info:
        asyncio.run(S.correr(cfg, _sub(50), CRITERIOS, ruta=ckpt,
                             escribir=lambda *a: None))

    assert "evaluar_payload" in str(info.value)
    escritos = ckpt.read_text(encoding="utf-8").strip() if ckpt.exists() else ""
    assert not escritos, "un error de programación no es dato sobre los tuits"


def test_el_cortacircuitos_detiene_una_racha(tmp_path: Path, monkeypatch) -> None:
    async def transitorio(*a, **k):
        raise RuntimeError("503 UNAVAILABLE")

    monkeypatch.setattr(S, "evaluar_payload", transitorio)
    monkeypatch.setattr(S, "construir_equipo", lambda *a, **k: (object(), []))
    monkeypatch.setattr(S, "verificar_aislamiento", lambda *a, **k: None)
    monkeypatch.setattr(S, "InMemoryRunner", lambda **k: object())

    cfg = cargar_config("piloto")
    cfg.max_intentos = 1          # sin esperas: la prueba no debe tardar
    cfg.fallos_consecutivos_max = 5
    ckpt = tmp_path / "racha.jsonl"

    res = asyncio.run(S.correr(cfg, _sub(200), CRITERIOS, ruta=ckpt,
                               escribir=lambda *a: None))

    assert res["abortada"], "una racha larga de fallos debe abortar"
    assert res["ok"] == 0
    # Se detuvo pronto: no procesó las 200 filas.
    assert res["fallidas"] < 200 * len(CRITERIOS)
    assert "consecutivas" in res["motivo_aborto"]


def test_los_resultados_previos_al_aborto_sobreviven(tmp_path: Path, monkeypatch) -> None:
    ckpt = tmp_path / "previo.jsonl"
    ckpt.write_text(_registro("t0", "c1", "OK") + "\n", encoding="utf-8")

    async def explota(*a, **k):
        raise NameError("boom")

    monkeypatch.setattr(S, "evaluar_payload", explota)
    monkeypatch.setattr(S, "construir_equipo", lambda *a, **k: (object(), []))
    monkeypatch.setattr(S, "verificar_aislamiento", lambda *a, **k: None)
    monkeypatch.setattr(S, "InMemoryRunner", lambda **k: object())

    cfg = cargar_config("piloto")
    with pytest.raises(S.FalloEstructural):
        asyncio.run(S.correr(cfg, _sub(10), CRITERIOS, ruta=ckpt,
                             escribir=lambda *a: None))

    assert ("t0", "c1") in S.claves_completadas(ckpt, "fallidos")
