from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from astrabridge_sidecar.codex_mcp_probe import probe_mcp_compatibility
from astrabridge_sidecar.mcp_config_service import McpConfigService


class _FakeMcpProbeClient:
    def __init__(self, scenario: str, payload: dict[str, object], on_notification=None) -> None:
        self._scenario = scenario
        self._payload = payload
        self._on_notification = on_notification
        self.requests: list[str] = []
        self.request_params: list[tuple[str, Any]] = []
        self.closed = False

    def start(self) -> None:
        if self._scenario in {"notify-startup", "notify-startup-timeout"} and self._on_notification is not None:
            self._on_notification(
                "mcpServer/startupStatus/updated",
                {"serverName": "astrabridge_probe_fixture", "status": "starting"},
            )
        return None

    def close(self) -> None:
        self.closed = True

    def request(self, method: str, params=None, timeout: float = 120.0):  # noqa: ARG002
        self.requests.append(method)
        self.request_params.append((method, params))
        if method == "config/mcpServer/reload":
            if self._scenario in {"notify-startup", "notify-startup-timeout"} and self._on_notification is not None:
                self._on_notification(
                    "mcpServer/startupStatus/updated",
                    {"serverName": "astrabridge_probe_fixture", "status": "running"},
                )
            return {"reloaded": True}
        if method == "thread/start":
            return {"thread": {"id": "probe-thread"}}
        if method == "mcpServerStatus/list":
            if isinstance(params, dict) and "limit" in params:
                raise AssertionError("MCP probe should use minimal thread-scoped mcpServerStatus/list params")
            if self._scenario in {"status-timeout", "notify-startup-timeout"}:
                raise TimeoutError("Timed out waiting for app-server response: mcpServerStatus/list")
            return self._payload
        raise AssertionError(f"Unexpected method: {method}")


class CodexMcpProbeTests(unittest.TestCase):
    def test_probe_reports_visible_servers_and_tools_from_rendered_codex_home(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            codex_home, snapshot = _prepare_codex_home(root, ["context7", "yunwu_image", "astrabridge_capabilities"])
            visible_payload = {
                "data": [
                    {
                        "name": "context7",
                        "tools": {
                            "resolve-library-id": {"name": "resolve-library-id"},
                            "get-library-docs": {"name": "get-library-docs"},
                        },
                        "authStatus": "not_configured",
                    },
                    {
                        "name": "yunwu_image",
                        "tools": {name: {"name": name} for name in _configured_tool_names(snapshot, "yunwu_image")},
                        "authStatus": {"state": "unauthenticated"},
                    },
                    {
                        "name": "astrabridge_capabilities",
                        "tools": {name: {"name": name} for name in _configured_tool_names(snapshot, "astrabridge_capabilities")},
                        "authStatus": {"state": "unknown"},
                    },
                ],
                "nextCursor": None,
            }

            report = probe_mcp_compatibility(
                codex_home=codex_home,
                mcp_config=snapshot,
                client_factory=lambda on_notification, on_server_request: _FakeMcpProbeClient("visible", visible_payload),
                artifact_root=root / "artifacts",
                request_timeout=1.0,
            )

            self.assertEqual(report["mcp"]["config_file_status"], "present")
            self.assertEqual(report["mcp"]["reload_status"], "supported")
            self.assertEqual(report["mcp"]["server_status_list_status"], "supported")
            self.assertEqual(report["mcp"]["config_visibility_status"], "visible")
            self.assertEqual(
                report["mcp"]["expected_servers"],
                ["astrabridge_capabilities", "context7", "yunwu_image"],
            )
            self.assertEqual(report["mcp"]["missing_servers"], [])
            self.assertEqual(report["mcp"]["missing_tools"], [])
            self.assertIn("astrabridge_capability_routes", report["mcp"]["expected_tools"])
            self.assertIn("yunwu_image_generate", report["mcp"]["visible_tools"])
            saved = json.loads(Path(report["report_path"]).read_text(encoding="utf-8"))
            self.assertEqual(saved["mcp"]["config_visibility_status"], "visible")

    def test_probe_reports_missing_when_codex_home_config_is_not_rendered(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            codex_home = root / "codex-home"
            codex_home.mkdir(parents=True, exist_ok=True)
            service = McpConfigService(root / "mcp_servers.json")
            service.apply_context7_preset()
            snapshot = service.snapshot()

            report = probe_mcp_compatibility(
                codex_home=codex_home,
                mcp_config=snapshot,
                artifact_root=root / "artifacts",
            )

            self.assertEqual(report["mcp"]["config_file_status"], "missing")
            self.assertEqual(report["mcp"]["config_render_status"], "error")
            self.assertEqual(report["mcp"]["config_visibility_status"], "missing")
            self.assertEqual(report["mcp"]["server_status_list_status"], "not_checked")
            self.assertEqual(report["mcp"]["missing_servers"], ["context7"])

    def test_probe_reports_malformed_config_without_starting_runtime_checks(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            codex_home = root / "codex-home"
            codex_home.mkdir(parents=True, exist_ok=True)
            (codex_home / "config.toml").write_text("[mcp_servers.context7\n", encoding="utf-8")
            service = McpConfigService(root / "mcp_servers.json")
            service.apply_context7_preset()
            snapshot = service.snapshot()

            report = probe_mcp_compatibility(
                codex_home=codex_home,
                mcp_config=snapshot,
                artifact_root=root / "artifacts",
            )

            self.assertEqual(report["mcp"]["config_file_status"], "malformed")
            self.assertEqual(report["mcp"]["config_render_status"], "error")
            self.assertEqual(report["mcp"]["config_visibility_status"], "malformed")
            self.assertEqual(report["mcp"]["reload_status"], "not_checked")
            self.assertEqual(report["mcp"]["server_status_list_status"], "not_checked")

    def test_probe_reports_partial_visibility_for_missing_servers_and_tools(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            codex_home, snapshot = _prepare_codex_home(root, ["context7", "yunwu_image", "astrabridge_capabilities"])
            capability_tools = _configured_tool_names(snapshot, "astrabridge_capabilities")
            visible_payload = {
                "data": [
                    {
                        "name": "astrabridge_capabilities",
                        "tools": {name: {"name": name} for name in capability_tools[:-1]},
                        "authStatus": {"state": "unknown"},
                    }
                ],
                "nextCursor": None,
            }

            report = probe_mcp_compatibility(
                codex_home=codex_home,
                mcp_config=snapshot,
                client_factory=lambda on_notification, on_server_request: _FakeMcpProbeClient("partial", visible_payload),
                artifact_root=root / "artifacts",
                request_timeout=1.0,
            )

            self.assertEqual(report["mcp"]["config_file_status"], "present")
            self.assertEqual(report["mcp"]["config_visibility_status"], "partial")
            self.assertEqual(report["mcp"]["missing_servers"], ["context7", "yunwu_image"])
            self.assertIn(capability_tools[-1], report["mcp"]["missing_tools"])
            capability_record = next(item for item in report["mcp"]["server_records"] if item["name"] == "astrabridge_capabilities")
            self.assertEqual(capability_record["visibility_status"], "partial")

    def test_probe_records_startup_notifications_when_status_list_times_out(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            codex_home, snapshot = _prepare_codex_home(root, ["astrabridge_capabilities"])

            report = probe_mcp_compatibility(
                codex_home=codex_home,
                mcp_config=snapshot,
                client_factory=lambda on_notification, on_server_request: _FakeMcpProbeClient(
                    "notify-startup-timeout",
                    {},
                    on_notification=on_notification,
                ),
                artifact_root=root / "artifacts",
                request_timeout=1.0,
            )

            self.assertEqual(report["mcp"]["server_status_list_status"], "timeout")
            self.assertIn("config/mcpServer/reload", report["mcp"]["request_sequence"])
            self.assertIn("thread/start", report["mcp"]["request_sequence"])
            self.assertIn("mcpServerStatus/list", report["mcp"]["request_sequence"])
            self.assertEqual(report["mcp"]["status_thread_id_observed"], "probe-thread")
            notifications = report["mcp"]["startup_notifications"]
            self.assertTrue(any(item.get("server") == "astrabridge_probe_fixture" for item in notifications))

    def test_probe_sends_thread_scoped_status_list_params(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            codex_home, snapshot = _prepare_codex_home(root, ["astrabridge_capabilities"])
            clients: list[_FakeMcpProbeClient] = []

            def factory(on_notification, on_server_request):  # noqa: ANN001, ARG001
                client = _FakeMcpProbeClient("success", {"data": []}, on_notification=on_notification)
                clients.append(client)
                return client

            probe_mcp_compatibility(
                codex_home=codex_home,
                mcp_config=snapshot,
                client_factory=factory,
                artifact_root=root / "artifacts",
                request_timeout=1.0,
            )

            self.assertEqual(clients[0].request_params[-1], ("mcpServerStatus/list", {"detail": "toolsAndAuthOnly", "threadId": "probe-thread"}))


def _prepare_codex_home(root: Path, presets: list[str]) -> tuple[Path, dict[str, object]]:
    service = McpConfigService(root / "mcp_servers.json")
    for preset in presets:
        if preset == "context7":
            service.apply_context7_preset()
        elif preset == "yunwu_image":
            service.apply_yunwu_image_preset()
        elif preset == "astrabridge_capabilities":
            service.apply_astrabridge_capabilities_preset()
        else:
            raise AssertionError(f"Unknown preset: {preset}")
    codex_home = root / "codex-home"
    codex_home.mkdir(parents=True, exist_ok=True)
    config_text = 'model = "demo"\n\n' + service.render_toml() + "\n"
    (codex_home / "config.toml").write_text(config_text, encoding="utf-8", newline="\n")
    return codex_home, service.snapshot()


def _configured_tool_names(snapshot: dict[str, object], server_name: str) -> list[str]:
    for server in list(snapshot.get("servers") or []):
        if isinstance(server, dict) and str(server.get("name") or "") == server_name:
            return sorted(str(name).strip() for name in dict(server.get("tools") or {}).keys() if str(name).strip())
    return []


if __name__ == "__main__":
    unittest.main()
