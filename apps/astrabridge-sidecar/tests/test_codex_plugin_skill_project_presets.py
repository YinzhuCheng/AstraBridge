from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from astrabridge_sidecar.codex_plugin_skill_project_presets import (
    DEFAULT_PROJECT_PLUGIN_SKILL_PRESET_ID,
    active_project_plugin_skill_preset,
    mutate_project_plugin_skill_presets,
    normalize_project_plugin_skill_presets,
)
from astrabridge_sidecar.project_service import ProjectService
from astrabridge_sidecar.server import Handler


class ProjectPluginSkillPresetStateTests(unittest.TestCase):
    def test_normalize_project_plugin_skill_presets_seeds_default_preset(self) -> None:
        state = normalize_project_plugin_skill_presets(None)

        self.assertEqual(state["schema_version"], "astrabridge-project-plugin-skill-presets-v1")
        self.assertEqual(state["active_preset_id"], DEFAULT_PROJECT_PLUGIN_SKILL_PRESET_ID)
        self.assertEqual(len(state["presets"]), 1)
        self.assertEqual(state["presets"][0]["preset_id"], DEFAULT_PROJECT_PLUGIN_SKILL_PRESET_ID)

    def test_mutate_project_plugin_skill_presets_adds_and_resets_refs(self) -> None:
        state = normalize_project_plugin_skill_presets(None)
        state = mutate_project_plugin_skill_presets(
            state,
            operation="add_plugin",
            plugin_ref={"plugin_id": "github", "source_catalog_id": "official::github", "display_name": "GitHub"},
        )
        state = mutate_project_plugin_skill_presets(
            state,
            operation="add_skill",
            skill_ref={
                "record_id": "skill::github:gh-address-comments::abc123",
                "skill_name": "github:gh-address-comments",
                "owner_plugin_id": "github",
                "source_catalog_id": "official::github",
                "display_name": "Address comments",
            },
        )
        active = active_project_plugin_skill_preset(state)
        self.assertEqual(len(active["plugin_refs"]), 1)
        self.assertEqual(len(active["skill_refs"]), 1)

        reset = mutate_project_plugin_skill_presets(state, operation="reset")
        active_reset = active_project_plugin_skill_preset(reset)
        self.assertEqual(active_reset["plugin_refs"], [])
        self.assertEqual(active_reset["skill_refs"], [])


class ProjectPluginSkillPresetPersistenceTests(unittest.TestCase):
    def test_project_service_persists_project_plugin_skill_presets_across_restart(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            project_file = root / "demo.abproj"
            workspace = root / "workspace"
            workspace.mkdir()
            service = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
            project = service.create_project("Demo", project_file, workspace_root=workspace, entry_mode="existing")

            updated_presets = mutate_project_plugin_skill_presets(
                project.get("plugin_skill_presets"),
                operation="add_plugin",
                plugin_ref={"plugin_id": "github", "source_catalog_id": "official::github", "display_name": "GitHub"},
            )
            updated_presets = mutate_project_plugin_skill_presets(
                updated_presets,
                operation="add_skill",
                skill_ref={
                    "record_id": "skill::github:gh-address-comments::abc123",
                    "skill_name": "github:gh-address-comments",
                    "owner_plugin_id": "github",
                    "source_catalog_id": "official::github",
                    "display_name": "Address comments",
                },
            )
            service.update_project({"plugin_skill_presets": updated_presets})

            reopened = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
            self.assertIsNotNone(reopened.current_project)
            active = active_project_plugin_skill_preset((reopened.current_project or {}).get("plugin_skill_presets"))
            self.assertEqual(active["plugin_refs"][0]["plugin_id"], "github")
            self.assertEqual(active["skill_refs"][0]["skill_name"], "github:gh-address-comments")
            self.assertEqual(list(workspace.glob(".codex*")), [])
            self.assertFalse((workspace / ".astrabridge" / "extensions" / "plugin-skill-presets.json").exists())

    def test_open_project_repairs_missing_project_plugin_skill_presets(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            project_file = root / "demo.abproj"
            workspace = root / "workspace"
            workspace.mkdir()
            payload = {
                "schema_version": "astrabridge-project-v1",
                "project_id": "demo",
                "name": "Demo",
                "project_file": str(project_file),
                "workspace_root": str(workspace),
                "entry_mode": "existing",
                "default_profile_id": "openai-compatible",
                "default_model": "gpt-5.5",
                "default_effort": "high",
                "current_thread_id": None,
                "recent_threads": [],
                "current_task_id": None,
                "recent_tasks": [],
                "ui_preferences": {"locale": "en", "appearance": "codex", "execution_host": "windows"},
                "created_at": "2026-06-25T21:00:00+08:00",
                "updated_at": "2026-06-25T21:00:00+08:00",
            }
            project_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

            service = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
            project = service.open_project(project_file)

            self.assertIn("plugin_skill_presets", project)
            active = active_project_plugin_skill_preset(project.get("plugin_skill_presets"))
            self.assertEqual(active["preset_id"], DEFAULT_PROJECT_PLUGIN_SKILL_PRESET_ID)
            persisted = json.loads(project_file.read_text(encoding="utf-8"))
            self.assertIn("plugin_skill_presets", persisted)


class ProjectPluginSkillPresetRouteTests(unittest.TestCase):
    def test_handler_projects_plugin_skill_presets_route_updates_current_project(self) -> None:
        handler = Handler.__new__(Handler)
        captured: dict[str, Any] = {}

        class Projects:
            def __init__(self) -> None:
                self.current_project = {
                    "schema_version": "astrabridge-project-v1",
                    "project_id": "demo",
                    "name": "Demo",
                    "project_file": "D:/AstraBridge/demo.abproj",
                    "workspace_root": "D:/AstraBridge/workspace",
                    "entry_mode": "existing",
                    "default_profile_id": "openai-compatible",
                    "default_model": "gpt-5.5",
                    "default_effort": "high",
                    "current_thread_id": None,
                    "recent_threads": [],
                    "ui_preferences": {"locale": "en", "appearance": "codex", "execution_host": "windows"},
                    "plugin_skill_presets": normalize_project_plugin_skill_presets(None),
                    "created_at": "2026-06-25T21:10:00+08:00",
                    "updated_at": "2026-06-25T21:10:00+08:00",
                }

            def update_project(self, patch: dict[str, Any]) -> dict[str, Any]:
                self.current_project = {**self.current_project, **patch}
                return self.current_project

        class Context:
            projects = Projects()

        handler.context = Context()  # type: ignore[assignment]
        handler.command = "POST"  # type: ignore[assignment]
        handler.path = "/api/projects/plugin-skill-presets"  # type: ignore[assignment]
        handler.send_json = lambda payload, status=200: captured.update({"payload": payload, "status": status})  # type: ignore[assignment]
        handler.read_json_body = lambda: {  # type: ignore[assignment]
            "operation": "add_plugin",
            "preset_id": "project-default",
            "plugin_ref": {
                "plugin_id": "github",
                "source_catalog_id": "official::github",
                "display_name": "GitHub",
            },
        }
        handler._require_admin_token = lambda: None  # type: ignore[assignment]
        handler._optional_string = lambda payload, key: payload.get(key)  # type: ignore[assignment]

        Handler.do_POST(handler)

        self.assertEqual(captured["status"], 200)
        active = active_project_plugin_skill_preset(captured["payload"]["project"]["plugin_skill_presets"])
        self.assertEqual(active["plugin_refs"][0]["plugin_id"], "github")


if __name__ == "__main__":
    unittest.main()
