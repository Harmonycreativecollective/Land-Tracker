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
            return None
        return json.loads(raw)
    except Exception:
        return None

def walk_values(obj: Any) -> Iterable[Any]:
    """
    Recursively yield all values in nested dict/list structures.
    """
    if isinstance(obj, dict):
        for v in obj.values():
            yield v
            yield from walk_values(v)
    elif isinstance(obj, list):
        for v in obj:
            yield v
            yield from walk_values(v)

def find_first_by_keys(obj: Any, keys: Set[str]) -> Optional[Any]:
    """
    Recursively find first dict value where key matches (case-insensitive).
    """
    if isinstance(obj, dict):
        for k, v in obj.items():
            if str(k).lower() in keys and v is not None:
                return v
        for v in obj.values():
            found = find_first_by_keys(v, keys)
            if found is not None:
                return found
    elif isinstance(obj, list):
        for v in obj:
            found = find_first_by_keys(v, keys)
            if found is not None:
                return found
    return None

def first_image_url(obj: Any) -> Optional[str]:
    """
    Try to locate a usable image URL from nested JSON structures.
    """
    # common patterns:
    # image: "https://..."
    # image: ["https://..."]
    # images: [{"url": "..."}, ...]
    candidate = find_first_by_keys(obj, {"image", "images", "primaryimage", "heroimage"})
    if isinstance(candidate, str) and candidate.startswith("http"):
        return candidate
    if isinstance(candidate, list):
        for v in candidate:
            if isinstance(v, str) and v.startswith("http"):
                return v
            if isinstance(v, dict):
                u = v.get("url") or v.get("src")
                if isinstance(u, str) and u.startswith("http"):
                    return u
    if isinstance(candidate, dict):
        u = candidate.get("url") or candidate.get("src")
        if isinstance(u, str) and u.startswith("http"):
            return u
    return None

# -----------------------------
# Scrape index pages -> property links
# -----------------------------
def extract_property_links_from_index(url: str, html: str) -> Set[str]:
    soup = soupify(html)
    links: Set[str] = set()
    for a in soup.select("a[href]"):
        href = a.get("href") or ""
        if not href:
            continue
        abs_url = urljoin(url, href)
        abs_url = norm_url(abs_url)
        if is_property_listing_url(abs_url):
            links.add(abs_url)
    return links

# -----------------------------
# Enrich property page
# -----------------------------
def enrich_landsearch_property(url: str) -> Optional[Dict[str, Any]]:
    status, html = fetch(url)
    time.sleep(SLEEP_BETWEEN_REQUESTS)

    if status != 200:
        print(f"[FETCH FAIL] {url} -> {status}")
        return None

    soup = soupify(html)
    jsonlds = extract_jsonld(soup)
    nextdata = extract_next_data(soup)

    # Title: prefer JSON-LD name, else page title
    title = None
    for block in jsonlds:
        nm = block.get("name")
        if isinstance(nm, str) and nm.strip():
            title = nm.strip()
            break
    if not title:
        og = soup.find("meta", property="og:title")
        if og and og.get("content"):
            title = og.get("content").strip()
    if not title:
        if soup.title and soup.title.get_text(strip=True):
            title = soup.title.get_text(strip=True)

    # Price: try json-ld offers.price, then nextdata keys
    price = None
    for block in jsonlds:
        offers = block.get("offers")
        if isinstance(offers, dict):
            p = offers.get("price")
            price = safe_int(p)
            if price is not None:
                break
    if price is None and nextdata:
        price_val = find_first_by_keys(nextdata, {"price", "listprice", "currentprice", "askingprice"})
        price = safe_int(price_val)

    # Acres: try json-ld "floorSize" or "areaServed"/other; then nextdata keys
    acres = None
    # JSON-LD patterns vary; try multiple key hunts
    for block in jsonlds:
        lot = block.get("floorSize") or block.get("landSize") or block.get("additionalProperty")
        if lot:
            # Sometimes floorSize is {"value": 10.3, "unitCode": "..."} etc
            if isinstance(lot, dict):
                acres = safe_float(lot.get("value") or lot.get("size") or lot.get("amount"))
            elif isinstance(lot, list):
                # additionalProperty might contain {"name": "...", "value": "..."}
                for entry in lot:
                    if isinstance(entry, dict):
                        nm = str(entry.get("name") or "").lower()
                        if "acre" in nm or "lot" in nm:
                            acres = safe_float(entry.get("value"))
                            if acres is not None:
                                break
            if acres is not None:
                break

    if acres is None and nextdata:
        acres_val = find_first_by_keys(nextdata, {"acres", "acreage", "lotsizeacres", "lotsize", "landsize"})
        acres = safe_float(acres_val)

    # Thumbnail: prefer OG image, else from JSON
    thumb = None
    ogimg = soup.find("meta", property="og:image")
    if ogimg and ogimg.get("content"):
        thumb = ogimg.get("content").strip()
    if not thumb and nextdata:
        thumb = first_image_url(nextdata)
    if not thumb and jsonlds:
        thumb = first_image_url(jsonlds)

    # Try to infer state/county from url slug if not provided (optional)
    # (Your app can live without these; better if scraper later provides true values.)
    state = None
    county = None

    item = {
        "source": "LandSearch",
        "title": title or "LandSearch listing",
        "url": url,
        "price": price,
        "acres": acres,
        "thumbnail": thumb,
        "state": state,
        "county": county,
        "status": "unknown",
        "found_utc": RUN_TS,  # current run timestamp
        "ever_top_match": False,  # computed after enrichment
    }
    return item

# -----------------------------
# Ever-top-match calculation
# -----------------------------
def is_top_match(item: Dict[str, Any], criteria: Dict[str, Any]) -> bool:
    try:
        pmax = int(criteria.get("max_price", 600000))
        amin = float(criteria.get("min_acres", 10))
        amax = float(criteria.get("max_acres", 50))
    except Exception:
        pmax, amin, amax = 600000, 10.0, 50.0

    price = item.get("price")
    acres = item.get("acres")
    if price is None or acres is None:
        return False
    try:
        return float(acres) >= amin and float(acres) <= amax and int(price) <= pmax
    except Exception:
        return False

# -----------------------------
# Main
# -----------------------------
RUN_TS = now_utc_iso()

def main() -> None:
    print("=== KB Land Tracker Scraper (LandSearch only) ===")
    print(f"Run timestamp (UTC): {RUN_TS}")
    print(f"Seeds ({len(SEED_URLS)}):")
    for s in SEED_URLS:
        print(f" - {s}")

    # 1) collect property urls
    property_urls: Set[str] = set()

    for seed in SEED_URLS:
        seed = norm_url(seed)
        if is_property_listing_url(seed):
            property_urls.add(seed)
            continue

        if not is_probable_index_page(seed):
            print(f"[SKIP] Not LandSearch or not recognized seed: {seed}")
            continue

        try:
            status, html = fetch(seed)
            time.sleep(SLEEP_BETWEEN_REQUESTS)
            if status != 200:
                print(f"[FETCH FAIL] {seed} -> {status}")
                continue
            links = extract_property_links_from_index(seed, html)
            print(f"[INDEX] {seed} -> found {len(links)} property links")
            property_urls.update(links)
        except Exception as e:
            print(f"[ERROR] seed fetch failed {seed}: {e}")

    property_urls = set(sorted(property_urls))
    print(f"Total unique property URLs: {len(property_urls)}")

    # 2) enrich property pages
    enriched: List[Dict[str, Any]] = []
    fails = 0

    for i, url in enumerate(property_urls, start=1):
        try:
            item = enrich_landsearch_property(url)
            if not item:
                fails += 1
                continue
            enriched.append(item)
            if i % 20 == 0:
                print(f"[PROGRESS] enriched {len(enriched)}/{i} (fails={fails})")
        except Exception as e:
            fails += 1
            print(f"[ERROR] enrich failed {url}: {e}")

    # 3) compute ever_top_match for this run
    for it in enriched:
        it["ever_top_match"] = bool(is_top_match(it, DEFAULT_CRITERIA))

    # 4) write listings.json
    payload = {
        "last_updated_utc": RUN_TS,
        "criteria": DEFAULT_CRITERIA,
        "items": enriched,
    }

    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    # 5) summary logs
    priced = sum(1 for it in enriched if it.get("price") is not None)
    ac = sum(1 for it in enriched if it.get("acres") is not None)
    both = sum(1 for it in enriched if it.get("price") is not None and it.get("acres") is not None)
    tops = sum(1 for it in enriched if it.get("ever_top_match") is True)

    print("=== DONE ===")
    print(f"Saved items: {len(enriched)}")
    print(f"Enrich fails: {fails}")
    print(f"Have price: {priced}")
    print(f"Have acres: {ac}")
    print(f"Have both: {both}")
    print(f"Ever top matches (based on criteria): {tops}")
    print(f"Wrote: {DATA_PATH}")

if __name__ == "__main__":
    main()
