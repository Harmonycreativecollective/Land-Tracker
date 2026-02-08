import base64
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import streamlit as st
from data_access import load_data

# ---------- Paths ----------
LOGO_PATH = Path("assets/kblogo.png")
PREVIEW_PATH = Path("assets/previewkb.png")  # branded placeholder

# ---------- Page config ----------
st.set_page_config(
    page_title="KB’s Land Tracker",
    page_icon=str(LOGO_PATH) if LOGO_PATH.exists() else "🗺️",
    layout="centered",
)

TITLE = "KB’s Land Tracker"
CAPTION = "What’s meant for you is already in motion."

# ---------- Load data ----------
data = load_data()
items: List[Dict[str, Any]] = data.get("items", []) or []
criteria = data.get("criteria", {}) or {}
last_updated = data.get("last_updated_utc")

# ---------- Time formatting (Eastern) ----------
def format_last_updated_et(ts: str) -> str:
    if not ts:
        return ""
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        from zoneinfo import ZoneInfo
        dt_et = dt.astimezone(ZoneInfo("America/New_York"))
        return dt_et.strftime("%b %d, %Y • %I:%M %p ET")
    except Exception:
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            return dt.strftime("%b %d, %Y • %I:%M %p")
        except Exception:
            return ts

# ---------- Header ----------
def render_header():
    logo_b64 = ""
    if LOGO_PATH.exists():
        logo_b64 = base64.b64encode(LOGO_PATH.read_bytes()).decode("utf-8")

    st.markdown(
        f"""
        <style>
          .kb-header {{
            display:flex;
            align-items:center;
            gap:16px;
            margin-top: 0.25rem;
            margin-bottom: 0.35rem;
          }}
          .kb-logo {{
            width:140px;
            height:140px;
            flex: 0 0 140px;
            border-radius: 16px;
            object-fit: contain;
          }}
          .kb-text {{
            flex: 1 1 auto;
            min-width: 0;
          }}
          .kb-title {{
            font-size: clamp(1.55rem, 3.3vw, 2.05rem);
            font-weight: 900;
            line-height: 1.05;
            margin: 0;
            color: #0f172a;
            overflow-wrap: anywhere;
            word-break: break-word;
          }}
          .kb-caption {{
            font-size: clamp(1.05rem, 2.5vw, 1.22rem);
            color: rgba(49, 51, 63, 0.75);
            margin-top: 8px;
            line-height: 1.35;
            overflow-wrap: anywhere;
            word-break: break-word;
          }}

          .kb-ph {{
            width:100%;
            height:220px;
            border-radius:16px;
            overflow:hidden;
            position:relative;
            display:flex;
            align-items:center;
            justify-content:center;
          }}
          .kb-ph img {{
            width:100%;
            height:100%;
            object-fit:cover;
            display:block;
          }}
          .kb-ph::after {{
            content:"";
            position:absolute;
            inset:0;
            background: linear-gradient(
              to bottom,
              rgba(255,255,255,0.0) 0%,
              rgba(255,255,255,0.30) 45%,
              rgba(255,255,255,0.70) 100%
            );
          }}
          .kb-ph-label {{
            position:absolute;
            z-index:2;
            text-align:center;
            font-weight:800;
            letter-spacing:0.2px;
            color: rgba(15, 23, 42, 0.78);
            padding: 10px 14px;
            border-radius: 999px;
            background: rgba(255,255,255,0.65);
            backdrop-filter: blur(6px);
            border: 1px solid rgba(15,23,42,0.08);
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

if last_updated:
    st.caption(f"Last updated: {format_last_updated_et(last_updated)}")

st.write("")

# ✅ Search stays top-of-page
search_query = st.text_input(
    "Search (title / location / source)",
    value="",
    placeholder="Try: king george, port royal, landwatch, 20 acres…",
)

# ---------- Defaults ----------
default_max_price = int(criteria.get("max_price", 600000) or 600000)
default_min_acres = float(criteria.get("min_acres", 10.0) or 10.0)
default_max_acres = float(criteria.get("max_acres", 50.0) or 50.0)

# ---------- Status helpers ----------
STATUS_EMOJI = {
    "available": "🟢 Available",
    "under_contract": "🟡 Under contract",
    "pending": "⏳ Pending",
    "sold": "🛑 Sold",
    "unknown": "⚪ Status unknown",
}

def get_status(it: Dict[str, Any]) -> str:
    s = (it.get("status") or "unknown").strip().lower()
    return s if s in STATUS_EMOJI else "unknown"

def is_unavailable(status: str) -> bool:
    return status in {"under_contract", "pending", "sold"}

# ---------- Match logic ----------
def meets_acres(it: Dict[str, Any], min_a: float, max_a: float) -> bool:
    acres = it.get("acres")
    if acres is None:
        return False
    try:
        return min_a <= float(acres) <= max_a
    except Exception:
        return False

def meets_price(it: Dict[str, Any], max_p: int) -> bool:
    price = it.get("price")
    if price is None:
        return False
    try:
        return int(price) <= int(max_p)
    except Exception:
        return False

def is_missing_price(it: Dict[str, Any]) -> bool:
    p = it.get("price")
    if p is None:
        return True
    if isinstance(p, str) and p.strip() == "":
        return True
    if p == 0:
        return True
    if isinstance(p, str):
        s = p.strip().lower()
        if s in {"n/a", "na", "none", "unknown", "call", "call for price", "contact"}:
            return True
    return False

def is_top_match(it: Dict[str, Any], min_a: float, max_a: float, max_p: int) -> bool:
    status = get_status(it)
    if is_unavailable(status):
        return False
    return meets_acres(it, min_a, max_a) and meets_price(it, max_p)

def is_possible_match(it: Dict[str, Any], min_a: float, max_a: float) -> bool:
    # Possible match = acres fits, but price missing
    status = get_status(it)
    if is_unavailable(status):
        return False
    if not meets_acres(it, min_a, max_a):
        return False
    return is_missing_price(it)

def searchable_text(it: Dict[str, Any]) -> str:
    return " ".join(
        [
            str(it.get("title", "")),
            str(it.get("county", "")),
            str(it.get("state", "")),
            str(it.get("source", "")),
            str(it.get("url", "")),
        ]
    ).lower()

def parse_dt(it: Dict[str, Any]) -> str:
    return it.get("found_utc") or ""

def is_new(it: Dict[str, Any]) -> bool:
    try:
        return bool(it.get("found_utc")) and bool(last_updated) and it.get("found_utc") == last_updated
    except Exception:
        return False

# ---------- Location options ----------
def norm_opt(x: Optional[str]) -> str:
    return (x or "").strip()

# ---------- Keep only real property pages ----------
def is_property_listing(it: Dict[str, Any]) -> bool:
    url = (it.get("url") or "").strip().lower()
    if not url:
        return False

    # LandSearch: property pages look like:
    # https://www.landsearch.com/properties/<slug...>/<numeric_id>
    if "landsearch.com" in url:
        parts = url.rstrip("/").split("/")
        return ("/properties/" in url) and parts[-1].isdigit()

    # LandWatch: property pages typically contain /property/
    if "landwatch.com" in url:
        return "/property/" in url

    # Unknown source: keep it (for future sites), but you can change to False if you want strict
    return True

# APPLY the property filter so junk nav pages disappear
items = [it for it in items if is_property_listing(it)]

states = sorted({norm_opt(it.get("state")) for it in items if norm_opt(it.get("state"))})
counties = sorted({norm_opt(it.get("county")) for it in items if norm_opt(it.get("county"))})

# ---------- Filters ----------
with st.expander("Filters", expanded=False):
    max_price = st.number_input("Max price (Top match)", min_value=0, value=default_max_price, step=10000)
    min_acres = st.number_input("Min acres", min_value=0.0, value=default_min_acres, step=1.0)
    max_acres = st.number_input("Max acres", min_value=0.0, value=default_max_acres, step=1.0)

    # Location filters (won't break if empty)
    selected_states = st.multiselect("State", options=states, default=states)
    selected_counties = st.multiselect("County", options=counties, default=counties)

    # Matching toggles
    show_top_only = st.toggle("✨ Top matches", value=True)   # default ON
    show_possible = st.toggle("🧩 Possible matches", value=False)

    show_new_only = st.toggle("🆕 New only", value=False)
    sort_newest = st.toggle("Newest first", value=True)
    show_n = st.slider("Show how many", min_value=5, max_value=200, value=50, step=5)

# ---------- Location filter ----------
def passes_location(it: Dict[str, Any]) -> bool:
    st_ = norm_opt(it.get("state"))
    co_ = norm_opt(it.get("county"))

    # If scraper doesn't provide location fields yet, don't filter
    if not states and not counties:
        return True

    # If user selected some states and item has state, enforce it
    if selected_states and st_ and st_ not in selected_states:
        return False

    # If user selected some counties and item has county, enforce it
    if selected_counties and co_ and co_ not in selected_counties:
        return False

    # Missing state/county stays visible
    return True

loc_items = [it for it in items if passes_location(it)]

# ---------- Details counts ----------
top_matches_all = [it for it in loc_items if is_top_match(it, min_acres, max_acres, max_price)]
possible_all = [it for it in loc_items if is_possible_match(it, min_acres, max_acres)]
new_all = [it for it in loc_items if is_new(it)]

with st.expander("Details", expanded=False):
    st.caption(f"Criteria: ${max_price:,.0f} max • {min_acres:g}–{max_acres:g} acres")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("All listings", f"{len(loc_items)}")
    c2.metric("Top matches", f"{len(top_matches_all)}")
    c3.metric("Possible matches", f"{len(possible_all)}")
    c4.metric("New", f"{len(new_all)}")

    # Helpful debug to see what scraper is actually returning
    with st.expander("Debug (first 5 items)", expanded=False):
        st.json(loc_items[:5])

st.divider()

# ---------- Apply filters ----------
filtered = loc_items[:]

if search_query.strip():
    q = search_query.strip().lower()
    filtered = [it for it in filtered if q in searchable_text(it)]

if show_new_only:
    filtered = [it for it in filtered if is_new(it)]

# Matching rules
if show_top_only:
    allowed = []
    for it in filtered:
        if is_top_match(it, min_acres, max_acres, max_price):
            allowed.append(it)
        elif show_possible and is_possible_match(it, min_acres, max_acres):
            allowed.append(it)
    filtered = allowed
else:
    # If not "top only", optionally hide possibles
    if not show_possible:
        filtered = [it for it in filtered if not is_possible_match(it, min_acres, max_acres)]

# Sorting
def sort_key(it: Dict[str, Any]):
    if is_top_match(it, min_acres, max_acres, max_price):
        tier = 3
    elif is_possible_match(it, min_acres, max_acres):
        tier = 2
    else:
        tier = 1
    return (tier, parse_dt(it))

if sort_newest:
    filtered = sorted(filtered, key=sort_key, reverse=True)

filtered = filtered[:show_n]

# ---------- Placeholder renderer ----------
def render_placeholder():
    if PREVIEW_PATH.exists():
        ph_b64 = base64.b64encode(PREVIEW_PATH.read_bytes()).decode("utf-8")
        st.markdown(
            f"""
            <div class="kb-ph">
              <img src="data:image/png;base64,{ph_b64}" />
              <div class="kb-ph-label">Preview not available</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            """
            <div style="width:100%; height:220px; background:#f2f2f2; border-radius:16px;
                        display:flex; align-items:center; justify-content:center; color:#777;
                        font-weight:700;">
                Preview not available
            </div>
            """,
            unsafe_allow_html=True,
        )

# ---------- Listing cards ----------
def listing_card(it: Dict[str, Any]):
    title = it.get("title") or f"{it.get('source', 'Land')} listing"
    url = it.get("url") or ""
    source = it.get("source") or ""
    price = it.get("price")
    acres = it.get("acres")
    thumb = it.get("thumbnail")
    st_ = it.get("state") or ""
    co_ = it.get("county") or ""

    status = get_status(it)
    status_badge = STATUS_EMOJI.get(status, STATUS_EMOJI["unknown"])

    top = is_top_match(it, min_acres, max_acres, max_price)
    possible = is_possible_match(it, min_acres, max_acres)
    new_flag = is_new(it)

    badges = []
    if top:
        badges.append("✨️ Top match")
    elif possible:
        badges.append("🧩 Possible match")
    else:
        badges.append("🔎 Found")

    if new_flag:
        badges.append("🆕 NEW")

    badges.append(status_badge)

    loc_line = " • ".join([x for x in [co_, st_] if x])

    with st.container(border=True):
        if thumb:
            st.image(thumb, use_container_width=True)
        else:
            render_placeholder()

        st.subheader(title)

        meta_bits = [" • ".join(badges), source]
        if loc_line:
            meta_bits.insert(1, loc_line)
        st.caption(" • ".join(meta_bits))

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

# Grid (2 columns)
cols = st.columns(2)
for idx, it in enumerate(filtered):
    with cols[idx % 2]:
        listing_card(it)

if not filtered:
    st.info("No listings matched your current search/filters.")

