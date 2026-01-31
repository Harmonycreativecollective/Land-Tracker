import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import streamlit as st

DATA_PATH = Path("data/listings.json")

TITLE = "KB’s Land Tracker"
CAPTION = "What’s meant for you is already in motion."


# ---------------- Page config ----------------
st.set_page_config(
    page_title=TITLE,
    page_icon="🗺️",
    layout="wide",
)


# ---------------- Load data ----------------
def load_data() -> Dict[str, Any]:
    if not DATA_PATH.exists():
        return {"items": [], "criteria": {}, "last_updated_utc": None}
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


data = load_data()
items: List[Dict[str, Any]] = data.get("items", []) or []
last_updated_raw = data.get("last_updated_utc")


# ---------------- Helpers ----------------
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


def pretty_utc(ts: str) -> str:
    # Accepts ISO timestamps; shows "Jan 31, 2026 • 07:26 PM UTC"
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc).strftime("%b %d, %Y • %I:%M %p UTC")
    except Exception:
        return str(ts)


def is_top_match(it: Dict[str, Any], min_acres: float, max_acres: float, max_price: int) -> bool:
    price = safe_int(it.get("price"))
    acres = safe_float(it.get("acres"))
    if price is None or acres is None:
        return False
    return (min_acres <= acres <= max_acres) and (price <= max_price)


def searchable_text(it: Dict[str, Any]) -> str:
    return " ".join(
        [
            str(it.get("title", "")),
            str(it.get("source", "")),
            str(it.get("url", "")),
        ]
    ).lower()


def get_first_seen_dt(it: Dict[str, Any]) -> Optional[datetime]:
    # Only works if your scraper adds first_seen_utc
    raw = it.get("first_seen_utc")
    if not raw:
        return None
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except Exception:
        return None


def is_new(it: Dict[str, Any], window_hours: int = 48) -> Optional[bool]:
    """
    Returns:
      True/False if first_seen_utc exists,
      None if we cannot determine.
    """
    dt = get_first_seen_dt(it)
    if not dt:
        return None
    now = datetime.now(timezone.utc)
    return dt >= (now - timedelta(hours=window_hours))


def sort_key_newest(it: Dict[str, Any]) -> str:
    # Sort by first_seen_utc if available; otherwise fall back to empty
    dt = get_first_seen_dt(it)
    if dt:
        return dt.isoformat()
    return ""


# ---------------- Header ----------------
st.title(TITLE)

# Bigger caption
st.markdown(
    f"""
    <div style="font-size:1.15rem; color: rgba(49, 51, 63, 0.75); margin-top:-6px;">
        {CAPTION}
    </div>
    """,
    unsafe_allow_html=True,
)

# Last updated — small, subtle, NOT inside details/filters
if last_updated_raw:
    st.markdown(
        f"""
        <div style="font-size:0.85rem; color: rgba(49, 51, 63, 0.55); margin-top:6px; margin-bottom:10px;">
            Last updated: {pretty_utc(last_updated_raw)}
        </div>
        """,
        unsafe_allow_html=True,
    )

# Search OUTSIDE filters/details
search_query = st.text_input(
    "Search (title / location / source)",
    value="",
    placeholder="Try: king george, port royal, landsearch, 20 acres…",
)


# ---------------- Advanced / Filters / Details dropdowns ----------------
# Default criteria
default_max_price = 600_000
default_min_acres = 11.0
default_max_acres = 50.0

# Put filters + details into two dropdown sections (expander)
with st.expander("Filters", expanded=False):
    max_price = st.number_input(
        "Max price (Top match)",
        min_value=0,
        value=default_max_price,
        step=10_000,
    )

    min_acres = st.number_input(
        "Min acres",
        min_value=0.0,
        value=default_min_acres,
        step=1.0,
        format="%.2f",
    )

    max_acres = st.number_input(
        "Max acres",
        min_value=0.0,
        value=default_max_acres,
        step=1.0,
        format="%.2f",
    )

    # Toggles
    colA, colB = st.columns(2)
    with colA:
        top_matches_only = st.toggle("Top matches only", value=True)
    with colB:
        new_only = st.toggle("New only", value=False)

    newest_first = st.toggle("Newest first", value=True)
    show_n = st.slider("Show how many", min_value=5, max_value=200, value=50, step=5)


# Details dropdown (counts / overview)
# Compute these based on current filter settings for top-match definition
top_match_count_all = sum(1 for it in items if is_top_match(it, min_acres, max_acres, max_price))

# New count (only if first_seen_utc exists)
new_flags = [is_new(it) for it in items]
new_known = [x for x in new_flags if x is not None]
new_count = sum(1 for x in new_known if x is True) if new_known else None

with st.expander("Details", expanded=False):
    st.metric("All found", f"{len(items)}")
    st.metric("Top matches", f"{top_match_count_all}")

    # If we can compute NEW, show it; otherwise show a note
    if new_count is not None:
        st.metric("New", f"{new_count}")
    else:
        st.caption("🆕 New: available once the scraper writes `first_seen_utc` (optional upgrade).")


# ---------------- Apply filters ----------------
filtered = items[:]

# Search
if search_query.strip():
    q = search_query.strip().lower()
    filtered = [it for it in filtered if q in searchable_text(it)]

# Top matches only
if top_matches_only:
    filtered = [it for it in filtered if is_top_match(it, min_acres, max_acres, max_price)]

# New only (only works if we can determine)
if new_only:
    filtered = [it for it in filtered if is_new(it) is True]

# Sort
if newest_first:
    filtered = sorted(filtered, key=sort_key_newest, reverse=True)

# Limit
filtered = filtered[:show_n]


# ---------------- Listing cards ----------------
def listing_card(it: Dict[str, Any]):
    title = (it.get("title") or "").strip()
    if not title or title.lower() == "land listing":
        # smarter fallback
        src = (it.get("source") or "Listing").strip()
        title = f"{src} listing"

    url = it.get("url") or ""
    source = it.get("source") or ""
    price = safe_int(it.get("price"))
    acres = safe_float(it.get("acres"))
    thumb = it.get("thumbnail")

    top_match = is_top_match(it, min_acres, max_acres, max_price)
    new_flag = is_new(it)  # True / False / None

    # Badges line
    badges = []
    if top_match:
        badges.append("⭐ Top match")
    if new_flag is True:
        badges.append("🆕 NEW")
    if not badges:
        badges.append("FOUND")

    with st.container(border=True):
        if thumb:
            st.image(thumb, use_container_width=True)
        else:
            st.markdown(
                """
                <div style="width:100%; height:220px; background:#f2f2f2; border-radius:16px;
                            display:flex; align-items:center; justify-content:center; color:#777;
                            font-weight:600;">
                    No preview available
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.subheader(title)
        st.caption(f"{' • '.join(badges)} • {source}")

        if price is None:
            st.write("**Price:** —")
        else:
            st.write(f"**Price:** ${price:,}")

        if acres is None:
            st.write("**Acres:** —")
        else:
            st.write(f"**Acres:** {acres:g}")

        if url:
            st.link_button("Open listing ↗", url, use_container_width=True)


if not filtered:
    st.info("No listings matched your current search/filters.")
else:
    cols = st.columns(2)
    for idx, it in enumerate(filtered):
        with cols[idx % 2]:
            listing_card(it)