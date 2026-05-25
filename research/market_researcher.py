"""
Claude-powered market researcher.
Produces sector overviews, company deep-dives, and narrative analysis
for AI/tech equity themes (data centers, photonics, AI chips, etc.).
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import anthropic
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from config import ANTHROPIC_API_KEY, CLAUDE_MODEL, THEMES
from data.fetchers.yahoo_finance import get_stock_info, get_recent_news, get_earnings_history
from data.fetchers.news_feeds import get_latest_ai_tech_news, format_news_for_prompt
from data.processors.normalizer import stock_info_to_prompt_text

console = Console()
client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


SYSTEM_PROMPT = """You are a senior equity research analyst specializing in AI infrastructure,
semiconductors, and technology companies. You think in themes and narratives — understanding
how capital flows through the AI supply chain from chip designers to power companies to
software platforms. You provide rigorous, actionable investment analysis grounded in
fundamentals but with a clear view on the narrative and momentum driving valuations.

Your output should be structured like a professional research note:
- Lead with the key thesis in 1-2 sentences
- Cover the bull/bear case clearly
- Flag specific catalysts and risks
- Use specific numbers and comparisons where possible
- Be direct about conviction level"""


def research_company(ticker: str, depth: str = "standard") -> str:
    """
    Generate a research note on a single company.
    depth: 'quick' | 'standard' | 'deep'
    """
    console.print(f"[cyan]Fetching data for {ticker}...[/cyan]")

    info = get_stock_info(ticker)
    news = get_recent_news(ticker, limit=8)
    earnings = get_earnings_history(ticker)

    fundamentals_text = stock_info_to_prompt_text(info)

    news_text = "\n".join(
        f"- {n['title']} ({n['publisher']})" for n in news if n.get("title")
    ) or "No recent news found."

    depth_instructions = {
        "quick": "Write a 200-word quick take: key thesis, one risk, and a price target range.",
        "standard": "Write a 500-word research note with thesis, bull/bear case, catalysts, key risks, and valuation commentary.",
        "deep": "Write a comprehensive 800-word research note covering: investment thesis, market position and competitive moat, AI/tech narrative exposure, financial analysis, bull/bear scenarios, key catalysts, risks, and valuation framework.",
    }.get(depth, "Write a 500-word research note.")

    prompt = f"""Research {ticker} for me.

FUNDAMENTALS:
{fundamentals_text}

RECENT NEWS:
{news_text}

NEXT EARNINGS: {earnings.get('next_earnings', 'N/A')}

{depth_instructions}

Focus specifically on the company's exposure to AI, data center, or photonics themes where relevant."""

    console.print(f"[cyan]Generating research note ({depth})...[/cyan]")

    with client.messages.stream(
        model=CLAUDE_MODEL,
        max_tokens=2000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        result = stream.get_final_text()

    return result


def research_sector(theme: str) -> str:
    """
    Generate a sector overview for a named theme from config.THEMES.
    """
    if theme not in THEMES:
        available = ", ".join(THEMES.keys())
        return f"Unknown theme '{theme}'. Available: {available}"

    theme_data = THEMES[theme]
    tickers = theme_data["tickers"]
    description = theme_data["description"]

    console.print(f"[cyan]Fetching data for {theme} sector ({len(tickers)} companies)...[/cyan]")

    company_summaries = []
    for t in tickers[:6]:  # cap at 6 to keep prompt reasonable
        try:
            info = get_stock_info(t)
            company_summaries.append(stock_info_to_prompt_text(info))
        except Exception as e:
            company_summaries.append(f"{t}: Error fetching data — {e}")

    news = get_latest_ai_tech_news(limit=15)
    news_text = format_news_for_prompt(news[:10])

    companies_text = "\n\n---\n\n".join(company_summaries)

    prompt = f"""Write a sector overview for the "{theme}" investment theme.

THEME: {description}
TICKERS IN BASKET: {", ".join(tickers)}

COMPANY DATA:
{companies_text}

RECENT RELEVANT NEWS:
{news_text}

Write a 600-word sector overview including:
1. Why this theme matters right now in the AI/tech narrative
2. The supply chain logic (who benefits most and why)
3. Top 2-3 names and why they're positioned well
4. Key risks to the thesis
5. What to watch as near-term catalysts

Be specific about valuations, competitive dynamics, and what drives the narrative."""

    console.print(f"[cyan]Generating sector overview...[/cyan]")

    with client.messages.stream(
        model=CLAUDE_MODEL,
        max_tokens=2500,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        result = stream.get_final_text()

    return result


def analyze_news_narrative() -> str:
    """
    Analyze the latest AI/tech news and extract the dominant market narrative.
    """
    console.print("[cyan]Fetching latest AI/tech news...[/cyan]")
    articles = get_latest_ai_tech_news(limit=25)
    news_text = format_news_for_prompt(articles)

    prompt = f"""Analyze these recent AI/tech financial news headlines and extract the market narrative.

NEWS FEED:
{news_text}

Provide:
1. **Dominant narrative** (2-3 sentences on what the market is most focused on right now)
2. **Emerging themes** (2-3 things gaining momentum that aren't fully priced in yet)
3. **Narrative risks** (what could break the current AI trade)
4. **Actionable implication** (which specific segments or names this points to)

This should read like a morning market brief from a hedge fund PM."""

    console.print("[cyan]Analyzing market narrative...[/cyan]")

    with client.messages.stream(
        model=CLAUDE_MODEL,
        max_tokens=1500,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        result = stream.get_final_text()

    return result


def main():
    import click

    @click.group()
    def cli():
        """AI/Tech Equity Market Researcher"""
        pass

    @cli.command()
    @click.argument("ticker")
    @click.option("--depth", default="standard", type=click.Choice(["quick", "standard", "deep"]))
    def company(ticker, depth):
        """Research a single company."""
        result = research_company(ticker.upper(), depth=depth)
        console.print(Panel(Markdown(result), title=f"[bold green]{ticker.upper()} Research Note[/bold green]"))

    @cli.command()
    @click.argument("theme")
    def sector(theme):
        """Research a sector theme. Themes: data_centers, photonics_optical, ai_chips, ai_software"""
        result = research_sector(theme)
        console.print(Panel(Markdown(result), title=f"[bold blue]{theme} Sector Overview[/bold blue]"))

    @cli.command()
    def narrative():
        """Analyze the current AI/tech market narrative from news."""
        result = analyze_news_narrative()
        console.print(Panel(Markdown(result), title="[bold magenta]Market Narrative Brief[/bold magenta]"))

    cli()


if __name__ == "__main__":
    main()
