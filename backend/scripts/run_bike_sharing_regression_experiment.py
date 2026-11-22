"""Run UCI Bike Sharing training-only missingness and duplicate regression experiments."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
from app.services.dataset_bike_reference_experiment import run_bike_sharing_regression_experiment
from app.services.dataset_regression_experiment import DEFAULT_REGRESSION_SEEDS


def _csv_values(value: str, converter):
    try:
        parts = [part.strip() for part in value.split(",") if part.strip()]
        if not parts:
            raise ValueError("at least one value is required")
        return tuple(converter(part) for part in parts)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def main() -> int:
    parser = argparse.ArgumentParser(description="Run DataSentry's UCI Bike Sharing downstream regression experiments.")
    parser.add_argument("--rates", default="0.01,0.05,0.10", help="Training-feature missingness rates.")
    parser.add_argument("--seeds", default=",".join(str(x) for x in DEFAULT_REGRESSION_SEEDS))
    parser.add_argument("--corruption-types", default="missingness,duplicates", help="Distinct training-only corruption types: missingness,duplicates.")
    parser.add_argument("--test-size", type=float, default=0.25)
    parser.add_argument("--alpha", type=float, default=1.0)
    parser.add_argument("--output", type=Path, default=Path("research-results/uci-bike-sharing-regression.json"))
    args = parser.parse_args()
    report = run_bike_sharing_regression_experiment(
        rates=_csv_values(args.rates, float), seeds=_csv_values(args.seeds, int),
        test_size=args.test_size, alpha=args.alpha,
        corruption_types=_csv_values(args.corruption_types, str),
    )
    destination = args.output.expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    downstream = report["downstream_regression"]
    def summarize(items):
        return [
            {
                "corruption_type": item["configuration"]["corruption_type"],
                "corruption_rate": item["configuration"]["corruption_rate"],
                "aggregates": item["aggregates"],
                "paired_cleaned_minus_corrupted": item["paired_cleaned_minus_corrupted"],
                "test_partitions": [
                    {"seed": run["seed"], "sha256": run["split"]["clean_test_sha256"],
                     "untouched": run["split"]["test_partition_untouched"]}
                    for run in item["per_seed"]
                ],
            }
            for item in items
        ]
    print(json.dumps({
        "report_path": str(destination),
        "dataset": report["dataset"],
        "corruption_types": downstream["corruption_types"],
        "missingness_experiments": summarize(downstream["experiments"]),
        "duplicate_experiments": summarize(downstream["duplicate_experiments"]),
    }, indent=2, ensure_ascii=False, allow_nan=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
