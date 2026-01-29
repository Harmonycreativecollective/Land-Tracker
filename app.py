import json
from pathlib import Path
from datetime import datetime

import pandas as pd
import streamlit as st

st.set_page_config(page_title="Land Watch", page_icon="🗺️", layout="wide")

# ---------- STYLE POLISH (optional but makes it feel like an app) ----------
st.markdown(
    """
    <style>
    .block-container { padding-top: 2rem; }
    div[data-testid="metric-container"] {
        background-color: rgba(255,255,255,0.04);
        border: 1px solid rgba(255,255,255,0.08);
        padding: 16px;
        border-radius: 18px;
    }
    .card {
        background-color: rgba(255,255,255,0.04);
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 18px;
        padding: 16px;
        margin-bottom: 12px;
    }
    .muted { opacity: 0.75; font-size: 0.95rem; }
    .title { font-size: 1.15rem; font-weight: 600; }
    </style>
    """,
    unsafe_allow_html=True
)

# ---------- STEP 2: LOAD DATA ----------
DATA_PATH = Path("data/listings.json")

def load_data():
    if not DATA_PATH.exists():
        return {
            "last_updated_utc": None,
            "criteria": {"min_acres": None, "max_acres": None, "max_price": None},
            "items": []
        }
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

data = load_data()
items = data.get("items", []) or []
criteria = data.get("criteria", {}) or {}
last_updated_utc = data.get("last_updated_utc")

# Convert items to dataframe for easy sorting/filtering
df = pd.DataFrame(items)
if not df.empty:
    # standardize columns (in case any missing)
    for col in ["title", "url", "price", "acres", "source"]:
        if col not in df.columns:
            df[col] = None

# ---------- HEADER ----------
st.title("Land Watch Dashboard")
st.caption("Your land matches — updated from your saved searches.")

if last_updated_utc:
    try:
        dt = datetime.fromisoformat(last_updated_utc.replace("Z", "+00:00"))
        st.caption(f"Last updated (UTC): {dt.isoformat()}")
    except Exception:
        st.caption(f"Last updated (UTC): {last_updated_utc}")
else:
    st.caption("Last updated (UTC): —")

# ---------- STEP 3: SIDEBAR FILTERS ----------
st.sidebar.header("Filters")

default_max_price = int(criteria.get("max_price") or 600000)
default_min_acres = float(criteria.get("min_acres") or 11)
default_max_acres = float(criteria.get("max_acres") or 50)

max_price = st.sidebar.number_input("Max price", min_value=0, value=default_max_price, step=10000)
min_acres = st.sidebar.number_input("Min acres", min_value=0.0, value=default_min_acres, step=1.0)
max_acres = st.sidebar.number_input("Max acres", min_value=0.0, value=default_max_acres, step=1.0)

sort_by = st.sidebar.selectbox(
    "Sort by",
    ["Newest (as-is)", "Price (low → high)", "Price (high → low)", "Acres (high → low)", "Acres (low → high)"]
)

# Apply filters
filtered = df.copy() if not df.empty else pd.DataFrame(columns=["title","url","price","acres","source"])

if not filtered.empty:
    filtered = filtered.dropna(subset=["price", "acres", "url"])
    filtered = filtered[(filtered["price"] <= max_price) & (filtered["acres"] >= min_acres) & (filtered["acres"] <= max_acres)]

# Apply sorting
if not filtered.empty:
    if sort_by == "Price (low → high)":
        filtered = filtered.sort_values("price", ascending=True)
    elif sort_by == "Price (high → low)":
        filtered = filtered.sort_values("price", ascending=False)
    elif sort_by == "Acres (high → low)":
        filtered = filtered.sort_values("acres", ascending=False)
    elif sort_by == "Acres (low → high)":
        filtered = filtered.sort_values("acres", ascending=True)
    # "Newest (as-is)" keeps the file order

# ---------- STEP 4: PRETTY DASHBOARD LAYOUT ----------
sources = sorted(set((df["source"].dropna().tolist() if not df.empty else [])))

c1, c2, c3, c4 = st.columns(4)
c1.metric("Saved matches", int(len(filtered)))
c2.metric("Max price", f"${max_price:,.0f}")
c3.metric("Acres range", f"{min_acres:g}–{max_acres:g}")
c4.metric("Sources", ", ".join(sources) if sources else "—")

st.divider()

# Show results
if filtered.empty:
    st.markdown(
        """
        <div class="card">
          <div class="title">No matches yet.</div>
          <div class="muted">
            Your scraper ran successfully, but nothing matched the current filter settings.
            Try increasing Max price, lowering Min acres, or widening the acres range.
          </div>
        </div>
        """,
        unsafe_allow_html=True
    )
else:
    st.subheader("Matches")

    # Card view
    for _, row in filtered.head(50).iterrows():
        title = row.get("title") or "Land listing"
        url = row.get("url")
        price = row.get("price")
        acres = row.get("acres")
        source = row.get("source") or ""

        st.markdown(
            f"""
            <div class="card">
              <div class="title">{title}</div>
              <div class="muted">{source}</div>
              <div style="margin-top:10px; display:flex; gap:18px; flex-wrap:wrap;">
                <div><b>Price:</b> ${int(price):,}</div>
                <div><b>Acres:</b> {float(acres):g}</div>
                <div><a href="{url}" target="_blank">Open listing ↗</a></div>
              </div>
            </div>
            """,
            unsafe_allow_html=True
        )

    st.subheader("Table view")
    table = filtered.copy()
    table["link"] = table["url"].apply(lambda u: f"[Open]({u})")
    table = table[["price", "acres", "title", "source", "link"]]
    st.dataframe(table, use_container_width=True, hide_index=True)
