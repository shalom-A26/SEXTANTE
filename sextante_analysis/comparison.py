"""Stage 4: compare clustering methods and projections on a bounded sample.

The batch contract keeps K-Means as the published segmentation; this module
records how hierarchical clustering and DBSCAN behave on the same reduced
space so the choice is documented by numbers, not assumed.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy import sparse
from sklearn.cluster import DBSCAN, AgglomerativeClustering, KMeans
from sklearn.decomposition import TruncatedSVD
from sklearn.manifold import TSNE
from sklearn.metrics import adjusted_rand_score, silhouette_score
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import normalize

SAMPLE_ROWS = 3_000


def _silhouette(points: np.ndarray, labels: np.ndarray) -> float | None:
    mask = labels >= 0
    if np.unique(labels[mask]).size < 2 or mask.sum() <= np.unique(labels[mask]).size:
        return None
    return float(silhouette_score(points[mask], labels[mask], metric="cosine"))


def compare_clusterings(
    matrix: sparse.csr_matrix,
    postings: pd.DataFrame,
    output_dir: str | Path,
    cluster_count: int,
) -> dict[str, Any]:
    rows = matrix.shape[0]
    size = min(SAMPLE_ROWS, rows)
    index = np.linspace(0, rows - 1, size, dtype=int)
    components = max(2, min(50, matrix.shape[1] - 1, size - 1))
    reduced = normalize(
        TruncatedSVD(n_components=components, random_state=42).fit_transform(matrix[index])
    )
    k = max(2, min(cluster_count, size - 1))
    published = postings["cluster_id"].to_numpy()[index]

    kmeans = KMeans(n_clusters=k, random_state=42, n_init=10).fit_predict(reduced)
    hierarchical = AgglomerativeClustering(n_clusters=k, linkage="ward").fit_predict(reduced)
    # eps from the median distance to the 5th neighbour: a standard heuristic.
    neighbours = min(5, size - 1)
    distances, _ = NearestNeighbors(n_neighbors=neighbours + 1).fit(reduced).kneighbors(reduced)
    eps = float(np.median(distances[:, -1])) or 0.5
    dbscan = DBSCAN(eps=eps, min_samples=neighbours).fit_predict(reduced)

    methods = {}
    for name, labels in (("kmeans", kmeans), ("hierarchical_ward", hierarchical),
                         ("dbscan", dbscan)):
        methods[name] = {
            "clusters": int(np.unique(labels[labels >= 0]).size),
            "noise_share": float((labels < 0).mean()),
            "silhouette_cosine": _silhouette(reduced, labels),
            "ari_vs_published_kmeans": float(adjusted_rand_score(published, labels)),
        }
    methods["dbscan"]["eps"] = eps

    perplexity = float(min(30, max(2, (size - 1) / 3)))
    if size >= 5:
        embedded = TSNE(n_components=2, perplexity=perplexity, random_state=42,
                        init="pca").fit_transform(reduced)
        projection = postings.iloc[index][["vacancy_id", "source", "cluster_id"]].copy()
        projection["tsne_1"] = embedded[:, 0].astype("float32")
        projection["tsne_2"] = embedded[:, 1].astype("float32")
        projection.to_parquet(Path(output_dir) / "segment_projection_tsne.parquet", index=False)
    return {
        "sample_rows": int(size),
        "svd_components": int(components),
        "methods": methods,
        "tsne_perplexity": perplexity if size >= 5 else None,
        "published_method": "kmeans on full TF-IDF",
    }
