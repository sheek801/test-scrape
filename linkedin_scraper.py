#!/usr/bin/env python3
"""
LinkedIn IEEE Company Search Scraper

Scrapes company search results from LinkedIn for the keyword "IEEE".
Uses Playwright with stealth to avoid detection.

Prerequisites:
    1. Run: pip install -r requirements.txt
    2. Run: playwright install chromium
    3. Run: python auth_capture.py (to create auth.json)

Usage:
    python linkedin_scraper.py [--start-page 1] [--end-page 100] [--headless]
"""

import asyncio
import argparse
import json
import random
import os
from datetime import datetime
from pathlib import Path

import pandas as pd
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
from playwright_stealth import stealth_async


class LinkedInCompanyScraper:
    """Scrapes LinkedIn company search results with anti-detection measures."""

    BASE_URL = "https://www.linkedin.com/search/results/companies/"
    SEARCH_PARAMS = "?keywords=ieee&origin=SWITCH_SEARCH_VERTICAL&spellCorrectionEnabled=true"

    # Multiple selector strategies - LinkedIn changes DOM frequently
    SELECTORS = {
        # Primary selectors (as of late 2024/early 2025)
        'result_container': [
            'li.reusable-search__result-container',
            'div.search-results-container li',
            '[data-chameleon-result-urn]',
            '.entity-result',
        ],
        'company_name': [
            '.entity-result__title-text a span[aria-hidden="true"]',
            '.entity-result__title-text a span:first-child',
            '.app-aware-link span[aria-hidden="true"]',
            'a[data-test-app-aware-link] span',
        ],
        'company_link': [
            '.entity-result__title-text a',
            'a.app-aware-link[href*="/company/"]',
            '.entity-result a[href*="/company/"]',
        ],
        'subtitle': [
            '.entity-result__primary-subtitle',
            '.entity-result__summary',
            '.linked-area .t-14',
        ],
        'secondary_subtitle': [
            '.entity-result__secondary-subtitle',
            '.entity-result__caption',
        ],
        'followers': [
            '.entity-result__secondary-subtitle',
            '.entity-result__caption',
            'span:has-text("follower")',
        ],
    }

    def __init__(self, headless: bool = False):
        self.headless = headless
        self.results = []
        self.browser = None
        self.context = None
        self.page = None

    async def _random_delay(self, min_sec: float = 2.0, max_sec: float = 5.0):
        """Human-like random delay."""
        delay = random.uniform(min_sec, max_sec)
        await asyncio.sleep(delay)

    async def _human_scroll(self):
        """Simulate human scrolling behavior to trigger lazy loading."""
        # Scroll down in chunks
        for _ in range(random.randint(3, 5)):
            scroll_amount = random.randint(200, 400)
            await self.page.mouse.wheel(0, scroll_amount)
            await asyncio.sleep(random.uniform(0.3, 0.7))

        # Scroll back up a bit (humans do this)
        await self.page.mouse.wheel(0, -random.randint(50, 150))
        await asyncio.sleep(random.uniform(0.2, 0.5))

        # Scroll to bottom to ensure all content loads
        await self.page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
        await asyncio.sleep(random.uniform(1.0, 2.0))

    async def _try_selectors(self, selectors: list, parent=None) -> list:
        """Try multiple selectors and return first successful result."""
        target = parent if parent else self.page
        for selector in selectors:
            try:
                elements = await target.query_selector_all(selector)
                if elements:
                    return elements
            except Exception:
                continue
        return []

    async def _try_selector_single(self, selectors: list, parent=None) -> any:
        """Try multiple selectors and return first match."""
        target = parent if parent else self.page
        for selector in selectors:
            try:
                element = await target.query_selector(selector)
                if element:
                    return element
            except Exception:
                continue
        return None

    async def _extract_text(self, element, selectors: list) -> str:
        """Extract text from element using multiple selector strategies."""
        el = await self._try_selector_single(selectors, element)
        if el:
            text = await el.text_content()
            return text.strip() if text else ""
        return ""

    async def _extract_href(self, element, selectors: list) -> str:
        """Extract href from element using multiple selector strategies."""
        el = await self._try_selector_single(selectors, element)
        if el:
            href = await el.get_attribute('href')
            if href:
                # Clean up the URL
                if href.startswith('/'):
                    return f"https://www.linkedin.com{href.split('?')[0]}"
                return href.split('?')[0]
        return ""

    async def _wait_for_results(self) -> bool:
        """Wait for search results to load with multiple strategies."""
        # Strategy 1: Wait for any result container
        for selector in self.SELECTORS['result_container']:
            try:
                await self.page.wait_for_selector(selector, timeout=10000)
                return True
            except PlaywrightTimeout:
                continue

        # Strategy 2: Wait for network idle
        try:
            await self.page.wait_for_load_state('networkidle', timeout=15000)
            return True
        except PlaywrightTimeout:
            pass

        # Strategy 3: Check for "no results" message
        no_results_selectors = [
            'text="No results found"',
            '.search-reusable-search-no-results',
            'text="We didn\'t find anyone"',
        ]
        for selector in no_results_selectors:
            try:
                if await self.page.query_selector(selector):
                    return False
            except Exception:
                continue

        return False

    async def _check_for_blocks(self) -> dict:
        """Check for LinkedIn blocks or restrictions."""
        checks = {
            'blocked': False,
            'auth_wall': False,
            'commercial_limit': False,
            'message': None
        }

        # Check for authentication wall
        if '/login' in self.page.url or '/checkpoint' in self.page.url:
            checks['auth_wall'] = True
            checks['message'] = "Authentication required - session may have expired"
            return checks

        # Check for commercial use limit
        commercial_limit_selectors = [
            'text="You\'ve reached the commercial use limit"',
            'text="commercial use limit"',
            '.search-paywall',
        ]
        for selector in commercial_limit_selectors:
            try:
                if await self.page.query_selector(selector):
                    checks['commercial_limit'] = True
                    checks['message'] = "LinkedIn commercial use limit reached"
                    return checks
            except Exception:
                continue

        # Check for CAPTCHA
        captcha_selectors = [
            '#captcha',
            '.captcha',
            'iframe[src*="captcha"]',
        ]
        for selector in captcha_selectors:
            try:
                if await self.page.query_selector(selector):
                    checks['blocked'] = True
                    checks['message'] = "CAPTCHA detected - manual intervention required"
                    return checks
            except Exception:
                continue

        return checks

    async def _extract_company_data(self, result_element) -> dict:
        """Extract company data from a single search result element."""
        company = {
            'name': '',
            'url': '',
            'subtitle': '',  # Usually industry/type
            'followers': '',
            'location': '',
            'scraped_at': datetime.now().isoformat()
        }

        # Extract company name
        company['name'] = await self._extract_text(result_element, self.SELECTORS['company_name'])

        # If name not found, try to get it from the link text
        if not company['name']:
            link_el = await self._try_selector_single(self.SELECTORS['company_link'], result_element)
            if link_el:
                text = await link_el.text_content()
                company['name'] = text.strip() if text else ""

        # Extract company URL
        company['url'] = await self._extract_href(result_element, self.SELECTORS['company_link'])

        # Extract subtitle (industry/type)
        company['subtitle'] = await self._extract_text(result_element, self.SELECTORS['subtitle'])

        # Extract secondary subtitle (often contains followers/location)
        secondary = await self._extract_text(result_element, self.SELECTORS['secondary_subtitle'])
        if secondary:
            # Parse followers if present
            if 'follower' in secondary.lower():
                company['followers'] = secondary
            else:
                company['location'] = secondary

        return company

    async def scrape_page(self, page_num: int) -> list:
        """Scrape a single page of search results."""
        url = f"{self.BASE_URL}{self.SEARCH_PARAMS}&page={page_num}"
        print(f"\n[Page {page_num}] Navigating to: {url}")

        try:
            # Navigate with realistic timeout
            await self.page.goto(url, wait_until='domcontentloaded', timeout=30000)
            await self._random_delay(2, 4)

            # Check for blocks
            block_status = await self._check_for_blocks()
            if block_status['auth_wall'] or block_status['blocked'] or block_status['commercial_limit']:
                print(f"[Page {page_num}] WARNING: {block_status['message']}")
                return []

            # Scroll to trigger lazy loading
            await self._human_scroll()

            # Wait for results
            has_results = await self._wait_for_results()
            if not has_results:
                print(f"[Page {page_num}] No results found or page empty")
                # Take debug screenshot
                await self.page.screenshot(path=f'debug_page_{page_num}.png')
                return []

            # Find all result containers
            results = await self._try_selectors(self.SELECTORS['result_container'])
            print(f"[Page {page_num}] Found {len(results)} result containers")

            if not results:
                # Debug: print page content summary
                content = await self.page.content()
                print(f"[Page {page_num}] DEBUG: Page length = {len(content)} chars")
                await self.page.screenshot(path=f'debug_page_{page_num}.png')
                return []

            # Extract data from each result
            page_companies = []
            for i, result in enumerate(results):
                try:
                    company = await self._extract_company_data(result)
                    if company['name']:  # Only add if we got a name
                        company['page'] = page_num
                        company['position'] = i + 1
                        page_companies.append(company)
                        print(f"  [{i+1}] {company['name']}")
                except Exception as e:
                    print(f"  [{i+1}] Error extracting: {e}")
                    continue

            return page_companies

        except PlaywrightTimeout as e:
            print(f"[Page {page_num}] Timeout: {e}")
            return []
        except Exception as e:
            print(f"[Page {page_num}] Error: {e}")
            return []

    async def run(self, start_page: int = 1, end_page: int = 100):
        """Run the scraper across specified page range."""
        if not Path('auth.json').exists():
            print("ERROR: auth.json not found!")
            print("Please run 'python auth_capture.py' first to capture your LinkedIn session.")
            return

        async with async_playwright() as p:
            # Launch browser with anti-detection measures
            self.browser = await p.chromium.launch(
                headless=self.headless,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-infobars',
                    '--window-position=0,0',
                    '--ignore-certificate-errors',
                    '--ignore-certificate-errors-spki-list',
                ]
            )

            # Create context with saved authentication
            self.context = await self.browser.new_context(
                storage_state='auth.json',
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                locale='en-US',
                timezone_id='America/New_York',
                java_script_enabled=True,
            )

            self.page = await self.context.new_page()

            # Apply stealth
            await stealth_async(self.page)

            # Additional stealth: override navigator properties
            await self.page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['en-US', 'en']
                });
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5]
                });
            """)

            print("="*60)
            print("LinkedIn IEEE Company Scraper")
            print("="*60)
            print(f"Scraping pages {start_page} to {end_page}")
            print(f"Headless mode: {self.headless}")
            print("="*60)

            # Warm up: visit LinkedIn homepage first
            print("\nWarming up session...")
            await self.page.goto('https://www.linkedin.com/feed/', wait_until='domcontentloaded')
            await self._random_delay(3, 5)

            # Scrape each page
            for page_num in range(start_page, end_page + 1):
                page_results = await self.scrape_page(page_num)
                self.results.extend(page_results)

                # Save progress incrementally
                if page_num % 5 == 0:
                    self._save_results(f'ieee_companies_progress_p{page_num}.csv')

                # Random delay between pages (longer than within-page delays)
                if page_num < end_page:
                    delay = random.uniform(5, 10)
                    print(f"Waiting {delay:.1f}s before next page...")
                    await asyncio.sleep(delay)

            # Final save
            self._save_results('ieee_companies_final.csv')
            self._save_results_json('ieee_companies_final.json')

            await self.browser.close()

            print("\n" + "="*60)
            print("SCRAPING COMPLETE")
            print("="*60)
            print(f"Total companies scraped: {len(self.results)}")
            print("Files saved: ieee_companies_final.csv, ieee_companies_final.json")

    def _save_results(self, filename: str):
        """Save results to CSV."""
        if not self.results:
            print(f"No results to save to {filename}")
            return
        df = pd.DataFrame(self.results)
        df.to_csv(filename, index=False)
        print(f"Saved {len(self.results)} results to {filename}")

    def _save_results_json(self, filename: str):
        """Save results to JSON."""
        if not self.results:
            return
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False)


def main():
    parser = argparse.ArgumentParser(description='LinkedIn IEEE Company Scraper')
    parser.add_argument('--start-page', type=int, default=1, help='Starting page number (default: 1)')
    parser.add_argument('--end-page', type=int, default=100, help='Ending page number (default: 100)')
    parser.add_argument('--headless', action='store_true', help='Run browser in headless mode')
    args = parser.parse_args()

    scraper = LinkedInCompanyScraper(headless=args.headless)
    asyncio.run(scraper.run(args.start_page, args.end_page))


if __name__ == '__main__':
    main()
