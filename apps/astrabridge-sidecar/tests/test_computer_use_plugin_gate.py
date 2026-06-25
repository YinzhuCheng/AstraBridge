from __future__ import annotations

import tempfile
import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from astrabridge_sidecar.app_server_client import app_server_command
from astrabridge_sidecar.runtime_config_service import RuntimeConfigService


def _has_disable_pair(command: list[str], feature: str) -> bool:
    return any(left == "--disable" and right == feature for left, right in zip(command, command[1:]))


def _profile() -> dict[str, object]:
    return {
        "profile_id": "unit-provider",
        "label": "Unit Provider",
        "provider_id": "unit",
        "base_url": "https://example.invalid/v1",
        "model": "unit-model",
        "reasoning_effort": "auto",
        "wire_api": "responses",
        "env_key": "UNIT_PROVIDER_KEY",
        "auth_mode": "session_paste",
        "proxy_mode": "direct",
        "proxy_url": "",
    }


class ComputerUsePluginGateTests(unittest.TestCase):
    def test_app_server_command_keeps_plugins_disabled_by_default(self) -> None:
        command = app_server_command()

        self.assertTrue(_has_disable_pair(command, "plugins"))
        self.assertTrue(_has_disable_pair(command, "plugin_sharing"))
        self.assertTrue(_has_disable_pair(command, "remote_plugin"))

    def test_app_server_command_allows_only_local_plugins_for_cua(self) -> None:
        command = app_server_command(allow_plugins=True)

        self.assertFalse(_has_disable_pair(command, "plugins"))
        self.assertTrue(_has_disable_pair(command, "plugin_sharing"))
        self.assertTrue(_has_disable_pair(command, "remote_plugin"))

    def test_runtime_config_can_temporarily_enable_computer_use_plugins(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            service = RuntimeConfigService(Path(temp) / "codex_home")

            default_status = service.prepare_profile(_profile(), require_secret=False)
            default_config = (Path(temp) / "codex_home" / "config.toml").read_text(encoding="utf-8")
            self.assertFalse(default_status["computer_use_plugins_enabled"])
            self.assertIn("plugins = false", default_config)

            cua_status = service.prepare_profile(
                _profile(),
                require_secret=False,
                enable_computer_use_plugins=True,
            )
            cua_config = (Path(temp) / "codex_home" / "config.toml").read_text(encoding="utf-8")
            self.assertTrue(cua_status["computer_use_plugins_enabled"])
            self.assertIn("plugins = true", cua_config)
            self.assertIn("plugin_sharing = false", cua_config)
            self.assertIn("remote_plugin = false", cua_config)
            self.assertNotEqual(service.runtime_signature(default_status), service.runtime_signature(cua_status))


if __name__ == "__main__":
    unittest.main()
