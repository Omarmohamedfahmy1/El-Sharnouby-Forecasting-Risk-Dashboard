from __future__ import annotations

from typing import Iterable, List, Optional

import pandas as pd
import streamlit as st


RISK_ORDER = {"High": 3, "Medium": 2, "Low": 1, "Insufficient Evidence": 0}
RISK_BADGE_CLASS = {
    "High": "risk-high",
    "Medium": "risk-medium",
    "Low": "risk-low",
    "Insufficient Evidence": "risk-unknown",
}


def inject_css() -> None:
    st.markdown(
        """
        <style>
        .block-container {padding-top: 1.4rem; padding-bottom: 2.5rem;}
        .metric-card {
            border: 1px solid #d8dee8;
            border-radius: 8px;
            padding: 14px 16px;
            background: #ffffff;
            min-height: 98px;
        }
        .metric-card .label {
            color: #475569;
            font-size: 0.82rem;
            line-height: 1.25rem;
            margin-bottom: 6px;
        }
        .metric-card .value {
            color: #111827;
            font-size: 1.55rem;
            font-weight: 700;
            line-height: 2rem;
            word-break: break-word;
        }
        .metric-card .subtext {
            color: #64748b;
            font-size: 0.78rem;
            line-height: 1.1rem;
            margin-top: 4px;
        }
        .risk-badge {
            display: inline-block;
            border-radius: 999px;
            padding: 0.18rem 0.58rem;
            font-size: 0.78rem;
            font-weight: 700;
            border: 1px solid transparent;
        }
        .risk-high {background:#fee2e2; color:#991b1b; border-color:#fecaca;}
        .risk-medium {background:#fef3c7; color:#92400e; border-color:#fde68a;}
        .risk-low {background:#dcfce7; color:#166534; border-color:#bbf7d0;}
        .risk-unknown {background:#e5e7eb; color:#374151; border-color:#d1d5db;}
        .note-box {
            border: 1px solid #cbd5e1;
            border-radius: 8px;
            padding: 0.85rem 1rem;
            background: #f8fafc;
            color: #1f2937;
            margin-bottom: 1rem;
        }
        .warning-box {
            border-color: #f59e0b;
            background: #fffbeb;
        }
        .danger-box {
            border-color: #ef4444;
            background: #fef2f2;
        }
        div[data-testid="stDataFrame"] {border: 1px solid #e5e7eb; border-radius: 8px;}
        </style>
        """,
        unsafe_allow_html=True,
    )


def fmt_number(value, decimals: int = 0) -> str:
    try:
        if pd.isna(value):
            return "-"
        number = float(value)
    except Exception:
        return str(value)
    if decimals == 0:
        return f"{number:,.0f}"
    return f"{number:,.{decimals}f}"


def fmt_pct(value, decimals: int = 1) -> str:
    try:
        if pd.isna(value):
            return "-"
        number = float(value)
    except Exception:
        return str(value)
    return f"{number * 100:,.{decimals}f}%" if abs(number) <= 1 else f"{number:,.{decimals}f}%"


def kpi(label: str, value, subtext: str = "", decimals: int = 0) -> None:
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="label">{label}</div>
            <div class="value">{fmt_number(value, decimals)}</div>
            <div class="subtext">{subtext}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def risk_badge(value: str) -> str:
    label = "Insufficient Evidence" if pd.isna(value) else str(value)
    css = RISK_BADGE_CLASS.get(label, "risk-unknown")
    return f'<span class="risk-badge {css}">{label}</span>'


def note(text: str, kind: str = "note") -> None:
    css = "note-box"
    if kind == "warning":
        css += " warning-box"
    if kind == "danger":
        css += " danger-box"
    st.markdown(f'<div class="{css}">{text}</div>', unsafe_allow_html=True)


def empty_state(message: str) -> None:
    st.info(message)


def show_table(df: pd.DataFrame, columns: Iterable[str], *, height: int = 430) -> None:
    selected = [col for col in columns if col in df.columns]
    if not selected:
        empty_state("No display columns are available for this accepted output.")
        return
    st.dataframe(df[selected], width="stretch", height=height)


def csv_download(df: pd.DataFrame, filename: str, label: str = "Download CSV") -> None:
    st.download_button(
        label,
        data=df.to_csv(index=False).encode("utf-8-sig"),
        file_name=filename,
        mime="text/csv",
        disabled=df.empty,
    )


def id_label_map(df: pd.DataFrame, id_col: str, name_col: str) -> dict:
    if id_col not in df.columns:
        return {}
    cols = [id_col] + ([name_col] if name_col in df.columns else [])
    pairs = df[cols].drop_duplicates().sort_values(id_col)
    mapping = {}
    for _, row in pairs.iterrows():
        item_id = row[id_col]
        item_name = row[name_col] if name_col in pairs.columns and pd.notna(row[name_col]) else ""
        label = f"{item_id} - {item_name}" if item_name else str(item_id)
        mapping[label] = item_id
    return mapping


def multiselect_with_all(label: str, options: List[str]) -> Optional[List[str]]:
    selected = st.sidebar.multiselect(label, ["All"] + options, default=["All"])
    if not selected or "All" in selected:
        return None
    return selected


def order_risk_frame(df: pd.DataFrame, column: str) -> pd.DataFrame:
    if df.empty or column not in df.columns:
        return df
    ordered = df.copy()
    ordered["_risk_order"] = ordered[column].map(RISK_ORDER).fillna(-1)
    return ordered.sort_values("_risk_order", ascending=False).drop(columns="_risk_order")
