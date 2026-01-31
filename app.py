import json
import base64
from datetime import datetime
from pathlib import Path

import streamlit as st


# -----------------------------
# Config
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
# Helpers
# -----------------------------
def load_data():
    if not DATA_PATH.exists():
        return {"items": [], "criteria": {}, "last_updated_utc": None}
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def pretty_utc(iso_str: str) -> str:
    """Format last_updated_utc nicely."""
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt.strftime("%b %d, %Y • %I:%M %p UTC")
    except Exception:
        return iso_str


def logo_base64(path: Path) -> str:
    if not path.exists():
        return ""
    return base64.b64encode(path.read_bytes()).decode("utf-8")


def searchable_text(it):
    return " ".join([
        str(it.get("title", "")),
        str(it.get("source", "")),
        str(it.get("url", "")),
    ]).lower()


def parse_dt(it):
    # Works if/when scraper adds found_utc later
    return it.get("found_utc") or ""


# -----------------------------
# Load
# -----------------------------
data = load_data()
items = data.get("items", [])
criteria = data.get("criteria", {}) or {}
last_updated_raw = data.get("last_updated_utc")


# -----------------------------
# Defaults (criteria)
# -----------------------------
DEFAULT_MAX_PRICE = int(criteria.get("max_price") or 600000)
DEFAULT_MIN_ACRES = float(criteria.get("min_acres") or 11.0)
DEFAULT_MAX_ACRES = float(criteria.get("max_acres") or 50.0)


# -----------------------------
# Header (Branded)
# -----------------------------
logo_b64 = logo_base64(LOGO_PATH)

st.markdown(
    f"""
    <div style="display:flex; align-items:center; gap:16px; margin-top:10px; margin-bottom:4px;">
        <div style="flex:0 0 auto;">
            {"<img src='data:image/png;base64," + logo_b64 + "' style='height:72px; width:auto; border-radius:14px;'/>" if logo_b64 else ""}
        </div>
        <div style="flex:1 1 auto;">
            <div style="font-size:3rem; font-weight:900; line-height:1.05; color:#0f172a;">
                {TITLE}
            </div>
            <div style="font-size:1.25rem; color: rgba(49, 51, 63, 0.78); margin-top:10px;">
                {CAPTION}
            </div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

if last_updated_raw:
    st.markdown(
        f"""
        <div style="font-size:0.88rem; color: rgba(49, 51, 63, 0.55); margin-top:10px; margin-bottom:14px;">
            Last updated: {pretty_utc(last_updated_raw)}
        </div>
        """,
        unsafe_allow_html=True,
    )


# -----------------------------
# Search (OUTSIDE filters)
# -----------------------------
search_query = st.text_input(
    "Search (title / location / source)",
    value="",
    placeholder="Try: king george, port royal, landsearch, 20 acres…",
)


# -----------------------------
# Filters + Details (dropdowns)
# -----------------------------
# ✅ Defaults
show_top_matches_only_default = True
new_only_default = False
newest_first_default = True


with st.expander("Filters", expanded=False):
    max_price = st.number_input(
        "Max price (Top match)",
        min_value=0,
        value=DEFAULT_MAX_PRICE,
        step=10000,
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

    show_top_matches_only = st.toggle("Top matches only", value=show_top_matches_only_default)
    new_only = st.toggle("New only", value=new_only_default)
    newest_first = st.toggle("Newest first", value=newest_first_default)

    show_n = st.slider("Show how many", min_value=5, max_value=200, value=50, step=5)


def is_top_match(it):
    """Top match = price is present AND <= max_price AND acres within range."""
    price = it.get("price")
    acres = it.get("acres")
    if price is None or acres is None:
        return False
    try:
        return (min_acres <= float(acres) <= max_acres) and (int(price) <= int(max_price))
    except Exception:
        return False


def is_new(it):
    """
    NEW badge logic:
    If your scraper later adds found_utc, we can compare it to last_updated
    or a rolling window.
    For now: treat everything as NEW if new_only toggle is used (simple MVP).
    """
    # If you later add found_utc, use it here.
    return True


strict_top_matches = [it for it in items if is_top_match(it)]


with st.expander("Details", expanded=False):
    col1, col2, col3 = st.columns(3)
    col1.metric("All found", f"{len(items)}")
    col2.metric("Top matches", f"{len(strict_top_matches)}")
    col3.metric("Max price", f"${int(max_price):,}")

    st.caption(f"Acre range: {min_acres:g}–{max_acres:g}")


st.divider()


# -----------------------------
# Apply filters
# -----------------------------
filtered = items[:]

# Search (OUTSIDE filters)
if search_query.strip():
    q = search_query.strip().lower()
    filtered = [it for it in filtered if q in searchable_text(it)]

# Top matches filter
if show_top_matches_only:
    filtered = [it for it in filtered if is_top_match(it)]

# New only filter
if new_only:
    filtered = [it for it in filtered if is_new(it)]

# Sorting
if newest_first:
    filtered = sorted(filtered, key=parse_dt, reverse=True)

# Limit
filtered = filtered[:show_n]


# -----------------------------
# Listing Cards
# -----------------------------
def badge_html(text: str, bg: str, fg: str = "white"):
    return f"""
        <span style="
            display:inline-block;
            padding:4px 10px;
            border-radius:999px;
            background:{bg};
            color:{fg};
            font-size:12px;
            font-weight:700;
            margin-right:6px;
        ">{text}</span>
    """


def listing_card(it):
    title = it.get("title") or f"{it.get('source','Listing')} listing"
    url = it.get("url") or ""
    source = it.get("source") or "Unknown"
    price = it.get("price")
    acres = it.get("acres")
    thumb = it.get("thumbnail")

    top_match = is_top_match(it)
    new_flag = is_new(it)

    with st.container(border=True):
        # thumbnail
        if thumb:
            st.image(thumb, use_container_width=True)
        else:
            st.markdown(
                """
                <div style="width:100%; height:220px; background:#f1f3f5; border-radius:16px;
                            display:flex; align-items:center; justify-content:center; color:#666;
                            font-weight:700; font-size:1.05rem;">
                    No preview available
                </div>
                """,
                unsafe_allow_html=True,
            )

        # title
        st.subheader(title)

        # badges
        badges = ""
        if top_match:
            badges += badge_html("⭐ Top match", "#2563eb")
        if new_flag:
            badges += badge_html("🆕 NEW", "#16a34a")
        if not top_match:
            badges += badge_html("FOUND", "#64748b")

        st.markdown(badges, unsafe_allow_html=True)
        st.caption(source)

        # details
        if price is None:
            st.write("**Price:** —")
        else:
            st.write(f"**Price:** ${int(price):,}")

        if acres is None:
            st.write("**Acres:** —")
        else:
            st.write(f"**Acres:** {float(acres):g}")

        if url:
            st.link_button("Open listing ↗", url, use_container_width=True)


# grid layout
cols = st.columns(2)
for idx, it in enumerate(filtered):
    with cols[idx % 2]:
        listing_card(it)

if not filtered:
    st.info("No listings matched your current search/filters.")