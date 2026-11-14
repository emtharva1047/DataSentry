"""Public UCI Wine reference benchmark and downstream classification experiment."""
from __future__ import annotations

from hashlib import sha256
from typing import Any, Sequence

import numpy as np
import pandas as pd
import sklearn
from sklearn.datasets import load_wine

from .dataset_benchmark import (
    DEFAULT_BENCHMARK_RATES,
    DEFAULT_BENCHMARK_SEEDS,
    run_synthetic_detector_benchmark,
)
from .dataset_ml_experiment import run_classification_corruption_experiment


WINE_SOURCE_URL = "https://archive.ics.uci.edu/dataset/109/wine"
WINE_SOURCE_DATA_URL = "https://archive.ics.uci.edu/ml/machine-learning-databases/wine/wine.data"
WINE_SKLEARN_DOCS_URL = "https://scikit-learn.org/stable/modules/generated/sklearn.datasets.load_wine.html"


def _frame_sha256(frame: pd.DataFrame) -> str:
    payload = frame.to_csv(index=False, lineterminator="\n").encode("utf-8")
    return sha256(payload).hexdigest()


def build_wine_reference() -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    """Load the bundled UCI Wine copy and add one documented categorical test feature."""
    wine = load_wine(as_frame=True)
    features = wine.data.copy(deep=True)
    alcohol_band = pd.cut(
        pd.to_numeric(features["alcohol"], errors="raise"),
        bins=[-np.inf, 12.0, 13.0, np.inf],
        labels=["low", "medium", "high"],
        include_lowest=True,
    )
    if alcohol_band.isna().any():
        raise ValueError("the deterministic alcohol_band derivation produced missing values")
    features["alcohol_band"] = alcohol_band.astype("string").astype(object)
    target = wine.target.astype(str).rename("target")

    full_frame = features.copy(deep=True)
    full_frame["target"] = target
    class_distribution = {
        str(label): int(count)
        for label, count in target.value_counts().sort_index().items()
    }
    metadata = {
        "name": "Wine Recognition",
        "repository": "UCI Machine Learning Repository",
        "uci_dataset_id": 109,
        "source_url": WINE_SOURCE_URL,
        "source_data_url": WINE_SOURCE_DATA_URL,
        "loader": "sklearn.datasets.load_wine(as_frame=True)",
        "loader_documentation": WINE_SKLEARN_DOCS_URL,
        "runtime_network_fetch": False,
        "rows": int(len(full_frame)),
        "original_numeric_features": int(wine.data.shape[1]),
        "derived_features": [
            {
                "name": "alcohol_band",
                "source_column": "alcohol",
                "method": "pandas.cut with fixed edges (-inf, 12.0, 13.0, inf)",
                "labels": ["low", "medium", "high"],
                "purpose": "make the categorical inconsistency detector and cleaning workflow applicable",
                "is_original_dataset_feature": False,
            }
        ],
        "target_column": "target",
        "class_distribution": class_distribution,
        "sha256_full_frame": _frame_sha256(full_frame),
        "sha256_detector_reference_without_target": _frame_sha256(features),
        "software_versions": {
            "pandas": pd.__version__,
            "numpy": np.__version__,
            "scikit_learn": sklearn.__version__,
        },
        "provenance_note": (
            "The experiment uses scikit-learn's bundled copy of the UCI Wine Recognition dataset; "
            "the original target is excluded from detector benchmarking. The derived alcohol_band "
            "feature is explicitly identified and is used only to exercise categorical consistency."
        ),
    }
    return features.reset_index(drop=True), full_frame.reset_index(drop=True), metadata


def run_wine_reference_experiment(
    *,
    rates: Sequence[float] = DEFAULT_BENCHMARK_RATES,
    seeds: Sequence[int] = DEFAULT_BENCHMARK_SEEDS,
    n_estimators: int = 100,
    ml_corruption_rates: Sequence[float] = (0.05, 0.10, 0.20),
) -> dict[str, Any]:
    """Run defect detection and clean-test downstream classification on the public reference."""
    detector_frame, modeling_frame, metadata = build_wine_reference()
    detector_report = run_synthetic_detector_benchmark(
        detector_frame,
        rates=rates,
        seeds=seeds,
        n_estimators=n_estimators,
    )
    normalized_ml_rates = tuple(float(rate) for rate in ml_corruption_rates)
    if (
        not normalized_ml_rates
        or len(set(normalized_ml_rates)) != len(normalized_ml_rates)
        or any(not np.isfinite(rate) or not 0 < rate <= 0.5 for rate in normalized_ml_rates)
    ):
        raise ValueError("ml_corruption_rates must be distinct values in (0, 0.5]")

    downstream_experiments = [
        run_classification_corruption_experiment(
            modeling_frame,
            target_column="target",
            feature_columns=["alcohol_band"],
            seeds=seeds,
            test_size=0.25,
            corruption_rate=rate,
        )
        for rate in normalized_ml_rates
    ]
    return {
        "schema_version": 1,
        "dataset": metadata,
        "detector_benchmark": detector_report,
        "downstream_classification": {
            "corruption_rates": list(normalized_ml_rates),
            "experiments": downstream_experiments,
        },
        "scope_limitations": [
            "The UCI Wine dataset is small (178 rows) and results are dataset-specific.",
            "The categorical alcohol_band feature is derived for detector coverage and is not an original UCI attribute.",
            "The downstream experiment uses only the derived alcohol_band feature (excluding its source alcohol column) and evaluates categorical inconsistency at 5%, 10%, and 20% training-feature corruption rates on one classification task.",
            "Regression downstream evaluation and other corruption types remain outstanding.",
            "Detector runtime excludes corruption generation and metric calculation; Python tracemalloc is only a partial memory proxy.",
        ],
    }
