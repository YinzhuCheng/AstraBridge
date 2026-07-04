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


if __name__ == "__main__":
    unittest.main()
