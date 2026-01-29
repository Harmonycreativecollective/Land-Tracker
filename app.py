import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import streamlit as st

# =========================
# Page setup
# =========================
st.set_page_config(
    page_title="KB’s Land Tracker",
    page_icon="🗺️",
    layout="wide",
)

# =========================
# Small UI helpers
# =========================
def safe_int(x) -> Optional[int]:
    try:
        if x is None:
            return None
        return int(float(x))
    except Exception:
        return None

def safe_float(x) -> Optional[float]:
    try:
        if x is None:
            return None
        return float(x)
    except Exception:
        return None

def money(n: Optional[int]) -> str:
    if n is None:
        return "—"
    return f"${n:,.0f}"

def fmt_acres(a: Optional[float]) -> str:
    if a is None:
        return "—"
    # show 1 decimal only when needed
    return f"{a:.1f}".rstrip("0").rstrip(".")

def parse_dt(dt_str: str) -> str:
    # show a friendly timestamp
    try:
        # examples: "2026-01-29T22:08:19.594685+00:00"
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        return dt.strftime("%b %d, %Y • %I:%M %p UTC")
    except Exception:
        return dt_str

def pill(label: str, kind: str = "neutral"):
    # IMPORTANT: renders HTML safely (won’t show code)
    if kind == "match":
        bg, bd, fg = "#E8F5E9", "#81C784", "#1B5E20"
    elif kind == "warn":
        bg, bd, fg = "#FFF7ED", "#FDBA74", "#7C2D12"
    else:
        bg, bd, fg = "#F3F4F6", "#D1D5DB", "#111827"

    st.markdown(
        f"""
        <div style="
          display:inline-block;
          padding:4px 10px;
          border-radius:999px;
          background:{bg};
          border:1px solid {bd};
          color:{fg};
          font-weight:800;
          font-size:12px;
          letter-spacing:.4px;">
          {label}
        </div>
        """,
        unsafe_allow_html=True,
    )

def card(title: str, source: str, price: Optional[int], acres: Optional[float], url: str, is_match: bool):
    with st.container(border=True):
        # header row
        left, right = st.columns([0.75, 0.25], vertical_alignment="center")
        with left:
            st.markdown(f"### {title}")
            st.caption(source)
        with right:
            if is_match:
                pill("MATCH", "match")
            else:
                pill("FOUND", "neutral")

        # stats row
        c1, c2, c3 = st.columns([0.34, 0.33, 0.33])
        c1.metric("Price", money(price))
        c2.metric("Acres", fmt_acres(acres))
        c3.markdown("")
        st.link_button("Open listing ↗", url, use_container_width=True)

# =========================
# Load data
# =========================
DATA_PATH = Path("data/listings.json")

if not DATA_PATH.exists():
    st.error("No data file found at data/listings.json yet. Run the scraper workflow first.")
    st.stop()

with open(DATA_PATH, "r", encoding="utf-8") as f:
    data = json.load(f)

items: List[Dict[str, Any]] = data.get("items", []) or []
criteria: Dict[str, Any] = data.get("criteria", {}) or {}

min_acres = safe_float(criteria.get("min_acres")) or 11.0
max_acres = safe_float(criteria.get("max_acres")) or 50.0
max_price_default = safe_int(criteria.get("max_price")) or 600000

last_updated = data.get("last_updated_utc", "")
last_updated_pretty = parse_dt(last_updated) if last_updated else "—"

# Normalize numeric fields once
normalized: List[Dict[str, Any]] = []
for it in items:
    price = safe_int(it.get("price"))
    acres = safe_float(it.get("acres"))
    normalized.append({
        "title": (it.get("title") or "Land listing").strip(),
        "source": (it.get("source") or "Unknown").strip(),
        "url": it.get("url") or "",
        "price": price,
        "acres": acres,
    })

# =========================
# Header / Branding
# =========================
st.title("KB’s Land Tracker")
st.caption("What’s meant for you is already in motion.")

# =========================
# Controls
# =========================
with st.container(border=True):
    left, mid, right = st.columns([0.35, 0.35, 0.30], vertical_alignment="center")

    with left:
        max_price = st.number_input(
            "Max price (for STRICT matches)",
            min_value=0,
            max_value=10_000_000,
            value=max_price_default,
            step=10_000,
            format="%d",
        )

    with mid:
        q = st.text_input("Search (title/location/source)", value="").strip().lower()

    with right:
        show_n = st.slider("Show how many", min_value=5, max_value=200, value=50, step=5)

# =========================
# Match logic
# =========================
def is_strict_match(price: Optional[int], acres: Optional[float]) -> bool:
    if price is None or acres is None:
        return False
    return (min_acres <= acres <= max_acres) and (price <= max_price)

# Apply search filter (but do NOT delete items for having weird/missing price)
def matches_search(it: Dict[str, Any]) -> bool:
    if not q:
        return True
    blob = f"{it['title']} {it['source']} {it['url']}".lower()
    return q in blob

filtered_all = [it for it in normalized if it["url"] and matches_search(it)]

# Strict matches are what YOU care about (your original “11”)
filtered_strict = [it for it in filtered_all if is_strict_match(it["price"], it["acres"])]

# Sort: strict matches first, then price ascending, then acres desc
def sort_key(it: Dict[str, Any]):
    strict = is_strict_match(it["price"], it["acres"])
    price = it["price"] if it["price"] is not None else 9_999_999_999
    acres = it["acres"] if it["acres"] is not None else 0.0
    return (0 if strict else 1, price, -acres)

filtered_all.sort(key=sort_key)

# =========================
# Top stats
# =========================
s1, s2, s3, s4 = st.columns(4)
s1.metric("All found", len(normalized))
s2.metric("Strict matches", len([it for it in normalized if is_strict_match(it["price"], it["acres"])]))
s3.metric("Max price", money(max_price))
s4.metric("Acres range", f"{fmt_acres(min_acres)}–{fmt_acres(max_acres)}")

st.caption(f"Last updated: {last_updated_pretty}")

st.divider()

# =========================
# Results (cards)
# =========================
if not filtered_all:
    st.info("No listings match your search text. Try clearing the search box.")
    st.stop()

# Show cards
count = 0
for it in filtered_all:
    if count >= show_n:
        break

    strict = is_strict_match(it["price"], it["acres"])

    # If you ONLY want strict ones displayed, flip this to: if not strict: continue
    # Right now it shows ALL, but with MATCH vs FOUND.
    card(
        title=it["title"],
        source=it["source"],
        price=it["price"],
        acres=it["acres"],
        url=it["url"],
        is_match=strict,
    )
    count += 1

st.caption(f"Showing {count} listings • {len(filtered_strict)} strict matches in this view")