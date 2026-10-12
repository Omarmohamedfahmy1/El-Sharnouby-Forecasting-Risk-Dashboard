# Phase 5.1 Fair Policy Validation Report

## Scope Boundary

This is Phase 5.1 only. It audits the Phase 5 policy comparison on fair validation coverage and does not start BOM/material requirements, procurement risk, production risk, final combined risk, Streamlit, or Phase 6.

## Key Answers

1. Guarded hybrid had 2,100 windows instead of 2,114 because some selected guarded advanced models did not produce candidate predictions for every rolling-origin fold. The missing windows were not baseline rows; they were unavailable advanced-model rows.
2. Exact missing windows: 14.
3. Common-window WAPE: baseline 22.160%; guarded 20.098%.
4. Full equal-coverage WAPE with per-window baseline fallback: baseline 22.251%; guarded 20.196%.
5. Results by 30/60/90 horizon are shown below.
6. Guarded hybrid still beats the baseline fairly: True.
7. Final policy to use: `guarded_hybrid`.
8. Phase 5 future forecasts regenerated: False.
9. 90-day inventory risk counts changed: False.
10. Expected shortage or replenishment totals changed: False.

Decision reason: Equal-coverage guarded hybrid WAPE 20.196% beat baseline 22.251%.

## Missing Guarded Validation Windows

Every baseline validation window missing from the strict guarded policy is listed here:

| Product_ID | Location_ID | Horizon_Days | Fold_ID | Forecast_Origin | Guarded_Model | Guarded_Model_Source | Unavailable_Reason |
| --- | --- | --- | --- | --- | --- | --- | --- |
| P002 | LOC002 | 90 | 1 | 2025-09-28 | advanced_local_holt_winters_additive_52w | advanced | advanced_local_holt_winters_additive_52w was not generated for this fold because completed weekly training history was 104 weeks, below the 112-week minimum used by Phase 4. |
| P005 | LOC002 | 30 | 1 | 2025-09-28 | advanced_local_holt_winters_additive_52w | advanced | advanced_local_holt_winters_additive_52w was not generated for this fold because completed weekly training history was 104 weeks, below the 112-week minimum used by Phase 4. |
| P012 | LOC003 | 30 | 1 | 2025-09-28 | advanced_local_holt_winters_additive_52w | advanced | advanced_local_holt_winters_additive_52w was not generated for this fold because completed weekly training history was 104 weeks, below the 112-week minimum used by Phase 4. |
| P012 | LOC003 | 60 | 1 | 2025-09-28 | advanced_local_holt_winters_additive_52w | advanced | advanced_local_holt_winters_additive_52w was not generated for this fold because completed weekly training history was 104 weeks, below the 112-week minimum used by Phase 4. |
| P017 | LOC003 | 30 | 1 | 2025-09-28 | advanced_local_holt_winters_additive_52w | advanced | advanced_local_holt_winters_additive_52w was not generated for this fold because completed weekly training history was 104 weeks, below the 112-week minimum used by Phase 4. |
| P020 | LOC003 | 30 | 1 | 2025-09-28 | advanced_local_holt_winters_additive_52w | advanced | advanced_local_holt_winters_additive_52w was not generated for this fold because completed weekly training history was 104 weeks, below the 112-week minimum used by Phase 4. |
| P031 | LOC002 | 30 | 1 | 2025-09-28 | advanced_local_holt_winters_additive_52w | advanced | advanced_local_holt_winters_additive_52w was not generated for this fold because completed weekly training history was 104 weeks, below the 112-week minimum used by Phase 4. |
| P037 | LOC001 | 60 | 1 | 2025-09-28 | advanced_local_holt_winters_additive_52w | advanced | advanced_local_holt_winters_additive_52w was not generated for this fold because completed weekly training history was 105 weeks, below the 112-week minimum used by Phase 4. |
| P043 | LOC001 | 30 | 1 | 2025-09-28 | advanced_local_holt_winters_additive_52w | advanced | advanced_local_holt_winters_additive_52w was not generated for this fold because completed weekly training history was 105 weeks, below the 112-week minimum used by Phase 4. |
| P044 | LOC001 | 30 | 1 | 2025-09-28 | advanced_local_holt_winters_additive_52w | advanced | advanced_local_holt_winters_additive_52w was not generated for this fold because completed weekly training history was 105 weeks, below the 112-week minimum used by Phase 4. |
| P044 | LOC001 | 60 | 1 | 2025-09-28 | advanced_local_holt_winters_additive_52w | advanced | advanced_local_holt_winters_additive_52w was not generated for this fold because completed weekly training history was 105 weeks, below the 112-week minimum used by Phase 4. |
| P047 | LOC003 | 90 | 1 | 2025-09-28 | advanced_local_holt_winters_additive_52w | advanced | advanced_local_holt_winters_additive_52w was not generated for this fold because completed weekly training history was 104 weeks, below the 112-week minimum used by Phase 4. |
| P049 | LOC003 | 30 | 1 | 2025-09-28 | advanced_local_holt_winters_additive_52w | advanced | advanced_local_holt_winters_additive_52w was not generated for this fold because completed weekly training history was 104 weeks, below the 112-week minimum used by Phase 4. |
| P058 | LOC003 | 90 | 1 | 2025-09-28 | advanced_local_holt_winters_additive_52w | advanced | advanced_local_holt_winters_additive_52w was not generated for this fold because completed weekly training history was 104 weeks, below the 112-week minimum used by Phase 4. |

Missing windows by model:

| Guarded_Model | Missing_Windows |
| --- | --- |
| advanced_local_holt_winters_additive_52w | 14 |

Missing windows by demand class:

| Demand_Pattern_Class | Missing_Windows |
| --- | --- |
| intermittent | 9 |
| lumpy | 5 |

Missing windows by horizon:

| Horizon_Days | Missing_Windows |
| --- | --- |
| 30 | 8 |
| 60 | 3 |
| 90 | 3 |

## Common-Window Comparison

This comparison uses only windows where both policies had predictions without runtime fallback.

| Policy | Cumulative_WAPE | Cumulative_MAE | Cumulative_RMSE | Period_WAPE | Evaluation_Windows | Series_Count |
| --- | --- | --- | --- | --- | --- | --- |
| global_best_baseline | 22.160 | 118.519 | 311.114 | 92.410 | 2,100 | 177 |
| guarded_hybrid | 20.098 | 107.492 | 295.263 | 91.745 | 2,100 | 177 |

By horizon:

| Policy | Horizon_Days | Cumulative_WAPE | Cumulative_MAE | Cumulative_RMSE | Period_WAPE | Evaluation_Windows |
| --- | --- | --- | --- | --- | --- | --- |
| global_best_baseline | 30 | 28.942 | 75.734 | 179.489 | 93.213 | 700 |
| global_best_baseline | 60 | 22.778 | 120.577 | 298.593 | 92.595 | 705 |
| global_best_baseline | 90 | 19.562 | 159.522 | 411.797 | 92.028 | 695 |
| guarded_hybrid | 30 | 27.112 | 70.947 | 174.198 | 92.974 | 700 |
| guarded_hybrid | 60 | 20.753 | 109.858 | 279.161 | 91.889 | 705 |
| guarded_hybrid | 90 | 17.400 | 141.899 | 392.183 | 91.254 | 695 |

## Full-Coverage Comparison With Baseline Fallback

This comparison reflects the intended production-safe guarded policy: if a guarded advanced prediction is unavailable for a validation window, that specific window falls back to `weekly_seasonal_naive_52w`.

| Policy | Cumulative_WAPE | Cumulative_MAE | Cumulative_RMSE | Period_WAPE | Evaluation_Windows | Series_Count |
| --- | --- | --- | --- | --- | --- | --- |
| global_best_baseline | 22.251 | 118.593 | 310.515 | 92.627 | 2,114 | 177 |
| guarded_hybrid | 20.196 | 107.639 | 294.740 | 91.965 | 2,114 | 177 |

By horizon:

| Policy | Horizon_Days | Cumulative_WAPE | Cumulative_MAE | Cumulative_RMSE | Period_WAPE | Evaluation_Windows |
| --- | --- | --- | --- | --- | --- | --- |
| global_best_baseline | 30 | 29.256 | 76.211 | 179.565 | 93.790 | 708 |
| global_best_baseline | 60 | 22.908 | 121.053 | 298.612 | 92.744 | 708 |
| global_best_baseline | 90 | 19.544 | 159.086 | 410.937 | 92.173 | 698 |
| guarded_hybrid | 30 | 27.439 | 71.478 | 174.336 | 93.552 | 708 |
| guarded_hybrid | 60 | 20.888 | 110.380 | 279.266 | 92.039 | 708 |
| guarded_hybrid | 90 | 17.388 | 141.538 | 391.367 | 91.400 | 698 |

By fold:

| Policy | Fold_ID | Forecast_Origin | Cumulative_WAPE | Cumulative_MAE | Cumulative_RMSE | Evaluation_Windows |
| --- | --- | --- | --- | --- | --- | --- |
| global_best_baseline | 1 | 2025-09-28 | 20.825 | 96.594 | 202.347 | 531 |
| global_best_baseline | 2 | 2025-12-28 | 18.599 | 86.298 | 190.667 | 531 |
| global_best_baseline | 3 | 2026-03-29 | 26.878 | 160.935 | 446.535 | 531 |
| global_best_baseline | 4 | 2026-06-28 | 21.554 | 130.774 | 330.496 | 521 |
| guarded_hybrid | 1 | 2025-09-28 | 17.815 | 82.630 | 176.794 | 531 |
| guarded_hybrid | 2 | 2025-12-28 | 17.422 | 80.835 | 180.381 | 531 |
| guarded_hybrid | 3 | 2026-03-29 | 24.693 | 147.856 | 435.147 | 531 |
| guarded_hybrid | 4 | 2026-06-28 | 19.688 | 119.457 | 307.381 | 521 |

## Guarded Advanced Coverage

- Guarded advanced Product x Location x Horizon selections: 69
- Full expected fold coverage: 55
- Partial fold coverage: 14
- No fold coverage: 0

Coverage status:

| Coverage_Status | Count |
| --- | --- |
| full | 55 |
| partial | 14 |

Models with missing predictions:

| Guarded_Model | Selections | Partial_Selections | Missing_Windows |
| --- | --- | --- | --- |
| advanced_global_hist_gradient_boosting | 52 | 0 | 0 |
| advanced_local_holt_winters_additive_52w | 14 | 14 | 14 |
| advanced_local_ses_grid | 3 | 0 | 0 |

## Monotonic Reconciliation Review

The original model forecast is preserved in `Original_Model_Forecast`, and the planning forecast is in `Reconciled_Planning_Forecast`.

- Rows adjusted: 5
- Affected Product x Location pairs: 5
- Deterministic cummax match: True
- No reductions versus original model forecast: True
- Non-negative original and planning forecasts: True
- Increases only when necessary: True

Adjusted rows:

| Product_ID | Location_ID | Horizon_Days | Selected_Model | Original_Model_Forecast | Reconciled_Planning_Forecast | Monotonic_Reconciliation_Adjustment |
| --- | --- | --- | --- | --- | --- | --- |
| P005 | LOC002 | 60 | weekly_seasonal_naive_52w | 74.286 | 103.081 | 28.795 |
| P012 | LOC003 | 90 | weekly_seasonal_naive_52w | 982.286 | 1,189.805 | 207.519 |
| P020 | LOC002 | 60 | weekly_seasonal_naive_52w | 26.000 | 27.906 | 1.906 |
| P031 | LOC002 | 60 | weekly_seasonal_naive_52w | 45.429 | 61.260 | 15.831 |
| P056 | LOC002 | 60 | weekly_seasonal_naive_52w | 64.714 | 76.549 | 11.835 |

## Downstream Phase 5 Output Impact

Phase 5 future forecasts regenerated: False.

Inventory risk count changes:

| Horizon_Days | Low_Risk_Count_Before | Medium_Risk_Count_Before | High_Risk_Count_Before | Low_Risk_Count_After | Medium_Risk_Count_After | High_Risk_Count_After | Low_Risk_Count_Delta | Medium_Risk_Count_Delta | High_Risk_Count_Delta |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 30 | 125 | 9 | 43 | 125 | 9 | 43 | 0 | 0 | 0 |
| 60 | 106 | 5 | 66 | 106 | 5 | 66 | 0 | 0 | 0 |
| 90 | 92 | 0 | 85 | 92 | 0 | 85 | 0 | 0 | 0 |

Expected shortage and replenishment changes:

| Horizon_Days | Expected_Shortage_Total_Before | Recommended_Replenishment_Total_Before | Expected_Shortage_Total_After | Recommended_Replenishment_Total_After | Expected_Shortage_Total_Delta | Recommended_Replenishment_Total_Delta |
| --- | --- | --- | --- | --- | --- | --- |
| 30 | 18,610.458 | 27,501.377 | 18,610.458 | 27,501.377 | 0 | 0 |
| 60 | 52,661.267 | 63,247.065 | 52,661.267 | 63,247.065 | 0 | 0 |
| 90 | 106,723.191 | 117,853.191 | 106,723.191 | 117,853.191 | 0 | 0 |

## Validation Checks

| check | passed | detail |
| --- | --- | --- |
| baseline_validation_window_count_confirmed | 1 | baseline_windows=2114 |
| strict_guarded_missing_windows_identified | 1 | missing_windows=14; strict_missing_count=14 |
| common_policy_windows_identical | 1 | baseline_common=2100; guarded_common=2100 |
| full_policy_windows_identical | 1 | baseline_full=2114; guarded_full=2114 |
| full_evaluation_windows_equal | 1 | [{'Policy': 'global_best_baseline', 'Evaluation_Windows': 2114}, {'Policy': 'guarded_hybrid', 'Evaluation_Windows': 2114}] |
| fallback_used_for_missing_guarded_windows | 1 | fallback_rows=14 |
| guarded_advanced_selection_count_69 | 1 | guarded_advanced_rows=69 |
| all_177_product_location_pairs_retained | 1 | checked baseline and full-coverage guarded records |
| all_30_60_90_horizons_retained | 1 | horizons=[30, 60, 90] |
| no_validation_forecast_leakage | 1 | Phase 5.1 uses Phase 4 rolling-origin candidate records and Phase 4.1 guardrails only |
| validation_forecasts_non_negative | 1 | min_guarded=0.857143 |
| monotonic_reconciliation_deterministic | 1 | checked_rows=531 |
| monotonic_reconciliation_no_reductions | 1 | checked original vs planning forecast |
| monotonic_reconciliation_non_negative | 1 | checked original and planning forecasts |
| monotonic_reconciliation_only_necessary_increases | 1 | checked adjusted rows against prior cumulative horizon |
| final_forecast_rows_531 | 1 | rows=531; phase5_regenerated=False |
| final_forecast_pairs_177 | 1 | pairs=177 |

Validation passed: True.

## Files Created Or Modified

Created:

- `outputs\phase5_1\phase5_1_fair_policy_validation_report.md`
- `outputs\phase5_1\missing_guarded_validation_windows.csv`
- `outputs\phase5_1\common_window_policy_comparison.csv`
- `outputs\phase5_1\full_coverage_policy_comparison.csv`
- `outputs\phase5_1\guarded_model_coverage.csv`
- `outputs\phase5_1\monotonic_reconciliation_validation.csv`
- `outputs\phase5_1\validation_checks.csv`
- `src/phase5_1_fair_policy_validation.py`

Modified Phase 5 outputs: False.

Stop here for review before Phase 6.
