from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from astrabridge_sidecar.codex_kernel_smoke import (
    _default_smoke_profile,
    _probe_automation_exec_help,
    run_codex_kernel_smoke,
)
from astrabridge_sidecar.mcp_config_service import McpConfigService
from astrabridge_sidecar.modal_service import ModalService
from astrabridge_sidecar.project_service import ProjectService
from astrabridge_sidecar.runtime_config_service import RuntimeConfigService


class CodexKernelSmokeTests(unittest.TestCase):
    def test_run_codex_kernel_smoke_writes_report_with_injected_probes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            repo_root = root / "repo"
            repo_root.mkdir(parents=True, exist_ok=True)
            artifact_root = repo_root / "PRIVATE" / "demo-runs" / "codex-kernel-smoke-test"

            def fake_help(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:  # noqa: ARG001
                return subprocess.CompletedProcess(
                    command,
                    0,
                    stdout="Run Codex non-interactively\n--sandbox\n--skip-git-repo-check\n--ignore-user-config\n",
                    stderr="",
                )

            report = run_codex_kernel_smoke(
                artifact_root=artifact_root,
                repo_root=repo_root,
                binary_discovery_fn=lambda **kwargs: {  # noqa: ARG005
                    "path": r"D:\Tools\OpenAI\Codex\bin\codex.exe",
                    "path_source": "env_override",
                    "launch_descriptor": r"D:\Tools\OpenAI\Codex\bin\codex.exe",
                    "version_text": "codex-cli 0.137.0",
                    "version_semver": "0.137.0",
                    "version_parse_status": "ok",
                    "version_error": None,
                },
                protocol_observer_fn=lambda: {
                    "source_kind": "generated_types_only",
                    "client_methods": {"turn/start": "declared"},
                    "server_notifications": {"thread/started": "declared"},
                    "notes": [],
                },
                app_server_status_override=(
                    {
                        "transport": "stdio",
                        "launch_mode": "probe_stub",
                        "available": True,
                        "initialize_status": "supported",
                        "thread_start_status": "not_checked",
                        "thread_resume_status": "not_checked",
                        "turn_start_status": "not_checked",
                        "approval_events_status": "not_checked",
                        "mcp_elicitation_status": "not_checked",
                        "disconnect_status": "clean",
                        "error_shape_status": "not_checked",
                        "last_checked_at": "2026-06-25T12:00:00+08:00",
                    },
                    object(),
                    [],
                ),
                app_server_probe_fn=lambda **kwargs: {  # noqa: ARG005
                    "report_path": str(artifact_root / "probes" / "app-server" / "probe.json"),
                    "app_server": {
                        "thread_start_status": "supported",
                        "thread_resume_status": "supported",
                        "turn_start_status": "error_response",
                        "turn_error_shape_status": "jsonrpc_error",
                        "notifications_seen": ["thread/started"],
                        "server_requests_seen": [],
                        "turn_error": {"code": -32000, "message": "provider auth missing"},
                    },
                    "known_warnings": [],
                },
                mcp_probe_fn=lambda **kwargs: {  # noqa: ARG005
                    "report_path": str(artifact_root / "probes" / "mcp" / "probe.json"),
                    "mcp": {
                        "config_render_status": "supported",
                        "config_updated_at": "2026-06-25T12:00:00+08:00",
                        "reload_status": "supported",
                        "server_status_list_status": "supported",
                        "config_visibility_status": "supported",
                        "expected_servers": ["astrabridge_capabilities", "astrabridge_probe_fixture", "astrabridge_web"],
                        "visible_servers": ["astrabridge_capabilities", "astrabridge_probe_fixture", "astrabridge_web"],
                        "expected_tools": ["astrabridge_capability_routes", "astrabridge_probe_ping", "astrabridge_web_search"],
                        "visible_tools": ["astrabridge_capability_routes", "astrabridge_probe_ping", "astrabridge_web_search"],
                        "missing_servers": [],
                        "missing_tools": [],
                        "unexpected_servers": [],
                    },
                    "known_warnings": [],
                },
                plugin_probe_fn=lambda **kwargs: {  # noqa: ARG005
                    "report_path": str(artifact_root / "probes" / "plugin" / "probe.json"),
                    "plugin": {
                        "config_feature_state": "disabled_by_app",
                        "plugin_sharing_feature_state": "disabled_by_app",
                        "remote_plugin_feature_state": "disabled_by_app",
                        "list_status": "unsupported",
                        "installed_status": "unsupported",
                        "read_status": "unsupported",
                        "marketplace_status": "not_checked",
                        "manifest_fallback_status": "not_checked",
                        "discovered_plugins": [],
                    },
                    "known_warnings": [],
                },
                skill_probe_fn=lambda **kwargs: {  # noqa: ARG005
                    "report_path": str(artifact_root / "probes" / "skill" / "probe.json"),
                    "skill": {
                        "list_status": "supported",
                        "extra_roots_status": "declared",
                        "config_write_status": "declared",
                        "change_notification_status": "declared",
                        "discovered_roots": [str(repo_root / "apps" / "astrabridge-sidecar" / "skills")],
                        "discovered_skills": [
                            {
                                "skill_name": "model-metadata-curator",
                                "display_name": "model-metadata-curator",
                                "source_kind": "local_skill_root",
                                "owner_plugin_id": None,
                                "enablement": "enabled",
                            }
                        ],
                    },
                    "known_warnings": [],
                },
                subprocess_run=fake_help,
            )

            self.assertIn(report["summary"]["overall_status"], {"pass", "warn"})
            self.assertEqual(report["summary"]["critical_failures"], [])
            self.assertTrue((artifact_root / "reports" / "smoke-report.json").exists())
            self.assertTrue((artifact_root / "reports" / "kernel-probe-snapshot.json").exists())
            check_ids = {item["check_id"] for item in report["checks"]}
            self.assertIn("automation_standalone_invocation", check_ids)
            self.assertIn("plugin_discovery", check_ids)
            self.assertIn("skill_discovery", check_ids)

    def test_probe_automation_exec_help_fails_when_codex_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            projects, runtime_config, profile = self._runtime_context(Path(temp_dir))

            def fake_missing(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:  # noqa: ARG001
                raise FileNotFoundError("codex not found")

            check = _probe_automation_exec_help(
                project_service=projects,
                runtime_config=runtime_config,
                profile=profile,
                subprocess_run=fake_missing,
            )

            self.assertEqual(check["check_id"], "automation_standalone_invocation")
            self.assertEqual(check["status"], "fail")
            self.assertIn("PATH", check["summary"])

    def _runtime_context(self, root: Path) -> tuple[ProjectService, RuntimeConfigService, dict[str, Any]]:
        projects = ProjectService(
            store_path=root / "projects.json",
            session_path=root / "current_project.json",
        )
        workspace_root = root / "workspace"
        project_file = root / "smoke.abproj"
        project = projects.create_project(
            "Smoke",
            project_file,
            workspace_root=workspace_root,
            entry_mode="new",
        )
        modal_service = ModalService(projects.require_shell_state_root)
        del modal_service  # The runtime config path needs only the shell state root side effect.
        mcp_config = McpConfigService(store_path=projects.require_shell_state_root() / "mcp_servers.json")
        runtime_config = RuntimeConfigService(
            codex_home_resolver=projects.current_runtime_codex_home,
            mcp_config=mcp_config,
        )
        profile = _default_smoke_profile(project)
        runtime_config.prepare_profile(profile, require_secret=False)
        return projects, runtime_config, profile


if __name__ == "__main__":
    unittest.main()
