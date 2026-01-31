import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

import streamlit as st

DATA_PATH = Path("data/listings.json")

st.set_page_config(
    page_title="KB’s Land Tracker",
    page_icon="🗺️",
    layout="wide",
)

TITLE = "KB’s Land Tracker"
CAPTION = "What’s meant for you is already in motion."

# ---------- Load data ----------
def load_data():
    if not DATA_PATH.exists():
        return {"items": [], "criteria": {}, "last_updated_utc": None}
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

data = load_data()
items = data.get("items", [])
last_updated = data.get("last_updated_utc")

# ---------- Helpers ----------
def searchable_text(it):
    return " ".join([
        str(it.get("title", "")),
        str(it.get("source", "")),
        str(it.get("url", "")),
    ]).lower()

def parse_iso_utc(value: str):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        return None

def is_new_listing(it, hours=48):
    dt = parse_iso_utc(it.get("found_utc", ""))
    if not dt:
        return False
    return dt >= (datetime.now(timezone.utc) - timedelta(hours=hours))

def sort_key(it):
    dt = parse_iso_utc(it.get("found_utc", ""))
    return dt or datetime.min.replace(tzinfo=timezone.utc)

def format_last_updated(last_updated_value):
    if not last_updated_value:
        return None
    try:
        dt = datetime.fromisoformat(last_updated_value.replace("Z", "+00:00"))
        return dt.strftime("%b %d, %Y • %I:%M %p UTC")
    except Exception:
        return str(last_updated_value)

# ---------- Header ----------
st.title(TITLE)

st.markdown(
    f"""
    <p style="font-size:1.45rem; color:#6b7280; margin-top:-10px; margin-bottom:8px;">
        {CAPTION}
    </p>
    """,
    unsafe_allow_html=True,
)

# ✅ Last updated OUTSIDE filters/details
pretty_last = format_last_updated(last_updated)
if pretty_last:
    st.caption(f"Last updated: {pretty_last}")

st.write("")

# ✅ Search OUTSIDE everything
search_query = st.text_input(
    "Search (title / location / source)",
    value="",
    placeholder="Try: king george, port royal, landsearch, 20 acres…",
).strip().lower()

# ---------- Defaults (editable via Filters box) ----------
max_price = 600000
min_acres = 11.0
max_acres = 50.0

top_matches_only = True
new_only = False
newest_first = True
show_n = 50

def is_top_match(it):
    """
    ⭐ Top match:
    - acres in range
    - AND (price <= max_price OR price missing)
    """
    acres = it.get("acres")
    price = it.get("price")

    if acres is None:
        return False

    acres_ok = (min_acres <= float(acres) <= max_acres)

    if price is None:
        price_ok = True
    else:
        price_ok = int(price) <= int(max_price)

    return acres_ok and price_ok

def badge_row(top_match: bool, new: bool, source: str):
    chips = []

    if top_match:
        chips.append(
            '<span style="display:inline-flex; align-items:center; gap:6px; padding:4px 10px; '
            'border-radius:999px; background:rgba(245,158,11,.14); border:1px solid rgba(245,158,11,.35); '
            'font-size:12px; font-weight:800; color:#92400e;">⭐ Top match</span>'
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
            'font-size:12px; font-weight:900; color:#1d4ed8;">🆕 NEW</span>'
        )

    chips.append(
        f'<span style="color:#6b7280; font-size:12px; font-weight:600;">• {source}</span>'
    )

    return " ".join(chips)

# ---------- Filters + Details (TWO BOXES) ----------
f_col, d_col = st.columns([1, 1])

with f_col:
    with st.container(border=True):
        st.subheader("Filters")

        max_price = st.number_input(
            "Max price (Top match)",
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

        top_matches_only = st.toggle("Top matches only", value=True)
        new_only = st.toggle("New only", value=False)
        newest_first = st.toggle("Newest first", value=True)

        show_n = st.slider("Show how many", 5, 200, 50, step=5)

with d_col:
    with st.container(border=True):
        st.subheader("Details")

        top_matches = [it for it in items if is_top_match(it)]
        new_matches = [it for it in items if is_new_listing(it, hours=48)]

        m1, m2, m3 = st.columns(3)
        m1.metric("All found", f"{len(items)}")
        m2.metric("Top matches", f"{len(top_matches)}")
        m3.metric("New", f"{len(new_matches)}")

        st.caption(f"Criteria: ${max_price:,.0f} max • {min_acres:g}–{max_acres:g} acres")

st.divider()

# ---------- Apply filters ----------
filtered = items[:]

# Search first
if search_query:
    filtered = [it for it in filtered if search_query in searchable_text(it)]

# filters
if top_matches_only:
    filtered = [it for it in filtered if is_top_match(it)]

if new_only:
    filtered = [it for it in filtered if is_new_listing(it, hours=48)]

# sort
if newest_first:
    filtered = sorted(filtered, key=sort_key, reverse=True)

# limit
filtered = filtered[:show_n]

# ---------- Listing cards ----------
def listing_card(it):
    title = it.get("title") or f"{it.get('source', 'Listing')} listing"
    url = it.get("url") or ""
    source = it.get("source") or ""
    price = it.get("price")
    acres = it.get("acres")
    thumb = it.get("thumbnail")

    top_match = is_top_match(it)
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

        st.subheader(title)

        st.markdown(
            f"""
            <div style="display:flex; flex-wrap:wrap; align-items:center; gap:8px; margin-top:-8px;">
                {badge_row(top_match=top_match, new=new_badge, source=source)}
            </div>
            """,
            unsafe_allow_html=True,
        )

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

# Grid
cols = st.columns(2)
for idx, it in enumerate(filtered):
    with cols[idx % 2]:
        listing_card(it)

if not filtered:
    st.info("No listings matched your current search/filters.")