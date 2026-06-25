from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Callable

from .codex_plugin_install_apply import execute_plugin_install
from .common import new_id, now_iso, write_json
from .security import redact_sensitive


PLUGIN_INSTALL_SMOKE_SCHEMA_VERSION = "astrabridge-plugin-install-smoke-v1"
MoveFn = Callable[..., Any]


def run_plugin_install_smoke(
    *,
    artifact_root: Path | None = None,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    root = (repo_root or Path(__file__).resolve().parents[3]).resolve()
    evidence_root = (artifact_root or _default_artifact_root(root)).resolve()
    reports_dir = evidence_root / "reports"
    fixtures_root = evidence_root / "fixtures"
    workspace_root = evidence_root / "workspace"
    codex_home = evidence_root / "codex-home"
    for path in (reports_dir, fixtures_root, workspace_root, codex_home):
        path.mkdir(parents=True, exist_ok=True)

    smoke_run_id = new_id("plugin-install-smoke")
    generated_at = now_iso()
    cases = [
        _run_install_case(fixtures_root=fixtures_root, workspace_root=workspace_root, codex_home=codex_home),
        _run_update_case(fixtures_root=fixtures_root, workspace_root=workspace_root, codex_home=codex_home),
        _run_noop_case(fixtures_root=fixtures_root, workspace_root=workspace_root, codex_home=codex_home),
        _run_malformed_case(fixtures_root=fixtures_root, workspace_root=workspace_root, codex_home=codex_home),
        _run_failed_apply_case(fixtures_root=fixtures_root, workspace_root=workspace_root, codex_home=codex_home),
        _run_secret_scan_case(fixtures_root=fixtures_root, workspace_root=workspace_root, codex_home=codex_home),
    ]
    summary = {
        "passed": [case["case_id"] for case in cases if case.get("status") == "pass"],
        "failed": [case["case_id"] for case in cases if case.get("status") != "pass"],
    }
    report_path = reports_dir / "smoke-report.json"
    report = {
        "schema_version": PLUGIN_INSTALL_SMOKE_SCHEMA_VERSION,
        "smoke_run_id": smoke_run_id,
        "generated_at": generated_at,
        "artifact_root": str(evidence_root),
        "repo_root": str(root),
        "workspace_root": str(workspace_root),
        "codex_home": str(codex_home),
        "cases": cases,
        "summary": {
            "overall_status": "pass" if not summary["failed"] else "fail",
            "passed_cases": summary["passed"],
            "failed_cases": summary["failed"],
        },
        "artifacts": [str(report_path)] + [artifact for case in cases for artifact in list(case.get("artifacts") or [])],
    }
    write_json(report_path, redact_sensitive(report))
    report["report_path"] = str(report_path)
    return redact_sensitive(report)


def _run_install_case(*, fixtures_root: Path, workspace_root: Path, codex_home: Path) -> dict[str, Any]:
    source_root = fixtures_root / "install-source"
    target_root = codex_home / "plugins" / "demo-plugin-install"
    _write(source_root / ".codex-plugin" / "plugin.json", '{"name":"demo-plugin-install"}')
    _write(source_root / "skills" / "demo" / "SKILL.md", "install")
    result = execute_plugin_install(
        registry_snapshot=_registry_snapshot(source_root=source_root, target_root=target_root, plugin_id="demo-plugin-install", install_status="available"),
        plugin_id="demo-plugin-install",
        source_catalog_id="catalog::demo-plugin-install",
        codex_home=codex_home,
        workspace_root=workspace_root,
    )
    return _case_record("install", result.get("status") == "applied", result)


def _run_update_case(*, fixtures_root: Path, workspace_root: Path, codex_home: Path) -> dict[str, Any]:
    source_root = fixtures_root / "update-source"
    target_root = codex_home / "plugins" / "demo-plugin-update"
    _write(source_root / ".codex-plugin" / "plugin.json", '{"name":"demo-plugin-update","version":"2.0.0"}')
    _write(source_root / "skills" / "demo" / "SKILL.md", "update")
    _write(target_root / ".codex-plugin" / "plugin.json", '{"name":"demo-plugin-update","version":"1.0.0"}')
    _write(target_root / "skills" / "demo" / "SKILL.md", "old")
    result = execute_plugin_install(
        registry_snapshot=_registry_snapshot(
            source_root=source_root,
            target_root=target_root,
            plugin_id="demo-plugin-update",
            install_status="update_available",
            available_version="2.0.0",
            installed_version="1.0.0",
        ),
        plugin_id="demo-plugin-update",
        source_catalog_id="catalog::demo-plugin-update",
        codex_home=codex_home,
        workspace_root=workspace_root,
    )
    passed = result.get("status") == "applied" and str((target_root / "skills" / "demo" / "SKILL.md").read_text(encoding="utf-8")) == "update"
    return _case_record("update", passed, result)


def _run_noop_case(*, fixtures_root: Path, workspace_root: Path, codex_home: Path) -> dict[str, Any]:
    source_root = fixtures_root / "noop-source"
    target_root = codex_home / "plugins" / "demo-plugin-noop"
    _write(source_root / ".codex-plugin" / "plugin.json", '{"name":"demo-plugin-noop"}')
    result = execute_plugin_install(
        registry_snapshot=_registry_snapshot(
            source_root=source_root,
            target_root=target_root,
            plugin_id="demo-plugin-noop",
            install_status="installed",
            available_version=None,
            installed_version="1.2.3",
        ),
        plugin_id="demo-plugin-noop",
        source_catalog_id="catalog::demo-plugin-noop",
        codex_home=codex_home,
        workspace_root=workspace_root,
    )
    return _case_record("already_current", result.get("status") == "noop", result)


def _run_malformed_case(*, fixtures_root: Path, workspace_root: Path, codex_home: Path) -> dict[str, Any]:
    source_root = fixtures_root / "malformed-source"
    target_root = codex_home / "plugins" / "demo-plugin-malformed"
    result = execute_plugin_install(
        registry_snapshot=_registry_snapshot(
            source_root=source_root,
            target_root=target_root,
            plugin_id="demo-plugin-malformed",
            install_status="malformed",
            available_version=None,
        ),
        plugin_id="demo-plugin-malformed",
        source_catalog_id="catalog::demo-plugin-malformed",
        codex_home=codex_home,
        workspace_root=workspace_root,
    )
    passed = result.get("status") == "failed" and any(str(item.get("code") or "") == "plugin-install-status-unsupported" for item in list(result.get("errors") or []))
    return _case_record("malformed", passed, result)


def _run_failed_apply_case(*, fixtures_root: Path, workspace_root: Path, codex_home: Path) -> dict[str, Any]:
    source_root = fixtures_root / "failure-source"
    target_root = codex_home / "plugins" / "demo-plugin-failure"
    _write(source_root / ".codex-plugin" / "plugin.json", '{"name":"demo-plugin-failure","version":"2.0.0"}')
    _write(source_root / "skills" / "demo" / "SKILL.md", "update")
    _write(target_root / ".codex-plugin" / "plugin.json", '{"name":"demo-plugin-failure","version":"1.0.0"}')
    _write(target_root / "skills" / "demo" / "SKILL.md", "old")

    def failing_move(source: Path, target: Path) -> None:  # noqa: ARG001
        raise RuntimeError("move failed")

    result = execute_plugin_install(
        registry_snapshot=_registry_snapshot(
            source_root=source_root,
            target_root=target_root,
            plugin_id="demo-plugin-failure",
            install_status="update_available",
            available_version="2.0.0",
            installed_version="1.0.0",
        ),
        plugin_id="demo-plugin-failure",
        source_catalog_id="catalog::demo-plugin-failure",
        codex_home=codex_home,
        workspace_root=workspace_root,
        move_fn=failing_move,
    )
    passed = result.get("status") == "failed" and str(result.get("rollback_snapshot", {}).get("status") or "") == "restored_after_failure"
    return _case_record("failed_apply_rollback", passed, result)


def _run_secret_scan_case(*, fixtures_root: Path, workspace_root: Path, codex_home: Path) -> dict[str, Any]:
    source_root = fixtures_root / "secret-source"
    target_root = codex_home / "plugins" / "demo-plugin-secret"
    _write(source_root / ".codex-plugin" / "plugin.json", '{"name":"demo-plugin-secret","token":"live-secret"}')
    result = execute_plugin_install(
        registry_snapshot=_registry_snapshot(source_root=source_root, target_root=target_root, plugin_id="demo-plugin-secret", install_status="available"),
        plugin_id="demo-plugin-secret",
        source_catalog_id="catalog::demo-plugin-secret",
        codex_home=codex_home,
        workspace_root=workspace_root,
    )
    passed = result.get("status") == "failed" and any(str(item.get("code") or "") == "plugin-secret-scan-failed" for item in list(result.get("errors") or []))
    return _case_record("secret_scan", passed, result)


def _registry_snapshot(
    *,
    source_root: Path,
    target_root: Path,
    plugin_id: str,
    install_status: str,
    available_version: str | None = "1.2.3",
    installed_version: str | None = None,
) -> dict[str, Any]:
    catalog_id = f"catalog::{plugin_id}"
    return {
        "schema_version": "astrabridge-plugin-skill-registry-v1",
        "generated_at": "2026-06-25T20:20:00+08:00",
        "source_catalogs": [
            {
                "schema_version": "astrabridge-plugin-skill-source-catalog-v1",
                "source_catalog_id": catalog_id,
                "kind": "local",
                "display_name": f"{plugin_id} catalog",
                "source_path": str(source_root),
                "writable": True,
            }
        ],
        "plugins": [
            {
                "schema_version": "astrabridge-plugin-registry-record-v1",
                "record_id": f"plugin::{plugin_id}::{catalog_id}",
                "plugin_id": plugin_id,
                "source_catalog_id": catalog_id,
                "display_name": plugin_id,
                "install_status": install_status,
                "enablement_status": "disabled",
                "compatibility_status": "compatible",
                "version": installed_version or available_version or "1.2.3",
                "installed_version": installed_version,
                "available_version": available_version if install_status in {"available", "update_available"} else None,
                "install_root": str(target_root),
                "provenance": {
                    "schema_version": "astrabridge-plugin-skill-provenance-v1",
                    "source_path": str(source_root),
                    "manifest_path": str(source_root / ".codex-plugin" / "plugin.json"),
                },
            }
        ],
        "skills": [],
        "notes": [],
    }


def _case_record(case_id: str, passed: bool, result: dict[str, Any]) -> dict[str, Any]:
    artifacts = list(dict(result.get("artifact_paths") or {}).values())
    return {
        "case_id": case_id,
        "status": "pass" if passed else "fail",
        "result_status": result.get("status"),
        "artifact_paths": dict(result.get("artifact_paths") or {}),
        "rollback_status": dict(result.get("rollback_snapshot") or {}).get("status"),
        "errors": list(result.get("errors") or []),
        "artifacts": [str(item) for item in artifacts if str(item or "").strip()],
    }


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _default_artifact_root(repo_root: Path) -> Path:
    stamp = new_id("run").split("-", 1)[1]
    return repo_root / "PRIVATE" / "demo-runs" / f"plugin-install-smoke-{stamp}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run AstraBridge plugin install/update no-key smoke.")
    parser.add_argument("--artifact-root", default="", help="Optional artifact root override.")
    parser.add_argument("--repo-root", default="", help="Optional repository root override.")
    args = parser.parse_args(argv)
    report = run_plugin_install_smoke(
        artifact_root=Path(args.artifact_root).resolve() if args.artifact_root else None,
        repo_root=Path(args.repo_root).resolve() if args.repo_root else None,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if str(report.get("summary", {}).get("overall_status") or "") == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
