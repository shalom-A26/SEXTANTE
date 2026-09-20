"""Colector de vacantes de LinkedIn (y otros sitios de JobSpy) a DataFrame canónico.

JobSpy agrega vacantes de varios portales en un DataFrame normalizado; este
módulo convierte ese DataFrame al esquema canónico de SEXTANTE (17 columnas).
"""

from __future__ import annotations

from datetime import date, datetime
from urllib.parse import urlparse

import pandas as pd

from src.extraccion.esquema import normalizar

# Valores de job_type de JobSpy -> texto canónico.
TIPO_CONTRATO_JOBTYPE = {
    "fulltime": "Tiempo completo",
    "parttime": "Medio tiempo",
    "contract": "Contrato temporal",
    "internship": "Prácticas",
}


def _id_desde_url(url: str | None) -> str | None:
    if not url:
        return None
    p = urlparse(url)
    base = p.path.rstrip("/").rsplit("/", 1)[-1]
    return base or None


def _parsear_ubicacion(loc: str | None) -> tuple[str | None, str | None, str | None]:
    """Divide 'Ciudad, Departamento/Pais, Colombia' en (ciudad, departamento, pais)."""
    if not loc:
        return None, None, None
    partes = [s.strip() for s in loc.split(",") if s.strip()]
    if not partes:
        return None, None, None
    pais = partes[-1]
    if len(partes) == 1:
        return (None, None, pais)
    ciudad = partes[0]
    departamento = partes[1] if len(partes) >= 3 else None
    if departamento and departamento.lower() == "colombia":
        departamento = None
    return ciudad, departamento, pais


def _salario_texto(min_a, max_a, currency, interval) -> str | None:
    if pd.isna(min_a) and pd.isna(max_a):
        return None
    texto = ""
    if currency and not pd.isna(currency):
        texto += f"{currency} "
    if not pd.isna(min_a) and not pd.isna(max_a):
        texto += f"{min_a:,.0f} - {max_a:,.0f}"
    elif not pd.isna(min_a):
        texto += f"desde {min_a:,.0f}"
    elif not pd.isna(max_a):
        texto += f"hasta {max_a:,.0f}"
    if interval and not pd.isna(interval):
        texto += f" ({interval})"
    return texto


def _fecha_captura() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def scrape_linkedin(
    busqueda: str = "analista",
    ubicacion: str = "Colombia",
    resultados: int = 25,
) -> pd.DataFrame:
    """Extrae vacantes de LinkedIn vía JobSpy y las mapea al esquema canónico."""
    from jobspy import scrape_jobs  # import diferido: dependencia opcional

    df = scrape_jobs(
        site_name=["linkedin"],
        search_term=busqueda,
        location=ubicacion,
        results_wanted=resultados,
    )

    if len(df) == 0:
        return normalizar(pd.DataFrame())

    out = pd.DataFrame()
    out["id_vacante"] = df["job_url"].map(_id_desde_url)
    out["portal"] = "linkedin"
    out["url"] = df["job_url"]
    out["titulo"] = df["title"]
    out["empresa"] = df["company"]

    ubic = df["location"].map(_parsear_ubicacion)
    out["ciudad"] = [u[0] for u in ubic]
    out["departamento"] = [u[1] for u in ubic]

    out["fecha_publicacion"] = df["date_posted"].astype(str)
    out["descripcion"] = df["description"]

    out["salario_texto"] = [
        _salario_texto(r.min_amount, r.max_amount, r.currency, r.interval)
        for _, r in df.iterrows()
    ]
    out["salario_min"] = [str(v) if not pd.isna(v) else None for v in df["min_amount"]]
    out["salario_max"] = [str(v) if not pd.isna(v) else None for v in df["max_amount"]]

    out["tipo_contrato"] = df["job_type"].map(TIPO_CONTRATO_JOBTYPE)
    out["modalidad"] = df["is_remote"].apply(
        lambda r: "Remoto" if r is True else None
    )
    out["nivel_educativo"] = None
    out["experiencia_texto"] = None
    out["fecha_captura"] = str(date.today())

    return normalizar(out)