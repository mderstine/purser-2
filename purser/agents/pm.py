"""Project Manager agent: spec intake and plan decomposition."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from purser.agents.base import AgentRunner
from purser.protocol import PM_TOOLS

if TYPE_CHECKING:
    from purser.adapters.base import LLMAdapter
    from purser.config import PurserConfig
    from purser.memory import MemoryStore

_PROMPTS_DIR = Path(__file__).parent.parent.parent / "prompts" / "pm"


def _load_prompt(name: str) -> str:
    """Load a prompt template from the prompts directory."""
    path = _PROMPTS_DIR / f"{name}.md"
    if path.exists():
        return path.read_text()
    # Fallback to inline prompt
    if name == "intake":
        return (
            "You are a PM agent. Read the raw spec and use purser_spec_intake "
            "to produce a structured markdown specification. Then store key "
            "decisions in memory."
        )
    return (
        "You are a PM agent. Read the spec using purser_spec_show, then use "
        "purser_create and purser_dep_add to decompose it into epics, features, "
        "and tasks with proper dependencies."
    )


class PMAgent:
    """Project Manager agent for spec intake and plan decomposition."""

    def __init__(
        self,
        adapter: LLMAdapter,
        memory: MemoryStore,
        config: PurserConfig,
    ):
        self.adapter = adapter
        self.memory = memory
        self.config = config

    async def run(
        self,
        task: str = "intake",
        input_file: str | None = None,
    ) -> str | None:
        """Run the PM agent for a specific task.

        Args:
            task: "intake" to process a raw spec, "plan" to decompose a spec.
            input_file: Path to raw spec file (for intake task).
        """
        if task == "intake":
            return await self._intake(input_file)
        elif task == "plan":
            return await self._plan(input_file)  # input_file is spec_id here
        else:
            raise ValueError(f"Unknown PM task: {task}. Use 'intake' or 'plan'.")

    async def _intake(self, input_file: str | None) -> str | None:
        """Run spec intake."""
        prompt = _load_prompt("intake")
        runner = AgentRunner(
            adapter=self.adapter,
            tools=PM_TOOLS,
            system_prompt=prompt,
            memory=self.memory,
            max_iterations=self.config.max_agent_iterations,
        )

        if input_file:
            user_msg = f"Please intake and structure this spec file: {input_file}"
        else:
            user_msg = (
                "Please check for any raw specs that need to be structured. "
                "Look in the current directory for .txt or .md files."
            )

        return await runner.run(user_msg)

    async def _plan(self, spec_id: str | None) -> str | None:
        """Run plan decomposition."""
        prompt = _load_prompt("plan")
        runner = AgentRunner(
            adapter=self.adapter,
            tools=PM_TOOLS,
            system_prompt=prompt,
            memory=self.memory,
            max_iterations=self.config.max_agent_iterations,
        )

        if spec_id:
            user_msg = f"Please decompose this spec into a plan: {spec_id}"
        else:
            user_msg = (
                "Please check for specs that need to be decomposed into plans. "
                "Use purser_list to find specs without plans."
            )

        return await runner.run(user_msg)
