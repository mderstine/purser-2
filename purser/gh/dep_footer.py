"""Render and parse dependency sections in GitHub issue bodies.

Dependencies are stored as a structured section at the end of
the issue body, delimited by HTML comments for machine parsing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Markers for the dependency section in issue body
SECTION_START = "<!-- purser:deps -->"
SECTION_END = "<!-- /purser:deps -->"


@dataclass
class DepFooter:
    """Parsed dependency footer data."""

    parent: int | None = None
    blocks: list[int] = field(default_factory=list)
    blocked_by: list[int] = field(default_factory=list)
    related: list[int] = field(default_factory=list)
    discovered_from: list[int] = field(default_factory=list)


def render_dep_footer(deps: DepFooter) -> str:
    """Render a dependency footer section for a GH issue body.

    Returns empty string if no dependencies.
    """
    lines: list[str] = []

    if deps.parent is not None:
        lines.append(f"**Parent:** #{deps.parent}")
    if deps.blocks:
        refs = ", ".join(f"#{n}" for n in sorted(deps.blocks))
        lines.append(f"**Blocks:** {refs}")
    if deps.blocked_by:
        refs = ", ".join(f"#{n}" for n in sorted(deps.blocked_by))
        lines.append(f"**Blocked by:** {refs}")
    if deps.related:
        refs = ", ".join(f"#{n}" for n in sorted(deps.related))
        lines.append(f"**Related:** {refs}")
    if deps.discovered_from:
        refs = ", ".join(f"#{n}" for n in sorted(deps.discovered_from))
        lines.append(f"**Discovered from:** {refs}")

    if not lines:
        return ""

    return f"\n\n{SECTION_START}\n---\n" + "\n".join(lines) + f"\n{SECTION_END}"


def parse_dep_footer(body: str) -> DepFooter:
    """Parse dependency footer from a GH issue body.

    Returns DepFooter with parsed values. If no footer section found,
    returns an empty DepFooter.
    """
    footer = DepFooter()

    # Extract the section between markers
    match = re.search(
        re.escape(SECTION_START) + r"(.*?)" + re.escape(SECTION_END),
        body,
        re.DOTALL,
    )
    if not match:
        return footer

    section = match.group(1)

    # Parse each line
    parent_match = re.search(r"\*\*Parent:\*\*\s*#(\d+)", section)
    if parent_match:
        footer.parent = int(parent_match.group(1))

    footer.blocks = _extract_refs(section, "Blocks")
    footer.blocked_by = _extract_refs(section, "Blocked by")
    footer.related = _extract_refs(section, "Related")
    footer.discovered_from = _extract_refs(section, "Discovered from")

    return footer


def strip_dep_footer(body: str) -> str:
    """Remove the dependency footer section from a body string."""
    pattern = re.escape(SECTION_START) + r".*?" + re.escape(SECTION_END)
    return re.sub(pattern, "", body, flags=re.DOTALL).rstrip()


def _extract_refs(text: str, label: str) -> list[int]:
    """Extract issue number refs from a line like '**Label:** #1, #2, #3'."""
    match = re.search(rf"\*\*{re.escape(label)}:\*\*\s*(.*?)$", text, re.MULTILINE)
    if not match:
        return []
    refs = re.findall(r"#(\d+)", match.group(1))
    return [int(r) for r in refs]
