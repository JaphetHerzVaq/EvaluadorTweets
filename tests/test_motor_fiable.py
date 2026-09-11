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


# ──────────────────────────────────────────────────────────────────────────
#  Auditoría de checkpoint
# ──────────────────────────────────────────────────────────────────────────

def test_la_auditoria_no_modifica_el_checkpoint(tmp_path: Path) -> None:
    ckpt = _checkpoint(tmp_path, [("t1", "c1", "OK"), ("t2", "c1", "ERROR")])
    antes = ckpt.read_bytes()
    S.auditar(ckpt, escribir=lambda *a: None)
    assert ckpt.read_bytes() == antes


def test_la_auditoria_resuelve_repeticiones_por_ultimo_valido(tmp_path: Path) -> None:
    ckpt = _checkpoint(tmp_path, [
        ("t1", "c1", "ERROR"), ("t1", "c1", "ERROR"), ("t1", "c1", "OK"),
        ("t2", "c1", "ERROR"),
    ])
    r = S.auditar(ckpt, escribir=lambda *a: None)
    assert r["registros"] == 4
    assert r["pares"] == 2
    assert r["repetidos"] == 1
    assert r["max_repeticiones"] == 3
    assert r["resueltos"] == 1 and r["fallidos"] == 1


def test_la_auditoria_cuenta_las_lineas_ilegibles(tmp_path: Path) -> None:
    p = tmp_path / "c.jsonl"
    p.write_text(_registro("t1", "c1", "OK") + "\n{ rota\n", encoding="utf-8")
    r = S.auditar(p, escribir=lambda *a: None)
    assert r["ilegibles"] == 1 and r["registros"] == 1


def test_reanudar_rehusa_si_la_rubrica_no_corresponde(tmp_path: Path) -> None:
    ckpt = _checkpoint(tmp_path, [("t1", "criterio_viejo", "OK")])
    with pytest.raises(RuntimeError, match="criterio_viejo"):
        S.verificar_correspondencia(ckpt, CRITERIOS)
    S.verificar_correspondencia(ckpt, CRITERIOS, forzar=True)   # no lanza


def test_criterios_coincidentes_no_bloquean(tmp_path: Path) -> None:
    ckpt = _checkpoint(tmp_path, [("t1", "c1", "OK"), ("t1", "c2", "OK")])
    S.verificar_correspondencia(ckpt, CRITERIOS)


def test_estimar_recalificacion_por_alcance(tmp_path: Path) -> None:
    ckpt = _checkpoint(tmp_path, [
        ("t0", "c1", "OK"), ("t0", "c2", "NO_APLICABLE"),
        ("t1", "c1", "ERROR"), ("t1", "c2", "OK"),
    ])
    cfg = cargar_config("piloto")
    sub = _sub(2)
    esperado = {"fallidos": 1, "sin-nivel": 2, "todo": 4}
    for alcance, n in esperado.items():
        r = S.estimar_recalificacion(ckpt, sub, CRITERIOS, cfg, alcance,
                                     escribir=lambda *a: None)
        assert r["total"] == 4
        assert r["recalificar"] == n, f"alcance {alcance}"


# ──────────────────────────────────────────────────────────────────────────
#  Huella de contenido de la rúbrica
# ──────────────────────────────────────────────────────────────────────────

def _rubrica(descriptor_c1: str = "d" * 80) -> dict:
    import copy
    r = {"criterios": copy.deepcopy(CRITERIOS)}
    r["criterios"][0]["niveles"][0]["descriptor"] = descriptor_c1
    return r


def test_la_huella_ignora_lo_que_no_cambia_el_juicio() -> None:
    from evaluador.rubrica import huella
    a, b = _rubrica(), _rubrica()
    b["criterios"] = list(reversed(b["criterios"]))      # otro orden
    b["criterios"][0]["nombre"] = "otro nombre"          # otro título
    assert huella(a) == huella(b)


def test_la_huella_cambia_si_cambia_un_descriptor() -> None:
    from evaluador.rubrica import huella
    assert huella(_rubrica()) != huella(_rubrica("texto completamente distinto"))


def test_reanudar_rehusa_si_los_descriptores_cambiaron(tmp_path: Path) -> None:
    """El caso que el cotejo de slugs no ve: mismo nombre, otro contenido.

    Ocurrió al anclar la rúbrica a México — tres slugs cambiaron y el cuarto
    no, aunque sus descriptores sí. Sin esto, ese criterio habría recuperado
    calificaciones de la rúbrica anterior como si fueran de la vigente.
    """
    ckpt = _checkpoint(tmp_path, [("t1", "c1", "OK")])
    vieja, nueva = _rubrica(), _rubrica("los descriptores fueron reescritos")

    S.registrar_huella(ckpt, vieja)
    S.verificar_correspondencia(ckpt, CRITERIOS, rubrica=vieja)   # no lanza

    with pytest.raises(RuntimeError, match="otra versión de la rúbrica"):
        S.verificar_correspondencia(ckpt, CRITERIOS, rubrica=nueva)

    S.verificar_correspondencia(ckpt, CRITERIOS, rubrica=nueva, forzar=True)


def test_sin_huella_registrada_no_bloquea(tmp_path: Path) -> None:
    """Un checkpoint anterior a esta comprobación se sigue pudiendo reanudar."""
    ckpt = _checkpoint(tmp_path, [("t1", "c1", "OK")])
    S.verificar_correspondencia(ckpt, CRITERIOS, rubrica=_rubrica())


# ──────────────────────────────────────────────────────────────────────────
#  Respaldo por llamada directa
# ──────────────────────────────────────────────────────────────────────────

class _Resp:
    """Respuesta mínima del cliente de google-genai."""

    def __init__(self, text=None, motivo=None):
        self.text = text
        self.candidates = [type("C", (), {"finish_reason": None})()]
        self.prompt_feedback = (
            type("F", (), {"block_reason": type("B", (), {"name": motivo})()})()
            if motivo else None)


def _fila():
    return {"id": "t1", "_payload": "p", "contexto_incompleto": ""}


def test_el_respaldo_recupera_lo_que_adk_no_resolvio(monkeypatch) -> None:
    """59% de los fallos reales eran esto: ADK no devolvía estado y la llamada
    directa sí respondía, con la misma instrucción y el mismo esquema."""
    monkeypatch.setattr(S, "_llamar_directo", lambda *a, **k: _Resp(
        text=json.dumps({"aplicable": True, "nivel": "1", "justificacion": "x"})))

    cfg = cargar_config("piloto")
    regs = asyncio.run(S.rescatar_faltantes(
        cfg, S.Validador(CRITERIOS), _fila(),
        {c["slug"]: c for c in CRITERIOS}, ["c1"], "t1"))

    assert len(regs) == 1
    assert regs[0]["estado"] == "OK"
    assert regs[0]["nivel"] == "1"
    assert regs[0]["puntaje"] == 1.0
    assert "respaldo directo" in regs[0]["detalle"]


def test_el_respaldo_expone_el_motivo_del_bloqueo(monkeypatch) -> None:
    """ADK se traga el block_reason; la vía directa lo entrega."""
    monkeypatch.setattr(S, "_llamar_directo",
                        lambda *a, **k: _Resp(motivo="PROHIBITED_CONTENT"))

    cfg = cargar_config("piloto")
    regs = asyncio.run(S.rescatar_faltantes(
        cfg, S.Validador(CRITERIOS), _fila(),
        {c["slug"]: c for c in CRITERIOS}, ["c1"], "t1"))

    assert regs[0]["estado"] == "BLOQUEADO"
    assert "PROHIBITED_CONTENT" in regs[0]["detalle"]


def test_un_par_bloqueado_no_se_reintenta(tmp_path: Path) -> None:
    """Es una decisión del proveedor sobre ese texto, no un fallo pasajero:
    reintentarlo en cada reanudación es gasto garantizado sin resultado."""
    ckpt = _checkpoint(tmp_path, [("t1", "c1", "BLOQUEADO"), ("t2", "c1", "ERROR")])
    hechas = S.claves_completadas(ckpt, "fallidos")
    assert ("t1", "c1") in hechas, "BLOQUEADO es terminal"
    assert ("t2", "c1") not in hechas, "ERROR sí se reintenta"


def test_el_alcance_todo_sigue_recalificando_los_bloqueados(tmp_path: Path) -> None:
    ckpt = _checkpoint(tmp_path, [("t1", "c1", "BLOQUEADO")])
    assert S.claves_completadas(ckpt, "todo") == set()


def test_un_fallo_del_respaldo_no_pierde_la_fila(monkeypatch) -> None:
    def explota(*a, **k):
        raise RuntimeError("503 UNAVAILABLE")

    monkeypatch.setattr(S, "_llamar_directo", explota)
    cfg = cargar_config("piloto")
    regs = asyncio.run(S.rescatar_faltantes(
        cfg, S.Validador(CRITERIOS), _fila(),
        {c["slug"]: c for c in CRITERIOS}, ["c1"], "t1"))

    assert len(regs) == 1
    assert regs[0]["estado"] == "ERROR_SERVIDOR"
    assert regs[0]["tweet_id"] == "t1"


def test_no_se_tira_lo_que_adk_si_devolvio(monkeypatch) -> None:
    """El bug del rescate: con 4 criterios pendientes, ADK devolvía 2 y los 2
    buenos se descartaban junto con la excepción. Se escribieron 31 pares de 56.
    """
    intentos = {"n": 0}

    async def parcial(runner, payload, claves):
        # Siempre devuelve c1 y nunca c2: sin acumulación, c1 se perdería.
        intentos["n"] += 1
        return {"cal_c1": {"aplicable": True, "nivel": "1", "justificacion": "x"}} \
            if "cal_c1" in claves else {}

    async def rescate(cfg, validador, fila, porslug, faltantes, tid):
        return [{"tweet_id": tid, "slug": s, "aplicable": False, "nivel": None,
                 "puntaje": None, "justificacion": "", "estado": "BLOQUEADO",
                 "detalle": "PROHIBITED_CONTENT", "contexto_incompleto": ""}
                for s in faltantes]

    monkeypatch.setattr(S, "evaluar_payload", parcial)
    monkeypatch.setattr(S, "rescatar_faltantes", rescate)

    cfg = cargar_config("piloto")
    sem = asyncio.Semaphore(1)
    regs = asyncio.run(S._evaluar_fila(
        cfg, S.Validador(CRITERIOS), object(), _fila(), ["c1", "c2"], sem,
        {c["slug"]: c for c in CRITERIOS}))

    por_slug = {r["slug"]: r for r in regs}
    assert len(regs) == 2, "deben salir registros para los dos criterios"
    assert por_slug["c1"]["estado"] == "OK", "lo que ADK sí devolvió se conserva"
    assert por_slug["c1"]["nivel"] == "1"
    assert por_slug["c2"]["estado"] == "BLOQUEADO", "lo que faltó pasa al respaldo"


def test_el_reintento_solo_persigue_lo_que_falta(monkeypatch) -> None:
    pedidos = []

    async def observa(runner, payload, claves):
        pedidos.append(sorted(claves))
        if len(pedidos) == 1:
            return {"cal_c1": {"aplicable": True, "nivel": "1", "justificacion": "x"}}
        return {"cal_c2": {"aplicable": True, "nivel": "0", "justificacion": "y"}}

    monkeypatch.setattr(S, "evaluar_payload", observa)
    cfg = cargar_config("piloto")
    cfg.max_intentos = 3
    regs = asyncio.run(S._evaluar_fila(
        cfg, S.Validador(CRITERIOS), object(), _fila(), ["c1", "c2"],
        asyncio.Semaphore(1), {c["slug"]: c for c in CRITERIOS}))

    assert pedidos[0] == ["cal_c1", "cal_c2"]
    assert pedidos[1] == ["cal_c2"], f"el reintento pidió de más: {pedidos[1]}"
    assert all(r["estado"] == "OK" for r in regs)
