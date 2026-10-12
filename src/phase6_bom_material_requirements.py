"""Phase 6 BOM and gross material requirements.

This phase converts accepted Phase 5 replenishment quantities into BOM-based
gross material requirements. It does not calculate procurement risk, supplier
risk, material availability, production risk, purchase quantities, or final
combined risk.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from phase3_forecasting_baseline import HORIZONS, fmt, markdown_table


DATA_DIR = Path(r"C:\Users\Acer\Downloads\Sharnouby_Enterprise")
DEFAULT_PHASE5_DIR = Path("outputs") / "phase5"
DEFAULT_OUTPUT_DIR = Path("outputs") / "phase6"
TOLERANCE = 1e-6


@dataclass
class Phase6Outputs:
    location_replenishment_requirements: pd.DataFrame
    product_replenishment_requirements: pd.DataFrame
    product_material_requirements: pd.DataFrame
    location_material_requirements: pd.DataFrame
    material_requirements_summary: pd.DataFrame
    incremental_replenishment_requirements: pd.DataFrame
    incremental_material_requirements: pd.DataFrame
    bom_coverage_validation: pd.DataFrame
    material_requirement_reconciliation: pd.DataFrame
    validation_checks: pd.DataFrame


def load_sources(phase5_dir: Path, data_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    stockout_path = phase5_dir / "stockout_analysis.csv"
    if not stockout_path.exists():
        raise FileNotFoundError(f"Missing accepted Phase 5 stockout output: {stockout_path}")
    stockout = pd.read_csv(stockout_path)
    product_master = pd.read_csv(data_dir / "Product_Master.csv")
    bom = pd.read_csv(data_dir / "Product_BOM.csv")
    materials = pd.read_csv(data_dir / "Materials.csv")
    return stockout, product_master, bom, materials


def validate_phase5_source(stockout: pd.DataFrame) -> pd.DataFrame:
    required = {
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
        "Inventory_Risk",
        "Estimated_Stockout_Date",
    }
    missing = sorted(required - set(stockout.columns))
    pairs = stockout[["Product_ID", "Location_ID"]].drop_duplicates().shape[0] if not missing else 0
    duplicate_keys = (
        stockout.duplicated(["Product_ID", "Location_ID", "Horizon_Days"]).sum()
        if {"Product_ID", "Location_ID", "Horizon_Days"}.issubset(stockout.columns)
        else -1
    )
    checks = [
        ("phase5_required_columns_present", len(missing) == 0, f"missing={missing}"),
        ("phase5_source_531_rows", len(stockout) == 531, f"rows={len(stockout)}"),
        ("phase5_source_177_product_location_pairs", pairs == 177, f"pairs={pairs}"),
        ("phase5_source_horizons_30_60_90", set(stockout.get("Horizon_Days", [])) == set(HORIZONS), f"horizons={sorted(stockout.get('Horizon_Days', pd.Series(dtype=int)).unique())}"),
        ("phase5_replenishment_non_negative", bool((stockout.get("Recommended_Replenishment_Qty", pd.Series(dtype=float)) >= 0).all()), f"min={stockout.get('Recommended_Replenishment_Qty', pd.Series([np.nan])).min()}"),
        ("phase5_product_id_complete", bool(stockout.get("Product_ID", pd.Series(dtype=object)).notna().all()), f"missing_product_id={stockout.get('Product_ID', pd.Series(dtype=object)).isna().sum()}"),
        ("phase5_no_duplicate_product_location_horizon", duplicate_keys == 0, f"duplicates={duplicate_keys}"),
    ]
    result = pd.DataFrame(checks, columns=["check", "passed", "detail"])
    if not result["passed"].all():
        raise RuntimeError("Accepted Phase 5 source validation failed. Stop before Phase 6 calculations.")
    return result


def build_location_replenishment(stockout: pd.DataFrame) -> pd.DataFrame:
    location = stockout[
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
            "Safety_Stock_Units",
            "Expected_Shortage_Units",
            "Recommended_Replenishment_Qty",
            "Inventory_Risk",
            "Estimated_Stockout_Date",
        ]
    ].copy()
    location = location.rename(columns={"Forecast_Demand": "Forecast_Demand_Raw"})
    return location.sort_values(["Product_ID", "Location_ID", "Horizon_Days"]).reset_index(drop=True)


def build_product_replenishment(location: pd.DataFrame, product_master: pd.DataFrame) -> pd.DataFrame:
    grouped = (
        location.groupby(["Product_ID", "Horizon_Days"], as_index=False)
        .agg(
            Production_Equivalent_Replenishment_Qty=("Recommended_Replenishment_Qty", "sum"),
            Locations_Requiring_Replenishment_Count=(
                "Recommended_Replenishment_Qty",
                lambda x: int((x > 0).sum()),
            ),
            High_Risk_Locations_Count=("Inventory_Risk", lambda x: int((x == "High").sum())),
        )
    )
    product_info = product_master[["Product_ID", "Product_Name", "Product_Family"]].drop_duplicates("Product_ID")
    product_horizons = product_info.merge(pd.DataFrame({"Horizon_Days": HORIZONS}), how="cross")
    product = product_horizons.merge(grouped, on=["Product_ID", "Horizon_Days"], how="left")
    numeric_cols = [
        "Production_Equivalent_Replenishment_Qty",
        "Locations_Requiring_Replenishment_Count",
        "High_Risk_Locations_Count",
    ]
    product[numeric_cols] = product[numeric_cols].fillna(0)
    product["Locations_Requiring_Replenishment_Count"] = product[
        "Locations_Requiring_Replenishment_Count"
    ].astype(int)
    product["High_Risk_Locations_Count"] = product["High_Risk_Locations_Count"].astype(int)
    product["Requires_Replenishment"] = product["Production_Equivalent_Replenishment_Qty"] > 0
    return product.sort_values(["Product_ID", "Horizon_Days"]).reset_index(drop=True)


def enrich_bom(bom: pd.DataFrame, materials: pd.DataFrame) -> pd.DataFrame:
    work = bom.copy()
    work["Required_Per_Unit"] = pd.to_numeric(work["Required_Per_Unit"], errors="coerce")
    materials_cols = [
        "Material_ID",
        "Material_Name",
        "Unit",
        "Material_Category",
        "Standard_Lead_Time_Days",
    ]
    enriched = work.merge(
        materials[materials_cols].rename(
            columns={
                "Material_Name": "Material_Name_Master",
                "Unit": "Unit_Master",
            }
        ),
        on="Material_ID",
        how="left",
        validate="many_to_one",
    )
    enriched["Material_Name"] = enriched["Material_Name_Master"].combine_first(enriched["Material_Name"])
    enriched["Unit"] = enriched["Unit"].combine_first(enriched["Unit_Master"])
    enriched["Unit_Mismatch_Flag"] = (
        enriched["Unit_Master"].notna()
        & enriched["Unit"].notna()
        & ~enriched["Unit"].astype(str).eq(enriched["Unit_Master"].astype(str))
    )
    return enriched


def build_bom_coverage_validation(
    product_replenishment: pd.DataFrame,
    bom: pd.DataFrame,
    enriched_bom: pd.DataFrame,
) -> pd.DataFrame:
    bom_row_counts = bom.groupby("Product_ID").size().rename("BOM_Row_Count")
    duplicate_counts = (
        bom[bom.duplicated(["Product_ID", "Material_ID"], keep=False)]
        .groupby("Product_ID")
        .size()
        .rename("Duplicate_Product_Material_Rows")
    )
    unresolved_counts = (
        enriched_bom[enriched_bom["Material_Name_Master"].isna()]
        .groupby("Product_ID")
        .size()
        .rename("Unresolved_BOM_Material_Count")
    )
    non_numeric_counts = (
        bom[pd.to_numeric(bom["Required_Per_Unit"], errors="coerce").isna()]
        .groupby("Product_ID")
        .size()
        .rename("Non_Numeric_Required_Per_Unit_Count")
    )
    negative_counts = (
        enriched_bom[enriched_bom["Required_Per_Unit"] < 0]
        .groupby("Product_ID")
        .size()
        .rename("Negative_Required_Per_Unit_Count")
    )
    missing_unit_counts = (
        enriched_bom[enriched_bom["Unit"].isna() | enriched_bom["Unit"].astype(str).str.strip().eq("")]
        .groupby("Product_ID")
        .size()
        .rename("Missing_Unit_Count")
    )
    unit_mismatch_counts = (
        enriched_bom[enriched_bom["Unit_Mismatch_Flag"]]
        .groupby("Product_ID")
        .size()
        .rename("Unit_Mismatch_Count")
    )

    validation = product_replenishment.merge(bom_row_counts, on="Product_ID", how="left")
    for series in [
        duplicate_counts,
        unresolved_counts,
        non_numeric_counts,
        negative_counts,
        missing_unit_counts,
        unit_mismatch_counts,
    ]:
        validation = validation.merge(series, on="Product_ID", how="left")

    count_cols = [
        "BOM_Row_Count",
        "Duplicate_Product_Material_Rows",
        "Unresolved_BOM_Material_Count",
        "Non_Numeric_Required_Per_Unit_Count",
        "Negative_Required_Per_Unit_Count",
        "Missing_Unit_Count",
        "Unit_Mismatch_Count",
    ]
    validation[count_cols] = validation[count_cols].fillna(0).astype(int)
    validation["Has_BOM_Coverage"] = validation["BOM_Row_Count"] > 0
    validation["Missing_BOM_Flag"] = validation["Requires_Replenishment"] & ~validation["Has_BOM_Coverage"]
    validation["BOM_Coverage_Status"] = np.select(
        [
            validation["Missing_BOM_Flag"],
            validation["Requires_Replenishment"] & validation["Has_BOM_Coverage"],
            ~validation["Requires_Replenishment"] & validation["Has_BOM_Coverage"],
        ],
        [
            "missing_bom_for_replenishment_product",
            "covered_replenishment_product",
            "covered_zero_replenishment_product",
        ],
        default="zero_replenishment_no_bom",
    )
    return validation.sort_values(["Product_ID", "Horizon_Days"]).reset_index(drop=True)


def build_product_material_requirements(
    product_replenishment: pd.DataFrame,
    enriched_bom: pd.DataFrame,
) -> pd.DataFrame:
    product_material = product_replenishment.merge(enriched_bom, on="Product_ID", how="left")
    product_material["Gross_Material_Requirement_If_Produced"] = (
        product_material["Production_Equivalent_Replenishment_Qty"]
        * product_material["Required_Per_Unit"]
    )
    columns = [
        "Product_ID",
        "Product_Name_x",
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
    ]
    product_material = product_material[columns].rename(columns={"Product_Name_x": "Product_Name"})
    return product_material.sort_values(["Product_ID", "Horizon_Days", "Material_ID"]).reset_index(drop=True)


def build_location_material_requirements(
    location_replenishment: pd.DataFrame,
    enriched_bom: pd.DataFrame,
) -> pd.DataFrame:
    location_material = location_replenishment.merge(enriched_bom, on="Product_ID", how="left")
    location_material["Location_Material_Requirement_If_Produced"] = (
        location_material["Recommended_Replenishment_Qty"] * location_material["Required_Per_Unit"]
    )
    columns = [
        "Product_ID",
        "Product_Name_x",
        "Location_ID",
        "Location_Name",
        "Channel",
        "Horizon_Days",
        "Recommended_Replenishment_Qty",
        "Material_ID",
        "Material_Name",
        "Required_Per_Unit",
        "Unit",
        "Location_Material_Requirement_If_Produced",
    ]
    location_material = location_material[columns].rename(columns={"Product_Name_x": "Product_Name"})
    return location_material.sort_values(
        ["Product_ID", "Location_ID", "Horizon_Days", "Material_ID"]
    ).reset_index(drop=True)


def build_reconciliation(
    product_material: pd.DataFrame,
    location_material: pd.DataFrame,
) -> pd.DataFrame:
    group_cols = ["Product_ID", "Material_ID", "Horizon_Days", "Unit"]
    product_sum = (
        product_material.groupby(group_cols, dropna=False, as_index=False)
        .agg(Product_Level_Gross_Material_Requirement=("Gross_Material_Requirement_If_Produced", "sum"))
    )
    location_sum = (
        location_material.groupby(group_cols, dropna=False, as_index=False)
        .agg(Location_Level_Material_Requirement_Sum=("Location_Material_Requirement_If_Produced", "sum"))
    )
    reconciliation = product_sum.merge(location_sum, on=group_cols, how="outer")
    reconciliation[[
        "Product_Level_Gross_Material_Requirement",
        "Location_Level_Material_Requirement_Sum",
    ]] = reconciliation[[
        "Product_Level_Gross_Material_Requirement",
        "Location_Level_Material_Requirement_Sum",
    ]].fillna(0)
    reconciliation["Difference"] = (
        reconciliation["Location_Level_Material_Requirement_Sum"]
        - reconciliation["Product_Level_Gross_Material_Requirement"]
    )
    reconciliation["Absolute_Difference"] = reconciliation["Difference"].abs()
    reconciliation["Reconciliation_Passed"] = reconciliation["Absolute_Difference"] <= (
        TOLERANCE * np.maximum(1, reconciliation["Product_Level_Gross_Material_Requirement"].abs())
    )
    return reconciliation.sort_values(["Product_ID", "Material_ID", "Horizon_Days"]).reset_index(drop=True)


def build_material_summary(product_material: pd.DataFrame, bom: pd.DataFrame) -> pd.DataFrame:
    using_counts = (
        bom.groupby("Material_ID")["Product_ID"].nunique().rename("Products_Using_Material_Count")
    )
    summary = (
        product_material.groupby(
            [
                "Material_ID",
                "Material_Name",
                "Material_Category",
                "Unit",
                "Horizon_Days",
                "Standard_Lead_Time_Days",
            ],
            dropna=False,
            as_index=False,
        )
        .agg(
            Products_Requiring_Material_Count=(
                "Gross_Material_Requirement_If_Produced",
                lambda x: int((x > 0).sum()),
            ),
            Total_Gross_Material_Requirement_If_Produced=(
                "Gross_Material_Requirement_If_Produced",
                "sum",
            ),
        )
    )
    summary = summary.merge(using_counts, on="Material_ID", how="left")
    summary = summary[
        [
            "Material_ID",
            "Material_Name",
            "Material_Category",
            "Unit",
            "Horizon_Days",
            "Standard_Lead_Time_Days",
            "Products_Using_Material_Count",
            "Products_Requiring_Material_Count",
            "Total_Gross_Material_Requirement_If_Produced",
        ]
    ]
    return summary.sort_values(["Material_ID", "Horizon_Days"]).reset_index(drop=True)


def build_incremental_replenishment(product_replenishment: pd.DataFrame) -> pd.DataFrame:
    base_cols = ["Product_ID", "Product_Name", "Product_Family"]
    pivot = product_replenishment.pivot_table(
        index=base_cols,
        columns="Horizon_Days",
        values="Production_Equivalent_Replenishment_Qty",
        aggfunc="first",
    ).reset_index()
    for horizon in HORIZONS:
        if horizon not in pivot.columns:
            pivot[horizon] = 0
    pivot = pivot.rename(
        columns={
            30: "Cumulative_30_Day_Production_Equivalent_Replenishment_Qty",
            60: "Cumulative_60_Day_Production_Equivalent_Replenishment_Qty",
            90: "Cumulative_90_Day_Production_Equivalent_Replenishment_Qty",
        }
    )
    pivot["Incremental_0_30_Production_Equivalent_Replenishment_Qty"] = pivot[
        "Cumulative_30_Day_Production_Equivalent_Replenishment_Qty"
    ]
    pivot["Incremental_31_60_Production_Equivalent_Replenishment_Qty"] = np.maximum(
        0,
        pivot["Cumulative_60_Day_Production_Equivalent_Replenishment_Qty"]
        - pivot["Cumulative_30_Day_Production_Equivalent_Replenishment_Qty"],
    )
    pivot["Incremental_61_90_Production_Equivalent_Replenishment_Qty"] = np.maximum(
        0,
        pivot["Cumulative_90_Day_Production_Equivalent_Replenishment_Qty"]
        - pivot["Cumulative_60_Day_Production_Equivalent_Replenishment_Qty"],
    )
    pivot["Requires_Replenishment"] = (
        pivot[
            [
                "Cumulative_30_Day_Production_Equivalent_Replenishment_Qty",
                "Cumulative_60_Day_Production_Equivalent_Replenishment_Qty",
                "Cumulative_90_Day_Production_Equivalent_Replenishment_Qty",
            ]
        ].max(axis=1)
        > 0
    )
    return pivot.sort_values("Product_ID").reset_index(drop=True)


def build_incremental_material(product_material: pd.DataFrame) -> pd.DataFrame:
    base_cols = [
        "Product_ID",
        "Product_Name",
        "Product_Family",
        "Material_ID",
        "Material_Name",
        "Material_Category",
        "Unit",
        "Standard_Lead_Time_Days",
    ]
    pivot = product_material.pivot_table(
        index=base_cols,
        columns="Horizon_Days",
        values="Gross_Material_Requirement_If_Produced",
        aggfunc="sum",
    ).reset_index()
    for horizon in HORIZONS:
        if horizon not in pivot.columns:
            pivot[horizon] = 0
    pivot = pivot.rename(
        columns={
            30: "Cumulative_30_Day_Gross_Material_Requirement_If_Produced",
            60: "Cumulative_60_Day_Gross_Material_Requirement_If_Produced",
            90: "Cumulative_90_Day_Gross_Material_Requirement_If_Produced",
        }
    )
    pivot["Incremental_0_30_Gross_Material_Requirement_If_Produced"] = pivot[
        "Cumulative_30_Day_Gross_Material_Requirement_If_Produced"
    ]
    pivot["Incremental_31_60_Gross_Material_Requirement_If_Produced"] = np.maximum(
        0,
        pivot["Cumulative_60_Day_Gross_Material_Requirement_If_Produced"]
        - pivot["Cumulative_30_Day_Gross_Material_Requirement_If_Produced"],
    )
    pivot["Incremental_61_90_Gross_Material_Requirement_If_Produced"] = np.maximum(
        0,
        pivot["Cumulative_90_Day_Gross_Material_Requirement_If_Produced"]
        - pivot["Cumulative_60_Day_Gross_Material_Requirement_If_Produced"],
    )
    return pivot.sort_values(["Material_ID", "Product_ID"]).reset_index(drop=True)


def validate_outputs(
    phase5_checks: pd.DataFrame,
    stockout: pd.DataFrame,
    product_master: pd.DataFrame,
    bom: pd.DataFrame,
    materials: pd.DataFrame,
    enriched_bom: pd.DataFrame,
    location_replenishment: pd.DataFrame,
    product_replenishment: pd.DataFrame,
    product_material: pd.DataFrame,
    location_material: pd.DataFrame,
    material_summary: pd.DataFrame,
    incremental_replenishment: pd.DataFrame,
    incremental_material: pd.DataFrame,
    bom_coverage: pd.DataFrame,
    reconciliation: pd.DataFrame,
) -> pd.DataFrame:
    product_wide = product_replenishment.pivot_table(
        index="Product_ID",
        columns="Horizon_Days",
        values="Production_Equivalent_Replenishment_Qty",
        aggfunc="first",
    )
    forbidden_columns = {
        "Current_Material_Stock",
        "Material_Shortage",
        "Net_Material_Requirement",
        "Material_Available",
        "Material_Stockout",
        "Purchase_Qty",
        "Purchase_Quantity",
        "Material_Availability",
    }
    output_frames = [
        location_replenishment,
        product_replenishment,
        product_material,
        location_material,
        material_summary,
        incremental_replenishment,
        incremental_material,
        bom_coverage,
        reconciliation,
    ]
    output_cols = set().union(*(set(frame.columns) for frame in output_frames))
    material_unit_counts = enriched_bom.groupby("Material_ID")["Unit"].nunique(dropna=False)
    checks = [
        *phase5_checks.itertuples(index=False, name=None),
        (
            "all_59_products_represented_in_product_planning",
            product_replenishment["Product_ID"].nunique() == 59
            and len(product_replenishment) == 59 * len(HORIZONS),
            f"products={product_replenishment['Product_ID'].nunique()}; rows={len(product_replenishment)}",
        ),
        (
            "all_30_60_90_horizons_represented",
            set(product_replenishment["Horizon_Days"].unique()) == set(HORIZONS),
            f"horizons={sorted(product_replenishment['Horizon_Days'].unique())}",
        ),
        (
            "location_replenishment_output_preserves_phase5_rows",
            len(location_replenishment) == 531
            and location_replenishment[["Product_ID", "Location_ID"]].drop_duplicates().shape[0] == 177,
            f"rows={len(location_replenishment)}; pairs={location_replenishment[['Product_ID', 'Location_ID']].drop_duplicates().shape[0]}",
        ),
        (
            "no_negative_replenishment_quantities",
            bool((location_replenishment["Recommended_Replenishment_Qty"] >= 0).all())
            and bool((product_replenishment["Production_Equivalent_Replenishment_Qty"] >= 0).all()),
            f"location_min={location_replenishment['Recommended_Replenishment_Qty'].min():.6f}",
        ),
        (
            "required_per_unit_numeric_and_non_negative",
            bool(enriched_bom["Required_Per_Unit"].notna().all())
            and bool((enriched_bom["Required_Per_Unit"] >= 0).all()),
            f"min={enriched_bom['Required_Per_Unit'].min():.6f}; missing={enriched_bom['Required_Per_Unit'].isna().sum()}",
        ),
        (
            "bom_units_present",
            bool(enriched_bom["Unit"].notna().all())
            and bool(enriched_bom["Unit"].astype(str).str.strip().ne("").all()),
            f"missing_units={int(enriched_bom['Unit'].isna().sum() + enriched_bom['Unit'].astype(str).str.strip().eq('').sum())}",
        ),
        (
            "material_lead_time_present_descriptive_only",
            bool(enriched_bom["Standard_Lead_Time_Days"].notna().all())
            and bool((enriched_bom["Standard_Lead_Time_Days"] >= 0).all()),
            f"missing={int(enriched_bom['Standard_Lead_Time_Days'].isna().sum())}",
        ),
        (
            "no_negative_material_requirements",
            bool((product_material["Gross_Material_Requirement_If_Produced"].fillna(0) >= 0).all())
            and bool((location_material["Location_Material_Requirement_If_Produced"].fillna(0) >= 0).all()),
            f"product_min={product_material['Gross_Material_Requirement_If_Produced'].min():.6f}",
        ),
        (
            "no_incompatible_unit_aggregation",
            bool((material_unit_counts <= 1).all()),
            f"materials_with_multiple_units={int((material_unit_counts > 1).sum())}",
        ),
        (
            "replenishment_products_have_bom_or_flagged",
            bool((~bom_coverage["Missing_BOM_Flag"]).all()),
            f"missing_bom_flags={int(bom_coverage['Missing_BOM_Flag'].sum())}",
        ),
        (
            "all_bom_material_ids_resolve_to_materials",
            set(bom["Material_ID"]).issubset(set(materials["Material_ID"])),
            f"unresolved={sorted(set(bom['Material_ID']) - set(materials['Material_ID']))}",
        ),
        (
            "no_duplicate_product_material_bom_rows",
            int(bom.duplicated(["Product_ID", "Material_ID"]).sum()) == 0,
            f"duplicates={int(bom.duplicated(['Product_ID', 'Material_ID']).sum())}",
        ),
        (
            "product_material_equals_location_material_sum",
            bool(reconciliation["Reconciliation_Passed"].all()),
            f"max_abs_diff={reconciliation['Absolute_Difference'].max():.12f}",
        ),
        (
            "cumulative_product_requirement_60_ge_30",
            bool((product_wide[60] + TOLERANCE >= product_wide[30]).all()),
            "checked all products",
        ),
        (
            "cumulative_product_requirement_90_ge_60",
            bool((product_wide[90] + TOLERANCE >= product_wide[60]).all()),
            "checked all products",
        ),
        (
            "incremental_replenishment_non_negative",
            bool(
                (
                    incremental_replenishment[
                        [
                            "Incremental_0_30_Production_Equivalent_Replenishment_Qty",
                            "Incremental_31_60_Production_Equivalent_Replenishment_Qty",
                            "Incremental_61_90_Production_Equivalent_Replenishment_Qty",
                        ]
                    ]
                    >= 0
                )
                .all()
                .all()
            ),
            "checked product incremental buckets",
        ),
        (
            "incremental_material_requirements_non_negative",
            bool(
                (
                    incremental_material[
                        [
                            "Incremental_0_30_Gross_Material_Requirement_If_Produced",
                            "Incremental_31_60_Gross_Material_Requirement_If_Produced",
                            "Incremental_61_90_Gross_Material_Requirement_If_Produced",
                        ]
                    ]
                    >= 0
                )
                .all()
                .all()
            ),
            "checked product-material incremental buckets",
        ),
        (
            "no_raw_material_stock_invented",
            forbidden_columns.isdisjoint(output_cols),
            f"forbidden_columns_present={sorted(forbidden_columns.intersection(output_cols))}",
        ),
        (
            "no_purchase_quantity_fabricated",
            "Purchase_Qty" not in output_cols and "Purchase_Quantity" not in output_cols,
            "Phase 6 outputs contain gross requirements only",
        ),
        (
            "no_external_data_used",
            True,
            "Used accepted Phase 5 output plus provided Product_BOM.csv, Materials.csv, and Product_Master.csv",
        ),
    ]
    return pd.DataFrame(checks, columns=["check", "passed", "detail"])


def build_report(outputs: Phase6Outputs, output_dir: Path) -> str:
    product = outputs.product_replenishment_requirements
    material_summary = outputs.material_requirements_summary
    product_material = outputs.product_material_requirements
    bom_coverage = outputs.bom_coverage_validation
    reconciliation = outputs.material_requirement_reconciliation
    incremental_product = outputs.incremental_replenishment_requirements
    incremental_material = outputs.incremental_material_requirements

    products_requiring = (
        product.groupby("Horizon_Days", as_index=False)
        .agg(
            Products_Requiring_Replenishment=("Requires_Replenishment", "sum"),
            Total_Production_Equivalent_Replenishment_Qty=(
                "Production_Equivalent_Replenishment_Qty",
                "sum",
            ),
        )
        .sort_values("Horizon_Days")
    )
    largest_products = product[product["Horizon_Days"].eq(90)].sort_values(
        "Production_Equivalent_Replenishment_Qty",
        ascending=False,
    )
    top_materials = material_summary[material_summary["Horizon_Days"].eq(90)].sort_values(
        "Total_Gross_Material_Requirement_If_Produced",
        ascending=False,
    )
    category_summary = (
        material_summary.groupby(["Horizon_Days", "Material_Category", "Unit"], as_index=False)
        .agg(
            Total_Gross_Material_Requirement_If_Produced=(
                "Total_Gross_Material_Requirement_If_Produced",
                "sum",
            )
        )
        .sort_values(["Horizon_Days", "Total_Gross_Material_Requirement_If_Produced"], ascending=[True, False])
    )
    longest_lead = (
        material_summary[["Material_ID", "Material_Name", "Material_Category", "Unit", "Standard_Lead_Time_Days"]]
        .drop_duplicates()
        .sort_values(["Standard_Lead_Time_Days", "Material_ID"], ascending=[False, True])
    )
    material_dependency = (
        material_summary[material_summary["Horizon_Days"].eq(90)]
        .sort_values("Products_Requiring_Material_Count", ascending=False)
    )
    missing_bom = bom_coverage[bom_coverage["Missing_BOM_Flag"]]
    max_recon_diff = reconciliation["Absolute_Difference"].max()
    incremental_material_summary = incremental_material[
        [
            "Incremental_0_30_Gross_Material_Requirement_If_Produced",
            "Incremental_31_60_Gross_Material_Requirement_If_Produced",
            "Incremental_61_90_Gross_Material_Requirement_If_Produced",
        ]
    ].sum().reset_index()
    incremental_material_summary.columns = ["Incremental_Bucket", "Gross_Material_Requirement_If_Produced"]

    report = f"""# Phase 6 BOM And Gross Material Requirements Report

## Scope Boundary

This is Phase 6 only. It converts accepted Phase 5 location replenishment quantities into BOM-based gross material requirements if those finished units were supplied through new production. It does not calculate procurement risk, supplier risk, production risk, material availability, purchase-order quantities, final combined risk, or Streamlit outputs.

## Interpretation

`Recommended_Replenishment_Qty` remains a location-level replenishment requirement. Product-level `Production_Equivalent_Replenishment_Qty` means the finished units that would need to be supplied if the location replenishment requirement were fulfilled through new production. `Gross_Material_Requirement_If_Produced` is the gross BOM material quantity required if those units are manufactured from new materials.

These are not confirmed purchase quantities.

## Product Replenishment Summary

Products requiring replenishment and production-equivalent quantities by horizon:

{markdown_table(products_requiring, ["Horizon_Days", "Products_Requiring_Replenishment", "Total_Production_Equivalent_Replenishment_Qty"], 10)}

Largest 90-day product-level requirements:

{markdown_table(largest_products, ["Product_ID", "Product_Name", "Product_Family", "Horizon_Days", "Production_Equivalent_Replenishment_Qty", "Locations_Requiring_Replenishment_Count", "High_Risk_Locations_Count"], 10)}

Do not sum the 30, 60, and 90-day requirements together. They are cumulative scenarios from the same forecast origin.

## BOM Coverage

Every replenishment product has valid BOM coverage: {bool(missing_bom.empty)}.

Missing BOM rows for replenishment products:

{markdown_table(missing_bom, ["Product_ID", "Product_Name", "Horizon_Days", "Production_Equivalent_Replenishment_Qty", "BOM_Coverage_Status"], 20)}

BOM validation summary:

{markdown_table(bom_coverage.groupby("BOM_Coverage_Status", as_index=False).size().rename(columns={"size": "Rows"}), ["BOM_Coverage_Status", "Rows"], 10)}

## Material Requirements

Largest 90-day gross material requirements:

{markdown_table(top_materials, ["Material_ID", "Material_Name", "Material_Category", "Unit", "Standard_Lead_Time_Days", "Products_Requiring_Material_Count", "Total_Gross_Material_Requirement_If_Produced"], 12)}

Material categories by cumulative horizon and unit:

{markdown_table(category_summary, ["Horizon_Days", "Material_Category", "Unit", "Total_Gross_Material_Requirement_If_Produced"], 20)}

Materials with the longest descriptive standard lead times:

{markdown_table(longest_lead, ["Material_ID", "Material_Name", "Material_Category", "Unit", "Standard_Lead_Time_Days"], 12)}

Products depending on each key material at the 90-day horizon:

{markdown_table(material_dependency, ["Material_ID", "Material_Name", "Unit", "Products_Using_Material_Count", "Products_Requiring_Material_Count", "Total_Gross_Material_Requirement_If_Produced"], 12)}

Standard lead time is descriptive only in Phase 6. It is not used to calculate procurement risk or order dates.

## Location Traceability And Reconciliation

Location-level and product-level material calculations reconcile: {bool(reconciliation["Reconciliation_Passed"].all())}.

- Reconciliation rows: {fmt(len(reconciliation))}
- Maximum absolute difference: {max_recon_diff:.12f}

Largest reconciliation differences:

{markdown_table(reconciliation.sort_values("Absolute_Difference", ascending=False), ["Product_ID", "Material_ID", "Horizon_Days", "Unit", "Product_Level_Gross_Material_Requirement", "Location_Level_Material_Requirement_Sum", "Difference", "Reconciliation_Passed"], 10)}

## Cumulative Versus Incremental

Cumulative requirements show the full requirement from 2026-10-01 through the horizon end. Incremental requirements show the additional quantity that becomes necessary after the prior horizon.

Product incremental replenishment totals:

{markdown_table(pd.DataFrame([{
    "Incremental_0_30_Production_Equivalent_Replenishment_Qty": incremental_product["Incremental_0_30_Production_Equivalent_Replenishment_Qty"].sum(),
    "Incremental_31_60_Production_Equivalent_Replenishment_Qty": incremental_product["Incremental_31_60_Production_Equivalent_Replenishment_Qty"].sum(),
    "Incremental_61_90_Production_Equivalent_Replenishment_Qty": incremental_product["Incremental_61_90_Production_Equivalent_Replenishment_Qty"].sum(),
}]), ["Incremental_0_30_Production_Equivalent_Replenishment_Qty", "Incremental_31_60_Production_Equivalent_Replenishment_Qty", "Incremental_61_90_Production_Equivalent_Replenishment_Qty"], 5)}

Product-material incremental gross requirement totals:

{markdown_table(incremental_material_summary, ["Incremental_Bucket", "Gross_Material_Requirement_If_Produced"], 10)}

## Why These Are Not Purchase Quantities

These requirements are gross BOM quantities implied by the replenishment scenario if finished units are manufactured. They do not subtract raw-material inventory, open purchase orders, supplier capacity, existing allocations, quality holds, scrap allowances, or material already reserved for production. The project still has no current raw-material inventory table, so Phase 6 does not create net material shortage or purchase quantity fields.

To calculate true net material shortage later, the project would need current raw-material on-hand inventory, open PO balances, reserved/allocated material, minimum order quantities, supplier constraints, scrap/yield assumptions, and material availability dates.

## Validation Checks

{markdown_table(outputs.validation_checks, ["check", "passed", "detail"], 30)}

Validation passed: {bool(outputs.validation_checks["passed"].all())}.

## Files Created Or Modified

- `{output_dir / "phase6_bom_material_requirements_report.md"}`
- `{output_dir / "location_replenishment_requirements.csv"}`
- `{output_dir / "product_replenishment_requirements.csv"}`
- `{output_dir / "product_material_requirements.csv"}`
- `{output_dir / "location_material_requirements.csv"}`
- `{output_dir / "material_requirements_summary.csv"}`
- `{output_dir / "incremental_replenishment_requirements.csv"}`
- `{output_dir / "incremental_material_requirements.csv"}`
- `{output_dir / "bom_coverage_validation.csv"}`
- `{output_dir / "material_requirement_reconciliation.csv"}`
- `{output_dir / "validation_checks.csv"}`
- `src/phase6_bom_material_requirements.py`

Stop here for review before Phase 7.
"""
    return report


def run_phase6(phase5_dir: Path, data_dir: Path) -> Phase6Outputs:
    stockout, product_master, bom, materials = load_sources(phase5_dir, data_dir)
    phase5_checks = validate_phase5_source(stockout)
    location = build_location_replenishment(stockout)
    product = build_product_replenishment(location, product_master)
    enriched_bom = enrich_bom(bom, materials)
    bom_coverage = build_bom_coverage_validation(product, bom, enriched_bom)
    product_material = build_product_material_requirements(product, enriched_bom)
    location_material = build_location_material_requirements(location, enriched_bom)
    reconciliation = build_reconciliation(product_material, location_material)
    material_summary = build_material_summary(product_material, bom)
    incremental_replenishment = build_incremental_replenishment(product)
    incremental_material = build_incremental_material(product_material)
    checks = validate_outputs(
        phase5_checks,
        stockout,
        product_master,
        bom,
        materials,
        enriched_bom,
        location,
        product,
        product_material,
        location_material,
        material_summary,
        incremental_replenishment,
        incremental_material,
        bom_coverage,
        reconciliation,
    )
    return Phase6Outputs(
        location_replenishment_requirements=location,
        product_replenishment_requirements=product,
        product_material_requirements=product_material,
        location_material_requirements=location_material,
        material_requirements_summary=material_summary,
        incremental_replenishment_requirements=incremental_replenishment,
        incremental_material_requirements=incremental_material,
        bom_coverage_validation=bom_coverage,
        material_requirement_reconciliation=reconciliation,
        validation_checks=checks,
    )


def write_outputs(outputs: Phase6Outputs, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs.location_replenishment_requirements.to_csv(
        output_dir / "location_replenishment_requirements.csv",
        index=False,
    )
    outputs.product_replenishment_requirements.to_csv(
        output_dir / "product_replenishment_requirements.csv",
        index=False,
    )
    outputs.product_material_requirements.to_csv(
        output_dir / "product_material_requirements.csv",
        index=False,
    )
    outputs.location_material_requirements.to_csv(
        output_dir / "location_material_requirements.csv",
        index=False,
    )
    outputs.material_requirements_summary.to_csv(
        output_dir / "material_requirements_summary.csv",
        index=False,
    )
    outputs.incremental_replenishment_requirements.to_csv(
        output_dir / "incremental_replenishment_requirements.csv",
        index=False,
    )
    outputs.incremental_material_requirements.to_csv(
        output_dir / "incremental_material_requirements.csv",
        index=False,
    )
    outputs.bom_coverage_validation.to_csv(output_dir / "bom_coverage_validation.csv", index=False)
    outputs.material_requirement_reconciliation.to_csv(
        output_dir / "material_requirement_reconciliation.csv",
        index=False,
    )
    outputs.validation_checks.to_csv(output_dir / "validation_checks.csv", index=False)
    report_path = output_dir / "phase6_bom_material_requirements_report.md"
    report_path.write_text(build_report(outputs, output_dir), encoding="utf-8")
    return report_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Phase 6 BOM gross material requirements only.")
    parser.add_argument("--phase5-dir", type=Path, default=DEFAULT_PHASE5_DIR)
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    outputs = run_phase6(args.phase5_dir, args.data_dir)
    report_path = write_outputs(outputs, args.output_dir)
    print(f"Phase 6 BOM material requirements complete: {report_path.resolve()}")


if __name__ == "__main__":
    main()
