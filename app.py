import base64
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import streamlit as st

# ---------- Paths ----------
DATA_PATH = Path("data/listings.json")
LOGO_PATH = Path("assets/kblogo.png")
PREVIEW_PATH = Path("assets/previewkb.png")  # your placeholder image

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

# ---------- Header (logo left, text right) ----------
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

def is_top_match(it: Dict[str, Any], min_a: float, max_a: float, max_p: int) -> bool:
    status = get_status(it)
    if is_unavailable(status):
        return False
    return meets_acres(it, min_a, max_a) and meets_price(it, max_p)

def is_possible_match(it: Dict[str, Any], min_a: float, max_a: float) -> bool:
    # Possible = acres fits, price missing, and it isn't unavailable
    status = get_status(it)
    if is_unavailable(status):
        return False
    if not meets_acres(it, min_a, max_a):
        return False
    return it.get("price") is None

def is_former_top_match(it: Dict[str, Any]) -> bool:
    # Former top match = ever was top match + now unavailable
    status = get_status(it)
    if not is_unavailable(status):
        return False
    return bool(it.get("ever_top_match", False))

def searchable_text(it: Dict[str, Any]) -> str:
    return " ".join(
        [
            str(it.get("title", "")),
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

    show_top_matches_only = st.toggle("✨ Top matches only", value=True)
    show_possible_matches = st.toggle("🧩 Include possible matches", value=False)
    show_former_top_matches = st.toggle("⭐ Former top matches", value=False)

    show_new_only = st.toggle("🆕 New only", value=False)
    sort_newest = st.toggle("Newest first", value=True)

    show_n = st.slider("Show how many", min_value=5, max_value=200, value=50, step=5)

# ---------- Details counts ----------
top_matches_all = [it for it in items if is_top_match(it, min_acres, max_acres, max_price)]
possible_all = [it for it in items if is_possible_match(it, min_acres, max_acres)]
former_all = [it for it in items if is_former_top_match(it)]
new_all = [it for it in items if is_new(it)]

with st.expander("Details", expanded=False):
    st.caption(f"Criteria: ${max_price:,.0f} max • {min_acres:g}–{max_acres:g} acres")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("All found", f"{len(items)}")
    c2.metric("Top matches", f"{len(top_matches_all)}")
    c3.metric("Possible matches", f"{len(possible_all)}")
    c4.metric("New", f"{len(new_all)}")

    if len(former_all) > 0:
        st.caption(f"Former top matches available: {len(former_all)} (toggle in Filters)")

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

# Mode logic
if show_top_matches_only:
    allowed: List[Dict[str, Any]] = []
    for it in filtered:
        if is_top_match(it, min_acres, max_acres, max_price):
            allowed.append(it)
        elif show_possible_matches and is_possible_match(it, min_acres, max_acres):
            allowed.append(it)

    # Never show former in Top-only mode
    allowed = [it for it in allowed if not is_former_top_match(it)]
    filtered = allowed
else:
    # If Former toggle OFF, remove them
    if not show_former_top_matches:
        filtered = [it for it in filtered if not is_former_top_match(it)]

    # If Possible toggle OFF, remove possibles
    if not show_possible_matches:
        filtered = [it for it in filtered if not is_possible_match(it, min_acres, max_acres)]

# ---------- Sorting: Top first, then Possible, then Former, then Found (each newest-first) ----------
def tier(it: Dict[str, Any]) -> int:
    if is_top_match(it, min_acres, max_acres, max_price):
        return 4
    if is_possible_match(it, min_acres, max_acres):
        return 3
    if is_former_top_match(it):
        return 2
    return 1

def sort_key(it: Dict[str, Any]):
    # tuple sorts by tier then date
    return (tier(it), parse_dt(it))

if sort_newest:
    filtered = sorted(filtered, key=sort_key, reverse=True)

# Limit
filtered = filtered[:show_n]

# ---------- Placeholder renderer (fixed height + soft fade) ----------
def render_placeholder(source: str):
    # fixed frame so the image never gets “giant”
    # uses your PREVIEW_PATH if present
    img_b64 = ""
    if PREVIEW_PATH.exists():
        img_b64 = base64.b64encode(PREVIEW_PATH.read_bytes()).decode("utf-8")

    # soft gradient “fade” behind the image + centered label close to it
    st.markdown(
        f"""
        <style>
          .kb-ph-wrap {{
            width: 100%;
            height: 240px;
            border-radius: 16px;
            overflow: hidden;
            position: relative;
            background: linear-gradient(180deg, rgba(255,255,255,0.0) 0%, rgba(0,0,0,0.04) 70%, rgba(0,0,0,0.06) 100%);
            display: flex;
            align-items: center;
            justify-content: center;
          }}
          .kb-ph-img {{
            max-height: 210px;
            width: 100%;
            object-fit: contain;
            display:block;
          }}
          .kb-ph-label {{
            text-align:center;
            margin-top: 6px;
            margin-bottom: 2px;
            color: rgba(49, 51, 63, 0.65);
            font-weight: 500;
          }}
        </style>

        <div class="kb-ph-wrap">
          {f"<img class='kb-ph-img' src='data:image/png;base64,{img_b64}' />" if img_b64 else ""}
        </div>
        <div class="kb-ph-label">Preview not available</div>
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

    status = get_status(it)
    status_badge = STATUS_EMOJI.get(status, STATUS_EMOJI["unknown"])

    top = is_top_match(it, min_acres, max_acres, max_price)
    possible = is_possible_match(it, min_acres, max_acres)
    former = is_former_top_match(it)
    new_flag = is_new(it)

    badges: List[str] = []
    if top:
        badges.append("✨️ Top match")
    elif possible:
        badges.append("🧩 Possible match")
    elif former:
        badges.append("⭐ Former top match")
    else:
        badges.append("🔎 Found")

    if new_flag:
        badges.append("🆕 NEW")

    badges.append(status_badge)

    with st.container(border=True):
        if thumb:
            st.image(thumb, use_container_width=True)
        else:
            render_placeholder(source)

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

# ---------- Sections renderer (optional but nice) ----------
def render_section(title: str, section_items: List[Dict[str, Any]]):
    if not section_items:
        return
    st.markdown(f"### {title} ({len(section_items)})")
    cols = st.columns(2)
    for i, it in enumerate(section_items):
        with cols[i % 2]:
            listing_card(it)

# Build buckets from filtered (already search/new/mode filtered)
tops = [it for it in filtered if is_top_match(it, min_acres, max_acres, max_price)]
possibles = [it for it in filtered if is_possible_match(it, min_acres, max_acres)]
formers = [it for it in filtered if is_former_top_match(it)]
found = [it for it in filtered if it not in tops and it not in possibles and it not in formers]

# Render sections in order
if show_top_matches_only:
    render_section("✨ Top matches", tops)
    if show_possible_matches:
        render_section("🧩 Possible matches", possibles)
else:
    render_section("✨ Top matches", tops)
    if show_possible_matches:
        render_section("🧩 Possible matches", possibles)
    if show_former_top_matches:
        render_section("⭐ Former top matches", formers)
    render_section("🔎 Found", found)

if not filtered:
    st.info("No listings matched your current search/filters.")