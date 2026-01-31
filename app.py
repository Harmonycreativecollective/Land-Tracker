import base64
import json
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

DATA_PATH = Path("data/listings.json")
LOGO_PATH = Path("assets/kblogo.png")

TITLE = "KB’s Land Tracker"
CAPTION = "What’s meant for you is already in motion."


# ---------------- Page config ----------------
st.set_page_config(
    page_title=TITLE,
    page_icon=str(LOGO_PATH) if LOGO_PATH.exists() else "🗺️",
    layout="wide",
)


# ---------------- Data loading ----------------
def load_data():
    if not DATA_PATH.exists():
        return {"items": [], "criteria": {}, "last_updated_utc": None}
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


data = load_data()
items = data.get("items", [])
last_updated = data.get("last_updated_utc")
criteria = data.get("criteria", {})


# ---------------- Helpers ----------------
def safe_title(it: dict) -> str:
    t = (it.get("title") or "").strip()
    if t and t.lower() != "land listing":
        return t
    src = (it.get("source") or "Listing").strip()
    return f"{src} listing"


def parse_price(it: dict):
    p = it.get("price")
    try:
        return int(p) if p is not None else None
    except Exception:
        return None


def parse_acres(it: dict):
    a = it.get("acres")
    try:
        return float(a) if a is not None else None
    except Exception:
        return None


def is_top_match(it: dict, min_acres: float, max_acres: float, max_price: int) -> bool:
    p = parse_price(it)
    a = parse_acres(it)
    if p is None or a is None:
        return False
    return (min_acres <= a <= max_acres) and (p <= max_price)


def is_new(it: dict, hours: int = 48) -> bool:
    """
    NEW is best-effort:
    - If scraper later adds found_utc/first_seen_utc, we use it.
    - If not present, we treat everything as NEW for now (so you still get the badge).
    """
    ts = it.get("found_utc") or it.get("first_seen_utc")
    if not ts:
        return True  # no timestamp available yet -> treat as new
    try:
        dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        age_hours = (datetime.now(timezone.utc) - dt).total_seconds() / 3600
        return age_hours <= hours
    except Exception:
        return True


def searchable_text(it: dict) -> str:
    return " ".join(
        [
            str(it.get("title", "")),
            str(it.get("source", "")),
            str(it.get("url", "")),
        ]
    ).lower()


def sort_key_newest(it: dict):
    # If timestamps exist later, this will truly sort by newest.
    # For now: stable ordering + keeps it from breaking.
    return it.get("found_utc") or it.get("first_seen_utc") or ""


def load_logo_base64(path: Path) -> str:
    if not path.exists():
        return ""
    return base64.b64encode(path.read_bytes()).decode("utf-8")


# ---------------- Header (HTML) ----------------
logo_b64 = load_logo_base64(LOGO_PATH)

# Auto-scale header: logo scales with viewport, title wraps cleanly on mobile
header_html = f"""
<div style="
    display:flex;
    align-items:center;
    gap:clamp(12px, 2vw, 22px);
    margin-top: 6px;
    margin-bottom: 8px;
">
  <div style="flex:0 0 auto;">
    {"<img src='data:image/png;base64," + logo_b64 + "' style='width:clamp(70px, 14vw, 120px); height:auto; display:block;' />" if logo_b64 else ""}
  </div>

  <div style="flex:1 1 auto; min-width:0;">
    <div style="
        font-size:clamp(2.0rem, 5.6vw, 3.2rem);
        font-weight:900;
        line-height:1.05;
        color:#0f172a;
        margin:0;
        word-break:break-word;
        overflow-wrap:anywhere;
    ">{TITLE}</div>

    <div style="
        font-size:clamp(1.05rem, 2.8vw, 1.35rem);
        color:rgba(49, 51, 63, 0.75);
        margin-top:10px;
        line-height:1.35;
    ">{CAPTION}</div>
  </div>
</div>
"""

st.markdown(header_html, unsafe_allow_html=True)


# ---------------- Last updated (OUTSIDE dropdowns) ----------------
if last_updated:
    try:
        dt = datetime.fromisoformat(str(last_updated).replace("Z", "+00:00"))
        st.caption(f"Last updated: {dt.strftime('%b %d, %Y • %I:%M %p UTC')}")
    except Exception:
        st.caption(f"Last updated: {last_updated}")

st.write("")  # small spacer


# ✅ Search outside filters (top of page)
search_query = st.text_input(
    "Search (title / location / source)",
    value="",
    placeholder="Try: king george, port royal, landsearch, 20 acres…",
)


# ---------------- Default criteria values ----------------
default_min_acres = float(criteria.get("min_acres", 11.0) or 11.0)
default_max_acres = float(criteria.get("max_acres", 50.0) or 50.0)
default_max_price = int(criteria.get("max_price", 600000) or 600000)


# ---------------- Filters + Details dropdowns ----------------
with st.expander("Filters", expanded=False):
    max_price = st.number_input(
        "Max price (Top match)",
        min_value=0,
        value=default_max_price,
        step=10000,
    )

    min_acres = st.number_input(
        "Min acres",
        min_value=0.0,
        value=default_min_acres,
        step=1.0,
    )

    max_acres = st.number_input(
        "Max acres",
        min_value=0.0,
        value=default_max_acres,
        step=1.0,
    )

    # Defaults
    show_top_only = st.toggle("Top matches only", value=True)
    new_only = st.toggle("New only", value=False)
    newest_first = st.toggle("Newest first", value=True)

    show_n = st.slider("Show how many", min_value=5, max_value=200, value=50, step=5)

# Compute metrics BEFORE Details so it always matches filters/criteria
top_count = sum(1 for it in items if is_top_match(it, min_acres, max_acres, max_price))
new_count = sum(1 for it in items if is_new(it, hours=48))

with st.expander("Details", expanded=False):
    st.caption(f"Criteria: ${max_price:,.0f} max • {min_acres:g}–{max_acres:g} acres")

    c1, c2, c3 = st.columns(3)
    c1.metric("All found", f"{len(items)}")
    c2.metric("Top matches", f"{top_count}")
    c3.metric("New", f"{new_count}")


# ---------------- Apply filters ----------------
filtered = items[:]

# Search first
if search_query.strip():
    q = search_query.strip().lower()
    filtered = [it for it in filtered if q in searchable_text(it)]

# New only
if new_only:
    filtered = [it for it in filtered if is_new(it, hours=48)]

# Top only
if show_top_only:
    filtered = [it for it in filtered if is_top_match(it, min_acres, max_acres, max_price)]

# Sort newest
if newest_first:
    filtered = sorted(filtered, key=sort_key_newest, reverse=True)

# Limit
filtered = filtered[:show_n]

st.divider()


# ---------------- Listing cards ----------------
def listing_card(it: dict):
    title = safe_title(it)
    url = it.get("url") or ""
    source = it.get("source") or ""
    price = parse_price(it)
    acres = parse_acres(it)
    thumb = it.get("thumbnail")

    top = is_top_match(it, min_acres, max_acres, max_price)
    new_flag = is_new(it, hours=48)

    # Badge line
    badges = []
    if top:
        badges.append("⭐ Top match")
    if new_flag:
        badges.append("🆕 NEW")
    if not top:
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
        st.caption(" • ".join([b for b in badges if b]) + (f" • {source}" if source else ""))

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


# 2-column grid (works fine on mobile too)
cols = st.columns(2)
for idx, it in enumerate(filtered):
    with cols[idx % 2]:
        listing_card(it)

if not filtered:
    st.info("No listings matched your current search/filters.")