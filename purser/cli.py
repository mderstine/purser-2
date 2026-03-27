"""Purser CLI entry point."""

from __future__ import annotations

import json
from pathlib import Path

import click

from purser import __version__


def _json_out(data, as_json: bool) -> None:
    """Print data as JSON or human-readable."""
    if as_json:
        if hasattr(data, "model_dump"):
            click.echo(json.dumps(data.model_dump(mode="json"), indent=2))
        elif isinstance(data, list) and data and hasattr(data[0], "model_dump"):
            click.echo(json.dumps([d.model_dump(mode="json") for d in data], indent=2))
        else:
            click.echo(json.dumps(data, indent=2, default=str))
    else:
        click.echo(data)


@click.group()
@click.version_option(__version__)
@click.option("--json", "use_json", is_flag=True, help="Output as JSON")
@click.pass_context
def cli(ctx: click.Context, use_json: bool) -> None:
    """Purser: Agent-agnostic project management framework."""
    ctx.ensure_object(dict)
    ctx.obj["json"] = use_json


# --- init ---


@cli.command()
@click.option("--check", is_flag=True, help="Check initialization status without modifying")
@click.option("--force", is_flag=True, help="Force re-initialization")
@click.pass_context
def init(ctx: click.Context, check: bool, force: bool) -> None:
    """Initialize purser in the current project.

    Creates the directory structure, initializes DuckDB for memory,
    and sets up beads (Dolt) for issue tracking.
    """
    import shutil

    from purser.config import load_config
    from purser.memory import MemoryStore

    config = load_config()

    # Check mode: just report status
    if check:
        _check_init_status(config)
        return

    # Check if already initialized
    is_init = _is_initialized(config)
    if is_init and not force:
        click.echo("Purser is already initialized. Use --force to re-initialize.")
        click.echo(f"  Memory DB: {config.memory_db}")
        click.echo(f"  Specs dir: {config.specs_dir}")
        click.echo(f"  Beads: {shutil.which('bd') or 'not found'}")
        return

    if force and is_init:
        click.echo("Force re-initializing purser...")

    # Create directories
    for d in [config.specs_dir, config.formulas_dir, Path(".purser")]:
        d.mkdir(parents=True, exist_ok=True)
        click.echo(f"Created: {d}")

    # Init DuckDB
    mem = MemoryStore(config.memory_db)
    mem.close()
    click.echo(f"Initialized: {config.memory_db}")

    # Init beads
    try:
        from purser.beads import init_beads

        init_beads()
        click.echo("Initialized: beads (issue tracking)")
    except FileNotFoundError:
        click.echo("Warning: bd CLI not found. Beads not initialized.", err=True)
        click.echo("  Install: brew install beads", err=True)
        click.echo("  Or visit: https://github.com/gastowngang/beads", err=True)
    except Exception as e:
        click.echo(f"Warning: beads init failed: {e}", err=True)

    # Check for recommended tools
    _check_recommended_tools()

    click.echo()
    click.echo("Purser initialized successfully!")
    click.echo(f"  Memory DB: {config.memory_db}")
    click.echo()
    click.echo("Next steps:")
    click.echo('  purser spec add "Your feature description"')
    click.echo("  purser work next  # See available work")


def _is_initialized(config) -> bool:
    """Check if purser appears to be initialized."""
    return (
        config.memory_db.parent.exists()
        and config.specs_dir.exists()
        and config.formulas_dir.exists()
    )


def _check_init_status(config) -> None:
    """Report initialization status."""
    import shutil

    click.echo("Purser initialization status:")
    click.echo(
        f"  Memory DB directory: {'✓' if config.memory_db.parent.exists() else '✗'} {config.memory_db.parent}"
    )
    click.echo(f"  Memory DB file: {'✓' if config.memory_db.exists() else '✗'} {config.memory_db}")
    click.echo(
        f"  Specs directory: {'✓' if config.specs_dir.exists() else '✗'} {config.specs_dir}"
    )
    click.echo(
        f"  Formulas directory: {'✓' if config.formulas_dir.exists() else '✗'} {config.formulas_dir}"
    )
    click.echo(
        f"  Beads CLI: {'✓' if shutil.which('bd') else '✗'} {shutil.which('bd') or 'not found'}"
    )


def _check_recommended_tools() -> None:
    """Check for recommended companion tools."""
    import shutil

    tools = [
        ("ruff", "uv add --dev ruff"),
        ("ty", "uv add --dev ty"),
        ("bd", "brew install beads"),
    ]

    missing = []
    for tool, install_cmd in tools:
        if not shutil.which(tool):
            missing.append((tool, install_cmd))

    if missing:
        click.echo()
        click.echo("Optional tools not found (install for full functionality):")
        for tool, install_cmd in missing:
            click.echo(f"  {tool}: {install_cmd}")


# --- spec ---


@cli.group()
def spec() -> None:
    """Manage specs and PRDs."""


@spec.command("intake")
@click.argument("source", type=click.Path(exists=True))
@click.option("--adapter", default=None, help="LLM adapter to use for structuring")
@click.pass_context
def spec_intake(ctx: click.Context, source: str, adapter: str | None) -> None:
    """Ingest a raw spec/PRD and produce structured markdown."""
    from purser.config import load_config
    from purser.spec import intake_spec

    config = load_config()
    llm = None
    if adapter:
        config.adapter.provider = adapter
        from purser.adapters import get_adapter

        llm = get_adapter(config.adapter)

    result = intake_spec(Path(source), adapter=llm, output_dir=config.specs_dir)
    _json_out(result, ctx.obj.get("json", False))


@spec.command("add")
@click.argument("description", required=False)
@click.option("--file", "-f", type=click.Path(exists=True), help="Read description from file")
@click.option("--adapter", default=None, help="LLM adapter to use for structuring")
@click.option("--title", "-t", default=None, help="Override the generated title")
@click.pass_context
def spec_add(
    ctx: click.Context,
    description: str | None,
    file: str | None,
    adapter: str | None,
    title: str | None,
) -> None:
    """Add a new spec from description text (uses PM agent to synthesize).

    Examples:
        purser spec add "Build a user authentication system with OAuth"
        echo "Feature description" | purser spec add
        purser spec add -f raw-notes.md
    """
    import sys
    from pathlib import Path

    from purser.adapters import get_adapter
    from purser.config import load_config
    from purser.spec import (
        _parse_frontmatter,
        _write_frontmatter,
        intake_spec,
    )

    # Get description from file, argument, or stdin
    if file:
        text = Path(file).read_text()
    elif description:
        text = description
    else:
        text = sys.stdin.read()

    if not text or not text.strip():
        click.echo(
            "Error: No description provided. Use argument, --file, or pipe to stdin.", err=True
        )
        ctx.exit(1)

    config = load_config()
    if adapter:
        config.adapter.provider = adapter

    try:
        llm = get_adapter(config.adapter)
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        ctx.exit(1)

    click.echo("Synthesizing spec with PM agent...")
    result = intake_spec(text, adapter=llm, output_dir=config.specs_dir)

    # Override title if provided
    if title:
        result.title = title
        # Update the file with new title
        spec_path = config.specs_dir / f"{result.id.replace('spec-', '')}.md"
        if spec_path.exists():
            content = spec_path.read_text()
            meta, body = _parse_frontmatter(content)
            meta["title"] = title
            spec_path.write_text(_write_frontmatter(meta, body))

    if ctx.obj.get("json"):
        _json_out(result, True)
    else:
        click.echo(f"Created spec: {result.id}")
        click.echo(f"  Title: {result.title}")
        click.echo(f"  Path: {config.specs_dir / f'{result.id.replace("spec-", "")}.md'}")


@spec.command("list")
@click.pass_context
def spec_list(ctx: click.Context) -> None:
    """List all specs."""
    from purser.config import load_config
    from purser.spec import list_specs

    config = load_config()
    specs = list_specs(config.specs_dir)
    if ctx.obj.get("json"):
        _json_out(specs, True)
    else:
        for s in specs:
            click.echo(f"  {s.id}  {s.title}")
        if not specs:
            click.echo("No specs found.")


@spec.command("show")
@click.argument("spec_id")
@click.pass_context
def spec_show(ctx: click.Context, spec_id: str) -> None:
    """Show a spec by ID."""
    from purser.config import load_config
    from purser.spec import show_spec

    config = load_config()
    result = show_spec(spec_id, config.specs_dir)
    if ctx.obj.get("json"):
        _json_out(result, True)
    else:
        click.echo(result.content)


# --- plan ---


@cli.group()
def plan() -> None:
    """Manage plans (spec decomposition)."""


@plan.command("create")
@click.argument("spec_id")
@click.option("--adapter", default=None, help="LLM adapter for decomposition")
@click.pass_context
def plan_create(ctx: click.Context, spec_id: str, adapter: str | None) -> None:
    """Decompose a spec into epics, features, and tasks."""
    from purser.config import load_config
    from purser.planner import create_plan

    config = load_config()
    llm = None
    if adapter:
        config.adapter.provider = adapter
        from purser.adapters import get_adapter

        llm = get_adapter(config.adapter)

    result = create_plan(spec_id, adapter=llm, config=config)
    _json_out(result, ctx.obj.get("json", False))


@plan.command("show")
@click.argument("plan_id")
@click.pass_context
def plan_show(ctx: click.Context, plan_id: str) -> None:
    """Show a plan's dependency tree."""
    from purser.beads import dep_tree

    click.echo(dep_tree(plan_id))


# --- work ---


@cli.group()
def work() -> None:
    """Worker commands for executing beads."""


@work.command("next")
@click.option("--limit", default=5, help="Max issues to show")
@click.pass_context
def work_next(ctx: click.Context, limit: int) -> None:
    """Show next ready (unblocked) beads."""
    from purser.beads import ready_issues

    issues = ready_issues(limit=limit)
    if ctx.obj.get("json"):
        _json_out(issues, True)
    else:
        for i in issues:
            click.echo(f"  {i.id}  [{i.type}] P{i.priority}  {i.title}")
        if not issues:
            click.echo("No ready issues.")


@work.command("claim")
@click.argument("issue_id")
@click.pass_context
def work_claim(ctx: click.Context, issue_id: str) -> None:
    """Claim a bead for work."""
    from purser.beads import claim_issue

    issue = claim_issue(issue_id)
    _json_out(issue, ctx.obj.get("json", False))
    if not ctx.obj.get("json"):
        click.echo(f"Claimed {issue.id}: {issue.title}")


@work.command("done")
@click.argument("issue_id")
@click.option("--reason", default=None, help="Completion reason")
@click.pass_context
def work_done(ctx: click.Context, issue_id: str, reason: str | None) -> None:
    """Mark a bead as complete."""
    from purser.beads import close_issue

    issue = close_issue(issue_id, reason=reason)
    _json_out(issue, ctx.obj.get("json", False))
    if not ctx.obj.get("json"):
        click.echo(f"Closed {issue.id}: {issue.title}")


@work.command("discover")
@click.argument("title")
@click.option("--from-issue", default=None, help="Issue this was discovered from")
@click.option("--type", "issue_type", default="bug", help="Issue type")
@click.option("-d", "--description", default=None)
@click.pass_context
def work_discover(
    ctx: click.Context,
    title: str,
    from_issue: str | None,
    issue_type: str,
    description: str | None,
) -> None:
    """File a new bead for a discovered issue."""
    from purser.beads import add_dependency, create_issue

    issue = create_issue(title, type=issue_type, description=description)
    if from_issue:
        add_dependency(issue.id, from_issue, dep_type="discovered-from")

    _json_out(issue, ctx.obj.get("json", False))
    if not ctx.obj.get("json"):
        click.echo(f"Filed {issue.id}: {issue.title}")


# --- memory ---


@cli.group()
def memory() -> None:
    """Session memory (DuckDB)."""


@memory.command("store")
@click.argument("key")
@click.argument("value")
@click.option("--namespace", default="default")
def memory_store(key: str, value: str, namespace: str) -> None:
    """Store a key-value pair in memory."""
    from purser.config import load_config
    from purser.memory import MemoryStore

    config = load_config()
    mem = MemoryStore(config.memory_db)
    mem.store(key, value, namespace=namespace)
    mem.close()
    click.echo(f"Stored: {key}")


@memory.command("query")
@click.argument("text")
@click.option("--limit", default=10)
@click.pass_context
def memory_query(ctx: click.Context, text: str, limit: int) -> None:
    """Search memory by text."""
    from purser.config import load_config
    from purser.memory import MemoryStore

    config = load_config()
    mem = MemoryStore(config.memory_db)
    results = mem.query(text, limit=limit)
    mem.close()

    if ctx.obj.get("json"):
        _json_out(results, True)
    else:
        for r in results:
            click.echo(f"  [{r.namespace}] {r.key}: {r.value[:80]}")
        if not results:
            click.echo("No results.")


# --- lint ---


@cli.command()
@click.option("--fix", is_flag=True, help="Auto-fix issues where possible")
@click.option("--path", "target", default=".", help="Path to lint (default: current directory)")
@click.pass_context
def lint(ctx: click.Context, fix: bool, target: str) -> None:
    """Run ruff and ty checks on project code.

    Runs ruff lint, ruff format, and ty type checking. Any agent (Claude, Codex,
    Gemini, Ollama, etc.) can call this to validate code quality.

    Exit code 0 = all clean. Non-zero = issues found.
    """
    from purser.lint import run_lint

    results = run_lint(target=target, fix=fix)
    if ctx.obj.get("json"):
        _json_out(results, True)
    else:
        for check in results["checks"]:
            status = "PASS" if check["passed"] else "FAIL"
            click.echo(f"  [{status}] {check['name']}")
            if check["output"]:
                for line in check["output"].strip().splitlines():
                    click.echo(f"         {line}")

        click.echo()
        if results["passed"]:
            click.echo("All checks passed.")
        else:
            click.echo(f"{results['failed_count']}/{results['total_count']} checks failed.")
            ctx.exit(1)


# --- launch ---


# --- launch ---


@cli.group()
def launch() -> None:
    """Configure external agents (opencode, codex, etc.) to use purser."""


@launch.command("opencode")
@click.option("--model", default="qwen3-coder:480b-cloud", help="Ollama Cloud model")
@click.option("--base-url", default="https://ollama.com/v1", help="API base URL")
@click.option(
    "--output",
    "output_path",
    default=None,
    type=click.Path(),
    help="Config output path (default: ~/.config/opencode/opencode.json)",
)
@click.pass_context
def launch_opencode(
    ctx: click.Context,
    model: str,
    base_url: str,
    output_path: str | None,
) -> None:
    """Generate opencode config with purser integration and Ollama Cloud.

    Sets up opencode to use Ollama Cloud as the LLM provider and injects
    purser CLI commands as the project management workflow.

    Requires: OLLAMA_API_KEY environment variable.
    Run `ollama signin` or create a key at https://ollama.com/settings/keys
    """
    from pathlib import Path

    from purser.launch import generate_opencode_config

    out = Path(output_path) if output_path else None
    config = generate_opencode_config(model=model, base_url=base_url, output_path=out)

    if ctx.obj.get("json"):
        _json_out(config, True)
    else:
        target = out or Path("~/.config/opencode/opencode.json").expanduser()
        click.echo(f"OpenCode config written to: {target}")
        click.echo("  Provider: ollama-cloud")
        click.echo(f"  Model: {model}")
        click.echo(f"  Base URL: {base_url}")
        click.echo()
        click.echo("Next steps:")
        click.echo("  1. export OLLAMA_API_KEY=<your key>")
        click.echo("  2. ollama launch opencode")
        click.echo("     OR: opencode  (if installed directly)")


@launch.command("instructions")
@click.argument("role", type=click.Choice(["pm", "worker"]))
@click.option(
    "--output",
    "output_path",
    default=None,
    type=click.Path(),
    help="Write to file instead of stdout",
)
def launch_instructions(role: str, output_path: str | None) -> None:
    """Print agent instructions for any external tool.

    These instructions can be pasted into any agent's system prompt,
    AGENTS.md, .codex config, or similar instruction file.
    """
    from purser.launch import generate_agent_instructions

    instructions = generate_agent_instructions(role)
    if output_path:
        from pathlib import Path

        Path(output_path).write_text(instructions)
        click.echo(f"Instructions written to: {output_path}")
    else:
        click.echo(instructions)


# --- sync ---


@cli.command()
def sync() -> None:
    """Sync beads state and flush memory."""
    from purser.config import load_config
    from purser.memory import MemoryStore

    config = load_config()

    # Flush memory
    mem = MemoryStore(config.memory_db)
    mem.flush()
    mem.close()
    click.echo("Memory flushed.")

    # Sync beads
    try:
        from purser.beads import sync as bd_sync

        bd_sync()
        click.echo("Beads synced.")
    except Exception as e:
        click.echo(f"Beads sync warning: {e}", err=True)


# --- agent ---


@cli.group()
def agent() -> None:
    """Run agent loops."""


@agent.command("run")
@click.argument("role", type=click.Choice(["pm", "worker"]))
@click.option("--adapter", default=None, help="LLM adapter provider")
@click.option("--model", default=None, help="Model name override")
@click.option("--task", default=None, help="Specific task (pm: intake/plan, worker: issue ID)")
@click.option(
    "--input",
    "input_file",
    default=None,
    type=click.Path(exists=True),
    help="Input file (e.g., raw spec for pm intake)",
)
def agent_run(
    role: str,
    adapter: str | None,
    model: str | None,
    task: str | None,
    input_file: str | None,
) -> None:
    """Run a PM or Worker agent loop."""
    import asyncio

    from purser.adapters import get_adapter
    from purser.config import load_config
    from purser.memory import MemoryStore

    config = load_config()
    if adapter:
        config.adapter.provider = adapter
    if model:
        config.adapter.model = model

    llm = get_adapter(config.adapter)
    mem = MemoryStore(config.memory_db)

    try:
        if role == "pm":
            from purser.agents.pm import PMAgent

            agent_instance = PMAgent(llm, mem, config)
            asyncio.run(agent_instance.run(task=task or "intake", input_file=input_file))
        else:
            from purser.agents.worker import WorkerAgent

            agent_instance = WorkerAgent(llm, mem, config)
            asyncio.run(agent_instance.run(issue_id=task))
    finally:
        mem.close()


# --- gh (GitHub integration) ---

from purser.gh.commands import gh_group  # noqa: E402

cli.add_command(gh_group)

if __name__ == "__main__":
    cli()
