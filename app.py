import base64
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import requests
import streamlit as st

from data_access import load_data

# ---------- Paths ----------
LOGO_PATH = Path("assets/kblogo.png")

# ---------- Page config ----------
st.set_page_config(
    page_title="Dashboard – KB’s Land Tracker",
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
            flex-wrap: wrap;
          }}
          .kb-logo {{
            width:140px;
            height:140px;
            flex: 0 0 auto;
            border-radius: 18px;
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

          .kb-tiles {{
            display:grid;
            grid-template-columns: 1fr 1fr;
            gap: 12px;
          }}
          .kb-tile {{
            border: 1px solid rgba(15,23,42,0.10);
            border-radius: 18px;
            padding: 14px 14px;
            background: rgba(255,255,255,0.9);
            box-shadow: 0 6px 18px rgba(15,23,42,0.06);
          }}
          .kb-tile-label {{
            font-size: 0.95rem;
            color: rgba(15,23,42,0.70);
            margin: 0 0 6px 0;
            font-weight: 700;
          }}
          .kb-tile-value {{
            font-size: 1.9rem;
            font-weight: 900;
            line-height: 1.0;
            color: rgba(15,23,42,0.92);
            margin: 0;
          }}
          .kb-tile-sub {{
            margin-top: 6px;
            font-size: 0.9rem;
            color: rgba(15,23,42,0.55);
            font-weight: 600;
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

# ---------- Thumbnail renderer (server-side fetch + fallback) ----------
def render_thumb(url: str, height: int = 140):
    try:
        if not url:
            st.markdown(
                f"<div style='width:100%;height:{height}px;border-radius:16px;background:#f2f2f2;'></div>",
                unsafe_allow_html=True,
            )
            return

        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200 and r.content:
            st.image(r.content, use_container_width=True)
        else:
            st.markdown(
                f"<div style='width:100%;height:{height}px;border-radius:16px;background:#f2f2f2;'></div>",
                unsafe_allow_html=True,
            )
    except Exception:
        st.markdown(
            f"<div style='width:100%;height:{height}px;border-radius:16px;background:#f2f2f2;'></div>",
            unsafe_allow_html=True,
        )

if last_updated:
    st.caption(f"Last updated: {format_last_updated_et(last_updated)}")

st.write("")

# ---------- Match logic (same as Properties defaults) ----------
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

# ---------- Dashboard metrics ----------
top_matches = [it for it in items if is_top_match(it)]
possible_matches = [it for it in items if is_possible_match(it)]
new_items = [it for it in items if is_new(it)]

st.caption(f"Criteria: ${default_max_price:,.0f} max • {default_min_acres:g}–{default_max_acres:g} acres")

st.markdown(
    f"""
    <div class="kb-tiles">
      <div class="kb-tile">
        <div class="kb-tile-label">All found</div>
        <div class="kb-tile-value">{len(items)}</div>
        <div class="kb-tile-sub">Total listings</div>
      </div>
      <div class="kb-tile">
        <div class="kb-tile-label">Top matches</div>
        <div class="kb-tile-value">{len(top_matches)}</div>
        <div class="kb-tile-sub">Meets acres + price</div>
      </div>
      <div class="kb-tile">
        <div class="kb-tile-label">Possible matches</div>
        <div class="kb-tile-value">{len(possible_matches)}</div>
        <div class="kb-tile-sub">Price missing</div>
      </div>
      <div class="kb-tile">
        <div class="kb-tile-label">New</div>
        <div class="kb-tile-value">{len(new_items)}</div>
        <div class="kb-tile-sub">Since last run</div>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# Big mobile-friendly CTA to Properties
if st.button("View all properties →", use_container_width=True):
    st.switch_page("pages/2_properties.py")

st.divider()

# ---------- Quick Top Matches (now with thumbnails) ----------
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
        thumb = it.get("thumbnail") or ""

        line_bits = []
        if acres is not None:
            try:
                line_bits.append(f"{float(acres):g} acres")
            except Exception:
                line_bits.append(f"{acres} acres")
        if price is not None:
            try:
                line_bits.append(f"${int(price):,}")
            except Exception:
                line_bits.append(str(price))

        with st.container(border=True):
            render_thumb(thumb, height=160)

            st.write(f"**{title}**")
            if line_bits:
                st.caption(" • ".join(line_bits))
            if url:
                st.link_button("Open listing ↗", url, use_container_width=True)

st.divider()
st.caption("Tip: Use Properties to search, filter, and view all listings.")
