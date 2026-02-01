import json
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

# -----------------------------
# Paths / output
# -----------------------------
DATA_PATH = Path("data/listings.json")
DATA_PATH.parent.mkdir(parents=True, exist_ok=True)

# -----------------------------
# Config (LandSearch only)
# Put whatever LandSearch search pages you want in SEED_URLS.
# These can be city pages, county pages, etc.
# -----------------------------
SEED_URLS = [
    # Examples you shared:
    "https://www.landsearch.com/properties/king-george-va-22485/4995042",  # sometimes a property page
    "https://www.landsearch.com/properties/round-hill-road-and-ridge-rd-king-george-va-22485/4011540",

    # Good seed types to add (index/search pages):
    # "https://www.landsearch.com/properties/king-george-county-va",
    # "https://www.landsearch.com/properties/king-george-va",
    # "https://www.landsearch.com/land-for-sale/king-george-va",
]

# If you want to override seeds without editing code:
# export SEED_URLS="https://...;https://..."
ENV_SEEDS = os.getenv("SEED_URLS", "").strip()
if ENV_SEEDS:
    SEED_URLS = [u.strip() for u in ENV_SEEDS.split(";") if u.strip()]

# Your app's default criteria (also written to listings.json)
DEFAULT_CRITERIA = {
    "min_acres": float(os.getenv("MIN_ACRES", "10")),
    "max_acres": float(os.getenv("MAX_ACRES", "50")),
    "max_price": int(os.getenv("MAX_PRICE", "600000")),
}

# -----------------------------
# HTTP setup
# -----------------------------
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
}

TIMEOUT = 25
RETRIES = 3
SLEEP_BETWEEN_REQUESTS = 0.6  # polite + helps avoid blocks

# -----------------------------
# Helpers
# -----------------------------
PROPERTY_ID_RE = re.compile(r"/properties/.+/\d+/?$")

def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def norm_url(url: str) -> str:
    return url.rstrip("/")

def is_landsearch_url(url: str) -> bool:
    try:
        return "landsearch.com" in urlparse(url).netloc.lower()
    except Exception:
        return False

def is_property_listing_url(url: str) -> bool:
    """
    LandSearch property pages are typically:
      https://www.landsearch.com/properties/<slug>/<id>
    """
    url = norm_url(url)
    if not is_landsearch_url(url):
        return False
    path = urlparse(url).path.lower()
    if "/properties/" not in path:
        return False
    # last segment numeric id
    last = path.rstrip("/").split("/")[-1]
    return last.isdigit()

def is_probable_index_page(url: str) -> bool:
    """
    If not a property page, assume it's an index/search page.
    """
    return is_landsearch_url(url) and not is_property_listing_url(url)

def fetch(url: str) -> Tuple[int, str]:
    """
    Returns (status_code, text). Raises final exception only on repeated network errors.
    """
    last_err = None
    for attempt in range(1, RETRIES + 1):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
            return resp.status_code, resp.text
        except Exception as e:
            last_err = e
            print(f"[WARN] network error attempt {attempt}/{RETRIES} for {url}: {e}")
            time.sleep(1.2 * attempt)
    raise RuntimeError(f"Failed fetching {url} after {RETRIES} retries: {last_err}")

def soupify(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")

def safe_int(x: Any) -> Optional[int]:
    try:
        if x is None:
            return None
        if isinstance(x, bool):
            return None
        if isinstance(x, (int, float)):
            return int(x)
        s = str(x)
        s = re.sub(r"[^\d]", "", s)
        return int(s) if s else None
    except Exception:
        return None

def safe_float(x: Any) -> Optional[float]:
    try:
        if x is None:
            return None
        if isinstance(x, bool):
            return None
        if isinstance(x, (int, float)):
            return float(x)
        s = str(x).strip().lower()
        # handle "10.3 acres" etc
        s = s.replace(",", "")
        m = re.search(r"(\d+(\.\d+)?)", s)
        if not m:
            return None
        return float(m.group(1))
    except Exception:
        return None

def extract_jsonld(soup: BeautifulSoup) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for tag in soup.select('script[type="application/ld+json"]'):
        try:
            raw = tag.get_text(strip=True)
            if not raw:
                continue
            data = json.loads(raw)
            if isinstance(data, dict):
                out.append(data)
            elif isinstance(data, list):
                out.extend([x for x in data if isinstance(x, dict)])
        except Exception:
            continue
    return out

def extract_next_data(soup: BeautifulSoup) -> Optional[Dict[str, Any]]:
    """
    LandSearch uses Next.js; pages often contain:
      <script id="__NEXT_DATA__" type="application/json">...</script>
    """
    tag = soup.find("script", id="__NEXT_DATA__")
    if not tag:
        return None
    try:
        raw = tag.get_text(strip=True)
        if not raw:
            return
