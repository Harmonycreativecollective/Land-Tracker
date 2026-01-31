import base64
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import streamlit as st
import streamlit.components.v1 as components

DATA_PATH = Path("data/listings.json")
LOGO_PATH = Path("assets/kblogo.png")

TITLE = "KB’s Land Tracker"
CAPTION = "What’s meant for you is already in motion."


# -------------------- Page config --------------------
st.set_page_config(
    page_title=TITLE,
    page_icon="assets/kblogo.png" if LOGO_PATH.exists() else "🗺️",
    layout="wide",
)


# -------------------- Helpers --------------------
def load_data() -> Dict[str, Any]:
    if not DATA_PATH.exists():
        return {"items": [], "criteria": {}, "last_updated_utc": None}
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def img_to_base64(path: Path) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def parse_iso_dt(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    try:
        # handles "+00:00" and "Z"
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None


def money(v: Any) -> Optional[int]:
    if v is None:
        return None
    try:
        return int(float(v))
    except Exception:
        return None


def acres_val(v: Any) -> Optional[float]:
    if v is None:
        return None
    try:
        return float(v)
    except Exception:
        return None


# -------------------- Data --------------------
data = load_data()
items = data.get("items", []) or []
last_updated_utc = data.get("last_updated_utc")

# -------------------- Responsive header --------------------
logo_b64 = img_to_base64(LOGO_PATH) if LOGO_PATH.exists() else ""

header_html = f"""
<style>
/* Container */
.kb-header {{
  display:flex;
  align-items:center;
  gap: clamp(12px, 2vw, 18px);
  padding: 10px 0 6px 0;
}}

/* Logo */
.kb-logo {{
  width: clamp(86px, 16vw, 120px);
  height: clamp(86px, 16vw, 120px);
  object-fit: contain;
  border-radius: 18px;
  flex: 0 0 auto;
}}

/* Text block */
.kb-text {{
  flex: 1 1 auto;
  min-width: 0; /* allows wrapping instead of overflow */
}}

/* Title */
.kb-title {{
  font-size: clamp(2.05rem, 4.6vw, 3.1rem);
  font-weight: 900;
  line-height: 1.05;
  margin: 0;
  color: #0f172a;

  /* wrapping controls */
  max-width: 22ch;
  word-break: keep-all;
  overflow-wrap: anywhere;
}}

/* Caption */
.kb-caption {{
  font-size: clamp(1.05rem, 2.6vw, 1.35rem);
  color: rgba(49, 51, 63, 0.72);
  margin-top: 8px;
  font-weight: 500;
}}

/* Mobile tweaks */
@media (max-width: 480px) {{
  .kb-title {{ max-width: 16ch; }}
  .kb-caption {{ margin-top: 6px; }}
}}
</style>

<div class="kb-header">
  {"<img class='kb-logo' src='data:image/png;base64," + logo_b64 + "' />" if logo_b64 else ""}
  <div class="kb-text">
    <div class="kb-title">{TITLE}</div>
    <div class="kb-caption">{CAPTION}</div>
  </div>
</div>
"""

components.html(header_html, height=170)

# Last updated OUTSIDE Filters/Details
if last_updated_utc:
    dt = parse_iso_dt(last_updated_utc)
    if dt:
        st.caption(f"Last updated: {dt.strftime('%b %d, %Y • %I:%M %p UTC')}")
    else:
        st.caption(f"Last updated: {last_updated_utc}")

st.write("")  # a little breathing room


# -------------------- Search (outside filters) --------------------
search_query = st.text_input(
    "Search (title / location / source)",
    value="",
    placeholder="Try: king george, port royal, landsearch, 20 acres…",
)


# -------------------- Default filter values --------------------
default_max_price = int(data.get("criteria", {}).get("max_price") or 600000)
default_min_acres = float(data.get("criteria", {}).get("min_acres") or 11.0)
default_max_acres = float(data.get("criteria", {}).get("max_acres") or 50.0)


# -------------------- Filters + Details dropdowns --------------------
colA, colB = st.columns([1, 1])

with colA:
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

        top_matches_only = st.toggle("Top matches only", value=True)
        new_only = st.toggle("New only", value=False)  # future-ready
        newest_first = st.toggle("Newest first", value=True)

        show_n = st.slider("Show how many", min_value=5, max_value=200, value=50, step=5)

with colB:
    with st.expander("Details", expanded=False):
        st.caption(f"Criteria: ${max_price:,.0f} max • {min_acres:g}–{max_acres:g} acres")
        st.write("")


# -------------------- Matching + “New” logic --------------------
def is_top_match(it: Dict[str, Any]) -> bool:
    p = money(it.get("price"))
    a = acres_val(it.get("acres"))
    if p is None or a is None:
        return False
    return (min_acres <= a <= max_acres) and (p <= max_price)


def is_new(it: Dict[str, Any]) -> bool:
    """
    Future-ready:
    - If your scraper later writes `found_utc`, we treat items found in last 24h as new.
    - If you later write `is_new: true`, we'll respect it.
    For now, if nothing exists, everything is considered "new" ONLY for the counter.
    """
    if it.get("is_new") is True:
        return True
    if it.get("new") is True:
        return True
    dt = parse_iso_dt(it.get("found_utc"))
    if not dt:
        return True  # no timestamp yet -> treat as new for now
    return (datetime.now(timezone.utc) - dt).total_seconds() <= 24 * 3600


def searchable_text(it: Dict[str, Any]) -> str:
    return " ".join(
        [
            str(it.get("title", "")),
            str(it.get("source", "")),
            str(it.get("url", "")),
        ]
    ).lower()


def sort_key(it: Dict[str, Any]) -> str:
    # If found_utc is missing, sort_key will be empty; order will fall back to original
    return it.get("found_utc") or ""


# -------------------- Apply search + filters --------------------
filtered = list(items)

if search_query.strip():
    q = search_query.strip().lower()
    filtered = [it for it in filtered if q in searchable_text(it)]

if top_matches_only:
    filtered = [it for it in filtered if is_top_match(it)]

if new_only:
    filtered = [it for it in filtered if is_new(it)]

if newest_first:
    filtered = sorted(filtered, key=sort_key, reverse=True)

filtered = filtered[:show_n]


# -------------------- Metrics (top-of-page, clean) --------------------
top_matches_all = [it for it in items if is_top_match(it)]
new_all = [it for it in items if is_new(it)]

m1, m2, m3 = st.columns(3)
m1.metric("All found", f"{len(items)}")
m2.metric("Top matches", f"{len(top_matches_all)}")
m3.metric("New", f"{len(new_all)}")

st.divider()


# -------------------- Card UI bits --------------------
def badge_row(top: bool, new: bool) -> str:
    badges = []
    if top:
        badges.append("<span style='padding:4px 10px;border-radius:999px;background:#111827;color:white;font-weight:700;'>⭐ Top match</span>")
    if new:
        badges.append("<span style='padding:4px 10px;border-radius:999px;background:#0ea5e9;color:white;font-weight:700;'>🆕 New</span>")
    if not badges:
        badges.append("<span style='padding:4px 10px;border-radius:999px;background:#e5e7eb;color:#111827;font-weight:700;'>✅ Found</span>")
    return " ".join(badges)


def listing_card(it: Dict[str, Any]):
    title = (it.get("title") or "").strip() or f"{(it.get('source') or 'Listing')} listing"
    url = it.get("url") or ""
    source = it.get("source") or "Source"
    p = money(it.get("price"))
    a = acres_val(it.get("acres"))
    thumb = it.get("thumbnail")

    top = is_top_match(it)
    new = is_new(it)

    with st.container(border=True):
        if thumb:
            st.image(thumb, use_container_width=True)
        else:
            # Placeholder block (you can later replace with your own image)
            st.markdown(
                """
                <div style="width:100%; height:220px; background:#f2f2f2; border-radius:16px;
                            display:flex; align-items:center; justify-content:center; color:#777;
                            font-weight:700;">
                    No preview available
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.markdown(badge_row(top, new), unsafe_allow_html=True)
        st.subheader(title)
        st.caption(f"{source}")

        if p is None:
            st.write("**Price:** —")
        else:
            st.write(f"**Price:** ${p:,}")

        if a is None:
            st.write("**Acres:** —")
        else:
            st.write(f"**Acres:** {a:g}")

        if url:
            st.link_button("Open listing ↗", url, use_container_width=True)


# -------------------- Results grid --------------------
cols = st.columns(2)
for idx, it in enumerate(filtered):
    with cols[idx % 2]:
        listing_card(it)

if not filtered:
    st.info("No listings matched your current search/filters.")