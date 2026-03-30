import json
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from supabase import create_client

from dotenv import load_dotenv
from scrapers import pipeline as scraper_pipeline
from scrapers.sites.landsearch import extract_from_landsearch_next as extract_landsearch_next
from scrapers.sites.landwatch import extract_landwatch_listings

load_dotenv()

# =========================
# Supabase client (WRITER)
# =========================


def get_env(name: str) -> str:
    v = os.getenv(name)
    if v:
        return v
    raise RuntimeError(f"Missing required environment variable: {name}")


SUPABASE_URL = get_env("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = get_env("SUPABASE_SERVICE_ROLE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

# ====== YOUR SETTINGS ======
LANDSEARCH_URLS = [
    "https://www.landsearch.com/properties/king-george-va",
    "https://www.landsearch.com/properties/westmoreland-county-va",
    "https://www.landsearch.com/properties/stafford-county-va",
    "https://www.landsearch.com/properties/caroline-county-va",
    "https://www.landsearch.com/properties/frederick-county-md",
    "https://www.landsearch.com/properties/anne-arundel-county-md",
    "https://www.landsearch.com/properties/king-william-county-va",
]

LANDWATCH_URLS = [
    "https://www.landwatch.com/virginia-land-for-sale/king-george",
    "https://www.landwatch.com/virginia-land-for-sale/westmoreland-county",
    "https://www.landwatch.com/virginia-land-for-sale/caroline-county",
    "https://www.landwatch.com/virginia-land-for-sale/stafford-county",
    "https://www.landwatch.com/maryland-land-for-sale/caroline-county",
    "https://www.landwatch.com/maryland-land-for-sale/frederick-county",
    "https://www.landwatch.com/maryland-land-for-sale/anne-arundel-county",
    "https://www.landwatch.com/maryland-land-for-sale/montgomery-county",
]

ENABLE_LANDWATCH = False

START_URLS = [
    # ---- LandSearch (county pages, NO filters) ----
    *LANDSEARCH_URLS,
    # ---- LandWatch (disabled by default while debugging 403 blocks) ----
    *(LANDWATCH_URLS if ENABLE_LANDWATCH else []),
]

MIN_ACRES = 10.0
MAX_ACRES = 50.0
MAX_PRICE = 600_000

# Enrich missing titles/thumbs/status/price by visiting a few detail pages
DETAIL_ENRICH_LIMIT = 80
# ===========================

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
}

TIMEOUT = 40
DATA_FILE = "data/listings.json"  # optional debug snapshot

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

STATUS_VALUES = {
    "available",
    "under_contract",
    "pending",
    "sold",
    "off_market",
    "unknown",
}

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
    host = urlparse(url).netloc.lower()
    headers = None
    if "landwatch.com" in host:
        headers = {
            **HEADERS,
            "Referer": "https://www.landwatch.com/",
            "Sec-Fetch-Site": "same-origin",
        }
    r = session.get(url, timeout=TIMEOUT, headers=headers)
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
        unit = (value.get("unit") or value.get("unitText")
                or value.get("unitCode") or "").lower()

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
def normalize_status(value: Any) -> str:
    t = str(value or "").strip().lower()
    if not t:
        return "unknown"

    t = re.sub(r"[_\-]+", " ", t)
    t = re.sub(r"\s+", " ", t).strip()

    if re.search(r"\b(sold|closed|sale completed)\b", t):
        return "sold"
    if re.search(r"\b(pending|sale pending)\b", t):
        return "pending"
    if re.search(r"\b(under contract|in contract|under agreement)\b", t):
        return "under_contract"
    if re.search(
        r"\b(off market|offmarket|withdrawn|removed|inactive|canceled|cancelled|expired|no longer available|not available)\b",
        t,
    ):
        return "off_market"

    if re.search(r"(schema\.org/instock|\bin stock\b)", t):
        return "available"
    if re.search(r"(schema\.org/soldout|\bsold out\b|\bout of stock\b|schema\.org/discontinued)", t):
        return "off_market"

    if re.search(r"\b(available|active)\b", t):
        return "available"

    return "unknown"


def detect_status(text: str) -> str:
    t = (text or "").strip()
    if not t:
        return "unknown"

    # Strict priority: sold -> under_contract -> pending -> off_market/removed.
    if re.search(r"\b(sold|closed|sale completed)\b", t, flags=re.IGNORECASE):
        return "sold"
    if re.search(r"\b(under\s+contract|in\s+contract|under\s+agreement)\b", t, flags=re.IGNORECASE):
        return "under_contract"
    if re.search(r"\b(pending|sale pending)\b", t, flags=re.IGNORECASE):
        return "pending"
    if re.search(
        r"\b(off[\s\-]?market|removed|withdrawn|inactive|canceled|cancelled|expired|no longer available|not available)\b",
        t,
        flags=re.IGNORECASE,
    ):
        return "off_market"

    # Only trust available/active when shown as a status label.
    if re.search(
        r"(?:listing\s*status|property\s*status|sale\s*status|transaction\s*status|availability|status)\s*[:\-]\s*(?:\bactive\b|\bavailable\b)",
        t,
        flags=re.IGNORECASE,
    ):
        return "available"
    if re.fullmatch(r"\s*(?:\bactive\b|\bavailable\b)\s*", t, flags=re.IGNORECASE):
        return "available"

    return "unknown"


def extract_status_from_next_data(next_data: dict) -> Optional[str]:
    status_keys = {
        "status",
        "listingstatus",
        "propertystatus",
        "salestatus",
        "transactionstatus",
        "availability",
    }

    for d in walk(next_data):
        if not isinstance(d, dict):
            continue

        for k, v in d.items():
            key = str(k).strip().lower().replace("_", "").replace("-", "")
            if key not in status_keys:
                continue

            if isinstance(v, str):
                s = detect_status(v)
                if s != "unknown":
                    return s

            if isinstance(v, (dict, list)):
                for nested in walk(v):
                    if not isinstance(nested, dict):
                        continue
                    for nv in nested.values():
                        if not isinstance(nv, str):
                            continue
                        s = detect_status(nv)
                        if s != "unknown":
                            return s

    return None


def extract_status_from_dict(d: dict) -> str:
    status_keys = {
        "status",
        "listingstatus",
        "salestatus",
        "transactionstatus",
        "state",
        "availability",
        "label",
        "badge",
        "badges",
    }
    allowed = {"available", "under_contract", "pending", "sold", "off_market", "unknown"}

    def _normalize_result(raw: str) -> str:
        s = (raw or "unknown").strip().lower()
        return s if s in allowed else "unknown"

    for k, v in d.items():
        key = str(k).strip().lower().replace("_", "").replace("-", "")
        if key not in status_keys:
            continue

        if isinstance(v, str):
            s = _normalize_result(detect_status(v))
            if s != "unknown":
                return s

        elif isinstance(v, list):
            for part in v:
                if isinstance(part, str):
                    s = _normalize_result(detect_status(part))
                    if s != "unknown":
                        return s
                elif isinstance(part, dict):
                    for sub_v in part.values():
                        if isinstance(sub_v, str):
                            s = _normalize_result(detect_status(sub_v))
                            if s != "unknown":
                                return s

        elif isinstance(v, dict):
            for sub_v in v.values():
                if isinstance(sub_v, str):
                    s = _normalize_result(detect_status(sub_v))
                    if s != "unknown":
                        return s

    return "unknown"


# ------------------- Helpers -------------------
def to_row(it: Dict[str, Any], run_utc: str) -> Dict[str, Any]:
    listing_id = it.get("listing_id") or it.get("url")
    status = detect_status(str(it.get("status") or ""))
    if status not in STATUS_VALUES:
        status = "unknown"
    return {
        "listing_id": listing_id,
        "title": it.get("title"),
        "url": it.get("url"),
        "source": it.get("source"),
        "price": it.get("price"),
        "acres": it.get("acres"),
        "status": status,
        "thumbnail": it.get("thumbnail"),
        "found_utc": it.get("found_utc") or run_utc,
        "derived_state": it.get("derived_state"),
        "derived_county": it.get("derived_county"),
        "last_seen_utc": run_utc,
        "is_active": True,
        # do NOT touch is_favorite here
    }


def _chunks(lst, size=500):
    for i in range(0, len(lst), size):
        yield lst[i: i + size]


def upsert_to_supabase(items: List[Dict[str, Any]], run_utc: str) -> int:
    rows = [scraper_pipeline.to_row(it, run_utc) for it in items if it.get("url")]
    if not rows:
        return 0

    total = 0
    for batch in _chunks(rows, size=500):
        supabase.table("listings").upsert(
            batch, on_conflict="listing_id").execute()
        total += len(batch)
    return total


def record_scrape_run(run_utc: str, written: int, enriched: int) -> None:
    supabase.table("scrape_runs").insert(
        {"run_utc": run_utc, "written": int(
            written), "enriched": int(enriched)}
    ).execute()


def mark_stale_listings_inactive(run_utc: str, stale_days: int = 14) -> int:
    try:
        run_dt = datetime.fromisoformat(run_utc)
    except Exception:
        run_dt = datetime.now(timezone.utc)

    stale_cutoff_utc = (run_dt - timedelta(days=stale_days)).isoformat()

    stale_rows: List[Dict[str, Any]] = []
    page_size = 1000
    start = 0
    while True:
        resp = (
            supabase.table("listings")
            .select("listing_id,status")
            .eq("is_active", True)
            .lt("last_seen_utc", stale_cutoff_utc)
            .range(start, start + page_size - 1)
            .execute()
        )
        batch = resp.data or []
        if not batch:
            break
        stale_rows.extend(batch)
        if len(batch) < page_size:
            break
        start += page_size

    stale_ids = [str(r.get("listing_id")) for r in stale_rows if r.get("listing_id")]
    if not stale_ids:
        return 0

    for chunk in _chunks(stale_ids, size=500):
        supabase.table("listings").update({"is_active": False}).eq("is_active", True).in_(
            "listing_id", chunk
        ).execute()

    # Only mark off_market when status is null/empty/unknown/available.
    for chunk in _chunks(stale_ids, size=500):
        supabase.table("listings").update({"status": "off_market"}).eq("is_active", False).eq(
            "status", "unknown"
        ).in_("listing_id", chunk).execute()
        supabase.table("listings").update({"status": "off_market"}).eq("is_active", False).eq(
            "status", "available"
        ).in_("listing_id", chunk).execute()
        supabase.table("listings").update({"status": "off_market"}).eq("is_active", False).eq(
            "status", ""
        ).in_("listing_id", chunk).execute()
        supabase.table("listings").update({"status": "off_market"}).eq("is_active", False).is_(
            "status", "null"
        ).in_("listing_id", chunk).execute()

    return len(stale_ids)


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


def is_top_match_now(it: Dict[str, Any], min_a: float, max_a: float, max_p: int) -> bool:
    try:
        acres = it.get("acres")
        price = it.get("price")
        status = (it.get("status") or "unknown").lower()
        if status != "available":
            return False
        if acres is None or price is None:
            return False
        return (min_a <= float(acres) <= max_a) and (int(price) <= int(max_p))
    except Exception:
        return False


def _collect_status_like_dom_text(soup: BeautifulSoup) -> List[str]:
    out: List[str] = []
    seen = set()
    key_re = re.compile(r"(status|badge|pill|label|availability)", flags=re.IGNORECASE)
    for el in soup.find_all(True):
        classes = " ".join(el.get("class") or [])
        ident = str(el.get("id") or "")
        attrs_blob = f"{classes} {ident}"
        if not key_re.search(attrs_blob):
            continue
        txt = el.get_text(" ", strip=True)
        txt = re.sub(r"\s+", " ", txt).strip()
        if not txt or len(txt) > 120:
            continue
        key = txt.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(txt)
    return out


def _collect_status_like_jsonld_values(blocks: List[dict]) -> List[str]:
    out: List[str] = []
    seen = set()
    status_keys = {
        "status",
        "listingstatus",
        "propertystatus",
        "salestatus",
        "transactionstatus",
        "availability",
        "availabilitystarts",
        "availabilityends",
    }
    for block in blocks:
        for d in walk(block):
            if not isinstance(d, dict):
                continue
            for k, v in d.items():
                key = str(k).strip().lower().replace("_", "").replace("-", "")
                if key not in status_keys:
                    continue
                if isinstance(v, str):
                    txt = re.sub(r"\s+", " ", v).strip()
                    if not txt:
                        continue
                    lk = txt.lower()
                    if lk in seen:
                        continue
                    seen.add(lk)
                    out.append(txt)
                elif isinstance(v, dict):
                    for sub_v in v.values():
                        if isinstance(sub_v, str):
                            txt = re.sub(r"\s+", " ", sub_v).strip()
                            if not txt:
                                continue
                            lk = txt.lower()
                            if lk in seen:
                                continue
                            seen.add(lk)
                            out.append(txt)
    return out


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

    blocks = get_json_ld(html)
    status = "unknown"
    next_data = get_next_data_json(html)
    if next_data and "landsearch.com" in urlparse(url).netloc.lower():
        next_status = extract_status_from_next_data(next_data)
        if next_status:
            status = next_status
    if status == "unknown":
        status_candidates: List[str] = []
        status_candidates.extend(_collect_status_like_dom_text(soup))
        status_candidates.extend(
            [
                meta("og:description", "property"),
                meta("twitter:description", "name"),
            ]
        )
        status_candidates.extend(_collect_status_like_jsonld_values(blocks))
        for candidate in status_candidates:
            s = detect_status(candidate)
            if s != "unknown":
                status = s
                break

    price = None
    acres = None
    for block in blocks:
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
        status = extract_status_from_dict(d)

        items.append(
            {
                "source": "LandSearch",
                "title": best_title(d, "LandSearch"),
                "url": url,
                "price": price,
                "acres": acres,
                "thumbnail": thumb,
                "status": status,
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

            raw_url = d.get("url") or d.get(
                "mainEntityOfPage") or d.get("sameAs") or ""
            if not raw_url:
                continue

            url = normalize_url(base_url, str(raw_url))
            if not url:
                continue

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

            acres = parse_acres(d.get("acres") or d.get("lotSize") or d.get(
                "lotSizeAcres") or d.get("size") or d.get("area"))
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
        title = raw_title if not is_bad_title(
            raw_title) else f"{source_name} listing"

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

    if "landsearch.com" in host and next_data:
        items.extend(extract_landsearch_next(url, next_data))
    elif "landwatch.com" in host:
        items.extend(extract_landwatch_listings(url, html))
    else:
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


def context_from_start_url(start_url: str) -> Tuple[str, str]:
    u = (start_url or "").strip().lower()

    if "landsearch.com" in u and "/properties/" in u:
        try:
            slug = u.split("/properties/")[1].split("/")[0]
            parts = [p for p in slug.split("-") if p]
            if not parts:
                return ("", "")

            st = ""
            if parts and parts[-1] in {"va", "md"}:
                st = parts[-1].upper()
                parts = parts[:-1]

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
    # kept for compatibility; not used beyond zero-result case
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

        for it in batch:
            if context_state:
                it["derived_state"] = context_state
            if context_county:
                it["derived_county"] = context_county

        all_items.extend(batch)

    final = scraper_pipeline.finalize_scraped_items(
        all_items,
        old_map,
        run_utc,
        MIN_ACRES,
        MAX_ACRES,
        MAX_PRICE,
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

    final = scraper_pipeline.finalize_enriched_items(
        final,
        MIN_ACRES,
        MAX_ACRES,
        MAX_PRICE,
    )

    if len(final) == 0 and os.path.exists(DATA_FILE):
        print("⚠️ Scrape returned 0 listings. Keeping existing items, updating last_attempted_utc.")
        if not isinstance(old_file, dict):
            old_file = {}
        old_file["last_attempted_utc"] = run_utc
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(old_file, f, indent=2)
        return

    written = upsert_to_supabase(final, run_utc)
    stale_marked = mark_stale_listings_inactive(run_utc, stale_days=14)
    record_scrape_run(run_utc, written, enriched)
    print(f"Upserted {written} listings to Supabase. Enriched: {enriched}.")
    print(f"Marked {stale_marked} stale listings inactive.")

    # Optional debug snapshot
    out = {
        "last_updated_utc": run_utc,
        "last_attempted_utc": run_utc,
        "criteria": {"min_acres": MIN_ACRES, "max_acres": MAX_ACRES, "max_price": MAX_PRICE},
        "items": final,
    }
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)

def run_update():
    main()


if __name__ == "__main__":
    main()
