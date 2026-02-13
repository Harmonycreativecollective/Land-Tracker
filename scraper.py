import json
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

# ====== YOUR SETTINGS ======
START_URLS = [
    # ---- LandSearch (county pages, NO filters) ----
    "https://www.landsearch.com/properties/king-george-va",
    "https://www.landsearch.com/properties/westmoreland-county-va",
    "https://www.landsearch.com/properties/stafford-county-va",
    "https://www.landsearch.com/properties/caroline-county-va",
    "https://www.landsearch.com/properties/frederick-county-md",
    "https://www.landsearch.com/properties/anne-arundel-county-md",
]

MIN_ACRES = 10.0
MAX_ACRES = 50.0
MAX_PRICE = 600_000

# Enrich missing titles/thumbs/status/price by visiting a few detail pages
DETAIL_ENRICH_LIMIT = 80
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

BAD_TITLE_SET = {
    "",
    "land listing",
    "skip to navigation",
    "skip to content",
    "listing",
    "landsearch listing",
    "landwatch listing",
}

STATUS_VALUES = {"available", "under_contract", "pending", "sold", "unknown"}

LEASE_KEYWORDS = {
    "lease",
    "for lease",
    "leasing",
    "rent",
    "rental",
    "ground lease",
    "land lease",
    "annual lease",
}


def is_lease_listing(it: Dict[str, Any]) -> bool:
    t = (it.get("title") or "").lower()
    u = (it.get("url") or "").lower()
    return any(kw in t or kw in u for kw in LEASE_KEYWORDS)


# ------------------- Fetch -------------------
def fetch_html(url: str) -> str:
    r = session.get(url, timeout=TIMEOUT)
    r.raise_for_status()
    return r.text


# ------------------- Walk JSON -------------------
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


# ------------------- Parsers -------------------
def parse_money(value: Any) -> Optional[int]:
    if value is None:
        return None

    if isinstance(value, (int, float)):
        v = int(value)
        return v if v >= 1000 else None

    s = str(value).strip().lower()
    if not s:
        return None

    if any(x in s for x in ["contact", "call", "tbd"]):
        return None

    s = s.replace(",", "")

    candidates: List[int] = []
    for m in re.finditer(r"(\d+(?:\.\d+)?)\s*([km])?\b", s):
        num = float(m.group(1))
        suffix = m.group(2)
        if suffix == "k":
            num *= 1000
        elif suffix == "m":
            num *= 1_000_000
        v = int(num)
        if v < 1000:
            continue
        candidates.append(v)

    if not candidates:
        return None

    return max(candidates)


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


# ------------------- Status detection (STRICT) -------------------
def detect_status(text: str) -> str:
    t = (text or "").lower()

    if re.search(r"\bsold\b", t):
        return "sold"
    if re.search(r"\bunder\s+contract\b", t):
        return "under_contract"
    if re.search(r"\bpending\b", t):
        return "pending"
    if re.search(r"\bavailable\b", t) or re.search(r"\bfor\s+sale\b", t) or re.search(r"\bactive\b", t):
        return "available"

    return "unknown"


# ------------------- Helpers -------------------
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
    out: List[dict] = []
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


def is_bad_title(title: Optional[str]) -> bool:
    t = (title or "").strip().lower()
    if t in BAD_TITLE_SET:
        return True
    if t.endswith(" listing"):
        return True
    return False


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
    return (
        is_bad_title(it.get("title"))
        or (not it.get("thumbnail"))
        or (it.get("status") in (None, "", "unknown"))
        or (it.get("price") is None)
        or (it.get("acres") is None)
    )


# ------------------- Matching logic (for ever_top_match) -------------------
def is_top_match_now(it: Dict[str, Any], min_a: float, max_a: float, max_p: int) -> bool:
    try:
        acres = it.get("acres")
        price = it.get("price")
        status = (it.get("status") or "unknown").lower()
        if status in {"under_contract", "pending", "sold"}:
            return False
        if acres is None or price is None:
            return False
        return (min_a <= float(acres) <= max_a) and (int(price) <= int(max_p))
    except Exception:
        return False


# ------------------- Detail enrichment -------------------
def enrich_from_detail_page(url: str) -> Dict[str, Any]:
    try:
        html = fetch_html(url)
    except Exception:
        return {"title": None, "thumbnail": None, "status": None, "price": None, "acres": None}

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

    status_text = " ".join(
        [
            meta("og:description", "property"),
            meta("twitter:description", "name"),
            soup.get_text(" ", strip=True)[:20000],
        ]
    )
    status = detect_status(status_text)

    price = None
    acres = None
    for block in get_json_ld(html):
        for d in walk(block):
            if not isinstance(d, dict):
                continue

            offers = d.get("offers")
            if isinstance(offers, dict):
                p = parse_money(offers.get("price"))
                if p is not None:
                    price = price or p

            p2 = parse_money(d.get("price") or d.get("listPrice"))
            if p2 is not None:
                price = price or p2

            a2 = parse_acres(
                d.get("acres")
                or d.get("lotSizeAcres")
                or d.get("lotSize")
                or d.get("size")
                or d.get("area")
            )
            if a2 is not None:
                acres = acres or a2

    if title:
        title = " ".join(title.split()).strip()
    if is_bad_title(title):
        title = None

    return {"title": title, "thumbnail": thumb or None, "status": status or None, "price": price, "acres": acres}


# ------------------- Extractors -------------------
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
        if not url:
            continue

        if "landsearch.com" in url:
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
        if it["url"] in seen:
            continue
        seen.add(it["url"])
        out.append(it)
    return out


def extract_from_jsonld(base_url: str, blocks: List[dict], source_name: str) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    host = urlparse(base_url).netloc.lower()

    for block in blocks:
        for d in walk(block):
            if not isinstance(d, dict):
                continue

            raw_url = d.get("url") or d.get("mainEntityOfPage") or d.get("sameAs") or ""
            if not raw_url:
                continue

            url = normalize_url(base_url, str(raw_url))
            if not url:
                continue

            # If we're on LandSearch, enforce property detail URL shape
            if "landsearch.com" in host:
                p = urlparse(url)
                if p.fragment:
                    continue
                parts = p.path.strip("/").split("/")
                if len(parts) < 3 or parts[0] != "properties" or not parts[-1].isdigit():
                    continue

            price = parse_money(
                d.get("price")
                or d.get("listPrice")
                or ((d.get("offers") or {}).get("price") if isinstance(d.get("offers"), dict) else None)
            )

            acres = parse_acres(d.get("acres") or d.get("lotSize") or d.get("lotSizeAcres") or d.get("size") or d.get("area"))
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

    links = soup.find_all("a", href=True)
    host = urlparse(base_url).netloc.lower()

    for a in links:
        href = a["href"]
        full = normalize_url(base_url, href)

        # If we're on LandSearch, enforce property detail URL shape
        if "landsearch.com" in host:
            p = urlparse(full)
            if p.fragment:
                continue
            parts = p.path.strip("/").split("/")
            if len(parts) < 3 or parts[0] != "properties" or not parts[-1].isdigit():
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

        thumb = None
        img = a.find("img")
        if img and img.get("src"):
            thumb = img.get("src")

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


def source_name_from_url(url: str) -> str:
    host = urlparse(url).netloc.lower()
    if "landsearch.com" in host:
        return "LandSearch"
    if "landwatch.com" in host:
        return "LandWatch"
    if "landandfarm.com" in host:
        return "LandAndFarm"
    if "land.com" in host:
        return "Land.com"
    return "Listing"


def extract_listings(url: str, html: str) -> List[Dict[str, Any]]:
    host = urlparse(url).netloc.lower()
    source_name = source_name_from_url(url)

    next_data = get_next_data_json(html)
    json_ld_blocks = get_json_ld(html)

    items: List[Dict[str, Any]] = []

    # LandSearch can use __NEXT_DATA__ to reliably get property URLs
    if "landsearch.com" in host and next_data:
        items.extend(extract_from_landsearch_next(url, next_data))

    # JSON-LD + fallback for any host
    if json_ld_blocks:
        items.extend(extract_from_jsonld(url, json_ld_blocks, source_name))

    if not items:
        items.extend(extract_from_html_fallback(url, html, source_name))

    items = [it for it in items if not is_lease_listing(it)]

    seen = set()
    out = []
    for it in items:
        if it["url"] in seen:
            continue
        seen.add(it["url"])
        out.append(it)
    return out


def load_existing_maps() -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    try:
        if not os.path.exists(DATA_FILE):
            return out
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            old = json.load(f)
        for it in old.get("items", []) or []:
            url = it.get("url")
            if not url:
                continue
            out[url] = {
                "found_utc": it.get("found_utc"),
                "ever_top_match": bool(it.get("ever_top_match", False)),
            }
    except Exception:
        return {}
    return out


def load_existing_file() -> Dict[str, Any]:
    if not os.path.exists(DATA_FILE):
        return {}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


# ============================================================
# NEW: context stamping from START_URL (LandSearch pages)
# ============================================================
def context_from_start_url(start_url: str) -> Tuple[str, str]:
    """
    Returns (derived_state, derived_county) based on the START_URL that is being scraped.
    This is intentionally "safe": it ONLY derives location from the *search page URL*,
    not from the listing URL (because listing URLs can be city/address-based).
    """
    u = (start_url or "").strip().lower()

    # LandSearch search pages:
    # https://www.landsearch.com/properties/king-george-va
    # https://www.landsearch.com/properties/westmoreland-county-va
    if "landsearch.com" in u and "/properties/" in u:
        try:
            slug = u.split("/properties/")[1].split("/")[0]  # king-george-va OR westmoreland-county-va
            parts = [p for p in slug.split("-") if p]
            if not parts:
                return ("", "")

            st = ""
            if parts and parts[-1] in {"va", "md"}:
                st = parts[-1].upper()
                parts = parts[:-1]

            # Remove a trailing literal "county" if present
            if parts and parts[-1] == "county":
                parts = parts[:-1]

            county_name = " ".join([w.capitalize() for w in parts]).strip()
            county = f"{county_name} County" if county_name else ""

            return (st, county)
        except Exception:
            return ("", "")

    return ("", "")


def main():
    os.makedirs("data", exist_ok=True)
    run_utc = datetime.now(timezone.utc).isoformat()

    old_map = load_existing_maps()
    old_file = load_existing_file()

    all_items: List[Dict[str, Any]] = []

    for url in START_URLS:
        context_state, context_county = context_from_start_url(url)

        try:
            html = fetch_html(url)
        except Exception as e:
            print(f"Failed to fetch {url}: {e}")
            continue

        batch = extract_listings(url, html)

        # stamp context onto every listing from this start page
        for it in batch:
            if context_state:
                it["derived_state"] = context_state
            if context_county:
                it["derived_county"] = context_county

        all_items.extend(batch)

    seen = set()
    final: List[Dict[str, Any]] = []
    for x in all_items:
        u = x.get("url")
        if not u or u in seen:
            continue
        seen.add(u)

        prev = old_map.get(u, {})
        x["found_utc"] = prev.get("found_utc") or run_utc
        x["ever_top_match"] = bool(prev.get("ever_top_match", False))

        if is_bad_title(x.get("title")):
            x["title"] = f"{x.get('source','Listing')} listing"

        x["status"] = "unknown"

        # drop leases early
        if is_lease_listing(x):
            continue

        final.append(x)

    # ------------------- Enrich (limited) -------------------
    final.sort(key=lambda it: it.get("found_utc") or "", reverse=True)
    final.sort(
        key=lambda it: (
            0 if is_top_match_now(it, MIN_ACRES, MAX_ACRES, MAX_PRICE) else 1,
            0 if should_enrich(it) else 1,
        )
    )

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

            s = (info.get("status") or "unknown").lower()
            it["status"] = s if s in STATUS_VALUES else "unknown"

            if it.get("price") is None and info.get("price") is not None:
                it["price"] = info["price"]

            if it.get("acres") is None and info.get("acres") is not None:
                it["acres"] = info["acres"]

            enriched += 1

    final = [it for it in final if not is_lease_listing(it)]

    for it in final:
        s = (it.get("status") or "unknown").lower()
        if s not in STATUS_VALUES:
            it["status"] = "unknown"

    for it in final:
        if not it.get("ever_top_match"):
            if is_top_match_now(it, MIN_ACRES, MAX_ACRES, MAX_PRICE):
                it["ever_top_match"] = True

    # If scrape returns 0, keep old items but record attempt time
    if len(final) == 0 and os.path.exists(DATA_FILE):
        print("⚠️ Scrape returned 0 listings. Keeping existing items, updating last_attempted_utc.")
        if not isinstance(old_file, dict):
            old_file = {}
        old_file["last_attempted_utc"] = run_utc
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(old_file, f, indent=2)
        return

    out = {
        "last_updated_utc": run_utc,
        "last_attempted_utc": run_utc,
        "criteria": {"min_acres": MIN_ACRES, "max_acres": MAX_ACRES, "max_price": MAX_PRICE},
        "items": final,
    }

    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)

    print(f"Saved {len(final)} listings. Enriched: {enriched}.")


def run_update():
    main()


if __name__ == "__main__":
    main()
