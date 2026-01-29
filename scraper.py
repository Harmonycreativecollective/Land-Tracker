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


def parse_money(value: Any) -> Optional[int]:
    """
    Parses prices like:
      599000, "$599,000", "$599K", "599K", "$1.2M", "From $350K", "$9", etc.
    Returns integer dollars.
    """
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)

    s = str(value).strip().lower()
    if not s:
        return None

    if "contact" in s or "call" in s or "tbd" in s:
        return None

    s = re.sub(r"(from|starting at|starting|approx\.?|about)", "", s).strip()

    # Grab first number + optional suffix
    m = re.search(r"(\d+(?:\.\d+)?)\s*([km])?\b", s.replace(",", ""))
    if not m:
        return None

    num = float(m.group(1))
    suffix = m.group(2)

    if suffix == "k":
        num *= 1000
    elif suffix == "m":
        num *= 1_000_000

    return int(num)


def parse_acres(value: Any) -> Optional[float]:
    """
    Parses acres from:
      14.2, "14.2 acres", dicts, sqft conversions, etc.
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

        try:
            vnum = float(str(val).replace(",", "").strip()) if val is not None else None
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


def passes(price: Optional[int], acres: Optional[float]) -> bool:
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


def normalize_url(base_url: str, u: str) -> str:
    if not u:
        return ""
    return urljoin(base_url, u)


def best_title(d: dict) -> str:
    return (d.get("title") or d.get("name") or d.get("headline") or "Land listing").strip()


def looks_like_property_url(url: str, base_url: str) -> bool:
    if not url:
        return False
    u = url.lower()
    host = urlparse(base_url).netloc.lower()

    if "landsearch.com" in host:
        # be forgiving
        return ("/properties/" in u) or ("/property/" in u) or ("/listing/" in u)

    if "landwatch.com" in host:
        return "/property/" in u

    # fallback
    return "property" in u


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
            or ""
        )
        url = normalize_url(base_url, str(raw_url)) if raw_url else ""

        if not url:
            for k in ["permalink", "detailUrl", "detailURL", "propertyUrl", "propertyURL"]:
                if d.get(k):
                    url = normalize_url(base_url, str(d.get(k)))
                    break

        if url and not looks_like_property_url(url, base_url):
            # still might be a real listing, but we skip obvious non-property links
            continue

        price = parse_money(
            d.get("price")
            or d.get("listPrice")
            or d.get("priceValue")
            or d.get("amount")
            or (d.get("offers", {}) or {}).get("price") if isinstance(d.get("offers"), dict) else None
            or (d.get("pricing", {}) or {}).get("price") if isinstance(d.get("pricing"), dict) else None
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

        if url:
            items.append(
                {
                    "source": "LandSearch (NEXT_DATA)",
                    "title": best_title(d),
                    "url": url,
                    "price": price,
                    "acres": acres,
                    "matches": passes(price, acres),
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


def extract_from_jsonld(base_url: str, blocks: List[dict], source_name: str) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for block in blocks:
        for d in walk(block):
            if not isinstance(d, dict):
                continue

            raw_url = d.get("url") or d.get("mainEntityOfPage") or d.get("sameAs") or ""
            url = normalize_url(base_url, str(raw_url)) if raw_url else ""

            if url and not looks_like_property_url(url, base_url):
                continue

            title = best_title(d)

            price = parse_money(
                d.get("price")
                or d.get("listPrice")
                or (d.get("offers", {}) or {}).get("price") if isinstance(d.get("offers"), dict) else None
            )

            acres = parse_acres(
                d.get("acres")
                or d.get("lotSize")
                or d.get("lotSizeAcres")
                or d.get("size")
                or d.get("area")
            )

            if url:
                items.append(
                    {
                        "source": f"{source_name} (JSON-LD)",
                        "title": title or "Land listing",
                        "url": url,
                        "price": price,
                        "acres": acres,
                        "matches": passes(price, acres),
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

    links = soup.find_all("a", href=True)
    for a in links:
        href = a["href"]
        full = normalize_url(base_url, href)

        if not looks_like_property_url(full, base_url):
            continue

        card_text = a.get_text(" ", strip=True)
        parent = a.parent
        for _ in range(4):
            if parent is None:
                break
            card_text = (parent.get_text(" ", strip=True) or card_text)
            parent = parent.parent

        price = parse_money(card_text)
        acres = None
        m = re.search(r"(\d+(?:\.\d+)?)\s*acres?\b", card_text.lower())
        if m:
            acres = float(m.group(1))

        items.append(
            {
                "source": f"{source_name} (HTML)",
                "title": a.get_text(" ", strip=True) or "Land listing",
                "url": full,
                "price": price,
                "acres": acres,
                "matches": passes(price, acres),
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

    print(f"Saved {len(final)} listings (including non-matching).")
    print(f"Matches (strict): {sum(1 for i in final if i.get('matches'))}")


if __name__ == "__main__":
    main()