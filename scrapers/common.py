import json
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

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
    "auction",
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
    if re.search(r"\bauction\b", t):
        return "auction"

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

    if re.search(r"\b(sold|closed|sale completed)\b", t, flags=re.IGNORECASE):
        return "sold"
    if re.search(r"\b(under\s+contract|in\s+contract|under\s+agreement)\b", t, flags=re.IGNORECASE):
        return "under_contract"
    if re.search(r"\b(pending|sale pending)\b", t, flags=re.IGNORECASE):
        return "pending"
    if re.search(r"\bauction\b", t, flags=re.IGNORECASE):
        return "auction"
    if re.search(
        r"\b(off[\s\-]?market|removed|withdrawn|inactive|canceled|cancelled|expired|no longer available|not available)\b",
        t,
        flags=re.IGNORECASE,
    ):
        return "off_market"
    if re.search(r"(schema\.org/soldout|\bsold out\b|\bout of stock\b|schema\.org/discontinued)", t, flags=re.IGNORECASE):
        return "off_market"
    if re.search(r"(schema\.org/instock|\bin stock\b|\bactive\s+sale\b)", t, flags=re.IGNORECASE):
        return "available"

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
    allowed = STATUS_VALUES

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



def is_lease_listing(it: Dict[str, Any]) -> bool:
    t = (it.get("title") or "").lower()
    u = (it.get("url") or "").lower()
    return any(kw in t or kw in u for kw in LEASE_KEYWORDS)



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



def collect_status_like_dom_text(soup: BeautifulSoup) -> List[str]:
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



def collect_status_like_jsonld_values(blocks: List[dict]) -> List[str]:
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



def is_landsearch_listing_url(url: str) -> bool:
    if "landsearch.com" not in url:
        return False
    p = urlparse(url)
    if p.fragment:
        return False
    parts = p.path.strip("/").split("/")
    return len(parts) >= 3 and parts[0] == "properties" and parts[-1].isdigit()



def dedupe_by_url(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    out: List[Dict[str, Any]] = []
    for it in items:
        url = it.get("url")
        if not url or url in seen:
            continue
        seen.add(url)
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

            if "landsearch.com" in host and not is_landsearch_listing_url(url):
                continue

            price = parse_money(
                d.get("price")
                or d.get("listPrice")
                or ((d.get("offers") or {}).get("price") if isinstance(d.get("offers"), dict) else None)
            )

            acres = parse_acres(
                d.get("acres") or d.get("lotSize") or d.get("lotSizeAcres") or d.get("size") or d.get("area")
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

    return dedupe_by_url(items)



def extract_from_html_fallback(base_url: str, html: str, source_name: str) -> List[Dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    items: List[Dict[str, Any]] = []
    host = urlparse(base_url).netloc.lower()

    for a in soup.find_all("a", href=True):
        full = normalize_url(base_url, a["href"])

        if "landsearch.com" in host and not is_landsearch_listing_url(full):
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

    return dedupe_by_url(items)
