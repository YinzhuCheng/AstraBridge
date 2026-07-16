from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from astrabridge_sidecar.coding_kernel.turn_loop import RuntimeToolFacade
from astrabridge_sidecar.model_catalog import model_catalog_entry
from astrabridge_sidecar.providers.ir import ToolCall
from astrabridge_sidecar.providers.tooling import (
    assess_model_authority,
    enforce_tool_message_sequence,
    normalize_tool_calls,
    sanitize_function_parameters,
    sanitize_tool_definitions,
)
from astrabridge_sidecar.runtime_config_service import RuntimeConfigService


def _moonshot_required_properties_error(parameters: dict[str, object]) -> str:
    # Moonshot rejects function schemas whose required fields are missing from properties.
    properties = parameters.get("properties")
    required = parameters.get("required")
    if not isinstance(properties, dict):
        return "properties must be an object"
    if not isinstance(required, list):
        return ""
    for name in required:
        field_name = str(name or "").strip()
        if field_name and field_name not in properties:
            return f"required property '{field_name}' is not defined in properties."
    return ""


class ToolCallCompatibilityTests(unittest.TestCase):
    def test_normalize_tool_calls_repairs_malformed_args_missing_ids_and_duplicate_ids(self) -> None:
        calls, warnings = normalize_tool_calls(
            [
                {
                    "name": "apply_patch",
                    "arguments": "```json\n{\"path\": README.md}\n```",
                },
                {
                    "id": "call_dup",
                    "function": {"name": "read_file", "arguments": {"path": "README.md"}},
                },
                {
                    "id": "call_dup",
                    "function": {"name": "read_file", "arguments": '{"path":"PLAN.md"}'},
                },
            ],
            allow_parallel=True,
        )

        self.assertEqual(len(calls), 3)
        self.assertTrue(str(calls[0]["id"]).startswith("call_"))
        self.assertEqual(str((calls[0].get("function") or {}).get("arguments") or ""), "{\"raw\":\"{\\\"path\\\": README.md}\"}")
        self.assertEqual(calls[1]["id"], "call_dup")
        self.assertNotEqual(calls[2]["id"], "call_dup")
        self.assertTrue(any("fenced tool-call arguments" in warning.lower() for warning in warnings))
        self.assertTrue(any("wrapped malformed tool-call arguments" in warning.lower() for warning in warnings))
        self.assertTrue(any("assigned deterministic tool call id" in warning.lower() for warning in warnings))
        self.assertTrue(any("repaired duplicate tool call id" in warning.lower() for warning in warnings))

    def test_normalize_tool_calls_drops_parallel_calls_for_serial_only_models(self) -> None:
        calls, warnings = normalize_tool_calls(
            [
                {"id": "call_1", "function": {"name": "read_file", "arguments": '{"path":"README.md"}'}},
                {"id": "call_2", "function": {"name": "read_file", "arguments": '{"path":"PLAN.md"}'}},
            ],
            allow_parallel=False,
        )

        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["id"], "call_1")
        self.assertTrue(any("dropped extra parallel tool calls" in warning.lower() for warning in warnings))

    def test_enforce_tool_message_sequence_repairs_orphan_results_and_missing_tool_outputs(self) -> None:
        repaired, warnings = enforce_tool_message_sequence(
            [
                {"role": "tool", "tool_call_id": "orphan_1", "content": "stale output"},
                {
                    "role": "assistant",
                    "content": "Need two tool calls.",
                    "tool_calls": [{"id": "call_1"}, {"id": "call_2"}],
                },
                {"role": "tool", "tool_call_id": "call_1", "content": "done"},
            ]
        )

        self.assertEqual(repaired[0]["role"], "user")
        self.assertIn("[orphan tool output for orphan_1]", str(repaired[0]["content"]))
        self.assertEqual(repaired[-1]["role"], "tool")
        self.assertEqual(repaired[-1]["tool_call_id"], "call_2")
        self.assertIn("Tool result was unavailable in Codex history", str(repaired[-1]["content"]))
        self.assertTrue(any("orphan tool result" in warning.lower() for warning in warnings))
        self.assertTrue(any("missing tool_call_id call_2" in warning.lower() for warning in warnings))

    def test_unsupported_apply_patch_surface_does_not_promote_model_authority(self) -> None:
        authority = assess_model_authority(
            {
                "codex_agent_enabled": True,
                "supports_mcp_tools": False,
                "mcp_tool_call_policy": "conservative",
                "apply_patch_tool_type": "yaml",
                "tool_mode": "full",
            }
        )

        self.assertEqual(authority.tier, "C")
        self.assertEqual(authority.parallel_tool_call_status, "disabled")
        self.assertTrue(any("tool calling is unavailable or unverified" in warning.lower() for warning in authority.ui_warnings))

    def test_partial_command_execution_status_surfaces_runtime_warning(self) -> None:
        authority = assess_model_authority(
            {
                "codex_agent_enabled": True,
                "supports_mcp_tools": True,
                "mcp_tool_call_policy": "conservative",
                "apply_patch_tool_type": "json",
                "tool_mode": "full",
                "command_execution_status": "partial_no_command_execution",
                "command_execution_note": "Runtime turn completed but no commandExecution event was observed.",
            }
        )

        self.assertEqual(authority.command_execution_status, "partial_no_command_execution")
        self.assertEqual(authority.command_execution_note, "Runtime turn completed but no commandExecution event was observed.")
        self.assertTrue(any("observable command execution" in warning.lower() for warning in authority.ui_warnings))
        self.assertTrue(any("no commandexecution event was observed" in warning.lower() for warning in authority.ui_warnings))

    def test_runtime_tool_facade_tier_b_is_preview_only(self) -> None:
        tools = SimpleNamespace(
            edit_preview=lambda arguments: {"ok": True, "path": arguments.get("path"), "preview": {"changed": True, "diff": "+ok"}},
            edit_apply=lambda arguments: {"ok": True, "arguments": arguments},
            run_command=lambda arguments: {"ok": True, "arguments": arguments},
            create_checkpoint=lambda arguments: {"ok": True, "arguments": arguments},
        )
        facade = RuntimeToolFacade(
            tools,
            profile_id="deepseek-default",
            provider_id="deepseek",
            model_id="deepseek-v4-pro",
            authority=SimpleNamespace(tier="B"),
            permission_mode="auto",
            thread_id="thread-deepseek",
            turn_id="turn-deepseek",
        )

        tool_names = [str((item.get("function") or {}).get("name") or "") for item in facade.tool_definitions()]
        self.assertIn("edit_preview", tool_names)
        self.assertNotIn("create_checkpoint", tool_names)
        self.assertNotIn("edit_apply", tool_names)
        self.assertNotIn("run_command", tool_names)
        self.assertNotIn("run_tests", tool_names)

        arguments, result, extra_items, tool_item = facade.execute(
            ToolCall(id="call-preview", name="edit_preview", arguments_json='{"path":"scorecard.py","content":"print(1)\\n"}')
        )
        self.assertEqual(arguments["path"], "scorecard.py")
        self.assertTrue(result["ok"])
        self.assertTrue(extra_items)
        self.assertEqual(tool_item["tool"], "edit_preview")

        with self.assertRaisesRegex(ValueError, "not allowed to apply workspace edits"):
            facade.execute(ToolCall(id="call-apply", name="edit_apply", arguments_json='{"path":"scorecard.py","content":"print(2)\\n"}'))
        with self.assertRaisesRegex(ValueError, "not allowed to execute commands"):
            facade.execute(ToolCall(id="call-cmd", name="run_command", arguments_json='{"command":"pytest -q"}'))
        with self.assertRaisesRegex(ValueError, "not allowed to create checkpoints"):
            facade.execute(ToolCall(id="call-save", name="create_checkpoint", arguments_json='{"description":"blocked"}'))

    def test_moonshot_contract_fixture_reproduces_required_field_missing_from_properties(self) -> None:
        parameters = {
            "type": "object",
            "properties": {
                "cwd": {"type": "string"},
                "timeout_seconds": {"type": "integer"},
            },
            "required": ["command"],
            "additionalProperties": False,
        }

        self.assertEqual(
            _moonshot_required_properties_error(parameters),
            "required property 'command' is not defined in properties.",
        )

    def test_sanitize_function_parameters_keeps_named_properties_for_shell_tools(self) -> None:
        parameters, removed = sanitize_function_parameters(
            {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "$schema": "bad"},
                    "cwd": {"type": "string"},
                    "timeout_seconds": {"type": "integer"},
                },
                "required": ["command"],
                "$schema": "https://json-schema.org/draft/2020-12/schema",
            }
        )

        self.assertEqual(_moonshot_required_properties_error(parameters), "")
        self.assertIn("$schema", removed)
        self.assertEqual(parameters["required"], ["command"])
        self.assertIn("command", parameters["properties"])
        self.assertEqual(parameters["properties"]["command"]["type"], "string")
        self.assertNotIn("$schema", json.dumps(parameters, ensure_ascii=False))

    def test_sanitize_tool_definitions_accepts_nested_function_shape(self) -> None:
        sanitized, warnings = sanitize_tool_definitions(
            [
                {
                    "type": "function",
                    "function": {
                        "name": "run_command",
                        "description": "Run a bounded command.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "command": {"type": "string", "$schema": "bad"},
                                "cwd": {"type": "string"},
                            },
                            "required": ["command"],
                            "$schema": "https://json-schema.org/draft/2020-12/schema",
                        },
                    },
                }
            ]
        )

        self.assertEqual(len(sanitized), 1)
        function = sanitized[0]["function"]
        self.assertEqual(function["name"], "run_command")
        self.assertEqual(_moonshot_required_properties_error(function["parameters"]), "")
        self.assertIn("command", function["parameters"]["properties"])
        self.assertTrue(any("run_command" in warning for warning in warnings))

    def test_native_kernel_run_command_schema_matches_kimi_compatible_required_shape(self) -> None:
        facade = RuntimeToolFacade(
            SimpleNamespace(),
            profile_id="kimi-default",
            provider_id="kimi",
            model_id="kimi-k2.6",
            authority=SimpleNamespace(tier="A"),
            permission_mode="auto",
            thread_id="thread-kimi",
            turn_id="turn-kimi",
        )

        run_command = next(
            item
            for item in facade.tool_definitions()
            if str((item.get("function") or {}).get("name") or "") == "run_command"
        )
        parameters = dict((run_command.get("function") or {}).get("parameters") or {})

        self.assertEqual(_moonshot_required_properties_error(parameters), "")
        self.assertEqual(parameters.get("type"), "object")
        self.assertEqual(parameters.get("required"), ["command"])
        self.assertIn("command", dict(parameters.get("properties") or {}))
        self.assertIn("cwd", dict(parameters.get("properties") or {}))
        self.assertIn("timeout_seconds", dict(parameters.get("properties") or {}))
        self.assertEqual(dict(parameters.get("properties") or {})["command"]["type"], "string")

    def test_runtime_status_and_catalog_keep_apply_patch_mapping_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            service = RuntimeConfigService(
                root / "codex_home",
                configured_models_resolver=lambda: [
                    {
                        "id": "compat/compat-model",
                        "provider": "compat",
                        "native_model": "compat-model",
                        "display_name": "Compat Model",
                        "apply_patch_tool_type": "json",
                        "supports_mcp_tools": True,
                        "mcp_tool_call_policy": "conservative",
                    }
                ],
            )

            status = service.prepare_profile(
                {
                    "profile_id": "compat-profile",
                    "label": "Compat",
                    "provider_id": "compat",
                    "base_url": "https://compat.example/v1",
                    "model": "compat-model",
                    "reasoning_effort": "high",
                    "wire_api": "chat",
                    "env_key": "TEST_COMPAT_PROVIDER_KEY",
                    "auth_mode": "env_ref",
                    "proxy_mode": "direct",
                    "proxy_url": "",
                },
                require_secret=False,
            )

            self.assertEqual(status["apply_patch_tool_type"], "json")
            self.assertEqual(status["codex_apply_patch_tool_type"], "freeform")
            self.assertEqual(status["apply_patch_mapping_status"], "json_to_codex_freeform")

            catalog = json.loads((root / "codex_home" / "models" / "astrabridge-models.json").read_text(encoding="utf-8"))
            self.assertEqual(catalog["models"][0]["apply_patch_tool_type"], "freeform")

    def test_runtime_catalog_exports_none_instead_of_off_reasoning_label(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            service = RuntimeConfigService(
                root / "codex_home",
                configured_models_resolver=lambda: [
                    {
                        "id": "compat/compat-model",
                        "provider": "compat",
                        "native_model": "compat-model",
                        "display_name": "Compat Model",
                        "supported_reasoning_levels": ["off", "high"],
                        "default_reasoning_level": "off",
                    }
                ],
            )

            service.prepare_profile(
                {
                    "profile_id": "compat-profile",
                    "label": "Compat",
                    "provider_id": "compat",
                    "base_url": "https://compat.example/v1",
                    "model": "compat-model",
                    "reasoning_effort": "off",
                    "wire_api": "chat",
                    "env_key": "TEST_COMPAT_PROVIDER_KEY",
                    "auth_mode": "env_ref",
                    "proxy_mode": "direct",
                    "proxy_url": "",
                },
                require_secret=False,
            )

            catalog = json.loads((root / "codex_home" / "models" / "astrabridge-models.json").read_text(encoding="utf-8"))
            model = catalog["models"][0]
            self.assertEqual(model["default_reasoning_level"], "none")
            exported_efforts = [item["effort"] for item in model["supported_reasoning_levels"]]
            exported_reasoning_efforts = [item["reasoningEffort"] for item in model["supportedReasoningEfforts"]]
            self.assertIn("none", exported_efforts)
            self.assertIn("high", exported_efforts)
            self.assertNotIn("off", exported_efforts)
            self.assertEqual(exported_reasoning_efforts, exported_efforts)
            self.assertNotIn('"off"', json.dumps(model, ensure_ascii=False))
            self.assertNotIn('"max"', json.dumps(model, ensure_ascii=False))

    def test_catalog_entry_keeps_unsupported_apply_patch_models_out_of_tier_a(self) -> None:
        entry = model_catalog_entry(
            model_id="custom/custom-model",
            provider_id="custom",
            native_model="custom-model",
            display_name="Custom Model",
            context_window=128000,
            configured_model={
                "apply_patch_tool_type": "yaml",
                "tool_mode": "full",
                "mcp_tool_call_policy": "conservative",
            },
        )

        self.assertEqual(entry["authority_tier"], "C")
        self.assertIn("unsupported_apply_patch_tool_type", entry["runtime_provider_contract"]["validation"]["warnings"])


if __name__ == "__main__":
    unittest.main()
