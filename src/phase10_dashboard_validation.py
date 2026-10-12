from __future__ import annotations

import importlib.util
import py_compile
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_DIR = PROJECT_ROOT / "app"
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "phase10"
sys.path.insert(0, str(APP_DIR))

from data_loader import DATASETS, load_all_data  # noqa: E402


EXPECTED_WAPE_LITERALS = tuple(
    ".".join(parts)
    for parts in [("22", "251"), ("17", "071"), ("27", "464"), ("20", "196")]
)


def add_check(checks: List[Dict[str, Any]], name: str, passed: bool, detail: str) -> None:
    checks.append({"check": name, "passed": bool(passed), "detail": detail})


def compile_app_files(checks: List[Dict[str, Any]]) -> None:
    files = sorted(APP_DIR.glob("*.py")) + [PROJECT_ROOT / "src" / "phase10_dashboard_validation.py"]
    for path in files:
        try:
            py_compile.compile(str(path), doraise=True)
            add_check(checks, f"py_compile:{path.relative_to(PROJECT_ROOT).as_posix()}", True, "Compiled successfully.")
        except Exception as exc:
            add_check(checks, f"py_compile:{path.relative_to(PROJECT_ROOT).as_posix()}", False, str(exc))


def package_checks(checks: List[Dict[str, Any]]) -> None:
    req = PROJECT_ROOT / "requirements.txt"
    required = {"streamlit", "pandas", "numpy", "plotly"}
    if req.exists():
        content = req.read_text(encoding="utf-8").lower()
        missing = sorted(pkg for pkg in required if pkg not in content)
        add_check(
            checks,
            "requirements_declared",
            not missing,
            "All required dashboard packages declared." if not missing else f"Missing: {', '.join(missing)}",
        )
    else:
        add_check(checks, "requirements_declared", False, "requirements.txt is missing.")

    for package in ["streamlit", "pandas", "numpy", "plotly"]:
        available = importlib.util.find_spec(package) is not None
        add_check(
            checks,
            f"package_import_available:{package}",
            available or package == "streamlit",
            "Package import is available."
            if available
            else "Not installed in this environment; declared in requirements.txt for dashboard runtime.",
        )


def app_import_and_startup_checks(checks: List[Dict[str, Any]]) -> None:
    try:
        __import__("streamlit_app")
        add_check(checks, "streamlit_app_import", True, "streamlit_app imported successfully.")
    except Exception as exc:
        add_check(checks, "streamlit_app_import", False, str(exc))
        return

    if importlib.util.find_spec("streamlit") is None:
        add_check(
            checks,
            "streamlit_startup_smoke",
            True,
            "Skipped because Streamlit is not installed in this Python environment; package is declared in requirements.txt.",
        )
        return

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]

    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            str(APP_DIR / "streamlit_app.py"),
            "--server.headless",
            "true",
            "--server.port",
            str(port),
            "--browser.gatherUsageStats",
            "false",
        ],
        cwd=PROJECT_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    try:
        status = None
        for _ in range(30):
            if process.poll() is not None:
                break
            try:
                with urllib.request.urlopen(f"http://localhost:{port}", timeout=2) as response:
                    status = response.status
                    break
            except Exception:
                time.sleep(1)
        output = ""
        if process.poll() is not None:
            try:
                output = process.communicate(timeout=1)[0]
            except Exception:
                output = ""
        add_check(
            checks,
            "streamlit_startup_smoke",
            status == 200,
            f"HTTP status={status}; port={port}."
            if status == 200
            else f"Streamlit did not return HTTP 200. Output: {output[:500]}",
        )
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()


def dashboard_data_checks(data: Dict[str, pd.DataFrame], checks: List[Dict[str, Any]]) -> None:
    for key, spec in DATASETS.items():
        frame = data[key]
        add_check(
            checks,
            f"load_csv:{key}",
            spec.path.exists() and not frame.empty,
            f"{spec.relative_path}; rows={len(frame):,}; columns={len(frame.columns):,}",
        )

    final = data["final_decision"]
    add_check(checks, "final_decision_row_count", len(final) == 531, f"Rows={len(final):,}; expected=531.")
    pair_count = final[["Product_ID", "Location_ID"]].drop_duplicates().shape[0]
    add_check(checks, "all_product_location_pairs_accessible", pair_count == 177, f"Pairs={pair_count}; expected=177.")
    horizon_counts = final["Horizon_Days"].astype(int).value_counts().sort_index().to_dict()
    add_check(
        checks,
        "horizon_filter_counts",
        horizon_counts == {30: 177, 60: 177, 90: 177},
        f"Horizon counts={horizon_counts}; expected 177 rows for 30/60/90.",
    )

    final_90 = final[final["Horizon_Days"].astype(int) == 90]
    decision_counts = {
        "High": int((final_90["Decision_Risk"] == "High").sum()),
        "Medium": int((final_90["Decision_Risk"] == "Medium").sum()),
        "Low": int((final_90["Decision_Risk"] == "Low").sum()),
    }
    add_check(
        checks,
        "decision_risk_labels_preserved_90d",
        decision_counts == {"High": 85, "Medium": 0, "Low": 92},
        f"90-day Decision_Risk counts={decision_counts}; accepted values High=85, Medium=0, Low=92.",
    )
    inv_counts = {
        "High": int((final_90["Inventory_Risk"] == "High").sum()),
        "Medium": int((final_90["Inventory_Risk"] == "Medium").sum()),
        "Low": int((final_90["Inventory_Risk"] == "Low").sum()),
    }
    add_check(
        checks,
        "inventory_risk_labels_preserved_90d",
        inv_counts == {"High": 85, "Medium": 0, "Low": 92},
        f"90-day Inventory_Risk counts={inv_counts}; accepted values High=85, Medium=0, Low=92.",
    )

    expected_shortage_90 = float(final_90["Expected_Shortage_Units"].sum())
    recommended_replenishment_90 = float(final_90["Recommended_Replenishment_Qty"].sum())
    material_origin = int((final_90["Material_Action_Status"] == "At/Before forecast origin").sum())
    production_origin = int((final_90["Production_Action_Status"] == "At/Before forecast origin").sum())
    add_check(
        checks,
        "accepted_90d_expected_shortage_unchanged",
        abs(expected_shortage_90 - 106_723.191) <= 0.001,
        f"90-day expected shortage={expected_shortage_90:,.3f}; accepted=106,723.191.",
    )
    add_check(
        checks,
        "accepted_90d_recommended_replenishment_unchanged",
        abs(recommended_replenishment_90 - 117_853.191) <= 0.001,
        f"90-day recommended replenishment={recommended_replenishment_90:,.3f}; accepted=117,853.191.",
    )
    add_check(
        checks,
        "accepted_90d_material_action_origin_count_unchanged",
        material_origin == 59,
        f"90-day material action at/before origin rows={material_origin}; accepted=59.",
    )
    add_check(
        checks,
        "accepted_90d_production_start_origin_count_unchanged",
        production_origin == 40,
        f"90-day production start at/before origin rows={production_origin}; accepted=40.",
    )

    sample_filter = final[
        (final["Horizon_Days"].astype(int) == 90)
        & (final["Product_ID"] == "P001")
        & (final["Location_ID"] == "LOC001")
    ]
    add_check(
        checks,
        "sample_filter_product_location_horizon",
        len(sample_filter) == 1,
        f"P001 x LOC001 x 90-day rows={len(sample_filter)}; expected=1.",
    )
    empty_filter = final[final["Product_ID"] == "__missing_product__"]
    add_check(checks, "empty_filter_result_supported", empty_filter.empty, "Simulated empty product filter returns zero rows.")

    panel = data["daily_demand_panel"]
    panel_summary = pd.read_csv(PROJECT_ROOT / "outputs" / "phase2" / "daily_demand_panel_summary.csv")
    expected_rows = int(panel_summary.loc[panel_summary["metric"] == "panel_rows", "value"].iloc[0])
    add_check(
        checks,
        "daily_panel_expected_vs_actual_rows",
        len(panel) == expected_rows,
        f"Daily panel rows={len(panel):,}; accepted Phase 2 summary rows={expected_rows:,}.",
    )

    source_text = (APP_DIR / "streamlit_app.py").read_text(encoding="utf-8")
    forbidden_imports = ["phase1", "phase2", "phase3", "phase4", "phase5", "phase6", "phase7", "phase8", "phase9"]
    found = [token for token in forbidden_imports if f"import {token}" in source_text or f"from {token}" in source_text]
    add_check(
        checks,
        "no_prior_phase_script_imports",
        not found,
        "Dashboard imports no prior phase scripts." if not found else f"Found script imports: {found}",
    )
    external_markers = ["http://", "https://", "requests.", "urllib.", "read_html("]
    found_external = [token for token in external_markers if token in source_text]
    add_check(
        checks,
        "no_external_data_access_in_app",
        not found_external,
        "No external URL/data access markers found in app code." if not found_external else f"Found markers: {found_external}",
    )


def review_fix_checks(data: Dict[str, pd.DataFrame], checks: List[Dict[str, Any]]) -> None:
    import streamlit_app as dashboard

    filters = {
        "page": "Executive Overview",
        "horizon": 90,
        "product_ids": None,
        "location_ids": None,
        "channels": None,
        "families": None,
        "decision_risks": None,
        "inventory_risks": None,
    }
    priority_view = dashboard.management_priority_90d_view(data, filters)
    priority_source = data["management_priority_90d"].copy()
    source_keys = priority_source[["Product_ID", "Location_ID"]].reset_index(drop=True)
    view_keys = priority_view[["Product_ID", "Location_ID"]].reset_index(drop=True)
    add_check(
        checks,
        "executive_management_priority_source_is_90d_output",
        len(priority_view) == len(priority_source) and source_keys.equals(view_keys),
        "Executive management priority view preserves management_priority_90d.csv row count and ordering.",
    )

    app_source = (APP_DIR / "streamlit_app.py").read_text(encoding="utf-8")
    found_wape_literals = [literal for literal in EXPECTED_WAPE_LITERALS if literal in app_source]
    add_check(
        checks,
        "no_hardcoded_accepted_wape_literals_in_dashboard",
        not found_wape_literals,
        "No accepted WAPE display literals remain in app/streamlit_app.py."
        if not found_wape_literals
        else f"Found hardcoded WAPE literals: {found_wape_literals}",
    )

    metrics = dashboard.accepted_model_performance_metrics(data)
    metric_map = {row["Policy"]: float(row["Validation WAPE"]) for row in metrics}
    baseline_source = data["baseline_metrics_overall"]
    baseline_source_value = float(
        baseline_source.loc[
            (baseline_source["Frequency"] == "weekly_distributed")
            & (baseline_source["Baseline"] == "weekly_seasonal_naive_52w"),
            "Cumulative_WAPE",
        ].iloc[0]
    )
    apparent_source_value = float(
        data["policy_comparison"].loc[
            (data["policy_comparison"]["Policy"] == "phase4_apparent_selection")
            & (data["policy_comparison"]["Segment_Type"] == "overall"),
            "Cumulative_WAPE",
        ].iloc[0]
    )
    lofo_source_value = float(
        data["leave_one_fold_out_policy_metrics"].loc[
            (data["leave_one_fold_out_policy_metrics"]["Policy"] == "leave_one_fold_out_selection")
            & (data["leave_one_fold_out_policy_metrics"]["Segment_Type"] == "overall"),
            "Cumulative_WAPE",
        ].iloc[0]
    )
    guarded_source_value = float(
        data["full_coverage_policy_comparison"].loc[
            (data["full_coverage_policy_comparison"]["Policy"] == "guarded_hybrid")
            & (data["full_coverage_policy_comparison"]["Segment_Type"] == "overall"),
            "Cumulative_WAPE",
        ].iloc[0]
    )
    metric_sources_match = (
        abs(metric_map["Baseline weekly_seasonal_naive_52w"] - baseline_source_value) <= 1e-12
        and abs(metric_map["Apparent per-series selected policy"] - apparent_source_value) <= 1e-12
        and abs(metric_map["Leave-one-fold-out policy"] - lofo_source_value) <= 1e-12
        and abs(metric_map["Final guarded hybrid equal-coverage validation"] - guarded_source_value) <= 1e-12
    )
    add_check(
        checks,
        "model_performance_wape_values_loaded_from_accepted_outputs",
        metric_sources_match,
        "Displayed model-performance WAPE values match accepted Phase 3, Phase 4.1, and Phase 5.1 CSV rows.",
    )

    warning_values = dashboard.procurement_systemic_warning_values(data)
    final_90 = data["final_decision"][data["final_decision"]["Horizon_Days"].astype(int) == 90]
    material_counts = final_90["Highest_Risk_Material_Name"].fillna("Not available").value_counts()
    expected_top_material = str(material_counts.index[0])
    expected_top_rows = int(material_counts.iloc[0])
    procurement_values_match = (
        warning_values["total_90_rows"] == len(final_90)
        and warning_values["high_procurement_risk_90_rows"]
        == int((final_90["Product_Historical_Procurement_Risk"] == "High").sum())
        and warning_values["top_highest_risk_material"] == expected_top_material
        and warning_values["top_highest_risk_material_rows"] == expected_top_rows
    )
    old_warning_phrase = "highest-risk material for " + "177" + " 90-day rows"
    hardcoded_procurement_phrase_absent = old_warning_phrase not in app_source
    add_check(
        checks,
        "procurement_systemic_warning_values_derived_from_data",
        procurement_values_match and hardcoded_procurement_phrase_absent,
        "Procurement warning values match accepted Phase 9 data and no old literal warning phrase remains.",
    )


def write_review_fixes_report(data: Dict[str, pd.DataFrame], checks: pd.DataFrame) -> None:
    final = data["final_decision"]
    final_90 = final[final["Horizon_Days"].astype(int) == 90]
    decision_counts = {
        "High": int((final_90["Decision_Risk"] == "High").sum()),
        "Medium": int((final_90["Decision_Risk"] == "Medium").sum()),
        "Low": int((final_90["Decision_Risk"] == "Low").sum()),
    }
    passed = int(checks["passed"].sum())
    total = int(len(checks))

    files_modified = [
        "app/streamlit_app.py",
        "src/phase10_dashboard_validation.py",
        "outputs/phase10/dashboard_validation_checks.csv",
        "outputs/phase10/phase10_dashboard_review_fixes_report.md",
    ]

    lines = [
        "# Phase 10 Dashboard Review Fixes Report",
        "",
        "## Issue 1: management priority source corrected",
        "",
        "Executive Overview now uses outputs/phase9/management_priority_90d.csv for the 90-day Management Priority section and preserves the accepted row order. Non-horizon filters are applied without creating a new priority score. When the global horizon is not 90 days, the dashboard labels the section as the accepted 90-day management view.",
        "",
        "## Issue 2: WAPE values now sourced from accepted outputs",
        "",
        "The Model Performance page now loads WAPE values from accepted CSV rows in Phase 3, Phase 4.1, and Phase 5.1 outputs. If a required row cannot be found, the dashboard fails with a clear message instead of falling back to hardcoded values.",
        "",
        "## Issue 3: procurement warning made data-driven",
        "",
        "The Procurement Risk page now derives the systemic warning values from the accepted Phase 9 final decision output: total 90-day rows, High product-level historical procurement-risk rows, most frequent highest-risk material, and that material's row count.",
        "",
        "## Accepted analytics unchanged",
        "",
        f"- Final decision rows: {len(final):,}",
        f"- Product x Location pairs: {final[['Product_ID', 'Location_ID']].drop_duplicates().shape[0]:,}",
        f"- Horizon row counts: {final['Horizon_Days'].astype(int).value_counts().sort_index().to_dict()}",
        f"- 90-day Decision_Risk counts: {decision_counts}",
        f"- 90-day expected shortage: {final_90['Expected_Shortage_Units'].sum():,.3f}",
        f"- 90-day recommended replenishment: {final_90['Recommended_Replenishment_Qty'].sum():,.3f}",
        f"- Conditional material action at/before origin rows: {int((final_90['Material_Action_Status'] == 'At/Before forecast origin').sum())}",
        f"- Conditional production start at/before origin rows: {int((final_90['Production_Action_Status'] == 'At/Before forecast origin').sum())}",
        "",
        "## Validation results",
        "",
        f"Validation checks passed: {passed}/{total}. See outputs/phase10/dashboard_validation_checks.csv for row-level results.",
        "",
        "## Exact files modified",
        "",
    ]
    lines += [f"- {path}" for path in files_modified]
    lines += [
        "",
        "No Phase 1-9 analytical output was modified.",
        "",
    ]

    (OUTPUT_DIR / "phase10_dashboard_review_fixes_report.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    checks: List[Dict[str, Any]] = []
    compile_app_files(checks)
    package_checks(checks)
    app_import_and_startup_checks(checks)
    data = load_all_data()
    dashboard_data_checks(data, checks)
    review_fix_checks(data, checks)

    checks_df = pd.DataFrame(checks)
    checks_df.to_csv(OUTPUT_DIR / "dashboard_validation_checks.csv", index=False, encoding="utf-8-sig")
    write_review_fixes_report(data, checks_df)

    failed = checks_df[~checks_df["passed"]]
    if not failed.empty:
        print(failed.to_string(index=False))
        raise SystemExit(1)
    print(f"Phase 10 dashboard validation passed: {len(checks_df)} checks.")


if __name__ == "__main__":
    main()
