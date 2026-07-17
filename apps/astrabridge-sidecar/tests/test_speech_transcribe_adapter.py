from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from astrabridge_sidecar.capabilities import QwenSpeechTranscribeAdapter


class _FakeResponse:
    def __init__(self, body: dict[str, object]) -> None:
        self._body = body

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, object]:
        return self._body


class SpeechTranscribeAdapterTests(unittest.TestCase):
    def test_build_request_uses_audio_only_content_and_out_of_band_asr_options(self) -> None:
        adapter = QwenSpeechTranscribeAdapter(api_key="sk-test")

        request_body = adapter.build_request(
            {
                "model": "qwen3-asr-flash",
                "audio_inputs": [{"mime_type": "audio/wav", "data": "UklGRg=="}],
                "language_hint": "en",
                "enable_itn": False,
                "prompt": "please transcribe carefully",
            }
        )

        self.assertEqual(request_body["model"], "qwen3-asr-flash")
        self.assertEqual(request_body["asr_options"], {"language": "en", "enable_itn": False})
        message = request_body["messages"][0]
        self.assertEqual(message["role"], "user")
        self.assertEqual(len(message["content"]), 1)
        self.assertEqual(message["content"][0]["type"], "input_audio")
        self.assertTrue(message["content"][0]["input_audio"]["data"].startswith("data:audio/wav;base64,"))
        self.assertNotIn("text", json.dumps(request_body["messages"]))

    def test_transcribe_normalizes_response_and_persists_secret_free_artifacts(self) -> None:
        captured: dict[str, object] = {}

        def fake_post(url: str, *, headers: dict[str, str], json: dict[str, object], timeout: int) -> _FakeResponse:
            captured["url"] = url
            captured["headers"] = headers
            captured["json"] = json
            captured["timeout"] = timeout
            return _FakeResponse(
                {
                    "choices": [
                        {
                            "finish_reason": "stop",
                            "index": 0,
                            "message": {
                                "annotations": [{"emotion": "neutral", "language": "en", "type": "audio_info"}],
                                "content": "This is an astro bridge speech recognition smoke test.",
                                "role": "assistant",
                            },
                        }
                    ],
                    "created": 1782305226,
                    "id": "chatcmpl-test",
                    "model": "qwen3-asr-flash",
                    "object": "chat.completion",
                    "usage": {
                        "completion_tokens": 17,
                        "completion_tokens_details": {"text_tokens": 17},
                        "prompt_tokens": 114,
                        "prompt_tokens_details": {"audio_tokens": 111, "text_tokens": 3},
                        "seconds": 4,
                        "total_tokens": 131,
                    },
                }
            )

        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            adapter = QwenSpeechTranscribeAdapter(api_key="sk-test", post_fn=fake_post)
            result = adapter.transcribe(
                {
                    "audio_inputs": [{"mime_type": "audio/wav", "data": "UklGRg=="}],
                    "language_hint": "en",
                    "prompt": "caller prompt should be ignored upstream",
                    "workspace_root": str(workspace),
                    "timeout_sec": 91,
                }
            )

            self.assertEqual(captured["url"], "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions")
            self.assertEqual(captured["timeout"], 91)
            self.assertEqual(captured["headers"]["Authorization"], "Bearer sk-test")
            self.assertEqual(result["capability_id"], "speech.transcribe")
            self.assertEqual(result["provider_id"], "qwen")
            self.assertEqual(result["model"], "qwen3-asr-flash")
            self.assertEqual(result["text"], "This is an astro bridge speech recognition smoke test.")
            self.assertEqual(result["language"], "en")
            self.assertTrue(result["audio_only_content"])
            self.assertTrue(result["prompt_ignored"])
            self.assertEqual(len(result["artifact_refs"]), 4)
            self.assertEqual(len(result["protocol_artifact_refs"]), 1)
            self.assertEqual(len(result["diagnostic_refs"]), 3)
            self.assertEqual(result["capability_output"]["status"], "ok")
            self.assertEqual(result["content_parts"][0]["kind"], "text")
            self.assertEqual(result["content_parts"][1]["kind"], "document")

            artifact_dir = Path(result["artifact_dir"])
            self.assertEqual(
                result["protocol_artifact_refs"][0]["artifact_uri"],
                f"workspace://.astrabridge/capabilities/speech_transcribe/{artifact_dir.name}/transcript.txt",
            )
            request_payload = json.loads((artifact_dir / "request.json").read_text(encoding="utf-8"))
            response_payload = json.loads((artifact_dir / "response.json").read_text(encoding="utf-8"))
            transcript_text = (artifact_dir / "transcript.txt").read_text(encoding="utf-8")
            summary_payload = json.loads((artifact_dir / "summary.json").read_text(encoding="utf-8"))

            self.assertNotIn("Authorization", json.dumps(request_payload))
            self.assertEqual(request_payload["json"]["messages"][0]["content"][0]["type"], "input_audio")
            self.assertEqual(response_payload["body"]["model"], "qwen3-asr-flash")
            self.assertEqual(transcript_text, "This is an astro bridge speech recognition smoke test.")
            self.assertEqual(summary_payload["prompt_ignored"], True)

    def test_build_request_can_load_audio_from_workspace_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            audio_path = Path(tmpdir) / "input.wav"
            audio_path.write_bytes(b"RIFFdemo")
            adapter = QwenSpeechTranscribeAdapter(api_key="sk-test")

            request_body = adapter.build_request({"audio_inputs": [{"path": str(audio_path), "mime_type": "audio/wav"}]})

            data_uri = request_body["messages"][0]["content"][0]["input_audio"]["data"]
            self.assertTrue(data_uri.startswith("data:audio/wav;base64,"))


if __name__ == "__main__":
    unittest.main()
