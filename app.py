import json
from pathlib import Path
import streamlit as st

st.set_page_config(page_title="KB’s Land Tracker", page_icon="🗺️", layout="wide")

# ---------- Load data ----------
p = Path("data/listings.json")
if not p.exists():
    st.error("No data yet. Run the scraper first so data/listings.json exists.")
    st.stop()

data = json.loads(p.read_text(encoding="utf-8"))
items = data.get("items", []) or []
criteria = data.get("criteria", {}) or {}

min_acres = float(criteria.get("min_acres", 0))
max_acres = float(criteria.get("max_acres", 999999))
max_price = int(criteria.get("max_price", 999999999))
last_updated = data.get("last_updated_utc", "")

# ---------- Helpers ----------
def money(x):
    return "—" if x is None else f"${int(x):,}"

def acres(x):
    return "—" if x is None else f"{float(x):g}"

def safe_text(s):
    return (s or "").strip()

def pill(label, kind="good"):
    if kind == "good":
        bg, bd, fg = "#E8F5E9", "#81C784", "#1B5E20"
    else:
        bg, bd, fg = "#F3F4F6", "#D1D5DB", "#111827"
    st.markdown(
        f"""
        <span style="
          display:inline-block;
          padding:4px 10px;
          border-radius:999px;
          background:{bg};
          border:1px solid {bd};
          color:{fg};
          font-weight:700;
          font-size:12px;">
          {label}
        </span>
        """,
        unsafe_allow_html=True
    )

# ---------- Header ----------
st.markdown(
    """
    <div style="padding: 18px 18px 10px 18px; border-radius: 18px; border: 1px solid rgba(0,0,0,0.08); background: white;">
      <div style="font-size: 34px; font-weight: 800; line-height: 1.1;">KB’s Land Tracker</div>
      <div style="opacity: 0.72; font-size: 15px; margin-top: 6px;">What’s meant for you is already in motion.</div>
    </div>
    """,
    unsafe_allow_html=True
)

st.write("")

# ---------- KPIs ----------
strict_matches = [i for i in items if i.get("matches")]
all_found = len(items)

k1, k2, k3, k4 = st.columns(4)
k1.metric("Strict matches", len(strict_matches))
k2.metric("All found", all_found)
k3.metric("Max price", f"${max_price:,.0f}")
k4.metric("Acres range", f"{min_acres:g}–{max_acres:g}")

st.caption(f"Last updated (UTC): {last_updated}")
st.divider()

# ---------- Filters ----------
left, mid, right = st.columns([2, 2, 2])

with left:
    show_only_matches = st.toggle("Show only strict matches", value=True)
with mid:
    max_price_ui = st.number_input("Max price filter", min_value=0, value=int(max_price), step=5000)
with right:
    query = st.text_input("Search")

# Filter + sort
filtered = items[:]
if show_only_matches:
    filtered = [i for i in filtered if i.get("matches")]

filtered = [i for i in filtered if (i.get("price") is None or int(i.get("price")) <= int(max_price_ui))]

if query.strip():
    q = query.strip().lower()
    filtered = [
        i for i in filtered
        if q in safe_text(i.get("title")).lower()
        or q in safe_text(i.get("source")).lower()
        or q in safe_text(i.get("url")).lower()
    ]

# Sort by price (unknown last)
filtered.sort(key=lambda x: (x.get("price") is None, x.get("price") or 10**18))

st.write("")
st.subheader("Listings")

if not filtered:
    st.info("No listings match your current filters.")
    st.stop()

# ---------- Cards with thumbnails ----------
for i in filtered[:40]:
    title = safe_text(i.get("title")) or "Land listing"
    url = i.get("url") or ""
    src = safe_text(i.get("source")) or "Unknown source"
    img = i.get("image_url")

    with st.container(border=True):
        c1, c2 = st.columns([1.2, 2.8])

        with c1:
            if img:
                st.image(img, use_container_width=True)
            else:
                st.markdown(
                    """
                    <div style="height: 140px; border-radius: 14px; border: 1px dashed rgba(0,0,0,0.15);
                                display:flex; align-items:center; justify-content:center; opacity:0.65;">
                      no photo
                    </div>
                    """,
                    unsafe_allow_html=True
                )

        with c2:
            top = st.columns([4, 1])
            with top[0]:
                st.markdown(f"### {title}")
                st.caption(src)
            with top[1]:
                if i.get("matches"):
                    pill("MATCH", "good")
                else:
                    pill("OTHER", "neutral")

            m1, m2, m3 = st.columns(3)
            m1.markdown(f"**Price:** {money(i.get('price'))}")
            m2.markdown(f"**Acres:** {acres(i.get('acres'))}")
            m3.markdown(f"[Open ↗]({url})" if url else "—")