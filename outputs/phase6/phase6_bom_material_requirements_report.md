# Phase 6 BOM And Gross Material Requirements Report

## Scope Boundary

This is Phase 6 only. It converts accepted Phase 5 location replenishment quantities into BOM-based gross material requirements if those finished units were supplied through new production. It does not calculate procurement risk, supplier risk, production risk, material availability, purchase-order quantities, final combined risk, or Streamlit outputs.

## Interpretation

`Recommended_Replenishment_Qty` remains a location-level replenishment requirement. Product-level `Production_Equivalent_Replenishment_Qty` means the finished units that would need to be supplied if the location replenishment requirement were fulfilled through new production. `Gross_Material_Requirement_If_Produced` is the gross BOM material quantity required if those units are manufactured from new materials.

These are not confirmed purchase quantities.

## Product Replenishment Summary

Products requiring replenishment and production-equivalent quantities by horizon:

| Horizon_Days | Products_Requiring_Replenishment | Total_Production_Equivalent_Replenishment_Qty |
| --- | --- | --- |
| 30 | 45 | 27,501.377 |
| 60 | 54 | 63,247.065 |
| 90 | 55 | 117,853.191 |

Largest 90-day product-level requirements:

| Product_ID | Product_Name | Product_Family | Horizon_Days | Production_Equivalent_Replenishment_Qty | Locations_Requiring_Replenishment_Count | High_Risk_Locations_Count |
| --- | --- | --- | --- | --- | --- | --- |
| P037 | Girls' sweatshirt-Flower | Sweatshirts | 90 | 8,318.857 | 3 | 3 |
| P033 | Boys' sweatshirt-LEO | Sweatshirts | 90 | 7,205.143 | 3 | 3 |
| P038 | Boys' Autumn Pajamas-Mickey Mouse | Pajamas/Homewear | 90 | 6,856.857 | 3 | 3 |
| P039 | Boys' Autumn Pajamas-Spider Man | Pajamas/Homewear | 90 | 6,425.000 | 3 | 3 |
| P043 | Girls' autumn pajamas-Snow White | Pajamas/Homewear | 90 | 5,799.000 | 3 | 3 |
| P032 | Boys' sweatshirt-blue | Sweatshirts | 90 | 5,768.429 | 3 | 3 |
| P045 | Girls' autumn pajamas-Stitch | Pajamas/Homewear | 90 | 5,755.857 | 3 | 3 |
| P044 | Girls' autumn pajamas-Ice Cream | Pajamas/Homewear | 90 | 5,536.429 | 3 | 3 |
| P035 | Girls' sweatshirt-Fuchsia | Sweatshirts | 90 | 3,249.857 | 3 | 3 |
| P051 | Ice cream - بيجامة حريمي صيفي2024 | Pajamas/Homewear | 90 | 3,043.857 | 1 | 1 |

Do not sum the 30, 60, and 90-day requirements together. They are cumulative scenarios from the same forecast origin.

## BOM Coverage

Every replenishment product has valid BOM coverage: True.

Missing BOM rows for replenishment products:

No rows.

BOM validation summary:

| BOM_Coverage_Status | Rows |
| --- | --- |
| covered_replenishment_product | 154 |
| covered_zero_replenishment_product | 23 |

## Material Requirements

Largest 90-day gross material requirements:

| Material_ID | Material_Name | Material_Category | Unit | Standard_Lead_Time_Days | Products_Requiring_Material_Count | Total_Gross_Material_Requirement_If_Produced |
| --- | --- | --- | --- | --- | --- | --- |
| M007 | Neck Label | Trims | piece | 7 | 55 | 117,853.191 |
| M008 | Care Label | Trims | piece | 14 | 55 | 117,853.191 |
| M009 | Poly Bag | Packaging | piece | 7 | 55 | 117,853.191 |
| M001 | Single Jersey Cotton 160 GSM | Fabric | meter | 10 | 14 | 30,562.841 |
| M002 | Single Jersey Cotton 180 GSM | Fabric | meter | 14 | 13 | 27,608.023 |
| M003 | Rib Cotton | Fabric | meter | 10 | 15 | 20,786.577 |
| M004 | Summer Melton | Fabric | meter | 10 | 13 | 20,036.779 |
| M006 | Sewing Thread | Trims | cone | 14 | 55 | 2,853.017 |
| M012 | Heat Transfer Film | Printing | sheet | 7 | 16 | 1,353.017 |
| M011 | Water-Based Ink | Printing | kg | 21 | 23 | 1,021.879 |

Material categories by cumulative horizon and unit:

| Horizon_Days | Material_Category | Unit | Total_Gross_Material_Requirement_If_Produced |
| --- | --- | --- | --- |
| 30 | Trims | piece | 55,002.754 |
| 30 | Packaging | piece | 27,501.377 |
| 30 | Fabric | meter | 22,586.705 |
| 30 | Trims | cone | 677.853 |
| 30 | Printing | sheet | 412.825 |
| 30 | Printing | kg | 237.588 |
| 60 | Trims | piece | 126,494.131 |
| 60 | Packaging | piece | 63,247.065 |
| 60 | Fabric | meter | 52,422.254 |
| 60 | Trims | cone | 1,551.048 |
| 60 | Printing | sheet | 813.667 |
| 60 | Printing | kg | 558.462 |
| 90 | Trims | piece | 235,706.383 |
| 90 | Packaging | piece | 117,853.191 |
| 90 | Fabric | meter | 98,994.219 |
| 90 | Trims | cone | 2,853.017 |
| 90 | Printing | sheet | 1,353.017 |
| 90 | Printing | kg | 1,021.879 |

Materials with the longest descriptive standard lead times:

| Material_ID | Material_Name | Material_Category | Unit | Standard_Lead_Time_Days |
| --- | --- | --- | --- | --- |
| M011 | Water-Based Ink | Printing | kg | 21 |
| M002 | Single Jersey Cotton 180 GSM | Fabric | meter | 14 |
| M006 | Sewing Thread | Trims | cone | 14 |
| M008 | Care Label | Trims | piece | 14 |
| M001 | Single Jersey Cotton 160 GSM | Fabric | meter | 10 |
| M003 | Rib Cotton | Fabric | meter | 10 |
| M004 | Summer Melton | Fabric | meter | 10 |
| M007 | Neck Label | Trims | piece | 7 |
| M009 | Poly Bag | Packaging | piece | 7 |
| M012 | Heat Transfer Film | Printing | sheet | 7 |

Products depending on each key material at the 90-day horizon:

| Material_ID | Material_Name | Unit | Products_Using_Material_Count | Products_Requiring_Material_Count | Total_Gross_Material_Requirement_If_Produced |
| --- | --- | --- | --- | --- | --- |
| M006 | Sewing Thread | cone | 59 | 55 | 2,853.017 |
| M007 | Neck Label | piece | 59 | 55 | 117,853.191 |
| M008 | Care Label | piece | 59 | 55 | 117,853.191 |
| M009 | Poly Bag | piece | 59 | 55 | 117,853.191 |
| M011 | Water-Based Ink | kg | 25 | 23 | 1,021.879 |
| M012 | Heat Transfer Film | sheet | 17 | 16 | 1,353.017 |
| M003 | Rib Cotton | meter | 16 | 15 | 20,786.577 |
| M001 | Single Jersey Cotton 160 GSM | meter | 15 | 14 | 30,562.841 |
| M002 | Single Jersey Cotton 180 GSM | meter | 15 | 13 | 27,608.023 |
| M004 | Summer Melton | meter | 13 | 13 | 20,036.779 |

Standard lead time is descriptive only in Phase 6. It is not used to calculate procurement risk or order dates.

## Location Traceability And Reconciliation

Location-level and product-level material calculations reconcile: True.

- Reconciliation rows: 1,011
- Maximum absolute difference: 0.000000000001

Largest reconciliation differences:

| Product_ID | Material_ID | Horizon_Days | Unit | Product_Level_Gross_Material_Requirement | Location_Level_Material_Requirement_Sum | Difference | Reconciliation_Passed |
| --- | --- | --- | --- | --- | --- | --- | --- |
| P038 | M002 | 90 | meter | 7,199.700 | 7,199.700 | -0.000 | 1 |
| P045 | M001 | 90 | meter | 5,698.299 | 5,698.299 | 0.000 | 1 |
| P029 | M002 | 90 | meter | 2,053.839 | 2,053.839 | 0.000 | 1 |
| P039 | M003 | 60 | meter | 2,842.431 | 2,842.431 | -0.000 | 1 |
| P038 | M002 | 60 | meter | 3,498.000 | 3,498.000 | -0.000 | 1 |
| P001 | M001 | 60 | meter | 1,837.680 | 1,837.680 | -0.000 | 1 |
| P001 | M001 | 30 | meter | 844.480 | 844.480 | 0.000 | 1 |
| P002 | M001 | 60 | meter | 820.507 | 820.507 | -0.000 | 1 |
| P042 | M004 | 30 | meter | 668.073 | 668.073 | -0.000 | 1 |
| P032 | M006 | 90 | cone | 184.590 | 184.590 | 0.000 | 1 |

## Cumulative Versus Incremental

Cumulative requirements show the full requirement from 2026-10-01 through the horizon end. Incremental requirements show the additional quantity that becomes necessary after the prior horizon.

Product incremental replenishment totals:

| Incremental_0_30_Production_Equivalent_Replenishment_Qty | Incremental_31_60_Production_Equivalent_Replenishment_Qty | Incremental_61_90_Production_Equivalent_Replenishment_Qty |
| --- | --- | --- |
| 27,501.377 | 35,745.688 | 54,606.126 |

Product-material incremental gross requirement totals:

| Incremental_Bucket | Gross_Material_Requirement_If_Produced |
| --- | --- |
| Incremental_0_30_Gross_Material_Requirement_If_Produced | 106,419.103 |
| Incremental_31_60_Gross_Material_Requirement_If_Produced | 138,667.525 |
| Incremental_61_90_Gross_Material_Requirement_If_Produced | 212,695.079 |

## Why These Are Not Purchase Quantities

These requirements are gross BOM quantities implied by the replenishment scenario if finished units are manufactured. They do not subtract raw-material inventory, open purchase orders, supplier capacity, existing allocations, quality holds, scrap allowances, or material already reserved for production. The project still has no current raw-material inventory table, so Phase 6 does not create net material shortage or purchase quantity fields.

To calculate true net material shortage later, the project would need current raw-material on-hand inventory, open PO balances, reserved/allocated material, minimum order quantities, supplier constraints, scrap/yield assumptions, and material availability dates.

## Validation Checks

| check | passed | detail |
| --- | --- | --- |
| phase5_required_columns_present | 1 | missing=[] |
| phase5_source_531_rows | 1 | rows=531 |
| phase5_source_177_product_location_pairs | 1 | pairs=177 |
| phase5_source_horizons_30_60_90 | 1 | horizons=[30, 60, 90] |
| phase5_replenishment_non_negative | 1 | min=0.0 |
| phase5_product_id_complete | 1 | missing_product_id=0 |
| phase5_no_duplicate_product_location_horizon | 1 | duplicates=0 |
| all_59_products_represented_in_product_planning | 1 | products=59; rows=177 |
| all_30_60_90_horizons_represented | 1 | horizons=[30, 60, 90] |
| location_replenishment_output_preserves_phase5_rows | 1 | rows=531; pairs=177 |
| no_negative_replenishment_quantities | 1 | location_min=0.000000 |
| required_per_unit_numeric_and_non_negative | 1 | min=0.010000; missing=0 |
| bom_units_present | 1 | missing_units=0 |
| material_lead_time_present_descriptive_only | 1 | missing=0 |
| no_negative_material_requirements | 1 | product_min=0.000000 |
| no_incompatible_unit_aggregation | 1 | materials_with_multiple_units=0 |
| replenishment_products_have_bom_or_flagged | 1 | missing_bom_flags=0 |
| all_bom_material_ids_resolve_to_materials | 1 | unresolved=[] |
| no_duplicate_product_material_bom_rows | 1 | duplicates=0 |
| product_material_equals_location_material_sum | 1 | max_abs_diff=0.000000000001 |
| cumulative_product_requirement_60_ge_30 | 1 | checked all products |
| cumulative_product_requirement_90_ge_60 | 1 | checked all products |
| incremental_replenishment_non_negative | 1 | checked product incremental buckets |
| incremental_material_requirements_non_negative | 1 | checked product-material incremental buckets |
| no_raw_material_stock_invented | 1 | forbidden_columns_present=[] |
| no_purchase_quantity_fabricated | 1 | Phase 6 outputs contain gross requirements only |
| no_external_data_used | 1 | Used accepted Phase 5 output plus provided Product_BOM.csv, Materials.csv, and Product_Master.csv |

Validation passed: True.

## Files Created Or Modified

- `outputs\phase6\phase6_bom_material_requirements_report.md`
- `outputs\phase6\location_replenishment_requirements.csv`
- `outputs\phase6\product_replenishment_requirements.csv`
- `outputs\phase6\product_material_requirements.csv`
- `outputs\phase6\location_material_requirements.csv`
- `outputs\phase6\material_requirements_summary.csv`
- `outputs\phase6\incremental_replenishment_requirements.csv`
- `outputs\phase6\incremental_material_requirements.csv`
- `outputs\phase6\bom_coverage_validation.csv`
- `outputs\phase6\material_requirement_reconciliation.csv`
- `outputs\phase6\validation_checks.csv`
- `src/phase6_bom_material_requirements.py`

Stop here for review before Phase 7.
