"""
Autonomous Market Research Agent.
Orchestrates multi-step research workflows using Claude as the reasoning engine.
Tools available to the agent:
  - get_stock_info       — fundamentals and metadata
  - get_recent_news      — ticker-specific news
  - get_latest_ai_news   — macro AI/tech news
  - screen_theme         — filter a thematic basket
  - get_momentum         — price momentum data
  - get_filing_excerpt   — SEC filing text

The agent decides which tools to call, in what order, to answer a research question.
This is implemented using Claude's native tool_use feature.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import json
import anthropic
import click
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.spinner import Spinner
from rich.live import Live

from config import ANTHROPIC_API_KEY, CLAUDE_MODEL, THEMES
from data.fetchers.yahoo_finance import get_stock_info, get_recent_news
from data.fetchers.news_feeds import get_latest_ai_tech_news
from data.fetchers.sec_filings import get_filing_excerpt
from data.processors.normalizer import stock_info_to_prompt_text, fmt_pct, fmt_number

console = Console()
client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


# ── Tool definitions ──────────────────────────────────────────────────────────

TOOLS = [
    {
        "name": "get_stock_fundamentals",
        "description": "Get key financial fundamentals for a stock ticker: price, market cap, P/E, revenue growth, margins, etc.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Stock ticker symbol, e.g. NVDA"},
            },
            "required": ["ticker"],
        },
    },
    {
        "name": "get_stock_news",
        "description": "Get recent news headlines for a specific stock ticker.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string"},
                "limit": {"type": "integer", "default": 8},
            },
            "required": ["ticker"],
        },
    },
    {
        "name": "get_ai_tech_news",
        "description": "Get the latest macro AI/tech sector news across all relevant companies and themes.",
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "default": 15},
            },
        },
    },
    {
        "name": "screen_theme_basket",
        "description": "Screen all stocks in a thematic basket by fundamentals. Returns ranked results.",
        "input_schema": {
            "type": "object",
            "properties": {
                "theme": {
                    "type": "string",
                    "description": "One of: data_centers, photonics_optical, ai_chips, ai_software, ai_infrastructure",
                },
                "sort_by": {
                    "type": "string",
                    "enum": ["revenue_growth", "market_cap", "gross_margin"],
                    "default": "revenue_growth",
                },
            },
            "required": ["theme"],
        },
    },
    {
        "name": "get_sec_filing",
        "description": "Fetch an excerpt from the most recent SEC filing (10-K or 10-Q) for a company.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string"},
                "form_type": {"type": "string", "enum": ["10-K", "10-Q", "8-K"], "default": "10-Q"},
            },
            "required": ["ticker"],
        },
    },
    {
        "name": "compare_stocks",
        "description": "Compare fundamentals across multiple stocks side by side.",
        "input_schema": {
            "type": "object",
            "properties": {
                "tickers": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of ticker symbols to compare",
                },
            },
            "required": ["tickers"],
        },
    },
]


# ── Tool execution ────────────────────────────────────────────────────────────

def execute_tool(tool_name: str, tool_input: dict) -> str:
    """Dispatch a tool call and return the result as a string."""
    try:
        if tool_name == "get_stock_fundamentals":
            info = get_stock_info(tool_input["ticker"].upper())
            return stock_info_to_prompt_text(info)

        elif tool_name == "get_stock_news":
            news = get_recent_news(tool_input["ticker"].upper(), limit=tool_input.get("limit", 8))
            if not news:
                return "No recent news found."
            return "\n".join(f"- {n['title']} ({n.get('publisher','')})" for n in news if n.get("title"))

        elif tool_name == "get_ai_tech_news":
            articles = get_latest_ai_tech_news(limit=tool_input.get("limit", 15))
            return "\n".join(f"- [{a.get('source','')}] {a.get('title','')}" for a in articles)

        elif tool_name == "screen_theme_basket":
            theme = tool_input["theme"]
            if theme not in THEMES:
                return f"Unknown theme '{theme}'. Available: {list(THEMES.keys())}"
            from screening.stock_screener import screen_theme
            df = screen_theme(theme, sort_by=tool_input.get("sort_by", "revenue_growth"))
            if df.empty:
                return "No results after screening."
            cols = ["name", "market_cap", "pe_forward", "revenue_growth", "gross_margin"]
            available = [c for c in cols if c in df.columns]
            return df[available].to_string()

        elif tool_name == "get_sec_filing":
            excerpt = get_filing_excerpt(
                tool_input["ticker"].upper(),
                form_type=tool_input.get("form_type", "10-Q"),
                max_chars=5000,
            )
            return excerpt

        elif tool_name == "compare_stocks":
            tickers = [t.upper() for t in tool_input["tickers"]]
            from data.fetchers.yahoo_finance import compare_tickers
            df = compare_tickers(tickers)
            cols = ["name", "market_cap", "price", "pe_forward", "ps_ratio", "revenue_growth", "gross_margin"]
            available = [c for c in cols if c in df.columns]
            return df[available].to_string()

        else:
            return f"Unknown tool: {tool_name}"

    except Exception as e:
        return f"Tool error: {str(e)}"


# ── Agent loop ────────────────────────────────────────────────────────────────

AGENT_SYSTEM = """You are an autonomous AI equity research agent specializing in AI/tech themes:
data centers, photonics, semiconductors, AI software, and hyperscaler infrastructure.

You have tools to fetch real-time financial data, news, SEC filings, and run screens.
Use them methodically to answer the user's research question thoroughly.

Think step by step:
1. Identify what data you need
2. Call the appropriate tools
3. Synthesize the results into a professional research answer

Always ground your analysis in actual data from your tools. Be specific about numbers,
multiples, and comparisons. Format your final answer as structured markdown."""


def run_agent(question: str, max_iterations: int = 8) -> str:
    """
    Run the agentic loop: repeatedly call Claude with tool results
    until it produces a final text answer.
    """
    messages = [{"role": "user", "content": question}]
    iteration = 0

    console.print(Panel(f"[bold]Research Query:[/bold] {question}", style="blue"))

    while iteration < max_iterations:
        iteration += 1
        console.print(f"\n[dim]Agent iteration {iteration}...[/dim]")

        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=4096,
            system=AGENT_SYSTEM,
            tools=TOOLS,
            messages=messages,
        )

        # Check if we have tool calls
        tool_calls = [b for b in response.content if b.type == "tool_use"]

        if not tool_calls:
            # Final answer — extract text
            final_text = "".join(
                b.text for b in response.content if hasattr(b, "text")
            )
            return final_text

        # Execute all tool calls
        console.print(f"[cyan]  Calling tools: {[t.name for t in tool_calls]}[/cyan]")

        tool_results = []
        for tool_call in tool_calls:
            result = execute_tool(tool_call.name, tool_call.input)
            console.print(f"[dim]  ✓ {tool_call.name} returned {len(result)} chars[/dim]")
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tool_call.id,
                "content": result,
            })

        # Add assistant turn + tool results to messages
        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": tool_results})

    return "Agent reached max iterations without a final answer."


@click.command()
@click.argument("question", nargs=-1, required=True)
@click.option("--max-iter", default=8, help="Max agent iterations")
def main(question, max_iter):
    """
    Run the market research agent with a natural language question.

    Examples:
      python market_research_agent.py "What are the best AI data center plays right now?"
      python market_research_agent.py "Compare NVDA vs AMD on AI exposure and valuation"
      python market_research_agent.py "What does COHR's latest 10-Q say about photonics demand?"
      python market_research_agent.py "Screen the photonics_optical theme and rank by growth"
    """
    query = " ".join(question)
    result = run_agent(query, max_iterations=max_iter)
    console.print("\n")
    console.print(Panel(Markdown(result), title="[bold green]Research Result[/bold green]", padding=(1, 2)))


if __name__ == "__main__":
    main()
