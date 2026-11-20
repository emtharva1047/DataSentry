"""Pure case-only categorical detector evaluation on public UCI references."""
from __future__ import annotations

from typing import Any, Sequence

from .dataset_benchmark import DEFAULT_BENCHMARK_RATES, DEFAULT_BENCHMARK_SEEDS, run_synthetic_detector_benchmark
from .dataset_bike_detector_experiment import build_bike_sharing_detector_reference
from .dataset_reference_experiment import build_wine_reference


def run_case_only_public_reference_benchmark(
    *,
    rates: Sequence[float] = DEFAULT_BENCHMARK_RATES,
    seeds: Sequence[int] = DEFAULT_BENCHMARK_SEEDS,
) -> dict[str, Any]:
    """Evaluate pure case swaps independently from whitespace corruption.

    Both public reference builders provide clean frames with semantic string
    categories. Each trial swaps letter case only: it does not add whitespace.
    The production quality-v2 detector is evaluated against exact cell labels.
    """
    wine_frame, _, wine_metadata = build_wine_reference()
    bike_frame, bike_metadata = build_bike_sharing_detector_reference()

    references = (
        ("uci_wine", wine_frame, wine_metadata),
        ("uci_bike_sharing", bike_frame, bike_metadata),
    )
    results: dict[str, Any] = {}
    for name, frame, metadata in references:
        benchmark = run_synthetic_detector_benchmark(
            frame,
            rates=rates,
            seeds=seeds,
            defects=("categorical_inconsistency",),
            categorical_mode="case_only",
        )
        experiments = benchmark["experiments"]
        complete = bool(experiments) and all(
            item["status"] == "completed"
            and item["completed_seed_count"] == len(seeds)
            and not item["skipped_runs"]
            for item in experiments
        )
        results[name] = {
            "dataset": metadata,
            "benchmark": benchmark,
            "status": "completed" if complete else "incomplete",
        }

    return {
        "schema_version": 1,
        "experiment": "pure_case_only_categorical_consistency",
        "configuration": {
            "categorical_mode": "case_only",
            "rates": [float(rate) for rate in rates],
            "seeds": [int(seed) for seed in seeds],
            "ground_truth_schema_version": 2,
        },
        "references": results,
        "status": (
            "completed"
            if all(item["status"] == "completed" for item in results.values())
            else "incomplete"
        ),
        "method_notes": [
            "Only letter case is changed; injected values receive no leading or trailing whitespace.",
            "Wine uses the documented derived alcohol_band feature; Bike Sharing uses semantic labels for its integer-coded categorical predictors.",
            "The production quality-v2 canonical-spelling heuristic is reused without a benchmark-specific implementation.",
            "Each public reference is checked for pre-existing deterministic quality defects before injection.",
            "The modal-spelling heuristic is a review aid: a legitimate minority spelling can be flagged, and ties remain ambiguous.",
            "These controlled synthetic results do not estimate real-world error rates or establish universal detector performance.",
        ],
    }
