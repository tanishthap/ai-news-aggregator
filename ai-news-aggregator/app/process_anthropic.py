"""Anthropic markdown processor: fills in `anthropic_articles.markdown`
for every row that doesn't have it yet.

Usage (inside the app container):
    uv run python -m app.process_anthropic        # process every row missing markdown
    uv run python -m app.process_anthropic 5       # process at most 5 rows

Safe to re-run any time -- only rows where `markdown IS NULL` are
touched, so already-processed rows are never re-fetched or overwritten.
"""

from __future__ import annotations

import sys

from .enrich import fill_anthropic_markdown


def main(limit: int | None = None) -> None:
    result = fill_anthropic_markdown(limit=limit)
    print(f"anthropic_articles: {result}")


if __name__ == "__main__":
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    main(limit)
