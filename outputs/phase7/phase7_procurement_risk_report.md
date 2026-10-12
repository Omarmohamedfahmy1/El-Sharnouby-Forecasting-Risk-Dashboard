# Phase 7 Procurement And Supplier Risk Report

## Scope Boundary

This is Phase 7 only. It analyzes historical procurement and supplier evidence, then joins that evidence to accepted Phase 6 gross material requirements. It does not calculate raw-material inventory, net material shortage, recommended purchase quantities, production risk, final combined risk, or Streamlit outputs.

## Data Sources Used

- Raw data directory supplied at runtime: `C:\Users\Acer\Downloads\Sharnouby_Enterprise`
- Accepted Phase 6 directory: `C:\Users\Acer\Documents\ChatGPT\El Sharnoby\outputs\phase6`
- CSV inputs: `Purchase_Orders.csv`, `Suppliers.csv`, `Materials.csv`, `Data_Dictionary.csv`, and `outputs/phase6/material_requirements_summary.csv`.
- No external data was used.

Relevant data dictionary rows:

| Table | Grain | Purpose | Real_vs_Modeled |
| --- | --- | --- | --- |
| Materials.csv | 1 row per material | Material master | Modeled generic operational master |
| Suppliers.csv | 1 row per anonymized supplier | Supplier segmentation | Modeled/anonymized |
| Purchase_Orders.csv | 1 row per material PO | Lead time, OTIF, purchase price and reject analysis | Modeled |

## Portability Fix

The new Phase 7 script accepts `--data-dir`, `--phase6-dir`, and `--output-dir`, uses `pathlib`, and defaults to project-relative paths. It does not depend on the machine-specific raw data path. Older scripts were not rewritten or rerun silently.

See `hardcoded_path_cleanup_note.md` for the list of older scripts that still contain machine-specific dataset paths.

## Procurement Data Quality Audit

- Purchase order rows handled: 3,600
- Unique `PO_ID`: 3,600
- Duplicate `PO_ID` rows: 0
- Accepted + rejected equals ordered: 100.0% of rows; mismatches: 0
- Historical PO date span inspected: 2023-10-01 to 2026-09-30

| Check | Metric_Value | Issue_Count | Issue_Pct | Detail |
| --- | --- | --- | --- | --- |
| row_count | 3,600 | 0 | 0 | Purchase_Orders.csv rows handled in enriched output. |
| unique_po_id_count | 3,600 | 0 | 0 | duplicate_po_id_rows=0 |
| duplicate_po_id_rows | 0 | 0 | 0 | Rows sharing a PO_ID with at least one other row. |
| missing_supplier_id | 0 | 0 | 0 | Supplier_ID missing before supplier resolution. |
| missing_material_id | 0 | 0 | 0 | Material_ID missing before material resolution. |
| missing_order_date | 0 | 0 | 0 | Order_Date missing or unparseable. |
| missing_promised_date | 0 | 0 | 0 | Promised_Date missing or unparseable. |
| missing_actual_receipt_date | 0 | 0 | 0 | Actual_Receipt_Date missing or unparseable. |
| impossible_date_ordering | 0 | 0 | 0 | Flags promised date before order date or actual receipt before order date. |
| negative_quantities | 0 | 0 | 0 | Flags negative Ordered_Qty, Accepted_Qty, or Rejected_Qty. |
| accepted_plus_rejected_vs_ordered_mismatch | 0 | 0 | 0 | accepted+rejected above ordered=0; below ordered=0 |
| unresolved_supplier_id | 0 | 0 | 0 | Supplier_ID not found in Suppliers.csv. |
| unresolved_material_id | 0 | 0 | 0 | Material_ID not found in Materials.csv. |
| unit_mismatch_vs_material_master | 0 | 0 | 0 | PO unit compared with Materials.csv unit. |
| negative_unit_cost | 0 | 0 | 0 | Unit_Cost_EGP is descriptive historical cost only. |

`Accepted_Qty + Rejected_Qty` matched `Ordered_Qty` in this dataset, but the script still keeps the relationship as a validation field rather than assuming it must always hold.

## Derived PO Metrics

The enriched PO file adds `Actual_Lead_Time_Days`, `Promised_Lead_Time_Days`, `Delivery_Delay_Days`, `On_Time_Flag`, `Acceptance_Rate`, and `Rejection_Rate`. `Ordered_Qty` remains the ordered PO quantity; it is not treated as a future physical availability amount.

Actual lead time distribution:

| Statistic | Days |
| --- | --- |
| count | 3,600 |
| mean | 12.310 |
| std | 6.009 |
| min | 3 |
| 50% | 10 |
| 75% | 16 |
| 90% | 21 |
| 95% | 23 |
| max | 33 |

Delivery delay distribution:

| Statistic | Days |
| --- | --- |
| count | 3,600 |
| mean | 0.898 |
| std | 2.099 |
| min | -6 |
| 50% | 0 |
| 75% | 2 |
| 90% | 3 |
| 95% | 5 |
| max | 12 |

Rejection-rate distribution:

| Statistic | Rate |
| --- | --- |
| count | 3,600 |
| mean | 0.018 |
| std | 0.010 |
| min | 0.000 |
| 50% | 0.017 |
| 75% | 0.026 |
| 90% | 0.032 |
| 95% | 0.033 |
| max | 0.039 |

Overall historical on-time rate: 65.4%. Overall historical late rate: 34.6%.

## Material-Level Procurement History

Material-level history includes PO count, supplier count, mean/median/P90 actual lead time, delivery delay, late/on-time rate, acceptance/rejection, quantities, and descriptive historical unit cost. Standard lead time is shown for comparison only.

Materials with highest late rates:

| Material_ID | Material_Name | PO_Count | Supplier_Count | Late_PO_Rate | Mean_Delivery_Delay_Days | Mean_Rejection_Rate |
| --- | --- | --- | --- | --- | --- | --- |
| M010 | Carton Box | 310 | 12 | 0.397 | 1.019 | 0.018 |
| M006 | Sewing Thread | 303 | 12 | 0.389 | 1.076 | 0.018 |
| M012 | Heat Transfer Film | 335 | 12 | 0.364 | 0.946 | 0.018 |
| M004 | Summer Melton | 286 | 12 | 0.357 | 0.832 | 0.018 |
| M009 | Poly Bag | 303 | 12 | 0.350 | 0.891 | 0.017 |
| M005 | Elastic Band | 279 | 12 | 0.344 | 0.932 | 0.019 |
| M001 | Single Jersey Cotton 160 GSM | 286 | 12 | 0.336 | 0.741 | 0.018 |
| M011 | Water-Based Ink | 286 | 12 | 0.332 | 1.119 | 0.017 |

Materials with highest mean rejection rates:

| Material_ID | Material_Name | PO_Count | Mean_Rejection_Rate | Mean_Acceptance_Rate | Total_Rejected_Qty |
| --- | --- | --- | --- | --- | --- |
| M005 | Elastic Band | 279 | 0.019 | 0.981 | 16,190 |
| M010 | Carton Box | 310 | 0.018 | 0.982 | 42,914 |
| M012 | Heat Transfer Film | 335 | 0.018 | 0.982 | 45,902 |
| M004 | Summer Melton | 286 | 0.018 | 0.982 | 14,810 |
| M006 | Sewing Thread | 303 | 0.018 | 0.982 | 15,975 |
| M008 | Care Label | 299 | 0.018 | 0.982 | 40,111 |
| M001 | Single Jersey Cotton 160 GSM | 286 | 0.018 | 0.982 | 15,158 |
| M007 | Neck Label | 290 | 0.017 | 0.983 | 37,650 |

Materials with limited evidence:

No rows.

## Supplier-Level Procurement History

Supplier history is based only on historical POs and supplier master attributes. It does not assert future supplier capacity or availability.

Suppliers with strongest historical delivery/quality pattern:

| Supplier_ID | Supplier_Name | Primary_Category | PO_Count | Material_Count | On_Time_PO_Rate | Mean_Rejection_Rate | Mean_Actual_Lead_Time_Days |
| --- | --- | --- | --- | --- | --- | --- | --- |
| SUP10 | Approved Supplier 10 (anonymized) | Trims | 300 | 12 | 0.740 | 0.017 | 12.127 |
| SUP02 | Approved Supplier 02 (anonymized) | Trims | 297 | 12 | 0.727 | 0.017 | 11.418 |
| SUP11 | Approved Supplier 11 (anonymized) | Trims | 305 | 12 | 0.725 | 0.019 | 11.862 |
| SUP05 | Approved Supplier 05 (anonymized) | Fabric | 297 | 12 | 0.724 | 0.018 | 11.943 |
| SUP03 | Approved Supplier 03 (anonymized) | Fabric | 291 | 12 | 0.722 | 0.017 | 11.828 |
| SUP01 | Approved Supplier 01 (anonymized) | Packaging | 279 | 12 | 0.703 | 0.017 | 11.573 |
| SUP07 | Approved Supplier 07 (anonymized) | Packaging | 335 | 12 | 0.693 | 0.018 | 12.110 |
| SUP08 | Approved Supplier 08 (anonymized) | Trims | 316 | 12 | 0.690 | 0.018 | 11.649 |

Suppliers with weakest historical delivery/quality pattern:

| Supplier_ID | Supplier_Name | Primary_Category | PO_Count | Material_Count | Late_PO_Rate | Mean_Rejection_Rate | Mean_Delivery_Delay_Days |
| --- | --- | --- | --- | --- | --- | --- | --- |
| SUP09 | Approved Supplier 09 (anonymized) | Trims | 289 | 12 | 0.654 | 0.019 | 3.619 |
| SUP04 | Approved Supplier 04 (anonymized) | Printing Consumables | 281 | 12 | 0.601 | 0.017 | 2.918 |
| SUP12 | Approved Supplier 12 (anonymized) | Fabric | 298 | 12 | 0.332 | 0.018 | 0.544 |
| SUP06 | Approved Supplier 06 (anonymized) | Packaging | 312 | 12 | 0.321 | 0.017 | 0.481 |
| SUP08 | Approved Supplier 08 (anonymized) | Trims | 316 | 12 | 0.310 | 0.018 | 0.491 |
| SUP07 | Approved Supplier 07 (anonymized) | Packaging | 335 | 12 | 0.307 | 0.018 | 0.496 |
| SUP01 | Approved Supplier 01 (anonymized) | Packaging | 279 | 12 | 0.297 | 0.017 | 0.477 |
| SUP03 | Approved Supplier 03 (anonymized) | Fabric | 291 | 12 | 0.278 | 0.017 | 0.364 |

## Supplier x Material Variation

The supplier-material view ranks historical suppliers per material descriptively. It is not a recommended supplier list and does not make future availability or price claims.

`Low_History_Flag` is `True` when a supplier-material pair has fewer than 5 historical POs.

Largest supplier-performance spreads by material:

| Material_ID | Material_Name | Supplier_Options | Late_Rate_Spread | Rejection_Rate_Spread | Mean_Lead_Time_Spread |
| --- | --- | --- | --- | --- | --- |
| M008 | Care Label | 12 | 0.689 | 0.009 | 2.329 |
| M004 | Summer Melton | 12 | 0.616 | 0.007 | 7.583 |
| M001 | Single Jersey Cotton 160 GSM | 12 | 0.595 | 0.004 | 7.095 |
| M011 | Water-Based Ink | 12 | 0.569 | 0.005 | 4.167 |
| M010 | Carton Box | 12 | 0.568 | 0.006 | 5.149 |
| M002 | Single Jersey Cotton 180 GSM | 12 | 0.552 | 0.006 | 3.888 |
| M003 | Rib Cotton | 12 | 0.529 | 0.007 | 5.712 |
| M005 | Elastic Band | 12 | 0.496 | 0.008 | 7.686 |
| M007 | Neck Label | 12 | 0.487 | 0.006 | 4.933 |
| M009 | Poly Bag | 12 | 0.459 | 0.008 | 6.855 |

Top-ranked historical supplier rows by material:

| Material_ID | Material_Name | Historical_Supplier_Performance_Rank | Supplier_ID | PO_Count | Late_PO_Rate | Rejection_Rate | Mean_Actual_Lead_Time_Days |
| --- | --- | --- | --- | --- | --- | --- | --- |
| M001 | Single Jersey Cotton 160 GSM | 1 | SUP03 | 18 | 0.111 | 0.016 | 10.778 |
| M002 | Single Jersey Cotton 180 GSM | 1 | SUP06 | 24 | 0.125 | 0.017 | 10.292 |
| M003 | Rib Cotton | 1 | SUP03 | 27 | 0.185 | 0.016 | 10.074 |
| M004 | Summer Melton | 1 | SUP05 | 31 | 0.161 | 0.019 | 12 |
| M005 | Elastic Band | 1 | SUP10 | 20 | 0.200 | 0.017 | 11.650 |
| M006 | Sewing Thread | 1 | SUP08 | 23 | 0.261 | 0.019 | 11.913 |
| M007 | Neck Label | 1 | SUP03 | 33 | 0.121 | 0.018 | 10.121 |
| M008 | Care Label | 1 | SUP02 | 21 | 0.048 | 0.017 | 11.381 |
| M009 | Poly Bag | 1 | SUP02 | 31 | 0.194 | 0.015 | 13 |
| M010 | Carton Box | 1 | SUP10 | 32 | 0.250 | 0.017 | 13.781 |
| M011 | Water-Based Ink | 1 | SUP06 | 24 | 0.125 | 0.018 | 13.333 |
| M012 | Heat Transfer Film | 1 | SUP01 | 22 | 0.227 | 0.021 | 11.591 |

## Historical Procurement Risk

Evidence levels use fixed sample-count thresholds: Low evidence is fewer than 5 POs, Medium evidence is 5-19 POs, and High evidence is 20+ POs. Low-evidence materials are classified as `Insufficient Evidence`, never `Low` risk.

Risk classification uses empirical P75 and P90 thresholds across material histories for late rate, mean delay, mean rejection, and historical P90 lead time:

| Metric | Empirical_P75 | Empirical_P90 |
| --- | --- | --- |
| Late_PO_Rate | 0.359 | 0.387 |
| Mean_Delivery_Delay_Days | 0.985 | 1.070 |
| Mean_Rejection_Rate | 0.018 | 0.018 |
| Historical_P90_Actual_Lead_Time_Days | 21 | 21 |

Risk count by material:

| Historical_Procurement_Risk | Material_Count |
| --- | --- |
| Low | 6 |
| High | 5 |
| Medium | 1 |

Evidence level count by material:

| Evidence_Level | Material_Count |
| --- | --- |
| High | 12 |

Highest historical procurement-risk materials:

| Material_ID | Material_Name | PO_Count | Evidence_Level | Historical_Procurement_Risk | Late_PO_Rate | Mean_Delivery_Delay_Days | Mean_Rejection_Rate |
| --- | --- | --- | --- | --- | --- | --- | --- |
| M010 | Carton Box | 310 | High | High | 0.397 | 1.019 | 0.018 |
| M006 | Sewing Thread | 303 | High | High | 0.389 | 1.076 | 0.018 |
| M005 | Elastic Band | 279 | High | High | 0.344 | 0.932 | 0.019 |
| M011 | Water-Based Ink | 286 | High | High | 0.332 | 1.119 | 0.017 |
| M003 | Rib Cotton | 321 | High | High | 0.327 | 0.763 | 0.017 |
| M012 | Heat Transfer Film | 335 | High | Medium | 0.364 | 0.946 | 0.018 |
| M004 | Summer Melton | 286 | High | Low | 0.357 | 0.832 | 0.018 |
| M009 | Poly Bag | 303 | High | Low | 0.350 | 0.891 | 0.017 |
| M001 | Single Jersey Cotton 160 GSM | 286 | High | Low | 0.336 | 0.741 | 0.018 |
| M007 | Neck Label | 290 | High | Low | 0.331 | 0.762 | 0.017 |
| M002 | Single Jersey Cotton 180 GSM | 302 | High | Low | 0.315 | 0.974 | 0.017 |
| M008 | Care Label | 299 | High | Low | 0.311 | 0.716 | 0.018 |

## Phase 6 Gross Requirements Joined To Procurement Risk

The join preserves Phase 6 gross material requirements by `Material_ID × Horizon_Days`. The 30, 60, and 90-day rows are separate cumulative scenarios and are not summed together.

High-gross and high/insufficient-risk material-horizon rows:

| Horizon_Days | Material_ID | Material_Name | Total_Gross_Material_Requirement_If_Produced | Historical_Procurement_Risk | Evidence_Level | Late_PO_Rate | Mean_Rejection_Rate |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 30 | M003 | Rib Cotton | 5,628.194 | High | High | 0.327 | 0.017 |
| 30 | M006 | Sewing Thread | 677.853 | High | High | 0.389 | 0.018 |
| 30 | M011 | Water-Based Ink | 237.588 | High | High | 0.332 | 0.017 |
| 60 | M003 | Rib Cotton | 11,533.657 | High | High | 0.327 | 0.017 |
| 60 | M006 | Sewing Thread | 1,551.048 | High | High | 0.389 | 0.018 |
| 60 | M011 | Water-Based Ink | 558.462 | High | High | 0.332 | 0.017 |
| 90 | M003 | Rib Cotton | 20,786.577 | High | High | 0.327 | 0.017 |
| 90 | M006 | Sewing Thread | 2,853.017 | High | High | 0.389 | 0.018 |
| 90 | M011 | Water-Based Ink | 1,021.879 | High | High | 0.332 | 0.017 |

Lead-time-to-horizon ratios using historical P90 actual lead time:

| Horizon_Days | Material_ID | Material_Name | Historical_P90_Actual_Lead_Time_Days | Lead_Time_To_Horizon_Ratio | Total_Gross_Material_Requirement_If_Produced |
| --- | --- | --- | --- | --- | --- |
| 30 | M003 | Rib Cotton | 22 | 0.733 | 5,628.194 |
| 30 | M001 | Single Jersey Cotton 160 GSM | 21 | 0.700 | 5,971.187 |
| 30 | M002 | Single Jersey Cotton 180 GSM | 21 | 0.700 | 6,566.924 |
| 30 | M004 | Summer Melton | 21 | 0.700 | 4,420.400 |
| 30 | M006 | Sewing Thread | 21 | 0.700 | 677.853 |
| 30 | M007 | Neck Label | 21 | 0.700 | 27,501.377 |
| 30 | M008 | Care Label | 21 | 0.700 | 27,501.377 |
| 30 | M009 | Poly Bag | 21 | 0.700 | 27,501.377 |
| 30 | M011 | Water-Based Ink | 21 | 0.700 | 237.588 |
| 30 | M012 | Heat Transfer Film | 21 | 0.700 | 412.825 |
| 60 | M003 | Rib Cotton | 22 | 0.367 | 11,533.657 |
| 60 | M001 | Single Jersey Cotton 160 GSM | 21 | 0.350 | 16,360.427 |
| 60 | M002 | Single Jersey Cotton 180 GSM | 21 | 0.350 | 13,530.314 |
| 60 | M004 | Summer Melton | 21 | 0.350 | 10,997.857 |
| 60 | M006 | Sewing Thread | 21 | 0.350 | 1,551.048 |
| 60 | M007 | Neck Label | 21 | 0.350 | 63,247.065 |
| 60 | M008 | Care Label | 21 | 0.350 | 63,247.065 |
| 60 | M009 | Poly Bag | 21 | 0.350 | 63,247.065 |

## Historical Cost Context

Historical unit cost is included only as descriptive procurement history. It is not multiplied by gross requirements and is not used as a future budget estimate.

| Material_ID | Material_Name | Historical_Mean_Unit_Cost_EGP | Historical_Median_Unit_Cost_EGP | Historical_Std_Unit_Cost_EGP |
| --- | --- | --- | --- | --- |
| M011 | Water-Based Ink | 321.596 | 322.180 | 75.547 |
| M003 | Rib Cotton | 99.938 | 100.570 | 19.780 |
| M001 | Single Jersey Cotton 160 GSM | 99.257 | 100.485 | 21.350 |
| M002 | Single Jersey Cotton 180 GSM | 99.200 | 101.055 | 21.479 |
| M004 | Summer Melton | 98.641 | 100 | 21.014 |
| M005 | Elastic Band | 97.694 | 94.120 | 21.365 |
| M006 | Sewing Thread | 72.797 | 72.530 | 14.285 |
| M012 | Heat Transfer Film | 12.830 | 12.750 | 3.753 |
| M007 | Neck Label | 4.804 | 4.830 | 2.210 |
| M009 | Poly Bag | 4.579 | 4.460 | 2.251 |
| M010 | Carton Box | 4.571 | 4.605 | 2.291 |
| M008 | Care Label | 4.411 | 4.170 | 2.183 |

## Required Questions Answered

1. PO count: 3,600 rows and 3,600 unique `PO_ID` values were handled.
2. Data quality: duplicate PO rows, missing keys/dates, impossible date ordering, negative quantities, supplier/material resolution, unit consistency, and accepted+rejected vs ordered were checked in `procurement_data_quality.csv`.
3. On-time performance: historical on-time rate is 65.4% and late rate is 34.6%.
4. Lead time distribution: mean actual lead time is 12.310 days, median is 10, P90 is 21, and max is 33.
5. Delay distribution: mean delivery delay is 0.898 days, median is 0, P90 is 3, and max is 12.
6. Acceptance/rejection: mean rejection rate is 1.8%; mean acceptance rate is 98.2%.
7. Materials with highest delay/late/rejection are listed in material history sections and full detail is in `material_procurement_history.csv`.
8. Limited-evidence materials are any material with fewer than 20 POs; none appear in the top limited-evidence table if all materials exceed that threshold.
9. Supplier performance is summarized by historical POs only in `supplier_procurement_history.csv`; no future capacity is asserted.
10. Supplier-material variation is shown in `supplier_material_procurement_history.csv` and the descriptive rank file.
11. High-gross plus high-risk material-horizon rows are shown above and in `material_requirement_procurement_risk.csv`.
12. Lead times vs horizons use `Lead_Time_To_Horizon_Ratio`; this is timing context only, not an order-date recommendation.
13. Gross Phase 6 material requirements are not purchase quantities because raw-material on-hand stock, open PO balances, allocations, minimum order quantities, supplier constraints, scrap/yield, and availability dates are not present in the provided data.
14. Net shortage cannot be calculated because the provided datasets do not include a current raw-material inventory balance. This phase therefore does not subtract stock or open orders.

## Data Limitations

- Supplier identities are anonymized/modeled in the provided supplier master.
- Purchase order history ends at the provided records and does not prove future supplier capacity, pricing, or availability.
- No raw-material inventory table is provided, so material availability and net shortage remain unknown.
- Phase 6 gross material requirements are scenarios from the forecasting origin; they are not confirmed production or procurement orders.
- Historical unit costs describe observed POs only and are not future quotes.

## Validation Checks

| check | passed | detail |
| --- | --- | --- |
| all_po_rows_handled | 1 | raw_rows=3600; enriched_rows=3600 |
| all_po_ids_preserved | 1 | raw_unique_po=3600; enriched_unique_po=3600 |
| supplier_ids_resolve_or_are_flagged | 1 | unresolved_supplier_rows=0 |
| material_ids_resolve_or_are_flagged | 1 | unresolved_material_rows=0 |
| negative_actual_lead_times_not_accepted_silently | 1 | negative_actual_lead_rows=0 |
| negative_promised_lead_times_not_accepted_silently | 1 | negative_promised_lead_rows=0 |
| impossible_date_ordering_flagged | 1 | impossible_date_rows=0 |
| rates_within_0_1 | 1 | Acceptance_Rate=True; Rejection_Rate=True; On_Time_Numeric=True |
| material_requirement_horizons_30_60_90 | 1 | horizons=[30, 60, 90] |
| phase6_requirement_rows_preserved | 1 | phase6_rows=30; joined_rows=30 |
| no_cumulative_horizons_summed | 1 | Each material keeps separate 30, 60, and 90-day rows. |
| phase6_gross_requirements_unchanged | 1 | max_abs_horizon_total_difference=0.000000000000 |
| no_raw_material_stock_invented | 1 | forbidden_columns_present=[] |
| no_net_shortage_calculated | 1 | forbidden_columns_present=[] |
| no_purchase_quantity_calculated | 1 | forbidden_columns_present=[] |
| no_supplier_future_availability_assumed | 1 | forbidden_columns_present=[] |
| no_external_data_used | 1 | Inputs limited to provided Purchase_Orders.csv, Suppliers.csv, Materials.csv, Data_Dictionary.csv, and accepted Phase 6 material requirements. |

Validation passed: True.

## Files Created Or Modified

- `C:\Users\Acer\Documents\ChatGPT\El Sharnoby\outputs\phase7\phase7_procurement_risk_report.md`
- `C:\Users\Acer\Documents\ChatGPT\El Sharnoby\outputs\phase7\procurement_po_enriched.csv`
- `C:\Users\Acer\Documents\ChatGPT\El Sharnoby\outputs\phase7\material_procurement_history.csv`
- `C:\Users\Acer\Documents\ChatGPT\El Sharnoby\outputs\phase7\supplier_procurement_history.csv`
- `C:\Users\Acer\Documents\ChatGPT\El Sharnoby\outputs\phase7\supplier_material_procurement_history.csv`
- `C:\Users\Acer\Documents\ChatGPT\El Sharnoby\outputs\phase7\historical_procurement_risk.csv`
- `C:\Users\Acer\Documents\ChatGPT\El Sharnoby\outputs\phase7\material_requirement_procurement_risk.csv`
- `C:\Users\Acer\Documents\ChatGPT\El Sharnoby\outputs\phase7\historical_supplier_performance_rank.csv`
- `C:\Users\Acer\Documents\ChatGPT\El Sharnoby\outputs\phase7\procurement_data_quality.csv`
- `C:\Users\Acer\Documents\ChatGPT\El Sharnoby\outputs\phase7\validation_checks.csv`
- `C:\Users\Acer\Documents\ChatGPT\El Sharnoby\outputs\phase7\hardcoded_path_cleanup_note.md`
- `C:\Users\Acer\Documents\ChatGPT\El Sharnoby\src\phase7_procurement_risk.py`

## Recommendation For Phase 8

After review, Phase 8 can use the Phase 7 historical procurement risk outputs together with production process data only if it remains separate from final combined risk and does not invent missing material inventory. Any final ordering or shortage logic should wait until raw-material stock/open-PO data is provided or explicitly scoped as unavailable.