from __future__ import annotations

import re
from typing import Any

from .common import append_jsonl, new_id, now_iso, read_json, write_json
from .security import SECRET_RE, SecurityError


CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


DEFAULT_CHOICE_PROMPTS = [
    {
        "prompt_id": "CP-INITIALIZATION-MATERIAL-SCOPE",
        "stage": "initialization_intake",
        "question": "How should Research OS interpret this initialization material bundle?",
        "recommended_option": "whole_folder_research_plan",
        "why_recommended": "The input includes drafts, submission requirements, templates, and example papers, so the app should first generate a folder-wide research plan instead of entering final-product production.",
        "options": [
            {
                "id": "whole_folder_research_plan",
                "label": "Use the full bundle",
                "description": "Identify file roles, evidence gaps, proof risks, and venue requirements before forming the research plan.",
                "is_recommended": True,
            },
            {
                "id": "draft_first",
                "label": "Diagnose the draft first",
                "description": "Read the main paper draft first while keeping templates, examples, and supporting files as context.",
            },
            {
                "id": "venue_first",
                "label": "Start from venue fit",
                "description": "Check Neural Networks rules, template, and comparable-paper style before deriving the research plan.",
            },
        ],
        "free_form_enabled": True,
        "free_form_label": "Natural-language additions",
        "free_form_placeholder": "Name the most important, reliable, or easy-to-miss files in this bundle.",
        "requires_human_response": True,
    },
    {
        "prompt_id": "CP-INITIALIZATION-SOURCE-VERIFICATION",
        "stage": "initialization_intake",
        "question": "How strict should source-authenticity verification be?",
        "recommended_option": "strict_online",
        "why_recommended": "A submission manuscript cannot rely on memory citations; every citation, venue rule, and template source needs DOI, arXiv, publisher, or official-page evidence.",
        "options": [
            {
                "id": "strict_online",
                "label": "Verify every source online",
                "description": "Record URL, access date, source type, and verification status for all venue rules and references.",
                "is_recommended": True,
            },
            {
                "id": "core_only",
                "label": "Verify core sources first",
                "description": "First verify venue rules, templates, and core references, then complete secondary references later.",
            },
            {
                "id": "local_first",
                "label": "Organize local sources first",
                "description": "First reconcile local PDFs, BibTeX, and example papers, then add online evidence in one pass.",
            },
        ],
        "free_form_enabled": True,
        "free_form_label": "Natural-language additions",
        "free_form_placeholder": "Add websites, literature scope, unacceptable source types, or citation-style constraints.",
        "requires_human_response": True,
    },
    {
        "prompt_id": "CP-INITIALIZATION-RESEARCH-PLAN",
        "stage": "initialization_intake",
        "question": "What research plan should be produced before entering the loop?",
        "recommended_option": "proof_and_submission_plan",
        "why_recommended": "A theoretical submission needs proof obligations, related-work positioning, venue fit, and the final submission-package path to be aligned together.",
        "options": [
            {
                "id": "proof_and_submission_plan",
                "label": "Proof and submission plan",
                "description": "Plan model definitions, theorem proof route, citation verification, writing structure, and final submission materials together.",
                "is_recommended": True,
            },
            {
                "id": "proof_first",
                "label": "Proof risk first",
                "description": "Audit model assumptions, depth/width bounds, construction details, and possible counterexamples before writing.",
            },
            {
                "id": "novelty_first",
                "label": "Novelty positioning first",
                "description": "Map contributions against arithmetic circuits, polynomial networks, and approximation theory before proof polishing.",
            },
        ],
        "free_form_enabled": True,
        "free_form_label": "Natural-language additions",
        "free_form_placeholder": "Add proof, writing, submission, or rebuttal-review priorities for the research plan.",
        "requires_human_response": True,
    },
]


DEFAULT_SUBMISSION_WORKFLOW = {
    "target_venue": "Neural Networks",
    "article_type": "Full Article",
    "target_section": "Mathematical and Computational Analysis",
    "status": "paper_workflow_ready",
    "author_metadata": {
        "author": "Cheng Yinzhu",
        "corresponding_author": "Cheng Yinzhu",
        "affiliations": [
            "Renmin University of China",
            "Beijing Institute of Mathematical Sciences and Applications (BIMSA)",
        ],
        "funding": "none",
        "competing_interests": "none",
        "ai_declaration": "verify_current_elsevier_policy_before_finalizing",
    },
    "source_verification": [
        {
            "id": "SRC-GUIDE",
            "label": "Neural Networks Guide for Authors",
            "status": "needs_online_refresh",
            "required_evidence": "official guide URL, access date, article type, abstract/highlights/AI declaration rules",
        },
        {
            "id": "SRC-TEMPLATE",
            "label": "Elsevier LaTeX template and bibliography style",
            "status": "needs_online_refresh",
            "required_evidence": "official template URL, template package version or access date",
        },
        {
            "id": "SRC-REFERENCES",
            "label": "All manuscript references",
            "status": "needs_doi_arxiv_publisher_check",
            "required_evidence": "DOI, arXiv, publisher page, or other reliable source for every cited item",
        },
    ],
    "proof_audit": [
        {
            "id": "PROOF-MODEL",
            "label": "Quadratic network model and output-layer assumptions",
            "status": "needs_review",
        },
        {
            "id": "PROOF-GATES",
            "label": "Identity, addition, and multiplication gate validity under hidden-layer activation rules",
            "status": "needs_review",
        },
        {
            "id": "PROOF-BOUNDS",
            "label": "Depth and width bounds for monomials and full polynomials",
            "status": "needs_review",
        },
        {
            "id": "PROOF-NOVELTY",
            "label": "Novelty framing against arithmetic circuits, polynomial networks, and approximation theory",
            "status": "needs_review",
        },
    ],
    "review_rounds": [],
    "workflow_gaps": [],
}


class ResearchStateService:
    def __init__(self, project_root_provider, project_update=None) -> None:
        self._project_root_provider = project_root_provider
        self._project_update = project_update

    def read_state(self) -> dict[str, Any]:
        root = self._project_root_provider()
        research_state = read_json(root / "PUBLIC" / "research_state.json", self._default_research_state())
        project_state = read_json(root / ".research-os" / "project.json", {})
        material_manifest = self._material_manifest_summary(root)
        prompts = research_state.get("choice_prompts") or research_state.get("questions") or DEFAULT_CHOICE_PROMPTS
        if "submission_workflow" not in research_state:
            research_state["submission_workflow"] = DEFAULT_SUBMISSION_WORKFLOW
        return {
            "project": project_state,
            "research_state": research_state,
            "choice_prompts": prompts,
            "submission_workflow": research_state.get("submission_workflow", DEFAULT_SUBMISSION_WORKFLOW),
            "material_manifest": material_manifest,
            "run_monitor": read_json(root / "PUBLIC" / "run_monitor.json", {"runs": []}),
            "archive_index": read_json(root / "PUBLIC" / "archive_index.json", {"archives": []}),
        }

    def submit_intake(self, payload: dict[str, Any]) -> dict[str, Any]:
        root = self._project_root_provider()
        session_id = payload.get("session_id") or new_id("INTAKE")
        free_text = str(payload.get("free_text") or "")
        private_intake = root / "PRIVATE" / "intake" / session_id
        private_intake.mkdir(parents=True, exist_ok=True)
        if free_text.strip():
            (private_intake / "free_text.md").write_text(free_text, encoding="utf-8")

        packet = {
            "schema_version": "desktop-intake-v1",
            "session_id": session_id,
            "created_at": now_iso(),
            "free_text_present": bool(free_text.strip()),
            "free_text_summary": "Raw free text is stored under PRIVATE/intake/<session_id>/free_text.md.",
            "source_links": payload.get("source_links", []),
            "uploaded_files": payload.get("uploaded_files", []),
            "privacy_default": "private",
            "status": "pending_intake_analysis",
            "source": "desktop_app",
        }
        write_json(root / "CONTROL" / "intake_queue" / f"{session_id}.intake.json", packet)

        state = read_json(root / "PUBLIC" / "research_state.json", self._default_research_state())
        material_manifest = self._material_manifest_summary(root)
        state.update(
            {
                "schema_version": "research-state-v1",
                "updated_at": now_iso(),
                "macro_phase": "initialization",
                "internal_phase": "initialization_intake",
                "status": "pending_intake_analysis",
                "active_session_id": session_id,
                "pending_user_confirmation": True,
                "choice_prompts": DEFAULT_CHOICE_PROMPTS,
                "submission_workflow": state.get("submission_workflow", DEFAULT_SUBMISSION_WORKFLOW),
                "intake_summary": {
                    "free_text_present": bool(free_text.strip()),
                    "free_text_summary": "Raw free text is private; summarized metadata is safe to render.",
                    "uploaded_file_count": len(payload.get("uploaded_files", [])),
                    "source_link_count": len(payload.get("source_links", [])),
                    "material_manifest": material_manifest,
                },
            }
        )
        write_json(root / "PUBLIC" / "research_state.json", state)
        self._sync_project_phase("initialization", "initialization_intake")
        append_jsonl(
            root / "PROVENANCE" / "run_manifest.jsonl",
            {
                "run_id": f"RUN-{session_id}",
                "timestamp": now_iso(),
                "status": "intake_saved",
                "privacy_level": "private_metadata_only",
                "outputs": ["PUBLIC/research_state.json", f"CONTROL/intake_queue/{session_id}.intake.json"],
            },
        )
        return {"packet": packet, "state": state}

    def select_final_products(self, tracks: list[str], free_form: str = "") -> dict[str, Any]:
        root = self._project_root_provider()
        allowed = {"paper", "report", "software"}
        selected = [track for track in tracks if track in allowed]
        if not selected:
            raise ValueError("At least one final product track is required.")
        plan = {
            "product_plan_id": new_id("FP"),
            "created_at": now_iso(),
            "phase": "final_product_selection",
            "selected_tracks": selected,
            "choice_prompts": [
                {
                    "prompt_id": "CP-FINAL-PRODUCT",
                    "purpose": "Select final product tracks and natural-language expectations.",
                }
            ],
            "tracks": {track: {"status": "selected"} for track in selected},
            "intermediate_artifact_policy": "preserve",
            "human_gates": ["public_export", "submission", "external_writeback", "software_release"],
            "user_free_form_expectations": free_form,
            "status": "approved",
        }
        if "paper" in selected:
            plan["tracks"]["paper"].update(
                {
                    "target_venue": "Neural Networks",
                    "article_type": "Full Article",
                    "target_section": "Mathematical and Computational Analysis",
                    "source_verification_required": True,
                    "proof_audit_required": True,
                    "review_rebuttal_required": True,
                }
            )
        write_json(root / "PUBLIC" / "final_product_plan.json", plan)
        state = read_json(root / "PUBLIC" / "research_state.json", self._default_research_state())
        state["macro_phase"] = "final_product"
        state["internal_phase"] = "final_product_selection"
        state["submission_workflow"] = state.get("submission_workflow", DEFAULT_SUBMISSION_WORKFLOW)
        state["updated_at"] = now_iso()
        write_json(root / "PUBLIC" / "research_state.json", state)
        self._sync_project_phase("final_product", "final_product_selection")
        return plan

    def submit_choice_response(self, payload: dict[str, Any]) -> dict[str, Any]:
        root = self._project_root_provider()
        prompt_id = str(payload.get("prompt_id") or "").strip()
        option_id = str(payload.get("option_id") or "").strip()
        free_form = str(payload.get("free_form") or "")
        if not prompt_id or not option_id:
            raise ValueError("prompt_id and option_id are required.")
        response = {
            "response_id": new_id("CR"),
            "created_at": now_iso(),
            "prompt_id": prompt_id,
            "option_id": option_id,
            "free_form": free_form,
            "source": "desktop_app",
        }
        target = root / "CONTROL" / "choice_responses" / f"{response['response_id']}.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        write_json(target, response)
        state = read_json(root / "PUBLIC" / "research_state.json", self._default_research_state())
        state["updated_at"] = now_iso()
        state["last_choice_response"] = {
            "prompt_id": prompt_id,
            "option_id": option_id,
            "free_form_present": bool(free_form.strip()),
        }
        if prompt_id == "CP-RESEARCH-PLAN-ACCEPTANCE":
            if option_id == "accept_with_audit":
                state["macro_phase"] = "research_loop"
                state["internal_phase"] = "loop_plan_alignment"
                state["status"] = "research_plan_accepted_pending_loop_alignment"
                state["pending_user_confirmation"] = True
                state["choice_prompts"] = [self._research_loop_alignment_prompt()]
                self._sync_project_phase("research_loop", "loop_plan_alignment")
            else:
                state["macro_phase"] = "research_loop"
                state["internal_phase"] = "loop_acceptance_gate"
                state["status"] = "research_plan_revision_requested" if option_id == "revise_plan" else "research_plan_material_expansion_requested"
                state["pending_user_confirmation"] = True
                state["choice_prompts"] = [self._research_plan_acceptance_prompt()]
                self._sync_project_phase("research_loop", "loop_acceptance_gate")
        elif prompt_id == "CP-RESEARCH-LOOP-ARTIFACT-ACCEPTANCE":
            if option_id == "accept_and_plan_next":
                state["macro_phase"] = "research_loop"
                state["internal_phase"] = "loop_plan_alignment"
                state["status"] = "research_loop_artifact_accepted_pending_next_alignment"
                state["pending_user_confirmation"] = True
                state["choice_prompts"] = [self._next_research_loop_prompt(state.get("submission_workflow", {}))]
                self._sync_project_phase("research_loop", "loop_plan_alignment")
            else:
                state["macro_phase"] = "research_loop"
                state["internal_phase"] = "loop_acceptance_gate"
                state["status"] = "research_loop_artifact_revision_requested"
                state["pending_user_confirmation"] = True
                state["choice_prompts"] = [self._research_loop_artifact_acceptance_prompt()]
                self._sync_project_phase("research_loop", "loop_acceptance_gate")
        elif prompt_id in {"CP-FIRST-RESEARCH-LOOP", "CP-NEXT-RESEARCH-LOOP"}:
            state["macro_phase"] = "research_loop"
            state["internal_phase"] = "loop_execute_analyze"
            state["status"] = f"research_loop_execution_requested:{option_id}"
            state["pending_user_confirmation"] = False
            state["choice_prompts"] = []
            self._sync_project_phase("research_loop", "loop_execute_analyze")
        else:
            state["pending_user_confirmation"] = False
        write_json(root / "PUBLIC" / "research_state.json", state)
        return response

    def write_research_plan(self, payload: dict[str, Any]) -> dict[str, Any]:
        root = self._project_root_provider()
        content = str(payload.get("content") or "").strip()
        summary = str(payload.get("summary") or "").strip()
        if not content:
            raise ValueError("Research plan content is required.")
        self._validate_public_text(content, "research plan")
        self._validate_public_text(summary, "research plan summary")

        plan_id = new_id("RP")
        plan_record = {
            "research_plan_id": plan_id,
            "created_at": now_iso(),
            "summary": summary or "Research plan generated from initialization materials.",
            "path": "PUBLIC/research_plan.md",
            "json_path": "PUBLIC/research_plan.json",
            "source_manifest": self._material_manifest_summary(root),
            "acceptance_required": True,
            "status": "ready_for_researcher_acceptance",
            "next_actions": payload.get("next_actions", []),
            "known_gaps": payload.get("known_gaps", []),
        }
        (root / "PUBLIC").mkdir(parents=True, exist_ok=True)
        (root / "PUBLIC" / "research_plan.md").write_text(content + "\n", encoding="utf-8")
        write_json(root / "PUBLIC" / "research_plan.json", plan_record)

        state = read_json(root / "PUBLIC" / "research_state.json", self._default_research_state())
        state.update(
            {
                "schema_version": "research-state-v1",
                "updated_at": now_iso(),
                "macro_phase": "research_loop",
                "internal_phase": "loop_acceptance_gate",
                "status": "research_plan_ready_for_acceptance",
                "pending_user_confirmation": True,
                "research_plan": plan_record,
                "choice_prompts": [self._research_plan_acceptance_prompt()],
            }
        )
        write_json(root / "PUBLIC" / "research_state.json", state)
        self._sync_project_phase("research_loop", "loop_acceptance_gate")
        append_jsonl(
            root / "PROVENANCE" / "run_manifest.jsonl",
            {
                "run_id": f"RUN-{plan_id}",
                "timestamp": now_iso(),
                "status": "research_plan_written",
                "privacy_level": "public",
                "outputs": ["PUBLIC/research_plan.md", "PUBLIC/research_plan.json", "PUBLIC/research_state.json"],
            },
        )
        return {"plan": plan_record, "state": state}

    def record_workflow_gap(self, payload: dict[str, Any]) -> dict[str, Any]:
        root = self._project_root_provider()
        description = str(payload.get("description") or "").strip()
        severity = str(payload.get("severity") or "medium").strip() or "medium"
        source = str(payload.get("source") or "desktop_app").strip() or "desktop_app"
        if not description:
            raise ValueError("Workflow gap description is required.")
        record = {
            "gap_id": new_id("GAP"),
            "created_at": now_iso(),
            "severity": severity,
            "source": source,
            "description": description,
            "status": "recorded",
            "policy": "Fix app/workflow first when the gap blocks reusable paper progress.",
        }
        append_jsonl(root / "PROVENANCE" / "app_workflow_gaps.jsonl", record)
        state = read_json(root / "PUBLIC" / "research_state.json", self._default_research_state())
        workflow = state.get("submission_workflow", DEFAULT_SUBMISSION_WORKFLOW)
        gaps = list(workflow.get("workflow_gaps", []))
        gaps.append(record)
        workflow["workflow_gaps"] = gaps[-20:]
        state["submission_workflow"] = workflow
        state["updated_at"] = now_iso()
        write_json(root / "PUBLIC" / "research_state.json", state)
        return record

    def _sync_project_phase(self, macro_phase: str, internal_phase: str) -> None:
        if not self._project_update:
            return
        self._project_update({"current_macro_phase": macro_phase, "current_phase": internal_phase})

    def _material_manifest_summary(self, root) -> dict[str, Any] | None:
        return read_json(root / "PUBLIC" / "material_manifest_summary.json", None)

    def _validate_public_text(self, text: str, label: str) -> None:
        if SECRET_RE.search(text):
            raise SecurityError(f"Secret-like content detected in {label}.")
        if CONTROL_CHAR_RE.search(text):
            raise SecurityError(f"Control character detected in {label}.")

    def _research_plan_acceptance_prompt(self) -> dict[str, Any]:
        return {
            "prompt_id": "CP-RESEARCH-PLAN-ACCEPTANCE",
            "stage": "loop_acceptance_gate",
            "question": "Do you accept the current research plan and enter the semi-automated research loop?",
            "recommended_option": "accept_with_audit",
            "why_recommended": "The plan is based on the full material bundle, but a theoretical paper still needs source verification, proof audit, and rebuttal-style review records.",
            "options": [
                {
                    "id": "accept_with_audit",
                    "label": "Accept and enter research loop",
                    "description": "Use this plan as the baseline and run source verification, proof audit, and novelty positioning next.",
                    "is_recommended": True,
                },
                {
                    "id": "revise_plan",
                    "label": "Revise the plan first",
                    "description": "Point out missing sections or goal drift and stay at the acceptance gate until revision is complete.",
                },
                {
                    "id": "expand_materials",
                    "label": "Add more materials first",
                    "description": "Import more drafts, notes, templates, example papers, or data before regenerating the plan.",
                },
            ],
            "free_form_enabled": True,
            "free_form_label": "Natural-language additions",
            "free_form_placeholder": "Add acceptance notes, revision requests, or next-loop priorities.",
            "requires_human_response": True,
        }

    def _research_loop_alignment_prompt(self) -> dict[str, Any]:
        return {
            "prompt_id": "CP-FIRST-RESEARCH-LOOP",
            "stage": "loop_plan_alignment",
            "question": "What should the first accepted research loop execute?",
            "recommended_option": "source_proof_novelty",
            "why_recommended": "The project is a theoretical submission, so the first loop should jointly verify sources, audit proof obligations, and position novelty before rewriting the paper.",
            "options": [
                {
                    "id": "source_proof_novelty",
                    "label": "Source, proof, and novelty audit",
                    "description": "Verify venue/source facts, audit the proof route, and map related-work differences before final writing.",
                    "is_recommended": True,
                },
                {
                    "id": "proof_first",
                    "label": "Proof audit first",
                    "description": "Focus on definitions, assumptions, construction validity, and possible counterexamples.",
                },
                {
                    "id": "source_first",
                    "label": "Source verification first",
                    "description": "Build the venue and citation verification table before proof or writing changes.",
                },
            ],
            "free_form_enabled": True,
            "free_form_label": "Natural-language additions",
            "free_form_placeholder": "Add first-loop priorities, constraints, or sources that must be checked.",
            "requires_human_response": True,
        }

    def _research_loop_artifact_acceptance_prompt(self) -> dict[str, Any]:
        return {
            "prompt_id": "CP-RESEARCH-LOOP-ARTIFACT-ACCEPTANCE",
            "stage": "loop_acceptance_gate",
            "question": "Do you accept the current research-loop audit artifacts?",
            "recommended_option": "accept_and_plan_next",
            "why_recommended": "Accepted audit artifacts can govern the next loop or final paper entry.",
            "options": [
                {
                    "id": "accept_and_plan_next",
                    "label": "Accept and plan next",
                    "description": "Use the current source, proof, novelty, and claim-evidence records as accepted loop outputs.",
                    "is_recommended": True,
                },
                {
                    "id": "revise_artifacts",
                    "label": "Revise artifacts first",
                    "description": "Repair missing checks and stay at the acceptance gate.",
                },
                {
                    "id": "expand_audit_scope",
                    "label": "Expand audit scope",
                    "description": "Add more sources, proof obligations, or reviewer-style checks before accepting.",
                },
            ],
            "free_form_enabled": True,
            "free_form_label": "Natural-language additions",
            "free_form_placeholder": "Add acceptance notes, missing checks, or next-loop priorities.",
            "requires_human_response": True,
        }

    def _next_research_loop_prompt(self, workflow: dict[str, Any] | None = None) -> dict[str, Any]:
        blocking = self._workflow_has_blocking_status(workflow or {})
        recommended = "repair_blocking_gaps" if blocking else "enter_final_product_after_audit"
        return {
            "prompt_id": "CP-NEXT-RESEARCH-LOOP",
            "stage": "loop_plan_alignment",
            "question": "What should Research OS do after the accepted audit artifacts?",
            "recommended_option": recommended,
            "why_recommended": (
                "The accepted audit still contains blocking or partial items, so the next loop should repair them before final-paper production."
                if blocking
                else "The accepted audit has no blocking items, so the next appropriate action is to select the paper final-product track and produce submission files through controlled sidecar routes."
            ),
            "options": [
                {
                    "id": "repair_blocking_gaps",
                    "label": "Repair blocking gaps",
                    "description": "Stay in the research loop to fix unresolved source, proof, novelty, or claim-evidence issues.",
                    "is_recommended": blocking,
                },
                {
                    "id": "run_rebuttal_loop",
                    "label": "Run rebuttal-style review",
                    "description": "Ask Codex or an external reviewer to attack novelty, proof rigor, venue fit, and clarity before writing.",
                },
                {
                    "id": "enter_final_product_after_audit",
                    "label": "Enter final paper production",
                    "description": "Open final-product selection with the accepted audit artifacts as constraints.",
                    "is_recommended": not blocking,
                },
                {
                    "id": "extend_source_audit",
                    "label": "Extend source audit",
                    "description": "Verify more references or replace weak citations before final writing.",
                },
            ],
            "free_form_enabled": True,
            "free_form_label": "Natural-language additions",
            "free_form_placeholder": "Add the exact next-loop target, budget, reviewer role, or final-paper constraints.",
            "requires_human_response": True,
        }

    def _workflow_has_blocking_status(self, workflow: dict[str, Any]) -> bool:
        blocking_markers = ("need", "partial", "unverified", "unsupported", "failed", "risk", "revision")
        for key in ("venue_requirements", "source_verification", "proof_audit", "claim_evidence", "novelty_positioning"):
            items = workflow.get(key) if isinstance(workflow, dict) else None
            if not isinstance(items, list):
                continue
            for item in items:
                if not isinstance(item, dict):
                    continue
                status = str(item.get("status") or "").lower()
                if any(marker in status for marker in blocking_markers):
                    return True
        return False

    def _default_research_state(self) -> dict[str, Any]:
        return {
            "schema_version": "research-state-v1",
            "macro_phase": "initialization",
            "internal_phase": "initialization_intake",
            "status": "ready_for_intake",
            "pending_user_confirmation": False,
            "choice_prompts": DEFAULT_CHOICE_PROMPTS,
            "submission_workflow": DEFAULT_SUBMISSION_WORKFLOW,
        }

