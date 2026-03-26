"""Anthropic Claude adapter."""

from __future__ import annotations

import os
from typing import Any

from purser.adapters import register
from purser.adapters.base import LLMAdapter
from purser.models import AdapterConfig, LLMResponse, Message, ToolCall


def _to_anthropic_messages(messages: list[Message]) -> tuple[str, list[dict]]:
    """Convert Messages to Anthropic format, extracting system separately."""
    system = ""
    api_messages = []

    for m in messages:
        if m.role == "system":
            system = m.content or ""
            continue

        if m.role == "tool":
            api_messages.append(
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": m.tool_call_id or "",
                            "content": m.content or "",
                        }
                    ],
                }
            )
            continue

        msg: dict[str, Any] = {"role": m.role}
        if m.tool_calls:
            content = []
            if m.content:
                content.append({"type": "text", "text": m.content})
            for tc in m.tool_calls:
                content.append(
                    {
                        "type": "tool_use",
                        "id": tc.id,
                        "name": tc.name,
                        "input": tc.arguments,
                    }
                )
            msg["content"] = content
        else:
            msg["content"] = m.content or ""

        api_messages.append(msg)

    return system, api_messages


def _to_anthropic_tools(tools: list[dict]) -> list[dict]:
    """Convert OpenAI-format tool defs to Anthropic format."""
    return [
        {
            "name": tool["name"],
            "description": tool.get("description", ""),
            "input_schema": tool.get("parameters", {"type": "object", "properties": {}}),
        }
        for tool in tools
    ]


@register("claude")
@register("anthropic")
class ClaudeAdapter(LLMAdapter):
    """Adapter for Anthropic's Claude API."""

    def __init__(self, config: AdapterConfig):
        super().__init__(config)
        self.api_key = config.api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        if not config.model or config.model.startswith("gpt"):
            self.config.model = "claude-sonnet-4-20250514"

    async def complete(
        self,
        messages: list[Message],
        tools: list[dict] | None = None,
    ) -> LLMResponse:
        try:
            import anthropic  # ty: ignore[unresolved-import]
        except ImportError as e:
            raise ImportError("anthropic package required. Install: uv add purser[claude]") from e

        client = anthropic.AsyncAnthropic(api_key=self.api_key)
        system, api_messages = _to_anthropic_messages(messages)

        kwargs: dict[str, Any] = {
            "model": self.config.model,
            "max_tokens": self.config.max_tokens,
            "messages": api_messages,
        }
        if system:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = _to_anthropic_tools(tools)
        if self.config.temperature > 0:
            kwargs["temperature"] = self.config.temperature

        response = await client.messages.create(**kwargs)

        # Parse response
        content_text = ""
        tool_calls = []
        for block in response.content:
            if block.type == "text":
                content_text += block.text
            elif block.type == "tool_use":
                tool_calls.append(
                    ToolCall(
                        id=block.id,
                        name=block.name,
                        arguments=block.input if isinstance(block.input, dict) else {},
                    )
                )

        return LLMResponse(
            content=content_text or None,
            tool_calls=tool_calls,
            stop_reason=response.stop_reason or "end_turn",
        )
