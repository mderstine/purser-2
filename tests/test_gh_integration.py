"""Integration tests for GitHub sync functionality.

Tests use mocked gh CLI subprocess calls to verify sync logic
without hitting the real GitHub API.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

import datetime as _dt

from purser.gh.conflict import ChangeClass, Resolution, classify_change, resolve_conflict
from purser.gh.content_hash import compute_content_hash
from purser.gh.dep_footer import DepFooter, parse_dep_footer, render_dep_footer, strip_dep_footer
from purser.gh.labels import prefixed_label
from purser.gh.serializer import (
    bead_to_gh_payload,
    gh_issue_to_bead_fields,
)
from purser.gh.sync_engine import push_to_project, sync_project_items
from purser.gh.sync_store import CONFLICT, LOCAL_DIRTY, SYNCED, SyncState, SyncStore
from purser.models import Dependency, GitHubConfig, Issue

# Rebuild Issue model — inject datetime into the module namespace
# so pydantic can resolve the TYPE_CHECKING-only forward ref
Issue.model_rebuild(_types_namespace={"datetime": _dt.datetime})


# --- Fixtures ---


@pytest.fixture
def sync_db(tmp_path: Path) -> SyncStore:
    """Create a temporary SyncStore."""
    db = tmp_path / "test_sync.duckdb"
    store = SyncStore(db)
    yield store
    store.close()


@pytest.fixture
def gh_config() -> GitHubConfig:
    """Default GitHub config for tests."""
    return GitHubConfig(
        enabled=True,
        repo="testowner/testrepo",
        project="Test Project",
        conflict_strategy="local-wins",
        label_prefix="",
        username_map={"local_user": "gh_user"},
    )


@pytest.fixture
def sample_issue() -> Issue:
    """A sample bead Issue for testing."""
    return Issue(
        id="bd-test1",
        title="Test task",
        type="task",
        status="open",
        priority=2,
        description="A test description",
        assignee="local_user",
        labels=["backend", "spec:test"],
        parent="bd-parent1",
        dependencies=[
            Dependency(type="blocks", target_id="bd-dep1"),
            Dependency(type="relates-to", target_id="bd-dep2"),
        ],
    )


@pytest.fixture
def sample_gh_issue() -> dict:
    """A sample GitHub Issue JSON response."""
    return {
        "number": 42,
        "title": "Test task from GH",
        "body": "A remote description\n\n<!-- purser:deps -->\n---\n**Parent:** #10\n**Blocks:** #20, #30\n<!-- /purser:deps -->",
        "state": "open",
        "node_id": "I_abc123",
        "assignee": {"login": "gh_user"},
        "labels": [
            {"name": "type:task"},
            {"name": "priority:high"},
            {"name": "backend"},
        ],
    }


# --- Content Hash Tests ---


class TestContentHash:
    def test_stable_hash(self, sample_issue: Issue) -> None:
        h1 = compute_content_hash(sample_issue)
        h2 = compute_content_hash(sample_issue)
        assert h1 == h2

    def test_label_order_independent(self) -> None:
        i1 = Issue(id="x", title="T", labels=["a", "b", "c"])
        i2 = Issue(id="x", title="T", labels=["c", "a", "b"])
        assert compute_content_hash(i1) == compute_content_hash(i2)

    def test_different_on_title_change(self, sample_issue: Issue) -> None:
        h1 = compute_content_hash(sample_issue)
        sample_issue.title = "Changed title"
        h2 = compute_content_hash(sample_issue)
        assert h1 != h2

    def test_different_on_status_change(self, sample_issue: Issue) -> None:
        h1 = compute_content_hash(sample_issue)
        sample_issue.status = "closed"
        h2 = compute_content_hash(sample_issue)
        assert h1 != h2


# --- Conflict Detection Tests ---


class TestConflictDetection:
    def test_no_change(self) -> None:
        assert classify_change("aaa", "aaa", "aaa") == ChangeClass.NO_CHANGE

    def test_local_only(self) -> None:
        assert classify_change("bbb", "aaa", "aaa") == ChangeClass.LOCAL_ONLY

    def test_remote_only(self) -> None:
        assert classify_change("aaa", "bbb", "aaa") == ChangeClass.REMOTE_ONLY

    def test_conflict(self) -> None:
        assert classify_change("bbb", "ccc", "aaa") == ChangeClass.CONFLICT

    def test_never_synced_same(self) -> None:
        assert classify_change("aaa", "aaa", None) == ChangeClass.NO_CHANGE

    def test_never_synced_different(self) -> None:
        assert classify_change("aaa", "bbb", None) == ChangeClass.CONFLICT

    def test_local_wins_strategy(self) -> None:
        result = resolve_conflict("bd-1", "local-wins")
        assert result == Resolution.USE_LOCAL

    def test_remote_wins_strategy(self) -> None:
        result = resolve_conflict("bd-1", "remote-wins")
        assert result == Resolution.USE_REMOTE


# --- Dependency Footer Tests ---


class TestDepFooter:
    def test_render_empty(self) -> None:
        footer = DepFooter()
        assert render_dep_footer(footer) == ""

    def test_render_full(self) -> None:
        footer = DepFooter(
            parent=10,
            blocks=[20, 30],
            blocked_by=[40],
            related=[50],
        )
        result = render_dep_footer(footer)
        assert "**Parent:** #10" in result
        assert "**Blocks:** #20, #30" in result
        assert "**Blocked by:** #40" in result
        assert "**Related:** #50" in result

    def test_parse_roundtrip(self) -> None:
        original = DepFooter(parent=10, blocks=[20, 30], blocked_by=[5])
        rendered = render_dep_footer(original)
        body = f"Some description\n{rendered}"
        parsed = parse_dep_footer(body)
        assert parsed.parent == 10
        assert parsed.blocks == [20, 30]
        assert parsed.blocked_by == [5]

    def test_strip_footer(self) -> None:
        footer = DepFooter(parent=10)
        body = f"Description\n{render_dep_footer(footer)}"
        stripped = strip_dep_footer(body)
        assert "purser:deps" not in stripped
        assert "Description" in stripped


# --- Sync Store Tests ---


class TestSyncStore:
    def test_upsert_and_get(self, sync_db: SyncStore) -> None:
        state = SyncState(
            bead_id="bd-1",
            gh_repo="owner/repo",
            gh_issue_num=42,
            sync_status=SYNCED,
        )
        sync_db.upsert(state)
        result = sync_db.get("bd-1")
        assert result is not None
        assert result.gh_issue_num == 42
        assert result.sync_status == SYNCED

    def test_get_nonexistent(self, sync_db: SyncStore) -> None:
        assert sync_db.get("nonexistent") is None

    def test_delete(self, sync_db: SyncStore) -> None:
        sync_db.upsert(SyncState(bead_id="bd-1", gh_repo="r"))
        sync_db.delete("bd-1")
        assert sync_db.get("bd-1") is None

    def test_mark_synced(self, sync_db: SyncStore) -> None:
        sync_db.upsert(SyncState(bead_id="bd-1", gh_repo="r", sync_status="unlinked"))
        sync_db.mark_synced("bd-1", "hash123")
        result = sync_db.get("bd-1")
        assert result is not None
        assert result.sync_status == SYNCED
        assert result.content_hash == "hash123"
        assert result.last_synced is not None

    def test_mark_dirty(self, sync_db: SyncStore) -> None:
        sync_db.upsert(SyncState(bead_id="bd-1", gh_repo="r", sync_status=SYNCED))
        sync_db.mark_dirty("bd-1", LOCAL_DIRTY)
        result = sync_db.get("bd-1")
        assert result is not None
        assert result.sync_status == LOCAL_DIRTY

    def test_mark_conflict(self, sync_db: SyncStore) -> None:
        sync_db.upsert(SyncState(bead_id="bd-1", gh_repo="r"))
        sync_db.mark_conflict("bd-1")
        result = sync_db.get("bd-1")
        assert result is not None
        assert result.sync_status == CONFLICT

    def test_list_by_status(self, sync_db: SyncStore) -> None:
        sync_db.upsert(SyncState(bead_id="bd-1", gh_repo="r", sync_status=SYNCED))
        sync_db.upsert(SyncState(bead_id="bd-2", gh_repo="r", sync_status=LOCAL_DIRTY))
        sync_db.upsert(SyncState(bead_id="bd-3", gh_repo="r", sync_status=SYNCED))
        synced = sync_db.list_by_status(SYNCED)
        assert len(synced) == 2
        dirty = sync_db.list_by_status(LOCAL_DIRTY)
        assert len(dirty) == 1

    def test_summary(self, sync_db: SyncStore) -> None:
        sync_db.upsert(SyncState(bead_id="bd-1", gh_repo="r", sync_status=SYNCED))
        sync_db.upsert(SyncState(bead_id="bd-2", gh_repo="r", sync_status=LOCAL_DIRTY))
        summary = sync_db.summary()
        assert summary[SYNCED] == 1
        assert summary[LOCAL_DIRTY] == 1


# --- Serializer Tests ---


class TestSerializer:
    def test_bead_to_gh_payload(self, sample_issue: Issue, gh_config: GitHubConfig) -> None:
        payload = bead_to_gh_payload(sample_issue, gh_config)
        assert payload["title"] == "Test task"
        assert "type:task" in payload["labels"]
        assert "priority:medium" in payload["labels"]
        assert payload["assignee"] == "gh_user"  # Mapped via username_map

    def test_bead_to_gh_payload_with_prefix(self, sample_issue: Issue) -> None:
        config = GitHubConfig(enabled=True, repo="o/r", label_prefix="purser:")
        payload = bead_to_gh_payload(sample_issue, config)
        assert "purser:type:task" in payload["labels"]
        assert "purser:priority:medium" in payload["labels"]

    def test_gh_issue_to_bead_fields(
        self, sample_gh_issue: dict, gh_config: GitHubConfig
    ) -> None:
        fields = gh_issue_to_bead_fields(sample_gh_issue, gh_config)
        assert fields["title"] == "Test task from GH"
        assert fields["type"] == "task"
        assert fields["priority"] == 1  # high
        assert fields["assignee"] == "local_user"  # Reverse mapped
        assert fields["status"] == "open"
        assert "backend" in fields["labels"]
        # type:task and priority:high should be stripped from labels
        assert "type:task" not in fields["labels"]
        assert "priority:high" not in fields["labels"]

    def test_gh_closed_issue(self, gh_config: GitHubConfig) -> None:
        gh_issue = {"title": "Closed", "state": "closed", "labels": [], "body": ""}
        fields = gh_issue_to_bead_fields(gh_issue, gh_config)
        assert fields["status"] == "closed"


class TestProjectSync:
    def test_push_to_project_reuses_existing_project_item(
        self,
        sync_db: SyncStore,
        sample_issue: Issue,
        gh_config: GitHubConfig,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        sync_db.upsert(
            SyncState(
                bead_id=sample_issue.id,
                gh_repo=gh_config.repo,
                gh_issue_num=42,
                gh_project_id="PVTI_existing",
                sync_status=SYNCED,
            )
        )

        calls: list[tuple[str, str, dict[str, str], str, int]] = []

        def fake_sync_item_fields(
            project_id: str,
            item_id: str,
            field_map: dict[str, str],
            issue_type: str,
            priority: int,
            blocks: list[str] | None = None,
            blocked_by: list[str] | None = None,
        ) -> None:
            calls.append((project_id, item_id, field_map, issue_type, priority))

        monkeypatch.setattr("purser.gh.project_fields.sync_item_fields", fake_sync_item_fields)
        monkeypatch.setattr(
            "purser.gh.issues.get_issue",
            lambda repo, issue_num: pytest.fail("existing project item should not refetch issue"),
        )
        monkeypatch.setattr(
            "purser.gh.projects.add_item_to_project",
            lambda project_id, content_id: pytest.fail("existing project item should not be re-added"),
        )

        count = push_to_project(
            [sample_issue],
            gh_config,
            sync_db,
            "PVT_project",
            {"Type": "field_type", "Priority": "field_priority"},
        )

        assert count == 1
        assert calls == [
            (
                "PVT_project",
                "PVTI_existing",
                {"Type": "field_type", "Priority": "field_priority"},
                "task",
                2,
            )
        ]
        state = sync_db.get(sample_issue.id)
        assert state is not None
        assert state.gh_project_id == "PVTI_existing"

    def test_sync_project_items_uses_configured_project(
        self,
        sync_db: SyncStore,
        sample_issue: Issue,
        gh_config: GitHubConfig,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        sync_db.upsert(
            SyncState(
                bead_id=sample_issue.id,
                gh_repo=gh_config.repo,
                gh_issue_num=42,
                sync_status=SYNCED,
            )
        )

        monkeypatch.setattr(
            "purser.gh.projects.find_project",
            lambda owner, project_name_or_number: {
                "id": "PVT_project",
                "title": project_name_or_number,
            },
        )
        monkeypatch.setattr(
            "purser.gh.project_fields.ensure_project_fields",
            lambda project_id: {"Type": "field_type", "Priority": "field_priority"},
        )

        captured: dict[str, object] = {}

        def fake_push_to_project(
            issues: list[Issue],
            config: GitHubConfig,
            store: SyncStore,
            project_id: str,
            field_map: dict[str, str],
            *,
            dry_run: bool = False,
        ) -> int:
            captured["issues"] = issues
            captured["config"] = config
            captured["project_id"] = project_id
            captured["field_map"] = field_map
            captured["dry_run"] = dry_run
            return 1

        monkeypatch.setattr("purser.gh.sync_engine.push_to_project", fake_push_to_project)

        count = sync_project_items([sample_issue], gh_config, sync_db)

        assert count == 1
        assert captured["issues"] == [sample_issue]
        assert captured["config"] == gh_config
        assert captured["project_id"] == "PVT_project"
        assert captured["field_map"] == {"Type": "field_type", "Priority": "field_priority"}
        assert captured["dry_run"] is False


# --- Label Helper Tests ---


class TestLabels:
    def test_prefixed_label_with_prefix(self) -> None:
        assert prefixed_label("purser:", "type:task") == "purser:type:task"

    def test_prefixed_label_no_prefix(self) -> None:
        assert prefixed_label("", "type:task") == "type:task"
