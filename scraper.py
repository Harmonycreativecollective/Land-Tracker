import json
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import requests
from bs4 import BeautifulSoup

# ====== YOUR SETTINGS ======
START_URLS = [
    "https://www.landsearch.com/properties/king-george-va/filter/format=sales,size[min]=10",
]

MIN_ACRES = 11.0
MAX_ACRES = 50.0
MAX_PRICE = 600_000

# helps avoid saving junk like "$8/acre" becoming "$8"
MIN_PRICE = 1000
# ===========================

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

def fetch_html(url: str) -> str:
    r = requests.get(url, headers=HEADERS, timeout=40)
    r.raise_for_status()
    return r.text

def get_next_data_json(html: str) -> Optional[dict]:
    soup = BeautifulSoup(html, "html.parser")
    tag = soup.find("script", id="__NEXT_DATA__", type="application/json")
    if not tag or not tag.string:
        return None
    try:
        return json.loads(tag.string)
    except Exception:
        return None

def get_json_ld(html: str) -> List[dict]:
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for tag in soup.find_all("script", type="application/ld+json"):
        if not tag.string:
            continue
        try:
            data = json.loads(tag.string)
            out.append(data)
        except Exception:
            continue
    return out

def walk(obj: Any):
    """Yield all dicts/lists in a nested structure."""
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

def to_float(x) -> Optional[float]:
    try:
        if x is None:
            return None
        if isinstance(x, (int, float)):
            return float(x)
        s = str(x).strip().lower().replace(",", "")
        m = re.findall(r"[\d.]+", s)
        return float(m[0]) if m else None
    except Exception:
        return None

def to_int(x) -> Optional[int]:
    """
    Parse integer prices safely.
    Avoid capturing rate prices like "$8/acre" or "$120/mo".
    """
    try:
        if x is None:
            return None
        if isinstance(x, int):
            return x
        if isinstance(x, float):
            return int(x)

        s = str(x).strip().lower()

        # Ignore rate prices like "$8/acre", "per acre", "/mo", etc.
        if any(token in s for token in ["/acre", "per acre", "/ac", "per ac", "/mo", "per month", "monthly"]):
            return None

        s = s.replace(",", "")
        m = re.search(r"\d+", s)
        return int(m.group(0)) if m else None
    except Exception:
        return None

def passes(price: Optional[int], acres: Optional[float]) -> bool:
    if price is None or acres is None:
        return False
    if price < MIN_PRICE:
        return False
    return (MIN_ACRES <= acres <= MAX_ACRES) and (price <= MAX_PRICE)

def normalize_url(u: str) -> str:
    if not u:
        return ""
    if u.startswith("//"):
        return "https:" + u
    if u.startswith("/"):
        return "https://www.landsearch.com" + u
    return u

def extract_listings(html: str) -> List[Dict[str, Any]]:
    matches: List[Dict[str, Any]] = []

    next_data = get_next_data_json(html)
    json_ld_blocks = get_json_ld(html)

    blobs = []
    if next_data:
        blobs.append(("next", next_data))
    for block in json_ld_blocks:
        blobs.append(("ld", block))

    for source, blob in blobs:
        for d in walk(blob):
            # URL
            url = normalize_url(
                d.get("url")
                or d.get("landingPage")
                or d.get("canonicalUrl")
                or d.get("link")
                or ""
            )

            # Title
            title = (
                d.get("title")
                or d.get("name")
                or d.get("headline")
                or ""
            )

            # Price (try common fields)
            price = to_int(
                d.get("price")
                or d.get("listPrice")
                or (d.get("offers", {}) or {}).get("price") if isinstance(d.get("offers"), dict) else None
            )

            # Acres (try common fields)
            acres = to_float(
                d.get("acres")
                or d.get("lotSize")
                or d.get("lotSizeAcres")
                or d.get("size")
                or d.get("area")
            )

            # Convert sq ft to acres if it looks like sq ft
            if acres and acres > 5000:
                acres = acres / 43560.0

            if url and passes(price, acres):
                matches.append({
                    "source": f"LandSearch ({source})",
                    "title": str(title).strip() or "Land listing",
                    "url": url,
                    "price": price,
                    "acres": acres,
                })

    # Dedup by url
    seen = set()
    out = []
    for m in matches:
        if m["url"] in seen:
            continue
        seen.add(m["url"])
        out.append(m)
    return out

def main():
    run_utc = datetime.now(timezone.utc).isoformat()
    all_items: List[Dict[str, Any]] = []

    for url in START_URLS:
        html = fetch_html(url)
        items = extract_listings(html)
        all_items.extend(items)

    # Final dedup
    seen = set()
    final = []
    for x in all_items:
        if x["url"] in seen:
            continue
        seen.add(x["url"])
        final.append(x)

    out = {
        "last_updated_utc": run_utc,
        "criteria": {
            "min_acres": MIN_ACRES,
            "max_acres": MAX_ACRES,
            "max_price": MAX_PRICE,
            "min_price": MIN_PRICE,
        },
        "items": final,
    }

    with open("data/listings.json", "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)

    print(f"Saved {len(final)} matches.")

if __name__ == "__main__":
    main()
