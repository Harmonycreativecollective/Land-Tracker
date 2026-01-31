import base64
import json
from datetime import datetime
from pathlib import Path

import streamlit as st

DATA_PATH = Path("data/listings.json")
LOGO_PATH = Path("assets/kblogo.png")

TITLE = "KB’s Land Tracker"
CAPTION = "What’s meant for you is already in motion."

st.set_page_config(
    page_title=TITLE,
    page_icon=str(LOGO_PATH) if LOGO_PATH.exists() else "🗺️",
    layout="wide",
)

# ---------- Load data ----------
def load_data():
    if not DATA_PATH.exists():
        return {"items": [], "criteria": {}, "last_updated_utc": None}
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

data = load_data()
items = data.get("items", [])
criteria = data.get("criteria", {}) or {}
last_updated = data.get("last_updated_utc")


# ---------- Helpers ----------
def b64_image(path: Path) -> str:
    if not path.exists():
        return ""
    return base64.b64encode(path.read_bytes()).decode("utf-8")


def format_last_updated(ts: str) -> str:
    if not ts:
        return ""
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return dt.strftime("%b %d, %Y • %I:%M %p UTC")
    except Exception:
        return ts


def parse_dt(it):
    # Found date from scraper (ISO string)
    return it.get("found_utc") or ""


def searchable_text(it):
    return " ".join(
        [
            str(it.get("title", "")),
            str(it.get("source", "")),
            str(it.get("url", "")),
            str(it.get("location", "")),
        ]
    ).lower()


# Top match logic (uses current filter values; criteria are just for display)
def is_top_match(it, min_acres, max_acres, max_price):
    price = it.get("price")
    acres = it.get("acres")
    if price is None or acres is None:
        return False
    try:
        return (min_acres <= float(acres) <= max_acres) and (int(price) <= int(max_price))
    except Exception:
        return False


def is_new(it, new_days=7):
    """NEW = first seen within last N days based on found_utc."""
    ts = it.get("found_utc")
    if not ts:
        return False
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        now = datetime.utcnow().replace(tzinfo=dt.tzinfo)
        return (now - dt).days < new_days
    except Exception:
        return False


# ---------- Header (FIXED: wrap + autoscale, no clipping) ----------
logo_b64 = b64_image(LOGO_PATH)

st.markdown(
    """
    <style>
      /* Give the main container a tiny bit more breathing room on mobile */
      @media (max-width: 600px) {
        .block-container { padding-top: 1.2rem; }
      }
    </style>
    """,
    unsafe_allow_html=True,
)

header_html = f"""
<div style="
  display:flex;
  align-items:center;
  gap:18px;
  margin-top:6px;
  margin-bottom:6px;
">
  <div style="
    flex: 0 0 auto;
    width: clamp(88px, 18vw, 130px);
  ">
    {"<img src='data:image/png;base64," + logo_b64 + "' style='width:100%; height:auto; display:block;' />" if logo_b64 else ""}
  </div>

  <div style="
    flex: 1 1 auto;
    min-width: 0;            /* IMPORTANT: allows text to wrap instead of overflow */
  ">
    <div style="
      font-size: clamp(2.0rem, 6.5vw, 3.2rem);
      font-weight: 900;
      line-height: 1.05;
      margin: 0;
      color: #0f172a;
      white-space: normal;   /* allow wrap */
      overflow-wrap: anywhere;