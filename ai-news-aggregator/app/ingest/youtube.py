"""YouTube ingestion adapter.

Thin wrapper around YouTubeScraper (app/scrapers/youtube_scraper.py)
that converts its ChannelVideo objects into rows shaped for the
`youtube_videos` table.

`include_transcripts` defaults to False: listing is meant to be fast and
resilient, so the runner stores items first and fetches transcripts in
a separate later pass (see ContentRepository.get_missing_transcripts()).
Pass include_transcripts=True to get the old fetch-everything-now
behavior.
"""

from __future__ import annotations

from typing import Any, Iterable

from ..scrapers.youtube_scraper import YouTubeScraper


def ingest_channels(
    channel_refs: Iterable[str], hours: int = 24, include_transcripts: bool = False
) -> list[dict[str, Any]]:
    """List (and optionally transcribe) every channel in `channel_refs`,
    returning rows ready to insert into `youtube_videos`.
    """
    scraper = YouTubeScraper()
    rows: list[dict[str, Any]] = []

    for ref in channel_refs:
        channel_id = scraper.resolve_channel_id(ref)
        videos = (
            scraper.fetch_channel(ref, hours=hours)
            if include_transcripts
            else scraper.get_latest_videos(channel_id, hours=hours)
        )

        for video in videos:
            rows.append(
                {
                    "video_id": video.video_id,
                    "channel_id": channel_id,
                    "title": video.title,
                    "url": str(video.url),
                    "published_at": video.published_at,
                    "description": video.description or None,
                    "transcript": video.transcript.text if video.transcript else None,
                }
            )

    return rows


if __name__ == "__main__":
    for row in ingest_channels(["@BetaSquad"], hours=1000):
        has_transcript = row["transcript"] is not None
        print(f"{row['published_at']:%Y-%m-%d %H:%M} | transcript={has_transcript} | {row['title']}")
