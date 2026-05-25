"""Fetches SEC filings (10-K, 10-Q, 8-K) via SEC EDGAR."""
import os
import re
from pathlib import Path

import requests

from config import DATA_CACHE_DIR

EDGAR_BASE = "https://data.sec.gov"
EDGAR_SEARCH = "https://efts.sec.gov/LATEST/search-index"
HEADERS = {"User-Agent": "financial-research-agent risheeksomu@gmail.com"}


def get_cik(ticker: str) -> Optional[str]:
    """Resolve a ticker to a CIK number from SEC EDGAR."""
    url = f"{EDGAR_BASE}/files/company_tickers.json"
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    ticker_upper = ticker.upper()
    for entry in data.values():
        if entry.get("ticker", "").upper() == ticker_upper:
            return str(entry["cik_str"]).zfill(10)
    return None


def get_recent_filings(ticker: str, form_type: str = "10-Q", count: int = 5) -> list[dict]:
    """Return recent filings for a ticker from EDGAR."""
    cik = get_cik(ticker)
    if not cik:
        return []

    url = f"{EDGAR_BASE}/submissions/CIK{cik}.json"
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    filings = data.get("filings", {}).get("recent", {})
    forms = filings.get("form", [])
    dates = filings.get("filingDate", [])
    accessions = filings.get("accessionNumber", [])
    primary_docs = filings.get("primaryDocument", [])

    results = []
    for i, form in enumerate(forms):
        if form == form_type and len(results) < count:
            accession = accessions[i].replace("-", "")
            doc = primary_docs[i]
            results.append({
                "form": form,
                "date": dates[i],
                "accession": accessions[i],
                "url": f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession}/{doc}",
            })
    return results


def fetch_filing_text(url: str) -> str:
    """Fetch the text content of an SEC filing (HTML stripped)."""
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(resp.text, "html.parser")
    for tag in soup(["script", "style", "table"]):
        tag.decompose()
    text = soup.get_text(separator="\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def get_filing_excerpt(ticker: str, form_type: str = "10-Q", max_chars: int = 8000) -> str:
    """Get the most recent filing text excerpt for a ticker."""
    filings = get_recent_filings(ticker, form_type=form_type, count=1)
    if not filings:
        return f"No {form_type} found for {ticker}"
    url = filings[0]["url"]
    text = fetch_filing_text(url)
    return text[:max_chars]


# make Optional importable since it's used in get_cik
from typing import Optional
