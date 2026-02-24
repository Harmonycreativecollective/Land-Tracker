[1mdiff --git a/scraper.py b/scraper.py[m
[1mindex 734a572..d06ef2b 100644[m
[1m--- a/scraper.py[m
[1m+++ b/scraper.py[m
[36m@@ -10,8 +10,25 @@[m [mfrom bs4 import BeautifulSoup[m
 [m
 from supabase import create_client[m
 [m
[32m+[m[32mimport streamlit as st[m
[32m+[m[32mfrom supabase import create_client[m
[32m+[m
[32m+[m
[32m+[m[32mdef get_secret(name: str) -> str:[m
[32m+[m[32m    # 1) Try Streamlit Cloud secrets[m
[32m+[m[32m    if name in st.secrets:[m
[32m+[m[32m        return st.secrets[name][m
[32m+[m
[32m+[m[32m    # 2) Fallback to environment variables (local dev)[m
[32m+[m[32m    value = os.getenv(name)[m
[32m+[m[32m    if value:[m
[32m+[m[32m        return value[m
[32m+[m
[32m+[m[32m    raise KeyError(f"Missing required secret: {name}")[m
 [m
 [m
[32m+[m[32mSUPABASE_URL = get_secret("SUPABASE_URL")[m
[32m+[m[32mSUPABASE_KEY = get_secret("SUPABASE_ANON_KEY")  # or SERVICE_ROLE_KEY if needed[m
 [m
 supabase = create_client(SUPABASE_URL, SUPABASE_KEY)[m
 # ====== YOUR SETTINGS ======[m
