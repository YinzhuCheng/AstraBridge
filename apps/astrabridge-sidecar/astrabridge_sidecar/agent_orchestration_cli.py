from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .agent_orchestration_checks import (
    compile_agent_orchestration_graph_file,
    diff_agent_orchestration_graph_files,
    dry_run_agent_orchestration_graph_file,
    lint_agent_orchestration_graph_file,
    migrate_task_graph_file_to_orchestration,
    render_agent_orchestration_report_markdown,
)
from .skill_orchestration_validation import (
    compile_skill_orchestration,
    diff_skill_orchestrations,
    dry_run_skill_orchestration,
    lint_skill_orchestration,
    render_skill_orchestration_report_markdown,
    validate_skill_orchestration,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m astrabridge_sidecar.agent_orchestration_cli")
    subparsers = parser.add_subparsers(dest="command", required=True)

    lint_parser = subparsers.add_parser("lint", help="Lint an agent orchestration graph file.")
    lint_parser.add_argument("graph_file")
    lint_parser.add_argument("--markdown-out", dest="markdown_out")

    compile_parser = subparsers.add_parser("compile", help="Compile an agent orchestration graph file into a canonical execution plan.")
    compile_parser.add_argument("graph_file")
    compile_parser.add_argument("--markdown-out", dest="markdown_out")

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

    for command, help_text in (
        ("skill-lint", "Lint a skill-backed orchestration without live calls."),
        ("skill-compile", "Compile a skill-backed orchestration without live calls."),
        ("skill-dry-run", "Dry-run a skill-backed orchestration without live calls."),
        ("skill-validate", "Run resolution, lint, compile, and dry-run checks for a skill."),
    ):
        skill_parser = subparsers.add_parser(command, help=help_text)
        skill_parser.add_argument("skill_ref")
        skill_parser.add_argument("--parameters-json", dest="parameters_json")
        skill_parser.add_argument("--parameters-file", dest="parameters_file")
        skill_parser.add_argument("--markdown-out", dest="markdown_out")

    skill_diff_parser = subparsers.add_parser("skill-diff", help="Diff two skill-backed orchestration resolutions.")
    skill_diff_parser.add_argument("old_skill_ref")
    skill_diff_parser.add_argument("new_skill_ref")
    skill_diff_parser.add_argument("--old-parameters-json", dest="old_parameters_json")
    skill_diff_parser.add_argument("--new-parameters-json", dest="new_parameters_json")
    skill_diff_parser.add_argument("--old-parameters-file", dest="old_parameters_file")
    skill_diff_parser.add_argument("--new-parameters-file", dest="new_parameters_file")
    skill_diff_parser.add_argument("--markdown-out", dest="markdown_out")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "lint":
        report = lint_agent_orchestration_graph_file(args.graph_file)
        _maybe_write_markdown(report, args.markdown_out)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    if args.command == "compile":
        report = compile_agent_orchestration_graph_file(args.graph_file)
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
    if args.command in {"skill-lint", "skill-compile", "skill-dry-run", "skill-validate"}:
        parameters = _load_parameters(args.parameters_json, args.parameters_file)
        operation = args.command.removeprefix("skill-").replace("-", "_")
        operation_fn = {
            "lint": lint_skill_orchestration,
            "compile": compile_skill_orchestration,
            "dry_run": dry_run_skill_orchestration,
            "validate": validate_skill_orchestration,
        }[operation]
        report = operation_fn(args.skill_ref, parameters)
        _maybe_write_skill_markdown(report, args.markdown_out)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if str(report.get("status") or "") != "blocked" else 1
    if args.command == "skill-diff":
        old_parameters = _load_parameters(args.old_parameters_json, args.old_parameters_file)
        new_parameters = _load_parameters(args.new_parameters_json, args.new_parameters_file)
        report = diff_skill_orchestrations(args.old_skill_ref, args.new_skill_ref, old_parameters, new_parameters)
        _maybe_write_skill_markdown(report, args.markdown_out)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if str(report.get("status") or "") != "blocked" else 1
    parser.error("Unknown command.")
    return 2


def _maybe_write_markdown(report: dict, output_path: str | None) -> None:
    if not output_path:
        return
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_agent_orchestration_report_markdown(report), encoding="utf-8")


def _maybe_write_skill_markdown(report: dict, output_path: str | None) -> None:
    if not output_path:
        return
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_skill_orchestration_report_markdown(report), encoding="utf-8")


def _load_parameters(parameters_json: str | None, parameters_file: str | None) -> dict | None:
    if parameters_json and parameters_file:
        raise SystemExit("Use only one of --parameters-json and --parameters-file.")
    if parameters_file:
        return json.loads(Path(parameters_file).read_text(encoding="utf-8"))
    if parameters_json:
        return json.loads(parameters_json)
    return None


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
