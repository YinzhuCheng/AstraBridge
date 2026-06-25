from __future__ import annotations

import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from astrabridge_sidecar import runtime_service as runtime_service_module
from astrabridge_sidecar.codex_skill_enablement import (
    apply_skill_enablement_snapshot,
    register_pending_skill_approval_rules,
)
from astrabridge_sidecar.runtime_service import RuntimeService
from astrabridge_sidecar.server import Handler


def _runtime_for_skill_enablement(root: Path) -> tuple[RuntimeService, list[dict[str, Any]], Path, Path]:
    runtime = RuntimeService.__new__(RuntimeService)
    events: list[dict[str, Any]] = []
    codex_home = (root / "codex-home").resolve()
    workspace = (root / "workspace").resolve()
    codex_home.mkdir(parents=True, exist_ok=True)
    workspace.mkdir(parents=True, exist_ok=True)

    class Projects:
        current_project = {"project_id": "demo-project"}

        def require_workspace_root(self) -> Path:
            return workspace

    runtime._projects = Projects()  # type: ignore[attr-defined]
    runtime._prepare_runtime = lambda profile, require_secret=False: {"codex_home": str(codex_home)}  # type: ignore[attr-defined]
    runtime._kernel_probe_app_server_status = lambda runtime_status: ({}, None, [])  # type: ignore[attr-defined]
    runtime._kernel_probe_search_roots = lambda: [root]  # type: ignore[attr-defined]
    runtime._kernel_probe_runtime_roots = lambda runtime_status: {  # type: ignore[attr-defined]
        "project_runtime_root": str(root / "runtime"),
        "workspace_runtime_cwd": str(workspace),
        "codex_home_root": str(codex_home),
    }
    runtime._record_event = lambda payload: events.append(dict(payload))  # type: ignore[attr-defined]
    return runtime, events, codex_home, workspace


def _plugin_report(*, include_second_plugin: bool = False, availability: str = "installed") -> dict[str, Any]:
    plugins = [
        {
            "plugin_id": "github",
            "display_name": "GitHub",
            "version": "0.1.5",
            "source_kind": "installed_root",
            "availability": availability,
            "manifest_status": "ok",
            "manifest_path": "D:/AstraBridge/.astrabridge/codex-home/plugins/github/.codex-plugin/plugin.json",
            "description": "GitHub plugin.",
            "enabled": availability == "installed",
        }
    ]
    if include_second_plugin:
        plugins.append(
            {
                "plugin_id": "legacy-helper",
                "display_name": "Legacy Helper",
                "version": "0.0.9",
                "source_kind": "installed_root",
                "availability": "installed",
                "manifest_status": "ok",
                "manifest_path": "D:/AstraBridge/.astrabridge/codex-home/plugins/legacy-helper/.codex-plugin/plugin.json",
                "description": "Legacy helper plugin.",
                "enabled": True,
            }
        )
    return {
        "plugin": {
            "list_status": "supported",
            "installed_status": "supported",
            "read_status": "supported",
            "marketplace_status": "used",
            "manifest_fallback_status": "used",
            "discovered_plugins": plugins,
            "notes": [],
        },
        "known_warnings": [],
    }


def _skill_report(records: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "skill": {
            "list_status": "supported",
            "extra_roots_status": "declared",
            "config_write_status": "declared",
            "change_notification_status": "declared",
            "discovered_skills": records,
            "duplicate_skill_names": [],
            "malformed_skill_paths": [],
            "missing_description_paths": [],
            "notes": [],
        },
        "known_warnings": [],
    }


class SkillEnablementRuntimeTests(unittest.TestCase):
    def test_runtime_skill_enablement_persists_global_and_project_settings(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            runtime, events, codex_home, workspace = _runtime_for_skill_enablement(root)
            skill_report = _skill_report(
                [
                    {
                        "skill_name": "github:gh-address-comments",
                        "display_name": "Address comments",
                        "description": "Address pull request comments.",
                        "description_status": "present",
                        "source_kind": "plugin",
                        "owner_plugin_id": "github",
                        "enablement": "enabled",
                        "path": "D:/AstraBridge/.astrabridge/codex-home/plugins/github/skills/gh-address-comments/SKILL.md",
                        "trigger_hints": ["pull request review"],
                        "version_hint": "0.1.5",
                        "manifest_status": "ok",
                        "dependency_tools": ["tool_search"],
                    }
                ]
            )
            with patch.object(runtime_service_module, "probe_plugin_discovery", return_value=_plugin_report()), patch.object(
                runtime_service_module, "probe_skill_discovery", return_value=skill_report
            ):
                initial = runtime.plugin_skill_registry_snapshot({"profile_id": "demo-profile"})
                skill = initial["skills"][0]
                self.assertEqual(skill["enablement_status"], "enabled")

                globally_disabled = runtime.skill_enablement_update(
                    {"profile_id": "demo-profile"},
                    record_id=skill["record_id"],
                    scope="global",
                    enablement_status="disabled",
                )
                disabled_skill = globally_disabled["skills"][0]
                self.assertEqual(disabled_skill["global_enablement_status"], "disabled")
                self.assertEqual(disabled_skill["project_enablement_status"], "inherited")
                self.assertEqual(disabled_skill["enablement_status"], "disabled")

                project_enabled = runtime.skill_enablement_update(
                    {"profile_id": "demo-profile"},
                    record_id=skill["record_id"],
                    scope="project",
                    enablement_status="enabled",
                )
                enabled_skill = project_enabled["skills"][0]
                self.assertEqual(enabled_skill["project_enablement_status"], "enabled")
                self.assertEqual(enabled_skill["enablement_status"], "enabled")

                inherited_again = runtime.skill_enablement_update(
                    {"profile_id": "demo-profile"},
                    record_id=skill["record_id"],
                    scope="project",
                    enablement_status="inherited",
                )
                inherited_skill = inherited_again["skills"][0]
                self.assertEqual(inherited_skill["project_enablement_status"], "inherited")
                self.assertEqual(inherited_skill["enablement_status"], "disabled")
                self.assertTrue((codex_home / "astrabridge-managed" / "skill-enablement.global.json").is_file())
                self.assertTrue((workspace / ".astrabridge" / "extensions" / "skill-enablement.json").is_file())
                self.assertTrue(any(event.get("type") == "skill_enablement_updated" for event in events))

    def test_runtime_skill_enablement_targets_duplicate_skill_names_independently(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            runtime, _events, _codex_home, _workspace = _runtime_for_skill_enablement(root)
            shared_name = "shared-review"
            skill_report = _skill_report(
                [
                    {
                        "skill_name": shared_name,
                        "display_name": "Shared review",
                        "description": "GitHub review helper.",
                        "description_status": "present",
                        "source_kind": "plugin",
                        "owner_plugin_id": "github",
                        "enablement": "enabled",
                        "path": "D:/AstraBridge/.astrabridge/codex-home/plugins/github/skills/shared-review/SKILL.md",
                        "trigger_hints": ["github"],
                        "version_hint": "0.1.5",
                        "manifest_status": "ok",
                        "dependency_tools": ["tool_search"],
                    },
                    {
                        "skill_name": shared_name,
                        "display_name": "Shared review",
                        "description": "Legacy review helper.",
                        "description_status": "present",
                        "source_kind": "plugin",
                        "owner_plugin_id": "legacy-helper",
                        "enablement": "enabled",
                        "path": "D:/AstraBridge/.astrabridge/codex-home/plugins/legacy-helper/skills/shared-review/SKILL.md",
                        "trigger_hints": ["legacy"],
                        "version_hint": "0.0.9",
                        "manifest_status": "ok",
                        "dependency_tools": ["tool_search"],
                    },
                ]
            )
            with patch.object(runtime_service_module, "probe_plugin_discovery", return_value=_plugin_report(include_second_plugin=True)), patch.object(
                runtime_service_module, "probe_skill_discovery", return_value=skill_report
            ):
                snapshot = runtime.plugin_skill_registry_snapshot({"profile_id": "demo-profile"})
                first_record_id = snapshot["skills"][0]["record_id"]
                updated = runtime.skill_enablement_update(
                    {"profile_id": "demo-profile"},
                    record_id=first_record_id,
                    scope="global",
                    enablement_status="disabled",
                )

                by_id = {item["record_id"]: item for item in updated["skills"]}
                self.assertEqual(by_id[first_record_id]["enablement_status"], "disabled")
                sibling = next(item for item in updated["skills"] if item["record_id"] != first_record_id)
                self.assertEqual(sibling["enablement_status"], "enabled")

    def test_runtime_skill_enablement_blocks_unavailable_owner_plugin_and_rejects_enable(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            runtime, _events, _codex_home, _workspace = _runtime_for_skill_enablement(root)
            skill_report = _skill_report(
                [
                    {
                        "skill_name": "github:gh-address-comments",
                        "display_name": "Address comments",
                        "description": "Address pull request comments.",
                        "description_status": "present",
                        "source_kind": "plugin",
                        "owner_plugin_id": "github",
                        "enablement": "enabled",
                        "path": "D:/AstraBridge/.astrabridge/codex-home/plugins/github/skills/gh-address-comments/SKILL.md",
                        "trigger_hints": ["pull request review"],
                        "version_hint": "0.1.5",
                        "manifest_status": "ok",
                        "dependency_tools": ["tool_search"],
                    }
                ]
            )
            with patch.object(runtime_service_module, "probe_plugin_discovery", return_value=_plugin_report(availability="available")), patch.object(
                runtime_service_module, "probe_skill_discovery", return_value=skill_report
            ):
                snapshot = runtime.plugin_skill_registry_snapshot({"profile_id": "demo-profile"})
                skill = snapshot["skills"][0]
                self.assertEqual(skill["enablement_status"], "blocked")
                self.assertEqual(skill["compatibility_warnings"][-1]["code"], "skill-owning-plugin-unavailable")
                with self.assertRaisesRegex(ValueError, "not installed in the current runtime lane"):
                    runtime.skill_enablement_update(
                        {"profile_id": "demo-profile"},
                        record_id=skill["record_id"],
                        scope="global",
                        enablement_status="enabled",
                    )

    def test_pending_skill_rules_keep_new_skills_disabled_until_approved(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            codex_home = (root / "codex-home").resolve()
            workspace = (root / "workspace").resolve()
            codex_home.mkdir(parents=True, exist_ok=True)
            workspace.mkdir(parents=True, exist_ok=True)
            register_pending_skill_approval_rules(
                codex_home=codex_home,
                plugin_id="github",
                source_catalog_id="official::github",
                skill_names=["github:gh-address-comments"],
            )
            snapshot = apply_skill_enablement_snapshot(
                registry_snapshot={
                    "schema_version": "astrabridge-plugin-skill-registry-v1",
                    "generated_at": "2026-06-25T20:20:00+08:00",
                    "source_catalogs": [
                        {
                            "schema_version": "astrabridge-plugin-skill-source-catalog-v1",
                            "source_catalog_id": "official::github",
                            "kind": "official",
                            "display_name": "Official GitHub",
                            "writable": False,
                        }
                    ],
                    "plugins": [
                        {
                            "schema_version": "astrabridge-plugin-registry-record-v1",
                            "record_id": "plugin::github",
                            "plugin_id": "github",
                            "source_catalog_id": "official::github",
                            "display_name": "GitHub",
                            "install_status": "installed",
                            "enablement_status": "enabled",
                            "compatibility_status": "compatible",
                        }
                    ],
                    "skills": [
                        {
                            "schema_version": "astrabridge-skill-registry-record-v1",
                            "record_id": "skill::github:gh-address-comments::abc123",
                            "skill_name": "github:gh-address-comments",
                            "source_catalog_id": "official::github",
                            "display_name": "Address comments",
                            "install_status": "installed",
                            "enablement_status": "enabled",
                            "compatibility_status": "compatible",
                            "owner_plugin_id": "github",
                            "compatibility_warnings": [],
                            "notes": [],
                        }
                    ],
                    "notes": [],
                },
                codex_home=codex_home,
                workspace_root=workspace,
            )
            skill = snapshot["skills"][0]
            self.assertEqual(skill["global_enablement_status"], "disabled")
            self.assertEqual(skill["enablement_status"], "disabled")
            self.assertIn("enablement_pending_user_approval", skill["notes"])


class SkillEnablementRouteTests(unittest.TestCase):
    def test_handler_runtime_skill_enablement_route_returns_snapshot(self) -> None:
        handler = Handler.__new__(Handler)
        captured: dict[str, Any] = {}

        class Runtime:
            def __init__(self) -> None:
                self.calls: list[dict[str, Any]] = []

            def skill_enablement_update(self, profile: dict[str, Any], *, record_id: str, scope: str, enablement_status: str) -> dict[str, Any]:
                self.calls.append(
                    {
                        "profile": profile,
                        "record_id": record_id,
                        "scope": scope,
                        "enablement_status": enablement_status,
                    }
                )
                return {
                    "schema_version": "astrabridge-plugin-skill-registry-v1",
                    "generated_at": "2026-06-25T20:30:00+08:00",
                    "source_catalogs": [],
                    "plugins": [],
                    "skills": [],
                    "notes": [],
                }

        class Context:
            runtime = Runtime()

        handler.context = Context()  # type: ignore[assignment]
        handler.command = "POST"  # type: ignore[assignment]
        handler.path = "/api/runtime/skill-enablement"  # type: ignore[assignment]
        handler.send_json = lambda payload, status=200: captured.update({"payload": payload, "status": status})  # type: ignore[assignment]
        handler._resolve_runtime_profile = lambda profile_id: {"profile_id": profile_id or "resolved-profile"}  # type: ignore[assignment]
        handler._optional_string = lambda payload, key: payload.get(key)  # type: ignore[assignment]
        handler.read_json_body = lambda: {  # type: ignore[assignment]
            "profile_id": "demo-profile",
            "record_id": "skill::github:gh-address-comments::abc123",
            "scope": "project",
            "enablement_status": "enabled",
        }
        handler._require_admin_token = lambda: None  # type: ignore[assignment]

        Handler.do_POST(handler)

        self.assertEqual(captured["status"], 200)
        self.assertEqual(captured["payload"]["schema_version"], "astrabridge-plugin-skill-registry-v1")
        self.assertEqual(
            handler.context.runtime.calls,  # type: ignore[attr-defined]
            [
                {
                    "profile": {"profile_id": "demo-profile"},
                    "record_id": "skill::github:gh-address-comments::abc123",
                    "scope": "project",
                    "enablement_status": "enabled",
                }
            ],
        )


if __name__ == "__main__":
    unittest.main()
