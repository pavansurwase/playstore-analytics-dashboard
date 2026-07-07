"""
tasks.py
--------
One builder per internship task. Each function takes the cleaned apps frame
and returns (figure, info) where `info` carries the row count after filtering
plus any notes to surface in the UI. Time-gating lives in the Streamlit layer;
these builders always produce the figure so they can be unit-tested and
screenshotted.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from data_prep import (display_category, add_display_labels, build_geo_frame,
                       load_geojson)

# Shared palette
BLUE = "#4C78A8"
ORANGE = "#F58518"
GREEN = "#54A24B"
PINK = "#FF4FA3"
GREY = "#BAB0AC"


# --------------------------------------------------------------------------- #
# Task 1 — Grouped bar: avg rating vs total reviews, top 10 categories
# --------------------------------------------------------------------------- #
def task1(apps: pd.DataFrame):
    df = apps.copy()
    mask = (df["Size_MB"] >= 10) & (df["Update_Month"] == 1)
    df = df[mask].dropna(subset=["Category", "Rating", "Reviews", "Installs"])

    grp = (
        df.groupby("Category")
        .agg(avg_rating=("Rating", "mean"),
             total_reviews=("Reviews", "sum"),
             total_installs=("Installs", "sum"))
        .reset_index()
    )
    grp = grp[grp["avg_rating"] >= 4.0]
    grp = grp.sort_values("total_installs", ascending=False).head(10)
    grp["avg_rating"] = grp["avg_rating"].round(2)
    grp["Label"] = grp["Category"].map(display_category)

    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Bar(x=grp["Label"], y=grp["avg_rating"], name="Avg Rating",
                         marker_color=BLUE, text=grp["avg_rating"],
                         textposition="outside"), secondary_y=False)
    fig.add_trace(go.Bar(x=grp["Label"], y=grp["total_reviews"],
                         name="Total Reviews", marker_color=ORANGE),
                  secondary_y=True)
    fig.update_layout(title="Top 10 Categories by Installs — Avg Rating vs Total Reviews",
                      barmode="group", template="plotly_white",
                      xaxis_tickangle=-40,
                      legend=dict(orientation="h", y=1.02, yanchor="bottom"))
    fig.update_yaxes(title_text="Average Rating", range=[0, 5], secondary_y=False)
    fig.update_yaxes(title_text="Total Reviews", secondary_y=True)
    return fig, {"rows": len(grp)}


# --------------------------------------------------------------------------- #
# Task 2 — Choropleth: global installs by category (simulated geography)
# --------------------------------------------------------------------------- #
def task2_top_categories(apps: pd.DataFrame):
    """Top 5 categories by installs whose name does NOT start with A/C/G/S."""
    df = apps.dropna(subset=["Category", "Installs"])
    df = df[~df["Category"].str[0].isin(list("ACGS"))]
    top = (df.groupby("Category")["Installs"].sum()
             .sort_values(ascending=False).head(5).index.tolist())
    return top


def task2(apps: pd.DataFrame, category: str | None = None):
    top = task2_top_categories(apps)
    if not top:
        return go.Figure(), {"rows": 0, "categories": []}
    category = category or top[0]

    geo = build_geo_frame(apps)
    geo = geo[geo["Category"] == category].copy()
    gj = load_geojson()

    fig = go.Figure()
    fig.add_trace(go.Choropleth(
        geojson=gj, featureidkey="id",
        locations=geo["ISO3"], z=geo["Installs"], text=geo["Country"],
        colorscale="Blues", colorbar_title="Installs",
        marker_line_color="white", marker_line_width=0.4,
        name="Installs"))

    # Highlight countries where installs exceed 1,000,000 with a bold pink
    # outline (keeps the underlying Blues fill visible rather than repainting).
    hot = geo[geo["Installs"] > 1_000_000]
    if not hot.empty:
        fig.add_trace(go.Choropleth(
            geojson=gj, featureidkey="id",
            locations=hot["ISO3"], z=hot["Installs"], text=hot["Country"],
            colorscale="Blues", showscale=False,
            marker_line_color=PINK, marker_line_width=2.2,
            hovertemplate="%{text}: %{z:,} installs (&gt;1M)<extra></extra>",
            name=">1M highlight"))

    fig.update_layout(
        title=f"Simulated Global Installs — {display_category(category)}  "
              f"(pink outline = &gt;1M installs)",
        template="plotly_white",
        geo=dict(showframe=False, showcoastlines=False, visible=False,
                 projection_type="natural earth"),
        margin=dict(l=0, r=0, t=60, b=0))
    return fig, {"rows": len(geo), "categories": top,
                 "hot": hot["Country"].tolist()}


# --------------------------------------------------------------------------- #
# Task 3 — Dual axis: avg installs & revenue, Free vs Paid, top 3 categories
# --------------------------------------------------------------------------- #
def task3(apps: pd.DataFrame):
    df = apps.copy()
    df = df.dropna(subset=["Type", "Category", "Installs"])
    df = df[df["App"].str.len() <= 30]
    df = df[df["Content Rating"] == "Everyone"]
    df = df[df["Installs"] >= 10_000]
    df = df[df["Android_Ver_Num"] > 4.0]
    df = df[df["Size_MB"] > 15]
    # Revenue >= $10k applies to paid apps only (free apps have $0 revenue by
    # definition; excluding them would make a "free vs paid" comparison empty).
    df = df[(df["Type"] == "Free") | (df["Revenue"] >= 10_000)]

    top3 = (df.groupby("Category")["Installs"].sum()
              .sort_values(ascending=False).head(3).index.tolist())
    df = df[df["Category"].isin(top3)]

    piv = (df.groupby(["Category", "Type"])
             .agg(avg_installs=("Installs", "mean"),
                  avg_revenue=("Revenue", "mean"))
             .reset_index())
    labels = [display_category(c) for c in top3]

    def series(metric, typ):
        out = []
        for c in top3:
            row = piv[(piv["Category"] == c) & (piv["Type"] == typ)]
            out.append(float(row[metric].iloc[0]) if not row.empty else 0.0)
        return out

    fig = make_subplots(specs=[[{"secondary_y": True}]])
    # avg installs -> left axis (bars)
    fig.add_trace(go.Bar(x=labels, y=series("avg_installs", "Free"),
                         name="Avg Installs (Free)", marker_color=BLUE),
                  secondary_y=False)
    fig.add_trace(go.Bar(x=labels, y=series("avg_installs", "Paid"),
                         name="Avg Installs (Paid)", marker_color="#9EC6E0"),
                  secondary_y=False)
    # avg revenue -> right axis (lines+markers)
    fig.add_trace(go.Scatter(x=labels, y=series("avg_revenue", "Free"),
                             name="Avg Revenue (Free)", mode="lines+markers",
                             marker_color=ORANGE, line=dict(width=3)),
                  secondary_y=True)
    fig.add_trace(go.Scatter(x=labels, y=series("avg_revenue", "Paid"),
                             name="Avg Revenue (Paid)", mode="lines+markers",
                             marker_color=GREEN, line=dict(width=3, dash="dot")),
                  secondary_y=True)

    fig.update_layout(title="Free vs Paid — Avg Installs & Avg Revenue (Top 3 Categories)",
                      barmode="group", template="plotly_white",
                      legend=dict(orientation="h", y=1.02, yanchor="bottom"))
    fig.update_yaxes(title_text="Average Installs", secondary_y=False)
    fig.update_yaxes(title_text="Average Revenue ($)", secondary_y=True)
    return fig, {"rows": len(df), "categories": top3}


# --------------------------------------------------------------------------- #
# Task 4 — Time series: total installs over time, by category, growth shading
# --------------------------------------------------------------------------- #
def task4(apps: pd.DataFrame):
    df = apps.dropna(subset=["Category", "Installs", "Update_Period"]).copy()
    df["_name"] = df["App"].str.lower()
    df = df[~df["_name"].str.startswith(("x", "y", "z"))]
    df = df[~df["_name"].str.contains("s")]
    df = df[df["Category"].str[0].isin(list("ECB"))]
    df = df[df["Reviews"] > 500]

    ts = (df.groupby(["Category", "Update_Period"])["Installs"]
            .sum().reset_index()
            .sort_values(["Category", "Update_Period"]))

    fig = go.Figure()
    cats = sorted(ts["Category"].unique())
    highlight_periods = set()
    for cat in cats:
        sub = ts[ts["Category"] == cat].copy()
        sub["mom"] = sub["Installs"].pct_change()
        label = display_category(cat, translate=True)
        fig.add_trace(go.Scatter(
            x=sub["Update_Period"], y=sub["Installs"], mode="lines",
            name=label, line=dict(width=2)))
        # highlight >20% MoM growth points
        hi = sub[sub["mom"] > 0.20]
        if not hi.empty:
            fig.add_trace(go.Scatter(
                x=hi["Update_Period"], y=hi["Installs"], mode="markers",
                marker=dict(size=11, symbol="diamond", color="#d62728",
                            line=dict(width=1, color="white")),
                name=f"{label} >20% MoM", showlegend=False,
                hovertemplate="%{x|%b %Y}: %{y:,} installs (>20% MoM)<extra></extra>"))
            highlight_periods.update(hi["Update_Period"].tolist())

    # shade months where any category grew >20%
    for p in highlight_periods:
        fig.add_vrect(x0=p - pd.Timedelta(days=15), x1=p + pd.Timedelta(days=15),
                      fillcolor="#d62728", opacity=0.06, line_width=0)

    fig.update_layout(title="Total Installs Over Time by Category "
                            "(red diamonds / bands = &gt;20% MoM growth)",
                      template="plotly_white", xaxis_title="Last Updated (month)",
                      yaxis_title="Total Installs",
                      legend=dict(orientation="h", y=-0.25))
    return fig, {"rows": len(df), "categories": cats}


# --------------------------------------------------------------------------- #
# Task 5 — Bubble: size vs rating, bubble=installs, sentiment filter
# --------------------------------------------------------------------------- #
_TASK5_CATS = ["GAME", "BEAUTY", "BUSINESS", "COMICS", "COMMUNICATION",
               "DATING", "ENTERTAINMENT", "SOCIAL", "EVENTS"]


def task5(apps: pd.DataFrame):
    df = apps.copy()
    df = df.dropna(subset=["Size_MB", "Rating", "Installs"])
    df = df[df["Rating"] > 3.5]
    df = df[df["Category"].isin(_TASK5_CATS)]
    df = df[df["Reviews"] > 500]
    df = df[~df["App"].str.lower().str.contains("s")]
    df = df[df["Sentiment_Subjectivity"] > 0.5]
    df = df[df["Installs"] > 50_000]
    df["Label"] = df["Category"].map(lambda c: display_category(c, translate=True))

    fig = go.Figure()
    for cat in df["Category"].unique():
        sub = df[df["Category"] == cat]
        color = PINK if cat == "GAME" else None
        fig.add_trace(go.Scatter(
            x=sub["Size_MB"], y=sub["Rating"], mode="markers",
            name=sub["Label"].iloc[0],
            marker=dict(size=sub["Installs"], sizemode="area",
                        sizeref=2.0 * df["Installs"].max() / (60.0 ** 2),
                        sizemin=4, color=color, line=dict(width=0.5, color="white")),
            text=sub["App"],
            hovertemplate="<b>%{text}</b><br>Size %{x:.0f} MB<br>"
                          "Rating %{y}<br>%{marker.size:,} installs<extra></extra>"))
    fig.update_layout(title="App Size vs Rating (bubble = installs; Game = pink)",
                      template="plotly_white", xaxis_title="Size (MB)",
                      yaxis_title="Average Rating",
                      legend=dict(orientation="h", y=-0.25))
    return fig, {"rows": len(df)}


# --------------------------------------------------------------------------- #
# Task 6 — Stacked area: cumulative installs over time per category
# --------------------------------------------------------------------------- #
def task6(apps: pd.DataFrame):
    df = apps.dropna(subset=["Category", "Installs", "Update_Period"]).copy()
    df = df[df["Rating"] >= 4.2]
    df = df[~df["App"].str.contains(r"\d", regex=True)]
    df = df[df["Category"].str[0].isin(list("TP"))]
    df = df[df["Reviews"] > 1000]
    df = df[(df["Size_MB"] >= 20) & (df["Size_MB"] <= 80)]

    ts = (df.groupby(["Category", "Update_Period"])["Installs"]
            .sum().reset_index()
            .sort_values(["Category", "Update_Period"]))

    fig = go.Figure()
    cats = sorted(ts["Category"].unique())
    for cat in cats:
        sub = ts[ts["Category"] == cat].copy()
        sub["cum"] = sub["Installs"].cumsum()
        sub["mom"] = sub["Installs"].pct_change()
        label = display_category(cat, translate=True)
        fig.add_trace(go.Scatter(
            x=sub["Update_Period"], y=sub["cum"], mode="lines",
            name=label, stackgroup="one", line=dict(width=0.5)))
        # intensify: mark months with >25% MoM growth
        hi = sub[sub["mom"] > 0.25]
        if not hi.empty:
            fig.add_trace(go.Scatter(
                x=hi["Update_Period"], y=hi["cum"], mode="markers",
                marker=dict(size=9, color="#111", symbol="circle",
                            line=dict(width=1, color="white")),
                name=f"{label} >25% MoM", showlegend=False,
                hovertemplate="%{x|%b %Y}: cumulative %{y:,} (>25% MoM)<extra></extra>"))

    fig.update_layout(title="Cumulative Installs Over Time by Category "
                            "(dots = &gt;25% MoM growth months)",
                      template="plotly_white", xaxis_title="Last Updated (month)",
                      yaxis_title="Cumulative Installs",
                      legend=dict(orientation="h", y=-0.25))
    return fig, {"rows": len(df), "categories": cats}


TASKS = {1: task1, 2: task2, 3: task3, 4: task4, 5: task5, 6: task6}
