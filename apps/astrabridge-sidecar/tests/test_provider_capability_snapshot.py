from __future__ import annotations

from datetime import datetime, timezone
import os
import sys
import tempfile
import threading
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from astrabridge_sidecar.modal_service import ModalService
from astrabridge_sidecar.profile_service import ProfileService
from astrabridge_sidecar.project_service import ProjectService
from astrabridge_sidecar.provider_capability_snapshot import (
    PROVIDER_CAPABILITY_MANIFEST_SCHEMA_VERSION,
    PROVIDER_CAPABILITY_SNAPSHOT_SCHEMA_VERSION,
    build_verified_capability_snapshot,
    current_model_provider_contract,
    describe_capability_snapshot_manifest,
)
from astrabridge_sidecar.router_config_service import RouterConfigService
from astrabridge_sidecar.runtime_service import RuntimeService
from astrabridge_sidecar.task_service import TaskService


class ProviderCapabilitySnapshotTests(unittest.TestCase):
    def _router_config(self, root: Path) -> RouterConfigService:
        profiles = ProfileService(root / "profiles.json")
        return RouterConfigService(profiles, root / "router.json")

    def _model_record(self, router_config: RouterConfigService, model_id: str) -> dict[str, object]:
        return next(item for item in router_config.models() if str(item.get("id") or "") == model_id)

    def test_router_config_records_aggregated_verified_capability_snapshot_from_matrix(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            router_config = self._router_config(root)
            model = self._model_record(router_config, "qwen/qwen3-vl-plus")
            provider = next(item for item in router_config.providers() if str(item.get("id") or "") == "qwen")
            contract = current_model_provider_contract(model, provider=provider)
            observed_at = datetime.now(timezone.utc).isoformat()
            matrix = {
                "schema_version": "astrabridge-provider-model-compatibility-matrix-v1",
                "generated_at": observed_at,
                "entries": [
                    {
                        "entry_id": "qwen/qwen3-vl-plus:vision.analyze",
                        "entry_kind": "model",
                        "provider_id": "qwen",
                        "model_id": "qwen/qwen3-vl-plus",
                        "overall_status": "verified",
                        "declared_capability": {},
                        "runtime_normalized_contract": {
                            "multimodal_lane": {
                                "capability_id": "vision.analyze",
                                "eligible_for_auto_route": True,
                                "eligible_for_pinned_route": True,
                                "adapter_family": "chat_multimodal_vision",
                                "adapter_id": "qwen.vision.chat.v1",
                                "route_resolution_status": "ok",
                                "request_shape_validation_status": "pass",
                                "required_modalities": ["image"],
                                "declared_modalities": ["text", "image"],
                                "exposure_state": "verified_runnable",
                            }
                        },
                        "validated_evidence": {
                            "validation_status": "pass",
                            "validation_scope": ["capability:vision.analyze", "exposure:verified_runnable"],
                            "evidence_paths": ["PRIVATE/provider-matrix/qwen-vl-summary.json"],
                            "last_verified_at": observed_at,
                            "known_failures": [],
                            "known_pitfalls": [],
                        },
                    }
                ],
            }

            router_config.record_provider_compatibility_matrix(matrix)
            refreshed = self._model_record(router_config, "qwen/qwen3-vl-plus")

            self.assertEqual(refreshed["verified_capability_snapshot_status"], "verified")
            snapshot = dict(refreshed.get("verified_capability_snapshot") or {})
            self.assertEqual(snapshot["schema_version"], PROVIDER_CAPABILITY_SNAPSHOT_SCHEMA_VERSION)
            self.assertEqual(snapshot["transport_signature"], contract["transport_signature"])
            self.assertEqual(snapshot["capabilities"]["vision.analyze"]["eligible_for_pinned_route"], True)
            self.assertEqual(snapshot["graph_capabilities"]["input_port_types"], ["image"])
            self.assertEqual(dict(snapshot.get("manifest") or {})["schema_version"], PROVIDER_CAPABILITY_MANIFEST_SCHEMA_VERSION)
            self.assertTrue(str(dict(snapshot.get("manifest") or {}).get("digest") or "").startswith("sha256:"))
            self.assertEqual(refreshed["verified_capability_snapshot_verification_state"], "verified")

    def test_router_config_marks_snapshot_stale_after_adapter_signature_change(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            router_config = self._router_config(root)
            model = self._model_record(router_config, "qwen/qwen3-vl-plus")
            provider = next(item for item in router_config.providers() if str(item.get("id") or "") == "qwen")
            snapshot = build_verified_capability_snapshot(
                model=model,
                provider=provider,
                matrix_entries=[
                    {
                        "overall_status": "verified",
                        "runtime_normalized_contract": {
                            "multimodal_lane": {
                                "capability_id": "vision.analyze",
                                "eligible_for_auto_route": True,
                                "eligible_for_pinned_route": True,
                                "adapter_family": "chat_multimodal_vision",
                                "adapter_id": "qwen.vision.chat.v1",
                                "route_resolution_status": "ok",
                                "request_shape_validation_status": "pass",
                                "required_modalities": ["image"],
                                "declared_modalities": ["text", "image"],
                                "exposure_state": "verified_runnable",
                            }
                        },
                        "validated_evidence": {
                            "validation_status": "pass",
                            "validation_scope": ["capability:vision.analyze"],
                            "evidence_paths": ["PRIVATE/provider-matrix/qwen-vl-summary.json"],
                            "last_verified_at": "2026-07-17T10:00:00+09:00",
                            "known_failures": [],
                            "known_pitfalls": [],
                        },
                    }
                ],
                created_at="2026-07-17T10:00:00+09:00",
            )
            snapshot["transport_signature"] = "stale-signature"

            refreshed = router_config.record_verified_capability_snapshot("qwen/qwen3-vl-plus", snapshot)

            self.assertEqual(refreshed["verified_capability_snapshot_status"], "stale")
            self.assertEqual(refreshed["verified_capability_snapshot_verification_state"], "drifted")

    def test_snapshot_manifest_marks_expired_evidence_when_freshness_window_is_past(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            router_config = self._router_config(root)
            model = self._model_record(router_config, "qwen/qwen3-vl-plus")
            provider = next(item for item in router_config.providers() if str(item.get("id") or "") == "qwen")
            contract = current_model_provider_contract(model, provider=provider)
            snapshot = build_verified_capability_snapshot(
                model=model,
                provider=provider,
                matrix_entries=[],
                created_at="2025-01-01T00:00:00+00:00",
            )

            manifest_state = describe_capability_snapshot_manifest(snapshot, current_contract=contract)

            self.assertEqual(manifest_state["verification_state"], "expired")
            self.assertEqual(manifest_state["freshness_status"], "expired")

    def test_runtime_requires_current_snapshot_for_multimodal_ports(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            previous_runtime_root = os.environ.get("ASTRABRIDGE_RUNTIME_ROOT")
            os.environ["ASTRABRIDGE_RUNTIME_ROOT"] = temp_dir
            try:
                root = Path(temp_dir)
                workspace = root / "workspace"
                workspace.mkdir()
                (workspace / "PRIVATE").mkdir()
                (workspace / ".astrabridge").mkdir()
                projects = ProjectService(store_path=root / "projects.json", session_path=root / "current_project.json")
                projects.create_project("Snapshot gating", root / "snapshot.abproj", workspace_root=workspace)
                router_config = self._router_config(root)
                runtime = RuntimeService(
                    projects,
                    ModalService(projects.require_shell_state_root),
                    router_config_service=router_config,
                )
                compiled_nodes = {
                    "node_vision": {
                        "input_ports": [{"port_id": "image_in", "port_type": "image", "required": True}],
                        "output_ports": [{"port_id": "report", "port_type": "text"}],
                    }
                }
                node_map = {
                    "node_vision": {
                        "node_id": "node_vision",
                        "provider_id": "qwen",
                        "model_id": "qwen/qwen3-vl-plus",
                    }
                }

                with self.assertRaisesRegex(ValueError, "verified capability snapshot"):
                    runtime._graph_live_require_current_capability_snapshots(  # noqa: SLF001
                        compiled_nodes=compiled_nodes,
                        node_map=node_map,
                        configured_models=router_config.models(),
                    )
            finally:
                if previous_runtime_root is None:
                    os.environ.pop("ASTRABRIDGE_RUNTIME_ROOT", None)
                else:
                    os.environ["ASTRABRIDGE_RUNTIME_ROOT"] = previous_runtime_root

    def test_live_run_policy_snapshot_pins_current_model_capability_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            previous_runtime_root = os.environ.get("ASTRABRIDGE_RUNTIME_ROOT")
            os.environ["ASTRABRIDGE_RUNTIME_ROOT"] = temp_dir
            try:
                root = Path(temp_dir)
                workspace = root / "workspace"
                (workspace / "PRIVATE").mkdir(parents=True)
                (workspace / ".astrabridge").mkdir()
                projects = ProjectService(
                    store_path=root / "projects.json",
                    session_path=root / "current_project.json",
                )
                projects.create_project("Pinned snapshot", root / "snapshot.abproj", workspace_root=workspace)
                tasks = TaskService(projects)
                tasks.create_task("Snapshot task")
                router_config = self._router_config(root)
                model = self._model_record(router_config, "qwen/qwen3.7-plus")
                provider = next(item for item in router_config.providers() if str(item.get("id") or "") == "qwen")
                snapshot = build_verified_capability_snapshot(
                    model=model,
                    provider=provider,
                    matrix_entries=[
                        {
                            "overall_status": "verified",
                            "runtime_normalized_contract": {
                                "multimodal_lane": {
                                    "capability_id": "vision.analyze",
                                    "eligible_for_auto_route": True,
                                    "eligible_for_pinned_route": True,
                                    "adapter_family": "chat_multimodal_vision",
                                    "adapter_id": "qwen.vision.chat.v1",
                                    "route_resolution_status": "ok",
                                    "request_shape_validation_status": "pass",
                                    "required_modalities": [],
                                    "declared_modalities": ["text"],
                                    "exposure_state": "verified_runnable",
                                }
                            },
                            "validated_evidence": {
                                "validation_status": "pass",
                                "validation_scope": ["capability:vision.analyze"],
                                "evidence_paths": ["PRIVATE/provider-matrix/qwen-summary.json"],
                                "last_verified_at": "2026-07-17T10:00:00+09:00",
                                "known_failures": [],
                                "known_pitfalls": [],
                            },
                        }
                    ],
                    created_at="2026-07-17T10:00:00+09:00",
                )
                router_config.record_verified_capability_snapshot("qwen/qwen3.7-plus", snapshot)
                graph = tasks.instantiate_graph_template("custom_blank_graph")["graph"]
                runtime = RuntimeService(
                    projects,
                    ModalService(projects.require_shell_state_root),
                    task_service=tasks,
                    router_config_service=router_config,
                )
                started = threading.Event()
                release = threading.Event()

                runtime._validate_graph_live_run_submission = lambda _payload: {  # type: ignore[method-assign]
                    "graph": graph,
                    "task": tasks.current_task() or {},
                    "graph_id": graph["graph_id"],
                    "run_budget": {"limits": {"total_tokens": 10}},
                    "run_token_limit": 10,
                    "compiled_plan": {
                        "entry_node_ids": ["node_start_here"],
                        "topology": {"parallel_group_count": 1, "max_parallelism": 1},
                        "parallel_groups": [{"group_id": "group_0", "node_ids": ["node_start_here"]}],
                        "nodes": [{"node_id": "node_start_here"}],
                    },
                    "compiled_nodes": {"node_start_here": {"node_id": "node_start_here"}},
                    "node_map": {"node_start_here": dict(graph["nodes"][0])},
                    "prepared_nodes": {},
                    "parent_thread_id": "",
                    "model_capability_snapshots": {
                        "qwen/qwen3.7-plus": {
                            "snapshot_status": "verified",
                            "snapshot": snapshot,
                            "contract": current_model_provider_contract(model, provider=provider),
                        }
                    },
                }

                def fake_execute(payload: dict[str, object]) -> dict[str, object]:
                    started.set()
                    release.wait(timeout=2)
                    return {"live_run": {"run_status": "completed"}}

                runtime.execute_task_graph_run = fake_execute  # type: ignore[method-assign]
                receipt = runtime.queue_task_graph_run(
                    {
                        "graph_id": graph["graph_id"],
                        "budget": {"limits": {"total_tokens": 10}},
                    }
                )
                run_id = str(receipt["live_run"]["run_id"])
                durable = tasks.durable_run_store().load_run(run_id, include_events=True)
                self.assertIsNotNone(durable)
                pinned = dict(dict(durable.get("run_policy_snapshot") or {}).get("model_capability_snapshots") or {})
                self.assertIn("qwen/qwen3.7-plus", pinned)
                self.assertEqual(str(dict(pinned["qwen/qwen3.7-plus"]).get("snapshot_status") or ""), "verified")
                self.assertTrue(
                    str(dict(dict(pinned["qwen/qwen3.7-plus"]).get("snapshot") or {}).get("manifest", {}).get("digest") or "").startswith("sha256:")
                )
                release.set()
                runtime._graph_scheduler.wait(run_id, timeout=3)
                runtime.shutdown()
            finally:
                if previous_runtime_root is None:
                    os.environ.pop("ASTRABRIDGE_RUNTIME_ROOT", None)
                else:
                    os.environ["ASTRABRIDGE_RUNTIME_ROOT"] = previous_runtime_root


if __name__ == "__main__":
    unittest.main()
