import base64
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import streamlit as st

# ---------- Paths ----------
DATA_PATH = Path("data/listings.json")
LOGO_PATH = Path("assets/kblogo.png")
PREVIEW_PATH = Path("assets/previewkb.png")

# ---------- Page config ----------
st.set_page_config(
    page_title="KB’s Land Tracker",
    page_icon=str(LOGO_PATH) if LOGO_PATH.exists() else "🗺️",
    layout="wide",
)

TITLE = "KB’s Land Tracker"
CAPTION = "What’s meant for you is already in motion."


# ---------- Load data ----------
def load_data() -> Dict[str, Any]:
    if not DATA_PATH.exists():
        return {"items": [], "criteria": {}, "last_updated_utc": None}
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


data = load_data()
items: List[Dict[str, Any]] = data.get("items", []) or []
criteria = data.get("criteria", {}) or {}
last_updated = data.get("last_updated_utc")


# ---------- Time formatting (Eastern) ----------
def format_ts_et(ts: str) -> str:
    if not ts:
        return ""
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        from zoneinfo import ZoneInfo  # py3.9+
        dt_et = dt.astimezone(ZoneInfo("America/New_York"))
        return dt_et.strftime("%b %d, %Y • %I:%M %p ET")
    except Exception:
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            return dt.strftime("%b %d, %Y • %I:%M %p")
        except Exception:
            return ts


# ---------- Header (logo left, text right) ----------
def render_header():
    logo_b64 = ""
    if LOGO_PATH.exists():
        logo_b64 = base64.b64encode(LOGO_PATH.read_bytes()).decode("utf-8")

    st.markdown(
        f"""
        <style>
          .kb-header {{
            display:flex;
            align-items:center;
            gap:16px;
            margin-top: 0.25rem;
            margin-bottom: 0.35rem;
          }}
          .kb-logo {{
            width:140px;
            height:140px;
            flex: 0 0 140px;
            border-radius: 16px;
            object-fit: contain;
          }}
          .kb-text {{
            flex: 1 1 auto;
            min-width: 0;
          }}
          .kb-title {{
            font-size: clamp(1.55rem, 3.3vw, 2.05rem);
            font-weight: 900;
            line-height: 1.05;
            margin: 0;
            color: #0f172a;
            overflow-wrap: anywhere;
            word-break: break-word;
          }}
          .kb-caption {{
            font-size: clamp(1.05rem, 2.5vw, 1.22rem);
            color: rgba(49, 51, 63, 0.75);
            margin-top: 8px;
            line-height: 1.35;
            overflow-wrap: anywhere;
            word-break: break-word;
          }}

          /* Placeholder card media */
          .kb-media {{
            position: relative;
            width: 100%;
            border-radius: 16px;
            overflow: hidden;
            background: #f3f4f6;
            border: 1px solid rgba(15, 23, 42, 0.06);
          }}
          .kb-media img {{
            display:block;
            width: 100%;
            max-height: 260px;          /* ✅ prevents giant placeholder */
            height: auto;
            object-fit: contain;         /* keep your design intact */
          }}
          .kb-media::after {{
            content: "";
            position:absolute;
            left:0; right:0; bottom:0;
            height: 60px;
            background: linear-gradient(to bottom,
              rgba(243,244,246,0.0),
              rgba(243,244,246,0.85),
              rgba(243,244,246,1.0)
            );
          }}
          .kb-media-label {{
            text-align:center;
            margin-top: -44px;          /* ✅ pulls label closer */
            padding-bottom: 8px;
            color: rgba(49, 51, 63, 0.62);
            font-weight: 500;
          }}

          /* Section headings spacing */
          .kb-section {{
            margin-top: 0.35rem;
            margin-bottom: 0.15rem;
          }}
        </style>

        <div class="kb-header">
          {"<img class='kb-logo' src='data:image/png;base64," + logo_b64 + "' />" if logo_b64 else ""}
          <div class="kb-text">
            <div class="kb-title">{TITLE}</div>
            <div class="kb-caption">{CAPTION}</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


render_header()

if last_updated:
    st.caption(f"Last updated: {format_ts_et(last_updated)}")

st.write("")

# Search stays top-of-page
search_query = st.text_input(
    "Search (title / location / source)",
    value="",
    placeholder="Try: king george, port royal, landsearch, 20 acres…",
)

# Defaults from criteria
default_max_price = int(criteria.get("max_price", 600000) or 600000)
default_min_acres = float(criteria.get("min_acres", 11.0) or 11.0)
default_max_acres = float(criteria.get("max_acres", 50.0) or 50.0)

# Status helpers
STATUS_EMOJI = {
    "available": "🟢 Available",
    "under_contract": "🟡 Under contract",
    "pending": "⏳ Pending",
    "sold": "🛑 Sold",
    "unknown": "⚪ Status unknown",
}


def get_status(it: Dict[str, Any]) -> str:
    s = (it.get("status") or "unknown").strip().lower()
    return s if s in STATUS_EMOJI else "unknown"


def is_unavailable(status: str) -> bool:
    return status in {"under_contract", "pending", "sold"}


# Match logic
def meets_acres(it: Dict[str, Any], min_a: float, max_a: float) -> bool:
    acres = it.get("acres")
    if acres is None:
        return False
    try:
        return min_a <= float(acres) <= max_a
    except Exception:
        return False


def meets_price(it: Dict[str, Any], max_p: int) -> bool:
    price = it.get("price")
    if price is None:
        return False
    try:
        return int(price) <= int(max_p)
    except Exception:
        return False


def is_top_match(it: Dict[str, Any], min_a: float, max_a: float, max_p: int) -> bool:
    status = get_status(it)
    if is_unavailable(status):
        return False
    return meets_acres(it, min_a, max_a) and meets_price(it, max_p)


def is_possible_match(it: Dict[str, Any], min_a: float, max_a: float) -> bool:
    status = get_status(it)
    if is_unavailable(status):
        return False
    if not meets_acres(it, min_a, max_a):
        return False
    return it.get("price") is None


def is_former_top_match(it: Dict[str, Any]) -> bool:
    status = get_status(it)
    if not is_unavailable(status):
        return False
    return bool(it.get("ever_top_match", False))


def searchable_text(it: Dict[str, Any]) -> str:
    return " ".join(
        [
            str(it.get("title", "")),
            str(it.get("source", "")),
            str(it.get("url", "")),
        ]
    ).lower()


def parse_dt(it: Dict[str, Any]) -> str:
    return it.get("found_utc") or ""


def is_new(it: Dict[str, Any]) -> bool:
    try:
        return bool(it.get("found_utc")) and bool(last_updated) and it.get("found_utc") == last_updated
    except Exception:
        return False


# ---------- Filters ----------
with st.expander("Filters", expanded=False):
    max_price = st.number_input("Max price (Top match)", min_value=0, value=default_max_price, step=10000)
    min_acres = st.number_input("Min acres", min_value=0.0, value=default_min_acres, step=1.0)
    max_acres = st.number_input("Max acres", min_value=0.0, value=default_max_acres, step=1.0)

    show_top_matches_only = st.toggle("✨ Top matches only", value=True)
    show_possible_matches = st.toggle("🧩 Include possible matches", value=False)
    show_former_top_matches = st.toggle("⭐ Former top matches", value=False)

    show_new_only = st.toggle("🆕 New only", value=False)
    sort_newest = st.toggle("Newest first", value=True)
    show_n = st.slider("Show how many", min_value=5, max_value=200, value=50, step=5)


# ---------- Apply search + new filter first ----------
pool = items[:]

if search_query.strip():
    q = search_query.strip().lower()
    pool = [it for it in pool if q in searchable_text(it)]

if show_new_only:
    pool = [it for it in pool if is_new(it)]

# ---------- Build buckets (sections) ----------
top_bucket = [it for it in pool if is_top_match(it, min_acres, max_acres, max_price)]
possible_bucket = [it for it in pool if is_possible_match(it, min_acres, max_acres)]
former_bucket = [it for it in pool if is_former_top_match(it)]

# "Other" excludes anything that is already in the special buckets
special_urls = {it.get("url") for it in (top_bucket + possible_bucket + former_bucket) if it.get("url")}
other_bucket = [it for it in pool if it.get("url") not in special_urls]

# Sorting inside each bucket
def sort_list(lst: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not sort_newest:
        return lst
    return sorted(lst, key=parse_dt, reverse=True)

top_bucket = sort_list(top_bucket)
possible_bucket = sort_list(possible_bucket)
former_bucket = sort_list(former_bucket)
other_bucket = sort_list(other_bucket)

# Apply filter modes
sections: List[tuple[str, List[Dict[str, Any]]]] = []

if show_top_matches_only:
    sections.append(("✨ Top matches", top_bucket))
    if show_possible_matches:
        sections.append(("🧩 Possible matches", possible_bucket))
    # never show former/other in top-only mode
else:
    # normal mode: show top always first (nice UX)
    sections.append(("✨ Top matches", top_bucket))
    if show_possible_matches:
        sections.append(("🧩 Possible matches", possible_bucket))
    if show_former_top_matches:
        sections.append(("⭐ Former top matches", former_bucket))
    sections.append(("🔎 Other listings", other_bucket))

# Combine to compute counts + enforce show_n
flat = []
for _, lst in sections:
    flat.extend(lst)
flat = flat[:show_n]

# Re-slice sections based on show_n limit
remaining = show_n
trimmed_sections: List[tuple[str, List[Dict[str, Any]]]] = []
for title, lst in sections:
    if remaining <= 0:
        break
    chunk = lst[:remaining]
    if chunk:
        trimmed_sections.append((title, chunk))
        remaining -= len(chunk)

# ---------- Details ----------
with st.expander("Details", expanded=False):
    st.caption(f"Criteria: ${max_price:,.0f} max • {min_acres:g}–{max_acres:g} acres")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("All found", f"{len(items)}")
    c2.metric("Top matches", f"{len(top_bucket)}")
    c3.metric("Possible matches", f"{len(possible_bucket)}")
    c4.metric("New", f"{len([it for it in items if is_new(it)])}")

    st.caption(f"Former top matches detected: {len(former_bucket)} (toggle in Filters)")

st.divider()

# ---------- Card rendering ----------
def placeholder_block():
    if PREVIEW_PATH.exists():
        b64 = base64.b64encode(PREVIEW_PATH.read_bytes()).decode("utf-8")
        st.markdown(
            f"""
            <div class="kb-media">
              <img src="data:image/png;base64,{b64}" alt="Preview not available" />
            </div>
            <div class="kb-media-label">Preview not available</div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            """
            <div style="width:100%; height:220px; background:#f2f2f2; border-radius:16px;
                        display:flex; align-items:center; justify-content:center; color:#777;
                        font-weight:600;">
                Preview not available
            </div>
            """,
            unsafe_allow_html=True,
        )


def listing_card(it: Dict[str, Any]):
    title = it.get("title") or f"{it.get('source', 'Land')} listing"
    url = it.get("url") or ""
    source = it.get("source") or ""
    price = it.get("price")
    acres = it.get("acres")
    thumb = it.get("thumbnail")

    status = get_status(it)
    status_badge = STATUS_EMOJI.get(status, STATUS_EMOJI["unknown"])

    top = is_top_match(it, min_acres, max_acres, max_price)
    possible = is_possible_match(it, min_acres, max_acres)
    former = is_former_top_match(it)
    new_flag = is_new(it)

    badges = []
    if top:
        badges.append("✨️ Top match")
    elif possible:
        badges.append("🧩 Possible match")
    elif former:
        badges.append("⭐ Former top match")
    else:
        badges.append("🔎 Found")

    if new_flag:
        badges.append("🆕 NEW")

    badges.append(status_badge)

    with st.container(border=True):
        if thumb:
            st.image(thumb, use_container_width=True)
        else:
            placeholder_block()

        st.subheader(title)
        st.caption(f"{' • '.join(badges)} • {source}")

        # show found timestamp (helps a LOT when you add more URLs)
        found_label = format_ts_et(it.get("found_utc") or "")
        if found_label:
            st.caption(f"Found: {found_label}")

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


# ---------- Render sections (2-col grid per section) ----------
rendered_any = False
for section_title, lst in trimmed_sections:
    st.markdown(f"<div class='kb-section'></div>", unsafe_allow_html=True)
    st.subheader(f"{section_title} ({len(lst)})")

    cols = st.columns(2)
    for idx, it in enumerate(lst):
        with cols[idx % 2]:
            listing_card(it)

    rendered_any = rendered_any or bool(lst)

if not rendered_any:
    st.info("No listings matched your current search/filters.")