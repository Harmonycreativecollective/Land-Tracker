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
    get_favorite_records,
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
favorite_records = get_favorite_records()
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
    if "auction" in s:
        return "auction"
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


def duplicate_fingerprint(it: Dict[str, Any]) -> tuple:
    t = re.sub(r"[^a-z0-9 ]+", " ", str(it.get("title") or "").lower())
    t = re.sub(r"\s+", " ", t).strip()[:90]
    try:
        p = int(float(it.get("price"))) if it.get("price") not in (None, "") else None
    except Exception:
        p = None
    try:
        a = round(float(it.get("acres")), 2) if it.get("acres") not in (None, "") else None
    except Exception:
        a = None
    return (
        t,
        p,
        a,
        str(it.get("derived_county") or "").lower(),
        str(it.get("derived_state") or "").lower(),
    )


def group_duplicate_items(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    grouped: Dict[tuple, Dict[str, Any]] = {}
    for it in rows:
        key = duplicate_fingerprint(it)
        src = str(it.get("source") or "Unknown").strip() or "Unknown"
        if key not in grouped:
            cp = dict(it)
            cp["_group_sources"] = {src}
            grouped[key] = cp
            continue
        existing = grouped[key]
        existing["_group_sources"].add(src)
        if not existing.get("thumbnail") and it.get("thumbnail"):
            for k, v in it.items():
                existing[k] = v
            existing["_group_sources"].add(src)
    out: List[Dict[str, Any]] = []
    for it in grouped.values():
        it["_group_sources"] = sorted(list(it.get("_group_sources", [])))
        out.append(it)
    return out


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


def render_active_chips(chips: List[str]) -> None:
    if not chips:
        return
    html = "".join([pill(c, "status") for c in chips])
    st.markdown(f"<div class='kb-badges'>{html}</div>", unsafe_allow_html=True)


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

STATUS_FILTER_OPTIONS = ["available", "under_contract", "pending", "sold", "off_market", "auction", "unknown"]
if "fav_search_query" not in st.session_state:
    st.session_state["fav_search_query"] = ""
if "fav_status_filter" not in st.session_state:
    st.session_state["fav_status_filter"] = STATUS_FILTER_OPTIONS[:]
if "fav_sort_mode" not in st.session_state:
    st.session_state["fav_sort_mode"] = "Newest"

if st.button("Reset Filters", key="fav_reset_filters", width="stretch"):
    st.session_state["fav_search_query"] = ""
    st.session_state["fav_show_top_only"] = False
    st.session_state["fav_hide_unknown"] = False
    st.session_state["fav_group_duplicates"] = False
    st.session_state["fav_sort_mode"] = "Newest"
    st.session_state["fav_status_filter"] = STATUS_FILTER_OPTIONS[:]
    st.rerun()

search_query = st.text_input("Search favorites", value="", placeholder="Search title/source/url...", key="fav_search_query")
show_top_only = st.toggle("Show top matches only", value=False, key="fav_show_top_only")
hide_unknown = st.toggle("Hide unknown status", value=False, key="fav_hide_unknown")
group_duplicates = st.toggle("Group duplicates", value=False, key="fav_group_duplicates")
sort_mode = st.selectbox(
    "Sort",
    options=["Newest", "Price Low to High", "Acres High to Low", "Top Matches First"],
    key="fav_sort_mode",
)
status_filter = st.multiselect(
    "Statuses",
    options=STATUS_FILTER_OPTIONS,
    default=STATUS_FILTER_OPTIONS,
    key="fav_status_filter",
)

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
if status_filter:
    favorite_items = [it for it in favorite_items if get_status(it) in set(status_filter)]
if hide_unknown:
    favorite_items = [it for it in favorite_items if get_status(it) != "unknown"]
if group_duplicates:
    favorite_items = group_duplicate_items(favorite_items)

def _num(val: Any, fallback: float) -> float:
    try:
        if val in (None, ""):
            return fallback
        return float(val)
    except Exception:
        return fallback

if sort_mode == "Newest":
    favorite_items = sorted(favorite_items, key=lambda it: it.get("found_utc") or "", reverse=True)
elif sort_mode == "Price Low to High":
    favorite_items = sorted(
        favorite_items,
        key=lambda it: _num(it.get("price"), float("inf")),
    )
elif sort_mode == "Acres High to Low":
    favorite_items = sorted(
        favorite_items,
        key=lambda it: _num(it.get("acres"), float("-inf")),
        reverse=True,
    )
else:
    favorite_items = sorted(
        favorite_items,
        key=lambda it: (1 if is_top_match(it) else 0, it.get("found_utc") or ""),
        reverse=True,
    )

chips: List[str] = [f"Saved: {len(favorite_items)}", f"Sort: {sort_mode}"]
if show_top_only:
    chips.append("Top Matches")
if hide_unknown:
    chips.append("Hide Unknown")
if group_duplicates:
    chips.append("Grouped")
if search_query.strip():
    chips.append(f"Search: {search_query.strip()}")
if status_filter and len(status_filter) < len(STATUS_FILTER_OPTIONS):
    chips.append("Status Filter")
render_active_chips(chips)
st.caption(
    f"Summary: {len([it for it in favorite_items if get_status(it) == 'available'])} available, "
    f"{len([it for it in favorite_items if is_top_match(it)])} top matches"
)

st.metric("Saved listings", len(favorite_items))
if st.button("Return to Dashboard", width="stretch"):
    st.switch_page("dashboard.py")
if st.button("Return to Properties", width="stretch"):
    st.switch_page("pages/2_properties.py")

cols = st.columns(2)
for idx, it in enumerate(favorite_items):
    listing_id = str(it.get("listing_id") or it.get("url") or "")
    is_fav = listing_id in favorite_ids
    favorite_created_at = favorite_records.get(listing_id)
    title = it.get("title") or f"{it.get('source', 'Land')} listing"
    url = it.get("url") or ""
    source = it.get("source") or ""
    grouped_sources = it.get("_group_sources") if isinstance(it.get("_group_sources"), list) else None
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
            if is_fav:
                st.caption("♥ Saved")
            pills: List[str] = []
            if top:
                pills.append(pill("TOP MATCH", "top"))
            if new_flag:
                pills.append(pill("NEW", "new"))
            if is_fav:
                pills.append(pill("FAVORITE", "favorite"))
            pills.append(pill(status.replace("_", " ").upper(), "status"))
            st.markdown(f"<div class='kb-badges'>{''.join(pills)}</div>", unsafe_allow_html=True)
            src_text = " / ".join(grouped_sources) if grouped_sources else source
            st.caption(" • ".join([x for x in [str(it.get("derived_county") or ""), str(it.get("derived_state") or ""), src_text] if x]))
            if favorite_created_at and is_fav:
                st.caption(f"Saved on {format_last_updated_et(favorite_created_at)}")
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
                    st.toast("Saved to favorites" if not is_fav else "Removed from favorites")
                    st.rerun()

if not favorite_items:
    st.info("No favorites yet. Save listings from Dashboard or Properties.")
