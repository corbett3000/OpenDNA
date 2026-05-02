from unittest.mock import MagicMock, patch

from opendna.llm.openai import OpenAIProvider
from opendna.models import ChatTurn, Finding


def _finding() -> Finding:
    return Finding(
        panel_id="cardiovascular", rsid="rs10757278", gene="9p21",
        genotype="GG", tier="risk", note="Elevated CAD risk",
        description="Best-characterized CAD-risk locus",
    )


def test_openai_provider_calls_sdk_and_returns_prose() -> None:
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.choices = [MagicMock(message=MagicMock(content="9p21 GG suggests..."))]
    mock_client.chat.completions.create.return_value = mock_resp

    with patch("opendna.llm.openai.openai.OpenAI", return_value=mock_client):
        provider = OpenAIProvider(api_key="sk-fake", model="gpt-4o")
        out = provider.interpret([_finding()])

    assert "9p21" in out
    call_kwargs = mock_client.chat.completions.create.call_args.kwargs
    assert call_kwargs["model"] == "gpt-4o"
    # Newer OpenAI API: use max_completion_tokens, not max_tokens
    assert "max_tokens" not in call_kwargs
    assert call_kwargs["max_completion_tokens"] == 1024


def test_openai_provider_can_answer_report_question() -> None:
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.choices = [MagicMock(message=MagicMock(content="This is a common CAD risk marker."))]
    mock_client.chat.completions.create.return_value = mock_resp

    with patch("opendna.llm.openai.openai.OpenAI", return_value=mock_client):
        provider = OpenAIProvider(api_key="sk-fake", model="gpt-4o")
        out = provider.answer_question(
            [_finding()],
            question="What does this say about 9p21?",
            history=[ChatTurn(role="assistant", content="Earlier summary.")],
        )

    assert "CAD" in out
    call_kwargs = mock_client.chat.completions.create.call_args.kwargs
    assert call_kwargs["messages"][-1]["content"] == "What does this say about 9p21?"
    assert "9p21" in call_kwargs["messages"][1]["content"]
    assert call_kwargs["max_completion_tokens"] == 700
