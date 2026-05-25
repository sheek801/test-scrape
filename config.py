import os
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = "claude-sonnet-4-6"

# AI/tech narrative watchlists — the core thematic baskets
THEMES = {
    "data_centers": {
        "description": "Power, cooling, infrastructure for AI compute",
        "tickers": ["NVDA", "SMCI", "VST", "CEG", "GEV", "ETN", "VRT", "EQIX", "AMT", "DLR", "IREN", "CORZ"],
    },
    "photonics_optical": {
        "description": "Optical interconnects and photonics for AI networking",
        "tickers": ["COHR", "LITE", "CIEN", "AAOI", "IIVI", "FNSR", "VIAV", "IPGP", "OLED"],
    },
    "ai_chips": {
        "description": "Semiconductor companies enabling AI acceleration",
        "tickers": ["NVDA", "AMD", "INTC", "ARM", "AVGO", "MRVL", "TSM", "QCOM", "MU", "ALAB"],
    },
    "ai_software": {
        "description": "Software platforms monetizing AI workloads",
        "tickers": ["MSFT", "GOOGL", "META", "AMZN", "PLTR", "SNOW", "DDOG", "NET", "AI", "BBAI"],
    },
    "ai_infrastructure": {
        "description": "Cloud and hyperscaler capex beneficiaries",
        "tickers": ["AMZN", "MSFT", "GOOGL", "META", "ORCL", "IBM", "HPE", "DELL"],
    },
}

# Key metrics for screening
SCREENING_DEFAULTS = {
    "min_market_cap_b": 0.5,        # $500M minimum
    "max_pe": 150,                   # allow high-growth multiples
    "min_revenue_growth_yoy": -0.10, # at least not declining fast
    "min_gross_margin": 0.20,
}

DATA_CACHE_DIR = os.path.join(os.path.dirname(__file__), "data", "cache")
os.makedirs(DATA_CACHE_DIR, exist_ok=True)
