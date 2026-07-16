from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from astrabridge_sidecar.agentic_update_service import AgenticUpdateService
from astrabridge_sidecar.automations import AutomationService
from astrabridge_sidecar.project_service import ProjectService


class AgenticUpdateAutomationTests(unittest.TestCase):
    def test_agentic_update_check_template_is_disabled_and_safety_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            projects, workspace = _project(temp)
            updates = AgenticUpdateService(workspace_root=workspace, router_config=_ReadOnlyRouterConfig([]))
            service = AutomationService(projects, agentic_update_service=updates)

            created = service.create_agentic_update_check_template(
                {
                    "automation_id": "agentic-update-qwen",
                    "run_contract": {"scope": "provider_metadata", "providers": ["qwen"]},
                    "schedule": {"mode": "daily", "expression": "03:00", "timezone": "UTC"},
                    **_fixture_payload_parts(),
                }
            )

            automation = created["automation"]
            contract = automation["agentic_update"]["run_contract"]
            self.assertFalse(automation["enabled"])
            self.assertEqual(automation["kind"], "agentic_update_check")
            self.assertEqual(automation["schedule"]["mode"], "daily")
            self.assertEqual(automation["runtime"]["permission_mode"], "read-only")
            self.assertEqual(automation["workspace"]["mode"], "current_workspace")
            self.assertEqual(automation["limits"]["daily_run_limit"], 1)
            self.assertEqual(contract["apply_mode"], "proposal_only")
            self.assertFalse(contract["allow_network"])
            self.assertFalse(contract["allow_provider_calls"])
            self.assertFalse(contract["allow_install"])
            self.assertFalse(contract["allow_code_changes"])
            self.assertEqual(automation["agentic_update"]["network_policy"], "fixture_only")

    def test_agentic_update_check_run_now_fixture_creates_inbox_finding_and_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            projects, workspace = _project(temp)
            updates = AgenticUpdateService(workspace_root=workspace, router_config=_ReadOnlyRouterConfig([]))
            service = AutomationService(projects, agentic_update_service=updates)
            service.start()
            service.create_agentic_update_check_template(
                {
                    "automation_id": "agentic-update-qwen",
                    "providers": ["qwen"],
                    "allow_network": False,
                    "schedule": {"mode": "interval", "interval_minutes": 1},
                    **_fixture_payload_parts(),
                }
            )
            service.resume_automation("agentic-update-qwen")

            queued = service._scheduler.tick()  # noqa: SLF001
            result = service.execute_run(queued["queued_run_ids"][0])
            inbox_item = result["inbox_item"]
            manifest = json.loads(Path(result["artifact_ref"]).read_text(encoding="utf-8"))

            self.assertEqual(result["run"]["trigger"], "schedule")
            self.assertEqual(result["run"]["status"], "completed")
            self.assertEqual(result["run"]["signal"], "finding")
            self.assertEqual(inbox_item["disposition"], "finding")
            self.assertEqual(inbox_item["state"], "unread")
            self.assertTrue(any(str(ref).endswith("proposals\\proposal.json") or str(ref).endswith("proposals/proposal.json") for ref in result["run"]["artifact_refs"]))
            self.assertTrue(any(str(ref).endswith("diffs\\proposal-diff.json") or str(ref).endswith("diffs/proposal-diff.json") for ref in inbox_item["artifact_refs"]))
            self.assertTrue(any(str(ref).endswith("proposals\\proposal.json") or str(ref).endswith("proposals/proposal.json") for ref in manifest["artifact_refs"]))
            self.assertFalse((workspace / ".codex").exists())

    def test_agentic_update_check_rejects_apply_install_provider_call_and_code_change_jobs(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            projects, workspace = _project(temp)
            updates = AgenticUpdateService(workspace_root=workspace, router_config=_ReadOnlyRouterConfig([]))
            service = AutomationService(projects, agentic_update_service=updates)
            cases = [
                {"apply_mode": "verify_candidate", "allow_provider_calls": True},
                {"scope": "codex_kernel", "version_policy": "pinned", "target_version": "0.138.0", "apply_mode": "verify_candidate", "allow_install": True},
                {"scope": "provider_adapter", "apply_mode": "isolated_apply", "allow_code_changes": True},
            ]

            for index, run_contract in enumerate(cases):
                with self.subTest(run_contract=run_contract):
                    payload = {
                        "automation_id": f"unsafe-{index}",
                        "run_contract": {
                            "scope": "provider_metadata",
                            "providers": ["qwen"],
                            "allow_network": False,
                            "apply_mode": "proposal_only",
                            **run_contract,
                        },
                        "schedule": {"mode": "daily", "expression": "03:00", "timezone": "UTC"},
                        **_fixture_payload_parts(),
                    }
                    with self.assertRaises(ValueError):
                        service.create_agentic_update_check_template(payload)


class _ReadOnlyRouterConfig:
    def __init__(self, models: list[dict[str, Any]]) -> None:
        self._models = models

    def models(self) -> list[dict[str, Any]]:
        return [dict(item) for item in self._models]

    def capability_routes(self) -> dict[str, Any]:
        return {}


def _project(temp: str) -> tuple[ProjectService, Path]:
    root = Path(temp)
    workspace = root / "workspace"
    project_file = root / "demo.abproj"
    projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
    projects.create_project("Demo", project_file, workspace_root=workspace, entry_mode="new")
    return projects, workspace


def _fixture_payload_parts() -> dict[str, Any]:
    return {
        "provider_sources": [_provider_source("qwen-fixture", "https://example.test/qwen/models")],
        "fixture_sources": {
            "qwen-fixture": {
                "content_type": "application/json",
                "body": json.dumps(
                    {
                        "models": [
                            {
                                "model_id": "qwen/qwen-next",
                                "display_name": "Qwen Next",
                                "context_window": 128000,
                                "input_modalities": ["text"],
                                "supported_reasoning_levels": ["low", "medium"],
                                "default_reasoning_level": "medium",
                                "pricing": {"input_per_mtok": 0.2, "output_per_mtok": 0.8, "currency": "USD"},
                                "confidence": "high",
                            }
                        ]
                    }
                ),
            }
        },
        "current_models": [],
    }


def _provider_source(source_id: str, url: str) -> dict[str, Any]:
    return {
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
                "source_id": source_id,
                "url": url,
                "source_type": "models_catalog",
                "trust_level": "official",
                "channel": "stable_docs",
                "parser_strategy": "json_api",
                "stale_after_days": 7,
            }
        ],
    }
