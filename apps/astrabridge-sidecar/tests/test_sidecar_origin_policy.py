from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from astrabridge_sidecar.server import is_allowed_origin
from astrabridge_sidecar.sidecar_provenance import (
    build_sidecar_provenance,
    parse_windows_netstat_port_owner,
    redact_command_argv,
)


class SidecarOriginPolicyTests(unittest.TestCase):
    def test_allows_default_astrabridge_dev_and_tauri_origins(self) -> None:
        self.assertTrue(is_allowed_origin("http://127.0.0.1:4181"))
        self.assertTrue(is_allowed_origin("http://localhost:4181"))
        self.assertTrue(is_allowed_origin("http://tauri.localhost"))
        self.assertTrue(is_allowed_origin("tauri://localhost"))

    def test_rejects_unlisted_loopback_origins_by_default(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ASTRABRIDGE_ALLOW_ANY_LOOPBACK_ORIGIN", None)
            os.environ.pop("ASTRABRIDGE_ALLOWED_ORIGINS", None)
            self.assertFalse(is_allowed_origin("http://127.0.0.1:5173"))
            self.assertFalse(is_allowed_origin("http://localhost:5173"))

    def test_allows_configured_extra_origin(self) -> None:
        with patch.dict(os.environ, {"ASTRABRIDGE_ALLOWED_ORIGINS": "http://127.0.0.1:5173"}):
            self.assertTrue(is_allowed_origin("http://127.0.0.1:5173"))

    def test_loopback_wildcard_requires_explicit_debug_env(self) -> None:
        with patch.dict(os.environ, {"ASTRABRIDGE_ALLOW_ANY_LOOPBACK_ORIGIN": "1"}):
            self.assertTrue(is_allowed_origin("http://127.0.0.1:5173"))
            self.assertFalse(is_allowed_origin("https://example.com"))

    def test_current_source_provenance_is_detected_from_repo_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp) / "AstraBridge"
            source_root = repo / "apps" / "astrabridge-sidecar"
            source_root.mkdir(parents=True)
            (repo / ".git").mkdir()

            provenance = build_sidecar_provenance(
                listen_port=8839,
                source_root=source_root,
                cwd=repo,
                seed_root=repo,
                argv=["python", "-m", "astrabridge_sidecar.server", "--serve", "--port", "8839"],
                pid=2468,
                executable="python",
                port_owner={"status": "self", "method": "fixture", "pid": 2468, "listen_port": 8839},
                environ={},
            )

            self.assertEqual(provenance["schema_version"], "astrabridge-sidecar-provenance-v1")
            self.assertEqual(provenance["origin"], "current_source")
            self.assertEqual(provenance["launcher_mode"], "current_source")
            self.assertTrue(provenance["current_source_match"])
            self.assertEqual(provenance["source_root"], str(source_root.resolve()))
            self.assertEqual(provenance["listen_port"], 8839)

    def test_app_managed_provenance_can_be_declared_by_launcher_env(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            bundle_root = Path(temp) / "bundle"
            bundle_root.mkdir()
            provenance = build_sidecar_provenance(
                listen_port=8790,
                source_root=bundle_root,
                cwd=bundle_root,
                argv=["astrabridge-sidecar.exe", "--serve"],
                pid=1357,
                executable=str(bundle_root / "astrabridge-sidecar.exe"),
                port_owner={"status": "self", "method": "fixture", "pid": 1357, "listen_port": 8790},
                environ={"ASTRABRIDGE_SIDECAR_ORIGIN": "app-managed", "ASTRABRIDGE_LAUNCHER_MODE": "desktop-app-managed"},
            )

            self.assertEqual(provenance["origin"], "app_managed")
            self.assertEqual(provenance["launcher_mode"], "desktop-app-managed")
            self.assertFalse(provenance["current_source_match"])

    def test_command_line_redaction_masks_secret_arguments(self) -> None:
        argv = redact_command_argv(
            [
                "python",
                "-m",
                "astrabridge_sidecar.server",
                "--api-key",
                "unit-redaction-value",
                "--callback=https://example.test/ok?token=unit-query-value",
            ]
        )

        self.assertEqual(argv[3], "--api-key")
        self.assertEqual(argv[4], "[REDACTED]")
        self.assertEqual(argv[5], "--callback=[REDACTED]")
        self.assertNotIn("unit-redaction-value", " ".join(argv))
        self.assertNotIn("unit-query-value", " ".join(argv))

    def test_windows_netstat_owner_parser_finds_listening_pid(self) -> None:
        output = """
          Proto  Local Address          Foreign Address        State           PID
          TCP    127.0.0.1:8839         0.0.0.0:0              LISTENING       44220
          TCP    127.0.0.1:8840         0.0.0.0:0              ESTABLISHED     999
        """

        self.assertEqual(parse_windows_netstat_port_owner(output, listen_port=8839), 44220)
        self.assertIsNone(parse_windows_netstat_port_owner(output, listen_port=8840))


if __name__ == "__main__":
    unittest.main()
