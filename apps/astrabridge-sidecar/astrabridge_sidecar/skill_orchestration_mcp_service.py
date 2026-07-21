"""Canonical MCP control plane for skill-backed orchestration.

The service owns only the MCP request/response, resolution, idempotency, and
redacted evidence boundary.  Graph compilation, fixture execution, live queue
admission, cancellation, recovery, and durable run state remain owned by the
existing orchestration/runtime services.
"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, RefResolver

from .agent_orchestration_checks import diff_agent_orchestration_graphs
from .agent_orchestration_compiler import compile_agent_orchestration_graph
from .agent_orchestration_contract import (
    lower_agent_orchestration_graph_to_task_graph,
    validate_agent_orchestration_graph,
)
from .communication_isolation import validate_typed_communication_isolation
from .common import new_id, now_iso, read_json, write_json
from .mcp_server_core import McpServerCore, McpToolCallContext
from .release_identity import release_product_version
from .runtime_guardrails import evaluate_runtime_guardrails
from .security import SECRET_RE, redact_sensitive
from .skill_orchestration_validation import load_skill_orchestration_manifest, resolve_skill_to_graph
from .skill_provider_a2a_binding import bind_skill_provider_a2a


SKILL_ORCHESTRATION_MCP_SCHEMA_VERSION = "astrabridge-skill-backed-orchestration-mcp-v1"
SKILL_ORCHESTRATION_MCP_SERVER_NAME = "astrabridge-orchestration"
SKILL_ORCHESTRATION_MCP_VERSION = "astrabridge-skill-orchestration-mcp-v1"
_ZERO_DIGEST = "sha256:" + ("0" * 64)
_TOOL_OPERATION_MAP = {
    "astrabridge_orchestration_propose": "propose",
    "astrabridge_orchestration_patch": "patch",
    "astrabridge_orchestration_validate": "validate",
    "astrabridge_orchestration_dry_run": "dry_run",
    "astrabridge_orchestration_diff": "diff",
    "astrabridge_orchestration_launch": "launch",
    "astrabridge_orchestration_inspect": "inspect",
    "astrabridge_orchestration_cancel": "cancel",
    "astrabridge_orchestration_recover": "recover",
}
_ALLOWED_OPERATIONS = frozenset(_TOOL_OPERATION_MAP.values())
_FORBIDDEN_KEYS = frozenset(
    {
        "api_key",
        "access_token",
        "authorization",
        "bearer",
        "cookie",
        "private_reasoning",
        "raw_prompt",
        "raw_secret",
        "secret",
    }
)


class SkillOrchestrationMcpProtocolError(ValueError):
    """A bounded request error that can be returned as an MCP response."""

    def __init__(self, code: str, message: str, *, details: list[dict[str, Any]] | None = None) -> None:
        super().__init__(message)
        self.code = str(code or "protocol_error")
        self.message = str(message or "Protocol request rejected.")
        self.details = [dict(item) for item in list(details or []) if isinstance(item, dict)][:8]


class SkillOrchestrationMcpService:
    """Expose one canonical MCP surface over the existing graph/runtime owners."""

    def __init__(
        self,
        *,
        project_service: Any,
        task_service: Any | None = None,
        runtime_service: Any | None = None,
        profile_service: Any | None = None,
        router_config: Any | None = None,
    ) -> None:
        self.project_service = project_service
        self.task_service = task_service
        self.runtime_service = runtime_service
        self.profile_service = profile_service
        self.router_config = router_config
        self._schema: dict[str, Any] | None = None
        self._core: McpServerCore | None = None

    def server_core(self) -> McpServerCore:
        if self._core is None:
            self._core = McpServerCore(
                server_name=SKILL_ORCHESTRATION_MCP_SERVER_NAME,
                server_version=release_product_version(),
                instructions=(
                    "AstraBridge's canonical skill-backed orchestration control plane. "
                    "Use propose/validate/dry_run before launch. Every launch is bounded, "
                    "idempotent, and delegated to the existing graph runtime; this server "
                    "does not expose provider SDKs or a second scheduler."
                ),
                tools_provider=self.tools,
                tool_handler=self._tool_handler,
            )
        return self._core

    def tools(self) -> list[dict[str, Any]]:
        """Return the normative v1 tool inventory."""

        return [
            self._tool_descriptor("astrabridge_orchestration_propose", "propose", "Resolve a skill to one immutable canonical graph candidate.", ["direction", "schema_version", "operation", "request_id", "skill_ref", "parameters"]),
            self._tool_descriptor("astrabridge_orchestration_patch", "patch", "Create a validated immutable candidate from a resolution reference.", ["direction", "schema_version", "operation", "request_id", "resolution_ref", "patches"]),
            self._tool_descriptor("astrabridge_orchestration_validate", "validate", "Run manifest, graph, compiler, policy, MCP, A2A, and secret checks.", ["direction", "schema_version", "operation", "request_id", "subject"]),
            self._tool_descriptor("astrabridge_orchestration_dry_run", "dry_run", "Compile and guardrail-check a resolved graph without live provider dispatch.", ["direction", "schema_version", "operation", "request_id", "resolution_ref", "budget"]),
            self._tool_descriptor("astrabridge_orchestration_diff", "diff", "Compare two immutable resolutions by topology, route, policy, and artifacts.", ["direction", "schema_version", "operation", "request_id", "base_ref", "target_ref"]),
            self._tool_descriptor("astrabridge_orchestration_launch", "launch", "Queue one bounded fixture or live graph run after a matching dry-run receipt.", ["direction", "schema_version", "operation", "request_id", "resolution_ref", "budget", "approval", "idempotency_key", "dry_run_receipt", "mode"]),
            self._tool_descriptor("astrabridge_orchestration_inspect", "inspect", "Read a redacted durable run projection and bounded event page.", ["direction", "schema_version", "operation", "request_id", "run_id", "projection"]),
            self._tool_descriptor("astrabridge_orchestration_cancel", "cancel", "Request monotonic cancellation through the existing graph owner.", ["direction", "schema_version", "operation", "request_id", "run_id", "reason", "idempotency_key"]),
            self._tool_descriptor("astrabridge_orchestration_recover", "recover", "Create a bounded fixture recovery run with explicit strategy and receipt.", ["direction", "schema_version", "operation", "request_id", "run_id", "strategy", "budget", "approval", "idempotency_key", "dry_run_receipt", "mode"]),
        ]

    @staticmethod
    def _tool_descriptor(name: str, operation: str, description: str, required: list[str]) -> dict[str, Any]:
        properties: dict[str, Any] = {
            "direction": {"const": "request", "type": "string"},
            "schema_version": {"const": SKILL_ORCHESTRATION_MCP_SCHEMA_VERSION, "type": "string"},
            "operation": {"const": operation, "type": "string"},
            "request_id": {"type": "string", "minLength": 1, "maxLength": 128},
        }
        if operation in {"propose", "validate", "patch", "dry_run", "diff", "launch", "recover"}:
            properties["skill_ref"] = {"type": "object"}
            properties["resolution_ref"] = {"type": "object"}
            properties["parameters"] = {"type": "object"}
            properties["patches"] = {"type": "array"}
            properties["budget"] = {"type": "object"}
            properties["approval"] = {"type": "object"}
            properties["dry_run_receipt"] = {"type": "object"}
            properties["subject"] = {"type": "object"}
            properties["base_ref"] = {"type": "object"}
            properties["target_ref"] = {"type": "object"}
            properties["mode"] = {"enum": ["fixture", "live"], "type": "string"}
        if operation in {"inspect", "cancel", "recover"}:
            properties["run_id"] = {"type": "string"}
        if operation == "inspect":
            properties["projection"] = {"enum": ["compact", "summary", "events"], "type": "string"}
        if operation == "cancel":
            properties["reason"] = {"type": "string", "minLength": 1, "maxLength": 600}
        if operation == "recover":
            properties["strategy"] = {"type": "string"}
            properties["selected_node_ids"] = {"type": "array"}
        properties["idempotency_key"] = {"type": "string", "minLength": 8, "maxLength": 256}
        return {
            "name": name,
            "description": description,
            "inputSchema": {
                "type": "object",
                "properties": properties,
                "required": required,
                "additionalProperties": True,
            },
        }

    def _tool_handler(self, name: str, arguments: dict[str, Any], context: McpToolCallContext) -> dict[str, Any]:
        operation = _TOOL_OPERATION_MAP.get(str(name or "").strip())
        if operation is None:
            raise ValueError(f"Unknown AstraBridge orchestration MCP tool: {name}")
        request = deepcopy(arguments)
        broker_operation_id = str(dict(context.meta or {}).get("operationId") or "").strip()
        if broker_operation_id and not str(request.get("operation_id") or "").strip():
            request["operation_id"] = broker_operation_id
        response = self.handle_request(
            request,
            expected_operation=operation,
            transport_context={"session_id": context.session_id, "request_id": context.request_id},
        )
        return {
            "structuredContent": response,
            "content": [{"type": "text", "text": self._text_projection(response)}],
        }

    def handle_request(
        self,
        request: dict[str, Any],
        *,
        expected_operation: str | None = None,
        transport_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        operation_id = str(request.get("operation_id") or "").strip() if isinstance(request, dict) else ""
        if not operation_id:
            operation_id = new_id("op-skill")
        try:
            self._validate_request(request, expected_operation=expected_operation)
            operation = str(request.get("operation") or "").strip()
            fingerprint = _fingerprint({"operation": operation, "request": request})
            replay = self._load_operation(operation_id)
            if replay is not None:
                if str(replay.get("request_fingerprint") or "") != fingerprint:
                    raise SkillOrchestrationMcpProtocolError(
                        "idempotency_conflict",
                        "operation_id is already bound to a different request fingerprint.",
                    )
                response = deepcopy(dict(replay.get("response") or {}))
                result = dict(response.get("result") or {})
                result["replayed"] = True
                response["result"] = result
                return response
            response = self._dispatch_operation(operation, request, operation_id=operation_id)
            self._save_operation(operation_id, fingerprint=fingerprint, response=response)
            return response
        except SkillOrchestrationMcpProtocolError as exc:
            return self._response(
                operation=str(request.get("operation") or expected_operation or "propose") if isinstance(request, dict) else (expected_operation or "propose"),
                operation_id=operation_id,
                status="blocked",
                resolution=None,
                blockers=[self._diagnostic(exc.code, exc.message, details=exc.details)],
                error_code=exc.code,
                error_message=exc.message,
            )
        except Exception as exc:  # noqa: BLE001
            message = str(redact_sensitive(str(exc) or type(exc).__name__))[:500]
            return self._response(
                operation=str(request.get("operation") or expected_operation or "propose") if isinstance(request, dict) else (expected_operation or "propose"),
                operation_id=operation_id,
                status="failed",
                resolution=None,
                blockers=[self._diagnostic("operation_failed", message)],
                error_code="operation_failed",
                error_message=message,
            )

    def _dispatch_operation(self, operation: str, request: dict[str, Any], *, operation_id: str) -> dict[str, Any]:
        if operation == "propose":
            return self._propose(request, operation_id=operation_id)
        if operation == "patch":
            return self._patch(request, operation_id=operation_id)
        if operation == "validate":
            return self._validate(request, operation_id=operation_id)
        if operation == "dry_run":
            return self._dry_run(request, operation_id=operation_id)
        if operation == "diff":
            return self._diff(request, operation_id=operation_id)
        if operation == "launch":
            return self._launch(request, operation_id=operation_id)
        if operation == "inspect":
            return self._inspect(request, operation_id=operation_id)
        if operation == "cancel":
            return self._cancel(request, operation_id=operation_id)
        if operation == "recover":
            return self._recover(request, operation_id=operation_id)
        raise SkillOrchestrationMcpProtocolError("unknown_operation", f"Unsupported orchestration operation: {operation}")

    def _propose(self, request: dict[str, Any], *, operation_id: str) -> dict[str, Any]:
        resolution = self._build_resolution(request)
        status = "completed" if not list(resolution.get("blockers") or []) else "blocked"
        blockers = [self._diagnostic("resolution_blocked", item) for item in list(resolution.get("blockers") or [])]
        warnings = [self._diagnostic("resolution_warning", item) for item in list(resolution.get("warnings") or [])]
        artifacts = self._resolution_artifacts(resolution)
        return self._response(
            operation="propose",
            operation_id=operation_id,
            status=status,
            resolution=resolution,
            warnings=warnings,
            blockers=blockers,
            artifacts=artifacts,
            result={"resolution_ref": resolution["resolution_ref"], "resolution": self._resolution_summary(resolution)},
            error_code="resolution_blocked" if blockers else None,
            error_message="Skill resolution is blocked." if blockers else None,
        )

    def _patch(self, request: dict[str, Any], *, operation_id: str) -> dict[str, Any]:
        base = self._load_resolution_ref(request.get("resolution_ref"))
        patched = deepcopy(base)
        patches = list(request.get("patches") or [])
        if len(patches) > 64:
            raise SkillOrchestrationMcpProtocolError("patch_limit_exceeded", "At most 64 immutable patches are allowed.")
        for patch in patches:
            self._apply_patch(patched, patch)
        skill_ref = dict(patched.get("skill_ref") or {})
        parameters = dict(patched.get("parameters") or {})
        fresh_request = {
            "skill_ref": skill_ref,
            "parameters": parameters,
            "requested_route": dict(dict(patched.get("policy") or {}).get("requested_route") or {}) or None,
            "requested_budget": request.get("requested_budget"),
        }
        refreshed = self._build_resolution(fresh_request)
        graph = patched.get("canonical_graph")
        if any(str(dict(item).get("path") or "").startswith("/graph") for item in patches if isinstance(item, dict)):
            graph = patched.get("canonical_graph")
            if not isinstance(graph, dict):
                raise SkillOrchestrationMcpProtocolError("graph_patch_target_missing", "Graph patch target is missing.")
            graph = validate_agent_orchestration_graph(graph)
            manifest = dict(patched.get("manifest") or {})
            binding = bind_skill_provider_a2a(manifest, graph)
            refreshed["provider_a2a_binding"] = binding
            if str(binding.get("status") or "") == "blocked":
                refreshed.setdefault("blockers", []).extend(
                    f"provider_a2a:{item}"
                    for item in list(binding.get("blockers") or [])
                    if str(item or "").strip()
                )
            elif str(binding.get("status") or "") == "downgraded":
                refreshed.setdefault("warnings", []).extend(
                    f"provider_a2a:{item}"
                    for item in list(binding.get("warnings") or [])
                    if str(item or "").strip()
                )
            refreshed["canonical_graph"] = graph
            refreshed["resolution_id"] = self._resolution_id(skill_ref=skill_ref, parameters=parameters, graph=graph)
            refreshed["graph_digest"] = _digest_ref(graph)
            refreshed["resolution_ref"]["resolution_id"] = refreshed["resolution_id"]
            refreshed["resolution_ref"]["graph_digest"] = refreshed["graph_digest"]
            refreshed["compiled_plan"] = compile_agent_orchestration_graph(graph)
            refreshed["compiled_plan_digest"] = _digest_ref(refreshed["compiled_plan"])
        refreshed["parent_resolution_id"] = base.get("resolution_id")
        self._persist_resolution(refreshed)
        blockers = [self._diagnostic("resolution_blocked", item) for item in list(refreshed.get("blockers") or [])]
        return self._response(
            operation="patch",
            operation_id=operation_id,
            status="blocked" if blockers else "completed",
            resolution=refreshed,
            warnings=[self._diagnostic("resolution_warning", item) for item in list(refreshed.get("warnings") or [])],
            blockers=blockers,
            artifacts=self._resolution_artifacts(refreshed),
            result={"resolution_ref": refreshed["resolution_ref"], "base_resolution_id": base.get("resolution_id")},
            error_code="resolution_blocked" if blockers else None,
            error_message="Patched resolution is blocked." if blockers else None,
        )

    def _validate(self, request: dict[str, Any], *, operation_id: str) -> dict[str, Any]:
        subject = dict(request.get("subject") or {})
        resolution_ref = subject.get("resolution_ref")
        if isinstance(resolution_ref, dict):
            resolution = self._load_resolution_ref(resolution_ref)
        else:
            resolution = self._build_resolution(
                {
                    "skill_ref": subject.get("skill_ref"),
                    "parameters": subject.get("parameters") or {},
                    "requested_route": subject.get("requested_route"),
                    "requested_budget": subject.get("requested_budget"),
                }
            )
            self._persist_resolution(resolution)
        checks = [str(item).strip() for item in list(request.get("checks") or []) if str(item or "").strip()]
        if not checks:
            checks = ["manifest", "graph", "compile", "policy", "mcp", "a2a", "secrets"]
        check_results = self._validation_checks(resolution, checks)
        blockers = [self._diagnostic(str(item.get("code") or "validation_blocked"), str(item.get("message") or "Validation blocked.")) for item in check_results if str(item.get("status") or "") == "blocked"]
        warnings = [self._diagnostic(str(item.get("code") or "validation_warning"), str(item.get("message") or "Validation warning.")) for item in check_results if str(item.get("status") or "") == "warning"]
        return self._response(
            operation="validate",
            operation_id=operation_id,
            status="blocked" if blockers else "completed",
            resolution=resolution,
            warnings=warnings,
            blockers=blockers,
            artifacts=self._resolution_artifacts(resolution),
            result={"resolution_ref": resolution["resolution_ref"], "checks": check_results},
            error_code="validation_blocked" if blockers else None,
            error_message="One or more requested validation checks failed." if blockers else None,
        )

    def _dry_run(self, request: dict[str, Any], *, operation_id: str) -> dict[str, Any]:
        resolution = self._load_resolution_ref(request.get("resolution_ref"))
        budget = self._validate_budget(request.get("budget"))
        graph = self._require_graph(resolution)
        compiled = compile_agent_orchestration_graph(graph)
        isolation = validate_typed_communication_isolation(graph, compiled)
        guardrails = evaluate_runtime_guardrails(
            graph=graph,
            compiled_plan=compiled,
            run_budget=budget,
            dispatch_limits=None,
            parent_context={},
            mode="fixture_run",
            require_complete_budget=True,
        )
        blockers = list(guardrails.get("blockers") or [])
        if str(isolation.get("status") or "") != "pass":
            blockers.extend(str(item) for item in list(isolation.get("blockers") or []))
        if str(resolution.get("status") or "") == "blocked":
            blockers.extend(str(item) for item in list(resolution.get("blockers") or []))
        policy = self._policy_snapshot_for_resolution(resolution, budget=budget)
        policy_digest = _digest_ref(policy)
        expires_at = (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat()
        receipt = {
            "operation_id": operation_id,
            "graph_digest": str(dict(resolution["resolution_ref"]).get("graph_digest") or _ZERO_DIGEST),
            "policy_digest": policy_digest,
            "expires_at": expires_at,
        }
        artifact_refs = self._write_dry_run_artifacts(
            resolution,
            operation_id=operation_id,
            compiled_plan=compiled,
            policy=policy,
            guardrails=guardrails,
            isolation=isolation,
            receipt=receipt,
        )
        status = "blocked" if blockers else "completed"
        self._record_receipt(resolution, receipt)
        return self._response(
            operation="dry_run",
            operation_id=operation_id,
            status=status,
            resolution=resolution,
            warnings=[self._diagnostic("dry_run_warning", item) for item in list(guardrails.get("warnings") or [])],
            blockers=[self._diagnostic("dry_run_blocked", item) for item in blockers],
            artifacts=artifact_refs,
            result={
                "resolution_ref": resolution["resolution_ref"],
                "dry_run_receipt": receipt,
                "compiled_plan": compiled if request.get("include_compiled_plan", True) else {"digest": _digest_ref(compiled)},
                "guardrails": self._bounded_guardrail_summary(guardrails),
                "communication_isolation": self._bounded_isolation_summary(isolation),
            },
            error_code="dry_run_blocked" if blockers else None,
            error_message="Dry-run did not pass the canonical guardrails." if blockers else None,
        )

    def _diff(self, request: dict[str, Any], *, operation_id: str) -> dict[str, Any]:
        base = self._load_resolution_ref(request.get("base_ref"))
        target = self._load_resolution_ref(request.get("target_ref"))
        graph_diff = diff_agent_orchestration_graphs(
            dict(base.get("canonical_graph") or {}),
            dict(target.get("canonical_graph") or {}),
            old_file_path=str(base.get("source_ref") or "<resolution>"),
            new_file_path=str(target.get("source_ref") or "<resolution>"),
        )
        changes = list(graph_diff.get("changes") or [])
        if _digest_ref(dict(base.get("parameters") or {})) != _digest_ref(dict(target.get("parameters") or {})):
            changes.append({"change_type": "parameters_changed"})
        if _digest_ref(dict(base.get("policy") or {})) != _digest_ref(dict(target.get("policy") or {})):
            changes.append({"change_type": "policy_changed"})
        categories = self._classify_changes(changes, base=base, target=target)
        return self._response(
            operation="diff",
            operation_id=operation_id,
            status="completed",
            resolution=target,
            result={
                "base_resolution_ref": base["resolution_ref"],
                "target_resolution_ref": target["resolution_ref"],
                "status": "changed" if changes else "no_change",
                "categories": categories,
                "changes": changes[:128],
            },
        )

    def _launch(self, request: dict[str, Any], *, operation_id: str) -> dict[str, Any]:
        resolution = self._load_resolution_ref(request.get("resolution_ref"))
        mode = str(request.get("mode") or "").strip()
        budget = self._validate_budget(request.get("budget"))
        approval = self._validate_approval(request.get("approval"))
        receipt = self._validate_receipt(request.get("dry_run_receipt"), resolution, budget)
        if mode == "live" and str(resolution.get("skill_status") or "candidate") not in {
            "productized",
            "provider-qualified",
            "external-a2a-qualified",
        }:
            raise SkillOrchestrationMcpProtocolError("skill_not_promoted", "Candidate skills cannot be launched in live mode.")
        if mode == "live" and str(dict(resolution.get("provider_a2a_binding") or {}).get("status") or "") != "qualified":
            raise SkillOrchestrationMcpProtocolError("provider_a2a_not_qualified", "Live launch requires qualified provider/A2A evidence.")
        graph_id = self._materialize_graph(resolution)
        input_payload = dict(request.get("input") or {})
        if mode == "fixture":
            if self.task_service is None:
                raise SkillOrchestrationMcpProtocolError("task_service_unavailable", "Fixture launch requires the canonical TaskService.")
            result = self.task_service.execute_fixture_graph(
                {
                    "graph_id": graph_id,
                    "execution_mode": str(input_payload.get("execution_mode") or "default"),
                    "node_behaviors": dict(input_payload.get("node_behaviors") or {}),
                    "budget": budget,
                    "approval": approval,
                    "skill_ref": deepcopy(resolution.get("skill_ref") or {}),
                    "resolution_ref": deepcopy(resolution.get("resolution_ref") or {}),
                    "dry_run_receipt": receipt,
                }
            )
        else:
            if self.runtime_service is None:
                raise SkillOrchestrationMcpProtocolError("runtime_service_unavailable", "Live launch requires the canonical RuntimeService.")
            runtime_budget = {**budget, "limits": {"total_tokens": int(budget["max_total_tokens"])}}
            result = self.runtime_service.queue_task_graph_run(
                {
                    "graph_id": graph_id,
                    "budget": runtime_budget,
                    "approval": approval,
                    "idempotency_key": str(request.get("idempotency_key") or "").strip(),
                    "skill_ref": deepcopy(resolution.get("skill_ref") or {}),
                    "resolution_ref": deepcopy(resolution.get("resolution_ref") or {}),
                    "dry_run_receipt": receipt,
                    "_require_complete_runtime_budget": True,
                    "parent_thread_id": str(input_payload.get("parent_thread_id") or "").strip() or None,
                }
            )
        run_id = self._extract_run_id(result)
        return self._response(
            operation="launch",
            operation_id=operation_id,
            status="accepted",
            resolution=resolution,
            artifacts=self._extract_artifacts(result),
            result={"run_id": run_id, "mode": mode, "resolution_ref": resolution["resolution_ref"], "run": self._compact_result(result)},
        )

    def _inspect(self, request: dict[str, Any], *, operation_id: str) -> dict[str, Any]:
        run_id = str(request.get("run_id") or "").strip()
        if not run_id:
            raise SkillOrchestrationMcpProtocolError("run_id_required", "run_id is required.")
        raw = self._read_run(run_id)
        projection = str(request.get("projection") or "compact").strip() or "compact"
        result = self._project_run(raw, projection=projection, event_cursor=int(request.get("event_cursor") or 0), max_events=int(request.get("max_events") or 200))
        resolution = self._resolution_for_run(raw)
        return self._response(operation="inspect", operation_id=operation_id, status="completed", resolution=resolution, result=result)

    def _cancel(self, request: dict[str, Any], *, operation_id: str) -> dict[str, Any]:
        run_id = str(request.get("run_id") or "").strip()
        reason = str(request.get("reason") or "").strip()
        if self.runtime_service is None and self.task_service is None:
            raise SkillOrchestrationMcpProtocolError("runtime_service_unavailable", "Cancellation requires a canonical run owner.")
        payload = {
            "run_id": run_id,
            "notes": reason,
            "reason": reason,
            "idempotency_key": request.get("idempotency_key"),
            "expected_state_version": request.get("expected_state_version"),
        }
        try:
            owner = self.runtime_service if self.runtime_service is not None else self.task_service
            method = getattr(owner, "cancel_task_graph_run", None) or getattr(owner, "cancel_graph_run", None)
            if not callable(method):
                raise SkillOrchestrationMcpProtocolError("cancel_owner_missing", "Canonical run owner does not expose cancellation.")
            result = method(payload)
            status = "cancelled" if str(dict(result.get("cancellation") or {}).get("status") or "").lower() in {"cancelled", "requested"} else "completed"
        except ValueError as exc:
            # Terminal runs are a structured no-op, not a permission to mutate.
            if "Only queued" not in str(exc) and "can be cancelled" not in str(exc):
                raise
            result = self._read_run(run_id)
            status = "completed"
        resolution = self._resolution_for_run(result)
        return self._response(operation="cancel", operation_id=operation_id, status=status, resolution=resolution, artifacts=self._extract_artifacts(result), result={"run_id": run_id, "cancellation": self._compact_result(result)})

    def _recover(self, request: dict[str, Any], *, operation_id: str) -> dict[str, Any]:
        if str(request.get("mode") or "") != "fixture":
            raise SkillOrchestrationMcpProtocolError("live_recovery_not_supported", "Step 11 recovery is intentionally limited to the existing fixture recovery owner.")
        budget = self._validate_budget(request.get("budget"))
        approval = self._validate_approval(request.get("approval"))
        source = self._read_run(str(request.get("run_id") or "").strip())
        resolution = self._resolution_for_run(source)
        receipt = self._validate_receipt(request.get("dry_run_receipt"), resolution, budget)
        if self.task_service is None:
            raise SkillOrchestrationMcpProtocolError("task_service_unavailable", "Fixture recovery requires the canonical TaskService.")
        result = self.task_service.recover_graph_run(
            {
                "run_id": str(request.get("run_id") or "").strip(),
                "strategy": str(request.get("strategy") or "").strip(),
                "selected_node_ids": list(request.get("selected_node_ids") or []),
                "budget": budget,
                "approval": approval,
                "dry_run_receipt": receipt,
                "idempotency_key": request.get("idempotency_key"),
            }
        )
        return self._response(operation="recover", operation_id=operation_id, status="accepted", resolution=resolution, artifacts=self._extract_artifacts(result), result={"run_id": self._extract_run_id(result), "recovery": self._compact_result(result)})

    def _build_resolution(self, request: dict[str, Any]) -> dict[str, Any]:
        skill_ref = dict(request.get("skill_ref") or {})
        if not skill_ref:
            raise SkillOrchestrationMcpProtocolError("skill_ref_required", "skill_ref is required to resolve a skill.")
        parameters = dict(request.get("parameters") or {})
        resolver_request_route = self._resolver_route(request.get("requested_route"))
        report = resolve_skill_to_graph(
            str(skill_ref.get("skill_id") or ""),
            parameters,
            requested_route=resolver_request_route,
            requested_budget=dict(request.get("requested_budget") or {}) or None,
        )
        graph = deepcopy(report.get("canonical_graph")) if isinstance(report.get("canonical_graph"), dict) else None
        compiled: dict[str, Any] | None = None
        extra_blockers: list[str] = []
        if graph is not None and not list(report.get("blockers") or []):
            try:
                graph = validate_agent_orchestration_graph(graph)
                compiled = compile_agent_orchestration_graph(graph)
                isolation = validate_typed_communication_isolation(graph, compiled)
                if str(isolation.get("status") or "") != "pass":
                    extra_blockers.extend(str(item) for item in list(isolation.get("blockers") or []))
            except Exception as exc:  # noqa: BLE001
                extra_blockers.append(f"canonical_graph_compile_failed:{type(exc).__name__}")
        manifest = load_skill_orchestration_manifest(str(skill_ref.get("skill_id") or ""))
        resolution_id = self._resolution_id(skill_ref=skill_ref, parameters=parameters, graph=graph)
        skill_version = str(manifest.get("version") or skill_ref.get("version") or "0.0.0").strip()
        manifest_digest = _digest_ref(manifest)
        graph_digest = _digest_ref(graph) if graph is not None else _ZERO_DIGEST
        policy = deepcopy(dict(report.get("policy_snapshot") or {}))
        if not policy:
            policy = self._policy_snapshot_for_resolution(
                {"manifest": manifest, "canonical_graph": graph, "skill_status": str(manifest.get("status") or "candidate")},
                budget=None,
            )
        blockers = [str(item) for item in list(report.get("blockers") or []) if str(item or "").strip()]
        blockers.extend(extra_blockers)
        resolution = {
            "schema_version": "astrabridge-skill-orchestration-resolution-v1",
            "resolution_id": resolution_id,
            "manifest": redact_sensitive(manifest),
            "skill_ref": {"skill_id": str(manifest.get("skill_id") or skill_ref.get("skill_id") or "").strip(), "version": skill_version, "manifest_digest": manifest_digest},
            "skill_status": str(manifest.get("status") or report.get("skill_status") or "candidate").strip() or "candidate",
            "manifest_digest": manifest_digest,
            "graph_digest": graph_digest,
            "source_ref": report.get("source_ref"),
            "canonical_graph": graph,
            "compiled_plan": compiled,
            "compiled_plan_digest": _digest_ref(compiled) if compiled is not None else _ZERO_DIGEST,
            "parameters": redact_sensitive(parameters),
            "policy": policy,
            "provider_a2a_binding": redact_sensitive(dict(report.get("provider_a2a_binding") or {})),
            "warnings": [str(item) for item in list(report.get("warnings") or []) if str(item or "").strip()],
            "blockers": blockers,
            "created_at": now_iso(),
            "updated_at": now_iso(),
        }
        resolution["resolution_ref"] = {
            "resolution_id": resolution_id,
            "skill_ref": resolution["skill_ref"],
            "manifest_digest": manifest_digest,
            "graph_digest": graph_digest,
        }
        declared_manifest_digest = str(skill_ref.get("manifest_digest") or "").strip()
        if declared_manifest_digest and declared_manifest_digest != manifest_digest:
            resolution["blockers"].append("skill_ref_manifest_digest_mismatch")
        self._persist_resolution(resolution)
        return resolution

    def _validation_checks(self, resolution: dict[str, Any], checks: list[str]) -> list[dict[str, Any]]:
        graph = resolution.get("canonical_graph")
        results: list[dict[str, Any]] = []
        for check in checks:
            if check == "manifest":
                status = "pass" if resolution.get("manifest_digest") not in {None, _ZERO_DIGEST} else "blocked"
                results.append({"check": check, "status": status, "code": "manifest_available" if status == "pass" else "manifest_missing", "message": "Manifest digest is present." if status == "pass" else "Manifest resolution is unavailable."})
            elif check == "graph":
                try:
                    validate_agent_orchestration_graph(dict(graph or {}))
                    results.append({"check": check, "status": "pass", "code": "graph_valid", "message": "Canonical graph validates."})
                except Exception as exc:  # noqa: BLE001
                    results.append({"check": check, "status": "blocked", "code": "graph_invalid", "message": f"Canonical graph validation failed: {type(exc).__name__}."})
            elif check == "compile":
                results.append({"check": check, "status": "pass" if resolution.get("compiled_plan") else "blocked", "code": "compiled_plan_present" if resolution.get("compiled_plan") else "compiled_plan_missing", "message": "Compiled plan is present." if resolution.get("compiled_plan") else "Compiled plan is unavailable."})
            elif check == "policy":
                results.append({"check": check, "status": "blocked" if resolution.get("blockers") else "pass", "code": "policy_blocked" if resolution.get("blockers") else "policy_valid", "message": "Resolution policy contains blockers." if resolution.get("blockers") else "Resolution policy is bounded."})
            elif check == "mcp":
                mcp = dict(dict(resolution.get("policy") or {}).get("mcp") or {})
                results.append({"check": check, "status": "pass" if mcp.get("loopback_allowed") is True else "blocked", "code": "mcp_loopback_valid" if mcp.get("loopback_allowed") is True else "mcp_loopback_missing", "message": "MCP loopback policy is enabled." if mcp.get("loopback_allowed") is True else "MCP loopback policy is not enabled."})
            elif check == "a2a":
                a2a = dict(resolution.get("provider_a2a_binding") or {})
                status = "blocked" if str(a2a.get("status") or "") == "blocked" else "pass"
                results.append({"check": check, "status": status, "code": "a2a_binding_blocked" if status == "blocked" else "a2a_binding_checked", "message": "Provider/A2A binding is blocked." if status == "blocked" else "Provider/A2A boundary was checked."})
            elif check == "secrets":
                results.append({"check": check, "status": "pass", "code": "secret_scan_pass", "message": "Redacted resolution contains no secret-like request values."})
            else:
                results.append({"check": check, "status": "blocked", "code": "unknown_check", "message": f"Unknown validation check: {check}."})
        return results

    def _materialize_graph(self, resolution: dict[str, Any]) -> str:
        if self.task_service is None:
            raise SkillOrchestrationMcpProtocolError("task_service_unavailable", "Graph materialization requires the canonical TaskService.")
        task = self.task_service.current_task()
        if not task:
            task = self.task_service.ensure_default_task(title=str(dict(resolution.get("skill_ref") or {}).get("skill_id") or "Skill orchestration"))
        task_id = str(task.get("task_id") or "").strip()
        if not task_id:
            raise SkillOrchestrationMcpProtocolError("task_id_missing", "Current task has no stable task_id.")
        graph_id = f"skill-resolution-{str(resolution.get('resolution_id') or '')[-48:]}"
        graph = deepcopy(dict(resolution.get("canonical_graph") or {}))
        if not graph:
            raise SkillOrchestrationMcpProtocolError("canonical_graph_missing", "Resolution has no canonical graph to launch.")
        graph["graph_id"] = graph_id
        graph["task_id"] = task_id
        graph["title"] = str(graph.get("title") or dict(resolution.get("skill_ref") or {}).get("skill_id") or "Skill orchestration")[:160]
        graph["state_version"] = max(1, int(graph.get("state_version") or 1))
        metadata = dict(graph.get("metadata") or {})
        metadata["updated_at"] = now_iso()
        graph["metadata"] = metadata
        graph = validate_agent_orchestration_graph(graph)
        task_graph = lower_agent_orchestration_graph_to_task_graph(graph)
        # Keep the canonical graph alongside the compatibility projection. The
        # TaskService then remains the sole graph/run persistence owner without
        # losing provider routes and typed ports during lowering.
        task_graph["orchestration_graph"] = deepcopy(graph)
        saved = self.task_service.upsert_graph_definition(task_graph)
        return str(saved.get("graph_id") or graph_id).strip()

    def _read_run(self, run_id: str) -> dict[str, Any]:
        clean = str(run_id or "").strip()
        if not clean:
            raise SkillOrchestrationMcpProtocolError("run_id_required", "run_id is required.")
        if self.runtime_service is not None and callable(getattr(self.runtime_service, "graph_run_status", None)):
            return dict(self.runtime_service.graph_run_status(clean) or {})
        if self.task_service is not None:
            store = self.task_service.durable_run_store()
            run = store.load_run(clean, include_events=True)
            if run is not None:
                return dict(run)
        raise SkillOrchestrationMcpProtocolError("run_not_found", "Durable graph run was not found.")

    def _project_run(self, raw: dict[str, Any], *, projection: str, event_cursor: int, max_events: int) -> dict[str, Any]:
        run = dict(raw.get("run") or raw)
        events = [redact_sensitive(dict(item)) for item in list(raw.get("events") or run.get("event_refs") or []) if isinstance(item, dict)]
        compact = {
            "run_id": str(run.get("run_id") or raw.get("run_id") or "").strip(),
            "graph_id": str(run.get("graph_id") or "").strip(),
            "task_id": str(run.get("task_id") or "").strip(),
            "status": str(run.get("status") or raw.get("live_run", {}).get("run_status") or "").strip(),
            "state_version": int(run.get("state_version") or 0),
            "created_at": run.get("created_at"),
            "updated_at": run.get("updated_at"),
            "event_cursor": len(events),
        }
        if projection == "compact":
            return {"run": compact}
        result = {"run": compact, "node_status_counts": self._node_status_counts(run)}
        if projection == "events":
            start = max(0, int(event_cursor))
            result["events"] = events[start : start + min(200, max(1, int(max_events or 200)))]
            result["event_cursor"] = start + len(result["events"])
        else:
            result["node_run_states"] = [
                {key: value for key, value in dict(item).items() if key in {"node_id", "status", "outcome", "attempt_count", "updated_at"}}
                for item in list(run.get("node_run_states") or [])
                if isinstance(item, dict)
            ][:64]
        return redact_sensitive(result)

    def _response(
        self,
        *,
        operation: str,
        operation_id: str,
        status: str,
        resolution: dict[str, Any] | None,
        warnings: list[dict[str, Any]] | None = None,
        blockers: list[dict[str, Any]] | None = None,
        artifacts: list[dict[str, Any]] | None = None,
        result: dict[str, Any] | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> dict[str, Any]:
        resolution = resolution if isinstance(resolution, dict) else {}
        response = {
            "direction": "response",
            "schema_version": SKILL_ORCHESTRATION_MCP_SCHEMA_VERSION,
            "operation": operation if operation in _ALLOWED_OPERATIONS else "propose",
            "operation_id": operation_id,
            "status": status,
            "provenance": self._provenance(resolution),
            "policy_snapshot": self._response_policy_snapshot(resolution),
            "warnings": [redact_sensitive(dict(item)) for item in list(warnings or []) if isinstance(item, dict)][:64],
            "blockers": [redact_sensitive(dict(item)) for item in list(blockers or []) if isinstance(item, dict)][:64],
            "artifacts": [redact_sensitive(dict(item)) for item in list(artifacts or []) if isinstance(item, dict)][:64],
            "result": redact_sensitive(dict(result or {})),
        }
        if status in {"blocked", "failed"}:
            response["error"] = {
                "code": str(error_code or "operation_blocked"),
                "message": str(error_message or "Operation was not admitted.")[:500],
            }
        return response

    def _validate_request(self, request: dict[str, Any], *, expected_operation: str | None) -> None:
        if not isinstance(request, dict):
            raise SkillOrchestrationMcpProtocolError("request_must_be_object", "MCP arguments must be an object.")
        if _contains_forbidden(request):
            raise SkillOrchestrationMcpProtocolError("secret_like_content", "Secret-like request keys or values are not allowed.")
        schema = self._load_schema()
        errors = sorted(Draft202012Validator(schema).iter_errors(request), key=lambda item: list(item.absolute_path))
        if errors:
            details = []
            for error in errors[:8]:
                location = ".".join(str(item) for item in error.absolute_path) or "$"
                details.append({"location": location, "message": str(error.message)[:300]})
            raise SkillOrchestrationMcpProtocolError("schema_validation_failed", "MCP request does not satisfy the orchestration schema.", details=details)
        operation = str(request.get("operation") or "").strip()
        if expected_operation and operation != expected_operation:
            raise SkillOrchestrationMcpProtocolError("tool_operation_mismatch", "MCP tool name and operation must agree.")

    def _load_schema(self) -> dict[str, Any]:
        if self._schema is None:
            path = Path(__file__).resolve().parents[3] / "PLAN" / "schemas" / "astrabridge-skill-backed-orchestration-mcp-v1.schema.json"
            self._schema = json.loads(path.read_text(encoding="utf-8"))
        return deepcopy(self._schema)

    def _load_resolution_ref(self, value: Any) -> dict[str, Any]:
        ref = dict(value or {}) if isinstance(value, dict) else {}
        resolution_id = str(ref.get("resolution_id") or "").strip()
        if not resolution_id:
            raise SkillOrchestrationMcpProtocolError("resolution_ref_required", "resolution_ref.resolution_id is required.")
        path = self._resolution_path(resolution_id)
        resolution = read_json(path, None)
        if not isinstance(resolution, dict):
            raise SkillOrchestrationMcpProtocolError("resolution_not_found", "Immutable resolution reference was not found.")
        stored_ref = dict(resolution.get("resolution_ref") or {})
        for field in ("manifest_digest", "graph_digest"):
            if str(ref.get(field) or "").strip() and str(ref.get(field) or "").strip() != str(stored_ref.get(field) or "").strip():
                raise SkillOrchestrationMcpProtocolError("resolution_digest_mismatch", f"resolution_ref.{field} does not match the stored candidate.")
        return resolution

    def _persist_resolution(self, resolution: dict[str, Any]) -> None:
        resolution_id = str(resolution.get("resolution_id") or "").strip()
        if not resolution_id:
            return
        path = self._resolution_path(resolution_id)
        payload = redact_sensitive(deepcopy(resolution))
        write_json(path, payload)

    def _resolution_path(self, resolution_id: str) -> Path:
        root = Path(self.project_service.require_workspace_root()) / ".astrabridge" / "skill-orchestration" / "resolutions"
        root.mkdir(parents=True, exist_ok=True)
        return root / f"{resolution_id}.json"

    def _operation_path(self, operation_id: str) -> Path:
        root = Path(self.project_service.require_workspace_root()) / ".astrabridge" / "skill-orchestration" / "operations"
        root.mkdir(parents=True, exist_ok=True)
        return root / f"{operation_id}.json"

    def _load_operation(self, operation_id: str) -> dict[str, Any] | None:
        value = read_json(self._operation_path(operation_id), None)
        return dict(value) if isinstance(value, dict) else None

    def _save_operation(self, operation_id: str, *, fingerprint: str, response: dict[str, Any]) -> None:
        write_json(
            self._operation_path(operation_id),
            {
                "schema_version": "astrabridge-skill-orchestration-mcp-operation-v1",
                "operation_id": operation_id,
                "request_fingerprint": fingerprint,
                "response": redact_sensitive(response),
                "created_at": now_iso(),
            },
        )

    def _write_dry_run_artifacts(self, resolution: dict[str, Any], *, operation_id: str, compiled_plan: dict[str, Any], policy: dict[str, Any], guardrails: dict[str, Any], isolation: dict[str, Any], receipt: dict[str, Any]) -> list[dict[str, Any]]:
        workspace = Path(self.project_service.require_workspace_root())
        root = workspace / ".astrabridge" / "skill-orchestration" / "dry-runs" / operation_id
        root.mkdir(parents=True, exist_ok=True)
        files = {
            "summary": root / "summary.json",
            "compiled_plan": root / "compiled-plan.json",
            "receipt": root / "dry-run-receipt.json",
        }
        write_json(files["compiled_plan"], redact_sensitive(compiled_plan))
        write_json(files["receipt"], receipt)
        write_json(
            files["summary"],
            {
                "schema_version": "astrabridge-skill-orchestration-dry-run-v1",
                "operation_id": operation_id,
                "resolution_ref": resolution.get("resolution_ref"),
                "policy": policy,
                "guardrails": self._bounded_guardrail_summary(guardrails),
                "communication_isolation": self._bounded_isolation_summary(isolation),
                "artifact_paths": {key: path.relative_to(workspace).as_posix() for key, path in files.items()},
                "created_at": now_iso(),
            },
        )
        return [
            self._artifact(f"{operation_id}-summary", "validation_report", "application/json", files["summary"], workspace),
            self._artifact(f"{operation_id}-compiled-plan", "graph_definition", "application/json", files["compiled_plan"], workspace),
            self._artifact(f"{operation_id}-receipt", "validation_report", "application/json", files["receipt"], workspace),
        ]

    def _record_receipt(self, resolution: dict[str, Any], receipt: dict[str, Any]) -> None:
        existing = list(resolution.get("dry_run_receipts") or []) if isinstance(resolution.get("dry_run_receipts"), list) else []
        existing = [dict(item) for item in existing if isinstance(item, dict) and str(item.get("operation_id") or "") != str(receipt.get("operation_id") or "")]
        existing.insert(0, deepcopy(receipt))
        resolution["dry_run_receipts"] = existing[:8]
        resolution["updated_at"] = now_iso()
        self._persist_resolution(resolution)

    def _validate_budget(self, value: Any) -> dict[str, Any]:
        budget = dict(value or {}) if isinstance(value, dict) else {}
        errors = self._definition_errors("budget", budget)
        if errors:
            raise SkillOrchestrationMcpProtocolError("budget_invalid", "Launch and dry-run budgets must be complete and finite.", details=[{"location": ".".join(str(item) for item in error.absolute_path) or "$", "message": str(error.message)[:300]} for error in errors[:8]])
        if int(budget.get("max_parallel_agents") or 0) > int(budget.get("max_total_agents") or 0):
            raise SkillOrchestrationMcpProtocolError("budget_parallelism_exceeds_total", "max_parallel_agents cannot exceed max_total_agents.")
        return redact_sensitive(budget)

    def _validate_approval(self, value: Any) -> dict[str, Any]:
        approval = dict(value or {}) if isinstance(value, dict) else {}
        errors = self._definition_errors("approval", approval)
        if errors:
            raise SkillOrchestrationMcpProtocolError("approval_invalid", "An explicit approval object is required.")
        if str(approval.get("mode") or "") == "deny":
            raise SkillOrchestrationMcpProtocolError("approval_denied", "The requested launch approval mode is deny.")
        return redact_sensitive(approval)

    def _validate_receipt(self, value: Any, resolution: dict[str, Any], budget: dict[str, Any]) -> dict[str, Any]:
        receipt = dict(value or {}) if isinstance(value, dict) else {}
        errors = self._definition_errors("dry_run_receipt", receipt)
        if errors:
            raise SkillOrchestrationMcpProtocolError("dry_run_receipt_invalid", "A valid dry-run receipt is required before launch or recovery.")
        if str(receipt.get("graph_digest") or "") != str(dict(resolution.get("resolution_ref") or {}).get("graph_digest") or ""):
            raise SkillOrchestrationMcpProtocolError("dry_run_graph_digest_mismatch", "The dry-run graph digest does not match the resolution.")
        expected_policy = self._policy_snapshot_for_resolution(resolution, budget=budget)
        if str(receipt.get("policy_digest") or "") != _digest_ref(expected_policy):
            raise SkillOrchestrationMcpProtocolError("dry_run_policy_digest_mismatch", "The dry-run policy digest does not match the launch budget.")
        try:
            expires_at = datetime.fromisoformat(str(receipt.get("expires_at") or "").replace("Z", "+00:00"))
        except ValueError as exc:
            raise SkillOrchestrationMcpProtocolError("dry_run_receipt_expiry_invalid", "The dry-run receipt expiry is invalid.") from exc
        if expires_at <= datetime.now(timezone.utc):
            raise SkillOrchestrationMcpProtocolError("dry_run_receipt_expired", "The dry-run receipt has expired.")
        return redact_sensitive(receipt)

    def _definition_errors(self, definition: str, value: Any) -> list[Any]:
        """Validate a nested schema definition while retaining its root refs."""

        schema = self._load_schema()
        validator = Draft202012Validator(
            {"$ref": f"#/$defs/{definition}"},
            resolver=RefResolver.from_schema(schema),
        )
        return sorted(validator.iter_errors(value), key=lambda item: list(item.absolute_path))

    def _policy_snapshot_for_resolution(self, resolution: dict[str, Any], *, budget: dict[str, Any] | None) -> dict[str, Any]:
        if budget is not None:
            effective_budget = deepcopy(budget)
        else:
            manifest = dict(resolution.get("manifest") or {})
            policies = dict(manifest.get("policies") or {})
            routing = dict(policies.get("routing") or {})
            graph_policy = dict(dict(resolution.get("canonical_graph") or {}).get("graph_policy") or {})
            declared = dict(policies.get("budget") or {})
            effective_budget = {
                "max_depth": min(2, max(1, int(graph_policy.get("max_depth") or 2))),
                "max_total_agents": max(1, int(declared.get("max_total_agents") or len(list(dict(resolution.get("canonical_graph") or {}).get("nodes") or [])) or 1)),
                "max_parallel_agents": max(1, int(declared.get("max_parallel_agents") or 1)),
                "max_total_tokens": max(1, int(declared.get("max_total_tokens") or 1)),
                "max_provider_calls": max(1, int(declared.get("max_provider_calls") or 1)),
                "max_retries": max(0, int(declared.get("max_retries") or 0)),
                "provider_concurrency": deepcopy(list(declared.get("provider_concurrency") or [])),
                "model_concurrency": deepcopy(list(declared.get("model_concurrency") or [])),
                "allow_nested_subagents": False,
                "allow_direct_teammate_messages": False,
            }
            if not effective_budget["provider_concurrency"]:
                effective_budget["provider_concurrency"] = [{"provider_id": str(item), "max_active_agents": 1} for item in list(routing.get("allowed_provider_ids") or []) if str(item).strip()]
            if not effective_budget["model_concurrency"]:
                effective_budget["model_concurrency"] = []
        return redact_sensitive(effective_budget)

    def _response_policy_snapshot(self, resolution: dict[str, Any]) -> dict[str, Any]:
        budget = self._policy_snapshot_for_resolution(resolution, budget=None)
        return {key: budget.get(key) for key in ("max_depth", "max_total_agents", "max_parallel_agents", "max_total_tokens", "max_provider_calls", "max_retries", "allow_nested_subagents", "allow_direct_teammate_messages")}

    def _provenance(self, resolution: dict[str, Any]) -> dict[str, Any]:
        ref = dict(resolution.get("resolution_ref") or {})
        skill_ref = dict(resolution.get("skill_ref") or {"skill_id": "unresolved", "version": "0.0.0", "manifest_digest": _ZERO_DIGEST})
        return {
            "resolution_id": str(ref.get("resolution_id") or "unresolved"),
            "skill_ref": {"skill_id": str(skill_ref.get("skill_id") or "unresolved"), "version": str(skill_ref.get("version") or "0.0.0"), "manifest_digest": str(skill_ref.get("manifest_digest") or _ZERO_DIGEST)},
            "manifest_digest": str(ref.get("manifest_digest") or _ZERO_DIGEST),
            "graph_digest": str(ref.get("graph_digest") or _ZERO_DIGEST),
            "source_digest": str(resolution.get("graph_digest") or _ZERO_DIGEST),
        }

    def _resolution_id(self, *, skill_ref: dict[str, Any], parameters: dict[str, Any], graph: dict[str, Any] | None) -> str:
        digest = _fingerprint({"skill_ref": skill_ref, "parameters": parameters, "graph": graph})
        return f"resolution-{digest[:48]}"

    def _require_graph(self, resolution: dict[str, Any]) -> dict[str, Any]:
        graph = resolution.get("canonical_graph")
        if not isinstance(graph, dict):
            raise SkillOrchestrationMcpProtocolError("canonical_graph_missing", "Resolution does not contain a canonical graph.")
        return validate_agent_orchestration_graph(graph)

    def _resolver_route(self, value: Any) -> dict[str, Any] | None:
        route = dict(value or {}) if isinstance(value, dict) else {}
        providers = [str(item).strip() for item in list(route.get("provider_ids") or []) if str(item or "").strip()]
        models = [str(item).strip() for item in list(route.get("model_ids") or []) if str(item or "").strip()]
        normalized = {}
        if len(providers) == 1:
            normalized["provider_id"] = providers[0]
        if len(models) == 1:
            normalized["model_id"] = models[0]
        return normalized or None

    def _apply_patch(self, target: dict[str, Any], patch: Any) -> None:
        data = dict(patch or {}) if isinstance(patch, dict) else {}
        op = str(data.get("op") or "").strip()
        path = str(data.get("path") or "").strip()
        if op not in {"add", "replace", "remove"} or not (path.startswith("/parameters") or path.startswith("/graph")):
            raise SkillOrchestrationMcpProtocolError("patch_path_forbidden", "Patches may only target /parameters or /graph.")
        segments = [segment.replace("~1", "/").replace("~0", "~") for segment in path.lstrip("/").split("/") if segment != ""]
        if not segments:
            raise SkillOrchestrationMcpProtocolError("patch_path_invalid", "Patch path must select a bounded field.")
        # The public patch namespace calls the canonical graph `/graph`, while
        # the durable resolution record stores it as `canonical_graph`.
        if segments[0] == "graph":
            if not isinstance(target.get("canonical_graph"), dict):
                raise SkillOrchestrationMcpProtocolError("patch_target_missing", "Canonical graph patch target does not exist.")
            parent: Any = target["canonical_graph"]
            segments = segments[1:]
            if not segments:
                raise SkillOrchestrationMcpProtocolError("patch_path_invalid", "The /graph root cannot be replaced wholesale.")
        else:
            parent = target
        for segment in segments[:-1]:
            if isinstance(parent, dict) and segment in parent:
                parent = parent[segment]
            elif isinstance(parent, list) and segment.isdigit() and 0 <= int(segment) < len(parent):
                parent = parent[int(segment)]
            else:
                raise SkillOrchestrationMcpProtocolError("patch_target_missing", "Patch target does not exist.")
        leaf = segments[-1]
        if isinstance(parent, dict):
            if op == "remove":
                if leaf not in parent:
                    raise SkillOrchestrationMcpProtocolError("patch_target_missing", "Patch remove target does not exist.")
                parent.pop(leaf)
            else:
                parent[leaf] = redact_sensitive(data.get("value"))
        elif isinstance(parent, list) and leaf.isdigit():
            index = int(leaf)
            if op == "add" and index == len(parent):
                parent.append(redact_sensitive(data.get("value")))
            elif 0 <= index < len(parent):
                if op == "remove":
                    parent.pop(index)
                else:
                    parent[index] = redact_sensitive(data.get("value"))
            else:
                raise SkillOrchestrationMcpProtocolError("patch_target_missing", "Patch list target does not exist.")
        else:
            raise SkillOrchestrationMcpProtocolError("patch_target_invalid", "Patch target is not mutable.")
        if _contains_forbidden(target):
            raise SkillOrchestrationMcpProtocolError("secret_like_content", "Patched resolution contains forbidden content.")

    def _resolution_summary(self, resolution: dict[str, Any]) -> dict[str, Any]:
        graph = dict(resolution.get("canonical_graph") or {})
        return {
            "resolution_id": resolution.get("resolution_id"),
            "skill_status": resolution.get("skill_status"),
            "graph_id": graph.get("graph_id"),
            "node_count": len(list(graph.get("nodes") or [])),
            "edge_count": len(list(graph.get("edges") or [])),
            "compiled_plan_digest": resolution.get("compiled_plan_digest"),
            "provider_a2a_status": dict(resolution.get("provider_a2a_binding") or {}).get("status"),
            "blocker_count": len(list(resolution.get("blockers") or [])),
        }

    def _resolution_artifacts(self, resolution: dict[str, Any]) -> list[dict[str, Any]]:
        try:
            workspace = Path(self.project_service.require_workspace_root())
            path = self._resolution_path(str(resolution.get("resolution_id") or ""))
            return [self._artifact(f"{resolution.get('resolution_id')}-resolution", "graph_definition", "application/json", path, workspace)]
        except Exception:
            return []

    @staticmethod
    def _artifact(artifact_id: str, kind: str, media_type: str, path: Path, workspace: Path) -> dict[str, Any]:
        relative = path.relative_to(workspace).as_posix()
        return {"artifact_id": str(artifact_id)[:128], "kind": kind, "media_type": media_type, "workspace_uri": relative, "digest": _digest_ref(read_json(path, {})), "status": "ready"}

    @staticmethod
    def _extract_run_id(result: dict[str, Any]) -> str | None:
        fixture_run = dict(result.get("fixture_run") or {})
        for candidate in (
            result.get("run_id"),
            dict(result.get("live_run") or {}).get("run_id"),
            dict(result.get("run_ref") or {}).get("run_id"),
            dict(fixture_run.get("run_ref") or {}).get("run_id"),
            fixture_run.get("run_id"),
            dict(dict(result.get("recovery") or {}).get("run_ref") or {}).get("run_id"),
        ):
            if str(candidate or "").strip():
                return str(candidate).strip()
        return None

    @staticmethod
    def _extract_artifacts(result: dict[str, Any]) -> list[dict[str, Any]]:
        values: list[dict[str, Any]] = []
        fixture_run = dict(result.get("fixture_run") or {})
        for source in (result, dict(result.get("run_ref") or {}), fixture_run, dict(fixture_run.get("run_ref") or {}), dict(result.get("recovery") or {})):
            for item in list(source.get("artifact_refs") or []) + list(source.get("diagnostic_refs") or []):
                if isinstance(item, dict) and str(item.get("artifact_id") or "").strip():
                    values.append({"artifact_id": str(item.get("artifact_id"))[:128], "kind": str(item.get("artifact_kind") or item.get("kind") or "diagnostic_bundle"), "media_type": str(item.get("media_type") or "application/json"), "workspace_uri": str(item.get("path") or item.get("artifact_uri") or "").strip() or None, "status": "ready" if str(item.get("status") or "ready") not in {"failed", "blocked"} else "failed"})
        return values[:64]

    def _resolution_for_run(self, value: dict[str, Any]) -> dict[str, Any]:
        run = dict(value.get("run") or value)
        policy = dict(run.get("run_policy_snapshot") or {})
        ref = dict(policy.get("resolution_ref") or {})
        if ref.get("resolution_id"):
            try:
                return self._load_resolution_ref(ref)
            except Exception:
                pass
        return {}

    @staticmethod
    def _compact_result(result: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(result, dict):
            return {}
        output: dict[str, Any] = {}
        for key in ("schema_version", "status", "queued", "run_id", "live_run", "run_ref", "cancellation", "recovery", "artifact_refs", "diagnostic_refs"):
            if key in result:
                output[key] = redact_sensitive(result[key])
        fixture_run = dict(result.get("fixture_run") or {})
        if fixture_run:
            output["fixture_run"] = {
                "run_ref": redact_sensitive(dict(fixture_run.get("run_ref") or {})),
                "run_id": str(fixture_run.get("run_id") or "").strip() or None,
            }
        return output

    @staticmethod
    def _node_status_counts(run: dict[str, Any]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for item in list(run.get("node_run_states") or []):
            if not isinstance(item, dict):
                continue
            status = str(item.get("status") or "unknown").strip() or "unknown"
            counts[status] = counts.get(status, 0) + 1
        return counts

    @staticmethod
    def _classify_changes(changes: list[dict[str, Any]], *, base: dict[str, Any], target: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
        categories = {key: [] for key in ("topology", "route", "mcp", "approval", "budget", "context", "artifact")}
        for change in changes:
            text = json.dumps(change, ensure_ascii=False, sort_keys=True).lower()
            if any(token in text for token in ("route", "provider", "model", "profile")):
                category = "route"
            elif any(token in text for token in ("mcp", "tool")):
                category = "mcp"
            elif any(token in text for token in ("approval", "risk")):
                category = "approval"
            elif any(token in text for token in ("budget", "parallel", "retry", "token")):
                category = "budget"
            elif any(token in text for token in ("context", "history", "memory", "message")):
                category = "context"
            elif any(token in text for token in ("artifact", "output")):
                category = "artifact"
            else:
                category = "topology"
            categories[category].append(change)
        return categories

    @staticmethod
    def _bounded_guardrail_summary(value: dict[str, Any]) -> dict[str, Any]:
        return {"status": value.get("status"), "decision_digest": value.get("decision_digest"), "blockers": list(value.get("blockers") or [])[:32], "warnings": list(value.get("warnings") or [])[:32], "normalized_budget": value.get("normalized_budget")}

    @staticmethod
    def _bounded_isolation_summary(value: dict[str, Any]) -> dict[str, Any]:
        return {"status": value.get("status"), "decision_digest": value.get("decision_digest"), "blockers": list(value.get("blockers") or [])[:32], "warnings": list(value.get("warnings") or [])[:32]}

    @staticmethod
    def _diagnostic(code: str, message: str, *, details: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        payload = {"code": str(code or "diagnostic"), "message": str(redact_sensitive(message or ""))[:500]}
        if details:
            payload["details"] = redact_sensitive(details[:8])
        return payload

    @staticmethod
    def _text_projection(response: dict[str, Any]) -> str:
        operation = str(response.get("operation") or "orchestration")
        status = str(response.get("status") or "unknown")
        blockers = len(list(response.get("blockers") or []))
        warnings = len(list(response.get("warnings") or []))
        return f"AstraBridge orchestration {operation}: status={status}; blockers={blockers}; warnings={warnings}."


def _contains_forbidden(value: Any) -> bool:
    if isinstance(value, dict):
        for key, item in value.items():
            clean = str(key or "").strip().lower()
            if clean in _FORBIDDEN_KEYS or any(token in clean for token in ("api_key", "access_token", "authorization", "cookie", "private_reasoning", "raw_secret")):
                return True
            if _contains_forbidden(item):
                return True
        return False
    if isinstance(value, list):
        return any(_contains_forbidden(item) for item in value)
    if isinstance(value, str):
        return bool(SECRET_RE.search(value))
    return False


def _fingerprint(value: Any) -> str:
    payload = redact_sensitive(value)
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _digest_ref(value: Any) -> str:
    return f"sha256:{_fingerprint(value)}"


__all__ = [
    "SKILL_ORCHESTRATION_MCP_SCHEMA_VERSION",
    "SKILL_ORCHESTRATION_MCP_SERVER_NAME",
    "SKILL_ORCHESTRATION_MCP_VERSION",
    "SkillOrchestrationMcpProtocolError",
    "SkillOrchestrationMcpService",
]
