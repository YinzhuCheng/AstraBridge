from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from astrabridge_sidecar.codex_plugin_fixture_catalog import materialize_controlled_plugin_fixture_catalog
from astrabridge_sidecar.codex_plugin_probe import probe_plugin_discovery
from astrabridge_sidecar.runtime_service import RuntimeService


PLUGIN_ID = "astrabridge-dogfood-fixture"


def _write_codex_home(root: Path) -> Path:
    codex_home = root / "codex-home"
    codex_home.mkdir(parents=True, exist_ok=True)
    (codex_home / "config.toml").write_text(
        "\n".join(
            [
                'model = "demo"',
                "",
                "[features]",
                "plugins = true",
                "plugin_sharing = false",
                "remote_plugin = false",
                "",
            ]
        ),
        encoding="utf-8",
        newline="\n",
    )
    return codex_home


class RealScenarioPluginFixtureRuntimeInstallTests(unittest.TestCase):
    def test_materialize_fixture_catalog_moves_plugin_count_from_zero_to_available(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace_root = root / "workspace"
            shell_root = workspace_root / ".astrabridge"
            shell_root.mkdir(parents=True, exist_ok=True)
            codex_home = _write_codex_home(root)

            before = probe_plugin_discovery(
                codex_home=codex_home,
                local_search_roots=[shell_root],
                artifact_root=root / "artifacts-before",
            )
            self.assertEqual(before["plugin"]["discovered_plugins"], [])

            first = materialize_controlled_plugin_fixture_catalog(shell_root)
            second = materialize_controlled_plugin_fixture_catalog(shell_root)

            self.assertEqual(first["status"], "materialized")
            self.assertEqual(second["status"], "reused")
            self.assertTrue(str(first["search_root"]).startswith(str(shell_root.resolve())))

            after = probe_plugin_discovery(
                codex_home=codex_home,
                local_search_roots=[shell_root],
                artifact_root=root / "artifacts-after",
            )
            plugin = next(item for item in after["plugin"]["discovered_plugins"] if item["plugin_id"] == PLUGIN_ID)

            self.assertEqual(plugin["availability"], "available")
            self.assertEqual(plugin["source_kind"], "local_marketplace")
            self.assertEqual(plugin["manifest_status"], "ok")

    def test_runtime_install_apply_is_idempotent_and_stays_inside_isolated_codex_home(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace_root = root / "workspace"
            shell_root = workspace_root / ".astrabridge"
            project_runtime_root = shell_root / "runtime"
            shell_root.mkdir(parents=True, exist_ok=True)
            project_runtime_root.mkdir(parents=True, exist_ok=True)
            codex_home = _write_codex_home(root)
            events: list[dict[str, object]] = []

            runtime = RuntimeService.__new__(RuntimeService)
            runtime._prepare_runtime = lambda profile, require_secret=False: {"codex_home": str(codex_home)}  # type: ignore[attr-defined]
            runtime._kernel_probe_app_server_status = lambda runtime_status: ({}, None, [])  # type: ignore[attr-defined]
            runtime._record_event = lambda payload: events.append(dict(payload))  # type: ignore[attr-defined]

            class Projects:
                @staticmethod
                def require_workspace_root() -> Path:
                    return workspace_root

                @staticmethod
                def require_shell_state_root() -> Path:
                    return shell_root

                @staticmethod
                def current_runtime_roots() -> dict[str, Path]:
                    return {
                        "project_runtime_root": project_runtime_root,
                        "workspace_runtime_cwd": workspace_root,
                        "codex_home_root": codex_home,
                    }

            runtime._projects = Projects()  # type: ignore[attr-defined]

            initial_snapshot = runtime.plugin_skill_registry_snapshot({"profile_id": "demo-profile"})
            initial_plugin = next(item for item in initial_snapshot["plugins"] if item["plugin_id"] == PLUGIN_ID)
            self.assertEqual(initial_plugin["install_status"], "available")
            self.assertEqual(initial_snapshot["skills"], [])

            first_apply = runtime.plugin_install_apply({"profile_id": "demo-profile"}, plugin_id=PLUGIN_ID)
            self.assertEqual(first_apply["status"], "applied")
            self.assertTrue(str(first_apply["target_root"]).startswith(str(codex_home.resolve())))
            self.assertTrue((codex_home / "plugins" / PLUGIN_ID / ".codex-plugin" / "plugin.json").exists())

            installed_snapshot = runtime.plugin_skill_registry_snapshot({"profile_id": "demo-profile"})
            installed_plugin = next(item for item in installed_snapshot["plugins"] if item["plugin_id"] == PLUGIN_ID)
            self.assertEqual(installed_plugin["install_status"], "installed")

            second_apply = runtime.plugin_install_apply({"profile_id": "demo-profile"}, plugin_id=PLUGIN_ID)
            self.assertEqual(second_apply["status"], "noop")
            self.assertEqual(second_apply["action"], "noop")
            self.assertTrue(any(event.get("type") == "plugin_install_apply_finished" for event in events))


if __name__ == "__main__":
    unittest.main()
