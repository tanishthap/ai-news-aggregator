"""Simplest zero-cost way to send yourself an email from Python: Gmail's
own SMTP server with an "app password." No external service, no new
account to create, no paid tier, no dependency beyond the Python
standard library (smtplib + email). Works with any Gmail address you
already have.

One-time setup (in your browser, not code -- do this once):
1. Turn on 2-Step Verification on your Google account, if it isn't
   already: https://myaccount.google.com/signinoptions/two-step-verification
   (Google requires this before it'll let you create an app password.)
2. Create an app password: https://myaccount.google.com/apppasswords
   Name it anything (e.g. "ai-news-aggregator"), then copy the 16-character
   password it gives you -- you won't see it again after leaving the page.
3. Add to .env (NOT your regular Gmail password -- Google blocks plain
   password SMTP login entirely now, an app password is required):
     GMAIL_ADDRESS=your_address@gmail.com
     GMAIL_APP_PASSWORD=<the 16-character app password, no spaces>

That's it -- send_email() below logs into smtp.gmail.com with those
credentials and sends the message from your address to your address
(or wherever you point `to_address`).
"""

from __future__ import annotations

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def send_email(
    subject: str,
    plain_text: str,
    html: str | None = None,
    to_address: str | None = None,
) -> None:
    """Send one email via Gmail SMTP. Defaults to sending from your
    Gmail address to that same address (i.e. to yourself) -- pass
    `to_address` to send elsewhere instead.

    Reads GMAIL_ADDRESS / GMAIL_APP_PASSWORD from the environment --
    see this module's docstring for one-time setup.
    """
    gmail_address = os.environ["GMAIL_ADDRESS"]
    app_password = os.environ["GMAIL_APP_PASSWORD"]
    to_address = to_address or gmail_address

    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = gmail_address
    message["To"] = to_address
    # Attach plain text first, then html -- email clients use the LAST
    # part they understand, so html (the nicer version) should be last.
    message.attach(MIMEText(plain_text, "plain"))
    if html:
        message.attach(MIMEText(html, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(gmail_address, app_password)
        server.sendmail(gmail_address, [to_address], message.as_string())
