from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

from .common import now_iso, slugify, write_json


PROMOTION_GATE_SCHEMA_VERSION = "astrabridge-promotion-gate-v1"
PROMOTION_GATE_MANIFEST_SCHEMA_VERSION = "astrabridge-promotion-gate-manifest-v1"
_PROBLEM_STATUSES = {"skipped", "missing", "unknown", "unevaluated"}
_REPO_ROOT = Path(__file__).resolve().parents[3]
_RUN_LOCAL_GATE = _REPO_ROOT / "scripts" / "run_local_gate.py"
_RUN_RUNTIME_STABILITY_GATE = _REPO_ROOT / "scripts" / "run_runtime_stability_gate.py"
_RUN_RUNTIME_ROLLOUT_GATE = _REPO_ROOT / "scripts" / "run_runtime_rollout_gate.py"
_RUN_PROVIDER_GATE = _REPO_ROOT / "scripts" / "run_provider_capability_verification_gate.py"
_RUN_SKILL_ORCHESTRATION_EVALUATION_GATE = _REPO_ROOT / "scripts" / "run_skill_orchestration_evaluation_gate.py"
_LOCKFILE_PATHS = {
    "desktop_package_lock": _REPO_ROOT / "apps" / "astrabridge-desktop" / "package-lock.json",
    "desktop_pnpm_lock": _REPO_ROOT / "apps" / "astrabridge-desktop" / "pnpm-lock.yaml",
    "desktop_cargo_lock": _REPO_ROOT / "apps" / "astrabridge-desktop" / "src-tauri" / "Cargo.lock",
    "sidecar_uv_lock": _REPO_ROOT / "apps" / "astrabridge-sidecar" / "uv.lock",
}

CommandRunner = Callable[[list[str], Path], dict[str, Any]]


def run_promotion_gate(
    *,
    mode: str,
    workspace_root: str | Path | None = None,
    artifact_root: str | Path | None = None,
    run_id: str | None = None,
    expected_commit: str | None = None,
    allow_dirty: bool = False,
    command_runner: CommandRunner | None = None,
    check_specs: Sequence[dict[str, Any]] | None = None,
    git_context: dict[str, Any] | None = None,
    toolchain_versions: dict[str, Any] | None = None,
) -> dict[str, Any]:
    repo_root = Path(workspace_root).expanduser().resolve() if workspace_root else _REPO_ROOT
    created_at = now_iso()
    resolved_mode = str(mode or "pr").strip().lower() or "pr"
    if resolved_mode not in {"pr", "nightly", "release"}:
        raise ValueError("mode must be pr, nightly, or release.")
    resolved_run_id = slugify(run_id or f"promotion-gate-{resolved_mode}-{created_at}", default="promotion-gate")
    gate_run_dir = _resolve_gate_run_dir(root=repo_root, artifact_root=artifact_root, run_id=resolved_run_id)
    raw_dir = gate_run_dir / "raw"
    checks_dir = raw_dir / "checks"
    reports_dir = gate_run_dir / "reports"
    validations_dir = gate_run_dir / "validations"
    for path in (gate_run_dir, raw_dir, checks_dir, reports_dir, validations_dir):
        path.mkdir(parents=True, exist_ok=True)

    runner = command_runner or _default_command_runner
    resolved_git_context = git_context or collect_git_context(repo_root=repo_root, expected_commit=expected_commit)
    resolved_toolchains = toolchain_versions or collect_toolchain_versions(repo_root=repo_root)
    resolved_specs = list(check_specs or promotion_gate_specs(mode=resolved_mode, gate_run_dir=gate_run_dir, repo_root=repo_root))

    manifest = {
        "schema_version": PROMOTION_GATE_MANIFEST_SCHEMA_VERSION,
        "mode": resolved_mode,
        "check_count": len(resolved_specs),
        "checks": [_manifest_entry(spec) for spec in resolved_specs],
    }
    manifest_path = validations_dir / "manifest.json"
    write_json(manifest_path, manifest)

    check_results: list[dict[str, Any]] = []
    promotion_errors: list[str] = []
    for spec in resolved_specs:
        result = _run_check(spec=spec, command_runner=runner)
        check_results.append(result)
        if result["status"] != "pass" and result.get("required", True):
            promotion_errors.extend(str(item) for item in list(result.get("failures") or []))

    if resolved_git_context.get("dirty") and not allow_dirty:
        promotion_errors.append("git worktree is dirty; promotion gates fail closed until evaluated from a clean tree")
    if resolved_git_context.get("expected_commit") and resolved_git_context.get("commit") != resolved_git_context.get("expected_commit"):
        promotion_errors.append(
            "tested commit does not match the required promotion commit: "
            f"{resolved_git_context.get('commit')} != {resolved_git_context.get('expected_commit')}"
        )

    summary_path = reports_dir / "summary.json"
    report_path = reports_dir / "report.md"
    summary = {
        "schema_version": PROMOTION_GATE_SCHEMA_VERSION,
        "run_id": resolved_run_id,
        "created_at": created_at,
        "status": "pass" if not promotion_errors else "fail",
        "mode": resolved_mode,
        "promotion_ready": not promotion_errors,
        "promotion_errors": promotion_errors,
        "source": resolved_git_context,
        "toolchains": resolved_toolchains,
        "locks": _lockfile_digests(repo_root),
        "manifest": {
            "path": str(manifest_path),
            "sha256": _hash_file(manifest_path),
            "check_count": len(resolved_specs),
        },
        "checks": check_results,
        "artifact_paths": {
            "run_dir": str(gate_run_dir),
            "raw_dir": str(raw_dir),
            "reports_dir": str(reports_dir),
            "validations_dir": str(validations_dir),
            "summary_json": str(summary_path),
            "report_md": str(report_path),
            "manifest_json": str(manifest_path),
        },
        "policy": {
            "allow_dirty": allow_dirty,
            "required_problem_statuses": sorted(_PROBLEM_STATUSES),
            "fail_closed_conditions": [
                "required check missing",
                "required summary missing or forged",
                "required status path missing",
                "required status path skipped/missing/unknown/unevaluated",
                "tested commit mismatch",
                "dirty worktree",
            ],
        },
    }
    write_json(summary_path, summary)
    report_path.write_text(render_promotion_gate_report(summary), encoding="utf-8", newline="\n")
    return summary


def collect_git_context(*, repo_root: Path, expected_commit: str | None) -> dict[str, Any]:
    commit = _git_output(["git", "rev-parse", "HEAD"], repo_root)
    branch = _git_output(["git", "rev-parse", "--abbrev-ref", "HEAD"], repo_root)
    dirty = bool(_git_output(["git", "status", "--porcelain"], repo_root))
    return {
        "repo_root": str(repo_root),
        "commit": commit,
        "expected_commit": str(expected_commit or commit),
        "branch": branch,
        "detached_head": branch == "HEAD",
        "dirty": dirty,
    }


def collect_toolchain_versions(*, repo_root: Path) -> dict[str, Any]:
    versions = {
        "python": _toolchain_output([sys.executable, "--version"], repo_root),
        "node": _toolchain_output(["node", "--version"], repo_root),
        "npm": _toolchain_output([("npm.cmd" if os.name == "nt" else "npm"), "--version"], repo_root),
        "cargo": _toolchain_output(["cargo", "--version"], repo_root),
    }
    return versions


def promotion_gate_specs(*, mode: str, gate_run_dir: Path, repo_root: Path) -> tuple[dict[str, Any], ...]:
    python_cmd = sys.executable
    local_quick_root = gate_run_dir / "nested" / "local-quick"
    local_full_root = gate_run_dir / "nested" / "local-full"
    provider_root = gate_run_dir / "nested" / "provider-capability"
    runtime_release_root = gate_run_dir / "nested" / "runtime-stability-release"
    rollout_root = gate_run_dir / "nested" / "runtime-rollout"
    skill_orchestration_root = gate_run_dir / "nested" / "skill-orchestration-evaluation"
    skill_orchestration_mode = "promotion" if mode == "release" else "evaluate"
    skill_orchestration_spec = {
        "check_id": "skill_orchestration_evaluation",
        "label": "Skill orchestration evaluation and promotion gate",
        "required": True,
        "cwd": repo_root,
        "command": [
            python_cmd,
            str(_RUN_SKILL_ORCHESTRATION_EVALUATION_GATE),
            "--mode",
            skill_orchestration_mode,
            "--artifact-root",
            str(skill_orchestration_root),
            "--run-id",
            "skill-orchestration-evaluation",
        ],
        "required_status_paths": ("status", "patterns.*.status"),
        "required_summary_fields": ("schema_version", "status", "mode", "promotion_ready", "patterns", "artifact_paths"),
        "required_artifact_keys": ("summary_json", "report_md"),
        "expected_schema_version": "astrabridge-skill-orchestration-evaluation-gate-v1",
    }
    if mode == "pr":
        return (
            {
                "check_id": "local_quick",
                "label": "Local quick gate",
                "required": True,
                "cwd": repo_root,
                "command": [
                    python_cmd,
                    str(_RUN_LOCAL_GATE),
                    "--quick",
                    "--json",
                    "--artifact-root",
                    str(local_quick_root),
                    "--run-id",
                    "local-quick",
                ],
                "required_status_paths": ("status", "checks.*.status"),
                "required_summary_fields": ("schema_version", "status", "mode", "checks", "artifact_paths"),
                "required_artifact_keys": ("summary_json", "report_md"),
                "expected_schema_version": "astrabridge-local-gate-v1",
            },
            skill_orchestration_spec,
        )
    if mode == "nightly":
        return (
            {
                "check_id": "local_full",
                "label": "Local full gate",
                "required": True,
                "cwd": repo_root,
                "command": [
                    python_cmd,
                    str(_RUN_LOCAL_GATE),
                    "--full",
                    "--json",
                    "--artifact-root",
                    str(local_full_root),
                    "--run-id",
                    "local-full",
                ],
                "required_status_paths": ("status", "checks.*.status"),
                "required_summary_fields": ("schema_version", "status", "mode", "checks", "artifact_paths"),
                "required_artifact_keys": ("summary_json", "report_md"),
                "expected_schema_version": "astrabridge-local-gate-v1",
            },
            {
                "check_id": "provider_capability_verification",
                "label": "Provider capability verification gate",
                "required": True,
                "cwd": repo_root,
                "command": [
                    python_cmd,
                    str(_RUN_PROVIDER_GATE),
                    "--artifact-root",
                    str(provider_root),
                    "--run-id",
                    "provider-capability",
                ],
                "required_status_paths": ("status", "baseline_evaluation.status"),
                "required_summary_fields": ("schema_version", "status", "artifact_paths", "baseline_evaluation"),
                "required_artifact_keys": ("summary_json", "report_md"),
                "expected_schema_version": "astrabridge-provider-capability-verification-gate-v1",
            },
            {
                "check_id": "runtime_stability_release",
                "label": "Runtime stability release gate",
                "required": True,
                "cwd": repo_root,
                "command": [
                    python_cmd,
                    str(_RUN_RUNTIME_STABILITY_GATE),
                    "--mode",
                    "release",
                    "--artifact-root",
                    str(runtime_release_root),
                    "--run-id",
                    "runtime-stability-release",
                ],
                "required_status_paths": ("status", "secret_scan.status", "suites.*.status"),
                "required_summary_fields": ("schema_version", "status", "suites", "secret_scan", "artifact_paths"),
                "required_artifact_keys": ("summary_json", "report_md"),
                "expected_schema_version": "astrabridge-runtime-stability-gate-v1",
            },
            skill_orchestration_spec,
        )
    return (
        {
            "check_id": "local_quick",
            "label": "Local quick gate",
            "required": True,
            "cwd": repo_root,
            "command": [
                python_cmd,
                str(_RUN_LOCAL_GATE),
                "--quick",
                "--json",
                "--artifact-root",
                str(local_quick_root),
                "--run-id",
                "local-quick",
            ],
            "required_status_paths": ("status", "checks.*.status"),
            "required_summary_fields": ("schema_version", "status", "mode", "checks", "artifact_paths"),
            "required_artifact_keys": ("summary_json", "report_md"),
            "expected_schema_version": "astrabridge-local-gate-v1",
        },
        {
            "check_id": "provider_capability_verification",
            "label": "Provider capability verification gate",
            "required": True,
            "cwd": repo_root,
            "command": [
                python_cmd,
                str(_RUN_PROVIDER_GATE),
                "--artifact-root",
                str(provider_root),
                "--run-id",
                "provider-capability",
            ],
            "required_status_paths": ("status", "baseline_evaluation.status"),
            "required_summary_fields": ("schema_version", "status", "artifact_paths", "baseline_evaluation"),
            "required_artifact_keys": ("summary_json", "report_md"),
            "expected_schema_version": "astrabridge-provider-capability-verification-gate-v1",
        },
        {
            "check_id": "runtime_rollout",
            "label": "Runtime rollout gate",
            "required": True,
            "cwd": repo_root,
            "command": [
                python_cmd,
                str(_RUN_RUNTIME_ROLLOUT_GATE),
                "--artifact-root",
                str(rollout_root),
                "--run-id",
                "runtime-rollout",
            ],
            "required_status_paths": ("status", "checks.*"),
            "required_summary_fields": ("schema_version", "status", "checks", "artifact_paths"),
            "required_artifact_keys": ("summary_json", "report_md"),
            "expected_schema_version": "astrabridge-runtime-rollout-gate-v1",
        },
        skill_orchestration_spec,
    )


def render_promotion_gate_report(summary: dict[str, Any]) -> str:
    lines = [
        "# Promotion Gate",
        "",
        f"- Run ID: `{summary.get('run_id')}`",
        f"- Created: `{summary.get('created_at')}`",
        f"- Status: `{summary.get('status')}`",
        f"- Mode: `{summary.get('mode')}`",
        f"- Commit: `{dict(summary.get('source') or {}).get('commit')}`",
        f"- Expected commit: `{dict(summary.get('source') or {}).get('expected_commit')}`",
        f"- Dirty: `{dict(summary.get('source') or {}).get('dirty')}`",
        "",
        "## Checks",
        "",
    ]
    for check in list(summary.get("checks") or []):
        lines.extend(
            [
                f"- `{check.get('check_id')}` status=`{check.get('status')}` exit=`{check.get('exit_code')}`",
                f"  - summary: `{check.get('summary_path')}`",
                f"  - report: `{check.get('report_path')}`",
                f"  - stdout: `{check.get('stdout_path')}`",
                f"  - stderr: `{check.get('stderr_path')}`",
            ]
        )
        for failure in list(check.get("failures") or []):
            lines.append(f"  - failure: `{failure}`")
    if summary.get("promotion_errors"):
        lines.extend(["", "## Promotion Errors", ""])
        for item in list(summary.get("promotion_errors") or []):
            lines.append(f"- `{item}`")
    return "\n".join(lines).rstrip() + "\n"


def _run_check(*, spec: dict[str, Any], command_runner: CommandRunner) -> dict[str, Any]:
    check_id = str(spec.get("check_id") or "check")
    command = [str(item) for item in list(spec.get("command") or [])]
    cwd = Path(spec.get("cwd") or _REPO_ROOT)
    artifact_root = _check_artifact_root(spec)
    artifact_root.mkdir(parents=True, exist_ok=True)
    stdout_path = artifact_root / "stdout.log"
    stderr_path = artifact_root / "stderr.log"
    result = command_runner(command, cwd)
    stdout = str(result.get("stdout") or "")
    stderr = str(result.get("stderr") or "")
    stdout_path.write_text(stdout, encoding="utf-8", newline="\n")
    stderr_path.write_text(stderr, encoding="utf-8", newline="\n")
    failures: list[str] = []
    summary_stdout = _parse_json_payload(stdout)
    if summary_stdout is None:
        failures.append(f"{check_id}: command did not emit a machine-readable JSON summary")
    summary_file: dict[str, Any] | None = None
    summary_path = None
    report_path = None
    if isinstance(summary_stdout, dict):
        artifact_paths = dict(summary_stdout.get("artifact_paths") or {})
        summary_path_text = str(artifact_paths.get("summary_json") or "").strip()
        report_path_text = str(artifact_paths.get("report_md") or "").strip()
        summary_path = Path(summary_path_text).resolve() if summary_path_text else None
        report_path = Path(report_path_text).resolve() if report_path_text else None
        if summary_path is None or not summary_path.exists():
            failures.append(f"{check_id}: required summary_json artifact is missing")
        else:
            summary_file = json.loads(summary_path.read_text(encoding="utf-8"))
            if summary_file != summary_stdout:
                failures.append(f"{check_id}: stdout summary does not match persisted summary.json")
        if report_path is None or not report_path.exists():
            failures.append(f"{check_id}: required report_md artifact is missing")
        _validate_summary_contract(spec=spec, summary=summary_file or summary_stdout, failures=failures)
    exit_code = int(result.get("exit_code") or 0)
    if exit_code != 0:
        failures.append(f"{check_id}: command exited with non-zero status {exit_code}")
    artifact_digests = {}
    if summary_path and summary_path.exists():
        artifact_digests["summary_json"] = _hash_file(summary_path)
    if report_path and report_path.exists():
        artifact_digests["report_md"] = _hash_file(report_path)
    artifact_digests["stdout_log"] = _hash_file(stdout_path)
    artifact_digests["stderr_log"] = _hash_file(stderr_path)
    return {
        "check_id": check_id,
        "label": str(spec.get("label") or check_id),
        "required": bool(spec.get("required", True)),
        "status": "pass" if not failures else "fail",
        "exit_code": exit_code,
        "cwd": str(cwd),
        "command": command,
        "stdout_path": str(stdout_path),
        "stderr_path": str(stderr_path),
        "summary_path": None if summary_path is None else str(summary_path),
        "report_path": None if report_path is None else str(report_path),
        "artifact_digests": artifact_digests,
        "failures": failures,
    }


def _validate_summary_contract(*, spec: dict[str, Any], summary: dict[str, Any] | None, failures: list[str]) -> None:
    check_id = str(spec.get("check_id") or "check")
    if not isinstance(summary, dict):
        failures.append(f"{check_id}: summary payload is missing or invalid")
        return
    for field in tuple(spec.get("required_summary_fields") or ()):
        if field not in summary:
            failures.append(f"{check_id}: summary missing required field `{field}`")
    expected_schema_version = str(spec.get("expected_schema_version") or "").strip()
    if expected_schema_version and str(summary.get("schema_version") or "") != expected_schema_version:
        failures.append(
            f"{check_id}: unexpected schema_version `{summary.get('schema_version')}`; expected `{expected_schema_version}`"
        )
    artifact_paths = dict(summary.get("artifact_paths") or {})
    for key in tuple(spec.get("required_artifact_keys") or ()):
        if not str(artifact_paths.get(key) or "").strip():
            failures.append(f"{check_id}: artifact_paths missing `{key}`")
    for path_expr in tuple(spec.get("required_status_paths") or ()):
        values = list(_resolve_path_values(summary, path_expr))
        if not values:
            failures.append(f"{check_id}: required status path `{path_expr}` was not present in summary")
            continue
        for value in values:
            normalized = str(value or "").strip().lower()
            if not normalized:
                failures.append(f"{check_id}: required status path `{path_expr}` was empty")
            elif normalized in _PROBLEM_STATUSES:
                failures.append(f"{check_id}: required status path `{path_expr}` is `{normalized}`")
            elif path_expr == "status" and normalized != "pass":
                failures.append(f"{check_id}: top-level status must be `pass`, got `{normalized}`")


def _resolve_gate_run_dir(*, root: Path, artifact_root: str | Path | None, run_id: str) -> Path:
    if artifact_root:
        return Path(artifact_root).expanduser().resolve() / run_id
    return root / "PRIVATE" / "promotion-gates" / run_id


def _manifest_entry(spec: dict[str, Any]) -> dict[str, Any]:
    return {
        "check_id": str(spec.get("check_id") or ""),
        "label": str(spec.get("label") or ""),
        "required": bool(spec.get("required", True)),
        "cwd": str(spec.get("cwd") or _REPO_ROOT),
        "command": [str(item) for item in list(spec.get("command") or [])],
        "required_status_paths": list(spec.get("required_status_paths") or []),
        "required_summary_fields": list(spec.get("required_summary_fields") or []),
        "required_artifact_keys": list(spec.get("required_artifact_keys") or []),
        "expected_schema_version": str(spec.get("expected_schema_version") or ""),
    }


def _check_artifact_root(spec: dict[str, Any]) -> Path:
    command = [str(item) for item in list(spec.get("command") or [])]
    for flag in ("--artifact-root",):
        if flag in command:
            index = command.index(flag)
            if index + 1 < len(command):
                return Path(command[index + 1]).expanduser().resolve()
    return _REPO_ROOT / "PRIVATE" / "promotion-gates" / "unknown-check"


def _lockfile_digests(repo_root: Path) -> dict[str, Any]:
    digests: dict[str, Any] = {}
    for lock_id, path in _LOCKFILE_PATHS.items():
        resolved = path if path.is_absolute() else repo_root / path
        digests[lock_id] = {
            "path": str(resolved),
            "exists": resolved.exists(),
            "sha256": _hash_file(resolved) if resolved.exists() else None,
        }
    return digests


def _resolve_path_values(payload: Any, path_expr: str) -> Iterable[Any]:
    parts = [part for part in str(path_expr).split(".") if part]

    def walk(current: Any, index: int) -> Iterable[Any]:
        if index >= len(parts):
            yield current
            return
        part = parts[index]
        if part == "*":
            if isinstance(current, dict):
                for value in current.values():
                    yield from walk(value, index + 1)
            elif isinstance(current, list):
                for value in current:
                    yield from walk(value, index + 1)
            return
        if isinstance(current, dict) and part in current:
            yield from walk(current[part], index + 1)
        elif isinstance(current, list):
            try:
                offset = int(part)
            except ValueError:
                return
            if 0 <= offset < len(current):
                yield from walk(current[offset], index + 1)

    yield from walk(payload, 0)


def _default_command_runner(command: list[str], cwd: Path) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except OSError as exc:
        return {"exit_code": 1, "stdout": "", "stderr": f"{type(exc).__name__}: {exc}"}
    return {
        "exit_code": int(completed.returncode),
        "stdout": completed.stdout or "",
        "stderr": completed.stderr or "",
    }


def _git_output(command: list[str], cwd: Path) -> str:
    completed = subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return str(completed.stdout or "").strip()


def _toolchain_output(command: list[str], cwd: Path) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except OSError as exc:
        return {"status": "missing", "version": None, "error": f"{type(exc).__name__}: {exc}"}
    output = str((completed.stdout or completed.stderr or "")).strip()
    return {
        "status": "pass" if completed.returncode == 0 and output else "fail",
        "version": output or None,
        "returncode": int(completed.returncode),
    }


def _parse_json_payload(payload: str) -> dict[str, Any] | None:
    text = str(payload or "").strip()
    if not text:
        return None
    try:
        loaded = json.loads(text)
    except json.JSONDecodeError:
        return None
    return loaded if isinstance(loaded, dict) else None


def _hash_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


__all__ = [
    "PROMOTION_GATE_MANIFEST_SCHEMA_VERSION",
    "PROMOTION_GATE_SCHEMA_VERSION",
    "collect_git_context",
    "collect_toolchain_versions",
    "promotion_gate_specs",
    "render_promotion_gate_report",
    "run_promotion_gate",
]
