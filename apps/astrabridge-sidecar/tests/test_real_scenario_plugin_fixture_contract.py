from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from astrabridge_sidecar.codex_plugin_install_apply import _scan_plugin_source_for_raw_secrets
from astrabridge_sidecar.codex_plugin_probe import probe_plugin_discovery
from astrabridge_sidecar.codex_plugin_skill_icon_pipeline import resolve_plugin_icon_metadata
from astrabridge_sidecar.codex_plugin_skill_project_presets import (
    active_project_plugin_skill_preset,
    mutate_project_plugin_skill_presets,
    normalize_project_plugin_skill_presets,
)


FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures" / "plugin_fixture_catalog"
CONTRACT_PATH = FIXTURE_ROOT / "fixture-contract.json"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


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


class RealScenarioPluginFixtureContractTests(unittest.TestCase):
    def test_fixture_manifest_and_marketplace_match_contract(self) -> None:
        contract = _load_json(CONTRACT_PATH)
        source = contract["source"]
        plugin_contract = contract["plugin"]

        marketplace_path = FIXTURE_ROOT / source["marketplace_path_rel"]
        plugin_root = FIXTURE_ROOT / source["plugin_root_rel"]
        manifest_path = FIXTURE_ROOT / source["manifest_path_rel"]

        marketplace = _load_json(marketplace_path)
        manifest = _load_json(manifest_path)

        self.assertEqual(manifest["name"], plugin_contract["plugin_id"])
        self.assertEqual(manifest["version"], plugin_contract["version"])
        self.assertEqual(manifest["interface"]["displayName"], plugin_contract["display_name"])
        self.assertEqual(manifest["interface"]["longDescription"], plugin_contract["description"])
        self.assertEqual(manifest["interface"]["brandColor"], plugin_contract["brand_color"])
        self.assertEqual(sorted(manifest["mcpServers"].keys()), plugin_contract["declared_mcp_servers"])
        self.assertEqual(manifest["apps"], plugin_contract["declared_app_ids"])
        self.assertEqual(manifest["skills"], plugin_contract["declared_skills"])
        self.assertNotIn("hooks", manifest)

        self.assertEqual(marketplace["plugins"][0]["name"], plugin_contract["plugin_id"])
        self.assertEqual(marketplace["plugins"][0]["source"]["source"], "local")
        self.assertEqual(marketplace["plugins"][0]["source"]["path"], "./plugins/astrabridge-dogfood-fixture")
        self.assertEqual(marketplace["plugins"][0]["policy"]["installation"], "AVAILABLE")
        self.assertEqual(marketplace["plugins"][0]["policy"]["authentication"], "ON_INSTALL")

        self.assertTrue((plugin_root / "skills" / "astrabridge-fixture-skill" / "SKILL.md").exists())
        self.assertTrue((plugin_root / "scripts" / "fixture-mcp-server.js").exists())
        self.assertTrue((plugin_root / ".app.json").exists())
        self.assertTrue((plugin_root / "assets" / "icon.png").exists())
        self.assertTrue((plugin_root / "assets" / "logo.png").exists())

    def test_fixture_is_probeable_safe_and_icon_resolvable(self) -> None:
        contract = _load_json(CONTRACT_PATH)
        source = contract["source"]
        plugin_contract = contract["plugin"]
        plugin_root = FIXTURE_ROOT / source["plugin_root_rel"]

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            codex_home = _write_codex_home(root, plugins_enabled=False)
            report = probe_plugin_discovery(
                codex_home=codex_home,
                local_search_roots=[FIXTURE_ROOT],
                artifact_root=root / "artifacts",
            )

            plugin = next(
                item
                for item in report["plugin"]["discovered_plugins"]
                if item["plugin_id"] == plugin_contract["plugin_id"]
            )

            self.assertEqual(report["plugin"]["marketplace_status"], "manifest_fallback")
            self.assertEqual(report["plugin"]["manifest_fallback_status"], "supported")
            self.assertEqual(plugin["availability"], source["expected_install_status"])
            self.assertEqual(plugin["source_kind"], "local_marketplace")
            self.assertEqual(plugin["manifest_status"], "ok")
            self.assertEqual(plugin["version"], plugin_contract["version"])
            self.assertEqual(plugin["display_name"], plugin_contract["display_name"])
            self.assertEqual(plugin["description"], plugin_contract["description"])
            self.assertEqual(plugin["mcp_servers_declared"], plugin_contract["declared_mcp_servers"])
            self.assertEqual(plugin["apps_declared"], plugin_contract["declared_app_ids"])
            self.assertEqual(plugin["skills_declared"], plugin_contract["declared_skills"])

            icon, warnings, notes = resolve_plugin_icon_metadata(
                plugin=plugin,
                source_catalog={"kind": "local", "source_path": str(FIXTURE_ROOT)},
                runtime_roots={"codex_home_root": str(codex_home), "workspace_runtime_cwd": str(FIXTURE_ROOT), "project_runtime_root": str(FIXTURE_ROOT)},
                search_roots=[FIXTURE_ROOT],
            )

        self.assertEqual(_scan_plugin_source_for_raw_secrets(plugin_root), [str(path) for path in sorted(path for path in plugin_root.rglob("*") if path.is_file() and path.suffix.lower() in {".json"})])
        self.assertIsNotNone(icon)
        self.assertEqual(icon["provenance_kind"], "bundled_local")
        self.assertTrue(icon["validated"])
        self.assertIn("manifest_local_icon", notes)
        self.assertEqual(warnings, [])

        mcp_payload = _load_json(plugin_root / ".codex-plugin" / "plugin.json")
        server_payload = mcp_payload["mcpServers"]["astrabridge_fixture_echo"]
        self.assertEqual(server_payload["command"], "node")
        self.assertNotIn("url", server_payload)

    def test_fixture_project_preset_reference_contract_normalizes(self) -> None:
        contract = _load_json(CONTRACT_PATH)
        preset_contract = contract["project_preset_reference"]

        state = normalize_project_plugin_skill_presets(None)
        state = mutate_project_plugin_skill_presets(
            state,
            operation="add_plugin",
            preset_id=preset_contract["preset_id"],
            plugin_ref=preset_contract["plugin_ref"],
        )
        state = mutate_project_plugin_skill_presets(
            state,
            operation="add_skill",
            preset_id=preset_contract["preset_id"],
            skill_ref=preset_contract["skill_ref"],
        )
        active = active_project_plugin_skill_preset(state)

        self.assertEqual(active["preset_id"], "project-default")
        self.assertEqual(active["plugin_refs"][0], preset_contract["plugin_ref"])
        self.assertEqual(active["skill_refs"][0], preset_contract["skill_ref"])
        self.assertTrue(active["plugin_refs"][0]["source_catalog_id"].startswith("fixture::"))
        self.assertEqual(active["skill_refs"][0]["owner_plugin_id"], "astrabridge-dogfood-fixture")


if __name__ == "__main__":
    unittest.main()
