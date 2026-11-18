"""Stage 5: supervised salary-band classification.

Colombian postings almost never publish an exact salary: the SPE export (and
elempleo) only give official bands such as ``$1.500.001 - $2.000.000``. A
"median salary" or a regression on band midpoints would invent precision the
data does not have, so salary is treated as an ordinal band end to end.

The classifier reuses the run's TF-IDF matrix plus one-hot categorical columns.
Metrics come from stratified K-fold cross-validation and are always reported
next to a majority-class baseline.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from scipy import sparse
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score
from sklearn.model_selection import StratifiedKFold
from sklearn.preprocessing import OneHotEncoder

CATEGORICAL_COLUMNS = (
    "source", "department", "contract_type", "work_modality", "education_level",
)
# Plausible monthly salary range in COP; outside it the value is almost
# certainly a parsing artifact (hourly/annual figures, placeholder zeros).
SALARY_FLOOR = 500_000
SALARY_CEILING = 60_000_000
MIN_LABELED_ROWS = 30
# Upper edges (inclusive, COP) aligned with the SPE official bands, merged so
# every class has enough postings; the last band is open-ended.
BAND_EDGES = (1_500_000, 2_000_000, 3_000_000, 4_000_000, 6_000_000)
BANDS = ("Hasta $1,5M", "$1,5M – $2M", "$2M – $3M", "$3M – $4M", "$4M – $6M", "Más de $6M")
# shortcut: cross-validation runs on a seeded sample of this size to keep the
# scheduled run short; the final model still trains on every labeled row.
CV_MAX_ROWS = 100_000


def salary_band(postings: pd.DataFrame) -> pd.Series:
    """Salary band index (0..len(BANDS)-1) per posting, <NA> when unusable.

    The (min, max) midpoint only locates the posting inside its band; it is
    never reported as a salary.
    """
    low = pd.to_numeric(postings.get("salary_min"), errors="coerce")
    high = pd.to_numeric(postings.get("salary_max"), errors="coerce")
    midpoint = pd.concat([low, high], axis=1).mean(axis=1, skipna=True)
    midpoint = midpoint.where(midpoint.between(SALARY_FLOOR, SALARY_CEILING))
    bands = pd.Series(np.searchsorted(BAND_EDGES, midpoint.fillna(0).to_numpy(), side="left"),
                      index=postings.index, dtype="Int64")
    return bands.mask(midpoint.isna())


def band_distribution(bands: pd.Series) -> dict[str, Any]:
    """Share of postings per band plus the modal and median band (ordinal)."""
    known = bands.dropna().astype(int)
    counts = np.bincount(known, minlength=len(BANDS)) if len(known) else np.zeros(len(BANDS))
    n = int(counts.sum())
    return {
        "n": n,
        "bands": [{"band": label, "count": int(count), "share": float(count / n) if n else 0.0}
                  for label, count in zip(BANDS, counts, strict=True)],
        "mode": BANDS[int(counts.argmax())] if n else None,
        "median": BANDS[int(np.median(known))] if n else None,
    }


def _design(matrix: sparse.csr_matrix, postings: pd.DataFrame, encoder=None):
    categorical = postings.reindex(columns=CATEGORICAL_COLUMNS).fillna("NA").astype(str)
    if encoder is None:
        encoder = OneHotEncoder(handle_unknown="ignore", min_frequency=5)
        encoder.fit(categorical)
    return sparse.hstack([matrix, encoder.transform(categorical)], format="csr"), encoder


def train_salary_models(
    matrix: sparse.csr_matrix,
    postings: pd.DataFrame,
    output_dir: str | Path,
) -> dict[str, Any]:
    """Fit, cross-validate and persist the salary-band classifier."""
    output_dir = Path(output_dir)
    target = salary_band(postings)
    labeled = np.flatnonzero(target.notna().to_numpy())
    result: dict[str, Any] = {
        "labeled_rows": int(labeled.size),
        "total_rows": int(len(postings)),
        "labels": list(BANDS),
        "band_edges_cop": list(BAND_EDGES),
    }
    if labeled.size < MIN_LABELED_ROWS:
        result["skipped"] = f"fewer than {MIN_LABELED_ROWS} postings with a usable salary"
        return result

    features, encoder = _design(matrix, postings)
    y_all = target.to_numpy()[labeled].astype(int)
    classification: dict[str, Any] = {
        "model": "LogisticRegression(multinomial) over SPE salary bands; "
                 "TF-IDF + one-hot categoricals",
        "class_counts": np.bincount(y_all, minlength=len(BANDS)).tolist(),
    }
    rng = np.random.default_rng(42)
    sample = (np.sort(rng.choice(labeled.size, CV_MAX_ROWS, replace=False))
              if labeled.size > CV_MAX_ROWS else np.arange(labeled.size))
    x, y = features[labeled[sample]], y_all[sample]
    present = np.bincount(y)
    min_class = int(present[present > 0].min())
    final_classifier = None
    if min_class >= 2 and (present > 0).sum() >= 2:
        folds = max(2, min(5, min_class))
        predictions = np.zeros_like(y)
        majority = np.zeros_like(y)
        for train, test in StratifiedKFold(folds, shuffle=True, random_state=42).split(x, y):
            model = LogisticRegression(max_iter=2000, C=2.0).fit(x[train], y[train])
            predictions[test] = model.predict(x[test])
            majority[test] = np.bincount(y[train]).argmax()
        classification.update({
            "cv_folds": folds,
            "cv_rows": int(len(y)),
            "accuracy": float(accuracy_score(y, predictions)),
            "macro_f1": float(f1_score(y, predictions, average="macro")),
            "within_one_band": float(np.mean(np.abs(predictions - y) <= 1)),
            "baseline_majority_accuracy": float(accuracy_score(y, majority)),
            "baseline_majority_macro_f1": float(f1_score(y, majority, average="macro")),
            "baseline_within_one_band": float(np.mean(np.abs(majority - y) <= 1)),
        })
        final_classifier = LogisticRegression(max_iter=2000, C=2.0).fit(
            features[labeled], y_all)
    else:
        classification["skipped"] = "a salary band has fewer than two postings"

    output = postings[["vacancy_id", "source", "url"]].copy()
    output["salary_band_observed"] = [BANDS[b] if pd.notna(b) else None for b in target]
    output["salary_band_estimate"] = (
        [BANDS[b] for b in final_classifier.predict(features)] if final_classifier else None)
    output.to_parquet(output_dir / "salary_estimates.parquet", index=False)
    joblib.dump(
        {
            "encoder": encoder,
            "classifier": final_classifier,
            "bands": list(BANDS),
            "categorical_columns": list(CATEGORICAL_COLUMNS),
        },
        output_dir / "salary_model.joblib",
    )
    result["classification"] = classification
    return result


def estimate_salary(bundle: dict[str, Any], vector: sparse.csr_matrix,
                    context: dict[str, str] | None = None) -> dict[str, Any] | None:
    """Predict the salary band for one already-vectorized text."""
    classifier = bundle.get("classifier")
    if classifier is None:
        return None
    row = pd.DataFrame([{column: (context or {}).get(column) for column in CATEGORICAL_COLUMNS}])
    x, _ = _design(vector, row, bundle["encoder"])
    probabilities = classifier.predict_proba(x)[0]
    best = int(probabilities.argmax())
    return {"salary_band": bundle["bands"][int(classifier.classes_[best])],
            "probability": float(probabilities[best])}
