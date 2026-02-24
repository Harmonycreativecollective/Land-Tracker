# KB’s Land Tracker

A lightweight land listings tracker powered by a Python scraper + Streamlit dashboard.

---

## Version History / Changelog

### v0.1 — Initial Build (Scraper MVP)
- [x] Created initial Python scraper to pull land listings from configured URLs  
- [x] Output saved to Output initially saved to data/listings.json (deprecated in v2.0.0; replaced with Supabase storage)  
- [x] Repo set up on GitHub  
- [x] GitHub Actions workflow created to automate runs on a schedule  

---

### v0.2 — Dashboard MVP (Streamlit)
- [x] Built initial Streamlit dashboard (`dashboard.py`)  
- [x] Loads listings from `data/listings.json`  
- [x] Displays listing title, acreage, price (when available), source, and link  
- [x] Added basic search + filter logic  

---

### v0.3 — Branding + UI Upgrade (Dashboard Styling)
- [x] Created/exported custom KB logo (PNG) inspired by William’s stuffed animal gift  
- [x] Added logo to repo: `assets/kblogo.png`  
- [x] Updated Streamlit page config to use logo as favicon/tab icon  
  - `page_icon="assets/kblogo.png"`  
- [x] Built branded dashboard header (logo + title side-by-side, mobile-friendly)  
- [x] Added mission caption:  
  - “What’s meant for you is already in motion.”  

---

## What’s Next (Planned)
- [ ] Favorites / saved listings  
- [ ] Notifications (email) for new listings only  
- [ ] Add more listing sources (more URLs/sites)  
- [ ] Better “NEW” logic (timestamps like `first_seen_utc`)  
- [ ] Domain mapping (cleaner URL)  
- [ ] Custom placeholder image/card when preview is unavailable

---

## 🆕 Version Updates (Continued)

### v0.4 — Matching Logic & Buyer Criteria
- [x] Implemented buyer-specific land criteria based on stated preferences
  - **Acreage:** 10–50 acres
  - **Price cap:** $600,000
- [x] Added match classification logic:
  - **✨ Top Match** — Meets acreage *and* price criteria and is available
  - **🧩 Possible Match** — Meets acreage but price is missing
  - **🔎 Found** — All other discovered listings
- [x] Excluded unavailable listings (pending / under contract / sold) from Top Matches

---

### v0.5 — Status Awareness & Historical Tracking
- [x] Added listing status support:
  - Available
  - Under Contract
  - Pending
  - Sold
  - Unknown
- [x] Introduced persistent historical tracking via `ever_top_match`
- [x] Added **Former Top Match** logic:
  - Listings that were once Top Matches but later became unavailable
- [x] Ensured historical flags persist across scraper runs

---

### v0.6 — Filters, Sorting & UX Improvements
- [x] Added collapsible **Filters** panel:
  - ✨ Top Matches only (default ON)
  - 🧩 Include Possible Matches
  - ⭐ Include Former Top Matches
  - 🆕 New listings only
  - Adjustable acreage and price inputs
- [x] Added full-text search (title / location / source / URL)
- [x] Implemented priority-based sorting:
  1. Top Matches  
  2. Possible Matches  
  3. Former Top Matches  
  4. Other listings
- [x] Added “Newest first” sorting using discovery timestamps

---

### v0.7 — Visual Branding & Placeholder Handling
- [x] Added branded dashboard header:
  - Custom KB logo
  - Title and mission caption
- [x] Created and integrated a **custom placeholder image** for listings without previews
- [x] Improved placeholder styling:
  - Rounded card layout
  - Overlay label (“Preview not available”)
  - Mobile-safe sizing
- [x] Prevented broken or empty image cards from disrupting layout

---

### v0.8 — Multi-County Expansion & URL Standardization
- [x] Expanded search coverage within ~1.5 hours of Washington, DC
- [x] Added county-level searches across:
  - **Virginia:** King George, Westmoreland, Caroline, Stafford
  - **Maryland:** Caroline, Frederick, Anne Arundel, Montgomery
- [x] Standardized scraper inputs to **clean county URLs only**
- [x] Centralized all filtering logic inside the app (not in source URLs)

---

### v0.9 — Automation, Deduplication & Data Reliability
- [x] Implemented automated scraping via GitHub Actions
- [x] Added deduplication safeguards across:
  - Counties
- [x] Normalized acreage and price parsing across sources
- [x] Preserved:
- [x] First-seen timestamps (`found_utc`)
- [x] Listing status across runs
- [x] Historical Top Match state

- [x]  Streamlit app deployed and publicly accessible
- [x]  Listings refresh automatically via scraper workflow 
- [x]  App accurately displays:
  - Active Top Matches
  - Possible Matches
  - Former Top Matches


---

### v2.0.0 — Supabase Backend & Production Architecture

- Migrated listings storage from `data/listings.json` to Supabase database
- Introduced `scrape_runs` table to track:
  - `last_updated_utc`
  - `last_attempted_utc`
  - listings written per run
- Refactored app to use shared `data_access.py` for centralized DB reads
- Removed manual scraping from public app (read-only frontend)
- Separated environments:
  - Streamlit uses Supabase ANON key (read-only)
  - GitHub Actions uses Service Role key (write access)
- Updated GitHub Actions workflow to write directly to Supabase
- Eliminated JSON commit conflicts and snapshot-based data model
- Established stable production pipeline:

  GitHub Actions (Scraper) → Supabase (Database) → Streamlit (Public UI)

  ### ✅ Current Status

- Supabase-backed production architecture
- Scraper runs automatically every 3 hours via GitHub Actions
- Public Streamlit app reads from database (no manual scraping)
- Branching workflow established (`main` stable, feature branches for development)

System is production-stable and ready for:

- Favorites / saved listings
- URL paste / add listing feature
- Cross-site canonical deduplication (LandSearch + LandWatch)
- Optional custom domain mapping
