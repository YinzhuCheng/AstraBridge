from __future__ import annotations

import argparse
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SIDECAR_ROOT = REPO_ROOT / "apps" / "astrabridge-sidecar"
if str(SIDECAR_ROOT) not in sys.path:
    sys.path.insert(0, str(SIDECAR_ROOT))

from astrabridge_sidecar.common import emit_json_stdout
from astrabridge_sidecar.promotion_gate import run_promotion_gate


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the AstraBridge promotion gate.")
    parser.add_argument("--mode", choices=("pr", "nightly", "release"), default="pr", help="Promotion mode to evaluate.")
    parser.add_argument("--workspace-root", default=str(REPO_ROOT), help="Workspace root used for PRIVATE/promotion-gates artifacts.")
    parser.add_argument("--artifact-root", default=None, help="Optional explicit artifact root for the promotion gate.")
    parser.add_argument("--run-id", default=None, help="Optional run identifier.")
    parser.add_argument("--expected-commit", default=None, help="Commit SHA that the promotion summary must be bound to.")
    parser.add_argument("--allow-dirty", action="store_true", help="Allow a dirty worktree for local diagnostics.")
    args = parser.parse_args(argv)

    summary = run_promotion_gate(
        mode=args.mode,
        workspace_root=Path(args.workspace_root),
        artifact_root=args.artifact_root,
        run_id=args.run_id,
        expected_commit=args.expected_commit,
        allow_dirty=args.allow_dirty,
    )
    emit_json_stdout(summary)
    return 0 if str(summary.get("status") or "") == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
