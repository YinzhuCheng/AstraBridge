from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORT_DIR = REPO_ROOT / "PRIVATE" / "agent-bench-dogfood" / "reports"
SCHEMA_VERSION = "astrabridge-agent-bench-harness-record-v1"

VALID_STATUSES = {"not_started", "running", "pass", "partial", "fail", "timeout", "skipped"}

SAFE_TOKEN_KEYS = {"token_signal", "input_tokens", "output_tokens", "total_tokens", "token_count"}
SENSITIVE_KEY_PARTS = (
    "api_key",
    "apikey",
    "authorization",
    "bearer",
    "cookie",
    "password",
    "passwd",
    "secret",
    "access_token",
    "refresh_token",
    "session_token",
    "id_token",
    "private_key",
)

SECRET_PATTERNS = (
    re.compile(r"Bearer\s+[A-Za-z0-9._~+/=-]{8,}", re.IGNORECASE),
    re.compile(r"(?<![A-Za-z0-9])sk-[A-Za-z0-9_-]{20,}", re.IGNORECASE),
    re.compile(r"(api[_-]?key\s*[:=]\s*)['\"]?[^'\"\s,}]{8,}", re.IGNORECASE),
    re.compile(r"((?:authorization|cookie|password|secret)\s*[:=]\s*)['\"]?[^'\"\s,}]{4,}", re.IGNORECASE),
)


class ValidationError(RuntimeError):
    pass


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean_string(value: Any, limit: int = 2000) -> str:
    text = str(value or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    for pattern in SECRET_PATTERNS:
        text = pattern.sub(lambda match: f"{match.group(1)}[REDACTED]" if match.groups() else "[REDACTED]", text)
    if len(text) > limit:
        return f"{text[:limit].rstrip()}... [truncated]"
    return text


def _is_sensitive_key(key: str) -> bool:
    normalized = re.sub(r"[^a-z0-9]+", "_", key.strip().lower()).strip("_")
    if normalized in SAFE_TOKEN_KEYS:
        return False
    return any(part == normalized or normalized.endswith(f"_{part}") or part in normalized for part in SENSITIVE_KEY_PARTS)


def sanitize_payload(value: Any) -> tuple[Any, int]:
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        redacted_count = 0
        for raw_key, raw_item in value.items():
            key = str(raw_key)
            if _is_sensitive_key(key):
                redacted_count += 1
                continue
            clean_item, item_count = sanitize_payload(raw_item)
            sanitized[key] = clean_item
            redacted_count += item_count
        if redacted_count:
            sanitized["_redacted_field_count"] = redacted_count
        return sanitized, redacted_count
    if isinstance(value, list):
        items: list[Any] = []
        redacted_count = 0
        for item in value:
            clean_item, item_count = sanitize_payload(item)
            items.append(clean_item)
            redacted_count += item_count
        return items, redacted_count
    if isinstance(value, str):
        cleaned = _clean_string(value)
        return cleaned, 1 if cleaned != value else 0
    return value, 0


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _sanitize_tool_call(value: dict[str, Any]) -> dict[str, Any]:
    arguments, argument_redactions = sanitize_payload(value.get("arguments") or value.get("input") or {})
    result_excerpt, result_redactions = sanitize_payload(value.get("result_excerpt") or value.get("result") or "")
    return {
        "name": _clean_string(value.get("name") or value.get("tool") or "unknown", limit=160),
        "status": _clean_string(value.get("status") or "unknown", limit=80),
        "summary": _clean_string(value.get("summary") or "", limit=800),
        "duration_ms": value.get("duration_ms"),
        "arguments": arguments,
        "result_excerpt": result_excerpt,
        "artifacts": [_clean_string(item, limit=500) for item in _as_list(value.get("artifacts"))],
        "redacted_field_count": argument_redactions + result_redactions,
    }


def build_record(payload: dict[str, Any], *, input_source: str, dry_run: bool = False) -> dict[str, Any]:
    now = _utc_now()
    raw_input = payload.get("agent_input") or payload.get("input") or payload.get("prompt") or ""
    clean_input, input_redactions = sanitize_payload(raw_input)
    context_payload, context_redactions = sanitize_payload(payload.get("context_summary") or payload.get("context_package") or "")

    raw_records: list[dict[str, Any]] = []
    for raw_record in _as_list(payload.get("raw_records")):
        raw_dict = dict(raw_record or {})
        clean_payload, redaction_count = sanitize_payload(raw_dict.get("payload") or raw_dict)
        raw_records.append(
            {
                "kind": _clean_string(raw_dict.get("kind") or "raw", limit=80),
                "redacted": True,
                "payload": clean_payload,
                "redacted_field_count": redaction_count,
            }
        )

    for key, kind in (("raw_request", "request"), ("raw_response", "response")):
        if key in payload:
            clean_payload, redaction_count = sanitize_payload(payload[key])
            raw_records.append(
                {
                    "kind": kind,
                    "redacted": True,
                    "payload": clean_payload,
                    "redacted_field_count": redaction_count,
                }
            )

    tool_calls = [_sanitize_tool_call(dict(item or {})) for item in _as_list(payload.get("tool_calls"))]
    status = _clean_string(payload.get("status") or "not_started", limit=80)
    if status not in VALID_STATUSES:
        status = "partial"

    record = {
        "schema_version": SCHEMA_VERSION,
        "task_id": _clean_string(payload.get("task_id") or "dry-run-step4", limit=120),
        "benchmark_shape": _clean_string(payload.get("benchmark_shape") or "agent_bench_dogfood_harness", limit=180),
        "task_title": _clean_string(payload.get("task_title") or "Agent bench harness record", limit=220),
        "task_summary": _clean_string(payload.get("task_summary") or "", limit=1000),
        "provider": _clean_string(payload.get("provider") or "", limit=120),
        "model": _clean_string(payload.get("model") or "", limit=160),
        "real_api_used": bool(payload.get("real_api_used", False)),
        "token_signal": payload.get("token_signal")
        or {"input_tokens": None, "output_tokens": None, "total_tokens": None, "source": "not available"},
        "cost_signal": payload.get("cost_signal") or {"estimated_cost_usd": None, "source": "not available"},
        "started_at": _clean_string(payload.get("started_at") or now, limit=80),
        "completed_at": _clean_string(payload.get("completed_at") or now, limit=80),
        "status": status,
        "agent_input": {
            "source": input_source,
            "prompt_excerpt": clean_input,
            "redacted": True,
            "redacted_field_count": input_redactions,
        },
        "context_package": {
            "summary": context_payload,
            "redacted": True,
            "redacted_field_count": context_redactions,
        },
        "tool_calls": tool_calls,
        "success_criteria": [_clean_string(item, limit=500) for item in _as_list(payload.get("success_criteria"))],
        "observed_result": _clean_string(payload.get("observed_result") or "", limit=1200),
        "final_state": {
            "status": status,
            "observed_result": _clean_string(payload.get("observed_result") or "", limit=1200),
            "failure_mode": _clean_string(payload.get("failure_mode") or "", limit=1000),
        },
        "screenshots": [_clean_string(item, limit=500) for item in _as_list(payload.get("screenshots"))],
        "artifacts": [_clean_string(item, limit=500) for item in _as_list(payload.get("artifacts"))],
        "raw_records": raw_records,
        "validations": [_clean_string(item, limit=800) for item in _as_list(payload.get("validations"))],
        "failure_mode": _clean_string(payload.get("failure_mode") or "", limit=1000),
        "product_fix": _clean_string(payload.get("product_fix") or "", limit=1000),
        "ui_review": payload.get("ui_review")
        or {"screenshots_checked": [], "issues_found": [], "fixes_applied": []},
        "next_entry": _clean_string(payload.get("next_entry") or "", limit=500),
        "notes": _clean_string(payload.get("notes") or "", limit=1000),
        "harness": {
            "script": "scripts/agent_bench_harness.py",
            "generated_at": now,
            "dry_run": dry_run,
            "input_source": input_source,
        },
    }
    validate_record(record)
    return record


def validate_record(record: dict[str, Any]) -> None:
    required = [
        "schema_version",
        "task_id",
        "agent_input",
        "context_package",
        "provider",
        "model",
        "tool_calls",
        "screenshots",
        "status",
        "final_state",
        "raw_records",
    ]
    missing = [key for key in required if key not in record]
    if missing:
        raise ValidationError(f"Missing required record fields: {', '.join(missing)}")
    if record["schema_version"] != SCHEMA_VERSION:
        raise ValidationError(f"Unsupported schema_version: {record['schema_version']}")
    if record["status"] not in VALID_STATUSES:
        raise ValidationError(f"Invalid status: {record['status']}")
    if not isinstance(record["tool_calls"], list):
        raise ValidationError("tool_calls must be a list")
    if not isinstance(record["screenshots"], list):
        raise ValidationError("screenshots must be a list")
    for raw_record in record.get("raw_records") or []:
        if not raw_record.get("redacted"):
            raise ValidationError("raw_records entries must be marked redacted")
    serialized = json.dumps(record, ensure_ascii=False)
    for pattern in SECRET_PATTERNS:
        if pattern.search(serialized):
            raise ValidationError(f"Record still matches sensitive pattern: {pattern.pattern}")


def dry_run_payload() -> dict[str, Any]:
    fake_secret_key = "fake-dry-run-" + "key-should-not-persist"
    fake_bearer_value = "Bear" + "er fake-dry-run-" + "token-should-not-persist"
    fake_cookie_value = "fake-" + "cookie-should-not-persist"
    api_key_field = "api" + "_key"
    authorization_field = "Author" + "ization"
    cookie_field = "set" + "-cookie"
    return {
        "task_id": "dry-run-step4",
        "benchmark_shape": "agent_bench_dogfood_harness",
        "task_title": "Dry-run harness record",
        "task_summary": "Validate that the minimal agent harness can emit a complete redacted record.",
        "provider": "dry-run-provider",
        "model": "dry-run-model",
        "real_api_used": False,
        "status": "pass",
        "agent_input": "Dry run: record input, context summary, tool calls, screenshots, final state, and redacted raw payloads.",
        "context_summary": {
            "plan": "PLAN/AGENT_BENCH_DOGFOOD_EXECUTION_PLAN.md step 4",
            "task_pool": "PLAN/AGENT_BENCH_DOGFOOD_TASK_POOL.md",
            "artifact_root": "PRIVATE/agent-bench-dogfood/",
        },
        "tool_calls": [
            {
                "name": "dry_run_validate",
                "status": "pass",
                "summary": "Confirmed required fields and redaction behavior.",
                "duration_ms": 12,
                "arguments": {"sample": "ok", api_key_field: fake_secret_key},
                "result_excerpt": "validation pass",
            }
        ],
        "success_criteria": [
            "Record includes input and context summaries.",
            "Record includes provider/model and tool call summary.",
            "Record includes screenshot paths and final state.",
            "Raw request and response records are redacted.",
        ],
        "observed_result": "Dry-run record completed and passed local validation.",
        "screenshots": [
            "PRIVATE/agent-bench-dogfood/screenshots/baseline-20260626-step2/04-runtime-status.png"
        ],
        "artifacts": [
            "PLAN/AGENT_BENCH_DOGFOOD_TASK_POOL.md",
            "PRIVATE/agent-bench-dogfood/reports/task-pool-20260626-step3.json",
        ],
        "raw_request": {
            "url": "https://example.invalid/v1/chat/completions",
            "headers": {
                authorization_field: fake_bearer_value,
                "Content-Type": "application/json",
            },
            "json": {
                "model": "dry-run-model",
                "messages": [{"role": "user", "content": "dry run"}],
                api_key_field: fake_secret_key,
            },
        },
        "raw_response": {
            "status_code": 200,
            "headers": {cookie_field: fake_cookie_value},
            "json": {"id": "dry-run", "output": "ok"},
        },
        "validations": [
            "python scripts/agent_bench_harness.py dry-run --output PRIVATE/agent-bench-dogfood/reports/dry-run-step4-record.json",
            "python scripts/agent_bench_harness.py validate --input PRIVATE/agent-bench-dogfood/reports/dry-run-step4-record.json",
        ],
        "product_fix": "No UI repair was required for this recorder-only step.",
        "ui_review": {
            "screenshots_checked": [],
            "issues_found": [],
            "fixes_applied": [],
        },
        "next_entry": "Step 5: run the baseline local code-fix task.",
        "notes": "This dry run does not call a real provider.",
    }


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def command_dry_run(args: argparse.Namespace) -> int:
    output = Path(args.output) if args.output else DEFAULT_REPORT_DIR / "dry-run-step4-record.json"
    record = build_record(dry_run_payload(), input_source="built-in dry run", dry_run=True)
    _write_json(output, record)
    print(f"wrote {output}")
    return 0


def command_record(args: argparse.Namespace) -> int:
    input_path = Path(args.input)
    output = Path(args.output) if args.output else DEFAULT_REPORT_DIR / f"{input_path.stem}.record.json"
    payload = _read_json(input_path)
    record = build_record(payload, input_source=str(input_path), dry_run=False)
    _write_json(output, record)
    print(f"wrote {output}")
    return 0


def command_validate(args: argparse.Namespace) -> int:
    input_path = Path(args.input)
    record = _read_json(input_path)
    validate_record(record)
    print(f"valid {input_path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Record redacted AstraBridge agent benchmark dogfood runs.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    dry_run = subparsers.add_parser("dry-run", help="Write a complete dry-run harness record.")
    dry_run.add_argument("--output", default=str(DEFAULT_REPORT_DIR / "dry-run-step4-record.json"))
    dry_run.set_defaults(func=command_dry_run)

    record = subparsers.add_parser("record", help="Build a harness record from a JSON payload.")
    record.add_argument("--input", required=True)
    record.add_argument("--output")
    record.set_defaults(func=command_record)

    validate = subparsers.add_parser("validate", help="Validate an existing harness record.")
    validate.add_argument("--input", required=True)
    validate.set_defaults(func=command_validate)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
