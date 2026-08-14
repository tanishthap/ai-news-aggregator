"""OpenAI ingestion adapter.

Thin wrapper around OpenAIScraper (app/scrapers/openai_scraper.py) that
converts its Article objects into rows shaped for the `openai_articles`
table.
"""

from __future__ import annotations

from typing import Any, Optional

from ..scrapers.openai_scraper import OpenAIScraper


def ingest_openai(hours: int = 24, category: Optional[str] = None) -> list[dict[str, Any]]:
    """List OpenAI news-feed articles published within the last `hours`,
    optionally filtered to a single `category` (e.g. "Research"),
    returning rows ready to insert into `openai_articles`.
    """
    scraper = OpenAIScraper()
    return [
        {
            "guid": article.external_id,
            "title": article.title,
            "url": str(article.url),
            "description": article.description or None,
            "published_at": article.published_at,
            "category": article.category,
        }
        for article in scraper.get_latest_articles(hours=hours, category=category)
    ]


if __name__ == "__main__":
    rows = ingest_openai(hours=24)
    print(f"{len(rows)} article(s) in the last 24 hours:")
    for row in rows:
        print(f"{row['published_at']:%Y-%m-%d %H:%M}Z | {row['title']}")
