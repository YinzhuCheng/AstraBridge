from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from astrabridge_sidecar.agentic_updates import (
    AGENTIC_UPDATE_ARTIFACT_CONTRACT_SCHEMA_VERSION,
    ROLLBACK_TARGET_KINDS,
    RUN_FILE_RELATIVE_PATHS,
    RUN_SUBDIRECTORIES,
    agentic_update_artifact_contract,
    agentic_update_run_layout,
    ensure_agentic_update_run_layout,
    rollback_manifest_template,
    validate_agentic_update_artifact_path,
    validate_rollback_manifest,
)
from astrabridge_sidecar.security import SecurityError


class AgenticUpdateArtifactsTests(unittest.TestCase):
    def test_artifact_contract_documents_run_layout_and_preservation_policy(self) -> None:
        contract = agentic_update_artifact_contract()

        self.assertEqual(contract["schema_version"], AGENTIC_UPDATE_ARTIFACT_CONTRACT_SCHEMA_VERSION)
        self.assertEqual(contract["runs_root_relative"], "PRIVATE/agentic-update-pipeline/runs")
        self.assertEqual(contract["preservation_policy"]["directory_initialization"], "mkdir_only")
        self.assertFalse(contract["preservation_policy"]["delete_existing_evidence"])
        self.assertFalse(contract["preservation_policy"]["cleanup_required_before_new_run"])
        for directory in RUN_SUBDIRECTORIES:
            self.assertIn(directory, contract["subdirectories"])
        for key, relative_path in RUN_FILE_RELATIVE_PATHS.items():
            self.assertEqual(contract["files"][key], relative_path)
        for target_kind in ROLLBACK_TARGET_KINDS:
            self.assertIn(target_kind, contract["rollback_target_kinds"])

    def test_run_layout_paths_stay_under_private_run_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            layout = agentic_update_run_layout(workspace, "unit-run-001")
            run_root = Path(layout["run_root"]).resolve()
            private_root = workspace.resolve() / "PRIVATE" / "agentic-update-pipeline"

            self.assertEqual(run_root, private_root / "runs" / "unit-run-001")
            for path in list(layout["subdirectories"].values()) + list(layout["files"].values()):
                resolved = Path(path).resolve()
                resolved.relative_to(run_root)
            self.assertEqual(
                validate_agentic_update_artifact_path(workspace, "unit-run-001", "validation/report.json"),
                run_root / "validation" / "report.json",
            )

    def test_run_id_and_artifact_path_escape_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            for run_id in ("../outside", "bad/run", "bad\\run", "bad..run", ""):
                with self.subTest(run_id=run_id):
                    with self.assertRaises((SecurityError, ValueError)):
                        agentic_update_run_layout(workspace, run_id)

            for relative_path in ("../escape.json", "validation/../escape.json", "/abs/path.json"):
                with self.subTest(relative_path=relative_path):
                    with self.assertRaises(SecurityError):
                        validate_agentic_update_artifact_path(workspace, "unit-run-001", relative_path)

    def test_ensure_layout_is_mkdir_only_and_preserves_existing_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            first_layout = ensure_agentic_update_run_layout(workspace, "preserve-run")
            sentinel = Path(first_layout["run_root"]) / "validation" / "existing-report.json"
            sentinel.write_text('{"status":"keep"}', encoding="utf-8")

            second_layout = ensure_agentic_update_run_layout(workspace, "preserve-run")

            self.assertEqual(first_layout["run_root"], second_layout["run_root"])
            self.assertEqual(sentinel.read_text(encoding="utf-8"), '{"status":"keep"}')
            for directory in second_layout["subdirectories"].values():
                self.assertTrue(Path(directory).is_dir())

    def test_rollback_manifest_round_trips_through_json_validation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            ensure_agentic_update_run_layout(workspace, "rollback-run")
            manifest = rollback_manifest_template(
                "rollback-run",
                {
                    "scope": ["provider_metadata", "provider_adapter"],
                    "providers": ["qwen"],
                    "version_policy": "stable",
                    "apply_mode": "isolated_apply",
                    "allow_code_changes": True,
                },
                created_at="2026-07-05T00:00:00+00:00",
            )
            manifest["rollback_targets"]["router_config"].append(
                {
                    "target_id": "router-config",
                    "workspace_path": "apps/astrabridge-sidecar/router.json",
                    "backup_path": "rollback/backups/router-config/router.json",
                }
            )
            manifest["rollback_targets"]["metadata_sources"].append(
                {
                    "target_id": "provider-sources",
                    "workspace_path": "apps/astrabridge-sidecar/astrabridge_sidecar/providers/registry.py",
                    "backup_path": "rollback/backups/provider-sources/registry.py",
                }
            )
            manifest["rollback_targets"]["generated_catalog_locks"].append(
                {
                    "target_id": "generated-catalog-lock",
                    "workspace_path": "apps/astrabridge-sidecar/generated/catalog-lock.json",
                    "backup_path": "rollback/backups/generated-catalog-lock/catalog-lock.json",
                }
            )
            manifest["rollback_targets"]["changed_source_files"].append(
                {
                    "target_id": "transport-adapter",
                    "workspace_path": "apps/astrabridge-sidecar/astrabridge_sidecar/providers/transports/qwen_dashscope.py",
                    "backup_path": "rollback/backups/transport-adapter/qwen_dashscope.py",
                }
            )
            manifest["rollback_targets"]["ui_changes"].append(
                {
                    "target_id": "desktop-update-ui",
                    "workspace_path": "apps/astrabridge-desktop/src/features/updates/UpdatePanel.tsx",
                    "backup_path": "rollback/backups/desktop-update-ui/UpdatePanel.tsx",
                }
            )
            manifest["rollback_targets"]["codex_binary_locator_state"].append(
                {
                    "target_id": "codex-locator",
                    "workspace_path": "apps/astrabridge-sidecar/codex-locator.json",
                    "backup_path": "rollback/backups/codex-locator/codex-locator.json",
                }
            )
            manifest["steps"].append(
                {
                    "step_id": "restore-router-config",
                    "target_kind": "router_config",
                    "action": "restore_backup",
                    "status": "planned",
                    "workspace_path": "apps/astrabridge-sidecar/router.json",
                    "backup_path": "rollback/backups/router-config/router.json",
                }
            )
            manifest["evidence_paths"].append("rollback/rollback-manifest.json")

            round_tripped = json.loads(json.dumps(manifest, sort_keys=True))
            validated = validate_rollback_manifest(round_tripped, workspace_root=workspace)

            self.assertEqual(validated["run_id"], "rollback-run")
            self.assertTrue(validated["reversible"])
            self.assertFalse(validated["preservation_policy"]["delete_existing_evidence"])
            self.assertEqual(set(validated["rollback_targets"]), set(ROLLBACK_TARGET_KINDS))
            self.assertEqual(validated["steps"][0]["target_kind"], "router_config")

    def test_rollback_manifest_rejects_escape_paths_and_cleanup_policy(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            manifest = rollback_manifest_template(
                "rollback-run",
                {"scope": "provider_metadata", "version_policy": "stable"},
                created_at="2026-07-05T00:00:00+00:00",
            )
            manifest["evidence_paths"].append("../outside.json")
            with self.assertRaises(SecurityError):
                validate_rollback_manifest(manifest, workspace_root=workspace)

            manifest = rollback_manifest_template(
                "rollback-run",
                {"scope": "provider_metadata", "version_policy": "stable"},
                created_at="2026-07-05T00:00:00+00:00",
            )
            manifest["preservation_policy"]["delete_existing_evidence"] = True
            with self.assertRaises(ValueError):
                validate_rollback_manifest(manifest, workspace_root=workspace)


if __name__ == "__main__":
    unittest.main()
