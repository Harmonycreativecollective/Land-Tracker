import base64
import json
from datetime import datetime
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

# ---------------- Paths ----------------
DATA_PATH = Path("data/listings.json")
LOGO_PATH = Path("assets/kblogo.png")

# ---------------- Branding ----------------
TITLE = "KB’s Land Tracker"
CAPTION = "What’s meant for you is already in motion."

st.set_page_config(
    page_title=TITLE,
    page_icon="assets/kblogo.png",
    layout="wide",
)

# ---------------- Helpers ----------------
def load_data():
    if not DATA_PATH.exists():
        return {"items": [], "criteria": {}, "last_updated_utc": None}
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def load_logo_base64(path: Path):
    try:
        if not path.exists():
            return None
        return base64.b64encode(path.read_bytes()).decode("utf-8")
    except Exception:
        return None

def pretty_last_updated(last_updated):
    if not last_updated:
        return None
    try:
        dt = datetime.fromisoformat(last_updated.replace("Z", "+00:00"))
        return dt.strftime("%b %d, %Y • %I:%M %p UTC")
    except Exception:
        return str(last_updated)

def searchable_text(it):
    return " ".join(
        [
            str(it.get("title", "")),
            str(it.get("source", "")),
            str(it.get("url", "")),
        ]
    ).lower()

def parse_dt(it):
    # Future-friendly if you add found_utc later
    return it.get("found_utc") or ""

# ---------------- Load ----------------
data = load_data()
items = data.get("items", [])
criteria = data.get("criteria", {})
last_updated = data.get("last_updated_utc")
last_updated_pretty = pretty_last_updated(last_updated)

# ---------------- Header (HTML, mobile-safe) ----------------
logo_b64 = load_logo_base64(LOGO_PATH)

header_html = f"""
<div style="
    display:flex;
    align-items:center;
    gap:clamp(12px, 2vw, 22px);
    margin: 6px 0 6px 0;
">
  <div style="flex:0 0 auto;">
    {"<img src='data:image/png;base64," + logo_b64 + "' style='width:clamp(95px, 17vw, 145px); height:auto; display:block;' />" if logo_b64 else ""}
  </div>

  <div style="flex:1 1 auto; min-width:0;">
    <div style="
        font-size:clamp(2.15rem, 6vw, 3.1rem);
        font-weight:900;
        line-height:1.05;
        color:#0f172a;
        margin:0;
        word-break:break-word;
        overflow-wrap:anywhere;
    ">{TITLE}</div>

    <div style="
        font-size:clamp(1.1rem, 3vw, 1.35rem);
        color:rgba(49, 51, 63, 0.72);
        margin-top:10px;
        line-height:1.35;
    ">{CAPTION}</div>
  </div>
</div>
"""

components.html(header_html, height=175)

# ✅ Last updated OUTSIDE
if last_updated_pretty:
    st.caption(f"Last updated: {last_updated_pretty}")

st.write("")  # spacer

# ---------------- Search (OUTSIDE filters) ----------------
search_query = st.text_input(
    "Search (title / location / source)",
    value="",
    placeholder="Try: king george, port royal, landsearch, 20 acres…",
)

# ---------------- Filter UI (as dropdowns) ----------------
# Defaults (your tracker criteria)
default_max_price = int(criteria.get("max_price", 600000))
default_min_acres = float(criteria.get("min_acres", 11.0))
default_max_acres = float(criteria.get("max_acres", 50.0))

# We want top matches ON by default
default_top_matches_only = True

# --- Apply search first ---
filtered = items[:]
if search_query.strip():
    q = search_query.strip().lower()
    filtered = [it for it in filtered if q in searchable_text(it)]

# ---------------- Filter + details expanders ----------------
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
        format="%.2f",
    )

    max_acres = st.number_input(
        "Max acres",
        min_value=0.0,
        value=default_max_acres,
        step=1.0,
        format="%.2f",
    )

    top_matches_only = st.toggle("Top matches only", value=default_top_matches_only)
    new_only = st.toggle("New only", value=False)
    newest_first = st.toggle("Newest first", value=True)

    show_n = st.slider("Show how many", min_value=5, max_value=200, value=50, step=5)

# ---------------- Match logic ----------------
def is_top_match(it):
    price = it.get("price")
    acres = it.get("acres")
    if price is None or acres is None:
        return False
    try:
        return (float(min_acres) <= float(acres) <= float(max_acres)) and (int(price) <= int(max_price))
    except Exception:
        return False

# New logic (simple version for now)
# If you later add found_utc, this becomes perfect. For now treat all scraped items as "new".
def is_new(it):
    return True

# Apply top match / new filters
if top_matches_only:
    filtered = [it for it in filtered if is_top_match(it)]

if new_only:
    filtered = [it for it in filtered if is_new(it)]

# Sorting
if newest_first:
    filtered = sorted(filtered, key=parse_dt, reverse=True)

# Limit
filtered = filtered[:show_n]

# ---------------- Details expander ----------------
all_found_count = len(items)
top_match_count = len([it for it in items if is_top_match(it)])
new_count = len([it for it in items if is_new(it)])

with st.expander("Details", expanded=False):
    st.caption(f"Criteria: ${max_price:,.0f} max • {min_acres:g}–{max_acres:g} acres")

    col1, col2, col3 = st.columns(3)
    col1.metric("All found", f"{all_found_count}")
    col2.metric("Top matches", f"{top_match_count}")
    col3.metric("New", f"{new_count}")

st.divider()

# ---------------- Listing Cards ----------------
def listing_card(it):
    title = it.get("title") or f"{it.get('source','Listing')} listing"
    url = it.get("url") or ""
    source = it.get("source") or ""
    price = it.get("price")
    acres = it.get("acres")
    thumb = it.get("thumbnail")

    top_match = is_top_match(it)
    new_badge = is_new(it)

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

        # Badges line
        badges = []
        if top_match:
            badges.append("⭐ Top match")
        if new_badge:
            badges.append("🆕 NEW")
        badge_text = " • ".join(badges) if badges else "FOUND"

        st.caption(f"{badge_text} • {source}")

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

# Grid
cols = st.columns(2)
for idx, it in enumerate(filtered):
    with cols[idx % 2]:
        listing_card(it)

if not filtered:
    st.info("No listings matched your current search/filters.")