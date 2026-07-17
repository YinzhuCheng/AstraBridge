"""Transactional workspace-local source of truth for graph runs and events.

The store is intentionally independent from HTTP and UI lifetimes.  Existing
``.astrabridge/tasks.json`` and run manifests remain readable exports; this
module owns the durable run state, ordered events, attempts, leases, inbox,
outbox, and external-operation records used by the scheduler migration.
"""

from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any, Iterator

from .common import WORKSPACE_STATE_DIRNAME, now_iso, write_json
from .security import SECRET_RE, SecurityError, redact_sensitive, resolve_under


DURABLE_RUN_STORE_SCHEMA_VERSION = "astrabridge-durable-run-store-v1"
DURABLE_RUN_STORE_FILENAME = "durable_runs.sqlite3"
DURABLE_RUN_MIGRATION_SCHEMA_VERSION = "astrabridge-durable-run-migration-v1"
DURABLE_RUN_PROJECTION_SCHEMA_VERSION = "astrabridge-durable-run-projection-v1"
DELIVERY_LEDGER_EVENT_TYPES = frozenset(
    {
        "handoff_created",
        "handoff_acknowledged",
        "handoff_rejected",
        "handoff_retry_scheduled",
        "handoff_delivery_failed",
    }
)

TERMINAL_RUN_STATUSES = frozenset(
    {
        "completed",
        "failed",
        "cancelled",
        "needs_review",
        "partial",
        "rolled_back",
        "dry_run_passed",
        "dry_run_blocked",
    }
)
LEGACY_ACTIVE_STATUSES = frozenset(
    {
        "queued",
        "ready",
        "ready_for_dry_run",
        "dry_run_running",
        "running",
        "paused_for_review",
        "waiting_on_approval",
        "waiting_on_artifact",
    }
)


class DurableRunStoreError(RuntimeError):
    """Base error for durable run-store operations."""


class StateVersionConflict(DurableRunStoreError):
    """The caller attempted a compare-and-swap against a stale state version."""


class TerminalStateConflict(DurableRunStoreError):
    """A terminal run was asked to regress or change terminal identity."""


class LeaseBusy(DurableRunStoreError):
    """A non-expired lease is owned by another scheduler boot."""


class ImmutableRecordConflict(DurableRunStoreError):
    """An immutable event/artifact/attempt was submitted with different data."""


def _json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _json_load(value: str | None, default: Any) -> Any:
    if not value:
        return deepcopy(default)
    try:
        return json.loads(value)
    except (TypeError, ValueError, json.JSONDecodeError):
        return deepcopy(default)


def _redacted(value: Any) -> Any:
    """Redact before storage and fail if a raw secret still survives."""

    clean = redact_sensitive(deepcopy(value))
    serialized = _json_text(clean)
    if SECRET_RE.search(serialized):
        raise SecurityError("Secret-like content is not allowed in durable run state.")
    return clean


def _identifier(value: Any, field: str) -> str:
    clean = str(value or "").strip()
    if not clean:
        raise ValueError(f"{field} is required.")
    return clean


def _safe_state_root(workspace_root: str | Path) -> tuple[Path, Path]:
    root = Path(workspace_root).expanduser().resolve()
    if root.name == WORKSPACE_STATE_DIRNAME:
        raise ValueError("workspace_root must be the project workspace, not .astrabridge itself.")
    state_root = root / WORKSPACE_STATE_DIRNAME
    state_root.mkdir(parents=True, exist_ok=True)
    return root, state_root


class DurableRunEventStore:
    """SQLite/WAL store for durable graph runs and ordered runtime events."""

    def __init__(self, workspace_root: str | Path, *, db_path: str | Path | None = None) -> None:
        self.workspace_root, self.state_root = _safe_state_root(workspace_root)
        requested_db = Path(db_path).expanduser() if db_path is not None else self.state_root / DURABLE_RUN_STORE_FILENAME
        if not requested_db.is_absolute():
            requested_db = self.workspace_root / requested_db
        self.db_path = requested_db.resolve()
        try:
            self.db_path.relative_to(self.state_root)
        except ValueError as exc:
            raise ValueError("Durable run store must remain under workspace-local .astrabridge/.") from exc
        self._initialized = False

    def initialize(self) -> dict[str, Any]:
        """Create the schema and enable WAL; safe to call repeatedly."""

        with self._connection() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS store_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    graph_id TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    trace_id TEXT NOT NULL,
                    context_id TEXT,
                    status TEXT NOT NULL,
                    state_version INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    legacy_status TEXT,
                    source TEXT NOT NULL DEFAULT 'scheduler'
                );
                CREATE TABLE IF NOT EXISTS node_attempts (
                    run_id TEXT NOT NULL,
                    node_id TEXT NOT NULL,
                    attempt INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    started_at TEXT,
                    updated_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    PRIMARY KEY (run_id, node_id, attempt),
                    FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS run_events (
                    event_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    trace_id TEXT NOT NULL,
                    sequence INTEGER NOT NULL,
                    event_type TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    UNIQUE (run_id, sequence),
                    FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS artifacts (
                    artifact_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    artifact_uri TEXT,
                    relative_path TEXT,
                    status TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS agent_envelopes (
                    envelope_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    graph_id TEXT NOT NULL,
                    source_node_id TEXT NOT NULL,
                    target_node_id TEXT NOT NULL,
                    message_id TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL,
                    trace_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    UNIQUE (run_id, idempotency_key),
                    FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS leases (
                    lease_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    node_id TEXT NOT NULL,
                    attempt INTEGER NOT NULL,
                    owner_boot_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    acquired_at TEXT NOT NULL,
                    heartbeat_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    UNIQUE (run_id, node_id, attempt),
                    FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS inbox (
                    idempotency_key TEXT PRIMARY KEY,
                    run_id TEXT,
                    event_id TEXT,
                    received_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS outbox (
                    operation_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    node_id TEXT,
                    kind TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    UNIQUE (run_id, operation_id),
                    FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS external_operations (
                    operation_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    classification TEXT NOT NULL,
                    status TEXT NOT NULL,
                    external_handle TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS run_idempotency (
                    idempotency_key TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    payload_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS legacy_imports (
                    source_key TEXT PRIMARY KEY,
                    run_id TEXT,
                    classification TEXT NOT NULL,
                    source_schema TEXT,
                    reason TEXT,
                    imported_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS migration_runs (
                    migration_id TEXT PRIMARY KEY,
                    source_hash TEXT NOT NULL UNIQUE,
                    source_path TEXT NOT NULL,
                    status TEXT NOT NULL,
                    report_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_run_events_run_sequence ON run_events(run_id, sequence);
                CREATE INDEX IF NOT EXISTS idx_node_attempts_run_node ON node_attempts(run_id, node_id, attempt);
                CREATE INDEX IF NOT EXISTS idx_agent_envelopes_run_target ON agent_envelopes(run_id, target_node_id, created_at, envelope_id);
                CREATE INDEX IF NOT EXISTS idx_leases_active ON leases(run_id, node_id, status, expires_at);
                CREATE INDEX IF NOT EXISTS idx_outbox_pending ON outbox(status, updated_at);
                """
            )
            conn.execute(
                "INSERT INTO store_meta(key, value) VALUES(?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                ("schema_version", DURABLE_RUN_STORE_SCHEMA_VERSION),
            )
        self._initialized = True
        return self.store_metadata()

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(
            self.db_path,
            timeout=30,
            isolation_level=None,
            check_same_thread=False,
        )
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=FULL")
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("PRAGMA busy_timeout=30000")
            yield conn
        finally:
            conn.close()

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        with self._connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                yield conn
            except Exception:
                conn.rollback()
                raise
            else:
                conn.commit()

    def _require_initialized(self) -> None:
        if not self._initialized:
            self.initialize()

    def store_metadata(self) -> dict[str, Any]:
        self._require_initialized_without_recursion()
        with self._connection() as conn:
            rows = conn.execute("SELECT key, value FROM store_meta ORDER BY key").fetchall()
        return {str(row["key"]): str(row["value"]) for row in rows}

    def _require_initialized_without_recursion(self) -> None:
        if self._initialized:
            return
        self.initialize()

    def _row_run(self, row: sqlite3.Row) -> dict[str, Any]:
        payload = _json_load(row["payload_json"], {})
        if not isinstance(payload, dict):
            payload = {}
        payload.update(
            {
                "run_id": str(row["run_id"]),
                "graph_id": str(row["graph_id"]),
                "task_id": str(row["task_id"]),
                "trace_id": str(row["trace_id"]),
                "context_id": row["context_id"],
                "status": str(row["status"]),
                "state_version": int(row["state_version"]),
                "created_at": str(row["created_at"]),
                "updated_at": str(row["updated_at"]),
            }
        )
        return payload

    @staticmethod
    def _event_payload(row: sqlite3.Row) -> dict[str, Any]:
        payload = _json_load(row["payload_json"], {})
        if not isinstance(payload, dict):
            payload = {"value": payload}
        payload.update(
            {
                "event_id": str(row["event_id"]),
                "run_id": str(row["run_id"]),
                "task_id": str(row["task_id"]),
                "trace_id": str(row["trace_id"]),
                "sequence": int(row["sequence"]),
                "event_type": str(row["event_type"]),
                "created_at": str(row["created_at"]),
            }
        )
        return payload

    def _projection_in_connection(self, conn: sqlite3.Connection, run_id: str, *, include_events: bool = True) -> dict[str, Any] | None:
        row = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
        if row is None:
            return None
        run = self._row_run(row)
        attempts = conn.execute(
            "SELECT * FROM node_attempts WHERE run_id = ? ORDER BY node_id, attempt",
            (run_id,),
        ).fetchall()
        run["node_run_states"] = [
            _json_load(item["payload_json"], {"node_id": item["node_id"], "attempt_count": item["attempt"]})
            for item in attempts
        ]
        artifact_rows = conn.execute(
            "SELECT * FROM artifacts WHERE run_id = ? ORDER BY created_at, artifact_id",
            (run_id,),
        ).fetchall()
        run["artifact_refs"] = [_json_load(item["payload_json"], {}) for item in artifact_rows]
        envelope_rows = conn.execute(
            "SELECT payload_json FROM agent_envelopes WHERE run_id = ? ORDER BY created_at, envelope_id",
            (run_id,),
        ).fetchall()
        run["agent_envelopes"] = [_json_load(item["payload_json"], {}) for item in envelope_rows]
        if include_events:
            event_rows = conn.execute(
                "SELECT * FROM run_events WHERE run_id = ? ORDER BY sequence",
                (run_id,),
            ).fetchall()
            run["event_refs"] = [self._event_payload(item) for item in event_rows]
        else:
            run["event_refs"] = []
        run["delivery_ledger"] = [
            dict(item)
            for item in list(run.get("event_refs") or [])
            if str(item.get("event_type") or "").strip() in DELIVERY_LEDGER_EVENT_TYPES
        ]
        run.setdefault("entry_node_ids", [])
        run.setdefault("approval_state", {"status": "not_required"})
        run.setdefault("run_policy_snapshot", {})
        return run

    def load_run(self, run_id: str, *, include_events: bool = True) -> dict[str, Any] | None:
        self._require_initialized()
        clean_id = _identifier(run_id, "run_id")
        with self._connection() as conn:
            return self._projection_in_connection(conn, clean_id, include_events=include_events)

    def list_runs(self, *, limit: int = 100) -> list[dict[str, Any]]:
        self._require_initialized()
        bounded = max(1, min(int(limit), 1000))
        with self._connection() as conn:
            rows = conn.execute(
                "SELECT * FROM runs ORDER BY updated_at DESC, run_id DESC LIMIT ?",
                (bounded,),
            ).fetchall()
            return [self._projection_in_connection(conn, str(row["run_id"])) for row in rows]

    def create_run(
        self,
        run: dict[str, Any],
        *,
        idempotency_key: str | None = None,
        source: str = "scheduler",
    ) -> dict[str, Any]:
        self._require_initialized()
        if not isinstance(run, dict):
            raise TypeError("run must be an object.")
        clean = _redacted(run)
        run_id = _identifier(clean.get("run_id"), "run_id")
        graph_id = _identifier(clean.get("graph_id"), "graph_id")
        task_id = _identifier(clean.get("task_id"), "task_id")
        trace_id = _identifier(clean.get("trace_id") or f"trace-{run_id}", "trace_id")
        context_id = str(clean.get("context_id") or "").strip() or None
        status = str(clean.get("status") or "queued").strip() or "queued"
        created_at = str(clean.get("created_at") or now_iso()).strip()
        updated_at = str(clean.get("updated_at") or created_at).strip()
        state_version = max(0, int(clean.get("state_version") or 0))
        clean.update(
            {
                "run_id": run_id,
                "graph_id": graph_id,
                "task_id": task_id,
                "trace_id": trace_id,
                "context_id": context_id,
                "status": status,
                "created_at": created_at,
                "updated_at": updated_at,
                "state_version": state_version,
            }
        )
        payload_hash = hashlib.sha256(_json_text(clean).encode("utf-8")).hexdigest()
        with self._transaction() as conn:
            if idempotency_key:
                idem = _identifier(idempotency_key, "idempotency_key")
                mapped = conn.execute(
                    "SELECT run_id, payload_hash FROM run_idempotency WHERE idempotency_key = ?",
                    (idem,),
                ).fetchone()
                if mapped is not None:
                    if str(mapped["payload_hash"]) != payload_hash:
                        raise ImmutableRecordConflict("idempotency_key is already bound to a different run payload.")
                    existing = self._projection_in_connection(conn, str(mapped["run_id"]))
                    if existing is not None:
                        return existing
            existing_row = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
            if existing_row is not None:
                existing = self._projection_in_connection(conn, run_id)
                # The run row is the mutable projection.  A repeated create is
                # therefore idempotent as long as its immutable identity agrees;
                # state changes must use compare_and_swap_run instead.
                immutable_fields = ("run_id", "graph_id", "task_id", "trace_id", "context_id", "created_at")
                if any((existing or {}).get(key) != clean.get(key) for key in immutable_fields):
                    raise ImmutableRecordConflict(f"run_id already exists with a different immutable identity: {run_id}")
                return existing or clean
            conn.execute(
                """INSERT INTO runs(run_id, graph_id, task_id, trace_id, context_id, status, state_version, created_at, updated_at, payload_json, legacy_status, source)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    run_id,
                    graph_id,
                    task_id,
                    trace_id,
                    context_id,
                    status,
                    state_version,
                    created_at,
                    updated_at,
                    _json_text(clean),
                    str(clean.get("legacy_status") or "") or None,
                    str(source or "scheduler"),
                ),
            )
            if idempotency_key:
                conn.execute(
                    "INSERT INTO run_idempotency(idempotency_key, run_id, payload_hash, created_at) VALUES(?,?,?,?)",
                    (idem, run_id, payload_hash, now_iso()),
                )
            self._insert_attempts(conn, clean)
            self._insert_artifacts(conn, clean)
            self._insert_agent_envelopes(conn, clean)
            self._insert_events(conn, clean)
            return self._projection_in_connection(conn, run_id) or clean

    def _insert_attempts(self, conn: sqlite3.Connection, run: dict[str, Any]) -> None:
        for item in list(run.get("node_run_states") or []):
            if not isinstance(item, dict):
                continue
            node_id = str(item.get("node_id") or "").strip()
            if not node_id:
                continue
            attempt = int(item.get("attempt_count") or 0)
            if attempt <= 0:
                continue
            status = str(item.get("status") or "queued").strip() or "queued"
            updated_at = str(item.get("updated_at") or run.get("updated_at") or now_iso()).strip()
            self._insert_attempt(conn, run_id=str(run["run_id"]), node_id=node_id, attempt=attempt, status=status, started_at=item.get("started_at"), updated_at=updated_at, payload=item)

    def _insert_attempt(
        self,
        conn: sqlite3.Connection,
        *,
        run_id: str,
        node_id: str,
        attempt: int,
        status: str,
        started_at: Any,
        updated_at: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        clean = _redacted(payload)
        existing = conn.execute(
            "SELECT payload_json FROM node_attempts WHERE run_id = ? AND node_id = ? AND attempt = ?",
            (run_id, node_id, attempt),
        ).fetchone()
        if existing is not None:
            old = _json_load(existing["payload_json"], {})
            if _json_text(old) != _json_text(clean):
                raise ImmutableRecordConflict(f"node attempt is immutable: {run_id}/{node_id}/{attempt}")
            return old
        conn.execute(
            "INSERT INTO node_attempts(run_id,node_id,attempt,status,started_at,updated_at,payload_json) VALUES(?,?,?,?,?,?,?)",
            (run_id, node_id, attempt, status, str(started_at or "") or None, updated_at, _json_text(clean)),
        )
        return clean

    def record_node_attempt(
        self,
        run_id: str,
        node_id: str,
        attempt: int,
        *,
        status: str,
        payload: dict[str, Any] | None = None,
        started_at: str | None = None,
        updated_at: str | None = None,
    ) -> dict[str, Any]:
        self._require_initialized()
        clean_run = _identifier(run_id, "run_id")
        clean_node = _identifier(node_id, "node_id")
        clean_attempt = max(1, int(attempt))
        with self._transaction() as conn:
            if conn.execute("SELECT 1 FROM runs WHERE run_id = ?", (clean_run,)).fetchone() is None:
                raise ValueError(f"Unknown run_id: {clean_run}")
            return self._insert_attempt(
                conn,
                run_id=clean_run,
                node_id=clean_node,
                attempt=clean_attempt,
                status=str(status or "queued").strip() or "queued",
                started_at=started_at,
                updated_at=str(updated_at or now_iso()),
                payload=dict(payload or {"node_id": clean_node, "attempt_count": clean_attempt, "status": status}),
            )

    def _insert_artifacts(self, conn: sqlite3.Connection, run: dict[str, Any]) -> None:
        for item in list(run.get("artifact_refs") or []):
            if isinstance(item, dict) and str(item.get("artifact_id") or "").strip():
                try:
                    self._insert_artifact(conn, run=run, artifact=item)
                except ImmutableRecordConflict:
                    # Legacy compact refs may enrich an existing artifact with
                    # UI-only labels/status.  The durable artifact identity is
                    # immutable; retain the first persisted evidence.
                    continue

    def _insert_artifact(self, conn: sqlite3.Connection, *, run: dict[str, Any], artifact: dict[str, Any]) -> dict[str, Any]:
        clean = _redacted(artifact)
        artifact_id = _identifier(clean.get("artifact_id"), "artifact_id")
        run_id = _identifier(run.get("run_id"), "run_id")
        existing = conn.execute("SELECT payload_json FROM artifacts WHERE artifact_id = ?", (artifact_id,)).fetchone()
        if existing is not None:
            old = _json_load(existing["payload_json"], {})
            if _json_text(old) != _json_text(clean):
                raise ImmutableRecordConflict(f"artifact is immutable: {artifact_id}")
            return old
        path = str(clean.get("path") or clean.get("relative_path") or "").replace("\\", "/").strip() or None
        uri = str(clean.get("artifact_uri") or "").strip() or None
        conn.execute(
            "INSERT INTO artifacts(artifact_id,run_id,task_id,artifact_uri,relative_path,status,payload_json,created_at) VALUES(?,?,?,?,?,?,?,?)",
            (
                artifact_id,
                run_id,
                str(run.get("task_id") or ""),
                uri,
                path,
                str(clean.get("status") or "ready"),
                _json_text(clean),
                str(clean.get("created_at") or run.get("created_at") or now_iso()),
            ),
        )
        return clean

    def record_artifact(self, run_id: str, artifact: dict[str, Any]) -> dict[str, Any]:
        self._require_initialized()
        with self._transaction() as conn:
            row = conn.execute("SELECT * FROM runs WHERE run_id = ?", (_identifier(run_id, "run_id"),)).fetchone()
            if row is None:
                raise ValueError(f"Unknown run_id: {run_id}")
            return self._insert_artifact(conn, run=self._row_run(row), artifact=artifact)

    def _insert_agent_envelopes(self, conn: sqlite3.Connection, run: dict[str, Any]) -> None:
        for item in list(run.get("agent_envelopes") or []):
            if isinstance(item, dict) and str(item.get("envelope_id") or "").strip():
                self._insert_agent_envelope(conn, envelope=item)

    def _insert_agent_envelope(
        self,
        conn: sqlite3.Connection,
        *,
        envelope: dict[str, Any],
    ) -> dict[str, Any]:
        clean = _redacted(envelope)
        envelope_id = _identifier(clean.get("envelope_id"), "envelope_id")
        run_id = _identifier(clean.get("run_id"), "run_id")
        task_id = _identifier(clean.get("task_id"), "task_id")
        message_id = _identifier(clean.get("message_id"), "message_id")
        delivery = dict(clean.get("delivery") or {})
        idempotency_key = _identifier(delivery.get("idempotency_key"), "delivery.idempotency_key")
        trace_id = _identifier(delivery.get("trace_id"), "delivery.trace_id")
        metadata = dict(clean.get("metadata") or {})
        graph_id = _identifier(metadata.get("graph_id"), "metadata.graph_id")
        source_node_id = _identifier(metadata.get("source_node_id"), "metadata.source_node_id")
        target_node_id = _identifier(metadata.get("target_node_id"), "metadata.target_node_id")
        created_at = str(clean.get("created_at") or now_iso()).strip() or now_iso()
        existing = conn.execute(
            "SELECT payload_json FROM agent_envelopes WHERE envelope_id = ?",
            (envelope_id,),
        ).fetchone()
        if existing is not None:
            old = _json_load(existing["payload_json"], {})
            if _json_text(old) != _json_text(clean):
                raise ImmutableRecordConflict(f"agent envelope is immutable: {envelope_id}")
            return old
        duplicate = conn.execute(
            "SELECT payload_json FROM agent_envelopes WHERE run_id = ? AND idempotency_key = ?",
            (run_id, idempotency_key),
        ).fetchone()
        if duplicate is not None:
            old = _json_load(duplicate["payload_json"], {})
            if _json_text(old) != _json_text(clean):
                raise ImmutableRecordConflict(f"delivery idempotency key is immutable: {run_id}/{idempotency_key}")
            return old
        conn.execute(
            """INSERT INTO agent_envelopes(
                   envelope_id, run_id, task_id, graph_id, source_node_id, target_node_id,
                   message_id, idempotency_key, trace_id, created_at, payload_json
               ) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
            (
                envelope_id,
                run_id,
                task_id,
                graph_id,
                source_node_id,
                target_node_id,
                message_id,
                idempotency_key,
                trace_id,
                created_at,
                _json_text(clean),
            ),
        )
        return clean

    def record_agent_envelope(self, envelope: dict[str, Any]) -> dict[str, Any]:
        self._require_initialized()
        clean_run_id = _identifier(envelope.get("run_id"), "run_id")
        with self._transaction() as conn:
            if conn.execute("SELECT 1 FROM runs WHERE run_id = ?", (clean_run_id,)).fetchone() is None:
                raise ValueError(f"Unknown run_id: {clean_run_id}")
            return self._insert_agent_envelope(conn, envelope=envelope)

    def get_agent_envelope(self, envelope_id: str) -> dict[str, Any] | None:
        self._require_initialized()
        with self._connection() as conn:
            row = conn.execute(
                "SELECT payload_json FROM agent_envelopes WHERE envelope_id = ?",
                (_identifier(envelope_id, "envelope_id"),),
            ).fetchone()
            if row is None:
                return None
            return _json_load(row["payload_json"], {})

    def list_agent_envelopes(
        self,
        *,
        run_id: str | None = None,
        source_node_id: str | None = None,
        target_node_id: str | None = None,
    ) -> list[dict[str, Any]]:
        self._require_initialized()
        query = "SELECT payload_json FROM agent_envelopes"
        clauses: list[str] = []
        params: list[Any] = []
        if str(run_id or "").strip():
            clauses.append("run_id = ?")
            params.append(_identifier(run_id, "run_id"))
        if str(source_node_id or "").strip():
            clauses.append("source_node_id = ?")
            params.append(_identifier(source_node_id, "source_node_id"))
        if str(target_node_id or "").strip():
            clauses.append("target_node_id = ?")
            params.append(_identifier(target_node_id, "target_node_id"))
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY created_at, envelope_id"
        with self._connection() as conn:
            return [
                _json_load(row["payload_json"], {})
                for row in conn.execute(query, tuple(params)).fetchall()
            ]

    def _insert_events(self, conn: sqlite3.Connection, run: dict[str, Any]) -> None:
        next_sequence = 0
        for item in list(run.get("event_refs") or []):
            if not isinstance(item, dict):
                continue
            event = dict(item)
            event.setdefault("event_id", f"{run['run_id']}-event-{next_sequence}")
            event.setdefault("run_id", run["run_id"])
            event.setdefault("task_id", run["task_id"])
            event.setdefault("trace_id", run.get("trace_id") or f"trace-{run['run_id']}")
            event.setdefault("event_type", "state_snapshot")
            event.setdefault("created_at", run.get("created_at") or now_iso())
            event.setdefault("sequence", next_sequence)
            sequence = int(event.get("sequence") or 0)
            if sequence < next_sequence:
                sequence = next_sequence
                event["sequence"] = sequence
            self._insert_event(conn, event, sequence=sequence)
            next_sequence = sequence + 1

    def _merge_runtime_records(self, conn: sqlite3.Connection, run: dict[str, Any]) -> None:
        """Merge immutable attempts, artifacts, and events in the same transaction.

        Legacy/full-run callers may send a newer snapshot containing records
        already seen by the store.  Existing immutable records are accepted
        idempotently; only missing records are appended.  This keeps the run
        row and its append-only evidence in one SQLite commit.
        """

        run_id = _identifier(run.get("run_id"), "run_id")
        task_id = _identifier(run.get("task_id"), "task_id")
        trace_id = _identifier(run.get("trace_id") or f"trace-{run_id}", "trace_id")
        for item in list(run.get("node_run_states") or []):
            if not isinstance(item, dict):
                continue
            node_id = str(item.get("node_id") or "").strip()
            if not node_id:
                continue
            attempt = int(item.get("attempt_count") or 0)
            if attempt <= 0:
                continue
            exists = conn.execute(
                "SELECT 1 FROM node_attempts WHERE run_id=? AND node_id=? AND attempt=?",
                (run_id, node_id, attempt),
            ).fetchone()
            if exists is None:
                self._insert_attempt(
                    conn,
                    run_id=run_id,
                    node_id=node_id,
                    attempt=attempt,
                    status=str(item.get("status") or "queued").strip() or "queued",
                    started_at=item.get("started_at"),
                    updated_at=str(item.get("updated_at") or run.get("updated_at") or now_iso()),
                    payload=item,
                )
        for item in list(run.get("artifact_refs") or []):
            if isinstance(item, dict) and str(item.get("artifact_id") or "").strip():
                try:
                    self._insert_artifact(conn, run=run, artifact=item)
                except ImmutableRecordConflict:
                    # Compact legacy refs may enrich an existing artifact with
                    # UI-only labels or status.  Keep the first durable record.
                    continue
        for item in list(run.get("agent_envelopes") or []):
            if isinstance(item, dict) and str(item.get("envelope_id") or "").strip():
                self._insert_agent_envelope(conn, envelope=item)
        for item in list(run.get("event_refs") or run.get("timeline_events") or []):
            if not isinstance(item, dict):
                continue
            event = dict(item)
            event.setdefault("run_id", run_id)
            event.setdefault("task_id", task_id)
            event.setdefault("trace_id", trace_id)
            event.setdefault("event_type", "state_snapshot")
            event.setdefault("created_at", run.get("updated_at") or run.get("created_at") or now_iso())
            if not str(event.get("event_id") or "").strip():
                event["event_id"] = f"{run_id}-event-{hashlib.sha256(_json_text(event).encode('utf-8')).hexdigest()[:20]}"
            existing = conn.execute("SELECT * FROM run_events WHERE event_id=?", (str(event["event_id"]),)).fetchone()
            if existing is not None:
                event.setdefault("sequence", int(existing["sequence"]))
                event.setdefault("created_at", str(existing["created_at"]))
                try:
                    self._insert_event(conn, event, sequence=int(event["sequence"]))
                except ImmutableRecordConflict:
                    # The compatibility projection may carry a shorter or
                    # enriched summary for an already durable event.  Keep
                    # the first immutable event payload and continue.
                    pass
                continue
            requested_sequence = event.get("sequence")
            if requested_sequence is not None:
                occupied = conn.execute(
                    "SELECT event_id FROM run_events WHERE run_id=? AND sequence=?",
                    (run_id, int(requested_sequence)),
                ).fetchone()
                if occupied is not None:
                    event.pop("sequence", None)
            self._insert_event(conn, event, sequence=None if event.get("sequence") is None else int(event["sequence"]))

    def _insert_event(self, conn: sqlite3.Connection, event: dict[str, Any], *, sequence: int | None = None) -> dict[str, Any]:
        clean = _redacted(event)
        event_id = _identifier(clean.get("event_id"), "event_id")
        run_id = _identifier(clean.get("run_id"), "run_id")
        task_id = _identifier(clean.get("task_id"), "task_id")
        trace_id = _identifier(clean.get("trace_id"), "trace_id")
        event_type = str(clean.get("event_type") or "state_snapshot").strip() or "state_snapshot"
        created_at = str(clean.get("created_at") or now_iso()).strip()
        if sequence is None:
            if clean.get("sequence") is not None:
                sequence = int(clean["sequence"])
            else:
                row = conn.execute("SELECT COALESCE(MAX(sequence), -1) AS latest FROM run_events WHERE run_id = ?", (run_id,)).fetchone()
                sequence = int(row["latest"]) + 1
        clean.update(
            {
                "event_id": event_id,
                "run_id": run_id,
                "task_id": task_id,
                "trace_id": trace_id,
                "event_type": event_type,
                "created_at": created_at,
                "sequence": int(sequence),
            }
        )
        existing = conn.execute("SELECT * FROM run_events WHERE event_id = ?", (event_id,)).fetchone()
        if existing is not None:
            old = self._event_payload(existing)
            if _json_text(old) != _json_text(clean):
                raise ImmutableRecordConflict(f"event is immutable: {event_id}")
            return old
        conflict = conn.execute("SELECT event_id FROM run_events WHERE run_id = ? AND sequence = ?", (run_id, int(sequence))).fetchone()
        if conflict is not None:
            raise ImmutableRecordConflict(f"event sequence is already occupied: {run_id}/{sequence}")
        clean["sequence"] = int(sequence)
        conn.execute(
            "INSERT INTO run_events(event_id,run_id,task_id,trace_id,sequence,event_type,created_at,payload_json) VALUES(?,?,?,?,?,?,?,?)",
            (event_id, run_id, task_id, trace_id, int(sequence), event_type, created_at, _json_text(clean)),
        )
        return clean

    def append_event(self, event: dict[str, Any], *, expected_state_version: int | None = None) -> dict[str, Any]:
        self._require_initialized()
        if not isinstance(event, dict):
            raise TypeError("event must be an object.")
        clean = _redacted(event)
        run_id = _identifier(clean.get("run_id"), "run_id")
        with self._transaction() as conn:
            row = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
            if row is None:
                raise ValueError(f"Unknown run_id: {run_id}")
            if expected_state_version is not None and int(row["state_version"]) != int(expected_state_version):
                raise StateVersionConflict(f"run {run_id} expected state_version {expected_state_version}, found {row['state_version']}")
            return self._insert_event(conn, clean)

    def compare_and_swap_run(
        self,
        run_id: str,
        expected_state_version: int,
        *,
        status: str | None = None,
        patch: dict[str, Any] | None = None,
        event: dict[str, Any] | None = None,
        runtime_records: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self._require_initialized()
        clean_id = _identifier(run_id, "run_id")
        with self._transaction() as conn:
            row = conn.execute("SELECT * FROM runs WHERE run_id = ?", (clean_id,)).fetchone()
            if row is None:
                raise ValueError(f"Unknown run_id: {clean_id}")
            existing_event_id = str((event or {}).get("event_id") or "").strip()
            if existing_event_id:
                existing_event = conn.execute("SELECT * FROM run_events WHERE event_id = ?", (existing_event_id,)).fetchone()
                if existing_event is not None:
                    return self._projection_in_connection(conn, clean_id) or {}
            current_version = int(row["state_version"])
            if current_version != int(expected_state_version):
                raise StateVersionConflict(f"run {clean_id} expected state_version {expected_state_version}, found {current_version}")
            current_status = str(row["status"])
            next_status = str(status if status is not None else current_status).strip() or current_status
            dry_run_promotion = current_status == "dry_run_passed" and next_status in {
                "completed",
                "failed",
                "cancelled",
                "partial",
            }
            if current_status in TERMINAL_RUN_STATUSES and next_status != current_status and not dry_run_promotion:
                raise TerminalStateConflict(f"terminal run {clean_id} cannot transition {current_status} -> {next_status}")
            if current_status == "needs_review" and next_status != "needs_review":
                raise TerminalStateConflict(f"legacy run {clean_id} requires review before transition")
            current_payload = self._row_run(row)
            if patch:
                safe_patch = _redacted(patch)
                for forbidden in ("run_id", "graph_id", "task_id", "trace_id", "created_at", "state_version"):
                    if forbidden in safe_patch and safe_patch[forbidden] != current_payload.get(forbidden):
                        raise ValueError(f"run identity field cannot be changed: {forbidden}")
                current_payload.update(safe_patch)
            current_payload["status"] = next_status
            current_payload["updated_at"] = str(current_payload.get("updated_at") or now_iso())
            next_version = current_version + 1
            current_payload["state_version"] = next_version
            conn.execute(
                "UPDATE runs SET status=?, state_version=?, updated_at=?, payload_json=? WHERE run_id=? AND state_version=?",
                (next_status, next_version, current_payload["updated_at"], _json_text(current_payload), clean_id, expected_state_version),
            )
            if runtime_records is not None:
                self._merge_runtime_records(conn, runtime_records)
            if event is not None:
                event_payload = dict(event)
                event_payload.setdefault("run_id", clean_id)
                event_payload.setdefault("task_id", current_payload["task_id"])
                event_payload.setdefault("trace_id", current_payload["trace_id"])
                event_payload.setdefault("created_at", current_payload["updated_at"])
                self._insert_event(conn, event_payload)
            return self._projection_in_connection(conn, clean_id) or current_payload

    def sync_legacy_run(self, run: dict[str, Any]) -> dict[str, Any]:
        """Ingest a validated legacy run as a monotonic compatibility projection."""

        self._require_initialized()
        run_id = _identifier(run.get("run_id"), "run_id")
        with self._connection() as conn:
            existing_row = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
            existing = self._projection_in_connection(conn, run_id) if existing_row is not None else None
        if existing is None:
            return self.create_run(run, source="legacy_projection")
        incoming_version = int(run.get("state_version") or 0)
        current_version = int(existing.get("state_version") or 0)
        if incoming_version <= current_version:
            with self._transaction() as conn:
                self._merge_runtime_records(conn, run)
                return self._projection_in_connection(conn, run_id) or existing
        status = str(run.get("status") or existing.get("status") or "queued")
        if str(existing.get("status") or "") in TERMINAL_RUN_STATUSES and status != existing.get("status"):
            raise TerminalStateConflict(f"legacy projection attempted terminal regression for {run_id}")
        patch = _redacted(dict(run))
        patch.pop("state_version", None)
        return self.compare_and_swap_run(run_id, current_version, status=status, patch=patch, runtime_records=run)

    def sync_compact_run_ref(self, run_ref: dict[str, Any]) -> dict[str, Any] | None:
        """Update only the observable projection fields from the current bridge."""

        if not isinstance(run_ref, dict):
            raise TypeError("run_ref must be an object.")
        run_id = str(run_ref.get("run_id") or "").strip()
        if not run_id:
            return None
        last_conflict: StateVersionConflict | None = None
        for _attempt in range(3):
            current = self.load_run(run_id)
            if current is None:
                return None
            current_version = int(current.get("state_version") or 0)
            patch = {
                key: deepcopy(run_ref[key])
                for key in (
                    "status",
                    "updated_at",
                    "entry_node_ids",
                    "node_status_counts",
                    "node_outcome_counts",
                    "artifact_count",
                    "event_count",
                    "approval_state",
                    "approval_details",
                    "latest_event_type",
                    "latest_event_at",
                    "metrics",
                    "budget",
                    "worker_count",
                    "worker_bindings",
                    "policy_snapshot",
                )
                if key in run_ref
            }
            patch["state_version"] = current_version
            runtime_records = {
                **dict(run_ref),
                # Compact live run refs carry the latest node snapshot, not an
                # immutable attempt journal. Attempt rows must be created only
                # through explicit durable attempt writes.
                "node_run_states": [],
                "event_refs": [dict(item) for item in list(run_ref.get("timeline_events") or []) if isinstance(item, dict)],
                "artifact_refs": [
                    *[dict(item) for item in list(run_ref.get("artifact_refs") or []) if isinstance(item, dict)],
                    *[dict(item) for item in list(run_ref.get("diagnostic_refs") or []) if isinstance(item, dict)],
                ],
            }
            raw_approval_state = runtime_records.get("approval_state")
            if not isinstance(raw_approval_state, dict):
                runtime_records["approval_state"] = {
                    "status": str(raw_approval_state or "not_required").strip() or "not_required"
                }
            if "approval_state" in patch and not isinstance(patch["approval_state"], dict):
                patch["approval_state"] = dict(runtime_records["approval_state"])
            try:
                # Projection updates still receive a durable state transition so a
                # scheduler never observes a partially-written ref.
                return self.compare_and_swap_run(
                    run_id,
                    current_version,
                    status=str(run_ref.get("status") or current.get("status") or "queued"),
                    patch={key: value for key, value in patch.items() if key != "state_version"},
                    runtime_records=runtime_records,
                )
            except StateVersionConflict as exc:
                last_conflict = exc
                continue
        if last_conflict is not None:
            raise last_conflict
        return None

    def acquire_lease(
        self,
        run_id: str,
        node_id: str,
        attempt: int,
        *,
        owner_boot_id: str,
        ttl_seconds: int = 60,
        lease_id: str | None = None,
    ) -> dict[str, Any]:
        self._require_initialized()
        clean_run = _identifier(run_id, "run_id")
        clean_node = _identifier(node_id, "node_id")
        owner = _identifier(owner_boot_id, "owner_boot_id")
        now = now_iso()
        expires = _iso_plus_seconds(now, max(1, int(ttl_seconds)))
        with self._transaction() as conn:
            if conn.execute("SELECT 1 FROM runs WHERE run_id = ?", (clean_run,)).fetchone() is None:
                raise ValueError(f"Unknown run_id: {clean_run}")
            existing = conn.execute(
                "SELECT * FROM leases WHERE run_id=? AND node_id=? AND attempt=?",
                (clean_run, clean_node, max(1, int(attempt))),
            ).fetchone()
            if existing is not None and str(existing["status"]) == "active" and str(existing["expires_at"]) > now and str(existing["owner_boot_id"]) != owner:
                raise LeaseBusy(f"active lease already held for {clean_run}/{clean_node}/{attempt}")
            clean_lease_id = str(lease_id or (existing["lease_id"] if existing else "lease-" + hashlib.sha256(f"{clean_run}:{clean_node}:{attempt}".encode()).hexdigest()[:20]))
            payload = {"run_id": clean_run, "node_id": clean_node, "attempt": max(1, int(attempt)), "owner_boot_id": owner}
            conn.execute(
                """INSERT INTO leases(lease_id,run_id,node_id,attempt,owner_boot_id,status,acquired_at,heartbeat_at,expires_at,payload_json)
                   VALUES(?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(run_id,node_id,attempt) DO UPDATE SET lease_id=excluded.lease_id, owner_boot_id=excluded.owner_boot_id, status='active', heartbeat_at=excluded.heartbeat_at, expires_at=excluded.expires_at, payload_json=excluded.payload_json""",
                (clean_lease_id, clean_run, clean_node, max(1, int(attempt)), owner, "active", now, now, expires, _json_text(payload)),
            )
            return self._lease_row(conn.execute("SELECT * FROM leases WHERE lease_id = ?", (clean_lease_id,)).fetchone())

    def list_leases(
        self,
        *,
        run_id: str | None = None,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        self._require_initialized()
        query = "SELECT * FROM leases"
        clauses: list[str] = []
        params: list[Any] = []
        if str(run_id or "").strip():
            clauses.append("run_id = ?")
            params.append(_identifier(run_id, "run_id"))
        if str(status or "").strip():
            clauses.append("status = ?")
            params.append(str(status).strip())
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY acquired_at, lease_id"
        with self._connection() as conn:
            return [self._lease_row(row) for row in conn.execute(query, tuple(params)).fetchall()]

    @staticmethod
    def _lease_row(row: sqlite3.Row | None) -> dict[str, Any]:
        if row is None:
            return {}
        payload = _json_load(row["payload_json"], {})
        payload.update(
            {
                "lease_id": row["lease_id"],
                "status": row["status"],
                "acquired_at": row["acquired_at"],
                "heartbeat_at": row["heartbeat_at"],
                "expires_at": row["expires_at"],
            }
        )
        return payload

    def heartbeat_lease(self, lease_id: str, *, owner_boot_id: str, ttl_seconds: int = 60) -> dict[str, Any]:
        self._require_initialized()
        with self._transaction() as conn:
            row = conn.execute("SELECT * FROM leases WHERE lease_id = ?", (_identifier(lease_id, "lease_id"),)).fetchone()
            if row is None or str(row["owner_boot_id"]) != str(owner_boot_id):
                raise LeaseBusy("lease is missing or owned by another scheduler boot")
            now = now_iso()
            expires = _iso_plus_seconds(now, max(1, int(ttl_seconds)))
            conn.execute("UPDATE leases SET heartbeat_at=?, expires_at=?, status='active' WHERE lease_id=?", (now, expires, lease_id))
            return self._lease_row(conn.execute("SELECT * FROM leases WHERE lease_id = ?", (lease_id,)).fetchone())

    def release_lease(self, lease_id: str, *, owner_boot_id: str) -> bool:
        self._require_initialized()
        with self._transaction() as conn:
            row = conn.execute("SELECT owner_boot_id FROM leases WHERE lease_id = ?", (_identifier(lease_id, "lease_id"),)).fetchone()
            if row is None:
                return False
            if str(row["owner_boot_id"]) != str(owner_boot_id):
                raise LeaseBusy("lease is owned by another scheduler boot")
            conn.execute("UPDATE leases SET status='released', heartbeat_at=?, expires_at=? WHERE lease_id=?", (now_iso(), now_iso(), lease_id))
            return True

    def record_inbox(self, idempotency_key: str, *, run_id: str | None = None, event_id: str | None = None, payload: Any = None) -> bool:
        self._require_initialized()
        key = _identifier(idempotency_key, "idempotency_key")
        with self._transaction() as conn:
            cursor = conn.execute(
                "INSERT OR IGNORE INTO inbox(idempotency_key,run_id,event_id,received_at,payload_json) VALUES(?,?,?,?,?)",
                (key, str(run_id or "") or None, str(event_id or "") or None, now_iso(), _json_text(_redacted(payload or {}))),
            )
            return cursor.rowcount == 1

    def enqueue_outbox(self, operation_id: str, run_id: str, *, kind: str, payload: Any = None, node_id: str | None = None) -> dict[str, Any]:
        self._require_initialized()
        op = _identifier(operation_id, "operation_id")
        rid = _identifier(run_id, "run_id")
        now = now_iso()
        clean_payload = _redacted(payload or {})
        with self._transaction() as conn:
            if conn.execute("SELECT 1 FROM runs WHERE run_id=?", (rid,)).fetchone() is None:
                raise ValueError(f"Unknown run_id: {rid}")
            conn.execute(
                "INSERT OR IGNORE INTO outbox(operation_id,run_id,node_id,kind,status,created_at,updated_at,payload_json) VALUES(?,?,?,?,?,?,?,?)",
                (op, rid, str(node_id or "") or None, str(kind or "dispatch"), "pending", now, now, _json_text(clean_payload)),
            )
            return self._outbox_row(conn.execute("SELECT * FROM outbox WHERE operation_id=?", (op,)).fetchone())

    @staticmethod
    def _outbox_row(row: sqlite3.Row | None) -> dict[str, Any] | None:
        if row is None:
            return None
        return {
            "operation_id": row["operation_id"],
            "run_id": row["run_id"],
            "node_id": row["node_id"],
            "kind": row["kind"],
            "status": row["status"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "payload": _json_load(row["payload_json"], {}),
        }

    def get_outbox_operation(self, operation_id: str) -> dict[str, Any] | None:
        self._require_initialized()
        with self._connection() as conn:
            return self._outbox_row(
                conn.execute(
                    "SELECT * FROM outbox WHERE operation_id = ?",
                    (_identifier(operation_id, "operation_id"),),
                ).fetchone()
            )

    def update_outbox_status(
        self,
        operation_id: str,
        *,
        status: str,
        payload: Any | None = None,
    ) -> dict[str, Any] | None:
        self._require_initialized()
        clean_operation_id = _identifier(operation_id, "operation_id")
        clean_status = str(status or "").strip() or "pending"
        with self._transaction() as conn:
            row = conn.execute("SELECT * FROM outbox WHERE operation_id = ?", (clean_operation_id,)).fetchone()
            if row is None:
                return None
            next_payload = _json_load(row["payload_json"], {})
            if payload is not None:
                next_payload = _redacted(payload)
            conn.execute(
                "UPDATE outbox SET status = ?, updated_at = ?, payload_json = ? WHERE operation_id = ?",
                (clean_status, now_iso(), _json_text(next_payload), clean_operation_id),
            )
            return self._outbox_row(conn.execute("SELECT * FROM outbox WHERE operation_id = ?", (clean_operation_id,)).fetchone())

    def record_external_operation(
        self,
        operation_id: str,
        run_id: str,
        *,
        kind: str,
        classification: str,
        status: str,
        external_handle: str | None = None,
        payload: Any = None,
    ) -> dict[str, Any]:
        self._require_initialized()
        now = now_iso()
        with self._transaction() as conn:
            conn.execute(
                """INSERT INTO external_operations(operation_id,run_id,kind,classification,status,external_handle,created_at,updated_at,payload_json)
                   VALUES(?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(operation_id) DO UPDATE SET status=excluded.status, external_handle=COALESCE(excluded.external_handle, external_operations.external_handle), updated_at=excluded.updated_at, payload_json=excluded.payload_json""",
                (
                    _identifier(operation_id, "operation_id"),
                    _identifier(run_id, "run_id"),
                    str(kind or "provider_call"),
                    str(classification or "read_only"),
                    str(status or "pending"),
                    str(external_handle or "") or None,
                    now,
                    now,
                    _json_text(_redacted(payload or {})),
                ),
            )
            return self._external_operation_row(conn.execute("SELECT * FROM external_operations WHERE operation_id=?", (operation_id,)).fetchone())

    @staticmethod
    def _external_operation_row(row: sqlite3.Row | None) -> dict[str, Any] | None:
        if row is None:
            return None
        return {
            "operation_id": row["operation_id"],
            "run_id": row["run_id"],
            "kind": row["kind"],
            "classification": row["classification"],
            "status": row["status"],
            "external_handle": row["external_handle"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "payload": _json_load(row["payload_json"], {}),
        }

    def get_external_operation(self, operation_id: str) -> dict[str, Any] | None:
        self._require_initialized()
        with self._connection() as conn:
            return self._external_operation_row(
                conn.execute(
                    "SELECT * FROM external_operations WHERE operation_id = ?",
                    (_identifier(operation_id, "operation_id"),),
                ).fetchone()
            )

    def rebuild_run_projection(self, run_id: str, *, output_path: str | Path | None = None) -> dict[str, Any] | None:
        run = self.load_run(run_id)
        if run is None:
            return None
        projection = {
            "schema_version": DURABLE_RUN_PROJECTION_SCHEMA_VERSION,
            "run_id": str(run["run_id"]),
            "state_version": int(run.get("state_version") or 0),
            # Derive this from the persisted run so rebuilding a projection is
            # byte-for-byte deterministic and does not create noisy diffs.
            "generated_at": str(run.get("updated_at") or run.get("created_at") or ""),
            "run": _redacted(run),
        }
        if output_path is not None:
            requested = Path(output_path)
            target = requested if requested.is_absolute() else self.workspace_root / requested
            target = target.resolve()
            try:
                target.relative_to(self.workspace_root)
            except ValueError as exc:
                raise SecurityError("Projection output must stay under the workspace root.") from exc
            write_json(target, projection)
            projection["path"] = target.relative_to(self.workspace_root).as_posix()
        return projection

    def rebuild_all_projections(self, *, limit: int = 1000) -> list[dict[str, Any]]:
        projections_root = self.state_root / "projections" / "runs"
        return [item for item in (self.rebuild_run_projection(str(run["run_id"]), output_path=projections_root / f"{run['run_id']}.json") for run in self.list_runs(limit=limit)) if item]

    def migrate_legacy_state(self) -> dict[str, Any]:
        """Import old task JSON/manifests once without deleting or mutating them."""

        self._require_initialized()
        source_path = self.state_root / "tasks.json"
        if not source_path.exists():
            return self._migration_report(status="empty", source_path=source_path, imported_runs=[], needs_review=[])
        try:
            raw_text = source_path.read_text(encoding="utf-8-sig")
            payload = json.loads(raw_text)
        except Exception as exc:
            return self._migration_report(status="needs_review", source_path=source_path, imported_runs=[], needs_review=[{"reason": f"tasks.json unreadable: {type(exc).__name__}"}])
        source_hash = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
        with self._connection() as conn:
            previous = conn.execute("SELECT report_json FROM migration_runs WHERE source_hash=?", (source_hash,)).fetchone()
            if previous is not None:
                report = _json_load(previous["report_json"], {})
                if isinstance(report, dict):
                    report["repeated"] = True
                    return report
        imported_runs: list[dict[str, Any]] = []
        needs_review: list[dict[str, Any]] = []
        tasks = list(payload.get("tasks") or []) if isinstance(payload, dict) else []
        for task in tasks:
            if not isinstance(task, dict):
                continue
            task_id = str(task.get("task_id") or "").strip()
            for ref in list(task.get("graph_run_refs") or []):
                if not isinstance(ref, dict):
                    continue
                run_id = str(ref.get("run_id") or "").strip()
                if not task_id or not run_id:
                    continue
                source_key = hashlib.sha256(f"{task_id}:{run_id}".encode("utf-8")).hexdigest()
                with self._connection() as conn:
                    already = conn.execute("SELECT run_id, classification FROM legacy_imports WHERE source_key=?", (source_key,)).fetchone()
                if already is not None:
                    continue
                try:
                    run = self._load_legacy_manifest(ref, task_id=task_id)
                    if run is None:
                        run = self._compact_legacy_run(ref, task_id=task_id)
                except Exception as exc:
                    needs_review.append(
                        {
                            "run_id": run_id,
                            "task_id": task_id,
                            "reason": f"legacy run could not be normalized: {type(exc).__name__}",
                        }
                    )
                    continue
                run, unsafe_paths = self._sanitize_legacy_paths(run)
                original_status = str(run.get("status") or ref.get("status") or "queued").strip() or "queued"
                classification = "imported"
                reason = "; ".join(unsafe_paths)
                if unsafe_paths:
                    classification = "needs_review"
                if original_status in LEGACY_ACTIVE_STATUSES:
                    classification = "needs_review"
                    active_reason = "legacy run was active at migration time; no automatic resume was attempted"
                    reason = "; ".join(item for item in (reason, active_reason) if item)
                    run["legacy_status"] = original_status
                    run["status"] = "needs_review"
                try:
                    stored = self.create_run(run, source="legacy_migration")
                    with self._transaction() as conn:
                        conn.execute(
                            "INSERT INTO legacy_imports(source_key,run_id,classification,source_schema,reason,imported_at,payload_json) VALUES(?,?,?,?,?,?,?)",
                            (source_key, run_id, classification, str(run.get("schema_version") or "") or None, reason or None, now_iso(), _json_text(_redacted({"run_id": run_id, "task_id": task_id, "legacy_status": original_status}))),
                        )
                    entry = {"run_id": str(stored.get("run_id") or run_id), "task_id": task_id, "classification": classification}
                    imported_runs.append(entry)
                    if classification == "needs_review":
                        needs_review.append({**entry, "reason": reason})
                except Exception as exc:
                    needs_review.append({"run_id": run_id, "task_id": task_id, "reason": f"migration failed: {type(exc).__name__}"})
        report = self._migration_report(status="needs_review" if needs_review else "pass", source_path=source_path, imported_runs=imported_runs, needs_review=needs_review, source_hash=source_hash)
        migration_id = hashlib.sha256(f"{DURABLE_RUN_MIGRATION_SCHEMA_VERSION}:{source_hash}".encode("utf-8")).hexdigest()[:24]
        with self._transaction() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO migration_runs(migration_id,source_hash,source_path,status,report_json,created_at) VALUES(?,?,?,?,?,?)",
                (migration_id, source_hash, source_path.relative_to(self.workspace_root).as_posix(), report["status"], _json_text(report), now_iso()),
            )
        return report

    def _load_legacy_manifest(self, ref: dict[str, Any], *, task_id: str) -> dict[str, Any] | None:
        for artifact in list(ref.get("artifact_refs") or []):
            if not isinstance(artifact, dict):
                continue
            relative = str(artifact.get("path") or "").replace("\\", "/").strip()
            if "run-manifest" not in relative:
                continue
            try:
                path = resolve_under(self.workspace_root, relative)
            except SecurityError:
                continue
            if not path.exists():
                continue
            try:
                loaded = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            if isinstance(loaded, dict) and str(loaded.get("run_id") or "").strip() == str(ref.get("run_id") or "").strip():
                return _redacted(loaded)
        return None

    def _compact_legacy_run(self, ref: dict[str, Any], *, task_id: str) -> dict[str, Any]:
        run_id = _identifier(ref.get("run_id"), "run_id")
        created_at = str(ref.get("created_at") or now_iso())
        return _redacted(
            {
                "schema_version": "astrabridge-task-graph-run-v1",
                "run_id": run_id,
                "graph_id": _identifier(ref.get("graph_id"), "graph_id"),
                "task_id": task_id,
                "trace_id": str(ref.get("trace_id") or f"trace-{run_id}"),
                "context_id": str(ref.get("context_id") or f"context-{run_id}"),
                "status": str(ref.get("status") or "queued"),
                "entry_node_ids": list(ref.get("entry_node_ids") or []),
                "node_run_states": [],
                "artifact_refs": [dict(item) for item in list(ref.get("artifact_refs") or []) if isinstance(item, dict)],
                "event_refs": [dict(item) for item in list(ref.get("timeline_events") or []) if isinstance(item, dict)],
                "approval_state": {"status": str(ref.get("approval_state") or "not_required")},
                "run_policy_snapshot": dict(ref.get("policy_snapshot") or {}),
                "created_at": created_at,
                "updated_at": str(ref.get("updated_at") or created_at),
                "state_version": max(0, int(ref.get("state_version") or 0)),
            }
        )

    def _sanitize_legacy_paths(self, run: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
        """Keep only workspace-relative artifact paths in imported state.

        A legacy ref may contain an absolute path from a different machine or
        an external mount.  Persist a stable hash marker instead of that path,
        and make the run require review so a scheduler cannot follow it.
        """

        clean = _redacted(run)
        reasons: list[str] = []
        for collection_name in ("artifact_refs", "diagnostic_refs"):
            normalized_items: list[dict[str, Any]] = []
            for item in list(clean.get(collection_name) or []):
                if not isinstance(item, dict):
                    continue
                current = dict(item)
                raw_path = str(current.get("path") or "").strip()
                if raw_path:
                    try:
                        resolved = resolve_under(self.workspace_root, raw_path)
                        current["path"] = resolved.relative_to(self.workspace_root).as_posix()
                    except SecurityError:
                        marker = hashlib.sha256(raw_path.encode("utf-8")).hexdigest()[:20]
                        current["path"] = f"UNSAFE_EXTERNAL_PATH/{marker}"
                        reasons.append(f"{collection_name} contains a path outside the workspace")
                normalized_items.append(current)
            if normalized_items or collection_name in clean:
                clean[collection_name] = normalized_items
        return clean, reasons

    def _migration_report(
        self,
        *,
        status: str,
        source_path: Path,
        imported_runs: list[dict[str, Any]],
        needs_review: list[dict[str, Any]],
        source_hash: str | None = None,
    ) -> dict[str, Any]:
        return {
            "schema_version": DURABLE_RUN_MIGRATION_SCHEMA_VERSION,
            "status": status,
            "source_path": source_path.relative_to(self.workspace_root).as_posix(),
            "source_hash": source_hash,
            "imported_runs": imported_runs,
            "needs_review": needs_review,
            "imported_count": len(imported_runs),
            "needs_review_count": len(needs_review),
        }

    def close(self) -> None:
        """Connections are short-lived; this method documents lifecycle ownership."""

        self._initialized = False

    def __enter__(self) -> "DurableRunEventStore":
        self.initialize()
        return self

    def __exit__(self, _exc_type: Any, _exc: Any, _tb: Any) -> None:
        self.close()


def _iso_plus_seconds(value: str, seconds: int) -> str:
    import datetime as dt

    parsed = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return (parsed + dt.timedelta(seconds=int(seconds))).isoformat()


__all__ = [
    "DURABLE_RUN_MIGRATION_SCHEMA_VERSION",
    "DURABLE_RUN_PROJECTION_SCHEMA_VERSION",
    "DURABLE_RUN_STORE_FILENAME",
    "DURABLE_RUN_STORE_SCHEMA_VERSION",
    "DurableRunEventStore",
    "DurableRunStoreError",
    "ImmutableRecordConflict",
    "LeaseBusy",
    "StateVersionConflict",
    "TerminalStateConflict",
]
