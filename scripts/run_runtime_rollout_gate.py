from __future__ import annotations

import argparse
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SIDECAR_ROOT = REPO_ROOT / "apps" / "astrabridge-sidecar"
if str(SIDECAR_ROOT) not in sys.path:
    sys.path.insert(0, str(SIDECAR_ROOT))

from astrabridge_sidecar.common import emit_json_stdout
from astrabridge_sidecar.runtime_rollout_gate import run_runtime_rollout_gate


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the AstraBridge runtime rollout gate.")
    parser.add_argument("--workspace-root", default=str(REPO_ROOT), help="Workspace root used for PRIVATE/runtime-rollout artifacts.")
    parser.add_argument("--artifact-root", default=None, help="Optional explicit artifact root for the rollout summary.")
    parser.add_argument("--run-id", default=None, help="Optional run identifier.")
    parser.add_argument("--skip-release-gate", action="store_true", help="Skip the nested runtime stability release gate.")
    parser.add_argument("--skip-desktop-build", action="store_true", help="Skip the desktop production build step.")
    parser.add_argument("--skip-desktop-visual-qa", action="store_true", help="Skip the Desktop screenshot capture step.")
    parser.add_argument("--dogfood-source-workspace", default=None, help="Optional source workspace copied into the bounded dogfood migration lane.")
    args = parser.parse_args(argv)

    summary = run_runtime_rollout_gate(
        workspace_root=Path(args.workspace_root),
        artifact_root=args.artifact_root,
        run_id=args.run_id,
        include_release_gate=not args.skip_release_gate,
        include_desktop_build=not args.skip_desktop_build,
        include_desktop_visual_qa=not args.skip_desktop_visual_qa,
        dogfood_source_workspace=args.dogfood_source_workspace,
    )
    emit_json_stdout(summary)
    return 0 if str(summary.get("status") or "") == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
