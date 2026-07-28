"""Rehearse the pre-preview contributor feedback cohort without external intake.

The runner validates local issue templates and runs the existing provider-free
candidate skill twice in independent roots. It does not open an issue, contact
a maintainer, invoke a provider, enable a plugin, or accept code.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SIDECAR_ROOT = REPO_ROOT / "apps" / "astrabridge-sidecar"
SCRIPTS_ROOT = REPO_ROOT / "scripts"
COHORT_MANIFEST_PATH = REPO_ROOT / "examples" / "contributor-feedback-cohort" / "cohort-manifest.json"
PROTOCOL_PATH = REPO_ROOT / "docs" / "CONTRIBUTOR_FEEDBACK_PROTOCOL.md"

for import_path in (SIDECAR_ROOT, SCRIPTS_ROOT):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))


REQUIRED_TEMPLATE_IDS = (
    "issue-feedback",
    "bug-reproduction",
    "feature-proposal",
    "documentation-evidence",
    "first-contribution-proposal",
)
REQUIRED_TEMPLATE_SAFETY_TEXT = "Do not include credentials, tokens, cookies, authorization headers, vault data, private user data, raw provider payloads, or vulnerability details."
EXPECTED_RESPONSE_TARGET_PREFIX = "Within 7 calendar days after public intake is explicitly activated"


def run_contributor_feedback_cohort_rehearsal(
    output_root: str | Path,
    *,
    repo_root: str | Path = REPO_ROOT,
    cohort_manifest_path: str | Path = COHORT_MANIFEST_PATH,
) -> dict[str, Any]:
    """Build a secret-free evidence packet for two independent local rehearsals."""

    repository = Path(repo_root).expanduser().resolve()
    root = Path(output_root).expanduser().resolve()
    if root.exists() and any(root.iterdir()):
        raise ValueError(f"Refusing to overwrite non-empty evidence root: {root}")
    root.mkdir(parents=True, exist_ok=True)

    manifest = _read_json_object(Path(cohort_manifest_path).expanduser().resolve(), label="cohort manifest")
    template_validation = _validate_static_protocol(repository, manifest)
    response_contract = dict(manifest.get("response_contract") or {})
    _require(str(response_contract.get("current_intake_status") or "") == "pending_public_intake", "Cohort must not claim active public intake.")
    _require(
        str(response_contract.get("activation_disposition_target") or "").startswith(EXPECTED_RESPONSE_TARGET_PREFIX),
        "Cohort response target drifted.",
    )
    _require(not any((repository / name).is_file() for name in ("LICENSE", "LICENSE.md", "LICENSE.txt")), "Cohort must remain pre-license until owner decision.")

    from run_first_contribution_extension_example import run_first_contribution_extension_example
    from astrabridge_sidecar.agentic_updates.contracts import assert_secret_free_agentic_update_payload

    rehearsal_specs = [dict(item) for item in list(manifest.get("independent_rehearsals") or []) if isinstance(item, dict)]
    _require(len(rehearsal_specs) == 2, "Cohort must retain exactly two independent rehearsals.")
    rehearsals: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for spec in rehearsal_specs:
        rehearsal_id = str(spec.get("rehearsal_id") or "")
        _require(rehearsal_id and rehearsal_id not in seen_ids, "Cohort rehearsal ids must be unique.")
        seen_ids.add(rehearsal_id)
        evidence_root = root / "rehearsals" / rehearsal_id
        candidate_evidence = run_first_contribution_extension_example(evidence_root)
        _require(str(dict(candidate_evidence.get("validation") or {}).get("status") or "") == "pass", "Candidate rehearsal validation must pass.")
        _require(str(dict(candidate_evidence.get("failure_boundary") or {}).get("status") or "") == "blocked", "Candidate rehearsal widening boundary must block.")
        _require(list(candidate_evidence.get("provider_calls") or []) == [], "Candidate rehearsal must not call a provider.")
        _require(not bool(candidate_evidence.get("network_calls_attempted")), "Candidate rehearsal must not call the network.")
        rehearsals.append(
            {
                "rehearsal_id": rehearsal_id,
                "task_id": str(spec.get("task_id") or ""),
                "status": "pass",
                "validation": str(dict(candidate_evidence.get("validation") or {}).get("status") or ""),
                "authority_widening_boundary": str(dict(candidate_evidence.get("failure_boundary") or {}).get("status") or ""),
                "evidence_path": f"rehearsals/{rehearsal_id}/evidence.json",
                "review_disposition": "pending_public_intake",
            }
        )

    task_candidates = [dict(item) for item in list(manifest.get("task_candidates") or []) if isinstance(item, dict)]
    _require(len(task_candidates) == 3, "Cohort must retain three bounded task candidates.")
    for candidate in task_candidates:
        source_path = str(candidate.get("source_path") or "")
        _require(bool(source_path) and (repository / source_path).is_file(), f"Cohort source path is missing: {source_path}")
        _require(bool(str(candidate.get("owner") or "")), "Cohort candidate must name an owner.")
        _require(bool(str(candidate.get("validation_command") or "")), "Cohort candidate must name validation.")

    evidence = {
        "schema_version": "astrabridge-contributor-feedback-cohort-evidence-v1",
        "mode": "deterministic_provider_free",
        "provider_calls": [],
        "network_calls_attempted": False,
        "template_validation": template_validation,
        "cohort": {
            "status": "rehearsed_pre_preview",
            "candidate_count": len(task_candidates),
            "independent_rehearsal_count": len(rehearsals),
            "rehearsals": rehearsals,
        },
        "review_expectation": {
            "current_status": str(response_contract.get("current_intake_status") or ""),
            "activation_disposition_target": str(response_contract.get("activation_disposition_target") or ""),
            "activation_conditions": [str(value) for value in list(response_contract.get("activation_conditions") or [])],
            "current_boundary": str(response_contract.get("current_boundary") or ""),
        },
        "claim_boundary": {
            "proved": "The repository has local feedback templates and a finite provider-free cohort that validates one candidate contribution path twice in independent roots, preserves a fail-closed authority-widening result, and records a future response expectation without inventing an active public intake or private contact.",
            "not_proved": [
                "an active public issue tracker or support SLA",
                "a configured private security or conduct-reporting route",
                "license or contribution terms",
                "acceptance of merge-ready external code",
                "provider, MCP, plugin-install, tool-write, or external-write authority",
            ],
        },
        "artifact_paths": {
            "evidence_json": "evidence.json",
            "evidence_markdown": "evidence.md",
        },
    }
    assert_secret_free_agentic_update_payload(evidence, label="contributor_feedback_cohort")
    _write_json(root / "evidence.json", evidence)
    (root / "evidence.md").write_text(_render_markdown(evidence), encoding="utf-8", newline="\n")
    return evidence


def _validate_static_protocol(repository: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    config_path = repository / ".github" / "ISSUE_TEMPLATE" / "config.yml"
    _require(config_path.is_file(), "Issue template config is missing.")
    _require("blank_issues_enabled: false" in config_path.read_text(encoding="utf-8"), "Blank issues must remain disabled.")
    _require(PROTOCOL_PATH.is_file(), "Contributor feedback protocol is missing.")
    protocol = PROTOCOL_PATH.read_text(encoding="utf-8")
    _require("Current status: `pending_public_intake`." in protocol, "Protocol must state pre-preview intake status.")
    _require(EXPECTED_RESPONSE_TARGET_PREFIX in " ".join(protocol.split()), "Protocol response target drifted.")
    _require("## Decision Record Path" in protocol, "Protocol must include decision-record routing.")

    template_specs = [dict(item) for item in list(manifest.get("template_files") or []) if isinstance(item, dict)]
    ids = tuple(str(item.get("template_id") or "") for item in template_specs)
    _require(ids == REQUIRED_TEMPLATE_IDS, "Cohort template inventory drifted.")
    checked: list[str] = []
    for spec in template_specs:
        template_id = str(spec["template_id"])
        path = repository / str(spec["path"])
        _require(path.is_file(), f"Template is missing: {path}")
        content = path.read_text(encoding="utf-8")
        _require(f"<!-- astrabridge-feedback-template: {template_id} -->" in content, f"Template id marker missing: {template_id}")
        _require(REQUIRED_TEMPLATE_SAFETY_TEXT in content, f"Safety boundary missing: {template_id}")
        _require("pending_public_intake" in content or template_id != "first-contribution-proposal", "First-contribution template must preserve pending intake.")
        checked.append(str(spec["path"]))
    return {"status": "pass", "blank_issues_enabled": False, "template_count": len(checked), "templates": checked}


def _read_json_object(path: Path, *, label: str) -> dict[str, Any]:
    _require(path.is_file(), f"Missing {label}: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid {label} JSON: {path}") from exc
    _require(isinstance(value, dict), f"{label.capitalize()} must be a JSON object.")
    return dict(value)


def _render_markdown(evidence: dict[str, Any]) -> str:
    cohort = dict(evidence.get("cohort") or {})
    expectation = dict(evidence.get("review_expectation") or {})
    return "\n".join(
        [
            "# Contributor Feedback Cohort Evidence",
            "",
            f"- Mode: {evidence.get('mode')}",
            f"- Template validation: {dict(evidence.get('template_validation') or {}).get('status')}",
            f"- Candidate tasks: {cohort.get('candidate_count')}",
            f"- Independent rehearsals: {cohort.get('independent_rehearsal_count')}",
            f"- Current intake: {expectation.get('current_status')}",
            "",
            "The cohort rehearses a local candidate path. It does not activate public intake, name a private contact, send feedback, accept code, or call a provider.",
            "",
        ]
    )


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Rehearse the AstraBridge pre-preview contributor feedback cohort.")
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args(argv)
    evidence = run_contributor_feedback_cohort_rehearsal(args.output_root)
    cohort = dict(evidence["cohort"])
    print(
        {
            "status": cohort.get("status"),
            "templates": dict(evidence["template_validation"]).get("template_count"),
            "independent_rehearsals": cohort.get("independent_rehearsal_count"),
            "evidence": str((args.output_root / "evidence.json").resolve()),
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
