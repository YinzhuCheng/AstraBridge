"""Validate the public quality dossier against bounded, secret-free evidence.

The dossier is intentionally an aggregation and negative-result index. It does
not invoke providers, start the Desktop, publish artifacts, or turn a local
check into an installer, authority, or support claim.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SIDECAR_ROOT = REPO_ROOT / "apps" / "astrabridge-sidecar"
MANIFEST_PATH = REPO_ROOT / "docs" / "PUBLIC_QUALITY_RELIABILITY_DOSSIER.json"

if str(SIDECAR_ROOT) not in sys.path:
    sys.path.insert(0, str(SIDECAR_ROOT))


REQUIRED_CLAIM_IDS = (
    "no_key_source_evaluation",
    "flagship_coding_workflow",
    "four_provider_reference_routes",
    "gui_code_orchestration_parity",
    "first_extension_candidate",
    "security_and_privacy_boundary",
    "package_and_update_baseline",
)
ALLOWED_EVIDENCE_CLASSES = {
    "deterministic_evidence",
    "documented_and_deterministic",
    "current_contract_and_scan",
}
POSITIVE_RESULT_STATES = {"pass", "demonstrated"}


def run_public_quality_reliability_dossier(
    output_root: str | Path,
    *,
    flagship_evidence: str | Path,
    provider_cohort_report: str | Path,
    gui_parity_evidence: str | Path,
    extension_evidence: str | Path,
    preview_baseline_evidence: str | Path,
    security_scan_report: str | Path,
    manifest_path: str | Path = MANIFEST_PATH,
    repo_root: str | Path = REPO_ROOT,
) -> dict[str, Any]:
    """Build a public, failure-visible quality dossier evidence packet."""

    repository = Path(repo_root).expanduser().resolve()
    root = Path(output_root).expanduser().resolve()
    if root.exists() and any(root.iterdir()):
        raise ValueError(f"Refusing to overwrite non-empty evidence root: {root}")
    root.mkdir(parents=True, exist_ok=True)

    manifest = _read_json_object(Path(manifest_path).expanduser().resolve(), label="quality dossier manifest")
    cards = _validate_manifest(manifest, repository)
    input_evidence = {
        "no_key_source": _verify_no_key_source(repository),
        "flagship": _verify_flagship(_read_json_object(Path(flagship_evidence).expanduser().resolve(), label="flagship evidence")),
        "provider_cohort": _verify_provider_cohort(
            _read_json_object(Path(provider_cohort_report).expanduser().resolve(), label="provider cohort report")
        ),
        "gui_parity": _verify_gui_parity(_read_json_object(Path(gui_parity_evidence).expanduser().resolve(), label="GUI parity evidence")),
        "extension_candidate": _verify_extension(
            _read_json_object(Path(extension_evidence).expanduser().resolve(), label="extension evidence")
        ),
        "preview_baseline": _verify_preview_baseline(
            _read_json_object(Path(preview_baseline_evidence).expanduser().resolve(), label="preview baseline evidence")
        ),
        "security_scan": _verify_security_scan(
            _read_json_object(Path(security_scan_report).expanduser().resolve(), label="security scan report"), repository
        ),
    }

    public_cards = [_public_card(card) for card in cards]
    negative_ledger = [card for card in public_cards if card["result_state"] not in POSITIVE_RESULT_STATES]
    _require(negative_ledger, "Quality dossier must expose at least one non-pass or bounded result.")
    _require(
        {card["claim_id"] for card in negative_ledger}
        == {"four_provider_reference_routes", "first_extension_candidate", "security_and_privacy_boundary", "package_and_update_baseline"},
        "Quality dossier negative ledger no longer matches its declared non-pass boundaries.",
    )

    evidence = {
        "schema_version": "astrabridge-public-quality-reliability-dossier-evidence-v1",
        "mode": "deterministic_provider_free",
        "provider_calls": [],
        "network_calls_attempted": False,
        "dossier": {
            "status": "pass",
            "manifest_path": "docs/PUBLIC_QUALITY_RELIABILITY_DOSSIER.json",
            "card_count": len(public_cards),
            "positive_card_count": len(public_cards) - len(negative_ledger),
            "negative_card_count": len(negative_ledger),
            "cards": public_cards,
            "negative_ledger": negative_ledger,
        },
        "input_evidence": input_evidence,
        "claim_boundary": {
            "proved": "The public dossier has seven bounded quality cards backed by current source-visible contracts and fresh secret-free deterministic evidence inputs. Every non-pass, warning-gated, reduced-authority, or release-blocked card is reproduced in one negative ledger.",
            "not_proved": [
                "a public installer or signed distribution",
                "live provider or coding-route qualification",
                "automatic plugin or skill enablement",
                "private vulnerability or conduct reporting availability",
                "universal GUI/code graph conversion",
            ],
        },
        "artifact_paths": {
            "evidence_json": "evidence.json",
            "evidence_markdown": "evidence.md",
        },
    }
    from astrabridge_sidecar.agentic_updates.contracts import assert_secret_free_agentic_update_payload

    assert_secret_free_agentic_update_payload(evidence, label="public_quality_reliability_dossier")
    _write_json(root / "evidence.json", evidence)
    (root / "evidence.md").write_text(_render_markdown(evidence), encoding="utf-8", newline="\n")
    return evidence


def _validate_manifest(manifest: dict[str, Any], repository: Path) -> list[dict[str, Any]]:
    _require(
        str(manifest.get("schema_version") or "") == "astrabridge-public-quality-reliability-dossier-v1",
        "Quality dossier manifest has an unexpected schema version.",
    )
    _require(str(manifest.get("status") or "") == "current_pre_preview", "Quality dossier manifest must remain pre-preview.")
    cards = [dict(item) for item in list(manifest.get("cards") or []) if isinstance(item, dict)]
    ids = [str(card.get("claim_id") or "") for card in cards]
    _require(tuple(ids) == REQUIRED_CLAIM_IDS, "Quality dossier cards must be complete and in canonical order.")
    for card in cards:
        _require(str(card.get("evidence_classification") or "") in ALLOWED_EVIDENCE_CLASSES, "Card has invalid evidence classification.")
        _require(bool(str(card.get("result_state") or "")), "Card must state a result.")
        _require(bool(str(card.get("result_date") or "")), "Card must state a result date.")
        _require(bool(list(card.get("owners") or [])), "Card must name an owner.")
        _require(bool(list(card.get("known_limitations") or [])), "Card must state at least one limitation.")
        reproduction = dict(card.get("reproduction") or {})
        sources = [str(value) for value in list(reproduction.get("public_sources") or [])]
        _require(sources, "Card must name public reproduction sources.")
        _require(bool(str(reproduction.get("test_command") or "")), "Card must name a test or reproduction command.")
        _require(bool(str(reproduction.get("artifact_contract") or "")), "Card must name a reproducible artifact contract.")
        for source in sources:
            _require(not source.startswith(("PRIVATE/", "output/")), "Public dossier must not cite a raw private artifact as primary evidence.")
            _require((repository / source).is_file(), f"Public reproduction source is missing: {source}")
        boundary = dict(card.get("failure_visibility") or {})
        _require(bool(str(boundary.get("status") or "")), "Card must expose a failure/limit status.")
        _require(bool(str(boundary.get("public_location") or "")), "Card must expose a public failure/limit location.")
        _require(bool(str(boundary.get("how_to_detect") or "")), "Card must say how to detect a failure or limit.")
    return cards


def _verify_no_key_source(repository: Path) -> dict[str, Any]:
    guide = (repository / "docs" / "NO_KEY_FIRST_TEN_MINUTES.md").read_text(encoding="utf-8")
    _require("c8988fef6f1139ac056fadb68e395122ee59254a" in guide, "No-key guide lost the recorded source revision.")
    _require("not a release-installer" in guide, "No-key guide lost its installer non-claim.")
    return {"status": "demonstrated", "source_revision_recorded": True, "provider_calls": 0, "network_boundary": "loopback_only_recorded"}


def _verify_flagship(value: dict[str, Any]) -> dict[str, Any]:
    _require(str(value.get("schema_version") or "") == "astrabridge-flagship-coding-agent-evidence-v1", "Unexpected flagship schema.")
    _require(list(value.get("provider_calls") or []) == [], "Flagship evidence must contain no provider calls.")
    _require(str(dict(value.get("dry_run") or {}).get("status") or "") == "pass", "Flagship dry run must pass.")
    _require(str(dict(value.get("failure_exercise") or {}).get("status") or "") == "failed", "Flagship failure exercise must remain visible.")
    _require(str(dict(value.get("recovery_exercise") or {}).get("status") or "") == "completed", "Flagship recovery must complete.")
    return {"status": "pass", "provider_calls": 0, "failure_exercise": "failed", "recovery_exercise": "completed"}


def _verify_provider_cohort(value: dict[str, Any]) -> dict[str, Any]:
    _require(str(value.get("schema_version") or "") == "astrabridge-four-provider-reference-cohort-v1", "Unexpected provider cohort schema.")
    _require(str(value.get("status") or "") == "pass", "Provider cohort must pass deterministic checks.")
    _require(not bool(value.get("provider_calls_attempted")), "Provider cohort must not attempt provider calls.")
    _require(not bool(value.get("network_calls_attempted")), "Provider cohort must not attempt network calls.")
    routes = [dict(item) for item in list(value.get("routes") or [])]
    _require(len(routes) == 4, "Provider cohort must retain four route cards.")
    _require(all(str(route.get("classification") or "") == "reduced_authority" for route in routes), "Provider routes must remain reduced authority.")
    _require(str(dict(value.get("live_smoke") or {}).get("status") or "") == "deferred", "Provider live smoke must remain deferred.")
    return {"status": "pass", "route_count": len(routes), "classification": "reduced_authority", "live_smoke": "deferred"}


def _verify_gui_parity(value: dict[str, Any]) -> dict[str, Any]:
    _require(str(value.get("schema_version") or "") == "astrabridge-gui-code-orchestration-parity-evidence-v1", "Unexpected GUI parity schema.")
    _require(list(value.get("provider_calls") or []) == [], "GUI parity evidence must contain no provider calls.")
    _require(not bool(value.get("network_calls_attempted")), "GUI parity evidence must contain no network calls.")
    _require(str(dict(value.get("code_to_gui") or {}).get("status") or "") == "pass", "Code-to-GUI projection must pass.")
    _require(str(dict(value.get("runtime") or {}).get("fixture_run_status") or "") == "completed", "GUI parity fixture run must complete.")
    _require(str(dict(value.get("gui_to_code") or {}).get("round_trip_diff_status") or "") == "no_change", "GUI parity round trip must remain no_change.")
    _require(str(dict(dict(value.get("authority_boundary") or {}).get("blocked_gui_edit") or {}).get("status") or "") == "blocked_as_expected", "Source-owned GUI write must stay blocked.")
    return {"status": "pass", "provider_calls": 0, "fixture_run": "completed", "round_trip": "no_change"}


def _verify_extension(value: dict[str, Any]) -> dict[str, Any]:
    _require(str(value.get("schema_version") or "") == "astrabridge-first-contribution-extension-evidence-v1", "Unexpected extension evidence schema.")
    _require(str(value.get("mode") or "") == "deterministic_provider_free", "Extension evidence must remain provider-free.")
    _require(list(value.get("provider_calls") or []) == [], "Extension evidence must contain no provider calls.")
    _require(not bool(value.get("network_calls_attempted")), "Extension evidence must contain no network calls.")
    _require(str(dict(value.get("extension") or {}).get("classification") or "") == "experimental_candidate", "Extension must remain a candidate.")
    _require(str(dict(value.get("validation") or {}).get("status") or "") == "pass", "Extension validation must pass.")
    _require(str(dict(value.get("failure_boundary") or {}).get("status") or "") == "blocked", "Extension widening boundary must remain blocked.")
    return {"status": "warning_gated", "provider_calls": 0, "classification": "experimental_candidate", "widening_boundary": "blocked"}


def _verify_preview_baseline(value: dict[str, Any]) -> dict[str, Any]:
    _require(str(value.get("schema_version") or "") == "astrabridge-developer-preview-baseline-evidence-v1", "Unexpected preview baseline schema.")
    _require(str(value.get("mode") or "") == "deterministic_provider_free", "Preview baseline must remain provider-free.")
    _require(list(value.get("provider_calls") or []) == [], "Preview baseline must contain no provider calls.")
    _require(str(dict(value.get("package_contract") or {}).get("status") or "") == "pass", "Package contract must pass.")
    _require(str(dict(value.get("update_rehearsal") or {}).get("status") or "") == "pass", "Update rehearsal must pass.")
    release = dict(value.get("public_release") or {})
    _require(str(release.get("status") or "") == "blocked", "Public release must remain blocked.")
    _require(len(list(release.get("blockers") or [])) >= 5, "Public release must expose all owner gates.")
    return {"status": "blocked", "package_contract": "pass", "update_rehearsal": "pass", "release_blocker_count": len(list(release.get("blockers") or []))}


def _verify_security_scan(value: dict[str, Any], repository: Path) -> dict[str, Any]:
    _require(bool(value.get("ok")), "Security scan must pass.")
    counts = dict(value.get("counts") or {})
    _require(int(counts.get("error") or 0) == 0 and int(counts.get("warning") or 0) == 0, "Security scan must have no errors or warnings.")
    security = (repository / "SECURITY.md").read_text(encoding="utf-8")
    conduct = (repository / "CODE_OF_CONDUCT.md").read_text(encoding="utf-8")
    _require("private vulnerability-reporting channel\nhas not yet been configured" in security, "Security policy lost its explicit missing-route boundary.")
    _require("No private conduct-reporting contact has been configured yet." in conduct, "Conduct policy lost its explicit missing-route boundary.")
    return {"status": "pass", "scan_errors": 0, "scan_warnings": 0, "reporting_routes": "not_configured_release_blocker"}


def _public_card(card: dict[str, Any]) -> dict[str, Any]:
    reproduction = dict(card.get("reproduction") or {})
    return {
        "claim_id": str(card["claim_id"]),
        "claim": str(card["claim"]),
        "evidence_classification": str(card["evidence_classification"]),
        "result_state": str(card["result_state"]),
        "result_date": str(card["result_date"]),
        "owners": [str(value) for value in list(card["owners"])],
        "reproduction": {
            "public_sources": [str(value) for value in list(reproduction["public_sources"])],
            "artifact_contract": str(reproduction["artifact_contract"]),
            "test_command": str(reproduction["test_command"]),
        },
        "known_limitations": [str(value) for value in list(card["known_limitations"])],
        "failure_visibility": {str(key): str(value) for key, value in dict(card["failure_visibility"]).items()},
    }


def _read_json_object(path: Path, *, label: str) -> dict[str, Any]:
    _require(path.is_file(), f"Missing {label}: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid {label} JSON: {path}") from exc
    _require(isinstance(value, dict), f"{label.capitalize()} must be a JSON object.")
    return dict(value)


def _render_markdown(evidence: dict[str, Any]) -> str:
    dossier = dict(evidence.get("dossier") or {})
    negative = [dict(item) for item in list(dossier.get("negative_ledger") or [])]
    lines = [
        "# Public Quality and Reliability Dossier Evidence",
        "",
        f"- Cards: {dossier.get('card_count')}",
        f"- Positive cards: {dossier.get('positive_card_count')}",
        f"- Negative or bounded cards: {dossier.get('negative_card_count')}",
        "",
        "## Negative and bounded ledger",
        "",
    ]
    for card in negative:
        lines.append(f"- `{card.get('claim_id')}`: `{card.get('result_state')}` — {dict(card.get('failure_visibility') or {}).get('how_to_detect')}")
    lines.extend(
        [
            "",
            "This aggregation is provider-free and does not turn deterministic evidence into an installer, support, authority, or live-provider claim.",
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
    parser = argparse.ArgumentParser(description="Build the AstraBridge public quality and reliability dossier evidence packet.")
    parser.add_argument("--flagship-evidence", type=Path, required=True)
    parser.add_argument("--provider-cohort-report", type=Path, required=True)
    parser.add_argument("--gui-parity-evidence", type=Path, required=True)
    parser.add_argument("--extension-evidence", type=Path, required=True)
    parser.add_argument("--preview-baseline-evidence", type=Path, required=True)
    parser.add_argument("--security-scan-report", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args(argv)
    evidence = run_public_quality_reliability_dossier(
        args.output_root,
        flagship_evidence=args.flagship_evidence,
        provider_cohort_report=args.provider_cohort_report,
        gui_parity_evidence=args.gui_parity_evidence,
        extension_evidence=args.extension_evidence,
        preview_baseline_evidence=args.preview_baseline_evidence,
        security_scan_report=args.security_scan_report,
    )
    dossier = dict(evidence["dossier"])
    print(
        {
            "status": dossier.get("status"),
            "cards": dossier.get("card_count"),
            "negative_cards": dossier.get("negative_card_count"),
            "evidence": str((args.output_root / "evidence.json").resolve()),
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
