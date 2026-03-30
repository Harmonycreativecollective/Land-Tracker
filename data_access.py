import os
from typing import Any, Dict, List, Optional, Set, Tuple

from dotenv import load_dotenv
from supabase import create_client
import streamlit as st

load_dotenv()


def _get_env(name: str) -> str:
    # Prefer Streamlit Cloud secrets when available, then env/.env fallback.
    v = None
    try:
        if name in st.secrets:
            v = str(st.secrets[name])
    except Exception:
        v = None
    if not v:
        v = os.getenv(name)
    if v:
        return str(v).strip()
    raise RuntimeError(f"Missing required environment variable: {name}")


def get_supabase_client():
    # For the Streamlit app (READ ONLY), you can use anon key
    url = _get_env("SUPABASE_URL")
    key = _get_env("SUPABASE_ANON_KEY")  # <-- make sure this exists in secrets
    return create_client(url, key)


def get_supabase_writer_client():
    # Favorites writes use anon key + explicit table grants.
    return get_supabase_client()


def get_favorites_user_key() -> str:
    try:
        if "FAVORITES_USER_KEY" in st.secrets:
            return str(st.secrets["FAVORITES_USER_KEY"]).strip() or "kb_owner"
    except Exception:
        pass
    return (os.getenv("FAVORITES_USER_KEY", "kb_owner") or "kb_owner").strip()


def get_items(limit: int = 2000) -> List[Dict[str, Any]]:
    sb = get_supabase_client()
    res = (
        sb.table("listings")
        .select(
            "listing_id,title,url,source,price,acres,status,thumbnail,found_utc,derived_state,derived_county,last_seen_utc,is_active,is_favorite"
        )
        .eq("is_active", True)
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


def get_listings(limit: int = 2000):
    return get_items(limit=limit)


def get_favorite_listing_ids(user_key: Optional[str] = None) -> Set[str]:
    sb = get_supabase_client()
    key = user_key or get_favorites_user_key()
    try:
        res = (
            sb.table("favorites")
            .select("listing_id")
            .eq("user_key", key)
            .limit(5000)
            .execute()
        )
        rows = res.data or []
        return {str(r.get("listing_id")) for r in rows if r.get("listing_id")}
    except Exception:
        return set()


def get_favorite_records(user_key: Optional[str] = None) -> Dict[str, Any]:
    sb = get_supabase_client()
    key = user_key or get_favorites_user_key()
    try:
        res = (
            sb.table("favorites")
            .select("listing_id,created_at")
            .eq("user_key", key)
            .limit(5000)
            .execute()
        )
        rows = res.data or []
        return {str(r.get("listing_id")): r.get("created_at") for r in rows if r.get("listing_id")}
    except Exception:
        return {}


def add_favorite(listing_id: str, user_key: Optional[str] = None) -> Tuple[bool, str]:
    if not listing_id:
        return (False, "missing listing_id")
    sb = get_supabase_writer_client()
    key = user_key or get_favorites_user_key()
    try:
        sb.table("favorites").upsert(
            {"user_key": key, "listing_id": listing_id},
            on_conflict="user_key,listing_id",
        ).execute()
        return (True, "")
    except Exception as e:
        return (False, f"failed to save favorite: {e}")


def remove_favorite(listing_id: str, user_key: Optional[str] = None) -> Tuple[bool, str]:
    if not listing_id:
        return (False, "missing listing_id")
    sb = get_supabase_writer_client()
    key = user_key or get_favorites_user_key()
    try:
        (
            sb.table("favorites")
            .delete()
            .eq("user_key", key)
            .eq("listing_id", listing_id)
            .execute()
        )
        return (True, "")
    except Exception as e:
        return (False, f"failed to remove favorite: {e}")
