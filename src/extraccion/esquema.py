"""Esquema canónico de vacantes (contrato único de todas las fuentes).

Cada colector de src/extraccion/portales/ debe emitir un DataFrame con
exactamente estas columnas, en este orden. Cualquier campo no disponible
en la fuente se deja como None (NaN).
"""

from __future__ import annotations

from collections.abc import Iterable

import pandas as pd

# Columnas del esquema canónico, en el orden de salida.
COLUMNAS_ESQUEMA: list[str] = [
    "id_vacante",
    "portal",
    "url",
    "titulo",
    "empresa",
    "ciudad",
    "departamento",
    "fecha_publicacion",
    "descripcion",
    "salario_texto",
    "salario_min",
    "salario_max",
    "tipo_contrato",
    "modalidad",
    "nivel_educativo",
    "experiencia_texto",
    "fecha_captura",
]

# Tipos esperados por columna (para validación en {None, tipo}).
TIPO_COLUMNA = {
    "id_vacante": object,
    "portal": object,
    "url": object,
    "titulo": object,
    "empresa": object,
    "ciudad": object,
    "departamento": object,
    "fecha_publicacion": object,
    "descripcion": object,
    "salario_texto": object,
    "salario_min": object,
    "salario_max": object,
    "tipo_contrato": object,
    "modalidad": object,
    "nivel_educativo": object,
    "experiencia_texto": object,
    "fecha_captura": object,
}


def dataframe_vacio() -> pd.DataFrame:
    """DataFrame vacío con el esquema canónico ordenado."""
    return pd.DataFrame(columns=COLUMNAS_ESQUEMA)


def normalizar(df: pd.DataFrame) -> pd.DataFrame:
    """Reordena/rellena un DataFrame arbitrario hacia el esquema canónico.

    - Agrega columnas faltantes con NaN.
    - Descarta columnas sobrantes.
    - Reordena al orden canónico.
    """
    for col in COLUMNAS_ESQUEMA:
        if col not in df.columns:
            df[col] = None
    df = df[COLUMNAS_ESQUEMA]
    return df


def validar(df: pd.DataFrame) -> Iterable[str]:
    """Devuelve las columnas canónicas ausentes en el DataFrame (vacío si ok)."""
    return [col for col in COLUMNAS_ESQUEMA if col not in df.columns]