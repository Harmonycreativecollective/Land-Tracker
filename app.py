import base64
import json
from datetime import datetime
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

# -----------------------------
# Paths / Config
# -----------------------------
DATA_PATH = Path("data/listings.json")
LOGO_PATH = Path("assets/kblogo.png")  # make sure this exists in your repo

TITLE = "KB’s Land Tracker"
CAPTION = "What’s meant for you is already in motion."

st.set_page_config(
    page_title=TITLE,
    page_icon=str(LOGO_PATH) if LOGO_PATH.exists() else "🗺️",
    layout="wide",
)

# -----------------------------
# Helpers
# -----------------------------
def load_data():
    if not DATA_PATH.exists():
        return {"items": [], "criteria": {}, "last_updated_utc": None}
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def logo_base64(path: Path) -> str | None:
    if not path.exists():
        return None
    data = path.read_bytes()
    return base64.b64encode(data).decode("utf-8")

def safe_title(it: dict) -> str:
    t = (it.get("title") or "").strip()
    if t and t.lower() != "land listing":
        return t
    src = (it.get("source") or "Listing").strip()
    return f"{src} listing"

def searchable_text(it: dict) -> str:
    return " ".join(
        [
            str(it.get("title", "")),
            str(it.get("source", "")),
            str(it.get("url", "")),
        ]
    ).lower()

def parse_dt(it: dict) -> str:
    # If you later add found_utc in scraper, this will sort properly.
    # For now it returns empty string, which keeps existing order stable.
    return str(it.get("found_utc") or "")

def is_top_match(it: dict, min_acres: float, max_acres: float, max_price: int) -> bool:
    price = it.get("price")
    acres = it.get("acres")
    if price is None or acres is None:
        return False
    try:
        price_i = int(price)
        acres_f = float(acres)
    except Exception:
        return False
    return (min_acres <= acres_f <= max_acres) and (price_i <= max_price)

def is_new(it: dict) -> bool:
    # Future-ready: when you add found_utc, compute "new" properly.
    # For now, treat everything as new if you haven't implemented tracking.
    # You can change this later.
    return True

# -----------------------------
# Load Data
# -----------------------------
data = load_data()
items = data.get("items", []) or []
last_updated = data.get("last_updated_utc")

# -----------------------------
# Branded Header (NEVER prints HTML)
# -----------------------------
logo_b64 = logo_base64(LOGO_PATH)
LOGO_HEIGHT_PX = 110  # make bigger/smaller as you want

header_html = f"""
<div style="
    display:flex;
    align-items:center;
    gap:18px;
    margin-top:12px;
    margin-bottom:6px;
    flex-wrap:nowrap;
">
    <div style="flex:0 0 auto;">
        {"<img src='data:image/png;base64," + logo_b64 + "' style='height:" + str(LOGO_HEIGHT_PX) + "px; width:auto; border-radius:16px;'/>" if logo_b64 else ""}
    </div>

    <div style="flex:1 1 auto;">
        <div style="
            font-size:3.0rem;
            font-weight:900;
            line-height:1.05;
            color:#0f172a;
            margin:0;
        ">
            {TITLE}
        </div>

        <div style="
            font-size:1.35rem;
            color: rgba(49, 51, 63, 0.78);
            margin-top:10px;
        ">
            {CAPTION}
        </div>
    </div>
</div>
"""
components.html(header_html, height=150)

# Last updated OUTSIDE filters/details
if last_updated:
    try:
        dt = datetime.fromisoformat(last_updated.replace("Z", "+00:00"))
        st.caption(f"Last updated: {dt.strftime('%b %d, %Y • %I:%M %p UTC')}")
    except Exception:
        st.caption(f"Last updated: {last_updated}")

st.write("")  # small spacing

# -----------------------------
# Search (outside filters)
# -----------------------------
search_query = st.text_input(
    "Search (title / location / source)",
    value="",
    placeholder="Try: king george, port royal, landsearch, 20 acres…",
)

# -----------------------------
# Expanders: Filters + Details
# -----------------------------
# Defaults (your current criteria)
default_max_price = 600000
default_min_acres = 11.0
default_max_acres = 50.0

with st.expander("Filters", expanded=False):
    max_price = st.number_input(
        "Max price (Top match)",
        min_value=0,
        value=default_max_price,
        step=10000,
    )
    min_acres = st.number_input(
        "Min acres",
        min_value=0.0,
        value=default_min_acres,
        step=1.0,
    )
    max_acres = st.number_input(
        "Max acres",
        min_value=0.0,
        value=default_max_acres,
        step=1.0,
    )

    colA, colB, colC = st.columns(3)
    with colA:
        top_matches_only = st.toggle("Top matches only", value=True)
    with colB:
        new_only = st.toggle("New only", value=False)
    with colC:
        newest_first = st.toggle("Newest first", value=True)

    show_n = st.slider("Show how many", min_value=5, max_value=200, value=50, step=5)

# -----------------------------
# Apply logic
# -----------------------------
filtered = items[:]

# Search first
if search_query.strip():
    q = search_query.strip().lower()
    filtered = [it for it in filtered if q in searchable_text(it)]

# Flags computed
def top_match_flag(it: dict) -> bool:
    return is_top_match(it, min_acres=min_acres, max_acres=max_acres, max_price=max_price)

def new_flag(it: dict) -> bool:
    return is_new(it)

# Filter toggles
if top_matches_only:
    filtered = [it for it in filtered if top_match_flag(it)]

if new_only:
    filtered = [it for it in filtered if new_flag(it)]

# Sort
if newest_first:
    filtered = sorted(filtered, key=parse_dt, reverse=True)

# Limit
filtered = filtered[:show_n]

# -----------------------------
# Details expander (counts, criteria)
# -----------------------------
all_found_count = len(items)
top_match_count = sum(1 for it in items if top_match_flag(it))
new_count = sum(1 for it in items if new_flag(it))

with st.expander("Details", expanded=False):
    col1, col2, col3 = st.columns(3)
    col1.metric("All found", f"{all_found_count}")
    col2.metric("Top matches", f"{top_match_count}")
    col3.metric("New", f"{new_count}")

    st.caption(f"Criteria: ${int(max_price):,} max • {min_acres:g}–{max_acres:g} acres")

st.divider()

# -----------------------------
# Listing card UI
# -----------------------------
def badge_row(it: dict) -> str:
    badges = []
    if top_match_flag(it):
        badges.append("⭐ Top match")
    if new_flag(it):
        badges.append("🆕 New")
    if not badges:
        badges.append("FOUND")
    return " • ".join(badges)

def listing_card(it: dict):
    title = safe_title(it)
    url = it.get("url") or ""
    source = it.get("source") or ""
    price = it.get("price")
    acres = it.get("acres")
    thumb = it.get("thumbnail")

    with st.container(border=True):
        if thumb:
            st.image(thumb, use_container_width=True)
        else:
            st.markdown(
                """
                <div style="width:100%; height:220px; background:#f2f2f2; border-radius:16px;
                            display:flex; align-items:center; justify-content:center; color:#777;
                            font-weight:700; font-size:1.05rem;">
                    No preview available
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.subheader(title)
        st.caption(f"{badge_row(it)} • {source}")

        if price is None:
            st.write("**Price:** —")
        else:
            try:
                st.write(f"**Price:** ${int(price):,}")
            except Exception:
                st.write(f"**Price:** {price}")

        if acres is None:
            st.write("**Acres:** —")
        else:
            try:
                st.write(f"**Acres:** {float(acres):g}")
            except Exception:
                st.write(f"**Acres:** {acres}")

        if url:
            st.link_button("Open listing ↗", url, use_container_width=True)

# -----------------------------
# Render grid
# -----------------------------
cols = st.columns(2)
for idx, it in enumerate(filtered):
    with cols[idx % 2]:
        listing_card(it)

if not filtered:
    st.info("No listings matched your current search/filters.")