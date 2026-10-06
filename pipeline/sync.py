"""Sync with Hugging Face — the pipeline's persistent memory.

Hugging Face is the hard drive of the capture: every GitHub Actions run
*pulls* the published corpus first, appends what's new, and pushes back. The
runner is ephemeral; without this step there is no accumulation.

Layout pulled (see ``pipeline.emit`` for the layout's rationale):

    data/spe/week-*.parquet     -> store data/store/spe.parquet
    data/jobspy/day-*.parquet   -> store data/store/jobspy.parquet

The pull also records the published row counts in ``data/_published.json``,
which is what lets ``pipeline emit`` report *genuinely new* rows instead of
the total (the total always looks like it grows).
"""

from __future__ import annotations

import json
import os
import warnings
from datetime import datetime, timezone

import pandas as pd

from . import env
from .schema import COLUMNS, empty


def _list_partition_files(repo: str, dataset: str, token: str | None) -> list[str]:
    """Paths of ``data/<dataset>/*`` in the repo, in chronological order."""
    from huggingface_hub import HfApi

    api = HfApi()
    info = api.repo_info(repo, repo_type="dataset", token=token)
    prefix = f"data/{dataset}/"
    return sorted(
        s.rfilename for s in info.siblings if s.rfilename.startswith(prefix)
    )


def _download(repo: str, paths: list[str], token: str | None) -> pd.DataFrame:
    from huggingface_hub import hf_hub_download

    parts = []
    for path in paths:
        cache = hf_hub_download(repo, path, repo_type="dataset", token=token)
        parts.append(pd.read_parquet(cache))
    if not parts:
        return empty()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", FutureWarning)
        frame = pd.concat(parts, ignore_index=True)
    return frame[COLUMNS] if len(frame) else empty()


def write_baseline(counts: dict[str, int], repo: str, revision: str) -> None:
    """Record published counts so emit can compute real growth.

    Merges with any counts already on disk: a run may pull only one dataset
    and must not erase the baseline of the other.
    """
    existing: dict = {}
    if env.BASELINE.exists():
        try:
            existing = json.loads(env.BASELINE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            existing = {}
    env.BASELINE.parent.mkdir(parents=True, exist_ok=True)
    env.BASELINE.write_text(
        json.dumps(
            {
                **existing,
                **counts,
                "repo": repo,
                "revision": revision,
                "written_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def pull(dataset: str, repo: str, token: str | None = None) -> dict[str, int]:
    """Rebuild one local store from what is published on Hugging Face.

    Returns the restored counts. On the very first run the folder does not
    exist yet: that is not an error, it is the empty seed of the dataset.
    """
    env.load_local_env()
    token = token or os.environ.get("HF_TOKEN")

    try:
        paths = _list_partition_files(repo, dataset, token)
    except Exception as exc:  # noqa: BLE001 — network/token errors must be explicit
        raise SystemExit(
            f"ERROR: could not list {repo} ({type(exc).__name__}: {exc}). "
            "Refusing to continue: without the published corpus a fresh runner "
            "would emit an incomplete dataset."
        ) from exc

    if not paths:
        print(f"[pull] {dataset}: no files published yet at {repo} (first run?)")
        # Create the empty store: emit requires it to exist, and on the very
        # first run of a dataset there is nothing to restore yet.
        env.write_store(env.empty(), dataset)
        counts = {f"rows_{dataset}": 0}
        write_baseline(counts, repo, "main")
        return counts

    frame = _download(repo, paths, token)
    # Deterministic store order regardless of download order: emission
    # stability depends on it (same tie-break as emit._stable).
    frame = frame.sort_values(
        ["vacancy_id", "url"], kind="stable", na_position="last"
    ).reset_index(drop=True)
    env.write_store(frame, dataset)

    counts = {f"rows_{dataset}": int(len(frame))}
    write_baseline(counts, repo, "main")
    print(f"[pull] {dataset}: restored {len(frame):,} rows from {len(paths)} file(s)")
    return counts
