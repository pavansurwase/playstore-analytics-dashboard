"""
Google Play Store — Internship Analytics Dashboard
==================================================
Interactive Streamlit dashboard implementing all six internship tasks on top of
the training project's Google Play Store dataset.

Run locally:
    pip install -r requirements.txt
    streamlit run app.py
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

import streamlit as st

from data_prep import get_data
import tasks
from timegate import window_label, task_visible, now_ist

st.set_page_config(page_title="Play Store Analytics", page_icon="📊",
                   layout="wide", initial_sidebar_state="expanded")


@st.cache_data
def load():
    return get_data()


apps = load()

TASK_TITLES = {
    1: "Top Categories — Rating vs Reviews",
    2: "Global Installs Choropleth",
    3: "Free vs Paid — Installs & Revenue",
    4: "Installs Over Time by Category",
    5: "Size vs Rating Bubble Chart",
    6: "Cumulative Installs (Stacked Area)",
}

TASK_FILTERS = {
    1: "Size ≥ 10 MB · Last Updated in January · category avg rating ≥ 4.0 · "
       "top 10 categories by installs.",
    2: "Top 5 categories by installs whose name does **not** start with A/C/G/S · "
       "countries exceeding 1M installs outlined in pink. *Geography is simulated "
       "(source data has no country field).*",
    3: "App name ≤ 30 chars · Content Rating = Everyone · Installs ≥ 10,000 · "
       "Android > 4.0 · Size > 15 MB · Revenue ≥ $10,000 (paid apps) · "
       "top 3 categories by installs. *Revenue = Price × Installs.*",
    4: "Category starts with E/C/B · app name doesn't start with x/y/z and "
       "contains no letter 's' · Reviews > 500 · red markers/bands flag >20% "
       "month-over-month growth. Beauty→Hindi, Business→Tamil, Dating→German.",
    5: "Rating > 3.5 · selected categories · Reviews > 500 · name has no 's' · "
       "Sentiment Subjectivity > 0.5 · Installs > 50k · bubble = installs · "
       "Game highlighted pink. Beauty→Hindi, Business→Tamil, Dating→German.",
    6: "Avg rating ≥ 4.2 · name has no digits · category starts T/P · "
       "Reviews > 1,000 · Size 20–80 MB · dark dots flag >25% MoM growth. "
       "Travel & Local→French, Productivity→Spanish, Photography→Japanese.",
}

# --------------------------------------------------------------------------- #
# Sidebar
# --------------------------------------------------------------------------- #
st.sidebar.title("📊 Play Store Analytics")
st.sidebar.caption("Elevance Skills internship · built on the training dataset")

choice = st.sidebar.radio(
    "Task", list(TASK_TITLES.keys()),
    format_func=lambda i: f"Task {i} — {TASK_TITLES[i]}")

st.sidebar.markdown("---")
preview = st.sidebar.toggle(
    "🔓 Preview mode (ignore time windows)", value=False,
    help="Each chart is normally only visible inside its IST window. Turn this "
         "on to review every chart regardless of the current time.")
st.sidebar.caption(f"Current time: **{now_ist().strftime('%I:%M %p IST')}**")

st.sidebar.markdown("---")
st.sidebar.subheader("Dataset")
st.sidebar.write(f"Apps (cleaned): **{len(apps):,}**")
st.sidebar.write(f"Categories: **{apps['Category'].nunique()}**")
st.sidebar.write(f"With sentiment: **{apps['Sentiment_Subjectivity'].notna().sum():,}**")

# --------------------------------------------------------------------------- #
# Header + KPI strip
# --------------------------------------------------------------------------- #
st.title("Google Play Store — Analytics Dashboard")
st.markdown("Interactive analytics on 10k+ Play Store apps. Each visual is "
            "time-gated to its assigned IST window per the internship brief.")

k1, k2, k3, k4 = st.columns(4)
k1.metric("Total apps", f"{len(apps):,}")
k2.metric("Total installs", f"{apps['Installs'].sum()/1e9:.1f} B")
k3.metric("Avg rating", f"{apps['Rating'].mean():.2f}")
k4.metric("Paid apps", f"{(apps['Type']=='Paid').sum():,}")

st.markdown("---")

# --------------------------------------------------------------------------- #
# Task renderer
# --------------------------------------------------------------------------- #
st.subheader(f"Task {choice} — {TASK_TITLES[choice]}")
st.markdown(f"**Filters:** {TASK_FILTERS[choice]}")
st.caption(f"⏱ Visible only between **{window_label(choice)}**")

visible = preview or task_visible(choice)

if not visible:
    st.warning(
        f"This chart is only available between **{window_label(choice)}**. "
        f"It is now {now_ist().strftime('%I:%M %p IST')}. "
        "Enable *Preview mode* in the sidebar to view it anyway.")
else:
    if choice == 2:
        tops = tasks.task2_top_categories(apps)
        from data_prep import display_category
        sel = st.selectbox("Category", tops,
                            format_func=lambda c: display_category(c))
        fig, info = tasks.task2(apps, category=sel)
        st.plotly_chart(fig, use_container_width=True)
        st.caption(f"Top 5 (no A/C/G/S): "
                   f"{', '.join(display_category(c) for c in info['categories'])}")
    else:
        fig, info = tasks.TASKS[choice](apps)
        st.plotly_chart(fig, use_container_width=True)
        st.caption(f"Rows after filtering: **{info['rows']:,}**")

st.markdown("---")
with st.expander("ℹ️ Data notes & transformations"):
    st.markdown(
        "- **Cleaning:** sizes → MB, installs/reviews → integers, price → float, "
        "Android version → numeric, `Last Updated` → datetime; the known corrupt "
        "row (rating 19) is dropped and apps de-duplicated by name.\n"
        "- **Revenue** is derived as `Price × Installs` (source has no revenue field).\n"
        "- **Geography (Task 2)** is simulated deterministically because the "
        "dataset has no country column.\n"
        "- **Time over time (Tasks 4 & 6)** uses `Last Updated` as the only "
        "available date dimension.\n"
        "- **Sentiment subjectivity (Task 5)** is merged from "
        "`googleplaystore_user_reviews.csv` (mean per app).")
