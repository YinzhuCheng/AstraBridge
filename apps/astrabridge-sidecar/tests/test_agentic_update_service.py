from __future__ import annotations

from copy import deepcopy
import json
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from astrabridge_sidecar.agentic_update_service import AgenticUpdateService
from astrabridge_sidecar.agentic_updates import agentic_update_proposal_template
from astrabridge_sidecar.common import read_json
from astrabridge_sidecar.server import Handler


class AgenticUpdateServiceTests(unittest.TestCase):
    def test_start_status_result_and_list_runs_for_fixture_proposal(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            service = AgenticUpdateService(workspace_root=workspace, router_config=_ReadOnlyRouterConfig([]))

            started = service.start(_provider_fixture_payload(run_id="fixture-proposal"))
            status = service.status(started["job_id"])
            result = service.result(started["job_id"])
            runs = service.list_runs()

            self.assertEqual(started["status"], "success")
            self.assertEqual(status["status"], "success")
            self.assertEqual(result["summary"]["status"], "proposal_only_complete")
            self.assertEqual(result["proposal"]["run_id"], "fixture-proposal")
            self.assertEqual(result["proposal"]["apply_manifest"]["changed_paths"], [])
            self.assertFalse(result["mutations"]["router_config_changed"])
            self.assertFalse(result["mutations"]["source_code_changed"])
            self.assertFalse(result["mutations"]["codex_binary_locator_changed"])
            self.assertFalse(result["mutations"]["provider_credentials_changed"])
            self.assertIn("PRIVATE\\agentic-update-pipeline\\runs\\fixture-proposal", result["artifact_paths"]["summary"])
            self.assertTrue(Path(result["artifact_paths"]["proposal"]).exists())
            self.assertTrue(Path(result["artifact_paths"]["proposal_diff"]).exists())
            self.assertEqual(runs["runs"][0]["run_id"], "fixture-proposal")
            self.assertFalse((workspace / ".astrabridge").exists())
            self.assertFalse((workspace / ".codex").exists())
            self.assertFalse((workspace / "codex-locator.json").exists())

    def test_kimi_official_index_fixture_produces_adapter_gated_proposal_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            current_models = [
                {
                    "id": "kimi/kimi-k2.7-code",
                    "provider": "kimi",
                    "native_model": "kimi-k2.7-code",
                    "display_name": "Kimi K2.7 Code",
                    "advertised_context_window": 262144,
                    "input_modalities": ["text"],
                    "supported_reasoning_levels": ["low", "high", "xhigh"],
                    "default_reasoning_level": "high",
                }
            ]
            router_config = _ReadOnlyRouterConfig(current_models)
            service = AgenticUpdateService(workspace_root=workspace, router_config=router_config)

            started = service.start(_kimi_provider_fixture_payload(run_id="kimi-k3-proposal"))
            result = service.result(started["job_id"])
            findings = list(result["proposal"]["discovery_result"]["findings"])
            kimi_k3 = next(item for item in findings if item.get("model_id") == "kimi/kimi-k3")
            added_change = next(
                item
                for item in result["diff"]["changes"]
                if item.get("change_type") == "added_model" and item.get("model_id") == "kimi/kimi-k3"
            )

            self.assertEqual(started["status"], "success")
            self.assertEqual(result["diff"]["risk_class"], "requires_adapter_review")
            self.assertEqual(added_change["risk_class"], "requires_adapter_review")
            self.assertIn("provider_reasoning_parameter_requires_transport_mapping", added_change["reasons"])
            self.assertEqual(kimi_k3["candidate_metadata"]["native_supported_reasoning_levels"], ["low", "high", "max"])
            self.assertEqual(kimi_k3["adapter_requirements"]["reasoning_parameter"], "reasoning_effort")
            self.assertEqual(result["proposal"]["apply_manifest"]["changed_paths"], [])
            self.assertFalse(result["summary"]["provider_calls_attempted"])
            self.assertFalse(result["summary"]["applied"])
            self.assertEqual(result["mutations"]["changed_paths"], [])
            self.assertEqual(router_config.models(), current_models)
            self.assertFalse((workspace / ".astrabridge").exists())

    def test_failed_job_status_is_exposed_and_result_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            service = AgenticUpdateService(workspace_root=Path(temp_dir), router_config=_ReadOnlyRouterConfig([]))

            started = service.start(
                {
                    "run_id": "failed-proposal",
                    "run_contract": {
                        "scope": "provider_metadata",
                        "providers": ["qwen"],
                        "allow_network": False,
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
                                    "source_id": "bad-url",
                                    "url": "not-a-public-url",
                                    "trust_level": "official",
                                    "source_type": "models_catalog",
                                    "channel": "stable_docs",
                                    "parser_strategy": "json_api",
                                }
                            ],
                        }
                    ],
                }
            )

            status = service.status("failed-proposal")

            self.assertEqual(started["status"], "failed")
            self.assertEqual(status["status"], "failed")
            self.assertIn("HTTP(S)", status["error"])
            with self.assertRaises(RuntimeError):
                service.result(started["job_id"])

    def test_proposal_only_service_refuses_apply_provider_call_install_and_code_change_modes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            service = AgenticUpdateService(workspace_root=Path(temp_dir), router_config=_ReadOnlyRouterConfig([]))
            cases = [
                {
                    "scope": "provider_metadata",
                    "apply_mode": "isolated_apply",
                },
                {
                    "scope": "provider_metadata",
                    "apply_mode": "verify_candidate",
                    "allow_provider_calls": True,
                },
                {
                    "scope": "codex_kernel",
                    "apply_mode": "verify_candidate",
                    "allow_install": True,
                },
                {
                    "scope": "provider_adapter",
                    "apply_mode": "isolated_apply",
                    "allow_code_changes": True,
                },
            ]

            for index, contract in enumerate(cases):
                with self.subTest(contract=contract):
                    payload = {
                        "run_id": f"unsafe-{index}",
                        "run_contract": {
                            **contract,
                            "version_policy": "pinned" if contract["scope"] == "codex_kernel" else "stable",
                            "target_version": "0.138.0" if contract["scope"] == "codex_kernel" else None,
                        },
                    }
                    started = service.start(payload)
                    self.assertEqual(started["status"], "failed")

    def test_apply_metadata_only_fixture_and_rollback_restores_isolated_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            service = AgenticUpdateService(workspace_root=workspace, router_config=_ReadOnlyRouterConfig([]))
            service.start(_provider_fixture_payload(run_id="apply-fixture"))

            applied = service.apply(
                {
                    "run_id": "apply-fixture",
                    "approval": _approval(),
                    "router_config_snapshot": _router_snapshot(models=[]),
                    "generated_catalog_snapshot": _catalog_snapshot(models=[]),
                }
            )
            router_path = Path(applied["touched"]["router_config"])
            models_lock_path = Path(applied["touched"]["generated_models_lock"])
            router_after_apply = json.loads(router_path.read_text(encoding="utf-8"))
            catalog_after_apply = json.loads(models_lock_path.read_text(encoding="utf-8"))

            self.assertEqual(applied["status"], "applied_metadata_only")
            self.assertEqual(applied["track_ids"], ["provider_metadata"])
            self.assertEqual(applied["before_summary"]["router_model_count"], 0)
            self.assertEqual(applied["after_summary"]["router_model_count"], 1)
            self.assertTrue(any(item.get("id") == "qwen/qwen-next" for item in router_after_apply["models"]))
            self.assertTrue(any(item.get("id") == "qwen/qwen-next" for item in catalog_after_apply["models"]))
            self.assertTrue(Path(applied["rollback_manifest_path"]).exists())
            self.assertTrue(Path(applied["journal_path"]).exists())
            self.assertEqual(applied["tracks"][0]["track_id"], "provider_metadata")
            self.assertEqual(applied["tracks"][0]["status"], "committed")

            rollback = service.rollback({"run_id": "apply-fixture"})
            router_after_rollback = json.loads(router_path.read_text(encoding="utf-8"))
            catalog_after_rollback = json.loads(models_lock_path.read_text(encoding="utf-8"))

            self.assertEqual(rollback["status"], "rolled_back")
            self.assertEqual(router_after_rollback["models"], [])
            self.assertEqual(catalog_after_rollback["models"], [])

    def test_apply_capability_route_fixture_and_rollback_restores_isolated_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            service = AgenticUpdateService(workspace_root=workspace, router_config=_ReadOnlyRouterConfig([_vision_model()]))

            applied = service.apply(
                {
                    "proposal": _capability_route_proposal(run_id="apply-capability-route"),
                    "approval": _approval(),
                    "router_config_snapshot": _router_snapshot(models=[_vision_model()]),
                    "generated_catalog_snapshot": _catalog_snapshot(models=[_vision_model()]),
                }
            )
            router_path = Path(applied["touched"]["router_config"])
            router_after_apply = json.loads(router_path.read_text(encoding="utf-8"))
            route_after_apply = dict(router_after_apply["capability_routes"]["vision.analyze"])
            journal = json.loads(Path(applied["journal_path"]).read_text(encoding="utf-8"))

            self.assertEqual(applied["status"], "applied_track_updates")
            self.assertEqual(applied["track_ids"], ["capability_routes"])
            self.assertEqual(route_after_apply["mode"], "pinned")
            self.assertEqual(route_after_apply["provider_id"], "qwen")
            self.assertEqual(route_after_apply["model"], "qwen/qwen3-vl-plus")
            self.assertEqual(journal["status"], "committed")
            self.assertEqual(journal["tracks"][0]["track_id"], "capability_routes")
            self.assertEqual(journal["tracks"][0]["health_verdict"], "pass")
            self.assertTrue(Path(applied["rollback_manifest_path"]).exists())

            rollback = service.rollback({"run_id": "apply-capability-route"})
            router_after_rollback = json.loads(router_path.read_text(encoding="utf-8"))

            self.assertEqual(rollback["status"], "rolled_back")
            self.assertEqual(router_after_rollback["capability_routes"], {})

    def test_apply_mixed_metadata_and_capability_route_tracks_record_distinct_journal_history(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            service = AgenticUpdateService(workspace_root=workspace, router_config=_ReadOnlyRouterConfig([_vision_model()]))

            applied = service.apply(
                {
                    "proposal": _mixed_metadata_and_route_proposal(run_id="apply-mixed-tracks"),
                    "approval": _approval(),
                    "router_config_snapshot": _router_snapshot(models=[_vision_model()]),
                    "generated_catalog_snapshot": _catalog_snapshot(models=[_vision_model()]),
                }
            )
            journal = json.loads(Path(applied["journal_path"]).read_text(encoding="utf-8"))
            track_ids = [track["track_id"] for track in journal["tracks"]]

            self.assertEqual(applied["status"], "applied_track_updates")
            self.assertEqual(applied["track_ids"], ["provider_metadata", "capability_routes"])
            self.assertEqual(track_ids, ["provider_metadata", "capability_routes"])
            self.assertTrue(all(track["status"] == "committed" for track in journal["tracks"]))
            self.assertTrue(all(track["health_verdict"] == "pass" for track in journal["tracks"]))

    def test_supervised_run_applies_supported_tracks_and_records_policy_health_and_recovery_points(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            service = AgenticUpdateService(workspace_root=workspace, router_config=_ReadOnlyRouterConfig([_vision_model()]))

            result = service.supervised_run(
                {
                    "proposal": _mixed_metadata_and_route_proposal(run_id="supervised-pass"),
                    "router_config_snapshot": _router_snapshot(models=[_vision_model()]),
                    "generated_catalog_snapshot": _catalog_snapshot(models=[_vision_model()]),
                }
            )
            summary = read_json(workspace / "PRIVATE" / "agentic-update-pipeline" / "runs" / "supervised-pass" / "summary.json", {})

            self.assertEqual(result["status"], "applied")
            self.assertEqual(result["committed_tracks"], ["provider_metadata", "capability_routes"])
            self.assertEqual(result["track_results"][0]["status"], "committed")
            self.assertEqual(result["track_results"][1]["status"], "committed")
            self.assertEqual(result["track_results"][0]["health_verdicts"]["provider_metadata"], "pass")
            self.assertEqual(result["track_results"][1]["health_verdicts"]["capability_routes"], "pass")
            self.assertTrue(Path(result["artifact_paths"]["supervised_run_summary"]).exists())
            self.assertTrue(Path(result["artifact_paths"]["supervised_run_markdown"]).exists())
            self.assertEqual(summary["summary"]["supervised_status"], "applied")
            self.assertEqual(summary["summary"]["supervised_committed_tracks"], ["provider_metadata", "capability_routes"])

    def test_supervised_run_contains_rollout_after_unsupported_track_and_preserves_recovery_point(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            service = AgenticUpdateService(workspace_root=workspace, router_config=_ReadOnlyRouterConfig([]))

            result = service.supervised_run(
                {
                    "proposal": _mixed_metadata_and_kernel_proposal(run_id="supervised-contained", version="0.138.0"),
                    "router_config_snapshot": _router_snapshot(models=[]),
                    "generated_catalog_snapshot": _catalog_snapshot(models=[]),
                }
            )

            self.assertEqual(result["status"], "contained")
            self.assertEqual(result["committed_tracks"], ["provider_metadata"])
            self.assertEqual(result["stopped_after_track"], "codex_kernel")
            self.assertTrue(result["containment"]["active"])
            self.assertEqual(result["track_results"][1]["track_id"], "codex_kernel")
            self.assertEqual(result["track_results"][1]["status"], "blocked")
            self.assertIn("automation_mode_off", result["track_results"][1]["reasons"])
            self.assertTrue(Path(result["containment"]["recovery_points"][0]["rollback_manifest_path"]).exists())

    def test_supervised_run_respects_pause_switch_before_apply(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            service = AgenticUpdateService(workspace_root=workspace, router_config=_ReadOnlyRouterConfig([]))

            result = service.supervised_run(
                {
                    "proposal": _mixed_metadata_and_kernel_proposal(run_id="supervised-paused", version="0.138.0"),
                    "policy": {
                        "tracks": {
                            "provider_metadata": {
                                "paused": True,
                            }
                        }
                    },
                    "router_config_snapshot": _router_snapshot(models=[]),
                    "generated_catalog_snapshot": _catalog_snapshot(models=[]),
                }
            )

            self.assertEqual(result["status"], "blocked")
            self.assertEqual(result["committed_tracks"], [])
            self.assertEqual(result["stopped_after_track"], "provider_metadata")
            self.assertIn("track_paused", result["track_results"][0]["reasons"])

    def test_apply_refuses_high_risk_missing_approval_missing_rollback_and_unsafe_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            service = AgenticUpdateService(workspace_root=workspace, router_config=_ReadOnlyRouterConfig([]))
            service.start(_provider_fixture_payload(run_id="apply-refusals"))
            proposal = service.result("apply-refusals")["proposal"]

            with self.assertRaisesRegex(ValueError, "Manual approval"):
                service.apply(
                    {
                        "run_id": "apply-refusals",
                        "router_config_snapshot": _router_snapshot(models=[]),
                        "generated_catalog_snapshot": _catalog_snapshot(models=[]),
                    }
                )

            high_risk = deepcopy(proposal)
            high_risk["diff"]["risk_class"] = "requires_provider_smoke"
            high_risk["diff"]["changes"][0]["risk_class"] = "requires_provider_smoke"
            with self.assertRaisesRegex(ValueError, "risk_class"):
                service.apply(
                    {
                        "proposal": high_risk,
                        "approval": _approval(),
                        "router_config_snapshot": _router_snapshot(models=[]),
                        "generated_catalog_snapshot": _catalog_snapshot(models=[]),
                    }
                )

            missing_rollback = deepcopy(proposal)
            missing_rollback.pop("rollback_manifest", None)
            with self.assertRaisesRegex(ValueError, "rollback_manifest"):
                service.apply(
                    {
                        "proposal": missing_rollback,
                        "approval": _approval(),
                        "router_config_snapshot": _router_snapshot(models=[]),
                        "generated_catalog_snapshot": _catalog_snapshot(models=[]),
                    }
                )

            with self.assertRaises(Exception):
                service.apply(
                    {
                        "run_id": "apply-refusals",
                        "approval": _approval(),
                        "router_config_snapshot": _router_snapshot(models=[]),
                        "generated_catalog_snapshot": _catalog_snapshot(models=[]),
                        "isolated_state_root": "../escape",
                    }
                )

    def test_apply_refuses_ambiguous_capability_route_change(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            service = AgenticUpdateService(workspace_root=workspace, router_config=_ReadOnlyRouterConfig([_vision_model()]))
            proposal = _capability_route_proposal(run_id="apply-capability-route-refusal")
            proposal["diff"]["changes"][0]["details"] = {}

            with self.assertRaisesRegex(ValueError, "details.route_record"):
                service.apply(
                    {
                        "proposal": proposal,
                        "approval": _approval(),
                        "router_config_snapshot": _router_snapshot(models=[_vision_model()]),
                        "generated_catalog_snapshot": _catalog_snapshot(models=[_vision_model()]),
                    }
                )

    def test_code_change_plan_uses_dedicated_worktree_boundary_without_mutating_source(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir) / "workspace"
            workspace.mkdir()
            runtime_root = Path(temp_dir) / "runtime"
            readme = workspace / "README.md"
            readme.write_text("before\n", encoding="utf-8")
            service = AgenticUpdateService(
                workspace_root=workspace,
                runtime_root_resolver=lambda: runtime_root,
                router_config=_ReadOnlyRouterConfig([]),
            )
            proposal = _adapter_review_proposal(run_id="adapter-plan")

            manifest = service.code_change_plan({"proposal": proposal, "approval": _approval(), "boundary": {"dry_run": True}})
            rollback_manifest = json.loads(Path(manifest["rollback_manifest_path"]).read_text(encoding="utf-8"))
            worktree_path = Path(manifest["boundary"]["worktree_path"]).resolve()

            self.assertEqual(manifest["status"], "planned_dry_run")
            self.assertEqual(manifest["mode"], "code_change_worktree_plan")
            self.assertEqual(manifest["changed_paths"], [])
            self.assertIn("providers/transports/qwen_dashscope.py", "\n".join(manifest["planned_changed_paths"]))
            self.assertTrue(str(manifest["boundary"]["branch_name"]).startswith("codex/agentic-update/"))
            self.assertTrue(runtime_root.resolve() == worktree_path or runtime_root.resolve() in worktree_path.parents)
            self.assertTrue(Path(manifest["task_brief_path"]).exists())
            self.assertEqual(readme.read_text(encoding="utf-8"), "before\n")
            self.assertFalse(worktree_path.exists())
            self.assertEqual(rollback_manifest["rollback_targets"]["changed_source_files"][0]["branch_name"], manifest["boundary"]["branch_name"])
            self.assertTrue(any(step.get("requires_user_approval") for step in rollback_manifest["steps"]))
            self.assertTrue(all(step.get("destructive_without_approval") is not True for step in rollback_manifest["steps"]))

    def test_code_change_plan_refuses_main_workspace_without_opt_in_and_non_code_proposals(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            service = AgenticUpdateService(workspace_root=workspace, router_config=_ReadOnlyRouterConfig([]))
            proposal = _adapter_review_proposal(run_id="adapter-refusal")

            with self.assertRaisesRegex(ValueError, "allow_main_worktree_mutation"):
                service.code_change_plan(
                    {
                        "proposal": proposal,
                        "approval": _approval(),
                        "boundary": {"mode": "current_workspace", "dry_run": True},
                    }
                )

            service.start(_provider_fixture_payload(run_id="metadata-only-proposal"))
            with self.assertRaisesRegex(ValueError, "allow_code_changes"):
                service.code_change_plan({"run_id": "metadata-only-proposal", "approval": _approval()})

    def test_validation_gate_fixture_mode_passes_without_provider_keys(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            service = AgenticUpdateService(workspace_root=workspace, router_config=_ReadOnlyRouterConfig([]))
            service.start(_provider_fixture_payload(run_id="validate-pass"))

            report = service.validate(
                {
                    "run_id": "validate-pass",
                    "mode": "fixture_only",
                    "execute_commands": False,
                    "fixture_command_results": _passing_validation_fixtures("metadata_tests", "model_catalog_tests", "diff_check"),
                }
            )
            proposal_after_validation = json.loads(
                (workspace / "PRIVATE" / "agentic-update-pipeline" / "runs" / "validate-pass" / "proposals" / "proposal.json").read_text(
                    encoding="utf-8"
                )
            )

            self.assertEqual(report["status"], "pass")
            self.assertFalse(report["promotion_blocked"])
            self.assertTrue(Path(report["artifact_paths"]["validation_report"]).exists())
            self.assertTrue(Path(report["artifact_paths"]["validation_markdown"]).exists())
            self.assertEqual(proposal_after_validation["validation_result"]["status"], "pass")

    def test_validation_dry_run_records_gates_without_execution(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            service = AgenticUpdateService(workspace_root=Path(temp_dir), router_config=_ReadOnlyRouterConfig([]))
            service.start(_provider_fixture_payload(run_id="validate-dry-run"))

            report = service.validate({"run_id": "validate-dry-run", "mode": "dry_run", "execute_commands": False})

            self.assertEqual(report["mode"], "dry_run")
            self.assertEqual(report["status"], "blocked")
            self.assertTrue(report["promotion_blocked"])
            self.assertTrue(all(gate["status"] == "skipped" for gate in report["gates"]))
            self.assertIn("dry_run_validation_did_not_execute_gates", report["warnings"])

    def test_validation_provider_backed_gates_skip_without_authorization_and_block_promotion(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            service = AgenticUpdateService(workspace_root=Path(temp_dir), router_config=_ReadOnlyRouterConfig([]))

            report = service.validate(
                {
                    "proposal": _provider_smoke_required_proposal(run_id="validate-provider-skip"),
                    "mode": "provider_backed",
                    "execute_commands": False,
                    "fixture_command_results": _passing_validation_fixtures("metadata_tests", "model_catalog_tests", "diff_check"),
                }
            )
            gates = {gate["gate_id"]: gate for gate in report["gates"]}

            self.assertEqual(report["status"], "blocked")
            self.assertTrue(report["promotion_blocked"])
            self.assertEqual(gates["provider_compatibility_smoke"]["status"], "skipped")
            self.assertIn("provider_calls_not_authorized", gates["provider_compatibility_smoke"]["reasons"])
            self.assertTrue(any(target["gate_id"] == "provider_compatibility_smoke" for target in report["next_fix_targets"]))

    def test_validation_generates_dry_run_provider_smoke_cases_and_matrix_suggestions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            service = AgenticUpdateService(workspace_root=workspace, router_config=_ReadOnlyRouterConfig([_vision_model()]))

            report = service.validate(
                {
                    "proposal": _provider_smoke_required_proposal(run_id="validate-smoke-dry"),
                    "mode": "fixture_only",
                    "execute_commands": False,
                    "fixture_command_results": _passing_validation_fixtures("metadata_tests", "model_catalog_tests", "diff_check"),
                }
            )
            provider_gate = next(gate for gate in report["gates"] if gate["gate_id"] == "provider_compatibility_smoke")
            smoke_report = provider_gate["provider_smoke_report"]
            case_pack_path = Path(smoke_report["artifact_paths"]["agentic_update_case_pack"])
            case_pack = json.loads(case_pack_path.read_text(encoding="utf-8"))

            self.assertEqual(report["status"], "pass")
            self.assertEqual(provider_gate["status"], "pass")
            self.assertEqual(case_pack["cases"][0]["capability_id"], "vision.analyze")
            self.assertEqual(case_pack["cases"][0]["agentic_update"]["run_id"], "validate-smoke-dry")
            self.assertTrue(smoke_report["matrix_update_suggestions"])
            self.assertIn("validate-smoke-dry", smoke_report["matrix_update_suggestions"][0]["evidence_paths"][0])

    def test_validation_provider_backed_smoke_requires_credentials_before_runtime_call(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = _FakeCapabilityRuntime()
            service = AgenticUpdateService(
                workspace_root=Path(temp_dir),
                router_config=_ReadOnlyRouterConfig([_vision_model()]),
                provider_smoke_runtime_resolver=lambda: runtime,
            )

            report = service.validate(
                {
                    "proposal": _provider_smoke_required_proposal(run_id="validate-smoke-no-credential", allow_provider_calls=True),
                    "mode": "provider_backed",
                    "allow_provider_calls": True,
                    "execute_commands": False,
                    "fixture_command_results": _passing_validation_fixtures("metadata_tests", "model_catalog_tests", "diff_check"),
                    "credential_status": {"providers": [{"provider_id": "qwen", "available": False, "sources": []}]},
                }
            )
            provider_gate = next(gate for gate in report["gates"] if gate["gate_id"] == "provider_compatibility_smoke")

            self.assertEqual(report["status"], "blocked")
            self.assertTrue(report["promotion_blocked"])
            self.assertEqual(runtime.calls, [])
            self.assertIn("provider_credential_status_unavailable", provider_gate["reasons"])

    def test_validation_provider_backed_smoke_invokes_runtime_when_authorized_and_credentialed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = _FakeCapabilityRuntime()
            service = AgenticUpdateService(
                workspace_root=Path(temp_dir),
                router_config=_ReadOnlyRouterConfig([_vision_model()]),
                provider_smoke_runtime_resolver=lambda: runtime,
            )

            report = service.validate(
                {
                    "proposal": _provider_smoke_required_proposal(run_id="validate-smoke-provider", allow_provider_calls=True),
                    "mode": "provider_backed",
                    "allow_provider_calls": True,
                    "execute_commands": False,
                    "fixture_command_results": _passing_validation_fixtures("metadata_tests", "model_catalog_tests", "diff_check"),
                    "credential_status": {"providers": [{"provider_id": "qwen", "available": True, "sources": ["unit-test-redacted"]}]},
                }
            )
            provider_gate = next(gate for gate in report["gates"] if gate["gate_id"] == "provider_compatibility_smoke")

            self.assertEqual(report["status"], "pass")
            self.assertFalse(report["promotion_blocked"])
            self.assertTrue(runtime.calls)
            self.assertEqual(runtime.calls[0][0], "vision.analyze")
            self.assertEqual(provider_gate["provider_smoke_report"]["status"], "pass")

    def test_kernel_candidate_verification_fixture_marks_verified_with_probe_and_smoke_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            service = AgenticUpdateService(workspace_root=workspace, router_config=_ReadOnlyRouterConfig([]))
            proposal = _kernel_candidate_proposal(run_id="kernel-verify-pass", version="0.138.0")

            report = service.verify_kernel_candidate(
                {
                    "proposal": proposal,
                    "mode": "fixture",
                    "binary_locator": r"D:\Tools\OpenAI\Codex\bin\codex.exe",
                    "fixture_smoke_report": _passing_kernel_smoke_report(version="0.138.0"),
                }
            )

            self.assertEqual(report["status"], "verified")
            self.assertTrue(report["verified"])
            self.assertTrue(report["candidate"]["validation_state"]["verified"])
            self.assertEqual(report["matrix_update_suggestion"]["overall_status"], "verified")
            self.assertEqual(report["matrix_update_suggestion"]["smoke_result"], "passed")
            self.assertTrue(Path(report["artifact_paths"]["verification_report"]).exists())
            self.assertTrue(Path(report["artifact_paths"]["smoke_report"]).exists())
            self.assertTrue(Path(report["artifact_paths"]["kernel_probe_snapshot"]).exists())
            self.assertTrue(Path(report["artifact_paths"]["apply_journal"]).exists())
            self.assertEqual(report["activation"]["journal_status"], "committed")
            summary = read_json(
                workspace / "PRIVATE" / "agentic-update-pipeline" / "runs" / "kernel-verify-pass" / "summary.json",
                {},
            )
            self.assertIn("apply_journal", dict(summary.get("artifact_paths") or {}))
            self.assertEqual(dict(summary.get("summary") or {}).get("apply_tracks"), ["codex_kernel_candidate"])
            self.assertFalse((workspace / ".codex").exists())
            self.assertFalse((workspace / ".astrabridge").exists())

    def test_kernel_candidate_verification_missing_probe_blocks_verified_and_records_rollback(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            service = AgenticUpdateService(workspace_root=Path(temp_dir), router_config=_ReadOnlyRouterConfig([]))
            proposal = _kernel_candidate_proposal(run_id="kernel-verify-blocked", version="0.138.0")

            report = service.verify_kernel_candidate(
                {
                    "proposal": proposal,
                    "mode": "fixture",
                    "fixture_smoke_report": {
                        "schema_version": "codex-kernel-smoke-v1",
                        "summary": {"overall_status": "pass", "critical_failures": []},
                        "checks": [],
                    },
                    "baseline": {
                        "overall_status": "verified",
                        "binary_locator": r"D:\Tools\OpenAI\Codex\bin\codex.exe",
                    },
                }
            )

            self.assertEqual(report["status"], "blocked")
            self.assertFalse(report["verified"])
            self.assertIn("kernel_probe_evidence_missing", report["reasons"])
            self.assertTrue(report["rollback"]["required"])
            self.assertTrue(Path(report["rollback"]["manifest_path"]).exists())
            self.assertTrue(Path(report["artifact_paths"]["apply_journal"]).exists())
            self.assertEqual(report["activation"]["journal_status"], "rolled_back")
            self.assertEqual(report["candidate"]["validation_state"]["probe_evidence_paths"], [])

    def test_validation_failure_blocks_promotion_and_records_next_fix_target(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            service = AgenticUpdateService(workspace_root=Path(temp_dir), router_config=_ReadOnlyRouterConfig([]))
            service.start(_provider_fixture_payload(run_id="validate-fail"))
            fixtures = _passing_validation_fixtures("model_catalog_tests", "diff_check")
            fixtures["metadata_tests"] = {
                "status": "fail",
                "exit_code": 1,
                "stdout": "metadata test failed",
                "stderr": "AssertionError: bad metadata",
            }

            report = service.validate(
                {
                    "run_id": "validate-fail",
                    "mode": "fixture_only",
                    "execute_commands": False,
                    "fixture_command_results": fixtures,
                }
            )

            self.assertEqual(report["status"], "fail")
            self.assertTrue(report["promotion_blocked"])
            self.assertTrue(any(target["gate_id"] == "metadata_tests" for target in report["next_fix_targets"]))
            metadata_gate = next(gate for gate in report["gates"] if gate["gate_id"] == "metadata_tests")
            self.assertIn("metadata test failed", metadata_gate["stdout_excerpt"])

    def test_http_api_start_status_result_and_runs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            agentic_updates = AgenticUpdateService(workspace_root=workspace, router_config=_ReadOnlyRouterConfig([]))

            class Context:
                admin_token = "unit-admin-token"

            Context.agentic_updates = agentic_updates

            class AgenticUpdateHandler(Handler):
                pass

            AgenticUpdateHandler.context = Context()  # type: ignore[assignment]
            server = ThreadingHTTPServer(("127.0.0.1", 0), AgenticUpdateHandler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base_url = f"http://127.0.0.1:{server.server_address[1]}"
                started = _post_json(base_url + "/api/agentic-updates/start", _provider_fixture_payload(run_id="http-proposal"))
                status = _get_json(base_url + "/api/agentic-updates/http-proposal/status")
                result = _get_json(base_url + "/api/agentic-updates/http-proposal/result")
                runs = _get_json(base_url + "/api/agentic-updates/runs")
                applied = _post_json(
                    base_url + "/api/agentic-updates/apply",
                    {
                        "run_id": "http-proposal",
                        "approval": _approval(),
                        "router_config_snapshot": _router_snapshot(models=[]),
                        "generated_catalog_snapshot": _catalog_snapshot(models=[]),
                    },
                )
                rollback = _post_json(base_url + "/api/agentic-updates/rollback", {"run_id": "http-proposal"})
                code_change = _post_json(
                    base_url + "/api/agentic-updates/code-change-plan",
                    {
                        "proposal": _adapter_review_proposal(run_id="http-code-plan"),
                        "approval": _approval(),
                        "boundary": {"dry_run": True},
                    },
                )
                validation = _post_json(
                    base_url + "/api/agentic-updates/validate",
                    {
                        "run_id": "http-proposal",
                        "mode": "fixture_only",
                        "execute_commands": False,
                        "fixture_command_results": _passing_validation_fixtures("metadata_tests", "model_catalog_tests", "diff_check"),
                    },
                )
                kernel_verify = _post_json(
                    base_url + "/api/agentic-updates/kernel-verify",
                    {
                        "proposal": _kernel_candidate_proposal(run_id="http-kernel-verify", version="0.138.0"),
                        "mode": "fixture",
                        "binary_locator": r"D:\Tools\OpenAI\Codex\bin\codex.exe",
                        "fixture_smoke_report": _passing_kernel_smoke_report(version="0.138.0"),
                    },
                )
                supervised = _post_json(
                    base_url + "/api/agentic-updates/supervised-run",
                    {
                        "proposal": _mixed_metadata_and_route_proposal(run_id="http-supervised"),
                        "router_config_snapshot": _router_snapshot(models=[_vision_model()]),
                        "generated_catalog_snapshot": _catalog_snapshot(models=[_vision_model()]),
                    },
                )

                self.assertEqual(started["status"], "success")
                self.assertEqual(status["status"], "success")
                self.assertEqual(result["run_id"], "http-proposal")
                self.assertEqual(result["summary"]["status"], "proposal_only_complete")
                self.assertEqual(runs["runs"][0]["run_id"], "http-proposal")
                self.assertTrue(Path(result["artifact_paths"]["proposal"]).exists())
                self.assertEqual(applied["status"], "applied_metadata_only")
                self.assertEqual(rollback["status"], "rolled_back")
                self.assertEqual(code_change["status"], "planned_dry_run")
                self.assertEqual(code_change["mode"], "code_change_worktree_plan")
                self.assertEqual(validation["status"], "pass")
                self.assertEqual(kernel_verify["status"], "verified")
                self.assertEqual(supervised["status"], "applied")
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()

    def test_http_failed_result_returns_error_response(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            agentic_updates = AgenticUpdateService(workspace_root=Path(temp_dir), router_config=_ReadOnlyRouterConfig([]))

            class Context:
                admin_token = "unit-admin-token"

            Context.agentic_updates = agentic_updates

            class AgenticUpdateHandler(Handler):
                pass

            AgenticUpdateHandler.context = Context()  # type: ignore[assignment]
            server = ThreadingHTTPServer(("127.0.0.1", 0), AgenticUpdateHandler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base_url = f"http://127.0.0.1:{server.server_address[1]}"
                started = _post_json(
                    base_url + "/api/agentic-updates/start",
                    {
                        "run_id": "http-failed",
                        "run_contract": {
                            "scope": "provider_metadata",
                            "providers": ["qwen"],
                            "apply_mode": "isolated_apply",
                        },
                    },
                )

                self.assertEqual(started["status"], "failed")
                with self.assertRaises(urllib.error.HTTPError) as raised:
                    _get_json(base_url + "/api/agentic-updates/http-failed/result")
                self.assertEqual(raised.exception.code, 400)
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()


class _ReadOnlyRouterConfig:
    def __init__(self, models: list[dict[str, Any]]) -> None:
        self._models = models

    def models(self) -> list[dict[str, Any]]:
        return [dict(item) for item in self._models]

    def capability_routes(self) -> dict[str, Any]:
        return {}

    def upsert_provider(self, _payload: dict[str, Any]) -> None:
        raise AssertionError("Proposal-only update service must not mutate providers.")

    def upsert_model(self, _payload: dict[str, Any]) -> None:
        raise AssertionError("Proposal-only update service must not mutate models.")

    def delete_model(self, _model_id: str) -> None:
        raise AssertionError("Proposal-only update service must not delete models.")


class _FakeCapabilityRuntime:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def invoke(self, capability_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        self.calls.append((capability_id, dict(payload)))
        return {
            "schema_version": "fake-provider-result-v1",
            "capability_id": capability_id,
            "provider_id": payload.get("provider_id") or "qwen",
            "model": payload.get("model") or "qwen3-vl-plus",
            "text": "fixture vision response",
            "usage": {"input_tokens": 3, "output_tokens": 4, "total_tokens": 7},
            "artifact_refs": [{"artifact_type": "summary", "path": "D:/AstraBridge/PRIVATE/provider-smoke/fake-summary.json"}],
            "route": {
                "capability_id": capability_id,
                "route_mode": "explicit",
                "resolved_candidate": {
                    "provider_id": payload.get("provider_id") or "qwen",
                    "model": payload.get("model") or "qwen3-vl-plus",
                    "adapter_id": "qwen.vision",
                },
            },
        }


def _provider_fixture_payload(*, run_id: str) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "run_contract": {
            "scope": "provider_metadata",
            "providers": ["qwen"],
            "allow_network": False,
            "apply_mode": "proposal_only",
        },
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


def _kimi_provider_fixture_payload(*, run_id: str) -> dict[str, Any]:
    index_url = "https://platform.kimi.ai/docs/llms.txt"
    models_url = "https://platform.kimi.ai/docs/models.md"
    guide_url = "https://platform.kimi.ai/docs/guide/kimi-k3-quickstart.md"
    reasoning_url = "https://platform.kimi.ai/docs/guide/use-reasoning-effort.md"
    pricing_url = "https://platform.kimi.ai/docs/pricing/chat-k3.md"
    return {
        "run_id": run_id,
        "run_contract": {
            "scope": ["provider_metadata", "provider_adapter"],
            "providers": ["kimi"],
            "version_policy": "latest",
            "allow_network": False,
            "apply_mode": "proposal_only",
        },
        "provider_sources": [
            {
                "provider_id": "kimi",
                "display_name": "Kimi",
                "source_status": "official_docs",
                "source_type": "documentation_index",
                "trust_level": "official",
                "channel": "stable_docs",
                "parser_strategy": "llms_index",
                "stale_after_days": 1,
                "source_records": [
                    {
                        "source_id": "kimi-llms-index",
                        "url": index_url,
                        "source_type": "documentation_index",
                        "trust_level": "official",
                        "channel": "stable_docs",
                        "parser_strategy": "llms_index",
                        "stale_after_days": 1,
                        "capability_categories": ["models_catalog", "context_window", "reasoning", "pricing"],
                    }
                ],
            }
        ],
        "fixture_sources": {
            "kimi-llms-index": {
                "content_type": "text/plain; charset=utf-8",
                "body": "\n".join(
                    [
                        "# Kimi API Platform",
                        f"- [Model List]({models_url})",
                        f"- [Kimi K3]({guide_url})",
                        f"- [Reasoning Effort]({reasoning_url})",
                        f"- [Kimi K3 Pricing]({pricing_url})",
                    ]
                ),
            },
            models_url: {
                "content_type": "text/markdown; charset=utf-8",
                "body": "| Model Name | Description |\n| --- | --- |\n| `kimi-k3` | Native visual understanding and a 1M-token context window. |",
            },
            guide_url: {
                "content_type": "text/markdown; charset=utf-8",
                "body": "# Kimi K3\nKimi K3 supports text, image, and video input plus ToolCalls.\nmodel=\"kimi-k3\"",
            },
            reasoning_url: {
                "content_type": "text/markdown; charset=utf-8",
                "body": "# Reasoning Effort\n`kimi-k3` uses top-level `reasoning_effort`; supports \"low\", \"high\", and \"max\", with \"max\" as the default.",
            },
            pricing_url: {
                "content_type": "text/markdown; charset=utf-8",
                "body": "| Model | Unit | Cache Hit | Cache Miss | Output | Context |\n| --- | --- | --- | --- | --- | --- |\n| `kimi-k3` | 1M tokens | $0.30 | $3.00 | $15.00 | 1,048,576 tokens |",
            },
        },
        "current_models": [
            {
                "id": "kimi/kimi-k2.7-code",
                "provider": "kimi",
                "native_model": "kimi-k2.7-code",
                "display_name": "Kimi K2.7 Code",
                "advertised_context_window": 262144,
                "input_modalities": ["text"],
                "supported_reasoning_levels": ["low", "high", "xhigh"],
                "default_reasoning_level": "high",
            }
        ],
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


def _approval() -> dict[str, Any]:
    return {"approved": True, "approved_by": "unit-test", "approval_note": "metadata-only fixture"}


def _router_snapshot(*, models: list[dict[str, Any]], capability_routes: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "providers": [
            {
                "id": "qwen",
                "provider_id": "qwen",
                "display_name": "Qwen",
                "enabled": True,
                "adapter_type": "responses",
                "base_url": "https://example.test/v1",
                "default_model": "qwen-next",
                "request_timeout_ms": 300000,
                "stream_idle_timeout_ms": 300000,
                "env_key": "QWEN_API_KEY",
                "auth_mode": "os_keychain",
                "auth_key_ref": "redacted-in-apply",
                "proxy_mode": "direct",
                "proxy_url": "",
            }
        ],
        "models": [dict(item) for item in models],
        "reasoning": {
            "global_effort": "high",
            "provider_overrides": {},
            "model_overrides": {},
            "native_parameter_overrides": {},
        },
        "capability_routes": dict(capability_routes or {}),
    }


def _catalog_snapshot(*, models: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "models_lock": {
            "schema_version": "astrabridge-generated-catalog-v1",
            "generated_at": "2026-07-05T00:00:00+00:00",
            "models": [dict(item) for item in models],
        },
        "sources_lock": {
            "schema_version": "astrabridge-generated-catalog-v1",
            "generated_at": "2026-07-05T00:00:00+00:00",
            "sources": [],
            "fetch_status": [],
        },
    }


def _adapter_review_proposal(*, run_id: str) -> dict[str, Any]:
    contract = {
        "scope": "provider_adapter",
        "providers": ["qwen"],
        "allow_network": False,
        "apply_mode": "isolated_apply",
        "allow_code_changes": True,
    }
    proposal = agentic_update_proposal_template(contract, run_id=run_id)
    proposal["diff"] = {
        "schema_version": "astrabridge-agentic-update-diff-v1",
        "status": "changes_detected",
        "risk_class": "requires_adapter_review",
        "summary": {
            "change_count": 1,
            "risk_counts": {"requires_adapter_review": 1},
            "provider_model_candidate_count": 1,
            "kernel_candidate_count": 0,
        },
        "changes": [
            {
                "change_id": "transport-schema-review-required-qwen-next",
                "change_type": "transport_schema_review_required",
                "risk_class": "requires_adapter_review",
                "target": "qwen/qwen-next",
                "model_id": "qwen/qwen-next",
                "provider_id": "qwen",
                "reasons": ["unknown_field:enable_magic"],
                "details": {"warnings": ["unknown_field:enable_magic"]},
                "source_refs": [],
                "current_state_refs": [],
                "validation_requirements": ["adapter_review", "transport_tests", "provider_compatibility_smoke"],
            }
        ],
        "warnings": [],
        "artifact_paths": {},
    }
    proposal["validation_result"]["status"] = "not_run"
    return proposal


def _provider_smoke_required_proposal(*, run_id: str, allow_provider_calls: bool = False) -> dict[str, Any]:
    contract = {
        "scope": "provider_metadata",
        "providers": ["qwen"],
        "allow_network": bool(allow_provider_calls),
        "apply_mode": "verify_candidate" if allow_provider_calls else "proposal_only",
        "allow_provider_calls": allow_provider_calls,
    }
    proposal = agentic_update_proposal_template(contract, run_id=run_id)
    proposal["diff"] = {
        "schema_version": "astrabridge-agentic-update-diff-v1",
        "status": "changes_detected",
        "risk_class": "requires_provider_smoke",
        "summary": {
            "change_count": 1,
            "risk_counts": {"requires_provider_smoke": 1},
            "provider_model_candidate_count": 1,
            "kernel_candidate_count": 0,
        },
        "changes": [
            {
                "change_id": "changed-capability-claim-qwen-next",
                "change_type": "changed_capability_claim",
                "risk_class": "requires_provider_smoke",
                "target": "qwen/qwen3-vl-plus",
                "model_id": "qwen/qwen3-vl-plus",
                "provider_id": "qwen",
                "reasons": ["image_modality_requires_provider_smoke"],
                "details": {
                    "capability": "vision",
                    "candidate_metadata": {
                        "input_modalities": ["text", "image"],
                    },
                    "candidate_declared": True,
                    "verified": False,
                },
                "source_refs": [],
                "current_state_refs": [],
                "validation_requirements": ["schema_validation", "metadata_tests", "provider_compatibility_smoke"],
            }
        ],
        "warnings": [],
        "artifact_paths": {},
    }
    proposal["validation_result"]["status"] = "not_run"
    return proposal


def _capability_route_proposal(*, run_id: str) -> dict[str, Any]:
    contract = {
        "scope": "capability_routes",
        "providers": ["qwen"],
        "models": ["qwen/qwen3-vl-plus"],
        "allow_network": False,
        "apply_mode": "isolated_apply",
    }
    proposal = agentic_update_proposal_template(contract, run_id=run_id)
    proposal["diff"] = {
        "schema_version": "astrabridge-agentic-update-diff-v1",
        "status": "changes_detected",
        "risk_class": "metadata_only",
        "summary": {
            "change_count": 1,
            "risk_counts": {"metadata_only": 1},
            "provider_model_candidate_count": 0,
            "kernel_candidate_count": 0,
        },
        "changes": [
            {
                "change_id": "set-capability-route-vision-analyze",
                "change_type": "set_capability_route",
                "risk_class": "metadata_only",
                "target": "vision.analyze",
                "capability_id": "vision.analyze",
                "provider_id": "qwen",
                "reasons": ["manual_route_pin"],
                "details": {
                    "route_record": {
                        "mode": "pinned",
                        "provider_id": "qwen",
                        "model": "qwen/qwen3-vl-plus",
                    }
                },
                "source_refs": [],
                "current_state_refs": [],
                "validation_requirements": ["schema_validation", "diff_check"],
            }
        ],
        "warnings": [],
        "artifact_paths": {},
    }
    proposal["validation_result"]["status"] = "not_run"
    return proposal


def _mixed_metadata_and_route_proposal(*, run_id: str) -> dict[str, Any]:
    contract = {
        "scope": ["provider_metadata", "capability_routes"],
        "providers": ["qwen"],
        "models": ["qwen/qwen-next", "qwen/qwen3-vl-plus"],
        "allow_network": False,
        "apply_mode": "isolated_apply",
    }
    proposal = agentic_update_proposal_template(contract, run_id=run_id)
    proposal["discovery_result"]["findings"] = [
        {
            "model_id": "qwen/qwen-next",
            "provider_id": "qwen",
            "native_model": "qwen-next",
            "display_name": "Qwen Next",
            "candidate_metadata": {
                "advertised_context_window": 128000,
                "input_modalities": ["text"],
                "supported_reasoning_levels": ["low", "medium"],
                "default_reasoning_level": "medium",
                "pricing": {"input_per_mtok": 0.2, "output_per_mtok": 0.8, "currency": "USD"},
                "confidence": "high",
            },
            "source_refs": [
                {
                    "source_id": "qwen-fixture-source",
                    "source_url": "https://example.test/qwen/models",
                    "trust_level": "official",
                    "content_hash": "fixture-qwen-next",
                }
            ],
        }
    ]
    proposal["diff"] = {
        "schema_version": "astrabridge-agentic-update-diff-v1",
        "status": "changes_detected",
        "risk_class": "metadata_only",
        "summary": {
            "change_count": 2,
            "risk_counts": {"metadata_only": 2},
            "provider_model_candidate_count": 1,
            "kernel_candidate_count": 0,
        },
        "changes": [
            {
                "change_id": "add-qwen-next",
                "change_type": "added_model",
                "risk_class": "metadata_only",
                "target": "qwen/qwen-next",
                "model_id": "qwen/qwen-next",
                "provider_id": "qwen",
                "reasons": ["new_model_candidate"],
                "details": {},
                "source_refs": [],
                "current_state_refs": [],
                "validation_requirements": ["schema_validation", "metadata_tests", "diff_check"],
            },
            {
                "change_id": "set-capability-route-vision-analyze",
                "change_type": "set_capability_route",
                "risk_class": "metadata_only",
                "target": "vision.analyze",
                "capability_id": "vision.analyze",
                "provider_id": "qwen",
                "reasons": ["manual_route_pin"],
                "details": {
                    "route_record": {
                        "mode": "pinned",
                        "provider_id": "qwen",
                        "model": "qwen/qwen3-vl-plus",
                    }
                },
                "source_refs": [],
                "current_state_refs": [],
                "validation_requirements": ["schema_validation", "diff_check"],
            },
        ],
        "warnings": [],
        "artifact_paths": {},
    }
    proposal["validation_result"]["status"] = "not_run"
    return proposal


def _mixed_metadata_and_kernel_proposal(*, run_id: str, version: str) -> dict[str, Any]:
    proposal = _mixed_metadata_and_route_proposal(run_id=run_id)
    proposal["run_contract"]["scope"] = ["provider_metadata", "codex_kernel"]
    proposal["run_contract"]["version_policy"] = "pinned"
    proposal["run_contract"]["target_version"] = version
    proposal["diff"]["summary"]["change_count"] = 2
    proposal["diff"]["summary"]["kernel_candidate_count"] = 1
    proposal["diff"]["summary"]["risk_counts"] = {"metadata_only": 1, "requires_kernel_smoke": 1}
    proposal["diff"]["risk_class"] = "metadata_only"
    proposal["diff"]["changes"] = [
        dict(proposal["diff"]["changes"][0]),
        {
            "change_id": f"codex-kernel-candidate-{version}",
            "change_type": "codex_kernel_candidate",
            "risk_class": "requires_kernel_smoke",
            "target": version,
            "model_id": None,
            "provider_id": None,
            "reasons": ["codex_kernel_candidates_require_probe_and_smoke"],
            "details": {"candidate": _kernel_candidate(version=version)},
            "source_refs": [],
            "current_state_refs": [],
            "validation_requirements": ["codex_kernel_probe", "codex_kernel_smoke"],
        },
    ]
    return proposal


def _kernel_candidate_proposal(*, run_id: str, version: str) -> dict[str, Any]:
    contract = {
        "scope": "codex_kernel",
        "version_policy": "pinned",
        "target_version": version,
        "allow_network": False,
        "apply_mode": "verify_candidate",
    }
    proposal = agentic_update_proposal_template(contract, run_id=run_id)
    candidate = _kernel_candidate(version=version)
    proposal["discovery_result"]["findings"] = [candidate]
    proposal["diff"] = {
        "schema_version": "astrabridge-agentic-update-diff-v1",
        "status": "changes_detected",
        "risk_class": "requires_kernel_smoke",
        "summary": {
            "change_count": 1,
            "risk_counts": {"requires_kernel_smoke": 1},
            "provider_model_candidate_count": 0,
            "kernel_candidate_count": 1,
        },
        "changes": [
            {
                "change_id": f"codex-kernel-candidate-{version}",
                "change_type": "codex_kernel_candidate",
                "risk_class": "requires_kernel_smoke",
                "target": version,
                "model_id": None,
                "provider_id": None,
                "reasons": ["codex_kernel_candidates_require_probe_and_smoke"],
                "details": {"candidate": candidate},
                "source_refs": [],
                "current_state_refs": [],
                "validation_requirements": ["codex_kernel_probe", "codex_kernel_smoke"],
            }
        ],
        "warnings": [],
        "artifact_paths": {},
    }
    proposal["validation_result"]["status"] = "not_run"
    return proposal


def _kernel_candidate(*, version: str) -> dict[str, Any]:
    return {
        "candidate_id": f"codex-kernel-{version}",
        "kind": "codex_kernel_candidate",
        "version": version,
        "release_date": "2026-07-01",
        "platforms": ["windows-x64"],
        "distribution": {
            "download_url": "https://github.com/openai/codex/releases/download/rust-v0.138.0/codex.zip",
            "install_hint": "npm install -g @openai/codex@0.138.0",
            "changelog_url": "https://github.com/openai/codex/releases/tag/rust-v0.138.0",
        },
        "source_refs": [],
        "permission_policy": {
            "install_allowed": False,
            "switch_allowed": False,
            "apply_mode": "verify_candidate",
        },
        "side_effect_policy": {
            "writes_official_codex_config": False,
            "writes_project_codex_files": False,
            "writes_astrabridge_runtime_config": False,
            "installs_binary": False,
            "switches_binary": False,
        },
        "validation_state": {
            "status": "requires_kernel_probe_and_smoke",
            "verified": False,
            "probe_evidence_paths": [],
            "smoke_evidence_paths": [],
        },
        "promotion_state": {
            "status": "blocked_until_validation",
            "recommended": False,
            "requires_manual_review": True,
        },
        "warnings": [],
    }


def _passing_kernel_smoke_report(*, version: str) -> dict[str, Any]:
    return {
        "schema_version": "codex-kernel-smoke-v1",
        "summary": {"overall_status": "pass", "critical_failures": []},
        "checks": [
            {
                "check_id": "binary_discovery",
                "status": "pass",
                "critical": True,
                "details": {
                    "path": r"D:\Tools\OpenAI\Codex\bin\codex.exe",
                    "path_source": "env_override",
                    "launch_descriptor": r"D:\Tools\OpenAI\Codex\bin\codex.exe",
                    "version_text": f"codex-cli {version}",
                    "version_semver": version,
                    "version_parse_status": "ok",
                    "version_error": None,
                },
            }
        ],
    }


def _vision_model() -> dict[str, Any]:
    return {
        "id": "qwen/qwen3-vl-plus",
        "provider": "qwen",
        "native_model": "qwen3-vl-plus",
        "display_name": "Qwen VL Plus",
        "enabled": True,
        "advertised_context_window": 128000,
        "input_modalities": ["text", "image"],
        "supports_vision": True,
    }


def _passing_validation_fixtures(*gate_ids: str) -> dict[str, dict[str, Any]]:
    return {gate_id: {"status": "pass", "exit_code": 0, "stdout": f"{gate_id} passed", "stderr": ""} for gate_id in gate_ids}


def _post_json(url: str, payload: dict[str, Any]) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "X-Admin-Session-Token": "unit-admin-token",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def _get_json(url: str) -> dict[str, Any]:
    with urllib.request.urlopen(url, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


if __name__ == "__main__":
    unittest.main()
