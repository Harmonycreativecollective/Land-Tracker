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

# Treat anything below this as "not a real price" (prevents $3, $8, $12 nonsense)
MIN_REASONABLE_PRICE = 1_000
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


def parse_money(value: Any) -> Optional[int]:
    """
    Parses: 599000, "$599,000", "$599K", "599K", "$1.2M", "From $350K"
    Returns integer dollars or None.
    """
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)

    s = str(value).strip().lower()
    if not s:
        return None

    if "contact" in s or "call" in s or "tbd" in s or "upon request" in s:
        return None

    s = re.sub(r"(from|starting at|starting|approx\.?|about)", "", s).strip()

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


def normalize_url(base_url: str, u: str) -> str:
    if not u:
        return ""
    return urljoin(base_url, u)


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

    # try og:title
    og = soup.find("meta", property="og:title")
    if og and og.get("content"):
        return og["content"].strip()

    # try <title>
    if soup.title and soup.title.string:
        t = soup.title.string.strip()
        if t:
            return t

    return "Land listing"


def is_listing_url(base_url: str, full_url: str) -> bool:
    host = urlparse(base_url).netloc.lower()

    if "landsearch.com" in host:
        return "/properties/" in full_url or "/property/" in full_url
    if "landwatch.com" in host:
        return "/property/" in full_url

    return False


def extract_price_acres_from_jsonld(blocks: List[dict]) -> (Optional[int], Optional[float], Optional[str], Optional[str]):
    price = None
    acres = None
    price_text = None
    acres_text = None

    for block in blocks:
        for d in walk(block):
            if not isinstance(d, dict):
                continue

            # price-ish
            candidate_price = (
                d.get("price")
                or d.get("listPrice")
                or (d.get("offers", {}) or {}).get("price") if isinstance(d.get("offers"), dict) else None
            )
            if price is None and candidate_price is not None:
                price_text = str(candidate_price)
                price = parse_money(candidate_price)

            # acres-ish
            candidate_acres = d.get("acres") or d.get("lotSizeAcres") or d.get("lotSize") or d.get("area")
            if acres is None and candidate_acres is not None:
                acres_text = str(candidate_acres)
                acres = parse_acres(candidate_acres)

            if price is not None and acres is not None:
                return price, acres, price_text, acres_text

    return price, acres, price_text, acres_text


def parse_acres_from_text(text: str) -> Optional[float]:
    t = text.lower()

    m = re.search(r"(\d+(?:\.\d+)?)\s*acres?\b", t)
    if m:
        try:
            return float(m.group(1))
        except Exception:
            return None

    m = re.search(r"acreage\s*[:\-]\s*(\d+(?:\.\d+)?)", t)
    if m:
        try:
            return float(m.group(1))
        except Exception:
            return None

    # "14.2 AC"
    m = re.search(r"(\d+(?:\.\d+)?)\s*(ac\b|a\.c\.)", t)
    if m:
        try:
            return float(m.group(1))
        except Exception:
            return None

    return None


def extract_price_acres_from_page_text(html: str) -> (Optional[int], Optional[float], Optional[str], Optional[str]):
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(" ", strip=True)

    acres = parse_acres_from_text(text)
    acres_text = None if acres is None else f"{acres}"

    price = None
    price_text = None

    # "Price: $599,000"
    m = re.search(r"(price|list price)\s*[:\-]\s*(\$?\s*[\d,]+(?:\.\d+)?)", text.lower())
    if m:
        price_text = m.group(2)
        price = parse_money(price_text)

    # "$599,000" anywhere (require 4+ digits to avoid $3/$12)
    if price is None:
        m = re.search(r"\$\s*([\d,]{4,})", text)
        if m:
            price_text = "$" + m.group(1)
            price = parse_money(price_text)

    # "USD 599,000"
    if price is None:
        m = re.search(r"\busd\s*([\d,]{4,})", text.lower())
        if m:
            price_text = "USD " + m.group(1)
            price = parse_money(price_text)

    return price, acres, price_text, acres_text


def clean_price(price: Optional[int]) -> Optional[int]:
    """Kills wonky tiny prices that are clearly not real listing prices."""
    if price is None:
        return None
    if price < MIN_REASONABLE_PRICE:
        return None
    return price


def get_listing_details(url: str) -> Dict[str, Any]:
    """
    ALWAYS returns a record (even if missing price/acres).
    That’s how we keep 'all 11 no matter what.'
    """
    record: Dict[str, Any] = {
        "title": "Land listing",
        "url": url,
        "price": None,
        "acres": None,
        "price_text": None,
        "acres_text": None,
        "status": "unknown",
    }

    try:
        html = fetch_html(url)
    except Exception as e:
        record["status"] = f"detail_fetch_failed: {e}"
        return record

    record["title"] = best_title_from_ld_or_page(html)

    soup = BeautifulSoup(html, "html.parser")

    # 1) JSON-LD
    blocks = get_json_ld_blocks(html)
    price, acres, ptxt, atxt = extract_price_acres_from_jsonld(blocks)

    # 2) meta tags fallback (LandWatch sometimes)
    if price is None:
        for key in ["property:price:amount", "og:price:amount", "twitter:data1"]:
            tag = soup.find("meta", attrs={"property": key}) or soup.find("meta", attrs={"name": key})
            if tag and tag.get("content"):
                ptxt = tag["content"]
                price = parse_money(ptxt)
                break

    if acres is None:
        for key in ["property:lot_size", "og:lot_size", "twitter:data2"]:
            tag = soup.find("meta", attrs={"property": key}) or soup.find("meta", attrs={"name": key})
            if tag and tag.get("content"):
                atxt = tag["content"]
                acres = parse_acres(atxt)
                break

    # 3) page text fallback
    if price is None or acres is None:
        p2, a2, ptxt2, atxt2 = extract_price_acres_from_page_text(html)
        if price is None and p2 is not None:
            price = p2
            ptxt = ptxt2
        if acres is None and a2 is not None:
            acres = a2
            atxt = atxt2

    price = clean_price(price)

    record["price"] = price
    record["acres"] = acres
    record["price_text"] = ptxt
    record["acres_text"] = atxt

    if price is not None and acres is not None:
        record["status"] = "ok"
    elif acres is not None and price is None:
        record["status"] = "missing_price"
    elif price is not None and acres is None:
        record["status"] = "missing_acres"
    else:
        record["status"] = "missing_price_and_acres"

    return record


def extract_candidate_listing_urls(base_url: str, html: str) -> List[str]:
    soup = BeautifulSoup(html, "html.parser")
    urls = []

    for a in soup.find_all("a", href=True):
        full = normalize_url(base_url, a["href"])
        if is_listing_url(base_url, full):
            urls.append(full)

    # dedup preserving order
    seen = set()
    out = []
    for u in urls:
        if u in seen:
            continue
        seen.add(u)
        out.append(u)
    return out


def passes_filters(price: Optional[int], acres: Optional[float]) -> bool:
    """
    For 'show all 11 no matter what':
    - If acres exists, enforce acreage range
    - If price exists, enforce max price
    - If one is missing, don't reject (we keep it)
    """
    if acres is not None:
        if not (MIN_ACRES <= acres <= MAX_ACRES):
            return False
    if price is not None:
        if price > MAX_PRICE:
            return False
    return True


def main():
    run_utc = datetime.now(timezone.utc).isoformat()
    all_items: List[Dict[str, Any]] = []

    for start_url in START_URLS:
        try:
            html = fetch_html(start_url)
        except Exception as e:
            print(f"Failed to fetch start page {start_url}: {e}")
            continue

        listing_urls = extract_candidate_listing_urls(start_url, html)
        print(f"Found {len(listing_urls)} candidate listing URLs from {start_url}")

        for u in listing_urls:
            detail = get_listing_details(u)

            # Apply filters only to known fields; unknown fields do not eliminate the listing
            if passes_filters(detail.get("price"), detail.get("acres")):
                detail["source"] = "LandSearch" if "landsearch.com" in start_url else "LandWatch"
                all_items.append(detail)

    # Final dedup by url
    seen = set()
    final = []
    for it in all_items:
        if it["url"] in seen:
            continue
        seen.add(it["url"])
        final.append(it)

    out = {
        "last_updated_utc": run_utc,
        "criteria": {
            "min_acres": MIN_ACRES,
            "max_acres": MAX_ACRES,
            "max_price": MAX_PRICE,
            "min_reasonable_price": MIN_REASONABLE_PRICE,
            "note": "Listings with missing price/acres are kept and marked in status.",
        },
        "items": final,
    }

    with open("data/listings.json", "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)

    print(f"Saved {len(final)} listings (including unknown price/acres).")


if __name__ == "__main__":
    main()