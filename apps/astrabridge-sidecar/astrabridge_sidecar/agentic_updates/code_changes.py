from __future__ import annotations

from pathlib import Path
import re
import subprocess
from typing import Any

from ..common import new_id, now_iso, write_json
from ..security import SecurityError, resolve_under
from .apply import AGENTIC_UPDATE_APPLY_MANIFEST_SCHEMA_VERSION
from .artifacts import (
    ensure_agentic_update_run_layout,
    rollback_manifest_template,
    validate_agentic_update_artifact_path,
    validate_rollback_manifest,
)
from .contracts import assert_secret_free_agentic_update_payload, validate_update_proposal


AGENTIC_UPDATE_CODE_CHANGE_TASK_BRIEF_FILENAME = "apply/code-change-task-brief.md"
CODE_CHANGE_BOUNDARY_MODES = {"dedicated_worktree", "current_workspace"}
CODE_CHANGE_SUPPORTED_RISK_CLASSES = {"requires_adapter_review"}
_SAFE_BRANCH_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,180}$")


def plan_code_change_worktree_boundary(
    *,
    workspace_root: str | Path,
    run_id: str,
    proposal: dict[str, Any],
    approval: dict[str, Any],
    boundary: dict[str, Any] | None = None,
    runtime_root: str | Path | None = None,
) -> dict[str, Any]:
    workspace = Path(workspace_root).resolve()
    layout = ensure_agentic_update_run_layout(workspace, run_id)
    validated_proposal = validate_update_proposal(proposal)
    _validate_manual_approval(approval)
    _validate_code_change_proposal(validated_proposal)

    spec = _normalize_boundary_spec(
        workspace=workspace,
        run_id=run_id,
        value=boundary or {},
        runtime_root=runtime_root,
    )
    apply_id = new_id("code-change-plan")
    repo_root = _git_repo_root(workspace) if not spec["dry_run"] or spec["mode"] == "dedicated_worktree" else workspace
    if repo_root is None:
        repo_root = workspace
    git_execution = _maybe_prepare_git_boundary(
        repo_root=repo_root,
        worktree_path=Path(spec["worktree_path"]) if spec.get("worktree_path") else None,
        branch_name=str(spec.get("branch_name") or ""),
        base_ref=str(spec.get("base_ref") or "HEAD"),
        dry_run=bool(spec["dry_run"]),
        create_worktree=bool(spec["create_worktree"]),
        use_existing_worktree=bool(spec["use_existing_worktree"]),
        mode=str(spec["mode"]),
    )

    planned_paths = _planned_source_paths(validated_proposal)
    task_brief_path = validate_agentic_update_artifact_path(workspace, run_id, AGENTIC_UPDATE_CODE_CHANGE_TASK_BRIEF_FILENAME)
    task_brief = _render_task_brief(
        proposal=validated_proposal,
        branch_name=str(spec.get("branch_name") or ""),
        worktree_path=str(spec.get("worktree_path") or ""),
        base_ref=str(spec.get("base_ref") or "HEAD"),
        planned_paths=planned_paths,
        git_execution=git_execution,
    )
    task_brief_path.parent.mkdir(parents=True, exist_ok=True)
    task_brief_path.write_text(task_brief, encoding="utf-8")

    rollback_manifest = _build_code_change_rollback_manifest(
        workspace=workspace,
        run_id=run_id,
        proposal=validated_proposal,
        apply_id=apply_id,
        branch_name=str(spec.get("branch_name") or ""),
        worktree_path=str(spec.get("worktree_path") or ""),
        repo_root=str(repo_root),
    )
    rollback_manifest_path = Path(layout["files"]["rollback_manifest"])
    write_json(rollback_manifest_path, rollback_manifest)

    status = "planned_dry_run" if spec["dry_run"] else git_execution["status"]
    manifest = {
        "schema_version": AGENTIC_UPDATE_APPLY_MANIFEST_SCHEMA_VERSION,
        "apply_id": apply_id,
        "run_id": run_id,
        "mode": "code_change_worktree_plan",
        "status": status,
        "planned_at": now_iso(),
        "risk_class": validated_proposal["diff"].get("risk_class"),
        "approval": {
            "approved": True,
            "approved_by": str(approval.get("approved_by") or "").strip(),
            "approved_at": str(approval.get("approved_at") or now_iso()).strip(),
            "approval_note": str(approval.get("approval_note") or "").strip(),
        },
        "boundary": {
            "mode": spec["mode"],
            "dry_run": spec["dry_run"],
            "create_worktree": spec["create_worktree"],
            "use_existing_worktree": spec["use_existing_worktree"],
            "base_ref": spec["base_ref"],
            "branch_name": spec["branch_name"],
            "worktree_path": spec["worktree_path"],
            "repo_root": str(repo_root),
            "allow_main_worktree_mutation": spec["allow_main_worktree_mutation"],
        },
        "git": git_execution,
        "changed_paths": [],
        "planned_changed_paths": planned_paths,
        "touched": {
            "task_brief": str(task_brief_path),
            "apply_manifest": layout["files"]["apply_manifest"],
            "rollback_manifest": str(rollback_manifest_path),
        },
        "task_brief_path": str(task_brief_path),
        "rollback_manifest_path": str(rollback_manifest_path),
        "rollback": {
            "requires_user_approval": True,
            "destructive_commands_executed": False,
            "instructions": [
                "Review worktree diff before rollback.",
                "Remove the dedicated worktree only after explicit user approval.",
                "Delete the branch only after explicit user approval and only when no needed commits remain.",
            ],
        },
        "warnings": _dedupe(
            [
                *list(spec.get("warnings") or []),
                "code_change_plan_does_not_modify_current_workspace",
                "rollback_commands_are_manual_and_require_user_approval",
            ]
        ),
    }
    assert_secret_free_agentic_update_payload(manifest, label="agentic_update_code_change_manifest")
    write_json(Path(layout["files"]["apply_manifest"]), manifest)
    return manifest


def _validate_manual_approval(approval: dict[str, Any] | None) -> None:
    if not isinstance(approval, dict) or approval.get("approved") is not True:
        raise ValueError("Manual approval is required before planning agentic update code changes.")
    if not str(approval.get("approved_by") or "").strip():
        raise ValueError("approval.approved_by is required.")


def _validate_code_change_proposal(proposal: dict[str, Any]) -> None:
    contract = dict(proposal.get("run_contract") or {})
    if not bool(contract.get("allow_code_changes")):
        raise ValueError("Code-change worktree planning requires run_contract.allow_code_changes=true.")
    risk_class = str(dict(proposal.get("diff") or {}).get("risk_class") or "")
    changes = [dict(item) for item in list(dict(proposal.get("diff") or {}).get("changes") or []) if isinstance(item, dict)]
    if risk_class not in CODE_CHANGE_SUPPORTED_RISK_CLASSES and not any(
        str(change.get("risk_class") or "") in CODE_CHANGE_SUPPORTED_RISK_CLASSES for change in changes
    ):
        raise ValueError("Code-change worktree planning is limited to requires_adapter_review proposals.")
    if risk_class == "blocked_manual_review" or any(str(change.get("risk_class") or "") == "blocked_manual_review" for change in changes):
        raise ValueError("Blocked manual review proposals cannot be converted into a code-change worktree plan.")


def _normalize_boundary_spec(
    *,
    workspace: Path,
    run_id: str,
    value: dict[str, Any],
    runtime_root: str | Path | None,
) -> dict[str, Any]:
    mode = str(value.get("mode") or "dedicated_worktree").strip() or "dedicated_worktree"
    if mode not in CODE_CHANGE_BOUNDARY_MODES:
        raise ValueError(f"Unsupported code-change boundary mode: {mode}")
    dry_run = bool(value.get("dry_run", True))
    create_worktree = bool(value.get("create_worktree", False))
    use_existing_worktree = bool(value.get("use_existing_worktree", False))
    allow_main = bool(value.get("allow_main_worktree_mutation", False))
    if mode == "current_workspace" and not allow_main:
        raise ValueError("Direct current-workspace code changes require allow_main_worktree_mutation=true.")
    if mode == "current_workspace" and create_worktree:
        raise ValueError("current_workspace mode cannot create a dedicated worktree.")
    if create_worktree and dry_run:
        create_worktree = False
    branch_name = _safe_branch_name(str(value.get("branch_name") or f"codex/agentic-update/{run_id}"))
    base_ref = _safe_git_ref(str(value.get("base_ref") or "HEAD"), field="base_ref")
    warnings: list[str] = []
    if mode == "current_workspace":
        warnings.append("current_workspace_mode_requires_separate_explicit_apply_approval")
        return {
            "mode": mode,
            "dry_run": dry_run,
            "create_worktree": False,
            "use_existing_worktree": False,
            "base_ref": base_ref,
            "branch_name": branch_name,
            "worktree_path": str(workspace),
            "allow_main_worktree_mutation": allow_main,
            "warnings": warnings,
        }
    worktree_path = _resolve_worktree_path(
        workspace=workspace,
        run_id=run_id,
        configured=value.get("worktree_path"),
        runtime_root=runtime_root,
        dry_run=dry_run,
    )
    return {
        "mode": mode,
        "dry_run": dry_run,
        "create_worktree": create_worktree,
        "use_existing_worktree": use_existing_worktree,
        "base_ref": base_ref,
        "branch_name": branch_name,
        "worktree_path": str(worktree_path),
        "allow_main_worktree_mutation": False,
        "warnings": warnings,
    }


def _resolve_worktree_path(
    *,
    workspace: Path,
    run_id: str,
    configured: Any,
    runtime_root: str | Path | None,
    dry_run: bool,
) -> Path:
    if configured not in (None, ""):
        candidate = Path(str(configured)).expanduser()
        if not candidate.is_absolute():
            if runtime_root is not None:
                return resolve_under(Path(runtime_root).expanduser().resolve(), candidate)
            if not dry_run:
                raise ValueError("runtime_root is required for relative worktree_path when creating a dedicated worktree.")
            return resolve_under(workspace, candidate)
        resolved = candidate.resolve()
        if runtime_root is not None:
            runtime = Path(runtime_root).expanduser().resolve()
            if resolved != runtime and runtime not in resolved.parents:
                raise SecurityError("Configured worktree_path must stay under runtime_root.")
        elif not dry_run:
            raise SecurityError("Absolute worktree_path requires runtime_root for non-dry-run worktree planning.")
        return resolved
    if runtime_root is not None:
        return resolve_under(Path(runtime_root).expanduser().resolve(), Path("agentic-update-worktrees") / run_id)
    if not dry_run:
        raise ValueError("runtime_root is required before creating a dedicated code-change worktree.")
    return validate_agentic_update_artifact_path(workspace, run_id, "tmp/code-change-worktree")


def _maybe_prepare_git_boundary(
    *,
    repo_root: Path,
    worktree_path: Path | None,
    branch_name: str,
    base_ref: str,
    dry_run: bool,
    create_worktree: bool,
    use_existing_worktree: bool,
    mode: str,
) -> dict[str, Any]:
    planned_commands = []
    if mode == "dedicated_worktree" and worktree_path is not None:
        planned_commands.append(["git", "-C", str(repo_root), "worktree", "add", "-b", branch_name, str(worktree_path), base_ref])
    if dry_run:
        return {
            "status": "planned_dry_run",
            "commands_planned": planned_commands,
            "commands_executed": [],
            "worktree_created": False,
            "branch_created": False,
        }
    if mode == "current_workspace":
        return {
            "status": "current_workspace_selected",
            "commands_planned": [],
            "commands_executed": [],
            "worktree_created": False,
            "branch_created": False,
        }
    if not create_worktree:
        return {
            "status": "planned_no_create",
            "commands_planned": planned_commands,
            "commands_executed": [],
            "worktree_created": False,
            "branch_created": False,
        }
    if worktree_path is None:
        raise ValueError("worktree_path is required to create a code-change worktree.")
    if worktree_path.exists() and not use_existing_worktree:
        raise ValueError("worktree_path already exists; set use_existing_worktree=true to use it.")
    if worktree_path.exists() and use_existing_worktree:
        return {
            "status": "existing_worktree_selected",
            "commands_planned": planned_commands,
            "commands_executed": [],
            "worktree_created": False,
            "branch_created": False,
        }
    worktree_path.parent.mkdir(parents=True, exist_ok=True)
    completed = _run_git(repo_root, ["worktree", "add", "-b", branch_name, str(worktree_path), base_ref])
    return {
        "status": "worktree_created",
        "commands_planned": planned_commands,
        "commands_executed": [["git", "-C", str(repo_root), "worktree", "add", "-b", branch_name, str(worktree_path), base_ref]],
        "worktree_created": True,
        "branch_created": True,
        "stdout_excerpt": str(completed.stdout or "").strip()[:500],
        "stderr_excerpt": str(completed.stderr or "").strip()[:500],
    }


def _build_code_change_rollback_manifest(
    *,
    workspace: Path,
    run_id: str,
    proposal: dict[str, Any],
    apply_id: str,
    branch_name: str,
    worktree_path: str,
    repo_root: str,
) -> dict[str, Any]:
    manifest = rollback_manifest_template(run_id, proposal["run_contract"])
    target = {
        "target_id": "code-change-worktree",
        "apply_id": apply_id,
        "branch_name": branch_name,
        "worktree_path": worktree_path,
        "repo_root": repo_root,
        "requires_user_approval": True,
    }
    manifest["rollback_targets"]["changed_source_files"].append(target)
    manifest["steps"].extend(
        [
            {
                "step_id": "review-code-worktree-diff",
                "target_kind": "changed_source_files",
                "action": "manual_review_worktree_diff",
                "status": "planned",
                "requires_user_approval": False,
                "review_commands": [
                    f"git -C {worktree_path} status --short",
                    f"git -C {worktree_path} diff --stat",
                ],
            },
            {
                "step_id": "remove-code-worktree-after-approval",
                "target_kind": "changed_source_files",
                "action": "manual_git_worktree_remove_after_user_approval",
                "status": "planned",
                "requires_user_approval": True,
                "destructive_without_approval": False,
                "manual_command": f"git -C {repo_root} worktree remove {worktree_path}",
            },
            {
                "step_id": "delete-code-branch-after-approval",
                "target_kind": "changed_source_files",
                "action": "manual_git_branch_delete_after_user_approval",
                "status": "planned",
                "requires_user_approval": True,
                "destructive_without_approval": False,
                "manual_command": f"git -C {repo_root} branch -d {branch_name}",
            },
        ]
    )
    manifest["evidence_paths"] = [
        "apply/apply-manifest.json",
        AGENTIC_UPDATE_CODE_CHANGE_TASK_BRIEF_FILENAME,
        "rollback/rollback-manifest.json",
    ]
    manifest["warnings"].extend(
        [
            "rollback_does_not_run_git_commands_automatically",
            "worktree_and_branch_removal_require_user_approval",
        ]
    )
    return validate_rollback_manifest(manifest, workspace_root=workspace)


def _render_task_brief(
    *,
    proposal: dict[str, Any],
    branch_name: str,
    worktree_path: str,
    base_ref: str,
    planned_paths: list[str],
    git_execution: dict[str, Any],
) -> str:
    diff = dict(proposal.get("diff") or {})
    changes = [dict(item) for item in list(diff.get("changes") or []) if isinstance(item, dict)]
    lines = [
        "# Agentic Update Code-Change Task Brief",
        "",
        f"- Run id: `{proposal.get('run_id')}`",
        f"- Risk class: `{diff.get('risk_class')}`",
        f"- Branch: `{branch_name}`",
        f"- Worktree: `{worktree_path}`",
        f"- Base ref: `{base_ref}`",
        f"- Boundary status: `{git_execution.get('status')}`",
        "",
        "## Required Boundary",
        "",
        "- Work only inside the dedicated worktree unless the user explicitly approves current-workspace mutation.",
        "- Do not edit the main worktree for adapter/profile/source-code changes.",
        "- Preserve run artifacts under `PRIVATE/agentic-update-pipeline/`.",
        "- Do not save API keys, bearer tokens, cookies, auth headers, or raw provider secrets.",
        "",
        "## Proposed Changes",
        "",
    ]
    for change in changes:
        lines.append(
            f"- `{change.get('change_type')}` for `{change.get('target') or change.get('model_id')}` "
            f"with risk `{change.get('risk_class')}`; reasons: {', '.join(str(item) for item in change.get('reasons') or []) or 'none'}."
        )
    lines.extend(["", "## Likely Files", ""])
    for path in planned_paths:
        lines.append(f"- `{path}`")
    lines.extend(
        [
            "",
            "## Minimum Validation",
            "",
            "- Run focused provider/profile/transport tests for changed providers.",
            "- Run agentic update contract/diff/service tests before promotion.",
            "- Run a focused secret scan over changed files and generated artifacts.",
            "- Provider-backed smoke requires a separate explicit authorization.",
            "",
            "## Evidence To Preserve",
            "",
            "- Worktree path and branch name in `apply/apply-manifest.json`.",
            "- Diff, test output excerpts, and any smoke reports under the run artifact root.",
            "- Rollback notes in `rollback/rollback-manifest.json`.",
        ]
    )
    text = "\n".join(lines).rstrip() + "\n"
    assert_secret_free_agentic_update_payload(text, label="agentic_update_code_change_task_brief")
    return text


def _planned_source_paths(proposal: dict[str, Any]) -> list[str]:
    providers = _providers_from_proposal(proposal)
    paths = {
        "apps/astrabridge-sidecar/astrabridge_sidecar/providers/profile.py",
        "apps/astrabridge-sidecar/astrabridge_sidecar/providers/registry.py",
        "apps/astrabridge-sidecar/astrabridge_sidecar/model_catalog/catalog.py",
        "apps/astrabridge-sidecar/tests/test_router_transport_registry.py",
        "apps/astrabridge-sidecar/tests/test_agentic_update_diffing.py",
    }
    transport_paths = {
        "qwen": "apps/astrabridge-sidecar/astrabridge_sidecar/providers/transports/qwen_dashscope.py",
        "deepseek": "apps/astrabridge-sidecar/astrabridge_sidecar/providers/transports/deepseek.py",
        "kimi": "apps/astrabridge-sidecar/astrabridge_sidecar/providers/transports/moonshot_kimi.py",
        "moonshot": "apps/astrabridge-sidecar/astrabridge_sidecar/providers/transports/moonshot_kimi.py",
        "glm": "apps/astrabridge-sidecar/astrabridge_sidecar/providers/transports/zai_glm.py",
        "zai": "apps/astrabridge-sidecar/astrabridge_sidecar/providers/transports/zai_glm.py",
    }
    for provider in providers:
        if provider in transport_paths:
            paths.add(transport_paths[provider])
    if not providers or any(provider not in transport_paths for provider in providers):
        paths.add("apps/astrabridge-sidecar/astrabridge_sidecar/providers/transports/")
    return sorted(paths)


def _providers_from_proposal(proposal: dict[str, Any]) -> set[str]:
    providers = {str(item).strip() for item in list(dict(proposal.get("run_contract") or {}).get("providers") or []) if str(item).strip()}
    for change in list(dict(proposal.get("diff") or {}).get("changes") or []):
        if isinstance(change, dict) and str(change.get("provider_id") or "").strip():
            providers.add(str(change.get("provider_id")).strip())
    return {provider.lower() for provider in providers}


def _git_repo_root(workspace: Path) -> Path | None:
    completed = _run_git(workspace, ["rev-parse", "--show-toplevel"], check=False)
    if completed.returncode != 0:
        return None
    text = str(completed.stdout or "").strip()
    return Path(text).resolve() if text else None


def _run_git(cwd: Path, args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        ["git", "-C", str(cwd), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=30,
    )
    if check and completed.returncode != 0:
        message = str(completed.stderr or "").strip() or str(completed.stdout or "").strip() or "git command failed"
        raise ValueError(message[:500])
    return completed


def _safe_branch_name(value: str) -> str:
    text = value.strip().replace("\\", "/")
    if not text or ".." in text or text.startswith("/") or text.endswith("/") or text.endswith(".lock") or not _SAFE_BRANCH_RE.match(text):
        raise SecurityError(f"Invalid branch name for code-change boundary: {value}")
    return text


def _safe_git_ref(value: str, *, field: str) -> str:
    text = value.strip()
    if not text or ".." in text or text.startswith("-") or any(ch.isspace() for ch in text) or not re.match(r"^[A-Za-z0-9._/@-]+$", text):
        raise SecurityError(f"Invalid {field} for code-change boundary: {value}")
    return text


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            result.append(value)
            seen.add(value)
    return result
