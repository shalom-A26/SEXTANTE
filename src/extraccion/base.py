"""Infraestructura común para los colectores de src/extraccion/portales/.

Concentra:
- User-Agent identificable del proyecto (criterio ético de la sonda).
- Sesión HTTP con reintentos y respeto a robots/ToS.
- Guardado incremental sobre data/raw/vacantes.csv con deduplicación
  y estampado de fecha_captura.
- Carga del `.env` local (`HF_TOKEN`), compartida con src/analisis/.
"""

from __future__ import annotations

import os
import shutil
import time
import warnings
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from .esquema import COLUMNAS_ESQUEMA, dataframe_vacio, normalizar

PROYECTO = "SEXTANTE-UTB-university-research"
UA = f"{PROYECTO}/1.0 (proyecto academico de analitica y mineria de datos; respeta robots.txt)"

# Ruta raíz del proyecto (sube de src/extraccion -> raíz).
RAIZ = Path(__file__).resolve().parent.parent.parent
RUTA_DATOS = RAIZ / "data"
RUTA_RAW = RUTA_DATOS / "raw"
RUTA_VACANTES = RUTA_RAW / "vacantes.csv"

# Intervalo mín./máx. de espera entre peticiones (throttling ético).
PAUSA_MIN = 1.0
PAUSA_MAX = 3.0


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, max=8))
def get(url: str, **kwargs) -> requests.Response:
    """GET con User-Agent del proyecto, reintentos con backoff y pausa ética."""
    time.sleep(PAUSA_MIN)
    headers = {"User-Agent": UA}
    headers.update(kwargs.pop("headers", {}) or {})
    return requests.get(url, headers=headers, timeout=30, **kwargs)


def cargar_entorno_local(raiz: Path | None = None) -> None:
    """Completa el entorno con un `.env` local si existe, sin imprimirlo.

    Guarda el token de Hugging Face (`HF_TOKEN`) fuera del control de versiones
    (`.env` está en `.gitignore`). Solo añade claves ausentes: lo que ya esté
    exportado tiene prioridad, así que `HF_TOKEN=hf_x python -m ...` manda
    sobre el archivo. Ningún valor se escribe en el log.

    Vive aquí, y no en `src/analisis/datos_hf.py`, porque lo necesitan tanto el
    análisis como el pipeline de captura: `sync_hf --pull` y `emitir_dataset
    --hf-upload` leen `HF_TOKEN` del entorno, y sin esto una captura manual
   recebía un 401 que se leía como "el repo no existe".
    """
    ruta = (raiz or RAIZ) / ".env"
    if not ruta.is_file():
        return
    try:
        lineas = ruta.read_text(encoding="utf-8").splitlines()
    except OSError:
        # Un `.env` ilegible no debe tumbar la captura: se sigue sin token y
        # quien lo necesite verá el 401 con su causa real.
        return
    for linea in lineas:
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        clave, _, valor = linea.partition("=")
        clave = clave.strip()
        valor = valor.strip().strip('"').strip("'")
        if clave and clave not in os.environ:
            os.environ[clave] = valor


def crear_estructura_datos() -> None:
    """Garantiza que existan data/raw/ y data/procesados/."""
    RUTA_RAW.mkdir(parents=True, exist_ok=True)
    (RUTA_DATOS / "procesados").mkdir(parents=True, exist_ok=True)
    (RUTA_DATOS / "snapshots").mkdir(parents=True, exist_ok=True)


def cargar_existentes(ruta: Path = RUTA_VACANTES) -> pd.DataFrame:
    """Carga el corpus acumulado, o un DataFrame vacío con el esquema canónico."""
    if ruta.exists():
        df = pd.read_csv(ruta, dtype=str)
        col_extra = [c for c in df.columns if c not in COLUMNAS_ESQUEMA]
        if col_extra:
            df = df.drop(columns=col_extra)
        return df
    return dataframe_vacio()


def _concat_canonico(*frames: pd.DataFrame) -> pd.DataFrame:
    """Concatena DataFrames canónicos ignorando el aviso de columnas todas-NaN
    (p. ej. campos aún sin capturar como nivel_educativo o experiencia_texto)."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", FutureWarning)
        return pd.concat(list(frames), ignore_index=True)


def guardar_lotes(df: pd.DataFrame, ruta: Path = RUTA_VACANTES) -> int:
    """Adjunta filas nuevas y elimina duplicados por url posteriormente.

    Una vacante ya presente nunca se reescribe: solo se agregan las filas cuya
    `url` no estaba antes. Es la misma semántica append-only que aplica al store
    del SPE (`portales/spe.guardar_parquet`), y por eso `fecha_captura` queda
    fijada a la primera observación.

    Devuelve el número de filas nuevas incorporadas.
    """
    crear_estructura_datos()
    df = normalizar(df.copy())
    existentes = cargar_existentes(ruta)
    if len(existentes):
        urls_previas = set(existentes["url"].dropna().unique())
        nuevos = df[~(df["url"].isin(urls_previas))].copy()
    else:
        nuevos = df.copy()

    if not len(nuevos):
        return 0

    nuevos = nuevos.set_index("url", drop=False)
    nuevos = nuevos[~nuevos.index.duplicated(keep="first")]
    nuevos = nuevos.reset_index(drop=True)

    if len(existentes):
        combinado = _concat_canonico(existentes, nuevos)
        combinado = combinado.drop_duplicates(subset=["url"], keep="last")
    else:
        combinado = nuevos
    combinado = normalizar(combinado)
    combinado.to_csv(ruta, index=False)
    return len(nuevos)


def resumen_fuente(portal: str, df: pd.DataFrame) -> None:
    """Imprime un reporte corto de lo capturado por una fuente."""
    if len(df) == 0:
        print(f"[{portal}] sin registros capturados")
        return
    con_desc = int(df["descripcion"].notna().sum())
    con_sal = int((df["salario_min"].notna() | df["salario_texto"].notna()).sum())
    fecha_min = df["fecha_publicacion"].dropna().min()
    fecha_max = df["fecha_publicacion"].dropna().max()
    print(
        f"[{portal}] {len(df)} filas | descripción: {con_desc} | "
        f"salario: {con_sal} | publicación: {fecha_min} → {fecha_max}"
    )


def guardar_snapshot(ruta_origen: Path, prefijo: str = "vacantes", subdir: str = "") -> Path:
    """Copia un store de data/raw/ a data/snapshots/ con marca de tiempo.

    Devuelve la ruta de la copia. Útil para la captura periódica: cada corrida
    deja un corte puntual ('instante de captura') de los datos crudos/canónicos.
    """
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    destino = (RUTA_DATOS / "snapshots" / subdir) if subdir else RUTA_DATOS / "snapshots"
    destino.mkdir(parents=True, exist_ok=True)
    copia = destino / f"{prefijo}_{ts}{ruta_origen.suffix}"
    shutil.copy2(ruta_origen, copia)
    return copia