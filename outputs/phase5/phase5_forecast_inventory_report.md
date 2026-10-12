# Phase 5 Forecast And Inventory Report

## Scope Boundary

This is Phase 5 only: final forecast generation plus finished-goods inventory and stockout logic. No BOM/material requirements, procurement risk, production risk, final combined business risk, or Streamlit dashboard was created.

## Final Forecasting Policy Test

The conservative guarded hybrid policy was tested before future forecasts were generated. It defaults to `weekly_seasonal_naive_52w` and allows a Phase 4 advanced model only when the Phase 4.1 guardrails are satisfied.

Policy validation:

| Policy | Cumulative_WAPE | Cumulative_MAE | Period_WAPE | Evaluation_Windows | Guarded_Advanced_Rows | Guarded_Baseline_Rows |
| --- | --- | --- | --- | --- | --- | --- |
| guarded_hybrid | 20.098 | 107.492 | 91.745 | 2,100 | 69 | 462 |
| global_best_baseline | 22.251 | 118.593 | 92.627 | 2,114 | 69 | 462 |

By horizon:

| Policy | Horizon_Days | Cumulative_WAPE | Cumulative_MAE | Period_WAPE | Evaluation_Windows |
| --- | --- | --- | --- | --- | --- |
| global_best_baseline | 30 | 29.256 | 76.211 | 93.790 | 708 |
| global_best_baseline | 60 | 22.908 | 121.053 | 92.744 | 708 |
| global_best_baseline | 90 | 19.544 | 159.086 | 92.173 | 698 |
| guarded_hybrid | 30 | 27.112 | 70.947 | 92.974 | 700 |
| guarded_hybrid | 60 | 20.753 | 109.858 | 91.889 | 705 |
| guarded_hybrid | 90 | 17.400 | 141.899 | 91.254 | 695 |

Final policy chosen: `guarded_hybrid`.

Reason: Guarded hybrid backtest cumulative WAPE 20.098% beat global baseline 22.251%.

## Forecast Periods

- Forecast origin: 2026-09-30
- 30-day horizon: 2026-10-01 through 2026-10-30
- 60-day horizon: 2026-10-01 through 2026-11-29
- 90-day horizon: 2026-10-01 through 2026-12-29

All windows were validated programmatically as exact 30/60/90-day periods.

## Forecast Coverage

- Forecast rows: 531
- Product x Location pairs forecast: 177
- Forecasts are cumulative gross outbound demand from the same origin.

Forecast demand totals:

| Horizon_Days | Forecast_Demand_Total |
| --- | --- |
| 30 | 37,801.008 |
| 60 | 79,879.831 |
| 90 | 140,059.639 |

Horizon monotonic reconciliation:

- Rows adjusted: 5
- Affected Product x Location pairs: 5

| Product_ID | Location_ID | Horizon_Days | Selected_Model | Model_Forecast_Demand_Before_Monotonic_Reconciliation | Forecast_Demand | Monotonic_Reconciliation_Adjustment |
| --- | --- | --- | --- | --- | --- | --- |
| P005 | LOC002 | 60 | weekly_seasonal_naive_52w | 74.286 | 103.081 | 28.795 |
| P012 | LOC003 | 90 | weekly_seasonal_naive_52w | 982.286 | 1,189.805 | 207.519 |
| P020 | LOC002 | 60 | weekly_seasonal_naive_52w | 26.000 | 27.906 | 1.906 |
| P031 | LOC002 | 60 | weekly_seasonal_naive_52w | 45.429 | 61.260 | 15.831 |
| P056 | LOC002 | 60 | weekly_seasonal_naive_52w | 64.714 | 76.549 | 11.835 |

The reconciliation is deterministic and only enforces that cumulative demand cannot decline as the horizon extends. The original selected-model totals are preserved in `Model_Forecast_Demand_Before_Monotonic_Reconciliation`.

## Inventory Alignment

Used September 2026 `Inventory_History.Closing_Stock` as latest finished-goods inventory. No inventory was fabricated.

- Latest inventory rows: 177
- Latest inventory Product x Location pairs: 177
- Negative latest stock rows: 0
- Safety stock missing rows: 0

Safety stock distribution:

| index | Safety_Stock_Units |
| --- | --- |
| count | 177 |
| mean | 71.836 |
| std | 121.530 |
| min | 5 |
| 5% | 5 |
| 25% | 6 |
| 50% | 16 |
| 75% | 74 |
| 95% | 312.000 |
| max | 672 |

Safety stock is used because it is directly provided in the latest inventory record. It is not combined with reorder point in the replenishment formula to avoid double-counting related planning logic.

## Stockout And Replenishment Results

At the 90-day horizon:

- Product x Location pairs expected to stock out: 85
- Product x Location pairs below reorder point: 40

Inventory summary by horizon:

| Horizon_Days | Forecast_Demand_Total | Expected_Shortage_Total | Recommended_Replenishment_Total | Pairs_With_Expected_Shortage | Pairs_Below_Reorder_Point | Low_Risk_Count | Medium_Risk_Count | High_Risk_Count |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 30 | 37,801.008 | 18,610.458 | 27,501.377 | 43 | 40 | 125 | 9 | 43 |
| 60 | 79,879.831 | 52,661.267 | 63,247.065 | 66 | 40 | 106 | 5 | 66 |
| 90 | 140,059.639 | 106,723.191 | 117,853.191 | 85 | 40 | 92 | 0 | 85 |

Largest 90-day expected shortages:

| Product_ID | Location_ID | Channel | Product_Family | Forecast_Demand | Available_Stock | Expected_Shortage_Units | Inventory_Risk |
| --- | --- | --- | --- | --- | --- | --- | --- |
| P037 | LOC003 | Wholesale | Sweatshirts | 9,732.857 | 2,014 | 7,718.857 | High |
| P033 | LOC003 | Wholesale | Sweatshirts | 6,725.143 | 45 | 6,680.143 | High |
| P038 | LOC003 | Wholesale | Pajamas/Homewear | 6,560.571 | 56 | 6,504.571 | High |
| P039 | LOC003 | Wholesale | Pajamas/Homewear | 5,949.429 | 258 | 5,691.429 | High |
| P043 | LOC003 | Wholesale | Pajamas/Homewear | 5,749.714 | 61 | 5,688.714 | High |
| P032 | LOC003 | Wholesale | Sweatshirts | 6,090.857 | 687 | 5,403.857 | High |
| P045 | LOC003 | Wholesale | Pajamas/Homewear | 5,509.714 | 207 | 5,302.714 | High |
| P044 | LOC003 | Wholesale | Pajamas/Homewear | 5,184.857 | 0 | 5,184.857 | High |
| P035 | LOC003 | Wholesale | Sweatshirts | 3,191.143 | 143 | 3,048.143 | High |
| P036 | LOC003 | Wholesale | Sweatshirts | 3,030.000 | 234 | 2,796.000 | High |

Largest 90-day recommended replenishment quantities:

| Product_ID | Location_ID | Channel | Product_Family | Forecast_Demand | Available_Stock | Safety_Stock_Units | Recommended_Replenishment_Qty | Inventory_Risk |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| P037 | LOC003 | Wholesale | Sweatshirts | 9,732.857 | 2,014 | 175 | 7,893.857 | High |
| P033 | LOC003 | Wholesale | Sweatshirts | 6,725.143 | 45 | 49 | 6,729.143 | High |
| P038 | LOC003 | Wholesale | Pajamas/Homewear | 6,560.571 | 56 | 34 | 6,538.571 | High |
| P039 | LOC003 | Wholesale | Pajamas/Homewear | 5,949.429 | 258 | 171 | 5,862.429 | High |
| P043 | LOC003 | Wholesale | Pajamas/Homewear | 5,749.714 | 61 | 67 | 5,755.714 | High |
| P032 | LOC003 | Wholesale | Sweatshirts | 6,090.857 | 687 | 98 | 5,501.857 | High |
| P045 | LOC003 | Wholesale | Pajamas/Homewear | 5,509.714 | 207 | 89 | 5,391.714 | High |
| P044 | LOC003 | Wholesale | Pajamas/Homewear | 5,184.857 | 0 | 74 | 5,258.857 | High |
| P035 | LOC003 | Wholesale | Sweatshirts | 3,191.143 | 143 | 33 | 3,081.143 | High |
| P051 | LOC003 | Wholesale | Pajamas/Homewear | 3,354.857 | 758 | 447 | 3,043.857 | High |

## Inventory Risk Rule

- High: forecast demand exceeds available stock within the horizon.
- Medium: no shortage within the horizon, but forecast demand plus source safety stock exceeds available stock, or available stock is at/below source reorder point.
- Low: available stock covers forecast demand plus source safety stock, and stock is above reorder point.

This is inventory-only risk, not the final combined project risk.

## Latest Inventory Accounting Mismatch Flags

Phase 2 found historical accounting mismatches. September 2026 latest rows with mismatch flags:

| Product_ID | Location_ID | Opening_Stock | Received_Qty | Returned_Qty | Sold_Qty | Damaged_Qty | Closing_Stock | Expected_Closing_Stock_From_Accounting | Latest_Inventory_Accounting_Mismatch_Flag |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| P002 | LOC002 | 0 | 55 | 6 | 62 | 0 | 0 | -1 | 1 |
| P002 | LOC003 | 4 | 504 | 0 | 588 | 3 | 0 | -83 | 1 |
| P004 | LOC003 | 0 | 445 | 0 | 462 | 2 | 0 | -19 | 1 |
| P042 | LOC003 | 0 | 435 | 0 | 456 | 1 | 0 | -22 | 1 |
| P044 | LOC003 | 29 | 463 | 0 | 504 | 1 | 0 | -13 | 1 |
| P048 | LOC003 | 0 | 905 | 0 | 1,056 | 2 | 0 | -153 | 1 |
| P049 | LOC003 | 0 | 789 | 0 | 942 | 2 | 0 | -155 | 1 |

These rows were flagged but not corrected or removed.

## Assumptions Avoided

- Did not assume raw-material inventory.
- Did not fabricate inventory, lost demand, production capacity, supplier availability, procurement risk, or production risk.
- Did not use reorder point in the replenishment formula.
- Did not round forecast demand internally.
- Did not use future data after 2026-09-30.

## Limitations

- `weekly_seasonal_naive_52w` uses completed historical weeks; the partial week ending 2026-10-04 was not used as a completed weekly training total.
- Stockout timing is based on the forecast daily path from the selected model, not observed future demand.
- Observed sales may be censored by historical stockouts; lost demand was not fabricated.
- Inventory accounting mismatches remain as source-data limitations.
- Procurement, production, material, and final combined risk remain out of scope until later phases.

## Validation Checks

| check | passed | detail |
| --- | --- | --- |
| final_policy_tested_before_use | 1 | final_policy=guarded_hybrid |
| final_forecast_starts_after_2026_09_30 | 1 | min_start=2026-10-01 |
| exact_30_60_90_day_windows | 1 | counts={30: 30, 60: 60, 90: 90} |
| all_177_pairs_forecast | 1 | pairs=177 |
| exactly_531_forecast_rows | 1 | rows=531 |
| forecasts_non_negative | 1 | min=4.285714 |
| monotonic_reconciliation_documented | 1 | adjusted_rows=5 |
| forecast_monotonic_60_ge_30 | 1 | checked all pairs |
| forecast_monotonic_90_ge_60 | 1 | checked all pairs |
| complete_inventory_join | 1 | missing_available_stock=0 |
| one_latest_inventory_row_per_pair | 1 | rows=177; pairs=177 |
| no_negative_available_stock | 1 | min=0 |
| no_negative_expected_shortage | 1 | min=0.000000 |
| no_negative_recommended_replenishment | 1 | min=0.000000 |
| expected_shortage_monotonic | 1 | checked all pairs |
| recommended_replenishment_monotonic | 1 | checked all pairs |
| safety_stock_from_source_complete | 1 | missing=0 |
| reorder_point_not_double_counted | 1 | Reorder_Point_Units used only for Below_Reorder_Point signal, not replenishment formula |
| stockout_date_after_origin_or_not_within_90 | 1 | checked populated stockout dates |
| no_fabricated_inventory | 1 | Inventory fields sourced only from September 2026 Inventory_History records |
| no_future_leakage | 1 | Forecast policy uses historical demand through 2026-09-30 and latest provided September inventory only |

Validation passed: True.

## Files Created Or Modified

- `outputs\phase5\phase5_forecast_inventory_report.md`
- `outputs\phase5\forecast_results.csv`
- `outputs\phase5\final_forecast_policy_validation.csv`
- `outputs\phase5\latest_inventory_snapshot.csv`
- `outputs\phase5\stockout_analysis.csv`
- `outputs\phase5\inventory_risk_summary.csv`
- `outputs\phase5\validation_checks.csv`
- `src/phase5_forecast_inventory.py`

Stop here for review before Phase 6.
