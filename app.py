import json
from datetime import datetime
from pathlib import Path

import streamlit as st

DATA_PATH = Path("data/listings.json")

st.set_page_config(
    page_title="KB’s Land Tracker",
    page_icon="🗺️",
    layout="wide",
)

TITLE = "KB’s Land Tracker"
CAPTION = "What’s meant for you is already in motion."

# ---------- Load data ----------
def load_data():
    if not DATA_PATH.exists():
        return {"items": [], "criteria": {}, "last_updated_utc": None}
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

data = load_data()
items = data.get("items", [])
last_updated = data.get("last_updated_utc")

# ---------- Header ----------
st.title(TITLE)
st.caption(CAPTION)

# ✅ Search OUTSIDE filters (top-of-page)
search_query = st.text_input(
    "Search (title / location / source)",
    value="",
    placeholder="Try: king george, port royal, landsearch, 20 acres…",
)

# ---------- Sidebar Filters ----------
st.sidebar.header("Filters")

max_price = st.sidebar.number_input(
    "Max price (STRICT matches)",
    min_value=0,
    value=600000,
    step=10000,
)

min_acres = st.sidebar.number_input(
    "Min acres",
    min_value=0.0,
    value=11.0,
    step=1.0,
)

max_acres = st.sidebar.number_input(
    "Max acres",
    min_value=0.0,
    value=50.0,
    step=1.0,
)

show_top_matches = st.sidebar.toggle("Top matches only", value=False)
show_matches_only = st.sidebar.toggle("STRICT matches only", value=False)

sort_newest = st.sidebar.toggle("Newest first", value=True)

show_n = st.sidebar.slider("Show how many", min_value=5, max_value=200, value=50, step=5)

# ---------- Helpers ----------
def is_match(it):
    price = it.get("price")
    acres = it.get("acres")
    if price is None or acres is None:
        return False
    return (min_acres <= float(acres) <= max_acres) and (int(price) <= int(max_price))

def searchable_text(it):
    return " ".join([
        str(it.get("title", "")),
        str(it.get("source", "")),
        str(it.get("url", "")),
    ]).lower()

def parse_dt(it):
    # if your scraper writes a timestamp field later, use it here
    # for now, we just keep original order
    return it.get("found_utc") or ""

# ---------- Apply filters ----------
filtered = items[:]

# Search first (OUTSIDE filters)
if search_query.strip():
    q = search_query.strip().lower()
    filtered = [it for it in filtered if q in searchable_text(it)]

# Match toggles
if show_matches_only:
    filtered = [it for it in filtered if is_match(it)]
elif show_top_matches:
    # "Top matches" can be stricter later; for now treat as matches
    filtered = [it for it in filtered if is_match(it)]

# Sorting
if sort_newest:
    # If you add found_utc later, this will work properly.
    filtered = sorted(filtered, key=parse_dt, reverse=True)

# Limit
filtered = filtered[:show_n]

# ---------- Metrics (simple + clean) ----------
strict_matches = [it for it in items if is_match(it)]

col1, col2, col3 = st.columns(3)
col1.metric("All found", f"{len(items)}")
col2.metric("Strict matches", f"{len(strict_matches)}")
col3.metric("Max price", f"${max_price:,.0f}")

st.caption(f"Acre range: {min_acres:g}–{max_acres:g}")

if last_updated:
    try:
        # make it prettier if it's ISO
        dt = datetime.fromisoformat(last_updated.replace("Z", "+00:00"))
        st.caption(f"Last updated: {dt.strftime('%b %d, %Y • %I:%M %p UTC')}")
    except Exception:
        st.caption(f"Last updated: {last_updated}")

st.divider()

# ---------- Listing cards ----------
def listing_card(it):
    title = it.get("title") or "Land listing"
    url = it.get("url") or ""
    source = it.get("source") or ""
    price = it.get("price")
    acres = it.get("acres")
    thumb = it.get("thumbnail")

    match = is_match(it)

    with st.container(border=True):
        if thumb:
            st.image(thumb, use_container_width=True)
        else:
            # “No preview available” placeholder
            st.markdown(
                """
                <div style="width:100%; height:220px; background:#f2f2f2; border-radius:16px;
                            display:flex; align-items:center; justify-content:center; color:#777;
                            font-weight:600;">
                    No preview available
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.subheader(title)

        pill = "MATCH" if match else "FOUND"
        st.caption(f"{pill} • {source}")

        if price is None:
            st.write("**Price:** —")
        else:
            st.write(f"**Price:** ${int(price):,}")

        if acres is None:
            st.write("**Acres:** —")
        else:
            st.write(f"**Acres:** {float(acres):g}")

        if url:
            st.link_button("Open listing ↗", url, use_container_width=True)

# Show grid (2 columns on mobile-ish works fine)
cols = st.columns(2)
for idx, it in enumerate(filtered):
    with cols[idx % 2]:
        listing_card(it)

if not filtered:
    st.info("No listings matched your current search/filters.")