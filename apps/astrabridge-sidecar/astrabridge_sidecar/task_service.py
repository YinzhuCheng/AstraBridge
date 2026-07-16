from __future__ import annotations

import datetime as dt
import json
import os
import re
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable

from .coding_kernel import task_refs_from_coding_events
from .common import WORKSPACE_STATE_DIRNAME, new_id, now_iso, read_json, write_json
from .durable_run_store import DurableRunEventStore
from .agent_orchestration_contract import (
    lift_task_graph_to_agent_orchestration_graph,
    lower_agent_orchestration_graph_to_task_graph,
)
from .agent_orchestration_checks import (
    build_known_model_capabilities,
    diff_agent_orchestration_graphs,
    render_agent_orchestration_report_markdown,
)
from .agent_orchestration_compiler import compile_agent_orchestration_graph
from .agent_orchestration_file_format import (
    load_agent_orchestration_graph_file,
    parse_agent_orchestration_graph_text,
    serialize_agent_orchestration_graph,
    write_agent_orchestration_graph_file,
)
from .model_catalog.catalog import preferred_provider_model_record, provider_model_records
from .providers.runtime_transition import summarize_transition
from .security import DESKTOP_KEY_PATH_RE, SECRET_RE, SecurityError, redact_sensitive, resolve_under
from .task_graph_contract import (
    ARTIFACT_KINDS,
    GRAPH_TEMPLATE_IDS,
    load_task_graph_fixture,
    validate_graph_definition,
    validate_task_graph_run,
)
from .usage_signal import normalize_usage_signal, usage_not_available


TASK_STATE_SCHEMA_VERSION = "astrabridge-task-state-v1"
TASK_GRAPH_DRY_RUN_SCHEMA_VERSION = "astrabridge-task-graph-dry-run-v1"
DEFAULT_HANDOFF_POLICY = "multi_provider_handoff"
GRAPH_DEFINITION_LIMIT = 20
GRAPH_RUN_REF_LIMIT = 40
GRAPH_SNAPSHOT_REF_LIMIT = 80
GRAPH_TEMPLATE_SUMMARIES = {
    "supervisor_worker_synthesizer": "Supervisor plans, one worker executes, one synthesizer returns the bounded result.",
    "fanout_fanin_research": "One planner fans out bounded research branches and one synthesizer merges their artifacts.",
    "code_fix_test_review": "Planner, code worker, test validator, and review node for code-change workflows.",
    "provider_update_smoke_gate": "Metadata discovery, smoke validation, and manual promotion gate for provider updates.",
    "document_extract_analyze_report": "Extractor, analyst, and report writer for bounded document workflows.",
    "multimodal_capability_adapter": "Probe supported input/output modes, adapt the message contract, and verify multimodal fallback behavior.",
    "custom_blank_graph": "Minimal starter graph with one neutral entry node for custom orchestration authoring.",
}
GRAPH_TEMPLATE_PRODUCT_METADATA = {
    "supervisor_worker_synthesizer": {
        "recommended_provider_ids": ["qwen", "kimi"],
        "recommended_model_ids": ["qwen3.7-plus", "kimi-k2.6"],
        "artifact_expectations": ["Structured plan", "Bounded worker report", "Final run summary"],
        "validation_hints": ["Check the worker route before dry-run.", "Keep the worker-to-synth handoff artifact-first."],
        "constraints": ["Single worker lane.", "No silent high-risk writes."],
    },
    "fanout_fanin_research": {
        "recommended_provider_ids": ["qwen", "kimi"],
        "recommended_model_ids": ["qwen3.7-plus", "kimi-k2.6"],
        "artifact_expectations": ["Branch research notes", "Merge summary", "Attributed branch outputs"],
        "validation_hints": ["Validate every fan-out edge policy.", "Keep branch outputs bounded before merge."],
        "constraints": ["Parallel branch lanes.", "Synthesizer consumes declared artifacts only."],
    },
    "code_fix_test_review": {
        "recommended_provider_ids": ["qwen", "deepseek", "kimi"],
        "recommended_model_ids": ["qwen3.7-plus", "deepseek-v4-pro", "kimi-k2.6"],
        "artifact_expectations": ["Fix plan", "Code diff", "Test report", "Review report"],
        "validation_hints": ["Pin the code worker model.", "Keep code-change, test, and review as separate nodes."],
        "constraints": ["Code changes stay bounded.", "Review evidence must survive reload."],
    },
    "provider_update_smoke_gate": {
        "recommended_provider_ids": ["qwen", "glm"],
        "recommended_model_ids": ["qwen3.7-plus", "glm-5.2"],
        "artifact_expectations": ["Provider diff bundle", "Smoke matrix", "Promotion decision record"],
        "validation_hints": ["Dry-run should surface blocked provider cases.", "Promotion remains gated until review."],
        "constraints": ["Human approval before promotion.", "No silent external writeback."],
    },
    "document_extract_analyze_report": {
        "recommended_provider_ids": ["qwen", "glm"],
        "recommended_model_ids": ["qwen3.7-plus", "glm-5.2"],
        "artifact_expectations": ["Document extract", "Structured analysis", "Final report"],
        "validation_hints": ["Check extract node output schema first.", "Preserve artifact handoff into the report node."],
        "constraints": ["Document path stays bounded.", "Report is generated from declared extract artifacts only."],
    },
    "multimodal_capability_adapter": {
        "recommended_provider_ids": ["qwen", "glm", "kimi"],
        "recommended_model_ids": ["qwen3.7-plus", "glm-5.2", "kimi-k2.6"],
        "artifact_expectations": ["Capability probe", "Adapted multimodal contract", "Fallback validation report"],
        "validation_hints": ["Confirm the target model actually supports the intended input modes.", "Keep fallback behavior explicit instead of silent degradation."],
        "constraints": ["Bound multimodal payload sizes.", "Declare fallback paths before live provider execution."],
    },
    "custom_blank_graph": {
        "recommended_provider_ids": ["qwen", "kimi"],
        "recommended_model_ids": ["qwen3.7-plus", "kimi-k2.6"],
        "artifact_expectations": ["Starter graph manifest"],
        "validation_hints": ["Rename the seed node before dry-run.", "Add at least one downstream worker before fixture execution."],
        "constraints": ["Treat this as an authoring scaffold, not a finished workflow."],
    },
}
AUTO_INJECTED_CONTEXT_NAME_MARKERS = (
    "--- astrabridge project context pack",
    "astrabridge project context pack",
    "--- astrabridge asset context pack",
    "astrabridge asset context pack",
    "freshness rule:",
)
SMOKE_TASK_PREFIX_PATTERN = re.compile(r"^Step\s+\d+\s+(?:source|target)\s+for\s+", re.IGNORECASE)


def _compact_text(value: Any, limit: int = 240) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


def _optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _promote_dry_run_status(current: str, next_status: str) -> str:
    rank = {"pass": 0, "warning": 1, "blocked": 2}
    return next_status if rank.get(next_status, 0) > rank.get(current, 0) else current


def _dry_run_status_counts(*, node_results: list[dict[str, Any]], edge_results: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"pass": 0, "warning": 0, "blocked": 0}
    for item in [*node_results, *edge_results]:
        if not isinstance(item, dict):
            continue
        status = str(item.get("status") or "").strip()
        if status in counts:
            counts[status] = int(counts[status] or 0) + 1
    return counts


def _sanitize_graph_machine_result(value: Any) -> Any:
    private_keys = {
        "raw_history",
        "history_transcript",
        "reasoning_content",
        "private_memory",
        "conversation_history",
        "full_history",
        "scratchpad",
    }
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            clean_key = str(key or "").strip()
            if clean_key in private_keys:
                continue
            sanitized[clean_key] = _sanitize_graph_machine_result(item)
        return sanitized
    if isinstance(value, list):
        return [_sanitize_graph_machine_result(item) for item in value]
    return value


class TaskService:
    """User-facing task state over internal provider-specific Codex threads.

    A task is what the user perceives as one conversation or objective. Each
    task may use multiple internal Codex threads, one per provider/model route.
    Provider switching should therefore preserve the task and only change the
    active provider thread.
    """

    def __init__(self, project_service) -> None:
        self._projects = project_service
        self._durable_store: DurableRunEventStore | None = None
        self._durable_store_workspace: Path | None = None

    def durable_run_store(self) -> DurableRunEventStore:
        """Return the workspace-local durable run store for this service.

        The store is initialized lazily so ordinary task-list reads keep their
        existing lightweight path.  A workspace switch closes the old logical
        owner before opening the new store; SQLite connections themselves are
        short-lived and never cross request lifetimes.
        """

        workspace = Path(self._projects.require_workspace_root()).expanduser().resolve()
        if self._durable_store is not None and self._durable_store_workspace == workspace:
            return self._durable_store
        if self._durable_store is not None:
            self._durable_store.close()
        store = DurableRunEventStore(workspace)
        store.initialize()
        store.migrate_legacy_state()
        self._durable_store = store
        self._durable_store_workspace = workspace
        return store

    def snapshot(self) -> dict[str, Any]:
        state = self._state()
        current = self._current_task_response_view(state=state)
        return {
            "schema_version": TASK_STATE_SCHEMA_VERSION,
            # This endpoint is polled by the shell. Full graph runs can contain
            # large artifact payloads, so callers load their detail through the
            # dedicated graph/run endpoints instead of repeatedly transferring it.
            "current_task": current,
            "tasks": [
                self.task_list_item(task)
                for task in list(state.get("tasks") or [])
                if isinstance(task, dict)
            ],
            "updated_at": state.get("updated_at"),
        }

    def task_list_item(self, task: dict[str, Any]) -> dict[str, Any]:
        """Return navigation metadata without duplicating task or graph payloads."""
        graph_summary = self._graph_activity_summary(task)
        provider_threads = [item for item in list(task.get("provider_threads") or []) if isinstance(item, dict)]
        return {
            "schema_version": str(task.get("schema_version") or TASK_STATE_SCHEMA_VERSION),
            "task_id": str(task.get("task_id") or "").strip(),
            "project_id": str(task.get("project_id") or "").strip(),
            "title": _display_task_title(task.get("title")) or "New task",
            "status": str(task.get("status") or "").strip(),
            "created_at": str(task.get("created_at") or "").strip(),
            "updated_at": str(task.get("updated_at") or "").strip(),
            "active_provider_thread_id": str(task.get("active_provider_thread_id") or "").strip() or None,
            "lane_state": {
                "lane_count": len(provider_threads),
                "handoff_count": len([item for item in list(task.get("handoff_events") or []) if isinstance(item, dict)]),
            },
            "graph_activity_summary": graph_summary,
        }

    def task_view(
        self,
        task: dict[str, Any] | None = None,
        *,
        compact_graph_runs: bool = False,
        compact_graph_details: bool = False,
    ) -> dict[str, Any] | None:
        current = dict(task) if isinstance(task, dict) else self.current_task()
        if not isinstance(current, dict):
            return None
        current["title"] = _display_task_title(current.get("title")) or "New task"
        current["lane_state"] = self.lane_state(task=current)
        current["graph_activity_summary"] = self._graph_activity_summary(current)
        if compact_graph_runs:
            current["graph_run_refs"] = self._task_response_graph_run_refs(current.get("graph_run_refs"))
        if compact_graph_details:
            current["graph_definitions"] = self._task_response_graph_definition_refs(current.get("graph_definitions"))
            current["graph_snapshot_refs"] = self._task_response_graph_snapshot_refs(current.get("graph_snapshot_refs"))
            current["handoff_events"] = [
                self.compact_handoff_event(item)
                for item in list(current.get("handoff_events") or [])
                if isinstance(item, dict)
            ][-12:]
        return current

    def _task_response_graph_run_refs(self, value: Any) -> list[dict[str, Any]]:
        compacted: list[dict[str, Any]] = []
        for item in list(value or []):
            if not isinstance(item, dict):
                continue
            compact_ref = {
                    "run_id": str(item.get("run_id") or "").strip(),
                    "graph_id": str(item.get("graph_id") or "").strip(),
                    "task_id": str(item.get("task_id") or "").strip(),
                    "status": str(item.get("status") or "").strip(),
                    "created_at": str(item.get("created_at") or "").strip(),
                    "updated_at": str(item.get("updated_at") or "").strip(),
                    "artifact_count": int(item.get("artifact_count") or 0),
                    "event_count": int(item.get("event_count") or 0),
                    "worker_count": int(item.get("worker_count") or 0),
                    "approval_state": str(item.get("approval_state") or "").strip() or None,
                    "latest_event_type": str(item.get("latest_event_type") or "").strip() or None,
                    "latest_event_at": str(item.get("latest_event_at") or "").strip() or None,
                    "node_status_counts": {
                        str(key): int(count or 0)
                        for key, count in dict(item.get("node_status_counts") or {}).items()
                        if str(key or "").strip()
                    },
                    "node_outcome_counts": {
                        str(key): int(count or 0)
                        for key, count in dict(item.get("node_outcome_counts") or {}).items()
                        if str(key or "").strip()
                    },
                    "metrics": redact_sensitive(dict(item.get("metrics") or {})),
                    "budget": redact_sensitive(dict(item.get("budget") or {})),
                }
            # Keep active-run payloads compact, but preserve sanitized worker
            # output after a run reaches a terminal state so the UI can show
            # truthful per-node results instead of only aggregate counts.
            status = str(item.get("status") or "").strip()
            if status in {"completed", "failed", "cancelled", "partial", "dry_run_passed", "dry_run_blocked"}:
                worker_bindings = [
                    redact_sensitive(dict(binding))
                    for binding in list(item.get("worker_bindings") or [])
                    if isinstance(binding, dict)
                ]
                if worker_bindings:
                    compact_ref["worker_bindings"] = worker_bindings[:80]
            compacted.append(compact_ref)
        return compacted[:12]

    def _task_response_graph_definition_refs(self, value: Any) -> list[dict[str, Any]]:
        compacted: list[dict[str, Any]] = []
        for item in list(value or []):
            if not isinstance(item, dict):
                continue
            graph_policy = dict(item.get("graph_policy") or {})
            compacted.append(
                {
                    "graph_id": str(item.get("graph_id") or "").strip(),
                    "task_id": str(item.get("task_id") or "").strip(),
                    "title": str(item.get("title") or "").strip(),
                    "template_id": str(item.get("template_id") or "").strip(),
                    "status": str(item.get("status") or "").strip(),
                    "state_version": int(item.get("state_version") or 0),
                    "node_count": len(list(item.get("nodes") or [])),
                    "edge_count": len(list(item.get("edges") or [])),
                    "graph_policy": {"entry_node_ids": list(graph_policy.get("entry_node_ids") or [])[:12]},
                    "created_at": str(item.get("created_at") or "").strip(),
                    "updated_at": str(item.get("updated_at") or "").strip(),
                }
            )
        return compacted[:20]

    def _task_response_graph_snapshot_refs(self, value: Any) -> list[dict[str, Any]]:
        compacted: list[dict[str, Any]] = []
        for item in list(value or []):
            if not isinstance(item, dict):
                continue
            compacted.append(
                {
                    "snapshot_id": str(item.get("snapshot_id") or "").strip(),
                    "graph_id": str(item.get("graph_id") or "").strip(),
                    "task_id": str(item.get("task_id") or "").strip(),
                    "run_id": str(item.get("run_id") or "").strip(),
                    "status": str(item.get("status") or "").strip(),
                    "label": str(item.get("label") or "").strip(),
                    "description": str(item.get("description") or "").strip(),
                    "created_at": str(item.get("created_at") or "").strip(),
                    "updated_at": str(item.get("updated_at") or "").strip(),
                }
            )
        return compacted[:24]

    def ensure_default_task(self, *, thread_id: str | None = None, title: str | None = None, settings: dict[str, Any] | None = None) -> dict[str, Any]:
        project = self._project()
        state = self._state()
        tasks = list(state.get("tasks") or [])
        current_task_id = self._resolved_current_task_id(state=state, project=project)
        task = self._find_task(tasks, current_task_id)
        if not task:
            task = self._new_task(title or project.get("name") or "New task")
            tasks.insert(0, task)
            current_task_id = str(task["task_id"])
        if thread_id:
            task = self._bind_thread_to_task(task, thread_id=thread_id, settings=settings or {}, role="provider", make_active=True)
        updated_tasks = self._replace_task(tasks, task)
        updated_tasks = self._enforce_task_thread_ownership(updated_tasks, owner_task=task)
        task = self._find_task(updated_tasks, str(task.get("task_id") or "")) or task
        state["tasks"] = updated_tasks
        state["current_task_id"] = current_task_id
        state["updated_at"] = now_iso()
        self._write_state(state)
        self._sync_project_current_task(task)
        return task

    def create_task(self, title: str | None = None, *, thread_id: str | None = None, settings: dict[str, Any] | None = None) -> dict[str, Any]:
        task = self._new_task(title or "New task")
        if thread_id:
            task = self._bind_thread_to_task(task, thread_id=thread_id, settings=settings or {}, role="provider", make_active=True)
        state = self._state()
        tasks = [item for item in list(state.get("tasks") or []) if item.get("task_id") != task.get("task_id")]
        tasks.insert(0, task)
        tasks = self._enforce_task_thread_ownership(tasks[:100], owner_task=task)
        task = self._find_task(tasks, str(task.get("task_id") or "")) or task
        state["tasks"] = tasks
        state["current_task_id"] = task["task_id"]
        state["updated_at"] = now_iso()
        self._write_state(state)
        self._sync_project_current_task(task)
        return task

    def switch_task(self, task_id: str) -> dict[str, Any]:
        state = self._state()
        tasks = list(state.get("tasks") or [])
        task = self._find_task(tasks, task_id)
        if not task:
            raise ValueError("Task not found.")
        task["updated_at"] = now_iso()
        state["tasks"] = self._replace_task(tasks, task)
        state["current_task_id"] = task["task_id"]
        state["updated_at"] = now_iso()
        self._write_state(state)
        self._sync_project_current_task(task)
        return self._current_task_response_view(state=state) or self.task_view(task, compact_graph_runs=True, compact_graph_details=True) or task

    def update_current_task_title(self, title: str) -> dict[str, Any]:
        task = self.current_task()
        if not task:
            raise ValueError("No current task.")
        clean_title = str(title or "").strip()
        if not clean_title:
            raise ValueError("Task title cannot be empty.")
        redacted_title = str(redact_sensitive(clean_title)).strip()
        if SECRET_RE.search(redacted_title):
            raise SecurityError("Secret-like content is not allowed in task titles.")
        task["title"] = redacted_title[:160]
        task["updated_at"] = now_iso()
        self._save_task(task)
        return task

    def current_task(self) -> dict[str, Any] | None:
        project = self._project()
        state = self._state()
        task_id = self._resolved_current_task_id(state=state, project=project)
        task = self._find_task(list(state.get("tasks") or []), task_id)
        if task:
            normalized_task, changed = self._normalize_task(task)
            if changed:
                state["tasks"] = self._replace_task(list(state.get("tasks") or []), normalized_task)
                state["current_task_id"] = normalized_task["task_id"]
                state["updated_at"] = now_iso()
                self._write_state(state)
                self._sync_project_current_task(normalized_task)
            elif self._project_sync_needed(normalized_task):
                self._sync_project_current_task(normalized_task)
            return normalized_task
        return None

    def _raw_current_task_from_state(self, *, state: dict[str, Any] | None = None) -> dict[str, Any] | None:
        current_state = state if isinstance(state, dict) else self._state()
        project = self._project()
        task_id = self._resolved_current_task_id(state=current_state, project=project)
        task = self._find_task(list(current_state.get("tasks") or []), task_id)
        return dict(task) if isinstance(task, dict) else None

    def _current_task_response_view(self, *, state: dict[str, Any] | None = None) -> dict[str, Any] | None:
        raw_task = self._raw_current_task_from_state(state=state)
        if raw_task:
            return self.task_view(raw_task, compact_graph_runs=True, compact_graph_details=True)
        current = self.current_task()
        if not current:
            return None
        return self.task_view(current, compact_graph_runs=True, compact_graph_details=True)

    def reconcile_after_project_reload(self, *, preferred_thread_id: str | None = None) -> dict[str, Any] | None:
        """Re-anchor task pointers after project reopen or checkpoint restore."""
        state = self._state()
        tasks = [dict(item) for item in list(state.get("tasks") or []) if isinstance(item, dict)]
        if not tasks:
            return None
        normalized_tasks: list[dict[str, Any]] = []
        changed = False
        for item in tasks:
            normalized, item_changed = self._normalize_task(item)
            normalized_tasks.append(normalized)
            changed = changed or item_changed or normalized != item
        project = self._project()
        selected = self._select_reloaded_task(
            normalized_tasks,
            current_task_id=self._resolved_current_task_id(state=state, project=project),
            preferred_thread_id=str(preferred_thread_id or project.get("current_thread_id") or "").strip(),
        )
        if not selected:
            return None
        selected_id = str(selected.get("task_id") or "").strip()
        if str(state.get("current_task_id") or "") != selected_id:
            state["current_task_id"] = selected_id
            changed = True
        if normalized_tasks != list(state.get("tasks") or []):
            state["tasks"] = normalized_tasks
            changed = True
        if changed:
            state["updated_at"] = now_iso()
            self._write_state(state)
        if self._project_sync_needed(selected):
            self._sync_project_current_task(selected)
        return selected

    def bind_thread(
        self,
        *,
        thread_id: str,
        settings: dict[str, Any] | None = None,
        role: str = "provider",
        title: str | None = None,
        make_active: bool = True,
    ) -> dict[str, Any]:
        task = self.ensure_default_task(title=title, settings=settings)
        task = self._bind_thread_to_task(task, thread_id=thread_id, settings=settings or {}, role=role, make_active=make_active)
        state = self._state()
        updated_tasks = self._replace_task(list(state.get("tasks") or []), task)
        updated_tasks = self._enforce_task_thread_ownership(updated_tasks, owner_task=task)
        task = self._find_task(updated_tasks, str(task.get("task_id") or "")) or task
        state["tasks"] = updated_tasks
        state["current_task_id"] = task["task_id"]
        state["updated_at"] = now_iso()
        self._write_state(state)
        self._sync_project_current_task(task)
        return task

    def bind_thread_to_task_id(
        self,
        *,
        task_id: str,
        thread_id: str,
        settings: dict[str, Any] | None = None,
        role: str = "provider",
        make_active: bool = True,
    ) -> dict[str, Any]:
        """Bind a runtime thread to the task selected before first-turn bootstrap."""
        clean_task_id = str(task_id or "").strip()
        if not clean_task_id:
            raise ValueError("task_id is required.")
        state = self._state()
        tasks = list(state.get("tasks") or [])
        task = self._find_task(tasks, clean_task_id)
        if not task:
            raise ValueError("Task not found.")
        task = self._bind_thread_to_task(
            task,
            thread_id=thread_id,
            settings=settings or {},
            role=role,
            make_active=make_active,
        )
        updated_tasks = self._replace_task(tasks, task)
        updated_tasks = self._enforce_task_thread_ownership(updated_tasks, owner_task=task)
        task = self._find_task(updated_tasks, clean_task_id) or task
        state["tasks"] = updated_tasks
        state["current_task_id"] = clean_task_id
        state["updated_at"] = now_iso()
        self._write_state(state)
        self._sync_project_current_task(task)
        return task

    def find_provider_thread(
        self,
        *,
        profile_id: str | None,
        provider_id: str | None = None,
        model: str | None,
        effort: str | None,
    ) -> dict[str, Any] | None:
        task = self.current_task()
        if not task:
            return None
        desired_profile = str(profile_id or "")
        desired_provider = str(provider_id or "").strip().lower()
        desired_model = _canonical_model_key(model)
        desired_effort = _canonical_effort_key(effort)
        matches: list[dict[str, Any]] = []
        for item in list(task.get("provider_threads") or []):
            if item.get("missing_at"):
                continue
            if not _provider_thread_entry_is_plausible(item):
                continue
            item_profile = str(item.get("profile_id") or "")
            item_provider = str(item.get("provider_id") or "").strip().lower()
            if desired_profile and item_profile != desired_profile:
                if not desired_provider or item_provider != desired_provider:
                    continue
            elif not desired_profile and desired_provider and item_provider != desired_provider:
                continue
            if desired_model and _canonical_model_key(item.get("model")) != desired_model:
                continue
            if desired_effort and _canonical_effort_key(item.get("reasoning_effort")) != desired_effort:
                continue
            matches.append(dict(item))
        if not matches:
            return None
        matches.sort(key=lambda item: str(item.get("updated_at") or ""), reverse=True)
        return matches[0]

    def active_provider_thread(self, *, include_missing_fallback: bool = False) -> dict[str, Any] | None:
        task = self.current_task()
        if not task:
            return None
        active_thread_id = str(task.get("active_provider_thread_id") or "")
        provider_threads = [dict(item) for item in list(task.get("provider_threads") or [])]
        for item in provider_threads:
            if (
                str(item.get("thread_id") or "") == active_thread_id
                and not item.get("missing_at")
                and _provider_thread_entry_is_plausible(item)
            ):
                return dict(item)
        if not include_missing_fallback:
            return None
        project_thread_id = str((self._projects.current_project or {}).get("current_thread_id") or "").strip()
        if project_thread_id:
            for item in provider_threads:
                if str(item.get("thread_id") or "") == project_thread_id:
                    return dict(item)
        live_threads = [
            item for item in provider_threads if not item.get("missing_at") and _provider_thread_entry_is_plausible(item)
        ]
        if live_threads:
            live_threads.sort(key=lambda item: str(item.get("updated_at") or ""), reverse=True)
            return dict(live_threads[0])
        if provider_threads:
            provider_threads.sort(key=lambda item: str(item.get("updated_at") or ""), reverse=True)
            return dict(provider_threads[0])
        return None

    def visible_provider_thread_id(self, *, include_missing_fallback: bool = False) -> str:
        """Return the best secret-free visible provider thread hint for the current task."""
        task = self.current_task()
        if not task:
            return ""
        active_thread_id = str(task.get("active_provider_thread_id") or "").strip()
        if active_thread_id:
            return active_thread_id
        fallback = self.active_provider_thread(include_missing_fallback=include_missing_fallback)
        return str((fallback or {}).get("thread_id") or "").strip()

    def restore_active_provider_thread(self, thread_id: str) -> dict[str, Any] | None:
        """Restore UI focus without mutating thread metadata or missing diagnostics."""
        clean_thread_id = str(thread_id or "").strip()
        if not clean_thread_id:
            return self.current_task()
        state = self._state()
        tasks = [dict(item) for item in list(state.get("tasks") or []) if isinstance(item, dict)]
        task = self._find_task_for_thread(tasks, clean_thread_id)
        if not task:
            task_id = str(self._project().get("current_task_id") or state.get("current_task_id") or "")
            task = self._find_task(tasks, task_id) or self.current_task()
        if not task:
            return None
        task["active_provider_thread_id"] = clean_thread_id
        task["updated_at"] = now_iso()
        updated_tasks = self._replace_task(tasks, task)
        updated_tasks = self._enforce_task_thread_ownership(updated_tasks, owner_task=task)
        task = self._find_task(updated_tasks, str(task.get("task_id") or "")) or task
        state["tasks"] = updated_tasks
        state["current_task_id"] = task["task_id"]
        state["updated_at"] = now_iso()
        self._write_state(state)
        self._sync_project_current_task(task)
        return task

    def force_visible_provider_thread(self, thread_id: str) -> dict[str, Any] | None:
        """Force the visible task/project pointers onto a known provider thread.

        This is intentionally stronger than restore_active_provider_thread() and is
        only meant for supervisor-style actions such as direct MCP tool calls,
        where we want to preserve the user's visible task continuity even if the
        source provider thread has been marked missing in the runtime.
        """
        clean_thread_id = str(thread_id or "").strip()
        if not clean_thread_id:
            return self.current_task()
        project = self._project()
        state = self._state()
        task_id = self._resolved_current_task_id(state=state, project=project)
        task = self._find_task(list(state.get("tasks") or []), task_id)
        if not task:
            return None
        task["active_provider_thread_id"] = clean_thread_id
        task["updated_at"] = now_iso()
        state["tasks"] = self._replace_task(list(state.get("tasks") or []), task)
        state["current_task_id"] = task["task_id"]
        state["updated_at"] = now_iso()
        self._write_state(state)
        self._sync_project_current_task(task)
        return task

    def needs_provider_handoff(self, *, thread_id: str | None, profile_id: str | None, model: str | None, effort: str | None) -> bool:
        if not thread_id:
            return False
        task = self.ensure_default_task(thread_id=thread_id)
        current = None
        for item in list(task.get("provider_threads") or []):
            if str(item.get("thread_id") or "") == str(thread_id):
                current = item
                break
        if not current:
            return False
        if not current.get("profile_id") and not current.get("model") and not current.get("reasoning_effort"):
            return False
        if profile_id and str(current.get("profile_id") or "") != str(profile_id):
            return True
        if model and _canonical_model_key(current.get("model")) != _canonical_model_key(model):
            return True
        if effort and _canonical_effort_key(current.get("reasoning_effort")) != _canonical_effort_key(effort):
            return True
        return False

    def record_provider_handoff(
        self,
        *,
        from_thread_id: str | None,
        to_thread_id: str,
        settings: dict[str, Any],
        reused_existing: bool,
        context_budget_report: dict[str, Any] | None = None,
        dropped_artifacts: int = 0,
        repaired_tool_pairs: int = 0,
        replayable_artifact_count: int = 0,
        projection_preview: str | None = None,
        warnings: list[str] | None = None,
    ) -> dict[str, Any]:
        task = self.bind_thread(thread_id=to_thread_id, settings=settings, role="provider", make_active=True)
        source_settings = self._provider_thread_settings(task, from_thread_id)
        transition = summarize_transition(
            from_provider=str((source_settings or {}).get("provider_id") or "") or None,
            to_provider=str(settings.get("provider_id") or "openai"),
            to_model=str(settings.get("model") or "") or None,
            dropped_artifacts=dropped_artifacts,
            repaired_tool_pairs=repaired_tool_pairs,
            replayable_artifact_count=replayable_artifact_count,
            projection_preview=projection_preview,
            warnings=warnings,
            projection_mode="reused_provider_thread" if reused_existing else "task_context_fresh_thread",
            reasoning_effort=str(settings.get("reasoning_effort") or "") or None,
            context_budget_report=context_budget_report,
        )
        event = {
            "event_id": new_id("handoff"),
            "type": "provider_handoff",
            "handoff_policy": DEFAULT_HANDOFF_POLICY,
            "from_thread_id": from_thread_id,
            "from_profile_id": (source_settings or {}).get("profile_id"),
            "from_provider_id": (source_settings or {}).get("provider_id"),
            "from_model": _display_model_id((source_settings or {}).get("model")),
            "from_reasoning_effort": _display_effort(
                (source_settings or {}).get("reasoning_effort"),
                (source_settings or {}).get("provider_id"),
            ),
            "from_permission_mode": (source_settings or {}).get("permission_mode"),
            "to_thread_id": to_thread_id,
            "profile_id": settings.get("profile_id"),
            "provider_id": settings.get("provider_id"),
            "model": settings.get("model"),
            "reasoning_effort": settings.get("reasoning_effort"),
            "permission_mode": settings.get("permission_mode"),
            "reused_existing": reused_existing,
            "transition_summary": transition.to_dict(),
            "created_at": now_iso(),
        }
        handoff_events = list(task.get("handoff_events") or [])
        handoff_events.append(event)
        task["handoff_events"] = handoff_events[-80:]
        task["updated_at"] = now_iso()
        state = self._state()
        state["tasks"] = self._replace_task(list(state.get("tasks") or []), task)
        state["current_task_id"] = task["task_id"]
        state["updated_at"] = now_iso()
        self._write_state(state)
        self._sync_project_current_task(task)
        return event

    def compact_handoff_event(self, event: dict[str, Any]) -> dict[str, Any]:
        transition = dict(event.get("transition_summary") or {})
        warnings = [str(item).strip() for item in list(transition.get("warnings") or []) if str(item or "").strip()]
        return {
            "event_id": str(event.get("event_id") or ""),
            "type": str(event.get("type") or ""),
            "handoff_policy": str(event.get("handoff_policy") or ""),
            "from_thread_id": str(event.get("from_thread_id") or ""),
            "from_profile_id": str(event.get("from_profile_id") or ""),
            "from_provider_id": str(event.get("from_provider_id") or ""),
            "from_model": str(event.get("from_model") or ""),
            "from_reasoning_effort": str(event.get("from_reasoning_effort") or ""),
            "from_permission_mode": str(event.get("from_permission_mode") or ""),
            "to_thread_id": str(event.get("to_thread_id") or ""),
            "profile_id": str(event.get("profile_id") or ""),
            "provider_id": str(event.get("provider_id") or ""),
            "model": str(event.get("model") or ""),
            "reasoning_effort": str(event.get("reasoning_effort") or ""),
            "permission_mode": str(event.get("permission_mode") or ""),
            "reused_existing": bool(event.get("reused_existing")),
            "created_at": str(event.get("created_at") or ""),
            "transition_summary": {
                "from_provider": str(transition.get("from_provider") or ""),
                "to_provider": str(transition.get("to_provider") or ""),
                "to_model": str(transition.get("to_model") or ""),
                "projection_mode": str(transition.get("projection_mode") or ""),
                "dropped_artifacts": int(transition.get("dropped_artifacts") or 0),
                "repaired_tool_pairs": int(transition.get("repaired_tool_pairs") or 0),
                "replayable_artifact_count": int(transition.get("replayable_artifact_count") or 0),
                "projection_preview": str(transition.get("projection_preview") or ""),
                "warnings": warnings,
                "warning_count": len(warnings),
            },
        }

    def lane_state(self, task: dict[str, Any] | None = None) -> dict[str, Any]:
        current = dict(task) if isinstance(task, dict) else self.current_task()
        if not isinstance(current, dict):
            return {
                "lane_count": 0,
                "handoff_count": 0,
                "active_lane": None,
                "previous_lane": None,
                "latest_handoff": None,
            }
        provider_threads = [dict(item) for item in list(current.get("provider_threads") or []) if isinstance(item, dict)]
        by_thread_id = {
            str(item.get("thread_id") or "").strip(): item
            for item in provider_threads
            if str(item.get("thread_id") or "").strip()
        }
        active_thread_id = str(current.get("active_provider_thread_id") or "").strip()
        handoff_events = [dict(item) for item in list(current.get("handoff_events") or []) if isinstance(item, dict)]
        latest_handoff = handoff_events[-1] if handoff_events else None
        active_lane = _lane_view(by_thread_id.get(active_thread_id))
        if active_lane is None and active_thread_id:
            active_lane = _lane_view({"thread_id": active_thread_id})
        previous_handoff = next(
            (
                event
                for event in reversed(handoff_events)
                if str(event.get("to_thread_id") or "").strip() == active_thread_id
            ),
            latest_handoff,
        )
        previous_thread_id = str((previous_handoff or {}).get("from_thread_id") or "").strip()
        previous_lane = _lane_view(by_thread_id.get(previous_thread_id))
        if previous_lane is None:
            previous_lane = _lane_view_from_handoff_event(previous_handoff, source=True)
        compact_handoff = self.compact_handoff_event(previous_handoff) if isinstance(previous_handoff, dict) else None
        return {
            "lane_count": len(provider_threads),
            "handoff_count": len(handoff_events),
            "active_lane": active_lane,
            "previous_lane": previous_lane,
            "latest_handoff": compact_handoff,
        }

    def _provider_thread_settings(self, task: dict[str, Any] | None, thread_id: str | None) -> dict[str, Any] | None:
        clean_thread_id = str(thread_id or "").strip()
        if not clean_thread_id or not isinstance(task, dict):
            return None
        for item in list(task.get("provider_threads") or []):
            if str(item.get("thread_id") or "") == clean_thread_id:
                return dict(item)
        return None

    def mark_provider_thread_missing(self, thread_id: str, *, reason: str | None = None) -> None:
        clean_thread_id = str(thread_id or "").strip()
        if not clean_thread_id:
            return
        task = self.current_task()
        if not task:
            return
        updated = False
        provider_threads: list[dict[str, Any]] = []
        for item in list(task.get("provider_threads") or []):
            entry = dict(item)
            if str(entry.get("thread_id") or "") == clean_thread_id:
                entry["missing_at"] = now_iso()
                entry["missing_reason"] = str(reason or "app_server_thread_not_found")
                updated = True
            provider_threads.append(entry)
        if not updated:
            return
        task["provider_threads"] = self._prune_provider_threads(provider_threads)
        if str(task.get("active_provider_thread_id") or "") == clean_thread_id:
            task["active_provider_thread_id"] = None
        task["updated_at"] = now_iso()
        self._save_task(task)

    def record_goal(self, thread_id: str, goal: Any) -> None:
        task = self.ensure_default_task(thread_id=thread_id)
        task["goal"] = redact_sensitive(goal)
        task["updated_at"] = now_iso()
        self._save_task(task)

    def record_plan(self, thread_id: str, plan: dict[str, Any]) -> None:
        task = self.ensure_default_task(thread_id=thread_id)
        task["plan"] = redact_sensitive(plan)
        task["updated_at"] = now_iso()
        self._save_task(task)

    def record_checkpoint(self, checkpoint: dict[str, Any]) -> None:
        task = self.current_task()
        if not task:
            return
        refs = list(task.get("checkpoint_refs") or [])
        refs.insert(
            0,
            {
                "save_id": checkpoint.get("save_id"),
                "description": checkpoint.get("description") or checkpoint.get("default_description"),
                "created_at": checkpoint.get("created_at") or now_iso(),
            },
        )
        task["checkpoint_refs"] = refs[:40]
        task["updated_at"] = now_iso()
        self._save_task(task)

    def record_coding_events(self, events: list[dict[str, Any]] | None) -> None:
        task = self.current_task()
        if not task:
            return
        refs = task_refs_from_coding_events(events)
        checkpoint_refs = [
            *list(refs.get("checkpoint_refs") or []),
            *list(task.get("checkpoint_refs") or []),
        ]
        verification_refs = [
            *list(refs.get("verification_refs") or []),
            *list(task.get("verification_refs") or []),
        ]
        diagnostic_refs = [
            *list(refs.get("diagnostic_refs") or []),
            *list(task.get("diagnostic_refs") or []),
        ]
        task["checkpoint_refs"] = self._dedupe_records(checkpoint_refs, key_fields=("save_id",), limit=40)
        task["verification_refs"] = self._dedupe_records(verification_refs, key_fields=("event_id",), limit=40)
        task["diagnostic_refs"] = self._dedupe_records(diagnostic_refs, key_fields=("event_id",), limit=40)
        task["updated_at"] = now_iso()
        self._save_task(task)

    def record_context_ref(self, *, pack_type: str, path: str, generated_at: str, summary: dict[str, Any] | None = None) -> None:
        task = self.current_task()
        if not task:
            return
        ref = {
            "pack_type": str(pack_type or "").strip() or "context",
            "path": str(path or "").strip(),
            "generated_at": str(generated_at or "").strip() or now_iso(),
            "summary": dict(summary or {}),
        }
        refs = [item for item in list(task.get("context_pack_refs") or []) if not self._same_context_ref(item, ref)]
        refs.insert(0, ref)
        task["context_pack_refs"] = refs[:20]
        if ref["pack_type"] == "asset":
            asset_refs = [item for item in list(task.get("asset_context_refs") or []) if not self._same_context_ref(item, ref)]
            asset_refs.insert(0, ref)
            task["asset_context_refs"] = asset_refs[:10]
        task["updated_at"] = now_iso()
        self._save_task(task)

    def upsert_graph_definition(self, graph_definition: dict[str, Any]) -> dict[str, Any]:
        task = self.current_task()
        if not task:
            raise ValueError("No current task.")
        validated = validate_graph_definition(graph_definition)
        if str(validated.get("task_id") or "") != str(task.get("task_id") or ""):
            raise ValueError("graph_definition.task_id must match the current task.")
        existing = [
            dict(item)
            for item in list(task.get("graph_definitions") or [])
            if isinstance(item, dict) and str(item.get("graph_id") or "").strip() != str(validated.get("graph_id") or "").strip()
        ]
        task["graph_definitions"] = [validated, *existing][:GRAPH_DEFINITION_LIMIT]
        task["graph_activity_summary"] = self._graph_activity_summary(task)
        task["updated_at"] = now_iso()
        self._save_task(task)
        return validated

    def graph_definition(self, graph_id: str | None = None) -> dict[str, Any] | None:
        task = self.current_task()
        if not task:
            return None
        graph_definitions = [dict(item) for item in list(task.get("graph_definitions") or []) if isinstance(item, dict)]
        if graph_id:
            for item in graph_definitions:
                if str(item.get("graph_id") or "").strip() == str(graph_id or "").strip():
                    return item
            return None
        return graph_definitions[0] if graph_definitions else None

    def graph_snapshot_ref(self, snapshot_id: str | None = None) -> dict[str, Any] | None:
        task = self.current_task()
        if not task:
            return None
        snapshot_refs = [dict(item) for item in list(task.get("graph_snapshot_refs") or []) if isinstance(item, dict)]
        if snapshot_id:
            clean_snapshot_id = str(snapshot_id or "").strip()
            for item in snapshot_refs:
                if str(item.get("snapshot_id") or "").strip() == clean_snapshot_id:
                    return item
            return None
        return snapshot_refs[0] if snapshot_refs else None

    def _snapshot_workspace_root(self) -> Path:
        return self._projects.require_workspace_root() / WORKSPACE_STATE_DIRNAME / "task-graph" / "snapshots"

    def _snapshot_root_for(self, *, task_id: str, graph_id: str, snapshot_id: str) -> Path:
        return self._snapshot_workspace_root() / str(task_id or "").strip() / str(graph_id or "").strip() / str(snapshot_id or "").strip()

    def _compact_graph_snapshot_ref(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        compact = {
            "snapshot_id": str(snapshot.get("snapshot_id") or "").strip(),
            "task_id": str(snapshot.get("task_id") or "").strip(),
            "graph_id": str(snapshot.get("graph_id") or "").strip(),
            "project_id": str(snapshot.get("project_id") or "").strip() or None,
            "label": str(snapshot.get("label") or "").strip() or None,
            "reason": str(snapshot.get("reason") or "").strip() or None,
            "source_action": str(snapshot.get("source_action") or "").strip() or None,
            "state_version": int(snapshot.get("state_version") or 0),
            "based_on_snapshot_id": str(snapshot.get("based_on_snapshot_id") or "").strip() or None,
            "rollback_source_snapshot_id": str(snapshot.get("rollback_source_snapshot_id") or "").strip() or None,
            "created_at": str(snapshot.get("created_at") or "").strip(),
            "updated_at": str(snapshot.get("updated_at") or "").strip(),
            "artifact_paths": redact_sensitive(dict(snapshot.get("artifact_paths") or {})),
            "summary": redact_sensitive(dict(snapshot.get("summary") or {})),
        }
        comparison = snapshot.get("comparison")
        if isinstance(comparison, dict):
            compact["comparison"] = redact_sensitive(dict(comparison))
        return compact

    def _prune_graph_snapshot_refs(self, records: list[Any], *, task_id: str) -> list[dict[str, Any]]:
        seen: set[str] = set()
        pruned: list[dict[str, Any]] = []
        workspace_root = self._projects.require_workspace_root().resolve()
        for item in records:
            if not isinstance(item, dict):
                continue
            snapshot_id = str(item.get("snapshot_id") or "").strip()
            graph_id = str(item.get("graph_id") or "").strip()
            item_task_id = str(item.get("task_id") or "").strip()
            if not snapshot_id or not graph_id or not item_task_id:
                continue
            if task_id and item_task_id != task_id:
                continue
            if snapshot_id in seen:
                continue
            artifact_paths = item.get("artifact_paths")
            if not isinstance(artifact_paths, dict):
                continue
            try:
                normalized_artifact_paths = {
                    key: str(resolve_under(workspace_root, value).relative_to(workspace_root).as_posix())
                    for key, value in artifact_paths.items()
                    if isinstance(value, str) and str(value).strip()
                }
            except SecurityError:
                continue
            compact = {
                "snapshot_id": snapshot_id,
                "task_id": item_task_id,
                "graph_id": graph_id,
                "project_id": str(item.get("project_id") or "").strip() or None,
                "label": str(item.get("label") or "").strip() or None,
                "reason": str(item.get("reason") or "").strip() or None,
                "source_action": str(item.get("source_action") or "").strip() or None,
                "state_version": int(item.get("state_version") or 0),
                "based_on_snapshot_id": str(item.get("based_on_snapshot_id") or "").strip() or None,
                "rollback_source_snapshot_id": str(item.get("rollback_source_snapshot_id") or "").strip() or None,
                "created_at": str(item.get("created_at") or "").strip(),
                "updated_at": str(item.get("updated_at") or "").strip(),
                "artifact_paths": normalized_artifact_paths,
                "summary": dict(item.get("summary") or {}),
            }
            comparison = item.get("comparison")
            if isinstance(comparison, dict):
                compact["comparison"] = dict(comparison)
            seen.add(snapshot_id)
            pruned.append(compact)
        return pruned[:GRAPH_SNAPSHOT_REF_LIMIT]

    def _persist_graph_snapshot_ref(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        task = self.current_task()
        if not task:
            raise ValueError("No current task.")
        compact_ref = self._compact_graph_snapshot_ref(snapshot)
        existing = [
            dict(item)
            for item in list(task.get("graph_snapshot_refs") or [])
            if isinstance(item, dict) and str(item.get("snapshot_id") or "").strip() != str(compact_ref.get("snapshot_id") or "").strip()
        ]
        task["graph_snapshot_refs"] = [compact_ref, *existing][:GRAPH_SNAPSHOT_REF_LIMIT]
        task["updated_at"] = now_iso()
        self._save_task(task)
        return compact_ref

    def _snapshot_workspace_root_candidates(
        self,
        *,
        task: dict[str, Any] | None,
        snapshot: dict[str, Any] | None = None,
    ) -> list[Path]:
        candidates: list[Path] = []
        seen: set[str] = set()

        def add(raw_root: Any) -> None:
            text = str(raw_root or "").strip()
            if not text:
                return
            resolved = Path(text).expanduser().resolve()
            key = str(resolved).lower()
            if key in seen:
                return
            seen.add(key)
            candidates.append(resolved)

        current_project = self._projects.current_project or {}
        add(current_project.get("workspace_root"))
        if isinstance(snapshot, dict):
            add(snapshot.get("workspace_root"))
        if isinstance(task, dict):
            add(task.get("workspace_root"))

        desired_project_ids = {
            str(source.get("project_id") or "").strip()
            for source in (snapshot or {}, task or {})
            if isinstance(source, dict) and str(source.get("project_id") or "").strip()
        }
        for item in list(self._projects.list_recent().get("projects") or []):
            if not isinstance(item, dict):
                continue
            project_id = str(item.get("project_id") or "").strip()
            if desired_project_ids and project_id not in desired_project_ids:
                continue
            add(item.get("workspace_root"))
        return candidates

    def _resolve_snapshot_artifact_path(
        self,
        snapshot: dict[str, Any],
        *,
        key: str,
        task: dict[str, Any] | None,
    ) -> Path:
        artifact_paths = dict(snapshot.get("artifact_paths") or {})
        relative_path = str(artifact_paths.get(key) or "").strip()
        if not relative_path:
            raise ValueError(f"Snapshot artifact path is missing for {key}.")
        fallback: Path | None = None
        for workspace_root in self._snapshot_workspace_root_candidates(task=task, snapshot=snapshot):
            try:
                candidate = resolve_under(workspace_root, relative_path)
            except SecurityError:
                continue
            if fallback is None:
                fallback = candidate
            if candidate.exists():
                return candidate
        if fallback is not None:
            return fallback
        raise ValueError(f"Snapshot artifact path is invalid for {key}.")

    def _snapshot_migration_report(self, *, task_graph: dict[str, Any], orchestration_graph: dict[str, Any]) -> dict[str, Any]:
        migration = dict(orchestration_graph.get("migration") or {})
        return {
            "schema_version": "astrabridge-task-graph-migration-report-v1",
            "generated_at": now_iso(),
            "task_id": str(task_graph.get("task_id") or "").strip(),
            "graph_id": str(task_graph.get("graph_id") or "").strip(),
            "task_graph_schema_version": str(task_graph.get("schema_version") or "").strip(),
            "task_graph_state_version": int(task_graph.get("state_version") or 0),
            "orchestration_graph_schema_version": str(orchestration_graph.get("schema_version") or "").strip(),
            "compiled_task_graph_version": str(migration.get("compiled_task_graph_version") or "").strip() or None,
            "source_kind": str(migration.get("source_kind") or "").strip() or "task_graph_definition",
            "warnings": [str(item) for item in list(migration.get("warnings") or []) if str(item).strip()],
            "node_count": len(list(task_graph.get("nodes") or [])),
            "edge_count": len(list(task_graph.get("edges") or [])),
        }

    def _record_graph_snapshot(
        self,
        graph_definition: dict[str, Any],
        *,
        label: str | None = None,
        reason: str,
        source_action: str,
        based_on_snapshot_id: str | None = None,
        rollback_source_snapshot_id: str | None = None,
        comparison_report: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        task = self.current_task()
        if not task:
            raise ValueError("No current task.")
        validated_graph = validate_graph_definition(deepcopy(graph_definition))
        orchestration_graph = self._orchestration_graph_for_task_graph(validated_graph)
        payload_text = serialize_agent_orchestration_graph(orchestration_graph)
        if SECRET_RE.search(payload_text) or DESKTOP_KEY_PATH_RE.search(payload_text):
            raise SecurityError("Secret-like content detected in orchestration graph snapshot payload.")
        task_graph_text = json.dumps(validated_graph, ensure_ascii=False, sort_keys=True)
        if SECRET_RE.search(task_graph_text) or DESKTOP_KEY_PATH_RE.search(task_graph_text):
            raise SecurityError("Secret-like content detected in task graph snapshot payload.")
        snapshot_id = new_id("graph-snapshot")
        created_at = now_iso()
        snapshot_root = self._snapshot_root_for(
            task_id=str(validated_graph.get("task_id") or ""),
            graph_id=str(validated_graph.get("graph_id") or ""),
            snapshot_id=snapshot_id,
        )
        task_graph_path = snapshot_root / "tg.json"
        orchestration_graph_path = snapshot_root / "og.json"
        migration_report_path = snapshot_root / "mr.json"
        manifest_path = snapshot_root / "manifest.json"
        write_json(task_graph_path, validated_graph)
        write_json(orchestration_graph_path, orchestration_graph)
        write_json(migration_report_path, self._snapshot_migration_report(task_graph=validated_graph, orchestration_graph=orchestration_graph))
        artifact_paths: dict[str, str | None] = {
            "snapshot_dir": snapshot_root.relative_to(self._projects.require_workspace_root()).as_posix(),
            "task_graph_json": task_graph_path.relative_to(self._projects.require_workspace_root()).as_posix(),
            "orchestration_graph_json": orchestration_graph_path.relative_to(self._projects.require_workspace_root()).as_posix(),
            "migration_report_json": migration_report_path.relative_to(self._projects.require_workspace_root()).as_posix(),
            "manifest_json": manifest_path.relative_to(self._projects.require_workspace_root()).as_posix(),
        }
        comparison_summary: dict[str, Any] | None = None
        if isinstance(comparison_report, dict):
            diff_json_path = snapshot_root / "diff.json"
            diff_md_path = snapshot_root / "diff.md"
            write_json(diff_json_path, redact_sensitive(comparison_report))
            diff_markdown = render_agent_orchestration_report_markdown(comparison_report)
            diff_md_path.write_text(diff_markdown, encoding="utf-8")
            artifact_paths["comparison_diff_json"] = diff_json_path.relative_to(self._projects.require_workspace_root()).as_posix()
            artifact_paths["comparison_diff_md"] = diff_md_path.relative_to(self._projects.require_workspace_root()).as_posix()
            comparison_summary = {
                "status": str(comparison_report.get("status") or "").strip() or "no_change",
                "change_count": int(dict(comparison_report.get("summary") or {}).get("change_count") or 0),
                "change_types": [str(item) for item in list(dict(comparison_report.get("summary") or {}).get("change_types") or []) if str(item).strip()],
            }
        snapshot = {
            "snapshot_id": snapshot_id,
            "task_id": str(validated_graph.get("task_id") or "").strip(),
            "graph_id": str(validated_graph.get("graph_id") or "").strip(),
            "project_id": str(task.get("project_id") or (self._projects.current_project or {}).get("project_id") or "").strip() or None,
            "label": str(label or "").strip() or f"{reason.replace('_', ' ')} @ v{int(validated_graph.get('state_version') or 0)}",
            "reason": reason,
            "source_action": source_action,
            "state_version": int(validated_graph.get("state_version") or 0),
            "based_on_snapshot_id": str(based_on_snapshot_id or "").strip() or None,
            "rollback_source_snapshot_id": str(rollback_source_snapshot_id or "").strip() or None,
            "created_at": created_at,
            "updated_at": created_at,
            "artifact_paths": artifact_paths,
            "summary": {
                "node_count": len(list(validated_graph.get("nodes") or [])),
                "edge_count": len(list(validated_graph.get("edges") or [])),
                "change_count": int((comparison_summary or {}).get("change_count") or 0),
                "change_types": list((comparison_summary or {}).get("change_types") or []),
            },
        }
        if comparison_summary:
            snapshot["comparison"] = comparison_summary
        write_json(manifest_path, redact_sensitive(snapshot))
        return self._persist_graph_snapshot_ref(snapshot)

    def create_graph_snapshot(self, payload: dict[str, Any]) -> dict[str, Any]:
        task = self.current_task()
        if not task:
            raise ValueError("No current task.")
        if not isinstance(payload, dict):
            raise TypeError("Graph snapshot payload must be a dict.")
        graph_id = str(payload.get("graph_id") or "").strip()
        if not graph_id:
            raise ValueError("graph_id is required.")
        graph = self.graph_definition(graph_id)
        if not graph:
            raise ValueError("Graph not found.")
        snapshot = self._record_graph_snapshot(
            graph,
            label=str(payload.get("label") or "").strip() or None,
            reason=str(payload.get("reason") or "").strip() or "manual_snapshot",
            source_action=str(payload.get("source_action") or "").strip() or "manual_snapshot",
        )
        return {
            "schema_version": "astrabridge-task-graph-snapshot-v1",
            "graph": validate_graph_definition(graph),
            "snapshot": snapshot,
            "task": self.task_view(self.current_task(), compact_graph_runs=True),
        }

    def diff_graph_snapshot(self, payload: dict[str, Any]) -> dict[str, Any]:
        task = self.current_task()
        if not task:
            raise ValueError("No current task.")
        if not isinstance(payload, dict):
            raise TypeError("Graph snapshot diff payload must be a dict.")
        snapshot_id = str(payload.get("snapshot_id") or "").strip()
        if not snapshot_id:
            raise ValueError("snapshot_id is required.")
        snapshot = self.graph_snapshot_ref(snapshot_id)
        if not snapshot:
            raise ValueError("Snapshot not found.")
        snapshot_graph_path = self._resolve_snapshot_artifact_path(
            snapshot,
            key="orchestration_graph_json",
            task=task,
        )
        old_graph = read_json(snapshot_graph_path, {})
        if not isinstance(old_graph, dict):
            raise ValueError("Snapshot orchestration graph is missing.")
        compare_to_snapshot_id = str(payload.get("compare_to_snapshot_id") or "").strip()
        comparison_target_snapshot = self.graph_snapshot_ref(compare_to_snapshot_id) if compare_to_snapshot_id else None
        if compare_to_snapshot_id and not comparison_target_snapshot:
            raise ValueError("Comparison snapshot not found.")
        if comparison_target_snapshot:
            comparison_graph_path = self._resolve_snapshot_artifact_path(
                comparison_target_snapshot,
                key="orchestration_graph_json",
                task=task,
            )
            new_graph = read_json(comparison_graph_path, {})
            compared_label = str(comparison_target_snapshot.get("label") or comparison_target_snapshot.get("snapshot_id") or "").strip() or None
        else:
            current_graph = self.graph_definition(str(snapshot.get("graph_id") or ""))
            if not current_graph:
                raise ValueError("Current graph not found for snapshot diff.")
            new_graph = self._orchestration_graph_for_task_graph(current_graph)
            compared_label = "current graph"
        if not isinstance(new_graph, dict):
            raise ValueError("Comparison graph is missing.")
        report = diff_agent_orchestration_graphs(old_graph, new_graph)
        markdown = render_agent_orchestration_report_markdown(report)
        return {
            "schema_version": "astrabridge-task-graph-snapshot-diff-v1",
            "snapshot": snapshot,
            "compared_snapshot": comparison_target_snapshot,
            "compared_label": compared_label,
            "diff_report": report,
            "diff_markdown": markdown,
            "task": self.task_view(task, compact_graph_runs=True),
        }

    def rollback_graph_to_snapshot(self, payload: dict[str, Any]) -> dict[str, Any]:
        task = self.current_task()
        if not task:
            raise ValueError("No current task.")
        if not isinstance(payload, dict):
            raise TypeError("Graph rollback payload must be a dict.")
        snapshot_id = str(payload.get("snapshot_id") or "").strip()
        if not snapshot_id:
            raise ValueError("snapshot_id is required.")
        snapshot = self.graph_snapshot_ref(snapshot_id)
        if not snapshot:
            raise ValueError("Snapshot not found.")
        task_graph_path = self._resolve_snapshot_artifact_path(
            snapshot,
            key="task_graph_json",
            task=task,
        )
        stored_graph = read_json(task_graph_path, {})
        if not isinstance(stored_graph, dict):
            raise ValueError("Snapshot task graph is missing.")
        current_graph = self.graph_definition(str(snapshot.get("graph_id") or ""))
        if not current_graph:
            raise ValueError("Current graph not found for rollback.")
        current_orchestration = self._orchestration_graph_for_task_graph(current_graph)
        snapshot_orchestration = read_json(
            self._resolve_snapshot_artifact_path(
                snapshot,
                key="orchestration_graph_json",
                task=task,
            ),
            {},
        )
        comparison_report = (
            diff_agent_orchestration_graphs(current_orchestration, snapshot_orchestration)
            if isinstance(snapshot_orchestration, dict)
            else None
        )
        restored_graph = validate_graph_definition(deepcopy(stored_graph))
        restored_graph["updated_at"] = now_iso()
        restored_graph["state_version"] = max(int(restored_graph.get("state_version") or 0), int(current_graph.get("state_version") or 0) + 1)
        restored_graph["orchestration_graph"] = self._sync_orchestration_graph_with_task_graph(
            dict(snapshot_orchestration) if isinstance(snapshot_orchestration, dict) else self._orchestration_graph_for_task_graph(restored_graph),
            task_graph=restored_graph,
        )
        saved = self.upsert_graph_definition(restored_graph)
        rollback_snapshot = self._record_graph_snapshot(
            saved,
            reason="rollback_applied",
            source_action="rollback",
            label=str(payload.get("label") or "").strip() or f"Rollback to {str(snapshot.get('label') or snapshot_id)}",
            based_on_snapshot_id=str(snapshot.get("based_on_snapshot_id") or "").strip() or None,
            rollback_source_snapshot_id=snapshot_id,
            comparison_report=comparison_report,
        )
        return {
            "schema_version": "astrabridge-task-graph-rollback-v1",
            "graph": saved,
            "snapshot": rollback_snapshot,
            "rolled_back_to_snapshot": snapshot,
            "task": self.task_view(self.current_task()),
        }

    def record_graph_run(self, run: dict[str, Any], *, graph_definition: dict[str, Any] | None = None) -> dict[str, Any]:
        task = self.current_task()
        if not task:
            raise ValueError("No current task.")
        graph = graph_definition
        if graph is None:
            graph = self.graph_definition(str(run.get("graph_id") or ""))
        validated_run = validate_task_graph_run(run, graph_definition=graph, workspace_root=self._projects.require_workspace_root())
        compact_ref = self._compact_graph_run_ref(validated_run)
        compact_ref = self._refresh_graph_run_export_report(compact_ref)
        self.durable_run_store().sync_legacy_run(validated_run)
        existing = [
            dict(item)
            for item in list(task.get("graph_run_refs") or [])
            if isinstance(item, dict) and str(item.get("run_id") or "").strip() != str(compact_ref.get("run_id") or "").strip()
        ]
        task["graph_run_refs"] = [compact_ref, *existing][:GRAPH_RUN_REF_LIMIT]
        task["graph_activity_summary"] = self._graph_activity_summary(task)
        task["updated_at"] = now_iso()
        self._save_task(task)
        return compact_ref

    def _refresh_graph_run_export_report(self, run_ref: dict[str, Any]) -> dict[str, Any]:
        clean_run = dict(run_ref or {})
        report_rel = self._graph_run_export_report_path(clean_run)
        if not report_rel:
            return clean_run
        workspace_root = self._projects.require_workspace_root()
        report_path = Path(workspace_root) / report_rel
        report_path.parent.mkdir(parents=True, exist_ok=True)
        export_payload = {
            "schema_version": "astrabridge-task-graph-run-export-v1",
            "generated_at": now_iso(),
            "run": {
                "run_id": str(clean_run.get("run_id") or ""),
                "graph_id": str(clean_run.get("graph_id") or ""),
                "task_id": str(clean_run.get("task_id") or ""),
                "status": str(clean_run.get("status") or ""),
                "created_at": str(clean_run.get("created_at") or ""),
                "updated_at": str(clean_run.get("updated_at") or ""),
                "latest_event_type": clean_run.get("latest_event_type"),
                "latest_event_at": clean_run.get("latest_event_at"),
            },
            "metrics": redact_sensitive(dict(clean_run.get("metrics") or {})),
            "budget": redact_sensitive(dict(clean_run.get("budget") or {})),
            "approval": redact_sensitive(dict(clean_run.get("approval_details") or {})),
            "timeline_events": [dict(item) for item in list(clean_run.get("timeline_events") or []) if isinstance(item, dict)],
            "artifact_refs": [
                {
                    "artifact_id": str(item.get("artifact_id") or "").strip(),
                    "artifact_kind": str(item.get("artifact_kind") or "").strip(),
                    "path": str(item.get("path") or "").strip(),
                    "status": str(item.get("status") or "").strip() or "ready",
                    "label": str(item.get("label") or "").strip() or None,
                }
                for item in list(clean_run.get("artifact_refs") or [])
                if isinstance(item, dict) and str(item.get("path") or "").strip()
            ],
            "diagnostic_refs": [
                {
                    "artifact_id": str(item.get("artifact_id") or "").strip(),
                    "artifact_kind": str(item.get("artifact_kind") or "").strip(),
                    "path": str(item.get("path") or "").strip(),
                    "status": str(item.get("status") or "").strip() or "ready",
                    "label": str(item.get("label") or "").strip() or None,
                }
                for item in list(clean_run.get("diagnostic_refs") or [])
                if isinstance(item, dict) and str(item.get("path") or "").strip()
            ],
        }
        write_json(report_path, export_payload)
        export_ref = {
            "artifact_id": f"{str(clean_run.get('run_id') or '').strip()}-run-export-json",
            "artifact_kind": "run_summary",
            "path": report_rel.as_posix(),
            "status": "ready",
            "label": "Run export",
        }
        clean_run["artifact_refs"] = self._merge_graph_run_export_ref(clean_run.get("artifact_refs"), export_ref)
        clean_run["diagnostic_refs"] = self._merge_graph_run_diagnostic_refs(
            [
                *[dict(item) for item in list(clean_run.get("diagnostic_refs") or []) if isinstance(item, dict)],
                export_ref,
            ]
        )
        return clean_run

    def _graph_run_export_report_path(self, run_ref: dict[str, Any]) -> Path | None:
        candidate_paths: list[str] = []
        for collection_name in ("artifact_refs", "diagnostic_refs"):
            for item in list(run_ref.get(collection_name) or []):
                if isinstance(item, dict):
                    path_text = str(item.get("path") or "").strip()
                    if path_text:
                        candidate_paths.append(path_text)
        for path_text in candidate_paths:
            relative = Path(path_text.replace("\\", "/"))
            if relative.name:
                return relative.parent / "run-export.json"
        return None

    def _refresh_compact_graph_run_observability(self, run_ref: dict[str, Any]) -> dict[str, Any]:
        clean_run = dict(run_ref or {})
        worker_bindings = [dict(item) for item in list(clean_run.get("worker_bindings") or []) if isinstance(item, dict)]
        usage_signals: list[dict[str, Any]] = []
        provider_call_count = 0
        tool_call_count = 0
        retry_count = 0
        elapsed_values: list[int] = []
        for binding in worker_bindings:
            if isinstance(binding.get("usage_signal"), dict):
                usage_signals.append(dict(binding.get("usage_signal") or {}))
            provider_value = _optional_int(binding.get("provider_call_count"))
            if provider_value is not None:
                provider_call_count += max(0, provider_value)
            tool_value = _optional_int(binding.get("tool_call_count"))
            if tool_value is not None:
                tool_call_count += max(0, tool_value)
            retry_value = _optional_int(binding.get("retry_count"))
            if retry_value is None:
                attempt_value = _optional_int(binding.get("attempt_count"))
                retry_value = max(0, attempt_value - 1) if attempt_value is not None else None
            if retry_value is not None:
                retry_count += max(0, retry_value)
            elapsed_value = _optional_int(binding.get("elapsed_ms"))
            if elapsed_value is not None:
                elapsed_values.append(max(0, elapsed_value))
        existing_metrics = dict(clean_run.get("metrics") or {})
        if not provider_call_count:
            existing_provider_calls = _optional_int(existing_metrics.get("provider_call_count"))
            if existing_provider_calls is not None:
                provider_call_count = max(0, existing_provider_calls)
        if not tool_call_count:
            existing_tool_calls = _optional_int(existing_metrics.get("tool_call_count"))
            if existing_tool_calls is not None:
                tool_call_count = max(0, existing_tool_calls)
        if not retry_count:
            existing_retries = _optional_int(existing_metrics.get("retry_count"))
            if existing_retries is not None:
                retry_count = max(0, existing_retries)
        if not elapsed_values:
            existing_elapsed = _optional_int(existing_metrics.get("elapsed_ms"))
            if existing_elapsed is not None:
                elapsed_values.append(max(0, existing_elapsed))
        pseudo_run = {
            "run_policy_snapshot": dict(clean_run.get("policy_snapshot") or {}),
        }
        metrics = self._compact_graph_run_metrics(
            run=pseudo_run,
            node_status_counts={
                str(key): int(value or 0)
                for key, value in dict(clean_run.get("node_status_counts") or {}).items()
                if str(key).strip()
            },
            elapsed_values=elapsed_values,
            retry_count=retry_count,
            provider_call_count=provider_call_count,
            tool_call_count=tool_call_count,
            usage_signals=usage_signals,
            artifact_count=int(clean_run.get("artifact_count") or 0),
            event_count=int(clean_run.get("event_count") or 0),
            approval_status=str(clean_run.get("approval_state") or "").strip(),
        )
        clean_run["metrics"] = metrics
        clean_run["budget"] = self._compact_graph_run_budget(
            run=pseudo_run,
            graph_metrics=metrics,
        )
        return clean_run

    def _merge_graph_run_export_ref(self, current: Any, export_ref: dict[str, Any]) -> list[dict[str, Any]]:
        refs = [dict(item) for item in list(current or []) if isinstance(item, dict)]
        filtered = [
            item
            for item in refs
            if str(item.get("artifact_id") or "").strip() != str(export_ref.get("artifact_id") or "").strip()
            and str(item.get("path") or "").strip() != str(export_ref.get("path") or "").strip()
        ]
        filtered.append(export_ref)
        return filtered[:24]

    def graph_run_ref(self, run_id: str | None = None) -> dict[str, Any] | None:
        task = self.current_task()
        if not task:
            return None
        graph_run_refs = [dict(item) for item in list(task.get("graph_run_refs") or []) if isinstance(item, dict)]
        if run_id:
            for item in graph_run_refs:
                if str(item.get("run_id") or "").strip() == str(run_id or "").strip():
                    return item
            return None
        return graph_run_refs[0] if graph_run_refs else None

    def persist_graph_run_ref(self, run_ref: dict[str, Any]) -> dict[str, Any]:
        task = self.current_task()
        if not task:
            raise ValueError("No current task.")
        if not isinstance(run_ref, dict):
            raise TypeError("Graph run ref must be a dict.")
        run_id = str(run_ref.get("run_id") or "").strip()
        if not run_id:
            raise ValueError("run_id is required.")
        graph_run_refs = [dict(item) for item in list(task.get("graph_run_refs") or []) if isinstance(item, dict)]
        if not any(str(item.get("run_id") or "").strip() == run_id for item in graph_run_refs):
            raise ValueError("Unknown run_id for graph run ref persistence.")
        refreshed = self._refresh_compact_graph_run_observability(dict(run_ref))
        refreshed = self._refresh_graph_run_export_report(refreshed)
        task["graph_run_refs"] = [
            refreshed if str(item.get("run_id") or "").strip() == run_id else item
            for item in graph_run_refs
        ]
        task["graph_activity_summary"] = self._graph_activity_summary(task)
        task["updated_at"] = now_iso()
        self._save_task(task)
        self.durable_run_store().sync_compact_run_ref(refreshed)
        return {"run_ref": refreshed, "task": self.task_view(task, compact_graph_runs=True)}

    def record_graph_worker(
        self,
        payload: dict[str, Any],
        *,
        graph_definition: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        task = self.current_task()
        if not task:
            raise ValueError("No current task.")
        if not isinstance(payload, dict):
            raise TypeError("Graph worker payload must be a dict.")
        graph_id = str(payload.get("graph_id") or "").strip()
        run_id = str(payload.get("run_id") or "").strip()
        node_id = str(payload.get("node_id") or "").strip()
        if not graph_id or not run_id or not node_id:
            raise ValueError("graph_id, run_id, and node_id are required.")
        graph = graph_definition or self.graph_definition(graph_id)
        if not graph:
            raise ValueError("Unknown graph_id for graph worker record.")
        if str(graph.get("task_id") or "") != str(task.get("task_id") or ""):
            raise ValueError("graph worker task_id must match the current task.")
        node_map = {
            str(item.get("node_id") or "").strip(): dict(item)
            for item in list(graph.get("nodes") or [])
            if isinstance(item, dict) and str(item.get("node_id") or "").strip()
        }
        if node_id not in node_map:
            raise ValueError(f"Unknown graph worker node_id: {node_id}")

        graph_run_refs = [dict(item) for item in list(task.get("graph_run_refs") or []) if isinstance(item, dict)]
        target_run = None
        for item in graph_run_refs:
            if str(item.get("run_id") or "").strip() == run_id:
                target_run = item
                break
        if target_run is None:
            raise ValueError("Unknown run_id for graph worker record.")

        binding = self._normalize_graph_worker_binding(
            {
                "binding_id": payload.get("binding_id") or new_id("graph-worker"),
                "graph_id": graph_id,
                "run_id": run_id,
                "node_id": node_id,
                "worker_thread_id": payload.get("worker_thread_id"),
                "parent_thread_id": payload.get("parent_thread_id"),
                "spawn_mode": payload.get("spawn_mode"),
                "worker_origin": payload.get("worker_origin"),
                "agent_role": payload.get("agent_role"),
                "agent_nickname": payload.get("agent_nickname"),
                "status": payload.get("status"),
                "execution_backend": payload.get("execution_backend"),
                "artifact_refs": payload.get("artifact_refs"),
                "runtime_contract": payload.get("runtime_contract"),
                "created_at": payload.get("created_at") or now_iso(),
                "updated_at": payload.get("updated_at") or now_iso(),
            },
            graph_id=graph_id,
            run_id=run_id,
            node_ids=set(node_map),
        )
        updated_bindings = [
            dict(item)
            for item in list(target_run.get("worker_bindings") or [])
            if isinstance(item, dict)
            and str(item.get("binding_id") or "").strip() != str(binding.get("binding_id") or "").strip()
            and not (
                str(item.get("node_id") or "").strip() == node_id
                and str(item.get("worker_thread_id") or "").strip() == str(binding.get("worker_thread_id") or "").strip()
            )
        ]
        updated_bindings.insert(0, binding)
        target_run["worker_bindings"] = updated_bindings[:80]
        target_run["worker_count"] = len(target_run["worker_bindings"])
        target_run["updated_at"] = str(binding.get("updated_at") or now_iso())

        task["graph_run_refs"] = [
            target_run if str(item.get("run_id") or "").strip() == run_id else item
            for item in graph_run_refs
        ]
        task["graph_activity_summary"] = self._graph_activity_summary(task)
        task["updated_at"] = now_iso()
        self._save_task(task)
        return {"worker_binding": binding, "run_ref": target_run, "task": self.task_view(task, compact_graph_runs=True)}

    def record_graph_worker_output(
        self,
        payload: dict[str, Any],
        *,
        graph_definition: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        task = self.current_task()
        if not task:
            raise ValueError("No current task.")
        if not isinstance(payload, dict):
            raise TypeError("Graph worker output payload must be a dict.")
        graph_id = str(payload.get("graph_id") or "").strip()
        run_id = str(payload.get("run_id") or "").strip()
        node_id = str(payload.get("node_id") or "").strip()
        worker_thread_id = str(payload.get("worker_thread_id") or "").strip()
        if not graph_id or not run_id or not node_id or not worker_thread_id:
            raise ValueError("graph_id, run_id, node_id, and worker_thread_id are required.")

        graph = graph_definition or self.graph_definition(graph_id)
        if not graph:
            raise ValueError("Unknown graph_id for graph worker output.")
        node_map = {
            str(item.get("node_id") or "").strip(): dict(item)
            for item in list(graph.get("nodes") or [])
            if isinstance(item, dict) and str(item.get("node_id") or "").strip()
        }
        source_node = node_map.get(node_id)
        if not source_node:
            raise ValueError(f"Unknown graph worker node_id: {node_id}")

        graph_run_refs = [dict(item) for item in list(task.get("graph_run_refs") or []) if isinstance(item, dict)]
        run_ref = next((item for item in graph_run_refs if str(item.get("run_id") or "").strip() == run_id), None)
        if run_ref is None:
            raise ValueError("Unknown run_id for graph worker output.")
        worker_bindings = [dict(item) for item in list(run_ref.get("worker_bindings") or []) if isinstance(item, dict)]
        binding = next(
            (
                dict(item)
                for item in worker_bindings
                if str(item.get("worker_thread_id") or "").strip() == worker_thread_id
                and str(item.get("node_id") or "").strip() == node_id
            ),
            None,
        )
        if binding is None:
            raise ValueError("Unknown worker binding for graph worker output.")

        created_at = str(payload.get("created_at") or now_iso()).strip() or now_iso()
        workspace_root = self._projects.require_workspace_root()
        relative_root = Path("PRIVATE") / "task-graph" / "workers" / run_id / node_id
        artifact_root = Path(workspace_root) / relative_root
        output_json_path = artifact_root / "output.json"
        summary_md_path = artifact_root / "summary.md"
        output_envelope_json_path = artifact_root / "output-envelope.json"
        handoff_json_path = artifact_root / "handoff.json"

        human_summary = _compact_text(redact_sensitive(payload.get("human_summary") or ""), limit=1200)
        machine_result = _sanitize_graph_machine_result(redact_sensitive(payload.get("machine_result") or {}))
        confidence = payload.get("confidence")
        next_action_hints = [
            _compact_text(redact_sensitive(item), limit=240)
            for item in list(payload.get("next_action_hints") or [])
            if str(item or "").strip()
        ][:8]
        provenance = {
            "worker_thread_id": worker_thread_id,
            "parent_thread_id": str(binding.get("parent_thread_id") or "").strip(),
            "worker_origin": str(binding.get("worker_origin") or "").strip(),
            "spawn_mode": str(binding.get("spawn_mode") or "").strip(),
            "agent_role": str(binding.get("agent_role") or "").strip(),
            "agent_nickname": str(binding.get("agent_nickname") or "").strip(),
        }
        output_contract = dict(source_node.get("output_contract") or {})
        runtime_contract = dict(binding.get("runtime_contract") or {})
        policy_snapshot = dict(run_ref.get("policy_snapshot") or {})
        pricing = dict(policy_snapshot.get("pricing") or {})
        provider_id = str(
            payload.get("provider_id")
            or runtime_contract.get("provider_id")
            or runtime_contract.get("provider")
            or ""
        ).strip()
        model = str(
            payload.get("model")
            or runtime_contract.get("model")
            or runtime_contract.get("model_id")
            or ""
        ).strip()
        raw_usage_signal = payload.get("usage_signal")
        usage_signal = None
        if isinstance(raw_usage_signal, dict):
            if str(raw_usage_signal.get("schema_version") or "").strip() == "astrabridge-usage-signal-v1":
                usage_signal = redact_sensitive(dict(raw_usage_signal))
            else:
                usage_signal = normalize_usage_signal(
                    source="graph_worker_output",
                    provider_id=provider_id or None,
                    model=model or None,
                    usage=raw_usage_signal,
                    pricing=pricing,
                    request_kind="graph_worker_output",
                )
        provider_call_count = _optional_int(payload.get("provider_call_count"))
        tool_call_count = _optional_int(payload.get("tool_call_count"))
        elapsed_ms = _optional_int(payload.get("elapsed_ms"))
        attempt_count = _optional_int(payload.get("attempt_count"))
        retry_count = _optional_int(payload.get("retry_count"))
        if retry_count is None and attempt_count is not None:
            retry_count = max(0, attempt_count - 1)

        output_bundle = {
            "schema_version": "astrabridge-task-graph-worker-output-v1",
            "graph_id": graph_id,
            "run_id": run_id,
            "task_id": str(task.get("task_id") or ""),
            "node_id": node_id,
            "worker_thread_id": worker_thread_id,
            "human_summary": human_summary,
            "machine_result": machine_result,
            "artifact_refs": list(binding.get("artifact_refs") or []),
            "provenance": provenance,
            "confidence": confidence,
            "next_action_hints": next_action_hints,
            "output_contract": {
                "artifact_only": bool(output_contract.get("artifact_only")),
                "human_summary_required": bool(output_contract.get("human_summary_required")),
                "artifact_outputs": list(output_contract.get("artifact_outputs") or []),
            },
            "created_at": created_at,
        }
        write_json(output_json_path, output_bundle)
        summary_md_path.parent.mkdir(parents=True, exist_ok=True)
        summary_md_path.write_text(self._graph_worker_summary_markdown(output_bundle), encoding="utf-8")

        generated_output_artifact_refs = [
            {
                "artifact_id": f"{worker_thread_id}-output-json",
                "artifact_kind": "structured_json",
                "path": output_json_path.relative_to(workspace_root).as_posix(),
                "status": "ready",
            },
            {
                "artifact_id": f"{worker_thread_id}-summary-md",
                "artifact_kind": "text_report",
                "path": summary_md_path.relative_to(workspace_root).as_posix(),
                "status": "ready",
            },
        ]
        output_envelope = self._build_graph_worker_output_envelope(
            graph=graph,
            source_node=source_node,
            output_bundle=output_bundle,
            output_contract=output_contract,
            bundle_paths={
                "output_json": output_json_path.relative_to(workspace_root).as_posix(),
                "summary_md": summary_md_path.relative_to(workspace_root).as_posix(),
                "output_envelope_json": output_envelope_json_path.relative_to(workspace_root).as_posix(),
            },
            generated_artifact_refs=generated_output_artifact_refs,
        )
        write_json(output_envelope_json_path, output_envelope)

        downstream_handoffs = self._build_graph_worker_handoffs(
            graph=graph,
            node_id=node_id,
            run_id=run_id,
            output_bundle=output_bundle,
            output_envelope=output_envelope,
            bundle_paths={
                "output_json": output_json_path.relative_to(workspace_root).as_posix(),
                "summary_md": summary_md_path.relative_to(workspace_root).as_posix(),
                "output_envelope_json": output_envelope_json_path.relative_to(workspace_root).as_posix(),
            },
            generated_artifact_refs=generated_output_artifact_refs,
        )
        write_json(
            handoff_json_path,
            {
                "schema_version": "astrabridge-task-graph-worker-handoff-v1",
                "graph_id": graph_id,
                "run_id": run_id,
                "node_id": node_id,
                "worker_thread_id": worker_thread_id,
                "output_envelope_path": output_envelope_json_path.relative_to(workspace_root).as_posix(),
                "downstream_handoffs": downstream_handoffs,
                "created_at": created_at,
            },
        )

        new_artifact_refs = [
            *generated_output_artifact_refs,
            {
                "artifact_id": f"{worker_thread_id}-output-envelope-json",
                "artifact_kind": "structured_json",
                "path": output_envelope_json_path.relative_to(workspace_root).as_posix(),
                "status": "ready",
            },
            {
                "artifact_id": f"{worker_thread_id}-handoff-json",
                "artifact_kind": "structured_json",
                "path": handoff_json_path.relative_to(workspace_root).as_posix(),
                "status": "ready",
            },
        ]
        compact_output = {
            "human_summary": _compact_text(human_summary, limit=240),
            "machine_result_preview": _compact_text(redact_sensitive(machine_result), limit=240),
            "confidence": confidence,
            "next_action_hints": next_action_hints,
            "artifact_bundle_path": output_json_path.relative_to(workspace_root).as_posix(),
            "output_envelope_path": output_envelope_json_path.relative_to(workspace_root).as_posix(),
        }

        binding["artifact_refs"] = self._merge_graph_worker_artifact_refs(
            list(binding.get("artifact_refs") or []),
            new_artifact_refs,
        )
        binding["output_summary"] = compact_output
        binding["downstream_handoffs"] = downstream_handoffs
        binding["status"] = str(payload.get("status") or "completed")
        binding["updated_at"] = str(payload.get("updated_at") or created_at)
        if usage_signal is not None:
            binding["usage_signal"] = usage_signal
        if provider_call_count is not None:
            binding["provider_call_count"] = provider_call_count
        if tool_call_count is not None:
            binding["tool_call_count"] = tool_call_count
        if elapsed_ms is not None:
            binding["elapsed_ms"] = elapsed_ms
        if attempt_count is not None:
            binding["attempt_count"] = attempt_count
        if retry_count is not None:
            binding["retry_count"] = retry_count

        updated_bindings = [
            binding if str(item.get("binding_id") or "").strip() == str(binding.get("binding_id") or "").strip() else item
            for item in worker_bindings
        ]
        run_ref["worker_bindings"] = updated_bindings[:80]
        run_ref["worker_count"] = len(run_ref["worker_bindings"])
        run_ref["artifact_count"] = int(run_ref.get("artifact_count") or 0) + len(new_artifact_refs)
        run_ref["latest_event_type"] = "node_completed"
        run_ref["latest_event_at"] = binding["updated_at"]
        run_ref["updated_at"] = binding["updated_at"]
        run_ref = self._refresh_compact_graph_run_observability(run_ref)
        run_ref = self._refresh_graph_run_export_report(run_ref)

        task["graph_run_refs"] = [
            run_ref if str(item.get("run_id") or "").strip() == run_id else item
            for item in graph_run_refs
        ]
        task["graph_activity_summary"] = self._graph_activity_summary(task)
        task["updated_at"] = now_iso()
        self._save_task(task)
        return {
            "worker_binding": binding,
            "run_ref": run_ref,
            "task": self.task_view(task, compact_graph_runs=True),
            "artifact_bundle": output_bundle,
        }

    def list_graph_templates(
        self,
        *,
        configured_models: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        templates: list[dict[str, Any]] = []
        for template_id in GRAPH_TEMPLATE_IDS:
            graph = validate_graph_definition(load_task_graph_fixture(template_id))
            metadata = dict(GRAPH_TEMPLATE_PRODUCT_METADATA.get(template_id) or {})
            templates.append(
                {
                    "template_id": template_id,
                    "title": str(graph.get("title") or template_id),
                    "summary": GRAPH_TEMPLATE_SUMMARIES.get(template_id, ""),
                    "node_count": len(list(graph.get("nodes") or [])),
                    "edge_count": len(list(graph.get("edges") or [])),
                    "entry_node_ids": list(dict(graph.get("graph_policy") or {}).get("entry_node_ids") or []),
                    "node_kinds": [
                        str(item.get("kind") or "")
                        for item in list(graph.get("nodes") or [])
                        if isinstance(item, dict)
                    ],
                    "preview_graph": {
                        "title": graph.get("title"),
                        "nodes": [
                            {
                                "node_id": item.get("node_id"),
                                "kind": item.get("kind"),
                                "label": item.get("label"),
                                "position": dict(item.get("position") or {}),
                            }
                            for item in list(graph.get("nodes") or [])
                            if isinstance(item, dict)
                        ],
                        "edges": [
                            {
                                "edge_id": item.get("edge_id"),
                                "from_node_id": item.get("from_node_id"),
                                "to_node_id": item.get("to_node_id"),
                                "edge_type": item.get("edge_type"),
                            }
                            for item in list(graph.get("edges") or [])
                            if isinstance(item, dict)
                        ],
                    },
                    "recommended_provider_ids": list(metadata.get("recommended_provider_ids") or []),
                    "recommended_model_ids": self._resolve_template_recommended_model_ids(
                        metadata,
                        configured_models=configured_models,
                    ),
                    "artifact_expectations": list(metadata.get("artifact_expectations") or []),
                    "validation_hints": list(metadata.get("validation_hints") or []),
                    "constraints": list(metadata.get("constraints") or []),
                }
            )
        return {"schema_version": "astrabridge-task-graph-template-list-v1", "templates": templates}

    @staticmethod
    def _resolve_template_recommended_model_ids(
        metadata: dict[str, Any],
        *,
        configured_models: list[dict[str, Any]] | None = None,
    ) -> list[str]:
        """Keep template guidance aligned with the effective model catalog."""
        providers = [
            str(item or "").strip()
            for item in list(metadata.get("recommended_provider_ids") or [])
            if str(item or "").strip()
        ]
        model_ids = [
            str(item or "").strip()
            for item in list(metadata.get("recommended_model_ids") or [])
            if str(item or "").strip()
        ]
        if configured_models is None:
            return model_ids

        resolved: list[str] = []
        for index, provider_id in enumerate(providers):
            candidate = model_ids[index] if index < len(model_ids) else ""
            available = provider_model_records(
                provider_id,
                configured_models,
                include_disabled=False,
                include_deprecated=False,
            )
            available_native = {
                str(item.get("native_model") or "").strip()
                for item in available
                if str(item.get("native_model") or "").strip()
            }
            if candidate in available_native:
                selected = candidate
            elif available:
                selected = str(available[0].get("native_model") or "").strip()
            else:
                selected = candidate
            if selected and selected not in resolved:
                resolved.append(selected)
        return resolved

    def instantiate_graph_template(
        self,
        template_id: str,
        *,
        title: str | None = None,
        configured_models: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        task = self.current_task()
        if not task:
            raise ValueError("No current task.")
        graph = deepcopy(load_task_graph_fixture(str(template_id or "").strip()))
        new_graph_id = new_id("graph")
        graph["graph_id"] = new_graph_id
        graph["task_id"] = str(task.get("task_id") or "")
        graph["created_at"] = now_iso()
        graph["updated_at"] = graph["created_at"]
        graph["state_version"] = 1
        if str(title or "").strip():
            graph["title"] = str(title or "").strip()
        for node in list(graph.get("nodes") or []):
            if isinstance(node, dict):
                node["graph_id"] = new_graph_id
        for edge in list(graph.get("edges") or []):
            if isinstance(edge, dict):
                edge["graph_id"] = new_graph_id
        self._apply_template_node_defaults(graph, configured_models=configured_models)
        debug_path = str(os.environ.get("ASTRABRIDGE_DEBUG_TEMPLATE_INSTANTIATE") or "").strip()
        if debug_path:
            write_json(
                Path(debug_path),
                {
                    "template_id": template_id,
                    "configured_models": [
                        {
                            "id": item.get("id"),
                            "provider": item.get("provider"),
                            "native_model": item.get("native_model"),
                        }
                        for item in list(configured_models or [])
                        if isinstance(item, dict)
                    ],
                    "post_apply_nodes": [
                        {
                            "node_id": node.get("node_id"),
                            "provider_id": node.get("provider_id"),
                            "model_id": node.get("model_id"),
                            "reasoning_effort": node.get("reasoning_effort"),
                        }
                        for node in list(graph.get("nodes") or [])
                        if isinstance(node, dict)
                    ],
                },
            )
        graph["orchestration_graph"] = self._sync_orchestration_graph_with_task_graph(
            lift_task_graph_to_agent_orchestration_graph(graph),
            task_graph=graph,
        )
        validated = self.upsert_graph_definition(graph)
        return {"graph": validated, "task": self.task_view(self.current_task())}

    def export_graph_for_orchestration_file(self, payload: dict[str, Any]) -> dict[str, Any]:
        task = self.current_task()
        if not task:
            raise ValueError("No current task.")
        if not isinstance(payload, dict):
            raise TypeError("Graph export payload must be a dict.")
        graph_id = str(payload.get("graph_id") or "").strip()
        if not graph_id:
            raise ValueError("graph_id is required.")
        graph = self.graph_definition(graph_id)
        if not graph:
            raise ValueError("Graph not found.")
        validated_graph = validate_graph_definition(graph)
        orchestration_graph = self._orchestration_graph_for_task_graph(validated_graph)
        serialized = serialize_agent_orchestration_graph(orchestration_graph)
        export_path_text = str(payload.get("export_path") or "").strip()
        workspace_root = self._projects.require_workspace_root()
        written_relative_path: str | None = None
        if export_path_text:
            written = write_agent_orchestration_graph_file(resolve_under(workspace_root, export_path_text), orchestration_graph)
            written_relative_path = written.relative_to(workspace_root).as_posix()
        return {
            "schema_version": "astrabridge-agent-orchestration-export-v1",
            "graph": validated_graph,
            "task": self.task_view(task, compact_graph_runs=True),
            "orchestration_graph": orchestration_graph,
            "serialized_text": serialized,
            "export_path": written_relative_path,
        }

    def _known_model_capabilities_for_graph(
        self,
        orchestration_graph: dict[str, Any],
        *,
        profiles_snapshot: dict[str, Any] | None = None,
        configured_models: list[dict[str, Any]] | None = None,
    ) -> dict[str, dict[str, Any]]:
        profile_records = [dict(item) for item in list((profiles_snapshot or {}).get("profiles") or []) if isinstance(item, dict)]
        return build_known_model_capabilities(
            graph=orchestration_graph,
            configured_models=configured_models,
            profile_records=profile_records,
        )

    def save_graph_definition(self, payload: dict[str, Any]) -> dict[str, Any]:
        task = self.current_task()
        if not task:
            raise ValueError("No current task.")
        if not isinstance(payload, dict):
            raise TypeError("Graph save payload must be a dict.")
        graph_payload = payload.get("graph")
        if not isinstance(graph_payload, dict):
            raise ValueError("graph is required.")
        validated_graph = validate_graph_definition(deepcopy(graph_payload))
        if str(validated_graph.get("task_id") or "").strip() != str(task.get("task_id") or "").strip():
            raise ValueError("graph.task_id must match the current task.")
        prior_graph = self.graph_definition(str(validated_graph.get("graph_id") or ""))
        pre_snapshot = (
            self._record_graph_snapshot(
                prior_graph,
                reason="before_graph_save",
                source_action="save_graph_definition",
                label=f"Before save: {str(prior_graph.get('title') or prior_graph.get('graph_id') or '')}".strip(),
            )
            if isinstance(prior_graph, dict)
            else None
        )
        validated_graph["orchestration_graph"] = self._orchestration_graph_for_task_graph(validated_graph)
        saved = self.upsert_graph_definition(validated_graph)
        comparison_report = (
            diff_agent_orchestration_graphs(
                self._orchestration_graph_for_task_graph(prior_graph),
                dict(saved.get("orchestration_graph") or {}),
            )
            if isinstance(prior_graph, dict)
            else None
        )
        snapshot = self._record_graph_snapshot(
            saved,
            reason="after_graph_save",
            source_action="save_graph_definition",
            label=f"After save: {str(saved.get('title') or saved.get('graph_id') or '')}".strip(),
            based_on_snapshot_id=str((pre_snapshot or {}).get("snapshot_id") or "").strip() or None,
            comparison_report=comparison_report,
        )
        return {
            "schema_version": "astrabridge-task-graph-save-v1",
            "graph": saved,
            "snapshot": snapshot,
            "task": self.task_view(self.current_task()),
        }

    def import_graph_from_orchestration_file(
        self,
        payload: dict[str, Any],
        *,
        profiles_snapshot: dict[str, Any] | None = None,
        configured_models: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        task = self.current_task()
        if not task:
            raise ValueError("No current task.")
        if not isinstance(payload, dict):
            raise TypeError("Graph import payload must be a dict.")
        graph_text = str(payload.get("graph_text") or "").strip()
        graph_path = str(payload.get("graph_path") or "").strip()
        if not graph_text and not graph_path:
            raise ValueError("graph_text or graph_path is required.")
        workspace_root = self._projects.require_workspace_root()
        if graph_path:
            orchestration_graph = load_agent_orchestration_graph_file(resolve_under(workspace_root, graph_path))
        else:
            orchestration_graph = parse_agent_orchestration_graph_text(graph_text, source_name="task-graph-import")
        compile_agent_orchestration_graph(
            orchestration_graph,
            known_model_capabilities=self._known_model_capabilities_for_graph(
                orchestration_graph,
                profiles_snapshot=profiles_snapshot,
                configured_models=configured_models,
            ),
        )
        prior_graph = self.graph_definition()
        pre_snapshot = (
            self._record_graph_snapshot(
                prior_graph,
                reason="before_graph_import",
                source_action="import_graph",
                label=f"Before import: {str(prior_graph.get('title') or prior_graph.get('graph_id') or '')}".strip(),
            )
            if isinstance(prior_graph, dict)
            else None
        )
        imported = deepcopy(orchestration_graph)
        imported["task_id"] = str(task.get("task_id") or "")
        imported["metadata"] = {
            **dict(imported.get("metadata") or {}),
            "updated_at": now_iso(),
        }
        task_graph = lower_agent_orchestration_graph_to_task_graph(imported)
        task_graph["task_id"] = str(task.get("task_id") or "")
        task_graph["updated_at"] = now_iso()
        task_graph["state_version"] = int(task_graph.get("state_version") or 0) + 1
        task_graph["orchestration_graph"] = self._sync_orchestration_graph_with_task_graph(imported, task_graph=task_graph)
        validated = self.upsert_graph_definition(task_graph)
        comparison_report = (
            diff_agent_orchestration_graphs(
                self._orchestration_graph_for_task_graph(prior_graph),
                dict(validated.get("orchestration_graph") or {}),
            )
            if isinstance(prior_graph, dict)
            else None
        )
        snapshot = self._record_graph_snapshot(
            validated,
            reason="after_graph_import",
            source_action="import_graph",
            label=f"After import: {str(validated.get('title') or validated.get('graph_id') or '')}".strip(),
            based_on_snapshot_id=str((pre_snapshot or {}).get("snapshot_id") or "").strip() or None,
            comparison_report=comparison_report,
        )
        return {
            "schema_version": "astrabridge-agent-orchestration-import-v1",
            "graph": validated,
            "task": self.task_view(self.current_task()),
            "orchestration_graph": dict(validated.get("orchestration_graph") or {}),
            "import_path": Path(graph_path).as_posix() if graph_path else None,
            "snapshot": snapshot,
        }

    def update_graph_node(self, payload: dict[str, Any]) -> dict[str, Any]:
        task = self.current_task()
        if not task:
            raise ValueError("No current task.")
        if not isinstance(payload, dict):
            raise TypeError("Graph node update payload must be a dict.")
        graph_id = str(payload.get("graph_id") or "").strip()
        node_id = str(payload.get("node_id") or "").strip()
        if not graph_id:
            raise ValueError("graph_id is required.")
        if not node_id:
            raise ValueError("node_id is required.")
        graph = self.graph_definition(graph_id)
        if not graph:
            raise ValueError("Graph not found.")
        pre_snapshot = self._record_graph_snapshot(
            graph,
            reason="before_node_update",
            source_action="update_graph_node",
            label=f"Before node update: {node_id}",
        )
        updated = deepcopy(graph)
        create_payload = payload.get("create")
        target_node = next(
            (
                item
                for item in list(updated.get("nodes") or [])
                if isinstance(item, dict) and str(item.get("node_id") or "").strip() == node_id
            ),
            None,
        )
        if create_payload is not None:
            if not isinstance(create_payload, dict):
                raise ValueError("create must be an object.")
            if isinstance(target_node, dict):
                raise ValueError("Node already exists.")
            target_node = self._build_graph_node(
                updated,
                requested_node_id=node_id,
                kind=str(create_payload.get("kind") or ""),
                label=str(create_payload.get("label") or ""),
                position=create_payload.get("position"),
                configuration=payload.get("configuration") if isinstance(payload.get("configuration"), dict) else None,
            )
            updated.setdefault("nodes", []).append(target_node)
            graph_policy = dict(updated.get("graph_policy") or {})
            entry_node_ids = [str(item).strip() for item in list(graph_policy.get("entry_node_ids") or []) if str(item).strip()]
            if not entry_node_ids:
                graph_policy["entry_node_ids"] = [target_node["node_id"]]
                updated["graph_policy"] = graph_policy
        elif not isinstance(target_node, dict):
            raise ValueError("Node not found.")
        if "position" in payload:
            position = payload.get("position")
            if not isinstance(position, dict):
                raise ValueError("position must be an object.")
            target_node["position"] = {"x": position.get("x"), "y": position.get("y")}
        if "configuration" in payload:
            configuration = payload.get("configuration")
            if not isinstance(configuration, dict):
                raise ValueError("configuration must be an object.")
            for key in (
                "label",
                "provider_id",
                "model_id",
                "reasoning_effort",
                "permission_mode",
                "collaboration_mode",
                "execution_backend",
                "budget",
                "human_summary_template",
                "machine_result_schema",
                "ui_hints",
                "artifact_requirements",
                "approval_gate",
                "status",
            ):
                if key in configuration:
                    target_node[key] = configuration.get(key)
            if "execution_policy" in configuration:
                target_node["execution_policy"] = dict(configuration.get("execution_policy") or {})
            if "output_contract" in configuration:
                target_node["output_contract"] = dict(configuration.get("output_contract") or {})
        updated["updated_at"] = now_iso()
        updated["state_version"] = int(updated.get("state_version") or 0) + 1
        updated["orchestration_graph"] = self._sync_orchestration_graph_with_task_graph(updated.get("orchestration_graph"), task_graph=updated)
        validated = self.upsert_graph_definition(updated)
        comparison_report = diff_agent_orchestration_graphs(
            self._orchestration_graph_for_task_graph(graph),
            dict(validated.get("orchestration_graph") or {}),
        )
        snapshot = self._record_graph_snapshot(
            validated,
            reason="after_node_update",
            source_action="update_graph_node",
            label=f"After node update: {node_id}",
            based_on_snapshot_id=str(pre_snapshot.get("snapshot_id") or "").strip() or None,
            comparison_report=comparison_report,
        )
        refreshed_node = next(
            dict(item)
            for item in list(validated.get("nodes") or [])
            if isinstance(item, dict) and str(item.get("node_id") or "").strip() == node_id
        )
        return {"graph": validated, "node": refreshed_node, "snapshot": snapshot, "task": self.task_view(self.current_task())}

    def _build_graph_node(
        self,
        graph: dict[str, Any],
        *,
        requested_node_id: str,
        kind: str,
        label: str,
        position: Any,
        configuration: dict[str, Any] | None,
    ) -> dict[str, Any]:
        clean_kind = self._sanitize_graph_token(kind) or "custom"
        clean_node_id = requested_node_id or self._next_graph_node_id(graph, clean_kind)
        clean_label = str(label or self._default_graph_node_label(clean_kind)).strip() or self._default_graph_node_label(clean_kind)
        resolved_position = self._next_graph_node_position(graph) if not isinstance(position, dict) else {
            "x": int(position.get("x") or 80),
            "y": int(position.get("y") or 160),
        }
        node = {
            "node_id": clean_node_id,
            "graph_id": str(graph.get("graph_id") or ""),
            "kind": clean_kind,
            "label": clean_label,
            "agent_card_ref": f"agent_card_{clean_kind}",
            "execution_policy": {
                "spawn_mode": "isolated_lane",
                "retry_policy": {"max_attempts": 1},
                "timeout_ms": 180000,
                "allow_provider_calls": True,
                "allow_code_changes": False,
                "allow_install": False,
                "requires_human_approval": False,
            },
            "output_contract": {
                "human_summary_required": True,
                "artifact_outputs": ["structured_json"],
                "machine_result_schema": {"type": "object", "required": ["result"]},
                "artifact_only": False,
            },
            "position": resolved_position,
            "status": "draft",
            "permission_mode": "ask",
            "collaboration_mode": "default",
            "execution_backend": "app_server",
            "ui_hints": {"context_policy_preset": "task_digest"},
        }
        if isinstance(configuration, dict):
            for key in (
                "provider_id",
                "model_id",
                "reasoning_effort",
                "permission_mode",
                "collaboration_mode",
                "execution_backend",
                "budget",
                "human_summary_template",
                "machine_result_schema",
                "ui_hints",
                "artifact_requirements",
                "approval_gate",
                "status",
                "label",
            ):
                if key in configuration:
                    node[key] = configuration.get(key)
            if "execution_policy" in configuration:
                node["execution_policy"] = dict(configuration.get("execution_policy") or {})
            if "output_contract" in configuration:
                node["output_contract"] = dict(configuration.get("output_contract") or {})
        return node

    def _next_graph_node_id(self, graph: dict[str, Any], kind: str) -> str:
        base = f"node_{self._sanitize_graph_token(kind) or 'custom'}"
        existing_ids = {
            str(item.get("node_id") or "").strip()
            for item in list(graph.get("nodes") or [])
            if isinstance(item, dict)
        }
        if base not in existing_ids:
            return base
        index = 2
        while f"{base}_{index}" in existing_ids:
            index += 1
        return f"{base}_{index}"

    def _next_graph_node_position(self, graph: dict[str, Any]) -> dict[str, int]:
        positions: list[dict[str, Any]] = [
            dict(item.get("position") or {})
            for item in list(graph.get("nodes") or [])
            if isinstance(item, dict) and isinstance(item.get("position"), dict)
        ]
        if not positions:
            return {"x": 80, "y": 160}
        min_x = min(int(item.get("x") or 0) for item in positions)
        min_y = min(int(item.get("y") or 0) for item in positions)
        next_index = len(positions)
        column = next_index % 3
        row = next_index // 3
        return {"x": min_x + column * 260, "y": min_y + row * 180}

    def _default_graph_node_label(self, kind: str) -> str:
        mapping = {
            "supervisor": "Supervisor",
            "planner": "Planner",
            "worker": "Worker",
            "coder": "Coder",
            "reviewer": "Reviewer",
            "validator": "Validator",
            "researcher": "Researcher",
            "extractor": "Extractor",
            "synthesizer": "Synthesizer",
            "gate": "Gate",
            "custom": "Custom Agent",
        }
        return mapping.get(self._sanitize_graph_token(kind) or "custom", "Custom Agent")

    @staticmethod
    def _sanitize_graph_token(value: str) -> str:
        return re.sub(r"[^a-z0-9_]+", "_", str(value or "").strip().lower()).strip("_")

    def update_graph_edge(self, payload: dict[str, Any]) -> dict[str, Any]:
        task = self.current_task()
        if not task:
            raise ValueError("No current task.")
        if not isinstance(payload, dict):
            raise TypeError("Graph edge update payload must be a dict.")
        graph_id = str(payload.get("graph_id") or "").strip()
        edge_id = str(payload.get("edge_id") or "").strip()
        if not graph_id:
            raise ValueError("graph_id is required.")
        graph = self.graph_definition(graph_id)
        if not graph:
            raise ValueError("Graph not found.")
        pre_snapshot = self._record_graph_snapshot(
            graph,
            reason="before_edge_update",
            source_action="update_graph_edge",
            label=f"Before edge update: {edge_id or 'new edge'}",
        )
        updated = deepcopy(graph)
        target_edge = next(
            (
                item
                for item in list(updated.get("edges") or [])
                if isinstance(item, dict) and str(item.get("edge_id") or "").strip() == edge_id
            ),
            None,
        )
        creating = not isinstance(target_edge, dict)
        if creating:
            from_node_id = str(payload.get("from_node_id") or "").strip()
            to_node_id = str(payload.get("to_node_id") or "").strip()
            edge_type = str(payload.get("edge_type") or "").strip()
            context_policy = payload.get("context_policy")
            handoff_contract = payload.get("handoff_contract")
            if not from_node_id:
                raise ValueError("from_node_id is required when creating an edge.")
            if not to_node_id:
                raise ValueError("to_node_id is required when creating an edge.")
            if not edge_type:
                raise ValueError("edge_type is required when creating an edge.")
            if from_node_id == to_node_id:
                raise ValueError("from_node_id and to_node_id must be different.")
            if not isinstance(context_policy, dict):
                raise ValueError("context_policy is required when creating an edge.")
            if handoff_contract is not None and not isinstance(handoff_contract, dict):
                raise ValueError("handoff_contract must be an object.")
            target_edge = {
                "edge_id": edge_id or new_id("edge"),
                "graph_id": graph_id,
                "from_node_id": from_node_id,
                "to_node_id": to_node_id,
                "edge_type": edge_type,
                "handoff_contract": dict(handoff_contract or {}),
                "context_policy": dict(context_policy),
                "status": str(payload.get("status") or "ready").strip() or "ready",
            }
            updated["edges"] = [*list(updated.get("edges") or []), target_edge]
        else:
            for key in ("from_node_id", "to_node_id", "edge_type", "status"):
                if key in payload:
                    target_edge[key] = payload.get(key)
            if "context_policy" in payload:
                context_policy = payload.get("context_policy")
                if not isinstance(context_policy, dict):
                    raise ValueError("context_policy must be an object.")
                target_edge["context_policy"] = dict(context_policy)
            if "handoff_contract" in payload:
                handoff_contract = payload.get("handoff_contract")
                if handoff_contract is not None and not isinstance(handoff_contract, dict):
                    raise ValueError("handoff_contract must be an object.")
                target_edge["handoff_contract"] = dict(handoff_contract or {})
            if str(target_edge.get("from_node_id") or "").strip() == str(target_edge.get("to_node_id") or "").strip():
                raise ValueError("from_node_id and to_node_id must be different.")
        updated["updated_at"] = now_iso()
        updated["state_version"] = int(updated.get("state_version") or 0) + 1
        updated["orchestration_graph"] = self._sync_orchestration_graph_with_task_graph(updated.get("orchestration_graph"), task_graph=updated)
        validated = self.upsert_graph_definition(updated)
        comparison_report = diff_agent_orchestration_graphs(
            self._orchestration_graph_for_task_graph(graph),
            dict(validated.get("orchestration_graph") or {}),
        )
        snapshot = self._record_graph_snapshot(
            validated,
            reason="after_edge_update",
            source_action="update_graph_edge",
            label=f"After edge update: {str(target_edge.get('edge_id') or edge_id or 'edge')}",
            based_on_snapshot_id=str(pre_snapshot.get("snapshot_id") or "").strip() or None,
            comparison_report=comparison_report,
        )
        refreshed_edge = next(
            dict(item)
            for item in list(validated.get("edges") or [])
            if isinstance(item, dict) and str(item.get("edge_id") or "").strip() == str(target_edge.get("edge_id") or "").strip()
        )
        return {"graph": validated, "edge": refreshed_edge, "snapshot": snapshot, "task": self.task_view(self.current_task())}

    def dry_run_graph(
        self,
        payload: dict[str, Any],
        *,
        profiles_snapshot: dict[str, Any] | None = None,
        configured_models: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        task = self.current_task()
        if not task:
            raise ValueError("No current task.")
        if not isinstance(payload, dict):
            raise TypeError("Task graph dry-run payload must be a dict.")
        graph_id = str(payload.get("graph_id") or "").strip()
        if not graph_id:
            raise ValueError("graph_id is required.")
        graph = self.graph_definition(graph_id)
        if not graph:
            raise ValueError("Graph not found.")
        repaired_graph, repaired = self._repair_stale_template_node_routes(
            graph,
            configured_models=configured_models,
        )
        if repaired:
            graph = self.upsert_graph_definition(repaired_graph)
        validated_graph = validate_graph_definition(graph)
        orchestration_graph = self._orchestration_graph_for_task_graph(validated_graph)
        known_model_capabilities = self._known_model_capabilities_for_graph(
            orchestration_graph,
            profiles_snapshot=profiles_snapshot,
            configured_models=configured_models,
        )
        compiled_plan = compile_agent_orchestration_graph(orchestration_graph, known_model_capabilities=known_model_capabilities)
        validation_mode = str(payload.get("validation_mode") or "default").strip().lower() or "default"
        require_live_contract = validation_mode == "live"
        budget_snapshot = self._graph_run_budget_snapshot(
            graph=validated_graph,
            compiled_plan=compiled_plan,
            run_budget=dict(payload.get("budget") or {}) if isinstance(payload.get("budget"), dict) else None,
        )
        workspace_root = self._projects.require_workspace_root()
        run_id = new_id("graph-dry-run")
        created_at = now_iso()
        entry_node_ids = list(dict(validated_graph.get("graph_policy") or {}).get("entry_node_ids") or [])
        node_map = {
            str(node.get("node_id") or "").strip(): dict(node)
            for node in list(validated_graph.get("nodes") or [])
            if isinstance(node, dict)
        }
        incoming_edges: dict[str, list[dict[str, Any]]] = {node_id: [] for node_id in node_map}
        outgoing_edges: dict[str, list[dict[str, Any]]] = {node_id: [] for node_id in node_map}
        for edge in list(validated_graph.get("edges") or []):
            if not isinstance(edge, dict):
                continue
            incoming_edges.setdefault(str(edge.get("to_node_id") or "").strip(), []).append(edge)
            outgoing_edges.setdefault(str(edge.get("from_node_id") or "").strip(), []).append(edge)
        profile_records = [dict(item) for item in list((profiles_snapshot or {}).get("profiles") or []) if isinstance(item, dict)]
        known_routes = {
            (str(item.get("provider_id") or "").strip(), str(item.get("model") or "").strip())
            for item in profile_records
            if str(item.get("provider_id") or "").strip() and str(item.get("model") or "").strip()
        }
        known_providers = {
            str(item.get("provider_id") or "").strip()
            for item in profile_records
            if str(item.get("provider_id") or "").strip()
        }
        node_results: list[dict[str, Any]] = []
        edge_results: list[dict[str, Any]] = []
        node_run_states: list[dict[str, Any]] = []
        warnings: list[str] = []
        blockers: list[str] = []

        for node_id, node in node_map.items():
            result = self._dry_run_node_result(
                node=node,
                entry_node_ids=entry_node_ids,
                incoming_edges=incoming_edges.get(node_id) or [],
                known_routes=known_routes,
                known_providers=known_providers,
                profile_records_present=bool(profile_records),
                require_live_contract=require_live_contract,
            )
            node_results.append(result)
            if result["status"] == "blocked":
                blockers.extend(result["reasons"])
            elif result["status"] == "warning":
                warnings.extend(result["reasons"])
            node_run_states.append(
                {
                    "node_id": node_id,
                    "run_id": run_id,
                    "status": "dry_run_blocked" if result["status"] == "blocked" else "dry_run_passed",
                    "attempt_count": 0,
                    "started_at": created_at,
                    "updated_at": created_at,
                    "worker_origin": "fixture_runner",
                    "warnings": list(result["reasons"]) if result["status"] == "warning" else [],
                }
            )

        for edge in list(validated_graph.get("edges") or []):
            if not isinstance(edge, dict):
                continue
            result = self._dry_run_edge_result(edge=edge, node_map=node_map)
            edge_results.append(result)
            if result["status"] == "blocked":
                blockers.extend(result["reasons"])
            elif result["status"] == "warning":
                warnings.extend(result["reasons"])
        blockers.extend(list(budget_snapshot.get("static_blockers") or []))

        overall_status = "blocked" if blockers else "warning" if warnings else "pass"
        graph_reasons = blockers if blockers else warnings
        relative_artifact_root = Path("PRIVATE") / "task-graph" / "dry-run" / run_id
        artifact_root = Path(workspace_root) / relative_artifact_root
        summary_json_path = artifact_root / "summary.json"
        report_md_path = artifact_root / "report.md"
        compiled_plan_path = artifact_root / "compiled-plan.json"
        report_payload = {
            "schema_version": TASK_GRAPH_DRY_RUN_SCHEMA_VERSION,
            "run_id": run_id,
            "graph_id": validated_graph["graph_id"],
            "task_id": validated_graph["task_id"],
            "created_at": created_at,
            "overall_status": overall_status,
            "status_counts": _dry_run_status_counts(node_results=node_results, edge_results=edge_results),
            "graph_result": {
                "status": overall_status,
                "reasons": graph_reasons,
            },
            "node_results": node_results,
            "edge_results": edge_results,
            "artifact_paths": {
                "summary_json": summary_json_path.relative_to(workspace_root).as_posix(),
                "report_md": report_md_path.relative_to(workspace_root).as_posix(),
                "compiled_plan_json": compiled_plan_path.relative_to(workspace_root).as_posix(),
            },
            "compiled_plan_summary": dict(compiled_plan.get("topology") or {}),
            "budget": budget_snapshot,
        }
        write_json(summary_json_path, report_payload)
        write_json(compiled_plan_path, compiled_plan)
        report_md_path.parent.mkdir(parents=True, exist_ok=True)
        report_md_path.write_text(self._dry_run_report_markdown(report_payload), encoding="utf-8")
        source_node_id = entry_node_ids[0] if entry_node_ids else next(iter(node_map), "graph")
        artifact_refs = [
            {
                "artifact_id": f"{run_id}-summary-json",
                "artifact_kind": "structured_json",
                "task_id": validated_graph["task_id"],
                "run_id": run_id,
                "source_node_id": source_node_id,
                "path": summary_json_path.relative_to(workspace_root).as_posix(),
                "media_type": "application/json",
                "status": "ready",
                "created_at": created_at,
            },
            {
                "artifact_id": f"{run_id}-report-md",
                "artifact_kind": "validation_report",
                "task_id": validated_graph["task_id"],
                "run_id": run_id,
                "source_node_id": source_node_id,
                "path": report_md_path.relative_to(workspace_root).as_posix(),
                "media_type": "text/markdown",
                "status": "ready",
                "created_at": created_at,
            },
            {
                "artifact_id": f"{run_id}-compiled-plan-json",
                "artifact_kind": "graph_definition",
                "task_id": validated_graph["task_id"],
                "run_id": run_id,
                "source_node_id": source_node_id,
                "path": compiled_plan_path.relative_to(workspace_root).as_posix(),
                "media_type": "application/json",
                "status": "ready",
                "created_at": created_at,
            },
        ]
        run = {
            "schema_version": "astrabridge-task-graph-run-v1",
            "run_id": run_id,
            "graph_id": validated_graph["graph_id"],
            "task_id": validated_graph["task_id"],
            "trace_id": f"trace-{run_id}",
            "context_id": f"context-{run_id}",
            "status": "dry_run_blocked" if overall_status == "blocked" else "dry_run_passed",
            "entry_node_ids": entry_node_ids,
            "node_run_states": node_run_states,
            "artifact_refs": artifact_refs,
            "event_refs": [
                {
                    "event_id": f"{run_id}-created",
                    "run_id": run_id,
                    "task_id": validated_graph["task_id"],
                    "trace_id": f"trace-{run_id}",
                    "event_type": "run_created",
                    "created_at": created_at,
                    "summary": "Dry-run created.",
                },
                {
                    "event_id": f"{run_id}-started",
                    "run_id": run_id,
                    "task_id": validated_graph["task_id"],
                    "trace_id": f"trace-{run_id}",
                    "event_type": "run_dry_run_started",
                    "created_at": created_at,
                    "summary": "Dry-run validation started.",
                },
                {
                    "event_id": f"{run_id}-completed",
                    "run_id": run_id,
                    "task_id": validated_graph["task_id"],
                    "trace_id": f"trace-{run_id}",
                    "event_type": "run_dry_run_completed",
                    "created_at": created_at,
                    "summary": f"Dry-run completed with overall status {overall_status}.",
                },
            ],
            "approval_state": {"status": "not_required"},
            "run_policy_snapshot": {
                "mode": "dry_run",
                "overall_status": overall_status,
                "blocker_count": len(blockers),
                "warning_count": len(warnings),
                "max_parallelism": int(dict(compiled_plan.get("topology") or {}).get("max_parallelism") or 1),
                "budget": budget_snapshot,
            },
            "created_at": created_at,
            "updated_at": created_at,
            "state_version": 1,
        }
        validated_run = validate_task_graph_run(run, graph_definition=validated_graph, workspace_root=workspace_root)
        compact_ref = self.record_graph_run(validated_run, graph_definition=validated_graph)
        return {
            "schema_version": TASK_GRAPH_DRY_RUN_SCHEMA_VERSION,
            "dry_run": {
                **report_payload,
                "run_status": validated_run["status"],
                "artifact_refs": artifact_refs,
                "run_ref": compact_ref,
                "compiled_plan": compiled_plan,
            },
            "graph": validated_graph,
            "task": self.task_view(self.current_task()),
        }

    def execute_fixture_graph(self, payload: dict[str, Any]) -> dict[str, Any]:
        task = self.current_task()
        if not task:
            raise ValueError("No current task.")
        if not isinstance(payload, dict):
            raise TypeError("Task graph fixture-run payload must be a dict.")
        graph_id = str(payload.get("graph_id") or "").strip()
        if not graph_id:
            raise ValueError("graph_id is required.")
        graph = self.graph_definition(graph_id)
        if not graph:
            raise ValueError("Graph not found.")
        validated_graph = validate_graph_definition(graph)
        template_id = str(validated_graph.get("template_id") or "").strip()
        execution_mode = str(payload.get("execution_mode") or "default").strip().lower() or "default"
        if execution_mode not in {"default", "cancellable"}:
            raise ValueError("execution_mode must be default or cancellable.")
        if template_id == "fanout_fanin_research":
            if execution_mode == "cancellable":
                return self._start_cancellable_fanout_fixture_graph(payload=payload, task=task, validated_graph=validated_graph)
        return self._execute_compiled_fixture_graph(payload=payload, task=task, validated_graph=validated_graph)

    def _execute_compiled_fixture_graph(
        self,
        *,
        payload: dict[str, Any],
        task: dict[str, Any],
        validated_graph: dict[str, Any],
        recovery_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        run_id = new_id("graph-run-fixture")
        created_at = now_iso()
        workspace_root = self._projects.require_workspace_root()
        relative_artifact_root = Path("PRIVATE") / "task-graph" / "fixture-run" / run_id
        artifact_root = Path(workspace_root) / relative_artifact_root
        artifact_root.mkdir(parents=True, exist_ok=True)
        summary_json_path = artifact_root / "summary.json"
        report_md_path = artifact_root / "report.md"
        compiled_plan_path = artifact_root / "compiled-plan.json"
        run_manifest_path = artifact_root / "run-manifest.json"

        orchestration_graph = self._orchestration_graph_for_task_graph(validated_graph)
        compiled_plan = compile_agent_orchestration_graph(
            orchestration_graph,
            known_model_capabilities=self._known_model_capabilities_for_graph(orchestration_graph),
        )
        write_json(compiled_plan_path, compiled_plan)
        budget_snapshot = self._graph_run_budget_snapshot(
            graph=validated_graph,
            compiled_plan=compiled_plan,
            run_budget=dict(payload.get("budget") or {}) if isinstance(payload.get("budget"), dict) else None,
        )

        node_behavior_overrides = self._fixture_node_behavior_overrides(payload)
        node_map = {
            str(item.get("node_id") or "").strip(): dict(item)
            for item in list(validated_graph.get("nodes") or [])
            if isinstance(item, dict) and str(item.get("node_id") or "").strip()
        }
        compiled_nodes = {
            str(item.get("node_id") or "").strip(): dict(item)
            for item in list(compiled_plan.get("nodes") or [])
            if isinstance(item, dict) and str(item.get("node_id") or "").strip()
        }
        incoming_by_node: dict[str, list[dict[str, Any]]] = {}
        for edge in list(compiled_plan.get("edges") or []):
            if not isinstance(edge, dict):
                continue
            to_node_id = str(edge.get("to_node_id") or "").strip()
            incoming_by_node.setdefault(to_node_id, []).append(dict(edge))

        recovery_context = dict(recovery_context or {})
        preloaded_node_states = {
            str(node_id).strip(): dict(state)
            for node_id, state in dict(recovery_context.get("preloaded_node_states") or {}).items()
            if str(node_id).strip() and isinstance(state, dict)
        }
        node_states: dict[str, dict[str, Any]] = dict(preloaded_node_states)
        node_results: list[dict[str, Any]] = []
        event_refs: list[dict[str, Any]] = [
            {
                "event_id": f"{run_id}-created",
                "run_id": run_id,
                "task_id": validated_graph["task_id"],
                "trace_id": f"trace-{run_id}",
                "event_type": "run_created",
                "created_at": created_at,
                "summary": f"{validated_graph['title']} compiled fixture run created.",
            }
        ]
        for node_id in [str(item).strip() for item in list(recovery_context.get("reused_node_ids") or []) if str(item or "").strip()]:
            if node_id not in node_states:
                continue
            node_state = dict(node_states.get(node_id) or {})
            node_results.append(
                {
                    "node_id": node_id,
                    "label": self._graph_node_label(validated_graph, node_id),
                    "outcome": str(node_state.get("outcome") or ""),
                    "status": str(node_state.get("status") or ""),
                    "reasons": list(node_state.get("reasons") or []),
                }
            )
            event_refs.append(
                {
                    "event_id": f"{run_id}-{node_id}-reused",
                    "run_id": run_id,
                    "task_id": validated_graph["task_id"],
                    "trace_id": f"trace-{run_id}",
                    "event_type": "node_progress",
                    "created_at": created_at,
                    "summary": f"{self._graph_node_label(validated_graph, node_id)} reused preserved output from source run {str(recovery_context.get('source_run_id') or '').strip()}.",
                    "node_id": node_id,
                    "status": "completed",
                }
            )
        approval_state: dict[str, Any] = {"status": "not_required"}
        terminal_stop = False
        parallel_groups = [dict(group) for group in list(compiled_plan.get("parallel_groups") or []) if isinstance(group, dict)]
        for group_index, group in enumerate(parallel_groups):
            if terminal_stop:
                break
            group_id = str(group.get("group_id") or "").strip() or f"group_{group_index}"
            group_node_ids = [
                str(item).strip()
                for item in list(group.get("node_ids") or [])
                if str(item or "").strip() and str(item).strip() not in node_states
            ]
            group_started_at = self._fixture_offset_iso(created_at, milliseconds=group_index * 1000)
            pending_group_states: list[tuple[str, dict[str, Any], dict[str, Any], dict[str, Any]]] = []
            for node_index, node_id in enumerate(group_node_ids):
                compiled_node = dict(compiled_nodes.get(str(node_id) or "") or {})
                graph_node = dict(node_map.get(str(node_id) or "") or {})
                label = self._graph_node_label(validated_graph, str(node_id))
                dependency_node_ids = [str(item).strip() for item in list(compiled_node.get("dependency_node_ids") or []) if str(item or "").strip()]
                dependency_states = [dict(node_states.get(dep_id) or {}) for dep_id in dependency_node_ids if isinstance(node_states.get(dep_id), dict)]
                node_state = self._compiled_fixture_node_state(
                    graph_node=graph_node,
                    compiled_node=compiled_node,
                    node_behavior_overrides=node_behavior_overrides,
                    dependency_states=dependency_states,
                    created_at=created_at,
                )
                elapsed_ms = self._compiled_fixture_elapsed_ms(node_state=node_state, node_index=node_index)
                node_state["started_at"] = group_started_at
                node_state["updated_at"] = self._fixture_offset_iso(group_started_at, milliseconds=elapsed_ms)
                node_state["elapsed_ms"] = elapsed_ms
                node_state["parallel_group_id"] = group_id
                node_state["join_mode"] = str(compiled_node.get("join_mode") or "").strip() or None
                node_states[str(node_id)] = node_state
                pending_group_states.append((str(node_id), compiled_node, graph_node, node_state))
            for node_id, compiled_node, graph_node, node_state in pending_group_states:
                label = self._graph_node_label(validated_graph, str(node_id))
                node_results.append(
                    {
                        "node_id": str(node_id),
                        "label": label,
                        "outcome": str(node_state.get("outcome") or ""),
                        "status": str(node_state.get("status") or ""),
                        "reasons": list(node_state.get("reasons") or []),
                    }
                )
                if str(node_state.get("status") or "") == "waiting_on_approval":
                    event_refs.append(
                        {
                            "event_id": f"{run_id}-{node_id}-approval-requested",
                            "run_id": run_id,
                            "task_id": validated_graph["task_id"],
                            "trace_id": f"trace-{run_id}",
                            "event_type": "approval_requested",
                            "created_at": str(node_state.get("updated_at") or group_started_at),
                            "summary": str(node_state.get("summary") or f"{label} is waiting on approval."),
                            "node_id": str(node_id),
                            "parallel_group_id": group_id,
                            "elapsed_ms": int(node_state.get("elapsed_ms") or 0),
                        }
                    )
                    approval_state = self._compiled_fixture_approval_state(
                        graph_node=graph_node,
                        node_id=str(node_id),
                        run_id=run_id,
                        created_at=str(node_state.get("updated_at") or group_started_at),
                    )
                    terminal_stop = True
                    break
                dependency_node_ids = [str(item).strip() for item in list(compiled_node.get("dependency_node_ids") or []) if str(item or "").strip()]
                if dependency_node_ids:
                    dependency_outcomes = [
                        str(dict(node_states.get(dep_id) or {}).get("outcome") or "").strip() or "unknown"
                        for dep_id in dependency_node_ids
                    ]
                    event_refs.append(
                        {
                            "event_id": f"{run_id}-{node_id}-join-ready",
                            "run_id": run_id,
                            "task_id": validated_graph["task_id"],
                            "trace_id": f"trace-{run_id}",
                            "event_type": "node_progress",
                            "created_at": self._fixture_offset_iso(str(node_state.get("started_at") or group_started_at), milliseconds=-50),
                            "summary": (
                                f"{label} satisfied join `{str(compiled_node.get('join_mode') or 'all_required')}` "
                                f"after dependencies {', '.join(dependency_node_ids)} resolved as {', '.join(dependency_outcomes)}."
                            ),
                            "node_id": str(node_id),
                            "parallel_group_id": group_id,
                        }
                    )
                event_refs.append(
                    {
                        "event_id": f"{run_id}-{node_id}-started",
                        "run_id": run_id,
                        "task_id": validated_graph["task_id"],
                        "trace_id": f"trace-{run_id}",
                        "event_type": "node_started",
                        "created_at": str(node_state.get("started_at") or group_started_at),
                        "summary": f"{label} fixture execution started.",
                        "node_id": str(node_id),
                        "parallel_group_id": group_id,
                    }
                )
                event_refs.append(
                    {
                        "event_id": f"{run_id}-{node_id}-{self._compiled_fixture_event_suffix(str(node_state.get('status') or 'completed'))}",
                        "run_id": run_id,
                        "task_id": validated_graph["task_id"],
                        "trace_id": f"trace-{run_id}",
                        "event_type": self._compiled_fixture_event_type(str(node_state.get("status") or "")),
                        "created_at": str(node_state.get("updated_at") or group_started_at),
                        "summary": str(node_state.get("summary") or f"{label} fixture execution finished."),
                        "node_id": str(node_id),
                        "parallel_group_id": group_id,
                        "elapsed_ms": int(node_state.get("elapsed_ms") or 0),
                    }
                )

        unresolved_nodes = [
            node_id
            for node_id in compiled_nodes
            if node_id not in node_states
        ]
        for node_id in unresolved_nodes:
            label = self._graph_node_label(validated_graph, node_id)
            node_states[node_id] = {
                "status": "blocked",
                "outcome": "blocked",
                "reasons": ["Node could not start because upstream dependencies did not produce a runnable handoff."],
                "worker_origin": "fixture_runner",
                "attempt_count": 0,
                "started_at": self._fixture_offset_iso(created_at, milliseconds=len(parallel_groups) * 1000),
                "updated_at": self._fixture_offset_iso(created_at, milliseconds=len(parallel_groups) * 1000),
                "elapsed_ms": 0,
                "summary": f"{label} did not run because upstream dependencies never produced a runnable handoff.",
                "machine_result": {
                    "node_id": node_id,
                    "status": "blocked",
                    "reason": "unrunnable_dependencies",
                },
                "next_action_hints": ["Fix upstream node outcomes or handoff contracts before rerunning this graph."],
            }
            node_results.append(
                {
                    "node_id": node_id,
                    "label": label,
                    "outcome": "blocked",
                    "status": "blocked",
                    "reasons": ["Node could not start because upstream dependencies did not produce a runnable handoff."],
                }
            )
            event_refs.append(
                {
                    "event_id": f"{run_id}-{node_id}-blocked-unstarted",
                    "run_id": run_id,
                    "task_id": validated_graph["task_id"],
                    "trace_id": f"trace-{run_id}",
                    "event_type": "node_blocked",
                    "created_at": self._fixture_offset_iso(created_at, milliseconds=len(parallel_groups) * 1000),
                    "summary": f"{label} remained blocked because no runnable upstream dependency set was available.",
                    "node_id": node_id,
                }
            )

        final_updated_at = max(
            [created_at, *[str(dict(state).get("updated_at") or created_at) for state in node_states.values() if isinstance(state, dict)]]
        )
        run_status = self._compiled_fixture_run_status(node_states=node_states, approval_state=approval_state)
        if run_status == "completed":
            event_refs.append(
                {
                    "event_id": f"{run_id}-completed",
                    "run_id": run_id,
                    "task_id": validated_graph["task_id"],
                    "trace_id": f"trace-{run_id}",
                    "event_type": "run_completed",
                    "created_at": final_updated_at,
                    "summary": f"{validated_graph['title']} compiled fixture run completed.",
                }
            )
        elif run_status in {"failed", "partial"}:
            event_refs.append(
                {
                    "event_id": f"{run_id}-terminal",
                    "run_id": run_id,
                    "task_id": validated_graph["task_id"],
                    "trace_id": f"trace-{run_id}",
                    "event_type": "run_failed" if run_status == "failed" else "run_completed",
                    "created_at": final_updated_at,
                    "summary": f"{validated_graph['title']} compiled fixture run finished with status {run_status}.",
                }
            )

        report_payload = {
            "schema_version": "astrabridge-task-graph-fixture-run-v1",
            "run_id": run_id,
            "graph_id": validated_graph["graph_id"],
            "task_id": validated_graph["task_id"],
            "created_at": created_at,
            "template_id": validated_graph["template_id"],
            "run_status": run_status,
            "node_results": node_results,
            "artifact_paths": {
                "summary_json": summary_json_path.relative_to(workspace_root).as_posix(),
                "report_md": report_md_path.relative_to(workspace_root).as_posix(),
                "compiled_plan_json": compiled_plan_path.relative_to(workspace_root).as_posix(),
                "run_manifest_json": run_manifest_path.relative_to(workspace_root).as_posix(),
            },
            "compiled_plan_summary": dict(compiled_plan.get("topology") or {}),
        }
        if recovery_context:
            report_payload["recovery"] = {
                "recovery_id": str(recovery_context.get("recovery_id") or "").strip(),
                "source_run_id": str(recovery_context.get("source_run_id") or "").strip(),
                "strategy": str(recovery_context.get("strategy") or "").strip(),
                "selected_node_ids": [str(item).strip() for item in list(recovery_context.get("selected_node_ids") or []) if str(item or "").strip()],
                "rerun_node_ids": [str(item).strip() for item in list(recovery_context.get("rerun_node_ids") or []) if str(item or "").strip()],
                "reused_node_ids": [str(item).strip() for item in list(recovery_context.get("reused_node_ids") or []) if str(item or "").strip()],
            }
        write_json(summary_json_path, report_payload)
        report_md_path.write_text(self._fixture_run_report_markdown(report_payload), encoding="utf-8")

        node_run_states = [
            {
                "node_id": node_id,
                "run_id": run_id,
                "status": str(state.get("status") or ""),
                "outcome": str(state.get("outcome") or ""),
                "attempt_count": int(state.get("attempt_count") or 0),
                "started_at": str(state.get("started_at") or created_at),
                "updated_at": str(state.get("updated_at") or created_at),
                "worker_origin": state.get("worker_origin"),
                "warnings": list(state.get("reasons") or []),
                "parallel_group_id": state.get("parallel_group_id"),
                "join_mode": state.get("join_mode"),
                "elapsed_ms": int(state.get("elapsed_ms") or 0),
                "reused_from_run_id": str(state.get("reused_from_run_id") or "").strip() or None,
                "worker_thread_id": f"fixture-{node_id}-{run_id}" if self._compiled_fixture_should_persist_worker_output(compiled_node=dict(compiled_nodes.get(node_id) or {})) or str(state.get("status") or "") == "waiting_on_approval" else None,
                "parent_thread_id": str(task.get("active_provider_thread_id") or "") if self._compiled_fixture_should_persist_worker_output(compiled_node=dict(compiled_nodes.get(node_id) or {})) or str(state.get("status") or "") == "waiting_on_approval" else None,
                "spawn_mode": "manual_only" if str(state.get("status") or "") == "waiting_on_approval" else ("isolated_lane" if self._compiled_fixture_should_persist_worker_output(compiled_node=dict(compiled_nodes.get(node_id) or {})) else None),
                "agent_role": str(dict(node_map.get(node_id) or {}).get("kind") or "worker") if self._compiled_fixture_should_persist_worker_output(compiled_node=dict(compiled_nodes.get(node_id) or {})) or str(state.get("status") or "") == "waiting_on_approval" else None,
                "agent_nickname": self._graph_node_label(validated_graph, node_id) if self._compiled_fixture_should_persist_worker_output(compiled_node=dict(compiled_nodes.get(node_id) or {})) or str(state.get("status") or "") == "waiting_on_approval" else None,
                "execution_backend": "human_review" if str(state.get("status") or "") == "waiting_on_approval" else ("fixture_runner" if self._compiled_fixture_should_persist_worker_output(compiled_node=dict(compiled_nodes.get(node_id) or {})) else None),
            }
            for node_id, state in node_states.items()
        ]
        artifact_refs = [
            {
                "artifact_id": f"{run_id}-summary-json",
                "artifact_kind": "structured_json",
                "task_id": validated_graph["task_id"],
                "run_id": run_id,
                "source_node_id": str(compiled_plan.get("entry_node_ids") or [next(iter(node_map), "")])[0],
                "path": summary_json_path.relative_to(workspace_root).as_posix(),
                "media_type": "application/json",
                "status": "ready",
                "created_at": created_at,
            },
            {
                "artifact_id": f"{run_id}-report-md",
                "artifact_kind": "run_summary",
                "task_id": validated_graph["task_id"],
                "run_id": run_id,
                "source_node_id": str(compiled_plan.get("entry_node_ids") or [next(iter(node_map), "")])[-1],
                "path": report_md_path.relative_to(workspace_root).as_posix(),
                "media_type": "text/markdown",
                "status": "ready",
                "created_at": created_at,
            },
            {
                "artifact_id": f"{run_id}-compiled-plan-json",
                "artifact_kind": "graph_definition",
                "task_id": validated_graph["task_id"],
                "run_id": run_id,
                "source_node_id": str(compiled_plan.get("entry_node_ids") or [next(iter(node_map), "")])[0],
                "path": compiled_plan_path.relative_to(workspace_root).as_posix(),
                "media_type": "application/json",
                "status": "ready",
                "created_at": created_at,
            },
            {
                "artifact_id": f"{run_id}-run-manifest-json",
                "artifact_kind": "structured_json",
                "task_id": validated_graph["task_id"],
                "run_id": run_id,
                "source_node_id": str(compiled_plan.get("entry_node_ids") or [next(iter(node_map), "")])[0],
                "path": run_manifest_path.relative_to(workspace_root).as_posix(),
                "media_type": "application/json",
                "status": "ready",
                "created_at": created_at,
            },
        ]
        run = {
            "schema_version": "astrabridge-task-graph-run-v1",
            "run_id": run_id,
            "graph_id": validated_graph["graph_id"],
            "task_id": validated_graph["task_id"],
            "trace_id": f"trace-{run_id}",
            "context_id": f"context-{run_id}",
            "status": run_status,
            "entry_node_ids": list(compiled_plan.get("entry_node_ids") or []),
            "node_run_states": node_run_states,
            "artifact_refs": artifact_refs,
            "event_refs": event_refs,
            "approval_state": approval_state,
            "run_policy_snapshot": {
                "mode": "fixture_run",
                "scheduler": "compiled_graph_mvp",
                "template_id": str(validated_graph.get("template_id") or ""),
                "parallel_group_count": int(dict(compiled_plan.get("topology") or {}).get("parallel_group_count") or 0),
                "max_parallelism": max((len(list(dict(group).get("node_ids") or [])) for group in list(compiled_plan.get("parallel_groups") or [])), default=1),
                "execution_mode": "default",
                "compatibility_shim": False,
                "parallel_group_ids": [str(dict(group).get("group_id") or "").strip() for group in parallel_groups if str(dict(group).get("group_id") or "").strip()],
                "budget": budget_snapshot,
                "recovery": (
                    {
                        "recovery_id": str(recovery_context.get("recovery_id") or "").strip(),
                        "source_run_id": str(recovery_context.get("source_run_id") or "").strip(),
                        "strategy": str(recovery_context.get("strategy") or "").strip(),
                        "selected_node_ids": [str(item).strip() for item in list(recovery_context.get("selected_node_ids") or []) if str(item or "").strip()],
                        "rerun_node_ids": [str(item).strip() for item in list(recovery_context.get("rerun_node_ids") or []) if str(item or "").strip()],
                        "reused_node_ids": [str(item).strip() for item in list(recovery_context.get("reused_node_ids") or []) if str(item or "").strip()],
                    }
                    if recovery_context
                    else None
                ),
            },
            "compiled_plan": {
                "schema_version": str(compiled_plan.get("schema_version") or ""),
                "topology": dict(compiled_plan.get("topology") or {}),
                "parallel_groups": list(compiled_plan.get("parallel_groups") or []),
            },
            "created_at": created_at,
            "updated_at": final_updated_at,
            "state_version": 1,
        }
        write_json(run_manifest_path, run)
        validated_run = validate_task_graph_run(run, graph_definition=validated_graph, workspace_root=workspace_root)
        compact_ref = self.record_graph_run(validated_run, graph_definition=validated_graph)

        persisted_worker_bindings: list[dict[str, Any]] = []
        for binding in list(recovery_context.get("preloaded_worker_bindings") or []):
            if not isinstance(binding, dict):
                continue
            cloned = dict(binding)
            cloned["binding_id"] = new_id("graph-worker")
            cloned["run_id"] = run_id
            cloned["reused_from_run_id"] = str(recovery_context.get("source_run_id") or "").strip() or None
            persisted_worker_bindings.append(cloned)
        for node_id, state in node_states.items():
            compiled_node = dict(compiled_nodes.get(node_id) or {})
            status = str(state.get("status") or "")
            if bool(state.get("reused_existing_output")):
                continue
            if status == "waiting_on_approval":
                self.record_graph_worker(
                    {
                        "graph_id": str(validated_graph.get("graph_id") or ""),
                        "run_id": run_id,
                        "node_id": node_id,
                        "worker_thread_id": f"fixture-{node_id}-{run_id}",
                        "parent_thread_id": str(task.get("active_provider_thread_id") or ""),
                        "spawn_mode": "manual_only",
                        "worker_origin": "manual",
                        "agent_role": str(dict(node_map.get(node_id) or {}).get("kind") or "gate"),
                        "agent_nickname": self._graph_node_label(validated_graph, node_id),
                        "status": "waiting_on_approval",
                        "execution_backend": "human_review",
                        "created_at": created_at,
                        "updated_at": created_at,
                    },
                    graph_definition=validated_graph,
                )
                continue
            if not self._compiled_fixture_should_persist_worker_output(compiled_node=compiled_node):
                continue
            output_record = self._record_fixture_worker_output(
                graph=validated_graph,
                run_id=run_id,
                node_id=node_id,
                parent_thread_id=str(task.get("active_provider_thread_id") or ""),
                created_at=str(state.get("started_at") or created_at),
                updated_at=str(state.get("updated_at") or created_at),
                behavior=status if status in {"completed", "blocked", "failed", "partial"} else str(state.get("outcome") or "failed"),
                summary=str(state.get("summary") or ""),
                machine_result=dict(state.get("machine_result") or {}),
                next_action_hints=[str(item).strip() for item in list(state.get("next_action_hints") or []) if str(item or "").strip()],
                status=status,
            )
            if isinstance(output_record, dict) and isinstance(output_record.get("worker_binding"), dict):
                persisted_worker_bindings.append(dict(output_record.get("worker_binding") or {}))

        refreshed_task = self.current_task()
        refreshed_task = self._reconcile_fixture_worker_bindings(
            refreshed_task,
            run_id=run_id,
            preferred_bindings=persisted_worker_bindings,
        ) or refreshed_task
        refreshed_run = self.graph_run_ref(run_id)
        report_payload["run_ref"] = refreshed_run or compact_ref
        write_json(summary_json_path, report_payload)
        report_md_path.write_text(self._fixture_run_report_markdown(report_payload), encoding="utf-8")
        return {
            "schema_version": "astrabridge-task-graph-fixture-run-v1",
            "fixture_run": {
                **report_payload,
                "run_ref": refreshed_run or compact_ref,
                "compiled_plan": compiled_plan,
            },
            "graph": validated_graph,
            "task": self.task_view(refreshed_task, compact_graph_runs=True),
        }

    def _fixture_node_behavior_overrides(self, payload: dict[str, Any]) -> dict[str, str]:
        merged: dict[str, str] = {}
        for key in ("node_behaviors", "branch_behaviors"):
            value = payload.get(key)
            if not isinstance(value, dict):
                continue
            for node_id, behavior in value.items():
                clean_node_id = str(node_id or "").strip()
                clean_behavior = str(behavior or "").strip().lower()
                if not clean_node_id:
                    continue
                if clean_behavior not in {"completed", "blocked", "failed"}:
                    raise ValueError("Fixture node behavior must be completed, blocked, or failed.")
                merged[clean_node_id] = clean_behavior
        return merged

    def _compiled_fixture_node_state(
        self,
        *,
        graph_node: dict[str, Any],
        compiled_node: dict[str, Any],
        node_behavior_overrides: dict[str, str],
        dependency_states: list[dict[str, Any]],
        created_at: str,
    ) -> dict[str, Any]:
        del created_at
        node_id = str(compiled_node.get("node_id") or "")
        label = str(compiled_node.get("label") or node_id)
        approval_gate = dict(graph_node.get("approval_gate") or {})
        review_kind = str(approval_gate.get("review_kind") or approval_gate.get("approval_kind") or compiled_node.get("approval_kind") or "").strip()
        explicit_gate = (
            str(dict(compiled_node.get("execution") or {}).get("spawn_mode") or "").strip() == "manual_only"
            or str(graph_node.get("kind") or "").strip() == "gate"
            or review_kind in {"provider_call_gate", "promotion_gate", "human_gate"}
        )
        if explicit_gate:
            review_kind = review_kind or "human_gate"
            return {
                "status": "waiting_on_approval",
                "outcome": "pending",
                "reasons": [f"{label} requires human approval before execution can continue."],
                "worker_origin": "manual",
                "attempt_count": 1,
                "summary": f"{label} requested human approval for `{review_kind}` before continuing the fixture run.",
                "machine_result": {
                    "node_id": node_id,
                    "status": "waiting_on_approval",
                    "review_kind": review_kind,
                },
                "next_action_hints": ["Resolve the approval request before rerunning or continuing this graph."],
            }

        dependency_outcomes = [str(item.get("outcome") or "").strip() for item in dependency_states]
        successful_dependencies = [
            dict(item)
            for item in dependency_states
            if str(item.get("outcome") or "").strip() in {"passed", "partial"}
        ]
        blocked_dependencies = [
            dict(item)
            for item in dependency_states
            if str(item.get("outcome") or "").strip() in {"blocked", "failed", "skipped"}
        ]

        explicit_behavior = node_behavior_overrides.get(node_id)
        if explicit_behavior:
            behavior = explicit_behavior
        elif dependency_states and not successful_dependencies:
            behavior = "blocked"
        elif dependency_states and blocked_dependencies:
            behavior = "partial"
        else:
            behavior = "completed"

        status = self._fixture_behavior_to_node_status(behavior)
        outcome = "passed" if behavior == "completed" else behavior
        if behavior == "partial":
            outcome = "partial"
        reasons: list[str] = []
        if behavior == "blocked" and dependency_states and not successful_dependencies:
            reasons.append("No upstream dependency produced a runnable artifact handoff for this node.")
        elif behavior in {"blocked", "failed"}:
            reasons.append(f"Fixture execution marked {label} as {behavior}.")
        elif behavior == "partial":
            reasons.append("One or more upstream dependencies did not complete successfully; this node merged the remaining declared artifacts only.")

        consumed_worker_artifacts = [
            str(dict(item.get("machine_result") or {}).get("artifact_bundle_path") or "")
            for item in successful_dependencies
            if str(dict(item.get("machine_result") or {}).get("artifact_bundle_path") or "").strip()
        ]
        if successful_dependencies and not consumed_worker_artifacts:
            consumed_worker_artifacts = [
                f"fixture://{str(dict(item.get('machine_result') or {}).get('node_id') or 'upstream')}"
                for item in successful_dependencies
            ]
        summary = self._compiled_fixture_summary(
            label=label,
            behavior=behavior,
            successful_dependencies=successful_dependencies,
            blocked_dependencies=blocked_dependencies,
        )
        machine_result = {
            "node_id": node_id,
            "status": status,
            "outcome": outcome,
            "dependency_outcomes": dependency_outcomes,
            "dependency_node_ids": list(compiled_node.get("dependency_node_ids") or []),
            "parallel_group_id": compiled_node.get("parallel_group_id"),
        }
        if consumed_worker_artifacts:
            machine_result["consumed_worker_artifacts"] = consumed_worker_artifacts

        next_action_hints = (
            ["Deliver the declared artifact bundle to downstream nodes according to edge policy."]
            if str(compiled_node.get("outgoing_edge_ids") or "")
            else ["Inspect the latest artifact bundle from the run view."]
        )
        return {
            "status": status,
            "outcome": outcome,
            "reasons": reasons,
            "worker_origin": "fixture_runner",
            "attempt_count": 1 if status not in {"skipped"} else 0,
            "summary": summary,
            "machine_result": machine_result,
            "next_action_hints": next_action_hints,
        }

    @staticmethod
    def _compiled_fixture_summary(
        *,
        label: str,
        behavior: str,
        successful_dependencies: list[dict[str, Any]],
        blocked_dependencies: list[dict[str, Any]],
    ) -> str:
        if behavior == "completed":
            if successful_dependencies:
                return f"{label} consumed the declared upstream artifacts and completed its bounded fixture execution."
            return f"{label} completed its bounded fixture execution."
        if behavior == "partial":
            return f"{label} merged the available declared upstream artifacts after one dependency did not complete successfully."
        if behavior == "blocked" and blocked_dependencies and not successful_dependencies:
            return f"{label} did not run because upstream dependencies never produced a runnable handoff."
        if behavior == "failed":
            return f"{label} failed its bounded fixture execution."
        return f"{label} was marked {behavior} during fixture execution."

    @staticmethod
    def _compiled_fixture_should_persist_worker_output(*, compiled_node: dict[str, Any]) -> bool:
        kind = str(compiled_node.get("kind") or "").strip()
        dependency_node_ids = [str(item).strip() for item in list(compiled_node.get("dependency_node_ids") or []) if str(item or "").strip()]
        outgoing_edge_ids = [str(item).strip() for item in list(compiled_node.get("outgoing_edge_ids") or []) if str(item or "").strip()]
        if kind == "supervisor" and not dependency_node_ids and len(outgoing_edge_ids) > 1:
            return False
        return True

    @staticmethod
    def _compiled_fixture_event_type(status: str) -> str:
        mapping = {
            "completed": "node_completed",
            "partial": "node_completed",
            "blocked": "node_blocked",
            "failed": "node_failed",
            "skipped": "node_blocked",
        }
        return mapping.get(status, "node_completed")

    @staticmethod
    def _compiled_fixture_event_suffix(status: str) -> str:
        mapping = {
            "completed": "completed",
            "partial": "partial",
            "blocked": "blocked",
            "failed": "failed",
            "skipped": "skipped",
        }
        return mapping.get(status, "completed")

    @staticmethod
    def _compiled_fixture_elapsed_ms(*, node_state: dict[str, Any], node_index: int) -> int:
        status = str(node_state.get("status") or "").strip()
        if status == "waiting_on_approval":
            return 40 + (node_index * 10)
        if status == "failed":
            return 160 + (node_index * 20)
        if status == "blocked":
            return 90 + (node_index * 10)
        if status == "partial":
            return 260 + (node_index * 20)
        return 220 + (node_index * 20)

    @staticmethod
    def _fixture_offset_iso(base: str, *, milliseconds: int) -> str:
        try:
            anchor = dt.datetime.fromisoformat(str(base))
        except Exception:
            anchor = dt.datetime.fromisoformat(now_iso())
        return (anchor + dt.timedelta(milliseconds=milliseconds)).isoformat()

    @staticmethod
    def _later_iso(*values: str, plus_ms: int = 0) -> str:
        anchors: list[dt.datetime] = []
        for value in values:
            text = str(value or "").strip()
            if not text:
                continue
            try:
                anchors.append(dt.datetime.fromisoformat(text))
            except Exception:
                continue
        anchor = max(anchors) if anchors else dt.datetime.fromisoformat(now_iso())
        if plus_ms:
            anchor = anchor + dt.timedelta(milliseconds=plus_ms)
        return anchor.isoformat()

    def _compiled_fixture_approval_state(
        self,
        *,
        graph_node: dict[str, Any],
        node_id: str,
        run_id: str,
        created_at: str,
    ) -> dict[str, Any]:
        approval_gate = dict(graph_node.get("approval_gate") or {})
        review_kind = str(approval_gate.get("review_kind") or approval_gate.get("approval_kind") or "human_gate").strip() or "human_gate"
        reason = str(approval_gate.get("reason") or approval_gate.get("description") or f"{self._graph_node_label({'nodes': [graph_node]}, node_id)} requires human approval before continuing.").strip()
        return {
            "status": "pending",
            "review_kind": review_kind,
            "node_id": node_id,
            "reason": reason,
            "requested_at": created_at,
            "worker_thread_id": f"fixture-{node_id}-{run_id}",
            "allowed_actions": [str(item).strip() for item in list(approval_gate.get("allowed_actions") or []) if str(item or "").strip()] or ["provider_call"],
            "blocked_actions": [str(item).strip() for item in list(approval_gate.get("blocked_actions") or []) if str(item or "").strip()] or ["silent_high_risk_execution"],
        }

    @staticmethod
    def _compiled_fixture_run_status(
        *,
        node_states: dict[str, dict[str, Any]],
        approval_state: dict[str, Any],
    ) -> str:
        if str(approval_state.get("status") or "").strip() == "pending":
            return "paused_for_review"
        statuses = [str(item.get("status") or "").strip() for item in node_states.values()]
        outcomes = [str(item.get("outcome") or "").strip() for item in node_states.values()]
        if "partial" in statuses or "partial" in outcomes:
            return "partial"
        if all(item == "passed" for item in outcomes if item):
            return "completed"
        if any(item in {"blocked", "failed"} for item in outcomes):
            if any(item == "passed" for item in outcomes):
                return "partial"
            return "failed"
        return "completed"

    def _apply_template_node_defaults(self, graph: dict[str, Any], *, configured_models: list[dict[str, Any]] | None = None) -> None:
        template_id = str(graph.get("template_id") or "").strip()
        raw_template_defaults = self._raw_template_node_defaults(template_id)
        template_defaults = self._resolve_template_node_defaults(
            raw_template_defaults,
            configured_models=configured_models,
        )
        node_ui_hints = {
            "supervisor_worker_synthesizer": {
                "node_supervisor": {"context_policy_preset": "task_digest", "artifact_expectation": "Structured plan", "validation_hint": "Define the worker scope before execution."},
                "node_worker": {"context_policy_preset": "artifact_first", "artifact_expectation": "Bounded worker report", "validation_hint": "Check the worker route before dry-run."},
                "node_synth": {"context_policy_preset": "latest_summary_only", "artifact_expectation": "Final run summary", "validation_hint": "Synthesize only declared worker artifacts."},
            },
            "fanout_fanin_research": {
                "node_supervisor": {"context_policy_preset": "task_digest", "artifact_expectation": "Branch brief", "validation_hint": "Keep fan-out branch scopes explicit."},
                "node_research_a": {"context_policy_preset": "artifact_first", "artifact_expectation": "Branch A research note", "validation_hint": "Branch outputs should stay attributable."},
                "node_research_b": {"context_policy_preset": "artifact_first", "artifact_expectation": "Branch B research note", "validation_hint": "Branch outputs should stay attributable."},
                "node_merge": {"context_policy_preset": "latest_summary_only", "artifact_expectation": "Merged synthesis", "validation_hint": "Consume only declared branch artifacts."},
            },
            "code_fix_test_review": {
                "node_plan_fix": {"context_policy_preset": "task_digest", "artifact_expectation": "Fix plan", "validation_hint": "List target files before code change."},
                "node_code_fix": {"context_policy_preset": "artifact_first", "artifact_expectation": "Code diff", "validation_hint": "Keep writes bounded to approved files."},
                "node_test": {"context_policy_preset": "artifact_first", "artifact_expectation": "Test report", "validation_hint": "Run tests against the declared diff only."},
                "node_review": {"context_policy_preset": "latest_summary_only", "artifact_expectation": "Review report", "validation_hint": "Review outcome should reference test evidence."},
            },
            "provider_update_smoke_gate": {
                "node_discover": {"context_policy_preset": "task_digest", "artifact_expectation": "Provider diff bundle", "validation_hint": "Capture only bounded provider changes."},
                "node_smoke": {"context_policy_preset": "artifact_first", "artifact_expectation": "Smoke matrix", "validation_hint": "Dry-run should surface blocked provider cases."},
                "node_gate": {"context_policy_preset": "latest_summary_only", "artifact_expectation": "Promotion decision record", "validation_hint": "Promotion remains gated until review."},
            },
            "document_extract_analyze_report": {
                "node_extract": {"context_policy_preset": "artifact_first", "artifact_expectation": "Document extract", "validation_hint": "Keep source extraction bounded to the declared input."},
                "node_analyze": {"context_policy_preset": "artifact_first", "artifact_expectation": "Structured analysis", "validation_hint": "Analysis must consume only declared extract artifacts."},
                "node_report": {"context_policy_preset": "latest_summary_only", "artifact_expectation": "Final report", "validation_hint": "Report output should cite the extract and analysis."},
            },
            "multimodal_capability_adapter": {
                "node_probe_input": {"context_policy_preset": "task_digest", "artifact_expectation": "Capability probe", "validation_hint": "Capture the model's supported input modes before adaptation."},
                "node_adapt_contract": {"context_policy_preset": "artifact_first", "artifact_expectation": "Adapted multimodal contract", "validation_hint": "Keep the fallback contract explicit and bounded."},
                "node_verify_output": {"context_policy_preset": "latest_summary_only", "artifact_expectation": "Fallback validation report", "validation_hint": "Verify declared output modes and fallback paths before live use."},
            },
            "custom_blank_graph": {
                "node_start_here": {"context_policy_preset": "task_digest", "artifact_expectation": "Starter graph manifest", "validation_hint": "Rename the seed node and add downstream roles before dry-run."},
            },
        }.get(template_id, {})
        available_by_provider: dict[str, set[str]] = {}
        preferred_by_provider: dict[str, str] = {}

        def available_models_for(provider_id: str) -> set[str]:
            cached = available_by_provider.get(provider_id)
            if cached is not None:
                return cached
            cached = {
                str(item.get("native_model") or "").strip()
                for item in provider_model_records(
                    provider_id,
                    configured_models or [],
                    include_disabled=False,
                    include_deprecated=False,
                )
                if str(item.get("native_model") or "").strip()
            }
            available_by_provider[provider_id] = cached
            return cached

        def preferred_model_for(provider_id: str) -> str:
            cached = preferred_by_provider.get(provider_id)
            if cached is not None:
                return cached
            preferred = preferred_provider_model_record(
                provider_id,
                configured_models or [],
                include_deprecated=False,
            )
            cached = str((preferred or {}).get("native_model") or "").strip()
            preferred_by_provider[provider_id] = cached
            return cached

        for node in list(graph.get("nodes") or []):
            if not isinstance(node, dict):
                continue
            node_id = str(node.get("node_id") or "").strip()
            defaults = dict(template_defaults.get(node_id) or {})
            raw_defaults = dict(raw_template_defaults.get(node_id) or {})
            for key, value in defaults.items():
                if value is not None and not str(node.get(key) or "").strip():
                    node[key] = value
            provider_id = str(node.get("provider_id") or defaults.get("provider_id") or "").strip()
            model_id = str(node.get("model_id") or "").strip()
            if configured_models is not None and provider_id:
                available_models = available_models_for(provider_id)
                preferred_model = preferred_model_for(provider_id)
                if preferred_model and model_id and available_models and model_id not in available_models:
                    node["provider_id"] = provider_id
                    node["model_id"] = preferred_model
                    if not str(node.get("reasoning_effort") or "").strip():
                        node["reasoning_effort"] = str(defaults.get("reasoning_effort") or raw_defaults.get("reasoning_effort") or "").strip() or None
            if "permission_mode" not in node:
                node["permission_mode"] = "ask"
            if "collaboration_mode" not in node:
                node["collaboration_mode"] = "default"
            if "execution_backend" not in node:
                node["execution_backend"] = "app_server"
            merged_ui_hints = dict(node.get("ui_hints") or {})
            merged_ui_hints.update(node_ui_hints.get(node_id) or {})
            metadata = GRAPH_TEMPLATE_PRODUCT_METADATA.get(template_id) or {}
            merged_ui_hints.setdefault("recommended_provider_ids", list(metadata.get("recommended_provider_ids") or []))
            merged_ui_hints.setdefault("recommended_model_ids", list(metadata.get("recommended_model_ids") or []))
            node["ui_hints"] = merged_ui_hints

    def _resolve_template_node_defaults(
        self,
        template_defaults: dict[str, dict[str, Any]],
        *,
        configured_models: list[dict[str, Any]] | None = None,
    ) -> dict[str, dict[str, Any]]:
        if configured_models is None:
            return {node_id: dict(defaults or {}) for node_id, defaults in template_defaults.items()}
        resolved: dict[str, dict[str, Any]] = {}
        available_by_provider: dict[str, set[str]] = {}
        for node_id, defaults in template_defaults.items():
            normalized = dict(defaults or {})
            provider_id = str(normalized.get("provider_id") or "").strip()
            model_id = str(normalized.get("model_id") or "").strip()
            if provider_id and model_id:
                available_models = available_by_provider.get(provider_id)
                if available_models is None:
                    available_models = {
                        str(item.get("native_model") or "").strip()
                        for item in provider_model_records(
                            provider_id,
                            configured_models,
                            include_disabled=False,
                            include_deprecated=False,
                        )
                        if str(item.get("native_model") or "").strip()
                    }
                    available_by_provider[provider_id] = available_models
                if available_models and model_id not in available_models:
                    preferred = preferred_provider_model_record(
                        provider_id,
                        configured_models,
                        include_deprecated=False,
                    )
                    preferred_model = str((preferred or {}).get("native_model") or "").strip()
                    if preferred_model:
                        normalized["model_id"] = preferred_model
            resolved[node_id] = normalized
        return resolved

    @staticmethod
    def _raw_template_node_defaults(template_id: str) -> dict[str, dict[str, Any]]:
        return {
            "supervisor_worker_synthesizer": {
                "node_supervisor": {"provider_id": "qwen", "model_id": "qwen3-coder-plus", "reasoning_effort": "medium"},
                "node_worker": {"provider_id": "qwen", "model_id": "qwen3-coder-plus", "reasoning_effort": "high"},
                "node_synth": {"provider_id": "kimi", "model_id": "kimi-k2.6", "reasoning_effort": "medium"},
            },
            "fanout_fanin_research": {
                "node_supervisor": {"provider_id": "qwen", "model_id": "qwen3-coder-plus", "reasoning_effort": "medium"},
                "node_research_a": {"provider_id": "qwen", "model_id": "qwen3-coder-plus", "reasoning_effort": "high"},
                "node_research_b": {"provider_id": "kimi", "model_id": "kimi-k2.6", "reasoning_effort": "high"},
                "node_merge": {"provider_id": "kimi", "model_id": "kimi-k2.6", "reasoning_effort": "medium"},
            },
            "code_fix_test_review": {
                "node_plan_fix": {"provider_id": "qwen", "model_id": "qwen3-coder-plus", "reasoning_effort": "medium"},
                "node_code_fix": {"provider_id": "qwen", "model_id": "qwen3-coder-plus", "reasoning_effort": "high"},
                "node_test": {"provider_id": "deepseek", "model_id": "deepseek-coder", "reasoning_effort": "medium"},
                "node_review": {"provider_id": "kimi", "model_id": "kimi-k2.6", "reasoning_effort": "medium"},
            },
            "provider_update_smoke_gate": {
                "node_discover": {"provider_id": "qwen", "model_id": "qwen3-coder-plus", "reasoning_effort": "medium"},
                "node_smoke": {"provider_id": "glm", "model_id": "glm-4.5", "reasoning_effort": "medium"},
            },
            "document_extract_analyze_report": {
                "node_extract": {"provider_id": "qwen", "model_id": "qwen3-coder-plus", "reasoning_effort": "medium"},
                "node_analyze": {"provider_id": "glm", "model_id": "glm-4.5", "reasoning_effort": "high"},
                "node_report": {"provider_id": "kimi", "model_id": "kimi-k2.6", "reasoning_effort": "medium"},
            },
            "multimodal_capability_adapter": {
                "node_probe_input": {"provider_id": "qwen", "model_id": "qwen3-coder-plus", "reasoning_effort": "medium"},
                "node_adapt_contract": {"provider_id": "glm", "model_id": "glm-4.5", "reasoning_effort": "high"},
                "node_verify_output": {"provider_id": "kimi", "model_id": "kimi-k2.6", "reasoning_effort": "medium"},
            },
            "custom_blank_graph": {
                "node_start_here": {"provider_id": "qwen", "model_id": "qwen3-coder-plus", "reasoning_effort": "medium"},
            },
        }.get(str(template_id or "").strip(), {})

    def _repair_stale_template_node_routes(
        self,
        graph: dict[str, Any],
        *,
        configured_models: list[dict[str, Any]] | None = None,
    ) -> tuple[dict[str, Any], bool]:
        template_id = str(graph.get("template_id") or "").strip()
        raw_defaults = self._raw_template_node_defaults(template_id)
        if not raw_defaults or configured_models is None:
            return dict(graph), False
        resolved_defaults = self._resolve_template_node_defaults(raw_defaults, configured_models=configured_models)
        if not resolved_defaults:
            return dict(graph), False
        repaired = deepcopy(graph)
        changed = False
        for node in list(repaired.get("nodes") or []):
            if not isinstance(node, dict):
                continue
            node_id = str(node.get("node_id") or "").strip()
            raw_default = dict(raw_defaults.get(node_id) or {})
            resolved_default = dict(resolved_defaults.get(node_id) or {})
            if not raw_default or not resolved_default:
                continue
            current_provider = str(node.get("provider_id") or "").strip()
            current_model = str(node.get("model_id") or "").strip()
            if (
                current_provider == str(raw_default.get("provider_id") or "").strip()
                and current_model == str(raw_default.get("model_id") or "").strip()
            ):
                next_provider = str(resolved_default.get("provider_id") or current_provider).strip()
                next_model = str(resolved_default.get("model_id") or current_model).strip()
                next_effort = str(resolved_default.get("reasoning_effort") or node.get("reasoning_effort") or "").strip()
                if next_provider != current_provider or next_model != current_model:
                    node["provider_id"] = next_provider
                    node["model_id"] = next_model
                    if next_effort:
                        node["reasoning_effort"] = next_effort
                    changed = True
        if changed:
            repaired["updated_at"] = now_iso()
            repaired["state_version"] = int(repaired.get("state_version") or 0) + 1
            repaired["orchestration_graph"] = self._sync_orchestration_graph_with_task_graph(
                repaired.get("orchestration_graph"),
                task_graph=repaired,
            )
        return repaired, changed


    def cancel_graph_run(self, payload: dict[str, Any]) -> dict[str, Any]:
        task = self.current_task()
        if not task:
            raise ValueError("No current task.")
        if not isinstance(payload, dict):
            raise TypeError("Task graph cancel payload must be a dict.")
        run_id = str(payload.get("run_id") or "").strip()
        notes = _compact_text(redact_sensitive(payload.get("notes") or ""), limit=600)
        if not run_id:
            raise ValueError("run_id is required.")

        graph_run_refs = [dict(item) for item in list(task.get("graph_run_refs") or []) if isinstance(item, dict)]
        run_ref = next((item for item in graph_run_refs if str(item.get("run_id") or "").strip() == run_id), None)
        if run_ref is None:
            raise ValueError("Unknown run_id for task graph cancellation.")
        if str(run_ref.get("status") or "").strip() not in {"queued", "running", "paused_for_review"}:
            raise ValueError("Only queued, running, or paused_for_review task graph runs can be cancelled.")

        graph_id = str(run_ref.get("graph_id") or "").strip()
        graph = self.graph_definition(graph_id)
        if not graph:
            raise ValueError("Graph not found for the requested cancellation.")

        created_at = now_iso()
        workspace_root = self._projects.require_workspace_root()
        artifact_root = Path(workspace_root) / "PRIVATE" / "task-graph" / "cancelled" / run_id
        artifact_root.mkdir(parents=True, exist_ok=True)
        summary_json_path = artifact_root / "summary.json"
        report_md_path = artifact_root / "report.md"
        report_payload = {
            "schema_version": "astrabridge-task-graph-cancelled-run-v1",
            "run_id": run_id,
            "graph_id": graph_id,
            "task_id": str(run_ref.get("task_id") or ""),
            "cancelled_at": created_at,
            "previous_status": str(run_ref.get("status") or ""),
            "notes": notes or None,
            "summary": "Fixture run cancelled before terminal completion.",
            "artifact_paths": {
                "summary_json": summary_json_path.relative_to(workspace_root).as_posix(),
                "report_md": report_md_path.relative_to(workspace_root).as_posix(),
            },
        }
        write_json(summary_json_path, report_payload)
        report_md_path.write_text(self._cancelled_run_report_markdown(report_payload), encoding="utf-8")

        previous_status_counts = dict(run_ref.get("node_status_counts") or {})
        node_status_counts = dict(previous_status_counts)
        cancelled_count = 0
        for active_status in ("running", "waiting_on_dependencies", "waiting_on_artifact", "waiting_on_approval", "ready", "queued"):
            active_count = int(node_status_counts.pop(active_status, 0) or 0)
            if active_count > 0:
                cancelled_count += active_count
        if cancelled_count:
            node_status_counts["cancelled"] = int(node_status_counts.get("cancelled") or 0) + cancelled_count

        timeline_events = [dict(item) for item in list(run_ref.get("timeline_events") or []) if isinstance(item, dict)]
        timeline_events.extend(
            [
                {
                    "event_id": f"{run_id}-cancel-requested",
                    "event_type": "run_cancel_requested",
                    "created_at": created_at,
                    "summary": "Run cancellation was requested from the task graph workspace.",
                    "status": "cancelled",
                },
                {
                    "event_id": f"{run_id}-cancelled",
                    "event_type": "run_cancelled",
                    "created_at": created_at,
                    "summary": "Fixture run was cancelled and preserved a diagnostic report.",
                    "status": "cancelled",
                },
            ]
        )

        diagnostic_refs = [dict(item) for item in list(run_ref.get("diagnostic_refs") or []) if isinstance(item, dict)]
        diagnostic_refs.extend(
            [
                {
                    "artifact_id": f"{run_id}-cancel-summary-json",
                    "artifact_kind": "diagnostic_bundle",
                    "path": summary_json_path.relative_to(workspace_root).as_posix(),
                    "status": "ready",
                    "label": "Cancellation summary",
                },
                {
                    "artifact_id": f"{run_id}-cancel-report-md",
                    "artifact_kind": "validation_report",
                    "path": report_md_path.relative_to(workspace_root).as_posix(),
                    "status": "ready",
                    "label": "Cancellation report",
                },
            ]
        )

        updated_bindings: list[dict[str, Any]] = []
        for binding in list(run_ref.get("worker_bindings") or []):
            if not isinstance(binding, dict):
                continue
            normalized_binding = dict(binding)
            if str(normalized_binding.get("status") or "").strip() in {
                "queued",
                "ready",
                "running",
                "waiting_on_dependencies",
                "waiting_on_artifact",
                "waiting_on_approval",
            }:
                normalized_binding["status"] = "cancelled"
                normalized_binding["updated_at"] = created_at
            updated_bindings.append(normalized_binding)

        run_ref["status"] = "cancelled"
        run_ref["updated_at"] = created_at
        run_ref["latest_event_type"] = "run_cancelled"
        run_ref["latest_event_at"] = created_at
        run_ref["event_count"] = len(timeline_events)
        run_ref["node_status_counts"] = node_status_counts
        if updated_bindings:
            run_ref["worker_bindings"] = updated_bindings[:80]
            run_ref["worker_count"] = len(run_ref["worker_bindings"])
        run_ref["timeline_events"] = timeline_events[-24:]
        run_ref["diagnostic_refs"] = self._merge_graph_run_diagnostic_refs(diagnostic_refs)
        if run_ref.get("approval_details") and str((run_ref.get("approval_details") or {}).get("status") or "").strip() == "pending":
            run_ref["approval_state"] = "expired"
            run_ref["approval_details"] = self._compact_graph_run_approval_state(
                {
                    **dict(run_ref.get("approval_details") or {}),
                    "status": "expired",
                    "resolved_at": created_at,
                    "resolution_summary": "Run was cancelled before the pending approval was resolved.",
                    "notes": notes,
                }
            )
        run_ref = self._refresh_compact_graph_run_observability(run_ref)
        run_ref = self._refresh_graph_run_export_report(run_ref)

        task["graph_run_refs"] = [
            run_ref if str(item.get("run_id") or "").strip() == run_id else item
            for item in graph_run_refs
        ]
        task["graph_activity_summary"] = self._graph_activity_summary(task)
        task["updated_at"] = now_iso()
        self._save_task(task)
        return {
            "cancellation": {
                "run_id": run_id,
                "cancelled_at": created_at,
                "artifact_paths": report_payload["artifact_paths"],
            },
            "run_ref": run_ref,
            "graph": graph,
            "task": self.task_view(task, compact_graph_runs=True),
        }

    def recover_graph_run(self, payload: dict[str, Any]) -> dict[str, Any]:
        task = self.current_task()
        if not task:
            raise ValueError("No current task.")
        if not isinstance(payload, dict):
            raise TypeError("Task graph recovery payload must be a dict.")
        run_id = str(payload.get("run_id") or "").strip()
        strategy = str(payload.get("strategy") or "").strip().lower()
        if not run_id:
            raise ValueError("run_id is required.")
        if strategy not in {"resume_run", "retry_failed_nodes", "rerun_selected_nodes", "partial_execution"}:
            raise ValueError("strategy must be resume_run, retry_failed_nodes, rerun_selected_nodes, or partial_execution.")

        graph_run_refs = [dict(item) for item in list(task.get("graph_run_refs") or []) if isinstance(item, dict)]
        source_run = next((item for item in graph_run_refs if str(item.get("run_id") or "").strip() == run_id), None)
        if source_run is None:
            raise ValueError("Unknown run_id for task graph recovery.")
        if str(dict(source_run.get("policy_snapshot") or {}).get("mode") or "").strip() != "fixture_run":
            raise ValueError("Only fixture runs currently support recovery.")

        graph_id = str(source_run.get("graph_id") or "").strip()
        graph = self.graph_definition(graph_id)
        if not graph:
            raise ValueError("Graph not found for the requested recovery.")
        validated_graph = validate_graph_definition(graph)
        orchestration_graph = self._orchestration_graph_for_task_graph(validated_graph)
        compiled_plan = compile_agent_orchestration_graph(
            orchestration_graph,
            known_model_capabilities=self._known_model_capabilities_for_graph(orchestration_graph),
        )
        compiled_nodes = {
            str(item.get("node_id") or "").strip(): dict(item)
            for item in list(compiled_plan.get("nodes") or [])
            if isinstance(item, dict) and str(item.get("node_id") or "").strip()
        }
        downstream_by_node: dict[str, list[str]] = {}
        for edge in list(compiled_plan.get("edges") or []):
            if not isinstance(edge, dict):
                continue
            from_node_id = str(edge.get("from_node_id") or "").strip()
            to_node_id = str(edge.get("to_node_id") or "").strip()
            if from_node_id and to_node_id:
                downstream_by_node.setdefault(from_node_id, []).append(to_node_id)

        full_source_run = self._load_full_graph_run(source_run) or source_run
        prior_node_states = {
            str(item.get("node_id") or "").strip(): dict(item)
            for item in list(full_source_run.get("node_run_states") or [])
            if isinstance(item, dict) and str(item.get("node_id") or "").strip()
        }
        if not prior_node_states:
            raise ValueError("Source run does not expose node_run_states for recovery.")

        selected_node_ids = [str(item).strip() for item in list(payload.get("selected_node_ids") or []) if str(item or "").strip()]
        for node_id in selected_node_ids:
            if node_id not in compiled_nodes:
                raise ValueError(f"Unknown selected_node_id for recovery: {node_id}")

        initial_targets: list[str]
        if strategy == "resume_run":
            initial_targets = [
                node_id
                for node_id, state in prior_node_states.items()
                if str(state.get("status") or "").strip()
                in {"queued", "ready", "running", "waiting_on_dependencies", "waiting_on_artifact", "waiting_on_approval", "cancelled"}
            ]
            if not initial_targets:
                raise ValueError("No resumable node state exists on the source run.")
        elif strategy == "retry_failed_nodes":
            initial_targets = [
                node_id
                for node_id, state in prior_node_states.items()
                if str(state.get("status") or "").strip() in {"failed", "blocked"}
                or str(state.get("outcome") or "").strip() in {"failed", "blocked"}
            ]
            if not initial_targets:
                raise ValueError("No failed or blocked node exists on the source run.")
        else:
            if not selected_node_ids:
                raise ValueError("selected_node_ids are required for rerun_selected_nodes and partial_execution.")
            initial_targets = selected_node_ids

        rerun_node_ids = self._graph_recovery_closure(initial_targets=initial_targets, downstream_by_node=downstream_by_node)
        rerun_node_ids.update(
            node_id
            for node_id, state in prior_node_states.items()
            if str(state.get("status") or "").strip()
            in {"queued", "ready", "running", "waiting_on_dependencies", "waiting_on_artifact", "waiting_on_approval", "cancelled"}
        )
        ordered_rerun_node_ids = [node_id for node_id in compiled_nodes if node_id in rerun_node_ids]
        reusable_node_ids = [
            node_id
            for node_id in compiled_nodes
            if node_id not in rerun_node_ids
            and str(dict(prior_node_states.get(node_id) or {}).get("status") or "").strip() in {"completed", "partial"}
        ]

        behavior_overrides = self._fixture_node_behavior_overrides(payload)
        for node_id in ordered_rerun_node_ids:
            behavior_overrides.setdefault(node_id, "completed")

        preloaded_node_states: dict[str, dict[str, Any]] = {}
        preloaded_worker_bindings: list[dict[str, Any]] = []
        previous_bindings = [
            dict(item)
            for item in list(source_run.get("worker_bindings") or [])
            if isinstance(item, dict)
        ]
        for node_id in reusable_node_ids:
            prior_state = dict(prior_node_states.get(node_id) or {})
            if not prior_state:
                continue
            prior_state["reused_existing_output"] = True
            prior_state["reused_from_run_id"] = run_id
            preloaded_node_states[node_id] = prior_state
            binding = next(
                (
                    dict(item)
                    for item in previous_bindings
                    if str(item.get("node_id") or "").strip() == node_id
                ),
                None,
            )
            if binding:
                preloaded_worker_bindings.append(binding)

        created_at = now_iso()
        recovery_id = new_id("graph-recovery")
        workspace_root = self._projects.require_workspace_root()
        artifact_root = Path(workspace_root) / "PRIVATE" / "task-graph" / "recovery" / recovery_id
        artifact_root.mkdir(parents=True, exist_ok=True)
        manifest_path = artifact_root / "manifest.json"
        report_md_path = artifact_root / "report.md"
        recovery_manifest = {
            "schema_version": "astrabridge-task-graph-recovery-v1",
            "recovery_id": recovery_id,
            "source_run_id": run_id,
            "graph_id": graph_id,
            "task_id": str(source_run.get("task_id") or ""),
            "strategy": strategy,
            "requested_at": created_at,
            "selected_node_ids": selected_node_ids,
            "initial_target_node_ids": initial_targets,
            "rerun_node_ids": ordered_rerun_node_ids,
            "reused_node_ids": reusable_node_ids,
            "effective_node_behaviors": behavior_overrides,
            "source_run_status": str(source_run.get("status") or ""),
            "artifact_paths": {
                "manifest_json": manifest_path.relative_to(workspace_root).as_posix(),
                "report_md": report_md_path.relative_to(workspace_root).as_posix(),
            },
        }
        write_json(manifest_path, recovery_manifest)
        report_md_path.write_text(self._graph_recovery_report_markdown(recovery_manifest), encoding="utf-8")

        result = self._execute_compiled_fixture_graph(
            payload={
                **payload,
                "node_behaviors": behavior_overrides,
            },
            task=task,
            validated_graph=validated_graph,
            recovery_context={
                "recovery_id": recovery_id,
                "source_run_id": run_id,
                "strategy": strategy,
                "selected_node_ids": selected_node_ids,
                "rerun_node_ids": ordered_rerun_node_ids,
                "reused_node_ids": reusable_node_ids,
                "preloaded_node_states": preloaded_node_states,
                "preloaded_worker_bindings": preloaded_worker_bindings,
                "recovery_manifest": recovery_manifest,
            },
        )
        return {
            "recovery": recovery_manifest,
            **result,
        }

    def resolve_graph_run_approval(self, payload: dict[str, Any]) -> dict[str, Any]:
        task = self.current_task()
        if not task:
            raise ValueError("No current task.")
        if not isinstance(payload, dict):
            raise TypeError("Task graph approval payload must be a dict.")
        run_id = str(payload.get("run_id") or "").strip()
        decision = str(payload.get("decision") or "").strip().lower()
        notes = _compact_text(redact_sensitive(payload.get("notes") or ""), limit=600)
        if not run_id:
            raise ValueError("run_id is required.")
        if decision not in {"approve", "reject"}:
            raise ValueError("decision must be approve or reject.")

        graph_run_refs = [dict(item) for item in list(task.get("graph_run_refs") or []) if isinstance(item, dict)]
        run_ref = next((item for item in graph_run_refs if str(item.get("run_id") or "").strip() == run_id), None)
        if run_ref is None:
            raise ValueError("Unknown run_id for graph approval.")

        approval_details = dict(run_ref.get("approval_details") or {})
        if str(approval_details.get("status") or "").strip() != "pending":
            raise ValueError("This task graph run is not waiting on approval.")

        graph_id = str(run_ref.get("graph_id") or "").strip()
        graph = self.graph_definition(graph_id)
        if not graph:
            raise ValueError("Graph not found for the requested approval.")

        node_id = str(approval_details.get("node_id") or "node_gate").strip() or "node_gate"
        review_kind = str(approval_details.get("review_kind") or "human_gate").strip() or "human_gate"
        created_at = self._later_iso(
            str(approval_details.get("requested_at") or "").strip(),
            now_iso(),
            plus_ms=100,
        )
        worker_thread_id = str(approval_details.get("worker_thread_id") or f"fixture-{node_id}-{run_id}").strip()
        binding = next(
            (
                dict(item)
                for item in list(run_ref.get("worker_bindings") or [])
                if isinstance(item, dict)
                and str(item.get("node_id") or "").strip() == node_id
                and str(item.get("worker_thread_id") or "").strip() == worker_thread_id
            ),
            None,
        )
        if binding is None:
            node = next(
                (
                    dict(item)
                    for item in list(graph.get("nodes") or [])
                    if isinstance(item, dict) and str(item.get("node_id") or "").strip() == node_id
                ),
                {},
            )
            self.record_graph_worker(
                {
                    "graph_id": graph_id,
                    "run_id": run_id,
                    "node_id": node_id,
                    "worker_thread_id": worker_thread_id,
                    "parent_thread_id": str(task.get("active_provider_thread_id") or ""),
                    "spawn_mode": "manual_only",
                    "worker_origin": "manual",
                    "agent_role": str(node.get("kind") or "gate"),
                    "agent_nickname": str(node.get("label") or node_id),
                    "status": "waiting_on_approval",
                    "created_at": str(approval_details.get("requested_at") or created_at),
                    "updated_at": str(approval_details.get("requested_at") or created_at),
                },
                graph_definition=graph,
            )
            refreshed = self.graph_run_ref(run_id) or {}
            run_ref = refreshed if isinstance(refreshed, dict) else run_ref

        resolved_status = "completed" if decision == "approve" else "blocked"
        resolved_outcome = "passed" if decision == "approve" else "blocked"
        human_summary = (
            "Manual promotion gate approved the high-risk action after human review."
            if decision == "approve"
            else "Manual promotion gate rejected the high-risk action and kept the run blocked."
        )
        next_actions = (
            ["Promote the provider update using the approved artifact bundle."]
            if decision == "approve"
            else ["Revise the smoke evidence or routing scope before asking for approval again."]
        )
        worker_output = self.record_graph_worker_output(
            {
                "graph_id": graph_id,
                "run_id": run_id,
                "node_id": node_id,
                "worker_thread_id": worker_thread_id,
                "human_summary": human_summary,
                "machine_result": {
                    "decision": decision,
                    "review_kind": review_kind,
                    "notes": notes,
                    "approval_reason": approval_details.get("reason"),
                },
                "confidence": "human_review",
                "next_action_hints": next_actions,
                "status": resolved_status,
                "created_at": created_at,
                "updated_at": created_at,
            },
            graph_definition=graph,
        )

        task = self.current_task() or task
        task = self._reconcile_fixture_worker_bindings(task, run_id=run_id, preferred_bindings=[dict(worker_output.get("worker_binding") or {})]) or task
        graph_run_refs = [dict(item) for item in list(task.get("graph_run_refs") or []) if isinstance(item, dict)]
        run_ref = next((item for item in graph_run_refs if str(item.get("run_id") or "").strip() == run_id), None)
        if run_ref is None:
            raise ValueError("Run disappeared while resolving approval.")

        self._transition_run_ref_counts(
            run_ref,
            from_status="waiting_on_approval",
            to_status=resolved_status,
            from_outcome="pending",
            to_outcome=resolved_outcome,
        )
        run_ref["status"] = "completed" if decision == "approve" else "failed"
        run_ref["approval_state"] = "approved" if decision == "approve" else "rejected"
        run_ref["approval_details"] = self._compact_graph_run_approval_state(
            {
                **approval_details,
                "status": "approved" if decision == "approve" else "rejected",
                "decision": decision,
                "notes": notes,
                "resolved_at": created_at,
                "resolution_summary": human_summary,
            }
        )
        run_ref["latest_event_type"] = "run_completed" if decision == "approve" else "run_failed"
        run_ref["latest_event_at"] = created_at
        run_ref["event_count"] = int(run_ref.get("event_count") or 0) + 2
        run_ref["updated_at"] = created_at

        task["graph_run_refs"] = [
            run_ref if str(item.get("run_id") or "").strip() == run_id else item
            for item in graph_run_refs
        ]
        task["graph_activity_summary"] = self._graph_activity_summary(task)
        task["updated_at"] = now_iso()
        self._save_task(task)
        return {
            "approval": run_ref["approval_details"],
            "run_ref": run_ref,
            "graph": graph,
            "task": self.task_view(task, compact_graph_runs=True),
        }

    def _execute_fanout_fixture_graph(
        self,
        *,
        payload: dict[str, Any],
        task: dict[str, Any],
        validated_graph: dict[str, Any],
    ) -> dict[str, Any]:

        branch_behaviors_raw = payload.get("branch_behaviors")
        branch_behaviors = dict(branch_behaviors_raw) if isinstance(branch_behaviors_raw, dict) else {}
        branch_a_behavior = str(branch_behaviors.get("node_research_a") or "completed").strip().lower() or "completed"
        branch_b_behavior = str(branch_behaviors.get("node_research_b") or "blocked").strip().lower() or "blocked"
        for behavior in (branch_a_behavior, branch_b_behavior):
            if behavior not in {"completed", "blocked", "failed"}:
                raise ValueError("Fixture branch behavior must be completed, blocked, or failed.")

        run_id = new_id("graph-run-fixture")
        created_at = now_iso()
        workspace_root = self._projects.require_workspace_root()
        relative_artifact_root = Path("PRIVATE") / "task-graph" / "fixture-run" / run_id
        artifact_root = Path(workspace_root) / relative_artifact_root
        artifact_root.mkdir(parents=True, exist_ok=True)

        node_states = self._fanout_fixture_node_states(
            behaviors={
                "node_research_a": branch_a_behavior,
                "node_research_b": branch_b_behavior,
            }
        )
        node_results = [
            {
                "node_id": node_id,
                "label": self._graph_node_label(validated_graph, node_id),
                "outcome": state["outcome"],
                "status": state["status"],
                "reasons": list(state["reasons"]),
            }
            for node_id, state in node_states.items()
        ]

        summary_json_path = artifact_root / "summary.json"
        report_md_path = artifact_root / "report.md"
        report_payload = {
            "schema_version": "astrabridge-task-graph-fixture-run-v1",
            "run_id": run_id,
            "graph_id": validated_graph["graph_id"],
            "task_id": validated_graph["task_id"],
            "created_at": created_at,
            "template_id": validated_graph["template_id"],
            "run_status": self._fanout_fixture_run_status(node_states),
            "node_results": node_results,
            "artifact_paths": {
                "summary_json": summary_json_path.relative_to(workspace_root).as_posix(),
                "report_md": report_md_path.relative_to(workspace_root).as_posix(),
            },
        }
        write_json(summary_json_path, report_payload)
        report_md_path.write_text(self._fixture_run_report_markdown(report_payload), encoding="utf-8")

        run = {
            "schema_version": "astrabridge-task-graph-run-v1",
            "run_id": run_id,
            "graph_id": validated_graph["graph_id"],
            "task_id": validated_graph["task_id"],
            "trace_id": f"trace-{run_id}",
            "context_id": f"context-{run_id}",
            "status": report_payload["run_status"],
            "entry_node_ids": list(dict(validated_graph.get("graph_policy") or {}).get("entry_node_ids") or []),
            "node_run_states": [
                {
                    "node_id": node_id,
                    "run_id": run_id,
                    "status": state["status"],
                    "outcome": state["outcome"],
                    "attempt_count": int(state.get("attempt_count") or 1),
                    "started_at": created_at,
                    "updated_at": created_at,
                    "worker_origin": state.get("worker_origin"),
                    "warnings": list(state["reasons"]) if state["outcome"] in {"blocked", "partial"} else [],
                }
                for node_id, state in node_states.items()
            ],
            "artifact_refs": [
                {
                    "artifact_id": f"{run_id}-summary-json",
                    "artifact_kind": "structured_json",
                    "task_id": validated_graph["task_id"],
                    "run_id": run_id,
                    "source_node_id": "node_supervisor",
                    "path": summary_json_path.relative_to(workspace_root).as_posix(),
                    "media_type": "application/json",
                    "status": "ready",
                    "created_at": created_at,
                },
                {
                    "artifact_id": f"{run_id}-report-md",
                    "artifact_kind": "run_summary",
                    "task_id": validated_graph["task_id"],
                    "run_id": run_id,
                    "source_node_id": "node_merge",
                    "path": report_md_path.relative_to(workspace_root).as_posix(),
                    "media_type": "text/markdown",
                    "status": "ready",
                    "created_at": created_at,
                },
            ],
            "event_refs": [
                {
                    "event_id": f"{run_id}-created",
                    "run_id": run_id,
                    "task_id": validated_graph["task_id"],
                    "trace_id": f"trace-{run_id}",
                    "event_type": "run_created",
                    "created_at": created_at,
                    "summary": "Fixture run created.",
                },
                {
                    "event_id": f"{run_id}-completed",
                    "run_id": run_id,
                    "task_id": validated_graph["task_id"],
                    "trace_id": f"trace-{run_id}",
                    "event_type": "run_completed" if report_payload["run_status"] == "completed" else "run_failed",
                    "created_at": created_at,
                    "summary": f"Fixture run completed with status {report_payload['run_status']}.",
                },
            ],
            "approval_state": {"status": "not_required"},
            "run_policy_snapshot": {
                "mode": "fixture_run",
                "topology": "fanout_fanin_research",
                "branch_behaviors": {
                    "node_research_a": branch_a_behavior,
                    "node_research_b": branch_b_behavior,
                },
            },
            "created_at": created_at,
            "updated_at": created_at,
            "state_version": 1,
        }
        validated_run = validate_task_graph_run(run, graph_definition=validated_graph, workspace_root=workspace_root)
        self.record_graph_run(validated_run, graph_definition=validated_graph)

        self._record_fixture_worker_output(
            graph=validated_graph,
            run_id=run_id,
            node_id="node_research_a",
            parent_thread_id=str(task.get("active_provider_thread_id") or ""),
            created_at=created_at,
            behavior=branch_a_behavior,
            summary="Branch A researched the first question set and produced bounded source notes.",
            machine_result={
                "findings": ["Branch A finding 1", "Branch A finding 2"],
                "sources": ["https://example.com/source-a"],
            },
            next_action_hints=["Merge Branch A artifacts into the synthesizer input."],
        )
        self._record_fixture_worker_output(
            graph=validated_graph,
            run_id=run_id,
            node_id="node_research_b",
            parent_thread_id=str(task.get("active_provider_thread_id") or ""),
            created_at=created_at,
            behavior=branch_b_behavior,
            summary="Branch B hit a bounded fixture issue and returned a diagnosable output instead of raw history.",
            machine_result={
                "findings": [] if branch_b_behavior != "completed" else ["Branch B finding 1"],
                "sources": [] if branch_b_behavior != "completed" else ["https://example.com/source-b"],
                "blocked_cases": ["Fixture branch B blocked"] if branch_b_behavior == "blocked" else [],
            },
            next_action_hints=["Continue with Branch A artifacts even if Branch B is blocked."],
        )
        merge_state = node_states["node_merge"]
        if merge_state["status"] != "skipped":
            refreshed_run = self.graph_run_ref(run_id) or {}
            branch_bindings = [
                dict(item)
                for item in list(refreshed_run.get("worker_bindings") or [])
                if isinstance(item, dict) and str(item.get("node_id") or "").strip() in {"node_research_a", "node_research_b"}
            ]
            consumed_artifacts = [
                str(artifact.get("path") or "").strip()
                for binding in branch_bindings
                for artifact in list(binding.get("artifact_refs") or [])
                if isinstance(artifact, dict) and str(artifact.get("path") or "").strip()
            ]
            consumed_summaries = [
                str((binding.get("output_summary") or {}).get("artifact_bundle_path") or "").strip()
                for binding in branch_bindings
                if isinstance(binding.get("output_summary"), dict)
                and str((binding.get("output_summary") or {}).get("artifact_bundle_path") or "").strip()
            ]
            self._record_fixture_worker_output(
                graph=validated_graph,
                run_id=run_id,
                node_id="node_merge",
                parent_thread_id=str(task.get("active_provider_thread_id") or ""),
                created_at=created_at,
                behavior="completed" if merge_state["outcome"] == "passed" else "blocked",
                summary="Synthesizer consumed only declared artifact bundles and structured summaries from completed or partial worker branches.",
                machine_result={
                    "synthesis": "Merged fan-out findings into one bounded summary.",
                    "gaps": ["Branch B unavailable"] if branch_b_behavior != "completed" else [],
                    "consumed_worker_artifacts": consumed_artifacts,
                    "consumed_worker_summaries": consumed_summaries,
                },
                next_action_hints=["Review the merged artifact bundle from the run panel."],
                status=merge_state["status"],
            )

        refreshed_task = self.current_task()
        refreshed_run = self.graph_run_ref(run_id)
        report_payload["run_ref"] = refreshed_run
        write_json(summary_json_path, report_payload)
        report_md_path.write_text(self._fixture_run_report_markdown(report_payload), encoding="utf-8")
        return {
            "schema_version": "astrabridge-task-graph-fixture-run-v1",
            "fixture_run": {
                **report_payload,
                "run_ref": refreshed_run,
            },
            "graph": validated_graph,
            "task": self.task_view(refreshed_task, compact_graph_runs=True),
        }

    def _start_cancellable_fanout_fixture_graph(
        self,
        *,
        payload: dict[str, Any],
        task: dict[str, Any],
        validated_graph: dict[str, Any],
    ) -> dict[str, Any]:
        run_id = new_id("graph-run-fixture")
        created_at = now_iso()
        workspace_root = self._projects.require_workspace_root()
        artifact_root = Path(workspace_root) / "PRIVATE" / "task-graph" / "fixture-run" / run_id
        artifact_root.mkdir(parents=True, exist_ok=True)
        summary_json_path = artifact_root / "summary.json"
        report_md_path = artifact_root / "report.md"
        compiled_plan_path = artifact_root / "compiled-plan.json"
        run_manifest_path = artifact_root / "run-manifest.json"
        orchestration_graph = self._orchestration_graph_for_task_graph(validated_graph)
        compiled_plan = compile_agent_orchestration_graph(
            orchestration_graph,
            known_model_capabilities=self._known_model_capabilities_for_graph(orchestration_graph),
        )
        write_json(compiled_plan_path, compiled_plan)
        budget_snapshot = self._graph_run_budget_snapshot(
            graph=validated_graph,
            compiled_plan=compiled_plan,
            run_budget=dict(payload.get("budget") or {}) if isinstance(payload.get("budget"), dict) else None,
        )
        node_results = [
            {
                "node_id": "node_supervisor",
                "label": self._graph_node_label(validated_graph, "node_supervisor"),
                "outcome": "passed",
                "status": "completed",
                "reasons": [],
            },
            {
                "node_id": "node_research_a",
                "label": self._graph_node_label(validated_graph, "node_research_a"),
                "outcome": "pending",
                "status": "running",
                "reasons": ["Branch A fixture run is still active and can be cancelled to test recovery diagnostics."],
            },
            {
                "node_id": "node_research_b",
                "label": self._graph_node_label(validated_graph, "node_research_b"),
                "outcome": "pending",
                "status": "waiting_on_dependencies",
                "reasons": ["Branch B is waiting on the primary branch artifact bundle."],
            },
            {
                "node_id": "node_merge",
                "label": self._graph_node_label(validated_graph, "node_merge"),
                "outcome": "pending",
                "status": "waiting_on_dependencies",
                "reasons": ["Synthesizer is waiting for a completed branch output."],
            },
        ]
        report_payload = {
            "schema_version": "astrabridge-task-graph-fixture-run-v1",
            "run_id": run_id,
            "graph_id": validated_graph["graph_id"],
            "task_id": validated_graph["task_id"],
            "created_at": created_at,
            "template_id": validated_graph["template_id"],
            "run_status": "running",
            "node_results": node_results,
            "artifact_paths": {
                "summary_json": summary_json_path.relative_to(workspace_root).as_posix(),
                "report_md": report_md_path.relative_to(workspace_root).as_posix(),
                "compiled_plan_json": compiled_plan_path.relative_to(workspace_root).as_posix(),
                "run_manifest_json": run_manifest_path.relative_to(workspace_root).as_posix(),
            },
        }
        write_json(summary_json_path, report_payload)
        report_md_path.write_text(self._fixture_run_report_markdown(report_payload), encoding="utf-8")

        run = {
            "schema_version": "astrabridge-task-graph-run-v1",
            "run_id": run_id,
            "graph_id": validated_graph["graph_id"],
            "task_id": validated_graph["task_id"],
            "trace_id": f"trace-{run_id}",
            "context_id": f"context-{run_id}",
            "status": "running",
            "entry_node_ids": list(dict(validated_graph.get("graph_policy") or {}).get("entry_node_ids") or []),
            "node_run_states": [
                {
                    "node_id": "node_supervisor",
                    "run_id": run_id,
                    "status": "completed",
                    "outcome": "passed",
                    "attempt_count": 1,
                    "started_at": created_at,
                    "updated_at": created_at,
                    "worker_origin": "fixture_runner",
                },
                {
                    "node_id": "node_research_a",
                    "run_id": run_id,
                    "status": "running",
                    "outcome": "pending",
                    "attempt_count": 1,
                    "started_at": created_at,
                    "updated_at": created_at,
                    "worker_origin": "fixture_runner",
                },
                {
                    "node_id": "node_research_b",
                    "run_id": run_id,
                    "status": "waiting_on_dependencies",
                    "outcome": "pending",
                    "attempt_count": 0,
                    "started_at": created_at,
                    "updated_at": created_at,
                    "worker_origin": "fixture_runner",
                },
                {
                    "node_id": "node_merge",
                    "run_id": run_id,
                    "status": "waiting_on_dependencies",
                    "outcome": "pending",
                    "attempt_count": 0,
                    "started_at": created_at,
                    "updated_at": created_at,
                    "worker_origin": "fixture_runner",
                },
            ],
            "artifact_refs": [
                {
                    "artifact_id": f"{run_id}-summary-json",
                    "artifact_kind": "structured_json",
                    "task_id": validated_graph["task_id"],
                    "run_id": run_id,
                    "source_node_id": "node_supervisor",
                    "path": summary_json_path.relative_to(workspace_root).as_posix(),
                    "media_type": "application/json",
                    "status": "ready",
                    "created_at": created_at,
                },
                {
                    "artifact_id": f"{run_id}-report-md",
                    "artifact_kind": "run_summary",
                    "task_id": validated_graph["task_id"],
                    "run_id": run_id,
                    "source_node_id": "node_supervisor",
                    "path": report_md_path.relative_to(workspace_root).as_posix(),
                    "media_type": "text/markdown",
                    "status": "ready",
                    "created_at": created_at,
                },
                {
                    "artifact_id": f"{run_id}-compiled-plan-json",
                    "artifact_kind": "graph_definition",
                    "task_id": validated_graph["task_id"],
                    "run_id": run_id,
                    "source_node_id": "node_supervisor",
                    "path": compiled_plan_path.relative_to(workspace_root).as_posix(),
                    "media_type": "application/json",
                    "status": "ready",
                    "created_at": created_at,
                },
                {
                    "artifact_id": f"{run_id}-run-manifest-json",
                    "artifact_kind": "structured_json",
                    "task_id": validated_graph["task_id"],
                    "run_id": run_id,
                    "source_node_id": "node_supervisor",
                    "path": run_manifest_path.relative_to(workspace_root).as_posix(),
                    "media_type": "application/json",
                    "status": "ready",
                    "created_at": created_at,
                },
            ],
            "event_refs": [
                {
                    "event_id": f"{run_id}-created",
                    "run_id": run_id,
                    "task_id": validated_graph["task_id"],
                    "trace_id": f"trace-{run_id}",
                    "event_type": "run_created",
                    "created_at": created_at,
                    "summary": "Cancellable fan-out fixture run created.",
                },
                {
                    "event_id": f"{run_id}-supervisor-completed",
                    "run_id": run_id,
                    "task_id": validated_graph["task_id"],
                    "trace_id": f"trace-{run_id}",
                    "event_type": "node_completed",
                    "created_at": created_at,
                    "summary": "Supervisor seeded the branch plan and declared the expected artifact bundle.",
                    "node_id": "node_supervisor",
                },
                {
                    "event_id": f"{run_id}-branch-a-started",
                    "run_id": run_id,
                    "task_id": validated_graph["task_id"],
                    "trace_id": f"trace-{run_id}",
                    "event_type": "node_started",
                    "created_at": created_at,
                    "summary": "Branch A started its bounded research fixture run.",
                    "node_id": "node_research_a",
                },
                {
                    "event_id": f"{run_id}-branch-a-progress",
                    "run_id": run_id,
                    "task_id": validated_graph["task_id"],
                    "trace_id": f"trace-{run_id}",
                    "event_type": "node_progress",
                    "created_at": created_at,
                    "summary": "Fixture run is still active and can be cancelled to test recovery diagnostics.",
                    "node_id": "node_research_a",
                },
            ],
            "approval_state": {"status": "not_required"},
            "run_policy_snapshot": {
                "mode": "fixture_run",
                "topology": "fanout_fanin_research",
                "execution_mode": "cancellable",
                "max_parallelism": int(dict(compiled_plan.get("topology") or {}).get("max_parallelism") or 1),
                "budget": budget_snapshot,
            },
            "created_at": created_at,
            "updated_at": created_at,
            "state_version": 1,
        }
        write_json(run_manifest_path, run)
        validated_run = validate_task_graph_run(run, graph_definition=validated_graph, workspace_root=workspace_root)
        compact_ref = self.record_graph_run(validated_run, graph_definition=validated_graph)
        report_payload["run_ref"] = compact_ref
        write_json(summary_json_path, report_payload)
        report_md_path.write_text(self._fixture_run_report_markdown(report_payload), encoding="utf-8")
        return {
            "schema_version": "astrabridge-task-graph-fixture-run-v1",
            "fixture_run": {
                **report_payload,
                "run_ref": compact_ref,
            },
            "graph": validated_graph,
            "task": self.task_view(self.current_task(), compact_graph_runs=True),
        }

    def _execute_provider_gate_fixture_graph(
        self,
        *,
        payload: dict[str, Any],
        task: dict[str, Any],
        validated_graph: dict[str, Any],
    ) -> dict[str, Any]:
        run_id = new_id("graph-run-fixture")
        created_at = now_iso()
        workspace_root = self._projects.require_workspace_root()
        relative_artifact_root = Path("PRIVATE") / "task-graph" / "fixture-run" / run_id
        artifact_root = Path(workspace_root) / relative_artifact_root
        artifact_root.mkdir(parents=True, exist_ok=True)
        orchestration_graph = self._orchestration_graph_for_task_graph(validated_graph)
        compiled_plan = compile_agent_orchestration_graph(
            orchestration_graph,
            known_model_capabilities=self._known_model_capabilities_for_graph(orchestration_graph),
        )
        budget_snapshot = self._graph_run_budget_snapshot(
            graph=validated_graph,
            compiled_plan=compiled_plan,
            run_budget=dict(payload.get("budget") or {}) if isinstance(payload.get("budget"), dict) else None,
        )

        node_states = {
            "node_discover": {
                "status": "completed",
                "outcome": "passed",
                "reasons": [],
                "worker_origin": "fixture_runner",
                "attempt_count": 1,
            },
            "node_smoke": {
                "status": "completed",
                "outcome": "passed",
                "reasons": [],
                "worker_origin": "fixture_runner",
                "attempt_count": 1,
            },
            "node_gate": {
                "status": "waiting_on_approval",
                "outcome": "pending",
                "reasons": ["High-risk provider promotion is blocked until a human approves the gate."],
                "worker_origin": "manual",
                "attempt_count": 1,
            },
        }
        node_results = [
            {
                "node_id": node_id,
                "label": self._graph_node_label(validated_graph, node_id),
                "outcome": state["outcome"],
                "status": state["status"],
                "reasons": list(state["reasons"]),
            }
            for node_id, state in node_states.items()
        ]

        summary_json_path = artifact_root / "summary.json"
        report_md_path = artifact_root / "report.md"
        report_payload = {
            "schema_version": "astrabridge-task-graph-fixture-run-v1",
            "run_id": run_id,
            "graph_id": validated_graph["graph_id"],
            "task_id": validated_graph["task_id"],
            "created_at": created_at,
            "template_id": validated_graph["template_id"],
            "run_status": "paused_for_review",
            "node_results": node_results,
            "artifact_paths": {
                "summary_json": summary_json_path.relative_to(workspace_root).as_posix(),
                "report_md": report_md_path.relative_to(workspace_root).as_posix(),
            },
        }
        write_json(summary_json_path, report_payload)
        report_md_path.write_text(self._fixture_run_report_markdown(report_payload), encoding="utf-8")

        worker_thread_id = f"fixture-node_gate-{run_id}"
        run = {
            "schema_version": "astrabridge-task-graph-run-v1",
            "run_id": run_id,
            "graph_id": validated_graph["graph_id"],
            "task_id": validated_graph["task_id"],
            "trace_id": f"trace-{run_id}",
            "context_id": f"context-{run_id}",
            "status": "paused_for_review",
            "entry_node_ids": list(dict(validated_graph.get("graph_policy") or {}).get("entry_node_ids") or []),
            "node_run_states": [
                {
                    "node_id": node_id,
                    "run_id": run_id,
                    "status": state["status"],
                    "outcome": state["outcome"],
                    "attempt_count": int(state.get("attempt_count") or 1),
                    "started_at": created_at,
                    "updated_at": created_at,
                    "worker_origin": state.get("worker_origin"),
                    "warnings": list(state["reasons"]) if state["outcome"] in {"blocked", "pending"} else [],
                    "worker_thread_id": worker_thread_id if node_id == "node_gate" else None,
                    "parent_thread_id": str(task.get("active_provider_thread_id") or "") if node_id == "node_gate" else None,
                    "spawn_mode": "manual_only" if node_id == "node_gate" else "isolated_lane",
                    "agent_role": "gate" if node_id == "node_gate" else None,
                    "agent_nickname": self._graph_node_label(validated_graph, node_id) if node_id == "node_gate" else None,
                    "execution_backend": "human_review" if node_id == "node_gate" else None,
                }
                for node_id, state in node_states.items()
            ],
            "artifact_refs": [
                {
                    "artifact_id": f"{run_id}-summary-json",
                    "artifact_kind": "structured_json",
                    "task_id": validated_graph["task_id"],
                    "run_id": run_id,
                    "source_node_id": "node_discover",
                    "path": summary_json_path.relative_to(workspace_root).as_posix(),
                    "media_type": "application/json",
                    "status": "ready",
                    "created_at": created_at,
                },
                {
                    "artifact_id": f"{run_id}-report-md",
                    "artifact_kind": "run_summary",
                    "task_id": validated_graph["task_id"],
                    "run_id": run_id,
                    "source_node_id": "node_gate",
                    "path": report_md_path.relative_to(workspace_root).as_posix(),
                    "media_type": "text/markdown",
                    "status": "ready",
                    "created_at": created_at,
                },
            ],
            "event_refs": [
                {
                    "event_id": f"{run_id}-created",
                    "run_id": run_id,
                    "task_id": validated_graph["task_id"],
                    "trace_id": f"trace-{run_id}",
                    "event_type": "run_created",
                    "created_at": created_at,
                    "summary": "Provider update gate fixture run created.",
                },
                {
                    "event_id": f"{run_id}-approval-requested",
                    "run_id": run_id,
                    "task_id": validated_graph["task_id"],
                    "trace_id": f"trace-{run_id}",
                    "event_type": "approval_requested",
                    "created_at": created_at,
                    "summary": "Manual promotion gate requested human approval before provider promotion.",
                    "node_id": "node_gate",
                },
            ],
            "approval_state": {
                "status": "pending",
                "review_kind": "provider_call_gate",
                "node_id": "node_gate",
                "reason": "Provider promotion is a high-risk action and requires human approval before execution continues.",
                "requested_at": created_at,
                "worker_thread_id": worker_thread_id,
                "allowed_actions": ["provider_call", "promotion"],
                "blocked_actions": ["silent_promotion", "external_writeback_without_review"],
            },
            "run_policy_snapshot": {
                "mode": "fixture_run",
                "topology": "provider_update_smoke_gate",
                "requires_human_review": True,
                "max_parallelism": int(dict(compiled_plan.get("topology") or {}).get("max_parallelism") or 1),
                "budget": budget_snapshot,
            },
            "created_at": created_at,
            "updated_at": created_at,
            "state_version": 1,
        }
        validated_run = validate_task_graph_run(run, graph_definition=validated_graph, workspace_root=workspace_root)
        self.record_graph_run(validated_run, graph_definition=validated_graph)

        self._record_fixture_worker_output(
            graph=validated_graph,
            run_id=run_id,
            node_id="node_discover",
            parent_thread_id=str(task.get("active_provider_thread_id") or ""),
            created_at=created_at,
            behavior="completed",
            summary="Discovery fixture found one provider metadata candidate and one promotion note for review.",
            machine_result={
                "provider_changes": ["qwen3-coder-plus metadata candidate"],
                "candidate_models": ["qwen3-coder-plus"],
            },
            next_action_hints=["Send the discovery artifact bundle into the smoke matrix node."],
        )
        self._record_fixture_worker_output(
            graph=validated_graph,
            run_id=run_id,
            node_id="node_smoke",
            parent_thread_id=str(task.get("active_provider_thread_id") or ""),
            created_at=created_at,
            behavior="completed",
            summary="Smoke validation fixture produced a bounded matrix and is ready for promotion review.",
            machine_result={
                "matrix": ["qwen3-coder-plus"],
                "blocked_cases": [],
            },
            next_action_hints=["Review the smoke matrix before approving promotion."],
        )
        self.record_graph_worker(
            {
                "graph_id": str(validated_graph.get("graph_id") or ""),
                "run_id": run_id,
                "node_id": "node_gate",
                "worker_thread_id": worker_thread_id,
                "parent_thread_id": str(task.get("active_provider_thread_id") or ""),
                "spawn_mode": "manual_only",
                "worker_origin": "manual",
                "agent_role": "gate",
                "agent_nickname": self._graph_node_label(validated_graph, "node_gate"),
                "status": "waiting_on_approval",
                "execution_backend": "human_review",
                "created_at": created_at,
                "updated_at": created_at,
            },
            graph_definition=validated_graph,
        )

        refreshed_task = self.current_task()
        refreshed_run = self.graph_run_ref(run_id)
        report_payload["run_ref"] = refreshed_run
        write_json(summary_json_path, report_payload)
        report_md_path.write_text(self._fixture_run_report_markdown(report_payload), encoding="utf-8")
        return {
            "schema_version": "astrabridge-task-graph-fixture-run-v1",
            "fixture_run": {
                **report_payload,
                "run_ref": refreshed_run,
            },
            "graph": validated_graph,
            "task": self.task_view(refreshed_task, compact_graph_runs=True),
        }

    def _dry_run_node_result(
        self,
        *,
        node: dict[str, Any],
        entry_node_ids: list[str],
        incoming_edges: list[dict[str, Any]],
        known_routes: set[tuple[str, str]],
        known_providers: set[str],
        profile_records_present: bool,
        require_live_contract: bool = False,
    ) -> dict[str, Any]:
        node_id = str(node.get("node_id") or "").strip()
        reasons: list[str] = []
        status = "pass"
        execution_policy = dict(node.get("execution_policy") or {})
        output_contract = dict(node.get("output_contract") or {})
        provider_id = str(node.get("provider_id") or "").strip()
        model_id = str(node.get("model_id") or "").strip()
        permission_mode = str(node.get("permission_mode") or "").strip()
        prompt_template = str(node.get("human_summary_template") or "").strip()
        if node_id not in entry_node_ids and not incoming_edges:
            status = "blocked"
            reasons.append("Node has no incoming edge and is not declared as an entry node.")
        if require_live_contract and not provider_id:
            status = "blocked"
            reasons.append("Live execution requires an explicit provider for every node.")
        if require_live_contract and not model_id:
            status = "blocked"
            reasons.append("Live execution requires a pinned model for every node.")
        if require_live_contract and not prompt_template:
            status = "blocked"
            reasons.append("Live execution requires an explicit node prompt; generic fallback prompts are not allowed.")
        if require_live_contract and not bool(execution_policy.get("allow_provider_calls")):
            status = "blocked"
            reasons.append("Live execution requires allow_provider_calls for every executable node.")
        if model_id and not provider_id:
            status = "blocked"
            reasons.append("Model is pinned but provider is empty.")
        if provider_id and not model_id:
            status = _promote_dry_run_status(status, "warning")
            reasons.append("Provider is set without a pinned model; route resolution is under-specified.")
        if provider_id and model_id:
            if profile_records_present and (provider_id, model_id) not in known_routes:
                status = "blocked"
                reasons.append(f"No configured profile matches {provider_id} / {model_id}.")
            elif not profile_records_present:
                status = _promote_dry_run_status(status, "warning")
                reasons.append("No profile catalog snapshot was available to verify provider/model compatibility.")
        elif provider_id and profile_records_present and provider_id not in known_providers:
            status = "blocked"
            reasons.append(f"Provider {provider_id} is not present in the configured profiles.")
        if permission_mode == "full":
            status = _promote_dry_run_status(status, "warning")
            reasons.append("Permission mode is full; this route should be reviewed before execution.")
        requires_human_approval = bool(execution_policy.get("requires_human_approval"))
        approval_gate = node.get("approval_gate")
        if (bool(execution_policy.get("allow_code_changes")) or bool(execution_policy.get("allow_install"))) and not approval_gate:
            status = "blocked"
            reasons.append("High-risk node allows code changes or installs without an approval gate.")
        if requires_human_approval and not approval_gate:
            status = "blocked"
            reasons.append("Execution policy requires human approval but no approval gate is declared.")
        artifact_outputs = [str(item).strip() for item in list(output_contract.get("artifact_outputs") or []) if str(item).strip()]
        if not artifact_outputs:
            status = "blocked"
            reasons.append("Output contract does not declare any artifact outputs.")
        machine_schema = output_contract.get("machine_result_schema")
        if not bool(output_contract.get("artifact_only")) and not isinstance(machine_schema, dict):
            status = "blocked"
            reasons.append("Output contract is missing machine_result_schema.")
        return {
            "node_id": node_id,
            "label": str(node.get("label") or node_id),
            "status": status,
            "reasons": reasons,
        }

    def _dry_run_edge_result(self, *, edge: dict[str, Any], node_map: dict[str, dict[str, Any]]) -> dict[str, Any]:
        edge_id = str(edge.get("edge_id") or "").strip()
        reasons: list[str] = []
        status = "pass"
        context_policy = dict(edge.get("context_policy") or {})
        from_node = node_map.get(str(edge.get("from_node_id") or "").strip()) or {}
        source_outputs = [str(item).strip() for item in list(dict(from_node.get("output_contract") or {}).get("artifact_outputs") or []) if str(item).strip()]
        artifact_mode = str(context_policy.get("artifact_mode") or "").strip()
        included_artifacts = [str(item).strip() for item in list(context_policy.get("included_artifacts") or []) if str(item).strip()]
        if artifact_mode == "required_output_only":
            included_artifacts = [item for item in included_artifacts if item != "required_output"]
        resource_refs = [str(item).strip() for item in list(context_policy.get("resource_refs") or []) if str(item).strip()]
        if artifact_mode == "explicit_artifacts" and not included_artifacts:
            status = "blocked"
            reasons.append("Edge uses explicit_artifacts but does not list included artifacts.")
        unknown_artifacts = sorted(set(included_artifacts).difference(source_outputs))
        if unknown_artifacts:
            status = "blocked"
            reasons.append(f"Included artifacts are not produced by the source node: {', '.join(unknown_artifacts)}.")
        if artifact_mode == "required_output_only" and not source_outputs:
            status = "blocked"
            reasons.append("Edge expects required output artifacts but the source node does not declare any.")
        if str(context_policy.get("history_mode") or "").strip() == "explicit_refs_only" and not resource_refs and not included_artifacts:
            status = _promote_dry_run_status(status, "warning")
            reasons.append("Edge uses explicit_refs_only but no resource refs or included artifacts are listed.")
        if not bool(context_policy.get("exclude_private_memory", False)):
            status = "blocked"
            reasons.append("Edge does not exclude private memory.")
        return {
            "edge_id": edge_id,
            "label": f"{edge.get('from_node_id')} -> {edge.get('to_node_id')}",
            "status": status,
            "reasons": reasons,
        }

    def _dry_run_report_markdown(self, payload: dict[str, Any]) -> str:
        lines = [
            "# Task Graph Dry-Run Report",
            "",
            f"- Run ID: `{payload.get('run_id')}`",
            f"- Graph ID: `{payload.get('graph_id')}`",
            f"- Task ID: `{payload.get('task_id')}`",
            f"- Overall status: `{payload.get('overall_status')}`",
            f"- Created at: `{payload.get('created_at')}`",
            "",
            "## Graph",
            "",
            f"- Status: `{dict(payload.get('graph_result') or {}).get('status')}`",
        ]
        graph_reasons = [str(item) for item in list(dict(payload.get("graph_result") or {}).get("reasons") or []) if str(item).strip()]
        if graph_reasons:
            lines.extend(["- Reasons:"] + [f"  - {item}" for item in graph_reasons])
        lines.extend(["", "## Nodes", ""])
        for item in list(payload.get("node_results") or []):
            if not isinstance(item, dict):
                continue
            lines.append(f"- `{item.get('node_id')}` / `{item.get('status')}`")
            for reason in list(item.get("reasons") or []):
                lines.append(f"  - {reason}")
        lines.extend(["", "## Edges", ""])
        for item in list(payload.get("edge_results") or []):
            if not isinstance(item, dict):
                continue
            lines.append(f"- `{item.get('edge_id')}` / `{item.get('status')}`")
            for reason in list(item.get("reasons") or []):
                lines.append(f"  - {reason}")
        return "\n".join(lines).strip() + "\n"

    def _new_task(self, title: str) -> dict[str, Any]:
        project = self._project()
        task_id = new_id("task")
        now = now_iso()
        return {
            "schema_version": TASK_STATE_SCHEMA_VERSION,
            "task_id": task_id,
            "project_id": project.get("project_id"),
            "title": str(title or "New task").strip() or "New task",
            "status": "active",
            "handoff_policy": DEFAULT_HANDOFF_POLICY,
            "active_provider_thread_id": None,
            "provider_threads": [],
            "fork_threads": [],
            "handoff_events": [],
            "goal": None,
            "plan": None,
            "checkpoint_refs": [],
            "verification_refs": [],
            "diagnostic_refs": [],
            "asset_context_refs": [],
            "context_pack_refs": [],
            "graph_definitions": [],
            "graph_run_refs": [],
            "graph_snapshot_refs": [],
            "graph_activity_summary": {
                "graph_count": 0,
                "run_count": 0,
                "latest_graph_id": None,
                "latest_run_id": None,
                "latest_run_status": None,
                "latest_updated_at": None,
            },
            "created_at": now,
            "updated_at": now,
        }

    def _bind_thread_to_task(
        self,
        task: dict[str, Any],
        *,
        thread_id: str,
        settings: dict[str, Any],
        role: str,
        make_active: bool,
    ) -> dict[str, Any]:
        clean_thread_id = str(thread_id or "").strip()
        if not clean_thread_id:
            return task
        now = now_iso()
        hint = self._thread_context_hint(clean_thread_id)
        prior_entry: dict[str, Any] = {}
        for item in list(task.get("provider_threads") or []):
            if str(item.get("thread_id") or "") == clean_thread_id:
                prior_entry = dict(item)
                break
        explicit_settings = {key: value for key, value in dict(settings or {}).items() if value is not None}
        merged_settings = {
            **{key: value for key, value in prior_entry.items() if value is not None},
            **{key: value for key, value in hint.items() if value is not None},
            **explicit_settings,
        }
        # Cache hints can be stale after provider handoffs or minimal visual turns.
        # Preserve an existing thread route unless this bind call explicitly
        # changes it; otherwise Kimi/DeepSeek metadata can bleed across providers.
        for route_key in (
            "profile_id",
            "provider_id",
            "model",
            "reasoning_effort",
            "permission_mode",
            "collaboration_mode",
            "execution_backend",
            "name",
        ):
            if route_key not in explicit_settings and prior_entry.get(route_key) is not None:
                merged_settings[route_key] = prior_entry.get(route_key)
        provider_id = merged_settings.get("provider_id")
        thread_entry = {
            "thread_id": clean_thread_id,
            "role": role or "provider",
            "profile_id": merged_settings.get("profile_id"),
            "provider_id": provider_id,
            "model": _display_model_id(merged_settings.get("model")),
            "reasoning_effort": _display_effort(merged_settings.get("reasoning_effort"), provider_id),
            "permission_mode": merged_settings.get("permission_mode"),
            "collaboration_mode": merged_settings.get("collaboration_mode"),
            "execution_backend": merged_settings.get("execution_backend"),
            "name": _display_thread_name(merged_settings.get("name"), provider_id),
            "updated_at": now,
        }
        existing = []
        created_at = now
        for item in list(task.get("provider_threads") or []):
            if str(item.get("thread_id") or "") == clean_thread_id:
                created_at = str(item.get("created_at") or now)
                continue
            existing.append(item)
        thread_entry["created_at"] = created_at
        existing.insert(0, thread_entry)
        task["provider_threads"] = self._prune_provider_threads(existing)
        if role == "fork":
            fork_threads = [item for item in list(task.get("fork_threads") or []) if str(item.get("thread_id") or "") != clean_thread_id]
            fork_threads.insert(0, thread_entry)
            task["fork_threads"] = fork_threads[:40]
        if make_active:
            task["active_provider_thread_id"] = clean_thread_id
        if task.get("goal") is None and hint.get("goal") is not None:
            task["goal"] = redact_sensitive(hint.get("goal"))
        if task.get("plan") is None and hint.get("latest_plan") is not None:
            task["plan"] = redact_sensitive(hint.get("latest_plan"))
        task["updated_at"] = now
        return task

    def _prune_provider_threads(self, provider_threads: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Keep task continuity records compact by route, not by raw thread count.

        The user-visible task should feel like one continuous chat even if app-server
        restarts or provider handoffs produce replacement internal threads. Keep the
        newest live thread per route and at most one recent missing diagnostic per
        route so context packs do not accumulate dozens of effectively equivalent
        provider-thread records.
        """
        seen_live_routes: set[tuple[str, str, str, str, str, str, str]] = set()
        seen_missing_routes: set[tuple[str, str, str, str, str, str, str]] = set()
        pruned: list[dict[str, Any]] = []
        for item in provider_threads:
            entry = dict(item)
            display_model = _display_model_id(entry.get("model"))
            if display_model is not None:
                entry["model"] = display_model
            display_effort = _display_effort(entry.get("reasoning_effort"), entry.get("provider_id"))
            if display_effort is not None:
                entry["reasoning_effort"] = display_effort
            display_name = _display_thread_name(entry.get("name"), entry.get("provider_id"))
            if display_name is not None or entry.get("name"):
                entry["name"] = display_name
            if not entry.get("missing_at") and not _provider_thread_entry_is_plausible(entry):
                entry["missing_at"] = now_iso()
                entry["missing_reason"] = "provider_model_mismatch"
            route_key = _provider_thread_route_key(entry)
            if entry.get("missing_at"):
                if route_key in seen_missing_routes:
                    continue
                seen_missing_routes.add(route_key)
            else:
                if route_key in seen_live_routes:
                    continue
                seen_live_routes.add(route_key)
                entry.pop("missing_at", None)
                entry.pop("missing_reason", None)
            pruned.append(entry)
        return pruned[:40]

    def _normalize_task(self, task: dict[str, Any]) -> tuple[dict[str, Any], bool]:
        normalized = dict(task)
        changed = False
        original_threads = list(normalized.get("provider_threads") or [])
        pruned_threads = self._prune_provider_threads(original_threads)
        if pruned_threads != original_threads:
            normalized["provider_threads"] = pruned_threads
            changed = True
        original_forks = list(normalized.get("fork_threads") or [])
        pruned_forks = self._prune_fork_threads(original_forks)
        if pruned_forks != original_forks:
            normalized["fork_threads"] = pruned_forks
            changed = True
        original_checkpoints = list(normalized.get("checkpoint_refs") or [])
        pruned_checkpoints = self._dedupe_records(original_checkpoints, key_fields=("save_id",))
        if pruned_checkpoints != original_checkpoints:
            normalized["checkpoint_refs"] = pruned_checkpoints
            changed = True
        original_verification_refs = list(normalized.get("verification_refs") or [])
        pruned_verification_refs = self._dedupe_records(original_verification_refs, key_fields=("event_id",))
        if pruned_verification_refs != original_verification_refs:
            normalized["verification_refs"] = pruned_verification_refs
            changed = True
        original_diagnostic_refs = list(normalized.get("diagnostic_refs") or [])
        pruned_diagnostic_refs = self._dedupe_records(original_diagnostic_refs, key_fields=("event_id",))
        if pruned_diagnostic_refs != original_diagnostic_refs:
            normalized["diagnostic_refs"] = pruned_diagnostic_refs
            changed = True
        original_asset_refs = list(normalized.get("asset_context_refs") or [])
        pruned_asset_refs = self._dedupe_records(original_asset_refs, key_fields=("pack_type", "path"))
        if pruned_asset_refs != original_asset_refs:
            normalized["asset_context_refs"] = pruned_asset_refs
            changed = True
        original_context_refs = list(normalized.get("context_pack_refs") or [])
        pruned_context_refs = self._dedupe_records(original_context_refs, key_fields=("pack_type", "path"))
        if pruned_context_refs != original_context_refs:
            normalized["context_pack_refs"] = pruned_context_refs
            changed = True
        original_graph_definitions = list(normalized.get("graph_definitions") or [])
        pruned_graph_definitions = self._prune_graph_definitions(original_graph_definitions, task_id=str(normalized.get("task_id") or ""))
        if pruned_graph_definitions != original_graph_definitions:
            normalized["graph_definitions"] = pruned_graph_definitions
            changed = True
        original_graph_run_refs = list(normalized.get("graph_run_refs") or [])
        pruned_graph_run_refs = self._prune_graph_run_refs(
            original_graph_run_refs,
            task_id=str(normalized.get("task_id") or ""),
            graph_definitions=pruned_graph_definitions,
        )
        if pruned_graph_run_refs != original_graph_run_refs:
            normalized["graph_run_refs"] = pruned_graph_run_refs
            changed = True
        original_graph_snapshot_refs = list(normalized.get("graph_snapshot_refs") or [])
        pruned_graph_snapshot_refs = self._prune_graph_snapshot_refs(
            original_graph_snapshot_refs,
            task_id=str(normalized.get("task_id") or ""),
        )
        if pruned_graph_snapshot_refs != original_graph_snapshot_refs:
            normalized["graph_snapshot_refs"] = pruned_graph_snapshot_refs
            changed = True
        summary = self._graph_activity_summary({**normalized, "graph_definitions": pruned_graph_definitions, "graph_run_refs": pruned_graph_run_refs})
        if dict(normalized.get("graph_activity_summary") or {}) != summary:
            normalized["graph_activity_summary"] = summary
            changed = True
        preferred_active_thread_id = self._preferred_active_thread_id(normalized, pruned_threads)
        if str(normalized.get("active_provider_thread_id") or "") != preferred_active_thread_id:
            normalized["active_provider_thread_id"] = preferred_active_thread_id or None
            changed = True
        return normalized, changed

    def _prune_fork_threads(self, fork_threads: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seen_ids: set[str] = set()
        pruned: list[dict[str, Any]] = []
        for item in fork_threads:
            if not isinstance(item, dict):
                continue
            entry = dict(item)
            thread_id = str(entry.get("thread_id") or "").strip()
            if not thread_id or thread_id in seen_ids:
                continue
            seen_ids.add(thread_id)
            pruned.append(entry)
        return pruned[:40]

    def _dedupe_records(self, records: list[Any], *, key_fields: tuple[str, ...], limit: int = 40) -> list[dict[str, Any]]:
        seen: set[tuple[str, ...]] = set()
        deduped: list[dict[str, Any]] = []
        for item in records:
            if not isinstance(item, dict):
                continue
            key = tuple(str(item.get(field) or "").strip() for field in key_fields)
            if not any(key):
                continue
            if key in seen:
                continue
            seen.add(key)
            deduped.append(dict(item))
        return deduped[:limit]

    def _prune_graph_definitions(self, records: list[Any], *, task_id: str) -> list[dict[str, Any]]:
        seen: set[str] = set()
        pruned: list[dict[str, Any]] = []
        for item in records:
            if not isinstance(item, dict):
                continue
            try:
                validated = validate_graph_definition(dict(item))
            except Exception:
                continue
            if task_id and str(validated.get("task_id") or "") != task_id:
                continue
            graph_id = str(validated.get("graph_id") or "").strip()
            if not graph_id or graph_id in seen:
                continue
            seen.add(graph_id)
            pruned.append(validated)
        return pruned[:GRAPH_DEFINITION_LIMIT]

    def _prune_graph_run_refs(
        self,
        records: list[Any],
        *,
        task_id: str,
        graph_definitions: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        graph_map = {
            str(item.get("graph_id") or "").strip(): dict(item)
            for item in graph_definitions
            if isinstance(item, dict) and str(item.get("graph_id") or "").strip()
        }
        seen: set[str] = set()
        pruned: list[dict[str, Any]] = []
        for item in records:
            normalized = self._normalize_graph_run_ref(item, task_id=task_id, graph_definitions=graph_map)
            if not normalized:
                continue
            run_id = str(normalized.get("run_id") or "").strip()
            if not run_id or run_id in seen:
                continue
            seen.add(run_id)
            pruned.append(normalized)
        return pruned[:GRAPH_RUN_REF_LIMIT]

    def _normalize_graph_run_ref(
        self,
        value: Any,
        *,
        task_id: str,
        graph_definitions: dict[str, dict[str, Any]],
    ) -> dict[str, Any] | None:
        if not isinstance(value, dict):
            return None
        run_id = str(value.get("run_id") or "").strip()
        graph_id = str(value.get("graph_id") or "").strip()
        current_task_id = str(value.get("task_id") or "").strip()
        # Accept persisted full run objects and compact them into refs.
        if value.get("schema_version") == "astrabridge-task-graph-run-v1":
            try:
                validated_run = validate_task_graph_run(
                    dict(value),
                    graph_definition=graph_definitions.get(graph_id),
                    workspace_root=self._projects.require_workspace_root(),
                )
            except Exception:
                return None
            if task_id and str(validated_run.get("task_id") or "") != task_id:
                return None
            return self._compact_graph_run_ref(validated_run)
        required = (
            "run_id",
            "graph_id",
            "task_id",
            "status",
            "created_at",
            "updated_at",
            "entry_node_ids",
            "node_status_counts",
            "artifact_count",
            "event_count",
        )
        if not run_id or not graph_id or not current_task_id:
            return None
        if task_id and current_task_id != task_id:
            return None
        if not all(field in value for field in required):
            return None
        normalized = dict(value)
        normalized["entry_node_ids"] = [
            str(item).strip()
            for item in list(normalized.get("entry_node_ids") or [])
            if str(item or "").strip()
        ]
        if not isinstance(normalized.get("node_status_counts"), dict):
            return None
        if "node_outcome_counts" in normalized and not isinstance(normalized.get("node_outcome_counts"), dict):
            return None
        approval_details = self._compact_graph_run_approval_state(normalized.get("approval_details"))
        if approval_details:
            normalized["approval_details"] = approval_details
        timeline_events = self._compact_graph_run_timeline_events(normalized.get("timeline_events"))
        if timeline_events:
            normalized["timeline_events"] = timeline_events
        diagnostic_refs = self._merge_graph_run_diagnostic_refs(normalized.get("diagnostic_refs"))
        if diagnostic_refs:
            normalized["diagnostic_refs"] = diagnostic_refs
        worker_bindings = []
        node_ids = set(normalized["entry_node_ids"])
        graph = graph_definitions.get(graph_id) or {}
        for node in list(graph.get("nodes") or []):
            if isinstance(node, dict):
                clean_node_id = str(node.get("node_id") or "").strip()
                if clean_node_id:
                    node_ids.add(clean_node_id)
        for item in list(normalized.get("worker_bindings") or []):
            binding = self._normalize_graph_worker_binding(item, graph_id=graph_id, run_id=run_id, node_ids=node_ids)
            if binding:
                worker_bindings.append(binding)
        if worker_bindings:
            normalized["worker_bindings"] = worker_bindings[:80]
            normalized["worker_count"] = len(normalized["worker_bindings"])
        else:
            normalized.pop("worker_bindings", None)
            normalized["worker_count"] = max(0, int(normalized.get("worker_count") or 0))
        return normalized

    def _compact_graph_run_ref(self, run: dict[str, Any]) -> dict[str, Any]:
        node_status_counts: dict[str, int] = {}
        node_outcome_counts: dict[str, int] = {}
        worker_bindings: list[dict[str, Any]] = []
        usage_signals: list[dict[str, Any]] = []
        provider_call_count = 0
        tool_call_count = 0
        total_retry_count = 0
        elapsed_values: list[int] = []
        for item in list(run.get("node_run_states") or []):
            if not isinstance(item, dict):
                continue
            status = str(item.get("status") or "").strip()
            if not status:
                continue
            node_status_counts[status] = int(node_status_counts.get(status) or 0) + 1
            outcome = str(item.get("outcome") or "").strip()
            if outcome:
                node_outcome_counts[outcome] = int(node_outcome_counts.get(outcome) or 0) + 1
            total_retry_count += max(0, int(item.get("attempt_count") or 0) - 1)
            if str(item.get("elapsed_ms") or "").strip():
                try:
                    elapsed_values.append(int(item.get("elapsed_ms") or 0))
                except (TypeError, ValueError):
                    pass
            if str(item.get("provider_call_count") or "").strip():
                provider_call_count += int(item.get("provider_call_count") or 0)
            if str(item.get("tool_call_count") or "").strip():
                tool_call_count += int(item.get("tool_call_count") or 0)
            usage_signal = item.get("usage_signal")
            if isinstance(usage_signal, dict):
                usage_signals.append(dict(usage_signal))
            worker_thread_id = str(item.get("worker_thread_id") or "").strip()
            if worker_thread_id:
                binding = self._normalize_graph_worker_binding(
                    {
                        "binding_id": item.get("worker_binding_id") or new_id("graph-worker"),
                        "graph_id": run.get("graph_id"),
                        "run_id": run.get("run_id"),
                        "node_id": item.get("node_id"),
                        "worker_thread_id": worker_thread_id,
                        "parent_thread_id": item.get("parent_thread_id"),
                        "spawn_mode": item.get("spawn_mode"),
                        "worker_origin": item.get("worker_origin"),
                        "agent_role": item.get("agent_role"),
                        "agent_nickname": item.get("agent_nickname"),
                        "status": item.get("status"),
                        "execution_backend": item.get("execution_backend"),
                        "artifact_refs": item.get("artifact_refs"),
                        "created_at": item.get("started_at") or run.get("created_at") or now_iso(),
                        "updated_at": item.get("updated_at") or run.get("updated_at") or now_iso(),
                    },
                    graph_id=str(run.get("graph_id") or ""),
                    run_id=str(run.get("run_id") or ""),
                    node_ids={str(item.get("node_id") or "").strip()},
                )
                if binding:
                    worker_bindings.append(binding)
        events = [dict(item) for item in list(run.get("event_refs") or []) if isinstance(item, dict)]
        latest_event = events[-1] if events else None
        approval_state = dict(run.get("approval_state") or {})
        compact = {
            "run_id": run.get("run_id"),
            "graph_id": run.get("graph_id"),
            "task_id": run.get("task_id"),
            "trace_id": run.get("trace_id"),
            "context_id": run.get("context_id"),
            "status": run.get("status"),
            "created_at": run.get("created_at"),
            "updated_at": run.get("updated_at"),
            "state_version": run.get("state_version"),
            "entry_node_ids": list(run.get("entry_node_ids") or []),
            "node_status_counts": node_status_counts,
            "node_outcome_counts": node_outcome_counts,
            "artifact_count": len(list(run.get("artifact_refs") or [])),
            "event_count": len(events),
            "approval_state": approval_state.get("status"),
            "approval_details": self._compact_graph_run_approval_state(approval_state),
            "latest_event_type": (latest_event or {}).get("event_type"),
            "latest_event_at": (latest_event or {}).get("created_at"),
            "timeline_events": self._compact_graph_run_timeline_events(events),
            "diagnostic_refs": self._extract_graph_run_diagnostic_refs(run),
            "artifact_refs": [
                {
                    "artifact_id": str(item.get("artifact_id") or "").strip(),
                    "artifact_kind": str(item.get("artifact_kind") or "").strip(),
                    "path": str(item.get("path") or "").strip(),
                    "status": str(item.get("status") or "").strip() or "ready",
                }
                for item in list(run.get("artifact_refs") or [])
                if isinstance(item, dict)
                and str(item.get("artifact_id") or "").strip()
                and str(item.get("artifact_kind") or "").strip()
                and str(item.get("path") or "").strip()
            ][:24],
            "policy_snapshot": redact_sensitive(dict(run.get("run_policy_snapshot") or {})),
        }
        compact["metrics"] = self._compact_graph_run_metrics(
            run=run,
            node_status_counts=node_status_counts,
            elapsed_values=elapsed_values,
            retry_count=total_retry_count,
            provider_call_count=provider_call_count,
            tool_call_count=tool_call_count,
            usage_signals=usage_signals,
            artifact_count=int(compact["artifact_count"] or 0),
            event_count=int(compact["event_count"] or 0),
            approval_status=str(compact.get("approval_state") or "").strip(),
        )
        compact["budget"] = self._compact_graph_run_budget(
            run=run,
            graph_metrics=dict(compact.get("metrics") or {}),
        )
        if worker_bindings:
            compact["worker_bindings"] = worker_bindings[:80]
            compact["worker_count"] = len(compact["worker_bindings"])
        else:
            compact["worker_count"] = 0
        return compact

    def _compact_graph_run_metrics(
        self,
        *,
        run: dict[str, Any],
        node_status_counts: dict[str, int],
        elapsed_values: list[int],
        retry_count: int,
        provider_call_count: int,
        tool_call_count: int,
        usage_signals: list[dict[str, Any]],
        artifact_count: int,
        event_count: int,
        approval_status: str,
    ) -> dict[str, Any]:
        policy_snapshot = dict(run.get("run_policy_snapshot") or {})
        pricing = dict(policy_snapshot.get("pricing") or {})
        combined_usage = self._combine_usage_signals(usage_signals, pricing=pricing)
        token_section = dict(combined_usage.get("tokens") or {})
        cost_section = dict(combined_usage.get("cost") or {})
        total_tokens = token_section.get("total_tokens")
        metrics_status = "available"
        unknown_fields: list[str] = []
        if combined_usage.get("status") != "available":
            metrics_status = "partial"
            unknown_fields.extend(["tokens", "cost"])
        if not provider_call_count:
            unknown_fields.append("provider_calls")
        if not tool_call_count:
            unknown_fields.append("tool_calls")
        elapsed_ms = max(elapsed_values) if elapsed_values else None
        if elapsed_ms is None:
            unknown_fields.append("elapsed_ms")
        parallelism = None
        if isinstance(policy_snapshot.get("max_parallelism"), int):
            parallelism = int(policy_snapshot.get("max_parallelism") or 0)
        elif isinstance(policy_snapshot.get("parallel_group_count"), int):
            parallelism = max(1, int(policy_snapshot.get("max_parallelism") or 1))
        if parallelism is None:
            unknown_fields.append("max_parallelism")
        if metrics_status == "available" and unknown_fields:
            metrics_status = "partial"
        failure_count = int(node_status_counts.get("failed") or 0) + int(node_status_counts.get("blocked") or 0)
        return {
            "status": metrics_status if metrics_status else "unknown",
            "elapsed_ms": elapsed_ms,
            "max_parallelism": parallelism,
            "artifact_count": artifact_count,
            "event_count": event_count,
            "retry_count": retry_count,
            "failure_count": failure_count,
            "approval_count": 0 if approval_status in {"", "not_required"} else 1,
            "provider_call_count": provider_call_count if provider_call_count else None,
            "tool_call_count": tool_call_count if tool_call_count else None,
            "token_usage": {
                "status": combined_usage.get("status") or "not_available",
                "reason": combined_usage.get("reason"),
                "input_tokens": token_section.get("input_tokens"),
                "output_tokens": token_section.get("output_tokens"),
                "reasoning_tokens": token_section.get("reasoning_tokens"),
                "cached_input_tokens": token_section.get("cached_input_tokens"),
                "total_tokens": total_tokens,
            },
            "cost": {
                "status": cost_section.get("status") or "not_available",
                "reason": cost_section.get("reason"),
                "currency": cost_section.get("currency"),
                "total_cost": cost_section.get("total_cost"),
            },
            "unknown_fields": sorted(set(unknown_fields)),
        }

    def _combine_usage_signals(self, signals: list[dict[str, Any]], *, pricing: dict[str, Any]) -> dict[str, Any]:
        available = [dict(item) for item in signals if isinstance(item, dict) and str(item.get("status") or "") == "available"]
        if not available:
            return usage_not_available(
                source="task_graph_run",
                reason="usage_not_reported",
                pricing=pricing,
                request_kind="graph_run",
            )
        totals = {
            "input_tokens": 0,
            "output_tokens": 0,
            "reasoning_tokens": 0,
            "cached_input_tokens": 0,
            "total_tokens": 0,
        }
        has_value = False
        provider_id = None
        model = None
        for signal in available:
            provider_id = provider_id or signal.get("provider_id")
            model = model or signal.get("model")
            tokens = dict(signal.get("tokens") or {})
            for key in tuple(totals):
                value = tokens.get(key)
                if value is None:
                    continue
                totals[key] += int(value)
                has_value = True
        if not has_value:
            return usage_not_available(
                source="task_graph_run",
                reason="usage_not_reported",
                provider_id=provider_id,
                model=model,
                pricing=pricing,
                request_kind="graph_run",
            )
        return normalize_usage_signal(
            source="task_graph_run",
            provider_id=provider_id,
            model=model,
            usage=totals,
            pricing=pricing,
            request_kind="graph_run",
        )

    def _compact_graph_run_budget(self, *, run: dict[str, Any], graph_metrics: dict[str, Any]) -> dict[str, Any]:
        policy_snapshot = dict(run.get("run_policy_snapshot") or {})
        budget = dict(policy_snapshot.get("budget") or {})
        if not budget:
            return {"status": "not_configured", "enforcement": "none"}
        def metric_or_snapshot(value: Any, fallback: Any) -> Any:
            return fallback if value is None else value
        graph_snapshot_observed = dict(dict(budget.get("graph") or {}).get("observed") or {})
        run_snapshot_observed = dict(dict(budget.get("run") or {}).get("observed") or {})
        graph_budget = self._evaluate_budget_section(
            limits=dict(dict(budget.get("graph") or {}).get("limits") or {}),
            observed={
                "max_parallelism": metric_or_snapshot(graph_metrics.get("max_parallelism"), graph_snapshot_observed.get("max_parallelism")),
                "artifact_count": metric_or_snapshot(graph_metrics.get("artifact_count"), graph_snapshot_observed.get("artifact_count")),
                "elapsed_ms": metric_or_snapshot(graph_metrics.get("elapsed_ms"), graph_snapshot_observed.get("elapsed_ms")),
                "provider_call_count": metric_or_snapshot(graph_metrics.get("provider_call_count"), graph_snapshot_observed.get("provider_call_count")),
                "tool_call_count": metric_or_snapshot(graph_metrics.get("tool_call_count"), graph_snapshot_observed.get("tool_call_count")),
                "total_tokens": metric_or_snapshot(dict(graph_metrics.get("token_usage") or {}).get("total_tokens"), graph_snapshot_observed.get("total_tokens")),
                "total_cost": metric_or_snapshot(dict(graph_metrics.get("cost") or {}).get("total_cost"), graph_snapshot_observed.get("total_cost")),
            },
        )
        run_budget = self._evaluate_budget_section(
            limits=dict(dict(budget.get("run") or {}).get("limits") or {}),
            observed={
                "artifact_count": metric_or_snapshot(graph_metrics.get("artifact_count"), run_snapshot_observed.get("artifact_count")),
                "event_count": metric_or_snapshot(graph_metrics.get("event_count"), run_snapshot_observed.get("event_count")),
                "failure_count": metric_or_snapshot(graph_metrics.get("failure_count"), run_snapshot_observed.get("failure_count")),
                "retry_count": metric_or_snapshot(graph_metrics.get("retry_count"), run_snapshot_observed.get("retry_count")),
                "elapsed_ms": metric_or_snapshot(graph_metrics.get("elapsed_ms"), run_snapshot_observed.get("elapsed_ms")),
                "provider_call_count": metric_or_snapshot(graph_metrics.get("provider_call_count"), run_snapshot_observed.get("provider_call_count")),
                "tool_call_count": metric_or_snapshot(graph_metrics.get("tool_call_count"), run_snapshot_observed.get("tool_call_count")),
                "total_tokens": metric_or_snapshot(dict(graph_metrics.get("token_usage") or {}).get("total_tokens"), run_snapshot_observed.get("total_tokens")),
                "total_cost": metric_or_snapshot(dict(graph_metrics.get("cost") or {}).get("total_cost"), run_snapshot_observed.get("total_cost")),
            },
        )
        provider_models = []
        for item in list(budget.get("provider_models") or []):
            if not isinstance(item, dict):
                continue
            provider_model_observed = dict(item.get("observed") or {})
            provider_models.append(
                {
                    "provider_id": str(item.get("provider_id") or "").strip() or None,
                    "model_id": str(item.get("model_id") or "").strip() or None,
                    **self._evaluate_budget_section(
                        limits=dict(item.get("limits") or {}),
                        observed={
                            "provider_call_count": metric_or_snapshot(graph_metrics.get("provider_call_count"), provider_model_observed.get("provider_call_count")),
                            "total_tokens": metric_or_snapshot(dict(graph_metrics.get("token_usage") or {}).get("total_tokens"), provider_model_observed.get("total_tokens")),
                            "total_cost": metric_or_snapshot(dict(graph_metrics.get("cost") or {}).get("total_cost"), provider_model_observed.get("total_cost")),
                        },
                    ),
                }
            )
        nodes = []
        for item in list(budget.get("nodes") or []):
            if not isinstance(item, dict):
                continue
            node_observed = dict(item.get("observed") or {})
            nodes.append(
                {
                    "node_id": str(item.get("node_id") or "").strip() or None,
                    "label": str(item.get("label") or "").strip() or None,
                    **self._evaluate_budget_section(
                        limits=dict(item.get("limits") or {}),
                        observed={
                            "attempt_count": node_observed.get("attempt_count"),
                            "elapsed_ms": node_observed.get("elapsed_ms"),
                            "provider_call_count": node_observed.get("provider_call_count"),
                            "tool_call_count": node_observed.get("tool_call_count"),
                            "total_tokens": node_observed.get("total_tokens"),
                            "total_cost": node_observed.get("total_cost"),
                        },
                    ),
                }
            )
        statuses = [graph_budget["status"], run_budget["status"], *[str(item.get("status") or "") for item in provider_models], *[str(item.get("status") or "") for item in nodes]]
        overall = "within_budget"
        if "exceeded" in statuses:
            overall = "exceeded"
        elif any(status == "unknown" for status in statuses):
            overall = "unknown"
        elif statuses and all(status == "not_configured" for status in statuses):
            overall = "not_configured"
        return {
            "status": overall,
            "enforcement": str(budget.get("enforcement") or "fail_fast_static_then_report_only_dynamic"),
            "graph": graph_budget,
            "run": run_budget,
            "provider_models": provider_models,
            "nodes": nodes,
        }

    def _evaluate_budget_section(self, *, limits: dict[str, Any], observed: dict[str, Any]) -> dict[str, Any]:
        clean_limits = {
            str(key).strip(): value
            for key, value in dict(limits or {}).items()
            if str(key).strip() and isinstance(value, (int, float))
        }
        if not clean_limits:
            return {"status": "not_configured", "limits": {}, "observed": {}, "exceeded_fields": [], "unknown_fields": []}
        exceeded_fields: list[str] = []
        unknown_fields: list[str] = []
        clean_observed: dict[str, Any] = {}
        for key, limit in clean_limits.items():
            value = observed.get(key)
            clean_observed[key] = value
            if value is None:
                unknown_fields.append(key)
                continue
            try:
                if float(value) > float(limit):
                    exceeded_fields.append(key)
            except (TypeError, ValueError):
                unknown_fields.append(key)
        status = "within_budget"
        if exceeded_fields:
            status = "exceeded"
        elif unknown_fields:
            status = "unknown"
        return {
            "status": status,
            "limits": clean_limits,
            "observed": clean_observed,
            "exceeded_fields": exceeded_fields,
            "unknown_fields": unknown_fields,
        }

    def _graph_run_budget_snapshot(
        self,
        *,
        graph: dict[str, Any],
        compiled_plan: dict[str, Any],
        run_budget: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        graph_policy = dict(graph.get("graph_policy") or {})
        graph_budget = dict(graph_policy.get("budget") or {})
        topology = dict(compiled_plan.get("topology") or {})
        routed_nodes = [
            dict(item)
            for item in list(graph.get("nodes") or [])
            if isinstance(item, dict) and bool(dict(item.get("execution_policy") or {}).get("allow_provider_calls"))
        ]
        provider_model_expected: dict[tuple[str, str], int] = {}
        node_budgets = []
        static_blockers: list[str] = []
        for node in routed_nodes:
            provider_id = str(node.get("provider_id") or "").strip()
            model_id = str(node.get("model_id") or "").strip()
            if provider_id or model_id:
                key = (provider_id, model_id)
                provider_model_expected[key] = int(provider_model_expected.get(key) or 0) + 1
        for node in list(graph.get("nodes") or []):
            if not isinstance(node, dict):
                continue
            budget = dict(node.get("budget") or {})
            execution_policy = dict(node.get("execution_policy") or {})
            if not budget:
                continue
            section = self._evaluate_budget_section(
                limits=budget,
                observed={
                    "attempt_count": int(dict(execution_policy.get("retry_policy") or {}).get("max_attempts") or 0),
                    "elapsed_ms": int(execution_policy.get("timeout_ms") or 0) if str(execution_policy.get("timeout_ms") or "").strip() else None,
                    "provider_call_count": 1 if bool(execution_policy.get("allow_provider_calls")) else 0,
                },
            )
            node_budgets.append(
                {
                    "node_id": str(node.get("node_id") or "").strip(),
                    "label": str(node.get("label") or "").strip(),
                    **section,
                }
            )
            if section["status"] == "exceeded":
                static_blockers.append(
                    f"Node budget exceeded for {str(node.get('label') or node.get('node_id') or 'node')}: {', '.join(section['exceeded_fields'])}."
                )
        provider_model_sections = []
        for item in list(graph_budget.get("provider_model_limits") or []):
            if not isinstance(item, dict):
                continue
            provider_id = str(item.get("provider_id") or "").strip()
            model_id = str(item.get("model_id") or "").strip()
            limits = dict(item.get("limits") or {})
            expected_calls = provider_model_expected.get((provider_id, model_id))
            section = self._evaluate_budget_section(
                limits=limits,
                observed={
                    "provider_call_count": expected_calls,
                },
            )
            provider_model_sections.append(
                {
                    "provider_id": provider_id or None,
                    "model_id": model_id or None,
                    **section,
                }
            )
            if section["status"] == "exceeded":
                static_blockers.append(
                    f"Provider/model budget exceeded for {provider_id or 'unknown provider'} / {model_id or 'unknown model'}: {', '.join(section['exceeded_fields'])}."
                )
        graph_section = self._evaluate_budget_section(
            limits=dict(graph_budget.get("limits") or {}),
            observed={
                "max_parallelism": int(topology.get("max_parallelism") or 1),
                "node_count": int(topology.get("node_count") or len(list(graph.get("nodes") or []))),
                "edge_count": int(topology.get("edge_count") or len(list(graph.get("edges") or []))),
                "provider_call_count": len(routed_nodes),
            },
        )
        if graph_section["status"] == "exceeded":
            static_blockers.append(f"Graph budget exceeded: {', '.join(graph_section['exceeded_fields'])}.")
        run_section = self._evaluate_budget_section(
            limits=dict(dict(run_budget or {}).get("limits") or (run_budget or {})),
            observed={
                "max_parallelism": int(topology.get("max_parallelism") or 1),
                "node_count": int(topology.get("node_count") or len(list(graph.get("nodes") or []))),
                "provider_call_count": len(routed_nodes),
            },
        )
        if run_section["status"] == "exceeded":
            static_blockers.append(f"Run budget exceeded: {', '.join(run_section['exceeded_fields'])}.")
        statuses = [graph_section["status"], run_section["status"], *[str(item.get("status") or "") for item in node_budgets], *[str(item.get("status") or "") for item in provider_model_sections]]
        overall = "within_budget"
        if "exceeded" in statuses:
            overall = "exceeded"
        elif "unknown" in statuses:
            overall = "unknown"
        elif "not_configured" in statuses and all(status == "not_configured" for status in statuses):
            overall = "not_configured"
        return {
            "status": overall,
            "enforcement": "fail_closed_goal_budget_with_dynamic_reconciliation",
            "graph": graph_section,
            "run": run_section,
            "provider_models": provider_model_sections,
            "nodes": node_budgets,
            "static_blockers": static_blockers,
        }

    def _compact_graph_run_timeline_events(self, value: Any) -> list[dict[str, Any]]:
        events = [dict(item) for item in list(value or []) if isinstance(item, dict)]
        compact: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in events:
            event_id = str(item.get("event_id") or "").strip()
            event_type = str(item.get("event_type") or "").strip()
            created_at = str(item.get("created_at") or "").strip()
            if not event_id or not event_type or not created_at:
                continue
            if event_id in seen:
                continue
            seen.add(event_id)
            compact.append(
                {
                    "event_id": event_id,
                    "event_type": event_type,
                    "created_at": created_at,
                    "summary": _compact_text(redact_sensitive(item.get("summary") or ""), limit=240) or None,
                    "node_id": str(item.get("node_id") or "").strip() or None,
                    "edge_id": str(item.get("edge_id") or "").strip() or None,
                    "artifact_id": str(item.get("artifact_id") or "").strip() or None,
                    "parallel_group_id": str(item.get("parallel_group_id") or "").strip() or None,
                    "elapsed_ms": int(item.get("elapsed_ms") or 0) if str(item.get("elapsed_ms") or "").strip() else None,
                    "status": self._timeline_status_for_event_type(event_type),
                }
            )
        return compact[-24:]

    def _extract_graph_run_diagnostic_refs(self, run: dict[str, Any]) -> list[dict[str, Any]]:
        return self._merge_graph_run_diagnostic_refs(
            [
                {
                    "artifact_id": item.get("artifact_id"),
                    "artifact_kind": item.get("artifact_kind"),
                    "path": item.get("path"),
                    "status": item.get("status"),
                    "label": self._graph_run_diagnostic_label(item),
                }
                for item in list(run.get("artifact_refs") or [])
                if isinstance(item, dict)
                and str(item.get("artifact_kind") or "").strip() in {"validation_report", "diagnostic_bundle", "run_summary"}
            ]
        )

    def _merge_graph_run_diagnostic_refs(self, value: Any) -> list[dict[str, Any]]:
        refs = [dict(item) for item in list(value or []) if isinstance(item, dict)]
        merged: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in refs:
            artifact_id = str(item.get("artifact_id") or "").strip()
            artifact_kind = str(item.get("artifact_kind") or "").strip()
            path = str(item.get("path") or "").strip()
            if not artifact_id or not artifact_kind or not path:
                continue
            key = f"{artifact_id}|{path}"
            if key in seen:
                continue
            seen.add(key)
            merged.append(
                {
                    "artifact_id": artifact_id,
                    "artifact_kind": artifact_kind,
                    "path": path,
                    "status": str(item.get("status") or "").strip() or "ready",
                    "label": _compact_text(redact_sensitive(item.get("label") or ""), limit=120) or self._graph_run_diagnostic_label(item),
                }
            )
        return merged[:12]

    @staticmethod
    def _graph_run_diagnostic_label(item: dict[str, Any]) -> str:
        artifact_kind = str(item.get("artifact_kind") or "").strip()
        if artifact_kind == "validation_report":
            return "Validation report"
        if artifact_kind == "diagnostic_bundle":
            return "Diagnostic bundle"
        if artifact_kind == "run_summary":
            return "Run summary"
        return artifact_kind or "Diagnostic"

    @staticmethod
    def _timeline_status_for_event_type(event_type: str) -> str:
        if event_type in {"run_failed", "node_failed", "node_blocked"}:
            return "failed"
        if event_type in {"run_cancel_requested", "run_cancelled", "node_cancelled"}:
            return "cancelled"
        if event_type in {"run_completed", "node_completed", "approval_resolved", "artifact_created"}:
            return "completed"
        if event_type in {"node_started", "node_progress", "approval_requested", "run_dry_run_started"}:
            return "in_progress"
        return "pending"

    def _merge_graph_worker_artifact_refs(
        self,
        existing: list[Any],
        additions: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        merged: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in [*list(existing or []), *additions]:
            if not isinstance(item, dict):
                continue
            artifact_id = str(item.get("artifact_id") or "").strip()
            artifact_kind = str(item.get("artifact_kind") or "").strip()
            path = str(item.get("path") or "").strip()
            if not artifact_id or not artifact_kind or not path:
                continue
            key = f"{artifact_id}|{path}"
            if key in seen:
                continue
            seen.add(key)
            merged.append(
                {
                    "artifact_id": artifact_id,
                    "artifact_kind": artifact_kind,
                    "path": path,
                    "status": str(item.get("status") or "").strip() or "ready",
                }
            )
        return merged[:24]

    def _execute_supervisor_worker_synth_fixture_graph(
        self,
        *,
        payload: dict[str, Any],
        task: dict[str, Any],
        validated_graph: dict[str, Any],
    ) -> dict[str, Any]:
        del payload
        return self._execute_linear_template_fixture_graph(
            task=task,
            validated_graph=validated_graph,
            topology="supervisor_worker_synthesizer",
            node_specs=[
                {
                    "node_id": "node_supervisor",
                    "summary": "Supervisor produced a bounded execution plan with one worker assignment and one synthesis expectation.",
                    "machine_result": {"plan": ["Inspect task input", "Delegate execution", "Synthesize result"], "next_workers": ["node_worker"]},
                    "next_action_hints": ["Send only the bounded execution plan into the worker lane."],
                },
                {
                    "node_id": "node_worker",
                    "summary": "Worker executed the bounded task and returned a constrained result bundle for synthesis.",
                    "machine_result": {"result": "Worker completed the requested bounded execution path.", "confidence": "fixture"},
                    "next_action_hints": ["Pass the worker artifact bundle into the synthesizer node."],
                },
                {
                    "node_id": "node_synth",
                    "summary": "Synthesizer merged the declared plan and worker output into one final operator-facing summary.",
                    "machine_result": {"summary": "Fixture workflow completed successfully.", "decision": "deliver_summary"},
                    "next_action_hints": ["Review the final run summary from the latest run panel."],
                },
            ],
        )

    def _execute_code_fix_review_fixture_graph(
        self,
        *,
        payload: dict[str, Any],
        task: dict[str, Any],
        validated_graph: dict[str, Any],
    ) -> dict[str, Any]:
        del payload
        return self._execute_linear_template_fixture_graph(
            task=task,
            validated_graph=validated_graph,
            topology="code_fix_test_review",
            node_specs=[
                {
                    "node_id": "node_plan_fix",
                    "summary": "Planner scoped the bug fix to a bounded file set and declared the expected validation evidence.",
                    "machine_result": {"files": ["apps/example.ts"], "approach": "Narrow bug fix with explicit follow-on test and review."},
                    "next_action_hints": ["Apply only the planned diff in the code-fix node."],
                },
                {
                    "node_id": "node_code_fix",
                    "summary": "Code-fix worker produced a bounded diff artifact without relying on transcript replay.",
                    "machine_result": {"changed_files": ["apps/example.ts"], "summary": "Applied the planned guard condition and preserved existing behavior elsewhere."},
                    "next_action_hints": ["Use the diff artifact as the only input to the test and review nodes."],
                },
                {
                    "node_id": "node_test",
                    "summary": "Test validator executed the declared regression checks against the bounded diff artifact.",
                    "machine_result": {"status": "passed", "failures": []},
                    "next_action_hints": ["Attach the test report to the review node."],
                },
                {
                    "node_id": "node_review",
                    "summary": "Review node accepted the bounded change after reading the diff and test evidence.",
                    "machine_result": {"decision": "approved", "issues": []},
                    "next_action_hints": ["Surface the review report and test evidence together in the run panel."],
                },
            ],
        )

    def _execute_document_extract_fixture_graph(
        self,
        *,
        payload: dict[str, Any],
        task: dict[str, Any],
        validated_graph: dict[str, Any],
    ) -> dict[str, Any]:
        del payload
        return self._execute_linear_template_fixture_graph(
            task=task,
            validated_graph=validated_graph,
            topology="document_extract_analyze_report",
            node_specs=[
                {
                    "node_id": "node_extract",
                    "summary": "Extractor produced a bounded document extract with sections and entities preserved as structured output.",
                    "machine_result": {"sections": ["Overview", "Risks"], "entities": ["Provider A", "Model B"]},
                    "next_action_hints": ["Pass only the extract artifact bundle into the analyst node."],
                },
                {
                    "node_id": "node_analyze",
                    "summary": "Analyst consumed the declared extract artifact and returned a structured interpretation.",
                    "machine_result": {"analysis": "The extracted document highlights two major rollout risks.", "confidence": "fixture"},
                    "next_action_hints": ["Generate the final report from the extract and analysis artifacts only."],
                },
                {
                    "node_id": "node_report",
                    "summary": "Report node produced a final operator-facing summary grounded in the bounded extract and analysis artifacts.",
                    "machine_result": {"report": "Fixture document report completed.", "recommendations": ["Validate the rollout gate before publishing."]},
                    "next_action_hints": ["Review the report artifact from the latest run panel."],
                },
            ],
        )

    def _execute_linear_template_fixture_graph(
        self,
        *,
        task: dict[str, Any],
        validated_graph: dict[str, Any],
        topology: str,
        node_specs: list[dict[str, Any]],
    ) -> dict[str, Any]:
        run_id = new_id("graph-run-fixture")
        created_at = now_iso()
        workspace_root = self._projects.require_workspace_root()
        relative_artifact_root = Path("PRIVATE") / "task-graph" / "fixture-run" / run_id
        artifact_root = Path(workspace_root) / relative_artifact_root
        artifact_root.mkdir(parents=True, exist_ok=True)
        summary_json_path = artifact_root / "summary.json"
        report_md_path = artifact_root / "report.md"

        node_results = [
            {
                "node_id": str(spec.get("node_id") or ""),
                "label": self._graph_node_label(validated_graph, str(spec.get("node_id") or "")),
                "outcome": "passed",
                "status": "completed",
                "reasons": [],
            }
            for spec in node_specs
        ]
        report_payload = {
            "schema_version": "astrabridge-task-graph-fixture-run-v1",
            "run_id": run_id,
            "graph_id": validated_graph["graph_id"],
            "task_id": validated_graph["task_id"],
            "created_at": created_at,
            "template_id": validated_graph["template_id"],
            "run_status": "completed",
            "node_results": node_results,
            "artifact_paths": {
                "summary_json": summary_json_path.relative_to(workspace_root).as_posix(),
                "report_md": report_md_path.relative_to(workspace_root).as_posix(),
            },
        }
        write_json(summary_json_path, report_payload)
        report_md_path.write_text(self._fixture_run_report_markdown(report_payload), encoding="utf-8")

        run = {
            "schema_version": "astrabridge-task-graph-run-v1",
            "run_id": run_id,
            "graph_id": validated_graph["graph_id"],
            "task_id": validated_graph["task_id"],
            "trace_id": f"trace-{run_id}",
            "context_id": f"context-{run_id}",
            "status": "completed",
            "entry_node_ids": list(dict(validated_graph.get("graph_policy") or {}).get("entry_node_ids") or []),
            "node_run_states": [
                {
                    "node_id": str(spec.get("node_id") or ""),
                    "run_id": run_id,
                    "status": "completed",
                    "outcome": "passed",
                    "attempt_count": 1,
                    "started_at": created_at,
                    "updated_at": created_at,
                    "worker_origin": "fixture_runner",
                }
                for spec in node_specs
            ],
            "artifact_refs": [
                {
                    "artifact_id": f"{run_id}-summary-json",
                    "artifact_kind": "structured_json",
                    "task_id": validated_graph["task_id"],
                    "run_id": run_id,
                    "source_node_id": str(node_specs[0].get("node_id") or ""),
                    "path": summary_json_path.relative_to(workspace_root).as_posix(),
                    "media_type": "application/json",
                    "status": "ready",
                    "created_at": created_at,
                },
                {
                    "artifact_id": f"{run_id}-report-md",
                    "artifact_kind": "run_summary",
                    "task_id": validated_graph["task_id"],
                    "run_id": run_id,
                    "source_node_id": str(node_specs[-1].get("node_id") or ""),
                    "path": report_md_path.relative_to(workspace_root).as_posix(),
                    "media_type": "text/markdown",
                    "status": "ready",
                    "created_at": created_at,
                },
            ],
            "event_refs": [
                {
                    "event_id": f"{run_id}-created",
                    "run_id": run_id,
                    "task_id": validated_graph["task_id"],
                    "trace_id": f"trace-{run_id}",
                    "event_type": "run_created",
                    "created_at": created_at,
                    "summary": f"{validated_graph['title']} fixture run created.",
                },
                *[
                    {
                        "event_id": f"{run_id}-{spec['node_id']}-completed",
                        "run_id": run_id,
                        "task_id": validated_graph["task_id"],
                        "trace_id": f"trace-{run_id}",
                        "event_type": "node_completed",
                        "created_at": created_at,
                        "summary": str(spec.get("summary") or ""),
                        "node_id": str(spec.get("node_id") or ""),
                    }
                    for spec in node_specs
                ],
                {
                    "event_id": f"{run_id}-completed",
                    "run_id": run_id,
                    "task_id": validated_graph["task_id"],
                    "trace_id": f"trace-{run_id}",
                    "event_type": "run_completed",
                    "created_at": created_at,
                    "summary": f"{validated_graph['title']} fixture run completed.",
                },
            ],
            "approval_state": {"status": "not_required"},
            "run_policy_snapshot": {
                "mode": "fixture_run",
                "topology": topology,
                "execution_mode": "default",
            },
            "created_at": created_at,
            "updated_at": created_at,
            "state_version": 1,
        }
        validated_run = validate_task_graph_run(run, graph_definition=validated_graph, workspace_root=workspace_root)
        compact_ref = self.record_graph_run(validated_run, graph_definition=validated_graph)
        for spec in node_specs:
            self._record_fixture_worker_output(
                graph=validated_graph,
                run_id=run_id,
                node_id=str(spec.get("node_id") or ""),
                parent_thread_id=str(task.get("active_provider_thread_id") or ""),
                created_at=created_at,
                behavior="completed",
                summary=str(spec.get("summary") or ""),
                machine_result=dict(spec.get("machine_result") or {}),
                next_action_hints=[str(item).strip() for item in list(spec.get("next_action_hints") or []) if str(item or "").strip()],
                status="completed",
            )
        refreshed_task = self.current_task()
        refreshed_run = self.graph_run_ref(run_id)
        report_payload["run_ref"] = refreshed_run or compact_ref
        write_json(summary_json_path, report_payload)
        report_md_path.write_text(self._fixture_run_report_markdown(report_payload), encoding="utf-8")
        return {
            "schema_version": "astrabridge-task-graph-fixture-run-v1",
            "fixture_run": {
                **report_payload,
                "run_ref": refreshed_run or compact_ref,
            },
            "graph": validated_graph,
            "task": self.task_view(refreshed_task, compact_graph_runs=True),
        }

    def _fanout_fixture_node_states(self, *, behaviors: dict[str, str]) -> dict[str, dict[str, Any]]:
        branch_a = str(behaviors.get("node_research_a") or "completed").strip().lower() or "completed"
        branch_b = str(behaviors.get("node_research_b") or "blocked").strip().lower() or "blocked"
        merge_outcome = "passed"
        merge_status = "completed"
        merge_reasons: list[str] = []
        completed_branches = sum(1 for item in (branch_a, branch_b) if item == "completed")
        if completed_branches == 0:
            merge_outcome = "skipped"
            merge_status = "skipped"
            merge_reasons = ["No successful worker branch produced declared artifacts for the synthesizer."]
        elif completed_branches < 2:
            merge_outcome = "partial"
            merge_status = "partial"
            merge_reasons = ["One fan-out branch did not finish successfully; synthesizer merged the remaining declared artifacts only."]
        return {
            "node_supervisor": {
                "status": "completed",
                "outcome": "passed",
                "reasons": [],
                "worker_origin": "fixture_runner",
                "attempt_count": 1,
            },
            "node_research_a": {
                "status": self._fixture_behavior_to_node_status(branch_a),
                "outcome": "passed" if branch_a == "completed" else branch_a,
                "reasons": [] if branch_a == "completed" else [f"Fixture branch A finished with status {branch_a}."],
                "worker_origin": "fixture_runner",
                "attempt_count": 1,
            },
            "node_research_b": {
                "status": self._fixture_behavior_to_node_status(branch_b),
                "outcome": "passed" if branch_b == "completed" else branch_b,
                "reasons": [] if branch_b == "completed" else [f"Fixture branch B finished with status {branch_b}."],
                "worker_origin": "fixture_runner",
                "attempt_count": 1,
            },
            "node_merge": {
                "status": merge_status,
                "outcome": merge_outcome,
                "reasons": merge_reasons,
                "worker_origin": "fixture_runner",
                "attempt_count": 1,
            },
        }

    @staticmethod
    def _fixture_behavior_to_node_status(behavior: str) -> str:
        mapping = {
            "completed": "completed",
            "blocked": "blocked",
            "failed": "failed",
            "partial": "partial",
            "skipped": "skipped",
        }
        return mapping.get(str(behavior or "").strip().lower(), "failed")

    @staticmethod
    def _fanout_fixture_run_status(node_states: dict[str, dict[str, Any]]) -> str:
        merge = dict(node_states.get("node_merge") or {})
        merge_status = str(merge.get("status") or "").strip()
        if merge_status == "completed":
            return "completed"
        if merge_status == "partial":
            return "partial"
        return "failed"

    @staticmethod
    def _compact_graph_run_approval_state(value: Any) -> dict[str, Any] | None:
        if not isinstance(value, dict):
            return None
        status = str(value.get("status") or "").strip()
        if not status:
            return None
        compact = {
            "status": status,
            "review_kind": str(value.get("review_kind") or "").strip() or None,
            "node_id": str(value.get("node_id") or "").strip() or None,
            "reason": _compact_text(redact_sensitive(value.get("reason") or ""), limit=240) or None,
            "requested_at": str(value.get("requested_at") or "").strip() or None,
            "resolved_at": str(value.get("resolved_at") or "").strip() or None,
            "decision": str(value.get("decision") or "").strip() or None,
            "notes": _compact_text(redact_sensitive(value.get("notes") or ""), limit=240) or None,
            "resolution_summary": _compact_text(redact_sensitive(value.get("resolution_summary") or ""), limit=240) or None,
            "worker_thread_id": str(value.get("worker_thread_id") or "").strip() or None,
            "allowed_actions": [str(item).strip() for item in list(value.get("allowed_actions") or []) if str(item or "").strip()][:8],
            "blocked_actions": [str(item).strip() for item in list(value.get("blocked_actions") or []) if str(item or "").strip()][:8],
        }
        return compact

    @staticmethod
    def _transition_run_ref_counts(
        run_ref: dict[str, Any],
        *,
        from_status: str,
        to_status: str,
        from_outcome: str | None = None,
        to_outcome: str | None = None,
    ) -> None:
        status_counts = dict(run_ref.get("node_status_counts") or {})
        if from_status:
            current = int(status_counts.get(from_status) or 0) - 1
            if current > 0:
                status_counts[from_status] = current
            else:
                status_counts.pop(from_status, None)
        if to_status:
            status_counts[to_status] = int(status_counts.get(to_status) or 0) + 1
        run_ref["node_status_counts"] = status_counts

        outcome_counts = dict(run_ref.get("node_outcome_counts") or {})
        if from_outcome:
            current = int(outcome_counts.get(from_outcome) or 0) - 1
            if current > 0:
                outcome_counts[from_outcome] = current
            else:
                outcome_counts.pop(from_outcome, None)
        if to_outcome:
            outcome_counts[to_outcome] = int(outcome_counts.get(to_outcome) or 0) + 1
        run_ref["node_outcome_counts"] = outcome_counts

    @staticmethod
    def _graph_node_label(graph: dict[str, Any], node_id: str) -> str:
        for node in list(graph.get("nodes") or []):
            if isinstance(node, dict) and str(node.get("node_id") or "").strip() == node_id:
                return str(node.get("label") or node_id)
        return node_id

    def _record_fixture_worker_output(
        self,
        *,
        graph: dict[str, Any],
        run_id: str,
        node_id: str,
        parent_thread_id: str,
        created_at: str,
        updated_at: str,
        behavior: str,
        summary: str,
        machine_result: dict[str, Any],
        next_action_hints: list[str],
        status: str | None = None,
    ) -> dict[str, Any]:
        worker_thread_id = f"fixture-{node_id}-{run_id}"
        node = next(
            (
                dict(item)
                for item in list(graph.get("nodes") or [])
                if isinstance(item, dict) and str(item.get("node_id") or "").strip() == node_id
            ),
            {},
        )
        role = str(node.get("kind") or "").strip() or "worker"
        nickname = str(node.get("label") or "").strip() or node_id
        self.record_graph_worker(
            {
                "graph_id": str(graph.get("graph_id") or ""),
                "run_id": run_id,
                "node_id": node_id,
                "worker_thread_id": worker_thread_id,
                "parent_thread_id": parent_thread_id,
                "spawn_mode": "isolated_lane",
                "worker_origin": "fixture_runner",
                "agent_role": role,
                "agent_nickname": nickname,
                "status": status or self._fixture_behavior_to_node_status(behavior),
                "created_at": created_at,
                "updated_at": updated_at,
            },
            graph_definition=graph,
        )
        return self.record_graph_worker_output(
            {
                "graph_id": str(graph.get("graph_id") or ""),
                "run_id": run_id,
                "node_id": node_id,
                "worker_thread_id": worker_thread_id,
                "human_summary": summary,
                "machine_result": machine_result,
                "confidence": "fixture",
                "next_action_hints": next_action_hints,
                "status": status or self._fixture_behavior_to_node_status(behavior),
                "created_at": created_at,
                "updated_at": updated_at,
            },
            graph_definition=graph,
        )

    def _reconcile_fixture_worker_bindings(
        self,
        task: dict[str, Any] | None,
        *,
        run_id: str,
        preferred_bindings: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any] | None:
        if not task:
            return task
        graph_run_refs = [dict(item) for item in list(task.get("graph_run_refs") or []) if isinstance(item, dict)]
        run_ref = next((item for item in graph_run_refs if str(item.get("run_id") or "").strip() == run_id), None)
        if run_ref is None:
            return task
        merged_bindings = [dict(item) for item in list(run_ref.get("worker_bindings") or []) if isinstance(item, dict)]
        for binding in list(preferred_bindings or []):
            if not isinstance(binding, dict):
                continue
            merged_bindings = self._merge_run_ref_worker_binding(merged_bindings, binding)
        for binding in list(run_ref.get("worker_bindings") or []):
            if not isinstance(binding, dict):
                continue
            output_path = str(dict(binding.get("output_summary") or {}).get("artifact_bundle_path") or "").strip()
            if output_path:
                merged_bindings = self._merge_run_ref_worker_binding(merged_bindings, binding)
        run_ref["worker_bindings"] = merged_bindings[:80]
        run_ref["worker_count"] = len(run_ref["worker_bindings"])
        task["graph_run_refs"] = [
            run_ref if str(item.get("run_id") or "").strip() == run_id else item
            for item in graph_run_refs
        ]
        task["graph_activity_summary"] = self._graph_activity_summary(task)
        task["updated_at"] = now_iso()
        self._save_task(task)
        return task

    @staticmethod
    def _merge_run_ref_worker_binding(existing: list[dict[str, Any]], binding: dict[str, Any]) -> list[dict[str, Any]]:
        clean_binding_id = str(binding.get("binding_id") or "").strip()
        clean_node_id = str(binding.get("node_id") or "").strip()
        clean_worker_thread_id = str(binding.get("worker_thread_id") or "").strip()
        remainder = [
            dict(item)
            for item in existing
            if isinstance(item, dict)
            and str(item.get("binding_id") or "").strip() != clean_binding_id
            and not (
                str(item.get("node_id") or "").strip() == clean_node_id
                and str(item.get("worker_thread_id") or "").strip() == clean_worker_thread_id
            )
        ]
        return [dict(binding), *remainder]

    def _build_graph_worker_handoffs(
        self,
        *,
        graph: dict[str, Any],
        node_id: str,
        run_id: str,
        output_bundle: dict[str, Any],
        output_envelope: dict[str, Any],
        bundle_paths: dict[str, str],
        generated_artifact_refs: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        handoffs: list[dict[str, Any]] = []
        for edge in list(graph.get("edges") or []):
            if not isinstance(edge, dict):
                continue
            if str(edge.get("from_node_id") or "").strip() != node_id:
                continue
            context_policy = dict(edge.get("context_policy") or {})
            handoff_contract = dict(edge.get("handoff_contract") or {})
            input_envelope = self._build_graph_worker_input_envelope(
                edge=edge,
                output_bundle=output_bundle,
                output_envelope=output_envelope,
                generated_artifact_refs=generated_artifact_refs,
                bundle_paths=bundle_paths,
            )
            input_envelope_path = (
                Path(bundle_paths["output_json"]).parent / f"input-envelope-{str(edge.get('edge_id') or '').strip() or 'edge'}.json"
            ).as_posix()
            write_json(self._projects.require_workspace_root() / input_envelope_path, input_envelope)
            handoffs.append(
                {
                    "edge_id": str(edge.get("edge_id") or "").strip(),
                    "to_node_id": str(edge.get("to_node_id") or "").strip(),
                    "edge_type": str(edge.get("edge_type") or "").strip(),
                    "context_policy": {
                        "history_mode": str(context_policy.get("history_mode") or "").strip(),
                        "artifact_mode": str(context_policy.get("artifact_mode") or "").strip(),
                        "exclude_private_memory": bool(context_policy.get("exclude_private_memory")),
                        "include_machine_results": bool(context_policy.get("include_machine_results")),
                        "include_human_summaries": bool(context_policy.get("include_human_summaries")),
                        "summary_strategy": str(context_policy.get("summary_strategy") or "").strip(),
                        "history_length": int(context_policy.get("history_length") or 0),
                        "included_artifacts": [str(item).strip() for item in list(context_policy.get("included_artifacts") or []) if str(item or "").strip()],
                        "resource_refs": [str(item).strip() for item in list(context_policy.get("resource_refs") or []) if str(item or "").strip()],
                    },
                    "downstream_input": {
                        "source": "artifact_refs_and_context_policy",
                        "run_id": run_id,
                        "artifact_paths": [bundle_paths["output_json"], bundle_paths["summary_md"]],
                        "human_summary_path": bundle_paths["summary_md"] if output_bundle.get("human_summary") else None,
                        "machine_result_path": bundle_paths["output_json"],
                        "output_envelope_path": bundle_paths["output_envelope_json"],
                        "input_envelope_path": input_envelope_path,
                        "message_part_types": list(input_envelope.get("message_part_types") or []),
                        "artifact_refs": deepcopy(list(input_envelope.get("artifact_refs") or [])),
                        "resource_refs": deepcopy(list(input_envelope.get("resource_refs") or [])),
                        "exclude_private_memory": bool(input_envelope.get("exclude_private_memory")),
                        "handoff_contract": {
                            "message_part_modes": [str(item).strip() for item in list(handoff_contract.get("message_part_modes") or []) if str(item or "").strip()],
                            "required_output_schema_refs": [str(item).strip() for item in list(handoff_contract.get("required_output_schema_refs") or []) if str(item or "").strip()],
                        },
                    },
                }
            )
        return handoffs[:20]

    def _build_graph_worker_output_envelope(
        self,
        *,
        graph: dict[str, Any],
        source_node: dict[str, Any],
        output_bundle: dict[str, Any],
        output_contract: dict[str, Any],
        bundle_paths: dict[str, str],
        generated_artifact_refs: list[dict[str, Any]],
    ) -> dict[str, Any]:
        human_summary = str(output_bundle.get("human_summary") or "").strip()
        machine_result = redact_sensitive(output_bundle.get("machine_result") or {})
        message_parts: list[dict[str, Any]] = []
        if isinstance(machine_result, dict) and machine_result:
            message_parts.append(
                {
                    "part_type": "machine_result",
                    "port_type": "structured_json",
                    "path": bundle_paths["output_json"],
                    "preview": _compact_text(machine_result, limit=240),
                }
            )
        if human_summary:
            message_parts.append(
                {
                    "part_type": "human_summary",
                    "port_type": "text",
                    "path": bundle_paths["summary_md"],
                    "preview": _compact_text(human_summary, limit=240),
                }
            )
        for item in generated_artifact_refs:
            if not isinstance(item, dict):
                continue
            message_parts.append(
                {
                    "part_type": "artifact_ref",
                    "artifact_id": str(item.get("artifact_id") or "").strip(),
                    "artifact_kind": str(item.get("artifact_kind") or "").strip(),
                    "path": str(item.get("path") or "").strip(),
                }
            )
        return {
            "schema_version": "astrabridge-task-graph-output-envelope-v1",
            "graph_id": str(graph.get("graph_id") or ""),
            "run_id": str(output_bundle.get("run_id") or ""),
            "task_id": str(output_bundle.get("task_id") or ""),
            "node_id": str(output_bundle.get("node_id") or ""),
            "worker_thread_id": str(output_bundle.get("worker_thread_id") or ""),
            "created_at": str(output_bundle.get("created_at") or now_iso()),
            "output_contract": {
                "artifact_only": bool(output_contract.get("artifact_only")),
                "human_summary_required": bool(output_contract.get("human_summary_required")),
                "artifact_outputs": list(output_contract.get("artifact_outputs") or []),
            },
            "source_node": {
                "node_id": str(source_node.get("node_id") or ""),
                "label": str(source_node.get("label") or ""),
                "kind": str(source_node.get("kind") or ""),
                "role": str(source_node.get("role") or ""),
            },
            "message_part_types": [str(item.get("part_type") or "").strip() for item in message_parts if str(item.get("part_type") or "").strip()],
            "message_parts": message_parts,
            "artifact_refs": deepcopy(generated_artifact_refs),
            "resource_refs": [],
            "exclude_private_memory": True,
        }

    def _build_graph_worker_input_envelope(
        self,
        *,
        edge: dict[str, Any],
        output_bundle: dict[str, Any],
        output_envelope: dict[str, Any],
        generated_artifact_refs: list[dict[str, Any]],
        bundle_paths: dict[str, str],
    ) -> dict[str, Any]:
        context_policy = dict(edge.get("context_policy") or {})
        handoff_contract = dict(edge.get("handoff_contract") or {})
        message_part_modes = {
            str(item).strip()
            for item in list(handoff_contract.get("message_part_modes") or [])
            if str(item or "").strip()
        }
        if not message_part_modes:
            message_part_modes = {"machine_result", "human_summary", "artifact_ref"}
        include_machine_results = bool(context_policy.get("include_machine_results"))
        include_human_summaries = bool(context_policy.get("include_human_summaries"))
        included_artifacts = {
            str(item).strip()
            for item in list(context_policy.get("included_artifacts") or [])
            if str(item or "").strip()
        }
        resource_refs = [str(item).strip() for item in list(context_policy.get("resource_refs") or []) if str(item or "").strip()]
        artifact_mode = str(context_policy.get("artifact_mode") or "").strip()
        selected_artifact_refs = []
        if artifact_mode != "none":
            for item in generated_artifact_refs:
                if not isinstance(item, dict):
                    continue
                artifact_id = str(item.get("artifact_id") or "").strip()
                artifact_kind = str(item.get("artifact_kind") or "").strip()
                if included_artifacts and artifact_id not in included_artifacts and artifact_kind not in included_artifacts:
                    continue
                selected_artifact_refs.append(
                    {
                        "artifact_id": artifact_id,
                        "artifact_kind": artifact_kind,
                        "path": str(item.get("path") or "").strip(),
                        "status": str(item.get("status") or "").strip() or "ready",
                    }
                )

        message_parts: list[dict[str, Any]] = []
        if include_machine_results and "machine_result" in message_part_modes:
            machine_result = redact_sensitive(output_bundle.get("machine_result") or {})
            if isinstance(machine_result, dict) and machine_result:
                message_parts.append(
                    {
                        "part_type": "machine_result",
                        "port_type": "structured_json",
                        "path": bundle_paths["output_json"],
                        "preview": _compact_text(machine_result, limit=240),
                    }
                )
        if include_human_summaries and "human_summary" in message_part_modes:
            human_summary = str(output_bundle.get("human_summary") or "").strip()
            if human_summary:
                message_parts.append(
                    {
                        "part_type": "human_summary",
                        "port_type": "text",
                        "path": bundle_paths["summary_md"],
                        "preview": _compact_text(human_summary, limit=240),
                    }
                )
        if "artifact_ref" in message_part_modes:
            for item in selected_artifact_refs:
                message_parts.append(
                    {
                        "part_type": "artifact_ref",
                        "artifact_id": str(item.get("artifact_id") or "").strip(),
                        "artifact_kind": str(item.get("artifact_kind") or "").strip(),
                        "path": str(item.get("path") or "").strip(),
                    }
                )
        for ref in resource_refs:
            message_parts.append(
                {
                    "part_type": "resource_ref",
                    "path": ref,
                }
            )
        return {
            "schema_version": "astrabridge-task-graph-input-envelope-v1",
            "graph_id": str(output_bundle.get("graph_id") or ""),
            "run_id": str(output_bundle.get("run_id") or ""),
            "task_id": str(output_bundle.get("task_id") or ""),
            "from_node_id": str(edge.get("from_node_id") or ""),
            "to_node_id": str(edge.get("to_node_id") or ""),
            "edge_id": str(edge.get("edge_id") or ""),
            "created_at": str(output_bundle.get("created_at") or now_iso()),
            "context_policy": {
                "history_mode": str(context_policy.get("history_mode") or "").strip(),
                "artifact_mode": artifact_mode,
                "exclude_private_memory": bool(context_policy.get("exclude_private_memory")),
                "include_machine_results": include_machine_results,
                "include_human_summaries": include_human_summaries,
                "summary_strategy": str(context_policy.get("summary_strategy") or "").strip(),
                "included_artifacts": sorted(included_artifacts),
                "resource_refs": resource_refs,
            },
            "handoff_contract": {
                "message_template": str(handoff_contract.get("message_template") or "").strip(),
                "message_part_modes": sorted(message_part_modes),
                "required_output_schema_refs": [str(item).strip() for item in list(handoff_contract.get("required_output_schema_refs") or []) if str(item or "").strip()],
            },
            "source_output_envelope_path": bundle_paths["output_envelope_json"],
            "message_part_types": [str(item.get("part_type") or "").strip() for item in message_parts if str(item.get("part_type") or "").strip()],
            "message_parts": message_parts,
            "artifact_refs": selected_artifact_refs,
            "resource_refs": resource_refs,
            "exclude_private_memory": bool(context_policy.get("exclude_private_memory")),
        }

    def _graph_worker_summary_markdown(self, output_bundle: dict[str, Any]) -> str:
        human_summary = str(output_bundle.get("human_summary") or "").strip()
        hints = [str(item).strip() for item in list(output_bundle.get("next_action_hints") or []) if str(item or "").strip()]
        lines = [
            "# Worker output",
            "",
            f"- Node: `{output_bundle.get('node_id')}`",
            f"- Worker thread: `{output_bundle.get('worker_thread_id')}`",
            f"- Role: `{dict(output_bundle.get('provenance') or {}).get('agent_role') or ''}`",
            f"- Created at: `{output_bundle.get('created_at')}`",
            "",
        ]
        if human_summary:
            lines.extend(["## Human summary", "", human_summary, ""])
        machine_preview = _compact_text(redact_sensitive(output_bundle.get("machine_result") or {}), limit=480)
        if machine_preview:
            lines.extend(["## Machine result preview", "", "```json", machine_preview, "```", ""])
        if hints:
            lines.extend(["## Next actions", ""])
            lines.extend([f"- {hint}" for hint in hints])
            lines.append("")
        return "\n".join(lines)

    def _fixture_run_report_markdown(self, report_payload: dict[str, Any]) -> str:
        lines = [
            "# Fixture run",
            "",
            f"- Run id: `{report_payload.get('run_id')}`",
            f"- Graph id: `{report_payload.get('graph_id')}`",
            f"- Status: `{report_payload.get('run_status')}`",
            "",
            "## Node results",
            "",
        ]
        for item in list(report_payload.get("node_results") or []):
            if not isinstance(item, dict):
                continue
            label = str(item.get("label") or item.get("node_id") or "node")
            outcome = str(item.get("outcome") or "")
            status = str(item.get("status") or "")
            reasons = [str(reason).strip() for reason in list(item.get("reasons") or []) if str(reason or "").strip()]
            lines.append(f"- **{label}**: `{outcome}` / `{status}`")
            for reason in reasons:
                lines.append(f"  - {reason}")
        lines.append("")
        return "\n".join(lines)

    def _cancelled_run_report_markdown(self, report_payload: dict[str, Any]) -> str:
        lines = [
            "# Cancelled task graph run",
            "",
            f"- Run id: `{report_payload.get('run_id')}`",
            f"- Graph id: `{report_payload.get('graph_id')}`",
            f"- Previous status: `{report_payload.get('previous_status')}`",
            f"- Cancelled at: `{report_payload.get('cancelled_at')}`",
            "",
            "## Summary",
            "",
            str(report_payload.get("summary") or "Run cancelled."),
            "",
        ]
        if report_payload.get("notes"):
            lines.extend(["## Notes", "", str(report_payload.get("notes") or ""), ""])
        return "\n".join(lines)

    def _load_full_graph_run(self, run_ref: dict[str, Any]) -> dict[str, Any] | None:
        artifact_refs = [dict(item) for item in list(run_ref.get("artifact_refs") or []) if isinstance(item, dict)]
        manifest_ref = next(
            (
                item
                for item in artifact_refs
                if str(item.get("artifact_kind") or "").strip() == "structured_json"
                and str(item.get("artifact_id") or "").strip().endswith("-run-manifest-json")
            ),
            None,
        )
        if manifest_ref is None:
            return None
        relative_path = str(manifest_ref.get("path") or "").strip()
        if not relative_path:
            return None
        workspace_root = self._projects.require_workspace_root()
        manifest_path = resolve_under(workspace_root, relative_path)
        if manifest_path is None or not manifest_path.exists():
            return None
        try:
            loaded = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            return None
        return dict(loaded) if isinstance(loaded, dict) else None

    @staticmethod
    def _graph_recovery_closure(*, initial_targets: list[str], downstream_by_node: dict[str, list[str]]) -> set[str]:
        closure = {str(item).strip() for item in list(initial_targets or []) if str(item or "").strip()}
        queue = list(closure)
        while queue:
            node_id = queue.pop(0)
            for downstream in list(downstream_by_node.get(node_id) or []):
                clean = str(downstream or "").strip()
                if not clean or clean in closure:
                    continue
                closure.add(clean)
                queue.append(clean)
        return closure

    def _graph_recovery_report_markdown(self, manifest: dict[str, Any]) -> str:
        lines = [
            "# Task graph recovery",
            "",
            f"- Recovery id: `{manifest.get('recovery_id')}`",
            f"- Source run id: `{manifest.get('source_run_id')}`",
            f"- Strategy: `{manifest.get('strategy')}`",
            f"- Source status: `{manifest.get('source_run_status')}`",
            f"- Selected node ids: `{', '.join(list(manifest.get('selected_node_ids') or [])) or '-'}`",
            f"- Initial targets: `{', '.join(list(manifest.get('initial_target_node_ids') or [])) or '-'}`",
            f"- Rerun node ids: `{', '.join(list(manifest.get('rerun_node_ids') or [])) or '-'}`",
            f"- Reused node ids: `{', '.join(list(manifest.get('reused_node_ids') or [])) or '-'}`",
            "",
            "## Effective Fixture Behaviors",
            "",
        ]
        for node_id, behavior in dict(manifest.get("effective_node_behaviors") or {}).items():
            lines.append(f"- `{node_id}` -> `{behavior}`")
        lines.append("")
        return "\n".join(lines)

    def _normalize_graph_worker_binding(
        self,
        value: Any,
        *,
        graph_id: str,
        run_id: str,
        node_ids: set[str],
    ) -> dict[str, Any] | None:
        if not isinstance(value, dict):
            return None
        binding_id = str(value.get("binding_id") or "").strip()
        node_id = str(value.get("node_id") or "").strip()
        worker_thread_id = str(value.get("worker_thread_id") or "").strip()
        current_graph_id = str(value.get("graph_id") or graph_id).strip()
        current_run_id = str(value.get("run_id") or run_id).strip()
        if not binding_id or not node_id or not worker_thread_id:
            return None
        if current_graph_id != graph_id or current_run_id != run_id:
            return None
        if node_ids and node_id not in node_ids:
            return None
        artifact_refs: list[dict[str, Any]] = []
        for item in list(value.get("artifact_refs") or []):
            if not isinstance(item, dict):
                continue
            artifact_path = str(item.get("path") or "").strip()
            artifact_kind = str(item.get("artifact_kind") or "").strip()
            artifact_status = str(item.get("status") or "").strip() or "ready"
            if not artifact_path or not artifact_kind:
                continue
            artifact_refs.append(
                {
                    "artifact_id": str(item.get("artifact_id") or "").strip() or new_id("graph-artifact"),
                    "artifact_kind": artifact_kind,
                    "path": artifact_path,
                    "status": artifact_status,
                }
            )
        output_summary = value.get("output_summary")
        normalized_output_summary = None
        if isinstance(output_summary, dict):
            normalized_output_summary = {
                "human_summary": _compact_text(redact_sensitive(output_summary.get("human_summary") or ""), limit=240),
                "machine_result_preview": _compact_text(redact_sensitive(output_summary.get("machine_result_preview") or ""), limit=240),
                "confidence": redact_sensitive(output_summary.get("confidence")),
                "next_action_hints": [
                    _compact_text(redact_sensitive(item), limit=240)
                    for item in list(output_summary.get("next_action_hints") or [])
                    if str(item or "").strip()
                ][:8],
                "artifact_bundle_path": str(output_summary.get("artifact_bundle_path") or "").strip(),
                "output_envelope_path": str(output_summary.get("output_envelope_path") or "").strip(),
            }
        runtime_contract = dict(value.get("runtime_contract") or {})
        normalized_runtime_contract = {
            "profile_id": str(runtime_contract.get("profile_id") or "").strip(),
            "provider_id": str(runtime_contract.get("provider_id") or "").strip(),
            "model": str(runtime_contract.get("model") or "").strip(),
            "reasoning_effort": str(runtime_contract.get("reasoning_effort") or "").strip(),
            "permission_mode": str(runtime_contract.get("permission_mode") or "").strip(),
            "collaboration_mode": str(runtime_contract.get("collaboration_mode") or "").strip() or "default",
            "execution_backend": str(runtime_contract.get("execution_backend") or "").strip(),
            "spawn_mode": str(runtime_contract.get("spawn_mode") or "").strip(),
            "timeout_ms": int(runtime_contract.get("timeout_ms") or 0),
            "mcp_preset_ids": [
                str(entry).strip()
                for entry in list(runtime_contract.get("mcp_preset_ids") or [])
                if str(entry or "").strip()
            ][:16],
            "skill_ids": [
                str(entry).strip()
                for entry in list(runtime_contract.get("skill_ids") or [])
                if str(entry or "").strip()
            ][:16],
            "prompt_template_mode": str(runtime_contract.get("prompt_template_mode") or "").strip(),
            "tool_policy": {
                "approval_mode": str(dict(runtime_contract.get("tool_policy") or {}).get("approval_mode") or "").strip(),
                "allowed_tool_classes": [
                    str(entry).strip()
                    for entry in list(dict(runtime_contract.get("tool_policy") or {}).get("allowed_tool_classes") or [])
                    if str(entry or "").strip()
                ][:16],
                "supports_mcp": bool(dict(runtime_contract.get("tool_policy") or {}).get("supports_mcp")),
            },
            "subagent_policy": {
                "isolation_mode": str(dict(runtime_contract.get("subagent_policy") or {}).get("isolation_mode") or "").strip(),
                "max_turns": int(dict(runtime_contract.get("subagent_policy") or {}).get("max_turns") or 0),
                "allow_direct_teammate_messages": bool(dict(runtime_contract.get("subagent_policy") or {}).get("allow_direct_teammate_messages")),
                "share_worktree": bool(dict(runtime_contract.get("subagent_policy") or {}).get("share_worktree")),
                "allow_nested_subagents": bool(dict(runtime_contract.get("subagent_policy") or {}).get("allow_nested_subagents")),
            },
        }
        downstream_handoffs: list[dict[str, Any]] = []
        for item in list(value.get("downstream_handoffs") or []):
            if not isinstance(item, dict):
                continue
            context_policy = dict(item.get("context_policy") or {})
            downstream_input = dict(item.get("downstream_input") or {})
            downstream_handoffs.append(
                {
                    "edge_id": str(item.get("edge_id") or "").strip(),
                    "to_node_id": str(item.get("to_node_id") or "").strip(),
                    "edge_type": str(item.get("edge_type") or "").strip(),
                    "context_policy": {
                        "history_mode": str(context_policy.get("history_mode") or "").strip(),
                        "artifact_mode": str(context_policy.get("artifact_mode") or "").strip(),
                        "exclude_private_memory": bool(context_policy.get("exclude_private_memory")),
                        "include_machine_results": bool(context_policy.get("include_machine_results")),
                        "include_human_summaries": bool(context_policy.get("include_human_summaries")),
                        "summary_strategy": str(context_policy.get("summary_strategy") or "").strip(),
                        "history_length": int(context_policy.get("history_length") or 0),
                        "included_artifacts": [str(entry).strip() for entry in list(context_policy.get("included_artifacts") or []) if str(entry or "").strip()],
                        "resource_refs": [str(entry).strip() for entry in list(context_policy.get("resource_refs") or []) if str(entry or "").strip()],
                    },
                    "downstream_input": {
                        "source": str(downstream_input.get("source") or "").strip(),
                        "run_id": str(downstream_input.get("run_id") or "").strip(),
                        "artifact_paths": [str(entry).strip() for entry in list(downstream_input.get("artifact_paths") or []) if str(entry or "").strip()],
                        "human_summary_path": str(downstream_input.get("human_summary_path") or "").strip() or None,
                        "machine_result_path": str(downstream_input.get("machine_result_path") or "").strip() or None,
                        "output_envelope_path": str(downstream_input.get("output_envelope_path") or "").strip() or None,
                        "input_envelope_path": str(downstream_input.get("input_envelope_path") or "").strip() or None,
                        "message_part_types": [str(entry).strip() for entry in list(downstream_input.get("message_part_types") or []) if str(entry or "").strip()],
                        "artifact_refs": [
                            {
                                "artifact_id": str(entry.get("artifact_id") or "").strip(),
                                "artifact_kind": str(entry.get("artifact_kind") or "").strip(),
                                "path": str(entry.get("path") or "").strip(),
                                "status": str(entry.get("status") or "").strip() or "ready",
                            }
                            for entry in list(downstream_input.get("artifact_refs") or [])
                            if isinstance(entry, dict)
                            and str(entry.get("artifact_id") or "").strip()
                            and str(entry.get("path") or "").strip()
                        ],
                        "resource_refs": [str(entry).strip() for entry in list(downstream_input.get("resource_refs") or []) if str(entry or "").strip()],
                        "exclude_private_memory": bool(downstream_input.get("exclude_private_memory")),
                        },
                }
            )
        return {
            "binding_id": binding_id,
            "graph_id": graph_id,
            "run_id": run_id,
            "node_id": node_id,
            "worker_thread_id": worker_thread_id,
            "parent_thread_id": str(value.get("parent_thread_id") or "").strip(),
            "spawn_mode": str(value.get("spawn_mode") or "").strip(),
            "worker_origin": str(value.get("worker_origin") or "").strip(),
            "agent_role": str(value.get("agent_role") or "").strip(),
            "agent_nickname": str(value.get("agent_nickname") or "").strip(),
            "status": str(value.get("status") or "").strip() or "queued",
            "execution_backend": str(value.get("execution_backend") or "").strip(),
            "runtime_contract": normalized_runtime_contract,
            "artifact_refs": artifact_refs[:16],
            "output_summary": normalized_output_summary,
            "downstream_handoffs": downstream_handoffs[:20],
            "created_at": str(value.get("created_at") or "").strip() or now_iso(),
            "updated_at": str(value.get("updated_at") or "").strip() or now_iso(),
        }

    def _graph_activity_summary(self, task: dict[str, Any]) -> dict[str, Any]:
        graph_definitions = [dict(item) for item in list(task.get("graph_definitions") or []) if isinstance(item, dict)]
        graph_run_refs = [dict(item) for item in list(task.get("graph_run_refs") or []) if isinstance(item, dict)]
        graph_status_counts: dict[str, int] = {}
        run_status_counts: dict[str, int] = {}
        for item in graph_definitions:
            status = str(item.get("status") or "").strip()
            if status:
                graph_status_counts[status] = int(graph_status_counts.get(status) or 0) + 1
        for item in graph_run_refs:
            status = str(item.get("status") or "").strip()
            if status:
                run_status_counts[status] = int(run_status_counts.get(status) or 0) + 1
        latest_graph_id = str(graph_definitions[0].get("graph_id") or "").strip() or None if graph_definitions else None
        latest_run_id = str(graph_run_refs[0].get("run_id") or "").strip() or None if graph_run_refs else None
        latest_run_status = str(graph_run_refs[0].get("status") or "").strip() or None if graph_run_refs else None
        latest_updated_at = None
        for candidate in [
            str((graph_run_refs[0] or {}).get("updated_at") or "").strip() if graph_run_refs else "",
            str((graph_definitions[0] or {}).get("updated_at") or "").strip() if graph_definitions else "",
        ]:
            if candidate:
                latest_updated_at = candidate
                break
        return {
            "graph_count": len(graph_definitions),
            "run_count": len(graph_run_refs),
            "latest_graph_id": latest_graph_id,
            "latest_run_id": latest_run_id,
            "latest_run_status": latest_run_status,
            "latest_updated_at": latest_updated_at,
            "graph_status_counts": graph_status_counts,
            "run_status_counts": run_status_counts,
        }

    def _select_reloaded_task(
        self,
        tasks: list[dict[str, Any]],
        *,
        current_task_id: str,
        preferred_thread_id: str,
    ) -> dict[str, Any] | None:
        existing = self._find_task(tasks, current_task_id)
        if existing:
            return existing
        if preferred_thread_id:
            for task in tasks:
                for item in list(task.get("provider_threads") or []):
                    if str((item or {}).get("thread_id") or "").strip() == preferred_thread_id:
                        return dict(task)
        if tasks:
            tasks = [dict(item) for item in tasks]
            tasks.sort(key=lambda item: str(item.get("updated_at") or item.get("created_at") or ""), reverse=True)
            return tasks[0]
        return None

    def _preferred_active_thread_id(self, task: dict[str, Any], provider_threads: list[dict[str, Any]]) -> str:
        active_thread_id = str(task.get("active_provider_thread_id") or "").strip()
        live_threads = [
            dict(item)
            for item in provider_threads
            if not item.get("missing_at") and _provider_thread_entry_is_plausible(item)
        ]
        live_ids = {str(item.get("thread_id") or "").strip() for item in live_threads}
        known_ids = {str(item.get("thread_id") or "").strip() for item in provider_threads}
        project_thread_id = str((self._projects.current_project or {}).get("current_thread_id") or "").strip()
        current_task_id = str((self._projects.current_project or {}).get("current_task_id") or "").strip()
        task_id = str(task.get("task_id") or "").strip()
        if active_thread_id and active_thread_id in live_ids:
            return active_thread_id
        if task_id and current_task_id == task_id and project_thread_id and project_thread_id in live_ids:
            return project_thread_id
        if project_thread_id and project_thread_id in live_ids:
            return project_thread_id
        if live_threads:
            live_threads.sort(key=lambda item: str(item.get("updated_at") or ""), reverse=True)
            return str(live_threads[0].get("thread_id") or "").strip()
        if active_thread_id and active_thread_id in known_ids:
            return active_thread_id
        if project_thread_id and project_thread_id in known_ids:
            return project_thread_id
        if provider_threads:
            provider_threads = [dict(item) for item in provider_threads]
            provider_threads.sort(key=lambda item: str(item.get("updated_at") or item.get("created_at") or ""), reverse=True)
            return str(provider_threads[0].get("thread_id") or "").strip()
        return ""

    def _thread_context_hint(self, thread_id: str) -> dict[str, Any]:
        """Return secret-free task continuity hints for a known Codex thread."""
        if not thread_id:
            return {}
        shell_root = self._projects.require_workspace_root() / WORKSPACE_STATE_DIRNAME
        merged: dict[str, Any] = {}
        context_state = read_json(shell_root / "project_context_state.json", {})
        context_threads = context_state.get("threads") if isinstance(context_state, dict) else None
        if isinstance(context_threads, dict):
            context_entry = context_threads.get(thread_id)
            if isinstance(context_entry, dict):
                merged.update(context_entry)
        thread_cache = read_json(shell_root / "thread_cache.json", {})
        cache_entry = (thread_cache.get("by_id") or {}).get(thread_id) if isinstance(thread_cache, dict) else None
        if isinstance(cache_entry, dict):
            merged.update({key: value for key, value in cache_entry.items() if value is not None})
        provider_id = merged.get("provider_id")
        if not provider_id:
            model_text = str(merged.get("model") or "")
            if "/" in model_text:
                provider_id = model_text.split("/", 1)[0]
        return redact_sensitive(
            {
                "profile_id": merged.get("profile_id"),
                "provider_id": provider_id,
                "model": merged.get("model"),
                "reasoning_effort": merged.get("reasoning_effort"),
                "permission_mode": merged.get("permission_mode"),
                "collaboration_mode": merged.get("collaboration_mode"),
                "name": merged.get("name"),
                "goal": merged.get("goal"),
                "latest_plan": merged.get("latest_plan"),
            }
        )

    def _save_task(self, task: dict[str, Any]) -> None:
        state = self._state()
        persisted_task = self._find_task(list(state.get("tasks") or []), str(task.get("task_id") or ""))
        if persisted_task:
            task = self._merge_task_graph_state(persisted_task, task)
        updated_tasks = self._replace_task(list(state.get("tasks") or []), task)
        updated_tasks = self._enforce_task_thread_ownership(updated_tasks, owner_task=task)
        task = self._find_task(updated_tasks, str(task.get("task_id") or "")) or task
        state["tasks"] = updated_tasks
        state["current_task_id"] = task["task_id"]
        state["updated_at"] = now_iso()
        self._write_state(state)
        self._sync_project_current_task(task)

    def _merge_task_graph_state(self, persisted_task: dict[str, Any], incoming_task: dict[str, Any]) -> dict[str, Any]:
        merged = dict(persisted_task)
        merged.update(incoming_task)
        merged["graph_definitions"] = self._merge_task_graph_definitions(
            persisted_task.get("graph_definitions"),
            incoming_task.get("graph_definitions"),
        )
        merged["graph_run_refs"] = self._merge_task_graph_run_refs(
            persisted_task.get("graph_run_refs"),
            incoming_task.get("graph_run_refs"),
        )
        merged["graph_snapshot_refs"] = self._merge_task_graph_snapshot_refs(
            persisted_task.get("graph_snapshot_refs"),
            incoming_task.get("graph_snapshot_refs"),
        )
        return merged

    def _merge_task_graph_definitions(self, persisted: Any, incoming: Any) -> list[dict[str, Any]]:
        by_id: dict[str, dict[str, Any]] = {}
        ordered_ids: list[str] = []
        for source in (incoming, persisted):
            for item in list(source or []):
                if not isinstance(item, dict):
                    continue
                graph_id = str(item.get("graph_id") or "").strip()
                if not graph_id:
                    continue
                if graph_id not in ordered_ids:
                    ordered_ids.append(graph_id)
                if graph_id not in by_id:
                    by_id[graph_id] = dict(item)
        merged = [by_id[graph_id] for graph_id in ordered_ids if graph_id in by_id]
        return self._prune_graph_definitions(merged, task_id="")

    def _orchestration_graph_for_task_graph(self, task_graph: dict[str, Any]) -> dict[str, Any]:
        base = dict(task_graph.get("orchestration_graph") or {})
        if base:
            return self._sync_orchestration_graph_with_task_graph(base, task_graph=task_graph)
        return self._sync_orchestration_graph_with_task_graph(
            lift_task_graph_to_agent_orchestration_graph(task_graph),
            task_graph=task_graph,
        )

    def _sync_orchestration_graph_with_task_graph(self, orchestration_graph: dict[str, Any], *, task_graph: dict[str, Any]) -> dict[str, Any]:
        executable_graph = self._reachable_task_graph_projection(task_graph)
        canonical_lifted = lift_task_graph_to_agent_orchestration_graph(executable_graph)
        existing_graph = deepcopy(orchestration_graph) if isinstance(orchestration_graph, dict) else {}
        synced = {**deepcopy(canonical_lifted), **existing_graph}
        synced["graph_id"] = task_graph["graph_id"]
        synced["task_id"] = task_graph["task_id"]
        synced["title"] = task_graph["title"]
        synced["template_id"] = task_graph["template_id"]
        synced["status"] = task_graph["status"]
        synced["state_version"] = task_graph["state_version"]
        synced["graph_policy"] = {
            **dict(synced.get("graph_policy") or {}),
            "entry_node_ids": list(dict(task_graph.get("graph_policy") or {}).get("entry_node_ids") or []),
        }
        metadata = dict(synced.get("metadata") or {})
        metadata["updated_at"] = str(task_graph.get("updated_at") or metadata.get("updated_at") or now_iso())
        synced["metadata"] = metadata
        schema_registry = dict(synced.get("schema_registry") or {})
        node_schema_refs: dict[str, str] = {}

        node_map = {
            str(item.get("node_id") or "").strip(): dict(item)
            for item in list(executable_graph.get("nodes") or [])
            if isinstance(item, dict)
        }
        existing_nodes = {
            str(item.get("node_id") or "").strip(): deepcopy(item)
            for item in list(existing_graph.get("nodes") or [])
            if isinstance(item, dict) and str(item.get("node_id") or "").strip()
        }
        synced["nodes"] = [
            {
                **deepcopy(item),
                **deepcopy(existing_nodes.get(str(item.get("node_id") or "").strip()) or {}),
            }
            for item in list(canonical_lifted.get("nodes") or [])
            if isinstance(item, dict)
        ]
        for node in list(synced.get("nodes") or []):
            if not isinstance(node, dict):
                continue
            task_node = node_map.get(str(node.get("node_id") or "").strip())
            if not task_node:
                continue
            node["kind"] = task_node.get("kind")
            node["label"] = task_node.get("label")
            node["card_ref"] = task_node.get("agent_card_ref")
            routing = dict(node.get("routing") or {})
            provider_id = str(task_node.get("provider_id") or "").strip()
            model_id = str(task_node.get("model_id") or "").strip()
            if provider_id and model_id:
                routing.update(
                    {
                        "selection_mode": "explicit",
                        "provider_id": provider_id,
                        "model_id": model_id,
                    }
                )
            elif provider_id:
                routing.update({"selection_mode": "explicit", "provider_id": provider_id})
            elif model_id:
                routing.update({"selection_mode": "explicit", "model_id": model_id})
            node["routing"] = routing
            prompt = dict(node.get("prompt") or {})
            human_summary_template = str(task_node.get("human_summary_template") or "").strip()
            if human_summary_template:
                prompt["template"] = human_summary_template
            node["prompt"] = prompt
            execution = dict(node.get("execution") or {})
            execution_policy = dict(task_node.get("execution_policy") or {})
            if execution_policy:
                execution["spawn_mode"] = execution_policy.get("spawn_mode", execution.get("spawn_mode"))
                execution["timeout_ms"] = execution_policy.get("timeout_ms", execution.get("timeout_ms"))
                execution["retry_policy"] = deepcopy(execution_policy.get("retry_policy") or execution.get("retry_policy") or {"max_attempts": 1})
                if execution.get("spawn_mode") == "subagent_worker":
                    execution["subagent_policy"] = deepcopy(
                        execution_policy.get("subagent_policy")
                        or execution.get("subagent_policy")
                        or {
                            "isolation_mode": "lane",
                            "max_turns": 8,
                            "allow_direct_teammate_messages": False,
                            "share_worktree": False,
                            "allow_nested_subagents": False,
                        }
                    )
            node["execution"] = execution
            safety = dict(node.get("safety") or {})
            if execution_policy:
                safety["allow_provider_calls"] = bool(execution_policy.get("allow_provider_calls"))
                safety["allow_code_changes"] = bool(execution_policy.get("allow_code_changes"))
                safety["allow_install"] = bool(execution_policy.get("allow_install"))
                safety["requires_human_approval"] = bool(execution_policy.get("requires_human_approval"))
            approval_kind = str(dict(task_node.get("approval_gate") or {}).get("review_kind") or "").strip()
            if approval_kind:
                safety["approval_kind"] = approval_kind
            node["safety"] = safety
            output_contract = dict(node.get("output_contract") or {})
            task_output_contract = dict(task_node.get("output_contract") or {})
            output_contract["human_summary_required"] = bool(task_output_contract.get("human_summary_required", output_contract.get("human_summary_required", True)))
            output_contract["mode"] = "artifact_only" if bool(task_output_contract.get("artifact_only")) else "structured_and_artifacts"
            artifact_outputs = [
                str(item).strip()
                for item in list(task_output_contract.get("artifact_outputs") or [])
                if str(item).strip()
            ]
            if artifact_outputs:
                existing_specs = [
                    deepcopy(item)
                    for item in list(output_contract.get("artifact_specs") or [])
                    if isinstance(item, dict)
                ]
                output_contract["artifact_specs"] = [
                    {
                        "kind": item if item in ARTIFACT_KINDS else "structured_json",
                        "id": self._artifact_spec_id_for_kind(existing_specs, item),
                    }
                    for item in artifact_outputs
                ]
            machine_schema = task_output_contract.get("machine_result_schema")
            if isinstance(machine_schema, dict) and machine_schema:
                schema_ref = f"schema.{task_node['node_id']}.machine_result"
                schema_registry[schema_ref] = deepcopy(machine_schema)
                output_contract["machine_result_schema_ref"] = schema_ref
                node_schema_refs[str(task_node["node_id"])] = schema_ref
            node["output_contract"] = output_contract
            node["ports"] = self._sync_orchestration_node_ports(
                node=dict(node),
                output_contract=output_contract,
            )
            ui = dict(node.get("ui") or {})
            ui["position"] = deepcopy(task_node.get("position") or ui.get("position") or {"x": 0, "y": 0})
            node["ui"] = ui
            node["status"] = task_node.get("status")
        synced["schema_registry"] = schema_registry

        task_node_positions = {
            str(item.get("node_id") or "").strip(): dict(item.get("position") or {})
            for item in list(executable_graph.get("nodes") or [])
            if isinstance(item, dict) and str(item.get("node_id") or "").strip()
        }
        edge_map = {
            str(item.get("edge_id") or "").strip(): dict(item)
            for item in list(executable_graph.get("edges") or [])
            if isinstance(item, dict)
        }
        existing_edges = {
            str(item.get("edge_id") or "").strip(): deepcopy(item)
            for item in list(existing_graph.get("edges") or [])
            if isinstance(item, dict) and str(item.get("edge_id") or "").strip()
        }
        synced["edges"] = [
            {
                **deepcopy(item),
                **deepcopy(existing_edges.get(str(item.get("edge_id") or "").strip()) or {}),
            }
            for item in list(canonical_lifted.get("edges") or [])
            if isinstance(item, dict)
        ]
        synced_edges: list[dict[str, Any]] = []
        for edge in list(synced.get("edges") or []):
            if not isinstance(edge, dict):
                continue
            task_edge = edge_map.get(str(edge.get("edge_id") or "").strip())
            if not task_edge:
                synced_edges.append(edge)
                continue
            edge["from_node_id"] = task_edge.get("from_node_id")
            edge["to_node_id"] = task_edge.get("to_node_id")
            edge["edge_type"] = task_edge.get("edge_type")
            edge["context_policy"] = deepcopy(task_edge.get("context_policy") or edge.get("context_policy") or {})
            handoff_contract = dict(edge.get("handoff_contract") or {})
            task_handoff_contract = task_edge.get("handoff_contract")
            if isinstance(task_handoff_contract, dict):
                handoff_contract.update(deepcopy(task_handoff_contract))
            source_schema_ref = str(node_schema_refs.get(str(edge["from_node_id"]) or "") or "").strip()
            if source_schema_ref:
                handoff_contract["required_output_schema_refs"] = [source_schema_ref]
            handoff_contract["port_bindings"] = self._default_handoff_port_bindings(
                synced,
                from_node_id=str(edge["from_node_id"] or ""),
                to_node_id=str(edge["to_node_id"] or ""),
                existing=list(handoff_contract.get("port_bindings") or []),
            )
            edge["handoff_contract"] = handoff_contract
            edge["status"] = task_edge.get("status")
            synced_edges.append(edge)

        existing_edge_ids = {
            str(item.get("edge_id") or "").strip()
            for item in synced_edges
            if isinstance(item, dict) and str(item.get("edge_id") or "").strip()
        }
        for task_edge in edge_map.values():
            edge_id = str(task_edge.get("edge_id") or "").strip()
            if not edge_id or edge_id in existing_edge_ids:
                continue
            from_node_id = str(task_edge.get("from_node_id") or "").strip()
            to_node_id = str(task_edge.get("to_node_id") or "").strip()
            source_schema_ref = str(node_schema_refs.get(from_node_id) or "").strip()
            task_handoff_contract = task_edge.get("handoff_contract") if isinstance(task_edge.get("handoff_contract"), dict) else {}
            from_position = task_node_positions.get(from_node_id) or {}
            to_position = task_node_positions.get(to_node_id) or {}
            synced_edges.append(
                {
                    "edge_id": edge_id,
                    "from_node_id": from_node_id,
                    "to_node_id": to_node_id,
                    "edge_type": task_edge.get("edge_type"),
                    "handoff_contract": {
                        "message_template": str(task_handoff_contract.get("message_template") or f"Deliver the required output from {from_node_id or 'source'} to {to_node_id or 'target'}."),
                        "message_part_modes": [
                            str(item).strip()
                            for item in list(task_handoff_contract.get("message_part_modes") or ["machine_result", "human_summary"])
                            if str(item).strip()
                        ],
                        "required_output_schema_refs": [source_schema_ref] if source_schema_ref else [
                            str(item).strip()
                            for item in list(task_handoff_contract.get("required_output_schema_refs") or [])
                            if str(item).strip()
                        ],
                        "port_bindings": self._default_handoff_port_bindings(
                            synced,
                            from_node_id=from_node_id,
                            to_node_id=to_node_id,
                            existing=list(task_handoff_contract.get("port_bindings") or []),
                        ),
                    },
                    "context_policy": deepcopy(task_edge.get("context_policy") or {}),
                    "ui": {
                        "position": {
                            "x": (float(from_position.get("x") or 0) + float(to_position.get("x") or 0)) / 2,
                            "y": (float(from_position.get("y") or 0) + float(to_position.get("y") or 0)) / 2,
                        }
                    },
                    "status": task_edge.get("status") or "ready",
                }
            )
        synced["edges"] = synced_edges
        return synced

    @staticmethod
    def _reachable_task_graph_projection(task_graph: dict[str, Any]) -> dict[str, Any]:
        projected = deepcopy(task_graph)
        nodes = [dict(item) for item in list(projected.get("nodes") or []) if isinstance(item, dict)]
        edges = [dict(item) for item in list(projected.get("edges") or []) if isinstance(item, dict)]
        node_ids = {
            str(item.get("node_id") or "").strip()
            for item in nodes
            if str(item.get("node_id") or "").strip()
        }
        entry_node_ids = [
            str(item).strip()
            for item in list(dict(projected.get("graph_policy") or {}).get("entry_node_ids") or [])
            if str(item).strip() in node_ids
        ]
        adjacency: dict[str, list[str]] = {node_id: [] for node_id in node_ids}
        for edge in edges:
            from_node_id = str(edge.get("from_node_id") or "").strip()
            to_node_id = str(edge.get("to_node_id") or "").strip()
            if from_node_id in node_ids and to_node_id in node_ids:
                adjacency.setdefault(from_node_id, []).append(to_node_id)

        reachable: set[str] = set()
        pending = list(reversed(entry_node_ids))
        while pending:
            node_id = pending.pop()
            if node_id in reachable:
                continue
            reachable.add(node_id)
            pending.extend(reversed(adjacency.get(node_id, [])))

        projected["nodes"] = [
            item for item in nodes if str(item.get("node_id") or "").strip() in reachable
        ]
        projected["edges"] = [
            item
            for item in edges
            if str(item.get("from_node_id") or "").strip() in reachable
            and str(item.get("to_node_id") or "").strip() in reachable
        ]
        projected.pop("orchestration_graph", None)
        return projected

    def _sync_orchestration_node_ports(self, *, node: dict[str, Any], output_contract: dict[str, Any]) -> dict[str, Any]:
        ports = dict(node.get("ports") or {})
        inputs = [deepcopy(item) for item in list(ports.get("inputs") or []) if isinstance(item, dict)]
        outputs = [deepcopy(item) for item in list(ports.get("outputs") or []) if isinstance(item, dict)]
        if not inputs:
            inputs = [{"port_id": "task_context", "label": "Task Context", "port_type": "text", "shape": "single", "required": True}]

        machine_schema_ref = str(output_contract.get("machine_result_schema_ref") or "").strip()
        artifact_specs = [deepcopy(item) for item in list(output_contract.get("artifact_specs") or []) if isinstance(item, dict)]
        by_id = {
            str(item.get("port_id") or "").strip(): item
            for item in outputs
            if str(item.get("port_id") or "").strip()
        }
        normalized_outputs: list[dict[str, Any]] = []
        if machine_schema_ref:
            machine_port = dict(by_id.get("machine_result") or {})
            machine_port.update(
                {
                    "port_id": "machine_result",
                    "label": str(machine_port.get("label") or "Machine Result"),
                    "port_type": "structured_json",
                    "shape": "single",
                    "required": True,
                    "schema_ref": machine_schema_ref,
                }
            )
            normalized_outputs.append(machine_port)
        for spec in artifact_specs:
            artifact_id = str(spec.get("id") or spec.get("kind") or "artifact").strip()
            artifact_kind = str(spec.get("kind") or "").strip() or "structured_json"
            artifact_port = dict(by_id.get(artifact_id) or {})
            artifact_port.update(
                {
                    "port_id": artifact_id,
                    "label": str(artifact_port.get("label") or artifact_id.replace("_", " ").title()),
                    "port_type": self._artifact_kind_to_port_type(artifact_kind),
                    "shape": "single",
                    "required": False,
                    "artifact_kind": artifact_kind,
                }
            )
            artifact_port.pop("schema_ref", None)
            normalized_outputs.append(artifact_port)
        if not normalized_outputs:
            normalized_outputs = outputs or [{"port_id": "human_summary", "label": "Human Summary", "port_type": "text", "shape": "single", "required": True}]
        return {"inputs": inputs, "outputs": normalized_outputs}

    def _default_handoff_port_bindings(self, orchestration_graph: dict[str, Any], *, from_node_id: str, to_node_id: str, existing: list[Any]) -> list[dict[str, str]]:
        normalized_existing: list[dict[str, str]] = []
        for item in existing:
            if not isinstance(item, dict):
                continue
            from_port_id = str(item.get("from_port_id") or "").strip()
            to_port_id = str(item.get("to_port_id") or "").strip()
            if from_port_id and to_port_id:
                normalized_existing.append({"from_port_id": from_port_id, "to_port_id": to_port_id})
        if normalized_existing:
            return normalized_existing
        node_map = {
            str(item.get("node_id") or "").strip(): dict(item)
            for item in list(orchestration_graph.get("nodes") or [])
            if isinstance(item, dict)
        }
        source_outputs = {
            str(item.get("port_id") or "").strip(): dict(item)
            for item in list(dict(node_map.get(from_node_id) or {}).get("ports", {}).get("outputs") or [])
            if isinstance(item, dict) and str(item.get("port_id") or "").strip()
        }
        target_inputs = {
            str(item.get("port_id") or "").strip(): dict(item)
            for item in list(dict(node_map.get(to_node_id) or {}).get("ports", {}).get("inputs") or [])
            if isinstance(item, dict) and str(item.get("port_id") or "").strip()
        }
        bindings: list[dict[str, str]] = []
        if "machine_result" in source_outputs:
            preferred_targets = [port_id for port_id in target_inputs if port_id != "task_context"] or (["task_context"] if "task_context" in target_inputs else [])
            if preferred_targets:
                bindings.append({"from_port_id": "machine_result", "to_port_id": preferred_targets[0]})
        for port_id in source_outputs:
            if port_id == "machine_result":
                continue
            if port_id in target_inputs:
                bindings.append({"from_port_id": port_id, "to_port_id": port_id})
                continue
            source_type = str(source_outputs[port_id].get("port_type") or "").strip()
            target_match = next(
                (
                    target_id
                    for target_id, target in target_inputs.items()
                    if target_id != "task_context" and str(target.get("port_type") or "").strip() == source_type
                ),
                "",
            )
            if target_match:
                bindings.append({"from_port_id": port_id, "to_port_id": target_match})
        if not bindings and source_outputs and target_inputs:
            first_source = next(iter(source_outputs))
            first_target = next(iter(target_inputs))
            bindings.append({"from_port_id": first_source, "to_port_id": first_target})
        return bindings

    @staticmethod
    def _artifact_spec_id_for_kind(existing_specs: list[dict[str, Any]], artifact_kind: str) -> str:
        for spec in existing_specs:
            if str(spec.get("kind") or "").strip() == artifact_kind:
                existing_id = str(spec.get("id") or "").strip()
                if existing_id:
                    return existing_id
        return artifact_kind

    @staticmethod
    def _artifact_kind_to_port_type(kind: str) -> str:
        mapping = {
            "structured_json": "structured_json",
            "image": "image",
            "audio": "audio",
            "video": "video",
            "document_extract": "document",
            "code_diff": "code_diff",
            "dataset": "dataset",
            "approval_record": "approval_record",
            "validation_report": "agent_report",
            "run_summary": "agent_report",
            "test_report": "agent_report",
            "text_report": "text",
            "diagnostic_bundle": "agent_report",
            "graph_definition": "structured_json",
        }
        return mapping.get(kind, "text")

    def _merge_task_graph_run_refs(self, persisted: Any, incoming: Any) -> list[dict[str, Any]]:
        by_id: dict[str, dict[str, Any]] = {}
        for source in (persisted, incoming):
            for item in list(source or []):
                if not isinstance(item, dict):
                    continue
                run_id = str(item.get("run_id") or "").strip()
                if not run_id:
                    continue
                candidate = dict(item)
                existing = by_id.get(run_id)
                by_id[run_id] = self._merge_task_graph_run_ref(existing, candidate)
        merged = sorted(
            by_id.values(),
            key=self._graph_run_ref_sort_key,
            reverse=True,
        )
        return merged[:GRAPH_RUN_REF_LIMIT]

    def _merge_task_graph_run_ref(
        self,
        existing: dict[str, Any] | None,
        candidate: dict[str, Any] | None,
    ) -> dict[str, Any]:
        if not existing:
            return dict(candidate or {})
        if not candidate:
            return dict(existing)
        left = dict(existing)
        right = dict(candidate)
        left_status = str(left.get("status") or "").strip()
        right_status = str(right.get("status") or "").strip()
        terminal_statuses = {"completed", "failed", "cancelled", "partial", "dry_run_passed", "dry_run_blocked"}
        left_terminal = left_status in terminal_statuses
        right_terminal = right_status in terminal_statuses
        left_sort_key = self._graph_run_ref_sort_key(left)
        right_sort_key = self._graph_run_ref_sort_key(right)
        if right_sort_key != left_sort_key:
            right_preferred = right_sort_key > left_sort_key
        elif right_terminal != left_terminal:
            right_preferred = right_terminal
        else:
            right_preferred = True
        preferred = right if right_preferred else left
        fallback = left if right_preferred else right
        preferred_sort_key = right_sort_key if right_preferred else left_sort_key
        fallback_sort_key = left_sort_key if right_preferred else right_sort_key
        worker_bindings, _worker_bindings_from_preferred = self._select_task_graph_run_ref_object_array(
            preferred=preferred.get("worker_bindings"),
            fallback=fallback.get("worker_bindings"),
            preferred_sort_key=preferred_sort_key,
            fallback_sort_key=fallback_sort_key,
            key_for=lambda item: str(item.get("node_id") or item.get("binding_id") or "").strip(),
        )
        artifact_refs, _artifact_refs_from_preferred = self._select_task_graph_run_ref_object_array(
            preferred=preferred.get("artifact_refs"),
            fallback=fallback.get("artifact_refs"),
            preferred_sort_key=preferred_sort_key,
            fallback_sort_key=fallback_sort_key,
            key_for=lambda item: (
                f"{str(item.get('artifact_id') or '').strip()}|"
                f"{str(item.get('path') or '').strip()}"
            ),
        )
        diagnostic_refs, _diagnostic_refs_from_preferred = self._select_task_graph_run_ref_object_array(
            preferred=preferred.get("diagnostic_refs"),
            fallback=fallback.get("diagnostic_refs"),
            preferred_sort_key=preferred_sort_key,
            fallback_sort_key=fallback_sort_key,
            key_for=lambda item: (
                f"{str(item.get('artifact_id') or '').strip()}|"
                f"{str(item.get('path') or '').strip()}"
            ),
        )
        timeline_events, timeline_source = self._select_task_graph_run_ref_timeline_events(
            preferred=preferred,
            fallback=fallback,
            preferred_sort_key=preferred_sort_key,
            fallback_sort_key=fallback_sort_key,
        )
        merged = {**fallback, **preferred}
        merged["node_status_counts"] = self._merge_task_graph_run_ref_count_map(
            fallback.get("node_status_counts"),
            preferred.get("node_status_counts"),
        )
        merged["node_outcome_counts"] = self._merge_task_graph_run_ref_count_map(
            fallback.get("node_outcome_counts"),
            preferred.get("node_outcome_counts"),
        )
        merged["worker_bindings"] = worker_bindings
        merged["artifact_refs"] = artifact_refs
        merged["diagnostic_refs"] = diagnostic_refs
        merged["timeline_events"] = timeline_events
        merged["worker_count"] = max(
            int(preferred.get("worker_count") or 0),
            int(fallback.get("worker_count") or 0),
            len(worker_bindings),
        )
        merged["artifact_count"] = max(
            int(preferred.get("artifact_count") or 0),
            int(fallback.get("artifact_count") or 0),
            len(artifact_refs),
        )
        merged["event_count"] = max(
            int(timeline_source.get("event_count") or 0),
            len(timeline_events),
        )
        latest_event = timeline_events[-1] if timeline_events else None
        latest_event_at = str(dict(latest_event or {}).get("created_at") or "").strip()
        latest_event_type = str(dict(latest_event or {}).get("event_type") or "").strip()
        merged["latest_event_at"] = (
            latest_event_at
            or str(preferred.get("latest_event_at") or "").strip()
            or str(fallback.get("latest_event_at") or "").strip()
            or None
        )
        merged["latest_event_type"] = (
            latest_event_type
            or str(preferred.get("latest_event_type") or "").strip()
            or str(fallback.get("latest_event_type") or "").strip()
            or None
        )
        merged["updated_at"] = (
            str(merged.get("latest_event_at") or "").strip()
            or str(preferred.get("updated_at") or "").strip()
            or str(fallback.get("updated_at") or "").strip()
            or now_iso()
        )
        return merged

    def _select_task_graph_run_ref_timeline_events(
        self,
        *,
        preferred: dict[str, Any],
        fallback: dict[str, Any],
        preferred_sort_key: tuple[float, float, str],
        fallback_sort_key: tuple[float, float, str],
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        preferred_timeline = self._compact_graph_run_timeline_events(preferred.get("timeline_events"))
        fallback_timeline = self._compact_graph_run_timeline_events(fallback.get("timeline_events"))
        if preferred_timeline and fallback_timeline:
            if preferred_sort_key > fallback_sort_key:
                return preferred_timeline, preferred
            if fallback_sort_key > preferred_sort_key:
                return fallback_timeline, fallback
            if len(preferred_timeline) >= len(fallback_timeline):
                return preferred_timeline, preferred
            return fallback_timeline, fallback
        if preferred_timeline:
            return preferred_timeline, preferred
        if fallback_timeline:
            return fallback_timeline, fallback
        return [], preferred

    def _select_task_graph_run_ref_object_array(
        self,
        *,
        preferred: Any,
        fallback: Any,
        preferred_sort_key: tuple[float, float, str],
        fallback_sort_key: tuple[float, float, str],
        key_for: Callable[[dict[str, Any]], str],
    ) -> tuple[list[dict[str, Any]], bool]:
        preferred_items = self._compact_task_graph_run_ref_object_array(preferred, key_for=key_for)
        fallback_items = self._compact_task_graph_run_ref_object_array(fallback, key_for=key_for)
        if preferred_items and fallback_items:
            if preferred_sort_key > fallback_sort_key:
                return preferred_items, True
            if fallback_sort_key > preferred_sort_key:
                return fallback_items, False
            if len(preferred_items) >= len(fallback_items):
                return preferred_items, True
            return fallback_items, False
        if preferred_items:
            return preferred_items, True
        if fallback_items:
            return fallback_items, False
        return [], True

    @staticmethod
    def _compact_task_graph_run_ref_object_array(
        value: Any,
        *,
        key_for: Callable[[dict[str, Any]], str],
    ) -> list[dict[str, Any]]:
        merged: dict[str, dict[str, Any]] = {}
        anonymous: list[dict[str, Any]] = []
        for item in list(value or []):
            if not isinstance(item, dict):
                continue
            clean = dict(item)
            key = key_for(clean)
            if not key:
                anonymous.append(clean)
                continue
            merged[key] = {**merged.get(key, {}), **clean}
        return [*merged.values(), *anonymous]

    @staticmethod
    def _merge_task_graph_run_ref_count_map(left: Any, right: Any) -> dict[str, int]:
        merged: dict[str, int] = {}
        for source in (left, right):
            for key, value in dict(source or {}).items():
                clean_key = str(key or "").strip()
                if not clean_key:
                    continue
                merged[clean_key] = max(int(merged.get(clean_key) or 0), int(value or 0))
        return merged

    def _merge_task_graph_snapshot_refs(self, persisted: Any, incoming: Any) -> list[dict[str, Any]]:
        by_id: dict[str, dict[str, Any]] = {}
        for source in (persisted, incoming):
            for item in list(source or []):
                if not isinstance(item, dict):
                    continue
                snapshot_id = str(item.get("snapshot_id") or "").strip()
                if not snapshot_id:
                    continue
                existing = by_id.get(snapshot_id)
                candidate = dict(item)
                if existing is None or self._graph_snapshot_ref_sort_key(candidate) >= self._graph_snapshot_ref_sort_key(existing):
                    by_id[snapshot_id] = candidate
        merged = sorted(
            by_id.values(),
            key=self._graph_snapshot_ref_sort_key,
            reverse=True,
        )
        return merged[:GRAPH_SNAPSHOT_REF_LIMIT]

    @staticmethod
    def _graph_run_ref_sort_key(item: dict[str, Any]) -> tuple[float, float, str]:
        updated = str(item.get("updated_at") or "").strip()
        created = str(item.get("created_at") or "").strip()
        updated_ts = dt.datetime.fromisoformat(updated).timestamp() if updated else float("-inf")
        created_ts = dt.datetime.fromisoformat(created).timestamp() if created else float("-inf")
        return (updated_ts, created_ts, str(item.get("run_id") or "").strip())

    @staticmethod
    def _graph_snapshot_ref_sort_key(item: dict[str, Any]) -> tuple[float, float, str]:
        updated = str(item.get("updated_at") or "").strip()
        created = str(item.get("created_at") or "").strip()
        updated_ts = dt.datetime.fromisoformat(updated).timestamp() if updated else float("-inf")
        created_ts = dt.datetime.fromisoformat(created).timestamp() if created else float("-inf")
        return (updated_ts, created_ts, str(item.get("snapshot_id") or "").strip())

    def _sync_project_current_task(self, task: dict[str, Any]) -> None:
        self._projects.reconcile_task_projection(task)

    def _project_sync_needed(self, task: dict[str, Any]) -> bool:
        project = self._project()
        task_id = str(task.get("task_id") or "")
        active_thread = str(task.get("active_provider_thread_id") or "")
        return (
            str(project.get("current_task_id") or "") != task_id
            or str(project.get("current_thread_id") or "") != active_thread
        )

    def _replace_task(self, tasks: list[dict[str, Any]], task: dict[str, Any]) -> list[dict[str, Any]]:
        return [task, *[item for item in tasks if item.get("task_id") != task.get("task_id")]][:100]

    def _enforce_task_thread_ownership(self, tasks: list[dict[str, Any]], *, owner_task: dict[str, Any]) -> list[dict[str, Any]]:
        owner_task_id = str(owner_task.get("task_id") or "").strip()
        if not owner_task_id:
            return tasks[:100]
        owned_thread_ids = {
            str(item.get("thread_id") or "").strip()
            for item in [
                *list(owner_task.get("provider_threads") or []),
                *list(owner_task.get("fork_threads") or []),
            ]
            if isinstance(item, dict) and str(item.get("thread_id") or "").strip()
        }
        if not owned_thread_ids:
            return tasks[:100]
        normalized_tasks: list[dict[str, Any]] = []
        for item in tasks[:100]:
            if not isinstance(item, dict):
                continue
            task = dict(item)
            task_id = str(task.get("task_id") or "").strip()
            if task_id == owner_task_id:
                normalized_tasks.append(task)
                continue
            changed = False
            provider_threads = [
                dict(entry)
                for entry in list(task.get("provider_threads") or [])
                if isinstance(entry, dict)
            ]
            filtered_provider_threads = [
                entry for entry in provider_threads if str(entry.get("thread_id") or "").strip() not in owned_thread_ids
            ]
            if filtered_provider_threads != provider_threads:
                task["provider_threads"] = filtered_provider_threads
                changed = True
            fork_threads = [
                dict(entry)
                for entry in list(task.get("fork_threads") or [])
                if isinstance(entry, dict)
            ]
            filtered_fork_threads = [
                entry for entry in fork_threads if str(entry.get("thread_id") or "").strip() not in owned_thread_ids
            ]
            if filtered_fork_threads != fork_threads:
                task["fork_threads"] = filtered_fork_threads
                changed = True
            active_thread_id = str(task.get("active_provider_thread_id") or "").strip()
            if active_thread_id and active_thread_id in owned_thread_ids:
                task["active_provider_thread_id"] = None
                changed = True
            if changed:
                task["updated_at"] = now_iso()
                task, _ = self._normalize_task(task)
            normalized_tasks.append(task)
        return normalized_tasks[:100]

    def _same_context_ref(self, left: Any, right: Any) -> bool:
        if not isinstance(left, dict) or not isinstance(right, dict):
            return False
        return (
            str(left.get("pack_type") or "") == str(right.get("pack_type") or "")
            and str(left.get("path") or "") == str(right.get("path") or "")
        )

    def _find_task(self, tasks: list[dict[str, Any]], task_id: str) -> dict[str, Any] | None:
        if not task_id:
            return None
        for task in tasks:
            if str(task.get("task_id") or "") == task_id:
                return dict(task)
        return None

    def _find_task_for_thread(self, tasks: list[dict[str, Any]], thread_id: str) -> dict[str, Any] | None:
        clean_thread_id = str(thread_id or "").strip()
        if not clean_thread_id:
            return None
        for task in tasks:
            if not isinstance(task, dict):
                continue
            for collection_name in ("provider_threads", "fork_threads"):
                for item in list(task.get(collection_name) or []):
                    if isinstance(item, dict) and str(item.get("thread_id") or "").strip() == clean_thread_id:
                        return dict(task)
        return None

    def _state(self) -> dict[str, Any]:
        state = dict(read_json(self._path(), {"schema_version": TASK_STATE_SCHEMA_VERSION, "current_task_id": None, "tasks": []}))
        state.setdefault("schema_version", TASK_STATE_SCHEMA_VERSION)
        state.setdefault("tasks", [])
        return state

    def _write_state(self, state: dict[str, Any]) -> None:
        self._reject_secret_like(state)
        write_json(self._path(), state)

    def _path(self) -> Path:
        return self._projects.require_workspace_root() / WORKSPACE_STATE_DIRNAME / "tasks.json"

    def _project(self) -> dict[str, Any]:
        project = self._projects.current_project
        if not project:
            raise ValueError("No project is open.")
        return dict(project)

    def _reject_secret_like(self, payload: dict[str, Any]) -> None:
        serialized = str(redact_sensitive(payload))
        if SECRET_RE.search(serialized):
            raise SecurityError("Secret-like content is not allowed in task records.")

    def _resolved_current_task_id(self, *, state: dict[str, Any], project: dict[str, Any] | None = None) -> str:
        project_payload = project if isinstance(project, dict) else self._projects.current_project or {}
        state_task_id = str(state.get("current_task_id") or "").strip()
        if state_task_id:
            return state_task_id
        return str((project_payload or {}).get("current_task_id") or "").strip()


def _canonical_model_key(model: Any) -> str:
    """Normalize display/provider-prefixed model ids for provider-thread reuse only."""
    text = str(model or "").strip().lower()
    if "/" in text:
        text = text.rsplit("/", 1)[-1]
    return text


def _display_model_id(model: Any) -> str | None:
    text = str(model or "").strip()
    if not text:
        return None
    if "/" in text:
        text = text.rsplit("/", 1)[-1]
    return text


def _canonical_effort_key(effort: Any) -> str:
    text = str(effort or "").strip().lower()
    if text == "max":
        return "xhigh"
    return text


def _display_effort(effort: Any, provider_id: Any = None) -> str | None:
    text = str(effort or "").strip()
    if not text:
        return None
    provider = str(provider_id or "").strip().lower()
    if provider.startswith("deepseek") and text.lower() in {"xhigh", "x-high"}:
        return "max"
    return text


def _display_thread_name(name: Any, provider_id: Any = None) -> str | None:
    text = str(name or "").strip()
    if not text:
        return None
    flattened = text.replace("\r", "\n")
    candidate_lines = [line.strip() for line in flattened.splitlines() if line.strip()]
    first_line = candidate_lines[0] if candidate_lines else ""
    first_line = SMOKE_TASK_PREFIX_PATTERN.sub("", first_line).strip()
    lowered_first_line = first_line.lower()
    for marker in AUTO_INJECTED_CONTEXT_NAME_MARKERS:
        if marker in lowered_first_line:
            prefix = first_line[:lowered_first_line.index(marker)].strip(" -:\t")
            first_line = prefix or ""
            break
    if not first_line:
        provider = str(provider_id or "").strip()
        return f"{provider.title() or 'Provider'} thread"
    if first_line.lower().startswith(("astrabridge minimal visual mode:", "lcr minimal visual mode:")):
        provider = str(provider_id or "").strip()
        return f"{provider.title() or 'Provider'} visual review"
    if len(first_line) > 96:
        return f"{first_line[:93].rstrip()}..."
    return first_line


def _display_task_title(title: Any) -> str:
    text = str(title or "").replace("\r", "\n")
    candidate_lines = [line.strip() for line in text.splitlines() if line.strip()]
    first_line = candidate_lines[0] if candidate_lines else str(title or "").strip()
    first_line = SMOKE_TASK_PREFIX_PATTERN.sub("", first_line).strip()
    return first_line


def _provider_thread_entry_is_plausible(item: dict[str, Any]) -> bool:
    """Reject obvious provider/model mismatches left by older handoff bugs.

    Keep this intentionally conservative. OpenAI-compatible providers such as
    Yunwu legitimately expose OpenAI-named models, while a Kimi thread with a
    DeepSeek model cannot be replayed or reused safely.
    """
    provider = str(item.get("provider_id") or "").strip().lower()
    profile = str(item.get("profile_id") or "").strip().lower()
    raw_model = str(item.get("model") or "").strip().lower()
    model = _canonical_model_key(raw_model)
    if not model or (not provider and not profile):
        return True
    if provider.startswith("deepseek"):
        return model.startswith("deepseek")
    if provider in {"kimi", "moonshot"} or profile.startswith(("kimi", "moonshot")):
        return model.startswith(("kimi", "moonshot"))
    if provider in {"qwen", "dashscope"} or profile.startswith(("qwen", "dashscope")):
        return model.startswith("qwen")
    return True


def _provider_thread_route_key(item: dict[str, Any]) -> tuple[str, str, str, str, str, str, str]:
    provider = str(item.get("provider_id") or "").strip().lower()
    model = _canonical_model_key(item.get("model"))
    if not provider and "/" in model:
        provider = model.split("/", 1)[0]
    permission_mode = str(item.get("permission_mode") or "").strip().lower()
    collaboration_mode = str(item.get("collaboration_mode") or "").strip().lower()
    execution_backend = str(item.get("execution_backend") or "").strip().lower() or "app_server"
    role = str(item.get("role") or "provider").strip().lower()
    return (
        provider,
        model,
        _canonical_effort_key(item.get("reasoning_effort")),
        permission_mode,
        collaboration_mode,
        execution_backend,
        role,
    )


def _lane_label(*, provider_id: Any = None, model: Any = None, name: Any = None) -> str:
    display_name = _display_thread_name(name, provider_id)
    if display_name:
        return str(redact_sensitive(display_name))[:160]
    provider = str(provider_id or "").strip()
    display_model = _display_model_id(model)
    if provider and display_model:
        return f"{provider} / {display_model}"
    if display_model:
        return display_model
    if provider:
        return provider
    return "Thread"


def _lane_view(item: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(item, dict):
        return None
    thread_id = str(item.get("thread_id") or "").strip() or None
    provider_id = str(item.get("provider_id") or "").strip() or None
    model = _display_model_id(item.get("model"))
    return {
        "thread_id": thread_id,
        "profile_id": str(item.get("profile_id") or "").strip() or None,
        "provider_id": provider_id,
        "model": model,
        "reasoning_effort": _display_effort(item.get("reasoning_effort"), provider_id),
        "permission_mode": str(item.get("permission_mode") or "").strip() or None,
        "collaboration_mode": str(item.get("collaboration_mode") or "").strip() or None,
        "name": _display_thread_name(item.get("name"), provider_id),
        "label": _lane_label(provider_id=provider_id, model=model, name=item.get("name")),
        "missing_at": str(item.get("missing_at") or "").strip() or None,
        "missing_reason": str(item.get("missing_reason") or "").strip() or None,
        "created_at": str(item.get("created_at") or "").strip() or None,
        "updated_at": str(item.get("updated_at") or "").strip() or None,
    }


def _lane_view_from_handoff_event(event: dict[str, Any] | None, *, source: bool) -> dict[str, Any] | None:
    if not isinstance(event, dict):
        return None
    prefix = "from_" if source else ""
    thread_key = f"{prefix}thread_id" if source else "to_thread_id"
    thread_id = str(event.get(thread_key) or "").strip()
    provider_id = str(event.get(f"{prefix}provider_id") or "").strip() or None
    model = _display_model_id(event.get(f"{prefix}model" if prefix else "model"))
    permission_mode = str(event.get(f"{prefix}permission_mode" if prefix else "permission_mode") or "").strip() or None
    reasoning_effort = _display_effort(
        event.get(f"{prefix}reasoning_effort" if prefix else "reasoning_effort"),
        provider_id,
    )
    profile_id = str(event.get(f"{prefix}profile_id" if prefix else "profile_id") or "").strip() or None
    label = _lane_label(provider_id=provider_id, model=model)
    if not any([thread_id, provider_id, model, profile_id, reasoning_effort]):
        return None
    return {
        "thread_id": thread_id or None,
        "profile_id": profile_id,
        "provider_id": provider_id,
        "model": model,
        "reasoning_effort": reasoning_effort,
        "permission_mode": permission_mode,
        "collaboration_mode": None,
        "name": None,
        "label": label,
        "missing_at": None,
        "missing_reason": None,
        "created_at": str(event.get("created_at") or "").strip() or None,
        "updated_at": str(event.get("created_at") or "").strip() or None,
    }

