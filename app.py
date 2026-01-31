import base64
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import streamlit as st

# ---------- Paths ----------
DATA_PATH = Path("data/listings.json")
LOGO_PATH = Path("assets/kblogo.png")
PREVIEW_PATH = Path("assets/previewkb.png")

# ---------- Page config ----------
st.set_page_config(
    page_title="KB’s Land Tracker",
    page_icon=str(LOGO_PATH) if LOGO_PATH.exists() else "🗺️",
    layout="wide",
)

TITLE = "KB’s Land Tracker"
CAPTION = "What’s meant for you is already in motion."

# ---------- Helpers ----------
def image_as_base64(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("utf-8")

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
        return ts

# ---------- Header ----------
def render_header():
    logo_b64 = image_as_base64(LOGO_PATH) if LOGO_PATH.exists() else ""

    st.markdown(
        f"""
        <style>
          .kb-header {{
            display:flex;
            align-items:center;
            gap:16px;
            margin-top:0.25rem;
            margin-bottom:0.35rem;
          }}
          .kb-logo {{
            width:140px;
            height:140px;
            flex:0 0 140px;
            border-radius:16px;
            object-fit:contain;
          }}
          .kb-title {{
            font-size:clamp(1.55rem, 3.3vw, 2.05rem);
            font-weight:900;
            line-height:1.05;
            margin:0;
            color:#0f172a;
          }}
          .kb-caption {{
            font-size:clamp(1.05rem, 2.5vw, 1.22rem);
            color:rgba(49,51,63,0.75);
            margin-top:8px;
            line-height:1.35;
          }}
        </style>

        <div class="kb-header">
          <img class="kb-logo" src="data:image/png;base64,{logo_b64}" />
          <div>
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

# ---------- Search ----------
search_query = st.text_input(
    "Search (title / location / source)",
    value="",
    placeholder="Try: king george, port royal, landsearch, 20 acres…",
)

# ---------- Defaults ----------
default_max_price = int(criteria.get("max_price", 600000))
default_min_acres = float(criteria.get("min_acres", 11.0))
default_max_acres = float(criteria.get("max_acres", 50.0))

# ---------- Status ----------
STATUS_EMOJI = {
    "available": "🟢 Available",
    "under_contract": "🟡 Under contract",
    "pending": "⏳ Pending",
    "sold": "🛑 Sold",
    "unknown": "⚪ Status unknown",
}

def get_status(it):
    s = (it.get("status") or "unknown").lower()
    return s if s in STATUS_EMOJI else "unknown"

def is_unavailable(status):
    return status in {"under_contract", "pending", "sold"}

# ---------- Match logic ----------
def meets_acres(it, min_a, max_a):
    try:
        return min_a <= float(it.get("acres")) <= max_a
    except Exception:
        return False

def meets_price(it, max_p):
    try:
        return int(it.get("price")) <= max_p
    except Exception:
        return False

def is_top_match(it, min_a, max_a, max_p):
    return not is_unavailable(get_status(it)) and meets_acres(it, min_a, max_a) and meets_price(it, max_p)

def is_possible_match(it, min_a, max_a):
    return not is_unavailable(get_status(it)) and meets_acres(it, min_a, max_a) and it.get("price") is None

def is_former_top_match(it):
    return is_unavailable(get_status(it)) and it.get("ever_top_match", False)

def searchable_text(it):
    return f"{it.get('title','')} {it.get('source','')} {it.get('url','')}".lower()

def parse_dt(it):
    return it.get("found_utc") or ""

def is_new(it):
    return it.get("found_utc") == last_updated if last_updated else False

# ---------- Filters ----------
with st.expander("Filters", expanded=False):
    max_price = st.number_input("Max price", 0, value=default_max_price, step=10000)
    min_acres = st.number_input("Min acres", 0.0, value=default_min_acres, step=1.0)
    max_acres = st.number_input("Max acres", 0.0, value=default_max_acres, step=1.0)

    show_top_only = st.toggle("✨ Top matches only", value=True)
    show_possible = st.toggle("🧩 Include possible matches", value=False)
    show_former = st.toggle("⭐ Former top matches", value=False)

    show_new_only = st.toggle("🆕 New only", value=False)
    sort_newest = st.toggle("Newest first", value=True)

    show_n = st.slider("Show how many", 5, 200, 50, 5)

# ---------- Apply filters ----------
filtered = items[:]

if search_query.strip():
    q = search_query.lower()
    filtered = [it for it in filtered if q in searchable_text(it)]

if show_new_only:
    filtered = [it for it in filtered if is_new(it)]

if show_top_only:
    filtered = [
        it for it in filtered
        if is_top_match(it, min_acres, max_acres, max_price)
        or (show_possible and is_possible_match(it, min_acres, max_acres))
    ]
else:
    if not show_former:
        filtered = [it for it in filtered if not is_former_top_match(it)]
    if not show_possible:
        filtered = [it for it in filtered if not is_possible_match(it, min_acres, max_acres)]

def sort_key(it):
    if is_top_match(it, min_acres, max_acres, max_price):
        tier = 4
    elif is_possible_match(it, min_acres, max_acres):
        tier = 3
    elif is_former_top_match(it):
        tier = 2
    else:
        tier = 1
    return (tier, parse_dt(it))

if sort_newest:
    filtered = sorted(filtered, key=sort_key, reverse=True)

filtered = filtered[:show_n]

# ---------- Listing cards ----------
def listing_card(it):
    title = it.get("title") or f"{it.get('source','Listing')} listing"
    url = it.get("url")
    source = it.get("source")
    price = it.get("price")
    acres = it.get("acres")
    thumb = it.get("thumbnail")

    badges = []
    if is_top_match(it, min_acres, max_acres, max_price):
        badges.append("✨️ Top match")
    elif is_possible_match(it, min_acres, max_acres):
        badges.append("🧩 Possible match")
    elif is_former_top_match(it):
        badges.append("⭐ Former top match")
    else:
        badges.append("🔎 Found")

    if is_new(it):
        badges.append("🆕 NEW")

    badges.append(STATUS_EMOJI[get_status(it)])

    with st.container(border=True):
        if thumb:
            st.image(thumb, use_container_width=True)
        elif PREVIEW_PATH.exists():
            preview_b64 = image_as_base64(PREVIEW_PATH)
            st.markdown(
                f"""
                <div style="width:100%; text-align:center;">
                  <div style="position:relative; border-radius:16px; overflow:hidden;">
                    <img src="data:image/png;base64,{preview_b64}"
                         style="width:100%; opacity:0.92;" />
                    <div style="
                        position:absolute; inset:0;
                        background:linear-gradient(
                          to bottom,
                          rgba(255,255,255,0.00) 60%,
                          rgba(255,255,255,0.28) 100%
                        );
                    "></div>
                  </div>
                  <div style="
                      margin-top:6px;
                      font-size:0.85rem;
                      color:rgba(49,51,63,0.6);
                  ">
                      Preview not available
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.subheader(title)
        st.caption(f"{' • '.join(badges)} • {source}")

        st.write(f"**Price:** ${int(price):,}" if price else "**Price:** —")
        st.write(f"**Acres:** {float(acres):g}" if acres else "**Acres:** —")

        if url:
            st.link_button("Open listing ↗", url, use_container_width=True)

# ---------- Grid ----------
cols = st.columns(2)
for i, it in enumerate(filtered):
    with cols[i % 2]:
        listing_card(it)

if not filtered:
    st.info("No listings matched your current filters.")