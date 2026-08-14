"""Anthropic ingestion adapter.

Thin wrapper around AnthropicScraper (app/scrapers/anthropic_scraper.py)
that converts its Article objects into rows shaped for the
`anthropic_articles` table. Mirrors app/ingest/openai.py exactly since
both scrapers share the same Article shape.
"""

from __future__ import annotations

from typing import Any

from ..scrapers.anthropic_scraper import AnthropicScraper


def ingest_anthropic(hours: int = 24) -> list[dict[str, Any]]:
    """List Anthropic articles (news + research + engineering) published
    within the last `hours`, returning rows ready to insert into
    `anthropic_articles`.
    """
    scraper = AnthropicScraper()
    return [
        {
            "guid": article.external_id,
            "title": article.title,
            "url": str(article.url),
            "description": article.description or None,
            "published_at": article.published_at,
            "category": article.category,
        }
        for article in scraper.get_latest_articles(hours=hours)
    ]


if __name__ == "__main__":
    rows = ingest_anthropic(hours=24)
    print(f"{len(rows)} article(s) in the last 24 hours:")
    for row in rows:
        print(f"{row['published_at']:%Y-%m-%d %H:%M}Z | {row['title']}")
