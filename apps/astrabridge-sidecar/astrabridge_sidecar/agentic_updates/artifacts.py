from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import re
from typing import Any

from ..common import now_iso
from ..security import SecurityError, resolve_under
from .contracts import assert_secret_free_agentic_update_payload, normalize_update_scope_contract


AGENTIC_UPDATE_ARTIFACT_CONTRACT_SCHEMA_VERSION = "astrabridge-agentic-update-artifact-contract-v1"
AGENTIC_UPDATE_RUN_LAYOUT_SCHEMA_VERSION = "astrabridge-agentic-update-run-layout-v1"
AGENTIC_UPDATE_ROLLBACK_MANIFEST_SCHEMA_VERSION = "astrabridge-agentic-update-rollback-manifest-v1"

AGENTIC_UPDATE_PRIVATE_ROOT = Path("PRIVATE") / "agentic-update-pipeline"
AGENTIC_UPDATE_RUNS_ROOT = AGENTIC_UPDATE_PRIVATE_ROOT / "runs"
RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")

RUN_SUBDIRECTORIES = (
    "sources",
    "parsed",
    "proposals",
    "diffs",
    "validation",
    "route-promotion",
    "screenshots",
    "apply",
    "rollback",
    "secret-scan",
    "logs",
    "tmp",
)
RUN_FILE_RELATIVE_PATHS = {
    "run_contract": "run-contract.json",
    "summary": "summary.json",
    "source_index": "sources/source-index.json",
    "source_pack": "sources/source-pack.jsonl",
    "parser_output": "parsed/parser-output.json",
    "proposal": "proposals/proposal.json",
    "proposal_diff": "diffs/proposal-diff.json",
    "validation_report": "validation/validation-report.json",
    "validation_markdown": "validation/validation-report.md",
    "route_promotion_proposal": "route-promotion/route-promotion-proposal.json",
    "route_promotion_validation": "route-promotion/route-promotion-validation.json",
    "route_promotion_apply_ledger": "route-promotion/route-promotion-apply-ledger.json",
    "route_promotion_rollback": "route-promotion/route-promotion-rollback.json",
    "screenshot_index": "screenshots/screenshot-index.json",
    "apply_journal": "apply/apply-journal.json",
    "apply_manifest": "apply/apply-manifest.json",
    "rollback_manifest": "rollback/rollback-manifest.json",
    "secret_scan": "secret-scan/secret-scan-report.json",
    "events": "logs/events.jsonl",
}
ROLLBACK_TARGET_KINDS = (
    "router_config",
    "execution_routes",
    "metadata_sources",
    "generated_catalog_locks",
    "changed_source_files",
    "ui_changes",
    "codex_binary_locator_state",
)
ROLLBACK_STEP_STATUSES = ("planned", "ready", "applied", "skipped", "blocked", "failed")
RUN_ARTIFACT_PATH_FIELDS = ("artifact_path", "backup_path", "evidence_path", "manifest_path")
WORKSPACE_PATH_FIELDS = ("workspace_path", "changed_path", "restore_path", "source_path")


def agentic_update_artifact_contract() -> dict[str, Any]:
    return {
        "schema_version": AGENTIC_UPDATE_ARTIFACT_CONTRACT_SCHEMA_VERSION,
        "generated_at": now_iso(),
        "root_relative": AGENTIC_UPDATE_PRIVATE_ROOT.as_posix(),
        "runs_root_relative": AGENTIC_UPDATE_RUNS_ROOT.as_posix(),
        "run_root_pattern": f"{AGENTIC_UPDATE_RUNS_ROOT.as_posix()}/<run_id>",
        "run_id_rules": {
            "pattern": RUN_ID_PATTERN.pattern,
            "max_length": 128,
            "path_separators_allowed": False,
            "dot_dot_allowed": False,
        },
        "subdirectories": list(RUN_SUBDIRECTORIES),
        "files": dict(RUN_FILE_RELATIVE_PATHS),
        "naming_rules": {
            "fetched_docs": "sources/<source_id>.<ext> with source-index.json as the authority",
            "parser_outputs": "parsed/<provider_id>-<parser_id>.json",
            "proposal_diffs": "diffs/proposal-diff.json plus optional diffs/<change_id>.diff",
            "validation_reports": "validation/validation-report.json and validation/validation-report.md",
            "screenshots": "screenshots/<view_id>.png with screenshot-index.json as the authority",
            "secret_scan_reports": "secret-scan/secret-scan-report.json",
            "rollback": "rollback/rollback-manifest.json plus rollback/backups/<target_id>/ when needed",
        },
        "preservation_policy": {
            "delete_existing_evidence": False,
            "cleanup_required_before_new_run": False,
            "directory_initialization": "mkdir_only",
            "overwrite_existing_artifacts_by_default": False,
        },
        "rollback_target_kinds": list(ROLLBACK_TARGET_KINDS),
    }


def normalize_agentic_update_run_id(run_id: str) -> str:
    if not isinstance(run_id, str):
        raise TypeError("Agentic update run_id must be a string.")
    text = run_id.strip()
    if not text:
        raise ValueError("Agentic update run_id must not be empty.")
    if "/" in text or "\\" in text or ".." in text or not RUN_ID_PATTERN.match(text):
        raise SecurityError(f"Invalid agentic update run_id: {run_id}")
    return text


def agentic_update_private_root(workspace_root: str | Path) -> Path:
    return resolve_under(Path(workspace_root).resolve(), AGENTIC_UPDATE_PRIVATE_ROOT)


def agentic_update_runs_root(workspace_root: str | Path) -> Path:
    return resolve_under(Path(workspace_root).resolve(), AGENTIC_UPDATE_RUNS_ROOT)


def agentic_update_run_root(workspace_root: str | Path, run_id: str) -> Path:
    safe_run_id = normalize_agentic_update_run_id(run_id)
    return resolve_under(Path(workspace_root).resolve(), AGENTIC_UPDATE_RUNS_ROOT / safe_run_id)


def validate_agentic_update_artifact_path(workspace_root: str | Path, run_id: str, relative_path: str | Path) -> Path:
    if isinstance(relative_path, Path):
        candidate = relative_path
    elif isinstance(relative_path, str):
        candidate = Path(relative_path)
    else:
        raise TypeError("Agentic update artifact path must be a string or Path.")
    if candidate.is_absolute():
        raise SecurityError(f"Agentic update artifact paths must be run-relative: {relative_path}")
    if not candidate.parts or any(part in {"", ".", ".."} for part in candidate.parts):
        raise SecurityError(f"Invalid agentic update artifact relative path: {relative_path}")
    run_root = agentic_update_run_root(workspace_root, run_id)
    return resolve_under(run_root, candidate)


def agentic_update_run_layout(workspace_root: str | Path, run_id: str) -> dict[str, Any]:
    workspace = Path(workspace_root).resolve()
    safe_run_id = normalize_agentic_update_run_id(run_id)
    private_root = agentic_update_private_root(workspace)
    runs_root = agentic_update_runs_root(workspace)
    run_root = agentic_update_run_root(workspace, safe_run_id)
    subdirectories = {name: str(resolve_under(run_root, name)) for name in RUN_SUBDIRECTORIES}
    files = {
        name: str(validate_agentic_update_artifact_path(workspace, safe_run_id, relative_path))
        for name, relative_path in RUN_FILE_RELATIVE_PATHS.items()
    }
    layout = {
        "schema_version": AGENTIC_UPDATE_RUN_LAYOUT_SCHEMA_VERSION,
        "generated_at": now_iso(),
        "workspace_root": str(workspace),
        "run_id": safe_run_id,
        "private_root": str(private_root),
        "runs_root": str(runs_root),
        "run_root": str(run_root),
        "run_root_relative": (AGENTIC_UPDATE_RUNS_ROOT / safe_run_id).as_posix(),
        "subdirectories": subdirectories,
        "files": files,
        "file_relative_paths": dict(RUN_FILE_RELATIVE_PATHS),
        "preservation_policy": deepcopy(agentic_update_artifact_contract()["preservation_policy"]),
    }
    assert_secret_free_agentic_update_payload(layout, label="agentic_update_run_layout")
    return layout


def ensure_agentic_update_run_layout(workspace_root: str | Path, run_id: str) -> dict[str, Any]:
    layout = agentic_update_run_layout(workspace_root, run_id)
    Path(layout["run_root"]).mkdir(parents=True, exist_ok=True)
    for path in layout["subdirectories"].values():
        Path(path).mkdir(parents=True, exist_ok=True)
    return layout


def rollback_manifest_template(
    run_id: str,
    run_contract: dict[str, Any],
    *,
    created_at: str | None = None,
) -> dict[str, Any]:
    safe_run_id = normalize_agentic_update_run_id(run_id)
    contract = normalize_update_scope_contract(run_contract)
    now = created_at or now_iso()
    manifest = {
        "schema_version": AGENTIC_UPDATE_ROLLBACK_MANIFEST_SCHEMA_VERSION,
        "created_at": now,
        "run_id": safe_run_id,
        "run_contract": contract,
        "reversible": True,
        "preservation_policy": {
            "delete_existing_evidence": False,
            "cleanup_required_before_rollback": False,
            "preserve_failed_apply_artifacts": True,
            "overwrite_without_backup": False,
        },
        "rollback_targets": {kind: [] for kind in ROLLBACK_TARGET_KINDS},
        "steps": [],
        "evidence_paths": [],
        "warnings": [],
    }
    return validate_rollback_manifest(manifest)


def validate_rollback_manifest(
    manifest: dict[str, Any],
    *,
    workspace_root: str | Path | None = None,
) -> dict[str, Any]:
    if not isinstance(manifest, dict):
        raise TypeError("Agentic update rollback manifest must be a dict.")
    assert_secret_free_agentic_update_payload(manifest, label="agentic_update_rollback_manifest")
    if manifest.get("schema_version") != AGENTIC_UPDATE_ROLLBACK_MANIFEST_SCHEMA_VERSION:
        raise ValueError("Unexpected agentic update rollback manifest schema version.")
    for field in (
        "created_at",
        "run_id",
        "run_contract",
        "reversible",
        "preservation_policy",
        "rollback_targets",
        "steps",
        "evidence_paths",
    ):
        if field not in manifest:
            raise ValueError(f"Agentic update rollback manifest is missing required field: {field}")

    normalized = deepcopy(manifest)
    normalized["run_id"] = normalize_agentic_update_run_id(str(manifest["run_id"]))
    normalized["run_contract"] = normalize_update_scope_contract(dict(manifest["run_contract"]))
    if not isinstance(normalized["reversible"], bool):
        raise ValueError("rollback_manifest.reversible must be a bool.")
    _validate_preservation_policy(normalized["preservation_policy"])
    _validate_rollback_targets(normalized["rollback_targets"])
    _validate_rollback_steps(normalized["steps"])
    if not isinstance(normalized["evidence_paths"], list):
        raise ValueError("rollback_manifest.evidence_paths must be a list.")
    if workspace_root is not None:
        _validate_rollback_manifest_paths(normalized, workspace_root=Path(workspace_root).resolve())
    assert_secret_free_agentic_update_payload(normalized, label="agentic_update_rollback_manifest")
    return normalized


def _validate_preservation_policy(policy: Any) -> None:
    if not isinstance(policy, dict):
        raise ValueError("rollback_manifest.preservation_policy must be a dict.")
    if policy.get("delete_existing_evidence") is not False:
        raise ValueError("rollback_manifest.preservation_policy.delete_existing_evidence must be false.")
    if policy.get("overwrite_without_backup") is not False:
        raise ValueError("rollback_manifest.preservation_policy.overwrite_without_backup must be false.")


def _validate_rollback_targets(targets: Any) -> None:
    if not isinstance(targets, dict):
        raise ValueError("rollback_manifest.rollback_targets must be a dict.")
    missing = [kind for kind in ROLLBACK_TARGET_KINDS if kind not in targets]
    if missing:
        raise ValueError(f"rollback_manifest.rollback_targets is missing target kinds: {', '.join(missing)}")
    for kind, records in targets.items():
        if kind not in ROLLBACK_TARGET_KINDS:
            raise ValueError(f"rollback_manifest.rollback_targets has unsupported target kind: {kind}")
        if not isinstance(records, list):
            raise ValueError(f"rollback_manifest.rollback_targets.{kind} must be a list.")


def _validate_rollback_steps(steps: Any) -> None:
    if not isinstance(steps, list):
        raise ValueError("rollback_manifest.steps must be a list.")
    for index, step in enumerate(steps):
        if not isinstance(step, dict):
            raise ValueError(f"rollback_manifest.steps[{index}] must be a dict.")
        for field in ("step_id", "target_kind", "action", "status"):
            if field not in step:
                raise ValueError(f"rollback_manifest.steps[{index}] is missing required field: {field}")
        if step["target_kind"] not in ROLLBACK_TARGET_KINDS:
            raise ValueError(f"rollback_manifest.steps[{index}].target_kind is invalid.")
        if step["status"] not in ROLLBACK_STEP_STATUSES:
            raise ValueError(f"rollback_manifest.steps[{index}].status is invalid.")


def _validate_rollback_manifest_paths(manifest: dict[str, Any], *, workspace_root: Path) -> None:
    run_id = manifest["run_id"]
    for path in manifest["evidence_paths"]:
        validate_agentic_update_artifact_path(workspace_root, run_id, path)
    for step in manifest["steps"]:
        for field in RUN_ARTIFACT_PATH_FIELDS:
            if field in step and step[field] not in (None, ""):
                validate_agentic_update_artifact_path(workspace_root, run_id, step[field])
        for field in WORKSPACE_PATH_FIELDS:
            if field in step and step[field] not in (None, ""):
                _validate_workspace_relative_path(workspace_root, step[field])
    for records in manifest["rollback_targets"].values():
        for record in records:
            if not isinstance(record, dict):
                raise ValueError("rollback_manifest.rollback_targets entries must be dicts.")
            for field in RUN_ARTIFACT_PATH_FIELDS:
                if field in record and record[field] not in (None, ""):
                    validate_agentic_update_artifact_path(workspace_root, run_id, record[field])
            for field in WORKSPACE_PATH_FIELDS:
                if field in record and record[field] not in (None, ""):
                    _validate_workspace_relative_path(workspace_root, record[field])


def _validate_workspace_relative_path(workspace_root: Path, relative_path: Any) -> Path:
    if not isinstance(relative_path, str):
        raise TypeError("Workspace rollback paths must be strings.")
    candidate = Path(relative_path)
    if candidate.is_absolute():
        raise SecurityError(f"Workspace rollback paths must be workspace-relative: {relative_path}")
    if not candidate.parts or any(part in {"", ".", ".."} for part in candidate.parts):
        raise SecurityError(f"Invalid workspace rollback relative path: {relative_path}")
    return resolve_under(workspace_root, candidate)
