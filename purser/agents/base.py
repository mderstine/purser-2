"""Base agent runner: the prompt -> LLM -> tool execution loop."""

from __future__ import annotations

import sys
import uuid
from typing import TYPE_CHECKING

from purser.models import Message
from purser.protocol import dispatch_tool

if TYPE_CHECKING:
    from purser.adapters.base import LLMAdapter
    from purser.memory import MemoryStore


class AgentRunner:
    """Drives the core agent loop: send messages to LLM, execute tool calls, repeat.

    This is agent-agnostic — any LLMAdapter can be plugged in.
    """

    def __init__(
        self,
        adapter: LLMAdapter,
        tools: list[dict],
        system_prompt: str,
        memory: MemoryStore,
        *,
        max_iterations: int = 50,
        session_id: str | None = None,
    ):
        self.adapter = adapter
        self.tools = tools
        self.system_prompt = system_prompt
        self.memory = memory
        self.max_iterations = max_iterations
        self.session_id = session_id or str(uuid.uuid4())[:8]
        self.messages: list[Message] = []

    async def run(self, initial_message: str | None = None) -> str | None:
        """Run the agent loop until completion or max iterations.

        Returns the final assistant message content, if any.
        """
        # Build initial messages
        self.messages = [Message(role="system", content=self.system_prompt)]

        # Inject beads context if available
        try:
            from purser.beads import prime

            context = prime()
            if context:
                self.messages.append(
                    Message(
                        role="system",
                        content=f"Current beads context:\n{context}",
                    )
                )
        except Exception:
            pass

        # Load conversation history from memory
        history = self.memory.get_conversation(self.session_id, limit=20)
        for entry in history:
            self.messages.append(Message(role=entry["role"], content=entry["content"]))  # ty: ignore[invalid-argument-type]

        # Add initial user message
        if initial_message:
            self.messages.append(Message(role="user", content=initial_message))
            self.memory.store_conversation(self.session_id, "user", initial_message)

        last_content = None
        tools_for_llm = self.tools if self.adapter.supports_tools() else None

        for _iteration in range(self.max_iterations):
            response = await self.adapter.complete(self.messages, tools_for_llm)

            # Handle tool calls
            if response.tool_calls:
                # Add assistant message with tool calls
                self.messages.append(
                    Message(
                        role="assistant",
                        content=response.content,
                        tool_calls=response.tool_calls,
                    )
                )

                # Execute each tool call
                for tc in response.tool_calls:
                    _log(f"  [{tc.name}] {_summarize_args(tc.arguments)}")
                    result = dispatch_tool(tc.name, tc.arguments, memory=self.memory)
                    self.messages.append(
                        Message(
                            role="tool",
                            content=result,
                            tool_call_id=tc.id,
                        )
                    )

                continue  # Loop back for more LLM reasoning

            # No tool calls — assistant is done or providing output
            if response.content:
                last_content = response.content
                self.messages.append(Message(role="assistant", content=response.content))
                self.memory.store_conversation(self.session_id, "assistant", response.content)
                _log(f"\n{response.content}\n")

            # Check if the LLM is signaling completion
            if response.stop_reason in ("end_turn", "stop", "stop_sequence"):
                break

        return last_content


def _log(msg: str) -> None:
    """Print to stderr for agent progress."""
    print(msg, file=sys.stderr)


def _summarize_args(args: dict) -> str:
    """Short summary of tool arguments for logging."""
    parts = []
    for k, v in args.items():
        s = str(v)
        if len(s) > 40:
            s = s[:37] + "..."
        parts.append(f"{k}={s}")
    return ", ".join(parts) or "(no args)"
