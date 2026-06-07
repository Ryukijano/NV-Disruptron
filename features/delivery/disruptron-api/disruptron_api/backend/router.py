"""Dual-agent routing: interactive (disruptron) vs autonomous (lifeline)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class AgentRoute(str, Enum):
    INTERACTIVE = "interactive"
    AUTONOMOUS = "autonomous"
    DIGEST = "digest"


@dataclass(frozen=True, slots=True)
class RouteDecision:
    route: AgentRoute
    agent_id: str
    reason: str
    prefetch_briefing: bool


_INTERACTIVE_ID = "disruptron"
_AUTONOMOUS_ID = "disruptron"

_DIGEST_PATTERNS = (
    r"\bmorning\s+(briefing|plan|digest)\b",
    r"\bdaily\s+(briefing|plan|digest)\b",
    r"\btoday'?s\s+briefing\b",
    r"\bgive\s+me\s+my\s+morning\b",
)

_AUTONOMOUS_PATTERNS = (
    r"\binvestigate\b",
    r"\banaly[sz]e\b",
    r"\bmonitor\b",
    r"\bwhat\s+should\s+i\s+watch\b",
    r"\bdeep\s+dive\b",
    r"\bfull\s+picture\b",
    r"\bcomprehensive\b",
    r"\bequity\s+impact\b",
    r"\bworst\s+affected\b",
    r"\brecommended\s+actions\b",
    r"\brun\s+analysis\b",
    r"\bhow(?:'s|\s+is)\s+london\b",
    r"\blondon\s+(?:right\s+now|status|today)\b",
    r"\btransport\s+status\b",
    r"\bany\s+disruptions?\b",
    r"\bwatch\s+mode\b",
    r"\bproactive\b",
)

_QUICK_QA_PATTERNS = (
    r"^(?:what|when|where|how|is|are|can|does|do)\b",
    r"\b(?:nearest|closest|quick|just)\b",
    r"\b(?:one\s+line|single\s+line)\b",
    r"^(?:hi|hello|hey|thanks|thank\s+you)\b",
)


def classify_intent(
    text: str,
    *,
    interactive_agent_id: str = _INTERACTIVE_ID,
    autonomous_agent_id: str = _AUTONOMOUS_ID,
    has_image: bool = False,
) -> RouteDecision:
    """Classify user input and pick interactive vs autonomous agent path."""
    cleaned = text.strip()
    lower = cleaned.lower()

    if has_image:
        return RouteDecision(
            AgentRoute.INTERACTIVE,
            interactive_agent_id,
            "multimodal image input → interactive Nemotron path",
            prefetch_briefing=False,
        )

    for pattern in _DIGEST_PATTERNS:
        if re.search(pattern, lower):
            return RouteDecision(
                AgentRoute.DIGEST,
                interactive_agent_id,
                "morning digest / plan request",
                prefetch_briefing=True,
            )

    for pattern in _AUTONOMOUS_PATTERNS:
        if re.search(pattern, lower):
            return RouteDecision(
                AgentRoute.AUTONOMOUS,
                autonomous_agent_id,
                "deep monitor / multi-domain London ops query",
                prefetch_briefing=True,
            )

    if len(cleaned) > 240:
        return RouteDecision(
            AgentRoute.AUTONOMOUS,
            autonomous_agent_id,
            "long-form query → autonomous analysis",
            prefetch_briefing=True,
        )

    for pattern in _QUICK_QA_PATTERNS:
        if re.search(pattern, lower):
            return RouteDecision(
                AgentRoute.INTERACTIVE,
                interactive_agent_id,
                "quick Q&A → interactive chat",
                prefetch_briefing=False,
            )

    return RouteDecision(
        AgentRoute.INTERACTIVE,
        interactive_agent_id,
        "default interactive path",
        prefetch_briefing=False,
    )


ROUTING_RULES_DOC = """# Agent routing rules

| Intent | Route | Agent ID | Prefetch briefing |
|--------|-------|----------|-------------------|
| Quick Q&A, voice, image | interactive | disruptron | no |
| Morning plan / digest | digest | disruptron | yes |
| Monitor, investigate, equity, "how's London" | autonomous | disruptron | yes |
| Long message (>240 chars) | autonomous | disruptron | yes |

Implemented in `disruptron_api/backend/router.py`. Web UI shows active mode via SSE `mode` events.
"""
