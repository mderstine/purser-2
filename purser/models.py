"""Data models for Purser."""

from __future__ import annotations

from datetime import datetime  # noqa: TC003
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

# --- Beads entities ---


class Dependency(BaseModel):
    type: str  # blocks, discovered-from, relates-to, parent-child
    target_id: str


class Issue(BaseModel):
    id: str
    title: str
    type: str = "task"  # bug, feature, task, epic, chore
    status: str = "open"  # open, in_progress, closed
    priority: int = 2
    description: str | None = None
    assignee: str | None = None
    labels: list[str] = Field(default_factory=list)
    parent: str | None = None
    dependencies: list[Dependency] = Field(default_factory=list)
    notes: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = {"extra": "ignore"}


class MolStep(BaseModel):
    id: str
    title: str
    status: str = "open"
    needs: list[str] = Field(default_factory=list)

    model_config = {"extra": "ignore"}


class Molecule(BaseModel):
    id: str
    formula: str
    steps: list[MolStep] = Field(default_factory=list)
    vars: dict[str, str] = Field(default_factory=dict)
    status: str = "open"

    model_config = {"extra": "ignore"}


class MolProgress(BaseModel):
    total: int = 0
    completed: int = 0
    in_progress: int = 0
    ready: int = 0
    blocked: int = 0

    model_config = {"extra": "ignore"}


# --- Purser entities ---


class Spec(BaseModel):
    id: str
    title: str
    source_file: str | None = None
    content: str = ""
    created_at: datetime | None = None
    issue_id: str | None = None


class PlanTask(BaseModel):
    title: str
    issue_id: str = ""
    description: str = ""
    depends_on: list[str] = Field(default_factory=list)
    priority: int = 2
    labels: list[str] = Field(default_factory=list)


class PlanFeature(BaseModel):
    title: str
    issue_id: str = ""
    description: str = ""
    tasks: list[PlanTask] = Field(default_factory=list)


class Plan(BaseModel):
    spec_id: str
    epic_id: str = ""
    epic_title: str = ""
    features: list[PlanFeature] = Field(default_factory=list)


# --- LLM protocol ---


class ToolCall(BaseModel):
    id: str
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class Message(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str | None = None
    tool_calls: list[ToolCall] | None = None
    tool_call_id: str | None = None


class LLMResponse(BaseModel):
    content: str | None = None
    tool_calls: list[ToolCall] = Field(default_factory=list)
    stop_reason: str = "end_turn"


class AdapterConfig(BaseModel):
    provider: str = "openai"
    model: str = "gpt-4o"
    api_key: str | None = None
    base_url: str | None = None
    temperature: float = 0.0
    max_tokens: int = 4096


# --- GitHub integration ---


def _validate_repo_format(v: str) -> str:
    """Validate owner/repo format."""
    if "/" not in v or v.count("/") != 1:
        raise ValueError(f"repo must be in 'owner/repo' format, got: {v!r}")
    owner, repo = v.split("/")
    if not owner or not repo:
        raise ValueError(f"repo must be in 'owner/repo' format, got: {v!r}")
    return v


class GitHubRepoConfig(BaseModel):
    """Configuration for a single GitHub repository in multi-repo setups."""

    name: str  # owner/repo format
    labels: list[str] = Field(default_factory=list)

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        return _validate_repo_format(v)


class GitHubConfig(BaseModel):
    """Optional GitHub integration configuration.

    When enabled, purser syncs beads bidirectionally with GitHub Issues
    and GitHub Projects via the gh CLI.
    """

    enabled: bool = False
    repo: str | None = None  # owner/repo format
    project: str | None = None  # GH Project name or number
    sync_on_commit: bool = False
    conflict_strategy: Literal["local-wins", "remote-wins", "prompt"] = "local-wins"
    label_prefix: str = ""
    username_map: dict[str, str] = Field(default_factory=dict)
    repos: list[GitHubRepoConfig] = Field(default_factory=list)

    @field_validator("repo")
    @classmethod
    def validate_repo(cls, v: str | None) -> str | None:
        if v is not None:
            _validate_repo_format(v)
        return v
