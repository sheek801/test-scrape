"""
Stock screener for AI/tech narrative themes.
Screens the configured thematic baskets against fundamental and momentum filters.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pandas as pd
import numpy as np
from rich.console import Console
from rich.table import Table
from rich import box
from typing import Optional

from config import THEMES, SCREENING_DEFAULTS
from data.fetchers.yahoo_finance import get_stock_info, get_price_history
from data.processors.normalizer import fmt_number, fmt_pct, fmt_multiple

console = Console()


def screen_theme(
    theme: str,
    min_market_cap_b: float = SCREENING_DEFAULTS["min_market_cap_b"],
    max_pe: float = SCREENING_DEFAULTS["max_pe"],
    min_revenue_growth: float = SCREENING_DEFAULTS["min_revenue_growth_yoy"],
    min_gross_margin: float = SCREENING_DEFAULTS["min_gross_margin"],
    sort_by: str = "revenue_growth",
) -> pd.DataFrame:
    """
    Screen all tickers in a theme and return a ranked DataFrame.
    sort_by options: revenue_growth | market_cap | gross_margin | pe_forward
    """
    if theme not in THEMES:
        raise ValueError(f"Unknown theme '{theme}'. Available: {list(THEMES.keys())}")

    tickers = THEMES[theme]["tickers"]
    console.print(f"[cyan]Screening {len(tickers)} tickers in '{theme}'...[/cyan]")

    rows = []
    for ticker in tickers:
        try:
            info = get_stock_info(ticker)
            rows.append(info)
        except Exception as e:
            console.print(f"[red]  {ticker}: {e}[/red]")

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    # Apply filters
    if "market_cap" in df.columns:
        df = df[df["market_cap"].fillna(0) >= min_market_cap_b * 1e9]
    if "pe_forward" in df.columns:
        # allow NaN (growth names with no earnings) but exclude extreme positives
        df = df[(df["pe_forward"].isna()) | (df["pe_forward"] <= max_pe)]
    if "revenue_growth" in df.columns:
        df = df[df["revenue_growth"].fillna(-999) >= min_revenue_growth]
    if "gross_margin" in df.columns:
        df = df[df["gross_margin"].fillna(0) >= min_gross_margin]

    if sort_by in df.columns:
        df = df.sort_values(sort_by, ascending=False)

    return df.set_index("ticker")


def momentum_screen(tickers: list[str], lookback: str = "3mo") -> pd.DataFrame:
    """
    Calculate price momentum for a list of tickers.
    Returns a DataFrame sorted by momentum (best performers first).
    """
    results = []
    for ticker in tickers:
        try:
            hist = get_price_history(ticker, period=lookback)
            if hist.empty or len(hist) < 5:
                continue
            start_price = hist["Close"].iloc[0]
            end_price = hist["Close"].iloc[-1]
            high = hist["Close"].max()
            low = hist["Close"].min()
            momentum = (end_price - start_price) / start_price
            from_high = (end_price - high) / high
            from_low = (end_price - low) / low
            avg_vol = hist["Volume"].mean()
            results.append({
                "ticker": ticker,
                "momentum": momentum,
                "from_52w_high": from_high,
                "from_52w_low": from_low,
                "current_price": end_price,
                "avg_volume": avg_vol,
            })
        except Exception as e:
            console.print(f"[red]  {ticker}: {e}[/red]")

    df = pd.DataFrame(results).set_index("ticker")
    return df.sort_values("momentum", ascending=False)


def print_screen_table(df: pd.DataFrame, theme: str) -> None:
    """Pretty-print a screening result as a rich table."""
    table = Table(
        title=f"[bold]{theme.replace('_', ' ').title()} — Screen Results[/bold]",
        box=box.ROUNDED,
        show_lines=True,
    )

    display_cols = {
        "name": "Company",
        "market_cap": "Mkt Cap",
        "price": "Price",
        "pe_forward": "Fwd P/E",
        "ps_ratio": "P/S",
        "revenue_growth": "Rev Growth",
        "gross_margin": "Gross Mgn",
        "operating_margin": "Op Mgn",
        "beta": "Beta",
    }

    table.add_column("Ticker", style="bold cyan", no_wrap=True)
    for col, header in display_cols.items():
        if col in df.columns:
            table.add_column(header, justify="right")

    for ticker, row in df.iterrows():
        values = [str(ticker)]
        for col in display_cols:
            if col not in df.columns:
                continue
            val = row.get(col)
            if col == "market_cap":
                values.append(fmt_number(val, prefix="$"))
            elif col == "price":
                values.append(f"${val:.2f}" if val else "N/A")
            elif col in ("revenue_growth", "gross_margin", "operating_margin"):
                values.append(fmt_pct(val))
            elif col in ("pe_forward", "ps_ratio", "ev_ebitda", "beta"):
                values.append(fmt_multiple(val, suffix="x" if col != "beta" else ""))
            else:
                values.append(str(val)[:30] if val else "N/A")
        table.add_row(*values)

    console.print(table)


def print_momentum_table(df: pd.DataFrame) -> None:
    """Pretty-print a momentum screen result."""
    table = Table(title="[bold]Momentum Screen[/bold]", box=box.ROUNDED)
    table.add_column("Ticker", style="bold cyan")
    table.add_column("Momentum", justify="right")
    table.add_column("From High", justify="right")
    table.add_column("From Low", justify="right")
    table.add_column("Price", justify="right")

    for ticker, row in df.iterrows():
        mom = row.get("momentum", 0)
        color = "green" if mom > 0 else "red"
        table.add_row(
            str(ticker),
            f"[{color}]{fmt_pct(mom)}[/{color}]",
            fmt_pct(row.get("from_52w_high")),
            fmt_pct(row.get("from_52w_low")),
            f"${row.get('current_price', 0):.2f}",
        )

    console.print(table)


def main():
    import click

    @click.group()
    def cli():
        """Stock Screener for AI/Tech Themes"""
        pass

    @cli.command()
    @click.argument("theme")
    @click.option("--sort", default="revenue_growth",
                  type=click.Choice(["revenue_growth", "market_cap", "gross_margin", "pe_forward"]))
    @click.option("--min-cap", default=0.5, help="Min market cap in billions")
    def screen(theme, sort, min_cap):
        """Screen a thematic basket. Themes: data_centers, photonics_optical, ai_chips, ai_software"""
        df = screen_theme(theme, min_market_cap_b=min_cap, sort_by=sort)
        if df.empty:
            console.print("[red]No results after filtering.[/red]")
            return
        print_screen_table(df, theme)

    @cli.command()
    @click.argument("theme")
    @click.option("--period", default="3mo", type=click.Choice(["1mo", "3mo", "6mo", "1y"]))
    def momentum(theme, period):
        """Run a momentum screen on a theme basket."""
        if theme not in THEMES:
            console.print(f"[red]Unknown theme. Available: {list(THEMES.keys())}[/red]")
            return
        tickers = THEMES[theme]["tickers"]
        console.print(f"[cyan]Calculating {period} momentum for {len(tickers)} tickers...[/cyan]")
        df = momentum_screen(tickers, lookback=period)
        print_momentum_table(df)

    @cli.command()
    def themes():
        """List available themes."""
        for name, data in THEMES.items():
            console.print(f"[bold cyan]{name}[/bold cyan]: {data['description']}")
            console.print(f"  Tickers: {', '.join(data['tickers'])}")

    cli()


if __name__ == "__main__":
    main()
