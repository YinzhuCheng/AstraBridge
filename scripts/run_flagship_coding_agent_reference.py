"""Run AstraBridge's deterministic flagship coding-agent reference workflow.

The runner is deliberately no-key and no-provider. It creates an isolated
abproj workspace, exercises the Code Fix / Test / Review graph through
dry-run, failure, and recovery paths, and emits a portable evidence packet.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator


REPO_ROOT = Path(__file__).resolve().parents[1]
SIDECAR_ROOT = REPO_ROOT / "apps" / "astrabridge-sidecar"
REFERENCE_ROOT = REPO_ROOT / "examples" / "flagship-coding-agent-reference"
SCENARIO_PATH = REFERENCE_ROOT / "flagship-coding-agent-reference.json"

if str(SIDECAR_ROOT) not in sys.path:
    sys.path.insert(0, str(SIDECAR_ROOT))


def load_reference_scenario() -> dict[str, Any]:
    payload = json.loads(SCENARIO_PATH.read_text(encoding="utf-8"))
    if str(payload.get("schema_version") or "") != "astrabridge-flagship-coding-agent-reference-v1":
        raise ValueError("Unsupported flagship coding-agent reference schema.")
    if str(payload.get("template_id") or "") != "code_fix_test_review":
        raise ValueError("The flagship reference must remain bound to code_fix_test_review.")
    return payload


@contextmanager
def isolated_astrabridge_environment(root: Path) -> Iterator[None]:
    values = {
        "ASTRABRIDGE_APPDATA": str(root / "appdata"),
        "ASTRABRIDGE_RUNTIME_ROOT": str(root / "runtime"),
        "ASTRABRIDGE_CODEX_HOME": str(root / "codex-home"),
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    previous = {key: os.environ.get(key) for key in values}
    try:
        for path in (root / "appdata", root / "runtime", root / "codex-home"):
            path.mkdir(parents=True, exist_ok=True)
        os.environ.update(values)
        yield
    finally:
        for key, old_value in previous.items():
            if old_value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old_value


def run_flagship_reference(output_root: str | Path) -> dict[str, Any]:
    root = Path(output_root).expanduser().resolve()
    if root.exists() and any(root.iterdir()):
        raise ValueError(f"Refusing to overwrite non-empty evidence root: {root}")
    root.mkdir(parents=True, exist_ok=True)
    scenario = load_reference_scenario()

    with isolated_astrabridge_environment(root):
        # Import after setting all product-state roots. Importing the sidecar
        # earlier can load a pre-existing user catalog before this reference
        # has established its no-key isolation boundary.
        from astrabridge_sidecar.project_service import ProjectService
        from astrabridge_sidecar.task_service import TaskService

        seed_evidence = _exercise_seed_project(root, scenario)
        # Keep the task-graph artifact root short. Fixture worker paths include
        # graph/run/node identifiers and must remain below Windows path limits
        # even when the caller preserves evidence beneath a deep project path.
        workspace = root / "w"
        workspace.mkdir(parents=True, exist_ok=True)
        (workspace / "PRIVATE").mkdir(exist_ok=True)
        (workspace / ".astrabridge").mkdir(exist_ok=True)

        projects = ProjectService(
            store_path=root / "projects.json",
            session_path=root / "current_project.json",
        )
        project_file = workspace / "flagship-coding-agent-reference.abproj"
        project = projects.create_project(
            str(dict(scenario.get("task") or {}).get("project_name") or "Flagship Coding Agent Reference"),
            project_file,
            workspace_root=workspace,
        )
        tasks = TaskService(projects)
        task = tasks.create_task(
            str(dict(scenario.get("task") or {}).get("title") or "Bounded coding-agent reference"),
            thread_id="thread-flagship-coding-reference",
            settings={
                "profile_id": "qwen-default",
                "provider_id": "qwen",
                "model": "qwen3-coder-plus",
                "reasoning_effort": "high",
                "permission_mode": "ask",
            },
        )
        graph = tasks.instantiate_graph_template(
            str(scenario["template_id"]),
            title=str(scenario.get("title") or "Flagship Coding Agent Reference"),
        )["graph"]
        graph_id = str(graph["graph_id"])
        permission_boundary = _permission_boundary(graph, scenario)

        route_snapshot = dict(scenario.get("route_snapshot") or {})
        profiles_snapshot = {
            "profiles": [
                dict(item)
                for item in list(route_snapshot.get("profiles") or [])
                if isinstance(item, dict)
            ]
        }
        configured_models = [
            dict(item)
            for item in list(route_snapshot.get("models") or [])
            if isinstance(item, dict)
        ]
        dry_run = dict(
            tasks.dry_run_graph(
                {"graph_id": graph_id},
                profiles_snapshot=profiles_snapshot,
                configured_models=configured_models,
            ).get("dry_run")
            or {}
        )
        expected_statuses = dict(dict(scenario.get("fixture") or {}).get("expected_statuses") or {})
        _require(str(dry_run.get("overall_status") or "") == str(expected_statuses.get("dry_run") or ""), "Flagship dry-run did not pass.")

        exported = tasks.export_graph_for_orchestration_file(
            {
                "graph_id": graph_id,
                "export_path": "PRIVATE/flagship-coding-agent-reference/code-fix-test-review.json",
            }
        )

        failure_spec = dict(dict(scenario.get("fixture") or {}).get("failure_injection") or {})
        failed = dict(
            tasks.execute_fixture_graph(
                {
                    "graph_id": graph_id,
                    "node_behaviors": {str(failure_spec["node_id"]): str(failure_spec["behavior"])},
                }
            ).get("fixture_run")
            or {}
        )
        failed_run = dict(failed.get("run_ref") or {})
        _require(str(failed.get("run_status") or "") == str(expected_statuses.get("failure") or ""), "Flagship failure exercise did not fail.")

        recovery_spec = dict(dict(scenario.get("fixture") or {}).get("recovery") or {})
        recovered = tasks.recover_graph_run(
            {
                "run_id": str(failed["run_id"]),
                "strategy": str(recovery_spec["strategy"]),
                "node_behaviors": dict(recovery_spec.get("node_behaviors") or {}),
            }
        )
        recovered_fixture = dict(recovered.get("fixture_run") or {})
        recovered_run = dict(recovered_fixture.get("run_ref") or {})
        _require(
            str(recovered_run.get("status") or "") == str(expected_statuses.get("recovery") or ""),
            "Flagship recovery did not complete.",
        )

        evidence = {
            "schema_version": "astrabridge-flagship-coding-agent-evidence-v1",
            "reference": {
                "reference_id": scenario["reference_id"],
                "title": scenario["title"],
                "template_id": scenario["template_id"],
                "execution_mode": scenario["execution_mode"],
            },
            "claims": dict(scenario.get("claims") or {}),
            "owners": dict(scenario.get("visible_boundaries") or {}),
            "provider_calls": [],
            "declared_route_snapshot": {
                "profile_ids": [
                    str(item.get("profile_id") or "")
                    for item in profiles_snapshot["profiles"]
                ],
                "model_ids": [
                    str(item.get("id") or "")
                    for item in configured_models
                ],
            },
            "project": {
                "project_id": project.get("project_id"),
                "project_file": "w/flagship-coding-agent-reference.abproj",
                "workspace_root": "w",
                "task_id": task.get("task_id"),
                "task_title": task.get("title"),
                "task_status": task.get("status"),
            },
            "graph": {
                "graph_id": graph_id,
                "template_id": graph.get("template_id"),
                "title": graph.get("title"),
                "node_count": len(list(graph.get("nodes") or [])),
                "edge_count": len(list(graph.get("edges") or [])),
                "export_path": str(exported.get("export_path") or ""),
            },
            "permission_boundary": permission_boundary,
            "seed_project": seed_evidence,
            "dry_run": {
                "status": dry_run.get("overall_status"),
                "run_status": dry_run.get("run_status"),
                "artifact_paths": dict(dry_run.get("artifact_paths") or {}),
            },
            "failure_exercise": {
                "run_id": failed.get("run_id"),
                "status": failed.get("run_status"),
                "failed_node_id": failure_spec.get("node_id"),
                "blocked_node_ids": _binding_ids_with_status(failed_run, "blocked"),
                "artifact_paths": dict(failed.get("artifact_paths") or {}),
            },
            "recovery_exercise": {
                "run_id": recovered_run.get("run_id"),
                "status": recovered_run.get("status"),
                "strategy": str(dict(recovered_run.get("policy_snapshot") or {}).get("recovery", {}).get("strategy") or ""),
                "rerun_node_ids": list(dict(recovered.get("recovery") or {}).get("rerun_node_ids") or []),
                "reused_node_ids": list(dict(recovered.get("recovery") or {}).get("reused_node_ids") or []),
                "artifact_paths": dict(dict(recovered.get("recovery") or {}).get("artifact_paths") or {}),
            },
        }
        evidence["artifact_packet"] = {
            "evidence_json": "evidence.json",
            "evidence_markdown": "evidence.md",
            "exported_orchestration_graph": str(exported.get("export_path") or ""),
            "failed_run_manifest": str(dict(failed.get("artifact_paths") or {}).get("run_manifest_json") or ""),
            "recovery_manifest": str(dict(dict(recovered.get("recovery") or {}).get("artifact_paths") or {}).get("manifest_json") or ""),
        }
        _write_json(root / "evidence.json", evidence)
        (root / "evidence.md").write_text(_render_evidence_markdown(evidence), encoding="utf-8", newline="\n")
        return evidence


def _exercise_seed_project(root: Path, scenario: dict[str, Any]) -> dict[str, Any]:
    task = dict(scenario.get("task") or {})
    before_source = REPO_ROOT / str(task["seed_project"])
    expected_source = REFERENCE_ROOT / "expected" / "task_title.py"
    expected_patch = REPO_ROOT / str(task["expected_patch"])
    before_root = root / "seed-project-before"
    recovered_root = root / "seed-project-recovered"
    shutil.copytree(before_source, before_root)
    before_check = _run_seed_check(before_root)
    _require(before_check["exit_code"] != 0, "The intentionally incomplete seed project unexpectedly passed.")
    shutil.copytree(before_source, recovered_root)
    shutil.copy2(expected_source, recovered_root / "task_title.py")
    recovered_check = _run_seed_check(recovered_root)
    _require(recovered_check["exit_code"] == 0, "The expected bounded seed fix did not pass its check.")
    copied_patch = root / "expected-task-title.patch"
    shutil.copy2(expected_patch, copied_patch)
    return {
        "task_context": task.get("task_context"),
        "expected_test_command": task.get("expected_test_command"),
        "before_check": before_check,
        "recovered_check": recovered_check,
        "before_root": "seed-project-before",
        "recovered_root": "seed-project-recovered",
        "expected_patch": copied_patch.name,
    }


def _run_seed_check(project_root: Path) -> dict[str, Any]:
    completed = subprocess.run(
        [sys.executable, "task_title_checks.py"],
        cwd=project_root,
        text=True,
        capture_output=True,
        check=False,
    )
    return {
        "command": "python task_title_checks.py",
        "exit_code": completed.returncode,
        "stdout": _trim_output(completed.stdout),
        "stderr": _trim_output(completed.stderr),
    }


def _permission_boundary(graph: dict[str, Any], scenario: dict[str, Any]) -> dict[str, Any]:
    node = next(
        (
            dict(item)
            for item in list(graph.get("nodes") or [])
            if isinstance(item, dict) and str(item.get("node_id") or "") == "node_code_fix"
        ),
        None,
    )
    if not node:
        raise ValueError("Code Fix / Test / Review graph is missing node_code_fix.")
    policy = dict(node.get("execution_policy") or {})
    gate = dict(node.get("approval_gate") or {})
    _require(bool(policy.get("requires_human_approval")), "Flagship code-fix node is not approval-gated.")
    _require(str(gate.get("review_kind") or "") == "filesystem_write_gate", "Flagship code-fix node does not declare filesystem_write_gate.")
    return {
        "owner": str(dict(scenario.get("visible_boundaries") or {}).get("permission_boundary", {}).get("owner") or ""),
        "node_id": node.get("node_id"),
        "label": node.get("label"),
        "requires_human_approval": True,
        "approval_kind": gate.get("review_kind"),
        "allow_code_changes": bool(policy.get("allow_code_changes")),
        "fixture_behavior": "No provider-backed write is performed; the reference only records the declared approval boundary.",
    }


def _binding_ids_with_status(run_ref: dict[str, Any], status: str) -> list[str]:
    return [
        str(binding.get("node_id") or "")
        for binding in list(run_ref.get("worker_bindings") or [])
        if isinstance(binding, dict) and str(binding.get("status") or "") == status
    ]


def _trim_output(value: str, *, limit: int = 1200) -> str:
    compact = value.strip()
    return compact if len(compact) <= limit else f"{compact[:limit]}…"


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def _render_evidence_markdown(evidence: dict[str, Any]) -> str:
    graph = dict(evidence.get("graph") or {})
    permission = dict(evidence.get("permission_boundary") or {})
    failure = dict(evidence.get("failure_exercise") or {})
    recovery = dict(evidence.get("recovery_exercise") or {})
    seed = dict(evidence.get("seed_project") or {})
    reference = dict(evidence.get("reference") or {})
    return "\n".join(
        [
            "# AstraBridge Flagship Coding-Agent Reference Evidence",
            "",
            f"Reference: {reference.get('reference_id')}",
            f"Template: {graph.get('template_id')} ({graph.get('node_count')} nodes / {graph.get('edge_count')} edges)",
            f"Provider calls: {len(list(evidence.get('provider_calls') or []))}",
            "",
            "## Visible Boundaries",
            "",
            f"Permission: {permission.get('approval_kind')} on {permission.get('node_id')}; human approval required: {permission.get('requires_human_approval')}.",
            f"Seed project check: before exit {dict(seed.get('before_check') or {}).get('exit_code')}, recovered exit {dict(seed.get('recovered_check') or {}).get('exit_code')}.",
            f"Dry-run: {dict(evidence.get('dry_run') or {}).get('status')}.",
            f"Failure exercise: {failure.get('status')}; blocked nodes: {', '.join(list(failure.get('blocked_node_ids') or []))}.",
            f"Recovery exercise: {recovery.get('status')} using {recovery.get('strategy')}; rerun nodes: {', '.join(list(recovery.get('rerun_node_ids') or []))}.",
            "",
            "## Limits",
            "",
            "This packet proves deterministic no-provider workflow structure, artifacts, and recovery. It does not prove a live provider response, autonomous write authority, or release-installer behavior.",
            "",
        ]
    )


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", required=True, help="Empty directory that will receive the isolated reference workspace and evidence packet.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    evidence = run_flagship_reference(args.output_root)
    print(json.dumps(evidence, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
