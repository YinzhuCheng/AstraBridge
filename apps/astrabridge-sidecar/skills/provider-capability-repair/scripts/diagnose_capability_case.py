from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[5]

_LANE_ENTRYPOINTS = {
    "vision.analyze": [
        "apps/astrabridge-sidecar/astrabridge_sidecar/capabilities/vision_analyze_adapter.py",
        "PRIVATE/provider-compatibility/step7_exhaustive_batch_b_runner.py",
    ],
    "speech.transcribe": [
        "apps/astrabridge-sidecar/astrabridge_sidecar/capabilities/speech_transcribe_adapter.py",
        "PRIVATE/provider-compatibility/step8_exhaustive_batch_c_runner.py",
    ],
    "speech.synthesize": [
        "apps/astrabridge-sidecar/astrabridge_sidecar/capabilities/speech_synthesize_adapter.py",
        "PRIVATE/provider-compatibility/step9_exhaustive_batch_d_runner.py",
    ],
    "image.generate": [
        "apps/astrabridge-sidecar/astrabridge_sidecar/capabilities/image_generate_adapter.py",
        "PRIVATE/provider-compatibility/step10_exhaustive_batch_e_runner.py",
    ],
}

_GENERAL_ENTRYPOINTS = [
    "apps/astrabridge-sidecar/astrabridge_sidecar/capabilities/smoke.py",
    "apps/astrabridge-sidecar/astrabridge_sidecar/capabilities/runtime.py",
    "apps/astrabridge-sidecar/astrabridge_sidecar/provider_compatibility_smoke.py",
    "apps/astrabridge-sidecar/astrabridge_sidecar/capabilities/capability_registry.py",
    "apps/astrabridge-sidecar/astrabridge_sidecar/capabilities/specs.py",
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Diagnose a preserved AstraBridge provider-capability smoke case.")
    parser.add_argument("--case", required=True, help="Path to a case JSON under PRIVATE/provider-compatibility/.../cases/")
    parser.add_argument("--out", help="Optional output JSON path.")
    args = parser.parse_args()

    case_path = Path(args.case).expanduser().resolve()
    case = _read_json(case_path)
    diagnosis = diagnose_case(case_path, case)
    payload = json.dumps(diagnosis, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        out_path = Path(args.out).expanduser().resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")


def diagnose_case(case_path: Path, case: dict[str, Any]) -> dict[str, Any]:
    lane_kind = _clean(case.get("lane_kind"))
    requested_provider = _requested_provider(case)
    requested_model = _requested_model(case)
    route = dict(case.get("route_observed") or {})
    route_provider = _clean(route.get("provider_id"))
    route_model = _clean(route.get("model"))
    artifacts = _artifact_paths(case)
    request_payload = _read_optional_json(artifacts.get("request"))
    response_payload = _read_optional_json(artifacts.get("response"))
    request_body = dict(request_payload.get("json") or {})
    response_body = dict(response_payload.get("body") or {})
    request_model = _clean(request_body.get("model"))
    response_model = _clean(response_body.get("model"))
    reasons = [str(item).strip() for item in list(case.get("reasons") or []) if str(item).strip()]

    diagnosis_kind = _classify_diagnosis(
        requested_provider=requested_provider,
        requested_model=requested_model,
        route_provider=route_provider,
        route_model=route_model,
        request_model=request_model,
        response_model=response_model,
        reasons=reasons,
    )
    summary = _diagnosis_summary(
        diagnosis_kind=diagnosis_kind,
        requested_provider=requested_provider,
        requested_model=requested_model,
        route_provider=route_provider,
        route_model=route_model,
        request_model=request_model,
        response_model=response_model,
    )

    return {
        "schema_version": "astrabridge-capability-case-diagnosis-v1",
        "case_path": str(case_path),
        "case_id": _clean(case.get("case_id")),
        "lane_kind": lane_kind,
        "requested_target": {
            "provider_id": requested_provider or None,
            "model": requested_model or None,
        },
        "route_observed": {
            "provider_id": route_provider or None,
            "model": route_model or None,
            "route_mode": _clean(route.get("route_mode")) or None,
            "resolution_status": _clean(route.get("resolution_status")) or None,
        },
        "request_artifact": {
            "path": artifacts.get("request"),
            "model": request_model or None,
            "url": _clean(request_payload.get("url")) or None,
        },
        "response_artifact": {
            "path": artifacts.get("response"),
            "model": response_model or None,
        },
        "diagnosis": diagnosis_kind,
        "summary": summary,
        "reasons": reasons,
        "suggested_entrypoints": _entrypoints_for_lane(lane_kind),
    }


def _classify_diagnosis(
    *,
    requested_provider: str,
    requested_model: str,
    route_provider: str,
    route_model: str,
    request_model: str,
    response_model: str,
    reasons: list[str],
) -> str:
    requested_target = "/".join(part for part in (requested_provider, requested_model) if part)
    route_target = "/".join(part for part in (route_provider, route_model) if part)
    route_mismatch = bool(requested_target and route_target and requested_target != route_target)
    request_matches = bool(request_model and requested_model and request_model == requested_model)
    response_matches = not requested_model or not response_model or response_model == requested_model
    if request_model and requested_model and request_model != requested_model:
        return "request_payload_mismatch"
    if route_mismatch and request_matches and response_matches:
        return "smoke_route_reporting_mismatch"
    if request_matches and response_model and requested_model and response_model != requested_model:
        return "provider_response_model_alias_or_remap"
    if any("unsupported" in reason.lower() for reason in reasons):
        return "provider_or_adapter_behavior"
    if any("empty" in reason.lower() or "artifact" in reason.lower() for reason in reasons):
        return "provider_or_adapter_behavior"
    return "unknown"


def _diagnosis_summary(
    *,
    diagnosis_kind: str,
    requested_provider: str,
    requested_model: str,
    route_provider: str,
    route_model: str,
    request_model: str,
    response_model: str,
) -> str:
    if diagnosis_kind == "smoke_route_reporting_mismatch":
        return (
            f"Request artifact targeted `{requested_provider}/{requested_model}`, "
            f"but smoke reported `{route_provider}/{route_model}`."
        )
    if diagnosis_kind == "request_payload_mismatch":
        return f"Request artifact used `{request_model}` instead of the expected `{requested_model}`."
    if diagnosis_kind == "provider_response_model_alias_or_remap":
        return f"Provider response echoed `{response_model}` while the request targeted `{requested_model}`."
    if diagnosis_kind == "provider_or_adapter_behavior":
        return "Route and request shape do not show a direct targeting error; inspect adapter behavior and artifact validation."
    return "Case does not match a known repair pattern; inspect request/response artifacts and smoke reasons manually."


def _requested_provider(case: dict[str, Any]) -> str:
    provider_id = _clean(case.get("provider_id"))
    if provider_id:
        return provider_id
    model_id = _clean(case.get("model_id"))
    if "/" in model_id:
        return model_id.split("/", 1)[0]
    return ""


def _requested_model(case: dict[str, Any]) -> str:
    for key in ("native_model", "model"):
        value = _clean(case.get(key))
        if value:
            return value
    model_id = _clean(case.get("model_id"))
    if "/" in model_id:
        return model_id.split("/", 1)[1]
    return model_id


def _artifact_paths(case: dict[str, Any]) -> dict[str, str]:
    paths = {
        "request": "",
        "response": "",
        "sse": "",
        "summary": "",
    }
    for item in list(case.get("artifact_observations") or []):
        if not isinstance(item, dict):
            continue
        path = _clean(item.get("path"))
        if not path:
            continue
        artifact_type = _clean(item.get("artifact_type"))
        if artifact_type in paths and not paths[artifact_type]:
            paths[artifact_type] = path
    for item in list(case.get("evidence_paths") or []):
        path = _clean(item)
        if not path:
            continue
        name = Path(path).name.lower()
        if name == "request.json" and not paths["request"]:
            paths["request"] = path
        elif name == "response.json" and not paths["response"]:
            paths["response"] = path
        elif name == "response.sse.txt" and not paths["sse"]:
            paths["sse"] = path
        elif name == "summary.json" and not paths["summary"]:
            paths["summary"] = path
    return paths


def _entrypoints_for_lane(lane_kind: str) -> list[str]:
    ordered = [*_GENERAL_ENTRYPOINTS, *_LANE_ENTRYPOINTS.get(lane_kind, [])]
    seen: set[str] = set()
    resolved: list[str] = []
    for item in ordered:
        if item in seen:
            continue
        seen.add(item)
        resolved.append(str((ROOT / item).resolve()))
    return resolved


def _read_optional_json(path_text: str) -> dict[str, Any]:
    if not path_text:
        return {}
    path = Path(path_text)
    if not path.exists() or path.is_dir():
        return {}
    return _read_json(path)


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected a JSON object in {path}")
    return payload


def _clean(value: Any) -> str:
    return str(value or "").strip()


if __name__ == "__main__":
    main()
