from __future__ import annotations

import tempfile
import unittest
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from astrabridge_sidecar.app_server_client import app_server_command
from astrabridge_sidecar.modal_service import ModalService
from astrabridge_sidecar.project_service import ProjectService
from astrabridge_sidecar.runtime_config_service import RuntimeConfigService
from astrabridge_sidecar.runtime_service import RuntimeService


def _has_disable_pair(command: list[str], feature: str) -> bool:
    return any(left == "--disable" and right == feature for left, right in zip(command, command[1:]))


def _profile() -> dict[str, object]:
    return {
        "profile_id": "unit-provider",
        "label": "Unit Provider",
        "provider_id": "unit",
        "base_url": "https://example.invalid/v1",
        "model": "unit-model",
        "reasoning_effort": "auto",
        "wire_api": "responses",
        "env_key": "UNIT_PROVIDER_KEY",
        "auth_mode": "session_paste",
        "proxy_mode": "direct",
        "proxy_url": "",
    }


class ComputerUsePluginGateTests(unittest.TestCase):
    def test_app_server_command_keeps_plugins_disabled_by_default(self) -> None:
        command = app_server_command()

        self.assertTrue(_has_disable_pair(command, "plugins"))
        self.assertTrue(_has_disable_pair(command, "plugin_sharing"))
        self.assertTrue(_has_disable_pair(command, "remote_plugin"))

    def test_app_server_command_allows_only_local_plugins_for_cua(self) -> None:
        command = app_server_command(allow_plugins=True)

        self.assertFalse(_has_disable_pair(command, "plugins"))
        self.assertTrue(_has_disable_pair(command, "plugin_sharing"))
        self.assertTrue(_has_disable_pair(command, "remote_plugin"))

    def test_runtime_config_can_temporarily_enable_computer_use_plugins(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            service = RuntimeConfigService(Path(temp) / "codex_home")

            default_status = service.prepare_profile(_profile(), require_secret=False)
            default_config = (Path(temp) / "codex_home" / "config.toml").read_text(encoding="utf-8")
            self.assertFalse(default_status["computer_use_plugins_enabled"])
            self.assertIn("plugins = false", default_config)

            cua_status = service.prepare_profile(
                _profile(),
                require_secret=False,
                enable_computer_use_plugins=True,
            )
            cua_config = (Path(temp) / "codex_home" / "config.toml").read_text(encoding="utf-8")
            self.assertTrue(cua_status["computer_use_plugins_enabled"])
            self.assertIn("plugins = true", cua_config)
            self.assertIn("plugin_sharing = false", cua_config)
            self.assertIn("remote_plugin = false", cua_config)
            self.assertNotEqual(service.runtime_signature(default_status), service.runtime_signature(cua_status))

    def test_browser_scenario_runner_starts_model_turn_and_writes_redacted_events(self) -> None:
        class FakeCuaClient:
            def __init__(self, on_notification, on_server_request) -> None:  # noqa: ANN001
                self.on_notification = on_notification
                self.on_server_request = on_server_request
                self.requests: list[tuple[str, object]] = []
                self.closed = False

            def start(self) -> None:
                self.on_notification("thread/status/changed", {"status": "ready"})

            def close(self) -> None:
                self.closed = True

            def request(self, method: str, params=None, timeout: float = 120.0):  # noqa: ANN001, ARG002
                self.requests.append((method, params or {}))
                if method == "thread/start":
                    self.on_notification("thread/started", {"thread": {"id": "thread-cua"}})
                    return {"thread": {"id": "thread-cua"}}
                if method == "turn/start":
                    self.on_notification(
                        "item/mcpToolCall/progress",
                        {"server": "computer-use", "tool": "screenshot", "window": "AstraBridge Browser - News"},
                    )
                    self.on_notification("turn/completed", {"threadId": "thread-cua", "turnId": "turn-cua"})
                    return {"turn": {"id": "turn-cua"}}
                raise AssertionError(f"Unexpected method: {method}")

        old_secret = os.environ.get("UNIT_PROVIDER_KEY")
        os.environ.pop("UNIT_PROVIDER_KEY", None)
        try:
            with tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                workspace = root / "workspace"
                workspace.mkdir()
                project = ProjectService(root / "projects.json")
                project.create_project("Demo", root / "demo.abproj", workspace_root=workspace, entry_mode="existing")
                runtime_config = RuntimeConfigService(root / "codex_home")
                def inject_key(profile: dict[str, object]) -> dict[str, object]:
                    os.environ[str(profile.get("env_key") or "UNIT_PROVIDER_KEY")] = "unit-provider-placeholder-for-cua-test"
                    return {"injected": True, "provider_id": profile.get("provider_id"), "env_key": profile.get("env_key")}

                runtime = RuntimeService(
                    project,
                    ModalService(project.require_shell_state_root),
                    runtime_config=runtime_config,
                    key_injector=inject_key,
                )
                clients: list[FakeCuaClient] = []

                runtime._resolve_launch_target = lambda _status, enable_computer_use_plugins=False: {  # type: ignore[method-assign]
                    "codex_executable": "codex",
                    "launch_command": ["codex", "app-server"],
                    "ws_url": None,
                    "env_updates": {},
                    "cwd": workspace,
                    "allow_plugins": enable_computer_use_plugins,
                }

                def fake_factory(_launch_target):  # noqa: ANN001
                    def factory(on_notification, on_server_request):  # noqa: ANN001
                        client = FakeCuaClient(on_notification, on_server_request)
                        clients.append(client)
                        return client

                    return factory

                runtime._spawned_probe_client_factory = fake_factory  # type: ignore[method-assign]

                report = runtime.computer_use_browser_scenario(
                    _profile(),
                    run_model=True,
                    include_yunwu=False,
                    max_wait_sec=0.0,
                    run_plugin_probe=False,
                )

                self.assertEqual(report["status"], "model_runner_cua_observed")
                self.assertEqual(report["attempts"][0]["status"], "cua_event_observed")
                self.assertEqual(report["attempts"][0]["key_injection"]["injected"], True)
                self.assertEqual([method for method, _params in clients[0].requests], ["thread/start", "turn/start"])
                self.assertTrue(clients[0].closed)
                events_path = Path(report["attempts"][0]["events_path"])
                self.assertTrue(events_path.is_file())
                saved_report = Path(report["artifact_path"]).read_text(encoding="utf-8")
                self.assertNotIn('"profile"', saved_report)
                self.assertNotIn("unit-provider-placeholder-for-cua-test", saved_report)
                self.assertNotIn("unit-provider-placeholder-for-cua-test", events_path.read_text(encoding="utf-8"))
        finally:
            if old_secret is None:
                os.environ.pop("UNIT_PROVIDER_KEY", None)
            else:
                os.environ["UNIT_PROVIDER_KEY"] = old_secret


if __name__ == "__main__":
    unittest.main()
