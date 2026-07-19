from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SHELL_MODULE_BUDGET_AUDIT_SCHEMA_VERSION = "astrabridge-shell-module-budget-audit-v1"
TARGET_SHELL_MODULES: tuple[dict[str, Any], ...] = (
    {
        "module_id": "sidecar_runtime_service",
        "path": "apps/astrabridge-sidecar/astrabridge_sidecar/runtime_service.py",
        "max_lines": 15850,
        "owner_focus": "runtime dispatch, cancellation, and runtime client lifecycle should stay delegated behind bounded owners while runtime_service.py remains the shell-level composition surface",
        "responsible_owners": (
            "apps/astrabridge-sidecar/astrabridge_sidecar/runtime_graph_run_dispatch_service.py",
            "apps/astrabridge-sidecar/astrabridge_sidecar/runtime_client_pool.py",
            "apps/astrabridge-sidecar/astrabridge_sidecar/mcp_broker_service.py",
        ),
    },
    {
        "module_id": "sidecar_task_service",
        "path": "apps/astrabridge-sidecar/astrabridge_sidecar/task_service.py",
        "max_lines": 10850,
        "owner_focus": "graph authoring, orchestration documents, and task persistence should stay delegated behind bounded owners while task_service.py remains the shell-level task API surface",
        "responsible_owners": (
            "apps/astrabridge-sidecar/astrabridge_sidecar/task_graph_mutation_service.py",
            "apps/astrabridge-sidecar/astrabridge_sidecar/task_graph_run_ref_service.py",
            "apps/astrabridge-sidecar/astrabridge_sidecar/agent_orchestration_file_format.py",
        ),
    },
    {
        "module_id": "desktop_app_shell",
        "path": "apps/astrabridge-desktop/src/App.tsx",
        "max_lines": 12100,
        "owner_focus": "top-level shell composition should stay in App while runtime, navigation, and update flows remain delegated to feature owners",
        "responsible_owners": (
            "apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.tsx",
            "apps/astrabridge-desktop/src/features/runtime/taskGraphAppState.ts",
            "apps/astrabridge-desktop/src/features/runtime/taskGraphRunDispatch.ts",
            "apps/astrabridge-desktop/src/features/navigation/ProjectTaskTree.tsx",
        ),
    },
    {
        "module_id": "desktop_task_graph_workspace",
        "path": "apps/astrabridge-desktop/src/features/runtime/TaskGraphWorkspace.tsx",
        "max_lines": 8700,
        "owner_focus": "task-graph canvas and inspector composition should remain in TaskGraphWorkspace while chrome state, persistence, and focused rendering helpers stay delegated behind runtime feature owners",
        "responsible_owners": (
            "apps/astrabridge-desktop/src/features/runtime/useTaskGraphWorkspaceChromeState.ts",
            "apps/astrabridge-desktop/src/features/runtime/taskGraphWorkspacePersistence.ts",
            "apps/astrabridge-desktop/src/features/runtime/TaskGraphSchemaForm.tsx",
            "apps/astrabridge-desktop/src/features/runtime/TaskGraphInspectorModal.tsx",
            "apps/astrabridge-desktop/src/features/runtime/taskGraphViewportCulling.ts",
        ),
    },
)


def _count_lines(path: Path) -> int:
    return len(path.read_text(encoding="utf-8", errors="replace").splitlines())


def audit_shell_module_budgets() -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    errors: list[str] = []
    for target in TARGET_SHELL_MODULES:
        relative_path = Path(str(target["path"]))
        path = REPO_ROOT / relative_path
        max_lines = int(target["max_lines"])
        if not path.exists():
            status = "fail"
            line_count = None
            message = "shell module path does not exist"
            errors.append(f"{target['module_id']}: expected path missing: {relative_path}")
        else:
            line_count = _count_lines(path)
            status = "pass" if line_count <= max_lines else "fail"
            message = (
                f"line budget ok ({line_count} <= {max_lines})"
                if status == "pass"
                else f"line budget exceeded ({line_count} > {max_lines})"
            )
            if status != "pass":
                errors.append(f"{target['module_id']}: {message}")
        checks.append(
            {
                "module_id": str(target["module_id"]),
                "path": str(relative_path).replace("\\", "/"),
                "status": status,
                "line_count": line_count,
                "max_lines": max_lines,
                "budget_headroom": None if line_count is None else max_lines - int(line_count),
                "owner_focus": str(target["owner_focus"]),
                "responsible_owners": [
                    str(Path(owner)).replace("\\", "/")
                    for owner in target.get("responsible_owners", ())
                ],
                "message": message,
            }
        )
    status = "pass" if not errors else "fail"
    return {
        "schema_version": SHELL_MODULE_BUDGET_AUDIT_SCHEMA_VERSION,
        "status": status,
        "summary": {
            "check_count": len(checks),
            "error_count": len(errors),
        },
        "checks": checks,
        "errors": errors,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit line-budget guardrails for remaining AstraBridge shell modules.")
    parser.parse_args(argv)
    report = audit_shell_module_budgets()
    json.dump(report, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0 if str(report.get("status") or "") == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
