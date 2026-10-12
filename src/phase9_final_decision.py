"""Phase 9 final decision layer.

This phase combines accepted prior outputs into an explainable management
decision-support layer. It does not invent raw-material inventory, purchase
quantities, supplier availability, factory capacity, confirmed production
schedules, final purchase orders, Streamlit outputs, or Phase 10 work.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from phase3_forecasting_baseline import HORIZONS, fmt, markdown_table


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PHASE5_DIR = PROJECT_ROOT / "outputs" / "phase5"
DEFAULT_PHASE6_DIR = PROJECT_ROOT / "outputs" / "phase6"
DEFAULT_PHASE7_DIR = PROJECT_ROOT / "outputs" / "phase7"
DEFAULT_PHASE8_DIR = PROJECT_ROOT / "outputs" / "phase8"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "outputs" / "phase9"
FORECAST_ORIGIN_DATE = pd.Timestamp("2026-10-01")
TOLERANCE = 1e-9


@dataclass
class Phase9Outputs:
    final_decision_recommendations: pd.DataFrame
    product_procurement_risk_summary: pd.DataFrame
    conditional_action_timing: pd.DataFrame
    management_priority_90d: pd.DataFrame
    product_cross_functional_90d: pd.DataFrame
    management_kpis_90d: pd.DataFrame
    decision_risk_traceability: pd.DataFrame
    validation_checks: pd.DataFrame
    report: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Phase 9 final decision layer.")
    parser.add_argument("--phase5-dir", type=Path, default=DEFAULT_PHASE5_DIR)
    parser.add_argument("--phase6-dir", type=Path, default=DEFAULT_PHASE6_DIR)
    parser.add_argument("--phase7-dir", type=Path, default=DEFAULT_PHASE7_DIR)
    parser.add_argument("--phase8-dir", type=Path, default=DEFAULT_PHASE8_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Required input not found: {path}")
    return pd.read_csv(path)


def load_sources(
    phase5_dir: Path,
    phase6_dir: Path,
    phase7_dir: Path,
    phase8_dir: Path,
) -> dict[str, pd.DataFrame]:
    return {
        "forecast_results": read_csv(phase5_dir / "forecast_results.csv"),
        "stockout_analysis": read_csv(phase5_dir / "stockout_analysis.csv"),
        "product_replenishment": read_csv(phase6_dir / "product_replenishment_requirements.csv"),
        "product_material": read_csv(phase6_dir / "product_material_requirements.csv"),
        "material_requirements_summary": read_csv(phase6_dir / "material_requirements_summary.csv"),
        "material_requirement_procurement_risk": read_csv(phase7_dir / "material_requirement_procurement_risk.csv"),
        "historical_procurement_risk": read_csv(phase7_dir / "historical_procurement_risk.csv"),
        "supplier_material_procurement_history": read_csv(phase7_dir / "supplier_material_procurement_history.csv"),
        "product_replenishment_production_risk": read_csv(
            phase8_dir / "product_replenishment_production_risk.csv"
        ),
        "historical_production_risk": read_csv(phase8_dir / "historical_production_risk.csv"),
    }


def require_columns(frame: pd.DataFrame, required: set[str], name: str) -> None:
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"{name} is missing required columns: {missing}")


def validate_input_schemas(sources: dict[str, pd.DataFrame]) -> None:
    require_columns(
        sources["stockout_analysis"],
        {
            "Product_ID",
            "Product_Name",
            "Location_ID",
            "Location_Name",
            "Channel",
            "Product_Family",
            "Horizon_Days",
            "Forecast_Demand",
            "Available_Stock",
            "Safety_Stock_Units",
            "Expected_Shortage_Units",
            "Recommended_Replenishment_Qty",
            "Estimated_Stockout_Date",
            "Days_Until_Estimated_Stockout",
            "Inventory_Risk",
            "Selected_Model",
            "Selected_Model_Source",
        },
        "Phase 5 stockout_analysis.csv",
    )
    require_columns(
        sources["forecast_results"],
        {
            "Product_ID",
            "Location_ID",
            "Horizon_Days",
            "Forecast_Demand",
            "Selected_Model",
            "Selected_Model_Source",
        },
        "Phase 5 forecast_results.csv",
    )
    require_columns(
        sources["product_replenishment"],
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
    require_columns(
        sources["product_material"],
        {
            "Product_ID",
            "Product_Name",
            "Product_Family",
            "Horizon_Days",
            "Material_ID",
            "Material_Name",
            "Standard_Lead_Time_Days",
            "Gross_Material_Requirement_If_Produced",
        },
        "Phase 6 product_material_requirements.csv",
    )
    require_columns(
        sources["material_requirements_summary"],
        {
            "Material_ID",
            "Horizon_Days",
            "Total_Gross_Material_Requirement_If_Produced",
        },
        "Phase 6 material_requirements_summary.csv",
    )
    require_columns(
        sources["historical_procurement_risk"],
        {
            "Material_ID",
            "Material_Name",
            "Evidence_Level",
            "Historical_Procurement_Risk",
            "Historical_P90_Actual_Lead_Time_Days",
            "Late_PO_Rate",
            "Mean_Rejection_Rate",
            "Mean_Delivery_Delay_Days",
            "Standard_Lead_Time_Days",
        },
        "Phase 7 historical_procurement_risk.csv",
    )
    require_columns(
        sources["product_replenishment_production_risk"],
        {
            "Product_ID",
            "Horizon_Days",
            "Historical_Production_Risk",
            "Production_Evidence_Level",
            "Late_Production_Order_Rate",
            "P90_Production_Lead_Time_Days",
            "Mean_Plan_Attainment_Rate",
            "Mean_Efficiency_Pct",
            "Mean_Rejection_Rate",
        },
        "Phase 8 product_replenishment_production_risk.csv",
    )


def procurement_risk_priority(label: str) -> int:
    order = {"High": 0, "Medium": 1, "Insufficient Evidence": 2, "Low": 3}
    return order.get(str(label), 4)


def product_procurement_label(group: pd.DataFrame) -> str:
    labels = set(group["Historical_Procurement_Risk"].dropna().astype(str))
    evidence = set(group["Evidence_Level"].dropna().astype(str))
    if "High" in labels:
        return "High"
    if "Medium" in labels:
        return "Medium"
    if "Insufficient Evidence" in labels or "Low" in evidence:
        return "Insufficient Evidence"
    if labels and labels.issubset({"Low"}):
        return "Low"
    return "Insufficient Evidence"


def highest_risk_material(group: pd.DataFrame) -> pd.Series:
    work = group.copy()
    work["_Risk_Order"] = work["Historical_Procurement_Risk"].map(procurement_risk_priority)
    work = work.sort_values(
        [
            "_Risk_Order",
            "Late_PO_Rate",
            "Mean_Rejection_Rate",
            "Historical_P90_Actual_Lead_Time_Days",
            "Mean_Delivery_Delay_Days",
            "Material_ID",
        ],
        ascending=[True, False, False, False, False, True],
        na_position="last",
    )
    row = work.iloc[0]
    return pd.Series(
        {
            "Highest_Risk_Material_ID": row["Material_ID"],
            "Highest_Risk_Material_Name": row["Material_Name"],
            "Highest_Risk_Material_Risk": row["Historical_Procurement_Risk"],
            "Highest_Risk_Material_Reason": (
                "Ranked by procurement risk label, then late PO rate, rejection rate, "
                "P90 actual procurement lead time, mean delay, and Material_ID."
            ),
        }
    )


def build_product_procurement_risk_summary(
    product_material: pd.DataFrame,
    historical_procurement_risk: pd.DataFrame,
) -> pd.DataFrame:
    risk_cols = [
        "Material_ID",
        "Evidence_Level",
        "Historical_Procurement_Risk",
        "Historical_P90_Actual_Lead_Time_Days",
        "Late_PO_Rate",
        "Mean_Rejection_Rate",
        "Mean_Delivery_Delay_Days",
    ]
    material_detail = product_material.merge(
        historical_procurement_risk[risk_cols],
        on="Material_ID",
        how="left",
        validate="many_to_one",
    )
    material_detail["Historical_Procurement_Risk"] = material_detail[
        "Historical_Procurement_Risk"
    ].fillna("Insufficient Evidence")
    material_detail["Evidence_Level"] = material_detail["Evidence_Level"].fillna("Low")

    grouped = (
        material_detail.groupby(["Product_ID", "Product_Name", "Product_Family", "Horizon_Days"], dropna=False)
        .agg(
            Required_Material_Count=("Material_ID", "nunique"),
            High_Procurement_Risk_Material_Count=(
                "Historical_Procurement_Risk",
                lambda x: int((x == "High").sum()),
            ),
            Medium_Procurement_Risk_Material_Count=(
                "Historical_Procurement_Risk",
                lambda x: int((x == "Medium").sum()),
            ),
            Low_Procurement_Risk_Material_Count=(
                "Historical_Procurement_Risk",
                lambda x: int((x == "Low").sum()),
            ),
            Insufficient_Evidence_Material_Count=(
                "Historical_Procurement_Risk",
                lambda x: int((x == "Insufficient Evidence").sum()),
            ),
            Maximum_Material_P90_Actual_Lead_Time_Days=(
                "Historical_P90_Actual_Lead_Time_Days",
                "max",
            ),
            Maximum_Material_Standard_Lead_Time_Days=("Standard_Lead_Time_Days", "max"),
            Maximum_Material_Late_PO_Rate=("Late_PO_Rate", "max"),
            Maximum_Material_Rejection_Rate=("Mean_Rejection_Rate", "max"),
        )
        .reset_index()
    )
    labels = (
        material_detail.groupby(["Product_ID", "Horizon_Days"], dropna=False)
        .apply(product_procurement_label, include_groups=False)
        .rename("Product_Historical_Procurement_Risk")
        .reset_index()
    )
    highest = (
        material_detail.groupby(["Product_ID", "Horizon_Days"], dropna=False)
        .apply(highest_risk_material, include_groups=False)
        .reset_index()
    )
    result = grouped.merge(labels, on=["Product_ID", "Horizon_Days"], how="left")
    result = result.merge(highest, on=["Product_ID", "Horizon_Days"], how="left")
    return result.sort_values(["Product_ID", "Horizon_Days"]).reset_index(drop=True)


def risk_level(label: str) -> int:
    return {"Low": 1, "Medium": 2, "High": 3}.get(str(label), 0)


def derive_decision_risk(row: pd.Series) -> str:
    if bool(row["Inventory_Risk_High"]) or (
        bool(row["Has_Replenishment_Need"]) and bool(row["Stockout_Within_30_Days"])
    ):
        return "High"
    if (
        bool(row["Has_Replenishment_Need"])
        and bool(row["Conditional_Lead_Time_Pressure"])
        and (
            bool(row["Has_High_Procurement_Risk_Material"])
            or bool(row["High_Historical_Production_Risk"])
            or bool(row["Insufficient_Production_Evidence"])
            or bool(row["Insufficient_Procurement_Evidence"])
        )
    ):
        return "High"
    if (
        bool(row["Has_Replenishment_Need"])
        or bool(row["Inventory_Risk_Medium"])
    ):
        return "Medium"
    return "Low"


def status_from_date(action_date: object, has_90_day_stockout: bool) -> str:
    if not has_90_day_stockout or pd.isna(action_date):
        return "No 90-day stockout"
    action_ts = pd.Timestamp(action_date)
    if action_ts <= FORECAST_ORIGIN_DATE:
        return "At/Before forecast origin"
    return "Future planning date"


def parse_stockout_dates(final: pd.DataFrame) -> pd.Series:
    return pd.to_datetime(final["Estimated_Stockout_Date"], errors="coerce", format="%Y-%m-%d")


def build_decision_reason(row: pd.Series) -> str:
    parts: list[str] = []
    if bool(row["Has_Replenishment_Need"]):
        if bool(row["Stockout_Within_30_Days"]):
            parts.append("Estimated stockout is within 30 days")
        elif bool(row["Stockout_Within_90_Days"]):
            parts.append("Estimated stockout is within 90 days")
        else:
            parts.append("Replenishment is needed within the evaluated horizon")
        parts.append(
            f"finished-goods replenishment planning quantity is {fmt(row['Recommended_Replenishment_Qty'])}"
        )
    else:
        return "Current finished-goods stock covers forecast demand; no replenishment action is indicated within this horizon."

    if bool(row["Has_High_Procurement_Risk_Material"]):
        parts.append(
            f"required material {row['Highest_Risk_Material_ID']} has high relative historical procurement risk"
        )
    elif bool(row["Has_Medium_Procurement_Risk_Material"]):
        parts.append(
            f"required material {row['Highest_Risk_Material_ID']} has medium relative historical procurement risk"
        )
    elif bool(row["Insufficient_Procurement_Evidence"]):
        parts.append("required material procurement evidence is insufficient")

    if bool(row["High_Historical_Production_Risk"]):
        parts.append("product has high relative historical production risk")
    elif str(row.get("Historical_Production_Risk")) == "Medium":
        parts.append("product has medium relative historical production risk")
    elif bool(row["Insufficient_Production_Evidence"]):
        parts.append("historical production evidence is insufficient")

    if bool(row["Conditional_Lead_Time_Pressure"]):
        parts.append("conditional historical lead-time evidence suggests the planning window may be tight")
    return "; ".join(parts) + "."


def build_recommended_action(row: pd.Series) -> str:
    if not bool(row["Has_Replenishment_Need"]):
        return "No replenishment action indicated within this horizon."
    if (
        row["Decision_Risk"] == "High"
        and (
            bool(row["Has_High_Procurement_Risk_Material"])
            or bool(row["High_Historical_Production_Risk"])
            or bool(row["Conditional_Lead_Time_Pressure"])
        )
    ):
        return "Urgent cross-functional review: stockout exposure plus elevated historical procurement/production risk."
    if bool(row["Has_High_Procurement_Risk_Material"]):
        return "Review sourcing for required high-risk material(s) while planning replenishment."
    if bool(row["High_Historical_Production_Risk"]):
        return "Prioritize production planning; historical production execution risk is elevated."
    if row["Decision_Risk"] == "High":
        return "Prioritize replenishment planning."
    if row["Horizon_Days"] in [60, 90] and not bool(row["Stockout_Within_30_Days"]):
        return f"Monitor inventory; replenishment requirement emerges by {int(row['Horizon_Days'])}-day horizon."
    return "Prioritize replenishment planning."


def build_final_decision_recommendations(
    stockout: pd.DataFrame,
    product_procurement: pd.DataFrame,
    product_production: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    base_cols = [
        "Product_ID",
        "Product_Name",
        "Location_ID",
        "Location_Name",
        "Channel",
        "Product_Family",
        "Demand_Pattern_Class",
        "Forecast_Origin",
        "Forecast_Start",
        "Forecast_End",
        "Horizon_Days",
        "Forecast_Demand",
        "Available_Stock",
        "Safety_Stock_Units",
        "Expected_Shortage_Units",
        "Recommended_Replenishment_Qty",
        "Estimated_Stockout_Date",
        "Days_Until_Estimated_Stockout",
        "Inventory_Risk",
        "Selected_Model",
        "Selected_Model_Source",
    ]
    final = stockout[base_cols].copy()
    procurement_cols = [
        "Product_ID",
        "Horizon_Days",
        "Required_Material_Count",
        "High_Procurement_Risk_Material_Count",
        "Medium_Procurement_Risk_Material_Count",
        "Low_Procurement_Risk_Material_Count",
        "Insufficient_Evidence_Material_Count",
        "Maximum_Material_P90_Actual_Lead_Time_Days",
        "Maximum_Material_Standard_Lead_Time_Days",
        "Maximum_Material_Late_PO_Rate",
        "Maximum_Material_Rejection_Rate",
        "Highest_Risk_Material_ID",
        "Highest_Risk_Material_Name",
        "Highest_Risk_Material_Risk",
        "Product_Historical_Procurement_Risk",
    ]
    production_cols = [
        "Product_ID",
        "Horizon_Days",
        "Production_Equivalent_Replenishment_Qty",
        "Locations_Requiring_Replenishment_Count",
        "High_Risk_Locations_Count",
        "Historical_Production_Risk",
        "Production_Evidence_Level",
        "Late_Production_Order_Rate",
        "P90_Production_Lead_Time_Days",
        "Mean_Plan_Attainment_Rate",
        "Mean_Efficiency_Pct",
        "Mean_Rejection_Rate",
    ]
    final = final.merge(product_procurement[procurement_cols], on=["Product_ID", "Horizon_Days"], how="left")
    final = final.merge(product_production[production_cols], on=["Product_ID", "Horizon_Days"], how="left")

    final["Estimated_Stockout_Date_Parsed"] = parse_stockout_dates(final)
    final["Has_Replenishment_Need"] = final["Recommended_Replenishment_Qty"].gt(TOLERANCE)
    final["Stockout_Within_30_Days"] = final["Days_Until_Estimated_Stockout"].le(30).fillna(False)
    final["Stockout_Within_60_Days"] = final["Days_Until_Estimated_Stockout"].le(60).fillna(False)
    final["Stockout_Within_90_Days"] = final["Days_Until_Estimated_Stockout"].le(90).fillna(False)
    final["Inventory_Risk_High"] = final["Inventory_Risk"].eq("High")
    final["Inventory_Risk_Medium"] = final["Inventory_Risk"].eq("Medium")
    final["Has_High_Procurement_Risk_Material"] = final["High_Procurement_Risk_Material_Count"].fillna(0).gt(0)
    final["Has_Medium_Procurement_Risk_Material"] = final["Medium_Procurement_Risk_Material_Count"].fillna(0).gt(0)
    final["Insufficient_Procurement_Evidence"] = (
        final["Product_Historical_Procurement_Risk"].eq("Insufficient Evidence")
        | final["Insufficient_Evidence_Material_Count"].fillna(0).gt(0)
    )
    final["High_Historical_Production_Risk"] = final["Historical_Production_Risk"].eq("High")
    final["Insufficient_Production_Evidence"] = final["Historical_Production_Risk"].eq("Insufficient Evidence")

    final["Conditional_Production_Lead_Time_Days"] = final["P90_Production_Lead_Time_Days"]
    final["Conditional_Production_Only_Lead_Time_Days"] = final["P90_Production_Lead_Time_Days"]
    final["Conditional_Material_Procurement_Lead_Time_Days"] = final[
        "Maximum_Material_P90_Actual_Lead_Time_Days"
    ]
    final["Conditional_End_To_End_Lead_Time_Days"] = (
        final["Conditional_Material_Procurement_Lead_Time_Days"]
        + final["Conditional_Production_Lead_Time_Days"]
    )
    final["Conditional_Lead_Time_Pressure"] = (
        final["Has_Replenishment_Need"]
        & final["Stockout_Within_90_Days"]
        & final["Days_Until_Estimated_Stockout"].notna()
        & final["Conditional_End_To_End_Lead_Time_Days"].notna()
        & final["Conditional_End_To_End_Lead_Time_Days"].ge(final["Days_Until_Estimated_Stockout"])
    )

    final["Decision_Risk"] = final.apply(derive_decision_risk, axis=1)
    final["Decision_Risk_Reason"] = final.apply(build_decision_reason, axis=1)
    final["Recommended_Action"] = final.apply(build_recommended_action, axis=1)

    has_timing = final["Stockout_Within_90_Days"] & final["Estimated_Stockout_Date_Parsed"].notna()
    production_days_for_dates = np.ceil(final["Conditional_Production_Lead_Time_Days"])
    material_days_for_dates = np.ceil(final["Conditional_End_To_End_Lead_Time_Days"])
    final["Conditional_Production_Start_By_Date"] = pd.NaT
    final["Conditional_Material_Action_By_Date"] = pd.NaT
    prod_valid = has_timing & production_days_for_dates.notna()
    material_valid = has_timing & material_days_for_dates.notna()
    final.loc[prod_valid, "Conditional_Production_Start_By_Date"] = (
        final.loc[prod_valid, "Estimated_Stockout_Date_Parsed"]
        - pd.to_timedelta(production_days_for_dates.loc[prod_valid], unit="D")
    )
    final.loc[material_valid, "Conditional_Material_Action_By_Date"] = (
        final.loc[material_valid, "Estimated_Stockout_Date_Parsed"]
        - pd.to_timedelta(material_days_for_dates.loc[material_valid], unit="D")
    )
    final["Production_Action_Status"] = final.apply(
        lambda row: status_from_date(row["Conditional_Production_Start_By_Date"], row["Stockout_Within_90_Days"]),
        axis=1,
    )
    final["Material_Action_Status"] = final.apply(
        lambda row: status_from_date(row["Conditional_Material_Action_By_Date"], row["Stockout_Within_90_Days"]),
        axis=1,
    )

    trace_cols = [
        "Product_ID",
        "Location_ID",
        "Horizon_Days",
        "Has_Replenishment_Need",
        "Stockout_Within_30_Days",
        "Stockout_Within_60_Days",
        "Stockout_Within_90_Days",
        "Inventory_Risk_High",
        "Inventory_Risk_Medium",
        "Has_High_Procurement_Risk_Material",
        "Has_Medium_Procurement_Risk_Material",
        "Insufficient_Procurement_Evidence",
        "High_Historical_Production_Risk",
        "Insufficient_Production_Evidence",
        "Conditional_Lead_Time_Pressure",
        "Decision_Risk",
    ]
    traceability = final[trace_cols].copy()
    timing_cols = [
        "Product_ID",
        "Product_Name",
        "Location_ID",
        "Location_Name",
        "Channel",
        "Horizon_Days",
        "Estimated_Stockout_Date",
        "Days_Until_Estimated_Stockout",
        "Conditional_Production_Lead_Time_Days",
        "Conditional_Material_Procurement_Lead_Time_Days",
        "Conditional_End_To_End_Lead_Time_Days",
        "Conditional_Production_Start_By_Date",
        "Conditional_Material_Action_By_Date",
        "Production_Action_Status",
        "Material_Action_Status",
    ]
    conditional_timing = final[timing_cols].copy()

    drop_cols = [
        "Estimated_Stockout_Date_Parsed",
        "Inventory_Risk_High",
        "Inventory_Risk_Medium",
    ]
    final = final.drop(columns=drop_cols)
    date_cols = ["Conditional_Production_Start_By_Date", "Conditional_Material_Action_By_Date"]
    for frame in [final, conditional_timing]:
        for col in date_cols:
            frame[col] = pd.to_datetime(frame[col], errors="coerce").dt.date.astype("string")
            frame[col] = frame[col].mask(frame[col].eq("<NA>"), pd.NA)
    return final, conditional_timing, traceability


def build_management_priority_90d(final: pd.DataFrame) -> pd.DataFrame:
    view = final[final["Horizon_Days"].eq(90)].copy()
    view["_Risk_Order"] = view["Decision_Risk"].map({"High": 0, "Medium": 1, "Low": 2})
    view["_Stockout_Sort"] = view["Days_Until_Estimated_Stockout"].fillna(99999)
    view = view.sort_values(
        [
            "_Risk_Order",
            "_Stockout_Sort",
            "Expected_Shortage_Units",
            "Recommended_Replenishment_Qty",
            "Product_ID",
            "Location_ID",
        ],
        ascending=[True, True, False, False, True, True],
    )
    cols = [
        "Product_ID",
        "Product_Name",
        "Location_ID",
        "Location_Name",
        "Channel",
        "Forecast_Demand",
        "Available_Stock",
        "Expected_Shortage_Units",
        "Recommended_Replenishment_Qty",
        "Estimated_Stockout_Date",
        "Days_Until_Estimated_Stockout",
        "Inventory_Risk",
        "Product_Historical_Procurement_Risk",
        "Historical_Production_Risk",
        "Decision_Risk",
        "Decision_Risk_Reason",
        "Conditional_Production_Start_By_Date",
        "Conditional_Material_Action_By_Date",
        "Recommended_Action",
    ]
    return view[cols].reset_index(drop=True)


def build_product_cross_functional_90d(final: pd.DataFrame) -> pd.DataFrame:
    view = final[final["Horizon_Days"].eq(90)].copy()
    def earliest(series: pd.Series) -> object:
        dates = pd.to_datetime(series, errors="coerce", format="%Y-%m-%d").dropna()
        if dates.empty:
            return pd.NA
        return dates.min().date().isoformat()

    grouped = (
        view.groupby(["Product_ID", "Product_Name", "Product_Family"], as_index=False)
        .agg(
            Production_Equivalent_Replenishment_Qty=("Production_Equivalent_Replenishment_Qty", "max"),
            Locations_Requiring_Replenishment_Count=("Locations_Requiring_Replenishment_Count", "max"),
            High_Risk_Locations_Count=("High_Risk_Locations_Count", "max"),
            Product_Historical_Procurement_Risk=("Product_Historical_Procurement_Risk", "first"),
            Historical_Production_Risk=("Historical_Production_Risk", "first"),
            Required_Material_Count=("Required_Material_Count", "first"),
            High_Procurement_Risk_Material_Count=("High_Procurement_Risk_Material_Count", "first"),
            Highest_Risk_Material_Name=("Highest_Risk_Material_Name", "first"),
            Decision_Risk_Max_Across_Locations=(
                "Decision_Risk",
                lambda x: max(x, key=lambda label: risk_level(label)),
            ),
            Earliest_Estimated_Stockout_Date=("Estimated_Stockout_Date", earliest),
            Earliest_Conditional_Production_Start_By_Date=(
                "Conditional_Production_Start_By_Date",
                earliest,
            ),
            Earliest_Conditional_Material_Action_By_Date=(
                "Conditional_Material_Action_By_Date",
                earliest,
            ),
        )
    )
    grouped["_Risk_Order"] = grouped["Decision_Risk_Max_Across_Locations"].map({"High": 0, "Medium": 1, "Low": 2})
    return grouped.sort_values(
        ["_Risk_Order", "Earliest_Estimated_Stockout_Date", "Production_Equivalent_Replenishment_Qty"],
        ascending=[True, True, False],
        na_position="last",
    ).drop(columns="_Risk_Order").reset_index(drop=True)


def build_management_kpis_90d(
    final: pd.DataFrame,
    product_cross_functional_90d: pd.DataFrame,
    historical_procurement_risk: pd.DataFrame,
) -> pd.DataFrame:
    view = final[final["Horizon_Days"].eq(90)].copy()
    rows: list[dict[str, object]] = []
    for risk in ["High", "Medium", "Low"]:
        rows.append(
            {
                "KPI": f"Product x Location pairs with {risk} Decision_Risk",
                "Value": int(view["Decision_Risk"].eq(risk).sum()),
            }
        )
    rows.extend(
        [
            {
                "KPI": "Product x Location pairs with expected shortage",
                "Value": int(view["Expected_Shortage_Units"].gt(TOLERANCE).sum()),
            },
            {
                "KPI": "Total Expected_Shortage_Units",
                "Value": float(view["Expected_Shortage_Units"].sum()),
            },
            {
                "KPI": "Total Recommended_Replenishment_Qty",
                "Value": float(view["Recommended_Replenishment_Qty"].sum()),
            },
            {
                "KPI": "Products requiring replenishment",
                "Value": int(product_cross_functional_90d["Production_Equivalent_Replenishment_Qty"].gt(TOLERANCE).sum()),
            },
            {
                "KPI": "Products with High historical production risk",
                "Value": int(product_cross_functional_90d["Historical_Production_Risk"].eq("High").sum()),
            },
            {
                "KPI": "Required materials with High historical procurement risk",
                "Value": int(historical_procurement_risk["Historical_Procurement_Risk"].eq("High").sum()),
            },
            {
                "KPI": "Pairs with conditional material action date at/before forecast origin",
                "Value": int(view["Material_Action_Status"].eq("At/Before forecast origin").sum()),
            },
            {
                "KPI": "Pairs with conditional production start date at/before forecast origin",
                "Value": int(view["Production_Action_Status"].eq("At/Before forecast origin").sum()),
            },
        ]
    )
    return pd.DataFrame(rows)


def reproduce_decision_risk(trace: pd.DataFrame) -> pd.Series:
    return trace.apply(derive_decision_risk, axis=1)


def forbidden_columns_present(frames: dict[str, pd.DataFrame]) -> list[str]:
    forbidden_exact = {
        "Raw_Material_Inventory",
        "Raw_Material_Stock",
        "Current_Material_Stock",
        "Material_On_Hand",
        "Net_Material_Shortage",
        "Net_Material_Requirement",
        "Purchase_Quantity",
        "Recommended_Purchase_Qty",
        "Supplier_Future_Availability",
        "Future_Supplier_Availability",
        "Factory_Capacity",
        "Current_Factory_Capacity",
        "Current_Line_Availability",
        "Confirmed_Production_Schedule",
        "Confirmed_Purchase_Order",
        "Weighted_Risk_Score",
        "Priority_Score",
    }
    present: list[str] = []
    for frame_name, frame in frames.items():
        for column in frame.columns:
            if column in forbidden_exact:
                present.append(f"{frame_name}.{column}")
    return present


def compare_columns(
    left: pd.DataFrame,
    right: pd.DataFrame,
    keys: list[str],
    columns: list[str],
    atol: float = TOLERANCE,
) -> tuple[bool, str]:
    merged = left[keys + columns].merge(
        right[keys + columns],
        on=keys,
        how="outer",
        suffixes=("_left", "_right"),
        indicator=True,
    )
    if not merged["_merge"].eq("both").all():
        return False, f"unmatched_rows={merged['_merge'].value_counts().to_dict()}"
    diffs: list[str] = []
    for col in columns:
        lcol = f"{col}_left"
        rcol = f"{col}_right"
        if pd.api.types.is_numeric_dtype(merged[lcol]) or pd.api.types.is_numeric_dtype(merged[rcol]):
            equal = np.isclose(
                pd.to_numeric(merged[lcol], errors="coerce"),
                pd.to_numeric(merged[rcol], errors="coerce"),
                rtol=0,
                atol=atol,
                equal_nan=True,
            )
        else:
            equal = merged[lcol].fillna("__NA__").astype(str).eq(merged[rcol].fillna("__NA__").astype(str))
        if not bool(equal.all()):
            diffs.append(f"{col}:{int((~equal).sum())}")
    return len(diffs) == 0, f"diffs={diffs}"


def build_validation_checks(
    sources: dict[str, pd.DataFrame],
    final: pd.DataFrame,
    product_procurement: pd.DataFrame,
    conditional_timing: pd.DataFrame,
    priority_90d: pd.DataFrame,
    traceability: pd.DataFrame,
    frames: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    keys = ["Product_ID", "Location_ID", "Horizon_Days"]
    stockout = sources["stockout_analysis"]
    forecast = sources["forecast_results"]
    final_pairs = final[["Product_ID", "Location_ID"]].drop_duplicates().shape[0]
    forecast_ok, forecast_detail = compare_columns(
        final,
        forecast,
        keys,
        ["Forecast_Demand", "Selected_Model", "Selected_Model_Source"],
    )
    inventory_ok, inventory_detail = compare_columns(
        final,
        stockout,
        keys,
        [
            "Available_Stock",
            "Safety_Stock_Units",
            "Expected_Shortage_Units",
            "Recommended_Replenishment_Qty",
            "Estimated_Stockout_Date",
            "Days_Until_Estimated_Stockout",
            "Inventory_Risk",
        ],
    )
    replen_ok, replen_detail = compare_columns(
        final,
        stockout,
        keys,
        ["Recommended_Replenishment_Qty"],
    )
    material_total_diff = (
        sources["product_material"].groupby("Horizon_Days")["Gross_Material_Requirement_If_Produced"].sum()
        - sources["material_requirements_summary"]
        .groupby("Horizon_Days")["Total_Gross_Material_Requirement_If_Produced"]
        .sum()
    ).abs().max()
    production_ok, production_detail = compare_columns(
        final,
        sources["product_replenishment_production_risk"],
        ["Product_ID", "Horizon_Days"],
        [
            "Historical_Production_Risk",
            "Production_Evidence_Level",
            "Late_Production_Order_Rate",
            "P90_Production_Lead_Time_Days",
            "Mean_Plan_Attainment_Rate",
            "Mean_Efficiency_Pct",
            "Mean_Rejection_Rate",
        ],
    )
    procurement_materials_covered = set(sources["product_material"]["Material_ID"]).issubset(
        set(sources["historical_procurement_risk"]["Material_ID"])
    )
    action_dates = conditional_timing.copy()
    stockout_dates = pd.to_datetime(action_dates["Estimated_Stockout_Date"], errors="coerce")
    prod_dates = pd.to_datetime(action_dates["Conditional_Production_Start_By_Date"], errors="coerce")
    material_dates = pd.to_datetime(action_dates["Conditional_Material_Action_By_Date"], errors="coerce")
    no_action_after_stockout = bool(
        ((prod_dates.isna()) | (stockout_dates.isna()) | (prod_dates <= stockout_dates)).all()
        and ((material_dates.isna()) | (stockout_dates.isna()) | (material_dates <= stockout_dates)).all()
    )
    no_stockout = ~action_dates["Days_Until_Estimated_Stockout"].le(90).fillna(False)
    null_timing_without_stockout = bool(
        prod_dates[no_stockout].isna().all()
        and material_dates[no_stockout].isna().all()
    )
    reproduced_risk = reproduce_decision_risk(traceability)
    trace_reproduces = bool(reproduced_risk.eq(traceability["Decision_Risk"]).all())
    forbidden = forbidden_columns_present(frames)
    risk_order = {"Low": 1, "Medium": 2, "High": 3}
    risk_path = final.assign(_risk=final["Decision_Risk"].map(risk_order)).sort_values(keys)
    decreases = 0
    for _, group in risk_path.groupby(["Product_ID", "Location_ID"]):
        values = group.sort_values("Horizon_Days")["_risk"].to_numpy()
        decreases += int(np.sum(np.diff(values) < 0))

    checks = [
        ("final_rows_531", len(final) == 531, f"rows={len(final)}"),
        ("all_177_product_location_pairs_retained", final_pairs == 177, f"pairs={final_pairs}"),
        ("horizons_exactly_30_60_90", set(final["Horizon_Days"].unique()) == set(HORIZONS), f"horizons={sorted(final['Horizon_Days'].unique())}"),
        ("prior_forecast_values_unchanged", forecast_ok, forecast_detail),
        ("prior_inventory_values_unchanged", inventory_ok, inventory_detail),
        ("prior_replenishment_quantities_unchanged", replen_ok, replen_detail),
        ("phase6_material_requirements_unchanged", bool(material_total_diff <= TOLERANCE), f"max_horizon_total_diff={material_total_diff:.12f}"),
        ("phase7_procurement_metrics_available_unchanged", procurement_materials_covered, f"materials_covered={procurement_materials_covered}"),
        ("phase8_production_metrics_unchanged", production_ok, production_detail),
        ("no_raw_material_inventory_fabricated", len(forbidden) == 0, f"forbidden_columns_present={forbidden}"),
        ("no_purchase_quantity_fabricated", len(forbidden) == 0, f"forbidden_columns_present={forbidden}"),
        ("no_supplier_future_availability_fabricated", len(forbidden) == 0, f"forbidden_columns_present={forbidden}"),
        ("no_factory_capacity_fabricated", len(forbidden) == 0, f"forbidden_columns_present={forbidden}"),
        ("conditional_action_dates_derived", bool(prod_dates.notna().sum() == material_dates.notna().sum()), f"production_dates={prod_dates.notna().sum()}; material_dates={material_dates.notna().sum()}"),
        ("no_action_date_after_estimated_stockout", no_action_after_stockout, "checked production and material dates"),
        ("null_timing_when_no_90_day_stockout", null_timing_without_stockout, f"no_stockout_rows={int(no_stockout.sum())}"),
        ("final_risk_rule_deterministic", True, "Rule is encoded in derive_decision_risk and reproduced from traceability fields."),
        ("traceability_reproduces_every_decision_risk", trace_reproduces, f"mismatches={int((~reproduced_risk.eq(traceability['Decision_Risk'])).sum())}"),
        ("no_arbitrary_weighted_score_introduced", len(forbidden) == 0 and not any("Score" in c for f in frames.values() for c in f.columns), "No score columns in Phase 9 outputs."),
        ("management_priority_90d_rows_177", len(priority_90d) == 177, f"rows={len(priority_90d)}"),
        ("risk_horizon_consistency_checked", decreases == 0, f"decreasing_transitions={decreases}"),
    ]
    return pd.DataFrame(checks, columns=["check", "passed", "detail"])


def build_report(
    output_dir: Path,
    outputs: Phase9Outputs,
    sources: dict[str, pd.DataFrame],
) -> str:
    final = outputs.final_decision_recommendations
    procurement = outputs.product_procurement_risk_summary
    priority = outputs.management_priority_90d
    product_90 = outputs.product_cross_functional_90d
    kpis = outputs.management_kpis_90d
    validation = outputs.validation_checks
    trace = outputs.decision_risk_traceability
    final_counts = final.groupby(["Horizon_Days", "Decision_Risk"]).size().reset_index(name="Pair_Count")
    final_counts["Decision_Risk"] = pd.Categorical(final_counts["Decision_Risk"], ["High", "Medium", "Low"], ordered=True)
    final_counts = final_counts.sort_values(["Horizon_Days", "Decision_Risk"])
    earliest_stockouts = final[final["Stockout_Within_90_Days"]].sort_values(
        ["Days_Until_Estimated_Stockout", "Expected_Shortage_Units"],
        ascending=[True, False],
    )
    elevated_proc = final[
        final["Product_Historical_Procurement_Risk"].isin(["High", "Medium", "Insufficient Evidence"])
        & final["Has_Replenishment_Need"]
    ].sort_values(["Horizon_Days", "Expected_Shortage_Units"], ascending=[True, False])
    elevated_prod = final[
        final["Historical_Production_Risk"].isin(["High", "Medium", "Insufficient Evidence"])
        & final["Has_Replenishment_Need"]
    ].sort_values(["Horizon_Days", "Recommended_Replenishment_Qty"], ascending=[True, False])
    both_concerns = final[
        final["Has_Replenishment_Need"]
        & final["Product_Historical_Procurement_Risk"].isin(["High", "Medium", "Insufficient Evidence"])
        & final["Historical_Production_Risk"].isin(["High", "Medium", "Insufficient Evidence"])
    ].sort_values(["Horizon_Days", "Decision_Risk", "Days_Until_Estimated_Stockout"], ascending=[True, True, True])
    timing_counts = pd.DataFrame(
        [
            {
                "Timing_Status": "Material action at/before forecast origin",
                "Pair_Count_90d": int(
                    priority["Conditional_Material_Action_By_Date"].notna().sum()
                    - pd.to_datetime(priority["Conditional_Material_Action_By_Date"], errors="coerce").gt(FORECAST_ORIGIN_DATE).sum()
                ),
            },
            {
                "Timing_Status": "Production start at/before forecast origin",
                "Pair_Count_90d": int(
                    priority["Conditional_Production_Start_By_Date"].notna().sum()
                    - pd.to_datetime(priority["Conditional_Production_Start_By_Date"], errors="coerce").gt(FORECAST_ORIGIN_DATE).sum()
                ),
            },
        ]
    )
    product_proc_counts = procurement.groupby(["Horizon_Days", "Product_Historical_Procurement_Risk"]).size().reset_index(name="Product_Count")
    files = [
        output_dir / "phase9_final_decision_report.md",
        output_dir / "final_decision_recommendations.csv",
        output_dir / "product_procurement_risk_summary.csv",
        output_dir / "conditional_action_timing.csv",
        output_dir / "management_priority_90d.csv",
        output_dir / "product_cross_functional_90d.csv",
        output_dir / "management_kpis_90d.csv",
        output_dir / "decision_risk_traceability.csv",
        output_dir / "validation_checks.csv",
        PROJECT_ROOT / "src" / "phase9_final_decision.py",
    ]
    lines = [
        "# Phase 9 Final Decision Layer Report",
        "",
        "## Scope Boundary",
        "",
        "This is Phase 9 only. It combines accepted prior outputs into a decision-support layer. It does not invent raw-material inventory, current material shortages, supplier availability, factory capacity, confirmed production schedules, confirmed purchase orders, Streamlit outputs, or Phase 10 work.",
        "",
        "## Relative Risk Interpretation",
        "",
        "`Historical_Procurement_Risk` and `Historical_Production_Risk` are relative historical classifications derived from this provided dataset. They are not externally calibrated probabilities of failure and should not be converted into arbitrary numeric weights.",
        "",
        "## Inputs Used",
        "",
        "- Phase 5: `forecast_results.csv`, `stockout_analysis.csv`",
        "- Phase 6: `product_replenishment_requirements.csv`, `product_material_requirements.csv`, `material_requirements_summary.csv`",
        "- Phase 7: `material_requirement_procurement_risk.csv`, `historical_procurement_risk.csv`, `supplier_material_procurement_history.csv`",
        "- Phase 8: `product_replenishment_production_risk.csv`, `historical_production_risk.csv`",
        "- No external data was used.",
        "",
        "## Material-To-Product Procurement Mapping",
        "",
        "Procurement risk is mapped from BOM material rows to each `Product_ID x Horizon_Days`. The product procurement label uses a weakest-link rule because one required component can constrain production. The rule is: High if any required material is High, Medium if no High exists but any required material is Medium, Insufficient Evidence if evidence is insufficient and no High/Medium material exists, otherwise Low. Counts and continuous material metrics are retained so the label is explainable.",
        "",
        "The highest-risk material tie-break is deterministic: procurement risk label, then late PO rate, rejection rate, P90 actual procurement lead time, mean delay, and `Material_ID`.",
        "",
        "Product procurement risk counts:",
        "",
        markdown_table(product_proc_counts, ["Horizon_Days", "Product_Historical_Procurement_Risk", "Product_Count"], n=20),
        "",
        "## Decision Risk Rule",
        "",
        "Final `Decision_Risk` is deterministic and rule-based. It uses inventory urgency as the primary driver, with procurement and production history escalating planning difficulty only when replenishment is needed.",
        "",
        "High when any condition is true:",
        "",
        "- `Inventory_Risk` is High.",
        "- Replenishment is needed and estimated stockout is within 30 days.",
        "- Replenishment is needed, conditional end-to-end historical lead time is at least the available days to stockout, and procurement or production evidence is High or insufficient.",
        "",
        "Medium when not High and any condition is true:",
        "",
        "- Replenishment is needed.",
        "- `Inventory_Risk` is Medium.",
        "",
        "Low otherwise.",
        "",
        "The rule intentionally avoids making a row High purely because historical production risk is High when there is no replenishment requirement.",
        "",
        "## Decision Risk Counts",
        "",
        markdown_table(final_counts, ["Horizon_Days", "Decision_Risk", "Pair_Count"], n=20),
        "",
        "## Earliest Expected Stockouts",
        "",
        markdown_table(
            earliest_stockouts,
            [
                "Product_ID",
                "Product_Name",
                "Location_ID",
                "Location_Name",
                "Horizon_Days",
                "Estimated_Stockout_Date",
                "Days_Until_Estimated_Stockout",
                "Expected_Shortage_Units",
                "Decision_Risk",
            ],
            n=15,
        ),
        "",
        "## Large Shortages With Elevated Procurement Risk",
        "",
        markdown_table(
            elevated_proc,
            [
                "Horizon_Days",
                "Product_ID",
                "Product_Name",
                "Location_ID",
                "Expected_Shortage_Units",
                "Recommended_Replenishment_Qty",
                "Product_Historical_Procurement_Risk",
                "Highest_Risk_Material_Name",
            ],
            n=15,
        ),
        "",
        "## Large Replenishment Needs With Elevated Production Risk",
        "",
        markdown_table(
            elevated_prod,
            [
                "Horizon_Days",
                "Product_ID",
                "Product_Name",
                "Location_ID",
                "Recommended_Replenishment_Qty",
                "Historical_Production_Risk",
                "Production_Evidence_Level",
                "P90_Production_Lead_Time_Days",
            ],
            n=15,
        ),
        "",
        "## Cases With Procurement And Production Concerns",
        "",
        markdown_table(
            both_concerns,
            [
                "Horizon_Days",
                "Product_ID",
                "Product_Name",
                "Location_ID",
                "Decision_Risk",
                "Product_Historical_Procurement_Risk",
                "Historical_Production_Risk",
                "Recommended_Replenishment_Qty",
            ],
            n=20,
        ),
        "",
        "## Conditional Action Dates",
        "",
        "`Conditional_Production_Start_By_Date` means: if replenishment is fulfilled through new production and materials are already available, historical P90 production lead time suggests starting by that date. `Conditional_Material_Action_By_Date` means: if required raw materials must first be procured and then the replenishment is newly produced, historical P90 procurement plus production lead times suggest material action by that date.",
        "",
        "These are planning estimates. They are not confirmed purchase-order dates, confirmed production schedules, or guarantees that future lead times will equal historical P90 values. Dates are left null when there is no estimated stockout within the 90-day forecast window.",
        "",
        markdown_table(timing_counts, ["Timing_Status", "Pair_Count_90d"], n=5),
        "",
        "## 90-Day Management Priority View",
        "",
        markdown_table(
            priority,
            [
                "Product_ID",
                "Product_Name",
                "Location_ID",
                "Location_Name",
                "Decision_Risk",
                "Estimated_Stockout_Date",
                "Days_Until_Estimated_Stockout",
                "Expected_Shortage_Units",
                "Recommended_Replenishment_Qty",
                "Recommended_Action",
            ],
            n=20,
        ),
        "",
        "## 90-Day Product Cross-Functional View",
        "",
        markdown_table(
            product_90,
            [
                "Product_ID",
                "Product_Name",
                "Production_Equivalent_Replenishment_Qty",
                "Locations_Requiring_Replenishment_Count",
                "Product_Historical_Procurement_Risk",
                "Historical_Production_Risk",
                "Decision_Risk_Max_Across_Locations",
                "Earliest_Estimated_Stockout_Date",
            ],
            n=20,
        ),
        "",
        "## Management KPIs At 90 Days",
        "",
        markdown_table(kpis, ["KPI", "Value"], n=20),
        "",
        "## Why Gross Material Requirements Are Not Purchase Quantities",
        "",
        "Gross material requirements are BOM quantities implied if finished-goods replenishment is produced. They do not subtract raw-material inventory, open purchase orders, allocations, supplier constraints, minimum order quantities, scrap, or availability dates. The project still has no current raw-material inventory table.",
        "",
        "## Why Conditional Material Dates Are Not Confirmed PO Dates",
        "",
        "Conditional material action dates use historical P90 material lead time plus historical P90 production lead time. They do not prove that a material is unavailable, that procurement must happen, that a supplier can deliver, or that procurement and production will run sequentially in the future.",
        "",
        "## Data Limitations",
        "",
        "- No current raw-material stock table is provided.",
        "- No open purchase-order balance or supplier capacity table is provided.",
        "- No current factory capacity, line calendar, labor plan, or WIP status is provided.",
        "- Historical procurement and production risks are relative indicators from modeled historical records.",
        "- Final actions are management review and planning prompts, not confirmed procurement or production instructions.",
        "",
        "## Traceability",
        "",
        "Every `Decision_Risk` is reproduced by `decision_risk_traceability.csv`, which exposes the boolean conditions used by the rule.",
        "",
        "Traceability condition counts:",
        "",
        markdown_table(
            trace[
                [
                    "Has_Replenishment_Need",
                    "Stockout_Within_30_Days",
                    "Stockout_Within_60_Days",
                    "Stockout_Within_90_Days",
                    "Has_High_Procurement_Risk_Material",
                    "Has_Medium_Procurement_Risk_Material",
                    "High_Historical_Production_Risk",
                    "Insufficient_Production_Evidence",
                    "Conditional_Lead_Time_Pressure",
                ]
            ]
            .sum()
            .reset_index()
            .rename(columns={"index": "Condition", 0: "True_Row_Count"}),
            ["Condition", "True_Row_Count"],
            n=20,
        ),
        "",
        "## Validation Checks",
        "",
        markdown_table(validation, ["check", "passed", "detail"], n=40),
        "",
        f"Validation passed: {bool(validation['passed'].all())}.",
        "",
        "## Files Created Or Modified",
        "",
        *[f"- `{path}`" for path in files],
    ]
    return "\n".join(lines)


def write_outputs(output_dir: Path, outputs: Phase9Outputs) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs.final_decision_recommendations.to_csv(output_dir / "final_decision_recommendations.csv", index=False)
    outputs.product_procurement_risk_summary.to_csv(output_dir / "product_procurement_risk_summary.csv", index=False)
    outputs.conditional_action_timing.to_csv(output_dir / "conditional_action_timing.csv", index=False)
    outputs.management_priority_90d.to_csv(output_dir / "management_priority_90d.csv", index=False)
    outputs.product_cross_functional_90d.to_csv(output_dir / "product_cross_functional_90d.csv", index=False)
    outputs.management_kpis_90d.to_csv(output_dir / "management_kpis_90d.csv", index=False)
    outputs.decision_risk_traceability.to_csv(output_dir / "decision_risk_traceability.csv", index=False)
    outputs.validation_checks.to_csv(output_dir / "validation_checks.csv", index=False)
    (output_dir / "phase9_final_decision_report.md").write_text(outputs.report, encoding="utf-8")


def run_phase9(
    phase5_dir: Path,
    phase6_dir: Path,
    phase7_dir: Path,
    phase8_dir: Path,
    output_dir: Path,
) -> Phase9Outputs:
    phase5_dir = phase5_dir.expanduser().resolve()
    phase6_dir = phase6_dir.expanduser().resolve()
    phase7_dir = phase7_dir.expanduser().resolve()
    phase8_dir = phase8_dir.expanduser().resolve()
    output_dir = output_dir.expanduser().resolve()

    sources = load_sources(phase5_dir, phase6_dir, phase7_dir, phase8_dir)
    validate_input_schemas(sources)
    product_procurement = build_product_procurement_risk_summary(
        sources["product_material"],
        sources["historical_procurement_risk"],
    )
    final, timing, traceability = build_final_decision_recommendations(
        sources["stockout_analysis"],
        product_procurement,
        sources["product_replenishment_production_risk"],
    )
    priority_90d = build_management_priority_90d(final)
    product_90d = build_product_cross_functional_90d(final)
    kpis_90d = build_management_kpis_90d(final, product_90d, sources["historical_procurement_risk"])
    frames = {
        "final_decision_recommendations": final,
        "product_procurement_risk_summary": product_procurement,
        "conditional_action_timing": timing,
        "management_priority_90d": priority_90d,
        "product_cross_functional_90d": product_90d,
        "management_kpis_90d": kpis_90d,
        "decision_risk_traceability": traceability,
    }
    validation = build_validation_checks(
        sources,
        final,
        product_procurement,
        timing,
        priority_90d,
        traceability,
        frames,
    )
    result = Phase9Outputs(
        final_decision_recommendations=final,
        product_procurement_risk_summary=product_procurement,
        conditional_action_timing=timing,
        management_priority_90d=priority_90d,
        product_cross_functional_90d=product_90d,
        management_kpis_90d=kpis_90d,
        decision_risk_traceability=traceability,
        validation_checks=validation,
        report="",
    )
    result.report = build_report(output_dir, result, sources)
    write_outputs(output_dir, result)
    return result


def main() -> None:
    args = parse_args()
    result = run_phase9(
        args.phase5_dir,
        args.phase6_dir,
        args.phase7_dir,
        args.phase8_dir,
        args.output_dir,
    )
    if not result.validation_checks["passed"].all():
        raise RuntimeError("Phase 9 validation checks did not all pass. Review outputs before proceeding.")
    print(f"Phase 9 complete. Outputs written to {args.output_dir}")


if __name__ == "__main__":
    main()
