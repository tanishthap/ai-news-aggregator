"""Shared contracts for ingestion sources.

Every ingestor (YouTube, blog, etc.) produces a list of NormalizedArticle
objects. This is the only shape the rest of the pipeline (fetch_service,
db layer) needs to know about, so blog.py should mirror this same contract.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Protocol


@dataclass
class NormalizedArticle:
    """A single normalized unit of content, ready for the `articles` table.

    `external_id` + the source's id form the uniqueness key
    (source_id, external_id) described in the DB schema.
    """

    source_name: str
    external_id: str
    title: str
    url: str
    content: Optional[str]
    published_at: datetime


class Ingestor(Protocol):
    """Any ingestor (YouTube, blog, ...) must expose a `fetch()` method
    that returns already-normalized articles."""

    def fetch(self) -> list[NormalizedArticle]: ...
