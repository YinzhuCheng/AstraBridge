from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from astrabridge_sidecar.durable_run_store import (
    DeliveryPolicyConflict,
    DURABLE_RUN_MIGRATION_SCHEMA_VERSION,
    DURABLE_RUN_STORE_SCHEMA_REVISION,
    DURABLE_RUN_STORE_SCHEMA_VERSION,
    DurableRunEventStore,
    ImmutableRecordConflict,
    LeaseBusy,
    StateVersionConflict,
    StoreInitializationBlocked,
    STORE_MIGRATION_BACKUP_DIRNAME,
    STORE_MIGRATION_REPORT_DIRNAME,
    TerminalStateConflict,
)


def _run(run_id: str = "run-1", *, status: str = "queued") -> dict[str, object]:
    return {
        "schema_version": "astrabridge-task-graph-run-v1",
        "run_id": run_id,
        "graph_id": "graph-1",
        "task_id": "task-1",
        "trace_id": f"trace-{run_id}",
        "context_id": f"context-{run_id}",
        "status": status,
        "entry_node_ids": ["node-a"],
        "node_run_states": [{"node_id": "node-a", "attempt_count": 1, "status": "queued"}],
        "artifact_refs": [{"artifact_id": f"{run_id}-artifact", "path": "PRIVATE/runs/result.json", "status": "ready"}],
        "event_refs": [{
            "event_id": f"{run_id}-created",
            "run_id": run_id,
            "task_id": "task-1",
            "trace_id": f"trace-{run_id}",
            "sequence": 0,
            "event_type": "run_created",
            "created_at": "2026-01-01T00:00:00+00:00",
        }],
        "approval_state": {"status": "not_required"},
        "run_policy_snapshot": {"max_parallelism": 1},
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T00:00:00+00:00",
        "state_version": 0,
    }


def _agent_envelope(
    run_id: str = "run-1",
    *,
    edge_id: str = "edge-source-target",
    attempt: int = 1,
    sequence: int | None = None,
) -> dict[str, object]:
    delivery_sequence = max(0, attempt - 1) if sequence is None else sequence
    return {
        "envelope_id": f"envelope-{run_id}-{edge_id}-{attempt}",
        "schema_version": "astrabridge-protocol-v1",
        "message_id": f"message-{run_id}-{edge_id}-{attempt}",
        "task_id": "task-1",
        "run_id": run_id,
        "sender": {
            "agent_id": "agent-source",
            "provider_id": "qwen",
            "model_id": "qwen3.7-plus",
            "lane_id": "worker-node-source",
        },
        "recipient": {
            "agent_id": "agent-target",
            "provider_id": "deepseek",
            "model_id": "deepseek-v4-pro",
            "lane_id": "node-target",
        },
        "kind": "handoff",
        "content": [
            {
                "part_id": f"part-{run_id}",
                "kind": "json",
                "mime_type": "application/json",
                "data": {"result": "ok"},
            }
        ],
        "created_at": "2026-01-01T00:01:00+00:00",
        "delivery": {
            "attempt": attempt,
            "idempotency_key": f"delivery-{run_id}-{edge_id}-{attempt}",
            "trace_id": f"trace-{run_id}",
            "sequence": delivery_sequence,
        },
        "security_policy": {
            "exclude_private_memory": True,
            "redaction_applied": True,
        },
        "metadata": {
            "graph_id": "graph-1",
            "context_id": f"context-{run_id}",
            "source_node_id": "node-source",
            "target_node_id": "node-target",
            "edge_id": edge_id,
            "intent": "graph_node_handoff",
            "correlation_id": f"corr-{run_id}",
            "causation_id": f"cause-{run_id}",
            "schema_refs": ["schema.result"],
            "context_policy_snapshot": {"exclude_private_memory": True},
            "budget": {"total_tokens": 10},
            "provenance": {"source_output_envelope_path": "PRIVATE/output-envelope.json"},
        },
    }


class DurableRunStoreTests(unittest.TestCase):
    def test_schema_is_workspace_local_wal_and_repeated_initialization_is_stable(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            store = DurableRunEventStore(root)
            self.assertEqual(store.initialize()["schema_version"], DURABLE_RUN_STORE_SCHEMA_VERSION)
            self.assertEqual(store.initialize(), {"schema_version": DURABLE_RUN_STORE_SCHEMA_VERSION})
            self.assertTrue(store.db_path.is_relative_to(root / ".astrabridge"))
            conn = sqlite3.connect(store.db_path)
            try:
                self.assertEqual(conn.execute("PRAGMA journal_mode").fetchone()[0].lower(), "wal")
                tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            finally:
                conn.close()
            self.assertTrue({"runs", "run_events", "node_attempts", "leases", "inbox", "outbox", "external_operations"}.issubset(tables))

    def test_initialize_upgrades_old_store_revision_with_backup_and_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            store = DurableRunEventStore(root)
            store.db_path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(store.db_path)
            try:
                conn.execute("CREATE TABLE store_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
                conn.execute("INSERT INTO store_meta(key, value) VALUES(?, ?)", ("schema_version", "legacy-schema"))
                conn.execute("PRAGMA user_version=0")
                conn.commit()
            finally:
                conn.close()

            self.assertEqual(store.initialize()["schema_version"], DURABLE_RUN_STORE_SCHEMA_VERSION)

            conn = sqlite3.connect(store.db_path)
            try:
                self.assertEqual(conn.execute("PRAGMA user_version").fetchone()[0], DURABLE_RUN_STORE_SCHEMA_REVISION)
            finally:
                conn.close()

            reports = sorted(
                path
                for path in (root / ".astrabridge" / STORE_MIGRATION_REPORT_DIRNAME).glob("*.json")
                if not path.name.endswith(".readback.json")
            )
            self.assertTrue(reports)
            report = next(
                json.loads(path.read_text(encoding="utf-8"))
                for path in reports
                if json.loads(path.read_text(encoding="utf-8")).get("detected_state") == "old"
            )
            self.assertEqual(report["detected_state"], "old")
            self.assertEqual(report["terminal_outcome"], "committed")
            self.assertTrue(report["backup_paths"])
            backup_root = root / ".astrabridge" / STORE_MIGRATION_BACKUP_DIRNAME / report["migration_id"]
            self.assertTrue((backup_root / store.db_path.name).exists())

    def test_initialize_blocks_future_store_revision_and_preserves_backup(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            store = DurableRunEventStore(root)
            store.create_run(_run("run-future"))
            store.record_agent_envelope(_agent_envelope("run-future"))
            conn = sqlite3.connect(store.db_path)
            try:
                conn.execute(f"PRAGMA user_version={DURABLE_RUN_STORE_SCHEMA_REVISION + 1}")
                conn.commit()
            finally:
                conn.close()

            with self.assertRaises(StoreInitializationBlocked) as raised:
                DurableRunEventStore(root).initialize()

            report = raised.exception.report
            self.assertEqual(report["detected_state"], "future_version")
            self.assertEqual(report["terminal_outcome"], "blocked_future_version")
            self.assertTrue(report["backup_paths"])
            backup_root = root / ".astrabridge" / STORE_MIGRATION_BACKUP_DIRNAME / report["migration_id"]
            self.assertTrue((backup_root / store.db_path.name).exists())
            self.assertEqual(report["readback"]["status"], "pass")
            self.assertEqual(report["readback"]["sample_run_id"], "run-future")
            self.assertEqual(sorted(report["readback"]["provider_participants"]), ["deepseek", "qwen"])
            readback = json.loads((root / report["readback"]["readback_path"]).read_text(encoding="utf-8"))
            self.assertEqual(readback["projection"]["run_id"], "run-future")
            self.assertEqual(readback["projection"]["graph_id"], "graph-1")

    def test_initialize_blocks_damaged_store_and_preserves_backup(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            store = DurableRunEventStore(root)
            store.db_path.parent.mkdir(parents=True, exist_ok=True)
            store.db_path.write_text("not-a-sqlite-database", encoding="utf-8")

            with self.assertRaises(StoreInitializationBlocked) as raised:
                store.initialize()

            report = raised.exception.report
            self.assertEqual(report["detected_state"], "damaged")
            self.assertEqual(report["terminal_outcome"], "blocked_damaged")
            self.assertTrue(report["backup_paths"])
            backup_root = root / ".astrabridge" / STORE_MIGRATION_BACKUP_DIRNAME / report["migration_id"]
            self.assertTrue((backup_root / store.db_path.name).exists())
            self.assertEqual(report["readback"]["status"], "blocked")

    def test_initialize_rolled_back_report_preserves_readback_for_prior_run_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            store = DurableRunEventStore(root)
            store.create_run(_run("run-rollback"))
            store.record_agent_envelope(_agent_envelope("run-rollback"))
            conn = sqlite3.connect(store.db_path)
            try:
                conn.execute("ALTER TABLE store_meta RENAME TO store_meta_valid")
                conn.execute("CREATE TABLE store_meta (key TEXT PRIMARY KEY)")
                conn.execute("INSERT INTO store_meta(key) VALUES(?)", ("schema_version",))
                conn.commit()
            finally:
                conn.close()

            with self.assertRaises(sqlite3.DatabaseError):
                DurableRunEventStore(root).initialize()

            reports = sorted(
                path
                for path in (root / ".astrabridge" / STORE_MIGRATION_REPORT_DIRNAME).glob("*.json")
                if not path.name.endswith(".readback.json")
            )
            self.assertTrue(reports)
            report = next(
                json.loads(path.read_text(encoding="utf-8"))
                for path in reports
                if json.loads(path.read_text(encoding="utf-8")).get("terminal_outcome") == "rolled_back"
            )
            self.assertEqual(report["terminal_outcome"], "rolled_back")
            self.assertTrue(report["backup_paths"])
            self.assertEqual(report["readback"]["status"], "pass")
            self.assertEqual(report["readback"]["sample_run_id"], "run-rollback")
            self.assertEqual(sorted(report["readback"]["provider_participants"]), ["deepseek", "qwen"])
            readback = json.loads((root / report["readback"]["readback_path"]).read_text(encoding="utf-8"))
            self.assertEqual(readback["projection"]["run_id"], "run-rollback")
            self.assertEqual(readback["projection"]["delivery_ledger"], [])

    def test_empty_migration_is_deterministic_and_does_not_create_legacy_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = DurableRunEventStore(temp)
            first = store.migrate_legacy_state()
            second = store.migrate_legacy_state()
            self.assertEqual(first, second)
            self.assertEqual(first["schema_version"], DURABLE_RUN_MIGRATION_SCHEMA_VERSION)
            self.assertEqual(first["status"], "empty")

    def test_create_reload_and_projection_rebuild_are_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            store = DurableRunEventStore(root)
            store.create_run(_run())
            store.record_node_attempt("run-1", "node-a", 2, status="retrying", payload={"node_id": "node-a", "attempt_count": 2, "status": "retrying"})
            store.record_artifact("run-1", {"artifact_id": "run-1-second", "path": "PRIVATE/runs/second.json", "status": "ready"})
            projection_a = store.rebuild_run_projection("run-1")
            reloaded = DurableRunEventStore(root)
            projection_b = reloaded.rebuild_run_projection("run-1")
            self.assertEqual(projection_a, projection_b)
            self.assertEqual([item["attempt_count"] for item in reloaded.load_run("run-1")["node_run_states"]], [1, 2])
            self.assertEqual(len(reloaded.load_run("run-1")["event_refs"]), 1)

    def test_compare_and_swap_allows_one_concurrent_terminal_writer(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = DurableRunEventStore(temp)
            store.create_run(_run())

            def write(index: int) -> str:
                try:
                    store.compare_and_swap_run(
                        "run-1",
                        0,
                        status="completed",
                        event={"event_id": f"run-1-complete-{index}", "event_type": "run_completed"},
                    )
                    return "ok"
                except StateVersionConflict:
                    return "conflict"

            with ThreadPoolExecutor(max_workers=8) as pool:
                results = [future.result() for future in as_completed([pool.submit(write, index) for index in range(8)])]
            self.assertEqual(results.count("ok"), 1)
            self.assertEqual(results.count("conflict"), 7)
            self.assertEqual(store.load_run("run-1")["status"], "completed")
            with self.assertRaises(TerminalStateConflict):
                store.compare_and_swap_run("run-1", 1, status="failed")

    def test_event_idempotency_and_sequence_conflicts_are_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = DurableRunEventStore(temp)
            store.create_run(_run())
            event = {
                "event_id": "run-1-node-start",
                "run_id": "run-1",
                "task_id": "task-1",
                "trace_id": "trace-run-1",
                "event_type": "node_started",
                "created_at": "2026-01-01T00:02:00+00:00",
                "sequence": 1,
            }
            first = store.append_event(event)
            self.assertEqual(store.append_event(event), first)
            with self.assertRaises(ImmutableRecordConflict):
                store.append_event({**event, "event_type": "node_completed"})
            with self.assertRaises(ImmutableRecordConflict):
                store.append_event({**event, "event_id": "run-1-other", "sequence": 1})

            with self.assertRaises(ImmutableRecordConflict):
                store.compare_and_swap_run(
                    "run-1",
                    0,
                    status="completed",
                    event={
                        "event_id": "run-1-invalid-terminal",
                        "run_id": "run-1",
                        "task_id": "task-1",
                        "trace_id": "trace-run-1",
                        "event_type": "run_completed",
                        "sequence": 0,
                    },
                )
            rolled_back = store.load_run("run-1")
            self.assertEqual(rolled_back["status"], "queued")
            self.assertEqual(rolled_back["state_version"], 0)

    def test_duplicate_run_create_with_idempotency_key_returns_same_projection(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = DurableRunEventStore(temp)
            original = store.create_run(_run(), idempotency_key="create-run-1")
            repeated = store.create_run(_run(), idempotency_key="create-run-1")
            self.assertEqual(repeated["run_id"], original["run_id"])
            self.assertEqual(repeated["status"], original["status"])

    def test_leases_inbox_outbox_and_external_operation_records_are_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = DurableRunEventStore(temp)
            store.create_run(_run())
            lease = store.acquire_lease("run-1", "node-a", 1, owner_boot_id="boot-a", lease_id="lease-a")
            self.assertEqual(lease["status"], "active")
            with self.assertRaises(LeaseBusy):
                store.acquire_lease("run-1", "node-a", 1, owner_boot_id="boot-b")
            self.assertEqual(store.heartbeat_lease("lease-a", owner_boot_id="boot-a")["status"], "active")
            self.assertTrue(store.release_lease("lease-a", owner_boot_id="boot-a"))
            self.assertEqual(store.acquire_lease("run-1", "node-a", 1, owner_boot_id="boot-b")["status"], "active")
            self.assertTrue(store.record_inbox("message-1", run_id="run-1"))
            self.assertFalse(store.record_inbox("message-1", run_id="run-1"))
            with self.assertRaises(ImmutableRecordConflict):
                store.record_inbox("message-1", run_id="run-1", payload={"different": True})
            self.assertEqual(store.enqueue_outbox("operation-1", "run-1", kind="dispatch")["status"], "pending")
            self.assertEqual(store.enqueue_outbox("operation-1", "run-1", kind="dispatch"), store.get_outbox_operation("operation-1"))
            with self.assertRaises(ImmutableRecordConflict):
                store.enqueue_outbox("operation-1", "run-1", kind="dispatch", payload={"different": True})
            operation = store.record_external_operation("operation-1", "run-1", kind="provider_call", classification="read_only", status="completed")
            self.assertEqual(operation["status"], "completed")

    def test_agent_envelope_persistence_is_immutable_and_delivery_events_project_into_delivery_ledger(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = DurableRunEventStore(temp)
            store.create_run(_run())
            envelope = _agent_envelope()
            stored = store.record_agent_envelope(envelope)
            self.assertEqual(store.record_agent_envelope(envelope), stored)
            store.append_event(
                {
                    "event_id": "run-1-handoff-created",
                    "run_id": "run-1",
                    "task_id": "task-1",
                    "trace_id": "trace-run-1",
                    "event_type": "handoff_created",
                    "created_at": "2026-01-01T00:01:01+00:00",
                    "payload": {
                        "envelope_id": "envelope-run-1",
                        "delivery_idempotency_key": "delivery-run-1",
                    },
                }
            )
            projection = store.load_run("run-1")
            self.assertEqual(len(projection["agent_envelopes"]), 1)
            self.assertEqual(projection["agent_envelopes"][0]["envelope_id"], "envelope-run-1-edge-source-target-1")
            self.assertEqual(len(projection["delivery_ledger"]), 1)
            self.assertEqual(projection["delivery_ledger"][0]["event_type"], "handoff_created")
            self.assertEqual(projection["delivery_ledger"][0]["payload"]["envelope_id"], "envelope-run-1")
            with self.assertRaises(ImmutableRecordConflict):
                store.record_agent_envelope(
                    {
                        **envelope,
                        "content": [
                            {
                                "part_id": "part-run-1",
                                "kind": "json",
                                "mime_type": "application/json",
                                "data": {"result": "different"},
                            }
                        ],
                    }
                )

    def test_agent_envelope_delivery_sequence_and_processing_policy_are_enforced(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = DurableRunEventStore(temp)
            store.create_run(_run())
            first = store.record_agent_envelope(_agent_envelope())
            first_sequence = dict(first.get("delivery") or {}).get("sequence")
            self.assertEqual(-1 if first_sequence is None else int(first_sequence), 0)
            second = store.record_agent_envelope(_agent_envelope(attempt=2))
            second_sequence = dict(second.get("delivery") or {}).get("sequence")
            self.assertEqual(-1 if second_sequence is None else int(second_sequence), 1)
            with self.assertRaises(DeliveryPolicyConflict):
                store.record_agent_envelope(_agent_envelope(edge_id="edge-source-target", attempt=4, sequence=3))
            with self.assertRaises(DeliveryPolicyConflict):
                store.record_agent_envelope(
                    {
                        **_agent_envelope(edge_id="edge-source-target", attempt=3, sequence=0),
                        "content": [
                            {
                                "part_id": "part-conflict",
                                "kind": "json",
                                "mime_type": "application/json",
                                "data": {"result": "conflict"},
                            }
                        ],
                    }
                )

    def test_admit_agent_envelope_processing_rejects_early_expired_or_mismatched_audience(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = DurableRunEventStore(temp)
            store.create_run(_run())
            accepted = store.admit_agent_envelope_processing(_agent_envelope(), target_node_id="node-target", target_provider_id="deepseek")
            self.assertEqual(accepted["status"], "accepted")
            duplicate = store.admit_agent_envelope_processing(_agent_envelope(), target_node_id="node-target", target_provider_id="deepseek")
            self.assertEqual(duplicate["status"], "duplicate")

            early = _agent_envelope(edge_id="edge-early")
            early["metadata"] = {**dict(early.get("metadata") or {}), "not_before_at": "2026-01-01T00:05:00+00:00"}
            with self.assertRaises(DeliveryPolicyConflict):
                store.admit_agent_envelope_processing(
                    early,
                    target_node_id="node-target",
                    target_provider_id="deepseek",
                    now="2026-01-01T00:04:00+00:00",
                )

            expired = _agent_envelope(edge_id="edge-expired")
            expired["metadata"] = {**dict(expired.get("metadata") or {}), "ttl_seconds": 10}
            with self.assertRaises(DeliveryPolicyConflict):
                store.admit_agent_envelope_processing(
                    expired,
                    target_node_id="node-target",
                    target_provider_id="deepseek",
                    now="2026-01-01T00:02:00+00:00",
                )

            wrong_audience = _agent_envelope(edge_id="edge-audience")
            wrong_audience["recipient"] = {**dict(wrong_audience.get("recipient") or {}), "lane_id": "node-other"}
            with self.assertRaises(DeliveryPolicyConflict):
                store.admit_agent_envelope_processing(wrong_audience, target_node_id="node-target", target_provider_id="deepseek")

    def test_legacy_migration_preserves_source_redacts_secrets_and_marks_active_or_external_runs(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            state = root / ".astrabridge"
            state.mkdir()
            secret_value = "Bearer-" + ("x" * 24)
            legacy = {
                "schema_version": "astrabridge-task-state-v1",
                "tasks": [
                    {
                        "task_id": "task-terminal",
                        "graph_run_refs": [{
                            "run_id": "run-terminal",
                            "graph_id": "graph-1",
                            "status": "completed",
                            "created_at": "2026-01-01T00:00:00+00:00",
                            "updated_at": "2026-01-01T00:01:00+00:00",
                            "policy_snapshot": {"authorization": secret_value},
                            "artifact_refs": [{"artifact_id": "artifact-terminal", "path": "PRIVATE/run-manifest.json"}],
                        }],
                    },
                    {
                        "task_id": "task-running",
                        "graph_run_refs": [{
                            "run_id": "run-running",
                            "graph_id": "graph-1",
                            "status": "running",
                            "artifact_refs": [{"artifact_id": "artifact-running", "path": "C:/outside/result.json"}],
                        }],
                    },
                ],
            }
            source_bytes = json.dumps(legacy, ensure_ascii=False, indent=2).encode("utf-8")
            source = state / "tasks.json"
            source.write_bytes(source_bytes)
            store = DurableRunEventStore(root)
            report = store.migrate_legacy_state()
            repeated = store.migrate_legacy_state()
            self.assertEqual(report["status"], "needs_review")
            self.assertEqual(report["imported_count"], 2)
            self.assertEqual(report["needs_review_count"], 1)
            self.assertTrue(repeated["repeated"])
            self.assertEqual(source.read_bytes(), source_bytes)
            running = store.load_run("run-running")
            self.assertEqual(running["status"], "needs_review")
            self.assertEqual(running["legacy_status"], "running")
            self.assertTrue(str(running["artifact_refs"][0]["path"]).startswith("UNSAFE_EXTERNAL_PATH/"))
            self.assertNotIn(secret_value.encode("utf-8"), store.db_path.read_bytes())


if __name__ == "__main__":
    unittest.main()
