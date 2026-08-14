"""Repository for the three source tables (openai_articles,
anthropic_articles, youtube_videos) plus the digests table.

Deliberately small: one generic "insert whatever's not already there"
helper shared by all three source tables, since they all follow the
same skip-on-conflict rule -- just with a different table and primary
key.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import AnthropicArticle, Digest, OpenAIArticle, RankedDigest, YouTubeVideo

# Maps a source model to the Digest FK column that links back to it, and
# to that model's own primary-key attribute name / digest source_type
# string. Used by get_articles_missing_digest() / create_digest() so
# callers don't need to know these details for each of the three sources.
_DIGEST_FK_BY_MODEL: dict[type, str] = {
    OpenAIArticle: "openai_guid",
    AnthropicArticle: "anthropic_guid",
    YouTubeVideo: "youtube_video_id",
}
_PK_ATTR_BY_MODEL: dict[type, str] = {
    OpenAIArticle: "guid",
    AnthropicArticle: "guid",
    YouTubeVideo: "video_id",
}
_SOURCE_TYPE_BY_MODEL: dict[type, str] = {
    OpenAIArticle: "openai",
    AnthropicArticle: "anthropic",
    YouTubeVideo: "youtube",
}


def upsert_new_rows(
    session: Session, model: type, pk_attr: str, rows: list[dict[str, Any]]
) -> int:
    """Insert every row whose primary key isn't already in `model`'s
    table. Rows that already exist are silently skipped, not updated --
    the first-seen version of a row wins forever. Returns how many were
    newly inserted.
    """
    if not rows:
        return 0

    pk_column = getattr(model, pk_attr)
    incoming_ids = [row[pk_attr] for row in rows]
    existing_ids = set(
        session.execute(select(pk_column).where(pk_column.in_(incoming_ids))).scalars()
    )

    new_count = 0
    for row in rows:
        if row[pk_attr] in existing_ids:
            continue
        session.add(model(**row))
        new_count += 1

    session.flush()
    return new_count


class ContentRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def upsert_openai_articles(self, rows: list[dict[str, Any]]) -> int:
        return upsert_new_rows(self.session, OpenAIArticle, "guid", rows)

    def upsert_anthropic_articles(self, rows: list[dict[str, Any]]) -> int:
        return upsert_new_rows(self.session, AnthropicArticle, "guid", rows)

    def upsert_youtube_videos(self, rows: list[dict[str, Any]]) -> int:
        return upsert_new_rows(self.session, YouTubeVideo, "video_id", rows)

    def get_missing_markdown(self, model: type, limit: int | None = None) -> list[Any]:
        """Rows with no `markdown` yet -- what a later get_markdown() pass
        should pick up. Use for OpenAIArticle / AnthropicArticle.
        `limit=None` (the default) returns every missing row.
        """
        stmt = select(model).where(model.markdown.is_(None))
        if limit is not None:
            stmt = stmt.limit(limit)
        return list(self.session.execute(stmt).scalars())

    def get_missing_transcripts(self, limit: int | None = None) -> list[YouTubeVideo]:
        """YouTubeVideo rows with no transcript yet, excluding ones
        already confirmed to have none (transcript_unavailable=True) --
        those are permanently skipped, not retried. `limit=None` returns
        every eligible row."""
        stmt = select(YouTubeVideo).where(
            YouTubeVideo.transcript.is_(None),
            YouTubeVideo.transcript_unavailable.is_(False),
        )
        if limit is not None:
            stmt = stmt.limit(limit)
        return list(self.session.execute(stmt).scalars())

    def get_articles_missing_digest(self, model: type, limit: int | None = None) -> list[Any]:
        """Rows from `model` (OpenAIArticle / AnthropicArticle /
        YouTubeVideo) that don't have a digest row yet -- an anti-join
        against `digests` on whichever FK column corresponds to this
        source. `limit=None` returns every eligible row.
        """
        pk_column = getattr(model, _PK_ATTR_BY_MODEL[model])
        digest_fk_column = getattr(Digest, _DIGEST_FK_BY_MODEL[model])
        already_digested = select(digest_fk_column).where(digest_fk_column.is_not(None))
        stmt = select(model).where(pk_column.not_in(already_digested))
        if limit is not None:
            stmt = stmt.limit(limit)
        return list(self.session.execute(stmt).scalars())

    def create_digest(self, model: type, row: Any, *, title: str, summary: str) -> Digest:
        """Insert one digests row linked back to `row` (an instance of
        `model`). Sets source_type and exactly the one FK column that
        matches `model`, per ck_digest_source_matches_type.
        """
        digest = Digest(
            source_type=_SOURCE_TYPE_BY_MODEL[model],
            url=row.url,
            title=title,
            summary=summary,
        )
        setattr(digest, _DIGEST_FK_BY_MODEL[model], getattr(row, _PK_ATTR_BY_MODEL[model]))
        self.session.add(digest)
        self.session.flush()
        return digest


    def get_recent_digests(self, since: datetime) -> list[Digest]:
        """Return digests whose source content was actually published
        at or after `since`.

        Filters on each source table's published_at timestamp rather
        than Digest.created_at, so old content discovered today does
        not incorrectly count as fresh news.
        """

        openai_recent = (
            select(Digest.id)
            .join(
                OpenAIArticle,
                Digest.openai_guid == OpenAIArticle.guid,
            )
            .where(
                Digest.source_type == "openai",
                OpenAIArticle.published_at >= since,
            )
        )

        anthropic_recent = (
            select(Digest.id)
            .join(
                AnthropicArticle,
                Digest.anthropic_guid == AnthropicArticle.guid,
            )
            .where(
                Digest.source_type == "anthropic",
                AnthropicArticle.published_at >= since,
            )
        )

        youtube_recent = (
            select(Digest.id)
            .join(
                YouTubeVideo,
                Digest.youtube_video_id == YouTubeVideo.video_id,
            )
            .where(
                Digest.source_type == "youtube",
                YouTubeVideo.published_at >= since,
            )
        )

        recent_ids = openai_recent.union(
            anthropic_recent,
            youtube_recent,
        )

        stmt = (
            select(Digest)
            .where(Digest.id.in_(recent_ids))
            .order_by(Digest.id)
        )

        return list(self.session.execute(stmt).scalars())
    
    def create_ranking(
        self,
        *,
        digest_id: int,
        category: str,
        score: int,
        rationale: str,
        ranked_at: datetime | None = None,
    ) -> RankedDigest:
        """Insert one ranked_digests row for a single ranking run.
        Never overwrites or dedupes against earlier runs -- see
        RankedDigest's docstring in app/database/models.py.

        Pass the SAME `ranked_at` for every row in one run (see
        app/rank_digests.py) rather than relying on the column's
        server_default -- that keeps "which rows belong to the same
        run" (used by get_latest_top_ranked()) deterministic across
        both SQLite (tests) and Postgres, instead of depending on
        per-database now()-within-a-transaction semantics.
        """
        ranking = RankedDigest(
            digest_id=digest_id, category=category, score=score, rationale=rationale
        )
        if ranked_at is not None:
            ranking.ranked_at = ranked_at
        self.session.add(ranking)
        self.session.flush()
        return ranking

    def get_latest_top_ranked(self, limit: int = 10) -> list[tuple[RankedDigest, Digest]]:
        """The top `limit` (RankedDigest, Digest) pairs, by score, from
        the single most recent ranking run (app/rank_digests.py) --
        what the email agent (app/build_email.py) sends out.

        "Most recent run" = every row sharing the max ranked_at value.
        Because run_ranking() inserts a run's rows inside one
        transaction, and Postgres's now() returns the transaction start
        time, every row from the same run shares the exact same
        ranked_at -- so this correctly groups one run without needing a
        separate run-id column.
        """
        latest_run = select(func.max(RankedDigest.ranked_at)).scalar_subquery()
        stmt = (
            select(RankedDigest, Digest)
            .join(Digest, Digest.id == RankedDigest.digest_id)
            .where(RankedDigest.ranked_at == latest_run)
            .order_by(RankedDigest.score.desc())
            .limit(limit)
        )
        return list(self.session.execute(stmt).all())
