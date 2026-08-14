"""OpenAI scraper.

Minimal RSS-first ingestion for OpenAI content, mirroring the shape of
app/scrapers/youtube_scraper.py:

  - get_latest_articles()   -> ResearchArticle list, published within last N hours

One Pydantic model defines exactly what shape of data flows through this
module:

  - ResearchArticle: everything the RSS feed gives us about one article.

Note on the feed source: the community "OpenAI Research Index RSS Feed"
referenced at
https://community.openai.com/t/rss-feed-openai-research-index-rss-feed/1088852
points at
raw.githubusercontent.com/Olshansk/rss-feeds/main/feeds/feed_openai_research.xml
-- checked directly, that URL now 404s and the repo's own README
(github.com/Olshansk/rss-feeds) lists "OpenAI Research News" as *planned*,
i.e. never shipped / no longer live.

OpenAI's own https://openai.com/news/rss.xml covers the same ground.
Note: <category> isn't present on every item (147 of 1110 items have none
at all), so it's kept as an optional field on the model rather than
relied on as a filter -- callers who want just research posts can filter
on category == "Research" themselves.

get_markdown() converts a single article URL to markdown via trafilatura
(fetch + main-content extraction + markdown export, no bespoke HTML
parsing, no ML models -- already a project dependency). Note it needs a
real (residential) IP the same way YouTube transcripts did -- OpenAI's
Cloudflare protection blocks datacenter IPs (confirmed from this
sandbox: fetch_url() comes back None), so this should be run from your
own machine.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

import feedparser
import trafilatura
from pydantic import BaseModel, HttpUrl

OPENAI_NEWS_RSS_ENDPOINT = "https://openai.com/news/rss.xml"


class Article(BaseModel):
    """One article as reported by OpenAI's news RSS feed."""

    external_id: str
    title: str
    url: HttpUrl
    published_at: datetime
    description: str = ""
    category: Optional[str] = None


class OpenAIScraper:
    """List recent OpenAI articles straight from the official news RSS feed."""

    def __init__(self, feed_url: str = OPENAI_NEWS_RSS_ENDPOINT) -> None:
        self.feed_url = feed_url

    def get_latest_articles(
        self, hours: int = 24, category: Optional[str] = None
    ) -> list[Article]:
        """Return articles published within the last `hours`. Pass a
        `category` (e.g. "Research") to filter to just that tag -- note
        not every item has one, so filtering narrows results further
        than the time window alone.
        """
        feed = feedparser.parse(self.feed_url)

        if feed.bozo and not feed.entries:
            raise ValueError(f"Failed to parse RSS feed {self.feed_url}: {feed.bozo_exception}")

        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        articles: list[Article] = []

        for entry in feed.entries:
            published_at = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
            if published_at < cutoff:
                continue

            entry_category = entry.tags[0].get("term") if entry.get("tags") else None
            if category is not None and entry_category != category:
                continue

            articles.append(
                Article(
                    external_id=entry.get("id", entry.link),
                    title=entry.title,
                    url=entry.link,
                    published_at=published_at,
                    description=entry.get("summary", ""),
                    category=entry_category,
                )
            )

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
    scraper = OpenAIScraper()
    articles = scraper.get_latest_articles(hours=24)
    print(f"{len(articles)} article(s) in the last 24 hours:")
    for article in articles:
        print(f"{article.published_at:%Y-%m-%d %H:%M}Z  [{article.category}]  {article.title}")
