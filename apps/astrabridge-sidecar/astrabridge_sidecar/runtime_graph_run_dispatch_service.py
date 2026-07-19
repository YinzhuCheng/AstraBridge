from __future__ import annotations

import hashlib
from copy import deepcopy
from typing import TYPE_CHECKING, Any

from .common import new_id, now_iso
from .durable_run_store import StateVersionConflict
from .graph_dispatch_control import GraphDispatchRequest
from .security import redact_sensitive

if TYPE_CHECKING:
    from .runtime_service import RuntimeService


GRAPH_DISPATCH_MAX_ACTIVE_NODES = 8
GRAPH_DISPATCH_RESERVED_INTERACTIVE_SLOTS = 1
GRAPH_DISPATCH_MAX_PROVIDER_ACTIVE_NODES = 4
GRAPH_DISPATCH_MAX_MODEL_ACTIVE_NODES = 2
GRAPH_DISPATCH_MAX_WORKSPACE_ACTIVE_NODES = 8
GRAPH_DISPATCH_BREAKER_FAILURE_THRESHOLD = 2
GRAPH_DISPATCH_BREAKER_COOLDOWN_SECONDS = 30.0
GRAPH_DISPATCH_RETRY_BUDGET_MAX = 4


class RuntimeGraphRunDispatchService:
    """Own live graph-run queue admission, status projection, and cancellation coordination."""

    def __init__(self, runtime_service: "RuntimeService") -> None:
        self._runtime = runtime_service

    @property
    def _tasks(self) -> Any:
        return self._runtime._tasks  # noqa: SLF001

    def resolve_dispatch_limits(
        self,
        *,
        payload: dict[str, Any],
        compiled_plan: dict[str, Any],
    ) -> dict[str, Any]:
        overrides = dict(payload.get("_dispatch_limits") or {}) if isinstance(payload.get("_dispatch_limits"), dict) else {}
        max_parallelism = max(1, int(dict(compiled_plan.get("topology") or {}).get("max_parallelism") or 1))

        def _override_or_default(key: str, default: Any) -> Any:
            return overrides[key] if key in overrides else default

        return {
            "max_active_nodes": max(
                1,
                int(_override_or_default("max_active_nodes", min(max(2, max_parallelism), GRAPH_DISPATCH_MAX_ACTIVE_NODES))),
            ),
            "reserved_interactive_slots": max(
                0,
                int(_override_or_default("reserved_interactive_slots", GRAPH_DISPATCH_RESERVED_INTERACTIVE_SLOTS)),
            ),
            "max_provider_active_nodes": max(
                1,
                int(_override_or_default("max_provider_active_nodes", GRAPH_DISPATCH_MAX_PROVIDER_ACTIVE_NODES)),
            ),
            "max_model_active_nodes": max(
                1,
                int(_override_or_default("max_model_active_nodes", GRAPH_DISPATCH_MAX_MODEL_ACTIVE_NODES)),
            ),
            "max_workspace_active_nodes": max(
                1,
                int(_override_or_default("max_workspace_active_nodes", max(2, max_parallelism, GRAPH_DISPATCH_MAX_WORKSPACE_ACTIVE_NODES))),
            ),
            "breaker_failure_threshold": max(
                1,
                int(_override_or_default("breaker_failure_threshold", GRAPH_DISPATCH_BREAKER_FAILURE_THRESHOLD)),
            ),
            "breaker_cooldown_seconds": max(
                1.0,
                float(_override_or_default("breaker_cooldown_seconds", GRAPH_DISPATCH_BREAKER_COOLDOWN_SECONDS)),
            ),
            "retry_budget_max": max(
                0,
                int(_override_or_default("retry_budget_max", min(max_parallelism, GRAPH_DISPATCH_RETRY_BUDGET_MAX))),
            ),
        }

    @staticmethod
    def normalize_parallel_groups(
        compiled_plan: dict[str, Any],
        *,
        dispatch_limits: dict[str, Any],
    ) -> tuple[list[dict[str, Any]], int]:
        parallel_groups = [
            dict(group)
            for group in list(compiled_plan.get("parallel_groups") or [])
            if isinstance(group, dict)
        ]
        raw_batch_limit = min(
            max(1, int(dispatch_limits.get("max_active_nodes") or 1) - max(0, int(dispatch_limits.get("reserved_interactive_slots") or 0))),
            max(1, int(dispatch_limits.get("max_provider_active_nodes") or 1)),
            max(1, int(dispatch_limits.get("max_model_active_nodes") or 1)),
            max(1, int(dispatch_limits.get("max_workspace_active_nodes") or 1)),
        )
        batch_limit = max(1, raw_batch_limit)
        normalized_groups: list[dict[str, Any]] = []
        for group_index, group in enumerate(parallel_groups):
            group_id = str(group.get("group_id") or "").strip() or f"group_{group_index}"
            node_ids = [
                str(item).strip()
                for item in list(group.get("node_ids") or [])
                if str(item or "").strip()
            ]
            if len(node_ids) <= batch_limit:
                normalized_groups.append({**group, "group_id": group_id, "node_ids": node_ids})
                continue
            for batch_index in range(0, len(node_ids), batch_limit):
                normalized_groups.append(
                    {
                        **group,
                        "group_id": f"{group_id}__batch_{(batch_index // batch_limit) + 1}",
                        "node_ids": node_ids[batch_index : batch_index + batch_limit],
                    }
                )
        normalized_parallelism = max(
            1,
            min(
                batch_limit,
                int(dict(compiled_plan.get("topology") or {}).get("max_parallelism") or batch_limit),
            ),
        )
        return normalized_groups, normalized_parallelism

    def dispatch_workspace_id(self) -> str:
        current_project = getattr(self._runtime._projects, "current_project", None)  # noqa: SLF001
        if isinstance(current_project, dict):
            project_id = str(current_project.get("project_id") or "").strip()
            if project_id:
                return project_id
        return "workspace-default"

    def build_dispatch_request(
        self,
        *,
        run_id: str,
        node_id: str,
        provider_id: str,
        model_id: str,
    ) -> GraphDispatchRequest:
        return GraphDispatchRequest(
            run_id=str(run_id or "").strip(),
            node_id=str(node_id or "").strip(),
            workspace_id=self.dispatch_workspace_id(),
            provider_id=str(provider_id or "").strip() or "unknown-provider",
            model_id=str(model_id or "").strip() or "unknown-model",
        )

    def queue_task_graph_run(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Persist a run receipt and dispatch it independently of HTTP lifetime."""

        self._runtime._reconcile_durable_graph_scheduler_runs()  # noqa: SLF001
        submission = self._runtime._validate_graph_live_run_submission(payload)  # noqa: SLF001
        graph = dict(submission["graph"])
        compiled_plan = dict(submission["compiled_plan"])
        compiled_nodes = dict(submission["compiled_nodes"])
        model_capability_snapshots = deepcopy(dict(submission.get("model_capability_snapshots") or {}))
        run_budget = dict(submission["run_budget"])
        idempotency_key = str(payload.get("idempotency_key") or "").strip() or None
        run_id = (
            f"graph-run-live-{hashlib.sha256(idempotency_key.encode('utf-8')).hexdigest()[:24]}"
            if idempotency_key
            else new_id("graph-run-live")
        )
        created_at = now_iso()
        dispatch_control = self.resolve_dispatch_limits(payload=payload, compiled_plan=compiled_plan)
        parallel_groups, max_parallelism = self.normalize_parallel_groups(
            compiled_plan,
            dispatch_limits=dispatch_control,
        )
        node_states: dict[str, dict[str, Any]] = {}
        event_refs: list[dict[str, Any]] = [
            {
                "event_id": f"{run_id}-created",
                "run_id": run_id,
                "task_id": graph["task_id"],
                "trace_id": f"trace-{run_id}",
                "event_type": "run_created",
                "created_at": created_at,
                "summary": f"{graph['title']} live task-graph run admitted to the durable scheduler.",
            }
        ]
        for node_id, compiled_node in compiled_nodes.items():
            dependency_node_ids = [
                str(item).strip()
                for item in list(compiled_node.get("dependency_node_ids") or [])
                if str(item or "").strip()
            ]
            node_states[node_id] = {
                "node_id": node_id,
                "run_id": run_id,
                "status": "waiting_on_dependencies" if dependency_node_ids else "queued",
                "outcome": "pending",
                "attempt_count": 0,
                "started_at": created_at,
                "updated_at": created_at,
                "worker_origin": None,
            }
            event_refs.append(
                {
                    "event_id": f"{run_id}-{node_id}-queued",
                    "run_id": run_id,
                    "task_id": graph["task_id"],
                    "trace_id": f"trace-{run_id}",
                    "event_type": "node_queued",
                    "created_at": created_at,
                    "summary": f"{self._tasks._graph_node_label(graph, node_id)} queued for scheduler dispatch.",  # noqa: SLF001
                    "node_id": node_id,
                }
            )
        budget_snapshot = self._tasks._graph_run_budget_snapshot(  # noqa: SLF001
            graph=graph,
            compiled_plan=compiled_plan,
            run_budget=run_budget,
        )
        node_mcp_tool_policies = self._runtime._graph_node_mcp_tool_policy_snapshots(  # noqa: SLF001
            graph=graph,
            compiled_plan=compiled_plan,
        )
        queued_manifest = {
            "schema_version": "astrabridge-task-graph-run-v1",
            "run_id": run_id,
            "graph_id": graph["graph_id"],
            "task_id": graph["task_id"],
            "trace_id": f"trace-{run_id}",
            "context_id": f"context-{run_id}",
            "status": "queued",
            "entry_node_ids": list(compiled_plan.get("entry_node_ids") or []),
            "node_run_states": [deepcopy(item) for item in node_states.values()],
            "artifact_refs": [],
            "event_refs": deepcopy(event_refs),
            "approval_state": {"status": "not_required"},
            "run_policy_snapshot": {
                "mode": "live_run",
                "scheduler": "durable_graph_scheduler_v1",
                "scheduler_owner_id": self._runtime._graph_scheduler.owner_id,  # noqa: SLF001
                "template_id": graph.get("template_id"),
                "parallel_group_count": int(
                    dict(compiled_plan.get("topology") or {}).get("parallel_group_count")
                    or len(parallel_groups)
                ),
                "max_parallelism": max_parallelism,
                "parallel_group_ids": [
                    str(group.get("group_id") or "").strip()
                    for group in parallel_groups
                    if str(group.get("group_id") or "").strip()
                ],
                "model_capability_snapshots": model_capability_snapshots,
                "dispatch_control": dispatch_control,
                "budget": budget_snapshot,
                "node_mcp_tool_policies": node_mcp_tool_policies,
                "resume_payload": self._runtime._graph_live_resume_payload(  # noqa: SLF001
                    {
                        "graph_id": graph["graph_id"],
                        "budget": run_budget,
                        "parent_thread_id": submission["parent_thread_id"],
                        "_scheduler_lease_ttl_seconds": payload.get("_scheduler_lease_ttl_seconds"),
                        "_crash_before_provider_dispatch": payload.get("_crash_before_provider_dispatch"),
                        "_crash_after_provider_handle": payload.get("_crash_after_provider_handle"),
                    }
                ),
            },
            "created_at": created_at,
            "updated_at": created_at,
            "state_version": 1,
        }
        live_run_ref = self._tasks.record_graph_run(queued_manifest, graph_definition=graph)
        if idempotency_key:
            durable_receipt = self._tasks.durable_run_store().load_run(run_id, include_events=True)
            if isinstance(durable_receipt, dict):
                live_run_ref = dict(
                    self._tasks.persist_graph_run_ref(
                        self._tasks._compact_graph_run_ref(durable_receipt)  # noqa: SLF001
                    ).get("run_ref")
                    or live_run_ref
                )
        worker_payload = dict(payload)
        worker_payload["_scheduler_run_id"] = run_id
        try:
            self._runtime._graph_scheduler.submit(  # noqa: SLF001
                run_id,
                worker_payload,
                max_parallelism=max_parallelism,
            )
        except Exception as exc:  # noqa: BLE001
            self._runtime._mark_graph_scheduler_failure(run_id, exc)  # noqa: SLF001
            raise
        return {
            "schema_version": "astrabridge-task-graph-run-receipt-v1",
            "queued": True,
            "live_run": {
                "run_id": run_id,
                "run_status": str(live_run_ref.get("status") or "queued"),
                "run_ref": live_run_ref,
                "status_url": f"/api/task-graphs/run/status?run_id={run_id}",
                "events_url": f"/api/task-graphs/run/status?run_id={run_id}",
                "event_cursor": len(event_refs),
            },
            "scheduler": self._runtime._graph_scheduler.status(),  # noqa: SLF001
            "graph": graph,
            "task": self._tasks.task_view(self._tasks.current_task(), compact_graph_runs=True),
        }

    def graph_scheduler_status(self) -> dict[str, Any]:
        self._runtime._reconcile_durable_graph_scheduler_runs()  # noqa: SLF001
        return self._runtime._graph_scheduler.status()  # noqa: SLF001

    def graph_run_status(self, run_id: str) -> dict[str, Any]:
        self._runtime._reconcile_durable_graph_scheduler_runs()  # noqa: SLF001
        clean_run_id = str(run_id or "").strip()
        if not clean_run_id:
            raise ValueError("run_id is required.")
        if self._tasks is None:
            raise ValueError("Task service is required for graph run status.")
        durable_run = self._tasks.durable_run_store().load_run(clean_run_id, include_events=True)
        if durable_run is None:
            raise ValueError("Task graph run not found.")
        run_ref = self._tasks.graph_run_ref(clean_run_id)
        if isinstance(run_ref, dict):
            live_status = str(run_ref.get("status") or "").strip()
            live_node_states = [dict(item) for item in list(run_ref.get("node_run_states") or []) if isinstance(item, dict)]
            live_events = [dict(item) for item in list(run_ref.get("event_refs") or []) if isinstance(item, dict)]
            if live_status:
                durable_run["status"] = live_status
            if live_node_states:
                durable_run["node_run_states"] = live_node_states
            if live_events:
                durable_run["event_refs"] = live_events
        graph_id = str(durable_run.get("graph_id") or "").strip()
        graph = self._tasks.graph_definition(graph_id) if graph_id else None
        scheduler_job = self._runtime._graph_scheduler.get(clean_run_id)  # noqa: SLF001
        return {
            "schema_version": "astrabridge-task-graph-run-status-v1",
            "run": redact_sensitive(durable_run),
            "live_run": {
                "run_id": clean_run_id,
                "run_status": str(durable_run.get("status") or ""),
                "run_ref": run_ref,
                "event_cursor": len(list(durable_run.get("event_refs") or [])),
            },
            "events": [
                redact_sensitive(dict(item))
                for item in list(durable_run.get("event_refs") or [])
                if isinstance(item, dict)
            ],
            "scheduler_job": scheduler_job,
            "scheduler": self._runtime._graph_scheduler.status(),  # noqa: SLF001
            "graph": graph,
            "task": self._tasks.task_view(self._tasks.current_task(), compact_graph_runs=True),
        }

    def cancel_task_graph_run(self, payload: dict[str, Any]) -> dict[str, Any]:
        if self._tasks is None:
            raise ValueError("Task service is required for task-graph cancellation.")
        if not isinstance(payload, dict):
            raise TypeError("Task-graph cancel payload must be a dict.")
        run_id = str(payload.get("run_id") or "").strip()
        if not run_id:
            raise ValueError("run_id is required.")
        store = self._tasks.durable_run_store()
        durable_run = store.load_run(run_id, include_events=True)
        if durable_run is None:
            raise ValueError("Task graph run not found.")
        run_policy = dict(durable_run.get("run_policy_snapshot") or {})
        if str(run_policy.get("mode") or "").strip() != "live_run":
            return self._tasks.cancel_graph_run(payload)

        def _terminal_cancellation_response(status: str) -> dict[str, Any]:
            current_status_payload = self.graph_run_status(run_id)
            return {
                "cancellation": {
                    "run_id": run_id,
                    "status": status,
                    "requested_at": None,
                    "interrupt_results": [],
                },
                "run_ref": current_status_payload["live_run"]["run_ref"],
                "graph": current_status_payload["graph"],
                "task": current_status_payload["task"],
            }

        run_ref = self._tasks.graph_run_ref(run_id)
        current_status = str((run_ref or {}).get("status") or durable_run.get("status") or "").strip()
        if current_status in {"completed", "failed", "cancelled", "needs_review"}:
            return _terminal_cancellation_response(current_status)

        notes = str(redact_sensitive(payload.get("notes") or "")).strip()[:600]
        requested_at = now_iso()
        grace_timeout_ms = max(250, int(payload.get("grace_timeout_ms") or 5000))
        cancellation = {
            "status": "requested",
            "requested_at": requested_at,
            "notes": notes or None,
            "grace_timeout_ms": grace_timeout_ms,
        }
        updated = durable_run
        last_conflict: StateVersionConflict | None = None
        for _ in range(4):
            try:
                updated = store.compare_and_swap_run(
                    run_id,
                    int(durable_run.get("state_version") or 0),
                    status=current_status,
                    patch={
                        "cancellation": cancellation,
                        "updated_at": requested_at,
                    },
                    event={
                        "event_id": f"{run_id}-cancel-requested",
                        "run_id": run_id,
                        "task_id": str(durable_run.get("task_id") or ""),
                        "trace_id": str(durable_run.get("trace_id") or f"trace-{run_id}"),
                        "event_type": "run_cancel_requested",
                        "created_at": requested_at,
                        "summary": "Live task-graph run cancellation was requested.",
                    },
                )
                last_conflict = None
                break
            except StateVersionConflict as exc:
                last_conflict = exc
                durable_run = store.load_run(run_id, include_events=True)
                if durable_run is None:
                    raise ValueError("Task graph run disappeared during cancellation.") from exc
                run_ref = self._tasks.graph_run_ref(run_id)
                current_status = str((run_ref or {}).get("status") or durable_run.get("status") or "").strip()
                if current_status in {"completed", "failed", "cancelled", "needs_review"}:
                    return _terminal_cancellation_response(current_status)
        if last_conflict is not None:
            raise last_conflict
        latest_run_ref = self._tasks.graph_run_ref(run_id)
        latest_node_states = {
            str(item.get("node_id") or "").strip(): dict(item)
            for item in list((latest_run_ref or {}).get("node_run_states") or [])
            if isinstance(item, dict) and str(item.get("node_id") or "").strip()
        }
        if not latest_node_states:
            latest_node_states = {
                str(item.get("node_id") or "").strip(): dict(item)
                for item in list(updated.get("node_run_states") or [])
                if isinstance(item, dict) and str(item.get("node_id") or "").strip()
            }
        graph = self._tasks.graph_definition(str(updated.get("graph_id") or "").strip()) or {}
        graph_nodes = {
            str(item.get("node_id") or "").strip(): dict(item)
            for item in list(graph.get("nodes") or [])
            if isinstance(item, dict) and str(item.get("node_id") or "").strip()
        }

        interrupt_results: list[dict[str, Any]] = []
        for node_id, state in latest_node_states.items():
            if str(state.get("status") or "").strip() != "running":
                continue
            execution_thread_id = str(state.get("execution_thread_id") or state.get("worker_thread_id") or "").strip()
            turn_id = str(state.get("turn_id") or "").strip()
            if not execution_thread_id or not turn_id:
                continue
            provider_id = str(state.get("provider_id") or graph_nodes.get(node_id, {}).get("provider_id") or "").strip()
            try:
                profile = self._runtime._profiles.resolve_runtime_profile(provider_id)  # noqa: SLF001
                interrupt_result = self._runtime.interrupt_turn(profile, execution_thread_id, turn_id)
            except Exception as exc:  # noqa: BLE001
                interrupt_results.append(
                    {
                        "node_id": node_id,
                        "thread_id": execution_thread_id,
                        "turn_id": turn_id,
                        "ok": False,
                        "error_type": type(exc).__name__,
                        "error": str(exc)[:300],
                    }
                )
            else:
                interrupt_results.append(
                    {
                        "node_id": node_id,
                        "thread_id": execution_thread_id,
                        "turn_id": turn_id,
                        "ok": True,
                        "interrupt": dict(interrupt_result.get("interrupt") or {}),
                    }
                )

        compact_ref = dict(self._tasks.graph_run_ref(run_id) or {})
        timeline_events = [dict(item) for item in list(compact_ref.get("timeline_events") or []) if isinstance(item, dict)]
        if not any(str(item.get("event_id") or "") == f"{run_id}-cancel-requested" for item in timeline_events):
            timeline_events.append(
                {
                    "event_id": f"{run_id}-cancel-requested",
                    "event_type": "run_cancel_requested",
                    "created_at": requested_at,
                    "summary": "Live task-graph run cancellation was requested.",
                    "status": "cancelled",
                }
            )
        compact_ref["timeline_events"] = timeline_events[-24:]
        compact_ref["latest_event_type"] = "run_cancel_requested"
        compact_ref["latest_event_at"] = requested_at
        compact_ref["updated_at"] = requested_at

        active_running = any(str(item.get("status") or "").strip() == "running" for item in latest_node_states.values())
        if not active_running and current_status == "queued":
            self._runtime._graph_scheduler.cancel(run_id, reason="cancelled_before_dispatch")  # noqa: SLF001
            cancelled_at = now_iso()
            last_cancel_conflict: StateVersionConflict | None = None
            for _ in range(4):
                try:
                    updated = store.compare_and_swap_run(
                        run_id,
                        int(updated.get("state_version") or 0),
                        status="cancelled",
                        patch={
                            "cancellation": {**cancellation, "status": "completed", "resolved_at": cancelled_at},
                            "updated_at": cancelled_at,
                        },
                        event={
                            "event_id": f"{run_id}-cancelled",
                            "run_id": run_id,
                            "task_id": str(updated.get("task_id") or ""),
                            "trace_id": str(updated.get("trace_id") or f"trace-{run_id}"),
                            "event_type": "run_cancelled",
                            "created_at": cancelled_at,
                            "summary": "Live task-graph run was cancelled before provider dispatch.",
                        },
                    )
                    last_cancel_conflict = None
                    break
                except StateVersionConflict as exc:
                    last_cancel_conflict = exc
                    refreshed = store.load_run(run_id, include_events=True)
                    if not isinstance(refreshed, dict):
                        raise ValueError("Task graph run disappeared during queued cancellation.") from exc
                    if str(refreshed.get("status") or "").strip() in {"completed", "failed", "cancelled", "needs_review"}:
                        updated = refreshed
                        last_cancel_conflict = None
                        break
                    updated = refreshed
            if last_cancel_conflict is not None:
                raise last_cancel_conflict
            compact_ref["status"] = "cancelled"
            compact_ref["latest_event_type"] = "run_cancelled"
            compact_ref["latest_event_at"] = cancelled_at
            compact_ref["updated_at"] = cancelled_at
            node_status_counts = dict(compact_ref.get("node_status_counts") or {})
            queued_count = 0
            for key in ("queued", "waiting_on_dependencies", "ready", "waiting_on_artifact", "waiting_on_approval"):
                queued_count += int(node_status_counts.pop(key, 0) or 0)
            if queued_count:
                node_status_counts["cancelled"] = int(node_status_counts.get("cancelled") or 0) + queued_count
            compact_ref["node_status_counts"] = node_status_counts
            compact_ref["timeline_events"] = [
                *compact_ref["timeline_events"],
                {
                    "event_id": f"{run_id}-cancelled",
                    "event_type": "run_cancelled",
                    "created_at": cancelled_at,
                    "summary": "Live task-graph run was cancelled before provider dispatch.",
                    "status": "cancelled",
                },
            ][-24:]

        persisted = self._tasks.persist_graph_run_ref(compact_ref)
        return {
            "cancellation": {
                "run_id": run_id,
                "status": str(dict(persisted.get("run_ref") or {}).get("status") or current_status),
                "requested_at": requested_at,
                "interrupt_results": interrupt_results,
            },
            "run_ref": dict(persisted.get("run_ref") or compact_ref),
            "graph": graph,
            "task": persisted.get("task") or self._tasks.task_view(self._tasks.current_task(), compact_graph_runs=True),
        }
