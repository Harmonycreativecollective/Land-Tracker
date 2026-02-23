import os
import json
from pathlib import Path
from typing import Any, Dict, List

import streamlit as st
from supabase import create_client


def get_secret(name: str) -> str:
    # Streamlit Cloud secrets
    if name in st.secrets:
        return st.secrets[name]

    # Local dev fallback
    value = os.getenv(name)
    if value:
        return value

    raise KeyError(f"Missing required secret: {name}")


SUPABASE_URL = get_secret("SUPABASE_URL")
SUPABASE_KEY = get_secret("SUPABASE_ANON_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


DATA_PATH = Path("data/listings.json")


def load_data() -> Dict[str, Any]:
    if not DATA_PATH.exists():
        return {"items": [], "criteria": {}, "last_updated_utc": None}
    return json.loads(DATA_PATH.read_text(encoding="utf-8"))


def get_items() -> List[Dict[str, Any]]:
    response = supabase.table("listings").select("*").execute()
    return response.data or []


def get_listings():
    return get_items()