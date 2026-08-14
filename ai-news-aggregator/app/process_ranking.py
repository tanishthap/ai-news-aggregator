"""CLI entry point for the Assignment Editor ranking pass.

    uv run python -m app.process_ranking [hours]

Ranks digests whose source article/video was published within the
last `hours` hours (default 24).
against the reader profile in app/user_profile.py and prints the
result, highest score first. `hours` is optional -- defaults to 24.
"""

from __future__ import annotations

import sys

from .rank_digests import run_ranking


def main(hours: int = 24) -> None:
    ranked = run_ranking(hours=hours)
    if not ranked:
        print(f"No digests found in the last {hours} hour(s).")
        return

    print(f"Top stories from the last {hours} hour(s), {len(ranked)} ranked:\n")
    for row in ranked:
        print(f"[{row['score']:3d}] ({row['category']}) {row['title']}")
        print(f"      {row['rationale']}")
        print(f"      {row['url']}\n")


if __name__ == "__main__":
    hours = int(sys.argv[1]) if len(sys.argv) > 1 else 24
    main(hours)
