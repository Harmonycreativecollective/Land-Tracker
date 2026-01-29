import json
import os
import re
from datetime import datetime, timezone
from typing import Dict, List

import requests
from bs4 import BeautifulSoup

DATA_PATH = "data/listings.json"

MAX_PRICE = 20000

# ✅ Put saved-search URLs here
SEARCH_URLS = [
    # "https://example.com/search?...",
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

def parse_generic(html: str, page_url: str) -> List[Dict]:
    soup = BeautifulSoup(html, "lxml")
    listings = []

    # Generic selectors (will vary per site)
    for card in soup.select(".listing, .listing-card, .result, [data-listing]"):
        a = card.select_one("a[href]")
        if not a:
            continue

        href = a["href"]
        if href.startswith("/"):
            from urllib.parse import urljoin
            href = urljoin(page_url, href)

        title = (a.get_text(" ", strip=True) or "Land listing").strip()

        price_el = card.select_one(".price, [data-price], .listing-price")
        price = money_to_int(price_el.get_text(strip=True)) if price_el else None

        location_el = card.select_one(".location, .city, [data-location]")
        location = location_el.get_text(" ", strip=True) if location_el else ""

        acres_el = card.select_one(".acres, [data-acres]")
        acres = acres_el.get_text(" ", strip=True) if acres_el else ""

        listings.append({
            "id": href,
            "title": title,
            "url": href,
            "price": price,
            "location": location,
            "acres": acres
        })

    return listings

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
    seen_ids = {item["id"] for item in data.get("items", [])}

    all_listings = []
    for url in SEARCH_URLS:
        html = safe_get(url)
        all_listings.extend(parse_generic(html, url))

    matches = []
    for item in all_listings:
        if item.get("price") is None:
            continue
        if item["price"] <= MAX_PRICE:
            matches.append(item)

    new_items = [m for m in matches if m["id"] not in seen_ids]

    data["items"] = new_items + data.get("items", [])
    data["last_updated_utc"] = datetime.now(timezone.utc).isoformat()
    save_data(data)

    print(f"Found {len(matches)} matches; added {len(new_items)} new.")

if __name__ == "__main__":
    main()
