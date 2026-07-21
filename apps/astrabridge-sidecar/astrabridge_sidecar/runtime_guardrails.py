from __future__ import annotations

"""Fail-closed runtime guardrails for canonical graph live admission.

The scheduler and dispatch controller remain the execution owners.  This
module only derives one bounded admission decision and a redacted policy
snapshot before a live graph can be queued or resumed.
"""

import hashlib
import json
from copy import deepcopy
from typing import Any


RUNTIME_GUARDRAIL_SCHEMA_VERSION = "astrabridge-runtime-guardrail-decision-v1"
RUNTIME_GUARDRAIL_HARD_LIMITS = {
    "max_depth": 2,
    "max_total_agents": 16,
    "max_parallel_agents": 8,
    "max_total_tokens": 1_000_000,
    "max_provider_calls": 64,
    "max_retries": 8,
    "max_provider_concurrency": 8,
    "max_model_concurrency": 8,
}
_FULL_HISTORY_MODES = {"all", "full", "full_history", "entire_history", "private_memory"}


def evaluate_runtime_guardrails(
    *,
    graph: dict[str, Any],
    compiled_plan: dict[str, Any],
    run_budget: dict[str, Any] | None,
    dispatch_limits: dict[str, Any] | None = None,
    parent_context: dict[str, Any] | None = None,
    mode: str = "live_run",
    require_complete_budget: bool = False,
) -> dict[str, Any]:
    """Evaluate static and request-level runtime limits before provider dispatch.

    Legacy HTTP/CLI callers may still provide only ``limits.total_tokens``.
    Missing non-token fields are filled from the finite compiled graph and the
    existing dispatch ceilings; they are recorded as compatibility-derived
    values rather than becoming unbounded defaults.  Strict callers can set
    ``require_complete_budget`` to reject omitted fields instead.
    """

    canonical_graph = deepcopy(graph) if isinstance(graph, dict) else {}
    plan = deepcopy(compiled_plan) if isinstance(compiled_plan, dict) else {}
    raw_budget = deepcopy(run_budget) if isinstance(run_budget, dict) else {}
    limits_payload = dict(raw_budget.get("limits") or {}) if isinstance(raw_budget.get("limits"), dict) else {}
    parent = deepcopy(parent_context) if isinstance(parent_context, dict) else {}
    compiled_nodes = [
        dict(item)
        for item in list(plan.get("nodes") or [])
        if isinstance(item, dict) and str(item.get("node_id") or "").strip()
    ]
    graph_nodes = [
        dict(item)
        for item in list(canonical_graph.get("nodes") or [])
        if isinstance(item, dict) and str(item.get("node_id") or "").strip()
    ]
    graph_node_by_id = {
        str(item.get("node_id") or "").strip(): item
        for item in graph_nodes
        if str(item.get("node_id") or "").strip()
    }
    agent_nodes = [
        item
        for item in compiled_nodes
        if str(item.get("compiler_executor_id") or "").strip() in {"agent_lane", "subagent_worker"}
        or bool(dict(graph_node_by_id.get(str(item.get("node_id") or "").strip()) or {}).get("provider_id"))
    ]
    provider_calls = sum(
        1
        for item in graph_nodes
        if bool(dict(item.get("safety") or item.get("execution_policy") or {}).get("allow_provider_calls"))
        or bool(item.get("provider_id"))
    )
    if provider_calls == 0:
        provider_calls = len(agent_nodes)
    provider_model_counts: dict[tuple[str, str], int] = {}
    provider_counts: dict[str, int] = {}
    for item in agent_nodes:
        graph_node = graph_node_by_id.get(str(item.get("node_id") or "").strip(), {})
        routing = dict(graph_node.get("routing") or {})
        provider_id = str(
            graph_node.get("provider_id")
            or routing.get("provider_id")
            or item.get("provider_id")
            or ""
        ).strip()
        model_id = str(
            graph_node.get("model_id")
            or routing.get("model_id")
            or item.get("model_id")
            or ""
        ).strip()
        if not provider_id:
            provider_id = "unknown-provider"
        if not model_id:
            model_id = "unknown-model"
        provider_counts[provider_id] = int(provider_counts.get(provider_id) or 0) + 1
        key = (provider_id, model_id)
        provider_model_counts[key] = int(provider_model_counts.get(key) or 0) + 1
    topology = dict(plan.get("topology") or {})
    observed_parallelism = max(
        1,
        int(
            topology.get("max_parallelism")
            or max(
                (
                    len(list(dict(group).get("node_ids") or []))
                    for group in list(plan.get("parallel_groups") or [])
                    if isinstance(group, dict)
                ),
                default=1,
            )
            or 1
        ),
    )
    observed_graph_depth = _graph_depth(canonical_graph)
    retry_events = 0
    for item in compiled_nodes:
        retry_policy = dict(dict(item.get("execution") or {}).get("retry_policy") or {})
        try:
            max_attempts = max(1, int(retry_policy.get("max_attempts") or 1))
        except (TypeError, ValueError):
            max_attempts = 1
        retry_events += max(0, max_attempts - 1)

    blockers: list[str] = []
    warnings: list[str] = []
    derived_fields: list[str] = []

    graph_policy = dict(canonical_graph.get("graph_policy") or {})
    declared_graph_depth = _optional_int(graph_policy.get("max_depth"))
    if declared_graph_depth is None:
        blockers.append("graph_policy.max_depth is required for live admission")
    elif declared_graph_depth > RUNTIME_GUARDRAIL_HARD_LIMITS["max_depth"]:
        blockers.append("graph depth exceeds hard limit 2")
    if observed_graph_depth > RUNTIME_GUARDRAIL_HARD_LIMITS["max_depth"]:
        blockers.append(f"observed graph depth {observed_graph_depth} exceeds hard limit 2")
    if graph_policy.get("requires_dry_run_before_live") is not True:
        blockers.append("graph_policy.requires_dry_run_before_live must be true")

    ancestor_graph_ids = [
        str(item).strip()
        for item in list(parent.get("ancestor_graph_ids") or [])
        if str(item or "").strip()
    ]
    runtime_depth = len(set(ancestor_graph_ids)) + 1
    if runtime_depth > RUNTIME_GUARDRAIL_HARD_LIMITS["max_depth"]:
        blockers.append(f"runtime graph invocation depth {runtime_depth} exceeds hard limit 2")

    max_depth, explicit = _budget_int(
        "max_depth",
        raw_budget,
        limits_payload,
        default=declared_graph_depth or observed_graph_depth or 1,
    )
    if not explicit:
        derived_fields.append("max_depth")
    max_total_agents, explicit = _budget_int(
        "max_total_agents",
        raw_budget,
        limits_payload,
        default=max(1, len(agent_nodes)),
    )
    if not explicit:
        derived_fields.append("max_total_agents")
    max_parallel_agents, explicit = _budget_int(
        "max_parallel_agents",
        raw_budget,
        limits_payload,
        default=observed_parallelism,
    )
    if not explicit:
        derived_fields.append("max_parallel_agents")
    max_total_tokens, explicit = _budget_int(
        "max_total_tokens",
        raw_budget,
        limits_payload,
        aliases=("total_tokens",),
        default=None,
    )
    if not explicit:
        derived_fields.append("max_total_tokens")
    max_retries, explicit = _budget_int(
        "max_retries",
        raw_budget,
        limits_payload,
        aliases=("retry_budget_max",),
        default=(
            max(0, int(dict(dispatch_limits or {}).get("retry_budget_max") or 0))
            if "retry_budget_max" in dict(dispatch_limits or {})
            else (min(4, max(0, retry_events)) if retry_events else 0)
        ),
    )
    if not explicit:
        derived_fields.append("max_retries")
    retry_allowance = max(0, int(max_retries or 0)) if isinstance(max_retries, int) else 0
    max_provider_calls, explicit = _budget_int(
        "max_provider_calls",
        raw_budget,
        limits_payload,
        aliases=("provider_calls",),
        default=max(1, provider_calls + retry_allowance),
    )
    if not explicit:
        derived_fields.append("max_provider_calls")

    if require_complete_budget:
        required_fields = {
            "max_depth": max_depth,
            "max_total_agents": max_total_agents,
            "max_parallel_agents": max_parallel_agents,
            "max_total_tokens": max_total_tokens,
            "max_provider_calls": max_provider_calls,
            "max_retries": max_retries,
        }
        for field in required_fields:
            if field in derived_fields:
                blockers.append(f"budget.{field} is required for strict live admission")

    _check_positive_or_zero("max_depth", max_depth, blockers, positive=True)
    _check_positive_or_zero("max_total_agents", max_total_agents, blockers, positive=True)
    _check_positive_or_zero("max_parallel_agents", max_parallel_agents, blockers, positive=True)
    _check_positive_or_zero("max_total_tokens", max_total_tokens, blockers, positive=True)
    _check_positive_or_zero("max_provider_calls", max_provider_calls, blockers, positive=True)
    _check_positive_or_zero("max_retries", max_retries, blockers, positive=False)

    for field, value in (
        ("max_depth", max_depth),
        ("max_total_agents", max_total_agents),
        ("max_parallel_agents", max_parallel_agents),
        ("max_total_tokens", max_total_tokens),
        ("max_provider_calls", max_provider_calls),
        ("max_retries", max_retries),
    ):
        ceiling = RUNTIME_GUARDRAIL_HARD_LIMITS[field]
        if isinstance(value, int) and value > ceiling:
            blockers.append(f"budget.{field} exceeds hard ceiling {ceiling}")

    if isinstance(max_depth, int) and observed_graph_depth > max_depth:
        blockers.append(f"observed graph depth {observed_graph_depth} exceeds budget.max_depth {max_depth}")
    if isinstance(max_parallel_agents, int) and observed_parallelism > max_parallel_agents:
        blockers.append(
            f"observed max parallelism {observed_parallelism} exceeds budget.max_parallel_agents {max_parallel_agents}"
        )
    if isinstance(max_total_agents, int) and len(agent_nodes) > max_total_agents:
        blockers.append(f"agent count {len(agent_nodes)} exceeds budget.max_total_agents {max_total_agents}")
    if isinstance(max_provider_calls, int) and provider_calls > max_provider_calls:
        blockers.append(f"provider call count {provider_calls} exceeds budget.max_provider_calls {max_provider_calls}")
    if isinstance(max_retries, int) and retry_events > max_retries:
        blockers.append(f"potential retry events {retry_events} exceed budget.max_retries {max_retries}")

    allow_nested = _budget_bool("allow_nested_subagents", raw_budget, limits_payload, default=False)
    allow_direct = _budget_bool("allow_direct_teammate_messages", raw_budget, limits_payload, default=False)
    if require_complete_budget:
        for field in ("allow_nested_subagents", "allow_direct_teammate_messages"):
            if field not in raw_budget and field not in limits_payload:
                blockers.append(f"budget.{field} is required for strict live admission")
    if allow_nested:
        blockers.append("allow_nested_subagents must be false")
    if allow_direct:
        blockers.append("allow_direct_teammate_messages must be false")
    if any(
        _compiled_subagent_flag(item, "allow_nested_subagents")
        for item in compiled_nodes
    ):
        blockers.append("compiled graph requests nested subagents")
    if any(
        _compiled_subagent_flag(item, "allow_direct_teammate_messages")
        for item in compiled_nodes
    ):
        blockers.append("compiled graph requests direct teammate messaging")

    for edge in list(canonical_graph.get("edges") or []):
        if not isinstance(edge, dict):
            continue
        context = dict(edge.get("context_policy") or {})
        if context.get("exclude_private_memory") is not True:
            blockers.append(f"edge {edge.get('edge_id')} does not exclude private memory")
        if bool(context.get("allow_direct_teammate_messages")):
            blockers.append(f"edge {edge.get('edge_id')} allows direct teammate messaging")
        if str(context.get("history_mode") or "").strip().lower() in _FULL_HISTORY_MODES:
            blockers.append(f"edge {edge.get('edge_id')} requests unrestricted history")

    provider_concurrency, provider_derived = _normalize_concurrency(
        raw_budget,
        limits_payload,
        field="provider_concurrency",
        key_fields=("provider_id",),
        observed_keys=sorted(provider_counts),
        default_limit=_dispatch_default(dispatch_limits, "max_provider_active_nodes", 4),
        hard_limit=RUNTIME_GUARDRAIL_HARD_LIMITS["max_provider_concurrency"],
        blockers=blockers,
    )
    model_observed_keys = [f"{provider}/{model}" for provider, model in sorted(provider_model_counts)]
    model_concurrency, model_derived = _normalize_concurrency(
        raw_budget,
        limits_payload,
        field="model_concurrency",
        key_fields=("provider_id", "model_id"),
        observed_keys=model_observed_keys,
        default_limit=_dispatch_default(dispatch_limits, "max_model_active_nodes", 2),
        hard_limit=RUNTIME_GUARDRAIL_HARD_LIMITS["max_model_concurrency"],
        blockers=blockers,
    )
    if provider_derived:
        derived_fields.append("provider_concurrency")
    if model_derived:
        derived_fields.append("model_concurrency")
    if require_complete_budget:
        if provider_derived:
            blockers.append("budget.provider_concurrency is required for strict live admission")
        if model_derived:
            blockers.append("budget.model_concurrency is required for strict live admission")

    normalized_budget = {
        "max_depth": max_depth,
        "max_total_agents": max_total_agents,
        "max_parallel_agents": max_parallel_agents,
        "max_total_tokens": max_total_tokens,
        "max_provider_calls": max_provider_calls,
        "max_retries": max_retries,
        "provider_concurrency": provider_concurrency,
        "model_concurrency": model_concurrency,
        "allow_nested_subagents": False,
        "allow_direct_teammate_messages": False,
        "limits": {
            "total_tokens": max_total_tokens,
            "max_depth": max_depth,
            "max_total_agents": max_total_agents,
            "max_parallel_agents": max_parallel_agents,
            "max_provider_calls": max_provider_calls,
            "max_retries": max_retries,
        },
    }
    effective_dispatch_limits = _effective_dispatch_limits(
        dispatch_limits or {},
        max_parallel_agents=max_parallel_agents,
        max_retries=max_retries,
        max_provider_calls=max_provider_calls,
        provider_concurrency=provider_concurrency,
        model_concurrency=model_concurrency,
    )
    observed = {
        "graph_depth": observed_graph_depth,
        "runtime_depth": runtime_depth,
        "agent_count": len(agent_nodes),
        "parallelism": observed_parallelism,
        "provider_call_count": provider_calls,
        "potential_retry_events": retry_events,
        "provider_counts": provider_counts,
        "provider_model_counts": {
            f"{provider}/{model}": count for (provider, model), count in sorted(provider_model_counts.items())
        },
    }
    policy_snapshot = {
        "mode": str(mode or "live_run").strip() or "live_run",
        "enforcement": "fail_closed",
        "hard_limits": deepcopy(RUNTIME_GUARDRAIL_HARD_LIMITS),
        "effective_budget": deepcopy(normalized_budget),
        "effective_dispatch_limits": deepcopy(effective_dispatch_limits),
        "observed": deepcopy(observed),
        "derived_fields": sorted(set(derived_fields)),
        "parent_context": {
            "ancestor_graph_ids": ancestor_graph_ids,
            "runtime_depth": runtime_depth,
        },
    }
    decision_payload = {
        "schema_version": RUNTIME_GUARDRAIL_SCHEMA_VERSION,
        "status": "blocked" if blockers else "pass",
        "policy_snapshot": policy_snapshot,
        "warnings": sorted(set(warnings)),
        "blockers": sorted(set(str(item) for item in blockers if str(item).strip())),
    }
    decision_digest = _digest(decision_payload)
    return {
        **decision_payload,
        "decision_digest": f"sha256:{decision_digest}",
        "normalized_budget": normalized_budget,
        "effective_dispatch_limits": effective_dispatch_limits,
        "observed": observed,
        "provenance": {
            "guardrail_schema_version": RUNTIME_GUARDRAIL_SCHEMA_VERSION,
            "decision_digest": f"sha256:{decision_digest}",
            "provider_calls_started": 0,
            "mcp_calls_started": 0,
            "agents_started": 0,
        },
    }


def _budget_int(
    field: str,
    raw_budget: dict[str, Any],
    limits_payload: dict[str, Any],
    *,
    aliases: tuple[str, ...] = (),
    default: int | None,
) -> tuple[int | None, bool]:
    for source in (raw_budget, limits_payload):
        for name in (field, *aliases):
            if name not in source:
                continue
            value = source.get(name)
            if isinstance(value, bool):
                return None, True
            try:
                return int(value), True
            except (TypeError, ValueError):
                return None, True
    return default, False


def _compiled_subagent_flag(item: dict[str, Any], field: str) -> bool:
    execution = dict(item.get("execution") or {})
    policy = dict(execution.get("subagent_policy") or {})
    return bool(policy.get(field))


def _optional_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _budget_bool(field: str, raw_budget: dict[str, Any], limits_payload: dict[str, Any], *, default: bool) -> bool:
    for source in (raw_budget, limits_payload):
        if field in source:
            return bool(source.get(field))
    return default


def _check_positive_or_zero(field: str, value: int | None, blockers: list[str], *, positive: bool) -> None:
    if value is None:
        blockers.append(f"budget.{field} must be an integer")
        return
    if positive and value <= 0:
        blockers.append(f"budget.{field} must be positive")
    if not positive and value < 0:
        blockers.append(f"budget.{field} must be non-negative")


def _normalize_concurrency(
    raw_budget: dict[str, Any],
    limits_payload: dict[str, Any],
    *,
    field: str,
    key_fields: tuple[str, ...],
    observed_keys: list[str],
    default_limit: int,
    hard_limit: int,
    blockers: list[str],
) -> tuple[list[dict[str, Any]], bool]:
    raw_entries: Any = None
    explicit = False
    for source in (raw_budget, limits_payload):
        if field in source:
            raw_entries = source.get(field)
            explicit = True
            break
    entries: list[dict[str, Any]] = []
    if explicit and not isinstance(raw_entries, list):
        blockers.append(f"budget.{field} must be a list")
        raw_entries = []
    seen: set[tuple[str, ...]] = set()
    for item in list(raw_entries or []):
        if not isinstance(item, dict):
            blockers.append(f"budget.{field} entries must be objects")
            continue
        key = tuple(str(item.get(part) or "").strip() for part in key_fields)
        if any(not part for part in key):
            blockers.append(f"budget.{field} entries must declare {'/'.join(key_fields)}")
            continue
        if key in seen:
            blockers.append(f"budget.{field} contains duplicate {'/'.join(key)} entry")
            continue
        seen.add(key)
        value = item.get("max_active_agents")
        if isinstance(value, bool):
            value = None
        try:
            value = int(value)
        except (TypeError, ValueError):
            value = None
        if value is None or value < 1:
            blockers.append(f"budget.{field} {key} must have positive max_active_agents")
            continue
        if value > hard_limit:
            blockers.append(f"budget.{field} {key} exceeds hard ceiling {hard_limit}")
        entry = {part: key[index] for index, part in enumerate(key_fields)}
        entry["max_active_agents"] = value
        entries.append(entry)
    if explicit:
        missing = sorted(set(observed_keys).difference(_concurrency_entry_keys(entries, key_fields)))
        if missing:
            blockers.extend(f"budget.{field} is missing route {item}" for item in missing)
        return entries, False
    bounded_default = max(1, min(int(default_limit or 1), hard_limit))
    for route in observed_keys:
        if len(key_fields) == 1:
            entries.append({key_fields[0]: route, "max_active_agents": bounded_default})
        else:
            provider, _, model = route.partition("/")
            entries.append({"provider_id": provider, "model_id": model, "max_active_agents": bounded_default})
    return entries, True


def _concurrency_entry_keys(entries: list[dict[str, Any]], key_fields: tuple[str, ...]) -> set[str]:
    if len(key_fields) == 1:
        return {str(item.get(key_fields[0]) or "").strip() for item in entries}
    return {
        f"{str(item.get(key_fields[0]) or '').strip()}/{str(item.get(key_fields[1]) or '').strip()}"
        for item in entries
    }


def _dispatch_default(dispatch_limits: dict[str, Any] | None, key: str, default: int) -> int:
    try:
        value = int(dict(dispatch_limits or {}).get(key) or default)
    except (TypeError, ValueError):
        value = default
    return max(1, value)


def _effective_dispatch_limits(
    dispatch_limits: dict[str, Any],
    *,
    max_parallel_agents: int | None,
    max_retries: int | None,
    max_provider_calls: int | None,
    provider_concurrency: list[dict[str, Any]],
    model_concurrency: list[dict[str, Any]],
) -> dict[str, Any]:
    result = deepcopy(dispatch_limits)
    if isinstance(max_parallel_agents, int) and max_parallel_agents > 0:
        original_max_active = max(1, int(result.get("max_active_nodes") or max_parallel_agents))
        original_reserved = max(0, int(result.get("reserved_interactive_slots") or 0))
        graph_slots = max(1, original_max_active - original_reserved)
        bounded_graph_slots = min(graph_slots, max_parallel_agents)
        result["reserved_interactive_slots"] = min(original_reserved, max(0, original_max_active - 1))
        result["max_active_nodes"] = bounded_graph_slots + int(result["reserved_interactive_slots"])
    provider_caps = [int(item.get("max_active_agents") or 1) for item in provider_concurrency]
    model_caps = [int(item.get("max_active_agents") or 1) for item in model_concurrency]
    if provider_caps:
        result["max_provider_active_nodes"] = min(
            max(1, int(result.get("max_provider_active_nodes") or max(provider_caps))),
            min(provider_caps),
        )
    if model_caps:
        result["max_model_active_nodes"] = min(
            max(1, int(result.get("max_model_active_nodes") or max(model_caps))),
            min(model_caps),
        )
    if isinstance(max_retries, int) and max_retries >= 0:
        existing_retry = result.get("retry_budget_max", max_retries)
        try:
            existing_retry_int = int(existing_retry)
        except (TypeError, ValueError):
            existing_retry_int = max_retries
        result["retry_budget_max"] = min(max(0, existing_retry_int), max_retries)
    if isinstance(max_provider_calls, int) and max_provider_calls > 0:
        existing_provider_calls = result.get("max_provider_calls", max_provider_calls)
        try:
            existing_provider_calls_int = int(existing_provider_calls)
        except (TypeError, ValueError):
            existing_provider_calls_int = max_provider_calls
        result["max_provider_calls"] = min(max(1, existing_provider_calls_int), max_provider_calls)
    result["provider_concurrency"] = deepcopy(provider_concurrency)
    result["model_concurrency"] = deepcopy(model_concurrency)
    return result


def _graph_depth(graph: dict[str, Any]) -> int:
    nodes = {
        str(item.get("node_id") or "").strip()
        for item in list(graph.get("nodes") or [])
        if isinstance(item, dict) and str(item.get("node_id") or "").strip()
    }
    entry_nodes = [
        str(item).strip()
        for item in list(dict(graph.get("graph_policy") or {}).get("entry_node_ids") or [])
        if str(item or "").strip() in nodes
    ]
    outgoing: dict[str, list[str]] = {node_id: [] for node_id in nodes}
    for edge in list(graph.get("edges") or []):
        if not isinstance(edge, dict):
            continue
        source = str(edge.get("from_node_id") or "").strip()
        target = str(edge.get("to_node_id") or "").strip()
        if source in nodes and target in nodes:
            outgoing[source].append(target)
    distances = {node_id: 0 for node_id in entry_nodes}
    queue = list(entry_nodes)
    while queue:
        current = queue.pop(0)
        for target in outgoing.get(current, []):
            candidate = int(distances.get(current) or 0) + 1
            if candidate > int(distances.get(target) or 0):
                distances[target] = candidate
                queue.append(target)
    return max(distances.values(), default=0)


def _digest(value: Any) -> str:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


__all__ = [
    "RUNTIME_GUARDRAIL_HARD_LIMITS",
    "RUNTIME_GUARDRAIL_SCHEMA_VERSION",
    "evaluate_runtime_guardrails",
]
