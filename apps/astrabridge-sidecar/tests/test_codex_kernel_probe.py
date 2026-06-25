from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from astrabridge_sidecar.codex_kernel_probe import (
    discover_codex_binary_and_version,
    parse_codex_version_text,
    resolve_codex_binary_metadata,
)
from astrabridge_sidecar.wsl_dependency_service import ASTRABRIDGE_WSL_BIN


class CodexKernelProbeTests(unittest.TestCase):
    def test_windows_env_override_is_preferred_for_binary_and_version(self) -> None:
        commands: list[list[str]] = []

        def fake_run(command: list[str]) -> dict[str, object]:
            commands.append(command)
            return {"returncode": 0, "stdout": "codex-cli 0.137.0\n", "stderr": ""}

        probe = discover_codex_binary_and_version(
            execution_host="windows",
            environ={"ASTRABRIDGE_CODEX_BIN": r"D:\Tools\OpenAI\Codex\bin\codex.EXE"},
            which_resolver=lambda name: None,
            run_version=fake_run,
        )

        self.assertEqual(probe["path"], r"D:\Tools\OpenAI\Codex\bin\codex.EXE")
        self.assertEqual(probe["path_source"], "env_override")
        self.assertEqual(probe["launch_descriptor"], r"D:\Tools\OpenAI\Codex\bin\codex.EXE")
        self.assertEqual(probe["version_semver"], "0.137.0")
        self.assertEqual(probe["version_parse_status"], "ok")
        self.assertEqual(commands, [[r"D:\Tools\OpenAI\Codex\bin\codex.EXE", "--version"]])

    def test_missing_windows_binary_reports_missing(self) -> None:
        probe = discover_codex_binary_and_version(
            execution_host="windows",
            environ={},
            which_resolver=lambda name: None,
            run_version=lambda command: {"returncode": 0, "stdout": "", "stderr": ""},
        )

        self.assertIsNone(probe["path"])
        self.assertEqual(probe["path_source"], "unknown")
        self.assertEqual(probe["version_parse_status"], "missing")
        self.assertIsNone(probe["version_semver"])

    def test_windows_path_from_which_is_used(self) -> None:
        probe = discover_codex_binary_and_version(
            execution_host="windows",
            environ={},
            which_resolver=lambda name: r"C:\Codex\codex.exe" if name == "codex" else None,
            run_version=lambda command: {"returncode": 0, "stdout": "0.140.1", "stderr": ""},
        )

        self.assertEqual(probe["path"], r"C:\Codex\codex.exe")
        self.assertEqual(probe["path_source"], "which")
        self.assertEqual(probe["version_semver"], "0.140.1")
        self.assertEqual(probe["version_parse_status"], "ok")

    def test_wsl_metadata_uses_default_path_and_distro(self) -> None:
        commands: list[list[str]] = []

        def fake_which(name: str) -> str | None:
            if name == "wsl.exe":
                return r"C:\Windows\System32\wsl.exe"
            return None

        def fake_run(command: list[str]) -> dict[str, object]:
            commands.append(command)
            return {"returncode": 0, "stdout": "codex-cli 0.137.0", "stderr": ""}

        probe = discover_codex_binary_and_version(
            execution_host="wsl",
            wsl_distro="Ubuntu-24.04",
            environ={},
            which_resolver=fake_which,
            run_version=fake_run,
        )

        self.assertEqual(probe["path"], ASTRABRIDGE_WSL_BIN)
        self.assertEqual(probe["path_source"], "wsl_default")
        self.assertEqual(probe["launch_descriptor"], f"wsl::Ubuntu-24.04::{ASTRABRIDGE_WSL_BIN}")
        self.assertEqual(probe["version_semver"], "0.137.0")
        self.assertEqual(probe["version_parse_status"], "ok")
        self.assertEqual(commands[0][0], r"C:\Windows\System32\wsl.exe")
        self.assertEqual(commands[0][1:4], ["-d", "Ubuntu-24.04", "bash"])
        self.assertIn("--version", commands[0][-1])
        self.assertIn("$HOME/.local/share/astrabridge/bin/codex", commands[0][-1])

    def test_parse_failure_reports_unparseable(self) -> None:
        probe = discover_codex_binary_and_version(
            execution_host="windows",
            environ={"ASTRABRIDGE_CODEX_BIN": r"D:\Codex\codex.exe"},
            which_resolver=lambda name: None,
            run_version=lambda command: {"returncode": 0, "stdout": "codex version unknown", "stderr": ""},
        )

        self.assertEqual(probe["version_parse_status"], "unparseable")
        self.assertIsNone(probe["version_semver"])

    def test_parse_codex_version_text_accepts_plain_and_prefixed_versions(self) -> None:
        self.assertEqual(parse_codex_version_text("codex-cli 0.137.0"), "0.137.0")
        self.assertEqual(parse_codex_version_text("0.140.1"), "0.140.1")
        self.assertIsNone(parse_codex_version_text("version unknown"))

    def test_resolve_codex_binary_metadata_preserves_wsl_env_override(self) -> None:
        metadata = resolve_codex_binary_metadata(
            execution_host="wsl",
            wsl_distro="Ubuntu",
            environ={"ASTRABRIDGE_WSL_CODEX_BIN": "$HOME/custom/bin/codex"},
            which_resolver=lambda name: None,
        )

        self.assertEqual(metadata["path"], "$HOME/custom/bin/codex")
        self.assertEqual(metadata["path_source"], "env_override")
        self.assertEqual(metadata["launch_descriptor"], "wsl::Ubuntu::$HOME/custom/bin/codex")


if __name__ == "__main__":
    unittest.main()
