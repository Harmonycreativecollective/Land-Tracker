import json
import os
import re
from datetime import datetime, timezone
from typing import Dict, List
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

DATA_PATH = "data/listings.json"

# ✅ Your filters 
MAX_PRICE = 60000

# ✅ Paste saved-search URLs here
SEARCH_URLS = [
    "https://www.landwatch.com/virginia-land-for-sale/king-george/acres-11-50/available",
    "https://www.landsearch.com/properties/king-george-va/filter/format=sales,size[min]=10",
]


def money_to_int(text: str) -> int | None:
    if not text:
        return None
    m = re.search(r"(\d[\d,]*)", text.replace("$", ""))
    return int(m.group(1).replace(",", "")) if m else None


def safe_get(url: str) -> str:
    headers = {"User-Agent": "Mozilla/5.0 (compatible; LandTracker/1.0)"}
    r = requests.get(url, headers=headers, timeout=30)
    r.raise_for_status()
    return r.text


def parse_landwatch(html: str, page_url: str) -> List[Dict]:
    soup = BeautifulSoup(html, "lxml")
    items: Dict[str, Dict] = {}

    # LandWatch property pages often contain "/property/" in hrefs
    for a in soup.select("a[href*='/property/']"):
        href = a.get("href")
        if not href:
            continue

        if href.startswith("/"):
            href = urljoin(page_url, href)

        text = a.get_text(" ", strip=True)
        title = (text[:160] if text else "LandWatch listing").strip()

        price = None
        m = re.search(r"\$[\d,]+", text)
        if m:
            price = money_to_int(m.group(0))

        items[href] = {
            "id": href,
            "title": title,
            "url": href,
            "price": price,
            "location": "",
            "acres": "",
            "source": "LandWatch",
        }

    return list(items.values())


def parse_landsearch(html: str, page_url: str) -> List[Dict]:
    soup = BeautifulSoup(html, "lxml")
    items: Dict[str, Dict] = {}

    # LandSearch listings often include "/properties/" links
    for a in soup.select("a[href*='/properties/']"):
        href = a.get("href")
        if not href:
            continue

        if href.startswith("/"):
            href = urljoin(page_url, href)

        text = a.get_text(" ", strip=True)
        title = (text[:160] if text else "LandSearch listing").strip()

        price = None
        m = re.search(r"\$[\d,]+", text)
        if m:
            price = money_to_int(m.group(0))

        items[href] = {
            "id": href,
            "title": title,
            "url": href,
            "price": price,
            "location": "",
            "acres": "",
            "source": "LandSearch",
        }

    return list(items.values())


def parse_listings(html: str, page_url: str) -> List[Dict]:
    host = urlparse(page_url).netloc.lower()

    if "landwatch.com" in host:
        return parse_landwatch(html, page_url)

    if "landsearch.com" in host:
        return parse_landsearch(html, page_url)

    return []


def load_data():
    if not os.path.exists(DATA_PATH):
        return {"last_updated_utc": None, "items": []}
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_data(data):
    os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def main():
    data = load_data()
    seen_ids = {item.get("id") for item in data.get("items", [])}

    all_listings: List[Dict] = []

    for url in SEARCH_URLS:
        try:
            html = safe_get(url)
            all_listings.extend(parse_listings(html, url))
        except Exception as e:
            print(f"Error scraping {url}: {e}")

    # Apply filters
    matches: List[Dict] = []
    for item in all_listings:
        price = item.get("price")
        if price is None:
            continue
        if price <= MAX_PRICE:
            matches.append(item)

    # Only new ones
    new_items = [m for m in matches if m.get("id") not in seen_ids]

    # Prepend new ones so newest show first
    data["items"] = new_items + data.get("items", [])
    data["last_updated_utc"] = datetime.now(timezone.utc).isoformat()

    save_data(data)

    print(f"Found {len(matches)} matches; added {len(new_items)} new.")


if __name__ == "__main__":
    main()
