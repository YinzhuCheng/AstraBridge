from __future__ import annotations

import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from astrabridge_sidecar.astrabridge_capabilities_mcp_server import _call_tool, _tools
from astrabridge_sidecar.capabilities.runtime import CapabilityRuntime
from astrabridge_sidecar.mcp_server_core import McpStdioFramingState, read_stdio_message, write_stdio_message
from astrabridge_sidecar.mcp_config_service import astrabridge_capabilities_preset
from astrabridge_sidecar.modal_service import ModalService
from astrabridge_sidecar.profile_service import ProfileService
from astrabridge_sidecar.project_service import ProjectService
from astrabridge_sidecar.router_config_service import RouterConfigService
from astrabridge_sidecar.runtime_service import RuntimeService


class CapabilityMcpServerTests(unittest.TestCase):
    def test_capability_mcp_tools_cover_routes_and_model_backed_capabilities(self) -> None:
        names = {tool["name"] for tool in _tools()}

        self.assertEqual(
            names,
            {
                "astrabridge_capability_routes",
                "astrabridge_capability_image_generate",
                "astrabridge_capability_vision_analyze",
                "astrabridge_capability_speech_transcribe",
                "astrabridge_capability_speech_synthesize",
            },
        )

    def test_capability_preset_uses_local_python_stdio_server(self) -> None:
        preset = astrabridge_capabilities_preset()

        self.assertEqual(preset["name"], "astrabridge_capabilities")
        self.assertEqual(preset["transport"], "stdio")
        self.assertIn("astrabridge_capability_routes", preset["tools"])
        self.assertIn("DASHSCOPE_API_KEY", preset["env_vars"])
        self.assertIn("KIMI_API_KEY", preset["env_vars"])
        self.assertIn("MOONSHOT_API_KEY", preset["env_vars"])
        self.assertIn("YUNWU_API_KEY", preset["env_vars"])

    def test_shared_stdio_core_accepts_raw_json_mcp_framing(self) -> None:
        state = McpStdioFramingState()
        raw_request = b'{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}\n'
        message = read_stdio_message(io.BytesIO(raw_request), state=state)
        self.assertEqual(message["method"], "tools/list")

        output = io.BytesIO()
        write_stdio_message(output, {"jsonrpc": "2.0", "id": 1, "result": {"tools": []}}, state=state)
        self.assertTrue(output.getvalue().startswith(b"{"))
        self.assertTrue(output.getvalue().endswith(b"\n"))

    def test_capability_runtime_route_snapshot_and_mcp_routes_tool_are_available(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            profiles = ProfileService(store_path=root / "profiles.json")
            router_config = RouterConfigService(profiles, store_path=root / "router_config.json")
            runtime = CapabilityRuntime(router_config=router_config)

            snapshot = runtime.route_snapshot("vision.analyze")
            self.assertEqual(len(snapshot["routes"]), 1)
            self.assertEqual(snapshot["routes"][0]["capability_id"], "vision.analyze")
            self.assertTrue(snapshot["routes"][0]["resolved_candidate"])

            result = _call_tool(runtime, {"name": "astrabridge_capability_routes", "arguments": {"capability_id": "vision.analyze"}})
            text = result["content"][0]["text"]
            self.assertIn("vision.analyze", text)
            self.assertIn("resolved_candidate", text)

    def test_runtime_thread_start_registers_capability_dynamic_tools_when_enabled(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            runtime_root = root / ".runtime"
            runtime_root.mkdir()
            with patch.dict(os.environ, {"ASTRABRIDGE_RUNTIME_ROOT": str(runtime_root)}):
                projects = ProjectService(root / "recent.json")
                projects.create_project("Demo", root / "demo.abproj", workspace_root=workspace, entry_mode="existing")
                profiles = ProfileService(store_path=root / "profiles.json")
                router_config = RouterConfigService(profiles, store_path=root / "router_config.json")
                runtime = RuntimeService(
                    projects,
                    ModalService(projects.require_shell_state_root),
                    profile_service=profiles,
                    router_config_service=router_config,
                )
                runtime._mcp_config.enabled_servers = lambda: [{"name": "astrabridge_capabilities", "enabled": True}]  # type: ignore[method-assign]

                params = runtime._thread_start_params(  # noqa: SLF001
                    profile={"profile_id": "deepseek", "provider_id": "deepseek", "model": "deepseek-v4-pro"},
                    model="deepseek-v4-pro",
                    permission_mode="auto",
                )

                names = {tool["name"] for tool in params["dynamicTools"]}
                self.assertIn("astrabridge_capability_routes", names)
                self.assertIn("astrabridge_capability_image_generate", names)
                self.assertIn("astrabridge_capability_vision_analyze", names)
                self.assertIn("astrabridge_capability_speech_transcribe", names)
                self.assertIn("astrabridge_capability_speech_synthesize", names)


if __name__ == "__main__":
    unittest.main()
