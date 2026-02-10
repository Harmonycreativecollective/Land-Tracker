import base64
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import streamlit as st
from data_access import load_data
from scraper import run_update


# ---------- Paths ----------
LOGO_PATH = Path("assets/kblogo.png")
PREVIEW_PATH = Path("assets/previewkb.png")  # branded placeholder

# ---------- Page config ----------
st.set_page_config(
    page_title="KB’s Land Tracker – Properties",
    page_icon=str(LOGO_PATH) if LOGO_PATH.exists() else "🗺️",
    layout="wide",
)

# ---------- Header copy ----------
DESCRIPTION = "Quietly tracks land listings so you don’t have to."
CAPTION = "What’s meant for you is already in motion."

# ---------- Manual Refresh ----------
if st.button("🔄 Check for new listings", use_container_width=True):
    with st.spinner("Updating listings…"):
        st.cache_data.clear()
        run_update()
        st.success("Updated just now ✨")
        st.rerun()

# ---------- Load data ----------
data = load_data() or {}
items: List[Dict[str, Any]] = data.get("items", []) or []
criteria = data.get("criteria", {}) or {}
last_updated = data.get("last_updated_utc")


# ---------- Time formatting (Eastern) ----------
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


# ============================================================
# ✅ Styling (match dashboard)
# ============================================================

st.markdown(
    """
<style>
/* --- Header (match dashboard option B) --- */
.kb-header {
  display:flex;
  align-items:center;
  gap:18px;
  flex-wrap: wrap;
  margin-top: 0.25rem;
  margin-bottom: 0.35rem;
}
.kb-logo {
  width:140px;
  height:140px;
  flex: 0 0 auto;
  border-radius: 22px;
  object-fit: contain;
}
.kb-text {
  flex: 1 1 auto;
  min-width: 240px;
}
.kb-description {
  font-size: 0.95rem;
  font-style: italic;
  color: rgba(15, 23, 42, 0.55);
  margin: 0;
}
.kb-caption {
  font-size: clamp(1.05rem, 2.2vw, 1.25rem);
  color: rgba(15, 23, 42, 0.62);
  margin-top: 10px;
  font-weight: 750;
}

/* --- Full-width tile card --- */
.kb-tile {
  padding: 14px 14px;
  border-radius: 14px;
  background: rgba(240, 242, 246, 0.65);
  border: 1px solid rgba(0,0,0,0.07);
}
.kb-tile-label {
  font-size: 0.85rem;
  color: rgba(0,0,0,0.55);
  margin-bottom: 6px;
  font-weight: 600;
}
.kb-tile-value {
  font-size: 1.65rem;
  font-weight: 850;
  line-height: 1.05;
  margin: 0;
  color: #0f172a;
}

/* --- Muted pill badges --- */
.kb-badges {
  display:flex;
  flex-wrap: wrap;
  gap: 8px;
  margin: 6px 0 8px 0;
}
.kb-pill {
  display:inline-flex;
  align-items:center;
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 0.72rem;
  font-weight: 850;
  letter-spacing: 0.35px;
  border: 1px solid rgba(0,0,0,0.10);
  background: rgba(240, 242, 246, 0.80);
  color: rgba(15, 23, 42, 0.90);
  text-transform: uppercase;
  white-space: nowrap;
}

/* variants (muted) */
.kb-pill--top       { background: rgba(16, 185, 129, 0.16); border-color: rgba(16, 185, 129, 0.35); }
.kb-pill--new       { background: rgba(59, 130, 246, 0.16); border-color: rgba(59, 130, 246, 0.35); }
.kb-pill--possible  { background: rgba(245, 158, 11, 0.16); border-color: rgba(245, 158, 11, 0.35); }
.kb-pill--found     { background: rgba(148, 163, 184, 0.22); border-color: rgba(148, 163, 184, 0.40); }

.kb-pill--available      { background: rgba(34, 197, 94, 0.16); border-color: rgba(34, 197, 94, 0.35); }
.kb-pill--under_contract { background: rgba(234, 179, 8, 0.16);  border-color: rgba(234, 179, 8, 0.35); }
.kb-pill--pending        { background: rgba(249, 115, 22, 0.16); border-color: rgba(249, 115, 22, 0.35); }
.kb-pill--sold           { background: rgba(239, 68, 68, 0.14);  border-color: rgba(239, 68, 68, 0.32); }
.kb-pill--off_market     { background: rgba(100, 116, 139, 0.14); border-color: rgba(100, 116, 139, 0.30); }
.kb-pill--unknown        { background: rgba(100, 116, 139, 0.14); border-color: rgba(100, 116, 139, 0.30); }

/* Placeholder */
.kb-ph {
  width:100%;
  height:220px;
  border-radius:16px;
  overflow:hidden;
  position:relative;
  display:flex;
  align-items:center;
  justify-content:center;
}
.kb-ph img {
  width:100%;
  height:100%;
  object-fit:cover;
  display:block;
}
.kb-ph::after {
  content:"";
  position:absolute;
  inset:0;
  background: linear-gradient(
    to bottom,
    rgba(255,255,255,0.0) 0%,
    rgba(255,255,255,0.30) 45%,
    rgba(255,255,255,0.70) 100%
  );
}
.kb-ph-label {
  position:absolute;
  z-index:2;
  text-align:center;
  font-weight:800;
  letter-spacing:0.2px;
  color: rgba(15, 23, 42, 0.78);
  padding: 10px 14px;
  border-radius: 999px;
  background: rgba(255,255,255,0.65);
  backdrop-filter: blur(6px);
  border: 1px solid rgba(15,23,42,0.08);
}
</style>
""",
    unsafe_allow_html=True,
)


# ============================================================
# UI helpers
# ============================================================

def render_header() -> None:
    logo_b64 = base64.b64encode(LOGO_PATH.read_bytes()).decode("utf-8") if LOGO_PATH.exists() else ""
    st.markdown(
        f"""
        <div class="kb-header">
          {"<img class='kb-logo' src='data:image/png;base64," + logo_b64 + "' />" if logo_b64 else ""}
          <div class="kb-text">
            <div class="kb-description">{DESCRIPTION}</div>
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


# ============================================================
# Header + Last updated
# ============================================================

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


# ============================================================
# STATUS NORMALIZATION
# ============================================================

STATUS_LABEL = {
    "available": "AVAILABLE",
    "under_contract": "UNDER CONTRACT",
    "pending": "PENDING",
    "sold": "SOLD",
    "contingent": "CONTINGENT",
    "off_market": "OFF MARKET",
    "unknown": "STATUS UNKNOWN",
}


def get_status(it: Dict[str, Any]) -> str:
    s = str(it.get("status") or "").strip().lower()
    s = s.replace("-", " ").replace("_", " ")
    s = re.sub(r"\s+", " ", s).strip()

    if not s:
        return "unknown"

    if "sold" in s:
        return "sold"
    if "pending" in s:
        return "pending"
    if "contingent" in s:
        return "contingent"
    if "under contract" in s or "active under contract" in s or s == "contract" or " contract" in s:
        return "under_contract"
    if "off market" in s or "removed" in s or "unavailable" in s:
        return "off_market"
    if "available" in s or "active" in s:
        return "available"

    return "unknown"


def meets_acres(it: Dict[str, Any], min_a: float, max_a: float) -> bool:
    acres = it.get("acres")
    if acres is None:
        return False
    try:
        return float(min_a) <= float(acres) <= float(max_a)
    except Exception:
        return False


def meets_price(it: Dict[str, Any], max_p: int) -> bool:
    price = it.get("price")
    if price is None or price == "":
        return False
    try:
        return float(price) <= float(max_p)
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


def is_new(it: Dict[str, Any]) -> bool:
    try:
        return bool(it.get("found_utc")) and bool(last_updated) and it.get("found_utc") == last_updated
    except Exception:
        return False


# ✅ MATCH RULES: only AVAILABLE can be Top/Possible
def is_top_match(it: Dict[str, Any], min_a: float, max_a: float, max_p: int) -> bool:
    if get_status(it) != "available":
        return False
    return meets_acres(it, min_a, max_a) and meets_price(it, max_p)


def is_possible_match(it: Dict[str, Any], min_a: float, max_a: float) -> bool:
    if get_status(it) != "available":
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
            str(it.get("derived_county", "")),
            str(it.get("derived_state", "")),
            str(it.get("source", "")),
            str(it.get("url", "")),
        ]
    ).lower()


def parse_dt(it: Dict[str, Any]) -> str:
    return it.get("found_utc") or ""


# ============================================================
# Lease removal + property page validation
# ============================================================

LEASE_RE = re.compile(
    r"\b(lease|leasing|rental|rent|for lease|land for lease|for rent|/mo|per month|tenant)\b",
    re.IGNORECASE,
)


def is_lease_listing(it: Dict[str, Any]) -> bool:
    title = str(it.get("title") or "")
    url = str(it.get("url") or "")
    source = str(it.get("source") or "")
    combined = " ".join([title, url, source])
    return bool(LEASE_RE.search(combined))


def is_property_listing(it: Dict[str, Any]) -> bool:
    url = (it.get("url") or "").strip().lower()
    if not url:
        return False

    # HARD REMOVE: leases
    if is_lease_listing(it):
        return False

    # LandSearch property pages
    if "landsearch.com" in url:
        parts = url.rstrip("/").split("/")
        return ("/properties/" in url) and parts[-1].isdigit()

    # LandWatch property pages
    if "landwatch.com" in url:
        return "/property/" in url

    # Unknown sources: keep (future-proof)
    return True


# Apply property filter (removes leases too)
items = [it for it in items if is_property_listing(it)]


# ============================================================
# Location helpers (use derived_* first)
# ============================================================

def norm_opt(x: Optional[str]) -> str:
    return (x or "").strip()


def get_state(it: Dict[str, Any]) -> str:
    return norm_opt(it.get("derived_state")) or norm_opt(it.get("state")) or norm_opt(it.get("state_raw"))


def get_county(it: Dict[str, Any]) -> str:
    c = norm_opt(it.get("derived_county")) or norm_opt(it.get("county")) or norm_opt(it.get("county_raw"))
    if c.lower() in {"", "unknown", "n/a", "na", "none"}:
        return ""
    return c


states = sorted({get_state(it) for it in items if get_state(it)})
counties = sorted({get_county(it) for it in items if get_county(it)})


# ============================================================
# Filters UI
# ============================================================

with st.expander("Filters", expanded=False):
    show_top_only = st.toggle("Show top matches", value=True)
    show_possible = st.toggle("Include possible", value=False)
    show_new_only = st.toggle("New only", value=False)
    sort_newest = st.toggle("Newest first", value=True)
    show_n = st.slider("Show how many", min_value=5, max_value=200, value=50, step=5)

    st.write("")

    max_price = st.number_input("Max price (Top match)", min_value=0, value=default_max_price, step=10000)
    min_acres = st.number_input("Min acres", min_value=0.0, value=default_min_acres, step=1.0)
    max_acres = st.number_input("Max acres", min_value=0.0, value=default_max_acres, step=1.0)

    with st.expander("Location", expanded=False):
        selected_states = st.multiselect("State", options=states, default=states)
        selected_counties = st.multiselect("County", options=counties, default=counties)

    show_debug = st.toggle("Show debug", value=False)


def passes_location(it: Dict[str, Any]) -> bool:
    st_ = get_state(it)
    co_ = get_county(it)

    if selected_states and st_ and st_ not in selected_states:
        return False
    if selected_counties and co_ and co_ not in selected_counties:
        return False
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
    c3.metric("Possible matches", f"{len(possible_all)}")
    c4.metric("New", f"{len(new_all)}")

    if show_debug:
        st.markdown("**Debug (first 8 items):**")
        st.json(loc_items[:8])

st.divider()


# ============================================================
# Apply filters
# ============================================================

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


# ============================================================
# Placeholder renderer
# ============================================================

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


# ============================================================
# Listing cards
# ============================================================

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

    status_variant = status if status in {"available", "under_contract", "pending", "sold", "off_market"} else "unknown"
    pills.append(pill(STATUS_LABEL.get(status, "STATUS UNKNOWN"), status_variant))

    loc_line = " • ".join([x for x in [co_, st_] if x])

    with st.container(border=True):
        if thumb:
            st.image(thumb, use_container_width=True)
        else:
            render_placeholder()

        st.subheader(title)
        st.markdown(f"<div class='kb-badges'>{''.join(pills)}</div>", unsafe_allow_html=True)

        meta_bits: List[str] = []
        if loc_line:
            meta_bits.append(loc_line)
        if source:
            meta_bits.append(source)
        if meta_bits:
            st.caption(" • ".join(meta_bits))

        if price is None or price == "":
            st.write("**Price:** —")
        else:
            try:
                st.write(f"**Price:** ${int(float(price)):,}")
            except Exception:
                st.write(f"**Price:** {price}")

        if acres is None or acres == "":
            st.write("**Acres:** —")
        else:
            try:
                st.write(f"**Acres:** {float(acres):g}")
            except Exception:
                st.write(f"**Acres:** {acres}")

        if url:
            st.link_button("Open listing ↗", url, use_container_width=True)


# Grid (2 columns)
cols = st.columns(2)
for idx, it in enumerate(filtered):
    with cols[idx % 2]:
        listing_card(it)

if not filtered:
    st.info("No listings matched your current search/filters.")
