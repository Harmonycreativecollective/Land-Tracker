import re
from typing import Any, Dict, List

from bs4 import BeautifulSoup

from scrapers.common import (
    dedupe_by_url,
    extract_status_from_dict,
    is_bad_title,
    is_landsearch_listing_url,
    normalize_url,
    parse_acres,
    parse_money,
    try_thumbnail_from_dict,
    walk,
)


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

        title = (d.get("title") or d.get("name") or d.get("headline") or "").strip()
        if is_bad_title(title):
            title = "LandSearch listing"

        items.append(
            {
                "source": "LandSearch",
                "title": title,
                "url": url,
                "price": price,
                "acres": acres,
                "thumbnail": try_thumbnail_from_dict(d),
                "status": extract_status_from_dict(d),
            }
        )

    return dedupe_by_url(items)


def _extract_card_status(card) -> str:
    texts: List[str] = []
    for selector in (".preview__flag", ".preview-gallery__info"):
        for el in card.select(selector):
            txt = re.sub(r"\s+", " ", el.get_text(" ", strip=True)).strip().lower()
            if txt:
                texts.append(txt)

    for txt in texts:
        if txt == "pending":
            return "pending"
        if txt == "under contract":
            return "under_contract"

    return "unknown"


def extract_from_landsearch_html_cards(base_url: str, html: str) -> List[Dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    items: List[Dict[str, Any]] = []

    for card in soup.select("article.preview"):
        link = card.select_one("a.preview__link[href]") or card.select_one("a.preview-gallery__images[href]")
        if not link:
            continue

        url = normalize_url(base_url, str(link.get("href") or ""))
        if not url or not is_landsearch_listing_url(url):
            continue

        image = card.select_one(".preview-gallery__image img")
        raw_title = ""
        if image and image.get("alt"):
            raw_title = str(image.get("alt") or "").strip()
        title = raw_title if raw_title and not is_bad_title(raw_title) else "LandSearch listing"

        price = parse_money(card.select_one(".preview__title").get_text(" ", strip=True) if card.select_one(".preview__title") else None)
        acres = parse_acres(card.select_one(".preview__size").get_text(" ", strip=True) if card.select_one(".preview__size") else None)

        thumbnail = None
        if image:
            thumbnail = image.get("src") or image.get("data-src") or image.get("data-lazy")

        county = ""
        county_el = card.select_one(".preview__subterritory")
        if county_el:
            county = re.sub(r"\s+", " ", county_el.get_text(" ", strip=True)).strip()

        location = ""
        location_el = card.select_one(".preview__location")
        if location_el:
            location = re.sub(r"\s+", " ", location_el.get_text(" ", strip=True)).strip()

        items.append(
            {
                "source": "LandSearch",
                "title": title,
                "url": url,
                "price": price,
                "acres": acres,
                "thumbnail": thumbnail,
                "status": _extract_card_status(card),
                "county": county,
                "location": location,
            }
        )

    return dedupe_by_url(items)


def extract_landsearch_listings(base_url: str, html: str, next_data: dict | None) -> List[Dict[str, Any]]:
    if next_data:
        items = extract_from_landsearch_next(base_url, next_data)
        if items:
            return items

    return extract_from_landsearch_html_cards(base_url, html)
