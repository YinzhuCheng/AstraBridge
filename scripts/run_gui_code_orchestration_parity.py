"""Prove the bounded GUI/code orchestration path without a provider call.

The runner imports the checked-in Code Fix / Test / Review source graph into
an isolated AstraBridge project, captures the GUI-facing task-graph state,
runs deterministic dry-run and fixture paths, exports canonical JSON, and
reimports that JSON. It is intentionally not a live model or code-write run.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
from typing import Any, Iterator


REPO_ROOT = Path(__file__).resolve().parents[1]
SIDECAR_ROOT = REPO_ROOT / "apps" / "astrabridge-sidecar"
SOURCE_GRAPH_PATH = REPO_ROOT / "examples" / "agent-orchestration" / "code_fix_review.json"
SOURCE_GRAPH_RELATIVE_PATH = "workflows/code_fix_review.json"

if str(SIDECAR_ROOT) not in sys.path:
    sys.path.insert(0, str(SIDECAR_ROOT))


def load_parity_source_graph() -> dict[str, Any]:
    payload = json.loads(SOURCE_GRAPH_PATH.read_text(encoding="utf-8"))
    if str(payload.get("graph_id") or "") != "graph_code_fix_review_v1":
        raise ValueError("The GUI/code parity reference must use the checked-in Code Fix / Test / Review graph.")
    if str(payload.get("template_id") or "") != "code_fix_test_review":
        raise ValueError("The GUI/code parity reference must remain bound to code_fix_test_review.")
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


def run_gui_code_orchestration_parity(output_root: str | Path) -> dict[str, Any]:
    """Create a secret-free GUI/code/runtime parity packet in output_root."""

    root = Path(output_root).expanduser().resolve()
    if root.exists() and any(root.iterdir()):
        raise ValueError(f"Refusing to overwrite non-empty evidence root: {root}")
    root.mkdir(parents=True, exist_ok=True)
    source_graph = load_parity_source_graph()

    with isolated_astrabridge_environment(root):
        from astrabridge_sidecar.agent_orchestration_checks import diff_agent_orchestration_graphs
        from astrabridge_sidecar.project_service import ProjectService
        from astrabridge_sidecar.task_service import GraphSourceOwnershipError, TaskService

        workspace = root / "w"
        workspace.mkdir(parents=True, exist_ok=True)
        (workspace / "PRIVATE").mkdir(exist_ok=True)
        (workspace / ".astrabridge").mkdir(exist_ok=True)
        source_copy = workspace / SOURCE_GRAPH_RELATIVE_PATH
        source_copy.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(SOURCE_GRAPH_PATH, source_copy)

        projects = ProjectService(
            store_path=root / "projects.json",
            session_path=root / "current_project.json",
        )
        project_file = workspace / "gui-code-parity.abproj"
        project = projects.create_project(
            "GUI Code Orchestration Parity",
            project_file,
            workspace_root=workspace,
        )
        tasks = TaskService(projects)
        task = tasks.create_task(
            "Inspect the Code Fix / Test / Review workflow from source and GUI",
            thread_id="thread-gui-code-parity",
            settings={
                "profile_id": "qwen-default",
                "provider_id": "qwen",
                "model": "qwen3-coder-plus",
                "reasoning_effort": "high",
                "permission_mode": "ask",
            },
        )

        profiles_snapshot = {
            "profiles": [
                {
                    "profile_id": "qwen-default",
                    "provider_id": "qwen",
                    "model": "qwen3-coder-plus",
                }
            ]
        }
        configured_models = [
            {
                "id": "qwen/qwen3-coder-plus",
                "provider": "qwen",
                "native_model": "qwen3-coder-plus",
            }
        ]
        imported = tasks.import_graph_from_orchestration_file(
            {"graph_path": SOURCE_GRAPH_RELATIVE_PATH},
            profiles_snapshot=profiles_snapshot,
            configured_models=configured_models,
        )
        imported_graph = dict(imported.get("graph") or {})
        imported_orchestration = dict(imported.get("orchestration_graph") or {})
        graph_id = str(imported_graph.get("graph_id") or "")
        _require(graph_id, "The imported graph has no graph_id.")
        _require(
            _semantic_projection(source_graph) == _semantic_projection(imported_orchestration),
            "Code source semantics changed while importing into the task graph.",
        )

        source_ownership = dict(dict(imported_graph.get("graph_document") or {}).get("source_ownership") or {})
        _require(
            str(source_ownership.get("ownership_mode") or "") == "source_owned",
            "Code import did not preserve source ownership.",
        )
        blocked_gui_edit = _capture_blocked_gui_edit(
            tasks,
            graph=imported_graph,
            graph_id=graph_id,
            error_type=GraphSourceOwnershipError,
        )
        _require(
            blocked_gui_edit["error"] == "graph_source_owned",
            "A source-owned graph did not reject the direct GUI edit.",
        )

        dry_run = dict(
            tasks.dry_run_graph(
                {"graph_id": graph_id},
                profiles_snapshot=profiles_snapshot,
                configured_models=configured_models,
            ).get("dry_run")
            or {}
        )
        _require(str(dry_run.get("overall_status") or "") == "pass", "Parity dry-run did not pass.")

        fixture_run = dict(
            tasks.execute_fixture_graph({"graph_id": graph_id}).get("fixture_run")
            or {}
        )
        _require(
            str(fixture_run.get("run_status") or "") == "completed",
            "Parity fixture run did not complete.",
        )

        exported = tasks.export_graph_for_orchestration_file(
            {
                "graph_id": graph_id,
                "export_path": "exports/code_fix_review.exported.json",
            }
        )
        exported_orchestration = dict(exported.get("orchestration_graph") or {})
        _require(
            _semantic_projection(imported_orchestration) == _semantic_projection(exported_orchestration),
            "GUI task-graph export changed canonical source semantics.",
        )

        reimported = tasks.import_graph_from_orchestration_file(
            {
                "graph_text": str(exported.get("serialized_text") or ""),
                **_expected_revision_payload(imported_graph),
            },
            profiles_snapshot=profiles_snapshot,
            configured_models=configured_models,
        )
        reexported = tasks.export_graph_for_orchestration_file(
            {"graph_id": str(dict(reimported.get("graph") or {}).get("graph_id") or "")}
        )
        round_trip_diff = diff_agent_orchestration_graphs(
            imported_orchestration,
            dict(reexported.get("orchestration_graph") or {}),
        )
        _require(
            str(round_trip_diff.get("status") or "") == "no_change",
            "The source -> GUI -> export -> reimport round trip changed canonical semantics.",
        )

        gui_surface = _gui_surface(imported_graph)
        _require(
            gui_surface["node_labels"] == ["Plan Fix", "Apply Code Fix", "Run Tests", "Review Result"],
            "The GUI surface lost a reference node.",
        )
        _require(
            gui_surface["edge_ids"] == ["edge_fix_review", "edge_fix_test", "edge_plan_fix"],
            "The GUI surface lost a reference edge.",
        )
        permission_boundary = _permission_boundary(imported_orchestration)
        _require(
            permission_boundary["requires_human_approval"] is True
            and permission_boundary["approval_kind"] == "filesystem_write_gate",
            "The code-fix permission boundary is not preserved.",
        )

        _write_json(root / "source-graph.json", source_graph)
        _write_json(root / "runtime-orchestration-manifest.json", imported_orchestration)
        _write_json(root / "gui-surface.json", gui_surface)
        _write_json(root / "round-trip-diff.json", round_trip_diff)

        evidence = {
            "schema_version": "astrabridge-gui-code-orchestration-parity-evidence-v1",
            "mode": "deterministic_provider_free",
            "provider_calls": [],
            "network_calls_attempted": False,
            "reference": {
                "source_graph": "examples/agent-orchestration/code_fix_review.json",
                "graph_id": str(source_graph.get("graph_id") or ""),
                "template_id": str(source_graph.get("template_id") or ""),
                "source_path_in_project": SOURCE_GRAPH_RELATIVE_PATH,
            },
            "project": {
                "project_file": "w/gui-code-parity.abproj",
                "isolated_project_created": bool(project.get("project_id")),
                "isolated_task_created": bool(task.get("task_id")),
                "task_title": task.get("title"),
            },
            "code_to_gui": {
                "status": "pass",
                "semantic_projection_matches": True,
                "source_ownership": _compact_source_ownership(source_ownership),
                "gui_surface": gui_surface,
            },
            "runtime": {
                "dry_run_status": dry_run.get("overall_status"),
                "fixture_run_status": fixture_run.get("run_status"),
                "fixture_run_created": bool(fixture_run.get("run_id")),
                "fixture_artifact_kinds": sorted(
                    str(key)
                    for key in dict(fixture_run.get("artifact_paths") or {})
                ),
            },
            "authority_boundary": {
                "permission_boundary": permission_boundary,
                "blocked_gui_edit": blocked_gui_edit,
                "supported_detach_action": "source_owner_action=detach creates a detached GUI copy; it does not write back to the source file.",
            },
            "gui_to_code": {
                "status": "pass",
                "export_path": str(exported.get("export_path") or ""),
                "round_trip_diff_status": round_trip_diff.get("status"),
                "round_trip_change_count": dict(round_trip_diff.get("summary") or {}).get("change_count"),
            },
            "claim_boundary": {
                "proved": "One canonical native JSON graph can be imported into the GUI task graph, rendered as declared nodes and edges, dry-run and fixture-run without a provider call, exported, reimported, and compared with no canonical semantic change.",
                "not_proved": [
                    "live provider behavior",
                    "autonomous code writes",
                    "tool authority",
                    "lossless conversion for every GUI graph or external workflow format",
                    "write-back from a source-owned GUI graph to its source file",
                ],
            },
            "artifact_paths": {
                "source_graph": "source-graph.json",
                "runtime_orchestration_manifest": "runtime-orchestration-manifest.json",
                "gui_surface": "gui-surface.json",
                "round_trip_diff": "round-trip-diff.json",
                "evidence_json": "evidence.json",
                "evidence_markdown": "evidence.md",
            },
        }
        _write_json(root / "evidence.json", evidence)
        (root / "evidence.md").write_text(
            _render_evidence_markdown(evidence),
            encoding="utf-8",
            newline="\n",
        )
        return evidence


def _capture_blocked_gui_edit(
    tasks: Any,
    *,
    graph: dict[str, Any],
    graph_id: str,
    error_type: type[Exception],
) -> dict[str, Any]:
    try:
        tasks.update_graph_node(
            {
                "graph_id": graph_id,
                "node_id": "node_apply_fix",
                **_expected_revision_payload(graph),
                "configuration": {"label": "Direct GUI edit must be blocked"},
            }
        )
    except error_type as exc:
        payload = dict(getattr(exc, "payload", {}) or {})
        return {
            "status": "blocked_as_expected",
            "error": str(payload.get("error") or ""),
            "action": str(payload.get("action") or ""),
            "ownership_mode": str(dict(payload.get("source_ownership") or {}).get("ownership_mode") or ""),
        }
    raise AssertionError("A source-owned graph accepted a direct GUI edit.")


def _expected_revision_payload(graph: dict[str, Any]) -> dict[str, str]:
    revision = dict(graph.get("graph_revision") or {})
    return {"expected_revision": str(revision.get("revision_id") or "")}


def _semantic_projection(graph: dict[str, Any]) -> dict[str, Any]:
    def node_projection(node: dict[str, Any]) -> dict[str, Any]:
        return {
            field: deepcopy(node.get(field))
            for field in (
                "node_id",
                "kind",
                "label",
                "role",
                "card_ref",
                "routing",
                "prompt",
                "tools",
                "ports",
                "input_contract",
                "output_contract",
                "execution",
                "safety",
                "ui",
                "status",
            )
        }

    def edge_projection(edge: dict[str, Any]) -> dict[str, Any]:
        return {
            field: deepcopy(edge.get(field))
            for field in (
                "edge_id",
                "from_node_id",
                "to_node_id",
                "edge_type",
                "handoff_contract",
                "context_policy",
                "ui",
                "status",
            )
        }

    return {
        "schema_version": graph.get("schema_version"),
        "graph_id": graph.get("graph_id"),
        "title": graph.get("title"),
        "template_id": graph.get("template_id"),
        "status": graph.get("status"),
        "graph_policy": deepcopy(graph.get("graph_policy")),
        "nodes": sorted(
            [node_projection(dict(node)) for node in list(graph.get("nodes") or []) if isinstance(node, dict)],
            key=lambda item: str(item.get("node_id") or ""),
        ),
        "edges": sorted(
            [edge_projection(dict(edge)) for edge in list(graph.get("edges") or []) if isinstance(edge, dict)],
            key=lambda item: str(item.get("edge_id") or ""),
        ),
        "schema_registry": deepcopy(graph.get("schema_registry")),
    }


def _gui_surface(task_graph: dict[str, Any]) -> dict[str, Any]:
    nodes = [
        {
            "node_id": str(node.get("node_id") or ""),
            "label": str(node.get("label") or ""),
            "kind": str(node.get("kind") or ""),
            "position": dict(node.get("position") or {}),
        }
        for node in list(task_graph.get("nodes") or [])
        if isinstance(node, dict)
    ]
    edges = [
        {
            "edge_id": str(edge.get("edge_id") or ""),
            "from_node_id": str(edge.get("from_node_id") or ""),
            "to_node_id": str(edge.get("to_node_id") or ""),
        }
        for edge in list(task_graph.get("edges") or [])
        if isinstance(edge, dict)
    ]
    return {
        "graph_id": str(task_graph.get("graph_id") or ""),
        "title": str(task_graph.get("title") or ""),
        "template_id": str(task_graph.get("template_id") or ""),
        "node_count": len(nodes),
        "edge_count": len(edges),
        "node_labels": [item["label"] for item in nodes],
        "edge_ids": sorted(item["edge_id"] for item in edges),
        "nodes": nodes,
        "edges": edges,
        "source_ownership": _compact_source_ownership(
            dict(dict(task_graph.get("graph_document") or {}).get("source_ownership") or {})
        ),
    }


def _permission_boundary(orchestration_graph: dict[str, Any]) -> dict[str, Any]:
    code_fix = next(
        (
            dict(node)
            for node in list(orchestration_graph.get("nodes") or [])
            if isinstance(node, dict) and str(node.get("node_id") or "") == "node_apply_fix"
        ),
        {},
    )
    safety = dict(code_fix.get("safety") or {})
    tools = dict(code_fix.get("tools") or {})
    return {
        "node_id": str(code_fix.get("node_id") or ""),
        "label": str(code_fix.get("label") or ""),
        "requires_human_approval": bool(safety.get("requires_human_approval")),
        "approval_kind": str(safety.get("approval_kind") or ""),
        "allow_code_changes": bool(safety.get("allow_code_changes")),
        "approval_mode": str(tools.get("approval_mode") or ""),
    }


def _compact_source_ownership(source_ownership: dict[str, Any]) -> dict[str, Any]:
    source_file = dict(source_ownership.get("source_file") or {})
    return {
        "ownership_mode": str(source_ownership.get("ownership_mode") or ""),
        "can_write_from_gui": bool(source_ownership.get("can_write_from_gui")),
        "source_path": str(source_ownership.get("source_path") or ""),
        "source_file_path": str(source_file.get("path") or ""),
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _render_evidence_markdown(evidence: dict[str, Any]) -> str:
    code_to_gui = dict(evidence.get("code_to_gui") or {})
    runtime = dict(evidence.get("runtime") or {})
    gui_to_code = dict(evidence.get("gui_to_code") or {})
    authority = dict(evidence.get("authority_boundary") or {})
    return "\n".join(
        [
            "# GUI / Code Orchestration Parity Evidence",
            "",
            f"- Mode: {evidence.get('mode')}",
            f"- Source graph: {dict(evidence.get('reference') or {}).get('source_graph')}",
            f"- Code to GUI: {code_to_gui.get('status')}",
            f"- Dry run: {runtime.get('dry_run_status')}",
            f"- Fixture run: {runtime.get('fixture_run_status')}",
            f"- Direct GUI edit: {dict(authority.get('blocked_gui_edit') or {}).get('status')}",
            f"- GUI to code round trip: {gui_to_code.get('round_trip_diff_status')}",
            "",
            "The run made no network or provider call. Source-owned GUI graphs stay read-only until an explicit detach creates a separate GUI copy.",
            "",
        ]
    )


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the deterministic GUI/code orchestration parity reference.")
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    evidence = run_gui_code_orchestration_parity(args.output_root)
    print(
        {
            "code_to_gui": dict(evidence["code_to_gui"]).get("status"),
            "dry_run": dict(evidence["runtime"]).get("dry_run_status"),
            "fixture_run": dict(evidence["runtime"]).get("fixture_run_status"),
            "round_trip": dict(evidence["gui_to_code"]).get("round_trip_diff_status"),
            "evidence": str(Path(args.output_root).resolve() / "evidence.json"),
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
