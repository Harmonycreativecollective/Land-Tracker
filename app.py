import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

import streamlit as st

DATA_PATH = Path("data/listings.json")

TITLE = "KB’s Land Tracker"
CAPTION = "What’s meant for you is already in motion."

st.set_page_config(
    page_title=TITLE,
    page_icon="assets/kblogo.png",
    layout="wide",
)

# ---------- Header (Logo + Title) ----------
col1, col2 = st.columns([2, 7], vertical_alignment="center")

with col1:
    st.image("assets/kblogo.png", width=140)

with col2:
    st.markdown(
        f"""
        <div style="line-height:1.05; padding-top: 14px;">
            <h1 style="margin:0;">{TITLE}</h1>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.divider()

# Bigger caption (instead of st.caption)
st.markdown(
    f"""
    <p style="font-size:1.45rem; color:#6b7280; margin-top:-6px; margin-bottom:18px;">
        {CAPTION}
    </p>
    """,
    unsafe_allow_html=True,
)

# ---------- Load data ----------
def load_data():
    if not DATA_PATH.exists():
        return {"items": [], "criteria": {}, "last_updated_utc": None}
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

data = load_data()
items = data.get("items", [])
last_updated = data.get("last_updated_utc")

# ✅ Search OUTSIDE filters (top-of-page)
search_query = st.text_input(
    "Search (title / location / source)",
    value="",
    placeholder="Try: king george, port royal, landsearch, 20 acres…",
).strip().lower()

# ---------- Defaults (overridden in expander) ----------
max_price = 600000
min_acres = 11.0
max_acres = 50.0
show_top_matches = False
show_matches_only = False
sort_newest = True
show_n = 50

# ---------- Helpers ----------
def is_match(it):
    price = it.get("price")
    acres = it.get("acres")
    if price is None or acres is None:
        return False
    return (min_acres <= float(acres) <= max_acres) and (int(price) <= int(max_price))

def searchable_text(it):
    return " ".join([
        str(it.get("title", "")),
        str(it.get("source", "")),
        str(it.get("url", "")),
    ]).lower()

def parse_dt(it):
    # Sort by found_utc if present; otherwise blank.
    return it.get("found_utc") or ""

def parse_iso_utc(value: str):
    if not value:
        return None
    try:
        # handles "Z" or "+00:00"
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        return None

def is_new_listing(it, hours=48):
    dt = parse_iso_utc(it.get("found_utc", ""))
    if not dt:
        return False
    return dt >= (datetime.now(timezone.utc) - timedelta(hours=hours))

def format_last_updated(last_updated_value):
    if not last_updated_value:
        return None
    try:
        dt = datetime.fromisoformat(last_updated_value.replace("Z", "+00:00"))
        return dt.strftime("%b %d, %Y • %I:%M %p UTC")
    except Exception:
        return str(last_updated_value)

def badge_row(match: bool, top_match: bool, new: bool):
    # Minimal, clean badges
    chips = []
    if top_match:
        chips.append(
            '<span style="display:inline-flex; align-items:center; gap:6px; padding:4px 10px; '
            'border-radius:999px; background:rgba(245,158,11,.14); border:1px solid rgba(245,158,11,.35); '
            'font-size:12px; font-weight:700; color:#92400e;">⭐ Top match</span>'
        )
    elif match:
        chips.append(
            '<span style="display:inline-flex; align-items:center; gap:6px; padding:4px 10px; '
            'border-radius:999px; background:rgba(16,185,129,.12); border:1px solid rgba(16,185,129,.35); '
            'font-size:12px; font-weight:700; color:#065f46;">MATCH</span>'
        )
    else:
        chips.append(
            '<span style="display:inline-flex; align-items:center; gap:6px; padding:4px 10px; '
            'border-radius:999px; background:rgba(107,114,128,.10); border:1px solid rgba(107,114,128,.25); '
            'font-size:12px; font-weight:700; color:#374151;">FOUND</span>'
        )

    if new:
        chips.append(
            '<span style="display:inline-flex; align-items:center; gap:6px; padding:4px 10px; '
            'border-radius:999px; background:rgba(59,130,246,.12); border:1px solid rgba(59,130,246,.35); '
            'font-size:12px; font-weight:800; color:#1d4ed8;">🆕 NEW</span>'
        )

    return " ".join(chips)

# ---------- Filters & Details (HIDES the “dashboard stuff”) ----------
with st.expander("Filters & Details", expanded=False):
    st.subheader("Filters")

    max_price = st.number_input(
        "Max price (STRICT matches)",
        min_value=0,
        value=600000,
        step=10000,
    )

    c1, c2 = st.columns(2)
    with c1:
        min_acres = st.number_input(
            "Min acres",
            min_value=0.0,
            value=11.0,
            step=1.0,
        )
    with c2:
        max_acres = st.number_input(
            "Max acres",
            min_value=0.0,
            value=50.0,
            step=1.0,
        )

    show_top_matches = st.toggle("Top matches only", value=False)
    show_matches_only = st.toggle("STRICT matches only", value=False)
    sort_newest = st.toggle("Newest first", value=True)

    show_n = st.slider("Show how many", min_value=5, max_value=200, value=50, step=5)

    st.divider()

    # ---------- Metrics (inside dropdown) ----------
    strict_matches = [it for it in items if is_match(it)]
    st.subheader("Details")

    m1, m2, m3 = st.columns(3)
    m1.metric("All found", f"{len(items)}")
    m2.metric("Strict matches", f"{len(strict_matches)}")
    m3.metric("Max price", f"${max_price:,.0f}")

    st.caption(f"Acre range: {min_acres:g}–{max_acres:g}")

    pretty_last = format_last_updated(last_updated)
    if pretty_last:
        st.caption(f"Last updated: {pretty_last}")

st.divider()

# ---------- Apply filters ----------
filtered = items[:]

# Search first (OUTSIDE filters)
if search_query:
    filtered = [it for it in filtered if search_query in searchable_text(it)]

# Match toggles
if show_matches_only:
    filtered = [it for it in filtered if is_match(it)]
elif show_top_matches:
    filtered = [it for it in filtered if is_match(it)]

# Sorting
if sort_newest:
    filtered = sorted(filtered, key=parse_dt, reverse=True)

# Limit
filtered = filtered[:show_n]

# ---------- Listing cards ----------
def listing_card(it):
    title = it.get("title") or "Land listing"
    url = it.get("url") or ""
    source = it.get("source") or ""
    price = it.get("price")
    acres = it.get("acres")
    thumb = it.get("thumbnail")

    match = is_match(it)

    # ⭐ only when user is specifically viewing top/strict modes AND it matches
    top_badge = bool(match and (show_top_matches or show_matches_only))
    new_badge = is_new_listing(it, hours=48)

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

        # Title
        st.subheader(title)

        # Badges + source
        st.markdown(
            f"""
            <div style="display:flex; flex-wrap:wrap; align-items:center; gap:8px; margin-top:-8px;">
                {badge_row(match=match, top_match=top_badge, new=new_badge)}
                <span style="color:#6b7280; font-size:12px; font-weight:600;">• {source}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Price / acres
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

# Grid (2 columns)
cols = st.columns(2)
for idx, it in enumerate(filtered):
    with cols[idx % 2]:
        listing_card(it)

if not filtered:
    st.info("No listings matched your current search/filters.")