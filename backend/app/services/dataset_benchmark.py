"""Ground-truth evaluation runner for controlled detector experiments.

The runner operates only on in-memory copies. It reuses the production numerical
anomaly algorithms so benchmark behavior cannot silently drift from the API.
"""
from __future__ import annotations

import tracemalloc
from math import isfinite
from time import perf_counter
from typing import Any, Callable, Sequence

import numpy as np
import pandas as pd

from . import dataset_anomaly
from .dataset_research import (
    SUPPORTED_DEFECTS,
    _infer_numeric_columns,
    aggregate_seed_metrics,
    evaluate_binary_detector,
    inject_synthetic_corruption,
)

DEFAULT_BENCHMARK_RATES = (0.01, 0.05, 0.10)
DEFAULT_BENCHMARK_SEEDS = (42, 123, 2026)
MAX_BENCHMARK_RATES = 5
MAX_BENCHMARK_SEEDS = 10
MAX_ISOLATION_ESTIMATORS = 500

DETECTORS_BY_DEFECT = {
    "missingness": ("missingness_rule",),
    "duplicates": ("exact_duplicate_rule",),
    "categorical_inconsistency": ("categorical_consistency_rule",),
    "invalid_values": ("numeric_parseability_rule",),
    "numerical_anomalies": ("iqr", "robust_zscore", "isolation_forest"),
}
UNIT_BY_DEFECT = {
    "missingness": "cell",
    "duplicates": "row",
    "categorical_inconsistency": "cell",
    "invalid_values": "cell",
    "numerical_anomalies": "row",
}


def _validate_benchmark_request(
    frame: pd.DataFrame,
    rates: Sequence[float],
    seeds: Sequence[int],
    defects: Sequence[str] | None,
    n_estimators: int,
    contamination: float,
    iqr_multiplier: float,
    robust_z_threshold: float,
) -> tuple[tuple[float, ...], tuple[int, ...], tuple[str, ...]]:
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        raise ValueError("frame must be a non-empty pandas DataFrame")
    if not frame.columns.is_unique:
        raise ValueError("frame must have unique column names")
    if any(not isinstance(name, str) or not name.strip() for name in frame.columns):
        raise ValueError("all column names must be non-empty strings")

    if isinstance(rates, (str, bytes)):
        raise ValueError("rates must be a sequence of numeric corruption rates")
    rate_values = tuple(rates)
    if not rate_values or len(rate_values) > MAX_BENCHMARK_RATES:
        raise ValueError(f"select between 1 and {MAX_BENCHMARK_RATES} corruption rates")
    normalized_rates: list[float] = []
    for value in rate_values:
        if isinstance(value, (bool, np.bool_)) or not isinstance(
            value, (int, float, np.integer, np.floating)
        ):
            raise ValueError("each corruption rate must be a finite number in (0, 0.5]")
        numeric_value = float(value)
        if not isfinite(numeric_value) or not 0 < numeric_value <= 0.5:
            raise ValueError("each corruption rate must be a finite number in (0, 0.5]")
        normalized_rates.append(numeric_value)
    if len(set(normalized_rates)) != len(normalized_rates):
        raise ValueError("corruption rates must be distinct")

    if isinstance(seeds, (str, bytes)):
        raise ValueError("seeds must be a sequence of distinct unsigned integers")
    seed_values = tuple(seeds)
    if len(seed_values) < 3 or len(seed_values) > MAX_BENCHMARK_SEEDS:
        raise ValueError(
            f"select between 3 and {MAX_BENCHMARK_SEEDS} distinct random seeds"
        )
    normalized_seeds: list[int] = []
    for value in seed_values:
        if isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, np.integer)):
            raise ValueError("each seed must be an integer between 0 and 4294967295")
        numeric_seed = int(value)
        if not 0 <= numeric_seed <= 4_294_967_295:
            raise ValueError("each seed must be an integer between 0 and 4294967295")
        normalized_seeds.append(numeric_seed)
    if len(set(normalized_seeds)) != len(normalized_seeds):
        raise ValueError("random seeds must be distinct")

    if defects is None:
        selected_defects = SUPPORTED_DEFECTS
    else:
        if isinstance(defects, (str, bytes)):
            raise ValueError("defects must be a sequence of supported defect names")
        selected_defects = tuple(defects)
    if not selected_defects:
        raise ValueError("select at least one supported defect type")
    if len(set(selected_defects)) != len(selected_defects):
        raise ValueError("defect types must be distinct")
    unknown = [name for name in selected_defects if name not in SUPPORTED_DEFECTS]
    if unknown:
        raise ValueError("unsupported defect type(s): " + ", ".join(unknown))

    if isinstance(n_estimators, bool) or not isinstance(n_estimators, int):
        raise ValueError("n_estimators must be an integer between 1 and 500")
    if not 1 <= n_estimators <= MAX_ISOLATION_ESTIMATORS:
        raise ValueError("n_estimators must be an integer between 1 and 500")
    for value, name in (
        (contamination, "contamination"),
        (iqr_multiplier, "iqr_multiplier"),
        (robust_z_threshold, "robust_z_threshold"),
    ):
        if isinstance(value, (bool, np.bool_)):
            raise ValueError(f"{name} must be a finite positive number")
        try:
            numeric_value = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{name} must be a finite positive number") from exc
        if not isfinite(numeric_value) or numeric_value <= 0:
            raise ValueError(f"{name} must be a finite positive number")
        if name == "contamination" and numeric_value > 0.5:
            raise ValueError("contamination must be at most 0.5")

    return tuple(normalized_rates), tuple(normalized_seeds), tuple(selected_defects)


def _cell_truth(
    frame: pd.DataFrame,
    ground_truth: dict[str, Any],
    defect: str,
) -> np.ndarray:
    mask = np.zeros(frame.shape, dtype=bool)
    positions = {name: index for index, name in enumerate(frame.columns)}
    for record in ground_truth["cell_labels"]:
        if record["defect_type"] == defect:
            mask[int(record["row_index"]), positions[record["column"]]] = True
    return mask.reshape(-1)


def _row_truth(
    frame: pd.DataFrame,
    ground_truth: dict[str, Any],
    defect: str,
) -> np.ndarray:
    mask = np.zeros(len(frame), dtype=bool)
    for record in ground_truth["row_labels"]:
        if defect in record["defect_types"]:
            mask[int(record["row_index"])] = True
    return mask


def _categorical_consistency_predictions(
    frame: pd.DataFrame,
    columns: Sequence[str],
) -> np.ndarray:
    """Mirror the production whitespace and casefold-variant rule at cell level."""
    mask = np.zeros(frame.shape, dtype=bool)
    positions = {name: index for index, name in enumerate(frame.columns)}
    for name in columns:
        column_position = positions[name]
        variants_by_key: dict[str, dict[str, list[int]]] = {}
        for row_index, value in enumerate(frame[name].tolist()):
            if pd.isna(value):
                continue
            raw = str(value)
            trimmed = raw.strip()
            if raw != trimmed:
                mask[row_index, column_position] = True
            variants_by_key.setdefault(trimmed.casefold(), {}).setdefault(
                trimmed, []
            ).append(row_index)
        for variants in variants_by_key.values():
            if len(variants) > 1:
                for row_indexes in variants.values():
                    mask[row_indexes, column_position] = True
    return mask.reshape(-1)


def _numeric_parseability_predictions(
    frame: pd.DataFrame,
    columns: Sequence[str],
) -> np.ndarray:
    """Flag non-missing values that fail finite numeric parsing in known numeric columns."""
    mask = np.zeros(frame.shape, dtype=bool)
    positions = {name: index for index, name in enumerate(frame.columns)}
    for name in columns:
        raw = frame[name]
        parsed = pd.to_numeric(raw, errors="coerce")
        values = parsed.to_numpy(dtype=float, na_value=np.nan)
        observed = raw.notna().to_numpy(dtype=bool)
        mask[:, positions[name]] = observed & ~np.isfinite(values)
    return mask.reshape(-1)


def _clean_reference_preflight(frame: pd.DataFrame) -> dict[str, Any]:
    """Reject deterministic pre-existing defects that would contaminate injected labels.

    Statistical outliers are deliberately not rejected: unusual observations are
    not automatically invalid and detector flags on the clean reference count as
    false positives relative to the injected-defect ground truth.
    """
    numeric_columns, _ = _infer_numeric_columns(frame)
    categorical_columns = [
        name
        for name in frame.columns
        if name not in numeric_columns
        and any(
            isinstance(value, str) and bool(value)
            for value in frame[name].dropna().tolist()
        )
    ]
    categorical_predictions = _categorical_consistency_predictions(
        frame, categorical_columns
    )
    invalid_predictions = _numeric_parseability_predictions(frame, numeric_columns)
    findings = {
        "missing_cells": int(frame.isna().sum().sum()),
        "duplicate_rows": int(frame.duplicated(keep="first").sum()),
        "categorical_inconsistency_cells": int(np.count_nonzero(categorical_predictions)),
        "invalid_numeric_cells": int(np.count_nonzero(invalid_predictions)),
        "numeric_columns": list(numeric_columns),
        "categorical_columns": list(categorical_columns),
        "statistical_outliers_rejected": False,
    }
    blockers = {
        name: findings[name]
        for name in (
            "missing_cells",
            "duplicate_rows",
            "categorical_inconsistency_cells",
            "invalid_numeric_cells",
        )
        if findings[name] > 0
    }
    if blockers:
        details = ", ".join(f"{name}={count}" for name, count in blockers.items())
        raise ValueError(
            "clean reference preflight failed: "
            + details
            + "; resolve these deterministic defects before benchmarking"
        )
    return findings


def _row_predictions(row_count: int, indexes: set[int]) -> np.ndarray:
    mask = np.zeros(row_count, dtype=bool)
    if indexes:
        valid_indexes = np.fromiter(indexes, dtype=int)
        mask[valid_indexes] = True
    return mask


def _numerical_detector_cases(
    frame: pd.DataFrame,
    ground_truth: dict[str, Any],
    seed: int,
    *,
    n_estimators: int,
    contamination: float,
    iqr_multiplier: float,
    robust_z_threshold: float,
) -> list[dict[str, Any]]:
    columns = list(ground_truth["numeric_columns_used"])
    numeric, _ = dataset_anomaly._numeric_candidates(frame, columns)
    if not numeric:
        reason = "No reference numeric columns remained eligible after corruption."
        return [
            {"detector": name, "unit": "row", "skip_reason": reason}
            for name in DETECTORS_BY_DEFECT["numerical_anomalies"]
        ]

    truth = _row_truth(frame, ground_truth, "numerical_anomalies")
    cases: list[dict[str, Any]] = []
    detector_calls: list[tuple[str, Callable[[], tuple[dict[str, Any], set[int]]]]] = [
        (
            "iqr",
            lambda: dataset_anomaly._run_iqr(
                numeric, iqr_multiplier, len(frame)
            ),
        ),
        (
            "robust_zscore",
            lambda: dataset_anomaly._run_robust_zscore(
                numeric, robust_z_threshold, len(frame)
            ),
        ),
        (
            "isolation_forest",
            lambda: dataset_anomaly._run_isolation_forest(
                numeric,
                len(frame),
                contamination,
                seed,
                n_estimators,
                len(frame),
            ),
        ),
    ]
    for detector_name, detector_call in detector_calls:
        result, flagged_indexes = detector_call()
        if result.get("status") != "completed":
            cases.append(
                {
                    "detector": detector_name,
                    "unit": "row",
                    "skip_reason": result.get("reason", "Detector was skipped."),
                }
            )
            continue
        cases.append(
            {
                "detector": detector_name,
                "unit": "row",
                "truth": truth,
                "predict": lambda indexes=set(flagged_indexes): _row_predictions(
                    len(frame), indexes
                ),
            }
        )
    return cases


def _detector_cases(
    frame: pd.DataFrame,
    ground_truth: dict[str, Any],
    defect: str,
    seed: int,
    *,
    n_estimators: int,
    contamination: float,
    iqr_multiplier: float,
    robust_z_threshold: float,
) -> list[dict[str, Any]]:
    if defect == "missingness":
        return [{
            "detector": "missingness_rule",
            "unit": "cell",
            "truth": _cell_truth(frame, ground_truth, defect),
            "predict": lambda: frame.isna().to_numpy(dtype=bool).reshape(-1),
        }]
    if defect == "duplicates":
        return [{
            "detector": "exact_duplicate_rule",
            "unit": "row",
            "truth": _row_truth(frame, ground_truth, defect),
            "predict": lambda: frame.duplicated(keep="first").to_numpy(dtype=bool),
        }]
    if defect == "categorical_inconsistency":
        columns = list(ground_truth["categorical_columns_used"])
        return [{
            "detector": "categorical_consistency_rule",
            "unit": "cell",
            "truth": _cell_truth(frame, ground_truth, defect),
            "predict": lambda: _categorical_consistency_predictions(frame, columns),
        }]
    if defect == "invalid_values":
        columns = list(ground_truth["numeric_columns_used"])
        return [{
            "detector": "numeric_parseability_rule",
            "unit": "cell",
            "truth": _cell_truth(frame, ground_truth, defect),
            "predict": lambda: _numeric_parseability_predictions(frame, columns),
        }]
    return _numerical_detector_cases(
        frame,
        ground_truth,
        seed,
        n_estimators=n_estimators,
        contamination=contamination,
        iqr_multiplier=iqr_multiplier,
        robust_z_threshold=robust_z_threshold,
    )


def _measure_detector(case: dict[str, Any]) -> dict[str, Any]:
    """Measure prediction time and Python-traced peak allocation for one detector."""
    was_tracing = tracemalloc.is_tracing()
    if not was_tracing:
        tracemalloc.start()
    tracemalloc.reset_peak()
    baseline_bytes, _ = tracemalloc.get_traced_memory()
    started = perf_counter()
    try:
        predictions = np.asarray(case["predict"](), dtype=bool)
        elapsed = perf_counter() - started
        _, peak_bytes = tracemalloc.get_traced_memory()
    finally:
        if not was_tracing and tracemalloc.is_tracing():
            tracemalloc.stop()

    truth = np.asarray(case["truth"], dtype=bool)
    if predictions.ndim != 1 or predictions.shape != truth.shape:
        raise RuntimeError("detector predictions must match the one-dimensional ground truth")
    report = evaluate_binary_detector(truth.tolist(), predictions.tolist())
    peak_delta = max(0, int(peak_bytes - baseline_bytes))
    metrics = {
        "precision": report["precision"],
        "recall": report["recall"],
        "f1": report["f1"],
        "accuracy": report["accuracy"],
        "runtime_seconds": round(float(elapsed), 6),
        "python_tracemalloc_peak_bytes": peak_delta,
    }
    return {
        "support": report["support"],
        "predicted_positive_count": report["predicted_positive_count"],
        "confusion_counts": report["confusion_counts"],
        "metrics": metrics,
    }


def run_synthetic_detector_benchmark(
    frame: pd.DataFrame,
    *,
    rates: Sequence[float] = DEFAULT_BENCHMARK_RATES,
    seeds: Sequence[int] = DEFAULT_BENCHMARK_SEEDS,
    defects: Sequence[str] | None = None,
    n_estimators: int = 100,
    contamination: float = 0.05,
    iqr_multiplier: float = 1.5,
    robust_z_threshold: float = 3.5,
) -> dict[str, Any]:
    """Run defect-specific detectors over rates and at least three distinct seeds.

    Cell-level defects are evaluated over all cells in the corrupted frame.
    Duplicate and numerical anomaly detectors are evaluated at row level because
    those production detectors return row flags. Timing excludes corruption
    generation and metric calculation. Memory is Python tracemalloc peak delta;
    it does not include all native NumPy/scikit-learn allocations.
    """
    rates, seeds, defects = _validate_benchmark_request(
        frame,
        rates,
        seeds,
        defects,
        n_estimators,
        contamination,
        iqr_multiplier,
        robust_z_threshold,
    )
    reference_preflight = _clean_reference_preflight(frame)
    source = frame.copy(deep=True)
    experiments: dict[tuple[float, str, str], dict[str, Any]] = {}
    for rate in rates:
        for defect in defects:
            for detector in DETECTORS_BY_DEFECT[defect]:
                experiments[(rate, defect, detector)] = {
                    "rate": rate,
                    "defect_type": defect,
                    "detector": detector,
                    "evaluation_unit": UNIT_BY_DEFECT[defect],
                    "runs": [],
                    "skipped_runs": [],
                }

    for rate in rates:
        for defect in defects:
            for seed in seeds:
                corruption = inject_synthetic_corruption(
                    source,
                    rate=rate,
                    seed=seed,
                    defects=[defect],
                )
                defect_info = corruption.ground_truth["defects"][defect]
                if defect_info["status"] != "completed":
                    for detector in DETECTORS_BY_DEFECT[defect]:
                        experiments[(rate, defect, detector)]["skipped_runs"].append({
                            "seed": seed,
                            "reason": defect_info.get("skipped_reason") or "Defect injection was skipped.",
                        })
                    continue

                cases = _detector_cases(
                    corruption.frame,
                    corruption.ground_truth,
                    defect,
                    seed,
                    n_estimators=n_estimators,
                    contamination=float(contamination),
                    iqr_multiplier=float(iqr_multiplier),
                    robust_z_threshold=float(robust_z_threshold),
                )
                case_by_name = {case["detector"]: case for case in cases}
                for detector in DETECTORS_BY_DEFECT[defect]:
                    experiment = experiments[(rate, defect, detector)]
                    case = case_by_name.get(detector)
                    if case is None or case.get("skip_reason"):
                        experiment["skipped_runs"].append({
                            "seed": seed,
                            "reason": (
                                case.get("skip_reason") if case else "Detector did not return a result."
                            ),
                        })
                        continue
                    measured = _measure_detector(case)
                    experiment["runs"].append({
                        "seed": seed,
                        "injected_count": int(defect_info["injected_count"]),
                        **measured,
                    })

    experiment_results: list[dict[str, Any]] = []
    for key in sorted(experiments, key=lambda item: (item[0], item[1], item[2])):
        experiment = experiments[key]
        complete = (
            len(experiment["runs"]) == len(seeds)
            and not experiment["skipped_runs"]
        )
        result = {
            **experiment,
            "status": "completed" if complete else "incomplete",
            "expected_seed_count": len(seeds),
            "completed_seed_count": len(experiment["runs"]),
            "aggregate": (
                aggregate_seed_metrics([
                    {"seed": run["seed"], "metrics": run["metrics"]}
                    for run in experiment["runs"]
                ])
                if complete else None
            ),
        }
        experiment_results.append(result)

    pd.testing.assert_frame_equal(source, frame)
    return {
        "schema_version": 1,
        "source_shape": {"rows": int(frame.shape[0]), "columns": int(frame.shape[1])},
        "reference_preflight": reference_preflight,
        "configuration": {
            "rates": list(rates),
            "seeds": list(seeds),
            "defects": list(defects),
            "iqr_multiplier": float(iqr_multiplier),
            "robust_z_threshold": float(robust_z_threshold),
            "contamination": float(contamination),
            "n_estimators": n_estimators,
        },
        "experiments": experiment_results,
        "method_notes": [
            "Each trial injects one defect type into a fresh in-memory copy of the clean reference frame.",
            "Missingness, categorical inconsistency, and invalid-value metrics are cell-level; duplicate and numerical-anomaly metrics are row-level.",
            "The numerical IQR, robust-Z, and Isolation Forest adapters reuse the production anomaly implementation and its numeric-column eligibility rules.",
            "The categorical rule mirrors whitespace and casefold-variant findings; a legitimate case variant can therefore be a false positive.",
            "Invalid-value evaluation uses numeric columns identified from the clean reference frame as the known schema for this controlled experiment.",
            "Timing covers detector prediction only and excludes corruption generation and metric calculation.",
            "Memory is the Python-traced peak allocation delta; native NumPy and scikit-learn allocations may not be fully represented.",
            "Every requested seed must complete for an aggregate to be reported; skipped runs are retained and never silently dropped.",
            "The clean-reference preflight rejects pre-existing missing cells, exact duplicate rows, detected categorical whitespace/case variants, and invalid values in inferred numeric-like columns.",
            "Statistical outliers are not rejected by preflight; if a detector flags them, they count as false positives against injected-only labels.",
            "The source DataFrame is not modified and no corrupted file or report is persisted.",
            "Synthetic corruption rates are controlled settings and are not estimates of real-world defect prevalence.",
        ],
    }
