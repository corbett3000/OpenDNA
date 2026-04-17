from unittest.mock import MagicMock, patch

import pytest

from opendna.llm import get_provider
from opendna.llm.anthropic import AnthropicProvider
from opendna.models import Finding


def _finding() -> Finding:
    return Finding(
        panel_id="methylation", rsid="rs1801133", gene="MTHFR",
        genotype="CT", tier="warning", note="~30% reduced activity",
        description="Central methylation enzyme",
    )


def test_get_provider_returns_anthropic_for_name() -> None:
    p = get_provider("anthropic", api_key="sk-fake", model="claude-sonnet-4-6")
    assert isinstance(p, AnthropicProvider)


def test_get_provider_raises_on_unknown_name() -> None:
    with pytest.raises(ValueError):
        get_provider("not-a-provider", api_key="x", model="y")


def test_anthropic_provider_calls_sdk_and_returns_prose() -> None:
    mock_client = MagicMock()
    mock_message = MagicMock()
    mock_message.content = [MagicMock(text="Your MTHFR result suggests...")]
    mock_client.messages.create.return_value = mock_message

    with patch("opendna.llm.anthropic.anthropic.Anthropic", return_value=mock_client):
        provider = AnthropicProvider(api_key="sk-fake", model="claude-sonnet-4-6")
        out = provider.interpret([_finding()])

    assert "MTHFR" in out
    call_kwargs = mock_client.messages.create.call_args.kwargs
    assert call_kwargs["model"] == "claude-sonnet-4-6"
    # Prompt caching: system block should be a list with cache_control.
    assert isinstance(call_kwargs["system"], list)
    assert call_kwargs["system"][0]["cache_control"] == {"type": "ephemeral"}


def test_anthropic_provider_redacts_api_key_in_repr() -> None:
    p = AnthropicProvider(api_key="sk-ant-very-secret", model="claude-sonnet-4-6")
    assert "very-secret" not in repr(p)
    assert "sk-ant-" not in repr(p)
