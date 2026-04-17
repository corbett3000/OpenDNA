"""OpenAI provider — secondary option."""
from __future__ import annotations

import openai

from opendna.llm.base import SYSTEM_PROMPT, Provider, findings_to_prompt
from opendna.models import Finding

DEFAULT_MODEL = "gpt-4o"


class OpenAIProvider(Provider):
    def interpret(self, findings: list[Finding]) -> str:
        client = openai.OpenAI(api_key=self._api_key)
        resp = client.chat.completions.create(
            model=self.model,
            max_completion_tokens=1024,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        "Synthesize these findings into a clinician-readable "
                        "summary:\n\n" + findings_to_prompt(findings)
                    ),
                },
            ],
        )
        return resp.choices[0].message.content or ""
