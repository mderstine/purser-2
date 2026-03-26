"""Ollama adapter for local models."""

from __future__ import annotations

import json
from typing import Any

import httpx

from purser.adapters import register
from purser.adapters.base import LLMAdapter
from purser.models import AdapterConfig, LLMResponse, Message, ToolCall


@register("ollama")
class OllamaAdapter(LLMAdapter):
    """Adapter for Ollama's local REST API."""

    def __init__(self, config: AdapterConfig):
        super().__init__(config)
        self.base_url = config.base_url or "http://localhost:11434"
        if not config.model or config.model.startswith("gpt"):
            self.config.model = "llama3.1"

    def supports_tools(self) -> bool:
        """Tool support depends on the model. Most recent models support it."""
        return True

    async def complete(
        self,
        messages: list[Message],
        tools: list[dict] | None = None,
    ) -> LLMResponse:
        # Convert messages to Ollama format
        ollama_messages = []
        for m in messages:
            msg: dict[str, Any] = {"role": m.role, "content": m.content or ""}
            if m.tool_calls:
                msg["tool_calls"] = [
                    {
                        "function": {
                            "name": tc.name,
                            "arguments": tc.arguments,
                        }
                    }
                    for tc in m.tool_calls
                ]
            ollama_messages.append(msg)

        payload: dict = {
            "model": self.config.model,
            "messages": ollama_messages,
            "stream": False,
            "options": {
                "temperature": self.config.temperature,
                "num_predict": self.config.max_tokens,
            },
        }

        # Convert tools to Ollama format (OpenAI-compatible)
        if tools:
            payload["tools"] = [
                {
                    "type": "function",
                    "function": tool,
                }
                for tool in tools
            ]

        async with httpx.AsyncClient(timeout=300) as client:
            resp = await client.post(
                f"{self.base_url}/api/chat",
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()

        message = data.get("message", {})
        tool_calls = []
        if message.get("tool_calls"):
            for tc in message["tool_calls"]:
                func = tc.get("function", {})
                args = func.get("arguments", {})
                if isinstance(args, str):
                    args = json.loads(args)
                tool_calls.append(
                    ToolCall(
                        id=f"call_{hash(func.get('name', ''))!s}",
                        name=func.get("name", ""),
                        arguments=args,
                    )
                )

        return LLMResponse(
            content=message.get("content"),
            tool_calls=tool_calls,
            stop_reason=data.get("done_reason", "stop"),
        )
