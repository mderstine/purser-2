"""Spec intake and management."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from purser.models import Spec

if TYPE_CHECKING:
    from purser.adapters.base import LLMAdapter

# --- Frontmatter parsing (no pyyaml dependency) ---


def _parse_frontmatter(content: str) -> tuple[dict[str, str], str]:
    """Extract YAML-like frontmatter from markdown."""
    if not content.startswith("---"):
        return {}, content

    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}, content

    meta = {}
    for line in parts[1].strip().splitlines():
        if ":" in line:
            key, _, val = line.partition(":")
            meta[key.strip()] = val.strip()

    return meta, parts[2].strip()


def _write_frontmatter(meta: dict[str, str], body: str) -> str:
    """Write frontmatter + body as markdown."""
    lines = ["---"]
    for k, v in meta.items():
        lines.append(f"{k}: {v}")
    lines.append("---")
    lines.append("")
    lines.append(body)
    return "\n".join(lines)


def _slugify(text: str) -> str:
    """Convert text to kebab-case slug."""
    slug = re.sub(r"[^\w\s-]", "", text.lower())
    slug = re.sub(r"[\s_]+", "-", slug)
    return slug.strip("-")[:60]


# --- Spec intake prompt ---

INTAKE_SYSTEM_PROMPT = """\
You are a project manager agent. Your task is to read a raw spec, PRD, or \
feature request and produce a well-structured specification document.

Output a markdown document with these sections:
# {Title}
## Problem Statement
## Goals
## Non-Goals
## User Stories
## Technical Constraints
## Acceptance Criteria
## Open Questions

Be thorough but concise. Preserve the intent of the original document. \
Fill in reasonable details where the original is vague, and note assumptions \
in the Open Questions section.

Respond with ONLY the markdown document, no preamble."""


def intake_spec(
    source: Path,
    *,
    adapter: LLMAdapter | None = None,
    output_dir: Path = Path("specs"),
) -> Spec:
    """Ingest a raw spec file and produce structured markdown.

    If an LLM adapter is provided, the raw text is processed through the LLM
    to produce a well-structured spec. Otherwise, the raw text is used as-is.
    """
    raw_text = source.read_text()

    if adapter:
        import asyncio

        from purser.models import Message

        messages = [
            Message(role="system", content=INTAKE_SYSTEM_PROMPT),
            Message(role="user", content=raw_text),
        ]
        response = asyncio.run(adapter.complete(messages))
        structured = response.content or raw_text
    else:
        structured = raw_text

    # Extract title from first heading or first line
    title_match = re.search(r"^#\s+(.+)$", structured, re.MULTILINE)
    if title_match:
        title = title_match.group(1).strip()
    else:
        first_line = structured.strip().splitlines()[0] if structured.strip() else "Untitled"
        title = first_line[:80]

    slug = _slugify(title)
    spec_id = f"spec-{slug}"
    now = datetime.now(UTC)

    # Write spec file
    output_dir.mkdir(parents=True, exist_ok=True)
    meta = {
        "id": spec_id,
        "title": title,
        "created": now.strftime("%Y-%m-%d"),
        "source": str(source),
    }
    content = _write_frontmatter(meta, structured)

    spec_path = output_dir / f"{slug}.md"
    spec_path.write_text(content)

    return Spec(
        id=spec_id,
        title=title,
        source_file=str(source),
        content=content,
        created_at=now,
    )


def list_specs(specs_dir: Path = Path("specs")) -> list[Spec]:
    """List all specs in the specs directory."""
    if not specs_dir.exists():
        return []

    specs = []
    for path in sorted(specs_dir.glob("*.md")):
        content = path.read_text()
        meta, _body = _parse_frontmatter(content)
        specs.append(
            Spec(
                id=meta.get("id", path.stem),
                title=meta.get("title", path.stem),
                source_file=meta.get("source"),
                content=content,
                created_at=datetime.fromisoformat(meta["created"]) if "created" in meta else None,
                issue_id=meta.get("issue_id"),
            )
        )
    return specs


def show_spec(spec_id: str, specs_dir: Path = Path("specs")) -> Spec:
    """Show a single spec by ID."""
    for s in list_specs(specs_dir):
        if s.id == spec_id:
            return s
    raise FileNotFoundError(f"Spec not found: {spec_id}")
