import base64
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import streamlit as st
from data_access import (
    add_favorite,
    get_app_settings,
    get_favorite_listing_ids,
    get_listings,
    get_system_state,
    remove_favorite,
)

LOGO_PATH = Path("assets/kblogo.png")
PREVIEW_PATH = Path("assets/previewkb.png")

st.set_page_config(
    page_title="KB's Land Tracker - Favorites",
    page_icon=str(LOGO_PATH) if LOGO_PATH.exists() else "❤️",
    layout="wide",
)

items: List[Dict[str, Any]] = get_listings() or []
favorite_ids = get_favorite_listing_ids()
app_settings = get_app_settings() or {}
criteria = (app_settings.get("criteria") if isinstance(app_settings, dict) else {}) or {}
state = get_system_state()
last_updated = state.get("last_updated_utc")

MIN_ACRES = 10.0
MAX_ACRES = 50.0
MAX_PRICE = 600_000
default_max_price = float(criteria.get("max_price", MAX_PRICE) or MAX_PRICE)
default_min_acres = float(criteria.get("min_acres", MIN_ACRES) or MIN_ACRES)
default_max_acres = float(criteria.get("max_acres", MAX_ACRES) or MAX_ACRES)


def get_status(it: Dict[str, Any]) -> str:
    s = str(it.get("status") or "").strip().lower().replace("-", " ").replace("_", " ")
    s = re.sub(r"\s+", " ", s).strip()
    if not s:
        return "unknown"
    if "sold" in s:
        return "sold"
    if "pending" in s:
        return "pending"
    if "under contract" in s or "contingent" in s or s == "contract" or " contract" in s:
        return "under_contract"
    if "off market" in s or "removed" in s or "unavailable" in s or re.search(r"\binactive\b", s):
        return "off_market"
    if re.search(r"\bavailable\b", s) or re.search(r"\bactive\b", s):
        return "available"
    return "unknown"


def is_top_match(it: Dict[str, Any]) -> bool:
    if it.get("is_active") is not True:
        return False
    if get_status(it) != "available":
        return False
    try:
        acres = float(it.get("acres"))
        price = float(it.get("price"))
        return default_min_acres <= acres <= default_max_acres and price <= default_max_price
    except Exception:
        return False


def is_new(it: Dict[str, Any]) -> bool:
    try:
        return bool(it.get("found_utc")) and bool(last_updated) and it.get("found_utc") == last_updated
    except Exception:
        return False


def format_last_updated_et(ts: Any) -> str:
    if not ts:
        return "—"
    try:
        dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        from zoneinfo import ZoneInfo

        dt_et = dt.astimezone(ZoneInfo("America/New_York"))
        return dt_et.strftime("%b %d, %Y • %I:%M %p ET")
    except Exception:
        return str(ts)


def render_placeholder() -> None:
    if PREVIEW_PATH.exists():
        ph_b64 = base64.b64encode(PREVIEW_PATH.read_bytes()).decode("utf-8")
        st.markdown(
            f"""
            <div style="width:100%;height:220px;border-radius:16px;overflow:hidden;position:relative;">
              <img src="data:image/png;base64,{ph_b64}" style="width:100%;height:100%;object-fit:cover;display:block;" />
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            """
            <div style="width:100%; height:220px; background:#f2f2f2; border-radius:16px;
                        display:flex; align-items:center; justify-content:center; color:#777;
                        font-weight:700;">
                Preview not available
            </div>
            """,
            unsafe_allow_html=True,
        )


def pill(text: str, variant: str) -> str:
    return f"<span class='kb-pill kb-pill--{variant}'>{text}</span>"


st.markdown(
    """
<style>
.kb-pill { display:inline-flex; align-items:center; padding:4px 10px; border-radius:999px; font-size:.72rem; font-weight:850; border:1px solid rgba(0,0,0,.10); text-transform:uppercase; }
.kb-pill--top       { background: rgba(16, 185, 129, 0.16); border-color: rgba(16, 185, 129, 0.35); }
.kb-pill--new       { background: rgba(59, 130, 246, 0.16); border-color: rgba(59, 130, 246, 0.35); }
.kb-pill--favorite  { background: rgba(244, 63, 94, 0.16); border-color: rgba(244, 63, 94, 0.35); }
.kb-pill--status    { background: rgba(100, 116, 139, 0.14); border-color: rgba(100, 116, 139, 0.30); }
.kb-badges { display:flex; flex-wrap:wrap; gap:8px; margin: 8px 0 8px 0; }
</style>
""",
    unsafe_allow_html=True,
)

st.title("Favorites")
st.caption(f"Last updated: {format_last_updated_et(last_updated)}")

search_query = st.text_input("Search favorites", value="", placeholder="Search title/source/url...")
show_top_only = st.toggle("Show top matches only", value=False)
sort_newest = st.toggle("Newest first", value=True)

favorite_items = [it for it in items if str(it.get("listing_id") or it.get("url") or "") in favorite_ids]
if search_query.strip():
    q = search_query.strip().lower()
    favorite_items = [
        it
        for it in favorite_items
        if q in " ".join(
            [
                str(it.get("title", "")),
                str(it.get("source", "")),
                str(it.get("url", "")),
                str(it.get("derived_county", "")),
                str(it.get("derived_state", "")),
            ]
        ).lower()
    ]

if show_top_only:
    favorite_items = [it for it in favorite_items if is_top_match(it)]

if sort_newest:
    favorite_items = sorted(favorite_items, key=lambda it: it.get("found_utc") or "", reverse=True)

st.metric("Saved listings", len(favorite_items))
if st.button("Return to Dashboard", width="stretch"):
    st.switch_page("dashboard.py")
if st.button("Return to Properties", width="stretch"):
    st.switch_page("pages/2_properties.py")

cols = st.columns(2)
for idx, it in enumerate(favorite_items):
    listing_id = str(it.get("listing_id") or it.get("url") or "")
    is_fav = listing_id in favorite_ids
    title = it.get("title") or f"{it.get('source', 'Land')} listing"
    url = it.get("url") or ""
    source = it.get("source") or ""
    status = get_status(it)
    top = is_top_match(it)
    new_flag = is_new(it)
    with cols[idx % 2]:
        with st.container(border=True):
            thumb = it.get("thumbnail")
            if thumb:
                st.image(thumb, width="stretch")
            else:
                render_placeholder()
            st.subheader(title)
            pills: List[str] = []
            if top:
                pills.append(pill("TOP MATCH", "top"))
            if new_flag:
                pills.append(pill("NEW", "new"))
            if is_fav:
                pills.append(pill("FAVORITE", "favorite"))
            pills.append(pill(status.replace("_", " ").upper(), "status"))
            st.markdown(f"<div class='kb-badges'>{''.join(pills)}</div>", unsafe_allow_html=True)
            st.caption(" • ".join([x for x in [str(it.get("derived_county") or ""), str(it.get("derived_state") or ""), source] if x]))
            try:
                st.write(f"**Price:** ${int(float(it.get('price'))):,}" if it.get("price") not in (None, "") else "**Price:** —")
            except Exception:
                st.write(f"**Price:** {it.get('price')}")
            try:
                st.write(f"**Acres:** {float(it.get('acres')):g}" if it.get("acres") not in (None, "") else "**Acres:** —")
            except Exception:
                st.write(f"**Acres:** {it.get('acres')}")
            if url:
                st.link_button("Open listing ↗", url, width="stretch")
            fav_label = "♥ Saved" if is_fav else "♡ Save"
            if st.button(fav_label, key=f"favs_page_{listing_id}", width="stretch"):
                if is_fav:
                    ok, err = remove_favorite(listing_id)
                else:
                    ok, err = add_favorite(listing_id)
                if not ok:
                    st.error(err)
                else:
                    st.rerun()

if not favorite_items:
    st.info("No favorites yet. Save listings from Dashboard or Properties.")
