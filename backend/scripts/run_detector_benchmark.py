"""Run a reproducible detector benchmark against a local clean CSV.

Example (from the backend directory):
python -m scripts.run_detector_benchmark reference.csv --output benchmark.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import sklearn

from app.services.dataset_benchmark import (
    DEFAULT_BENCHMARK_RATES,
    DEFAULT_BENCHMARK_SEEDS,
    run_synthetic_detector_benchmark,
)


def _csv_numbers(value: str, converter):
    try:
        return tuple(converter(part.strip()) for part in value.split(",") if part.strip())
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def main() -> int:
    parser = argparse.ArgumentParser(description="Run DataSentry's seeded detector benchmark.")
    parser.add_argument("input_csv", type=Path, help="Clean reference CSV; it is read-only.")
    parser.add_argument(
        "--rates",
        default=",".join(str(value) for value in DEFAULT_BENCHMARK_RATES),
        help="Comma-separated corruption rates (default: 0.01,0.05,0.10).",
    )
    parser.add_argument(
        "--seeds",
        default=",".join(str(value) for value in DEFAULT_BENCHMARK_SEEDS),
        help="At least three distinct integer seeds (default: 42,123,2026).",
    )
    parser.add_argument(
        "--defects",
        default="missingness,duplicates,categorical_inconsistency,invalid_values,numerical_anomalies",
        help="Comma-separated supported defect types.",
    )
    parser.add_argument("--estimators", type=int, default=100, help="Isolation Forest trees.")
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional JSON output path. Without it, the report is printed to stdout.",
    )
    args = parser.parse_args()

    source_path = args.input_csv.expanduser().resolve()
    if not source_path.is_file():
        parser.error("input_csv must be an existing regular file")

    try:
        rates = _csv_numbers(args.rates, float)
        seeds = _csv_numbers(args.seeds, int)
        defects = tuple(part.strip() for part in args.defects.split(",") if part.strip())
        source_bytes = source_path.read_bytes()
        frame = pd.read_csv(source_path, dtype=str)
        report = run_synthetic_detector_benchmark(
            frame,
            rates=rates,
            seeds=seeds,
            defects=defects,
            n_estimators=args.estimators,
        )
    except (OSError, UnicodeError, pd.errors.ParserError, ValueError) as exc:
        parser.error(str(exc))

    payload = {
        "provenance": {
            "source_filename": source_path.name,
            "source_sha256": hashlib.sha256(source_bytes).hexdigest(),
            "source_size_bytes": len(source_bytes),
            "source_shape": {"rows": int(frame.shape[0]), "columns": int(frame.shape[1])},
            "python_version": platform.python_version(),
            "pandas_version": pd.__version__,
            "numpy_version": np.__version__,
            "scikit_learn_version": sklearn.__version__,
        },
        "benchmark": report,
    }
    rendered = json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False)
    if args.output:
        destination = args.output.expanduser().resolve()
        if destination == source_path:
            parser.error("output path must not overwrite the clean reference CSV")
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    sys.exit(main())
