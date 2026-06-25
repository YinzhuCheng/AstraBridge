from __future__ import annotations

import io
import json
import struct
import sys
import tempfile
import unittest
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from astrabridge_sidecar.capabilities import QwenSpeechSynthesizeAdapter


def _demo_wav_bytes() -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(8000)
        wav_file.writeframes(struct.pack("<hhhh", 0, 4000, -4000, 0))
    return buffer.getvalue()


class _FakeStreamingResponse:
    def __init__(self, lines: list[str]) -> None:
        self._lines = lines

    def raise_for_status(self) -> None:
        return None

    def iter_lines(self):  # type: ignore[no-untyped-def]
        for line in self._lines:
            yield line.encode("utf-8")


class SpeechSynthesizeAdapterTests(unittest.TestCase):
    def test_build_request_uses_streaming_text_and_audio_modalities(self) -> None:
        adapter = QwenSpeechSynthesizeAdapter(api_key="sk-test")

        request_body = adapter.build_request(
            {
                "text": "Please say hello.",
                "voice": "Tina",
                "audio_format": "wav",
                "instructions": "Speak slowly.",
            }
        )

        self.assertEqual(request_body["model"], "qwen3.5-omni-plus")
        self.assertEqual(request_body["stream"], True)
        self.assertEqual(request_body["stream_options"], {"include_usage": True})
        self.assertEqual(request_body["modalities"], ["text", "audio"])
        self.assertEqual(request_body["audio"], {"voice": "Tina", "format": "wav"})
        self.assertEqual(request_body["messages"][0], {"role": "system", "content": "Speak slowly."})
        self.assertEqual(request_body["messages"][1], {"role": "user", "content": "Please say hello."})

    def test_synthesize_assembles_sse_audio_and_persists_secret_free_artifacts(self) -> None:
        wav_bytes = _demo_wav_bytes()
        wav_b64 = __import__("base64").b64encode(wav_bytes).decode("ascii")
        captured: dict[str, object] = {}

        def fake_post(url: str, *, headers: dict[str, str], json: dict[str, object], timeout: int, stream: bool) -> _FakeStreamingResponse:
            captured["url"] = url
            captured["headers"] = headers
            captured["json"] = json
            captured["timeout"] = timeout
            captured["stream"] = stream
            return _FakeStreamingResponse(
                [
                    'data: {"choices":[{"delta":{"content":"","role":"assistant"},"index":0,"finish_reason":null}],"model":"qwen3.5-omni-plus","id":"chatcmpl-test","usage":null}',
                    'data: {"choices":[{"delta":{"content":"Astra"},"index":0,"finish_reason":null}],"model":"qwen3.5-omni-plus","id":"chatcmpl-test","usage":null}',
                    'data: {"choices":[{"delta":{"content":"Bridge passed."},"index":0,"finish_reason":null}],"model":"qwen3.5-omni-plus","id":"chatcmpl-test","usage":null}',
                    f'data: {json_module({"choices":[{"delta":{"audio":{"data":wav_b64}},"index":0,"finish_reason":None}],"model":"qwen3.5-omni-plus","id":"chatcmpl-test","usage":None})}',
                    'data: {"choices":[{"delta":{"content":""},"index":0,"finish_reason":"stop"}],"model":"qwen3.5-omni-plus","id":"chatcmpl-test","usage":null}',
                    'data: {"choices":[],"model":"qwen3.5-omni-plus","id":"chatcmpl-test","usage":{"prompt_tokens":25,"completion_tokens":52,"total_tokens":77,"completion_tokens_details":{"audio_tokens":39,"text_tokens":13},"prompt_tokens_details":{"text_tokens":25}}}',
                    "data: [DONE]",
                ]
            )

        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            adapter = QwenSpeechSynthesizeAdapter(api_key="sk-test", post_fn=fake_post)
            result = adapter.synthesize(
                {
                    "text": "Please say in Chinese: AstraBridge capability runtime smoke test passed.",
                    "voice": "Tina",
                    "audio_format": "wav",
                    "workspace_root": str(workspace),
                    "timeout_sec": 91,
                }
            )

            self.assertEqual(captured["url"], "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions")
            self.assertEqual(captured["timeout"], 91)
            self.assertEqual(captured["stream"], True)
            self.assertEqual(captured["headers"]["Authorization"], "Bearer sk-test")
            self.assertEqual(result["capability_id"], "speech.synthesize")
            self.assertEqual(result["provider_id"], "qwen")
            self.assertEqual(result["model"], "qwen3.5-omni-plus")
            self.assertEqual(result["text"], "AstraBridge passed.")
            self.assertEqual(result["mime_type"], "audio/wav")
            self.assertEqual(result["finish_reason"], "stop")
            self.assertAlmostEqual(result["duration_sec"], 0.0005, places=6)
            self.assertEqual(result["usage"]["completion_tokens_details"]["audio_tokens"], 39)
            self.assertEqual(len(result["artifact_refs"]), 5)

            artifact_dir = Path(result["artifact_dir"])
            request_payload = json.loads((artifact_dir / "request.json").read_text(encoding="utf-8"))
            sse_text = (artifact_dir / "response.sse.txt").read_text(encoding="utf-8")
            transcript_text = (artifact_dir / "transcript.txt").read_text(encoding="utf-8")
            audio_bytes = (artifact_dir / "output.wav").read_bytes()
            summary_payload = json.loads((artifact_dir / "summary.json").read_text(encoding="utf-8"))

            self.assertNotIn("Authorization", json.dumps(request_payload))
            self.assertIn('"modalities": [', json.dumps(request_payload))
            self.assertIn("delta", sse_text)
            self.assertEqual(transcript_text, "AstraBridge passed.")
            self.assertEqual(audio_bytes, wav_bytes)
            self.assertEqual(summary_payload["mime_type"], "audio/wav")


def json_module(payload: dict[str, object]) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


if __name__ == "__main__":
    unittest.main()
