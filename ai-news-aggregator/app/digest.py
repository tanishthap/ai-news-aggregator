"""Stage 3: digest generation.

Stage 1 (app/runner.py) lists metadata. Stage 2 (app/enrich.py) fills
in markdown/transcripts. This module is the third pass: for every
article/video that doesn't have a digest yet, call the digest agent
(app/agents/digest_agent.py, Gemini API) and write the result as a new
row in `digests` -- one row per source row, linked back to it via a
real foreign key (see Digest in app/database/models.py).

Safe to re-run any time: get_articles_missing_digest() only ever
returns rows with no digest yet, and the per-source-column unique
constraint on `digests` means a source row can never end up with two
digests even under a race.

Body text passed to the agent, per source:
- OpenAI/Anthropic: `markdown` if it's been filled in yet (see
  app/enrich.py), otherwise `description` as a fallback so a slow/failed
  markdown fetch doesn't block the digest indefinitely.
- YouTube: `transcript` if available, otherwise `description`.
"""

from __future__ import annotations

from typing import Any

from google import genai

from .agents.digest_agent import generate_digest
from .database.models import AnthropicArticle, OpenAIArticle, YouTubeVideo
from .database.repository import ContentRepository
from .database.session import SessionLocal


def _fill_digests(
    model: type, source_label: str, client: genai.Client, body_attr: str, limit: int | None = None
) -> dict[str, int]:
    """Shared by all three sources: generate a digest for every row
    missing one, committing after each row so a crash partway through
    doesn't lose progress already made. `limit=None` processes every
    missing row.
    """
    filled = failed = 0
    with SessionLocal() as session:
        repo = ContentRepository(session)
        for row in repo.get_articles_missing_digest(model, limit=limit):
            try:
                body = getattr(row, body_attr, None) or row.description
                result = generate_digest(
                    source=source_label, title=row.title, body=body, client=client
                )
                repo.create_digest(model, row, title=result.title, summary=result.summary)
                filled += 1
            except Exception as exc:
                print(f"  failed: {row.url} ({exc})")
                failed += 1
                session.rollback()
                continue
            session.commit()
    return {"filled": filled, "failed": failed}


def fill_openai_digests(
    limit: int | None = None, client: genai.Client | None = None
) -> dict[str, int]:
    return _fill_digests(OpenAIArticle, "OpenAI", client or genai.Client(), "markdown", limit=limit)


def fill_anthropic_digests(
    limit: int | None = None, client: genai.Client | None = None
) -> dict[str, int]:
    return _fill_digests(
        AnthropicArticle, "Anthropic", client or genai.Client(), "markdown", limit=limit
    )


def fill_youtube_digests(
    limit: int | None = None, client: genai.Client | None = None
) -> dict[str, int]:
    return _fill_digests(
        YouTubeVideo, "YouTube", client or genai.Client(), "transcript", limit=limit
    )


def run_digest_enrichment(limit: int | None = None) -> dict[str, dict[str, int]]:
    """Process all three sources with a single shared Gemini client."""
    client = genai.Client()
    return {
        "openai": fill_openai_digests(limit=limit, client=client),
        "anthropic": fill_anthropic_digests(limit=limit, client=client),
        "youtube": fill_youtube_digests(limit=limit, client=client),
    }


if __name__ == "__main__":
    for source, counts in run_digest_enrichment().items():
        print(f"{source}: {counts}")
