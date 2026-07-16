from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "scripts" / "repo_governance_check.py"

spec = importlib.util.spec_from_file_location("repo_governance_check", SCRIPT_PATH)
assert spec is not None and spec.loader is not None
repo_governance_check = importlib.util.module_from_spec(spec)
sys.modules["repo_governance_check"] = repo_governance_check
spec.loader.exec_module(repo_governance_check)


class RepoGovernanceCheckTests(unittest.TestCase):
    def run_check(self, root: Path) -> dict[str, object]:
        return repo_governance_check.check_repo(root)

    def write(self, root: Path, rel: str, text: str) -> None:
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def registry_entry(
        self,
        path: str,
        status: str,
        *,
        replacement: str | None = None,
    ) -> dict[str, object]:
        return {
            "path": path,
            "status": status,
            "owner": "test",
            "scope": "test fixture",
            "last_verified": "2026-07-10",
            "replacement": replacement,
            "archive_policy": "keep_in_place",
        }

    def write_registry(
        self,
        root: Path,
        entries: list[dict[str, object]],
        *,
        current_execution_plan: str | None = None,
    ) -> None:
        payload = {
            "schema_version": "astrabridge-document-registry-v1",
            "last_verified": "2026-07-10",
            "current_execution_plan": current_execution_plan,
            "conditional_execution_plans": [],
            "status_taxonomy": ["active", "complete", "superseded", "archived", "reference"],
            "entries": entries,
        }
        self.write(root, "docs/DOCUMENT_REGISTRY.json", json.dumps(payload, ensure_ascii=False))

    def test_clean_current_docs_pass(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.write(root, "README.md", "AstraBridge uses .abproj and workspace-local .astrabridge/ state.\n")
            self.write(root, "docs/archive/LEGACY_COMPATIBILITY_SHIMS.md", "Archived `.lcrproj` guardrail only.\n")

            report = self.run_check(root)

            self.assertTrue(report["ok"])
            self.assertEqual(report["counts"]["error"], 0)

    def test_mojibake_in_active_doc_is_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.write(root, "docs/BAD.md", "Broken text: Ã¦\n")

            report = self.run_check(root)

            self.assertFalse(report["ok"])
            self.assertEqual(report["counts"]["error"], 1)
            self.assertEqual(report["findings"][0]["code"], "mojibake")

    def test_mojibake_in_test_file_is_info(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.write(root, "apps/astrabridge-desktop/src/features/i18n/catalog.test.ts", "expect(text).not.toMatch(/[�]/)\n")

            report = self.run_check(root)

            self.assertTrue(report["ok"])
            self.assertEqual(report["counts"]["info"], 1)

    def test_legacy_marker_in_active_code_is_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.write(root, "apps/astrabridge-sidecar/astrabridge_sidecar/new_service.py", "PATH = '.lcrproj'\n")

            report = self.run_check(root)

            self.assertFalse(report["ok"])
            self.assertEqual(report["findings"][0]["code"], "legacy-marker")

    def test_generated_egg_info_is_not_a_source_audit_input(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.write(root, "apps/astrabridge-sidecar/astrabridge_sidecar.egg-info/SOURCES.txt", "astrabridge_sidecar/lcr_web_service.py\n")

            report = self.run_check(root)

            self.assertTrue(report["ok"])
            self.assertEqual(report["counts"]["error"], 0)
            self.assertEqual(report["scanned_files"], 0)

    def test_retired_runtime_symbol_in_active_code_is_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.write(root, "apps/astrabridge-sidecar/astrabridge_sidecar/new_service.py", "adapter = QwenResponsesAdapter()\n")

            report = self.run_check(root)

            self.assertFalse(report["ok"])
            self.assertEqual(report["counts"]["error"], 1)
            self.assertEqual(report["findings"][0]["code"], "retired-runtime-symbol")

    def test_retired_runtime_symbol_in_inventory_is_info(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.write(root, "scripts/interface_registry_audit.py", 'SYMBOL = "QwenResponsesAdapter"\n')

            report = self.run_check(root)

            self.assertTrue(report["ok"])
            self.assertEqual(report["counts"]["info"], 1)

    def test_legacy_marker_in_archive_is_allowed_info(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.write(root, "docs/archive/LEGACY_COMPATIBILITY_SHIMS.md", "The `.codex-shell` path is archived.\n")

            report = self.run_check(root)

            self.assertTrue(report["ok"])
            self.assertEqual(report["counts"]["info"], 1)

    def test_secret_like_string_is_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.write(root, "docs/BAD_SECRET.md", "Authorization: Bearer abcdefghijklmnopqrstuvwxyz\n")

            report = self.run_check(root)

            self.assertFalse(report["ok"])
            self.assertEqual(report["findings"][0]["code"], "secret-like")

    def test_report_is_json_serializable(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.write(root, "README.md", "AstraBridge current docs.\n")

            report = self.run_check(root)
            encoded = json.dumps(report, ensure_ascii=False)

            self.assertIn("scanned_files", encoded)

    def test_registry_rejects_unregistered_document(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.write(root, "docs/CURRENT.md", "Current guidance.\n")
            self.write_registry(
                root,
                [self.registry_entry("docs/DOCUMENT_REGISTRY.json", "active")],
            )

            report = self.run_check(root)

            self.assertFalse(report["ok"])
            self.assertIn("document-registry-unregistered", {item["code"] for item in report["findings"]})

    def test_registry_rejects_superseded_entry_without_replacement(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.write(root, "PLAN/OLD.md", "Historical plan.\n")
            self.write_registry(
                root,
                [
                    self.registry_entry("docs/DOCUMENT_REGISTRY.json", "active"),
                    self.registry_entry("PLAN/OLD.md", "superseded"),
                ],
            )

            report = self.run_check(root)

            self.assertFalse(report["ok"])
            self.assertIn("document-registry-replacement", {item["code"] for item in report["findings"]})

    def test_registered_current_doc_rejects_missing_local_link(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.write(root, "docs/CURRENT.md", "See [missing](MISSING.md).\n")
            self.write_registry(
                root,
                [
                    self.registry_entry("docs/DOCUMENT_REGISTRY.json", "active"),
                    self.registry_entry("docs/CURRENT.md", "reference"),
                ],
            )

            report = self.run_check(root)

            self.assertFalse(report["ok"])
            self.assertIn("current-doc-link-missing", {item["code"] for item in report["findings"]})

    def test_registered_active_plan_requires_guardrail_context_for_legacy_marker(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.write(root, "PLAN/CURRENT.md", "Use .lcrproj for project state.\n")
            self.write_registry(
                root,
                [
                    self.registry_entry("docs/DOCUMENT_REGISTRY.json", "active"),
                    self.registry_entry("PLAN/CURRENT.md", "active"),
                ],
                current_execution_plan="PLAN/CURRENT.md",
            )

            report = self.run_check(root)

            self.assertFalse(report["ok"])
            legacy = [item for item in report["findings"] if item["code"] == "legacy-marker"]
            self.assertEqual(len(legacy), 1)
            self.assertEqual(legacy[0]["severity"], "error")


if __name__ == "__main__":
    unittest.main()
