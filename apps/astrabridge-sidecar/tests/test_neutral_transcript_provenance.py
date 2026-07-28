from __future__ import annotations

import json
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

from astrabridge_sidecar.providers.history_projector import (
    HistoryProjector,
    NeutralMessage,
    ReasoningArtifact,
    build_neutral_transcript,
)


class NeutralTranscriptProvenanceTests(unittest.TestCase):
    endpoint_fingerprint = "a" * 64
    adapter_signature = "b" * 64
    now = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)

    @staticmethod
    def _replayable_profile() -> SimpleNamespace:
        return SimpleNamespace(
            capabilities=SimpleNamespace(supports_reasoning_replay=True, supports_tool_result_images=False),
            reasoning_policy=SimpleNamespace(allow_cross_provider_replay=False),
        )

    def _provenance(self, *, expires_at: str = "2026-07-28T00:00:00+00:00") -> dict[str, object]:
        return {
            "schema_version": "astrabridge-reasoning-artifact-provenance-v1",
            "issuer": {
                "provider_id": "qwen",
                "model_id": "qwen3.7-plus",
                "endpoint_fingerprint": self.endpoint_fingerprint,
                "adapter_signature": self.adapter_signature,
            },
            "lineage": {
                "thread_id": "thread-qwen",
                "turn_id": "turn-1",
                "item_id": "message-1",
                "tool_call_id": "call-readme",
            },
            "replay": {
                "eligible": True,
                "scope": "same_issuer_endpoint_model",
                "retention": "ephemeral",
                "issued_at": "2026-07-27T00:00:00+00:00",
                "expires_at": expires_at,
            },
        }

    def _same_route_project(self, *, artifacts: list[ReasoningArtifact], messages: list[NeutralMessage]):
        with patch(
            "astrabridge_sidecar.providers.history_projector.get_provider_profile",
            return_value=self._replayable_profile(),
        ):
            return HistoryProjector().project(
                source_provider="qwen",
                target_provider="qwen",
                source_model_id="qwen3.7-plus",
                target_model_id="qwen3.7-plus",
                source_endpoint_fingerprint=self.endpoint_fingerprint,
                target_endpoint_fingerprint=self.endpoint_fingerprint,
                source_adapter_signature=self.adapter_signature,
                target_adapter_signature=self.adapter_signature,
                now=self.now,
                neutral_messages=messages,
                artifacts=artifacts,
            )

    def test_same_route_replay_requires_complete_current_provenance_and_repairs_tool_pair(self) -> None:
        result = self._same_route_project(
            messages=[
                NeutralMessage(
                    role="assistant",
                    text="Use the existing task context.",
                    tool_call_id="call-readme",
                    tool_name="read_file",
                    provider_data={"arguments_json": '{"path":"README.md"}'},
                    lineage={"thread_id": "thread-qwen", "turn_id": "turn-1", "item_id": "message-1"},
                )
            ],
            artifacts=[
                ReasoningArtifact(
                    provider_id="qwen",
                    model_id="qwen3.7-plus",
                    kind="reasoning_state",
                    replayable=True,
                    payload={
                        "visible_summary": "Read the project guide before changing code.",
                        "opaque_provider_blob": "must-not-persist",
                        "thought_signature": "must-not-persist",
                    },
                    provenance=self._provenance(),
                )
            ],
        )

        self.assertEqual(result.dropped_artifacts, 0)
        self.assertEqual(result.replayable_artifact_count, 1)
        descriptor = result.replayable_artifacts[0]
        self.assertEqual(descriptor["schema_version"], "astrabridge-reasoning-artifact-replay-descriptor-v1")
        self.assertNotIn("payload", descriptor)
        self.assertNotIn("opaque_provider_blob", json.dumps(descriptor, ensure_ascii=False))
        self.assertNotIn("thought_signature", json.dumps(descriptor, ensure_ascii=False))
        self.assertTrue(any(item.get("role") == "tool" and item.get("tool_call_id") == "call-readme" for item in result.messages))
        self.assertTrue(any(item.get("entry_id") == "repair:call-readme" for item in result.transcript_entries))

    def test_stale_or_incomplete_provenance_always_records_a_drop(self) -> None:
        result = self._same_route_project(
            messages=[NeutralMessage(role="assistant", text="Continue from the safe summary.")],
            artifacts=[
                ReasoningArtifact(
                    provider_id="qwen",
                    model_id="qwen3.7-plus",
                    kind="reasoning_state",
                    replayable=True,
                    payload={"visible_summary": "Stale thought summary."},
                    provenance=self._provenance(expires_at="2026-07-26T00:00:00+00:00"),
                ),
                ReasoningArtifact(
                    provider_id="qwen",
                    model_id="qwen3.7-plus",
                    kind="reasoning_state",
                    replayable=True,
                    payload={"visible_summary": "Incomplete thought summary."},
                    provenance={},
                ),
            ],
        )

        self.assertEqual(result.replayable_artifacts, [])
        self.assertEqual(result.dropped_artifacts, 2)
        self.assertEqual(len(result.artifact_drop_records), 2)
        reasons = {reason for item in result.artifact_drop_records for reason in list(item.get("reasons") or [])}
        self.assertIn("artifact_provenance_stale", reasons)
        self.assertIn("provenance_schema_invalid", reasons)
        self.assertTrue(any(item.get("role") == "system" for item in result.messages))

    def test_cross_provider_transcript_keeps_visible_continuity_but_redacts_private_state(self) -> None:
        result = HistoryProjector().project(
            source_provider="openai",
            target_provider="deepseek",
            neutral_messages=[
                NeutralMessage(
                    role="user",
                    text="Review this using sk-not-a-real-secret-123456.",
                    lineage={"thread_id": "thread-openai", "turn_id": "turn-1", "item_id": "user-1"},
                ),
                NeutralMessage(
                    role="assistant",
                    text="I will inspect the task state.",
                    tool_call_id="call-state",
                    tool_name="read_file",
                    provider_data={"arguments_json": '{"path":"TASK.md"}'},
                    lineage={"thread_id": "thread-openai", "turn_id": "turn-1", "item_id": "agent-1"},
                ),
                NeutralMessage(
                    role="tool",
                    text="Tool returned pk-not-a-real-token-123456",
                    tool_call_id="call-state",
                    lineage={"thread_id": "thread-openai", "turn_id": "turn-1", "item_id": "tool-1"},
                ),
            ],
            artifacts=[
                ReasoningArtifact(
                    provider_id="openai",
                    model_id="gpt-5.5",
                    kind="reasoning_state",
                    replayable=True,
                    payload={
                        "visible_summary": "Inspect TASK.md before edits.",
                        "encrypted_reasoning": "opaque-private-chain",
                        "response_id": "resp-private",
                    },
                    provenance={},
                )
            ],
        )
        transcript = build_neutral_transcript(
            transcript_entries=[
                *result.transcript_entries,
                {
                    "entry_id": "untrusted-entry",
                    "role": "assistant",
                    "entry_kind": "visible_output",
                    "content": "Only this visible text may survive.",
                    "untrusted_provider_blob": "must-not-survive",
                },
            ],
            projected_messages=result.messages,
            replayable_artifacts=result.replayable_artifacts,
            artifact_drop_records=result.artifact_drop_records,
            lineage={"task_id": "task-1", "source_thread_id": "thread-openai", "target_thread_id": "thread-deepseek"},
            task_state={"task_id": "task-1", "goal_summary": "Safely continue the task."},
            checkpoint_refs=[{"save_id": "checkpoint-1", "description": "Before provider handoff."}],
        )

        transcript_text = json.dumps(transcript, ensure_ascii=False)
        self.assertEqual(transcript["schema_version"], "astrabridge-neutral-transcript-v1")
        self.assertEqual(transcript["lineage"]["source_thread_id"], "thread-openai")
        self.assertEqual(transcript["checkpoints"][0]["checkpoint_id"], "checkpoint-1")
        self.assertTrue(any(entry.get("entry_kind") == "tool_call_summary" for entry in transcript["entries"]))
        self.assertTrue(any(entry.get("entry_kind") == "tool_result_summary" for entry in transcript["entries"]))
        self.assertTrue(list(transcript["reasoning_artifacts"]["drop_records"]))
        for forbidden in (
            "sk-not-a-real-secret-123456",
            "not-a-real-token-123456",
            "opaque-private-chain",
            "resp-private",
            "untrusted_provider_blob",
            "must-not-survive",
        ):
            self.assertNotIn(forbidden, transcript_text)


if __name__ == "__main__":
    unittest.main()
