import base64
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import streamlit as st
from data_access import load_data

# ---------- Paths ----------
LOGO_PATH = Path("assets/kblogo.png")
PREVIEW_PATH = Path("assets/previewkb.png")  # branded placeholder

# ---------- Page config ----------
st.set_page_config(
    page_title="KB’s Land Tracker",
    page_icon=str(LOGO_PATH) if LOGO_PATH.exists() else "🗺️",
    layout="centered",
)

TITLE = "KB’s Land Tracker"
CAPTION = "What’s meant for you is already in motion."

# ---------- Load data ----------
data = load_data() or {}
items: List[Dict[str, Any]] = data.get("items", []) or []
criteria = data.get("criteria", {}) or {}
last_updated = data.get("last_updated_utc")


# ---------- Time formatting (Eastern) ----------
def format_last_updated_et(ts: str) -> str:
    if not ts:
        return "—"
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        from zoneinfo import ZoneInfo
        dt_et = dt.astimezone(ZoneInfo("America/New_York"))
        return dt_et.strftime("%b %d, %Y • %I:%M %p ET")
    except Exception:
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            return dt.strftime("%b %d, %Y • %I:%M %p")
        except Exception:
            return str(ts)


# ============================================================
# ✅ UI: Header + Last Updated tile + Muted Pill badges
# ============================================================
st.markdown(
    """
<style>
.kb-header { display:flex; align-items:center; gap:18px; flex-wrap:wrap; margin-top:0.25rem; margin-bottom:0.35rem; }
.kb-logo { width:140px; height:140px; flex:0 0 auto; border-radius:22px; object-fit:contain; }
.kb-text { flex:1 1 auto; min-width:240px; }
.kb-title { font-size:clamp(2.0rem,4vw,2.8rem); font-weight:950; line-height:1.05; margin:0; color:#0f172a; }
.kb-caption { font-size:clamp(1.05rem,2.2vw,1.25rem); color:rgba(15,23,42,0.62); margin-top:10px; font-weight:750; }

.kb-tile { padding:14px 14px; border-radius:14px; background:rgba(240,242,246,0.65); border:1px solid rgba(0,0,0,0.07); }
.kb-tile-label { font-size:0.85rem; color:rgba(0,0,0,0.55); margin-bottom:6px; font-weight:600; }
.kb-tile-value { font-size:1.65rem; font-weight:850; line-height:1.05; margin:0; color:#0f172a; }

.kb-filter-box { padding:14px; border-radius:12px; background:rgba(240,242,246,0.55); border:1px solid rgba(0,0,0,0.08); margin:12px 0; }
.kb-filter-title { font-size:0.85rem; font-weight:800; letter-spacing:0.4px; color:rgba(15,23,42,0.65); margin-bottom:10px; text-transform:uppercase; }

.kb-badges { display:flex; flex-wrap:wrap; gap:8px; margin:6px 0 8px 0; }
.kb-pill {
  display:inline-flex; align-items:center; padding:4px 10px; border-radius:999px;
  font-size:0.72rem; font-weight:850; letter-spacing:0.35px;
  border:1px solid rgba(0,0,0,0.10); background:rgba(240,242,246,0.80);
  color:rgba(15,23,42,0.90); text-transform:uppercase; white-space:nowrap;
}

.kb-pill--top { background:rgba(16,185,129,0.16); border-color:rgba(16,185,129,0.35); }
.kb-pill--new { background:rgba(59,130,246,0.16); border-color:rgba(59,130,246,0.35); }
.kb-pill--possible { background:rgba(245,158,11,0.16); border-color:rgba(245,158,11,0.35); }
.kb-pill--found { background:rgba(148,163,184,0.22); border-color:rgba(148,163,184,0.40); }

.kb-pill--available { background:rgba(34,197,94,0.16); border-color:rgba(34,197,94,0.35); }
.kb-pill--under_contract { background:rgba(234,179,8,0.16); border-color:rgba(234,179,8,0.35); }
.kb-pill--pending { background:rgba(249,115,22,0.16); border-color:rgba(249,115,22,0.35); }
.kb-pill--sold { background:rgba(239,68,68,0.14); border-color:rgba(239,68,68,0.32); }
.kb-pill--unknown { background:rgba(100,116,139,0.14); border-color:rgba(100,116,139,0.30); }

.kb-ph { width:100%; height:220px; border-radius:16px; overflow:hidden; position:relative; display:flex; align-items:center; justify-content:center; }
.kb-ph img { width:100%; height:100%; object-fit:cover; display:block; }
.kb-ph::after { content:""; position:absolute; inset:0; background:linear-gradient(to bottom, rgba(255,255,255,0.0) 0%, rgba(255,255,255,0.30) 45%, rgba(255,255,255,0.70) 100%); }
.kb-ph-label { position:absolute; z-index:2; text-align:center; font-weight:800; letter-spacing:0.2px; color:rgba(15,23,42,0.78);
  padding:10px 14px; border-radius:999px; background:rgba(255,255,255,0.65); backdrop-filter:blur(6px); border:1px solid rgba(15,23,42,0.08); }
</style>
""",
    unsafe_allow_html=True,
)


def render_header() -> None:
    logo_b64 = base64.b64encode(LOGO_PATH.read_bytes()).decode("utf-8") if LOGO_PATH.exists() else ""
    st.markdown(
        f"""
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


def render_tile(label: str, value: str) -> None:
    st.markdown(
        f"""
        <div class="kb-tile">
          <div class="kb-tile-label">{label}</div>
          <div class="kb-tile-value">{value}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def pill(text: str, variant: str) -> str:
    return f"<span class='kb-pill kb-pill--{variant}'>{text}</span>"


render_header()
render_tile("Last updated", format_last_updated_et(last_updated))
st.write("")

# ✅ Search stays top-of-page
search_query = st.text_input(
    "Search (title / location / source)",
    value="",
    placeholder="Try: king george, port royal, landwatch, 20 acres…",
)

# ---------- Defaults ----------
default_max_price = int(criteria.get("max_price", 600000) or 600000)
default_min_acres = float(criteria.get("min_acres", 10.0) or 10.0)
default_max_acres = float(criteria.get("max_acres", 50.0) or 50.0)

# ---------- Status helpers ----------
STATUS_LABEL = {
    "available": "AVAILABLE",
    "under_contract": "UNDER CONTRACT",
    "pending": "PENDING",
    "sold": "SOLD",
    "unknown": "STATUS UNKNOWN",
}


def get_status(it: Dict[str, Any]) -> str:
    s = (it.get("status") or "unknown").strip().lower()
    return s if s in STATUS_LABEL else "unknown"


def is_unavailable(status: str) -> bool:
    return status in {"under_contract", "pending", "sold", "off market", "removed", "unavailable"}


# ---------- Match logic ----------
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


def is_missing_price(it: Dict[str, Any]) -> bool:
    p = it.get("price")
    if p is None:
        return True
    if isinstance(p, str) and p.strip() == "":
        return True
    if p == 0:
        return True
    if isinstance(p, str):
        s = p.strip().lower()
        if s in {"n/a", "na", "none", "unknown", "call", "call for price", "contact"}:
            return True
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
    return is_missing_price(it)


def searchable_text(it: Dict[str, Any]) -> str:
    return " ".join(
        [
            str(it.get("title", "")),
            str(it.get("county", "")),
            str(it.get("state", "")),
            str(it.get("location", "")),
            str(it.get("city", "")),
            str(it.get("region", "")),
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


# ---------- Normalizers ----------
def norm_opt(x: Optional[str]) -> str:
    return (x or "").strip()


def title_case_keep(s: str) -> str:
    s = (s or "").strip()
    return s[:1].upper() + s[1:] if s else ""


# ---------- NEW: Robust location extraction ----------
def get_state(it: Dict[str, Any]) -> str:
    # Try common keys your scraper might use
    candidates = [
        it.get("state"),
        it.get("state_code"),
        it.get("state_abbr"),
        it.get("state_name"),
        it.get("region_state"),
    ]
    for c in candidates:
        c = norm_opt(str(c) if c is not None else "")
        if c:
            return c.upper() if len(c) == 2 else title_case_keep(c)

    # Fallback: parse from location/title like "... , Virginia" or "... , VA"
    loc = norm_opt(it.get("location") or it.get("title") or "")
    if "," in loc:
        tail = loc.split(",")[-1].strip()
        if len(tail) == 2:
            return tail.upper()
        if tail:
            return title_case_keep(tail)
    return ""


def get_county(it: Dict[str, Any]) -> str:
    candidates = [
        it.get("county"),
        it.get("county_name"),
        it.get("region_county"),
    ]
    for c in candidates:
        c = norm_opt(str(c) if c is not None else "")
        if c:
            # normalize "King George County" -> "King George"
            c2 = c.replace(" County", "").replace(" county", "").strip()
            return title_case_keep(c2)

    # Some scrapers store city instead of county
    city = norm_opt(it.get("city") or "")
    if city:
        return title_case_keep(city)

    return ""


# ---------- Keep only real property pages ----------
def is_property_listing(it: Dict[str, Any]) -> bool:
    url = (it.get("url") or "").strip().lower()
    if not url:
        return False

    if "landsearch.com" in url:
        parts = url.rstrip("/").split("/")
        return ("/properties/" in url) and parts[-1].isdigit()

    if "landwatch.com" in url:
        return "/property/" in url

    return True


items = [it for it in items if is_property_listing(it)]

# Build options from robust getters
states = sorted({get_state(it) for it in items if get_state(it)})
counties = sorted({get_county(it) for it in items if get_county(it)})

# ============================================================
# ✅ Filters (toggles first + boxed Criteria + boxed Location)
# ============================================================
with st.expander("Filters", expanded=False):
    st.markdown("<div class='kb-filter-box'><div class='kb-filter-title'>Quick filters</div>", unsafe_allow_html=True)
    show_top_only = st.toggle("Show top matches", value=True)
    show_possible = st.toggle("Include possible", value=False)
    show_new_only = st.toggle("New only", value=False)
    sort_newest = st.toggle("Newest first", value=True)
    show_n = st.slider("Show how many", min_value=5, max_value=200, value=50, step=5)
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div class='kb-filter-box'><div class='kb-filter-title'>Criteria</div>", unsafe_allow_html=True)
    max_price = st.number_input("Max price (Top match)", min_value=0, value=default_max_price, step=10000)
    min_acres = st.number_input("Min acres", min_value=0.0, value=default_min_acres, step=1.0)
    max_acres = st.number_input("Max acres", min_value=0.0, value=default_max_acres, step=1.0)
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div class='kb-filter-box'><div class='kb-filter-title'>Location</div>", unsafe_allow_html=True)
    selected_states = st.multiselect("State", options=states, default=states)
    selected_counties = st.multiselect("County (or City)", options=counties, default=counties)
    st.markdown("</div>", unsafe_allow_html=True)


def passes_location(it: Dict[str, Any]) -> bool:
    st_ = get_state(it)
    co_ = get_county(it)

    # If we have no location options at all, do not filter
    if not states and not counties:
        return True

    if selected_states and st_ and st_ not in selected_states:
        return False

    if selected_counties and co_ and co_ not in selected_counties:
        return False

    # If missing location fields, keep visible (don’t accidentally hide stuff)
    return True


loc_items = [it for it in items if passes_location(it)]

top_matches_all = [it for it in loc_items if is_top_match(it, min_acres, max_acres, max_price)]
possible_all = [it for it in loc_items if is_possible_match(it, min_acres, max_acres)]
new_all = [it for it in loc_items if is_new(it)]

with st.expander("Details", expanded=False):
    st.caption(f"Criteria: ${max_price:,.0f} max • {min_acres:g}–{max_acres:g} acres")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("All listings", f"{len(loc_items)}")
    c2.metric("Top matches", f"{len(top_matches_all)}")
    c3.metric("Possible", f"{len(possible_all)}")
    c4.metric("New", f"{len(new_all)}")

    # ✅ quick debug so you can confirm what keys exist
    with st.expander("Location debug (first 5)", expanded=False):
        for it in loc_items[:5]:
            st.write(
                {
                    "title": it.get("title"),
                    "state_raw": it.get("state"),
                    "county_raw": it.get("county"),
                    "location_raw": it.get("location"),
                    "city_raw": it.get("city"),
                    "derived_state": get_state(it),
                    "derived_county": get_county(it),
                }
            )

st.divider()

# ---------- Apply filters ----------
filtered = loc_items[:]

if search_query.strip():
    q = search_query.strip().lower()
    filtered = [it for it in filtered if q in searchable_text(it)]

if show_new_only:
    filtered = [it for it in filtered if is_new(it)]

if show_top_only:
    allowed: List[Dict[str, Any]] = []
    for it in filtered:
        if is_top_match(it, min_acres, max_acres, max_price):
            allowed.append(it)
        elif show_possible and is_possible_match(it, min_acres, max_acres):
            allowed.append(it)
    filtered = allowed
else:
    if not show_possible:
        filtered = [it for it in filtered if not is_possible_match(it, min_acres, max_acres)]


def sort_key(it: Dict[str, Any]):
    if is_top_match(it, min_acres, max_acres, max_price):
        tier = 3
    elif is_possible_match(it, min_acres, max_acres):
        tier = 2
    else:
        tier = 1
    return (tier, parse_dt(it))


if sort_newest:
    filtered = sorted(filtered, key=sort_key, reverse=True)

filtered = filtered[:show_n]


# ---------- Placeholder renderer ----------
def render_placeholder():
    if PREVIEW_PATH.exists():
        ph_b64 = base64.b64encode(PREVIEW_PATH.read_bytes()).decode("utf-8")
        st.markdown(
            f"""
            <div class="kb-ph">
              <img src="data:image/png;base64,{ph_b64}" />
              <div class="kb-ph-label">Preview not available</div>
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


# ---------- Listing cards ----------
def listing_card(it: Dict[str, Any]):
    title = it.get("title") or f"{it.get('source', 'Land')} listing"
    url = it.get("url") or ""
    source = it.get("source") or ""
    price = it.get("price")
    acres = it.get("acres")
    thumb = it.get("thumbnail")

    st_ = get_state(it)
    co_ = get_county(it)

    status = get_status(it)
    top = is_top_match(it, min_acres, max_acres, max_price)
    possible = is_possible_match(it, min_acres, max_acres)
    new_flag = is_new(it)

    pills: List[str] = []
    if new_flag:
        pills.append(pill("NEW", "new"))

    if top:
        pills.append(pill("TOP MATCH", "top"))
    elif possible:
        pills.append(pill("POSSIBLE", "possible"))
    else:
        pills.append(pill("FOUND", "found"))

    status_variant = {
        "available": "available",
        "under_contract": "under_contract",
        "pending": "pending",
        "sold": "sold",
        "unknown": "unknown",
    }.get(status, "unknown")

    pills.append(pill(STATUS_LABEL.get(status, "STATUS UNKNOWN"), status_variant))

    loc_line = " • ".join([x for x in [co_, st_] if x])

    with st.container(border=True):
        if thumb:
            st.image(thumb, use_container_width=True)
        else:
            render_placeholder()

        st.subheader(title)
        st.markdown(f"<div class='kb-badges'>{''.join(pills)}</div>", unsafe_allow_html=True)

        meta_bits = []
        if loc_line:
            meta_bits.append(loc_line)
        if source:
            meta_bits.append(source)
        if meta_bits:
            st.caption(" • ".join(meta_bits))

        if price is None:
            st.write("**Price:** —")
        else:
            try:
                st.write(f"**Price:** ${int(price):,}")
            except Exception:
                st.write(f"**Price:** {price}")

        if acres is None:
            st.write("**Acres:** —")
        else:
            try:
                st.write(f"**Acres:** {float(acres):g}")
            except Exception:
                st.write(f"**Acres:** {acres}")

        if url:
            st.link_button("Open listing ↗", url, use_container_width=True)


cols = st.columns(2)
for idx, it in enumerate(filtered):
    with cols[idx % 2]:
        listing_card(it)

if not filtered:
    st.info("No listings matched your current search/filters.")
