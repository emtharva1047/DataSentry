"""Run the UCI Bike Sharing Isolation Forest contamination-sensitivity sweep."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from app.services.dataset_bike_contamination_sensitivity import (
    DEFAULT_CONTAMINATION_VALUES,
    run_bike_sharing_contamination_sensitivity,
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
        description="Measure Isolation Forest contamination sensitivity on UCI Bike Sharing."
    )
    parser.add_argument("--rates", default="0.01,0.05,0.10")
    parser.add_argument("--seeds", default="42,123,2026")
    parser.add_argument(
        "--contaminations",
        default=",".join(str(value) for value in DEFAULT_CONTAMINATION_VALUES),
    )
    parser.add_argument("--n-estimators", type=int, default=100)
    parser.add_argument("--iqr-multiplier", type=float, default=1.5)
    parser.add_argument("--robust-z-threshold", type=float, default=3.5)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("research-results/uci-bike-sharing-if-sensitivity.json"),
    )
    args = parser.parse_args()

    report = run_bike_sharing_contamination_sensitivity(
        rates=_csv_values(args.rates, float),
        seeds=_csv_values(args.seeds, int),
        contamination_values=_csv_values(args.contaminations, float),
        n_estimators=args.n_estimators,
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
    for sweep in report["sweeps"]:
        for experiment in sweep["experiments"]:
            if experiment["detector"] != "isolation_forest":
                continue
            if experiment["status"] != "completed":
                summary.append({
                    "contamination": sweep["contamination"],
                    "rate": experiment["rate"],
                    "status": experiment["status"],
                    "skipped_runs": experiment["skipped_runs"],
                })
                continue
            metrics = experiment["aggregate"]["metrics"]
            prevalence = experiment["prevalence_aggregate"]["metrics"]
            summary.append({
                "contamination": sweep["contamination"],
                "rate": experiment["rate"],
                "status": experiment["status"],
                "ground_truth_row_prevalence_mean": prevalence["ground_truth_row_prevalence"]["mean"],
                "predicted_row_prevalence_mean": prevalence["predicted_row_prevalence"]["mean"],
                "precision_mean": metrics["precision"]["mean"],
                "recall_mean": metrics["recall"]["mean"],
                "f1_mean": metrics["f1"]["mean"],
                "f1_sample_sd": metrics["f1"]["sample_standard_deviation"],
                "runtime_seconds_mean": metrics["runtime_seconds"]["mean"],
            })
    print(json.dumps({
        "report_path": str(destination),
        "status": report["status"],
        "dataset": report["dataset"],
        "configuration": report["configuration"],
        "control_checks_passed": report["control_checks_passed"],
        "control_checks": report["control_checks"],
        "isolation_forest_summary": summary,
    }, indent=2, ensure_ascii=False, allow_nan=False))
    return 0 if report["status"] == "completed" else 2


if __name__ == "__main__":
    sys.exit(main())
