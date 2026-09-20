"""Portal SPE (Servicio Público de Empleo): exportador oficial de vacantes.

El buscador público del SPE (`https://www.buscadordeempleo.gov.co/`) expone
una API REST en `/backbue/v1` que permite generar, vía un job asíncrono, un
export CSV del total de vacantes registradas (el mismo botón "CSV (Se
exportan todas las vacantes)" de la interfaz web). Volumen observado:
~285.000 ofertas con descripción completa, nivel educativo, departamento,
rango salarial, tipo de contrato y experiencia en meses.

Este módulo:
  1. descarga el export CSV completo (mecanismo oficial del portal, 3
     peticiones: crear job, consultar estado, descargar);
  2. lo mapea al esquema canónico de 17 columnas (src/extraccion/esquema.py);
  3. lo guarda en data/raw/spe/vacantes_spe.parquet con deduplicación por
     CODIGO_VACANTE (ustedes la matrícula de la vacante, no por url: varias
     vacantes distintas pueden compartir la url del prestador).

Referencia: los campos brutos usan mayúsculas (CODIGO_VACANTE, TITULO_VACANTE,
DESCRIPCION_VACANTE, NIVEL_ESTUDIOS, RANGO_SALARIAL, NOMBRE_PRESTADOR,
DEPARTAMENTO, MUNICIPIO, TIPO_CONTRATO, URL_DETALLE_VACANTE,
CANTIDAD_VACANTES, CARGO, FECHA_PUBLICACION, FECHA_VENCIMIENTO,
SECTOR_ECONOMICO, TELETRABAJO, DISCAPACIDAD, MESES_EXPERIENCIA_CARGO,
HIDROCARBUROS, PLAZA_PRACTICA).
"""

from __future__ import annotations

import re
import time
import warnings
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests
from requests.exceptions import SSLError

from .. import base
from ..esquema import COLUMNAS_ESQUEMA, normalizar

API_SPE = "https://www.buscadordeempleo.gov.co/backbue/v1"
RUTA_SPE = base.RUTA_RAW / "spe"
RUTA_CSV_SPE = RUTA_SPE / "vacantes_spe_latest.csv"
RUTA_PARQUET_SPE = RUTA_SPE / "vacantes_spe.parquet"

# Intervalo (s) de espera entre reintentos del estado del job de export.
_POLL_DEMORA = 2.0


def _request(method: str, url: str, **kwargs) -> requests.Response:
    """GET/POST al SPE con User-Agent del proyecto.

    El certificado del sitio es intermitente (cadena CA local incompleta): se
    reenvía la petición con `verify=False` solo si la validación SSL falla.
    """
    headers = {"User-Agent": base.UA}
    headers.update(kwargs.pop("headers", {}) or {})
    try:
        return requests.request(method, url, headers=headers, timeout=(30, 300), **kwargs)
    except SSLError:
        warnings.warn("Validación SSL contra el SPE falló; reintentando sin verificar (sitio estatal público).")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=requests.packages.urllib3.exceptions.InsecureRequestWarning)
            return requests.request(method, url, headers=headers, timeout=(30, 300), verify=False, **kwargs)


def _get(url: str, **kwargs) -> requests.Response:
    return _request("GET", url, **kwargs)


def _post(url: str, **kwargs) -> requests.Response:
    return _request("POST", url, **kwargs)


def descargar_export_csv(ruta: Path = RUTA_CSV_SPE) -> Path:
    """Descarga el export CSV del total de vacantes del SPE (job asíncrono)."""
    ruta.parent.mkdir(parents=True, exist_ok=True)
    r = _post(f"{API_SPE}/vacantes/export/csv/async")
    r.raise_for_status()
    job_id = r.json().get("jobId")
    if not job_id:
        raise RuntimeError(f"El SPE no devolvió un jobId para el export: {r.text[:200]}")

    estado = None
    for _ in range(150):  # hasta ~5 min
        time.sleep(_POLL_DEMORA)
        s = _get(f"{API_SPE}/vacantes/export/csv/async/{job_id}/status")
        s.raise_for_status()
        estado = s.json().get("status")
        if estado in ("completed", "failed"):
            break
    if estado != "completed":
        raise RuntimeError(f"El export CSV del SPE falló (job {job_id}): {estado}")

    d = _get(f"{API_SPE}/vacantes/export/csv/async/{job_id}/download")
    d.raise_for_status()
    ruta.write_bytes(d.content)
    return ruta


def _parsear_salario(rango: object) -> tuple[object, object]:
    """Rango salarial del SPE ('$1.500.001 - $2.000.000', 'A Convenir', ...)
    a (salario_min, salario_max) numéricos en COP. Devuelve (None, None) si
    no es un rango numérico usable."""
    if not isinstance(rango, str):
        return (None, None)
    texto = rango.strip()
    if not texto or texto.lower() in ("a convenir", "menos del salario mínimo"):
        return (None, None)
    m = re.search(r"Mayor de \$([\d\.]+)", texto)
    if m:
        return (int(m.group(1).replace(".", "")), None)
    m = re.search(r"\$([\d\.]+)\s*-\s*\$([\d\.]+)", texto)
    if m:
        return (int(m.group(1).replace(".", "")), int(m.group(2).replace(".", "")))
    return (None, None)


def exportar_a_canonico(csv: Path, fecha_captura: str | None = None) -> pd.DataFrame:
    """Lee el export CSV del SPE y lo convierte al esquema canónico de 17 columnas."""
    bruto = pd.read_csv(csv, dtype=str, encoding="utf-8-sig", low_memory=False)
    captura = fecha_captura or datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    salarios = bruto["RANGO_SALARIAL"].map(_parsear_salario)
    salario_min = pd.array([s[0] for s in salarios], dtype="Int64")
    salario_max = pd.array([s[1] for s in salarios], dtype="Int64")

    experiencia = bruto["MESES_EXPERIENCIA_CARGO"].map(
        lambda v: f"{v} meses" if pd.notna(v) and str(v).strip() else None
    )
    teletrabajo = bruto["TELETRABAJO"].map(
        lambda v: "Teletrabajo" if pd.notna(v) and str(v).strip() == "1" else None
    )

    can = pd.DataFrame(
        {
            "id_vacante": "spe-" + bruto["CODIGO_VACANTE"].astype(str),
            "portal": "spe",
            "url": bruto["URL_DETALLE_VACANTE"],
            "titulo": bruto["TITULO_VACANTE"],
            "empresa": bruto["NOMBRE_PRESTADOR"],
            "ciudad": bruto["MUNICIPIO"],
            "departamento": bruto["DEPARTAMENTO"],
            "fecha_publicacion": bruto["FECHA_PUBLICACION"],
            "descripcion": bruto["DESCRIPCION_VACANTE"],
            "salario_texto": bruto["RANGO_SALARIAL"],
            "salario_min": salario_min,
            "salario_max": salario_max,
            "tipo_contrato": bruto["TIPO_CONTRATO"],
            "modalidad": teletrabajo,
            "nivel_educativo": bruto["NIVEL_ESTUDIOS"],
            "experiencia_texto": experiencia,
            "fecha_captura": captura,
        }
    )
    return normalizar(can)


def guardar_parquet(df: pd.DataFrame, ruta: Path = RUTA_PARQUET_SPE) -> int:
    """Adjunta las filas nuevas al store canónico (parquet) del SPE.

    Deduplica por id_vacante (CODIGO_VACANTE): es la clave primaria real del
    SPE; varias vacantes distintas pueden compartir url. Devuelve el número
    de registros nuevos incorporados.
    """
    df = normalizar(df.copy())
    ruta.parent.mkdir(parents=True, exist_ok=True)
    if ruta.exists():
        previo = pd.read_parquet(ruta, columns=COLUMNAS_ESQUEMA)
        df = pd.concat([previo, df], ignore_index=True)
    df = df.drop_duplicates(subset=["id_vacante"], keep="last")
    df = df.sort_values("fecha_publicacion", na_position="last").reset_index(drop=True)
    df.to_parquet(ruta, index=False)
    return len(df)


def extraer_spe(csv: Path | None = None, fecha_captura: str | None = None) -> int:
    """Orquesta la extracción del SPE y guarda el store canónico parquet.

    Devuelve el número de registros guardados. Si `csv` no se pasa, descarga
    el export completo del portal (mecanismo oficial de exportación).
    """
    base.crear_estructura_datos()
    csv_origen = csv or descargar_export_csv(RUTA_CSV_SPE)
    can = exportar_a_canonico(csv_origen, fecha_captura=fecha_captura)
    return guardar_parquet(can)