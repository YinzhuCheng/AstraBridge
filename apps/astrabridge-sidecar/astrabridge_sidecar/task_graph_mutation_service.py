from __future__ import annotations

import json
import os
import re
from copy import deepcopy
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .agent_orchestration_checks import build_known_model_capabilities, diff_agent_orchestration_graphs
from .agent_orchestration_compiler import compile_agent_orchestration_graph
from .agent_orchestration_file_format import (
    parse_agent_orchestration_graph_text,
    serialize_agent_orchestration_graph,
    write_agent_orchestration_graph_file,
)
from .comfyui_workflow_adapter import (
    COMFYUI_WORKFLOW_SOURCE_FORMAT,
    export_comfyui_workflow,
    import_comfyui_workflow,
    looks_like_comfyui_workflow,
)
from .langgraph_stategraph_adapter import (
    LANGGRAPH_STATEGRAPH_SOURCE_FORMAT,
    export_langgraph_stategraph_manifest,
    import_langgraph_stategraph_manifest,
    looks_like_langgraph_stategraph_manifest,
)
from .model_catalog.catalog import provider_model_records
from .common import new_id, now_iso, write_json
from .security import resolve_under
from .task_graph_contract import load_task_graph_fixture, validate_graph_definition

if TYPE_CHECKING:
    from .task_service import TaskService


class TaskGraphMutationService:
    """Own task-graph mutation and import/export transforms behind TaskService."""

    def __init__(self, task_service: "TaskService") -> None:
        self._tasks = task_service

    def export_graph_for_orchestration_file(self, payload: dict[str, Any]) -> dict[str, Any]:
        from .task_service import AGENT_ORCHESTRATION_GRAPH_SOURCE_FORMAT

        task = self._tasks.current_task()
        if not task:
            raise ValueError("No current task.")
        if not isinstance(payload, dict):
            raise TypeError("Graph export payload must be a dict.")
        graph_id = str(payload.get("graph_id") or "").strip()
        if not graph_id:
            raise ValueError("graph_id is required.")
        graph = self._tasks.graph_definition(graph_id)
        if not graph:
            raise ValueError("Graph not found.")
        validated_graph = validate_graph_definition(graph)
        orchestration_graph = self._tasks._orchestration_graph_for_task_graph(validated_graph)  # noqa: SLF001
        requested_format = str(payload.get("format") or "").strip()
        source_format = self._graph_interop_source_format(validated_graph)
        export_format = requested_format or source_format
        if export_format not in {
            AGENT_ORCHESTRATION_GRAPH_SOURCE_FORMAT,
            COMFYUI_WORKFLOW_SOURCE_FORMAT,
            LANGGRAPH_STATEGRAPH_SOURCE_FORMAT,
        }:
            raise ValueError(
                "Unsupported graph export format. Expected one of: "
                f"{AGENT_ORCHESTRATION_GRAPH_SOURCE_FORMAT}, {COMFYUI_WORKFLOW_SOURCE_FORMAT}, "
                f"{LANGGRAPH_STATEGRAPH_SOURCE_FORMAT}."
            )
        adapter_manifest: dict[str, Any] | None = None
        loss_report: dict[str, Any] | None = None
        source_version: str | None = None
        serialized = ""
        generated_python: str | None = None
        export_path_text = str(payload.get("export_path") or "").strip()
        generated_python_path_text = str(payload.get("generated_python_path") or "").strip()
        workspace_root = self._tasks._projects.require_workspace_root()  # noqa: SLF001
        written_relative_path: str | None = None
        if export_format == COMFYUI_WORKFLOW_SOURCE_FORMAT:
            exported = export_comfyui_workflow(orchestration_graph, task_graph=validated_graph)
            serialized = str(exported.get("serialized_text") or "")
            adapter_manifest = deepcopy(exported.get("adapter_manifest") or None)
            loss_report = deepcopy(exported.get("loss_report") or None)
            source_version = str(exported.get("source_version") or "").strip() or None
            if export_path_text:
                target_path = resolve_under(workspace_root, export_path_text)
                target_path.parent.mkdir(parents=True, exist_ok=True)
                target_path.write_text(serialized, encoding="utf-8")
                written_relative_path = target_path.relative_to(workspace_root).as_posix()
        elif export_format == LANGGRAPH_STATEGRAPH_SOURCE_FORMAT:
            exported = export_langgraph_stategraph_manifest(
                orchestration_graph,
                task_graph=validated_graph,
                emit_generated_python=bool(payload.get("emit_generated_python", True)),
            )
            serialized = str(exported.get("serialized_text") or "")
            generated_python = str(exported.get("generated_python") or "").strip() or None
            adapter_manifest = deepcopy(exported.get("adapter_manifest") or None)
            loss_report = deepcopy(exported.get("loss_report") or None)
            source_version = str(exported.get("source_version") or "").strip() or None
            if export_path_text:
                target_path = resolve_under(workspace_root, export_path_text)
                target_path.parent.mkdir(parents=True, exist_ok=True)
                target_path.write_text(serialized, encoding="utf-8")
                written_relative_path = target_path.relative_to(workspace_root).as_posix()
            if generated_python and generated_python_path_text:
                python_target_path = resolve_under(workspace_root, generated_python_path_text)
                python_target_path.parent.mkdir(parents=True, exist_ok=True)
                python_target_path.write_text(generated_python, encoding="utf-8")
        else:
            serialized = serialize_agent_orchestration_graph(orchestration_graph)
            if export_path_text:
                written = write_agent_orchestration_graph_file(resolve_under(workspace_root, export_path_text), orchestration_graph)
                written_relative_path = written.relative_to(workspace_root).as_posix()
        return {
            "schema_version": "astrabridge-agent-orchestration-export-v1",
            "graph": validated_graph,
            "task": self._tasks.task_view(task, compact_graph_runs=True),
            "orchestration_graph": orchestration_graph,
            "serialized_text": serialized,
            "source_format": source_format,
            "export_format": export_format,
            "source_version": source_version,
            "adapter_manifest": adapter_manifest,
            "loss_report": loss_report,
            "generated_python": generated_python,
            "export_path": written_relative_path,
        }

    def _known_model_capabilities_for_graph(
        self,
        orchestration_graph: dict[str, Any],
        *,
        profiles_snapshot: dict[str, Any] | None = None,
        configured_models: list[dict[str, Any]] | None = None,
    ) -> dict[str, dict[str, Any]]:
        profile_records = [dict(item) for item in list((profiles_snapshot or {}).get("profiles") or []) if isinstance(item, dict)]
        return build_known_model_capabilities(
            graph=orchestration_graph,
            configured_models=configured_models,
            profile_records=profile_records,
        )

    def save_graph_definition(self, payload: dict[str, Any]) -> dict[str, Any]:
        task = self._tasks.current_task()
        if not task:
            raise ValueError("No current task.")
        if not isinstance(payload, dict):
            raise TypeError("Graph save payload must be a dict.")
        graph_payload = payload.get("graph")
        if not isinstance(graph_payload, dict):
            raise ValueError("graph is required.")
        validated_graph = validate_graph_definition(deepcopy(graph_payload))
        if str(validated_graph.get("task_id") or "").strip() != str(task.get("task_id") or "").strip():
            raise ValueError("graph.task_id must match the current task.")
        prior_graph = self._tasks.graph_definition(str(validated_graph.get("graph_id") or ""))
        ownership_override: dict[str, Any] | None = None
        if isinstance(prior_graph, dict):
            ownership_override = self._tasks._require_graph_source_ownership_write_allowed(  # noqa: SLF001
                action="save_graph_definition",
                payload=payload,
                current_graph=prior_graph,
            )
            expected_revision, expected_etag = self._tasks._payload_expected_graph_revision(payload, graph=graph_payload)  # noqa: SLF001
            try:
                self._tasks._require_graph_revision_match(  # noqa: SLF001
                    action="save_graph_definition",
                    current_graph=prior_graph,
                    expected_revision=expected_revision,
                    expected_etag=expected_etag,
                    require_token=True,
                )
            except self._graph_revision_conflict():
                validated_graph = self._tasks._attempt_non_conflicting_graph_merge(  # noqa: SLF001
                    action="save_graph_definition",
                    current_graph=prior_graph,
                    incoming_graph=validated_graph,
                    expected_revision=expected_revision,
                    expected_etag=expected_etag,
                )
        if ownership_override:
            validated_graph["orchestration_graph"] = self._tasks._apply_graph_source_ownership(  # noqa: SLF001
                dict(validated_graph.get("orchestration_graph") or self._tasks._orchestration_graph_for_task_graph(validated_graph)),  # noqa: SLF001
                ownership_override,
            )
        pre_snapshot = (
            self._tasks._record_graph_snapshot(  # noqa: SLF001
                prior_graph,
                reason="before_graph_save",
                source_action="save_graph_definition",
                label=f"Before save: {str(prior_graph.get('title') or prior_graph.get('graph_id') or '')}".strip(),
            )
            if isinstance(prior_graph, dict)
            else None
        )
        validated_graph = self._prepare_graph_for_persist(validated_graph, prior_graph=prior_graph)
        saved = self._tasks.upsert_graph_definition(validated_graph)
        comparison_report = (
            diff_agent_orchestration_graphs(
                self._tasks._orchestration_graph_for_task_graph(prior_graph),  # noqa: SLF001
                dict(saved.get("orchestration_graph") or {}),
            )
            if isinstance(prior_graph, dict)
            else None
        )
        snapshot = self._tasks._record_graph_snapshot(  # noqa: SLF001
            saved,
            reason="after_graph_save",
            source_action="save_graph_definition",
            label=f"After save: {str(saved.get('title') or saved.get('graph_id') or '')}".strip(),
            based_on_snapshot_id=str((pre_snapshot or {}).get("snapshot_id") or "").strip() or None,
            comparison_report=comparison_report,
        )
        return {
            "schema_version": "astrabridge-task-graph-save-v1",
            "graph": saved,
            "snapshot": snapshot,
            "task": self._tasks.task_view(self._tasks.current_task()),
        }

    def import_graph_from_orchestration_file(
        self,
        payload: dict[str, Any],
        *,
        profiles_snapshot: dict[str, Any] | None = None,
        configured_models: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        from .task_service import AGENT_ORCHESTRATION_GRAPH_SOURCE_FORMAT

        task = self._tasks.current_task()
        if not task:
            raise ValueError("No current task.")
        if not isinstance(payload, dict):
            raise TypeError("Graph import payload must be a dict.")
        graph_text = str(payload.get("graph_text") or "").strip()
        graph_path = str(payload.get("graph_path") or "").strip()
        if not graph_text and not graph_path:
            raise ValueError("graph_text or graph_path is required.")
        workspace_root = self._tasks._projects.require_workspace_root()  # noqa: SLF001
        raw_import_text = graph_text
        import_path_text: str | None = None
        if graph_path:
            resolved_path = resolve_under(workspace_root, graph_path)
            raw_import_text = resolved_path.read_text(encoding="utf-8")
            import_path_text = resolved_path.relative_to(workspace_root).as_posix()
        source_name = import_path_text or "task-graph-import"
        source_format = AGENT_ORCHESTRATION_GRAPH_SOURCE_FORMAT
        source_version: str | None = None
        adapter_manifest: dict[str, Any] | None = None
        loss_report: dict[str, Any] | None = None
        task_graph_overlays: dict[str, dict[str, Any]] = {}
        parsed_json: Any = None
        try:
            parsed_json = json.loads(raw_import_text)
        except json.JSONDecodeError:
            parsed_json = None
        if looks_like_comfyui_workflow(parsed_json):
            imported_payload = import_comfyui_workflow(
                parsed_json,
                task_id=str(task.get("task_id") or ""),
                title=str(payload.get("title") or "").strip() or None,
            )
            orchestration_graph = deepcopy(dict(imported_payload.get("orchestration_graph") or {}))
            source_format = COMFYUI_WORKFLOW_SOURCE_FORMAT
            source_version = str(imported_payload.get("source_version") or "").strip() or None
            adapter_manifest = deepcopy(imported_payload.get("adapter_manifest") or None)
            loss_report = deepcopy(imported_payload.get("loss_report") or None)
            task_graph_overlays = {
                str(node_id).strip(): deepcopy(dict(overlay))
                for node_id, overlay in dict(imported_payload.get("task_graph_overlays") or {}).items()
                if str(node_id).strip() and isinstance(overlay, dict)
            }
        elif looks_like_langgraph_stategraph_manifest(parsed_json):
            imported_payload = import_langgraph_stategraph_manifest(
                parsed_json,
                task_id=str(task.get("task_id") or ""),
                title=str(payload.get("title") or "").strip() or None,
            )
            orchestration_graph = deepcopy(dict(imported_payload.get("orchestration_graph") or {}))
            source_format = LANGGRAPH_STATEGRAPH_SOURCE_FORMAT
            source_version = str(imported_payload.get("source_version") or "").strip() or None
            adapter_manifest = deepcopy(imported_payload.get("adapter_manifest") or None)
            loss_report = deepcopy(imported_payload.get("loss_report") or None)
            task_graph_overlays = {
                str(node_id).strip(): deepcopy(dict(overlay))
                for node_id, overlay in dict(imported_payload.get("task_graph_overlays") or {}).items()
                if str(node_id).strip() and isinstance(overlay, dict)
            }
        else:
            orchestration_graph = parse_agent_orchestration_graph_text(raw_import_text, source_name=source_name)
        compile_agent_orchestration_graph(
            orchestration_graph,
            known_model_capabilities=self._known_model_capabilities_for_graph(
                orchestration_graph,
                profiles_snapshot=profiles_snapshot,
                configured_models=configured_models,
            ),
        )
        prior_graph = self._tasks.graph_definition()
        if isinstance(prior_graph, dict):
            expected_revision, expected_etag = self._tasks._payload_expected_graph_revision(payload)  # noqa: SLF001
            try:
                self._tasks._require_graph_revision_match(  # noqa: SLF001
                    action="import_graph_from_orchestration_file",
                    current_graph=prior_graph,
                    expected_revision=expected_revision,
                    expected_etag=expected_etag,
                    require_token=True,
                )
            except self._graph_revision_conflict():
                pass
        pre_snapshot = (
            self._tasks._record_graph_snapshot(  # noqa: SLF001
                prior_graph,
                reason="before_graph_import",
                source_action="import_graph",
                label=f"Before import: {str(prior_graph.get('title') or prior_graph.get('graph_id') or '')}".strip(),
            )
            if isinstance(prior_graph, dict)
            else None
        )
        imported = deepcopy(orchestration_graph)
        ownership_metadata = (
            self._tasks._build_graph_source_ownership(  # noqa: SLF001
                canonical_graph=imported,
                source_path=import_path_text,
                source_text=raw_import_text,
                source_format=source_format,
            )
            if import_path_text and source_format == AGENT_ORCHESTRATION_GRAPH_SOURCE_FORMAT
            else self._tasks._normalize_graph_source_ownership(dict(imported.get("metadata") or {}).get("source_ownership"))  # noqa: SLF001
        )
        imported["task_id"] = str(task.get("task_id") or "")
        imported["metadata"] = {
            **dict(imported.get("metadata") or {}),
            "updated_at": now_iso(),
            **({"source_ownership": ownership_metadata} if ownership_metadata else {}),
        }
        task_graph = self._tasks.lower_agent_orchestration_graph_to_task_graph(imported) if hasattr(self._tasks, "lower_agent_orchestration_graph_to_task_graph") else None  # type: ignore[attr-defined]
        if task_graph is None:
            from .agent_orchestration_contract import lower_agent_orchestration_graph_to_task_graph

            task_graph = lower_agent_orchestration_graph_to_task_graph(imported)
        task_graph["task_id"] = str(task.get("task_id") or "")
        self._apply_task_graph_overlays(task_graph, task_graph_overlays)
        task_graph["orchestration_graph"] = self._tasks._sync_orchestration_graph_with_task_graph(imported, task_graph=task_graph)  # noqa: SLF001
        task_graph = validate_graph_definition(task_graph)
        if isinstance(prior_graph, dict):
            expected_revision, expected_etag = self._tasks._payload_expected_graph_revision(payload)  # noqa: SLF001
            if (
                str(expected_revision or "").strip()
                and str(expected_revision or "").strip() != str(dict(prior_graph.get("graph_revision") or {}).get("revision_id") or "").strip()
            ) or (
                str(expected_etag or "").strip()
                and str(expected_etag or "").strip() != str(dict(prior_graph.get("graph_revision") or {}).get("etag") or "").strip()
            ):
                task_graph = self._tasks._attempt_non_conflicting_graph_merge(  # noqa: SLF001
                    action="import_graph_from_orchestration_file",
                    current_graph=prior_graph,
                    incoming_graph=task_graph,
                    expected_revision=expected_revision,
                    expected_etag=expected_etag,
                )
        task_graph = self._prepare_graph_for_persist(task_graph, prior_graph=prior_graph)
        validated = self._tasks.upsert_graph_definition(task_graph)
        comparison_report = (
            diff_agent_orchestration_graphs(
                self._tasks._orchestration_graph_for_task_graph(prior_graph),  # noqa: SLF001
                dict(validated.get("orchestration_graph") or {}),
            )
            if isinstance(prior_graph, dict)
            else None
        )
        snapshot = self._tasks._record_graph_snapshot(  # noqa: SLF001
            validated,
            reason="after_graph_import",
            source_action="import_graph",
            label=f"After import: {str(validated.get('title') or validated.get('graph_id') or '')}".strip(),
            based_on_snapshot_id=str((pre_snapshot or {}).get("snapshot_id") or "").strip() or None,
            comparison_report=comparison_report,
        )
        return {
            "schema_version": "astrabridge-agent-orchestration-import-v1",
            "graph": validated,
            "task": self._tasks.task_view(self._tasks.current_task()),
            "orchestration_graph": dict(validated.get("orchestration_graph") or {}),
            "source_format": source_format,
            "source_version": source_version,
            "adapter_manifest": adapter_manifest,
            "loss_report": loss_report,
            "import_path": import_path_text,
            "snapshot": snapshot,
        }

    def _graph_interop_source_format(self, task_graph: dict[str, Any] | None) -> str:
        from .task_service import AGENT_ORCHESTRATION_GRAPH_SOURCE_FORMAT

        graph = dict(task_graph or {})
        orchestration_graph = dict(graph.get("orchestration_graph") or {})
        migration = dict(orchestration_graph.get("migration") or {})
        adapter = dict(migration.get("adapter") or {})
        source_format = str(adapter.get("source_format") or "").strip()
        if source_format:
            return source_format
        metadata = dict(orchestration_graph.get("metadata") or {})
        manifest = dict(metadata.get("adapter_manifest") or {})
        manifest_source_format = str(manifest.get("source_format") or "").strip()
        if manifest_source_format:
            return manifest_source_format
        return AGENT_ORCHESTRATION_GRAPH_SOURCE_FORMAT

    def _apply_task_graph_overlays(
        self,
        task_graph: dict[str, Any],
        node_overlays: dict[str, dict[str, Any]] | None,
    ) -> None:
        if not isinstance(task_graph, dict) or not isinstance(node_overlays, dict) or not node_overlays:
            return
        for node in list(task_graph.get("nodes") or []):
            if not isinstance(node, dict):
                continue
            node_id = str(node.get("node_id") or "").strip()
            overlay = dict(node_overlays.get(node_id) or {})
            if not node_id or not overlay:
                continue
            ui_hints = dict(node.get("ui_hints") or {})
            overlay_node_type_config = dict(overlay.get("node_type_config") or {})
            existing_node_type_config = dict(ui_hints.get("node_type_config") or {})
            node["ui_hints"] = {
                **ui_hints,
                **{key: deepcopy(value) for key, value in overlay.items() if key != "node_type_config"},
                "node_type_config": {
                    **existing_node_type_config,
                    **overlay_node_type_config,
                },
            }

    def _prepare_graph_for_persist(
        self,
        graph: dict[str, Any],
        *,
        prior_graph: dict[str, Any] | None,
    ) -> dict[str, Any]:
        prepared = validate_graph_definition(deepcopy(graph))
        prepared["updated_at"] = now_iso()
        if isinstance(prior_graph, dict):
            prepared["state_version"] = max(
                int(prepared.get("state_version") or 0),
                int(prior_graph.get("state_version") or 0) + 1,
            )
        else:
            prepared["state_version"] = max(int(prepared.get("state_version") or 0), 1)
        prepared["orchestration_graph"] = self._tasks._sync_orchestration_graph_with_task_graph(  # noqa: SLF001
            prepared.get("orchestration_graph"),
            task_graph=prepared,
        )
        return prepared

    def _apply_graph_node_payload_to_graph(
        self,
        graph: dict[str, Any],
        payload: dict[str, Any],
    ) -> tuple[dict[str, Any], str]:
        updated = deepcopy(graph)
        node_id = str(payload.get("node_id") or "").strip()
        create_payload = payload.get("create")
        target_node = next(
            (
                item
                for item in list(updated.get("nodes") or [])
                if isinstance(item, dict) and str(item.get("node_id") or "").strip() == node_id
            ),
            None,
        )
        if create_payload is not None:
            if not isinstance(create_payload, dict):
                raise ValueError("create must be an object.")
            if isinstance(target_node, dict):
                raise ValueError("Node already exists.")
            target_node = self._build_graph_node(
                updated,
                requested_node_id=node_id,
                kind=str(create_payload.get("kind") or ""),
                label=str(create_payload.get("label") or ""),
                position=create_payload.get("position"),
                configuration=payload.get("configuration") if isinstance(payload.get("configuration"), dict) else None,
            )
            updated.setdefault("nodes", []).append(target_node)
            graph_policy = dict(updated.get("graph_policy") or {})
            entry_node_ids = [str(item).strip() for item in list(graph_policy.get("entry_node_ids") or []) if str(item).strip()]
            if not entry_node_ids:
                graph_policy["entry_node_ids"] = [target_node["node_id"]]
                updated["graph_policy"] = graph_policy
        elif not isinstance(target_node, dict):
            raise ValueError("Node not found.")
        if "position" in payload:
            position = payload.get("position")
            if not isinstance(position, dict):
                raise ValueError("position must be an object.")
            target_node["position"] = {"x": position.get("x"), "y": position.get("y")}
        if "configuration" in payload:
            configuration = payload.get("configuration")
            if not isinstance(configuration, dict):
                raise ValueError("configuration must be an object.")
            for key in (
                "label",
                "provider_id",
                "model_id",
                "reasoning_effort",
                "permission_mode",
                "collaboration_mode",
                "execution_backend",
                "budget",
                "human_summary_template",
                "machine_result_schema",
                "ui_hints",
                "artifact_requirements",
                "approval_gate",
                "status",
            ):
                if key in configuration:
                    target_node[key] = configuration.get(key)
            if "execution_policy" in configuration:
                target_node["execution_policy"] = dict(configuration.get("execution_policy") or {})
            if "output_contract" in configuration:
                target_node["output_contract"] = dict(configuration.get("output_contract") or {})
        return updated, node_id

    def _apply_graph_edge_payload_to_graph(
        self,
        graph: dict[str, Any],
        payload: dict[str, Any],
    ) -> tuple[dict[str, Any], str]:
        updated = deepcopy(graph)
        graph_id = str(payload.get("graph_id") or "").strip()
        edge_id = str(payload.get("edge_id") or "").strip()
        target_edge = next(
            (
                item
                for item in list(updated.get("edges") or [])
                if isinstance(item, dict) and str(item.get("edge_id") or "").strip() == edge_id
            ),
            None,
        )
        creating = not isinstance(target_edge, dict)
        if creating:
            from_node_id = str(payload.get("from_node_id") or "").strip()
            to_node_id = str(payload.get("to_node_id") or "").strip()
            edge_type = str(payload.get("edge_type") or "").strip()
            context_policy = payload.get("context_policy")
            handoff_contract = payload.get("handoff_contract")
            if not from_node_id:
                raise ValueError("from_node_id is required when creating an edge.")
            if not to_node_id:
                raise ValueError("to_node_id is required when creating an edge.")
            if not edge_type:
                raise ValueError("edge_type is required when creating an edge.")
            if from_node_id == to_node_id:
                raise ValueError("from_node_id and to_node_id must be different.")
            if not isinstance(context_policy, dict):
                raise ValueError("context_policy is required when creating an edge.")
            if handoff_contract is not None and not isinstance(handoff_contract, dict):
                raise ValueError("handoff_contract must be an object.")
            target_edge = {
                "edge_id": edge_id or new_id("edge"),
                "graph_id": graph_id,
                "from_node_id": from_node_id,
                "to_node_id": to_node_id,
                "edge_type": edge_type,
                "handoff_contract": dict(handoff_contract or {}),
                "context_policy": dict(context_policy),
                "status": str(payload.get("status") or "ready").strip() or "ready",
            }
            updated["edges"] = [*list(updated.get("edges") or []), target_edge]
        else:
            for key in ("from_node_id", "to_node_id", "edge_type", "status"):
                if key in payload:
                    target_edge[key] = payload.get(key)
            if "context_policy" in payload:
                context_policy = payload.get("context_policy")
                if not isinstance(context_policy, dict):
                    raise ValueError("context_policy must be an object.")
                target_edge["context_policy"] = dict(context_policy)
            if "handoff_contract" in payload:
                handoff_contract = payload.get("handoff_contract")
                if handoff_contract is not None and not isinstance(handoff_contract, dict):
                    raise ValueError("handoff_contract must be an object.")
                target_edge["handoff_contract"] = dict(handoff_contract or {})
            if str(target_edge.get("from_node_id") or "").strip() == str(target_edge.get("to_node_id") or "").strip():
                raise ValueError("from_node_id and to_node_id must be different.")
        return updated, str(target_edge.get("edge_id") or edge_id or "").strip()

    def update_graph_node(self, payload: dict[str, Any]) -> dict[str, Any]:
        task = self._tasks.current_task()
        if not task:
            raise ValueError("No current task.")
        if not isinstance(payload, dict):
            raise TypeError("Graph node update payload must be a dict.")
        graph_id = str(payload.get("graph_id") or "").strip()
        node_id = str(payload.get("node_id") or "").strip()
        if not graph_id:
            raise ValueError("graph_id is required.")
        if not node_id:
            raise ValueError("node_id is required.")
        graph = self._tasks.graph_definition(graph_id)
        if not graph:
            raise ValueError("Graph not found.")
        ownership_override = self._tasks._require_graph_source_ownership_write_allowed(  # noqa: SLF001
            action="update_graph_node",
            payload=payload,
            current_graph=graph,
        )
        expected_revision, expected_etag = self._tasks._payload_expected_graph_revision(payload)  # noqa: SLF001
        resolved_node_id = node_id
        try:
            self._tasks._require_graph_revision_match(  # noqa: SLF001
                action="update_graph_node",
                current_graph=graph,
                expected_revision=expected_revision,
                expected_etag=expected_etag,
                require_token=True,
            )
            updated, resolved_node_id = self._apply_graph_node_payload_to_graph(graph, payload)
        except self._graph_revision_conflict():
            base_snapshot_graph = self._tasks._graph_snapshot_for_revision(  # noqa: SLF001
                graph_id=graph_id,
                expected_revision=expected_revision,
                expected_etag=expected_etag,
            )
            if not isinstance(base_snapshot_graph, dict):
                raise
            base_graph = self._tasks._graph_from_snapshot_ref(base_snapshot_graph)  # noqa: SLF001
            if not isinstance(base_graph, dict):
                raise
            incoming_graph, resolved_node_id = self._apply_graph_node_payload_to_graph(base_graph, payload)
            updated = self._tasks._attempt_non_conflicting_graph_merge(  # noqa: SLF001
                action="update_graph_node",
                current_graph=graph,
                incoming_graph=incoming_graph,
                expected_revision=expected_revision,
                expected_etag=expected_etag,
            )
        if ownership_override:
            updated["orchestration_graph"] = self._tasks._apply_graph_source_ownership(  # noqa: SLF001
                dict(updated.get("orchestration_graph") or self._tasks._orchestration_graph_for_task_graph(updated)),  # noqa: SLF001
                ownership_override,
            )
        pre_snapshot = self._tasks._record_graph_snapshot(  # noqa: SLF001
            graph,
            reason="before_node_update",
            source_action="update_graph_node",
            label=f"Before node update: {node_id}",
        )
        updated = self._prepare_graph_for_persist(updated, prior_graph=graph)
        validated = self._tasks.upsert_graph_definition(updated)
        comparison_report = diff_agent_orchestration_graphs(
            self._tasks._orchestration_graph_for_task_graph(graph),  # noqa: SLF001
            dict(validated.get("orchestration_graph") or {}),
        )
        snapshot = self._tasks._record_graph_snapshot(  # noqa: SLF001
            validated,
            reason="after_node_update",
            source_action="update_graph_node",
            label=f"After node update: {node_id}",
            based_on_snapshot_id=str(pre_snapshot.get("snapshot_id") or "").strip() or None,
            comparison_report=comparison_report,
        )
        refreshed_node = next(
            dict(item)
            for item in list(validated.get("nodes") or [])
            if isinstance(item, dict) and str(item.get("node_id") or "").strip() == resolved_node_id
        )
        return {"graph": validated, "node": refreshed_node, "snapshot": snapshot, "task": self._tasks.task_view(self._tasks.current_task())}

    def _build_graph_node(
        self,
        graph: dict[str, Any],
        *,
        requested_node_id: str,
        kind: str,
        label: str,
        position: Any,
        configuration: dict[str, Any] | None,
    ) -> dict[str, Any]:
        clean_kind = self._sanitize_graph_token(kind) or "custom"
        clean_node_id = requested_node_id or self._next_graph_node_id(graph, clean_kind)
        clean_label = str(label or self._default_graph_node_label(clean_kind)).strip() or self._default_graph_node_label(clean_kind)
        resolved_position = self._next_graph_node_position(graph) if not isinstance(position, dict) else {
            "x": int(position.get("x") or 80),
            "y": int(position.get("y") or 160),
        }
        node = {
            "node_id": clean_node_id,
            "graph_id": str(graph.get("graph_id") or ""),
            "kind": clean_kind,
            "label": clean_label,
            "agent_card_ref": f"agent_card_{clean_kind}",
            "execution_policy": {
                "spawn_mode": "isolated_lane",
                "retry_policy": {"max_attempts": 1},
                "timeout_ms": 180000,
                "allow_provider_calls": True,
                "allow_code_changes": False,
                "allow_install": False,
                "requires_human_approval": False,
            },
            "output_contract": {
                "human_summary_required": True,
                "artifact_outputs": ["structured_json"],
                "machine_result_schema": {"type": "object", "required": ["result"]},
                "artifact_only": False,
            },
            "position": resolved_position,
            "status": "draft",
            "permission_mode": "ask",
            "collaboration_mode": "default",
            "execution_backend": "app_server",
            "ui_hints": {"context_policy_preset": "task_digest"},
        }
        if isinstance(configuration, dict):
            for key in (
                "provider_id",
                "model_id",
                "reasoning_effort",
                "permission_mode",
                "collaboration_mode",
                "execution_backend",
                "budget",
                "human_summary_template",
                "machine_result_schema",
                "ui_hints",
                "artifact_requirements",
                "approval_gate",
                "status",
                "label",
            ):
                if key in configuration:
                    node[key] = configuration.get(key)
            if "execution_policy" in configuration:
                node["execution_policy"] = dict(configuration.get("execution_policy") or {})
            if "output_contract" in configuration:
                node["output_contract"] = dict(configuration.get("output_contract") or {})
        return node

    def _next_graph_node_id(self, graph: dict[str, Any], kind: str) -> str:
        base = f"node_{self._sanitize_graph_token(kind) or 'custom'}"
        existing_ids = {
            str(item.get("node_id") or "").strip()
            for item in list(graph.get("nodes") or [])
            if isinstance(item, dict)
        }
        if base not in existing_ids:
            return base
        index = 2
        while f"{base}_{index}" in existing_ids:
            index += 1
        return f"{base}_{index}"

    def _next_graph_node_position(self, graph: dict[str, Any]) -> dict[str, int]:
        positions: list[dict[str, Any]] = [
            dict(item.get("position") or {})
            for item in list(graph.get("nodes") or [])
            if isinstance(item, dict) and isinstance(item.get("position"), dict)
        ]
        if not positions:
            return {"x": 80, "y": 160}
        min_x = min(int(item.get("x") or 0) for item in positions)
        min_y = min(int(item.get("y") or 0) for item in positions)
        next_index = len(positions)
        column = next_index % 3
        row = next_index // 3
        return {"x": min_x + column * 260, "y": min_y + row * 180}

    def _default_graph_node_label(self, kind: str) -> str:
        mapping = {
            "supervisor": "Supervisor",
            "planner": "Planner",
            "worker": "Worker",
            "coder": "Coder",
            "reviewer": "Reviewer",
            "validator": "Validator",
            "researcher": "Researcher",
            "extractor": "Extractor",
            "synthesizer": "Synthesizer",
            "gate": "Gate",
            "custom": "Custom Agent",
        }
        return mapping.get(self._sanitize_graph_token(kind) or "custom", "Custom Agent")

    @staticmethod
    def _sanitize_graph_token(value: str) -> str:
        return re.sub(r"[^a-z0-9_]+", "_", str(value or "").strip().lower()).strip("_")

    def update_graph_edge(self, payload: dict[str, Any]) -> dict[str, Any]:
        task = self._tasks.current_task()
        if not task:
            raise ValueError("No current task.")
        if not isinstance(payload, dict):
            raise TypeError("Graph edge update payload must be a dict.")
        graph_id = str(payload.get("graph_id") or "").strip()
        edge_id = str(payload.get("edge_id") or "").strip()
        if not graph_id:
            raise ValueError("graph_id is required.")
        graph = self._tasks.graph_definition(graph_id)
        if not graph:
            raise ValueError("Graph not found.")
        ownership_override = self._tasks._require_graph_source_ownership_write_allowed(  # noqa: SLF001
            action="update_graph_edge",
            payload=payload,
            current_graph=graph,
        )
        expected_revision, expected_etag = self._tasks._payload_expected_graph_revision(payload)  # noqa: SLF001
        try:
            self._tasks._require_graph_revision_match(  # noqa: SLF001
                action="update_graph_edge",
                current_graph=graph,
                expected_revision=expected_revision,
                expected_etag=expected_etag,
                require_token=True,
            )
            updated, resolved_edge_id = self._apply_graph_edge_payload_to_graph(graph, payload)
        except self._graph_revision_conflict():
            base_snapshot_graph = self._tasks._graph_snapshot_for_revision(  # noqa: SLF001
                graph_id=graph_id,
                expected_revision=expected_revision,
                expected_etag=expected_etag,
            )
            if not isinstance(base_snapshot_graph, dict):
                raise
            base_graph = self._tasks._graph_from_snapshot_ref(base_snapshot_graph)  # noqa: SLF001
            if not isinstance(base_graph, dict):
                raise
            incoming_graph, resolved_edge_id = self._apply_graph_edge_payload_to_graph(base_graph, payload)
            updated = self._tasks._attempt_non_conflicting_graph_merge(  # noqa: SLF001
                action="update_graph_edge",
                current_graph=graph,
                incoming_graph=incoming_graph,
                expected_revision=expected_revision,
                expected_etag=expected_etag,
            )
        if ownership_override:
            updated["orchestration_graph"] = self._tasks._apply_graph_source_ownership(  # noqa: SLF001
                dict(updated.get("orchestration_graph") or self._tasks._orchestration_graph_for_task_graph(updated)),  # noqa: SLF001
                ownership_override,
            )
        pre_snapshot = self._tasks._record_graph_snapshot(  # noqa: SLF001
            graph,
            reason="before_edge_update",
            source_action="update_graph_edge",
            label=f"Before edge update: {edge_id or 'new edge'}",
        )
        updated = self._prepare_graph_for_persist(updated, prior_graph=graph)
        validated = self._tasks.upsert_graph_definition(updated)
        comparison_report = diff_agent_orchestration_graphs(
            self._tasks._orchestration_graph_for_task_graph(graph),  # noqa: SLF001
            dict(validated.get("orchestration_graph") or {}),
        )
        snapshot = self._tasks._record_graph_snapshot(  # noqa: SLF001
            validated,
            reason="after_edge_update",
            source_action="update_graph_edge",
            label=f"After edge update: {resolved_edge_id or edge_id or 'edge'}",
            based_on_snapshot_id=str(pre_snapshot.get("snapshot_id") or "").strip() or None,
            comparison_report=comparison_report,
        )
        refreshed_edge = next(
            dict(item)
            for item in list(validated.get("edges") or [])
            if isinstance(item, dict) and str(item.get("edge_id") or "").strip() == resolved_edge_id
        )
        return {"graph": validated, "edge": refreshed_edge, "snapshot": snapshot, "task": self._tasks.task_view(self._tasks.current_task())}

    @staticmethod
    def _graph_revision_conflict() -> type[Exception]:
        from .task_service import GraphRevisionConflictError

        return GraphRevisionConflictError

