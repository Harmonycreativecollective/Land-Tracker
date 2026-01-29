import json
import re
import time
from datetime import datetime, timezone
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


# ====== YOUR SETTINGS ======
SOURCES = [
    {
        "name": "LandWatch",
        "url": "https://www.landwatch.com/virginia-land-for-sale/king-george/acres-11-50/available",
        "base": "https://www.landwatch.com",
    },
    {
        "name": "LandSearch",
        "url": "https://www.landsearch.com/properties/king-george-va/filter/format=sales,size[min]=10",
        "base": "https://www.landsearch.com",
    },
]

MIN_ACRES = 11.0
MAX_ACRES = 50.0
MAX_PRICE = 600_000  # <= you asked for 600k

# If you want to require "land only" (no houses), add keyword rules later.
# For now we keep it simple and just do acreage + max price.
# ===========================


HEADERS = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
}

PRICE_RE = re.compile(r"\$[\s]*([\d,]+)")
ACRES_RE = re.compile(r"([\d,.]+)\s*acres?", re.IGNORECASE)

def parse_price(text: str):
    m = PRICE_RE.search(text or "")
    if not m:
        return None
    return int(m.group(1).replace(",", ""))

def parse_acres(text: str):
    m = ACRES_RE.search(text or "")
    if not m:
        return None
    return float(m.group(1).replace(",", ""))

def normalize_whitespace(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip()

def fetch_html(url: str) -> str:
    r = requests.get(url, headers=HEADERS, timeout=30)
    return r.status_code, r.text

def extract_candidates_generic(html: str, base_url: str):
    """
    Generic extraction:
    - Collect likely listing blocks by scanning for repeated "$... • ... acres" patterns
    - Also grab nearby links from the page
    This is not perfect but is intentionally "robust" across minor site changes.
    """
    soup = BeautifulSoup(html, "html.parser")

    # Grab all links for later matching
    links = []
    for a in soup.select("a[href]"):
        href = a.get("href", "")
        text = normalize_whitespace(a.get_text(" "))
        if not href or href.startswith("#"):
            continue
        full = href if href.startswith("http") else urljoin(base_url, href)
        links.append((full, text))

    # Find text chunks that contain price + acres
    text = normalize_whitespace(soup.get_text(" "))
    # This finds many, so we’ll build candidates from link texts too
    candidates = []

    # Candidate approach 1: use link text blocks
    for full, ltext in links:
        if "$" in ltext and "acre" in ltext.lower():
            price = parse_price(ltext)
            acres = parse_acres(ltext)
            candidates.append({
                "title": ltext,
                "url": full,
                "price": price,
                "acres": acres,
                "raw": ltext,
            })

    # Candidate approach 2: if link-text approach found nothing, try scanning page text
    if not candidates:
        # Pull snippets around each "$"
        idxs = [m.start() for m in re.finditer(r"\$", text)]
        for i in idxs[:200]:
            snippet = text[max(0, i-120): i+180]
            if "acre" not in snippet.lower():
                continue
            price = parse_price(snippet)
            acres = parse_acres(snippet)
            if price is None or acres is None:
                continue
            candidates.append({
                "title": snippet,
                "url": None,
                "price": price,
                "acres": acres,
                "raw": snippet,
            })

    # Deduplicate by (price, acres, url/title)
    seen = set()
    deduped = []
    for c in candidates:
        key = (c.get("price"), c.get("acres"), c.get("url") or c.get("title"))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(c)

    return deduped

def passes_filters(item):
    reasons = []
    price = item.get("price")
    acres = item.get("acres")

    if price is None:
        reasons.append("missing_price")
    if acres is None:
        reasons.append("missing_acres")

    if acres is not None and acres < MIN_ACRES:
        reasons.append("acres_too_small")
    if acres is not None and acres > MAX_ACRES:
        reasons.append("acres_too_big")
    if price is not None and price > MAX_PRICE:
        reasons.append("price_too_high")

    return (len(reasons) == 0), reasons

def main():
    debug = {
        "run_utc": datetime.now(timezone.utc).isoformat(),
        "sources": [],
        "totals": {
            "candidates_found": 0,
            "matches": 0,
            "filtered_out": 0,
        },
        "filtered_reasons_count": {},
        "notes": [],
    }

    matches = []
    filtered_samples = []

    for src in SOURCES:
        status, html = fetch_html(src["url"])
        src_debug = {
            "name": src["name"],
            "url": src["url"],
            "http_status": status,
            "candidates": 0,
            "matches": 0,
            "filtered_out": 0,
        }

        if status != 200 or not html or len(html) < 5000:
            src_debug["error"] = f"Bad response: status={status}, html_len={len(html) if html else 0}"
            debug["sources"].append(src_debug)
            continue

        candidates = extract_candidates_generic(html, src["base"])
        src_debug["candidates"] = len(candidates)
        debug["totals"]["candidates_found"] += len(candidates)

        for c in candidates:
            ok, reasons = passes_filters(c)
            if ok:
                c["source"] = src["name"]
                matches.append(c)
                src_debug["matches"] += 1
            else:
                src_debug["filtered_out"] += 1
                debug["totals"]["filtered_out"] += 1
                for r in reasons:
                    debug["filtered_reasons_count"][r] = debug["filtered_reasons_count"].get(r, 0) + 1

                # keep a few examples to inspect later
                if len(filtered_samples) < 25:
                    filtered_samples.append({
                        "source": src["name"],
                        "price": c.get("price"),
                        "acres": c.get("acres"),
                        "url": c.get("url"),
                        "raw": c.get("raw"),
                        "reasons": reasons,
                    })

        debug["sources"].append(src_debug)

    # Deduplicate matches
    seen = set()
    final_matches = []
    for m in matches:
        key = (m.get("url"), m.get("price"), m.get("acres"), m.get("title"))
        if key in seen:
            continue
        seen.add(key)
        final_matches.append(m)

    debug["totals"]["matches"] = len(final_matches)
    debug["filtered_samples"] = filtered_samples

    # Write outputs
    out = {
        "last_updated_utc": debug["run_utc"],
        "criteria": {
            "min_acres": MIN_ACRES,
            "max_acres": MAX_ACRES,
            "max_price": MAX_PRICE,
        },
        "matches": final_matches,
    }

    with open("data/listings.json", "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)

    with open("data/debug.json", "w", encoding="utf-8") as f:
        json.dump(debug, f, indent=2)

    print("Done.")
    print(json.dumps(debug["totals"], indent=2))


if __name__ == "__main__":
    main()
