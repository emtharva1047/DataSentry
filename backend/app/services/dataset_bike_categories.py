"""Shared semantic labels for the integer-coded UCI Bike Sharing predictors."""
from __future__ import annotations

import numpy as np
import pandas as pd


CATEGORY_LABELS: dict[str, dict[int, str]] = {
    "season": {1: "season_spring", 2: "season_summer", 3: "season_fall", 4: "season_winter"},
    "yr": {0: "year_2011", 1: "year_2012"},
    "mnth": {
        1: "month_january", 2: "month_february", 3: "month_march", 4: "month_april",
        5: "month_may", 6: "month_june", 7: "month_july", 8: "month_august",
        9: "month_september", 10: "month_october", 11: "month_november", 12: "month_december",
    },
    "hr": {value: f"hour_{value:02d}" for value in range(24)},
    "holiday": {0: "not_holiday", 1: "holiday"},
    "weekday": {
        0: "weekday_sunday", 1: "weekday_monday", 2: "weekday_tuesday",
        3: "weekday_wednesday", 4: "weekday_thursday", 5: "weekday_friday",
        6: "weekday_saturday",
    },
    "workingday": {0: "non_working_day", 1: "working_day"},
    "weathersit": {
        1: "weather_clear", 2: "weather_mist_cloudy",
        3: "weather_light_rain_snow", 4: "weather_heavy_rain_snow",
    },
}


def semantic_category(series: pd.Series, column: str) -> pd.Series:
    """Map a validated integer-coded source column to readable category labels."""
    if column not in CATEGORY_LABELS:
        raise ValueError(f"{column} is not a supported Bike Sharing categorical column")
    codes = pd.to_numeric(series, errors="coerce").to_numpy(dtype=float)
    if not np.isfinite(codes).all() or not np.equal(codes, np.floor(codes)).all():
        raise ValueError(f"{column} must contain finite integer category codes")
    mapping = CATEGORY_LABELS[column]
    unknown = sorted({int(value) for value in codes} - set(mapping))
    if unknown:
        raise ValueError(
            f"{column} contains unsupported category code(s): "
            + ", ".join(str(value) for value in unknown)
        )
    return pd.Series(
        [mapping[int(value)] for value in codes],
        index=series.index,
        name=column,
        dtype="string",
    )
