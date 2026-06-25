from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from .automations import AutomationRunner, AutomationWorkspaceManager
from .codex_app_server_probe import probe_app_server_protocol
from .codex_kernel_probe import discover_codex_binary_and_version
from .codex_kernel_snapshot import build_codex_kernel_probe_snapshot, observe_protocol_features
from .codex_mcp_probe import probe_mcp_compatibility
from .codex_plugin_probe import probe_plugin_discovery
from .codex_skill_probe import probe_skill_discovery
from .common import new_id, now_iso, write_json
from .mcp_config_service import McpConfigService, astrabridge_probe_fixture_preset
from .modal_service import ModalService
from .project_service import ProjectService
from .runtime_config_service import RuntimeConfigService
from .runtime_service import RuntimeService
from .security import redact_sensitive


CODEX_KERNEL_SMOKE_SCHEMA_VERSION = "codex-kernel-smoke-v1"
EXPECTED_MCP_SERVER_NAMES = ("astrabridge_capabilities", "astrabridge_web")
EXPECTED_AUTOMATION_HELP_FLAGS = ("--sandbox", "--skip-git-repo-check", "--ignore-user-config")

BinaryDiscoveryFn = Callable[..., dict[str, Any]]
ProtocolObserverFn = Callable[[], dict[str, Any]]
AppServerProbeFn = Callable[..., dict[str, Any]]
McpProbeFn = Callable[..., dict[str, Any]]
PluginProbeFn = Callable[..., dict[str, Any]]
SkillProbeFn = Callable[..., dict[str, Any]]
SubprocessRunFn = Callable[..., subprocess.CompletedProcess[str]]


def run_codex_kernel_smoke(
    *,
    artifact_root: Path | None = None,
    repo_root: Path | None = None,
    execution_host: str = "windows",
    wsl_distro: str | None = None,
    binary_discovery_fn: BinaryDiscoveryFn = discover_codex_binary_and_version,
    protocol_observer_fn: ProtocolObserverFn = observe_protocol_features,
    app_server_probe_fn: AppServerProbeFn = probe_app_server_protocol,
    mcp_probe_fn: McpProbeFn = probe_mcp_compatibility,
    plugin_probe_fn: PluginProbeFn = probe_plugin_discovery,
    skill_probe_fn: SkillProbeFn = probe_skill_discovery,
    subprocess_run: SubprocessRunFn = subprocess.run,
    app_server_status_override: tuple[dict[str, Any], Any | None, list[str]] | None = None,
) -> dict[str, Any]:
    normalized_host = "wsl" if str(execution_host or "").strip().lower() == "wsl" else "windows"
    root = (repo_root or Path(__file__).resolve().parents[3]).resolve()
    evidence_root = (artifact_root or _default_artifact_root(root)).resolve()
    reports_dir = evidence_root / "reports"
    probes_dir = evidence_root / "probes"
    state_dir = evidence_root / "state"
    workspace_root = evidence_root / "workspace"
    project_dir = evidence_root / "project"
    for path in (reports_dir, probes_dir, state_dir, workspace_root, project_dir):
        path.mkdir(parents=True, exist_ok=True)

    smoke_run_id = new_id("codex-kernel-smoke")
    generated_at = now_iso()
    project_file = project_dir / "codex-kernel-smoke.abproj"
    projects = ProjectService(
        store_path=state_dir / "projects.json",
        session_path=state_dir / "current_project.json",
    )
    project = projects.create_project(
        "Codex Kernel Smoke",
        project_file,
        workspace_root=workspace_root,
        entry_mode="new",
    )
    projects.update_project(
        {
            "ui_preferences": {
                **dict(project.get("ui_preferences") or {}),
                "execution_host": normalized_host,
                "wsl_distro": str(wsl_distro or "").strip() or None,
            }
        }
    )

    appdata_root = state_dir / "appdata"
    modal_service = ModalService(projects.require_shell_state_root)
    mcp_config = McpConfigService(store_path=projects.require_shell_state_root() / "mcp_servers.json")
    applied_servers = [
        mcp_config.apply_astrabridge_capabilities_preset()["server"]["name"],
        mcp_config.apply_astrabridge_web_preset()["server"]["name"],
        mcp_config.upsert_server(astrabridge_probe_fixture_preset())["name"],
    ]
    runtime_config = RuntimeConfigService(
        codex_home_resolver=projects.current_runtime_codex_home,
        mcp_config=mcp_config,
    )
    runtime = RuntimeService(
        projects,
        modal_service,
        runtime_config=runtime_config,
        mcp_config=mcp_config,
    )
    profile = _default_smoke_profile(project)

    with _temporary_env({"ASTRABRIDGE_APPDATA": str(appdata_root)}):
        runtime_status = runtime._prepare_runtime(profile, require_secret=False)
        runtime_roots = runtime._kernel_probe_runtime_roots(runtime_status)
        search_roots = runtime._kernel_probe_search_roots()
        binary = binary_discovery_fn(
            execution_host=normalized_host,
            wsl_distro=wsl_distro,
        )
        protocol_features = protocol_observer_fn()
        if app_server_status_override is None:
            app_server_snapshot, client_factory, startup_warnings = runtime._kernel_probe_app_server_status(runtime_status)
        else:
            app_server_snapshot, client_factory, startup_warnings = app_server_status_override

        app_server_report = None
        if client_factory is not None:
            app_server_report = app_server_probe_fn(
                client_factory=client_factory,
                artifact_root=probes_dir / "app-server",
                cwd=runtime._runtime_workspace_root(),
                request_timeout=20.0,
            )
            app_server_snapshot = {
                **app_server_snapshot,
                **dict((app_server_report or {}).get("app_server") or {}),
                "report_path": app_server_report.get("report_path"),
            }
        codex_home = Path(str(runtime_status.get("codex_home") or "")).expanduser().resolve()
        mcp_report = mcp_probe_fn(
            codex_home=codex_home,
            mcp_config=mcp_config.snapshot(),
            client_factory=client_factory,
            artifact_root=probes_dir / "mcp",
            request_timeout=20.0,
        )
        plugin_report = plugin_probe_fn(
            codex_home=codex_home,
            client_factory=client_factory,
            local_search_roots=search_roots,
            artifact_root=probes_dir / "plugin",
            request_timeout=20.0,
        )
        skill_report = skill_probe_fn(
            codex_home=codex_home,
            client_factory=client_factory,
            local_search_roots=search_roots,
            artifact_root=probes_dir / "skill",
            request_timeout=20.0,
        )
        probe_snapshot = build_codex_kernel_probe_snapshot(
            binary=binary,
            execution_host=normalized_host,
            wsl_distro=wsl_distro,
            runtime_status=runtime_status,
            runtime_roots=runtime_roots,
            app_server=app_server_snapshot,
            protocol_features=protocol_features,
            mcp_report=mcp_report,
            plugin_report=plugin_report,
            skill_report=skill_report,
            extra_warnings=list(startup_warnings or []),
            evidence_sources=[
                "apps/astrabridge-sidecar/astrabridge_sidecar/codex_kernel_smoke.py",
                "apps/astrabridge-sidecar/astrabridge_sidecar/runtime_service.py",
            ],
        )
        probe_snapshot_path = reports_dir / "kernel-probe-snapshot.json"
        write_json(probe_snapshot_path, redact_sensitive(probe_snapshot))
        runtime_status_path = reports_dir / "runtime-status.json"
        write_json(runtime_status_path, redact_sensitive(runtime_status))

        automation_probe = _probe_automation_exec_help(
            project_service=projects,
            runtime_config=runtime_config,
            profile=profile,
            subprocess_run=subprocess_run,
        )
        tool_bridge_probe = _probe_native_tool_bridge_readiness(
            runtime_status=runtime_status,
            protocol_features=protocol_features,
        )

    checks = [
        _binary_check(binary),
        _app_server_startup_check(app_server_snapshot),
        _thread_lifecycle_check(app_server_report),
        _event_parsing_check(app_server_report),
        _mcp_visibility_check(mcp_report, applied_servers),
        _plugin_discovery_check(plugin_report),
        _skill_discovery_check(skill_report),
        automation_probe,
        tool_bridge_probe,
    ]
    report_path = reports_dir / "smoke-report.json"
    report = {
        "schema_version": CODEX_KERNEL_SMOKE_SCHEMA_VERSION,
        "smoke_run_id": smoke_run_id,
        "generated_at": generated_at,
        "artifact_root": str(evidence_root),
        "repo_root": str(root),
        "execution_host": normalized_host,
        "wsl_distro": str(wsl_distro or "").strip() or None,
        "project_file": str(project_file),
        "workspace_root": str(workspace_root),
        "runtime_status_path": str(runtime_status_path),
        "kernel_probe_snapshot_path": str(probe_snapshot_path),
        "kernel_probe_inference": dict(probe_snapshot.get("inferred") or {}),
        "checks": checks,
        "summary": _summarize_checks(checks),
        "known_warnings": _dedupe_preserve_order(
            list(probe_snapshot.get("known_warnings") or [])
            + list(startup_warnings or [])
            + [warning for check in checks for warning in list(check.get("warnings") or [])]
        ),
        "artifacts": [
            str(probe_snapshot_path),
            str(runtime_status_path),
            str(report_path),
            *_artifact_refs(app_server_report),
            *_artifact_refs(mcp_report),
            *_artifact_refs(plugin_report),
            *_artifact_refs(skill_report),
            *_artifact_refs(automation_probe),
        ],
    }
    write_json(report_path, redact_sensitive(report))
    report["report_path"] = str(report_path)
    return redact_sensitive(report)


def _default_artifact_root(repo_root: Path) -> Path:
    stamp = new_id("run").split("-", 1)[1]
    return repo_root / "PRIVATE" / "demo-runs" / f"codex-kernel-smoke-{stamp}"


def _default_smoke_profile(project: dict[str, Any]) -> dict[str, Any]:
    model = str(project.get("default_model") or "gpt-5.5").strip() or "gpt-5.5"
    effort = str(project.get("default_effort") or "high").strip().lower() or "high"
    return {
        "profile_id": "openai-compatible",
        "provider_id": "openai",
        "label": "OpenAI Compatible",
        "base_url": "https://api.openai.com/v1",
        "model": model,
        "reasoning_effort": effort,
        "wire_api": "responses",
        "env_key": "OPENAI_API_KEY",
        "auth_mode": "env_ref",
    }


def _binary_check(binary: dict[str, Any]) -> dict[str, Any]:
    status = "pass" if str(binary.get("version_parse_status") or "") == "ok" else "fail"
    summary = (
        f"Resolved Codex binary {binary.get('path')} as {binary.get('version_semver')}."
        if status == "pass"
        else f"Codex binary discovery failed with status {binary.get('version_parse_status')}."
    )
    return _check(
        "binary_discovery",
        status=status,
        critical=True,
        summary=summary,
        details={
            "path": binary.get("path"),
            "path_source": binary.get("path_source"),
            "launch_descriptor": binary.get("launch_descriptor"),
            "version_text": binary.get("version_text"),
            "version_semver": binary.get("version_semver"),
            "version_parse_status": binary.get("version_parse_status"),
            "version_error": binary.get("version_error"),
        },
    )


def _app_server_startup_check(app_server_snapshot: dict[str, Any]) -> dict[str, Any]:
    initialize_status = str(app_server_snapshot.get("initialize_status") or "not_checked")
    available = bool(app_server_snapshot.get("available"))
    status = "pass" if available and initialize_status == "supported" else "fail"
    summary = (
        f"Codex app-server initialized over {app_server_snapshot.get('transport')}."
        if status == "pass"
        else f"Codex app-server did not initialize cleanly ({initialize_status})."
    )
    return _check(
        "app_server_startup",
        status=status,
        critical=True,
        summary=summary,
        details=app_server_snapshot,
        evidence_refs=_artifact_refs(app_server_snapshot),
    )


def _thread_lifecycle_check(app_server_report: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(app_server_report, dict):
        return _check(
            "thread_lifecycle",
            status="fail",
            critical=True,
            summary="Thread lifecycle probe did not run because no app-server client factory was available.",
            details={},
        )
    payload = dict(app_server_report.get("app_server") or {})
    thread_start_status = str(payload.get("thread_start_status") or "not_checked")
    thread_resume_status = str(payload.get("thread_resume_status") or "not_checked")
    turn_start_status = str(payload.get("turn_start_status") or "not_checked")
    resume_warning = thread_resume_status not in {"supported", "not_checked"}
    status = "pass" if thread_start_status == "supported" and turn_start_status in {"supported", "error_response"} else "fail"
    summary = (
        "App-server created a fresh thread and exercised turn/start without protocol incompatibility."
        if status == "pass"
        else (
            "App-server fresh thread lifecycle was not compatible: "
            f"thread/start={thread_start_status}, turn/start={turn_start_status}, thread/resume={thread_resume_status}."
        )
    )
    warnings = list(app_server_report.get("known_warnings") or [])
    if status == "pass" and resume_warning:
        warnings.append(f"thread/resume remains an independent compatibility warning: {thread_resume_status}.")
    return _check(
        "thread_lifecycle",
        status=status,
        critical=True,
        summary=summary,
        details=payload,
        warnings=warnings,
        evidence_refs=_artifact_refs(app_server_report),
    )


def _event_parsing_check(app_server_report: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(app_server_report, dict):
        return _check(
            "event_parsing",
            status="warn",
            critical=False,
            summary="No app-server protocol report was available for event parsing checks.",
            details={},
        )
    payload = dict(app_server_report.get("app_server") or {})
    notifications = list(payload.get("notifications_seen") or [])
    requests = list(payload.get("server_requests_seen") or [])
    error_shape = str(payload.get("turn_error_shape_status") or "not_observed")
    status = "pass" if notifications or requests or error_shape != "not_observed" else "warn"
    summary = (
        "Observed notifications, server requests, or structured turn errors during the smoke turn."
        if status == "pass"
        else "Smoke turn produced no observable notifications or structured errors to parse."
    )
    return _check(
        "event_parsing",
        status=status,
        critical=False,
        summary=summary,
        details={
            "notifications_seen": notifications,
            "server_requests_seen": requests,
            "turn_error_shape_status": error_shape,
            "turn_error": payload.get("turn_error"),
        },
        warnings=list(app_server_report.get("known_warnings") or []),
        evidence_refs=_artifact_refs(app_server_report),
    )


def _mcp_visibility_check(mcp_report: dict[str, Any], expected_servers: list[str]) -> dict[str, Any]:
    payload = dict(mcp_report.get("mcp") or {})
    visible_servers = list(payload.get("visible_servers") or [])
    missing_servers = sorted(set(expected_servers) - set(visible_servers))
    status = (
        "pass"
        if str(payload.get("config_render_status") or "") == "supported"
        and str(payload.get("reload_status") or "") == "supported"
        and str(payload.get("server_status_list_status") or "") == "supported"
        and not missing_servers
        else "fail"
    )
    summary = (
        "Rendered MCP config was visible to Codex and expected app-owned servers appeared."
        if status == "pass"
        else f"MCP visibility failed; missing servers: {', '.join(missing_servers) or 'unknown'}."
    )
    return _check(
        "mcp_visibility",
        status=status,
        critical=True,
        summary=summary,
        details=payload,
        warnings=list(mcp_report.get("known_warnings") or []),
        evidence_refs=_artifact_refs(mcp_report),
    )


def _plugin_discovery_check(plugin_report: dict[str, Any]) -> dict[str, Any]:
    payload = dict(plugin_report.get("plugin") or {})
    config_state = str(payload.get("config_feature_state") or "unknown")
    list_status = str(payload.get("list_status") or "not_checked")
    read_status = str(payload.get("read_status") or "not_checked")
    if config_state == "disabled_by_app":
        status = "pass"
        summary = "Plugin probing recorded the current app-level plugin disablement without incompatible behavior."
    elif list_status in {"supported", "unsupported"} and read_status not in {"timeout", "error", "incompatible_response"}:
        status = "pass"
        summary = "Plugin discovery surfaces responded without incompatible behavior."
    else:
        status = "fail"
        summary = (
            "Plugin discovery surfaced an incompatible state: "
            f"config={config_state}, list={list_status}, read={read_status}."
        )
    return _check(
        "plugin_discovery",
        status=status,
        critical=True,
        summary=summary,
        details=payload,
        warnings=list(plugin_report.get("known_warnings") or []),
        evidence_refs=_artifact_refs(plugin_report),
    )


def _skill_discovery_check(skill_report: dict[str, Any]) -> dict[str, Any]:
    payload = dict(skill_report.get("skill") or {})
    discovered_skills = list(payload.get("discovered_skills") or [])
    list_status = str(payload.get("list_status") or "not_checked")
    status = "pass" if discovered_skills and list_status in {"supported", "unsupported"} else "fail"
    summary = (
        f"Skill discovery found {len(discovered_skills)} skill entries."
        if status == "pass"
        else f"Skill discovery did not produce usable results (list_status={list_status})."
    )
    return _check(
        "skill_discovery",
        status=status,
        critical=True,
        summary=summary,
        details=payload,
        warnings=list(skill_report.get("known_warnings") or []),
        evidence_refs=_artifact_refs(skill_report),
    )


def _probe_automation_exec_help(
    *,
    project_service: ProjectService,
    runtime_config: RuntimeConfigService,
    profile: dict[str, Any],
    subprocess_run: SubprocessRunFn,
) -> dict[str, Any]:
    runner = AutomationRunner(
        project_service,
        runtime_config=runtime_config,
    )
    automation = {
        "automation_id": "codex-kernel-smoke",
        "project_id": str((project_service.current_project or {}).get("project_id") or "codex-kernel-smoke"),
        "kind": "standalone",
        "prompt": "Kernel smoke automation help check",
        "runtime": {
            "profile_id": str(profile.get("profile_id") or "openai-compatible"),
            "provider_id": str(profile.get("provider_id") or "openai"),
            "model": profile.get("model"),
            "effort": profile.get("reasoning_effort"),
            "permission_mode": "read-only",
        },
        "workspace": {
            "mode": "current_workspace",
            "cleanup_policy": "manual",
        },
        "limits": {"timeout_sec": 20},
    }
    run = {
        "run_id": new_id("automation-smoke"),
        "automation_id": automation["automation_id"],
        "project_id": automation["project_id"],
        "trigger": "manual",
        "status": "queued",
        "due_at": now_iso(),
    }
    session = AutomationWorkspaceManager(project_service).prepare_workspace(automation, run)
    env = runner._standalone_env(profile=profile, workspace_session=session, automation=automation, run=run)
    preview_command = runner._standalone_command(automation, session)
    help_command = [preview_command[0], "exec", "--help"]
    details: dict[str, Any] = {
        "preview_command": preview_command,
        "help_command": help_command,
        "execution_root": session.execution_root,
        "path_has_codex": bool(shutil.which(preview_command[0])),
        "expected_flags": list(EXPECTED_AUTOMATION_HELP_FLAGS),
    }
    try:
        completed = subprocess_run(
            help_command,
            cwd=str(Path(session.execution_root).resolve()),
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=20,
            check=False,
        )
    except FileNotFoundError as exc:
        return _check(
            "automation_standalone_invocation",
            status="fail",
            critical=True,
            summary="Automation standalone invocation could not find `codex` on PATH.",
            details={**details, "error": str(exc)},
        )
    except subprocess.TimeoutExpired as exc:
        return _check(
            "automation_standalone_invocation",
            status="fail",
            critical=True,
            summary="Automation standalone invocation help probe timed out.",
            details={**details, "error": str(exc)},
        )

    stdout = str(getattr(completed, "stdout", "") or "")
    stderr = str(getattr(completed, "stderr", "") or "")
    combined = f"{stdout}\n{stderr}"
    missing_flags = [flag for flag in EXPECTED_AUTOMATION_HELP_FLAGS if flag not in combined]
    returncode = getattr(completed, "returncode", 1)
    normalized_returncode = int(returncode) if returncode is not None else 1
    status = "pass" if normalized_returncode == 0 and not missing_flags else "fail"
    summary = (
        "Standalone automation CLI surface responded to `codex exec --help` with expected sandbox/config flags."
        if status == "pass"
        else f"Standalone automation CLI help probe failed; missing flags: {', '.join(missing_flags) or 'none'}."
    )
    details.update(
        {
            "returncode": normalized_returncode,
            "stdout_excerpt": stdout[:1200],
            "stderr_excerpt": stderr[:1200],
            "missing_flags": missing_flags,
            "codex_home": env.get("CODEX_HOME"),
        }
    )
    return _check(
        "automation_standalone_invocation",
        status=status,
        critical=True,
        summary=summary,
        details=details,
    )


def _probe_native_tool_bridge_readiness(
    *,
    runtime_status: dict[str, Any],
    protocol_features: dict[str, Any],
) -> dict[str, Any]:
    apply_patch_tool_type = runtime_status.get("apply_patch_tool_type")
    turn_start_declared = dict(protocol_features.get("client_methods") or {}).get("turn/start") == "declared"
    status = "pass" if apply_patch_tool_type in {"json", "freeform"} and turn_start_declared else "warn"
    summary = (
        "Native shell/apply_patch bridge metadata is present; no-key smoke intentionally skipped a provider-backed tool call."
        if status == "pass"
        else "Native shell/apply_patch bridge metadata is incomplete or conservative; no-key smoke did not force a provider-backed tool call."
    )
    return _check(
        "native_tool_bridge_readiness",
        status=status,
        critical=False,
        summary=summary,
        details={
            "apply_patch_tool_type": apply_patch_tool_type,
            "supports_mcp_tools": runtime_status.get("supports_mcp_tools"),
            "tool_mode": runtime_status.get("tool_mode"),
            "turn_start_declared": turn_start_declared,
        },
    )


def _artifact_refs(payload: dict[str, Any] | None) -> list[str]:
    if not isinstance(payload, dict):
        return []
    candidates: list[str] = []
    report_path = str(payload.get("report_path") or "").strip()
    if report_path:
        candidates.append(report_path)
    evidence = payload.get("evidence")
    if isinstance(evidence, dict):
        for item in list(evidence.get("artifacts") or []):
            text = str(item or "").strip()
            if text:
                candidates.append(text)
    return _dedupe_preserve_order(candidates)


def _check(
    check_id: str,
    *,
    status: str,
    critical: bool,
    summary: str,
    details: dict[str, Any],
    warnings: list[str] | None = None,
    evidence_refs: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "check_id": check_id,
        "status": status,
        "critical": critical,
        "summary": summary,
        "details": redact_sensitive(details),
        "warnings": _dedupe_preserve_order(list(warnings or [])),
        "evidence_refs": _dedupe_preserve_order(list(evidence_refs or [])),
    }


def _summarize_checks(checks: list[dict[str, Any]]) -> dict[str, Any]:
    counts = {"pass": 0, "warn": 0, "fail": 0, "skipped": 0}
    for check in checks:
        status = str(check.get("status") or "warn")
        counts[status] = counts.get(status, 0) + 1
    critical_failures = [check["check_id"] for check in checks if check.get("critical") and check.get("status") == "fail"]
    if critical_failures:
        overall_status = "fail"
    elif counts.get("warn", 0):
        overall_status = "warn"
    else:
        overall_status = "pass"
    return {
        "overall_status": overall_status,
        "counts": counts,
        "critical_failures": critical_failures,
    }


def _dedupe_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        text = str(item or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        ordered.append(text)
    return ordered


@contextmanager
def _temporary_env(updates: dict[str, str]) -> Iterator[None]:
    original: dict[str, str | None] = {key: os.environ.get(key) for key in updates}
    for key, value in updates.items():
        os.environ[key] = str(value)
    try:
        yield
    finally:
        for key, value in original.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the AstraBridge Codex kernel smoke suite.")
    parser.add_argument("--artifact-root", type=Path, default=None, help="Optional artifact root. Defaults to PRIVATE/demo-runs/codex-kernel-smoke-* under the repo root.")
    parser.add_argument("--repo-root", type=Path, default=None, help="Optional repo root override. Defaults to the current AstraBridge checkout.")
    parser.add_argument("--execution-host", choices=("windows", "wsl"), default="windows", help="Runtime host to probe.")
    parser.add_argument("--wsl-distro", default=None, help="Optional WSL distro name when --execution-host=wsl.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    report = run_codex_kernel_smoke(
        artifact_root=args.artifact_root,
        repo_root=args.repo_root,
        execution_host=args.execution_host,
        wsl_distro=args.wsl_distro,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if str(report.get("summary", {}).get("overall_status") or "fail") == "fail" else 0


if __name__ == "__main__":
    raise SystemExit(main())
