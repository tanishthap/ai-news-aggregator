"""YouTube transcript processor: fills in `youtube_videos.transcript`
for every video that doesn't have one yet.

Usage (inside the app container):
    uv run python -m app.process_youtube        # process every eligible row
    uv run python -m app.process_youtube 5       # process at most 5 rows

Safe to re-run any time. Videos genuinely confirmed to have no
transcript (captions disabled, none found, video unavailable) are
marked `transcript_unavailable=True` and are never retried again --
this is what stops it from looping forever on videos that will simply
never succeed. Videos that failed for a transient reason (e.g. a
blocked/rate-limited request) are left alone and retried next run.
"""

from __future__ import annotations

import sys

from .enrich import fill_youtube_transcripts


def main(limit: int | None = None) -> None:
    result = fill_youtube_transcripts(limit=limit)
    print(f"youtube_videos: {result}")


if __name__ == "__main__":
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    main(limit)
