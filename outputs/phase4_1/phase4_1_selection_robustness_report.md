# Phase 4.1 Model Selection Robustness Report

## Scope Boundary

This is Phase 4.1 only. It validates the Phase 4 model-selection policy using leave-one-fold-out selection over the same four rolling validation folds. It does not generate final future forecasts, inventory/replenishment logic, BOM/material requirements, procurement risk, production risk, final risk scores, or Streamlit outputs.

## Why This Was Needed

The Phase 4 selected-policy WAPE was apparent because each Product x Location x Horizon model was selected using the same validation folds used to report its performance. Phase 4.1 estimates how the selection policy generalizes by selecting with three folds and evaluating on the held-out fold.

## Policies Compared

- `global_best_baseline`: use `weekly_seasonal_naive_52w` everywhere.
- `phase4_apparent_selection`: use the Phase 4 all-fold selected model per series/horizon.
- `leave_one_fold_out_selection`: for each held-out fold, select the best model using only the other folds, then evaluate on the held-out fold.

Overall policy comparison:

| Policy | Cumulative_WAPE | Cumulative_MAE | Period_WAPE | Period_MAE | Evaluation_Windows | Series_Count |
| --- | --- | --- | --- | --- | --- | --- |
| phase4_apparent_selection | 17.071 | 94.265 | 90.425 | 8.280 | 1,965 | 177 |
| global_best_baseline | 22.251 | 118.593 | 92.627 | 8.248 | 2,114 | 177 |
| leave_one_fold_out_selection | 27.464 | 146.379 | 94.884 | 8.449 | 2,114 | 177 |

Note: the apparent Phase 4 policy has fewer evaluation windows because some selected advanced models were not available for every fold. The global baseline and leave-one-fold-out policies are evaluated on the full set of available held-out windows.

Headline numbers:

- Apparent Phase 4 selected-policy cumulative WAPE: 17.071%
- Leave-one-fold-out selected-policy cumulative WAPE: 27.464%
- Global baseline cumulative WAPE: 22.251%

The leave-one-fold-out estimate is the primary robustness result.

## Results By Horizon

| Horizon_Days | Cumulative_WAPE | Cumulative_MAE | Period_WAPE | Period_MAE | Evaluation_Windows | Series_Count |
| --- | --- | --- | --- | --- | --- | --- |
| 30 | 38.243 | 99.621 | 98.046 | 8.513 | 708 | 177 |
| 60 | 29.192 | 154.260 | 95.843 | 8.441 | 708 | 177 |
| 90 | 22.827 | 185.814 | 93.226 | 8.432 | 698 | 177 |

## Results By Demand Class

| Demand_Pattern_Class | Cumulative_WAPE | Cumulative_MAE | Period_WAPE | Evaluation_Windows | Series_Count |
| --- | --- | --- | --- | --- | --- |
| erratic | 38.214 | 102.000 | 60.437 | 48 | 4 |
| intermittent | 26.519 | 151.749 | 99.105 | 1,659 | 139 |
| lumpy | 28.414 | 95.128 | 70.770 | 347 | 29 |
| smooth | 40.887 | 329.798 | 79.084 | 60 | 5 |

## Results By Held-Out Fold

| Fold_ID | Cumulative_WAPE | Cumulative_MAE | Period_WAPE | Evaluation_Windows | Series_Count |
| --- | --- | --- | --- | --- | --- |
| 1 | 34.854 | 161.664 | 109.449 | 531 | 177 |
| 2 | 20.566 | 95.423 | 97.225 | 531 | 177 |
| 3 | 32.477 | 194.462 | 90.981 | 531 | 177 |
| 4 | 22.041 | 133.729 | 85.637 | 521 | 177 |

## Selection Counts And Stability

Leave-one-fold-out selected source counts:

- Baseline selections: 1,618
- Advanced selections: 496

Selection stability distribution:

| Selection_Stability | Rows |
| --- | --- |
| 0.250 | 18 |
| 0.500 | 149 |
| 0.750 | 181 |
| 1 | 183 |

`Selection_Stability` is the maximum number of times one exact model was selected across four leave-one-fold-out runs divided by 4. Rows below 0.75 mean no exact model was selected in at least three of four runs; this is a descriptive instability flag, not a business-risk label.

## Advanced Selection Robustness

Phase 4 had 226 advanced selections. Leave-one-fold-out source behavior for those rows:

| LOO_Source_Result | Rows |
| --- | --- |
| switches_to_baseline | 106 |
| remains_advanced | 86 |
| unstable_source | 34 |

Rows where the Phase 4 advanced selection had `Robustness_Flag = one_fold_dominates`:

| LOO_Source_Result | Rows | Mean_LOO_WAPE | Median_Stability |
| --- | --- | --- | --- |
| remains_advanced | 15 | 27.275 | 0.750 |
| switches_to_baseline | 31 | 52.829 | 0.500 |
| unstable_source | 8 | 52.284 | 0.500 |

Advanced choices that remain advanced in at least three of four leave-one-fold-out runs are more trustworthy than advanced choices that switch back to baseline or have unstable model selection.

## Recommended Final Model-Selection Policy For Phase 5

Use the leave-one-fold-out robustness outputs as a guardrail:

- Keep `weekly_seasonal_naive_52w` as the global fallback benchmark.
- Use advanced models only where the Phase 4 selected row is also supported by leave-one-fold-out stability, especially where advanced is selected in at least three of four held-out runs.
- Fall back to the best baseline where selection is unstable, where the source switches back to baseline in leave-one-fold-out validation, or where one fold dominates the apparent improvement.
- Do not treat the 17.071% apparent WAPE as the expected future performance; use the leave-one-fold-out WAPE as the more honest planning estimate.

No arbitrary minimum improvement threshold was introduced.

## Validation Checks

| check | passed | detail |
| --- | --- | --- |
| heldout_fold_excluded_from_selection | 1 | Selection_Folds never contains Heldout_Fold_ID |
| all_4_folds_evaluated | 1 | folds=[1, 2, 3, 4] |
| all_177_product_location_pairs_represented | 1 | pairs=177 |
| all_horizons_evaluated | 1 | horizons=[30, 60, 90] |
| forecast_dates_after_training | 1 | Forecast_Start is after Forecast_Origin and Forecast_End matches the exact horizon |
| no_negative_forecasts | 1 | min_forecast_total=0.000000 |
| no_future_information_used_for_selection | 1 | LOO selection metrics aggregate only candidate records from folds other than the held-out fold |
| no_series_silently_dropped | 1 | stability_rows=531; phase4_selection_rows=531 |
| candidate_records_available | 1 | candidate_records=35365 |
| loo_records_available | 1 | loo_records=2114 |
| finite_loo_metrics | 1 | actual and forecast totals present for all LOO rows |

Validation passed: True.

## Files Created

- `outputs\phase4_1\phase4_1_selection_robustness_report.md`
- `outputs\phase4_1\leave_one_fold_out_policy_metrics.csv`
- `outputs\phase4_1\policy_comparison.csv`
- `outputs\phase4_1\selection_stability_by_series_horizon.csv`
- `outputs\phase4_1\selection_by_heldout_fold.csv`
- `outputs\phase4_1\advanced_selection_robustness.csv`
- `outputs\phase4_1\validation_checks.csv`
- `src/phase4_1_selection_robustness.py`

Stop here for review before Phase 5.
