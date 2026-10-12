# Hardcoded Path Cleanup Note

Phase 7 uses `--data-dir`, `--phase6-dir`, `--output-dir`, and project-relative defaults via `pathlib`.
Older scripts were not rewritten in this phase, and existing outputs were not silently regenerated.

Older scripts still containing machine-specific dataset paths:

- `src\phase1_audit.py`
- `src\phase2_cleaning_eda.py`
- `src\phase5_forecast_inventory.py`
- `src\phase6_bom_material_requirements.py`

Recommended later cleanup: update those scripts to follow the Phase 7 argument-based pattern, then rerun their own validation checks only when that cleanup phase is approved.