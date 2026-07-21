from __future__ import annotations

import argparse
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SIDECAR_ROOT = REPO_ROOT / "apps" / "astrabridge-sidecar"
sys.path.insert(0, str(SIDECAR_ROOT))

from astrabridge_sidecar.common import emit_json_stdout  # noqa: E402
from astrabridge_sidecar.skill_orchestration_dogfood import run_skill_orchestration_dogfood  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run provider-free realistic dogfood workflows through AstraBridge MCP skill orchestration.")
    parser.add_argument("--artifact-root", default=None, help="Optional explicit artifact root.")
    parser.add_argument("--run-id", default=None, help="Optional run identifier.")
    parser.add_argument("--case-id", action="append", default=[], help="Run one or more finite case IDs; repeat for multiple cases.")
    parser.add_argument("--repo-root", default=str(REPO_ROOT), help="Repository root used for read-only workflow references.")
    args = parser.parse_args(argv)
    summary = run_skill_orchestration_dogfood(
        artifact_root=args.artifact_root,
        run_id=args.run_id,
        case_ids=args.case_id,
        repo_root=args.repo_root,
    )
    emit_json_stdout(summary)
    return 0 if str(summary.get("status") or "") == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
