from __future__ import annotations

import argparse
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SIDECAR_ROOT = REPO_ROOT / "apps" / "astrabridge-sidecar"
if str(SIDECAR_ROOT) not in sys.path:
    sys.path.insert(0, str(SIDECAR_ROOT))

from astrabridge_sidecar.common import emit_json_stdout
from astrabridge_sidecar.release_identity import run_release_readiness_gate


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the AstraBridge release readiness gate.")
    parser.add_argument("--workspace-root", default=str(REPO_ROOT), help="Workspace root used for release staging and readiness artifacts.")
    parser.add_argument("--artifact-root", default=None, help="Optional explicit artifact root for the readiness gate.")
    parser.add_argument("--run-id", default=None, help="Optional run identifier.")
    args = parser.parse_args(argv)

    summary = run_release_readiness_gate(
        repo_root=Path(args.workspace_root),
        artifact_root=args.artifact_root,
        run_id=args.run_id,
    )
    emit_json_stdout(summary)
    return 0 if str(summary.get("status") or "") == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
