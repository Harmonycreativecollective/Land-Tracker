from data_access import load_data

data = load_data()
items = data.get("items", []) or []
criteria = data.get("criteria", {}) or {}
last_updated = data.get("last_updated_utc")

