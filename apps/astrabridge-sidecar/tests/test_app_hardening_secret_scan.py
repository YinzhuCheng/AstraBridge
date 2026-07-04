from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "scripts" / "app_hardening_secret_scan.py"

spec = importlib.util.spec_from_file_location("app_hardening_secret_scan", SCRIPT_PATH)
assert spec is not None and spec.loader is not None
app_hardening_secret_scan = importlib.util.module_from_spec(spec)
sys.modules["app_hardening_secret_scan"] = app_hardening_secret_scan
spec.loader.exec_module(app_hardening_secret_scan)


class AppHardeningSecretScanTests(unittest.TestCase):
    def write(self, root: Path, rel: str, text: str) -> None:
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def write_binary(self, root: Path, rel: str, content: bytes = b"png") -> None:
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    def run_check(self, root: Path, public_docs: list[str] | None = None) -> dict[str, object]:
        return app_hardening_secret_scan.check_repo(root, artifact_root="PRIVATE/app-hardening", public_docs=public_docs or [])

    def test_clean_layout_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.write(root, "PRIVATE/app-hardening/raw/trace.json", "{\"ok\": true}\n")
            self.write(root, "PRIVATE/app-hardening/reports/step18.md", "# ok\n")
            self.write(root, "PRIVATE/app-hardening/validations/step18.json", "{\"status\": \"pass\"}\n")
            self.write_binary(root, "PRIVATE/app-hardening/screenshots/final.png")
            self.write(root, "docs/SECURITY_AND_ISOLATION.md", "Preserve secret-safe artifacts only.\n")

            report = self.run_check(root, ["docs/SECURITY_AND_ISOLATION.md"])

            self.assertTrue(report["ok"])
            self.assertEqual(report["counts"]["error"], 0)

    def test_unexpected_bucket_is_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.write(root, "PRIVATE/app-hardening/tmp/leak.txt", "safe\n")

            report = self.run_check(root)

            self.assertFalse(report["ok"])
            self.assertEqual(report["findings"][0]["code"], "unexpected-artifact-bucket")

    def test_screenshot_text_file_is_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.write(root, "PRIVATE/app-hardening/screenshots/not-an-image.txt", "oops\n")

            report = self.run_check(root)

            self.assertFalse(report["ok"])
            self.assertEqual(report["findings"][0]["code"], "unexpected-screenshot-file")

    def test_secret_like_line_is_redacted_in_excerpt(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.write(root, "PRIVATE/app-hardening/raw/bad.json", "Authorization: Bearer abcdefghijklmnopqrstuvwxyz\n")

            report = self.run_check(root)

            self.assertFalse(report["ok"])
            self.assertEqual(report["findings"][0]["code"], "secret-like")
            self.assertNotIn("abcdefghijklmnopqrstuvwxyz", report["findings"][0]["excerpt"])
            self.assertIn("[REDACTED]", report["findings"][0]["excerpt"])

    def test_desktop_key_path_in_public_doc_is_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.write(root, "PRIVATE/app-hardening/raw/trace.json", "{\"ok\": true}\n")
            self.write(root, "docs/NOTE.md", r"Do not persist C:\Users\cyz19\Desktop\key.txt in docs.\n")

            report = self.run_check(root, ["docs/NOTE.md"])

            self.assertFalse(report["ok"])
            self.assertEqual(report["findings"][0]["code"], "desktop-key-path")
            self.assertIn("[REDACTED_DESKTOP_SECRET_PATH]", report["findings"][0]["excerpt"])

    def test_report_is_json_serializable(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.write(root, "PRIVATE/app-hardening/raw/trace.json", "{\"ok\": true}\n")
            self.write(root, "PRIVATE/app-hardening/reports/step18.md", "# ok\n")
            self.write(root, "PRIVATE/app-hardening/validations/step18.json", "{\"status\": \"pass\"}\n")
            self.write_binary(root, "PRIVATE/app-hardening/screenshots/final.png")

            report = self.run_check(root)
            encoded = json.dumps(report, ensure_ascii=False)

            self.assertIn("scanned_files", encoded)


if __name__ == "__main__":
    unittest.main()
