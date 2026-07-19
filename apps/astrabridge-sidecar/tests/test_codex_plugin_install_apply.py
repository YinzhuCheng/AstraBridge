from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from tempfile import mkdtemp
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from astrabridge_sidecar.codex_plugin_install_apply import execute_plugin_install
from astrabridge_sidecar.runtime_service import RuntimeService
from astrabridge_sidecar.server import Handler


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _registry_snapshot(
    *,
    source_root: Path,
    target_root: Path,
    install_status: str,
    source_kind: str = "local",
    available_version: str | None = "1.2.3",
    installed_version: str | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": "astrabridge-plugin-skill-registry-v1",
        "generated_at": "2026-06-25T20:00:00+08:00",
        "source_catalogs": [
            {
                "schema_version": "astrabridge-plugin-skill-source-catalog-v1",
                "source_catalog_id": "catalog::demo",
                "kind": source_kind,
                "display_name": "Demo catalog",
                "source_path": str(source_root),
                "writable": source_kind in {"local", "project_local", "manual"},
            }
        ],
        "plugins": [
            {
                "schema_version": "astrabridge-plugin-registry-record-v1",
                "record_id": "plugin::demo-plugin::catalog",
                "plugin_id": "demo-plugin",
                "source_catalog_id": "catalog::demo",
                "display_name": "Demo Plugin",
                "install_status": install_status,
                "enablement_status": "disabled",
                "compatibility_status": "compatible",
                "version": installed_version or available_version or "1.2.3",
                "installed_version": installed_version,
                "available_version": available_version if install_status in {"available", "update_available"} else None,
                "install_root": str(target_root),
                "declared_mcp_servers": ["demo-mcp"],
                "declared_app_ids": ["demo-app"],
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


class PluginInstallApplyTests(unittest.TestCase):
    def test_install_copies_plugin_into_isolated_root_and_writes_report(self) -> None:
        temp_root = Path(mkdtemp())
        workspace_root = temp_root / "workspace"
        codex_home = temp_root / "codex-home"
        source_root = temp_root / "marketplace" / "demo-plugin"
        target_root = codex_home / "plugins" / "demo-plugin"
        _write(source_root / ".codex-plugin" / "plugin.json", '{"name":"demo-plugin"}')
        _write(source_root / "skills" / "demo" / "SKILL.md", "demo skill")

        result = execute_plugin_install(
            registry_snapshot=_registry_snapshot(source_root=source_root, target_root=target_root, install_status="available"),
            plugin_id="demo-plugin",
            source_catalog_id="catalog::demo",
            codex_home=codex_home,
            workspace_root=workspace_root,
        )

        self.assertEqual(result["status"], "applied")
        self.assertTrue((target_root / ".codex-plugin" / "plugin.json").exists())
        self.assertTrue(Path(result["artifact_paths"]["result_path"]).exists())
        self.assertTrue(Path(result["artifact_paths"]["apply_journal_path"]).exists())
        self.assertTrue(Path(result["artifact_paths"]["rollback_manifest_path"]).exists())
        journal = json.loads(Path(result["artifact_paths"]["apply_journal_path"]).read_text(encoding="utf-8"))
        self.assertEqual(journal["schema_version"], "astrabridge-agentic-update-apply-journal-v1")
        self.assertEqual(journal["status"], "committed")
        self.assertEqual(journal["tracks"][0]["track_id"], "plugin_skill_activation")
        self.assertEqual(journal["tracks"][0]["health_verdict"], "pass")
        self.assertEqual(result["changes"]["written_file_count"], 2)

    def test_update_captures_rollback_snapshot_and_replaces_files(self) -> None:
        temp_root = Path(mkdtemp())
        workspace_root = temp_root / "workspace"
        codex_home = temp_root / "codex-home"
        source_root = temp_root / "marketplace" / "demo-plugin-update"
        target_root = codex_home / "plugins" / "demo-plugin"
        _write(source_root / ".codex-plugin" / "plugin.json", '{"name":"demo-plugin","version":"2.0.0"}')
        _write(source_root / "skills" / "demo" / "SKILL.md", "updated")
        _write(target_root / ".codex-plugin" / "plugin.json", '{"name":"demo-plugin","version":"1.0.0"}')
        _write(target_root / "skills" / "demo" / "SKILL.md", "old")

        result = execute_plugin_install(
            registry_snapshot=_registry_snapshot(
                source_root=source_root,
                target_root=target_root,
                install_status="update_available",
                available_version="2.0.0",
                installed_version="1.0.0",
            ),
            plugin_id="demo-plugin",
            source_catalog_id="catalog::demo",
            codex_home=codex_home,
            workspace_root=workspace_root,
        )

        self.assertEqual(result["status"], "applied")
        self.assertEqual(result["rollback_snapshot"]["status"], "captured")
        self.assertEqual((target_root / "skills" / "demo" / "SKILL.md").read_text(encoding="utf-8"), "updated")
        self.assertTrue(Path(str(result["rollback_snapshot"]["snapshot_root"])) .exists())
        rollback_manifest = json.loads(Path(result["artifact_paths"]["rollback_manifest_path"]).read_text(encoding="utf-8"))
        self.assertEqual(rollback_manifest["restore_status"], "available_for_manual_restore")
        self.assertTrue(rollback_manifest["target_existed_before"])

    def test_noop_for_already_current_plugin(self) -> None:
        temp_root = Path(mkdtemp())
        workspace_root = temp_root / "workspace"
        codex_home = temp_root / "codex-home"
        source_root = temp_root / "marketplace" / "demo-plugin"
        target_root = codex_home / "plugins" / "demo-plugin"
        _write(source_root / ".codex-plugin" / "plugin.json", '{"name":"demo-plugin"}')

        result = execute_plugin_install(
            registry_snapshot=_registry_snapshot(
                source_root=source_root,
                target_root=target_root,
                install_status="installed",
                available_version=None,
                installed_version="1.2.3",
            ),
            plugin_id="demo-plugin",
            source_catalog_id="catalog::demo",
            codex_home=codex_home,
            workspace_root=workspace_root,
        )

        self.assertEqual(result["status"], "noop")
        self.assertEqual(result["rollback_snapshot"]["status"], "not_needed")
        journal = json.loads(Path(result["artifact_paths"]["apply_journal_path"]).read_text(encoding="utf-8"))
        self.assertEqual(journal["status"], "committed")
        self.assertEqual(journal["tracks"][0]["changed_paths"], [])

    def test_malformed_plugin_plan_is_rejected_without_write(self) -> None:
        temp_root = Path(mkdtemp())
        workspace_root = temp_root / "workspace"
        codex_home = temp_root / "codex-home"
        source_root = temp_root / "marketplace" / "demo-plugin"
        target_root = codex_home / "plugins" / "demo-plugin"

        result = execute_plugin_install(
            registry_snapshot=_registry_snapshot(
                source_root=source_root,
                target_root=target_root,
                install_status="malformed",
                available_version=None,
            ),
            plugin_id="demo-plugin",
            source_catalog_id="catalog::demo",
            codex_home=codex_home,
            workspace_root=workspace_root,
        )

        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["errors"][0]["code"], "plugin-install-status-unsupported")
        self.assertFalse(target_root.exists())

    def test_failed_apply_restores_snapshot_metadata_and_target_content(self) -> None:
        temp_root = Path(mkdtemp())
        workspace_root = temp_root / "workspace"
        codex_home = temp_root / "codex-home"
        source_root = temp_root / "marketplace" / "demo-plugin-update"
        target_root = codex_home / "plugins" / "demo-plugin"
        _write(source_root / ".codex-plugin" / "plugin.json", '{"name":"demo-plugin","version":"2.0.0"}')
        _write(source_root / "skills" / "demo" / "SKILL.md", "updated")
        _write(target_root / ".codex-plugin" / "plugin.json", '{"name":"demo-plugin","version":"1.0.0"}')
        _write(target_root / "skills" / "demo" / "SKILL.md", "old")

        def failing_move(source: Path, target: Path) -> None:  # noqa: ARG001
            raise RuntimeError("move failed")

        result = execute_plugin_install(
            registry_snapshot=_registry_snapshot(
                source_root=source_root,
                target_root=target_root,
                install_status="update_available",
                available_version="2.0.0",
                installed_version="1.0.0",
            ),
            plugin_id="demo-plugin",
            source_catalog_id="catalog::demo",
            codex_home=codex_home,
            workspace_root=workspace_root,
            move_fn=failing_move,
        )

        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["rollback_snapshot"]["status"], "restored_after_failure")
        self.assertEqual((target_root / "skills" / "demo" / "SKILL.md").read_text(encoding="utf-8"), "old")
        journal = json.loads(Path(result["artifact_paths"]["apply_journal_path"]).read_text(encoding="utf-8"))
        self.assertEqual(journal["status"], "rolled_back")
        self.assertEqual(journal["tracks"][0]["health_verdict"], "fail")
        rollback_manifest = json.loads(Path(result["artifact_paths"]["rollback_manifest_path"]).read_text(encoding="utf-8"))
        self.assertEqual(rollback_manifest["restore_status"], "restored_after_failure")

    def test_secret_scan_rejects_raw_secret_in_manifest(self) -> None:
        temp_root = Path(mkdtemp())
        workspace_root = temp_root / "workspace"
        codex_home = temp_root / "codex-home"
        source_root = temp_root / "marketplace" / "demo-plugin"
        target_root = codex_home / "plugins" / "demo-plugin"
        _write(source_root / ".codex-plugin" / "plugin.json", '{"name":"demo-plugin","api_key":"live-secret-value"}')

        result = execute_plugin_install(
            registry_snapshot=_registry_snapshot(source_root=source_root, target_root=target_root, install_status="available"),
            plugin_id="demo-plugin",
            source_catalog_id="catalog::demo",
            codex_home=codex_home,
            workspace_root=workspace_root,
        )

        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["errors"][0]["code"], "plugin-secret-scan-failed")
        self.assertFalse(target_root.exists())


class PluginInstallApplyRuntimeRouteTests(unittest.TestCase):
    def test_runtime_plugin_install_apply_uses_workspace_and_codex_home(self) -> None:
        runtime = RuntimeService.__new__(RuntimeService)
        runtime._record_event = lambda payload: payload  # type: ignore[attr-defined]
        runtime._plugin_skill_registry_snapshot_payload = lambda profile: (  # type: ignore[attr-defined]
            {"codex_home": "D:/AstraBridge/.astrabridge/codex-home"},
            {"schema_version": "astrabridge-plugin-skill-registry-v1", "generated_at": "2026-06-25T20:00:00+08:00", "source_catalogs": [], "plugins": [], "skills": []},
        )

        class Projects:
            @staticmethod
            def require_workspace_root() -> Path:
                return Path("D:/AstraBridge")

        runtime._projects = Projects()  # type: ignore[attr-defined]

        captured: dict[str, Any] = {}

        def fake_execute(**kwargs: Any) -> dict[str, Any]:
            captured.update(kwargs)
            return {"schema_version": "astrabridge-plugin-install-execution-v1", "status": "noop", "action": "noop"}

        from unittest.mock import patch

        with patch("astrabridge_sidecar.runtime_service.execute_plugin_install", side_effect=fake_execute):
            result = runtime.plugin_install_apply({"profile_id": "demo-profile"}, plugin_id="demo-plugin", source_catalog_id="catalog::demo")

        self.assertEqual(result["status"], "noop")
        self.assertEqual(captured["plugin_id"], "demo-plugin")
        self.assertEqual(str(captured["codex_home"]), "D:\\AstraBridge\\.astrabridge\\codex-home")
        self.assertEqual(str(captured["workspace_root"]), "D:\\AstraBridge")

    def test_handler_plugin_install_apply_route_returns_execution_result(self) -> None:
        handler = Handler.__new__(Handler)
        captured: dict[str, Any] = {}

        class Runtime:
            def __init__(self) -> None:
                self.calls: list[dict[str, Any]] = []

            def plugin_install_apply(self, profile: dict[str, Any], *, plugin_id: str, source_catalog_id: str | None = None) -> dict[str, Any]:
                self.calls.append({"profile": profile, "plugin_id": plugin_id, "source_catalog_id": source_catalog_id})
                return {
                    "schema_version": "astrabridge-plugin-install-execution-v1",
                    "execution_id": "plugin-install-123",
                    "executed_at": "2026-06-25T20:10:00+08:00",
                    "status": "noop",
                    "action": "noop",
                }

        class Context:
            runtime = Runtime()

        handler.context = Context()  # type: ignore[assignment]
        handler.path = "/api/runtime/plugin-install-apply"  # type: ignore[assignment]
        handler.command = "POST"  # type: ignore[assignment]
        handler._require_admin_token = lambda: None  # type: ignore[assignment]
        handler.read_json_body = lambda: {"profile_id": "demo-profile", "plugin_id": "demo-plugin", "source_catalog_id": "catalog::demo"}  # type: ignore[assignment]
        handler._resolve_runtime_profile = lambda profile_id: {"profile_id": profile_id or "resolved-profile"}  # type: ignore[assignment]
        handler._optional_string = lambda payload, key: str(payload.get(key) or "").strip() or None  # type: ignore[assignment]
        handler.send_json = lambda payload, status=200: captured.update({"payload": payload, "status": status})  # type: ignore[assignment]

        Handler.do_POST(handler)

        self.assertEqual(captured["status"], 200)
        self.assertEqual(captured["payload"]["schema_version"], "astrabridge-plugin-install-execution-v1")
        self.assertEqual(
            handler.context.runtime.calls,  # type: ignore[attr-defined]
            [{"profile": {"profile_id": "demo-profile"}, "plugin_id": "demo-plugin", "source_catalog_id": "catalog::demo"}],
        )


if __name__ == "__main__":
    unittest.main()
