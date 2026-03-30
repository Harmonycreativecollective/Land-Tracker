from typing import Any, Dict, List

from scrapers.common import dedupe_by_url, extract_from_html_fallback, extract_from_jsonld, get_json_ld, is_lease_listing


SOURCE_NAME = "LandAndFarm"


def extract_landandfarm_listings(base_url: str, html: str) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    json_ld_blocks = get_json_ld(html)

    if json_ld_blocks:
        items.extend(extract_from_jsonld(base_url, json_ld_blocks, SOURCE_NAME))

    if not items:
        items.extend(extract_from_html_fallback(base_url, html, SOURCE_NAME))

    return dedupe_by_url([item for item in items if not is_lease_listing(item)])
