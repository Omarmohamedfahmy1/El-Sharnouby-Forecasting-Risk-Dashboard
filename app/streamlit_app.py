from __future__ import annotations

from typing import Any, Dict

import pandas as pd
import streamlit as st

from charts import (
    horizontal_bar,
    line_chart,
    metric_delta_bar,
    risk_distribution,
    scatter_chart,
    vertical_bar,
)
from components import (
    csv_download,
    empty_state,
    fmt_number,
    fmt_pct,
    id_label_map,
    inject_css,
    kpi,
    multiselect_with_all,
    note,
    order_risk_frame,
    risk_badge,
    show_table,
)
from data_loader import DashboardDataError, build_data_manifest, load_all_data


PAGES = [
    "Executive Overview",
    "Demand Forecast",
    "Inventory & Stockout Risk",
    "Material Requirements",
    "Procurement Risk",
    "Production Risk",
    "Final Decision Center",
    "Model Performance",
    "Methodology & Limitations",
]


def page_setup() -> None:
    st.set_page_config(
        page_title="El-Sharnouby Decision Dashboard",
        layout="wide",
    )
    inject_css()
    st.title("El-Sharnouby Forecasting & Risk Dashboard")
    st.caption(
        "Phase 10 dashboard built only from accepted Phase 1-9 project outputs. "
        "No forecasting models or accepted analytics are recomputed here."
    )


def get_filters(final_df: pd.DataFrame) -> Dict[str, Any]:
    st.sidebar.header("Dashboard Filters")
    page = st.sidebar.radio("Section", PAGES, index=0)
    horizon_options = ["All"] + sorted(final_df["Horizon_Days"].dropna().astype(int).unique().tolist())
    horizon = st.sidebar.selectbox("Forecast Horizon", horizon_options, index=horizon_options.index(90))

    product_map = id_label_map(final_df, "Product_ID", "Product_Name")
    location_map = id_label_map(final_df, "Location_ID", "Location_Name")

    product_labels = multiselect_with_all("Product", list(product_map.keys()))
    location_labels = multiselect_with_all("Location", list(location_map.keys()))

    channel_options = sorted(final_df["Channel"].dropna().astype(str).unique().tolist())
    family_options = sorted(final_df["Product_Family"].dropna().astype(str).unique().tolist())
    decision_options = sorted(final_df["Decision_Risk"].dropna().astype(str).unique().tolist())
    inventory_options = sorted(final_df["Inventory_Risk"].dropna().astype(str).unique().tolist())

    channels = multiselect_with_all("Channel", channel_options)
    families = multiselect_with_all("Product Family", family_options)
    decision_risks = multiselect_with_all("Decision Risk", decision_options)
    inventory_risks = multiselect_with_all("Inventory Risk", inventory_options)

    return {
        "page": page,
        "horizon": horizon,
        "product_ids": None if product_labels is None else [product_map[label] for label in product_labels],
        "location_ids": None if location_labels is None else [location_map[label] for label in location_labels],
        "channels": channels,
        "families": families,
        "decision_risks": decision_risks,
        "inventory_risks": inventory_risks,
    }


def apply_filters(df: pd.DataFrame, filters: Dict[str, Any]) -> pd.DataFrame:
    if df.empty:
        return df.copy()
    out = df.copy()
    if filters["horizon"] != "All" and "Horizon_Days" in out.columns:
        out = out[out["Horizon_Days"].astype(int) == int(filters["horizon"])]
    if filters["product_ids"] is not None and "Product_ID" in out.columns:
        out = out[out["Product_ID"].isin(filters["product_ids"])]
    if filters["location_ids"] is not None and "Location_ID" in out.columns:
        out = out[out["Location_ID"].isin(filters["location_ids"])]
    if filters["channels"] is not None and "Channel" in out.columns:
        out = out[out["Channel"].isin(filters["channels"])]
    if filters["families"] is not None and "Product_Family" in out.columns:
        out = out[out["Product_Family"].isin(filters["families"])]
    if filters["decision_risks"] is not None and "Decision_Risk" in out.columns:
        out = out[out["Decision_Risk"].isin(filters["decision_risks"])]
    if filters["inventory_risks"] is not None and "Inventory_Risk" in out.columns:
        out = out[out["Inventory_Risk"].isin(filters["inventory_risks"])]
    return out


def align_to_final_context(df: pd.DataFrame, final_view: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df.copy()
    out = df.copy()
    if final_view.empty:
        return out.iloc[0:0].copy()
    if "Product_ID" in out.columns:
        out = out[out["Product_ID"].isin(final_view["Product_ID"].dropna().unique())]
    if "Location_ID" in out.columns:
        out = out[out["Location_ID"].isin(final_view["Location_ID"].dropna().unique())]
    if "Horizon_Days" in out.columns and "Horizon_Days" in final_view.columns:
        out = out[out["Horizon_Days"].astype(int).isin(final_view["Horizon_Days"].astype(int).unique())]
    return out


def management_priority_90d_view(data: Dict[str, pd.DataFrame], filters: Dict[str, Any]) -> pd.DataFrame:
    priority = data["management_priority_90d"].copy()
    priority["_accepted_priority_order"] = range(len(priority))

    final_90 = data["final_decision"][data["final_decision"]["Horizon_Days"].astype(int) == 90]
    context_cols = ["Product_ID", "Location_ID", "Product_Family", "Horizon_Days"]
    priority = priority.merge(
        final_90[context_cols].drop_duplicates(),
        on=["Product_ID", "Location_ID"],
        how="left",
        validate="one_to_one",
    )

    if filters["product_ids"] is not None:
        priority = priority[priority["Product_ID"].isin(filters["product_ids"])]
    if filters["location_ids"] is not None:
        priority = priority[priority["Location_ID"].isin(filters["location_ids"])]
    if filters["channels"] is not None:
        priority = priority[priority["Channel"].isin(filters["channels"])]
    if filters["families"] is not None:
        priority = priority[priority["Product_Family"].isin(filters["families"])]
    if filters["decision_risks"] is not None:
        priority = priority[priority["Decision_Risk"].isin(filters["decision_risks"])]
    if filters["inventory_risks"] is not None:
        priority = priority[priority["Inventory_Risk"].isin(filters["inventory_risks"])]

    return priority.sort_values("_accepted_priority_order").drop(columns=["_accepted_priority_order"])


def procurement_systemic_warning_values(data: Dict[str, pd.DataFrame]) -> Dict[str, Any]:
    final_90 = data["final_decision"][data["final_decision"]["Horizon_Days"].astype(int) == 90]
    material_counts = final_90["Highest_Risk_Material_Name"].fillna("Not available").value_counts()
    if material_counts.empty:
        top_material = "Not available"
        top_material_rows = 0
    else:
        top_material = str(material_counts.index[0])
        top_material_rows = int(material_counts.iloc[0])

    return {
        "total_90_rows": int(len(final_90)),
        "high_procurement_risk_90_rows": int(
            (final_90["Product_Historical_Procurement_Risk"] == "High").sum()
        ),
        "top_highest_risk_material": top_material,
        "top_highest_risk_material_rows": top_material_rows,
    }


def _single_cumulative_wape(
    frame: pd.DataFrame,
    source_name: str,
    *,
    policy_col: str,
    policy_value: str,
    extra_filters: Dict[str, Any] | None = None,
) -> float:
    mask = frame[policy_col].astype(str).eq(policy_value)
    for column, value in (extra_filters or {}).items():
        if pd.isna(value):
            mask &= frame[column].isna()
        else:
            mask &= frame[column].astype(str).eq(str(value))
    matches = frame[mask]
    if len(matches) != 1:
        raise DashboardDataError(
            f"Expected exactly one accepted WAPE row in {source_name} for "
            f"{policy_col}={policy_value}; found {len(matches)}."
        )
    value = matches["Cumulative_WAPE"].iloc[0]
    if pd.isna(value):
        raise DashboardDataError(
            f"Accepted WAPE row in {source_name} for {policy_value} has a missing Cumulative_WAPE."
        )
    return float(value)


def accepted_model_performance_metrics(data: Dict[str, pd.DataFrame]) -> list[dict]:
    baseline_source = data["baseline_metrics_overall"]
    baseline_mask = (
        baseline_source["Frequency"].astype(str).eq("weekly_distributed")
        & baseline_source["Baseline"].astype(str).eq("weekly_seasonal_naive_52w")
    )
    baseline_rows = baseline_source[baseline_mask]
    if len(baseline_rows) != 1:
        raise DashboardDataError(
            "Expected exactly one Phase 3 baseline row for weekly_seasonal_naive_52w; "
            f"found {len(baseline_rows)}."
        )
    baseline_wape = float(baseline_rows["Cumulative_WAPE"].iloc[0])

    apparent_wape = _single_cumulative_wape(
        data["policy_comparison"],
        "outputs/phase4_1/policy_comparison.csv",
        policy_col="Policy",
        policy_value="phase4_apparent_selection",
        extra_filters={"Segment_Type": "overall"},
    )
    leave_one_fold_out_wape = _single_cumulative_wape(
        data["leave_one_fold_out_policy_metrics"],
        "outputs/phase4_1/leave_one_fold_out_policy_metrics.csv",
        policy_col="Policy",
        policy_value="leave_one_fold_out_selection",
        extra_filters={"Segment_Type": "overall"},
    )
    guarded_wape = _single_cumulative_wape(
        data["full_coverage_policy_comparison"],
        "outputs/phase5_1/full_coverage_policy_comparison.csv",
        policy_col="Policy",
        policy_value="guarded_hybrid",
        extra_filters={"Segment_Type": "overall"},
    )

    return [
        {
            "Policy": "Baseline weekly_seasonal_naive_52w",
            "Validation WAPE": baseline_wape,
            "Interpretation": "Strong transparent baseline from Phase 3.",
        },
        {
            "Policy": "Apparent per-series selected policy",
            "Validation WAPE": apparent_wape,
            "Interpretation": "Optimistic because model selection used the same folds being scored.",
        },
        {
            "Policy": "Leave-one-fold-out policy",
            "Validation WAPE": leave_one_fold_out_wape,
            "Interpretation": "More honest robustness check; apparent gains did not hold up.",
        },
        {
            "Policy": "Final guarded hybrid equal-coverage validation",
            "Validation WAPE": guarded_wape,
            "Interpretation": "Accepted guarded policy with fairer equal-coverage comparison.",
        },
    ]


def render_fig(fig) -> None:
    if fig is None:
        empty_state("No chart is available for the current filter selection.")
        return
    st.plotly_chart(fig, width="stretch")


def active_filter_note(filters: Dict[str, Any], rows: int) -> None:
    horizon = filters["horizon"]
    note(
        f"Current view contains <b>{fmt_number(rows)}</b> accepted decision rows. "
        f"Forecast horizon filter: <b>{horizon}</b>.",
        kind="note",
    )


def page_executive(data: Dict[str, pd.DataFrame], final_view: pd.DataFrame, filters: Dict[str, Any]) -> None:
    st.header("Executive Overview")
    note(
        "Decision outputs are planning signals. "
        "<b>Recommended Finished-Goods Replenishment</b> is not a production quantity, "
        "<b>Gross Material Requirement If Produced</b> is not a material purchase quantity, "
        "and historical procurement/production risks are relative evidence from provided history.",
        kind="warning",
    )
    active_filter_note(filters, len(final_view))
    if final_view.empty:
        empty_state("No accepted decision rows match the selected filters.")
        return

    high_decision = int((final_view["Decision_Risk"] == "High").sum())
    unique_pairs = final_view[["Product_ID", "Location_ID"]].drop_duplicates().shape[0]
    total_shortage = final_view["Expected_Shortage_Units"].sum()
    total_replenishment = final_view["Recommended_Replenishment_Qty"].sum()
    material_pressure = int(
        (final_view.get("Material_Action_Status", pd.Series(dtype=str)) == "At/Before forecast origin").sum()
    )
    production_pressure = int(
        (final_view.get("Production_Action_Status", pd.Series(dtype=str)) == "At/Before forecast origin").sum()
    )

    cols = st.columns(6)
    with cols[0]:
        kpi("Product x Location Pairs", unique_pairs, "Filtered accepted rows")
    with cols[1]:
        kpi("High Decision Risk Rows", high_decision, "Decision_Risk = High")
    with cols[2]:
        kpi("Expected Shortage Units", total_shortage, "Accepted Phase 9 values")
    with cols[3]:
        kpi("Recommended Finished-Goods Replenishment", total_replenishment, "Planning quantity")
    with cols[4]:
        kpi("Conditional Material Action By", material_pressure, "At/before forecast origin")
    with cols[5]:
        kpi("Conditional Production Start By", production_pressure, "At/before forecast origin")

    c1, c2 = st.columns(2)
    with c1:
        render_fig(risk_distribution(final_view, "Decision_Risk", "Decision Risk Distribution"))
    with c2:
        render_fig(risk_distribution(final_view, "Inventory_Risk", "Inventory Risk Distribution"))

    by_location = (
        final_view.groupby(["Location_ID", "Location_Name", "Channel"], as_index=False)
        .agg(
            Expected_Shortage_Units=("Expected_Shortage_Units", "sum"),
            Recommended_Replenishment_Qty=("Recommended_Replenishment_Qty", "sum"),
            High_Decision_Rows=("Decision_Risk", lambda s: int((s == "High").sum())),
        )
        .sort_values("Expected_Shortage_Units", ascending=False)
    )
    by_location["Location"] = by_location["Location_ID"] + " - " + by_location["Location_Name"]
    c3, c4 = st.columns(2)
    with c3:
        render_fig(
            horizontal_bar(
                by_location,
                "Expected_Shortage_Units",
                "Location",
                "Expected Shortage by Location",
                color="Channel",
                top_n=10,
            )
        )
    with c4:
        by_family = (
            final_view.groupby("Product_Family", as_index=False)
            .agg(
                Recommended_Replenishment_Qty=("Recommended_Replenishment_Qty", "sum"),
                Expected_Shortage_Units=("Expected_Shortage_Units", "sum"),
            )
            .sort_values("Recommended_Replenishment_Qty", ascending=False)
        )
        render_fig(
            vertical_bar(
                by_family,
                "Product_Family",
                "Recommended_Replenishment_Qty",
                "Recommended Finished-Goods Replenishment by Family",
            )
        )

    st.subheader("90-Day Management Priority")
    if filters["horizon"] != 90:
        note(
            "The accepted management priority table is a 90-day management view. "
            "The table below keeps that accepted 90-day ordering and applies only the non-horizon filters.",
            kind="warning",
        )
    else:
        note(
            "This table uses outputs/phase9/management_priority_90d.csv and preserves its accepted ordering.",
            kind="note",
        )
    priority = management_priority_90d_view(data, filters)
    if priority.empty:
        empty_state("No accepted 90-day management priority rows match the selected non-horizon filters.")
        return
    show_table(
        priority.head(30),
        [
            "Product_ID",
            "Product_Name",
            "Location_ID",
            "Location_Name",
            "Channel",
            "Product_Family",
            "Horizon_Days",
            "Forecast_Demand",
            "Available_Stock",
            "Expected_Shortage_Units",
            "Recommended_Replenishment_Qty",
            "Inventory_Risk",
            "Product_Historical_Procurement_Risk",
            "Historical_Production_Risk",
            "Decision_Risk",
            "Decision_Risk_Reason",
            "Conditional_Production_Start_By_Date",
            "Conditional_Material_Action_By_Date",
            "Recommended_Action",
        ],
    )


def page_demand(data: Dict[str, pd.DataFrame], final_view: pd.DataFrame, filters: Dict[str, Any]) -> None:
    st.header("Demand Forecast")
    forecast = align_to_final_context(apply_filters(data["forecast_results"], filters), final_view)
    if forecast.empty:
        empty_state("No accepted forecast rows match the selected filters.")
        return
    note(
        "Forecast values shown here are accepted Phase 5 outputs. "
        "This page does not generate new 30/60/90 forecasts.",
        kind="note",
    )

    cols = st.columns(4)
    with cols[0]:
        kpi("Forecast Rows", len(forecast), "Accepted Phase 5")
    with cols[1]:
        kpi("Forecast Demand", forecast["Forecast_Demand"].sum(), "Filtered cumulative demand")
    with cols[2]:
        kpi("Products", forecast["Product_ID"].nunique(), "Filtered products")
    with cols[3]:
        kpi("Locations", forecast["Location_ID"].nunique(), "Filtered locations")

    c1, c2 = st.columns(2)
    with c1:
        by_horizon = forecast.groupby("Horizon_Days", as_index=False)["Forecast_Demand"].sum()
        render_fig(vertical_bar(by_horizon, "Horizon_Days", "Forecast_Demand", "Forecast Demand by Horizon"))
    with c2:
        source = forecast["Selected_Model_Source"].fillna("Unknown").value_counts().reset_index()
        source.columns = ["Selected_Model_Source", "Rows"]
        render_fig(vertical_bar(source, "Selected_Model_Source", "Rows", "Selected Model Source Count"))

    top = forecast.copy()
    top["Pair"] = top["Product_ID"] + " / " + top["Location_ID"]
    render_fig(
        horizontal_bar(
            top.sort_values("Forecast_Demand", ascending=False),
            "Forecast_Demand",
            "Pair",
            "Top Forecast Demand Rows",
            color="Channel",
            top_n=15,
        )
    )

    st.subheader("Accepted Demand Behavior EDA")
    eda = align_to_final_context(data["demand_series_eda"], final_view)
    c3, c4 = st.columns(2)
    with c3:
        render_fig(scatter_chart(eda, "Demand_Frequency_Pct", "Zero_Demand_Pct", "Intermittency View", color="Demand_Pattern_Class", size="Total_Demand", hover_name="Product_Name"))
    with c4:
        fallback = eda["May_Need_Fallback_Later"].value_counts().rename_axis("May_Need_Fallback_Later").reset_index(name="Series")
        render_fig(vertical_bar(fallback, "May_Need_Fallback_Later", "Series", "Series Flagged for Future Fallback Methods"))

    st.subheader("Historical Daily Demand Panel")
    pair_options = (
        forecast[["Product_ID", "Product_Name", "Location_ID", "Location_Name"]]
        .drop_duplicates()
        .sort_values(["Product_ID", "Location_ID"])
    )
    pair_options["Label"] = (
        pair_options["Product_ID"]
        + " - "
        + pair_options["Product_Name"]
        + " / "
        + pair_options["Location_ID"]
        + " - "
        + pair_options["Location_Name"]
    )
    chosen = st.selectbox("Product x Location to inspect", pair_options["Label"].tolist())
    selected_pair = pair_options[pair_options["Label"] == chosen].iloc[0]
    daily = data["daily_demand_panel"]
    daily_pair = daily[
        (daily["Product_ID"] == selected_pair["Product_ID"])
        & (daily["Location_ID"] == selected_pair["Location_ID"])
    ].copy()
    if daily_pair.empty:
        empty_state("No accepted daily demand panel rows are available for this pair.")
    else:
        daily_pair["Date"] = pd.to_datetime(daily_pair["Date"], errors="coerce")
        daily_pair["28D_Moving_Average"] = daily_pair["Demand_Units"].rolling(28, min_periods=1).mean()
        render_fig(
            line_chart(
                daily_pair,
                "Date",
                "Demand_Units",
                "Daily Demand Units from Accepted Phase 2 Panel",
            )
        )
        render_fig(
            line_chart(
                daily_pair,
                "Date",
                "28D_Moving_Average",
                "28-Day Moving Average for Visual EDA Only",
            )
        )

    st.subheader("Forecast Rows")
    show_table(
        forecast,
        [
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
            "Selection_Reason",
        ],
    )


def page_inventory(data: Dict[str, pd.DataFrame], final_view: pd.DataFrame, filters: Dict[str, Any]) -> None:
    st.header("Inventory & Stockout Risk")
    stockout = align_to_final_context(apply_filters(data["stockout_analysis"], filters), final_view)
    if stockout.empty:
        empty_state("No accepted stockout rows match the selected filters.")
        return

    note(
        "Inventory values are accepted Phase 5 outputs. "
        "<b>Recommended Finished-Goods Replenishment</b> is a planning quantity, not a production order.",
        kind="warning",
    )
    cols = st.columns(5)
    with cols[0]:
        kpi("High Inventory Risk Rows", int((stockout["Inventory_Risk"] == "High").sum()))
    with cols[1]:
        kpi("Expected Shortage Units", stockout["Expected_Shortage_Units"].sum())
    with cols[2]:
        kpi("Available Stock", stockout["Available_Stock"].sum())
    with cols[3]:
        kpi("Recommended Finished-Goods Replenishment", stockout["Recommended_Replenishment_Qty"].sum())
    with cols[4]:
        mismatch_count = int(stockout.get("Latest_Inventory_Accounting_Mismatch_Flag", pd.Series(dtype=bool)).fillna(False).sum())
        kpi("Latest Accounting Mismatch Flags", mismatch_count)

    c1, c2 = st.columns(2)
    with c1:
        render_fig(risk_distribution(stockout, "Inventory_Risk", "Inventory Risk Distribution"))
    with c2:
        view = stockout.copy()
        view["Pair"] = view["Product_ID"] + " / " + view["Location_ID"]
        render_fig(horizontal_bar(view, "Expected_Shortage_Units", "Pair", "Top Expected Shortages", color="Channel"))

    stockout_dates = stockout.dropna(subset=["Estimated_Stockout_Date"]).copy()
    if not stockout_dates.empty:
        stockout_dates["Estimated_Stockout_Date"] = pd.to_datetime(
            stockout_dates["Estimated_Stockout_Date"], errors="coerce"
        )
        timeline = (
            stockout_dates.groupby("Estimated_Stockout_Date", as_index=False)
            .agg(Rows=("Product_ID", "count"), Expected_Shortage_Units=("Expected_Shortage_Units", "sum"))
            .sort_values("Estimated_Stockout_Date")
        )
        render_fig(line_chart(timeline, "Estimated_Stockout_Date", "Rows", "Estimated Stockout Row Count by Date"))

    st.subheader("Stockout Detail")
    show_table(
        stockout.sort_values("Expected_Shortage_Units", ascending=False),
        [
            "Product_ID",
            "Product_Name",
            "Location_ID",
            "Location_Name",
            "Channel",
            "Horizon_Days",
            "Forecast_Demand",
            "Available_Stock",
            "Safety_Stock_Units",
            "Expected_Shortage_Units",
            "Recommended_Replenishment_Qty",
            "Estimated_Stockout_Date",
            "Days_Until_Estimated_Stockout",
            "Inventory_Risk",
            "Inventory_Risk_Reason",
        ],
    )
    csv_download(stockout, "filtered_inventory_stockout_risk.csv")


def page_materials(data: Dict[str, pd.DataFrame], final_view: pd.DataFrame, filters: Dict[str, Any]) -> None:
    st.header("Material Requirements")
    product_material = align_to_final_context(apply_filters(data["product_material_requirements"], filters), final_view)
    material_summary = align_to_final_context(apply_filters(data["material_requirements_summary"], filters), final_view)
    if product_material.empty:
        empty_state("No accepted material requirement rows match the selected filters.")
        return

    note(
        "<b>Gross Material Requirement If Produced</b> is conditional on making the recommended finished-goods replenishment. "
        "It is not a material purchase quantity because no raw-material inventory or open purchase-order balance was assumed.",
        kind="warning",
    )

    cols = st.columns(4)
    with cols[0]:
        kpi("Product-Material Rows", len(product_material))
    with cols[1]:
        kpi("Materials", product_material["Material_ID"].nunique())
    with cols[2]:
        kpi("Products", product_material["Product_ID"].nunique())
    with cols[3]:
        kpi("Units Present", product_material["Unit"].nunique())

    units = sorted(product_material["Unit"].dropna().astype(str).unique().tolist())
    selected_unit = st.selectbox("Material unit for quantity chart", ["All"] + units)
    chart_data = product_material if selected_unit == "All" else product_material[product_material["Unit"] == selected_unit]
    material_chart = (
        chart_data.groupby(["Material_ID", "Material_Name", "Unit"], as_index=False)[
            "Gross_Material_Requirement_If_Produced"
        ]
        .sum()
        .sort_values("Gross_Material_Requirement_If_Produced", ascending=False)
    )
    material_chart["Material"] = material_chart["Material_ID"] + " - " + material_chart["Material_Name"]
    render_fig(
        horizontal_bar(
            material_chart,
            "Gross_Material_Requirement_If_Produced",
            "Material",
            "Gross Material Requirement If Produced",
            color="Unit",
            top_n=15,
        )
    )
    if selected_unit == "All":
        note("Rows may use different units, so compare quantities within each displayed unit.", kind="note")

    st.subheader("Material-Level Accepted Summary")
    show_table(
        material_summary,
        [
            "Material_ID",
            "Material_Name",
            "Material_Category",
            "Unit",
            "Horizon_Days",
            "Products_Using_Material_Count",
            "Products_Requiring_Material_Count",
            "Total_Gross_Material_Requirement_If_Produced",
        ],
    )

    st.subheader("Product-Material Detail")
    show_table(
        product_material.sort_values("Gross_Material_Requirement_If_Produced", ascending=False),
        [
            "Product_ID",
            "Product_Name",
            "Product_Family",
            "Horizon_Days",
            "Production_Equivalent_Replenishment_Qty",
            "Material_ID",
            "Material_Name",
            "Material_Category",
            "Required_Per_Unit",
            "Unit",
            "Standard_Lead_Time_Days",
            "Gross_Material_Requirement_If_Produced",
        ],
    )
    csv_download(product_material, "filtered_gross_material_requirements_if_produced.csv")


def page_procurement(data: Dict[str, pd.DataFrame], final_view: pd.DataFrame, filters: Dict[str, Any]) -> None:
    st.header("Procurement Risk")
    product_summary = align_to_final_context(apply_filters(data["product_procurement_risk_summary"], filters), final_view)
    product_material = align_to_final_context(apply_filters(data["product_material_requirements"], filters), final_view)
    material_risk = apply_filters(data["material_requirement_procurement_risk"], filters)
    if not product_material.empty and "Material_ID" in material_risk.columns:
        material_risk = material_risk[material_risk["Material_ID"].isin(product_material["Material_ID"].unique())]
    if product_summary.empty:
        empty_state("No accepted procurement-risk rows match the selected filters.")
        return

    high_products = int((product_summary["Product_Historical_Procurement_Risk"] == "High").sum())
    procurement_warning = procurement_systemic_warning_values(data)
    note(
        "Systemic warning: under the accepted weakest-link procurement rule, "
        f"<b>{fmt_number(procurement_warning['high_procurement_risk_90_rows'])}</b> of "
        f"<b>{fmt_number(procurement_warning['total_90_rows'])}</b> 90-day product-location rows carry "
        "High product-level historical procurement risk. The most frequent highest-risk material is "
        f"<b>{procurement_warning['top_highest_risk_material']}</b>, appearing in "
        f"<b>{fmt_number(procurement_warning['top_highest_risk_material_rows'])}</b> rows. "
        "Review material-level evidence below to identify the operational driver.",
        kind="danger",
    )

    cols = st.columns(4)
    with cols[0]:
        kpi("Product Historical Procurement Risk = High", high_products)
    with cols[1]:
        kpi(
            f"Rows with {procurement_warning['top_highest_risk_material']} as Highest Risk Material",
            procurement_warning["top_highest_risk_material_rows"],
        )
    with cols[2]:
        kpi("Material-Risk Rows", len(material_risk))
    with cols[3]:
        kpi("Suppliers in History", data["supplier_procurement_history"]["Supplier_ID"].nunique())

    c1, c2 = st.columns(2)
    with c1:
        render_fig(risk_distribution(material_risk, "Historical_Procurement_Risk", "Historical Procurement Risk by Material-Horizon"))
    with c2:
        if not material_risk.empty:
            mat_plot = material_risk.copy()
            mat_plot["Material"] = mat_plot["Material_ID"] + " - " + mat_plot["Material_Name"]
            render_fig(horizontal_bar(mat_plot, "Late_PO_Rate", "Material", "Material Late PO Rate", color="Historical_Procurement_Risk", top_n=15))

    supplier_history = data["supplier_procurement_history"].sort_values("Late_PO_Rate", ascending=False)
    supplier_rank = data["historical_supplier_performance_rank"]
    st.subheader("Material-Level Historical Procurement Risk")
    show_table(
        material_risk.sort_values(["Historical_Procurement_Risk", "Late_PO_Rate"], ascending=[True, False]),
        [
            "Material_ID",
            "Material_Name",
            "Material_Category",
            "Unit",
            "Horizon_Days",
            "Total_Gross_Material_Requirement_If_Produced",
            "PO_Count",
            "Supplier_Count",
            "Evidence_Level",
            "Historical_Procurement_Risk",
            "Procurement_Risk_Reason",
            "Historical_P90_Actual_Lead_Time_Days",
            "Late_PO_Rate",
            "Mean_Rejection_Rate",
        ],
    )

    st.subheader("Historical Supplier Evidence")
    show_table(
        supplier_history,
        [
            "Supplier_ID",
            "Supplier_Name",
            "Primary_Category",
            "Contracted",
            "PO_Count",
            "Material_Count",
            "Mean_Actual_Lead_Time_Days",
            "Historical_P90_Actual_Lead_Time_Days",
            "Late_PO_Rate",
            "On_Time_PO_Rate",
            "Mean_Rejection_Rate",
            "Latest_PO_Date",
        ],
    )
    with st.expander("Historical supplier-material ranks"):
        show_table(
            supplier_rank,
            [
                "Material_ID",
                "Material_Name",
                "Historical_Supplier_Performance_Rank",
                "Supplier_ID",
                "Supplier_Name",
                "PO_Count",
                "Late_PO_Rate",
                "On_Time_PO_Rate",
                "Rejection_Rate",
                "Latest_PO_Date",
            ],
            height=360,
        )


def page_production(data: Dict[str, pd.DataFrame], final_view: pd.DataFrame, filters: Dict[str, Any]) -> None:
    st.header("Production Risk")
    product_risk = align_to_final_context(apply_filters(data["product_replenishment_production_risk"], filters), final_view)
    if product_risk.empty:
        empty_state("No accepted production-risk rows match the selected filters.")
        return

    note(
        "<b>Historical Production Risk</b> is relative evidence from past production performance. "
        "It is not a future production failure prediction or a confirmed production schedule.",
        kind="warning",
    )
    cols = st.columns(5)
    with cols[0]:
        kpi("High Historical Production Risk Rows", int((product_risk["Historical_Production_Risk"] == "High").sum()))
    with cols[1]:
        kpi("Recommended Finished-Goods Replenishment Bridge", product_risk["Production_Equivalent_Replenishment_Qty"].sum())
    with cols[2]:
        kpi("Products", product_risk["Product_ID"].nunique())
    with cols[3]:
        kpi("Mean P90 Production Lead Time", product_risk["P90_Production_Lead_Time_Days"].mean(), decimals=1)
    with cols[4]:
        kpi("Mean Late Production Order Rate", product_risk["Late_Production_Order_Rate"].mean(), decimals=3)

    c1, c2 = st.columns(2)
    with c1:
        render_fig(risk_distribution(product_risk, "Historical_Production_Risk", "Historical Production Risk Distribution"))
    with c2:
        bottlenecks = data["bottleneck_analysis"].sort_values("Bottleneck_Share", ascending=False)
        render_fig(vertical_bar(bottlenecks, "Primary_Bottleneck", "Bottleneck_Share", "Historical Bottleneck Share"))

    c3, c4 = st.columns(2)
    with c3:
        line_history = data["line_production_history"].sort_values("Late_Order_Rate", ascending=False)
        render_fig(vertical_bar(line_history, "Line_ID", "Late_Order_Rate", "Line Late Order Rate"))
    with c4:
        prod_plot = product_risk.copy()
        prod_plot["Product"] = prod_plot["Product_ID"] + " - " + prod_plot["Product_Name"]
        render_fig(horizontal_bar(prod_plot, "Production_Equivalent_Replenishment_Qty", "Product", "Largest Replenishment Bridge by Product", color="Historical_Production_Risk"))

    st.subheader("Product Production Risk Detail")
    show_table(
        product_risk.sort_values("Production_Equivalent_Replenishment_Qty", ascending=False),
        [
            "Product_ID",
            "Product_Name",
            "Product_Family",
            "Horizon_Days",
            "Production_Equivalent_Replenishment_Qty",
            "Locations_Requiring_Replenishment_Count",
            "High_Risk_Locations_Count",
            "Production_Evidence_Level",
            "Historical_Production_Risk",
            "Production_Risk_Reason",
            "Late_Production_Order_Rate",
            "P90_Production_Lead_Time_Days",
            "Mean_Plan_Attainment_Rate",
            "Mean_Efficiency_Pct",
            "Mean_Rejection_Rate",
            "Most_Common_Historical_Primary_Bottleneck",
            "Latest_Production_Date",
        ],
    )


def page_decision_center(data: Dict[str, pd.DataFrame], final_view: pd.DataFrame, filters: Dict[str, Any]) -> None:
    st.header("Final Decision Center")
    note(
        "Decision rules and explanations are accepted Phase 9 outputs. "
        "Conditional dates are planning estimates derived from historical lead-time evidence, not deadlines or purchase orders.",
        kind="warning",
    )
    if final_view.empty:
        empty_state("No accepted final decision rows match the selected filters.")
        return

    cols = st.columns(4)
    with cols[0]:
        kpi("Decision Rows", len(final_view))
    with cols[1]:
        kpi("High Decision Risk", int((final_view["Decision_Risk"] == "High").sum()))
    with cols[2]:
        kpi("Expected Shortage Units", final_view["Expected_Shortage_Units"].sum())
    with cols[3]:
        kpi("Recommended Finished-Goods Replenishment", final_view["Recommended_Replenishment_Qty"].sum())

    decision_rows = final_view.copy()
    decision_rows["Inspect_Label"] = (
        decision_rows["Product_ID"]
        + " / "
        + decision_rows["Location_ID"]
        + " / "
        + decision_rows["Horizon_Days"].astype(str)
        + " days"
    )
    chosen = st.selectbox("Inspect accepted decision row", decision_rows["Inspect_Label"].tolist())
    row = decision_rows[decision_rows["Inspect_Label"] == chosen].iloc[0]

    st.markdown(
        f"""
        <div class="note-box">
        <b>{row['Product_ID']} - {row['Product_Name']}</b><br>
        {row['Location_ID']} - {row['Location_Name']} | {row['Channel']} | Horizon {int(row['Horizon_Days'])} days<br><br>
        Decision Risk: {risk_badge(row['Decision_Risk'])}
        Inventory Risk: {risk_badge(row['Inventory_Risk'])}
        Historical Procurement Risk: {risk_badge(row['Product_Historical_Procurement_Risk'])}
        Historical Production Risk: {risk_badge(row['Historical_Production_Risk'])}
        </div>
        """,
        unsafe_allow_html=True,
    )

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        kpi("Forecast Demand", row["Forecast_Demand"], "Accepted Phase 5")
    with c2:
        kpi("Available Stock", row["Available_Stock"], "Accepted Phase 5")
    with c3:
        kpi("Expected Shortage Units", row["Expected_Shortage_Units"], "Accepted Phase 9")
    with c4:
        kpi("Recommended Finished-Goods Replenishment", row["Recommended_Replenishment_Qty"], "Planning quantity")

    st.subheader("Accepted Reasoning")
    st.write(row["Decision_Risk_Reason"])
    st.write(f"Recommended action: {row['Recommended_Action']}")
    c5, c6 = st.columns(2)
    with c5:
        st.markdown("**Conditional Production Start By**")
        st.write(row.get("Conditional_Production_Start_By_Date", "-"))
        st.caption("Planning estimate based on historical production lead time; not a confirmed schedule.")
    with c6:
        st.markdown("**Conditional Material Action By**")
        st.write(row.get("Conditional_Material_Action_By_Date", "-"))
        st.caption("Planning estimate based on historical procurement lead time; not a purchase-order deadline.")

    trace = data["decision_traceability"]
    trace_row = trace[
        (trace["Product_ID"] == row["Product_ID"])
        & (trace["Location_ID"] == row["Location_ID"])
        & (trace["Horizon_Days"].astype(int) == int(row["Horizon_Days"]))
    ]
    with st.expander("Decision-risk traceability flags"):
        show_table(
            trace_row,
            [
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
            ],
            height=180,
        )

    st.subheader("Filtered Final Decision Table")
    show_table(
        final_view.sort_values(["Decision_Risk", "Expected_Shortage_Units"], ascending=[True, False]),
        [
            "Product_ID",
            "Product_Name",
            "Location_ID",
            "Location_Name",
            "Channel",
            "Product_Family",
            "Horizon_Days",
            "Forecast_Demand",
            "Available_Stock",
            "Expected_Shortage_Units",
            "Recommended_Replenishment_Qty",
            "Estimated_Stockout_Date",
            "Inventory_Risk",
            "Highest_Risk_Material_Name",
            "Product_Historical_Procurement_Risk",
            "Historical_Production_Risk",
            "Decision_Risk",
            "Recommended_Action",
            "Conditional_Production_Start_By_Date",
            "Conditional_Material_Action_By_Date",
        ],
    )
    csv_download(final_view, "filtered_final_decision_recommendations.csv")


def page_model_performance(data: Dict[str, pd.DataFrame], final_view: pd.DataFrame) -> None:
    st.header("Model Performance")
    note(
        "This page reads accepted Phase 3, Phase 4, Phase 4.1, and Phase 5.1 validation outputs. "
        "It does not refit models or change the final forecast.",
        kind="note",
    )
    try:
        metrics = accepted_model_performance_metrics(data)
    except DashboardDataError as exc:
        st.error(str(exc))
        return
    metric_df = pd.DataFrame(metrics)
    c1, c2 = st.columns([1, 1])
    with c1:
        render_fig(metric_delta_bar(metrics, "Accepted Validation WAPE Summary"))
    with c2:
        st.dataframe(metric_df, width="stretch", height=260)

    note(
        "The dashboard does not blindly choose the most complex model because Phase 4.1 showed that "
        "apparent per-series selection was optimistic. The accepted final policy uses guardrails and "
        "falls back when advanced models do not show defensible validation evidence.",
        kind="warning",
    )

    c3, c4 = st.columns(2)
    with c3:
        overall = data["full_coverage_policy_comparison"]
        overall = overall[overall["Segment_Type"] == "overall"].copy()
        render_fig(vertical_bar(overall, "Policy", "Cumulative_WAPE", "Full-Coverage Policy WAPE"))
    with c4:
        source_counts = data["forecast_results"]["Selected_Model_Source"].value_counts().rename_axis("Selected_Model_Source").reset_index(name="Rows")
        render_fig(vertical_bar(source_counts, "Selected_Model_Source", "Rows", "Final Forecast Selected Source Count"))

    st.subheader("Accepted Validation Tables")
    tabs = st.tabs(["Phase 3 Baselines", "Phase 4 Models", "Phase 4.1 Policy", "Phase 5.1 Guarded"])
    with tabs[0]:
        show_table(data["baseline_metrics_overall"], data["baseline_metrics_overall"].columns, height=360)
    with tabs[1]:
        show_table(data["model_metrics_overall"], data["model_metrics_overall"].columns, height=360)
    with tabs[2]:
        show_table(data["policy_comparison"], data["policy_comparison"].columns, height=360)
    with tabs[3]:
        show_table(data["full_coverage_policy_comparison"], data["full_coverage_policy_comparison"].columns, height=360)


def page_methodology(data: Dict[str, pd.DataFrame], manifest: pd.DataFrame) -> None:
    st.header("Methodology & Limitations")
    note(
        "This dashboard is a presentation layer over accepted outputs only. "
        "It is deliberately not a modeling, replenishment optimization, purchase-order, or production scheduling engine.",
        kind="warning",
    )

    st.subheader("Scope")
    st.write(
        "- Dataset scope: only the provided project datasets and accepted Phase 1-9 outputs.\n"
        "- Modeling grain: Product_ID x Location_ID.\n"
        "- Forecast horizons: 30, 60, and 90 days from the accepted forecast origin.\n"
        "- Finished-goods replenishment is a planning quantity, not a production quantity.\n"
        "- Gross material requirement is conditional on producing replenishment and is not a material purchase quantity."
    )

    st.subheader("Key Limitations")
    st.write(
        "- No raw-material inventory was provided, so current material shortages cannot be calculated.\n"
        "- No future supplier availability, open purchase orders, confirmed production schedule, or factory capacity is inferred.\n"
        "- Historical procurement risk and historical production risk are relative evidence from past records, not future guarantees.\n"
        "- Conditional material and production dates are planning estimates, not contractual deadlines.\n"
        "- Phase 2 found inventory accounting mismatches; the data was not altered to force the equation to hold."
    )

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Phase 2 Inventory Accounting Summary")
        show_table(data["inventory_accounting_summary"], ["metric", "value"], height=360)
    with c2:
        st.subheader("Sales vs Inventory Reconciliation Summary")
        show_table(data["sales_inventory_reconciliation_summary"], ["metric", "value"], height=360)

    st.subheader("Forecast Leakage-Risk Table")
    show_table(data["leakage_risk_table"], ["table", "column_or_group", "leakage_risk", "safe_use_rule"], height=360)

    st.subheader("Dashboard Data Manifest")
    show_table(manifest, manifest.columns, height=500)


def main() -> None:
    page_setup()
    try:
        data = load_all_data()
    except DashboardDataError as exc:
        st.error(str(exc))
        st.stop()

    final_df = data["final_decision"]
    filters = get_filters(final_df)
    final_view = apply_filters(final_df, filters)
    manifest = build_data_manifest(data)

    page = filters["page"]
    if page == "Executive Overview":
        page_executive(data, final_view, filters)
    elif page == "Demand Forecast":
        page_demand(data, final_view, filters)
    elif page == "Inventory & Stockout Risk":
        page_inventory(data, final_view, filters)
    elif page == "Material Requirements":
        page_materials(data, final_view, filters)
    elif page == "Procurement Risk":
        page_procurement(data, final_view, filters)
    elif page == "Production Risk":
        page_production(data, final_view, filters)
    elif page == "Final Decision Center":
        page_decision_center(data, final_view, filters)
    elif page == "Model Performance":
        page_model_performance(data, final_view)
    elif page == "Methodology & Limitations":
        page_methodology(data, manifest)


if __name__ == "__main__":
    main()
