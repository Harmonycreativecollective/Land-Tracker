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
        return float(re.findall(r"[\d.]+", s)[0])
    except Exception:
        return None

def to_int(x) -> Optional[int]:
    try:
        if x is None:
            return None
        if isinstance(x, int):
            return x
        if isinstance(x, float):
            return int(x)
        s = str(x).strip().replace(",", "")
        m = re.search(r"\d+", s)
        return int(m.group(0)) if m else None
    except Exception:
        return None

def passes(price: Optional[int], acres: Optional[float]) -> bool:
    if price is None or acres is None:
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

def extract_candidates_from_next(next_data: dict) -> List[dict]:
    # This pulls out "listing-ish" objects by hunting keys that commonly exist in property cards.
    candidates = []
    for d in walk(next_data):
        keys = set(d.keys())
        if any(k in keys for k in ["acres", "price", "url", "title", "name", "city", "state"]):
            candidates.append(d)
    return candidates

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
            # Try a bunch of likely fields for link/title/price/acres
            url = normalize_url(
                d.get("url")
                or d.get("landingPage")
                or d.get("canonicalUrl")
                or d.get("link")
                or ""
            )

            title = (
                d.get("title")
                or d.get("name")
                or d.get("headline")
                or ""
            )

            price = to_int(
                d.get("price")
                or d.get("listPrice")
                or (d.get("offers", {}) or {}).get("price") if isinstance(d.get("offers"), dict) else None
            )

            acres = to_float(
                d.get("acres")
                or d.get("lotSize")
                or d.get("lotSizeAcres")
                or d.get("size")
                or d.get("area")
            )

            # Some pages store lot size in square feet—try to convert if it's huge.
            if acres and acres > 5000:  # probably sq ft
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
        },
        "items": final,
    }

    with open("data/listings.json", "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)

    print(f"Saved {len(final)} matches.")

if __name__ == "__main__":
    main()
