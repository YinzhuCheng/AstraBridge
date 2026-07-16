from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def npm_command() -> str:
    return "npm.cmd" if os.name == "nt" else "npm"


def run_command(command: list[str], cwd: Path, dry_run: bool) -> int:
    display = " ".join(command)
    print(f"\n$ {display}\n  cwd: {cwd}")
    if dry_run:
        return 0
    completed = subprocess.run(command, cwd=cwd)
    return completed.returncode


def quick_commands() -> list[tuple[list[str], Path]]:
    return [
        ([sys.executable, "scripts/repo_governance_check.py", "--repo", "."], REPO_ROOT),
        ([sys.executable, "scripts/app_hardening_secret_scan.py", "--repo", "."], REPO_ROOT),
        ([sys.executable, "scripts/contract_boundary_audit.py"], REPO_ROOT),
        (
            [
                sys.executable,
                "-m",
                "unittest",
                "discover",
                "-s",
                "apps/astrabridge-sidecar/tests",
                "-p",
                "test_repo_governance_check.py",
            ],
            REPO_ROOT,
        ),
        (
            [
                sys.executable,
                "-m",
                "unittest",
                "discover",
                "-s",
                "apps/astrabridge-sidecar/tests",
                "-p",
                "test_app_hardening_secret_scan.py",
            ],
            REPO_ROOT,
        ),
    ]


def full_commands() -> list[tuple[list[str], Path]]:
    desktop = REPO_ROOT / "apps" / "astrabridge-desktop"
    return [
        *quick_commands(),
        (
            [
                sys.executable,
                "-m",
                "unittest",
                "discover",
                "-s",
                "apps/astrabridge-sidecar/tests",
            ],
            REPO_ROOT,
        ),
        ([npm_command(), "run", "test"], desktop),
        ([npm_command(), "run", "build"], desktop),
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run AstraBridge local verification gates.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--quick", action="store_true", help="Run governance checks and governance tests.")
    group.add_argument("--full", action="store_true", help="Run governance, sidecar tests, desktop tests, and desktop build.")
    parser.add_argument("--dry-run", action="store_true", help="Print commands without executing them.")
    args = parser.parse_args(argv)

    commands = full_commands() if args.full else quick_commands()
    for command, cwd in commands:
        code = run_command(command, cwd, args.dry_run)
        if code != 0:
            print(f"\nLocal gate failed with exit code {code}: {' '.join(command)}")
            return code
    print("\nLocal gate passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
