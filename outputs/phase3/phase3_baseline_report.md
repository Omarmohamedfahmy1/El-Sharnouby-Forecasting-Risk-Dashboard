# Phase 3 Baseline Forecasting Report

## Scope Boundary

This is Phase 3 only: simple baseline forecasting benchmarks. No advanced model comparison, final `forecast_results.csv`, future production forecast, stockout logic, replenishment, BOM requirements, procurement risk, production risk, final risk score, or Streamlit dashboard was created.

All baselines use only historical gross outbound demand from the Phase 2 daily `Product_ID x Location_ID` panel. No external data was used.

## Returns Clarification

`Inventory_History.Returned_Qty` reconciles exactly with returned transaction quantity grouped by order month, not `Return_Date` month. Therefore it is not evidence of the actual calendar timing of physical returns. Future return outcomes are leakage for demand forecasting and were not used as features. Gross outbound demand from `Sales_Transactions.Quantity` remains the forecasting target, while returns remain a separate descriptive behavior.

## Validation Design

- Available daily demand history: 2023-10-01 to 2026-09-30.
- Forecast origins: 2025-09-28, 2025-12-28, 2026-03-29, 2026-06-28.
- Origins are the last Sundays before quarter-end anchors so weekly aggregation can use completed weeks without partial-week leakage.
- Training window: expanding history from each series' first panel date through the forecast origin.
- Validation windows: exact 30, 60, and 90 calendar days after each origin.
- Backtest folds: 4 rolling-origin folds.
- Minimum training threshold: 90 days for a fold; under 180 days is marked reduced-history.
- No random train/test splits were used.

The last four days of available history are not used in validation because the latest complete-week origin that supports a full 90-day horizon is 2026-06-28.

## Baselines Evaluated

Daily baselines:

- `daily_naive_last_day`
- `daily_historical_mean`
- `daily_moving_average_7d`
- `daily_moving_average_14d`
- `daily_moving_average_28d`
- `daily_same_weekday_naive`
- `daily_croston_sba_alpha_0_1`

Weekly-distributed baselines:

- `weekly_naive_last_week`
- `weekly_historical_mean`
- `weekly_moving_average_4w`
- `weekly_moving_average_8w`
- `weekly_seasonal_naive_52w`
- `weekly_croston_sba_alpha_0_1`

Weekly models forecast weekly totals from completed training weeks, then distribute each weekly total evenly across days so the required 30/60/90-day horizons remain exact. This is only a frequency comparison benchmark, not a final modeling decision.

All forecasts were clipped at zero. No rounding was applied during evaluation.

## Daily Vs Weekly Frequency

Frequency comparison using each frequency's best baseline by horizon:

| Horizon_Days | Frequency | Best_Baseline_For_Frequency | Cumulative_WAPE | Cumulative_MAE | Period_WAPE | Period_MAE | Series_Count |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 30 | weekly_distributed | weekly_seasonal_naive_52w | 29.256 | 76.211 | 93.790 | 8.144 | 177 |
| 30 | daily | daily_moving_average_28d | 43.888 | 114.324 | 99.091 | 8.604 | 177 |
| 60 | weekly_distributed | weekly_seasonal_naive_52w | 22.908 | 121.053 | 92.744 | 8.168 | 177 |
| 60 | daily | daily_moving_average_28d | 44.768 | 236.567 | 99.843 | 8.793 | 177 |
| 90 | weekly_distributed | weekly_seasonal_naive_52w | 19.544 | 159.086 | 92.173 | 8.336 | 177 |
| 90 | daily | daily_moving_average_28d | 45.994 | 374.391 | 101.647 | 9.193 | 177 |

Current evidence: choose the best-performing baseline/frequency as a benchmark only. Phase 4 should compare stronger models against both the best direct daily baseline and the best weekly-distributed baseline because weekly smoothing may help intermittent demand, while daily baselines preserve operational timing.

## Overall Baseline Result

Best overall benchmark by cumulative WAPE:

- Frequency: `weekly_distributed`
- Baseline: `weekly_seasonal_naive_52w`
- Cumulative WAPE: 22.251%
- Cumulative MAE: 118.593
- Period WAPE: 92.627%

Overall metrics:

| Frequency | Baseline | Cumulative_WAPE | Cumulative_MAE | Period_WAPE | Period_MAE | Series_Count |
| --- | --- | --- | --- | --- | --- | --- |
| weekly_distributed | weekly_seasonal_naive_52w | 22.251 | 118.593 | 92.627 | 8.248 | 177 |
| daily | daily_moving_average_28d | 45.242 | 241.133 | 100.630 | 8.960 | 177 |
| weekly_distributed | weekly_moving_average_4w | 45.242 | 241.133 | 100.630 | 8.960 | 177 |
| daily | daily_moving_average_14d | 49.196 | 262.207 | 101.818 | 9.066 | 177 |
| daily | daily_croston_sba_alpha_0_1 | 49.274 | 262.624 | 102.240 | 9.104 | 177 |
| daily | daily_moving_average_7d | 53.083 | 282.923 | 102.338 | 9.112 | 177 |
| weekly_distributed | weekly_naive_last_week | 53.083 | 282.923 | 102.338 | 9.112 | 177 |
| daily | daily_same_weekday_naive | 53.274 | 283.940 | 120.800 | 10.756 | 177 |
| weekly_distributed | weekly_moving_average_8w | 54.860 | 292.392 | 105.853 | 9.425 | 177 |
| weekly_distributed | weekly_croston_sba_alpha_0_1 | 54.995 | 293.115 | 106.061 | 9.444 | 177 |
| weekly_distributed | weekly_historical_mean | 55.083 | 293.580 | 103.932 | 9.254 | 177 |
| daily | daily_historical_mean | 55.093 | 293.638 | 104.014 | 9.262 | 177 |

## Horizon Performance

Best baseline rows by horizon:

| Horizon_Days | Frequency | Baseline | Cumulative_WAPE | Cumulative_MAE | Period_WAPE | Period_MAE | Series_Count |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 30 | weekly_distributed | weekly_seasonal_naive_52w | 29.256 | 76.211 | 93.790 | 8.144 | 177 |
| 30 | daily | daily_moving_average_28d | 43.888 | 114.324 | 99.091 | 8.604 | 177 |
| 30 | weekly_distributed | weekly_moving_average_4w | 43.888 | 114.324 | 99.091 | 8.604 | 177 |
| 30 | daily | daily_moving_average_14d | 47.267 | 123.127 | 100.197 | 8.700 | 177 |
| 30 | daily | daily_croston_sba_alpha_0_1 | 47.624 | 124.056 | 100.591 | 8.734 | 177 |
| 30 | daily | daily_moving_average_7d | 51.462 | 134.055 | 100.516 | 8.728 | 177 |
| 30 | weekly_distributed | weekly_naive_last_week | 51.462 | 134.055 | 100.516 | 8.728 | 177 |
| 30 | daily | daily_same_weekday_naive | 51.761 | 134.833 | 120.045 | 10.424 | 177 |
| 30 | weekly_distributed | weekly_moving_average_8w | 52.032 | 135.539 | 104.100 | 9.039 | 177 |
| 30 | weekly_distributed | weekly_croston_sba_alpha_0_1 | 57.888 | 150.793 | 106.061 | 9.209 | 177 |
| 30 | weekly_distributed | weekly_historical_mean | 60.034 | 156.384 | 106.407 | 9.239 | 177 |
| 30 | daily | daily_historical_mean | 60.055 | 156.440 | 106.503 | 9.248 | 177 |
| 30 | daily | daily_naive_last_day | 90.069 | 234.623 | 113.640 | 9.867 | 177 |
| 60 | weekly_distributed | weekly_seasonal_naive_52w | 22.908 | 121.053 | 92.744 | 8.168 | 177 |
| 60 | daily | daily_moving_average_28d | 44.768 | 236.567 | 99.843 | 8.793 | 177 |
| 60 | weekly_distributed | weekly_moving_average_4w | 44.768 | 236.567 | 99.843 | 8.793 | 177 |
| 60 | daily | daily_croston_sba_alpha_0_1 | 48.520 | 256.394 | 101.494 | 8.939 | 177 |
| 60 | daily | daily_moving_average_14d | 48.687 | 257.274 | 101.060 | 8.901 | 177 |

## Demand Class Performance

Series per Phase 2 demand class:

| Demand_Class | Series_Count |
| --- | --- |
| erratic | 4 |
| intermittent | 139 |
| lumpy | 29 |
| smooth | 5 |

Best baseline rows by demand class and horizon:

| Demand_Pattern_Class | Horizon_Days | Frequency | Baseline | Cumulative_WAPE | Cumulative_MAE | Period_WAPE | Series_Count |
| --- | --- | --- | --- | --- | --- | --- | --- |
| erratic | 30 | weekly_distributed | weekly_seasonal_naive_52w | 33.694 | 47.277 | 54.006 | 4 |
| erratic | 30 | daily | daily_moving_average_28d | 35.861 | 50.317 | 57.572 | 4 |
| erratic | 30 | weekly_distributed | weekly_moving_average_4w | 35.861 | 50.317 | 57.572 | 4 |
| erratic | 30 | daily | daily_moving_average_14d | 39.115 | 54.884 | 59.255 | 4 |
| erratic | 30 | daily | daily_croston_sba_alpha_0_1 | 39.142 | 54.921 | 58.772 | 4 |
| erratic | 30 | daily | daily_moving_average_7d | 41.686 | 58.491 | 59.911 | 4 |
| erratic | 30 | weekly_distributed | weekly_naive_last_week | 41.686 | 58.491 | 59.911 | 4 |
| erratic | 30 | daily | daily_same_weekday_naive | 41.871 | 58.750 | 69.131 | 4 |
| erratic | 30 | weekly_distributed | weekly_moving_average_8w | 43.266 | 60.708 | 63.358 | 4 |
| erratic | 30 | weekly_distributed | weekly_croston_sba_alpha_0_1 | 54.552 | 76.543 | 66.164 | 4 |
| erratic | 30 | weekly_distributed | weekly_historical_mean | 65.441 | 91.822 | 72.701 | 4 |
| erratic | 30 | daily | daily_historical_mean | 65.481 | 91.878 | 72.688 | 4 |
| erratic | 30 | daily | daily_naive_last_day | 67.305 | 94.438 | 76.125 | 4 |
| erratic | 60 | weekly_distributed | weekly_seasonal_naive_52w | 30.102 | 79.902 | 54.758 | 4 |
| erratic | 60 | daily | daily_moving_average_28d | 41.051 | 108.964 | 62.071 | 4 |
| erratic | 60 | weekly_distributed | weekly_moving_average_4w | 41.051 | 108.964 | 62.071 | 4 |
| erratic | 60 | daily | daily_croston_sba_alpha_0_1 | 41.554 | 110.299 | 63.176 | 4 |
| erratic | 60 | daily | daily_same_weekday_naive | 42.642 | 113.188 | 75.277 | 4 |
| erratic | 60 | daily | daily_moving_average_7d | 42.750 | 113.473 | 64.304 | 4 |
| erratic | 60 | weekly_distributed | weekly_naive_last_week | 42.750 | 113.473 | 64.304 | 4 |
| erratic | 60 | daily | daily_moving_average_14d | 44.546 | 118.241 | 64.042 | 4 |
| erratic | 60 | weekly_distributed | weekly_moving_average_8w | 48.392 | 128.451 | 68.616 | 4 |
| erratic | 60 | weekly_distributed | weekly_croston_sba_alpha_0_1 | 50.774 | 134.774 | 68.948 | 4 |
| erratic | 60 | weekly_distributed | weekly_historical_mean | 62.286 | 165.331 | 71.420 | 4 |

Best intermittent-demand benchmark:

- `weekly_distributed` / `weekly_seasonal_naive_52w` with cumulative WAPE 18.864%

## Difficult Series

Highest cumulative WAPE among selected best baselines:

| Product_ID | Location_ID | Channel | Product_Family | Demand_Pattern_Class | Horizon_Days | Best_Frequency | Best_Baseline_Name | Cumulative_WAPE | Cumulative_MAE | Fallback_Flag_For_Phase4 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| P052 | LOC003 | Wholesale | Pajamas/Homewear | intermittent | 30 | daily | daily_historical_mean | 69.991 | 81.889 | 1 |
| P045 | LOC001 | Retail | Pajamas/Homewear | lumpy | 30 | weekly_distributed | weekly_seasonal_naive_52w | 62.534 | 24.857 | 1 |
| P057 | LOC001 | Retail | Pajamas/Homewear | intermittent | 30 | weekly_distributed | weekly_seasonal_naive_52w | 58.929 | 10.607 | 1 |
| P054 | LOC001 | Retail | Pajamas/Homewear | intermittent | 30 | daily | daily_moving_average_28d | 58.730 | 7.929 | 1 |
| P035 | LOC001 | Retail | Sweatshirts | intermittent | 30 | weekly_distributed | weekly_seasonal_naive_52w | 54.407 | 12.786 | 1 |
| P052 | LOC003 | Wholesale | Pajamas/Homewear | intermittent | 90 | weekly_distributed | weekly_historical_mean | 53.235 | 221.456 | 1 |
| P052 | LOC001 | Retail | Pajamas/Homewear | intermittent | 60 | weekly_distributed | weekly_seasonal_naive_52w | 52.515 | 9.321 | 1 |
| P025 | LOC001 | Retail | Pajamas/Homewear | intermittent | 30 | daily | daily_moving_average_28d | 52.455 | 8.393 | 1 |
| P028 | LOC003 | Wholesale | Pajamas/Homewear | intermittent | 30 | weekly_distributed | weekly_historical_mean | 50.556 | 152.427 | 1 |
| P052 | LOC001 | Retail | Pajamas/Homewear | intermittent | 30 | daily | daily_moving_average_14d | 50.216 | 4.143 | 1 |
| P025 | LOC001 | Retail | Pajamas/Homewear | intermittent | 60 | daily | daily_moving_average_28d | 48.848 | 15.143 | 1 |
| P035 | LOC003 | Wholesale | Sweatshirts | intermittent | 30 | weekly_distributed | weekly_seasonal_naive_52w | 48.830 | 210.214 | 1 |
| P043 | LOC001 | Retail | Pajamas/Homewear | intermittent | 30 | weekly_distributed | weekly_seasonal_naive_52w | 47.512 | 21.143 | 1 |
| P022 | LOC002 | Online | Pajamas/Homewear | intermittent | 30 | weekly_distributed | weekly_seasonal_naive_52w | 45.153 | 6.321 | 1 |
| P052 | LOC001 | Retail | Pajamas/Homewear | intermittent | 90 | daily | daily_moving_average_14d | 45.006 | 12.714 | 1 |

These are not failures to drop; they are candidates for Phase 4 fallback handling, pooling, or alternative model classes.

## Series Coverage And Status

- Product x Location series represented: 177
- Best-baseline rows: 531
- Fallback-flagged series for Phase 4 consideration: 168
- Series status counts: baseline_evaluated_normally: 167, reduced_history_evaluation: 10

Every one of the 177 Product x Location series has a status row and selected baseline benchmark for each 30/60/90-day horizon.

## Leakage Protection

Phase 3 used demand-history-only baselines. It did not use future `Quantity`, inventory outcomes, returns, discounts, production outcomes, procurement outcomes, customer fields, or future business facts. Price and discount remain EDA-only until a later phase can prove which values are known before forecast origin.

## Limitations

- Baselines are benchmarks, not final model recommendations.
- Weekly forecasts were evenly distributed across days only for comparable 30/60/90-day validation; this may hide within-week timing.
- Croston/SBA uses a fixed alpha of 0.1; Phase 4 can tune or compare alternatives.
- Strong intermittency remains: many series need fallback-aware modeling.
- No inventory or replenishment decisions were made in this phase.

## Validation Checks

| check | passed | detail |
| --- | --- | --- |
| all_177_product_location_pairs_represented | 1 | panel=177; best_baseline=177 |
| no_train_test_overlap | 1 | checked_rows=2114 |
| forecast_dates_after_training | 1 | checked_rows=2114 |
| forecasts_non_negative | 1 | min_forecast_total=0.000000 |
| horizons_exactly_30_60_90 | 1 | horizons=[30, 60, 90] |
| all_best_rows_have_finite_selection_score | 1 | best_rows=531 |

Validation passed: True.

## Files Created Or Modified

- `outputs\phase3\phase3_baseline_report.md`
- `outputs\phase3\baseline_metrics_overall.csv`
- `outputs\phase3\baseline_metrics_by_horizon.csv`
- `outputs\phase3\baseline_metrics_by_demand_class.csv`
- `outputs\phase3\baseline_metrics_by_series.csv`
- `outputs\phase3\best_baseline_by_series_horizon.csv`
- `outputs\phase3\validation_fold_summary.csv`
- `outputs\phase3\frequency_comparison.csv`
- `outputs\phase3\series_evaluation_status.csv`
- `outputs\phase3\validation_checks.csv`
- `src/phase3_forecasting_baseline.py`
- `outputs/phase2/phase2_cleaning_eda_report.md` was updated only with the requested returns clarification.

## Recommendation For Phase 4

Phase 4 should compare stronger forecasting approaches against these benchmarks, especially the best direct daily baseline, the best weekly-distributed baseline, and Croston/SBA for intermittent or lumpy demand. Candidate approaches should remain time-series validated and leakage-safe.

Stop here for approval before Phase 4.
