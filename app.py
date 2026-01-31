import base64
import json
from datetime import datetime
from pathlib import Path

import streamlit as st

DATA_PATH = Path("data/listings.json")
LOGO_PATH = Path("assets/kblogo.png")

TITLE = "KB’s Land Tracker"
CAPTION = "What’s meant for you is already in motion."

st.set_page_config(
    page_title=TITLE,
    page_icon=str(LOGO_PATH) if LOGO_PATH.exists() else "🗺️",
    layout="wide",
)

# ---------- Load data ----------
def load_data():
    if not DATA_PATH.exists():
        return {"items": [], "criteria": {}, "last_updated_utc": None}
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

data = load_data()
items = data.get("items", [])
criteria = data.get("criteria", {}) or {}
last_updated = data.get("last_updated_utc")


# ---------- Helpers ----------
def b64_image(path: Path) -> str:
    if not path.exists():
        return ""
    return base64.b64encode(path.read_bytes()).decode("utf-8")


def format_last_updated(ts: str) -> str:
    if not ts:
        return ""
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return dt.strftime("%b %d, %Y • %I:%M %p UTC")
    except Exception:
        return ts


def parse_dt(it):
    # Found date from scraper (ISO string)
    return it.get("found_utc") or ""


def searchable_text(it):
    return " ".join(
        [
            str(it.get("title", "")),
            str(it.get("source", "")),
            str(it.get("url", "")),
            str(it.get("location", "")),
        ]
    ).lower()


# Top match logic (uses current filter values; criteria are just for display)
def is_top_match(it, min_acres, max_acres, max_price):
    price = it.get("price")
    acres = it.get("acres")
    if price is None or acres is None:
        return False
    try:
        return (min_acres <= float(acres) <= max_acres) and (int(price) <= int(max_price))
    except Exception:
        return False


def is_new(it, new_days=7):
    """NEW = first seen within last N days based on found_utc."""
    ts = it.get("found_utc")
    if not ts:
        return False
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        now = datetime.utcnow().replace(tzinfo=dt.tzinfo)
        return (now - dt).days < new_days
    except Exception:
        return False


# ---------- Header (FIXED: wrap + autoscale, no clipping) ----------
logo_b64 = b64_image(LOGO_PATH)

st.markdown(
    """
    <style>
      /* Give the main container a tiny bit more breathing room on mobile */
      @media (max-width: 600px) {
        .block-container { padding-top: 1.2rem; }
      }
    </style>
    """,
    unsafe_allow_html=True,
)

header_html = f"""
<div style="
  display:flex;
  align-items:center;
  gap:18px;
  margin-top:6px;
  margin-bottom:6px;
">
  <div style="
    flex: 0 0 auto;
    width: clamp(88px, 18vw, 130px);
  ">
    {"<img src='data:image/png;base64," + logo_b64 + "' style='width:100%; height:auto; display:block;' />" if logo_b64 else ""}
  </div>

  <div style="
    flex: 1 1 auto;
    min-width: 0;            /* IMPORTANT: allows text to wrap instead of overflow */
  ">
    <div style="
      font-size: clamp(2.0rem, 6.5vw, 3.2rem);
      font-weight: 900;
      line-height: 1.05;
      margin: 0;
      color: #0f172a;
      white-space: normal;   /* allow wrap */
      overflow-wrap: anywhere;
      word-break: break-word;
    ">
      {TITLE}
    </div>

    <div style="
      font-size: clamp(1.05rem, 3.8vw, 1.35rem);
      color: rgba(51, 51, 51, 0.72);
      margin-top: 10px;
      line-height: 1.35;
      white-space: normal;   /* allow wrap */
      overflow-wrap: anywhere;
      word-break: break-word;
    ">
      {CAPTION}
    </div>
  </div>
</div>
"""
st.markdown(header_html, unsafe_allow_html=True)

# Last updated OUTSIDE details (as requested)
if last_updated:
    st.caption(f"Last updated: {format_last_updated(last_updated)}")

st.write("")  # a little spacing


# ✅ Search (top-of-page)
search_query = st.text_input(
    "Search (title / location / source)",
    value="",
    placeholder="Try: king george, port royal, landsearch, 20 acres…",
)


# ---------- Filters + Details as dropdowns ----------
# Defaults (prefer JSON criteria when present)
default_min = float(criteria.get("min_acres", 11.0) or 11.0)
default_max = float(criteria.get("max_acres", 50.0) or 50.0)
default_price = int(criteria.get("max_price", 600000) or 600000)

with st.expander("Filters", expanded=False):
    max_price = st.number_input("Max price (Top match)", min_value=0, value=default_price, step=10000)
    min_acres = st.number_input("Min acres", min_value=0.0, value=default_min, step=1.0)
    max_acres = st.number_input("Max acres", min_value=0.0, value=default_max, step=1.0)

    show_top_matches_only = st.toggle("Top matches only", value=True)  # ON by default
    show_new_only = st.toggle("New only", value=False)
    sort_newest = st.toggle("Newest first", value=True)

    show_n = st.slider("Show how many", min_value=5, max_value=200, value=50, step=5)

with st.expander("Details", expanded=False):
    st.caption(f"Criteria: ${max_price:,.0f} max • {min_acres:g}–{max_acres:g} acres")


# ---------- Apply filters ----------
filtered = items[:]

# Search
if search_query.strip():
    q = search_query.strip().lower()
    filtered = [it for it in filtered if q in searchable_text(it)]

# Top match / New toggles
if show_top_matches_only:
    filtered = [it for it in filtered if is_top_match(it, min_acres, max_acres, max_price)]

if show_new_only:
    filtered = [it for it in filtered if is_new(it, new_days=7)]

# Sort newest (by found_utc, which scraper should write)
if sort_newest:
    filtered = sorted(filtered, key=parse_dt, reverse=True)

# Limit
filtered = filtered[:show_n]


# ---------- Metrics ----------
all_found = len(items)
top_match_count = sum(1 for it in items if is_top_match(it, min_acres, max_acres, max_price))
new_count = sum(1 for it in items if is_new(it, new_days=7))

col1, col2, col3 = st.columns(3)
col1.metric("All found", f"{all_found}")
col2.metric("Top matches", f"{top_match_count}")
col3.metric("New", f"{new_count}")

st.divider()


# ---------- Listing cards ----------
def listing_card(it):
    title = it.get("title") or f"{it.get('source','Listing')} listing"
    url = it.get("url") or ""
    source = it.get("source") or ""
    price = it.get("price")
    acres = it.get("acres")
    thumb = it.get("thumbnail")

    top_match = is_top_match(it, min_acres, max_acres, max_price)
    new_badge = is_new(it, new_days=7)

    with st.container(border=True):
        if thumb:
            st.image(thumb, use_container_width=True)
        else:
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

        badges = []
        if top_match:
            badges.append("⭐ Top match")
        if new_badge:
            badges.append("🆕 New")
        if not badges:
            badges.append("FOUND")

        st.caption(" • ".join([*badges, source]))

        st.write(f"**Price:** {'—' if price is None else '$' + format(int(price), ',')}")
        st.write(f"**Acres:** {'—' if acres is None else str(float(acres)).rstrip('0').rstrip('.')}")
        if url:
            st.link_button("Open listing ↗", url, use_container_width=True)


cols = st.columns(2)
for idx, it in enumerate(filtered):
    with cols[idx % 2]:
        listing_card(it)

if not filtered:
    st.info("No listings matched your current search/filters.")