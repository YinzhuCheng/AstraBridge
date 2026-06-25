from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Callable

from .codex_plugin_probe import probe_plugin_discovery
from .codex_plugin_skill_registry import build_plugin_skill_registry_snapshot
from .codex_skill_probe import probe_skill_discovery
from .common import new_id, now_iso, write_json
from .security import redact_sensitive


PLUGIN_SKILL_SMOKE_SCHEMA_VERSION = "astrabridge-plugin-skill-smoke-v1"
PLUGIN_SKILL_UI_ASSERTIONS_SCHEMA_VERSION = "astrabridge-plugin-skill-ui-assertions-v1"

PluginProbeFn = Callable[..., dict[str, Any]]
SkillProbeFn = Callable[..., dict[str, Any]]
RegistryBuilderFn = Callable[..., dict[str, Any]]
UiSmokeRunnerFn = Callable[..., dict[str, Any]]
SubprocessRunFn = Callable[..., subprocess.CompletedProcess[str]]


def run_plugin_skill_smoke(
    *,
    artifact_root: Path | None = None,
    repo_root: Path | None = None,
    plugin_probe_fn: PluginProbeFn = probe_plugin_discovery,
    skill_probe_fn: SkillProbeFn = probe_skill_discovery,
    registry_builder_fn: RegistryBuilderFn = build_plugin_skill_registry_snapshot,
    ui_smoke_runner: UiSmokeRunnerFn | None = None,
    subprocess_run: SubprocessRunFn = subprocess.run,
) -> dict[str, Any]:
    root = (repo_root or Path(__file__).resolve().parents[3]).resolve()
    evidence_root = (artifact_root or _default_artifact_root(root)).resolve()
    reports_dir = evidence_root / "reports"
    probes_dir = evidence_root / "probes"
    fixtures_dir = evidence_root / "fixtures"
    ui_dir = evidence_root / "ui"
    codex_home = evidence_root / "codex-home"
    workspace_root = evidence_root / "workspace"
    for path in (reports_dir, probes_dir, fixtures_dir, ui_dir, codex_home, workspace_root):
        path.mkdir(parents=True, exist_ok=True)

    smoke_run_id = new_id("plugin-skill-smoke")
    generated_at = now_iso()
    fixture = _write_plugin_skill_smoke_fixture(codex_home=codex_home, fixtures_dir=fixtures_dir)
    search_roots = [Path(str(fixture["search_root"]))]

    plugin_report = plugin_probe_fn(
        codex_home=codex_home,
        local_search_roots=search_roots,
        artifact_root=probes_dir / "plugin",
    )
    skill_report = skill_probe_fn(
        codex_home=codex_home,
        local_search_roots=search_roots,
        artifact_root=probes_dir / "skill",
    )
    registry_snapshot = registry_builder_fn(
        plugin_report=plugin_report,
        skill_report=skill_report,
        runtime_roots={
            "codex_home_root": str(codex_home),
            "project_runtime_root": str(workspace_root),
            "workspace_runtime_cwd": str(workspace_root),
        },
        search_roots=search_roots,
        generated_at=generated_at,
        extra_notes=[f"plugin_skill_smoke_fixture:{fixture['plugin_id']}/{fixture['skill_name']}"],
    )
    snapshot_path = reports_dir / "plugin-skill-registry-snapshot.json"
    write_json(snapshot_path, redact_sensitive(registry_snapshot))

    ui_runner = ui_smoke_runner or run_plugin_skill_inventory_ui_smoke
    ui_report = ui_runner(
        repo_root=root,
        snapshot_path=snapshot_path,
        artifact_root=ui_dir,
        fixture=fixture,
        subprocess_run=subprocess_run,
    )

    checks = [
        _plugin_discovery_check(plugin_report, fixture),
        _skill_discovery_check(skill_report, fixture),
        _fixture_skill_availability_check(registry_snapshot, fixture, snapshot_path=snapshot_path),
        _mcp_side_effects_check(registry_snapshot, fixture, snapshot_path=snapshot_path),
        _ui_inventory_rendering_check(ui_report, fixture),
    ]

    report_path = reports_dir / "smoke-report.json"
    report = {
        "schema_version": PLUGIN_SKILL_SMOKE_SCHEMA_VERSION,
        "smoke_run_id": smoke_run_id,
        "generated_at": generated_at,
        "artifact_root": str(evidence_root),
        "repo_root": str(root),
        "codex_home": str(codex_home),
        "workspace_root": str(workspace_root),
        "fixture": fixture,
        "search_roots": [str(item) for item in search_roots],
        "plugin_probe_path": plugin_report.get("report_path"),
        "skill_probe_path": skill_report.get("report_path"),
        "registry_snapshot_path": str(snapshot_path),
        "checks": checks,
        "summary": _summarize_checks(checks),
        "known_warnings": _dedupe_preserve_order(
            [
                *list(plugin_report.get("known_warnings") or []),
                *list(skill_report.get("known_warnings") or []),
                *list(ui_report.get("warnings") or []),
            ]
        ),
        "artifacts": _dedupe_preserve_order(
            [
                str(snapshot_path),
                str(report_path),
                *_artifact_refs(plugin_report),
                *_artifact_refs(skill_report),
                *_artifact_refs(ui_report),
            ]
        ),
    }
    write_json(report_path, redact_sensitive(report))
    report["report_path"] = str(report_path)
    return redact_sensitive(report)


def run_plugin_skill_inventory_ui_smoke(
    *,
    repo_root: Path,
    snapshot_path: Path,
    artifact_root: Path,
    fixture: dict[str, Any],
    subprocess_run: SubprocessRunFn = subprocess.run,
) -> dict[str, Any]:
    artifact_root.mkdir(parents=True, exist_ok=True)
    assertions_path = artifact_root / "ui-assertions.json"
    vitest_report_path = artifact_root / "vitest-report.json"
    desktop_root = (repo_root / "apps" / "astrabridge-desktop").resolve()
    vitest_entry = desktop_root / "node_modules" / "vitest" / "vitest.mjs"
    node_bin = shutil.which("node")
    command = [
        node_bin or "node",
        str(vitest_entry),
        "run",
        "src/features/extensions/PluginSkillInventoryPanel.smoke.test.tsx",
        "--reporter=json",
        f"--outputFile={vitest_report_path}",
    ]
    result: dict[str, Any] = {
        "status": "fail",
        "command": command,
        "snapshot_path": str(snapshot_path),
        "assertions_path": str(assertions_path),
        "vitest_report_path": str(vitest_report_path),
        "fixture": {
            "plugin_id": fixture.get("plugin_id"),
            "skill_name": fixture.get("skill_name"),
            "declared_mcp_server": fixture.get("declared_mcp_server"),
        },
        "warnings": [],
    }

    if node_bin is None:
        result["error"] = "Node.js is not available on PATH."
        return result
    if not vitest_entry.exists():
        result["error"] = f"Vitest entrypoint is missing: {vitest_entry}"
        return result

    env = dict(os.environ)
    env["ASTRABRIDGE_PLUGIN_SKILL_SMOKE_SNAPSHOT_JSON"] = snapshot_path.read_text(encoding="utf-8")
    try:
        completed = subprocess_run(
            command,
            cwd=str(desktop_root),
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
            check=False,
        )
    except FileNotFoundError as exc:
        result["error"] = str(exc)
        return result
    except subprocess.TimeoutExpired as exc:
        result["error"] = str(exc)
        result["warnings"] = ["UI smoke timed out."]
        return result

    stdout = str(getattr(completed, "stdout", "") or "")
    stderr = str(getattr(completed, "stderr", "") or "")
    raw_returncode = getattr(completed, "returncode", 1)
    returncode = int(raw_returncode) if raw_returncode is not None else 1
    vitest_payload = _read_json(vitest_report_path)
    assertions = _ui_assertions_from_vitest_report(vitest_payload)
    write_json(
        assertions_path,
        {
            "schema_version": PLUGIN_SKILL_UI_ASSERTIONS_SCHEMA_VERSION,
            "assertion_count": len(assertions),
            "assertions": assertions,
        },
    )
    failed_assertions = [item for item in assertions if not bool(item.get("ok"))]

    result.update(
        {
            "returncode": returncode,
            "stdout_excerpt": stdout[:2000],
            "stderr_excerpt": stderr[:2000],
            "assertions": assertions,
            "failed_assertions": failed_assertions,
            "vitest_report": vitest_payload if isinstance(vitest_payload, dict) else None,
            "status": "pass" if returncode == 0 and assertions and not failed_assertions else "fail",
        }
    )
    if not assertions:
        result["warnings"] = [*list(result.get("warnings") or []), "UI smoke did not produce structured assertions."]
    if not isinstance(vitest_payload, dict):
        result["warnings"] = [*list(result.get("warnings") or []), "Vitest JSON report was not produced."]
    return result


def _write_plugin_skill_smoke_fixture(*, codex_home: Path, fixtures_dir: Path) -> dict[str, str]:
    plugin_id = "demo-plugin-smoke"
    plugin_display_name = "Demo Plugin Smoke"
    skill_name = "demo-plugin-skill"
    declared_mcp_server = "demo_mcp"
    search_root = fixtures_dir / "catalog-root"
    marketplace_path = search_root / ".agents" / "plugins" / "marketplace.json"
    plugin_root = marketplace_path.parent / "plugins" / plugin_id
    skill_path = plugin_root / "skills" / skill_name / "SKILL.md"

    _write_codex_home_config(codex_home)
    _write(
        marketplace_path,
        json.dumps(
            {
                "name": "personal",
                "plugins": [
                    {
                        "name": plugin_id,
                        "source": {"source": "local", "path": f"./plugins/{plugin_id}"},
                        "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
                        "category": "Productivity",
                    }
                ],
            }
        ),
    )
    _write(
        plugin_root / ".codex-plugin" / "plugin.json",
        json.dumps(
            {
                "name": plugin_id,
                "version": "1.2.3",
                "interface": {
                    "displayName": plugin_display_name,
                    "shortDescription": "Fixture plugin used by the AstraBridge plugin/skill smoke suite.",
                    "brandColor": "#2563eb",
                },
                "mcpServers": {declared_mcp_server: {"command": "node", "args": ["demo-mcp.js"]}},
                "apps": ["demo-app"],
                "skills": [skill_name],
            }
        ),
    )
    _write(
        skill_path,
        "\n".join(
            [
                "---",
                f"name: {skill_name}",
                "description: Use this skill when the plugin smoke fixture should handle demo tasks.",
                "---",
                "",
                "# Demo Plugin Skill",
                "",
                "This is a fixture skill for smoke testing only.",
                "",
            ]
        ),
    )
    return {
        "search_root": str(search_root.resolve()),
        "marketplace_path": str(marketplace_path.resolve()),
        "plugin_root": str(plugin_root.resolve()),
        "manifest_path": str((plugin_root / ".codex-plugin" / "plugin.json").resolve()),
        "skill_path": str(skill_path.resolve()),
        "plugin_id": plugin_id,
        "plugin_display_name": plugin_display_name,
        "skill_name": skill_name,
        "declared_mcp_server": declared_mcp_server,
    }


def _write_codex_home_config(codex_home: Path) -> None:
    _write(
        codex_home / "config.toml",
        "\n".join(
            [
                'model = "gpt-5.5"',
                "",
                "[features]",
                "plugins = true",
                "plugin_sharing = false",
                "remote_plugin = false",
                "",
            ]
        ),
    )


def _plugin_discovery_check(plugin_report: dict[str, Any], fixture: dict[str, Any]) -> dict[str, Any]:
    payload = dict(plugin_report.get("plugin") or {})
    discovered = next((item for item in list(payload.get("discovered_plugins") or []) if str(item.get("plugin_id") or "") == fixture["plugin_id"]), None)
    marketplace_status = str(payload.get("marketplace_status") or "unknown")
    manifest_status = str((discovered or {}).get("manifest_status") or "missing")
    status = "pass" if isinstance(discovered, dict) and manifest_status == "ok" and marketplace_status in {"manifest_fallback", "supported"} else "fail"
    summary = (
        f"Plugin discovery found fixture plugin {fixture['plugin_id']} with manifest fallback metadata."
        if status == "pass"
        else f"Plugin discovery did not produce a usable fixture plugin record for {fixture['plugin_id']}."
    )
    return _check(
        "plugin_discovery",
        status=status,
        critical=True,
        summary=summary,
        details={
            "fixture_plugin_id": fixture["plugin_id"],
            "marketplace_status": marketplace_status,
            "manifest_fallback_status": payload.get("manifest_fallback_status"),
            "plugin_record": discovered,
        },
        warnings=list(plugin_report.get("known_warnings") or []),
        evidence_refs=_artifact_refs(plugin_report),
    )


def _skill_discovery_check(skill_report: dict[str, Any], fixture: dict[str, Any]) -> dict[str, Any]:
    payload = dict(skill_report.get("skill") or {})
    discovered = next((item for item in list(payload.get("discovered_skills") or []) if str(item.get("skill_name") or "") == fixture["skill_name"]), None)
    owner_plugin_id = str((discovered or {}).get("owner_plugin_id") or "")
    status = "pass" if isinstance(discovered, dict) and owner_plugin_id == fixture["plugin_id"] else "fail"
    summary = (
        f"Skill discovery found fixture skill {fixture['skill_name']} owned by {fixture['plugin_id']}."
        if status == "pass"
        else f"Skill discovery did not produce a usable fixture skill record for {fixture['skill_name']}."
    )
    return _check(
        "skill_discovery",
        status=status,
        critical=True,
        summary=summary,
        details={
            "fixture_skill_name": fixture["skill_name"],
            "list_status": payload.get("list_status"),
            "skill_record": discovered,
        },
        warnings=list(skill_report.get("known_warnings") or []),
        evidence_refs=_artifact_refs(skill_report),
    )


def _fixture_skill_availability_check(snapshot: dict[str, Any], fixture: dict[str, Any], *, snapshot_path: Path) -> dict[str, Any]:
    plugin = next((item for item in list(snapshot.get("plugins") or []) if str(item.get("plugin_id") or "") == fixture["plugin_id"]), None)
    skill = next((item for item in list(snapshot.get("skills") or []) if str(item.get("skill_name") or "") == fixture["skill_name"]), None)
    status = (
        "pass"
        if isinstance(plugin, dict)
        and isinstance(skill, dict)
        and str(skill.get("owner_plugin_id") or "") == fixture["plugin_id"]
        and str(skill.get("install_status") or "") == "installed"
        else "fail"
    )
    summary = (
        "Registry snapshot carries the fixture skill as an available plugin-owned skill."
        if status == "pass"
        else "Registry snapshot did not preserve the fixture skill as an installed plugin-owned skill."
    )
    return _check(
        "fixture_skill_availability",
        status=status,
        critical=True,
        summary=summary,
        details={"plugin_record": plugin, "skill_record": skill},
        evidence_refs=[str(snapshot_path)],
    )


def _mcp_side_effects_check(snapshot: dict[str, Any], fixture: dict[str, Any], *, snapshot_path: Path) -> dict[str, Any]:
    plugin = next((item for item in list(snapshot.get("plugins") or []) if str(item.get("plugin_id") or "") == fixture["plugin_id"]), None)
    declared_mcp = list((plugin or {}).get("declared_mcp_servers") or [])
    status = "pass" if fixture["declared_mcp_server"] in declared_mcp else "fail"
    summary = (
        f"Fixture plugin preserves declared MCP side effects for {fixture['declared_mcp_server']}."
        if status == "pass"
        else f"Fixture plugin did not preserve declared MCP side effects for {fixture['declared_mcp_server']}."
    )
    return _check(
        "mcp_side_effects",
        status=status,
        critical=True,
        summary=summary,
        details={"plugin_record": plugin, "declared_mcp_servers": declared_mcp},
        evidence_refs=[str(snapshot_path)],
    )


def _ui_inventory_rendering_check(ui_report: dict[str, Any], fixture: dict[str, Any]) -> dict[str, Any]:
    failed_assertions = list(ui_report.get("failed_assertions") or [])
    status = "pass" if str(ui_report.get("status") or "") == "pass" and not failed_assertions else "fail"
    summary = (
        "PluginSkillInventoryPanel rendered the smoke snapshot and wrote structured UI assertions."
        if status == "pass"
        else "PluginSkillInventoryPanel smoke render failed or did not produce complete structured assertions."
    )
    return _check(
        "ui_inventory_rendering",
        status=status,
        critical=True,
        summary=summary,
        details={
            "fixture_plugin_id": fixture["plugin_id"],
            "fixture_skill_name": fixture["skill_name"],
            "ui_status": ui_report.get("status"),
            "returncode": ui_report.get("returncode"),
            "failed_assertions": failed_assertions,
            "assertions": list(ui_report.get("assertions") or []),
        },
        warnings=list(ui_report.get("warnings") or []),
        evidence_refs=_artifact_refs(ui_report),
    )


def _artifact_refs(payload: dict[str, Any] | None) -> list[str]:
    if not isinstance(payload, dict):
        return []
    refs: list[str] = []
    for key in ("report_path", "snapshot_path", "assertions_path", "vitest_report_path"):
        text = str(payload.get(key) or "").strip()
        if text:
            refs.append(text)
    for artifact in list(payload.get("artifacts") or []):
        text = str(artifact or "").strip()
        if text:
            refs.append(text)
    return _dedupe_preserve_order(refs)


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


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _ui_assertions_from_vitest_report(payload: Any) -> list[dict[str, Any]]:
    assertions: list[dict[str, Any]] = []
    _collect_vitest_assertions(payload, assertions)
    return assertions


def _collect_vitest_assertions(payload: Any, assertions: list[dict[str, Any]]) -> None:
    if isinstance(payload, dict):
        status = str(payload.get("status") or "").strip().lower()
        title = str(payload.get("fullName") or payload.get("title") or payload.get("name") or "").strip()
        if status and title and "assertionResults" not in payload:
            assertions.append(
                {
                    "id": f"ui_assertion_{len(assertions) + 1}",
                    "name": title,
                    "status": status,
                    "ok": status in {"passed", "pass"},
                }
            )
        nested = payload.get("assertionResults")
        if isinstance(nested, list):
            for item in nested:
                _collect_vitest_assertions(item, assertions)
        for key in ("testResults", "children"):
            nested = payload.get(key)
            if isinstance(nested, list):
                for item in nested:
                    _collect_vitest_assertions(item, assertions)
        return
    if isinstance(payload, list):
        for item in payload:
            _collect_vitest_assertions(item, assertions)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


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


def _default_artifact_root(repo_root: Path) -> Path:
    stamp = new_id("run").split("-", 1)[1]
    return repo_root / "PRIVATE" / "demo-runs" / f"plugin-skill-smoke-{stamp}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run AstraBridge plugin and skill no-key smoke.")
    parser.add_argument("--artifact-root", default="", help="Optional artifact root override.")
    parser.add_argument("--repo-root", default="", help="Optional repository root override.")
    args = parser.parse_args(argv)
    report = run_plugin_skill_smoke(
        artifact_root=Path(args.artifact_root).resolve() if args.artifact_root else None,
        repo_root=Path(args.repo_root).resolve() if args.repo_root else None,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if str(report.get("summary", {}).get("overall_status") or "") == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
