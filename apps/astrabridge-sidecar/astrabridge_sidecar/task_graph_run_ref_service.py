from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from .common import now_iso, write_json
from .security import redact_sensitive

if TYPE_CHECKING:
    from .task_service import TaskService


def _optional_int(value: Any) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


class TaskGraphRunRefService:
    """Own task-graph run-ref persistence, merge, and shell-projection helpers."""

    def __init__(self, task_service: "TaskService") -> None:
        self._tasks = task_service

    def task_response_graph_run_refs(self, value: Any, *, limit: int = 12) -> list[dict[str, Any]]:
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
        return compacted[: max(0, int(limit or 0)) or 12]

    def graph_activity_summary(self, task: dict[str, Any]) -> dict[str, Any]:
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

    def graph_run_ref(self, run_id: str | None = None) -> dict[str, Any] | None:
        task = self._tasks._raw_current_task_from_state()  # noqa: SLF001
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
        state = self._tasks._state()  # noqa: SLF001
        task = self._tasks._raw_current_task_from_state(state=state)  # noqa: SLF001
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
        refreshed = self.refresh_compact_graph_run_observability(dict(run_ref))
        refreshed = self.refresh_graph_run_export_report(refreshed)
        task["graph_run_refs"] = [
            refreshed if str(item.get("run_id") or "").strip() == run_id else item
            for item in graph_run_refs
        ]
        task["graph_activity_summary"] = self.graph_activity_summary(task)
        task["updated_at"] = now_iso()
        updated_tasks = self._tasks._replace_task(list(state.get("tasks") or []), task)  # noqa: SLF001
        updated_tasks = self._tasks._enforce_task_thread_ownership(updated_tasks, owner_task=task)  # noqa: SLF001
        task = self._tasks._find_task(updated_tasks, str(task.get("task_id") or "")) or task  # noqa: SLF001
        state["tasks"] = updated_tasks
        state["current_task_id"] = task["task_id"]
        state["updated_at"] = now_iso()
        self._tasks._write_state(state)  # noqa: SLF001
        self._tasks._sync_project_current_task(task)  # noqa: SLF001
        self._tasks.durable_run_store().sync_compact_run_ref(refreshed)
        return {"run_ref": refreshed, "task": self._tasks.task_view(task, compact_graph_runs=True)}

    def refresh_graph_run_export_report(self, run_ref: dict[str, Any]) -> dict[str, Any]:
        clean_run = dict(run_ref or {})
        report_rel = self._graph_run_export_report_path(clean_run)
        if not report_rel:
            return clean_run
        workspace_root = self._tasks._projects.require_workspace_root()  # noqa: SLF001
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
        clean_run["diagnostic_refs"] = self._tasks._merge_graph_run_diagnostic_refs(  # noqa: SLF001
            [
                *[dict(item) for item in list(clean_run.get("diagnostic_refs") or []) if isinstance(item, dict)],
                export_ref,
            ]
        )
        return clean_run

    @staticmethod
    def _graph_run_export_report_path(run_ref: dict[str, Any]) -> Path | None:
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

    def refresh_compact_graph_run_observability(self, run_ref: dict[str, Any]) -> dict[str, Any]:
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
        metrics = self._tasks._compact_graph_run_metrics(  # noqa: SLF001
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
        clean_run["budget"] = self._tasks._compact_graph_run_budget(  # noqa: SLF001
            run=pseudo_run,
            graph_metrics=metrics,
        )
        return clean_run

    @staticmethod
    def _merge_graph_run_export_ref(current: Any, export_ref: dict[str, Any]) -> list[dict[str, Any]]:
        refs = [dict(item) for item in list(current or []) if isinstance(item, dict)]
        filtered = [
            item
            for item in refs
            if str(item.get("artifact_id") or "").strip() != str(export_ref.get("artifact_id") or "").strip()
            and str(item.get("path") or "").strip() != str(export_ref.get("path") or "").strip()
        ]
        filtered.append(export_ref)
        return filtered[:24]

    def merge_task_graph_run_refs(
        self,
        persisted: Any,
        incoming: Any,
        *,
        limit: int,
    ) -> list[dict[str, Any]]:
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
                by_id[run_id] = self.merge_task_graph_run_ref(existing, candidate)
        merged = sorted(
            by_id.values(),
            key=self.graph_run_ref_sort_key,
            reverse=True,
        )
        return merged[: max(0, int(limit or 0))]

    def merge_task_graph_run_ref(
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
        left_sort_key = self.graph_run_ref_sort_key(left)
        right_sort_key = self.graph_run_ref_sort_key(right)
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
        preferred_timeline = self._tasks._compact_graph_run_timeline_events(preferred.get("timeline_events"))  # noqa: SLF001
        fallback_timeline = self._tasks._compact_graph_run_timeline_events(fallback.get("timeline_events"))  # noqa: SLF001
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

    @staticmethod
    def graph_run_ref_sort_key(item: dict[str, Any]) -> tuple[float, float, str]:
        updated = str(item.get("updated_at") or "").strip()
        created = str(item.get("created_at") or "").strip()
        updated_ts = dt.datetime.fromisoformat(updated).timestamp() if updated else float("-inf")
        created_ts = dt.datetime.fromisoformat(created).timestamp() if created else float("-inf")
        return (updated_ts, created_ts, str(item.get("run_id") or "").strip())
