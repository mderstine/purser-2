"""Worker agent: claim, execute, and close one bead."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from purser.agents.base import AgentRunner
from purser.protocol import WORKER_TOOLS

if TYPE_CHECKING:
    from purser.adapters.base import LLMAdapter
    from purser.config import PurserConfig
    from purser.memory import MemoryStore

_PROMPTS_DIR = Path(__file__).parent.parent.parent / "prompts" / "worker"


def _load_prompt() -> str:
    """Load the worker execution prompt."""
    path = _PROMPTS_DIR / "execute.md"
    if path.exists():
        return path.read_text()
    return (
        "You are a Worker agent. Use purser_ready to find work, purser_claim "
        "to take an issue, execute the work, and purser_close when done. "
        "If you find unrelated problems, use purser_discover to file them. "
        "Work on exactly ONE bead."
    )


class WorkerAgent:
    """Worker agent that claims and executes one bead at a time."""

    def __init__(
        self,
        adapter: LLMAdapter,
        memory: MemoryStore,
        config: PurserConfig,
    ):
        self.adapter = adapter
        self.memory = memory
        self.config = config

    async def run(self, issue_id: str | None = None) -> str | None:
        """Run the worker agent.

        Args:
            issue_id: Specific issue to work on. If None, picks next ready.
        """
        prompt = _load_prompt()
        runner = AgentRunner(
            adapter=self.adapter,
            tools=WORKER_TOOLS,
            system_prompt=prompt,
            memory=self.memory,
            max_iterations=self.config.max_agent_iterations,
        )

        if issue_id:
            user_msg = f"Please claim and work on this issue: {issue_id}"
        else:
            user_msg = (
                "Please find the next ready bead, claim it, execute the work, "
                "and close it when done. File discoveries for any unrelated "
                "problems you notice."
            )

        return await runner.run(user_msg)
