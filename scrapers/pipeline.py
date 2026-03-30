from typing import Any, Dict, List

from scrapers.common import STATUS_VALUES, dedupe_by_url, detect_status, is_bad_title, is_lease_listing, is_top_match_now, should_enrich


def finalize_scraped_items(
    all_items: List[Dict[str, Any]],
    old_map: Dict[str, Dict[str, Any]],
    run_utc: str,
    min_acres: float,
    max_acres: float,
    max_price: int,
) -> List[Dict[str, Any]]:
    final: List[Dict[str, Any]] = []

    for item in dedupe_by_url(all_items):
        url = item.get("url")
        if not url:
            continue

        prev = old_map.get(url, {})
        current = dict(item)
        current["listing_id"] = current.get("listing_id") or url
        current["found_utc"] = prev.get("found_utc") or current.get("found_utc") or run_utc
        current["ever_top_match"] = bool(prev.get("ever_top_match", False))

        if is_bad_title(current.get("title")):
            current["title"] = f"{current.get('source', 'Listing')} listing"

        status = detect_status(str(current.get("status") or ""))
        current["status"] = status if status in STATUS_VALUES else "unknown"

        if is_lease_listing(current):
            continue

        final.append(current)

    final.sort(key=lambda item: item.get("found_utc") or "", reverse=True)
    final.sort(
        key=lambda item: (
            0 if is_top_match_now(item, min_acres, max_acres, max_price) else 1,
            0 if should_enrich(item) else 1,
        )
    )
    return final



def finalize_enriched_items(
    items: List[Dict[str, Any]],
    min_acres: float,
    max_acres: float,
    max_price: int,
) -> List[Dict[str, Any]]:
    final = [dict(item) for item in items if not is_lease_listing(item)]

    for item in final:
        status = (item.get("status") or "unknown").lower()
        if status not in STATUS_VALUES:
            item["status"] = "unknown"

        if not item.get("listing_id"):
            item["listing_id"] = item.get("url")

        if not item.get("ever_top_match") and is_top_match_now(item, min_acres, max_acres, max_price):
            item["ever_top_match"] = True

    return final



def to_row(item: Dict[str, Any], run_utc: str) -> Dict[str, Any]:
    listing_id = item.get("listing_id") or item.get("url")
    status = detect_status(str(item.get("status") or ""))
    if status not in STATUS_VALUES:
        status = "unknown"
    return {
        "listing_id": listing_id,
        "title": item.get("title"),
        "url": item.get("url"),
        "source": item.get("source"),
        "price": item.get("price"),
        "acres": item.get("acres"),
        "status": status,
        "thumbnail": item.get("thumbnail"),
        "found_utc": item.get("found_utc") or run_utc,
        "derived_state": item.get("derived_state"),
        "derived_county": item.get("derived_county"),
        "last_seen_utc": run_utc,
        "is_active": True,
    }
