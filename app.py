import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import streamlit as st

# =========================
# PAGE CONFIG
# =========================
st.set_page_config(
    page_title="KB’s Land Tracker",
    page_icon="🗺️",
    layout="wide",
)

DATA_PATH = Path("data/listings.json")

# =========================
# HELPERS
# =========================
TAG_RE = re.compile(r"<[^>]+>")

def strip_html(text: str) -> str:
    if not text:
        return ""
    return TAG_RE.sub("", str(text)).strip()

def safe_int(x) -> Optional[int]:
    try:
        if x is None:
            return None
        return int(float(x))
    except Exception:
        return None

def safe_float(x) -> Optional[float]:
    try:
        if x is None:
            return None
        return float(x)
    except Exception:
        return None

def money(v: Any) -> str:
    n = safe_int(v)
    return f"${n:,.0f}" if n is not None else "—"

def acres_fmt(v: Any) -> str:
    a = safe_float(v)
    return f"{a:g}" if a is not None else "—"

def parse_dt(iso_str: str) -> str:
    if not iso_str:
        return "—"
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt.strftime("%b %d, %Y • %I:%M %p UTC")
    except Exception:
        return iso_str

def domain_from_url(u: str) -> str:
    try:
        return urlparse(u).netloc.replace("www.", "")
    except Exception:
        return ""

def get_image(item: dict) -> Optional[str]:
    # support multiple keys (whatever your scraper saved)
    for k in ("thumbnail", "image_url", "image", "thumbnail_url", "img", "photo"):
        v = item.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    imgs = item.get("images")
    if isinstance(imgs, list) and imgs:
        v = imgs[0]
        if isinstance(v, str) and v.strip():
            return v.strip()
        if isinstance(v, dict):
            for kk in ("url", "src", "image", "thumbnail"):
                vv = v.get(kk)
                if isinstance(vv, str) and vv.strip():
                    return vv.strip()
    return None

def is_strict_match(it: Dict[str, Any], min_acres: float, max_acres: float, max_price: int) -> bool:
    p = safe_int(it.get("price"))
    a = safe_float(it.get("acres"))
    if p is None or a is None:
        return False
    return (min_acres <= a <= max_acres) and (p <= max_price)

def load_data() -> Dict[str, Any]:
    if not DATA_PATH.exists():
        return {"last_updated_utc": "", "criteria": {}, "items": []}
    try:
        return json.loads(DATA_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"last_updated_utc": "", "criteria": {}, "items": []}

def no_preview_block():
    st.markdown(
        """
        <div style="
            height:160px;
            border-radius:14px;
            background:linear-gradient(135deg,#f3f4f6,#e5e7eb);
            display:flex;
            align-items:center;
            justify-content:center;
            color:#6b7280;
            font-weight:700;">
          No preview available
        </div>
        """,
        unsafe_allow_html=True
    )

# =========================
# LOAD
# =========================
data = load_data()
items: List[Dict[str, Any]] = data.get("items", []) or []
criteria: Dict[str, Any] = data.get("criteria", {}) or {}

min_acres = float(criteria.get("min_acres", 11.0) or 11.0)
max_acres = float(criteria.get("max_acres", 50.0) or 50.0)
default_max_price = int(criteria.get("max_price", 600000) or 600000)

last_updated = parse_dt(data.get("last_updated_utc", ""))

# =========================
# HEADER
# =========================
st.title("KB’s Land Tracker")
st.caption("What’s meant for you is already in motion.")

# =========================
# FILTERS (HIDDEN FROM HIM BY DEFAULT)
# =========================
with st.expander("Filters", expanded=False):
    max_price = st.number_input(
        "Max price (for STRICT matches)",
        min_value=0,
        value=default_max_price,
        step=10_000,
        format="%d",
    )
    search_q = st.text_input("Search (title/location/source)")
    show_n = st.slider("Show how many", 5, 200, 60, step=5)

# If user never opens Filters, we still need defaults:
# Streamlit will still set them, but this ensures variables exist even if UI changes later.
if "max_price" not in locals():
    max_price = default_max_price
if "search_q" not in locals():
    search_q = ""
if "show_n" not in locals():
    show_n = 60

# =========================
# ADVANCED (THIS IS WHERE THE 4 KPIs GO — HIDDEN)
# =========================
strict_total = sum(1 for it in items if is_strict_match(it, min_acres, max_acres, max_price))

with st.expander("Advanced", expanded=False):
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("All found", len(items))
    c2.metric("Strict matches", strict_total)
    c3.metric("Max price", money(max_price))
    c4.metric("Acres range", f"{min_acres:g}–{max_acres:g}")
    st.caption(f"Last updated: {last_updated}")

st.divider()

# =========================
# SEARCH FILTER
# =========================
q = (search_q or "").strip().lower()

def matches_search(it: Dict[str, Any]) -> bool:
    if not q:
        return True
    hay = " ".join([
        strip_html(it.get("title", "")),
        strip_html(it.get("location", "")),
        str(it.get("source", "")),
        domain_from_url(str(it.get("url", ""))),
    ]).lower()
    return q in hay

filtered = [it for it in items if it.get("url") and matches_search(it)]

# Sort: strict matches first, then lowest price, then higher acres
def sort_key(it: Dict[str, Any]):
    strict = is_strict_match(it, min_acres, max_acres, max_price)
    p = safe_int(it.get("price"))
    a = safe_float(it.get("acres"))
    price_sort = p if p is not None else 10**15
    acres_sort = a if a is not None else 0.0
    return (0 if strict else 1, price_sort, -acres_sort)

filtered = sorted(filtered, key=sort_key)[:show_n]

# =========================
# RENDER CARDS
# =========================
if not filtered:
    st.info("No results. Try clearing the search or widening your max price.")
else:
    # 3 columns desktop, collapses naturally on mobile
    cols = st.columns(3)

    for idx, it in enumerate(filtered):
        col = cols[idx % 3]
        with col:
            title = strip_html(it.get("title") or "Land listing")
            src = strip_html(it.get("source") or domain_from_url(str(it.get("url", ""))) or "Source")
            url = str(it.get("url") or "").strip()

            p = safe_int(it.get("price"))
            a = safe_float(it.get("acres"))

            strict = is_strict_match(it, min_acres, max_acres, max_price)

            with st.container(border=True):
                img = get_image(it)
                if img:
                    st.image(img, use_container_width=True)
                else:
                    no_preview_block()

                st.subheader(title)

                # Small badge-ish line
                badge = "MATCH" if strict else "FOUND"
                st.caption(f"{badge} • {src}")

                m1, m2 = st.columns(2)
                with m1:
                    st.write(f"**Price:** {money(p)}")
                with m2:
                    st.write(f"**Acres:** {acres_fmt(a)}")

                if url:
                    st.link_button("Open listing ↗", url, use_container_width=True)