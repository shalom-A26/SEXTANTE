"""Orchestrate a revision-pinned analytics run and publish derived artifacts."""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import numpy as np
import pandas as pd
import scipy
import sklearn
from scipy import sparse

from . import __version__
from .artifacts import publish_run, sha256_file, write_json, write_manifest
from .comparison import compare_clusterings
from .config import AnalysisConfig
from .corpus import load_corpus
from .duplicates import find_duplicate_candidates
from .eda import summarize
from .features import run_models
from .graph import build_graphs
from .supervised import train_salary_models
from .taxonomy import extract_skills, load_esco_csv


def run_analysis(
    config: AnalysisConfig,
    token: str | None = None,
) -> Path:
    """Load one pinned HF revision and run every analytics stage on it."""
    if not config.esco_csv.is_file():
        raise FileNotFoundError(f"ESCO CSV does not exist: {config.esco_csv}")
    frame, source = load_corpus(repo=config.repo, token=token, limit=config.limit)
    run_dir = build_run(frame, source, config)
    if config.upload:
        publish_run(run_dir, config.repo, run_dir.name, token or os.environ.get("HF_TOKEN"))
    return run_dir


def build_run(frame: pd.DataFrame, source: dict[str, Any], config: AnalysisConfig) -> Path:
    """Run EDA, ESCO matching, duplicates, topics, segments, models and graphs."""
    taxonomy_path = config.esco_csv
    if frame.empty:
        raise RuntimeError("The published corpus contains no vacancy rows")
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    run_id = f"{timestamp}-{str(source['revision'])[:8]}"
    config.output_root.mkdir(parents=True, exist_ok=True)
    run_dir = config.output_root / run_id
    with TemporaryDirectory(prefix=f".{run_id}.", dir=config.output_root) as staging_name:
        staging = Path(staging_name)
        write_json(staging / "eda.json", summarize(frame))
        matcher = load_esco_csv(taxonomy_path)
        skills = extract_skills(frame, matcher)
        skills.to_parquet(staging / "skill_mentions.parquet", index=False)
        duplicates = find_duplicate_candidates(frame, threshold=config.duplicate_threshold)
        duplicates.to_parquet(staging / "duplicate_candidates.parquet", index=False)
        model_info = run_models(
            frame,
            staging,
            topic_count=config.topic_count,
            cluster_count=config.cluster_count,
            embeddings=config.embeddings,
        )
        matrix = sparse.load_npz(staging / "tfidf_matrix.npz").tocsr()
        postings = pd.read_parquet(staging / "postings.parquet")
        comparison = compare_clusterings(matrix, postings, staging, config.cluster_count)
        write_json(staging / "clustering_comparison.json", comparison)
        supervised = train_salary_models(matrix, postings, staging)
        write_json(staging / "supervised_metrics.json", supervised)
        graph_info = build_graphs(skills, postings, staging)
        write_json(staging / "graph_metrics.json", graph_info)

        manifest: dict[str, Any] = {
            "run_id": run_id,
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "analysis_version": __version__,
            "package_versions": {
                "python": sys.version.split()[0],
                "pandas": pd.__version__,
                "numpy": np.__version__,
                "scipy": scipy.__version__,
                "scikit_learn": sklearn.__version__,
                **{
                    distribution: _package_version(distribution)
                    for distribution in ("datasketch", "networkx", "sentence-transformers")
                    if config.embeddings or distribution != "sentence-transformers"
                },
            },
            "source": source,
            "taxonomy": {
                "name": "ESCO",
                "language": "es",
                "version": matcher.taxonomy_version,
                "concepts_loaded": matcher.concepts,
                "sha256": sha256_file(taxonomy_path),
            },
            "parameters": {
                "duplicate_similarity_threshold": config.duplicate_threshold,
                "duplicate_candidate_cap_per_posting": 20,
                "duplicate_candidate_pair_cap": 500_000,
                "topic_count_requested": config.topic_count,
                "cluster_count_requested": config.cluster_count,
                "embeddings_enabled": config.embeddings,
                "sample_limit_per_dataset": config.limit,
                "random_seed": 42,
            },
            "results": {
                "skill_mentions": int(len(skills)),
                "duplicate_candidates": int(len(duplicates)),
                **model_info,
                "clustering_comparison": comparison["methods"],
                "supervised": {
                    key: supervised.get(key)
                    for key in ("labeled_rows", "regression", "classification", "skipped")
                    if key in supervised
                },
                "graph": graph_info,
            },
        }
        write_manifest(staging, manifest)
        staging.rename(run_dir)
    return run_dir


def _package_version(distribution: str) -> str | None:
    try:
        return version(distribution)
    except PackageNotFoundError:
        return None
