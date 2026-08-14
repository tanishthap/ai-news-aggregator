"""OpenAI markdown processor: fills in `openai_articles.markdown` for
every row that doesn't have it yet.

Usage (inside the app container):
    uv run python -m app.process_openai        # process every row missing markdown
    uv run python -m app.process_openai 5       # process at most 5 rows

Safe to re-run any time -- only rows where `markdown IS NULL` are
touched, so already-processed rows are never re-fetched or overwritten.
Note: OpenAI's Cloudflare protection blocks datacenter IPs, so this
needs to run from the app container on your own machine (which it does
here), not from a cloud host.
"""

from __future__ import annotations

import sys

from .enrich import fill_openai_markdown


def main(limit: int | None = None) -> None:
    result = fill_openai_markdown(limit=limit)
    print(f"openai_articles: {result}")


if __name__ == "__main__":
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    main(limit)
