"""Analysis-side text repair. Source rows on HF are never modified.

Part of the SPE export arrives double-encoded (UTF-8 bytes decoded as
Windows-1252/Latin-1: "TÃ©cnico" instead of "Técnico"). After accent
stripping those become tokens like "ta cnico" or "gestia3n" that pollute
TF-IDF, topics and segments, and hide ESCO matches.
"""

from __future__ import annotations

import re

import pandas as pd

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
