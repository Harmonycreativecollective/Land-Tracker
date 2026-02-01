import json
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse, urljoin

import requests
from bs4 import BeautifulSoup

# ====== YOUR SETTINGS ======
START_URLS = [
    "https://www.landsearch.com/properties/king-george-va",
    "https://www.landsearch.com/properties/westmoreland-county-va",
    "https://www.landsearch.com/properties/caroline-county-va",
    "https://www.landsearch.com/properties/stafford-county-va",
    "https://www.landsearch.com/properties/frederick-county-md",
    "https://www.landsearch.com/properties/anne-arundel-county-md",

    "https://www.landwatch.com/virginia-land-for-sale/king-george",
    "https://www.landwatch.com/virginia-land-for-sale/westmoreland-county",
    "https://www.landwatch.com/virginia-land-for-sale/caroline-county",
    "https://www.landwatch.com/virginia-land-for-sale/stafford-county",
    "https://www.landwatch.com/maryland-land-for-sale/caroline-county",
    "https://www.landwatch.com/maryland-land-for-sale/frederick-county",
    "https://www.landwatch.com/maryland-land-for-sale/anne-arundel-county",
    "https://www.landwatch.com/maryland-land-for-sale/montgomery-county",
]

MIN_ACRES = 10.0
MAX_ACRES = 50.0
MAX_PRICE = 600_000

DETAIL_ENRICH_LIMIT = 12
# ===========================

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

TIMEOUT = 40
DATA_FILE = "data/listings.json"

session = requests.Session()
session.headers.update(HEADERS)

# ------------------------------
# Utilities
# ------------------------------
def fetch_html(url: str) -> str:
    r = session.get(url, timeout=TIMEOUT)
    r.raise_for_status()
    return r.text

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

def normalize_url(base_url: str, u: str) -> str:
    if not u:
        return ""
    return urljoin(base_url, u)

def canonicalize_url(u: str) -> str:
    """
    Helps dedupe reliably (removes fragments + some tracking params).
    """
    try:
        p = urlparse(u)
        # keep path + netloc; drop fragment
        clean = p._replace(fragment="").geturl()
        return clean
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

    s = re.sub(r"(from|starting at|starting|approx\.?|about)", "", s).strip()
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

    if isinstance(value, dict):
        for k in ["acres", "acreage", "lotSizeAcres", "sizeAcres", "landSize"]:
            if k in value:
                v = parse_acres(value.get(k))
                if v is not None:
                    return v

        val = value.get("value") or value.get("amount") or value.get("number")
        unit = (value.get("unit") or value.get("unitText") or value.get("unitCode") or "").lower()

        try:
            vnum = float(str(val).replace(",", "").strip())
        except Exception:
            return None

        if "acre" in unit or "acr" in unit:
            return vnum
        if "sq" in unit or "ft" in unit:
            return vnum / 43560.0
        if vnum > 5000:
            return vnum / 43560.0

        return vnum

    s = str(value).strip().lower().replace(",", "")
    if not s:
        return None
    m = re.search(r"(\d+(?:\.\d+)?)", s)
    if not m:
        return None
    num = float(m.group(1))
    if "sq" in s and ("ft" in s or "feet" in s):
        return num / 43560.0
    if num > 5000:
        return num / 43560.0
    return num

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
            out.append(json.loads(tag.string))
        except Exception:
            continue
    return out

BAD_TITLE_SET = {"", "land listing", "skip to navigation", "skip to content", "listing"}

def is_bad_title(title: Optional[str]) -> bool:
    t = (title or "").strip().lower()
    return t in BAD_TITLE_SET

def best_title(d: dict, source_name: str) -> str:
    t = (d.get("title") or d.get("name") or d.get("headline") or "").strip()
    if is_bad_title(t):
        return f"{source_name} listing"
    return t

def try_thumbnail_from_dict(d: dict) -> Optional[str]:
    for k in ["image", "thumbnail", "thumbnailUrl", "photo", "photoUrl", "imageUrl"]:
        if d.get(k):
            v = d.get(k)
            if isinstance(v, str):
                return v
            if isinstance(v, list) and v and isinstance(v[0], str):
                return v[0]
            if isinstance(v, dict) and v.get("url"):
                return v.get("url")
    return None

def should_enrich(it: Dict[str, Any]) -> bool:
    return is_bad_title(it.get("title")) or (not it.get("thumbnail")) or (it.get("status") in [None, "", "unknown"])

# ------------------------------
# Match logic for ever_top_match (scraper-side)
# ------------------------------
def meets_acres(acres: Optional[float]) -> bool:
    if acres is None:
        return False
    try:
        a = float(acres)
        return MIN_ACRES <= a <= MAX_ACRES
    except Exception:
        return False

def meets_price(price: Optional[int]) -> bool:
    if price is None:
        return False
    try:
        return int(price) <= int(MAX_PRICE)
    except Exception:
        return False

def is_current_top_match(item: Dict[str, Any]) -> bool:
    # We exclude unavailable statuses if we detect them.
    status = (item.get("status") or "unknown").strip().lower()
    if status in {"under_contract", "pending", "sold"}:
        return False
    return meets_acres(item.get("acres")) and meets_price(item.get("price"))

# ------------------------------
# Status detection from detail pages
# ------------------------------
STATUS_KEYWORDS = [
    ("sold", ["sold"]),
    ("pending", ["pending"]),
    ("under_contract", ["under contract", "under-contract", "contract"]),
]

def detect_status_from_html(html: str) -> str:
    """
    Conservative: only returns a non-unknown status if we are pretty sure.
    """
    text = BeautifulSoup(html, "html.parser").get_text(" ", strip=True).lower()

    # Strong signals first
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

    def meta(tag_key: str, attr: str = "property") -> str:
        tag = soup.find("meta", attrs={attr: tag_key})
        if tag and tag.get("content"):
            return tag["content"].strip()
        return ""

    title = meta("og:title", "property") or meta("twitter:title", "name")
    if not title:
        h1 = soup.find("h1")
        if h1:
            title = h1.get_text(" ", strip=True)
    if not title and soup.title and soup.title.string:
        title = soup.title.string.strip()

    thumb = meta("og:image", "property") or meta("twitter:image", "name")

    status = detect_status_from_html(str(soup))

    if title:
        title = " ".join(title.split()).strip()
    if is_bad_title(title):
        title = None

    return {"title": title or None, "thumbnail": thumb or None, "status": status or None}

# ------------------------------
# Extraction
# ------------------------------
def extract_from_landsearch_next(base_url: str, next_data: dict) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for d in walk(next_data):
        if not isinstance(d, dict):
            continue

        raw_url = (
            d.get("url")
            or d.get("href")
            or d.get("canonicalUrl")
            or d.get("link")
            or d.get("landingPage")
            or d.get("permalink")
            or ""
        )
        url = normalize_url(base_url, str(raw_url)) if raw_url else ""
        if not url or "landsearch.com" not in url:
            continue

        p = urlparse(url)
        if p.fragment:
            continue
        parts = p.path.strip("/").split("/")
        if len(parts) < 3 or parts[0] != "properties" or not parts[-1].isdigit():
            continue

        price = parse_money(
            d.get("price")
            or d.get("listPrice")
            or d.get("priceValue")
            or d.get("amount")
            or ((d.get("offers") or {}).get("price") if isinstance(d.get("offers"), dict) else None)
        )
        acres = parse_acres(
            d.get("acres")
            or d.get("acreage")
            or d.get("lotSizeAcres")
            or d.get("sizeAcres")
            or d.get("lotSize")
            or d.get("size")
            or d.get("area")
            or d.get("landSize")
        )
        thumb = try_thumbnail_from_dict(d)

        items.append(
            {
                "source": "LandSearch",
                "title": best_title(d, "LandSearch"),
                "url": url,
                "price": price,
                "acres": acres,
                "thumbnail": thumb,
                "status": "unknown",
            }
        )

    seen = set()
    out = []
    for it in items:
        cu = canonicalize_url(it["url"])
        if cu in seen:
            continue
        seen.add(cu)
        it["url"] = cu
        out.append(it)
    return out

def extract_from_jsonld(base_url: str, blocks: List[dict], source_name: str) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for block in blocks:
        for d in walk(block):
            if not isinstance(d, dict):
                continue

            raw_url = d.get("url") or d.get("mainEntityOfPage") or d.get("sameAs") or ""
            if not raw_url:
                continue
            url = canonicalize_url(normalize_url(base_url, str(raw_url)))
            if not url:
                continue

            host = urlparse(base_url).netloc.lower()

            if "landwatch.com" in host and "/property/" not in urlparse(url).path:
                continue

            price = parse_money(
                d.get("price")
                or d.get("listPrice")
                or ((d.get("offers") or {}).get("price") if isinstance(d.get("offers"), dict) else None)
            )
            acres = parse_acres(
                d.get("acres")
                or d.get("lotSize")
                or d.get("lotSizeAcres")
                or d.get("size")
                or d.get("area")
            )
            thumb = try_thumbnail_from_dict(d)

            items.append(
                {
                    "source": source_name,
                    "title": best_title(d, source_name),
                    "url": url,
                    "price": price,
                    "acres": acres,
                    "thumbnail": thumb,
                    "status": "unknown",
                }
            )

    seen = set()
    out = []
    for it in items:
        if it["url"] in seen:
            continue
        seen.add(it["url"])
        out.append(it)
    return out

def extract_from_html_fallback(base_url: str, html: str, source_name: str) -> List[Dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    items: List[Dict[str, Any]] = []

    for a in soup.find_all("a", href=True):
        full = canonicalize_url(normalize_url(base_url, a["href"]))
        if not full:
            continue

        host = urlparse(base_url).netloc.lower()
        if "landwatch.com" in host and "/property/" not in urlparse(full).path:
            continue

        card_text = a.get_text(" ", strip=True) or ""
        price = parse_money(card_text)
        acres = None
        m = re.search(r"(\d+(?:\.\d+)?)\s*acres?\b", card_text.lower())
        if m:
            acres = float(m.group(1))

        img = a.find("img")
        thumb = img.get("src") if img and img.get("src") else None

        raw_title = a.get_text(" ", strip=True)
        title = raw_title if not is_bad_title(raw_title) else f"{source_name} listing"

        items.append(
            {
                "source": source_name,
                "title": title,
                "url": full,
                "price": price,
                "acres": acres,
                "thumbnail": thumb,
                "status": "unknown",
            }
        )

    seen = set()
    out = []
    for it in items:
        if it["url"] in seen:
            continue
        seen.add(it["url"])
        out.append(it)
    return out

def extract_listings(url: str, html: str) -> List[Dict[str, Any]]:
    host = urlparse(url).netloc.lower()
    next_data = get_next_data_json(html)
    json_ld_blocks = get_json_ld(html)

    items: List[Dict[str, Any]] = []

    if "landsearch.com" in host and next_data:
        items.extend(extract_from_landsearch_next(url, next_data))

    if json_ld_blocks:
        items.extend(
            extract_from_jsonld(
                url,
                json_ld_blocks,
                "LandSearch" if "landsearch.com" in host else "LandWatch",
            )
        )

    if not items:
        items.extend(
            extract_from_html_fallback(
                url,
                html,
                "LandSearch" if "landsearch.com" in host else "LandWatch",
            )
        )

    seen = set()
    out = []
    for it in items:
        if it["url"] in seen:
            continue
        seen.add(it["url"])
        out.append(it)
    return out

# ------------------------------
# Persistence across runs
# ------------------------------
def load_existing_maps() -> Dict[str, Dict[str, Any]]:
    """
    Returns per-url metadata we want to persist:
    found_utc, status, ever_top_match
    """
    try:
        if not os.path.exists(DATA_FILE):
            return {}
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            old = json.load(f)
        out: Dict[str, Dict[str, Any]] = {}
        for it in old.get("items", []) or []:
            u = it.get("url")
            if not u:
                continue
            out[u] = {
                "found_utc": it.get("found_utc"),
                "status": (it.get("status") or "unknown"),
                "ever_top_match": bool(it.get("ever_top_match", False)),
            }
        return out
    except Exception:
        return {}

def main():
    os.makedirs("data", exist_ok=True)

    run_utc = datetime.now(timezone.utc).isoformat()

    old_map = load_existing_maps()

    all_items: List[Dict[str, Any]] = []
    for url in START_URLS:
        try:
            html = fetch_html(url)
        except Exception as e:
            print(f"Failed to fetch {url}: {e}")
            continue
        all_items.extend(extract_listings(url, html))

    # Dedup by URL across sources
    seen = set()
    final: List[Dict[str, Any]] = []
    for x in all_items:
        u = x.get("url")
        if not u:
            continue
        u = canonicalize_url(u)
        if u in seen:
            continue
        seen.add(u)
        x["url"] = u

        # Persist found_utc
        prev = old_map.get(u, {})
        if prev.get("found_utc"):
            x["found_utc"] = prev["found_utc"]
        else:
            x["found_utc"] = run_utc

        # Persist status if we already had something better than unknown
        prev_status = (prev.get("status") or "unknown").strip().lower()
        cur_status = (x.get("status") or "unknown").strip().lower()
        if prev_status != "unknown" and cur_status == "unknown":
            x["status"] = prev_status

        # Never allow generic titles into file
        if is_bad_title(x.get("title")):
            x["title"] = f"{x.get('source','Listing')} listing"

        # Compute ever_top_match (sticky)
        prev_ever = bool(prev.get("ever_top_match", False))
        cur_top = is_current_top_match(x)
        x["ever_top_match"] = prev_ever or cur_top

        final.append(x)

    # Enrichment (title/thumb/status) for limited items
    enriched = 0
    for it in final:
        if enriched >= DETAIL_ENRICH_LIMIT:
            break
        if should_enrich(it):
            info = enrich_from_detail_page(it["url"])

            if info.get("title") and is_bad_title(it.get("title")):
                it["title"] = info["title"]

            if (not it.get("thumbnail")) and info.get("thumbnail"):
                it["thumbnail"] = info["thumbnail"]

            # Only overwrite status if we learned something
            if info.get("status") and info["status"] != "unknown":
                it["status"] = info["status"]

            enriched += 1

    out = {
        "last_updated_utc": run_utc,
        "criteria": {
            "min_acres": MIN_ACRES,
            "max_acres": MAX_ACRES,
            "max_price": MAX_PRICE,
        },
        "items": final,
    }

    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)

    print(f"Saved {len(final)} listings found. Enriched: {enriched}.")

if __name__ == "__main__":
    main()
