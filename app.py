import base64
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import streamlit as st

# ---------- Paths ----------
DATA_PATH = Path("data/listings.json")
LOGO_PATH = Path("assets/kblogo.png")
PLACEHOLDER_PATH = Path("assets/previewkb.png")

# ---------- Page config ----------
st.set_page_config(
    page_title="KB’s Land Tracker",
    page_icon=str(LOGO_PATH) if LOGO_PATH.exists() else "🗺️",
    layout="wide",
)

TITLE = "KB’s Land Tracker"
CAPTION = "What’s meant for you is already in motion."

# ---------- CSS ----------
st.markdown("""
<style>
/* Card image wrapper */
.listing-image {
  position: relative;
  width: 100%;
  border-radius: 16px;
  overflow: hidden;
  background: linear-gradient(180deg, #f6f7f9, #eef0f3);
}

/* Image itself */
.listing-image img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

/* Desktop size cap */
@media (min-width: 900px) {
  .listing-image {
    max-height: 260px;
  }
}

/* Mobile size */
@media (max-width: 899px) {
  .listing-image {
    max-height: 200px;
  }
}

/* Preview overlay */
.preview-overlay {
  position: absolute;
  left: 50%;
  top: 58%;
  transform: translate(-50%, -50%);
  padding: 8px 14px;
  border-radius: 999px;
  font-size: 0.85rem;
  font-weight: 500;
  color: #444;
  background: rgba(255,255,255,0.75);
  backdrop-filter: blur(6px);
  box-shadow: 0 2px 8px rgba(0,0,0,0.08);
}
</style>
""", unsafe_allow_html=True)

# ---------- Load data ----------
def load_data() -> Dict[str, Any]:
    if not DATA_PATH.exists():
        return {"items": [], "criteria": {}, "last_updated_utc": None}
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

data = load_data()
items = data.get("items", [])
criteria = data.get("criteria", {})
last_updated = data.get("last_updated_utc")

# ---------- Time ----------
def format_time(ts: str) -> str:
    if not ts:
        return ""
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return dt.strftime("%b %d, %Y • %I:%M %p")
    except Exception:
        return ts

# ---------- Status ----------
STATUS_LABELS = {
    "available": "🟢 Available",
    "under_contract": "🟡 Under contract",
    "pending": "⏳ Pending",
    "sold": "🛑 Sold",
    "unknown": "⚪ Status unknown",
}

def get_status(it):
    s = (it.get("status") or "unknown").lower()
    return s if s in STATUS_LABELS else "unknown"

def unavailable(s):
    return s in {"under_contract", "pending", "sold"}

# ---------- Match logic ----------
def is_top(it):
    return (
        not unavailable(get_status(it))
        and it.get("price") is not None
        and it.get("acres") is not None
        and it["price"] <= criteria.get("max_price", 600000)
    )

def is_possible(it):
    return (
        not unavailable(get_status(it))
        and it.get("acres") is not None
        and it.get("price") is None
    )

def is_former(it):
    return unavailable(get_status(it)) and it.get("ever_top_match", False)

# ---------- Header ----------
st.title(TITLE)
st.caption(CAPTION)

if last_updated:
    st.caption(f"Last updated: {format_time(last_updated)}")

st.divider()

# ---------- Listing card ----------
def listing_card(it: Dict[str, Any]):
    title = it.get("title", "Land listing")
    source = it.get("source", "")
    url = it.get("url")
    price = it.get("price")
    acres = it.get("acres")
    thumb = it.get("thumbnail")

    badges = []
    if is_top(it):
        badges.append("✨ Top match")
    elif is_possible(it):
        badges.append("🧩 Possible match")
    elif is_former(it):
        badges.append("⭐ Former top match")
    else:
        badges.append("🔎 Found")

    badges.append(STATUS_LABELS[get_status(it)])
    badges.append(source)

    # ---------- Image logic ----------
    has_real_image = bool(thumb)

    if has_real_image:
        image_html = f"""
        <div class="listing-image">
            <img src="{thumb}">
        </div>
        """
    else:
        image_html = f"""
        <div class="listing-image">
            <img src="{PLACEHOLDER_PATH}">
            <div class="preview-overlay">Preview not available</div>
        </div>
        """

    with st.container(border=True):
        st.markdown(image_html, unsafe_allow_html=True)

        st.subheader(title)
        st.caption(" • ".join(badges))

        st.write(f"**Price:** ${price:,.0f}" if price else "**Price:** —")
        st.write(f"**Acres:** {acres:g}" if acres else "**Acres:** —")

        if url:
            st.link_button("Open listing ↗", url, use_container_width=True)

# ---------- Render ----------
cols = st.columns(2)
for i, it in enumerate(items):
    with cols[i % 2]:
        listing_card(it)
