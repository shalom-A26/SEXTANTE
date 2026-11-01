"""Manual validation: export review samples and score the labeled answers.

``export_review_samples`` writes CSVs with an empty ``is_correct`` column
for a human reviewer (open the ``url`` to judge). ``evaluate_reviews`` reads
the filled CSVs and reports precision with a Wilson 95% interval, which is
what the analytics limitations ask for before product decisions.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import pandas as pd

SAMPLES = {
    "skill_mentions": ("skill_mentions.parquet", 200),
    "duplicate_candidates": ("duplicate_candidates.parquet", 100),
    "segments": ("postings.parquet", 150),
}
TRUE_VALUES = {"1", "true", "si", "sí", "yes", "y", "x"}


def export_review_samples(run_dir: str | Path, output_dir: str | Path | None = None) -> list[Path]:
    run_dir = Path(run_dir)
    output_dir = Path(output_dir or run_dir / "review")
    output_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for name, (artifact, size) in SAMPLES.items():
        path = run_dir / artifact
        if not path.is_file():
            continue
        frame = pd.read_parquet(path)
        if frame.empty:
            continue
        sample = frame.sample(n=min(size, len(frame)), random_state=42)
        if name == "segments":
            sample = sample[["vacancy_id", "source", "url", "title", "cluster_id"]]
            profiles = run_dir / "segment_profiles.csv"
            if profiles.is_file():
                terms = pd.read_csv(profiles).set_index("cluster_id")["terms"]
                sample["segment_terms"] = sample["cluster_id"].map(terms)
        sample = sample.copy()
        sample["is_correct"] = ""
        sample["notes"] = ""
        target = output_dir / f"review_{name}.csv"
        sample.to_csv(target, index=False)
        written.append(target)
    return written


def wilson_interval(successes: int, total: int, z: float = 1.96) -> tuple[float, float]:
    if total == 0:
        return (0.0, 0.0)
    p = successes / total
    centre = (p + z * z / (2 * total)) / (1 + z * z / total)
    margin = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / (1 + z * z / total)
    return (max(0.0, centre - margin), min(1.0, centre + margin))


def evaluate_reviews(review_dir: str | Path) -> dict[str, Any]:
    report: dict[str, Any] = {}
    for path in sorted(Path(review_dir).glob("review_*.csv")):
        frame = pd.read_csv(path, dtype=str).fillna("")
        answered = frame[frame["is_correct"].str.strip() != ""]
        correct = int(answered["is_correct"].str.strip().str.casefold().isin(TRUE_VALUES).sum())
        total = int(len(answered))
        low, high = wilson_interval(correct, total)
        report[path.stem.removeprefix("review_")] = {
            "reviewed": total,
            "pending": int(len(frame) - total),
            "precision": correct / total if total else None,
            "precision_ci95": [low, high] if total else None,
        }
    return report
