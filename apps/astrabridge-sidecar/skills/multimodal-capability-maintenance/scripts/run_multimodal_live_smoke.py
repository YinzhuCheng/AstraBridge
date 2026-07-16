from __future__ import annotations

import argparse
import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a bounded multimodal provider-backed smoke bundle through the sidecar.")
    parser.add_argument("--sidecar", default="http://127.0.0.1:8791")
    parser.add_argument("--workspace-root", required=True)
    parser.add_argument("--artifact-root", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--provider", default="qwen")
    parser.add_argument("--image-model", default="")
    parser.add_argument("--vision-model", default="qwen3-vl-plus")
    parser.add_argument("--asr-model", default="qwen3-asr-flash")
    parser.add_argument("--tts-model", default="qwen3-tts-flash")
    parser.add_argument("--tts-voice", default="Tina")
    parser.add_argument("--asr-audio-path", default="")
    return parser.parse_args()


def _get_json(url: str, headers: dict[str, str] | None = None, timeout: int = 60) -> dict:
    request = urllib.request.Request(url, headers=headers or {}, method="GET")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _post_json(url: str, payload: dict, headers: dict[str, str] | None = None, timeout: int = 900) -> dict:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", **(headers or {})},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _lane_id(provider_id: str, model: str, capability_id: str) -> str:
    return f"{provider_id}/{model}:{capability_id}"


def main() -> None:
    args = _parse_args()
    workspace_root = Path(args.workspace_root).resolve()
    artifact_root = Path(args.artifact_root).resolve()
    artifact_root.mkdir(parents=True, exist_ok=True)
    sidecar = str(args.sidecar).rstrip("/")
    admin_token = _get_json(f"{sidecar}/api/admin/session").get("admin_session_token")
    health = _get_json(f"{sidecar}/api/health")
    session = _get_json(f"{sidecar}/api/llm-manager/session")
    profiles = _get_json(f"{sidecar}/api/profiles")

    audio_path = Path(args.asr_audio_path).resolve() if args.asr_audio_path else (
        workspace_root / ".astrabridge" / "capabilities" / "speech_synthesize" / "qwen-tts-20260706T142419894491-04e0aa" / "output.wav"
    )
    cases: list[dict] = []
    if str(args.image_model).strip():
        cases.append(
            {
                "case_id": f"{args.provider}-image-generate-live",
                "capability_id": "image.generate",
                "provider_id": args.provider,
                "model": args.image_model,
                "mode": "provider",
                "allow_provider": True,
                "workspace_root": str(workspace_root),
                "prompt": "A minimal blue square app icon on a white background.",
                "n": 1,
                "size": "1024x1024",
                "response_format": "url",
                "image_format": "png",
                "purpose": "multimodal_live_smoke_image_generate",
            }
        )
    if str(args.vision_model).strip():
        cases.append(
            {
                "case_id": f"{args.provider}-vision-analyze-live",
                "capability_id": "vision.analyze",
                "provider_id": args.provider,
                "model": args.vision_model,
                "mode": "provider",
                "allow_provider": True,
                "workspace_root": str(workspace_root),
            }
        )
    if str(args.asr_model).strip():
        cases.append(
            {
                "case_id": f"{args.provider}-speech-transcribe-live",
                "capability_id": "speech.transcribe",
                "provider_id": args.provider,
                "model": args.asr_model,
                "mode": "provider",
                "allow_provider": True,
                "workspace_root": str(workspace_root),
                "audio_inputs": [{"path": str(audio_path), "mime_type": "audio/wav"}],
                "language_hint": "en",
            }
        )
    if str(args.tts_model).strip():
        cases.append(
            {
                "case_id": f"{args.provider}-speech-synthesize-live",
                "capability_id": "speech.synthesize",
                "provider_id": args.provider,
                "model": args.tts_model,
                "mode": "provider",
                "allow_provider": True,
                "workspace_root": str(workspace_root),
                "voice": args.tts_voice,
            }
        )
    smoke_payload = {"run_id": args.run_id, "cases": cases}
    smoke_response = _post_json(
        f"{sidecar}/api/runtime/provider-compatibility-smoke",
        smoke_payload,
        headers={"X-Admin-Session-Token": str(admin_token or "")},
    )
    smoke = dict(smoke_response.get("smoke") or {})

    preflight = {
        "schema_version": "astrabridge-multimodal-live-smoke-preflight-v1",
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(),
        "sidecar": sidecar,
        "health": {
            "ok": health.get("ok"),
            "provider_count": ((health.get("router") or {}).get("provider_count")),
            "model_count": ((health.get("router") or {}).get("model_count")),
        },
        "session": {
            "mode": session.get("mode"),
            "username": session.get("username"),
            "unlocked": session.get("unlocked"),
            "active_provider_ids": sorted((session.get("active_key_ids") or {}).keys()),
        },
        "profiles": {
            "provider_ids": sorted({str(item.get("provider_id") or "") for item in list(profiles.get("profiles") or []) if isinstance(item, dict)}),
        },
    }
    lane_index = []
    for case in list(smoke.get("cases") or []):
        provider_id = str(case.get("provider_id") or "")
        model = str(case.get("model") or "")
        capability_id = str(case.get("capability_id") or "")
        lane_index.append(
            {
                "case_id": case.get("case_id"),
                "lane_id": _lane_id(provider_id, model, capability_id),
                "status": case.get("status"),
                "reasons": list(case.get("reasons") or []),
                "warnings": list(case.get("warnings") or []),
                "summary_case_path": str(Path(smoke.get("artifact_paths", {}).get("case_dir") or "") / f"{case.get('case_id')}.json"),
            }
        )
    summary = {
        "schema_version": "astrabridge-multimodal-live-smoke-wrapper-v1",
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(),
        "run_id": args.run_id,
        "status": smoke.get("status"),
        "counts": smoke.get("counts"),
        "preflight_json": str((artifact_root / "preflight.json").resolve()),
        "case_pack_json": str((artifact_root / "case-pack.json").resolve()),
        "lane_index_json": str((artifact_root / "lane-index.json").resolve()),
        "provider_smoke_summary_json": smoke.get("artifact_paths", {}).get("summary_json"),
        "provider_smoke_report_md": smoke.get("artifact_paths", {}).get("report_md"),
        "provider_smoke_case_dir": smoke.get("artifact_paths", {}).get("case_dir"),
        "lane_index": lane_index,
    }
    (artifact_root / "preflight.json").write_text(json.dumps(preflight, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (artifact_root / "case-pack.json").write_text(json.dumps(smoke_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (artifact_root / "lane-index.json").write_text(json.dumps(lane_index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (artifact_root / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(str((artifact_root / "summary.json").resolve()))


if __name__ == "__main__":
    main()
