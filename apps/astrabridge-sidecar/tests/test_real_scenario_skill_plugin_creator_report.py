from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

from jsonschema import Draft7Validator

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from astrabridge_sidecar.codex_skill_plugin_creator_scenario import (  # noqa: E402
    build_plugin_creator_skill_dogfood_report,
    execute_plugin_creator_skill_scenario,
)
from astrabridge_sidecar.runtime_service import RuntimeService  # noqa: E402
from astrabridge_sidecar.server import Handler  # noqa: E402


MIN_PNG_BYTES = bytes.fromhex(
    "89504E470D0A1A0A"
    "0000000D49484452000000010000000108060000001F15C489"
    "0000000A49444154789C6360000002000154A24F5D00000000"
    "49454E44AE426082"
)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _write_png(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(MIN_PNG_BYTES)


def _fake_plugin_creator_skill_root(root: Path, *, validate_exit: int = 0) -> Path:
    skill_root = root / "plugin-creator"
    create_script = skill_root / "scripts" / "create_basic_plugin.py"
    validate_script = skill_root / "scripts" / "validate_plugin.py"
    _write(
        create_script,
        """
import argparse
import json
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("plugin_name")
parser.add_argument("--path", required=True)
parser.add_argument("--marketplace-path", required=True)
parser.add_argument("--with-skills", action="store_true")
parser.add_argument("--with-scripts", action="store_true")
parser.add_argument("--with-assets", action="store_true")
parser.add_argument("--with-mcp", action="store_true")
parser.add_argument("--with-apps", action="store_true")
parser.add_argument("--with-marketplace", action="store_true")
parser.add_argument("--force", action="store_true")
args = parser.parse_args()

plugin_root = Path(args.path) / args.plugin_name
(plugin_root / ".codex-plugin").mkdir(parents=True, exist_ok=True)
(plugin_root / "skills").mkdir(parents=True, exist_ok=True)
(plugin_root / "scripts").mkdir(parents=True, exist_ok=True)
(plugin_root / "assets").mkdir(parents=True, exist_ok=True)
(plugin_root / ".codex-plugin" / "plugin.json").write_text(json.dumps({
    "name": args.plugin_name,
    "version": "0.1.0",
    "description": f"{args.plugin_name} plugin",
    "author": {"name": "Local developer"},
    "skills": "./skills/",
    "mcpServers": "./.mcp.json",
    "apps": "./.app.json",
    "interface": {
        "displayName": "Astrabridge Skills Dogfood Sample",
        "shortDescription": "Use Astrabridge Skills Dogfood Sample in Codex.",
        "longDescription": "Astrabridge Skills Dogfood Sample adds a local Codex plugin scaffold.",
        "developerName": "Local developer",
        "category": "Productivity",
        "capabilities": [],
        "defaultPrompt": "Help me use Astrabridge Skills Dogfood Sample."
    }
}, indent=2) + "\\n", encoding="utf-8")
(plugin_root / ".mcp.json").write_text('{"mcpServers": {}}\\n', encoding="utf-8")
(plugin_root / ".app.json").write_text('{"apps": {}}\\n', encoding="utf-8")
marketplace_path = Path(args.marketplace_path)
marketplace_path.parent.mkdir(parents=True, exist_ok=True)
marketplace_path.write_text(json.dumps({
    "name": "personal",
    "interface": {"displayName": "Personal"},
    "plugins": [{
        "name": args.plugin_name,
        "source": {"source": "local", "path": f"./plugins/{args.plugin_name}"},
        "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
        "category": "Productivity"
    }]
}, indent=2) + "\\n", encoding="utf-8")
print(f"Created plugin scaffold: {plugin_root}")
""".strip(),
    )
    _write(
        validate_script,
        f"""
import sys
from pathlib import Path

plugin_root = Path(sys.argv[1]).resolve()
manifest_path = plugin_root / ".codex-plugin" / "plugin.json"
if not manifest_path.is_file():
    print("missing manifest")
    raise SystemExit(1)
print(f"validated: {{manifest_path}}")
raise SystemExit({validate_exit})
""".strip(),
    )
    return skill_root


class SkillPluginCreatorScenarioTests(unittest.TestCase):
    def test_execute_skill_plugin_creator_scenario_tracks_outputs_and_builds_schema_ready_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace_root = root / "workspace"
            workspace_root.mkdir(parents=True, exist_ok=True)
            skill_root = _fake_plugin_creator_skill_root(root)

            result = execute_plugin_creator_skill_scenario(
                workspace_root=workspace_root,
                skill_root=skill_root,
                skill_record_id="skill::plugin-creator::unit",
                skill_display_name="Plugin Creator",
            )

            self.assertEqual(result["status"], "pass")
            self.assertTrue(Path(result["artifact_paths"]["result_path"]).exists())
            self.assertTrue(Path(result["artifact_paths"]["report_seed_path"]).exists())
            self.assertTrue(Path(result["output"]["plugin_root"]).is_dir())
            self.assertTrue(Path(result["output"]["manifest_path"]).is_file())
            self.assertTrue(Path(result["output"]["marketplace_path"]).is_file())
            self.assertEqual(len(result["verification_commands"]), 2)
            self.assertTrue(all(item["exit_code"] == 0 for item in result["verification_commands"]))

            screenshot_path = workspace_root / "apps" / "astrabridge-desktop" / "output" / "playwright" / "real-scenario-dogfood" / "step10-skills-plugin-creator-reference.png"
            _write_png(screenshot_path)
            report = build_plugin_creator_skill_dogfood_report(
                execution_result=result,
                screenshots=[{"kind": "reference", "path": str(screenshot_path), "note": "Backend report-chain validation without UI capture."}],
                step_id="step_10",
                status="partial",
                notes=["Step 10 validates the report chain before the UI execution step."],
            )

            schema = json.loads(Path(r"D:\AstraBridge\docs\REAL_SCENARIO_DOGFOOD_REPORT_SCHEMA.json").read_text(encoding="utf-8"))
            errors = sorted(Draft7Validator(schema).iter_errors(report), key=lambda item: item.path)
            self.assertEqual(errors, [])
            roles = {item["role"] for item in report["artifacts"]}
            self.assertIn("skill-scenario-brief", roles)
            self.assertIn("generated-plugin-manifest", roles)
            self.assertIn("generated-marketplace", roles)
            self.assertEqual(report["scenario_id"], "skills_plugin_creator_fixture_scaffold")
            self.assertEqual(report["record_id"], "skill::plugin-creator::unit")

    def test_execute_skill_plugin_creator_scenario_captures_failure_reason_and_fail_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace_root = root / "workspace"
            workspace_root.mkdir(parents=True, exist_ok=True)
            skill_root = _fake_plugin_creator_skill_root(root, validate_exit=3)

            result = execute_plugin_creator_skill_scenario(
                workspace_root=workspace_root,
                skill_root=skill_root,
            )

            self.assertEqual(result["status"], "failed")
            self.assertIn("validate_plugin.py exited with code 3", result["failure_reason"])
            self.assertEqual(result["verification_commands"][1]["exit_code"], 3)

            screenshot_path = workspace_root / "apps" / "astrabridge-desktop" / "output" / "playwright" / "real-scenario-dogfood" / "step10-skills-plugin-creator-failure.png"
            _write_png(screenshot_path)
            report = build_plugin_creator_skill_dogfood_report(
                execution_result=result,
                screenshots=[{"kind": "failure", "path": str(screenshot_path), "note": "Validation failure captured for report-chain testing."}],
                step_id="step_10",
            )

            schema = json.loads(Path(r"D:\AstraBridge\docs\REAL_SCENARIO_DOGFOOD_REPORT_SCHEMA.json").read_text(encoding="utf-8"))
            errors = sorted(Draft7Validator(schema).iter_errors(report), key=lambda item: item.path)
            self.assertEqual(errors, [])
            self.assertEqual(report["status"], "fail")
            self.assertIn("failure_reason", report)


class SkillPluginCreatorScenarioRuntimeRouteTests(unittest.TestCase):
    def test_runtime_skill_plugin_creator_fixture_scenario_uses_discovered_skill_root_and_workspace(self) -> None:
        runtime = RuntimeService.__new__(RuntimeService)
        runtime._record_event = lambda payload: payload  # type: ignore[attr-defined]
        runtime._plugin_skill_registry_snapshot_payload = lambda profile: (  # type: ignore[attr-defined]
            {},
            {
                "schema_version": "astrabridge-plugin-skill-registry-v1",
                "generated_at": "2026-06-26T12:00:00+08:00",
                "source_catalogs": [],
                "plugins": [],
                "skills": [
                    {
                        "record_id": "skill::plugin-creator::catalog",
                        "skill_name": "plugin-creator",
                        "display_name": "Plugin Creator",
                        "provenance": {
                            "source_path": "D:/codex-home/skills/.system/plugin-creator/SKILL.md",
                        },
                    }
                ],
            },
        )

        class Projects:
            @staticmethod
            def require_workspace_root() -> Path:
                return Path("D:/AstraBridge")

        runtime._projects = Projects()  # type: ignore[attr-defined]

        captured: dict[str, Any] = {}

        def fake_execute(**kwargs: Any) -> dict[str, Any]:
            captured.update(kwargs)
            return {"schema_version": "astrabridge-skill-plugin-creator-scenario-v1", "status": "pass", "execution_id": "skill-plugin-creator-123"}

        with patch("astrabridge_sidecar.runtime_service.execute_plugin_creator_skill_scenario", side_effect=fake_execute):
            result = runtime.skill_plugin_creator_fixture_scenario({"profile_id": "demo-profile"})

        self.assertEqual(result["status"], "pass")
        self.assertEqual(str(captured["workspace_root"]), "D:\\AstraBridge")
        self.assertEqual(str(captured["skill_root"]), "D:\\codex-home\\skills\\.system\\plugin-creator")
        self.assertEqual(captured["skill_record_id"], "skill::plugin-creator::catalog")

    def test_handler_skill_plugin_creator_fixture_route_returns_execution_result(self) -> None:
        handler = Handler.__new__(Handler)
        captured: dict[str, Any] = {}

        class Runtime:
            def __init__(self) -> None:
                self.calls: list[dict[str, Any]] = []

            def skill_plugin_creator_fixture_scenario(self, profile: dict[str, Any], *, skill_name: str = "plugin-creator") -> dict[str, Any]:
                self.calls.append({"profile": profile, "skill_name": skill_name})
                return {
                    "schema_version": "astrabridge-skill-plugin-creator-scenario-v1",
                    "execution_id": "skill-plugin-creator-123",
                    "status": "pass",
                }

        class Context:
            runtime = Runtime()

        handler.context = Context()  # type: ignore[assignment]
        handler.path = "/api/runtime/skill-scenario/plugin-creator-fixture"  # type: ignore[assignment]
        handler.command = "POST"  # type: ignore[assignment]
        handler._require_admin_token = lambda: None  # type: ignore[assignment]
        handler.read_json_body = lambda: {"profile_id": "demo-profile", "skill_name": "plugin-creator"}  # type: ignore[assignment]
        handler._resolve_runtime_profile = lambda profile_id: {"profile_id": profile_id or "resolved-profile"}  # type: ignore[assignment]
        handler.send_json = lambda payload, status=200: captured.update({"payload": payload, "status": status})  # type: ignore[assignment]

        Handler.do_POST(handler)

        self.assertEqual(captured["status"], 200)
        self.assertEqual(captured["payload"]["schema_version"], "astrabridge-skill-plugin-creator-scenario-v1")
        self.assertEqual(
            handler.context.runtime.calls,  # type: ignore[attr-defined]
            [{"profile": {"profile_id": "demo-profile"}, "skill_name": "plugin-creator"}],
        )


if __name__ == "__main__":
    unittest.main()
