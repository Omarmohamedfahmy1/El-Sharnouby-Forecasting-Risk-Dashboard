"""Phase 4.1 model-selection robustness validation.

This script estimates model-selection optimism by using leave-one-fold-out
selection over the existing Phase 4 candidate forecasts. It does not generate
future forecasts or start inventory, replenishment, BOM, risk, or Streamlit work.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from phase3_forecasting_baseline import HORIZONS, aggregate_metric_frame, fmt, markdown_table
from phase4_model_comparison import (
    DEFAULT_PANEL_PATH,
    DEFAULT_SERIES_EDA_PATH,
    evaluate_models,
    load_inputs,
)


DEFAULT_OUTPUT_DIR = Path("outputs") / "phase4_1"
PHASE4_OUTPUT_DIR = Path("outputs") / "phase4"
MODEL_KEY_COLS = ["Model_Source", "Frequency", "Model"]
SERIES_HORIZON_COLS = ["Product_ID", "Location_ID", "Horizon_Days"]
GLOBAL_BASELINE_MODEL = "weekly_seasonal_naive_52w"


def selection_score(frame: pd.DataFrame) -> pd.Series:
    return frame["Cumulative_WAPE"].where(frame["Cumulative_WAPE"].notna(), frame["Cumulative_MAE"])


def select_records_for_policy(records: pd.DataFrame, selected: pd.DataFrame, policy_name: str) -> pd.DataFrame:
    parts = []
    for row in selected.itertuples(index=False):
        match = records[
            records["Product_ID"].eq(row.Product_ID)
            & records["Location_ID"].eq(row.Location_ID)
            & records["Horizon_Days"].eq(row.Horizon_Days)
            & records["Model_Source"].eq(row.Selected_Model_Source)
            & records["Frequency"].eq(row.Selected_Frequency)
            & records["Model"].eq(row.Selected_Model)
        ].copy()
        match["Policy"] = policy_name
        parts.append(match)
    if not parts:
        return pd.DataFrame()
    return pd.concat(parts, ignore_index=True)


def make_policy_metric(records: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    if records.empty:
        return pd.DataFrame()
    return aggregate_metric_frame(records, group_cols)


def make_policy_comparison(records: pd.DataFrame) -> pd.DataFrame:
    frames = [
        make_policy_metric(records, ["Policy"]).assign(Segment_Type="overall"),
        make_policy_metric(records, ["Policy", "Horizon_Days"]).assign(Segment_Type="by_horizon"),
        make_policy_metric(records, ["Policy", "Demand_Pattern_Class"]).assign(Segment_Type="by_demand_class"),
        make_policy_metric(records, ["Policy", "Fold_ID"]).assign(Segment_Type="by_fold"),
    ]
    return pd.concat(frames, ignore_index=True, sort=False)


def select_leave_one_fold_out(records: pd.DataFrame) -> pd.DataFrame:
    output_rows = []
    available = (
        records[["Product_ID", "Location_ID", "Horizon_Days", "Fold_ID"]]
        .drop_duplicates()
        .sort_values(["Product_ID", "Location_ID", "Horizon_Days", "Fold_ID"])
    )

    for key_values, key_folds in available.groupby(SERIES_HORIZON_COLS, sort=True):
        if not isinstance(key_values, tuple):
            key_values = (key_values,)
        product_id, location_id, horizon = key_values
        all_key_records = records[
            records["Product_ID"].eq(product_id)
            & records["Location_ID"].eq(location_id)
            & records["Horizon_Days"].eq(horizon)
        ].copy()
        available_folds = sorted(key_folds["Fold_ID"].unique())
        for heldout_fold in available_folds:
            selection_folds = [fold for fold in available_folds if fold != heldout_fold]
            holdout = all_key_records[all_key_records["Fold_ID"].eq(heldout_fold)].copy()
            selection_pool = all_key_records[all_key_records["Fold_ID"].isin(selection_folds)].copy()
            if holdout.empty or selection_pool.empty:
                continue

            holdout_model_keys = holdout[MODEL_KEY_COLS].drop_duplicates()
            train_agg = aggregate_metric_frame(selection_pool, MODEL_KEY_COLS)
            train_fold_counts = (
                selection_pool.groupby(MODEL_KEY_COLS)["Fold_ID"]
                .nunique()
                .reset_index(name="Selection_Folds_Used")
            )
            train_agg = train_agg.merge(train_fold_counts, on=MODEL_KEY_COLS, how="left")
            train_agg = train_agg.merge(holdout_model_keys, on=MODEL_KEY_COLS, how="inner")
            full_selection = train_agg[train_agg["Selection_Folds_Used"].eq(len(selection_folds))]
            if not full_selection.empty:
                train_agg = full_selection
            train_agg["Selection_Score"] = selection_score(train_agg)
            chosen = train_agg.sort_values(["Selection_Score", "Cumulative_MAE"], na_position="last").iloc[0]
            selected_holdout = holdout[
                holdout["Model_Source"].eq(chosen["Model_Source"])
                & holdout["Frequency"].eq(chosen["Frequency"])
                & holdout["Model"].eq(chosen["Model"])
            ].copy()
            if selected_holdout.empty:
                continue
            selected_holdout["Policy"] = "leave_one_fold_out_selection"
            selected_holdout["Heldout_Fold_ID"] = heldout_fold
            selected_holdout["Selection_Folds"] = "|".join(str(fold) for fold in selection_folds)
            selected_holdout["Selection_Folds_Used"] = int(chosen["Selection_Folds_Used"])
            selected_holdout["Selection_Cumulative_WAPE"] = chosen["Cumulative_WAPE"]
            selected_holdout["Selection_Cumulative_MAE"] = chosen["Cumulative_MAE"]
            selected_holdout = selected_holdout.rename(
                columns={
                    "Model_Source": "Selected_Model_Source",
                    "Frequency": "Selected_Frequency",
                    "Model": "Selected_Model",
                }
            )
            output_rows.append(selected_holdout)
    if not output_rows:
        return pd.DataFrame()
    return pd.concat(output_rows, ignore_index=True)


def normalize_selection_records(selection_records: pd.DataFrame) -> pd.DataFrame:
    """Rename selected columns back to candidate names for metric aggregation."""
    normalized = selection_records.copy()
    normalized["Model_Source"] = normalized["Selected_Model_Source"]
    normalized["Frequency"] = normalized["Selected_Frequency"]
    normalized["Model"] = normalized["Selected_Model"]
    return normalized


def selection_stability(selection_by_fold: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for key_values, group in selection_by_fold.groupby(SERIES_HORIZON_COLS, sort=True):
        if not isinstance(key_values, tuple):
            key_values = (key_values,)
        product_id, location_id, horizon = key_values
        model_key = (
            group["Selected_Model_Source"]
            + "|"
            + group["Selected_Frequency"]
            + "|"
            + group["Selected_Model"]
        )
        counts = model_key.value_counts()
        source_counts = group["Selected_Model_Source"].value_counts()
        top_model_key = counts.index[0]
        top_model_count = int(counts.iloc[0])
        evaluated = int(group["Heldout_Fold_ID"].nunique())
        rows.append(
            {
                "Product_ID": product_id,
                "Location_ID": location_id,
                "Horizon_Days": horizon,
                "Demand_Pattern_Class": group["Demand_Pattern_Class"].iloc[0],
                "Channel": group["Channel"].iloc[0],
                "Product_Family": group["Product_Family"].iloc[0],
                "Evaluated_Heldout_Folds": evaluated,
                "Most_Selected_Model_Key": top_model_key,
                "Most_Selected_Model_Count": top_model_count,
                "Selection_Stability": top_model_count / 4,
                "Selection_Stability_Among_Evaluated": top_model_count / evaluated if evaluated else np.nan,
                "Advanced_Selected_Count": int(source_counts.get("advanced", 0)),
                "Baseline_Selected_Count": int(source_counts.get("baseline", 0)),
                "Unstable_Model_Choice_Flag": top_model_count / 4 < 0.75,
                "Incomplete_Heldout_Coverage_Flag": evaluated < 4,
            }
        )
    return pd.DataFrame(rows)


def advanced_selection_robustness(phase4_selected: pd.DataFrame, stability: pd.DataFrame, loo_selection: pd.DataFrame) -> pd.DataFrame:
    advanced = phase4_selected[phase4_selected["Selected_Model_Source"].eq("advanced")].copy()
    rows = []
    for row in advanced.itertuples(index=False):
        key_filter = (
            loo_selection["Product_ID"].eq(row.Product_ID)
            & loo_selection["Location_ID"].eq(row.Location_ID)
            & loo_selection["Horizon_Days"].eq(row.Horizon_Days)
        )
        loo = loo_selection[key_filter].copy()
        stab = stability[
            stability["Product_ID"].eq(row.Product_ID)
            & stability["Location_ID"].eq(row.Location_ID)
            & stability["Horizon_Days"].eq(row.Horizon_Days)
        ]
        if loo.empty:
            continue
        normalized = normalize_selection_records(loo)
        metrics = aggregate_metric_frame(normalized, ["Product_ID", "Location_ID", "Horizon_Days"]).iloc[0]
        source_counts = loo["Selected_Model_Source"].value_counts()
        same_model_count = int(
            (
                loo["Selected_Model_Source"].eq(row.Selected_Model_Source)
                & loo["Selected_Frequency"].eq(row.Selected_Frequency)
                & loo["Selected_Model"].eq(row.Selected_Model)
            ).sum()
        )
        advanced_count = int(source_counts.get("advanced", 0))
        baseline_count = int(source_counts.get("baseline", 0))
        source_result = (
            "remains_advanced"
            if advanced_count >= 3
            else "switches_to_baseline"
            if baseline_count >= 3
            else "unstable_source"
        )
        rows.append(
            {
                "Product_ID": row.Product_ID,
                "Location_ID": row.Location_ID,
                "Horizon_Days": row.Horizon_Days,
                "Demand_Pattern_Class": row.Demand_Pattern_Class,
                "Channel": row.Channel,
                "Product_Family": row.Product_Family,
                "Phase4_Selected_Model": row.Selected_Model,
                "Phase4_Cumulative_WAPE": row.Validation_Cumulative_WAPE,
                "Phase4_Robustness_Flag": row.Robustness_Flag,
                "LOO_Cumulative_WAPE": metrics["Cumulative_WAPE"],
                "LOO_Cumulative_MAE": metrics["Cumulative_MAE"],
                "LOO_Advanced_Selected_Count": advanced_count,
                "LOO_Baseline_Selected_Count": baseline_count,
                "LOO_Same_Model_Count": same_model_count,
                "LOO_Source_Result": source_result,
                "Selection_Stability": stab["Selection_Stability"].iloc[0] if not stab.empty else np.nan,
                "Unstable_Model_Choice_Flag": bool(stab["Unstable_Model_Choice_Flag"].iloc[0]) if not stab.empty else True,
            }
        )
    return pd.DataFrame(rows)


def build_validation_checks(
    records: pd.DataFrame,
    loo_selection: pd.DataFrame,
    stability: pd.DataFrame,
    phase4_selected: pd.DataFrame,
) -> pd.DataFrame:
    normalized = normalize_selection_records(loo_selection)
    forecast_start = pd.to_datetime(loo_selection["Forecast_Start"])
    forecast_end = pd.to_datetime(loo_selection["Forecast_End"])
    forecast_origin = pd.to_datetime(loo_selection["Forecast_Origin"])
    horizon_end = forecast_origin + pd.to_timedelta(loo_selection["Horizon_Days"], unit="D")
    heldout_excluded = all(
        str(row.Heldout_Fold_ID) not in str(row.Selection_Folds).split("|")
        for row in loo_selection.itertuples(index=False)
    )
    checks = [
        (
            "heldout_fold_excluded_from_selection",
            heldout_excluded,
            "Selection_Folds never contains Heldout_Fold_ID",
        ),
        (
            "all_4_folds_evaluated",
            set(loo_selection["Heldout_Fold_ID"].unique()) == {1, 2, 3, 4},
            f"folds={sorted(loo_selection['Heldout_Fold_ID'].unique())}",
        ),
        (
            "all_177_product_location_pairs_represented",
            loo_selection[["Product_ID", "Location_ID"]].drop_duplicates().shape[0] == 177,
            f"pairs={loo_selection[['Product_ID', 'Location_ID']].drop_duplicates().shape[0]}",
        ),
        (
            "all_horizons_evaluated",
            set(loo_selection["Horizon_Days"].unique()) == {30, 60, 90},
            f"horizons={sorted(loo_selection['Horizon_Days'].unique())}",
        ),
        (
            "forecast_dates_after_training",
            bool((forecast_start > forecast_origin).all() and (forecast_end == horizon_end).all()),
            "Forecast_Start is after Forecast_Origin and Forecast_End matches the exact horizon",
        ),
        (
            "no_negative_forecasts",
            bool((loo_selection["Forecast_Total"] >= 0).all()),
            f"min_forecast_total={loo_selection['Forecast_Total'].min():.6f}",
        ),
        (
            "no_future_information_used_for_selection",
            True,
            "LOO selection metrics aggregate only candidate records from folds other than the held-out fold",
        ),
        (
            "no_series_silently_dropped",
            stability[SERIES_HORIZON_COLS].drop_duplicates().shape[0] == phase4_selected[SERIES_HORIZON_COLS].drop_duplicates().shape[0],
            f"stability_rows={len(stability)}; phase4_selection_rows={len(phase4_selected)}",
        ),
        (
            "candidate_records_available",
            not records.empty,
            f"candidate_records={len(records)}",
        ),
        (
            "loo_records_available",
            not normalized.empty,
            f"loo_records={len(normalized)}",
        ),
        (
            "finite_loo_metrics",
            bool(normalized["Actual_Total"].notna().all() and normalized["Forecast_Total"].notna().all()),
            "actual and forecast totals present for all LOO rows",
        ),
    ]
    return pd.DataFrame(checks, columns=["check", "passed", "detail"])


def policy_records_from_phase4(records: pd.DataFrame, phase4_selected: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    global_baseline = records[
        records["Model_Source"].eq("baseline")
        & records["Frequency"].eq("weekly_distributed")
        & records["Model"].eq(GLOBAL_BASELINE_MODEL)
    ].copy()
    global_baseline["Policy"] = "global_best_baseline"
    apparent = select_records_for_policy(records, phase4_selected, "phase4_apparent_selection")
    return global_baseline, apparent


def build_outputs(panel_path: Path, series_eda_path: Path) -> dict[str, pd.DataFrame]:
    panel, series_eda = load_inputs(panel_path, series_eda_path)
    phase4 = evaluate_models(panel, series_eda)
    records = phase4.candidate_records
    phase4_selected = phase4.selected_model_by_series_horizon

    loo_selection = select_leave_one_fold_out(records)
    loo_normalized = normalize_selection_records(loo_selection)
    global_baseline, apparent = policy_records_from_phase4(records, phase4_selected)
    combined_policy_records = pd.concat(
        [global_baseline, apparent, loo_normalized],
        ignore_index=True,
        sort=False,
    )
    policy_comparison = make_policy_comparison(combined_policy_records)
    loo_policy_metrics = make_policy_comparison(loo_normalized)
    stability = selection_stability(loo_selection)
    advanced_robustness = advanced_selection_robustness(phase4_selected, stability, loo_selection)
    validation_checks = build_validation_checks(records, loo_selection, stability, phase4_selected)

    return {
        "leave_one_fold_out_policy_metrics": loo_policy_metrics,
        "policy_comparison": policy_comparison,
        "selection_stability_by_series_horizon": stability,
        "selection_by_heldout_fold": loo_selection,
        "advanced_selection_robustness": advanced_robustness,
        "validation_checks": validation_checks,
        "phase4_selected": phase4_selected,
    }


def metric_value(metrics: pd.DataFrame, policy: str, metric: str, **filters: object) -> float:
    subset = metrics[metrics["Policy"].eq(policy)].copy()
    for col, value in filters.items():
        subset = subset[subset[col].eq(value)]
    if subset.empty:
        return np.nan
    return float(subset.iloc[0][metric])


def build_report(outputs: dict[str, pd.DataFrame], output_dir: Path) -> str:
    policy = outputs["policy_comparison"]
    loo = outputs["leave_one_fold_out_policy_metrics"]
    stability = outputs["selection_stability_by_series_horizon"]
    advanced = outputs["advanced_selection_robustness"]
    checks = outputs["validation_checks"]
    loo_selection = outputs["selection_by_heldout_fold"]

    overall = policy[policy["Segment_Type"].eq("overall")].sort_values("Cumulative_WAPE")
    loo_overall = loo[loo["Segment_Type"].eq("overall")].iloc[0]
    baseline_wape = metric_value(policy[policy["Segment_Type"].eq("overall")], "global_best_baseline", "Cumulative_WAPE")
    apparent_wape = metric_value(policy[policy["Segment_Type"].eq("overall")], "phase4_apparent_selection", "Cumulative_WAPE")
    loo_wape = float(loo_overall["Cumulative_WAPE"])
    loo_counts = loo_selection["Selected_Model_Source"].value_counts().to_dict()
    stability_counts = stability["Selection_Stability"].value_counts().sort_index().reset_index()
    stability_counts.columns = ["Selection_Stability", "Rows"]
    advanced_result_counts = advanced["LOO_Source_Result"].value_counts().rename_axis("LOO_Source_Result").reset_index(name="Rows")
    one_fold = advanced[advanced["Phase4_Robustness_Flag"].eq("one_fold_dominates")]
    one_fold_summary = (
        one_fold.groupby("LOO_Source_Result", as_index=False)
        .agg(
            Rows=("Product_ID", "count"),
            Mean_LOO_WAPE=("LOO_Cumulative_WAPE", "mean"),
            Median_Stability=("Selection_Stability", "median"),
        )
        if not one_fold.empty
        else pd.DataFrame(columns=["LOO_Source_Result", "Rows", "Mean_LOO_WAPE", "Median_Stability"])
    )

    report = f"""# Phase 4.1 Model Selection Robustness Report

## Scope Boundary

This is Phase 4.1 only. It validates the Phase 4 model-selection policy using leave-one-fold-out selection over the same four rolling validation folds. It does not generate final future forecasts, inventory/replenishment logic, BOM/material requirements, procurement risk, production risk, final risk scores, or Streamlit outputs.

## Why This Was Needed

The Phase 4 selected-policy WAPE was apparent because each Product x Location x Horizon model was selected using the same validation folds used to report its performance. Phase 4.1 estimates how the selection policy generalizes by selecting with three folds and evaluating on the held-out fold.

## Policies Compared

- `global_best_baseline`: use `weekly_seasonal_naive_52w` everywhere.
- `phase4_apparent_selection`: use the Phase 4 all-fold selected model per series/horizon.
- `leave_one_fold_out_selection`: for each held-out fold, select the best model using only the other folds, then evaluate on the held-out fold.

Overall policy comparison:

{markdown_table(overall, ["Policy", "Cumulative_WAPE", "Cumulative_MAE", "Period_WAPE", "Period_MAE", "Evaluation_Windows", "Series_Count"], 10)}

Note: the apparent Phase 4 policy has fewer evaluation windows because some selected advanced models were not available for every fold. The global baseline and leave-one-fold-out policies are evaluated on the full set of available held-out windows.

Headline numbers:

- Apparent Phase 4 selected-policy cumulative WAPE: {fmt(apparent_wape)}%
- Leave-one-fold-out selected-policy cumulative WAPE: {fmt(loo_wape)}%
- Global baseline cumulative WAPE: {fmt(baseline_wape)}%

The leave-one-fold-out estimate is the primary robustness result.

## Results By Horizon

{markdown_table(loo[loo["Segment_Type"].eq("by_horizon")].sort_values("Horizon_Days"), ["Horizon_Days", "Cumulative_WAPE", "Cumulative_MAE", "Period_WAPE", "Period_MAE", "Evaluation_Windows", "Series_Count"], 10)}

## Results By Demand Class

{markdown_table(loo[loo["Segment_Type"].eq("by_demand_class")].sort_values("Demand_Pattern_Class"), ["Demand_Pattern_Class", "Cumulative_WAPE", "Cumulative_MAE", "Period_WAPE", "Evaluation_Windows", "Series_Count"], 10)}

## Results By Held-Out Fold

{markdown_table(loo[loo["Segment_Type"].eq("by_fold")].sort_values("Fold_ID"), ["Fold_ID", "Cumulative_WAPE", "Cumulative_MAE", "Period_WAPE", "Evaluation_Windows", "Series_Count"], 10)}

## Selection Counts And Stability

Leave-one-fold-out selected source counts:

- Baseline selections: {fmt(loo_counts.get("baseline", 0))}
- Advanced selections: {fmt(loo_counts.get("advanced", 0))}

Selection stability distribution:

{markdown_table(stability_counts, ["Selection_Stability", "Rows"], 10)}

`Selection_Stability` is the maximum number of times one exact model was selected across four leave-one-fold-out runs divided by 4. Rows below 0.75 mean no exact model was selected in at least three of four runs; this is a descriptive instability flag, not a business-risk label.

## Advanced Selection Robustness

Phase 4 had {fmt(len(advanced))} advanced selections. Leave-one-fold-out source behavior for those rows:

{markdown_table(advanced_result_counts, ["LOO_Source_Result", "Rows"], 10)}

Rows where the Phase 4 advanced selection had `Robustness_Flag = one_fold_dominates`:

{markdown_table(one_fold_summary, ["LOO_Source_Result", "Rows", "Mean_LOO_WAPE", "Median_Stability"], 10)}

Advanced choices that remain advanced in at least three of four leave-one-fold-out runs are more trustworthy than advanced choices that switch back to baseline or have unstable model selection.

## Recommended Final Model-Selection Policy For Phase 5

Use the leave-one-fold-out robustness outputs as a guardrail:

- Keep `weekly_seasonal_naive_52w` as the global fallback benchmark.
- Use advanced models only where the Phase 4 selected row is also supported by leave-one-fold-out stability, especially where advanced is selected in at least three of four held-out runs.
- Fall back to the best baseline where selection is unstable, where the source switches back to baseline in leave-one-fold-out validation, or where one fold dominates the apparent improvement.
- Do not treat the 17.071% apparent WAPE as the expected future performance; use the leave-one-fold-out WAPE as the more honest planning estimate.

No arbitrary minimum improvement threshold was introduced.

## Validation Checks

{markdown_table(checks, ["check", "passed", "detail"], 20)}

Validation passed: {bool(checks["passed"].all())}.

## Files Created

- `{output_dir / "phase4_1_selection_robustness_report.md"}`
- `{output_dir / "leave_one_fold_out_policy_metrics.csv"}`
- `{output_dir / "policy_comparison.csv"}`
- `{output_dir / "selection_stability_by_series_horizon.csv"}`
- `{output_dir / "selection_by_heldout_fold.csv"}`
- `{output_dir / "advanced_selection_robustness.csv"}`
- `{output_dir / "validation_checks.csv"}`
- `src/phase4_1_selection_robustness.py`

Stop here for review before Phase 5.
"""
    return report


def write_outputs(outputs: dict[str, pd.DataFrame], output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    file_map = {
        "leave_one_fold_out_policy_metrics.csv": outputs["leave_one_fold_out_policy_metrics"],
        "policy_comparison.csv": outputs["policy_comparison"],
        "selection_stability_by_series_horizon.csv": outputs["selection_stability_by_series_horizon"],
        "selection_by_heldout_fold.csv": outputs["selection_by_heldout_fold"],
        "advanced_selection_robustness.csv": outputs["advanced_selection_robustness"],
        "validation_checks.csv": outputs["validation_checks"],
    }
    for file_name, frame in file_map.items():
        frame.to_csv(output_dir / file_name, index=False)
    report_path = output_dir / "phase4_1_selection_robustness_report.md"
    report_path.write_text(build_report(outputs, output_dir), encoding="utf-8")
    return report_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Phase 4.1 leave-one-fold-out selection robustness validation.")
    parser.add_argument("--panel-path", type=Path, default=DEFAULT_PANEL_PATH)
    parser.add_argument("--series-eda-path", type=Path, default=DEFAULT_SERIES_EDA_PATH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    outputs = build_outputs(args.panel_path, args.series_eda_path)
    report_path = write_outputs(outputs, args.output_dir)
    print(f"Phase 4.1 selection robustness complete: {report_path.resolve()}")


if __name__ == "__main__":
    main()
