"""CLI entry point for the daily digest email.

    uv run python -m app.process_email [limit]

Builds today's email (top `limit` stories, default 10, from the most
recent app.rank_digests run + a Gemini-written subject/preview) and
sends it to yourself via Gmail SMTP.

Requires GMAIL_ADDRESS and GMAIL_APP_PASSWORD in .env -- see
app/send_email.py's docstring for one-time setup.
"""

from __future__ import annotations

import sys

from .build_email import build_daily_email, render_email_body
from .send_email import send_email


def main(limit: int = 10) -> None:
    content = build_daily_email(limit=limit)
    if not content["items"]:
        print(content["preview"])
        return

    plain_text, html = render_email_body(content)
    send_email(subject=content["subject"], plain_text=plain_text, html=html)
    print(f"Sent: {content['subject']!r} ({len(content['items'])} stories)")


if __name__ == "__main__":
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    main(limit)
