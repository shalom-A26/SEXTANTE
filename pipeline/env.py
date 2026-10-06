"""Environment and paths shared by the whole pipeline.

Centralizes:
- The repository root and the ``data/`` layout.
- Local ``.env`` loading (``HF_TOKEN`` lives there, gitignored) without
  printing values. Exported variables win over the file, so
  ``HF_TOKEN=hf_x python -m pipeline ...`` on the command line takes
  precedence.
- Numeric coercion of the salary columns, so stores and parquet files agree
  on types regardless of which source produced the rows.
"""

from __future__ import annotations

import os
from pathlib import Path

import pandas as pd

from . import USER_AGENT  # sources reference env.USER_AGENT
from .schema import COLUMNS, NUMERIC_COLUMNS, empty, normalize

# Repository root (pipeline/ -> root).
ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
STORE_DIR = DATA / "store"          # local append-only stores (rebuildable)
EMIT_DIR = DATA / "emitido"         # emitted dataset directory (build artifact)

# Published-count baseline written by `pipeline pull`: it is what lets
# `pipeline emit` report how many rows are genuinely new (the total always
# "looks like it grows").
BASELINE = DATA / "_published.json"

# Datasets published to Hugging Face: one folder under data/ per dataset.
DATASETS = ("spe", "jobspy")


def store_path(dataset: str) -> Path:
    """Local store path for a dataset: data/store/<dataset>.parquet."""
    if dataset not in DATASETS:
        raise ValueError(f"unknown dataset: {dataset!r} (expected one of {DATASETS})")
    return STORE_DIR / f"{dataset}.parquet"


def load_local_env(root: Path | None = None) -> None:
    """Complete the environment from a local ``.env`` if present, quietly.

    Only adds keys that are absent; never prints or logs a value. An
    unreadable ``.env`` must not break a capture run, so I/O errors are
    swallowed (the run then proceeds without a token and whoever needs one
    sees the real 401).
    """
    path = (root or ROOT) / ".env"
    if not path.is_file():
        return
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def coerce_types(df: pd.DataFrame) -> pd.DataFrame:
    """Force the canonical dtypes: salary columns numeric, the rest objects.

    Keeps parquet bytes reproducible: the same logical content must always
    serialize identically, or Hugging Face re-uploads every file on every run.
    """
    df = normalize(df.copy())
    for col in NUMERIC_COLUMNS:
        df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")
    for col in COLUMNS:
        if col in NUMERIC_COLUMNS:
            continue
        series = df[col]
        df[col] = series.astype(object).where(series.notna(), None)
    return df


def read_store(dataset: str) -> pd.DataFrame:
    """Load a local store (canonical schema), or an empty frame if absent."""
    path = store_path(dataset)
    if not path.exists():
        return empty()
    return pd.read_parquet(path)


def write_store(df: pd.DataFrame, dataset: str, path: Path | None = None) -> Path:
    """Write a store with canonical, stable types."""
    path = path or store_path(dataset)
    path.parent.mkdir(parents=True, exist_ok=True)
    coerce_types(df).to_parquet(path, index=False)
    return path
