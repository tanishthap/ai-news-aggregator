"""App-wide config.

Kept as plain Python for now -- simplest possible "storage" for the one
setting we need. Move to a DB table or YAML file later if this grows.
"""

from __future__ import annotations

# YouTube channels to monitor. Any ref YouTubeScraper.resolve_channel_id()
# accepts works here: @handle, channel ID, or full channel URL.
# Edit this list to add/remove channels.
YOUTUBE_CHANNELS: list[str] = [
    "@aiexplained-official",
    "@mreflow",
    "@TwoMinutePapers",
    "@matthew_berman",
    "@MachineLearningStreetTalk",
    "@googledeepmind",
    "@OpenAI",
    "@anthropic-ai",
    "@NVIDIA",
    "@IBMTechnology",
]

# Default lookback window for a run, in hours. Every source (YouTube,
# OpenAI, Anthropic) is called with this same window.
DEFAULT_LOOKBACK_HOURS = 24
