import json
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse, urlunparse, parse_qsl, urlencode

import requests
from bs4 import BeautifulSoup

# ============================================================
# SETTINGS (edit these)
# ============================================================

START_URLS = [
    # -------- LandSearch (results pages) --------
    "https://www.landsearch.com/properties/king-george-va",
    "https://www.landsearch.com/properties/westmoreland-county-va",
    "https://www.landsearch.com/properties/caroline-county-va",
    "https://www.landsearch.com/properties/stafford-county-va",
    "https://www.landsearch.com/properties/frederick-county-md",
    "https://www.landsearch.com/properties/anne-arundel-county-md",

    # -------- LandWatch (results pages) --------
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

DETAIL_ENRICH_LIMIT = 20  # how many listing pages to open to improve title/thumb/status
DATA_FILE = "data/listings.json"

# ============================================================
# HTTP
# ============================================================

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

TIMEOUT = 40

session = requests.Session()
session.headers.update(HEADERS)

# ============================================================
# Utilities
# ============================================================

BAD_TITLE_SET = {
    "",
    "land listing",
    "skip to navigation",
    "skip to content",
    "skip to main content",
    "listing",
    "properties",
    "log in",
    "sign up",
    "find agent",
    "post listing",
}

TRACKING_QUERY_KEYS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "fbclid", "gclid", "msclkid"
}

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
            stack.extend(cur)

def normalize_url(base_url: str, u: str) -> str:
    if not u:
        return ""
    return urljoin(base_url, u)

def canonicalize_url(u: str) -> str:
    """
    - Drop fragments
    - Remove tracking query params
    - Keep other query params (some sites use them for the actual listing)
    """
    try:
        p = urlparse(u)
        query = [(k, v) for (k, v) in parse_qsl(p.query, keep_blank_values=True) if k not in TRACKING_QUERY_KEYS]
        new_query = urlencode(query, doseq=True)
        clean = urlunparse((p.scheme, p.netloc, p.path, p.params, new_query, ""))  # fragment removed
        return clean
    except Exception:
        return u

def slug_to_title(s: str) -> str:
    s = s.strip().replace("-", " ")
    return " ".join(w.capitalize() for w in s.split())

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

def parse_money(value: Any) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        v = int(value)
        return v if v >= 1000 else None

    s = str(value).strip().lower()
    if not s:
        return None
    if any(x in s for x in ["contact", "call", "tbd", "request", "auction"]):
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
        # common keys
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

# ============================================================
# Area parsing from START_URL (so app can filter by state/county)
# ============================================================

def infer_area_from_start_url(start_url: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Returns (state, county) like ("VA", "King George") if we can infer it.
    """
    u = start_url.lower()

    # LandSearch: .../properties/king-george-va
    if "landsearch.com" in u and "/properties/" in u:
        slug = u.split("/properties/")[-1].strip("/")

        # examples: king-george-va, westmoreland-county-va, frederick-county-md
        m = re.search(r"(.+?)-(va|md)$", slug)
        if m:
            county_slug = m.group(1)
            st = m.group(2).upper()
            county = slug_to_title(county_slug.replace("-county", ""))
            return st, county

    # LandWatch: .../virginia-land-for-sale/king-george
    if "landwatch.com" in u and "-land-for-sale/" in u:
        # state comes from /virginia-land-for-sale/ or /maryland-land-for-sale/
        st = None
        if "/virginia-land-for-sale/" in u:
            st = "VA"
            county_slug = u.split("/virginia-land-for-sale/")[-1].strip("/")
        elif "/maryland-land-for-sale/" in u:
            st = "MD"
            county_slug = u.split("/maryland-land-for-sale/")[-1].strip("/")
        else:
            county_slug = None

        if st and county_slug:
            county = slug_to_title(county_slug.replace("-county", ""))
            return st, county

    return None, None

# ============================================================
# Valid listing URL rules (THIS is the big fix)
# ============================================================

def is_landsearch_listing_url(u: str) -> bool:
    """
    LandSearch listing pattern:
    https://www.landsearch.com/properties/<stuff>/<ID>
    where last segment is digits.
    """
    try:
        p = urlparse(u)
        if "landsearch.com" not in p.netloc:
            return False
        parts = p.path.strip("/").split("/")
        return len(parts) >= 3 and parts[0] == "properties" and parts[-1].isdigit()
    except Exception:
        return False

def is_landwatch_listing_url(u: str) -> bool:
    """
    LandWatch listing pattern usually contains /property/<ID> somewhere.
    """
    try:
        p = urlparse(u)
        if "landwatch.com" not in p.netloc:
            return False
        return "/property/" in p.path
    except Exception:
        return False

def is_valid_listing_url(base_url: str, u: str) -> bool:
    host = urlparse(base_url).netloc.lower()
    if "landsearch.com" in host:
        return is_landsearch_listing_url(u)
    if "landwatch.com" in host:
        return is_landwatch_listing_url(u)
    return False

# ============================================================
# JSON extraction helpers
# ============================================================

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

# ============================================================
# Status detection (conservative)
# ============================================================

STATUS_KEYWORDS = [
    ("sold", ["sold"]),
    ("pending", ["pending"]),
    ("under_contract", ["under contract", "under-contract"]),
]

def detect_status_from_html(html: str) -> str:
    text = BeautifulSoup(html, "html.parser").get_text(" ", strip=True).lower()

    # A tiny guard: ignore matches on login / nav pages by requiring listing-ish words too
    # (prevents “pending” on random site chrome from poisoning status)
    listing_hint = any(x in text for x in ["acres", "property", "listing", "price", "lot"])
    if not listing_hint:
        return "unknown"

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

    def meta(key: str, attr: str = "property") -> str:
        tag = soup.find("meta", attrs={attr: key})
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

def should_enrich(it: Dict[str, Any]) -> bool:
    return is_bad_title(it.get("title")) or (not it.get("thumbnail")) or ((it.get("status") or "unknown") == "unknown")

# ============================================================
# Match logic (scraper-side: sticky ever_top_match)
# ============================================================

def meets_acres_val(acres: Optional[float]) -> bool:
    if acres is None:
        return False
    try:
        a = float(acres)
        return MIN_ACRES <= a <= MAX_ACRES
    except Exception:
        return False

def meets_price_val(price: Optional[int]) -> bool:
    if price is None:
        return False
    try:
        return int(price) <= int(MAX_PRICE)
    except Exception:
        return False

def is_current_top_match(item: Dict[str, Any]) -> bool:
    status = (item.get("status") or "unknown").strip().lower()
    if status in {"under_contract", "pending", "sold"}:
        return False
    return meets_acres_val(item.get("acres")) and meets_price_val(item.get("price"))

# ============================================================
# Extractors
# ============================================================

def extract_from_landsearch_next(base_url: str, next_data: dict, state: Optional[str], county: Optional[str]) -> List[Dict[str, Any]]:
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
        if not raw_url:
            continue

        url = canonicalize_url(normalize_url(base_url, str(raw_url)))
        if not url or not is_landsearch_listing_url(url):
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
                "state": state,
                "county": county,
            }
        )

    # dedupe
    seen = set()
    out = []
    for it in items:
        u = it["url"]
        if u in seen:
            continue
        seen.add(u)
        out.append(it)
    return out

def extract_from_landwatch_links(base_url: str, html: str, state: Optional[str], county: Optional[str]) -> List[Dict[str, Any]]:
    """
    LandWatch pages: easiest reliable method is to collect anchor tags that contain /property/
    """
    soup = BeautifulSoup(html, "html.parser")
    items: List[Dict[str, Any]] = []

    for a in soup.find_all("a", href=True):
        href = a["href"]
        full = canonicalize_url(normalize_url(base_url, href))
        if not full or not is_landwatch_listing_url(full):
            continue

        # Try pull some text around the link as a crude title
        raw_title = a.get_text(" ", strip=True)
        title = raw_title if not is_bad_title(raw_title) else "LandWatch listing"

        # Price/acres might be in nearby card text; this is a best-effort
        card_text = a.get_text(" ", strip=True) or ""
        price = parse_money(card_text)
        acres = None
        m = re.search(r"(\d+(?:\.\d+)?)\s*acres?\b", card_text.lower())
        if m:
            acres = float(m.group(1))

        # thumbnail sometimes in img
        img = a.find("img")
        thumb = img.get("src") if img and img.get("src") else None
        if thumb:
            thumb = canonicalize_url(normalize_url(base_url, thumb))

        items.append(
            {
                "source": "LandWatch",
                "title": title,
                "url": full,
                "price": price,
                "acres": acres,
                "thumbnail": thumb,
                "status": "unknown",
                "state": state,
                "county": county,
            }
        )

    # dedupe
    seen = set()
    out = []
    for it in items:
        u = it["url"]
        if u in seen:
            continue
        seen.add(u)
        out.append(it)
    return out

def extract_listings(start_url: str, html: str, state: Optional[str], county: Optional[str]) -> List[Dict[str, Any]]:
    host = urlparse(start_url).netloc.lower()

    items: List[Dict[str, Any]] = []

    if "landsearch.com" in host:
        next_data = get_next_data_json(html)
        if next_data:
            items.extend(extract_from_landsearch_next(start_url, next_data, state, county))

        # extra safety: do NOT use generic JSON-LD / fallback on LandSearch results pages
        # because it tends to capture nav URLs like /login, /properties, homepage, etc.

    elif "landwatch.com" in host:
        items.extend(extract_from_landwatch_links(start_url, html, state, county))

        # optional: also parse JSON-LD if present, but still enforce valid listing urls
        for block in get_json_ld(html):
            for d in walk(block):
                if not isinstance(d, dict):
                    continue
                raw_url = d.get("url") or d.get("mainEntityOfPage") or d.get("sameAs") or ""
                if not raw_url:
                    continue
                url = canonicalize_url(normalize_url(start_url, str(raw_url)))
                if not is_landwatch_listing_url(url):
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
                        "source": "LandWatch",
                        "title": best_title(d, "LandWatch"),
                        "url": url,
                        "price": price,
                        "acres": acres,
                        "thumbnail": thumb,
                        "status": "unknown",
                        "state": state,
                        "county": county,
                    }
                )

    # final dedupe
    seen = set()
    out = []
    for it in items:
        u = it.get("url") or ""
        if not u:
            continue
        if u in seen:
            continue
        seen.add(u)
        out.append(it)
    return out

# ============================================================
# Persistence across runs
# ============================================================

def load_existing_maps() -> Dict[str, Dict[str, Any]]:
    """
    Per-URL fields we want to keep stable across runs:
    - found_utc
    - status (if we previously detected something real)
    - ever_top_match (sticky)
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

# ============================================================
# Main
# ============================================================

def main():
    os.makedirs("data", exist_ok=True)

    run_utc = datetime.now(timezone.utc).isoformat()
    old_map = load_existing_maps()

    all_items: List[Dict[str, Any]] = []

    for start_url in START_URLS:
        state, county = infer_area_from_start_url(start_url)

        try:
            html = fetch_html(start_url)
        except Exception as e:
            print(f"Failed to fetch {start_url}: {e}")
            continue

        extracted = extract_listings(start_url, html, state, county)
        all_items.extend(extracted)

    # Dedupe across sources by URL (canonical)
    seen = set()
    final: List[Dict[str, Any]] = []

    for x in all_items:
        u = x.get("url")
        if not u:
            continue
        u = canonicalize_url(u)

        # One last “trash guard”
        base_host = (x.get("source") or "").lower()
        if base_host == "landsearch" and not is_landsearch_listing_url(u):
            continue
        if base_host == "landwatch" and not is_landwatch_listing_url(u):
            continue

        if u in seen:
            continue
        seen.add(u)
        x["url"] = u

        prev = old_map.get(u, {})

        # Persist found_utc (first seen)
        if prev.get("found_utc"):
            x["found_utc"] = prev["found_utc"]
        else:
            x["found_utc"] = run_utc

        # Persist status if previous was better than unknown
        prev_status = (prev.get("status") or "unknown").strip().lower()
        cur_status = (x.get("status") or "unknown").strip().lower()
        if prev_status != "unknown" and cur_status == "unknown":
            x["status"] = prev_status

        # Clean garbage titles
        if is_bad_title(x.get("title")):
            x["title"] = f"{x.get('source','Listing')} listing"

        # Sticky ever_top_match
        prev_ever = bool(prev.get("ever_top_match", False))
        cur_top = is_current_top_match(x)
        x["ever_top_match"] = prev_ever or cur_top

        final.append(x)

    # Enrichment pass (limited)
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
