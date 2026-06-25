from __future__ import annotations

import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from astrabridge_sidecar.codex_plugin_skill_icon_pipeline import (
    resolve_plugin_icon_metadata,
    resolve_skill_icon_metadata,
)
from astrabridge_sidecar.codex_plugin_skill_registry import build_plugin_skill_registry_snapshot


class PluginSkillIconPipelineTests(unittest.TestCase):
    def test_resolves_curated_official_icon_override(self) -> None:
        with TemporaryDirectory() as tempdir:
            asset_path = Path(tempdir) / "official.svg"
            asset_path.write_text("<svg xmlns=\"http://www.w3.org/2000/svg\"></svg>\n", encoding="utf-8")

            icon, warnings, notes = resolve_plugin_icon_metadata(
                plugin={"plugin_id": "github", "display_name": "GitHub"},
                source_catalog={"kind": "official", "source_url": "https://github.com/openai/plugins"},
                runtime_roots={"codex_home_root": tempdir},
                search_roots=[],
                official_overrides={"plugins": {"github": {"asset_path": str(asset_path), "label": "GitHub"}}},
            )

        self.assertIsNotNone(icon)
        self.assertEqual(icon["provenance_kind"], "official")
        self.assertEqual(icon["asset_path"], str(asset_path))
        self.assertTrue(icon["validated"])
        self.assertIn("licensed_or_curated_official_asset", notes)
        self.assertEqual(warnings, [])

    def test_resolves_safe_local_manifest_icon(self) -> None:
        with TemporaryDirectory() as tempdir:
            plugin_root = Path(tempdir) / "plugins" / "demo-plugin"
            manifest_path = plugin_root / ".codex-plugin" / "plugin.json"
            icon_path = plugin_root / "assets" / "logo.png"
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            icon_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text("{}", encoding="utf-8")
            icon_path.write_bytes(b"png")

            icon, warnings, notes = resolve_plugin_icon_metadata(
                plugin={
                    "plugin_id": "demo-plugin",
                    "display_name": "Demo Plugin",
                    "manifest_path": str(manifest_path),
                    "logo": "assets/logo.png",
                },
                source_catalog={"kind": "local"},
                runtime_roots={"codex_home_root": tempdir},
                search_roots=[Path(tempdir)],
            )

        self.assertIsNotNone(icon)
        self.assertEqual(icon["provenance_kind"], "bundled_local")
        self.assertEqual(icon["asset_path"], str(icon_path.resolve()))
        self.assertEqual(icon["mime_type"], "image/png")
        self.assertTrue(icon["validated"])
        self.assertIn("manifest_local_icon", notes)
        self.assertEqual(warnings, [])

    def test_generates_fallback_icon_when_no_candidates_exist(self) -> None:
        with TemporaryDirectory() as tempdir:
            skill_path = Path(tempdir) / "skills" / "address-comments" / "SKILL.md"
            skill_path.parent.mkdir(parents=True, exist_ok=True)
            skill_path.write_text("---\nname: github:gh-address-comments\ndescription: Review comments\n---\n", encoding="utf-8")

            icon, warnings, notes = resolve_skill_icon_metadata(
                skill={
                    "skill_name": "github:gh-address-comments",
                    "display_name": "Address comments",
                    "path": str(skill_path),
                },
                source_catalog={"kind": "official"},
                runtime_roots={"codex_home_root": tempdir},
                search_roots=[Path(tempdir)],
            )

            self.assertIsNotNone(icon)
            self.assertEqual(icon["provenance_kind"], "generated_fallback")
            self.assertTrue(Path(icon["asset_path"]).is_file())
            self.assertEqual(icon["mime_type"], "image/svg+xml")
            self.assertIn("not_official_brand_asset", icon["notes"])
            self.assertIn("icon_provenance:generated_fallback", notes)
            self.assertTrue(any(item["code"] == "icon-missing" for item in warnings))

    def test_missing_local_icon_falls_back_and_records_warning(self) -> None:
        with TemporaryDirectory() as tempdir:
            plugin_root = Path(tempdir) / "plugins" / "demo-plugin"
            manifest_path = plugin_root / ".codex-plugin" / "plugin.json"
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text("{}", encoding="utf-8")

            icon, warnings, notes = resolve_plugin_icon_metadata(
                plugin={
                    "plugin_id": "demo-plugin",
                    "display_name": "Demo Plugin",
                    "manifest_path": str(manifest_path),
                    "logo": "assets/missing.png",
                },
                source_catalog={"kind": "local"},
                runtime_roots={"codex_home_root": tempdir},
                search_roots=[Path(tempdir)],
            )

        self.assertEqual(icon["provenance_kind"], "generated_fallback")
        self.assertTrue(any(item["code"] == "icon-local-invalid" and "missing" in item["message"].lower() for item in warnings))
        self.assertIn("icon_provenance:generated_fallback", notes)

    def test_unsafe_local_icon_path_falls_back_and_records_warning(self) -> None:
        with TemporaryDirectory() as tempdir:
            plugin_root = Path(tempdir) / "plugins" / "demo-plugin"
            manifest_path = plugin_root / ".codex-plugin" / "plugin.json"
            outside_icon = Path(tempdir) / "outside.png"
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text("{}", encoding="utf-8")
            outside_icon.write_bytes(b"png")

            icon, warnings, _notes = resolve_plugin_icon_metadata(
                plugin={
                    "plugin_id": "demo-plugin",
                    "display_name": "Demo Plugin",
                    "manifest_path": str(manifest_path),
                    "logo": "../outside.png",
                },
                source_catalog={"kind": "local"},
                runtime_roots={"codex_home_root": tempdir},
                search_roots=[Path(tempdir)],
            )

        self.assertEqual(icon["provenance_kind"], "generated_fallback")
        self.assertTrue(any(item["code"] == "icon-unsafe-path" for item in warnings))

    def test_unsafe_remote_icon_url_falls_back_and_records_warning(self) -> None:
        with TemporaryDirectory() as tempdir:
            icon, warnings, _notes = resolve_plugin_icon_metadata(
                plugin={
                    "plugin_id": "official-plugin",
                    "display_name": "Official Plugin",
                    "logo_url": "https://tracker.example.invalid/logo.png",
                },
                source_catalog={"kind": "official", "source_url": "https://github.com/openai/plugins"},
                runtime_roots={"codex_home_root": tempdir},
                search_roots=[],
            )

        self.assertEqual(icon["provenance_kind"], "generated_fallback")
        self.assertTrue(any(item["code"] == "icon-unsafe-url" for item in warnings))

    def test_snapshot_builder_attaches_resolved_icon_metadata(self) -> None:
        with TemporaryDirectory() as tempdir:
            plugin_root = Path(tempdir) / "plugins" / "demo-plugin"
            manifest_path = plugin_root / ".codex-plugin" / "plugin.json"
            icon_path = plugin_root / "assets" / "logo.png"
            skill_root = plugin_root / "skills" / "demo-skill"
            skill_path = skill_root / "SKILL.md"
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            icon_path.parent.mkdir(parents=True, exist_ok=True)
            skill_root.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text("{}", encoding="utf-8")
            icon_path.write_bytes(b"png")
            skill_path.write_text("---\nname: demo-skill\ndescription: Demo skill\n---\n", encoding="utf-8")

            snapshot = build_plugin_skill_registry_snapshot(
                plugin_report={
                    "plugin": {
                        "list_status": "supported",
                        "installed_status": "supported",
                        "read_status": "supported",
                        "marketplace_status": "supported",
                        "manifest_fallback_status": "used",
                        "discovered_plugins": [
                            {
                                "plugin_id": "demo-plugin",
                                "display_name": "Demo Plugin",
                                "availability": "installed",
                                "enabled": True,
                                "source_kind": "installed_root",
                                "manifest_status": "ok",
                                "manifest_path": str(manifest_path),
                                "logo": "assets/logo.png",
                            }
                        ],
                        "notes": [],
                    },
                    "known_warnings": [],
                },
                skill_report={
                    "skill": {
                        "list_status": "supported",
                        "extra_roots_status": "declared",
                        "config_write_status": "declared",
                        "change_notification_status": "declared",
                        "discovered_skills": [
                            {
                                "skill_name": "demo-skill",
                                "display_name": "Demo Skill",
                                "description": "Demo skill",
                                "description_status": "present",
                                "source_kind": "plugin",
                                "owner_plugin_id": "demo-plugin",
                                "enablement": "enabled",
                                "path": str(skill_path),
                                "trigger_hints": ["demo"],
                                "version_hint": "1.0.0",
                                "manifest_status": "ok",
                                "dependency_tools": [],
                            }
                        ],
                        "duplicate_skill_names": [],
                        "malformed_skill_paths": [],
                        "missing_description_paths": [],
                        "notes": [],
                    },
                    "known_warnings": [],
                },
                runtime_roots={"codex_home_root": tempdir, "workspace_runtime_cwd": tempdir, "project_runtime_root": tempdir},
                search_roots=[Path(tempdir)],
            )

        self.assertEqual(snapshot["plugins"][0]["icon"]["provenance_kind"], "bundled_local")
        self.assertEqual(snapshot["skills"][0]["icon"]["provenance_kind"], "generated_fallback")


if __name__ == "__main__":
    unittest.main()
