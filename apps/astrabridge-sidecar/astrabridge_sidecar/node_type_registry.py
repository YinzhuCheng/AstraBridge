from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any, TypedDict

from .common import now_iso, read_json, slugify, write_json


NODE_TYPE_REGISTRY_SCHEMA_VERSION = "astrabridge-node-type-registry-v1"
EXECUTOR_REGISTRY_SCHEMA_VERSION = "astrabridge-executor-registry-v1"
EXECUTOR_ACTIVATION_JOURNAL_SCHEMA_VERSION = "astrabridge-executor-activation-journal-v1"
EXECUTOR_ACTIVATION_ROLLBACK_SCHEMA_VERSION = "astrabridge-executor-activation-rollback-v1"
EXECUTOR_ACTIVATION_TRACK_ID = "node_executor_activation"
OPAQUE_DISABLED_NODE_TYPE_ID = "opaque_disabled"
EXECUTION_MODE_IDS = ("live_run", "fixture_run")
NODE_TYPE_ROLE_IDS = (
    "supervisor",
    "worker",
    "synthesizer",
    "extractor",
    "validator",
    "reviewer",
    "planner",
    "coder",
    "researcher",
    "gate",
    "custom",
)


class NodeTypeSpec(TypedDict, total=False):
    type_id: str
    version: int
    category: str
    title: str
    description: str
    config_schema: dict[str, Any]
    typed_ports: dict[str, list[dict[str, Any]]]
    compiler_executor_id: str
    default_policy: dict[str, Any]
    ui_hints: dict[str, Any]
    migration: dict[str, Any]
    internal_only: bool
    registry_fingerprint: str
    executor_capability: dict[str, Any]


class ExecutorModeSpec(TypedDict, total=False):
    available: bool
    status: str
    reason: str
    supports_checkpointing: bool
    supports_cancellation: bool


class ExecutorSpec(TypedDict, total=False):
    executor_id: str
    version: int
    title: str
    description: str
    supported_modes: dict[str, ExecutorModeSpec]
    effect_classification: str
    capability_dependencies: list[str]
    internal_only: bool
    registry_fingerprint: str


def task_graph_node_kind_ids() -> tuple[str, ...]:
    registry = build_node_type_registry()
    ordered: list[str] = []
    for spec in list(registry["node_types"] or []):
        type_id = str(spec.get("type_id") or "").strip()
        if type_id and type_id not in ordered:
            ordered.append(type_id)
        for alias in list(dict(spec.get("migration") or {}).get("legacy_kind_aliases") or []):
            alias_text = str(alias or "").strip()
            if alias_text and alias_text not in ordered:
                ordered.append(alias_text)
    if OPAQUE_DISABLED_NODE_TYPE_ID not in ordered:
        ordered.append(OPAQUE_DISABLED_NODE_TYPE_ID)
    return tuple(ordered)


def build_node_type_registry(
    *,
    extra_specs: list[dict[str, Any]] | None = None,
    include_internal: bool = True,
) -> dict[str, Any]:
    raw_specs = [deepcopy(spec) for spec in _base_node_type_specs()]
    raw_specs.extend(deepcopy(item) for item in list(extra_specs or []) if isinstance(item, dict))
    node_types: list[NodeTypeSpec] = []
    by_type_id: dict[str, NodeTypeSpec] = {}
    kind_aliases: dict[str, str] = {}
    seen_type_ids: set[str] = set()
    executor_registry = build_executor_registry(include_internal=include_internal)
    executor_by_id = dict(executor_registry.get("_by_executor_id") or {})
    for raw in raw_specs:
        spec = _normalize_spec(raw)
        type_id = str(spec.get("type_id") or "").strip()
        version = int(spec.get("version") or 0)
        if not type_id:
            raise ValueError("NodeTypeSpec.type_id is required.")
        if version <= 0:
            raise ValueError(f"NodeTypeSpec.version must be positive for {type_id}.")
        if type_id in seen_type_ids:
            raise ValueError(f"Duplicate or conflicting node type registration: {type_id}@v{version}")
        seen_type_ids.add(type_id)
        for alias in [type_id, *list(dict(spec.get("migration") or {}).get("legacy_kind_aliases") or [])]:
            alias_text = str(alias or "").strip()
            if not alias_text:
                continue
            existing = kind_aliases.get(alias_text)
            if existing and existing != type_id:
                raise ValueError(f"Conflicting node type alias registration: {alias_text} -> {existing} vs {type_id}")
            kind_aliases[alias_text] = type_id
        executor_id = str(spec.get("compiler_executor_id") or "").strip()
        executor_spec = dict(executor_by_id.get(executor_id) or {})
        if not executor_spec:
            raise ValueError(f"NodeTypeSpec `{type_id}` references unknown compiler_executor_id `{executor_id}`.")
        spec["executor_capability"] = _node_type_executor_capability(
            spec=spec,
            executor_spec=executor_spec,
            executor_registry_fingerprint=str(executor_registry.get("registry_fingerprint") or ""),
        )
        node_types.append(spec)
        by_type_id[type_id] = spec
    execution_view = [
        _execution_fingerprint_view(spec)
        for spec in sorted(node_types, key=lambda item: (str(item.get("type_id") or ""), int(item.get("version") or 0)))
        if include_internal or not bool(spec.get("internal_only"))
    ]
    registry_fingerprint = _fingerprint(execution_view)
    public_node_types = [
        deepcopy(spec)
        for spec in node_types
        if include_internal or not bool(spec.get("internal_only"))
    ]
    return {
        "schema_version": NODE_TYPE_REGISTRY_SCHEMA_VERSION,
        "registry_fingerprint": registry_fingerprint,
        "executor_registry_fingerprint": str(executor_registry.get("registry_fingerprint") or ""),
        "node_types": public_node_types,
        "kind_aliases": {
            alias: target
            for alias, target in sorted(kind_aliases.items())
            if include_internal or not bool(by_type_id.get(target, {}).get("internal_only"))
        },
        "role_ids": list(NODE_TYPE_ROLE_IDS),
        "executor_matrix": _executor_matrix_snapshot(
            node_types=public_node_types,
            executor_registry=executor_registry,
        ),
        "_all_node_types": node_types,
        "_by_type_id": by_type_id,
        "_executor_registry": executor_registry,
    }


def node_type_registry_snapshot(*, extra_specs: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    registry = build_node_type_registry(extra_specs=extra_specs, include_internal=False)
    return {
        "schema_version": NODE_TYPE_REGISTRY_SCHEMA_VERSION,
        "registry_fingerprint": registry["registry_fingerprint"],
        "executor_registry_fingerprint": str(registry.get("executor_registry_fingerprint") or ""),
        "role_ids": list(registry["role_ids"]),
        "kind_aliases": dict(registry["kind_aliases"]),
        "node_types": [deepcopy(spec) for spec in list(registry["node_types"] or [])],
        "executor_matrix": deepcopy(dict(registry.get("executor_matrix") or {})),
    }


def build_executor_registry(*, include_internal: bool = True) -> dict[str, Any]:
    raw_specs = [deepcopy(spec) for spec in _base_executor_specs()]
    executors: list[ExecutorSpec] = []
    by_executor_id: dict[str, ExecutorSpec] = {}
    seen_executor_ids: set[str] = set()
    for raw in raw_specs:
        spec = _normalize_executor_spec(raw)
        executor_id = str(spec.get("executor_id") or "").strip()
        if not executor_id:
            raise ValueError("ExecutorSpec.executor_id is required.")
        if executor_id in seen_executor_ids:
            raise ValueError(f"Duplicate executor registration: {executor_id}")
        seen_executor_ids.add(executor_id)
        executors.append(spec)
        by_executor_id[executor_id] = spec
    public_executors = [
        deepcopy(spec)
        for spec in executors
        if include_internal or not bool(spec.get("internal_only"))
    ]
    registry_fingerprint = _fingerprint(
        [
            _executor_fingerprint_view(spec)
            for spec in sorted(public_executors, key=lambda item: (str(item.get("executor_id") or ""), int(item.get("version") or 0)))
        ]
    )
    for spec in executors:
        spec["registry_fingerprint"] = registry_fingerprint
    return {
        "schema_version": EXECUTOR_REGISTRY_SCHEMA_VERSION,
        "registry_fingerprint": registry_fingerprint,
        "execution_modes": list(EXECUTION_MODE_IDS),
        "executors": public_executors,
        "_all_executors": executors,
        "_by_executor_id": by_executor_id,
    }


def compiled_plan_executor_capability_report(
    compiled_plan: dict[str, Any],
    *,
    execution_mode: str,
    extra_specs: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    normalized_mode = str(execution_mode or "").strip().lower() or "fixture_run"
    if normalized_mode not in EXECUTION_MODE_IDS:
        raise ValueError(f"Unsupported execution_mode `{execution_mode}`.")
    registry = build_node_type_registry(extra_specs=extra_specs, include_internal=True)
    current_registry_fingerprint = str(registry.get("registry_fingerprint") or "")
    compiled_registry_fingerprint = str(dict(compiled_plan or {}).get("node_type_registry_fingerprint") or "").strip()
    by_type_id = dict(registry.get("_by_type_id") or {})
    blockers: list[str] = []
    if compiled_registry_fingerprint and compiled_registry_fingerprint != current_registry_fingerprint:
        blockers.append(
            "Registry fingerprint drift detected before execution: "
            f"compiled plan expects {compiled_registry_fingerprint}, current registry is {current_registry_fingerprint}."
        )
    entries: list[dict[str, Any]] = []
    by_node_id: dict[str, dict[str, Any]] = {}
    for compiled_node in list(dict(compiled_plan or {}).get("nodes") or []):
        if not isinstance(compiled_node, dict):
            continue
        node_id = str(compiled_node.get("node_id") or "").strip()
        resolved_type_id = str(compiled_node.get("resolved_node_type_id") or "").strip()
        compiler_executor_id = str(compiled_node.get("compiler_executor_id") or "").strip()
        node_registry_fingerprint = str(compiled_node.get("node_type_registry_fingerprint") or "").strip()
        current_spec = dict(by_type_id.get(resolved_type_id) or {})
        capability = dict(current_spec.get("executor_capability") or {})
        mode_spec = dict(dict(capability.get("supported_modes") or {}).get(normalized_mode) or {})
        expected_executor_id = str(current_spec.get("compiler_executor_id") or resolved_type_id or "").strip()
        node_blockers: list[str] = []
        if not current_spec:
            node_blockers.append(
                f"Node `{node_id}` resolved to unknown node type `{resolved_type_id}` in the current registry."
            )
        if node_registry_fingerprint and node_registry_fingerprint != current_registry_fingerprint:
            node_blockers.append(
                f"Node `{node_id}` carries stale registry fingerprint {node_registry_fingerprint}; current registry is {current_registry_fingerprint}."
            )
        if current_spec and compiler_executor_id != expected_executor_id:
            node_blockers.append(
                f"Node `{node_id}` compiled executor `{compiler_executor_id}` no longer matches current node-type executor `{expected_executor_id}`."
            )
        if current_spec and not capability:
            node_blockers.append(
                f"Node `{node_id}` resolved executor metadata is missing for `{compiler_executor_id or expected_executor_id}`."
            )
        if current_spec and capability and not bool(mode_spec.get("available")):
            reason = str(mode_spec.get("reason") or "").strip() or "executor mode unavailable"
            node_blockers.append(
                f"Node `{node_id}` cannot run in `{normalized_mode}` because executor `{str(capability.get('executor_id') or compiler_executor_id or expected_executor_id)}` is unavailable: {reason}"
            )
        entry = {
            "node_id": node_id,
            "resolved_node_type_id": resolved_type_id,
            "compiler_executor_id": compiler_executor_id,
            "expected_executor_id": expected_executor_id or compiler_executor_id,
            "execution_mode": normalized_mode,
            "mode_available": bool(mode_spec.get("available")) and not node_blockers,
            "mode_status": str(mode_spec.get("status") or "").strip() or "unknown",
            "mode_reason": str(mode_spec.get("reason") or "").strip() or None,
            "blocking_reasons": node_blockers,
        }
        entries.append(entry)
        if node_id:
            by_node_id[node_id] = entry
        blockers.extend(node_blockers)
    return {
        "schema_version": "astrabridge-compiled-plan-executor-report-v1",
        "execution_mode": normalized_mode,
        "ok": not blockers,
        "current_registry_fingerprint": current_registry_fingerprint,
        "compiled_plan_registry_fingerprint": compiled_registry_fingerprint or None,
        "blocker_count": len(blockers),
        "blockers": blockers,
        "entries": entries,
        "by_node_id": by_node_id,
        "executor_matrix": _executor_matrix_snapshot(
            node_types=[
                deepcopy(spec)
                for spec in list(registry.get("node_types") or [])
                if not bool(spec.get("internal_only"))
            ],
            executor_registry=dict(registry.get("_executor_registry") or {}),
        ),
    }


def journaled_compiled_plan_executor_capability_report(
    compiled_plan: dict[str, Any],
    *,
    execution_mode: str,
    workspace_root: str | Path,
    activation_scope: str,
    extra_specs: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    workspace = Path(workspace_root).expanduser().resolve()
    state_root = workspace / ".astrabridge" / "executor-activation"
    state_root.mkdir(parents=True, exist_ok=True)
    activation_id = _executor_activation_artifact_id(
        activation_scope=activation_scope,
        execution_mode=execution_mode,
        compiled_plan=compiled_plan,
    )
    artifact_root = state_root / activation_id
    artifact_root.mkdir(parents=True, exist_ok=True)
    journal_path = artifact_root / "apply-journal.json"
    report_path = artifact_root / "executor-report.json"
    rollback_path = artifact_root / "rollback-manifest.json"
    current_path = state_root / "current.json"
    previous_pointer = read_json(current_path, None) if current_path.exists() else None
    baseline_state = _executor_activation_baseline(previous_pointer)

    journal = _initialize_executor_activation_journal(
        activation_id=activation_id,
        activation_scope=activation_scope,
        execution_mode=execution_mode,
        baseline_state=baseline_state,
    )
    _write_executor_activation_json(journal_path, journal)
    _append_executor_activation_stage(journal, journal_path, stage="baseline_captured")

    report = compiled_plan_executor_capability_report(
        compiled_plan,
        execution_mode=execution_mode,
        extra_specs=extra_specs,
    )
    report["activation"] = {
        "activation_id": activation_id,
        "activation_scope": activation_scope,
        "artifact_root": str(artifact_root),
        "report_path": str(report_path),
        "journal_path": str(journal_path),
        "rollback_manifest_path": str(rollback_path),
        "current_pointer_path": str(current_path),
    }
    write_json(report_path, report)
    _append_executor_activation_stage(
        journal,
        journal_path,
        stage="report_written",
        staged_digest=_executor_activation_digest(report),
        blocker_count=int(report.get("blocker_count") or 0),
    )

    if bool(report.get("ok")):
        pointer_payload = {
            "schema_version": "astrabridge-executor-activation-current-v1",
            "updated_at": now_iso(),
            "activation_id": activation_id,
            "activation_scope": activation_scope,
            "execution_mode": execution_mode,
            "report_path": str(report_path),
            "journal_path": str(journal_path),
            "registry_fingerprint": str(report.get("current_registry_fingerprint") or ""),
            "compiled_plan_registry_fingerprint": report.get("compiled_plan_registry_fingerprint"),
        }
        write_json(current_path, pointer_payload)
        rollback_manifest = _write_executor_activation_rollback_manifest(
            rollback_path=rollback_path,
            activation_id=activation_id,
            activation_scope=activation_scope,
            execution_mode=execution_mode,
            baseline_state=baseline_state,
            report=report,
            restore_status="available_for_manual_restore",
            current_pointer_path=current_path,
        )
        _finalize_executor_activation_journal(
            journal,
            journal_path,
            terminal_status="committed",
            staged_state=report,
            health_verdict="pass",
            changed_paths=[str(report_path), str(journal_path), str(rollback_path), str(current_path)],
            rollback_target={
                "rollback_manifest_path": str(rollback_path),
                "restore_status": str(rollback_manifest.get("restore_status") or ""),
                "previous_pointer": deepcopy(previous_pointer),
            },
        )
    else:
        rollback_manifest = _write_executor_activation_rollback_manifest(
            rollback_path=rollback_path,
            activation_id=activation_id,
            activation_scope=activation_scope,
            execution_mode=execution_mode,
            baseline_state=baseline_state,
            report=report,
            restore_status="restored_after_failure",
            current_pointer_path=current_path,
        )
        _finalize_executor_activation_journal(
            journal,
            journal_path,
            terminal_status="rolled_back",
            staged_state=report,
            health_verdict="fail",
            changed_paths=[str(report_path), str(journal_path), str(rollback_path)],
            rollback_target={
                "rollback_manifest_path": str(rollback_path),
                "restore_status": str(rollback_manifest.get("restore_status") or ""),
                "previous_pointer": deepcopy(previous_pointer),
            },
        )
    return read_json(report_path, report)


def _executor_activation_artifact_id(
    *,
    activation_scope: str,
    execution_mode: str,
    compiled_plan: dict[str, Any],
) -> str:
    scope_hint = slugify(str(activation_scope or ""), default="activation")
    mode_hint = slugify(str(execution_mode or ""), default="mode")
    digest = hashlib.sha256(
        json.dumps(
            {
                "activation_scope": str(activation_scope or ""),
                "execution_mode": str(execution_mode or ""),
                "compiled_plan": compiled_plan or {},
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()[:16]
    readable_prefix = slugify(
        f"{scope_hint[:20]}-{mode_hint[:8]}",
        default="executor-activation",
    )
    return slugify(f"{readable_prefix}-{digest}", default="executor-activation")


def _executor_activation_baseline(previous_pointer: dict[str, Any] | None) -> dict[str, Any]:
    payload = dict(previous_pointer or {})
    return {
        "has_previous_pointer": bool(payload),
        "activation_id": str(payload.get("activation_id") or ""),
        "activation_scope": str(payload.get("activation_scope") or ""),
        "execution_mode": str(payload.get("execution_mode") or ""),
        "report_path": str(payload.get("report_path") or ""),
        "journal_path": str(payload.get("journal_path") or ""),
        "registry_fingerprint": str(payload.get("registry_fingerprint") or ""),
        "compiled_plan_registry_fingerprint": str(payload.get("compiled_plan_registry_fingerprint") or ""),
    }


def _initialize_executor_activation_journal(
    *,
    activation_id: str,
    activation_scope: str,
    execution_mode: str,
    baseline_state: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": EXECUTOR_ACTIVATION_JOURNAL_SCHEMA_VERSION,
        "apply_id": activation_id,
        "run_id": activation_id,
        "status": "running",
        "mode": "node_executor_activation",
        "started_at": now_iso(),
        "completed_at": None,
        "risk_class": "node_executor_activation",
        "approval": {
            "approved": True,
            "approved_by": "node_type_registry_activation_gate",
            "approved_at": now_iso(),
            "approval_note": activation_scope,
        },
        "tracks": [
            {
                "track_id": EXECUTOR_ACTIVATION_TRACK_ID,
                "status": "running",
                "source_digest": _executor_activation_digest(baseline_state),
                "staged_digest": None,
                "trust_decision": f"registry_activation_gate:{execution_mode}",
                "health_verdict": "not_run",
                "changed_paths": [],
                "change_ids": [activation_scope],
                "rollback_target": {"previous_pointer": deepcopy(baseline_state)},
                "history": [
                    {
                        "stage": "initialized",
                        "at": now_iso(),
                        "activation_scope": activation_scope,
                        "execution_mode": execution_mode,
                    }
                ],
            }
        ],
    }


def _write_executor_activation_json(path: Path, payload: dict[str, Any]) -> None:
    write_json(path, payload)


def _append_executor_activation_stage(
    journal: dict[str, Any],
    journal_path: Path,
    *,
    stage: str,
    **details: Any,
) -> None:
    track = _executor_activation_track(journal)
    history = list(track.get("history") or [])
    entry = {"stage": stage, "at": now_iso()}
    for key, value in details.items():
        if value is not None:
            entry[key] = value
    history.append(entry)
    track["history"] = history
    _write_executor_activation_json(journal_path, journal)


def _finalize_executor_activation_journal(
    journal: dict[str, Any],
    journal_path: Path,
    *,
    terminal_status: str,
    staged_state: dict[str, Any],
    health_verdict: str,
    changed_paths: list[str],
    rollback_target: dict[str, Any],
) -> None:
    journal["status"] = terminal_status
    journal["completed_at"] = now_iso()
    track = _executor_activation_track(journal)
    track["status"] = terminal_status
    track["staged_digest"] = _executor_activation_digest(staged_state)
    track["health_verdict"] = health_verdict
    track["changed_paths"] = list(changed_paths)
    track["rollback_target"] = dict(rollback_target)
    history = list(track.get("history") or [])
    history.append({"stage": "healthcheck_completed", "at": now_iso(), "verdict": health_verdict})
    history.append({"stage": terminal_status, "at": now_iso()})
    track["history"] = history
    _write_executor_activation_json(journal_path, journal)


def _executor_activation_track(journal: dict[str, Any]) -> dict[str, Any]:
    for track in list(journal.get("tracks") or []):
        if str(track.get("track_id") or "") == EXECUTOR_ACTIVATION_TRACK_ID:
            return track
    raise ValueError("Missing executor activation journal track.")


def _write_executor_activation_rollback_manifest(
    *,
    rollback_path: Path,
    activation_id: str,
    activation_scope: str,
    execution_mode: str,
    baseline_state: dict[str, Any],
    report: dict[str, Any],
    restore_status: str,
    current_pointer_path: Path,
) -> dict[str, Any]:
    manifest = {
        "schema_version": EXECUTOR_ACTIVATION_ROLLBACK_SCHEMA_VERSION,
        "generated_at": now_iso(),
        "activation_id": activation_id,
        "activation_scope": activation_scope,
        "execution_mode": execution_mode,
        "restore_status": restore_status,
        "current_pointer_path": str(current_pointer_path),
        "baseline_state": deepcopy(baseline_state),
        "report_path": str(dict(report.get("activation") or {}).get("report_path") or ""),
        "registry_fingerprint": str(report.get("current_registry_fingerprint") or ""),
        "compiled_plan_registry_fingerprint": report.get("compiled_plan_registry_fingerprint"),
        "blocker_count": int(report.get("blocker_count") or 0),
        "steps": [
            {
                "step_id": "preserve_previous_pointer",
                "status": "ready",
                "current_pointer_path": str(current_pointer_path),
                "has_previous_pointer": bool(baseline_state.get("has_previous_pointer")),
            }
        ],
    }
    write_json(rollback_path, manifest)
    return manifest


def _executor_activation_digest(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def default_role_for_kind(kind: str) -> str:
    resolved = resolve_node_type(kind, allow_unknown=True)
    spec = dict(resolved.get("spec") or {})
    migration = dict(spec.get("migration") or {})
    alias_defaults = dict(migration.get("default_role_by_kind") or {})
    return str(alias_defaults.get(str(kind or "").strip()) or migration.get("default_role") or "custom")


def compatible_roles_for_kind(kind: str) -> set[str]:
    resolved = resolve_node_type(kind, allow_unknown=True)
    spec = dict(resolved.get("spec") or {})
    migration = dict(spec.get("migration") or {})
    roles = {
        str(item).strip()
        for item in list(migration.get("compatible_roles") or [])
        if str(item or "").strip()
    }
    return roles or {"custom"}


def resolve_node_type(kind: str, *, allow_unknown: bool = False) -> dict[str, Any]:
    registry = build_node_type_registry(include_internal=True)
    by_type_id = dict(registry.get("_by_type_id") or {})
    kind_text = str(kind or "").strip()
    resolved_type_id = str(dict(registry.get("kind_aliases") or {}).get(kind_text) or kind_text).strip()
    spec = deepcopy(by_type_id.get(resolved_type_id) or {})
    if spec:
        migration = dict(spec.get("migration") or {})
        alias_defaults = dict(migration.get("default_role_by_kind") or {})
        return {
            "known": True,
            "source_kind": kind_text,
            "resolved_type_id": resolved_type_id,
            "spec": spec,
            "default_role": str(alias_defaults.get(kind_text) or migration.get("default_role") or "custom"),
            "registry_fingerprint": str(registry.get("registry_fingerprint") or ""),
            "diagnostics": [],
        }
    if not allow_unknown:
        raise ValueError(f"Unknown node type: {kind_text}")
    opaque = deepcopy(by_type_id[OPAQUE_DISABLED_NODE_TYPE_ID])
    return {
        "known": False,
        "source_kind": kind_text,
        "resolved_type_id": OPAQUE_DISABLED_NODE_TYPE_ID,
        "spec": opaque,
        "default_role": "custom",
        "registry_fingerprint": str(registry.get("registry_fingerprint") or ""),
        "diagnostics": [
            {
                "code": "unknown_node_type",
                "severity": "warning",
                "source_kind": kind_text,
                "resolved_type_id": OPAQUE_DISABLED_NODE_TYPE_ID,
                "message": f"Unknown node type `{kind_text}` was preserved as an opaque disabled node.",
            }
        ],
    }


def project_task_graph_kind(*, authored_kind: str, allow_unknown: bool = False) -> str:
    authored = str(authored_kind or "").strip()
    known = set(task_graph_node_kind_ids())
    if authored in known:
        return authored
    resolved = resolve_node_type(authored, allow_unknown=allow_unknown)
    spec = dict(resolved.get("spec") or {})
    migration = dict(spec.get("migration") or {})
    candidate = str(migration.get("task_graph_projection_kind") or resolved.get("resolved_type_id") or "").strip()
    if candidate in known:
        return candidate
    return OPAQUE_DISABLED_NODE_TYPE_ID


def _normalize_spec(value: dict[str, Any]) -> NodeTypeSpec:
    spec = deepcopy(value)
    spec["type_id"] = str(spec.get("type_id") or "").strip()
    spec["version"] = int(spec.get("version") or 1)
    spec["category"] = str(spec.get("category") or "").strip() or "custom"
    spec["title"] = str(spec.get("title") or "").strip() or spec["type_id"]
    spec["description"] = str(spec.get("description") or "").strip()
    spec["config_schema"] = deepcopy(dict(spec.get("config_schema") or {}))
    typed_ports = dict(spec.get("typed_ports") or {})
    spec["typed_ports"] = {
        "inputs": [deepcopy(item) for item in list(typed_ports.get("inputs") or []) if isinstance(item, dict)],
        "outputs": [deepcopy(item) for item in list(typed_ports.get("outputs") or []) if isinstance(item, dict)],
    }
    spec["compiler_executor_id"] = str(spec.get("compiler_executor_id") or "").strip() or spec["type_id"]
    spec["default_policy"] = deepcopy(dict(spec.get("default_policy") or {}))
    spec["ui_hints"] = deepcopy(dict(spec.get("ui_hints") or {}))
    spec["migration"] = deepcopy(dict(spec.get("migration") or {}))
    spec["internal_only"] = bool(spec.get("internal_only"))
    spec["registry_fingerprint"] = _fingerprint(_execution_fingerprint_view(spec))
    return spec


def _execution_fingerprint_view(spec: NodeTypeSpec) -> dict[str, Any]:
    return {
        "type_id": spec.get("type_id"),
        "version": spec.get("version"),
        "category": spec.get("category"),
        "config_schema": spec.get("config_schema"),
        "typed_ports": spec.get("typed_ports"),
        "compiler_executor_id": spec.get("compiler_executor_id"),
        "executor_capability": spec.get("executor_capability"),
        "default_policy": spec.get("default_policy"),
        "migration": spec.get("migration"),
        "internal_only": bool(spec.get("internal_only")),
    }


def _normalize_executor_spec(value: dict[str, Any]) -> ExecutorSpec:
    spec = deepcopy(value)
    spec["executor_id"] = str(spec.get("executor_id") or "").strip()
    spec["version"] = int(spec.get("version") or 1)
    spec["title"] = str(spec.get("title") or spec["executor_id"]).strip() or spec["executor_id"]
    spec["description"] = str(spec.get("description") or "").strip()
    supported_modes = dict(spec.get("supported_modes") or {})
    normalized_modes: dict[str, ExecutorModeSpec] = {}
    for mode_id in EXECUTION_MODE_IDS:
        raw_mode = dict(supported_modes.get(mode_id) or {})
        normalized_modes[mode_id] = {
            "available": bool(raw_mode.get("available")),
            "status": str(raw_mode.get("status") or ("available" if raw_mode.get("available") else "disabled")).strip()
            or ("available" if raw_mode.get("available") else "disabled"),
            "reason": str(raw_mode.get("reason") or "").strip(),
            "supports_checkpointing": bool(raw_mode.get("supports_checkpointing")),
            "supports_cancellation": bool(raw_mode.get("supports_cancellation")),
        }
    spec["supported_modes"] = normalized_modes
    spec["effect_classification"] = str(spec.get("effect_classification") or "").strip() or "deterministic"
    spec["capability_dependencies"] = [
        str(item).strip()
        for item in list(spec.get("capability_dependencies") or [])
        if str(item or "").strip()
    ]
    spec["internal_only"] = bool(spec.get("internal_only"))
    spec["registry_fingerprint"] = ""
    return spec


def _executor_fingerprint_view(spec: ExecutorSpec) -> dict[str, Any]:
    return {
        "executor_id": spec.get("executor_id"),
        "version": spec.get("version"),
        "supported_modes": spec.get("supported_modes"),
        "effect_classification": spec.get("effect_classification"),
        "capability_dependencies": spec.get("capability_dependencies"),
        "internal_only": bool(spec.get("internal_only")),
    }


def _node_type_executor_capability(
    *,
    spec: NodeTypeSpec,
    executor_spec: dict[str, Any],
    executor_registry_fingerprint: str,
) -> dict[str, Any]:
    supported_modes = deepcopy(dict(executor_spec.get("supported_modes") or {}))
    available_modes = [
        mode_id
        for mode_id in EXECUTION_MODE_IDS
        if bool(dict(supported_modes.get(mode_id) or {}).get("available"))
    ]
    if set(available_modes) == set(EXECUTION_MODE_IDS):
        availability_summary = "live_and_fixture"
    elif available_modes == ["fixture_run"] or set(available_modes) == {"fixture_run"}:
        availability_summary = "fixture_only"
    elif available_modes == ["live_run"] or set(available_modes) == {"live_run"}:
        availability_summary = "live_only"
    else:
        availability_summary = "disabled"
    return {
        "executor_id": str(executor_spec.get("executor_id") or spec.get("compiler_executor_id") or "").strip(),
        "executor_version": int(executor_spec.get("version") or 1),
        "executor_registry_fingerprint": executor_registry_fingerprint,
        "availability_summary": availability_summary,
        "supported_modes": supported_modes,
        "effect_classification": str(executor_spec.get("effect_classification") or "").strip() or "deterministic",
        "capability_dependencies": deepcopy(list(executor_spec.get("capability_dependencies") or [])),
    }


def _executor_matrix_snapshot(*, node_types: list[dict[str, Any]], executor_registry: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": EXECUTOR_REGISTRY_SCHEMA_VERSION,
        "registry_fingerprint": str(executor_registry.get("registry_fingerprint") or ""),
        "execution_modes": list(EXECUTION_MODE_IDS),
        "executors": [
            deepcopy(item)
            for item in list(executor_registry.get("executors") or [])
            if isinstance(item, dict)
        ],
        "node_types": [
            {
                "type_id": str(spec.get("type_id") or "").strip(),
                "compiler_executor_id": str(spec.get("compiler_executor_id") or "").strip(),
                "executor_capability": deepcopy(dict(spec.get("executor_capability") or {})),
            }
            for spec in node_types
            if isinstance(spec, dict)
        ],
    }


def _fingerprint(payload: Any) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:16]


def _base_executor_specs() -> tuple[ExecutorSpec, ...]:
    return (
        {
            "executor_id": "agent_lane",
            "version": 1,
            "title": "Agent Lane",
            "description": "Provider-backed live lane with durable turn dispatch and fixture parity.",
            "supported_modes": {
                "live_run": {
                    "available": True,
                    "status": "available",
                    "reason": "Live provider-lane dispatch is implemented.",
                    "supports_checkpointing": True,
                    "supports_cancellation": True,
                },
                "fixture_run": {
                    "available": True,
                    "status": "available",
                    "reason": "Fixture runner can simulate bounded agent results.",
                    "supports_checkpointing": True,
                    "supports_cancellation": True,
                },
            },
            "effect_classification": "provider_lane",
            "capability_dependencies": ["provider_profile", "model_capability_snapshot", "node_tool_policy"],
        },
        {
            "executor_id": "mcp_tool",
            "version": 1,
            "title": "MCP Tool",
            "description": "Runs a declared MCP tool call through the broker boundary.",
            "supported_modes": {
                "live_run": {
                    "available": True,
                    "status": "available",
                    "reason": "Dedicated live MCP tool executor is available through the shared runtime lifecycle.",
                    "supports_checkpointing": True,
                    "supports_cancellation": True,
                },
                "fixture_run": {
                    "available": True,
                    "status": "available",
                    "reason": "Fixture runner can validate topology and preserve bounded artifacts.",
                    "supports_checkpointing": True,
                },
            },
            "effect_classification": "mcp_dispatch",
            "capability_dependencies": ["mcp_broker", "node_mcp_tool_policy"],
        },
        {
            "executor_id": "mcp_resource",
            "version": 1,
            "title": "MCP Resource",
            "description": "Reads a declared MCP resource through the broker boundary.",
            "supported_modes": {
                "live_run": {
                    "available": True,
                    "status": "available",
                    "reason": "Dedicated live MCP resource executor is available through the shared runtime lifecycle.",
                    "supports_checkpointing": True,
                },
                "fixture_run": {
                    "available": True,
                    "status": "available",
                    "reason": "Fixture runner can model declared resource inputs.",
                    "supports_checkpointing": True,
                },
            },
            "effect_classification": "mcp_dispatch",
            "capability_dependencies": ["mcp_broker", "resource_resolution"],
        },
        {
            "executor_id": "transform",
            "version": 1,
            "title": "Transform",
            "description": "Applies a deterministic transform between typed graph ports.",
            "supported_modes": {
                "live_run": {
                    "available": True,
                    "status": "available",
                    "reason": "Dedicated live transform executor is available through the shared runtime lifecycle.",
                    "supports_checkpointing": True,
                },
                "fixture_run": {
                    "available": True,
                    "status": "available",
                    "reason": "Fixture runner can exercise typed-port planning paths.",
                    "supports_checkpointing": True,
                },
            },
            "effect_classification": "deterministic_transform",
            "capability_dependencies": ["typed_port_projection"],
        },
        {
            "executor_id": "router_condition",
            "version": 1,
            "title": "Router / Condition",
            "description": "Deterministically selects downstream edges from validated conditions.",
            "supported_modes": {
                "live_run": {
                    "available": True,
                    "status": "available",
                    "reason": "Dedicated live router executor is available through the shared runtime lifecycle.",
                    "supports_checkpointing": True,
                },
                "fixture_run": {
                    "available": True,
                    "status": "available",
                    "reason": "Fixture runner can preserve branch-shape diagnostics.",
                    "supports_checkpointing": True,
                },
            },
            "effect_classification": "deterministic_control",
            "capability_dependencies": ["typed_port_projection"],
        },
        {
            "executor_id": "loop",
            "version": 1,
            "title": "Loop",
            "description": "Runs a bounded loop with explicit iteration and recovery semantics.",
            "supported_modes": {
                "live_run": {
                    "available": True,
                    "status": "available",
                    "reason": "Dedicated durable loop executor lands in Step 14.2.",
                    "supports_checkpointing": True,
                },
                "fixture_run": {
                    "available": True,
                    "status": "available",
                    "reason": "Fixture runner can preserve bounded loop planning diagnostics.",
                    "supports_checkpointing": True,
                },
            },
            "effect_classification": "stateful_control",
            "capability_dependencies": ["retry_policy", "checkpointing"],
        },
        {
            "executor_id": "subgraph",
            "version": 1,
            "title": "Subgraph",
            "description": "Invokes a nested graph with isolated trace and typed I/O.",
            "supported_modes": {
                "live_run": {
                    "available": True,
                    "status": "available",
                    "reason": "Dedicated live subgraph executor lands in Step 14.2.",
                    "supports_checkpointing": True,
                },
                "fixture_run": {
                    "available": True,
                    "status": "available",
                    "reason": "Fixture runner can preserve subgraph topology and replay diagnostics.",
                    "supports_checkpointing": True,
                },
            },
            "effect_classification": "stateful_control",
            "capability_dependencies": ["compiled_plan", "checkpointing"],
        },
        {
            "executor_id": "human_approval",
            "version": 1,
            "title": "Human Approval",
            "description": "Pauses execution for bounded human review and durable approval state.",
            "supported_modes": {
                "live_run": {
                    "available": True,
                    "status": "available",
                    "reason": "Dedicated durable approval pause lands in Step 14.1.",
                    "supports_checkpointing": True,
                },
                "fixture_run": {
                    "available": True,
                    "status": "available",
                    "reason": "Fixture runner can preserve approval pauses and review diagnostics.",
                    "supports_checkpointing": True,
                },
            },
            "effect_classification": "approval_gate",
            "capability_dependencies": ["approval_state", "checkpointing"],
        },
        {
            "executor_id": "artifact_source",
            "version": 1,
            "title": "Artifact Source",
            "description": "Introduces an external or preserved artifact into the graph.",
            "supported_modes": {
                "live_run": {
                    "available": True,
                    "status": "available",
                    "reason": "Dedicated live artifact source executor is available through the shared runtime lifecycle.",
                    "supports_checkpointing": True,
                },
                "fixture_run": {
                    "available": True,
                    "status": "available",
                    "reason": "Fixture runner can preserve artifact-source manifests.",
                    "supports_checkpointing": True,
                },
            },
            "effect_classification": "artifact_io",
            "capability_dependencies": ["artifact_store", "typed_port_projection"],
        },
        {
            "executor_id": "artifact_sink",
            "version": 1,
            "title": "Artifact Sink",
            "description": "Persists or promotes a terminal artifact output.",
            "supported_modes": {
                "live_run": {
                    "available": True,
                    "status": "available",
                    "reason": "Dedicated live artifact sink executor is available through the shared runtime lifecycle.",
                    "supports_checkpointing": True,
                },
                "fixture_run": {
                    "available": True,
                    "status": "available",
                    "reason": "Fixture runner can preserve artifact sink projections.",
                    "supports_checkpointing": True,
                },
            },
            "effect_classification": "artifact_io",
            "capability_dependencies": ["artifact_store", "typed_port_projection"],
        },
        {
            "executor_id": OPAQUE_DISABLED_NODE_TYPE_ID,
            "version": 1,
            "title": "Opaque Disabled",
            "description": "Disabled fallback for imported or unknown node kinds.",
            "supported_modes": {
                "live_run": {
                    "available": False,
                    "status": "disabled",
                    "reason": "Unknown or disabled node types must fail closed.",
                },
                "fixture_run": {
                    "available": False,
                    "status": "disabled",
                    "reason": "Unknown or disabled node types must fail closed.",
                },
            },
            "effect_classification": "disabled",
            "capability_dependencies": [],
            "internal_only": True,
        },
    )


def _base_node_type_specs() -> tuple[NodeTypeSpec, ...]:
    agent_roles = list(NODE_TYPE_ROLE_IDS)
    return (
        {
            "type_id": "agent_model",
            "version": 1,
            "category": "agent",
            "title": "Agent / Model",
            "description": "Bounded provider-backed agent lane with explicit routing, prompt, and typed input/output ports.",
            "config_schema": {
                "type": "object",
                "properties": {
                    "routing": {"type": "object", "title": "Routing"},
                    "prompt": {"type": "object", "title": "Prompt"},
                    "execution": {"type": "object", "title": "Execution"},
                    "safety": {"type": "object", "title": "Safety"},
                },
            },
            "typed_ports": {
                "inputs": [{"port_id": "task_context", "port_type": "text", "shape": "single", "required": True}],
                "outputs": [{"port_id": "machine_result", "port_type": "structured_json", "shape": "single", "required": True}],
            },
            "compiler_executor_id": "agent_lane",
            "default_policy": {
                "execution_backend": "app_server",
                "spawn_mode": "isolated_lane",
                "approval_mode": "ask",
            },
            "ui_hints": {
                "palette_role": "custom",
                "palette_sections": ["planning", "execution"],
                "icon": "bot",
                "tone": "neutral",
                "palette_variants": [
                    {
                        "kind": "supervisor",
                        "label": "Supervisor",
                        "description": "Plans the bounded workflow and coordinates downstream workers.",
                        "palette_sections": ["planning"],
                        "icon": "compass",
                        "tone": "planner",
                    },
                    {
                        "kind": "planner",
                        "label": "Planner",
                        "description": "Breaks work into explicit steps and hands them to other agents.",
                        "palette_sections": ["planning"],
                        "icon": "file-text",
                        "tone": "planner",
                    },
                    {
                        "kind": "researcher",
                        "label": "Researcher",
                        "description": "Collects evidence, docs, or comparisons before synthesis.",
                        "palette_sections": ["planning"],
                        "icon": "search",
                        "tone": "extractor",
                    },
                    {
                        "kind": "extractor",
                        "label": "Extractor",
                        "description": "Pulls structured facts from files, docs, or provider metadata.",
                        "palette_sections": ["planning"],
                        "icon": "database",
                        "tone": "extractor",
                    },
                    {
                        "kind": "worker",
                        "label": "Worker",
                        "description": "Executes the main task and returns the primary artifact.",
                        "palette_sections": ["execution"],
                        "icon": "wrench",
                        "tone": "worker",
                    },
                    {
                        "kind": "coder",
                        "label": "Coder",
                        "description": "Applies code or document changes in a bounded implementation lane.",
                        "palette_sections": ["execution"],
                        "icon": "braces",
                        "tone": "worker",
                    },
                    {
                        "kind": "synthesizer",
                        "label": "Synthesizer",
                        "description": "Merges branch outputs into one bounded answer or artifact set.",
                        "palette_sections": ["execution"],
                        "icon": "sparkles",
                        "tone": "synthesizer",
                    },
                    {
                        "kind": "reviewer",
                        "label": "Reviewer",
                        "description": "Reads outputs critically and returns review feedback or approval.",
                        "palette_sections": ["execution"],
                        "icon": "eye",
                        "tone": "reviewer",
                    },
                    {
                        "kind": "validator",
                        "label": "Validator",
                        "description": "Runs checks, tests, or smoke validation before promotion.",
                        "palette_sections": ["execution"],
                        "icon": "shield-check",
                        "tone": "validator",
                    },
                    {
                        "kind": "custom",
                        "label": "Custom",
                        "description": "Starts as a neutral agent shell with the default fallback icon.",
                        "palette_sections": ["control"],
                        "icon": "bot",
                        "tone": "neutral",
                    },
                ],
            },
            "migration": {
                "legacy_kind_aliases": [
                    "supervisor",
                    "worker",
                    "synthesizer",
                    "extractor",
                    "validator",
                    "reviewer",
                    "planner",
                    "coder",
                    "researcher",
                    "custom",
                ],
                "compatible_roles": agent_roles,
                "default_role": "custom",
                "default_role_by_kind": {
                    "supervisor": "supervisor",
                    "worker": "worker",
                    "synthesizer": "synthesizer",
                    "extractor": "extractor",
                    "validator": "validator",
                    "reviewer": "reviewer",
                    "planner": "planner",
                    "coder": "coder",
                    "researcher": "researcher",
                    "custom": "custom",
                },
                "task_graph_projection_kind": "agent_model",
            },
        },
        {
            "type_id": "mcp_tool",
            "version": 1,
            "category": "mcp",
            "title": "MCP Tool",
            "description": "Executes one declared MCP tool/resource operation through the broker boundary.",
            "config_schema": {
                "type": "object",
                "properties": {
                    "tool": {"type": "string", "title": "Tool"},
                    "server": {"type": "string", "title": "Server"},
                },
            },
            "typed_ports": {
                "inputs": [{"port_id": "task_context", "port_type": "text", "shape": "single", "required": True}],
                "outputs": [{"port_id": "tool_result", "port_type": "tool_result", "shape": "single", "required": True}],
            },
            "compiler_executor_id": "mcp_tool",
            "default_policy": {"execution_backend": "app_server", "spawn_mode": "inline_lane", "approval_mode": "ask"},
            "ui_hints": {"palette_role": "custom", "palette_sections": ["control"], "icon": "wrench", "tone": "neutral"},
            "migration": {"legacy_kind_aliases": [], "compatible_roles": ["custom"], "default_role": "custom", "task_graph_projection_kind": "mcp_tool"},
        },
        {
            "type_id": "mcp_resource",
            "version": 1,
            "category": "mcp",
            "title": "MCP Resource",
            "description": "Reads declared MCP resources and projects them into a typed port.",
            "config_schema": {
                "type": "object",
                "properties": {
                    "resource": {"type": "string", "title": "Resource"},
                    "server": {"type": "string", "title": "Server"},
                },
            },
            "typed_ports": {
                "inputs": [{"port_id": "task_context", "port_type": "text", "shape": "single", "required": True}],
                "outputs": [{"port_id": "resource_payload", "port_type": "structured_json", "shape": "single", "required": True}],
            },
            "compiler_executor_id": "mcp_resource",
            "default_policy": {"execution_backend": "app_server", "spawn_mode": "inline_lane", "approval_mode": "ask"},
            "ui_hints": {"palette_role": "custom", "palette_sections": ["control"], "icon": "database", "tone": "neutral"},
            "migration": {"legacy_kind_aliases": [], "compatible_roles": ["custom"], "default_role": "custom", "task_graph_projection_kind": "mcp_resource"},
        },
        {
            "type_id": "transform",
            "version": 1,
            "category": "transform",
            "title": "Transform",
            "description": "Applies deterministic shaping or schema transformation between typed ports.",
            "config_schema": {
                "type": "object",
                "properties": {
                    "transform_id": {"type": "string", "title": "Transform id"},
                },
            },
            "typed_ports": {
                "inputs": [{"port_id": "input_payload", "port_type": "structured_json", "shape": "single", "required": True}],
                "outputs": [{"port_id": "machine_result", "port_type": "structured_json", "shape": "single", "required": True}],
            },
            "compiler_executor_id": "transform",
            "default_policy": {"execution_backend": "local_only", "spawn_mode": "inline_lane", "approval_mode": "deny"},
            "ui_hints": {"palette_role": "custom", "palette_sections": ["execution"], "icon": "repeat", "tone": "neutral"},
            "migration": {"legacy_kind_aliases": [], "compatible_roles": ["custom"], "default_role": "custom", "task_graph_projection_kind": "transform"},
        },
        {
            "type_id": "router_condition",
            "version": 1,
            "category": "control",
            "title": "Router / Condition",
            "description": "Routes control flow based on deterministic conditions or structured guards.",
            "config_schema": {"type": "object", "properties": {"condition": {"type": "object"}}},
            "typed_ports": {
                "inputs": [{"port_id": "input_payload", "port_type": "structured_json", "shape": "single", "required": True}],
                "outputs": [{"port_id": "route_decision", "port_type": "structured_json", "shape": "single", "required": True}],
            },
            "compiler_executor_id": "router_condition",
            "default_policy": {"execution_backend": "local_only", "spawn_mode": "inline_lane", "approval_mode": "deny"},
            "ui_hints": {"palette_role": "custom", "palette_sections": ["control"], "icon": "git-branch", "tone": "neutral"},
            "migration": {"legacy_kind_aliases": [], "compatible_roles": ["custom"], "default_role": "custom", "task_graph_projection_kind": "router_condition"},
        },
        {
            "type_id": "loop",
            "version": 1,
            "category": "control",
            "title": "Loop",
            "description": "Repeats a bounded subpath with explicit retry/iteration controls.",
            "config_schema": {"type": "object", "properties": {"max_iterations": {"type": "integer", "minimum": 1}}},
            "typed_ports": {
                "inputs": [{"port_id": "loop_input", "port_type": "structured_json", "shape": "single", "required": True}],
                "outputs": [{"port_id": "loop_result", "port_type": "structured_json", "shape": "single", "required": True}],
            },
            "compiler_executor_id": "loop",
            "default_policy": {"execution_backend": "local_only", "spawn_mode": "inline_lane", "approval_mode": "deny"},
            "ui_hints": {"palette_role": "custom", "palette_sections": ["control"], "icon": "repeat", "tone": "neutral"},
            "migration": {"legacy_kind_aliases": [], "compatible_roles": ["custom"], "default_role": "custom", "task_graph_projection_kind": "loop"},
        },
        {
            "type_id": "subgraph",
            "version": 1,
            "category": "graph",
            "title": "Subgraph",
            "description": "Invokes a nested bounded graph with explicit inputs and outputs.",
            "config_schema": {"type": "object", "properties": {"graph_ref": {"type": "string"}}},
            "typed_ports": {
                "inputs": [{"port_id": "subgraph_input", "port_type": "structured_json", "shape": "single", "required": True}],
                "outputs": [{"port_id": "subgraph_result", "port_type": "structured_json", "shape": "single", "required": True}],
            },
            "compiler_executor_id": "subgraph",
            "default_policy": {"execution_backend": "app_server", "spawn_mode": "subagent_worker", "approval_mode": "ask"},
            "ui_hints": {"palette_role": "custom", "palette_sections": ["control"], "icon": "boxes", "tone": "neutral"},
            "migration": {"legacy_kind_aliases": [], "compatible_roles": ["custom"], "default_role": "custom", "task_graph_projection_kind": "subgraph"},
        },
        {
            "type_id": "human_approval",
            "version": 1,
            "category": "approval",
            "title": "Human Approval",
            "description": "Pauses execution behind an explicit review and approval decision.",
            "config_schema": {
                "type": "object",
                "properties": {
                    "review_kind": {"type": "string", "title": "Review kind"},
                },
            },
            "typed_ports": {
                "inputs": [{"port_id": "approval_input", "port_type": "structured_json", "shape": "single", "required": True}],
                "outputs": [{"port_id": "approval_record", "port_type": "approval_record", "shape": "single", "required": True}],
            },
            "compiler_executor_id": "human_approval",
            "default_policy": {"execution_backend": "human_review", "spawn_mode": "manual_only", "approval_mode": "manual"},
            "ui_hints": {"palette_role": "gate", "palette_sections": ["control"], "icon": "lock", "tone": "gate"},
            "migration": {
                "legacy_kind_aliases": ["gate"],
                "compatible_roles": ["gate"],
                "default_role": "gate",
                "default_role_by_kind": {"gate": "gate"},
                "task_graph_projection_kind": "human_approval",
            },
        },
        {
            "type_id": "artifact_source",
            "version": 1,
            "category": "artifact",
            "title": "Artifact Source",
            "description": "Introduces an external or preserved artifact into the graph as a typed source node.",
            "config_schema": {
                "type": "object",
                "properties": {
                    "artifact_kind": {"type": "string", "title": "Artifact kind"},
                    "artifact_uri": {"type": "string", "title": "Artifact URI"},
                },
            },
            "typed_ports": {
                "inputs": [{"port_id": "task_context", "port_type": "text", "shape": "single", "required": False}],
                "outputs": [{"port_id": "artifact_output", "port_type": "structured_json", "shape": "single", "required": True}],
            },
            "compiler_executor_id": "artifact_source",
            "default_policy": {"execution_backend": "local_only", "spawn_mode": "inline_lane", "approval_mode": "deny"},
            "ui_hints": {"palette_role": "custom", "palette_sections": ["control"], "icon": "file-text", "tone": "neutral"},
            "migration": {
                "legacy_kind_aliases": ["artifact_source"],
                "compatible_roles": ["custom"],
                "default_role": "custom",
                "default_role_by_kind": {"artifact_source": "custom"},
                "task_graph_projection_kind": "artifact_source",
            },
        },
        {
            "type_id": "artifact_sink",
            "version": 1,
            "category": "artifact",
            "title": "Artifact Sink",
            "description": "Persists or promotes a typed artifact or structured payload as a terminal sink.",
            "config_schema": {
                "type": "object",
                "properties": {
                    "target_kind": {"type": "string", "title": "Target kind"},
                },
            },
            "typed_ports": {
                "inputs": [{"port_id": "artifact_input", "port_type": "structured_json", "shape": "single", "required": True}],
                "outputs": [{"port_id": "artifact_record", "port_type": "structured_json", "shape": "single", "required": True}],
            },
            "compiler_executor_id": "artifact_sink",
            "default_policy": {"execution_backend": "local_only", "spawn_mode": "inline_lane", "approval_mode": "deny"},
            "ui_hints": {"palette_role": "custom", "palette_sections": ["control"], "icon": "square-stack", "tone": "neutral"},
            "migration": {"legacy_kind_aliases": [], "compatible_roles": ["custom"], "default_role": "custom", "task_graph_projection_kind": "artifact_sink"},
        },
        {
            "type_id": OPAQUE_DISABLED_NODE_TYPE_ID,
            "version": 1,
            "category": "opaque",
            "title": "Opaque Disabled Node",
            "description": "Fallback placeholder used to preserve unknown imported node types without executing them.",
            "config_schema": {"type": "object", "properties": {"original_node_type_kind": {"type": "string"}}},
            "typed_ports": {
                "inputs": [{"port_id": "opaque_input", "port_type": "structured_json", "shape": "single", "required": False}],
                "outputs": [{"port_id": "opaque_output", "port_type": "structured_json", "shape": "single", "required": False}],
            },
            "compiler_executor_id": OPAQUE_DISABLED_NODE_TYPE_ID,
            "default_policy": {"execution_backend": "local_only", "spawn_mode": "manual_only", "approval_mode": "manual"},
            "ui_hints": {"palette_role": "custom", "palette_sections": ["control"], "icon": "bot", "tone": "neutral"},
            "migration": {"legacy_kind_aliases": [], "compatible_roles": ["custom"], "default_role": "custom", "task_graph_projection_kind": OPAQUE_DISABLED_NODE_TYPE_ID},
            "internal_only": True,
        },
    )
