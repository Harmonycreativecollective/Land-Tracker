import base64
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import streamlit as st

# ---------- Paths ----------
DATA_PATH = Path("data/listings.json")
LOGO_PATH = Path("assets/kblogo.png")
PREVIEW_PATH = Path("assets/previewkb.png")  # placeholder image (NO TEXT)

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
          .kb-title {{
            font-size: clamp(1.55rem, 3.3vw, 2.05rem);
            font-weight: 900;
            margin: 0;
            color: #0f172a;
          }}
          .kb-caption {{
            font-size: clamp(1.05rem, 2.5vw, 1.22rem);
            color: rgba(49, 51, 63, 0.75);
            margin-top: 8px;
          }}
        </style>

        <div class="kb-header">
          {"<img class='kb-logo' src='data:image/png;base64," + logo_b64 + "' />" if logo_b64 else ""}
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
    return is_unavailable(get_status(it)) and bool(it.get("ever_top_match"))

def searchable_text(it):
    return f"{it.get('title','')} {it.get('source','')} {it.get('url','')}".lower()

def is_new(it):
    return it.get("found_utc") == last_updated

# ---------- Filters ----------
with st.expander("Filters", expanded=False):
    max_price = st.number_input("Max price", 0, value=default_max_price, step=10000)
    min_acres = st.number_input("Min acres", 0.0, value=default_min_acres, step=1.0)
    max_acres = st.number_input("Max acres", 0.0, value=default_max_acres, step=1.0)

    show_top_only = st.toggle("✨ Top matches only", value=True)
    show_possible = st.toggle("🧩 Include possible matches", value=False)
    show_former = st.toggle("⭐ Former top matches", value=False)
    show_new_only = st.toggle("🆕 New only", value=False)

    show_n = st.slider("Show how many", 5, 200, 50, 5)

# ---------- Filtering ----------
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
    filtered = [it for it in filtered if not is_former_top_match(it)]
else:
    if not show_possible:
        filtered = [it for it in filtered if not is_possible_match(it, min_acres, max_acres)]
    if not show_former:
        filtered = [it for it in filtered if not is_former_top_match(it)]

# ---------- Sorting ----------
def sort_key(it):
    if is_top_match(it, min_acres, max_acres, max_price):
        tier = 4
    elif is_possible_match(it, min_acres, max_acres):
        tier = 3
    elif is_former_top_match(it):
        tier = 2
    else:
        tier = 1
    return (tier, it.get("found_utc") or "")

filtered = sorted(filtered, key=sort_key, reverse=True)[:show_n]

# ---------- Placeholder ----------
def render_placeholder(source: str):
    if PREVIEW_PATH.exists():
        st.image(str(PREVIEW_PATH), use_container_width=True)
    st.caption(f"Preview not available • {source or 'Unknown'}")

# ---------- Listing cards ----------
cols = st.columns(2)
for idx, it in enumerate(filtered):
    with cols[idx % 2]:
        with st.container(border=True):
            if it.get("thumbnail"):
                try:
                    st.image(it["thumbnail"], use_container_width=True)
                except Exception:
                    render_placeholder(it.get("source"))
            else:
                render_placeholder(it.get("source"))

            badges = []
            if is_top_match(it, min_acres, max_acres, max_price):
                badges.append("✨ Top match")
            elif is_possible_match(it, min_acres, max_acres):
                badges.append("🧩 Possible match")
            elif is_former_top_match(it):
                badges.append("⭐ Former top match")
            else:
                badges.append("🔎 Found")

            if is_new(it):
                badges.append("🆕 NEW")

            badges.append(STATUS_EMOJI[get_status(it)])

            st.subheader(it.get("title", "Land listing"))
            st.caption(" • ".join(badges) + f" • {it.get('source','')}")

            st.write(f"**Price:** ${int(it['price']):,}" if it.get("price") else "**Price:** —")
            st.write(f"**Acres:** {it['acres']}" if it.get("acres") else "**Acres:** —")

            if it.get("url"):
                st.link_button("Open listing ↗", it["url"], use_container_width=True)

if not filtered:
    st.info("No listings matched your current filters.")