"""Digest agent: turns one source row (an OpenAI/Anthropic article or a
YouTube video) into a short digest -- a title plus a 2-3 sentence
summary -- using the Gemini API's Structured Outputs.

Originally built against OpenAI's Responses API, but the OpenAI account
in use ran out of credits, so this was switched to Gemini (google-genai
SDK). Structured Outputs here works by configuring `response_schema` on
the generation call (`response_mime_type: "application/json"` +
`response_schema: <Pydantic model>`) -- Gemini's equivalent of the
Responses API's `text.format`. Passing a Pydantic model directly as
`response_schema` is supported out of the box; the SDK builds the
schema for you.

Model: gemini-3.1-flash-lite -- the cheapest currently-active Gemini 3
model ($0.25/$1.50 per 1M tokens as of Aug 2026), in the same cost/speed
tier as gpt-4.1-mini. A few other model names either 404 ("no longer
available to new users" -- gemini-2.5-flash / gemini-2.5-flash-lite) or
aren't reachable on this account's API version (gemini-3-flash) as of
this writing; gemini-3.1-flash-lite and the gemini-flash-latest alias
both verified working.

Auth: reads GEMINI_API_KEY (or GOOGLE_API_KEY) from the environment
automatically via genai.Client() -- no code change needed if the key is
ever rotated, just update .env.

Reference: https://ai.google.dev/gemini-api/docs/structured-output
"""

from __future__ import annotations

from google import genai
from pydantic import BaseModel, Field

DIGEST_MODEL = "gemini-3.1-flash-lite"

_INSTRUCTIONS = (
    "You are a news digest writer for an AI industry news aggregator. "
    "You will be given the source, title, and full text (article "
    "markdown or video transcript) of one piece of content. Write a "
    "short digest for a reader who wants to stay current on AI news "
    "without reading the whole thing.\n\n"
    "Rules:\n"
    "- title: a concise, informative headline (you may reuse or lightly "
    "edit the original title).\n"
    "- summary: exactly 2-3 sentences of plain prose (no bullet points, "
    "no markdown) covering what happened and why it matters.\n"
    "- Base the summary only on the provided content -- never invent "
    "facts, numbers, or claims that aren't in it.\n"
    "- If the provided content is too thin to summarize meaningfully, "
    "write the best short summary you can from the title alone rather "
    "than refusing."
)


class DigestOutput(BaseModel):
    """Structured Outputs schema for one digest -- passed directly as
    `response_schema` to client.models.generate_content()."""

    title: str = Field(description="Concise digest headline, one line.")
    summary: str = Field(description="2-3 sentence summary of the content.")


def build_input_text(*, source: str, title: str, body: str | None) -> str:
    """Assemble the prompt content the model sees: source + title +
    whatever body text is available (markdown / transcript / falls back
    to just the title if neither is available yet)."""
    body_text = body or "(no article/transcript text available -- summarize from the title alone)"
    return f"Source: {source}\nTitle: {title}\n\nContent:\n{body_text}"


def generate_digest(
    *, source: str, title: str, body: str | None, client: genai.Client | None = None
) -> DigestOutput:
    """Call the Gemini API once and return a structured DigestOutput.

    `client` is injectable so tests/processors can pass a stub instead
    of hitting the real API -- see app/digest.py for how the processors
    use this.
    """
    client = client or genai.Client()
    response = client.models.generate_content(
        model=DIGEST_MODEL,
        contents=build_input_text(source=source, title=title, body=body),
        config={
            "system_instruction": _INSTRUCTIONS,
            "response_mime_type": "application/json",
            "response_schema": DigestOutput,
        },
    )
    return DigestOutput.model_validate_json(response.text)
