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


class _FakeDownloadResponse:
    def __init__(self, content: bytes) -> None:
        self.content = content

    def raise_for_status(self) -> None:
        return None


class SpeechSynthesizeAdapterTests(unittest.TestCase):
    def test_build_request_uses_dashscope_tts_input_shape(self) -> None:
        adapter = QwenSpeechSynthesizeAdapter(api_key="sk-test")

        request_body, profile = adapter.build_request(
            {
                "text": "Please say hello.",
                "voice": "Tina",
                "audio_format": "wav",
                "instructions": "Speak slowly.",
                "language_type": "Zhichun",
            }
        )

        self.assertEqual(profile["family_id"], "qwen_tts")
        self.assertEqual(request_body["model"], "qwen3-tts-instruct-flash")
        self.assertEqual(request_body["stream"], True)
        self.assertEqual(
            request_body["input"],
            {
                "text": "Please say hello.",
                "voice": "Tina",
                "format": "wav",
                "language_type": "Zhichun",
                "instructions": "Speak slowly.",
            },
        )
        self.assertNotIn("messages", request_body)
        self.assertNotIn("modalities", request_body)
        self.assertNotIn("audio", request_body)

    def test_build_request_normalizes_cosyvoice_http_shape(self) -> None:
        adapter = QwenSpeechSynthesizeAdapter(api_key="sk-test")

        request_body, profile = adapter.build_request(
            {
                "model": "cosyvoice-v3-plus",
                "text": "Please say hello.",
                "voice": "longxiaochun_v2",
                "audio_format": "mp3",
                "instructions": "Speak with calm pacing.",
                "sample_rate": 24000,
                "language_hint": "zh",
            }
        )

        self.assertEqual(profile["family_id"], "cosyvoice")
        self.assertEqual(request_body["model"], "cosyvoice-v3-plus")
        self.assertEqual(request_body["parameters"], {"streaming": True})
        self.assertEqual(
            request_body["input"],
            {
                "text": "Please say hello.",
                "voice": "longxiaochun_v2",
                "format": "mp3",
                "sample_rate": 24000,
                "language_hints": ["zh"],
                "instruction": "Speak with calm pacing.",
            },
        )

    def test_build_request_requires_explicit_voice_for_cosyvoice(self) -> None:
        adapter = QwenSpeechSynthesizeAdapter(api_key="sk-test")

        with self.assertRaisesRegex(ValueError, "requires an explicit voice"):
            adapter.build_request(
                {
                    "model": "cosyvoice-v3.5-plus",
                    "text": "Please say hello.",
                }
            )

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
                    'data: {"request_id":"req-test","output":{"text":"Astra","finish_reason":null},"usage":null}',
                    'data: {"request_id":"req-test","output":{"text":"Bridge passed.","audio":{"data":"' + wav_b64 + '"},"finish_reason":"stop"},"usage":{"input_tokens":25,"output_tokens":52,"total_tokens":77}}',
                    "data: [DONE]",
                ]
            )

        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            adapter = QwenSpeechSynthesizeAdapter(
                api_key="sk-test",
                base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
                post_fn=fake_post,
            )
            result = adapter.synthesize(
                {
                    "text": "Please say in Chinese: AstraBridge capability runtime smoke test passed.",
                    "voice": "Tina",
                    "audio_format": "wav",
                    "workspace_root": str(workspace),
                    "timeout_sec": 91,
                }
            )

            self.assertEqual(captured["url"], "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation")
            self.assertEqual(captured["timeout"], 91)
            self.assertEqual(captured["stream"], True)
            self.assertEqual(captured["headers"]["Authorization"], "Bearer sk-test")
            self.assertEqual(captured["headers"]["X-DashScope-SSE"], "enable")
            self.assertEqual(result["capability_id"], "speech.synthesize")
            self.assertEqual(result["provider_id"], "qwen")
            self.assertEqual(result["model"], "qwen3-tts-flash")
            self.assertEqual(result["text"], "AstraBridge passed.")
            self.assertEqual(result["mime_type"], "audio/wav")
            self.assertEqual(result["finish_reason"], "stop")
            self.assertAlmostEqual(result["duration_sec"], 0.0005, places=6)
            self.assertEqual(result["usage"]["total_tokens"], 77)
            self.assertEqual(len(result["artifact_refs"]), 5)
            self.assertEqual(len(result["protocol_artifact_refs"]), 2)
            self.assertEqual(len(result["diagnostic_refs"]), 3)
            self.assertEqual(result["capability_output"]["status"], "ok")
            self.assertTrue(result["audio_bytes_base64_present"])
            self.assertNotIn("audio_bytes_base64", result)
            self.assertEqual(result["tts_family"], "qwen_tts")

            artifact_dir = Path(result["artifact_dir"])
            artifact_uris = {item["artifact_uri"] for item in result["protocol_artifact_refs"]}
            self.assertIn(
                f"workspace://.astrabridge/capabilities/speech_synthesize/{artifact_dir.name}/output.wav",
                artifact_uris,
            )
            self.assertIn(
                f"workspace://.astrabridge/capabilities/speech_synthesize/{artifact_dir.name}/transcript.txt",
                artifact_uris,
            )
            request_payload = json.loads((artifact_dir / "request.json").read_text(encoding="utf-8"))
            sse_text = (artifact_dir / "response.sse.txt").read_text(encoding="utf-8")
            transcript_text = (artifact_dir / "transcript.txt").read_text(encoding="utf-8")
            audio_bytes = (artifact_dir / "output.wav").read_bytes()
            summary_payload = json.loads((artifact_dir / "summary.json").read_text(encoding="utf-8"))

            self.assertNotIn("Authorization", json.dumps(request_payload))
            self.assertIn('"input": {', json.dumps(request_payload))
            self.assertIn('"output"', sse_text)
            self.assertEqual(transcript_text, "AstraBridge passed.")
            self.assertEqual(audio_bytes, wav_bytes)
            self.assertEqual(summary_payload["mime_type"], "audio/wav")

    def test_synthesize_downloads_audio_from_output_url_when_inline_audio_is_empty(self) -> None:
        wav_bytes = _demo_wav_bytes()
        captured: dict[str, object] = {}

        def fake_post(url: str, *, headers: dict[str, str], json: dict[str, object], timeout: int, stream: bool) -> _FakeStreamingResponse:
            captured["url"] = url
            return _FakeStreamingResponse(
                [
                    'data: {"request_id":"req-url","output":{"audio":{"url":"https://example.com/audio.wav"},"finish_reason":"stop"}}',
                    "data: [DONE]",
                ]
            )

        def fake_get(url: str, *, timeout: int) -> _FakeDownloadResponse:
            captured["download_url"] = url
            captured["download_timeout"] = timeout
            return _FakeDownloadResponse(wav_bytes)

        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            adapter = QwenSpeechSynthesizeAdapter(
                api_key="sk-test",
                base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
                post_fn=fake_post,
                get_fn=fake_get,
            )
            result = adapter.synthesize(
                {
                    "text": "Please say hello.",
                    "voice": "Tina",
                    "audio_format": "wav",
                    "workspace_root": str(workspace),
                    "timeout_sec": 45,
                }
            )

            self.assertEqual(captured["download_url"], "https://example.com/audio.wav")
            self.assertEqual(captured["download_timeout"], 45)
            artifact_dir = Path(result["artifact_dir"])
            self.assertEqual((artifact_dir / "output.wav").read_bytes(), wav_bytes)

    def test_synthesize_uses_latest_output_audio_snapshot_instead_of_concatenating(self) -> None:
        first_wav = _demo_wav_bytes()
        second_wav = first_wav + first_wav
        first_b64 = __import__("base64").b64encode(first_wav).decode("ascii")
        second_b64 = __import__("base64").b64encode(second_wav).decode("ascii")

        def fake_post(url: str, *, headers: dict[str, str], json: dict[str, object], timeout: int, stream: bool) -> _FakeStreamingResponse:
            return _FakeStreamingResponse(
                [
                    'data: {"request_id":"req-snapshot","output":{"audio":{"data":"' + first_b64 + '"}}}',
                    'data: {"request_id":"req-snapshot","output":{"audio":{"data":"' + second_b64 + '"},"finish_reason":"stop"}}',
                    "data: [DONE]",
                ]
            )

        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            adapter = QwenSpeechSynthesizeAdapter(
                api_key="sk-test",
                post_fn=fake_post,
            )
            result = adapter.synthesize(
                {
                    "text": "Please say hello.",
                    "voice": "Cherry",
                    "audio_format": "wav",
                    "workspace_root": str(workspace),
                    "timeout_sec": 45,
                }
            )

            artifact_dir = Path(result["artifact_dir"])
            self.assertEqual((artifact_dir / "output.wav").read_bytes(), second_wav)

    def test_cosyvoice_stream_prefers_final_audio_url_for_non_pcm_artifacts(self) -> None:
        chunk_bytes = b"pcm-chunk-1"
        chunk_b64 = __import__("base64").b64encode(chunk_bytes).decode("ascii")
        wav_bytes = _demo_wav_bytes()
        captured: dict[str, object] = {}

        def fake_post(url: str, *, headers: dict[str, str], json: dict[str, object], timeout: int, stream: bool) -> _FakeStreamingResponse:
            captured["url"] = url
            captured["json"] = json
            return _FakeStreamingResponse(
                [
                    'data: {"request_id":"req-cosy","type":"sentence-begin","output":{"original_text":"CosyVoice hello"}}',
                    'data: {"request_id":"req-cosy","type":"sentence-synthesis","output":{"audio":{"data":"' + chunk_b64 + '","url":"https://example.com/cosyvoice.wav","format":"pcm"}}}',
                    'data: {"request_id":"req-cosy","type":"completed","output":{"finish_reason":"stop"}}',
                    "data: [DONE]",
                ]
            )

        def fake_get(url: str, *, timeout: int) -> _FakeDownloadResponse:
            captured["download_url"] = url
            captured["download_timeout"] = timeout
            return _FakeDownloadResponse(wav_bytes)

        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            adapter = QwenSpeechSynthesizeAdapter(
                api_key="sk-test",
                post_fn=fake_post,
                get_fn=fake_get,
            )
            result = adapter.synthesize(
                {
                    "model": "cosyvoice-v3-plus",
                    "text": "Please say hello.",
                    "voice": "longxiaochun_v2",
                    "audio_format": "wav",
                    "workspace_root": str(workspace),
                    "timeout_sec": 61,
                }
            )

            self.assertEqual(captured["url"], "https://dashscope.aliyuncs.com/api/v1/services/audio/tts/SpeechSynthesizer")
            self.assertEqual(captured["download_url"], "https://example.com/cosyvoice.wav")
            self.assertEqual(captured["download_timeout"], 61)
            self.assertEqual(result["provider_id"], "qwen")
            self.assertEqual(result["model"], "cosyvoice-v3-plus")
            self.assertEqual(result["tts_family"], "cosyvoice")
            self.assertEqual(result["tts_protocol_profile"], "dashscope_speech_synthesizer_sse")
            self.assertEqual(result["text"], "CosyVoice hello")
            self.assertEqual(result["audio_format"], "wav")
            self.assertIn("sentence-begin", result["stream_event_types"])
            self.assertIn("sentence-synthesis", result["stream_event_types"])

            artifact_dir = Path(result["artifact_dir"])
            self.assertEqual((artifact_dir / "output.wav").read_bytes(), wav_bytes)
            summary_payload = json.loads((artifact_dir / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary_payload["tts_family"], "cosyvoice")


def json_module(payload: dict[str, object]) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


if __name__ == "__main__":
    unittest.main()
