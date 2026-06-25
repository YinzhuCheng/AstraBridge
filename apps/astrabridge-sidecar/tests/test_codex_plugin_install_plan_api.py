from __future__ import annotations

import sys
import unittest
from pathlib import Path
from tempfile import mkdtemp
from typing import Any
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from astrabridge_sidecar.codex_plugin_install_plan import build_plugin_install_plan
from astrabridge_sidecar.runtime_service import RuntimeService
from astrabridge_sidecar.server import Handler


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _registry_snapshot(*, source_root: Path, target_root: Path, source_kind: str = "local", source_url: str | None = None) -> dict[str, Any]:
    return {
        "schema_version": "astrabridge-plugin-skill-registry-v1",
        "generated_at": "2026-06-25T19:00:00+08:00",
        "source_catalogs": [
            {
                "schema_version": "astrabridge-plugin-skill-source-catalog-v1",
                "source_catalog_id": "catalog::demo",
                "kind": source_kind,
                "display_name": "Demo catalog",
                "source_path": str(source_root),
                "source_url": source_url,
                "writable": source_kind in {"local", "project_local", "manual"},
            }
        ],
        "plugins": [
            {
                "schema_version": "astrabridge-plugin-registry-record-v1",
                "record_id": "plugin::demo::catalog",
                "plugin_id": "demo-plugin",
                "source_catalog_id": "catalog::demo",
                "display_name": "Demo Plugin",
                "install_status": "available" if source_kind == "local" else "update_available",
                "enablement_status": "disabled",
                "compatibility_status": "compatible",
                "version": "1.2.3",
                "available_version": "1.2.3",
                "install_root": str(target_root),
                "permission_hints": ["declares_mcp_servers"],
                "declared_app_ids": ["demo-app"],
                "declared_mcp_servers": ["demo-mcp"],
                "keywords": ["demo:skill"],
                "provenance": {
                    "schema_version": "astrabridge-plugin-skill-provenance-v1",
                    "source_path": str(source_root),
                    "manifest_path": str(source_root / ".codex-plugin" / "plugin.json"),
                },
            }
        ],
        "skills": [
            {
                "schema_version": "astrabridge-skill-registry-record-v1",
                "record_id": "skill::demo:skill::catalog",
                "skill_name": "demo:skill",
                "source_catalog_id": "catalog::demo",
                "display_name": "demo:skill",
                "install_status": "installed",
                "enablement_status": "enabled",
                "compatibility_status": "compatible",
                "owner_plugin_id": "demo-plugin",
                "provenance": {
                    "schema_version": "astrabridge-plugin-skill-provenance-v1",
                    "source_path": str(source_root / "skills" / "demo" / "SKILL.md"),
                    "manifest_path": str(source_root / "skills" / "demo" / "SKILL.md"),
                },
            }
        ],
        "notes": [],
    }


class PluginInstallPlanBuilderTests(unittest.TestCase):
    def test_build_install_plan_for_local_plugin(self) -> None:
        temp_root = Path(mkdtemp())
        codex_home = temp_root / "codex-home"
        source_root = temp_root / "marketplace" / "demo-plugin"
        target_root = codex_home / "plugins" / "demo-plugin"
        _write(source_root / ".codex-plugin" / "plugin.json", '{"name":"demo-plugin"}')
        _write(source_root / "skills" / "demo" / "SKILL.md", "demo skill")

        plan = build_plugin_install_plan(
            registry_snapshot=_registry_snapshot(source_root=source_root, target_root=target_root),
            plugin_id="demo-plugin",
            source_catalog_id="catalog::demo",
            codex_home=codex_home,
        )

        self.assertEqual(plan["schema_version"], "astrabridge-plugin-install-plan-v1")
        self.assertEqual(plan["action"], "install")
        self.assertEqual(plan["status"], "ready")
        self.assertEqual(plan["files"]["source_file_count"], 2)
        self.assertEqual(plan["files"]["planned_write_count"], 2)
        self.assertEqual(plan["mcp_changes"]["declared_servers"], ["demo-mcp"])
        self.assertEqual(plan["skill_changes"]["declared_skills"], ["demo:skill"])
        self.assertEqual(plan["rollback_snapshot"]["status"], "planned")
        self.assertEqual(plan["errors"], [])

    def test_build_plan_redacts_sensitive_source_url_and_marks_remote_source_unsupported(self) -> None:
        temp_root = Path(mkdtemp())
        codex_home = temp_root / "codex-home"
        source_root = temp_root / "remote" / "demo-plugin"
        target_root = codex_home / "plugins" / "demo-plugin"
        _write(source_root / ".codex-plugin" / "plugin.json", '{"name":"demo-plugin"}')

        snapshot = _registry_snapshot(
            source_root=source_root,
            target_root=target_root,
            source_kind="official",
            source_url="https://plugins.example.com/demo-plugin?token=super-secret-token",
        )

        plan = build_plugin_install_plan(
            registry_snapshot=snapshot,
            plugin_id="demo-plugin",
            source_catalog_id="catalog::demo",
            codex_home=codex_home,
        )

        self.assertEqual(plan["action"], "unsupported")
        self.assertEqual(plan["status"], "unsupported")
        self.assertEqual(plan["source"]["source_url"], "https://plugins.example.com/demo-plugin?token=[REDACTED]")
        self.assertEqual(plan["errors"][0]["code"], "plugin-source-unsupported")


class PluginInstallPlanRuntimeTests(unittest.TestCase):
    def test_runtime_plugin_install_plan_calls_builder(self) -> None:
        runtime = RuntimeService.__new__(RuntimeService)
        runtime._prepare_runtime = lambda profile, require_secret=False: {"codex_home": "D:/AstraBridge/.astrabridge/codex-home"}  # type: ignore[attr-defined]
        runtime._record_event = lambda payload: payload  # type: ignore[attr-defined]
        runtime._plugin_skill_registry_snapshot_payload = lambda profile: (  # type: ignore[attr-defined]
            {"codex_home": "D:/AstraBridge/.astrabridge/codex-home"},
            {"schema_version": "astrabridge-plugin-skill-registry-v1", "generated_at": "2026-06-25T19:00:00+08:00", "source_catalogs": [], "plugins": [], "skills": []},
        )
        with patch("astrabridge_sidecar.runtime_service.build_plugin_install_plan", return_value={"schema_version": "astrabridge-plugin-install-plan-v1", "action": "noop", "status": "ready"}) as builder:
            plan = runtime.plugin_install_plan({"profile_id": "demo-profile"}, plugin_id="demo-plugin", source_catalog_id="catalog::demo")

        self.assertEqual(plan["action"], "noop")
        builder.assert_called_once()


class PluginInstallPlanRouteTests(unittest.TestCase):
    def test_handler_plugin_install_plan_route_returns_plan(self) -> None:
        handler = Handler.__new__(Handler)
        captured: dict[str, Any] = {}

        class Runtime:
            def __init__(self) -> None:
                self.calls: list[dict[str, Any]] = []

            def plugin_install_plan(self, profile: dict[str, Any], *, plugin_id: str, source_catalog_id: str | None = None) -> dict[str, Any]:
                self.calls.append(
                    {
                        "profile": profile,
                        "plugin_id": plugin_id,
                        "source_catalog_id": source_catalog_id,
                    }
                )
                return {
                    "schema_version": "astrabridge-plugin-install-plan-v1",
                    "generated_at": "2026-06-25T19:00:00+08:00",
                    "action": "noop",
                    "status": "ready",
                    "reason": "already_current",
                }

        class Context:
            runtime = Runtime()

        handler.context = Context()  # type: ignore[assignment]
        handler.path = "/api/runtime/plugin-install-plan"  # type: ignore[assignment]
        handler.send_json = lambda payload, status=200: captured.update({"payload": payload, "status": status})  # type: ignore[assignment]
        handler.read_json_body = lambda: {"profile_id": "demo-profile", "plugin_id": "demo-plugin", "source_catalog_id": "catalog::demo"}  # type: ignore[assignment]
        handler._resolve_runtime_profile = lambda profile_id: {"profile_id": profile_id or "resolved-profile"}  # type: ignore[assignment]
        handler._optional_string = lambda payload, key: str(payload.get(key) or "").strip() or None  # type: ignore[assignment]
        handler._require_admin_token = lambda: None  # type: ignore[assignment]
        handler.command = "POST"  # type: ignore[assignment]

        Handler.do_POST(handler)

        self.assertEqual(captured["status"], 200)
        self.assertEqual(captured["payload"]["schema_version"], "astrabridge-plugin-install-plan-v1")
        self.assertEqual(
            handler.context.runtime.calls,  # type: ignore[attr-defined]
            [
                {
                    "profile": {"profile_id": "demo-profile"},
                    "plugin_id": "demo-plugin",
                    "source_catalog_id": "catalog::demo",
                }
            ],
        )


if __name__ == "__main__":
    unittest.main()
