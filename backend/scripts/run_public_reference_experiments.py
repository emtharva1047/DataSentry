"""Execute the public UCI Wine detector and downstream ML research experiments.

Run from the backend directory:
python -m scripts.run_public_reference_experiments --output /tmp/uci-wine-experiment.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from app.services.dataset_reference_experiment import (
    run_wine_reference_experiment,
)
from app.services.dataset_benchmark import (
    DEFAULT_BENCHMARK_RATES,
    DEFAULT_BENCHMARK_SEEDS,
)


def _csv_values(value: str, converter):
    try:
        parts = [part.strip() for part in value.split(",") if part.strip()]
        if not parts:
            raise ValueError("at least one value is required")
        return tuple(converter(part) for part in parts)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run DataSentry's reproducible UCI Wine research experiment."
    )
    parser.add_argument(
        "--rates",
        default=",".join(str(value) for value in DEFAULT_BENCHMARK_RATES),
        help="Comma-separated detector corruption rates.",
    )
    parser.add_argument(
        "--seeds",
        default=",".join(str(value) for value in DEFAULT_BENCHMARK_SEEDS),
        help="At least three distinct random seeds.",
    )
    parser.add_argument(
        "--n-estimators",
        type=int,
        default=100,
        help="Isolation Forest estimator count.",
    )
    parser.add_argument(
        "--ml-corruption-rates",
        default="0.05,0.10,0.20",
        help="Comma-separated training-only categorical corruption rates.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("research-results/uci-wine-reference-experiment.json"),
        help="JSON report destination.",
    )
    args = parser.parse_args()

    rates = _csv_values(args.rates, float)
    seeds = _csv_values(args.seeds, int)
    report = run_wine_reference_experiment(
        rates=rates,
        seeds=seeds,
        n_estimators=args.n_estimators,
        ml_corruption_rates=_csv_values(args.ml_corruption_rates, float),
    )
    rendered = json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False)
    destination = args.output.expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(rendered + "\n", encoding="utf-8")

    summary = {
        "report_path": str(destination),
        "dataset": report["dataset"],
        "detector_experiments": [
            {
                "rate": item["rate"],
                "defect_type": item["defect_type"],
                "detector": item["detector"],
                "status": item["status"],
                "completed_seed_count": item["completed_seed_count"],
                "aggregate_metrics": (
                    item["aggregate"]["metrics"] if item["aggregate"] else None
                ),
                "skipped_runs": item["skipped_runs"],
            }
            for item in report["detector_benchmark"]["experiments"]
        ],
        "downstream_classification": [
            {
                "corruption_rate": experiment["configuration"]["corruption_rate"],
                "aggregates": experiment["aggregates"],
                "paired_cleaned_minus_corrupted_macro_f1": experiment[
                    "paired_cleaned_minus_corrupted_macro_f1"
                ],
                "per_seed_test_fingerprints": [
                    {
                        "seed": item["seed"],
                        "clean_test_sha256": item["split"]["clean_test_sha256"],
                        "test_partition_untouched": item["split"][
                            "test_partition_untouched"
                        ],
                    }
                    for item in experiment["per_seed"]
                ],
            }
            for experiment in report["downstream_classification"]["experiments"]
        ],
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False, allow_nan=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
