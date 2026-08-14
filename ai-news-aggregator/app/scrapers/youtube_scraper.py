"""YouTube scraper.

Single class wrapping everything needed to go from a channel reference to
transcribed videos, with no YouTube Data API key required:

  - resolve_channel_id()  @handle / full URL / legacy username -> UC... id
  - get_latest_videos()   channel_id -> ChannelVideo list, last N hours
  - get_transcript()      video_id -> Transcript
  - fetch_channel()       convenience wrapper chaining all three

Two Pydantic models define exactly what shape of data flows through this
module, so every caller (ingest adapter, CLI, tests) knows precisely what
it's getting back instead of passing raw dicts around:

  - ChannelVideo: everything the RSS feed gives us about one video, plus
    an optional `transcript` field filled in once fetch_channel() runs.
  - Transcript: just the plain-text transcript body.

See app/ingest/youtube.py for the thin adapter that turns ChannelVideo
objects into NormalizedArticle rows for the DB layer.

Caveat carried over from earlier testing: get_transcript() can raise
IpBlocked/RequestBlocked when called from a datacenter IP (most cloud
hosts, including Render). That's intentionally NOT caught here -- it's an
infrastructure problem, not a "no transcript" problem. fetch_channel() is
the one place that downgrades any transcript failure to transcript=None
so a bad IP doesn't take down an entire ingestion run.
"""

from __future__ import annotations

import re
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

import feedparser
import requests
from pydantic import BaseModel, HttpUrl
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    NoTranscriptFound,
    TranscriptsDisabled,
    VideoUnavailable,
)

YOUTUBE_RSS_ENDPOINT = "https://www.youtube.com/feeds/videos.xml"

_CHANNEL_ID_PATTERN = re.compile(r"UC[\w-]{22}")
_CANONICAL_LINK_PATTERN = re.compile(
    r'<link rel="canonical" href="https://www\.youtube\.com/channel/(UC[\w-]{22})"'
)
_INLINE_CHANNEL_ID_PATTERN = re.compile(r'"channelId":"(UC[\w-]{22})"')
_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; ai-news-aggregator/0.1)"}


class TranscriptUnavailable(Exception):
    """Raised when a video genuinely has no transcript (disabled, missing,
    or the video itself is unavailable) -- as opposed to an IP block."""


class Transcript(BaseModel):
    """A fetched transcript, flattened to plain text."""

    text: str


class ChannelVideo(BaseModel):
    """One video as reported by a channel's RSS feed."""

    video_id: str
    title: str
    url: HttpUrl
    published_at: datetime
    description: str = ""
    thumbnail_url: Optional[HttpUrl] = None
    transcript: Optional[Transcript] = None


class YouTubeScraper:
    """Resolve channels, list recent videos, and fetch transcripts."""

    def __init__(
        self,
        session: Optional[requests.Session] = None,
        request_delay_seconds: float = 1.0,
    ) -> None:
        self.session = session or requests.Session()
        self.request_delay_seconds = request_delay_seconds
        self._transcript_api = YouTubeTranscriptApi()

    # -- channel resolution ------------------------------------------- #

    def resolve_channel_id(self, channel_ref: str) -> str:
        """Resolve a handle, full URL, or legacy username to a UC... id.

        No API key needed: every channel page embeds its canonical
        channel id in the HTML, either in a <link rel="canonical"> tag
        or inline as JSON, regardless of which URL style was used to
        reach the page.
        """
        ref = channel_ref.strip()

        if _CHANNEL_ID_PATTERN.fullmatch(ref):
            return ref

        if ref.startswith("http"):
            url = ref
        elif ref.startswith("@"):
            url = f"https://www.youtube.com/{ref}"
        else:
            url = f"https://www.youtube.com/@{ref}"

        response = self.session.get(url, headers=_HEADERS, timeout=15, allow_redirects=True)
        response.raise_for_status()

        match = _CANONICAL_LINK_PATTERN.search(response.text) or _INLINE_CHANNEL_ID_PATTERN.search(
            response.text
        )
        if not match:
            raise ValueError(f"Could not resolve a channel id for {channel_ref!r}")

        return match.group(1)

    # -- video listing -------------------------------------------------- #

    def get_latest_videos(self, channel_id: str, hours: int = 24) -> list[ChannelVideo]:
        """Return videos from `channel_id`'s RSS feed published within
        the last `hours`. The feed only ever exposes the ~15 most recent
        uploads, so this can't backfill a full archive.
        """
        feed = feedparser.parse(f"{YOUTUBE_RSS_ENDPOINT}?channel_id={channel_id}")

        if feed.bozo and not feed.entries:
            raise ValueError(
                f"Failed to parse RSS feed for channel {channel_id}: {feed.bozo_exception}"
            )

        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        videos: list[ChannelVideo] = []

        for entry in feed.entries:
            published_at = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
            if published_at < cutoff:
                continue

            video_id = getattr(entry, "yt_videoid", None) or entry.id.split(":")[-1]
            thumbnails = getattr(entry, "media_thumbnail", None)
            thumbnail_url = thumbnails[0].get("url") if thumbnails else None
            description = getattr(entry, "media_description", None) or entry.get("summary", "")

            videos.append(
                ChannelVideo(
                    video_id=video_id,
                    title=entry.title,
                    url=entry.link,
                    published_at=published_at,
                    description=description,
                    thumbnail_url=thumbnail_url,
                )
            )

        return videos

    # -- transcript retrieval -------------------------------------------- #

    def get_transcript(self, video_id: str, languages: Optional[list[str]] = None) -> Transcript:
        """Return the transcript for `video_id` as a Transcript model."""
        languages = languages or ["en"]

        try:
            fetched = self._transcript_api.fetch(video_id, languages=languages)
        except (TranscriptsDisabled, NoTranscriptFound, VideoUnavailable) as exc:
            raise TranscriptUnavailable(f"No transcript available for video {video_id}") from exc

        text = " ".join(snippet.text for snippet in fetched.snippets)
        return Transcript(text=text)

    # -- convenience: full pipeline for one channel ----------------------- #

    def fetch_channel(self, channel_ref: str, hours: int = 24) -> list[ChannelVideo]:
        """Resolve -> list -> transcribe for a single channel.

        Never raises on a missing or blocked transcript: `video.transcript`
        stays None in that case so ingestion can keep going.
        """
        channel_id = self.resolve_channel_id(channel_ref)
        videos = self.get_latest_videos(channel_id, hours=hours)

        for video in videos:
            try:
                video.transcript = self.get_transcript(video.video_id)
            except TranscriptUnavailable:
                video.transcript = None
            except Exception:
                # Includes IpBlocked / RequestBlocked from a datacenter IP.
                # An infrastructure problem shouldn't take down the whole
                # ingestion run -- the video is still returned, just
                # without a transcript.
                video.transcript = None
            time.sleep(self.request_delay_seconds)

        return videos


if __name__ == "__main__":
    scraper = YouTubeScraper()
    for video in scraper.fetch_channel("@BetaSquad", hours=1000):
        has_transcript = video.transcript is not None
        print(f"{video.published_at:%Y-%m-%d %H:%M} | transcript={has_transcript} | {video.title}")
