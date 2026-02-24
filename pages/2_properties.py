import base64
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from urllib.parse import urlparse

import streamlit as st
from data_access import get_listings, get_system_state



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
CAPTION = "What's meant for you is already in motion."


# ---------- Load data ----------
items: List[Dict[str, Any]] = get_listings() or []
criteria = {}
state = get_system_state()
last_updated = state.get("last_updated_utc")
last_attempted = state.get("last_attempted_utc")


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
/* --- Header --- */
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


st.info("Updates run automatically every 3 hours. ")

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


def is_new(it: Dict[str, Any]) -> bool:
    try:
        return bool(it.get("found_utc")) and bool(last_updated) and it.get("found_utc") == last_updated
    except Exception:
        return False


# ✅ MATCH RULES: only AVAILABLE can be Top
def is_top_match(it: Dict[str, Any], min_a: float, max_a: float, max_p: int) -> bool:
    if get_status(it) != "available":
        return False
    return meets_acres(it, min_a, max_a) and meets_price(it, max_p)


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

    # LandSearch property pages (they're /properties/<id>)
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
# Location helpers (safe: counties from derived fields only)
# ============================================================

def norm_opt(x: Optional[str]) -> str:
    return (x or "").strip()

STATE_ABBR = {"va": "VA", "md": "MD"}
STATE_WORDS = {"virginia": "VA", "maryland": "MD"}

def get_state_from_text(text: str) -> str:
    t = (text or "").lower()
    for k, v in STATE_WORDS.items():
        if k in t:
            return v
    m = re.search(r"\b(va|md)\b", t)
    return STATE_ABBR.get(m.group(1).lower(), "") if m else ""

def get_state(it: Dict[str, Any]) -> str:
    st_ = norm_opt(it.get("derived_state")) or norm_opt(it.get("state")) or norm_opt(it.get("state_raw"))
    if st_:
        return st_.upper()
    blob = " ".join([norm_opt(it.get("title")), norm_opt(it.get("url"))])
    return get_state_from_text(blob)

def normalize_county(c: str) -> str:
    """
    Normalize county labels WITHOUT turning cities into counties.
    If it's a real county label already, we format it consistently.
    """
    c = norm_opt(c)
    if not c:
        return ""

    low = c.lower()
    if low in {"unknown", "n/a", "na", "none"}:
        return ""

    # strip trailing ", VA" etc
    c = re.sub(r",\s*(VA|MD)\b", "", c, flags=re.IGNORECASE).strip()

    # If it already contains County/Co, normalize it; otherwise leave it alone
    has_county_word = bool(re.search(r"\b(county|co\.?)\b", c, flags=re.IGNORECASE))

    if has_county_word:
        c = re.sub(r"\bco\.?\b", "County", c, flags=re.IGNORECASE)
        c = re.sub(r"\bcounty\b", "County", c, flags=re.IGNORECASE)
        c = re.sub(r"\s+", " ", c).strip()

    # Title case words except "County"
    parts = c.split()
    parts = [p.capitalize() if p.lower() != "county" else "County" for p in parts]
    return " ".join(parts).strip()

def get_county(it: Dict[str, Any]) -> str:
    """
    IMPORTANT:
    Only use derived_county/county fields (which should come from the START_URL context).
    DO NOT infer county from a property URL slug — that’s how we got Middletown County.
    """
    c = norm_opt(it.get("derived_county")) or norm_opt(it.get("county")) or norm_opt(it.get("county_raw"))
    c = normalize_county(c)

    # only accept if it truly looks like a county label
    if c and re.search(r"\bCounty\b", c):
        return c
    return ""

# A separate "place/city" helper for cards only
STREET_STOPWORDS = {
    "rd","road","st","street","ave","avenue","ln","lane","dr","drive","ct","court",
    "blvd","boulevard","hwy","highway","way","pkwy","parkway","cir","circle",
    "trl","trail","pl","place","ter","terrace","sq","square","loop","pike",
    "unit","apt","suite","mount","mt","tabor"
}
DIGIT_RE = re.compile(r"\d")

def titleize_words(words: List[str]) -> str:
    return " ".join(w.capitalize() for w in words if w)

def derive_state_and_place_from_landsearch_url(url: str) -> tuple[str, str]:
    """
    For LandSearch property URLs, derive (state, place/city-ish).
    We ONLY use this for the listing card caption, not for county filters.
    """
    u = norm_opt(url).lower()
    if "landsearch.com" not in u or "/properties/" not in u:
        return ("", "")

    try:
        after = u.split("/properties/")[1].strip("/")
        slug = after.split("/")[0]
        parts = [p for p in slug.split("-") if p]

        st_idx = None
        for i in range(len(parts) - 1, -1, -1):
            if parts[i] in STATE_ABBR:
                st_idx = i
                break
        if st_idx is None:
            return ("", "")

        st = STATE_ABBR[parts[st_idx]]

        place_tokens: List[str] = []
        for j in range(st_idx - 1, -1, -1):
            tok = parts[j]
            if tok.isdigit() or DIGIT_RE.search(tok):
                break
            if tok in STREET_STOPWORDS:
                break
            place_tokens.append(tok)
            if len(place_tokens) >= 3:
                break

        place_tokens = list(reversed(place_tokens))
        place = titleize_words(place_tokens)
        return (st, place)
    except Exception:
        return ("", "")

def get_place_for_card(it: Dict[str, Any]) -> str:
    # if you ever add a city field later, it can go first here
    url = norm_opt(it.get("url"))
    _, place = derive_state_and_place_from_landsearch_url(url)
    return place


# ============================================================
# Filters UI (expander) + Location INSIDE Filters
# ============================================================

# Build state list from items
states = sorted({s for s in (get_state(it) for it in items) if s})

# Build state -> counties map (county labels ONLY, state-scoped)
state_to_counties: Dict[str, Set[str]] = {}
for it in items:
    st_ = get_state(it)
    co_ = get_county(it)
    if not st_ or not co_:
        continue
    state_to_counties.setdefault(st_, set()).add(co_)

state_to_counties_sorted: Dict[str, List[str]] = {k: sorted(list(v)) for k, v in state_to_counties.items()}

with st.expander("Filters", expanded=False):
    show_top_only = st.toggle("Show top matches", value=True)
    show_new_only = st.toggle("New only", value=False)
    sort_newest = st.toggle("Newest first", value=True)
    show_n = st.slider("Show how many", min_value=5, max_value=200, value=50, step=5)

    st.write("")
    max_price = st.number_input("Max price (Top match)", min_value=0, value=default_max_price, step=10000)
    min_acres = st.number_input("Min acres", min_value=0.0, value=default_min_acres, step=1.0)
    max_acres = st.number_input("Max acres", min_value=0.0, value=default_max_acres, step=1.0)

    st.write("")
    st.markdown("**Location**")

    colA, colB = st.columns(2)
    with colA:
        selected_states = st.multiselect(
            "State",
            options=states,
            default=states if states else [],
        )

    # counties limited to selected states
    counties_for_selected_states: List[str] = []
    for st_ in selected_states:
        counties_for_selected_states.extend(state_to_counties_sorted.get(st_, []))
    counties_for_selected_states = sorted(set(counties_for_selected_states))

    with colB:
        selected_counties = st.multiselect(
            "County",
            options=counties_for_selected_states,
            default=counties_for_selected_states,
            disabled=(len(counties_for_selected_states) == 0),
        )

    show_debug = st.toggle("Show debug", value=False)

    if show_debug:
        st.write("### Debug (first 12 items)")
        st.json(
            [
                {
                    "title": it.get("title"),
                    "url": it.get("url"),
                    "derived_state": it.get("derived_state"),
                    "derived_county": it.get("derived_county"),
                    "state_calc": get_state(it),
                    "county_calc": get_county(it),
                    "place_for_card": get_place_for_card(it),
                }
                for it in items[:12]
            ]
        )


def passes_location(it: Dict[str, Any]) -> bool:
    st_ = get_state(it)
    co_ = get_county(it)

    if selected_states and st_ not in selected_states:
        return False

    # If counties are selected (they will be by default if any exist), enforce them
    if selected_counties and co_ not in selected_counties:
        return False

    return True


loc_items = [it for it in items if passes_location(it)]


# ============================================================
# Details (location-scoped)
# ============================================================

available_loc = [it for it in loc_items if get_status(it) == "available"]
top_matches_all = [it for it in loc_items if is_top_match(it, min_acres, max_acres, max_price)]
new_top_matches_all = [it for it in top_matches_all if is_new(it)]

source_counts: Dict[str, int] = {}
for it in loc_items:
    src = (it.get("source") or "Unknown").strip() or "Unknown"
    source_counts[src] = source_counts.get(src, 0) + 1

with st.expander("Details", expanded=False):
    st.caption(f"Criteria: ${max_price:,.0f} max • {min_acres:g}–{max_acres:g} acres")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("All listings", f"{len(loc_items)}")
    c2.metric("Available", f"{len(available_loc)}")
    c3.metric("Top matches", f"{len(top_matches_all)}")
    c4.metric("New top matches", f"{len(new_top_matches_all)}")

    st.write("")
    st.markdown("**Sources**")
    for src, n in sorted(source_counts.items(), key=lambda x: x[1], reverse=True):
        st.caption(f"{src}: {n}")

st.divider()


# ============================================================
# Apply filters (AFTER location scope)
# ============================================================

filtered = loc_items[:]

# Search
if search_query.strip():
    q = search_query.strip().lower()
    filtered = [it for it in filtered if q in searchable_text(it)]

# New only = NEW TOP MATCHES only (to match Dashboard meaning)
if show_new_only:
    filtered = [it for it in filtered if is_new(it) and is_top_match(it, min_acres, max_acres, max_price)]

# Top only
if show_top_only:
    filtered = [it for it in filtered if is_top_match(it, min_acres, max_acres, max_price)]


def sort_key(it: Dict[str, Any]):
    tier = 2 if is_top_match(it, min_acres, max_acres, max_price) else 1
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
    county = get_county(it)          # only real counties
    place = get_place_for_card(it)   # city/place fallback

    status = get_status(it)
    top = is_top_match(it, min_acres, max_acres, max_price)
    new_flag = is_new(it)

    pills: List[str] = []
    if new_flag:
        pills.append(pill("NEW", "new"))

    if top:
        pills.append(pill("TOP MATCH", "top"))
    else:
        pills.append(pill("FOUND", "found"))

    status_variant = status if status in {"available", "under_contract", "pending", "sold", "off_market"} else "unknown"
    pills.append(pill(STATUS_LABEL.get(status, "STATUS UNKNOWN"), status_variant))

    # Card location line: prefer County if we have it, else show place/city
    loc_primary = county or place
    loc_line = " • ".join([x for x in [loc_primary, st_] if x])

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
