"""Stage 4: ranking.

Stage 3 (app/digest.py) produces short digests. This module is the
fourth pass: pull every digest created in the last N hours, hand the
whole batch to the Assignment Editor agent
(app/agents/assignment_editor.py) in one call, persist the resulting
scores as ranked_digests rows, and return them sorted highest score
first.

Safe to run more than once a day/on overlapping windows -- it never
mutates or dedupes against earlier runs, it just adds a fresh batch of
ranked_digests rows tagged with their own ranked_at. If you run it
twice in a day you'll get two scored batches for any digest created
before both runs; that's expected, not a bug -- treat the newest run
as the current answer.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from google import genai

from .agents.assignment_editor import rank_digests
from .database.repository import ContentRepository
from .database.session import SessionLocal


def run_ranking(hours: int = 24, client: genai.Client | None = None) -> list[dict[str, Any]]:
    """Score every digest created in the last `hours` hours against the
    reader profile (app/user_profile.py), persist the scores, and
    return them as plain dicts sorted highest score first.
    """
    client = client or genai.Client()
    run_time = datetime.now(timezone.utc)
    cutoff = run_time - timedelta(hours=hours)

    with SessionLocal() as session:
        repo = ContentRepository(session)
        digests = repo.get_recent_digests(since=cutoff)
        if not digests:
            return []

        result = rank_digests(
            digests=[
                {"id": d.id, "source": d.source_type, "title": d.title, "summary": d.summary}
                for d in digests
            ],
            client=client,
        )

        by_id = {d.id: d for d in digests}
        ranked_rows: list[dict[str, Any]] = []
        for item in result.rankings:
            digest = by_id.get(item.digest_id)
            if digest is None:
                # Model referenced an id we never sent -- ignore rather
                # than crash the whole run over one bad entry.
                continue
            row = repo.create_ranking(
                digest_id=digest.id,
                category=item.category,
                score=item.score,
                rationale=item.rationale,
                ranked_at=run_time,
            )
            ranked_rows.append(
                {
                    "digest_id": digest.id,
                    "source_type": digest.source_type,
                    "title": digest.title,
                    "url": digest.url,
                    "summary": digest.summary,
                    "category": row.category,
                    "score": row.score,
                    "rationale": row.rationale,
                }
            )
        session.commit()

    ranked_rows.sort(key=lambda r: r["score"], reverse=True)
    return ranked_rows


if __name__ == "__main__":
    for row in run_ranking():
        print(f"[{row['score']:3d}] ({row['category']}) {row['title']}")
