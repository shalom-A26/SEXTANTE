"""Serving bundle: a small slice of a run that fits a free 512 MB host.

The full run (481k postings) needs ~2.5 GB of RAM in the API. The bundle
keeps the corpus-wide numbers but shrinks what CV matching scans:

- ``dashboard.json`` — the dashboard payload computed over the full run;
- ``segment_stats.json`` — names, sizes and median salaries per segment;
- ``centroids.npy`` — segment centroids from the full TF-IDF matrix;
- ``skill_aliases.parquet`` — every ESCO alias seen, so CV skill detection
  keeps the full vocabulary;
- the ``rows`` most recently captured postings (recent ones are the most
  likely to still accept applications), with their TF-IDF rows and skills;
- the vectorizer, segment skills, transitions and salary model, unchanged.

    python -m sextante_api.serving <run_dir> [--rows 40000]

writes ``<run_dir>/serving/``, which ``load_run`` reads like any run.
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import sparse

from sextante_analysis.supervised import salary_target

from .data import load_run
from .insights import dashboard, segment_names

SERVING_ROWS = 40_000
COPIED = (
    "eda.json", "tfidf_vectorizer.joblib", "segment_profiles.csv", "segment_skills.parquet",
    "segment_transitions.parquet", "topics.csv", "supervised_metrics.json",
    "clustering_comparison.json", "graph_metrics.json", "salary_model.joblib",
)


def build_bundle(run_dir: str | Path, rows: int = SERVING_ROWS) -> Path:
    run_dir = Path(run_dir)
    out = run_dir / "serving"
    out.mkdir(exist_ok=True)
    run = load_run(run_dir)

    (out / "dashboard.json").write_text(json.dumps(dashboard(run), ensure_ascii=False),
                                        encoding="utf-8")
    names = segment_names(run)
    salaries = salary_target(run.postings)
    stats = {
        str(segment): {
            "name": names.get(segment),
            "postings": int((run.postings["cluster_id"] == segment).sum()),
            "median_salary": _median(salaries[run.postings["cluster_id"] == segment]),
        }
        for segment in run.segment_ids
    }
    (out / "segment_stats.json").write_text(json.dumps(stats, ensure_ascii=False),
                                            encoding="utf-8")
    np.save(out / "centroids.npy", run.centroids.astype(np.float32))

    captured = pd.to_datetime(run.postings["captured_at"], errors="coerce") \
        if "captured_at" in run.postings else pd.Series(pd.NaT, index=run.postings.index)
    order = np.argsort(captured.fillna(pd.Timestamp.min).to_numpy(), kind="stable")[::-1]
    keep = np.sort(order[:rows])
    postings = run.postings.iloc[keep].reset_index(drop=True)
    postings.to_parquet(out / "postings.parquet", index=False)
    sparse.save_npz(out / "tfidf_matrix.npz", run.matrix[keep].astype(np.float32).tocsr())

    mentions = pd.read_parquet(run_dir / "skill_mentions.parquet")
    keys = set(zip(postings["vacancy_id"].astype(str), postings["source"].astype(str),
                   strict=True))
    in_bundle = [(str(v), str(s)) in keys for v, s in
                 mentions[["vacancy_id", "source"]].itertuples(index=False)]
    mentions.loc[in_bundle, ["vacancy_id", "source", "esco_uri"]].to_parquet(
        out / "skill_mentions.parquet", index=False)
    mentions[["esco_uri", "skill_label", "matched_text"]].drop_duplicates().to_parquet(
        out / "skill_aliases.parquet", index=False)

    for name in COPIED:
        if (run_dir / name).is_file():
            shutil.copy2(run_dir / name, out / name)
    manifest = dict(run.manifest)
    manifest["serving"] = {"rows": int(len(postings)), "of": int(len(run.postings)),
                           "selection": "most recently captured"}
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2),
                                       encoding="utf-8")
    return out


def _median(values: pd.Series) -> float | None:
    values = values.dropna()
    return float(values.median()) if len(values) else None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("run_dir")
    parser.add_argument("--rows", type=int, default=SERVING_ROWS)
    args = parser.parse_args()
    print(build_bundle(args.run_dir, args.rows))


if __name__ == "__main__":
    main()
