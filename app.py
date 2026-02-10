import base64
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import streamlit as st
from data_access import load_data
from scraper import run_update


# ---------- Paths ----------
LOGO_PATH = Path("assets/kblogo.png")

# ---------- Page config ----------
st.set_page_config(
    page_title="Dashboard – KB’s Land Tracker",
    page_icon=str(LOGO_PATH) if LOGO_PATH.exists() else "🗺️",
    layout="wide",
)

# ---------- Header text ----------
# Keep your personal caption, but add a smaller italic description
DESCRIPTION = "A private land listing tracker that monitors acreage and flags qualifying properties."
CAPTION = "What’s meant for you is already in motion."

# ---------- Load data ----------
data = load_data() or {}
items: List[Dict[str, Any]] = data.get("items", []) or []
criteria = data.get("criteria", {}) or {}
last_updated = data.get("last_updated_utc")
last_attempted = data.get("last_attempted_utc")

# ============================================================
# Helpers (MUST exist in app.py)
# ============================================================

def format_last_updated_et(dt_str: Any) -> str:
    """Convert stored UTC ISO -> America/New_York so Dashboard matches Properties."""
    if not dt_str:
        return "—"
    try:
        s = str(dt_str).replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)

        from zoneinfo import ZoneInfo
        dt_et = dt.astimezone(ZoneInfo("America/New_York"))
        return dt_et.strftime("%b %d, %Y • %I:%M %p ET")
    except Exception:
        return str(dt_str)


def meets_acres(it: Dict[str, Any], min_acres: float, max_acres: float) -> bool:
    try:
        a = it.get("acres")
        if a is None:
            return False
        a = float(a)
        return (min_acres is None or a >= float(min_acres)) and (max_acres is None or a <= float(max_acres))
    except Exception:
        return False


def meets_price(it: Dict[str, Any], max_price: float) -> bool:
    try:
        p = it.get("price")
        if p is None or p == "":
            return False
        return float(p) <= float(max_price)
    except Exception:
        return False


# ---------- Status normalization ----------
# NOTE: we *normalize* status strings and then use these normalized values everywhere.
STATUS_VALUES_UNAVAILABLE = {
    "unavailable",
    "sold",
    "pending",
    "off market",
    "removed",
    "under contract",
    "contingent",
    "unknown",
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
    if "under contract" in s or "active under contract" in s or s == "contract" or " contract" in s:
        return "under contract"
    if "contingent" in s:
        return "contingent"
    if "off market" in s or "removed" in s or "unavailable" in s:
        return "off market"
    if "available" in s or "active" in s:
        return "available"

    return "unknown"

# ---------- Defaults from criteria ----------
default_min_acres = float(criteria.get("min_acres", 0) or 0)
default_max_acres = float(criteria.get("max_acres", 10**9) or 10**9)
default_max_price = float(criteria.get("max_price", 10**12) or 10**12)

# ============================================================
# Match logic
# ============================================================

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


def is_top_match(it: Dict[str, Any]) -> bool:
    # ✅ HARD RULE: only AVAILABLE can be a top match
    if get_status(it) != "available":
        return False
    return meets_acres(it, default_min_acres, default_max_acres) and meets_price(it, default_max_price)


def is_possible_match(it: Dict[str, Any]) -> bool:
    # Possible = acres fits, but price missing. Still must be AVAILABLE.
    if get_status(it) != "available":
        return False
    if not meets_acres(it, default_min_acres, default_max_acres):
        return False
    return is_missing_price(it)


def is_new(it: Dict[str, Any]) -> bool:
    try:
        return bool(it.get("found_utc")) and bool(last_updated) and it.get("found_utc") == last_updated
    except Exception:
        return False


top_matches = [it for it in items if is_top_match(it)]
possible_matches = [it for it in items if is_possible_match(it)]
new_items = [it for it in items if is_new(it)]

# ============================================================
# UI / Styling
# ============================================================

st.markdown(
    """
<style>
.kb-tile {
  padding: 14px 14px;
  border-radius: 14px;
  background: rgba(240, 242, 246, 0.65);
  border: 1px solid rgba(0,0,0,0.07);
}
.kb-tile:hover {
  box-shadow: 0 4px 14px rgba(0,0,0,0.08);
  transform: translateY(-1px);
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
.kb-tile-help {
  font-size: 0.82rem;
  color: rgba(0,0,0,0.48);
  margin-top: 8px;
}

/* Muted pills */
.kb-badges { display:flex; flex-wrap:wrap; gap:8px; margin: 8px 0 4px 0; }
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
.kb-pill--top       { background: rgba(16, 185, 129, 0.16); border-color: rgba(16, 185, 129, 0.35); }
.kb-pill--new       { background: rgba(59, 130, 246, 0.16); border-color: rgba(59, 130, 246, 0.35); }
.kb-pill--possible  { background: rgba(245, 158, 11, 0.16); border-color: rgba(245, 158, 11, 0.35); }
.kb-pill--found     { background: rgba(148, 163, 184, 0.22); border-color: rgba(148, 163, 184, 0.40); }
.kb-pill--status    { background: rgba(100, 116, 139, 0.14); border-color: rgba(100, 116, 139, 0.30); }
</style>
""",
    unsafe_allow_html=True,
)

def render_tile(label: str, value: str, help_text: str = "") -> None:
    st.markdown(
        f"""
<div class="kb-tile">
  <div class="kb-tile-label">{label}</div>
  <div class="kb-tile-value">{value}</div>
  {"<div class='kb-tile-help'>" + help_text + "</div>" if help_text else ""}
</div>
""",
        unsafe_allow_html=True,
    )

def pill(text: str, variant: str) -> str:
    return f"<span class='kb-pill kb-pill--{variant}'>{text}</span>"

def render_badges_dashboard(it: Dict[str, Any]) -> None:
    pills: List[str] = []

    if is_new(it):
        pills.append(pill("NEW", "new"))

    if is_top_match(it):
        pills.append(pill("TOP MATCH", "top"))
    elif is_possible_match(it):
        pills.append(pill("POSSIBLE", "possible"))
    else:
        pills.append(pill("FOUND", "found"))

    status_label = get_status(it).upper()
    if status_label == "OFF MARKET":
        status_label = "OFF MARKET"
    pills.append(pill(status_label if status_label else "STATUS UNKNOWN", "status"))

    st.markdown(f"<div class='kb-badges'>{''.join(pills)}</div>", unsafe_allow_html=True)

# ---------- Header ----------
logo_b64 = base64.b64encode(LOGO_PATH.read_bytes()).decode("utf-8") if LOGO_PATH.exists() else ""
st.markdown(
    f"""
    <style>
      .kb-header {{
        display:flex;
        align-items:center;
        gap:18px;
        flex-wrap: wrap;
        margin-top: 0.25rem;
        margin-bottom: 0.35rem;
      }}
      .kb-logo {{
        width:140px;
        height:140px;
        flex: 0 0 auto;
        border-radius: 22px;
        object-fit: contain;
      }}
      .kb-text {{
        flex: 1 1 auto;
        min-width: 240px;
      }}
      .kb-desc {{
        font-size: clamp(0.95rem, 2vw, 1.05rem);
        color: rgba(15, 23, 42, 0.62);
        margin-top: 4px;
        font-weight: 600;
        font-style: italic;
      }}
      .kb-caption {{
        font-size: clamp(1.05rem, 2.2vw, 1.25rem);
        color: rgba(15, 23, 42, 0.62);
        margin-top: 10px;
        font-weight: 750;
      }}
    </style>

    <div class="kb-header">
      {"<img class='kb-logo' src='data:image/png;base64," + logo_b64 + "' />" if logo_b64 else ""}
      <div class="kb-text">
        <div class="kb-desc">{DESCRIPTION}</div>
        <div class="kb-caption">{CAPTION}</div>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---------- Last updated / refresh ----------
if last_attempted and (last_attempted != last_updated):
    render_tile(
        "Last updated",
        f"{format_last_updated_et(last_updated)}",
        f"Refresh attempt: {format_last_updated_et(last_attempted)}",
    )
else:
    render_tile("Last updated", format_last_updated_et(last_updated or last_attempted))

st.write("")

# ---------- Refresh control ----------
if st.button("🔄 Check for new listings", use_container_width=True):
    with st.spinner("Checking for new listings…"):
        st.cache_data.clear()
        run_update()
        st.rerun()
        
# ---------- Tiles ----------
c1, c2 = st.columns(2, gap="small")
c3, c4 = st.columns(2, gap="small")

with c1:
    render_tile("All found", f"{len(items)}", "Total listings loaded")
with c2:
    render_tile("Top matches", f"{len(top_matches)}", "Meets Criteria (Available only)")
with c3:
    render_tile("New", f"{len(new_items)}", "Found in the last run")
with c4:
    render_tile("Possible", f"{len(possible_matches)}", "Missing price (Available only)")

st.write("")

if st.button("View all properties →", use_container_width=True):
    st.switch_page("pages/2_properties.py")

st.divider()

# ---------- Quick Top Matches ----------
st.subheader("Top matches (quick view)")

if not top_matches:
    st.info("No top matches right now. Check Properties for everything found.")
else:
    def key_dt(it: Dict[str, Any]) -> str:
        return it.get("found_utc") or ""

    top_sorted = sorted(top_matches, key=key_dt, reverse=True)[:5]

    for it in top_sorted:
        title = it.get("title") or f"{it.get('source', 'Land')} listing"
        url = it.get("url") or ""
        price = it.get("price")
        acres = it.get("acres")
        thumb = it.get("thumbnail")

        with st.container(border=True):
            if thumb:
                st.image(thumb, use_container_width=True)

            bits = []
            if acres is not None:
                try:
                    bits.append(f"{float(acres):g} acres")
                except Exception:
                    bits.append(f"{acres} acres")
            if price is not None:
                try:
                    bits.append(f"${int(price):,}")
                except Exception:
                    bits.append(str(price))

            st.write(f"**{title}**")
            render_badges_dashboard(it)

            if bits:
                st.caption(" • ".join(bits))
            if url:
                st.link_button("Open listing ↗", url, use_container_width=True)

st.caption("Tip: Use Properties to search, filter, and view all listings.")
