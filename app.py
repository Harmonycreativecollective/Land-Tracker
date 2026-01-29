import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import streamlit as st

# -----------------------------
# Page setup
# -----------------------------
st.set_page_config(
    page_title="KB’s Land Tracker",
    page_icon="🗺️",
    layout="wide",
)

# -----------------------------
# Helpers
# -----------------------------
DATA_PATH = Path("data/listings.json")

def strip_html(s: str) -> str:
    """Remove any HTML tags so we never render code-looking titles/snippets."""
    if not s:
        return ""
    return re.sub(r"<[^>]+>", "", s).strip()

def money(v):
    try:
        if v is None:
            return "—"
        return f"${int(v):,}"
    except Exception:
        return "—"

def acres_fmt(v):
    try:
        if v is None:
            return "—"
        v = float(v)
        # prettier: 19.0 -> 19, 19.3 -> 19.3
        return f"{v:g}"
    except Exception:
        return "—"

def safe_dt_label(iso_str: str) -> str:
    if not iso_str:
        return "—"
    try:
        # Handles "2026-01-29T22:08:19.594685+00:00"
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt.strftime("%b %d, %Y • %I:%M %p UTC")
    except Exception:
        return iso_str

def get_image(item: dict) -> str | None:
    """Support multiple possible keys from different scrapers."""
    for k in ("image", "image_url", "thumbnail", "thumbnail_url", "img", "photo"):
        v = item.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    # Sometimes an images list exists
    imgs = item.get("images")
    if isinstance(imgs, list) and imgs:
        v = imgs[0]
        if isinstance(v, str) and v.strip():
            return v.strip()
        if isinstance(v, dict):
            for k in ("url", "src", "image", "thumbnail"):
                vv = v.get(k)
                if isinstance(vv, str) and vv.strip():
                    return vv.strip()
    return None

def get_location(item: dict) -> str:
    # Optional: you may have these fields
    for k in ("location", "city", "county", "state"):
        v = item.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""

def domain_from_url(u: str) -> str:
    try:
        return urlparse(u).netloc.replace("www.", "")
    except Exception:
        return ""

def load_data() -> dict:
    if not DATA_PATH.exists():
        return {"last_updated_utc": "", "criteria": {}, "items": []}
    try:
        return json.loads(DATA_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"last_updated_utc": "", "criteria": {}, "items": []}

def is_strict_match(item: dict, criteria: dict, max_price_override: int | None = None) -> bool:
    """
    Strict match = has both price & acres and fits within criteria bounds.
    If a listing has wonky/unknown price or acres, it will count only as "All found" not strict.
    """
    try:
        price = item.get("price")
        acres = item.get("acres")
        if price is None or acres is None:
            return False

        min_acres = float(criteria.get("min_acres", 0) or 0)
        max_acres = float(criteria.get("max_acres", 10**9) or 10**9)

        max_price = int(max_price_override if max_price_override is not None else (criteria.get("max_price") or 10**12))

        return (min_acres <= float(acres) <= max_acres) and (int(price) <= max_price)
    except Exception:
        return False

# -----------------------------
# Load listings
# -----------------------------
data = load_data()
items = data.get("items", []) or []
criteria = data.get("criteria", {}) or {}

last_updated = safe_dt_label(data.get("last_updated_utc", ""))

default_max_price = int(criteria.get("max_price", 600000) or 600000)

# -----------------------------
# Header
# -----------------------------
st.title("KB’s Land Tracker")
st.caption("What’s meant for you is already in motion.")

# -----------------------------
# Filters (hidden by default)
# -----------------------------
# These are collapsed so William won't see them unless someone expands
with st.expander("Filters", expanded=False):
    max_price = st.number_input(
        "Max price (for STRICT matches)",
        min_value=0,
        value=default_max_price,
        step=5000,
    )
    search_q = st.text_input("Search (title/location/source)")
    show_n = st.slider("Show how many", 5, 200, 60)

# -----------------------------
# Apply search filter (for display only)
# -----------------------------
def matches_search(it: dict, q: str) -> bool:
    if not q:
        return True
    q = q.lower().strip()
    hay = " ".join(
        [
            strip_html(str(it.get("title", ""))),
            str(get_location(it)),
            str(it.get("source", "")),
            str(domain_from_url(str(it.get("url", "")))),
        ]
    ).lower()
    return q in hay

filtered = [it for it in items if matches_search(it, search_q)]

# Strict matches count uses max_price from UI
strict_count = sum(1 for it in items if is_strict_match(it, criteria, max_price_override=max_price))

# -----------------------------
# Top KPIs
# -----------------------------
k1, k2, k3, k4 = st.columns(4)
k1.metric("All found", len(items))
k2.metric("Strict matches", strict_count)
k3.metric("Max price", money(max_price))
k4.metric("Acres range", f"{criteria.get('min_acres', '—')}–{criteria.get('max_acres', '—')}")

st.caption(f"Last updated: {last_updated}")

st.divider()

# -----------------------------
# Cards grid
# -----------------------------
if not filtered:
    st.info("No matches with the current search. Try clearing the search box.")
else:
    # Sort: strict matches first, then by price (unknown last)
    def sort_key(it):
        strict = is_strict_match(it, criteria, max_price_override=max_price)
        price = it.get("price")
        price_sort = int(price) if isinstance(price, (int, float)) else 10**15
        return (0 if strict else 1, price_sort)

    filtered_sorted = sorted(filtered, key=sort_key)[:show_n]

    # Responsive-ish: 2 cols on mobile, 3 on desktop-ish
    cols = st.columns(3)
    for idx, it in enumerate(filtered_sorted):
        col = cols[idx % 3]
        with col:
            title = strip_html(str(it.get("title") or "Land listing"))
            url = str(it.get("url") or "").strip()
            src = str(it.get("source") or "").strip()
            loc = strip_html(get_location(it))
            img = get_image(it)

            # Card container
            with st.container(border=True):
                if img:
                    st.image(img, use_container_width=True)

                st.subheader(title)

                meta_left, meta_right = st.columns(2)
                with meta_left:
                    st.write(f"**Price:** {money(v=it.get('price'))}")
                with meta_right:
                    st.write(f"**Acres:** {acres_fmt(v=it.get('acres'))}")

                if loc:
                    st.write(f"📍 {loc}")

                if src:
                    st.caption(src)

                if url:
                    st.link_button("Open listing ↗", url)

# -----------------------------
# Notes:
# - No tables are shown.
# - Filters/search are hidden in the expander.
# - If images are not present in listings.json, cards still work.
# -----------------------------