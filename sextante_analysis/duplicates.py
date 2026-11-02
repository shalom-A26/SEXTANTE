"""Scalable candidate generation and exact text similarity for duplicates."""

from __future__ import annotations

import unicodedata
from typing import Any

import numpy as np
import pandas as pd

from .taxonomy import TOKEN_RE


def _shingles(text: Any, width: int = 3, cap: int = 512) -> list[str]:
    value = unicodedata.normalize("NFKD", str(text or "").casefold())
    value = "".join(char for char in value if not unicodedata.combining(char))
    tokens = TOKEN_RE.findall(value)
    grams = [
        " ".join(tokens[index:index + width])
        for index in range(max(1, len(tokens) - width + 1))
    ]
    if len(grams) <= cap:
        return grams
    step = len(grams) / cap
    return [grams[int(index * step)] for index in range(cap)]


def find_duplicate_candidates(
    frame: pd.DataFrame,
    threshold: float = 0.90,
    max_candidates_per_posting: int = 20,
    max_candidate_pairs: int = 500_000,
) -> pd.DataFrame:
    """Find high-similarity pairs using MinHash blocking then exact TF-IDF.

    LSH only limits the comparison set; it never marks or removes a posting.
    Candidate pairs are retained only when exact word n-gram cosine
    similarity reaches ``threshold``.
    """
    if not 0.0 < threshold <= 1.0:
        raise ValueError("threshold must be in (0, 1]")
    try:
        from datasketch import MinHash, MinHashLSH
        from sklearn.feature_extraction.text import HashingVectorizer, TfidfTransformer
    except ImportError as exc:  # pragma: no cover - depends on analysis setup
        raise RuntimeError("Install requirements-analysis.txt for duplicate detection") from exc

    required = ["vacancy_id", "source", "url", "title", "description"]
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise ValueError(f"Missing columns for duplicate detection: {', '.join(missing)}")
    texts = frame["description"].fillna("").astype(str).tolist()
    indices = [index for index, text in enumerate(texts) if len(text.strip()) >= 80]
    columns = ["vacancy_id_a", "source_a", "url_a", "title_a", "vacancy_id_b",
               "source_b", "url_b", "title_b", "similarity"]
    if len(indices) < 2:
        return pd.DataFrame(columns=columns)

    lsh = MinHashLSH(threshold=0.70, num_perm=64)
    signatures: dict[int, MinHash] = {}
    for index in indices:
        signature = MinHash(num_perm=64, seed=42)
        for shingle in sorted(_shingles(texts[index])):
            signature.update(shingle.encode("utf-8"))
        signatures[index] = signature
        lsh.insert(str(index), signature)

    pairs: list[tuple[int, int]] = []
    total_pairs = 0
    random = np.random.default_rng(42)
    for index in indices:
        candidates = sorted(
            int(value)
            for value in lsh.query(signatures[index])
            if int(value) > index
        )
        if len(candidates) > max_candidates_per_posting:
            positions = np.linspace(
                0, len(candidates) - 1, max_candidates_per_posting, dtype=int
            )
            candidates = [candidates[position] for position in positions]
        for candidate in candidates[:max_candidates_per_posting]:
            pair = (index, candidate)
            total_pairs += 1
            if len(pairs) < max_candidate_pairs:
                pairs.append(pair)
            else:
                slot = int(random.integers(total_pairs))
                if slot < max_candidate_pairs:
                    pairs[slot] = pair
    if not pairs:
        return pd.DataFrame(columns=columns)

    # Hashed word 1-2-grams + TF-IDF: the same cosine as a vocabulary-based
    # TF-IDF up to rare hash collisions (2**20 buckets), without building a
    # multi-million-entry vocabulary over the whole corpus. Only postings
    # that take part in a candidate pair are vectorized.
    involved = sorted({index for pair in pairs for index in pair})
    hasher = HashingVectorizer(
        analyzer="word",
        ngram_range=(1, 2),
        strip_accents="unicode",
        n_features=2**20,
        alternate_sign=False,
        norm=None,
        dtype=np.float32,
    )
    counts = hasher.transform(texts[index] for index in involved)
    if counts.nnz == 0:
        return pd.DataFrame(columns=columns)
    matrix = TfidfTransformer(sublinear_tf=True).fit_transform(counts).tocsr()
    positions = {original: position for position, original in enumerate(involved)}
    rows: list[dict[str, Any]] = []
    for left, right in sorted(pairs):
        similarity = min(1.0, float(
            matrix[positions[left]].multiply(matrix[positions[right]]).sum()
        ))  # float32 rounding can exceed 1
        if similarity < threshold:
            continue
        a, b = frame.iloc[left], frame.iloc[right]
        rows.append({
            "vacancy_id_a": a["vacancy_id"], "source_a": a["source"], "url_a": a["url"],
            "title_a": a["title"], "vacancy_id_b": b["vacancy_id"], "source_b": b["source"],
            "url_b": b["url"], "title_b": b["title"], "similarity": similarity,
        })
    return pd.DataFrame(rows, columns=columns).sort_values(
        "similarity", ascending=False, kind="stable"
    ).reset_index(drop=True)
