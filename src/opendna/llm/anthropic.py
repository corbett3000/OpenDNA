"""Anthropic Claude provider — default for OpenDNA."""
from __future__ import annotations

import anthropic

from opendna.llm.base import (
    REPORT_QA_SYSTEM_PROMPT,
    SYSTEM_PROMPT,
    Provider,
    findings_to_prompt,
    report_chat_messages,
)
from opendna.models import AnalysisSummary, ChatTurn, Finding, SourceFileInfo

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

    def answer_question(
        self,
        findings: list[Finding],
        question: str,
        analysis_summary: AnalysisSummary | None = None,
        source_file: SourceFileInfo | None = None,
        history: list[ChatTurn] | None = None,
    ) -> str:
        client = anthropic.Anthropic(api_key=self._api_key)
        message = client.messages.create(
            model=self.model,
            max_tokens=700,
            system=[
                {
                    "type": "text",
                    "text": REPORT_QA_SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=report_chat_messages(
                question,
                findings,
                analysis_summary=analysis_summary,
                source_file=source_file,
                history=history,
            ),
        )
        return "".join(b.text for b in message.content if hasattr(b, "text"))
