# Phase 4 Forecasting Model Comparison Report

## Scope Boundary

This is Phase 4 only: forecasting model comparison and validation-based model-selection policy. No final future `forecast_results.csv`, inventory/replenishment calculation, BOM/material logic, procurement risk, production risk, final business risk score, or Streamlit dashboard was created.

All models use only the provided project data. The business grain remains `Product_ID x Location_ID`, the target remains gross outbound `Quantity`, and the horizons remain exactly 30, 60, and 90 days.

## Models Tested

Baseline candidates recomputed for comparability:

- Phase 3 daily baselines: naive, historical mean, 7/14/28-day moving averages, same-weekday naive, fixed SBA/Croston.
- Phase 3 weekly-distributed baselines: naive last week, historical mean, 4/8-week moving averages, 52-week seasonal naive, fixed SBA/Croston.

Advanced candidates:

- `advanced_local_ses_grid`: local weekly simple exponential smoothing with alpha selected using training-history-only holdout.
- `advanced_local_holt_winters_additive_52w`: local additive Holt-Winters style weekly model, evaluated only where enough seasonal history exists.
- `advanced_local_sba_tuned`: local intermittent-demand SBA/Croston with alpha selected from training history.
- `advanced_global_hist_gradient_boosting`: global scikit-learn weekly tree model trained across series using shifted weekly lags, shifted rolling features, calendar fields, and one-hot encoded static product/location attributes.

No future prices, discounts, returns, inventory outcomes, production outcomes, or procurement outcomes were used. Future promotion plans are unavailable in the provided data, so forecasts are not conditioned on future promotions.

## Weekly Frequency Decision

Weekly frequency was retained as the primary advanced-modeling frequency because Phase 3 showed weekly-distributed baselines were materially better for cumulative business horizons. Weekly forecasts are converted into exact 30/60/90-day estimates by distributing each forecast weekly total evenly across its seven days, then summing the exact horizon days.

Frequency/model comparison by horizon:

| Horizon_Days | Model_Source | Frequency | Best_Model | Cumulative_WAPE | Cumulative_MAE | Period_WAPE | Series_Count |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 30 | advanced | weekly_distributed | advanced_global_hist_gradient_boosting | 28.434 | 74.068 | 93.901 | 177 |
| 30 | baseline | weekly_distributed | weekly_seasonal_naive_52w | 29.256 | 76.211 | 93.790 | 177 |
| 30 | baseline | daily | daily_moving_average_28d | 43.888 | 114.324 | 99.091 | 177 |
| 60 | baseline | weekly_distributed | weekly_seasonal_naive_52w | 22.908 | 121.053 | 92.744 | 177 |
| 60 | advanced | weekly_distributed | advanced_global_hist_gradient_boosting | 23.624 | 124.836 | 93.162 | 177 |
| 60 | baseline | daily | daily_moving_average_28d | 44.768 | 236.567 | 99.843 | 177 |
| 90 | baseline | weekly_distributed | weekly_seasonal_naive_52w | 19.544 | 159.086 | 92.173 | 177 |
| 90 | advanced | weekly_distributed | advanced_global_hist_gradient_boosting | 21.575 | 175.620 | 92.637 | 177 |
| 90 | baseline | daily | daily_moving_average_28d | 45.994 | 374.391 | 101.647 | 177 |

## Overall Results

Phase 3 benchmark recomputed in Phase 4:

- `weekly_seasonal_naive_52w` cumulative WAPE: 22.251%
- Period WAPE: 92.627%

Best single candidate overall:

- Source: `baseline`
- Model: `weekly_seasonal_naive_52w`
- Frequency: `weekly_distributed`
- Cumulative WAPE: 22.251%

Selected policy cumulative WAPE after keeping the baseline wherever it wins: 17.071%.

Overall model metrics:

| Model_Source | Frequency | Model | Cumulative_WAPE | Cumulative_MAE | Period_WAPE | Period_MAE | Series_Count |
| --- | --- | --- | --- | --- | --- | --- | --- |
| baseline | weekly_distributed | weekly_seasonal_naive_52w | 22.251 | 118.593 | 92.627 | 8.248 | 177 |
| advanced | weekly_distributed | advanced_global_hist_gradient_boosting | 23.378 | 124.601 | 93.018 | 8.282 | 177 |
| advanced | weekly_distributed | advanced_local_holt_winters_additive_52w | 31.170 | 176.132 | 92.577 | 8.747 | 177 |
| baseline | daily | daily_moving_average_28d | 45.242 | 241.133 | 100.630 | 8.960 | 177 |
| baseline | weekly_distributed | weekly_moving_average_4w | 45.242 | 241.133 | 100.630 | 8.960 | 177 |
| baseline | daily | daily_moving_average_14d | 49.196 | 262.207 | 101.818 | 9.066 | 177 |
| baseline | daily | daily_croston_sba_alpha_0_1 | 49.274 | 262.624 | 102.240 | 9.104 | 177 |
| baseline | daily | daily_moving_average_7d | 53.083 | 282.923 | 102.338 | 9.112 | 177 |
| baseline | weekly_distributed | weekly_naive_last_week | 53.083 | 282.923 | 102.338 | 9.112 | 177 |
| advanced | weekly_distributed | advanced_local_sba_tuned | 53.258 | 283.855 | 102.676 | 9.142 | 177 |
| baseline | daily | daily_same_weekday_naive | 53.274 | 283.940 | 120.800 | 10.756 | 177 |
| baseline | weekly_distributed | weekly_moving_average_8w | 54.860 | 292.392 | 105.853 | 9.425 | 177 |
| baseline | weekly_distributed | weekly_croston_sba_alpha_0_1 | 54.995 | 293.115 | 106.061 | 9.444 | 177 |
| baseline | weekly_distributed | weekly_historical_mean | 55.083 | 293.580 | 103.932 | 9.254 | 177 |
| baseline | daily | daily_historical_mean | 55.093 | 293.638 | 104.014 | 9.262 | 177 |
| advanced | weekly_distributed | advanced_local_ses_grid | 55.469 | 295.640 | 106.465 | 9.480 | 177 |
| baseline | daily | daily_naive_last_day | 90.599 | 482.875 | 114.312 | 10.178 | 177 |

## Horizon Results

Best rows by horizon:

| Horizon_Days | Model_Source | Frequency | Model | Cumulative_WAPE | Cumulative_MAE | Period_WAPE | Series_Count |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 30 | advanced | weekly_distributed | advanced_global_hist_gradient_boosting | 28.434 | 74.068 | 93.901 | 177 |
| 30 | baseline | weekly_distributed | weekly_seasonal_naive_52w | 29.256 | 76.211 | 93.790 | 177 |
| 30 | advanced | weekly_distributed | advanced_local_holt_winters_additive_52w | 30.907 | 87.976 | 90.404 | 177 |
| 30 | baseline | daily | daily_moving_average_28d | 43.888 | 114.324 | 99.091 | 177 |
| 30 | baseline | weekly_distributed | weekly_moving_average_4w | 43.888 | 114.324 | 99.091 | 177 |
| 30 | baseline | daily | daily_moving_average_14d | 47.267 | 123.127 | 100.197 | 177 |
| 30 | baseline | daily | daily_croston_sba_alpha_0_1 | 47.624 | 124.056 | 100.591 | 177 |
| 30 | baseline | daily | daily_moving_average_7d | 51.462 | 134.055 | 100.516 | 177 |
| 30 | baseline | weekly_distributed | weekly_naive_last_week | 51.462 | 134.055 | 100.516 | 177 |
| 30 | baseline | daily | daily_same_weekday_naive | 51.761 | 134.833 | 120.045 | 177 |
| 30 | baseline | weekly_distributed | weekly_moving_average_8w | 52.032 | 135.539 | 104.100 | 177 |
| 30 | advanced | weekly_distributed | advanced_local_sba_tuned | 54.881 | 142.961 | 102.217 | 177 |
| 30 | advanced | weekly_distributed | advanced_local_ses_grid | 55.144 | 143.645 | 105.408 | 177 |
| 30 | baseline | weekly_distributed | weekly_croston_sba_alpha_0_1 | 57.888 | 150.793 | 106.061 | 177 |
| 30 | baseline | weekly_distributed | weekly_historical_mean | 60.034 | 156.384 | 106.407 | 177 |
| 30 | baseline | daily | daily_historical_mean | 60.055 | 156.440 | 106.503 | 177 |
| 30 | baseline | daily | daily_naive_last_day | 90.069 | 234.623 | 113.640 | 177 |
| 60 | baseline | weekly_distributed | weekly_seasonal_naive_52w | 22.908 | 121.053 | 92.744 | 177 |
| 60 | advanced | weekly_distributed | advanced_global_hist_gradient_boosting | 23.624 | 124.836 | 93.162 | 177 |
| 60 | advanced | weekly_distributed | advanced_local_holt_winters_additive_52w | 31.029 | 175.995 | 92.055 | 177 |
| 60 | baseline | daily | daily_moving_average_28d | 44.768 | 236.567 | 99.843 | 177 |
| 60 | baseline | weekly_distributed | weekly_moving_average_4w | 44.768 | 236.567 | 99.843 | 177 |
| 60 | baseline | daily | daily_croston_sba_alpha_0_1 | 48.520 | 256.394 | 101.494 | 177 |
| 60 | baseline | daily | daily_moving_average_14d | 48.687 | 257.274 | 101.060 | 177 |

## Demand Class Results

Best rows by demand class and horizon:

| Demand_Pattern_Class | Horizon_Days | Model_Source | Model | Cumulative_WAPE | Cumulative_MAE | Period_WAPE | Series_Count |
| --- | --- | --- | --- | --- | --- | --- | --- |
| erratic | 30 | advanced | advanced_local_holt_winters_additive_52w | 22.240 | 38.031 | 48.427 | 4 |
| erratic | 30 | baseline | weekly_seasonal_naive_52w | 33.694 | 47.277 | 54.006 | 4 |
| erratic | 30 | advanced | advanced_global_hist_gradient_boosting | 34.861 | 48.914 | 55.958 | 4 |
| erratic | 30 | baseline | daily_moving_average_28d | 35.861 | 50.317 | 57.572 | 4 |
| erratic | 30 | baseline | weekly_moving_average_4w | 35.861 | 50.317 | 57.572 | 4 |
| erratic | 30 | baseline | daily_moving_average_14d | 39.115 | 54.884 | 59.255 | 4 |
| erratic | 30 | baseline | daily_croston_sba_alpha_0_1 | 39.142 | 54.921 | 58.772 | 4 |
| erratic | 30 | baseline | daily_moving_average_7d | 41.686 | 58.491 | 59.911 | 4 |
| erratic | 30 | baseline | weekly_naive_last_week | 41.686 | 58.491 | 59.911 | 4 |
| erratic | 30 | baseline | daily_same_weekday_naive | 41.871 | 58.750 | 69.131 | 4 |
| erratic | 30 | baseline | weekly_moving_average_8w | 43.266 | 60.708 | 63.358 | 4 |
| erratic | 30 | advanced | advanced_local_ses_grid | 44.988 | 63.124 | 62.931 | 4 |
| erratic | 30 | advanced | advanced_local_sba_tuned | 49.317 | 69.197 | 63.313 | 4 |
| erratic | 30 | baseline | weekly_croston_sba_alpha_0_1 | 54.552 | 76.543 | 66.164 | 4 |
| erratic | 30 | baseline | weekly_historical_mean | 65.441 | 91.822 | 72.701 | 4 |
| erratic | 30 | baseline | daily_historical_mean | 65.481 | 91.878 | 72.688 | 4 |
| erratic | 30 | baseline | daily_naive_last_day | 67.305 | 94.438 | 76.125 | 4 |
| erratic | 60 | advanced | advanced_local_holt_winters_additive_52w | 28.840 | 92.240 | 53.418 | 4 |
| erratic | 60 | baseline | weekly_seasonal_naive_52w | 30.102 | 79.902 | 54.758 | 4 |
| erratic | 60 | advanced | advanced_global_hist_gradient_boosting | 31.949 | 84.805 | 57.971 | 4 |
| erratic | 60 | baseline | daily_moving_average_28d | 41.051 | 108.964 | 62.071 | 4 |
| erratic | 60 | baseline | weekly_moving_average_4w | 41.051 | 108.964 | 62.071 | 4 |
| erratic | 60 | baseline | daily_croston_sba_alpha_0_1 | 41.554 | 110.299 | 63.176 | 4 |
| erratic | 60 | baseline | daily_same_weekday_naive | 42.642 | 113.188 | 75.277 | 4 |
| erratic | 60 | baseline | daily_moving_average_7d | 42.750 | 113.473 | 64.304 | 4 |
| erratic | 60 | baseline | weekly_naive_last_week | 42.750 | 113.473 | 64.304 | 4 |
| erratic | 60 | baseline | daily_moving_average_14d | 44.546 | 118.241 | 64.042 | 4 |
| erratic | 60 | advanced | advanced_local_sba_tuned | 45.239 | 120.082 | 65.556 | 4 |
| erratic | 60 | baseline | weekly_moving_average_8w | 48.392 | 128.451 | 68.616 | 4 |
| erratic | 60 | advanced | advanced_local_ses_grid | 48.813 | 129.568 | 67.718 | 4 |
| erratic | 60 | baseline | weekly_croston_sba_alpha_0_1 | 50.774 | 134.774 | 68.948 | 4 |
| erratic | 60 | baseline | weekly_historical_mean | 62.286 | 165.331 | 71.420 | 4 |

Intermittent/lumpy decisions selected advanced models for 215 of 504 Product x Location x Horizon rows. Complex models were not forced onto intermittent demand; the baseline remains selected whenever it wins.

## Selection Policy

For each Product x Location x Horizon, the selected model is the best advanced model only if its validation cumulative WAPE is lower than the best baseline candidate. Otherwise the baseline is retained.

- Baseline selections: 305
- Advanced selections: 226
- Total selections: 531

Selection examples:

| Product_ID | Location_ID | Horizon_Days | Demand_Pattern_Class | Selected_Model_Source | Selected_Model | Validation_Cumulative_WAPE | Baseline_Cumulative_WAPE | Improvement_Vs_Baseline_WAPE_Points | Robustness_Flag |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| P023 | LOC002 | 60 | intermittent | advanced | advanced_local_holt_winters_additive_52w | 8.340 | 38.944 | 30.603 | one_fold_dominates |
| P057 | LOC001 | 30 | intermittent | advanced | advanced_local_holt_winters_additive_52w | 31.225 | 58.929 | 27.704 | ok |
| P017 | LOC001 | 30 | intermittent | advanced | advanced_local_holt_winters_additive_52w | 9.750 | 36.871 | 27.122 | ok |
| P052 | LOC001 | 60 | intermittent | advanced | advanced_local_holt_winters_additive_52w | 25.467 | 52.515 | 27.048 | one_fold_dominates |
| P016 | LOC003 | 30 | intermittent | advanced | advanced_local_holt_winters_additive_52w | 5.838 | 31.514 | 25.676 | one_fold_dominates |
| P030 | LOC003 | 30 | intermittent | advanced | advanced_global_hist_gradient_boosting | 12.194 | 36.287 | 24.093 | ok |
| P019 | LOC002 | 30 | intermittent | advanced | advanced_local_holt_winters_additive_52w | 12.962 | 36.996 | 24.034 | one_fold_dominates |
| P019 | LOC002 | 60 | intermittent | advanced | advanced_local_holt_winters_additive_52w | 9.531 | 33.395 | 23.864 | one_fold_dominates |
| P011 | LOC002 | 30 | intermittent | advanced | advanced_local_holt_winters_additive_52w | 6.904 | 30.014 | 23.110 | ok |
| P054 | LOC001 | 60 | intermittent | advanced | advanced_local_holt_winters_additive_52w | 18.121 | 41.209 | 23.088 | one_fold_dominates |
| P019 | LOC003 | 60 | intermittent | advanced | advanced_global_hist_gradient_boosting | 13.786 | 35.279 | 21.493 | ok |
| P043 | LOC001 | 30 | intermittent | advanced | advanced_local_holt_winters_additive_52w | 26.024 | 47.512 | 21.488 | ok |
| P054 | LOC001 | 90 | intermittent | advanced | advanced_local_holt_winters_additive_52w | 8.922 | 29.746 | 20.824 | one_fold_dominates |
| P023 | LOC003 | 90 | intermittent | advanced | advanced_local_holt_winters_additive_52w | 1.540 | 21.648 | 20.108 | one_fold_dominates |
| P023 | LOC003 | 60 | intermittent | advanced | advanced_local_holt_winters_additive_52w | 14.419 | 34.280 | 19.861 | one_fold_dominates |
| P049 | LOC003 | 60 | intermittent | advanced | advanced_global_hist_gradient_boosting | 7.930 | 26.772 | 18.842 | ok |
| P002 | LOC002 | 30 | lumpy | advanced | advanced_local_holt_winters_additive_52w | 20.240 | 38.796 | 18.555 | ok |
| P052 | LOC001 | 90 | intermittent | advanced | advanced_local_holt_winters_additive_52w | 26.568 | 45.006 | 18.438 | one_fold_dominates |
| P012 | LOC003 | 30 | intermittent | advanced | advanced_local_holt_winters_additive_52w | 11.858 | 29.569 | 17.711 | ok |
| P035 | LOC003 | 30 | intermittent | advanced | advanced_local_holt_winters_additive_52w | 31.311 | 48.830 | 17.520 | one_fold_dominates |

## Robustness Across Folds

Fold-level metrics were exported to `model_metrics_by_fold.csv`. Selected rows include `Fold_Error_Dominance`; rows above 0.70 are flagged as `one_fold_dominates`.

Best fold-level candidate rows:

| Fold_ID | Horizon_Days | Model_Source | Frequency | Model | Cumulative_WAPE | Cumulative_MAE | Series_Count |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 4 | 30 | baseline | weekly_distributed | weekly_moving_average_8w | 16.696 | 53.811 | 177 |
| 2 | 30 | advanced | weekly_distributed | advanced_global_hist_gradient_boosting | 20.841 | 48.629 | 177 |
| 4 | 30 | advanced | weekly_distributed | advanced_global_hist_gradient_boosting | 21.032 | 67.787 | 177 |
| 4 | 30 | baseline | daily | daily_croston_sba_alpha_0_1 | 21.323 | 68.725 | 177 |
| 4 | 30 | baseline | daily | daily_moving_average_28d | 21.861 | 70.458 | 177 |
| 4 | 30 | baseline | weekly_distributed | weekly_moving_average_4w | 21.861 | 70.458 | 177 |
| 4 | 30 | advanced | weekly_distributed | advanced_local_holt_winters_additive_52w | 21.893 | 70.562 | 177 |
| 2 | 30 | baseline | weekly_distributed | weekly_seasonal_naive_52w | 23.801 | 55.536 | 177 |
| 4 | 30 | advanced | weekly_distributed | advanced_local_ses_grid | 23.981 | 77.290 | 177 |
| 4 | 30 | baseline | daily | daily_moving_average_14d | 24.624 | 79.362 | 177 |
| 4 | 30 | advanced | weekly_distributed | advanced_local_sba_tuned | 27.631 | 89.053 | 177 |
| 4 | 30 | baseline | daily | daily_same_weekday_naive | 28.065 | 90.452 | 177 |
| 4 | 30 | baseline | daily | daily_moving_average_7d | 28.191 | 90.858 | 177 |
| 4 | 30 | baseline | weekly_distributed | weekly_naive_last_week | 28.191 | 90.858 | 177 |
| 3 | 30 | baseline | weekly_distributed | weekly_seasonal_naive_52w | 30.321 | 85.990 | 177 |
| 4 | 30 | baseline | weekly_distributed | weekly_seasonal_naive_52w | 30.380 | 97.914 | 177 |
| 2 | 30 | baseline | weekly_distributed | weekly_croston_sba_alpha_0_1 | 30.533 | 71.243 | 177 |
| 2 | 30 | baseline | weekly_distributed | weekly_moving_average_8w | 30.555 | 71.296 | 177 |
| 2 | 30 | advanced | weekly_distributed | advanced_local_holt_winters_additive_52w | 32.218 | 78.907 | 163 |
| 1 | 30 | baseline | weekly_distributed | weekly_seasonal_naive_52w | 32.259 | 65.404 | 177 |
| 4 | 30 | baseline | weekly_distributed | weekly_croston_sba_alpha_0_1 | 33.055 | 106.537 | 177 |
| 3 | 30 | advanced | weekly_distributed | advanced_global_hist_gradient_boosting | 33.252 | 94.300 | 177 |
| 2 | 30 | advanced | weekly_distributed | advanced_local_sba_tuned | 33.917 | 79.140 | 177 |
| 2 | 30 | baseline | daily | daily_croston_sba_alpha_0_1 | 35.028 | 81.732 | 177 |

## Global Vs Local Finding

The global tree model was trained across all series with one-hot encoded identifiers/static fields plus shifted lag and rolling features. It is valid for comparison because it uses only history available before each origin and recursively feeds predictions into future lag features. Local statistical models remain useful but were not automatically preferred.

The HistGradientBoosting model used here does not expose a stable native `feature_importances_` attribute, so no `feature_importance.csv` was fabricated.

## Limitations

- These are validation comparisons, not final future forecasts.
- Weekly-to-daily distribution is a practical horizon-aggregation method and may smooth within-week timing.
- Observed sales may understate latent demand during stockout periods; lost demand was not fabricated.
- Future promotions/prices are unavailable, so forecasts are not promotion-conditioned.
- Holt-Winters was evaluated only where enough weekly seasonal history existed.
- More advanced models should still be compared carefully in the notebook/dashboard phases before operational deployment.

## Validation Checks

| check | passed | detail |
| --- | --- | --- |
| all_177_product_location_pairs_represented | 1 | panel=177; selected=177 |
| exactly_531_selection_rows | 1 | selected_rows=531 |
| no_train_test_overlap | 1 | checked_rows=2114 |
| forecast_dates_after_training | 1 | checked_rows=2114 |
| forecasts_non_negative | 1 | min_forecast_total=0.000000 |
| horizons_exactly_30_60_90 | 1 | horizons=[30, 60, 90] |
| rolling_features_shifted | 1 | weekly lag/rolling features use group shift(1); recursive ML forecasts append predictions before future lags |
| baseline_retained_where_it_wins | 1 | advanced selected only when advanced WAPE is lower than best baseline WAPE |
| finite_selected_metrics | 1 | selected_rows=531 |
| phase3_benchmark_comparable | 1 | Phase 3 winning baseline recomputed inside Phase 4 candidates |

Validation passed: True.

## Files Created Or Modified

- `outputs\phase4\phase4_model_comparison_report.md`
- `outputs\phase4\model_metrics_overall.csv`
- `outputs\phase4\model_metrics_by_horizon.csv`
- `outputs\phase4\model_metrics_by_demand_class.csv`
- `outputs\phase4\model_metrics_by_series.csv`
- `outputs\phase4\model_metrics_by_fold.csv`
- `outputs\phase4\selected_model_by_series_horizon.csv`
- `outputs\phase4\advanced_vs_baseline_comparison.csv`
- `outputs\phase4\model_improvement_distribution.csv`
- `outputs\phase4\frequency_comparison.csv`
- `outputs\phase4\validation_checks.csv`
- `src/phase4_model_comparison.py`

## Recommendation For Final Future Forecasting Policy

For Phase 5 and later forecast generation, use the selected model policy from `selected_model_by_series_horizon.csv`: retain the best baseline when advanced models do not improve validation cumulative WAPE, and use advanced models only for series/horizons where validation shows improvement. Keep this policy separate from future inventory and replenishment logic until Phase 5 is approved.

Stop here for review before any inventory or replenishment work.
