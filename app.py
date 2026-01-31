import base64
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

import streamlit as st

# ---------- Paths ----------
DATA_PATH = Path("data/listings.json")
LOGO_PATH = Path("assets/kblogo.png")

# ---------- Page config ----------
st.set_page_config(
    page_title="KB’s Land Tracker",
    page_icon=str(LOGO_PATH) if LOGO_PATH.exists() else "🗺️",
    layout="wide",
)

TITLE = "KB’s Land Tracker"
CAPTION = "What’s meant for you is already in motion."

# ---------- Load data ----------
def load_data() -> Dict[str, Any]:
    if not DATA_PATH.exists():
        return {"items": [], "criteria": {}, "last_updated_utc": None}
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

data = load_data()
items = data.get("items", []) or []
criteria = data.get("criteria", {}) or {}
last_updated = data.get("last_updated_utc")

# ---------- Time formatting (Eastern) ----------
def format_last_updated_et(ts: str) -> str:
    if not ts:
        return ""
    try:
        # parse ISO (works for "...+00:00" and "Z")
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        # convert to ET (handle environments without zoneinfo gracefully)
        try:
            from zoneinfo import ZoneInfo  # py3.9+
            dt_et = dt.astimezone(ZoneInfo("America/New_York"))
            return dt_et.strftime("%b %d, %Y • %I:%M %p ET")
        except Exception:
            # fallback: approximate ET from UTC using -5 or -4 is tricky due DST,
            # so if zoneinfo isn't available, just display local time without label.
            dt_local = dt.astimezone()
            return dt_local.strftime("%b %d, %Y • %I:%M %p")
    except Exception:
        return ts

# ---------- Header (logo left, text right) ----------
def render_header():
    logo_b64 = ""
    if LOGO_PATH.exists():
        logo_b64 = base64.b64encode(LOGO_PATH.read_bytes()).decode("utf-8")

    # Bigger logo + smaller title + safe wrapping
    st.markdown(
        f"""
        <style>
          .kb-header {{
            display:flex;
            align-items:center;
            gap:16px;
            margin-top: 0.25rem;
            margin-bottom: 0.2rem;
          }}
          .kb-logo {{
            width:92px;
            height:92px;
            flex: 0 0 92px;
            border-radius: 16px;
            object-fit: contain;
          }}
          .kb-text {{
            flex: 1 1 auto;
            min-width: 0; /* critical: allows text to wrap instead of overflow */
          }}
          .kb-title {{
            font-size: clamp(2.0rem, 4.5vw, 2.6rem);
            font-weight: 900;
            line-height: 1.05;
            margin: 0;
            color: #0f172a;
            overflow-wrap: anywhere;
            word-break: break-word;
          }}
          .kb-caption {{
            font-size: clamp(1.05rem, 2.6vw, 1.25rem);
            color: rgba(49, 51, 63, 0.75);
            margin-top: 8px;
            line-height: 1.35;
            overflow-wrap: anywhere;
            word-break: break-word;
          }}
        </style>

        <div class="kb-header">
          {"<img class='kb-logo' src='data:image/png;base64," + logo_b64 + "' />" if logo_b64 else ""}
          <div class="kb-text">
            <div class="kb-title">{TITLE}</div>
            <div class="kb-caption">{CAPTION}</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

render_header()

# last updated OUTSIDE details/filters
if last_updated:
    st.caption(f"Last updated: {format_last_updated_et(last_updated)}")

st.write("")  # small spacing

# ✅ Search stays top-of-page (outside dropdowns)
search_query = st.text_input(
    "Search (title / location / source)",
    value="",
    placeholder="Try: king george, port royal, landsearch, 20 acres…",
)

# ---------- Defaults (pull from json criteria if present) ----------
default_max_price = int(criteria.get("max_price", 600000) or 600000)
default_min_acres = float(criteria.get("min_acres", 11.0) or 11.0)
default_max_acres = float(criteria.get("max_acres", 50.0) or 50.0)

# ---------- Helpers ----------
def is_top_match(it: Dict[str, Any], min_a: float, max_a: float, max_p: int) -> bool:
    price = it.get("price")
    acres = it.get("acres")
    if price is None or acres is None:
        return False
    try:
        return (min_a <= float(acres) <= max_a) and (int(price) <= int(max_p))
    except Exception:
        return False

def searchable_text(it: Dict[str, Any]) -> str:
    return " ".join(
        [
            str(it.get("title", "")),
            str(it.get("source", "")),
            str(it.get("url", "")),
        ]
    ).lower()

def parse_dt(it: Dict[str, Any]) -> str:
    # scraper provides found_utc (recommended). if missing, sort falls back.
    return it.get("found_utc") or ""

def is_new(it: Dict[str, Any]) -> bool:
    # With your current setup, NEW = seen in this run (found_utc == last_updated_utc)
    # Works only if scraper preserves found_utc across runs (yours does ✅)
    try:
        return bool(it.get("found_utc")) and bool(last_updated) and it.get("found_utc") == last_updated
    except Exception:
        return False

# ---------- Dropdowns ----------
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

    # Top matches default ON
    show_top_matches_only = st.toggle("Top matches only", value=True)
    show_new_only = st.toggle("New only", value=False)
    sort_newest = st.toggle("Newest first", value=True)

    show_n = st.slider("Show how many", min_value=5, max_value=200, value=50, step=5)

# Compute counts for Details section
top_matches_all = [it for it in items if is_top_match(it, min_acres, max_acres, max_price)]
new_all = [it for it in items if is_new(it)]

with st.expander("Details", expanded=False):
    st.caption(f"Criteria: ${max_price:,.0f} max • {min_acres:g}–{max_acres:g} acres")

    c1, c2, c3 = st.columns(3)
    c1.metric("All found", f"{len(items)}")
    c2.metric("Top matches", f"{len(top_matches_all)}")
    c3.metric("New", f"{len(new_all)}")

st.divider()

# ---------- Apply filters ----------
filtered = items[:]

# Search first
if search_query.strip():
    q = search_query.strip().lower()
    filtered = [it for it in filtered if q in searchable_text(it)]

# New filter
if show_new_only:
    filtered = [it for it in filtered if is_new(it)]

# Top matches filter
if show_top_matches_only:
    filtered = [it for it in filtered if is_top_match(it, min_acres, max_acres, max_price)]

# Sorting
if sort_newest:
    filtered = sorted(filtered, key=parse_dt, reverse=True)

# Limit
filtered = filtered[:show_n]

# ---------- Listing cards ----------
def listing_card(it: Dict[str, Any]):
    title = it.get("title") or f"{it.get('source', 'Land')} listing"
    url = it.get("url") or ""
    source = it.get("source") or ""
    price = it.get("price")
    acres = it.get("acres")
    thumb = it.get("thumbnail")

    top_match = is_top_match(it, min_acres, max_acres, max_price)
    new_flag = is_new(it)

    # badge line
    badges = []
    if top_match:
        badges.append("⭐ Top match")
    if new_flag:
        badges.append("🆕 NEW")
    if not badges:
        badges.append("FOUND")

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

        st.caption(f"{' • '.join(badges)} • {source}")

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

# Grid (2 columns)
cols = st.columns(2)
for idx, it in enumerate(filtered):
    with cols[idx % 2]:
        listing_card(it)

if not filtered:
    st.info("No listings matched your current search/filters.")