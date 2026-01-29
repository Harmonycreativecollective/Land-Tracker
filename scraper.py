import json
import re
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set
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

# safety/anti-rate-limit
MAX_LISTINGS_TO_CHECK_PER_SOURCE = 80  # increase if you want
REQUEST_DELAY_SECONDS = 0.35
# ===========================

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}
TIMEOUT = 40


# ---------------- Helpers ----------------

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
    Parses prices like:
      599000, "$599,000", "$599K", "599K", "$1.2M", "From $350K"
    Returns integer dollars.
    """
    if value is None:
        return None

    if isinstance(value, (int, float)):
        p = int(value)
        return p if p >= 1000 else None

    s = str(value).strip().lower()
    if not s:
        return None

    if any(w in s for w in ["contact", "call", "tbd", "auction", "bid"]):
        return None

    s = re.sub(r"(from|starting at|starting|approx\.?|about)", "", s).strip()

    # must have at least a $ or a K/M suffix OR the word price nearby
    if ("$" not in s) and (re.search(r"\b\d+(\.\d+)?\s*[km]\b", s) is None) and ("price" not in s):
        return None

    m = re.search(r"(\d+(?:\.\d+)?)\s*([km])?\b", s.replace(",", ""))
    if not m:
        return None

    num = float(m.group(1))
    suf = m.group(2)

    if suf == "k":
        num *= 1000
    elif suf == "m":
        num *= 1_000_000

    p = int(num)
    return p if p >= 1000 else None


def parse_acres_from_text(text: str) -> Optional[float]:
    if not text:
        return None
    t = text.lower().replace(",", "")
    m = re.search(r"(\d+(?:\.\d+)?)\s*acres?\b", t)
    if m:
        try:
            return float(m.group(1))
        except Exception:
            return None
    return None


def parse_acres(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)

    if isinstance(value, dict):
        for k in ["acres", "acreage", "lotSizeAcres", "sizeAcres", "landSizeAcres"]:
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
            return float(vnum)

        # sqft -> acres
        if "sq" in unit or "ft" in unit:
            return float(vnum) / 43560.0

        if vnum > 5000:
            return float(vnum) / 43560.0

        return float(vnum)

    s = str(value).strip()
    return parse_acres_from_text(s)


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


def get_json_ld_blocks(html: str) -> List[dict]:
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


def best_title_from_ld_or_page(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    if soup.title and soup.title.string:
        return soup.title.string.strip()
    h1 = soup.find(["h1"])
    if h1:
        txt = h1.get_text(" ", strip=True)
        if txt:
            return txt
    return "Land listing"


# ---------------- Step 1: Collect listing URLs from search pages ----------------

def collect_listing_urls_from_landsearch(search_url: str, html: str) -> List[str]:
    urls: Set[str] = set()
    next_data = get_next_data_json(html)

    if next_data:
        for d in walk(next_data):
            if not isinstance(d, dict):
                continue
            raw = d.get("href") or d.get("url") or d.get("canonicalUrl") or d.get("permalink")
            if not raw:
                continue
            u = normalize_url(search_url, str(raw))
            # keep property detail pages
            if "landsearch.com" in u and ("/properties/" in u or "/property/" in u):
                urls.add(u)

    # HTML backup for links
    soup = BeautifulSoup(html, "html.parser")
    for a in soup.find_all("a", href=True):
        u = normalize_url(search_url, a["href"])
        if "landsearch.com" in u and ("/properties/" in u or "/property/" in u):
            urls.add(u)

    return sorted(urls)


def collect_listing_urls_from_landwatch(search_url: str, html: str) -> List[str]:
    urls: Set[str] = set()
    soup = BeautifulSoup(html, "html.parser")
    for a in soup.find_all("a", href=True):
        u = normalize_url(search_url, a["href"])
        if "landwatch.com" in u and "/property/" in u:
            urls.add(u)
    return sorted(urls)


def collect_listing_urls(search_url: str, html: str) -> List[str]:
    host = urlparse(search_url).netloc.lower()
    if "landsearch.com" in host:
        return collect_listing_urls_from_landsearch(search_url, html)
    if "landwatch.com" in host:
        return collect_listing_urls_from_landwatch(search_url, html)
    return []


# ---------------- Step 2: Fetch listing detail pages & extract price/acres correctly ----------------

def extract_price_acres_from_jsonld(blocks: List[dict]) -> (Optional[int], Optional[float]):
    """
    Try to find price + acres from any JSON-LD block.
    """
    price = None
    acres = None

    for block in blocks:
        for d in walk(block):
            if not isinstance(d, dict):
                continue

            # PRICE:
            if price is None:
                # common: offers.price
                offers = d.get("offers")
                if isinstance(offers, dict):
                    price = parse_money(offers.get("price"))

                # sometimes a direct price field exists
                if price is None:
                    price = parse_money(d.get("price") or d.get("listPrice"))

            # ACRES:
            if acres is None:
                acres = parse_acres(
                    d.get("acres")
                    or d.get("acreage")
                    or d.get("lotSizeAcres")
                    or d.get("landSizeAcres")
                    or d.get("lotSize")
                    or d.get("landSize")
                    or d.get("size")
                    or d.get("area")
                )

            if price is not None and acres is not None:
                return price, acres

    return price, acres


def extract_price_acres_from_page_text(html: str) -> (Optional[int], Optional[float]):
    """
    Fallback: look for '$123,456' + '12.3 acres' in visible text.
    """
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(" ", strip=True)

    acres = parse_acres_from_text(text)

    # Try to locate a $price in text
    price = None
    m = re.search(r"\$\s*([\d,]+)", text)
    if m:
        price = parse_money("$" + m.group(1))

    return price, acres


def get_listing_details(url: str) -> Optional[Dict[str, Any]]:
    """
    Fetch detail page and extract price/acres/title reliably.
    """
    try:
        html = fetch_html(url)
    except Exception as e:
        print(f"Failed detail fetch: {url} -> {e}")
        return None

    blocks = get_json_ld_blocks(html)
    price, acres = extract_price_acres_from_jsonld(blocks)

    if price is None or acres is None:
        p2, a2 = extract_price_acres_from_page_text(html)
        price = price if price is not None else p2
        acres = acres if acres is not None else a2

    title = best_title_from_ld_or_page(html)

    if price is None or acres is None:
        # still can’t validate—skip so we don’t save junk
        return None

    return {
        "title": title,
        "url": url,
        "price": price,
        "acres": acres,
    }


# ---------------- Main ----------------

def main():
    run_utc = datetime.now(timezone.utc).isoformat()

    all_matches: List[Dict[str, Any]] = []
    seen_detail_urls: Set[str] = set()

    for search_url in START_URLS:
        try:
            search_html = fetch_html(search_url)
        except Exception as e:
            print(f"Failed to fetch search page {search_url}: {e}")
            continue

        host = urlparse(search_url).netloc.lower()
        source_name = "LandSearch" if "landsearch.com" in host else ("LandWatch" if "landwatch.com" in host else host)

        candidate_urls = collect_listing_urls(search_url, search_html)
        if not candidate_urls:
            print(f"{source_name}: No candidate listing URLs found on search page.")
            continue

        # limit to reduce requests
        candidate_urls = candidate_urls[:MAX_LISTINGS_TO_CHECK_PER_SOURCE]
        print(f"{source_name}: Checking up to {len(candidate_urls)} listing detail pages...")

        for detail_url in candidate_urls:
            if detail_url in seen_detail_urls:
                continue
            seen_detail_urls.add(detail_url)

            time.sleep(REQUEST_DELAY_SECONDS)

            details = get_listing_details(detail_url)
            if not details:
                continue

            price = details["price"]
            acres = details["acres"]

            if passes(price, acres):
                all_matches.append(
                    {
                        "source": source_name,
                        "title": details["title"],
                        "url": details["url"],
                        "price": price,
                        "acres": acres,
                    }
                )

    # Final dedup by URL
    out_items = []
    seen = set()
    for x in all_matches:
        if x["url"] in seen:
            continue
        seen.add(x["url"])
        out_items.append(x)

    out = {
        "last_updated_utc": run_utc,
        "criteria": {
            "min_acres": MIN_ACRES,
            "max_acres": MAX_ACRES,
            "max_price": MAX_PRICE,
        },
        "items": out_items,
    }

    with open("data/listings.json", "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)

    print(f"Saved {len(out_items)} matches.")


if __name__ == "__main__":
    main()
