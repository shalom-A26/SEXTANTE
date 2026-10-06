"""SPE (Servicio Público de Empleo): the official Colombian job-board export.

The public search at ``https://www.buscadordeempleo.gov.co/`` exposes a REST
API under ``/backbue/v1`` that can generate, through an asynchronous job, a
CSV export of *all* registered vacancies — the same "CSV (export all
vacancies)" button of the web UI. Observed volume: ~285k postings per capture
with full description, education level, department, salary band, contract
type and experience in months.

Flow (3 HTTP requests per capture, the portal's official mechanism — no
scraping):

1. ``POST /vacantes/export/csv/async`` -> ``{jobId}`` (202 queued)
2. ``GET  /vacantes/export/csv/async/{jobId}/status`` -> polling until completed
3. ``GET  /vacantes/export/csv/async/{jobId}/download`` -> CSV (~415 MB, UTF-8 BOM)

The CSV is mapped to the canonical schema and appended to the ``spe`` store,
deduped by ``CODIGO_VACANTE`` (``vacancy_id``): several distinct vacancies can
share the provider's URL, so URL is not the key here.

Raw column reference (uppercase): CODIGO_VACANTE, TITULO_VACANTE,
DESCRIPCION_VACANTE, NIVEL_ESTUDIOS, RANGO_SALARIAL, NOMBRE_PRESTADOR,
DEPARTAMENTO, MUNICIPIO, TIPO_CONTRATO, URL_DETALLE_VACANTE, FECHA_PUBLICACION,
SECTOR_ECONOMICO, TELETRABAJO, MESES_EXPERIENCIA_CARGO.
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

from .. import env, store
from ..schema import normalize

API = "https://www.buscadordeempleo.gov.co/backbue/v1"
LATEST_CSV = env.STORE_DIR / "spe_latest.csv"

# Seconds between status polls of the export job.
_POLL_DELAY = 2.0

# The SPE certificate chain is incomplete, so TLS validation fails
# systematically (not intermittently): the export poll makes ~130 requests per
# run and each one repeated the verify-then-fail handshake before retrying
# without verification (100-132 warnings, minutes lost). The first SSLError
# remembers it and the rest of the run goes straight to verify=False. The
# posture is unchanged: every request ended up unverified anyway. This is a
# public state site, read-only.
_VERIFY_SSL = True
_SSL_WARNING = (
    "TLS validation against the SPE failed; skipping verification for the "
    "rest of the run (public state site, incomplete CA chain)."
)


def _request(method: str, url: str, **kwargs) -> requests.Response:
    global _VERIFY_SSL
    headers = {"User-Agent": env.USER_AGENT}
    headers.update(kwargs.pop("headers", {}) or {})
    if not _VERIFY_SSL:
        return _request_unverified(method, url, headers, kwargs)
    try:
        return requests.request(method, url, headers=headers, timeout=(30, 300), **kwargs)
    except SSLError:
        _VERIFY_SSL = False
        warnings.warn(_SSL_WARNING)
        return _request_unverified(method, url, headers, kwargs)


def _request_unverified(method, url, headers, kwargs) -> requests.Response:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=requests.packages.urllib3.exceptions.InsecureRequestWarning)
        return requests.request(method, url, headers=headers, timeout=(30, 300), verify=False, **kwargs)


def _get(url: str, **kwargs) -> requests.Response:
    return _request("GET", url, **kwargs)


def _post(url: str, **kwargs) -> requests.Response:
    return _request("POST", url, **kwargs)


def download_export_csv(path: Path = LATEST_CSV) -> Path:
    """Download the full-vacancies CSV export (official asynchronous job)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    r = _post(f"{API}/vacantes/export/csv/async")
    r.raise_for_status()
    job_id = r.json().get("jobId")
    if not job_id:
        raise RuntimeError(f"SPE returned no jobId for the export: {r.text[:200]}")

    status = None
    for _ in range(150):  # up to ~5 min
        time.sleep(_POLL_DELAY)
        s = _get(f"{API}/vacantes/export/csv/async/{job_id}/status")
        s.raise_for_status()
        status = s.json().get("status")
        if status in ("completed", "failed"):
            break
    if status != "completed":
        raise RuntimeError(f"SPE CSV export failed (job {job_id}): {status}")

    d = _get(f"{API}/vacantes/export/csv/async/{job_id}/download")
    d.raise_for_status()
    path.write_bytes(d.content)
    return path


def _parse_salary(band: object) -> tuple[object, object]:
    """SPE salary band ('$1.500.001 - $2.000.000', 'A Convenir', ...) into a
    (salary_min, salary_max) numeric pair in COP. Non-numeric bands give
    (None, None)."""
    if not isinstance(band, str):
        return (None, None)
    text = band.strip()
    if not text or text.lower() in ("a convenir", "menos del salario mínimo"):
        return (None, None)
    m = re.search(r"Mayor de \$([\d\.]+)", text)
    if m:
        return (int(m.group(1).replace(".", "")), None)
    m = re.search(r"\$([\d\.]+)\s*-\s*\$([\d\.]+)", text)
    if m:
        return (int(m.group(1).replace(".", "")), int(m.group(2).replace(".", "")))
    return (None, None)


def to_canonical(csv: Path, captured_at: str | None = None) -> pd.DataFrame:
    """Read the SPE CSV export and map it to the canonical 17-column schema."""
    raw = pd.read_csv(csv, dtype=str, encoding="utf-8-sig", low_memory=False)
    stamp = captured_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    salaries = raw["RANGO_SALARIAL"].map(_parse_salary)
    salary_min = pd.array([s[0] for s in salaries], dtype="Int64")
    salary_max = pd.array([s[1] for s in salaries], dtype="Int64")

    experience = raw["MESES_EXPERIENCIA_CARGO"].map(
        lambda v: f"{v} meses" if pd.notna(v) and str(v).strip() else None
    )
    telework = raw["TELETRABAJO"].map(
        lambda v: "Teletrabajo" if pd.notna(v) and str(v).strip() == "1" else None
    )

    out = pd.DataFrame(
        {
            "vacancy_id": "spe-" + raw["CODIGO_VACANTE"].astype(str),
            "source": "spe",
            "url": raw["URL_DETALLE_VACANTE"],
            "title": raw["TITULO_VACANTE"],
            "company": raw["NOMBRE_PRESTADOR"],
            "city": raw["MUNICIPIO"],
            "department": raw["DEPARTAMENTO"],
            "published_at": raw["FECHA_PUBLICACION"],
            "description": raw["DESCRIPCION_VACANTE"],
            "salary_text": raw["RANGO_SALARIAL"],
            "salary_min": salary_min,
            "salary_max": salary_max,
            "contract_type": raw["TIPO_CONTRATO"],
            "work_modality": telework,
            "education_level": raw["NIVEL_ESTUDIOS"],
            "experience_text": experience,
            "captured_at": stamp,
        }
    )
    return normalize(out)


def capture(csv: Path | None = None) -> int:
    """Run a full SPE capture: download (unless ``csv`` given), map, append.

    Returns the number of vacancies added to the store. Uses the official
    export mechanism — 3 requests for the whole corpus.
    """
    origin = csv or download_export_csv(LATEST_CSV)
    frame = to_canonical(origin)
    added = store.append("spe", frame)
    path = env.store_path("spe")
    # count_rows and not pd.read_parquet: see store.count_rows (exit 134).
    total = store.count_rows(path) if path.exists() else 0
    print(f"[spe] {added} new rows (store: {total:,} total)")
    return added
