"""Validate the bounded, provider-free first-extension example.

The script validates a candidate skill manifest against one existing canonical
graph. It does not install a plugin, enable a skill, call a provider, invoke
MCP, or start a live run.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SIDECAR_ROOT = REPO_ROOT / "apps" / "astrabridge-sidecar"
EXAMPLE_SKILL_ROOT = REPO_ROOT / "examples" / "extension-contribution" / "contributor-read-only-brief"
EXAMPLE_MANIFEST_PATH = EXAMPLE_SKILL_ROOT / "orchestration-manifest.json"

if str(SIDECAR_ROOT) not in sys.path:
    sys.path.insert(0, str(SIDECAR_ROOT))


def run_first_contribution_extension_example(output_root: str | Path) -> dict[str, Any]:
    """Create a secret-free evidence packet for the example candidate skill."""

    root = Path(output_root).expanduser().resolve()
    if root.exists() and any(root.iterdir()):
        raise ValueError(f"Refusing to overwrite non-empty evidence root: {root}")
    root.mkdir(parents=True, exist_ok=True)

    from astrabridge_sidecar.agentic_updates.contracts import assert_secret_free_agentic_update_payload
    from astrabridge_sidecar.skill_orchestration_validation import (
        load_skill_orchestration_manifest,
        resolve_skill_to_graph,
        validate_skill_orchestration,
    )

    parameters = {
        "task_goal": "Summarize a bounded, read-only contributor proposal.",
        "constraints": ["Use repository-visible contracts only.", "Do not make external calls."],
        "worker_scope": "Read the stated source files and produce a compact evidence summary.",
    }
    manifest = load_skill_orchestration_manifest(EXAMPLE_MANIFEST_PATH)
    validation = validate_skill_orchestration(EXAMPLE_MANIFEST_PATH, parameters)
    _require(str(validation.get("status") or "") == "pass", "Candidate example did not pass canonical validation.")
    checks = dict(validation.get("checks") or {})
    _require(
        all(str(dict(checks.get(name) or {}).get("status") or "") == "pass" for name in ("lint", "compile", "dry_run")),
        "Candidate example did not pass every canonical check.",
    )
    resolution = dict(validation.get("resolution") or {})
    _require(str(resolution.get("status") or "") == "candidate", "Example must remain candidate status.")
    provenance = dict(resolution.get("provenance") or {})
    _require(int(provenance.get("live_provider_calls") or 0) == 0, "Validation attempted a provider call.")
    _require(int(provenance.get("mcp_calls") or 0) == 0, "Validation attempted an MCP call.")
    _require(int(provenance.get("agent_invocations") or 0) == 0, "Validation attempted an agent invocation.")

    widened = resolve_skill_to_graph(
        EXAMPLE_MANIFEST_PATH,
        parameters,
        requested_route={"provider_id": "glm", "model_id": "glm-5.2"},
    )
    widened_blockers = [str(item) for item in list(widened.get("blockers") or [])]
    _require(str(widened.get("status") or "") == "blocked", "Out-of-allowlist route did not fail closed.")
    _require(
        any("requested_route_widens_provider_allowlist" in item for item in widened_blockers),
        "Out-of-allowlist provider did not produce an explicit blocker.",
    )

    evidence = {
        "schema_version": "astrabridge-first-contribution-extension-evidence-v1",
        "mode": "deterministic_provider_free",
        "provider_calls": [],
        "network_calls_attempted": False,
        "extension": {
            "classification": "experimental_candidate",
            "skill_id": str(manifest.get("skill_id") or ""),
            "version": str(manifest.get("version") or ""),
            "status": str(manifest.get("status") or ""),
            "manifest_path": EXAMPLE_MANIFEST_PATH.relative_to(REPO_ROOT).as_posix(),
            "skill_guide_path": (EXAMPLE_SKILL_ROOT / "SKILL.md").relative_to(REPO_ROOT).as_posix(),
            "graph_template_ref": str(dict(manifest.get("resolution") or {}).get("graph_template_ref") or ""),
            "first_contribution_scope": str(dict(manifest.get("extensions") or {}).get("first_contribution_scope") or ""),
        },
        "validation": {
            "status": str(validation.get("status") or ""),
            "checks": {name: str(dict(checks.get(name) or {}).get("status") or "") for name in ("lint", "compile", "dry_run")},
            "warnings": [str(item) for item in list(validation.get("warnings") or [])],
            "blockers": [str(item) for item in list(validation.get("blockers") or [])],
            "provenance": {
                "live_provider_calls": int(provenance.get("live_provider_calls") or 0),
                "mcp_calls": int(provenance.get("mcp_calls") or 0),
                "agent_invocations": int(provenance.get("agent_invocations") or 0),
            },
        },
        "failure_boundary": {
            "status": str(widened.get("status") or ""),
            "scenario": "Requested provider outside the candidate manifest allowlist.",
            "blockers": widened_blockers,
        },
        "claim_boundary": {
            "proved": "A newcomer can inspect and validate one bounded candidate skill manifest that resolves to an existing canonical graph, passes lint/compile/dry-run, and rejects an authority-widening route request without credentials, provider calls, MCP calls, or agent execution.",
            "not_proved": [
                "automatic skill discovery or enablement",
                "plugin installation",
                "live provider behavior or route qualification",
                "tool, file-write, install, or external-write authority",
                "acceptance of external merge-ready contributions before license and intake decisions",
            ],
        },
        "artifact_paths": {
            "evidence_json": "evidence.json",
            "evidence_markdown": "evidence.md",
        },
    }
    assert_secret_free_agentic_update_payload(evidence, label="first_contribution_extension_example")
    _write_json(root / "evidence.json", evidence)
    (root / "evidence.md").write_text(_render_evidence_markdown(evidence), encoding="utf-8", newline="\n")
    return evidence


def _render_evidence_markdown(evidence: dict[str, Any]) -> str:
    extension = dict(evidence.get("extension") or {})
    validation = dict(evidence.get("validation") or {})
    boundary = dict(evidence.get("failure_boundary") or {})
    checks = dict(validation.get("checks") or {})
    return "\n".join(
        [
            "# First-Contribution Extension Evidence",
            "",
            f"- Mode: {evidence.get('mode')}",
            f"- Candidate skill: {extension.get('skill_id')} / {extension.get('version')}",
            f"- Validation: {validation.get('status')}",
            f"- Lint: {checks.get('lint')}",
            f"- Compile: {checks.get('compile')}",
            f"- Dry run: {checks.get('dry_run')}",
            f"- Authority-widening request: {boundary.get('status')}",
            "",
            "The run made no network, provider, MCP, or agent-execution call. The skill remains a candidate and is not auto-enabled.",
            "",
        ]
    )


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the bounded first-contribution extension example.")
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    evidence = run_first_contribution_extension_example(args.output_root)
    print(
        {
            "skill": dict(evidence["extension"]).get("skill_id"),
            "validation": dict(evidence["validation"]).get("status"),
            "failure_boundary": dict(evidence["failure_boundary"]).get("status"),
            "evidence": str(Path(args.output_root).resolve() / "evidence.json"),
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
