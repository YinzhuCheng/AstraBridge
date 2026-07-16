from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .agent_orchestration_checks import (
    diff_agent_orchestration_graph_files,
    dry_run_agent_orchestration_graph_file,
    lint_agent_orchestration_graph_file,
    migrate_task_graph_file_to_orchestration,
    render_agent_orchestration_report_markdown,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m astrabridge_sidecar.agent_orchestration_cli")
    subparsers = parser.add_subparsers(dest="command", required=True)

    lint_parser = subparsers.add_parser("lint", help="Lint an agent orchestration graph file.")
    lint_parser.add_argument("graph_file")
    lint_parser.add_argument("--markdown-out", dest="markdown_out")

    dry_run_parser = subparsers.add_parser("dry-run", help="Dry-run an agent orchestration graph file without live provider calls.")
    dry_run_parser.add_argument("graph_file")
    dry_run_parser.add_argument("--markdown-out", dest="markdown_out")

    diff_parser = subparsers.add_parser("diff", help="Diff two agent orchestration graph files.")
    diff_parser.add_argument("old_graph_file")
    diff_parser.add_argument("new_graph_file")
    diff_parser.add_argument("--markdown-out", dest="markdown_out")

    migrate_parser = subparsers.add_parser("migrate-task-graph", help="Lift a legacy task graph JSON file into the canonical agent orchestration graph format.")
    migrate_parser.add_argument("task_graph_file")
    migrate_parser.add_argument("--output", dest="output_path")
    migrate_parser.add_argument("--markdown-out", dest="markdown_out")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "lint":
        report = lint_agent_orchestration_graph_file(args.graph_file)
        _maybe_write_markdown(report, args.markdown_out)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    if args.command == "dry-run":
        report = dry_run_agent_orchestration_graph_file(args.graph_file)
        _maybe_write_markdown(report, args.markdown_out)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if str(report.get("status") or "") != "blocked" else 1
    if args.command == "diff":
        report = diff_agent_orchestration_graph_files(args.old_graph_file, args.new_graph_file)
        _maybe_write_markdown(report, args.markdown_out)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    if args.command == "migrate-task-graph":
        report = migrate_task_graph_file_to_orchestration(args.task_graph_file, output_path=args.output_path)
        _maybe_write_markdown(report, args.markdown_out)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    parser.error("Unknown command.")
    return 2


def _maybe_write_markdown(report: dict, output_path: str | None) -> None:
    if not output_path:
        return
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_agent_orchestration_report_markdown(report), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
