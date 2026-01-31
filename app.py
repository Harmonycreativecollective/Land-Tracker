import base64
import json
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

# =========================
# Config / Branding
# =========================
DATA_PATH = Path("data/listings.json")
LOGO_PATH = Path("assets/kblogo.png")  # optional

TITLE = "KB’s Land Tracker"
CAPTION = "What’s meant for you is already in motion."

st.set_page_config(
    page_title=TITLE,
    page_icon="🗺️",  # you can swap to "assets/kblogo.png" once it's working everywhere
    layout="wide",
)

# =========================
# Data load
# =========================
def load_data():
    if not DATA_PATH.exists():
        return {"items": [], "criteria": {}, "last_updated_utc": None}
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

data = load_data()
items = data.get("items", []) or []
criteria = data.get("criteria", {}) or {}
last_updated = data.get("last_updated_utc")

# =========================
# Logo helper
# =========================
def logo_base64(path: Path) -> str | None:
    if not path.exists():
        return None
    try:
        raw = path.read_bytes()
        return base64.b64encode(raw).decode("utf-8")
    except Exception:
        return None

logo_b64 = logo_base64(LOGO_PATH)

# =========================
# UI Header (logo + title + bigger caption)
# =========================
if logo_b64:
    st.markdown(
        f"""
        <div style="display:flex; align-items:center; gap:14px; flex-wrap:wrap;">
          <img src="data:image/png;base64,{logo_b64}" style="height:56px; width:auto; border-radius:12px;" />
          <div>
            <div style="font-size:46px; font-weight:800; line-height:1.05; margin:0;">{TITLE}</div>
            <div style="font-size:18px; opacity:0.75; margin-top:6px;">{CAPTION}</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
else:
    st.title(TITLE)
    st.markdown(f"<div style='font-size:18px; opacity:0.75; margin-top:-6px;'>{CAPTION}</div>", unsafe_allow_html=True)

st.write("")  # spacing

# =========================
# Search (outside of filters)
# =========================
search_query = st.text_input(
    "Search (title / location / source)",
    value="",
    placeholder="Try: king george, port royal, landsearch, 20 acres…",
)

# =========================
# Helpers
# =========================
def parse_iso(dt_str: str):
    try:
        return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
    except Exception:
        return None

def searchable_text(it: dict) -> str:
    # Include title + source + url
    return " ".join([
        str(it.get("title", "")),
        str(it.get("source", "")),
        str(it.get("url", "")),
    ]).lower()

def is_top_match(it: dict, min_acres: float, max_acres: float, max_price: int) -> bool:
    price = it.get("price")
    acres = it.get("acres")
    if price is None or acres is None:
        return False
    try:
        return (min_acres <= float(acres) <= max_acres) and (int(price) <= int(max_price))
    except Exception:
        return False

def is_new(it: dict) -> bool:
    """
    If you later add found_utc/first_seen_utc in the scraper, this will work perfectly.
    For now: if no timestamp exists, treat as NEW (so the badge system still works).
    """
    ts = it.get("found_utc") or it.get("first_seen_utc") or it.get("seen_utc")
    if not ts:
        return True
    dt = parse_iso(ts)
    if not dt:
        return True
    now = datetime.now(timezone.utc)
    age_hours = (now - dt.replace(tzinfo=timezone.utc)).total_seconds() / 3600
    return age_hours <= 48  # "new within 2 days"

def sort_key_newest(it: dict):
    # If you add found_utc later, this sorts properly.
    # Otherwise we fall back to title so it's stable.
    ts = it.get("found_utc") or it.get("first_seen_utc") or ""
    dt = parse_iso(ts) if ts else None
    return dt or datetime(1970, 1, 1, tzinfo=timezone.utc)

# =========================
# Sidebar (dropdowns)
# =========================
st.sidebar.markdown("")

with st.sidebar.expander("Filters", expanded=True):
    max_price = st.number_input("Max price (Top match)", min_value=0, value=600000, step=10000)
    min_acres = st.number_input("Min acres", min_value=0.0, value=11.0, step=1.0, format="%.2f")
    max_acres = st.number_input("Max acres", min_value=0.0, value=50.0, step=1.0, format="%.2f")

    top_matches_only = st.toggle("Top matches only", value=True)
    new_only = st.toggle("New only", value=False)
    newest_first = st.toggle("Newest first", value=True)

    show_n = st.slider("Show how many", min_value=5, max_value=200, value=50, step=5)

with st.sidebar.expander("Details", expanded=False):
    # We'll compute these after filtering logic runs,
    # but the sidebar layout lives here.
    details_placeholder = st.empty()

# Optional “Admin” section (hidden unless you want it)
with st.sidebar.expander("Admin", expanded=False):
    show_debug = st.toggle("Show debug (raw data)", value=False)

# =========================
# Apply search + filters
# =========================
filtered = list(items)

# Search first
if search_query.strip():
    q = search_query.strip().lower()
    filtered = [it for it in filtered if q in searchable_text(it)]

# Compute top match & new flags
def enrich(it: dict) -> dict:
    it2 = dict(it)
    it2["_top_match"] = is_top_match(it2, min_acres, max_acres, int(max_price))
    it2["_new"] = is_new(it2)
    return it2

filtered = [enrich(it) for it in filtered]

# Toggles
if top_matches_only:
    filtered = [it for it in filtered if it["_top_match"]]

if new_only:
    filtered = [it for it in filtered if it["_new"]]

# Sorting
if newest_first:
    filtered = sorted(filtered, key=sort_key_newest, reverse=True)

# Limit
filtered = filtered[:show_n]

# =========================
# Metrics on main page (clean dashboard)
# =========================
all_top = [enrich(it) for it in items]
top_count = sum(1 for it in all_top if it["_top_match"])
new_count = sum(1 for it in all_top if it["_new"])

m1, m2, m3 = st.columns(3)
m1.metric("All found", f"{len(items)}")
m2.metric("Top matches", f"{top_count}")
m3.metric("New", f"{new_count}")

st.write("")  # spacing

# Update Details dropdown content
with details_placeholder.container():
    st.caption(f"Criteria: ${int(max_price):,} max • {min_acres:g}–{max_acres:g} acres")

# =========================
# Last updated (moved OUT of sidebar)
# =========================
if last_updated:
    dt = parse_iso(last_updated)
    if dt:
        st.caption(f"Last updated: {dt.strftime('%b %d, %Y • %I:%M %p UTC')}")
    else:
        st.caption(f"Last updated: {last_updated}")

st.divider()

# =========================
# Listing card
# =========================
def pill(label: str, bg: str, border: str) -> str:
    return f"""
    <span style="
      display:inline-block;
      padding:4px 10px;
      border-radius:999px;
      background:{bg};
      border:1px solid {border};
      font-size:12px;
      font-weight:700;
      margin-right:6px;
      ">
      {label}
    </span>
    """

def listing_card(it: dict):
    title = (it.get("title") or "").strip()
    source = (it.get("source") or "").strip()
    url = it.get("url") or ""
    price = it.get("price")
    acres = it.get("acres")
    thumb = it.get("thumbnail")

    # Smarter fallback title
    if not title or title.lower() == "land listing":
        title = f"{source} listing" if source else "Land listing"

    top = bool(it.get("_top_match"))
    new = bool(it.get("_new"))

    with st.container(border=True):
        # Image / placeholder
        if thumb:
            st.image(thumb, use_container_width=True)
        else:
            st.markdown(
                """
                <div style="width:100%; height:220px; background:#f3f4f6; border-radius:16px;
                            display:flex; align-items:center; justify-content:center; color:#6b7280;
                            font-weight:700;">
                    No preview available
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.subheader(title)

        # Badges row (no visible code)
        badges = ""
        if top:
            badges += pill("⭐ Top match", "rgba(245, 158, 11, 0.12)", "rgba(245, 158, 11, 0.35)")
        if new:
            badges += pill("🆕 New", "rgba(34, 197, 94, 0.12)", "rgba(34, 197, 94, 0.35)")
        if not top and not new:
            badges += pill("FOUND", "rgba(99, 102, 241, 0.10)", "rgba(99, 102, 241, 0.25)")

        st.markdown(badges, unsafe_allow_html=True)
        st.caption(source)

        # Price + acres
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

# =========================
# Grid
# =========================
cols = st.columns(2)
for i, it in enumerate(filtered):
    with cols[i % 2]:
        listing_card(it)

if not filtered:
    st.info("No listings matched your current search/filters.")

# =========================
# Debug (Admin)
# =========================
if show_debug:
    st.divider()
    st.subheader("Debug")
    st.write("Criteria (from file):", criteria)
    st.write("Items (first 3):")
    st.json(items[:3])