"""Stage 2: content enrichment.

Ingestion (app/runner.py) only lists metadata -- fast, and one bad
network call can't take down the whole listing pass. This module is
the separate, slower pass that fills in what listing deliberately
skips:

  - openai_articles.markdown / anthropic_articles.markdown, via each
    scraper's get_markdown(url) (trafilatura fetch + extract)
  - youtube_videos.transcript, via YouTubeScraper.get_transcript(video_id)

Run it any time after app.runner -- it only ever touches rows that are
still missing that field, so re-running is always safe and never redoes
work.

Markdown fetches: a row that fails (dead link, blocked request) is left
NULL and retried next run. There's no "we tried and gave up" state for
these yet -- fine at this scale; revisit if a permanently broken URL
ever becomes wasteful to keep retrying.

YouTube transcripts: this DOES distinguish permanent from transient
failure. A video with no transcript available (captions disabled, none
found, video unavailable) is genuinely never going to succeed, so it's
marked `transcript_unavailable=True` and excluded from future runs --
see ContentRepository.get_missing_transcripts(). Any other error
(e.g. a blocked/rate-limited request) is treated as transient and left
alone so it's retried next run.

get_markdown() needs a real residential IP (openai.com blocks
datacenter IPs) -- run this from the app container on your own machine,
not from a cloud host.
"""

from __future__ import annotations

import time
from typing import Any

from .database.models import AnthropicArticle, OpenAIArticle, YouTubeVideo
from .database.repository import ContentRepository
from .database.session import SessionLocal
from .scrapers.anthropic_scraper import AnthropicScraper
from .scrapers.openai_scraper import OpenAIScraper
from .scrapers.youtube_scraper import TranscriptUnavailable, YouTubeScraper

REQUEST_DELAY_SECONDS = 1.0


def _fill_article_markdown(model: type, scraper: Any, limit: int | None = None) -> dict[str, int]:
    """Shared by OpenAI/Anthropic: fetch markdown for every row missing
    it, committing after each one so a crash partway through doesn't
    lose progress already made. `limit=None` processes every missing row.
    """
    filled = failed = 0
    with SessionLocal() as session:
        repo = ContentRepository(session)
        for row in repo.get_missing_markdown(model, limit=limit):
            try:
                row.markdown = scraper.get_markdown(row.url)
                filled += 1
            except Exception as exc:
                print(f"  failed: {row.url} ({exc})")
                failed += 1
            session.commit()
            time.sleep(REQUEST_DELAY_SECONDS)
    return {"filled": filled, "failed": failed}


def fill_openai_markdown(limit: int | None = None) -> dict[str, int]:
    return _fill_article_markdown(OpenAIArticle, OpenAIScraper(), limit=limit)


def fill_anthropic_markdown(limit: int | None = None) -> dict[str, int]:
    return _fill_article_markdown(AnthropicArticle, AnthropicScraper(), limit=limit)


def fill_youtube_transcripts(limit: int | None = None) -> dict[str, int]:
    """Fetch transcripts for youtube_videos rows missing one.

    - TranscriptUnavailable (captions disabled / none found / video
      gone) is permanent: mark `transcript_unavailable=True` so this
      video is never selected again.
    - Any other error (blocked request, network hiccup, etc.) is
      treated as transient: leave the row untouched so it's retried
      next run.
    """
    scraper = YouTubeScraper()
    filled = unavailable = skipped = 0
    with SessionLocal() as session:
        repo = ContentRepository(session)
        for row in repo.get_missing_transcripts(limit=limit):
            try:
                row.transcript = scraper.get_transcript(row.video_id).text
                filled += 1
            except TranscriptUnavailable:
                row.transcript_unavailable = True
                unavailable += 1
            except Exception as exc:
                print(f"  failed (will retry later): {row.video_id} ({exc})")
                skipped += 1
            session.commit()
            time.sleep(REQUEST_DELAY_SECONDS)
    return {"filled": filled, "unavailable": unavailable, "skipped": skipped}


def run_enrichment() -> dict[str, dict[str, int]]:
    return {
        "openai": fill_openai_markdown(),
        "anthropic": fill_anthropic_markdown(),
        "youtube": fill_youtube_transcripts(),
    }


if __name__ == "__main__":
    for source, counts in run_enrichment().items():
        print(f"{source}: {counts}")
