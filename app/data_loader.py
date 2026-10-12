from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Tuple

import pandas as pd

try:
    import streamlit as st
except Exception:  # pragma: no cover - lets validation run before Streamlit is installed.
    st = None


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
DATA_DIR = PROJECT_ROOT / "data"


class DashboardDataError(RuntimeError):
    """Raised when an accepted Phase 1-9 dashboard input is missing or malformed."""


def _cache_data(func):
    if st is None:
        return func
    return st.cache_data(show_spinner=False)(func)


@dataclass(frozen=True)
class DatasetSpec:
    relative_path: str
    required_columns: Tuple[str, ...]
    pages: Tuple[str, ...]
    required: bool = True
    description: str = ""

    @property
    def path(self) -> Path:
        return PROJECT_ROOT / self.relative_path


DATASETS: Dict[str, DatasetSpec] = {
    "forecast_results": DatasetSpec(
        "outputs/phase5/forecast_results.csv",
        (
            "Product_ID",
            "Product_Name",
            "Location_ID",
            "Location_Name",
            "Channel",
            "Product_Family",
            "Horizon_Days",
            "Forecast_Demand",
            "Selected_Model",
            "Selected_Model_Source",
        ),
        ("Demand Forecast", "Model Performance"),
        description="Accepted Phase 5 final forecast output.",
    ),
    "stockout_analysis": DatasetSpec(
        "outputs/phase5/stockout_analysis.csv",
        (
            "Product_ID",
            "Location_ID",
            "Horizon_Days",
            "Forecast_Demand",
            "Available_Stock",
            "Expected_Shortage_Units",
            "Recommended_Replenishment_Qty",
            "Estimated_Stockout_Date",
            "Inventory_Risk",
        ),
        ("Inventory & Stockout Risk",),
        description="Accepted Phase 5 inventory and stockout analysis.",
    ),
    "product_replenishment_requirements": DatasetSpec(
        "outputs/phase6/product_replenishment_requirements.csv",
        (
            "Product_ID",
            "Product_Name",
            "Horizon_Days",
            "Production_Equivalent_Replenishment_Qty",
            "Requires_Replenishment",
        ),
        ("Material Requirements",),
        description="Accepted Phase 6 product-level replenishment requirement bridge.",
    ),
    "product_material_requirements": DatasetSpec(
        "outputs/phase6/product_material_requirements.csv",
        (
            "Product_ID",
            "Product_Name",
            "Product_Family",
            "Horizon_Days",
            "Material_ID",
            "Material_Name",
            "Unit",
            "Gross_Material_Requirement_If_Produced",
        ),
        ("Material Requirements",),
        description="Accepted Phase 6 gross material requirements if finished goods are produced.",
    ),
    "material_requirements_summary": DatasetSpec(
        "outputs/phase6/material_requirements_summary.csv",
        (
            "Material_ID",
            "Material_Name",
            "Unit",
            "Horizon_Days",
            "Total_Gross_Material_Requirement_If_Produced",
        ),
        ("Material Requirements",),
        description="Accepted Phase 6 material-level gross requirement summary.",
    ),
    "material_requirement_procurement_risk": DatasetSpec(
        "outputs/phase7/material_requirement_procurement_risk.csv",
        (
            "Material_ID",
            "Material_Name",
            "Unit",
            "Horizon_Days",
            "Historical_Procurement_Risk",
            "Procurement_Risk_Reason",
        ),
        ("Procurement Risk", "Material Requirements"),
        description="Accepted Phase 7 material requirements with historical procurement risk.",
    ),
    "historical_procurement_risk": DatasetSpec(
        "outputs/phase7/historical_procurement_risk.csv",
        (
            "Material_ID",
            "Material_Name",
            "Historical_Procurement_Risk",
            "Procurement_Risk_Reason",
        ),
        ("Procurement Risk",),
        description="Accepted Phase 7 historical material procurement risk.",
    ),
    "supplier_procurement_history": DatasetSpec(
        "outputs/phase7/supplier_procurement_history.csv",
        (
            "Supplier_ID",
            "Supplier_Name",
            "PO_Count",
            "Late_PO_Rate",
            "On_Time_PO_Rate",
            "Mean_Rejection_Rate",
        ),
        ("Procurement Risk",),
        description="Accepted Phase 7 historical supplier-level procurement performance.",
    ),
    "supplier_material_procurement_history": DatasetSpec(
        "outputs/phase7/supplier_material_procurement_history.csv",
        (
            "Supplier_ID",
            "Supplier_Name",
            "Material_ID",
            "Material_Name",
            "PO_Count",
            "Late_PO_Rate",
        ),
        ("Procurement Risk",),
        description="Accepted Phase 7 supplier-material historical procurement performance.",
    ),
    "historical_supplier_performance_rank": DatasetSpec(
        "outputs/phase7/historical_supplier_performance_rank.csv",
        (
            "Material_ID",
            "Material_Name",
            "Historical_Supplier_Performance_Rank",
            "Supplier_ID",
            "Supplier_Name",
        ),
        ("Procurement Risk",),
        description="Accepted Phase 7 historical supplier ranking by material.",
    ),
    "product_replenishment_production_risk": DatasetSpec(
        "outputs/phase8/product_replenishment_production_risk.csv",
        (
            "Product_ID",
            "Product_Name",
            "Horizon_Days",
            "Production_Equivalent_Replenishment_Qty",
            "Historical_Production_Risk",
            "Production_Risk_Reason",
        ),
        ("Production Risk",),
        description="Accepted Phase 8 product replenishment with historical production risk.",
    ),
    "line_production_history": DatasetSpec(
        "outputs/phase8/line_production_history.csv",
        (
            "Line_ID",
            "Production_Order_Count",
            "Mean_Efficiency_Pct",
            "Late_Order_Rate",
            "Latest_Production_Date",
        ),
        ("Production Risk",),
        description="Accepted Phase 8 line-level historical production performance.",
    ),
    "bottleneck_analysis": DatasetSpec(
        "outputs/phase8/bottleneck_analysis.csv",
        (
            "Primary_Bottleneck",
            "Production_Order_Count",
            "Late_Order_Rate",
            "Bottleneck_Share",
        ),
        ("Production Risk",),
        description="Accepted Phase 8 historical bottleneck analysis.",
    ),
    "product_production_history": DatasetSpec(
        "outputs/phase8/product_production_history.csv",
        (
            "Product_ID",
            "Product_Name",
            "Production_Order_Count",
            "Late_Production_Order_Rate",
            "Mean_Efficiency_Pct",
        ),
        ("Production Risk",),
        description="Accepted Phase 8 product historical production performance.",
    ),
    "product_line_production_history": DatasetSpec(
        "outputs/phase8/product_line_production_history.csv",
        (
            "Product_ID",
            "Line_ID",
            "Production_Order_Count",
            "Mean_Efficiency_Pct",
            "Late_Order_Rate",
        ),
        ("Production Risk",),
        description="Accepted Phase 8 product-line historical production performance.",
    ),
    "historical_production_risk": DatasetSpec(
        "outputs/phase8/historical_production_risk.csv",
        (
            "Product_ID",
            "Product_Name",
            "Historical_Production_Risk",
            "Production_Risk_Reason",
        ),
        ("Production Risk",),
        description="Accepted Phase 8 historical product production risk.",
    ),
    "final_decision": DatasetSpec(
        "outputs/phase9/final_decision_recommendations.csv",
        (
            "Product_ID",
            "Product_Name",
            "Location_ID",
            "Location_Name",
            "Channel",
            "Product_Family",
            "Horizon_Days",
            "Forecast_Demand",
            "Expected_Shortage_Units",
            "Recommended_Replenishment_Qty",
            "Inventory_Risk",
            "Product_Historical_Procurement_Risk",
            "Historical_Production_Risk",
            "Decision_Risk",
            "Decision_Risk_Reason",
            "Recommended_Action",
            "Conditional_Material_Action_By_Date",
        ),
        ("Executive Overview", "Final Decision Center"),
        description="Accepted Phase 9 final decision layer.",
    ),
    "management_priority_90d": DatasetSpec(
        "outputs/phase9/management_priority_90d.csv",
        (
            "Product_ID",
            "Location_ID",
            "Expected_Shortage_Units",
            "Recommended_Replenishment_Qty",
            "Decision_Risk",
            "Recommended_Action",
        ),
        ("Executive Overview", "Final Decision Center"),
        description="Accepted Phase 9 90-day management priority table.",
    ),
    "management_kpis_90d": DatasetSpec(
        "outputs/phase9/management_kpis_90d.csv",
        ("KPI", "Value"),
        ("Executive Overview",),
        description="Accepted Phase 9 90-day KPI table.",
    ),
    "product_cross_functional_90d": DatasetSpec(
        "outputs/phase9/product_cross_functional_90d.csv",
        (
            "Product_ID",
            "Product_Name",
            "Product_Historical_Procurement_Risk",
            "Historical_Production_Risk",
            "Decision_Risk_Max_Across_Locations",
        ),
        ("Executive Overview", "Procurement Risk", "Production Risk"),
        description="Accepted Phase 9 product-level cross-functional 90-day summary.",
    ),
    "decision_traceability": DatasetSpec(
        "outputs/phase9/decision_risk_traceability.csv",
        (
            "Product_ID",
            "Location_ID",
            "Horizon_Days",
            "Decision_Risk",
            "Has_High_Procurement_Risk_Material",
            "Conditional_Lead_Time_Pressure",
        ),
        ("Final Decision Center",),
        description="Accepted Phase 9 decision-risk rule traceability.",
    ),
    "conditional_action_timing": DatasetSpec(
        "outputs/phase9/conditional_action_timing.csv",
        (
            "Product_ID",
            "Location_ID",
            "Horizon_Days",
            "Conditional_Production_Start_By_Date",
            "Conditional_Material_Action_By_Date",
            "Production_Action_Status",
            "Material_Action_Status",
        ),
        ("Final Decision Center", "Inventory & Stockout Risk"),
        description="Accepted Phase 9 conditional planning-date table.",
    ),
    "product_procurement_risk_summary": DatasetSpec(
        "outputs/phase9/product_procurement_risk_summary.csv",
        (
            "Product_ID",
            "Product_Name",
            "Horizon_Days",
            "Product_Historical_Procurement_Risk",
            "Highest_Risk_Material_Name",
            "Highest_Risk_Material_Risk",
        ),
        ("Procurement Risk", "Final Decision Center"),
        description="Accepted Phase 9 product-level historical procurement risk summary.",
    ),
    "daily_demand_panel": DatasetSpec(
        "data/processed/daily_product_location_demand_panel.csv",
        (
            "Date",
            "Product_ID",
            "Location_ID",
            "Demand_Units",
            "Zero_Demand_Day",
            "Product_Name",
            "Location_Name",
            "Channel",
        ),
        ("Demand Forecast", "Methodology & Limitations"),
        description="Accepted Phase 2 daily demand panel.",
    ),
    "monthly_sales_inventory_reconciliation": DatasetSpec(
        "data/processed/monthly_sales_inventory_reconciliation.csv",
        (
            "Month",
            "Product_ID",
            "Location_ID",
            "Sales_Quantity",
            "Sold_Qty",
            "Absolute_Difference",
            "Exact_Match",
        ),
        ("Methodology & Limitations",),
        description="Accepted Phase 2 sales vs inventory reconciliation detail.",
    ),
    "demand_series_eda": DatasetSpec(
        "outputs/phase2/demand_series_eda.csv",
        (
            "Product_ID",
            "Location_ID",
            "Total_Demand",
            "Zero_Demand_Pct",
            "Demand_Pattern_Class",
            "May_Need_Fallback_Later",
        ),
        ("Demand Forecast", "Methodology & Limitations"),
        description="Accepted Phase 2 product-location demand behavior EDA.",
    ),
    "inventory_accounting_summary": DatasetSpec(
        "outputs/phase2/inventory_accounting_summary.csv",
        ("metric", "value"),
        ("Methodology & Limitations",),
        description="Accepted Phase 2 inventory accounting validation summary.",
    ),
    "inventory_accounting_validation": DatasetSpec(
        "outputs/phase2/inventory_accounting_validation.csv",
        (
            "Snapshot_Month",
            "Product_ID",
            "Location_ID",
            "Closing_Stock_Mismatch",
            "Accounting_Holds_Exactly",
        ),
        ("Methodology & Limitations",),
        description="Accepted Phase 2 row-level inventory accounting validation.",
    ),
    "sales_inventory_reconciliation_summary": DatasetSpec(
        "outputs/phase2/sales_inventory_reconciliation_summary.csv",
        ("metric", "value"),
        ("Methodology & Limitations",),
        description="Accepted Phase 2 sales vs inventory reconciliation summary.",
    ),
    "leakage_risk_table": DatasetSpec(
        "outputs/phase2/leakage_risk_table.csv",
        ("table", "column_or_group", "leakage_risk", "safe_use_rule"),
        ("Methodology & Limitations",),
        description="Accepted Phase 2 leakage-risk table.",
    ),
    "weekday_demand_pattern": DatasetSpec(
        "outputs/phase2/weekday_demand_pattern.csv",
        ("Day_Of_Week", "Total_Demand", "Mean_Daily_Demand", "Zero_Demand_Pct"),
        ("Demand Forecast",),
        description="Accepted Phase 2 weekday demand pattern.",
    ),
    "monthly_demand_pattern": DatasetSpec(
        "outputs/phase2/monthly_demand_pattern.csv",
        ("Month_Of_Year", "Total_Demand", "Mean_Daily_Demand", "Zero_Demand_Pct"),
        ("Demand Forecast",),
        description="Accepted Phase 2 monthly demand pattern.",
    ),
    "location_channel_demand_summary": DatasetSpec(
        "outputs/phase2/location_channel_demand_summary.csv",
        ("Location_ID", "Location_Name", "Channel", "Total_Demand", "Zero_Demand_Pct"),
        ("Demand Forecast",),
        description="Accepted Phase 2 demand summary by location and channel.",
    ),
    "product_family_demand_summary": DatasetSpec(
        "outputs/phase2/product_family_demand_summary.csv",
        ("Product_Family", "Total_Demand", "Zero_Demand_Pct"),
        ("Demand Forecast",),
        description="Accepted Phase 2 demand summary by product family.",
    ),
    "baseline_metrics_overall": DatasetSpec(
        "outputs/phase3/baseline_metrics_overall.csv",
        ("Frequency", "Baseline", "Cumulative_WAPE", "Series_Count"),
        ("Model Performance",),
        description="Accepted Phase 3 baseline model metrics.",
    ),
    "baseline_metrics_by_horizon": DatasetSpec(
        "outputs/phase3/baseline_metrics_by_horizon.csv",
        ("Horizon_Days", "Frequency", "Baseline", "Cumulative_WAPE"),
        ("Model Performance",),
        description="Accepted Phase 3 baseline metrics by horizon.",
    ),
    "model_metrics_overall": DatasetSpec(
        "outputs/phase4/model_metrics_overall.csv",
        ("Model_Source", "Frequency", "Model", "Cumulative_WAPE", "Series_Count"),
        ("Model Performance",),
        description="Accepted Phase 4 model comparison metrics.",
    ),
    "advanced_vs_baseline_comparison": DatasetSpec(
        "outputs/phase4/advanced_vs_baseline_comparison.csv",
        (
            "Product_ID",
            "Location_ID",
            "Horizon_Days",
            "Selected_Model_Source",
            "Selected_Model",
            "Validation_Cumulative_WAPE",
        ),
        ("Model Performance",),
        description="Accepted Phase 4 per-series advanced vs baseline comparison.",
    ),
    "policy_comparison": DatasetSpec(
        "outputs/phase4_1/policy_comparison.csv",
        ("Policy", "Cumulative_WAPE", "Segment_Type", "Series_Count"),
        ("Model Performance",),
        description="Accepted Phase 4.1 policy comparison.",
    ),
    "leave_one_fold_out_policy_metrics": DatasetSpec(
        "outputs/phase4_1/leave_one_fold_out_policy_metrics.csv",
        ("Policy", "Cumulative_WAPE", "Segment_Type", "Series_Count"),
        ("Model Performance",),
        description="Accepted Phase 4.1 leave-one-fold-out policy metrics.",
    ),
    "full_coverage_policy_comparison": DatasetSpec(
        "outputs/phase5_1/full_coverage_policy_comparison.csv",
        ("Policy", "Cumulative_WAPE", "Segment_Type", "Series_Count"),
        ("Model Performance",),
        description="Accepted Phase 5.1 equal-coverage policy comparison.",
    ),
    "common_window_policy_comparison": DatasetSpec(
        "outputs/phase5_1/common_window_policy_comparison.csv",
        ("Policy", "Cumulative_WAPE", "Segment_Type", "Series_Count"),
        ("Model Performance",),
        description="Accepted Phase 5.1 common-window policy comparison.",
    ),
}


@_cache_data
def load_dataset(key: str) -> pd.DataFrame:
    if key not in DATASETS:
        raise DashboardDataError(f"Unknown dashboard dataset key: {key}")

    spec = DATASETS[key]
    path = spec.path
    if not path.exists():
        if spec.required:
            raise DashboardDataError(
                f"Required accepted dashboard input is missing: {spec.relative_path}"
            )
        return pd.DataFrame(columns=list(spec.required_columns))

    try:
        frame = pd.read_csv(path)
    except Exception as exc:
        raise DashboardDataError(f"Could not load {spec.relative_path}: {exc}") from exc

    missing = [col for col in spec.required_columns if col not in frame.columns]
    if missing:
        raise DashboardDataError(
            f"{spec.relative_path} is missing required columns: {', '.join(missing)}"
        )
    return frame


@_cache_data
def load_all_data() -> Dict[str, pd.DataFrame]:
    return {key: load_dataset(key) for key in DATASETS}


def build_data_manifest(data: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows = []
    for key, spec in DATASETS.items():
        frame = data.get(key, pd.DataFrame())
        rows.append(
            {
                "dataset_key": key,
                "relative_path": spec.relative_path,
                "exists": spec.path.exists(),
                "rows": int(len(frame)),
                "columns": int(len(frame.columns)),
                "pages": "; ".join(spec.pages),
                "description": spec.description,
            }
        )
    return pd.DataFrame(rows)


def require_nonempty(data: Dict[str, pd.DataFrame], keys: Iterable[str]) -> None:
    empty = [key for key in keys if data.get(key, pd.DataFrame()).empty]
    if empty:
        raise DashboardDataError(
            "Required dashboard datasets loaded but are empty: " + ", ".join(empty)
        )
