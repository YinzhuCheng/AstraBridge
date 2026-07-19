from __future__ import annotations

from contextlib import contextmanager
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from .common import now_iso, slugify, write_json
from .provider_capability_dry_run_matrix import run_provider_capability_dry_run_matrix


PROVIDER_CAPABILITY_VERIFICATION_GATE_SCHEMA_VERSION = "astrabridge-provider-capability-verification-gate-v1"
_PROBLEM_CAPABILITY_STATUSES = {"conflicting", "unknown"}
_REPO_ROOT = Path(__file__).resolve().parents[3]
_SIDECAR_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_TEST_GROUPS: tuple[dict[str, Any], ...] = (
    {
        "label": "static_request_shape_and_routes",
        "modules": (
            "tests.test_vision_analyze_adapter",
            "tests.test_speech_transcribe_adapter",
            "tests.test_speech_synthesize_adapter",
            "tests.test_provider_transport_conformance",
            "tests.test_capability_smoke",
            "tests.test_provider_compatibility_smoke",
            "tests.test_capability_registry",
        ),
    },
    {
        "label": "matrix_contract_and_catalog",
        "modules": (
            "tests.test_provider_source_registry",
            "tests.test_provider_catalog_contract",
            "tests.test_model_catalog_contract",
            "tests.test_provider_model_compatibility_matrix",
        ),
    },
    {
        "label": "reasoning_mapping_and_gate",
        "modules": (
            "tests.test_reasoning_policy_normalization",
            "tests.test_provider_capability_dry_run_matrix",
            "tests.test_provider_capability_verification_gate",
        ),
    },
)


def default_baseline_path() -> Path:
    return Path(__file__).with_name("provider_capability_verification_gate_baseline.json")


def load_verification_baseline(path: str | Path | None = None) -> dict[str, Any]:
    baseline_path = Path(path).resolve() if path else default_baseline_path()
    payload = json.loads(baseline_path.read_text(encoding="utf-8"))
    if str(payload.get("schema_version") or "") != PROVIDER_CAPABILITY_VERIFICATION_GATE_SCHEMA_VERSION:
        raise ValueError(f"Unexpected verification gate baseline schema version: {baseline_path}")
    return payload


def evaluate_dry_run_summary(summary: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    allowed_preview = {
        str(item.get("case_id") or ""): {str(status) for status in list(item.get("allowed_statuses") or []) if str(status).strip()}
        for item in list(baseline.get("allowed_nonpass_preview_cases") or [])
        if str(item.get("case_id") or "").strip()
    }
    allowed_capability = {
        str(item.get("case_id") or ""): {
            str(status) for status in list(item.get("allowed_capability_statuses") or []) if str(status).strip()
        }
        for item in list(baseline.get("allowed_problem_capability_cases") or [])
        if str(item.get("case_id") or "").strip()
    }

    current_preview = {
        str(case.get("case_id") or ""): case
        for case in list(summary.get("preview_cases") or [])
        if str(case.get("status") or "") != "pass" and str(case.get("case_id") or "").strip()
    }
    current_capability = {
        str(case.get("case_id") or ""): case
        for case in list(summary.get("capability_cases") or [])
        if str(case.get("capability_status") or "") in _PROBLEM_CAPABILITY_STATUSES and str(case.get("case_id") or "").strip()
    }

    unexpected_preview_cases = [
        case
        for case_id, case in current_preview.items()
        if str(case.get("status") or "") not in allowed_preview.get(case_id, set())
    ]
    unexpected_capability_cases = [
        case
        for case_id, case in current_capability.items()
        if str(case.get("capability_status") or "") not in allowed_capability.get(case_id, set())
    ]

    resolved_preview_case_ids = sorted(case_id for case_id in allowed_preview if case_id not in current_preview)
    resolved_capability_case_ids = sorted(case_id for case_id in allowed_capability if case_id not in current_capability)

    return {
        "status": "pass" if not unexpected_preview_cases and not unexpected_capability_cases else "fail",
        "unexpected_preview_cases": unexpected_preview_cases,
        "unexpected_capability_cases": unexpected_capability_cases,
        "resolved_preview_case_ids": resolved_preview_case_ids,
        "resolved_capability_case_ids": resolved_capability_case_ids,
        "allowed_preview_case_count": len(allowed_preview),
        "allowed_capability_case_count": len(allowed_capability),
    }


def run_provider_capability_verification_gate(
    *,
    workspace_root: str | Path | None = None,
    artifact_root: str | Path | None = None,
    run_id: str | None = None,
    baseline_path: str | Path | None = None,
    python_executable: str | None = None,
    include_tests: bool = True,
) -> dict[str, Any]:
    root = Path(workspace_root).expanduser().resolve() if workspace_root else _REPO_ROOT
    created_at = now_iso()
    resolved_run_id = slugify(run_id or f"provider-capability-verification-gate-{created_at}", default="provider-capability-verification-gate")
    gate_run_dir = _resolve_gate_run_dir(root=root, artifact_root=artifact_root, run_id=resolved_run_id)
    gate_run_dir.mkdir(parents=True, exist_ok=True)
    command_dir = gate_run_dir / "commands"
    command_dir.mkdir(parents=True, exist_ok=True)
    state_root = gate_run_dir / "state"
    state_root.mkdir(parents=True, exist_ok=True)

    python_cmd = python_executable or sys.executable
    command_results: list[dict[str, Any]] = []

    with _temporary_env(
        {
            "ASTRABRIDGE_APPDATA": str(state_root / "appdata"),
            "ASTRABRIDGE_RUNTIME_ROOT": str(state_root / "runtime"),
        }
    ):
        if include_tests:
            for group in DEFAULT_TEST_GROUPS:
                command_results.append(
                    _run_test_group(
                        label=str(group.get("label") or "tests"),
                        modules=tuple(str(item) for item in tuple(group.get("modules") or ()) if str(item).strip()),
                        python_executable=python_cmd,
                        cwd=_SIDECAR_ROOT,
                        command_dir=command_dir,
                    )
                )
                if command_results[-1]["exit_code"] != 0:
                    summary = _write_gate_outputs(
                        gate_run_dir=gate_run_dir,
                        created_at=created_at,
                        run_id=resolved_run_id,
                        baseline_path=baseline_path,
                        command_results=command_results,
                        dry_run_summary=None,
                        baseline_evaluation=None,
                        status="fail",
                        include_tests=include_tests,
                    )
                    return summary

        dry_run_summary = run_provider_capability_dry_run_matrix(
            workspace_root=root,
            run_id=f"{resolved_run_id}-dry-run",
        )
        baseline = load_verification_baseline(baseline_path)
        baseline_evaluation = evaluate_dry_run_summary(dry_run_summary, baseline)
        summary = _write_gate_outputs(
            gate_run_dir=gate_run_dir,
            created_at=created_at,
            run_id=resolved_run_id,
            baseline_path=baseline_path,
            command_results=command_results,
            dry_run_summary=dry_run_summary,
            baseline_evaluation=baseline_evaluation,
            status="pass" if baseline_evaluation["status"] == "pass" else "fail",
            include_tests=include_tests,
        )
        return summary


def _resolve_gate_run_dir(*, root: Path, artifact_root: str | Path | None, run_id: str) -> Path:
    if artifact_root:
        return Path(artifact_root).expanduser().resolve() / run_id
    return root / "PRIVATE" / "agentic-update-pipeline" / "runs" / run_id


def _run_test_group(
    *,
    label: str,
    modules: tuple[str, ...],
    python_executable: str,
    cwd: Path,
    command_dir: Path,
) -> dict[str, Any]:
    command = [python_executable, "-m", "unittest", *modules]
    completed = subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    stdout_path = command_dir / f"{label}.stdout.log"
    stderr_path = command_dir / f"{label}.stderr.log"
    stdout_path.write_text(completed.stdout or "", encoding="utf-8", newline="\n")
    stderr_path.write_text(completed.stderr or "", encoding="utf-8", newline="\n")
    return {
        "label": label,
        "command": command,
        "cwd": str(cwd),
        "modules": list(modules),
        "exit_code": int(completed.returncode),
        "stdout_path": str(stdout_path),
        "stderr_path": str(stderr_path),
    }


def _write_gate_outputs(
    *,
    gate_run_dir: Path,
    created_at: str,
    run_id: str,
    baseline_path: str | Path | None,
    command_results: list[dict[str, Any]],
    dry_run_summary: dict[str, Any] | None,
    baseline_evaluation: dict[str, Any] | None,
    status: str,
    include_tests: bool,
) -> dict[str, Any]:
    resolved_baseline_path = str(Path(baseline_path).resolve()) if baseline_path else str(default_baseline_path())
    summary_path = gate_run_dir / "summary.json"
    report_path = gate_run_dir / "report.md"
    summary = {
        "schema_version": PROVIDER_CAPABILITY_VERIFICATION_GATE_SCHEMA_VERSION,
        "run_id": run_id,
        "created_at": created_at,
        "status": status,
        "include_tests": include_tests,
        "baseline_path": resolved_baseline_path,
        "commands": command_results,
        "dry_run_summary": {
            "run_id": dry_run_summary.get("run_id"),
            "summary_json": dry_run_summary.get("artifact_paths", {}).get("summary_json"),
            "report_md": dry_run_summary.get("artifact_paths", {}).get("report_md"),
            "matrix_json": dry_run_summary.get("artifact_paths", {}).get("matrix_json"),
            "preview_status_counts": dry_run_summary.get("preview_status_counts"),
            "capability_status_counts": dry_run_summary.get("capability_status_counts"),
            "matrix_overall_status_counts": dry_run_summary.get("matrix_overall_status_counts"),
        }
        if isinstance(dry_run_summary, dict)
        else None,
        "baseline_evaluation": baseline_evaluation,
        "artifact_paths": {
            "run_dir": str(gate_run_dir),
            "summary_json": str(summary_path),
            "report_md": str(report_path),
            "command_dir": str(gate_run_dir / "commands"),
            "state_root": str(gate_run_dir / "state"),
        },
        "policy": {
            "live_provider_calls": False,
            "managed_key_required": False,
            "web_lane_policy": "standalone",
        },
    }
    write_json(summary_path, summary)
    report_path.write_text(_render_gate_report(summary), encoding="utf-8", newline="\n")
    return summary


def _render_gate_report(summary: dict[str, Any]) -> str:
    lines = [
        "# Provider Capability Verification Gate",
        "",
        f"- Run ID: `{summary.get('run_id')}`",
        f"- Created: `{summary.get('created_at')}`",
        f"- Status: `{summary.get('status')}`",
        f"- Baseline: `{summary.get('baseline_path')}`",
        f"- Live provider calls: `{summary.get('policy', {}).get('live_provider_calls')}`",
        "",
        "## Commands",
        "",
    ]
    for command in list(summary.get("commands") or []):
        lines.extend(
            [
                f"- `{command.get('label')}` exit=`{command.get('exit_code')}`",
                f"  - cwd: `{command.get('cwd')}`",
                f"  - command: `{_shell_line(list(command.get('command') or []))}`",
                f"  - stdout: `{command.get('stdout_path')}`",
                f"  - stderr: `{command.get('stderr_path')}`",
            ]
        )
    dry_run = dict(summary.get("dry_run_summary") or {})
    if dry_run:
        lines.extend(
            [
                "",
                "## Dry-Run Matrix",
                "",
                f"- Run ID: `{dry_run.get('run_id')}`",
                f"- Summary JSON: `{dry_run.get('summary_json')}`",
                f"- Report MD: `{dry_run.get('report_md')}`",
                f"- Matrix JSON: `{dry_run.get('matrix_json')}`",
                f"- Preview status counts: `{json.dumps(dry_run.get('preview_status_counts') or {}, ensure_ascii=False)}`",
                f"- Capability status counts: `{json.dumps(dry_run.get('capability_status_counts') or {}, ensure_ascii=False)}`",
                f"- Matrix overall status counts: `{json.dumps(dry_run.get('matrix_overall_status_counts') or {}, ensure_ascii=False)}`",
            ]
        )
    evaluation = dict(summary.get("baseline_evaluation") or {})
    if evaluation:
        lines.extend(
            [
                "",
                "## Baseline Evaluation",
                "",
                f"- Allowed preview blockers: `{evaluation.get('allowed_preview_case_count')}`",
                f"- Allowed capability conflicts: `{evaluation.get('allowed_capability_case_count')}`",
                f"- Resolved preview blockers: `{json.dumps(evaluation.get('resolved_preview_case_ids') or [], ensure_ascii=False)}`",
                f"- Resolved capability conflicts: `{json.dumps(evaluation.get('resolved_capability_case_ids') or [], ensure_ascii=False)}`",
            ]
        )
        unexpected_preview = list(evaluation.get("unexpected_preview_cases") or [])
        unexpected_capability = list(evaluation.get("unexpected_capability_cases") or [])
        if unexpected_preview:
            lines.extend(["", "### Unexpected Preview Blockers", ""])
            for case in unexpected_preview:
                lines.append(
                    f"- `{case.get('case_id')}` `{case.get('model')}` `{case.get('preview_variant')}` -> `{case.get('status')}` `{json.dumps(case.get('reasons') or [], ensure_ascii=False)}`"
                )
        if unexpected_capability:
            lines.extend(["", "### Unexpected Capability Regressions", ""])
            for case in unexpected_capability:
                lines.append(
                    f"- `{case.get('case_id')}` `{case.get('model')}` `{case.get('capability_id')}` -> capability_status=`{case.get('capability_status')}` status=`{case.get('status')}` reasons=`{json.dumps(case.get('reasons') or [], ensure_ascii=False)}`"
                )
    return "\n".join(lines).rstrip() + "\n"


def _shell_line(command: list[str]) -> str:
    return " ".join(str(item) for item in command)


@contextmanager
def _temporary_env(updates: dict[str, str]) -> Any:
    previous = {key: os.environ.get(key) for key in updates}
    try:
        for key, value in updates.items():
            os.environ[key] = value
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
