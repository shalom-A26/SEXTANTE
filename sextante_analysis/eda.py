"""Descriptive metrics for the canonical vacancy corpus."""

from __future__ import annotations

from typing import Any

import pandas as pd


def summarize(frame: pd.DataFrame) -> dict[str, Any]:
    """Return dataset-level coverage and distribution summaries as JSON data."""
    if frame.empty:
        return {"rows": 0, "columns": list(frame.columns)}
    description = frame.get("description", pd.Series(index=frame.index, dtype=object))
    text = description.fillna("").astype(str)
    summary: dict[str, Any] = {
        "rows": int(len(frame)),
        "columns": list(frame.columns),
        "missing_fraction": {
            column: float(frame[column].isna().mean()) for column in frame.columns
        },
        "description": {
            "nonempty_rows": int(text.str.strip().ne("").sum()),
            "empty_rows": int(text.str.strip().eq("").sum()),
            "median_characters": float(text.str.len().median()),
            "p95_characters": float(text.str.len().quantile(0.95)),
        },
    }
    for column in ("source", "department", "work_modality", "contract_type", "education_level"):
        if column in frame:
            summary[f"top_{column}"] = {
                str(key): int(value)
                for key, value in frame[column].fillna("unknown").value_counts().head(20).items()
            }
    for column in ("salary_min", "salary_max"):
        if column in frame:
            values = pd.to_numeric(frame[column], errors="coerce").dropna()
            if not values.empty:
                summary[column] = {
                    "count": int(values.size),
                    "median_cop": float(values.median()),
                    "p10_cop": float(values.quantile(0.10)),
                    "p90_cop": float(values.quantile(0.90)),
                }
    if "captured_at" in frame:
        captured = pd.to_datetime(frame["captured_at"], errors="coerce")
        summary["captured_at"] = {
            "valid_rows": int(captured.notna().sum()),
            "min": captured.min().isoformat() if captured.notna().any() else None,
            "max": captured.max().isoformat() if captured.notna().any() else None,
        }
    if "published_at" in frame:
        published = pd.to_datetime(frame["published_at"], errors="coerce", dayfirst=True)
        summary["published_at_parseable_rows"] = int(published.notna().sum())
    return summary
