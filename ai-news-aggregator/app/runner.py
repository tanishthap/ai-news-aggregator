"""Runner: kicks off every ingestion source and stores what's new.

Listing-only for now -- YouTube transcripts and OpenAI/Anthropic full
article content (get_markdown()) are deliberately deferred to a later
content-processing pass, not fetched here. Which YouTube channels get
checked and how far back every source looks both live in app/config.py.

run_scrapers() returns the same {"youtube": [...], "openai": [...],
"anthropic": [...]} shape regardless of the DB layer underneath, so
main.py doesn't need to change if the storage design changes.
"""

from __future__ import annotations

from typing import Any

from .config import DEFAULT_LOOKBACK_HOURS, YOUTUBE_CHANNELS
from .database.repository import ContentRepository
from .database.session import SessionLocal
from .ingest.anthropic import ingest_anthropic
from .ingest.openai import ingest_openai
from .ingest.youtube import ingest_channels


def run_scrapers(hours: int = DEFAULT_LOOKBACK_HOURS) -> dict[str, list[dict[str, Any]]]:
    """List new items per source, published within the last `hours`."""
    return {
        "youtube": ingest_channels(YOUTUBE_CHANNELS, hours=hours),
        "openai": ingest_openai(hours=hours),
        "anthropic": ingest_anthropic(hours=hours),
    }


def run_and_store(hours: int = DEFAULT_LOOKBACK_HOURS) -> dict[str, int]:
    """run_scrapers() + persist everything new into its own table
    (openai_articles / anthropic_articles / youtube_videos).

    Returns how many new (not-already-seen) rows were written per source.
    """
    results = run_scrapers(hours=hours)

    with SessionLocal() as session:
        repo = ContentRepository(session)
        counts = {
            "youtube": repo.upsert_youtube_videos(results["youtube"]),
            "openai": repo.upsert_openai_articles(results["openai"]),
            "anthropic": repo.upsert_anthropic_articles(results["anthropic"]),
        }
        session.commit()

    return counts


if __name__ == "__main__":
    counts = run_and_store()
    for source, count in counts.items():
        print(f"{source}: {count} new row(s) stored")
