"""LLM adapter registry."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from purser.adapters.base import LLMAdapter
    from purser.models import AdapterConfig

_ADAPTERS: dict[str, type[LLMAdapter]] = {}


def register(name: str):
    """Decorator to register an adapter class."""

    def decorator(cls):
        _ADAPTERS[name] = cls
        return cls

    return decorator


def get_adapter(config: AdapterConfig) -> LLMAdapter:
    """Instantiate an adapter from config."""
    # Lazy import to avoid loading all adapters upfront
    from purser.adapters import claude, ollama, openai_compat  # noqa: F401

    provider = config.provider.lower()
    if provider not in _ADAPTERS:
        available = ", ".join(sorted(_ADAPTERS.keys()))
        raise ValueError(f"Unknown adapter provider '{provider}'. Available: {available}")
    return _ADAPTERS[provider](config)
