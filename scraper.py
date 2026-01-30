import json
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse, urljoin

import requests
from bs4 import BeautifulSoup

# ====== YOUR SETTINGS ======
START_URLS = [
    "https://www.landsearch.com/properties/king-george-va/filter/format=sales,size[min]=10",
    "https://www.landwatch.com/virginia-land-for-sale/king-george/acres-11-50/available",
]

MIN_ACRES = 11.0
MAX_ACRES = 50.0
MAX_PRICE = 600_000
MIN_PRICE = 1000  # helps reject bogus tiny numbers like 3, 4, 1
# ===========================

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

TIMEOUT = 40


def fetch_html(url: str) -> str:
    r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    return r.text


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


def normalize_url(base_url: str, u: str) -> str:
    if not u:
        return ""
    return urljoin(base_url, u)


def is_real_landsearch_listing_url(url: str) -> bool:
    """
    Accept only real LandSearch property detail pages.
    Example:
      https://www.landsearch.com/properties/13467-ellis-way-king-george-va-22485/4865687
    Reject:
      .../filter/...#nav
      .../properties/king-george-va/filter/...
    """
    if not url:
        return False
    if "landsearch.com" not in url:
        return False
    # Must end with /properties/<slug>/<id>
    return bool(re.search(r"/properties/[^/]+/\d+/?$", url))


def is_real_landwatch_listing_url(url: str) -> bool:
    """
    LandWatch detail pages commonly look like:
      https://www.landwatch.com/property/<...>/<id>
    This rejects non-detail navigation links.
    """
    if not url:
        return False
    if "landwatch.com" not in url:
        return False
    # Common LandWatch pattern: /property/...
    return "/property/" in url


def best_title(d: dict) -> str:
    t = (d.get("title") or d.get("name") or d.get("headline") or "").strip()
    # Kill obvious junk titles
    bad = {"skip to navigation", "navigation", "skip"}
    if t.lower() in bad:
        return "Land listing"
    return t or "Land listing"


def normalize_price(price: Optional[int]) -> Optional[int]:
    """Reject bogus tiny numeric values (3,4,1) that aren't real land prices."""
    if price is None:
        return None
    if price < MIN_PRICE:
        return None
    return price


def parse_money(value: Any) -> Optional[int]:
    """
    Parses prices like:
      599000, "$599,000", "$599K", "599K", "$1.2M", "From $350K", etc.
    Returns integer dollars.
    """
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return normalize_price(int(value))

    s = str(value).strip().lower()
    if not s:
        return None

    # common "contact for price"
    if "contact" in s or "call" in s or "tbd" in s:
        return None

    # Remove words like "from", "starting at"
    s = re.sub(r"(from|starting at|starting|approx\.?|about)", "", s).strip()

    # Find something like 599, 599k, 1.2m
    m = re.search(r"(\d+(?:\.\d+)?)\s*([km])?\b", s.replace(",", ""))
    if not m:
        return None

    num = float(m.group(1))
    suffix = m.group(2)

    if suffix == "k":
        num *= 1000
    elif suffix == "m":
        num *= 1_000_000

    return normalize_price(int(num))


def parse_acres(value: Any) -> Optional[float]:
    """
    Parses acres from:
      14.2, "14.2 acres", {"value": 14.2, "unit": "acre"}, {"acres": 14.2}, sqft conversions, etc.
    """
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)

    if isinstance(value, dict):
        for k in ["acres", "acreage", "lotSizeAcres", "lotSize_acres", "sizeAcres", "size_acres"]:
            if k in value:
                v = parse_acres(value.get(k))
                if v is not None:
                    return v

        val = value.get("value") or value.get("amount") or value.get("number")
        unit = (value.get("unit") or value.get("unitText") or value.get("unitCode") or "").lower()

        vnum = None
        if val is not None:
            try:
                vnum = float(str(val).replace(",", "").strip())
            except Exception:
                vnum = None

        if vnum is None:
            return None

        if "acr" in unit or "acre" in unit:
            return float(vnum)

        if "sq" in unit or "ft" in unit:
            return float(vnum) / 43560.0

        if vnum > 5000:
            return float(vnum) / 43560.0

        return float(vnum)

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


def get_og_image(html: str, base_url: str) -> Optional[str]:
    """Fallback thumbnail via og:image."""
    soup = BeautifulSoup(html, "html.parser")
    og = soup.find("meta", property="og:image")
    if og and og.get("content"):
        return normalize_url(base_url, og["content"])
    return None


def extract_thumbnail_from_dict(d: dict, base_url: str) -> Optional[str]:
    """
    Try common thumbnail keys from Next.js / JSON-LD blobs.
    """
    # Common keys we’ve seen
    for k in ["thumbnail", "image", "photo", "photoUrl", "imageUrl", "imageURL", "heroImage", "coverImage"]:
        if k in d and d.get(k):
            val = d.get(k)
            if isinstance(val, str):
                return normalize_url(base_url, val)
            if isinstance(val, dict):
                u = val.get("url") or val.get("src")
                if u:
                    return normalize_url(base_url, str(u))
            if isinstance(val, list) and val:
                first = val[0]
                if isinstance(first, str):
                    return normalize_url(base_url, first)
                if isinstance(first, dict):
                    u = first.get("url") or first.get("src")
                    if u:
                        return normalize_url(base_url, str(u))

    # JSON-LD style: "image": {"url": "..."} or "image": ["..."]
    if "image" in d and d.get("image"):
        img = d.get("image")
        if isinstance(img, str):
            return normalize_url(base_url, img)
        if isinstance(img, dict) and img.get("url"):
            return normalize_url(base_url, str(img.get("url")))
        if isinstance(img, list) and img:
            first = img[0]
            if isinstance(first, str):
                return normalize_url(base_url, first)
            if isinstance(first, dict) and first.get("url"):
                return normalize_url(base_url, str(first.get("url")))

    return None


def looks_like_listing_candidate(d: dict) -> bool:
    """
    A loose heuristic: we only want dicts that appear to describe a property/listing.
    This prevents random layout/meta dicts from being treated like listings.
    """
    keys = set(k.lower() for k in d.keys())
    # A listing-like dict often has at least a couple of these
    score = 0
    for k in ["price", "listprice", "acres", "acreage", "lotsize", "lotsizeacres", "url", "href", "permalink", "title", "name"]:
        if k in keys:
            score += 1
    return score >= 3


def extract_from_landsearch_next(base_url: str, next_data: dict) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []

    for d in walk(next_data):
        if not isinstance(d, dict):
            continue
        if not looks_like_listing_candidate(d):
            continue

        raw_url = (
            d.get("url")
            or d.get("href")
            or d.get("canonicalUrl")
            or d.get("link")
            or d.get("landingPage")
            or d.get("permalink")
            or d.get("detailUrl")
            or d.get("propertyUrl")
            or ""
        )
        url = normalize_url(base_url, str(raw_url)) if raw_url else ""
        if not is_real_landsearch_listing_url(url):
            continue

        price = parse_money(
            d.get("price")
            or d.get("listPrice")
            or d.get("priceValue")
            or d.get("amount")
            or ((d.get("offers") or {}).get("price") if isinstance(d.get("offers"), dict) else None)
            or ((d.get("pricing") or {}).get("price") if isinstance(d.get("pricing"), dict) else None)
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

        thumb = extract_thumbnail_from_dict(d, base_url)

        items.append(
            {
                "source": "LandSearch",
                "title": best_title(d),
                "url": url,
                "price": price,
                "acres": acres,
                "thumbnail": thumb,
            }
        )

    # Dedup by URL
    seen = set()
    out = []
    for it in items:
        if it["url"] in seen:
            continue
        seen.add(it["url"])
        out.append(it)
    return out


def extract_from_jsonld(base_url: str, blocks: List[dict], source_name: str) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for block in blocks:
        for d in walk(block):
            if not isinstance(d, dict):
                continue
            if not looks_like_listing_candidate(d):
                continue

            raw_url = d.get("url") or d.get("mainEntityOfPage") or d.get("sameAs") or ""
            url = normalize_url(base_url, str(raw_url)) if raw_url else ""

            host = urlparse(base_url).netloc.lower()
            if "landsearch.com" in host:
                if not is_real_landsearch_listing_url(url):
                    continue
            if "landwatch.com" in host:
                if not is_real_landwatch_listing_url(url):
                    continue

            title = best_title(d)

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

            thumb = extract_thumbnail_from_dict(d, base_url)

            items.append(
                {
                    "source": source_name,
                    "title": title or "Land listing",
                    "url": url,
                    "price": price,
                    "acres": acres,
                    "thumbnail": thumb,
                }
            )

    # Dedup
    seen = set()
    out = []
    for it in items:
        if it["url"] in seen:
            continue
        seen.add(it["url"])
        out.append(it)
    return out


def extract_from_html_fallback(base_url: str, html: str, source_name: str) -> List[Dict[str, Any]]:
    """
    Fallback: scrape visible text on listing cards.
    Only keeps links that look like *real* detail pages.
    """
    soup = BeautifulSoup(html, "html.parser")
    items: List[Dict[str, Any]] = []

    host = urlparse(base_url).netloc.lower()

    links = soup.find_all("a", href=True)
    for a in links:
        href = a["href"]
        full = normalize_url(base_url, href)

        if "landsearch.com" in host:
            if not is_real_landsearch_listing_url(full):
                continue
        if "landwatch.com" in host:
            if not is_real_landwatch_listing_url(full):
                continue

        # Use nearby text as a rough card block
        card_text = a.get_text(" ", strip=True)
        parent = a.parent
        for _ in range(4):
            if parent is None:
                break
            card_text = (parent.get_text(" ", strip=True) or card_text)
            parent = parent.parent

        title = a.get_text(" ", strip=True) or "Land listing"
        title = "Land listing" if title.lower() in {"skip to navigation", "navigation"} else title

        price = parse_money(card_text)

        acres = None
        m = re.search(r"(\d+(?:\.\d+)?)\s*acres?\b", card_text.lower())
        if m:
            acres = float(m.group(1))

        # thumbnail not reliable in fallback
        items.append(
            {
                "source": source_name,
                "title": title,
                "url": full,
                "price": price,
                "acres": acres,
                "thumbnail": None,
            }
        )

    # Dedup
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

    # LandSearch Next.js extraction
    if "landsearch.com" in host and next_data:
        items.extend(extract_from_landsearch_next(url, next_data))

    # JSON-LD extraction (both sites)
    if json_ld_blocks:
        source_name = "LandSearch" if "landsearch.com" in host else "LandWatch"
        items.extend(extract_from_jsonld(url, json_ld_blocks, source_name))

    # If we still got nothing, do a light HTML fallback
    if not items:
        source_name = "LandSearch" if "landsearch.com" in host else "LandWatch"
        items.extend(extract_from_html_fallback(url, html, source_name))

    # Final pass: fix missing thumbnails with og:image (only for pages where we already fetched HTML for that page)
    # Note: We do NOT fetch each detail page here (keeps it fast + avoids being blocked).
    # App can show placeholder for None thumbnails.

    # Dedup by URL again
    seen = set()
    out = []
    for it in items:
        if it["url"] in seen:
            continue
        seen.add(it["url"])
        out.append(it)

    return out


def in_acres_range(acres: Optional[float]) -> bool:
    return acres is not None and (MIN_ACRES <= acres <= MAX_ACRES)


def in_price_range(price: Optional[int]) -> bool:
    return price is not None and (price <= MAX_PRICE)


def main():
    run_utc = datetime.now(timezone.utc).isoformat()
    all_items: List[Dict[str, Any]] = []

    for url in START_URLS:
        try:
            html = fetch_html(url)
        except Exception as e:
            print(f"Failed to fetch {url}: {e}")
            continue

        items = extract_listings(url, html)
        all_items.extend(items)

    # Final dedup
    seen = set()
    final = []
    for x in all_items:
        if x["url"] in seen:
            continue
        seen.add(x["url"])

        # Optional: add flags your app can use (won't break anything if app ignores them)
        acres = x.get("acres")
        price = x.get("price")

        x["acres_in_range"] = in_acres_range(acres)
        x["price_in_range"] = in_price_range(price)
        x["strict_match"] = x["acres_in_range"] and x["price_in_range"]

        # IMPORTANT: keep even if price is missing/odd; URL filter already removed junk
        final.append(x)

    out = {
        "last_updated_utc": run_utc,
        "criteria": {
            "min_acres": MIN_ACRES,
            "max_acres": MAX_ACRES,
            "min_price": MIN_PRICE,
            "max_price": MAX_PRICE,
        },
        "items": final,
    }

    with open("data/listings.json", "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)

    strict_count = sum(1 for i in final if i.get("strict_match") is True)
    print(f"Saved {len(final)} total listings.")
    print(f"Strict matches: {strict_count}")


if __name__ == "__main__":
    main()