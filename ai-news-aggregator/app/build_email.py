"""Build and render the daily AI news digest email."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo
from html import escape
from typing import Any

from google import genai

from .agents.email_agent import generate_email_intro
from .database.repository import ContentRepository
from .database.session import SessionLocal
from .user_profile import USER_NAME


def build_daily_email(
    limit: int = 10,
    client: genai.Client | None = None,
) -> dict[str, Any]:
    """Build today's email from the most recent ranking run."""

    client = client or genai.Client()

    # Portable across macOS + Linux/Docker.
    now = datetime.now(ZoneInfo("America/Los_Angeles"))
    date_str = f"{now.strftime('%B')} {now.day}, {now.year}"

    greeting = (
        f"Hey {USER_NAME}, here's your daily digest "
        f"of AI news for {date_str}."
    )

    with SessionLocal() as session:
        repo = ContentRepository(session)
        rows = repo.get_latest_top_ranked(limit=limit)

    if not rows:
        return {
            "subject": f"Your AI digest for {date_str}",
            "greeting": greeting,
            "preview": (
                "No new stories were ranked yet -- "
                "run app.rank_digests first."
            ),
            "items": [],
        }

    items = []

    for ranking, digest in rows:
        items.append(
            {
                "title": digest.title,
                "url": digest.url,
                "summary": digest.summary,
                "category": ranking.category,
                "score": ranking.score,
                "rationale": ranking.rationale,
            }
        )

    intro = generate_email_intro(
        name=USER_NAME,
        date_str=date_str,
        top_items=[
            {
                "title": item["title"],
                "category": item["category"],
                "rationale": item["rationale"],
            }
            for item in items
        ],
        client=client,
    )

    return {
        "subject": intro.subject,
        "greeting": greeting,
        "preview": intro.preview,
        "items": items,
    }


def render_email_body(
    email_content: dict[str, Any],
) -> tuple[str, str]:
    """Render the digest as plain text and HTML."""

    greeting = email_content["greeting"]
    preview = email_content["preview"]
    items = email_content["items"]

    # -----------------------
    # Plain-text version
    # -----------------------

    text_lines = [
        greeting,
        "",
        preview,
        "",
    ]

    # -----------------------
    # HTML version
    # -----------------------

    html_items = []

    for i, item in enumerate(items, start=1):

        text_lines.append(
            f"{i}. [{item['category']}] {item['title']}"
        )

        text_lines.append(
            f"   {item['summary']}"
        )

        text_lines.append(
            f"   {item['url']}"
        )

        text_lines.append("")

        title = escape(str(item["title"]))
        category = escape(str(item["category"]))
        summary = escape(str(item["summary"]))
        url = escape(str(item["url"]), quote=True)

        html_items.append(
            "<li style='margin-bottom: 20px;'>"
            f"<strong>{title}</strong><br>"
            f"<em>{category}</em><br><br>"
            f"{summary}<br><br>"
            f'<a href="{url}">Read story</a>'
            "</li>"
        )

    plain_text = "\n".join(text_lines).rstrip() + "\n"

    safe_greeting = escape(str(greeting))
    safe_preview = escape(str(preview))

    html = (
        "<html>"
        "<body style='font-family: Arial, sans-serif; "
        "max-width: 700px; margin: auto; line-height: 1.5;'>"
        f"<h2>{safe_greeting}</h2>"
        f"<p>{safe_preview}</p>"
        "<hr>"
        "<ol>"
        f"{''.join(html_items)}"
        "</ol>"
        "</body>"
        "</html>"
    )

    return plain_text, html
