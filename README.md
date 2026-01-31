# KB's Land-Tracker

v0.1 — Initial Build (Scraper MVP)
✅ Created initial Python scraper to pull land listings from configured URLs
✅ Output saved to data/listings.json
✅ Repo set up on GitHub
✅ GitHub Actions workflow created to automate runs on schedule
v0.2 — Dashboard MVP (Streamlit)
✅ Built initial Streamlit dashboard (app.py)
✅ Loads listings from data/listings.json
✅ Displays listing title, acreage, price (when available), source, and link
✅ Added basic search + filter logic
v0.3 — Branding + UI Upgrade (Dashboard Styling)
✅ Created/exported custom KB logo (PNG) inspired by William’s stuffed animal gift
✅ Added logo to repo: assets/kblogo.png
✅ Updated Streamlit page config to use logo as favicon/tab icon
(page_icon="assets/kblogo.png")
✅ Built branded dashboard header (logo + title side-by-side, mobile-friendly)
✅ Added mission caption/statement:
“What’s meant for you is already in motion.”
v0.4 — Listing Display Improvements
✅ Fixed listings that showed generic “Land listing”
✅ Added smart fallback titles when missing:
“{Source} listing” (ex: “LandSearch listing”)
✅ Added listing thumbnails when available
✅ Added “No preview available” placeholder card when thumbnail cannot be pulled
v0.5 — Filters + Badge Logic Cleanup (UX Refinement)
✅ Removed unnecessary STRICT match mode
✅ Kept only Top match filtering based on criteria (max price + acreage range)
✅ Converted filters into cleaner checkbox/toggle system:
✅ Top matches only
✅ New only
✅ Default view loads with Top matches only ON
✅ Confirmed newest listings show first in results
✅ Simplified badges for clarity:
⭐ Top match
🆕 NEW
FOUND
✅ Updated ⭐ Top match badge to display consistently whenever criteria is met (not dependent on view mode)
🔜 Next Planned Releases
v0.6 — First-Seen Tracking (NEW Accuracy)
⏳ Add persistent found_utc timestamps per listing (first time seen)
⏳ NEW badge becomes truly accurate (based on found_utc)
⏳ Improve dedup logic across runs (stable listing counts)
v0.7 — Notifications (Email)
⏳ Email notifications for new Top matches
⏳ Use Google Workspace for sending alerts
⏳ Create “sent log” to prevent duplicate notifications
v0.8 — Favorites / Saved Listings
⏳ Viewer can favorite/save listings
⏳ Favorites persist across refresh (file/database)
⏳ Dedicated Favorites view/tab
v1.0 — Multi-Source Expansion + Polished Dashboard
⏳ Add more listing sources + regions
⏳ Improve match scoring logic (deal-breakers + preferences)
⏳ Optional map view (if location data becomes available)
⏳ Full “real product” dashboard feel