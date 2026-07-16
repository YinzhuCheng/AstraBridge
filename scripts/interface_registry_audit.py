from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import re
import sys
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable


STATUS_VALUES = {"current", "deprecated", "shim-only", "test-only", "historical", "unknown"}
CLEANUP_STATUSES = {"deprecated", "shim-only", "test-only", "historical", "unknown"}
REPO_TEXT_SUFFIXES = {".css", ".html", ".js", ".json", ".md", ".mjs", ".py", ".toml", ".ts", ".tsx", ".yaml", ".yml"}
SKIP_DIRS = {".git", ".venv", "__pycache__", "build", "dist", "node_modules", "target", "test-results"}
SERVER_PATH = "apps/astrabridge-sidecar/astrabridge_sidecar/server.py"
ROUTER_PATH = "apps/astrabridge-sidecar/astrabridge_sidecar/router_service.py"
DESKTOP_API_PATH = "apps/astrabridge-desktop/src/api.ts"
DOCUMENT_REGISTRY_PATH = "docs/DOCUMENT_REGISTRY.json"
NON_CONSUMER_DOCUMENTS = {
    "PLAN/ASTRABRIDGE_STANDARDIZATION_UI_LIVE_DOGFOOD_EXECUTION_PLAN.md",
    "docs/DOCUMENT_REGISTRY.md",
    "docs/INTERFACE_GOVERNANCE.md",
    "docs/LEGACY_CLEANUP_AUDIT.md",
    "docs/PROJECT_LOG.md",
}
HTTP_LITERAL_RE = re.compile(r"/(?:api/[A-Za-z0-9_./-]+|healthz?|readyz|v1/[A-Za-z0-9_./-]+)")


HTTP_SHIM_REPLACEMENTS: dict[tuple[str, str], str] = {
    ("GET", "/api/project/current"): "GET /api/projects/current",
    ("POST", "/api/project/open"): "POST /api/projects/open",
    ("GET", "/api/tasks"): "GET /api/project/tasks",
    ("GET", "/api/tasks/current"): "GET /api/project/tasks/current",
    ("POST", "/api/turn/start"): "POST /api/runtime/turns/start",
    ("POST", "/api/turn/interrupt"): "POST /api/runtime/turns/interrupt",
    ("GET", "/api/agentic-updates/{run_id}/status"): "GET /api/agentic-updates/status?run_id={run_id}",
    ("GET", "/api/agentic-updates/{run_id}/result"): "GET /api/agentic-updates/result?run_id={run_id}",
}
HTTP_DEPRECATED_REPLACEMENTS: dict[tuple[str, str], str] = {
    ("GET", "/api/official-codex/status"): "GET /api/llm-manager/session",
    ("POST", "/api/official-codex/apply"): "POST /api/llm-manager/login",
    ("POST", "/api/official-codex/restore"): "POST /api/llm-manager/logout",
}
HTTP_TEST_ONLY = {("POST", "/api/runtime/modals/fake")}
HTTP_CURRENT_OVERRIDES = {
    ("GET", "/health"),
    ("GET", "/api/health"),
    ("GET", "/api/project/tasks/current"),
    ("GET", "/healthz"),
    ("GET", "/readyz"),
    ("GET", "/v1/models"),
    ("POST", "/v1/responses"),
}


def normalize_path(path: Path, repo: Path) -> str:
    return path.resolve().relative_to(repo.resolve()).as_posix()


@lru_cache(maxsize=None)
def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def evidence(path: str, line: int, symbol: str | None = None) -> dict[str, Any]:
    item: dict[str, Any] = {"path": path, "line": line}
    if symbol:
        item["symbol"] = symbol
    return item


def find_symbol(repo: Path, rel: str, symbol: str) -> dict[str, Any]:
    text = read_text(repo / rel)
    match = re.search(re.escape(symbol), text)
    return evidence(rel, line_number(text, match.start()) if match else 1, symbol)


def iter_repo_text_files(repo: Path) -> Iterable[Path]:
    for root, dirs, files in os.walk(repo):
        root_path = Path(root)
        rel_parts = root_path.resolve().relative_to(repo.resolve()).parts
        if "PRIVATE" in rel_parts or any(part in SKIP_DIRS for part in rel_parts):
            dirs[:] = []
            continue
        dirs[:] = [name for name in dirs if name not in SKIP_DIRS and name != "PRIVATE"]
        for name in files:
            path = root_path / name
            if path.suffix.lower() in REPO_TEXT_SUFFIXES:
                yield path


def load_document_statuses(repo: Path) -> dict[str, str]:
    path = repo / DOCUMENT_REGISTRY_PATH
    if not path.is_file():
        return {}
    payload = json.loads(read_text(path))
    return {
        str(item.get("path")): str(item.get("status"))
        for item in list(payload.get("entries") or [])
        if isinstance(item, dict) and item.get("path") and item.get("status")
    }


def expression_is_path(node: ast.AST) -> bool:
    return (isinstance(node, ast.Name) and node.id == "path") or (isinstance(node, ast.Attribute) and node.attr == "path")


def string_values(node: ast.AST) -> list[str]:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [node.value]
    if isinstance(node, (ast.Set, ast.List, ast.Tuple)):
        values: list[str] = []
        for item in node.elts:
            values.extend(string_values(item))
        return values
    return []


def route_values(test: ast.AST) -> list[str]:
    if isinstance(test, ast.Compare) and expression_is_path(test.left) and len(test.ops) == 1 and len(test.comparators) == 1:
        if isinstance(test.ops[0], (ast.Eq, ast.In)):
            return string_values(test.comparators[0])
    if isinstance(test, ast.Call) and isinstance(test.func, ast.Attribute) and test.func.attr == "startswith":
        if expression_is_path(test.func.value) and test.args:
            return string_values(test.args[0])
    return []


def call_name(node: ast.Call) -> str:
    parts: list[str] = []
    value: ast.AST = node.func
    while isinstance(value, ast.Attribute):
        parts.append(value.attr)
        value = value.value
    if isinstance(value, ast.Name):
        parts.append(value.id)
    return ".".join(reversed(parts))


def route_handler_symbols(node: ast.If) -> list[str]:
    ignored = {
        "int",
        "list",
        "str",
        "float",
        "dict",
        "len",
        "min",
        "max",
        "bool",
        "self.send_json",
        "self._send_json",
        "self._optional_query_string",
        "urllib.parse.urlparse",
    }
    symbols: list[str] = []
    module = ast.Module(body=node.body, type_ignores=[])
    for child in ast.walk(module):
        if not isinstance(child, ast.Call):
            continue
        name = call_name(child)
        if not name or name in ignored or name.startswith("query."):
            continue
        if name not in symbols:
            symbols.append(name)
    return symbols[:8]


def extract_http_routes(repo: Path, rel: str) -> list[dict[str, Any]]:
    text = read_text(repo / rel)
    tree = ast.parse(text.lstrip("\ufeff"), filename=rel)
    routes: list[dict[str, Any]] = []
    for function in ast.walk(tree):
        if not isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)) or function.name not in {"do_GET", "do_POST", "do_DELETE"}:
            continue
        method = function.name.removeprefix("do_")
        for node in ast.walk(function):
            if not isinstance(node, ast.If):
                continue
            values = route_values(node.test)
            for route in values:
                if route == "/api/":
                    continue
                if route == "/api/agentic-updates/":
                    for suffix in ("status", "result"):
                        routes.append(
                            {
                                "method": method,
                                "path": f"/api/agentic-updates/{{run_id}}/{suffix}",
                                "definition_evidence": [evidence(rel, node.lineno, "path.startswith")],
                                "handler_symbols": [f"self.context.agentic_updates.{suffix}"],
                            }
                        )
                    continue
                routes.append(
                    {
                        "method": method,
                        "path": route,
                        "definition_evidence": [evidence(rel, node.lineno, function.name)],
                        "handler_symbols": route_handler_symbols(node),
                    }
                )
    if rel == ROUTER_PATH:
        routes.append(
            {
                "method": "POST",
                "path": "/v1/responses",
                "definition_evidence": [find_symbol(repo, rel, 'parsed.path != "/v1/responses"')],
                "handler_symbols": ["service.forward_response"],
            }
        )
    unique: dict[tuple[str, str], dict[str, Any]] = {}
    for item in routes:
        unique[(item["method"], item["path"])] = item
    return [unique[key] for key in sorted(unique)]


def owner_for_http(path: str) -> str:
    prefixes = [
        ("/api/agentic-updates", "agentic-update"),
        ("/api/automations", "automation"),
        ("/api/browser", "browser-workbench"),
        ("/api/dogfood", "dogfood"),
        ("/api/llm-manager", "llm-api-manager"),
        ("/api/project", "project-runtime"),
        ("/api/projects", "project-runtime"),
        ("/api/task-graphs", "agent-orchestration"),
        ("/api/runtime/capability", "capability-runtime"),
        ("/api/runtime/plugin", "extensions"),
        ("/api/runtime/skill", "extensions"),
        ("/api/runtime", "runtime"),
        ("/api/router", "router-provider"),
        ("/api/tools/web", "web-lane"),
        ("/api/audit", "security"),
        ("/api/official-codex", "auth-guardrail"),
        ("/api/admin", "security"),
        ("/v1/", "router-provider"),
        ("/health", "runtime"),
        ("/ready", "runtime"),
    ]
    return next((owner for prefix, owner in prefixes if path.startswith(prefix)), "sidecar-api")


def search_needle(path: str) -> str:
    return path.split("{", 1)[0].rstrip("/") or path


def collect_matches(files: Iterable[Path], repo: Path, needle: str, *, exclude: set[str] | None = None, limit: int = 12) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    excluded = exclude or set()
    for path in files:
        rel = normalize_path(path, repo)
        if rel in excluded:
            continue
        for index, line in enumerate(read_text(path).splitlines(), start=1):
            if needle not in line:
                continue
            matches.append(evidence(rel, index))
            if len(matches) >= limit:
                return matches
    return matches


def consumer_scopes(repo: Path, document_statuses: dict[str, str]) -> dict[str, list[Path]]:
    all_files = list(iter_repo_text_files(repo))
    desktop = [
        path
        for path in all_files
        if normalize_path(path, repo).startswith("apps/astrabridge-desktop/src/")
        and ".test." not in path.name
        and "/gen/" not in f"/{normalize_path(path, repo)}/"
    ]
    tests = [path for path in all_files if "tests" in path.parts or ".test." in path.name]
    scripts_and_runtime = [
        path
        for path in all_files
        if normalize_path(path, repo).startswith("scripts/")
        or normalize_path(path, repo).startswith("apps/astrabridge-sidecar/astrabridge_sidecar/")
    ]
    current_docs = [
        repo / rel
        for rel, status in document_statuses.items()
        if status in {"active", "reference"}
        and rel not in NON_CONSUMER_DOCUMENTS
        and (repo / rel).suffix.lower() == ".md"
        and (repo / rel).is_file()
    ]
    historical_docs = [
        repo / rel
        for rel, status in document_statuses.items()
        if status in {"complete", "superseded", "archived"} and (repo / rel).suffix.lower() == ".md" and (repo / rel).is_file()
    ]
    return {
        "desktop": desktop,
        "tests": tests,
        "runtime": scripts_and_runtime,
        "current_docs": current_docs,
        "historical_docs": historical_docs,
    }


def consumer_search(repo: Path, scopes: dict[str, list[Path]], query: str, definition_paths: set[str]) -> dict[str, Any]:
    return {
        "query": query,
        "searched_scopes": ["desktop", "runtime", "tests", "current_docs", "historical_docs"],
        "matches": {
            name: collect_matches(paths, repo, query, exclude=definition_paths)
            for name, paths in scopes.items()
        },
    }


def build_text_search_index(
    repo: Path,
    scopes: dict[str, list[Path]],
    queries: Iterable[str],
) -> dict[str, dict[str, list[dict[str, Any]]]]:
    unique_queries = sorted({query for query in queries if query}, key=lambda value: (-len(value), value))
    result = {
        query: {scope_name: [] for scope_name in scopes}
        for query in unique_queries
    }
    if not unique_queries:
        return result
    pattern = re.compile("|".join(re.escape(query) for query in unique_queries))
    for scope_name, paths in scopes.items():
        for path in paths:
            rel = normalize_path(path, repo)
            for line_number_value, line in enumerate(read_text(path).splitlines(), start=1):
                for match in pattern.finditer(line):
                    query = match.group(0)
                    records = result[query][scope_name]
                    record = evidence(rel, line_number_value)
                    if record not in records and len(records) < 12:
                        records.append(record)
    return result


def indexed_consumer_search(
    query: str,
    index: dict[str, dict[str, list[dict[str, Any]]]],
    definition_paths: set[str],
) -> dict[str, Any]:
    matches = {
        scope_name: [record for record in records if record.get("path") not in definition_paths]
        for scope_name, records in dict(index.get(query) or {}).items()
    }
    return {
        "query": query,
        "searched_scopes": ["desktop", "runtime", "tests", "current_docs", "historical_docs"],
        "matches": matches,
    }


def build_http_consumer_index(repo: Path, scopes: dict[str, list[Path]]) -> dict[str, dict[str, list[dict[str, Any]]]]:
    index: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for scope_name, paths in scopes.items():
        by_path: dict[str, list[dict[str, Any]]] = {}
        for path in paths:
            rel = normalize_path(path, repo)
            for line_number_value, line in enumerate(read_text(path).splitlines(), start=1):
                for match in HTTP_LITERAL_RE.finditer(line):
                    prefix = line[: match.start()]
                    if prefix.endswith("@tauri-apps") or re.search(r"https?://[^\s\"'`]*$", prefix):
                        continue
                    route = match.group(0).rstrip("/.") or "/"
                    records = by_path.setdefault(route, [])
                    record = evidence(rel, line_number_value)
                    if record not in records and len(records) < 12:
                        records.append(record)
        index[scope_name] = by_path
    return index


def http_consumer_search(
    repo: Path,
    scopes: dict[str, list[Path]],
    index: dict[str, dict[str, list[dict[str, Any]]]],
    path: str,
    definition_paths: set[str],
) -> dict[str, Any]:
    if "{" in path:
        return consumer_search(repo, scopes, search_needle(path), definition_paths)
    matches: dict[str, list[dict[str, Any]]] = {}
    for scope_name, by_path in index.items():
        matches[scope_name] = [record for record in by_path.get(path, []) if record.get("path") not in definition_paths]
    return {
        "query": path,
        "searched_scopes": ["desktop", "runtime", "tests", "current_docs", "historical_docs"],
        "matches": matches,
    }


def has_current_consumer(search: dict[str, Any]) -> bool:
    matches = dict(search.get("matches") or {})
    return any(matches.get(name) for name in ("desktop", "runtime", "current_docs"))


def cleanup_metadata(status: str, replacement: str | None) -> tuple[list[str], str, bool]:
    if status == "current":
        return [], "", False
    if status == "unknown":
        return (
            ["Trace runtime callers outside string-search coverage.", "Exercise the interface with focused tests or visible product flow.", "Assign an owner and replacement before any removal."],
            "Investigate runtime and external callers in Step 5; unknown is never deletion approval.",
            True,
        )
    if status == "shim-only":
        return (
            ["Prove replacement parity.", "Search preserved imports, routes, and evidence.", "Add a migration or explicit rejection path before removal."],
            f"Verify all callers use {replacement or 'the canonical replacement'} before Step 5 changes the shim.",
            True,
        )
    if status == "deprecated":
        return (
            ["Confirm replacement adoption.", "Preserve an actionable migration or disabled response.", "Run focused compatibility tests."],
            f"Confirm no supported caller needs this interface and validate {replacement or 'the replacement'}.",
            True,
        )
    if status == "test-only":
        return (
            ["Confirm fixture ownership.", "Verify the interface is unreachable from normal product UI.", "Update tests before removal."],
            "Review the owning fixture/test suite before Step 5.",
            True,
        )
    return (
        ["Confirm zero imports and zero runtime dispatch.", "Preserve historical evidence links.", "Run replacement parity tests."],
        f"Confirm the historical implementation can be removed in favor of {replacement or 'its maintained replacement'}.",
        True,
    )


def build_http_interfaces(
    repo: Path,
    scopes: dict[str, list[Path]],
    index: dict[str, dict[str, list[dict[str, Any]]]],
) -> list[dict[str, Any]]:
    routes = extract_http_routes(repo, SERVER_PATH) + extract_http_routes(repo, ROUTER_PATH)
    interfaces: list[dict[str, Any]] = []
    for route in routes:
        method = str(route["method"])
        path = str(route["path"])
        key = (method, path)
        definition_paths = {str(item["path"]) for item in route["definition_evidence"]}
        search = http_consumer_search(repo, scopes, index, path, definition_paths)
        replacement: str | None = None
        if key in HTTP_SHIM_REPLACEMENTS:
            status = "shim-only"
            replacement = HTTP_SHIM_REPLACEMENTS[key]
        elif key in HTTP_DEPRECATED_REPLACEMENTS:
            status = "deprecated"
            replacement = HTTP_DEPRECATED_REPLACEMENTS[key]
        elif key in HTTP_TEST_ONLY:
            status = "test-only"
        elif key in HTTP_CURRENT_OVERRIDES or has_current_consumer(search):
            status = "current"
        else:
            status = "unknown"
        prerequisites, investigation, cleanup_candidate = cleanup_metadata(status, replacement)
        interfaces.append(
            {
                "id": f"http.{method}.{path}",
                "family": "http",
                "kind": "router-protocol" if path.startswith("/v1/") or path in {"/healthz", "/readyz"} else "sidecar-rest",
                "name": f"{method} {path}",
                "status": status,
                "owner": owner_for_http(path),
                "schema": {
                    "request": "query parameters" if method in {"GET", "DELETE"} else "JSON object",
                    "response": "JSON object or inline file/SSE response as defined by the handler",
                    "handler_symbols": list(route.get("handler_symbols") or []),
                },
                "definition_evidence": route["definition_evidence"],
                "consumer_search_evidence": search,
                "replacement": replacement,
                "compatibility_dependencies": [replacement] if replacement else [],
                "removal_prerequisites": prerequisites,
                "cleanup_candidate": cleanup_candidate,
                "safe_to_remove": False,
                "next_investigation": investigation,
            }
        )
    return interfaces


def manual_interface(
    repo: Path,
    scopes: dict[str, list[Path]],
    *,
    interface_id: str,
    family: str,
    kind: str,
    name: str,
    status: str,
    owner: str,
    definition_path: str,
    symbol: str,
    schema: dict[str, Any],
    replacement: str | None = None,
    compatibility_dependencies: list[str] | None = None,
    search_query: str | None = None,
    search_index: dict[str, dict[str, list[dict[str, Any]]]] | None = None,
    archived: bool = False,
) -> dict[str, Any]:
    definition = find_symbol(repo, definition_path, symbol)
    query = search_query or symbol
    search = (
        indexed_consumer_search(query, search_index, {definition_path})
        if search_index is not None
        else consumer_search(repo, scopes, query, {definition_path})
    )
    prerequisites, investigation, cleanup_candidate = cleanup_metadata(status, replacement)
    if archived:
        prerequisites = []
        investigation = "Removed from current runtime source; preserve the archived evidence and do not reintroduce the retired symbol."
        cleanup_candidate = False
    return {
        "id": interface_id,
        "family": family,
        "kind": kind,
        "name": name,
        "status": status,
        "owner": owner,
        "schema": schema,
        "definition_evidence": [definition],
        "consumer_search_evidence": search,
        "replacement": replacement,
        "compatibility_dependencies": compatibility_dependencies or ([replacement] if replacement else []),
        "removal_prerequisites": prerequisites,
        "cleanup_candidate": cleanup_candidate,
        "safe_to_remove": False,
        "next_investigation": investigation,
    }


def build_manual_interfaces(repo: Path, scopes: dict[str, list[Path]]) -> list[dict[str, Any]]:
    specs = [
        dict(interface_id="sse.astrabridge.hello", family="sse", kind="event", name="astrabridge.hello", status="current", owner="runtime", definition_path=SERVER_PATH, symbol='event="astrabridge.hello"', schema={"payload": {"cursor": "integer"}, "transport": "text/event-stream"}, search_query="astrabridge.hello"),
        dict(interface_id="sse.astrabridge.event", family="sse", kind="event", name="astrabridge.event", status="current", owner="runtime", definition_path=SERVER_PATH, symbol='event="astrabridge.event"', schema={"payload": {"cursor": "integer", "event": "RuntimeEvent"}, "transport": "text/event-stream"}, search_query="astrabridge.event"),
        dict(interface_id="payload.runtime-event", family="runtime-payload", kind="event-envelope", name="RuntimeEvent", status="current", owner="runtime", definition_path="apps/astrabridge-desktop/src/types.ts", symbol="export type RuntimeEvent", schema={"fields": ["id", "method", "params", "thread_id", "turn_id", "item_id", "created_at"]}),
        dict(interface_id="payload.task-graph", family="runtime-payload", kind="graph-contract", name="TaskGraphDefinition", status="current", owner="agent-orchestration", definition_path="apps/astrabridge-sidecar/astrabridge_sidecar/task_graph_contract.py", symbol="TASK_GRAPH_SCHEMA_VERSION", schema={"schema_source": "validate_graph_definition", "format": "JSON object"}),
        dict(interface_id="payload.agent-orchestration-graph", family="runtime-payload", kind="graph-contract", name="AgentOrchestrationGraph", status="current", owner="agent-orchestration", definition_path="apps/astrabridge-sidecar/astrabridge_sidecar/agent_orchestration_contract.py", symbol="AGENT_ORCHESTRATION_SCHEMA_VERSION", schema={"schema_source": "validate_agent_orchestration_graph", "format": "JSON object"}),
        dict(interface_id="payload.automation-spec", family="runtime-payload", kind="automation-contract", name="AutomationSpec", status="current", owner="automation", definition_path="apps/astrabridge-sidecar/astrabridge_sidecar/automations/specs.py", symbol="class AutomationSpec", schema={"schema_source": "AutomationSpec", "format": "JSON object"}),
        dict(interface_id="payload.capability-spec", family="runtime-payload", kind="capability-contract", name="CapabilitySpec", status="current", owner="capability-runtime", definition_path="apps/astrabridge-sidecar/astrabridge_sidecar/capabilities/specs.py", symbol="class CapabilitySpec", schema={"schema_source": "CapabilitySpec", "format": "JSON object"}),
        dict(interface_id="payload.agentic-update", family="runtime-payload", kind="update-contract", name="AgenticUpdateContract", status="current", owner="agentic-update", definition_path="apps/astrabridge-sidecar/astrabridge_sidecar/agentic_updates/contracts.py", symbol="UPDATE_DOMAINS", schema={"schema_source": "agentic_updates.contracts", "format": "JSON object"}),
        dict(interface_id="payload.provider-failure", family="runtime-payload", kind="error-envelope", name="ProviderFailureEnvelope", status="current", owner="router-provider", definition_path="apps/astrabridge-sidecar/astrabridge_sidecar/providers/failures.py", symbol="def classify_runtime_failure", schema={"schema_source": "classify_runtime_failure", "format": "JSON object"}),
        dict(interface_id="provider.profile", family="provider-metadata", kind="profile-contract", name="ProviderProfile", status="current", owner="provider-compatibility", definition_path="apps/astrabridge-sidecar/astrabridge_sidecar/providers/profile.py", symbol="class ProviderProfile", schema={"schema_source": "ProviderProfile.to_dict", "format": "dataclass/JSON"}),
        dict(interface_id="provider.capabilities", family="provider-metadata", kind="capability-contract", name="ProviderCapabilities", status="current", owner="provider-compatibility", definition_path="apps/astrabridge-sidecar/astrabridge_sidecar/providers/profile.py", symbol="class ProviderCapabilities", schema={"schema_source": "ProviderCapabilities", "format": "dataclass/JSON"}),
        dict(interface_id="provider.registry", family="provider-metadata", kind="provider-registry", name="ProviderRegistry", status="current", owner="provider-compatibility", definition_path="apps/astrabridge-sidecar/astrabridge_sidecar/providers/registry.py", symbol="_PROFILES", schema={"schema_source": "_PROFILES", "format": "ProviderProfile tuple"}),
        dict(interface_id="provider.transport-registry", family="provider-metadata", kind="transport-registry", name="ProviderTransportRegistry", status="current", owner="provider-compatibility", definition_path="apps/astrabridge-sidecar/astrabridge_sidecar/providers/transports/__init__.py", symbol="transport_class_for_profile", schema={"schema_source": "transport_class_for_profile", "format": "Python dispatch contract"}),
        dict(interface_id="provider.runtime-contract", family="provider-metadata", kind="runtime-contract", name="RuntimeProviderContract", status="current", owner="model-catalog", definition_path="apps/astrabridge-sidecar/astrabridge_sidecar/model_catalog/catalog.py", symbol="RUNTIME_PROVIDER_CONTRACT_SCHEMA_VERSION", schema={"schema_source": "resolved_runtime_provider_contract_fields", "format": "JSON object"}),
        dict(interface_id="provider.generated-catalog", family="provider-metadata", kind="catalog", name="GeneratedCatalog", status="current", owner="model-catalog", definition_path="apps/astrabridge-sidecar/astrabridge_sidecar/model_catalog/generated_catalog.py", symbol="class GeneratedCatalog", schema={"schema_source": "GeneratedCatalog", "format": "JSON object"}),
        dict(interface_id="provider.source-registry", family="provider-metadata", kind="source-registry", name="ProviderSourceRegistry", status="current", owner="model-catalog", definition_path="apps/astrabridge-sidecar/astrabridge_sidecar/model_catalog/source_registry.py", symbol="SOURCE_REGISTRY_SCHEMA_VERSION", schema={"schema_source": "SOURCE_REGISTRY_SCHEMA_VERSION", "format": "JSON object"}),
        dict(interface_id="cli.sidecar-module", family="cli-launcher", kind="python-module", name="python -m astrabridge_sidecar.server", status="current", owner="runtime", definition_path=SERVER_PATH, symbol="def main", schema={"arguments": ["--serve", "--port", "--seed-root"]}, search_query="astrabridge_sidecar.server"),
        dict(interface_id="cli.sidecar-wrapper", family="cli-launcher", kind="python-script", name="sidecar_server.py", status="shim-only", owner="runtime", definition_path="apps/astrabridge-sidecar/sidecar_server.py", symbol="from astrabridge_sidecar.server import main", schema={"delegates_to": "astrabridge_sidecar.server.main"}, replacement="python -m astrabridge_sidecar.server", search_query="sidecar_server.py"),
        dict(interface_id="cli.agent-orchestration", family="cli-launcher", kind="python-module", name="python -m astrabridge_sidecar.agent_orchestration_cli", status="current", owner="agent-orchestration", definition_path="apps/astrabridge-sidecar/astrabridge_sidecar/agent_orchestration_cli.py", symbol="def build_parser", schema={"commands": ["lint", "dry-run", "diff", "migrate-task-graph"]}, search_query="agent_orchestration_cli"),
        dict(interface_id="cli.kernel-smoke", family="cli-launcher", kind="python-module", name="python -m astrabridge_sidecar.codex_kernel_smoke", status="current", owner="kernel-compatibility", definition_path="apps/astrabridge-sidecar/astrabridge_sidecar/codex_kernel_smoke.py", symbol="def main", schema={"output": "secret-safe smoke report"}, search_query="codex_kernel_smoke"),
        dict(interface_id="cli.plugin-skill-smoke", family="cli-launcher", kind="python-module", name="python -m astrabridge_sidecar.codex_plugin_skill_smoke", status="current", owner="extensions", definition_path="apps/astrabridge-sidecar/astrabridge_sidecar/codex_plugin_skill_smoke.py", symbol="def main", schema={"output": "plugin/skill smoke report"}, search_query="codex_plugin_skill_smoke"),
        dict(interface_id="cli.plugin-install-smoke", family="cli-launcher", kind="python-module", name="python -m astrabridge_sidecar.codex_plugin_install_smoke", status="current", owner="extensions", definition_path="apps/astrabridge-sidecar/astrabridge_sidecar/codex_plugin_install_smoke.py", symbol="def main", schema={"output": "plugin install smoke report"}, search_query="codex_plugin_install_smoke"),
        dict(interface_id="cli.automation-smoke", family="cli-launcher", kind="python-script", name="scripts/run_automation_smoke.py", status="current", owner="automation", definition_path="scripts/run_automation_smoke.py", symbol="def main", schema={"output": "automation smoke report"}, search_query="run_automation_smoke.py"),
        dict(interface_id="cli.desktop-package-scripts", family="cli-launcher", kind="npm-scripts", name="astrabridge-desktop package scripts", status="current", owner="desktop", definition_path="apps/astrabridge-desktop/package.json", symbol='"scripts"', schema={"commands": ["dev", "build", "preview", "test", "tauri"]}),
        dict(interface_id="mcp.web", family="mcp", kind="stdio-jsonrpc", name="astrabridge-web-tools", status="current", owner="web-lane", definition_path="apps/astrabridge-sidecar/astrabridge_sidecar/astrabridge_web_mcp_server.py", symbol="SERVER_NAME", schema={"methods": ["initialize", "tools/list", "tools/call"], "schema_source": "_tools"}, search_query="astrabridge_web_mcp_server"),
        dict(interface_id="mcp.capabilities", family="mcp", kind="stdio-jsonrpc", name="astrabridge-capabilities", status="current", owner="capability-runtime", definition_path="apps/astrabridge-sidecar/astrabridge_sidecar/astrabridge_capabilities_mcp_server.py", symbol="SERVER_NAME", schema={"methods": ["initialize", "tools/list", "tools/call"], "schema_source": "_tools"}, search_query="astrabridge_capabilities_mcp_server"),
        dict(interface_id="mcp.yunwu-image", family="mcp", kind="stdio-jsonrpc", name="astrabridge-yunwu-image", status="current", owner="image-capability", definition_path="apps/astrabridge-sidecar/astrabridge_sidecar/yunwu_image_mcp_server.py", symbol="SERVER_NAME", schema={"methods": ["initialize", "tools/list", "tools/call"], "schema_source": "_tools"}, search_query="yunwu_image_mcp_server"),
        dict(interface_id="mcp.fixture", family="mcp", kind="stdio-jsonrpc", name="codex-mcp-probe-fixture", status="test-only", owner="kernel-compatibility", definition_path="apps/astrabridge-sidecar/astrabridge_sidecar/codex_mcp_probe_fixture_server.py", symbol="def main", schema={"methods": ["initialize", "tools/list", "tools/call"]}, search_query="codex_mcp_probe_fixture_server"),
        dict(interface_id="shim.lcr-web-mcp-module", family="compatibility-shim", kind="python-module-alias", name="lcr_web_mcp_server", status="shim-only", owner="web-lane", definition_path="apps/astrabridge-sidecar/astrabridge_sidecar/lcr_web_mcp_server.py", symbol="sys.modules[__name__]", schema={"delegates_to": "astrabridge_web_mcp_server"}, replacement="astrabridge_sidecar.astrabridge_web_mcp_server", search_query="lcr_web_mcp_server"),
        dict(interface_id="shim.lcr-web-service", family="compatibility-shim", kind="python-class-alias", name="LcrWebService", status="shim-only", owner="web-lane", definition_path="apps/astrabridge-sidecar/astrabridge_sidecar/lcr_web_service.py", symbol="LcrWebService", schema={"delegates_to": "AstraBridgeWebService"}, replacement="AstraBridgeWebService", search_query="LcrWebService"),
        dict(interface_id="shim.router-inline-adapters", family="compatibility-shim", kind="archived-implementation", name="RouterService legacy inline adapters", status="historical", owner="router-provider", definition_path="PRIVATE/app-standardization-ui-dogfood/docs-api/step5-router-inline-adapters-before.py", symbol="class ProviderAdapter", schema={"symbols": ["ProviderAdapter", "QwenResponsesAdapter", "ChatCompletionsAdapter", "DeepSeekChatAdapter", "KimiChatAdapter"], "removed_from_runtime_source_on": "2026-07-10"}, replacement="astrabridge_sidecar.providers.transports", search_query="QwenResponsesAdapter", archived=True),
        dict(interface_id="shim.legacy-task-graph-lift", family="compatibility-shim", kind="payload-migration", name="legacy task graph lift", status="shim-only", owner="agent-orchestration", definition_path="apps/astrabridge-sidecar/astrabridge_sidecar/agent_orchestration_contract.py", symbol="legacy_task_graph", schema={"input": "TaskGraphDefinition", "output": "AgentOrchestrationGraph"}, replacement="AgentOrchestrationGraph native authoring", search_query="legacy_task_graph"),
        dict(interface_id="shim.dashscope-image-base-url", family="compatibility-shim", kind="provider-url-normalizer", name="DashScope image legacy compatible-mode suffix", status="shim-only", owner="image-capability", definition_path="apps/astrabridge-sidecar/astrabridge_sidecar/capabilities/dashscope_image_generate_adapter.py", symbol="legacy_suffix", schema={"input": "/compatible-mode/v1", "output": "/api/v1"}, replacement="DashScope /api/v1 base URL", search_query="legacy_suffix"),
        dict(interface_id="shim.dashscope-speech-base-url", family="compatibility-shim", kind="provider-url-normalizer", name="DashScope speech legacy compatible-mode suffix", status="shim-only", owner="speech-capability", definition_path="apps/astrabridge-sidecar/astrabridge_sidecar/capabilities/speech_synthesize_adapter.py", symbol="legacy_suffix", schema={"input": "/compatible-mode/v1", "output": "/api/v1"}, replacement="DashScope /api/v1 base URL", search_query="legacy_suffix"),
    ]
    search_index = build_text_search_index(repo, scopes, (str(spec.get("search_query") or spec["symbol"]) for spec in specs))
    return [manual_interface(repo, scopes, search_index=search_index, **spec) for spec in specs]


def source_fingerprint(repo: Path, paths: Iterable[str]) -> str:
    digest = hashlib.sha256()
    for rel in sorted(set(paths)):
        path = repo / rel
        digest.update(rel.encode("utf-8"))
        if path.is_file():
            digest.update(path.read_bytes())
    return digest.hexdigest()


def build_registry(repo: Path) -> dict[str, Any]:
    repo = repo.resolve()
    document_statuses = load_document_statuses(repo)
    scopes = consumer_scopes(repo, document_statuses)
    http_index = build_http_consumer_index(repo, scopes)
    interfaces = build_http_interfaces(repo, scopes, http_index) + build_manual_interfaces(repo, scopes)
    interfaces.sort(key=lambda item: (str(item["family"]), str(item["name"]), str(item["id"])))
    source_paths = {
        str(record["path"])
        for item in interfaces
        for record in list(item.get("definition_evidence") or [])
        if isinstance(record, dict) and record.get("path")
    }
    status_counts = Counter(str(item["status"]) for item in interfaces)
    family_counts = Counter(str(item["family"]) for item in interfaces)
    cleanup_candidates = [str(item["id"]) for item in interfaces if item.get("cleanup_candidate")]
    defined_http_paths = {
        str(item["name"]).split(" ", 1)[1]
        for item in interfaces
        if item.get("family") == "http" and " " in str(item.get("name") or "")
    }
    desktop_http_paths = set(http_index.get("desktop", {}))
    desktop_paths_missing_definition = sorted(desktop_http_paths - defined_http_paths)
    return {
        "schema_version": "astrabridge-interface-registry-v1",
        "generated_on": "2026-07-10",
        "source_fingerprint_sha256": source_fingerprint(repo, source_paths),
        "status_taxonomy": sorted(STATUS_VALUES),
        "source_roots": [SERVER_PATH, ROUTER_PATH, DESKTOP_API_PATH, "apps/astrabridge-sidecar/tests", "apps/astrabridge-desktop/src", "docs", "PLAN", "scripts"],
        "summary": {
            "interfaces": len(interfaces),
            "status_counts": dict(sorted(status_counts.items())),
            "family_counts": dict(sorted(family_counts.items())),
            "cleanup_candidates": len(cleanup_candidates),
            "unknown": status_counts.get("unknown", 0),
            "desktop_literal_http_paths": len(desktop_http_paths),
            "desktop_paths_missing_definition": len(desktop_paths_missing_definition),
        },
        "coverage": {
            "defined_http_paths": len(defined_http_paths),
            "desktop_literal_http_paths": sorted(desktop_http_paths),
            "desktop_paths_missing_definition": desktop_paths_missing_definition,
        },
        "cleanup_candidate_ids": cleanup_candidates,
        "interfaces": interfaces,
    }


def validate_registry(registry: dict[str, Any], repo: Path) -> list[str]:
    errors: list[str] = []
    required = {
        "id",
        "family",
        "kind",
        "name",
        "status",
        "owner",
        "schema",
        "definition_evidence",
        "consumer_search_evidence",
        "replacement",
        "compatibility_dependencies",
        "removal_prerequisites",
        "cleanup_candidate",
        "safe_to_remove",
        "next_investigation",
    }
    interfaces = list(registry.get("interfaces") or [])
    seen: set[str] = set()
    for item in interfaces:
        if not isinstance(item, dict):
            errors.append("interface entry is not an object")
            continue
        missing = sorted(required - set(item))
        if missing:
            errors.append(f"{item.get('id', '<missing-id>')}: missing fields {missing}")
        interface_id = str(item.get("id") or "")
        if interface_id in seen:
            errors.append(f"{interface_id}: duplicate id")
        seen.add(interface_id)
        status = str(item.get("status") or "")
        if status not in STATUS_VALUES:
            errors.append(f"{interface_id}: invalid status {status!r}")
        definitions = list(item.get("definition_evidence") or [])
        if not definitions:
            errors.append(f"{interface_id}: missing definition evidence")
        for record in definitions:
            rel = str(record.get("path") or "") if isinstance(record, dict) else ""
            line = int(record.get("line") or 0) if isinstance(record, dict) else 0
            if not rel or not (repo / rel).is_file() or line <= 0:
                errors.append(f"{interface_id}: invalid definition evidence {record!r}")
        if status in {"shim-only", "deprecated"} and not item.get("replacement"):
            errors.append(f"{interface_id}: {status} entry requires replacement")
        if item.get("cleanup_candidate"):
            search = item.get("consumer_search_evidence")
            if not isinstance(search, dict) or not search.get("searched_scopes") or "matches" not in search:
                errors.append(f"{interface_id}: cleanup candidate lacks consumer-search evidence")
            if not item.get("removal_prerequisites"):
                errors.append(f"{interface_id}: cleanup candidate lacks removal prerequisites")
            if not item.get("next_investigation"):
                errors.append(f"{interface_id}: cleanup candidate lacks next investigation")
            if item.get("safe_to_remove") is not False:
                errors.append(f"{interface_id}: inventory cannot authorize removal")
        if status == "unknown" and not item.get("next_investigation"):
            errors.append(f"{interface_id}: unknown entry lacks next investigation")
    expected_summary = Counter(str(item.get("status")) for item in interfaces)
    if dict(sorted(expected_summary.items())) != dict(registry.get("summary", {}).get("status_counts") or {}):
        errors.append("summary status counts do not match interfaces")
    cleanup_ids = [str(item.get("id")) for item in interfaces if item.get("cleanup_candidate")]
    if cleanup_ids != list(registry.get("cleanup_candidate_ids") or []):
        errors.append("cleanup candidate id list does not match interfaces")
    missing_desktop_paths = list(registry.get("coverage", {}).get("desktop_paths_missing_definition") or [])
    if missing_desktop_paths:
        errors.append(f"desktop HTTP paths lack server definitions: {missing_desktop_paths}")
    return errors


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Build and validate the AstraBridge interface registry from current sources.")
    parser.add_argument("--repo", default=".", help="Repository root.")
    parser.add_argument("--json-out", help="Write the generated machine-readable registry.")
    args = parser.parse_args(argv)
    repo = Path(args.repo).resolve()
    registry = build_registry(repo)
    errors = validate_registry(registry, repo)
    if args.json_out:
        output = Path(args.json_out)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"ok": not errors, "summary": registry["summary"], "errors": errors}, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
