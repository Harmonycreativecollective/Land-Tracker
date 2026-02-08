import json
from pathlib import Path
from typing import Any, Dict, List

DATA_PATH = Path("data/listings.json")

def load_data() -> Dict[str, Any]:
    if not DATA_PATH.exists():
        return {"items": [], "criteria": {}, "last_updated_utc": None}
    return json.loads(DATA_PATH.read_text(encoding="utf-8"))

def get_items() -> List[Dict[str, Any]]:
    return load_data().get("items", []) or []

