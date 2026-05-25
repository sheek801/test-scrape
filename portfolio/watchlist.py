"""
Watchlist manager — track your AI/tech positions and theses.
Stores entries in a local JSON file with thesis notes.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import json
from datetime import datetime
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table
from rich import box

from data.fetchers.yahoo_finance import get_stock_info
from data.processors.normalizer import fmt_number, fmt_pct, fmt_multiple

console = Console()
WATCHLIST_FILE = Path(__file__).parent / "watchlist.json"


def load_watchlist() -> dict:
    if WATCHLIST_FILE.exists():
        return json.loads(WATCHLIST_FILE.read_text())
    return {}


def save_watchlist(data: dict) -> None:
    WATCHLIST_FILE.write_text(json.dumps(data, indent=2))


def add_to_watchlist(ticker: str, thesis: str, theme: str = "", conviction: str = "medium") -> None:
    """Add a ticker to the watchlist with a thesis note."""
    data = load_watchlist()
    data[ticker.upper()] = {
        "thesis": thesis,
        "theme": theme,
        "conviction": conviction,
        "added": datetime.now().isoformat(),
        "alerts": [],
    }
    save_watchlist(data)
    console.print(f"[green]Added {ticker.upper()} to watchlist.[/green]")


def remove_from_watchlist(ticker: str) -> None:
    data = load_watchlist()
    if ticker.upper() in data:
        del data[ticker.upper()]
        save_watchlist(data)
        console.print(f"[yellow]Removed {ticker.upper()} from watchlist.[/yellow]")
    else:
        console.print(f"[red]{ticker.upper()} not in watchlist.[/red]")


def show_watchlist() -> None:
    """Print a live-updated watchlist with current prices."""
    data = load_watchlist()
    if not data:
        console.print("[yellow]Watchlist is empty. Use 'add' to add tickers.[/yellow]")
        return

    table = Table(title="[bold]Watchlist[/bold]", box=box.ROUNDED, show_lines=True)
    table.add_column("Ticker", style="bold cyan", no_wrap=True)
    table.add_column("Company", max_width=22)
    table.add_column("Theme")
    table.add_column("Conv.", justify="center")
    table.add_column("Price", justify="right")
    table.add_column("Mkt Cap", justify="right")
    table.add_column("Fwd P/E", justify="right")
    table.add_column("Rev Growth", justify="right")
    table.add_column("Thesis", max_width=35)

    conviction_colors = {"high": "green", "medium": "yellow", "low": "red"}

    for ticker, meta in data.items():
        try:
            info = get_stock_info(ticker)
            price = f"${info.get('price', 0):.2f}" if info.get("price") else "N/A"
            mkt_cap = fmt_number(info.get("market_cap"), prefix="$")
            fwd_pe = fmt_multiple(info.get("pe_forward"))
            rev_growth = fmt_pct(info.get("revenue_growth"))
            name = (info.get("name") or "")[:22]
        except Exception:
            price = mkt_cap = fwd_pe = rev_growth = "ERR"
            name = ""

        conv = meta.get("conviction", "medium")
        conv_display = f"[{conviction_colors.get(conv, 'white')}]{conv.upper()}[/{conviction_colors.get(conv, 'white')}]"

        table.add_row(
            ticker,
            name,
            meta.get("theme", ""),
            conv_display,
            price,
            mkt_cap,
            fwd_pe,
            rev_growth,
            meta.get("thesis", "")[:35],
        )

    console.print(table)


def add_alert(ticker: str, note: str) -> None:
    """Add a price alert or note to a watchlist entry."""
    data = load_watchlist()
    if ticker.upper() not in data:
        console.print(f"[red]{ticker.upper()} not in watchlist.[/red]")
        return
    data[ticker.upper()]["alerts"].append({
        "note": note,
        "added": datetime.now().isoformat(),
    })
    save_watchlist(data)
    console.print(f"[green]Alert added to {ticker.upper()}.[/green]")


@click.group()
def cli():
    """Watchlist manager for AI/tech equity positions."""
    pass


@cli.command()
@click.argument("ticker")
@click.argument("thesis")
@click.option("--theme", default="", help="e.g. data_centers, photonics_optical, ai_chips")
@click.option("--conviction", default="medium", type=click.Choice(["high", "medium", "low"]))
def add(ticker, thesis, theme, conviction):
    """Add a ticker with a thesis. Example: add NVDA 'AI datacenter supercycle beneficiary' --theme ai_chips --conviction high"""
    add_to_watchlist(ticker, thesis, theme=theme, conviction=conviction)


@cli.command()
@click.argument("ticker")
def remove(ticker):
    """Remove a ticker from the watchlist."""
    remove_from_watchlist(ticker)


@cli.command()
def show():
    """Show the current watchlist with live prices."""
    show_watchlist()


@cli.command()
@click.argument("ticker")
@click.argument("note")
def alert(ticker, note):
    """Add a note/alert to a watchlist entry."""
    add_alert(ticker, note)


if __name__ == "__main__":
    cli()
