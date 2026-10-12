# Phase 2 Data Cleaning And EDA Report

Generated: 2026-10-07 17:49:29

Data directory: `C:\Users\Acer\Downloads\Sharnouby_Enterprise`

## Scope Boundary

This is Phase 2 only. No forecasting models were trained, no 30/60/90-day forecasts were generated, no replenishment recommendations were calculated, no procurement or production risk scores were calculated, and no Streamlit dashboard was built.

All work uses only the provided CSV datasets. Raw files were read only. Derived files were written under `C:\Users\Acer\Documents\ChatGPT\El Sharnoby\data\processed` and `C:\Users\Acer\Documents\ChatGPT\El Sharnoby\outputs\phase2`.

The modeling grain remains `Product_ID x Location_ID`.

## Cleaning Decisions

- Parsed sales `Order_Date`, sales `Return_Date`, and inventory `Snapshot_Month` as dates.
- Standardized key columns by trimming whitespace in derived in-memory frames only.
- Did not impute missing values, fabricate records, alter stock quantities, or force accounting equations to balance.
- Preserved raw transaction data separately; the daily panel is a derived Product x Location EDA table.
- Built zero-demand dates only within each Product x Location pair's first-to-last observed demand window.

## Inventory Accounting Validation

Checked identity:

`Closing_Stock = Opening_Stock + Received_Qty + Returned_Qty - Sold_Qty - Damaged_Qty`

- Rows checked: 6,372
- Rows holding exactly: 6,225 (97.693%)
- Mismatch rows: 147 (2.307%)
- Nonzero mismatch median: 47
- Nonzero mismatch 95th percentile: 244.200
- Nonzero mismatch max: 2,108

Largest mismatch examples:

| Snapshot_Month | Product_ID | Location_ID | Opening_Stock | Received_Qty | Returned_Qty | Sold_Qty | Damaged_Qty | Expected_Closing_Stock | Closing_Stock | Closing_Stock_Mismatch |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2026-07-01 | P001 | LOC003 | 0 | 2,024 | 48 | 4,164 | 16 | -2,108 | 0 | 2,108 |
| 2026-06-01 | P001 | LOC003 | 0 | 1,868 | 24 | 3,486 | 12 | -1,606 | 0 | 1,606 |
| 2026-05-01 | P001 | LOC003 | 625 | 2,656 | 150 | 4,500 | 18 | -1,087 | 0 | 1,087 |
| 2026-06-01 | P002 | LOC003 | 0 | 679 | 66 | 1,392 | 7 | -654 | 0 | 654 |
| 2026-07-01 | P002 | LOC003 | 0 | 574 | 0 | 1,092 | 4 | -522 | 0 | 522 |

The data was not changed to force these rows to balance.

## Snapshot_Month Interpretation

- Snapshot day values: day 1: 6372
- Snapshot month range: 2023-10-01 to 2026-09-01
- Product x Location month transitions checked: 6,195
- Consecutive one-month transitions: 6,195 (100%)
- Previous `Closing_Stock` equals next `Opening_Stock`: 6,195 (100%)

Safest interpretation for later phases: `Snapshot_Month` is a monthly period label represented by the first day of the month. It is not safe to treat it as a point-in-time stock snapshot at the beginning of that day, because the 2026-09-01 rows include September sales through 2026-09-30 and reconcile to the full monthly `Sold_Qty`.

For future inventory alignment, use the latest inventory row as the latest completed monthly summary available in the dataset, and label `Closing_Stock` as the period closing finished-goods stock. Do not infer raw-material inventory.

## Sales Vs Inventory Demand Reconciliation

Monthly `Sales_Transactions.Quantity` was aggregated by `Month x Product_ID x Location_ID` and compared with `Inventory_History.Sold_Qty`.

- Rows compared: 6,372
- Rows with both sources: 6,353
- Inventory-only rows after zero sales fill: 19
- Sales-only rows: 0
- Exact matches: 6,372 (100%)
- Mean absolute difference: 0
- Max absolute difference: 0
- Correlation: 1

Mismatch examples:

No rows.

There is no evidence of systematic difference between monthly sales `Quantity` and inventory `Sold_Qty`; they reconcile exactly after representing missing transaction months as zero sales where inventory also records zero sold units.

## Returns Treatment And Forecast Target Decision

- Returned transaction rows: 8,543 (4.746%)
- Total sold quantity: 1,660,589
- Returned quantity by order date: 37,233 (2.242% of sold quantity)
- Return date present for returned rows: 100%
- Median return lag: 11 days
- 95th percentile return lag: 20 days

Decision: Use gross outbound demand: Sales_Transactions.Quantity aggregated by Order_Date x Product_ID x Location_ID. Inventory Sold_Qty matches Quantity by month exactly, and inventory Returned_Qty matches returned sales by order month exactly. Returns should be analyzed separately, not silently subtracted from demand.

Returns clarification for forecasting: `Inventory_History.Returned_Qty` reconciles exactly with returned transaction quantity grouped by order month, not by `Return_Date` month. Therefore it should not be interpreted as the actual calendar timing of physical returns, and future return outcomes must not be used as demand-forecasting features.

## Daily Product x Location Demand Panel

- Panel rows: 193,435
- Expected rows from pair observation windows: 193,435
- Nonzero daily rows before zero filling: 98,264
- Explicit zero-demand rows: 95,171
- Date range: 2023-10-01 to 2026-09-30
- Product x Location pairs: 177

Missing transaction rows inside an observed pair window were treated as zero observed demand days for EDA because monthly sales reconcile exactly to inventory `Sold_Qty` and the transaction table is line-level sales history. No zeros were created outside each pair's first and last observed demand date.

## Demand Behavior EDA

- Product x Location series analyzed: 177
- Total demand across panel: 1,660,589
- Mean zero-demand percentage across series: 49.223%
- Median zero-demand percentage across series: 50.091%
- Mean coefficient of variation across series: 1.400
- Demand pattern classes: erratic: 4, intermittent: 139, lumpy: 29, smooth: 5
- Series flagged as possibly needing fallback methods later: 168 (94.915%)

Top demand series:

| Product_ID | Location_ID | Channel | Product_Family | Total_Demand | Mean_Daily_Demand | Zero_Demand_Pct | Demand_Pattern_Class | May_Need_Fallback_Later |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| P051 | LOC003 | Wholesale | Pajamas/Homewear | 63,456 | 57.898 | 22.536 | smooth | 0 |
| P001 | LOC003 | Wholesale | Pajamas/Homewear | 60,438 | 55.144 | 24.726 | lumpy | 1 |
| P008 | LOC003 | Wholesale | Pajamas/Homewear | 57,048 | 52.242 | 26.007 | intermittent | 1 |
| P037 | LOC003 | Wholesale | Sweatshirts | 53,076 | 48.738 | 39.669 | intermittent | 1 |
| P029 | LOC003 | Wholesale | Pajamas/Homewear | 41,724 | 38.174 | 33.486 | intermittent | 1 |

Location/channel summary:

| Location_ID | Channel | Total_Demand | Mean_Daily_Demand | Zero_Demand_Pct | Product_Count |
| --- | --- | --- | --- | --- | --- |
| LOC003 | Wholesale | 1,475,076 | 22.893 | 55.362 | 59 |
| LOC002 | Online | 99,339 | 1.540 | 44.414 | 59 |
| LOC001 | Retail | 86,174 | 1.336 | 47.831 | 59 |

Product-family summary:

| Product_Family | Total_Demand | Mean_Daily_Demand | Zero_Demand_Pct | Product_Count |
| --- | --- | --- | --- | --- |
| Pajamas/Homewear | 1,176,405 | 8.545 | 49.334 | 42 |
| Sweatshirts | 198,807 | 10.096 | 51.168 | 6 |
| T-Shirts | 155,397 | 7.909 | 47.817 | 6 |
| Kids Sets | 129,980 | 7.916 | 47.378 | 5 |

Weekly and monthly pattern summaries were exported for Phase 3 review. They should be treated as descriptive EDA, not model selection.

## Sparsity And Intermittency Definitions

For each Product x Location series:

- `Demand_Frequency_Pct = nonzero demand days / active days`.
- `Zero_Demand_Pct = zero demand days / active days`.
- `Average_Demand_Interval_Days = active days / nonzero demand days`.
- `Nonzero_Demand_CV2 = squared coefficient of variation for nonzero daily demand`.
- Demand pattern classes use documented EDA thresholds: smooth when ADI <= 1.32 and CV2 <= 0.49, intermittent when ADI > 1.32 and CV2 <= 0.49, erratic when ADI <= 1.32 and CV2 > 0.49, and lumpy when ADI > 1.32 and CV2 > 0.49.

These flags are for Phase 3 fallback planning only. No final forecasting model has been selected.

## Price And Discount Exploration

Sale-day-only exploratory correlations:

- Avg_List_Price_EGP: correlation with sale-day demand = 0.041
- Avg_Discount_Pct: correlation with sale-day demand = 0.680
- Avg_Net_Unit_Price_EGP: correlation with sale-day demand = -0.370

Demand is visibly associated with discount in the aggregate EDA, but this is not causal evidence. Wholesale orders have much higher quantities and higher discounts, so channel and product mix are major confounders. Any future feature use must avoid leakage and use only price/discount information known before the forecast origin.

## Leakage Risks

Created `leakage_risk_table.csv`. High-risk fields include realized financial outcomes, return outcomes, period-end inventory outcomes, and future procurement/production outcomes. `List_Price_EGP` and `Discount_Pct` are conditional: safe only if known as planned future inputs, not if derived from same-day realized transactions.

## Data Limitations

- No current raw-material inventory table exists; do not calculate current material stock.
- `Snapshot_Month` is monthly-period data, not a daily stock snapshot.
- Inventory accounting mismatches exist in 147 rows and should be handled transparently later.
- Sales and inventory use three commercial locations; head office and factory locations have no sales/inventory demand rows.
- Gross demand is selected as the target; returns are real and should be monitored separately.
- EDA associations with price/discount are confounded and not causal.

## Files Created Or Modified

- `C:\Users\Acer\Documents\ChatGPT\El Sharnoby\data\processed\daily_product_location_demand_panel.csv`
- `C:\Users\Acer\Documents\ChatGPT\El Sharnoby\data\processed\monthly_sales_inventory_reconciliation.csv`
- `C:\Users\Acer\Documents\ChatGPT\El Sharnoby\outputs\phase2\phase2_cleaning_eda_report.md`
- `C:\Users\Acer\Documents\ChatGPT\El Sharnoby\outputs\phase2\inventory_accounting_validation.csv`
- `C:\Users\Acer\Documents\ChatGPT\El Sharnoby\outputs\phase2\inventory_accounting_summary.csv`
- `C:\Users\Acer\Documents\ChatGPT\El Sharnoby\outputs\phase2\inventory_month_continuity.csv`
- `C:\Users\Acer\Documents\ChatGPT\El Sharnoby\outputs\phase2\inventory_month_interpretation_summary.csv`
- `C:\Users\Acer\Documents\ChatGPT\El Sharnoby\outputs\phase2\sales_inventory_reconciliation_summary.csv`
- `C:\Users\Acer\Documents\ChatGPT\El Sharnoby\outputs\phase2\sales_inventory_reconciliation_by_month.csv`
- `C:\Users\Acer\Documents\ChatGPT\El Sharnoby\outputs\phase2\returns_summary.csv`
- `C:\Users\Acer\Documents\ChatGPT\El Sharnoby\outputs\phase2\returns_reconciliation.csv`
- `C:\Users\Acer\Documents\ChatGPT\El Sharnoby\outputs\phase2\daily_demand_panel_summary.csv`
- `C:\Users\Acer\Documents\ChatGPT\El Sharnoby\outputs\phase2\demand_series_eda.csv`
- `C:\Users\Acer\Documents\ChatGPT\El Sharnoby\outputs\phase2\weekday_demand_pattern.csv`
- `C:\Users\Acer\Documents\ChatGPT\El Sharnoby\outputs\phase2\monthly_demand_pattern.csv`
- `C:\Users\Acer\Documents\ChatGPT\El Sharnoby\outputs\phase2\location_channel_demand_summary.csv`
- `C:\Users\Acer\Documents\ChatGPT\El Sharnoby\outputs\phase2\product_family_demand_summary.csv`
- `C:\Users\Acer\Documents\ChatGPT\El Sharnoby\outputs\phase2\price_discount_summary.csv`
- `C:\Users\Acer\Documents\ChatGPT\El Sharnoby\outputs\phase2\discount_bin_demand_summary.csv`
- `C:\Users\Acer\Documents\ChatGPT\El Sharnoby\outputs\phase2\price_bin_demand_summary.csv`
- `C:\Users\Acer\Documents\ChatGPT\El Sharnoby\outputs\phase2\leakage_risk_table.csv`
- `C:\Users\Acer\Documents\ChatGPT\El Sharnoby\outputs\phase2\data_quality_summary.csv`
- `src/phase2_cleaning_eda.py`

## Recommendation For Phase 3

After review approval, Phase 3 should build baseline forecasting only. Use the gross daily demand panel at `Product_ID x Location_ID`, keep time-based validation, and define fallback behavior for sparse or high-variability series before comparing stronger models in later phases.

Stop here for approval before Phase 3.
