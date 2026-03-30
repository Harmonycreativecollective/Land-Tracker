from typing import Any, Dict, List

from scrapers.common import (
    best_title,
    dedupe_by_url,
    extract_status_from_dict,
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

        items.append(
            {
                "source": "LandSearch",
                "title": best_title(d, "LandSearch"),
                "url": url,
                "price": price,
                "acres": acres,
                "thumbnail": try_thumbnail_from_dict(d),
                "status": extract_status_from_dict(d),
            }
        )

    return dedupe_by_url(items)
