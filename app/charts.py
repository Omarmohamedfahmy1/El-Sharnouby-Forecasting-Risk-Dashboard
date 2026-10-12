from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


RISK_COLORS = {
    "High": "#dc2626",
    "Medium": "#f59e0b",
    "Low": "#16a34a",
    "Insufficient Evidence": "#6b7280",
}
SERIES_COLORS = ["#2563eb", "#059669", "#f97316", "#7c3aed", "#0891b2", "#be123c"]


def risk_distribution(df: pd.DataFrame, column: str, title: str):
    if df.empty or column not in df.columns:
        return None
    counts = (
        df[column]
        .fillna("Insufficient Evidence")
        .value_counts()
        .rename_axis(column)
        .reset_index(name="Rows")
    )
    order = ["High", "Medium", "Low", "Insufficient Evidence"]
    counts[column] = pd.Categorical(counts[column], categories=order, ordered=True)
    counts = counts.sort_values(column)
    fig = px.bar(
        counts,
        x=column,
        y="Rows",
        color=column,
        color_discrete_map=RISK_COLORS,
        text="Rows",
        title=title,
    )
    fig.update_layout(showlegend=False, margin=dict(l=10, r=10, t=48, b=20))
    return fig


def horizontal_bar(
    df: pd.DataFrame,
    x: str,
    y: str,
    title: str,
    *,
    color: str | None = None,
    top_n: int = 15,
):
    if df.empty or x not in df.columns or y not in df.columns:
        return None
    view = df[[x, y] + ([color] if color and color in df.columns else [])].copy()
    view = view.sort_values(x, ascending=False).head(top_n).sort_values(x)
    fig = px.bar(
        view,
        x=x,
        y=y,
        color=color if color in view.columns else None,
        orientation="h",
        title=title,
        color_discrete_sequence=SERIES_COLORS,
    )
    fig.update_layout(margin=dict(l=10, r=10, t=48, b=20), yaxis_title="")
    return fig


def vertical_bar(
    df: pd.DataFrame,
    x: str,
    y: str,
    title: str,
    *,
    color: str | None = None,
):
    if df.empty or x not in df.columns or y not in df.columns:
        return None
    fig = px.bar(
        df,
        x=x,
        y=y,
        color=color if color and color in df.columns else None,
        title=title,
        color_discrete_sequence=SERIES_COLORS,
    )
    fig.update_layout(margin=dict(l=10, r=10, t=48, b=20))
    return fig


def line_chart(
    df: pd.DataFrame,
    x: str,
    y: str,
    title: str,
    *,
    color: str | None = None,
):
    if df.empty or x not in df.columns or y not in df.columns:
        return None
    fig = px.line(
        df,
        x=x,
        y=y,
        color=color if color and color in df.columns else None,
        title=title,
        color_discrete_sequence=SERIES_COLORS,
    )
    fig.update_layout(margin=dict(l=10, r=10, t=48, b=20))
    return fig


def scatter_chart(
    df: pd.DataFrame,
    x: str,
    y: str,
    title: str,
    *,
    color: str | None = None,
    size: str | None = None,
    hover_name: str | None = None,
):
    if df.empty or x not in df.columns or y not in df.columns:
        return None
    fig = px.scatter(
        df,
        x=x,
        y=y,
        color=color if color and color in df.columns else None,
        size=size if size and size in df.columns else None,
        hover_name=hover_name if hover_name and hover_name in df.columns else None,
        title=title,
        color_discrete_map=RISK_COLORS,
        color_discrete_sequence=SERIES_COLORS,
    )
    fig.update_layout(margin=dict(l=10, r=10, t=48, b=20))
    return fig


def metric_delta_bar(rows: list[dict], title: str):
    df = pd.DataFrame(rows)
    if df.empty:
        return None
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=df["Validation WAPE"],
            y=df["Policy"],
            orientation="h",
            text=df["Validation WAPE"].map(lambda value: f"{value:.3f}%"),
            marker_color=["#2563eb", "#f97316", "#dc2626", "#16a34a"][: len(df)],
        )
    )
    fig.update_layout(
        title=title,
        xaxis_title="Validation WAPE",
        yaxis_title="",
        margin=dict(l=10, r=10, t=48, b=20),
    )
    return fig
