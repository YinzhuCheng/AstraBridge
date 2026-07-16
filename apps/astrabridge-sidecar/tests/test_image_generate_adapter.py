from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from astrabridge_sidecar.capabilities import DashScopeImageGenerateAdapter, YunwuImageGenerateAdapter
from astrabridge_sidecar.yunwu_image_service import YunwuImageService


class _FakeYunwuService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    def generate(self, **kwargs: object) -> dict[str, object]:
        self.calls.append(("generate", dict(kwargs)))
        return {
            "created": 111,
            "requested_n": 1,
            "actual_n": 1,
            "count_mismatch": False,
            "asset_manifest_path": "D:/workspace/.astrabridge/assets/generated/asset_manifest.json",
            "persisted_assets": [
                {
                    "asset_id": "yunwu-asset-1",
                    "provider": "yunwu",
                    "tool": "yunwu_image_generate",
                    "model": "gpt-image-2",
                    "local_path": "D:/workspace/.astrabridge/assets/generated/yunwu-asset-1.png",
                    "source_url": "https://example.test/generated.png",
                    "result_index": 0,
                    "has_alpha": True,
                    "transparency_status": "passed",
                    "actual_width": 1024,
                    "actual_height": 1024,
                    "actual_format": "png",
                    "validation_warnings": [],
                }
            ],
            "data": [{"revised_prompt": "revised prompt from provider"}],
        }

    def edit(self, **kwargs: object) -> dict[str, object]:
        self.calls.append(("edit", dict(kwargs)))
        return {
            "created": 222,
            "requested_n": 1,
            "actual_n": 1,
            "count_mismatch": False,
            "asset_manifest_path": "D:/workspace/.astrabridge/assets/generated/asset_manifest.json",
            "persisted_assets": [
                {
                    "asset_id": "yunwu-asset-edit-1",
                    "provider": "yunwu",
                    "tool": "yunwu_image_edit",
                    "model": "gpt-image-2",
                    "local_path": "D:/workspace/.astrabridge/assets/generated/yunwu-asset-edit-1.png",
                    "source_url": "",
                    "result_index": 0,
                    "has_alpha": False,
                    "transparency_status": "not_requested",
                    "actual_width": 1024,
                    "actual_height": 1024,
                    "actual_format": "png",
                    "validation_warnings": [],
                }
            ],
            "data": [{"revised_prompt": ""}],
        }

    def transparent_asset(self, **kwargs: object) -> dict[str, object]:
        self.calls.append(("transparent_asset", dict(kwargs)))
        return {
            "created": 333,
            "requested_n": 1,
            "actual_n": 1,
            "count_mismatch": False,
            "asset_manifest_path": "D:/workspace/.astrabridge/assets/generated/asset_manifest.json",
            "persisted_assets": [
                {
                    "asset_id": "yunwu-asset-transparent-1",
                    "provider": "yunwu",
                    "tool": "yunwu_image_edit",
                    "model": "gpt-image-2",
                    "local_path": "D:/workspace/.astrabridge/assets/generated/yunwu-asset-transparent-1.png",
                    "source_url": "",
                    "result_index": 0,
                    "has_alpha": True,
                    "transparency_status": "passed",
                    "actual_width": 1024,
                    "actual_height": 1024,
                    "actual_format": "png",
                    "validation_warnings": [],
                    "revised_prompt": "transparent revised prompt",
                }
            ],
            "data": [{"revised_prompt": "transparent revised prompt"}],
        }


class ImageGenerateAdapterTests(unittest.TestCase):
    def test_capability_generate_normalizes_existing_persisted_assets(self) -> None:
        adapter = YunwuImageGenerateAdapter(_FakeYunwuService())  # type: ignore[arg-type]

        result = adapter.generate({"prompt": "draw a blue crystal", "workspace_root": "D:/workspace"})

        self.assertEqual(result["capability_id"], "image.generate")
        self.assertEqual(result["provider_id"], "yunwu")
        self.assertEqual(result["model"], "gpt-image-2")
        self.assertEqual(result["operation"], "generate")
        self.assertEqual(result["requested_n"], 1)
        self.assertEqual(result["actual_n"], 1)
        self.assertEqual(result["artifact_refs"][0]["asset_id"], "yunwu-asset-1")
        self.assertEqual(result["artifact_refs"][0]["local_path"], "D:/workspace/.astrabridge/assets/generated/yunwu-asset-1.png")
        self.assertEqual(result["revised_prompt"], "revised prompt from provider")

    def test_capability_edit_and_transparent_asset_keep_legacy_service_methods(self) -> None:
        fake = _FakeYunwuService()
        service = YunwuImageService("https://example.test/v1")
        service.generate = fake.generate  # type: ignore[method-assign]
        service.edit = fake.edit  # type: ignore[method-assign]
        service.transparent_asset = fake.transparent_asset  # type: ignore[method-assign]

        edit_result = service.capability_edit({"prompt": "edit this icon", "image_paths": ["D:/input.png"]})
        transparent_result = service.capability_transparent_asset({"prompt": "transparent yellow key"})

        self.assertEqual(edit_result["operation"], "edit")
        self.assertEqual(edit_result["artifact_refs"][0]["asset_id"], "yunwu-asset-edit-1")
        self.assertEqual(transparent_result["operation"], "transparent_asset")
        self.assertEqual(transparent_result["artifact_refs"][0]["asset_id"], "yunwu-asset-transparent-1")
        self.assertEqual([name for name, _kwargs in fake.calls], ["edit", "transparent_asset"])

    def test_dashscope_image_generate_normalizes_async_task_result(self) -> None:
        post_calls: list[dict[str, object]] = []
        get_calls: list[dict[str, object]] = []

        class _Response:
            def __init__(self, body: dict[str, object], *, content: bytes = b"") -> None:
                self._body = body
                self.content = content

            def raise_for_status(self) -> None:
                return None

            def json(self) -> dict[str, object]:
                return dict(self._body)

        def _fake_post(url: str, *, headers: dict[str, object], json: dict[str, object], timeout: int) -> _Response:
            post_calls.append({"url": url, "headers": dict(headers), "json": dict(json), "timeout": timeout})
            return _Response({"output": {"task_id": "task-123"}, "model": "qwen-image-plus"})

        def _fake_get(url: str, *, headers: dict[str, object] | None = None, timeout: int) -> _Response:
            get_calls.append({"url": url, "headers": dict(headers or {}), "timeout": timeout})
            if url.endswith("/tasks/task-123"):
                return _Response(
                    {
                        "output": {
                            "task_id": "task-123",
                            "task_status": "SUCCEEDED",
                            "results": [{"url": "https://example.test/qwen-image.png"}],
                        },
                        "usage": {"image_count": 1},
                    }
                )
            return _Response({}, content=b"\x89PNG\r\n\x1a\n")

        with tempfile.TemporaryDirectory() as temp_dir:
            adapter = DashScopeImageGenerateAdapter(post_fn=_fake_post, get_fn=_fake_get)

            result = adapter.generate(
                {
                    "prompt": "draw a lantern on a wooden table",
                    "model": "qwen-image-plus",
                    "size": "1024x1024",
                    "n": 1,
                    "api_key": "test-key",
                    "workspace_root": temp_dir,
                }
            )

            self.assertEqual(result["provider_id"], "qwen")
            self.assertEqual(result["model"], "qwen-image-plus")
            self.assertEqual(result["operation"], "generate")
            self.assertEqual(result["requested_n"], 1)
            self.assertEqual(result["actual_n"], 1)
            self.assertEqual(result["task_id"], "task-123")
            self.assertTrue(result["artifact_refs"][0]["local_path"].endswith("result-0.png"))
            self.assertTrue(Path(result["asset_manifest_path"]).is_file())
            self.assertEqual(post_calls[0]["json"]["parameters"]["size"], "1024*1024")
            self.assertEqual(post_calls[0]["json"]["parameters"]["n"], 1)
            self.assertEqual(get_calls[0]["url"].split("/")[-2:], ["tasks", "task-123"])

    def test_dashscope_image_generate_rejects_unsupported_operation_and_model(self) -> None:
        adapter = DashScopeImageGenerateAdapter(post_fn=lambda **_kwargs: None, get_fn=lambda **_kwargs: None)  # type: ignore[arg-type]

        with self.assertRaisesRegex(ValueError, "only operation `generate`"):
            adapter.build_request({"prompt": "x", "operation": "edit", "model": "qwen-image-plus"})

        with self.assertRaisesRegex(ValueError, "Supported image models"):
            adapter.build_request({"prompt": "x", "operation": "generate", "model": "wanx-legacy"})


if __name__ == "__main__":
    unittest.main()
