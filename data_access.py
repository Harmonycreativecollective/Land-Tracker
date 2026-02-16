from typing import Any, Dict, List
import streamlit as st
from supabase import create_client

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_ANON_KEY"]

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_items() -> List[Dict[str, Any]]:
    resp = supabase.table("listings").select("*").execute()
    return resp.data or []

def load_data() -> Dict[str, Any]:
    st.write("Reading from Supabase")
    items = get_items()

    return {
        "items": items,
        "criteria": {},
        "last_updated_utc": None,
    }

def get_listings() -> List[Dict[str, Any]]:
    return get_items()