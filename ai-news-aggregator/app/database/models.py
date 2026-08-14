"""SQLAlchemy models.

One table per source (matching the reference project), not a single
shared `articles` table. Each row's natural key from the source itself
is the primary key -- no separate surrogate id column:

- openai_articles / anthropic_articles: `guid` (the RSS <guid>, i.e.
  what the scrapers call `external_id`)
- youtube_videos: `video_id`

Re-running a scraper over an overlapping window skips a row whose
primary key already exists -- never duplicates, never updates it
(see ContentRepository.upsert_new_rows()).

`digests` is a separate table (stage 3), one row per source article/
video, produced by app/agents/digest_agent.py. It's polymorphic across
the three source tables: exactly one of openai_guid / anthropic_guid /
youtube_video_id is set per row (enforced by ck_digest_source_matches_type
below), matching `source_type`. Each is a real foreign key -- that's the
"database link" back to the source row -- and each has its own unique
constraint so a source row can have at most one digest (Postgres treats
multiple NULLs in a unique column as distinct, so this only constrains
the non-null case, i.e. exactly what we want).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class OpenAIArticle(Base):
    __tablename__ = "openai_articles"

    guid: Mapped[str] = mapped_column(Text, primary_key=True)
    title: Mapped[str] = mapped_column(Text)
    url: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    category: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Left NULL at ingest time -- filled in later by the separate
    # processing pass in app/process_openai.py (get_markdown()).
    # See ContentRepository.get_missing_markdown().
    markdown: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class AnthropicArticle(Base):
    __tablename__ = "anthropic_articles"

    guid: Mapped[str] = mapped_column(Text, primary_key=True)
    title: Mapped[str] = mapped_column(Text)
    url: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    category: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Filled in later by app/process_anthropic.py -- see OpenAIArticle above.
    markdown: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class YouTubeVideo(Base):
    __tablename__ = "youtube_videos"

    video_id: Mapped[str] = mapped_column(Text, primary_key=True)
    title: Mapped[str] = mapped_column(Text)
    url: Mapped[str] = mapped_column(Text)
    channel_id: Mapped[str] = mapped_column(Text, index=True)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Left NULL at ingest time -- filled in later by app/process_youtube.py.
    # See ContentRepository.get_missing_transcripts().
    transcript: Mapped[str | None] = mapped_column(Text, nullable=True)
    # True once we've confirmed there genuinely is no transcript for this
    # video (captions disabled, none found, video unavailable) -- keeps
    # process_youtube.py from retrying it forever. Stays False for videos
    # not yet tried AND for transient failures (e.g. a blocked request),
    # which should still be retried later.
    transcript_unavailable: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Digest(Base):
    __tablename__ = "digests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # "openai" | "anthropic" | "youtube" -- says which of the three FK
    # columns below is populated for this row.
    source_type: Mapped[str] = mapped_column(Text, nullable=False)

    # Exactly one of these three is non-null per row (see check
    # constraint below) -- the real foreign-key "database link" back to
    # the source article/video.
    openai_guid: Mapped[str | None] = mapped_column(
        Text, ForeignKey("openai_articles.guid"), nullable=True
    )
    anthropic_guid: Mapped[str | None] = mapped_column(
        Text, ForeignKey("anthropic_articles.guid"), nullable=True
    )
    youtube_video_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("youtube_videos.video_id"), nullable=True
    )

    # Denormalized copy of the source row's URL so callers can render a
    # digest without a join.
    url: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            "(source_type = 'openai' AND openai_guid IS NOT NULL "
            "  AND anthropic_guid IS NULL AND youtube_video_id IS NULL) OR "
            "(source_type = 'anthropic' AND anthropic_guid IS NOT NULL "
            "  AND openai_guid IS NULL AND youtube_video_id IS NULL) OR "
            "(source_type = 'youtube' AND youtube_video_id IS NOT NULL "
            "  AND openai_guid IS NULL AND anthropic_guid IS NULL)",
            name="ck_digest_source_matches_type",
        ),
        UniqueConstraint("openai_guid", name="uq_digest_openai_guid"),
        UniqueConstraint("anthropic_guid", name="uq_digest_anthropic_guid"),
        UniqueConstraint("youtube_video_id", name="uq_digest_youtube_video_id"),
    )


class RankedDigest(Base):
    """Stage 4: one row per (digest, ranking run) -- produced by the
    Assignment Editor agent (app/agents/assignment_editor.py) via
    app/rank_digests.py, which scores every digest from the last N
    hours against the reader profile in app/user_profile.py.

    Kept as its own table rather than adding score columns onto
    `digests` so re-running the ranking never overwrites history --
    every run just inserts a fresh batch of rows, each tagged with its
    own ranked_at. A digest can have zero, one, or many ranked_digests
    rows over time (e.g. if you re-run the ranking more than once).
    """

    __tablename__ = "ranked_digests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    digest_id: Mapped[int] = mapped_column(Integer, ForeignKey("digests.id"), nullable=False)

    # One of the fixed categories in app/user_profile.py (or "Other").
    category: Mapped[str] = mapped_column(Text, nullable=False)
    # 0-100: how much this story deserves the reader's attention today.
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    # One-sentence justification for the score.
    rationale: Mapped[str] = mapped_column(Text, nullable=False)

    ranked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
