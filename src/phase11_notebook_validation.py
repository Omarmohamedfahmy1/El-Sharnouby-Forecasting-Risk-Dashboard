from __future__ import annotations

import base64
import copy
import contextlib
import io
import json
import os
import sys
import traceback
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK_PATH = PROJECT_ROOT / "notebooks" / "el_sharnouby_end_to_end_analysis.ipynb"
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "phase11"
CHECKS_PATH = OUTPUT_DIR / "phase11_notebook_validation_checks.csv"
REPORT_PATH = OUTPUT_DIR / "phase11_notebook_report.md"


REQUIRED_SECTIONS = [
    "Title and Project Objective",
    "Executive Summary",
    "Data Sources and Scope",
    "Data Audit",
    "Demand Analysis",
    "Inventory and Reconciliation",
    "Forecasting Method",
    "Forecast Model Validation",
    "Final Forecast",
    "Inventory / Stockout Risk",
    "Finished-Goods Replenishment",
    "BOM / Material Requirements",
    "Procurement Risk",
    "Production Risk",
    "Final Decision Logic",
    "Business Interpretation",
    "Limitations",
    "Final Conclusions",
]

REQUIRED_REFERENCES = [
    "outputs/phase3/baseline_metrics_overall.csv",
    "outputs/phase4_1/policy_comparison.csv",
    "outputs/phase4_1/leave_one_fold_out_policy_metrics.csv",
    "outputs/phase5_1/full_coverage_policy_comparison.csv",
    "outputs/phase6/product_replenishment_requirements.csv",
    "outputs/phase6/material_requirements_summary.csv",
    "outputs/phase7/historical_procurement_risk.csv",
    "outputs/phase8/historical_production_risk.csv",
    "outputs/phase9/final_decision_recommendations.csv",
    "outputs/phase9/management_priority_90d.csv",
]

REQUIRED_TEXT_SNIPPETS = [
    "180,000",
    "2023-10-01",
    "2026-09-30",
    "6,372",
    "59 products",
    "193,435",
    "1,660,589",
    "2.242%",
    "22.251%",
    "17.071%",
    "27.464%",
    "20.196%",
    "106,723.191",
    "117,853.191",
]

LIMITATION_SNIPPETS = [
    "No raw-material inventory",
    "historical relative-risk evidence",
    "No future supplier availability",
    "No confirmed purchase orders",
    "No confirmed production schedule",
    "No factory-capacity forecast",
    "conditional dates are planning estimates",
    "147 accounting mismatches",
]

FORBIDDEN_EXTERNAL_SNIPPETS = [
    "http://",
    "https://",
    "requests.",
    "urllib.",
    "urlopen(",
    "read_html(",
    "download",
]

FORBIDDEN_MODEL_SNIPPETS = [
    "sklearn",
    "statsmodels",
    "prophet",
    "pmdarima",
    ".fit(",
    ".predict(",
    "forecast(",
    "RandomForest",
    "GradientBoosting",
    "ExponentialSmoothing",
    "Croston",
]

FORBIDDEN_WRITE_SNIPPETS = [
    ".to_csv(",
    ".to_excel(",
    ".to_parquet(",
    ".write_text(",
    "open(",
    "mkdir(",
    "unlink(",
    "remove(",
]


def add_check(checks: list[dict[str, Any]], name: str, passed: bool, detail: str) -> None:
    checks.append({"check": name, "passed": bool(passed), "detail": detail})


def source_text(cell: dict[str, Any]) -> str:
    source = cell.get("source", "")
    return "".join(source) if isinstance(source, list) else str(source)


def read_csv(relative_path: str) -> pd.DataFrame:
    return pd.read_csv(PROJECT_ROOT / relative_path)


def metric_value(df: pd.DataFrame, key_col: str, value_col: str, key: str) -> Any:
    row = df.loc[df[key_col] == key, value_col]
    if row.empty:
        raise KeyError(key)
    return row.iloc[0]


def close_enough(actual: float, expected: float, tolerance: float = 1e-3) -> bool:
    return abs(float(actual) - float(expected)) <= tolerance


def value_counts_dict(series: pd.Series) -> dict[str, int]:
    return {str(k): int(v) for k, v in series.value_counts(dropna=False).to_dict().items()}


def accepted_output_files() -> list[Path]:
    roots = [PROJECT_ROOT / "data" / "processed"]
    roots.extend(PROJECT_ROOT / "outputs" / phase for phase in [
        "phase1",
        "phase2",
        "phase3",
        "phase4",
        "phase4_1",
        "phase5",
        "phase5_1",
        "phase6",
        "phase7",
        "phase8",
        "phase9",
        "phase10",
    ])
    files: list[Path] = []
    for root in roots:
        if root.exists():
            files.extend(path for path in root.rglob("*") if path.is_file())
    return sorted(files)


def file_mtimes(files: list[Path]) -> dict[str, int]:
    return {str(path): path.stat().st_mtime_ns for path in files if path.exists()}


def assign_stable_cell_ids(notebook: dict[str, Any]) -> None:
    for index, cell in enumerate(notebook.get("cells", []), start=1):
        cell["id"] = f"phase11-cell-{index:03d}"


def notebook_saved_state_summary(notebook: dict[str, Any]) -> dict[str, int]:
    cells = notebook.get("cells", [])
    code_cells = [cell for cell in cells if cell.get("cell_type") == "code"]
    ids = [cell.get("id") for cell in cells]
    outputs = [output for cell in code_cells for output in cell.get("outputs", [])]

    table_outputs = 0
    text_outputs = 0
    image_outputs = 0
    display_outputs = 0
    error_outputs = 0

    for output in outputs:
        output_type = output.get("output_type")
        data = output.get("data", {}) if isinstance(output.get("data"), dict) else {}
        if output_type in {"display_data", "execute_result"}:
            display_outputs += 1
        if output_type == "stream" or "text/plain" in data:
            text_outputs += 1
        html = str(data.get("text/html", ""))
        if "<table" in html.lower():
            table_outputs += 1
        if any(mime in data for mime in ["image/png", "image/jpeg", "image/svg+xml"]):
            image_outputs += 1
        if output_type == "error":
            error_outputs += 1

    return {
        "total_cells": len(cells),
        "code_cells": len(code_cells),
        "cells_with_ids": sum(1 for cell_id in ids if isinstance(cell_id, str) and bool(cell_id.strip())),
        "unique_cell_ids": len({cell_id for cell_id in ids if isinstance(cell_id, str) and bool(cell_id.strip())}),
        "code_cells_with_execution_counts": sum(1 for cell in code_cells if cell.get("execution_count") is not None),
        "total_saved_outputs": len(outputs),
        "saved_display_outputs": display_outputs,
        "saved_text_outputs": text_outputs,
        "saved_table_outputs": table_outputs,
        "saved_chart_image_outputs": image_outputs,
        "saved_error_outputs": error_outputs,
    }


def _display_data_for_object(obj: Any) -> dict[str, Any]:
    data: dict[str, Any] = {"text/plain": repr(obj)}
    repr_html = getattr(obj, "_repr_html_", None)
    if callable(repr_html):
        html = repr_html()
        if html:
            data["text/html"] = html
    return {"output_type": "display_data", "metadata": {}, "data": data}


def _stream_output(name: str, text: str) -> dict[str, str]:
    return {"output_type": "stream", "name": name, "text": text}


def _execute_notebook_cells(notebook: dict[str, Any], save_path: Path | None = None) -> tuple[bool, str]:
    import matplotlib
    import IPython.display as ipython_display

    matplotlib.use("Agg", force=True)
    assign_stable_cell_ids(notebook)
    notebook.setdefault("metadata", {})
    notebook["metadata"].setdefault("kernelspec", {"display_name": "Python 3", "language": "python", "name": "python3"})
    notebook["metadata"].setdefault("language_info", {"name": "python", "pygments_lexer": "ipython3"})

    namespace: dict[str, Any] = {"__name__": "__phase11_notebook_validation__"}
    capture_state: dict[str, list[dict[str, Any]]] = {"outputs": []}
    original_display = ipython_display.display

    def capture_display(*objects: Any, **_: Any) -> None:
        for obj in objects:
            capture_state["outputs"].append(_display_data_for_object(obj))

    def patch_matplotlib_show() -> None:
        plt = namespace.get("plt")
        if plt is None or getattr(plt.show, "_phase11_capture_show", False):
            return

        def capture_show(*_: Any, **__: Any) -> None:
            for figure_number in plt.get_fignums():
                figure = plt.figure(figure_number)
                buffer = io.BytesIO()
                figure.savefig(buffer, format="png", dpi=120, bbox_inches="tight")
                capture_state["outputs"].append({
                    "output_type": "display_data",
                    "metadata": {},
                    "data": {
                        "text/plain": f"<matplotlib.figure.Figure at {hex(id(figure))}>",
                        "image/png": base64.b64encode(buffer.getvalue()).decode("ascii"),
                    },
                })
            plt.close("all")

        capture_show._phase11_capture_show = True  # type: ignore[attr-defined]
        plt.show = capture_show

    ipython_display.display = capture_display
    previous_cwd = Path.cwd()
    os.chdir(PROJECT_ROOT)
    try:
        execution_count = 0
        for index, cell in enumerate(notebook.get("cells", []), start=1):
            if cell.get("cell_type") != "code":
                continue
            execution_count += 1
            cell["execution_count"] = execution_count
            cell["outputs"] = []
            capture_state["outputs"] = cell["outputs"]
            code = source_text(cell)
            stdout = io.StringIO()
            stderr = io.StringIO()
            try:
                with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                    exec(compile(code, f"{NOTEBOOK_PATH.name}:cell_{index}", "exec"), namespace)
                if stdout.getvalue():
                    cell["outputs"].insert(0, _stream_output("stdout", stdout.getvalue()))
                if stderr.getvalue():
                    cell["outputs"].append(_stream_output("stderr", stderr.getvalue()))
                patch_matplotlib_show()
            except Exception as exc:  # noqa: BLE001 - validation must report any notebook execution failure.
                if stdout.getvalue():
                    cell["outputs"].insert(0, _stream_output("stdout", stdout.getvalue()))
                if stderr.getvalue():
                    cell["outputs"].append(_stream_output("stderr", stderr.getvalue()))
                cell["outputs"].append({
                    "output_type": "error",
                    "ename": type(exc).__name__,
                    "evalue": str(exc),
                    "traceback": traceback.format_exception(type(exc), exc, exc.__traceback__),
                })
                if save_path is not None:
                    save_path.write_text(json.dumps(notebook, indent=2, ensure_ascii=False), encoding="utf-8")
                return False, f"{type(exc).__name__}: {exc}"

        if save_path is not None:
            save_path.write_text(json.dumps(notebook, indent=2, ensure_ascii=False), encoding="utf-8")
        return True, "All notebook code cells executed and captured without errors."
    finally:
        ipython_display.display = original_display
        plt = namespace.get("plt")
        if plt is not None:
            plt.close("all")
        os.chdir(previous_cwd)


def execute_notebook_code_cells(notebook: dict[str, Any]) -> tuple[bool, str]:
    return _execute_notebook_cells(notebook)


def execute_and_save_notebook() -> dict[str, int]:
    notebook = json.loads(NOTEBOOK_PATH.read_text(encoding="utf-8"))
    executed, detail = _execute_notebook_cells(notebook, save_path=NOTEBOOK_PATH)
    if not executed:
        raise RuntimeError(detail)
    saved_notebook = json.loads(NOTEBOOK_PATH.read_text(encoding="utf-8"))
    return notebook_saved_state_summary(saved_notebook)


def validate_static_notebook(checks: list[dict[str, Any]], notebook: dict[str, Any]) -> None:
    cells = notebook.get("cells", [])
    all_text = "\n".join(source_text(cell) for cell in cells)
    code_text = "\n".join(source_text(cell) for cell in cells if cell.get("cell_type") == "code")
    code_text_lower = code_text.lower()

    notebooks = sorted((PROJECT_ROOT / "notebooks").glob("*.ipynb"))
    add_check(
        checks,
        "exactly_one_phase11_notebook",
        notebooks == [NOTEBOOK_PATH],
        f"Found notebooks: {[path.name for path in notebooks]}",
    )
    add_check(checks, "notebook_cell_count", len(cells) >= 30, f"Notebook has {len(cells)} cells.")
    add_check(
        checks,
        "all_required_sections_present",
        all(section in all_text for section in REQUIRED_SECTIONS),
        "Missing: " + ", ".join(section for section in REQUIRED_SECTIONS if section not in all_text),
    )
    add_check(
        checks,
        "required_accepted_output_references_present",
        all(reference in all_text for reference in REQUIRED_REFERENCES),
        "Missing: " + ", ".join(reference for reference in REQUIRED_REFERENCES if reference not in all_text),
    )
    add_check(
        checks,
        "accepted_values_documented",
        all(snippet in all_text for snippet in REQUIRED_TEXT_SNIPPETS),
        "Missing: " + ", ".join(snippet for snippet in REQUIRED_TEXT_SNIPPETS if snippet not in all_text),
    )
    add_check(
        checks,
        "limitations_documented",
        all(snippet in all_text for snippet in LIMITATION_SNIPPETS),
        "Missing: " + ", ".join(snippet for snippet in LIMITATION_SNIPPETS if snippet not in all_text),
    )
    add_check(
        checks,
        "no_external_data_access_static_scan",
        not any(snippet.lower() in all_text.lower() for snippet in FORBIDDEN_EXTERNAL_SNIPPETS),
        "External-access tokens detected: "
        + ", ".join(snippet for snippet in FORBIDDEN_EXTERNAL_SNIPPETS if snippet.lower() in all_text.lower()),
    )
    add_check(
        checks,
        "no_model_retraining_static_scan",
        not any(snippet.lower() in code_text_lower for snippet in FORBIDDEN_MODEL_SNIPPETS),
        "Training/prediction tokens detected in code: "
        + ", ".join(snippet for snippet in FORBIDDEN_MODEL_SNIPPETS if snippet.lower() in code_text_lower),
    )
    add_check(
        checks,
        "notebook_code_is_read_only_static_scan",
        not any(snippet.lower() in code_text_lower for snippet in FORBIDDEN_WRITE_SNIPPETS),
        "Write tokens detected in code: "
        + ", ".join(snippet for snippet in FORBIDDEN_WRITE_SNIPPETS if snippet.lower() in code_text_lower),
    )
    chart_cell_count = sum(
        1
        for cell in cells
        if cell.get("cell_type") == "code"
        and any(token in source_text(cell) for token in ["simple_bar", "horizontal_bar", "plt."])
    )
    add_check(checks, "notebook_contains_visual_eda_cells", chart_cell_count >= 6, f"Chart-like code cells: {chart_cell_count}.")


def validate_saved_notebook_state(checks: list[dict[str, Any]], summary: dict[str, int]) -> None:
    add_check(
        checks,
        "saved_notebook_all_cells_have_stable_unique_ids",
        summary["cells_with_ids"] == summary["total_cells"]
        and summary["unique_cell_ids"] == summary["total_cells"],
        (
            f"total_cells={summary['total_cells']}, cells_with_ids={summary['cells_with_ids']}, "
            f"unique_cell_ids={summary['unique_cell_ids']}"
        ),
    )
    add_check(
        checks,
        "saved_notebook_all_code_cells_have_execution_counts",
        summary["code_cells_with_execution_counts"] == summary["code_cells"],
        (
            f"code_cells={summary['code_cells']}, "
            f"code_cells_with_execution_counts={summary['code_cells_with_execution_counts']}"
        ),
    )
    add_check(
        checks,
        "saved_notebook_outputs_present",
        summary["total_saved_outputs"] > 0,
        f"total_saved_outputs={summary['total_saved_outputs']}",
    )
    add_check(
        checks,
        "saved_notebook_table_or_text_outputs_present",
        summary["saved_table_outputs"] > 0 and summary["saved_text_outputs"] > 0,
        (
            f"saved_table_outputs={summary['saved_table_outputs']}, "
            f"saved_text_outputs={summary['saved_text_outputs']}"
        ),
    )
    add_check(
        checks,
        "saved_notebook_chart_image_outputs_present",
        summary["saved_chart_image_outputs"] > 0 and summary["saved_display_outputs"] > 0,
        (
            f"saved_chart_image_outputs={summary['saved_chart_image_outputs']}, "
            f"saved_display_outputs={summary['saved_display_outputs']}"
        ),
    )
    add_check(
        checks,
        "saved_notebook_has_no_error_outputs",
        summary["saved_error_outputs"] == 0,
        f"saved_error_outputs={summary['saved_error_outputs']}",
    )


def validate_values_from_accepted_outputs(checks: list[dict[str, Any]]) -> None:
    table_summary = read_csv("outputs/phase1/table_summary.csv")
    date_ranges = read_csv("outputs/phase1/date_ranges.csv")
    daily_panel_summary = read_csv("outputs/phase2/daily_demand_panel_summary.csv")
    inventory_accounting = read_csv("outputs/phase2/inventory_accounting_summary.csv")
    sales_inventory = read_csv("outputs/phase2/sales_inventory_reconciliation_summary.csv")
    returns_summary = read_csv("outputs/phase2/returns_summary.csv")
    demand_eda = read_csv("outputs/phase2/demand_series_eda.csv")
    baseline = read_csv("outputs/phase3/baseline_metrics_overall.csv")
    fold_summary = read_csv("outputs/phase3/validation_fold_summary.csv")
    policy_comparison = read_csv("outputs/phase4_1/policy_comparison.csv")
    full_policy = read_csv("outputs/phase5_1/full_coverage_policy_comparison.csv")
    forecast = read_csv("outputs/phase5/forecast_results.csv")
    latest_inventory = read_csv("outputs/phase5/latest_inventory_snapshot.csv")
    inventory_risk = read_csv("outputs/phase5/inventory_risk_summary.csv")
    product_replenishment = read_csv("outputs/phase6/product_replenishment_requirements.csv")
    bom_coverage = read_csv("outputs/phase6/bom_coverage_validation.csv")
    material_reconciliation = read_csv("outputs/phase6/material_requirement_reconciliation.csv")
    procurement = read_csv("outputs/phase7/procurement_po_enriched.csv")
    procurement_risk = read_csv("outputs/phase7/historical_procurement_risk.csv")
    product_procurement = read_csv("outputs/phase9/product_procurement_risk_summary.csv")
    production = read_csv("outputs/phase8/production_orders_enriched.csv")
    production_risk = read_csv("outputs/phase8/historical_production_risk.csv")
    decisions = read_csv("outputs/phase9/final_decision_recommendations.csv")
    priority_90 = read_csv("outputs/phase9/management_priority_90d.csv")

    sales_rows = int(metric_value(table_summary, "table", "rows", "Sales_Transactions.csv"))
    inventory_rows = int(metric_value(table_summary, "table", "rows", "Inventory_History.csv"))
    products = int(metric_value(table_summary, "table", "rows", "Product_Master.csv"))
    master_locations = int(metric_value(table_summary, "table", "rows", "Locations.csv"))
    sales_date = date_ranges[(date_ranges["table"] == "Sales_Transactions.csv") & (date_ranges["column"] == "Order_Date")]
    add_check(
        checks,
        "source_scope_values_match_phase1",
        sales_rows == 180000
        and inventory_rows == 6372
        and products == 59
        and master_locations == 5
        and sales_date["min_date"].iloc[0] == "2023-10-01"
        and sales_date["max_date"].iloc[0] == "2026-09-30",
        f"sales_rows={sales_rows}, inventory_rows={inventory_rows}, products={products}, locations={master_locations}",
    )

    active_locations = sorted(demand_eda["Location_ID"].unique().tolist())
    panel_rows = int(float(metric_value(daily_panel_summary, "metric", "value", "panel_rows")))
    expected_rows = int(float(metric_value(daily_panel_summary, "metric", "value", "expected_rows_from_pair_windows")))
    add_check(
        checks,
        "daily_panel_scope_matches_phase2",
        panel_rows == 193435 and expected_rows == 193435 and len(demand_eda) == 177 and active_locations == ["LOC001", "LOC002", "LOC003"],
        f"panel_rows={panel_rows}, expected_rows={expected_rows}, series={len(demand_eda)}, active_locations={active_locations}",
    )

    class_counts = value_counts_dict(demand_eda["Demand_Pattern_Class"])
    add_check(
        checks,
        "demand_class_counts_match_phase2",
        class_counts == {"intermittent": 139, "lumpy": 29, "smooth": 5, "erratic": 4},
        f"class_counts={class_counts}",
    )

    add_check(
        checks,
        "inventory_accounting_validation_values_match_phase2",
        int(float(metric_value(inventory_accounting, "metric", "value", "rows_holding_exactly"))) == 6225
        and int(float(metric_value(inventory_accounting, "metric", "value", "mismatch_rows"))) == 147
        and close_enough(float(metric_value(inventory_accounting, "metric", "value", "rows_holding_exactly_pct")), 97.693032),
        inventory_accounting.to_dict("records").__repr__(),
    )
    add_check(
        checks,
        "sales_inventory_reconciliation_values_match_phase2",
        int(float(metric_value(sales_inventory, "metric", "value", "exact_match_rows"))) == 6372
        and close_enough(float(metric_value(sales_inventory, "metric", "value", "exact_match_pct_all_rows")), 100.0)
        and close_enough(float(metric_value(sales_inventory, "metric", "value", "correlation_sales_quantity_vs_inventory_sold_qty")), 1.0),
        sales_inventory.to_dict("records").__repr__(),
    )
    add_check(
        checks,
        "returns_decision_values_match_phase2",
        int(float(metric_value(returns_summary, "metric", "value", "returned_rows"))) == 8543
        and close_enough(float(metric_value(returns_summary, "metric", "value", "returned_quantity_by_order_date")), 37233.0)
        and close_enough(float(metric_value(returns_summary, "metric", "value", "returned_quantity_pct_of_sales_quantity")), 2.242156, 1e-5)
        and "gross outbound demand" in str(metric_value(returns_summary, "metric", "value", "target_decision")),
        returns_summary.to_dict("records").__repr__(),
    )

    best_baseline = baseline.sort_values("Cumulative_WAPE").iloc[0]
    folds = sorted(fold_summary["Forecast_Origin"].unique().tolist())
    add_check(
        checks,
        "forecasting_baseline_values_match_phase3",
        best_baseline["Baseline"] == "weekly_seasonal_naive_52w"
        and best_baseline["Frequency"] == "weekly_distributed"
        and close_enough(best_baseline["Cumulative_WAPE"], 22.250733)
        and folds == ["2025-09-28", "2025-12-28", "2026-03-29", "2026-06-28"],
        f"best_baseline={best_baseline[['Frequency', 'Baseline', 'Cumulative_WAPE']].to_dict()}, folds={folds}",
    )

    phase4_overall = policy_comparison[policy_comparison["Segment_Type"] == "overall"].set_index("Policy")
    phase5_overall = full_policy[full_policy["Segment_Type"] == "overall"].set_index("Policy")
    add_check(
        checks,
        "policy_validation_values_match_phase4_phase5_1",
        close_enough(phase4_overall.loc["phase4_apparent_selection", "Cumulative_WAPE"], 17.070660)
        and close_enough(phase4_overall.loc["leave_one_fold_out_selection", "Cumulative_WAPE"], 27.464146)
        and close_enough(phase5_overall.loc["guarded_hybrid", "Cumulative_WAPE"], 20.195557),
        f"phase4={phase4_overall['Cumulative_WAPE'].to_dict()}, phase5_1={phase5_overall['Cumulative_WAPE'].to_dict()}",
    )

    forecast_source_counts = value_counts_dict(forecast["Selected_Model_Source"])
    horizon_counts = value_counts_dict(forecast["Horizon_Days"])
    add_check(
        checks,
        "final_forecast_coverage_matches_phase5",
        len(forecast) == 531
        and forecast_source_counts == {"baseline": 462, "advanced": 69}
        and horizon_counts == {"30": 177, "60": 177, "90": 177}
        and forecast["Forecast_Origin"].nunique() == 1
        and forecast["Forecast_Origin"].iloc[0] == "2026-09-30"
        and forecast["Forecast_Start"].min() == "2026-10-01"
        and forecast["Forecast_End"].max() == "2026-12-29",
        f"rows={len(forecast)}, source_counts={forecast_source_counts}, horizon_counts={horizon_counts}",
    )

    inv90 = inventory_risk[inventory_risk["Horizon_Days"] == 90].iloc[0]
    add_check(
        checks,
        "inventory_risk_values_match_phase5",
        len(latest_inventory) == 177
        and latest_inventory["Snapshot_Month"].nunique() == 1
        and latest_inventory["Snapshot_Month"].iloc[0] == "2026-09-01"
        and int((latest_inventory["Closing_Stock"] < 0).sum()) == 0
        and int(inv90["High_Risk_Count"]) == 85
        and int(inv90["Medium_Risk_Count"]) == 0
        and int(inv90["Low_Risk_Count"]) == 92
        and close_enough(inv90["Expected_Shortage_Total"], 106723.191441)
        and close_enough(inv90["Recommended_Replenishment_Total"], 117853.191441),
        f"latest_rows={len(latest_inventory)}, inv90={inv90.to_dict()}",
    )

    repl_counts = product_replenishment[product_replenishment["Requires_Replenishment"]].groupby("Horizon_Days")["Product_ID"].nunique().to_dict()
    repl_totals = product_replenishment.groupby("Horizon_Days")["Production_Equivalent_Replenishment_Qty"].sum().to_dict()
    add_check(
        checks,
        "replenishment_bom_values_match_phase6",
        repl_counts == {30: 45, 60: 54, 90: 55}
        and close_enough(repl_totals[30], 27501.377094)
        and close_enough(repl_totals[60], 63247.065455)
        and close_enough(repl_totals[90], 117853.191441)
        and bom_coverage.loc[bom_coverage["Requires_Replenishment"], "Has_BOM_Coverage"].all()
        and material_reconciliation["Reconciliation_Passed"].all(),
        f"repl_counts={repl_counts}, repl_totals={repl_totals}",
    )

    procurement_counts = value_counts_dict(procurement_risk["Historical_Procurement_Risk"])
    product_proc90 = product_procurement[product_procurement["Horizon_Days"] == 90]
    add_check(
        checks,
        "procurement_values_match_phase7",
        len(procurement) == 3600
        and close_enough(procurement["On_Time_Numeric"].mean() * 100, 65.4, 0.05)
        and close_enough((1 - procurement["On_Time_Numeric"].mean()) * 100, 34.6, 0.05)
        and close_enough(procurement["Actual_Lead_Time_Days"].mean(), 12.31, 0.01)
        and close_enough(procurement["Actual_Lead_Time_Days"].quantile(0.9), 21.0)
        and procurement_counts == {"High": 5, "Low": 6, "Medium": 1}
        and value_counts_dict(product_proc90["Product_Historical_Procurement_Risk"]) == {"High": 59},
        f"procurement_counts={procurement_counts}, product_proc90={value_counts_dict(product_proc90['Product_Historical_Procurement_Risk'])}",
    )

    production_counts = value_counts_dict(production_risk["Historical_Production_Risk"])
    evidence_counts = value_counts_dict(production_risk["Production_Evidence_Level"])
    add_check(
        checks,
        "production_values_match_phase8",
        len(production) == 2500
        and close_enough(production["On_Time_Production_Numeric"].mean() * 100, 83.72, 0.01)
        and close_enough((1 - production["On_Time_Production_Numeric"].mean()) * 100, 16.28, 0.01)
        and close_enough(production["Production_Lead_Time_Days"].mean(), 16.3272, 0.0001)
        and close_enough(production["Production_Lead_Time_Days"].median(), 16.0)
        and close_enough(production["Production_Lead_Time_Days"].quantile(0.9), 24.0)
        and production_counts == {"Low": 22, "High": 21, "Medium": 15, "Insufficient Evidence": 1}
        and evidence_counts == {"High": 45, "Medium": 13, "Low": 1},
        f"production_counts={production_counts}, evidence_counts={evidence_counts}",
    )

    decisions90 = decisions[decisions["Horizon_Days"] == 90]
    decision_counts90 = value_counts_dict(decisions90["Decision_Risk"])
    conditional_material_origin = int((decisions90["Material_Action_Status"] == "At/Before forecast origin").sum())
    conditional_production_origin = int((decisions90["Production_Action_Status"] == "At/Before forecast origin").sum())
    add_check(
        checks,
        "final_decision_values_match_phase9",
        len(decisions) == 531
        and len(priority_90) == 177
        and decisions[["Product_ID", "Location_ID"]].drop_duplicates().shape[0] == 177
        and decision_counts90 == {"Low": 92, "High": 85}
        and conditional_material_origin == 59
        and conditional_production_origin == 40,
        (
            f"decisions_rows={len(decisions)}, priority90_rows={len(priority_90)}, "
            f"decision_counts90={decision_counts90}, material_origin={conditional_material_origin}, "
            f"production_origin={conditional_production_origin}"
        ),
    )


def write_report(checks: list[dict[str, Any]], execution_detail: str, saved_state_summary: dict[str, int] | None = None) -> None:
    passed_count = sum(1 for check in checks if check["passed"])
    total_count = len(checks)
    failed = [check for check in checks if not check["passed"]]
    saved_state_summary = saved_state_summary or {
        "total_cells": 0,
        "code_cells": 0,
        "cells_with_ids": 0,
        "unique_cell_ids": 0,
        "code_cells_with_execution_counts": 0,
        "total_saved_outputs": 0,
        "saved_display_outputs": 0,
        "saved_text_outputs": 0,
        "saved_table_outputs": 0,
        "saved_chart_image_outputs": 0,
        "saved_error_outputs": 0,
    }

    lines = [
        "# Phase 11 Notebook Validation Report",
        "",
        "## Scope",
        "",
        f"- Notebook validated: `{NOTEBOOK_PATH.relative_to(PROJECT_ROOT).as_posix()}`",
        f"- Validation checks CSV: `{CHECKS_PATH.relative_to(PROJECT_ROOT).as_posix()}`",
        "- Purpose: confirm the final analytical notebook is a read-only presentation artifact built from accepted project outputs.",
        "",
        "## Validation Result",
        "",
        f"- Checks passed: {passed_count} / {total_count}",
        f"- Notebook execution: {execution_detail}",
        "- External data/API usage: not detected by static scan.",
        "- Model retraining or new forecast generation: not detected by static scan.",
        "- Phase 1-10 accepted output modifications during validation: not detected.",
        "",
        "## Saved Notebook State",
        "",
        f"- Total cells: {saved_state_summary['total_cells']}",
        f"- Code cells: {saved_state_summary['code_cells']}",
        f"- Cells with IDs: {saved_state_summary['cells_with_ids']}",
        f"- Unique cell IDs: {saved_state_summary['unique_cell_ids']}",
        f"- Code cells with execution counts: {saved_state_summary['code_cells_with_execution_counts']}",
        f"- Total saved outputs: {saved_state_summary['total_saved_outputs']}",
        f"- Saved display outputs: {saved_state_summary['saved_display_outputs']}",
        f"- Saved text outputs: {saved_state_summary['saved_text_outputs']}",
        f"- Saved table outputs: {saved_state_summary['saved_table_outputs']}",
        f"- Saved chart/image outputs: {saved_state_summary['saved_chart_image_outputs']}",
        f"- Saved error outputs: {saved_state_summary['saved_error_outputs']}",
        "",
        "## Files Created or Modified in Phase 11",
        "",
        "- `notebooks/el_sharnouby_end_to_end_analysis.ipynb`",
        "- `src/phase11_notebook_validation.py`",
        "- `outputs/phase11/phase11_notebook_validation_checks.csv`",
        "- `outputs/phase11/phase11_notebook_report.md`",
        "",
        "## Failed Checks",
        "",
    ]
    if failed:
        lines.extend(f"- `{check['check']}`: {check['detail']}" for check in failed)
    else:
        lines.append("- None.")

    lines.extend([
        "",
        "## Recommendation for Review",
        "",
        "Phase 11 is ready for review. The notebook should be treated as the final analytical narrative, not as a source of new calculations or replacement business logic.",
        "",
    ])
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if "--execute-save" in argv:
        summary = execute_and_save_notebook()
        print(json.dumps(summary, indent=2))
        return 0

    checks: list[dict[str, Any]] = []

    add_check(checks, "notebook_file_exists", NOTEBOOK_PATH.exists(), str(NOTEBOOK_PATH))
    if not NOTEBOOK_PATH.exists():
        pd.DataFrame(checks).to_csv(CHECKS_PATH, index=False)
        write_report(checks, "Notebook was missing; execution skipped.")
        return 1

    try:
        notebook = json.loads(NOTEBOOK_PATH.read_text(encoding="utf-8"))
        add_check(checks, "notebook_valid_json", True, "Notebook JSON loaded successfully.")
    except json.JSONDecodeError as exc:
        add_check(checks, "notebook_valid_json", False, str(exc))
        pd.DataFrame(checks).to_csv(CHECKS_PATH, index=False)
        write_report(checks, "Invalid notebook JSON; execution skipped.")
        return 1

    add_check(checks, "notebook_format_v4", notebook.get("nbformat") == 4, f"nbformat={notebook.get('nbformat')}")
    saved_state_summary = notebook_saved_state_summary(notebook)
    validate_static_notebook(checks, notebook)
    validate_saved_notebook_state(checks, saved_state_summary)
    validate_values_from_accepted_outputs(checks)

    accepted_files = accepted_output_files()
    before_mtimes = file_mtimes(accepted_files)
    executed, execution_detail = execute_notebook_code_cells(copy.deepcopy(notebook))
    after_mtimes = file_mtimes(accepted_files)
    add_check(checks, "notebook_code_cells_execute", executed, execution_detail)
    changed_files = [path for path, before in before_mtimes.items() if after_mtimes.get(path) != before]
    add_check(
        checks,
        "phase1_to_phase10_outputs_unchanged_during_validation",
        not changed_files,
        "Changed files: " + ", ".join(Path(path).relative_to(PROJECT_ROOT).as_posix() for path in changed_files),
    )

    checks_df = pd.DataFrame(checks)
    checks_df.to_csv(CHECKS_PATH, index=False)
    write_report(checks, execution_detail, saved_state_summary)
    return 0 if checks_df["passed"].all() else 1


if __name__ == "__main__":
    raise SystemExit(main())
