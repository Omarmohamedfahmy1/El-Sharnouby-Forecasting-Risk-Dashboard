# El-Sharnouby Forecasting and Risk Decision Project

## Project Objective

This project builds an end-to-end planning view for El-Sharnouby Group using only the provided datasets and accepted phase outputs. It connects historical sales demand, finished-goods inventory, validated forecasts, replenishment planning, gross material requirements, historical procurement risk, historical production risk, and a final decision layer.

The project is a management-support artifact. It does not create purchase orders, confirm production schedules, calculate raw-material shortages, or replace human operational review.

## Business Scope

- Forecasting grain: `Product_ID x Location_ID`.
- Active demand and inventory locations: `LOC001`, `LOC002`, and `LOC003`.
- Forecast horizons: 30, 60, and 90 days from the accepted forecast origin.
- Demand target: gross outbound demand from `Sales_Transactions.Quantity`.
- Finished-goods replenishment is a planning quantity.
- Material requirements are gross requirements if replenishment is produced.
- Procurement and production risks are historical relative evidence from the provided records.

No external data, APIs, or fabricated business facts are used.

## Folder Structure

```text
app/                 Streamlit dashboard source files
data/processed/      Accepted processed Phase 2 data panels
notebooks/           Final executed analytical notebook
outputs/phase1/      Data audit outputs
outputs/phase2/      Cleaning, EDA, demand panel, reconciliation outputs
outputs/phase3/      Forecasting baseline outputs
outputs/phase4/      Forecasting model comparison outputs
outputs/phase4_1/    Selection robustness outputs
outputs/phase5/      Final forecast and finished-goods inventory risk outputs
outputs/phase5_1/    Fair policy validation outputs
outputs/phase6/      BOM and gross material requirements outputs
outputs/phase7/      Historical procurement risk outputs
outputs/phase8/      Historical production risk outputs
outputs/phase9/      Final decision layer outputs
outputs/phase10/     Dashboard validation outputs
outputs/phase11/     Final notebook validation outputs
outputs/phase12/     Final delivery validation outputs
src/                 Phase scripts and validation scripts
requirements.txt     Runtime dependencies for dashboard, notebook, and validation
```

## Install Requirements

From the project root:

```powershell
python -m pip install -r requirements.txt
```

The project was prepared on Python 3.12. A virtual environment is recommended for review.

## Run the Streamlit Dashboard

From the project root:

```powershell
streamlit run app/streamlit_app.py
```

The dashboard reads accepted project outputs only. It does not rerun phase scripts, retrain forecasting models, regenerate forecasts, or calculate new replenishment, procurement, or production decisions.

## Review the Final Notebook

Open:

```text
notebooks/el_sharnouby_end_to_end_analysis.ipynb
```

The notebook is saved with stable cell IDs, execution counts, tables, and chart outputs. It is the final analytical narrative, not a replacement implementation.

## Key Outputs

- Final notebook: `notebooks/el_sharnouby_end_to_end_analysis.ipynb`
- Streamlit app: `app/streamlit_app.py`
- Phase 10 dashboard validation: `outputs/phase10/dashboard_validation_checks.csv`
- Phase 11 notebook validation: `outputs/phase11/phase11_notebook_validation_checks.csv`
- Final decision table: `outputs/phase9/final_decision_recommendations.csv`
- 90-day management priority: `outputs/phase9/management_priority_90d.csv`
- Final forecast: `outputs/phase5/forecast_results.csv`
- Finished-goods stockout analysis: `outputs/phase5/stockout_analysis.csv`
- Gross material requirements: `outputs/phase6/material_requirements_summary.csv`

## Known Limitations

- No raw-material inventory table is available.
- Current raw-material shortages cannot be calculated.
- Material requirements are gross requirements if replenishment is produced, not purchase quantities.
- No future supplier availability, open purchase orders, confirmed production schedule, or factory-capacity forecast is inferred.
- Historical procurement and production risks are relative evidence, not future probability guarantees.
- Conditional material and production dates are planning estimates, not contractual deadlines.
- Phase 2 documented inventory accounting mismatches; accepted data was not altered to force accounting identities to hold.

## Final Validation

Run the Phase 12 packaging validation from the project root:

```powershell
python src/phase12_final_validation.py
```

The validation writes:

- `outputs/phase12/phase12_final_validation_checks.csv`
- `outputs/phase12/phase12_final_delivery_report.md`
- `outputs/phase12/delivery_manifest.csv`
