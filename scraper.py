import json
import re
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse

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
    "Accept-Language": "en-US,en;q=0.9",
}
TIMEOUT = 45

# Limit how many “detail page” requests we do per run (keeps it fast + less likely to get blocked)
DETAIL_FETCH_LIMIT = 25


# ---------------------------
# Core helpers
# ---------------------------
def fetch_html(url: str) -> str:
    r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    return r.text


def normalize_url(base_url: str, u: str) -> str:
    if not u:
        return ""
    return urljoin(base_url, u)


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


def clean_title(s: str) -> str:
    if not s:
        return ""
    t = " ".join(str(s).split()).strip()

    bad = {
        "skip to navigation",
        "skip to content",
        "land listing",
        "properties",
        "property",
    }
    if t.lower() in bad:
        return ""
    return t


def best_title_from_dict(d: dict) -> str:
    for k in ("title", "name", "headline", "label"):
        v = d.get(k)
        if isinstance(v, str):
            ct = clean_title(v)
            if ct:
                return ct
    return ""


def parse_money(value: Any) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)

    s = str(value).strip().lower()
    if not s:
        return None

    if any(x in s for x in ("contact", "call", "tbd", "request", "inquire")):
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
        for k in ("acres", "acreage", "lotSizeAcres", "sizeAcres", "lotSize", "size", "area"):
            if k in value:
                v = parse_acres(value.get(k))
                if v is not None:
                    return v

        val = value.get("value") or value.get("amount") or value.get("number")
        unit = str(value.get("unit") or value.get("unitText") or value.get("unitCode") or "").lower()

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


def is_strict_match(price: Optional[int], acres: Optional[float]) -> bool:
    if price is None or acres is None:
        return False
    return (MIN_ACRES <= float(acres) <= MAX_ACRES) and (int(price) <= int(MAX_PRICE))


def get_meta_content(soup: BeautifulSoup, key: str, attr: str = "property") -> str:
    tag = soup.find("meta", attrs={attr: key})
    if tag and tag.get("content"):
        return tag["content"].strip()
    return ""


def should_enrich_title(title: str) -> bool:
    t = (title or "").strip().lower()
    if not t:
        return True
    if t in {"land listing", "skip to navigation", "skip to content"}:
        return True
    # Sometimes it returns extremely short junk
    if len(t) < 6:
        return True
    return False


def enrich_from_detail_page(url: str) -> Dict[str, Optional[str]]:
    """
    Fetch listing detail page once and try to extract a real title + thumbnail.
    Returns dict with keys: title, thumbnail (each can be None).
    """
    try:
        html = fetch_html(url)
    except Exception:
        return {"title": None, "thumbnail": None}

    soup = BeautifulSoup(html, "html.parser")

    # Title priority: og:title -> twitter:title -> h1 -> <title>
    og_title = get_meta_content(soup, "og:title", attr="property")
    if og_title:
        title = clean_title(og_title)
        if title:
            pass
        else:
            title = None
    else:
        title = None

    if not title:
        tw_title = get_meta_content(soup, "twitter:title", attr="name")
        title = clean_title(tw_title) if tw_title else ""

    if not title:
        h1 = soup.find("h1")
        if h1:
            title = clean_title(h1.get_text(" ", strip=True))

    if not title:
        if soup.title and soup.title.string:
            title = clean_title(soup.title.string)

    # Thumbnail priority: og:image -> twitter:image -> first reasonable <img>
    og_img = get_meta_content(soup, "og:image", attr="property")
    thumb = og_img.strip() if og_img else ""

    if not thumb:
        tw_img = get_meta_content(soup, "twitter:image", attr="name")
        thumb = tw_img.strip() if tw_img else ""

    if not thumb:
        img = soup.find("img")
        if img and img.get("src"):
            thumb = img["src"].strip()

    thumb = thumb or None

    return {"title": title or None, "thumbnail": thumb}


# ---------------------------
# Parsers
# ---------------------------
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


def extract_thumbnail_from_dict(base_url: str, d: dict) -> Optional[str]:
    for k in ("thumbnail", "image", "img", "photo", "primaryImage", "primary_image"):
        v = d.get(k)
        if isinstance(v, str) and v.strip():
            return normalize_url(base_url, v.strip())

    img = d.get("image")
    if isinstance(img, list) and img:
        if isinstance(img[0], str) and img[0].strip():
            return normalize_url(base_url, img[0].strip())
        if isinstance(img[0], dict):
            u = img[0].get("url")
            if isinstance(u, str) and u.strip():
                return normalize_url(base_url, u.strip())

    if isinstance(img, dict):
        u = img.get("url")
        if isinstance(u, str) and u.strip():
            return normalize_url(base_url, u.strip())

    return None


def extract_from_landsearch_cards(base_url: str, html: str) -> List[Dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    items: List[Dict[str, Any]] = []

    for a in soup.select('a[href*="/properties/"], a[href*="/property/"]'):
        href = a.get("href", "")
        url = normalize_url(base_url, href)
        if not url:
            continue
        if "landsearch.com" not in url:
            continue

        # card-ish container heuristic
        card = a
        for _ in range(6):
            if card.parent is None:
                break
            card = card.parent
            txt = card.get_text(" ", strip=True).lower()
            if "acres" in txt or "$" in txt:
                break

        card_text = card.get_text(" ", strip=True)

        title = clean_title(a.get_text(" ", strip=True))
        if not title:
            h = card.find(["h1", "h2", "h3"])
            if h:
                title = clean_title(h.get_text(" ", strip=True))

        price = parse_money(card_text)

        acres = None
        m = re.search(r"(\d+(?:\.\d+)?)\s*acres?\b", card_text.lower())
        if m:
            try:
                acres = float(m.group(1))
            except Exception:
                acres = None

        thumb = None
        img = card.find("img")
        if img and img.get("src"):
            thumb = normalize_url(base_url, img["src"])

        items.append(
            {
                "source": "LandSearch",
                "title": title or "Land listing",
                "url": url,
                "price": price,
                "acres": acres,
                "thumbnail": thumb,
            }
        )

    return items


def extract_from_jsonld(base_url: str, blocks: List[dict], source_name: str) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for block in blocks:
        for d in walk(block):
            if not isinstance(d, dict):
                continue

            raw_url = d.get("url") or d.get("mainEntityOfPage") or d.get("sameAs") or ""
            url = normalize_url(base_url, str(raw_url)) if raw_url else ""
            if not url:
                continue

            title = best_title_from_dict(d) or "Land listing"

            price = parse_money(
                d.get("price")
                or d.get("listPrice")
                or (d.get("offers", {}).get("price") if isinstance(d.get("offers"), dict) else None)
            )

            acres = parse_acres(
                d.get("acres")
                or d.get("lotSize")
                or d.get("lotSizeAcres")
                or d.get("size")
                or d.get("area")
            )

            thumb = extract_thumbnail_from_dict(base_url, d)

            items.append(
                {
                    "source": source_name,
                    "title": title,
                    "url": url,
                    "price": price,
                    "acres": acres,
                    "thumbnail": thumb,
                }
            )
    return items


def extract_from_next_data(base_url: str, next_data: dict, source_name: str) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []

    for d in walk(next_data):
        if not isinstance(d, dict):
            continue

        raw_url = d.get("url") or d.get("href") or d.get("canonicalUrl") or d.get("permalink") or ""
        if not raw_url:
            continue

        url = normalize_url(base_url, str(raw_url))
        if not url:
            continue

        if any(x in url for x in ("/filter/", "#nav", "sort=", "format=")):
            if ("/properties/" not in url) and ("/property/" not in url):
                continue

        title = best_title_from_dict(d) or "Land listing"

        price = parse_money(
            d.get("price")
            or d.get("listPrice")
            or d.get("priceValue")
            or d.get("amount")
            or (d.get("offers", {}).get("price") if isinstance(d.get("offers"), dict) else None)
            or (d.get("pricing", {}).get("price") if isinstance(d.get("pricing"), dict) else None)
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

        thumb = extract_thumbnail_from_dict(base_url, d)

        items.append(
            {
                "source": source_name,
                "title": title,
                "url": url,
                "price": price,
                "acres": acres,
                "thumbnail": thumb,
            }
        )

    return items


def dedupe_and_clean(items: List[Dict[str, Any]], base_url: str) -> List[Dict[str, Any]]:
    seen = set()
    out: List[Dict[str, Any]] = []
    for it in items:
        url = it.get("url") or ""
        if not url:
            continue

        url = normalize_url(base_url, url)
        it["url"] = url

        if url in seen:
            continue
        seen.add(url)

        it["title"] = clean_title(it.get("title", "")) or "Land listing"

        if any(x in url for x in ("#nav", "skip", "/filter/")) and ("/properties/" not in url and "/property/" not in url):
            continue

        out.append(it)
    return out


def extract_listings(url: str, html: str) -> List[Dict[str, Any]]:
    host = urlparse(url).netloc.lower()

    items: List[Dict[str, Any]] = []

    if "landsearch.com" in host:
        items.extend(extract_from_landsearch_cards(url, html))

    json_ld_blocks = get_json_ld(html)
    if json_ld_blocks:
        src = "LandSearch" if "landsearch.com" in host else "LandWatch"
        items.extend(extract_from_jsonld(url, json_ld_blocks, src))

    next_data = get_next_data_json(html)
    if next_data:
        src = "LandSearch" if "landsearch.com" in host else "LandWatch"
        items.extend(extract_from_next_data(url, next_data, src))

    items = dedupe_and_clean(items, url)

    cleaned = []
    for it in items:
        u = it.get("url", "")
        if "landsearch.com" in host:
            if ("/properties/" not in u) and ("/property/" not in u):
                continue
        if "landwatch.com" in host:
            if "/property/" not in u:
                continue
        cleaned.append(it)

    return cleaned


def main():
    run_utc = datetime.now(timezone.utc).isoformat()
    found_utc = run_utc

    all_items: List[Dict[str, Any]] = []

    for url in START_URLS:
        try:
            html = fetch_html(url)
        except Exception as e:
            print(f"Failed to fetch {url}: {e}")
            continue

        items = extract_listings(url, html)
        for it in items:
            it["found_utc"] = found_utc
            it["match"] = is_strict_match(it.get("price"), it.get("acres"))
        all_items.extend(items)

    # Dedup across sources
    seen = set()
    final: List[Dict[str, Any]] = []
    for x in all_items:
        u = x.get("url")
        if not u or u in seen:
            continue
        seen.add(u)
        final.append(x)

    # --- DETAIL PAGE ENRICHMENT (fix “Land listing”) ---
    enriched = 0
    for it in final:
        if enriched >= DETAIL_FETCH_LIMIT:
            break

        title = it.get("title") or ""
        if not should_enrich_title(title):
            continue

        detail = enrich_from_detail_page(it["url"])
        if detail.get("title"):
            it["title"] = detail["title"]

        # If we don’t have a thumbnail, try to fill it from the detail page
        if not it.get("thumbnail") and detail.get("thumbnail"):
            it["thumbnail"] = detail["thumbnail"]

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

    os.makedirs("data", exist_ok=True)
    with open("data/listings.json", "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)

    matches = sum(1 for it in final if it.get("match") is True)
    print(f"Saved {len(final)} total listings. Strict matches: {matches}. Enriched titles: {enriched}.")


if __name__ == "__main__":
    main()