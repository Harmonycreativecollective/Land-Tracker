import base64
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import streamlit as st
from data_access import load_data

# ---------- Paths ----------
LOGO_PATH = Path("assets/kblogo.png")

# ---------- Page config ----------
st.set_page_config(
    page_title="KB’s Land Tracker",
    page_icon=str(LOGO_PATH) if LOGO_PATH.exists() else "🗺️",
    layout="centered",
)

TITLE = "KB’s Land Tracker"
CAPTION = "What’s meant for you is already in motion."

# ---------- Time formatting (Eastern) ----------
def format_last_updated_et(ts: str | None) -> str:
    if not ts:
        return "—"
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        from zoneinfo import ZoneInfo
        dt_et = dt.astimezone(ZoneInfo("America/New_York"))
        return dt_et.strftime("%b %d, %Y • %I:%M %p ET")
    except Exception:
        return ts or "—"

# ---------- Load data ----------
data = load_data()
items: List[Dict[str, Any]] = data.get("items", []) or []
criteria = data.get("criteria", {}) or {}
last_updated = data.get("last_updated_utc")

# NOTE: We are intentionally NOT showing criteria on the dashboard.

# ---------- Match logic ----------
default_max_price = int(criteria.get("max_price", 600000) or 600000)
default_min_acres = float(criteria.get("min_acres", 10.0) or 10.0)
default_max_acres = float(criteria.get("max_acres", 50.0) or 50.0)

STATUS_VALUES_UNAVAILABLE = {"under_contract", "pending", "sold"}

def get_status(it: Dict[str, Any]) -> str:
    return (it.get("status") or "unknown").strip().lower()

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

def is_top_match(it: Dict[str, Any]) -> bool:
    if get_status(it) in STATUS_VALUES_UNAVAILABLE:
        return False
    return meets_acres(it, default_min_acres, default_max_acres) and meets_price(it, default_max_price)

def is_possible_match(it: Dict[str, Any]) -> bool:
    if get_status(it) in STATUS_VALUES_UNAVAILABLE:
        return False
    if not meets_acres(it, default_min_acres, default_max_acres):
        return False
    return is_missing_price(it)

def is_new(it: Dict[str, Any]) -> bool:
    try:
        return bool(it.get("found_utc")) and bool(last_updated) and it.get("found_utc") == last_updated
    except Exception:
        return False

top_matches = [it for it in items if is_top_match(it)]
possible_matches = [it for it in items if is_possible_match(it)]
new_items = [it for it in items if is_new(it)]

# ---------- Header (safe HTML, but only for layout/branding) ----------
logo_b64 = base64.b64encode(LOGO_PATH.read_bytes()).decode("utf-8") if LOGO_PATH.exists() else ""

st.markdown(
    f"""
    <style>
      .kb-header {{
        display:flex;
        align-items:center;
        gap:18px;
        flex-wrap: wrap;
        margin-top: 0.25rem;
        margin-bottom: 0.35rem;
      }}
      .kb-logo {{
        width:140px;
        height:140px;
        flex: 0 0 auto;
        border-radius: 22px;
        object-fit: contain;
      }}
      .kb-text {{
        flex: 1 1 auto;
        min-width: 240px;
      }}
      .kb-title {{
        font-size: clamp(2.0rem, 4vw, 2.8rem);
        font-weight: 950;
        line-height: 1.05;
        margin: 0;
        color: #0f172a;
      }}
      .kb-caption {{
        font-size: clamp(1.05rem, 2.2vw, 1.25rem);
        color: rgba(15, 23, 42, 0.62);
        margin-top: 10px;
        font-weight: 750;
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

# ---------- Last updated bar (FULL WIDTH card) ----------
with st.container(border=True):
    st.caption("Last updated")
    st.write(f"**{format_last_updated_et(last_updated)}**")

st.write("")

# ---------- Tiles (2x2) ----------
c1, c2 = st.columns(2)
c3, c4 = st.columns(2)

with c1:
    st.metric("All found", f"{len(items)}", help="Total listings loaded")
with c2:
    st.metric("Top matches", f"{len(top_matches)}", help="Meets target acres + max price")
with c3:
    st.metric("New", f"{len(new_items)}", help="Found exactly at the most recent run time")
with c4:
    st.metric("Possible", f"{len(possible_matches)}", help="Acre range fits but price is missing")

st.write("")
if st.button("View all properties →", use_container_width=True):
    st.switch_page("pages/2_properties.py")

st.divider()

# ---------- Quick Top Matches ----------
st.subheader("Top matches (quick view)")

if not top_matches:
    st.info("No top matches right now. Check Properties for everything found.")
else:
    def key_dt(it: Dict[str, Any]) -> str:
        return it.get("found_utc") or ""

    top_sorted = sorted(top_matches, key=key_dt, reverse=True)[:5]

    for it in top_sorted:
        title = it.get("title") or f"{it.get('source', 'Land')} listing"
        url = it.get("url") or ""
        price = it.get("price")
        acres = it.get("acres")
        thumb = it.get("thumbnail")

        with st.container(border=True):
            if thumb:
                st.image(thumb, use_container_width=True)

            bits = []
            if acres is not None:
                try:
                    bits.append(f"{float(acres):g} acres")
                except Exception:
                    bits.append(f"{acres} acres")
            if price is not None:
                try:
                    bits.append(f"${int(price):,}")
                except Exception:
                    bits.append(str(price))

            st.write(f"**{title}**")
            if bits:
                st.caption(" • ".join(bits))
            if url:
                st.link_button("Open listing ↗", url, use_container_width=True)

st.caption("Tip: Use Properties to search, filter, and view all listings.")

