from __future__ import annotations

import copy
import hashlib
import json
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from astrabridge_sidecar.agent_orchestration_file_format import (  # noqa: E402
    agent_orchestration_example_catalog,
)
from astrabridge_sidecar.external_a2a_gateway import (  # noqa: E402
    EXTERNAL_A2A_AGENT_CARD_REGISTRY_SCHEMA_VERSION,
    EXTERNAL_A2A_CARD_REF_PREFIX,
)
from astrabridge_sidecar.skill_orchestration_validation import load_skill_orchestration_manifest  # noqa: E402
from astrabridge_sidecar.skill_provider_a2a_binding import (  # noqa: E402
    SKILL_PROVIDER_A2A_BINDING_SCHEMA_VERSION,
    bind_skill_provider_a2a,
)


class SkillProviderA2ABindingTests(unittest.TestCase):
    def test_candidate_skills_bind_bounded_routes_with_explicit_downgrade_states(self) -> None:
        catalog = agent_orchestration_example_catalog()
        template_map = {
            "supervisor_worker_synthesizer": "supervisor_worker_synthesizer",
            "code_fix_test_review": "code_fix_review",
            "fanout_fanin_research": "fanout_research_synthesis",
            "provider_update_smoke_gate": "provider_update_smoke",
            "multimodal_capability_adapter": "multimodal_capability_adapter",
        }
        for manifest_path in sorted(Path(__file__).resolve().parents[1].joinpath("skills").glob("*/orchestration-manifest.json")):
            manifest = load_skill_orchestration_manifest(manifest_path)
            graph = catalog[template_map[str(manifest["resolution"]["graph_template_ref"])]]
            with self.subTest(skill_id=manifest["skill_id"]):
                report = bind_skill_provider_a2a(manifest, graph)
                self.assertEqual(report["schema_version"], SKILL_PROVIDER_A2A_BINDING_SCHEMA_VERSION)
                self.assertIn(report["status"], {"downgraded", "qualified"})
                self.assertEqual(report["blockers"], [])
                self.assertEqual(report["provenance"]["provider_calls"], 0)
                self.assertEqual(report["provenance"]["network_discovery_calls"], 0)

    def test_provider_qualified_fixture_requires_verified_catalog_capability_and_profile_binding(self) -> None:
        manifest = load_skill_orchestration_manifest("astrabridge-supervisor-worker-synthesizer")
        manifest["status"] = "provider-qualified"
        manifest["evidence"]["required_level"] = "provider-qualified"
        manifest["policies"]["routing"]["profile_ids"] = ["qwen-default"]
        graph = copy.deepcopy(agent_orchestration_example_catalog()["supervisor_worker_synthesizer"])
        for node in graph["nodes"]:
            if str(node["routing"].get("selection_mode")) == "explicit":
                node["routing"]["model_id"] = "qwen3.7-plus"
        configured_models = [_verified_model("qwen", "qwen3.7-plus")]
        report = bind_skill_provider_a2a(
            manifest,
            graph,
            configured_models=configured_models,
            profile_records=[
                {
                    "profile_id": "qwen-default",
                    "provider_id": "qwen",
                    "model": "qwen3.7-plus",
                }
            ],
        )
        self.assertEqual(report["status"], "qualified")
        self.assertEqual(report["blockers"], [])
        self.assertTrue(all(item["profile_id"] == "qwen-default" for item in report["route_results"] if item["status"] == "qualified"))
        self.assertTrue(all(item["capability_status"] == "qualified" for item in report["route_results"] if item["status"] == "qualified"))

    def test_route_outside_skill_allowlist_is_blocked_without_provider_calls(self) -> None:
        manifest = load_skill_orchestration_manifest("astrabridge-supervisor-worker-synthesizer")
        graph = copy.deepcopy(agent_orchestration_example_catalog()["supervisor_worker_synthesizer"])
        graph["nodes"][0]["routing"]["provider_id"] = "glm"
        graph["nodes"][0]["routing"]["model_id"] = "glm-5.2"
        report = bind_skill_provider_a2a(manifest, graph)
        self.assertEqual(report["status"], "blocked")
        self.assertTrue(any("provider_not_in_skill_allowlist" in item for item in report["blockers"]))
        self.assertEqual(report["provenance"]["provider_calls"], 0)

    def test_external_a2a_qualified_fixture_uses_gateway_snapshot_and_conformance_kit(self) -> None:
        manifest = load_skill_orchestration_manifest("astrabridge-supervisor-worker-synthesizer")
        manifest["status"] = "external-a2a-qualified"
        manifest["evidence"]["required_level"] = "external-a2a-qualified"
        manifest["policies"]["a2a"] = {
            "external_enabled": True,
            "allowed_card_refs": [f"{EXTERNAL_A2A_CARD_REF_PREFIX}geo_route"],
            "minimum_trust_level": "pinned",
            "gateway_required": True,
        }
        graph = copy.deepcopy(agent_orchestration_example_catalog()["code_fix_review"])
        graph["nodes"][0]["card_ref"] = f"{EXTERNAL_A2A_CARD_REF_PREFIX}geo_route"
        graph["external_agent_card_registry"] = _registry(trust_level="pinned")
        report = bind_skill_provider_a2a(
            manifest,
            graph,
            configured_models=[_verified_model("qwen", "qwen3-coder-plus")],
        )
        self.assertEqual(report["status"], "qualified")
        self.assertEqual(report["blockers"], [])
        gateway = report["external_a2a"]["gateway_snapshot"]
        self.assertEqual(gateway["verification_state"], "verified")
        self.assertIn("a2a_card:geo_route", gateway["routable_card_refs"])
        self.assertEqual(report["external_a2a"]["conformance"]["network_calls"], 0)

    def test_external_a2a_trust_downgrade_and_missing_registry_fail_closed_for_qualified_skill(self) -> None:
        manifest = load_skill_orchestration_manifest("astrabridge-supervisor-worker-synthesizer")
        manifest["status"] = "external-a2a-qualified"
        manifest["evidence"]["required_level"] = "external-a2a-qualified"
        manifest["policies"]["a2a"] = {
            "external_enabled": True,
            "allowed_card_refs": [f"{EXTERNAL_A2A_CARD_REF_PREFIX}geo_route"],
            "minimum_trust_level": "pinned",
            "gateway_required": True,
        }
        graph = copy.deepcopy(agent_orchestration_example_catalog()["code_fix_review"])
        graph["nodes"][0]["card_ref"] = f"{EXTERNAL_A2A_CARD_REF_PREFIX}geo_route"
        graph["external_agent_card_registry"] = _registry(trust_level="workspace_trusted")
        report = bind_skill_provider_a2a(
            manifest,
            graph,
            configured_models=[_verified_model("qwen", "qwen3-coder-plus")],
        )
        self.assertEqual(report["status"], "blocked")
        self.assertTrue(any("trust_requirement_not_met" in item for item in report["blockers"]))

        missing_graph = copy.deepcopy(graph)
        missing_graph.pop("external_agent_card_registry", None)
        missing = bind_skill_provider_a2a(
            manifest,
            missing_graph,
            configured_models=[_verified_model("qwen", "qwen3-coder-plus")],
        )
        self.assertEqual(missing["status"], "blocked")
        self.assertTrue(any("gateway_validation_failed" in item for item in missing["blockers"]))


def _verified_model(provider: str, native_model: str) -> dict[str, object]:
    return {
        "id": f"{provider}/{native_model}",
        "provider": provider,
        "native_model": native_model,
        "input_modalities": ["text", "image"],
        "enabled": True,
        "verified_capability_snapshot_status": "verified",
        "verified_capability_snapshot_verification_state": "verified",
        "verified_capability_snapshot": {
            "status": "verified",
            "graph_capabilities": {
                "input_port_types": ["text", "structured_json", "code_diff", "image"],
                "output_port_types": ["structured_json", "code_diff", "agent_report", "text", "image"],
            },
        },
    }


def _registry(*, trust_level: str) -> dict[str, object]:
    public_card = {
        "protocolVersion": "1.0",
        "name": "Geo Route Agent",
        "description": "Plans routes for external A2A handoffs.",
        "url": "https://geo.example.com/a2a",
        "version": "2026.07.17",
        "supportedInterfaces": [
            {
                "url": "https://geo.example.com/a2a",
                "protocolBinding": "JSONRPC",
                "protocolVersion": "1.0",
            }
        ],
        "capabilities": {
            "streaming": True,
            "pushNotifications": False,
            "extendedAgentCard": False,
        },
        "defaultInputModes": ["text/plain", "application/json"],
        "defaultOutputModes": ["text/plain", "application/json"],
        "skills": [
            {
                "id": "route-plan",
                "name": "Route Planner",
                "description": "Returns structured route plans.",
            }
        ],
    }
    encoded = json.dumps(public_card, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return {
        "schema_version": EXTERNAL_A2A_AGENT_CARD_REGISTRY_SCHEMA_VERSION,
        "supported_protocol_versions": ["1.0"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "cards": [
            {
                "card_ref": f"{EXTERNAL_A2A_CARD_REF_PREFIX}geo_route",
                "trust_level": trust_level,
                "discovery": {
                    "mode": "well_known",
                    "url": "https://geo.example.com/.well-known/agent-card.json",
                },
                "public_agent_card": public_card,
                "public_agent_card_digest": f"sha256:{hashlib.sha256(encoded.encode('utf-8')).hexdigest()}",
            }
        ],
    }


if __name__ == "__main__":
    unittest.main()
