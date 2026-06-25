from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from astrabridge_sidecar.codex_plugin_skill_registry_contract import (
    PluginRegistryRecord,
    RegistryCompatibilityWarning,
    SkillRegistryRecord,
    normalize_plugin_registry_record,
    normalize_plugin_skill_registry_snapshot,
    normalize_skill_registry_record,
    normalize_source_catalog,
)


class RegistrySourceCatalogTests(unittest.TestCase):
    def test_source_catalog_supports_required_source_kinds(self) -> None:
        catalogs = [
            normalize_source_catalog({"source_catalog_id": "official-core", "kind": "official", "display_name": "Official"}),
            normalize_source_catalog({"source_catalog_id": "curated-team", "kind": "curated", "display_name": "Curated"}),
            normalize_source_catalog({"source_catalog_id": "local-marketplace", "kind": "local", "display_name": "Local"}),
            normalize_source_catalog({"source_catalog_id": "project-root", "kind": "project_local", "display_name": "Project"}),
            normalize_source_catalog({"source_catalog_id": "manual-import", "kind": "manual", "display_name": "Manual"}),
        ]

        self.assertEqual(
            [catalog.kind for catalog in catalogs],
            ["official", "curated", "local", "project_local", "manual"],
        )
        self.assertTrue(all(catalog.to_dict()["source_catalog_id"] for catalog in catalogs))


class PluginRegistryContractTests(unittest.TestCase):
    def test_plugin_record_roundtrips_installed_and_available_records(self) -> None:
        installed = normalize_plugin_registry_record(
            {
                "record_id": "installed::context7",
                "plugin_id": "context7",
                "source_catalog_id": "official-core",
                "display_name": "Context7",
                "install_status": "installed",
                "enablement_status": "enabled",
                "compatibility_status": "compatible",
                "installed_version": "1.0.0",
                "keywords": ["docs", "search", "docs"],
                "declared_mcp_servers": ["context7"],
                "provenance": {"manifest_path": "D:/AstraBridge/.astrabridge/plugins/context7/.codex-plugin/plugin.json"},
            }
        )
        available = normalize_plugin_registry_record(
            {
                "record_id": "available::context7",
                "plugin_id": "context7",
                "source_catalog_id": "official-core",
                "display_name": "Context7",
                "install_status": "available",
                "enablement_status": "unknown",
                "compatibility_status": "compatible",
                "available_version": "1.1.0",
            }
        )

        self.assertEqual(installed.installed_version, "1.0.0")
        self.assertEqual(installed.keywords, ("docs", "search"))
        self.assertEqual(installed.declared_mcp_servers, ("context7",))
        self.assertEqual(available.available_version, "1.1.0")
        self.assertEqual(available.to_dict()["install_status"], "available")

    def test_plugin_record_roundtrips_update_incompatible_and_malformed_records(self) -> None:
        update_available = normalize_plugin_registry_record(
            {
                "record_id": "update::github",
                "plugin_id": "github",
                "source_catalog_id": "curated-team",
                "display_name": "GitHub",
                "install_status": "update_available",
                "enablement_status": "enabled",
                "compatibility_status": "warning",
                "installed_version": "0.1.0",
                "available_version": "0.1.5",
                "compatibility_warnings": [
                    {"code": "upgrade-recommended", "severity": "warning", "message": "A newer version is available."}
                ],
            }
        )
        incompatible = normalize_plugin_registry_record(
            {
                "record_id": "incompatible::legacy",
                "plugin_id": "legacy-plugin",
                "source_catalog_id": "manual-import",
                "display_name": "Legacy Plugin",
                "install_status": "incompatible",
                "enablement_status": "blocked",
                "compatibility_status": "incompatible",
                "compatibility_warnings": [
                    {"code": "kernel-floor", "severity": "error", "message": "Requires a newer Codex kernel."}
                ],
            }
        )
        malformed = normalize_plugin_registry_record(
            {
                "record_id": "malformed::broken",
                "plugin_id": "broken-plugin",
                "source_catalog_id": "local-marketplace",
                "display_name": "Broken Plugin",
                "install_status": "malformed",
                "enablement_status": "unknown",
                "compatibility_status": "warning",
                "notes": ["manifest_parse_failed"],
            }
        )

        self.assertEqual(update_available.available_version, "0.1.5")
        self.assertEqual(update_available.compatibility_warnings[0].code, "upgrade-recommended")
        self.assertEqual(incompatible.compatibility_status, "incompatible")
        self.assertEqual(incompatible.compatibility_warnings[0].severity, "error")
        self.assertEqual(malformed.notes, ("manifest_parse_failed",))


class SkillRegistryContractTests(unittest.TestCase):
    def test_skill_record_roundtrips_disabled_incompatible_and_malformed_records(self) -> None:
        disabled = normalize_skill_registry_record(
            {
                "record_id": "skill::gh-address-comments",
                "skill_name": "github:gh-address-comments",
                "source_catalog_id": "curated-team",
                "display_name": "Address PR comments",
                "install_status": "installed",
                "enablement_status": "disabled",
                "compatibility_status": "compatible",
                "owner_plugin_id": "github",
                "trigger_hints": ["pull request review", "review comments", "pull request review"],
            }
        )
        incompatible = normalize_skill_registry_record(
            {
                "record_id": "skill::future-only",
                "skill_name": "future-only",
                "source_catalog_id": "official-core",
                "display_name": "Future Only",
                "install_status": "incompatible",
                "enablement_status": "blocked",
                "compatibility_status": "incompatible",
                "compatibility_warnings": [
                    {"code": "unsupported-protocol", "severity": "error", "message": "Requires unsupported protocol surface."}
                ],
            }
        )
        malformed = normalize_skill_registry_record(
            {
                "record_id": "skill::broken",
                "skill_name": "broken",
                "source_catalog_id": "project-root",
                "display_name": "Broken Skill",
                "install_status": "malformed",
                "enablement_status": "unknown",
                "compatibility_status": "warning",
                "notes": ["missing_description"],
            }
        )

        self.assertEqual(disabled.enablement_status, "disabled")
        self.assertEqual(disabled.trigger_hints, ("pull request review", "review comments"))
        self.assertEqual(incompatible.compatibility_warnings[0].code, "unsupported-protocol")
        self.assertEqual(malformed.install_status, "malformed")


class RegistrySnapshotContractTests(unittest.TestCase):
    def test_snapshot_roundtrips_mixed_states_and_validates_catalog_links(self) -> None:
        snapshot = normalize_plugin_skill_registry_snapshot(
            {
                "generated_at": "2026-06-25T20:00:00Z",
                "source_catalogs": [
                    {"source_catalog_id": "official-core", "kind": "official", "display_name": "Official"},
                    {"source_catalog_id": "curated-team", "kind": "curated", "display_name": "Curated"},
                    {"source_catalog_id": "local-marketplace", "kind": "local", "display_name": "Local"},
                    {"source_catalog_id": "project-root", "kind": "project_local", "display_name": "Project"},
                    {"source_catalog_id": "manual-import", "kind": "manual", "display_name": "Manual"},
                ],
                "plugins": [
                    {
                        "record_id": "installed::context7",
                        "plugin_id": "context7",
                        "source_catalog_id": "official-core",
                        "display_name": "Context7",
                        "install_status": "installed",
                        "enablement_status": "enabled",
                        "compatibility_status": "compatible",
                    },
                    {
                        "record_id": "available::context7",
                        "plugin_id": "context7",
                        "source_catalog_id": "official-core",
                        "display_name": "Context7",
                        "install_status": "available",
                        "enablement_status": "unknown",
                        "compatibility_status": "compatible",
                    },
                    {
                        "record_id": "update::github",
                        "plugin_id": "github",
                        "source_catalog_id": "curated-team",
                        "display_name": "GitHub",
                        "install_status": "update_available",
                        "enablement_status": "enabled",
                        "compatibility_status": "warning",
                        "available_version": "0.1.5",
                    },
                ],
                "skills": [
                    {
                        "record_id": "skill::disabled",
                        "skill_name": "github:gh-address-comments",
                        "source_catalog_id": "curated-team",
                        "display_name": "Address comments",
                        "install_status": "installed",
                        "enablement_status": "disabled",
                        "compatibility_status": "compatible",
                    },
                    {
                        "record_id": "skill::incompatible",
                        "skill_name": "future-only",
                        "source_catalog_id": "manual-import",
                        "display_name": "Future Only",
                        "install_status": "incompatible",
                        "enablement_status": "blocked",
                        "compatibility_status": "incompatible",
                    },
                    {
                        "record_id": "skill::malformed",
                        "skill_name": "broken",
                        "source_catalog_id": "project-root",
                        "display_name": "Broken",
                        "install_status": "malformed",
                        "enablement_status": "unknown",
                        "compatibility_status": "warning",
                    },
                ],
            }
        )

        rendered = snapshot.to_dict()
        self.assertEqual(rendered["plugins"][0]["install_status"], "installed")
        self.assertEqual(rendered["plugins"][1]["install_status"], "available")
        self.assertEqual(rendered["plugins"][2]["install_status"], "update_available")
        self.assertEqual(rendered["skills"][0]["enablement_status"], "disabled")
        self.assertEqual(rendered["skills"][1]["install_status"], "incompatible")
        self.assertEqual(rendered["skills"][2]["install_status"], "malformed")

    def test_snapshot_rejects_missing_source_catalog_reference(self) -> None:
        with self.assertRaises(ValueError):
            normalize_plugin_skill_registry_snapshot(
                {
                    "generated_at": "2026-06-25T20:00:00Z",
                    "source_catalogs": [{"source_catalog_id": "official-core", "kind": "official", "display_name": "Official"}],
                    "plugins": [
                        {
                            "record_id": "installed::context7",
                            "plugin_id": "context7",
                            "source_catalog_id": "missing-catalog",
                            "display_name": "Context7",
                            "install_status": "installed",
                            "enablement_status": "enabled",
                            "compatibility_status": "compatible",
                        }
                    ],
                }
            )


class RegistryWarningContractTests(unittest.TestCase):
    def test_warning_roundtrips(self) -> None:
        warning = RegistryCompatibilityWarning.from_any(
            {"code": "icon-license-unclear", "severity": "warning", "message": "Icon license is unclear."}
        )

        self.assertEqual(warning.to_dict()["severity"], "warning")
        self.assertEqual(warning.code, "icon-license-unclear")


if __name__ == "__main__":
    unittest.main()
