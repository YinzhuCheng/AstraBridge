from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _capability_entry(summary: dict[str, Any], run_dir: Path, capability_id: str) -> dict[str, Any]:
    tests = dict(summary.get("tests") or {})
    if capability_id == "speech.transcribe":
        primary = dict(tests.get("qwen_asr_retry") or tests.get("qwen_asr") or {})
        return {
            "capability_id": capability_id,
            "lane_type": "model_backed",
            "provider_id": "qwen",
            "model": _clean_text(primary.get("model") or "qwen3-asr-flash"),
            "status": "pass" if primary.get("ok") else "fail",
            "evidence": [
                str(run_dir / "qwen_asr_retry.request.json"),
                str(run_dir / "qwen_asr_retry.response.json"),
            ],
            "notes": [
                "Qwen ASR capability smoke uses the audio-only content contract.",
                f"Transcript length: {len(_clean_text(primary.get('text')))} characters.",
            ],
        }
    if capability_id == "speech.synthesize":
        primary = dict(tests.get("qwen_omni_tts") or {})
        return {
            "capability_id": capability_id,
            "lane_type": "model_backed",
            "provider_id": "qwen",
            "model": _clean_text(primary.get("model") or "qwen3.5-omni-plus"),
            "status": "pass" if primary.get("ok") else "fail",
            "evidence": [
                str(run_dir / "qwen_omni_tts.qwen3.5-omni-plus.request.json"),
                str(run_dir / "qwen_omni_tts.qwen3.5-omni-plus.sse.txt"),
                str(run_dir / "qwen_omni_tts.wav"),
            ],
            "notes": [
                "Qwen Omni TTS capability smoke validates SSE delta.audio.data assembly.",
                f"Audio bytes: {primary.get('audio_bytes', 'unknown')}",
            ],
        }
    if capability_id == "vision.analyze":
        qwen = dict(tests.get("qwen_vision") or {})
        kimi = dict(tests.get("kimi_vision") or {})
        return {
            "capability_id": capability_id,
            "lane_type": "model_backed",
            "status": "pass" if qwen.get("ok") and kimi.get("ok") else "partial",
            "providers": [
                {
                    "provider_id": "qwen",
                    "model": _clean_text(qwen.get("model") or "qwen3.7-plus"),
                    "status": "pass" if qwen.get("ok") else "fail",
                    "evidence": [
                        str(run_dir / "qwen_vision.qwen3.7-plus.request.json"),
                        str(run_dir / "qwen_vision.qwen3.7-plus.response.json"),
                        str(run_dir / "qwen_vision.text.txt"),
                    ],
                },
                {
                    "provider_id": "kimi",
                    "model": _clean_text(kimi.get("model") or "kimi-k2.6"),
                    "status": "pass" if kimi.get("ok") else "fail",
                    "evidence": [
                        str(run_dir / "kimi_vision.kimi-k2.6.request.json"),
                        str(run_dir / "kimi_vision.kimi-k2.6.response.json"),
                        str(run_dir / "kimi_vision.text.txt"),
                    ],
                },
            ],
            "notes": [
                "Vision capability smoke covers both Qwen and Kimi adapters.",
            ],
        }
    if capability_id == "image.generate":
        return {
            "capability_id": capability_id,
            "lane_type": "model_backed",
            "provider_id": "yunwu",
            "status": "regression_only_this_round",
            "evidence": [
                "apps/astrabridge-sidecar/tests/test_image_generate_adapter.py",
                "apps/astrabridge-sidecar/astrabridge_sidecar/yunwu_image_mcp_server.py",
            ],
            "notes": [
                "This round reused existing Yunwu image compatibility coverage and did not run a fresh live image smoke.",
            ],
        }
    if capability_id == "web.search":
        return {
            "capability_id": capability_id,
            "lane_type": "web_standalone",
            "status": "regression_only_this_round",
            "evidence": [
                "apps/astrabridge-sidecar/tests/test_web_lane.py",
                "apps/astrabridge-sidecar/astrabridge_sidecar/astrabridge_web_mcp_server.py",
            ],
            "notes": [
                "Web search remains standalone and is tracked in the same matrix for interface completeness.",
            ],
        }
    raise ValueError(f"Unsupported capability id: {capability_id}")


def build_matrix(summary_path: Path) -> dict[str, Any]:
    summary = _load_json(summary_path)
    run_dir = Path(summary["run_dir"])
    capabilities = [
        _capability_entry(summary, run_dir, "image.generate"),
        _capability_entry(summary, run_dir, "vision.analyze"),
        _capability_entry(summary, run_dir, "speech.transcribe"),
        _capability_entry(summary, run_dir, "speech.synthesize"),
        _capability_entry(summary, run_dir, "web.search"),
    ]
    return {
        "schema_version": "astrabridge-capability-smoke-matrix-v1",
        "generated_from": str(summary_path),
        "generated_at": summary.get("finished_at") or summary.get("started_at"),
        "run_dir": str(run_dir),
        "capabilities": capabilities,
    }


def render_markdown(matrix: dict[str, Any]) -> str:
    lines = [
        "# Capability Smoke Matrix",
        "",
        f"- Source summary: `{matrix['generated_from']}`",
        f"- Run dir: `{matrix['run_dir']}`",
        "",
        "| Capability | Lane | Status | Notes |",
        "| --- | --- | --- | --- |",
    ]
    for item in matrix["capabilities"]:
        notes = "; ".join(str(note) for note in item.get("notes") or [])
        lines.append(f"| `{item['capability_id']}` | `{item['lane_type']}` | `{item['status']}` | {notes} |")
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("Usage: python scripts/build_capability_smoke_matrix.py PRIVATE/smoke/<run>/summary.json")
        return 2
    summary_path = Path(argv[1]).resolve()
    matrix = build_matrix(summary_path)
    run_dir = Path(matrix["run_dir"])
    json_path = run_dir / "capability_smoke_matrix.json"
    md_path = run_dir / "capability_smoke_matrix.md"
    json_path.write_text(json.dumps(matrix, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(matrix), encoding="utf-8")
    print(str(json_path))
    print(str(md_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
