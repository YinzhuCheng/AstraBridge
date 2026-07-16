from __future__ import annotations

import json
import subprocess
import sys
import unittest
from copy import deepcopy
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SIDECAR_ROOT = REPO_ROOT / "apps" / "astrabridge-sidecar"
DESKTOP_FIXTURE_PATH = REPO_ROOT / "apps" / "astrabridge-desktop" / "src" / "astrabridge_protocol" / "fixtures" / "protocol_v1.json"
if str(SIDECAR_ROOT) not in sys.path:
    sys.path.insert(0, str(SIDECAR_ROOT))

from astrabridge_sidecar.agent_orchestration_compiler import compile_agent_orchestration_graph  # noqa: E402
from astrabridge_sidecar.agent_orchestration_file_format import agent_orchestration_example_catalog  # noqa: E402
from astrabridge_sidecar.protocol.compatibility import (  # noqa: E402
    adapt_legacy_artifact_path,
    canonical_graph_signature,
    compatibility_manifest,
    migrate_compiled_plan,
    migrate_graph_definition,
)
from astrabridge_sidecar.protocol.generated.v1 import (  # noqa: E402
    SCHEMA_VERSION,
    ProtocolValidationError,
    validate_protocol_payload,
    validation_verdict,
)
from astrabridge_sidecar.task_graph_contract import load_task_graph_fixture  # noqa: E402


class ProtocolSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixtures = json.loads(DESKTOP_FIXTURE_PATH.read_text(encoding="utf-8"))

    def test_generated_projection_is_fresh(self) -> None:
        result = subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" / "generate_protocol_types.py"), "--check"],
            cwd=REPO_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_shared_positive_and_negative_fixture_verdicts(self) -> None:
        for kind, payload in self.fixtures["valid"].items():
            self.assertTrue(validation_verdict(kind, payload), kind)
        for case_id, case in self.fixtures["invalid"].items():
            self.assertFalse(validation_verdict(case["kind"], case["payload"]), case_id)

    def test_required_envelope_and_security_fields_are_rejected(self) -> None:
        envelope = deepcopy(self.fixtures["valid"]["AgentEnvelope"])
        envelope.pop("recipient")
        with self.assertRaises(ProtocolValidationError):
            validate_protocol_payload("AgentEnvelope", envelope)
        envelope = deepcopy(self.fixtures["valid"]["AgentEnvelope"])
        envelope["metadata"] = {"private_reasoning": "forbidden"}
        with self.assertRaises(ProtocolValidationError):
            validate_protocol_payload("AgentEnvelope", envelope)

    def test_legacy_graph_migration_is_idempotent_and_preserves_topology(self) -> None:
        legacy = load_task_graph_fixture("fanout_fanin_research")
        canonical = migrate_graph_definition(legacy)
        self.assertEqual(canonical["schema_version"], SCHEMA_VERSION)
        self.assertEqual(canonical_graph_signature(legacy), canonical_graph_signature(canonical))
        self.assertEqual(canonical, migrate_graph_definition(canonical))
        self.assertEqual(canonical["migration"]["legacy_projection"]["graph_id"], legacy["graph_id"])

    def test_all_orchestration_examples_use_the_same_graph_migration_adapter(self) -> None:
        for example_id, legacy in agent_orchestration_example_catalog().items():
            with self.subTest(example_id=example_id):
                canonical = migrate_graph_definition(legacy)
                self.assertEqual(canonical_graph_signature(legacy), canonical_graph_signature(canonical))
                self.assertEqual(canonical, migrate_graph_definition(canonical))

    def test_compiled_plan_migration_is_idempotent_and_preserves_ids(self) -> None:
        example = next(iter(agent_orchestration_example_catalog().values()))
        compiled = compile_agent_orchestration_graph(example)
        canonical = migrate_compiled_plan(compiled)
        self.assertEqual(canonical["graph_id"], compiled["graph_id"])
        self.assertEqual(canonical["task_id"], compiled["task_id"])
        self.assertEqual(canonical["entry_node_ids"], compiled["entry_node_ids"])
        self.assertEqual(canonical["topology"], compiled["topology"])
        self.assertEqual(canonical, migrate_compiled_plan(canonical))

    def test_artifact_adapter_preserves_lineage_and_rejects_external_paths(self) -> None:
        artifact = adapt_legacy_artifact_path(
            {
                "artifact_id": "artifact-legacy",
                "path": ".astrabridge/runs/run-1/result.json",
                "media_type": "application/json",
                "status": "ready",
                "task_id": "task-1",
                "run_id": "run-1",
                "source_node_id": "node-worker",
            }
        )
        self.assertEqual(artifact["artifact_uri"], "workspace://.astrabridge/runs/run-1/result.json")
        self.assertEqual(artifact["lineage"]["task_id"], "task-1")
        with self.assertRaises(ValueError):
            adapt_legacy_artifact_path({"artifact_id": "bad", "path": "C:/outside/result.json"})

    def test_manifest_declares_current_write_and_legacy_read_rules(self) -> None:
        manifest = compatibility_manifest()
        self.assertTrue(manifest["idempotent"])
        self.assertEqual(manifest["target_schema"], SCHEMA_VERSION)
        self.assertIn("astrabridge-task-graph-v1", manifest["read_compatibility"])
        self.assertIn("artifact lineage", manifest["preserves"])
        self.assertIn("security policy", manifest["preserves"])


if __name__ == "__main__":
    unittest.main()
