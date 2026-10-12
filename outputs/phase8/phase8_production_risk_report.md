# Phase 8 Production Risk Report

## Scope Boundary

This is Phase 8 only. It uses historical production orders to assess production execution risk for products that may require replenishment. It does not prove current factory capacity, future line availability, exact production scheduling, final combined project risk, final recommendations, action dates, Streamlit outputs, or Phase 9 work.

## Data Sources Used

- Raw data directory supplied at runtime: `C:\Users\Acer\Downloads\Sharnouby_Enterprise`
- Accepted Phase 6 directory: `C:\Users\Acer\Documents\ChatGPT\El Sharnoby\outputs\phase6`
- CSV inputs: `Production_Orders.csv`, `Product_Master.csv`, `Data_Dictionary.csv`, and `outputs/phase6/product_replenishment_requirements.csv`.
- No external data was used.

Relevant data dictionary rows:

| Table | Grain | Purpose | Real_vs_Modeled |
| --- | --- | --- | --- |
| Product_Master.csv | 1 row per public product | Public product catalog master and public retail price | Public/verified master data |
| Production_Orders.csv | 1 row per production order | Throughput, efficiency, bottleneck and delay analysis | Modeled using public capacity context |

## Production Data Quality Audit

- Historical production order rows handled: 2,500
- Unique `Production_Order_ID`: 2,500
- Duplicate `Production_Order_ID` rows: 0
- Historical production date span inspected: 2023-10-01 to 2026-09-30

| Check | Metric_Value | Issue_Count | Issue_Pct | Detail |
| --- | --- | --- | --- | --- |
| row_count | 2,500 | 0 | 0 | Production_Orders.csv rows handled in enriched output. |
| unique_production_order_id_count | 2,500 | 0 | 0 | duplicate_id_rows=0 |
| duplicate_production_order_id_rows | 0 | 0 | 0 | Rows sharing a Production_Order_ID with at least one other row. |
| missing_product_id | 0 | 0 | 0 | Product_ID missing before product resolution. |
| missing_start_date | 0 | 0 | 0 | Start_Date missing or unparseable. |
| missing_due_date | 0 | 0 | 0 | Due_Date missing or unparseable. |
| missing_completion_date | 0 | 0 | 0 | Completion_Date missing or unparseable. |
| invalid_date_ordering | 0 | 0 | 0 | Flags due date before start date or completion date before start date. |
| negative_quantities | 0 | 0 | 0 | Checked ['Planned_Qty', 'Produced_Qty', 'Good_Qty', 'Rejected_Qty']. |
| negative_efficiency_pct | 0 | 0 | 0 | Efficiency_Pct below zero. |
| efficiency_pct_above_100 | 0 | 0 | 0 | Efficiency_Pct above 100. |
| good_qty_greater_than_produced_qty | 0 | 0 | 0 | Good_Qty should not exceed Produced_Qty. |
| rejected_qty_relationship_mismatch | 0 | 0 | 0 | Checks Produced_Qty - Good_Qty - Rejected_Qty equals zero. |
| produced_qty_greater_than_planned_qty | 0 | 0 | 0 | Produced_Qty above Planned_Qty. |
| produced_qty_differs_from_planned_qty | 2,015 | 2,015 | 0.806 | Produced below planned=2015; above planned=0. This feeds plan attainment. |
| delay_days_source_mismatch | 2 | 2 | 0.001 | Compares source Delay_Days with Completion_Date - Due_Date. |
| unresolved_product_id | 0 | 0 | 0 | Product_ID not found in Product_Master.csv. |

Date-derived `Completion_Delay_Days` is used for analysis. Any mismatch with source `Delay_Days` remains flagged in the enriched file and data-quality output.

## Derived Production Metrics

The enriched order file adds `Production_Lead_Time_Days`, `Planned_Lead_Time_Days`, `Completion_Delay_Days`, `On_Time_Production_Flag`, `Plan_Attainment_Rate`, `Good_Yield_Rate`, `Rejection_Rate`, and `Good_vs_Planned_Rate`. Missing or zero denominators are not assumed.

Production lead time distribution:

| Statistic | Days |
| --- | --- |
| count | 2,500 |
| mean | 16.327 |
| std | 5.624 |
| min | 7 |
| 50% | 16 |
| 75% | 21 |
| 90% | 24 |
| 95% | 24 |
| max | 36 |

Completion delay distribution:

| Statistic | Days |
| --- | --- |
| count | 2,500 |
| mean | 0.892 |
| std | 2.422 |
| min | -1 |
| 50% | 0 |
| 75% | 0 |
| 90% | 4 |
| 95% | 7 |
| max | 16 |

Overall historical on-time production rate: 83.7%. Historical late production rate: 16.3%.

## Product-Level Production History

Product-level history includes order count, line count, lead time, delay, late/on-time rate, efficiency, plan attainment, yield, rejection, overtime, planned/produced/good/rejected quantities, most common recorded bottleneck, and latest production date.

Products with highest delay risk:

| Product_ID | Product_Name | Production_Order_Count | Late_Production_Order_Rate | Mean_Completion_Delay_Days | P90_Production_Lead_Time_Days |
| --- | --- | --- | --- | --- | --- |
| P027 | Girls' pajamas - I'm Just a girl | 22 | 0.409 | 2.864 | 24 |
| P047 | Mauve - طقم تيشيرت وشورت اطفال صيفي | 23 | 0.304 | 1.609 | 22 |
| P053 | PINK panther - بيجامة حريمي صيفي2024 | 21 | 0.286 | 1.952 | 26 |
| P056 | BATGIRL - بيجامة حريمي صيفي2024 | 67 | 0.269 | 1.448 | 25.400 |
| P007 | Summer children's boys-Black and turquoise | 28 | 0.250 | 1.286 | 22.300 |
| P003 | Summer children's girls-Hello kitty Rose & turquoise | 47 | 0.234 | 1.447 | 24.400 |
| P032 | Boys' sweatshirt-blue | 77 | 0.234 | 1.221 | 23.400 |
| P016 | Girls' summer pajamas-Watercolor Floral | 30 | 0.233 | 0.933 | 24 |
| P038 | Boys' Autumn Pajamas-Mickey Mouse | 66 | 0.212 | 1.333 | 23.500 |
| P001 | Summer children's girls-Happy | 114 | 0.211 | 1.228 | 24 |
| P050 | Yellow - طقم تيشيرت وشورت اطفال صيفي | 39 | 0.205 | 1.256 | 24 |
| P051 | Ice cream - بيجامة حريمي صيفي2024 | 117 | 0.197 | 1.103 | 23.400 |

Products with lower mean efficiency:

| Product_ID | Product_Name | Production_Order_Count | Mean_Efficiency_Pct | Mean_Plan_Attainment_Rate | Mean_Overtime_Hours |
| --- | --- | --- | --- | --- | --- |
| P019 | Boys' summer pajamas- Seeds OF | 26 | 76.973 | 0.861 | 7.562 |
| P034 | Boys' sweatshirt-black and white | 26 | 79.631 | 0.899 | 7.596 |
| P053 | PINK panther - بيجامة حريمي صيفي2024 | 21 | 79.738 | 0.884 | 6.776 |
| P007 | Summer children's boys-Black and turquoise | 28 | 79.775 | 0.885 | 7.779 |
| P020 | Boys' summer pajamas-Rock Band | 18 | 80.289 | 0.887 | 6.200 |
| P005 | Summer children's boys-Black and orange | 50 | 80.402 | 0.890 | 8.170 |
| P046 | Mustard - طقم تيشيرت وشورت اطفال صيفي | 29 | 80.472 | 0.886 | 7.328 |
| P028 | Girls' summer pajamas | 29 | 80.731 | 0.895 | 6.272 |
| P058 | OHANA - بيجامة حريمي صيفي 2024 | 27 | 80.826 | 0.893 | 4.696 |
| P025 | Boys' summer pajamas-Snoopy | 18 | 80.917 | 0.897 | 6.233 |
| P044 | Girls' autumn pajamas-Ice Cream | 52 | 80.931 | 0.899 | 7.160 |
| P010 | Boys' summer t-shirt-olive | 29 | 81.055 | 0.919 | 8.059 |

Products with lower plan attainment:

| Product_ID | Product_Name | Production_Order_Count | Mean_Plan_Attainment_Rate | Mean_Efficiency_Pct | Mean_Good_vs_Planned_Rate |
| --- | --- | --- | --- | --- | --- |
| P019 | Boys' summer pajamas- Seeds OF | 26 | 0.861 | 76.973 | 0.835 |
| P053 | PINK panther - بيجامة حريمي صيفي2024 | 21 | 0.884 | 79.738 | 0.864 |
| P007 | Summer children's boys-Black and turquoise | 28 | 0.885 | 79.775 | 0.863 |
| P046 | Mustard - طقم تيشيرت وشورت اطفال صيفي | 29 | 0.886 | 80.472 | 0.865 |
| P020 | Boys' summer pajamas-Rock Band | 18 | 0.887 | 80.289 | 0.867 |
| P005 | Summer children's boys-Black and orange | 50 | 0.890 | 80.402 | 0.866 |
| P058 | OHANA - بيجامة حريمي صيفي 2024 | 27 | 0.893 | 80.826 | 0.872 |
| P028 | Girls' summer pajamas | 29 | 0.895 | 80.731 | 0.873 |
| P036 | Girls' sweatshirt-Tinker Bell | 25 | 0.896 | 81.464 | 0.877 |
| P026 | Boys' summer pajamas-Bluey | 22 | 0.896 | 81.605 | 0.872 |
| P025 | Boys' summer pajamas-Snoopy | 18 | 0.897 | 80.917 | 0.876 |
| P034 | Boys' sweatshirt-black and white | 26 | 0.899 | 79.631 | 0.874 |

Products with higher rejection and lower good yield:

| Product_ID | Product_Name | Production_Order_Count | Mean_Rejection_Rate | Mean_Good_Yield_Rate | Total_Rejected_Qty |
| --- | --- | --- | --- | --- | --- |
| P023 | Girls' summer pajamas-Dumbo | 7 | 0.030 | 0.970 | 709 |
| P019 | Boys' summer pajamas- Seeds OF | 26 | 0.030 | 0.970 | 1,829 |
| P049 | Fuchsia - طقم تيشيرت وشورت اطفال صيفي | 48 | 0.029 | 0.971 | 3,261 |
| P009 | Boys' summer t-shirt-Aubergine | 38 | 0.028 | 0.972 | 2,749 |
| P026 | Boys' summer pajamas-Bluey | 22 | 0.028 | 0.972 | 1,253 |
| P016 | Girls' summer pajamas-Watercolor Floral | 30 | 0.027 | 0.973 | 1,623 |
| P024 | Boys' summer pajamas-Mickey | 44 | 0.027 | 0.973 | 2,753 |
| P034 | Boys' sweatshirt-black and white | 26 | 0.027 | 0.973 | 1,755 |
| P015 | Girls' summer pajamas-Stay cool | 23 | 0.027 | 0.973 | 1,409 |
| P027 | Girls' pajamas - I'm Just a girl | 22 | 0.027 | 0.973 | 1,679 |
| P008 | Summer children's boys-SpongeBob | 94 | 0.027 | 0.973 | 7,069 |
| P005 | Summer children's boys-Black and orange | 50 | 0.027 | 0.973 | 3,652 |

Products with limited production history:

| Product_ID | Product_Name | Production_Order_Count | Production_Evidence_Level | Historical_Production_Risk |
| --- | --- | --- | --- | --- |
| P023 | Girls' summer pajamas-Dumbo | 7 | Low | Insufficient Evidence |
| P052 | Teddy bear - بيجامة حريمي صيفي2024 | 10 | Medium | Low |
| P020 | Boys' summer pajamas-Rock Band | 18 | Medium | High |
| P025 | Boys' summer pajamas-Snoopy | 18 | Medium | Medium |
| P030 | Boys' pajamas -Mickey Mouse | 19 | Medium | Low |
| P022 | Girls' summer pajamas-Stitch | 21 | Medium | Low |
| P053 | PINK panther - بيجامة حريمي صيفي2024 | 21 | Medium | High |
| P057 | Save the planet بيجامة حريمي صيفي - 2024 | 21 | Medium | Low |
| P026 | Boys' summer pajamas-Bluey | 22 | Medium | High |
| P027 | Girls' pajamas - I'm Just a girl | 22 | Medium | High |
| P015 | Girls' summer pajamas-Stay cool | 23 | Medium | Medium |
| P047 | Mauve - طقم تيشيرت وشورت اطفال صيفي | 23 | Medium | High |
| P011 | Boys' summer t-shirt-Navy blue | 24 | Medium | Medium |
| P054 | Gazelle - بيجامة حريمي صيفي2024 | 24 | Medium | Low |

## Production Line Analysis

Line-level metrics describe historical performance only. They do not imply current line capacity, future line availability, or a line assignment recommendation.

Historically stronger line patterns:

| Line_ID | Production_Order_Count | Product_Count | On_Time_Order_Rate | Mean_Efficiency_Pct | Mean_Good_Yield_Rate | Mean_Overtime_Hours |
| --- | --- | --- | --- | --- | --- | --- |
| LINE-02 | 501 | 59 | 0.856 | 82.368 | 0.975 | 7.300 |
| LINE-01 | 525 | 59 | 0.855 | 82.184 | 0.975 | 6.545 |
| LINE-03 | 489 | 58 | 0.853 | 82.135 | 0.975 | 6.731 |
| LINE-05 | 483 | 57 | 0.824 | 81.881 | 0.975 | 7.360 |
| LINE-04 | 502 | 59 | 0.797 | 82.465 | 0.975 | 7.342 |

Historically weaker line patterns:

| Line_ID | Production_Order_Count | Product_Count | Late_Order_Rate | Mean_Completion_Delay_Days | Mean_Rejection_Rate | Mean_Overtime_Hours |
| --- | --- | --- | --- | --- | --- | --- |
| LINE-04 | 502 | 59 | 0.203 | 1.054 | 0.025 | 7.342 |
| LINE-05 | 483 | 57 | 0.176 | 0.954 | 0.025 | 7.360 |
| LINE-03 | 489 | 58 | 0.147 | 0.861 | 0.025 | 6.731 |
| LINE-01 | 525 | 59 | 0.145 | 0.851 | 0.025 | 6.545 |
| LINE-02 | 501 | 59 | 0.144 | 0.743 | 0.025 | 7.300 |

## Product x Line History

`Low_History_Flag` is `True` when a product-line pair has fewer than 5 historical production orders.

Largest product-line performance spreads:

| Product_ID | Product_Name | Line_Options | Late_Rate_Spread | Efficiency_Spread | Rejection_Rate_Spread |
| --- | --- | --- | --- | --- | --- |
| P027 | Girls' pajamas - I'm Just a girl | 5 | 0.750 | 13 | 0.014 |
| P047 | Mauve - طقم تيشيرت وشورت اطفال صيفي | 5 | 0.667 | 11.483 | 0.012 |
| P012 | Boys' summer t-shirt-light beige | 5 | 0.576 | 8.192 | 0.016 |
| P007 | Summer children's boys-Black and turquoise | 5 | 0.524 | 5 | 0.010 |
| P015 | Girls' summer pajamas-Stay cool | 5 | 0.500 | 15.400 | 0.014 |
| P020 | Boys' summer pajamas-Rock Band | 5 | 0.500 | 14.467 | 0.013 |
| P023 | Girls' summer pajamas-Dumbo | 4 | 0.500 | 12.200 | 0.038 |
| P050 | Yellow - طقم تيشيرت وشورت اطفال صيفي | 5 | 0.500 | 8.596 | 0.010 |
| P034 | Boys' sweatshirt-black and white | 4 | 0.500 | 8.050 | 0.013 |
| P028 | Girls' summer pajamas | 5 | 0.500 | 7.712 | 0.016 |
| P058 | OHANA - بيجامة حريمي صيفي 2024 | 5 | 0.429 | 8.489 | 0.006 |
| P016 | Girls' summer pajamas-Watercolor Floral | 5 | 0.429 | 7.155 | 0.020 |

## Bottleneck Analysis

Bottleneck analysis uses the provided `Primary_Bottleneck` field. Rows without a recorded bottleneck are kept as `No bottleneck recorded`. The table describes historical co-occurrence only and does not prove a bottleneck caused the delay or will recur.

| Primary_Bottleneck | Production_Order_Count | Bottleneck_Share | Average_Completion_Delay_Days | Average_Efficiency_Pct | Average_Overtime_Hours |
| --- | --- | --- | --- | --- | --- |
| No bottleneck recorded | 2,093 | 0.837 | -0.001 | 83.038 | 5.615 |
| Sewing | 134 | 0.054 | 7.052 | 73.360 | 13.993 |
| Finishing | 109 | 0.044 | 5.339 | 75.488 | 15.353 |
| Packing | 61 | 0.024 | 4.328 | 81.544 | 14.184 |
| Cutting | 59 | 0.024 | 4.186 | 84.398 | 14.329 |
| Printing | 44 | 0.018 | 4.409 | 84.389 | 13.959 |

## Historical Production Risk

Evidence levels use fixed sample-count thresholds: Low evidence is fewer than 10 historical orders, Medium evidence is 10-24 orders, and High evidence is 25+ orders. Low-evidence products are classified as `Insufficient Evidence`, not `Low` risk.

Risk classification is relative historical production risk within this dataset. Thresholds are empirical quantiles across products with at least the low-evidence minimum number of orders. The continuous metrics are retained in the output and should be used as evidence rather than converting the labels into arbitrary numeric weights.

| Metric | Medium_Threshold | High_Threshold | Direction |
| --- | --- | --- | --- |
| Late_Production_Order_Rate | 0.192 | 0.234 | Higher is higher risk |
| Mean_Completion_Delay_Days | 1.201 | 1.447 | Higher is higher risk |
| P90_Production_Lead_Time_Days | 24 | 24 | Higher is higher risk |
| Mean_Efficiency_Pct | 81.377 | 80.451 | Lower is higher risk |
| Mean_Plan_Attainment_Rate | 0.902 | 0.892 | Lower is higher risk |
| Mean_Good_Yield_Rate | 0.974 | 0.973 | Lower is higher risk |
| Mean_Rejection_Rate | 0.026 | 0.027 | Higher is higher risk |
| Mean_Overtime_Hours | 7.599 | 8.047 | Higher is higher risk |

Risk count by product:

| Historical_Production_Risk | Product_Count |
| --- | --- |
| Low | 22 |
| High | 21 |
| Medium | 15 |
| Insufficient Evidence | 1 |

Evidence level count by product:

| Production_Evidence_Level | Product_Count |
| --- | --- |
| High | 45 |
| Medium | 13 |
| Low | 1 |

Highest historical production-risk products:

| Product_ID | Product_Name | Production_Order_Count | Production_Evidence_Level | Historical_Production_Risk | Late_Production_Order_Rate | Mean_Efficiency_Pct | Mean_Plan_Attainment_Rate | Mean_Rejection_Rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| P027 | Girls' pajamas - I'm Just a girl | 22 | Medium | High | 0.409 | 81.209 | 0.904 | 0.027 |
| P047 | Mauve - طقم تيشيرت وشورت اطفال صيفي | 23 | Medium | High | 0.304 | 82.800 | 0.907 | 0.025 |
| P053 | PINK panther - بيجامة حريمي صيفي2024 | 21 | Medium | High | 0.286 | 79.738 | 0.884 | 0.023 |
| P056 | BATGIRL - بيجامة حريمي صيفي2024 | 67 | High | High | 0.269 | 81.340 | 0.902 | 0.024 |
| P007 | Summer children's boys-Black and turquoise | 28 | High | High | 0.250 | 79.775 | 0.885 | 0.025 |
| P003 | Summer children's girls-Hello kitty Rose & turquoise | 47 | High | High | 0.234 | 83.072 | 0.908 | 0.025 |
| P016 | Girls' summer pajamas-Watercolor Floral | 30 | High | High | 0.233 | 84.107 | 0.928 | 0.027 |
| P019 | Boys' summer pajamas- Seeds OF | 26 | High | High | 0.192 | 76.973 | 0.861 | 0.030 |
| P034 | Boys' sweatshirt-black and white | 26 | High | High | 0.192 | 79.631 | 0.899 | 0.027 |
| P024 | Boys' summer pajamas-Mickey | 44 | High | High | 0.182 | 81.559 | 0.903 | 0.027 |
| P026 | Boys' summer pajamas-Bluey | 22 | Medium | High | 0.182 | 81.605 | 0.896 | 0.028 |
| P049 | Fuchsia - طقم تيشيرت وشورت اطفال صيفي | 48 | High | High | 0.167 | 82.802 | 0.914 | 0.029 |
| P006 | Summer children's boys-Sonic | 31 | High | High | 0.161 | 81.348 | 0.901 | 0.024 |
| P036 | Girls' sweatshirt-Tinker Bell | 25 | High | High | 0.160 | 81.464 | 0.896 | 0.021 |
| P009 | Boys' summer t-shirt-Aubergine | 38 | High | High | 0.158 | 81.761 | 0.906 | 0.028 |

## Phase 6 Replenishment Joined To Production Risk

The join preserves accepted Phase 6 `Product_ID x Horizon_Days` replenishment rows. The 30, 60, and 90-day values remain separate cumulative scenarios and are not summed together.

High-replenishment products with high or insufficient historical production risk:

| Horizon_Days | Product_ID | Product_Name | Production_Equivalent_Replenishment_Qty | Historical_Production_Risk | Production_Evidence_Level | Late_Production_Order_Rate | Mean_Plan_Attainment_Rate |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 30 | P005 | Summer children's boys-Black and orange | 934.857 | High | High | 0.140 | 0.890 |
| 30 | P036 | Girls' sweatshirt-Tinker Bell | 800.571 | High | High | 0.160 | 0.896 |
| 30 | P049 | Fuchsia - طقم تيشيرت وشورت اطفال صيفي | 616.500 | High | High | 0.167 | 0.914 |
| 30 | P006 | Summer children's boys-Sonic | 582.286 | High | High | 0.161 | 0.901 |
| 30 | P027 | Girls' pajamas - I'm Just a girl | 378.857 | High | Medium | 0.409 | 0.904 |
| 30 | P053 | PINK panther - بيجامة حريمي صيفي2024 | 368.714 | High | Medium | 0.286 | 0.884 |
| 30 | P046 | Mustard - طقم تيشيرت وشورت اطفال صيفي | 326.659 | High | High | 0.103 | 0.886 |
| 30 | P058 | OHANA - بيجامة حريمي صيفي 2024 | 264 | High | High | 0.148 | 0.893 |
| 30 | P003 | Summer children's girls-Hello kitty Rose & turquoise | 224.571 | High | High | 0.234 | 0.908 |
| 30 | P016 | Girls' summer pajamas-Watercolor Floral | 195.857 | High | High | 0.233 | 0.928 |
| 30 | P034 | Boys' sweatshirt-black and white | 192.714 | High | High | 0.192 | 0.899 |
| 30 | P009 | Boys' summer t-shirt-Aubergine | 143.571 | High | High | 0.158 | 0.906 |
| 30 | P024 | Boys' summer pajamas-Mickey | 113.347 | High | High | 0.182 | 0.903 |
| 30 | P047 | Mauve - طقم تيشيرت وشورت اطفال صيفي | 6.571 | High | Medium | 0.304 | 0.907 |
| 60 | P036 | Girls' sweatshirt-Tinker Bell | 1,820.571 | High | High | 0.160 | 0.896 |
| 60 | P005 | Summer children's boys-Black and orange | 1,228.857 | High | High | 0.140 | 0.890 |
| 60 | P034 | Boys' sweatshirt-black and white | 1,167.857 | High | High | 0.192 | 0.899 |
| 60 | P049 | Fuchsia - طقم تيشيرت وشورت اطفال صيفي | 1,123.615 | High | High | 0.167 | 0.914 |
| 60 | P053 | PINK panther - بيجامة حريمي صيفي2024 | 773.286 | High | Medium | 0.286 | 0.884 |
| 60 | P006 | Summer children's boys-Sonic | 769.143 | High | High | 0.161 | 0.901 |

Replenishment compared with historical production-order scale:

| Horizon_Days | Product_ID | Product_Name | Production_Equivalent_Replenishment_Qty | Historical_Median_Planned_Qty | Historical_P90_Planned_Qty | Replenishment_To_Historical_Median_Order_Ratio | Replenishment_To_Historical_P90_Order_Ratio |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 30 | P033 | Boys' sweatshirt-LEO | 1,972.857 | 2,771 | 4,769 | 0.712 | 0.414 |
| 30 | P039 | Boys' Autumn Pajamas-Spider Man | 1,639.714 | 2,638 | 4,710.500 | 0.622 | 0.348 |
| 30 | P043 | Girls' autumn pajamas-Snow White | 1,400.349 | 2,319.500 | 4,220 | 0.604 | 0.332 |
| 30 | P038 | Boys' Autumn Pajamas-Mickey Mouse | 1,449.714 | 2,927.500 | 4,725.500 | 0.495 | 0.307 |
| 30 | P045 | Girls' autumn pajamas-Stitch | 1,149.714 | 2,355 | 4,835.900 | 0.488 | 0.238 |
| 30 | P044 | Girls' autumn pajamas-Ice Cream | 1,383.187 | 3,031 | 4,705.200 | 0.456 | 0.294 |
| 30 | P032 | Boys' sweatshirt-blue | 860.429 | 2,336 | 4,434.800 | 0.368 | 0.194 |
| 30 | P014 | Boys' summer t-shirt-Black | 1,063.571 | 2,890 | 4,546.800 | 0.368 | 0.234 |
| 30 | P017 | Girls' summer pajamas-flower | 935.822 | 2,713 | 4,679.200 | 0.345 | 0.200 |
| 30 | P002 | Summer children's girls-turtle | 812.347 | 2,511.500 | 4,943.800 | 0.323 | 0.164 |
| 30 | P001 | Summer children's girls-Happy | 812.000 | 2,678.500 | 4,539.300 | 0.303 | 0.179 |
| 30 | P037 | Girls' sweatshirt-Flower | 806.143 | 2,724 | 4,899 | 0.296 | 0.165 |
| 30 | P005 | Summer children's boys-Black and orange | 934.857 | 3,186 | 4,828.300 | 0.293 | 0.194 |
| 30 | P042 | Girls' autumn pajamas-Cheeky Charmins | 767.900 | 2,729 | 4,387.700 | 0.281 | 0.175 |
| 30 | P008 | Summer children's boys-SpongeBob | 869 | 3,225.500 | 4,768 | 0.269 | 0.182 |
| 30 | P049 | Fuchsia - طقم تيشيرت وشورت اطفال صيفي | 616.500 | 2,304 | 4,433.200 | 0.268 | 0.139 |
| 30 | P021 | Girls' summer pajamas-Minnie Mouse | 671.429 | 2,555 | 4,511.200 | 0.263 | 0.149 |
| 30 | P051 | Ice cream - بيجامة حريمي صيفي2024 | 633.571 | 2,452 | 4,487.400 | 0.258 | 0.141 |
| 30 | P035 | Girls' sweatshirt-Fuchsia | 598.857 | 2,319 | 4,221.000 | 0.258 | 0.142 |
| 30 | P004 | Summer children's girls-Hello kitty black&white | 533.857 | 2,135 | 4,674.600 | 0.250 | 0.114 |

P90 production lead time compared with horizon:

| Horizon_Days | Product_ID | Product_Name | P90_Production_Lead_Time_Days | P90_Production_Lead_Time_To_Horizon_Ratio | Production_Equivalent_Replenishment_Qty |
| --- | --- | --- | --- | --- | --- |
| 30 | P053 | PINK panther - بيجامة حريمي صيفي2024 | 26 | 0.867 | 368.714 |
| 30 | P056 | BATGIRL - بيجامة حريمي صيفي2024 | 25.400 | 0.847 | 0 |
| 30 | P023 | Girls' summer pajamas-Dumbo | 25.000 | 0.833 | 0 |
| 30 | P003 | Summer children's girls-Hello kitty Rose & turquoise | 24.400 | 0.813 | 224.571 |
| 30 | P028 | Girls' summer pajamas | 24.400 | 0.813 | 0 |
| 30 | P001 | Summer children's girls-Happy | 24 | 0.800 | 812.000 |
| 30 | P005 | Summer children's boys-Black and orange | 24 | 0.800 | 934.857 |
| 30 | P006 | Summer children's boys-Sonic | 24 | 0.800 | 582.286 |
| 30 | P008 | Summer children's boys-SpongeBob | 24 | 0.800 | 869 |
| 30 | P015 | Girls' summer pajamas-Stay cool | 24 | 0.800 | 434.131 |
| 30 | P016 | Girls' summer pajamas-Watercolor Floral | 24 | 0.800 | 195.857 |
| 30 | P017 | Girls' summer pajamas-flower | 24 | 0.800 | 935.822 |
| 30 | P019 | Boys' summer pajamas- Seeds OF | 24 | 0.800 | 0 |
| 30 | P024 | Boys' summer pajamas-Mickey | 24 | 0.800 | 113.347 |
| 30 | P025 | Boys' summer pajamas-Snoopy | 24 | 0.800 | 300 |
| 30 | P027 | Girls' pajamas - I'm Just a girl | 24 | 0.800 | 378.857 |
| 30 | P030 | Boys' pajamas -Mickey Mouse | 24 | 0.800 | 0 |
| 30 | P035 | Girls' sweatshirt-Fuchsia | 24 | 0.800 | 598.857 |
| 30 | P037 | Girls' sweatshirt-Flower | 24 | 0.800 | 806.143 |
| 30 | P044 | Girls' autumn pajamas-Ice Cream | 24 | 0.800 | 1,383.187 |

## Required Questions Answered

1. Historical production orders: 2,500 rows and 2,500 unique `Production_Order_ID` values.
2. Historical on-time production performance: 83.7% on time and 16.3% late.
3. Production lead time distribution: mean 16.327 days, median 16, P90 24, and max 36.
4. Products with the highest delay risk are listed in the product-level delay table and full file.
5. Products with lower efficiency or plan attainment are listed in separate product-level tables.
6. Products with higher rejection or lower good yield are listed in the rejection/yield table.
7. Limited production history uses evidence thresholds. Products below 25 orders are listed, and products below 10 orders are not assigned Low risk.
8. Production line performance is summarized by historical line metrics only.
9. Historical bottleneck frequencies and shares are shown in `bottleneck_analysis.csv`.
10. High-replenishment products with high or insufficient historical production risk are shown in the joined risk section.
11. Requirement-to-history ratios compare replenishment quantities with historical median and P90 planned order quantities. They are context indicators only.
12. P90 lead-time-to-horizon ratios compare historical P90 production lead time with 30/60/90-day horizons. They are not action dates.
13. This does not prove current factory capacity because the provided data has historical orders, not current line calendars, labor availability, WIP, shift plans, confirmed machine availability, or capacity reservations.
14. Limitations remain around current capacity, current line availability, exact scheduling, future bottlenecks, future efficiency, and integration with procurement risk.
15. Exact files created or modified are listed below.

## Data Limitations

- Production orders are modeled historical records in the provided dataset.
- The data does not include current factory capacity, open WIP, line calendars, shift staffing, machine availability, or current line assignments.
- Historical line performance does not prove a line is available now or in the future.
- Bottleneck fields describe recorded historical orders. They do not prove causality or future recurrence.
- Phase 6 replenishment quantities are planning scenarios, not confirmed production orders.

## Validation Checks

| check | passed | detail |
| --- | --- | --- |
| all_production_order_rows_handled | 1 | raw_rows=2500; enriched_rows=2500 |
| all_production_order_ids_preserved | 1 | raw_unique_orders=2500; enriched_unique_orders=2500 |
| product_ids_resolve_or_are_flagged | 1 | unresolved_product_rows=0 |
| invalid_date_ordering_not_accepted_silently | 1 | invalid_date_rows=0 |
| negative_quantities_not_accepted_silently | 1 | negative_quantity_rows=0 |
| rates_within_valid_ranges | 1 | On_Time_Production_Numeric=True; Plan_Attainment_Rate=True; Good_Yield_Rate=True; Rejection_Rate=True; Good_vs_Planned_Rate=True; Efficiency_Pct_0_100=True |
| good_qty_not_above_produced_qty | 1 | good_qty_gt_produced_rows=0 |
| rejected_qty_relationship_valid | 1 | produced_minus_good_minus_rejected_nonzero_rows=0 |
| all_phase6_product_replenishment_rows_preserved | 1 | phase6_rows=177; joined_rows=177 |
| all_30_60_90_horizons_retained | 1 | horizons=[30, 60, 90] |
| phase6_quantities_unchanged | 1 | max_abs_horizon_total_difference=0.000000000000 |
| no_cumulative_horizons_summed | 1 | Each product keeps separate 30, 60, and 90-day rows. |
| no_future_production_capacity_fabricated | 1 | forbidden_columns_present=[] |
| no_current_line_availability_fabricated | 1 | forbidden_columns_present=[] |
| no_exact_production_schedule_created | 1 | forbidden_columns_present=[] |
| no_external_data_used | 1 | Inputs limited to provided Production_Orders.csv, Product_Master.csv, Data_Dictionary.csv, and accepted Phase 6 product replenishment requirements. |

Validation passed: True.

## Files Created Or Modified

- `C:\Users\Acer\Documents\ChatGPT\El Sharnoby\outputs\phase8\phase8_production_risk_report.md`
- `C:\Users\Acer\Documents\ChatGPT\El Sharnoby\outputs\phase8\production_orders_enriched.csv`
- `C:\Users\Acer\Documents\ChatGPT\El Sharnoby\outputs\phase8\product_production_history.csv`
- `C:\Users\Acer\Documents\ChatGPT\El Sharnoby\outputs\phase8\line_production_history.csv`
- `C:\Users\Acer\Documents\ChatGPT\El Sharnoby\outputs\phase8\product_line_production_history.csv`
- `C:\Users\Acer\Documents\ChatGPT\El Sharnoby\outputs\phase8\bottleneck_analysis.csv`
- `C:\Users\Acer\Documents\ChatGPT\El Sharnoby\outputs\phase8\historical_production_risk.csv`
- `C:\Users\Acer\Documents\ChatGPT\El Sharnoby\outputs\phase8\product_replenishment_production_risk.csv`
- `C:\Users\Acer\Documents\ChatGPT\El Sharnoby\outputs\phase8\production_data_quality.csv`
- `C:\Users\Acer\Documents\ChatGPT\El Sharnoby\outputs\phase8\validation_checks.csv`
- `C:\Users\Acer\Documents\ChatGPT\El Sharnoby\src\phase8_production_risk.py`