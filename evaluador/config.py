"""Carga de perfiles, parámetros y credencial.

Reemplaza la celda CONFIG del cuaderno. La diferencia que importa no es el
formato: es que un perfil queda registrado y se puede comparar entre
versiones, mientras que una celda editada a mano no deja rastro. El CONFIG
declaraba ``CHECKPOINT_PATH = "checkpoint.jsonl"`` mientras en disco había
``checkpoint_piloto.jsonl``, y nada lo delataba.
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

RUTA_CONFIG_POR_DEFECTO = "config.toml"
ARCHIVO_ENTORNO = ".env"


def configurar_consola() -> None:
    """Fuerza UTF-8 en la salida estándar.

    En Windows la consola usa cp1252 por defecto y cualquier escritura con un
    acento, una comilla angular o un carácter de caja levanta
    UnicodeEncodeError y mata el proceso. Todo el reporte de este paquete está
    en español, así que sin esto una corrida de horas puede morir al imprimir
    su propio avance.

    El cuaderno nunca lo necesitó: Colab es UTF-8 de extremo a extremo. Es un
    requisito que sólo aparece al bajar a proceso local en Windows.

    Activa además el volcado por líneas. Cuando la salida no va a una terminal
    —redirigida a un archivo, a una tarea en segundo plano, a un registro— Python
    almacena en búfer por bloques y no aparece nada hasta que el proceso
    termina. En una corrida de horas eso equivale a no tener reporte de avance:
    no hay forma de distinguir un proceso trabajando de uno colgado, que es
    justo lo que hay que poder distinguir.
    """
    import sys
    for flujo in (sys.stdout, sys.stderr):
        reconfigurar = getattr(flujo, "reconfigure", None)
        if reconfigurar is not None:
            try:
                reconfigurar(encoding="utf-8", errors="replace", line_buffering=True)
            except (ValueError, OSError):
                pass   # flujo redirigido a algo que no admite reconfiguración


class ErrorDeConfiguracion(RuntimeError):
    """Configuración ausente, mal formada o incoherente."""


class InsumoAusente(FileNotFoundError):
    """Falta un artefacto de entrada que otra etapa debía producir."""


def exigir_insumo(ruta: Path, descripcion: str, producido_por: str | None = None) -> Path:
    """Devuelve `ruta` si existe; si no, falla nombrando qué falta y quién lo genera.

    En el cuaderno, un archivo ausente disparaba la rama de subida interactiva
    y, fuera de Colab, eso producía ``ImportError: google.colab`` — un
    diagnóstico que manda a investigar el problema equivocado. Aquí el error
    dice la ruta esperada y la etapa que la produce.
    """
    if ruta.exists():
        return ruta
    mensaje = f"Falta {descripcion}.\n  Se esperaba en: {ruta}"
    if producido_por:
        mensaje += f"\n  Lo produce la etapa: {producido_por}"
    raise InsumoAusente(mensaje)


# ──────────────────────────────────────────────────────────────────────────
#  Períodos
# ──────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Periodo:
    nombre: str
    desde: date
    hasta: date | None          # None = período abierto, sólo el último

    def contiene(self, dia: date) -> bool:
        """Intervalo [desde, hasta): inferior inclusivo, superior exclusivo."""
        if dia < self.desde:
            return False
        return self.hasta is None or dia < self.hasta


def _fecha(valor: Any, campo: str, nombre: str) -> date | None:
    if valor is None:
        return None
    if isinstance(valor, date):
        return valor
    try:
        return date.fromisoformat(str(valor))
    except ValueError as exc:
        raise ErrorDeConfiguracion(
            f"'{campo}' del período «{nombre}» no es una fecha ISO (AAAA-MM-DD): {valor!r}"
        ) from exc


def validar_periodos(crudos: list[dict]) -> list[Periodo]:
    """Los períodos alimentan toda la visualización. Un solapamiento aquí se
    vuelve un tuit contado dos veces en las gráficas, y eso no se ve: se lee
    como señal."""
    if not crudos:
        raise ErrorDeConfiguracion(
            "No hay períodos declarados: la visualización no tendría nada que segmentar."
        )

    nombres = [p.get("nombre", "") for p in crudos]
    if any(not n for n in nombres):
        raise ErrorDeConfiguracion(
            "Todo período necesita 'nombre': es la etiqueta de las gráficas."
        )
    if len(set(nombres)) != len(nombres):
        raise ErrorDeConfiguracion(f"Nombres de período duplicados: {nombres}")

    periodos: list[Periodo] = []
    anterior_desde: date | None = None
    anterior_hasta: date | None = None

    for k, p in enumerate(crudos):
        nombre = p["nombre"]
        desde = _fecha(p.get("desde"), "desde", nombre)
        hasta = _fecha(p.get("hasta"), "hasta", nombre)

        if desde is None:
            raise ErrorDeConfiguracion(f"El período «{nombre}» no declara 'desde'.")
        if hasta is not None and hasta <= desde:
            raise ErrorDeConfiguracion(
                f"El período «{nombre}» termina antes de empezar: {desde} → {hasta}"
            )
        if hasta is None and k != len(crudos) - 1:
            raise ErrorDeConfiguracion(
                f"Sólo el último período puede quedar abierto, y «{nombre}» no lo es. "
                f"Declara su 'hasta'."
            )
        if anterior_desde is not None and desde < anterior_desde:
            raise ErrorDeConfiguracion(
                f"Los períodos no están ordenados: «{nombre}» empieza en {desde}, "
                f"antes que «{crudos[k-1]['nombre']}» ({anterior_desde}). "
                f"Decláralos en orden cronológico."
            )
        if anterior_hasta is not None and desde < anterior_hasta:
            raise ErrorDeConfiguracion(
                f"Los períodos se solapan: «{crudos[k-1]['nombre']}» llega hasta "
                f"{anterior_hasta} y «{nombre}» empieza en {desde}. Con límites "
                f"[desde, hasta) el corte compartido debe ser la MISMA fecha."
            )

        periodos.append(Periodo(nombre=nombre, desde=desde, hasta=hasta))
        anterior_desde, anterior_hasta = desde, hasta

    return periodos


# ──────────────────────────────────────────────────────────────────────────
#  Configuración
# ──────────────────────────────────────────────────────────────────────────

@dataclass
class Config:
    """Parámetros efectivos de una corrida: [comun] con el perfil encima."""

    perfil: str
    descripcion: str

    # Modelo
    modelo: str
    temperatura: float
    presupuesto_razonamiento: int
    modelo_calibracion: str

    # Credencial
    nombre_variable_clave: str

    # Corpus
    corpus_fuente_xlsx: Path
    corpus_reparado: Path
    corpus_traducido: Path
    forzar_reparacion: bool
    col_id: str
    col_texto: str
    col_traduccion: str
    col_lang: str

    # Selección
    n_muestra: int                      # 0 = corpus completo
    semilla: int
    excluir_retweets: bool
    excluir_quotes: bool
    filtro_lang: list[str]
    filtro_tipo_query: list[str]

    # Rúbrica
    rubrica_pdf: Path
    rubrica_json: Path

    # Traducción
    modelo_traduccion: str
    checkpoint_traduccion: Path
    concurrencia_traduccion: int
    retraducir_existentes: bool

    # Calificación
    justificacion_max_palabras: int

    # Corrida
    concurrencia: int
    reciclar_cada: int
    max_intentos: int
    timeout_llamada: float
    checkpoint: Path
    alcance_recalificacion: str         # "fallidos" | "sin-nivel" | "todo"

    # Salida
    salida_ancho: Path
    salida_tidy: Path
    salida_html: Path

    # Visualización
    zona_horaria: str
    escala_niveles: str
    niveles_ausencia: Any
    umbral_muestra_pequena: int
    umbral_cobertura_diaria: int
    ventana_suavizado: int

    # Umbrales de calidad
    umbral_concentracion: float
    umbral_no_aplicable: float
    umbral_estabilidad: float

    # Derivados
    periodos: list[Periodo] = field(default_factory=list)
    precios: dict[str, tuple[float, float]] = field(default_factory=dict)
    raiz: Path = Path(".")

    @property
    def corpus_a_calificar(self) -> Path:
        """El traducido si existe; si no, el reparado. La traducción es de
        apoyo para consumo humano, no el objeto evaluado."""
        return self.corpus_traducido if self.corpus_traducido.exists() else self.corpus_reparado

    def precio_de(self, modelo: str) -> tuple[float, float]:
        if modelo not in self.precios:
            raise ErrorDeConfiguracion(
                f"No hay precio declarado para '{modelo}'. "
                f"Declarados: {sorted(self.precios)}. Añádelo en [precios] de config.toml."
            )
        return self.precios[modelo]

    def resumen(self) -> str:
        """Lo que determina gasto y destino, para que quede en el registro de
        la corrida y no haya que adivinarlo después."""
        muestra = "completa" if self.n_muestra == 0 else f"{self.n_muestra:,}"
        razona = "apagado" if self.presupuesto_razonamiento == 0 else str(self.presupuesto_razonamiento)
        return (
            f"perfil «{self.perfil}» · {self.descripcion}\n"
            f"  modelo       {self.modelo} · temp={self.temperatura} · razonamiento={razona}\n"
            f"  selección    muestra={muestra} · semilla={self.semilla}\n"
            f"  corrida      concurrencia={self.concurrencia} · max_intentos={self.max_intentos}\n"
            f"  corpus       {self.corpus_a_calificar}\n"
            f"  rúbrica      {self.rubrica_json}\n"
            f"  checkpoint   {self.checkpoint}\n"
            f"  salidas      {self.salida_ancho} · {self.salida_tidy} · {self.salida_html}\n"
            f"  períodos     {len(self.periodos)} · día en {self.zona_horaria} · "
            f"{' | '.join(p.nombre for p in self.periodos)}"
        )


# Alcances de recalificación. El orden es de menor a mayor gasto, y 'fallidos'
# es el defecto por ser el único que no repite trabajo ya pagado.
ALCANCES = {
    "fallidos":  "sólo los pares con estado de fallo (ERROR, SIN_RESPUESTA)",
    "sin-nivel": "los de fallo más los declarados no aplicables: todo lo que quedó sin nivel",
    "todo":      "la selección entera, sin consultar los estados del checkpoint",
}

#: Estados que cuentan como resultado terminado. NO_APLICABLE es el modelo
#: respondiendo que el criterio no aplica, no un fallo: confundirlo con error
#: dispararía la recalificación del 74% del corpus sin razón.
ESTADOS_RESULTADO = frozenset({"OK", "NO_APLICABLE"})

#: Estados de resultado que además traen un nivel asignado.
ESTADOS_CON_NIVEL = frozenset({"OK"})


def estados_a_conservar(alcance: str) -> frozenset[str]:
    """Estados cuyos pares NO se recalifican bajo este alcance."""
    if alcance == "fallidos":
        return ESTADOS_RESULTADO
    if alcance == "sin-nivel":
        return ESTADOS_CON_NIVEL
    if alcance == "todo":
        return frozenset()
    raise ErrorDeConfiguracion(
        f"Alcance de recalificación desconocido: {alcance!r}. "
        f"Válidos: {sorted(ALCANCES)}"
    )


_CLAVES_RUTA = {
    "corpus_fuente_xlsx", "corpus_reparado", "corpus_traducido",
    "rubrica_pdf", "rubrica_json", "checkpoint", "checkpoint_traduccion",
    "salida_ancho", "salida_tidy", "salida_html",
}


def cargar_config(perfil: str | None = None,
                  ruta: str | Path = RUTA_CONFIG_POR_DEFECTO) -> Config:
    """Funde [comun] con el perfil pedido y devuelve los parámetros efectivos."""
    p = Path(ruta)
    if not p.exists():
        raise ErrorDeConfiguracion(
            f"No existe el archivo de configuración '{p}'. "
            f"Se esperaba en la raíz del proyecto."
        )

    with p.open("rb") as fh:
        crudo = tomllib.load(fh)

    perfiles = crudo.get("perfiles") or {}
    if not perfiles:
        raise ErrorDeConfiguracion(f"'{p}' no declara ningún perfil en [perfiles].")

    elegido = perfil or crudo.get("perfil_por_defecto")
    if elegido is None:
        raise ErrorDeConfiguracion(
            f"No se indicó perfil y '{p}' no declara 'perfil_por_defecto'. "
            f"Disponibles: {sorted(perfiles)}"
        )
    if elegido not in perfiles:
        raise ErrorDeConfiguracion(
            f"El perfil «{elegido}» no está definido en '{p}'. "
            f"Disponibles: {sorted(perfiles)}"
        )

    valores: dict[str, Any] = dict(crudo.get("comun") or {})
    valores.update(perfiles[elegido])

    # 'checkpoint' sólo existe en los perfiles: una corrida nunca debe heredar
    # el checkpoint de otra sin declararlo.
    if "checkpoint" not in valores:
        raise ErrorDeConfiguracion(
            f"El perfil «{elegido}» no declara 'checkpoint'. Cada perfil debe "
            f"tener el suyo: un piloto no puede contaminar la corrida completa."
        )

    raiz = p.resolve().parent
    for clave in _CLAVES_RUTA:
        if clave in valores:
            valores[clave] = raiz / str(valores[clave])

    precios = {m: (float(v[0]), float(v[1])) for m, v in (crudo.get("precios") or {}).items()}
    periodos = validar_periodos(list(crudo.get("periodos") or []))

    valores.setdefault("descripcion", "")
    validos = set(Config.__dataclass_fields__) - {"perfil", "periodos", "precios", "raiz"}
    desconocidos = sorted(set(valores) - validos)
    if desconocidos:
        raise ErrorDeConfiguracion(
            f"Parámetros no reconocidos en '{p}' (perfil «{elegido}»): {desconocidos}. "
            f"Un nombre mal escrito se ignoraría en silencio y la corrida usaría el "
            f"valor por defecto sin avisar."
        )

    faltantes = sorted(validos - set(valores))
    if faltantes:
        raise ErrorDeConfiguracion(
            f"Faltan parámetros en '{p}' (perfil «{elegido}»): {faltantes}"
        )

    alcance = valores.get("alcance_recalificacion")
    if alcance not in ALCANCES:
        raise ErrorDeConfiguracion(
            f"'alcance_recalificacion' no válido en '{p}' (perfil «{elegido}»): "
            f"{alcance!r}.\n" +
            "\n".join(f"  «{k}» → {v}" for k, v in ALCANCES.items())
        )

    return Config(perfil=elegido, periodos=periodos, precios=precios, raiz=raiz, **valores)


# ──────────────────────────────────────────────────────────────────────────
#  Credencial
# ──────────────────────────────────────────────────────────────────────────

def _leer_archivo_entorno(nombre: str, raiz: Path) -> str | None:
    """Lee NOMBRE=valor de .env. Sin dependencia externa: el formato que
    necesitamos es una línea."""
    p = raiz / ARCHIVO_ENTORNO
    if not p.exists():
        return None
    for linea in p.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        clave, _, valor = linea.partition("=")
        if clave.strip() == nombre:
            return valor.strip().strip('"').strip("'")
    return None


def cargar_clave(cfg: Config) -> str:
    """Devuelve la clave de API. Nunca la imprime ni la registra.

    Orden: variable de entorno, luego .env. La variable gana para que una
    corrida puntual pueda usar otra credencial sin editar archivos.
    """
    nombre = cfg.nombre_variable_clave
    clave = os.environ.get(nombre) or _leer_archivo_entorno(nombre, cfg.raiz)

    if not clave or not clave.strip():
        raise ErrorDeConfiguracion(
            f"No hay credencial disponible.\n"
            f"  Defínela como variable de entorno {nombre}, o\n"
            f"  escríbela en '{cfg.raiz / ARCHIVO_ENTORNO}' como {nombre}=tu_clave\n"
            f"  (ese archivo está excluido por .gitignore; ver .env.example).\n"
            f"  Se obtiene en https://aistudio.google.com/apikey"
        )
    return clave.strip()


def preparar_entorno_modelo(cfg: Config) -> str:
    """Publica la credencial donde google-genai la busca y devuelve un reporte
    sin el valor.

    En ADK el cliente de google-genai se construye SIN argumentos
    (google/adk/models/google_llm.py → api_client): sólo lee variables de
    entorno, así que pasar api_key= o vertexai= al objeto Gemini no tiene
    efecto. Verificado en ADK 1.26: ninguno de los dos es campo del modelo.
    """
    clave = cargar_clave(cfg)
    os.environ[cfg.nombre_variable_clave] = clave
    os.environ["GOOGLE_API_KEY"] = clave
    os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "False"   # AI Studio, no Vertex AI
    return (f"credencial cargada desde '{cfg.nombre_variable_clave}' "
            f"({len(clave)} caracteres, no se imprime el valor) · backend AI Studio")
