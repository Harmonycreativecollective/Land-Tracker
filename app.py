import base64
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import streamlit as st

# Your project import (keep this exactly as you have it)
from data_access import load_data


# ---------- Paths ----------
LOGO_PATH = Path("assets/kblogo.png")

# ---------- Page config ----------
st.set_page_config(
    page_title="Dashboard – KB’s Land Tracker",
    page_icon=str(LOGO_PATH) if LOGO_PATH.exists() else "🗺️",
    layout="centered",
)

TITLE = "KB’s Land Tracker"
CAPTION = "What’s meant for you is already in motion."


# ---------- Helpers ----------
def _parse_dt_utc(dt_str: Optional[str]) -> Optional[datetime]:
    """
    Parse an ISO-ish datetime string. Returns an aware datetime in UTC if possible.
    Accepts:
      - "2026-02-07T18:38:00Z"
      - "2026-02-07T18:38:00+00:00"
      - "2026-02-07 18:38:00"
    """
    if not dt_str:
        return None

    s = str(dt_str).strip()
    try:
        # Normalize "Z"
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        # If naive, assume UTC (safer than local guessing)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def _format_eastern(dt_utc: Optional[datetime]) -> str:
    """
    Format as Eastern Time without requiring extra deps.
    Streamlit runs in an environment where zoneinfo usually exists (py3.9+).
    If it doesn't, we fall back to UTC text.
    """
    if not dt_utc:
        return "—"

    try:
        from zoneinfo import ZoneInfo  # py3.9+
        et = dt_utc.astimezone(ZoneInfo("America/New_York"))
        return et.strftime("%b %d, %Y • %I:%M %p ET")
    except Exception:
        # Fallback: show UTC
        return dt_utc.strftime("%b %d, %Y • %I:%M %p UTC")


def _is_top_match(item: Dict[str, Any]) -> bool:
    # Try several possible flags/fields so we don't break your schema
    if item.get("is_top_match") is True:
        return True
    if str(item.get("match_tier", "")).lower() in {"top", "top_match", "top match"}:
        return True
    if str(item.get("match", "")).lower() in {"top", "top_match", "top match"}:
        return True
    # Score-based fallback if you store a score
    score = item.get("score") or item.get("match_score") or item.get("rank_score")
    try:
        return float(score) >= 0.80
    except Exception:
        return False


def _is_possible(item: Dict[str, Any]) -> bool:
    if item.get("is_possible") is True:
        return True
    if str(item.get("match_tier", "")).lower() in {"possible", "maybe"}:
        return True
    if str(item.get("match", "")).lower() in {"possible", "maybe"}:
        return True
    return False


def _is_new(item: Dict[str, Any]) -> bool:
    if item.get("is_new") is True:
        return True
    if item.get("new") is True:
        return True
    if item.get("is_new_since_last") is True:
        return True
    # Some scrapers store a tag
    if str(item.get("status", "")).lower() == "new":
        return True
    return False


def _safe_text(x: Any, fallback: str = "—") -> str:
    if x is None:
        return fallback
    s = str(x).strip()
    return s if s else fallback


def _best_title(item: Dict[str, Any]) -> str:
    return _safe_text(
        item.get("title")
        or item.get("name")
        or item.get("headline")
        or item.get("site_name")
        or item.get("source")
        or "Listing"
    )


def _best_subtitle(item: Dict[str, Any]) -> str:
    acres = item.get("acres") or item.get("lot_acres") or item.get("acreage")
    price = item.get("price") or item.get("list_price")

    parts = []
    if acres is not None:
        try:
            parts.append(f"{float(acres):g} acres")
        except Exception:
            parts.append(f"{acres} acres")

    if price is not None:
        try:
            parts.append(f"${int(float(price)):,}")
        except Exception:
            parts.append(f"${price}")

    # If you store location
    loc = item.get("location") or item.get("county") or item.get("city")
    if loc:
        parts.append(str(loc))

    return " • ".join(parts) if parts else _safe_text(item.get("subtitle") or item.get("summary") or "")


def _best_url(item: Dict[str, Any]) -> Optional[str]:
    return item.get("url") or item.get("link") or item.get("listing_url")


def _sort_key(item: Dict[str, Any]) -> Tuple[int, float]:
    """
    Sorting: Top matches first, then possibles, then by score desc if available.
    """
    top = 1 if _is_top_match(item) else 0
    poss = 1 if _is_possible(item) else 0
    score = item.get("score") or item.get("match_score") or item.get("rank_score") or 0
    try:
        score_f = float(score)
    except Exception:
        score_f = 0.0
    # Desc: top > possible > score
    return (top * 10 + poss * 5, score_f)


# ---------- Load data ----------
data = load_data() or {}
items: List[Dict[str, Any]] = data.get("items", []) or []
last_updated_raw = data.get("last_updated_utc")
last_updated_dt_utc = _parse_dt_utc(last_updated_raw)

# Derived counts
all_found = len(items)
top_items = [it for it in items if _is_top_match(it)]
possible_items = [it for it in items if _is_possible(it)]
new_items = [it for it in items if _is_new(it)]

top_count = len(top_items)
possible_count = len(possible_items)
new_count = len(new_items)

# Sorted view for quick display
items_sorted = sorted(items, key=_sort_key, reverse=True)


# ---------- Styling ----------
st.markdown(
    """
<style>
/* Make the overall header area feel bigger */
.kb-header {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-top: 6px;
  margin-bottom: 14px;
}

.kb-title {
  font-size: 2.0rem;
  font-weight: 700;
  line-height: 1.1;
  margin: 0;
}

.kb-caption {
  font-size: 0.98rem;
  color: rgba(0,0,0,0.55);
  margin-top: 4px;
}

/* “Tile” / card UI */
.tile {
  padding: 14px 14px;
  border-radius: 14px;
  background: rgba(240, 242, 246, 0.65);
  border: 1px solid rgba(0,0,0,0.06);
}

.tile:hover {
  box-shadow: 0 4px 14px rgba(0,0,0,0.08);
  transform: translateY(-1px);
}

.tile-label {
  font-size: 0.85rem;
  color: rgba(0,0,0,0.55);
  margin-bottom: 6px;
}

.tile-value {
  font-size: 1.55rem;
  font-weight: 700;
  margin: 0;
}

.tile-sub {
  font-size: 0.92rem;
  color: rgba(0,0,0,0.55);
  margin-top: 6px;
}

/* Small divider spacing */
.section-gap {
  margin-top: 18px;
}
</style>
""",
    unsafe_allow_html=True,
)


# ---------- Header ----------
logo_col, title_col = st.columns([1, 8], vertical_alignment="center")

with logo_col:
    if LOGO_PATH.exists():
        st.image(str(LOGO_PATH), width=62)
    else:
        st.write("🗺️")

with title_col:
    st.markdown(
        f"""
<div class="kb-header">
  <div>
    <div class="kb-title">{TITLE}</div>
    <div class="kb-caption">{CAPTION}</div>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

# ---------- Last Updated tile ----------
formatted_last_updated = _format_eastern(last_updated_dt_utc)
st.markdown(
    f"""
<div class="tile">
  <div class="tile-label">Last updated</div>
  <div class="tile-value" style="font-size:1.05rem; font-weight:600;">{formatted_last_updated}</div>
</div>
""",
    unsafe_allow_html=True,
)

st.markdown('<div class="section-gap"></div>', unsafe_allow_html=True)

# ---------- Stat tiles (boxed) ----------
c1, c2, c3, c4 = st.columns(4, gap="small")

with c1:
    st.markdown(
        f"""
<div class="tile">
  <div class="tile-label">All found</div>
  <div class="tile-value">{all_found}</div>
</div>
""",
        unsafe_allow_html=True,
    )

with c2:
    st.markdown(
        f"""
<div class="tile">
  <div class="tile-label">Top matches</div>
  <div class="tile-value">{top_count}</div>
</div>
""",
        unsafe_allow_html=True,
    )

with c3:
    st.markdown(
        f"""
<div class="tile">
  <div class="tile-label">New</div>
  <div class="tile-value">{new_count}</div>
</div>
""",
        unsafe_allow_html=True,
    )

with c4:
    st.markdown(
        f"""
<div class="tile">
  <div class="tile-label">Possible</div>
  <div class="tile-value">{possible_count}</div>
</div>
""",
        unsafe_allow_html=True,
    )

st.markdown('<div class="section-gap"></div>', unsafe_allow_html=True)

# ---------- Primary action ----------
# Keep this simple; you can wire it to a separate page later if you add multipage nav.
st.markdown(
    """
<div style="margin-top: 6px; margin-bottom: 10px;">
</div>
""",
    unsafe_allow_html=True,
)

view_all = st.button("View all properties →", use_container_width=True)

if view_all:
    st.session_state["show_all"] = True

show_all = st.session_state.get("show_all", False)


# ---------- Top matches quick view ----------
st.subheader("Top matches (quick view)")

quick_list = [it for it in items_sorted if _is_top_match(it)]
if not quick_list:
    # If your matching logic is still evolving, we don't want the page to look empty.
    st.info("No top matches yet — once matching rules are set, they’ll show here.")
else:
    for it in quick_list[:10]:
        title = _best_title(it)
        subtitle = _best_subtitle(it)
        url = _best_url(it)

        st.markdown(
            f"""
<div class="tile" style="margin-bottom: 10px;">
  <div style="font-weight: 650; margin-bottom: 4px;">{title}</div>
  <div class="tile-sub">{subtitle}</div>
</div>
""",
            unsafe_allow_html=True,
        )
        if url:
            st.link_button("Open listing ↗", url, use_container_width=True)

# ---------- Optional: Show all listings (toggle via button) ----------
if show_all:
    st.markdown('<div class="section-gap"></div>', unsafe_allow_html=True)
    st.subheader("All properties")

    if not items_sorted:
        st.warning("No listings found yet.")
    else:
        # Show as cards to keep mobile-friendly
        for it in items_sorted[:200]:  # safety cap
            title = _best_title(it)
            subtitle = _best_subtitle(it)
            url = _best_url(it)

            # Badge text (non-breaking)
            badges = []
            if _is_top_match(it):
                badges.append("Top match")
            if _is_new(it):
                badges.append("New")
            if _is_possible(it) and not _is_top_match(it):
                badges.append("Possible")

            badge_str = " • ".join(badges) if badges else ""

            st.markdown(
                f"""
<div class="tile" style="margin-bottom: 10px;">
  <div style="display:flex; justify-content:space-between; gap:10px;">
    <div style="font-weight:650;">{title}</div>
    <div style="color: rgba(0,0,0,0.45); font-size:0.85rem;">{badge_str}</div>
  </div>
  <div class="tile-sub">{subtitle}</div>
</div>
""",
                unsafe_allow_html=True,
            )
            if url:
                st.link_button("Open listing ↗", url, use_container_width=True)

