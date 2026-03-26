"""OpenAI-compatible adapter.

Works with OpenAI, Azure OpenAI, Codex, Gemini (via OpenAI-compatible API),
Ollama Cloud, and any other provider exposing the OpenAI chat completions API.
"""

from __future__ import annotations

import os

import httpx

from purser.adapters import register
from purser.adapters.base import LLMAdapter
from purser.models import AdapterConfig, LLMResponse, Message, ToolCall

_DEFAULT_URLS = {
    "openai": "https://api.openai.com/v1",
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai",
    "codex": "https://api.openai.com/v1",
    "ollama-cloud": "https://ollama.com/v1",
}

# Provider -> env var for API key lookup
_API_KEY_ENV = {
    "openai": "OPENAI_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "codex": "OPENAI_API_KEY",
    "ollama-cloud": "OLLAMA_API_KEY",
}

# Default models per provider (used when config.model is unset or inherited from another provider)
_DEFAULT_MODELS = {
    "openai": "gpt-4o",
    "gemini": "gemini-2.5-pro",
    "codex": "gpt-4o",
    "ollama-cloud": "qwen3-coder:480b-cloud",
}


def _to_openai_messages(messages: list[Message]) -> list[dict]:
    """Convert Message models to OpenAI format."""
    result = []
    for m in messages:
        msg: dict = {"role": m.role, "content": m.content or ""}
        if m.tool_calls:
            msg["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": __import__("json").dumps(tc.arguments),
                    },
                }
                for tc in m.tool_calls
            ]
        if m.tool_call_id:
            msg["tool_call_id"] = m.tool_call_id
        result.append(msg)
    return result


def _to_openai_tools(tools: list[dict]) -> list[dict]:
    """Wrap tool definitions in OpenAI function-calling format."""
    return [
        {
            "type": "function",
            "function": tool,
        }
        for tool in tools
    ]


def _parse_response(data: dict) -> LLMResponse:
    """Parse OpenAI response into LLMResponse."""
    choice = data["choices"][0]
    message = choice["message"]

    tool_calls = []
    if message.get("tool_calls"):
        import json

        for tc in message["tool_calls"]:
            tool_calls.append(
                ToolCall(
                    id=tc["id"],
                    name=tc["function"]["name"],
                    arguments=json.loads(tc["function"].get("arguments", "{}")),
                )
            )

    return LLMResponse(
        content=message.get("content"),
        tool_calls=tool_calls,
        stop_reason=choice.get("finish_reason", "stop"),
    )


@register("openai")
@register("gemini")
@register("codex")
@register("ollama-cloud")
class OpenAICompatAdapter(LLMAdapter):
    """Adapter for any OpenAI-compatible chat completions API.

    Supports: OpenAI, Gemini, Codex, Ollama Cloud, and any custom
    OpenAI-compatible endpoint via base_url override.
    """

    def __init__(self, config: AdapterConfig):
        super().__init__(config)
        provider = config.provider.lower()
        self.base_url = config.base_url or _DEFAULT_URLS.get(provider, _DEFAULT_URLS["openai"])
        env_var = _API_KEY_ENV.get(provider, "OPENAI_API_KEY")
        self.api_key = config.api_key or os.environ.get(env_var, "")

        # Apply provider-specific default model if current model doesn't match provider
        default_model = _DEFAULT_MODELS.get(provider)
        if default_model and (
            not config.model or (config.model == "gpt-4o" and provider != "openai")
        ):
            self.config.model = default_model

    async def complete(
        self,
        messages: list[Message],
        tools: list[dict] | None = None,
    ) -> LLMResponse:
        payload: dict = {
            "model": self.config.model,
            "messages": _to_openai_messages(messages),
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
        }
        if tools:
            payload["tools"] = _to_openai_tools(tools)

        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            resp.raise_for_status()
            return _parse_response(resp.json())
