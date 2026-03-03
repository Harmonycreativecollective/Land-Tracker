import os
from collections import Counter

from dotenv import load_dotenv
from supabase import create_client


def _env(name: str) -> str:
    v = os.getenv(name)
    if not v:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return v


def main() -> None:
    load_dotenv()
    url = _env("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or _env("SUPABASE_ANON_KEY")
    sb = create_client(url, key)

    rows = (
        sb.table("listings")
        .select("status", count="exact")
        .eq("is_active", True)
        .limit(5000)
        .execute()
    ).data or []

    counts = Counter((str(r.get("status") or "unknown").strip().lower() or "unknown") for r in rows)
    print("Active listings:", len(rows))
    print("Status counts (active only):")
    for status, count in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
        print(f"  {status}: {count}")


if __name__ == "__main__":
    main()
