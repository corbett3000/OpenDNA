from unittest.mock import MagicMock, patch

import httpx

from opendna.llm import get_provider
from opendna.llm.ollama import OllamaProvider
from opendna.models import ChatTurn, Finding


def _finding() -> Finding:
    return Finding(
        panel_id="methylation",
        rsid="rs4680",
        gene="COMT",
        genotype="AG",
        tier="warning",
        note="Intermediate COMT activity",
        description="Catechol-O-methyltransferase",
    )


def _mock_client(content: str) -> MagicMock:
    response = httpx.Response(
        200,
        json={"message": {"role": "assistant", "content": content}},
        request=httpx.Request("POST", "http://127.0.0.1:11434/api/chat"),
    )
    client = MagicMock()
    client.post.return_value = response
    context = MagicMock()
    context.__enter__.return_value = client
    context.__exit__.return_value = None
    return context


def test_get_provider_returns_ollama_without_api_key() -> None:
    provider = get_provider("ollama", model="llama3.2")
    assert isinstance(provider, OllamaProvider)
    assert provider.model == "llama3.2"


def test_ollama_provider_calls_local_chat_api_for_synthesis() -> None:
    mock_context = _mock_client("COMT summary from local model.")

    with patch("opendna.llm.ollama.httpx.Client", return_value=mock_context):
        provider = OllamaProvider(model="llama3.2")
        out = provider.interpret([_finding()])

    assert "COMT" in out
    call_kwargs = mock_context.__enter__.return_value.post.call_args.kwargs
    assert call_kwargs["json"]["model"] == "llama3.2"
    assert call_kwargs["json"]["stream"] is False
    assert call_kwargs["json"]["messages"][0]["role"] == "system"
    assert "rs4680" in call_kwargs["json"]["messages"][1]["content"]


def test_ollama_provider_can_answer_report_question() -> None:
    mock_context = _mock_client("This report includes COMT rs4680.")

    with patch("opendna.llm.ollama.httpx.Client", return_value=mock_context):
        provider = OllamaProvider(model="llama3.2")
        out = provider.answer_question(
            [_finding()],
            question="Does this report include COMT?",
            history=[ChatTurn(role="user", content="Focus on methylation.")],
        )

    assert "COMT" in out
    messages = mock_context.__enter__.return_value.post.call_args.kwargs["json"]["messages"]
    assert messages[-1]["content"] == "Does this report include COMT?"
    assert "rs4680" in messages[1]["content"]
