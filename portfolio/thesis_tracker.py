"""
Investment thesis tracker.
Maintains structured thesis documents per position and scores them against news.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import json
from datetime import datetime
from pathlib import Path

import anthropic
import click
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from config import ANTHROPIC_API_KEY, CLAUDE_MODEL
from data.fetchers.yahoo_finance import get_stock_info, get_recent_news
from data.fetchers.news_feeds import get_latest_ai_tech_news
from data.processors.normalizer import stock_info_to_prompt_text

console = Console()
client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
THESES_FILE = Path(__file__).parent / "theses.json"


def load_theses() -> dict:
    if THESES_FILE.exists():
        return json.loads(THESES_FILE.read_text())
    return {}


def save_theses(data: dict) -> None:
    THESES_FILE.write_text(json.dumps(data, indent=2))


def create_thesis(ticker: str) -> str:
    """Use Claude to generate a structured thesis template for a ticker."""
    console.print(f"[cyan]Generating thesis for {ticker}...[/cyan]")
    info = get_stock_info(ticker)
    news = get_recent_news(ticker, limit=6)
    fundamentals = stock_info_to_prompt_text(info)
    news_text = "\n".join(f"- {n['title']}" for n in news if n.get("title"))

    prompt = f"""Create a structured investment thesis for {ticker}.

FUNDAMENTALS:
{fundamentals}

RECENT NEWS:
{news_text}

Format the thesis as a structured markdown document with:

# {ticker} Investment Thesis

## One-Line Pitch
[Single sentence encapsulating the bull case]

## AI/Tech Narrative Exposure
[How does this company benefit from AI, data centers, photonics, or related themes?]

## Business Model
[How does it make money? Key revenue drivers?]

## Bull Case
- [Key bull point 1]
- [Key bull point 2]
- [Key bull point 3]

## Bear Case / Key Risks
- [Key risk 1]
- [Key risk 2]

## Key Catalysts to Watch
- [Near-term catalyst 1]
- [Catalyst 2]

## Valuation Framework
[What multiple is justified? How does it compare to peers?]

## Exit Criteria
[Under what conditions would you sell? What would break the thesis?]

## Conviction Level
[High / Medium / Low — and why]"""

    with client.messages.stream(
        model=CLAUDE_MODEL,
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        return stream.get_final_text()


def score_thesis(ticker: str) -> str:
    """Score the existing thesis against current news and price action."""
    theses = load_theses()
    if ticker.upper() not in theses:
        return f"No thesis found for {ticker}. Run 'create {ticker}' first."

    thesis = theses[ticker.upper()]["thesis"]
    info = get_stock_info(ticker)
    news = get_recent_news(ticker, limit=8)
    macro_news = get_latest_ai_tech_news(limit=10)

    fundamentals = stock_info_to_prompt_text(info)
    ticker_news = "\n".join(f"- {n['title']}" for n in news if n.get("title"))
    macro_text = "\n".join(f"- {a['title']}" for a in macro_news[:8])

    prompt = f"""Score this investment thesis for {ticker} against current news and data.

ORIGINAL THESIS:
{thesis}

CURRENT FUNDAMENTALS:
{fundamentals}

RECENT TICKER NEWS:
{ticker_news}

MACRO AI/TECH NEWS:
{macro_text}

Provide a thesis scorecard:

## Thesis Health Check — {ticker}

**Overall Score**: [1-10] — [One-line verdict]

**What's going right** (supporting the thesis):
- [Point 1]
- [Point 2]

**What's going wrong** (challenging the thesis):
- [Point 1]
- [Point 2]

**Thesis status**: [INTACT / WEAKENING / BROKEN / STRENGTHENING]

**Recommended action**: [Hold / Add / Trim / Exit — with reasoning]

**Updated conviction**: [High / Medium / Low]"""

    with client.messages.stream(
        model=CLAUDE_MODEL,
        max_tokens=1200,
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        return stream.get_final_text()


@click.group()
def cli():
    """Investment thesis tracker."""
    pass


@cli.command()
@click.argument("ticker")
def create(ticker):
    """Generate a structured investment thesis for a ticker."""
    ticker = ticker.upper()
    thesis = create_thesis(ticker)

    data = load_theses()
    data[ticker] = {
        "thesis": thesis,
        "created": datetime.now().isoformat(),
        "updated": datetime.now().isoformat(),
    }
    save_theses(data)

    console.print(Panel(Markdown(thesis), title=f"[bold green]{ticker} Investment Thesis[/bold green]"))
    console.print(f"[green]Thesis saved to {THESES_FILE}[/green]")


@cli.command()
@click.argument("ticker")
def score(ticker):
    """Score the existing thesis against current news."""
    result = score_thesis(ticker.upper())
    console.print(Panel(Markdown(result), title=f"[bold yellow]{ticker.upper()} Thesis Scorecard[/bold yellow]"))


@cli.command()
def list():
    """List all tracked theses."""
    data = load_theses()
    if not data:
        console.print("[yellow]No theses saved yet.[/yellow]")
        return
    for ticker, meta in data.items():
        console.print(f"[bold cyan]{ticker}[/bold cyan] — added {meta.get('created','')[:10]}")


@cli.command()
@click.argument("ticker")
def show(ticker):
    """Display the full thesis for a ticker."""
    data = load_theses()
    if ticker.upper() not in data:
        console.print(f"[red]No thesis for {ticker.upper()}.[/red]")
        return
    thesis = data[ticker.upper()]["thesis"]
    console.print(Panel(Markdown(thesis), title=f"[bold]{ticker.upper()} Thesis[/bold]"))


if __name__ == "__main__":
    cli()
