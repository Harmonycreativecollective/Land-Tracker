import json
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse, urljoin

import requests
from bs4 import BeautifulSoup

# ====== SETTINGS ======
START_URLS = [
    # LandSearch
    "https://www.landsearch.com/properties/king-george-va",
    "https://www.landsearch.com/properties/westmoreland-county-va",
    "https://www.landsearch.com/properties/caroline-county-va",
    "https://www.landsearch.com/properties/stafford-county-va",
    "https://www.landsearch.com/properties/frederick-county-md",
    "https://www.landsearch.com/properties/anne-arundel-county-md",

    # LandWatch
    "https://www.landwatch.com/virginia-land-for-sale/king-george",
    "https://www.landwatch.com/virginia-land-for-sale/westmoreland-county",
    "https://www.landwatch.com/virginia-land-for-sale/caroline-county",
    "https://www.landwatch.com/virginia-land-for-sale/stafford-county",
    "https://www.landwatch.com/maryland-land-for-sale/frederick-county",
    "https://www.landwatch.com/maryland-land-for-sale/anne-arundel-county",
    "https://www.landwatch.com/maryland-land-for-sale/montgomery-county",
]

MIN_ACRES = 10.0
MAX_ACRES = 50.0
MAX_PRICE = 600_000

DETAIL_ENRICH_LIMIT = 20
TIMEOUT = 40

DATA_FILE = "data/listings.json"
# =======================

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
}

session = requests.Session()
session.headers.update(HEADERS)


# ------------------------------
# Helpers
# ------------------------------
def fetch_html(url: str) -> str:
    r = session.get(url, timeout=TIMEOUT)
    r.raise_for_status()
    return r.text


def normalize_url(base_url: str, u: str) -> str:
    if not u:
        return ""
    return urljoin(base_url, u)


def canonicalize_url(u: str) -> str:
    try:
        p = urlparse(u)
        return p._replace(fragment="").geturl()
    except Exception:
        return u


def parse_money(value: Any) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        v = int(value)
        return v if v >= 1000 else None

    s = str(value).strip().lower()
    if not s:
        return None
    if any(x in s for x in ["contact", "call", "tbd", "request"]):
        return None

    s = s.replace(",", "")
    m = re.search(r"(\d+(?:\.\d+)?)\s*([km])?\b", s)
    if not m:
        return None

    num = float(m.group(1))
    suffix = m.group(2)
    if suffix == "k":
        num *= 1000
    elif suffix == "m":
        num *= 1_000_000

    v = int(num)
    return v if v >= 1000 else None


def parse_acres(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)

    s = str(value).strip().lower().replace(",", "")
    if not s:
        return None

    m = re.search(r"(\d+(?:\.\d+)?)", s)
    if not m:
        return None
    num = float(m.group(1))

    # sq ft -> acres
    if "sq" in s and ("ft" in s or "feet" in s):
        return num / 43560.0

    # sometimes large number implies sq ft
    if num > 5000:
        return num / 43560.0

    return num


def detect_blocked(html: str) -> bool:
    t = html.lower()
    # super common bot-block patterns
    blockers = [
        "access denied",
        "verify you are human",
        "captcha",
        "cloudflare",
        "unusual traffic",
    ]
    return any(b in t for b in blockers)


def get_json_ld(html: str) -> List[dict]:
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for tag in soup.find_all("script", type="application/ld+json"):
        if not tag.string:
            continue
        try:
            out.append(json.loads(tag.string))
        except Exception:
            continue
    return out


def walk(obj: Any):
    stack = [obj]
    while stack:
        cur = stack.pop()
        if isinstance(cur, dict):
            yield cur
            for v in cur.values():
                stack.append(v)
        elif isinstance(cur, list):
            for v in cur:
                stack.append(v)


# ------------------------------
# URL classification (IMPORTANT)
# ------------------------------
def is_landsearch_listing_url(url: str) -> bool:
    """
    LandSearch listing urls are under /properties/ and are NOT the county index page.

    Examples we want:
      /properties/<place>/<something>/<something>
      /properties/<place>/<something>
    Examples we reject:
      /properties
      /properties/<place>
    """
    p = urlparse(url)
    if "landsearch.com" not in p.netloc.lower():
        return False
    parts = [x for x in p.path.split("/") if x]
    if len(parts) < 2:
        return False
    if parts[0] != "properties":
        return False

    # reject index pages
    if len(parts) == 1:
        return False
    if len(parts) == 2:
        # /properties/king-george-va  (index page)
        return False

    # ✅ listing-like: /properties/<place>/<listing-slug...>
    return True


def is_landwatch_listing_url(url: str) -> bool:
    p = urlparse(url)
    if "landwatch.com" not in p.netloc.lower():
        return False
    return "/property/" in p.path.lower()


# ------------------------------
# Extract from HTML anchors + JSON-LD
# ------------------------------
def extract_listings(base_url: str, html: str) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    host = urlparse(base_url).netloc.lower()

    # 1) JSON-LD first (cleanest)
    for block in get_json_ld(html):
        for d in walk(block):
            if not isinstance(d, dict):
                continue

            raw_url = d.get("url") or d.get("mainEntityOfPage") or d.get("sameAs") or ""
            if not raw_url:
                continue
            url = canonicalize_url(normalize_url(base_url, str(raw_url)))

            if "landsearch.com" in host:
                if not is_landsearch_listing_url(url):
                    continue
                source_name = "LandSearch"
            else:
                if not is_landwatch_listing_url(url):
                    continue
                source_name = "LandWatch"

            title = (d.get("name") or d.get("headline") or d.get("title") or "").strip() or f"{source_name} listing"
            price = parse_money(d.get("price") or d.get("listPrice") or ((d.get("offers") or {}).get("price") if isinstance(d.get("offers"), dict) else None))
            acres = parse_acres(d.get("acres") or d.get("lotSize") or d.get("area"))
            thumb = None

            img = d.get("image")
            if isinstance(img, str):
                thumb = img
            elif isinstance(img, list) and img and isinstance(img[0], str):
                thumb = img[0]
            elif isinstance(img, dict) and img.get("url"):
                thumb = img.get("url")

            items.append({
                "source": source_name,
                "title": title,
                "url": url,
                "price": price,
                "acres": acres,
                "thumbnail": thumb,
                "status": "unknown",
            })

    # 2) Anchor fallback (if JSON-LD was sparse)
    soup = BeautifulSoup(html, "html.parser")
    for a in soup.find_all("a", href=True):
        full = canonicalize_url(normalize_url(base_url, a["href"]))
        if not full:
            continue

        if "landsearch.com" in host:
            if not is_landsearch_listing_url(full):
                continue
            source_name = "LandSearch"
        else:
            if not is_landwatch_listing_url(full):
                continue
            source_name = "LandWatch"

        text = a.get_text(" ", strip=True)
        title = text if text else f"{source_name} listing"
        price = parse_money(text)
        acres = None
        m = re.search(r"(\d+(?:\.\d+)?)\s*acres?\b", text.lower())
        if m:
            acres = float(m.group(1))

        items.append({
            "source": source_name,
            "title": title,
            "url": full,
            "price": price,
            "acres": acres,
            "thumbnail": None,
            "status": "unknown",
        })

    # Dedup
    seen = set()
    out = []
    for it in items:
        u = it.get("url")
        if not u or u in seen:
            continue
        seen.add(u)
        out.append(it)
    return out


# ------------------------------
# Detail enrichment (title/thumb/status)
# ------------------------------
STATUS_KEYWORDS = [
    ("sold", ["sold"]),
    ("pending", ["pending"]),
    ("under_contract", ["under contract", "under-contract", "contract"]),
]

def detect_status_from_html(html: str) -> str:
    text = BeautifulSoup(html, "html.parser").get_text(" ", strip=True).lower()
    for status, keys in STATUS_KEYWORDS:
        for k in keys:
            if k in text:
                return status
    return "unknown"


def enrich_from_detail_page(url: str) -> Dict[str, Optional[str]]:
    try:
        html = fetch_html(url)
    except Exception:
        return {"title": None, "thumbnail": None, "status": None}

    soup = BeautifulSoup(html, "html.parser")

    def meta(key: str, attr: str) -> str:
        tag = soup.find("meta", attrs={attr: key})
        return tag["content"].strip() if tag and tag.get("content") else ""

    title = meta("og:title", "property") or meta("twitter:title", "name")
    if not title:
        h1 = soup.find("h1")
        title = h1.get_text(" ", strip=True) if h1 else ""
    if not title and soup.title and soup.title.string:
        title = soup.title.string.strip()

    thumb = meta("og:image", "property") or meta("twitter:image", "name")
    status = detect_status_from_html(str(soup))

    title = title.strip() if title else None
    thumb = thumb.strip() if thumb else None
    return {"title": title, "thumbnail": thumb, "status": status}


# ------------------------------
# Main
# ------------------------------
def main():
    os.makedirs("data", exist_ok=True)
    run_utc = datetime.now(timezone.utc).isoformat()

    all_items: List[Dict[str, Any]] = []

    for url in START_URLS:
        try:
            html = fetch_html(url)
        except Exception as e:
            print(f"[FETCH FAIL] {url} -> {e}")
            continue

        if detect_blocked(html):
            print(f"[BLOCKED?] {url} looks like bot protection. Try later or change approach.")
            continue

        extracted = extract_listings(url, html)
        print(f"[OK] {url} -> {len(extracted)} extracted")
        all_items.extend(extracted)

    # Dedup across everything
    seen = set()
    final: List[Dict[str, Any]] = []
    for it in all_items:
        u = it.get("url")
        if not u:
            continue
        u = canonicalize_url(u)
        if u in seen:
            continue
        seen.add(u)
        it["url"] = u
        it["found_utc"] = run_utc
        it["ever_top_match"] = False  # keep field for app compatibility
        final.append(it)

    # Enrich a limited number
    enriched = 0
    for it in final:
        if enriched >= DETAIL_ENRICH_LIMIT:
            break
        info = enrich_from_detail_page(it["url"])
        if info.get("title"):
            it["title"] = info["title"]
        if info.get("thumbnail"):
            it["thumbnail"] = info["thumbnail"]
        if info.get("status") and info["status"] != "unknown":
            it["status"] = info["status"]
        enriched += 1

    out = {
        "last_updated_utc": run_utc,
        "criteria": {"min_acres": MIN_ACRES, "max_acres": MAX_ACRES, "max_price": MAX_PRICE},
        "items": final,
    }

    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)

    print(f"\nSaved {len(final)} listings. Enriched: {enriched}.")


if __name__ == "__main__":
    main()
