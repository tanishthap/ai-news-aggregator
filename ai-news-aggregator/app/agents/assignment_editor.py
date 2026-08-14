"""Assignment Editor agent.

In a newsroom, the Assignment Editor is the person who decides which
stories matter and how they should be prioritized for the day -- not
the reporter who writes them (that's the digest agent,
app/agents/digest_agent.py), but the editor who reads the day's
output and decides what leads.

This agent takes a batch of digests plus the reader profile
(app/user_profile.py) and scores each one, using the Gemini API's
Structured Outputs -- same setup as the digest agent (see that file's
docstring for why Gemini rather than OpenAI's Responses API: the
OpenAI account in use ran out of credits).

Ranking design -- pointwise scoring, not direct listwise ranking:
rather than asking the model to hand back one fully ordered list
(unreliable once the batch gets large -- LLMs are prone to losing
track of order and to positional bias across many items), this asks it
to independently score every digest 0-100 (pointwise scoring), and the
caller (app/rank_digests.py) sorts deterministically by score in
Python. That also makes the score itself a reusable signal later, e.g.
to filter down to only 80+ stories.

Reference: https://ai.google.dev/gemini-api/docs/structured-output
"""

from __future__ import annotations

import json

from google import genai
from pydantic import BaseModel, Field

from ..user_profile import CATEGORIES, USER_PROFILE

RANKING_MODEL = "gemini-3.1-flash-lite"

_INSTRUCTIONS = (
    "You are the Assignment Editor for a personal AI news digest -- the "
    "person who decides which stories matter most today and how "
    "strongly they deserve the reader's attention. You will be given "
    "the reader's profile and a JSON array of digests, each with an "
    "id, source, title, and summary.\n\n"
    "For EVERY digest in the input, return exactly one ranking entry "
    "(same count in, same count out -- never invent an id that wasn't "
    "given to you, never skip one you were given):\n"
    "- digest_id: copy the id exactly as given.\n"
    "- category: the single best-fitting label from this fixed list -- "
    f"{', '.join(CATEGORIES)}. If truly nothing fits, use \"Other\".\n"
    "- score: an integer 0-100 for how much this specific story "
    "deserves the reader's attention today. Score on genuine "
    "newsworthiness and significance (a major release, a landmark "
    "result, a widely-discussed incident) -- not just topical "
    "relevance, since the reader's interests are broad and almost "
    "everything AI-related is 'on topic' for them. A routine or minor "
    "item should score low even when it's squarely on-topic.\n"
    "- rationale: one short sentence justifying the score.\n\n"
    "Reader profile:\n"
    f"{USER_PROFILE}"
)


class RankedItem(BaseModel):
    digest_id: int = Field(description="The id of the digest being scored, copied from the input.")
    category: str = Field(description="Best-fitting category label for this digest.")
    score: int = Field(ge=0, le=100, description="0-100: how much this story deserves attention today.")
    rationale: str = Field(description="One short sentence justifying the score.")


class RankingResult(BaseModel):
    rankings: list[RankedItem]


def rank_digests(*, digests: list[dict], client: genai.Client | None = None) -> RankingResult:
    """One Gemini call: score every item in `digests` against the
    reader profile. Each dict needs at least id/source/title/summary
    keys -- see app/rank_digests.py for how these are built from the
    `digests` table.

    `client` is injectable so tests/processors can pass a stub instead
    of hitting the real API.
    """
    client = client or genai.Client()
    response = client.models.generate_content(
        model=RANKING_MODEL,
        contents=json.dumps(digests),
        config={
            "system_instruction": _INSTRUCTIONS,
            "response_mime_type": "application/json",
            "response_schema": RankingResult,
        },
    )
    result = RankingResult.model_validate_json(response.text)

    # Defensive normalization: if the model ever returns a category
    # outside the fixed vocabulary, fall back to "Other" rather than
    # letting an unexpected label leak into the database.
    valid_categories = set(CATEGORIES) | {"Other"}
    for item in result.rankings:
        if item.category not in valid_categories:
            item.category = "Other"
    return result
