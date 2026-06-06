"""Shared agent-loop policy constants (AI-Q + OpenClaw)."""

from __future__ import annotations

# Bounded execution — production agent patterns (step budget, tool caps)
MAX_AGENT_STEPS_PER_TURN = 8
MAX_SAME_TOOL_CALLS_PER_TURN = 2
MAX_OUTPUT_CHARS_TELEGRAM = 3800  # Telegram hard limit 4096; leave margin
HEARTBEAT_ACK_MAX_CHARS = 300

# Tool-first routing
BRIEFING_TOOL = "get_london_city_briefing"
BRIEFING_TOOL_SLIM = "disruptron_ops__get_london_city_briefing"
BRIEFING_TOOL_IMPACT = "london_impact__get_london_city_briefing"

# Response sections (autonomous ops contract)
RESPONSE_SECTIONS = (
    "Situation",
    "Impact",
    "Evidence",
    "Recommended actions",
)
