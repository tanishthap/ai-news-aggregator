"""Email agent: writes the subject line and short preview paragraph for
the daily digest email, using the Gemini API's Structured Outputs --
same setup as the digest agent and the Assignment Editor (see
app/agents/digest_agent.py's docstring for why Gemini rather than
OpenAI's Responses API).

The rest of the email -- the "Hey {name}, here's your digest for
{date}" greeting, and the top-10 story list itself -- is built
deterministically in app/build_email.py (plain string formatting, no
LLM needed for that part). This agent's only job is the part that
actually benefits from a model: a short, specific preview of what's in
today's digest, written from the *themes* of the top stories rather
than just concatenating headlines.

Reference: https://ai.google.dev/gemini-api/docs/structured-output
"""

from __future__ import annotations

import json

from google import genai
from pydantic import BaseModel, Field

EMAIL_MODEL = "gemini-3.1-flash-lite"

_INSTRUCTIONS = (
    "You are writing the opening of a reader's personalized daily AI "
    "news digest email. You'll be given the reader's name, today's "
    "date, and the day's top-ranked stories (title, category, and a "
    "one-line rationale for why each made the cut, already sorted "
    "highest-priority first).\n\n"
    "Write:\n"
    "- subject: a short, specific email subject line. Reference what's "
    "actually notable today -- never a generic subject like 'Your "
    "Daily Digest' or 'AI News Update'.\n"
    "- preview: 2-4 friendly sentences previewing today's digest, "
    "written directly to the reader in second person. Highlight the "
    "single most important story or the overall theme across the top "
    "stories -- do not just list every headline in order."
)


class EmailIntro(BaseModel):
    subject: str = Field(description="Specific, non-generic email subject line for today's digest.")
    preview: str = Field(
        description="2-4 sentence friendly preview of today's top stories, written in second person."
    )


def generate_email_intro(
    *, name: str, date_str: str, top_items: list[dict], client: genai.Client | None = None
) -> EmailIntro:
    """One Gemini call: given the reader's name, today's date, and the
    top-ranked stories (each a dict with at least title/category), get
    back a subject line and a short preview paragraph.

    `client` is injectable for tests -- see app/build_email.py.
    """
    client = client or genai.Client()
    contents = json.dumps({"name": name, "date": date_str, "top_stories": top_items})
    response = client.models.generate_content(
        model=EMAIL_MODEL,
        contents=contents,
        config={
            "system_instruction": _INSTRUCTIONS,
            "response_mime_type": "application/json",
            "response_schema": EmailIntro,
        },
    )
    return EmailIntro.model_validate_json(response.text)
