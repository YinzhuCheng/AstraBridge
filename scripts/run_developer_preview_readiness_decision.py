"""Evaluate the evidence-backed public developer-preview readiness decision.

This evaluator is deliberately provider-free. It reads the current public
foundation policies plus secret-free evidence packets, makes DG-OSS-04's
mandatory pause branch visible when legal, security, or privacy gates are
unresolved, and never enables public intake, distribution, or provider
authority.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SIDECAR_ROOT = REPO_ROOT / "apps" / "astrabridge-sidecar"
QUALITY_DOSSIER_PATH = REPO_ROOT / "docs" / "PUBLIC_QUALITY_RELIABILITY_DOSSIER.json"

if str(SIDECAR_ROOT) not in sys.path:
    sys.path.insert(0, str(SIDECAR_ROOT))


REQUIRED_QUALITY_CARD_IDS = (
    "no_key_source_evaluation",
    "flagship_coding_workflow",
    "four_provider_reference_routes",
    "gui_code_orchestration_parity",
    "first_extension_candidate",
    "security_and_privacy_boundary",
    "package_and_update_baseline",
)
EXPECTED_QUALITY_STATES = {
    "no_key_source_evaluation": "demonstrated",
    "flagship_coding_workflow": "pass",
    "four_provider_reference_routes": "reduced_authority",
    "gui_code_orchestration_parity": "pass",
    "first_extension_candidate": "warning_gated",
    "security_and_privacy_boundary": "blocked",
    "package_and_update_baseline": "blocked",
}
REQUIRED_RELEASE_BLOCKER_IDS = (
    "license_and_contribution_terms",
    "private_vulnerability_reporting",
    "private_conduct_reporting",
    "public_support_and_issue_triage",
    "authorized_distribution_release",
)
HARD_PAUSE_CATEGORIES = {"legal", "security", "privacy"}


def run_developer_preview_readiness_decision(
    output_root: str | Path,
    *,
    preview_baseline_evidence: str | Path,
    contributor_cohort_evidence: str | Path,
    quality_dossier_path: str | Path = QUALITY_DOSSIER_PATH,
    repo_root: str | Path = REPO_ROOT,
) -> dict[str, Any]:
    """Write a secret-free DG-OSS-04 decision packet from current evidence."""

    repository = Path(repo_root).expanduser().resolve()
    root = Path(output_root).expanduser().resolve()
    if root.exists() and any(root.iterdir()):
        raise ValueError(f"Refusing to overwrite non-empty evidence root: {root}")
    root.mkdir(parents=True, exist_ok=True)

    quality_cards = _validate_quality_dossier(
        _read_json_object(Path(quality_dossier_path).expanduser().resolve(), label="quality dossier")
    )
    preview = _validate_preview_baseline(
        _read_json_object(Path(preview_baseline_evidence).expanduser().resolve(), label="preview baseline evidence")
    )
    cohort = _validate_contributor_cohort(
        _read_json_object(Path(contributor_cohort_evidence).expanduser().resolve(), label="contributor cohort evidence")
    )
    policy = _inspect_public_preview_policies(repository)
    gates = _build_gates(policy, preview)
    hard_pause_gates = [gate for gate in gates if gate["category"] in HARD_PAUSE_CATEGORIES and gate["status"] != "pass"]
    unresolved_gates = [gate for gate in gates if gate["status"] != "pass"]

    if hard_pause_gates:
        verdict = "pause"
        branch = "C"
        decision_reason = "DG-OSS-04 branch C is mandatory because unresolved legal, security, or privacy gates remain."
    elif unresolved_gates:
        verdict = "continue_dogfood"
        branch = "B"
        decision_reason = "Only non-blocking quality or release qualification gaps remain, so public release stays closed while internal dogfood continues."
    else:
        verdict = "go"
        branch = "A"
        decision_reason = "All declared foundation and public-release gates are evidenced as complete."

    _require(verdict == "pause", "Current DG-OSS-04 evidence must select pause while hard foundation gates remain unresolved.")
    _require(branch == "C", "Current DG-OSS-04 branch must remain C.")

    negative_quality = [
        {
            "claim_id": card["claim_id"],
            "result_state": card["result_state"],
            "failure_status": card["failure_status"],
        }
        for card in quality_cards
        if card["result_state"] not in {"pass", "demonstrated"}
    ]
    _require(len(negative_quality) == 4, "Readiness decision must preserve all four quality-dossier non-pass cards.")

    evidence = {
        "schema_version": "astrabridge-developer-preview-readiness-decision-evidence-v1",
        "mode": "deterministic_provider_free",
        "provider_calls": [],
        "network_calls_attempted": False,
        "decision": {
            "gate_id": "DG-OSS-04",
            "decision_date": date.today().isoformat(),
            "verdict": verdict,
            "branch": branch,
            "reason": decision_reason,
            "public_preview_status": "paused",
            "hard_pause_gate_ids": [gate["id"] for gate in hard_pause_gates],
            "unresolved_gate_ids": [gate["id"] for gate in unresolved_gates],
        },
        "readiness_scorecard": {
            "quality_card_count": len(quality_cards),
            "quality_positive_card_count": len(quality_cards) - len(negative_quality),
            "quality_non_pass_card_count": len(negative_quality),
            "quality_non_pass_cards": negative_quality,
            "foundation_gates": gates,
        },
        "source_evidence": {
            "quality_dossier": {
                "status": "current_pre_preview",
                "card_count": len(quality_cards),
                "non_pass_card_count": len(negative_quality),
            },
            "preview_baseline": preview,
            "contributor_cohort": cohort,
        },
        "public_scope": {
            "allowed": [
                "preserve and inspect documented no-provider source-evaluation evidence",
                "continue private or local deterministic dogfood without a public release claim",
                "review bounded contributor materials locally with redacted evidence",
            ],
            "prohibited": [
                "public developer-preview release or installer distribution",
                "activation of public issue intake or a support SLA",
                "claiming configured private vulnerability or conduct reporting",
                "accepting merge-ready external code before contribution terms",
                "promoting reduced-authority provider routes to coding-route or tool authority",
            ],
        },
        "next_execution_unit": {
            "id": "OSS-FOUNDATION-CLEARANCE-01",
            "status": "owner_gated",
            "coordinator": "project and legal foundation owner",
            "goal": "Clear the named legal, private-reporting, public-intake, and distribution gates before any new public-preview decision is evaluated.",
            "activation_condition": "An authorized owner explicitly selects the license and contribution terms, configures and verifies private vulnerability and conduct routes, assigns public triage ownership, and authorizes distribution review.",
            "completion_evidence": [
                "root license and verified contribution terms with required notices",
                "tested private vulnerability and conduct reporting routes with response owners",
                "explicit public-intake and triage enablement after those private routes exist",
                "authorized signing, distribution, clean-user validation, and release evidence",
            ],
            "reconsideration": "Rerun the preview baseline, contributor cohort, quality dossier, and this readiness evaluator after every owner-gated item has current evidence.",
        },
        "claim_boundary": {
            "proved": "The repository has a reproducible, evidence-bound decision that selects pause for the public developer-preview transition and preserves positive, reduced-authority, warning-gated, and blocked evidence together.",
            "not_proved": [
                "authorization to publish a developer preview",
                "a project license or contribution terms",
                "private vulnerability or conduct reporting availability",
                "public support intake or a maintainer response commitment",
                "authorized installer distribution or a live update service",
                "provider coding-route, tool, or write authority",
            ],
        },
        "artifact_paths": {
            "evidence_json": "evidence.json",
            "evidence_markdown": "evidence.md",
        },
    }
    from astrabridge_sidecar.agentic_updates.contracts import assert_secret_free_agentic_update_payload

    assert_secret_free_agentic_update_payload(evidence, label="developer_preview_readiness_decision")
    _write_json(root / "evidence.json", evidence)
    (root / "evidence.md").write_text(_render_markdown(evidence), encoding="utf-8", newline="\n")
    return evidence


def _validate_quality_dossier(manifest: dict[str, Any]) -> list[dict[str, str]]:
    _require(
        str(manifest.get("schema_version") or "") == "astrabridge-public-quality-reliability-dossier-v1",
        "Quality dossier schema version is unexpected.",
    )
    _require(str(manifest.get("status") or "") == "current_pre_preview", "Quality dossier must remain current pre-preview evidence.")
    cards = [dict(item) for item in list(manifest.get("cards") or []) if isinstance(item, dict)]
    card_ids = [str(card.get("claim_id") or "") for card in cards]
    _require(tuple(card_ids) == REQUIRED_QUALITY_CARD_IDS, "Quality dossier cards must retain the canonical readiness inventory.")
    result: list[dict[str, str]] = []
    for card in cards:
        claim_id = str(card.get("claim_id") or "")
        result_state = str(card.get("result_state") or "")
        _require(result_state == EXPECTED_QUALITY_STATES[claim_id], f"Quality dossier result drifted: {claim_id}")
        boundary = dict(card.get("failure_visibility") or {})
        failure_status = str(boundary.get("status") or "")
        _require(failure_status, f"Quality dossier card lacks visible boundary: {claim_id}")
        result.append({"claim_id": claim_id, "result_state": result_state, "failure_status": failure_status})
    return result


def _validate_preview_baseline(evidence: dict[str, Any]) -> dict[str, Any]:
    _require(
        str(evidence.get("schema_version") or "") == "astrabridge-developer-preview-baseline-evidence-v1",
        "Preview baseline evidence schema version is unexpected.",
    )
    _require(str(evidence.get("mode") or "") == "deterministic_provider_free", "Preview baseline must remain provider-free.")
    _require(list(evidence.get("provider_calls") or []) == [], "Preview baseline must not call providers.")
    _require(not bool(evidence.get("network_calls_attempted")), "Preview baseline must not call the network.")
    _require(str(dict(evidence.get("package_contract") or {}).get("status") or "") == "pass", "Package evidence must pass.")
    _require(str(dict(evidence.get("update_rehearsal") or {}).get("status") or "") == "pass", "Update rehearsal evidence must pass.")
    release = dict(evidence.get("public_release") or {})
    _require(str(release.get("status") or "") == "blocked", "Public release must remain blocked for the current readiness decision.")
    blockers = [dict(item) for item in list(release.get("blockers") or []) if isinstance(item, dict)]
    blocker_ids = tuple(str(item.get("id") or "") for item in blockers)
    _require(blocker_ids == REQUIRED_RELEASE_BLOCKER_IDS, "Preview baseline must expose all five canonical release blockers in order.")
    return {
        "status": "blocked",
        "release_version": str(release.get("release_version") or ""),
        "blockers": blockers,
    }


def _validate_contributor_cohort(evidence: dict[str, Any]) -> dict[str, Any]:
    _require(
        str(evidence.get("schema_version") or "") == "astrabridge-contributor-feedback-cohort-evidence-v1",
        "Contributor cohort evidence schema version is unexpected.",
    )
    _require(str(evidence.get("mode") or "") == "deterministic_provider_free", "Contributor cohort must remain provider-free.")
    _require(list(evidence.get("provider_calls") or []) == [], "Contributor cohort must not call providers.")
    _require(not bool(evidence.get("network_calls_attempted")), "Contributor cohort must not call the network.")
    cohort = dict(evidence.get("cohort") or {})
    _require(str(cohort.get("status") or "") == "rehearsed_pre_preview", "Contributor cohort must remain pre-preview rehearsal evidence.")
    _require(int(cohort.get("candidate_count") or 0) == 3, "Contributor cohort must retain three bounded candidates.")
    _require(int(cohort.get("independent_rehearsal_count") or 0) == 2, "Contributor cohort must retain two independent rehearsals.")
    review = dict(evidence.get("review_expectation") or {})
    _require(str(review.get("current_status") or "") == "pending_public_intake", "Contributor cohort intake must remain pending.")
    return {
        "status": "rehearsed_pre_preview",
        "candidate_count": int(cohort.get("candidate_count") or 0),
        "independent_rehearsal_count": int(cohort.get("independent_rehearsal_count") or 0),
        "current_intake_status": str(review.get("current_status") or ""),
    }


def _inspect_public_preview_policies(repository: Path) -> dict[str, bool]:
    paths = {
        "foundation": repository / "docs" / "OPEN_SOURCE_FOUNDATION_DECISION_RECORD.md",
        "security": repository / "SECURITY.md",
        "conduct": repository / "CODE_OF_CONDUCT.md",
        "contributing": repository / "CONTRIBUTING.md",
        "feedback": repository / "docs" / "CONTRIBUTOR_FEEDBACK_PROTOCOL.md",
    }
    for label, path in paths.items():
        _require(path.is_file(), f"Required readiness policy is missing: {label}")
    text = {label: path.read_text(encoding="utf-8") for label, path in paths.items()}
    has_license = any((repository / name).is_file() for name in ("LICENSE", "LICENSE.md", "LICENSE.txt"))
    return {
        "license_selected": has_license and "root license remains absent" not in text["foundation"],
        "contribution_terms_selected": "not yet accepting merge-ready external code contributions" not in text["contributing"],
        "private_vulnerability_route_configured": "has not yet been configured for public use" not in text["security"],
        "private_conduct_route_configured": "No private conduct-reporting contact has been configured yet." not in text["conduct"],
        "public_intake_enabled": "Current status: `pending_public_intake`." not in text["feedback"],
    }


def _build_gates(policy: dict[str, bool], preview: dict[str, Any]) -> list[dict[str, Any]]:
    blockers = {str(item["id"]): item for item in list(preview["blockers"])}
    statuses = {
        "license_and_contribution_terms": "pass" if policy["license_selected"] and policy["contribution_terms_selected"] else "blocked",
        "private_vulnerability_reporting": "pass" if policy["private_vulnerability_route_configured"] else "blocked",
        "private_conduct_reporting": "pass" if policy["private_conduct_route_configured"] else "blocked",
        "public_support_and_issue_triage": "pass" if policy["public_intake_enabled"] else "blocked",
        "authorized_distribution_release": "blocked",
    }
    categories = {
        "license_and_contribution_terms": "legal",
        "private_vulnerability_reporting": "security",
        "private_conduct_reporting": "privacy",
        "public_support_and_issue_triage": "support",
        "authorized_distribution_release": "distribution",
    }
    gates: list[dict[str, Any]] = []
    for gate_id in REQUIRED_RELEASE_BLOCKER_IDS:
        blocker = dict(blockers[gate_id])
        gates.append(
            {
                "id": gate_id,
                "category": categories[gate_id],
                "status": statuses[gate_id],
                "owner": str(blocker.get("owner") or ""),
                "required_action": str(blocker.get("required_action") or ""),
            }
        )
    return gates


def _read_json_object(path: Path, *, label: str) -> dict[str, Any]:
    _require(path.is_file(), f"Missing {label}: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid {label} JSON: {path}") from exc
    _require(isinstance(value, dict), f"{label.capitalize()} must be a JSON object.")
    return dict(value)


def _render_markdown(evidence: dict[str, Any]) -> str:
    decision = dict(evidence.get("decision") or {})
    scorecard = dict(evidence.get("readiness_scorecard") or {})
    next_unit = dict(evidence.get("next_execution_unit") or {})
    lines = [
        "# Developer Preview Readiness Decision Evidence",
        "",
        f"- Gate: {decision.get('gate_id')}",
        f"- Verdict: {decision.get('verdict')}",
        f"- Branch: {decision.get('branch')}",
        f"- Positive quality cards: {scorecard.get('quality_positive_card_count')}",
        f"- Non-pass quality cards: {scorecard.get('quality_non_pass_card_count')}",
        "",
        "## Foundation gates",
        "",
    ]
    for gate in list(scorecard.get("foundation_gates") or []):
        item = dict(gate)
        lines.append(f"- `{item.get('id')}`: `{item.get('status')}` ({item.get('owner')})")
    lines.extend(
        [
            "",
            "## Next owner-gated unit",
            "",
            f"- ID: {next_unit.get('id')}",
            f"- Status: {next_unit.get('status')}",
            f"- Coordinator: {next_unit.get('coordinator')}",
            "",
            "This evaluator never enables a public release, public intake, provider authority, or a private reporting route.",
            "",
        ]
    )
    return "\n".join(lines)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate the AstraBridge public developer-preview readiness decision.")
    parser.add_argument("--preview-baseline-evidence", type=Path, required=True)
    parser.add_argument("--contributor-cohort-evidence", type=Path, required=True)
    parser.add_argument("--quality-dossier", type=Path, default=QUALITY_DOSSIER_PATH)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args(argv)
    evidence = run_developer_preview_readiness_decision(
        args.output_root,
        preview_baseline_evidence=args.preview_baseline_evidence,
        contributor_cohort_evidence=args.contributor_cohort_evidence,
        quality_dossier_path=args.quality_dossier,
    )
    decision = dict(evidence["decision"])
    print(
        {
            "gate": decision.get("gate_id"),
            "verdict": decision.get("verdict"),
            "branch": decision.get("branch"),
            "evidence": str((args.output_root / "evidence.json").resolve()),
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
