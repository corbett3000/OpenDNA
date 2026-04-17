"""Anthropic Claude provider — default for OpenDNA."""
from __future__ import annotations

import anthropic

from opendna.llm.base import SYSTEM_PROMPT, Provider, findings_to_prompt
from opendna.models import Finding

DEFAULT_MODEL = "claude-sonnet-4-6"


class AnthropicProvider(Provider):
    def interpret(self, findings: list[Finding]) -> str:
        client = anthropic.Anthropic(api_key=self._api_key)
        message = client.messages.create(
            model=self.model,
            max_tokens=1024,
            system=[
                {
                    "type": "text",
                    "text": SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[
                {
                    "role": "user",
                    "content": (
                        "Synthesize these findings into a clinician-readable "
                        "summary:\n\n" + findings_to_prompt(findings)
                    ),
                }
            ],
        )
        return "".join(b.text for b in message.content if hasattr(b, "text"))
