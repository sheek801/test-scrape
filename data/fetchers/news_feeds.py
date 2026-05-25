"""Fetches AI/tech financial news from RSS feeds and free APIs."""
import feedparser
import requests
from datetime import datetime
from typing import Optional


RSS_FEEDS = {
    "seeking_alpha_tech": "https://seekingalpha.com/feed/sectors/technology",
    "reuters_tech": "https://feeds.reuters.com/reuters/technologyNews",
    "yahoo_finance": "https://finance.yahoo.com/news/rssindex",
    "techcrunch": "https://techcrunch.com/feed/",
    "the_information_rss": "https://www.theinformation.com/feed",
    "semiconductor_engineering": "https://semiengineering.com/feed/",
}

AI_KEYWORDS = [
    "artificial intelligence", "AI", "machine learning", "GPU", "NVDA", "nvidia",
    "data center", "inference", "LLM", "large language model", "hyperscaler",
    "photonics", "optical interconnect", "silicon photonics", "COHR", "coherent",
    "ARM", "TSMC", "semiconductor", "chip", "accelerator", "HBM", "memory bandwidth",
    "capex", "cloud", "Azure", "AWS", "Google Cloud", "Anthropic", "OpenAI",
]


def fetch_rss_feed(feed_url: str, limit: int = 20) -> list[dict]:
    """Parse an RSS feed and return articles."""
    try:
        feed = feedparser.parse(feed_url)
        articles = []
        for entry in feed.entries[:limit]:
            articles.append({
                "title": entry.get("title", ""),
                "link": entry.get("link", ""),
                "published": entry.get("published", ""),
                "summary": entry.get("summary", "")[:300],
                "source": feed.feed.get("title", feed_url),
            })
        return articles
    except Exception as e:
        return [{"error": str(e), "source": feed_url}]


def fetch_all_feeds(limit_per_feed: int = 10) -> list[dict]:
    """Fetch from all configured feeds."""
    all_articles = []
    for name, url in RSS_FEEDS.items():
        articles = fetch_rss_feed(url, limit=limit_per_feed)
        for a in articles:
            a["feed_name"] = name
        all_articles.extend(articles)
    return all_articles


def filter_ai_tech_news(articles: list[dict]) -> list[dict]:
    """Filter articles to only those matching AI/tech keywords."""
    relevant = []
    for a in articles:
        text = f"{a.get('title','')} {a.get('summary','')}".lower()
        if any(kw.lower() in text for kw in AI_KEYWORDS):
            relevant.append(a)
    return relevant


def get_latest_ai_tech_news(limit: int = 30) -> list[dict]:
    """Convenience: fetch and filter to AI/tech relevant news."""
    all_articles = fetch_all_feeds(limit_per_feed=15)
    relevant = filter_ai_tech_news(all_articles)
    return relevant[:limit]


def format_news_for_prompt(articles: list[dict]) -> str:
    """Format a list of articles as a text block for an LLM prompt."""
    lines = []
    for i, a in enumerate(articles, 1):
        lines.append(f"{i}. [{a.get('source','')}] {a.get('title','')}")
        if a.get("summary"):
            lines.append(f"   {a['summary'][:200]}")
        lines.append(f"   {a.get('link','')}")
        lines.append("")
    return "\n".join(lines)
