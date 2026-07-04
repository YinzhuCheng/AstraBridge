from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Sequence

from .common import append_jsonl, new_id, now_iso, write_json
from .security import redact_sensitive, resolve_under


SKILL_PLUGIN_CREATOR_SCENARIO_SCHEMA_VERSION = "astrabridge-skill-plugin-creator-scenario-v1"
REAL_SCENARIO_DOGFOOD_REPORT_SCHEMA_VERSION = "astrabridge-real-scenario-dogfood-report-v1"
REAL_SCENARIO_DOGFOOD_PLAN_ID = "capability_real_scenario_dogfood"
DEFAULT_SKILL_TRIGGER_PATH = "能力 -> 技能 -> Plugin Creator"

SubprocessRunFn = Callable[..., Any]

_TRACKED_FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "skill_plugin_creator_fixture"
_DEFAULT_REPORT_DIR_REL = Path("apps") / "astrabridge-desktop" / "output" / "playwright" / "real-scenario-dogfood"


def load_skill_plugin_creator_fixture_contract(
    fixture_root: Path | None = None,
) -> tuple[dict[str, Any], Path]:
    root = Path(fixture_root or _TRACKED_FIXTURE_ROOT).expanduser().resolve()
    contract_path = root / "fixture-contract.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    return contract, contract_path


def execute_plugin_creator_skill_scenario(
    *,
    workspace_root: Path,
    fixture_root: Path | None = None,
    skill_root: Path | None = None,
    skill_record_id: str | None = None,
    skill_display_name: str | None = None,
    python_executable: str | None = None,
    subprocess_run: SubprocessRunFn = subprocess.run,
) -> dict[str, Any]:
    started_at = now_iso()
    execution_id = new_id("skill-plugin-creator")
    workspace_root = Path(workspace_root).expanduser().resolve()
    contract, contract_path = load_skill_plugin_creator_fixture_contract(fixture_root)
    contract_root = contract_path.parent
    skill_payload = dict(contract.get("skill") or {})
    input_payload = dict(contract.get("input") or {})
    output_payload = dict(contract.get("output") or {})
    verification_payload = dict(contract.get("verification") or {})

    run_root = resolve_under(workspace_root, Path(str(output_payload.get("run_root_rel") or "")))
    execution_root = resolve_under(run_root, Path("executions") / execution_id)
    execution_root.mkdir(parents=True, exist_ok=True)
    events_path = execution_root / "events.jsonl"
    result_path = execution_root / "result.json"
    report_seed_path = execution_root / "dogfood-report-seed.json"

    brief_path = resolve_under(contract_root, Path(str(input_payload.get("brief_path_rel") or "")))
    plugin_root = resolve_under(workspace_root, Path(str(output_payload.get("plugin_root_rel") or "")))
    plugin_parent = resolve_under(workspace_root, Path(str(output_payload.get("plugin_parent_rel") or "")))
    manifest_path = resolve_under(workspace_root, Path(str(output_payload.get("manifest_path_rel") or "")))
    marketplace_path = resolve_under(workspace_root, Path(str(output_payload.get("marketplace_path_rel") or "")))
    required_paths = [
        resolve_under(workspace_root, Path(str(item)))
        for item in list(output_payload.get("required_paths_rel") or [])
        if str(item).strip()
    ]
    report_dir = resolve_under(workspace_root, _DEFAULT_REPORT_DIR_REL)
    report_seed = _report_seed(
        report_dir=report_dir,
        expected_screenshots=list(((contract.get("ui_evidence") or {}).get("expected_screenshots") or [])),
    )

    resolved_skill_root = Path(skill_root or _default_plugin_creator_skill_root()).expanduser().resolve()
    create_script = resolved_skill_root / "scripts" / "create_basic_plugin.py"
    validate_script = resolved_skill_root / "scripts" / "validate_plugin.py"
    plugin_name = str(output_payload.get("plugin_name") or "").strip()

    result: dict[str, Any] = {
        "schema_version": SKILL_PLUGIN_CREATOR_SCENARIO_SCHEMA_VERSION,
        "execution_id": execution_id,
        "scenario_id": str(contract.get("scenario_id") or "skills_plugin_creator_fixture_scaffold"),
        "capability": "skills",
        "skill_name": str(skill_payload.get("skill_name") or "plugin-creator"),
        "skill_display_name": skill_display_name or str(skill_payload.get("display_name") or "Plugin Creator"),
        "skill_record_id": skill_record_id,
        "started_at": started_at,
        "completed_at": started_at,
        "status": "failed",
        "failure_reason": "",
        "input": {
            "fixture_contract_path": str(contract_path),
            "brief_path": str(brief_path),
        },
        "output": {
            "run_root": str(run_root),
            "execution_root": str(execution_root),
            "plugin_root": str(plugin_root),
            "manifest_path": str(manifest_path),
            "marketplace_path": str(marketplace_path),
            "required_paths": [str(path) for path in required_paths],
        },
        "artifact_paths": {
            "events_path": str(events_path),
            "result_path": str(result_path),
            "report_seed_path": str(report_seed_path),
        },
        "verification_commands": [],
        "command_results": [],
        "checks": [],
        "notes": [
            "This execution is the controlled backend path for the Plugin Creator skill scenario.",
            "UI screenshots and final in-app acceptance remain reserved for later plan steps.",
        ],
        "report_seed": report_seed,
    }
    _append_event(events_path, {"event": "execution_started", "scenario_id": result["scenario_id"]})

    preflight_error = _preflight_failure(
        brief_path=brief_path,
        skill_root=resolved_skill_root,
        create_script=create_script,
        validate_script=validate_script,
        plugin_name=plugin_name,
    )
    if preflight_error:
        result["failure_reason"] = preflight_error
        result["completed_at"] = now_iso()
        result["checks"].append({"label": "preflight", "passed": False, "message": preflight_error})
        write_json(report_seed_path, redact_sensitive(report_seed))
        return _write_result(result_path, result)

    create_command = [
        python_executable or sys.executable,
        str(create_script),
        plugin_name,
        "--path",
        str(plugin_parent),
        "--marketplace-path",
        str(marketplace_path),
        "--with-skills",
        "--with-scripts",
        "--with-assets",
        "--with-mcp",
        "--with-apps",
        "--with-marketplace",
        "--force",
    ]
    create_result = _run_command(
        create_command,
        cwd=workspace_root,
        execution_root=execution_root,
        label="create-plugin",
        subprocess_run=subprocess_run,
    )
    result["verification_commands"].append(
        {
            "command": create_result["command"],
            "cwd": str(workspace_root),
            "exit_code": create_result["exit_code"],
            "summary": "Scaffold the controlled demo plugin under the PRIVATE/demo-runs skill scenario root.",
        }
    )
    result["command_results"].append(create_result)
    _append_event(events_path, {"event": "create_plugin_finished", "exit_code": create_result["exit_code"]})

    if create_result["exit_code"] != 0:
        result["failure_reason"] = f"create_basic_plugin.py exited with code {create_result['exit_code']}."
        result["checks"].append({"label": "create-plugin", "passed": False, "message": result["failure_reason"]})
        result["completed_at"] = now_iso()
        write_json(report_seed_path, redact_sensitive(report_seed))
        return _write_result(result_path, result)

    validate_command = [
        python_executable or sys.executable,
        str(validate_script),
        str(plugin_root),
    ]
    validate_result = _run_command(
        validate_command,
        cwd=workspace_root,
        execution_root=execution_root,
        label="validate-plugin",
        subprocess_run=subprocess_run,
    )
    result["verification_commands"].append(
        {
            "command": validate_result["command"],
            "cwd": str(workspace_root),
            "exit_code": validate_result["exit_code"],
            "summary": "Validate the generated plugin manifest and scaffold contract.",
        }
    )
    result["command_results"].append(validate_result)
    _append_event(events_path, {"event": "validate_plugin_finished", "exit_code": validate_result["exit_code"]})

    checks = _collect_checks(
        manifest_path=manifest_path,
        marketplace_path=marketplace_path,
        plugin_root=plugin_root,
        plugin_name=plugin_name,
        required_paths=required_paths,
        required_manifest_fields=list(verification_payload.get("required_manifest_fields") or []),
    )
    result["checks"].extend(checks)
    failed_checks = [check for check in checks if not bool(check.get("passed"))]

    if validate_result["exit_code"] != 0:
        result["failure_reason"] = f"validate_plugin.py exited with code {validate_result['exit_code']}."
    elif failed_checks:
        result["failure_reason"] = str(failed_checks[0].get("message") or "Scenario output checks failed.")
    else:
        result["status"] = "pass"
        result["failure_reason"] = ""

    result["completed_at"] = now_iso()
    write_json(report_seed_path, redact_sensitive(report_seed))
    return _write_result(result_path, result)


def build_plugin_creator_skill_dogfood_report(
    *,
    execution_result: dict[str, Any],
    screenshots: list[dict[str, Any]],
    step_id: str = "step_12",
    trigger_path: str = DEFAULT_SKILL_TRIGGER_PATH,
    status: str | None = None,
    notes: list[str] | None = None,
) -> dict[str, Any]:
    normalized_status = status or ("pass" if str(execution_result.get("status") or "") == "pass" else "fail")
    artifacts = _report_artifacts(execution_result)
    report: dict[str, Any] = {
        "schema_version": REAL_SCENARIO_DOGFOOD_REPORT_SCHEMA_VERSION,
        "plan_id": REAL_SCENARIO_DOGFOOD_PLAN_ID,
        "step_id": step_id,
        "capability": "skills",
        "scenario_id": str(execution_result.get("scenario_id") or "skills_plugin_creator_fixture_scaffold"),
        "trigger_path": trigger_path,
        "status": normalized_status,
        "started_at": str(execution_result.get("started_at") or now_iso()),
        "completed_at": str(execution_result.get("completed_at") or now_iso()),
        "run_id": str(execution_result.get("execution_id") or ""),
        "screenshots": [
            {
                "kind": str(item.get("kind") or "reference"),
                "path": str(item.get("path") or ""),
                **({"note": str(item.get("note") or "")} if str(item.get("note") or "").strip() else {}),
            }
            for item in screenshots
        ],
        "artifacts": artifacts,
        "verification_commands": [
            {
                "command": str(item.get("command") or ""),
                "cwd": str(item.get("cwd") or ""),
                **({"exit_code": int(item["exit_code"])} if item.get("exit_code") is not None else {}),
                "summary": str(item.get("summary") or ""),
            }
            for item in list(execution_result.get("verification_commands") or [])
        ],
        "notes": [*list(execution_result.get("notes") or []), *list(notes or [])],
    }
    if execution_result.get("skill_record_id"):
        report["record_id"] = str(execution_result.get("skill_record_id") or "")
    if normalized_status in {"fail", "timeout"}:
        report["failure_reason"] = str(
            execution_result.get("failure_reason")
            or "Skill scenario execution failed before producing a valid plugin scaffold."
        )
    return redact_sensitive(report)


def write_plugin_creator_skill_dogfood_report(
    report_path: Path,
    *,
    execution_result: dict[str, Any],
    screenshots: list[dict[str, Any]],
    step_id: str = "step_12",
    trigger_path: str = DEFAULT_SKILL_TRIGGER_PATH,
    status: str | None = None,
    notes: list[str] | None = None,
) -> dict[str, Any]:
    report = build_plugin_creator_skill_dogfood_report(
        execution_result=execution_result,
        screenshots=screenshots,
        step_id=step_id,
        trigger_path=trigger_path,
        status=status,
        notes=notes,
    )
    write_json(report_path, report)
    return report


def _default_plugin_creator_skill_root() -> Path:
    codex_home = Path(os.environ.get("CODEX_HOME") or (Path.home() / ".codex")).expanduser().resolve()
    return codex_home / "skills" / ".system" / "plugin-creator"


def _run_command(
    command: Sequence[str],
    *,
    cwd: Path,
    execution_root: Path,
    label: str,
    subprocess_run: SubprocessRunFn,
) -> dict[str, Any]:
    stdout_path = execution_root / f"{label}.stdout.txt"
    stderr_path = execution_root / f"{label}.stderr.txt"
    completed = subprocess_run(
        list(command),
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    stdout_text = str(getattr(completed, "stdout", "") or "")
    stderr_text = str(getattr(completed, "stderr", "") or "")
    stdout_path.write_text(stdout_text, encoding="utf-8")
    stderr_path.write_text(stderr_text, encoding="utf-8")
    return {
        "label": label,
        "command": subprocess.list2cmdline([str(item) for item in command]),
        "cwd": str(cwd),
        "exit_code": int(getattr(completed, "returncode", 1)),
        "stdout_path": str(stdout_path),
        "stderr_path": str(stderr_path),
    }


def _collect_checks(
    *,
    manifest_path: Path,
    marketplace_path: Path,
    plugin_root: Path,
    plugin_name: str,
    required_paths: list[Path],
    required_manifest_fields: list[str],
) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    checks.append(
        {
            "label": "plugin-root-exists",
            "passed": plugin_root.is_dir(),
            "message": "Plugin root was created." if plugin_root.is_dir() else "Plugin root was not created.",
        }
    )
    for required in required_paths:
        checks.append(
            {
                "label": f"required-path:{required.name}",
                "passed": required.exists(),
                "message": f"Required output exists: {required}" if required.exists() else f"Required output is missing: {required}",
            }
        )

    manifest_payload: dict[str, Any] = {}
    if manifest_path.is_file():
        manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    checks.append(
        {
            "label": "manifest-plugin-name",
            "passed": bool(manifest_payload) and str(manifest_payload.get("name") or "") == plugin_name,
            "message": "Generated manifest uses the fixed plugin name."
            if bool(manifest_payload) and str(manifest_payload.get("name") or "") == plugin_name
            else f"Generated manifest name does not match {plugin_name}.",
        }
    )
    for field in required_manifest_fields:
        exists = _field_exists(manifest_payload, str(field))
        checks.append(
            {
                "label": f"manifest-field:{field}",
                "passed": exists,
                "message": f"Manifest field contract satisfied: {field}" if exists else f"Manifest field is missing: {field}",
            }
        )

    marketplace_payload: dict[str, Any] = {}
    if marketplace_path.is_file():
        marketplace_payload = json.loads(marketplace_path.read_text(encoding="utf-8"))
    marketplace_entry = next(
        (
            item
            for item in list(marketplace_payload.get("plugins") or [])
            if isinstance(item, dict) and str(item.get("name") or "") == plugin_name
        ),
        None,
    )
    expected_source_path = f"./plugins/{plugin_name}"
    checks.append(
        {
            "label": "marketplace-entry",
            "passed": isinstance(marketplace_entry, dict)
            and str(((marketplace_entry.get("source") or {}).get("path") or "")) == expected_source_path,
            "message": "Marketplace entry references the generated plugin."
            if isinstance(marketplace_entry, dict)
            and str(((marketplace_entry.get("source") or {}).get("path") or "")) == expected_source_path
            else f"Marketplace entry is missing or does not reference {expected_source_path}.",
        }
    )
    return checks


def _field_exists(payload: dict[str, Any], field_expression: str) -> bool:
    if not isinstance(payload, dict) or not field_expression:
        return False
    for alternative in [item.strip() for item in field_expression.split("|") if item.strip()]:
        current: Any = payload
        found = True
        for part in alternative.split("."):
            if not isinstance(current, dict) or part not in current:
                found = False
                break
            current = current[part]
        if found and current not in (None, "", []):
            return True
    return False


def _preflight_failure(
    *,
    brief_path: Path,
    skill_root: Path,
    create_script: Path,
    validate_script: Path,
    plugin_name: str,
) -> str:
    if not brief_path.is_file():
        return f"Skill scenario brief is missing: {brief_path}"
    if not skill_root.exists():
        return f"Plugin Creator skill root is missing: {skill_root}"
    if not create_script.is_file():
        return f"Plugin Creator scaffold script is missing: {create_script}"
    if not validate_script.is_file():
        return f"Plugin Creator validation script is missing: {validate_script}"
    if not plugin_name:
        return "Fixed plugin name is missing from the skill scenario contract."
    return ""


def _report_seed(*, report_dir: Path, expected_screenshots: list[dict[str, Any]]) -> dict[str, Any]:
    suggested_report = report_dir / "step12-skills-plugin-creator-pass.json"
    return {
        "schema_version": "astrabridge-real-scenario-dogfood-report-seed-v1",
        "step_id": "step_12",
        "capability": "skills",
        "scenario_id": "skills_plugin_creator_fixture_scaffold",
        "trigger_path": DEFAULT_SKILL_TRIGGER_PATH,
        "suggested_report_path": str(suggested_report),
        "suggested_screenshots": [
            {
                "kind": str(item.get("kind") or "reference"),
                "path": str(report_dir / str(item.get("name") or "")),
                **({"note": str(item.get("assertion") or "")} if str(item.get("assertion") or "").strip() else {}),
            }
            for item in expected_screenshots
            if str(item.get("name") or "").strip()
        ],
    }


def _report_artifacts(execution_result: dict[str, Any]) -> list[dict[str, Any]]:
    input_payload = dict(execution_result.get("input") or {})
    output_payload = dict(execution_result.get("output") or {})
    artifact_paths = dict(execution_result.get("artifact_paths") or {})
    command_results = list(execution_result.get("command_results") or [])
    artifacts = [
        {
            "kind": "json",
            "role": "skill-scenario-fixture-contract",
            "path": str(input_payload.get("fixture_contract_path") or ""),
            "sensitive": False,
        },
        {
            "kind": "document",
            "role": "skill-scenario-brief",
            "path": str(input_payload.get("brief_path") or ""),
            "sensitive": False,
        },
        {
            "kind": "other",
            "role": "generated-plugin-root",
            "path": str(output_payload.get("plugin_root") or ""),
            "sensitive": False,
        },
        {
            "kind": "manifest",
            "role": "generated-plugin-manifest",
            "path": str(output_payload.get("manifest_path") or ""),
            "sensitive": False,
        },
        {
            "kind": "json",
            "role": "generated-marketplace",
            "path": str(output_payload.get("marketplace_path") or ""),
            "sensitive": False,
        },
        {
            "kind": "json",
            "role": "skill-scenario-result",
            "path": str(artifact_paths.get("result_path") or ""),
            "sensitive": False,
        },
        {
            "kind": "json",
            "role": "skill-scenario-report-seed",
            "path": str(artifact_paths.get("report_seed_path") or ""),
            "sensitive": False,
        },
        {
            "kind": "log",
            "role": "skill-scenario-events",
            "path": str(artifact_paths.get("events_path") or ""),
            "sensitive": False,
        },
    ]
    for item in command_results:
        artifacts.append(
            {
                "kind": "log",
                "role": f"{str(item.get('label') or 'command')}-stdout",
                "path": str(item.get("stdout_path") or ""),
                "sensitive": False,
            }
        )
        artifacts.append(
            {
                "kind": "log",
                "role": f"{str(item.get('label') or 'command')}-stderr",
                "path": str(item.get("stderr_path") or ""),
                "sensitive": False,
            }
        )
    return [item for item in artifacts if str(item.get("path") or "").strip()]


def _write_result(path: Path, result: dict[str, Any]) -> dict[str, Any]:
    write_json(path, redact_sensitive(result))
    return redact_sensitive(result)


def _append_event(path: Path, payload: dict[str, Any]) -> None:
    append_jsonl(path, redact_sensitive({"at": now_iso(), **payload}))
