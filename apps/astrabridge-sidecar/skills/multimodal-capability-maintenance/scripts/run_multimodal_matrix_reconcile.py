from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def _bootstrap() -> Path:
    sidecar_root = Path(__file__).resolve().parents[3]
    if str(sidecar_root) not in sys.path:
        sys.path.insert(0, str(sidecar_root))
    return sidecar_root.parents[1]


REPO_ROOT = _bootstrap()

from astrabridge_sidecar.provider_capability_dry_run_matrix import (  # noqa: E402
    run_provider_capability_dry_run_matrix,
)
from astrabridge_sidecar.provider_capability_verification_gate import (  # noqa: E402
    run_provider_capability_verification_gate,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run multimodal dry-run matrix reconcile and optional verification gate.")
    parser.add_argument("--workspace-root", default=str(REPO_ROOT))
    parser.add_argument("--artifact-root", default=None)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--providers", default="yunwu,openai,qwen,deepseek,kimi,glm")
    parser.add_argument("--with-verification-gate", action="store_true")
    parser.add_argument("--skip-tests", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    workspace_root = Path(args.workspace_root).resolve()
    artifact_root = Path(args.artifact_root).resolve() if args.artifact_root else workspace_root / "PRIVATE" / "agentic-update-pipeline" / "runs" / args.run_id / "matrix"
    artifact_root.mkdir(parents=True, exist_ok=True)
    provider_ids = [item.strip() for item in str(args.providers or "").split(",") if item.strip()]

    dry_run = run_provider_capability_dry_run_matrix(
        workspace_root=workspace_root,
        artifact_root=artifact_root / "dry-run",
        run_id=f"{args.run_id}-dry-run",
        priority_provider_ids=provider_ids,
    )
    gate = None
    if args.with_verification_gate:
        gate = run_provider_capability_verification_gate(
            workspace_root=workspace_root,
            artifact_root=artifact_root / "verification-gate",
            run_id=f"{args.run_id}-verification-gate",
            include_tests=not args.skip_tests,
        )
    summary = {
        "schema_version": "astrabridge-multimodal-matrix-reconcile-v1",
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(),
        "run_id": args.run_id,
        "provider_ids": provider_ids,
        "dry_run_summary": {
            "status_counts": dry_run.get("matrix_overall_status_counts"),
            "exposure_counts": dry_run.get("matrix_exposure_state_counts"),
            "summary_json": dry_run.get("artifact_paths", {}).get("summary_json"),
            "report_md": dry_run.get("artifact_paths", {}).get("report_md"),
            "matrix_json": dry_run.get("artifact_paths", {}).get("matrix_json"),
        },
        "verification_gate": {
            "status": gate.get("status"),
            "summary_json": gate.get("artifact_paths", {}).get("summary_json"),
            "report_md": gate.get("artifact_paths", {}).get("report_md"),
        }
        if gate
        else None,
    }
    summary_path = artifact_root / "summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(str(summary_path))


if __name__ == "__main__":
    main()
