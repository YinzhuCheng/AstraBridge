from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SIDECAR_ROOT = REPO_ROOT / "apps" / "astrabridge-sidecar"
if str(SIDECAR_ROOT) not in sys.path:
    sys.path.insert(0, str(SIDECAR_ROOT))

from astrabridge_sidecar.common import emit_json_stdout  # noqa: E402
from astrabridge_sidecar.release_identity import run_windows_update_rehearsal  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the AstraBridge isolated Windows update rehearsal.")
    parser.add_argument("--artifact-root", default=None, help="Optional artifact root. Defaults to PRIVATE/release-readiness.")
    parser.add_argument("--run-id", default=None, help="Optional stable run id.")
    parser.add_argument("--channel", default=None, choices=("stable", "beta", "canary"), help="Optional explicit rehearsal channel override.")
    args = parser.parse_args()

    project = {"ui_preferences": {"update_channel": args.channel}} if args.channel else None
    result = run_windows_update_rehearsal(
        repo_root=REPO_ROOT,
        artifact_root=args.artifact_root,
        project=project,
        run_id=args.run_id,
    )
    emit_json_stdout(result)
    return 0 if str(result.get("status") or "fail") == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
