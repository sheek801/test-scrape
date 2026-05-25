# AI/Tech Equity Research Engine

A Python toolkit for autonomous market research on AI infrastructure themes — data centers, photonics, semiconductors, and AI software. Built on Claude AI (Anthropic) as the reasoning layer, with real-time data from Yahoo Finance and SEC EDGAR.

**Primary focus:** Equity research on the AI/tech capital cycle — identifying how money flows from hyperscaler capex through the semiconductor supply chain, optical interconnects, and power infrastructure.

---

## What this does

| Tool | What it answers |
|------|----------------|
| `agents/market_research_agent.py` | "What are the best data center plays right now?" — autonomous multi-step research |
| `research/market_researcher.py` | Company deep-dives, sector overviews, narrative analysis |
| `research/earnings_analyzer.py` | Pre-earnings setups, SEC filing analysis for AI signals |
| `screening/stock_screener.py` | Screen thematic baskets by fundamentals + momentum |
| `screening/peer_comps.py` | Comparable company valuation analysis |
| `portfolio/watchlist.py` | Live watchlist with thesis notes |
| `portfolio/thesis_tracker.py` | Structured thesis creation and scoring vs. current news |

---

## Thematic Baskets

Research is organized around 5 AI/tech investment themes:

- **`data_centers`** — Power, cooling, and infrastructure: NVDA, SMCI, VST, CEG, VRT, EQIX
- **`photonics_optical`** — Optical interconnects for AI networking: COHR, LITE, CIEN, AAOI
- **`ai_chips`** — Semiconductor accelerators: NVDA, AMD, AVGO, MRVL, ARM, TSM
- **`ai_software`** — Platforms monetizing AI workloads: MSFT, GOOGL, PLTR, DDOG, NET
- **`ai_infrastructure`** — Hyperscaler capex beneficiaries: AMZN, MSFT, GOOGL, META, ORCL

---

## Setup

```bash
git clone https://github.com/sheek801/test-scrape
cd test-scrape
pip install -r requirements.txt
cp .env.example .env
# Add your Anthropic API key to .env
```

---

## Usage

### Autonomous Agent (most powerful)
```bash
# Natural language research questions
python agents/market_research_agent.py "What are the best AI data center plays right now?"
python agents/market_research_agent.py "Compare NVDA vs AMD on AI exposure and valuation"
python agents/market_research_agent.py "What does COHR's latest 10-Q say about photonics demand?"
python agents/market_research_agent.py "Screen photonics_optical and find the best risk/reward"
```

### Company Research
```bash
python research/market_researcher.py company NVDA --depth deep
python research/market_researcher.py company COHR --depth quick
python research/market_researcher.py sector data_centers
python research/market_researcher.py narrative   # what's the market focused on today?
```

### Earnings Analysis
```bash
python research/earnings_analyzer.py filing NVDA --form 10-Q
python research/earnings_analyzer.py preearnings SMCI
```

### Stock Screener
```bash
python screening/stock_screener.py screen ai_chips --sort revenue_growth
python screening/stock_screener.py momentum photonics_optical --period 3mo
python screening/stock_screener.py themes   # list all themes
```

### Peer Comps
```bash
python screening/peer_comps.py NVDA AMD INTC AVGO MRVL --target NVDA
python screening/peer_comps.py COHR LITE CIEN --target COHR
```

### Watchlist
```bash
python portfolio/watchlist.py add NVDA "AI datacenter supercycle; dominant GPU share" --theme ai_chips --conviction high
python portfolio/watchlist.py show
python portfolio/watchlist.py alert NVDA "Watch for Blackwell ramp commentary on next earnings"
```

### Thesis Tracker
```bash
python portfolio/thesis_tracker.py create NVDA
python portfolio/thesis_tracker.py score NVDA    # score thesis vs. current news
python portfolio/thesis_tracker.py list
```

---

## Architecture

```
├── agents/
│   └── market_research_agent.py   # Claude tool-use agentic loop
├── research/
│   ├── market_researcher.py       # Sector + company research with streaming
│   └── earnings_analyzer.py       # Filing analysis + pre-earnings setups
├── screening/
│   ├── stock_screener.py          # Fundamental + momentum screener
│   └── peer_comps.py              # Comparable company analysis
├── portfolio/
│   ├── watchlist.py               # Live watchlist manager
│   └── thesis_tracker.py          # Thesis creation + scoring
├── data/
│   ├── fetchers/
│   │   ├── yahoo_finance.py       # Price, fundamentals, news (yfinance)
│   │   ├── sec_filings.py         # SEC EDGAR 10-K/10-Q fetcher
│   │   └── news_feeds.py          # RSS feeds filtered for AI/tech
│   └── processors/
│       └── normalizer.py          # Number formatting and text preparation
└── config.py                      # Thematic baskets and global settings
```

**AI layer:** Claude claude-sonnet-4-6 via the Anthropic SDK with streaming and native tool use. The agent loop uses Claude's `tool_use` stop condition to orchestrate multi-step research without manual chaining.

**Data sources (free tier):**
- Yahoo Finance via `yfinance` — prices, fundamentals, news
- SEC EDGAR API — 10-K, 10-Q, 8-K filings
- RSS news feeds — Reuters, TechCrunch, Semiconductor Engineering

---

## Engineering notes

- **Agentic orchestration:** The market research agent uses Claude's native `tool_use` API, not a framework. The agent loop runs until `stop_reason != "tool_use"`, giving Claude full control over tool sequencing.
- **Streaming throughout:** All research outputs stream token-by-token using `client.messages.stream()` for responsive CLI UX.
- **No hardcoded prompts:** Theme baskets, screening defaults, and model settings live in `config.py` — easy to extend without touching tool logic.
- **Composable tools:** Each module (`screener`, `fetcher`, `researcher`) is independently importable. The agent imports screener functions directly, so there's no duplicate logic.

---

## Extending this

1. **Add a new theme** — Edit `THEMES` in `config.py` with tickers and description
2. **Add a data source** — Create a new fetcher in `data/fetchers/`, add it as a tool in `agents/market_research_agent.py`
3. **Add a new command** — Each CLI module uses `click` groups; add a new `@cli.command()` function
4. **Connect real data providers** — Replace `yahoo_finance.py` with MCP-based providers (Morningstar, FactSet, S&P Global) following the `anthropics/financial-services` connector pattern

---

## Skills demonstrated (for finance/fintech roles)

- Agentic AI system design using LLM tool-use APIs
- Financial data pipelines (fundamentals, SEC filings, news)
- Equity research workflow automation
- Python software engineering: modular design, CLI tooling, data processing
- Domain knowledge: AI supply chain, semiconductor valuation, equity research process
