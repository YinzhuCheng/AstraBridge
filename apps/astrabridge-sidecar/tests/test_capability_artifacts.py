from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from astrabridge_sidecar.capabilities.artifacts import capability_artifact_snapshot
from astrabridge_sidecar.common import write_json


class CapabilityArtifactTests(unittest.TestCase):
    def test_lists_sanitized_text_audio_and_image_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            vision_dir = root / ".astrabridge" / "capabilities" / "vision_analyze" / "vision-run"
            vision_dir.mkdir(parents=True)
            text_path = vision_dir / "text.txt"
            text_path.write_text("AstraBridge vision artifact preview", encoding="utf-8")
            write_json(
                vision_dir / "summary.json",
                {
                    "saved_at": "2026-06-25T01:00:00Z",
                    "capability_id": "vision.analyze",
                    "provider_id": "qwen",
                    "model": "qwen3-vl-plus",
                    "text_path": str(text_path),
                    "request_path": str(vision_dir / "request.json"),
                    "authorization": "should-not-appear",
                    "api_key": "should-not-appear",
                },
            )

            audio_dir = root / ".astrabridge" / "capabilities" / "speech_synthesize" / "tts-run"
            audio_dir.mkdir(parents=True)
            audio_path = audio_dir / "output.wav"
            transcript_path = audio_dir / "transcript.txt"
            audio_path.write_bytes(b"RIFF")
            transcript_path.write_text("AstraBridge TTS preview", encoding="utf-8")
            write_json(
                audio_dir / "summary.json",
                {
                    "saved_at": "2026-06-25T02:00:00Z",
                    "capability_id": "speech.synthesize",
                    "provider_id": "qwen",
                    "model": "qwen3-omni-flash",
                    "mime_type": "audio/wav",
                    "audio_path": str(audio_path),
                    "transcript_path": str(transcript_path),
                },
            )

            assets_dir = root / ".astrabridge" / "assets"
            assets_dir.mkdir(parents=True)
            image_path = assets_dir / "generated.png"
            image_path.write_bytes(b"png")
            write_json(
                assets_dir / "asset_registry.json",
                {
                    "assets": [
                        {
                            "asset_id": "asset-1",
                            "source_path": str(image_path),
                            "created_at": "2026-06-25T03:00:00Z",
                            "status": "approved",
                            "role": "sprite",
                        }
                    ]
                },
            )

            snapshot = capability_artifact_snapshot(str(root))
            by_capability = {item["capability_id"]: item for item in snapshot["artifacts"]}

            self.assertEqual(snapshot["schema_version"], "astrabridge-capability-artifacts-v1")
            self.assertEqual(snapshot["total_count"], 3)
            self.assertEqual(by_capability["vision.analyze"]["preview"]["text"], "AstraBridge vision artifact preview")
            self.assertNotIn("authorization", by_capability["vision.analyze"]["metadata"])
            self.assertNotIn("api_key", by_capability["vision.analyze"]["metadata"])
            self.assertEqual(by_capability["speech.synthesize"]["preview"]["audio_path"], str(audio_path.resolve()))
            self.assertEqual(by_capability["image.generate"]["preview"]["image_path"], str(image_path.resolve()))
            self.assertTrue(by_capability["image.generate"]["artifact_refs"][0]["exists"])

    def test_ignores_paths_outside_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            run_dir = root / ".astrabridge" / "capabilities" / "vision_analyze" / "run"
            run_dir.mkdir(parents=True)
            write_json(
                run_dir / "summary.json",
                {
                    "saved_at": "2026-06-25T01:00:00Z",
                    "capability_id": "vision.analyze",
                    "provider_id": "qwen",
                    "model": "qwen3-vl-plus",
                    "text_path": str(Path(temp_dir).parent / "outside.txt"),
                },
            )

            snapshot = capability_artifact_snapshot(str(root))

            self.assertEqual(snapshot["artifacts"][0]["artifact_refs"], [])
            self.assertEqual(snapshot["artifacts"][0]["preview"]["text"], "")


if __name__ == "__main__":
    unittest.main()
