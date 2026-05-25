"""
Earnings call and filing analyzer.
Extracts AI/tech narrative signals from earnings transcripts and SEC filings.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import anthropic
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from config import ANTHROPIC_API_KEY, CLAUDE_MODEL
from data.fetchers.yahoo_finance import get_stock_info, get_earnings_history, get_recent_news
from data.fetchers.sec_filings import get_filing_excerpt
from data.processors.normalizer import stock_info_to_prompt_text

console = Console()
client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# Keyword signals to look for in filings and calls
AI_SIGNALS = [
    "AI", "artificial intelligence", "GPU", "inference", "training",
    "data center", "cloud", "capex", "capital expenditure", "photonics",
    "optical", "interconnect", "accelerator", "foundation model",
    "sovereign AI", "enterprise AI", "AI-driven", "generative AI",
]


def analyze_recent_filing(ticker: str, form_type: str = "10-Q") -> str:
    """
    Fetch the most recent SEC filing and analyze it for AI/tech signals.
    """
    console.print(f"[cyan]Fetching {form_type} for {ticker}...[/cyan]")
    info = get_stock_info(ticker)
    fundamentals = stock_info_to_prompt_text(info)

    filing_text = get_filing_excerpt(ticker, form_type=form_type, max_chars=6000)

    prompt = f"""Analyze this {form_type} filing excerpt from {ticker} for investment-relevant signals.

COMPANY FUNDAMENTALS:
{fundamentals}

FILING EXCERPT:
{filing_text}

Provide:
1. **AI/Tech Narrative Signals** — Count and quote specific mentions of AI, data center, GPU, photonics etc.
   How bullish is management on these themes? Is this genuine or buzzword inflation?
2. **Financial Health Signals** — Any concerning trends in revenue, margins, cash flow, or guidance?
3. **Risk Factors** — What are the most material risks mentioned?
4. **Bull Case Validation** — Does this filing support or undermine a bullish thesis on AI exposure?
5. **Model Update** — If you were updating an equity model, what 2-3 numbers would you revise?

Be specific — quote the filing where relevant."""

    console.print(f"[cyan]Analyzing {form_type} with Claude...[/cyan]")
    with client.messages.stream(
        model=CLAUDE_MODEL,
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        return stream.get_final_text()


def pre_earnings_setup(ticker: str) -> str:
    """
    Pre-earnings setup: what to watch, consensus expectations, scenario analysis.
    """
    info = get_stock_info(ticker)
    earnings = get_earnings_history(ticker)
    news = get_recent_news(ticker, limit=6)
    fundamentals = stock_info_to_prompt_text(info)
    news_text = "\n".join(f"- {n['title']}" for n in news if n.get("title"))

    prompt = f"""Create a pre-earnings setup note for {ticker}.

FUNDAMENTALS:
{fundamentals}

NEXT EARNINGS: {earnings.get('next_earnings', 'N/A')}

RECENT NEWS FLOW:
{news_text}

Write a pre-earnings brief covering:
1. **The setup** — What does the stock need to do to rally vs. sell off?
2. **Key metrics to watch** — Top 3-4 numbers the market is focused on (revenue, margins, guidance, bookings)
3. **Consensus bar** — Is the bar high or low? What's the whisper?
4. **AI narrative check** — What commentary from management would validate or break the AI thesis?
5. **Trade setup** — Bull case (+X%), base case (flat), bear case (-X%) with specific price levels
6. **Options play** — Given implied vol, is there a defined-risk options structure worth considering?"""

    console.print(f"[cyan]Building pre-earnings setup...[/cyan]")
    with client.messages.stream(
        model=CLAUDE_MODEL,
        max_tokens=1800,
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        return stream.get_final_text()


def main():
    import click

    @click.group()
    def cli():
        """Earnings and Filing Analyzer"""
        pass

    @cli.command()
    @click.argument("ticker")
    @click.option("--form", default="10-Q", type=click.Choice(["10-K", "10-Q", "8-K"]))
    def filing(ticker, form):
        """Analyze the most recent SEC filing for AI/tech signals."""
        result = analyze_recent_filing(ticker.upper(), form_type=form)
        console.print(Panel(Markdown(result), title=f"[bold green]{ticker.upper()} {form} Analysis[/bold green]"))

    @cli.command()
    @click.argument("ticker")
    def preearnings(ticker):
        """Build a pre-earnings setup note."""
        result = pre_earnings_setup(ticker.upper())
        console.print(Panel(Markdown(result), title=f"[bold yellow]{ticker.upper()} Pre-Earnings Setup[/bold yellow]"))

    cli()


if __name__ == "__main__":
    main()
