from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .artifact_content import decode_artifact_content
from .common import append_jsonl, new_id, now_iso, read_json, write_json
from .security import SECRET_RE, SecurityError, resolve_under


ALLOWED_ARTIFACT_PREFIXES = (
    "PUBLIC/paper/",
    "PUBLIC/submission/",
    "PROVENANCE/paper/",
)
CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


class PaperArtifactService:
    def __init__(self, project_root_provider, project_update=None) -> None:
        self._project_root_provider = project_root_provider
        self._project_update = project_update

    def write_artifacts(self, payload: dict[str, Any]) -> dict[str, Any]:
        root = self._project_root_provider()
        files = payload.get("files")
        if not isinstance(files, list) or not files:
            raise ValueError("files must be a non-empty list.")
        batch_id = new_id("PAPER")
        written: list[dict[str, Any]] = []
        for item in files:
            if not isinstance(item, dict):
                raise ValueError("Each paper artifact must be an object.")
            relative_path = self._validate_relative_path(str(item.get("path") or ""))
            content = decode_artifact_content(item, "Paper artifact")
            if SECRET_RE.search(content):
                raise SecurityError(f"Secret-like content detected in paper artifact: {relative_path}")
            if CONTROL_CHAR_RE.search(content):
                raise SecurityError(f"Control character detected in paper artifact: {relative_path}")
            target = resolve_under(root, relative_path)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8", newline="\n")
            written.append(
                {
                    "path": relative_path,
                    "role": str(item.get("role") or "paper_artifact"),
                    "bytes": len(content.encode("utf-8")),
                    "updated_at": now_iso(),
                }
            )
        workflow_updates = payload.get("workflow_updates") if isinstance(payload.get("workflow_updates"), dict) else {}
        self._update_research_state(root, batch_id, written, str(payload.get("summary") or ""), workflow_updates)
        append_jsonl(
            root / "PROVENANCE" / "run_manifest.jsonl",
            {
                "run_id": f"RUN-{batch_id}",
                "timestamp": now_iso(),
                "status": "paper_artifacts_written",
                "privacy_level": "public",
                "outputs": [item["path"] for item in written],
                "summary": str(payload.get("summary") or ""),
            },
        )
        return {"batch_id": batch_id, "written": written}

    def _validate_relative_path(self, value: str) -> str:
        normalized = value.replace("\\", "/").lstrip("/")
        if not normalized or ".." in Path(normalized).parts:
            raise SecurityError(f"Invalid paper artifact path: {value}")
        if not any(normalized.startswith(prefix) for prefix in ALLOWED_ARTIFACT_PREFIXES):
            raise SecurityError(
                "Paper artifacts must be written under PUBLIC/paper/, PUBLIC/submission/, or PROVENANCE/paper/."
            )
        if "/PRIVATE/" in f"/{normalized}/" or normalized.startswith("PRIVATE/"):
            raise SecurityError(f"Paper artifacts may not target PRIVATE paths: {value}")
        return normalized

    def _update_research_state(
        self,
        root: Path,
        batch_id: str,
        written: list[dict[str, Any]],
        summary: str,
        workflow_updates: dict[str, Any],
    ) -> None:
        state = read_json(root / "PUBLIC" / "research_state.json", {"schema_version": "research-state-v1"})
        workflow = state.get("submission_workflow") or {}
        for key in ("source_verification", "proof_audit", "review_rounds", "status"):
            if key in workflow_updates:
                workflow[key] = workflow_updates[key]
        previous = list(workflow.get("artifact_status") or [])
        indexed = {str(item.get("path")): item for item in previous if isinstance(item, dict)}
        for item in written:
            indexed[item["path"]] = item
        workflow["artifact_status"] = list(indexed.values())
        workflow["last_artifact_batch"] = {
            "batch_id": batch_id,
            "summary": summary,
            "written_count": len(written),
            "updated_at": now_iso(),
        }
        if "status" not in workflow_updates:
            workflow["status"] = "paper_artifacts_written"
        state["submission_workflow"] = workflow
        state["macro_phase"] = "final_product"
        state["internal_phase"] = "final_product_production"
        state["updated_at"] = now_iso()
        write_json(root / "PUBLIC" / "research_state.json", state)
        if self._project_update:
            self._project_update({"current_macro_phase": "final_product", "current_phase": "final_product_production"})

