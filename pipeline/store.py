"""Append-only stores: the local corpus each dataset accumulates.

Invariants (the same ones the original pipeline proved with its tests):

- **Append-only, ``keep="first"``**: a vacancy already in the store is never
  rewritten. ``captured_at`` is therefore the *first* time we saw it, which is
  what lets us archive rows by capture week/day and keep published files
  immutable.
- **Dedupe key per dataset**: ``url`` for jobspy (a job URL is the natural
  identity across sites), ``vacancy_id`` for SPE (``CODIGO_VACANTE`` is the
  real primary key; several distinct vacancies can share the provider URL).

Returns the number of *new* rows added, never the total.
"""

from __future__ import annotations

import warnings
from pathlib import Path

import pandas as pd

from . import env
from .schema import normalize

# Dedupe key per dataset.
DEDUPE_KEY = {"spe": "vacancy_id", "jobspy": "url"}


def count_rows(path: Path) -> int:
    """Row count of a parquet file, reading only its footer.

    **Do not replace with ``len(pd.read_parquet(...))``.** That spins up
    Arrow's thread-pooled scanner; if its reader is still alive at interpreter
    shutdown the process dies with ``terminate called without an active
    exception`` (SIGABRT, exit code 134) — the Arrow #34314 race. It killed a
    production capture on 2026-10-05: the run aborted at teardown, losing ~10
    minutes *and* the emission that never executed. ``read_metadata`` never
    creates that destructor chain and is ~20x faster.
    """
    import pyarrow.parquet as pq

    return pq.read_metadata(path).num_rows


def append(dataset: str, incoming: pd.DataFrame, path: Path | None = None) -> int:
    """Append new rows to a store; return how many rows were actually new.

    Rows whose dedupe key is already present are dropped *and* the stored
    version wins: re-observing a vacancy must never change its text or its
    ``captured_at``.
    """
    key = DEDUPE_KEY[dataset]
    path = path or env.store_path(dataset)
    incoming = normalize(incoming.copy())
    if len(incoming) == 0:
        return 0

    existing = pd.read_parquet(path) if path.exists() else normalize(pd.DataFrame())

    if len(existing):
        seen = set(existing[key].dropna())
        fresh = incoming[~incoming[key].isin(seen)].copy()
    else:
        fresh = incoming.copy()

    if len(fresh) == 0:
        return 0

    # Dedupe within the batch itself, first occurrence wins.
    fresh = fresh.drop_duplicates(subset=[key], keep="first")

    if len(existing):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", FutureWarning)
            merged = pd.concat([existing, fresh], ignore_index=True)
    else:
        merged = fresh

    # `keep="first"`: the row already in the store beats any re-observation.
    merged = merged.drop_duplicates(subset=[key], keep="first")
    env.write_store(merged, dataset, path=path)
    return len(fresh)
