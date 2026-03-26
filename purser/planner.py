"""Plan decomposition: spec -> epics/features/tasks with dependencies."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from purser.models import Plan, PlanFeature, PlanTask
from purser.spec import show_spec

if TYPE_CHECKING:
    from purser.adapters.base import LLMAdapter
    from purser.config import PurserConfig

PLAN_SYSTEM_PROMPT = """\
You are a project manager agent. Your task is to decompose a specification \
into a hierarchy of implementable work items.

Given a spec, produce a JSON object with this structure:
{
  "epic_title": "Short epic title",
  "epic_description": "One-paragraph epic description",
  "features": [
    {
      "title": "Feature title",
      "description": "Feature description",
      "tasks": [
        {
          "title": "Task title",
          "description": "What to implement",
          "depends_on": ["other-task-slug"],
          "priority": 2,
          "labels": ["backend"]
        }
      ]
    }
  ]
}

Guidelines:
- Tasks should be 30-120 minutes of focused work
- Use depends_on to reference task slugs within the SAME feature (kebab-case of title)
- Cross-feature dependencies: prefix with feature slug (e.g., "auth/create-user-model")
- Priority: 0=critical, 1=high, 2=medium, 3=low, 4=backlog
- Labels: use domain tags like "backend", "frontend", "infra", "docs", "test"
- Every feature should have at least one task
- Map dependencies carefully: a task should only depend on tasks that MUST complete first

Respond with ONLY the JSON object, no markdown fencing or explanation."""


class PlanBlueprint:
    """Parsed plan before beads creation."""

    def __init__(self, data: dict):
        self.epic_title: str = data["epic_title"]
        self.epic_description: str = data.get("epic_description", "")
        self.features: list[dict] = data.get("features", [])

    def validate_dag(self) -> list[str]:
        """Check for dependency issues. Returns list of warnings."""
        warnings = []
        all_slugs: set[str] = set()

        for feat in self.features:
            feat_slug = _slugify(feat["title"])
            for task in feat.get("tasks", []):
                task_slug = _slugify(task["title"])
                full_slug = f"{feat_slug}/{task_slug}"
                all_slugs.add(task_slug)
                all_slugs.add(full_slug)

        for feat in self.features:
            feat_slug = _slugify(feat["title"])
            for task in feat.get("tasks", []):
                for dep in task.get("depends_on", []):
                    if dep not in all_slugs:
                        warnings.append(f"Task '{task['title']}' depends on unknown '{dep}'")
        return warnings


def _slugify(text: str) -> str:
    import re

    slug = re.sub(r"[^\w\s-]", "", text.lower())
    slug = re.sub(r"[\s_]+", "-", slug)
    return slug.strip("-")[:60]


def create_plan(
    spec_id: str,
    *,
    adapter: LLMAdapter | None = None,
    config: PurserConfig | None = None,
) -> Plan:
    """Decompose a spec into a plan with beads issues."""
    from purser.config import load_config

    if config is None:
        config = load_config()

    spec = show_spec(spec_id, config.specs_dir)

    if adapter:
        blueprint = _decompose_with_llm(spec.content, adapter)
    else:
        # Without an LLM, create a minimal single-feature plan
        blueprint = PlanBlueprint(
            {
                "epic_title": spec.title,
                "epic_description": f"Implementation of {spec.title}",
                "features": [
                    {
                        "title": spec.title,
                        "description": "Implement the specification",
                        "tasks": [
                            {
                                "title": f"Implement {spec.title}",
                                "description": spec.content[:500],
                                "depends_on": [],
                                "priority": 2,
                                "labels": [],
                            }
                        ],
                    }
                ],
            }
        )

    warnings = blueprint.validate_dag()
    if warnings:
        import click

        for w in warnings:
            click.echo(f"Warning: {w}", err=True)

    return _create_beads(blueprint, spec_id)


def _decompose_with_llm(spec_content: str, adapter: LLMAdapter) -> PlanBlueprint:
    """Use LLM to decompose a spec into a plan blueprint."""
    import asyncio

    from purser.models import Message

    messages = [
        Message(role="system", content=PLAN_SYSTEM_PROMPT),
        Message(role="user", content=spec_content),
    ]
    response = asyncio.run(adapter.complete(messages))
    text = response.content or "{}"

    # Strip markdown code fencing if present
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])

    data = json.loads(text)
    return PlanBlueprint(data)


def _create_beads(blueprint: PlanBlueprint, spec_id: str) -> Plan:
    """Create bd issues from a plan blueprint.

    Attempts to use bd CLI. Falls back to returning the plan without
    issue IDs if bd is not available.
    """
    plan = Plan(
        spec_id=spec_id,
        epic_title=blueprint.epic_title,
    )

    try:
        from purser.beads import add_dependency, create_issue

        # Create epic
        epic = create_issue(
            blueprint.epic_title,
            type="epic",
            description=blueprint.epic_description,
            labels=["spec:" + spec_id],
        )
        plan.epic_id = epic.id

        # Track slug -> issue ID for dependency wiring
        slug_to_id: dict[str, str] = {}

        for feat_data in blueprint.features:
            feat_slug = _slugify(feat_data["title"])

            # Create feature issue as child of epic
            feat_issue = create_issue(
                feat_data["title"],
                type="feature",
                description=feat_data.get("description", ""),
                parent=epic.id,
            )

            feature = PlanFeature(
                title=feat_data["title"],
                issue_id=feat_issue.id,
                description=feat_data.get("description", ""),
            )

            for task_data in feat_data.get("tasks", []):
                task_slug = _slugify(task_data["title"])
                full_slug = f"{feat_slug}/{task_slug}"

                task_issue = create_issue(
                    task_data["title"],
                    type="task",
                    description=task_data.get("description", ""),
                    priority=task_data.get("priority", 2),
                    parent=feat_issue.id,
                    labels=task_data.get("labels", []),
                )

                slug_to_id[task_slug] = task_issue.id
                slug_to_id[full_slug] = task_issue.id

                feature.tasks.append(
                    PlanTask(
                        title=task_data["title"],
                        issue_id=task_issue.id,
                        description=task_data.get("description", ""),
                        depends_on=task_data.get("depends_on", []),
                        priority=task_data.get("priority", 2),
                        labels=task_data.get("labels", []),
                    )
                )

            plan.features.append(feature)

        # Wire dependencies (second pass after all issues exist)
        for feature in plan.features:
            for task in feature.tasks:
                for dep_slug in task.depends_on:
                    dep_id = slug_to_id.get(dep_slug)
                    if dep_id and task.issue_id:
                        add_dependency(dep_id, task.issue_id, dep_type="blocks")

    except FileNotFoundError:
        # bd not available, return plan without issue IDs
        for feat_data in blueprint.features:
            feature = PlanFeature(
                title=feat_data["title"],
                description=feat_data.get("description", ""),
            )
            for task_data in feat_data.get("tasks", []):
                feature.tasks.append(
                    PlanTask(
                        title=task_data["title"],
                        description=task_data.get("description", ""),
                        depends_on=task_data.get("depends_on", []),
                        priority=task_data.get("priority", 2),
                        labels=task_data.get("labels", []),
                    )
                )
            plan.features.append(feature)

    return plan
