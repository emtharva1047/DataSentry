"""Read-only, explainable ML-readiness diagnostics for tabular datasets."""
from datetime import datetime, timezone
from hashlib import sha256
from itertools import combinations
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import sklearn

from ..models import Dataset
from . import dataset_ingestion

MIN_NUMERIC_VALUES = 4
MIN_NUMERIC_PARSEABILITY = 0.8
MAX_NUMERIC_FEATURES = 20
MAX_EVIDENCE_PAIRS = 50
EVIDENCE_ROW_LIMIT = 20
CLASS_DISTRIBUTION_LIMIT = 20


class DatasetReadinessFileUnavailableError(RuntimeError):
    """Raised when the source CSV is missing, unreadable, or outside upload storage."""


class DatasetReadinessRequestError(ValueError):
    """Raised when a target or feature selection does not match the dataset."""


def _read_dataset(dataset: Dataset) -> pd.DataFrame:
    """Read only the registered upload; never accept a client-supplied path."""
    try:
        permitted_root = dataset_ingestion.UPLOAD_DIR.resolve()
        source_path = Path(dataset.original_path).resolve(strict=True)
        source_path.relative_to(permitted_root)
        return pd.read_csv(source_path, encoding=dataset.encoding, dtype=str)
    except (
        OSError,
        RuntimeError,
        ValueError,
        UnicodeDecodeError,
        pd.errors.EmptyDataError,
        pd.errors.ParserError,
    ) as exc:
        raise DatasetReadinessFileUnavailableError(
            "The stored CSV is unavailable or could not be read for ML-readiness assessment."
        ) from exc


def _clean_text(series: pd.Series) -> pd.Series:
    """Treat whitespace-only cells as missing without changing stored source data."""
    values = series.astype("string")
    blank = values.str.strip().eq("").fillna(False)
    return values.mask(blank, pd.NA)


def _numeric_array(series: pd.Series) -> np.ndarray:
    """Return finite numeric values, using NaN for missing or non-numeric cells."""
    parsed = pd.to_numeric(series, errors="coerce")
    values = parsed.to_numpy(dtype=float, na_value=np.nan)
    values[~np.isfinite(values)] = np.nan
    return values


def _warning(code: str, message: str, severity: str = "medium") -> dict[str, str]:
    return {"code": code, "severity": severity, "message": message}


def _duplicate_feature_rows(features: pd.DataFrame) -> dict[str, Any]:
    duplicate_mask = features.duplicated(keep="first")
    all_duplicate_mask = features.duplicated(keep=False)
    duplicate_count = int(duplicate_mask.sum())
    group_count = (
        int(features.loc[all_duplicate_mask].drop_duplicates().shape[0])
        if duplicate_count
        else 0
    )
    row_numbers = (features.index[duplicate_mask] + 1).astype(int).tolist()
    return {
        "duplicate_rows_after_first": duplicate_count,
        "duplicate_groups": group_count,
        "duplicate_rate_pct": round(duplicate_count / len(features) * 100, 2)
        if len(features)
        else 0.0,
        "row_numbers": row_numbers[:EVIDENCE_ROW_LIMIT],
        "row_numbers_truncated": len(row_numbers) > EVIDENCE_ROW_LIMIT,
        "definition": "Repeated selected feature vectors after the first occurrence; target is excluded, and matching missing-value positions are treated as equal.",
    }


def _exact_match_rate(left: pd.Series, right: pd.Series) -> tuple[int, float, float]:
    comparable = left.notna() & right.notna()
    compared_count = int(comparable.sum())
    coverage = compared_count / len(left) if len(left) else 0.0
    if compared_count == 0:
        return 0, 0.0, coverage
    matches = left.loc[comparable].astype(str).eq(right.loc[comparable].astype(str))
    return compared_count, float(matches.mean()), coverage


def _leakage_indicators(
    target: pd.Series,
    features: pd.DataFrame,
    task_type: str,
    leakage_threshold: float,
) -> list[dict[str, Any]]:
    indicators: list[dict[str, Any]] = []
    for name in features.columns:
        compared_count, agreement, coverage = _exact_match_rate(target, features[name])
        if compared_count >= 2 and coverage >= 0.8 and agreement >= leakage_threshold:
            indicators.append(
                {
                    "feature": str(name),
                    "kind": "near_exact_target_copy",
                    "agreement_pct": round(agreement * 100, 2),
                    "coverage_pct": round(coverage * 100, 2),
                    "compared_rows": compared_count,
                    "review_required": True,
                }
            )

    if task_type == "regression":
        target_values = _numeric_array(target)
        for name in features.columns:
            feature_values = _numeric_array(features[name])
            valid = np.isfinite(target_values) & np.isfinite(feature_values)
            if int(valid.sum()) < MIN_NUMERIC_VALUES:
                continue
            left = target_values[valid]
            right = feature_values[valid]
            if np.std(left) == 0 or np.std(right) == 0:
                continue
            correlation = float(np.corrcoef(left, right)[0, 1])
            if np.isfinite(correlation) and abs(correlation) >= leakage_threshold:
                if any(item["feature"] == str(name) for item in indicators):
                    continue
                indicators.append(
                    {
                        "feature": str(name),
                        "kind": "near_perfect_numeric_target_association",
                        "absolute_pearson_correlation": round(abs(correlation), 6),
                        "compared_rows": int(valid.sum()),
                        "review_required": True,
                    }
                )
    return indicators[:MAX_EVIDENCE_PAIRS]


def _feature_redundancy(
    features: pd.DataFrame, correlation_threshold: float
) -> dict[str, Any]:
    exact_pairs: list[dict[str, Any]] = []
    correlated_pairs: list[dict[str, Any]] = []
    numeric_candidates: dict[str, np.ndarray] = {}

    names = [str(name) for name in features.columns]
    for name in names:
        series = features[name]
        values = _numeric_array(series)
        non_missing = int(series.notna().sum())
        valid_count = int(np.isfinite(values).sum())
        ratio = valid_count / non_missing if non_missing else 0.0
        if valid_count >= MIN_NUMERIC_VALUES and ratio >= MIN_NUMERIC_PARSEABILITY:
            numeric_candidates[name] = values

    # Hash each feature column once, then verify candidate groups by digest.
    # This keeps wide-dataset duplicate checks O(rows × columns), not O(rows × columns²).
    fingerprint_groups: dict[str, list[str]] = {}
    for name in names:
        hashes = pd.util.hash_pandas_object(features[name], index=False, categorize=True)
        fingerprint = sha256(hashes.to_numpy(dtype="uint64").tobytes()).hexdigest()
        fingerprint_groups.setdefault(fingerprint, []).append(name)

    valid_duplicate_groups: list[tuple[list[str], int, float]] = []
    total_exact_pairs = 0
    for group in fingerprint_groups.values():
        if len(group) < 2:
            continue
        compared_count = int(features[group[0]].notna().sum())
        coverage = compared_count / len(features) if len(features) else 0.0
        if compared_count < 2 or coverage < 0.8:
            continue
        total_exact_pairs += len(group) * (len(group) - 1) // 2
        valid_duplicate_groups.append((group, compared_count, coverage))

    for group, compared_count, coverage in valid_duplicate_groups:
        for left_name, right_name in combinations(group, 2):
            if len(exact_pairs) >= MAX_EVIDENCE_PAIRS:
                break
            exact_pairs.append(
                {
                    "left_feature": left_name,
                    "right_feature": right_name,
                    "agreement_pct": 100.0,
                    "coverage_pct": round(coverage * 100, 2),
                    "compared_rows": compared_count,
                }
            )
        if len(exact_pairs) >= MAX_EVIDENCE_PAIRS:
            break


    numeric_names = list(numeric_candidates)[:MAX_NUMERIC_FEATURES]
    for left_index, left_name in enumerate(numeric_names):
        for right_name in numeric_names[left_index + 1 :]:
            left = numeric_candidates[left_name]
            right = numeric_candidates[right_name]
            valid = np.isfinite(left) & np.isfinite(right)
            if int(valid.sum()) < MIN_NUMERIC_VALUES:
                continue
            left_values = left[valid]
            right_values = right[valid]
            if np.std(left_values) == 0 or np.std(right_values) == 0:
                continue
            correlation = float(np.corrcoef(left_values, right_values)[0, 1])
            if np.isfinite(correlation) and abs(correlation) >= correlation_threshold:
                correlated_pairs.append(
                    {
                        "left_feature": left_name,
                        "right_feature": right_name,
                        "pearson_correlation": round(correlation, 6),
                        "absolute_correlation": round(abs(correlation), 6),
                        "compared_rows": int(valid.sum()),
                    }
                )

    reported_exact_pairs = exact_pairs[:MAX_EVIDENCE_PAIRS]
    reported_correlated_pairs = correlated_pairs[:MAX_EVIDENCE_PAIRS]
    return {
        "exact_duplicate_feature_pairs": reported_exact_pairs,
        "high_correlation_pairs": reported_correlated_pairs,
        "reported_pair_limit_per_category": MAX_EVIDENCE_PAIRS,
        "pairs_truncated": total_exact_pairs > MAX_EVIDENCE_PAIRS or len(correlated_pairs) > MAX_EVIDENCE_PAIRS,
        "reported_pair_count": len(reported_exact_pairs) + len(reported_correlated_pairs),
        "numeric_columns_assessed": numeric_names,
        "numeric_columns_truncated": len(numeric_candidates) > MAX_NUMERIC_FEATURES,
        "correlation_threshold": correlation_threshold,
        "method": "pairwise Pearson correlation on finite numeric observations; exact agreement on co-observed feature values",
    }


def assess_ml_readiness(dataset: Dataset, request: dict[str, Any]) -> dict[str, Any]:
    """Assess target suitability, leakage risks, duplicate splits, redundancy, and sample size."""
    frame = _read_dataset(dataset)
    target_name = str(request["target_column"])
    task_type = str(request["task_type"])

    if target_name not in frame.columns:
        raise DatasetReadinessRequestError(
            f"Target column '{target_name}' does not exist in the dataset."
        )

    requested_features = request.get("feature_columns")
    if requested_features is None:
        feature_names = [str(name) for name in frame.columns if str(name) != target_name]
    else:
        feature_names = [str(name) for name in requested_features]
    if not feature_names:
        raise DatasetReadinessRequestError("At least one feature column is required.")
    if target_name in feature_names:
        raise DatasetReadinessRequestError("The target column cannot also be a feature.")
    unknown = [name for name in feature_names if name not in frame.columns]
    if unknown:
        raise DatasetReadinessRequestError(
            f"Unknown feature column(s): {', '.join(unknown[:10])}."
        )

    row_count = int(len(frame))
    target = _clean_text(frame[target_name])
    missing_target = target.isna()
    missing_target_count = int(missing_target.sum())
    observed_target = target.loc[~missing_target]
    features = pd.DataFrame(
        {name: _clean_text(frame[name]) for name in feature_names},
        index=frame.index,
    )
    warnings: list[dict[str, str]] = []
    blockers: list[dict[str, str]] = []

    if missing_target_count:
        warnings.append(
            _warning(
                "incomplete_target",
                f"{missing_target_count} of {row_count} rows have a missing or whitespace-only target; exclude or resolve these rows before fitting.",
                "high" if missing_target_count / max(row_count, 1) >= 0.2 else "medium",
            )
        )

    target_report: dict[str, Any] = {
        "column": target_name,
        "task_type": task_type,
        "row_count": row_count,
        "observed_count": int(len(observed_target)),
        "missing_count": missing_target_count,
        "completeness_pct": round(len(observed_target) / row_count * 100, 2)
        if row_count
        else 0.0,
    }

    if task_type == "classification":
        counts = observed_target.value_counts(dropna=True)
        class_count = int(len(counts))
        observed_count = int(counts.sum())
        distribution = [
            {
                "label": str(label),
                "count": int(count),
                "percentage": round(int(count) / observed_count * 100, 2)
                if observed_count
                else 0.0,
            }
            for label, count in counts.head(CLASS_DISTRIBUTION_LIMIT).items()
        ]
        majority_count = int(counts.max()) if class_count else 0
        minority_count = int(counts.min()) if class_count else 0
        majority_share = majority_count / observed_count if observed_count else 0.0
        imbalance_ratio = majority_count / minority_count if minority_count else None
        target_report.update(
            {
                "class_count": class_count,
                "class_distribution": distribution,
                "class_distribution_truncated": class_count > CLASS_DISTRIBUTION_LIMIT,
                "majority_class_share_pct": round(majority_share * 100, 2),
                "minority_class_count": minority_count,
                "majority_to_minority_ratio": round(imbalance_ratio, 4)
                if imbalance_ratio is not None
                else None,
                "minimum_class_count_threshold": int(request["min_class_count"]),
            }
        )
        if class_count < 2:
            blockers.append(
                _warning(
                    "insufficient_target_classes",
                    "Classification requires at least two observed target classes.",
                    "high",
                )
            )
        elif (
            majority_share >= float(request["majority_class_threshold"])
            or (imbalance_ratio is not None and imbalance_ratio >= 10)
            or minority_count < int(request["min_class_count"])
        ):
            warnings.append(
                _warning(
                    "class_imbalance",
                    "The target distribution is imbalanced or contains a class below the configured minimum count; use stratified evaluation and report per-class metrics.",
                    "high" if majority_share >= 0.9 or minority_count < 2 else "medium",
                )
            )
    else:
        numeric_target = _numeric_array(observed_target)
        valid_target = np.isfinite(numeric_target)
        numeric_count = int(valid_target.sum())
        invalid_count = int(len(observed_target) - numeric_count)
        target_report.update(
            {
                "numeric_parseable_count": numeric_count,
                "non_numeric_or_non_finite_count": invalid_count,
                "numeric_completeness_pct": round(numeric_count / row_count * 100, 2)
                if row_count
                else 0.0,
            }
        )
        if numeric_count < 2:
            blockers.append(
                _warning(
                    "insufficient_numeric_target",
                    "Regression requires at least two finite numeric target values.",
                    "high",
                )
            )
        if invalid_count:
            warnings.append(
                _warning(
                    "non_numeric_regression_target",
                    f"{invalid_count} non-missing target values are not finite numbers and cannot be used as regression labels.",
                    "high",
                )
            )

    feature_missingness = []
    for name in feature_names:
        missing_count = int(features[name].isna().sum())
        feature_missingness.append(
            {
                "column": name,
                "missing_count": missing_count,
                "missing_pct": round(missing_count / row_count * 100, 2)
                if row_count
                else 0.0,
            }
        )

    duplicate_risk = _duplicate_feature_rows(features)
    if duplicate_risk["duplicate_rows_after_first"]:
        warnings.append(
            _warning(
                "duplicate_feature_vectors",
                f"{duplicate_risk['duplicate_rows_after_first']} rows repeat an earlier feature vector; random train/test splitting can place identical feature vectors in both partitions.",
                "high",
            )
        )

    leakage = _leakage_indicators(
        target,
        features,
        task_type,
        float(request["leakage_threshold"]),
    )
    if leakage:
        warnings.append(
            _warning(
                "suspicious_target_association",
                "One or more features closely reproduce or are almost perfectly associated with the target; inspect feature provenance and exclude post-outcome fields before modeling.",
                "high",
            )
        )

    redundancy = _feature_redundancy(
        features, float(request["correlation_threshold"])
    )
    if redundancy["exact_duplicate_feature_pairs"] or redundancy["high_correlation_pairs"]:
        warnings.append(
            _warning(
                "redundant_features",
                "Potentially duplicated or highly correlated feature pairs were found; review redundancy and fit any feature selection on training data only.",
                "medium",
            )
        )

    rows_per_feature = row_count / len(feature_names) if feature_names else None
    size_category = "very_small" if row_count < 100 else "small" if row_count < 1000 else "moderate"
    dataset_size = {
        "rows": row_count,
        "feature_count": len(feature_names),
        "rows_per_feature": round(rows_per_feature, 2) if rows_per_feature is not None else None,
        "category": size_category,
        "minimum_row_guidance": 100,
    }
    if row_count < 100:
        warnings.append(
            _warning(
                "very_small_dataset",
                "Fewer than 100 rows are available; holdout metrics may have high variance and should be interpreted cautiously.",
                "high",
            )
        )
    elif row_count < 1000:
        warnings.append(
            _warning(
                "small_dataset",
                "Fewer than 1,000 rows are available; use repeated or stratified evaluation where appropriate and report uncertainty.",
                "medium",
            )
        )
    if len(feature_names) >= row_count:
        warnings.append(
            _warning(
                "high_dimensionality",
                "The number of selected features is at least the number of rows; overfitting risk is elevated.",
                "high",
            )
        )

    readiness_status = "blocked" if blockers else "review_required" if warnings else "ready_for_baseline"
    return {
        "dataset_id": dataset.id,
        "filename": dataset.filename,
        "source_sha256": dataset.sha256_hash,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "shape": {"rows": row_count, "columns": int(frame.shape[1])},
        "readiness_status": readiness_status,
        "target": target_report,
        "selected_features": feature_names,
        "feature_missingness": feature_missingness,
        "duplicate_split_risk": duplicate_risk,
        "leakage_indicators": leakage,
        "feature_redundancy": redundancy,
        "dataset_size": dataset_size,
        "warnings": warnings,
        "blockers": blockers,
        "model_training_performed": False,
        "baseline_models": {
            "status": "not_run",
            "note": "This endpoint performs diagnostics only; it does not fit or evaluate a model.",
        },
        "parameters": {
            "leakage_threshold": float(request["leakage_threshold"]),
            "correlation_threshold": float(request["correlation_threshold"]),
            "minimum_class_count": int(request["min_class_count"]),
            "majority_class_threshold": float(request["majority_class_threshold"]),
            "numeric_parseability_threshold": MIN_NUMERIC_PARSEABILITY,
            "minimum_numeric_values": MIN_NUMERIC_VALUES,
            "maximum_numeric_features_for_pairwise_correlation": MAX_NUMERIC_FEATURES,
        },
        "software_versions": {
            "pandas": pd.__version__,
            "numpy": np.__version__,
            "scikit_learn": sklearn.__version__,
        },
        "method_notes": [
            "This is a deterministic heuristic assessment, not proof that a dataset is fit for a particular model.",
            "Whitespace-only cells are treated as missing for target and feature diagnostics; stored CSV bytes are never changed.",
            "Exact target-copy and near-perfect regression-correlation indicators require human provenance review; association alone does not prove leakage.",
            "Repeated feature vectors can cross random train/test partitions; group-aware splitting may be preferable when repeated entities are present.",
            "Feature redundancy uses exact co-observed agreement and pairwise Pearson correlation for numeric-like columns; only the first 20 eligible numeric features are assessed.",
            "The endpoint does not fit a model, impute values, encode categories, select features, or modify the source dataset.",
            "Baseline classifier and regressor pipelines with train-only preprocessing remain a separate implementation milestone.",
        ],
    }
