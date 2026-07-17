from __future__ import annotations

import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SIDECAR_ROOT = REPO_ROOT / "apps" / "astrabridge-sidecar"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(SIDECAR_ROOT) not in sys.path:
    sys.path.insert(0, str(SIDECAR_ROOT))

from astrabridge_sidecar.mcp_node_policy import (  # noqa: E402
    McpToolPolicyDenied,
    authorize_mcp_tool_call,
    resolve_node_mcp_tool_policy,
)


class McpNodePolicyTests(unittest.TestCase):
    def test_resolve_node_mcp_tool_policy_intersects_graph_ceiling(self) -> None:
        policy = resolve_node_mcp_tool_policy(
            tools={
                "approval_mode": "ask",
                "allowed_tool_classes": [],
                "supports_mcp": False,
                "mcp_policy": {
                    "tool_rules": [
                        {
                            "server": "astrabridge_web",
                            "tools": ["astrabridge_web_search_batch", "astrabridge_web_fetch"],
                            "approval_mode": "allow",
                        },
                        {
                            "server": "astrabridge_capabilities",
                            "tools": ["astrabridge_capability_image_generate"],
                            "approval_mode": "allow",
                        },
                    ]
                },
            },
            graph_policy={
                "mcp_policy": {
                    "tool_rules": [
                        {
                            "server": "astrabridge_web",
                            "tools": ["astrabridge_web_search_batch"],
                            "approval_mode": "allow",
                        }
                    ]
                }
            },
            node_id="node_policy_test",
        )

        exposed = {(item["server"], item["tool"]) for item in policy["exposed_tools"]}
        self.assertEqual(exposed, {("astrabridge_web", "astrabridge_web_search_batch")})
        self.assertTrue(policy["graph_has_ceiling"])
        self.assertTrue(policy["fingerprint"])

    def test_authorize_mcp_tool_call_supports_ask_and_approval_reuse(self) -> None:
        policy = resolve_node_mcp_tool_policy(
            tools={
                "approval_mode": "ask",
                "allowed_tool_classes": [],
                "supports_mcp": False,
                "mcp_policy": {
                    "tool_rules": [
                        {
                            "server": "astrabridge_capabilities",
                            "tools": ["astrabridge_capability_image_generate"],
                            "approval_mode": "ask",
                            "budget": {"max_calls": 2},
                        }
                    ]
                },
            },
            node_id="node_policy_test",
        )

        first = authorize_mcp_tool_call(
            policy,
            server="astrabridge_capabilities",
            tool="astrabridge_capability_image_generate",
            arguments={"prompt": "render a prop"},
            caller="unit_test",
            state={"auto_bootstrap_approval": True, "tool_call_counts": {}, "approval_cache": {}},
            context={"run_id": "run-1", "node_id": "node-a", "attempt_count": 1},
        )
        self.assertEqual(first["decision"], "allow")
        self.assertEqual(first["approval_mode"], "ask")
        self.assertEqual(first["approval_decision"], "ask_auto_bootstrap")
        self.assertFalse(first["approval_reused"])
        self.assertEqual(first["budget"]["observed_calls_after"], 1)

        second = authorize_mcp_tool_call(
            policy,
            server="astrabridge_capabilities",
            tool="astrabridge_capability_image_generate",
            arguments={"prompt": "render a prop"},
            caller="unit_test",
            state={
                "tool_call_counts": {"astrabridge_capabilities::astrabridge_capability_image_generate": 1},
                "approval_cache": {"astrabridge_capabilities::astrabridge_capability_image_generate": {"approved_at": "2026-07-17T00:00:00+09:00"}},
            },
            context={"run_id": "run-1", "node_id": "node-a", "attempt_count": 1},
        )
        self.assertEqual(second["decision"], "allow")
        self.assertTrue(second["approval_reused"])
        self.assertEqual(second["approval_decision"], "approval_reused")
        self.assertEqual(second["budget"]["observed_calls_after"], 2)

    def test_authorize_mcp_tool_call_blocks_budget_exhaustion(self) -> None:
        policy = resolve_node_mcp_tool_policy(
            tools={
                "approval_mode": "allow",
                "allowed_tool_classes": [],
                "supports_mcp": False,
                "mcp_policy": {
                    "tool_rules": [
                        {
                            "server": "astrabridge_web",
                            "tools": ["astrabridge_web_search_batch"],
                            "approval_mode": "allow",
                            "budget": {"max_calls": 1},
                        }
                    ]
                },
            },
            node_id="node_policy_test",
        )

        with self.assertRaises(McpToolPolicyDenied) as denied:
            authorize_mcp_tool_call(
                policy,
                server="astrabridge_web",
                tool="astrabridge_web_search_batch",
                arguments={"query": "AstraBridge"},
                caller="unit_test",
                state={"tool_call_counts": {"astrabridge_web::astrabridge_web_search_batch": 1}},
                context={"run_id": "run-1", "node_id": "node-a", "attempt_count": 2},
            )
        self.assertEqual(denied.exception.decision["reason"], "budget_exhausted")

    def test_authorize_mcp_tool_call_blocks_resource_uri_escape(self) -> None:
        policy = resolve_node_mcp_tool_policy(
            tools={
                "approval_mode": "allow",
                "allowed_tool_classes": [],
                "supports_mcp": False,
                "mcp_policy": {
                    "tool_rules": [
                        {
                            "server": "astrabridge_web",
                            "tools": ["astrabridge_web_fetch"],
                            "approval_mode": "allow",
                            "resource_uri_patterns": ["workspace://PRIVATE/provider-smoke/*"],
                        }
                    ]
                },
            },
            node_id="node_policy_test",
        )

        with self.assertRaises(McpToolPolicyDenied) as denied:
            authorize_mcp_tool_call(
                policy,
                server="astrabridge_web",
                tool="astrabridge_web_fetch",
                arguments={"resource_uri": "workspace://.astrabridge/research/outside.json"},
                caller="unit_test",
                state={},
                context={"run_id": "run-1", "node_id": "node-a", "attempt_count": 1},
            )
        self.assertEqual(denied.exception.decision["reason"], "resource_uri_not_allowlisted")

    def test_authorize_mcp_tool_call_denies_undeclared_tool(self) -> None:
        policy = resolve_node_mcp_tool_policy(
            tools={
                "approval_mode": "allow",
                "allowed_tool_classes": [],
                "supports_mcp": False,
                "mcp_policy": {
                    "tool_rules": [
                        {
                            "server": "astrabridge_web",
                            "tools": ["astrabridge_web_search_batch"],
                            "approval_mode": "allow",
                        }
                    ]
                },
            },
            node_id="node_policy_test",
        )

        with self.assertRaises(McpToolPolicyDenied) as denied:
            authorize_mcp_tool_call(
                policy,
                server="astrabridge_web",
                tool="astrabridge_web_fetch",
                arguments={"query": "AstraBridge"},
                caller="unit_test",
                state={},
                context={"run_id": "run-1", "node_id": "node-a", "attempt_count": 1},
            )
        self.assertEqual(denied.exception.decision["reason"], "undeclared_tool")


if __name__ == "__main__":
    unittest.main()
