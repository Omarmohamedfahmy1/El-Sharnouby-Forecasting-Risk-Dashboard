# Phase 10 Dashboard Run Note

Working directory:

```powershell
C:\Users\Acer\Documents\ChatGPT\El Sharnoby
```

Run command:

```powershell
streamlit run app/streamlit_app.py
```

The dashboard reads accepted Phase 1-9 outputs only. It does not rerun earlier scripts, retrain forecasts, create new 30/60/90 forecasts, calculate new procurement or production recommendations, or infer raw-material inventory.

Main sections:

- Executive Overview
- Demand Forecast
- Inventory & Stockout Risk
- Material Requirements
- Procurement Risk
- Production Risk
- Final Decision Center
- Model Performance
- Methodology & Limitations

Global filters are in the sidebar: forecast horizon, location, channel, product, product family, decision risk, and inventory risk. Each filter has an All option.
