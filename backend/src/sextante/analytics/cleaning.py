"""Analysis-side text repair. Source rows on HF are never modified.

Part of the SPE export arrives double-encoded (UTF-8 bytes decoded as
Windows-1252/Latin-1: "TÃ©cnico" instead of "Técnico"). After accent
stripping those become tokens like "ta cnico" or "gestia3n" that pollute
TF-IDF, topics and segments, and hide ESCO matches.
"""

from __future__ import annotations

import re
import unicodedata

import pandas as pd

# Canonical department names (SPE spelling). JobSpy boards use other forms:
# Indeed three-letter codes ("ANT", "VAC"), LinkedIn title case or English.
DEPARTMENTS = (
    "AMAZONAS", "ANTIOQUIA", "ARAUCA",
    "ARCHIPIÉLAGO DE SAN ANDRÉS, PROVIDENCIA Y SANTA CATALINA", "ATLÁNTICO",
    "BOGOTÁ, D.C.", "BOLÍVAR", "BOYACÁ", "CALDAS", "CAQUETÁ", "CASANARE", "CAUCA",
    "CESAR", "CHOCÓ", "CÓRDOBA", "CUNDINAMARCA", "GUAINÍA", "GUAVIARE", "HUILA",
    "LA GUAJIRA", "MAGDALENA", "META", "NARIÑO", "NORTE DE SANTANDER", "PUTUMAYO",
    "QUINDIO", "RISARALDA", "SANTANDER", "SUCRE", "TOLIMA", "VALLE DEL CAUCA",
    "VAUPÉS", "VICHADA",
)
DEPARTMENT_ALIASES = {
    "AMA": "AMAZONAS", "ANT": "ANTIOQUIA", "ARA": "ARAUCA", "ATL": "ATLÁNTICO",
    "BOL": "BOLÍVAR", "BOY": "BOYACÁ", "CAL": "CALDAS", "CAQ": "CAQUETÁ",
    "CAS": "CASANARE", "CAU": "CAUCA", "CES": "CESAR", "CHO": "CHOCÓ", "COR": "CÓRDOBA",
    "CUN": "CUNDINAMARCA", "GUA": "GUAINÍA", "GUV": "GUAVIARE", "HUI": "HUILA",
    "LAG": "LA GUAJIRA", "MAG": "MAGDALENA", "MET": "META", "NAR": "NARIÑO",
    "NSA": "NORTE DE SANTANDER", "PUT": "PUTUMAYO", "QUI": "QUINDIO", "RIS": "RISARALDA",
    "SAN": "SANTANDER", "SAP": "ARCHIPIÉLAGO DE SAN ANDRÉS, PROVIDENCIA Y SANTA CATALINA",
    "SUC": "SUCRE", "TOL": "TOLIMA", "VAC": "VALLE DEL CAUCA", "VAU": "VAUPÉS",
    "VID": "VICHADA", "DC": "BOGOTÁ, D.C.", "CAPITAL DISTRICT": "BOGOTÁ, D.C.",
    "BOGOTA": "BOGOTÁ, D.C.", "BOGOTA D.C.": "BOGOTÁ, D.C.", "SAN ANDRES": "ARCHIPIÉLAGO DE "
    "SAN ANDRÉS, PROVIDENCIA Y SANTA CATALINA",
}

TEXT_COLUMNS = ("title", "description", "company", "city", "department",
                "contract_type", "work_modality", "education_level", "experience_text")
_MOJIBAKE = re.compile(r"Ã[\x80-\xbf¡-ÿ]|â€|Â[\xa0-\xbf]")


def repair_mojibake(text: str) -> str:
    """Undo up to two rounds of UTF-8 → cp1252/latin-1 mis-decoding."""
    for _ in range(2):
        if not _MOJIBAKE.search(text):
            break
        for codec in ("cp1252", "latin-1"):
            try:
                text = text.encode(codec).decode("utf-8")
                break
            except (UnicodeEncodeError, UnicodeDecodeError):
                continue
        else:
            break
    return text


def _fold(text: str) -> str:
    """Upper-case and strip accents: 'Quindío' -> 'QUINDIO'."""
    decomposed = unicodedata.normalize("NFKD", text.strip().upper())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


_DEPARTMENT_KEYS = {_fold(name): name for name in DEPARTMENTS} | {
    _fold(alias): name for alias, name in DEPARTMENT_ALIASES.items()}


def normalize_departments(frame: pd.DataFrame) -> int:
    """Map department spellings onto the SPE names in place; return changed cells.

    Bogotá is its own department in SPE, while Indeed files it under
    Cundinamarca, so a Bogotá city wins over the department code. Unknown
    values (e.g. SPE's nationwide "VACANTES PARA TODO EL TERRITORIO") stay.
    """
    if "department" not in frame:
        return 0
    before = frame["department"].copy()
    folded = before.map(lambda value: _DEPARTMENT_KEYS.get(_fold(value))
                        if isinstance(value, str) else None)
    after = folded.fillna(before)
    if "city" in frame:
        bogota = frame["city"].map(lambda value: isinstance(value, str)
                                   and _fold(value).startswith("BOGOTA"))
        after = after.mask(bogota, "BOGOTÁ, D.C.")
    frame["department"] = after
    return int((before.fillna("") != after.fillna("")).sum())


def repair_frame(frame: pd.DataFrame) -> int:
    """Repair text columns in place; return how many cells changed."""
    changed = 0
    for column in TEXT_COLUMNS:
        if column not in frame:
            continue
        values = frame[column]
        mask = values.map(lambda value: isinstance(value, str) and bool(_MOJIBAKE.search(value)))
        if mask.any():
            fixed = values[mask].map(repair_mojibake)
            changed += int((fixed != values[mask]).sum())
            frame.loc[mask, column] = fixed
    return changed
