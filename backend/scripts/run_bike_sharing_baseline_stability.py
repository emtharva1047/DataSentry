"""Run UCI Bike Sharing clean-baseline rolling-origin stability evaluation."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from app.services.dataset_bike_categories import CATEGORY_LABELS, semantic_category
from app.services.dataset_bike_reference_experiment import (
    CATEGORICAL_COLUMNS,
    NUMERIC_COLUMNS,
    TARGET_COLUMN,
    build_bike_sharing_reference,
)
from app.services.dataset_regression_stability import (
    DEFAULT_TEST_WINDOW_FRACTION,
    DEFAULT_TRAIN_FRACTIONS,
    run_rolling_origin_baseline_stability,
)


def _csv_floats(value: str) -> tuple[float, ...]:
    try:
        parts = [part.strip() for part in value.split(",") if part.strip()]
        if not parts:
            raise ValueError("at least one fraction is required")
        return tuple(float(part) for part in parts)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Measure clean Ridge baseline variation across future Bike Sharing windows."
    )
    parser.add_argument(
        "--train-fractions",
        default=",".join(str(value) for value in DEFAULT_TRAIN_FRACTIONS),
        help="Expanding training-prefix fractions; future test windows must not overlap.",
    )
    parser.add_argument(
        "--test-window-fraction",
        type=float,
        default=DEFAULT_TEST_WINDOW_FRACTION,
    )
    parser.add_argument("--alpha", type=float, default=1.0)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("research-results/uci-bike-sharing-rolling-origin-baseline.json"),
    )
    args = parser.parse_args()

    features, source_frame, metadata = build_bike_sharing_reference()
    for column in CATEGORICAL_COLUMNS:
        features[column] = semantic_category(features[column], column)
    frame = features.copy(deep=True)
    frame[TARGET_COLUMN] = source_frame[TARGET_COLUMN].to_numpy(copy=True)

    report = run_rolling_origin_baseline_stability(
        frame,
        target_column=TARGET_COLUMN,
        feature_columns=list(features.columns),
        numeric_columns=NUMERIC_COLUMNS,
        categorical_columns=CATEGORICAL_COLUMNS,
        train_fractions=_csv_floats(args.train_fractions),
        test_window_fraction=args.test_window_fraction,
        alpha=args.alpha,
    )
    report["dataset"] = {
        **metadata,
        "semantic_regression_frame_sha256": report["clean_reference_frame_sha256"],
        "categorical_label_maps": {
            column: {str(code): label for code, label in mapping.items()}
            for column, mapping in CATEGORY_LABELS.items()
        },
    }

    destination = args.output.expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "report_path": str(destination),
        "dataset": report["dataset"],
        "configuration": report["configuration"],
        "aggregates": report["aggregates"],
        "per_window": report["per_window"],
        "limitations": report["limitations"],
    }, indent=2, ensure_ascii=False, allow_nan=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
