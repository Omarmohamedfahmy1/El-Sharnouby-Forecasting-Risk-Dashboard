# Phase 1 Data Audit Report

Generated: 2026-10-07 17:32:01

Data directory: `C:\Users\Acer\Downloads\Sharnouby_Enterprise`

## Scope Boundary

This is Phase 1 only: data audit and project understanding. No forecasting model, Streamlit dashboard, replenishment output, or final risk score was built.

Important inventory boundary: `Inventory_History.csv` is finished-goods inventory at month x location x product grain. The provided files do not contain a current raw-material inventory table. Later phases can calculate material quantities required from the BOM and procurement risk from historical purchase orders, but they must not claim current raw-material stock.

## Files Inspected

- CSV files found and read: 20
- PDF present: yes
- Data dictionary listed file missing from folder: Sources.csv

## Dataset Summary

| Dataset | Rows | Columns | Full duplicate rows |
|---|---:|---:|---:|
| Business_Units.csv | 5 | 5 | 0 |
| Case_Briefs.csv | 10 | 4 | 0 |
| Customer_Service.csv | 6,500 | 9 | 0 |
| Customers.csv | 30,000 | 9 | 0 |
| Data_Dictionary.csv | 19 | 4 | 0 |
| Group_Operations.csv | 180 | 7 | 0 |
| Inventory_History.csv | 6,372 | 19 | 0 |
| Locations.csv | 5 | 9 | 0 |
| Machine_Downtime.csv | 2,800 | 8 | 0 |
| Marketing.csv | 420 | 15 | 0 |
| Materials.csv | 12 | 6 | 0 |
| Printing_Batches.csv | 1,900 | 15 | 0 |
| Product_BOM.csv | 337 | 7 | 0 |
| Product_Master.csv | 59 | 12 | 0 |
| Production_Orders.csv | 2,500 | 16 | 0 |
| Purchase_Orders.csv | 3,600 | 13 | 0 |
| Quality.csv | 9,000 | 12 | 0 |
| Sales_Transactions.csv | 180,000 | 30 | 0 |
| Suppliers.csv | 12 | 7 | 0 |
| Web_Traffic_Daily.csv | 1,096 | 11 | 0 |

## Primary Keys And Duplicate-Key Checks

Candidate keys were checked from the declared grain and observed columns. No duplicate rows found for the Phase 1 candidate primary/composite keys.

Full details are exported to `key_checks.csv`.

## Date Ranges

- Sales order history: 2023-10-01 to 2026-09-30 (180,000 valid)
- Inventory snapshots: 2023-10-01 to 2026-09-01 (6,372 valid)
- Purchase order dates: 2023-10-01 to 2026-09-15 (3,600 valid)
- Purchase receipt dates: 2023-10-08 to 2026-09-30 (3,600 valid)
- Production start dates: 2023-10-01 to 2026-09-10 (2,500 valid)
- Production completion dates: 2023-10-09 to 2026-09-30 (2,500 valid)

## Missing Values

High-level missingness notes:

- Sales_Transactions.csv: Return_Date: 171,457 (95.254%)
- Inventory_History.csv: No missing values detected.
- Product_BOM.csv: No missing values detected.
- Materials.csv: No missing values detected.
- Purchase_Orders.csv: No missing values detected.
- Production_Orders.csv: Primary_Bottleneck: 2,093 (83.72%)

Full missing-value detail is exported to `missing_values.csv`.

## Product And Location Consistency

No missing Product_ID, Location_ID, Material_ID, Supplier_ID, or Customer_ID references detected in the audited tables.

- Products in Product_Master.csv: 59
- Locations in Locations.csv: 5
- Product x Location combinations theoretically possible from master data: 295
- Product x Location combinations observed in sales: 177
- Product x Location combinations observed in inventory history: 177
- Sales Product x Location pairs missing inventory history: 0
- Inventory Product x Location pairs without sales rows: 0
- Locations represented in sales and inventory: LOC001, LOC002, LOC003
- Master locations without sales rows: LOC004, LOC005
- Master locations without inventory rows: LOC004, LOC005

## Sales History, Frequency, And Sparsity

- Sales rows: 180,000
- Distinct invoices: 180,000
- Distinct products sold: 59
- Distinct locations sold: 3
- Distinct Product x Location sales pairs: 177
- Quantity sold total: 1,660,589
- Sales frequency classes by active selling-day ratio: dense: 46, moderate: 127, sparse: 4

The sales data is not equally dense for every Product x Location pair. Phase 2 should keep the Product_ID x Location_ID grain, but profile sparse or intermittent pairs before choosing fallback rules for modeling.

## Inventory History

- Inventory rows: 6,372
- Inventory Product x Location pairs: 177
- Inventory snapshot range: 2023-10-01 to 2026-09-01 (6,372 valid)
- Latest inventory snapshot across pairs ranges from 2026-09-01 to 2026-09-01.
- Finished-goods fields available for later shortage logic: `Closing_Stock`, `Safety_Stock_Units`, `Reorder_Point_Units`, `Days_of_Cover`, `Stockout_Days_In_Month`.

This table is not raw-material inventory. It should be used only as Product x Location finished-goods stock evidence.

## BOM And Material Coverage

- BOM product count: 59
- Products in Product_Master.csv missing from BOM: 0
- BOM products missing from Product_Master.csv: 0
- BOM materials count: 10
- BOM materials missing from Materials.csv: 0
- Materials in Materials.csv without BOM usage: 2

Material requirements can be calculated later as recommended production quantity x `Required_Per_Unit`, preserving the BOM unit. No current material stock can be calculated from the provided tables.

## Purchase-Order History

- Purchase-order rows: 3,600
- Materials with purchase history: 12
- Suppliers with purchase history: 12
- Median actual lead time: 10.0 days
- 90th percentile actual lead time: 21.0 days
- Median receipt delay vs promised date: 0.0 days
- 90th percentile receipt delay vs promised date: 3.0 days

Purchase orders support historical procurement risk, not current supplier availability or current raw-material stock.

## Production-Order History

- Production-order rows: 2,500
- Products with production history: 59
- Sales products without production history: 0
- Median actual production duration: 16.0 days
- Median delay: 0.0 days
- 90th percentile delay: 4.0 days
- Mean efficiency: 82.2%

Production orders support historical production-risk indicators. They do not prove exact future capacity.

## Necessary Datasets For This Project

Required for the shortage-risk decision app:

- `Sales_Transactions.csv`
- `Inventory_History.csv`
- `Product_Master.csv`
- `Locations.csv`
- `Product_BOM.csv`
- `Materials.csv`
- `Purchase_Orders.csv`
- `Suppliers.csv`
- `Production_Orders.csv`
- `Data_Dictionary.csv`

Optional later, if they improve defensible analysis: `Marketing.csv`, `Web_Traffic_Daily.csv`, `Quality.csv`, `Printing_Batches.csv`, `Machine_Downtime.csv`.

Not required for the core Product x Location shortage question: `Customers.csv`, `Customer_Service.csv`, `Business_Units.csv`, `Group_Operations.csv`, `Case_Briefs.csv`.

## Proposed Relationship Map

- `Product_Master.Product_ID` -> `Sales_Transactions.Product_ID`, `Inventory_History.Product_ID`, `Product_BOM.Product_ID`, `Production_Orders.Product_ID`, plus optional production/quality/marketing tables.
- `Locations.Location_ID` -> `Sales_Transactions.Location_ID`, `Inventory_History.Location_ID`.
- `Product_BOM.Product_ID` + `Product_BOM.Material_ID` links finished goods to material requirements.
- `Materials.Material_ID` -> `Product_BOM.Material_ID`, `Purchase_Orders.Material_ID`.
- `Suppliers.Supplier_ID` -> `Purchase_Orders.Supplier_ID`.
- `Sales_Transactions.Customer_ID` -> `Customers.Customer_ID`, but customer analysis is outside the core Phase 1 shortage scope.

## Proposed Modeling Grain

The defensible modeling grain remains `Product_ID x Location_ID`, because both demand and finished-goods inventory share that grain. Phase 2 should create daily demand series per pair, audit returns treatment, inspect zero-demand days, and define explicit fallback rules for pairs with sparse/intermittent demand before any model is trained.

## Limitations And Blockers Before Modeling

- No raw-material current inventory table is present. Do not calculate or display current material stock.
- `Data_Dictionary.csv` references `Sources.csv`, but that file is not present in the folder.
- Product x Location demand is unevenly dense; some pairs may require fallback forecasting rules.
- Inventory is monthly while sales is daily, so Phase 2 must define how latest monthly finished-goods stock is aligned with daily forecasts.
- Later action-date logic must rely on available lead-time evidence and should be labeled as planning guidance, not exact capacity scheduling.

## Phase 2 Recommendation

Proceed with data cleaning and EDA only after approval. Recommended Phase 2 tasks:

- Normalize date types and key columns.
- Decide whether returns reduce demand or are analyzed separately.
- Build daily Product x Location demand tables with explicit zero-demand handling.
- Align latest finished-goods inventory to Product x Location demand.
- Profile sparse/intermittent pairs and document fallback rules.
- Keep raw-material inventory out of scope unless a provided table explicitly supplies it.

## Files Created By Phase 1

- `C:\Users\Acer\Documents\ChatGPT\El Sharnoby\outputs\phase1\phase1_data_audit_report.md`
- `C:\Users\Acer\Documents\ChatGPT\El Sharnoby\outputs\phase1\table_summary.csv`
- `C:\Users\Acer\Documents\ChatGPT\El Sharnoby\outputs\phase1\missing_values.csv`
- `C:\Users\Acer\Documents\ChatGPT\El Sharnoby\outputs\phase1\date_ranges.csv`
- `C:\Users\Acer\Documents\ChatGPT\El Sharnoby\outputs\phase1\key_checks.csv`
- `C:\Users\Acer\Documents\ChatGPT\El Sharnoby\outputs\phase1\relationship_integrity.csv`
- `C:\Users\Acer\Documents\ChatGPT\El Sharnoby\outputs\phase1\dataset_relevance.csv`
- `C:\Users\Acer\Documents\ChatGPT\El Sharnoby\outputs\phase1\sales_pair_sparsity.csv`
- `C:\Users\Acer\Documents\ChatGPT\El Sharnoby\outputs\phase1\inventory_latest_by_product_location.csv`
- `C:\Users\Acer\Documents\ChatGPT\El Sharnoby\outputs\phase1\procurement_history_by_material.csv`
- `C:\Users\Acer\Documents\ChatGPT\El Sharnoby\outputs\phase1\production_history_by_product.csv`
- `C:\Users\Acer\Documents\ChatGPT\El Sharnoby\outputs\phase1\dictionary_file_status.csv`
- `src/phase1_audit.py`
