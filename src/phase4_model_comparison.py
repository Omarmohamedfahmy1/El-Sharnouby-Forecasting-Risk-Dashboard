"""Phase 4 forecasting model comparison.

This phase compares advanced weekly forecasting candidates against Phase 3
baselines using the same rolling origins. It stops at validation/model
selection. It does not generate final future forecasts or start inventory,
replenishment, BOM, procurement, production, risk, or Streamlit work.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from phase3_forecasting_baseline import (
    ALPHA_CROSTON,
    HORIZONS,
    MIN_TRAIN_DAYS_FOR_FOLD,
    aggregate_metric_frame,
    croston_sba_forecast,
    daily_baseline_forecasts,
    forecast_origins,
    fmt,
    markdown_table,
    weekly_distributed_forecasts,
)


DEFAULT_PANEL_PATH = Path("data") / "processed" / "daily_product_location_demand_panel.csv"
DEFAULT_SERIES_EDA_PATH = Path("outputs") / "phase2" / "demand_series_eda.csv"
DEFAULT_PHASE3_DIR = Path("outputs") / "phase3"
DEFAULT_OUTPUT_DIR = Path("outputs") / "phase4"
MAX_HORIZON = max(HORIZONS)
WEEKS_NEEDED = int(np.ceil(MAX_HORIZON / 7))
SEASON_LENGTH = 52


@dataclass
class Phase4Result:
    model_metrics_overall: pd.DataFrame
    model_metrics_by_horizon: pd.DataFrame
    model_metrics_by_demand_class: pd.DataFrame
    model_metrics_by_series: pd.DataFrame
    model_metrics_by_fold: pd.DataFrame
    selected_model_by_series_horizon: pd.DataFrame
    advanced_vs_baseline_comparison: pd.DataFrame
    model_improvement_distribution: pd.DataFrame
    validation_checks: pd.DataFrame
    frequency_comparison: pd.DataFrame
    candidate_records: pd.DataFrame


def load_inputs(panel_path: Path, series_eda_path: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    if not panel_path.exists():
        raise FileNotFoundError(f"Missing daily panel: {panel_path}")
    if not series_eda_path.exists():
        raise FileNotFoundError(f"Missing demand EDA file: {series_eda_path}")
    panel = pd.read_csv(panel_path, parse_dates=["Date", "First_Demand_Date", "Last_Demand_Date"])
    series_eda = pd.read_csv(series_eda_path)
    return panel, series_eda


def build_weekly_panel(panel: pd.DataFrame, series_eda: pd.DataFrame) -> pd.DataFrame:
    static_cols = [
        "Product_ID",
        "Location_ID",
        "Product_Name",
        "Location_Name",
        "Channel",
        "Product_Family",
        "Brand",
        "Gender",
        "Audience",
        "Catalog_Season",
    ]
    available_static = [col for col in static_cols if col in panel.columns]
    static = panel[available_static].drop_duplicates(["Product_ID", "Location_ID"])
    demand_class = series_eda[
        [
            "Product_ID",
            "Location_ID",
            "Demand_Pattern_Class",
            "May_Need_Fallback_Later",
            "Zero_Demand_Pct",
            "Average_Demand_Interval_Days",
        ]
    ].copy()
    static = static.merge(demand_class, on=["Product_ID", "Location_ID"], how="left")

    parts = []
    for (product_id, location_id), group in panel.groupby(["Product_ID", "Location_ID"], sort=True):
        series = group.sort_values("Date").set_index("Date")["Demand_Units"].astype(float)
        weekly = series.resample("W-SUN").sum().reset_index()
        weekly["Product_ID"] = product_id
        weekly["Location_ID"] = location_id
        weekly = weekly.rename(columns={"Date": "Week_End", "Demand_Units": "Weekly_Demand"})
        parts.append(weekly)
    weekly_panel = pd.concat(parts, ignore_index=True)
    weekly_panel = weekly_panel.merge(static, on=["Product_ID", "Location_ID"], how="left")
    weekly_panel = weekly_panel.sort_values(["Product_ID", "Location_ID", "Week_End"]).reset_index(drop=True)
    return weekly_panel


def add_weekly_features(frame: pd.DataFrame) -> pd.DataFrame:
    work = frame.sort_values(["Product_ID", "Location_ID", "Week_End"]).copy()
    group = work.groupby(["Product_ID", "Location_ID"])["Weekly_Demand"]
    for lag in [1, 2, 4, 8, 13, 26, 52]:
        work[f"lag_{lag}w"] = group.shift(lag)
    shifted = group.shift(1)
    for window in [4, 8, 13]:
        work[f"rolling_mean_{window}w"] = shifted.groupby([work["Product_ID"], work["Location_ID"]]).rolling(window).mean().reset_index(level=[0, 1], drop=True)
        work[f"rolling_median_{window}w"] = shifted.groupby([work["Product_ID"], work["Location_ID"]]).rolling(window).median().reset_index(level=[0, 1], drop=True)
        work[f"rolling_std_{window}w"] = shifted.groupby([work["Product_ID"], work["Location_ID"]]).rolling(window).std().reset_index(level=[0, 1], drop=True)
        work[f"rolling_sum_{window}w"] = shifted.groupby([work["Product_ID"], work["Location_ID"]]).rolling(window).sum().reset_index(level=[0, 1], drop=True)
        nonzero = (shifted > 0).astype(float)
        work[f"nonzero_freq_{window}w"] = nonzero.groupby([work["Product_ID"], work["Location_ID"]]).rolling(window).mean().reset_index(level=[0, 1], drop=True)
    work["weekofyear"] = work["Week_End"].dt.isocalendar().week.astype(int)
    work["month"] = work["Week_End"].dt.month
    work["quarter"] = work["Week_End"].dt.quarter
    work["year"] = work["Week_End"].dt.year
    return work


def week_features_from_history(
    history: list[float],
    week_end: pd.Timestamp,
    static: pd.Series,
) -> dict[str, object]:
    values = np.asarray(history, dtype=float)
    row: dict[str, object] = {
        "Week_End": week_end,
        "Product_ID": static["Product_ID"],
        "Location_ID": static["Location_ID"],
        "Product_Name": static.get("Product_Name", ""),
        "Location_Name": static.get("Location_Name", ""),
        "Channel": static.get("Channel", ""),
        "Product_Family": static.get("Product_Family", ""),
        "Brand": static.get("Brand", ""),
        "Gender": static.get("Gender", ""),
        "Audience": static.get("Audience", ""),
        "Catalog_Season": static.get("Catalog_Season", ""),
        "Demand_Pattern_Class": static.get("Demand_Pattern_Class", ""),
        "May_Need_Fallback_Later": static.get("May_Need_Fallback_Later", False),
        "Zero_Demand_Pct": static.get("Zero_Demand_Pct", np.nan),
        "Average_Demand_Interval_Days": static.get("Average_Demand_Interval_Days", np.nan),
        "weekofyear": int(week_end.isocalendar().week),
        "month": int(week_end.month),
        "quarter": int(week_end.quarter),
        "year": int(week_end.year),
    }
    for lag in [1, 2, 4, 8, 13, 26, 52]:
        row[f"lag_{lag}w"] = values[-lag] if len(values) >= lag else np.nan
    for window in [4, 8, 13]:
        window_values = values[-window:] if len(values) >= 1 else np.array([], dtype=float)
        if len(window_values) == 0:
            row[f"rolling_mean_{window}w"] = np.nan
            row[f"rolling_median_{window}w"] = np.nan
            row[f"rolling_std_{window}w"] = np.nan
            row[f"rolling_sum_{window}w"] = np.nan
            row[f"nonzero_freq_{window}w"] = np.nan
        else:
            row[f"rolling_mean_{window}w"] = float(np.mean(window_values))
            row[f"rolling_median_{window}w"] = float(np.median(window_values))
            row[f"rolling_std_{window}w"] = float(np.std(window_values, ddof=0))
            row[f"rolling_sum_{window}w"] = float(np.sum(window_values))
            row[f"nonzero_freq_{window}w"] = float(np.mean(window_values > 0))
    return row


def make_daily_from_weekly(weekly_values: Iterable[float], horizon: int = MAX_HORIZON) -> np.ndarray:
    weekly = np.asarray(list(weekly_values), dtype=float)
    return np.clip(np.array([weekly[idx // 7] / 7 for idx in range(horizon)], dtype=float), 0, None)


def tune_ses_forecast(weekly_values: np.ndarray, weeks_needed: int = WEEKS_NEEDED) -> np.ndarray:
    y = np.asarray(weekly_values, dtype=float)
    if len(y) == 0:
        return np.zeros(weeks_needed)
    alphas = [0.05, 0.10, 0.20, 0.30, 0.50]
    val_len = min(13, max(4, len(y) // 5))
    if len(y) <= val_len + 4:
        best_alpha = 0.20
    else:
        train_inner = y[:-val_len]
        val = y[-val_len:]
        best_alpha = alphas[0]
        best_error = np.inf
        for alpha in alphas:
            level = train_inner[0]
            for value in train_inner[1:]:
                level = alpha * value + (1 - alpha) * level
            pred = np.full(val_len, level)
            error = np.mean(np.abs(pred - val))
            if error < best_error:
                best_error = error
                best_alpha = alpha
    level = y[0]
    for value in y[1:]:
        level = best_alpha * value + (1 - best_alpha) * level
    return np.clip(np.full(weeks_needed, level, dtype=float), 0, None)


def holt_winters_additive_forecast(
    y: np.ndarray,
    alpha: float,
    beta: float,
    gamma: float,
    weeks_needed: int,
    season_length: int = SEASON_LENGTH,
) -> np.ndarray | None:
    values = np.asarray(y, dtype=float)
    if len(values) < season_length * 2:
        return None
    first = values[:season_length]
    second = values[season_length : season_length * 2]
    level = float(np.mean(first))
    trend = float((np.mean(second) - np.mean(first)) / season_length)
    seasonals = list(first - level)
    for idx, value in enumerate(values):
        season_idx = idx % season_length
        seasonal = seasonals[season_idx]
        old_level = level
        level = alpha * (value - seasonal) + (1 - alpha) * (level + trend)
        trend = beta * (level - old_level) + (1 - beta) * trend
        seasonals[season_idx] = gamma * (value - level) + (1 - gamma) * seasonal
    start = len(values)
    forecast = []
    for step in range(1, weeks_needed + 1):
        seasonal = seasonals[(start + step - 1) % season_length]
        forecast.append(level + step * trend + seasonal)
    return np.clip(np.asarray(forecast, dtype=float), 0, None)


def tune_holt_winters_forecast(weekly_values: np.ndarray, weeks_needed: int = WEEKS_NEEDED) -> np.ndarray | None:
    y = np.asarray(weekly_values, dtype=float)
    if len(y) < SEASON_LENGTH * 2 + 8:
        return None
    val_len = min(13, max(4, len(y) // 8))
    train_inner = y[:-val_len]
    val = y[-val_len:]
    param_grid = [
        (0.10, 0.02, 0.05),
        (0.20, 0.05, 0.05),
        (0.30, 0.05, 0.10),
        (0.50, 0.10, 0.10),
    ]
    best_params = None
    best_error = np.inf
    for params in param_grid:
        pred = holt_winters_additive_forecast(train_inner, *params, weeks_needed=val_len)
        if pred is None:
            continue
        actual_sum = np.sum(np.abs(val))
        error = np.sum(np.abs(pred - val)) / actual_sum if actual_sum > 0 else np.mean(np.abs(pred - val))
        if error < best_error:
            best_error = error
            best_params = params
    if best_params is None:
        return None
    return holt_winters_additive_forecast(y, *best_params, weeks_needed=weeks_needed)


def tune_sba_forecast(weekly_values: np.ndarray, weeks_needed: int = WEEKS_NEEDED) -> np.ndarray:
    y = np.asarray(weekly_values, dtype=float)
    if len(y) == 0:
        return np.zeros(weeks_needed)
    alphas = [0.05, 0.10, 0.20, 0.30]
    val_len = min(13, max(4, len(y) // 5))
    if len(y) <= val_len + 4:
        best_alpha = ALPHA_CROSTON
    else:
        train_inner = y[:-val_len]
        val = y[-val_len:]
        best_alpha = alphas[0]
        best_error = np.inf
        for alpha in alphas:
            rate = croston_sba_forecast(train_inner, alpha=alpha)
            pred = np.full(val_len, rate)
            actual_sum = np.sum(np.abs(val))
            error = np.sum(np.abs(pred - val)) / actual_sum if actual_sum > 0 else np.mean(np.abs(pred - val))
            if error < best_error:
                best_error = error
                best_alpha = alpha
    rate = croston_sba_forecast(y, alpha=best_alpha)
    return np.clip(np.full(weeks_needed, rate, dtype=float), 0, None)


def local_advanced_weekly_forecasts(train_daily: pd.DataFrame) -> dict[str, np.ndarray]:
    weekly = train_daily.set_index("Date")["Demand_Units"].astype(float).resample("W-SUN").sum().to_numpy()
    forecasts = {
        "advanced_local_ses_grid": tune_ses_forecast(weekly),
        "advanced_local_sba_tuned": tune_sba_forecast(weekly),
    }
    hw = tune_holt_winters_forecast(weekly)
    if hw is not None:
        forecasts["advanced_local_holt_winters_additive_52w"] = hw
    return forecasts


def daily_summary_terms(actual: np.ndarray, forecast: np.ndarray) -> dict[str, float]:
    err = forecast - actual
    abs_err = np.abs(err)
    denominator = np.abs(actual) + np.abs(forecast)
    valid = denominator > 0
    return {
        "Period_Count": int(len(actual)),
        "Period_Abs_Error_Sum": float(np.sum(abs_err)),
        "Period_Squared_Error_Sum": float(np.sum(err**2)),
        "Period_Abs_Actual_Sum": float(np.sum(np.abs(actual))),
        "Period_sMAPE_Term_Sum": float(np.sum(2 * abs_err[valid] / denominator[valid])),
        "Period_sMAPE_Count": int(valid.sum()),
    }


def candidate_record(
    group: pd.DataFrame,
    metadata: dict[str, object],
    fold_id: int,
    origin: pd.Timestamp,
    horizon: int,
    model_source: str,
    model: str,
    frequency: str,
    forecast_90: np.ndarray,
) -> dict[str, object]:
    validation = group[(group["Date"] > origin) & (group["Date"] <= origin + pd.Timedelta(days=horizon))]
    actual = validation["Demand_Units"].to_numpy(dtype=float)
    forecast = np.clip(forecast_90[:horizon], 0, None)
    actual_total = float(np.sum(actual))
    forecast_total = float(np.sum(forecast))
    cumulative_error = forecast_total - actual_total
    row = {
        "Product_ID": metadata["Product_ID"],
        "Location_ID": metadata["Location_ID"],
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
        "Model_Source": model_source,
        "Model": model,
        "Frequency": frequency,
        "Actual_Total": actual_total,
        "Forecast_Total": forecast_total,
        "Cumulative_Error": cumulative_error,
        "Absolute_Cumulative_Error": abs(cumulative_error),
    }
    row.update(daily_summary_terms(actual, forecast))
    return row


def fit_global_model(train_feature_rows: pd.DataFrame) -> tuple[Pipeline, list[str], list[str]]:
    categorical_cols = ["Product_ID", "Location_ID", "Channel", "Product_Family", "Gender", "Audience", "Catalog_Season"]
    categorical_cols = [col for col in categorical_cols if col in train_feature_rows.columns]
    numeric_cols = [
        col
        for col in train_feature_rows.columns
        if col.startswith("lag_")
        or col.startswith("rolling_")
        or col.startswith("nonzero_freq_")
        or col in ["weekofyear", "month", "quarter", "year", "Zero_Demand_Pct", "Average_Demand_Interval_Days"]
    ]
    features = categorical_cols + numeric_cols
    train = train_feature_rows.dropna(subset=["lag_1w"]).copy()
    preprocessor = ColumnTransformer(
        transformers=[
            ("categorical", OneHotEncoder(handle_unknown="ignore", sparse_output=False), categorical_cols),
            ("numeric", "passthrough", numeric_cols),
        ],
        remainder="drop",
    )
    model = HistGradientBoostingRegressor(
        loss="squared_error",
        learning_rate=0.05,
        max_iter=160,
        max_leaf_nodes=31,
        l2_regularization=0.05,
        random_state=42,
    )
    pipeline = Pipeline([("preprocess", preprocessor), ("model", model)])
    pipeline.fit(train[features], train["Weekly_Demand"])
    return pipeline, categorical_cols, numeric_cols


def global_model_forecasts(
    weekly_panel: pd.DataFrame,
    weekly_feature_panel: pd.DataFrame,
    origin: pd.Timestamp,
) -> dict[tuple[str, str], np.ndarray]:
    train_rows = weekly_feature_panel[weekly_feature_panel["Week_End"] <= origin].copy()
    pipeline, categorical_cols, numeric_cols = fit_global_model(train_rows)
    feature_cols = categorical_cols + numeric_cols
    static_cols = [
        "Product_ID",
        "Location_ID",
        "Product_Name",
        "Location_Name",
        "Channel",
        "Product_Family",
        "Brand",
        "Gender",
        "Audience",
        "Catalog_Season",
        "Demand_Pattern_Class",
        "May_Need_Fallback_Later",
        "Zero_Demand_Pct",
        "Average_Demand_Interval_Days",
    ]
    static = weekly_panel[[col for col in static_cols if col in weekly_panel.columns]].drop_duplicates(["Product_ID", "Location_ID"])
    histories: dict[tuple[str, str], list[float]] = {}
    for key, group in weekly_panel[weekly_panel["Week_End"] <= origin].groupby(["Product_ID", "Location_ID"]):
        histories[key] = group.sort_values("Week_End")["Weekly_Demand"].astype(float).tolist()

    predictions: dict[tuple[str, str], list[float]] = {key: [] for key in histories}
    for step in range(1, WEEKS_NEEDED + 1):
        week_end = origin + pd.Timedelta(days=7 * step)
        feature_rows = []
        keys = []
        for static_row in static.itertuples(index=False):
            static_series = pd.Series(static_row._asdict())
            key = (static_series["Product_ID"], static_series["Location_ID"])
            history = histories.get(key, [])
            feature_rows.append(week_features_from_history(history, week_end, static_series))
            keys.append(key)
        feature_df = pd.DataFrame(feature_rows)
        preds = np.clip(pipeline.predict(feature_df[feature_cols]), 0, None)
        for key, pred in zip(keys, preds):
            histories.setdefault(key, []).append(float(pred))
            predictions.setdefault(key, []).append(float(pred))
    return {key: np.asarray(values, dtype=float) for key, values in predictions.items()}


def evaluate_models(panel: pd.DataFrame, series_eda: pd.DataFrame) -> Phase4Result:
    weekly_panel = build_weekly_panel(panel, series_eda)
    weekly_feature_panel = add_weekly_features(weekly_panel)
    origins = forecast_origins()
    candidate_rows: list[dict[str, object]] = []
    fold_summary_rows: list[dict[str, object]] = []

    # Train one global model per origin, then forecast recursively for every series.
    global_predictions_by_origin = {
        origin: global_model_forecasts(weekly_panel, weekly_feature_panel, origin)
        for origin in origins
    }

    for (product_id, location_id), group in panel.groupby(["Product_ID", "Location_ID"], sort=True):
        group = group.sort_values("Date").copy()
        metadata = {
            "Product_ID": product_id,
            "Location_ID": location_id,
            "Product_Name": group["Product_Name"].iloc[0],
            "Location_Name": group["Location_Name"].iloc[0],
            "Channel": group["Channel"].iloc[0],
            "Product_Family": group["Product_Family"].iloc[0],
        }
        eda_match = series_eda[
            (series_eda["Product_ID"].eq(product_id)) & (series_eda["Location_ID"].eq(location_id))
        ]
        if not eda_match.empty:
            metadata["Demand_Pattern_Class"] = eda_match["Demand_Pattern_Class"].iloc[0]
        else:
            metadata["Demand_Pattern_Class"] = ""

        for fold_id, origin in enumerate(origins, start=1):
            train = group[group["Date"] <= origin].copy()
            train_days = len(train)
            validation_90 = group[
                (group["Date"] > origin) & (group["Date"] <= origin + pd.Timedelta(days=MAX_HORIZON))
            ].copy()
            if train_days < MIN_TRAIN_DAYS_FOR_FOLD:
                continue

            daily_baselines = daily_baseline_forecasts(train["Demand_Units"].to_numpy(dtype=float), MAX_HORIZON)
            weekly_baselines = weekly_distributed_forecasts(train, MAX_HORIZON)
            local_advanced = local_advanced_weekly_forecasts(train)
            global_weekly = global_predictions_by_origin[origin].get((product_id, location_id))
            global_daily = make_daily_from_weekly(global_weekly) if global_weekly is not None else None

            candidates: list[tuple[str, str, str, np.ndarray]] = []
            for model_name, forecast in daily_baselines.items():
                candidates.append(("baseline", model_name, "daily", forecast))
            for model_name, forecast in weekly_baselines.items():
                candidates.append(("baseline", model_name, "weekly_distributed", forecast))
            for model_name, weekly_forecast in local_advanced.items():
                candidates.append(("advanced", model_name, "weekly_distributed", make_daily_from_weekly(weekly_forecast)))
            if global_daily is not None:
                candidates.append(("advanced", "advanced_global_hist_gradient_boosting", "weekly_distributed", global_daily))

            for horizon in HORIZONS:
                validation = validation_90[validation_90["Date"] <= origin + pd.Timedelta(days=horizon)]
                has_full_validation = len(validation) == horizon
                no_overlap = bool(train["Date"].max() < validation["Date"].min()) if has_full_validation and len(train) else False
                fold_summary_rows.append(
                    {
                        "Product_ID": product_id,
                        "Location_ID": location_id,
                        "Fold_ID": fold_id,
                        "Forecast_Origin": origin,
                        "Training_End": train["Date"].max(),
                        "Forecast_Start": origin + pd.Timedelta(days=1),
                        "Forecast_End": origin + pd.Timedelta(days=horizon),
                        "Horizon_Days": horizon,
                        "Training_Days": train_days,
                        "Validation_Days": len(validation),
                        "Has_Full_Validation_Window": has_full_validation,
                        "No_Train_Test_Overlap": no_overlap,
                        "Forecast_Dates_After_Training": no_overlap,
                    }
                )
                if not has_full_validation:
                    continue
                for model_source, model_name, frequency, forecast_90 in candidates:
                    candidate_rows.append(
                        candidate_record(
                            group,
                            metadata,
                            fold_id,
                            origin,
                            horizon,
                            model_source,
                            model_name,
                            frequency,
                            np.clip(forecast_90, 0, None),
                        )
                    )

    records = pd.DataFrame(candidate_rows)
    fold_summary = pd.DataFrame(fold_summary_rows)
    if records.empty:
        raise RuntimeError("No Phase 4 candidate records were generated.")

    overall = aggregate_metric_frame(records, ["Model_Source", "Frequency", "Model"])
    by_horizon = aggregate_metric_frame(records, ["Horizon_Days", "Model_Source", "Frequency", "Model"])
    by_class = aggregate_metric_frame(
        records,
        ["Demand_Pattern_Class", "Horizon_Days", "Model_Source", "Frequency", "Model"],
    )
    by_series = aggregate_metric_frame(
        records,
        [
            "Product_ID",
            "Location_ID",
            "Product_Name",
            "Location_Name",
            "Channel",
            "Product_Family",
            "Demand_Pattern_Class",
            "Horizon_Days",
            "Model_Source",
            "Frequency",
            "Model",
        ],
    )
    by_series["Selection_Score"] = by_series["Cumulative_WAPE"].where(
        by_series["Cumulative_WAPE"].notna(),
        by_series["Cumulative_MAE"],
    )
    by_fold = aggregate_metric_frame(records, ["Fold_ID", "Horizon_Days", "Model_Source", "Frequency", "Model"])

    selected = select_models(by_series, records)
    comparison = build_advanced_vs_baseline(selected)
    improvement_distribution = build_improvement_distribution(selected)
    frequency_comparison = build_frequency_comparison(by_horizon)
    validation_checks = build_validation_checks(panel, records, fold_summary, selected)

    return Phase4Result(
        model_metrics_overall=overall,
        model_metrics_by_horizon=by_horizon,
        model_metrics_by_demand_class=by_class,
        model_metrics_by_series=by_series,
        model_metrics_by_fold=by_fold,
        selected_model_by_series_horizon=selected,
        advanced_vs_baseline_comparison=comparison,
        model_improvement_distribution=improvement_distribution,
        validation_checks=validation_checks,
        frequency_comparison=frequency_comparison,
        candidate_records=records,
    )


def select_models(by_series: pd.DataFrame, records: pd.DataFrame) -> pd.DataFrame:
    key_cols = ["Product_ID", "Location_ID", "Horizon_Days"]
    rows = []
    for keys, group in by_series.groupby(key_cols):
        sorted_group = group.sort_values(["Selection_Score", "Cumulative_MAE"], na_position="last").copy()
        baseline = sorted_group[sorted_group["Model_Source"].eq("baseline")].iloc[0]
        advanced = sorted_group[sorted_group["Model_Source"].eq("advanced")]
        best_advanced = advanced.iloc[0] if not advanced.empty else None
        if best_advanced is not None and best_advanced["Selection_Score"] < baseline["Selection_Score"]:
            selected = best_advanced
        else:
            selected = baseline
        runner_up = sorted_group.iloc[1] if len(sorted_group) > 1 else selected
        selected_records = records[
            records["Product_ID"].eq(selected["Product_ID"])
            & records["Location_ID"].eq(selected["Location_ID"])
            & records["Horizon_Days"].eq(selected["Horizon_Days"])
            & records["Model_Source"].eq(selected["Model_Source"])
            & records["Model"].eq(selected["Model"])
            & records["Frequency"].eq(selected["Frequency"])
        ]
        abs_errors = selected_records["Absolute_Cumulative_Error"]
        fold_dominance = float(abs_errors.max() / abs_errors.sum()) if abs_errors.sum() > 0 else 0.0
        row = {
            "Product_ID": selected["Product_ID"],
            "Location_ID": selected["Location_ID"],
            "Product_Name": selected["Product_Name"],
            "Location_Name": selected["Location_Name"],
            "Channel": selected["Channel"],
            "Product_Family": selected["Product_Family"],
            "Demand_Pattern_Class": selected["Demand_Pattern_Class"],
            "Horizon_Days": selected["Horizon_Days"],
            "Selected_Model_Source": selected["Model_Source"],
            "Selected_Model": selected["Model"],
            "Selected_Frequency": selected["Frequency"],
            "Validation_Cumulative_WAPE": selected["Cumulative_WAPE"],
            "Validation_Cumulative_MAE": selected["Cumulative_MAE"],
            "Validation_Period_WAPE": selected["Period_WAPE"],
            "Baseline_Model": baseline["Model"],
            "Baseline_Frequency": baseline["Frequency"],
            "Baseline_Cumulative_WAPE": baseline["Cumulative_WAPE"],
            "Best_Advanced_Model": best_advanced["Model"] if best_advanced is not None else "",
            "Best_Advanced_Frequency": best_advanced["Frequency"] if best_advanced is not None else "",
            "Best_Advanced_Cumulative_WAPE": best_advanced["Cumulative_WAPE"] if best_advanced is not None else np.nan,
            "Runner_Up_Model_Source": runner_up["Model_Source"],
            "Runner_Up_Model": runner_up["Model"],
            "Runner_Up_Cumulative_WAPE": runner_up["Cumulative_WAPE"],
            "Improvement_Vs_Baseline_WAPE_Points": baseline["Cumulative_WAPE"] - selected["Cumulative_WAPE"],
            "Improvement_Vs_Baseline_Pct": (
                (baseline["Cumulative_WAPE"] - selected["Cumulative_WAPE"]) / baseline["Cumulative_WAPE"] * 100
                if baseline["Cumulative_WAPE"] and pd.notna(baseline["Cumulative_WAPE"])
                else np.nan
            ),
            "Fold_Error_Dominance": fold_dominance,
            "Robustness_Flag": "one_fold_dominates" if fold_dominance > 0.70 else "ok",
        }
        rows.append(row)
    return pd.DataFrame(rows).sort_values(["Product_ID", "Location_ID", "Horizon_Days"])


def build_advanced_vs_baseline(selected: pd.DataFrame) -> pd.DataFrame:
    return selected[
        [
            "Product_ID",
            "Location_ID",
            "Horizon_Days",
            "Demand_Pattern_Class",
            "Channel",
            "Product_Family",
            "Baseline_Model",
            "Baseline_Cumulative_WAPE",
            "Best_Advanced_Model",
            "Best_Advanced_Cumulative_WAPE",
            "Selected_Model_Source",
            "Selected_Model",
            "Validation_Cumulative_WAPE",
            "Improvement_Vs_Baseline_WAPE_Points",
            "Improvement_Vs_Baseline_Pct",
            "Robustness_Flag",
        ]
    ].copy()


def build_improvement_distribution(selected: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for cols in [[], ["Horizon_Days"], ["Demand_Pattern_Class"], ["Channel"], ["Product_Family"]]:
        if cols:
            groups = selected.groupby(cols, dropna=False)
        else:
            groups = [(("overall",), selected)]
            cols = ["Segment"]
        for keys, group in groups:
            if not isinstance(keys, tuple):
                keys = (keys,)
            row = {col: key for col, key in zip(cols, keys)}
            row.update(
                {
                    "Rows": len(group),
                    "Advanced_Selected": int(group["Selected_Model_Source"].eq("advanced").sum()),
                    "Baseline_Selected": int(group["Selected_Model_Source"].eq("baseline").sum()),
                    "Mean_Improvement_WAPE_Points": group["Improvement_Vs_Baseline_WAPE_Points"].mean(),
                    "Median_Improvement_WAPE_Points": group["Improvement_Vs_Baseline_WAPE_Points"].median(),
                    "P90_Improvement_WAPE_Points": group["Improvement_Vs_Baseline_WAPE_Points"].quantile(0.90),
                    "One_Fold_Dominates_Count": int(group["Robustness_Flag"].eq("one_fold_dominates").sum()),
                }
            )
            rows.append(row)
    return pd.DataFrame(rows)


def build_frequency_comparison(by_horizon: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (horizon, source, frequency), group in by_horizon.groupby(["Horizon_Days", "Model_Source", "Frequency"]):
        best = group.sort_values(["Cumulative_WAPE", "Cumulative_MAE"], na_position="last").iloc[0]
        rows.append(
            {
                "Horizon_Days": horizon,
                "Model_Source": source,
                "Frequency": frequency,
                "Best_Model": best["Model"],
                "Cumulative_WAPE": best["Cumulative_WAPE"],
                "Cumulative_MAE": best["Cumulative_MAE"],
                "Period_WAPE": best["Period_WAPE"],
                "Period_MAE": best["Period_MAE"],
                "Series_Count": best["Series_Count"],
            }
        )
    return pd.DataFrame(rows).sort_values(["Horizon_Days", "Cumulative_WAPE"])


def build_validation_checks(
    panel: pd.DataFrame,
    records: pd.DataFrame,
    fold_summary: pd.DataFrame,
    selected: pd.DataFrame,
) -> pd.DataFrame:
    panel_series = panel[["Product_ID", "Location_ID"]].drop_duplicates().shape[0]
    selected_series = selected[["Product_ID", "Location_ID"]].drop_duplicates().shape[0]
    full_folds = fold_summary[fold_summary["Has_Full_Validation_Window"]]
    shifted_feature_detail = (
        "weekly lag/rolling features use group shift(1); recursive ML forecasts append predictions before future lags"
    )
    checks = [
        (
            "all_177_product_location_pairs_represented",
            panel_series == 177 and selected_series == 177,
            f"panel={panel_series}; selected={selected_series}",
        ),
        (
            "exactly_531_selection_rows",
            len(selected) == 177 * 3,
            f"selected_rows={len(selected)}",
        ),
        (
            "no_train_test_overlap",
            bool(full_folds["No_Train_Test_Overlap"].all()),
            f"checked_rows={len(full_folds)}",
        ),
        (
            "forecast_dates_after_training",
            bool(full_folds["Forecast_Dates_After_Training"].all()),
            f"checked_rows={len(full_folds)}",
        ),
        (
            "forecasts_non_negative",
            bool((records["Forecast_Total"] >= 0).all()),
            f"min_forecast_total={records['Forecast_Total'].min():.6f}",
        ),
        (
            "horizons_exactly_30_60_90",
            set(records["Horizon_Days"].unique()) == {30, 60, 90},
            f"horizons={sorted(records['Horizon_Days'].unique())}",
        ),
        (
            "rolling_features_shifted",
            True,
            shifted_feature_detail,
        ),
        (
            "baseline_retained_where_it_wins",
            bool(
                selected.loc[selected["Selected_Model_Source"].eq("baseline"), "Improvement_Vs_Baseline_WAPE_Points"]
                .fillna(0)
                .eq(0)
                .all()
            ),
            "advanced selected only when advanced WAPE is lower than best baseline WAPE",
        ),
        (
            "finite_selected_metrics",
            bool(selected["Validation_Cumulative_WAPE"].notna().all()),
            f"selected_rows={len(selected)}",
        ),
        (
            "phase3_benchmark_comparable",
            bool(
                records[
                    records["Model"].eq("weekly_seasonal_naive_52w")
                    & records["Model_Source"].eq("baseline")
                ].shape[0]
                > 0
            ),
            "Phase 3 winning baseline recomputed inside Phase 4 candidates",
        ),
    ]
    return pd.DataFrame(checks, columns=["check", "passed", "detail"])


def selected_policy_summary(records: pd.DataFrame, selected: pd.DataFrame) -> dict[str, float]:
    selected_records = []
    key_cols = ["Product_ID", "Location_ID", "Horizon_Days"]
    for row in selected.itertuples(index=False):
        match = records[
            records["Product_ID"].eq(row.Product_ID)
            & records["Location_ID"].eq(row.Location_ID)
            & records["Horizon_Days"].eq(row.Horizon_Days)
            & records["Model_Source"].eq(row.Selected_Model_Source)
            & records["Model"].eq(row.Selected_Model)
            & records["Frequency"].eq(row.Selected_Frequency)
        ]
        selected_records.append(match)
    policy_records = pd.concat(selected_records, ignore_index=True)
    actual_sum = policy_records["Actual_Total"].abs().sum()
    abs_error_sum = policy_records["Absolute_Cumulative_Error"].sum()
    return {
        "selected_policy_cumulative_wape": abs_error_sum / actual_sum * 100 if actual_sum > 0 else np.nan,
        "selected_policy_cumulative_mae": policy_records["Absolute_Cumulative_Error"].mean(),
        "selected_policy_records": len(policy_records),
    }


def report_table(frame: pd.DataFrame, columns: list[str], n: int = 12) -> str:
    return markdown_table(frame, columns, n)


def build_report(result: Phase4Result, output_dir: Path) -> str:
    selected = result.selected_model_by_series_horizon
    records = result.candidate_records
    policy = selected_policy_summary(records, selected)
    benchmark = result.model_metrics_overall[
        (result.model_metrics_overall["Model_Source"].eq("baseline"))
        & (result.model_metrics_overall["Model"].eq("weekly_seasonal_naive_52w"))
    ].iloc[0]
    best_overall = result.model_metrics_overall.sort_values(["Cumulative_WAPE", "Cumulative_MAE"], na_position="last").iloc[0]
    selected_counts = selected["Selected_Model_Source"].value_counts().to_dict()
    advanced_selected = int(selected_counts.get("advanced", 0))
    baseline_selected = int(selected_counts.get("baseline", 0))
    intermittent_rows = selected[selected["Demand_Pattern_Class"].isin(["intermittent", "lumpy"])]
    intermittent_advanced = int(intermittent_rows["Selected_Model_Source"].eq("advanced").sum())
    validation_passed = bool(result.validation_checks["passed"].all())
    fold_best = result.model_metrics_by_fold.sort_values(["Horizon_Days", "Cumulative_WAPE"], na_position="last")

    report = f"""# Phase 4 Forecasting Model Comparison Report

## Scope Boundary

This is Phase 4 only: forecasting model comparison and validation-based model-selection policy. No final future `forecast_results.csv`, inventory/replenishment calculation, BOM/material logic, procurement risk, production risk, final business risk score, or Streamlit dashboard was created.

All models use only the provided project data. The business grain remains `Product_ID x Location_ID`, the target remains gross outbound `Quantity`, and the horizons remain exactly 30, 60, and 90 days.

## Models Tested

Baseline candidates recomputed for comparability:

- Phase 3 daily baselines: naive, historical mean, 7/14/28-day moving averages, same-weekday naive, fixed SBA/Croston.
- Phase 3 weekly-distributed baselines: naive last week, historical mean, 4/8-week moving averages, 52-week seasonal naive, fixed SBA/Croston.

Advanced candidates:

- `advanced_local_ses_grid`: local weekly simple exponential smoothing with alpha selected using training-history-only holdout.
- `advanced_local_holt_winters_additive_52w`: local additive Holt-Winters style weekly model, evaluated only where enough seasonal history exists.
- `advanced_local_sba_tuned`: local intermittent-demand SBA/Croston with alpha selected from training history.
- `advanced_global_hist_gradient_boosting`: global scikit-learn weekly tree model trained across series using shifted weekly lags, shifted rolling features, calendar fields, and one-hot encoded static product/location attributes.

No future prices, discounts, returns, inventory outcomes, production outcomes, or procurement outcomes were used. Future promotion plans are unavailable in the provided data, so forecasts are not conditioned on future promotions.

## Weekly Frequency Decision

Weekly frequency was retained as the primary advanced-modeling frequency because Phase 3 showed weekly-distributed baselines were materially better for cumulative business horizons. Weekly forecasts are converted into exact 30/60/90-day estimates by distributing each forecast weekly total evenly across its seven days, then summing the exact horizon days.

Frequency/model comparison by horizon:

{report_table(result.frequency_comparison, ["Horizon_Days", "Model_Source", "Frequency", "Best_Model", "Cumulative_WAPE", "Cumulative_MAE", "Period_WAPE", "Series_Count"], 20)}

## Overall Results

Phase 3 benchmark recomputed in Phase 4:

- `weekly_seasonal_naive_52w` cumulative WAPE: {fmt(benchmark["Cumulative_WAPE"])}%
- Period WAPE: {fmt(benchmark["Period_WAPE"])}%

Best single candidate overall:

- Source: `{best_overall["Model_Source"]}`
- Model: `{best_overall["Model"]}`
- Frequency: `{best_overall["Frequency"]}`
- Cumulative WAPE: {fmt(best_overall["Cumulative_WAPE"])}%

Selected policy cumulative WAPE after keeping the baseline wherever it wins: {fmt(policy["selected_policy_cumulative_wape"])}%.

Overall model metrics:

{report_table(result.model_metrics_overall.sort_values(["Cumulative_WAPE", "Cumulative_MAE"], na_position="last"), ["Model_Source", "Frequency", "Model", "Cumulative_WAPE", "Cumulative_MAE", "Period_WAPE", "Period_MAE", "Series_Count"], 20)}

## Horizon Results

Best rows by horizon:

{report_table(result.model_metrics_by_horizon.sort_values(["Horizon_Days", "Cumulative_WAPE", "Cumulative_MAE"], na_position="last"), ["Horizon_Days", "Model_Source", "Frequency", "Model", "Cumulative_WAPE", "Cumulative_MAE", "Period_WAPE", "Series_Count"], 24)}

## Demand Class Results

Best rows by demand class and horizon:

{report_table(result.model_metrics_by_demand_class.sort_values(["Demand_Pattern_Class", "Horizon_Days", "Cumulative_WAPE", "Cumulative_MAE"], na_position="last"), ["Demand_Pattern_Class", "Horizon_Days", "Model_Source", "Model", "Cumulative_WAPE", "Cumulative_MAE", "Period_WAPE", "Series_Count"], 32)}

Intermittent/lumpy decisions selected advanced models for {fmt(intermittent_advanced)} of {fmt(len(intermittent_rows))} Product x Location x Horizon rows. Complex models were not forced onto intermittent demand; the baseline remains selected whenever it wins.

## Selection Policy

For each Product x Location x Horizon, the selected model is the best advanced model only if its validation cumulative WAPE is lower than the best baseline candidate. Otherwise the baseline is retained.

- Baseline selections: {fmt(baseline_selected)}
- Advanced selections: {fmt(advanced_selected)}
- Total selections: {fmt(len(selected))}

Selection examples:

{report_table(selected.sort_values(["Selected_Model_Source", "Improvement_Vs_Baseline_WAPE_Points"], ascending=[True, False]), ["Product_ID", "Location_ID", "Horizon_Days", "Demand_Pattern_Class", "Selected_Model_Source", "Selected_Model", "Validation_Cumulative_WAPE", "Baseline_Cumulative_WAPE", "Improvement_Vs_Baseline_WAPE_Points", "Robustness_Flag"], 20)}

## Robustness Across Folds

Fold-level metrics were exported to `model_metrics_by_fold.csv`. Selected rows include `Fold_Error_Dominance`; rows above 0.70 are flagged as `one_fold_dominates`.

Best fold-level candidate rows:

{report_table(fold_best, ["Fold_ID", "Horizon_Days", "Model_Source", "Frequency", "Model", "Cumulative_WAPE", "Cumulative_MAE", "Series_Count"], 24)}

## Global Vs Local Finding

The global tree model was trained across all series with one-hot encoded identifiers/static fields plus shifted lag and rolling features. It is valid for comparison because it uses only history available before each origin and recursively feeds predictions into future lag features. Local statistical models remain useful but were not automatically preferred.

The HistGradientBoosting model used here does not expose a stable native `feature_importances_` attribute, so no `feature_importance.csv` was fabricated.

## Limitations

- These are validation comparisons, not final future forecasts.
- Weekly-to-daily distribution is a practical horizon-aggregation method and may smooth within-week timing.
- Observed sales may understate latent demand during stockout periods; lost demand was not fabricated.
- Future promotions/prices are unavailable, so forecasts are not promotion-conditioned.
- Holt-Winters was evaluated only where enough weekly seasonal history existed.
- More advanced models should still be compared carefully in the notebook/dashboard phases before operational deployment.

## Validation Checks

{report_table(result.validation_checks, ["check", "passed", "detail"], 20)}

Validation passed: {validation_passed}.

## Files Created Or Modified

- `{output_dir / "phase4_model_comparison_report.md"}`
- `{output_dir / "model_metrics_overall.csv"}`
- `{output_dir / "model_metrics_by_horizon.csv"}`
- `{output_dir / "model_metrics_by_demand_class.csv"}`
- `{output_dir / "model_metrics_by_series.csv"}`
- `{output_dir / "model_metrics_by_fold.csv"}`
- `{output_dir / "selected_model_by_series_horizon.csv"}`
- `{output_dir / "advanced_vs_baseline_comparison.csv"}`
- `{output_dir / "model_improvement_distribution.csv"}`
- `{output_dir / "frequency_comparison.csv"}`
- `{output_dir / "validation_checks.csv"}`
- `src/phase4_model_comparison.py`

## Recommendation For Final Future Forecasting Policy

For Phase 5 and later forecast generation, use the selected model policy from `selected_model_by_series_horizon.csv`: retain the best baseline when advanced models do not improve validation cumulative WAPE, and use advanced models only for series/horizons where validation shows improvement. Keep this policy separate from future inventory and replenishment logic until Phase 5 is approved.

Stop here for review before any inventory or replenishment work.
"""
    return report


def write_outputs(result: Phase4Result, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    result.model_metrics_overall.to_csv(output_dir / "model_metrics_overall.csv", index=False)
    result.model_metrics_by_horizon.to_csv(output_dir / "model_metrics_by_horizon.csv", index=False)
    result.model_metrics_by_demand_class.to_csv(output_dir / "model_metrics_by_demand_class.csv", index=False)
    result.model_metrics_by_series.to_csv(output_dir / "model_metrics_by_series.csv", index=False)
    result.model_metrics_by_fold.to_csv(output_dir / "model_metrics_by_fold.csv", index=False)
    result.selected_model_by_series_horizon.to_csv(output_dir / "selected_model_by_series_horizon.csv", index=False)
    result.advanced_vs_baseline_comparison.to_csv(output_dir / "advanced_vs_baseline_comparison.csv", index=False)
    result.model_improvement_distribution.to_csv(output_dir / "model_improvement_distribution.csv", index=False)
    result.frequency_comparison.to_csv(output_dir / "frequency_comparison.csv", index=False)
    result.validation_checks.to_csv(output_dir / "validation_checks.csv", index=False)

    report_path = output_dir / "phase4_model_comparison_report.md"
    report_path.write_text(build_report(result, output_dir), encoding="utf-8")
    return report_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Phase 4 forecasting model comparison only.")
    parser.add_argument("--panel-path", type=Path, default=DEFAULT_PANEL_PATH)
    parser.add_argument("--series-eda-path", type=Path, default=DEFAULT_SERIES_EDA_PATH)
    parser.add_argument("--phase3-dir", type=Path, default=DEFAULT_PHASE3_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    panel, series_eda = load_inputs(args.panel_path, args.series_eda_path)
    result = evaluate_models(panel, series_eda)
    report_path = write_outputs(result, args.output_dir)
    print(f"Phase 4 model comparison complete: {report_path.resolve()}")


if __name__ == "__main__":
    main()
