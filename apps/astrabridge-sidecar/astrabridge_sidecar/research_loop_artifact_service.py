from __future__ import annotations

import re
from copy import deepcopy
from pathlib import Path
from typing import Any

from .artifact_content import decode_artifact_content
from .common import append_jsonl, new_id, now_iso, read_json, write_json
from .security import SECRET_RE, SecurityError, resolve_under
from .state_service import DEFAULT_SUBMISSION_WORKFLOW


ALLOWED_RESEARCH_LOOP_PREFIXES = (
    "PUBLIC/research_loop/",
    "PROVENANCE/research_loop/",
)
CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


class ResearchLoopArtifactService:
    def __init__(self, project_root_provider, project_update=None) -> None:
        self._project_root_provider = project_root_provider
        self._project_update = project_update

    def write_artifacts(self, payload: dict[str, Any]) -> dict[str, Any]:
        root = self._project_root_provider()
        files = payload.get("files")
        if not isinstance(files, list) or not files:
            raise ValueError("files must be a non-empty list.")

        loop_id = new_id("LOOP")
        written: list[dict[str, Any]] = []
        for item in files:
            if not isinstance(item, dict):
                raise ValueError("Each research loop artifact must be an object.")
            relative_path = self._validate_relative_path(str(item.get("path") or ""))
            content = decode_artifact_content(item, "Research loop artifact")
            if SECRET_RE.search(content):
                raise SecurityError(f"Secret-like content detected in research loop artifact: {relative_path}")
            if CONTROL_CHAR_RE.search(content):
                raise SecurityError(f"Control character detected in research loop artifact: {relative_path}")
            target = resolve_under(root, relative_path)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8", newline="\n")
            written.append(
                {
                    "path": relative_path,
                    "role": str(item.get("role") or "research_loop_artifact"),
                    "bytes": len(content.encode("utf-8")),
                    "updated_at": now_iso(),
                }
            )

        workflow_updates = payload.get("workflow_updates") if isinstance(payload.get("workflow_updates"), dict) else {}
        self._update_research_state(root, loop_id, written, str(payload.get("summary") or ""), workflow_updates)
        append_jsonl(
            root / "PROVENANCE" / "run_manifest.jsonl",
            {
                "run_id": f"RUN-{loop_id}",
                "timestamp": now_iso(),
                "status": "research_loop_artifacts_written",
                "privacy_level": "public_or_sanitized",
                "outputs": [item["path"] for item in written],
                "summary": str(payload.get("summary") or ""),
            },
        )
        return {"loop_id": loop_id, "written": written}

    def _validate_relative_path(self, value: str) -> str:
        normalized = value.replace("\\", "/").lstrip("/")
        if not normalized or ".." in Path(normalized).parts:
            raise SecurityError(f"Invalid research loop artifact path: {value}")
        if not any(normalized.startswith(prefix) for prefix in ALLOWED_RESEARCH_LOOP_PREFIXES):
            raise SecurityError(
                "Research loop artifacts must be written under PUBLIC/research_loop/ or PROVENANCE/research_loop/."
            )
        if "/PRIVATE/" in f"/{normalized}/" or normalized.startswith("PRIVATE/"):
            raise SecurityError(f"Research loop artifacts may not target PRIVATE paths: {value}")
        return normalized

    def _update_research_state(
        self,
        root: Path,
        loop_id: str,
        written: list[dict[str, Any]],
        summary: str,
        workflow_updates: dict[str, Any],
    ) -> None:
        state = read_json(root / "PUBLIC" / "research_state.json", {"schema_version": "research-state-v1"})
        workflow = state.get("submission_workflow") or deepcopy(DEFAULT_SUBMISSION_WORKFLOW)
        for key in (
            "source_verification",
            "proof_audit",
            "venue_requirements",
            "claim_evidence",
            "novelty_positioning",
            "review_rounds",
            "status",
        ):
            if key in workflow_updates:
                workflow[key] = workflow_updates[key]

        previous = list(workflow.get("research_loop_artifacts") or [])
        indexed = {str(item.get("path")): item for item in previous if isinstance(item, dict)}
        for item in written:
            indexed[item["path"]] = item
        workflow["research_loop_artifacts"] = list(indexed.values())
        workflow["last_research_loop_batch"] = {
            "loop_id": loop_id,
            "summary": summary,
            "written_count": len(written),
            "updated_at": now_iso(),
        }
        workflow.setdefault("status", "research_loop_artifacts_ready_for_acceptance")

        state["submission_workflow"] = workflow
        state["macro_phase"] = "research_loop"
        state["internal_phase"] = "loop_acceptance_gate"
        state["status"] = "research_loop_artifacts_ready_for_acceptance"
        state["pending_user_confirmation"] = True
        state["choice_prompts"] = [self._artifact_acceptance_prompt()]
        state["updated_at"] = now_iso()
        write_json(root / "PUBLIC" / "research_state.json", state)
        if self._project_update:
            self._project_update({"current_macro_phase": "research_loop", "current_phase": "loop_acceptance_gate"})

    def _artifact_acceptance_prompt(self) -> dict[str, Any]:
        return {
            "prompt_id": "CP-RESEARCH-LOOP-ARTIFACT-ACCEPTANCE",
            "stage": "loop_acceptance_gate",
            "question": "Do you accept the current research-loop audit artifacts?",
            "recommended_option": "accept_and_plan_next",
            "why_recommended": "Accepted source verification, proof audit, novelty positioning, and claim-evidence records can govern the next loop or final paper entry.",
            "options": [
                {
                    "id": "accept_and_plan_next",
                    "label": "Accept and plan next",
                    "description": "Use the current audit artifacts as accepted evidence and return to next-loop alignment.",
                    "is_recommended": True,
                },
                {
                    "id": "revise_artifacts",
                    "label": "Revise artifacts first",
                    "description": "Stay at the acceptance gate and repair missing sources, proof checks, or claim-evidence links.",
                },
                {
                    "id": "expand_audit_scope",
                    "label": "Expand audit scope",
                    "description": "Add more references, proof obligations, or novelty comparisons before accepting.",
                },
            ],
            "free_form_enabled": True,
            "free_form_label": "Natural-language additions",
            "free_form_placeholder": "Add acceptance notes, missing checks, or next-loop priorities.",
            "requires_human_response": True,
        }

