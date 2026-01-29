import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import requests
import streamlit as st

# -----------------------------
# Page / Theme-y layout settings
# -----------------------------
st.set_page_config(
    page_title="KB’s Land Tracker",
    page_icon="🗺️",
    layout="wide",
)

st.title("KB’s Land Tracker")
st.caption("What’s meant for you is already in motion.")

DATA_PATH = Path("data/listings.json")


# -----------------------------
# Helpers
# -----------------------------
TAG_RE = re.compile(r"<[^>]+>")

def strip_html(text: str) -> str:
    """Remove HTML tags so titles never show raw code."""
    if not text:
        return ""
    return TAG_RE.sub("", text).strip()

def money_fmt(value: Optional[Any]) -> str:
    if value is None:
        return "—"
    try:
        n = float(value)
        # If it's tiny like 1, 3, 9 but clearly meant to be "$X,XXX" sometimes,
        # don't guess here — just show it as-is and let the strict filter handle.
        return f"${n:,.0f}"
    except Exception:
        return str(value)

def acres_fmt(value: Optional[Any]) -> str:
    if value is None:
        return "—"
    try:
        n = float(value)
        # show 1 decimal if needed
        return f"{n:g}"
    except Exception:
        return str(value)

def safe_host(url: str) -> str:
    try:
        return urlparse(url).netloc.replace("www.", "")
    except Exception:
        return ""

@st.cache_data(show_spinner=False)
def load_data() -> Dict[str, Any]:
    if not DATA_PATH.exists():
        return {"last_updated_utc": None, "criteria": {}, "items": []}
    with DATA_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)

def parse_last_updated(iso_str: Optional[str]) -> str:
    if not iso_str:
        return "—"
    try:
        # Handle "2026-01-29T22:08:19.594685+00:00"
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt.strftime("%b %d, %Y • %I:%M %p UTC")
    except Exception:
        return iso_str

def is_strict_match(item: Dict[str, Any], max_price: int, min_acres: float, max_acres: float) -> bool:
    """Strict = within acres range AND price <= max_price, and both are parseable numbers."""
    try:
        p = float(item.get("price"))
        a = float(item.get("acres"))
    except Exception:
        return False
    return (min_acres <= a <= max_acres) and (p <= max_price)

@st.cache_data(show_spinner=False)
def fetch_thumbnail(url: str) -> Optional[str]:
    """
    Best-effort thumbnail:
    - tries OpenGraph image (og:image)
    - lightweight: only hits when card is rendered
    NOTE: Some sites block this; if so it just returns None.
    """
    try:
        r = requests.get(
            url,
            timeout=10,
            headers={
                "User-Agent": "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml",
            },
        )
        if r.status_code != 200 or not r.text:
            return None

        # super light OG parse without full bs4 dependency in app
        m = re.search(r'<meta\s+property=["\']og:image["\']\s+content=["\']([^"\']+)["\']', r.text, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    except Exception:
        return None

    return None


# -----------------------------
# Load data
# -----------------------------
data = load_data()
items: List[Dict[str, Any]] = data.get("items", []) or []
criteria = data.get("criteria", {}) or {}

min_acres = float(criteria.get("min_acres", 11))
max_acres = float(criteria.get("max_acres", 50))
default_max_price = int(criteria.get("max_price", 600000))

last_updated = parse_last_updated(data.get("last_updated_utc"))

# -----------------------------
# Controls (keep these visible)
# -----------------------------
with st.container():
    c1, c2 = st.columns([2, 1])
    with c1:
        query = st.text_input("Search (title/location/source)", value="")
    with c2:
        show_n = st.slider("Show how many", min_value=5, max_value=200, value=50, step=5)

# For STRICT filter only (kept but not shouted)
max_price_strict = st.number_input(
    "Max price (for STRICT matches)",
    min_value=0,
    max_value=5_000_000,
    value=default_max_price,
    step=10_000,
)

# -----------------------------
# Filtering
# -----------------------------
q = (query or "").strip().lower()

def matches_query(item: Dict[str, Any]) -> bool:
    if not q:
        return True
    hay = " ".join(
        [
            str(item.get("title", "")),
            str(item.get("source", "")),
            str(item.get("location", "")),
            safe_host(str(item.get("url", ""))),
        ]
    ).lower()
    return q in hay

filtered_all = [it for it in items if matches_query(it)]

# STRICT subset (what you originally cared about)
strict = [it for it in filtered_all if is_strict_match(it, max_price_strict, min_acres, max_acres)]

# -----------------------------
# Advanced (hidden) stats panel
# -----------------------------
with st.expander("Advanced (stats & details)", expanded=False):
    st.markdown(f"**Last updated:** {last_updated}")
    st.markdown(f"**Acres range (strict):** {min_acres:g}–{max_acres:g}")
    st.markdown(f"**Strict max price:** ${max_price_strict:,.0f}")

    # These numbers are helpful for you, not for William — so they live here.
    st.metric("All found (includes weird/unparsed prices)", len(filtered_all))
    st.metric("Strict matches", len(strict))

    st.caption("Tip: If prices look weird but listings are real, they’ll still appear under All found.")


# -----------------------------
# Main output (what William sees)
# -----------------------------
st.subheader("Listings")

# Prefer strict list first if it exists, otherwise show all.
# This keeps the “good matches” front and center while still showing everything.
display_list = strict if len(strict) > 0 else filtered_all

if not display_list:
    st.info("No matches with the current search. Try clearing the search box.")
else:
    # Sort: strict matches by price ascending when possible
    def sort_key(it: Dict[str, Any]):
        try:
            return float(it.get("price", 9e18))
        except Exception:
            return 9e18

    display_list = sorted(display_list, key=sort_key)[:show_n]

    for it in display_list:
        title = strip_html(str(it.get("title") or "Land listing"))
        url = str(it.get("url") or "")
        source = str(it.get("source") or safe_host(url) or "Source")
        price = it.get("price")
        acres = it.get("acres")

        # Optional thumbnail (best-effort)
        thumb = fetch_thumbnail(url) if url else None

        with st.container(border=True):
            cols = st.columns([1, 3, 1])
            with cols[0]:
                if thumb:
                    st.image(thumb, use_container_width=True)
                else:
                    st.caption("")

            with cols[1]:
                st.markdown(f"### {title}")
                st.caption(source)
                st.markdown(f"**Price:** {money_fmt(price)} &nbsp;&nbsp; **Acres:** {acres_fmt(acres)}")

            with cols[2]:
                if url:
                    st.link_button("Open ↗", url)
                else:
                    st.caption("No link")