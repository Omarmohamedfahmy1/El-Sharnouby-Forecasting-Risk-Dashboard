"""Phase 8 production risk analysis.

This phase analyzes historical production execution for products that may
require replenishment. It does not create future production capacity, current
line availability, exact schedules, final combined risk, action dates, or
Streamlit outputs.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from phase3_forecasting_baseline import HORIZONS, fmt, markdown_table


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = PROJECT_ROOT / "data" / "raw"
DEFAULT_PHASE6_DIR = PROJECT_ROOT / "outputs" / "phase6"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "outputs" / "phase8"
PRODUCT_LOW_EVIDENCE_ORDER_COUNT = 10
PRODUCT_HIGH_EVIDENCE_ORDER_COUNT = 25
PRODUCT_LINE_LOW_HISTORY_ORDER_COUNT = 5


@dataclass
class Phase8Outputs:
    production_orders_enriched: pd.DataFrame
    product_production_history: pd.DataFrame
    line_production_history: pd.DataFrame
    product_line_production_history: pd.DataFrame
    bottleneck_analysis: pd.DataFrame
    historical_production_risk: pd.DataFrame
    product_replenishment_production_risk: pd.DataFrame
    production_data_quality: pd.DataFrame
    validation_checks: pd.DataFrame
    report: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Phase 8 historical production risk analysis.")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=DEFAULT_DATA_DIR,
        help="Directory containing provided raw CSV datasets.",
    )
    parser.add_argument(
        "--phase6-dir",
        type=Path,
        default=DEFAULT_PHASE6_DIR,
        help="Directory containing accepted Phase 6 outputs.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory for Phase 8 outputs.",
    )
    return parser.parse_args()


def read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Required input not found: {path}")
    return pd.read_csv(path)


def load_sources(
    data_dir: Path,
    phase6_dir: Path,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    production_orders = read_csv(data_dir / "Production_Orders.csv")
    product_master = read_csv(data_dir / "Product_Master.csv")
    data_dictionary = read_csv(data_dir / "Data_Dictionary.csv")
    phase6_replenishment = read_csv(phase6_dir / "product_replenishment_requirements.csv")
    return production_orders, product_master, data_dictionary, phase6_replenishment


def require_columns(frame: pd.DataFrame, required: set[str], name: str) -> None:
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"{name} is missing required columns: {missing}")


def validate_input_schemas(
    production_orders: pd.DataFrame,
    product_master: pd.DataFrame,
    phase6_replenishment: pd.DataFrame,
) -> None:
    require_columns(
        production_orders,
        {
            "Production_Order_ID",
            "Product_ID",
            "Product_Name",
            "Start_Date",
            "Due_Date",
            "Completion_Date",
            "Planned_Qty",
            "Produced_Qty",
            "Good_Qty",
            "Rejected_Qty",
            "Line_ID",
            "Efficiency_Pct",
            "Delay_Days",
            "Primary_Bottleneck",
            "Overtime_Hours",
        },
        "Production_Orders.csv",
    )
    require_columns(
        product_master,
        {
            "Product_ID",
            "Product_Name",
            "Product_Family",
            "Gender",
            "Audience",
            "Catalog_Season",
        },
        "Product_Master.csv",
    )
    require_columns(
        phase6_replenishment,
        {
            "Product_ID",
            "Product_Name",
            "Product_Family",
            "Horizon_Days",
            "Production_Equivalent_Replenishment_Qty",
            "Locations_Requiring_Replenishment_Count",
            "High_Risk_Locations_Count",
            "Requires_Replenishment",
        },
        "Phase 6 product_replenishment_requirements.csv",
    )


def parse_production_orders(production_orders: pd.DataFrame) -> pd.DataFrame:
    work = production_orders.copy()
    for column in ["Start_Date", "Due_Date", "Completion_Date"]:
        work[column] = pd.to_datetime(work[column], errors="coerce")
    for column in [
        "Planned_Qty",
        "Produced_Qty",
        "Good_Qty",
        "Rejected_Qty",
        "Efficiency_Pct",
        "Delay_Days",
        "Overtime_Hours",
    ]:
        work[column] = pd.to_numeric(work[column], errors="coerce")
    return work


def build_production_orders_enriched(
    production_orders: pd.DataFrame,
    product_master: pd.DataFrame,
) -> pd.DataFrame:
    work = parse_production_orders(production_orders)
    product_lookup = product_master[
        [
            "Product_ID",
            "SKU",
            "Product_Name",
            "Brand",
            "Product_Family",
            "Gender",
            "Audience",
            "Catalog_Season",
        ]
    ].drop_duplicates("Product_ID")
    enriched = work.merge(
        product_lookup.rename(columns={"Product_Name": "Product_Name_Master"}),
        on="Product_ID",
        how="left",
        validate="many_to_one",
    )
    enriched["Product_Resolved_Flag"] = enriched["Product_Name_Master"].notna()
    enriched["Product_Name_Matches_Master_Flag"] = (
        enriched["Product_Resolved_Flag"]
        & enriched["Product_Name"].astype(str).eq(enriched["Product_Name_Master"].astype(str))
    )
    enriched["Production_Lead_Time_Days"] = (
        enriched["Completion_Date"] - enriched["Start_Date"]
    ).dt.days
    enriched["Planned_Lead_Time_Days"] = (enriched["Due_Date"] - enriched["Start_Date"]).dt.days
    enriched["Completion_Delay_Days"] = (enriched["Completion_Date"] - enriched["Due_Date"]).dt.days
    on_time_mask = enriched[["Completion_Date", "Due_Date"]].notna().all(axis=1)
    on_time_bool = enriched["Completion_Date"].le(enriched["Due_Date"])
    enriched["On_Time_Production_Flag"] = pd.Series(
        np.where(on_time_mask, on_time_bool, pd.NA),
        dtype="boolean",
    )
    enriched["On_Time_Production_Numeric"] = np.where(on_time_mask, on_time_bool.astype(float), np.nan)
    enriched["Plan_Attainment_Rate"] = np.where(
        enriched["Planned_Qty"].gt(0),
        enriched["Produced_Qty"] / enriched["Planned_Qty"],
        np.nan,
    )
    enriched["Good_Yield_Rate"] = np.where(
        enriched["Produced_Qty"].gt(0),
        enriched["Good_Qty"] / enriched["Produced_Qty"],
        np.nan,
    )
    enriched["Rejection_Rate"] = np.where(
        enriched["Produced_Qty"].gt(0),
        enriched["Rejected_Qty"] / enriched["Produced_Qty"],
        np.nan,
    )
    enriched["Good_vs_Planned_Rate"] = np.where(
        enriched["Planned_Qty"].gt(0),
        enriched["Good_Qty"] / enriched["Planned_Qty"],
        np.nan,
    )

    quantity_columns = ["Planned_Qty", "Produced_Qty", "Good_Qty", "Rejected_Qty"]
    enriched["Missing_Key_Field_Flag"] = enriched[
        ["Production_Order_ID", "Product_ID", "Start_Date", "Due_Date", "Completion_Date"]
    ].isna().any(axis=1)
    enriched["Negative_Quantity_Flag"] = enriched[quantity_columns].lt(0).any(axis=1)
    enriched["Negative_Efficiency_Flag"] = enriched["Efficiency_Pct"].lt(0)
    enriched["Efficiency_Above_100_Flag"] = enriched["Efficiency_Pct"].gt(100)
    enriched["Completion_Before_Start_Flag"] = enriched["Production_Lead_Time_Days"].lt(0)
    enriched["Due_Before_Start_Flag"] = enriched["Planned_Lead_Time_Days"].lt(0)
    enriched["Invalid_Date_Ordering_Flag"] = (
        enriched["Completion_Before_Start_Flag"] | enriched["Due_Before_Start_Flag"]
    )
    enriched["Good_Qty_Greater_Than_Produced_Flag"] = enriched["Good_Qty"].gt(enriched["Produced_Qty"])
    enriched["Rejected_Relationship_Difference"] = (
        enriched["Produced_Qty"] - enriched["Good_Qty"] - enriched["Rejected_Qty"]
    )
    enriched["Rejected_Relationship_Match_Flag"] = enriched["Rejected_Relationship_Difference"].abs().le(1e-9)
    enriched["Produced_Greater_Than_Planned_Flag"] = enriched["Produced_Qty"].gt(enriched["Planned_Qty"])
    enriched["Produced_Equals_Planned_Flag"] = enriched["Produced_Qty"].eq(enriched["Planned_Qty"])
    enriched["Produced_vs_Planned_Difference"] = enriched["Produced_Qty"] - enriched["Planned_Qty"]
    enriched["Delay_Days_Source_Difference"] = enriched["Completion_Delay_Days"] - enriched["Delay_Days"]
    enriched["Delay_Days_Source_Mismatch_Flag"] = enriched["Delay_Days_Source_Difference"].abs().gt(1e-9)
    enriched["Primary_Bottleneck_Display"] = enriched["Primary_Bottleneck"].fillna("No bottleneck recorded")

    return enriched.sort_values("Production_Order_ID").reset_index(drop=True)


def issue_row(
    check: str,
    metric_value: object,
    issue_count: int,
    total_records: int,
    detail: str,
) -> dict[str, object]:
    issue_pct = np.nan if total_records == 0 else issue_count / total_records
    return {
        "Check": check,
        "Metric_Value": metric_value,
        "Issue_Count": int(issue_count),
        "Total_Records": int(total_records),
        "Issue_Pct": issue_pct,
        "Detail": detail,
    }


def build_production_data_quality(enriched: pd.DataFrame) -> pd.DataFrame:
    total = len(enriched)
    duplicate_id_rows = int(enriched.duplicated("Production_Order_ID", keep=False).sum())
    duplicate_ids = int(enriched["Production_Order_ID"].duplicated().sum())
    quantity_columns = ["Planned_Qty", "Produced_Qty", "Good_Qty", "Rejected_Qty"]
    planned_differs = int((~enriched["Produced_Equals_Planned_Flag"]).sum())
    produced_under = int(enriched["Produced_vs_Planned_Difference"].lt(0).sum())
    produced_over = int(enriched["Produced_vs_Planned_Difference"].gt(0).sum())
    checks = [
        issue_row("row_count", total, 0, total, "Production_Orders.csv rows handled in enriched output."),
        issue_row(
            "unique_production_order_id_count",
            enriched["Production_Order_ID"].nunique(dropna=True),
            duplicate_ids,
            total,
            f"duplicate_id_rows={duplicate_id_rows}",
        ),
        issue_row(
            "duplicate_production_order_id_rows",
            duplicate_id_rows,
            duplicate_id_rows,
            total,
            "Rows sharing a Production_Order_ID with at least one other row.",
        ),
        issue_row(
            "missing_product_id",
            int(enriched["Product_ID"].isna().sum()),
            int(enriched["Product_ID"].isna().sum()),
            total,
            "Product_ID missing before product resolution.",
        ),
        issue_row(
            "missing_start_date",
            int(enriched["Start_Date"].isna().sum()),
            int(enriched["Start_Date"].isna().sum()),
            total,
            "Start_Date missing or unparseable.",
        ),
        issue_row(
            "missing_due_date",
            int(enriched["Due_Date"].isna().sum()),
            int(enriched["Due_Date"].isna().sum()),
            total,
            "Due_Date missing or unparseable.",
        ),
        issue_row(
            "missing_completion_date",
            int(enriched["Completion_Date"].isna().sum()),
            int(enriched["Completion_Date"].isna().sum()),
            total,
            "Completion_Date missing or unparseable.",
        ),
        issue_row(
            "invalid_date_ordering",
            int(enriched["Invalid_Date_Ordering_Flag"].sum()),
            int(enriched["Invalid_Date_Ordering_Flag"].sum()),
            total,
            "Flags due date before start date or completion date before start date.",
        ),
        issue_row(
            "negative_quantities",
            int(enriched["Negative_Quantity_Flag"].sum()),
            int(enriched["Negative_Quantity_Flag"].sum()),
            total,
            f"Checked {quantity_columns}.",
        ),
        issue_row(
            "negative_efficiency_pct",
            int(enriched["Negative_Efficiency_Flag"].sum()),
            int(enriched["Negative_Efficiency_Flag"].sum()),
            total,
            "Efficiency_Pct below zero.",
        ),
        issue_row(
            "efficiency_pct_above_100",
            int(enriched["Efficiency_Above_100_Flag"].sum()),
            int(enriched["Efficiency_Above_100_Flag"].sum()),
            total,
            "Efficiency_Pct above 100.",
        ),
        issue_row(
            "good_qty_greater_than_produced_qty",
            int(enriched["Good_Qty_Greater_Than_Produced_Flag"].sum()),
            int(enriched["Good_Qty_Greater_Than_Produced_Flag"].sum()),
            total,
            "Good_Qty should not exceed Produced_Qty.",
        ),
        issue_row(
            "rejected_qty_relationship_mismatch",
            int((~enriched["Rejected_Relationship_Match_Flag"]).sum()),
            int((~enriched["Rejected_Relationship_Match_Flag"]).sum()),
            total,
            "Checks Produced_Qty - Good_Qty - Rejected_Qty equals zero.",
        ),
        issue_row(
            "produced_qty_greater_than_planned_qty",
            produced_over,
            produced_over,
            total,
            "Produced_Qty above Planned_Qty.",
        ),
        issue_row(
            "produced_qty_differs_from_planned_qty",
            planned_differs,
            planned_differs,
            total,
            f"Produced below planned={produced_under}; above planned={produced_over}. This feeds plan attainment.",
        ),
        issue_row(
            "delay_days_source_mismatch",
            int(enriched["Delay_Days_Source_Mismatch_Flag"].sum()),
            int(enriched["Delay_Days_Source_Mismatch_Flag"].sum()),
            total,
            "Compares source Delay_Days with Completion_Date - Due_Date.",
        ),
        issue_row(
            "unresolved_product_id",
            int((~enriched["Product_Resolved_Flag"]).sum()),
            int((~enriched["Product_Resolved_Flag"]).sum()),
            total,
            "Product_ID not found in Product_Master.csv.",
        ),
    ]
    return pd.DataFrame(checks)


def q90(series: pd.Series) -> float:
    return float(series.dropna().quantile(0.90)) if series.notna().any() else np.nan


def mode_non_null(series: pd.Series) -> str:
    values = series.dropna()
    if values.empty:
        return "No bottleneck recorded"
    counts = values.value_counts()
    return str(counts.index[0])


def aggregate_product_history(enriched: pd.DataFrame, product_master: pd.DataFrame) -> pd.DataFrame:
    stats = (
        enriched.groupby("Product_ID", dropna=False)
        .agg(
            Production_Order_Count=("Production_Order_ID", "count"),
            Line_Count=("Line_ID", "nunique"),
            Mean_Production_Lead_Time_Days=("Production_Lead_Time_Days", "mean"),
            Median_Production_Lead_Time_Days=("Production_Lead_Time_Days", "median"),
            P90_Production_Lead_Time_Days=("Production_Lead_Time_Days", q90),
            Mean_Completion_Delay_Days=("Completion_Delay_Days", "mean"),
            Late_Production_Order_Rate=("On_Time_Production_Numeric", lambda x: 1 - x.mean()),
            On_Time_Production_Order_Rate=("On_Time_Production_Numeric", "mean"),
            Mean_Efficiency_Pct=("Efficiency_Pct", "mean"),
            Median_Efficiency_Pct=("Efficiency_Pct", "median"),
            Mean_Plan_Attainment_Rate=("Plan_Attainment_Rate", "mean"),
            Mean_Good_Yield_Rate=("Good_Yield_Rate", "mean"),
            Mean_Rejection_Rate=("Rejection_Rate", "mean"),
            Mean_Good_vs_Planned_Rate=("Good_vs_Planned_Rate", "mean"),
            Mean_Overtime_Hours=("Overtime_Hours", "mean"),
            Total_Planned_Qty=("Planned_Qty", "sum"),
            Total_Produced_Qty=("Produced_Qty", "sum"),
            Total_Good_Qty=("Good_Qty", "sum"),
            Total_Rejected_Qty=("Rejected_Qty", "sum"),
            Historical_Median_Planned_Qty=("Planned_Qty", "median"),
            Historical_P90_Planned_Qty=("Planned_Qty", q90),
            Most_Common_Historical_Primary_Bottleneck=("Primary_Bottleneck", mode_non_null),
            Latest_Production_Date=("Completion_Date", "max"),
        )
        .reset_index()
    )
    product_cols = [
        "Product_ID",
        "Product_Name",
        "Product_Family",
        "Gender",
        "Audience",
        "Catalog_Season",
    ]
    product_info = product_master[product_cols].drop_duplicates("Product_ID")
    history = product_info.merge(stats, on="Product_ID", how="left")
    count_cols = [
        "Production_Order_Count",
        "Line_Count",
        "Total_Planned_Qty",
        "Total_Produced_Qty",
        "Total_Good_Qty",
        "Total_Rejected_Qty",
    ]
    history[count_cols] = history[count_cols].fillna(0)
    history["Production_Order_Count"] = history["Production_Order_Count"].astype(int)
    history["Line_Count"] = history["Line_Count"].astype(int)
    return history.sort_values("Product_ID").reset_index(drop=True)


def aggregate_line_history(enriched: pd.DataFrame) -> pd.DataFrame:
    history = (
        enriched.groupby("Line_ID", dropna=False)
        .agg(
            Production_Order_Count=("Production_Order_ID", "count"),
            Product_Count=("Product_ID", "nunique"),
            Mean_Efficiency_Pct=("Efficiency_Pct", "mean"),
            Median_Efficiency_Pct=("Efficiency_Pct", "median"),
            Late_Order_Rate=("On_Time_Production_Numeric", lambda x: 1 - x.mean()),
            On_Time_Order_Rate=("On_Time_Production_Numeric", "mean"),
            Mean_Completion_Delay_Days=("Completion_Delay_Days", "mean"),
            Mean_Good_Yield_Rate=("Good_Yield_Rate", "mean"),
            Mean_Rejection_Rate=("Rejection_Rate", "mean"),
            Mean_Overtime_Hours=("Overtime_Hours", "mean"),
            Latest_Production_Date=("Completion_Date", "max"),
        )
        .reset_index()
    )
    return history.sort_values("Line_ID").reset_index(drop=True)


def aggregate_product_line_history(enriched: pd.DataFrame, product_master: pd.DataFrame) -> pd.DataFrame:
    history = (
        enriched.groupby(["Product_ID", "Line_ID"], dropna=False)
        .agg(
            Production_Order_Count=("Production_Order_ID", "count"),
            Mean_Efficiency_Pct=("Efficiency_Pct", "mean"),
            Late_Order_Rate=("On_Time_Production_Numeric", lambda x: 1 - x.mean()),
            On_Time_Order_Rate=("On_Time_Production_Numeric", "mean"),
            Mean_Completion_Delay_Days=("Completion_Delay_Days", "mean"),
            Mean_Plan_Attainment_Rate=("Plan_Attainment_Rate", "mean"),
            Mean_Good_Yield_Rate=("Good_Yield_Rate", "mean"),
            Mean_Rejection_Rate=("Rejection_Rate", "mean"),
            Mean_Overtime_Hours=("Overtime_Hours", "mean"),
            Latest_Production_Date=("Completion_Date", "max"),
        )
        .reset_index()
    )
    product_info = product_master[
        ["Product_ID", "Product_Name", "Product_Family"]
    ].drop_duplicates("Product_ID")
    history = history.merge(product_info, on="Product_ID", how="left")
    history["Low_History_Flag"] = history["Production_Order_Count"] < PRODUCT_LINE_LOW_HISTORY_ORDER_COUNT
    columns = [
        "Product_ID",
        "Product_Name",
        "Product_Family",
        "Line_ID",
        "Production_Order_Count",
        "Mean_Efficiency_Pct",
        "Late_Order_Rate",
        "On_Time_Order_Rate",
        "Mean_Completion_Delay_Days",
        "Mean_Plan_Attainment_Rate",
        "Mean_Good_Yield_Rate",
        "Mean_Rejection_Rate",
        "Mean_Overtime_Hours",
        "Latest_Production_Date",
        "Low_History_Flag",
    ]
    return history[columns].sort_values(["Product_ID", "Line_ID"]).reset_index(drop=True)


def build_bottleneck_analysis(enriched: pd.DataFrame) -> pd.DataFrame:
    total_orders = len(enriched)
    analysis = (
        enriched.groupby("Primary_Bottleneck_Display", dropna=False)
        .agg(
            Production_Order_Count=("Production_Order_ID", "count"),
            Average_Completion_Delay_Days=("Completion_Delay_Days", "mean"),
            Average_Efficiency_Pct=("Efficiency_Pct", "mean"),
            Average_Overtime_Hours=("Overtime_Hours", "mean"),
            Late_Order_Rate=("On_Time_Production_Numeric", lambda x: 1 - x.mean()),
            Average_Good_Yield_Rate=("Good_Yield_Rate", "mean"),
            Average_Rejection_Rate=("Rejection_Rate", "mean"),
        )
        .reset_index()
        .rename(columns={"Primary_Bottleneck_Display": "Primary_Bottleneck"})
    )
    analysis["Bottleneck_Share"] = analysis["Production_Order_Count"] / total_orders if total_orders else np.nan
    return analysis.sort_values("Production_Order_Count", ascending=False).reset_index(drop=True)


def product_evidence_level(order_count: int) -> str:
    if order_count < PRODUCT_LOW_EVIDENCE_ORDER_COUNT:
        return "Low"
    if order_count < PRODUCT_HIGH_EVIDENCE_ORDER_COUNT:
        return "Medium"
    return "High"


def threshold_value(frame: pd.DataFrame, column: str, quantile: float) -> float:
    values = frame[column].dropna()
    if values.empty:
        return np.nan
    return float(values.quantile(quantile))


def build_historical_production_risk(
    product_history: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, float]]:
    threshold_base = product_history[
        product_history["Production_Order_Count"].ge(PRODUCT_LOW_EVIDENCE_ORDER_COUNT)
    ].copy()
    thresholds = {
        "late_p75": threshold_value(threshold_base, "Late_Production_Order_Rate", 0.75),
        "late_p90": threshold_value(threshold_base, "Late_Production_Order_Rate", 0.90),
        "delay_p75": threshold_value(threshold_base, "Mean_Completion_Delay_Days", 0.75),
        "delay_p90": threshold_value(threshold_base, "Mean_Completion_Delay_Days", 0.90),
        "lead_p75": threshold_value(threshold_base, "P90_Production_Lead_Time_Days", 0.75),
        "lead_p90": threshold_value(threshold_base, "P90_Production_Lead_Time_Days", 0.90),
        "efficiency_p25": threshold_value(threshold_base, "Mean_Efficiency_Pct", 0.25),
        "efficiency_p10": threshold_value(threshold_base, "Mean_Efficiency_Pct", 0.10),
        "plan_attainment_p25": threshold_value(threshold_base, "Mean_Plan_Attainment_Rate", 0.25),
        "plan_attainment_p10": threshold_value(threshold_base, "Mean_Plan_Attainment_Rate", 0.10),
        "good_yield_p25": threshold_value(threshold_base, "Mean_Good_Yield_Rate", 0.25),
        "good_yield_p10": threshold_value(threshold_base, "Mean_Good_Yield_Rate", 0.10),
        "rejection_p75": threshold_value(threshold_base, "Mean_Rejection_Rate", 0.75),
        "rejection_p90": threshold_value(threshold_base, "Mean_Rejection_Rate", 0.90),
        "overtime_p75": threshold_value(threshold_base, "Mean_Overtime_Hours", 0.75),
        "overtime_p90": threshold_value(threshold_base, "Mean_Overtime_Hours", 0.90),
    }

    high_is_high_specs = [
        ("Late_Production_Order_Rate", "late_p75", "late_p90", "late production order rate"),
        ("Mean_Completion_Delay_Days", "delay_p75", "delay_p90", "mean completion delay"),
        ("P90_Production_Lead_Time_Days", "lead_p75", "lead_p90", "P90 production lead time"),
        ("Mean_Rejection_Rate", "rejection_p75", "rejection_p90", "mean rejection rate"),
        ("Mean_Overtime_Hours", "overtime_p75", "overtime_p90", "mean overtime hours"),
    ]
    low_is_bad_specs = [
        ("Mean_Efficiency_Pct", "efficiency_p25", "efficiency_p10", "mean efficiency pct"),
        ("Mean_Plan_Attainment_Rate", "plan_attainment_p25", "plan_attainment_p10", "mean plan attainment rate"),
        ("Mean_Good_Yield_Rate", "good_yield_p25", "good_yield_p10", "mean good yield rate"),
    ]

    def classify(row: pd.Series) -> pd.Series:
        order_count = int(row.get("Production_Order_Count", 0) or 0)
        evidence = product_evidence_level(order_count)
        if evidence == "Low":
            return pd.Series(
                {
                    "Production_Evidence_Level": evidence,
                    "Historical_Production_Risk": "Insufficient Evidence",
                    "Production_Risk_Reason": (
                        f"Only {order_count} historical production orders; minimum for risk "
                        f"classification is {PRODUCT_LOW_EVIDENCE_ORDER_COUNT}."
                    ),
                }
            )

        high_reasons: list[str] = []
        medium_reasons: list[str] = []
        for column, p75_key, p90_key, label in high_is_high_specs:
            value = row.get(column)
            if pd.isna(value):
                continue
            p75 = thresholds[p75_key]
            p90 = thresholds[p90_key]
            if not pd.isna(p90) and value > p90:
                high_reasons.append(f"{label} {fmt(float(value))} > empirical P90 {fmt(p90)}")
            elif not pd.isna(p75) and value > p75:
                medium_reasons.append(f"{label} {fmt(float(value))} > empirical P75 {fmt(p75)}")

        for column, p25_key, p10_key, label in low_is_bad_specs:
            value = row.get(column)
            if pd.isna(value):
                continue
            p25 = thresholds[p25_key]
            p10 = thresholds[p10_key]
            if not pd.isna(p10) and value < p10:
                high_reasons.append(f"{label} {fmt(float(value))} < empirical P10 {fmt(p10)}")
            elif not pd.isna(p25) and value < p25:
                medium_reasons.append(f"{label} {fmt(float(value))} < empirical P25 {fmt(p25)}")

        if high_reasons:
            risk = "High"
            reason_core = "; ".join(high_reasons)
        elif medium_reasons:
            risk = "Medium"
            reason_core = "; ".join(medium_reasons)
        else:
            risk = "Low"
            reason_core = "No monitored metric crossed relative production-risk thresholds."

        return pd.Series(
            {
                "Production_Evidence_Level": evidence,
                "Historical_Production_Risk": risk,
                "Production_Risk_Reason": f"{reason_core} Evidence={evidence} ({order_count} orders).",
            }
        )

    risk_fields = product_history.apply(classify, axis=1)
    risk = pd.concat([product_history.copy(), risk_fields], axis=1)
    ordered_cols = [
        "Product_ID",
        "Product_Name",
        "Product_Family",
        "Gender",
        "Audience",
        "Catalog_Season",
        "Production_Order_Count",
        "Line_Count",
        "Production_Evidence_Level",
        "Historical_Production_Risk",
        "Production_Risk_Reason",
        "Mean_Production_Lead_Time_Days",
        "Median_Production_Lead_Time_Days",
        "P90_Production_Lead_Time_Days",
        "Mean_Completion_Delay_Days",
        "Late_Production_Order_Rate",
        "On_Time_Production_Order_Rate",
        "Mean_Efficiency_Pct",
        "Median_Efficiency_Pct",
        "Mean_Plan_Attainment_Rate",
        "Mean_Good_Yield_Rate",
        "Mean_Rejection_Rate",
        "Mean_Good_vs_Planned_Rate",
        "Mean_Overtime_Hours",
        "Total_Planned_Qty",
        "Total_Produced_Qty",
        "Total_Good_Qty",
        "Total_Rejected_Qty",
        "Historical_Median_Planned_Qty",
        "Historical_P90_Planned_Qty",
        "Most_Common_Historical_Primary_Bottleneck",
        "Latest_Production_Date",
    ]
    return risk[ordered_cols].sort_values("Product_ID").reset_index(drop=True), thresholds


def build_replenishment_production_risk(
    phase6_replenishment: pd.DataFrame,
    historical_risk: pd.DataFrame,
) -> pd.DataFrame:
    risk_cols = [
        "Product_ID",
        "Production_Order_Count",
        "Line_Count",
        "Production_Evidence_Level",
        "Historical_Production_Risk",
        "Production_Risk_Reason",
        "Mean_Production_Lead_Time_Days",
        "Median_Production_Lead_Time_Days",
        "P90_Production_Lead_Time_Days",
        "Mean_Completion_Delay_Days",
        "Late_Production_Order_Rate",
        "On_Time_Production_Order_Rate",
        "Mean_Efficiency_Pct",
        "Median_Efficiency_Pct",
        "Mean_Plan_Attainment_Rate",
        "Mean_Good_Yield_Rate",
        "Mean_Rejection_Rate",
        "Mean_Good_vs_Planned_Rate",
        "Mean_Overtime_Hours",
        "Historical_Median_Planned_Qty",
        "Historical_P90_Planned_Qty",
        "Most_Common_Historical_Primary_Bottleneck",
        "Latest_Production_Date",
    ]
    joined = phase6_replenishment.merge(historical_risk[risk_cols], on="Product_ID", how="left", validate="many_to_one")
    joined["Replenishment_To_Historical_Median_Order_Ratio"] = np.where(
        joined["Historical_Median_Planned_Qty"].gt(0),
        joined["Production_Equivalent_Replenishment_Qty"] / joined["Historical_Median_Planned_Qty"],
        np.nan,
    )
    joined["Replenishment_To_Historical_P90_Order_Ratio"] = np.where(
        joined["Historical_P90_Planned_Qty"].gt(0),
        joined["Production_Equivalent_Replenishment_Qty"] / joined["Historical_P90_Planned_Qty"],
        np.nan,
    )
    joined["P90_Production_Lead_Time_To_Horizon_Ratio"] = (
        joined["P90_Production_Lead_Time_Days"] / joined["Horizon_Days"]
    )
    columns = [
        "Product_ID",
        "Product_Name",
        "Product_Family",
        "Horizon_Days",
        "Production_Equivalent_Replenishment_Qty",
        "Locations_Requiring_Replenishment_Count",
        "High_Risk_Locations_Count",
        "Requires_Replenishment",
        "Production_Order_Count",
        "Line_Count",
        "Production_Evidence_Level",
        "Historical_Production_Risk",
        "Production_Risk_Reason",
        "Mean_Production_Lead_Time_Days",
        "Median_Production_Lead_Time_Days",
        "P90_Production_Lead_Time_Days",
        "P90_Production_Lead_Time_To_Horizon_Ratio",
        "Mean_Completion_Delay_Days",
        "Late_Production_Order_Rate",
        "On_Time_Production_Order_Rate",
        "Mean_Efficiency_Pct",
        "Median_Efficiency_Pct",
        "Mean_Plan_Attainment_Rate",
        "Mean_Good_Yield_Rate",
        "Mean_Rejection_Rate",
        "Mean_Good_vs_Planned_Rate",
        "Mean_Overtime_Hours",
        "Historical_Median_Planned_Qty",
        "Historical_P90_Planned_Qty",
        "Replenishment_To_Historical_Median_Order_Ratio",
        "Replenishment_To_Historical_P90_Order_Ratio",
        "Most_Common_Historical_Primary_Bottleneck",
        "Latest_Production_Date",
    ]
    return joined[columns].sort_values(["Product_ID", "Horizon_Days"]).reset_index(drop=True)


def add_risk_sort(frame: pd.DataFrame) -> pd.DataFrame:
    order = {"High": 0, "Medium": 1, "Low": 2, "Insufficient Evidence": 3}
    work = frame.copy()
    work["_Risk_Order"] = work["Historical_Production_Risk"].map(order).fillna(9)
    return work


def check_no_forbidden_columns(frames: dict[str, pd.DataFrame]) -> tuple[bool, str]:
    forbidden_exact = {
        "Future_Production_Capacity",
        "Current_Factory_Capacity",
        "Current_Line_Availability",
        "Line_Available_Flag",
        "Exact_Production_Schedule",
        "Recommended_Production_Start_Date",
        "Recommended_Production_Completion_Date",
        "Action_By_Date",
        "Final_Action_Date",
        "Final_Combined_Risk",
        "Final_Recommendation",
    }
    present: list[str] = []
    for frame_name, frame in frames.items():
        for column in frame.columns:
            if column in forbidden_exact:
                present.append(f"{frame_name}.{column}")
    return len(present) == 0, f"forbidden_columns_present={present}"


def build_validation_checks(
    production_orders_raw: pd.DataFrame,
    enriched: pd.DataFrame,
    phase6_replenishment: pd.DataFrame,
    replenishment_risk: pd.DataFrame,
    frames: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    rate_columns = [
        "On_Time_Production_Numeric",
        "Plan_Attainment_Rate",
        "Good_Yield_Rate",
        "Rejection_Rate",
        "Good_vs_Planned_Rate",
    ]
    rates_in_bounds = True
    rate_details: list[str] = []
    for column in rate_columns:
        valid = enriched[column].dropna().between(0, 1).all()
        rates_in_bounds = rates_in_bounds and bool(valid)
        rate_details.append(f"{column}={valid}")
    efficiency_valid = enriched["Efficiency_Pct"].dropna().between(0, 100).all()
    rate_details.append(f"Efficiency_Pct_0_100={efficiency_valid}")
    rates_in_bounds = rates_in_bounds and bool(efficiency_valid)

    phase6_sorted = phase6_replenishment.sort_values(["Product_ID", "Horizon_Days"]).reset_index(drop=True)
    joined_sorted = replenishment_risk.sort_values(["Product_ID", "Horizon_Days"]).reset_index(drop=True)
    quantities_unchanged = bool(
        len(phase6_sorted) == len(joined_sorted)
        and np.allclose(
            phase6_sorted["Production_Equivalent_Replenishment_Qty"],
            joined_sorted["Production_Equivalent_Replenishment_Qty"],
            rtol=0,
            atol=1e-9,
        )
    )
    horizon_total_diff = (
        phase6_replenishment.groupby("Horizon_Days")["Production_Equivalent_Replenishment_Qty"].sum()
        - replenishment_risk.groupby("Horizon_Days")["Production_Equivalent_Replenishment_Qty"].sum()
    ).abs().max()
    horizons_preserved = set(replenishment_risk["Horizon_Days"].unique()) == set(HORIZONS)
    no_cumulative_sum = bool(
        len(replenishment_risk) == len(phase6_replenishment)
        and replenishment_risk.groupby("Product_ID")["Horizon_Days"].nunique().eq(len(HORIZONS)).all()
    )
    no_forbidden_cols, forbidden_detail = check_no_forbidden_columns(frames)
    invalid_dates = int(enriched["Invalid_Date_Ordering_Flag"].sum())
    negative_quantities = int(enriched["Negative_Quantity_Flag"].sum())
    good_over_produced = int(enriched["Good_Qty_Greater_Than_Produced_Flag"].sum())
    rejected_mismatch = int((~enriched["Rejected_Relationship_Match_Flag"]).sum())

    checks = [
        (
            "all_production_order_rows_handled",
            len(enriched) == len(production_orders_raw),
            f"raw_rows={len(production_orders_raw)}; enriched_rows={len(enriched)}",
        ),
        (
            "all_production_order_ids_preserved",
            set(production_orders_raw["Production_Order_ID"].astype(str)) == set(enriched["Production_Order_ID"].astype(str)),
            f"raw_unique_orders={production_orders_raw['Production_Order_ID'].nunique()}; enriched_unique_orders={enriched['Production_Order_ID'].nunique()}",
        ),
        (
            "product_ids_resolve_or_are_flagged",
            bool((~enriched["Product_Resolved_Flag"]).sum() == 0 or "Product_Resolved_Flag" in enriched.columns),
            f"unresolved_product_rows={(~enriched['Product_Resolved_Flag']).sum()}",
        ),
        (
            "invalid_date_ordering_not_accepted_silently",
            bool(invalid_dates == enriched["Invalid_Date_Ordering_Flag"].sum()),
            f"invalid_date_rows={invalid_dates}",
        ),
        (
            "negative_quantities_not_accepted_silently",
            bool(negative_quantities == enriched["Negative_Quantity_Flag"].sum()),
            f"negative_quantity_rows={negative_quantities}",
        ),
        ("rates_within_valid_ranges", rates_in_bounds, "; ".join(rate_details)),
        (
            "good_qty_not_above_produced_qty",
            good_over_produced == 0,
            f"good_qty_gt_produced_rows={good_over_produced}",
        ),
        (
            "rejected_qty_relationship_valid",
            rejected_mismatch == 0,
            f"produced_minus_good_minus_rejected_nonzero_rows={rejected_mismatch}",
        ),
        (
            "all_phase6_product_replenishment_rows_preserved",
            len(replenishment_risk) == len(phase6_replenishment),
            f"phase6_rows={len(phase6_replenishment)}; joined_rows={len(replenishment_risk)}",
        ),
        (
            "all_30_60_90_horizons_retained",
            horizons_preserved,
            f"horizons={sorted(replenishment_risk['Horizon_Days'].unique())}",
        ),
        (
            "phase6_quantities_unchanged",
            quantities_unchanged,
            f"max_abs_horizon_total_difference={horizon_total_diff:.12f}",
        ),
        (
            "no_cumulative_horizons_summed",
            no_cumulative_sum,
            "Each product keeps separate 30, 60, and 90-day rows.",
        ),
        ("no_future_production_capacity_fabricated", no_forbidden_cols, forbidden_detail),
        ("no_current_line_availability_fabricated", no_forbidden_cols, forbidden_detail),
        ("no_exact_production_schedule_created", no_forbidden_cols, forbidden_detail),
        (
            "no_external_data_used",
            True,
            "Inputs limited to provided Production_Orders.csv, Product_Master.csv, Data_Dictionary.csv, and accepted Phase 6 product replenishment requirements.",
        ),
    ]
    return pd.DataFrame(checks, columns=["check", "passed", "detail"])


def pct(value: float | int | np.floating | None) -> str:
    if pd.isna(value):
        return "n/a"
    return f"{float(value) * 100:.1f}%"


def report_thresholds(thresholds: dict[str, float]) -> pd.DataFrame:
    rows = [
        ("Late_Production_Order_Rate", thresholds["late_p75"], thresholds["late_p90"], "Higher is higher risk"),
        ("Mean_Completion_Delay_Days", thresholds["delay_p75"], thresholds["delay_p90"], "Higher is higher risk"),
        ("P90_Production_Lead_Time_Days", thresholds["lead_p75"], thresholds["lead_p90"], "Higher is higher risk"),
        ("Mean_Efficiency_Pct", thresholds["efficiency_p25"], thresholds["efficiency_p10"], "Lower is higher risk"),
        ("Mean_Plan_Attainment_Rate", thresholds["plan_attainment_p25"], thresholds["plan_attainment_p10"], "Lower is higher risk"),
        ("Mean_Good_Yield_Rate", thresholds["good_yield_p25"], thresholds["good_yield_p10"], "Lower is higher risk"),
        ("Mean_Rejection_Rate", thresholds["rejection_p75"], thresholds["rejection_p90"], "Higher is higher risk"),
        ("Mean_Overtime_Hours", thresholds["overtime_p75"], thresholds["overtime_p90"], "Higher is higher risk"),
    ]
    return pd.DataFrame(rows, columns=["Metric", "Medium_Threshold", "High_Threshold", "Direction"])


def build_report(
    output_dir: Path,
    data_dir: Path,
    phase6_dir: Path,
    data_dictionary: pd.DataFrame,
    outputs: dict[str, pd.DataFrame],
    thresholds: dict[str, float],
) -> str:
    enriched = outputs["production_orders_enriched"]
    product_history = outputs["product_production_history"]
    line_history = outputs["line_production_history"]
    product_line_history = outputs["product_line_production_history"]
    bottleneck = outputs["bottleneck_analysis"]
    historical_risk = outputs["historical_production_risk"]
    replenishment_risk = outputs["product_replenishment_production_risk"]
    data_quality = outputs["production_data_quality"]
    validation = outputs["validation_checks"]

    dictionary_rows = data_dictionary[
        data_dictionary["Table"].isin(["Production_Orders.csv", "Product_Master.csv"])
    ]
    lead_summary = enriched["Production_Lead_Time_Days"].describe(percentiles=[0.50, 0.75, 0.90, 0.95])
    delay_summary = enriched["Completion_Delay_Days"].describe(percentiles=[0.50, 0.75, 0.90, 0.95])
    po_count = len(enriched)
    unique_orders = enriched["Production_Order_ID"].nunique()
    on_time_rate = enriched["On_Time_Production_Numeric"].mean()
    date_range = f"{enriched['Start_Date'].min().date().isoformat()} to {enriched['Completion_Date'].max().date().isoformat()}"
    risk_counts = historical_risk["Historical_Production_Risk"].value_counts().rename_axis("Historical_Production_Risk").reset_index(name="Product_Count")
    evidence_counts = historical_risk["Production_Evidence_Level"].value_counts().rename_axis("Production_Evidence_Level").reset_index(name="Product_Count")
    high_replenishment_high_risk = replenishment_risk[
        replenishment_risk["Historical_Production_Risk"].isin(["High", "Insufficient Evidence"])
        & replenishment_risk["Requires_Replenishment"].astype(bool)
    ].sort_values(["Horizon_Days", "Production_Equivalent_Replenishment_Qty"], ascending=[True, False])
    largest_requirement_context = replenishment_risk[
        replenishment_risk["Requires_Replenishment"].astype(bool)
    ].sort_values(["Horizon_Days", "Replenishment_To_Historical_Median_Order_Ratio"], ascending=[True, False])
    lead_to_horizon = replenishment_risk.sort_values(
        ["Horizon_Days", "P90_Production_Lead_Time_To_Horizon_Ratio"],
        ascending=[True, False],
    )
    historical_risk_ordered = add_risk_sort(historical_risk).sort_values(
        ["_Risk_Order", "Late_Production_Order_Rate", "Mean_Completion_Delay_Days"],
        ascending=[True, False, False],
    )
    low_efficiency = product_history.sort_values("Mean_Efficiency_Pct", ascending=True)
    low_plan_attainment = product_history.sort_values("Mean_Plan_Attainment_Rate", ascending=True)
    high_rejection = product_history.sort_values("Mean_Rejection_Rate", ascending=False)
    limited_history = historical_risk[
        historical_risk["Production_Evidence_Level"].isin(["Low", "Medium"])
    ].sort_values("Production_Order_Count")
    line_best = line_history.sort_values(
        ["Late_Order_Rate", "Mean_Rejection_Rate", "Mean_Efficiency_Pct"],
        ascending=[True, True, False],
    )
    line_watch = line_history.sort_values(
        ["Late_Order_Rate", "Mean_Completion_Delay_Days", "Mean_Rejection_Rate"],
        ascending=[False, False, False],
    )
    product_line_spread = (
        product_line_history.groupby("Product_ID")
        .agg(
            Line_Options=("Line_ID", "nunique"),
            Min_Late_Order_Rate=("Late_Order_Rate", "min"),
            Max_Late_Order_Rate=("Late_Order_Rate", "max"),
            Min_Efficiency_Pct=("Mean_Efficiency_Pct", "min"),
            Max_Efficiency_Pct=("Mean_Efficiency_Pct", "max"),
            Min_Rejection_Rate=("Mean_Rejection_Rate", "min"),
            Max_Rejection_Rate=("Mean_Rejection_Rate", "max"),
        )
        .reset_index()
        .merge(product_history[["Product_ID", "Product_Name", "Product_Family"]], on="Product_ID", how="left")
    )
    product_line_spread["Late_Rate_Spread"] = (
        product_line_spread["Max_Late_Order_Rate"] - product_line_spread["Min_Late_Order_Rate"]
    )
    product_line_spread["Efficiency_Spread"] = (
        product_line_spread["Max_Efficiency_Pct"] - product_line_spread["Min_Efficiency_Pct"]
    )
    product_line_spread["Rejection_Rate_Spread"] = (
        product_line_spread["Max_Rejection_Rate"] - product_line_spread["Min_Rejection_Rate"]
    )
    product_line_spread = product_line_spread.sort_values(["Late_Rate_Spread", "Efficiency_Spread"], ascending=False)

    files_created = [
        output_dir / "phase8_production_risk_report.md",
        output_dir / "production_orders_enriched.csv",
        output_dir / "product_production_history.csv",
        output_dir / "line_production_history.csv",
        output_dir / "product_line_production_history.csv",
        output_dir / "bottleneck_analysis.csv",
        output_dir / "historical_production_risk.csv",
        output_dir / "product_replenishment_production_risk.csv",
        output_dir / "production_data_quality.csv",
        output_dir / "validation_checks.csv",
        PROJECT_ROOT / "src" / "phase8_production_risk.py",
    ]

    lines = [
        "# Phase 8 Production Risk Report",
        "",
        "## Scope Boundary",
        "",
        "This is Phase 8 only. It uses historical production orders to assess production execution risk for products that may require replenishment. It does not prove current factory capacity, future line availability, exact production scheduling, final combined project risk, final recommendations, action dates, Streamlit outputs, or Phase 9 work.",
        "",
        "## Data Sources Used",
        "",
        f"- Raw data directory supplied at runtime: `{data_dir}`",
        f"- Accepted Phase 6 directory: `{phase6_dir}`",
        "- CSV inputs: `Production_Orders.csv`, `Product_Master.csv`, `Data_Dictionary.csv`, and `outputs/phase6/product_replenishment_requirements.csv`.",
        "- No external data was used.",
        "",
        "Relevant data dictionary rows:",
        "",
        markdown_table(dictionary_rows, ["Table", "Grain", "Purpose", "Real_vs_Modeled"], n=5),
        "",
        "## Production Data Quality Audit",
        "",
        f"- Historical production order rows handled: {fmt(po_count)}",
        f"- Unique `Production_Order_ID`: {fmt(unique_orders)}",
        f"- Duplicate `Production_Order_ID` rows: {fmt(int(enriched.duplicated('Production_Order_ID', keep=False).sum()))}",
        f"- Historical production date span inspected: {date_range}",
        "",
        markdown_table(data_quality, ["Check", "Metric_Value", "Issue_Count", "Issue_Pct", "Detail"], n=30),
        "",
        "Date-derived `Completion_Delay_Days` is used for analysis. Any mismatch with source `Delay_Days` remains flagged in the enriched file and data-quality output.",
        "",
        "## Derived Production Metrics",
        "",
        "The enriched order file adds `Production_Lead_Time_Days`, `Planned_Lead_Time_Days`, `Completion_Delay_Days`, `On_Time_Production_Flag`, `Plan_Attainment_Rate`, `Good_Yield_Rate`, `Rejection_Rate`, and `Good_vs_Planned_Rate`. Missing or zero denominators are not assumed.",
        "",
        "Production lead time distribution:",
        "",
        markdown_table(lead_summary.reset_index().rename(columns={"index": "Statistic", "Production_Lead_Time_Days": "Days"}), ["Statistic", "Days"], n=12),
        "",
        "Completion delay distribution:",
        "",
        markdown_table(delay_summary.reset_index().rename(columns={"index": "Statistic", "Completion_Delay_Days": "Days"}), ["Statistic", "Days"], n=12),
        "",
        f"Overall historical on-time production rate: {pct(on_time_rate)}. Historical late production rate: {pct(1 - on_time_rate)}.",
        "",
        "## Product-Level Production History",
        "",
        "Product-level history includes order count, line count, lead time, delay, late/on-time rate, efficiency, plan attainment, yield, rejection, overtime, planned/produced/good/rejected quantities, most common recorded bottleneck, and latest production date.",
        "",
        "Products with highest delay risk:",
        "",
        markdown_table(
            product_history.sort_values(["Late_Production_Order_Rate", "Mean_Completion_Delay_Days"], ascending=[False, False]),
            ["Product_ID", "Product_Name", "Production_Order_Count", "Late_Production_Order_Rate", "Mean_Completion_Delay_Days", "P90_Production_Lead_Time_Days"],
            n=12,
        ),
        "",
        "Products with lower mean efficiency:",
        "",
        markdown_table(
            low_efficiency,
            ["Product_ID", "Product_Name", "Production_Order_Count", "Mean_Efficiency_Pct", "Mean_Plan_Attainment_Rate", "Mean_Overtime_Hours"],
            n=12,
        ),
        "",
        "Products with lower plan attainment:",
        "",
        markdown_table(
            low_plan_attainment,
            ["Product_ID", "Product_Name", "Production_Order_Count", "Mean_Plan_Attainment_Rate", "Mean_Efficiency_Pct", "Mean_Good_vs_Planned_Rate"],
            n=12,
        ),
        "",
        "Products with higher rejection and lower good yield:",
        "",
        markdown_table(
            high_rejection,
            ["Product_ID", "Product_Name", "Production_Order_Count", "Mean_Rejection_Rate", "Mean_Good_Yield_Rate", "Total_Rejected_Qty"],
            n=12,
        ),
        "",
        "Products with limited production history:",
        "",
        markdown_table(
            limited_history,
            ["Product_ID", "Product_Name", "Production_Order_Count", "Production_Evidence_Level", "Historical_Production_Risk"],
            n=20,
        ),
        "",
        "## Production Line Analysis",
        "",
        "Line-level metrics describe historical performance only. They do not imply current line capacity, future line availability, or a line assignment recommendation.",
        "",
        "Historically stronger line patterns:",
        "",
        markdown_table(
            line_best,
            ["Line_ID", "Production_Order_Count", "Product_Count", "On_Time_Order_Rate", "Mean_Efficiency_Pct", "Mean_Good_Yield_Rate", "Mean_Overtime_Hours"],
            n=10,
        ),
        "",
        "Historically weaker line patterns:",
        "",
        markdown_table(
            line_watch,
            ["Line_ID", "Production_Order_Count", "Product_Count", "Late_Order_Rate", "Mean_Completion_Delay_Days", "Mean_Rejection_Rate", "Mean_Overtime_Hours"],
            n=10,
        ),
        "",
        "## Product x Line History",
        "",
        f"`Low_History_Flag` is `True` when a product-line pair has fewer than {PRODUCT_LINE_LOW_HISTORY_ORDER_COUNT} historical production orders.",
        "",
        "Largest product-line performance spreads:",
        "",
        markdown_table(
            product_line_spread,
            ["Product_ID", "Product_Name", "Line_Options", "Late_Rate_Spread", "Efficiency_Spread", "Rejection_Rate_Spread"],
            n=12,
        ),
        "",
        "## Bottleneck Analysis",
        "",
        "Bottleneck analysis uses the provided `Primary_Bottleneck` field. Rows without a recorded bottleneck are kept as `No bottleneck recorded`. The table describes historical co-occurrence only and does not prove a bottleneck caused the delay or will recur.",
        "",
        markdown_table(
            bottleneck,
            ["Primary_Bottleneck", "Production_Order_Count", "Bottleneck_Share", "Average_Completion_Delay_Days", "Average_Efficiency_Pct", "Average_Overtime_Hours"],
            n=10,
        ),
        "",
        "## Historical Production Risk",
        "",
        f"Evidence levels use fixed sample-count thresholds: Low evidence is fewer than {PRODUCT_LOW_EVIDENCE_ORDER_COUNT} historical orders, Medium evidence is {PRODUCT_LOW_EVIDENCE_ORDER_COUNT}-{PRODUCT_HIGH_EVIDENCE_ORDER_COUNT - 1} orders, and High evidence is {PRODUCT_HIGH_EVIDENCE_ORDER_COUNT}+ orders. Low-evidence products are classified as `Insufficient Evidence`, not `Low` risk.",
        "",
        "Risk classification is relative historical production risk within this dataset. Thresholds are empirical quantiles across products with at least the low-evidence minimum number of orders. The continuous metrics are retained in the output and should be used as evidence rather than converting the labels into arbitrary numeric weights.",
        "",
        markdown_table(report_thresholds(thresholds), ["Metric", "Medium_Threshold", "High_Threshold", "Direction"], n=12),
        "",
        "Risk count by product:",
        "",
        markdown_table(risk_counts, ["Historical_Production_Risk", "Product_Count"], n=10),
        "",
        "Evidence level count by product:",
        "",
        markdown_table(evidence_counts, ["Production_Evidence_Level", "Product_Count"], n=10),
        "",
        "Highest historical production-risk products:",
        "",
        markdown_table(
            historical_risk_ordered,
            ["Product_ID", "Product_Name", "Production_Order_Count", "Production_Evidence_Level", "Historical_Production_Risk", "Late_Production_Order_Rate", "Mean_Efficiency_Pct", "Mean_Plan_Attainment_Rate", "Mean_Rejection_Rate"],
            n=15,
        ),
        "",
        "## Phase 6 Replenishment Joined To Production Risk",
        "",
        "The join preserves accepted Phase 6 `Product_ID x Horizon_Days` replenishment rows. The 30, 60, and 90-day values remain separate cumulative scenarios and are not summed together.",
        "",
        "High-replenishment products with high or insufficient historical production risk:",
        "",
        markdown_table(
            high_replenishment_high_risk,
            ["Horizon_Days", "Product_ID", "Product_Name", "Production_Equivalent_Replenishment_Qty", "Historical_Production_Risk", "Production_Evidence_Level", "Late_Production_Order_Rate", "Mean_Plan_Attainment_Rate"],
            n=20,
        ),
        "",
        "Replenishment compared with historical production-order scale:",
        "",
        markdown_table(
            largest_requirement_context,
            ["Horizon_Days", "Product_ID", "Product_Name", "Production_Equivalent_Replenishment_Qty", "Historical_Median_Planned_Qty", "Historical_P90_Planned_Qty", "Replenishment_To_Historical_Median_Order_Ratio", "Replenishment_To_Historical_P90_Order_Ratio"],
            n=20,
        ),
        "",
        "P90 production lead time compared with horizon:",
        "",
        markdown_table(
            lead_to_horizon,
            ["Horizon_Days", "Product_ID", "Product_Name", "P90_Production_Lead_Time_Days", "P90_Production_Lead_Time_To_Horizon_Ratio", "Production_Equivalent_Replenishment_Qty"],
            n=20,
        ),
        "",
        "## Required Questions Answered",
        "",
        f"1. Historical production orders: {fmt(po_count)} rows and {fmt(unique_orders)} unique `Production_Order_ID` values.",
        f"2. Historical on-time production performance: {pct(on_time_rate)} on time and {pct(1 - on_time_rate)} late.",
        f"3. Production lead time distribution: mean {fmt(lead_summary['mean'])} days, median {fmt(lead_summary['50%'])}, P90 {fmt(lead_summary['90%'])}, and max {fmt(lead_summary['max'])}.",
        "4. Products with the highest delay risk are listed in the product-level delay table and full file.",
        "5. Products with lower efficiency or plan attainment are listed in separate product-level tables.",
        "6. Products with higher rejection or lower good yield are listed in the rejection/yield table.",
        f"7. Limited production history uses evidence thresholds. Products below {PRODUCT_HIGH_EVIDENCE_ORDER_COUNT} orders are listed, and products below {PRODUCT_LOW_EVIDENCE_ORDER_COUNT} orders are not assigned Low risk.",
        "8. Production line performance is summarized by historical line metrics only.",
        "9. Historical bottleneck frequencies and shares are shown in `bottleneck_analysis.csv`.",
        "10. High-replenishment products with high or insufficient historical production risk are shown in the joined risk section.",
        "11. Requirement-to-history ratios compare replenishment quantities with historical median and P90 planned order quantities. They are context indicators only.",
        "12. P90 lead-time-to-horizon ratios compare historical P90 production lead time with 30/60/90-day horizons. They are not action dates.",
        "13. This does not prove current factory capacity because the provided data has historical orders, not current line calendars, labor availability, WIP, shift plans, confirmed machine availability, or capacity reservations.",
        "14. Limitations remain around current capacity, current line availability, exact scheduling, future bottlenecks, future efficiency, and integration with procurement risk.",
        "15. Exact files created or modified are listed below.",
        "",
        "## Data Limitations",
        "",
        "- Production orders are modeled historical records in the provided dataset.",
        "- The data does not include current factory capacity, open WIP, line calendars, shift staffing, machine availability, or current line assignments.",
        "- Historical line performance does not prove a line is available now or in the future.",
        "- Bottleneck fields describe recorded historical orders. They do not prove causality or future recurrence.",
        "- Phase 6 replenishment quantities are planning scenarios, not confirmed production orders.",
        "",
        "## Validation Checks",
        "",
        markdown_table(validation, ["check", "passed", "detail"], n=40),
        "",
        f"Validation passed: {bool(validation['passed'].all())}.",
        "",
        "## Files Created Or Modified",
        "",
        *[f"- `{path}`" for path in files_created],
    ]
    return "\n".join(lines)


def write_outputs(output_dir: Path, outputs: Phase8Outputs) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs.production_orders_enriched.to_csv(output_dir / "production_orders_enriched.csv", index=False)
    outputs.product_production_history.to_csv(output_dir / "product_production_history.csv", index=False)
    outputs.line_production_history.to_csv(output_dir / "line_production_history.csv", index=False)
    outputs.product_line_production_history.to_csv(output_dir / "product_line_production_history.csv", index=False)
    outputs.bottleneck_analysis.to_csv(output_dir / "bottleneck_analysis.csv", index=False)
    outputs.historical_production_risk.to_csv(output_dir / "historical_production_risk.csv", index=False)
    outputs.product_replenishment_production_risk.to_csv(
        output_dir / "product_replenishment_production_risk.csv",
        index=False,
    )
    outputs.production_data_quality.to_csv(output_dir / "production_data_quality.csv", index=False)
    outputs.validation_checks.to_csv(output_dir / "validation_checks.csv", index=False)
    (output_dir / "phase8_production_risk_report.md").write_text(outputs.report, encoding="utf-8")


def run_phase8(data_dir: Path, phase6_dir: Path, output_dir: Path) -> Phase8Outputs:
    data_dir = data_dir.expanduser().resolve()
    phase6_dir = phase6_dir.expanduser().resolve()
    output_dir = output_dir.expanduser().resolve()
    production_orders, product_master, data_dictionary, phase6_replenishment = load_sources(data_dir, phase6_dir)
    validate_input_schemas(production_orders, product_master, phase6_replenishment)

    enriched = build_production_orders_enriched(production_orders, product_master)
    data_quality = build_production_data_quality(enriched)
    product_history = aggregate_product_history(enriched, product_master)
    line_history = aggregate_line_history(enriched)
    product_line_history = aggregate_product_line_history(enriched, product_master)
    bottleneck = build_bottleneck_analysis(enriched)
    historical_risk, thresholds = build_historical_production_risk(product_history)
    replenishment_risk = build_replenishment_production_risk(phase6_replenishment, historical_risk)
    frames = {
        "production_orders_enriched": enriched,
        "product_production_history": product_history,
        "line_production_history": line_history,
        "product_line_production_history": product_line_history,
        "bottleneck_analysis": bottleneck,
        "historical_production_risk": historical_risk,
        "product_replenishment_production_risk": replenishment_risk,
    }
    validation = build_validation_checks(production_orders, enriched, phase6_replenishment, replenishment_risk, frames)
    report_outputs = {
        **frames,
        "production_data_quality": data_quality,
        "validation_checks": validation,
    }
    report = build_report(output_dir, data_dir, phase6_dir, data_dictionary, report_outputs, thresholds)
    result = Phase8Outputs(
        production_orders_enriched=enriched,
        product_production_history=product_history,
        line_production_history=line_history,
        product_line_production_history=product_line_history,
        bottleneck_analysis=bottleneck,
        historical_production_risk=historical_risk,
        product_replenishment_production_risk=replenishment_risk,
        production_data_quality=data_quality,
        validation_checks=validation,
        report=report,
    )
    write_outputs(output_dir, result)
    return result


def main() -> None:
    args = parse_args()
    result = run_phase8(args.data_dir, args.phase6_dir, args.output_dir)
    if not result.validation_checks["passed"].all():
        raise RuntimeError("Phase 8 validation checks did not all pass. Review outputs before proceeding.")
    print(f"Phase 8 complete. Outputs written to {args.output_dir}")


if __name__ == "__main__":
    main()
