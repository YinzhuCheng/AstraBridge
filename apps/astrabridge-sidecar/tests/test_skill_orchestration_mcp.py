from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


REPO_ROOT = Path(__file__).resolve().parents[3]
SIDECAR_ROOT = REPO_ROOT / "apps" / "astrabridge-sidecar"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(SIDECAR_ROOT) not in sys.path:
    sys.path.insert(0, str(SIDECAR_ROOT))

from astrabridge_sidecar.mcp_broker_service import McpBrokerService  # noqa: E402
from astrabridge_sidecar.project_service import ProjectService  # noqa: E402
from astrabridge_sidecar.skill_orchestration_mcp_service import (  # noqa: E402
    SKILL_ORCHESTRATION_MCP_SCHEMA_VERSION,
    SkillOrchestrationMcpService,
)
from astrabridge_sidecar.task_service import TaskService  # noqa: E402


SKILL_REF = {
    "skill_id": "astrabridge.supervisor-worker-synthesizer",
    "version": "1.0.0",
}


def _budget() -> dict[str, Any]:
    return {
        "max_depth": 2,
        "max_total_agents": 3,
        "max_parallel_agents": 1,
        "max_total_tokens": 60000,
        "max_provider_calls": 3,
        "max_retries": 1,
        "provider_concurrency": [{"provider_id": "qwen", "max_active_agents": 1}],
        "model_concurrency": [{"provider_id": "qwen", "model_id": "qwen3-coder-plus", "max_active_agents": 1}],
        "allow_nested_subagents": False,
        "allow_direct_teammate_messages": False,
    }


def _approval() -> dict[str, Any]:
    return {
        "mode": "manual",
        "approval_ref": "approval-mcp-fixture-1",
        "risky_effects_require_approval": ["provider_call", "file_write"],
    }


class SkillOrchestrationMcpTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.workspace = root / "workspace"
        self.workspace.mkdir(parents=True)
        (self.workspace / "PRIVATE").mkdir()
        (self.workspace / ".astrabridge").mkdir()
        self.projects = ProjectService(store_path=root / "projects.json", session_path=root / "current.json")
        self.projects.create_project("MCP fixture", root / "mcp-fixture.abproj", workspace_root=self.workspace, entry_mode="new")
        self.tasks = TaskService(self.projects)
        self.tasks.create_task("MCP fixture task")
        self.service = SkillOrchestrationMcpService(project_service=self.projects, task_service=self.tasks)
        self.broker = McpBrokerService(project_service=self.projects, orchestration_service=self.service)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def call(self, tool: str, arguments: dict[str, Any], operation_id: str) -> dict[str, Any]:
        payload = self.broker.invoke_tool(
            "astrabridge-orchestration",
            tool,
            arguments,
            caller="unit-test",
            operation_id=operation_id,
        )
        response = dict(payload.get("result") or {})
        self.assertEqual(payload.get("mcp", {}).get("transport"), "loopback")
        return response

    def assert_protocol_response(self, response: dict[str, Any]) -> None:
        schema = json.loads((REPO_ROOT / "PLAN" / "schemas" / "astrabridge-skill-backed-orchestration-mcp-v1.schema.json").read_text(encoding="utf-8"))
        errors = list(Draft202012Validator(schema).iter_errors(response))
        self.assertFalse(errors, [error.message for error in errors[:4]])
        self.assertEqual(response.get("schema_version"), SKILL_ORCHESTRATION_MCP_SCHEMA_VERSION)

    def test_loopback_tools_and_skill_fixture_lifecycle(self) -> None:
        tools = self.service.tools()
        self.assertEqual(len(tools), 9)
        self.assertEqual(
            {item["name"] for item in tools},
            {
                "astrabridge_orchestration_propose",
                "astrabridge_orchestration_patch",
                "astrabridge_orchestration_validate",
                "astrabridge_orchestration_dry_run",
                "astrabridge_orchestration_diff",
                "astrabridge_orchestration_launch",
                "astrabridge_orchestration_inspect",
                "astrabridge_orchestration_cancel",
                "astrabridge_orchestration_recover",
            },
        )
        proposed = self.call(
            "astrabridge_orchestration_propose",
            {
                "direction": "request",
                "schema_version": SKILL_ORCHESTRATION_MCP_SCHEMA_VERSION,
                "operation": "propose",
                "request_id": "request-propose-1",
                "skill_ref": SKILL_REF,
                "parameters": {"task_goal": "Verify the canonical MCP fixture path."},
            },
            "op-mcp-propose-1",
        )
        self.assert_protocol_response(proposed)
        self.assertEqual(proposed.get("status"), "completed")
        resolution_ref = dict(dict(proposed.get("result") or {}).get("resolution_ref") or {})
        self.assertTrue(resolution_ref.get("resolution_id"))
        self.assertTrue((self.workspace / ".astrabridge" / "skill-orchestration" / "resolutions").is_dir())

        patched = self.call(
            "astrabridge_orchestration_patch",
            {
                "direction": "request",
                "schema_version": SKILL_ORCHESTRATION_MCP_SCHEMA_VERSION,
                "operation": "patch",
                "request_id": "request-patch-1",
                "resolution_ref": resolution_ref,
                "patches": [{"op": "replace", "path": "/graph/nodes/0/prompt", "value": {"template_mode": "inline", "template": "Keep the supervisor plan bounded and evidence-first."}}],
            },
            "op-mcp-patch-1",
        )
        self.assert_protocol_response(patched)
        self.assertEqual(patched.get("status"), "completed")
        patched_ref = dict(dict(patched.get("result") or {}).get("resolution_ref") or {})
        self.assertNotEqual(patched_ref.get("resolution_id"), resolution_ref.get("resolution_id"))

        diffed = self.call(
            "astrabridge_orchestration_diff",
            {
                "direction": "request",
                "schema_version": SKILL_ORCHESTRATION_MCP_SCHEMA_VERSION,
                "operation": "diff",
                "request_id": "request-diff-1",
                "base_ref": resolution_ref,
                "target_ref": patched_ref,
            },
            "op-mcp-diff-1",
        )
        self.assert_protocol_response(diffed)
        self.assertEqual(diffed.get("status"), "completed")
        self.assertEqual(dict(diffed.get("result") or {}).get("status"), "changed")

        validated = self.call(
            "astrabridge_orchestration_validate",
            {
                "direction": "request",
                "schema_version": SKILL_ORCHESTRATION_MCP_SCHEMA_VERSION,
                "operation": "validate",
                "request_id": "request-validate-1",
                "subject": {"resolution_ref": resolution_ref},
            },
            "op-mcp-validate-1",
        )
        self.assert_protocol_response(validated)
        self.assertEqual(validated.get("status"), "completed")
        check_statuses = {item.get("check"): item.get("status") for item in dict(validated.get("result") or {}).get("checks") or []}
        self.assertEqual(check_statuses.get("mcp"), "pass")

        dry_run = self.call(
            "astrabridge_orchestration_dry_run",
            {
                "direction": "request",
                "schema_version": SKILL_ORCHESTRATION_MCP_SCHEMA_VERSION,
                "operation": "dry_run",
                "request_id": "request-dry-run-1",
                "resolution_ref": resolution_ref,
                "budget": _budget(),
                "include_compiled_plan": True,
            },
            "op-mcp-dry-run-1",
        )
        self.assert_protocol_response(dry_run)
        self.assertEqual(dry_run.get("status"), "completed")
        receipt = dict(dict(dry_run.get("result") or {}).get("dry_run_receipt") or {})
        self.assertTrue(receipt.get("operation_id"))
        self.assertTrue((self.workspace / ".astrabridge" / "skill-orchestration" / "dry-runs" / "op-mcp-dry-run-1" / "dry-run-receipt.json").is_file())

        launch = self.call(
            "astrabridge_orchestration_launch",
            {
                "direction": "request",
                "schema_version": SKILL_ORCHESTRATION_MCP_SCHEMA_VERSION,
                "operation": "launch",
                "request_id": "request-launch-1",
                "resolution_ref": resolution_ref,
                "budget": _budget(),
                "approval": _approval(),
                "idempotency_key": "idem-mcp-fixture-1",
                "dry_run_receipt": receipt,
                "mode": "fixture",
                "input": {},
            },
            "op-mcp-launch-1",
        )
        self.assert_protocol_response(launch)
        self.assertEqual(launch.get("status"), "accepted")
        run_id = str(dict(launch.get("result") or {}).get("run_id") or "")
        self.assertTrue(run_id)

        inspected = self.call(
            "astrabridge_orchestration_inspect",
            {
                "direction": "request",
                "schema_version": SKILL_ORCHESTRATION_MCP_SCHEMA_VERSION,
                "operation": "inspect",
                "request_id": "request-inspect-1",
                "run_id": run_id,
                "projection": "summary",
            },
            "op-mcp-inspect-1",
        )
        self.assert_protocol_response(inspected)
        self.assertEqual(inspected.get("status"), "completed")
        self.assertEqual(dict(dict(inspected.get("result") or {}).get("run") or {}).get("run_id"), run_id)

        cancelled = self.call(
            "astrabridge_orchestration_cancel",
            {
                "direction": "request",
                "schema_version": SKILL_ORCHESTRATION_MCP_SCHEMA_VERSION,
                "operation": "cancel",
                "request_id": "request-cancel-1",
                "run_id": run_id,
                "reason": "Fixture run is already terminal.",
                "idempotency_key": "idem-mcp-cancel-1",
            },
            "op-mcp-cancel-1",
        )
        self.assert_protocol_response(cancelled)
        self.assertIn(cancelled.get("status"), {"completed", "cancelled"})

    def test_broker_operation_id_replay_and_secret_fail_closed(self) -> None:
        request = {
            "direction": "request",
            "schema_version": SKILL_ORCHESTRATION_MCP_SCHEMA_VERSION,
            "operation": "propose",
            "request_id": "request-replay-1",
            "skill_ref": SKILL_REF,
            "parameters": {"task_goal": "Replay the same MCP proposal."},
        }
        first = self.call("astrabridge_orchestration_propose", request, "op-mcp-replay-1")
        replay = self.call("astrabridge_orchestration_propose", request, "op-mcp-replay-1")
        self.assert_protocol_response(first)
        self.assert_protocol_response(replay)
        self.assertTrue(dict(replay.get("result") or {}).get("replayed"))

        conflict = dict(request)
        conflict["parameters"] = {"task_goal": "A different proposal must not reuse the operation id."}
        conflicted = self.call("astrabridge_orchestration_propose", conflict, "op-mcp-replay-1")
        self.assert_protocol_response(conflicted)
        self.assertEqual(conflicted.get("status"), "blocked")
        self.assertEqual(dict(conflicted.get("error") or {}).get("code"), "idempotency_conflict")

        secret_request = dict(request)
        secret_request["request_id"] = "request-secret-1"
        secret_request["parameters"] = {"task_goal": "Author" + "ization: Bearer " + "test-secret-value"}
        rejected = self.call("astrabridge_orchestration_propose", secret_request, "op-mcp-secret-1")
        self.assert_protocol_response(rejected)
        self.assertEqual(rejected.get("status"), "blocked")
        self.assertEqual(dict(rejected.get("error") or {}).get("code"), "secret_like_content")
        self.assertNotIn("test-secret-value", json.dumps(rejected, ensure_ascii=False))

    def test_fixture_recovery_stays_on_canonical_task_owner(self) -> None:
        base = {
            "direction": "request",
            "schema_version": SKILL_ORCHESTRATION_MCP_SCHEMA_VERSION,
            "skill_ref": SKILL_REF,
            "parameters": {"task_goal": "Exercise bounded fixture recovery."},
        }
        proposed = self.call(
            "astrabridge_orchestration_propose",
            {**base, "operation": "propose", "request_id": "request-recovery-propose-1"},
            "op-mcp-recovery-propose-1",
        )
        resolution_ref = dict(dict(proposed.get("result") or {}).get("resolution_ref") or {})
        dry_run = self.call(
            "astrabridge_orchestration_dry_run",
            {
                "direction": "request",
                "schema_version": SKILL_ORCHESTRATION_MCP_SCHEMA_VERSION,
                "operation": "dry_run",
                "request_id": "request-recovery-dry-run-1",
                "resolution_ref": resolution_ref,
                "budget": _budget(),
            },
            "op-mcp-recovery-dry-run-1",
        )
        receipt = dict(dict(dry_run.get("result") or {}).get("dry_run_receipt") or {})
        failed = self.call(
            "astrabridge_orchestration_launch",
            {
                "direction": "request",
                "schema_version": SKILL_ORCHESTRATION_MCP_SCHEMA_VERSION,
                "operation": "launch",
                "request_id": "request-recovery-launch-1",
                "resolution_ref": resolution_ref,
                "budget": _budget(),
                "approval": _approval(),
                "idempotency_key": "idem-mcp-recovery-launch-1",
                "dry_run_receipt": receipt,
                "mode": "fixture",
                "input": {"node_behaviors": {"node_worker": "failed"}},
            },
            "op-mcp-recovery-launch-1",
        )
        source_run_id = str(dict(failed.get("result") or {}).get("run_id") or "")
        self.assertTrue(source_run_id)
        recovered = self.call(
            "astrabridge_orchestration_recover",
            {
                "direction": "request",
                "schema_version": SKILL_ORCHESTRATION_MCP_SCHEMA_VERSION,
                "operation": "recover",
                "request_id": "request-recovery-1",
                "run_id": source_run_id,
                "strategy": "retry_failed_nodes",
                "budget": _budget(),
                "approval": _approval(),
                "idempotency_key": "idem-mcp-recovery-1",
                "dry_run_receipt": receipt,
                "mode": "fixture",
            },
            "op-mcp-recovery-1",
        )
        self.assert_protocol_response(recovered)
        self.assertEqual(recovered.get("status"), "accepted")
        recovery_run_id = str(dict(recovered.get("result") or {}).get("run_id") or "")
        self.assertTrue(recovery_run_id)
        self.assertNotEqual(recovery_run_id, source_run_id)
        self.assertTrue((self.workspace / "PRIVATE" / "task-graph" / "recovery").is_dir())


if __name__ == "__main__":
    unittest.main()
