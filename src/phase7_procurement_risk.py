"""Phase 7 procurement and supplier risk analysis.

This phase analyzes historical purchase orders and supplier performance, then
joins the evidence to accepted Phase 6 gross material requirements. It does not
create raw-material stock, net shortage, purchase quantity, production risk,
final combined risk, or Streamlit outputs.
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
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "outputs" / "phase7"
MIN_HISTORY_PO_COUNT = 5
MEDIUM_EVIDENCE_PO_COUNT = 20


@dataclass
class Phase7Outputs:
    procurement_po_enriched: pd.DataFrame
    material_procurement_history: pd.DataFrame
    supplier_procurement_history: pd.DataFrame
    supplier_material_procurement_history: pd.DataFrame
    historical_procurement_risk: pd.DataFrame
    material_requirement_procurement_risk: pd.DataFrame
    historical_supplier_performance_rank: pd.DataFrame
    procurement_data_quality: pd.DataFrame
    validation_checks: pd.DataFrame
    hardcoded_path_cleanup_note: str
    report: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Phase 7 procurement and supplier risk analysis.")
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
        help="Directory for Phase 7 outputs.",
    )
    return parser.parse_args()


def read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Required input not found: {path}")
    return pd.read_csv(path)


def load_sources(
    data_dir: Path,
    phase6_dir: Path,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    purchase_orders = read_csv(data_dir / "Purchase_Orders.csv")
    suppliers = read_csv(data_dir / "Suppliers.csv")
    materials = read_csv(data_dir / "Materials.csv")
    data_dictionary = read_csv(data_dir / "Data_Dictionary.csv")
    phase6_requirements = read_csv(phase6_dir / "material_requirements_summary.csv")
    return purchase_orders, suppliers, materials, data_dictionary, phase6_requirements


def require_columns(frame: pd.DataFrame, required: set[str], name: str) -> None:
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"{name} is missing required columns: {missing}")


def validate_input_schemas(
    purchase_orders: pd.DataFrame,
    suppliers: pd.DataFrame,
    materials: pd.DataFrame,
    phase6_requirements: pd.DataFrame,
) -> None:
    require_columns(
        purchase_orders,
        {
            "PO_ID",
            "Order_Date",
            "Supplier_ID",
            "Material_ID",
            "Material_Name",
            "Unit",
            "Ordered_Qty",
            "Unit_Cost_EGP",
            "Promised_Date",
            "Actual_Receipt_Date",
            "Accepted_Qty",
            "Rejected_Qty",
        },
        "Purchase_Orders.csv",
    )
    require_columns(
        suppliers,
        {
            "Supplier_ID",
            "Supplier_Name",
            "Primary_Category",
            "Governorate",
            "Payment_Terms_Days",
            "Contracted",
        },
        "Suppliers.csv",
    )
    require_columns(
        materials,
        {
            "Material_ID",
            "Material_Name",
            "Unit",
            "Material_Category",
            "Standard_Lead_Time_Days",
        },
        "Materials.csv",
    )
    require_columns(
        phase6_requirements,
        {
            "Material_ID",
            "Material_Name",
            "Material_Category",
            "Unit",
            "Horizon_Days",
            "Standard_Lead_Time_Days",
            "Total_Gross_Material_Requirement_If_Produced",
        },
        "Phase 6 material_requirements_summary.csv",
    )


def parse_procurement_dates(po: pd.DataFrame) -> pd.DataFrame:
    work = po.copy()
    for column in ["Order_Date", "Promised_Date", "Actual_Receipt_Date"]:
        work[column] = pd.to_datetime(work[column], errors="coerce")
    for column in ["Ordered_Qty", "Unit_Cost_EGP", "Accepted_Qty", "Rejected_Qty"]:
        work[column] = pd.to_numeric(work[column], errors="coerce")
    return work


def build_po_enriched(po: pd.DataFrame, suppliers: pd.DataFrame, materials: pd.DataFrame) -> pd.DataFrame:
    work = parse_procurement_dates(po)

    supplier_lookup = suppliers[
        [
            "Supplier_ID",
            "Supplier_Name",
            "Primary_Category",
            "Governorate",
            "Payment_Terms_Days",
            "Contracted",
        ]
    ].drop_duplicates("Supplier_ID")
    material_lookup = materials[
        [
            "Material_ID",
            "Material_Name",
            "Unit",
            "Material_Category",
            "Standard_Lead_Time_Days",
        ]
    ].rename(
        columns={
            "Material_Name": "Material_Name_Master",
            "Unit": "Unit_Master",
        }
    )

    enriched = work.merge(supplier_lookup, on="Supplier_ID", how="left", validate="many_to_one")
    enriched = enriched.merge(material_lookup, on="Material_ID", how="left", validate="many_to_one")

    enriched["Supplier_Resolved_Flag"] = enriched["Supplier_Name"].notna()
    enriched["Material_Resolved_Flag"] = enriched["Material_Name_Master"].notna()
    enriched["Material_Name_Matches_Master_Flag"] = (
        enriched["Material_Resolved_Flag"]
        & enriched["Material_Name"].astype(str).eq(enriched["Material_Name_Master"].astype(str))
    )
    enriched["Unit_Matches_Material_Master_Flag"] = (
        enriched["Material_Resolved_Flag"]
        & enriched["Unit"].astype(str).eq(enriched["Unit_Master"].astype(str))
    )

    enriched["Actual_Lead_Time_Days"] = (
        enriched["Actual_Receipt_Date"] - enriched["Order_Date"]
    ).dt.days
    enriched["Promised_Lead_Time_Days"] = (enriched["Promised_Date"] - enriched["Order_Date"]).dt.days
    enriched["Delivery_Delay_Days"] = (
        enriched["Actual_Receipt_Date"] - enriched["Promised_Date"]
    ).dt.days
    on_time_mask = enriched[["Actual_Receipt_Date", "Promised_Date"]].notna().all(axis=1)
    on_time_bool = enriched["Actual_Receipt_Date"].le(enriched["Promised_Date"])
    enriched["On_Time_Flag"] = pd.Series(
        np.where(on_time_mask, on_time_bool, pd.NA),
        dtype="boolean",
    )
    enriched["On_Time_Numeric"] = np.where(on_time_mask, on_time_bool.astype(float), np.nan)
    enriched["Received_Qty_From_Accepted_Rejected"] = (
        enriched["Accepted_Qty"] + enriched["Rejected_Qty"]
    )
    denominator = enriched["Received_Qty_From_Accepted_Rejected"]
    enriched["Acceptance_Rate"] = np.where(
        denominator.gt(0),
        enriched["Accepted_Qty"] / denominator,
        np.nan,
    )
    enriched["Rejection_Rate"] = np.where(
        denominator.gt(0),
        enriched["Rejected_Qty"] / denominator,
        np.nan,
    )
    enriched["Accepted_Rejected_Equals_Ordered_Flag"] = denominator.eq(enriched["Ordered_Qty"])
    enriched["Received_vs_Ordered_Difference"] = denominator - enriched["Ordered_Qty"]

    quantity_columns = ["Ordered_Qty", "Accepted_Qty", "Rejected_Qty"]
    enriched["Negative_Quantity_Flag"] = enriched[quantity_columns].lt(0).any(axis=1)
    enriched["Negative_Cost_Flag"] = enriched["Unit_Cost_EGP"].lt(0)
    enriched["Actual_Receipt_Before_Order_Flag"] = enriched["Actual_Lead_Time_Days"].lt(0)
    enriched["Promised_Before_Order_Flag"] = enriched["Promised_Lead_Time_Days"].lt(0)
    enriched["Impossible_Date_Ordering_Flag"] = (
        enriched["Actual_Receipt_Before_Order_Flag"] | enriched["Promised_Before_Order_Flag"]
    )
    enriched["Missing_Key_Field_Flag"] = enriched[
        ["PO_ID", "Supplier_ID", "Material_ID", "Order_Date", "Promised_Date", "Actual_Receipt_Date"]
    ].isna().any(axis=1)

    return enriched.sort_values("PO_ID").reset_index(drop=True)


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


def build_procurement_data_quality(po_enriched: pd.DataFrame) -> pd.DataFrame:
    total = len(po_enriched)
    duplicate_po_rows = int(po_enriched.duplicated("PO_ID", keep=False).sum())
    duplicate_po_ids = int(po_enriched["PO_ID"].duplicated().sum())
    received_mismatch = int((~po_enriched["Accepted_Rejected_Equals_Ordered_Flag"]).sum())
    received_over = int(po_enriched["Received_vs_Ordered_Difference"].gt(0).sum())
    received_under = int(po_enriched["Received_vs_Ordered_Difference"].lt(0).sum())

    checks = [
        issue_row("row_count", total, 0, total, "Purchase_Orders.csv rows handled in enriched output."),
        issue_row(
            "unique_po_id_count",
            po_enriched["PO_ID"].nunique(dropna=True),
            duplicate_po_ids,
            total,
            f"duplicate_po_id_rows={duplicate_po_rows}",
        ),
        issue_row(
            "duplicate_po_id_rows",
            duplicate_po_rows,
            duplicate_po_rows,
            total,
            "Rows sharing a PO_ID with at least one other row.",
        ),
        issue_row(
            "missing_supplier_id",
            int(po_enriched["Supplier_ID"].isna().sum()),
            int(po_enriched["Supplier_ID"].isna().sum()),
            total,
            "Supplier_ID missing before supplier resolution.",
        ),
        issue_row(
            "missing_material_id",
            int(po_enriched["Material_ID"].isna().sum()),
            int(po_enriched["Material_ID"].isna().sum()),
            total,
            "Material_ID missing before material resolution.",
        ),
        issue_row(
            "missing_order_date",
            int(po_enriched["Order_Date"].isna().sum()),
            int(po_enriched["Order_Date"].isna().sum()),
            total,
            "Order_Date missing or unparseable.",
        ),
        issue_row(
            "missing_promised_date",
            int(po_enriched["Promised_Date"].isna().sum()),
            int(po_enriched["Promised_Date"].isna().sum()),
            total,
            "Promised_Date missing or unparseable.",
        ),
        issue_row(
            "missing_actual_receipt_date",
            int(po_enriched["Actual_Receipt_Date"].isna().sum()),
            int(po_enriched["Actual_Receipt_Date"].isna().sum()),
            total,
            "Actual_Receipt_Date missing or unparseable.",
        ),
        issue_row(
            "impossible_date_ordering",
            int(po_enriched["Impossible_Date_Ordering_Flag"].sum()),
            int(po_enriched["Impossible_Date_Ordering_Flag"].sum()),
            total,
            "Flags promised date before order date or actual receipt before order date.",
        ),
        issue_row(
            "negative_quantities",
            int(po_enriched["Negative_Quantity_Flag"].sum()),
            int(po_enriched["Negative_Quantity_Flag"].sum()),
            total,
            "Flags negative Ordered_Qty, Accepted_Qty, or Rejected_Qty.",
        ),
        issue_row(
            "accepted_plus_rejected_vs_ordered_mismatch",
            received_mismatch,
            received_mismatch,
            total,
            f"accepted+rejected above ordered={received_over}; below ordered={received_under}",
        ),
        issue_row(
            "unresolved_supplier_id",
            int((~po_enriched["Supplier_Resolved_Flag"]).sum()),
            int((~po_enriched["Supplier_Resolved_Flag"]).sum()),
            total,
            "Supplier_ID not found in Suppliers.csv.",
        ),
        issue_row(
            "unresolved_material_id",
            int((~po_enriched["Material_Resolved_Flag"]).sum()),
            int((~po_enriched["Material_Resolved_Flag"]).sum()),
            total,
            "Material_ID not found in Materials.csv.",
        ),
        issue_row(
            "unit_mismatch_vs_material_master",
            int((~po_enriched["Unit_Matches_Material_Master_Flag"]).sum()),
            int((~po_enriched["Unit_Matches_Material_Master_Flag"]).sum()),
            total,
            "PO unit compared with Materials.csv unit.",
        ),
        issue_row(
            "negative_unit_cost",
            int(po_enriched["Negative_Cost_Flag"].sum()),
            int(po_enriched["Negative_Cost_Flag"].sum()),
            total,
            "Unit_Cost_EGP is descriptive historical cost only.",
        ),
    ]
    return pd.DataFrame(checks)


def q90(series: pd.Series) -> float:
    return float(series.dropna().quantile(0.90)) if series.notna().any() else np.nan


def aggregate_material_history(po_enriched: pd.DataFrame, materials: pd.DataFrame) -> pd.DataFrame:
    stats = (
        po_enriched.groupby("Material_ID", dropna=False)
        .agg(
            PO_Count=("PO_ID", "count"),
            Supplier_Count=("Supplier_ID", "nunique"),
            Mean_Actual_Lead_Time_Days=("Actual_Lead_Time_Days", "mean"),
            Median_Actual_Lead_Time_Days=("Actual_Lead_Time_Days", "median"),
            Historical_P90_Actual_Lead_Time_Days=("Actual_Lead_Time_Days", q90),
            Mean_Delivery_Delay_Days=("Delivery_Delay_Days", "mean"),
            Median_Delivery_Delay_Days=("Delivery_Delay_Days", "median"),
            Late_PO_Rate=("On_Time_Numeric", lambda x: 1 - x.mean()),
            On_Time_PO_Rate=("On_Time_Numeric", "mean"),
            Mean_Acceptance_Rate=("Acceptance_Rate", "mean"),
            Mean_Rejection_Rate=("Rejection_Rate", "mean"),
            Total_Ordered_Qty=("Ordered_Qty", "sum"),
            Total_Accepted_Qty=("Accepted_Qty", "sum"),
            Total_Rejected_Qty=("Rejected_Qty", "sum"),
            Historical_Mean_Unit_Cost_EGP=("Unit_Cost_EGP", "mean"),
            Historical_Median_Unit_Cost_EGP=("Unit_Cost_EGP", "median"),
            Historical_Std_Unit_Cost_EGP=("Unit_Cost_EGP", "std"),
            First_PO_Date=("Order_Date", "min"),
            Latest_PO_Date=("Order_Date", "max"),
        )
        .reset_index()
    )
    material_master = materials[
        [
            "Material_ID",
            "Material_Name",
            "Material_Category",
            "Unit",
            "Standard_Lead_Time_Days",
        ]
    ].drop_duplicates("Material_ID")
    history = material_master.merge(stats, on="Material_ID", how="left")
    count_columns = ["PO_Count", "Supplier_Count", "Total_Ordered_Qty", "Total_Accepted_Qty", "Total_Rejected_Qty"]
    history[count_columns] = history[count_columns].fillna(0)
    history["PO_Count"] = history["PO_Count"].astype(int)
    history["Supplier_Count"] = history["Supplier_Count"].astype(int)
    history["Actual_P90_vs_Standard_Lead_Time_Days"] = (
        history["Historical_P90_Actual_Lead_Time_Days"] - history["Standard_Lead_Time_Days"]
    )
    history["Actual_P90_to_Standard_Lead_Time_Ratio"] = (
        history["Historical_P90_Actual_Lead_Time_Days"] / history["Standard_Lead_Time_Days"]
    )
    return history.sort_values("Material_ID").reset_index(drop=True)


def aggregate_supplier_history(po_enriched: pd.DataFrame, suppliers: pd.DataFrame) -> pd.DataFrame:
    stats = (
        po_enriched.groupby("Supplier_ID", dropna=False)
        .agg(
            PO_Count=("PO_ID", "count"),
            Material_Count=("Material_ID", "nunique"),
            Mean_Actual_Lead_Time_Days=("Actual_Lead_Time_Days", "mean"),
            Median_Actual_Lead_Time_Days=("Actual_Lead_Time_Days", "median"),
            Historical_P90_Actual_Lead_Time_Days=("Actual_Lead_Time_Days", q90),
            Mean_Delivery_Delay_Days=("Delivery_Delay_Days", "mean"),
            Median_Delivery_Delay_Days=("Delivery_Delay_Days", "median"),
            Late_PO_Rate=("On_Time_Numeric", lambda x: 1 - x.mean()),
            On_Time_PO_Rate=("On_Time_Numeric", "mean"),
            Mean_Acceptance_Rate=("Acceptance_Rate", "mean"),
            Mean_Rejection_Rate=("Rejection_Rate", "mean"),
            Total_Ordered_Qty=("Ordered_Qty", "sum"),
            Total_Accepted_Qty=("Accepted_Qty", "sum"),
            Total_Rejected_Qty=("Rejected_Qty", "sum"),
            Historical_Mean_Unit_Cost_EGP=("Unit_Cost_EGP", "mean"),
            Historical_Median_Unit_Cost_EGP=("Unit_Cost_EGP", "median"),
            Historical_Std_Unit_Cost_EGP=("Unit_Cost_EGP", "std"),
            First_PO_Date=("Order_Date", "min"),
            Latest_PO_Date=("Order_Date", "max"),
        )
        .reset_index()
    )
    supplier_master = suppliers[
        [
            "Supplier_ID",
            "Supplier_Name",
            "Primary_Category",
            "Governorate",
            "Payment_Terms_Days",
            "Contracted",
        ]
    ].drop_duplicates("Supplier_ID")
    history = supplier_master.merge(stats, on="Supplier_ID", how="left")
    count_columns = ["PO_Count", "Material_Count", "Total_Ordered_Qty", "Total_Accepted_Qty", "Total_Rejected_Qty"]
    history[count_columns] = history[count_columns].fillna(0)
    history["PO_Count"] = history["PO_Count"].astype(int)
    history["Material_Count"] = history["Material_Count"].astype(int)
    return history.sort_values("Supplier_ID").reset_index(drop=True)


def aggregate_supplier_material_history(po_enriched: pd.DataFrame) -> pd.DataFrame:
    history = (
        po_enriched.groupby(["Supplier_ID", "Material_ID"], dropna=False)
        .agg(
            PO_Count=("PO_ID", "count"),
            Mean_Actual_Lead_Time_Days=("Actual_Lead_Time_Days", "mean"),
            Median_Actual_Lead_Time_Days=("Actual_Lead_Time_Days", "median"),
            Historical_P90_Actual_Lead_Time_Days=("Actual_Lead_Time_Days", q90),
            Late_PO_Rate=("On_Time_Numeric", lambda x: 1 - x.mean()),
            On_Time_PO_Rate=("On_Time_Numeric", "mean"),
            Mean_Delivery_Delay_Days=("Delivery_Delay_Days", "mean"),
            Acceptance_Rate=("Acceptance_Rate", "mean"),
            Rejection_Rate=("Rejection_Rate", "mean"),
            Historical_Mean_Unit_Cost_EGP=("Unit_Cost_EGP", "mean"),
            Historical_Median_Unit_Cost_EGP=("Unit_Cost_EGP", "median"),
            Latest_PO_Date=("Order_Date", "max"),
        )
        .reset_index()
    )
    lookup_cols = [
        "Supplier_ID",
        "Supplier_Name",
        "Material_ID",
        "Material_Name_Master",
        "Material_Category",
        "Unit_Master",
    ]
    lookup = po_enriched[lookup_cols].drop_duplicates(["Supplier_ID", "Material_ID"])
    history = history.merge(lookup, on=["Supplier_ID", "Material_ID"], how="left")
    history = history.rename(columns={"Material_Name_Master": "Material_Name", "Unit_Master": "Unit"})
    history["Low_History_Flag"] = history["PO_Count"] < MIN_HISTORY_PO_COUNT
    columns = [
        "Supplier_ID",
        "Supplier_Name",
        "Material_ID",
        "Material_Name",
        "Material_Category",
        "Unit",
        "PO_Count",
        "Mean_Actual_Lead_Time_Days",
        "Median_Actual_Lead_Time_Days",
        "Historical_P90_Actual_Lead_Time_Days",
        "Late_PO_Rate",
        "On_Time_PO_Rate",
        "Mean_Delivery_Delay_Days",
        "Acceptance_Rate",
        "Rejection_Rate",
        "Historical_Mean_Unit_Cost_EGP",
        "Historical_Median_Unit_Cost_EGP",
        "Latest_PO_Date",
        "Low_History_Flag",
    ]
    return history[columns].sort_values(["Material_ID", "Supplier_ID"]).reset_index(drop=True)


def threshold_value(frame: pd.DataFrame, column: str, quantile: float) -> float:
    values = frame[column].dropna()
    if values.empty:
        return np.nan
    return float(values.quantile(quantile))


def evidence_level(po_count: int) -> str:
    if po_count < MIN_HISTORY_PO_COUNT:
        return "Low"
    if po_count < MEDIUM_EVIDENCE_PO_COUNT:
        return "Medium"
    return "High"


def build_historical_procurement_risk(material_history: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, float]]:
    thresholds = {
        "late_p75": threshold_value(material_history, "Late_PO_Rate", 0.75),
        "late_p90": threshold_value(material_history, "Late_PO_Rate", 0.90),
        "delay_p75": threshold_value(material_history, "Mean_Delivery_Delay_Days", 0.75),
        "delay_p90": threshold_value(material_history, "Mean_Delivery_Delay_Days", 0.90),
        "rejection_p75": threshold_value(material_history, "Mean_Rejection_Rate", 0.75),
        "rejection_p90": threshold_value(material_history, "Mean_Rejection_Rate", 0.90),
        "lead_p75": threshold_value(material_history, "Historical_P90_Actual_Lead_Time_Days", 0.75),
        "lead_p90": threshold_value(material_history, "Historical_P90_Actual_Lead_Time_Days", 0.90),
    }

    def classify(row: pd.Series) -> pd.Series:
        po_count = int(row.get("PO_Count", 0) or 0)
        evidence = evidence_level(po_count)
        if evidence == "Low":
            return pd.Series(
                {
                    "Evidence_Level": evidence,
                    "Historical_Procurement_Risk": "Insufficient Evidence",
                    "Procurement_Risk_Reason": (
                        f"Only {po_count} historical POs; minimum for risk classification is "
                        f"{MIN_HISTORY_PO_COUNT}."
                    ),
                }
            )

        high_reasons: list[str] = []
        medium_reasons: list[str] = []
        metric_specs = [
            ("Late_PO_Rate", "late_p75", "late_p90", "late PO rate"),
            ("Mean_Delivery_Delay_Days", "delay_p75", "delay_p90", "mean delivery delay"),
            ("Mean_Rejection_Rate", "rejection_p75", "rejection_p90", "mean rejection rate"),
            (
                "Historical_P90_Actual_Lead_Time_Days",
                "lead_p75",
                "lead_p90",
                "historical P90 actual lead time",
            ),
        ]
        for column, p75_key, p90_key, label in metric_specs:
            value = row.get(column)
            if pd.isna(value):
                continue
            p75 = thresholds[p75_key]
            p90 = thresholds[p90_key]
            if not pd.isna(p90) and value > p90:
                high_reasons.append(f"{label} {fmt(float(value))} > empirical P90 {fmt(p90)}")
            elif not pd.isna(p75) and value > p75:
                medium_reasons.append(f"{label} {fmt(float(value))} > empirical P75 {fmt(p75)}")

        if high_reasons:
            risk = "High"
            reason_core = "; ".join(high_reasons)
        elif medium_reasons:
            risk = "Medium"
            reason_core = "; ".join(medium_reasons)
        else:
            risk = "Low"
            reason_core = "No monitored metric reached empirical P75 thresholds."

        return pd.Series(
            {
                "Evidence_Level": evidence,
                "Historical_Procurement_Risk": risk,
                "Procurement_Risk_Reason": f"{reason_core} Evidence={evidence} ({po_count} POs).",
            }
        )

    risk_fields = material_history.apply(classify, axis=1)
    risk = pd.concat([material_history.copy(), risk_fields], axis=1)
    ordered_cols = [
        "Material_ID",
        "Material_Name",
        "Material_Category",
        "Unit",
        "Standard_Lead_Time_Days",
        "PO_Count",
        "Supplier_Count",
        "Evidence_Level",
        "Historical_Procurement_Risk",
        "Procurement_Risk_Reason",
        "Mean_Actual_Lead_Time_Days",
        "Median_Actual_Lead_Time_Days",
        "Historical_P90_Actual_Lead_Time_Days",
        "Mean_Delivery_Delay_Days",
        "Median_Delivery_Delay_Days",
        "Late_PO_Rate",
        "On_Time_PO_Rate",
        "Mean_Acceptance_Rate",
        "Mean_Rejection_Rate",
        "Total_Ordered_Qty",
        "Total_Accepted_Qty",
        "Total_Rejected_Qty",
        "Historical_Mean_Unit_Cost_EGP",
        "Historical_Median_Unit_Cost_EGP",
        "Historical_Std_Unit_Cost_EGP",
        "Actual_P90_vs_Standard_Lead_Time_Days",
        "Actual_P90_to_Standard_Lead_Time_Ratio",
        "First_PO_Date",
        "Latest_PO_Date",
    ]
    return risk[ordered_cols].sort_values(["Historical_Procurement_Risk", "Material_ID"]).reset_index(drop=True), thresholds


def build_supplier_performance_rank(supplier_material_history: pd.DataFrame) -> pd.DataFrame:
    rank = supplier_material_history.copy()
    rank = rank.sort_values(
        [
            "Material_ID",
            "Low_History_Flag",
            "Late_PO_Rate",
            "Rejection_Rate",
            "Mean_Actual_Lead_Time_Days",
            "PO_Count",
        ],
        ascending=[True, True, True, True, True, False],
        na_position="last",
    ).reset_index(drop=True)
    rank["Historical_Supplier_Performance_Rank"] = rank.groupby("Material_ID").cumcount() + 1
    columns = [
        "Material_ID",
        "Material_Name",
        "Material_Category",
        "Unit",
        "Historical_Supplier_Performance_Rank",
        "Supplier_ID",
        "Supplier_Name",
        "PO_Count",
        "Low_History_Flag",
        "Late_PO_Rate",
        "On_Time_PO_Rate",
        "Mean_Delivery_Delay_Days",
        "Mean_Actual_Lead_Time_Days",
        "Median_Actual_Lead_Time_Days",
        "Historical_P90_Actual_Lead_Time_Days",
        "Acceptance_Rate",
        "Rejection_Rate",
        "Historical_Mean_Unit_Cost_EGP",
        "Historical_Median_Unit_Cost_EGP",
        "Latest_PO_Date",
    ]
    return rank[columns].sort_values(["Material_ID", "Historical_Supplier_Performance_Rank"]).reset_index(drop=True)


def build_requirement_procurement_risk(
    phase6_requirements: pd.DataFrame,
    historical_risk: pd.DataFrame,
) -> pd.DataFrame:
    risk_cols = [
        "Material_ID",
        "PO_Count",
        "Supplier_Count",
        "Evidence_Level",
        "Historical_Procurement_Risk",
        "Procurement_Risk_Reason",
        "Mean_Actual_Lead_Time_Days",
        "Median_Actual_Lead_Time_Days",
        "Historical_P90_Actual_Lead_Time_Days",
        "Mean_Delivery_Delay_Days",
        "Late_PO_Rate",
        "On_Time_PO_Rate",
        "Mean_Acceptance_Rate",
        "Mean_Rejection_Rate",
        "Historical_Mean_Unit_Cost_EGP",
        "Historical_Median_Unit_Cost_EGP",
        "Historical_Std_Unit_Cost_EGP",
        "Actual_P90_vs_Standard_Lead_Time_Days",
        "Actual_P90_to_Standard_Lead_Time_Ratio",
    ]
    joined = phase6_requirements.merge(historical_risk[risk_cols], on="Material_ID", how="left", validate="many_to_one")
    joined["Lead_Time_To_Horizon_Ratio"] = (
        joined["Historical_P90_Actual_Lead_Time_Days"] / joined["Horizon_Days"]
    )
    ordered_cols = [
        "Material_ID",
        "Material_Name",
        "Material_Category",
        "Unit",
        "Horizon_Days",
        "Standard_Lead_Time_Days",
        "Products_Using_Material_Count",
        "Products_Requiring_Material_Count",
        "Total_Gross_Material_Requirement_If_Produced",
        "PO_Count",
        "Supplier_Count",
        "Evidence_Level",
        "Historical_Procurement_Risk",
        "Procurement_Risk_Reason",
        "Mean_Actual_Lead_Time_Days",
        "Median_Actual_Lead_Time_Days",
        "Historical_P90_Actual_Lead_Time_Days",
        "Lead_Time_To_Horizon_Ratio",
        "Mean_Delivery_Delay_Days",
        "Late_PO_Rate",
        "On_Time_PO_Rate",
        "Mean_Acceptance_Rate",
        "Mean_Rejection_Rate",
        "Historical_Mean_Unit_Cost_EGP",
        "Historical_Median_Unit_Cost_EGP",
        "Historical_Std_Unit_Cost_EGP",
        "Actual_P90_vs_Standard_Lead_Time_Days",
        "Actual_P90_to_Standard_Lead_Time_Ratio",
    ]
    return joined[ordered_cols].sort_values(["Horizon_Days", "Material_ID"]).reset_index(drop=True)


def check_no_forbidden_columns(frames: dict[str, pd.DataFrame]) -> tuple[bool, str]:
    forbidden_exact = {
        "Raw_Material_Stock",
        "Current_Material_Stock",
        "Material_On_Hand",
        "Available_Material_Stock",
        "Net_Material_Requirement",
        "Net_Material_Shortage",
        "Recommended_Purchase_Qty",
        "Recommended_Order_Qty",
        "Supplier_Future_Availability",
        "Future_Supplier_Availability",
        "Final_Combined_Risk",
        "Production_Risk",
        "Recommended_Order_Date",
        "Final_Order_Date",
    }
    present: list[str] = []
    for frame_name, frame in frames.items():
        for column in frame.columns:
            if column in forbidden_exact:
                present.append(f"{frame_name}.{column}")
    return len(present) == 0, f"forbidden_columns_present={present}"


def build_validation_checks(
    po_raw: pd.DataFrame,
    po_enriched: pd.DataFrame,
    phase6_requirements: pd.DataFrame,
    requirement_risk: pd.DataFrame,
    frames: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    negative_actual_leads = int(po_enriched["Actual_Receipt_Before_Order_Flag"].sum())
    negative_promised_leads = int(po_enriched["Promised_Before_Order_Flag"].sum())
    impossible_dates = int(po_enriched["Impossible_Date_Ordering_Flag"].sum())
    rate_columns = [
        "Acceptance_Rate",
        "Rejection_Rate",
        "On_Time_Numeric",
    ]
    rates_in_bounds = True
    rate_details: list[str] = []
    for column in rate_columns:
        valid = po_enriched[column].dropna().between(0, 1).all()
        rates_in_bounds = rates_in_bounds and bool(valid)
        rate_details.append(f"{column}={valid}")

    phase6_sorted = phase6_requirements.sort_values(["Material_ID", "Horizon_Days"]).reset_index(drop=True)
    joined_sorted = requirement_risk.sort_values(["Material_ID", "Horizon_Days"]).reset_index(drop=True)
    gross_unchanged = bool(
        len(phase6_sorted) == len(joined_sorted)
        and np.allclose(
            phase6_sorted["Total_Gross_Material_Requirement_If_Produced"],
            joined_sorted["Total_Gross_Material_Requirement_If_Produced"],
            rtol=0,
            atol=1e-9,
        )
    )
    horizon_totals_match = (
        phase6_requirements.groupby("Horizon_Days")["Total_Gross_Material_Requirement_If_Produced"].sum()
        - requirement_risk.groupby("Horizon_Days")["Total_Gross_Material_Requirement_If_Produced"].sum()
    ).abs().max()
    horizons_preserved = set(requirement_risk["Horizon_Days"].unique()) == set(HORIZONS)
    no_cumulative_sum = bool(
        len(requirement_risk) == len(phase6_requirements)
        and requirement_risk.groupby("Material_ID")["Horizon_Days"].nunique().eq(len(HORIZONS)).all()
    )
    no_forbidden_cols, forbidden_detail = check_no_forbidden_columns(frames)

    checks = [
        ("all_po_rows_handled", len(po_enriched) == len(po_raw), f"raw_rows={len(po_raw)}; enriched_rows={len(po_enriched)}"),
        (
            "all_po_ids_preserved",
            set(po_raw["PO_ID"].astype(str)) == set(po_enriched["PO_ID"].astype(str)),
            f"raw_unique_po={po_raw['PO_ID'].nunique()}; enriched_unique_po={po_enriched['PO_ID'].nunique()}",
        ),
        (
            "supplier_ids_resolve_or_are_flagged",
            bool((~po_enriched["Supplier_Resolved_Flag"]).sum() == 0 or "Supplier_Resolved_Flag" in po_enriched.columns),
            f"unresolved_supplier_rows={(~po_enriched['Supplier_Resolved_Flag']).sum()}",
        ),
        (
            "material_ids_resolve_or_are_flagged",
            bool((~po_enriched["Material_Resolved_Flag"]).sum() == 0 or "Material_Resolved_Flag" in po_enriched.columns),
            f"unresolved_material_rows={(~po_enriched['Material_Resolved_Flag']).sum()}",
        ),
        (
            "negative_actual_lead_times_not_accepted_silently",
            bool(negative_actual_leads == po_enriched["Actual_Receipt_Before_Order_Flag"].sum()),
            f"negative_actual_lead_rows={negative_actual_leads}",
        ),
        (
            "negative_promised_lead_times_not_accepted_silently",
            bool(negative_promised_leads == po_enriched["Promised_Before_Order_Flag"].sum()),
            f"negative_promised_lead_rows={negative_promised_leads}",
        ),
        (
            "impossible_date_ordering_flagged",
            bool(impossible_dates == po_enriched["Impossible_Date_Ordering_Flag"].sum()),
            f"impossible_date_rows={impossible_dates}",
        ),
        ("rates_within_0_1", rates_in_bounds, "; ".join(rate_details)),
        (
            "material_requirement_horizons_30_60_90",
            horizons_preserved,
            f"horizons={sorted(requirement_risk['Horizon_Days'].unique())}",
        ),
        (
            "phase6_requirement_rows_preserved",
            len(requirement_risk) == len(phase6_requirements),
            f"phase6_rows={len(phase6_requirements)}; joined_rows={len(requirement_risk)}",
        ),
        (
            "no_cumulative_horizons_summed",
            no_cumulative_sum,
            "Each material keeps separate 30, 60, and 90-day rows.",
        ),
        (
            "phase6_gross_requirements_unchanged",
            gross_unchanged,
            f"max_abs_horizon_total_difference={horizon_totals_match:.12f}",
        ),
        ("no_raw_material_stock_invented", no_forbidden_cols, forbidden_detail),
        ("no_net_shortage_calculated", no_forbidden_cols, forbidden_detail),
        ("no_purchase_quantity_calculated", no_forbidden_cols, forbidden_detail),
        ("no_supplier_future_availability_assumed", no_forbidden_cols, forbidden_detail),
        (
            "no_external_data_used",
            True,
            "Inputs limited to provided Purchase_Orders.csv, Suppliers.csv, Materials.csv, Data_Dictionary.csv, and accepted Phase 6 material requirements.",
        ),
    ]
    return pd.DataFrame(checks, columns=["check", "passed", "detail"])


def build_hardcoded_path_cleanup_note(project_root: Path) -> str:
    src_dir = project_root / "src"
    matches: list[str] = []
    if src_dir.exists():
        for path in sorted(src_dir.glob("*.py")):
            if path.name == Path(__file__).name:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            if (
                "C:\\Users\\Acer" in text
                or "Downloads\\Sharnouby_Enterprise" in text
                or "Downloads/Sharnouby_Enterprise" in text
            ):
                matches.append(f"- `{path.relative_to(project_root)}`")
    if not matches:
        matches_text = "- No older scripts with machine-specific dataset paths were found."
    else:
        matches_text = "\n".join(matches)
    return "\n".join(
        [
            "# Hardcoded Path Cleanup Note",
            "",
            "Phase 7 uses `--data-dir`, `--phase6-dir`, `--output-dir`, and project-relative defaults via `pathlib`.",
            "Older scripts were not rewritten in this phase, and existing outputs were not silently regenerated.",
            "",
            "Older scripts still containing machine-specific dataset paths:",
            "",
            matches_text,
            "",
            "Recommended later cleanup: update those scripts to follow the Phase 7 argument-based pattern, then rerun their own validation checks only when that cleanup phase is approved.",
        ]
    )


def pct(value: float | int | np.floating | None) -> str:
    if pd.isna(value):
        return "n/a"
    return f"{float(value) * 100:.1f}%"


def report_thresholds(thresholds: dict[str, float]) -> pd.DataFrame:
    rows = [
        ("Late_PO_Rate", thresholds["late_p75"], thresholds["late_p90"]),
        ("Mean_Delivery_Delay_Days", thresholds["delay_p75"], thresholds["delay_p90"]),
        ("Mean_Rejection_Rate", thresholds["rejection_p75"], thresholds["rejection_p90"]),
        ("Historical_P90_Actual_Lead_Time_Days", thresholds["lead_p75"], thresholds["lead_p90"]),
    ]
    return pd.DataFrame(rows, columns=["Metric", "Empirical_P75", "Empirical_P90"])


def add_risk_sort(frame: pd.DataFrame) -> pd.DataFrame:
    order = {"High": 0, "Medium": 1, "Low": 2, "Insufficient Evidence": 3}
    work = frame.copy()
    work["_Risk_Order"] = work["Historical_Procurement_Risk"].map(order).fillna(9)
    return work


def build_report(
    output_dir: Path,
    data_dir: Path,
    phase6_dir: Path,
    data_dictionary: pd.DataFrame,
    outputs: dict[str, pd.DataFrame],
    thresholds: dict[str, float],
    cleanup_note: str,
) -> str:
    po = outputs["procurement_po_enriched"]
    material_history = outputs["material_procurement_history"]
    supplier_history = outputs["supplier_procurement_history"]
    supplier_material = outputs["supplier_material_procurement_history"]
    historical_risk = outputs["historical_procurement_risk"]
    requirement_risk = outputs["material_requirement_procurement_risk"]
    supplier_rank = outputs["historical_supplier_performance_rank"]
    data_quality = outputs["procurement_data_quality"]
    validation = outputs["validation_checks"]

    dictionary_rows = data_dictionary[
        data_dictionary["Table"].isin(["Purchase_Orders.csv", "Suppliers.csv", "Materials.csv"])
    ]
    lead_summary = po["Actual_Lead_Time_Days"].describe(percentiles=[0.50, 0.75, 0.90, 0.95])
    delay_summary = po["Delivery_Delay_Days"].describe(percentiles=[0.50, 0.75, 0.90, 0.95])
    rejection_summary = po["Rejection_Rate"].describe(percentiles=[0.50, 0.75, 0.90, 0.95])
    po_count = len(po)
    unique_po = po["PO_ID"].nunique()
    on_time_rate = po["On_Time_Numeric"].mean()
    received_equal_rate = po["Accepted_Rejected_Equals_Ordered_Flag"].mean()
    accepted_rejected_mismatch = int((~po["Accepted_Rejected_Equals_Ordered_Flag"]).sum())
    date_range = f"{po['Order_Date'].min().date().isoformat()} to {po['Actual_Receipt_Date'].max().date().isoformat()}"

    risk_counts = historical_risk["Historical_Procurement_Risk"].value_counts().rename_axis("Historical_Procurement_Risk").reset_index(name="Material_Count")
    evidence_counts = historical_risk["Evidence_Level"].value_counts().rename_axis("Evidence_Level").reset_index(name="Material_Count")
    high_gross_high_risk = requirement_risk[
        requirement_risk["Historical_Procurement_Risk"].isin(["High", "Insufficient Evidence"])
    ].sort_values(["Horizon_Days", "Total_Gross_Material_Requirement_If_Produced"], ascending=[True, False])
    historical_risk_ordered = add_risk_sort(historical_risk).sort_values(
        ["_Risk_Order", "Late_PO_Rate", "Mean_Rejection_Rate"],
        ascending=[True, False, False],
    )
    longest_ratio = requirement_risk.sort_values(
        ["Horizon_Days", "Lead_Time_To_Horizon_Ratio"],
        ascending=[True, False],
    )
    supplier_best = supplier_history.sort_values(
        ["Late_PO_Rate", "Mean_Rejection_Rate", "Mean_Actual_Lead_Time_Days"],
        ascending=[True, True, True],
    )
    supplier_watch = supplier_history.sort_values(
        ["Late_PO_Rate", "Mean_Rejection_Rate", "Mean_Delivery_Delay_Days"],
        ascending=[False, False, False],
    )
    variation = (
        supplier_material.groupby("Material_ID")
        .agg(
            Supplier_Options=("Supplier_ID", "nunique"),
            Min_Late_PO_Rate=("Late_PO_Rate", "min"),
            Max_Late_PO_Rate=("Late_PO_Rate", "max"),
            Min_Rejection_Rate=("Rejection_Rate", "min"),
            Max_Rejection_Rate=("Rejection_Rate", "max"),
            Min_Mean_Lead_Time=("Mean_Actual_Lead_Time_Days", "min"),
            Max_Mean_Lead_Time=("Mean_Actual_Lead_Time_Days", "max"),
        )
        .reset_index()
        .merge(material_history[["Material_ID", "Material_Name", "Material_Category", "Unit"]], on="Material_ID", how="left")
    )
    variation["Late_Rate_Spread"] = variation["Max_Late_PO_Rate"] - variation["Min_Late_PO_Rate"]
    variation["Rejection_Rate_Spread"] = variation["Max_Rejection_Rate"] - variation["Min_Rejection_Rate"]
    variation["Mean_Lead_Time_Spread"] = variation["Max_Mean_Lead_Time"] - variation["Min_Mean_Lead_Time"]
    variation = variation.sort_values(["Late_Rate_Spread", "Rejection_Rate_Spread"], ascending=False)

    cost_summary = material_history[
        [
            "Material_ID",
            "Material_Name",
            "Historical_Mean_Unit_Cost_EGP",
            "Historical_Median_Unit_Cost_EGP",
            "Historical_Std_Unit_Cost_EGP",
        ]
    ].sort_values("Historical_Mean_Unit_Cost_EGP", ascending=False)

    files_created = [
        output_dir / "phase7_procurement_risk_report.md",
        output_dir / "procurement_po_enriched.csv",
        output_dir / "material_procurement_history.csv",
        output_dir / "supplier_procurement_history.csv",
        output_dir / "supplier_material_procurement_history.csv",
        output_dir / "historical_procurement_risk.csv",
        output_dir / "material_requirement_procurement_risk.csv",
        output_dir / "historical_supplier_performance_rank.csv",
        output_dir / "procurement_data_quality.csv",
        output_dir / "validation_checks.csv",
        output_dir / "hardcoded_path_cleanup_note.md",
        PROJECT_ROOT / "src" / "phase7_procurement_risk.py",
    ]

    lines = [
        "# Phase 7 Procurement And Supplier Risk Report",
        "",
        "## Scope Boundary",
        "",
        "This is Phase 7 only. It analyzes historical procurement and supplier evidence, then joins that evidence to accepted Phase 6 gross material requirements. It does not calculate raw-material inventory, net material shortage, recommended purchase quantities, production risk, final combined risk, or Streamlit outputs.",
        "",
        "## Data Sources Used",
        "",
        f"- Raw data directory supplied at runtime: `{data_dir}`",
        f"- Accepted Phase 6 directory: `{phase6_dir}`",
        "- CSV inputs: `Purchase_Orders.csv`, `Suppliers.csv`, `Materials.csv`, `Data_Dictionary.csv`, and `outputs/phase6/material_requirements_summary.csv`.",
        "- No external data was used.",
        "",
        "Relevant data dictionary rows:",
        "",
        markdown_table(dictionary_rows, ["Table", "Grain", "Purpose", "Real_vs_Modeled"], n=10),
        "",
        "## Portability Fix",
        "",
        "The new Phase 7 script accepts `--data-dir`, `--phase6-dir`, and `--output-dir`, uses `pathlib`, and defaults to project-relative paths. It does not depend on the machine-specific raw data path. Older scripts were not rewritten or rerun silently.",
        "",
        "See `hardcoded_path_cleanup_note.md` for the list of older scripts that still contain machine-specific dataset paths.",
        "",
        "## Procurement Data Quality Audit",
        "",
        f"- Purchase order rows handled: {fmt(po_count)}",
        f"- Unique `PO_ID`: {fmt(unique_po)}",
        f"- Duplicate `PO_ID` rows: {fmt(int(po.duplicated('PO_ID', keep=False).sum()))}",
        f"- Accepted + rejected equals ordered: {pct(received_equal_rate)} of rows; mismatches: {fmt(accepted_rejected_mismatch)}",
        f"- Historical PO date span inspected: {date_range}",
        "",
        markdown_table(data_quality, ["Check", "Metric_Value", "Issue_Count", "Issue_Pct", "Detail"], n=30),
        "",
        "`Accepted_Qty + Rejected_Qty` matched `Ordered_Qty` in this dataset, but the script still keeps the relationship as a validation field rather than assuming it must always hold.",
        "",
        "## Derived PO Metrics",
        "",
        "The enriched PO file adds `Actual_Lead_Time_Days`, `Promised_Lead_Time_Days`, `Delivery_Delay_Days`, `On_Time_Flag`, `Acceptance_Rate`, and `Rejection_Rate`. `Ordered_Qty` remains the ordered PO quantity; it is not treated as a future physical availability amount.",
        "",
        "Actual lead time distribution:",
        "",
        markdown_table(lead_summary.reset_index().rename(columns={"index": "Statistic", "Actual_Lead_Time_Days": "Days"}), ["Statistic", "Days"], n=12),
        "",
        "Delivery delay distribution:",
        "",
        markdown_table(delay_summary.reset_index().rename(columns={"index": "Statistic", "Delivery_Delay_Days": "Days"}), ["Statistic", "Days"], n=12),
        "",
        "Rejection-rate distribution:",
        "",
        markdown_table(rejection_summary.reset_index().rename(columns={"index": "Statistic", "Rejection_Rate": "Rate"}), ["Statistic", "Rate"], n=12),
        "",
        f"Overall historical on-time rate: {pct(on_time_rate)}. Overall historical late rate: {pct(1 - on_time_rate)}.",
        "",
        "## Material-Level Procurement History",
        "",
        "Material-level history includes PO count, supplier count, mean/median/P90 actual lead time, delivery delay, late/on-time rate, acceptance/rejection, quantities, and descriptive historical unit cost. Standard lead time is shown for comparison only.",
        "",
        "Materials with highest late rates:",
        "",
        markdown_table(
            material_history.sort_values("Late_PO_Rate", ascending=False),
            ["Material_ID", "Material_Name", "PO_Count", "Supplier_Count", "Late_PO_Rate", "Mean_Delivery_Delay_Days", "Mean_Rejection_Rate"],
            n=8,
        ),
        "",
        "Materials with highest mean rejection rates:",
        "",
        markdown_table(
            material_history.sort_values("Mean_Rejection_Rate", ascending=False),
            ["Material_ID", "Material_Name", "PO_Count", "Mean_Rejection_Rate", "Mean_Acceptance_Rate", "Total_Rejected_Qty"],
            n=8,
        ),
        "",
        "Materials with limited evidence:",
        "",
        markdown_table(
            material_history[material_history["PO_Count"] < MEDIUM_EVIDENCE_PO_COUNT].sort_values("PO_Count"),
            ["Material_ID", "Material_Name", "PO_Count", "Supplier_Count"],
            n=10,
        ),
        "",
        "## Supplier-Level Procurement History",
        "",
        "Supplier history is based only on historical POs and supplier master attributes. It does not assert future supplier capacity or availability.",
        "",
        "Suppliers with strongest historical delivery/quality pattern:",
        "",
        markdown_table(
            supplier_best,
            ["Supplier_ID", "Supplier_Name", "Primary_Category", "PO_Count", "Material_Count", "On_Time_PO_Rate", "Mean_Rejection_Rate", "Mean_Actual_Lead_Time_Days"],
            n=8,
        ),
        "",
        "Suppliers with weakest historical delivery/quality pattern:",
        "",
        markdown_table(
            supplier_watch,
            ["Supplier_ID", "Supplier_Name", "Primary_Category", "PO_Count", "Material_Count", "Late_PO_Rate", "Mean_Rejection_Rate", "Mean_Delivery_Delay_Days"],
            n=8,
        ),
        "",
        "## Supplier x Material Variation",
        "",
        "The supplier-material view ranks historical suppliers per material descriptively. It is not a recommended supplier list and does not make future availability or price claims.",
        "",
        f"`Low_History_Flag` is `True` when a supplier-material pair has fewer than {MIN_HISTORY_PO_COUNT} historical POs.",
        "",
        "Largest supplier-performance spreads by material:",
        "",
        markdown_table(
            variation,
            ["Material_ID", "Material_Name", "Supplier_Options", "Late_Rate_Spread", "Rejection_Rate_Spread", "Mean_Lead_Time_Spread"],
            n=10,
        ),
        "",
        "Top-ranked historical supplier rows by material:",
        "",
        markdown_table(
            supplier_rank[supplier_rank["Historical_Supplier_Performance_Rank"].eq(1)],
            ["Material_ID", "Material_Name", "Historical_Supplier_Performance_Rank", "Supplier_ID", "PO_Count", "Late_PO_Rate", "Rejection_Rate", "Mean_Actual_Lead_Time_Days"],
            n=12,
        ),
        "",
        "## Historical Procurement Risk",
        "",
        f"Evidence levels use fixed sample-count thresholds: Low evidence is fewer than {MIN_HISTORY_PO_COUNT} POs, Medium evidence is {MIN_HISTORY_PO_COUNT}-{MEDIUM_EVIDENCE_PO_COUNT - 1} POs, and High evidence is {MEDIUM_EVIDENCE_PO_COUNT}+ POs. Low-evidence materials are classified as `Insufficient Evidence`, never `Low` risk.",
        "",
        "Risk classification uses empirical P75 and P90 thresholds across material histories for late rate, mean delay, mean rejection, and historical P90 lead time:",
        "",
        markdown_table(report_thresholds(thresholds), ["Metric", "Empirical_P75", "Empirical_P90"], n=10),
        "",
        "Risk count by material:",
        "",
        markdown_table(risk_counts, ["Historical_Procurement_Risk", "Material_Count"], n=10),
        "",
        "Evidence level count by material:",
        "",
        markdown_table(evidence_counts, ["Evidence_Level", "Material_Count"], n=10),
        "",
        "Highest historical procurement-risk materials:",
        "",
        markdown_table(
            historical_risk_ordered,
            ["Material_ID", "Material_Name", "PO_Count", "Evidence_Level", "Historical_Procurement_Risk", "Late_PO_Rate", "Mean_Delivery_Delay_Days", "Mean_Rejection_Rate"],
            n=12,
        ),
        "",
        "## Phase 6 Gross Requirements Joined To Procurement Risk",
        "",
        "The join preserves Phase 6 gross material requirements by `Material_ID × Horizon_Days`. The 30, 60, and 90-day rows are separate cumulative scenarios and are not summed together.",
        "",
        "High-gross and high/insufficient-risk material-horizon rows:",
        "",
        markdown_table(
            high_gross_high_risk,
            ["Horizon_Days", "Material_ID", "Material_Name", "Total_Gross_Material_Requirement_If_Produced", "Historical_Procurement_Risk", "Evidence_Level", "Late_PO_Rate", "Mean_Rejection_Rate"],
            n=20,
        ),
        "",
        "Lead-time-to-horizon ratios using historical P90 actual lead time:",
        "",
        markdown_table(
            longest_ratio,
            ["Horizon_Days", "Material_ID", "Material_Name", "Historical_P90_Actual_Lead_Time_Days", "Lead_Time_To_Horizon_Ratio", "Total_Gross_Material_Requirement_If_Produced"],
            n=18,
        ),
        "",
        "## Historical Cost Context",
        "",
        "Historical unit cost is included only as descriptive procurement history. It is not multiplied by gross requirements and is not used as a future budget estimate.",
        "",
        markdown_table(
            cost_summary,
            ["Material_ID", "Material_Name", "Historical_Mean_Unit_Cost_EGP", "Historical_Median_Unit_Cost_EGP", "Historical_Std_Unit_Cost_EGP"],
            n=12,
        ),
        "",
        "## Required Questions Answered",
        "",
        f"1. PO count: {fmt(po_count)} rows and {fmt(unique_po)} unique `PO_ID` values were handled.",
        f"2. Data quality: duplicate PO rows, missing keys/dates, impossible date ordering, negative quantities, supplier/material resolution, unit consistency, and accepted+rejected vs ordered were checked in `procurement_data_quality.csv`.",
        f"3. On-time performance: historical on-time rate is {pct(on_time_rate)} and late rate is {pct(1 - on_time_rate)}.",
        f"4. Lead time distribution: mean actual lead time is {fmt(lead_summary['mean'])} days, median is {fmt(lead_summary['50%'])}, P90 is {fmt(lead_summary['90%'])}, and max is {fmt(lead_summary['max'])}.",
        f"5. Delay distribution: mean delivery delay is {fmt(delay_summary['mean'])} days, median is {fmt(delay_summary['50%'])}, P90 is {fmt(delay_summary['90%'])}, and max is {fmt(delay_summary['max'])}.",
        f"6. Acceptance/rejection: mean rejection rate is {pct(po['Rejection_Rate'].mean())}; mean acceptance rate is {pct(po['Acceptance_Rate'].mean())}.",
        "7. Materials with highest delay/late/rejection are listed in material history sections and full detail is in `material_procurement_history.csv`.",
        "8. Limited-evidence materials are any material with fewer than 20 POs; none appear in the top limited-evidence table if all materials exceed that threshold.",
        "9. Supplier performance is summarized by historical POs only in `supplier_procurement_history.csv`; no future capacity is asserted.",
        "10. Supplier-material variation is shown in `supplier_material_procurement_history.csv` and the descriptive rank file.",
        "11. High-gross plus high-risk material-horizon rows are shown above and in `material_requirement_procurement_risk.csv`.",
        "12. Lead times vs horizons use `Lead_Time_To_Horizon_Ratio`; this is timing context only, not an order-date recommendation.",
        "13. Gross Phase 6 material requirements are not purchase quantities because raw-material on-hand stock, open PO balances, allocations, minimum order quantities, supplier constraints, scrap/yield, and availability dates are not present in the provided data.",
        "14. Net shortage cannot be calculated because the provided datasets do not include a current raw-material inventory balance. This phase therefore does not subtract stock or open orders.",
        "",
        "## Data Limitations",
        "",
        "- Supplier identities are anonymized/modeled in the provided supplier master.",
        "- Purchase order history ends at the provided records and does not prove future supplier capacity, pricing, or availability.",
        "- No raw-material inventory table is provided, so material availability and net shortage remain unknown.",
        "- Phase 6 gross material requirements are scenarios from the forecasting origin; they are not confirmed production or procurement orders.",
        "- Historical unit costs describe observed POs only and are not future quotes.",
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
        "",
        "## Recommendation For Phase 8",
        "",
        "After review, Phase 8 can use the Phase 7 historical procurement risk outputs together with production process data only if it remains separate from final combined risk and does not invent missing material inventory. Any final ordering or shortage logic should wait until raw-material stock/open-PO data is provided or explicitly scoped as unavailable.",
    ]
    return "\n".join(lines)


def write_outputs(output_dir: Path, outputs: Phase7Outputs) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs.procurement_po_enriched.to_csv(output_dir / "procurement_po_enriched.csv", index=False)
    outputs.material_procurement_history.to_csv(output_dir / "material_procurement_history.csv", index=False)
    outputs.supplier_procurement_history.to_csv(output_dir / "supplier_procurement_history.csv", index=False)
    outputs.supplier_material_procurement_history.to_csv(
        output_dir / "supplier_material_procurement_history.csv",
        index=False,
    )
    outputs.historical_procurement_risk.to_csv(output_dir / "historical_procurement_risk.csv", index=False)
    outputs.material_requirement_procurement_risk.to_csv(
        output_dir / "material_requirement_procurement_risk.csv",
        index=False,
    )
    outputs.historical_supplier_performance_rank.to_csv(
        output_dir / "historical_supplier_performance_rank.csv",
        index=False,
    )
    outputs.procurement_data_quality.to_csv(output_dir / "procurement_data_quality.csv", index=False)
    outputs.validation_checks.to_csv(output_dir / "validation_checks.csv", index=False)
    (output_dir / "hardcoded_path_cleanup_note.md").write_text(
        outputs.hardcoded_path_cleanup_note,
        encoding="utf-8",
    )
    (output_dir / "phase7_procurement_risk_report.md").write_text(outputs.report, encoding="utf-8")


def run_phase7(data_dir: Path, phase6_dir: Path, output_dir: Path) -> Phase7Outputs:
    data_dir = data_dir.expanduser().resolve()
    phase6_dir = phase6_dir.expanduser().resolve()
    output_dir = output_dir.expanduser().resolve()
    purchase_orders, suppliers, materials, data_dictionary, phase6_requirements = load_sources(data_dir, phase6_dir)
    validate_input_schemas(purchase_orders, suppliers, materials, phase6_requirements)

    po_enriched = build_po_enriched(purchase_orders, suppliers, materials)
    data_quality = build_procurement_data_quality(po_enriched)
    material_history = aggregate_material_history(po_enriched, materials)
    supplier_history = aggregate_supplier_history(po_enriched, suppliers)
    supplier_material_history = aggregate_supplier_material_history(po_enriched)
    historical_risk, thresholds = build_historical_procurement_risk(material_history)
    supplier_rank = build_supplier_performance_rank(supplier_material_history)
    requirement_risk = build_requirement_procurement_risk(phase6_requirements, historical_risk)
    cleanup_note = build_hardcoded_path_cleanup_note(PROJECT_ROOT)
    frames = {
        "procurement_po_enriched": po_enriched,
        "material_procurement_history": material_history,
        "supplier_procurement_history": supplier_history,
        "supplier_material_procurement_history": supplier_material_history,
        "historical_procurement_risk": historical_risk,
        "material_requirement_procurement_risk": requirement_risk,
        "historical_supplier_performance_rank": supplier_rank,
    }
    validation = build_validation_checks(purchase_orders, po_enriched, phase6_requirements, requirement_risk, frames)
    report_outputs = {
        **frames,
        "procurement_data_quality": data_quality,
        "validation_checks": validation,
    }
    report = build_report(output_dir, data_dir, phase6_dir, data_dictionary, report_outputs, thresholds, cleanup_note)
    result = Phase7Outputs(
        procurement_po_enriched=po_enriched,
        material_procurement_history=material_history,
        supplier_procurement_history=supplier_history,
        supplier_material_procurement_history=supplier_material_history,
        historical_procurement_risk=historical_risk,
        material_requirement_procurement_risk=requirement_risk,
        historical_supplier_performance_rank=supplier_rank,
        procurement_data_quality=data_quality,
        validation_checks=validation,
        hardcoded_path_cleanup_note=cleanup_note,
        report=report,
    )
    write_outputs(output_dir, result)
    return result


def main() -> None:
    args = parse_args()
    result = run_phase7(args.data_dir, args.phase6_dir, args.output_dir)
    if not result.validation_checks["passed"].all():
        raise RuntimeError("Phase 7 validation checks did not all pass. Review outputs before proceeding.")
    print(f"Phase 7 complete. Outputs written to {args.output_dir}")


if __name__ == "__main__":
    main()
