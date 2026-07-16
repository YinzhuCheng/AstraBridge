from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SIDECAR_ROOT = REPO_ROOT / "apps" / "astrabridge-sidecar"
sys.path.insert(0, str(SIDECAR_ROOT))

from astrabridge_sidecar.provider_capability_verification_gate import run_provider_capability_verification_gate


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the AstraBridge provider capability verification gate.")
    parser.add_argument("--workspace-root", default=str(REPO_ROOT), help="Workspace root used for PRIVATE/** artifacts.")
    parser.add_argument("--artifact-root", default=None, help="Optional explicit artifact root for the gate summary.")
    parser.add_argument("--run-id", default=None, help="Optional run identifier.")
    parser.add_argument("--baseline", default=None, help="Optional path to a verification baseline JSON file.")
    parser.add_argument("--skip-tests", action="store_true", help="Skip unittest groups and evaluate only the dry-run matrix against the baseline.")
    args = parser.parse_args(argv)

    summary = run_provider_capability_verification_gate(
        workspace_root=Path(args.workspace_root),
        artifact_root=args.artifact_root,
        run_id=args.run_id,
        baseline_path=args.baseline,
        include_tests=not args.skip_tests,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if str(summary.get("status") or "") == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
