"""Ollama provider for local LLM inference."""
from __future__ import annotations

import httpx

from opendna.llm.base import (
    REPORT_QA_SYSTEM_PROMPT,
    SYSTEM_PROMPT,
    Provider,
    findings_to_prompt,
    report_chat_messages,
)
from opendna.models import AnalysisSummary, ChatTurn, Finding, SourceFileInfo

DEFAULT_MODEL = "llama3.2"
DEFAULT_BASE_URL = "http://127.0.0.1:11434"


class OllamaProvider(Provider):
    """Provider backed by a local Ollama server."""

    def __init__(self, api_key: str = "", model: str = DEFAULT_MODEL) -> None:
        super().__init__(api_key=api_key, model=model or DEFAULT_MODEL)

    def _chat(self, messages: list[dict[str, str]], system_prompt: str) -> str:
        payload = {
            "model": self.model,
            "stream": False,
            "messages": [
                {"role": "system", "content": system_prompt},
                *messages,
            ],
        }
        try:
            with httpx.Client(timeout=120.0) as client:
                resp = client.post(f"{DEFAULT_BASE_URL}/api/chat", json=payload)
                resp.raise_for_status()
        except httpx.ConnectError as exc:
            raise RuntimeError(
                "Ollama is not reachable at http://127.0.0.1:11434. "
                "Start Ollama and pull the selected model first."
            ) from exc

        body = resp.json()
        message = body.get("message", {})
        content = message.get("content", "")
        if not isinstance(content, str):
            raise RuntimeError("Ollama returned an unexpected response shape.")
        return content

    def interpret(self, findings: list[Finding]) -> str:
        return self._chat(
            [
                {
                    "role": "user",
                    "content": (
                        "Synthesize these findings into a clinician-readable "
                        "summary:\n\n" + findings_to_prompt(findings)
                    ),
                }
            ],
            SYSTEM_PROMPT,
        )

    def answer_question(
        self,
        findings: list[Finding],
        question: str,
        analysis_summary: AnalysisSummary | None = None,
        source_file: SourceFileInfo | None = None,
        history: list[ChatTurn] | None = None,
    ) -> str:
        return self._chat(
            report_chat_messages(
                question,
                findings,
                analysis_summary=analysis_summary,
                source_file=source_file,
                history=history,
            ),
            REPORT_QA_SYSTEM_PROMPT,
        )
