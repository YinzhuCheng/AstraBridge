from __future__ import annotations

import sys
import unittest
from pathlib import Path
from tempfile import mkdtemp
from typing import Any
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from astrabridge_sidecar import runtime_service as runtime_service_module
from astrabridge_sidecar.runtime_service import RuntimeService
from astrabridge_sidecar.server import Handler


def _runtime_for_registry() -> tuple[RuntimeService, list[dict[str, Any]]]:
    runtime = RuntimeService.__new__(RuntimeService)
    events: list[dict[str, Any]] = []
    codex_home = Path(mkdtemp()) / "codex-home"
    runtime._prepare_runtime = lambda profile, require_secret=False: {"codex_home": str(codex_home)}  # type: ignore[attr-defined]
    runtime._kernel_probe_app_server_status = lambda runtime_status: ({}, None, [])  # type: ignore[attr-defined]
    runtime._kernel_probe_search_roots = lambda: [Path("D:/AstraBridge/.astrabridge/shell"), Path("D:/AstraBridge")]  # type: ignore[attr-defined]
    runtime._kernel_probe_runtime_roots = lambda runtime_status: {  # type: ignore[attr-defined]
        "project_runtime_root": "D:/AstraBridge",
        "workspace_runtime_cwd": "D:/AstraBridge",
        "codex_home_root": str(codex_home),
    }
    runtime._record_event = lambda payload: events.append(dict(payload))  # type: ignore[attr-defined]
    return runtime, events


class PluginSkillRegistryRuntimeTests(unittest.TestCase):
    def test_runtime_registry_snapshot_handles_empty_inventory(self) -> None:
        runtime, events = _runtime_for_registry()
        plugin_report = {"plugin": {"list_status": "supported", "installed_status": "supported", "read_status": "skipped", "marketplace_status": "empty", "manifest_fallback_status": "empty", "discovered_plugins": [], "notes": []}, "known_warnings": []}
        skill_report = {"skill": {"list_status": "supported", "extra_roots_status": "declared", "config_write_status": "declared", "change_notification_status": "declared", "discovered_skills": [], "duplicate_skill_names": [], "malformed_skill_paths": [], "missing_description_paths": [], "notes": []}, "known_warnings": []}
        with patch.object(runtime_service_module, "probe_plugin_discovery", return_value=plugin_report), patch.object(runtime_service_module, "probe_skill_discovery", return_value=skill_report):
            snapshot = runtime.plugin_skill_registry_snapshot({"profile_id": "demo-profile"})

        self.assertEqual(snapshot["schema_version"], "astrabridge-plugin-skill-registry-v1")
        self.assertEqual(snapshot["plugins"], [])
        self.assertEqual(snapshot["skills"], [])
        self.assertTrue(any(event.get("type") == "plugin_skill_registry_snapshot_built" for event in events))

    def test_runtime_registry_snapshot_includes_fixture_plugin_and_skill(self) -> None:
        runtime, _events = _runtime_for_registry()
        plugin_report = {
            "plugin": {
                "list_status": "supported",
                "installed_status": "supported",
                "read_status": "supported",
                "marketplace_status": "used",
                "manifest_fallback_status": "used",
                "discovered_plugins": [
                    {
                        "plugin_id": "demo-plugin",
                        "display_name": "Demo Plugin",
                        "version": "1.2.3",
                        "source_kind": "installed_root",
                        "availability": "installed",
                        "manifest_status": "ok",
                        "manifest_path": "D:/AstraBridge/.astrabridge/shell/plugins/demo-plugin/.codex-plugin/plugin.json",
                        "description": "Demo plugin description",
                        "apps_declared": ["demo-app"],
                        "mcp_servers_declared": ["demo-mcp"],
                        "skills_declared": ["demo-plugin-skill"],
                        "enabled": True,
                    }
                ],
                "notes": [],
            },
            "known_warnings": [],
        }
        skill_report = {
            "skill": {
                "list_status": "supported",
                "extra_roots_status": "declared",
                "config_write_status": "declared",
                "change_notification_status": "declared",
                "discovered_skills": [
                    {
                        "skill_name": "demo-plugin-skill",
                        "display_name": "demo-plugin-skill",
                        "description": "Trigger on plugin tasks.",
                        "description_status": "present",
                        "source_kind": "plugin",
                        "owner_plugin_id": "demo-plugin",
                        "enablement": "enabled",
                        "path": "D:/AstraBridge/.astrabridge/shell/plugins/demo-plugin/skills/demo-plugin-skill/SKILL.md",
                        "trigger_hints": ["plugin tasks"],
                        "version_hint": "1.2.3",
                        "manifest_status": "ok",
                        "dependency_tools": ["tool_search"],
                    }
                ],
                "duplicate_skill_names": [],
                "malformed_skill_paths": [],
                "missing_description_paths": [],
                "notes": ["plugin_skills_detected"],
            },
            "known_warnings": [],
        }
        with patch.object(runtime_service_module, "probe_plugin_discovery", return_value=plugin_report), patch.object(runtime_service_module, "probe_skill_discovery", return_value=skill_report):
            snapshot = runtime.plugin_skill_registry_snapshot({"profile_id": "demo-profile"})

        self.assertEqual(len(snapshot["plugins"]), 1)
        self.assertEqual(len(snapshot["skills"]), 1)
        plugin = snapshot["plugins"][0]
        skill = snapshot["skills"][0]
        self.assertEqual(plugin["plugin_id"], "demo-plugin")
        self.assertEqual(plugin["install_status"], "installed")
        self.assertIn("declares_mcp_servers", plugin["permission_hints"])
        self.assertEqual(skill["owner_plugin_id"], "demo-plugin")
        self.assertEqual(skill["source_catalog_id"], plugin["source_catalog_id"])

    def test_runtime_registry_snapshot_marks_malformed_metadata(self) -> None:
        runtime, _events = _runtime_for_registry()
        plugin_report = {
            "plugin": {
                "list_status": "supported",
                "installed_status": "supported",
                "read_status": "skipped",
                "marketplace_status": "used",
                "manifest_fallback_status": "malformed",
                "discovered_plugins": [
                    {
                        "plugin_id": "broken-plugin",
                        "display_name": "Broken Plugin",
                        "source_kind": "local_marketplace",
                        "availability": "available",
                        "manifest_status": "malformed",
                        "manifest_path": "D:/AstraBridge/.astrabridge/shell/plugins/broken-plugin/.codex-plugin/plugin.json",
                    }
                ],
                "notes": [],
            },
            "known_warnings": [],
        }
        skill_report = {
            "skill": {
                "list_status": "supported",
                "extra_roots_status": "declared",
                "config_write_status": "declared",
                "change_notification_status": "declared",
                "discovered_skills": [
                    {
                        "skill_name": "broken-skill",
                        "display_name": "broken-skill",
                        "description": None,
                        "description_status": "missing",
                        "source_kind": "local_skill_root",
                        "enablement": "unknown",
                        "path": "D:/AstraBridge/.astrabridge/shell/skills/broken-skill/SKILL.md",
                        "manifest_status": "malformed",
                        "dependency_tools": [],
                    }
                ],
                "duplicate_skill_names": [],
                "malformed_skill_paths": ["D:/AstraBridge/.astrabridge/shell/skills/broken-skill/SKILL.md"],
                "missing_description_paths": ["D:/AstraBridge/.astrabridge/shell/skills/broken-skill/SKILL.md"],
                "notes": [],
            },
            "known_warnings": [],
        }
        with patch.object(runtime_service_module, "probe_plugin_discovery", return_value=plugin_report), patch.object(runtime_service_module, "probe_skill_discovery", return_value=skill_report):
            snapshot = runtime.plugin_skill_registry_snapshot({"profile_id": "demo-profile"})

        plugin = snapshot["plugins"][0]
        skill = snapshot["skills"][0]
        self.assertEqual(plugin["install_status"], "malformed")
        self.assertEqual(plugin["compatibility_warnings"][0]["code"], "plugin-manifest-malformed")
        self.assertEqual(skill["install_status"], "malformed")
        self.assertEqual(skill["compatibility_warnings"][0]["code"], "skill-manifest-malformed")

    def test_runtime_registry_snapshot_dedupes_duplicate_plugin_ids(self) -> None:
        runtime, _events = _runtime_for_registry()
        plugin_report = {
            "plugin": {
                "list_status": "supported",
                "installed_status": "supported",
                "read_status": "supported",
                "marketplace_status": "used",
                "manifest_fallback_status": "used",
                "discovered_plugins": [
                    {"plugin_id": "dup-plugin", "display_name": "Dup Plugin", "source_kind": "local_marketplace", "availability": "available", "manifest_status": "ok", "manifest_path": "D:/AstraBridge/.astrabridge/shell/marketplace/dup-plugin/.codex-plugin/plugin.json"},
                    {"plugin_id": "dup-plugin", "display_name": "Dup Plugin", "source_kind": "installed_root", "availability": "installed", "manifest_status": "ok", "manifest_path": "D:/AstraBridge/.astrabridge/shell/plugins/dup-plugin/.codex-plugin/plugin.json", "enabled": True},
                ],
                "notes": [],
            },
            "known_warnings": [],
        }
        skill_report = {"skill": {"list_status": "supported", "extra_roots_status": "declared", "config_write_status": "declared", "change_notification_status": "declared", "discovered_skills": [], "duplicate_skill_names": [], "malformed_skill_paths": [], "missing_description_paths": [], "notes": []}, "known_warnings": []}
        with patch.object(runtime_service_module, "probe_plugin_discovery", return_value=plugin_report), patch.object(runtime_service_module, "probe_skill_discovery", return_value=skill_report):
            snapshot = runtime.plugin_skill_registry_snapshot({"profile_id": "demo-profile"})

        self.assertEqual(len(snapshot["plugins"]), 1)
        self.assertEqual(snapshot["plugins"][0]["install_status"], "installed")
        self.assertIn("plugin_duplicate_ids:dup-plugin", snapshot["notes"])

    def test_runtime_registry_snapshot_reports_unsupported_feature_status(self) -> None:
        runtime, _events = _runtime_for_registry()
        plugin_report = {"plugin": {"list_status": "unsupported", "installed_status": "unsupported", "read_status": "unsupported", "marketplace_status": "not_checked", "manifest_fallback_status": "empty", "discovered_plugins": [], "notes": []}, "known_warnings": []}
        skill_report = {"skill": {"list_status": "unsupported", "extra_roots_status": "declared", "config_write_status": "declared", "change_notification_status": "unsupported", "discovered_skills": [], "duplicate_skill_names": [], "malformed_skill_paths": [], "missing_description_paths": [], "notes": []}, "known_warnings": []}
        with patch.object(runtime_service_module, "probe_plugin_discovery", return_value=plugin_report), patch.object(runtime_service_module, "probe_skill_discovery", return_value=skill_report):
            snapshot = runtime.plugin_skill_registry_snapshot({"profile_id": "demo-profile"})

        self.assertEqual(snapshot["plugins"], [])
        self.assertEqual(snapshot["skills"], [])
        self.assertIn("plugin_list_status:unsupported", snapshot["notes"])
        self.assertIn("skill_list_status:unsupported", snapshot["notes"])


class PluginSkillRegistryRouteTests(unittest.TestCase):
    def test_handler_runtime_plugin_skill_registry_route_returns_snapshot(self) -> None:
        handler = Handler.__new__(Handler)
        captured: dict[str, Any] = {}

        class Runtime:
            def __init__(self) -> None:
                self.profiles: list[dict[str, Any]] = []

            def plugin_skill_registry_snapshot(self, profile: dict[str, Any]) -> dict[str, Any]:
                self.profiles.append(profile)
                return {
                    "schema_version": "astrabridge-plugin-skill-registry-v1",
                    "generated_at": "2026-06-25T12:34:56+08:00",
                    "source_catalogs": [],
                    "plugins": [],
                    "skills": [],
                    "notes": [],
                }

        class Context:
            runtime = Runtime()

        handler.context = Context()  # type: ignore[assignment]
        handler.path = "/api/runtime/plugin-skill-registry?profile_id=test-profile"  # type: ignore[assignment]
        handler.send_json = lambda payload, status=200: captured.update({"payload": payload, "status": status})  # type: ignore[assignment]
        handler._resolve_runtime_profile = lambda profile_id: {"profile_id": profile_id or "resolved-profile"}  # type: ignore[assignment]

        Handler.do_GET(handler)

        self.assertEqual(captured["status"], 200)
        self.assertEqual(captured["payload"]["schema_version"], "astrabridge-plugin-skill-registry-v1")
        self.assertEqual(handler.context.runtime.profiles, [{"profile_id": "test-profile"}])  # type: ignore[attr-defined]


if __name__ == "__main__":
    unittest.main()
