from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .exhaustive_smoke_contract import normalize_exhaustive_smoke_result


_EXIT_CODE_RE = re.compile(r"Exit code:\s*(-?\d+)", re.IGNORECASE)


def load_session_events(session_path: str | Path | None) -> list[dict[str, Any]]:
    text = str(session_path or "").strip()
    if not text:
        return []
    path = Path(text)
    if not path.exists() or path.is_dir():
        return []
    events: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except Exception:
            continue
        if isinstance(item, dict):
            events.append(item)
    return events


def session_function_calls(events: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    calls_by_id: dict[str, dict[str, Any]] = {}
    ordered: list[str] = []
    for event in list(events or []):
        if not isinstance(event, dict):
            continue
        if str(event.get("type") or "") != "response_item":
            continue
        payload = dict(event.get("payload") or {})
        payload_type = str(payload.get("type") or "")
        if payload_type == "function_call":
            call_id = str(payload.get("call_id") or f"call-{len(ordered)+1}")
            calls_by_id[call_id] = {
                "call_id": call_id,
                "name": str(payload.get("name") or ""),
                "arguments": str(payload.get("arguments") or ""),
                "output": "",
                "exit_code": None,
            }
            ordered.append(call_id)
        elif payload_type == "function_call_output":
            call_id = str(payload.get("call_id") or "")
            if not call_id:
                continue
            call = calls_by_id.setdefault(
                call_id,
                {"call_id": call_id, "name": "", "arguments": "", "output": "", "exit_code": None},
            )
            call["output"] = str(payload.get("output") or "")
            call["exit_code"] = _output_exit_code(call["output"])
    return [calls_by_id[call_id] for call_id in ordered if call_id in calls_by_id]


def session_assistant_text(events: list[dict[str, Any]] | None) -> str:
    last_text = ""
    for event in list(events or []):
        if not isinstance(event, dict):
            continue
        if str(event.get("type") or "") == "event_msg":
            payload = dict(event.get("payload") or {})
            if str(payload.get("type") or "") == "agent_message":
                message = str(payload.get("message") or "").strip()
                if message:
                    last_text = message
        if str(event.get("type") or "") == "response_item":
            payload = dict(event.get("payload") or {})
            if str(payload.get("type") or "") == "message" and str(payload.get("role") or "") == "assistant":
                for item in list(payload.get("content") or []):
                    if not isinstance(item, dict):
                        continue
                    if str(item.get("type") or "") not in {"output_text", "text"}:
                        continue
                    text = str(item.get("text") or "").strip()
                    if text:
                        last_text = text
    return last_text[:1200]


def summarize_thread_execution(
    thread: dict[str, Any] | None,
    session_events: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    data = dict(thread or {})
    turns = list(data.get("turns") or [])
    turn = dict(turns[-1] or {}) if turns else {}
    items = [dict(item) for item in list(turn.get("items") or []) if isinstance(item, dict)]
    function_calls = session_function_calls(session_events)
    command_events = []
    file_change_paths = []
    dynamic_tools = []
    assistant_text = ""
    for item in items:
        item_type = str(item.get("type") or "")
        if item_type == "commandExecution":
            command_events.append(
                {
                    "command": str(item.get("command") or ""),
                    "status": str(item.get("status") or ""),
                    "exit_code": item.get("exitCode"),
                    "output_excerpt": str(item.get("aggregatedOutput") or "")[:800],
                }
            )
        elif item_type == "dynamicToolCall":
            dynamic_tools.append(
                {
                    "tool": str(item.get("tool") or ""),
                    "status": str(item.get("status") or ""),
                    "success": bool(item.get("success", True)),
                }
            )
        elif item_type == "fileChange":
            for change in list(item.get("changes") or []):
                if isinstance(change, dict):
                    path = str(change.get("path") or "").strip()
                    if path:
                        file_change_paths.append(path)
        elif item_type == "agentMessage":
            text = str(item.get("text") or "").strip()
            if text:
                assistant_text = text[:1200]
    assistant_text = assistant_text or session_assistant_text(session_events)
    shell_calls = [call for call in function_calls if str(call.get("name") or "") == "shell_command"]
    edit_calls = [call for call in function_calls if str(call.get("name") or "") in {"apply_patch", "edit_apply", "edit_preview"}]
    return {
        "thread_id": str(data.get("id") or ""),
        "session_path": str(data.get("path") or ""),
        "cwd": str(data.get("cwd") or ""),
        "terminal_status": str(turn.get("status") or ""),
        "thread_status_type": str(((data.get("status") or {}).get("type")) or ""),
        "assistant_text": assistant_text,
        "command_events": command_events,
        "dynamic_tools": dynamic_tools,
        "file_change_paths": file_change_paths,
        "function_calls": function_calls,
        "shell_calls": shell_calls,
        "edit_calls": edit_calls,
        "shell_call_count": len(shell_calls),
        "edit_call_count": len(edit_calls),
        "command_event_count": len(command_events),
        "file_change_count": len(file_change_paths),
        "token_usage": dict(turn.get("usage") or {}),
    }


def build_text_health_result(case: dict[str, Any], *, test_result: dict[str, Any], key_summary: dict[str, Any] | None = None) -> dict[str, Any]:
    excerpt = str(test_result.get("response_excerpt") or "").strip()
    ok = bool(test_result.get("ok"))
    exact_ok = excerpt.lower() == "ok"
    lower_level_status = "pass" if ok and exact_ok else "partial" if ok and excerpt else "fail"
    reasons = []
    if lower_level_status == "partial":
        reasons.append("Provider returned visible text, but the reply was not exactly `ok`.")
    elif lower_level_status == "fail":
        reasons.append(
            str(((test_result.get("failure_notice") or {}).get("summary")) or excerpt or "Text health request failed.")[:500]
        )
    notes = []
    if key_summary:
        notes.append(f"key_id: {key_summary.get('key_id')}")
        notes.append(f"key_test_status: {key_summary.get('last_test_status')}")
    route_observed = {
        "provider_id": str(test_result.get("provider") or case.get("provider_id") or ""),
        "model": str(test_result.get("model") or case.get("model_id") or ""),
        "status": test_result.get("status"),
    }
    if test_result.get("preview"):
        route_observed["preview_model"] = str((test_result.get("preview") or {}).get("model") or "")
    payload = {
        "case_id": str(case.get("case_id") or ""),
        "lane_id": str(case.get("lane_id") or ""),
        "lane_group": str(case.get("lane_group") or ""),
        "lane_kind": str(case.get("lane_kind") or ""),
        "provider_id": str(case.get("provider_id") or ""),
        "model_id": str(case.get("model_id") or ""),
        "capability_id": str(case.get("capability_id") or ""),
        "scope_decision": str(case.get("scope_decision") or ""),
        "execution_policy": str(case.get("execution_policy") or ""),
        "runner_kind": str(case.get("runner_kind") or ""),
        "lower_level_status": lower_level_status,
        "route_observed": route_observed,
        "usage_signal": dict(test_result.get("usage_signal") or {}),
        "artifact_observations": [
            {"artifact_key": "case_summary", "status": "pass", "observed": True, "artifact_type": "result_record"},
            {
                "artifact_key": "visible_text_signal",
                "status": "pass" if excerpt else "missing",
                "observed": bool(excerpt),
                "artifact_type": "semantic_signal",
            },
        ],
        "reasons": reasons,
        "warnings": list(test_result.get("warnings") or []),
        "failure_notice": dict(test_result.get("failure_notice") or {}),
        "notes": notes + [f"response_excerpt: {excerpt[:160]}"] if excerpt else notes,
    }
    return normalize_exhaustive_smoke_result(payload)


def build_command_execution_result(case: dict[str, Any], *, thread: dict[str, Any], session_events: list[dict[str, Any]]) -> dict[str, Any]:
    observed = summarize_thread_execution(thread, session_events)
    expected = str(((case.get("runner_hints") or {}).get("expected_authority_outcome")) or "").strip()
    shell_success = any(
        (call.get("exit_code") == 0 and str(call.get("name") or "") == "shell_command")
        for call in list(observed.get("function_calls") or [])
    )
    if shell_success:
        lower_level_status = "pass"
        reasons: list[str] = []
    elif expected == "reduced_authority_confirmation":
        lower_level_status = "partial"
        reasons = ["No successful shell tool execution was observed during the command smoke."]
    elif expected == "command_execution_required":
        lower_level_status = "fail"
        reasons = ["This lane expected real shell execution, but no successful shell tool execution was observed."]
    else:
        lower_level_status = "partial"
        reasons = ["No successful shell tool execution was observed during the authority probe."]
    payload = {
        "case_id": str(case.get("case_id") or ""),
        "lane_id": str(case.get("lane_id") or ""),
        "lane_group": str(case.get("lane_group") or ""),
        "lane_kind": str(case.get("lane_kind") or ""),
        "provider_id": str(case.get("provider_id") or ""),
        "model_id": str(case.get("model_id") or ""),
        "capability_id": str(case.get("capability_id") or ""),
        "scope_decision": str(case.get("scope_decision") or ""),
        "execution_policy": str(case.get("execution_policy") or ""),
        "runner_kind": str(case.get("runner_kind") or ""),
        "lower_level_status": lower_level_status,
        "route_observed": {
            "thread_id": observed.get("thread_id"),
            "session_path": observed.get("session_path"),
            "cwd": observed.get("cwd"),
            "terminal_status": observed.get("terminal_status"),
            "thread_status_type": observed.get("thread_status_type"),
            "shell_call_count": observed.get("shell_call_count"),
            "command_event_count": observed.get("command_event_count"),
        },
        "usage_signal": dict(observed.get("token_usage") or {}),
        "artifact_observations": [
            {"artifact_key": "case_summary", "status": "pass", "observed": True, "artifact_type": "result_record"},
            {
                "artifact_key": "command_execution_signal",
                "status": "pass" if shell_success else "missing",
                "observed": shell_success,
                "artifact_type": "runtime_signal",
            },
        ],
        "reasons": reasons,
        "warnings": [],
        "failure_notice": {},
        "evidence_paths": [path for path in [str(observed.get("session_path") or "")] if path],
        "notes": _thread_notes(observed),
    }
    if not shell_success and observed.get("assistant_text"):
        payload["notes"].append(f"assistant_text: {str(observed.get('assistant_text') or '')[:200]}")
    return normalize_exhaustive_smoke_result(payload)


def build_edit_apply_patch_result(
    case: dict[str, Any],
    *,
    thread: dict[str, Any],
    session_events: list[dict[str, Any]],
    scratch_path: str | Path,
    before_text: str,
    after_text: str,
) -> dict[str, Any]:
    observed = summarize_thread_execution(thread, session_events)
    expected = str(((case.get("runner_hints") or {}).get("expected_authority_outcome")) or "").strip()
    edit_tool_success = bool(observed.get("edit_call_count"))
    shell_edit_success = bool(before_text != after_text and any(_shell_call_targets_path(call, str(scratch_path)) for call in list(observed.get("shell_calls") or [])))
    file_changed = before_text != after_text
    if edit_tool_success and file_changed:
        lower_level_status = "pass"
        reasons: list[str] = []
    elif shell_edit_success:
        lower_level_status = "partial"
        reasons = ["The scratch file changed, but the edit happened through shell commands rather than an explicit apply_patch/edit tool call."]
    elif expected == "reduced_authority_confirmation":
        lower_level_status = "partial"
        reasons = ["No scratch-file edit tool execution was observed during the reduced-authority confirmation."]
    elif expected == "apply_patch_required":
        lower_level_status = "fail"
        reasons = ["This lane expected explicit apply_patch/edit tool execution, but none was observed."]
    else:
        lower_level_status = "partial"
        reasons = ["No scratch-file edit tool execution was observed during the authority probe."]
    payload = {
        "case_id": str(case.get("case_id") or ""),
        "lane_id": str(case.get("lane_id") or ""),
        "lane_group": str(case.get("lane_group") or ""),
        "lane_kind": str(case.get("lane_kind") or ""),
        "provider_id": str(case.get("provider_id") or ""),
        "model_id": str(case.get("model_id") or ""),
        "capability_id": str(case.get("capability_id") or ""),
        "scope_decision": str(case.get("scope_decision") or ""),
        "execution_policy": str(case.get("execution_policy") or ""),
        "runner_kind": str(case.get("runner_kind") or ""),
        "lower_level_status": lower_level_status,
        "route_observed": {
            "thread_id": observed.get("thread_id"),
            "session_path": observed.get("session_path"),
            "cwd": observed.get("cwd"),
            "terminal_status": observed.get("terminal_status"),
            "thread_status_type": observed.get("thread_status_type"),
            "edit_call_count": observed.get("edit_call_count"),
            "shell_call_count": observed.get("shell_call_count"),
            "file_change_count": observed.get("file_change_count"),
        },
        "usage_signal": dict(observed.get("token_usage") or {}),
        "artifact_observations": [
            {"artifact_key": "case_summary", "status": "pass", "observed": True, "artifact_type": "result_record"},
            {
                "artifact_key": "edit_strategy_signal",
                "status": "pass" if edit_tool_success and file_changed else "missing",
                "observed": bool(edit_tool_success and file_changed),
                "artifact_type": "runtime_signal",
            },
        ],
        "reasons": reasons,
        "warnings": [],
        "failure_notice": {},
        "evidence_paths": [path for path in [str(observed.get("session_path") or ""), str(scratch_path)] if path],
        "notes": _thread_notes(observed) + [f"scratch_changed: {'true' if file_changed else 'false'}"],
    }
    if shell_edit_success:
        payload["notes"].append("shell_edit_success: true")
    if observed.get("assistant_text"):
        payload["notes"].append(f"assistant_text: {str(observed.get('assistant_text') or '')[:200]}")
    return normalize_exhaustive_smoke_result(payload)


def _thread_notes(observed: dict[str, Any]) -> list[str]:
    notes = []
    for key in ("session_path", "cwd", "terminal_status", "thread_status_type"):
        value = str(observed.get(key) or "").strip()
        if value:
            notes.append(f"{key}: {value}")
    return notes


def _shell_call_targets_path(call: dict[str, Any], scratch_path: str) -> bool:
    text = f"{str(call.get('arguments') or '')}\n{str(call.get('output') or '')}"
    return scratch_path.lower() in text.lower()


def _output_exit_code(output: str) -> int | None:
    match = _EXIT_CODE_RE.search(str(output or ""))
    if not match:
        return None
    try:
        return int(match.group(1))
    except Exception:
        return None
