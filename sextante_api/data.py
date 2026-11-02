"""Load one analytics run into memory for the API.

Resolution order for the run directory:

1. ``SEXTANTE_RUN_DIR`` — an explicit run directory;
2. the newest run under ``SEXTANTE_RUNS_ROOT`` (default ``data/analysis/runs``);
3. ``derived/latest.json`` of ``SEXTANTE_HF_REPO`` (needs ``HF_TOKEN``),
   downloaded into the runs root. With ``SEXTANTE_SERVING=1`` only the run's
   ``serving/`` bundle is downloaded (see ``serving.py``; fits ~512 MB hosts).
"""

from __future__ import annotations

import json
import os
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from scipy import sparse
from sklearn.preprocessing import normalize

from sextante_analysis.taxonomy import EscoMatcher, matcher_from_mentions


@dataclass
class RunData:
    run_dir: Path
    manifest: dict[str, Any]
    eda: dict[str, Any]
    postings: pd.DataFrame          # row-aligned with ``matrix``
    matrix: sparse.csr_matrix
    vectorizer: Any
    centroids: np.ndarray           # L2-normalized mean TF-IDF per segment
    segment_ids: list[int]
    segment_profiles: pd.DataFrame
    segment_skills: pd.DataFrame
    skill_nodes: pd.DataFrame
    skill_edges: pd.DataFrame
    transitions: pd.DataFrame
    topics: pd.DataFrame
    projection: pd.DataFrame
    supervised: dict[str, Any]
    comparison: dict[str, Any]
    graph_metrics: dict[str, Any]
    salary_bundle: dict[str, Any] | None
    matcher: EscoMatcher
    skill_labels: dict[str, str]
    posting_skills: list[frozenset[str]]  # per matrix row
    segment_names: dict[int, str] | None = None  # cached by insights.segment_names
    precomputed_dashboard: dict[str, Any] | None = None  # serving bundle only
    segment_stats: dict[int, dict[str, Any]] | None = None  # serving bundle only


# Artifacts the API reads; the rest of a run (duplicates, topic assignments,
# per-posting estimates) is for analysts and is not downloaded.
API_FILES = (
    "manifest.json", "eda.json", "postings.parquet", "tfidf_matrix.npz",
    "tfidf_vectorizer.joblib", "segment_profiles.csv", "segment_skills.parquet",
    "skill_graph_nodes.parquet", "skill_graph_edges.parquet", "segment_transitions.parquet",
    "topics.csv", "segment_projection.parquet", "supervised_metrics.json",
    "clustering_comparison.json", "graph_metrics.json", "salary_model.joblib",
    "skill_mentions.parquet",
)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def _parquet(path: Path) -> pd.DataFrame:
    return pd.read_parquet(path) if path.is_file() else pd.DataFrame()


def resolve_run_dir() -> Path:
    explicit = os.environ.get("SEXTANTE_RUN_DIR")
    if explicit:
        return Path(explicit)
    root = Path(os.environ.get("SEXTANTE_RUNS_ROOT", "data/analysis/runs"))
    runs = sorted(
        path for path in root.glob("*")
        if path.is_dir() and not path.name.startswith(".") and (path / "manifest.json").is_file()
    ) if root.is_dir() else []
    if runs:
        return runs[-1]
    repo = os.environ.get("SEXTANTE_HF_REPO")
    if repo:
        return _download_latest(repo, root)
    raise FileNotFoundError(
        f"No analytics run found under {root}. Run `python -m sextante_analysis demo` "
        "or set SEXTANTE_RUN_DIR / SEXTANTE_HF_REPO."
    )


def _download_latest(repo: str, root: Path) -> Path:
    from huggingface_hub import hf_hub_download, snapshot_download

    token = os.environ.get("HF_TOKEN")
    latest = hf_hub_download(repo, "derived/latest.json", repo_type="dataset", token=token)
    run_id = json.loads(Path(latest).read_text(encoding="utf-8"))["run_id"]
    run_path = f"derived/runs/{run_id}"
    if os.environ.get("SEXTANTE_SERVING") == "1":
        run_path += "/serving"
        patterns = [f"{run_path}/*"]
    else:
        patterns = [f"{run_path}/{name}" for name in API_FILES]
    snapshot_download(repo, repo_type="dataset", token=token, local_dir=str(root / "_hf"),
                      allow_patterns=patterns)
    return root / "_hf" / run_path


def load_run(run_dir: str | Path) -> RunData:
    run_dir = Path(run_dir)
    postings = pd.read_parquet(run_dir / "postings.parquet")
    matrix = sparse.load_npz(run_dir / "tfidf_matrix.npz").tocsr()
    if matrix.shape[0] != len(postings):
        raise ValueError("postings.parquet is not row-aligned with tfidf_matrix.npz")
    labels = postings["cluster_id"].to_numpy()
    stats = _read_json(run_dir / "segment_stats.json")
    segment_stats = {int(key): value for key, value in stats.items()} or None
    if segment_stats:  # serving bundle: segments come from the full run
        segment_ids = sorted(segment_stats)
        centroids = np.load(run_dir / "centroids.npy")
    else:
        segment_ids = sorted(int(value) for value in np.unique(labels))
        centroids = normalize(np.vstack([
            np.asarray(matrix[labels == segment].mean(axis=0)).ravel()
            for segment in segment_ids
        ]))

    mentions = _parquet(run_dir / "skill_mentions.parquet")
    aliases = _parquet(run_dir / "skill_aliases.parquet")
    if aliases.empty:
        aliases = mentions
    skills_by_posting: dict[tuple[str, str], set[str]] = defaultdict(set)
    for vacancy_id, source, uri in mentions[["vacancy_id", "source", "esco_uri"]].itertuples(
        index=False
    ) if not mentions.empty else []:
        skills_by_posting[(str(vacancy_id), str(source))].add(uri)
    posting_skills = [
        frozenset(skills_by_posting.get((str(v), str(s)), ()))
        for v, s in postings[["vacancy_id", "source"]].itertuples(index=False)
    ]
    salary_path = run_dir / "salary_model.joblib"
    projection = _parquet(run_dir / "segment_projection.parquet")
    return RunData(
        run_dir=run_dir,
        manifest=_read_json(run_dir / "manifest.json"),
        eda=_read_json(run_dir / "eda.json"),
        postings=postings,
        matrix=matrix,
        vectorizer=joblib.load(run_dir / "tfidf_vectorizer.joblib"),
        centroids=centroids,
        segment_ids=segment_ids,
        segment_profiles=pd.read_csv(run_dir / "segment_profiles.csv"),
        segment_skills=_parquet(run_dir / "segment_skills.parquet"),
        skill_nodes=_parquet(run_dir / "skill_graph_nodes.parquet"),
        skill_edges=_parquet(run_dir / "skill_graph_edges.parquet"),
        transitions=_parquet(run_dir / "segment_transitions.parquet"),
        topics=pd.read_csv(run_dir / "topics.csv") if (run_dir / "topics.csv").is_file()
        else pd.DataFrame(),
        projection=projection,
        supervised=_read_json(run_dir / "supervised_metrics.json"),
        comparison=_read_json(run_dir / "clustering_comparison.json"),
        graph_metrics=_read_json(run_dir / "graph_metrics.json"),
        salary_bundle=joblib.load(salary_path) if salary_path.is_file() else None,
        matcher=matcher_from_mentions(aliases) if not aliases.empty
        else matcher_from_mentions(pd.DataFrame(columns=["esco_uri", "skill_label",
                                                         "matched_text"])),
        skill_labels=dict(zip(aliases.get("esco_uri", []), aliases.get("skill_label", []),
                              strict=True)),
        posting_skills=posting_skills,
        segment_names={key: value["name"] for key, value in segment_stats.items()}
        if segment_stats else None,
        precomputed_dashboard=_read_json(run_dir / "dashboard.json") or None,
        segment_stats=segment_stats,
    )
