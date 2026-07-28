from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


SIDECAR_ROOT = Path(__file__).resolve().parents[3]
if str(SIDECAR_ROOT) not in sys.path:
    sys.path.insert(0, str(SIDECAR_ROOT))

from astrabridge_sidecar.agentic_updates.artifacts import ensure_agentic_update_run_layout  # noqa: E402
from astrabridge_sidecar.agentic_updates.contracts import (  # noqa: E402
    assert_secret_free_agentic_update_payload,
    normalize_update_scope_contract,
)
from astrabridge_sidecar.common import now_iso, write_json  # noqa: E402
from astrabridge_sidecar.model_catalog.generated_catalog import current_generated_catalog  # noqa: E402
from astrabridge_sidecar.providers.reference_cohort import build_reference_cohort_report  # noqa: E402

from run_four_provider_fixture_coverage import run_coverage  # noqa: E402


def run_cohort(*, workspace_root: Path, run_id: str) -> dict[str, Any]:
    """Run the bounded provider-free Step 12 cohort and preserve its evidence."""

    layout = ensure_agentic_update_run_layout(workspace_root, run_id)
    run_contract = normalize_update_scope_contract(
        {
            "scope": ["provider_metadata", "provider_adapter", "execution_routes"],
            "providers": ["qwen", "deepseek", "kimi", "glm"],
            "models": [
                "qwen/qwen3.7-plus",
                "deepseek/deepseek-v4-pro",
                "kimi/kimi-k3",
                "glm/glm-5.2",
            ],
            "version_policy": "stable",
            "apply_mode": "verify_candidate",
            "allow_network": False,
            "allow_provider_calls": False,
            "allow_install": False,
            "allow_code_changes": False,
            "approval_policy": "manual_review_required",
        }
    )
    run_contract["cohort_mode"] = "deterministic_provider_free"
    run_contract["live_smoke"] = "deferred_pending_explicit_current_turn_authorization"
    assert_secret_free_agentic_update_payload(run_contract, label="four_provider_reference_cohort_contract")
    run_contract_path = Path(layout["files"]["run_contract"])
    write_json(run_contract_path, run_contract)

    parser_coverage = run_coverage(workspace_root=workspace_root, run_id=run_id)
    corpus_path = SIDECAR_ROOT / "tests" / "fixtures" / "provider_semantic_conformance_v1.json"
    semantic_corpus = json.loads(corpus_path.read_text(encoding="utf-8"))
    report = build_reference_cohort_report(
        catalog_models=current_generated_catalog().models,
        semantic_corpus=semantic_corpus,
        run_id=run_id,
        ledger_root=Path(layout["run_root"]) / "validation" / "reference-cohort-ledgers",
        parser_coverage=parser_coverage,
    )
    report = {
        **report,
        "generated_at": now_iso(),
        "artifact_paths": {
            "run_contract": str(run_contract_path),
            "parser_coverage": str(parser_coverage["artifact_paths"]["coverage_report"]),
            "semantic_corpus": str(corpus_path),
            "reference_cohort": str(Path(layout["run_root"]) / "validation" / "reference-cohort.json"),
        },
    }
    assert_secret_free_agentic_update_payload(report, label="four_provider_reference_cohort")
    report_path = Path(report["artifact_paths"]["reference_cohort"])
    write_json(report_path, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the deterministic four-provider/Kimi K3 reference cohort without provider calls.")
    parser.add_argument("--workspace-root", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    report = run_cohort(workspace_root=args.workspace_root.resolve(), run_id=str(args.run_id))
    print(
        {
            "status": report["status"],
            "classifications": report["classification_summary"],
            "report": report["artifact_paths"]["reference_cohort"],
        }
    )
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
