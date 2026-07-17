from __future__ import annotations

import base64
import json
import os
import struct
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from astrabridge_sidecar.capabilities import KimiVisionAnalyzeAdapter, QwenVisionAnalyzeAdapter


_TINY_PNG_BASE64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+y3ioAAAAASUVORK5CYII="
)


def _png_chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)


def _solid_png_base64(width: int = 64, height: int = 64) -> str:
    raw = b"".join(b"\x00" + (b"\xf0\x3a\x2f" * width) for _ in range(height))
    png = b"\x89PNG\r\n\x1a\n" + _png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
    png += _png_chunk(b"IDAT", zlib.compress(raw))
    png += _png_chunk(b"IEND", b"")
    return base64.b64encode(png).decode("ascii")


_RED_SQUARE_PNG_BASE64 = _solid_png_base64()


class _FakeResponse:
    def __init__(self, body: dict[str, object]) -> None:
        self._body = body

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, object]:
        return self._body


class VisionAnalyzeAdapterTests(unittest.TestCase):
    def test_qwen_build_request_uses_image_parts_plus_trailing_text_prompt(self) -> None:
        adapter = QwenVisionAnalyzeAdapter(api_key="sk-test")

        request_body = adapter.build_request(
            {
                "model": "qwen3.7-plus",
                "prompt": "Read the large title and subtitle in this image. Keep the answer concise.",
                "detail": "high",
                "image_inputs": [{"mime_type": "image/png", "data": _RED_SQUARE_PNG_BASE64}],
                "max_output_tokens": 256,
            }
        )

        self.assertEqual(request_body["model"], "qwen3.7-plus")
        self.assertEqual(request_body["max_tokens"], 256)
        content = request_body["messages"][0]["content"]
        self.assertEqual(content[0]["type"], "image_url")
        self.assertTrue(content[0]["image_url"]["url"].startswith("data:image/png;base64,"))
        self.assertEqual(content[0]["image_url"]["detail"], "high")
        self.assertEqual(content[1], {"type": "text", "text": "Read the large title and subtitle in this image. Keep the answer concise."})

    def test_qwen_build_request_accepts_public_https_image_url(self) -> None:
        adapter = QwenVisionAnalyzeAdapter(api_key="sk-test")

        request_body = adapter.build_request(
            {
                "model": "qwen3-vl-plus",
                "prompt": "Name the dominant color.",
                "image_inputs": [{"url": "https://example.com/fixtures/red-square.png"}],
            }
        )

        content = request_body["messages"][0]["content"]
        self.assertEqual(request_body["model"], "qwen3-vl-plus")
        self.assertEqual(content[0]["type"], "image_url")
        self.assertEqual(content[0]["image_url"]["url"], "https://example.com/fixtures/red-square.png")
        self.assertEqual(content[1], {"type": "text", "text": "Name the dominant color."})

    def test_qwen_build_request_rejects_non_fetchable_image_url_with_redacted_error(self) -> None:
        adapter = QwenVisionAnalyzeAdapter(api_key="sk-test")

        with self.assertRaisesRegex(ValueError, "public https image URLs or inline data:image payloads") as captured:
            adapter.build_request(
                {
                    "prompt": "Name the dominant color.",
                    "image_inputs": [{"url": "https://127.0.0.1/fixtures/red-square.png?sig=secret-token"}],
                }
            )
        self.assertNotIn("127.0.0.1", str(captured.exception))
        self.assertNotIn("secret-token", str(captured.exception))

    def test_qwen_build_request_rejects_unsupported_vision_model(self) -> None:
        adapter = QwenVisionAnalyzeAdapter(api_key="sk-test")

        with self.assertRaisesRegex(ValueError, "does not support model `qwen3-coder-plus`"):
            adapter.build_request(
                {
                    "model": "qwen3-coder-plus",
                    "prompt": "Name the dominant color.",
                    "image_inputs": [{"mime_type": "image/png", "data": _RED_SQUARE_PNG_BASE64}],
                }
            )

    def test_qwen_build_request_rejects_too_small_inline_image(self) -> None:
        adapter = QwenVisionAnalyzeAdapter(api_key="sk-test")

        with self.assertRaisesRegex(ValueError, "greater than 10px"):
            adapter.build_request(
                {
                    "model": "qwen3-vl-plus",
                    "prompt": "Name the dominant color.",
                    "image_inputs": [{"mime_type": "image/png", "data": _TINY_PNG_BASE64}],
                }
            )

    def test_qwen_analyze_normalizes_reasoning_and_persists_secret_free_artifacts(self) -> None:
        captured: dict[str, object] = {}

        def fake_post(url: str, *, headers: dict[str, str], json: dict[str, object], timeout: int) -> _FakeResponse:
            captured["url"] = url
            captured["headers"] = headers
            captured["json"] = json
            captured["timeout"] = timeout
            return _FakeResponse(
                {
                    "model": "qwen3.7-plus",
                    "id": "chatcmpl-test",
                    "choices": [
                        {
                            "message": {
                                "content": "Based on the image:\n\n*   **Title:** AstraBridge\n*   **Subtitle:** vision smoke test",
                                "reasoning_content": "Title: AstraBridge. Subtitle: vision smoke test.",
                                "role": "assistant",
                            },
                            "index": 0,
                            "finish_reason": "stop",
                        }
                    ],
                    "created": 1782305154,
                    "object": "chat.completion",
                    "usage": {
                        "total_tokens": 2268,
                        "completion_tokens": 1273,
                        "prompt_tokens": 995,
                        "completion_tokens_details": {"reasoning_tokens": 1247, "text_tokens": 26},
                        "prompt_tokens_details": {"image_tokens": 970, "cached_tokens": 0, "text_tokens": 25},
                    },
                }
            )

        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            adapter = QwenVisionAnalyzeAdapter(api_key="sk-test", post_fn=fake_post)
            result = adapter.analyze(
                {
                    "prompt": "Read the large title and subtitle in this image. Keep the answer concise.",
                    "detail": "high",
                    "image_inputs": [{"mime_type": "image/png", "data": _RED_SQUARE_PNG_BASE64}],
                    "workspace_root": str(workspace),
                    "timeout_sec": 77,
                }
            )

            self.assertEqual(captured["url"], "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions")
            self.assertEqual(captured["timeout"], 77)
            self.assertEqual(captured["headers"]["Authorization"], "Bearer sk-test")
            self.assertEqual(result["capability_id"], "vision.analyze")
            self.assertEqual(result["provider_id"], "qwen")
            self.assertEqual(result["model"], "qwen3.7-plus")
            self.assertIn("AstraBridge", result["text"])
            self.assertEqual(result["finish_reason"], "stop")
            self.assertEqual(result["annotations"][0]["type"], "reasoning_content")
            self.assertEqual(result["usage"]["prompt_tokens_details"]["image_tokens"], 970)
            self.assertEqual(result["detail"], "high")
            self.assertTrue(result["request_detail_sent"])
            self.assertEqual(len(result["artifact_refs"]), 4)

            artifact_dir = Path(result["artifact_dir"])
            self.assertEqual(len(result["protocol_artifact_refs"]), 1)
            self.assertEqual(result["protocol_artifact_refs"][0]["artifact_uri"], f"workspace://.astrabridge/capabilities/vision_analyze/{artifact_dir.name}/text.txt")
            self.assertEqual(len(result["diagnostic_refs"]), 3)
            self.assertEqual(result["capability_output"]["status"], "ok")
            self.assertEqual(result["content_parts"][0]["kind"], "text")
            self.assertEqual(result["content_parts"][1]["kind"], "document")
            request_payload = json.loads((artifact_dir / "request.json").read_text(encoding="utf-8"))
            response_payload = json.loads((artifact_dir / "response.json").read_text(encoding="utf-8"))
            text_value = (artifact_dir / "text.txt").read_text(encoding="utf-8")
            summary_payload = json.loads((artifact_dir / "summary.json").read_text(encoding="utf-8"))

            self.assertNotIn("Authorization", json.dumps(request_payload))
            self.assertEqual(request_payload["json"]["messages"][0]["content"][0]["type"], "image_url")
            self.assertEqual(request_payload["json"]["messages"][0]["content"][0]["image_url"]["detail"], "high")
            self.assertEqual(response_payload["body"]["model"], "qwen3.7-plus")
            self.assertIn("AstraBridge", text_value)
            self.assertEqual(summary_payload["provider_id"], "qwen")

    def test_kimi_build_request_can_encode_local_image_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            image_path = Path(tmpdir) / "vision.png"
            image_path.write_bytes(base64.b64decode(_TINY_PNG_BASE64))
            adapter = KimiVisionAnalyzeAdapter(api_key="sk-test")

            request_body = adapter.build_request(
                {
                    "prompt": "What is the title?",
                    "image_inputs": [{"path": str(image_path), "mime_type": "image/png"}],
                }
            )

            content = request_body["messages"][0]["content"]
            self.assertEqual(request_body["model"], "kimi-k2.6")
            self.assertTrue(content[0]["image_url"]["url"].startswith("data:image/png;base64,"))
            self.assertEqual(content[1]["text"], "What is the title?")

    def test_kimi_build_request_rejects_remote_image_url(self) -> None:
        adapter = KimiVisionAnalyzeAdapter(api_key="sk-test")

        with self.assertRaisesRegex(ValueError, "inline/base64 image inputs or local file paths") as captured:
            adapter.build_request(
                {
                    "model": "kimi-k2.6",
                    "prompt": "What is the title?",
                    "image_inputs": [{"url": "https://example.com/vision.png?sig=secret-token"}],
                }
            )
        self.assertNotIn("example.com", str(captured.exception))
        self.assertNotIn("secret-token", str(captured.exception))

    def test_kimi_analyze_normalizes_smoke_response(self) -> None:
        def fake_post(url: str, *, headers: dict[str, str], json: dict[str, object], timeout: int) -> _FakeResponse:
            return _FakeResponse(
                {
                    "id": "chatcmpl-kimi-test",
                    "object": "chat.completion",
                    "created": 1782305183,
                    "model": "kimi-k2.6",
                    "choices": [
                        {
                            "index": 0,
                            "message": {
                                "role": "assistant",
                                "content": "**Title:** AstraBridge  \n**Subtitle:** vision smoke test",
                                "reasoning_content": "The user wants me to read the large title and subtitle from the image.",
                            },
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": {
                        "prompt_tokens": 1276,
                        "completion_tokens": 119,
                        "total_tokens": 1395,
                        "cached_tokens": 6,
                        "prompt_tokens_details": {"cached_tokens": 6},
                    },
                }
            )

        adapter = KimiVisionAnalyzeAdapter(api_key="sk-test", post_fn=fake_post)
        result = adapter.analyze(
            {
                "prompt": "Read the large title and subtitle in this image. Keep the answer concise.",
                "image_inputs": [{"mime_type": "image/png", "data": _TINY_PNG_BASE64}],
            }
        )

        self.assertEqual(result["provider_id"], "kimi")
        self.assertEqual(result["model"], "kimi-k2.6")
        self.assertIn("AstraBridge", result["text"])
        self.assertEqual(result["finish_reason"], "stop")
        self.assertEqual(result["annotations"][0]["type"], "reasoning_content")
        self.assertEqual(result["usage"]["total_tokens"], 1395)

    def test_kimi_analyze_accepts_kimi_api_key_env(self) -> None:
        captured: dict[str, object] = {}

        def fake_post(url: str, *, headers: dict[str, str], json: dict[str, object], timeout: int) -> _FakeResponse:
            captured["headers"] = headers
            return _FakeResponse(
                {
                    "id": "chatcmpl-kimi-env",
                    "object": "chat.completion",
                    "created": 1782305183,
                    "model": "kimi-k2.6",
                    "choices": [{"message": {"role": "assistant", "content": "red square"}, "finish_reason": "stop"}],
                    "usage": {"total_tokens": 9},
                }
            )

        original = os.environ.get("KIMI_API_KEY")
        try:
            os.environ["KIMI_API_KEY"] = "unitfake"
            result = KimiVisionAnalyzeAdapter(post_fn=fake_post).analyze(
                {
                    "prompt": "Describe the image.",
                    "image_inputs": [{"mime_type": "image/png", "data": _TINY_PNG_BASE64}],
                }
            )
        finally:
            if original is None:
                os.environ.pop("KIMI_API_KEY", None)
            else:
                os.environ["KIMI_API_KEY"] = original

        self.assertEqual(captured["headers"]["Authorization"], "Bearer unitfake")
        self.assertEqual(result["provider_id"], "kimi")
        self.assertEqual(result["text"], "red square")


if __name__ == "__main__":
    unittest.main()
