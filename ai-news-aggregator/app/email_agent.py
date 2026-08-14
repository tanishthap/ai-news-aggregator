"""Email agent for the daily AI news digest.

Uses Gemini Structured Outputs to generate a specific subject line
and a short introduction based on the day's highest-ranked stories.
"""

from __future__ import annotations

import json

from google import genai
from pydantic import BaseModel, Field


EMAIL_MODEL = "gemini-3.1-flash-lite"


_INSTRUCTIONS = """
You write the opening of a personalized daily AI news digest.

You will receive:
- the reader's name
- today's date
- the day's highest-ranked AI news stories
- the category of each story
- the ranking rationale when available

Return:

1. subject
A concise, specific email subject line based on what is genuinely
important in today's news.

Do not use generic subjects such as:
"Your Daily AI Digest"
"AI News Today"
"Daily AI Update"

2. preview
Write 2-4 friendly sentences introducing today's digest.

Write directly to the reader.

Identify the most important development or an important theme across
the stories rather than simply listing all the headlines.

Do not exaggerate the significance of the stories.
"""


class EmailIntro(BaseModel):
    subject: str = Field(
        description="Specific subject line describing today's most important AI news."
    )

    preview: str = Field(
        description="Friendly 2-4 sentence introduction to today's AI news digest."
    )


def generate_email_intro(
    *,
    name: str,
    date_str: str,
    top_items: list[dict],
    client: genai.Client | None = None,
) -> EmailIntro:
    """Generate the subject and introduction for today's digest."""

    client = client or genai.Client()

    contents = json.dumps(
        {
            "name": name,
            "date": date_str,
            "top_stories": top_items,
        }
    )

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
