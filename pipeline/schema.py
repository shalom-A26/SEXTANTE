"""Canonical job-posting schema — the single contract of every source.

Each collector in ``pipeline.sources`` must emit a DataFrame with exactly
these columns in this order. Fields unavailable in a given source are left
as None (NaN).

The column names are English (renamed on 2026-10-05 from the original
Spanish schema when the HF dataset was re-partitioned under ``data/spe/`` and
``data/jobspy/``). The *values* of the data stay in Spanish: they describe
Colombian job postings.
"""

from __future__ import annotations

from collections.abc import Iterable

import pandas as pd

# Canonical columns, in output order.
COLUMNS: list[str] = [
    "vacancy_id",
    "source",
    "url",
    "title",
    "company",
    "city",
    "department",
    "published_at",
    "description",
    "salary_text",
    "salary_min",
    "salary_max",
    "contract_type",
    "work_modality",
    "education_level",
    "experience_text",
    "captured_at",
]

# Columns that must hold numbers (written as float64 for stable parquet bytes).
NUMERIC_COLUMNS = ("salary_min", "salary_max")

# Legacy (pre-2026-10-05) Spanish column names -> canonical English names.
# Used by the one-off HF migration to read the old weekly files.
LEGACY_RENAME = {
    "id_vacante": "vacancy_id",
    "portal": "source",
    "titulo": "title",
    "empresa": "company",
    "ciudad": "city",
    "departamento": "department",
    "fecha_publicacion": "published_at",
    "descripcion": "description",
    "salario_texto": "salary_text",
    "salario_min": "salary_min",
    "salario_max": "salary_max",
    "tipo_contrato": "contract_type",
    "modalidad": "work_modality",
    "nivel_educativo": "education_level",
    "experiencia_texto": "experience_text",
    "fecha_captura": "captured_at",
}


def empty() -> pd.DataFrame:
    """Empty DataFrame with the canonical schema, in order."""
    return pd.DataFrame(columns=COLUMNS)


def normalize(df: pd.DataFrame) -> pd.DataFrame:
    """Reshape an arbitrary DataFrame to the canonical schema.

    - Adds missing columns as None.
    - Drops extra columns (e.g. the legacy ``almacen`` column).
    - Reorders to the canonical order.
    """
    for col in COLUMNS:
        if col not in df.columns:
            df[col] = None
    return df[COLUMNS]


def validate(df: pd.DataFrame) -> Iterable[str]:
    """Return the canonical columns missing from the DataFrame (empty if ok)."""
    return [col for col in COLUMNS if col not in df.columns]
