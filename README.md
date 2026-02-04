# LinkedIn IEEE Company Scraper

A Python-based scraper using Playwright to extract company search results from LinkedIn for the keyword "IEEE".

## Features

- **Stealth Mode**: Uses `playwright-stealth` to avoid detection
- **Session Persistence**: Saves and reuses login sessions via `auth.json`
- **Multiple Selector Strategies**: Handles LinkedIn DOM changes gracefully
- **Human-like Behavior**: Random delays, scrolling, realistic navigation
- **Incremental Saves**: Progress saved every 5 pages
- **Debug Screenshots**: Captures screenshots when issues occur

## Prerequisites

- Python 3.10+
- A LinkedIn account

## Installation

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Install Playwright browsers
playwright install chromium
```

## Usage

### Step 1: Capture Authentication

First, run the auth capture script to save your LinkedIn session:

```bash
python auth_capture.py
```

This opens a browser window where you:
1. Log into LinkedIn manually
2. Complete any 2FA if prompted
3. Press ENTER in the terminal once logged in

This creates `auth.json` containing your session cookies.

### Step 2: Run the Scraper

```bash
# Scrape all 100 pages (with visible browser)
python linkedin_scraper.py

# Scrape specific page range
python linkedin_scraper.py --start-page 1 --end-page 10

# Run in headless mode (no visible browser)
python linkedin_scraper.py --headless
```

### Output Files

- `ieee_companies_final.csv` - All results in CSV format
- `ieee_companies_final.json` - All results in JSON format
- `ieee_companies_progress_p*.csv` - Incremental saves every 5 pages
- `debug_page_*.png` - Screenshots when pages fail to load

## Data Extracted

| Field | Description |
|-------|-------------|
| name | Company name |
| url | LinkedIn company page URL |
| subtitle | Industry/company type |
| followers | Follower count |
| location | Company location |
| page | Search result page number |
| position | Position on page |
| scraped_at | Timestamp of extraction |

## Troubleshooting

### "No results found" on pages

**Possible causes:**

1. **Session expired**: Re-run `python auth_capture.py` to refresh
2. **Commercial Use Limit**: LinkedIn limits searches for non-premium accounts. Try:
   - Wait 24 hours and try again
   - Use a LinkedIn Premium account
   - Reduce scraping speed (increase delays)
3. **Bot detection**: Run with `--headless=false` to see what's happening
4. **DOM changes**: LinkedIn may have updated their HTML. Check debug screenshots.

### Authentication wall

If you see login prompts, your session has expired. Re-run `auth_capture.py`.

### CAPTCHA

If CAPTCHA appears, you may need to:
1. Solve it manually (run without `--headless`)
2. Wait a few hours before retrying
3. Use a different IP/network

### Rate limiting tips

- Keep delays between pages (5-10 seconds minimum)
- Don't run multiple instances simultaneously
- Consider spreading scraping over multiple days
- Scrape during off-peak hours

## Limitations

- LinkedIn actively detects and blocks scraping
- Commercial use limits may restrict search results
- Selectors may break when LinkedIn updates their UI
- Not suitable for high-volume automated scraping

## Legal Notice

This tool is provided for educational purposes. Be aware that:
- Scraping LinkedIn may violate their Terms of Service
- Use responsibly and respect rate limits
- Consider using LinkedIn's official API for production use cases
