from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from astrabridge_sidecar.app_server_client import JsonRpcError
from astrabridge_sidecar.codex_plugin_probe import probe_plugin_discovery


class _FakePluginProbeClient:
    def __init__(self, scenario: str) -> None:
        self._scenario = scenario
        self.requests: list[str] = []
        self.closed = False

    def start(self) -> None:
        return None

    def close(self) -> None:
        self.closed = True

    def request(self, method: str, params=None, timeout: float = 120.0):  # noqa: ARG002
        self.requests.append(method)
        if self._scenario == "unsupported":
            raise JsonRpcError("Method not found", code=-32601)
        if self._scenario == "timeout":
            raise TimeoutError(f"Timed out waiting for app-server response: {method}")
        if self._scenario == "empty":
            if method in {"plugin/list", "plugin/installed"}:
                return {"marketplaces": [], "marketplaceLoadErrors": [], "featuredPluginIds": []}
            raise AssertionError(f"Unexpected method: {method}")
        if self._scenario == "installed":
            if method == "plugin/list":
                return {
                    "marketplaces": [
                        {
                            "name": "personal",
                            "path": "D:/isolated/.agents/plugins/marketplace.json",
                            "plugins": [
                                {
                                    "id": "demo-plugin",
                                    "name": "demo-plugin",
                                    "localVersion": "1.2.3",
                                    "installed": False,
                                    "enabled": False,
                                    "installPolicy": "AVAILABLE",
                                    "authPolicy": "ON_INSTALL",
                                    "availability": "AVAILABLE",
                                    "source": {"type": "local", "path": "D:/isolated/.agents/plugins/plugins/demo-plugin"},
                                    "interface": {
                                        "displayName": "Demo Plugin",
                                        "shortDescription": "Local plugin catalog entry.",
                                    },
                                    "keywords": ["demo"],
                                }
                            ],
                        }
                    ],
                    "marketplaceLoadErrors": [],
                    "featuredPluginIds": ["demo-plugin"],
                }
            if method == "plugin/installed":
                return {
                    "marketplaces": [
                        {
                            "name": "personal",
                            "path": "D:/isolated/.agents/plugins/marketplace.json",
                            "plugins": [
                                {
                                    "id": "demo-plugin",
                                    "name": "demo-plugin",
                                    "localVersion": "1.2.3",
                                    "installed": True,
                                    "enabled": True,
                                    "installPolicy": "AVAILABLE",
                                    "authPolicy": "ON_INSTALL",
                                    "availability": "AVAILABLE",
                                    "source": {"type": "local", "path": "D:/isolated/.agents/plugins/plugins/demo-plugin"},
                                    "interface": {
                                        "displayName": "Demo Plugin",
                                        "shortDescription": "Installed plugin.",
                                    },
                                    "keywords": ["demo"],
                                }
                            ],
                        }
                    ],
                    "marketplaceLoadErrors": [],
                }
            if method == "plugin/read":
                return {
                    "plugin": {
                        "marketplaceName": "personal",
                        "marketplacePath": "D:/isolated/.agents/plugins/marketplace.json",
                        "summary": {
                            "id": "demo-plugin",
                            "name": "demo-plugin",
                            "interface": {"displayName": "Demo Plugin"},
                        },
                        "description": "Detailed plugin description.",
                        "skills": [{"name": "demo-skill"}],
                        "apps": [{"id": "demo-app"}],
                        "mcpServers": ["demo_mcp"],
                    }
                }
            raise AssertionError(f"Unexpected method: {method}")
        raise AssertionError(f"Unknown scenario: {self._scenario}")


class CodexPluginProbeTests(unittest.TestCase):
    def test_probe_distinguishes_unsupported_plugin_commands(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            codex_home = _write_codex_home(root, plugins_enabled=True)

            report = probe_plugin_discovery(
                codex_home=codex_home,
                client_factory=lambda on_notification, on_server_request: _FakePluginProbeClient("unsupported"),
                artifact_root=root / "artifacts",
                request_timeout=1.0,
            )

            self.assertEqual(report["plugin"]["config_feature_state"], "enabled")
            self.assertEqual(report["plugin"]["list_status"], "unsupported")
            self.assertEqual(report["plugin"]["installed_status"], "unsupported")
            self.assertEqual(report["plugin"]["read_status"], "skipped")
            self.assertEqual(report["plugin"]["discovered_plugins"], [])

    def test_probe_distinguishes_supported_empty_catalog(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            codex_home = _write_codex_home(root, plugins_enabled=True)

            report = probe_plugin_discovery(
                codex_home=codex_home,
                client_factory=lambda on_notification, on_server_request: _FakePluginProbeClient("empty"),
                artifact_root=root / "artifacts",
                request_timeout=1.0,
            )

            self.assertEqual(report["plugin"]["list_status"], "supported")
            self.assertEqual(report["plugin"]["installed_status"], "supported")
            self.assertEqual(report["plugin"]["read_status"], "skipped")
            self.assertEqual(report["plugin"]["marketplace_status"], "empty")
            self.assertEqual(report["plugin"]["manifest_fallback_status"], "empty")
            self.assertEqual(report["plugin"]["discovered_plugins"], [])

    def test_probe_reports_installed_plugin_list_and_detail(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            codex_home = _write_codex_home(root, plugins_enabled=True)

            report = probe_plugin_discovery(
                codex_home=codex_home,
                client_factory=lambda on_notification, on_server_request: _FakePluginProbeClient("installed"),
                artifact_root=root / "artifacts",
                request_timeout=1.0,
            )

            self.assertEqual(report["plugin"]["list_status"], "supported")
            self.assertEqual(report["plugin"]["installed_status"], "supported")
            self.assertEqual(report["plugin"]["read_status"], "supported")
            self.assertEqual(report["plugin"]["marketplace_status"], "supported")
            self.assertEqual(report["plugin"]["featured_plugin_ids"], ["demo-plugin"])
            plugin = report["plugin"]["discovered_plugins"][0]
            self.assertEqual(plugin["plugin_id"], "demo-plugin")
            self.assertEqual(plugin["availability"], "installed")
            self.assertEqual(plugin["source_kind"], "local_marketplace")
            self.assertEqual(plugin["skills"], ["demo-skill"])
            self.assertEqual(plugin["apps"], ["demo-app"])
            self.assertEqual(plugin["mcp_servers"], ["demo_mcp"])

    def test_probe_distinguishes_malformed_plugin_manifest_from_local_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            codex_home = _write_codex_home(root, plugins_enabled=False)
            isolated_plugins_root = root / "isolated-marketplace"
            marketplace_path = isolated_plugins_root / ".agents" / "plugins" / "marketplace.json"
            plugin_root = marketplace_path.parent / "plugins" / "demo-plugin"
            (plugin_root / ".codex-plugin").mkdir(parents=True, exist_ok=True)
            marketplace_path.parent.mkdir(parents=True, exist_ok=True)
            marketplace_path.write_text(
                json.dumps(
                    {
                        "name": "personal",
                        "plugins": [
                            {
                                "name": "demo-plugin",
                                "source": {"source": "local", "path": "./plugins/demo-plugin"},
                                "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
                                "category": "Productivity",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            (plugin_root / ".codex-plugin" / "plugin.json").write_text("{bad json", encoding="utf-8")

            report = probe_plugin_discovery(
                codex_home=codex_home,
                local_search_roots=[isolated_plugins_root],
                artifact_root=root / "artifacts",
            )

            self.assertEqual(report["plugin"]["config_feature_state"], "disabled_by_app")
            self.assertEqual(report["plugin"]["marketplace_status"], "manifest_fallback")
            self.assertEqual(report["plugin"]["manifest_fallback_status"], "malformed")
            self.assertTrue(report["plugin"]["malformed_manifest_paths"])
            plugin = report["plugin"]["discovered_plugins"][0]
            self.assertEqual(plugin["plugin_id"], "demo-plugin")
            self.assertEqual(plugin["manifest_status"], "malformed")

    def test_probe_distinguishes_plugin_command_timeout(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            codex_home = _write_codex_home(root, plugins_enabled=True)

            report = probe_plugin_discovery(
                codex_home=codex_home,
                client_factory=lambda on_notification, on_server_request: _FakePluginProbeClient("timeout"),
                artifact_root=root / "artifacts",
                request_timeout=1.0,
            )

            self.assertEqual(report["plugin"]["list_status"], "timeout")
            self.assertEqual(report["plugin"]["installed_status"], "timeout")
            self.assertEqual(report["plugin"]["read_status"], "skipped")
            self.assertEqual(report["plugin"]["marketplace_status"], "empty")


def _write_codex_home(root: Path, *, plugins_enabled: bool) -> Path:
    codex_home = root / "codex-home"
    codex_home.mkdir(parents=True, exist_ok=True)
    config_text = "\n".join(
        [
            'model = "demo"',
            "",
            "[features]",
            f"plugins = {'true' if plugins_enabled else 'false'}",
            "plugin_sharing = false",
            "remote_plugin = false",
            "",
        ]
    )
    (codex_home / "config.toml").write_text(config_text, encoding="utf-8", newline="\n")
    return codex_home


if __name__ == "__main__":
    unittest.main()
