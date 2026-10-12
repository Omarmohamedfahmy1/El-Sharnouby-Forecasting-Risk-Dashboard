"""Phase 1 data audit for the El-Sharnouby shortage-risk project.

This script intentionally stops at data understanding. It does not train
forecasting models, generate recommendations, or infer raw-material inventory.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd


DEFAULT_DATA_DIR = Path(r"C:\Users\Acer\Downloads\Sharnouby_Enterprise")
DEFAULT_OUTPUT_DIR = Path("outputs") / "phase1"

EXPECTED_FILES = [
    "Business_Units.csv",
    "Case_Briefs.csv",
    "Customer_Service.csv",
    "Customers.csv",
    "Data_Dictionary.csv",
    "Group_Operations.csv",
    "Inventory_History.csv",
    "Locations.csv",
    "Machine_Downtime.csv",
    "Marketing.csv",
    "Materials.csv",
    "Printing_Batches.csv",
    "Product_BOM.csv",
    "Product_Master.csv",
    "Production_Orders.csv",
    "Purchase_Orders.csv",
    "Quality.csv",
    "Sales_Transactions.csv",
    "Suppliers.csv",
    "Web_Traffic_Daily.csv",
]

KEY_CHECKS = {
    "Business_Units.csv": [["Business_Unit"]],
    "Case_Briefs.csv": [["Card_No"]],
    "Customer_Service.csv": [["Ticket_ID"]],
    "Customers.csv": [["Customer_ID"]],
    "Data_Dictionary.csv": [["Table"]],
    "Group_Operations.csv": [["Month", "Business_Unit", "Primary_KPI"]],
    "Inventory_History.csv": [["Snapshot_Month", "Location_ID", "Product_ID"]],
    "Locations.csv": [["Location_ID"]],
    "Machine_Downtime.csv": [["Downtime_ID"]],
    "Marketing.csv": [["Campaign_ID"]],
    "Materials.csv": [["Material_ID"]],
    "Printing_Batches.csv": [["Print_Batch_ID"]],
    "Product_BOM.csv": [["Product_ID", "Material_ID"]],
    "Product_Master.csv": [["Product_ID"], ["SKU"]],
    "Production_Orders.csv": [["Production_Order_ID"]],
    "Purchase_Orders.csv": [["PO_ID"]],
    "Quality.csv": [["QC_ID"]],
    "Sales_Transactions.csv": [["Row_ID"], ["Invoice_ID"]],
    "Suppliers.csv": [["Supplier_ID"]],
    "Web_Traffic_Daily.csv": [["Date"]],
}

DATE_HINTS = ("date", "month", "completion", "due")
CORE_REQUIRED = {
    "Data_Dictionary.csv": "Project metadata and table grain reference.",
    "Sales_Transactions.csv": "Demand history at Product_ID x Location_ID.",
    "Inventory_History.csv": "Finished-goods stock history for shortage logic.",
    "Product_Master.csv": "Product attributes and product ID reference.",
    "Locations.csv": "Location/channel reference.",
    "Product_BOM.csv": "Product-to-material requirements.",
    "Materials.csv": "Material reference and standard lead times.",
    "Purchase_Orders.csv": "Historical procurement lead time, delay, and rejection evidence.",
    "Suppliers.csv": "Supplier reference for procurement history.",
    "Production_Orders.csv": "Historical production efficiency, delay, and yield evidence.",
}


@dataclass
class AuditFrames:
    tables: dict[str, pd.DataFrame]
    table_summary: pd.DataFrame
    missing_summary: pd.DataFrame
    date_ranges: pd.DataFrame
    key_checks: pd.DataFrame
    relationship_integrity: pd.DataFrame
    dataset_relevance: pd.DataFrame
    sales_pair_sparsity: pd.DataFrame
    inventory_latest: pd.DataFrame
    procurement_summary: pd.DataFrame
    production_summary: pd.DataFrame
    dictionary_file_status: pd.DataFrame


def read_csvs(data_dir: Path) -> dict[str, pd.DataFrame]:
    tables: dict[str, pd.DataFrame] = {}
    for file_name in EXPECTED_FILES:
        path = data_dir / file_name
        if path.exists():
            tables[file_name] = pd.read_csv(path)
    return tables


def date_like_columns(columns: Iterable[str]) -> list[str]:
    return [
        col
        for col in columns
        if any(hint in col.lower() for hint in DATE_HINTS)
        or col.lower() in {"month_key", "snapshot_month"}
    ]


def summarize_tables(tables: dict[str, pd.DataFrame], data_dir: Path) -> pd.DataFrame:
    rows = []
    for file_name, df in tables.items():
        path = data_dir / file_name
        rows.append(
            {
                "table": file_name,
                "rows": len(df),
                "columns": len(df.columns),
                "duplicate_full_rows": int(df.duplicated().sum()),
                "file_size_mb": round(path.stat().st_size / (1024 * 1024), 3),
                "columns_list": ", ".join(df.columns),
            }
        )
    return pd.DataFrame(rows).sort_values("table")


def summarize_missing(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows = []
    for file_name, df in tables.items():
        for col in df.columns:
            missing = int(df[col].isna().sum())
            rows.append(
                {
                    "table": file_name,
                    "column": col,
                    "dtype": str(df[col].dtype),
                    "missing_count": missing,
                    "missing_pct": round((missing / len(df)) * 100, 3) if len(df) else 0.0,
                    "unique_count": int(df[col].nunique(dropna=True)),
                }
            )
    return pd.DataFrame(rows).sort_values(["table", "missing_pct", "column"], ascending=[True, False, True])


def summarize_dates(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows = []
    for file_name, df in tables.items():
        for col in date_like_columns(df.columns):
            parsed = pd.to_datetime(df[col], errors="coerce")
            rows.append(
                {
                    "table": file_name,
                    "column": col,
                    "valid_dates": int(parsed.notna().sum()),
                    "invalid_or_missing": int(parsed.isna().sum()),
                    "min_date": parsed.min().date().isoformat() if parsed.notna().any() else "",
                    "max_date": parsed.max().date().isoformat() if parsed.notna().any() else "",
                }
            )
    return pd.DataFrame(rows).sort_values(["table", "column"])


def check_keys(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows = []
    for file_name, checks in KEY_CHECKS.items():
        df = tables.get(file_name)
        if df is None:
            continue
        for key_cols in checks:
            available = [col for col in key_cols if col in df.columns]
            if len(available) != len(key_cols):
                rows.append(
                    {
                        "table": file_name,
                        "key_columns": " + ".join(key_cols),
                        "available": False,
                        "rows": len(df),
                        "null_key_rows": np.nan,
                        "duplicate_key_rows": np.nan,
                        "unique_keys": np.nan,
                    }
                )
                continue
            null_key_rows = int(df[available].isna().any(axis=1).sum())
            duplicate_key_rows = int(df.duplicated(subset=available, keep=False).sum())
            unique_keys = int(df[available].drop_duplicates().shape[0])
            rows.append(
                {
                    "table": file_name,
                    "key_columns": " + ".join(key_cols),
                    "available": True,
                    "rows": len(df),
                    "null_key_rows": null_key_rows,
                    "duplicate_key_rows": duplicate_key_rows,
                    "unique_keys": unique_keys,
                }
            )
    return pd.DataFrame(rows).sort_values(["table", "key_columns"])


def add_integrity_row(
    rows: list[dict[str, object]],
    source_table: str,
    source_key: str,
    reference_table: str,
    missing_values: set[object],
) -> None:
    examples = sorted(str(value) for value in list(missing_values)[:10])
    rows.append(
        {
            "source_table": source_table,
            "source_key": source_key,
            "reference_table": reference_table,
            "missing_in_reference_count": len(missing_values),
            "example_missing_values": ", ".join(examples),
        }
    )


def relationship_integrity(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    products = set(tables["Product_Master.csv"]["Product_ID"].dropna()) if "Product_Master.csv" in tables else set()
    locations = set(tables["Locations.csv"]["Location_ID"].dropna()) if "Locations.csv" in tables else set()
    materials = set(tables["Materials.csv"]["Material_ID"].dropna()) if "Materials.csv" in tables else set()
    suppliers = set(tables["Suppliers.csv"]["Supplier_ID"].dropna()) if "Suppliers.csv" in tables else set()
    customers = set(tables["Customers.csv"]["Customer_ID"].dropna()) if "Customers.csv" in tables else set()

    for file_name, df in tables.items():
        if "Product_ID" in df.columns and products:
            add_integrity_row(
                rows,
                file_name,
                "Product_ID",
                "Product_Master.csv",
                set(df["Product_ID"].dropna()) - products,
            )
        if "Location_ID" in df.columns and locations:
            add_integrity_row(
                rows,
                file_name,
                "Location_ID",
                "Locations.csv",
                set(df["Location_ID"].dropna()) - locations,
            )
        if "Material_ID" in df.columns and materials:
            add_integrity_row(
                rows,
                file_name,
                "Material_ID",
                "Materials.csv",
                set(df["Material_ID"].dropna()) - materials,
            )
        if "Supplier_ID" in df.columns and suppliers:
            add_integrity_row(
                rows,
                file_name,
                "Supplier_ID",
                "Suppliers.csv",
                set(df["Supplier_ID"].dropna()) - suppliers,
            )
        if "Customer_ID" in df.columns and customers:
            add_integrity_row(
                rows,
                file_name,
                "Customer_ID",
                "Customers.csv",
                set(df["Customer_ID"].dropna()) - customers,
            )
    return pd.DataFrame(rows).sort_values(["source_table", "source_key"])


def assess_dataset_relevance(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows = []
    for file_name in sorted(tables):
        if file_name in CORE_REQUIRED:
            relevance = "Required"
            rationale = CORE_REQUIRED[file_name]
        elif file_name in {"Marketing.csv", "Web_Traffic_Daily.csv"}:
            relevance = "Optional later"
            rationale = "Potential exogenous demand context, but not required for a defensible first forecasting grain."
        elif file_name in {"Quality.csv", "Printing_Batches.csv", "Machine_Downtime.csv"}:
            relevance = "Optional later"
            rationale = "May enrich production or quality risk, but Production_Orders.csv is the primary required production-risk source."
        else:
            relevance = "Not required for current shortage-risk scope"
            rationale = "Useful for other case briefs, but not needed to answer Product x Location shortage and replenishment questions."
        rows.append({"table": file_name, "phase1_relevance": relevance, "rationale": rationale})
    return pd.DataFrame(rows)


def analyze_sales_sparsity(sales: pd.DataFrame) -> pd.DataFrame:
    work = sales.copy()
    work["Order_Date"] = pd.to_datetime(work["Order_Date"], errors="coerce")
    daily = (
        work.dropna(subset=["Order_Date", "Product_ID", "Location_ID"])
        .groupby(["Product_ID", "Location_ID", "Order_Date"], as_index=False)["Quantity"]
        .sum()
    )
    if daily.empty:
        return pd.DataFrame()

    global_start = daily["Order_Date"].min()
    global_end = daily["Order_Date"].max()
    global_days = max((global_end - global_start).days + 1, 1)

    pair = (
        daily.groupby(["Product_ID", "Location_ID"])
        .agg(
            first_order_date=("Order_Date", "min"),
            last_order_date=("Order_Date", "max"),
            sales_days=("Order_Date", "nunique"),
            total_quantity=("Quantity", "sum"),
            mean_daily_quantity_when_sold=("Quantity", "mean"),
        )
        .reset_index()
    )
    pair["active_days"] = (pair["last_order_date"] - pair["first_order_date"]).dt.days + 1
    pair["active_sales_day_ratio"] = (pair["sales_days"] / pair["active_days"]).round(4)
    pair["global_sales_day_ratio"] = (pair["sales_days"] / global_days).round(4)
    pair["first_order_date"] = pair["first_order_date"].dt.date.astype(str)
    pair["last_order_date"] = pair["last_order_date"].dt.date.astype(str)

    conditions = [
        pair["active_sales_day_ratio"] >= 0.60,
        pair["active_sales_day_ratio"] >= 0.25,
        pair["active_sales_day_ratio"] >= 0.05,
    ]
    labels = ["dense", "moderate", "sparse"]
    pair["frequency_class"] = np.select(conditions, labels, default="intermittent")
    return pair.sort_values(["frequency_class", "Product_ID", "Location_ID"])


def analyze_inventory_latest(inventory: pd.DataFrame) -> pd.DataFrame:
    work = inventory.copy()
    work["Snapshot_Month"] = pd.to_datetime(work["Snapshot_Month"], errors="coerce")
    latest_idx = work.groupby(["Product_ID", "Location_ID"])["Snapshot_Month"].idxmax()
    latest = work.loc[latest_idx].copy()
    keep_cols = [
        "Product_ID",
        "Location_ID",
        "Location_Name",
        "Snapshot_Month",
        "Closing_Stock",
        "Safety_Stock_Units",
        "Reorder_Point_Units",
        "Days_of_Cover",
        "Stockout_Days_In_Month",
    ]
    latest = latest[[col for col in keep_cols if col in latest.columns]]
    latest["Snapshot_Month"] = latest["Snapshot_Month"].dt.date.astype(str)
    return latest.sort_values(["Product_ID", "Location_ID"])


def procurement_history_summary(purchase_orders: pd.DataFrame) -> pd.DataFrame:
    work = purchase_orders.copy()
    for col in ["Order_Date", "Promised_Date", "Actual_Receipt_Date"]:
        work[col] = pd.to_datetime(work[col], errors="coerce")
    work["actual_lead_time_days"] = (work["Actual_Receipt_Date"] - work["Order_Date"]).dt.days
    work["receipt_delay_days"] = (work["Actual_Receipt_Date"] - work["Promised_Date"]).dt.days
    work["accepted_ratio"] = np.where(
        (work["Accepted_Qty"] + work["Rejected_Qty"]) > 0,
        work["Accepted_Qty"] / (work["Accepted_Qty"] + work["Rejected_Qty"]),
        np.nan,
    )

    summary = (
        work.groupby("Material_ID")
        .agg(
            po_count=("PO_ID", "count"),
            supplier_count=("Supplier_ID", "nunique"),
            first_order_date=("Order_Date", "min"),
            last_receipt_date=("Actual_Receipt_Date", "max"),
            median_actual_lead_time_days=("actual_lead_time_days", "median"),
            p90_actual_lead_time_days=("actual_lead_time_days", lambda s: s.quantile(0.90)),
            median_receipt_delay_days=("receipt_delay_days", "median"),
            p90_receipt_delay_days=("receipt_delay_days", lambda s: s.quantile(0.90)),
            mean_accepted_ratio=("accepted_ratio", "mean"),
        )
        .reset_index()
    )
    for col in ["first_order_date", "last_receipt_date"]:
        summary[col] = summary[col].dt.date.astype(str)
    return summary.sort_values("Material_ID")


def production_history_summary(production_orders: pd.DataFrame) -> pd.DataFrame:
    work = production_orders.copy()
    for col in ["Start_Date", "Due_Date", "Completion_Date"]:
        work[col] = pd.to_datetime(work[col], errors="coerce")
    work["actual_duration_days"] = (work["Completion_Date"] - work["Start_Date"]).dt.days
    work["good_qty_ratio"] = np.where(work["Produced_Qty"] > 0, work["Good_Qty"] / work["Produced_Qty"], np.nan)

    summary = (
        work.groupby("Product_ID")
        .agg(
            production_order_count=("Production_Order_ID", "count"),
            first_start_date=("Start_Date", "min"),
            last_completion_date=("Completion_Date", "max"),
            median_actual_duration_days=("actual_duration_days", "median"),
            median_delay_days=("Delay_Days", "median"),
            p90_delay_days=("Delay_Days", lambda s: s.quantile(0.90)),
            mean_efficiency_pct=("Efficiency_Pct", "mean"),
            mean_good_qty_ratio=("good_qty_ratio", "mean"),
            bottleneck_count=("Primary_Bottleneck", lambda s: s.notna().sum()),
        )
        .reset_index()
    )
    for col in ["first_start_date", "last_completion_date"]:
        summary[col] = summary[col].dt.date.astype(str)
    return summary.sort_values("Product_ID")


def dictionary_file_status(tables: dict[str, pd.DataFrame], data_dir: Path) -> pd.DataFrame:
    dictionary = tables.get("Data_Dictionary.csv")
    if dictionary is None:
        return pd.DataFrame()

    rows = []
    actual_files = {path.name for path in data_dir.glob("*.csv")}
    for file_name in dictionary["Table"].dropna():
        rows.append(
            {
                "dictionary_table": file_name,
                "present_in_folder": (data_dir / file_name).exists(),
                "grain": dictionary.loc[dictionary["Table"] == file_name, "Grain"].iloc[0],
            }
        )
    for extra_file in sorted(actual_files - set(dictionary["Table"].dropna())):
        rows.append({"dictionary_table": extra_file, "present_in_folder": True, "grain": "Not listed in dictionary"})
    return pd.DataFrame(rows)


def run_audit(data_dir: Path) -> AuditFrames:
    tables = read_csvs(data_dir)
    table_summary = summarize_tables(tables, data_dir)
    missing = summarize_missing(tables)
    dates = summarize_dates(tables)
    keys = check_keys(tables)
    integrity = relationship_integrity(tables)
    relevance = assess_dataset_relevance(tables)
    sales_sparsity = analyze_sales_sparsity(tables["Sales_Transactions.csv"])
    inventory_latest = analyze_inventory_latest(tables["Inventory_History.csv"])
    procurement = procurement_history_summary(tables["Purchase_Orders.csv"])
    production = production_history_summary(tables["Production_Orders.csv"])
    dictionary_status = dictionary_file_status(tables, data_dir)
    return AuditFrames(
        tables=tables,
        table_summary=table_summary,
        missing_summary=missing,
        date_ranges=dates,
        key_checks=keys,
        relationship_integrity=integrity,
        dataset_relevance=relevance,
        sales_pair_sparsity=sales_sparsity,
        inventory_latest=inventory_latest,
        procurement_summary=procurement,
        production_summary=production,
        dictionary_file_status=dictionary_status,
    )


def fmt_int(value: int | float) -> str:
    if pd.isna(value):
        return "n/a"
    return f"{int(value):,}"


def range_for(date_ranges: pd.DataFrame, table: str, column: str) -> str:
    match = date_ranges[(date_ranges["table"] == table) & (date_ranges["column"] == column)]
    if match.empty:
        return "n/a"
    row = match.iloc[0]
    return f"{row['min_date']} to {row['max_date']} ({fmt_int(row['valid_dates'])} valid)"


def top_missing(missing: pd.DataFrame, table: str, n: int = 5) -> str:
    subset = missing[(missing["table"] == table) & (missing["missing_count"] > 0)].head(n)
    if subset.empty:
        return "No missing values detected."
    return "; ".join(
        f"{row.column}: {fmt_int(row.missing_count)} ({row.missing_pct}%)"
        for row in subset.itertuples(index=False)
    )


def duplicate_key_text(key_checks: pd.DataFrame) -> str:
    duplicate_rows = key_checks[key_checks["duplicate_key_rows"].fillna(0) > 0]
    if duplicate_rows.empty:
        return "No duplicate rows found for the Phase 1 candidate primary/composite keys."
    return "; ".join(
        f"{row.table} [{row.key_columns}]: {fmt_int(row.duplicate_key_rows)} duplicate-key rows"
        for row in duplicate_rows.itertuples(index=False)
    )


def relationship_issues_text(integrity: pd.DataFrame) -> str:
    issues = integrity[integrity["missing_in_reference_count"] > 0]
    if issues.empty:
        return "No missing Product_ID, Location_ID, Material_ID, Supplier_ID, or Customer_ID references detected in the audited tables."
    return "; ".join(
        f"{row.source_table}.{row.source_key} missing from {row.reference_table}: {fmt_int(row.missing_in_reference_count)}"
        for row in issues.itertuples(index=False)
    )


def build_report(frames: AuditFrames, data_dir: Path, output_dir: Path) -> str:
    tables = frames.tables
    table_summary = frames.table_summary.set_index("table")
    sales = tables["Sales_Transactions.csv"].copy()
    sales["Order_Date"] = pd.to_datetime(sales["Order_Date"], errors="coerce")
    inventory = tables["Inventory_History.csv"].copy()
    inventory["Snapshot_Month"] = pd.to_datetime(inventory["Snapshot_Month"], errors="coerce")
    product_master = tables["Product_Master.csv"]
    locations = tables["Locations.csv"]
    bom = tables["Product_BOM.csv"]
    materials = tables["Materials.csv"]
    purchase_orders = tables["Purchase_Orders.csv"].copy()
    production_orders = tables["Production_Orders.csv"].copy()

    sales_pairs = sales[["Product_ID", "Location_ID"]].drop_duplicates()
    inventory_pairs = inventory[["Product_ID", "Location_ID"]].drop_duplicates()
    all_master_location_pairs = len(product_master["Product_ID"].dropna().unique()) * len(
        locations["Location_ID"].dropna().unique()
    )
    missing_inventory_pairs = len(
        sales_pairs.merge(inventory_pairs, on=["Product_ID", "Location_ID"], how="left", indicator=True).query(
            "_merge == 'left_only'"
        )
    )
    inventory_only_pairs = len(
        inventory_pairs.merge(sales_pairs, on=["Product_ID", "Location_ID"], how="left", indicator=True).query(
            "_merge == 'left_only'"
        )
    )
    sales_location_ids = set(sales["Location_ID"].dropna())
    inventory_location_ids = set(inventory["Location_ID"].dropna())
    master_location_ids = set(locations["Location_ID"].dropna())
    non_sales_locations = sorted(master_location_ids - sales_location_ids)
    non_inventory_locations = sorted(master_location_ids - inventory_location_ids)

    dictionary_missing = frames.dictionary_file_status[
        frames.dictionary_file_status["present_in_folder"] == False  # noqa: E712
    ]

    sparsity_counts = frames.sales_pair_sparsity["frequency_class"].value_counts().to_dict()
    sparsity_text = ", ".join(f"{key}: {fmt_int(value)}" for key, value in sorted(sparsity_counts.items()))

    bom_products = set(bom["Product_ID"].dropna())
    master_products = set(product_master["Product_ID"].dropna())
    bom_materials = set(bom["Material_ID"].dropna())
    material_master = set(materials["Material_ID"].dropna())
    sales_products = set(sales["Product_ID"].dropna())
    production_products = set(production_orders["Product_ID"].dropna())

    purchase_orders["Order_Date"] = pd.to_datetime(purchase_orders["Order_Date"], errors="coerce")
    purchase_orders["Promised_Date"] = pd.to_datetime(purchase_orders["Promised_Date"], errors="coerce")
    purchase_orders["Actual_Receipt_Date"] = pd.to_datetime(purchase_orders["Actual_Receipt_Date"], errors="coerce")
    po_actual_lead = (purchase_orders["Actual_Receipt_Date"] - purchase_orders["Order_Date"]).dt.days
    po_delay = (purchase_orders["Actual_Receipt_Date"] - purchase_orders["Promised_Date"]).dt.days

    production_orders["Start_Date"] = pd.to_datetime(production_orders["Start_Date"], errors="coerce")
    production_orders["Completion_Date"] = pd.to_datetime(production_orders["Completion_Date"], errors="coerce")
    production_duration = (production_orders["Completion_Date"] - production_orders["Start_Date"]).dt.days

    latest_inventory_dates = inventory.groupby(["Product_ID", "Location_ID"])["Snapshot_Month"].max()

    report = f"""# Phase 1 Data Audit Report

Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

Data directory: `{data_dir}`

## Scope Boundary

This is Phase 1 only: data audit and project understanding. No forecasting model, Streamlit dashboard, replenishment output, or final risk score was built.

Important inventory boundary: `Inventory_History.csv` is finished-goods inventory at month x location x product grain. The provided files do not contain a current raw-material inventory table. Later phases can calculate material quantities required from the BOM and procurement risk from historical purchase orders, but they must not claim current raw-material stock.

## Files Inspected

- CSV files found and read: {fmt_int(len(tables))}
- PDF present: {"yes" if (data_dir / "EL_SHARNOUBY_GROUP_HVIA_TASK02.pdf").exists() else "no"}
- Data dictionary listed file missing from folder: {", ".join(dictionary_missing["dictionary_table"]) if not dictionary_missing.empty else "none"}

## Dataset Summary

| Dataset | Rows | Columns | Full duplicate rows |
|---|---:|---:|---:|
"""

    for row in frames.table_summary.sort_values("table").itertuples(index=False):
        report += f"| {row.table} | {fmt_int(row.rows)} | {fmt_int(row.columns)} | {fmt_int(row.duplicate_full_rows)} |\n"

    report += f"""
## Primary Keys And Duplicate-Key Checks

Candidate keys were checked from the declared grain and observed columns. {duplicate_key_text(frames.key_checks)}

Full details are exported to `key_checks.csv`.

## Date Ranges

- Sales order history: {range_for(frames.date_ranges, "Sales_Transactions.csv", "Order_Date")}
- Inventory snapshots: {range_for(frames.date_ranges, "Inventory_History.csv", "Snapshot_Month")}
- Purchase order dates: {range_for(frames.date_ranges, "Purchase_Orders.csv", "Order_Date")}
- Purchase receipt dates: {range_for(frames.date_ranges, "Purchase_Orders.csv", "Actual_Receipt_Date")}
- Production start dates: {range_for(frames.date_ranges, "Production_Orders.csv", "Start_Date")}
- Production completion dates: {range_for(frames.date_ranges, "Production_Orders.csv", "Completion_Date")}

## Missing Values

High-level missingness notes:

- Sales_Transactions.csv: {top_missing(frames.missing_summary, "Sales_Transactions.csv")}
- Inventory_History.csv: {top_missing(frames.missing_summary, "Inventory_History.csv")}
- Product_BOM.csv: {top_missing(frames.missing_summary, "Product_BOM.csv")}
- Materials.csv: {top_missing(frames.missing_summary, "Materials.csv")}
- Purchase_Orders.csv: {top_missing(frames.missing_summary, "Purchase_Orders.csv")}
- Production_Orders.csv: {top_missing(frames.missing_summary, "Production_Orders.csv")}

Full missing-value detail is exported to `missing_values.csv`.

## Product And Location Consistency

{relationship_issues_text(frames.relationship_integrity)}

- Products in Product_Master.csv: {fmt_int(product_master["Product_ID"].nunique())}
- Locations in Locations.csv: {fmt_int(locations["Location_ID"].nunique())}
- Product x Location combinations theoretically possible from master data: {fmt_int(all_master_location_pairs)}
- Product x Location combinations observed in sales: {fmt_int(len(sales_pairs))}
- Product x Location combinations observed in inventory history: {fmt_int(len(inventory_pairs))}
- Sales Product x Location pairs missing inventory history: {fmt_int(missing_inventory_pairs)}
- Inventory Product x Location pairs without sales rows: {fmt_int(inventory_only_pairs)}
- Locations represented in sales and inventory: {", ".join(sorted(sales_location_ids & inventory_location_ids))}
- Master locations without sales rows: {", ".join(non_sales_locations) if non_sales_locations else "none"}
- Master locations without inventory rows: {", ".join(non_inventory_locations) if non_inventory_locations else "none"}

## Sales History, Frequency, And Sparsity

- Sales rows: {fmt_int(len(sales))}
- Distinct invoices: {fmt_int(sales["Invoice_ID"].nunique())}
- Distinct products sold: {fmt_int(sales["Product_ID"].nunique())}
- Distinct locations sold: {fmt_int(sales["Location_ID"].nunique())}
- Distinct Product x Location sales pairs: {fmt_int(len(sales_pairs))}
- Quantity sold total: {fmt_int(sales["Quantity"].sum())}
- Sales frequency classes by active selling-day ratio: {sparsity_text}

The sales data is not equally dense for every Product x Location pair. Phase 2 should keep the Product_ID x Location_ID grain, but profile sparse or intermittent pairs before choosing fallback rules for modeling.

## Inventory History

- Inventory rows: {fmt_int(len(inventory))}
- Inventory Product x Location pairs: {fmt_int(len(inventory_pairs))}
- Inventory snapshot range: {range_for(frames.date_ranges, "Inventory_History.csv", "Snapshot_Month")}
- Latest inventory snapshot across pairs ranges from {latest_inventory_dates.min().date().isoformat()} to {latest_inventory_dates.max().date().isoformat()}.
- Finished-goods fields available for later shortage logic: `Closing_Stock`, `Safety_Stock_Units`, `Reorder_Point_Units`, `Days_of_Cover`, `Stockout_Days_In_Month`.

This table is not raw-material inventory. It should be used only as Product x Location finished-goods stock evidence.

## BOM And Material Coverage

- BOM product count: {fmt_int(len(bom_products))}
- Products in Product_Master.csv missing from BOM: {fmt_int(len(master_products - bom_products))}
- BOM products missing from Product_Master.csv: {fmt_int(len(bom_products - master_products))}
- BOM materials count: {fmt_int(len(bom_materials))}
- BOM materials missing from Materials.csv: {fmt_int(len(bom_materials - material_master))}
- Materials in Materials.csv without BOM usage: {fmt_int(len(material_master - bom_materials))}

Material requirements can be calculated later as recommended production quantity x `Required_Per_Unit`, preserving the BOM unit. No current material stock can be calculated from the provided tables.

## Purchase-Order History

- Purchase-order rows: {fmt_int(len(purchase_orders))}
- Materials with purchase history: {fmt_int(purchase_orders["Material_ID"].nunique())}
- Suppliers with purchase history: {fmt_int(purchase_orders["Supplier_ID"].nunique())}
- Median actual lead time: {po_actual_lead.median():.1f} days
- 90th percentile actual lead time: {po_actual_lead.quantile(0.90):.1f} days
- Median receipt delay vs promised date: {po_delay.median():.1f} days
- 90th percentile receipt delay vs promised date: {po_delay.quantile(0.90):.1f} days

Purchase orders support historical procurement risk, not current supplier availability or current raw-material stock.

## Production-Order History

- Production-order rows: {fmt_int(len(production_orders))}
- Products with production history: {fmt_int(len(production_products))}
- Sales products without production history: {fmt_int(len(sales_products - production_products))}
- Median actual production duration: {production_duration.median():.1f} days
- Median delay: {production_orders["Delay_Days"].median():.1f} days
- 90th percentile delay: {production_orders["Delay_Days"].quantile(0.90):.1f} days
- Mean efficiency: {production_orders["Efficiency_Pct"].mean():.1f}%

Production orders support historical production-risk indicators. They do not prove exact future capacity.

## Necessary Datasets For This Project

Required for the shortage-risk decision app:

- `Sales_Transactions.csv`
- `Inventory_History.csv`
- `Product_Master.csv`
- `Locations.csv`
- `Product_BOM.csv`
- `Materials.csv`
- `Purchase_Orders.csv`
- `Suppliers.csv`
- `Production_Orders.csv`
- `Data_Dictionary.csv`

Optional later, if they improve defensible analysis: `Marketing.csv`, `Web_Traffic_Daily.csv`, `Quality.csv`, `Printing_Batches.csv`, `Machine_Downtime.csv`.

Not required for the core Product x Location shortage question: `Customers.csv`, `Customer_Service.csv`, `Business_Units.csv`, `Group_Operations.csv`, `Case_Briefs.csv`.

## Proposed Relationship Map

- `Product_Master.Product_ID` -> `Sales_Transactions.Product_ID`, `Inventory_History.Product_ID`, `Product_BOM.Product_ID`, `Production_Orders.Product_ID`, plus optional production/quality/marketing tables.
- `Locations.Location_ID` -> `Sales_Transactions.Location_ID`, `Inventory_History.Location_ID`.
- `Product_BOM.Product_ID` + `Product_BOM.Material_ID` links finished goods to material requirements.
- `Materials.Material_ID` -> `Product_BOM.Material_ID`, `Purchase_Orders.Material_ID`.
- `Suppliers.Supplier_ID` -> `Purchase_Orders.Supplier_ID`.
- `Sales_Transactions.Customer_ID` -> `Customers.Customer_ID`, but customer analysis is outside the core Phase 1 shortage scope.

## Proposed Modeling Grain

The defensible modeling grain remains `Product_ID x Location_ID`, because both demand and finished-goods inventory share that grain. Phase 2 should create daily demand series per pair, audit returns treatment, inspect zero-demand days, and define explicit fallback rules for pairs with sparse/intermittent demand before any model is trained.

## Limitations And Blockers Before Modeling

- No raw-material current inventory table is present. Do not calculate or display current material stock.
- `Data_Dictionary.csv` references `Sources.csv`, but that file is not present in the folder.
- Product x Location demand is unevenly dense; some pairs may require fallback forecasting rules.
- Inventory is monthly while sales is daily, so Phase 2 must define how latest monthly finished-goods stock is aligned with daily forecasts.
- Later action-date logic must rely on available lead-time evidence and should be labeled as planning guidance, not exact capacity scheduling.

## Phase 2 Recommendation

Proceed with data cleaning and EDA only after approval. Recommended Phase 2 tasks:

- Normalize date types and key columns.
- Decide whether returns reduce demand or are analyzed separately.
- Build daily Product x Location demand tables with explicit zero-demand handling.
- Align latest finished-goods inventory to Product x Location demand.
- Profile sparse/intermittent pairs and document fallback rules.
- Keep raw-material inventory out of scope unless a provided table explicitly supplies it.

## Files Created By Phase 1

- `{output_dir / "phase1_data_audit_report.md"}`
- `{output_dir / "table_summary.csv"}`
- `{output_dir / "missing_values.csv"}`
- `{output_dir / "date_ranges.csv"}`
- `{output_dir / "key_checks.csv"}`
- `{output_dir / "relationship_integrity.csv"}`
- `{output_dir / "dataset_relevance.csv"}`
- `{output_dir / "sales_pair_sparsity.csv"}`
- `{output_dir / "inventory_latest_by_product_location.csv"}`
- `{output_dir / "procurement_history_by_material.csv"}`
- `{output_dir / "production_history_by_product.csv"}`
- `{output_dir / "dictionary_file_status.csv"}`
- `src/phase1_audit.py`
"""
    return report


def write_outputs(frames: AuditFrames, data_dir: Path, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    exports = {
        "table_summary.csv": frames.table_summary,
        "missing_values.csv": frames.missing_summary,
        "date_ranges.csv": frames.date_ranges,
        "key_checks.csv": frames.key_checks,
        "relationship_integrity.csv": frames.relationship_integrity,
        "dataset_relevance.csv": frames.dataset_relevance,
        "sales_pair_sparsity.csv": frames.sales_pair_sparsity,
        "inventory_latest_by_product_location.csv": frames.inventory_latest,
        "procurement_history_by_material.csv": frames.procurement_summary,
        "production_history_by_product.csv": frames.production_summary,
        "dictionary_file_status.csv": frames.dictionary_file_status,
    }
    for file_name, frame in exports.items():
        frame.to_csv(output_dir / file_name, index=False, encoding="utf-8")

    report_path = output_dir / "phase1_data_audit_report.md"
    report_path.write_text(build_report(frames, data_dir, output_dir), encoding="utf-8")
    return report_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Phase 1 data audit.")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    data_dir = args.data_dir.resolve()
    output_dir = args.output_dir.resolve()
    if not data_dir.exists():
        raise FileNotFoundError(f"Data directory not found: {data_dir}")

    frames = run_audit(data_dir)
    report_path = write_outputs(frames, data_dir, output_dir)
    print(f"Phase 1 audit complete: {report_path}")


if __name__ == "__main__":
    main()
