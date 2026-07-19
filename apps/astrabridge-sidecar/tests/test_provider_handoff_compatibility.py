from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from astrabridge_sidecar.modal_service import ModalService
from astrabridge_sidecar.project_service import ProjectService
from astrabridge_sidecar.project_context_service import ProjectContextService
from astrabridge_sidecar.runtime_service import RuntimeService
from astrabridge_sidecar.server import Handler
from astrabridge_sidecar.task_conversation_service import TaskConversationService
from astrabridge_sidecar.task_service import TaskService


class ProviderHandoffCompatibilityTests(unittest.TestCase):
    def test_task_handoff_view_exposes_active_and_previous_lanes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(root / "recent.json")
            projects.create_project("Demo", root / "demo.abproj", workspace_root=workspace, entry_mode="existing")
            tasks = TaskService(projects)
            task = tasks.create_task(
                "Same task",
                thread_id="thread-openai",
                settings={
                    "profile_id": "openai-default",
                    "provider_id": "openai",
                    "model": "gpt-5.5",
                    "reasoning_effort": "high",
                    "permission_mode": "auto",
                },
            )
            tasks.bind_thread(
                thread_id="thread-kimi",
                settings={
                    "profile_id": "kimi-default",
                    "provider_id": "kimi",
                    "model": "kimi-k2.6",
                    "reasoning_effort": "high",
                    "permission_mode": "auto",
                },
                make_active=False,
            )

            event = tasks.record_provider_handoff(
                from_thread_id="thread-openai",
                to_thread_id="thread-kimi",
                settings={
                    "profile_id": "kimi-default",
                    "provider_id": "kimi",
                    "model": "kimi-k2.6",
                    "reasoning_effort": "high",
                    "permission_mode": "auto",
                },
                reused_existing=True,
            )

            self.assertEqual(event["from_provider_id"], "openai")
            self.assertEqual(event["from_model"], "gpt-5.5")
            self.assertEqual(event["from_reasoning_effort"], "high")

            task_view = tasks.task_view(tasks.current_task())
            self.assertIsNotNone(task_view)
            lane_state = dict((task_view or {}).get("lane_state") or {})
            self.assertEqual(lane_state["lane_count"], 2)
            self.assertEqual(lane_state["handoff_count"], 1)
            self.assertEqual((lane_state["active_lane"] or {}).get("thread_id"), "thread-kimi")
            self.assertEqual((lane_state["active_lane"] or {}).get("label"), "kimi / kimi-k2.6")
            self.assertEqual((lane_state["previous_lane"] or {}).get("thread_id"), "thread-openai")
            self.assertEqual((lane_state["previous_lane"] or {}).get("label"), "openai / gpt-5.5")
            self.assertGreaterEqual(((lane_state["latest_handoff"] or {}).get("transition_summary") or {}).get("warning_count"), 1)

            conversation = TaskConversationService(projects, tasks).conversation(task_id=str(task.get("task_id") or ""))
            thread = dict(conversation.get("thread") or {})
            self.assertEqual((((thread.get("lane_state") or {}).get("active_lane") or {}).get("label")), "kimi / kimi-k2.6")
            self.assertEqual((((thread.get("lane_state") or {}).get("previous_lane") or {}).get("label")), "openai / gpt-5.5")

            handler = Handler.__new__(Handler)
            handler.context = SimpleNamespace(tasks=tasks)
            compact = handler._compact_task(tasks.current_task())  # type: ignore[attr-defined]
            self.assertEqual((((compact.get("lane_state") or {}).get("active_lane") or {}).get("label")), "kimi / kimi-k2.6")
            self.assertEqual((((compact.get("lane_state") or {}).get("previous_lane") or {}).get("label")), "openai / gpt-5.5")
            self.assertEqual((compact.get("handoff_events") or [])[0]["from_provider_id"], "openai")

    def test_cross_provider_projection_warning_path_keeps_lane_state_secret_free(self) -> None:
        class FakeClient:
            def __init__(self) -> None:
                self.requests: list[tuple[str, dict[str, object]]] = []

            def request(self, method: str, params: dict[str, object], timeout: float | None = None) -> dict[str, object]:
                self.requests.append((method, params))
                if method == "thread/read":
                    return {"thread": {"id": "thread-openai"}}
                if method == "thread/start":
                    return {"thread": {"id": "thread-deepseek-fresh", "name": "Fresh DS"}}
                raise AssertionError(f"Unexpected method {method}")

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(root / "recent.json")
            projects.create_project("Demo", root / "demo.abproj", workspace_root=workspace, entry_mode="existing")
            tasks = TaskService(projects)
            tasks.create_task(
                "Same task",
                thread_id="thread-openai",
                settings={
                    "profile_id": "openai-default",
                    "provider_id": "openai",
                    "model": "gpt-5.5",
                    "reasoning_effort": "high",
                    "permission_mode": "auto",
                },
            )
            runtime = RuntimeService(projects, ModalService(projects.require_shell_state_root), task_service=tasks)
            runtime._cache_thread_entry(  # noqa: SLF001
                "thread-openai",
                {
                    "thread": {
                        "id": "thread-openai",
                        "shellSettings": {
                            "profile_id": "openai-default",
                            "provider_id": "openai",
                            "model": "gpt-5.5",
                            "reasoning_effort": "high",
                        },
                        "turns": [
                            {
                                "id": "turn-source",
                                "items": [
                                    {
                                        "type": "agentMessage",
                                        "id": "agent-source",
                                        "text": "Reviewed the current task.",
                                        "providerData": {
                                            "normalized": {
                                                "text": "Reviewed the current task.",
                                                "reasoning_summary": "Need to inspect the repo before editing.",
                                                "reasoning_state": {
                                                    "provider_id": "openai",
                                                    "model_id": "openai/gpt-5.5",
                                                    "replayable": True,
                                                    "visible_summary": "Need to inspect the repo before editing.",
                                                    "thought_signature": "private-signature",
                                                    "opaque_artifacts": [
                                                        {
                                                            "encrypted_reasoning": "opaque-secret",
                                                            "response_id": "resp_123",
                                                            "summary": "private chain",
                                                        }
                                                    ],
                                                },
                                                "tool_calls": [
                                                    {
                                                        "id": "call-readme",
                                                        "name": "read_file",
                                                        "arguments_json": "{\"path\":\"README.md\"}",
                                                    }
                                                ],
                                                "finish_reason": "completed",
                                            }
                                        },
                                    }
                                ],
                            }
                        ],
                    }
                },
            )

            _thread_id, handoff = runtime._ensure_provider_thread_for_turn(  # noqa: SLF001
                FakeClient(),
                source_thread_id="thread-openai",
                profile={"profile_id": "deepseek-default", "provider_id": "deepseek", "model": "deepseek-v4-pro", "reasoning_effort": "max"},
                model="deepseek-v4-pro",
                effort="max",
                permission_mode="auto",
                collaboration_mode=None,
            )

            self.assertEqual(handoff["from_provider_id"], "openai")
            self.assertEqual(handoff["from_model"], "gpt-5.5")
            self.assertEqual(handoff["transition_summary"]["dropped_artifacts"], 1)
            self.assertTrue(any("Opaque provider reasoning artifacts were dropped" in warning for warning in handoff["transition_summary"]["warnings"]))
            self.assertTrue(any("provider-private fields" in warning for warning in handoff["transition_summary"]["warnings"]))
            handoff_bundle = dict(handoff.get("neutral_handoff_bundle") or {})
            self.assertEqual(handoff_bundle["projection_mode"], "task_context_fresh_thread")
            self.assertTrue(str(handoff_bundle.get("projection_digest") or ""))
            self.assertTrue(str(handoff_bundle.get("lineage_digest") or ""))
            bundle_path = workspace / str(handoff_bundle.get("path") or "")
            self.assertTrue(bundle_path.is_file())
            bundle_payload = json.loads(bundle_path.read_text(encoding="utf-8"))
            self.assertEqual(bundle_payload["lineage"]["source_thread_id"], "thread-openai")
            self.assertEqual(bundle_payload["lineage"]["target_thread_id"], "thread-deepseek-fresh")
            self.assertEqual(bundle_payload["lineage"]["target_provider_id"], "deepseek")
            self.assertEqual(bundle_payload["projection_digest"], handoff_bundle["projection_digest"])
            self.assertNotIn("opaque-secret", json.dumps(bundle_payload, ensure_ascii=False))
            self.assertNotIn("resp_123", json.dumps(bundle_payload, ensure_ascii=False))
            self.assertNotIn("private-signature", json.dumps(bundle_payload, ensure_ascii=False))

            task_view = tasks.task_view(tasks.current_task())
            compact_handoff = (((task_view or {}).get("lane_state") or {}).get("latest_handoff") or {})
            self.assertEqual((((task_view or {}).get("lane_state") or {}).get("previous_lane") or {}).get("label"), "openai / gpt-5.5")
            self.assertGreaterEqual(((compact_handoff.get("transition_summary") or {}).get("warning_count")), 2)
            self.assertIn("requested tool call(s): read_file", str((compact_handoff.get("transition_summary") or {}).get("projection_preview") or ""))
            self.assertEqual(str(dict(compact_handoff.get("neutral_handoff_bundle") or {}).get("projection_digest") or ""), handoff_bundle["projection_digest"])

            handler = Handler.__new__(Handler)
            handler.context = SimpleNamespace(tasks=tasks)
            compact = handler._compact_task(tasks.current_task())  # type: ignore[attr-defined]
            compact_text = json.dumps(compact, ensure_ascii=False)
            self.assertIn("provider-private fields", compact_text)
            self.assertNotIn("opaque-secret", compact_text)
            self.assertNotIn("resp_123", compact_text)
            self.assertNotIn("private-signature", compact_text)

            context = ProjectContextService(
                projects,
                task_service=tasks,
                task_conversation_service=TaskConversationService(projects, tasks),
            )
            inputs = context.context_inputs(
                thread_id="thread-deepseek-fresh",
                provider_id="deepseek",
                model_id="deepseek-v4-pro",
            )
            self.assertTrue(any(str(item.get("type") or "") == "mention" for item in inputs))
            self.assertTrue(any("Latest neutral handoff bundle:" in str(item.get("text") or "") for item in inputs if str(item.get("type") or "") == "text"))
            self.assertTrue(any(str(item.get("path") or "").endswith(bundle_path.as_posix()) for item in inputs if str(item.get("type") or "") == "mention"))

            reloaded_tasks = TaskService(projects)
            reloaded_context = ProjectContextService(
                projects,
                task_service=reloaded_tasks,
                task_conversation_service=TaskConversationService(projects, reloaded_tasks),
            )
            reloaded_inputs = reloaded_context.context_inputs(
                thread_id="thread-deepseek-fresh",
                provider_id="deepseek",
                model_id="deepseek-v4-pro",
            )
            self.assertTrue(any("Latest neutral handoff bundle:" in str(item.get("text") or "") for item in reloaded_inputs if str(item.get("type") or "") == "text"))
            self.assertTrue(any(str(item.get("path") or "").endswith(bundle_path.as_posix()) for item in reloaded_inputs if str(item.get("type") or "") == "mention"))

    def test_reused_target_thread_handoff_persists_neutral_bundle_with_reused_projection_mode(self) -> None:
        class FakeClient:
            def __init__(self) -> None:
                self.requests: list[tuple[str, dict[str, object]]] = []

            def request(self, method: str, params: dict[str, object], timeout: float | None = None) -> dict[str, object]:
                self.requests.append((method, params))
                if method == "thread/read":
                    return {"thread": {"id": str(params.get("threadId") or "")}}
                raise AssertionError(f"Unexpected method {method}")

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            workspace.mkdir()
            projects = ProjectService(root / "recent.json")
            projects.create_project("Demo", root / "demo.abproj", workspace_root=workspace, entry_mode="existing")
            tasks = TaskService(projects)
            tasks.create_task(
                "Same task",
                thread_id="thread-openai",
                settings={
                    "profile_id": "openai-default",
                    "provider_id": "openai",
                    "model": "gpt-5.5",
                    "reasoning_effort": "high",
                    "permission_mode": "auto",
                },
            )
            tasks.bind_thread(
                thread_id="thread-deepseek-existing",
                settings={
                    "profile_id": "deepseek-default",
                    "provider_id": "deepseek",
                    "model": "deepseek-v4-pro",
                    "reasoning_effort": "max",
                    "permission_mode": "auto",
                },
                make_active=False,
            )
            runtime = RuntimeService(projects, ModalService(projects.require_shell_state_root), task_service=tasks)
            runtime._cache_thread_entry(  # noqa: SLF001
                "thread-openai",
                {
                    "thread": {
                        "id": "thread-openai",
                        "shellSettings": {
                            "profile_id": "openai-default",
                            "provider_id": "openai",
                            "model": "gpt-5.5",
                            "reasoning_effort": "high",
                        },
                        "turns": [
                            {
                                "id": "turn-source",
                                "items": [
                                    {
                                        "type": "agentMessage",
                                        "id": "agent-source",
                                        "text": "Reviewed the same task.",
                                        "providerData": {
                                            "normalized": {
                                                "text": "Reviewed the same task.",
                                                "tool_calls": [
                                                    {
                                                        "id": "call-openai-1",
                                                        "name": "read_file",
                                                        "arguments_json": "{\"path\":\"README.md\"}",
                                                    }
                                                ],
                                            }
                                        },
                                    }
                                ],
                            }
                        ],
                    }
                },
            )

            thread_id, handoff = runtime._ensure_provider_thread_for_turn(  # noqa: SLF001
                FakeClient(),
                source_thread_id="thread-openai",
                profile={"profile_id": "deepseek-default", "provider_id": "deepseek", "model": "deepseek-v4-pro", "reasoning_effort": "max"},
                model="deepseek-v4-pro",
                effort="max",
                permission_mode="auto",
                collaboration_mode=None,
            )

            self.assertEqual(thread_id, "thread-deepseek-existing")
            handoff_bundle = dict(handoff.get("neutral_handoff_bundle") or {})
            self.assertEqual(handoff_bundle["projection_mode"], "reused_provider_thread")
            self.assertEqual(handoff_bundle["target_thread_id"], "thread-deepseek-existing")
            self.assertTrue(str(handoff_bundle.get("projection_digest") or ""))
            bundle_path = workspace / str(handoff_bundle.get("path") or "")
            self.assertTrue(bundle_path.is_file())
            bundle_payload = json.loads(bundle_path.read_text(encoding="utf-8"))
            self.assertEqual(bundle_payload["lineage"]["projection_mode"], "reused_provider_thread")
            self.assertEqual(bundle_payload["lineage"]["target_thread_id"], "thread-deepseek-existing")


if __name__ == "__main__":
    unittest.main()
