"""Text representations, topic models, and occupational segmentation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy import sparse
from sklearn.cluster import KMeans
from sklearn.decomposition import NMF, TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import silhouette_score

SPANISH_STOP_WORDS = frozenset({
    "a", "al", "algo", "algunas", "algunos", "ante", "como", "con", "cuando",
    "de", "del", "desde", "donde", "durante", "e", "el", "ella", "ellas", "ellos",
    "en", "entre", "era", "erais", "eran", "eras", "eres", "es", "esa", "esas",
    "ese", "eso", "esos", "esta", "estaba", "estado", "estamos", "estan", "estar",
    "estas", "este", "esto", "estos", "fue", "fueron", "ha", "haber", "habia",
    "han", "hasta", "hay", "la", "las", "le", "les", "lo", "los", "mas", "me",
    "mi", "mis", "mucho", "muy", "no", "nos", "o", "of", "para", "pero", "por",
    "porque", "que", "quien", "se", "ser", "si", "sin", "sobre", "su", "sus", "te",
    "tener", "tiene", "todo", "un", "una", "uno", "unos", "y", "ya",
})


def prepare_descriptions(frame: pd.DataFrame) -> list[str]:
    """Combine title and description while retaining both vacancy identifiers."""
    title = frame["title"].fillna("").astype(str)
    description = frame["description"].fillna("").astype(str)
    return (title + " . " + description).tolist()


def fit_tfidf(
    texts: list[str], max_features: int = 50_000
) -> tuple[TfidfVectorizer, sparse.csr_matrix]:
    vectorizer = TfidfVectorizer(
        strip_accents="unicode",
        lowercase=True,
        stop_words=sorted(SPANISH_STOP_WORDS),
        ngram_range=(1, 2),
        min_df=2,
        max_df=0.98,
        max_features=max_features,
        sublinear_tf=True,
        dtype=np.float32,
    )
    return vectorizer, vectorizer.fit_transform(texts)


def _top_terms(vectorizer: TfidfVectorizer, values: np.ndarray, count: int = 12) -> list[str]:
    terms = vectorizer.get_feature_names_out()
    indices = np.argsort(values)[-count:][::-1]
    return [str(terms[index]) for index in indices if values[index] > 0]


def run_models(
    frame: pd.DataFrame,
    output_dir: str | Path,
    topic_count: int = 12,
    cluster_count: int = 8,
    max_features: int = 50_000,
    embeddings: bool = False,
) -> dict[str, Any]:
    """Fit TF-IDF, NMF topics, K-Means, and a two-dimensional SVD projection."""
    if len(frame) < 3:
        raise ValueError("At least three postings with text are required for segmentation")
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    texts = prepare_descriptions(frame)
    nonempty = [index for index, text in enumerate(texts) if len(text.strip()) > 3]
    if len(nonempty) < 3:
        raise ValueError("At least three non-empty vacancy texts are required")
    working = frame.iloc[nonempty].reset_index(drop=True)
    vectorizer, matrix = fit_tfidf([texts[index] for index in nonempty], max_features)
    if matrix.shape[1] < 2:
        raise ValueError("Text corpus has fewer than two usable terms")
    k_topics = min(topic_count, max(2, min(matrix.shape[0] - 1, matrix.shape[1] - 1)))
    k_clusters = min(cluster_count, matrix.shape[0] - 1)

    topic_model = NMF(
        n_components=k_topics,
        init="nndsvda",
        random_state=42,
        max_iter=250,
        l1_ratio=0.1,
    )
    topic_values = topic_model.fit_transform(matrix)
    topic_rows = working[["vacancy_id", "source", "url"]].copy()
    topic_rows["topic_id"] = topic_values.argmax(axis=1).astype("int32")
    topic_rows["topic_weight"] = topic_values.max(axis=1).astype("float32")
    topic_rows.to_parquet(output_dir / "topic_assignments.parquet", index=False)
    topics = pd.DataFrame([
        {"topic_id": index, "terms": " | ".join(_top_terms(vectorizer, weights))}
        for index, weights in enumerate(topic_model.components_)
    ])
    topics.to_csv(output_dir / "topics.csv", index=False)

    cluster_model = KMeans(n_clusters=k_clusters, random_state=42, n_init=10, max_iter=300)
    labels = cluster_model.fit_predict(matrix)
    actual_clusters = np.unique(labels)
    clusters = working[["vacancy_id", "source", "url"]].copy()
    clusters["cluster_id"] = labels.astype("int32")
    clusters.to_parquet(output_dir / "occupational_segments.parquet", index=False)
    cluster_terms = []
    for cluster_id in actual_clusters:
        members = matrix[labels == cluster_id]
        mean = np.asarray(members.mean(axis=0)).ravel()
        cluster_terms.append({
            "cluster_id": int(cluster_id),
            "postings": int((labels == cluster_id).sum()),
            "terms": " | ".join(_top_terms(vectorizer, mean)),
        })
    pd.DataFrame(cluster_terms).to_csv(output_dir / "segment_profiles.csv", index=False)

    projection = TruncatedSVD(n_components=2, random_state=42).fit_transform(matrix)
    coordinates = working[["vacancy_id", "source", "url"]].copy()
    coordinates["component_1"] = projection[:, 0].astype("float32")
    coordinates["component_2"] = projection[:, 1].astype("float32")
    coordinates["cluster_id"] = labels.astype("int32")
    coordinates.to_parquet(output_dir / "segment_projection.parquet", index=False)

    sample_size = min(5_000, matrix.shape[0])
    sample_indices = np.linspace(0, matrix.shape[0] - 1, sample_size, dtype=int)
    sampled_labels = labels[sample_indices]
    if 1 < np.unique(sampled_labels).size < sample_size:
        silhouette = float(silhouette_score(
            matrix[sample_indices], sampled_labels, metric="cosine"
        ))
    else:
        silhouette = None
    sparse.save_npz(output_dir / "tfidf_matrix.npz", matrix, compressed=True)
    (output_dir / "tfidf_vocabulary.json").write_text(
        json.dumps(
            {term: int(index) for term, index in vectorizer.vocabulary_.items()},
            ensure_ascii=False,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    np.save(output_dir / "tfidf_idf.npy", vectorizer.idf_.astype("float32"))

    model_info: dict[str, Any] = {
        "text_rows": int(matrix.shape[0]),
        "tfidf_features": int(matrix.shape[1]),
        "topic_count": int(k_topics),
        "cluster_count": int(actual_clusters.size),
        "cluster_count_requested": int(k_clusters),
        "silhouette_cosine_sample": silhouette,
        "silhouette_sample_rows": int(sample_size),
        "projection": "TruncatedSVD-2D (sparse PCA approximation)",
        "embedding_model": None,
    }
    if embeddings:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError("Install requirements-embeddings.txt to enable embeddings") from exc
        model_id = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
        model_revision = "b8ef00830037f9868450f778081ea683e900fe39"
        model = SentenceTransformer(model_id, revision=model_revision)
        vectors = model.encode(
            [texts[index] for index in nonempty],
            batch_size=64,
            show_progress_bar=True,
            normalize_embeddings=True,
            convert_to_numpy=True,
        ).astype("float32")
        np.save(output_dir / "sentence_embeddings.npy", vectors)
        model_info["embedding_model"] = {"id": model_id, "revision": model_revision}
    return model_info
