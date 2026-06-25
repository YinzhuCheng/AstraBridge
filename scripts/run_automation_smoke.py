from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SIDECAR_ROOT = REPO_ROOT / "apps" / "astrabridge-sidecar"
sys.path.insert(0, str(SIDECAR_ROOT))

from astrabridge_sidecar.automations import AutomationService  # noqa: E402
from astrabridge_sidecar.project_service import ProjectService  # noqa: E402


UTC = timezone.utc


class _FakeRuntime:
    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    def record_external_event(self, event_type: str, payload: dict[str, Any] | None = None) -> None:
        self.events.append({"type": event_type, **dict(payload or {})})


class _FakeProfiles:
    @staticmethod
    def resolve_runtime_profile(profile_id: str | None) -> dict[str, Any]:
        return {
            "profile_id": profile_id or "openai-compatible",
            "provider_id": "openai",
            "model": "gpt-5.5",
            "reasoning_effort": "high",
        }


class _SmokeRunner:
    def execute(self, automation: dict[str, Any], run: dict[str, Any], workspace_session: Any) -> dict[str, Any]:
        automation_id = str(automation.get("automation_id") or "")
        common = {
            "run_id": run["run_id"],
            "automation_id": run["automation_id"],
            "project_id": run["project_id"],
            "trigger": run["trigger"],
            "status": "completed",
            "due_at": run["due_at"],
            "started_at": run.get("started_at"),
            "finished_at": datetime.now(UTC).isoformat(),
            "thread_id": run.get("thread_id"),
            "turn_id": None,
            "worktree_path": getattr(workspace_session, "worktree_path", None),
            "runtime_profile_id": "openai-compatible",
            "exit_code": 0,
            "artifact_refs": [],
            "redacted_error": None,
            "next_retry_at": None,
        }
        if automation_id == "auto-no-signal":
            return {
                **common,
                "signal": "no_signal",
                "summary": "No actionable change detected in the workspace.",
                "stdout_excerpt": "scan complete; no findings",
                "stderr_excerpt": None,
                "diff_excerpt": None,
            }
        if automation_id == "auto-finding":
            return {
                **common,
                "signal": "finding",
                "summary": "Found TODO marker that should be reviewed.",
                "stdout_excerpt": "todo: investigate stale route mapping",
                "stderr_excerpt": None,
                "diff_excerpt": "@@ -1 +1 @@\n- TODO\n+ TODO: review\n",
            }
        raise ValueError(f"Unknown smoke automation: {automation_id}")


def _base_automation(project_id: str, automation_id: str, name: str, prompt: str) -> dict[str, Any]:
    return {
        "automation_id": automation_id,
        "project_id": project_id,
        "name": name,
        "description": "Deterministic smoke automation for Step 10 release verification.",
        "enabled": True,
        "kind": "standalone",
        "prompt": prompt,
        "schedule": {"mode": "manual", "expression": "", "timezone": "UTC"},
        "runtime": {
            "profile_id": "openai-compatible",
            "model": "gpt-5.5",
            "effort": "high",
            "permission_mode": "read-only",
            "collaboration_mode": None,
            "execution_host": "windows",
            "mcp_preset_ids": [],
        },
        "workspace": {"mode": "current_workspace", "base_branch": None, "cleanup_policy": "manual"},
        "triage": {"archive_no_signal": True, "notify_on": "every_run", "finding_keywords": ["todo", "finding"]},
        "limits": {"timeout_sec": 120, "max_retries": 0, "max_parallel_runs": 1, "max_artifact_bytes": 200000},
    }


def main() -> int:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    output_root = REPO_ROOT / "PRIVATE" / "demo-runs" / f"automation-smoke-{timestamp}"
    project_root = output_root / "workspace-bundle"
    workspace_root = project_root / "workspace"
    project_file = project_root / "automation-smoke.abproj"
    report_path = output_root / "automation-smoke-report.json"
    summary_path = output_root / "automation-smoke-summary.md"
    output_root.mkdir(parents=True, exist_ok=True)

    projects = ProjectService(
        store_path=output_root / "projects.json",
        session_path=output_root / "current_project.json",
    )
    project = projects.create_project(
        "Automation Smoke",
        project_file,
        workspace_root=workspace_root,
        entry_mode="new",
    )
    runtime = _FakeRuntime()
    service = AutomationService(
        projects,
        runtime_service=runtime,
        profile_service=_FakeProfiles(),
        runtime_config=None,
        event_recorder=runtime.record_external_event,
    )
    service._runner = _SmokeRunner()  # noqa: SLF001
    scheduler = service.start()

    created_no_signal = service.create_automation(
        _base_automation(project["project_id"], "auto-no-signal", "No Signal Smoke", "Check workspace and report no-signal.")
    )["automation"]
    created_finding = service.create_automation(
        _base_automation(project["project_id"], "auto-finding", "Finding Smoke", "Check workspace and report finding.")
    )["automation"]

    no_signal_run = service.run_now(created_no_signal["automation_id"])
    finding_run = service.run_now(created_finding["automation_id"])

    finding_item = dict(finding_run.get("inbox_item") or {})
    promoted_item = service.promote_inbox_item(str(finding_item.get("item_id") or ""), "task:automation-smoke")["item"]
    inbox = service.list_inbox_items(include_archived=True)
    runs = service.list_runs()
    runtime_roots = {key: str(value) for key, value in projects.current_runtime_roots().items()}
    shell_state_root = str(projects.require_shell_state_root())

    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "project": {
            "project_id": project["project_id"],
            "project_file": str(project_file),
            "workspace_root": str(workspace_root),
            "shell_state_root": shell_state_root,
            "runtime_roots": runtime_roots,
        },
        "scheduler": scheduler,
        "steps": [
            {"step": "create manual automation", "status": "passed", "automation_id": created_no_signal["automation_id"]},
            {"step": "run-now no-signal", "status": "passed", "run_id": no_signal_run["run"]["run_id"], "signal": no_signal_run["run"]["signal"]},
            {"step": "create second manual automation", "status": "passed", "automation_id": created_finding["automation_id"]},
            {"step": "run-now finding", "status": "passed", "run_id": finding_run["run"]["run_id"], "signal": finding_run["run"]["signal"]},
            {
                "step": "inbox archive/promote",
                "status": "passed",
                "archived_item_id": (no_signal_run.get("inbox_item") or {}).get("item_id"),
                "promoted_item_id": promoted_item.get("item_id"),
                "promotion_ref": promoted_item.get("promotion_ref"),
            },
        ],
        "runs": runs["runs"],
        "inbox": inbox["items"],
        "inbox_summary": service.scheduler_status().get("inbox_summary"),
        "events": runtime.events,
    }
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    lines = [
        "# Automation Smoke Summary",
        "",
        f"- Generated at: `{report['generated_at']}`",
        f"- Project file: `{project_file}`",
        f"- Workspace root: `{workspace_root}`",
        f"- Shell state root: `{shell_state_root}`",
        f"- Runtime root: `{runtime_roots['project_runtime_root']}`",
        "",
        "## Results",
        "",
        f"- Manual automation created: `{created_no_signal['automation_id']}`",
        f"- No-signal run: `{no_signal_run['run']['run_id']}` -> `{no_signal_run['run']['signal']}`",
        f"- Archived inbox item: `{(no_signal_run.get('inbox_item') or {}).get('item_id')}`",
        f"- Finding run: `{finding_run['run']['run_id']}` -> `{finding_run['run']['signal']}`",
        f"- Promoted inbox item: `{promoted_item.get('item_id')}` -> `{promoted_item.get('promotion_ref')}`",
        "",
        "## Artifact Paths",
        "",
        f"- JSON report: `{report_path}`",
        f"- Shell automations index: `{Path(shell_state_root) / 'automations' / 'automations.json'}`",
        f"- Shell run index: `{Path(shell_state_root) / 'automations' / 'runs' / 'index.json'}`",
        f"- Shell inbox index: `{Path(shell_state_root) / 'automations' / 'inbox' / 'index.json'}`",
    ]
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(summary_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
