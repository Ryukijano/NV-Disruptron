"""NeMo Guardrails wrapper for NV-Disruptron agent.

Wraps the agent's ask() method with safety rails:
- Topic control (mobility/London only)
- Jailbreak detection
- PII output filtering (mask email/phone/NHS numbers)

Usage:
    from features.agent.guardrails.wrapper import GuardedAgent
    agent = GuardedAgent(agent_module)
    response = await agent.ask("How do I get to Waterloo?")
"""

import os
from pathlib import Path
from typing import Any

# NeMo Guardrails imports
from nemoguardrails import RailsConfig, LLMRails

RAILS_CONFIG_DIR = Path(__file__).parent


class GuardedAgent:
    """Wraps an agent module with NeMo Guardrails safety checks."""

    def __init__(self, agent_module: Any):
        self.agent = agent_module
        self.config = RailsConfig.from_path(str(RAILS_CONFIG_DIR))
        self.rails = LLMRails(self.config, verbose=False)

    async def ask(self, user_message: str, **kwargs: Any) -> str:
        """Process user message through guardrails before agent."""
        # Run input rails
        input_result = await self.rails.generate_async(
            messages=[{"role": "user", "content": user_message}],
            return_context=True,
        )

        # Check if guardrails blocked the input
        if input_result.get("bot_message"):
            # Guardrails generated a response (e.g., off-topic warning)
            return input_result["bot_message"]

        # Get the sanitized user message
        sanitized = input_result.get("user_message", user_message)

        # Pass to the actual agent
        agent_response = await self.agent.ask(sanitized, **kwargs)

        # Run output rails on agent response
        output_result = await self.rails.generate_async(
            messages=[
                {"role": "user", "content": sanitized},
                {"role": "assistant", "content": agent_response},
            ],
            return_context=True,
        )

        return output_result.get("bot_message", agent_response)

    def ask_sync(self, user_message: str, **kwargs: Any) -> str:
        """Synchronous wrapper for non-async contexts."""
        import asyncio
        return asyncio.get_event_loop().run_until_complete(
            self.ask(user_message, **kwargs)
        )


def get_guarded_agent(agent_module: Any) -> GuardedAgent:
    """Factory: return GuardedAgent wrapping the provided agent module."""
    return GuardedAgent(agent_module)
