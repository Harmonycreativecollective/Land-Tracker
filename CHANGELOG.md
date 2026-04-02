# Changelog

## 2026-04-02
- Improved listing status detection for active sale, auction, and detail-page signals
- Improved LandSearch list-page extraction and card status parsing
- Prioritized richer detail-page enrichment during scraping
- Refactored scraper pipeline by source and expanded blocked-site experiments
- Updated scraper workflow to report per-source counts
- Continued scraper modularization into shared pipeline and site-specific modules
- Fixed Streamlit column index errors
- Improved mobile-first UI and favorites workflow

## 2026-03-29 — v3 (merged to main)
- Introduced Playwright experimentation branch
- Began testing browser-based scraping for blocked sources (LandWatch, LandAndFarm)
- Preserved LandSearch request-based scraping
- Kept blocked sources disabled by default

## 2026-02 — v2
- Implemented strict Top Match filtering (status must be available)
- Added favorites system (single-user, Supabase)
- Improved scraper status normalization
- Fixed inactive listings being misclassified as active

## 2026-01 — v1
- Initial LandSearch scraper implemented
- Basic dashboard and listing display
- JSON-based data storage
