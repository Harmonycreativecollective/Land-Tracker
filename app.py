import json
from pathlib import Path
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Land Watch", page_icon="🗺️", layout="wide")

# ---------- theme-ish styling (works even without config.toml) ----------
st.markdown(
    """
    <style>
      .block-container { padding-top: 2rem; padding-bottom: 2rem; }
      a { text-decoration: none; }
      .small-muted { opacity: 0.75; font-size: 0.95rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("Land Watch Dashboard")
st.caption("Find land deals automatically — updated from your saved searches.")

# ---------- load data ----------
DATA_PATH = Path("data/listings.json")

data = {"last_updated_utc": None, "criteria": {}, "items": []}
if DATA_PATH.exists():
    try:
        data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    except Exception:
        st.error("Could not read data/listings.json (invalid JSON).")

items = data.get("items", []) or []
criteria = data.get("criteria", {}) or {}

last_updated = data.get("last_updated_utc", None)

min_acres = float(criteria.get("min_acres", 0) or 0)
max_acres = float(criteria.get("max_acres", 0) or 0)
max_price_default = int(criteria.get("max_price", 0) or 0)

# ---------- sidebar filters ----------
st.sidebar.header("Filters")

max_price = st.sidebar.number_input(
    "Max price",
    min_value=0,
    value=max_price_default if max_price_default else 600000,
    step=10000,
)

q = st.sidebar.text_input("Search (title/source)")

show_n = st.sidebar.slider("Show how many", 10, 300, 120)

show_table = st.sidebar.toggle("Show table view", value=False)

# ---------- normalize + filter ----------
def safe_int(x):
    try:
        return int(x)
    except Exception:
        return None

def safe_float(x):
    try:
        return float(x)
    except Exception:
        return None

filtered = []
for it in items:
    price = safe_int(it.get("price"))
    acres = safe_float(it.get("acres"))
    title = (it.get("title") or "Land listing").strip()
    source = (it.get("source") or "").strip()
    url = (it.get("url") or "").strip()

    if price is None or acres is None:
        continue

    if price > max_price:
        continue

    if q:
        hay = f"{title} {source}".lower()
        if q.lower() not in hay:
            continue

    filtered.append(
        {
            "price": price,
            "acres": acres,
            "title": title,
            "source": source,
            "url": url,
        }
    )

# sort cheapest first
filtered.sort(key=lambda x: (x["price"], -x["acres"]))

# cap results displayed
displayed = filtered[:show_n]

# ---------- top metrics ----------
c1, c2, c3, c4 = st.columns(4)

c1.metric("Saved matches", len(items))
c2.metric("Showing now", len(displayed))
c3.metric("Max price", f"${max_price:,.0f}")
c4.metric("Acres range", f"{min_acres:g}–{max_acres:g}" if max_acres else "—")

if last_updated:
    st.markdown(f"<div class='small-muted'>Last updated (UTC): {last_updated}</div>", unsafe_allow_html=True)

st.divider()

# ---------- results ----------
if not displayed:
    st.info("No matches yet with the current filters. Try raising max price or clearing the search box.")
else:
    # cards
    for it in displayed:
        price_str = f"${it['price']:,.0f}"
        acres_str = f"{it['acres']:g} acres"
        title = it["title"]
        source = it["source"] or "Source"
        url = it["url"]

        st.markdown(
            f"""
            <div style="
              border: 1px solid rgba(255,255,255,0.08);
              border-radius: 18px;
              padding: 16px 18px;
              margin-bottom: 12px;
              background: rgba(255,255,255,0.02);
            ">
              <div style="font-size: 1.15rem; font-weight: 700; margin-bottom: 2px;">{title}</div>
              <div style="opacity: 0.75; margin-bottom: 10px;">{source}</div>
              <div style="display:flex; gap:18px; align-items:center; flex-wrap:wrap;">
                <div><b>Price:</b> {price_str}</div>
                <div><b>Acres:</b> {acres_str}</div>
                <div style="margin-left:auto;">
                  <a href="{url}" target="_blank">Open listing ↗</a>
                </div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

# ---------- optional table ----------
if show_table and displayed:
    st.subheader("Table view")
    df = pd.DataFrame(displayed)
    df["link"] = df["url"].apply(lambda u: f"[Open]({u})")
    df = df.drop(columns=["url"])
    st.dataframe(df, use_container_width=True, hide_index=True)
