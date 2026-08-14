"""Sandbox-only test for the email pipeline (app/build_email.py,
app/send_email.py, app/process_email.py) against an in-memory SQLite
DB, with the Gemini call and SMTP send both stubbed out. Not pushed to
the Mac project.
"""

import os
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.agents.email_agent import EmailIntro
from app.database.models import Base, Digest, RankedDigest

engine = create_engine("sqlite:///:memory:")
Base.metadata.create_all(engine)
SessionLocal = sessionmaker(bind=engine)

run_time = datetime.now(timezone.utc)

with SessionLocal() as session:
    session.add_all(
        [
            Digest(
                id=1,
                source_type="openai",
                openai_guid="g1",
                url="https://openai.com/a",
                title="Major frontier model launch",
                summary="A new frontier model with big benchmark gains.",
            ),
            Digest(
                id=2,
                source_type="anthropic",
                anthropic_guid="g2",
                url="https://anthropic.com/b",
                title="Minor blog post",
                summary="An internal engineering note.",
            ),
        ]
    )
    session.flush()
    session.add_all(
        [
            RankedDigest(digest_id=1, category="Frontier Models", score=95, rationale="Major release.", ranked_at=run_time),
            RankedDigest(digest_id=2, category="Developer Ecosystem", score=15, rationale="Minor/internal.", ranked_at=run_time),
        ]
    )
    session.commit()

import app.build_email as build_email_module


def stub_generate_email_intro(*, name, date_str, top_items, client=None):
    assert name == "Tanishtha", name
    assert len(top_items) == 2
    return EmailIntro(subject="Big model drop today", preview=f"Hey {name}, big news today.")


print("--- test 1: build_daily_email assembles greeting + LLM subject/preview + sorted items ---")
with patch.object(build_email_module, "generate_email_intro", stub_generate_email_intro), \
     patch.object(build_email_module, "SessionLocal", SessionLocal), \
     patch.object(build_email_module.genai, "Client", lambda: None):
    content = build_email_module.build_daily_email(limit=10)

assert content["subject"] == "Big model drop today", content
assert "Tanishtha" in content["greeting"], content
assert len(content["items"]) == 2
assert content["items"][0]["score"] == 95 and content["items"][1]["score"] == 15, content["items"]
print("  OK: content assembled correctly, sorted highest score first")

print("--- test 2: render_email_body produces sane plain text and html ---")
plain_text, html = build_email_module.render_email_body(content)
assert "Tanishtha" in plain_text
assert "Major frontier model launch" in plain_text
assert "https://openai.com/a" in plain_text
assert "<html>" in html and "Major frontier model launch" in html
assert 'href="https://openai.com/a"' in html
print("  OK: plain text and html both contain expected content")

print("--- test 3: build_daily_email with no ranked rows returns a graceful empty result ---")
empty_engine = create_engine("sqlite:///:memory:")
Base.metadata.create_all(empty_engine)
EmptySessionLocal = sessionmaker(bind=empty_engine)
with patch.object(build_email_module, "generate_email_intro", stub_generate_email_intro), \
     patch.object(build_email_module, "SessionLocal", EmptySessionLocal), \
     patch.object(build_email_module.genai, "Client", lambda: None):
    empty_content = build_email_module.build_daily_email(limit=10)
assert empty_content["items"] == [], empty_content
assert "run app.rank_digests" in empty_content["preview"]
print("  OK: empty state handled without crashing")

print("--- test 4: send_email logs into Gmail SMTP and sends to self by default ---")
os.environ["GMAIL_ADDRESS"] = "me@gmail.com"
os.environ["GMAIL_APP_PASSWORD"] = "fake-app-password"

import app.send_email as send_email_module

fake_smtp = MagicMock()
fake_smtp.__enter__ = MagicMock(return_value=fake_smtp)
fake_smtp.__exit__ = MagicMock(return_value=False)

with patch.object(send_email_module.smtplib, "SMTP_SSL", return_value=fake_smtp) as smtp_cls:
    send_email_module.send_email("Subject line", "plain body", html="<p>html body</p>")

smtp_cls.assert_called_once_with("smtp.gmail.com", 465)
fake_smtp.login.assert_called_once_with("me@gmail.com", "fake-app-password")
assert fake_smtp.sendmail.call_count == 1
sent_from, sent_to, sent_msg = fake_smtp.sendmail.call_args[0]
assert sent_from == "me@gmail.com"
assert sent_to == ["me@gmail.com"], sent_to  # defaults to sending to self
assert "Subject line" in sent_msg
assert "plain body" in sent_msg
assert "<p>html body</p>" in sent_msg
print("  OK: SMTP_SSL used, logged in with app password, sent from/to self, both parts attached")

print("--- test 5: send_email respects an explicit to_address override ---")
with patch.object(send_email_module.smtplib, "SMTP_SSL", return_value=fake_smtp):
    send_email_module.send_email("S", "body", to_address="someone-else@example.com")
_, sent_to2, _ = fake_smtp.sendmail.call_args[0]
assert sent_to2 == ["someone-else@example.com"], sent_to2
print("  OK: explicit to_address overrides the self-send default")

print("\nAll email pipeline tests passed.")
