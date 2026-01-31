# KB’s Land Tracker

A lightweight land listings tracker powered by a Python scraper + Streamlit dashboard.

---

## Version History / Changelog

### v0.1 — Initial Build (Scraper MVP)
- [x] Created initial Python scraper to pull land listings from configured URLs  
- [x] Output saved to `data/listings.json`  
- [x] Repo set up on GitHub  
- [x] GitHub Actions workflow created to automate runs on a schedule  

---

### v0.2 — Dashboard MVP (Streamlit)
- [x] Built initial Streamlit dashboard (`app.py`)  
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