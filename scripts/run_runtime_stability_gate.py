from __future__ import annotations

import argparse
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SIDECAR_ROOT = REPO_ROOT / "apps" / "astrabridge-sidecar"
if str(SIDECAR_ROOT) not in sys.path:
    sys.path.insert(0, str(SIDECAR_ROOT))

from astrabridge_sidecar.common import emit_json_stdout
from astrabridge_sidecar.runtime_stability_gate import run_runtime_stability_gate


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the AstraBridge runtime stability gate.")
    parser.add_argument("--workspace-root", default=str(REPO_ROOT), help="Workspace root used for PRIVATE/runtime-stability artifacts.")
    parser.add_argument("--artifact-root", default=None, help="Optional explicit artifact root for the gate summary.")
    parser.add_argument("--run-id", default=None, help="Optional run identifier.")
    parser.add_argument("--mode", choices=("fast", "release"), default="release", help="Gate mode: fast for the normal gate, release for the conformance gate.")
    parser.add_argument("--skip-fixture-evidence", action="store_true", help="Skip deterministic fixture evidence capture.")
    parser.add_argument("--skip-process-inventory", action="store_true", help="Skip before/after process inventory capture.")
    args = parser.parse_args(argv)

    summary = run_runtime_stability_gate(
        workspace_root=Path(args.workspace_root),
        artifact_root=args.artifact_root,
        run_id=args.run_id,
        mode=args.mode,
        include_fixture_evidence=not args.skip_fixture_evidence,
        include_process_inventory=not args.skip_process_inventory,
    )
    emit_json_stdout(summary)
    return 0 if str(summary.get("status") or "") == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
