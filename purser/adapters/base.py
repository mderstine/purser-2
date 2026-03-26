"""Abstract base class for LLM adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from purser.models import AdapterConfig, LLMResponse, Message


class LLMAdapter(ABC):
    """Thin adapter interface for LLM providers.

    Each adapter implements a single complete() method that takes messages
    and optionally tool definitions, and returns a response. This is the
    only abstraction needed for agent-agnostic design.
    """

    def __init__(self, config: AdapterConfig):
        self.config = config

    @abstractmethod
    async def complete(
        self,
        messages: list[Message],
        tools: list[dict] | None = None,
    ) -> LLMResponse:
        """Send messages to the LLM and return a response.

        Args:
            messages: Conversation messages (system, user, assistant, tool).
            tools: Optional tool definitions in OpenAI function-calling format.

        Returns:
            LLMResponse with content and/or tool_calls.
        """
        ...

    @property
    def name(self) -> str:
        """Human-readable adapter name."""
        return f"{self.config.provider}:{self.config.model}"

    def supports_tools(self) -> bool:
        """Whether this adapter supports function/tool calling."""
        return True
