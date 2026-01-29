import json
import streamlit as st
from datetime import datetime

st.set_page_config(page_title="Land Watch", page_icon="🗺️", layout="wide")

def load_data(path="data/listings.json"):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"last_updated_utc": None, "criteria": {}, "items": []}

data = load_data()
items = data.get("items", [])
criteria = data.get("criteria", {})

last_updated = data.get("last_updated_utc")
if last_updated:
    try:
        dt = datetime.fromisoformat(last_updated.replace("Z", "+00:00"))
        last_updated_display = dt.strftime("%Y-%m-%d %H:%M UTC")
    except Exception:
        last_updated_display = str(last_updated)
else:
    last_updated_display = "Unknown"

min_acres = criteria.get("min_acres", 11)
max_acres = criteria.get("max_acres", 50)
default_max_price = criteria.get("max_price", 600000)

st.title("Land Watch Dashboard")
st.caption(f"Last updated: {last_updated_display}")

# Top stats
col1, col2, col3, col4 = st.columns(4)
col1.metric("Total listings saved", len(items))
col2.metric("Target max price", f"${default_max_price:,.0f}")
col3.metric("Target acres", f"{min_acres}–{max_acres}")
statuses = sorted(set([i.get("status", "unknown") for i in items]))
col4.metric("Statuses", ", ".join(statuses) if statuses else "—")

st.divider()

# Filters
with st.container():
    f1, f2, f3 = st.columns([2, 2, 2])

    max_price_filter = f1.slider(
        "Max price filter (keeps Unknown too)",
        min_value=1000,
        max_value=int(default_max_price),
        value=int(default_max_price),
        step=1000,
    )

    status_filter = f2.multiselect(
        "Status filter",
        options=sorted(set([i.get("status", "unknown") for i in items])),
        default=sorted(set([i.get("status", "unknown") for i in items])),
    )

    query = f3.text_input("Search (title/url)")

show_n = st.slider("Show how many", 1, max(1, len(items)), min(50, len(items)) if items else 1)

def matches_filters(i):
    # status
    if status_filter and i.get("status", "unknown") not in status_filter:
        return False

    # query
    if query:
        blob = f"{i.get('title','')} {i.get('url','')}".lower()
        if query.lower() not in blob:
            return False

    # price filter: keep unknown prices
    p = i.get("price")
    if p is not None and p > max_price_filter:
        return False

    return True

filtered = [i for i in items if matches_filters(i)]
filtered = filtered[:show_n]

st.divider()

def fmt_price(i):
    if i.get("price") is not None:
        return f"${int(i['price']):,}"
    # fall back to captured text if present
    if i.get("price_text"):
        return str(i["price_text"]).strip()
    return "Unknown / Contact for price"

def fmt_acres(i):
    if i.get("acres") is not None:
        return f"{float(i['acres']):g}"
    if i.get("acres_text"):
        return str(i["acres_text"]).strip()
    return "Unknown"

# Cards
if not items:
    st.info("No listings found yet. Once the scraper runs and saves data, results will appear here.")
elif not filtered:
    st.warning("No listings match the current filters. Try widening filters or clearing the search box.")
else:
    for i in filtered:
        with st.container(border=True):
            top = st.columns([4, 2])
            top[0].markdown(f"### {i.get('title','Land listing')}")
            top[1].markdown(f"**Status:** `{i.get('status','unknown')}`")

            meta = st.columns(4)
            meta[0].markdown(f"**Source:** {i.get('source','—')}")
            meta[1].markdown(f"**Price:** {fmt_price(i)}")
            meta[2].markdown(f"**Acres:** {fmt_acres(i)}")
            meta[3].markdown(f"[Open listing ↗]({i.get('url','')})")

st.divider()
st.caption(f"Showing {len(filtered)} of {len(items)} saved listings.")