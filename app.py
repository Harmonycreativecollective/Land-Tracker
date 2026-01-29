import json
import pandas as pd
import streamlit as st

DATA_PATH = "data/listings.json"

st.set_page_config(page_title="Land Watch Dashboard", layout="wide")
st.title("Land Watch Dashboard")

with open(DATA_PATH, "r", encoding="utf-8") as f:
    data = json.load(f)

last_updated = data.get("last_updated_utc")
items = data.get("items", [])

st.caption(f"Last updated (UTC): {last_updated or '—'}")

if not items:
    st.info("No matches yet. Once the scraper runs, results will appear here.")
    st.stop()

df = pd.DataFrame(items)

if "price" in df.columns:
    df["price"] = pd.to_numeric(df["price"], errors="coerce")

col1, col2, col3 = st.columns(3)
with col1:
    max_price = st.number_input("Max price", min_value=0, value=20000, step=500)
with col2:
    search_text = st.text_input("Search (title/location)")
with col3:
    show_n = st.slider("Show how many", min_value=10, max_value=300, value=50, step=10)

filtered = df.copy()

if "price" in filtered.columns:
    filtered = filtered[filtered["price"].fillna(10**12) <= max_price]

if search_text.strip():
    s = search_text.strip().lower()
    filtered = filtered[
        filtered.apply(lambda r: s in str(r.get("title","")).lower() or s in str(r.get("location","")).lower(), axis=1)
    ]

def as_link(url):
    return f"[Open]({url})" if isinstance(url, str) and url.startswith("http") else url

if "url" in filtered.columns:
    filtered["link"] = filtered["url"].apply(as_link)

filtered = filtered.head(show_n)

cols = [c for c in ["price", "acres", "location", "title", "link"] if c in filtered.columns]
st.dataframe(filtered[cols] if cols else filtered, use_container_width=True, hide_index=True)

st.markdown("### Quick stats")
c1, c2 = st.columns(2)
c1.metric("Total saved matches", len(df))
c2.metric("Showing now", len(filtered))
