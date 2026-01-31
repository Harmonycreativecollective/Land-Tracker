import json
import base64
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import streamlit as st

# -----------------------------
# Paths / Branding
# -----------------------------
DATA_PATH = Path("data/listings.json")
LOGO_PATH = Path("assets/kblogo.png")

TITLE = "KB’s Land Tracker"
CAPTION = "What’s meant for you is already in motion."

st.set_page_config(
    page_title=TITLE,
    page_icon="assets/kblogo.png",
    layout="wide",
)

# -----------------------------
# Load data
# -----------------------------
def load_data() -> Dict[str, Any]:
    if not DATA_PATH.exists():
        return {"items": [], "criteria": {}, "last_updated_utc": None}
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

data = load_data()
items: List[Dict[str, Any]] = data.get("items", []) or []
criteria: Dict[str, Any] = data.get("criteria", {}) or {}
last_updated_raw = data.get("last_updated_utc")

# -----------------------------
# Helpers
# -----------------------------
def logo_base64(path: Path) -> str:
    if not path.exists():
        return ""
    try:
        return base64.b64encode(path.read_bytes()).decode("utf-8")
    except Exception:
        return ""

def pretty_utc(iso_str: str) -> str:
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt.strftime("%b %d, %Y • %I:%M %p UTC")
    except Exception:
        return str(iso_str)

def searchable_text(it: Dict[str, Any]) -> str:
    return " ".join([
        str(it.get("title", "")),
        str(it.get("source", "")),
        str(it.get("url", "")),
    ]).lower()

def safe_float(x) -> Optional[float]:
    try:
        if x is None:
            return None
        return float(x)
    except Exception:
        return None

def safe_int(x) -> Optional[int]:
    try:
        if x is None:
            return None
        return int(float(x))
    except Exception:
        return None

# -----------------------------
# Defaults (from criteria)
# -----------------------------
DEFAULT_MAX_PRICE = int(criteria.get("max_price") or 600000)
DEFAULT_MIN_ACRES = float(criteria.get("min_acres") or 11.0)
DEFAULT_MAX_ACRES = float(criteria.get("max_acres") or 50.0)

# -----------------------------
# Header (Big Logo, Left)
# -----------------------------
logo_b64 = logo_base64(LOGO_PATH)

# ✅ The key: hard-set logo height so it won't randomly shrink
LOGO_HEIGHT_PX = 92  # <-- make this 100-120 if you want it even bigger

st.markdown(
    f"""
    <div style="
        display:flex;
        align-items:center;
        gap:18px;
        margin-top:12px;
        margin-bottom:8px;
        flex-wrap:nowrap;
    ">
        <div style="flex:0 0 auto;">
            {"<img src='data:image/png;base64," + logo_b64 + "' style='height:" + str(LOGO_HEIGHT_PX) + "px; width:auto; border-radius:16px;'/>" if logo_b64 else ""}
        </div>

        <div style="flex:1 1 auto;">
            <div style="
                font-size:3.1rem;
                font-weight:900;
                line-height:1.05;
                color:#0f172a;
                margin:0;
            ">
                {TITLE}
            </div>

            <div style="
                font-size:1.28rem;
                color: rgba(49, 51, 63, 0.78);
                margin-top:10px;
            ">
                {CAPTION}
            </div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# Last updated: NOT in filters/details
if last_updated_raw:
    st.markdown(
        f"""
        <div style="font-size:0.9rem; color: rgba(49, 51, 63, 0.55); margin-top:2px; margin-bottom:14px;">
            Last updated: {pretty_utc(last_updated_raw)}
        </div>
        """,
        unsafe_allow_html=True,
    )

# -----------------------------
# Search (outside filters)
# -----------------------------
search_query = st.text_input(
    "Search (title / location / source)",
    value="",
    placeholder="Try: king george, port royal, landsearch, 20 acres…",
)

# -----------------------------
# Filters dropdown
# -----------------------------
with st.expander("Filters", expanded=False):
    max_price = st.number_input(
        "Max price (Top match)",
        min_value=0,
        value=DEFAULT_MAX_PRICE,
        step=10_000,
    )

    min_acres = st.number_input(
        "Min acres",
        min_value=0.0,
        value=DEFAULT_MIN_ACRES,
        step=1.0,
        format="%.2f",
    )

    max_acres = st.number_input(
        "Max acres",
        min_value=0.0,
        value=DEFAULT_MAX_ACRES,
        step=1.0,
        format="%.2f",
    )

    colA, colB = st.columns(2)
    with colA:
        show_top_matches_only = st.toggle("Top matches only", value=True)
    with colB:
        new_only = st.toggle("New only", value=False)

    newest_first = st.toggle("Newest first", value=True)
    show_n = st.slider("Show how many", min_value=5, max_value=200, value=50, step=5)

# -----------------------------
# Logic
# -----------------------------
def is_top_match(it: Dict[str, Any]) -> bool:
    price = safe_int(it.get("price"))
    acres = safe_float(it.get("acres"))
    if price is None or acres is None:
        return False
    return (min_acres <= acres <= max_acres) and (price <= max_price)

def is_new(it: Dict[str, Any]) -> bool:
    # "New" will become real once scraper adds found_utc/first_seen_utc
    # For now: safe default, keep badge on
    return True

def parse_dt(it: Dict[str, Any]) -> str:
    return str(it.get("found_utc") or "")

top_matches_all = [it for it in items if is_top_match(it)]

# -----------------------------
# Details dropdown
# -----------------------------
with st.expander("Details", expanded=False):
    c1, c2, c3 = st.columns(3)
    c1.metric("All found", f"{len(items)}")
    c2.metric("Top matches", f"{len(top_matches_all)}")
    c3.metric("Max price", f"${int(max_price):,}")

    st.caption(f"Acre range: {min_acres:g}–{max_acres:g}")

st.divider()

# -----------------------------
# Apply search + filters
# -----------------------------
filtered = items[:]

# Search
if search_query.strip():
    q = search_query.strip().lower()
    filtered = [it for it in filtered if q in searchable_text(it)]

# Top matches only
if show_top_matches_only:
    filtered = [it for it in filtered if is_top_match(it)]

# New only
if new_only:
    filtered = [it for it in filtered if is_new(it)]

# Sort newest first
if newest_first:
    filtered = sorted(filtered, key=parse_dt, reverse=True)

# Limit
filtered = filtered[:show_n]

# -----------------------------
# Listing card UI
# -----------------------------
def badge_html(text: str, bg: str):
    return f"""
    <span style="
        display:inline-block;
        padding:4px 10px;
        border-radius:999px;
        background:{bg};
        color:white;
        font-size:12px;
        font-weight:800;
        margin-right:6px;
    ">{text}</span>
    """

def listing_card(it: Dict[str, Any]):
    title = (it.get("title") or "").strip()
    source = it.get("source") or "Unknown"
    url = it.get("url") or ""
    price = safe_int(it.get("price"))
    acres = safe_float(it.get("acres"))
    thumb = it.get("thumbnail")

    if not title or title.lower() == "land listing":
        title = f"{source} listing"

    top_match = is_top_match(it)
    new_flag = is_new(it)

    with st.container(border=True):
        if thumb:
            st.image(thumb, use_container_width=True)
        else:
            st.markdown(
                """
                <div style="width:100%; height:220px; background:#f1f3f5; border-radius:16px;
                            display:flex; align-items:center; justify-content:center; color:#666;
                            font-weight:800; font-size:1.05rem;">
                    No preview available
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.subheader(title)

        badges = ""
        if top_match:
            badges += badge_html("⭐ Top match", "#2563eb")
        if new_flag:
            badges += badge_html("🆕 NEW", "#16a34a")
        if not top_match:
            badges += badge_html("FOUND", "#64748b")

        st.markdown(badges, unsafe_allow_html=True)
        st.caption(source)

        st.write(f"**Price:** {'—' if price is None else f'${price:,}'}")
        st.write(f"**Acres:** {'—' if acres is None else f'{acres:g}'}")

        if url:
            st.link_button("Open listing ↗", url, use_container_width=True)

# -----------------------------
# Render
# -----------------------------
if not filtered:
    st.info("No listings matched your current search/filters.")
else:
    cols = st.columns(2)
    for idx, it in enumerate(filtered):
        with cols[idx % 2]:
            listing_card(it)