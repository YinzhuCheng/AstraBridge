from __future__ import annotations

import argparse
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SIDECAR_ROOT = REPO_ROOT / "apps" / "astrabridge-sidecar"
if str(SIDECAR_ROOT) not in sys.path:
    sys.path.insert(0, str(SIDECAR_ROOT))

from astrabridge_sidecar.common import emit_json_stdout  # noqa: E402
from astrabridge_sidecar.skill_orchestration_evaluation_gate import run_skill_orchestration_evaluation_gate  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the AstraBridge skill orchestration evaluation/promotion gate.")
    parser.add_argument("--mode", choices=("evaluate", "promotion"), default="evaluate")
    parser.add_argument(
        "--artifact-root",
        default=str(REPO_ROOT / "PRIVATE" / "skill-first-orchestration" / "evaluation"),
        help="Root directory under which the run-specific evidence bundle is preserved.",
    )
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--skill-id", action="append", dest="skill_ids", default=None)
    parser.add_argument("--no-fixture-runs", action="store_true", help="Skip fixture execution for a diagnostic-only run.")
    args = parser.parse_args(argv)

    summary = run_skill_orchestration_evaluation_gate(
        mode=args.mode,
        artifact_root=Path(args.artifact_root),
        run_id=args.run_id,
        skill_ids=args.skill_ids,
        fixture_runs=not args.no_fixture_runs,
    )
    emit_json_stdout(summary)
    return 0 if str(summary.get("status") or "") == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
