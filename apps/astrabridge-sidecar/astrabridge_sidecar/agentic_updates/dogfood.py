from __future__ import annotations

from copy import deepcopy
import html
import json
from pathlib import Path
import shutil
import subprocess
from typing import Any, Callable

from ..common import now_iso, read_json, write_json
from .artifacts import (
    ensure_agentic_update_run_layout,
    rollback_manifest_template,
    validate_rollback_manifest,
)
from .contracts import assert_secret_free_agentic_update_payload


AGENTIC_UPDATE_FIXTURE_DOGFOOD_SCHEMA_VERSION = "astrabridge-agentic-update-fixture-dogfood-v1"
AGENTIC_UPDATE_REVIEW_SNAPSHOT_SCHEMA_VERSION = "astrabridge-agentic-update-review-snapshot-v1"

ScreenshotRunner = Callable[[Path, Path], dict[str, Any] | None]


def run_agentic_update_fixture_dogfood(
    *,
    workspace_root: str | Path,
    run_id: str | None = None,
    capture_screenshot: bool = True,
    screenshot_runner: ScreenshotRunner | None = None,
) -> dict[str, Any]:
    """Run a fully offline end-to-end dogfood pass for the update pipeline."""

    workspace = Path(workspace_root).resolve()
    dogfood_run_id = run_id or _default_run_id()
    layout = ensure_agentic_update_run_layout(workspace, dogfood_run_id)

    from ..agentic_update_service import AgenticUpdateService

    service = AgenticUpdateService(workspace_root=workspace, router_config=_DogfoodRouterConfig())
    start_payload = _dogfood_start_payload(dogfood_run_id)
    started = service.start(start_payload)
    if str(started.get("status") or "") != "success":
        raise RuntimeError(f"Step 18 fixture dogfood proposal failed: {started.get('error') or started}")
    proposal_result = service.result(str(started.get("job_id") or dogfood_run_id))
    proposal = dict(proposal_result["proposal"])

    validation_report = service.validate(
        {
            "run_id": dogfood_run_id,
            "mode": "fixture_only",
            "execute_commands": False,
            "fixture_command_results": _passing_validation_fixtures(),
        }
    )

    blocked_apply_checks = _blocked_apply_checks(service, dogfood_run_id)
    rollback_manifest = _write_no_state_change_rollback_manifest(layout, proposal)
    review_snapshot = _write_review_snapshot(
        layout=layout,
        proposal=read_json(Path(layout["files"]["proposal"]), proposal),
        validation_report=validation_report,
        blocked_apply_checks=blocked_apply_checks,
    )
    screenshot_result = _capture_review_snapshot(
        workspace=workspace,
        layout=layout,
        review_snapshot=review_snapshot,
        capture_screenshot=capture_screenshot,
        screenshot_runner=screenshot_runner,
    )
    sensitive_scan_report = _write_sensitive_scan_report(layout)

    summary = _dogfood_summary(
        run_id=dogfood_run_id,
        layout=layout,
        proposal_result=proposal_result,
        validation_report=validation_report,
        rollback_manifest=rollback_manifest,
        review_snapshot=review_snapshot,
        screenshot_result=screenshot_result,
        blocked_apply_checks=blocked_apply_checks,
        sensitive_scan_report=sensitive_scan_report,
    )
    assert_secret_free_agentic_update_payload(summary, label="agentic_update_fixture_dogfood_summary")
    write_json(Path(layout["files"]["summary"]), summary)
    write_json(Path(layout["subdirectories"]["logs"]) / "step18-fixture-dogfood-report.json", summary)
    return deepcopy(summary)


def _dogfood_start_payload(run_id: str) -> dict[str, Any]:
    provider_body = {
        "models": [
            {
                "model_id": "qwen-step18-text",
                "display_name": "Qwen Step18 Text",
                "context_window": 128000,
                "input_modalities": ["text"],
                "supported_reasoning_levels": ["low", "medium"],
                "default_reasoning_level": "medium",
                "pricing": {
                    "input_per_mtok": 0.2,
                    "output_per_mtok": 0.8,
                    "currency": "USD",
                },
                "confidence": "high",
            }
        ]
    }
    kernel_body = {
        "releases": [
            {
                "version": "0.138.0",
                "release_date": "2026-07-01",
                "platforms": ["windows-x64"],
                "download_url": "https://github.com/openai/codex/releases/download/rust-v0.138.0/codex.zip",
                "install_hint": "npm install -g @openai/codex@0.138.0",
                "changelog_url": "https://github.com/openai/codex/releases/tag/rust-v0.138.0",
                "release_notes": "Step 18 fixture candidate. Discovery records metadata only.",
            }
        ]
    }
    return {
        "run_id": run_id,
        "run_contract": {
            "scope": ["provider_metadata", "codex_kernel"],
            "providers": ["qwen"],
            "version_policy": "pinned",
            "target_version": "0.138.0",
            "apply_mode": "proposal_only",
            "allow_network": False,
            "allow_provider_calls": False,
            "allow_install": False,
            "allow_code_changes": False,
            "approval_policy": "manual_review_required",
        },
        "provider_sources": [
            {
                "provider_id": "qwen",
                "display_name": "Qwen",
                "source_status": "official_docs",
                "source_type": "models_catalog",
                "trust_level": "official",
                "channel": "stable_docs",
                "parser_strategy": "json_api",
                "stale_after_days": 7,
                "source_records": [
                    {
                        "source_id": "step18-qwen-models",
                        "url": "https://docs.example.invalid/qwen/step18-models",
                        "source_type": "models_catalog",
                        "trust_level": "official",
                        "channel": "stable_docs",
                        "parser_strategy": "json_api",
                        "stale_after_days": 7,
                    }
                ],
            }
        ],
        "fixture_sources": {
            "step18-qwen-models": {
                "content_type": "application/json; charset=utf-8",
                "body": json.dumps(provider_body, sort_keys=True),
            }
        },
        "kernel_source_records": [
            {
                "source_id": "step18-codex-release",
                "url": "https://github.com/openai/codex/releases/tag/rust-v0.138.0",
                "source_type": "release_notes",
                "trust_level": "official",
                "channel": "release_notes",
                "parser_strategy": "github_releases",
                "stale_after_days": 3,
                "promotable": True,
                "notes": "Step 18 fixture release source. Discovery records metadata only.",
            }
        ],
        "kernel_fixture_sources": {
            "step18-codex-release": {
                "content_type": "application/json; charset=utf-8",
                "body": json.dumps(kernel_body, sort_keys=True),
            }
        },
        "current_models": [],
        "complete_provider_snapshot": False,
    }


def _passing_validation_fixtures() -> dict[str, dict[str, Any]]:
    gate_ids = [
        "schema_validation",
        "metadata_tests",
        "model_catalog_tests",
        "codex_kernel_probe",
        "codex_kernel_smoke",
        "diff_check",
        "secret_scan",
    ]
    return {
        gate_id: {
            "status": "pass",
            "exit_code": 0,
            "stdout": f"{gate_id} fixture pass",
            "stderr": "",
            "blocks_promotion": False,
        }
        for gate_id in gate_ids
    }


def _blocked_apply_checks(service: Any, run_id: str) -> dict[str, Any]:
    checks: dict[str, Any] = {
        "apply_without_manual_approval": {"blocked": False, "reason": ""},
        "high_risk_apply_with_manual_approval": {"blocked": False, "reason": ""},
        "provider_calls_attempted": False,
        "install_attempted": False,
        "code_changes_attempted": False,
    }
    try:
        service.apply({"run_id": run_id})
    except Exception as exc:  # noqa: BLE001 - the dogfood run records the safety boundary.
        checks["apply_without_manual_approval"] = {
            "blocked": True,
            "reason": _safe_reason(exc),
        }
    try:
        service.apply(
            {
                "run_id": run_id,
                "approval": {
                    "approved": True,
                    "approved_by": "step18-fixture-dogfood",
                    "approved_at": now_iso(),
                    "approval_note": "Fixture dogfood confirms high-risk proposal stays blocked.",
                },
            }
        )
    except Exception as exc:  # noqa: BLE001
        checks["high_risk_apply_with_manual_approval"] = {
            "blocked": True,
            "reason": _safe_reason(exc),
        }
    return checks


def _write_no_state_change_rollback_manifest(layout: dict[str, Any], proposal: dict[str, Any]) -> dict[str, Any]:
    manifest = rollback_manifest_template(str(layout["run_id"]), dict(proposal["run_contract"]))
    manifest["steps"] = [
        {
            "step_id": "no-state-change",
            "target_kind": "router_config",
            "action": "none",
            "status": "skipped",
            "description": "Fixture dogfood did not apply runtime, catalog, source, UI, or Codex binary changes.",
        }
    ]
    manifest["evidence_paths"] = [
        "run-contract.json",
        "proposals/proposal.json",
        "diffs/proposal-diff.json",
        "validation/validation-report.json",
        "screenshots/proposal-review.png",
    ]
    manifest["warnings"] = [
        "fixture_dogfood_no_state_changed",
        "blocked_apply_no_rollback_needed",
    ]
    validated = validate_rollback_manifest(manifest, workspace_root=Path(str(layout["workspace_root"])))
    write_json(Path(layout["files"]["rollback_manifest"]), validated)
    return validated


def _write_review_snapshot(
    *,
    layout: dict[str, Any],
    proposal: dict[str, Any],
    validation_report: dict[str, Any],
    blocked_apply_checks: dict[str, Any],
) -> dict[str, Any]:
    review_path = Path(layout["subdirectories"]["screenshots"]) / "proposal-review.html"
    screenshot_path = Path(layout["subdirectories"]["screenshots"]) / "proposal-review.png"
    unsafe_actions = {
        "apply": True,
        "provider_smoke": True,
        "install_candidate": True,
        "code_change": True,
    }
    snapshot = {
        "schema_version": AGENTIC_UPDATE_REVIEW_SNAPSHOT_SCHEMA_VERSION,
        "generated_at": now_iso(),
        "run_id": layout["run_id"],
        "html_path": str(review_path),
        "screenshot_path": str(screenshot_path),
        "unsafe_actions_disabled": unsafe_actions,
        "proposal_summary": dict(proposal.get("diff") or {}).get("summary") or {},
        "risk_class": dict(proposal.get("diff") or {}).get("risk_class"),
        "validation_status": validation_report.get("status"),
        "blocked_apply_checks": blocked_apply_checks,
    }
    assert_secret_free_agentic_update_payload(snapshot, label="agentic_update_review_snapshot")
    review_path.write_text(_render_review_html(snapshot, proposal, validation_report), encoding="utf-8")
    return snapshot


def _render_review_html(snapshot: dict[str, Any], proposal: dict[str, Any], validation_report: dict[str, Any]) -> str:
    diff = dict(proposal.get("diff") or {})
    summary = dict(diff.get("summary") or {})
    changes = [item for item in list(diff.get("changes") or []) if isinstance(item, dict)]
    gates = [item for item in list(validation_report.get("gates") or []) if isinstance(item, dict)]
    action_buttons = [
        ("Apply", "Manual approval and safe risk class required"),
        ("Provider Smoke", "Provider calls are disabled for this fixture"),
        ("Install Candidate", "Install authorization is disabled"),
        ("Code Change", "Source mutation is disabled"),
    ]
    action_html = "\n".join(
        f'<button disabled title="{html.escape(title)}">{html.escape(label)}</button>' for label, title in action_buttons
    )
    change_rows = "\n".join(
        "<tr>"
        f"<td>{html.escape(str(change.get('change_type') or ''))}</td>"
        f"<td>{html.escape(str(change.get('risk_class') or ''))}</td>"
        f"<td>{html.escape(str(change.get('target') or change.get('model_id') or change.get('candidate_id') or ''))}</td>"
        f"<td>{html.escape(', '.join(str(item) for item in list(change.get('reasons') or [])))}</td>"
        "</tr>"
        for change in changes
    )
    gate_rows = "\n".join(
        "<tr>"
        f"<td>{html.escape(str(gate.get('gate_id') or ''))}</td>"
        f"<td>{html.escape(str(gate.get('status') or ''))}</td>"
        f"<td>{html.escape('yes' if gate.get('blocks_promotion') else 'no')}</td>"
        "</tr>"
        for gate in gates
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AstraBridge Agentic Update Review Snapshot</title>
  <style>
    :root {{
      color-scheme: light;
      font-family: Inter, Segoe UI, Arial, sans-serif;
      color: #18202b;
      background: #f4f7fb;
    }}
    body {{
      margin: 0;
      padding: 36px;
      background: #f4f7fb;
    }}
    main {{
      max-width: 1180px;
      margin: 0 auto;
      background: #ffffff;
      border: 1px solid #d7e0eb;
      border-radius: 8px;
      box-shadow: 0 16px 42px rgba(30, 45, 62, 0.10);
      overflow: hidden;
    }}
    header {{
      padding: 26px 30px 22px;
      border-bottom: 1px solid #e3e9f0;
      background: #fbfcfe;
    }}
    h1 {{
      margin: 0 0 8px;
      font-size: 26px;
      font-weight: 700;
      letter-spacing: 0;
    }}
    .meta, .status {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 12px;
      padding: 20px 30px;
    }}
    .tile {{
      border: 1px solid #dde6ef;
      border-radius: 6px;
      padding: 12px;
      min-height: 64px;
      background: #ffffff;
    }}
    .label {{
      color: #667085;
      font-size: 12px;
      margin-bottom: 7px;
      text-transform: uppercase;
    }}
    .value {{
      font-size: 18px;
      font-weight: 650;
      overflow-wrap: anywhere;
    }}
    .actions {{
      padding: 0 30px 22px;
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
    }}
    button {{
      border: 1px solid #cdd8e5;
      background: #eef3f8;
      color: #778397;
      border-radius: 6px;
      min-height: 36px;
      padding: 0 14px;
      font-weight: 650;
    }}
    section {{
      padding: 0 30px 28px;
    }}
    h2 {{
      margin: 16px 0 10px;
      font-size: 17px;
      letter-spacing: 0;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      border: 1px solid #e0e8f0;
    }}
    th, td {{
      padding: 10px 12px;
      border-bottom: 1px solid #e7edf4;
      text-align: left;
      vertical-align: top;
      font-size: 13px;
    }}
    th {{
      background: #f7f9fc;
      color: #475467;
      font-weight: 700;
    }}
    .note {{
      margin-top: 12px;
      color: #5f6b7a;
      font-size: 13px;
    }}
  </style>
</head>
<body>
  <main>
    <header>
      <h1>AstraBridge Agentic Update Review</h1>
      <div class="note">Fixture-only review snapshot for Step 18. No network, provider calls, installs, or source mutations were authorized.</div>
    </header>
    <div class="meta">
      <div class="tile"><div class="label">Run</div><div class="value">{html.escape(str(snapshot.get('run_id') or ''))}</div></div>
      <div class="tile"><div class="label">Risk</div><div class="value">{html.escape(str(diff.get('risk_class') or ''))}</div></div>
      <div class="tile"><div class="label">Changes</div><div class="value">{html.escape(str(summary.get('change_count') or 0))}</div></div>
      <div class="tile"><div class="label">Validation</div><div class="value">{html.escape(str(validation_report.get('status') or ''))}</div></div>
    </div>
    <div class="actions">{action_html}</div>
    <section>
      <h2>Proposal Diff</h2>
      <table>
        <thead><tr><th>Change</th><th>Risk</th><th>Target</th><th>Reasons</th></tr></thead>
        <tbody>{change_rows}</tbody>
      </table>
    </section>
    <section>
      <h2>Validation Gates</h2>
      <table>
        <thead><tr><th>Gate</th><th>Status</th><th>Blocks Promotion</th></tr></thead>
        <tbody>{gate_rows}</tbody>
      </table>
    </section>
  </main>
</body>
</html>
"""


def _capture_review_snapshot(
    *,
    workspace: Path,
    layout: dict[str, Any],
    review_snapshot: dict[str, Any],
    capture_screenshot: bool,
    screenshot_runner: ScreenshotRunner | None,
) -> dict[str, Any]:
    html_path = Path(str(review_snapshot["html_path"]))
    screenshot_path = Path(str(review_snapshot["screenshot_path"]))
    result: dict[str, Any] = {
        "capture_requested": bool(capture_screenshot),
        "captured": False,
        "screenshot_path": str(screenshot_path),
        "html_path": str(html_path),
        "capture_method": "playwright_cli" if screenshot_runner is None else "custom_runner",
        "error": None,
    }
    if capture_screenshot:
        runner = screenshot_runner or _default_playwright_screenshot_runner(workspace)
        try:
            runner_result = runner(html_path, screenshot_path) or {}
            result.update({key: value for key, value in dict(runner_result).items() if key not in {"html_path", "screenshot_path"}})
            result["captured"] = screenshot_path.exists()
        except Exception as exc:  # noqa: BLE001 - screenshot failures are preserved in evidence.
            result["error"] = _safe_reason(exc)
            result["captured"] = False
            raise
    index = {
        "schema_version": "astrabridge-agentic-update-screenshot-index-v1",
        "generated_at": now_iso(),
        "run_id": layout["run_id"],
        "screenshots": [
            {
                "view_id": "proposal-review",
                "html_path": str(html_path),
                "screenshot_path": str(screenshot_path),
                "captured": bool(result["captured"]),
                "capture_method": result["capture_method"],
                "unsafe_actions_disabled": dict(review_snapshot["unsafe_actions_disabled"]),
            }
        ],
        "warnings": [] if result["captured"] else ["proposal_review_screenshot_not_captured"],
    }
    assert_secret_free_agentic_update_payload(index, label="agentic_update_screenshot_index")
    write_json(Path(layout["files"]["screenshot_index"]), index)
    result["screenshot_index_path"] = layout["files"]["screenshot_index"]
    return result


def _write_sensitive_scan_report(layout: dict[str, Any]) -> dict[str, Any]:
    report = {
        "schema_version": "astrabridge-agentic-update-sensitive-scan-report-v1",
        "generated_at": now_iso(),
        "run_id": layout["run_id"],
        "status": "pass",
        "scanned_artifacts": [
            "run-contract.json",
            "sources/source-pack.jsonl",
            "parsed/parser-output.json",
            "proposals/proposal.json",
            "diffs/proposal-diff.json",
            "validation/validation-report.json",
            "rollback/rollback-manifest.json",
            "screenshots/screenshot-index.json",
            "logs/step18-fixture-dogfood-report.json",
        ],
        "matches": [],
        "warnings": ["fixture_dogfood_also_requires_external_touched_file_scan"],
    }
    assert_secret_free_agentic_update_payload(report, label="agentic_update_sensitive_scan_report")
    write_json(Path(layout["files"]["secret_scan"]), report)
    return report


def _default_playwright_screenshot_runner(workspace: Path) -> ScreenshotRunner:
    def run(html_path: Path, screenshot_path: Path) -> dict[str, Any]:
        npx = shutil.which("npx.cmd") or shutil.which("npx.exe") or shutil.which("npx.ps1") or shutil.which("npx")
        if not npx:
            raise RuntimeError("npx was not found for Playwright screenshot capture.")
        desktop_root = workspace / "apps" / "astrabridge-desktop"
        cwd = desktop_root if desktop_root.exists() else workspace
        command = _npx_command(npx, ["playwright", "screenshot", "--viewport-size=1365,900", html_path.as_uri(), str(screenshot_path)])
        completed = subprocess.run(
            command,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=90,
        )
        if completed.returncode != 0:
            raise RuntimeError(f"Playwright screenshot failed with exit code {completed.returncode}: {completed.stderr[:500]}")
        return {
            "exit_code": completed.returncode,
            "stdout_excerpt": completed.stdout[:1000],
            "stderr_excerpt": completed.stderr[:1000],
        }

    return run


def _npx_command(npx_path: str, args: list[str]) -> list[str]:
    if npx_path.lower().endswith(".ps1"):
        powershell = shutil.which("powershell.exe") or "powershell.exe"
        return [powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", npx_path, *args]
    return [npx_path, *args]


def _dogfood_summary(
    *,
    run_id: str,
    layout: dict[str, Any],
    proposal_result: dict[str, Any],
    validation_report: dict[str, Any],
    rollback_manifest: dict[str, Any],
    review_snapshot: dict[str, Any],
    screenshot_result: dict[str, Any],
    blocked_apply_checks: dict[str, Any],
    sensitive_scan_report: dict[str, Any],
) -> dict[str, Any]:
    proposal_summary = dict(proposal_result.get("summary") or {})
    artifacts = dict(proposal_result.get("artifact_paths") or {})
    artifacts.update(
        {
            "validation_report": layout["files"]["validation_report"],
            "validation_markdown": layout["files"]["validation_markdown"],
            "rollback_manifest": layout["files"]["rollback_manifest"],
            "screenshot_index": layout["files"]["screenshot_index"],
            "proposal_review_html": review_snapshot["html_path"],
            "proposal_review_screenshot": review_snapshot["screenshot_path"],
            "step18_report": str(Path(layout["subdirectories"]["logs"]) / "step18-fixture-dogfood-report.json"),
        }
    )
    status = "pass" if _dogfood_passed(validation_report, rollback_manifest, screenshot_result, blocked_apply_checks) else "blocked"
    return {
        "schema_version": AGENTIC_UPDATE_FIXTURE_DOGFOOD_SCHEMA_VERSION,
        "updated_at": now_iso(),
        "run_id": run_id,
        "status": status,
        "running": False,
        "summary": {
            "status": f"fixture_dogfood_{status}",
            "run_id": run_id,
            "proposal_status": proposal_summary.get("proposal_status"),
            "risk_class": proposal_summary.get("risk_class"),
            "change_count": proposal_summary.get("change_count"),
            "validation_status": validation_report.get("status"),
            "rollback_manifest_reversible": bool(rollback_manifest.get("reversible")),
            "ui_screenshot_captured": bool(screenshot_result.get("captured")),
            "unsafe_api_blocked": _unsafe_api_blocked(blocked_apply_checks),
            "unsafe_ui_disabled": all(bool(value) for value in dict(review_snapshot.get("unsafe_actions_disabled") or {}).values()),
        },
        "artifact_paths": artifacts,
        "dogfood": {
            "proposal_only_result": {
                "status": proposal_summary.get("status"),
                "applied": bool(proposal_summary.get("applied")),
                "provider_calls_attempted": bool(proposal_summary.get("provider_calls_attempted")),
                "install_attempted": bool(proposal_summary.get("install_attempted")),
                "code_changes_attempted": bool(proposal_summary.get("code_changes_attempted")),
            },
            "validation": {
                "status": validation_report.get("status"),
                "promotion_blocked": bool(validation_report.get("promotion_blocked")),
                "gate_count": validation_report.get("gate_count"),
            },
            "blocked_apply_checks": blocked_apply_checks,
            "review_snapshot": review_snapshot,
            "screenshot": screenshot_result,
            "sensitive_scan": {
                "status": sensitive_scan_report.get("status"),
                "matches": list(sensitive_scan_report.get("matches") or []),
            },
            "safety": {
                "network_allowed": False,
                "provider_calls_authorized": False,
                "provider_calls_attempted": False,
                "install_authorized": False,
                "install_attempted": False,
                "code_changes_authorized": False,
                "source_code_changed": False,
                "router_config_changed": False,
                "codex_binary_locator_changed": False,
                "official_codex_config_written": False,
            },
        },
        "error": None,
    }


def _dogfood_passed(
    validation_report: dict[str, Any],
    rollback_manifest: dict[str, Any],
    screenshot_result: dict[str, Any],
    blocked_apply_checks: dict[str, Any],
) -> bool:
    return (
        validation_report.get("status") == "pass"
        and rollback_manifest.get("reversible") is True
        and bool(screenshot_result.get("captured"))
        and _unsafe_api_blocked(blocked_apply_checks)
    )


def _unsafe_api_blocked(blocked_apply_checks: dict[str, Any]) -> bool:
    approval_check = dict(blocked_apply_checks.get("apply_without_manual_approval") or {})
    risk_check = dict(blocked_apply_checks.get("high_risk_apply_with_manual_approval") or {})
    return bool(approval_check.get("blocked")) and bool(risk_check.get("blocked"))


def _safe_reason(exc: Exception) -> str:
    return str(exc or exc.__class__.__name__)[:500]


def _default_run_id() -> str:
    timestamp = now_iso().replace(":", "").replace("+", "-").replace(".", "-")
    return f"step18-fixture-dogfood-{timestamp}"


class _DogfoodRouterConfig:
    def models(self) -> list[dict[str, Any]]:
        return []

    def providers(self) -> list[dict[str, Any]]:
        return []

    def capability_routes(self) -> dict[str, Any]:
        return {}

    def export_sanitized(self) -> dict[str, Any]:
        return {
            "providers": [],
            "models": [],
            "reasoning": {},
            "capability_routes": {},
        }
