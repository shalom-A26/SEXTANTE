"""Validated run configuration for the analytics batch job."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .constants import DEFAULT_REPO


@dataclass(frozen=True, slots=True)
class AnalysisConfig:
    """Immutable inputs and parameters for one analysis snapshot."""

    esco_csv: Path
    repo: str = DEFAULT_REPO
    output_root: Path = Path("data/analysis/runs")
    limit: int | None = None
    duplicate_threshold: float = 0.90
    topic_count: int = 12
    cluster_count: int = 8
    embeddings: bool = False
    upload: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "esco_csv", Path(self.esco_csv))
        object.__setattr__(self, "output_root", Path(self.output_root))
        if not self.repo.strip():
            raise ValueError("repo must be a non-empty Hugging Face dataset ID")
        if self.limit is not None and self.limit < 3:
            raise ValueError("limit must be at least 3 rows per dataset")
        if not 0.0 < self.duplicate_threshold <= 1.0:
            raise ValueError("duplicate_threshold must be in (0, 1]")
        if self.topic_count < 2:
            raise ValueError("topic_count must be at least 2")
        if self.cluster_count < 2:
            raise ValueError("cluster_count must be at least 2")

