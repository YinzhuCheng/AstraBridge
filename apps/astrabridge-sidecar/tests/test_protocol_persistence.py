from __future__ import annotations

import json
import re
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SIDECAR_ROOT = REPO_ROOT / "apps" / "astrabridge-sidecar"
DESKTOP_FIXTURE_PATH = REPO_ROOT / "apps" / "astrabridge-desktop" / "src" / "astrabridge_protocol" / "fixtures" / "protocol_v1.json"
PROTOCOL_SCHEMA_PATH = SIDECAR_ROOT / "astrabridge_sidecar" / "protocol" / "schema" / "v1" / "protocol.json"
RUNTIME_EVENT_SOURCE_PATHS = (
    SIDECAR_ROOT / "astrabridge_sidecar" / "durable_run_store.py",
    SIDECAR_ROOT / "astrabridge_sidecar" / "runtime_service.py",
    SIDECAR_ROOT / "astrabridge_sidecar" / "task_service.py",
)
EVENT_TYPE_LITERAL_RE = re.compile(r'["\']event_type["\']\s*:\s*["\']([^"\']+)["\']')

if str(SIDECAR_ROOT) not in sys.path:
    sys.path.insert(0, str(SIDECAR_ROOT))

from astrabridge_sidecar.durable_run_store import DurableRunEventStore  # noqa: E402
from astrabridge_sidecar.protocol.generated.v1 import PROTOCOL_VOCABULARIES, RUN_EVENT_TYPES  # noqa: E402
from astrabridge_sidecar.protocol.persistence import (  # noqa: E402
    DEFAULT_SOURCE_NODE_ID,
    ProtocolPersistenceError,
    canonicalize_run_projection_payload,
)


class ProtocolPersistenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixtures = json.loads(DESKTOP_FIXTURE_PATH.read_text(encoding="utf-8"))
        cls.schema = json.loads(PROTOCOL_SCHEMA_PATH.read_text(encoding="utf-8"))

    def test_runtime_protocol_vocabularies_match_the_canonical_schema(self) -> None:
        defs = self.schema["$defs"]
        expected = {
            "run_event_types": tuple(defs["RunEvent"]["properties"]["event_type"]["enum"]),
            "artifact_statuses": tuple(defs["ArtifactStatus"]["enum"]),
            "content_part_kinds": tuple(defs["ContentPart"]["properties"]["kind"]["enum"]),
            "port_types": tuple(defs["PortDefinition"]["properties"]["port_type"]["enum"]),
            "port_shapes": tuple(defs["PortDefinition"]["properties"]["shape"]["enum"]),
            "capability_output_statuses": tuple(defs["CapabilityOutput"]["properties"]["status"]["enum"]),
        }
        self.assertEqual(PROTOCOL_VOCABULARIES, expected)
        self.assertEqual(tuple(RUN_EVENT_TYPES), expected["run_event_types"])

    def test_runtime_event_write_sites_do_not_emit_schema_external_event_types(self) -> None:
        discovered: set[str] = set()
        for path in RUNTIME_EVENT_SOURCE_PATHS:
            discovered.update(EVENT_TYPE_LITERAL_RE.findall(path.read_text(encoding="utf-8")))
        self.assertEqual(sorted(discovered.difference(RUN_EVENT_TYPES)), [])

    def test_create_run_normalizes_protocol_records_before_persistence(self) -> None:
        event_fixture = dict(self.fixtures["valid"]["RunEvent"])
        event_fixture.pop("schema_version")
        event_fixture.pop("payload")
        with tempfile.TemporaryDirectory() as temp:
            store = DurableRunEventStore(temp)
            stored = store.create_run(
                {
                    "schema_version": "astrabridge-task-graph-run-v1",
                    "run_id": "run-protocol-boundary",
                    "graph_id": "graph-1",
                    "task_id": "task-1",
                    "trace_id": "trace-run-protocol-boundary",
                    "context_id": "context-run-protocol-boundary",
                    "status": "queued",
                    "entry_node_ids": ["node-a"],
                    "node_run_states": [{"node_id": "node-a", "attempt_count": 1, "status": "queued"}],
                    "artifact_refs": [
                        {
                            "artifact_id": "artifact-legacy",
                            "path": "PRIVATE/runs/result.json",
                            "status": "ready",
                        }
                    ],
                    "event_refs": [{**event_fixture, "event_id": "event-legacy", "run_id": "run-protocol-boundary", "trace_id": "trace-run-protocol-boundary"}],
                    "created_at": "2026-07-17T12:00:00+09:00",
                    "updated_at": "2026-07-17T12:00:00+09:00",
                    "state_version": 0,
                }
            )
            self.assertEqual(stored["protocol_schema_version"], "astrabridge-protocol-v1")
            artifact = stored["artifact_refs"][0]
            self.assertEqual(artifact["artifact_uri"], "workspace://PRIVATE/runs/result.json")
            self.assertEqual(artifact["lineage"]["source_node_id"], DEFAULT_SOURCE_NODE_ID)
            event = stored["event_refs"][0]
            self.assertEqual(event["schema_version"], "astrabridge-protocol-v1")
            self.assertEqual(event["payload"], {})

    def test_persistence_rejects_schema_external_run_events(self) -> None:
        invalid_event = {**dict(self.fixtures["invalid"]["invalid_run_event_type"]["payload"]), "run_id": "run-invalid-event"}
        with tempfile.TemporaryDirectory() as temp:
            store = DurableRunEventStore(temp)
            store.create_run(
                {
                    "schema_version": "astrabridge-task-graph-run-v1",
                    "run_id": "run-invalid-event",
                    "graph_id": "graph-1",
                    "task_id": "task-1",
                    "trace_id": "trace-run-invalid-event",
                    "context_id": "context-run-invalid-event",
                    "status": "queued",
                    "entry_node_ids": ["node-a"],
                    "node_run_states": [],
                    "artifact_refs": [],
                    "event_refs": [],
                    "created_at": "2026-07-17T12:00:00+09:00",
                    "updated_at": "2026-07-17T12:00:00+09:00",
                    "state_version": 0,
                }
            )
            with self.assertRaisesRegex(ValueError, "allowed value"):
                store.append_event(invalid_event)

    def test_run_projection_schema_version_failures_are_actionable(self) -> None:
        with self.assertRaisesRegex(ProtocolPersistenceError, "Supported read-compatible versions"):
            canonicalize_run_projection_payload(
                {
                    "schema_version": "astrabridge-task-graph-run-v0",
                    "run_id": "run-unsupported",
                    "graph_id": "graph-1",
                    "task_id": "task-1",
                    "trace_id": "trace-run-unsupported",
                    "status": "queued",
                }
            )


if __name__ == "__main__":
    unittest.main()
