"""Normalizes and formats raw financial data for display and LLM prompts."""
import pandas as pd
from typing import Any


def fmt_number(n: Any, prefix: str = "", suffix: str = "", decimals: int = 2) -> str:
    if n is None or (isinstance(n, float) and pd.isna(n)):
        return "N/A"
    try:
        n = float(n)
    except (TypeError, ValueError):
        return "N/A"

    if abs(n) >= 1e12:
        return f"{prefix}{n/1e12:.{decimals}f}T{suffix}"
    if abs(n) >= 1e9:
        return f"{prefix}{n/1e9:.{decimals}f}B{suffix}"
    if abs(n) >= 1e6:
        return f"{prefix}{n/1e6:.{decimals}f}M{suffix}"
    return f"{prefix}{n:.{decimals}f}{suffix}"


def fmt_pct(n: Any, decimals: int = 1) -> str:
    if n is None or (isinstance(n, float) and pd.isna(n)):
        return "N/A"
    try:
        return f"{float(n)*100:.{decimals}f}%"
    except (TypeError, ValueError):
        return "N/A"


def fmt_multiple(n: Any, suffix: str = "x") -> str:
    if n is None or (isinstance(n, float) and pd.isna(n)):
        return "N/A"
    try:
        return f"{float(n):.1f}{suffix}"
    except (TypeError, ValueError):
        return "N/A"


def stock_info_to_prompt_text(info: dict) -> str:
    """Convert a stock info dict to a compact text block for an LLM."""
    lines = [
        f"Ticker: {info.get('ticker','?')} — {info.get('name','')}",
        f"Sector: {info.get('sector','')} | Industry: {info.get('industry','')}",
        f"Market Cap: {fmt_number(info.get('market_cap'), prefix='$')}",
        f"Price: ${info.get('price','N/A')} | 52W Range: ${info.get('52w_low','?')} - ${info.get('52w_high','?')}",
        f"P/E (TTM): {fmt_multiple(info.get('pe_trailing'))} | P/E (Fwd): {fmt_multiple(info.get('pe_forward'))}",
        f"EV/EBITDA: {fmt_multiple(info.get('ev_ebitda'))} | P/S: {fmt_multiple(info.get('ps_ratio'))}",
        f"Revenue (TTM): {fmt_number(info.get('revenue_ttm'), prefix='$')}",
        f"Gross Margin: {fmt_pct(info.get('gross_margin'))} | Op Margin: {fmt_pct(info.get('operating_margin'))}",
        f"Revenue Growth YoY: {fmt_pct(info.get('revenue_growth'))}",
        f"Free Cash Flow: {fmt_number(info.get('free_cash_flow'), prefix='$')}",
        f"Beta: {fmt_multiple(info.get('beta'), suffix='')}",
        f"Short Float: {fmt_pct(info.get('short_float'))}",
        "",
        f"Description: {info.get('description','')}",
    ]
    return "\n".join(lines)


def comparison_df_to_text(df: pd.DataFrame) -> str:
    """Turn a comparison DataFrame into a readable text table."""
    cols = ["name", "market_cap", "price", "pe_forward", "ps_ratio", "revenue_growth", "gross_margin"]
    available = [c for c in cols if c in df.columns]
    subset = df[available].copy()
    return subset.to_string()
