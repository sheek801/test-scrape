"""Fetches price, fundamentals, and news from Yahoo Finance via yfinance."""
import json
import os
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd
import yfinance as yf

from config import DATA_CACHE_DIR


def get_stock_info(ticker: str) -> dict:
    """Return key fundamentals and metadata for a ticker."""
    t = yf.Ticker(ticker)
    info = t.info
    return {
        "ticker": ticker,
        "name": info.get("longName", ""),
        "sector": info.get("sector", ""),
        "industry": info.get("industry", ""),
        "market_cap": info.get("marketCap"),
        "price": info.get("currentPrice") or info.get("regularMarketPrice"),
        "pe_trailing": info.get("trailingPE"),
        "pe_forward": info.get("forwardPE"),
        "ps_ratio": info.get("priceToSalesTrailing12Months"),
        "ev_ebitda": info.get("enterpriseToEbitda"),
        "revenue_ttm": info.get("totalRevenue"),
        "gross_margin": info.get("grossMargins"),
        "operating_margin": info.get("operatingMargins"),
        "net_margin": info.get("profitMargins"),
        "revenue_growth": info.get("revenueGrowth"),
        "earnings_growth": info.get("earningsGrowth"),
        "free_cash_flow": info.get("freeCashflow"),
        "cash": info.get("totalCash"),
        "debt": info.get("totalDebt"),
        "beta": info.get("beta"),
        "52w_high": info.get("fiftyTwoWeekHigh"),
        "52w_low": info.get("fiftyTwoWeekLow"),
        "avg_volume": info.get("averageVolume"),
        "short_float": info.get("shortPercentOfFloat"),
        "description": info.get("longBusinessSummary", "")[:500],
    }


def get_price_history(
    ticker: str,
    period: str = "6mo",
    interval: str = "1d",
) -> pd.DataFrame:
    """Return OHLCV history as a DataFrame."""
    t = yf.Ticker(ticker)
    df = t.history(period=period, interval=interval)
    df.index = df.index.tz_localize(None)
    return df


def get_recent_news(ticker: str, limit: int = 10) -> list[dict]:
    """Return recent news headlines for a ticker."""
    t = yf.Ticker(ticker)
    news = t.news or []
    results = []
    for item in news[:limit]:
        content = item.get("content", {})
        results.append({
            "title": content.get("title", item.get("title", "")),
            "publisher": content.get("provider", {}).get("displayName", ""),
            "url": content.get("canonicalUrl", {}).get("url", ""),
            "published": content.get("pubDate", ""),
            "summary": content.get("summary", ""),
        })
    return results


def get_earnings_history(ticker: str) -> dict:
    """Return earnings history and next earnings date."""
    t = yf.Ticker(ticker)
    try:
        cal = t.earnings_dates
        if cal is not None and not cal.empty:
            upcoming = cal[cal.index > pd.Timestamp.now()].tail(1)
            next_date = upcoming.index[0].strftime("%Y-%m-%d") if not upcoming.empty else "N/A"
        else:
            next_date = "N/A"
    except Exception:
        next_date = "N/A"

    try:
        hist = t.quarterly_earnings
        earnings_data = hist.to_dict() if hist is not None else {}
    except Exception:
        earnings_data = {}

    return {"next_earnings": next_date, "quarterly": earnings_data}


def get_institutional_holders(ticker: str) -> pd.DataFrame:
    """Return top institutional holders."""
    t = yf.Ticker(ticker)
    try:
        return t.institutional_holders or pd.DataFrame()
    except Exception:
        return pd.DataFrame()


def get_options_chain(ticker: str) -> dict:
    """Return the nearest expiry options chain (calls + puts)."""
    t = yf.Ticker(ticker)
    try:
        expirations = t.options
        if not expirations:
            return {}
        nearest = expirations[0]
        chain = t.option_chain(nearest)
        return {
            "expiry": nearest,
            "calls": chain.calls[["strike", "lastPrice", "bid", "ask", "volume", "openInterest", "impliedVolatility"]].to_dict("records"),
            "puts": chain.puts[["strike", "lastPrice", "bid", "ask", "volume", "openInterest", "impliedVolatility"]].to_dict("records"),
        }
    except Exception:
        return {}


def compare_tickers(tickers: list[str]) -> pd.DataFrame:
    """Return a comparison DataFrame of key metrics for a list of tickers."""
    rows = []
    for t in tickers:
        try:
            info = get_stock_info(t)
            rows.append(info)
        except Exception as e:
            rows.append({"ticker": t, "error": str(e)})
    df = pd.DataFrame(rows).set_index("ticker")
    return df
