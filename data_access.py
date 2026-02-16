import os
from supabase import create_client
import streamlit as st

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_ANON_KEY"]

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

import json
from pathlib import Path
from typing import Any, Dict, List

DATA_PATH = Path("data/listings.json")

def load_data() -> Dict[str, Any]:
    if not DATA_PATH.exists():
        return {"items": [], "criteria": {}, "last_updated_utc": None}
    return json.loads(DATA_PATH.read_text(encoding="utf-8"))

def get_items() -> List[Dict[str, Any]]:
    response = supabase.table("listings").select("*").execute()
    if response.data:
        return response.data
    return []

def get_listings():
    return get_items()  
