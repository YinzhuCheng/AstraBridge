from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
SIDECAR_ROOT = REPO_ROOT / "apps" / "astrabridge-sidecar"
sys.path.insert(0, str(SIDECAR_ROOT))

from astrabridge_sidecar.agentic_updates import run_agentic_update_fixture_dogfood


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the offline Step 18 agentic update fixture dogfood.")
    parser.add_argument("--workspace-root", default=str(REPO_ROOT), help="AstraBridge workspace root.")
    parser.add_argument("--run-id", default=None, help="Optional deterministic run id.")
    parser.add_argument("--no-screenshot", action="store_true", help="Skip Playwright screenshot capture.")
    args = parser.parse_args()

    report = run_agentic_update_fixture_dogfood(
        workspace_root=Path(args.workspace_root).resolve(),
        run_id=args.run_id,
        capture_screenshot=not args.no_screenshot,
    )
    print(
        json.dumps(
            {
                "run_id": report["run_id"],
                "status": report["status"],
                "summary": report["summary"],
                "artifact_paths": report["artifact_paths"],
            },
            ensure_ascii=True,
            indent=2,
        )
    )
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
