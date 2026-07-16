from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "astrabridge-sidecar"))

from astrabridge_sidecar.security import DESKTOP_KEY_PATH_RE, SECRET_RE, SECRET_QUERY_RE  # noqa: E402


TEXT_SUFFIXES = {".json", ".md", ".txt", ".yaml", ".yml", ".log"}


def collect_files(paths: list[Path]) -> list[Path]:
    collected: list[Path] = []
    for path in paths:
        if path.is_file():
            collected.append(path)
            continue
        if not path.exists():
            continue
        for candidate in sorted(path.rglob("*")):
            if candidate.is_file() and candidate.suffix.lower() in TEXT_SUFFIXES:
                collected.append(candidate)
    return collected


def scan_file(path: Path) -> list[dict[str, str]]:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return []
    findings: list[dict[str, str]] = []
    if DESKTOP_KEY_PATH_RE.search(text):
        findings.append({"path": str(path), "kind": "desktop_key_path"})
    if SECRET_QUERY_RE.search(text):
        findings.append({"path": str(path), "kind": "secret_query_parameter"})
    if SECRET_RE.search(text):
        findings.append({"path": str(path), "kind": "secret_like_token"})
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description="Focused secret scan for task-graph snapshots, prompts, and evidence.")
    parser.add_argument("paths", nargs="+", help="Files or directories to scan.")
    parser.add_argument("--output", dest="output_path", help="Optional JSON report output path.")
    args = parser.parse_args()

    scan_paths = [Path(item).resolve() for item in args.paths]
    files = collect_files(scan_paths)
    findings: list[dict[str, str]] = []
    for path in files:
        findings.extend(scan_file(path))
    report = {
        "schema_version": "astrabridge-agent-orchestration-secret-scan-v1",
        "status": "fail" if findings else "pass",
        "scanned_paths": [str(path) for path in scan_paths],
        "checked_file_count": len(files),
        "checked_files": [str(path) for path in files],
        "finding_count": len(findings),
        "findings": findings,
    }
    if args.output_path:
        output_path = Path(args.output_path).resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
