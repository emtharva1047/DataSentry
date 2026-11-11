"""Leakage-safe baseline classification and regression for uploaded CSVs."""
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from time import perf_counter
from typing import Any

import numpy as np
import pandas as pd
import sklearn
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    confusion_matrix,
    f1_score,
    mean_absolute_error,
    mean_squared_error,
    precision_score,
    r2_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from ..models import Dataset
from . import dataset_ingestion

MINIMUM_ROWS = 10
MINIMUM_CLASS_COUNT = 2
MINIMUM_NUMERIC_VALUES = 2
NUMERIC_PARSEABILITY = 0.8
MAX_CATEGORIES = 100


class DatasetModelingFileUnavailableError(RuntimeError):
    """Raised when the registered source CSV cannot be read safely."""


class DatasetModelingRequestError(ValueError):
    """Raised when the requested baseline cannot be evaluated reliably."""


def _read_source(dataset: Dataset) -> tuple[pd.DataFrame, str]:
    """Read only the registered upload and fingerprint its exact stored bytes."""
    try:
        permitted_root = dataset_ingestion.UPLOAD_DIR.resolve()
        source_path = Path(dataset.original_path).resolve(strict=True)
        source_path.relative_to(permitted_root)
        payload = source_path.read_bytes()
        frame = pd.read_csv(source_path, encoding=dataset.encoding, dtype=str)
    except (
        OSError,
        RuntimeError,
        ValueError,
        UnicodeDecodeError,
        pd.errors.EmptyDataError,
        pd.errors.ParserError,
    ) as exc:
        raise DatasetModelingFileUnavailableError(
            "The stored CSV is unavailable or could not be read for baseline modeling."
        ) from exc
    return frame, sha256(payload).hexdigest()


def _clean_text(series: pd.Series) -> pd.Series:
    """Treat whitespace-only cells as missing without modifying the source."""
    values = series.astype("string")
    return values.mask(values.str.strip().eq("").fillna(False), pd.NA)


def _infer_numeric_columns(training_features: pd.DataFrame) -> list[str]:
    """Infer feature types from training rows only to avoid test-partition leakage."""
    numeric: list[str] = []
    for name in training_features.columns:
        values = _clean_text(training_features[name])
        observed = values.dropna()
        if observed.empty:
            continue
        parsed = pd.to_numeric(observed, errors="coerce").to_numpy(dtype=float)
        finite_count = int(np.isfinite(parsed).sum())
        if (
            finite_count >= MINIMUM_NUMERIC_VALUES
            and finite_count / len(observed) >= NUMERIC_PARSEABILITY
        ):
            numeric.append(str(name))
    return numeric


def _prepare_partition(
    features: pd.DataFrame,
    numeric_columns: list[str],
    categorical_columns: list[str],
) -> pd.DataFrame:
    """Convert features using types inferred on training data; retain missing values."""
    prepared = features.copy()
    for name in numeric_columns:
        parsed = pd.to_numeric(prepared[name], errors="coerce")
        values = parsed.to_numpy(dtype=float, na_value=np.nan)
        values[~np.isfinite(values)] = np.nan
        prepared[name] = values
    for name in categorical_columns:
        values = _clean_text(prepared[name]).astype(object)
        prepared[name] = values.where(pd.notna(values), np.nan)
    return prepared


def _build_preprocessor(
    numeric_columns: list[str], categorical_columns: list[str]
) -> ColumnTransformer:
    """Build imputers, scaling, and encoding that are fitted only inside the pipeline."""
    transformers: list[tuple[str, Pipeline, list[str]]] = []
    if numeric_columns:
        numeric_pipeline = Pipeline(
            steps=[
                ("imputer", SimpleImputer(strategy="median", keep_empty_features=True)),
                ("scaler", StandardScaler()),
            ]
        )
        transformers.append(("numeric", numeric_pipeline, numeric_columns))
    if categorical_columns:
        categorical_pipeline = Pipeline(
            steps=[
                (
                    "imputer",
                    SimpleImputer(
                        strategy="constant",
                        fill_value="__DATASENTRY_MISSING__",
                        keep_empty_features=True,
                    ),
                ),
                (
                    "onehot",
                    OneHotEncoder(
                        handle_unknown="ignore",
                        max_categories=MAX_CATEGORIES,
                    ),
                ),
            ]
        )
        transformers.append(("categorical", categorical_pipeline, categorical_columns))
    return ColumnTransformer(transformers=transformers, remainder="drop")


def train_baseline_model(dataset: Dataset, request: dict[str, Any]) -> dict[str, Any]:
    """Fit one deterministic baseline after splitting, with preprocessing fit on train only."""
    frame, source_fingerprint = _read_source(dataset)
    target_name = str(request["target_column"])
    task_type = str(request["task_type"])
    if target_name not in frame.columns:
        raise DatasetModelingRequestError(
            f"Target column '{target_name}' does not exist in the dataset."
        )

    requested_features = request.get("feature_columns")
    if requested_features is None:
        feature_names = [str(name) for name in frame.columns if str(name) != target_name]
    else:
        feature_names = [str(name) for name in requested_features]
    if not feature_names:
        raise DatasetModelingRequestError("At least one feature column is required.")
    if target_name in feature_names:
        raise DatasetModelingRequestError("The target column cannot also be a feature.")
    unknown = [name for name in feature_names if name not in frame.columns]
    if unknown:
        raise DatasetModelingRequestError(
            f"Unknown feature column(s): {', '.join(unknown[:10])}."
        )

    raw_target = _clean_text(frame[target_name])
    excluded_target_rows = int(raw_target.isna().sum())
    if task_type == "classification":
        valid_mask = raw_target.notna()
        target = raw_target.loc[valid_mask].astype(str)
    else:
        parsed_target = pd.to_numeric(raw_target, errors="coerce")
        target_values = parsed_target.to_numpy(dtype=float, na_value=np.nan)
        valid_mask = pd.Series(np.isfinite(target_values), index=frame.index)
        excluded_target_rows = int((~valid_mask).sum())
        target = pd.Series(target_values[valid_mask.to_numpy()], index=frame.index[valid_mask])

    features = pd.DataFrame(
        {name: _clean_text(frame.loc[valid_mask, name]) for name in feature_names},
        index=frame.index[valid_mask],
    )
    row_count = len(features)
    if row_count < MINIMUM_ROWS:
        raise DatasetModelingRequestError(
            f"At least {MINIMUM_ROWS} rows with usable target values are required."
        )

    test_size = float(request["test_size"])
    random_state = int(request["random_state"])
    stratify = None
    split_strategy = "random_holdout"
    if task_type == "classification":
        class_counts = target.value_counts()
        class_count = int(len(class_counts))
        if class_count < 2:
            raise DatasetModelingRequestError(
                "Classification requires at least two observed target classes."
            )
        if int(class_counts.min()) < MINIMUM_CLASS_COUNT:
            raise DatasetModelingRequestError(
                "Every classification class needs at least two rows for a stratified holdout."
            )
        expected_test_rows = int(np.ceil(row_count * test_size))
        expected_train_rows = row_count - expected_test_rows
        if expected_test_rows < class_count or expected_train_rows < class_count:
            raise DatasetModelingRequestError(
                "The selected test size cannot place every class in both partitions; add rows or adjust test_size."
            )
        stratify = target
        split_strategy = "stratified_random_holdout"

    try:
        X_train_raw, X_test_raw, y_train, y_test = train_test_split(
            features,
            target,
            test_size=test_size,
            random_state=random_state,
            stratify=stratify,
        )
    except ValueError as exc:
        raise DatasetModelingRequestError(
            f"A valid train/test split could not be created: {exc}"
        ) from exc

    numeric_columns = _infer_numeric_columns(X_train_raw)
    categorical_columns = [
        str(name) for name in X_train_raw.columns if str(name) not in numeric_columns
    ]
    X_train = _prepare_partition(X_train_raw, numeric_columns, categorical_columns)
    X_test = _prepare_partition(X_test_raw, numeric_columns, categorical_columns)

    preprocessor = _build_preprocessor(numeric_columns, categorical_columns)
    if task_type == "classification":
        estimator = LogisticRegression(
            max_iter=1000,
            class_weight="balanced",
            solver="lbfgs",
            random_state=random_state,
        )
        model_name = "logistic_regression"
        model_parameters: dict[str, Any] = {
            "max_iter": 1000,
            "class_weight": "balanced",
            "solver": "lbfgs",
        }
    else:
        estimator = Ridge(alpha=1.0, solver="lsqr")
        model_name = "ridge_regression"
        model_parameters = {"alpha": 1.0, "solver": "lsqr"}

    pipeline = Pipeline(
        steps=[("preprocessor", preprocessor), ("model", estimator)]
    )
    started = perf_counter()
    try:
        pipeline.fit(X_train, y_train)
        predictions = pipeline.predict(X_test)
    except (ValueError, TypeError, FloatingPointError) as exc:
        raise DatasetModelingRequestError(
            f"The baseline pipeline could not fit this feature selection: {exc}"
        ) from exc
    elapsed = perf_counter() - started

    if task_type == "classification":
        model = pipeline.named_steps["model"]
        labels = [str(label) for label in model.classes_]
        matrix = confusion_matrix(y_test, predictions, labels=model.classes_)
        metrics: dict[str, Any] = {
            "accuracy": round(float(accuracy_score(y_test, predictions)), 6),
            "balanced_accuracy": round(float(balanced_accuracy_score(y_test, predictions)), 6),
            "macro_precision": round(
                float(precision_score(y_test, predictions, average="macro", zero_division=0)),
                6,
            ),
            "macro_recall": round(
                float(recall_score(y_test, predictions, average="macro", zero_division=0)),
                6,
            ),
            "macro_f1": round(
                float(f1_score(y_test, predictions, average="macro", zero_division=0)),
                6,
            ),
            "confusion_matrix": {
                "labels": labels,
                "counts": matrix.astype(int).tolist(),
            },
            "roc_auc": None,
            "roc_auc_positive_class": None,
        }
        if len(model.classes_) == 2:
            try:
                probabilities = pipeline.predict_proba(X_test)[:, 1]
                positive_class = model.classes_[1]
                metrics["roc_auc"] = round(
                    float(roc_auc_score(y_test == positive_class, probabilities)), 6
                )
                metrics["roc_auc_positive_class"] = str(positive_class)
            except (ValueError, AttributeError):
                metrics["roc_auc"] = None
    else:
        predictions_array = np.asarray(predictions, dtype=float)
        actual_array = np.asarray(y_test, dtype=float)
        metrics = {
            "mae": round(float(mean_absolute_error(actual_array, predictions_array)), 6),
            "rmse": round(
                float(np.sqrt(mean_squared_error(actual_array, predictions_array))), 6
            ),
            "r2": round(float(r2_score(actual_array, predictions_array)), 6),
        }

    return {
        "dataset_id": dataset.id,
        "filename": dataset.filename,
        "source_sha256": source_fingerprint,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "task_type": task_type,
        "model": model_name,
        "model_training_performed": True,
        "target": {
            "column": target_name,
            "eligible_rows": int(row_count),
            "excluded_rows": int(excluded_target_rows),
        },
        "features": {
            "selected_columns": feature_names,
            "numeric_columns_inferred_from_training": numeric_columns,
            "categorical_columns_inferred_from_training": categorical_columns,
            "numeric_parseability_threshold": NUMERIC_PARSEABILITY,
            "max_categories_per_feature": MAX_CATEGORIES,
        },
        "split": {
            "strategy": split_strategy,
            "random_state": random_state,
            "test_size": test_size,
            "train_rows": int(len(X_train)),
            "test_rows": int(len(X_test)),
        },
        "preprocessing": {
            "fit_scope": "training_partition_only",
            "fit_rows": int(len(X_train)),
            "test_partition_used_to_fit_preprocessing": False,
            "numeric": "training-median imputation followed by standard scaling",
            "categorical": "training-only constant imputation and one-hot encoding; unknown test categories are ignored",
        },
        "model_parameters": model_parameters,
        "metrics": metrics,
        "duration_seconds": round(float(elapsed), 6),
        "software_versions": {
            "pandas": pd.__version__,
            "numpy": np.__version__,
            "scikit_learn": sklearn.__version__,
        },
        "method_notes": [
            "The train/test split is created before feature-type inference, imputation, scaling, or encoding.",
            "Numeric/categorical inference and every fitted preprocessing transform use training rows only; the test partition is transformed by the fitted training pipeline.",
            "Classification uses a stratified random holdout; regression uses a seeded random holdout.",
            "Rows with missing targets, and non-finite/non-numeric regression targets, are excluded before splitting; feature rows are retained and imputed by the training pipeline.",
            "The classifier is class-weighted logistic regression; the regressor is Ridge regression. These are transparent baselines, not tuned production models.",
            "Random row splitting does not prevent repeated entities or duplicate feature vectors crossing partitions; inspect ML-readiness diagnostics and use group-aware splitting when appropriate.",
            "A single holdout is sensitive to the split seed. Report repeated-seed mean and standard deviation before making comparative research claims.",
            "No model artifact is persisted and the uploaded CSV is never modified.",
        ],
    }
