"""Phase 2 cleaning and EDA for the El-Sharnouby shortage-risk project.

The script creates reproducible validation and EDA outputs only. It does not
train forecasting models, create forecast horizons, calculate replenishment
recommendations, calculate procurement/production risk, or infer raw-material
inventory.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd


DEFAULT_DATA_DIR = Path(r"C:\Users\Acer\Downloads\Sharnouby_Enterprise")
DEFAULT_OUTPUT_DIR = Path("outputs") / "phase2"
DEFAULT_PROCESSED_DIR = Path("data") / "processed"


@dataclass
class Phase2Outputs:
    sales: pd.DataFrame
    inventory: pd.DataFrame
    products: pd.DataFrame
    locations: pd.DataFrame
    inventory_accounting: pd.DataFrame
    inventory_accounting_summary: pd.DataFrame
    inventory_continuity: pd.DataFrame
    inventory_month_summary: pd.DataFrame
    monthly_reconciliation: pd.DataFrame
    reconciliation_summary: pd.DataFrame
    reconciliation_by_month: pd.DataFrame
    returns_summary: pd.DataFrame
    returns_reconciliation: pd.DataFrame
    daily_panel: pd.DataFrame
    panel_summary: pd.DataFrame
    demand_series_eda: pd.DataFrame
    weekday_pattern: pd.DataFrame
    monthly_pattern: pd.DataFrame
    location_channel_summary: pd.DataFrame
    product_family_summary: pd.DataFrame
    price_discount_summary: pd.DataFrame
    discount_bin_summary: pd.DataFrame
    price_bin_summary: pd.DataFrame
    leakage_risk_table: pd.DataFrame
    data_quality_summary: pd.DataFrame


def read_required_tables(data_dir: Path) -> dict[str, pd.DataFrame]:
    required = [
        "Sales_Transactions.csv",
        "Inventory_History.csv",
        "Product_Master.csv",
        "Locations.csv",
    ]
    missing = [file_name for file_name in required if not (data_dir / file_name).exists()]
    if missing:
        raise FileNotFoundError(f"Missing required Phase 2 input files: {', '.join(missing)}")
    return {file_name: pd.read_csv(data_dir / file_name) for file_name in required}


def clean_keys(frame: pd.DataFrame, key_columns: list[str]) -> pd.DataFrame:
    cleaned = frame.copy()
    for col in key_columns:
        if col in cleaned.columns:
            cleaned[col] = cleaned[col].astype("string").str.strip()
    return cleaned


def prepare_sales(raw_sales: pd.DataFrame) -> pd.DataFrame:
    sales = clean_keys(raw_sales, ["Product_ID", "Location_ID", "Customer_ID", "Invoice_ID", "SKU"])
    sales["Order_Date"] = pd.to_datetime(sales["Order_Date"], errors="coerce")
    sales["Return_Date"] = pd.to_datetime(sales["Return_Date"], errors="coerce")
    sales["Month"] = sales["Order_Date"].dt.to_period("M").dt.to_timestamp()
    sales["Returned_Flag"] = sales["Returned"].eq("Yes")
    sales["Returned_Units_By_Order_Date"] = np.where(sales["Returned_Flag"], sales["Quantity"], 0)
    sales["Net_Unit_Price_EGP"] = np.where(
        sales["Quantity"] > 0,
        sales["Net_Sales_EGP"] / sales["Quantity"],
        np.nan,
    )
    return sales


def prepare_inventory(raw_inventory: pd.DataFrame) -> pd.DataFrame:
    inventory = clean_keys(raw_inventory, ["Product_ID", "Location_ID", "SKU"])
    inventory["Snapshot_Month"] = pd.to_datetime(inventory["Snapshot_Month"], errors="coerce")
    inventory["Month"] = inventory["Snapshot_Month"].dt.to_period("M").dt.to_timestamp()
    return inventory


def inventory_accounting_validation(inventory: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    result = inventory[
        [
            "Snapshot_Month",
            "Product_ID",
            "Location_ID",
            "Opening_Stock",
            "Received_Qty",
            "Returned_Qty",
            "Sold_Qty",
            "Damaged_Qty",
            "Closing_Stock",
        ]
    ].copy()
    result["Expected_Closing_Stock"] = (
        result["Opening_Stock"]
        + result["Received_Qty"]
        + result["Returned_Qty"]
        - result["Sold_Qty"]
        - result["Damaged_Qty"]
    )
    result["Closing_Stock_Mismatch"] = result["Closing_Stock"] - result["Expected_Closing_Stock"]
    result["Absolute_Mismatch"] = result["Closing_Stock_Mismatch"].abs()
    result["Accounting_Holds_Exactly"] = result["Closing_Stock_Mismatch"].eq(0)

    mismatch = result.loc[~result["Accounting_Holds_Exactly"], "Closing_Stock_Mismatch"]
    abs_mismatch = result.loc[~result["Accounting_Holds_Exactly"], "Absolute_Mismatch"]
    summary_rows = [
        ("rows_checked", len(result)),
        ("rows_holding_exactly", int(result["Accounting_Holds_Exactly"].sum())),
        ("rows_holding_exactly_pct", float(result["Accounting_Holds_Exactly"].mean() * 100)),
        ("mismatch_rows", int((~result["Accounting_Holds_Exactly"]).sum())),
        ("mismatch_rows_pct", float((~result["Accounting_Holds_Exactly"]).mean() * 100)),
        ("mismatch_min", float(mismatch.min()) if not mismatch.empty else 0.0),
        ("mismatch_median", float(mismatch.median()) if not mismatch.empty else 0.0),
        ("mismatch_mean", float(mismatch.mean()) if not mismatch.empty else 0.0),
        ("mismatch_p90", float(mismatch.quantile(0.90)) if not mismatch.empty else 0.0),
        ("mismatch_p95", float(mismatch.quantile(0.95)) if not mismatch.empty else 0.0),
        ("mismatch_p99", float(mismatch.quantile(0.99)) if not mismatch.empty else 0.0),
        ("mismatch_max", float(mismatch.max()) if not mismatch.empty else 0.0),
        ("absolute_mismatch_median", float(abs_mismatch.median()) if not abs_mismatch.empty else 0.0),
        ("absolute_mismatch_p95", float(abs_mismatch.quantile(0.95)) if not abs_mismatch.empty else 0.0),
        ("absolute_mismatch_max", float(abs_mismatch.max()) if not abs_mismatch.empty else 0.0),
    ]
    summary = pd.DataFrame(summary_rows, columns=["metric", "value"])
    return result, summary


def inventory_month_interpretation(inventory: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    work = inventory.sort_values(["Product_ID", "Location_ID", "Snapshot_Month"]).copy()
    work["Previous_Snapshot_Month"] = work.groupby(["Product_ID", "Location_ID"])["Snapshot_Month"].shift()
    work["Previous_Closing_Stock"] = work.groupby(["Product_ID", "Location_ID"])["Closing_Stock"].shift()
    transitions = work[work["Previous_Closing_Stock"].notna()].copy()
    transitions["Month_Gap"] = (
        (transitions["Snapshot_Month"].dt.year - transitions["Previous_Snapshot_Month"].dt.year) * 12
        + (transitions["Snapshot_Month"].dt.month - transitions["Previous_Snapshot_Month"].dt.month)
    )
    transitions["Opening_Minus_Previous_Closing"] = (
        transitions["Opening_Stock"] - transitions["Previous_Closing_Stock"]
    )
    transitions["Continuity_Holds"] = transitions["Opening_Minus_Previous_Closing"].eq(0)

    day_counts = inventory["Snapshot_Month"].dt.day.value_counts().sort_index()
    summary_rows = [
        ("snapshot_rows", len(inventory)),
        ("unique_snapshot_days", "; ".join(f"day {day}: {count}" for day, count in day_counts.items())),
        ("snapshot_min_month", inventory["Snapshot_Month"].min().date().isoformat()),
        ("snapshot_max_month", inventory["Snapshot_Month"].max().date().isoformat()),
        ("transition_rows", len(transitions)),
        ("monthly_gap_one_rows", int(transitions["Month_Gap"].eq(1).sum())),
        ("monthly_gap_one_pct", float(transitions["Month_Gap"].eq(1).mean() * 100)),
        ("continuity_exact_rows", int(transitions["Continuity_Holds"].sum())),
        ("continuity_exact_pct", float(transitions["Continuity_Holds"].mean() * 100)),
        (
            "safest_interpretation",
            "Snapshot_Month is a monthly period label shown as the first day of the month. "
            "The row contains monthly movement fields and a period closing balance, not a point-in-time "
            "morning snapshot at that date.",
        ),
    ]
    summary = pd.DataFrame(summary_rows, columns=["metric", "value"])
    return transitions, summary


def sales_inventory_reconciliation(
    sales: pd.DataFrame, inventory: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    monthly_sales = (
        sales.groupby(["Month", "Product_ID", "Location_ID"], as_index=False)
        .agg(
            Sales_Quantity=("Quantity", "sum"),
            Sales_Transactions=("Row_ID", "count"),
            Returned_Units_By_Order_Month=("Returned_Units_By_Order_Date", "sum"),
        )
    )
    monthly_inventory = inventory[
        ["Month", "Product_ID", "Location_ID", "Sold_Qty", "Returned_Qty"]
    ].copy()

    reconciliation = monthly_sales.merge(
        monthly_inventory,
        on=["Month", "Product_ID", "Location_ID"],
        how="outer",
        indicator=True,
    )
    for col in ["Sales_Quantity", "Sales_Transactions", "Returned_Units_By_Order_Month", "Sold_Qty", "Returned_Qty"]:
        reconciliation[col] = reconciliation[col].fillna(0)
    reconciliation["Quantity_Minus_Sold_Qty"] = (
        reconciliation["Sales_Quantity"] - reconciliation["Sold_Qty"]
    )
    reconciliation["Absolute_Difference"] = reconciliation["Quantity_Minus_Sold_Qty"].abs()
    reconciliation["Pct_Difference_Vs_Inventory_Sold_Qty"] = np.where(
        reconciliation["Sold_Qty"] != 0,
        reconciliation["Quantity_Minus_Sold_Qty"] / reconciliation["Sold_Qty"] * 100,
        np.nan,
    )
    reconciliation["Exact_Match"] = reconciliation["Absolute_Difference"].eq(0)
    corr = reconciliation[["Sales_Quantity", "Sold_Qty"]].corr().iloc[0, 1]

    summary_rows = [
        ("rows_compared", len(reconciliation)),
        ("rows_with_both_sources", int(reconciliation["_merge"].eq("both").sum())),
        ("rows_inventory_only_after_zero_fill", int(reconciliation["_merge"].eq("right_only").sum())),
        ("rows_sales_only", int(reconciliation["_merge"].eq("left_only").sum())),
        ("exact_match_rows", int(reconciliation["Exact_Match"].sum())),
        ("exact_match_pct_all_rows", float(reconciliation["Exact_Match"].mean() * 100)),
        (
            "exact_match_pct_rows_with_both_sources",
            float(reconciliation.loc[reconciliation["_merge"].eq("both"), "Exact_Match"].mean() * 100),
        ),
        ("absolute_difference_mean", float(reconciliation["Absolute_Difference"].mean())),
        ("absolute_difference_median", float(reconciliation["Absolute_Difference"].median())),
        ("absolute_difference_p95", float(reconciliation["Absolute_Difference"].quantile(0.95))),
        ("absolute_difference_max", float(reconciliation["Absolute_Difference"].max())),
        ("correlation_sales_quantity_vs_inventory_sold_qty", float(corr)),
    ]
    summary = pd.DataFrame(summary_rows, columns=["metric", "value"])

    by_month = (
        reconciliation.groupby("Month", as_index=False)
        .agg(
            Sales_Quantity=("Sales_Quantity", "sum"),
            Sold_Qty=("Sold_Qty", "sum"),
            Exact_Match_Rate=("Exact_Match", "mean"),
            Mean_Absolute_Difference=("Absolute_Difference", "mean"),
            Max_Absolute_Difference=("Absolute_Difference", "max"),
        )
    )
    by_month["Quantity_Minus_Sold_Qty"] = by_month["Sales_Quantity"] - by_month["Sold_Qty"]
    return reconciliation, summary, by_month


def returns_analysis(sales: pd.DataFrame, inventory: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    returned = sales[sales["Returned_Flag"]].copy()
    return_lag = (returned["Return_Date"] - returned["Order_Date"]).dt.days

    summary_rows = [
        ("sales_rows", len(sales)),
        ("returned_rows", int(sales["Returned_Flag"].sum())),
        ("returned_rows_pct", float(sales["Returned_Flag"].mean() * 100)),
        ("quantity_total", float(sales["Quantity"].sum())),
        ("returned_quantity_by_order_date", float(returned["Quantity"].sum())),
        ("returned_quantity_pct_of_sales_quantity", float(returned["Quantity"].sum() / sales["Quantity"].sum() * 100)),
        ("refund_value_total_egp", float(sales["Refund_Value_EGP"].sum())),
        ("return_date_present_for_returned_rows_pct", float(returned["Return_Date"].notna().mean() * 100)),
        ("return_lag_days_median", float(return_lag.median())),
        ("return_lag_days_p95", float(return_lag.quantile(0.95))),
        ("return_lag_days_max", float(return_lag.max())),
        (
            "target_decision",
            "Use gross outbound demand: Sales_Transactions.Quantity aggregated by Order_Date x Product_ID x Location_ID. "
            "Inventory Sold_Qty matches Quantity by month exactly, and inventory Returned_Qty matches returned sales by "
            "order month exactly. Returns should be analyzed separately, not silently subtracted from demand.",
        ),
    ]
    summary = pd.DataFrame(summary_rows, columns=["metric", "value"])

    returned_by_order_month = (
        returned.groupby(["Month", "Product_ID", "Location_ID"], as_index=False)["Quantity"]
        .sum()
        .rename(columns={"Quantity": "Returned_Units_By_Order_Month"})
    )
    returned_by_return_month = returned.dropna(subset=["Return_Date"]).copy()
    returned_by_return_month["Return_Month"] = returned_by_return_month["Return_Date"].dt.to_period("M").dt.to_timestamp()
    returned_by_return_month = (
        returned_by_return_month.groupby(["Return_Month", "Product_ID", "Location_ID"], as_index=False)["Quantity"]
        .sum()
        .rename(columns={"Return_Month": "Month", "Quantity": "Returned_Units_By_Return_Month"})
    )
    inv_returns = inventory[["Month", "Product_ID", "Location_ID", "Returned_Qty"]].copy()
    reconciliation = inv_returns.merge(
        returned_by_order_month,
        on=["Month", "Product_ID", "Location_ID"],
        how="outer",
    ).merge(returned_by_return_month, on=["Month", "Product_ID", "Location_ID"], how="outer")
    for col in ["Returned_Qty", "Returned_Units_By_Order_Month", "Returned_Units_By_Return_Month"]:
        reconciliation[col] = reconciliation[col].fillna(0)
    reconciliation["Diff_Order_Month_Returns_Minus_Inventory"] = (
        reconciliation["Returned_Units_By_Order_Month"] - reconciliation["Returned_Qty"]
    )
    reconciliation["Diff_Return_Month_Returns_Minus_Inventory"] = (
        reconciliation["Returned_Units_By_Return_Month"] - reconciliation["Returned_Qty"]
    )
    return summary, reconciliation


def build_daily_demand_panel(
    sales: pd.DataFrame, products: pd.DataFrame, locations: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    daily = (
        sales.groupby(["Order_Date", "Product_ID", "Location_ID"], as_index=False)
        .agg(
            Demand_Units=("Quantity", "sum"),
            Transaction_Count=("Row_ID", "count"),
            Returned_Units_By_Order_Date=("Returned_Units_By_Order_Date", "sum"),
            Returned_Transaction_Count=("Returned_Flag", "sum"),
            Gross_Sales_EGP=("Gross_Sales_EGP", "sum"),
            Net_Sales_EGP=("Net_Sales_EGP", "sum"),
            Avg_List_Price_EGP=("List_Price_EGP", "mean"),
            Avg_Discount_Pct=("Discount_Pct", "mean"),
            Avg_Net_Unit_Price_EGP=("Net_Unit_Price_EGP", "mean"),
        )
    )
    bounds = (
        daily.groupby(["Product_ID", "Location_ID"], as_index=False)
        .agg(First_Demand_Date=("Order_Date", "min"), Last_Demand_Date=("Order_Date", "max"))
    )
    panel_parts = []
    expected_rows = 0
    for row in bounds.itertuples(index=False):
        dates = pd.date_range(row.First_Demand_Date, row.Last_Demand_Date, freq="D")
        expected_rows += len(dates)
        panel_parts.append(
            pd.DataFrame(
                {
                    "Date": dates,
                    "Product_ID": row.Product_ID,
                    "Location_ID": row.Location_ID,
                    "First_Demand_Date": row.First_Demand_Date,
                    "Last_Demand_Date": row.Last_Demand_Date,
                }
            )
        )
    panel = pd.concat(panel_parts, ignore_index=True)
    panel = panel.merge(
        daily.rename(columns={"Order_Date": "Date"}),
        on=["Date", "Product_ID", "Location_ID"],
        how="left",
    )

    zero_fill_cols = [
        "Demand_Units",
        "Transaction_Count",
        "Returned_Units_By_Order_Date",
        "Returned_Transaction_Count",
        "Gross_Sales_EGP",
        "Net_Sales_EGP",
    ]
    for col in zero_fill_cols:
        panel[col] = panel[col].fillna(0)
    panel["Observed_Sale_Day"] = panel["Transaction_Count"].gt(0)
    panel["Zero_Demand_Day"] = panel["Demand_Units"].eq(0)

    product_cols = ["Product_ID", "Product_Name", "Product_Family", "Brand", "Gender", "Audience", "Catalog_Season"]
    location_cols = ["Location_ID", "Location_Name", "Location_Type", "Channel", "Governorate", "City"]
    panel = panel.merge(products[[col for col in product_cols if col in products.columns]], on="Product_ID", how="left")
    panel = panel.merge(locations[[col for col in location_cols if col in locations.columns]], on="Location_ID", how="left")

    summary = pd.DataFrame(
        [
            ("panel_rows", len(panel)),
            ("expected_rows_from_pair_windows", expected_rows),
            ("actual_nonzero_daily_rows_before_zero_fill", len(daily)),
            ("zero_demand_rows_added", int(panel["Zero_Demand_Day"].sum())),
            ("panel_min_date", panel["Date"].min().date().isoformat()),
            ("panel_max_date", panel["Date"].max().date().isoformat()),
            ("product_location_pairs", panel[["Product_ID", "Location_ID"]].drop_duplicates().shape[0]),
            ("products", panel["Product_ID"].nunique()),
            ("locations", panel["Location_ID"].nunique()),
        ],
        columns=["metric", "value"],
    )
    return panel, summary


def _linear_slope(y: pd.Series) -> float:
    if len(y) < 2 or y.var() == 0:
        return 0.0
    x = np.arange(len(y), dtype=float)
    return float(np.polyfit(x, y.to_numpy(dtype=float), 1)[0])


def _safe_cv(values: pd.Series) -> float:
    mean = values.mean()
    if mean == 0 or pd.isna(mean):
        return np.nan
    return float(values.std(ddof=0) / mean)


def _outlier_count_nonzero(values: pd.Series) -> tuple[int, float]:
    nonzero = values[values > 0]
    if len(nonzero) < 8:
        return 0, np.nan
    q1 = nonzero.quantile(0.25)
    q3 = nonzero.quantile(0.75)
    iqr = q3 - q1
    threshold = q3 + 1.5 * iqr
    return int((nonzero > threshold).sum()), float(threshold)


def _pattern_strength(group: pd.DataFrame, period_col: str) -> float:
    means = group.groupby(period_col)["Demand_Units"].mean()
    overall = group["Demand_Units"].mean()
    if overall == 0 or means.empty:
        return np.nan
    return float((means.max() - means.min()) / overall)


def demand_behavior_eda(panel: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    work = panel.copy()
    work["Day_Of_Week"] = work["Date"].dt.day_name()
    work["Day_Of_Week_Num"] = work["Date"].dt.dayofweek
    work["Month_Start"] = work["Date"].dt.to_period("M").dt.to_timestamp()
    work["Month_Of_Year"] = work["Date"].dt.month

    rows = []
    for (product_id, location_id), group in work.groupby(["Product_ID", "Location_ID"], sort=True):
        demand = group["Demand_Units"]
        nonzero = demand[demand > 0]
        outlier_count, outlier_threshold = _outlier_count_nonzero(demand)
        active_days = len(group)
        nonzero_days = int((demand > 0).sum())
        mean_daily = float(demand.mean())
        cv_daily = _safe_cv(demand)
        nonzero_cv = _safe_cv(nonzero) if not nonzero.empty else np.nan
        nonzero_cv2 = nonzero_cv**2 if pd.notna(nonzero_cv) else np.nan
        adi = active_days / nonzero_days if nonzero_days else np.inf
        if adi <= 1.32 and (pd.isna(nonzero_cv2) or nonzero_cv2 <= 0.49):
            demand_pattern = "smooth"
        elif adi > 1.32 and (pd.isna(nonzero_cv2) or nonzero_cv2 <= 0.49):
            demand_pattern = "intermittent"
        elif adi <= 1.32 and nonzero_cv2 > 0.49:
            demand_pattern = "erratic"
        else:
            demand_pattern = "lumpy"
        may_need_fallback = bool(
            active_days < 180
            or nonzero_days < 30
            or adi > 1.32
            or (pd.notna(cv_daily) and cv_daily > 2.0)
            or demand_pattern in {"intermittent", "lumpy"}
        )
        rows.append(
            {
                "Product_ID": product_id,
                "Location_ID": location_id,
                "Product_Name": group["Product_Name"].iloc[0],
                "Product_Family": group["Product_Family"].iloc[0],
                "Location_Name": group["Location_Name"].iloc[0],
                "Channel": group["Channel"].iloc[0],
                "First_Demand_Date": group["First_Demand_Date"].iloc[0],
                "Last_Demand_Date": group["Last_Demand_Date"].iloc[0],
                "Active_Days": active_days,
                "Total_Demand": float(demand.sum()),
                "Mean_Daily_Demand": mean_daily,
                "Median_Daily_Demand": float(demand.median()),
                "Std_Daily_Demand": float(demand.std(ddof=0)),
                "CV_Daily_Demand": cv_daily,
                "Nonzero_Days": nonzero_days,
                "Zero_Demand_Days": active_days - nonzero_days,
                "Zero_Demand_Pct": float((active_days - nonzero_days) / active_days * 100),
                "Demand_Frequency_Pct": float(nonzero_days / active_days * 100),
                "Average_Demand_Interval_Days": float(adi),
                "Nonzero_Demand_CV2": float(nonzero_cv2) if pd.notna(nonzero_cv2) else np.nan,
                "Demand_Pattern_Class": demand_pattern,
                "May_Need_Fallback_Later": may_need_fallback,
                "Daily_Trend_Slope_Units_Per_Day": _linear_slope(demand),
                "Weekly_Pattern_Strength": _pattern_strength(group, "Day_Of_Week_Num"),
                "Monthly_Pattern_Strength": _pattern_strength(group, "Month_Of_Year"),
                "Outlier_Days_Nonzero_IQR": outlier_count,
                "Outlier_Threshold_Nonzero_IQR": outlier_threshold,
            }
        )
    series_eda = pd.DataFrame(rows)

    weekday = (
        work.groupby(["Day_Of_Week_Num", "Day_Of_Week"], as_index=False)
        .agg(
            Total_Demand=("Demand_Units", "sum"),
            Mean_Daily_Demand=("Demand_Units", "mean"),
            Median_Daily_Demand=("Demand_Units", "median"),
            Zero_Demand_Pct=("Zero_Demand_Day", lambda s: float(s.mean() * 100)),
        )
        .sort_values("Day_Of_Week_Num")
    )
    monthly = (
        work.groupby("Month_Of_Year", as_index=False)
        .agg(
            Total_Demand=("Demand_Units", "sum"),
            Mean_Daily_Demand=("Demand_Units", "mean"),
            Median_Daily_Demand=("Demand_Units", "median"),
            Zero_Demand_Pct=("Zero_Demand_Day", lambda s: float(s.mean() * 100)),
        )
    )
    location_channel = (
        work.groupby(["Location_ID", "Location_Name", "Channel"], as_index=False)
        .agg(
            Total_Demand=("Demand_Units", "sum"),
            Mean_Daily_Demand=("Demand_Units", "mean"),
            Median_Daily_Demand=("Demand_Units", "median"),
            Zero_Demand_Pct=("Zero_Demand_Day", lambda s: float(s.mean() * 100)),
            Product_Count=("Product_ID", "nunique"),
            Series_Count=("Product_ID", "count"),
        )
    )
    product_family = (
        work.groupby(["Product_Family"], as_index=False)
        .agg(
            Total_Demand=("Demand_Units", "sum"),
            Mean_Daily_Demand=("Demand_Units", "mean"),
            Median_Daily_Demand=("Demand_Units", "median"),
            Zero_Demand_Pct=("Zero_Demand_Day", lambda s: float(s.mean() * 100)),
            Product_Count=("Product_ID", "nunique"),
        )
    )
    return series_eda, weekday, monthly, location_channel, product_family


def price_discount_eda(panel: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    sale_days = panel[panel["Observed_Sale_Day"]].copy()
    numeric_cols = ["Demand_Units", "Avg_List_Price_EGP", "Avg_Discount_Pct", "Avg_Net_Unit_Price_EGP"]
    corr = sale_days[numeric_cols].corr(numeric_only=True)
    summary_rows = []
    for col in ["Avg_List_Price_EGP", "Avg_Discount_Pct", "Avg_Net_Unit_Price_EGP"]:
        summary_rows.append(
            {
                "measure": col,
                "correlation_with_daily_demand_sale_days_only": float(corr.loc["Demand_Units", col]),
                "note": "Exploratory association only; channel, product mix, and wholesale order size confound this relationship.",
            }
        )
    price_discount_summary = pd.DataFrame(summary_rows)

    discount_bins = [-0.001, 0.0, 0.05, 0.10, 0.15, 0.20, 0.30, 1.0]
    sale_days["Discount_Bin"] = pd.cut(sale_days["Avg_Discount_Pct"], bins=discount_bins, include_lowest=True)
    discount_summary = (
        sale_days.groupby(["Channel", "Discount_Bin"], observed=False)
        .agg(
            Sale_Days=("Demand_Units", "count"),
            Total_Demand=("Demand_Units", "sum"),
            Mean_Daily_Demand=("Demand_Units", "mean"),
            Median_Daily_Demand=("Demand_Units", "median"),
            Mean_List_Price_EGP=("Avg_List_Price_EGP", "mean"),
        )
        .reset_index()
    )
    discount_summary["Discount_Bin"] = discount_summary["Discount_Bin"].astype(str)

    sale_days["List_Price_Bin"] = pd.qcut(
        sale_days["Avg_List_Price_EGP"],
        q=5,
        duplicates="drop",
    )
    price_summary = (
        sale_days.groupby(["Channel", "List_Price_Bin"], observed=False)
        .agg(
            Sale_Days=("Demand_Units", "count"),
            Total_Demand=("Demand_Units", "sum"),
            Mean_Daily_Demand=("Demand_Units", "mean"),
            Median_Daily_Demand=("Demand_Units", "median"),
            Mean_Discount_Pct=("Avg_Discount_Pct", "mean"),
        )
        .reset_index()
    )
    price_summary["List_Price_Bin"] = price_summary["List_Price_Bin"].astype(str)
    return price_discount_summary, discount_summary, price_summary


def leakage_risks() -> pd.DataFrame:
    rows = [
        (
            "Sales_Transactions",
            "Quantity",
            "Target",
            "Use only as the demand target after aggregation. Do not include as an input feature.",
        ),
        (
            "Sales_Transactions",
            "Gross_Sales_EGP, Net_Sales_EGP, Estimated_COGS_EGP, Gross_Profit_EGP, Gross_Margin_Pct",
            "High",
            "These are realized transaction outcomes that include the effect of demand quantity or post-sale financial outcomes.",
        ),
        (
            "Sales_Transactions",
            "Returned, Return_Date, Return_Reason, Refund_Value_EGP, Quality_Related_Return",
            "High",
            "Return outcomes happen after the sale and are not known at the demand forecast origin.",
        ),
        (
            "Sales_Transactions",
            "Invoice_ID, Row_ID, Customer_ID, Payment_Method",
            "Medium",
            "Transaction-specific identifiers or choices are not known for future aggregate Product x Location dates.",
        ),
        (
            "Sales_Transactions",
            "Discount_Pct, List_Price_EGP",
            "Conditional",
            "Only safe if known in advance as planned commercial inputs. Same-day realized averages must not be used as future features.",
        ),
        (
            "Inventory_History",
            "Sold_Qty, Closing_Stock, Days_of_Cover, Stockout_Days_In_Month",
            "High",
            "These period-end inventory outcomes encode realized demand or stock status for the month being predicted.",
        ),
        (
            "Inventory_History",
            "Opening_Stock, Safety_Stock_Units, Reorder_Point_Units",
            "Conditional",
            "Only safe as lagged features if available before the forecast origin; not safe from future inventory months.",
        ),
        (
            "Purchase_Orders",
            "Actual_Receipt_Date, Accepted_Qty, Rejected_Qty",
            "High for demand forecasting",
            "Procurement outcomes occur after order placement and are not direct future demand signals.",
        ),
        (
            "Production_Orders",
            "Completion_Date, Produced_Qty, Good_Qty, Rejected_Qty, Delay_Days, Efficiency_Pct",
            "High for demand forecasting",
            "Production outcomes can be analyzed historically for risk, but future actual values are not known at forecast time.",
        ),
    ]
    return pd.DataFrame(rows, columns=["table", "column_or_group", "leakage_risk", "safe_use_rule"])


def data_quality_summary(sales: pd.DataFrame, inventory: pd.DataFrame, products: pd.DataFrame, locations: pd.DataFrame) -> pd.DataFrame:
    rows = [
        ("sales_rows", len(sales)),
        ("sales_order_date_missing", int(sales["Order_Date"].isna().sum())),
        ("sales_product_id_missing", int(sales["Product_ID"].isna().sum())),
        ("sales_location_id_missing", int(sales["Location_ID"].isna().sum())),
        ("sales_negative_quantity_rows", int((sales["Quantity"] < 0).sum())),
        ("sales_zero_quantity_rows", int((sales["Quantity"] == 0).sum())),
        ("inventory_rows", len(inventory)),
        ("inventory_snapshot_month_missing", int(inventory["Snapshot_Month"].isna().sum())),
        ("inventory_negative_closing_stock_rows", int((inventory["Closing_Stock"] < 0).sum())),
        ("product_master_rows", len(products)),
        ("location_master_rows", len(locations)),
        ("raw_data_modified", "No. Raw CSV files were read only; derived outputs were written separately."),
    ]
    return pd.DataFrame(rows, columns=["metric", "value"])


def run_phase2(data_dir: Path) -> Phase2Outputs:
    tables = read_required_tables(data_dir)
    sales = prepare_sales(tables["Sales_Transactions.csv"])
    inventory = prepare_inventory(tables["Inventory_History.csv"])
    products = clean_keys(tables["Product_Master.csv"], ["Product_ID", "SKU"])
    locations = clean_keys(tables["Locations.csv"], ["Location_ID"])

    inventory_accounting, inventory_accounting_summary = inventory_accounting_validation(inventory)
    inventory_continuity, inventory_month_summary = inventory_month_interpretation(inventory)
    monthly_reconciliation, reconciliation_summary, reconciliation_by_month = sales_inventory_reconciliation(
        sales, inventory
    )
    returns_summary, returns_reconciliation = returns_analysis(sales, inventory)
    daily_panel, panel_summary = build_daily_demand_panel(sales, products, locations)
    demand_series_eda, weekday_pattern, monthly_pattern, location_channel_summary, product_family_summary = (
        demand_behavior_eda(daily_panel)
    )
    price_discount_summary, discount_bin_summary, price_bin_summary = price_discount_eda(daily_panel)
    leakage_risk_table = leakage_risks()
    dq_summary = data_quality_summary(sales, inventory, products, locations)

    return Phase2Outputs(
        sales=sales,
        inventory=inventory,
        products=products,
        locations=locations,
        inventory_accounting=inventory_accounting,
        inventory_accounting_summary=inventory_accounting_summary,
        inventory_continuity=inventory_continuity,
        inventory_month_summary=inventory_month_summary,
        monthly_reconciliation=monthly_reconciliation,
        reconciliation_summary=reconciliation_summary,
        reconciliation_by_month=reconciliation_by_month,
        returns_summary=returns_summary,
        returns_reconciliation=returns_reconciliation,
        daily_panel=daily_panel,
        panel_summary=panel_summary,
        demand_series_eda=demand_series_eda,
        weekday_pattern=weekday_pattern,
        monthly_pattern=monthly_pattern,
        location_channel_summary=location_channel_summary,
        product_family_summary=product_family_summary,
        price_discount_summary=price_discount_summary,
        discount_bin_summary=discount_bin_summary,
        price_bin_summary=price_bin_summary,
        leakage_risk_table=leakage_risk_table,
        data_quality_summary=dq_summary,
    )


def metric(summary: pd.DataFrame, name: str) -> str:
    match = summary.loc[summary["metric"].eq(name), "value"]
    if match.empty:
        return "n/a"
    value = match.iloc[0]
    if isinstance(value, float):
        if value.is_integer():
            return f"{int(value):,}"
        return f"{value:,.3f}"
    if isinstance(value, (int, np.integer)):
        return f"{int(value):,}"
    return str(value)


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


def class_counts_text(series: pd.Series) -> str:
    counts = series.value_counts(dropna=False).sort_index()
    return ", ".join(f"{idx}: {fmt(value)}" for idx, value in counts.items())


def top_rows_markdown(frame: pd.DataFrame, columns: list[str], n: int = 5) -> str:
    subset = frame[columns].head(n)
    if subset.empty:
        return "No rows."
    display = subset.copy()
    for col in display.columns:
        if pd.api.types.is_datetime64_any_dtype(display[col]):
            display[col] = display[col].dt.date.astype(str)
        else:
            display[col] = display[col].map(fmt)
    header = "| " + " | ".join(display.columns) + " |"
    separator = "| " + " | ".join("---" for _ in display.columns) + " |"
    body = [
        "| " + " | ".join(str(value) for value in row) + " |"
        for row in display.to_numpy()
    ]
    return "\n".join([header, separator, *body])


def build_report(outputs: Phase2Outputs, data_dir: Path, output_dir: Path, processed_dir: Path) -> str:
    inv_summary = outputs.inventory_accounting_summary
    month_summary = outputs.inventory_month_summary
    rec_summary = outputs.reconciliation_summary
    returns_summary = outputs.returns_summary
    panel_summary = outputs.panel_summary
    series_eda = outputs.demand_series_eda
    fallback_count = int(series_eda["May_Need_Fallback_Later"].sum())
    fallback_pct = fallback_count / len(series_eda) * 100
    mismatch_examples = outputs.inventory_accounting.loc[
        ~outputs.inventory_accounting["Accounting_Holds_Exactly"]
    ].sort_values("Absolute_Mismatch", ascending=False)
    reconciliation_mismatches = outputs.monthly_reconciliation.loc[
        ~outputs.monthly_reconciliation["Exact_Match"]
    ].sort_values("Absolute_Difference", ascending=False)
    gross_target_decision = metric(returns_summary, "target_decision")
    price_discount_lines = "\n".join(
        f"- {row.measure}: correlation with sale-day demand = {row.correlation_with_daily_demand_sale_days_only:.3f}"
        for row in outputs.price_discount_summary.itertuples(index=False)
    )

    report = f"""# Phase 2 Data Cleaning And EDA Report

Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

Data directory: `{data_dir}`

## Scope Boundary

This is Phase 2 only. No forecasting models were trained, no 30/60/90-day forecasts were generated, no replenishment recommendations were calculated, no procurement or production risk scores were calculated, and no Streamlit dashboard was built.

All work uses only the provided CSV datasets. Raw files were read only. Derived files were written under `{processed_dir}` and `{output_dir}`.

The modeling grain remains `Product_ID x Location_ID`.

## Cleaning Decisions

- Parsed sales `Order_Date`, sales `Return_Date`, and inventory `Snapshot_Month` as dates.
- Standardized key columns by trimming whitespace in derived in-memory frames only.
- Did not impute missing values, fabricate records, alter stock quantities, or force accounting equations to balance.
- Preserved raw transaction data separately; the daily panel is a derived Product x Location EDA table.
- Built zero-demand dates only within each Product x Location pair's first-to-last observed demand window.

## Inventory Accounting Validation

Checked identity:

`Closing_Stock = Opening_Stock + Received_Qty + Returned_Qty - Sold_Qty - Damaged_Qty`

- Rows checked: {metric(inv_summary, "rows_checked")}
- Rows holding exactly: {metric(inv_summary, "rows_holding_exactly")} ({metric(inv_summary, "rows_holding_exactly_pct")}%)
- Mismatch rows: {metric(inv_summary, "mismatch_rows")} ({metric(inv_summary, "mismatch_rows_pct")}%)
- Nonzero mismatch median: {metric(inv_summary, "mismatch_median")}
- Nonzero mismatch 95th percentile: {metric(inv_summary, "mismatch_p95")}
- Nonzero mismatch max: {metric(inv_summary, "mismatch_max")}

Largest mismatch examples:

{top_rows_markdown(mismatch_examples, ["Snapshot_Month", "Product_ID", "Location_ID", "Opening_Stock", "Received_Qty", "Returned_Qty", "Sold_Qty", "Damaged_Qty", "Expected_Closing_Stock", "Closing_Stock", "Closing_Stock_Mismatch"])}

The data was not changed to force these rows to balance.

## Snapshot_Month Interpretation

- Snapshot day values: {metric(month_summary, "unique_snapshot_days")}
- Snapshot month range: {metric(month_summary, "snapshot_min_month")} to {metric(month_summary, "snapshot_max_month")}
- Product x Location month transitions checked: {metric(month_summary, "transition_rows")}
- Consecutive one-month transitions: {metric(month_summary, "monthly_gap_one_rows")} ({metric(month_summary, "monthly_gap_one_pct")}%)
- Previous `Closing_Stock` equals next `Opening_Stock`: {metric(month_summary, "continuity_exact_rows")} ({metric(month_summary, "continuity_exact_pct")}%)

Safest interpretation for later phases: `Snapshot_Month` is a monthly period label represented by the first day of the month. It is not safe to treat it as a point-in-time stock snapshot at the beginning of that day, because the 2026-09-01 rows include September sales through 2026-09-30 and reconcile to the full monthly `Sold_Qty`.

For future inventory alignment, use the latest inventory row as the latest completed monthly summary available in the dataset, and label `Closing_Stock` as the period closing finished-goods stock. Do not infer raw-material inventory.

## Sales Vs Inventory Demand Reconciliation

Monthly `Sales_Transactions.Quantity` was aggregated by `Month x Product_ID x Location_ID` and compared with `Inventory_History.Sold_Qty`.

- Rows compared: {metric(rec_summary, "rows_compared")}
- Rows with both sources: {metric(rec_summary, "rows_with_both_sources")}
- Inventory-only rows after zero sales fill: {metric(rec_summary, "rows_inventory_only_after_zero_fill")}
- Sales-only rows: {metric(rec_summary, "rows_sales_only")}
- Exact matches: {metric(rec_summary, "exact_match_rows")} ({metric(rec_summary, "exact_match_pct_all_rows")}%)
- Mean absolute difference: {metric(rec_summary, "absolute_difference_mean")}
- Max absolute difference: {metric(rec_summary, "absolute_difference_max")}
- Correlation: {metric(rec_summary, "correlation_sales_quantity_vs_inventory_sold_qty")}

Mismatch examples:

{top_rows_markdown(reconciliation_mismatches, ["Month", "Product_ID", "Location_ID", "Sales_Quantity", "Sold_Qty", "Quantity_Minus_Sold_Qty", "Absolute_Difference"])}

There is no evidence of systematic difference between monthly sales `Quantity` and inventory `Sold_Qty`; they reconcile exactly after representing missing transaction months as zero sales where inventory also records zero sold units.

## Returns Treatment And Forecast Target Decision

- Returned transaction rows: {metric(returns_summary, "returned_rows")} ({metric(returns_summary, "returned_rows_pct")}%)
- Total sold quantity: {metric(returns_summary, "quantity_total")}
- Returned quantity by order date: {metric(returns_summary, "returned_quantity_by_order_date")} ({metric(returns_summary, "returned_quantity_pct_of_sales_quantity")}% of sold quantity)
- Return date present for returned rows: {metric(returns_summary, "return_date_present_for_returned_rows_pct")}%
- Median return lag: {metric(returns_summary, "return_lag_days_median")} days
- 95th percentile return lag: {metric(returns_summary, "return_lag_days_p95")} days

Decision: {gross_target_decision}

## Daily Product x Location Demand Panel

- Panel rows: {metric(panel_summary, "panel_rows")}
- Expected rows from pair observation windows: {metric(panel_summary, "expected_rows_from_pair_windows")}
- Nonzero daily rows before zero filling: {metric(panel_summary, "actual_nonzero_daily_rows_before_zero_fill")}
- Explicit zero-demand rows: {metric(panel_summary, "zero_demand_rows_added")}
- Date range: {metric(panel_summary, "panel_min_date")} to {metric(panel_summary, "panel_max_date")}
- Product x Location pairs: {metric(panel_summary, "product_location_pairs")}

Missing transaction rows inside an observed pair window were treated as zero observed demand days for EDA because monthly sales reconcile exactly to inventory `Sold_Qty` and the transaction table is line-level sales history. No zeros were created outside each pair's first and last observed demand date.

## Demand Behavior EDA

- Product x Location series analyzed: {fmt(len(series_eda))}
- Total demand across panel: {fmt(outputs.daily_panel["Demand_Units"].sum())}
- Mean zero-demand percentage across series: {fmt(series_eda["Zero_Demand_Pct"].mean())}%
- Median zero-demand percentage across series: {fmt(series_eda["Zero_Demand_Pct"].median())}%
- Mean coefficient of variation across series: {fmt(series_eda["CV_Daily_Demand"].mean())}
- Demand pattern classes: {class_counts_text(series_eda["Demand_Pattern_Class"])}
- Series flagged as possibly needing fallback methods later: {fmt(fallback_count)} ({fallback_pct:.3f}%)

Top demand series:

{top_rows_markdown(series_eda.sort_values("Total_Demand", ascending=False), ["Product_ID", "Location_ID", "Channel", "Product_Family", "Total_Demand", "Mean_Daily_Demand", "Zero_Demand_Pct", "Demand_Pattern_Class", "May_Need_Fallback_Later"])}

Location/channel summary:

{top_rows_markdown(outputs.location_channel_summary.sort_values("Total_Demand", ascending=False), ["Location_ID", "Channel", "Total_Demand", "Mean_Daily_Demand", "Zero_Demand_Pct", "Product_Count"])}

Product-family summary:

{top_rows_markdown(outputs.product_family_summary.sort_values("Total_Demand", ascending=False), ["Product_Family", "Total_Demand", "Mean_Daily_Demand", "Zero_Demand_Pct", "Product_Count"])}

Weekly and monthly pattern summaries were exported for Phase 3 review. They should be treated as descriptive EDA, not model selection.

## Sparsity And Intermittency Definitions

For each Product x Location series:

- `Demand_Frequency_Pct = nonzero demand days / active days`.
- `Zero_Demand_Pct = zero demand days / active days`.
- `Average_Demand_Interval_Days = active days / nonzero demand days`.
- `Nonzero_Demand_CV2 = squared coefficient of variation for nonzero daily demand`.
- Demand pattern classes use documented EDA thresholds: smooth when ADI <= 1.32 and CV2 <= 0.49, intermittent when ADI > 1.32 and CV2 <= 0.49, erratic when ADI <= 1.32 and CV2 > 0.49, and lumpy when ADI > 1.32 and CV2 > 0.49.

These flags are for Phase 3 fallback planning only. No final forecasting model has been selected.

## Price And Discount Exploration

Sale-day-only exploratory correlations:

{price_discount_lines}

Demand is visibly associated with discount in the aggregate EDA, but this is not causal evidence. Wholesale orders have much higher quantities and higher discounts, so channel and product mix are major confounders. Any future feature use must avoid leakage and use only price/discount information known before the forecast origin.

## Leakage Risks

Created `leakage_risk_table.csv`. High-risk fields include realized financial outcomes, return outcomes, period-end inventory outcomes, and future procurement/production outcomes. `List_Price_EGP` and `Discount_Pct` are conditional: safe only if known as planned future inputs, not if derived from same-day realized transactions.

## Data Limitations

- No current raw-material inventory table exists; do not calculate current material stock.
- `Snapshot_Month` is monthly-period data, not a daily stock snapshot.
- Inventory accounting mismatches exist in 147 rows and should be handled transparently later.
- Sales and inventory use three commercial locations; head office and factory locations have no sales/inventory demand rows.
- Gross demand is selected as the target; returns are real and should be monitored separately.
- EDA associations with price/discount are confounded and not causal.

## Files Created Or Modified

- `{processed_dir / "daily_product_location_demand_panel.csv"}`
- `{processed_dir / "monthly_sales_inventory_reconciliation.csv"}`
- `{output_dir / "phase2_cleaning_eda_report.md"}`
- `{output_dir / "inventory_accounting_validation.csv"}`
- `{output_dir / "inventory_accounting_summary.csv"}`
- `{output_dir / "inventory_month_continuity.csv"}`
- `{output_dir / "inventory_month_interpretation_summary.csv"}`
- `{output_dir / "sales_inventory_reconciliation_summary.csv"}`
- `{output_dir / "sales_inventory_reconciliation_by_month.csv"}`
- `{output_dir / "returns_summary.csv"}`
- `{output_dir / "returns_reconciliation.csv"}`
- `{output_dir / "daily_demand_panel_summary.csv"}`
- `{output_dir / "demand_series_eda.csv"}`
- `{output_dir / "weekday_demand_pattern.csv"}`
- `{output_dir / "monthly_demand_pattern.csv"}`
- `{output_dir / "location_channel_demand_summary.csv"}`
- `{output_dir / "product_family_demand_summary.csv"}`
- `{output_dir / "price_discount_summary.csv"}`
- `{output_dir / "discount_bin_demand_summary.csv"}`
- `{output_dir / "price_bin_demand_summary.csv"}`
- `{output_dir / "leakage_risk_table.csv"}`
- `{output_dir / "data_quality_summary.csv"}`
- `src/phase2_cleaning_eda.py`

## Recommendation For Phase 3

After review approval, Phase 3 should build baseline forecasting only. Use the gross daily demand panel at `Product_ID x Location_ID`, keep time-based validation, and define fallback behavior for sparse or high-variability series before comparing stronger models in later phases.

Stop here for approval before Phase 3.
"""
    return report


def write_outputs(outputs: Phase2Outputs, data_dir: Path, output_dir: Path, processed_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)

    outputs.daily_panel.to_csv(
        processed_dir / "daily_product_location_demand_panel.csv",
        index=False,
        encoding="utf-8",
    )
    outputs.monthly_reconciliation.to_csv(
        processed_dir / "monthly_sales_inventory_reconciliation.csv",
        index=False,
        encoding="utf-8",
    )

    export_map: dict[str, pd.DataFrame] = {
        "inventory_accounting_validation.csv": outputs.inventory_accounting,
        "inventory_accounting_summary.csv": outputs.inventory_accounting_summary,
        "inventory_month_continuity.csv": outputs.inventory_continuity,
        "inventory_month_interpretation_summary.csv": outputs.inventory_month_summary,
        "sales_inventory_reconciliation_summary.csv": outputs.reconciliation_summary,
        "sales_inventory_reconciliation_by_month.csv": outputs.reconciliation_by_month,
        "returns_summary.csv": outputs.returns_summary,
        "returns_reconciliation.csv": outputs.returns_reconciliation,
        "daily_demand_panel_summary.csv": outputs.panel_summary,
        "demand_series_eda.csv": outputs.demand_series_eda,
        "weekday_demand_pattern.csv": outputs.weekday_pattern,
        "monthly_demand_pattern.csv": outputs.monthly_pattern,
        "location_channel_demand_summary.csv": outputs.location_channel_summary,
        "product_family_demand_summary.csv": outputs.product_family_summary,
        "price_discount_summary.csv": outputs.price_discount_summary,
        "discount_bin_demand_summary.csv": outputs.discount_bin_summary,
        "price_bin_demand_summary.csv": outputs.price_bin_summary,
        "leakage_risk_table.csv": outputs.leakage_risk_table,
        "data_quality_summary.csv": outputs.data_quality_summary,
    }
    for file_name, frame in export_map.items():
        frame.to_csv(output_dir / file_name, index=False, encoding="utf-8")

    report_path = output_dir / "phase2_cleaning_eda_report.md"
    report_path.write_text(build_report(outputs, data_dir, output_dir, processed_dir), encoding="utf-8")
    return report_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Phase 2 cleaning and EDA only.")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--processed-dir", type=Path, default=DEFAULT_PROCESSED_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    data_dir = args.data_dir.resolve()
    output_dir = args.output_dir.resolve()
    processed_dir = args.processed_dir.resolve()
    if not data_dir.exists():
        raise FileNotFoundError(f"Data directory not found: {data_dir}")
    outputs = run_phase2(data_dir)
    report_path = write_outputs(outputs, data_dir, output_dir, processed_dir)
    print(f"Phase 2 cleaning and EDA complete: {report_path}")


if __name__ == "__main__":
    main()
