"""Run the UCI Bike Sharing mixed-type detector benchmark."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from app.services.dataset_bike_detector_experiment import (
    run_bike_sharing_detector_benchmark,
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
        description="Run DataSentry's UCI Bike Sharing detector benchmark."
    )
    parser.add_argument("--rates", default="0.01,0.05,0.10")
    parser.add_argument("--seeds", default="42,123,2026")
    parser.add_argument("--n-estimators", type=int, default=100)
    parser.add_argument("--contamination", type=float, default=0.05)
    parser.add_argument("--iqr-multiplier", type=float, default=1.5)
    parser.add_argument("--robust-z-threshold", type=float, default=3.5)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("research-results/uci-bike-sharing-detectors.json"),
    )
    args = parser.parse_args()

    report = run_bike_sharing_detector_benchmark(
        rates=_csv_values(args.rates, float),
        seeds=_csv_values(args.seeds, int),
        n_estimators=args.n_estimators,
        contamination=args.contamination,
        iqr_multiplier=args.iqr_multiplier,
        robust_z_threshold=args.robust_z_threshold,
    )
    destination = args.output.expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )

    summary = []
    for experiment in report["benchmark"]["experiments"]:
        aggregate = experiment["aggregate"]
        summary.append({
            "rate": experiment["rate"],
            "defect_type": experiment["defect_type"],
            "detector": experiment["detector"],
            "status": experiment["status"],
            "completed_seed_count": experiment["completed_seed_count"],
            "skipped_runs": experiment["skipped_runs"],
            "aggregate": aggregate,
        })
    print(json.dumps({
        "report_path": str(destination),
        "status": report["status"],
        "dataset": report["dataset"],
        "configuration": report["benchmark"]["configuration"],
        "reference_preflight": report["benchmark"]["reference_preflight"],
        "experiments": summary,
    }, indent=2, ensure_ascii=False, allow_nan=False))
    return 0 if report["status"] == "completed" else 2


if __name__ == "__main__":
    sys.exit(main())
