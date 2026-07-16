from __future__ import annotations

from pathlib import Path
from threading import RLock
from typing import Any

from ..common import now_iso, read_json, write_json
from ..security import redact_sensitive
from .specs import AutomationInboxItem, AutomationRun, AutomationSpec


AUTOMATION_STORE_SCHEMA_VERSION = "astrabridge-automation-store-v1"
AUTOMATION_RUN_INDEX_SCHEMA_VERSION = "astrabridge-automation-run-index-v1"
AUTOMATION_INBOX_INDEX_SCHEMA_VERSION = "astrabridge-automation-inbox-index-v1"

_LOCKS: dict[str, RLock] = {}
_LOCKS_GUARD = RLock()


class AutomationStore:
    def __init__(self, project_service) -> None:
        self._projects = project_service

    def list_automations(self, *, include_archived: bool = False) -> list[dict[str, Any]]:
        records = [dict(item) for item in list(self._spec_state().get("automations") or []) if isinstance(item, dict)]
        if not include_archived:
            records = [item for item in records if not item.get("archived_at")]
        records.sort(key=lambda item: str(item.get("updated_at") or ""), reverse=True)
        return [self._public_automation_record(item) for item in records]

    def get_automation(self, automation_id: str, *, include_archived: bool = False) -> dict[str, Any] | None:
        clean_id = str(automation_id or "").strip()
        if not clean_id:
            return None
        for item in list(self._spec_state().get("automations") or []):
            if not isinstance(item, dict):
                continue
            if str(item.get("automation_id") or "").strip() != clean_id:
                continue
            if item.get("archived_at") and not include_archived:
                return None
            return self._public_automation_record(item)
        return None

    def create_automation(self, payload: dict[str, Any]) -> dict[str, Any]:
        normalized = AutomationSpec.normalize(payload).to_dict()
        clean_id = str(normalized.get("automation_id") or "")
        with self._path_lock(self._spec_path()):
            state = self._spec_state()
            records = [dict(item) for item in list(state.get("automations") or []) if isinstance(item, dict)]
            if any(str(item.get("automation_id") or "").strip() == clean_id and not item.get("archived_at") for item in records):
                raise ValueError(f"Automation already exists: {clean_id}")
            records = [item for item in records if str(item.get("automation_id") or "").strip() != clean_id]
            records.insert(0, self._storage_automation_record(normalized))
            state["automations"] = records[:500]
            state["updated_at"] = now_iso()
            self._write_spec_state(state)
        stored = self.get_automation(clean_id, include_archived=True)
        if not stored:
            raise ValueError(f"Failed to persist automation: {clean_id}")
        return stored

    def update_automation(self, automation_id: str, patch: dict[str, Any]) -> dict[str, Any]:
        existing = self._require_automation_record(automation_id, include_archived=False)
        merged = self._merge_automation(existing, patch)
        normalized = AutomationSpec.normalize(merged).to_dict()
        with self._path_lock(self._spec_path()):
            state = self._spec_state()
            records = [dict(item) for item in list(state.get("automations") or []) if isinstance(item, dict)]
            updated = False
            next_records: list[dict[str, Any]] = []
            for item in records:
                if str(item.get("automation_id") or "").strip() == str(automation_id).strip():
                    archived_at = item.get("archived_at")
                    archived_reason = item.get("archived_reason")
                    replacement = self._storage_automation_record(normalized)
                    if archived_at:
                        replacement["archived_at"] = archived_at
                    if archived_reason:
                        replacement["archived_reason"] = archived_reason
                    next_records.append(replacement)
                    updated = True
                else:
                    next_records.append(item)
            if not updated:
                raise ValueError("Automation not found.")
            state["automations"] = next_records[:500]
            state["updated_at"] = now_iso()
            self._write_spec_state(state)
        stored = self.get_automation(str(automation_id))
        if not stored:
            raise ValueError(f"Failed to persist automation update: {automation_id}")
        return stored

    def delete_automation(self, automation_id: str, *, reason: str = "deleted") -> dict[str, Any]:
        clean_id = str(automation_id or "").strip()
        with self._path_lock(self._spec_path()):
            state = self._spec_state()
            records = [dict(item) for item in list(state.get("automations") or []) if isinstance(item, dict)]
            updated = False
            next_records: list[dict[str, Any]] = []
            for item in records:
                if str(item.get("automation_id") or "").strip() == clean_id:
                    archived = dict(item)
                    archived["enabled"] = False
                    archived["archived_at"] = archived.get("archived_at") or now_iso()
                    archived["archived_reason"] = str(reason or "deleted").strip() or "deleted"
                    archived["updated_at"] = now_iso()
                    next_records.append(self._sanitize_payload(archived))
                    updated = True
                else:
                    next_records.append(item)
            if not updated:
                raise ValueError("Automation not found.")
            state["automations"] = next_records[:500]
            state["updated_at"] = now_iso()
            self._write_spec_state(state)
        stored = self.get_automation(clean_id, include_archived=True)
        if not stored:
            raise ValueError(f"Failed to archive automation: {clean_id}")
        return stored

    def pause_automation(self, automation_id: str) -> dict[str, Any]:
        return self.update_automation(str(automation_id), {"enabled": False})

    def resume_automation(self, automation_id: str) -> dict[str, Any]:
        existing = self._require_automation_record(automation_id, include_archived=True)
        if existing.get("archived_at"):
            raise ValueError("Archived automations cannot be resumed.")
        return self.update_automation(str(automation_id), {"enabled": True})

    def record_run(self, payload: dict[str, Any]) -> dict[str, Any]:
        normalized = AutomationRun.normalize(payload).to_dict()
        run_id = str(normalized.get("run_id") or "")
        automation_id = str(normalized.get("automation_id") or "")
        with self._path_lock(self._run_index_path()):
            state = self._run_state()
            runs = [dict(item) for item in list(state.get("runs") or []) if isinstance(item, dict)]
            replaced = False
            next_runs: list[dict[str, Any]] = []
            for item in runs:
                if str(item.get("run_id") or "").strip() == run_id:
                    next_runs.append(self._sanitize_payload(normalized))
                    replaced = True
                else:
                    next_runs.append(item)
            if not replaced:
                next_runs.insert(0, self._sanitize_payload(normalized))
            state["runs"] = next_runs[:5000]
            state["updated_at"] = now_iso()
            self._write_run_state(state)
        self._update_last_run_projection(automation_id=automation_id, run=normalized)
        return self.get_run(run_id) or normalized

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        clean_id = str(run_id or "").strip()
        if not clean_id:
            return None
        for item in list(self._run_state().get("runs") or []):
            if not isinstance(item, dict):
                continue
            if str(item.get("run_id") or "").strip() == clean_id:
                return dict(item)
        return None

    def list_runs(self, automation_id: str | None = None) -> list[dict[str, Any]]:
        clean_automation_id = str(automation_id or "").strip()
        runs = [dict(item) for item in list(self._run_state().get("runs") or []) if isinstance(item, dict)]
        if clean_automation_id:
            runs = [item for item in runs if str(item.get("automation_id") or "").strip() == clean_automation_id]
        runs.sort(key=lambda item: str(item.get("due_at") or item.get("started_at") or ""), reverse=True)
        return runs

    def upsert_inbox_item(self, payload: dict[str, Any]) -> dict[str, Any]:
        normalized = AutomationInboxItem.normalize(payload).to_dict()
        item_id = str(normalized.get("item_id") or "")
        with self._path_lock(self._inbox_index_path()):
            state = self._inbox_state()
            items = [dict(item) for item in list(state.get("items") or []) if isinstance(item, dict)]
            replaced = False
            next_items: list[dict[str, Any]] = []
            for item in items:
                if str(item.get("item_id") or "").strip() == item_id:
                    next_items.append(self._sanitize_payload(normalized))
                    replaced = True
                else:
                    next_items.append(item)
            if not replaced:
                next_items.insert(0, self._sanitize_payload(normalized))
            state["items"] = next_items[:5000]
            state["updated_at"] = now_iso()
            self._write_inbox_state(state)
        return self.get_inbox_item(item_id) or normalized

    def get_inbox_item(self, item_id: str) -> dict[str, Any] | None:
        clean_id = str(item_id or "").strip()
        if not clean_id:
            return None
        for item in list(self._inbox_state().get("items") or []):
            if not isinstance(item, dict):
                continue
            if str(item.get("item_id") or "").strip() == clean_id:
                return dict(item)
        return None

    def update_inbox_item(self, item_id: str, patch: dict[str, Any]) -> dict[str, Any]:
        existing = self.get_inbox_item(item_id)
        if not existing:
            raise ValueError("Automation inbox item not found.")
        merged = dict(existing)
        for key, value in dict(patch or {}).items():
            if key in {"schema_version", "item_id", "run_id", "automation_id", "project_id", "created_at"}:
                continue
            merged[key] = value
        merged["updated_at"] = now_iso()
        return self.upsert_inbox_item(merged)

    def promote_inbox_item(self, item_id: str, promotion_ref: str) -> dict[str, Any]:
        clean_ref = str(promotion_ref or "").strip()
        if not clean_ref:
            raise ValueError("promotion_ref is required.")
        return self.update_inbox_item(item_id, {"state": "promoted", "promotion_ref": clean_ref})

    def list_inbox_items(self, automation_id: str | None = None, *, include_archived: bool = True) -> list[dict[str, Any]]:
        clean_automation_id = str(automation_id or "").strip()
        items = [dict(item) for item in list(self._inbox_state().get("items") or []) if isinstance(item, dict)]
        if clean_automation_id:
            items = [item for item in items if str(item.get("automation_id") or "").strip() == clean_automation_id]
        if not include_archived:
            items = [item for item in items if str(item.get("state") or "").strip().lower() != "archived"]
        items.sort(key=lambda item: str(item.get("updated_at") or item.get("created_at") or ""), reverse=True)
        return items

    def inbox_summary(self, automation_id: str | None = None) -> dict[str, int]:
        summary = {"unread": 0, "reviewed": 0, "archived": 0, "promoted": 0}
        for item in self.list_inbox_items(automation_id):
            state = str(item.get("state") or "").strip().lower()
            if state in summary:
                summary[state] += 1
        return summary

    def _require_automation_record(self, automation_id: str, *, include_archived: bool) -> dict[str, Any]:
        record = self.get_automation(automation_id, include_archived=include_archived)
        if not record:
            raise ValueError("Automation not found.")
        return record

    def _merge_automation(self, existing: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
        merged = dict(existing)
        nested_fields = {"schedule", "runtime", "workspace", "triage", "limits", "agentic_update"}
        for key, value in dict(patch or {}).items():
            if key in {"schema_version", "automation_id", "project_id", "created_at", "archived_at", "archived_reason"}:
                continue
            if key in nested_fields and isinstance(value, dict):
                current = dict(merged.get(key) or {})
                current.update(value)
                merged[key] = current
                continue
            merged[key] = value
        merged["updated_at"] = now_iso()
        return merged

    def _update_last_run_projection(self, *, automation_id: str, run: dict[str, Any]) -> None:
        clean_id = str(automation_id or "").strip()
        if not clean_id:
            return
        with self._path_lock(self._spec_path()):
            state = self._spec_state()
            records = [dict(item) for item in list(state.get("automations") or []) if isinstance(item, dict)]
            changed = False
            next_records: list[dict[str, Any]] = []
            for item in records:
                if str(item.get("automation_id") or "").strip() == clean_id:
                    updated = dict(item)
                    updated["last_run_at"] = str(run.get("finished_at") or run.get("started_at") or run.get("due_at") or "") or None
                    updated["last_status"] = str(run.get("status") or "") or None
                    updated["updated_at"] = now_iso()
                    next_records.append(self._sanitize_payload(updated))
                    changed = True
                else:
                    next_records.append(item)
            if not changed:
                return
            state["automations"] = next_records[:500]
            state["updated_at"] = now_iso()
            self._write_spec_state(state)

    def _public_automation_record(self, record: dict[str, Any]) -> dict[str, Any]:
        item = dict(record)
        automation_id = str(item.get("automation_id") or "").strip()
        item["inbox_summary"] = self.inbox_summary(automation_id) if automation_id else self.inbox_summary()
        return item

    def _spec_state(self) -> dict[str, Any]:
        state = dict(read_json(self._spec_path(), {"schema_version": AUTOMATION_STORE_SCHEMA_VERSION, "automations": []}))
        state.setdefault("schema_version", AUTOMATION_STORE_SCHEMA_VERSION)
        state.setdefault("automations", [])
        return state

    def _run_state(self) -> dict[str, Any]:
        state = dict(read_json(self._run_index_path(), {"schema_version": AUTOMATION_RUN_INDEX_SCHEMA_VERSION, "runs": []}))
        state.setdefault("schema_version", AUTOMATION_RUN_INDEX_SCHEMA_VERSION)
        state.setdefault("runs", [])
        return state

    def _inbox_state(self) -> dict[str, Any]:
        state = dict(read_json(self._inbox_index_path(), {"schema_version": AUTOMATION_INBOX_INDEX_SCHEMA_VERSION, "items": []}))
        state.setdefault("schema_version", AUTOMATION_INBOX_INDEX_SCHEMA_VERSION)
        state.setdefault("items", [])
        return state

    def _write_spec_state(self, state: dict[str, Any]) -> None:
        payload = self._sanitize_payload(state)
        write_json(self._spec_path(), payload)

    def _write_run_state(self, state: dict[str, Any]) -> None:
        payload = self._sanitize_payload(state)
        write_json(self._run_index_path(), payload)

    def _write_inbox_state(self, state: dict[str, Any]) -> None:
        payload = self._sanitize_payload(state)
        write_json(self._inbox_index_path(), payload)

    def _storage_automation_record(self, payload: dict[str, Any]) -> dict[str, Any]:
        sanitized = self._sanitize_payload(payload)
        sanitized.setdefault("archived_at", None)
        sanitized.setdefault("archived_reason", None)
        return sanitized

    def _sanitize_payload(self, payload: Any) -> Any:
        return redact_sensitive(payload)

    def _automations_root(self) -> Path:
        return self._projects.require_shell_subdir("automations")

    def _runs_root(self) -> Path:
        return self._projects.require_shell_subdir("automations", "runs")

    def _inbox_root(self) -> Path:
        return self._projects.require_shell_subdir("automations", "inbox")

    def _spec_path(self) -> Path:
        return self._automations_root() / "automations.json"

    def _run_index_path(self) -> Path:
        return self._runs_root() / "index.json"

    def _inbox_index_path(self) -> Path:
        return self._inbox_root() / "index.json"

    def _path_lock(self, path: Path) -> RLock:
        key = str(path.resolve()).lower()
        with _LOCKS_GUARD:
            lock = _LOCKS.get(key)
            if lock is None:
                lock = RLock()
                _LOCKS[key] = lock
            return lock
