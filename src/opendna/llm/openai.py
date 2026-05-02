"""OpenAI provider — secondary option."""
from __future__ import annotations

import openai

from opendna.llm.base import (
    REPORT_QA_SYSTEM_PROMPT,
    SYSTEM_PROMPT,
    Provider,
    findings_to_prompt,
    report_chat_messages,
)
from opendna.models import AnalysisSummary, ChatTurn, Finding, SourceFileInfo

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

    def answer_question(
        self,
        findings: list[Finding],
        question: str,
        analysis_summary: AnalysisSummary | None = None,
        source_file: SourceFileInfo | None = None,
        history: list[ChatTurn] | None = None,
    ) -> str:
        client = openai.OpenAI(api_key=self._api_key)
        resp = client.chat.completions.create(
            model=self.model,
            max_completion_tokens=700,
            messages=[
                {"role": "system", "content": REPORT_QA_SYSTEM_PROMPT},
                *report_chat_messages(
                    question,
                    findings,
                    analysis_summary=analysis_summary,
                    source_file=source_file,
                    history=history,
                ),
            ],
        )
        return resp.choices[0].message.content or ""
