"""The reader profile used by the Assignment Editor agent
(app/agents/assignment_editor.py) to score each day's digests.

Edit USER_PROFILE (and CATEGORIES, if you want to change the tagging
vocabulary) directly to change what gets surfaced first -- both are
read fresh on every ranking run, no other code changes needed.
"""

from __future__ import annotations

# Used by the email agent (app/agents/email_agent.py) to address you by
# name in the daily digest email ("Hey Tanishtha, here's your...").
# Edit this if you'd rather it use something else.
USER_NAME: str = "Tanishtha"

# Fixed vocabulary the Assignment Editor tags every digest with. Kept
# as a flat list (not nested/weighted) because the reader's interest
# spans nearly the whole field -- see the note in USER_PROFILE below
# about how ranking actually discriminates between stories.
CATEGORIES: list[str] = [
    "Frontier Models",
    "AI Research",
    "AI Agents",
    "Computer Vision",
    "Generative Media",
    "AI Coding",
    "Robotics / Physical AI",
    "AI + Science",
    "AI + Healthcare",
    "AI Business",
    "Enterprise AI",
    "AI Economics / Investment",
    "AI Chips",
    "AI Infrastructure",
    "AI Cybersecurity",
    "AI Safety / Alignment",
    "AI Regulation",
    "Copyright / IP",
    "Privacy / Surveillance",
    "AI Ethics",
    "AI Education",
    "Creative Industries",
    "AI Gaming",
    "AI Journalism",
    "AI Geopolitics",
    "AI Defense",
    "Open Source AI",
    "Benchmarks / Evaluation",
    "AI Failures / Incidents",
    "Real-World Adoption",
    "Jobs / Labor",
    "AI Startups",
    "AI Company Competition",
    "Academic Research",
    "Developer Ecosystem",
    "Data",
    "Energy / Environment",
    "AGI / Future",
]

USER_PROFILE: str = """\
Reader: a student who follows AI news broadly, across nearly every
corner of the field -- nothing on the list below is off-limits or
deprioritized:

Technology & research: Frontier Models, AI Research, AI Agents,
Computer Vision, Generative Media, AI Coding, Robotics / Physical AI,
AI + Science, AI + Healthcare, Benchmarks / Evaluation, Academic
Research, Developer Ecosystem, Data, Open Source AI.

Business & economy: AI Business, Enterprise AI, AI Economics /
Investment, AI Chips, AI Infrastructure, AI Startups, AI Company
Competition, Real-World Adoption, Jobs / Labor.

Safety, policy & society: AI Cybersecurity, AI Safety / Alignment, AI
Regulation, Copyright / IP, Privacy / Surveillance, AI Ethics, AI
Failures / Incidents.

Culture & other: AI Education, Creative Industries, AI Gaming, AI
Journalism, AI Geopolitics, AI Defense, Energy / Environment, AGI /
Future.

Because the reader's interest spans almost the entire field, don't use
topical relevance alone to differentiate stories -- nearly everything
about AI qualifies as "on topic." Instead, rank primarily on genuine
newsworthiness and significance: a major frontier-model launch, a
landmark safety incident, or a widely-discussed research result should
score far higher than a minor blog post or a routine incremental
update, even when both are on the same topic.
"""
