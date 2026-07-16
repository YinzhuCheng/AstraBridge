"""Compatibility adapters for the canonical AstraBridge protocol schemas.

The existing task-graph and orchestration validators remain read-compatible
bridges.  New writes go through the generated protocol validator, while these
adapters preserve the legacy IDs, topology, artifact lineage, and security
policy during migration.
"""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any

from ..agent_orchestration_contract import (
    AGENT_ORCHESTRATION_SCHEMA_VERSION,
    validate_agent_orchestration_graph,
)
from ..agent_orchestration_compiler import AGENT_ORCHESTRATION_COMPILED_PLAN_VERSION
from ..task_graph_contract import TASK_GRAPH_SCHEMA_VERSION, validate_graph_definition
from .generated.v1 import SCHEMA_VERSION, validate_protocol_payload


_MANIFEST_PATH = Path(__file__).with_name("compatibility_manifest.json")
LEGACY_READ_SCHEMA_VERSIONS = (
    "astrabridge-task-graph-v1",
    "astrabridge-task-graph-run-v1",
    AGENT_ORCHESTRATION_SCHEMA_VERSION,
    AGENT_ORCHESTRATION_COMPILED_PLAN_VERSION,
)


def compatibility_manifest() -> dict[str, Any]:
    return json.loads(_MANIFEST_PATH.read_text(encoding="utf-8"))


def adapt_legacy_artifact_path(
    artifact: dict[str, Any],
    *,
    task_id: str | None = None,
    run_id: str | None = None,
    source_node_id: str | None = None,
) -> dict[str, Any]:
    """Lift a legacy workspace-relative artifact reference into an URI ref."""

    if not isinstance(artifact, dict):
        raise TypeError("Legacy artifact reference must be an object.")
    source = deepcopy(artifact)
    path = str(source.get("artifact_uri") or source.get("path") or "").replace("\\", "/").strip()
    if path.startswith(("workspace://", "ab-artifact://")):
        artifact_uri = path
    elif path.startswith((".astrabridge/", "PRIVATE/")):
        artifact_uri = f"workspace://{path}"
    else:
        raise ValueError("Legacy artifact paths must stay under .astrabridge/ or PRIVATE/.")
    lineage = dict(source.get("lineage") or {})
    lineage.setdefault("task_id", task_id or source.get("task_id"))
    lineage.setdefault("run_id", run_id or source.get("run_id"))
    lineage.setdefault("source_node_id", source_node_id or source.get("source_node_id"))
    canonical = {
        "artifact_id": str(source.get("artifact_id") or "").strip(),
        "artifact_uri": artifact_uri,
        "media_type": str(source.get("media_type") or source.get("mime_type") or "application/octet-stream").strip(),
        "status": str(source.get("status") or "ready").strip(),
        "lineage": lineage,
    }
    if source.get("metadata") is not None:
        canonical["metadata"] = deepcopy(source["metadata"])
    return validate_protocol_payload("ArtifactRef", canonical)


def migrate_graph_definition(graph: dict[str, Any]) -> dict[str, Any]:
    """Return an idempotent canonical graph projection."""

    if not isinstance(graph, dict):
        raise TypeError("Graph definition must be an object.")
    if graph.get("schema_version") == SCHEMA_VERSION:
        return deepcopy(validate_protocol_payload("GraphDefinition", graph))

    source_version = str(graph.get("schema_version") or "").strip()
    if source_version == TASK_GRAPH_SCHEMA_VERSION:
        legacy = validate_graph_definition(graph)
    elif source_version == AGENT_ORCHESTRATION_SCHEMA_VERSION:
        legacy = validate_agent_orchestration_graph(graph)
    else:
        raise ValueError(f"Unsupported graph schema for migration: {source_version}")
    policy = dict(legacy.get("graph_policy") or {})
    canonical = {
        "schema_version": SCHEMA_VERSION,
        "graph_id": str(legacy["graph_id"]),
        "task_id": str(legacy["task_id"]),
        "title": str(legacy["title"]),
        "nodes": deepcopy(list(legacy.get("nodes") or [])),
        "edges": deepcopy(list(legacy.get("edges") or [])),
        "entry_node_ids": list(policy.get("entry_node_ids") or []),
        "state_version": int(legacy.get("state_version") or 1),
        "graph_policy": deepcopy(policy),
        "migration": {
            "source_schema": source_version,
            "target_schema": SCHEMA_VERSION,
            "idempotency_key": f"graph:{legacy['graph_id']}:{legacy.get('state_version') or 1}",
            "warnings": ["legacy graph fields are preserved under legacy_projection"],
            "legacy_projection": deepcopy(legacy),
        },
    }
    return validate_protocol_payload("GraphDefinition", canonical)


def migrate_compiled_plan(plan: dict[str, Any]) -> dict[str, Any]:
    """Lift a legacy compiled plan without changing graph identity or topology."""

    if not isinstance(plan, dict):
        raise TypeError("Compiled plan must be an object.")
    if plan.get("schema_version") == SCHEMA_VERSION:
        return deepcopy(validate_protocol_payload("CompiledPlan", plan))
    source_version = str(plan.get("schema_version") or "").strip()
    if source_version != AGENT_ORCHESTRATION_COMPILED_PLAN_VERSION:
        raise ValueError(f"Unsupported compiled-plan schema for migration: {source_version}")
    legacy = deepcopy(plan)
    canonical = {
        "schema_version": SCHEMA_VERSION,
        "graph_id": str(legacy.get("graph_id") or ""),
        "task_id": str(legacy.get("task_id") or ""),
        "graph_schema_version": str(legacy.get("graph_schema_version") or AGENT_ORCHESTRATION_SCHEMA_VERSION),
        "compiled_at": str(legacy.get("compiled_at") or "1970-01-01T00:00:00+00:00"),
        "entry_node_ids": deepcopy(list(legacy.get("entry_node_ids") or [])),
        "topology": deepcopy(dict(legacy.get("topology") or {})),
        "nodes": deepcopy(list(legacy.get("nodes") or [])),
        "edges": deepcopy(list(legacy.get("edges") or [])),
        "migration": {
            "source_schema": source_version,
            "target_schema": SCHEMA_VERSION,
            "idempotency_key": f"compiled:{legacy.get('graph_id')}:{legacy.get('task_id')}",
            "legacy_projection": legacy,
        },
    }
    return validate_protocol_payload("CompiledPlan", canonical)


def canonical_graph_signature(graph: dict[str, Any]) -> dict[str, Any]:
    """Return the identity/topology fields used by migration tests and audits."""

    return {
        "graph_id": str(graph.get("graph_id") or ""),
        "task_id": str(graph.get("task_id") or ""),
        "node_ids": sorted(str(item.get("node_id") or "") for item in list(graph.get("nodes") or []) if isinstance(item, dict)),
        "edge_ids": sorted(str(item.get("edge_id") or "") for item in list(graph.get("edges") or []) if isinstance(item, dict)),
        "edge_pairs": sorted(
            (str(item.get("from_node_id") or ""), str(item.get("to_node_id") or ""))
            for item in list(graph.get("edges") or [])
            if isinstance(item, dict)
        ),
        "entry_node_ids": sorted(str(item) for item in list(graph.get("entry_node_ids") or dict(graph.get("graph_policy") or {}).get("entry_node_ids") or [])),
    }


__all__ = [
    "LEGACY_READ_SCHEMA_VERSIONS",
    "SCHEMA_VERSION",
    "adapt_legacy_artifact_path",
    "canonical_graph_signature",
    "compatibility_manifest",
    "migrate_compiled_plan",
    "migrate_graph_definition",
]
