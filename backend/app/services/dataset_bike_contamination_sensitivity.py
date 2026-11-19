"""Contamination-sensitivity experiments for Isolation Forest on UCI Bike Sharing."""
from __future__ import annotations

from typing import Any, Sequence

import numpy as np
import pandas as pd

from .dataset_benchmark import (
    DEFAULT_BENCHMARK_RATES,
    DEFAULT_BENCHMARK_SEEDS,
    run_synthetic_detector_benchmark,
)
from .dataset_bike_detector_experiment import build_bike_sharing_detector_reference
from .dataset_research import aggregate_seed_metrics

DEFAULT_CONTAMINATION_VALUES = (0.01, 0.05, 0.10)
MAX_CONTAMINATION_VALUES = 5


def _validate_contamination_values(values: Sequence[float]) -> tuple[float, ...]:
    if isinstance(values, (str, bytes)):
        raise ValueError("contamination_values must be a sequence of numeric values")
    try:
        selected = tuple(values)
    except TypeError as exc:
        raise ValueError("contamination_values must be a sequence of numeric values") from exc
    if not 2 <= len(selected) <= MAX_CONTAMINATION_VALUES:
        raise ValueError(
            f"select between 2 and {MAX_CONTAMINATION_VALUES} distinct contamination values"
        )
    normalized: list[float] = []
    for value in selected:
        if isinstance(value, (bool, np.bool_)) or not isinstance(
            value, (int, float, np.integer, np.floating)
        ):
            raise ValueError("each contamination value must be finite and in (0, 0.5]")
        numeric = float(value)
        if not np.isfinite(numeric) or not 0 < numeric <= 0.5:
            raise ValueError("each contamination value must be finite and in (0, 0.5]")
        normalized.append(numeric)
    if len(set(normalized)) != len(normalized):
        raise ValueError("contamination values must be distinct")
    return tuple(normalized)


def _add_row_prevalence(experiment: dict[str, Any], row_count: int) -> None:
    """Expose actual injected and predicted row prevalence beside confusion counts."""
    for run in experiment["runs"]:
        counts = run["confusion_counts"]
        actual = int(counts["true_positive"] + counts["false_negative"])
        predicted = int(counts["true_positive"] + counts["false_positive"])
        if actual != int(run["support"]):
            raise RuntimeError("ground-truth support does not match confusion counts")
        run["ground_truth_positive_rows"] = actual
        run["ground_truth_row_prevalence"] = round(actual / row_count, 6)
        run["predicted_positive_rows"] = predicted
        run["predicted_row_prevalence"] = round(predicted / row_count, 6)

    if experiment["status"] == "completed":
        experiment["prevalence_aggregate"] = aggregate_seed_metrics([
            {
                "seed": run["seed"],
                "metrics": {
                    "ground_truth_row_prevalence": run["ground_truth_row_prevalence"],
                    "predicted_row_prevalence": run["predicted_row_prevalence"],
                },
            }
            for run in experiment["runs"]
        ])
    else:
        experiment["prevalence_aggregate"] = None


def _control_invariance(sweeps: list[dict[str, Any]], rates: Sequence[float]) -> dict[str, Any]:
    """Check that IF contamination does not change the IQR or robust-Z controls."""
    controls: dict[str, Any] = {}
    for detector in ("iqr", "robust_zscore"):
        controls[detector] = {}
        for rate in rates:
            signatures = []
            for sweep in sweeps:
                match = next(
                    (
                        item for item in sweep["experiments"]
                        if item["rate"] == float(rate) and item["detector"] == detector
                    ),
                    None,
                )
                if match is None or match["status"] != "completed":
                    signatures.append(None)
                    continue
                signatures.append([
                    {
                        "seed": run["seed"],
                        "confusion_counts": run["confusion_counts"],
                        "quality_metrics": {
                            key: run["metrics"][key]
                            for key in ("precision", "recall", "f1", "accuracy")
                        },
                    }
                    for run in match["runs"]
                ])
            controls[detector][str(float(rate))] = {
                "invariant_across_contamination": (
                    bool(signatures)
                    and signatures[0] is not None
                    and all(value == signatures[0] for value in signatures[1:])
                ),
                "compared_settings": len(signatures),
            }
    return controls


def run_bike_sharing_contamination_sensitivity(
    *,
    rates: Sequence[float] = DEFAULT_BENCHMARK_RATES,
    seeds: Sequence[int] = DEFAULT_BENCHMARK_SEEDS,
    contamination_values: Sequence[float] = DEFAULT_CONTAMINATION_VALUES,
    n_estimators: int = 100,
    iqr_multiplier: float = 1.5,
    robust_z_threshold: float = 3.5,
) -> dict[str, Any]:
    """Sweep Isolation Forest contamination against exact row-level ground truth.

    Each contamination setting receives the same clean reference, corruption
    rates, and seeds. Only Isolation Forest's contamination parameter changes.
    IQR and robust-Z results are retained as controls. Cell-level corruption
    rate is not assumed to equal row-level anomaly prevalence; both actual
    ground-truth and predicted row prevalence are recorded for every seed.
    """
    selected_contaminations = _validate_contamination_values(contamination_values)
    frame, metadata = build_bike_sharing_detector_reference()
    sweep_results: list[dict[str, Any]] = []

    for contamination in selected_contaminations:
        benchmark = run_synthetic_detector_benchmark(
            frame,
            rates=rates,
            seeds=seeds,
            defects=("numerical_anomalies",),
            n_estimators=n_estimators,
            contamination=contamination,
            iqr_multiplier=iqr_multiplier,
            robust_z_threshold=robust_z_threshold,
        )
        experiments = benchmark["experiments"]
        for experiment in experiments:
            _add_row_prevalence(experiment, len(frame))
        complete = all(item["status"] == "completed" for item in experiments)
        sweep_results.append({
            "contamination": contamination,
            "status": "completed" if complete else "incomplete",
            "reference_preflight": benchmark["reference_preflight"],
            "configuration": benchmark["configuration"],
            "experiments": experiments,
        })

    complete = all(item["status"] == "completed" for item in sweep_results)
    control_checks = _control_invariance(sweep_results, rates)
    return {
        "schema_version": 1,
        "experiment": "uci_bike_sharing_isolation_forest_contamination_sensitivity",
        "dataset": metadata,
        "status": "completed" if complete else "incomplete",
        "configuration": {
            "rates": [float(value) for value in rates],
            "seeds": [int(value) for value in seeds],
            "contamination_values": list(selected_contaminations),
            "n_estimators": int(n_estimators),
            "iqr_multiplier": float(iqr_multiplier),
            "robust_z_threshold": float(robust_z_threshold),
        },
        "sweeps": sweep_results,
        "control_checks": control_checks,
        "method_notes": [
            "Each contamination setting reuses the same clean semantic reference, corruption rates, and random seeds.",
            "The synthetic corruption rate is cell-level; the actual row-level anomaly prevalence is measured from TP+FN and reported per seed.",
            "Isolation Forest contamination is a model threshold parameter, not an estimate of the cell-level corruption rate.",
            "IQR and robust-Z are retained as controls and should be invariant to the Isolation Forest contamination setting.",
            "All detector runs use the production anomaly implementations and exact injected row labels.",
            "An aggregate is retained only when every requested seed completes; skipped runs are never silently dropped.",
            "Runtime excludes corruption generation and metric calculation. Python tracemalloc is a partial allocation proxy and may omit native allocations.",
            "The source DataFrame is not modified; no corrupted dataset is persisted.",
        ],
    }
