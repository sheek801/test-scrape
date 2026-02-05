#!/usr/bin/env python3
"""
LinkedIn IEEE Group Search Scraper

Scrapes group search results from LinkedIn for the keyword "IEEE".
Uses Playwright with stealth to avoid detection.

Prerequisites:
    1. Run: pip install -r requirements.txt
    2. Run: playwright install chromium
    3. Run: python auth_capture.py (to create auth.json)

Usage:
    python linkedin_groups_scraper.py [--start-page 1] [--end-page 100] [--headless]
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

# Try to import stealth - handle different package versions
try:
    from playwright_stealth import stealth_async
    STEALTH_AVAILABLE = True
except ImportError:
    try:
        from playwright_stealth import Stealth
        STEALTH_AVAILABLE = "class"
    except ImportError:
        STEALTH_AVAILABLE = False


async def apply_stealth(page):
    """Apply anti-detection measures to the page."""
    if STEALTH_AVAILABLE == True:
        await stealth_async(page)
    elif STEALTH_AVAILABLE == "class":
        stealth = Stealth()
        await stealth.apply_stealth_async(page)
    else:
        await page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
            Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
            window.chrome = {runtime: {}};
        """)


class LinkedInGroupScraper:
    """Scrapes LinkedIn group search results with anti-detection measures."""

    BASE_URL = "https://www.linkedin.com/search/results/groups/"
    SEARCH_PARAMS = "?keywords=ieee&origin=SWITCH_SEARCH_VERTICAL&sid=(Hg"

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
        for _ in range(random.randint(3, 5)):
            scroll_amount = random.randint(200, 400)
            await self.page.mouse.wheel(0, scroll_amount)
            await asyncio.sleep(random.uniform(0.3, 0.7))

        await self.page.mouse.wheel(0, -random.randint(50, 150))
        await asyncio.sleep(random.uniform(0.2, 0.5))

        await self.page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
        await asyncio.sleep(random.uniform(1.0, 2.0))

    async def _get_result_containers(self) -> list:
        """Get all search result containers using multiple selector strategies."""
        selectors = [
            'li.reusable-search__result-container',
            '.search-results-container li.reusable-search__result-container',
            'ul.reusable-search__entity-result-list > li',
            '[data-chameleon-result-urn]',
        ]
        for selector in selectors:
            try:
                elements = await self.page.query_selector_all(selector)
                if elements:
                    return elements
            except Exception:
                continue
        return []

    async def _wait_for_results(self) -> bool:
        """Wait for search results to load with multiple strategies."""
        result_selectors = [
            'li.reusable-search__result-container',
            '[data-chameleon-result-urn]',
            '.entity-result',
        ]

        for selector in result_selectors:
            try:
                await self.page.wait_for_selector(selector, timeout=10000)
                return True
            except PlaywrightTimeout:
                continue

        try:
            await self.page.wait_for_load_state('networkidle', timeout=15000)
            return True
        except PlaywrightTimeout:
            pass

        no_results_selectors = [
            'text="No results found"',
            '.search-reusable-search-no-results',
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

        if '/login' in self.page.url or '/checkpoint' in self.page.url:
            checks['auth_wall'] = True
            checks['message'] = "Authentication required - session may have expired"
            return checks

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

        page_content = await self.page.content()
        captcha_indicators = [
            'challenge/verify' in self.page.url,
            '/checkpoint/' in self.page.url,
            'captcha-internal' in page_content.lower(),
            'security verification' in page_content.lower(),
        ]

        if any(captcha_indicators):
            checks['blocked'] = True
            checks['message'] = "Security challenge detected"
            return checks

        return checks

    async def _extract_group_data(self, result_element) -> dict:
        """Extract group data from a single search result element."""
        group = {
            'group_name': '',
            'members': '',
            'url': '',
            'scraped_at': datetime.now().isoformat()
        }

        # Get all text content for fallback parsing
        full_text = await result_element.text_content()
        lines = [line.strip() for line in full_text.split('\n') if line.strip()]

        # Strategy 1: Find the group link (href contains /groups/)
        group_link = await result_element.query_selector('a[href*="/groups/"]')
        if group_link:
            href = await group_link.get_attribute('href')
            if href:
                group['url'] = f"https://www.linkedin.com{href.split('?')[0]}" if href.startswith('/') else href.split('?')[0]

            # Get group name from the link's visible text
            name_span = await group_link.query_selector('span[aria-hidden="true"]')
            if name_span:
                group['group_name'] = (await name_span.text_content()).strip()
            else:
                link_text = await group_link.text_content()
                if link_text:
                    group['group_name'] = link_text.strip().split('\n')[0].strip()

        # Strategy 2: Parse group name from text lines if link method failed
        if not group['group_name'] and lines:
            for line in lines:
                if not any(skip in line.lower() for skip in ['member', 'join', 'joined']):
                    group['group_name'] = line
                    break

        # Extract members from primary subtitle
        subtitle_el = await result_element.query_selector('.entity-result__primary-subtitle')
        if subtitle_el:
            subtitle_text = await subtitle_el.text_content()
            if subtitle_text and 'member' in subtitle_text.lower():
                group['members'] = subtitle_text.strip()

        # Fallback: search all text for member count
        if not group['members']:
            for line in lines:
                if 'member' in line.lower():
                    group['members'] = line.strip()
                    break

        return group

    async def scrape_page(self, page_num: int) -> list:
        """Scrape a single page of search results."""
        url = f"{self.BASE_URL}{self.SEARCH_PARAMS}&page={page_num}"
        print(f"\n[Page {page_num}] Navigating to: {url}")

        try:
            await self.page.goto(url, wait_until='domcontentloaded', timeout=30000)
            await self._random_delay(2, 4)

            block_status = await self._check_for_blocks()
            if block_status['auth_wall'] or block_status['blocked']:
                print(f"[Page {page_num}] WARNING: {block_status['message']}")
                print("[!] Please solve any challenge in the browser window, then press ENTER to continue...")
                await self.page.screenshot(path=f'debug_groups_page_{page_num}.png')
                input()
                await self.page.goto(url, wait_until='domcontentloaded', timeout=30000)
                await self._random_delay(2, 4)
            elif block_status['commercial_limit']:
                print(f"[Page {page_num}] WARNING: {block_status['message']}")
                print("[!] Commercial limit reached. Consider waiting 24h or using LinkedIn Premium.")
                return []

            await self._human_scroll()

            has_results = await self._wait_for_results()
            if not has_results:
                print(f"[Page {page_num}] No results found or page empty")
                await self.page.screenshot(path=f'debug_groups_page_{page_num}.png')
                return []

            results = await self._get_result_containers()
            print(f"[Page {page_num}] Found {len(results)} result containers")

            if not results:
                content = await self.page.content()
                print(f"[Page {page_num}] DEBUG: Page length = {len(content)} chars")
                await self.page.screenshot(path=f'debug_groups_page_{page_num}.png')
                return []

            page_groups = []
            for i, result in enumerate(results):
                try:
                    group = await self._extract_group_data(result)
                    if group['group_name']:
                        group['page'] = page_num
                        group['position'] = i + 1
                        page_groups.append(group)
                        print(f"  [{i+1}] {group['group_name']} - {group['members']}")
                except Exception as e:
                    print(f"  [{i+1}] Error extracting: {e}")
                    continue

            return page_groups

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

            self.context = await self.browser.new_context(
                storage_state='auth.json',
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                locale='en-US',
                timezone_id='America/New_York',
                java_script_enabled=True,
            )

            self.page = await self.context.new_page()

            await apply_stealth(self.page)

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
            print("LinkedIn IEEE Group Scraper")
            print("="*60)
            print(f"Scraping pages {start_page} to {end_page}")
            print(f"Headless mode: {self.headless}")
            print("="*60)

            print("\nWarming up session...")
            await self.page.goto('https://www.linkedin.com/feed/', wait_until='domcontentloaded')
            await self._random_delay(3, 5)

            for page_num in range(start_page, end_page + 1):
                page_results = await self.scrape_page(page_num)
                self.results.extend(page_results)

                if page_num % 5 == 0:
                    self._save_results(f'ieee_groups_progress_p{page_num}.csv')

                if page_num < end_page:
                    delay = random.uniform(5, 10)
                    print(f"Waiting {delay:.1f}s before next page...")
                    await asyncio.sleep(delay)

            self._save_results('ieee_groups_final.csv')
            self._save_results_json('ieee_groups_final.json')

            await self.browser.close()

            print("\n" + "="*60)
            print("SCRAPING COMPLETE")
            print("="*60)
            print(f"Total groups scraped: {len(self.results)}")
            print("Files saved: ieee_groups_final.csv, ieee_groups_final.json")

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
    parser = argparse.ArgumentParser(description='LinkedIn IEEE Group Scraper')
    parser.add_argument('--start-page', type=int, default=1, help='Starting page number (default: 1)')
    parser.add_argument('--end-page', type=int, default=100, help='Ending page number (default: 100)')
    parser.add_argument('--headless', action='store_true', help='Run browser in headless mode')
    args = parser.parse_args()

    scraper = LinkedInGroupScraper(headless=args.headless)
    asyncio.run(scraper.run(args.start_page, args.end_page))


if __name__ == '__main__':
    main()
