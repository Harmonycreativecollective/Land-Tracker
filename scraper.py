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


def parse_money(value: Any) -> Optional[int]:
    """
    Robust price parser:
    - Handles: 599000, "$599,000", "$599K", "599K", "$1.2M", "From $350K"
    - Returns integer dollars or None
    """
    if value is None:
        return None

    if isinstance(value, (int, float)):
        return int(value)

    s = str(value).strip().lower()
    if not s:
        return None

    # common non-prices
    if ("contact" in s) or ("call" in s) or ("tbd" in s) or ("auction" in s):
        return None

    # remove fluff words
    s = re.sub(r"(from|starting at|starting|approx\.?|about)", "", s).strip()

    # extract number + optional K/M
    s_clean = s.replace(",", "")
    m = re.search(r"(\d+(?:\.\d+)?)\s*([km])?\b", s_clean)
    if not m:
        return None

    num = float(m.group(1))
    suffix = m.group(2)

    if suffix == "k":
        num *= 1000
    elif suffix == "m":
        num *= 1_000_000

    # guard against absurd tiny values (like "$3" that are actually "$300k" missing suffix)
    # we keep it though — because you said “I want all 11 no matter what”
    return int(num)


def parse_acres(value: Any) -> Optional[float]:
    if value is None:
        return None

    if isinstance(value, (int, float)):
        return float(value)

    if isinstance(value, dict):
        for k in [
            "acres", "acreage", "lotSizeAcres", "lotSize_acres",
            "sizeAcres", "size_acres"
        ]:
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

        if ("acr" in unit) or ("acre" in unit):
            return float(vnum)

        if ("sq" in unit) or ("ft" in unit):
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

    if ("sq" in s) and (("ft" in s) or ("feet" in s)):
        return num / 43560.0

    if num > 5000:
        return num / 43560.0

    return num


def matches_filters(price: Optional[int], acres: Optional[float]) -> bool:
    """
    Strict match:
    - only True if both price and acres exist AND fit your filters
    """
    if price is None or acres is None:
        return False
    return (MIN_ACRES <= acres <= MAX_ACRES) and (price <= MAX_PRICE)


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


def best_title(d: dict) -> str:
    return (d.get("title") or d.get("name") or d.get("headline") or "Land listing").strip()


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
            or d.get("detailUrl")
            or d.get("propertyUrl")
            or ""
        )
        url = normalize_url(base_url, str(raw_url)) if raw_url else ""

        price_raw = (
            d.get("price")
            or d.get("listPrice")
            or d.get("priceValue")
            or d.get("amount")
            or (d.get("offers", {}) or {}).get("price") if isinstance(d.get("offers"), dict) else None
            or (d.get("pricing", {}) or {}).get("price") if isinstance(d.get("pricing"), dict) else None
        )
        acres_raw = (
            d.get("acres")
            or d.get("acreage")
            or d.get("lotSizeAcres")
            or d.get("sizeAcres")
            or d.get("lotSize")
            or d.get("size")
            or d.get("area")
            or d.get("landSize")
        )

        price = parse_money(price_raw)
        acres = parse_acres(acres_raw)

        # keep EVERYTHING that has a property-ish url, even if price/acres are weird
        if url and ("landsearch.com" in url) and (("/properties/" in url) or ("/property/" in url)):
            items.append(
                {
                    "source": "LandSearch",
                    "title": best_title(d),
                    "url": url,
                    "price": price,
                    "acres": acres,
                    "raw_price": None if price_raw is None else str(price_raw),
                    "raw_acres": None if acres_raw is None else str(acres_raw),
                    "matches": matches_filters(price, acres),
                }
            )

    return dedup(items)


def extract_from_jsonld(base_url: str, blocks: List[dict], source_name: str) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []

    for block in blocks:
        for d in walk(block):
            if not isinstance(d, dict):
                continue

            raw_url = d.get("url") or d.get("mainEntityOfPage") or d.get("sameAs") or ""
            url = normalize_url(base_url, str(raw_url)) if raw_url else ""

            price_raw = (
                d.get("price")
                or d.get("listPrice")
                or (d.get("offers", {}) or {}).get("price") if isinstance(d.get("offers"), dict) else None
            )
            acres_raw = d.get("acres") or d.get("lotSize") or d.get("lotSizeAcres") or d.get("size") or d.get("area")

            price = parse_money(price_raw)
            acres = parse_acres(acres_raw)

            # Keep if it looks like a property link for that site
            if url:
                host = urlparse(base_url).netloc.lower()
                if ("landsearch.com" in host and ("/properties/" in url or "/property/" in url)) or (
                    "landwatch.com" in host and "/property/" in url
                ):
                    items.append(
                        {
                            "source": source_name,
                            "title": best_title(d),
                            "url": url,
                            "price": price,
                            "acres": acres,
                            "raw_price": None if price_raw is None else str(price_raw),
                            "raw_acres": None if acres_raw is None else str(acres_raw),
                            "matches": matches_filters(price, acres),
                        }
                    )

    return dedup(items)


def extract_from_html_fallback(base_url: str, html: str, source_name: str) -> List[Dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    items: List[Dict[str, Any]] = []

    host = urlparse(base_url).netloc.lower()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        full = normalize_url(base_url, href)

        if "landsearch.com" in host:
            if "/properties/" not in full and "/property/" not in full:
                continue
        if "landwatch.com" in host:
            if "/property/" not in full:
                continue

        card_text = a.get_text(" ", strip=True)
        parent = a.parent
        for _ in range(4):
            if parent is None:
                break
            card_text = parent.get_text(" ", strip=True) or card_text
            parent = parent.parent

        price = parse_money(card_text)

        acres = None
        m = re.search(r"(\d+(?:\.\d+)?)\s*acres?\b", card_text.lower())
        if m:
            acres = float(m.group(1))

        items.append(
            {
                "source": source_name,
                "title": a.get_text(" ", strip=True) or "Land listing",
                "url": full,
                "price": price,
                "acres": acres,
                "raw_price": card_text[:200],
                "raw_acres": card_text[:200],
                "matches": matches_filters(price, acres),
            }
        )

    return dedup(items)


def dedup(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    out = []
    for it in items:
        u = it.get("url")
        if not u or u in seen:
            continue
        seen.add(u)
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
        src = "LandSearch" if "landsearch.com" in host else "LandWatch"
        items.extend(extract_from_jsonld(url, json_ld_blocks, src))

    # always try fallback too (because you want ALL listings)
    fallback_src = "LandSearch (HTML)" if "landsearch.com" in host else "LandWatch (HTML)"
    items.extend(extract_from_html_fallback(url, html, fallback_src))

    return dedup(items)


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

    final = dedup(all_items)

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

    total = len(final)
    matched = sum(1 for x in final if x.get("matches"))
    print(f"Saved {total} listings total. ({matched} match your filters.)")


if __name__ == "__main__":
    main()