"""
data_prep.py
------------
All data loading, cleaning and shared transformations for the
Google Play Store internship dashboard.

The raw Kaggle dataset (`googleplaystore.csv`) is messy, so every downstream
task imports its cleaned frame from here instead of re-parsing the CSV.

Structural gaps in the source data and how we handle them
---------------------------------------------------------
* No revenue column .......... derived as  Revenue = Price * Installs
* No geography/country column  simulated deterministically (see build_geo_frame)
* No install history over time  `Last Updated` is used as the time dimension,
                                since it is the only date available.
* Sentiment subjectivity ..... merged from googleplaystore_user_reviews.csv
"""

from __future__ import annotations

import os
import re
import numpy as np
import pandas as pd

# --------------------------------------------------------------------------- #
# Paths
# --------------------------------------------------------------------------- #
HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(os.path.dirname(HERE), "data")
APPS_CSV = os.path.join(DATA_DIR, "googleplaystore.csv")
REVIEWS_CSV = os.path.join(DATA_DIR, "googleplaystore_user_reviews.csv")
GEOJSON = os.path.join(DATA_DIR, "countries.geo.json")


def load_geojson():
    """World countries GeoJSON, features keyed by ISO-3 (`id`)."""
    import json
    with open(GEOJSON) as f:
        return json.load(f)


# --------------------------------------------------------------------------- #
# Cleaning helpers
# --------------------------------------------------------------------------- #
def _clean_size(value) -> float:
    """'19M' -> 19.0, '512k' -> 0.5, 'Varies with device' -> NaN (in MB)."""
    if pd.isna(value):
        return np.nan
    s = str(value).strip()
    if s.lower().startswith("varies"):
        return np.nan
    m = re.match(r"([\d.]+)\s*([kKmMgG]?)", s)
    if not m:
        return np.nan
    num = float(m.group(1))
    unit = m.group(2).lower()
    if unit == "k":
        return num / 1024.0
    if unit == "g":
        return num * 1024.0
    return num  # already MB (or unit-less)


def _clean_installs(value) -> float:
    """'10,000+' -> 10000."""
    if pd.isna(value):
        return np.nan
    s = re.sub(r"[+,]", "", str(value)).strip()
    return float(s) if s.isdigit() else np.nan


def _clean_price(value) -> float:
    """'$4.99' -> 4.99, '0' -> 0.0."""
    if pd.isna(value):
        return 0.0
    s = str(value).replace("$", "").strip()
    try:
        return float(s)
    except ValueError:
        return 0.0


def _clean_reviews(value) -> float:
    if pd.isna(value):
        return np.nan
    s = str(value).strip()
    # a few rows use '3.0M' style review counts
    m = re.match(r"([\d.]+)\s*([kKmM]?)$", s)
    if not m:
        return np.nan
    num = float(m.group(1))
    unit = m.group(2).lower()
    if unit == "k":
        return num * 1_000
    if unit == "m":
        return num * 1_000_000
    return num


def _clean_android_ver(value) -> float:
    """'4.0.3 and up' -> 4.0 ; 'Varies with device' -> NaN."""
    if pd.isna(value):
        return np.nan
    s = str(value)
    if s.lower().startswith("varies"):
        return np.nan
    m = re.search(r"(\d+)\.(\d+)", s)
    if m:
        return float(f"{m.group(1)}.{m.group(2)}")
    m = re.search(r"(\d+)", s)
    return float(m.group(1)) if m else np.nan


# --------------------------------------------------------------------------- #
# Category display + translations
# --------------------------------------------------------------------------- #
# Raw categories are UPPER_SNAKE (e.g. TRAVEL_AND_LOCAL). We keep the raw value
# for filtering and add a human-friendly display label, applying the specific
# translations the tasks require.
_TRANSLATIONS = {
    # task 4 & 5
    "BEAUTY": "सौंदर्य (Beauty)",          # Hindi
    "BUSINESS": "வணிகம் (Business)",       # Tamil
    "DATING": "Partnersuche (Dating)",     # German
    # task 6
    "TRAVEL_AND_LOCAL": "Voyage et Local (Travel & Local)",  # French
    "PRODUCTIVITY": "Productividad (Productivity)",           # Spanish
    "PHOTOGRAPHY": "写真 (Photography)",                       # Japanese
}


def display_category(raw: str, translate: bool = False) -> str:
    """Human label for a raw UPPER_SNAKE category."""
    if translate and raw in _TRANSLATIONS:
        return _TRANSLATIONS[raw]
    return raw.replace("_", " ").title()


def add_display_labels(df: pd.DataFrame, translate: bool = False) -> pd.DataFrame:
    df = df.copy()
    df["Category_Display"] = df["Category"].map(
        lambda c: display_category(c, translate=translate)
    )
    return df


# --------------------------------------------------------------------------- #
# Load + clean the apps table
# --------------------------------------------------------------------------- #
def load_apps(path: str = APPS_CSV) -> pd.DataFrame:
    df = pd.read_csv(path)

    # Drop the single well-known corrupt row (shifted columns -> Rating 19).
    df = df[pd.to_numeric(df["Rating"], errors="coerce").le(5)].copy()

    df["Rating"] = pd.to_numeric(df["Rating"], errors="coerce")
    df["Size_MB"] = df["Size"].map(_clean_size)
    df["Installs"] = df["Installs"].map(_clean_installs)
    df["Reviews"] = df["Reviews"].map(_clean_reviews)
    df["Price"] = df["Price"].map(_clean_price)
    df["Android_Ver_Num"] = df["Android Ver"].map(_clean_android_ver)
    df["Last_Updated"] = pd.to_datetime(df["Last Updated"], errors="coerce")
    df["Update_Month"] = df["Last_Updated"].dt.month
    df["Update_Period"] = df["Last_Updated"].dt.to_period("M").dt.to_timestamp()

    # Derived: revenue (only meaningful for paid apps; free apps => 0)
    df["Revenue"] = df["Price"] * df["Installs"]

    # Normalise Type (one stray '0' value in the raw file)
    df["Type"] = df["Type"].where(df["Type"].isin(["Free", "Paid"]), np.nan)

    # De-duplicate on App name keeping the row with the most reviews
    df = (
        df.sort_values("Reviews", ascending=False)
        .drop_duplicates(subset="App", keep="first")
        .reset_index(drop=True)
    )
    return df


# --------------------------------------------------------------------------- #
# Sentiment subjectivity (Task 5)
# --------------------------------------------------------------------------- #
def load_sentiment(path: str = REVIEWS_CSV) -> pd.DataFrame:
    """Mean sentiment subjectivity/polarity per app."""
    rev = pd.read_csv(path)
    rev = rev.dropna(subset=["Sentiment_Subjectivity"])
    agg = (
        rev.groupby("App")
        .agg(
            Sentiment_Subjectivity=("Sentiment_Subjectivity", "mean"),
            Sentiment_Polarity=("Sentiment_Polarity", "mean"),
        )
        .reset_index()
    )
    return agg


def merge_sentiment(apps: pd.DataFrame, path: str = REVIEWS_CSV) -> pd.DataFrame:
    sent = load_sentiment(path)
    return apps.merge(sent, on="App", how="left")


# --------------------------------------------------------------------------- #
# Simulated geography for the choropleth (Task 2)
# --------------------------------------------------------------------------- #
# The source dataset has NO country field. To build a choropleth we distribute
# each category's total installs across a fixed basket of markets using a fixed
# random seed, so the map is reproducible. This is clearly a simulation and is
# documented as such in the README and in the app UI.
_MARKETS = [
    # (name, iso3, weight)
    ("United States", "USA", 0.18), ("India", "IND", 0.16),
    ("Brazil", "BRA", 0.10), ("Indonesia", "IDN", 0.09),
    ("Russia", "RUS", 0.07), ("Germany", "DEU", 0.05),
    ("United Kingdom", "GBR", 0.05), ("Japan", "JPN", 0.04),
    ("Mexico", "MEX", 0.04), ("France", "FRA", 0.03),
    ("Canada", "CAN", 0.03), ("Australia", "AUS", 0.02),
    ("Nigeria", "NGA", 0.03), ("Turkey", "TUR", 0.02),
    ("South Korea", "KOR", 0.02), ("Spain", "ESP", 0.02),
    ("Italy", "ITA", 0.02), ("Vietnam", "VNM", 0.02),
    ("Philippines", "PHL", 0.02), ("Egypt", "EGY", 0.02),
]


def build_geo_frame(apps: pd.DataFrame, seed: int = 42) -> pd.DataFrame:
    """
    Return a long frame: one row per (Category, Country) with simulated installs.
    Total installs per category are preserved (distributed across markets).
    """
    rng = np.random.default_rng(seed)
    cat_installs = (
        apps.groupby("Category")["Installs"].sum().reset_index()
    )
    names = [m[0] for m in _MARKETS]
    isos = [m[1] for m in _MARKETS]
    base_w = np.array([m[2] for m in _MARKETS])

    rows = []
    for _, r in cat_installs.iterrows():
        # jitter the weights a little per category so the map varies
        w = base_w * rng.uniform(0.6, 1.4, size=len(base_w))
        w = w / w.sum()
        shares = (r["Installs"] * w).round().astype(int)
        for name, iso, inst in zip(names, isos, shares):
            rows.append(
                {"Category": r["Category"], "Country": name,
                 "ISO3": iso, "Installs": int(inst)}
            )
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- #
# Convenience: one call to get everything
# --------------------------------------------------------------------------- #
def get_data():
    apps = load_apps()
    apps = merge_sentiment(apps)
    return apps


if __name__ == "__main__":
    df = get_data()
    print("Cleaned apps:", df.shape)
    print("With sentiment:", df["Sentiment_Subjectivity"].notna().sum())
    print("Categories:", df["Category"].nunique())
    print("Date range:", df["Last_Updated"].min(), "->", df["Last_Updated"].max())
    print("Revenue > 0 apps:", (df["Revenue"] > 0).sum())
