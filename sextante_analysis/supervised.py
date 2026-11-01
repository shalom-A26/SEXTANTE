"""Stage 5: supervised salary estimation and salary-band classification.

Both models reuse the run's TF-IDF matrix plus one-hot categorical columns.
Metrics come from K-fold cross-validation and are always reported next to a
naive baseline, so a model that does not beat "predict the median" is
visible as such.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from scipy import sparse
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import accuracy_score, f1_score, mean_absolute_error, r2_score
from sklearn.model_selection import KFold, StratifiedKFold
from sklearn.preprocessing import OneHotEncoder

CATEGORICAL_COLUMNS = (
    "source", "department", "contract_type", "work_modality", "education_level",
)
# Plausible monthly salary range in COP; outside it the value is almost
# certainly a parsing artifact (hourly/annual figures, placeholder zeros).
SALARY_FLOOR = 500_000
SALARY_CEILING = 60_000_000
MIN_LABELED_ROWS = 30
BANDS = ("bajo", "medio", "alto")


def salary_target(postings: pd.DataFrame) -> pd.Series:
    """Monthly salary midpoint (COP), NaN when missing or implausible."""
    low = pd.to_numeric(postings.get("salary_min"), errors="coerce")
    high = pd.to_numeric(postings.get("salary_max"), errors="coerce")
    midpoint = pd.concat([low, high], axis=1).mean(axis=1, skipna=True)
    return midpoint.where(midpoint.between(SALARY_FLOOR, SALARY_CEILING))


def _design(matrix: sparse.csr_matrix, postings: pd.DataFrame, encoder=None):
    categorical = postings.reindex(columns=CATEGORICAL_COLUMNS).fillna("NA").astype(str)
    if encoder is None:
        encoder = OneHotEncoder(handle_unknown="ignore", min_frequency=5)
        encoder.fit(categorical)
    return sparse.hstack([matrix, encoder.transform(categorical)], format="csr"), encoder


def _folds(rows: int) -> int:
    return max(2, min(5, rows // 10))


def train_salary_models(
    matrix: sparse.csr_matrix,
    postings: pd.DataFrame,
    output_dir: str | Path,
) -> dict[str, Any]:
    """Fit, cross-validate and persist the regression and classification models."""
    output_dir = Path(output_dir)
    target = salary_target(postings)
    labeled = np.flatnonzero(target.notna().to_numpy())
    result: dict[str, Any] = {
        "labeled_rows": int(labeled.size),
        "total_rows": int(len(postings)),
        "salary_range_cop": [SALARY_FLOOR, SALARY_CEILING],
    }
    if labeled.size < MIN_LABELED_ROWS:
        result["skipped"] = f"fewer than {MIN_LABELED_ROWS} postings with a usable salary"
        return result

    features, encoder = _design(matrix, postings)
    x = features[labeled]
    y = target.to_numpy()[labeled]
    log_y = np.log(y)

    # Regression on log salary; errors reported back in COP.
    predictions = np.zeros_like(y)
    baseline = np.zeros_like(y)
    for train, test in KFold(_folds(labeled.size), shuffle=True, random_state=42).split(x):
        model = Ridge(alpha=1.0).fit(x[train], log_y[train])
        predictions[test] = np.exp(model.predict(x[test]))
        baseline[test] = np.median(y[train])
    regression = {
        "model": "Ridge(alpha=1.0) on log salary; TF-IDF + one-hot categoricals",
        "cv_folds": _folds(labeled.size),
        "mae_cop": float(mean_absolute_error(y, predictions)),
        "baseline_median_mae_cop": float(mean_absolute_error(y, baseline)),
        "median_abs_pct_error": float(np.median(np.abs(predictions - y) / y)),
        "r2_log": float(r2_score(log_y, np.log(predictions))),
    }
    final_regressor = Ridge(alpha=1.0).fit(x, log_y)

    # Classification into salary tertiles.
    edges = np.quantile(y, [1 / 3, 2 / 3])
    bands = np.digitize(y, edges)
    band_predictions = np.zeros_like(bands)
    majority = np.zeros_like(bands)
    classification: dict[str, Any] = {
        "model": "LogisticRegression(multinomial) over salary tertiles",
        "band_edges_cop": [float(edge) for edge in edges],
        "labels": list(BANDS),
    }
    final_classifier = None
    min_class = int(np.bincount(bands, minlength=3).min())
    if min_class >= 2:
        folds = max(2, min(_folds(labeled.size), min_class))
        splitter = StratifiedKFold(folds, shuffle=True, random_state=42)
        for train, test in splitter.split(x, bands):
            classifier = LogisticRegression(max_iter=2000, C=2.0).fit(x[train], bands[train])
            band_predictions[test] = classifier.predict(x[test])
            majority[test] = np.bincount(bands[train]).argmax()
        classification.update({
            "cv_folds": folds,
            "accuracy": float(accuracy_score(bands, band_predictions)),
            "macro_f1": float(f1_score(bands, band_predictions, average="macro")),
            "baseline_majority_accuracy": float(accuracy_score(bands, majority)),
        })
        final_classifier = LogisticRegression(max_iter=2000, C=2.0).fit(x, bands)
    else:
        classification["skipped"] = "a salary band has fewer than two postings"

    estimates = np.exp(final_regressor.predict(features))
    output = postings[["vacancy_id", "source", "url"]].copy()
    output["salary_observed"] = target.astype("float64")
    output["salary_estimate"] = estimates.astype("float64")
    output.to_parquet(output_dir / "salary_estimates.parquet", index=False)
    joblib.dump(
        {
            "encoder": encoder,
            "regressor": final_regressor,
            "classifier": final_classifier,
            "band_edges": edges.tolist(),
            "bands": list(BANDS),
            "categorical_columns": list(CATEGORICAL_COLUMNS),
        },
        output_dir / "salary_model.joblib",
    )
    result["regression"] = regression
    result["classification"] = classification
    return result


def estimate_salary(bundle: dict[str, Any], vector: sparse.csr_matrix,
                    context: dict[str, str] | None = None) -> dict[str, Any]:
    """Predict a salary and band for one already-vectorized text."""
    row = pd.DataFrame([{column: (context or {}).get(column) for column in CATEGORICAL_COLUMNS}])
    x, _ = _design(vector, row, bundle["encoder"])
    estimate = float(np.exp(bundle["regressor"].predict(x)[0]))
    band = None
    if bundle.get("classifier") is not None:
        band = bundle["bands"][int(bundle["classifier"].predict(x)[0])]
    return {"salary_estimate_cop": estimate, "salary_band": band}
