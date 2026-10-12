# Phase 10 Streamlit Dashboard Report

## 1. Pages built

Built nine dashboard sections: Executive Overview, Demand Forecast, Inventory & Stockout Risk, Material Requirements, Procurement Risk, Production Risk, Final Decision Center, Model Performance, and Methodology & Limitations.

## 2. Prior outputs used by page

- Executive Overview: outputs/phase9/final_decision_recommendations.csv, management_kpis_90d.csv, management_priority_90d.csv
- Demand Forecast: outputs/phase5/forecast_results.csv, data/processed/daily_product_location_demand_panel.csv, outputs/phase2/demand_series_eda.csv
- Inventory & Stockout Risk: outputs/phase5/stockout_analysis.csv, outputs/phase9/conditional_action_timing.csv
- Material Requirements: outputs/phase6/product_material_requirements.csv, material_requirements_summary.csv
- Procurement Risk: outputs/phase7/material_requirement_procurement_risk.csv, supplier history outputs, outputs/phase9/product_procurement_risk_summary.csv
- Production Risk: outputs/phase8/product_replenishment_production_risk.csv, line and bottleneck history outputs
- Final Decision Center: outputs/phase9/final_decision_recommendations.csv, decision_risk_traceability.csv, conditional_action_timing.csv
- Model Performance: outputs/phase3, phase4, phase4_1, and phase5_1 validation metric outputs
- Methodology & Limitations: outputs/phase2 validation and leakage outputs plus dashboard manifest

## 3. Filters implemented

Global sidebar filters: Forecast Horizon 30/60/90/All, Location, Channel, Product, Product Family, Decision Risk, and Inventory Risk. Product/location tables preserve the Product_ID x Location_ID grain where applicable.

## 4. KPIs shown

KPIs include filtered decision row counts, Product x Location pairs, high-risk counts, forecast demand, available stock, expected shortage, Recommended Finished-Goods Replenishment, material rows, supplier history counts, production lead-time summaries, and accepted validation WAPE values.

## 5. Decision_Risk explanation

The dashboard displays accepted Phase 9 Decision_Risk labels and deterministic Decision_Risk_Reason text. For 90 days the accepted distribution is {'Low': 92, 'High': 85}.

## 6. Systemic/common-material procurement risk communication

Procurement Risk contains a warning that all 177 accepted 90-day product-location rows have Product_Historical_Procurement_Risk=High and Sewing Thread as the highest-risk material. Material-level risk tables and drivers are shown so the common High label is not hidden.

## 7. Conditional date labels

Conditional Production Start By and Conditional Material Action By are labeled as historical lead-time planning estimates. They are not presented as production schedules, purchase-order deadlines, or supplier commitments.

## 8. Limitations exposed

Methodology & Limitations includes data scope, Product_ID x Location_ID grain, 30/60/90 horizons, no raw-material inventory assumption, historical-only procurement/production evidence, conditional-date caveats, replenishment meaning, gross material requirement meaning, and Phase 2 inventory accounting mismatch context. Phase 2 exact accounting hold rate shown in source output: 97.693%.

## 9. Missing file handling

The data loader validates required accepted files and columns. If a required input is missing or malformed, the app stops with a specific file/column message instead of fabricating values.

## 10. Downloads

Download buttons are available for filtered final decisions, inventory/stockout rows, and gross material requirements if produced.

## 11. Packages added

requirements.txt was created with streamlit, pandas, numpy, and plotly only.

## 12. Validation and smoke checks

Validation checks passed: 65/65. See outputs/phase10/dashboard_validation_checks.csv for row-level results.

## 13. Exact files created or modified

- app/streamlit_app.py
- app/data_loader.py
- app/components.py
- app/charts.py
- app/RUN_DASHBOARD.md
- src/phase10_dashboard_validation.py
- outputs/phase10/phase10_dashboard_report.md
- outputs/phase10/dashboard_validation_checks.csv
- outputs/phase10/dashboard_data_manifest.csv
- requirements.txt

## Recommendation for review

Review the Streamlit navigation, labels, and filtering behavior before approving any final documentation or packaging phase.
