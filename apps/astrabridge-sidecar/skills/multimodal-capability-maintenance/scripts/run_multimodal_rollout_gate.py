from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _bootstrap() -> Path:
    sidecar_root = Path(__file__).resolve().parents[3]
    if str(sidecar_root) not in sys.path:
        sys.path.insert(0, str(sidecar_root))
    return sidecar_root.parents[1]


REPO_ROOT = _bootstrap()

from astrabridge_sidecar.provider_capability_verification_gate import (  # noqa: E402
    run_provider_capability_verification_gate,
)
from astrabridge_sidecar.agentic_updates import (  # noqa: E402
    ensure_agentic_update_run_layout,
    normalize_update_scope_contract,
    rollback_manifest_template,
    validate_rollback_manifest,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the multimodal rollout gate.")
    parser.add_argument("--workspace-root", default=str(REPO_ROOT))
    parser.add_argument("--artifact-root", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--scope", action="append", default=[])
    parser.add_argument("--provider", action="append", default=[])
    parser.add_argument("--model", action="append", default=[])
    parser.add_argument("--model-family", action="append", default=[])
    parser.add_argument(
        "--version-policy",
        choices=("pinned", "stable", "latest", "deprecated_check", "security_fix_only"),
        default="stable",
    )
    parser.add_argument("--target-version", default=None)
    parser.add_argument(
        "--apply-mode",
        choices=("discover_only", "proposal_only", "isolated_apply", "verify_candidate", "promote_after_smoke"),
        default="proposal_only",
    )
    parser.add_argument("--baseline-path", default=None)
    parser.add_argument("--skip-tests", action="store_true")
    parser.add_argument("--require-matrix-summary", default=None)
    parser.add_argument("--require-live-smoke-summary", default=None)
    parser.add_argument("--allow-nonpass-lane", action="append", default=[])
    return parser.parse_args()


def _normalize_string_list(values: list[str] | None) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for item in list(values or []):
        text = str(item or "").strip()
        if not text or text in seen:
            continue
        normalized.append(text)
        seen.add(text)
    return normalized


def _build_run_contract(args: argparse.Namespace) -> dict[str, Any]:
    scope = _normalize_string_list(list(args.scope or [])) or ["provider_metadata", "capability_routes"]
    payload = {
        "scope": scope,
        "providers": _normalize_string_list(list(args.provider or [])),
        "models": _normalize_string_list(list(args.model or [])),
        "version_policy": str(args.version_policy or "stable"),
        "target_version": str(args.target_version).strip() if args.target_version else None,
        "apply_mode": str(args.apply_mode or "proposal_only"),
        "allow_network": True,
        "allow_provider_calls": bool(args.require_live_smoke_summary),
        "allow_install": False,
        "allow_code_changes": False,
        "approval_policy": "manual_review_required",
    }
    return normalize_update_scope_contract(payload)


def _evaluate_matrix(summary_path: Path) -> dict[str, Any]:
    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    dry_run = dict(payload.get("dry_run_summary") or {})
    summary_json = Path(str(dry_run.get("summary_json") or "")).resolve()
    matrix_json = Path(str(dry_run.get("matrix_json") or "")).resolve()
    offenders: list[dict[str, Any]] = []
    if payload.get("schema_version") != "astrabridge-multimodal-matrix-reconcile-v1":
        offenders.append({"reason": "unexpected_matrix_reconcile_schema"})
    if not summary_json.exists():
        offenders.append({"reason": "missing_dry_run_summary_json", "path": str(summary_json)})
    if not matrix_json.exists():
        offenders.append({"reason": "missing_dry_run_matrix_json", "path": str(matrix_json)})
    return {
        "status": "pass" if not offenders else "fail",
        "summary_path": str(summary_path.resolve()),
        "dry_run_summary_json": str(summary_json),
        "dry_run_matrix_json": str(matrix_json),
        "provider_ids": list(payload.get("provider_ids") or []),
        "offenders": offenders,
    }


def _evaluate_live_smoke(summary_path: Path, allowed_lanes: set[str]) -> dict:
    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    offenders = []
    for lane in list(payload.get("lane_index") or []):
        lane_id = str(lane.get("lane_id") or "")
        status = str(lane.get("status") or "")
        if status == "pass":
            continue
        if lane_id in allowed_lanes:
            continue
        offenders.append(
            {
                "lane_id": lane_id,
                "status": status,
                "reasons": list(lane.get("reasons") or []),
            }
        )
    return {
        "status": "pass" if not offenders else "fail",
        "summary_path": str(summary_path.resolve()),
        "provider_smoke_summary_json": payload.get("provider_smoke_summary_json"),
        "offenders": offenders,
    }


def _rollout_decision(*, run_contract: dict[str, Any], gate_status: str, matrix_status: str | None, live_smoke_status: str | None) -> dict[str, Any]:
    if gate_status != "pass":
        return {
            "status": "blocked",
            "reason": "verification_gate_failed",
            "promotion_ready": False,
            "exposure_change_allowed": False,
        }
    if matrix_status and matrix_status != "pass":
        return {
            "status": "blocked",
            "reason": "matrix_reconcile_missing_or_failed",
            "promotion_ready": False,
            "exposure_change_allowed": False,
        }
    if live_smoke_status and live_smoke_status != "pass":
        return {
            "status": "blocked",
            "reason": "required_live_smoke_failed",
            "promotion_ready": False,
            "exposure_change_allowed": False,
        }
    apply_mode = str(run_contract.get("apply_mode") or "proposal_only")
    if apply_mode == "proposal_only":
        return {
            "status": "verify_only",
            "reason": "proposal_only_requires_manual_promotion_decision",
            "promotion_ready": False,
            "exposure_change_allowed": False,
        }
    if apply_mode == "verify_candidate":
        return {
            "status": "candidate_verified",
            "reason": "candidate_verified_manual_review_pending",
            "promotion_ready": True,
            "exposure_change_allowed": False,
        }
    if apply_mode == "promote_after_smoke":
        return {
            "status": "eligible_for_manual_promotion",
            "reason": "all_required_evidence_present_manual_review_required",
            "promotion_ready": True,
            "exposure_change_allowed": True,
        }
    return {
        "status": "blocked",
        "reason": "apply_mode_not_supported_for_rollout_promotion",
        "promotion_ready": False,
        "exposure_change_allowed": False,
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _build_rollback_manifest(
    *,
    workspace_root: Path,
    run_id: str,
    run_contract: dict[str, Any],
    decision_artifact: str,
    linked_evidence_artifact: str,
    summary_artifact: str,
) -> dict[str, Any]:
    manifest = rollback_manifest_template(run_id, run_contract)
    manifest["rollback_targets"]["router_config"].append(
        {
            "target_id": "multimodal-route-exposure",
            "workspace_path": "apps/astrabridge-sidecar/astrabridge_sidecar/capabilities/capability_registry.py",
            "reason": "restore_hidden_or_blocked exposure when verification regresses",
        }
    )
    manifest["rollback_targets"]["generated_catalog_locks"].append(
        {
            "target_id": "multimodal-generated-catalog",
            "workspace_path": "apps/astrabridge-sidecar/astrabridge_sidecar/model_catalog/generated_catalog.py",
            "reason": "revert promoted model visibility or seed metadata changes",
        }
    )
    manifest["rollback_targets"]["metadata_sources"].append(
        {
            "target_id": "multimodal-official-source-pack",
            "workspace_path": "PLAN/MULTIMODAL_PROVIDER_OFFICIAL_SOURCE_PACK.md",
            "reason": "restore prior documented support claims if later evidence downgrades a lane",
        }
    )
    manifest["steps"] = [
        {
            "step_id": "review-rollout-decision",
            "target_kind": "router_config",
            "action": "review_rollout_decision_and_regressed_lanes",
            "status": "ready",
            "evidence_path": decision_artifact,
            "manifest_path": linked_evidence_artifact,
        },
        {
            "step_id": "hide-regressed-runtime-lanes",
            "target_kind": "router_config",
            "action": "restore_hidden_or_blocked_runtime_exposure",
            "status": "planned",
            "workspace_path": "apps/astrabridge-sidecar/astrabridge_sidecar/capabilities/capability_registry.py",
            "evidence_path": summary_artifact,
        },
        {
            "step_id": "revert-promoted-catalog-state",
            "target_kind": "generated_catalog_locks",
            "action": "restore_previous_generated_catalog_or_visibility_flags",
            "status": "planned",
            "workspace_path": "apps/astrabridge-sidecar/astrabridge_sidecar/model_catalog/generated_catalog.py",
            "evidence_path": decision_artifact,
        },
        {
            "step_id": "downgrade-doc-backed-support-claims",
            "target_kind": "metadata_sources",
            "action": "revert_documented_support_from_verified_to_blocked_or_hidden",
            "status": "planned",
            "workspace_path": "PLAN/MULTIMODAL_PROVIDER_OFFICIAL_SOURCE_PACK.md",
            "evidence_path": decision_artifact,
        },
        {
            "step_id": "rerun-rollout-gate-after-rollback",
            "target_kind": "router_config",
            "action": "rerun_multimodal_matrix_and_rollout_gate",
            "status": "planned",
            "evidence_path": linked_evidence_artifact,
        },
    ]
    manifest["evidence_paths"] = [
        "run-contract.json",
        summary_artifact,
        decision_artifact,
        linked_evidence_artifact,
        "rollback/rollback-manifest.json",
    ]
    manifest["warnings"] = [
        "rollback_manifest_preserves_all_existing_evidence",
        "rollout_gate_does_not_apply_runtime_changes_automatically",
        "promotion_still_requires_manual_review_even_after_pass",
    ]
    return validate_rollback_manifest(manifest, workspace_root=workspace_root)


def main() -> None:
    args = _parse_args()
    workspace_root = Path(args.workspace_root).resolve()
    artifact_root = Path(args.artifact_root).resolve()
    artifact_root.mkdir(parents=True, exist_ok=True)
    run_layout = ensure_agentic_update_run_layout(workspace_root, args.run_id)
    run_contract = _build_run_contract(args)
    run_contract_path = Path(run_layout["files"]["run_contract"])
    _write_json(run_contract_path, run_contract)

    matrix_requirement = None
    if args.require_matrix_summary:
        matrix_requirement = _evaluate_matrix(Path(args.require_matrix_summary))
    gate = run_provider_capability_verification_gate(
        workspace_root=workspace_root,
        artifact_root=artifact_root / "verification-gate",
        run_id=f"{args.run_id}-verification-gate",
        baseline_path=args.baseline_path,
        include_tests=not args.skip_tests,
    )
    live_smoke = None
    allowed_lanes = {str(item).strip() for item in list(args.allow_nonpass_lane or []) if str(item).strip()}
    if args.require_live_smoke_summary:
        live_smoke = _evaluate_live_smoke(Path(args.require_live_smoke_summary), allowed_lanes)
    decision = _rollout_decision(
        run_contract=run_contract,
        gate_status=str(gate.get("status") or ""),
        matrix_status=str(matrix_requirement.get("status") or "") if matrix_requirement else None,
        live_smoke_status=str(live_smoke.get("status") or "") if live_smoke else None,
    )
    overall_status = "pass" if decision["status"] in {"verify_only", "candidate_verified", "eligible_for_manual_promotion"} else "fail"
    linked_evidence = {
        "schema_version": "astrabridge-multimodal-rollout-linked-evidence-v1",
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(),
        "run_id": args.run_id,
        "paths": {
            "verification_gate_summary_json": gate.get("artifact_paths", {}).get("summary_json"),
            "verification_gate_report_md": gate.get("artifact_paths", {}).get("report_md"),
            "matrix_summary_json": str(Path(args.require_matrix_summary).resolve()) if args.require_matrix_summary else None,
            "live_smoke_summary_json": str(Path(args.require_live_smoke_summary).resolve()) if args.require_live_smoke_summary else None,
            "live_provider_smoke_summary_json": live_smoke.get("provider_smoke_summary_json") if live_smoke else None,
        },
    }
    linked_evidence_path = Path(run_layout["subdirectories"]["rollback"]) / "linked-evidence.json"
    _write_json(linked_evidence_path, linked_evidence)
    decision_payload = {
        "schema_version": "astrabridge-multimodal-rollout-decision-v1",
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(),
        "run_id": args.run_id,
        "status": decision["status"],
        "reason": decision["reason"],
        "promotion_ready": decision["promotion_ready"],
        "exposure_change_allowed": decision["exposure_change_allowed"],
        "run_contract": run_contract,
        "scope_filters": {
            "model_families": _normalize_string_list(list(args.model_family or [])),
        },
        "default_safe_behavior": {
            "manual_review_required": True,
            "exposure_change_without_passed_gate": False,
            "evidence_deletion_allowed": False,
        },
        "verification_gate": {
            "status": gate.get("status"),
            "summary_json": gate.get("artifact_paths", {}).get("summary_json"),
            "report_md": gate.get("artifact_paths", {}).get("report_md"),
        },
        "matrix_requirement": matrix_requirement,
        "live_smoke_requirement": live_smoke,
        "allowed_nonpass_lanes": sorted(allowed_lanes),
        "linked_evidence_json": str(linked_evidence_path),
    }
    decision_path = Path(run_layout["subdirectories"]["rollback"]) / "multimodal-rollout-decision.json"
    _write_json(decision_path, decision_payload)
    rollback_manifest = _build_rollback_manifest(
        workspace_root=workspace_root,
        run_id=args.run_id,
        run_contract=run_contract,
        summary_artifact="rollback/rollout-gate-summary.json",
        decision_artifact="rollback/multimodal-rollout-decision.json",
        linked_evidence_artifact="rollback/linked-evidence.json",
    )
    rollback_manifest_path = Path(run_layout["files"]["rollback_manifest"])
    _write_json(rollback_manifest_path, rollback_manifest)
    summary = {
        "schema_version": "astrabridge-multimodal-rollout-gate-v1",
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(),
        "run_id": args.run_id,
        "status": overall_status,
        "run_contract_json": str(run_contract_path),
        "promotion_decision": {
            "status": decision["status"],
            "reason": decision["reason"],
            "promotion_ready": decision["promotion_ready"],
            "exposure_change_allowed": decision["exposure_change_allowed"],
        },
        "matrix_requirement": matrix_requirement,
        "verification_gate": {
            "status": gate.get("status"),
            "summary_json": gate.get("artifact_paths", {}).get("summary_json"),
            "report_md": gate.get("artifact_paths", {}).get("report_md"),
        },
        "live_smoke_requirement": live_smoke,
        "allowed_nonpass_lanes": sorted(allowed_lanes),
        "decision_json": str(decision_path),
        "rollback_manifest_json": str(rollback_manifest_path),
    }
    summary_path = artifact_root / "summary.json"
    report_path = artifact_root / "report.md"
    _write_json(summary_path, summary)
    _write_json(Path(run_layout["subdirectories"]["rollback"]) / "rollout-gate-summary.json", summary)
    lines = [
        "# Multimodal Rollout Gate",
        "",
        f"- Run ID: `{args.run_id}`",
        f"- Status: `{overall_status}`",
        f"- Scope: `{json.dumps(run_contract.get('scope') or [], ensure_ascii=False)}`",
        f"- Providers: `{json.dumps(run_contract.get('providers') or [], ensure_ascii=False)}`",
        f"- Models: `{json.dumps(run_contract.get('models') or [], ensure_ascii=False)}`",
        f"- Model families: `{json.dumps(_normalize_string_list(list(args.model_family or [])), ensure_ascii=False)}`",
        f"- Version policy: `{run_contract.get('version_policy')}`",
        f"- Apply mode: `{run_contract.get('apply_mode')}`",
        f"- Verification gate: `{gate.get('status')}`",
        f"- Verification summary: `{gate.get('artifact_paths', {}).get('summary_json')}`",
        f"- Promotion decision: `{decision['status']}` (`{decision['reason']}`)",
        f"- Rollback manifest: `{rollback_manifest_path}`",
    ]
    if matrix_requirement:
        lines.extend(
            [
                f"- Matrix requirement: `{matrix_requirement.get('status')}`",
                f"- Matrix summary: `{matrix_requirement.get('summary_path')}`",
            ]
        )
    if live_smoke:
        lines.extend(
            [
                f"- Live smoke requirement: `{live_smoke.get('status')}`",
                f"- Live smoke summary: `{live_smoke.get('summary_path')}`",
                f"- Allowed non-pass lanes: `{json.dumps(sorted(allowed_lanes), ensure_ascii=False)}`",
            ]
        )
        if live_smoke.get("offenders"):
            lines.extend(["", "## Blocking Live Smoke Lanes", ""])
            for item in list(live_smoke.get("offenders") or []):
                lines.append(
                    f"- `{item.get('lane_id')}` status=`{item.get('status')}` reasons=`{json.dumps(item.get('reasons') or [], ensure_ascii=False)}`"
                )
    if matrix_requirement and matrix_requirement.get("offenders"):
        lines.extend(["", "## Blocking Matrix Evidence", ""])
        for item in list(matrix_requirement.get("offenders") or []):
            lines.append(f"- `{json.dumps(item, ensure_ascii=False)}`")
    report_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    print(str(summary_path))


if __name__ == "__main__":
    main()
