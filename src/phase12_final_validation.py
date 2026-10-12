from __future__ import annotations

import hashlib
import importlib.util
import json
import py_compile
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_DIR = PROJECT_ROOT / "app"
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "phase12"
CHECKS_PATH = OUTPUT_DIR / "phase12_final_validation_checks.csv"
REPORT_PATH = OUTPUT_DIR / "phase12_final_delivery_report.md"
MANIFEST_PATH = OUTPUT_DIR / "delivery_manifest.csv"
NOTEBOOK_PATH = PROJECT_ROOT / "notebooks" / "el_sharnouby_end_to_end_analysis.ipynb"


REQUIRED_FOLDERS = [
    "app",
    "data/processed",
    "notebooks",
    "outputs/phase1",
    "outputs/phase2",
    "outputs/phase3",
    "outputs/phase4",
    "outputs/phase4_1",
    "outputs/phase5",
    "outputs/phase5_1",
    "outputs/phase6",
    "outputs/phase7",
    "outputs/phase8",
    "outputs/phase9",
    "outputs/phase10",
    "outputs/phase11",
    "src",
]

REQUIRED_SOURCE_FILES = [
    "README.md",
    "requirements.txt",
    "app/streamlit_app.py",
    "app/data_loader.py",
    "app/charts.py",
    "app/components.py",
    "app/RUN_DASHBOARD.md",
    "src/phase10_dashboard_validation.py",
    "src/phase11_notebook_validation.py",
    "src/phase12_final_validation.py",
]

REQUIRED_ACCEPTED_OUTPUTS = [
    "data/processed/daily_product_location_demand_panel.csv",
    "data/processed/monthly_sales_inventory_reconciliation.csv",
    "notebooks/el_sharnouby_end_to_end_analysis.ipynb",
    "outputs/phase1/table_summary.csv",
    "outputs/phase1/phase1_data_audit_report.md",
    "outputs/phase2/demand_series_eda.csv",
    "outputs/phase2/inventory_accounting_summary.csv",
    "outputs/phase2/sales_inventory_reconciliation_summary.csv",
    "outputs/phase2/leakage_risk_table.csv",
    "outputs/phase2/phase2_cleaning_eda_report.md",
    "outputs/phase3/baseline_metrics_overall.csv",
    "outputs/phase3/phase3_baseline_report.md",
    "outputs/phase4/model_metrics_overall.csv",
    "outputs/phase4/phase4_model_comparison_report.md",
    "outputs/phase4_1/policy_comparison.csv",
    "outputs/phase4_1/leave_one_fold_out_policy_metrics.csv",
    "outputs/phase4_1/phase4_1_selection_robustness_report.md",
    "outputs/phase5/forecast_results.csv",
    "outputs/phase5/stockout_analysis.csv",
    "outputs/phase5/phase5_forecast_inventory_report.md",
    "outputs/phase5_1/full_coverage_policy_comparison.csv",
    "outputs/phase5_1/phase5_1_fair_policy_validation_report.md",
    "outputs/phase6/material_requirements_summary.csv",
    "outputs/phase6/product_replenishment_requirements.csv",
    "outputs/phase6/phase6_bom_material_requirements_report.md",
    "outputs/phase7/historical_procurement_risk.csv",
    "outputs/phase7/material_requirement_procurement_risk.csv",
    "outputs/phase7/phase7_procurement_risk_report.md",
    "outputs/phase8/historical_production_risk.csv",
    "outputs/phase8/product_replenishment_production_risk.csv",
    "outputs/phase8/phase8_production_risk_report.md",
    "outputs/phase9/final_decision_recommendations.csv",
    "outputs/phase9/management_priority_90d.csv",
    "outputs/phase9/phase9_final_decision_report.md",
    "outputs/phase10/dashboard_validation_checks.csv",
    "outputs/phase10/phase10_dashboard_report.md",
    "outputs/phase10/phase10_dashboard_review_fixes_report.md",
    "outputs/phase11/phase11_notebook_validation_checks.csv",
    "outputs/phase11/phase11_notebook_report.md",
]

REQUIRED_PACKAGES = ["streamlit", "pandas", "numpy", "plotly", "matplotlib", "ipython"]


def add_check(checks: list[dict[str, Any]], name: str, passed: bool, detail: str) -> None:
    checks.append({"check": name, "passed": bool(passed), "detail": detail})


def relative(path: Path) -> str:
    return path.relative_to(PROJECT_ROOT).as_posix()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def accepted_phase_files() -> list[Path]:
    roots = [PROJECT_ROOT / "data" / "processed", PROJECT_ROOT / "notebooks"]
    roots.extend(PROJECT_ROOT / "outputs" / f"phase{index}" for index in range(1, 12))
    files: list[Path] = []
    for root in roots:
        if root.exists():
            files.extend(path for path in root.rglob("*") if path.is_file())
    return sorted(files)


def file_hashes(files: list[Path]) -> dict[str, str]:
    return {str(path): sha256(path) for path in files if path.exists()}


def notebook_summary() -> dict[str, int]:
    notebook = json.loads(NOTEBOOK_PATH.read_text(encoding="utf-8"))
    cells = notebook.get("cells", [])
    code_cells = [cell for cell in cells if cell.get("cell_type") == "code"]
    outputs = [output for cell in code_cells for output in cell.get("outputs", [])]
    return {
        "total_cells": len(cells),
        "code_cells": len(code_cells),
        "cells_with_ids": sum(1 for cell in cells if isinstance(cell.get("id"), str) and bool(cell.get("id").strip())),
        "unique_ids": len({cell.get("id") for cell in cells if isinstance(cell.get("id"), str) and bool(cell.get("id").strip())}),
        "code_cells_with_execution_counts": sum(1 for cell in code_cells if cell.get("execution_count") is not None),
        "saved_outputs": len(outputs),
        "saved_error_outputs": sum(1 for output in outputs if output.get("output_type") == "error"),
        "saved_table_outputs": sum(1 for output in outputs if "<table" in str(output.get("data", {}).get("text/html", "")).lower()),
        "saved_chart_outputs": sum(1 for output in outputs if "image/png" in output.get("data", {})),
    }


def check_folders_and_files(checks: list[dict[str, Any]]) -> None:
    missing_folders = [folder for folder in REQUIRED_FOLDERS if not (PROJECT_ROOT / folder).is_dir()]
    add_check(
        checks,
        "required_folders_exist",
        not missing_folders,
        "Missing folders: " + ", ".join(missing_folders),
    )
    missing_sources = [path for path in REQUIRED_SOURCE_FILES if not (PROJECT_ROOT / path).is_file()]
    add_check(
        checks,
        "required_source_files_exist",
        not missing_sources,
        "Missing source files: " + ", ".join(missing_sources),
    )
    missing_outputs = [path for path in REQUIRED_ACCEPTED_OUTPUTS if not (PROJECT_ROOT / path).is_file()]
    add_check(
        checks,
        "required_accepted_output_files_exist",
        not missing_outputs,
        "Missing accepted outputs: " + ", ".join(missing_outputs),
    )


def check_readme_and_requirements(checks: list[dict[str, Any]]) -> None:
    readme = PROJECT_ROOT / "README.md"
    requirements = PROJECT_ROOT / "requirements.txt"
    add_check(checks, "readme_exists", readme.exists(), relative(readme) if readme.exists() else "README.md missing.")
    if readme.exists():
        text = readme.read_text(encoding="utf-8").lower()
        required_snippets = [
            "project objective",
            "business scope",
            "folder structure",
            "python -m pip install -r requirements.txt",
            "streamlit run app/streamlit_app.py",
            "notebooks/el_sharnouby_end_to_end_analysis.ipynb",
            "key outputs",
            "known limitations",
        ]
        missing = [snippet for snippet in required_snippets if snippet not in text]
        add_check(checks, "readme_run_review_instructions_exist", not missing, "Missing README snippets: " + ", ".join(missing))

    add_check(checks, "requirements_file_exists", requirements.exists(), relative(requirements) if requirements.exists() else "requirements.txt missing.")
    if requirements.exists():
        lines = [
            line.strip().lower()
            for line in requirements.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        missing = [package for package in REQUIRED_PACKAGES if package not in lines]
        unexpected = [package for package in lines if package not in REQUIRED_PACKAGES]
        add_check(checks, "requirements_are_minimal_for_delivery_runtime", not missing and not unexpected, f"missing={missing}; unexpected={unexpected}")
        unavailable = [package for package in REQUIRED_PACKAGES if importlib.util.find_spec("IPython" if package == "ipython" else package) is None]
        add_check(checks, "required_packages_importable_in_current_environment", not unavailable, "Unavailable packages: " + ", ".join(unavailable))


def check_notebook(checks: list[dict[str, Any]]) -> dict[str, int]:
    add_check(checks, "final_notebook_exists", NOTEBOOK_PATH.exists(), relative(NOTEBOOK_PATH))
    summary = notebook_summary() if NOTEBOOK_PATH.exists() else {}
    if summary:
        add_check(
            checks,
            "final_notebook_saved_state_ready",
            summary["total_cells"] == 33
            and summary["code_cells"] == 15
            and summary["cells_with_ids"] == summary["total_cells"]
            and summary["unique_ids"] == summary["total_cells"]
            and summary["code_cells_with_execution_counts"] == summary["code_cells"]
            and summary["saved_outputs"] > 0
            and summary["saved_table_outputs"] > 0
            and summary["saved_chart_outputs"] > 0
            and summary["saved_error_outputs"] == 0,
            str(summary),
        )
    return summary


def compile_python_sources(checks: list[dict[str, Any]]) -> None:
    files = [
        APP_DIR / "charts.py",
        APP_DIR / "components.py",
        APP_DIR / "data_loader.py",
        APP_DIR / "streamlit_app.py",
        PROJECT_ROOT / "src" / "phase10_dashboard_validation.py",
        PROJECT_ROOT / "src" / "phase11_notebook_validation.py",
        PROJECT_ROOT / "src" / "phase12_final_validation.py",
    ]
    failures: list[str] = []
    for path in files:
        try:
            py_compile.compile(str(path), doraise=True)
        except Exception as exc:  # noqa: BLE001 - validation must report any compile failure.
            failures.append(f"{relative(path)}: {exc}")
    add_check(checks, "delivery_python_sources_compile", not failures, "Failures: " + " | ".join(failures))


def dashboard_import_and_data_check(checks: list[dict[str, Any]]) -> str:
    sys.path.insert(0, str(APP_DIR))
    try:
        import streamlit_app  # noqa: F401
        from data_loader import load_all_data

        data = load_all_data()
        final_rows = len(data["final_decision"])
        add_check(checks, "dashboard_import_and_data_load", final_rows == 531, f"final_decision_rows={final_rows}")
        return f"Dashboard import/data load passed; final_decision rows={final_rows}."
    except Exception as exc:  # noqa: BLE001 - validation must report import/data failures.
        add_check(checks, "dashboard_import_and_data_load", False, str(exc))
        return f"Dashboard import/data load failed: {exc}"


def dashboard_startup_check(checks: list[dict[str, Any]]) -> str:
    if importlib.util.find_spec("streamlit") is None:
        detail = "Skipped because Streamlit is not installed in this environment."
        add_check(checks, "dashboard_streamlit_startup_smoke", True, detail)
        return detail

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
            "--server.fileWatcherType",
            "none",
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
                with urllib.request.urlopen(f"http://127.0.0.1:{port}", timeout=2) as response:
                    status = response.status
                    break
            except Exception:
                time.sleep(1)
        output = ""
        if process.poll() is not None:
            output = process.communicate(timeout=1)[0]
        passed = status == 200
        detail = f"HTTP status={status}; port={port}." if passed else f"HTTP status={status}; output={output[:500]}"
        add_check(checks, "dashboard_streamlit_startup_smoke", passed, detail)
        return detail
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()


def check_no_external_or_retraining_artifacts(checks: list[dict[str, Any]]) -> None:
    suspicious_path_tokens = ("external", "api", "downloaded", "web_data")
    suspicious_paths = []
    for path in PROJECT_ROOT.rglob("*"):
        if not path.is_file():
            continue
        rel = relative(path).lower()
        if rel.startswith(".git/"):
            continue
        if any(token in Path(rel).parts for token in suspicious_path_tokens):
            suspicious_paths.append(relative(path))
    add_check(
        checks,
        "no_external_data_or_api_artifact_paths",
        not suspicious_paths,
        "Suspicious paths: " + ", ".join(suspicious_paths),
    )

    scanned_files = [
        PROJECT_ROOT / "README.md",
        APP_DIR / "streamlit_app.py",
        APP_DIR / "data_loader.py",
        APP_DIR / "charts.py",
        APP_DIR / "components.py",
        NOTEBOOK_PATH,
    ]
    forbidden_external = ["requests.", "read_html(", "urlopen(", "http://", "https://"]
    external_hits = []
    forbidden_modeling = ["sklearn", ".fit(", ".predict(", "HistGradientBoostingRegressor", "RandomForest", "ExponentialSmoothing"]
    modeling_hits = []
    for path in scanned_files:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for token in forbidden_external:
            if token in text:
                external_hits.append(f"{relative(path)}:{token}")
        for token in forbidden_modeling:
            if token in text:
                modeling_hits.append(f"{relative(path)}:{token}")
    add_check(checks, "no_external_data_access_in_delivery_artifacts", not external_hits, "Hits: " + ", ".join(external_hits))
    add_check(checks, "no_model_retraining_or_forecast_regeneration_in_delivery_artifacts", not modeling_hits, "Hits: " + ", ".join(modeling_hits))


def write_manifest() -> None:
    rows = []
    main_files = [
        "README.md",
        "requirements.txt",
        "app/streamlit_app.py",
        "app/RUN_DASHBOARD.md",
        "notebooks/el_sharnouby_end_to_end_analysis.ipynb",
        "outputs/phase10/dashboard_validation_checks.csv",
        "outputs/phase10/phase10_dashboard_review_fixes_report.md",
        "outputs/phase11/phase11_notebook_validation_checks.csv",
        "outputs/phase11/phase11_notebook_report.md",
        "outputs/phase12/phase12_final_validation_checks.csv",
        "outputs/phase12/phase12_final_delivery_report.md",
    ]
    main_files.extend(REQUIRED_ACCEPTED_OUTPUTS[:])
    for item in dict.fromkeys(main_files):
        path = PROJECT_ROOT / item
        rows.append({
            "relative_path": item,
            "exists": path.exists(),
            "file_size_bytes": path.stat().st_size if path.exists() else None,
            "delivery_role": "final_delivery_file",
        })
    pd.DataFrame(rows).to_csv(MANIFEST_PATH, index=False)


def write_report(
    checks: list[dict[str, Any]],
    notebook: dict[str, int],
    dashboard_import_detail: str,
    dashboard_startup_detail: str,
    changed_accepted_files: list[str],
) -> None:
    passed = sum(1 for check in checks if check["passed"])
    total = len(checks)
    failed = [check for check in checks if not check["passed"]]
    lines = [
        "# Phase 12 Final Delivery Report",
        "",
        "## Scope",
        "",
        "Phase 12 prepared packaging, documentation, runtime requirements, and final validation only. It did not retrain models, regenerate forecasts, change accepted metrics, or add external data.",
        "",
        "## Validation Result",
        "",
        f"- Checks passed: {passed} / {total}",
        f"- Dashboard import/data result: {dashboard_import_detail}",
        f"- Dashboard startup result: {dashboard_startup_detail}",
        f"- Accepted Phase 1-11 files changed during validation: {len(changed_accepted_files)}",
        "",
        "## Notebook Readiness",
        "",
        f"- Total cells: {notebook.get('total_cells', 0)}",
        f"- Code cells: {notebook.get('code_cells', 0)}",
        f"- Cells with IDs: {notebook.get('cells_with_ids', 0)}",
        f"- Unique IDs: {notebook.get('unique_ids', 0)}",
        f"- Code cells with execution counts: {notebook.get('code_cells_with_execution_counts', 0)}",
        f"- Saved outputs: {notebook.get('saved_outputs', 0)}",
        f"- Saved table outputs: {notebook.get('saved_table_outputs', 0)}",
        f"- Saved chart outputs: {notebook.get('saved_chart_outputs', 0)}",
        f"- Saved error outputs: {notebook.get('saved_error_outputs', 0)}",
        "",
        "## Files Created or Modified in Phase 12",
        "",
        "- `README.md`",
        "- `requirements.txt`",
        "- `src/phase12_final_validation.py`",
        "- `outputs/phase12/phase12_final_validation_checks.csv`",
        "- `outputs/phase12/phase12_final_delivery_report.md`",
        "- `outputs/phase12/delivery_manifest.csv`",
        "",
        "## Accepted Analytical Outputs",
        "",
    ]
    if changed_accepted_files:
        lines.append("The following accepted Phase 1-11 files changed during validation and require review:")
        lines.extend(f"- `{path}`" for path in changed_accepted_files)
    else:
        lines.append("No accepted Phase 1-11 analytical outputs were modified during Phase 12 validation.")

    lines.extend(["", "## Failed Checks", ""])
    if failed:
        lines.extend(f"- `{check['check']}`: {check['detail']}" for check in failed)
    else:
        lines.append("- None.")

    lines.extend([
        "",
        "## Delivery Recommendation",
        "",
        "The project is ready for final review using the README instructions, Streamlit dashboard, final executed notebook, and accepted phase outputs.",
        "",
    ])
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    checks: list[dict[str, Any]] = []
    accepted_files = accepted_phase_files()
    before_hashes = file_hashes(accepted_files)

    check_folders_and_files(checks)
    check_readme_and_requirements(checks)
    notebook = check_notebook(checks)
    compile_python_sources(checks)
    dashboard_import_detail = dashboard_import_and_data_check(checks)
    dashboard_startup_detail = dashboard_startup_check(checks)
    check_no_external_or_retraining_artifacts(checks)

    after_hashes = file_hashes(accepted_files)
    changed = [relative(Path(path)) for path, digest in before_hashes.items() if after_hashes.get(path) != digest]
    add_check(
        checks,
        "phase1_to_phase11_accepted_outputs_unchanged_during_validation",
        not changed,
        "Changed files: " + ", ".join(changed),
    )

    checks_df = pd.DataFrame(checks)
    checks_df.to_csv(CHECKS_PATH, index=False)
    write_report(checks, notebook, dashboard_import_detail, dashboard_startup_detail, changed)
    write_manifest()

    failed = checks_df[~checks_df["passed"]]
    if not failed.empty:
        print(failed.to_string(index=False))
        return 1
    print(f"Phase 12 final validation passed: {len(checks_df)} checks.")
    print(f"Dashboard startup: {dashboard_startup_detail}")
    print(f"Notebook saved outputs: {notebook.get('saved_outputs', 0)}")
    print(f"Accepted Phase 1-11 changed files: {len(changed)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
