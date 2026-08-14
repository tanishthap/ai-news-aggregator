"""Anthropic scraper.

Same shape as app/scrapers/openai_scraper.py, but combines three
community-maintained feeds into a single interface, since Anthropic
doesn't publish a first-party RSS feed for any of these pages:

  - get_latest_articles()   -> Article list, merged across all three
                                feeds, published within last N hours
  - get_markdown()          -> same trafilatura URL-to-markdown as OpenAI

Feeds (all checked live, 200 OK), from
https://github.com/Olshansk/rss-feeds:
  feed_anthropic_news.xml         -> anthropic.com/news
  feed_anthropic_research.xml     -> anthropic.com/research
  feed_anthropic_engineering.xml  -> anthropic.com/engineering

Note: anthropic.com did NOT block requests from this sandbox when
tested (unlike openai.com), but run get_markdown() from your own machine
anyway for consistency in case that changes.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

import feedparser
import trafilatura
from pydantic import BaseModel, HttpUrl

ANTHROPIC_FEED_URLS = [
    "https://raw.githubusercontent.com/Olshansk/rss-feeds/main/feeds/feed_anthropic_news.xml",
    "https://raw.githubusercontent.com/Olshansk/rss-feeds/main/feeds/feed_anthropic_research.xml",
    "https://raw.githubusercontent.com/Olshansk/rss-feeds/main/feeds/feed_anthropic_engineering.xml",
]


class Article(BaseModel):
    """One article as reported by one of Anthropic's RSS feeds."""

    external_id: str
    title: str
    url: HttpUrl
    published_at: datetime
    description: str = ""
    category: Optional[str] = None


class AnthropicScraper:
    """List recent Anthropic articles, merged across news/research/engineering."""

    def __init__(self, feed_urls: Optional[list[str]] = None) -> None:
        self.feed_urls = feed_urls or ANTHROPIC_FEED_URLS

    def get_latest_articles(self, hours: int = 24) -> list[Article]:
        """Return articles published within the last `hours`, merged
        across every configured feed and sorted newest first.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        articles: list[Article] = []

        for feed_url in self.feed_urls:
            feed = feedparser.parse(feed_url)

            if feed.bozo and not feed.entries:
                raise ValueError(f"Failed to parse RSS feed {feed_url}: {feed.bozo_exception}")

            for entry in feed.entries:
                published_at = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                if published_at < cutoff:
                    continue

                category = entry.tags[0].get("term") if entry.get("tags") else None

                articles.append(
                    Article(
                        external_id=entry.get("id", entry.link),
                        title=entry.title,
                        url=entry.link,
                        published_at=published_at,
                        description=entry.get("summary", ""),
                        category=category,
                    )
                )

        articles.sort(key=lambda a: a.published_at, reverse=True)
        return articles

    # -- content extraction --------------------------------------------- #

    def get_markdown(self, url: str) -> str:
        """Fetch the article at `url` and return it as a markdown string."""
        downloaded = trafilatura.fetch_url(url)
        if downloaded is None:
            raise ValueError(f"Failed to fetch {url}")

        markdown = trafilatura.extract(
            downloaded, output_format="markdown", include_links=True, with_metadata=True
        )
        if markdown is None:
            raise ValueError(f"Failed to extract content from {url}")

        return markdown


if __name__ == "__main__":
    scraper = AnthropicScraper()
    articles = scraper.get_latest_articles(hours=24 * 7)
    print(f"{len(articles)} article(s) in the last 7 days:")
    for article in articles:
        print(f"{article.published_at:%Y-%m-%d}  [{article.category}]  {article.title}")
