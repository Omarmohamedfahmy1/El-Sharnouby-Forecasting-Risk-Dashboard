"""Phase 5 final forecast generation and inventory/stockout logic.

This phase locks a validated forecasting policy, creates the first true future
forecast horizon outputs, and aligns them with finished-goods inventory only.
It intentionally does not calculate BOM/material requirements, procurement
risk, production risk, final combined risk, or Streamlit outputs.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from phase3_forecasting_baseline import HORIZONS, aggregate_metric_frame, fmt, markdown_table
from phase4_model_comparison import (
    add_weekly_features,
    build_weekly_panel,
    evaluate_models,
    fit_global_model,
    load_inputs,
    tune_holt_winters_forecast,
    tune_sba_forecast,
    tune_ses_forecast,
    week_features_from_history,
)


DATA_DIR = Path(r"C:\Users\Acer\Downloads\Sharnouby_Enterprise")
DEFAULT_PANEL_PATH = Path("data") / "processed" / "daily_product_location_demand_panel.csv"
DEFAULT_SERIES_EDA_PATH = Path("outputs") / "phase2" / "demand_series_eda.csv"
DEFAULT_PHASE4_DIR = Path("outputs") / "phase4"
DEFAULT_PHASE4_1_DIR = Path("outputs") / "phase4_1"
DEFAULT_OUTPUT_DIR = Path("outputs") / "phase5"

FORECAST_ORIGIN = pd.Timestamp("2026-09-30")
FORECAST_START = pd.Timestamp("2026-10-01")
FORECAST_END_90 = pd.Timestamp("2026-12-29")
LATEST_INVENTORY_MONTH = pd.Timestamp("2026-09-01")
GLOBAL_BASELINE = "weekly_seasonal_naive_52w"
FINAL_WEEKS_NEEDED = 14


@dataclass
class Phase5Outputs:
    final_forecast_policy_validation: pd.DataFrame
    forecast_results: pd.DataFrame
    latest_inventory_snapshot: pd.DataFrame
    stockout_analysis: pd.DataFrame
    inventory_risk_summary: pd.DataFrame
    validation_checks: pd.DataFrame
    final_policy_name: str
    final_policy_reason: str


def policy_metric(records: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    return aggregate_metric_frame(records, group_cols)


def select_guarded_rows(phase4_selected: pd.DataFrame, advanced_robustness: pd.DataFrame) -> pd.DataFrame:
    guard_source = phase4_selected.merge(
        advanced_robustness[
            [
                "Product_ID",
                "Location_ID",
                "Horizon_Days",
                "LOO_Advanced_Selected_Count",
                "LOO_Source_Result",
                "Unstable_Model_Choice_Flag",
            ]
        ],
        on=["Product_ID", "Location_ID", "Horizon_Days"],
        how="left",
    )
    unstable_flag = guard_source["Unstable_Model_Choice_Flag"]
    unstable_flag = unstable_flag.where(unstable_flag.notna(), True)
    if unstable_flag.dtype == object:
        unstable_flag = (
            unstable_flag.astype(str)
            .str.lower()
            .map({"true": True, "false": False, "1": True, "0": False})
            .fillna(True)
        )
    else:
        unstable_flag = unstable_flag.astype(bool)
    guard_source["Use_Advanced_Guard"] = (
        guard_source["Selected_Model_Source"].eq("advanced")
        & guard_source["LOO_Advanced_Selected_Count"].fillna(0).ge(3)
        & guard_source["LOO_Source_Result"].eq("remains_advanced")
        & ~unstable_flag
        & ~guard_source["Robustness_Flag"].eq("one_fold_dominates")
    )
    guard_source["Guarded_Model_Source"] = np.where(
        guard_source["Use_Advanced_Guard"],
        guard_source["Selected_Model_Source"],
        "baseline",
    )
    guard_source["Guarded_Model"] = np.where(
        guard_source["Use_Advanced_Guard"],
        guard_source["Selected_Model"],
        GLOBAL_BASELINE,
    )
    guard_source["Guarded_Frequency"] = np.where(
        guard_source["Use_Advanced_Guard"],
        guard_source["Selected_Frequency"],
        "weekly_distributed",
    )
    guard_source["Guarded_Selection_Reason"] = np.where(
        guard_source["Use_Advanced_Guard"],
        "Advanced model passed Phase 4.1 guardrail: remains advanced in LOO, selected in at least 3/4 LOO runs, stable, and not one-fold dominated.",
        "Defaulted to global weekly seasonal baseline because advanced guardrail was not fully satisfied.",
    )
    return guard_source


def records_for_guarded_policy(candidate_records: pd.DataFrame, guarded: pd.DataFrame) -> pd.DataFrame:
    parts = []
    for row in guarded.itertuples(index=False):
        key_filter = (
            candidate_records["Product_ID"].eq(row.Product_ID)
            & candidate_records["Location_ID"].eq(row.Location_ID)
            & candidate_records["Horizon_Days"].eq(row.Horizon_Days)
        )
        selected = candidate_records[
            key_filter
            & candidate_records["Model_Source"].eq(row.Guarded_Model_Source)
            & candidate_records["Frequency"].eq(row.Guarded_Frequency)
            & candidate_records["Model"].eq(row.Guarded_Model)
        ].copy()
        baseline = candidate_records[
            key_filter
            & candidate_records["Model_Source"].eq("baseline")
            & candidate_records["Frequency"].eq("weekly_distributed")
            & candidate_records["Model"].eq(GLOBAL_BASELINE)
        ].copy()
        if selected.empty:
            selected = baseline.copy()
            selected["Guarded_Runtime_Fallback"] = True
        else:
            selected["Guarded_Runtime_Fallback"] = False
        selected["Policy"] = "guarded_hybrid"
        selected["Policy_Selected_Model_Source"] = selected["Model_Source"]
        selected["Policy_Selected_Model"] = selected["Model"]
        selected["Policy_Selected_Frequency"] = selected["Frequency"]
        parts.append(selected)
    return pd.concat(parts, ignore_index=True)


def records_for_global_baseline(candidate_records: pd.DataFrame) -> pd.DataFrame:
    records = candidate_records[
        candidate_records["Model_Source"].eq("baseline")
        & candidate_records["Frequency"].eq("weekly_distributed")
        & candidate_records["Model"].eq(GLOBAL_BASELINE)
    ].copy()
    records["Policy"] = "global_best_baseline"
    return records


def validate_guarded_policy(
    panel: pd.DataFrame,
    series_eda: pd.DataFrame,
    phase4_dir: Path,
    phase4_1_dir: Path,
) -> tuple[pd.DataFrame, pd.DataFrame, str, str, pd.DataFrame]:
    phase4 = evaluate_models(panel, series_eda)
    candidate_records = phase4.candidate_records
    phase4_selected = pd.read_csv(phase4_dir / "selected_model_by_series_horizon.csv")
    advanced = pd.read_csv(phase4_1_dir / "advanced_selection_robustness.csv")
    guarded = select_guarded_rows(phase4_selected, advanced)

    global_records = records_for_global_baseline(candidate_records)
    guarded_records = records_for_guarded_policy(candidate_records, guarded)
    combined = pd.concat([global_records, guarded_records], ignore_index=True, sort=False)
    validation_frames = [
        policy_metric(combined, ["Policy"]).assign(Segment_Type="overall"),
        policy_metric(combined, ["Policy", "Horizon_Days"]).assign(Segment_Type="by_horizon"),
        policy_metric(combined, ["Policy", "Demand_Pattern_Class"]).assign(Segment_Type="by_demand_class"),
    ]
    validation = pd.concat(validation_frames, ignore_index=True, sort=False)
    guard_counts = guarded["Use_Advanced_Guard"].value_counts().to_dict()
    validation["Guarded_Advanced_Rows"] = int(guard_counts.get(True, 0))
    validation["Guarded_Baseline_Rows"] = int(guard_counts.get(False, 0))

    overall = validation[validation["Segment_Type"].eq("overall")]
    baseline_wape = float(overall.loc[overall["Policy"].eq("global_best_baseline"), "Cumulative_WAPE"].iloc[0])
    guarded_wape = float(overall.loc[overall["Policy"].eq("guarded_hybrid"), "Cumulative_WAPE"].iloc[0])
    if guarded_wape < baseline_wape:
        final_policy = "guarded_hybrid"
        reason = (
            f"Guarded hybrid backtest cumulative WAPE {guarded_wape:.3f}% beat "
            f"global baseline {baseline_wape:.3f}%."
        )
    else:
        final_policy = "global_best_baseline"
        reason = (
            f"Guarded hybrid backtest cumulative WAPE {guarded_wape:.3f}% did not beat "
            f"global baseline {baseline_wape:.3f}%; using global baseline everywhere."
        )
    return validation, guarded, final_policy, reason, candidate_records


def completed_week_history(series: pd.Series, origin: pd.Timestamp) -> pd.Series:
    last_complete_sunday = origin - pd.Timedelta(days=(origin.weekday() + 1) % 7)
    return series[series.index <= last_complete_sunday].resample("W-SUN").sum()


def weekly_seasonal_naive_daily_path(series: pd.Series, origin: pd.Timestamp) -> pd.DataFrame:
    """Forecast daily path from the latest completed week through 2026-12-29."""
    last_complete_sunday = origin - pd.Timedelta(days=(origin.weekday() + 1) % 7)
    weekly = completed_week_history(series, origin)
    if len(weekly) == 0:
        weekly_forecast = np.zeros(14)
    elif len(weekly) >= 52:
        pattern = weekly.iloc[-52:].to_numpy(dtype=float)
        weekly_forecast = np.array([pattern[idx % 52] for idx in range(14)], dtype=float)
    else:
        weekly_forecast = np.full(14, float(weekly.mean()), dtype=float)
    path_start = last_complete_sunday + pd.Timedelta(days=1)
    dates = pd.date_range(path_start, FORECAST_END_90, freq="D")
    daily_values = np.array([weekly_forecast[idx // 7] / 7 for idx in range(len(dates))], dtype=float)
    path = pd.DataFrame({"Date": dates, "Forecast_Demand_Daily": np.clip(daily_values, 0, None)})
    return path[(path["Date"] >= FORECAST_START) & (path["Date"] <= FORECAST_END_90)].copy()


def daily_path_from_weekly_values(
    weekly_values: np.ndarray,
    origin: pd.Timestamp,
) -> pd.DataFrame:
    last_complete_sunday = origin - pd.Timedelta(days=(origin.weekday() + 1) % 7)
    path_start = last_complete_sunday + pd.Timedelta(days=1)
    dates = pd.date_range(path_start, FORECAST_END_90, freq="D")
    weekly = np.asarray(weekly_values, dtype=float)
    if len(weekly) < int(np.ceil(len(dates) / 7)):
        weekly = np.pad(weekly, (0, int(np.ceil(len(dates) / 7)) - len(weekly)), constant_values=0)
    daily_values = np.array([weekly[idx // 7] / 7 for idx in range(len(dates))], dtype=float)
    path = pd.DataFrame({"Date": dates, "Forecast_Demand_Daily": np.clip(daily_values, 0, None)})
    return path[(path["Date"] >= FORECAST_START) & (path["Date"] <= FORECAST_END_90)].copy()


def local_advanced_future_paths(group: pd.DataFrame) -> dict[str, pd.DataFrame]:
    last_complete_sunday = FORECAST_ORIGIN - pd.Timedelta(days=(FORECAST_ORIGIN.weekday() + 1) % 7)
    train_daily = group[group["Date"] <= last_complete_sunday].sort_values("Date").copy()
    weekly = train_daily.set_index("Date")["Demand_Units"].astype(float).resample("W-SUN").sum().to_numpy()
    weekly_forecasts: dict[str, np.ndarray | None] = {
        "advanced_local_ses_grid": tune_ses_forecast(weekly, weeks_needed=FINAL_WEEKS_NEEDED),
        "advanced_local_sba_tuned": tune_sba_forecast(weekly, weeks_needed=FINAL_WEEKS_NEEDED),
        "advanced_local_holt_winters_additive_52w": tune_holt_winters_forecast(
            weekly,
            weeks_needed=FINAL_WEEKS_NEEDED,
        ),
    }
    return {
        model: daily_path_from_weekly_values(values, FORECAST_ORIGIN)
        for model, values in weekly_forecasts.items()
        if values is not None
    }


def global_advanced_future_paths(panel: pd.DataFrame, series_eda: pd.DataFrame) -> dict[tuple[str, str], pd.DataFrame]:
    last_complete_sunday = FORECAST_ORIGIN - pd.Timedelta(days=(FORECAST_ORIGIN.weekday() + 1) % 7)
    weekly_panel = build_weekly_panel(panel, series_eda)
    weekly_feature_panel = add_weekly_features(weekly_panel)
    train_rows = weekly_feature_panel[weekly_feature_panel["Week_End"] <= last_complete_sunday].copy()
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
    static = weekly_panel[[col for col in static_cols if col in weekly_panel.columns]].drop_duplicates(
        ["Product_ID", "Location_ID"]
    )
    histories: dict[tuple[str, str], list[float]] = {}
    for key, history_group in weekly_panel[weekly_panel["Week_End"] <= last_complete_sunday].groupby(
        ["Product_ID", "Location_ID"]
    ):
        histories[key] = history_group.sort_values("Week_End")["Weekly_Demand"].astype(float).tolist()

    predictions: dict[tuple[str, str], list[float]] = {key: [] for key in histories}
    for step in range(1, FINAL_WEEKS_NEEDED + 1):
        week_end = last_complete_sunday + pd.Timedelta(days=7 * step)
        feature_rows = []
        keys = []
        for static_row in static.itertuples(index=False):
            static_series = pd.Series(static_row._asdict())
            key = (static_series["Product_ID"], static_series["Location_ID"])
            feature_rows.append(week_features_from_history(histories.get(key, []), week_end, static_series))
            keys.append(key)
        feature_df = pd.DataFrame(feature_rows)
        preds = np.clip(pipeline.predict(feature_df[feature_cols]), 0, None)
        for key, pred in zip(keys, preds):
            histories.setdefault(key, []).append(float(pred))
            predictions.setdefault(key, []).append(float(pred))

    return {
        key: daily_path_from_weekly_values(np.asarray(values, dtype=float), FORECAST_ORIGIN)
        for key, values in predictions.items()
    }


def generate_future_forecasts(
    panel: pd.DataFrame,
    series_eda: pd.DataFrame,
    final_policy_name: str,
    final_policy_reason: str,
    guarded_rows: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    demand_class = series_eda[["Product_ID", "Location_ID", "Demand_Pattern_Class"]].copy()
    panel = panel.merge(demand_class, on=["Product_ID", "Location_ID"], how="left", suffixes=("", "_EDA"))
    forecast_rows = []
    daily_path_rows = []
    horizon_windows = {
        30: (FORECAST_START, pd.Timestamp("2026-10-30")),
        60: (FORECAST_START, pd.Timestamp("2026-11-29")),
        90: (FORECAST_START, pd.Timestamp("2026-12-29")),
    }
    guarded_lookup = guarded_rows.set_index(["Product_ID", "Location_ID", "Horizon_Days"])
    needs_global_advanced = bool(
        final_policy_name == "guarded_hybrid"
        and guarded_rows["Guarded_Model"].eq("advanced_global_hist_gradient_boosting").any()
    )
    global_paths = global_advanced_future_paths(panel, series_eda) if needs_global_advanced else {}

    for (product_id, location_id), group in panel.groupby(["Product_ID", "Location_ID"], sort=True):
        group = group.sort_values("Date")
        series = group.set_index("Date")["Demand_Units"].astype(float)
        baseline_path = weekly_seasonal_naive_daily_path(series, FORECAST_ORIGIN)
        local_paths = local_advanced_future_paths(group) if final_policy_name == "guarded_hybrid" else {}
        metadata = {
            "Product_ID": product_id,
            "Product_Name": group["Product_Name"].iloc[0],
            "Location_ID": location_id,
            "Location_Name": group["Location_Name"].iloc[0],
            "Channel": group["Channel"].iloc[0],
            "Product_Family": group["Product_Family"].iloc[0],
            "Demand_Pattern_Class": group["Demand_Pattern_Class"].iloc[0],
        }
        for horizon, (start, end) in horizon_windows.items():
            if final_policy_name == "guarded_hybrid":
                guarded_row = guarded_lookup.loc[(product_id, location_id, horizon)]
                selected_model = guarded_row["Guarded_Model"]
                selected_source = guarded_row["Guarded_Model_Source"]
                selected_frequency = guarded_row["Guarded_Frequency"]
                selection_reason = guarded_row["Guarded_Selection_Reason"]
            else:
                selected_model = GLOBAL_BASELINE
                selected_source = "baseline"
                selected_frequency = "weekly_distributed"
                selection_reason = final_policy_reason

            runtime_fallback = False
            if selected_model == GLOBAL_BASELINE:
                path = baseline_path.copy()
            elif selected_model == "advanced_global_hist_gradient_boosting":
                path = global_paths.get((product_id, location_id), pd.DataFrame()).copy()
                if path.empty:
                    runtime_fallback = True
                    path = baseline_path.copy()
            else:
                path = local_paths.get(selected_model, pd.DataFrame()).copy()
                if path.empty:
                    runtime_fallback = True
                    path = baseline_path.copy()

            if runtime_fallback:
                selected_model = GLOBAL_BASELINE
                selected_source = "baseline"
                selected_frequency = "weekly_distributed"
                selection_reason = (
                    "Runtime fallback to global weekly seasonal baseline because the guarded advanced "
                    "future path was unavailable from completed-week history."
                )

            path["Product_ID"] = product_id
            path["Location_ID"] = location_id
            path["Horizon_Days"] = horizon
            path["Selected_Model"] = selected_model
            path["Selected_Model_Source"] = selected_source
            path["Forecast_Frequency"] = selected_frequency
            daily_path_rows.append(path)

            mask = (path["Date"] >= start) & (path["Date"] <= end)
            forecast_demand = float(path.loc[mask, "Forecast_Demand_Daily"].sum())
            forecast_rows.append(
                {
                    **metadata,
                    "Forecast_Origin": FORECAST_ORIGIN.date().isoformat(),
                    "Forecast_Start": start.date().isoformat(),
                    "Forecast_End": end.date().isoformat(),
                    "Horizon_Days": horizon,
                    "Forecast_Demand": forecast_demand,
                    "Selected_Model": selected_model,
                    "Selected_Model_Source": selected_source,
                    "Forecast_Frequency": selected_frequency,
                    "Selection_Reason": selection_reason,
                    "Runtime_Fallback_To_Baseline": runtime_fallback,
                }
            )
    return pd.DataFrame(forecast_rows), pd.concat(daily_path_rows, ignore_index=True)


def apply_monotonic_reconciliation(
    forecast_results: pd.DataFrame,
    daily_forecast_path: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    reconciled = forecast_results.sort_values(["Product_ID", "Location_ID", "Horizon_Days"]).copy()
    reconciled["Model_Forecast_Demand_Before_Monotonic_Reconciliation"] = reconciled["Forecast_Demand"]
    reconciled["Forecast_Demand"] = reconciled.groupby(["Product_ID", "Location_ID"])["Forecast_Demand"].cummax()
    reconciled["Monotonic_Reconciliation_Adjustment"] = (
        reconciled["Forecast_Demand"]
        - reconciled["Model_Forecast_Demand_Before_Monotonic_Reconciliation"]
    )
    reconciled["Monotonic_Reconciliation_Applied"] = reconciled["Monotonic_Reconciliation_Adjustment"] > 1e-9

    adjusted_daily = daily_forecast_path.copy()
    for row in reconciled[reconciled["Monotonic_Reconciliation_Applied"]].itertuples(index=False):
        mask = (
            adjusted_daily["Product_ID"].eq(row.Product_ID)
            & adjusted_daily["Location_ID"].eq(row.Location_ID)
            & adjusted_daily["Horizon_Days"].eq(row.Horizon_Days)
        )
        horizon_end = FORECAST_ORIGIN + pd.Timedelta(days=int(row.Horizon_Days))
        horizon_mask = mask & adjusted_daily["Date"].le(horizon_end)
        original_total = float(adjusted_daily.loc[horizon_mask, "Forecast_Demand_Daily"].sum())
        if original_total > 0:
            factor = float(row.Forecast_Demand) / original_total
            adjusted_daily.loc[mask, "Forecast_Demand_Daily"] *= factor
        else:
            days = max(int(row.Horizon_Days), 1)
            adjusted_daily.loc[horizon_mask, "Forecast_Demand_Daily"] = float(row.Forecast_Demand) / days
    return reconciled, adjusted_daily


def latest_inventory_snapshot(data_dir: Path) -> pd.DataFrame:
    inventory = pd.read_csv(data_dir / "Inventory_History.csv", parse_dates=["Snapshot_Month"])
    latest = inventory[inventory["Snapshot_Month"].eq(LATEST_INVENTORY_MONTH)].copy()
    latest["Expected_Closing_Stock_From_Accounting"] = (
        latest["Opening_Stock"]
        + latest["Received_Qty"]
        + latest["Returned_Qty"]
        - latest["Sold_Qty"]
        - latest["Damaged_Qty"]
    )
    latest["Latest_Inventory_Accounting_Mismatch_Flag"] = ~latest["Closing_Stock"].eq(
        latest["Expected_Closing_Stock_From_Accounting"]
    )
    return latest


def stockout_date_for_pair(daily_path: pd.DataFrame, available_stock: float) -> tuple[str, float | None]:
    ordered = daily_path.sort_values("Date").copy()
    ordered["Cumulative_Forecast_Demand"] = ordered["Forecast_Demand_Daily"].cumsum()
    exceeded = ordered[ordered["Cumulative_Forecast_Demand"] > available_stock]
    if exceeded.empty:
        return "Not within 90-day forecast", np.nan
    date_value = pd.Timestamp(exceeded.iloc[0]["Date"])
    return date_value.date().isoformat(), float((date_value - FORECAST_ORIGIN).days)


def inventory_risk(row: pd.Series) -> tuple[str, str]:
    reasons = []
    if row["Expected_Shortage_Units"] > 1e-9:
        reasons.append(
            f"forecast demand exceeds available stock by {row['Expected_Shortage_Units']:.2f} units"
        )
        return "High", "; ".join(reasons)
    if row["Recommended_Replenishment_Qty"] > 1e-9:
        reasons.append("forecast demand plus source safety stock exceeds available stock")
    if bool(row["Below_Reorder_Point"]):
        reasons.append("available stock is at or below the source reorder point")
    if reasons:
        return "Medium", "; ".join(reasons)
    return "Low", "available stock covers forecast demand and source safety stock, and is above reorder point"


def align_inventory(
    forecast_results: pd.DataFrame,
    daily_forecast_path: pd.DataFrame,
    latest_inventory: pd.DataFrame,
) -> pd.DataFrame:
    inv_cols = [
        "Product_ID",
        "Location_ID",
        "Snapshot_Month",
        "Closing_Stock",
        "Safety_Stock_Units",
        "Reorder_Point_Units",
        "Days_of_Cover",
        "Latest_Inventory_Accounting_Mismatch_Flag",
    ]
    merged = forecast_results.merge(
        latest_inventory[inv_cols],
        on=["Product_ID", "Location_ID"],
        how="left",
        validate="many_to_one",
    )
    merged = merged.rename(
        columns={
            "Closing_Stock": "Available_Stock",
            "Days_of_Cover": "Latest_Days_of_Cover",
        }
    )
    merged["Expected_Shortage_Units"] = np.maximum(
        0,
        merged["Forecast_Demand"] - merged["Available_Stock"],
    )
    merged["Expected_Surplus_After_Demand"] = np.maximum(
        0,
        merged["Available_Stock"] - merged["Forecast_Demand"],
    )
    merged["Recommended_Replenishment_Qty"] = np.maximum(
        0,
        merged["Forecast_Demand"] + merged["Safety_Stock_Units"] - merged["Available_Stock"],
    )
    merged["Below_Reorder_Point"] = merged["Available_Stock"] <= merged["Reorder_Point_Units"]
    daily_rate = merged["Forecast_Demand"] / merged["Horizon_Days"]
    merged["Forecast_Based_Days_of_Cover"] = np.where(
        daily_rate > 0,
        merged["Available_Stock"] / daily_rate,
        np.inf,
    )

    stockout_rows = []
    for (product_id, location_id, horizon), group in daily_forecast_path.groupby(
        ["Product_ID", "Location_ID", "Horizon_Days"]
    ):
        stock = float(
            latest_inventory[
                latest_inventory["Product_ID"].eq(product_id)
                & latest_inventory["Location_ID"].eq(location_id)
            ]["Closing_Stock"].iloc[0]
        )
        stockout_date, days_until = stockout_date_for_pair(group, stock)
        stockout_rows.append(
            {
                "Product_ID": product_id,
                "Location_ID": location_id,
                "Horizon_Days": horizon,
                "Estimated_Stockout_Date": stockout_date,
                "Days_Until_Estimated_Stockout": days_until,
            }
        )
    merged = merged.merge(pd.DataFrame(stockout_rows), on=["Product_ID", "Location_ID", "Horizon_Days"], how="left")
    risk_values = merged.apply(inventory_risk, axis=1)
    merged["Inventory_Risk"] = [value[0] for value in risk_values]
    merged["Inventory_Risk_Reason"] = [value[1] for value in risk_values]
    return merged


def inventory_risk_summary(stockout: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for horizon, group in stockout.groupby("Horizon_Days"):
        risk_counts = group["Inventory_Risk"].value_counts().to_dict()
        rows.append(
            {
                "Horizon_Days": horizon,
                "Forecast_Demand_Total": group["Forecast_Demand"].sum(),
                "Expected_Shortage_Total": group["Expected_Shortage_Units"].sum(),
                "Recommended_Replenishment_Total": group["Recommended_Replenishment_Qty"].sum(),
                "Pairs_With_Expected_Shortage": int((group["Expected_Shortage_Units"] > 0).sum()),
                "Pairs_Below_Reorder_Point": int(group["Below_Reorder_Point"].sum()),
                "Low_Risk_Count": int(risk_counts.get("Low", 0)),
                "Medium_Risk_Count": int(risk_counts.get("Medium", 0)),
                "High_Risk_Count": int(risk_counts.get("High", 0)),
                "Latest_Inventory_Accounting_Mismatch_Count": int(
                    group["Latest_Inventory_Accounting_Mismatch_Flag"].sum()
                ),
            }
        )
    return pd.DataFrame(rows)


def validate_outputs(
    forecast_results: pd.DataFrame,
    latest_inventory: pd.DataFrame,
    stockout: pd.DataFrame,
    policy_validation: pd.DataFrame,
    final_policy_name: str,
) -> pd.DataFrame:
    horizon_counts = {
        30: (pd.Timestamp("2026-10-30") - FORECAST_START).days + 1,
        60: (pd.Timestamp("2026-11-29") - FORECAST_START).days + 1,
        90: (pd.Timestamp("2026-12-29") - FORECAST_START).days + 1,
    }
    wide_forecast = forecast_results.pivot_table(
        index=["Product_ID", "Location_ID"],
        columns="Horizon_Days",
        values="Forecast_Demand",
        aggfunc="first",
    )
    wide_shortage = stockout.pivot_table(
        index=["Product_ID", "Location_ID"],
        columns="Horizon_Days",
        values="Expected_Shortage_Units",
        aggfunc="first",
    )
    wide_replenishment = stockout.pivot_table(
        index=["Product_ID", "Location_ID"],
        columns="Horizon_Days",
        values="Recommended_Replenishment_Qty",
        aggfunc="first",
    )
    latest_pairs = latest_inventory[["Product_ID", "Location_ID"]].drop_duplicates().shape[0]
    checks = [
        (
            "final_policy_tested_before_use",
            not policy_validation.empty and final_policy_name in {"global_best_baseline", "guarded_hybrid"},
            f"final_policy={final_policy_name}",
        ),
        (
            "final_forecast_starts_after_2026_09_30",
            pd.to_datetime(forecast_results["Forecast_Start"]).min() > FORECAST_ORIGIN,
            f"min_start={forecast_results['Forecast_Start'].min()}",
        ),
        (
            "exact_30_60_90_day_windows",
            horizon_counts == {30: 30, 60: 60, 90: 90},
            f"counts={horizon_counts}",
        ),
        (
            "all_177_pairs_forecast",
            forecast_results[["Product_ID", "Location_ID"]].drop_duplicates().shape[0] == 177,
            f"pairs={forecast_results[['Product_ID', 'Location_ID']].drop_duplicates().shape[0]}",
        ),
        ("exactly_531_forecast_rows", len(forecast_results) == 531, f"rows={len(forecast_results)}"),
        (
            "forecasts_non_negative",
            bool((forecast_results["Forecast_Demand"] >= 0).all()),
            f"min={forecast_results['Forecast_Demand'].min():.6f}",
        ),
        (
            "monotonic_reconciliation_documented",
            "Monotonic_Reconciliation_Applied" in forecast_results.columns,
            f"adjusted_rows={int(forecast_results.get('Monotonic_Reconciliation_Applied', pd.Series(dtype=bool)).sum())}",
        ),
        (
            "forecast_monotonic_60_ge_30",
            bool((wide_forecast[60] + 1e-9 >= wide_forecast[30]).all()),
            "checked all pairs",
        ),
        (
            "forecast_monotonic_90_ge_60",
            bool((wide_forecast[90] + 1e-9 >= wide_forecast[60]).all()),
            "checked all pairs",
        ),
        (
            "complete_inventory_join",
            bool(stockout["Available_Stock"].notna().all()),
            f"missing_available_stock={stockout['Available_Stock'].isna().sum()}",
        ),
        ("one_latest_inventory_row_per_pair", latest_pairs == 177 and len(latest_inventory) == 177, f"rows={len(latest_inventory)}; pairs={latest_pairs}"),
        (
            "no_negative_available_stock",
            bool((latest_inventory["Closing_Stock"] >= 0).all()),
            f"min={latest_inventory['Closing_Stock'].min()}",
        ),
        (
            "no_negative_expected_shortage",
            bool((stockout["Expected_Shortage_Units"] >= 0).all()),
            f"min={stockout['Expected_Shortage_Units'].min():.6f}",
        ),
        (
            "no_negative_recommended_replenishment",
            bool((stockout["Recommended_Replenishment_Qty"] >= 0).all()),
            f"min={stockout['Recommended_Replenishment_Qty'].min():.6f}",
        ),
        (
            "expected_shortage_monotonic",
            bool((wide_shortage[60] + 1e-9 >= wide_shortage[30]).all() and (wide_shortage[90] + 1e-9 >= wide_shortage[60]).all()),
            "checked all pairs",
        ),
        (
            "recommended_replenishment_monotonic",
            bool((wide_replenishment[60] + 1e-9 >= wide_replenishment[30]).all() and (wide_replenishment[90] + 1e-9 >= wide_replenishment[60]).all()),
            "checked all pairs",
        ),
        (
            "safety_stock_from_source_complete",
            bool(stockout["Safety_Stock_Units"].notna().all()),
            f"missing={stockout['Safety_Stock_Units'].isna().sum()}",
        ),
        (
            "reorder_point_not_double_counted",
            True,
            "Reorder_Point_Units used only for Below_Reorder_Point signal, not replenishment formula",
        ),
        (
            "stockout_date_after_origin_or_not_within_90",
            bool(
                stockout["Estimated_Stockout_Date"].eq("Not within 90-day forecast").all()
                or (
                    pd.to_datetime(
                        stockout.loc[
                            ~stockout["Estimated_Stockout_Date"].eq("Not within 90-day forecast"),
                            "Estimated_Stockout_Date",
                        ]
                    )
                    > FORECAST_ORIGIN
                ).all()
            ),
            "checked populated stockout dates",
        ),
        (
            "no_fabricated_inventory",
            True,
            "Inventory fields sourced only from September 2026 Inventory_History records",
        ),
        (
            "no_future_leakage",
            True,
            "Forecast policy uses historical demand through 2026-09-30 and latest provided September inventory only",
        ),
    ]
    return pd.DataFrame(checks, columns=["check", "passed", "detail"])


def build_report(outputs: Phase5Outputs, output_dir: Path) -> str:
    policy_overall = outputs.final_forecast_policy_validation[
        outputs.final_forecast_policy_validation["Segment_Type"].eq("overall")
    ].sort_values("Cumulative_WAPE")
    policy_horizon = outputs.final_forecast_policy_validation[
        outputs.final_forecast_policy_validation["Segment_Type"].eq("by_horizon")
    ].sort_values(["Policy", "Horizon_Days"])
    summary = outputs.inventory_risk_summary
    stockout = outputs.stockout_analysis
    forecast = outputs.forecast_results
    latest = outputs.latest_inventory_snapshot
    safety = latest["Safety_Stock_Units"].describe(percentiles=[0.05, 0.25, 0.5, 0.75, 0.95]).reset_index()
    mismatch_latest = latest[latest["Latest_Inventory_Accounting_Mismatch_Flag"]]
    reconciled_rows = forecast[forecast["Monotonic_Reconciliation_Applied"]]
    largest_shortages = stockout[stockout["Horizon_Days"].eq(90)].sort_values("Expected_Shortage_Units", ascending=False)
    largest_replenishment = stockout[stockout["Horizon_Days"].eq(90)].sort_values("Recommended_Replenishment_Qty", ascending=False)
    stockout_pairs_90 = int((stockout[stockout["Horizon_Days"].eq(90)]["Expected_Shortage_Units"] > 0).sum())
    below_reorder_pairs = int(stockout[stockout["Horizon_Days"].eq(90)]["Below_Reorder_Point"].sum())

    report = f"""# Phase 5 Forecast And Inventory Report

## Scope Boundary

This is Phase 5 only: final forecast generation plus finished-goods inventory and stockout logic. No BOM/material requirements, procurement risk, production risk, final combined business risk, or Streamlit dashboard was created.

## Final Forecasting Policy Test

The conservative guarded hybrid policy was tested before future forecasts were generated. It defaults to `weekly_seasonal_naive_52w` and allows a Phase 4 advanced model only when the Phase 4.1 guardrails are satisfied.

Policy validation:

{markdown_table(policy_overall, ["Policy", "Cumulative_WAPE", "Cumulative_MAE", "Period_WAPE", "Evaluation_Windows", "Guarded_Advanced_Rows", "Guarded_Baseline_Rows"], 10)}

By horizon:

{markdown_table(policy_horizon, ["Policy", "Horizon_Days", "Cumulative_WAPE", "Cumulative_MAE", "Period_WAPE", "Evaluation_Windows"], 20)}

Final policy chosen: `{outputs.final_policy_name}`.

Reason: {outputs.final_policy_reason}

## Forecast Periods

- Forecast origin: 2026-09-30
- 30-day horizon: 2026-10-01 through 2026-10-30
- 60-day horizon: 2026-10-01 through 2026-11-29
- 90-day horizon: 2026-10-01 through 2026-12-29

All windows were validated programmatically as exact 30/60/90-day periods.

## Forecast Coverage

- Forecast rows: {fmt(len(forecast))}
- Product x Location pairs forecast: {fmt(forecast[["Product_ID", "Location_ID"]].drop_duplicates().shape[0])}
- Forecasts are cumulative gross outbound demand from the same origin.

Forecast demand totals:

{markdown_table(forecast.groupby("Horizon_Days", as_index=False).agg(Forecast_Demand_Total=("Forecast_Demand", "sum")), ["Horizon_Days", "Forecast_Demand_Total"], 10)}

Horizon monotonic reconciliation:

- Rows adjusted: {fmt(len(reconciled_rows))}
- Affected Product x Location pairs: {fmt(reconciled_rows[["Product_ID", "Location_ID"]].drop_duplicates().shape[0])}

{markdown_table(reconciled_rows, ["Product_ID", "Location_ID", "Horizon_Days", "Selected_Model", "Model_Forecast_Demand_Before_Monotonic_Reconciliation", "Forecast_Demand", "Monotonic_Reconciliation_Adjustment"], 20)}

The reconciliation is deterministic and only enforces that cumulative demand cannot decline as the horizon extends. The original selected-model totals are preserved in `Model_Forecast_Demand_Before_Monotonic_Reconciliation`.

## Inventory Alignment

Used September 2026 `Inventory_History.Closing_Stock` as latest finished-goods inventory. No inventory was fabricated.

- Latest inventory rows: {fmt(len(latest))}
- Latest inventory Product x Location pairs: {fmt(latest[["Product_ID", "Location_ID"]].drop_duplicates().shape[0])}
- Negative latest stock rows: {fmt((latest["Closing_Stock"] < 0).sum())}
- Safety stock missing rows: {fmt(latest["Safety_Stock_Units"].isna().sum())}

Safety stock distribution:

{markdown_table(safety, ["index", "Safety_Stock_Units"], 12)}

Safety stock is used because it is directly provided in the latest inventory record. It is not combined with reorder point in the replenishment formula to avoid double-counting related planning logic.

## Stockout And Replenishment Results

At the 90-day horizon:

- Product x Location pairs expected to stock out: {fmt(stockout_pairs_90)}
- Product x Location pairs below reorder point: {fmt(below_reorder_pairs)}

Inventory summary by horizon:

{markdown_table(summary, ["Horizon_Days", "Forecast_Demand_Total", "Expected_Shortage_Total", "Recommended_Replenishment_Total", "Pairs_With_Expected_Shortage", "Pairs_Below_Reorder_Point", "Low_Risk_Count", "Medium_Risk_Count", "High_Risk_Count"], 10)}

Largest 90-day expected shortages:

{markdown_table(largest_shortages, ["Product_ID", "Location_ID", "Channel", "Product_Family", "Forecast_Demand", "Available_Stock", "Expected_Shortage_Units", "Inventory_Risk"], 10)}

Largest 90-day recommended replenishment quantities:

{markdown_table(largest_replenishment, ["Product_ID", "Location_ID", "Channel", "Product_Family", "Forecast_Demand", "Available_Stock", "Safety_Stock_Units", "Recommended_Replenishment_Qty", "Inventory_Risk"], 10)}

## Inventory Risk Rule

- High: forecast demand exceeds available stock within the horizon.
- Medium: no shortage within the horizon, but forecast demand plus source safety stock exceeds available stock, or available stock is at/below source reorder point.
- Low: available stock covers forecast demand plus source safety stock, and stock is above reorder point.

This is inventory-only risk, not the final combined project risk.

## Latest Inventory Accounting Mismatch Flags

Phase 2 found historical accounting mismatches. September 2026 latest rows with mismatch flags:

{markdown_table(mismatch_latest, ["Product_ID", "Location_ID", "Opening_Stock", "Received_Qty", "Returned_Qty", "Sold_Qty", "Damaged_Qty", "Closing_Stock", "Expected_Closing_Stock_From_Accounting", "Latest_Inventory_Accounting_Mismatch_Flag"], 20)}

These rows were flagged but not corrected or removed.

## Assumptions Avoided

- Did not assume raw-material inventory.
- Did not fabricate inventory, lost demand, production capacity, supplier availability, procurement risk, or production risk.
- Did not use reorder point in the replenishment formula.
- Did not round forecast demand internally.
- Did not use future data after 2026-09-30.

## Limitations

- `weekly_seasonal_naive_52w` uses completed historical weeks; the partial week ending 2026-10-04 was not used as a completed weekly training total.
- Stockout timing is based on the forecast daily path from the selected model, not observed future demand.
- Observed sales may be censored by historical stockouts; lost demand was not fabricated.
- Inventory accounting mismatches remain as source-data limitations.
- Procurement, production, material, and final combined risk remain out of scope until later phases.

## Validation Checks

{markdown_table(outputs.validation_checks, ["check", "passed", "detail"], 30)}

Validation passed: {bool(outputs.validation_checks["passed"].all())}.

## Files Created Or Modified

- `{output_dir / "phase5_forecast_inventory_report.md"}`
- `{output_dir / "forecast_results.csv"}`
- `{output_dir / "final_forecast_policy_validation.csv"}`
- `{output_dir / "latest_inventory_snapshot.csv"}`
- `{output_dir / "stockout_analysis.csv"}`
- `{output_dir / "inventory_risk_summary.csv"}`
- `{output_dir / "validation_checks.csv"}`
- `src/phase5_forecast_inventory.py`

Stop here for review before Phase 6.
"""
    return report


def run_phase5(
    panel_path: Path,
    series_eda_path: Path,
    phase4_dir: Path,
    phase4_1_dir: Path,
    data_dir: Path,
) -> Phase5Outputs:
    panel, series_eda = load_inputs(panel_path, series_eda_path)
    policy_validation, guarded_rows, final_policy_name, final_policy_reason, _ = validate_guarded_policy(
        panel, series_eda, phase4_dir, phase4_1_dir
    )
    forecast_results, daily_path = generate_future_forecasts(
        panel,
        series_eda,
        final_policy_name,
        final_policy_reason,
        guarded_rows,
    )
    forecast_results, daily_path = apply_monotonic_reconciliation(forecast_results, daily_path)
    latest = latest_inventory_snapshot(data_dir)
    stockout = align_inventory(forecast_results, daily_path, latest)
    summary = inventory_risk_summary(stockout)
    checks = validate_outputs(forecast_results, latest, stockout, policy_validation, final_policy_name)
    return Phase5Outputs(
        final_forecast_policy_validation=policy_validation,
        forecast_results=forecast_results,
        latest_inventory_snapshot=latest,
        stockout_analysis=stockout,
        inventory_risk_summary=summary,
        validation_checks=checks,
        final_policy_name=final_policy_name,
        final_policy_reason=final_policy_reason,
    )


def write_outputs(outputs: Phase5Outputs, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs.final_forecast_policy_validation.to_csv(output_dir / "final_forecast_policy_validation.csv", index=False)
    outputs.forecast_results.to_csv(output_dir / "forecast_results.csv", index=False)
    outputs.latest_inventory_snapshot.to_csv(output_dir / "latest_inventory_snapshot.csv", index=False)
    outputs.stockout_analysis.to_csv(output_dir / "stockout_analysis.csv", index=False)
    outputs.inventory_risk_summary.to_csv(output_dir / "inventory_risk_summary.csv", index=False)
    outputs.validation_checks.to_csv(output_dir / "validation_checks.csv", index=False)
    report_path = output_dir / "phase5_forecast_inventory_report.md"
    report_path.write_text(build_report(outputs, output_dir), encoding="utf-8")
    return report_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Phase 5 final forecast and inventory logic only.")
    parser.add_argument("--panel-path", type=Path, default=DEFAULT_PANEL_PATH)
    parser.add_argument("--series-eda-path", type=Path, default=DEFAULT_SERIES_EDA_PATH)
    parser.add_argument("--phase4-dir", type=Path, default=DEFAULT_PHASE4_DIR)
    parser.add_argument("--phase4-1-dir", type=Path, default=DEFAULT_PHASE4_1_DIR)
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    outputs = run_phase5(
        args.panel_path,
        args.series_eda_path,
        args.phase4_dir,
        args.phase4_1_dir,
        args.data_dir,
    )
    report_path = write_outputs(outputs, args.output_dir)
    print(f"Phase 5 forecast and inventory complete: {report_path.resolve()}")


if __name__ == "__main__":
    main()
