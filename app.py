import json
from datetime import datetime
from typing import Any, Dict, List

import streamlit as st

# ---------------------------------------------------------
# Page config
# ---------------------------------------------------------
st.set_page_config(
    page_title="KB’s Land Tracker",
    page_icon="🗺️",
    layout="wide",
)

# ---------------------------------------------------------
# Theme / Style (Grey aesthetic, clean dashboard look)
# ---------------------------------------------------------
st.markdown(
    """
    <style>
      /* overall app background */
      .stApp {
        background: #f6f7f9;
      }

      /* remove the default top padding */
      .block-container {
        padding-top: 1.25rem;
        padding-bottom: 3rem;
      }

      /* title styling */
      h1 {
        font-weight: 800 !important;
        letter-spacing: -0.02em;
      }

      /* subtle caption */
      .caption {
        color: #6b7280;
        font-size: 1rem;
        margin-top: -0.6rem;
        margin-bottom: 1rem;
      }

      /* card styling */
      .kb-card {
        border: 1px solid #e5e7eb;
        border-radius: 18px;
        padding: 16px;
        background: white;
        box-shadow: 0px 2px 12px rgba(0,0,0,0.05);
        margin-bottom: 12px;
      }

      .kb-card h3 {
        margin: 0 0 6px 0;
        font-size: 20px;
        line-height: 1.2;
      }

      .kb-pill {
        display: inline-block;
        font-size: 12px;
        font-weight: 600;
        padding: 4px 10px;
        border-radius: 999px;
        border: 1px solid #e5e7eb;
        background: #f3f4f6;
        color: #374151;
        margin-right: 6px;
        margin-top: 6px;
      }

      .kb-muted {
        color: #6b7280;
        font-size: 0.95rem;
      }

      .kb-price {
        font-weight: 800;
        font-size: 22px;
      }

      .kb-btn a {
        text-decoration: none !important;
      }

      /* make Streamlit widgets look cleaner */
      [data-testid="stSlider"] {
        padding-top: 8px;
      }
    </style>
    """,
    unsafe_allow_html=True
)

# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------
def load_data(path: str = "data/listings.json") -> Dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"items": [], "criteria": {}, "last_updated_utc": None}

def safe_int(x):
    try:
        return int(x)
    except Exception:
        return None

def safe_float(x):
    try:
        return float(x)
    except Exception:
        return None

def fmt_money(n: Any) -> str:
    n = safe_int(n)
    if n is None:
        return "Price: Unknown"
    return f"${n:,.0f}"

def fmt_acres(a: Any) -> str:
    a = safe_float(a)
    if a is None:
        return "Acres: Unknown"
    return f"{a:g} acres"

def fmt_dt(iso_utc: str) -> str:
    if not iso_utc:
        return "Unknown"
    try:
        dt = datetime.fromisoformat(iso_utc.replace("Z","+00:00"))
        return dt.strftime("%b %d, %Y • %I:%M %p UTC")
    except Exception:
        return iso_utc

def is_strict_match(item: Dict[str, Any], max_price: int, min_acres: float, max_acres: float) -> bool:
    price = safe_int(item.get("price"))
    acres = safe_float(item.get("acres"))
    if price is None or acres is None:
        return False
    return (min_acres <= acres <= max_acres) and (price <= max_price)

# ---------------------------------------------------------
# Load
# ---------------------------------------------------------
data = load_data()
items: List[Dict[str, Any]] = data.get("items", [])
criteria = data.get("criteria", {})
last_updated = data.get("last_updated_utc")

# fallback criteria
min_acres = float(criteria.get("min_acres", 11.0))
max_acres = float(criteria.get("max_acres", 50.0))
max_price_default = int(criteria.get("max_price", 600000))

# ---------------------------------------------------------
# Header
# ---------------------------------------------------------
st.title("KB’s Land Tracker")
st.markdown('<div class="caption">What’s meant for you is already in motion.</div>', unsafe_allow_html=True)

# ---------------------------------------------------------
# Sidebar controls
# ---------------------------------------------------------
with st.sidebar:
    st.subheader("Filters")

    max_price = st.number_input(
        "Max price (for STRICT matches)",
        min_value=0,
        value=max_price_default,
        step=10_000
    )

    search = st.text_input("Search (title/location/source)")

    show_n = st.slider("Show how many", 5, 200, 60, step=5)

    st.divider()
    st.caption("Tip: STRICT matches = within acres + max price.")

# ---------------------------------------------------------
# Stats row
# ---------------------------------------------------------
strict = [i for i in items if is_strict_match(i, max_price, min_acres, max_acres)]
all_found_count = len(items)
strict_count = len(strict)

c1, c2, c3, c4 = st.columns(4)
c1.metric("All found", all_found_count)
c2.metric("Strict matches", strict_count)
c3.metric("Max price", f"${max_price:,.0f}")
c4.metric("Acres range", f"{min_acres:g}–{max_acres:g}")

st.caption(f"Last updated: {fmt_dt(last_updated)}")

st.divider()

# ---------------------------------------------------------
# Listing display logic (Option A = show Strict first, then All Found)
# ---------------------------------------------------------
def matches_search(i: Dict[str, Any], q: str) -> bool:
    if not q:
        return True
    q = q.lower().strip()
    blob = " ".join([
        str(i.get("title","")),
        str(i.get("source","")),
        str(i.get("url",""))
    ]).lower()
    return q in blob

strict_display = [i for i in strict if matches_search(i, search)]
all_display = [i for i in items if matches_search(i, search)]

# sort: strict by lowest price first, unknown last
def sort_key(i: Dict[str, Any]):
    p = safe_int(i.get("price"))
    if p is None:
        return (1, 10**18)
    return (0, p)

strict_display.sort(key=sort_key)
all_display.sort(key=sort_key)

# Limit
strict_display = strict_display[:show_n]
all_display = all_display[:show_n]

# ---------------------------------------------------------
# Card renderer
# ---------------------------------------------------------
def render_card(item: Dict[str, Any], tag: str):
    title = item.get("title") or "Land listing"
    source = item.get("source") or ""
    url = item.get("url") or ""
    thumb = item.get("thumbnail")  # optional

    price = item.get("price")
    acres = item.get("acres")

    colA, colB = st.columns([1, 3], vertical_alignment="top")

    # Thumbnail
    with colA:
        if thumb:
            st.image(thumb, use_container_width=True)
        else:
            st.markdown(
                """
                <div class="kb-card" style="height:170px; display:flex; align-items:center; justify-content:center; background:#f3f4f6;">
                  <div class="kb-muted">No preview</div>
                </div>
                """,
                unsafe_allow_html=True
            )

    # Main card
    with colB:
        st.markdown(
            f"""
            <div class="kb-card">
              <div class="kb-pill">{tag}</div>
              <div class="kb-pill">{source}</div>
              <h3>{title}</h3>

              <div style="margin-top:10px;">
                <span class="kb-price">{fmt_money(price)}</span>
                <span class="kb-muted" style="margin-left:14px;">• {fmt_acres(acres)}</span>
              </div>

              <div style="margin-top:12px;" class="kb-btn">
                <a href="{url}" target="_blank">Open listing ↗</a>
              </div>
            </div>
            """,
            unsafe_allow_html=True
        )

# ---------------------------------------------------------
# Layout sections
# ---------------------------------------------------------
st.subheader("STRICT matches")
if not strict_display:
    st.info("No strict matches with the current max price filter.")
else:
    for i in strict_display:
        render_card(i, "MATCHES")

st.divider()

st.subheader("All found (including weird pricing)")
if not all_display:
    st.info("No listings found.")
else:
    for i in all_display:
        render_card(i, "ALL FOUND")