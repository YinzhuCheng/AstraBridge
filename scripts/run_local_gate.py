from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable


REPO_ROOT = Path(__file__).resolve().parents[1]
SIDECAR_ROOT = REPO_ROOT / "apps" / "astrabridge-sidecar"
if str(SIDECAR_ROOT) not in sys.path:
    sys.path.insert(0, str(SIDECAR_ROOT))

from astrabridge_sidecar.common import now_iso, slugify, write_json  # noqa: E402


LOCAL_GATE_SCHEMA_VERSION = "astrabridge-local-gate-v1"

CommandRunner = Callable[[list[str], Path, bool], dict[str, Any]]


def npm_command() -> str:
    return "npm.cmd" if os.name == "nt" else "npm"


def default_command_runner(command: list[str], cwd: Path, dry_run: bool) -> dict[str, Any]:
    if dry_run:
        return {"exit_code": 0, "stdout": "", "stderr": "", "dry_run": True}
    completed = subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return {
        "exit_code": int(completed.returncode),
        "stdout": completed.stdout or "",
        "stderr": completed.stderr or "",
        "dry_run": False,
    }


def quick_command_specs() -> list[dict[str, Any]]:
    return [
        {
            "check_id": "repo_governance",
            "label": "Repository governance check",
            "command": [sys.executable, "scripts/repo_governance_check.py", "--repo", "."],
            "cwd": REPO_ROOT,
        },
        {
            "check_id": "app_hardening_secret_scan",
            "label": "App-hardening secret scan",
            "command": [sys.executable, "scripts/app_hardening_secret_scan.py", "--repo", "."],
            "cwd": REPO_ROOT,
        },
        {
            "check_id": "contract_boundary_audit",
            "label": "Contract boundary audit",
            "command": [sys.executable, "scripts/contract_boundary_audit.py"],
            "cwd": REPO_ROOT,
        },
        {
            "check_id": "shell_module_budget_audit",
            "label": "Shell-module budget audit",
            "command": [sys.executable, "scripts/shell_module_budget_audit.py"],
            "cwd": REPO_ROOT,
        },
        {
            "check_id": "repo_governance_tests",
            "label": "Repository governance tests",
            "command": [
                sys.executable,
                "-m",
                "unittest",
                "discover",
                "-s",
                "apps/astrabridge-sidecar/tests",
                "-p",
                "test_repo_governance_check.py",
            ],
            "cwd": REPO_ROOT,
        },
        {
            "check_id": "app_hardening_secret_scan_tests",
            "label": "App-hardening secret-scan tests",
            "command": [
                sys.executable,
                "-m",
                "unittest",
                "discover",
                "-s",
                "apps/astrabridge-sidecar/tests",
                "-p",
                "test_app_hardening_secret_scan.py",
            ],
            "cwd": REPO_ROOT,
        },
        {
            "check_id": "shell_module_budget_audit_tests",
            "label": "Shell-module budget audit tests",
            "command": [
                sys.executable,
                "-m",
                "unittest",
                "discover",
                "-s",
                "apps/astrabridge-sidecar/tests",
                "-p",
                "test_shell_module_budget_audit.py",
            ],
            "cwd": REPO_ROOT,
        },
    ]


def full_command_specs() -> list[dict[str, Any]]:
    desktop = REPO_ROOT / "apps" / "astrabridge-desktop"
    return [
        *quick_command_specs(),
        {
            "check_id": "sidecar_unittests",
            "label": "Sidecar unittest discovery",
            "command": [
                sys.executable,
                "-m",
                "unittest",
                "discover",
                "-s",
                "apps/astrabridge-sidecar/tests",
            ],
            "cwd": REPO_ROOT,
        },
        {
            "check_id": "runtime_stability_fast",
            "label": "Runtime stability gate (fast projection)",
            "command": [
                sys.executable,
                "scripts/run_runtime_stability_gate.py",
                "--mode",
                "fast",
            ],
            "cwd": REPO_ROOT,
        },
        {
            "check_id": "desktop_tests",
            "label": "Desktop tests",
            "command": [npm_command(), "run", "test"],
            "cwd": desktop,
        },
        {
            "check_id": "desktop_build",
            "label": "Desktop build",
            "command": [npm_command(), "run", "build"],
            "cwd": desktop,
        },
    ]


def command_specs_for_mode(mode: str) -> list[dict[str, Any]]:
    resolved_mode = str(mode or "quick").strip().lower() or "quick"
    if resolved_mode == "full":
        return full_command_specs()
    return quick_command_specs()


def _resolve_local_gate_run_dir(*, artifact_root: str | Path | None, run_id: str) -> Path:
    if artifact_root:
        return Path(artifact_root).expanduser().resolve() / run_id
    return REPO_ROOT / "PRIVATE" / "local-gate" / run_id


def run_local_gate(
    *,
    mode: str,
    dry_run: bool = False,
    artifact_root: str | Path | None = None,
    run_id: str | None = None,
    command_runner: CommandRunner | None = None,
    emit_logs: bool = True,
) -> dict[str, Any]:
    resolved_mode = str(mode or "quick").strip().lower() or "quick"
    if resolved_mode not in {"quick", "full"}:
        raise ValueError("mode must be quick or full.")
    created_at = now_iso()
    resolved_run_id = slugify(run_id or f"local-gate-{resolved_mode}-{created_at}", default="local-gate")
    gate_run_dir = _resolve_local_gate_run_dir(artifact_root=artifact_root, run_id=resolved_run_id)
    raw_dir = gate_run_dir / "raw"
    reports_dir = gate_run_dir / "reports"
    for path in (gate_run_dir, raw_dir, reports_dir):
        path.mkdir(parents=True, exist_ok=True)

    runner = command_runner or default_command_runner
    checks: list[dict[str, Any]] = []
    overall_status = "pass"
    for spec in command_specs_for_mode(resolved_mode):
        command = [str(item) for item in list(spec.get("command") or [])]
        cwd = Path(spec.get("cwd") or REPO_ROOT)
        if emit_logs:
            print(f"\n$ {' '.join(command)}\n  cwd: {cwd}")
        result = runner(command, cwd, dry_run)
        stdout = str(result.get("stdout") or "")
        stderr = str(result.get("stderr") or "")
        if emit_logs and stdout:
            print(stdout, end="" if stdout.endswith("\n") else "\n")
        if emit_logs and stderr:
            print(stderr, file=sys.stderr, end="" if stderr.endswith("\n") else "\n")
        exit_code = int(result.get("exit_code") or 0)
        status = "pass" if exit_code == 0 else "fail"
        if status != "pass":
            overall_status = "fail"
        stdout_path = raw_dir / f"{spec['check_id']}.stdout.log"
        stderr_path = raw_dir / f"{spec['check_id']}.stderr.log"
        stdout_path.write_text(stdout, encoding="utf-8", newline="\n")
        stderr_path.write_text(stderr, encoding="utf-8", newline="\n")
        checks.append(
            {
                "check_id": str(spec["check_id"]),
                "label": str(spec["label"]),
                "command": command,
                "cwd": str(cwd),
                "status": status,
                "exit_code": exit_code,
                "dry_run": bool(result.get("dry_run")),
                "stdout_path": str(stdout_path),
                "stderr_path": str(stderr_path),
            }
        )
        if exit_code != 0:
            break

    summary_path = reports_dir / "summary.json"
    report_path = reports_dir / "report.md"
    summary = {
        "schema_version": LOCAL_GATE_SCHEMA_VERSION,
        "run_id": resolved_run_id,
        "created_at": created_at,
        "status": overall_status,
        "mode": resolved_mode,
        "dry_run": dry_run,
        "check_count": len(checks),
        "checks": checks,
        "artifact_paths": {
            "run_dir": str(gate_run_dir),
            "raw_dir": str(raw_dir),
            "reports_dir": str(reports_dir),
            "summary_json": str(summary_path),
            "report_md": str(report_path),
        },
    }
    write_json(summary_path, summary)
    report_path.write_text(render_local_gate_report(summary), encoding="utf-8", newline="\n")
    return summary


def render_local_gate_report(summary: dict[str, Any]) -> str:
    lines = [
        "# Local Gate",
        "",
        f"- Run ID: `{summary.get('run_id')}`",
        f"- Created: `{summary.get('created_at')}`",
        f"- Status: `{summary.get('status')}`",
        f"- Mode: `{summary.get('mode')}`",
        f"- Dry run: `{summary.get('dry_run')}`",
        "",
        "## Checks",
        "",
    ]
    for check in list(summary.get("checks") or []):
        lines.extend(
            [
                f"- `{check.get('check_id')}` status=`{check.get('status')}` exit=`{check.get('exit_code')}`",
                f"  - cwd: `{check.get('cwd')}`",
                f"  - command: `{' '.join(str(item) for item in list(check.get('command') or []))}`",
                f"  - stdout: `{check.get('stdout_path')}`",
                f"  - stderr: `{check.get('stderr_path')}`",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run AstraBridge local verification gates.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--quick", action="store_true", help="Run governance checks and governance tests.")
    group.add_argument("--full", action="store_true", help="Run governance, sidecar tests, desktop tests, and desktop build.")
    parser.add_argument("--dry-run", action="store_true", help="Print commands without executing them.")
    parser.add_argument("--artifact-root", default=None, help="Optional artifact root for machine-readable gate outputs.")
    parser.add_argument("--run-id", default=None, help="Optional gate run identifier.")
    parser.add_argument("--json", action="store_true", help="Print the machine-readable summary instead of a plain success/failure line.")
    args = parser.parse_args(argv)

    summary = run_local_gate(
        mode="full" if args.full else "quick",
        dry_run=args.dry_run,
        artifact_root=args.artifact_root,
        run_id=args.run_id,
        emit_logs=not args.json,
    )
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        if summary["status"] == "pass":
            print("\nLocal gate passed.")
        else:
            last_failed = next((check for check in reversed(summary["checks"]) if check.get("status") != "pass"), None)
            if last_failed:
                print(
                    "\nLocal gate failed with exit code "
                    f"{last_failed.get('exit_code')}: {' '.join(list(last_failed.get('command') or []))}"
                )
            else:
                print("\nLocal gate failed.")
    return 0 if summary["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
