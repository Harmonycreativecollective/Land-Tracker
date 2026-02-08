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
def render_header(last_updated: str | None):
    logo_b64 = ""
    if LOGO_PATH.exists():
        logo_b64 = base64.b64encode(LOGO_PATH.read_bytes()).decode("utf-8")

    updated_text = format_last_updated_et(last_updated) if last_updated else "—"

    st.markdown(
        f"""
        <style>
          /* tighten page container a bit */
          .block-container {{
            padding-top: 2.0rem;
            padding-bottom: 2.5rem;
            max-width: 980px;
          }}

          .kb-hero {{
            border: 1px solid rgba(15,23,42,0.08);
            border-radius: 24px;
            padding: 18px 18px;
            background: rgba(255,255,255,0.92);
            box-shadow: 0 10px 30px rgba(15,23,42,0.06);
            margin-bottom: 14px;
          }}

          .kb-header {{
            display:flex;
            align-items:center;
            gap:16px;
            flex-wrap: wrap;
          }}

          .kb-logo {{
            width: 120px;
            height: 120px;
            border-radius: 20px;
            object-fit: contain;
            flex: 0 0 auto;
          }}

          .kb-text {{
            flex: 1 1 auto;
            min-width: 220px;
          }}

          .kb-title {{
            font-size: clamp(1.9rem, 3.2vw, 2.45rem);
            font-weight: 950;
            line-height: 1.05;
            margin: 0;
            color: #0f172a;
          }}

          .kb-caption {{
            font-size: clamp(1.05rem, 1.8vw, 1.2rem);
            color: rgba(15, 23, 42, 0.62);
            margin-top: 8px;
            font-weight: 700;
          }}

          .kb-meta {{
            display:flex;
            gap:10px;
            flex-wrap: wrap;
            margin-top: 12px;
          }}

          .kb-chip {{
            border: 1px solid rgba(15,23,42,0.10);
            background: rgba(248,250,252,0.85);
            border-radius: 999px;
            padding: 8px 12px;
            display:flex;
            gap:8px;
            align-items: baseline;
          }}

          .kb-chip-label {{
            font-size: 0.85rem;
            color: rgba(15,23,42,0.60);
            font-weight: 800;
          }}

          .kb-chip-value {{
            font-size: 0.90rem;
            color: rgba(15,23,42,0.88);
            font-weight: 900;
          }}

          /* tiles: 3 per row on desktop, 2 on tablet, 1 on mobile */
          .kb-tiles {{
            display:grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 12px;
            margin-top: 12px;
          }}

          @media (max-width: 920px) {{
            .kb-tiles {{
              grid-template-columns: repeat(2, minmax(0, 1fr));
            }}
          }}

          @media (max-width: 520px) {{
            .kb-tiles {{
              grid-template-columns: 1fr;
            }}
          }}

          .kb-tile {{
            border: 1px solid rgba(15,23,42,0.10);
            border-radius: 18px;
            padding: 12px 12px;
            background: rgba(255,255,255,0.92);
            box-shadow: 0 8px 22px rgba(15,23,42,0.05);
          }}

          .kb-tile-label {{
            font-size: 0.90rem;
            color: rgba(15,23,42,0.62);
            margin: 0 0 6px 0;
            font-weight: 800;
          }}

          .kb-tile-value {{
            font-size: 1.55rem;
            font-weight: 950;
            line-height: 1.0;
            color: rgba(15,23,42,0.92);
            margin: 0;
          }}

          .kb-tile-sub {{
            margin-top: 6px;
            font-size: 0.85rem;
            color: rgba(15,23,42,0.52);
            font-weight: 700;
          }}
        </style>

        <div class="kb-hero">
          <div class="kb-header">
            {"<img class='kb-logo' src='data:image/png;base64," + logo_b64 + "' />" if logo_b64 else ""}
            <div class="kb-text">
              <div class="kb-title">{TITLE}</div>
              <div class="kb-caption">{CAPTION}</div>

              <div class="kb-meta">
                <div class="kb-chip">
                  <div class="kb-chip-label">Last updated</div>
                  <div class="kb-chip-value">{updated_text}</div>
                </div>
              </div>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# ---------- Lease filter (UI-only, safe for now) ----------
def is_lease_listing(it: Dict[str, Any]) -> bool:
    title = (it.get("title") or "").lower()
    url = (it.get("url") or "").lower()

    lease_words = [" lease", "for lease", "rent", "rental", "per month", "/mo", "monthly"]
    if any(w in title for w in lease_words):
        return True

    # optional extra catch (commented on purpose):
    # if "lease" in url or "rent" in url:
    #     return True

    return False

# ---------- Load data ----------
data = load_data()
items: List[Dict[str, Any]] = data.get("items", []) or []
criteria = data.get("criteria", {}) or {}
last_updated = data.get("last_updated_utc")

# render header AFTER we have last_updated
render_header(last_updated)

# Hide leases by default (quick fix until scraper tags them)
items = [it for it in items if not is_lease_listing(it)]

# ---------- Defaults (match Properties) ----------
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

# ---------- Metrics ----------
top_matches = [it for it in items if is_top_match(it)]
possible_matches = [it for it in items if is_possible_match(it)]
new_items = [it for it in items if is_new(it)]

# No more “criteria line” up top — keep it clean.
# If you want a tiny “settings” chip later, we can do that without the ugly text block.

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
        <div class="kb-tile-label">New</div>
        <div class="kb-tile-value">{len(new_items)}</div>
        <div class="kb-tile-sub">Since last run</div>
      </div>

      <div class="kb-tile">
        <div class="kb-tile-label">Possible</div>
        <div class="kb-tile-value">{len(possible_matches)}</div>
        <div class="kb-tile-sub">Price missing</div>
      </div>

      <div class="kb-tile">
        <div class="kb-tile-label">Max price</div>
        <div class="kb-tile-value">${default_max_price:,}</div>
        <div class="kb-tile-sub">Top-match cap</div>
      </div>

      <div class="kb-tile">
        <div class="kb-tile-label">Acre range</div>
        <div class="kb-tile-value">{default_min_acres:g}–{default_max_acres:g}</div>
        <div class="kb-tile-sub">Target acres</div>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.write("")

# CTA to properties
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
            # show thumb if present
            if thumb:
                st.image(thumb, use_container_width=True)

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

            st.write(f"**{title}**")
            if line_bits:
                st.caption(" • ".join(line_bits))

            if url:
                st.link_button("Open listing ↗", url, use_container_width=True)

st.divider()
st.caption("Tip: Use Properties to search, filter, and view all listings.")
