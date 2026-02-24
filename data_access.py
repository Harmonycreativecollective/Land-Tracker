import os
from typing import Any, Dict, List, Optional, Tuple

from supabase import create_client


def _get_env(name: str) -> str:
    v = os.getenv(name)
    if v:
        return v
    raise RuntimeError(f"Missing required environment variable: {name}")


def get_supabase_client():
    # For the Streamlit app (READ ONLY), you can use anon key
    url = _get_env("SUPABASE_URL")
    key = _get_env("SUPABASE_ANON_KEY")  # <-- make sure this exists in secrets
    return create_client(url, key)


def get_items(limit: int = 2000) -> List[Dict[str, Any]]:
    sb = get_supabase_client()
    res = (
        sb.table("listings")
        .select(
            "listing_id,title,url,source,price,acres,status,thumbnail,found_utc,derived_state,derived_county,last_seen_utc,is_active,is_favorite"
        )
        .order("found_utc", desc=True)
        .limit(limit)
        .execute()
    )
    return res.data or []


def get_system_state() -> Dict[str, Any]:
    """
    Returns last_updated_utc / last_attempted_utc from scrape_runs.
    If scrape_runs is empty, falls back to max(last_seen_utc) from listings.
    """
    sb = get_supabase_client()

    # 1) Preferred: scrape_runs newest row
    try:
        run = (
            sb.table("scrape_runs")
            .select("run_utc,written,enriched")
            .order("run_utc", desc=True)
            .limit(1)
            .execute()
        )
        if run.data:
            latest = run.data[0]
            return {
                "last_updated_utc": latest.get("run_utc"),
                "last_attempted_utc": latest.get("run_utc"),
                "written": latest.get("written"),
                "enriched": latest.get("enriched"),
            }
    except Exception:
        pass

    # 2) Fallback: max last_seen_utc from listings
    try:
        mx = (
            sb.table("listings")
            .select("last_seen_utc")
            .order("last_seen_utc", desc=True)
            .limit(1)
            .execute()
        )
        if mx.data:
            return {
                "last_updated_utc": mx.data[0].get("last_seen_utc"),
                "last_attempted_utc": mx.data[0].get("last_seen_utc"),
            }
    except Exception:
        pass

    return {"last_updated_utc": None, "last_attempted_utc": None}


def get_app_settings() -> Dict[str, Any]:
    """
    Optional: if you made an app_settings table like we discussed.
    If you don't have this table yet, just return {}.
    """
    sb = get_supabase_client()
    try:
        res = sb.table("app_settings").select("*").limit(1).execute()
        return (res.data[0] if res.data else {}) or {}
    except Exception:
        return {}


def get_listings():
    return get_items()
