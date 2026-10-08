"""Read a revision-pinned snapshot of the published Hugging Face corpus."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pandas as pd

from pipeline.schema import COLUMNS, empty

from .constants import DEFAULT_REPO


def load_corpus(
    repo: str = DEFAULT_REPO,
    token: str | None = None,
    limit: int | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Download corpus partitions from one immutable repository revision.

    ``limit`` keeps up to that many rows per source dataset in lexical
    partition order and is intended for notebooks and demonstrations only.
    """
    try:
        from huggingface_hub import HfApi, hf_hub_download
    except ImportError as exc:  # pragma: no cover - depends on optional setup
        raise RuntimeError("Install the base requirements to read Hugging Face data") from exc

    token = token or os.environ.get("HF_TOKEN")
    info = HfApi().repo_info(repo, repo_type="dataset", token=token)
    revision = info.sha
    files = sorted(
        sibling.rfilename
        for sibling in info.siblings
        if sibling.rfilename.startswith(("data/spe/", "data/jobspy/"))
        and sibling.rfilename.endswith(".parquet")
    )
    if not files:
        raise RuntimeError(f"No canonical Parquet partitions found in {repo}@{revision}")

    frames: list[pd.DataFrame] = []
    rows_loaded = {"spe": 0, "jobspy": 0}
    selected_files: list[str] = []
    for remote_path in files:
        dataset = "jobspy" if remote_path.startswith("data/jobspy/") else "spe"
        if limit is not None and rows_loaded[dataset] >= limit:
            continue
        local_path = hf_hub_download(
            repo_id=repo,
            filename=remote_path,
            repo_type="dataset",
            revision=revision,
            token=token,
        )
        frame = pd.read_parquet(local_path, columns=COLUMNS)
        if limit is not None:
            remaining = limit - rows_loaded[dataset]
            if remaining <= 0:
                continue
            frame = frame.head(remaining)
        if not frame.empty:
            frames.append(frame)
            rows_loaded[dataset] += len(frame)
            selected_files.append(remote_path)

    corpus = pd.concat(frames, ignore_index=True) if frames else empty()
    return corpus, {
        "repo": repo,
        "revision": revision,
        "files": selected_files,
        "rows": len(corpus),
        "sample_limit_per_dataset": limit,
    }


def load_local_parquet(path: str | Path, limit: int | None = None) -> pd.DataFrame:
    """Load a local canonical Parquet file for notebook demonstrations."""
    frame = pd.read_parquet(path, columns=COLUMNS)
    return frame.head(limit).copy() if limit is not None else frame
