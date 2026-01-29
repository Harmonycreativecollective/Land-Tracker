import json
from pathlib import Path
import streamlit as st
from datetime import datetime

st.set_page_config(page_title="Land Watch", page_icon="🗺️", layout="wide")

# ---------- helpers ----------
def money_fmt(x):
    if x is None:
        return "—"
    try:
        return f"${int(x):,}"
    except Exception:
        return str(x)

def acres_fmt(x):
    if x is None:
        return "—"
    try:
        return f"{float(x):g}"
    except Exception:
        return str(x)

def pill(text, good=True):
    bg = "rgba(56, 142, 60, 0.18)" if good else "rgba(255, 167, 38, 0.18)"
    border = "rgba(56, 142, 60, 0.45)" if good else "rgba(255, 167, 38, 0.45)"
    return f"""
    <span style="
        display:inline-block;
        padding:4px 10px;
        border-radius:999px;
        background:{bg};
        border:1px solid {border};
        font-size:12px;
        font-weight:600;
        margin-left:8px;
        ">
        {text}
    </span>
    """

# ---------- load data ----------
data_path = Path("data/listings.json")
if not data_path.exists():
    st.error("No data/listings.json found yet. Run the scraper first.")
    st.stop()

data = json.loads(data_path.read_text(encoding="utf-8"))
items = data.get("items", []) or []
criteria = data.get("criteria", {}) or {}

min_acres = criteria.get("min_acres", 0)
max_acres = criteria.get("max_acres", 999999)
max_price = criteria.get("max_price", 999999999)

last_updated = data.get("last_updated_utc", "")

# ---------- header ----------
st.title("Land Watch Dashboard")
st.caption("Saved searches → scraper → dashboard. (Now keeps ALL listings, even if price looks weird.)")

# ---------- top stats ----------
matches = [i for i in items if i.get("matches")]
sources = sorted(set((i.get("source") or "").strip() for i in items if i.get("source")))

c1, c2, c3, c4 = st.columns(4)
c1.metric("All found", len(items))
c2.metric("Strict matches", len(matches))
c3.metric("Max price", f"${max_price:,.0f}")
c4.metric("Acres range", f"{min_acres:g}–{max_acres:g}")

st.caption(f"Last updated (UTC): {last_updated}")

st.divider()

# ---------- controls ----------
left, right = st.columns([2, 3])

with left:
    show_only_matches = st.toggle("Show only strict matches", value=False)
    max_price_ui = st.number_input("Filter: max price", min_value=0, value=int(max_price), step=5000)
    search = st.text_input("Search (title/source/url)", value="")
with right:
    st.write("")
    st.write("")
    show_n = st.slider("Show how many", 5, 200, 20)

# ---------- apply filters ----------
filtered = items[:]

if show_only_matches:
    filtered = [i for i in filtered if i.get("matches")]

filtered = [i for i in filtered if (i.get("price") is None or int(i.get("price")) <= int(max_price_ui))]

if search.strip():
    s = search.strip().lower()
    def hit(i):
        return (
            s in (i.get("title") or "").lower()
            or s in (i.get("source") or "").lower()
            or s in (i.get("url") or "").lower()
        )
    filtered = [i for i in filtered if hit(i)]

# Sort: cheapest first (None last)
def sort_key(i):
    p = i.get("price")
    return (p is None, p if p is not None else 10**18)

filtered.sort(key=sort_key)
filtered = filtered[:show_n]

# ---------- display ----------
if not filtered:
    st.info("No listings with the current filters. Try toggling off ‘Show only strict matches’ or raising max price.")
    st.stop()

# cards layout
st.subheader("Listings")

for i in filtered:
    title = i.get("title") or "Land listing"
    url = i.get("url") or ""
    src = i.get("source") or "Unknown source"
    price = i.get("price")
    acres = i.get("acres")
    is_match = bool(i.get("matches"))

    with st.container(border=True):
        colA, colB = st.columns([4, 1])
        with colA:
            badge = pill("MATCHES", good=True) if is_match else pill("PRICE/ACRES UNKNOWN", good=False)
            st.markdown(f"### {title} {badge}", unsafe_allow_html=True)
            st.caption(src)
            st.markdown(
                f"**Price:** {money_fmt(price)} &nbsp;&nbsp; **Acres:** {acres_fmt(acres)}"
            )
        with colB:
            if url:
                st.link_button("Open listing ↗", url)
            else:
                st.write("")

st.divider()
st.caption("Tip: If something has a weird price like $9 or $3, it’s usually ‘Contact for price’ or a formatting issue — we keep it anyway.")