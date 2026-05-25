"""
Comparable company analysis (comps) tool.
Fetches and formats peer group data for valuation benchmarking.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import anthropic
import pandas as pd
from rich.console import Console
from rich.table import Table
from rich.markdown import Markdown
from rich.panel import Panel
from rich import box

from config import ANTHROPIC_API_KEY, CLAUDE_MODEL, THEMES
from data.fetchers.yahoo_finance import get_stock_info, compare_tickers
from data.processors.normalizer import fmt_number, fmt_pct, fmt_multiple, stock_info_to_prompt_text

console = Console()
client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def build_comps_table(tickers: list[str]) -> pd.DataFrame:
    """Fetch fundamentals for a peer group and return a comps DataFrame."""
    console.print(f"[cyan]Building comps table for: {', '.join(tickers)}...[/cyan]")
    rows = []
    for t in tickers:
        try:
            info = get_stock_info(t)
            rows.append({
                "ticker": t,
                "name": (info.get("name") or "")[:25],
                "market_cap_b": (info.get("market_cap") or 0) / 1e9,
                "price": info.get("price"),
                "pe_fwd": info.get("pe_forward"),
                "pe_ttm": info.get("pe_trailing"),
                "ps": info.get("ps_ratio"),
                "ev_ebitda": info.get("ev_ebitda"),
                "rev_growth": info.get("revenue_growth"),
                "gross_margin": info.get("gross_margin"),
                "op_margin": info.get("operating_margin"),
                "fcf_b": (info.get("free_cash_flow") or 0) / 1e9,
                "beta": info.get("beta"),
            })
        except Exception as e:
            console.print(f"[red]  {t}: {e}[/red]")

    df = pd.DataFrame(rows).set_index("ticker")
    return df


def print_comps_table(df: pd.DataFrame, title: str = "Peer Comps") -> None:
    table = Table(title=f"[bold]{title}[/bold]", box=box.ROUNDED, show_lines=True)

    table.add_column("Ticker", style="bold cyan", no_wrap=True)
    table.add_column("Company", max_width=20)
    table.add_column("Mkt Cap ($B)", justify="right")
    table.add_column("Price", justify="right")
    table.add_column("Fwd P/E", justify="right")
    table.add_column("P/S", justify="right")
    table.add_column("EV/EBITDA", justify="right")
    table.add_column("Rev Growth", justify="right")
    table.add_column("Gross Mgn", justify="right")
    table.add_column("Op Mgn", justify="right")

    for ticker, row in df.iterrows():
        table.add_row(
            str(ticker),
            str(row.get("name", ""))[:20],
            f"{row.get('market_cap_b', 0):.1f}",
            f"${row.get('price', 0):.2f}" if row.get("price") else "N/A",
            fmt_multiple(row.get("pe_fwd")),
            fmt_multiple(row.get("ps")),
            fmt_multiple(row.get("ev_ebitda")),
            fmt_pct(row.get("rev_growth")),
            fmt_pct(row.get("gross_margin")),
            fmt_pct(row.get("op_margin")),
        )

    # Add median row
    numerics = df.select_dtypes(include="number")
    medians = numerics.median()
    table.add_row(
        "[bold]MEDIAN[/bold]", "",
        f"{medians.get('market_cap_b', 0):.1f}",
        "",
        fmt_multiple(medians.get("pe_fwd")),
        fmt_multiple(medians.get("ps")),
        fmt_multiple(medians.get("ev_ebitda")),
        fmt_pct(medians.get("rev_growth")),
        fmt_pct(medians.get("gross_margin")),
        fmt_pct(medians.get("op_margin")),
        style="bold yellow",
    )

    console.print(table)


def ai_comps_analysis(target: str, peers: list[str]) -> str:
    """
    Use Claude to interpret comps — is the target cheap/expensive vs. peers?
    """
    all_tickers = [target] + [p for p in peers if p != target]
    rows = []
    for t in all_tickers:
        try:
            info = get_stock_info(t)
            rows.append(stock_info_to_prompt_text(info))
        except Exception:
            pass

    companies_text = "\n\n---\n\n".join(rows)

    prompt = f"""Analyze {target} vs. its peer group from a valuation perspective.

PEER GROUP DATA:
{companies_text}

Provide a 300-word comps analysis:
1. Where does {target} trade relative to peers on key multiples (P/E, P/S, EV/EBITDA)?
2. Is the premium or discount justified given growth, margins, and AI exposure?
3. What would fair value be if {target} traded at peer median multiples?
4. Does {target} deserve a premium, discount, or in-line multiple — and why?"""

    with client.messages.stream(
        model=CLAUDE_MODEL,
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        return stream.get_final_text()


def main():
    import click

    @click.command()
    @click.argument("tickers", nargs=-1, required=True)
    @click.option("--target", default=None, help="Target ticker to focus the AI analysis on")
    @click.option("--ai-analysis/--no-ai-analysis", default=True)
    def comps(tickers, target, ai_analysis):
        """
        Run comparable company analysis.
        Example: python peer_comps.py NVDA AMD INTC AVGO MRVL --target NVDA
        """
        tickers = [t.upper() for t in tickers]
        df = build_comps_table(tickers)
        print_comps_table(df, title="Peer Comps — " + " / ".join(tickers))

        if ai_analysis and target:
            target = target.upper()
            console.print(f"\n[cyan]Generating AI comps analysis for {target}...[/cyan]")
            analysis = ai_comps_analysis(target, [t for t in tickers if t != target])
            console.print(Panel(Markdown(analysis), title=f"[bold green]{target} Valuation Analysis[/bold green]"))

    comps()


if __name__ == "__main__":
    main()
