"""Hierarchy mapping for GitHub integration.

Maps purser's 5-level bead hierarchy to GitHub constructs:
- Objective -> GitHub Project (Board)
- Epic -> GitHub Milestone + epic: label
- Feature -> GitHub Issue (type:feature)
- Task -> GitHub Issue (type:task)
- Sub-task -> GitHub Task List (within parent issue body)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from purser.gh.dep_footer import DepFooter, render_dep_footer
from purser.gh.hierarchy import build_subtask_list, ensure_type_labels
from purser.gh.labels import prefixed_label
from purser.gh.metadata import get_gh_issue_number

if TYPE_CHECKING:
    from purser.models import GitHubConfig, Issue


class GitHubMapping:
    """Maps purser beads to GitHub constructs.

    This class provides methods to:
    - Map bead types to GitHub constructs (project, milestone, issue, task list)
    - Generate appropriate GitHub labels for beads
    - Format issue bodies with dependencies, parent links, and sub-tasks
    """

    def __init__(self, config: GitHubConfig) -> None:
        """Initialize with GitHub configuration.

        Args:
            config: The GitHub configuration including repo, label prefix, etc.
        """
        self.config = config

    @property
    def label_prefix(self) -> str:
        """Return the configured label prefix (or empty string)."""
        return self.config.label_prefix

    def ensure_labels(self, repo: str) -> None:
        """Ensure all standard labels exist on the repository.

        Creates type:* and priority:* labels if they don't exist.

        Args:
            repo: The repository in owner/repo format.
        """
        ensure_type_labels(repo, self.label_prefix)

    def bead_to_github_level(self, bead_type: str) -> dict[str, Any]:
        """Map a bead type to its GitHub construct representation.

        Args:
            bead_type: The bead type (objective, epic, feature, task, sub-task).

        Returns:
            A dictionary describing the GitHub construct:
            - objective: {"construct": "project", "gh_type": None}
            - epic: {"construct": "milestone", "gh_type": "epic"}
            - feature: {"construct": "issue", "gh_type": "feature"}
            - task: {"construct": "issue", "gh_type": "task"}
            - sub-task: {"construct": "task_list", "gh_type": None}
        """
        mapping: dict[str, dict[str, Any]] = {
            "objective": {"construct": "project", "gh_type": None},
            "epic": {"construct": "milestone", "gh_type": "epic"},
            "feature": {"construct": "issue", "gh_type": "feature"},
            "task": {"construct": "issue", "gh_type": "task"},
            "sub-task": {"construct": "task_list", "gh_type": None},
            # Aliases for common variations
            "story": {"construct": "issue", "gh_type": "feature"},
            "bug": {"construct": "issue", "gh_type": "bug"},
            "chore": {"construct": "issue", "gh_type": "chore"},
        }
        return mapping.get(bead_type.lower(), {"construct": "issue", "gh_type": "task"})

    def get_github_labels(self, bead: Issue) -> list[str]:
        """Generate GitHub labels for a bead.

        Args:
            bead: The bead/issue to generate labels for.

        Returns:
            A list of label names to apply to the GitHub issue.
        """
        labels: list[str] = []

        # Add type label (e.g., type:task, type:feature)
        bead_type = bead.type.lower()
        type_label = self._type_to_label(bead_type)
        if type_label:
            labels.append(prefixed_label(self.label_prefix, type_label))

        # Add priority label if priority is set
        if bead.priority is not None:
            priority_label = self._priority_to_label(bead.priority)
            if priority_label:
                labels.append(prefixed_label(self.label_prefix, priority_label))

        # Add epic label for epics
        if bead_type == "epic":
            # Generate epic label from title (e.g., "Launch v2.0" -> epic:launch-v2-0)
            epic_slug = self._slugify(bead.title.removeprefix("Epic: ").strip())
            labels.append(prefixed_label(self.label_prefix, f"epic:{epic_slug}"))

        # Add user-defined labels with prefix
        for label in bead.labels:
            labels.append(prefixed_label(self.label_prefix, label))

        return labels

    def format_issue_body(
        self,
        bead: Issue,
        subtasks: list[Issue] | None = None,
        deps: DepFooter | None = None,
    ) -> str:
        """Format a bead as a GitHub issue body.

        Args:
            bead: The bead to format.
            subtasks: Optional list of child/sub-task beads to render as task list.
            deps: Optional dependency footer data to include.

        Returns:
            A markdown-formatted string suitable for a GitHub issue body.
        """
        lines: list[str] = []

        # Main description
        if bead.description:
            lines.append(bead.description)
            lines.append("")

        # Notes section
        if bead.notes:
            lines.append("## Notes")
            lines.append(bead.notes)
            lines.append("")

        # Sub-tasks as task list
        if subtasks:
            lines.append("## Sub-tasks")
            lines.append(build_subtask_list(subtasks))
            lines.append("")

        # Metadata section
        meta_lines = self._format_metadata_section(bead)
        if meta_lines:
            lines.extend(meta_lines)
            lines.append("")

        # Join the main body
        body = "\n".join(lines).strip()

        # Add dependency footer if provided
        if deps:
            body += render_dep_footer(deps)

        return body

    def _type_to_label(self, bead_type: str) -> str | None:
        """Convert bead type to a type:* label.

        Args:
            bead_type: The bead type string.

        Returns:
            The type label (e.g., "type:task") or None if not applicable.
        """
        type_map: dict[str, str] = {
            "task": "type:task",
            "feature": "type:feature",
            "epic": "type:epic",
            "bug": "type:bug",
            "chore": "type:chore",
            "story": "type:feature",
        }
        return type_map.get(bead_type.lower())

    def _priority_to_label(self, priority: int) -> str | None:
        """Convert numeric priority to a priority:* label.

        Args:
            priority: Priority level (0=critical, 4=backlog).

        Returns:
            The priority label (e.g., "priority:high") or None.
        """
        priority_map: dict[int, str] = {
            0: "priority:critical",
            1: "priority:high",
            2: "priority:medium",
            3: "priority:low",
            4: "priority:backlog",
        }
        return priority_map.get(priority)

    def _slugify(self, text: str) -> str:
        """Convert text to a URL-friendly slug.

        Args:
            text: The text to slugify.

        Returns:
            A lowercase, hyphenated slug.
        """
        # Replace non-alphanumeric chars with hyphens
        import re

        slug = re.sub(r"[^\w\s-]", "", text.lower())
        slug = re.sub(r"[-\s]+", "-", slug)
        return slug.strip("-")

    def _format_metadata_section(self, bead: Issue) -> list[str]:
        """Format metadata as a markdown section.

        Args:
            bead: The bead to extract metadata from.

        Returns:
            List of markdown lines for the metadata section.
        """
        lines: list[str] = []
        meta_items: list[str] = []

        # Local bead ID reference
        if bead.id:
            meta_items.append(f"**Bead ID:** `{bead.id}`")

        # Status
        if bead.status:
            meta_items.append(f"**Status:** {bead.status}")

        # Priority
        if bead.priority is not None:
            priority_names = {
                0: "Critical",
                1: "High",
                2: "Medium",
                3: "Low",
                4: "Backlog",
            }
            priority_name = priority_names.get(bead.priority, str(bead.priority))
            meta_items.append(f"**Priority:** {priority_name}")

        # Assignee
        if bead.assignee:
            # Map local username to GitHub if configured
            gh_user = self.config.username_map.get(bead.assignee, bead.assignee)
            meta_items.append(f"**Assignee:** @{gh_user}")

        # Owner (from metadata)
        from purser.gh.metadata import get_owner

        owner = get_owner(bead.metadata)
        if owner:
            gh_owner = self.config.username_map.get(owner, owner)
            meta_items.append(f"**Owner:** @{gh_owner}")

        # Due date
        from purser.gh.metadata import get_due_date

        due_date = get_due_date(bead.metadata)
        if due_date:
            meta_items.append(f"**Due:** {due_date.isoformat()}")

        # Estimated effort
        from purser.gh.metadata import get_estimated_effort

        effort = get_estimated_effort(bead.metadata)
        if effort:
            meta_items.append(f"**Estimated Effort:** {effort}")

        # GitHub issue cross-reference (if synced)
        gh_issue = get_gh_issue_number(bead.metadata)
        if gh_issue:
            meta_items.append(f"**GitHub Issue:** #{gh_issue}")

        if meta_items:
            lines.append("## Metadata")
            lines.extend(meta_items)

        return lines

    def is_standalone_issue(self, bead_type: str) -> bool:
        """Check if a bead type maps to a standalone GitHub issue.

        Args:
            bead_type: The bead type to check.

        Returns:
            True if the bead type creates a standalone issue.
        """
        mapping = self.bead_to_github_level(bead_type)
        return mapping["construct"] == "issue"

    def requires_milestone(self, bead_type: str) -> bool:
        """Check if a bead type requires a milestone.

        Args:
            bead_type: The bead type to check.

        Returns:
            True if the bead type maps to a milestone.
        """
        mapping = self.bead_to_github_level(bead_type)
        return mapping["construct"] == "milestone"

    def requires_project(self, bead_type: str) -> bool:
        """Check if a bead type requires a GitHub Project.

        Args:
            bead_type: The bead type to check.

        Returns:
            True if the bead type maps to a project.
        """
        mapping = self.bead_to_github_level(bead_type)
        return mapping["construct"] == "project"
