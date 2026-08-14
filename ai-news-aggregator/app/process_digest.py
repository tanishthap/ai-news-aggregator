"""Digest processor: generates a title + 2-3 sentence summary (via the
OpenAI Responses API, gpt-4.1-mini, Structured Outputs) for every
openai_articles / anthropic_articles / youtube_videos row that doesn't
have a digest yet, and writes it to the `digests` table.

Usage (inside the app container):
    uv run python -m app.process_digest        # process every row missing a digest, all 3 sources
    uv run python -m app.process_digest 5       # process at most 5 rows PER SOURCE (15 total max)

Safe to re-run any time -- only rows with no digests row yet are
touched, so already-digested rows are never re-summarized.

Requires OPENAI_API_KEY to be set (in .env, loaded via env_file: .env
in docker-compose.yml -- same mechanism as DATABASE_URL).
"""

from __future__ import annotations

import sys

from .digest import run_digest_enrichment


def main(limit: int | None = None) -> None:
    for source, counts in run_digest_enrichment(limit=limit).items():
        print(f"{source}: {counts}")


if __name__ == "__main__":
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    main(limit)
