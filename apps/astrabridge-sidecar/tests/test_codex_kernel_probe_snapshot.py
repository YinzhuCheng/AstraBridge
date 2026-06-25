from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from astrabridge_sidecar.codex_kernel_snapshot import build_codex_kernel_probe_snapshot, observe_protocol_features
from astrabridge_sidecar.server import Handler


class CodexKernelProbeSnapshotTests(unittest.TestCase):
    def test_observe_protocol_features_parses_generated_methods(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            client_path = root / "ClientRequest.ts"
            notification_path = root / "ServerNotification.ts"
            client_path.write_text(
                'export type ClientRequest = { "method": "initialize" } | { "method": "plugin/list" } | { "method": "skills/list" };',
                encoding="utf-8",
            )
            notification_path.write_text(
                'export type ServerNotification = { "method": "thread/started" } | { "method": "skills/changed" };',
                encoding="utf-8",
            )

            observed = observe_protocol_features(
                client_request_path=client_path,
                server_notification_path=notification_path,
            )

            self.assertEqual(observed["source_kind"], "generated_types_only")
            self.assertEqual(observed["client_methods"]["initialize"], "declared")
            self.assertEqual(observed["client_methods"]["plugin/list"], "declared")
            self.assertEqual(observed["client_methods"]["skills/list"], "declared")
            self.assertEqual(observed["server_notifications"]["thread/started"], "declared")
            self.assertEqual(observed["server_notifications"]["skills/changed"], "declared")

    def test_build_snapshot_preserves_contract_and_conservative_inference(self) -> None:
        snapshot = build_codex_kernel_probe_snapshot(
            binary={
                "path": r"D:\Tools\OpenAI\Codex\bin\codex.EXE",
                "path_source": "which",
                "version_text": "codex-cli 0.137.0",
                "version_semver": "0.137.0",
                "version_parse_status": "ok",
                "launch_descriptor": r"D:\Tools\OpenAI\Codex\bin\codex.EXE",
            },
            execution_host="windows",
            wsl_distro=None,
            runtime_status={"codex_home": r"D:\AstraBridge\.astrabridge\codex-home"},
            runtime_roots={
                "project_runtime_root": r"D:\AstraBridge\.astrabridge\runtime",
                "workspace_runtime_cwd": r"D:\AstraBridge\.astrabridge\runtime-cwd",
            },
            app_server={
                "transport": "stdio",
                "launch_mode": "reused_client",
                "available": True,
                "initialize_status": "supported",
                "thread_start_status": "not_checked",
                "thread_resume_status": "not_checked",
                "turn_start_status": "not_checked",
                "approval_events_status": "not_checked",
                "mcp_elicitation_status": "not_checked",
                "disconnect_status": "not_observed",
                "error_shape_status": "not_checked",
                "last_checked_at": "2026-06-25T12:00:00+08:00",
            },
            protocol_features={
                "source_kind": "generated_types_only",
                "client_methods": {
                    "plugin/install": "declared",
                    "plugin/uninstall": "declared",
                    "plugin/share/list": "declared",
                    "skills/extraRoots/set": "declared",
                    "skills/config/write": "declared",
                },
                "server_notifications": {"skills/changed": "declared"},
                "notes": [],
            },
            mcp_report={
                "report_path": "PRIVATE/demo-runs/kernel/mcp.json",
                "known_warnings": [],
                "mcp": {
                    "config_render_status": "supported",
                    "config_updated_at": "2026-06-25T11:00:00+08:00",
                    "reload_status": "supported",
                    "server_status_list_status": "supported",
                    "expected_servers": ["astrabridge_capabilities"],
                    "visible_servers": ["astrabridge_capabilities"],
                    "expected_tools": ["astrabridge_capability_routes"],
                    "visible_tools": ["astrabridge_capability_routes"],
                    "missing_servers": [],
                    "missing_tools": [],
                    "unexpected_servers": [],
                },
            },
            plugin_report={
                "report_path": "PRIVATE/demo-runs/kernel/plugin.json",
                "known_warnings": [],
                "plugin": {
                    "config_feature_state": "disabled_by_app",
                    "list_status": "unsupported",
                    "installed_status": "unsupported",
                    "read_status": "unsupported",
                    "marketplace_status": "not_checked",
                    "featured_plugin_ids": [],
                    "marketplace_load_errors": [],
                    "malformed_manifest_paths": [],
                    "discovered_plugins": [],
                },
            },
            skill_report={
                "report_path": "PRIVATE/demo-runs/kernel/skill.json",
                "known_warnings": [],
                "skill": {
                    "list_status": "supported",
                    "discovered_roots": [r"D:\AstraBridge\.astrabridge\skills"],
                    "discovered_skills": [
                        {
                            "skill_name": "frontend-ui-engineering",
                            "display_name": "frontend-ui-engineering",
                            "source_kind": "local_skill_root",
                            "owner_plugin_id": None,
                            "enablement": "enabled",
                        }
                    ],
                    "notes": [],
                },
            },
            extra_warnings=[],
            evidence_sources=["apps/astrabridge-sidecar/astrabridge_sidecar/runtime_service.py"],
        )

        self.assertEqual(snapshot["schema_version"], "codex-kernel-probe-v1")
        self.assertEqual(snapshot["observed"]["binary"]["version_semver"], "0.137.0")
        self.assertEqual(snapshot["inferred"]["compatibility_status"], "probed")
        self.assertEqual(snapshot["inferred"]["plugin_integration_readiness"], "blocked_by_app_config")
        self.assertEqual(snapshot["inferred"]["skill_integration_readiness"], "partial")
        self.assertIn("rendered_config_disables_plugins", snapshot["known_warnings"])
        self.assertIn("PRIVATE/demo-runs/kernel/mcp.json", snapshot["evidence"]["artifacts"])
        self.assertIn("PRIVATE/demo-runs/kernel/plugin.json", snapshot["evidence"]["artifacts"])
        self.assertIn("PRIVATE/demo-runs/kernel/skill.json", snapshot["evidence"]["artifacts"])


class CodexKernelProbeRouteTests(unittest.TestCase):
    def test_handler_runtime_kernel_probe_route_returns_snapshot(self) -> None:
        handler = Handler.__new__(Handler)
        captured: dict[str, Any] = {}

        class Runtime:
            def __init__(self) -> None:
                self.profiles: list[dict[str, Any]] = []

            def kernel_probe_snapshot(self, profile: dict[str, Any]) -> dict[str, Any]:
                self.profiles.append(profile)
                return {
                    "schema_version": "codex-kernel-probe-v1",
                    "generated_at": "2026-06-25T12:34:56+08:00",
                    "probe_run_id": "codex-kernel-probe-unit",
                    "observed": {},
                    "inferred": {"compatibility_status": "unknown"},
                    "known_warnings": [],
                    "evidence": {"sources": [], "commands": [], "artifacts": []},
                }

        class Context:
            runtime = Runtime()

        handler.context = Context()  # type: ignore[assignment]
        handler.path = "/api/runtime/kernel-probe?profile_id=test-profile"  # type: ignore[assignment]
        handler.send_json = lambda payload, status=200: captured.update({"payload": payload, "status": status})  # type: ignore[assignment]
        handler._resolve_runtime_profile = lambda profile_id: {"profile_id": profile_id or "resolved-profile"}  # type: ignore[assignment]

        Handler.do_GET(handler)

        self.assertEqual(captured["status"], 200)
        self.assertEqual(captured["payload"]["schema_version"], "codex-kernel-probe-v1")
        self.assertEqual(handler.context.runtime.profiles, [{"profile_id": "test-profile"}])  # type: ignore[attr-defined]


if __name__ == "__main__":
    unittest.main()
