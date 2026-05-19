"""LLM provider factory."""
from __future__ import annotations

from opendna.llm.anthropic import AnthropicProvider
from opendna.llm.base import Provider
from opendna.llm.ollama import OllamaProvider
from opendna.llm.openai import OpenAIProvider


def get_provider(name: str, api_key: str = "", model: str = "") -> Provider:
    name = name.lower().strip()
    if name == "anthropic":
        return AnthropicProvider(api_key=api_key, model=model)
    if name == "openai":
        return OpenAIProvider(api_key=api_key, model=model)
    if name == "ollama":
        return OllamaProvider(api_key="", model=model)
    raise ValueError(f"Unknown provider: {name!r} (known: anthropic, openai, ollama)")


__all__ = ["Provider", "AnthropicProvider", "OpenAIProvider", "OllamaProvider", "get_provider"]
