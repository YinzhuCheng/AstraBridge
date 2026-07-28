from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from ..common import new_id, now_iso
from ..providers.ir import NormalizedResponse, ToolCall
from ..providers.tooling.model_authority import AuthorityAssessment, assess_model_authority
from ..providers.tooling import summarize_tool_output, tool_output_char_limit
from ..security import redact_sensitive
from ..tool_action_ledger import ToolActionValidationError, is_side_effecting_tool, validate_side_effect_arguments


NATIVE_KERNEL_SYSTEM_PROMPT = (
    "You are AstraBridge's provider-neutral coding kernel. "
    "Use the provided tools for repository inspection and file edits instead of inventing file state. "
    "Keep tool arguments as valid JSON. After finishing tool work, provide a concise final answer."
)
MAX_NATIVE_TOOL_ROUNDS = 6


@dataclass(frozen=True)
class NativeTurnResult:
    turn: dict[str, Any]
    thread: dict[str, Any]
    thread_cache_patch: dict[str, Any]
    handoff: dict[str, Any] | None = None


class RuntimeToolFacade:
    def __init__(
        self,
        project_tools: Any,
        *,
        profile_id: str,
        provider_id: str,
        model_id: str,
        authority: AuthorityAssessment,
        permission_mode: str,
        thread_id: str,
        turn_id: str,
        tool_output_char_limit: int = 20000,
    ) -> None:
        self._project_tools = project_tools
        self._profile_id = profile_id
        self._provider_id = provider_id
        self._model_id = model_id
        self._authority = authority
        self._permission_mode = permission_mode
        self._thread_id = thread_id
        self._turn_id = turn_id
        self._tool_output_char_limit = max(512, int(tool_output_char_limit or 20000))

    def tool_definitions(self) -> list[dict[str, Any]]:
        definitions: list[dict[str, Any]] = [
            self._tool_definition("review_status", "Inspect workspace review status, git summary, and changed files.", {}),
            self._tool_definition(
                "review_diff",
                "Read a unified diff for the whole workspace or one path.",
                {
                    "path": {
                        "type": "string",
                        "description": "Optional workspace-relative path to diff.",
                    }
                },
            ),
            self._tool_definition(
                "files_tree",
                "List workspace files with bounded metadata.",
                {
                    "query": {"type": "string", "description": "Optional substring filter."},
                    "limit": {"type": "integer", "description": "Optional result cap."},
                },
            ),
            self._tool_definition(
                "terminal_history",
                "Read bounded recent terminal and command execution history recorded for the current workspace.",
                {
                    "limit": {"type": "integer", "description": "Optional result cap."},
                },
            ),
            self._tool_definition(
                "list_checkpoints",
                "List recent AstraBridge checkpoints for the current workspace.",
                {
                    "limit": {"type": "integer", "description": "Optional result cap."},
                },
            ),
            self._tool_definition(
                "read_file",
                "Read one text or image file from the workspace.",
                {
                    "path": {"type": "string", "description": "Workspace-relative file path."},
                },
                required=("path",),
            ),
        ]
        if self._authority.tier == "A":
            definitions.extend(
                [
                    self._tool_definition(
                        "create_checkpoint",
                        "Create a workspace checkpoint under .astrabridge/saves with an optional description.",
                        {
                            "description": {"type": "string", "description": "Optional checkpoint description."},
                        },
                    ),
                    self._tool_definition(
                        "edit_preview",
                        "Preview a proposed file edit and return a synthetic diff without writing files.",
                        self._edit_parameters(),
                        required=("path",),
                    ),
                ]
            )
            definitions.extend(
                [
                    self._tool_definition(
                        "run_command",
                        "Run a bounded workspace command. Destructive or global commands require explicit approval.",
                        {
                            "command": {"type": "string", "description": "Command line to run inside the workspace."},
                            "cwd": {"type": "string", "description": "Optional workspace-relative working directory."},
                            "timeout_seconds": {"type": "integer", "description": "Optional timeout in seconds."},
                        },
                        required=("command",),
                    ),
                    self._tool_definition(
                        "run_tests",
                        "Run a workspace test command and capture its output as a command execution event.",
                        {
                            "command": {"type": "string", "description": "Test command to run inside the workspace."},
                            "cwd": {"type": "string", "description": "Optional workspace-relative working directory."},
                            "timeout_seconds": {"type": "integer", "description": "Optional timeout in seconds."},
                        },
                        required=("command",),
                    ),
                    self._tool_definition(
                        "edit_apply",
                        "Apply a bounded file edit, create a checkpoint when appropriate, and return diff metadata.",
                        self._edit_parameters(),
                        required=("path",),
                    ),
                ]
            )
        elif self._authority.tier == "B":
            definitions.append(
                self._tool_definition(
                    "edit_preview",
                    "Preview a proposed file edit and return a synthetic diff without writing files.",
                    self._edit_parameters(),
                    required=("path",),
                )
            )
        return definitions

    def execute(self, call: ToolCall) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
        try:
            arguments = self._tool_arguments(call)
        except (ToolActionValidationError, ValueError) as exc:
            result = {
                "ok": False,
                "status": "repairable",
                "repairable": True,
                "error": str(exc),
                "tool_event_verified": True,
            }
            return {}, result, [], self._tool_item(call, {}, result)
        name = call.name
        if name == "review_status":
            result = self._project_tools.review_status()
        elif name == "review_diff":
            result = self._project_tools.review_diff(arguments.get("path"))
        elif name == "files_tree":
            result = self._project_tools.files_tree(arguments.get("query"), arguments.get("limit") or 200)
        elif name == "terminal_history":
            result = self._project_tools.terminal_history(arguments.get("limit") or 30)
        elif name == "list_checkpoints":
            result = self._project_tools.list_checkpoints(arguments.get("limit") or 20)
        elif name == "create_checkpoint":
            if self._authority.tier != "A":
                raise ValueError("The selected model is not allowed to create checkpoints through the native kernel.")
            result = self._project_tools.create_checkpoint(self._checkpoint_payload(arguments, tool_call_id=call.id))
        elif name == "read_file":
            result = self._project_tools.read_file(str(arguments.get("path") or ""))
        elif name == "run_command":
            if self._authority.tier != "A":
                raise ValueError("The selected model is not allowed to execute commands through the native kernel.")
            result = self._project_tools.run_command(self._command_payload(arguments, tool_call_id=call.id))
        elif name == "run_tests":
            if self._authority.tier != "A":
                raise ValueError("The selected model is not allowed to execute test commands through the native kernel.")
            result = self._project_tools.run_tests(self._command_payload(arguments, tool_call_id=call.id))
        elif name == "edit_preview":
            if self._authority.tier not in {"A", "B"}:
                raise ValueError("The selected model is not allowed to preview edits through the native kernel.")
            result = self._project_tools.edit_preview(self._edit_payload(arguments))
        elif name == "edit_apply":
            if self._authority.tier != "A":
                raise ValueError("The selected model is not allowed to apply workspace edits through the native kernel.")
            result = self._project_tools.edit_apply(self._edit_payload(arguments, tool_call_id=call.id))
        else:
            raise ValueError(f"Unsupported native kernel tool: {name}")
        tool_item = self._tool_item(call, arguments, result)
        extra_items = self._extra_items_for_result(call, result)
        return arguments, result, extra_items, tool_item

    def tool_result_message(self, name: str, result: dict[str, Any]) -> str:
        if name == "read_file":
            content, _warnings = summarize_tool_output(
                str(result.get("content") or "") if result.get("kind") == "text" else result.get("message"),
                char_limit=self._tool_output_char_limit,
            )
            payload = {
                "path": result.get("path"),
                "kind": result.get("kind"),
                "size": result.get("size"),
                "content": content,
            }
            return json.dumps(redact_sensitive(payload), ensure_ascii=False)
        if name == "terminal_history":
            payload = {
                "execution_host": result.get("execution_host"),
                "commands": list(result.get("commands") or [])[:20],
            }
            return json.dumps(redact_sensitive(payload), ensure_ascii=False)
        if name == "list_checkpoints":
            payload = {
                "available": result.get("available"),
                "truncated": result.get("truncated"),
                "saves": list(result.get("saves") or [])[:12],
            }
            return json.dumps(redact_sensitive(payload), ensure_ascii=False)
        if name == "create_checkpoint":
            payload = {
                "save": result.get("save") or result.get("manifest"),
                "path": result.get("path"),
                "error": result.get("error"),
                "action_receipt": self._safe_action_receipt(result),
            }
            return json.dumps(redact_sensitive(payload), ensure_ascii=False)
        if name in {"run_command", "run_tests"}:
            output, _warnings = summarize_tool_output(str(result.get("output") or ""), char_limit=self._tool_output_char_limit)
            payload = {
                "ok": result.get("ok"),
                "status": result.get("status"),
                "command": result.get("command"),
                "cwd": result.get("cwd"),
                "exit_code": result.get("exit_code"),
                "approved": result.get("approved"),
                "output": output,
                "error": result.get("error"),
                "action_receipt": self._safe_action_receipt(result),
            }
            return json.dumps(redact_sensitive(payload), ensure_ascii=False)
        if name == "review_diff":
            diff, _warnings = summarize_tool_output(str(result.get("diff") or ""), char_limit=self._tool_output_char_limit)
            payload = {
                "ok": result.get("ok"),
                "path": result.get("path"),
                "diff": diff,
                "error": result.get("error"),
            }
            return json.dumps(redact_sensitive(payload), ensure_ascii=False)
        if name in {"edit_preview", "edit_apply"}:
            preview = dict(result.get("preview") or {})
            preview["diff"], _warnings = summarize_tool_output(str(preview.get("diff") or ""), char_limit=self._tool_output_char_limit)
            payload = {
                "ok": result.get("ok"),
                "applied": result.get("applied"),
                "path": result.get("path"),
                "strategy": result.get("strategy"),
                "preview": preview,
                "checkpoint": result.get("checkpoint"),
                "verification": result.get("verification"),
                "error": result.get("error"),
                "action_receipt": self._safe_action_receipt(result),
            }
            return json.dumps(redact_sensitive(payload), ensure_ascii=False)
        payload = redact_sensitive(result)
        return json.dumps(self._truncate_payload(payload), ensure_ascii=False)

    def _tool_definition(
        self,
        name: str,
        description: str,
        properties: dict[str, Any],
        *,
        required: tuple[str, ...] = (),
    ) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": name,
                "description": description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": list(required),
                    "additionalProperties": False,
                },
            },
        }

    def _edit_parameters(self) -> dict[str, Any]:
        return {
            "path": {"type": "string", "description": "Workspace-relative path to edit."},
            "content": {"type": "string", "description": "Complete replacement content or new file content."},
            "search": {"type": "string", "description": "Single search string for a bounded patch edit."},
            "replace": {"type": "string", "description": "Replacement text for the search edit."},
            "count": {"type": "integer", "description": "Optional expected match count."},
        }

    def _tool_arguments(self, call: ToolCall) -> dict[str, Any]:
        try:
            parsed = json.loads(call.arguments_json or "{}")
        except Exception as exc:  # noqa: BLE001
            raise ValueError(f"Invalid native tool arguments for {call.name}: {exc}") from exc
        if not isinstance(parsed, dict):
            raise ValueError(f"Native tool arguments for {call.name} must be a JSON object.")
        if is_side_effecting_tool(call.name):
            return validate_side_effect_arguments(call.name, parsed)
        return parsed

    def _edit_payload(self, arguments: dict[str, Any], *, tool_call_id: str | None = None) -> dict[str, Any]:
        payload = {
            "profile_id": self._profile_id,
            "provider_id": self._provider_id,
            "model": self._model_id,
            "thread_id": self._thread_id,
            "turn_id": self._turn_id,
        }
        if tool_call_id:
            payload["tool_call_id"] = tool_call_id
            payload["action_source"] = "native_model_tool"
        for key in ("path", "content", "search", "replace", "count", "edits", "operation"):
            if key in arguments and arguments.get(key) is not None and arguments.get(key) != "":
                payload[key] = arguments.get(key)
        return payload

    def _command_payload(self, arguments: dict[str, Any], *, tool_call_id: str) -> dict[str, Any]:
        payload = {
            "profile_id": self._profile_id,
            "provider_id": self._provider_id,
            "model": self._model_id,
            "permission_mode": self._permission_mode,
            "thread_id": self._thread_id,
            "turn_id": self._turn_id,
            "tool_call_id": tool_call_id,
            "action_source": "native_model_tool",
        }
        for key in ("command", "cwd", "timeout_seconds"):
            if key in arguments and arguments.get(key) is not None and arguments.get(key) != "":
                payload[key] = arguments.get(key)
        return payload

    def _checkpoint_payload(self, arguments: dict[str, Any], *, tool_call_id: str) -> dict[str, Any]:
        payload = {
            "profile_id": self._profile_id,
            "provider_id": self._provider_id,
            "model": self._model_id,
            "permission_mode": self._permission_mode,
            "thread_id": self._thread_id,
            "turn_id": self._turn_id,
            "tool_call_id": tool_call_id,
            "action_source": "native_model_tool",
        }
        if "description" in arguments and arguments.get("description") not in {None, ""}:
            payload["description"] = arguments.get("description")
        return payload

    def _tool_item(self, call: ToolCall, arguments: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
        summary = {
            "tool": call.name,
            "ok": bool(result.get("ok", True)),
            "path": result.get("path"),
            "applied": result.get("applied"),
            "checkpoint_save_id": ((result.get("checkpoint") or {}).get("save_id") if isinstance(result.get("checkpoint"), dict) else None),
            "review_diff_path": ((result.get("verification") or {}).get("review_diff_path") if isinstance(result.get("verification"), dict) else None),
            "tool_event_verified": True,
        }
        if call.name == "files_tree":
            summary["item_count"] = len(list(result.get("items") or []))
            summary["paths"] = [str(item.get("path") or "") for item in list(result.get("items") or [])[:6] if isinstance(item, dict)]
        elif call.name == "review_status":
            summary["git"] = dict(result.get("git") or {})
            summary["files"] = [str(item.get("path") or "") for item in list(result.get("files") or [])[:6] if isinstance(item, dict)]
        elif call.name == "terminal_history":
            commands = list(result.get("commands") or [])
            summary["command_count"] = len(commands)
            summary["commands"] = [str(item.get("summary") or item.get("command") or "")[:120] for item in commands[:6] if isinstance(item, dict)]
        elif call.name == "list_checkpoints":
            saves = list(result.get("saves") or [])
            summary["checkpoint_count"] = len(saves)
            summary["save_ids"] = [str(item.get("save_id") or "") for item in saves[:6] if isinstance(item, dict)]
        elif call.name == "create_checkpoint":
            save = dict(result.get("save") or result.get("manifest") or {})
            summary["checkpoint_save_id"] = save.get("save_id")
            summary["checkpoint_description"] = save.get("description")
        elif call.name in {"run_command", "run_tests"}:
            summary["command"] = result.get("command")
            summary["cwd"] = result.get("cwd")
            summary["exit_code"] = result.get("exit_code")
            summary["approved"] = result.get("approved")
            summary["output_excerpt"] = str(result.get("output") or "")[:800]
        elif call.name == "read_file":
            summary["kind"] = result.get("kind")
            if result.get("kind") == "text":
                summary["excerpt"] = str(result.get("content") or "")[:400]
        elif call.name == "review_diff":
            summary["excerpt"] = str(result.get("diff") or "")[:800]
        elif call.name in {"edit_preview", "edit_apply"}:
            preview = dict(result.get("preview") or {})
            summary["diff_excerpt"] = str(preview.get("diff") or "")[:800]
            summary["changed"] = preview.get("changed")
        receipt = self._safe_action_receipt(result)
        if receipt is not None:
            summary["action_receipt"] = receipt
        return {
            "type": "dynamicToolCall",
            "id": f"tool-{call.id}",
            "namespace": "astrabridge_native",
            "tool": call.name,
            "status": "repairable" if result.get("repairable") else "completed",
            "success": bool(result.get("ok", True)),
            "arguments": redact_sensitive(arguments),
            "codingEventPayload": redact_sensitive(summary),
            "contentItems": [
                {
                    "type": "inputText",
                    "text": f"AstraBridge native tool result for {call.name}:\n{json.dumps(redact_sensitive(summary), ensure_ascii=False)}",
                }
            ],
        }

    def _safe_action_receipt(self, result: dict[str, Any]) -> dict[str, Any] | None:
        receipt = result.get("action_receipt")
        if not isinstance(receipt, dict):
            return None
        return {
            "receipt_id": receipt.get("receipt_id"),
            "idempotency_key": receipt.get("idempotency_key"),
            "state": receipt.get("state"),
            "outcome": receipt.get("outcome"),
            "recovery_required": bool(receipt.get("recovery_required")),
        }

    def _extra_items_for_result(self, call: ToolCall, result: dict[str, Any]) -> list[dict[str, Any]]:
        if call.name not in {"edit_preview", "edit_apply"}:
            if call.name in {"run_command", "run_tests"}:
                if result.get("repairable"):
                    return []
                return [
                    {
                        "type": "commandExecution",
                        "id": f"cmd-{call.id}",
                        "command": str(result.get("command") or ""),
                        "status": str(result.get("status") or ("completed" if result.get("ok") else "failed")),
                        "exitCode": result.get("exit_code"),
                        "aggregatedOutput": str(result.get("output") or ""),
                    }
                ]
            return []
        preview = dict(result.get("preview") or {})
        path = str(preview.get("path") or result.get("path") or "").strip()
        if not path or not preview.get("changed"):
            return []
        return [
            {
                "type": "fileChange",
                "id": f"file-{call.id}",
                "status": "completed",
                "changes": [
                    {
                        "path": path,
                        "kind": {"type": "update"},
                        "diff": preview.get("diff") or "",
                    }
                ],
            }
        ]

    def _truncate_payload(self, value: Any, *, string_limit: int = 4000, list_limit: int = 40) -> Any:
        if isinstance(value, str):
            return value[:string_limit]
        if isinstance(value, list):
            return [self._truncate_payload(item, string_limit=string_limit, list_limit=list_limit) for item in value[:list_limit]]
        if isinstance(value, dict):
            return {str(key): self._truncate_payload(item, string_limit=string_limit, list_limit=list_limit) for key, item in list(value.items())[:80]}
        return value


class NativeCodingTurnLoop:
    def __init__(self, runtime: Any, router: Any, project_tools: Any) -> None:
        self._runtime = runtime
        self._router = router
        self._project_tools = project_tools

    def run_turn(
        self,
        *,
        thread_id: str,
        profile: dict[str, Any],
        text: str,
        attachments: list[dict[str, Any]],
        model: str | None,
        effort: str | None,
        permission_mode: str,
        collaboration_mode: str | None,
        context_mode: str,
        prepared_inputs: list[dict[str, Any]] | None = None,
    ) -> NativeTurnResult:
        provider_id = str(profile.get("provider_id") or "openai").strip() or "openai"
        model_id = str(model or profile.get("model") or "").strip()
        profile_id = str(profile.get("profile_id") or "").strip()
        model_record = self._project_tools.resolve_model_record(provider_id, model_id, target_exists=False)
        authority = assess_model_authority(model_record)
        if authority.tier == "D":
            raise ValueError("The selected model is not eligible for native kernel execution.")
        turn_id = new_id("turn")
        output_limit = tool_output_char_limit(model_record.get("tool_output_token_limit"), default=20000)
        facade = RuntimeToolFacade(
            self._project_tools,
            profile_id=profile_id,
            provider_id=provider_id,
            model_id=model_id,
            authority=authority,
            permission_mode=permission_mode,
            thread_id=thread_id,
            turn_id=turn_id,
            tool_output_char_limit=output_limit,
        )
        started_at = int(__import__("time").time() * 1000)
        existing_thread = dict(self._runtime._read_native_thread(thread_id) or {})  # noqa: SLF001
        history = list(existing_thread.get("native_history") or [])
        user_inputs = list(prepared_inputs) if prepared_inputs is not None else self._runtime._build_user_inputs(  # noqa: SLF001
            text,
            attachments,
            thread_id=thread_id,
            context_mode=context_mode,
            profile_id=profile_id,
            provider_id=provider_id,
            model_id=model_id,
        )
        turn_items: list[dict[str, Any]] = [self._user_message_item(turn_id, text, attachments)]
        working_history = [*history, *user_inputs]
        response: NormalizedResponse | None = None

        for _round in range(MAX_NATIVE_TOOL_ROUNDS):
            result = self._router.complete_response(
                {
                    "model": f"{provider_id}/{model_id}",
                    "instructions": NATIVE_KERNEL_SYSTEM_PROMPT,
                    "input": working_history,
                    "tools": facade.tool_definitions(),
                    "stream": False,
                }
            )
            response = result["normalized"]
            if response.reasoning_summary:
                turn_items.append(
                    {
                        "type": "reasoning",
                        "id": f"{turn_id}-reasoning-{len(turn_items)}",
                        "summary": [response.reasoning_summary],
                        "content": [response.reasoning_summary],
                    }
                )
            if not response.tool_calls:
                break
            working_history.append(self._assistant_tool_call_message(response))
            for call in response.tool_calls:
                arguments, tool_result, extra_items, tool_item = facade.execute(call)
                turn_items.append(tool_item)
                turn_items.extend(extra_items)
                working_history.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.id,
                        "content": facade.tool_result_message(call.name, tool_result),
                    }
                )
        if response is None:
            raise RuntimeError("Native kernel did not receive a provider response.")
        final_text = str(response.text or "").strip() or str(response.reasoning_summary or "").strip()
        if not final_text:
            final_text = "The native kernel completed tool work but did not receive a final assistant message."
        turn_items.append({"type": "agentMessage", "id": f"{turn_id}-assistant", "text": final_text})
        working_history.append(
            {
                "role": "assistant",
                "content": final_text,
                **({"reasoning_content": response.reasoning_summary} if response.reasoning_summary else {}),
            }
        )
        turn = {
            "id": turn_id,
            "status": "completed",
            "startedAt": started_at,
            "completedAt": int(__import__("time").time() * 1000),
            "source_thread_id": thread_id,
            "profile_id": profile_id,
            "provider_id": provider_id,
            "model": model_id,
            "reasoning_effort": str(effort or profile.get("reasoning_effort") or "").strip() or None,
            "items": turn_items,
        }
        turns = [dict(item) for item in list(existing_thread.get("turns") or [])]
        turns.append(turn)
        thread = {
            "id": thread_id,
            "sessionId": thread_id,
            "name": existing_thread.get("name") or f"{provider_id}:{model_id}",
            "preview": final_text[:200],
            "status": {"type": "idle"},
            "cwd": self._runtime._runtime_workspace_root(),  # noqa: SLF001
            "turns": turns[-80:],
            "native_history": working_history[-120:],
        }
        cache_patch = {
            "name": thread.get("name"),
            "profile_id": profile_id,
            "provider_id": provider_id,
            "model": model_id,
            "reasoning_effort": str(effort or profile.get("reasoning_effort") or "").strip() or None,
            "permission_mode": permission_mode,
            "collaboration_mode": collaboration_mode or "default",
            "execution_backend": "native_kernel",
            "thread": thread,
            "status": {"type": "idle"},
            "updated_at": now_iso(),
        }
        return NativeTurnResult(turn={"id": turn_id, "status": "completed"}, thread=thread, thread_cache_patch=cache_patch)

    def _assistant_tool_call_message(self, response: NormalizedResponse) -> dict[str, Any]:
        return {
            "role": "assistant",
            "content": response.text or "",
            **({"reasoning_content": response.reasoning_summary} if response.reasoning_summary else {}),
            "tool_calls": [
                {
                    "id": call.id,
                    "type": "function",
                    "function": {
                        "name": call.name,
                        "arguments": call.arguments_json,
                    },
                }
                for call in response.tool_calls
            ],
        }

    def _user_message_item(self, turn_id: str, text: str, attachments: list[dict[str, Any]]) -> dict[str, Any]:
        content: list[dict[str, Any]] = [{"type": "text", "text": text}]
        for attachment in attachments:
            name = str(attachment.get("name") or attachment.get("path") or attachment.get("id") or "attachment")
            kind = str(attachment.get("kind") or "file")
            if kind == "image":
                content.append({"type": "localImage", "path": str(attachment.get("path") or name)})
            else:
                content.append({"type": "file", "name": name})
        return {"type": "userMessage", "id": f"{turn_id}-user", "content": content}
