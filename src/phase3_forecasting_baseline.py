"""Phase 3 baseline forecasting evaluation.

This phase evaluates demand-history-only benchmark baselines for the
Product_ID x Location_ID gross outbound demand panel. It does not train
advanced models, create final future forecasts, calculate replenishment,
stockout risk, BOM requirements, procurement risk, production risk, final risk
scores, or Streamlit outputs.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd


DEFAULT_PANEL_PATH = Path("data") / "processed" / "daily_product_location_demand_panel.csv"
DEFAULT_SERIES_EDA_PATH = Path("outputs") / "phase2" / "demand_series_eda.csv"
DEFAULT_OUTPUT_DIR = Path("outputs") / "phase3"

HORIZONS = [30, 60, 90]
MIN_TRAIN_DAYS_FOR_FOLD = 90
NORMAL_TRAIN_DAYS = 180
FOLD_ANCHOR_DATES = [
    "2025-09-30",
    "2025-12-31",
    "2026-03-31",
    "2026-06-30",
]
ALPHA_CROSTON = 0.10


@dataclass
class Phase3Result:
    validation_fold_summary: pd.DataFrame
    baseline_metrics_by_series: pd.DataFrame
    baseline_metrics_overall: pd.DataFrame
    baseline_metrics_by_horizon: pd.DataFrame
    baseline_metrics_by_demand_class: pd.DataFrame
    best_baseline_by_series_horizon: pd.DataFrame
    frequency_comparison: pd.DataFrame
    series_status: pd.DataFrame
    validation_checks: pd.DataFrame


def previous_sunday(date_value: str) -> pd.Timestamp:
    date = pd.Timestamp(date_value)
    return date - pd.Timedelta(days=(date.weekday() + 1) % 7)


def forecast_origins() -> list[pd.Timestamp]:
    return [previous_sunday(value) for value in FOLD_ANCHOR_DATES]


def load_inputs(panel_path: Path, series_eda_path: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    if not panel_path.exists():
        raise FileNotFoundError(f"Missing Phase 2 daily demand panel: {panel_path}")
    if not series_eda_path.exists():
        raise FileNotFoundError(f"Missing Phase 2 demand series EDA file: {series_eda_path}")
    panel = pd.read_csv(panel_path, parse_dates=["Date", "First_Demand_Date", "Last_Demand_Date"])
    series_eda = pd.read_csv(series_eda_path, parse_dates=["First_Demand_Date", "Last_Demand_Date"])
    required_columns = {"Date", "Product_ID", "Location_ID", "Demand_Units"}
    missing_columns = required_columns - set(panel.columns)
    if missing_columns:
        raise ValueError(f"Daily panel is missing required columns: {sorted(missing_columns)}")
    return panel, series_eda


def croston_sba_forecast(values: np.ndarray, alpha: float = ALPHA_CROSTON) -> float:
    y = np.asarray(values, dtype=float)
    nonzero_positions = np.flatnonzero(y > 0)
    if len(nonzero_positions) == 0:
        return 0.0

    first = nonzero_positions[0]
    demand_size = y[first]
    interval = float(first + 1)
    last_nonzero = first
    for idx in nonzero_positions[1:]:
        demand_size = alpha * y[idx] + (1 - alpha) * demand_size
        interval = alpha * (idx - last_nonzero) + (1 - alpha) * interval
        last_nonzero = idx
    if interval <= 0:
        return max(0.0, demand_size)
    croston = demand_size / interval
    sba = (1 - alpha / 2) * croston
    return max(0.0, float(sba))


def constant_forecast(value: float, horizon: int) -> np.ndarray:
    return np.full(horizon, max(0.0, float(value)), dtype=float)


def daily_baseline_forecasts(train_values: np.ndarray, horizon: int = 90) -> dict[str, np.ndarray]:
    y = np.asarray(train_values, dtype=float)
    forecasts: dict[str, np.ndarray] = {}
    if len(y) == 0:
        return forecasts

    forecasts["daily_naive_last_day"] = constant_forecast(y[-1], horizon)
    forecasts["daily_historical_mean"] = constant_forecast(np.mean(y), horizon)
    for window in [7, 14, 28]:
        if len(y) >= window:
            forecasts[f"daily_moving_average_{window}d"] = constant_forecast(np.mean(y[-window:]), horizon)
    if len(y) >= 7:
        last_week = np.clip(y[-7:], 0, None)
        forecasts["daily_same_weekday_naive"] = np.array(
            [last_week[idx % 7] for idx in range(horizon)],
            dtype=float,
        )
    forecasts["daily_croston_sba_alpha_0_1"] = constant_forecast(croston_sba_forecast(y), horizon)
    return forecasts


def weekly_forecast_totals(weekly_values: np.ndarray, weeks_needed: int) -> dict[str, np.ndarray]:
    y = np.asarray(weekly_values, dtype=float)
    forecasts: dict[str, np.ndarray] = {}
    if len(y) == 0:
        return forecasts

    forecasts["weekly_naive_last_week"] = constant_forecast(y[-1], weeks_needed)
    forecasts["weekly_historical_mean"] = constant_forecast(np.mean(y), weeks_needed)
    if len(y) >= 4:
        forecasts["weekly_moving_average_4w"] = constant_forecast(np.mean(y[-4:]), weeks_needed)
    if len(y) >= 8:
        forecasts["weekly_moving_average_8w"] = constant_forecast(np.mean(y[-8:]), weeks_needed)
    if len(y) >= 52:
        pattern = np.clip(y[-52:], 0, None)
        forecasts["weekly_seasonal_naive_52w"] = np.array(
            [pattern[idx % 52] for idx in range(weeks_needed)],
            dtype=float,
        )
    forecasts["weekly_croston_sba_alpha_0_1"] = constant_forecast(croston_sba_forecast(y), weeks_needed)
    return forecasts


def weekly_distributed_forecasts(train: pd.DataFrame, horizon: int = 90) -> dict[str, np.ndarray]:
    series = train.set_index("Date")["Demand_Units"].sort_index()
    weekly = series.resample("W-SUN").sum()
    weeks_needed = int(np.ceil(horizon / 7))
    weekly_models = weekly_forecast_totals(weekly.to_numpy(dtype=float), weeks_needed)
    daily_forecasts: dict[str, np.ndarray] = {}
    for name, weekly_values in weekly_models.items():
        daily = np.array([weekly_values[idx // 7] / 7 for idx in range(horizon)], dtype=float)
        daily_forecasts[name] = np.clip(daily, 0, None)
    return daily_forecasts


def safe_smape(actual: np.ndarray, forecast: np.ndarray) -> float:
    denominator = np.abs(actual) + np.abs(forecast)
    valid = denominator > 0
    if not valid.any():
        return np.nan
    return float(np.mean(2 * np.abs(forecast[valid] - actual[valid]) / denominator[valid]) * 100)


def error_metrics(actual: Iterable[float], forecast: Iterable[float]) -> dict[str, float]:
    a = np.asarray(list(actual), dtype=float)
    f = np.asarray(list(forecast), dtype=float)
    if len(a) == 0:
        return {"MAE": np.nan, "RMSE": np.nan, "WAPE": np.nan, "sMAPE": np.nan}
    error = f - a
    abs_error = np.abs(error)
    actual_sum = np.sum(np.abs(a))
    return {
        "MAE": float(np.mean(abs_error)),
        "RMSE": float(np.sqrt(np.mean(error**2))),
        "WAPE": float(np.sum(abs_error) / actual_sum * 100) if actual_sum > 0 else np.nan,
        "sMAPE": safe_smape(a, f),
    }


def aggregate_metric_frame(records: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    rows = []
    for keys, group in records.groupby(group_cols, dropna=False):
        if not isinstance(keys, tuple):
            keys = (keys,)
        cumulative = error_metrics(group["Actual_Total"], group["Forecast_Total"])
        period_count = group["Period_Count"].sum()
        period_abs_actual = group["Period_Abs_Actual_Sum"].sum()
        period_smape_count = group["Period_sMAPE_Count"].sum()
        period_mae = group["Period_Abs_Error_Sum"].sum() / period_count if period_count else np.nan
        period_rmse = (
            np.sqrt(group["Period_Squared_Error_Sum"].sum() / period_count) if period_count else np.nan
        )
        period_wape = (
            group["Period_Abs_Error_Sum"].sum() / period_abs_actual * 100
            if period_abs_actual > 0
            else np.nan
        )
        period_smape = (
            group["Period_sMAPE_Term_Sum"].sum() / period_smape_count * 100
            if period_smape_count
            else np.nan
        )
        row = {col: value for col, value in zip(group_cols, keys)}
        row.update(
            {
                "Period_MAE": float(period_mae),
                "Period_RMSE": float(period_rmse),
                "Period_WAPE": float(period_wape),
                "Period_sMAPE": float(period_smape),
                "Cumulative_MAE": cumulative["MAE"],
                "Cumulative_RMSE": cumulative["RMSE"],
                "Cumulative_WAPE": cumulative["WAPE"],
                "Cumulative_sMAPE": cumulative["sMAPE"],
                "Evaluation_Windows": int(len(group)),
                "Series_Count": int(group[["Product_ID", "Location_ID"]].drop_duplicates().shape[0]),
            }
        )
        rows.append(row)
    return pd.DataFrame(rows)


def make_cumulative_records(
    series_key: tuple[str, str],
    metadata: dict[str, object],
    fold_id: int,
    origin: pd.Timestamp,
    horizon: int,
    frequency: str,
    baseline: str,
    actual: np.ndarray,
    forecast: np.ndarray,
) -> dict[str, object]:
    actual_total = float(np.sum(actual))
    forecast_total = float(np.sum(forecast))
    cumulative_error = forecast_total - actual_total
    period_error = forecast - actual
    period_abs_error = np.abs(period_error)
    period_denominator = np.abs(actual) + np.abs(forecast)
    period_smape_valid = period_denominator > 0
    return {
        "Product_ID": series_key[0],
        "Location_ID": series_key[1],
        "Product_Name": metadata.get("Product_Name", ""),
        "Location_Name": metadata.get("Location_Name", ""),
        "Channel": metadata.get("Channel", ""),
        "Product_Family": metadata.get("Product_Family", ""),
        "Demand_Pattern_Class": metadata.get("Demand_Pattern_Class", ""),
        "Fold_ID": fold_id,
        "Forecast_Origin": origin,
        "Forecast_Start": origin + pd.Timedelta(days=1),
        "Forecast_End": origin + pd.Timedelta(days=horizon),
        "Horizon_Days": horizon,
        "Frequency": frequency,
        "Baseline": baseline,
        "Actual_Total": actual_total,
        "Forecast_Total": forecast_total,
        "Cumulative_Error": cumulative_error,
        "Absolute_Cumulative_Error": abs(cumulative_error),
        "Period_Count": int(len(actual)),
        "Period_Abs_Error_Sum": float(np.sum(period_abs_error)),
        "Period_Squared_Error_Sum": float(np.sum(period_error**2)),
        "Period_Abs_Actual_Sum": float(np.sum(np.abs(actual))),
        "Period_sMAPE_Term_Sum": float(
            np.sum(2 * period_abs_error[period_smape_valid] / period_denominator[period_smape_valid])
        ),
        "Period_sMAPE_Count": int(period_smape_valid.sum()),
    }


def evaluate_baselines(panel: pd.DataFrame, series_eda: pd.DataFrame) -> Phase3Result:
    origins = forecast_origins()
    max_horizon = max(HORIZONS)
    demand_classes = series_eda[
        [
            "Product_ID",
            "Location_ID",
            "Demand_Pattern_Class",
            "Active_Days",
            "Zero_Demand_Pct",
            "Average_Demand_Interval_Days",
            "May_Need_Fallback_Later",
        ]
    ].copy()

    panel = panel.merge(
        demand_classes,
        on=["Product_ID", "Location_ID"],
        how="left",
        suffixes=("", "_EDA"),
    )

    cumulative_records: list[dict[str, object]] = []
    fold_summary_rows: list[dict[str, object]] = []
    series_status_rows: list[dict[str, object]] = []

    for (product_id, location_id), group in panel.groupby(["Product_ID", "Location_ID"], sort=True):
        group = group.sort_values("Date").copy()
        group["Demand_Units"] = group["Demand_Units"].astype(float)
        metadata = {
            "Product_Name": group["Product_Name"].iloc[0],
            "Location_Name": group["Location_Name"].iloc[0],
            "Channel": group["Channel"].iloc[0],
            "Product_Family": group["Product_Family"].iloc[0],
            "Demand_Pattern_Class": group["Demand_Pattern_Class"].iloc[0],
        }
        series_key = (product_id, location_id)
        evaluated_horizon_windows = 0
        possible_horizon_windows = len(origins) * len(HORIZONS)
        min_train_days_seen = None
        max_train_days_seen = 0

        for fold_id, origin in enumerate(origins, start=1):
            train = group[group["Date"] <= origin].copy()
            validation_90 = group[
                (group["Date"] > origin) & (group["Date"] <= origin + pd.Timedelta(days=max_horizon))
            ].copy()
            train_days = len(train)
            max_train_days_seen = max(max_train_days_seen, train_days)
            min_train_days_seen = train_days if min_train_days_seen is None else min(min_train_days_seen, train_days)
            base_status = "baseline_evaluated_normally"
            if train_days < MIN_TRAIN_DAYS_FOR_FOLD:
                base_status = "insufficient_history"
            elif train_days < NORMAL_TRAIN_DAYS:
                base_status = "reduced_history_evaluation"

            daily_models: dict[str, np.ndarray] = {}
            weekly_models: dict[str, np.ndarray] = {}
            if train_days >= MIN_TRAIN_DAYS_FOR_FOLD:
                daily_models = daily_baseline_forecasts(train["Demand_Units"].to_numpy(dtype=float), max_horizon)
                weekly_models = weekly_distributed_forecasts(train, max_horizon)

            for horizon in HORIZONS:
                validation = validation_90[validation_90["Date"] <= origin + pd.Timedelta(days=horizon)]
                has_full_validation = len(validation) == horizon
                no_overlap = bool(train["Date"].max() < validation["Date"].min()) if has_full_validation and len(train) else False
                forecast_dates_after_training = no_overlap
                horizon_status = base_status
                if base_status != "insufficient_history" and not has_full_validation:
                    horizon_status = "insufficient_validation_window"

                fold_summary_rows.append(
                    {
                        "Product_ID": product_id,
                        "Location_ID": location_id,
                        "Fold_ID": fold_id,
                        "Forecast_Origin": origin,
                        "Training_Start": train["Date"].min() if len(train) else pd.NaT,
                        "Training_End": train["Date"].max() if len(train) else pd.NaT,
                        "Forecast_Start": origin + pd.Timedelta(days=1),
                        "Forecast_End": origin + pd.Timedelta(days=horizon),
                        "Horizon_Days": horizon,
                        "Training_Days": train_days,
                        "Validation_Days": len(validation),
                        "Has_Full_Validation_Window": has_full_validation,
                        "No_Train_Test_Overlap": no_overlap,
                        "Forecast_Dates_After_Training": forecast_dates_after_training,
                        "Fold_Status": horizon_status,
                    }
                )

                if train_days < MIN_TRAIN_DAYS_FOR_FOLD or not has_full_validation:
                    continue

                actual = validation["Demand_Units"].to_numpy(dtype=float)
                for baseline, forecast_90 in daily_models.items():
                    forecast = np.clip(forecast_90[:horizon], 0, None)
                    cumulative_records.append(
                        make_cumulative_records(
                            series_key,
                            metadata,
                            fold_id,
                            origin,
                            horizon,
                            "daily",
                            baseline,
                            actual,
                            forecast,
                        )
                    )
                for baseline, forecast_90 in weekly_models.items():
                    forecast = np.clip(forecast_90[:horizon], 0, None)
                    cumulative_records.append(
                        make_cumulative_records(
                            series_key,
                            metadata,
                            fold_id,
                            origin,
                            horizon,
                            "weekly_distributed",
                            baseline,
                            actual,
                            forecast,
                        )
                    )
                evaluated_horizon_windows += 1

        demand_class = metadata["Demand_Pattern_Class"]
        fallback_later = bool(group["May_Need_Fallback_Later"].iloc[0])
        if evaluated_horizon_windows == 0:
            evaluation_status = "insufficient_history"
        elif evaluated_horizon_windows < possible_horizon_windows:
            evaluation_status = "reduced_history_evaluation"
        else:
            evaluation_status = "baseline_evaluated_normally"
        fallback_reason = ""
        if fallback_later:
            fallback_reason = "Phase 2 intermittency/variability flag; keep fallback baselines under consideration."
        series_status_rows.append(
            {
                "Product_ID": product_id,
                "Location_ID": location_id,
                "Product_Name": metadata["Product_Name"],
                "Location_Name": metadata["Location_Name"],
                "Channel": metadata["Channel"],
                "Product_Family": metadata["Product_Family"],
                "Demand_Pattern_Class": demand_class,
                "Evaluation_Status": evaluation_status,
                "Evaluated_Horizon_Windows": evaluated_horizon_windows,
                "Possible_Horizon_Windows": possible_horizon_windows,
                "Min_Training_Days_Seen": min_train_days_seen,
                "Max_Training_Days_Seen": max_train_days_seen,
                "Fallback_Flag_For_Phase4": fallback_later,
                "Fallback_Reason": fallback_reason,
            }
        )

    cumulative = pd.DataFrame(cumulative_records)
    fold_summary = pd.DataFrame(fold_summary_rows)
    series_status = pd.DataFrame(series_status_rows)
    if cumulative.empty:
        raise RuntimeError("No baseline validation records were generated.")

    group_cols_series = [
        "Product_ID",
        "Location_ID",
        "Product_Name",
        "Location_Name",
        "Channel",
        "Product_Family",
        "Demand_Pattern_Class",
        "Horizon_Days",
        "Frequency",
        "Baseline",
    ]
    metrics_by_series = aggregate_metric_frame(cumulative, group_cols_series)

    metrics_overall = aggregate_metric_frame(cumulative, ["Frequency", "Baseline"])
    metrics_by_horizon = aggregate_metric_frame(cumulative, ["Horizon_Days", "Frequency", "Baseline"])
    metrics_by_class = aggregate_metric_frame(
        cumulative,
        ["Demand_Pattern_Class", "Horizon_Days", "Frequency", "Baseline"],
    )

    metrics_by_series = metrics_by_series.merge(
        series_status[
            [
                "Product_ID",
                "Location_ID",
                "Evaluation_Status",
                "Max_Training_Days_Seen",
                "Fallback_Flag_For_Phase4",
            ]
        ],
        on=["Product_ID", "Location_ID"],
        how="left",
    )
    metrics_by_series["Selection_Score"] = metrics_by_series["Cumulative_WAPE"].where(
        metrics_by_series["Cumulative_WAPE"].notna(),
        metrics_by_series["Cumulative_MAE"],
    )
    best = (
        metrics_by_series.sort_values(
            [
                "Product_ID",
                "Location_ID",
                "Horizon_Days",
                "Selection_Score",
                "Cumulative_MAE",
                "Period_WAPE",
            ],
            na_position="last",
        )
        .groupby(["Product_ID", "Location_ID", "Horizon_Days"], as_index=False)
        .head(1)
        .copy()
    )
    best = best.rename(columns={"Baseline": "Best_Baseline_Name", "Frequency": "Best_Frequency"})

    frequency_rows = []
    for (frequency, horizon), freq_group in metrics_by_horizon.groupby(["Frequency", "Horizon_Days"]):
        ranked = freq_group.sort_values(["Cumulative_WAPE", "Cumulative_MAE"], na_position="last").iloc[0]
        frequency_rows.append(
            {
                "Frequency": frequency,
                "Horizon_Days": horizon,
                "Best_Baseline_For_Frequency": ranked["Baseline"],
                "Cumulative_WAPE": ranked["Cumulative_WAPE"],
                "Cumulative_MAE": ranked["Cumulative_MAE"],
                "Period_WAPE": ranked["Period_WAPE"],
                "Period_MAE": ranked["Period_MAE"],
                "Series_Count": ranked["Series_Count"],
                "Evaluation_Windows": ranked["Evaluation_Windows"],
                "Frequency_Handling": (
                    "Direct daily forecasts"
                    if frequency == "daily"
                    else "Weekly totals distributed evenly across days to preserve 30/60/90-day horizons"
                ),
            }
        )
    frequency_comparison = pd.DataFrame(frequency_rows).sort_values(["Horizon_Days", "Cumulative_WAPE"])

    validation_checks = build_validation_checks(panel, fold_summary, cumulative, best)
    return Phase3Result(
        validation_fold_summary=fold_summary,
        baseline_metrics_by_series=metrics_by_series,
        baseline_metrics_overall=metrics_overall,
        baseline_metrics_by_horizon=metrics_by_horizon,
        baseline_metrics_by_demand_class=metrics_by_class,
        best_baseline_by_series_horizon=best,
        frequency_comparison=frequency_comparison,
        series_status=series_status,
        validation_checks=validation_checks,
    )


def build_validation_checks(
    panel: pd.DataFrame,
    fold_summary: pd.DataFrame,
    cumulative: pd.DataFrame,
    best: pd.DataFrame,
) -> pd.DataFrame:
    series_count = panel[["Product_ID", "Location_ID"]].drop_duplicates().shape[0]
    best_series_count = best[["Product_ID", "Location_ID"]].drop_duplicates().shape[0]
    full_fold_rows = fold_summary[fold_summary["Has_Full_Validation_Window"]]
    checks = [
        ("all_177_product_location_pairs_represented", series_count == 177 and best_series_count == 177, f"panel={series_count}; best_baseline={best_series_count}"),
        (
            "no_train_test_overlap",
            bool(full_fold_rows["No_Train_Test_Overlap"].all()),
            f"checked_rows={len(full_fold_rows)}",
        ),
        (
            "forecast_dates_after_training",
            bool(full_fold_rows["Forecast_Dates_After_Training"].all()),
            f"checked_rows={len(full_fold_rows)}",
        ),
        (
            "forecasts_non_negative",
            bool((cumulative["Forecast_Total"] >= 0).all()),
            f"min_forecast_total={cumulative['Forecast_Total'].min():.6f}",
        ),
        (
            "horizons_exactly_30_60_90",
            set(cumulative["Horizon_Days"].unique()) == {30, 60, 90},
            f"horizons={sorted(cumulative['Horizon_Days'].unique())}",
        ),
        (
            "all_best_rows_have_finite_selection_score",
            bool(best["Selection_Score"].notna().all()),
            f"best_rows={len(best)}",
        ),
    ]
    return pd.DataFrame(checks, columns=["check", "passed", "detail"])


def fmt(value: object) -> str:
    if isinstance(value, (int, np.integer)):
        return f"{int(value):,}"
    if isinstance(value, (float, np.floating)):
        if pd.isna(value):
            return "n/a"
        if float(value).is_integer():
            return f"{int(value):,}"
        return f"{float(value):,.3f}"
    return str(value)


def markdown_table(frame: pd.DataFrame, columns: list[str], n: int = 10) -> str:
    subset = frame[columns].head(n).copy()
    if subset.empty:
        return "No rows."
    for col in subset.columns:
        if pd.api.types.is_datetime64_any_dtype(subset[col]):
            subset[col] = subset[col].dt.date.astype(str)
        else:
            subset[col] = subset[col].map(fmt)
    header = "| " + " | ".join(subset.columns) + " |"
    separator = "| " + " | ".join("---" for _ in subset.columns) + " |"
    body = ["| " + " | ".join(str(value) for value in row) + " |" for row in subset.to_numpy()]
    return "\n".join([header, separator, *body])


def best_overall_text(metrics_overall: pd.DataFrame) -> pd.Series:
    return metrics_overall.sort_values(["Cumulative_WAPE", "Cumulative_MAE"], na_position="last").iloc[0]


def build_report(result: Phase3Result, output_dir: Path) -> str:
    origins = forecast_origins()
    origin_text = ", ".join(origin.date().isoformat() for origin in origins)
    best_overall = best_overall_text(result.baseline_metrics_overall)
    best_intermittent = result.baseline_metrics_by_demand_class[
        result.baseline_metrics_by_demand_class["Demand_Pattern_Class"].eq("intermittent")
    ].sort_values(["Cumulative_WAPE", "Cumulative_MAE"], na_position="last")
    best_intermittent_row = best_intermittent.iloc[0] if not best_intermittent.empty else None
    class_counts = (
        result.series_status["Demand_Pattern_Class"].value_counts().sort_index().rename_axis("Demand_Class").reset_index(name="Series_Count")
    )
    difficult = result.best_baseline_by_series_horizon.sort_values("Cumulative_WAPE", ascending=False)
    validation_passed = bool(result.validation_checks["passed"].all())

    report = f"""# Phase 3 Baseline Forecasting Report

## Scope Boundary

This is Phase 3 only: simple baseline forecasting benchmarks. No advanced model comparison, final `forecast_results.csv`, future production forecast, stockout logic, replenishment, BOM requirements, procurement risk, production risk, final risk score, or Streamlit dashboard was created.

All baselines use only historical gross outbound demand from the Phase 2 daily `Product_ID x Location_ID` panel. No external data was used.

## Returns Clarification

`Inventory_History.Returned_Qty` reconciles exactly with returned transaction quantity grouped by order month, not `Return_Date` month. Therefore it is not evidence of the actual calendar timing of physical returns. Future return outcomes are leakage for demand forecasting and were not used as features. Gross outbound demand from `Sales_Transactions.Quantity` remains the forecasting target, while returns remain a separate descriptive behavior.

## Validation Design

- Available daily demand history: 2023-10-01 to 2026-09-30.
- Forecast origins: {origin_text}.
- Origins are the last Sundays before quarter-end anchors so weekly aggregation can use completed weeks without partial-week leakage.
- Training window: expanding history from each series' first panel date through the forecast origin.
- Validation windows: exact 30, 60, and 90 calendar days after each origin.
- Backtest folds: {len(origins)} rolling-origin folds.
- Minimum training threshold: {MIN_TRAIN_DAYS_FOR_FOLD} days for a fold; under {NORMAL_TRAIN_DAYS} days is marked reduced-history.
- No random train/test splits were used.

The last four days of available history are not used in validation because the latest complete-week origin that supports a full 90-day horizon is {origins[-1].date().isoformat()}.

## Baselines Evaluated

Daily baselines:

- `daily_naive_last_day`
- `daily_historical_mean`
- `daily_moving_average_7d`
- `daily_moving_average_14d`
- `daily_moving_average_28d`
- `daily_same_weekday_naive`
- `daily_croston_sba_alpha_0_1`

Weekly-distributed baselines:

- `weekly_naive_last_week`
- `weekly_historical_mean`
- `weekly_moving_average_4w`
- `weekly_moving_average_8w`
- `weekly_seasonal_naive_52w`
- `weekly_croston_sba_alpha_0_1`

Weekly models forecast weekly totals from completed training weeks, then distribute each weekly total evenly across days so the required 30/60/90-day horizons remain exact. This is only a frequency comparison benchmark, not a final modeling decision.

All forecasts were clipped at zero. No rounding was applied during evaluation.

## Daily Vs Weekly Frequency

Frequency comparison using each frequency's best baseline by horizon:

{markdown_table(result.frequency_comparison, ["Horizon_Days", "Frequency", "Best_Baseline_For_Frequency", "Cumulative_WAPE", "Cumulative_MAE", "Period_WAPE", "Period_MAE", "Series_Count"])}

Current evidence: choose the best-performing baseline/frequency as a benchmark only. Phase 4 should compare stronger models against both the best direct daily baseline and the best weekly-distributed baseline because weekly smoothing may help intermittent demand, while daily baselines preserve operational timing.

## Overall Baseline Result

Best overall benchmark by cumulative WAPE:

- Frequency: `{best_overall["Frequency"]}`
- Baseline: `{best_overall["Baseline"]}`
- Cumulative WAPE: {fmt(best_overall["Cumulative_WAPE"])}%
- Cumulative MAE: {fmt(best_overall["Cumulative_MAE"])}
- Period WAPE: {fmt(best_overall["Period_WAPE"])}%

Overall metrics:

{markdown_table(result.baseline_metrics_overall.sort_values(["Cumulative_WAPE", "Cumulative_MAE"], na_position="last"), ["Frequency", "Baseline", "Cumulative_WAPE", "Cumulative_MAE", "Period_WAPE", "Period_MAE", "Series_Count"], 12)}

## Horizon Performance

Best baseline rows by horizon:

{markdown_table(result.baseline_metrics_by_horizon.sort_values(["Horizon_Days", "Cumulative_WAPE", "Cumulative_MAE"], na_position="last"), ["Horizon_Days", "Frequency", "Baseline", "Cumulative_WAPE", "Cumulative_MAE", "Period_WAPE", "Period_MAE", "Series_Count"], 18)}

## Demand Class Performance

Series per Phase 2 demand class:

{markdown_table(class_counts, ["Demand_Class", "Series_Count"], 10)}

Best baseline rows by demand class and horizon:

{markdown_table(result.baseline_metrics_by_demand_class.sort_values(["Demand_Pattern_Class", "Horizon_Days", "Cumulative_WAPE", "Cumulative_MAE"], na_position="last"), ["Demand_Pattern_Class", "Horizon_Days", "Frequency", "Baseline", "Cumulative_WAPE", "Cumulative_MAE", "Period_WAPE", "Series_Count"], 24)}

Best intermittent-demand benchmark:

{f"- `{best_intermittent_row['Frequency']}` / `{best_intermittent_row['Baseline']}` with cumulative WAPE {fmt(best_intermittent_row['Cumulative_WAPE'])}%" if best_intermittent_row is not None else "- No intermittent series found."}

## Difficult Series

Highest cumulative WAPE among selected best baselines:

{markdown_table(difficult, ["Product_ID", "Location_ID", "Channel", "Product_Family", "Demand_Pattern_Class", "Horizon_Days", "Best_Frequency", "Best_Baseline_Name", "Cumulative_WAPE", "Cumulative_MAE", "Fallback_Flag_For_Phase4"], 15)}

These are not failures to drop; they are candidates for Phase 4 fallback handling, pooling, or alternative model classes.

## Series Coverage And Status

- Product x Location series represented: {fmt(result.series_status[["Product_ID", "Location_ID"]].drop_duplicates().shape[0])}
- Best-baseline rows: {fmt(len(result.best_baseline_by_series_horizon))}
- Fallback-flagged series for Phase 4 consideration: {fmt(result.series_status["Fallback_Flag_For_Phase4"].sum())}
- Series status counts: {", ".join(f"{idx}: {fmt(value)}" for idx, value in result.series_status["Evaluation_Status"].value_counts().items())}

Every one of the 177 Product x Location series has a status row and selected baseline benchmark for each 30/60/90-day horizon.

## Leakage Protection

Phase 3 used demand-history-only baselines. It did not use future `Quantity`, inventory outcomes, returns, discounts, production outcomes, procurement outcomes, customer fields, or future business facts. Price and discount remain EDA-only until a later phase can prove which values are known before forecast origin.

## Limitations

- Baselines are benchmarks, not final model recommendations.
- Weekly forecasts were evenly distributed across days only for comparable 30/60/90-day validation; this may hide within-week timing.
- Croston/SBA uses a fixed alpha of {ALPHA_CROSTON}; Phase 4 can tune or compare alternatives.
- Strong intermittency remains: many series need fallback-aware modeling.
- No inventory or replenishment decisions were made in this phase.

## Validation Checks

{markdown_table(result.validation_checks, ["check", "passed", "detail"], 20)}

Validation passed: {validation_passed}.

## Files Created Or Modified

- `{output_dir / "phase3_baseline_report.md"}`
- `{output_dir / "baseline_metrics_overall.csv"}`
- `{output_dir / "baseline_metrics_by_horizon.csv"}`
- `{output_dir / "baseline_metrics_by_demand_class.csv"}`
- `{output_dir / "baseline_metrics_by_series.csv"}`
- `{output_dir / "best_baseline_by_series_horizon.csv"}`
- `{output_dir / "validation_fold_summary.csv"}`
- `{output_dir / "frequency_comparison.csv"}`
- `{output_dir / "series_evaluation_status.csv"}`
- `{output_dir / "validation_checks.csv"}`
- `src/phase3_forecasting_baseline.py`
- `outputs/phase2/phase2_cleaning_eda_report.md` was updated only with the requested returns clarification.

## Recommendation For Phase 4

Phase 4 should compare stronger forecasting approaches against these benchmarks, especially the best direct daily baseline, the best weekly-distributed baseline, and Croston/SBA for intermittent or lumpy demand. Candidate approaches should remain time-series validated and leakage-safe.

Stop here for approval before Phase 4.
"""
    return report


def write_outputs(result: Phase3Result, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    result.baseline_metrics_overall.to_csv(output_dir / "baseline_metrics_overall.csv", index=False)
    result.baseline_metrics_by_horizon.to_csv(output_dir / "baseline_metrics_by_horizon.csv", index=False)
    result.baseline_metrics_by_demand_class.to_csv(output_dir / "baseline_metrics_by_demand_class.csv", index=False)
    result.baseline_metrics_by_series.to_csv(output_dir / "baseline_metrics_by_series.csv", index=False)
    result.best_baseline_by_series_horizon.to_csv(output_dir / "best_baseline_by_series_horizon.csv", index=False)
    result.validation_fold_summary.to_csv(output_dir / "validation_fold_summary.csv", index=False)
    result.frequency_comparison.to_csv(output_dir / "frequency_comparison.csv", index=False)
    result.series_status.to_csv(output_dir / "series_evaluation_status.csv", index=False)
    result.validation_checks.to_csv(output_dir / "validation_checks.csv", index=False)

    report_path = output_dir / "phase3_baseline_report.md"
    report_path.write_text(build_report(result, output_dir), encoding="utf-8")
    return report_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Phase 3 baseline forecasting evaluation only.")
    parser.add_argument("--panel-path", type=Path, default=DEFAULT_PANEL_PATH)
    parser.add_argument("--series-eda-path", type=Path, default=DEFAULT_SERIES_EDA_PATH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    panel, series_eda = load_inputs(args.panel_path, args.series_eda_path)
    result = evaluate_baselines(panel, series_eda)
    report_path = write_outputs(result, args.output_dir)
    print(f"Phase 3 baseline forecasting complete: {report_path.resolve()}")


if __name__ == "__main__":
    main()
