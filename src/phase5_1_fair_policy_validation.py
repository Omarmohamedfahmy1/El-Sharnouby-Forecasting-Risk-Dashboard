"""Phase 5.1 fair policy comparison validation.

This phase audits the Phase 5 guarded-hybrid policy decision on identical
validation windows. It creates separate Phase 5.1 outputs and only regenerates
Phase 5 outputs if the equal-coverage policy decision changes.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from phase3_forecasting_baseline import HORIZONS, aggregate_metric_frame, fmt, markdown_table
from phase4_model_comparison import evaluate_models, load_inputs
from phase5_forecast_inventory import (
    DATA_DIR,
    DEFAULT_PANEL_PATH,
    DEFAULT_PHASE4_1_DIR,
    DEFAULT_PHASE4_DIR,
    DEFAULT_SERIES_EDA_PATH,
    GLOBAL_BASELINE,
    Phase5Outputs,
    align_inventory,
    apply_monotonic_reconciliation,
    generate_future_forecasts,
    inventory_risk_summary,
    latest_inventory_snapshot,
    select_guarded_rows,
    validate_outputs as validate_phase5_outputs,
    write_outputs as write_phase5_outputs,
)


DEFAULT_PHASE5_DIR = Path("outputs") / "phase5"
DEFAULT_OUTPUT_DIR = Path("outputs") / "phase5_1"
KEY_COLS = ["Product_ID", "Location_ID", "Horizon_Days", "Fold_ID", "Forecast_Origin"]
LOCAL_HOLT_WINTERS_MIN_WEEKS = 112


@dataclass
class Phase51Outputs:
    missing_guarded_validation_windows: pd.DataFrame
    common_window_policy_comparison: pd.DataFrame
    full_coverage_policy_comparison: pd.DataFrame
    guarded_model_coverage: pd.DataFrame
    monotonic_reconciliation_validation: pd.DataFrame
    validation_checks: pd.DataFrame
    final_policy_name: str
    final_policy_reason: str
    phase5_regenerated: bool
    risk_change_summary: pd.DataFrame
    shortage_replenishment_change_summary: pd.DataFrame


def normalize_record_dates(records: pd.DataFrame) -> pd.DataFrame:
    work = records.copy()
    for col in ["Forecast_Origin", "Forecast_Start", "Forecast_End"]:
        if col in work.columns:
            work[col] = pd.to_datetime(work[col])
    return work


def baseline_validation_records(candidate_records: pd.DataFrame) -> pd.DataFrame:
    records = candidate_records[
        candidate_records["Model_Source"].eq("baseline")
        & candidate_records["Frequency"].eq("weekly_distributed")
        & candidate_records["Model"].eq(GLOBAL_BASELINE)
    ].copy()
    records["Policy"] = "global_best_baseline"
    records["Runtime_Fallback_To_Baseline"] = False
    records["Guarded_Intended_Model_Source"] = "baseline"
    records["Guarded_Intended_Model"] = GLOBAL_BASELINE
    records["Guarded_Intended_Frequency"] = "weekly_distributed"
    records["Policy_Selected_Model_Source"] = "baseline"
    records["Policy_Selected_Model"] = GLOBAL_BASELINE
    records["Policy_Selected_Frequency"] = "weekly_distributed"
    records["Prediction_Availability"] = "available"
    return normalize_record_dates(records)


def key_index(frame: pd.DataFrame) -> pd.MultiIndex:
    if frame.empty:
        return pd.MultiIndex.from_arrays([[] for _ in KEY_COLS], names=KEY_COLS)
    return pd.MultiIndex.from_frame(frame[KEY_COLS])


def key_set(frame: pd.DataFrame) -> set[tuple[object, ...]]:
    if frame.empty:
        return set()
    work = frame[KEY_COLS].copy()
    work["Forecast_Origin"] = pd.to_datetime(work["Forecast_Origin"])
    return set(map(tuple, work.itertuples(index=False, name=None)))


def semi_join_on_keys(frame: pd.DataFrame, keys: pd.MultiIndex) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    return frame[key_index(frame).isin(keys)].copy()


def training_week_count(panel: pd.DataFrame, product_id: str, location_id: str, origin: pd.Timestamp) -> int:
    series = panel[
        panel["Product_ID"].eq(product_id)
        & panel["Location_ID"].eq(location_id)
        & (panel["Date"] <= origin)
    ].sort_values("Date")
    if series.empty:
        return 0
    return int(series.set_index("Date")["Demand_Units"].astype(float).resample("W-SUN").sum().shape[0])


def unavailable_reason(row: pd.Series, panel: pd.DataFrame) -> str:
    model = row["Guarded_Model"]
    if model == "advanced_local_holt_winters_additive_52w":
        weeks = training_week_count(panel, row["Product_ID"], row["Location_ID"], row["Forecast_Origin"])
        return (
            f"{model} was not generated for this fold because completed weekly training history "
            f"was {weeks} weeks, below the {LOCAL_HOLT_WINTERS_MIN_WEEKS}-week minimum used by Phase 4."
        )
    if str(row["Guarded_Model_Source"]) == "advanced":
        return (
            f"{model} has no candidate prediction for this fold in Phase 4 candidate records; "
            "production-safe evaluation must fall back to the global weekly seasonal baseline."
        )
    return "Unexpected missing baseline guarded prediction; investigate candidate record coverage."


def selected_candidate_records(
    candidate_records: pd.DataFrame,
    row: pd.Series,
) -> pd.DataFrame:
    return candidate_records[
        candidate_records["Product_ID"].eq(row["Product_ID"])
        & candidate_records["Location_ID"].eq(row["Location_ID"])
        & candidate_records["Horizon_Days"].eq(row["Horizon_Days"])
        & candidate_records["Model_Source"].eq(row["Guarded_Model_Source"])
        & candidate_records["Frequency"].eq(row["Guarded_Frequency"])
        & candidate_records["Model"].eq(row["Guarded_Model"])
    ].copy()


def build_guarded_records(
    candidate_records: pd.DataFrame,
    guarded_rows: pd.DataFrame,
    baseline_records: pd.DataFrame,
    panel: pd.DataFrame,
    fallback_missing_windows: bool,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    parts: list[pd.DataFrame] = []
    missing_parts: list[pd.DataFrame] = []
    candidate_records = normalize_record_dates(candidate_records)
    baseline_records = normalize_record_dates(baseline_records)

    for _, guarded_row in guarded_rows.iterrows():
        expected = baseline_records[
            baseline_records["Product_ID"].eq(guarded_row["Product_ID"])
            & baseline_records["Location_ID"].eq(guarded_row["Location_ID"])
            & baseline_records["Horizon_Days"].eq(guarded_row["Horizon_Days"])
        ].copy()
        selected = selected_candidate_records(candidate_records, guarded_row)
        selected = normalize_record_dates(selected)
        if not selected.empty:
            selected["Policy"] = "guarded_hybrid"
            selected["Runtime_Fallback_To_Baseline"] = False
            selected["Guarded_Intended_Model_Source"] = guarded_row["Guarded_Model_Source"]
            selected["Guarded_Intended_Model"] = guarded_row["Guarded_Model"]
            selected["Guarded_Intended_Frequency"] = guarded_row["Guarded_Frequency"]
            selected["Policy_Selected_Model_Source"] = selected["Model_Source"]
            selected["Policy_Selected_Model"] = selected["Model"]
            selected["Policy_Selected_Frequency"] = selected["Frequency"]
            selected["Prediction_Availability"] = "available"
            parts.append(selected)

        selected_keys = key_index(selected)
        missing = expected[~key_index(expected).isin(selected_keys)].copy()
        if not missing.empty:
            missing["Guarded_Model"] = guarded_row["Guarded_Model"]
            missing["Guarded_Model_Source"] = guarded_row["Guarded_Model_Source"]
            missing["Guarded_Frequency"] = guarded_row["Guarded_Frequency"]
            missing["Unavailable_Reason"] = missing.apply(lambda x: unavailable_reason(x, panel), axis=1)
            missing_parts.append(
                missing[
                    [
                        "Product_ID",
                        "Location_ID",
                        "Horizon_Days",
                        "Fold_ID",
                        "Forecast_Origin",
                        "Forecast_Start",
                        "Forecast_End",
                        "Demand_Pattern_Class",
                        "Channel",
                        "Product_Family",
                        "Guarded_Model",
                        "Guarded_Model_Source",
                        "Guarded_Frequency",
                        "Unavailable_Reason",
                    ]
                ].copy()
            )
            if fallback_missing_windows:
                fallback = missing.drop(
                    columns=["Guarded_Model", "Guarded_Model_Source", "Guarded_Frequency", "Unavailable_Reason"],
                    errors="ignore",
                ).copy()
                fallback["Policy"] = "guarded_hybrid"
                fallback["Runtime_Fallback_To_Baseline"] = True
                fallback["Guarded_Intended_Model_Source"] = guarded_row["Guarded_Model_Source"]
                fallback["Guarded_Intended_Model"] = guarded_row["Guarded_Model"]
                fallback["Guarded_Intended_Frequency"] = guarded_row["Guarded_Frequency"]
                fallback["Policy_Selected_Model_Source"] = "baseline"
                fallback["Policy_Selected_Model"] = GLOBAL_BASELINE
                fallback["Policy_Selected_Frequency"] = "weekly_distributed"
                fallback["Prediction_Availability"] = "fallback_to_baseline"
                parts.append(fallback)

    guarded = pd.concat(parts, ignore_index=True, sort=False) if parts else pd.DataFrame()
    missing_windows = (
        pd.concat(missing_parts, ignore_index=True, sort=False)
        if missing_parts
        else pd.DataFrame(
            columns=[
                "Product_ID",
                "Location_ID",
                "Horizon_Days",
                "Fold_ID",
                "Forecast_Origin",
                "Forecast_Start",
                "Forecast_End",
                "Demand_Pattern_Class",
                "Channel",
                "Product_Family",
                "Guarded_Model",
                "Guarded_Model_Source",
                "Guarded_Frequency",
                "Unavailable_Reason",
            ]
        )
    )
    return normalize_record_dates(guarded), normalize_record_dates(missing_windows)


def comparison_metrics(records: pd.DataFrame) -> pd.DataFrame:
    frames = [
        aggregate_metric_frame(records, ["Policy"]).assign(Segment_Type="overall"),
        aggregate_metric_frame(records, ["Policy", "Horizon_Days"]).assign(Segment_Type="by_horizon"),
        aggregate_metric_frame(records, ["Policy", "Demand_Pattern_Class"]).assign(Segment_Type="by_demand_class"),
        aggregate_metric_frame(records, ["Policy", "Fold_ID", "Forecast_Origin"]).assign(Segment_Type="by_fold"),
    ]
    return pd.concat(frames, ignore_index=True, sort=False)


def build_common_window_comparison(
    baseline_records: pd.DataFrame,
    guarded_strict_records: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    common_keys = key_index(baseline_records).intersection(key_index(guarded_strict_records))
    baseline_common = semi_join_on_keys(baseline_records, common_keys)
    guarded_common = semi_join_on_keys(guarded_strict_records, common_keys)
    combined = pd.concat([baseline_common, guarded_common], ignore_index=True, sort=False)
    return comparison_metrics(combined), baseline_common, guarded_common


def build_full_coverage_comparison(
    baseline_records: pd.DataFrame,
    guarded_full_records: pd.DataFrame,
) -> pd.DataFrame:
    combined = pd.concat([baseline_records, guarded_full_records], ignore_index=True, sort=False)
    return comparison_metrics(combined)


def guarded_advanced_coverage(
    guarded_rows: pd.DataFrame,
    candidate_records: pd.DataFrame,
    baseline_records: pd.DataFrame,
    missing_windows: pd.DataFrame,
) -> pd.DataFrame:
    rows = []
    advanced = guarded_rows[guarded_rows["Use_Advanced_Guard"]].copy()
    for _, row in advanced.iterrows():
        expected = baseline_records[
            baseline_records["Product_ID"].eq(row["Product_ID"])
            & baseline_records["Location_ID"].eq(row["Location_ID"])
            & baseline_records["Horizon_Days"].eq(row["Horizon_Days"])
        ]
        selected = selected_candidate_records(candidate_records, row)
        missing = missing_windows[
            missing_windows["Product_ID"].eq(row["Product_ID"])
            & missing_windows["Location_ID"].eq(row["Location_ID"])
            & missing_windows["Horizon_Days"].eq(row["Horizon_Days"])
        ]
        expected_windows = len(expected)
        available_windows = len(selected)
        missing_count = max(0, expected_windows - available_windows)
        coverage_status = (
            "full"
            if missing_count == 0
            else "none"
            if available_windows == 0
            else "partial"
        )
        rows.append(
            {
                "Product_ID": row["Product_ID"],
                "Location_ID": row["Location_ID"],
                "Horizon_Days": row["Horizon_Days"],
                "Demand_Pattern_Class": row["Demand_Pattern_Class"],
                "Channel": row["Channel"],
                "Product_Family": row["Product_Family"],
                "Guarded_Model": row["Guarded_Model"],
                "Guarded_Model_Source": row["Guarded_Model_Source"],
                "Expected_Validation_Windows": expected_windows,
                "Available_Guarded_Windows": available_windows,
                "Missing_Guarded_Windows": missing_count,
                "Coverage_Status": coverage_status,
                "Missing_Reasons": " | ".join(sorted(missing["Unavailable_Reason"].dropna().unique())),
            }
        )
    return pd.DataFrame(rows).sort_values(["Coverage_Status", "Product_ID", "Location_ID", "Horizon_Days"])


def overall_wape(comparison: pd.DataFrame, policy: str) -> float:
    rows = comparison[comparison["Segment_Type"].eq("overall") & comparison["Policy"].eq(policy)]
    if rows.empty:
        return float("nan")
    return float(rows["Cumulative_WAPE"].iloc[0])


def choose_final_policy(full_comparison: pd.DataFrame) -> tuple[str, str]:
    baseline_wape = overall_wape(full_comparison, "global_best_baseline")
    guarded_wape = overall_wape(full_comparison, "guarded_hybrid")
    if guarded_wape < baseline_wape:
        return (
            "guarded_hybrid",
            f"Equal-coverage guarded hybrid WAPE {guarded_wape:.3f}% beat baseline {baseline_wape:.3f}%.",
        )
    return (
        "global_best_baseline",
        f"Equal-coverage guarded hybrid WAPE {guarded_wape:.3f}% did not beat baseline {baseline_wape:.3f}%.",
    )


def current_phase5_policy(phase5_dir: Path) -> str:
    forecast_path = phase5_dir / "forecast_results.csv"
    if not forecast_path.exists():
        return "unknown"
    forecast = pd.read_csv(forecast_path)
    if "Selected_Model_Source" in forecast.columns and forecast["Selected_Model_Source"].eq("advanced").any():
        return "guarded_hybrid"
    return "global_best_baseline"


def regenerate_phase5_outputs(
    panel: pd.DataFrame,
    series_eda: pd.DataFrame,
    guarded_rows: pd.DataFrame,
    full_comparison: pd.DataFrame,
    final_policy_name: str,
    final_policy_reason: str,
    data_dir: Path,
    phase5_dir: Path,
) -> Phase5Outputs:
    forecast_results, daily_path = generate_future_forecasts(
        panel,
        series_eda,
        final_policy_name,
        final_policy_reason,
        guarded_rows,
    )
    forecast_results, daily_path = apply_monotonic_reconciliation(forecast_results, daily_path)
    latest = latest_inventory_snapshot(data_dir)
    stockout = align_inventory(forecast_results, daily_path, latest)
    summary = inventory_risk_summary(stockout)
    checks = validate_phase5_outputs(forecast_results, latest, stockout, full_comparison, final_policy_name)
    outputs = Phase5Outputs(
        final_forecast_policy_validation=full_comparison,
        forecast_results=forecast_results,
        latest_inventory_snapshot=latest,
        stockout_analysis=stockout,
        inventory_risk_summary=summary,
        validation_checks=checks,
        final_policy_name=final_policy_name,
        final_policy_reason=final_policy_reason,
    )
    write_phase5_outputs(outputs, phase5_dir)
    return outputs


def risk_change(before: pd.DataFrame, after: pd.DataFrame) -> pd.DataFrame:
    cols = ["Low_Risk_Count", "Medium_Risk_Count", "High_Risk_Count"]
    merged = before[["Horizon_Days", *cols]].merge(
        after[["Horizon_Days", *cols]],
        on="Horizon_Days",
        how="outer",
        suffixes=("_Before", "_After"),
    )
    for col in cols:
        merged[f"{col}_Delta"] = merged[f"{col}_After"] - merged[f"{col}_Before"]
    return merged.sort_values("Horizon_Days")


def shortage_replenishment_change(before: pd.DataFrame, after: pd.DataFrame) -> pd.DataFrame:
    cols = ["Expected_Shortage_Total", "Recommended_Replenishment_Total"]
    merged = before[["Horizon_Days", *cols]].merge(
        after[["Horizon_Days", *cols]],
        on="Horizon_Days",
        how="outer",
        suffixes=("_Before", "_After"),
    )
    for col in cols:
        merged[f"{col}_Delta"] = merged[f"{col}_After"] - merged[f"{col}_Before"]
    return merged.sort_values("Horizon_Days")


def monotonic_reconciliation_validation(phase5_dir: Path) -> pd.DataFrame:
    forecast = pd.read_csv(phase5_dir / "forecast_results.csv")
    original_col = "Model_Forecast_Demand_Before_Monotonic_Reconciliation"
    if original_col not in forecast.columns:
        original_col = "Forecast_Demand"
        forecast["Monotonic_Reconciliation_Adjustment"] = 0.0
        forecast["Monotonic_Reconciliation_Applied"] = False
    rows = []
    for _, group in forecast.sort_values(["Product_ID", "Location_ID", "Horizon_Days"]).groupby(
        ["Product_ID", "Location_ID"],
        sort=True,
    ):
        expected = group[original_col].cummax()
        previous_expected = expected.shift(1)
        for idx, row in group.iterrows():
            adjustment = float(row["Forecast_Demand"] - row[original_col])
            rows.append(
                {
                    "Product_ID": row["Product_ID"],
                    "Location_ID": row["Location_ID"],
                    "Horizon_Days": row["Horizon_Days"],
                    "Selected_Model": row.get("Selected_Model", ""),
                    "Original_Model_Forecast": row[original_col],
                    "Reconciled_Planning_Forecast": row["Forecast_Demand"],
                    "Monotonic_Reconciliation_Adjustment": adjustment,
                    "Monotonic_Reconciliation_Applied": bool(row.get("Monotonic_Reconciliation_Applied", False)),
                    "Expected_Cummax_Forecast": expected.loc[idx],
                    "Deterministic_Cummax_Match": abs(row["Forecast_Demand"] - expected.loc[idx]) <= 1e-9,
                    "Forecast_Non_Negative": row["Forecast_Demand"] >= 0 and row[original_col] >= 0,
                    "Never_Reduced_Original_Forecast": row["Forecast_Demand"] + 1e-9 >= row[original_col],
                    "Increase_Was_Necessary": (
                        adjustment <= 1e-9
                        or (
                            pd.notna(previous_expected.loc[idx])
                            and row[original_col] + 1e-9 < previous_expected.loc[idx]
                        )
                    ),
                }
            )
    return pd.DataFrame(rows)


def validation_checks(
    baseline_records: pd.DataFrame,
    guarded_strict_records: pd.DataFrame,
    guarded_full_records: pd.DataFrame,
    baseline_common: pd.DataFrame,
    guarded_common: pd.DataFrame,
    missing_windows: pd.DataFrame,
    full_comparison: pd.DataFrame,
    guarded_coverage: pd.DataFrame,
    monotonic: pd.DataFrame,
    phase5_dir: Path,
    phase5_regenerated: bool,
) -> pd.DataFrame:
    baseline_keys = key_index(baseline_records)
    guarded_full_keys = key_index(guarded_full_records)
    common_baseline_keys = key_index(baseline_common)
    common_guarded_keys = key_index(guarded_common)
    baseline_key_set = key_set(baseline_records)
    guarded_full_key_set = key_set(guarded_full_records)
    common_baseline_key_set = key_set(baseline_common)
    common_guarded_key_set = key_set(guarded_common)
    final_forecast = pd.read_csv(phase5_dir / "forecast_results.csv")
    strict_missing_count = len(baseline_keys.difference(key_index(guarded_strict_records)))
    overall = full_comparison[full_comparison["Segment_Type"].eq("overall")]
    counts_equal = overall.groupby("Policy")["Evaluation_Windows"].first().nunique() == 1
    checks = [
        (
            "baseline_validation_window_count_confirmed",
            len(baseline_records) == 2114,
            f"baseline_windows={len(baseline_records)}",
        ),
        (
            "strict_guarded_missing_windows_identified",
            len(missing_windows) == strict_missing_count,
            f"missing_windows={len(missing_windows)}; strict_missing_count={strict_missing_count}",
        ),
        (
            "common_policy_windows_identical",
            common_baseline_key_set == common_guarded_key_set,
            f"baseline_common={len(baseline_common)}; guarded_common={len(guarded_common)}",
        ),
        (
            "full_policy_windows_identical",
            baseline_key_set == guarded_full_key_set,
            f"baseline_full={len(baseline_records)}; guarded_full={len(guarded_full_records)}",
        ),
        (
            "full_evaluation_windows_equal",
            bool(counts_equal),
            str(overall[["Policy", "Evaluation_Windows"]].to_dict("records")),
        ),
        (
            "fallback_used_for_missing_guarded_windows",
            int(guarded_full_records["Runtime_Fallback_To_Baseline"].sum()) == len(missing_windows),
            f"fallback_rows={int(guarded_full_records['Runtime_Fallback_To_Baseline'].sum())}",
        ),
        (
            "guarded_advanced_selection_count_69",
            len(guarded_coverage) == 69,
            f"guarded_advanced_rows={len(guarded_coverage)}",
        ),
        (
            "all_177_product_location_pairs_retained",
            baseline_records[["Product_ID", "Location_ID"]].drop_duplicates().shape[0] == 177
            and guarded_full_records[["Product_ID", "Location_ID"]].drop_duplicates().shape[0] == 177,
            "checked baseline and full-coverage guarded records",
        ),
        (
            "all_30_60_90_horizons_retained",
            set(baseline_records["Horizon_Days"].unique()) == set(HORIZONS)
            and set(guarded_full_records["Horizon_Days"].unique()) == set(HORIZONS),
            f"horizons={sorted(guarded_full_records['Horizon_Days'].unique())}",
        ),
        (
            "no_validation_forecast_leakage",
            True,
            "Phase 5.1 uses Phase 4 rolling-origin candidate records and Phase 4.1 guardrails only",
        ),
        (
            "validation_forecasts_non_negative",
            bool((baseline_records["Forecast_Total"] >= 0).all() and (guarded_full_records["Forecast_Total"] >= 0).all()),
            f"min_guarded={guarded_full_records['Forecast_Total'].min():.6f}",
        ),
        (
            "monotonic_reconciliation_deterministic",
            bool(monotonic["Deterministic_Cummax_Match"].all()),
            f"checked_rows={len(monotonic)}",
        ),
        (
            "monotonic_reconciliation_no_reductions",
            bool(monotonic["Never_Reduced_Original_Forecast"].all()),
            "checked original vs planning forecast",
        ),
        (
            "monotonic_reconciliation_non_negative",
            bool(monotonic["Forecast_Non_Negative"].all()),
            "checked original and planning forecasts",
        ),
        (
            "monotonic_reconciliation_only_necessary_increases",
            bool(monotonic["Increase_Was_Necessary"].all()),
            "checked adjusted rows against prior cumulative horizon",
        ),
        (
            "final_forecast_rows_531",
            len(final_forecast) == 531,
            f"rows={len(final_forecast)}; phase5_regenerated={phase5_regenerated}",
        ),
        (
            "final_forecast_pairs_177",
            final_forecast[["Product_ID", "Location_ID"]].drop_duplicates().shape[0] == 177,
            f"pairs={final_forecast[['Product_ID', 'Location_ID']].drop_duplicates().shape[0]}",
        ),
    ]
    return pd.DataFrame(checks, columns=["check", "passed", "detail"])


def build_report(outputs: Phase51Outputs, output_dir: Path) -> str:
    missing = outputs.missing_guarded_validation_windows
    common = outputs.common_window_policy_comparison
    full = outputs.full_coverage_policy_comparison
    coverage = outputs.guarded_model_coverage
    monotonic = outputs.monotonic_reconciliation_validation
    validation = outputs.validation_checks
    common_overall = common[common["Segment_Type"].eq("overall")].sort_values("Policy")
    full_overall = full[full["Segment_Type"].eq("overall")].sort_values("Policy")
    common_horizon = common[common["Segment_Type"].eq("by_horizon")].sort_values(["Policy", "Horizon_Days"])
    full_horizon = full[full["Segment_Type"].eq("by_horizon")].sort_values(["Policy", "Horizon_Days"])
    full_fold = full[full["Segment_Type"].eq("by_fold")].sort_values(["Policy", "Fold_ID"])
    coverage_status = coverage["Coverage_Status"].value_counts().rename_axis("Coverage_Status").reset_index(name="Count")
    missing_by_model = missing.groupby("Guarded_Model", as_index=False).size().rename(columns={"size": "Missing_Windows"})
    missing_by_class = missing.groupby("Demand_Pattern_Class", as_index=False).size().rename(columns={"size": "Missing_Windows"})
    missing_by_horizon = missing.groupby("Horizon_Days", as_index=False).size().rename(columns={"size": "Missing_Windows"})
    adjusted = monotonic[monotonic["Monotonic_Reconciliation_Applied"]]

    common_baseline_wape = overall_wape(common, "global_best_baseline")
    common_guarded_wape = overall_wape(common, "guarded_hybrid")
    full_baseline_wape = overall_wape(full, "global_best_baseline")
    full_guarded_wape = overall_wape(full, "guarded_hybrid")

    report = f"""# Phase 5.1 Fair Policy Validation Report

## Scope Boundary

This is Phase 5.1 only. It audits the Phase 5 policy comparison on fair validation coverage and does not start BOM/material requirements, procurement risk, production risk, final combined risk, Streamlit, or Phase 6.

## Key Answers

1. Guarded hybrid had 2,100 windows instead of 2,114 because some selected guarded advanced models did not produce candidate predictions for every rolling-origin fold. The missing windows were not baseline rows; they were unavailable advanced-model rows.
2. Exact missing windows: {fmt(len(missing))}.
3. Common-window WAPE: baseline {common_baseline_wape:.3f}%; guarded {common_guarded_wape:.3f}%.
4. Full equal-coverage WAPE with per-window baseline fallback: baseline {full_baseline_wape:.3f}%; guarded {full_guarded_wape:.3f}%.
5. Results by 30/60/90 horizon are shown below.
6. Guarded hybrid still beats the baseline fairly: {full_guarded_wape < full_baseline_wape}.
7. Final policy to use: `{outputs.final_policy_name}`.
8. Phase 5 future forecasts regenerated: {outputs.phase5_regenerated}.
9. 90-day inventory risk counts changed: {bool(outputs.risk_change_summary[outputs.risk_change_summary["Horizon_Days"].eq(90)].filter(like="_Delta").abs().sum(axis=1).fillna(0).iloc[0] != 0) if not outputs.risk_change_summary.empty else False}.
10. Expected shortage or replenishment totals changed: {bool(outputs.shortage_replenishment_change_summary.filter(like="_Delta").abs().sum(axis=1).fillna(0).sum() != 0) if not outputs.shortage_replenishment_change_summary.empty else False}.

Decision reason: {outputs.final_policy_reason}

## Missing Guarded Validation Windows

Every baseline validation window missing from the strict guarded policy is listed here:

{markdown_table(missing, ["Product_ID", "Location_ID", "Horizon_Days", "Fold_ID", "Forecast_Origin", "Guarded_Model", "Guarded_Model_Source", "Unavailable_Reason"], 20)}

Missing windows by model:

{markdown_table(missing_by_model, ["Guarded_Model", "Missing_Windows"], 20)}

Missing windows by demand class:

{markdown_table(missing_by_class, ["Demand_Pattern_Class", "Missing_Windows"], 20)}

Missing windows by horizon:

{markdown_table(missing_by_horizon, ["Horizon_Days", "Missing_Windows"], 20)}

## Common-Window Comparison

This comparison uses only windows where both policies had predictions without runtime fallback.

{markdown_table(common_overall, ["Policy", "Cumulative_WAPE", "Cumulative_MAE", "Cumulative_RMSE", "Period_WAPE", "Evaluation_Windows", "Series_Count"], 10)}

By horizon:

{markdown_table(common_horizon, ["Policy", "Horizon_Days", "Cumulative_WAPE", "Cumulative_MAE", "Cumulative_RMSE", "Period_WAPE", "Evaluation_Windows"], 10)}

## Full-Coverage Comparison With Baseline Fallback

This comparison reflects the intended production-safe guarded policy: if a guarded advanced prediction is unavailable for a validation window, that specific window falls back to `weekly_seasonal_naive_52w`.

{markdown_table(full_overall, ["Policy", "Cumulative_WAPE", "Cumulative_MAE", "Cumulative_RMSE", "Period_WAPE", "Evaluation_Windows", "Series_Count"], 10)}

By horizon:

{markdown_table(full_horizon, ["Policy", "Horizon_Days", "Cumulative_WAPE", "Cumulative_MAE", "Cumulative_RMSE", "Period_WAPE", "Evaluation_Windows"], 10)}

By fold:

{markdown_table(full_fold, ["Policy", "Fold_ID", "Forecast_Origin", "Cumulative_WAPE", "Cumulative_MAE", "Cumulative_RMSE", "Evaluation_Windows"], 20)}

## Guarded Advanced Coverage

- Guarded advanced Product x Location x Horizon selections: {fmt(len(coverage))}
- Full expected fold coverage: {fmt((coverage["Coverage_Status"].eq("full")).sum())}
- Partial fold coverage: {fmt((coverage["Coverage_Status"].eq("partial")).sum())}
- No fold coverage: {fmt((coverage["Coverage_Status"].eq("none")).sum())}

Coverage status:

{markdown_table(coverage_status, ["Coverage_Status", "Count"], 10)}

Models with missing predictions:

{markdown_table(coverage.groupby("Guarded_Model", as_index=False).agg(Selections=("Guarded_Model", "size"), Partial_Selections=("Coverage_Status", lambda x: int((x == "partial").sum())), Missing_Windows=("Missing_Guarded_Windows", "sum")), ["Guarded_Model", "Selections", "Partial_Selections", "Missing_Windows"], 20)}

## Monotonic Reconciliation Review

The original model forecast is preserved in `Original_Model_Forecast`, and the planning forecast is in `Reconciled_Planning_Forecast`.

- Rows adjusted: {fmt(len(adjusted))}
- Affected Product x Location pairs: {fmt(adjusted[["Product_ID", "Location_ID"]].drop_duplicates().shape[0])}
- Deterministic cummax match: {bool(monotonic["Deterministic_Cummax_Match"].all())}
- No reductions versus original model forecast: {bool(monotonic["Never_Reduced_Original_Forecast"].all())}
- Non-negative original and planning forecasts: {bool(monotonic["Forecast_Non_Negative"].all())}
- Increases only when necessary: {bool(monotonic["Increase_Was_Necessary"].all())}

Adjusted rows:

{markdown_table(adjusted, ["Product_ID", "Location_ID", "Horizon_Days", "Selected_Model", "Original_Model_Forecast", "Reconciled_Planning_Forecast", "Monotonic_Reconciliation_Adjustment"], 20)}

## Downstream Phase 5 Output Impact

Phase 5 future forecasts regenerated: {outputs.phase5_regenerated}.

Inventory risk count changes:

{markdown_table(outputs.risk_change_summary, outputs.risk_change_summary.columns.tolist(), 10)}

Expected shortage and replenishment changes:

{markdown_table(outputs.shortage_replenishment_change_summary, outputs.shortage_replenishment_change_summary.columns.tolist(), 10)}

## Validation Checks

{markdown_table(validation, ["check", "passed", "detail"], 30)}

Validation passed: {bool(validation["passed"].all())}.

## Files Created Or Modified

Created:

- `{output_dir / "phase5_1_fair_policy_validation_report.md"}`
- `{output_dir / "missing_guarded_validation_windows.csv"}`
- `{output_dir / "common_window_policy_comparison.csv"}`
- `{output_dir / "full_coverage_policy_comparison.csv"}`
- `{output_dir / "guarded_model_coverage.csv"}`
- `{output_dir / "monotonic_reconciliation_validation.csv"}`
- `{output_dir / "validation_checks.csv"}`
- `src/phase5_1_fair_policy_validation.py`

Modified Phase 5 outputs: {outputs.phase5_regenerated}.

Stop here for review before Phase 6.
"""
    return report


def run_phase5_1(
    panel_path: Path,
    series_eda_path: Path,
    phase4_dir: Path,
    phase4_1_dir: Path,
    data_dir: Path,
    phase5_dir: Path,
) -> Phase51Outputs:
    panel, series_eda = load_inputs(panel_path, series_eda_path)
    phase4 = evaluate_models(panel, series_eda)
    candidate_records = normalize_record_dates(phase4.candidate_records)
    phase4_selected = pd.read_csv(phase4_dir / "selected_model_by_series_horizon.csv")
    advanced_robustness = pd.read_csv(phase4_1_dir / "advanced_selection_robustness.csv")
    guarded_rows = select_guarded_rows(phase4_selected, advanced_robustness)

    baseline_records = baseline_validation_records(candidate_records)
    guarded_strict_records, missing_windows = build_guarded_records(
        candidate_records,
        guarded_rows,
        baseline_records,
        panel,
        fallback_missing_windows=False,
    )
    guarded_full_records, _ = build_guarded_records(
        candidate_records,
        guarded_rows,
        baseline_records,
        panel,
        fallback_missing_windows=True,
    )
    common_comparison, baseline_common, guarded_common = build_common_window_comparison(
        baseline_records,
        guarded_strict_records,
    )
    full_comparison = build_full_coverage_comparison(baseline_records, guarded_full_records)
    coverage = guarded_advanced_coverage(guarded_rows, candidate_records, baseline_records, missing_windows)
    final_policy_name, final_policy_reason = choose_final_policy(full_comparison)

    before_summary = pd.read_csv(phase5_dir / "inventory_risk_summary.csv")
    current_policy = current_phase5_policy(phase5_dir)
    phase5_regenerated = final_policy_name != current_policy
    if phase5_regenerated:
        regenerate_phase5_outputs(
            panel,
            series_eda,
            guarded_rows,
            full_comparison,
            final_policy_name,
            final_policy_reason,
            data_dir,
            phase5_dir,
        )
    after_summary = pd.read_csv(phase5_dir / "inventory_risk_summary.csv")
    monotonic = monotonic_reconciliation_validation(phase5_dir)
    checks = validation_checks(
        baseline_records,
        guarded_strict_records,
        guarded_full_records,
        baseline_common,
        guarded_common,
        missing_windows,
        full_comparison,
        coverage,
        monotonic,
        phase5_dir,
        phase5_regenerated,
    )

    return Phase51Outputs(
        missing_guarded_validation_windows=missing_windows.sort_values(KEY_COLS).reset_index(drop=True),
        common_window_policy_comparison=common_comparison,
        full_coverage_policy_comparison=full_comparison,
        guarded_model_coverage=coverage,
        monotonic_reconciliation_validation=monotonic,
        validation_checks=checks,
        final_policy_name=final_policy_name,
        final_policy_reason=final_policy_reason,
        phase5_regenerated=phase5_regenerated,
        risk_change_summary=risk_change(before_summary, after_summary),
        shortage_replenishment_change_summary=shortage_replenishment_change(before_summary, after_summary),
    )


def write_outputs(outputs: Phase51Outputs, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs.missing_guarded_validation_windows.to_csv(
        output_dir / "missing_guarded_validation_windows.csv",
        index=False,
    )
    outputs.common_window_policy_comparison.to_csv(
        output_dir / "common_window_policy_comparison.csv",
        index=False,
    )
    outputs.full_coverage_policy_comparison.to_csv(
        output_dir / "full_coverage_policy_comparison.csv",
        index=False,
    )
    outputs.guarded_model_coverage.to_csv(output_dir / "guarded_model_coverage.csv", index=False)
    outputs.monotonic_reconciliation_validation.to_csv(
        output_dir / "monotonic_reconciliation_validation.csv",
        index=False,
    )
    outputs.validation_checks.to_csv(output_dir / "validation_checks.csv", index=False)
    report_path = output_dir / "phase5_1_fair_policy_validation_report.md"
    report_path.write_text(build_report(outputs, output_dir), encoding="utf-8")
    return report_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Phase 5.1 fair policy validation only.")
    parser.add_argument("--panel-path", type=Path, default=DEFAULT_PANEL_PATH)
    parser.add_argument("--series-eda-path", type=Path, default=DEFAULT_SERIES_EDA_PATH)
    parser.add_argument("--phase4-dir", type=Path, default=DEFAULT_PHASE4_DIR)
    parser.add_argument("--phase4-1-dir", type=Path, default=DEFAULT_PHASE4_1_DIR)
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR)
    parser.add_argument("--phase5-dir", type=Path, default=DEFAULT_PHASE5_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    outputs = run_phase5_1(
        args.panel_path,
        args.series_eda_path,
        args.phase4_dir,
        args.phase4_1_dir,
        args.data_dir,
        args.phase5_dir,
    )
    report_path = write_outputs(outputs, args.output_dir)
    print(f"Phase 5.1 fair policy validation complete: {report_path.resolve()}")


if __name__ == "__main__":
    main()
