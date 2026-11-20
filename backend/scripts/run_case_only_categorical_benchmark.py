"""Run isolated pure case-only categorical detector benchmarks."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from app.services.dataset_case_only_experiment import run_case_only_public_reference_benchmark


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
        description="Evaluate pure case-only categorical corruption on UCI Wine and Bike Sharing."
    )
    parser.add_argument("--rates", default="0.01,0.05,0.10")
    parser.add_argument("--seeds", default="42,123,2026")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("research-results/pure-case-only-categorical.json"),
    )
    args = parser.parse_args()
    report = run_case_only_public_reference_benchmark(
        rates=_csv_values(args.rates, float),
        seeds=_csv_values(args.seeds, int),
    )
    destination = args.output.expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    summary = {}
    for name, reference in report["references"].items():
        summary[name] = [
            {
                "rate": item["rate"],
                "detector": item["detector"],
                "status": item["status"],
                "aggregate": item["aggregate"],
            }
            for item in reference["benchmark"]["experiments"]
        ]
    print(json.dumps({
        "report_path": str(destination),
        "status": report["status"],
        "configuration": report["configuration"],
        "references": summary,
    }, indent=2, ensure_ascii=False, allow_nan=False))
    return 0 if report["status"] == "completed" else 2


if __name__ == "__main__":
    sys.exit(main())
