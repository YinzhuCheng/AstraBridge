from __future__ import annotations

import base64
import hashlib
import json
import mimetypes
import os
import subprocess
from pathlib import Path
from typing import Any

from .common import WORKSPACE_STATE_DIRNAME, new_id, now_iso, path_for_host
from .coding_kernel import (
    EditExecutor,
    available_operations_for_request,
    edit_operation_to_coding_event,
    request_from_payload,
    select_edit_strategy,
)
from .providers import get_provider_profile
from .providers.ir import NormalizedResponse, ToolCall
from .security import classify_command, redact_sensitive, resolve_under
from .tool_action_ledger import (
    ToolActionReceiptLedger,
    reject_unvalidated_raw_wrapper,
    validate_side_effect_arguments,
)


TEXT_EXTENSIONS = {
    ".css",
    ".diff",
    ".html",
    ".js",
    ".json",
    ".jsonl",
    ".jsx",
    ".log",
    ".md",
    ".mdx",
    ".mjs",
    ".patch",
    ".py",
    ".rst",
    ".toml",
    ".ts",
    ".tsx",
    ".txt",
    ".yaml",
    ".yml",
}
MARKDOWN_EXTENSIONS = {".md", ".markdown", ".mdx"}
JSON_EXTENSIONS = {".json", ".jsonl"}
IMAGE_EXTENSIONS = {".bmp", ".gif", ".jpeg", ".jpg", ".png", ".svg", ".webp"}
PDF_EXTENSIONS = {".pdf"}
AUDIO_EXTENSIONS = {".aac", ".flac", ".m4a", ".mp3", ".oga", ".ogg", ".wav", ".webm"}
VIDEO_EXTENSIONS = {".avi", ".m4v", ".mkv", ".mov", ".mp4", ".mpeg", ".mpg", ".ogv", ".webm"}
SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".agents",
    ".codex",
    ".cache",
    ".pytest_cache",
    ".ruff_cache",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
    "target",
}
MANAGED_STATE_PREVIEW_ALLOWLIST = {"artifacts", "assets", "capabilities", "captures", "exports", "reports", "reviews", "saves"}
SECRET_NAME_PARTS = ("secret", "token", "apikey", "api_key", "authorization", "cookie", "password", ".env")
MAX_TEXT_BYTES = 1_000_000
MAX_IMAGE_BYTES = 2_500_000
MAX_MEDIA_BYTES = 50_000_000
MAX_TREE_ITEMS = 500
RELEASE_DEMO_COMMAND = "python scorecard.py --checks checks.json"
RELEASE_DEMO_REVIEW_ARTIFACT = f"{WORKSPACE_STATE_DIRNAME}/reviews/release-workflow-demo.diff"
NATIVE_KERNEL_DEMO_TEST_COMMAND = "python -m unittest -q test_native_kernel_demo"


class ProjectToolsService:
    """Bounded project tools for the inspector and coding workflow surfaces.

    This intentionally exposes summaries, bounded previews, and guarded edit
    operations rather than raw project logs. The UI can inspect useful
    workspace state without creating a second uncontrolled file/terminal
    surface.
    """

    def __init__(self, projects, runtime, *, checkpoints=None, tasks=None, profiles=None, router_config=None, task_conversation=None) -> None:
        self._projects = projects
        self._runtime = runtime
        self._checkpoints = checkpoints
        self._tasks = tasks
        self._profiles = profiles
        self._router_config = router_config
        self._task_conversation = task_conversation
        self._tool_action_ledgers: dict[str, ToolActionReceiptLedger] = {}

    def review_status(self) -> dict[str, Any]:
        root = self._workspace_root()
        git = self._git_summary(root)
        files = git.get("files") or self._recent_files(root)
        return {
            "workspace_root": str(root),
            "git": {key: value for key, value in git.items() if key != "files"},
            "files": files[:80],
            "updated_at": now_iso(),
        }

    def review_diff(self, rel_path: str | None = None) -> dict[str, Any]:
        root = self._workspace_root()
        if rel_path:
            target = self._safe_rel_path(root, rel_path, allow_managed_state=False)
            display_path = target.relative_to(root).as_posix()
            args = ["git", "-C", str(root), "diff", "--", display_path]
        else:
            args = ["git", "-C", str(root), "diff", "--stat", "--", "."]
        result = self._run(args, timeout=10)
        if result["ok"]:
            diff = str(result["stdout"] or "")
            if rel_path and not diff.strip():
                synthetic = self._synthetic_file_diff(root, target)
                if synthetic:
                    return {"ok": True, "path": rel_path or "", "diff": synthetic[:120_000], "truncated": len(synthetic) > 120_000, "synthetic": True}
            return {"ok": True, "path": rel_path or "", "diff": diff[:120_000], "truncated": len(diff) > 120_000}
        if rel_path:
            synthetic = self._synthetic_file_diff(root, target)
            if synthetic:
                return {"ok": True, "path": rel_path or "", "diff": synthetic[:120_000], "truncated": len(synthetic) > 120_000, "synthetic": True}
        return {"ok": False, "path": rel_path or "", "diff": "", "error": result["stderr"] or result["error"]}

    def files_tree(self, query: str | None = None, limit: int = MAX_TREE_ITEMS) -> dict[str, Any]:
        root = self._workspace_root()
        query_text = (query or "").strip().lower()
        items: list[dict[str, Any]] = []
        limit = max(50, min(int(limit or MAX_TREE_ITEMS), 1000))
        for current, dirs, files in os.walk(root):
            current_path = Path(current)
            rel_dir = current_path.relative_to(root)
            dirs[:] = [name for name in sorted(dirs) if not self._skip_dir(rel_dir / name)]
            for name in sorted(files):
                rel = rel_dir / name
                rel_text = rel.as_posix()
                if self._skip_file(rel):
                    continue
                if query_text and query_text not in rel_text.lower():
                    continue
                path = current_path / name
                try:
                    stat = path.stat()
                except OSError:
                    continue
                items.append(
                    {
                        "path": rel_text,
                        "name": name,
                        "kind": self._file_kind(path),
                        "size": stat.st_size,
                        "updated_at": stat.st_mtime,
                    }
                )
                if len(items) >= limit:
                    return {"workspace_root": str(root), "filter_version": "preview-artifacts-v2", "items": items, "truncated": True, "updated_at": now_iso()}
        return {"workspace_root": str(root), "filter_version": "preview-artifacts-v2", "items": items, "truncated": False, "updated_at": now_iso()}

    def read_file(self, rel_path: str) -> dict[str, Any]:
        root = self._workspace_root()
        path = self._safe_rel_path(root, rel_path, allow_managed_state=True)
        stat = path.stat()
        kind = self._file_kind(path)
        payload: dict[str, Any] = {
            "path": path.relative_to(root).as_posix(),
            "name": path.name,
            "kind": kind,
            "size": stat.st_size,
            "updated_at": stat.st_mtime,
        }
        if kind in {"text", "markdown", "json"}:
            if stat.st_size > MAX_TEXT_BYTES:
                return {**payload, "kind": "too_large", "message": f"Text preview is limited to {MAX_TEXT_BYTES} bytes."}
            payload["mime_type"] = mimetypes.guess_type(path.name)[0] or "text/plain"
            payload["content"] = path.read_text(encoding="utf-8-sig", errors="replace")
            return payload
        if kind == "image":
            if stat.st_size > MAX_IMAGE_BYTES:
                return {**payload, "kind": "too_large", "message": f"Image preview is limited to {MAX_IMAGE_BYTES} bytes."}
            mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            payload["mime_type"] = mime
            payload["data_url"] = f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode('ascii')}"
            return payload
        if kind in {"pdf", "audio", "video"}:
            if stat.st_size > MAX_MEDIA_BYTES:
                return {**payload, "kind": "too_large", "message": f"Media preview is limited to {MAX_MEDIA_BYTES} bytes."}
            payload["mime_type"] = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            return payload
        return {**payload, "message": "Binary preview is not supported yet."}

    def file_media(self, rel_path: str) -> dict[str, Any]:
        root = self._workspace_root()
        path = self._safe_rel_path(root, rel_path, allow_managed_state=True)
        stat = path.stat()
        if stat.st_size > MAX_MEDIA_BYTES:
            raise ValueError(f"Media preview is limited to {MAX_MEDIA_BYTES} bytes.")
        return {
            "path": path,
            "name": path.name,
            "mime_type": mimetypes.guess_type(path.name)[0] or "application/octet-stream",
            "size": stat.st_size,
            "updated_at": stat.st_mtime,
        }

    def terminal_history(self, limit: int = 30) -> dict[str, Any]:
        root = self._workspace_root()
        events = self._runtime.list_events(after=0, limit=250).get("events") or []
        commands: list[dict[str, Any]] = []
        for event in reversed(events):
            command = self._extract_command(event)
            if not command:
                continue
            commands.append(
                {
                    "timestamp": event.get("timestamp"),
                    "status": self._extract_status(event),
                    "command": command[:600],
                    "summary": " ".join(command.split())[:180],
                }
            )
            if len(commands) >= limit:
                break
        return {
            "workspace_root": str(root),
            "execution_host": (self._projects.current_project or {}).get("ui_preferences", {}).get("execution_host", "unknown"),
            "commands": list(reversed(commands)),
            "updated_at": now_iso(),
        }

    def list_checkpoints(self, limit: int = 20) -> dict[str, Any]:
        if self._checkpoints is None:
            return {"saves": [], "saves_root": "", "available": False}
        response = dict(self._checkpoints.list_saves() or {})
        saves = list(response.get("saves") or [])
        bounded_limit = max(1, min(int(limit or 20), 100))
        response["saves"] = saves[:bounded_limit]
        response["available"] = True
        response["truncated"] = len(saves) > bounded_limit
        response["updated_at"] = now_iso()
        return response

    def create_checkpoint(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        if self._checkpoints is None:
            raise ValueError("Checkpoint service is not available.")
        request = self._materialize_tool_action_payload(dict(payload or {}))
        root = self._workspace_root()
        context = self._edit_context(request, target_exists=False)
        action_arguments = self._side_effect_arguments("create_checkpoint", request)
        ledger, envelope, authorized, authorization_reason = self._tool_action_envelope(
            root=root,
            tool_name="create_checkpoint",
            action_arguments=action_arguments,
            payload=request,
            context=context,
        )
        if not authorized:
            receipt = ledger.record_terminal(envelope, reason=authorization_reason)
            return self._blocked_tool_action_result(authorization_reason, receipt)
        admission = ledger.admit(envelope)
        if admission["decision"] != "execute":
            return self._checkpoint_receipt_result(admission)
        thread_name = "Current thread"
        if self._tasks is not None:
            active = self._tasks.active_provider_thread(include_missing_fallback=True) or {}
            thread_name = str(active.get("name") or "").strip() or thread_name
        save_payload = {
            "thread_id": context.get("execution_thread_id"),
            "thread_name": request.get("thread_name") or thread_name,
            "description": request.get("description") or "",
            "provider": context.get("provider_id") or "",
            "model": context.get("model_id") or "",
        }
        try:
            response = self._checkpoints.create(save_payload, system=bool(request.get("system")))
            manifest = (response.get("save") or response.get("manifest") or response) if isinstance(response, dict) else {}
            if isinstance(manifest, dict) and self._tasks is not None:
                try:
                    self._tasks.record_checkpoint(manifest)
                    self._tasks.record_coding_events(
                        [
                            {
                                "event_id": f"checkpoint:{manifest.get('save_id') or 'unknown'}",
                                "task_id": context.get("task_id"),
                                "visible_thread_id": context.get("visible_thread_id"),
                                "execution_thread_id": context.get("execution_thread_id"),
                                "provider_id": context.get("provider_id"),
                                "model_id": context.get("model_id"),
                                "event_type": "checkpoint_created",
                                "timestamp": manifest.get("created_at") or now_iso(),
                                "payload": {
                                    "save_id": manifest.get("save_id"),
                                    "description": manifest.get("description") or manifest.get("default_description"),
                                },
                                "redaction_status": "secret_free",
                                "source": "sidecar",
                            }
                        ]
                    )
                except Exception:
                    pass
            result = {
                "ok": True,
                "status": "completed",
                "applied": True,
                "checkpoint_save_id": (manifest.get("save_id") if isinstance(manifest, dict) else None),
            }
            receipt = ledger.complete(envelope, result=result)
            output = dict(response) if isinstance(response, dict) else {"save": manifest}
            output.update({"ok": True, "status": "completed", "action_receipt": receipt})
            return output
        except Exception:
            ledger.interrupt(
                envelope,
                reason="Checkpoint creation was interrupted after action admission; effect status is unknown.",
            )
            raise

    def prepare_release_workflow_demo(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        root = self._workspace_root()
        self._require_isolated_demo_workspace(root)
        payload = dict(payload or {})
        context = self._edit_context(payload, target_exists=False)

        baseline_files = self._release_demo_baseline_files()
        for rel_path, content in baseline_files.items():
            target = root / rel_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        scorecard_path = root / "scorecard.py"
        if not scorecard_path.exists():
            scorecard_path.write_text(self._release_demo_scorecard_source(), encoding="utf-8")
        tests_path = root / "test_scorecard.py"
        if not tests_path.exists():
            tests_path.write_text(self._release_demo_test_source(), encoding="utf-8")

        baseline_commit = self._ensure_release_demo_git_baseline(root)

        failing_checks = [
            {"id": "build", "label": "Desktop build", "status": "pass", "notes": "Vite build completed"},
            {"id": "sidecar", "label": "Sidecar tests", "status": "pass", "notes": "unittest suite completed"},
            {"id": "browser", "label": "Browser smoke", "status": "fail", "notes": "needs provider switch acceptance"},
        ]
        passing_checks = [
            {"id": "build", "label": "Desktop build", "status": "pass", "notes": "Vite build completed"},
            {"id": "sidecar", "label": "Sidecar tests", "status": "pass", "notes": "unittest suite completed"},
            {"id": "browser", "label": "Browser smoke", "status": "pass", "notes": "provider switch acceptance captured"},
            {"id": "recovery", "label": "Recovery path", "status": "pass", "notes": "failure reproduced and recovered in the same task"},
        ]
        checks_path = root / "checks.json"
        checks_path.write_text(json.dumps(failing_checks, indent=2) + "\n", encoding="utf-8")
        failed_run = self.run_command({"command": RELEASE_DEMO_COMMAND, "permission_mode": "full"})
        checks_path.write_text(json.dumps(passing_checks, indent=2) + "\n", encoding="utf-8")

        readme_path = root / "README.md"
        readme_path.write_text(self._release_demo_readme_after_recovery(), encoding="utf-8")
        workflow_note_path = root / "workflow_note.txt"
        workflow_note_path.write_text("Recovery verified and ready for browser smoke.\n", encoding="utf-8")

        recovered_run = self.run_command({"command": RELEASE_DEMO_COMMAND, "permission_mode": "full"})
        checkpoint_response = self.create_checkpoint(
            {
                "description": "Release workflow demo checkpoint after recovery verification",
                "system": True,
            }
        )
        review_status = self.review_status()
        full_diff = self._full_git_diff(root)
        review_artifact = self._write_release_demo_review_artifact(root, full_diff)
        files_tree = self.files_tree(limit=40)
        checkpoints = self.list_checkpoints(limit=10)

        changed_paths = [str(item.get("path") or "").strip() for item in list(review_status.get("files") or []) if str(item.get("path") or "").strip()]
        provider_switch_summary = None
        if self._tasks is not None:
            self._tasks.record_coding_events(
                [
                    self._release_demo_command_event(context, failed_run, event_id="release-demo-command-failed"),
                    self._release_demo_command_event(context, recovered_run, event_id="release-demo-command-recovered"),
                    self._release_demo_verification_event(
                        context,
                        event_id="release-demo-review-status",
                        tool="review_status",
                        files=changed_paths[:6],
                    ),
                    self._release_demo_verification_event(
                        context,
                        event_id="release-demo-review-diff",
                        tool="review_diff",
                        path=changed_paths[0] if changed_paths else "checks.json",
                        review_diff_path=review_artifact,
                        files=changed_paths[:6],
                    ),
                    self._release_demo_verification_event(
                        context,
                        event_id="release-demo-files-tree",
                        tool="files_tree",
                        paths=[str(item.get("path") or "").strip() for item in list(files_tree.get("items") or [])[:6] if str(item.get("path") or "").strip()],
                    ),
                    self._release_demo_verification_event(
                        context,
                        event_id="release-demo-list-checkpoints",
                        tool="list_checkpoints",
                        save_ids=[str(item.get("save_id") or "").strip() for item in list(checkpoints.get("saves") or [])[:6] if str(item.get("save_id") or "").strip()],
                    ),
                    self._release_demo_runtime_transition_event(
                        context,
                        event_id="release-demo-recovery-verified",
                        transition="recovery_verified",
                    ),
                ]
            )
            provider_switch_summary = self._prepare_release_demo_provider_switch(
                failed_run=failed_run,
                recovered_run=recovered_run,
            )
            self._projects.reconcile_task_projection(self._tasks.current_task())

        return {
            "ok": True,
            "workspace_root": str(root),
            "task": self._tasks.current_task() if self._tasks is not None else None,
            "review_status": review_status,
            "terminal_history": self.terminal_history(limit=12),
            "checkpoints": checkpoints,
            "baseline_commit": baseline_commit,
            "review_artifact": review_artifact,
            "failed_run": failed_run,
            "recovered_run": recovered_run,
            "provider_switch": provider_switch_summary,
            "provider_switch_present": bool((self._tasks.current_task() or {}).get("handoff_events")) if self._tasks is not None else False,
            "updated_at": now_iso(),
        }

    def prepare_native_kernel_workflow_demo(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        root = self._workspace_root()
        self._require_isolated_demo_workspace(root)
        if self._tasks is None or self._profiles is None:
            raise RuntimeError("Native kernel demo requires task and profile services.")
        payload = dict(payload or {})
        profile = self._resolve_profile(payload)
        profile_id = str(payload.get("profile_id") or profile.get("profile_id") or "").strip() or "deepseek-default"
        provider_id = str(payload.get("provider_id") or profile.get("provider_id") or "").strip() or "deepseek"
        model_id = str(payload.get("model") or payload.get("model_id") or profile.get("model") or "").strip() or "deepseek-v4-pro"
        reasoning_effort = str(payload.get("effort") or payload.get("reasoning_effort") or profile.get("reasoning_effort") or "high").strip() or "high"
        permission_mode = str(payload.get("permission_mode") or profile.get("permission_mode") or "auto").strip() or "auto"
        collaboration_mode = str(payload.get("collaboration_mode") or profile.get("collaboration_mode") or "default").strip() or "default"

        readme = (
            "# AstraBridge Native Kernel Demo\n\n"
            "This workspace is used for the AstraBridge native-kernel constrained coding demo.\n\n"
            "It proves one local read/edit/test/checkpoint workflow without using the Codex app-server thread path.\n"
        )
        (root / "README.md").write_text(readme, encoding="utf-8")
        (root / "native_kernel_scorecard.py").write_text(
            "def status():\n"
            "    return 'draft'\n",
            encoding="utf-8",
        )
        (root / "test_native_kernel_demo.py").write_text(
            "import unittest\n"
            "from native_kernel_scorecard import status\n\n"
            "class NativeKernelScorecardTest(unittest.TestCase):\n"
            "    def test_status_ready(self):\n"
            "        self.assertEqual(status(), 'ready')\n\n"
            "if __name__ == '__main__':\n"
            "    unittest.main()\n",
            encoding="utf-8",
        )
        baseline_commit = self._ensure_release_demo_git_baseline(root)
        native_thread_id = "native-kernel-demo-thread"
        native_settings = {
            "profile_id": profile_id,
            "provider_id": provider_id,
            "model": model_id,
            "reasoning_effort": reasoning_effort,
            "permission_mode": permission_mode,
            "collaboration_mode": collaboration_mode,
            "execution_backend": "native_kernel",
            "name": "Native kernel demo lane",
        }
        task = self._tasks.ensure_default_task(thread_id=native_thread_id, settings=native_settings, title="Native kernel demo")
        if self._router_config is not None:
            model_record = self._resolve_model_record(provider_id, model_id, target_exists=True)
            self._router_config.upsert_model(
                {
                    **model_record,
                    "id": f"{provider_id}/{model_id}",
                    "provider": provider_id,
                    "native_model": model_id,
                    "display_name": str(model_record.get("display_name") or model_record.get("native_model") or model_id),
                    "supports_tool_calls": True,
                    "apply_patch_tool_type": "json",
                    "supports_mcp_tools": bool(model_record.get("supports_mcp_tools", True)),
                    "mcp_tool_call_policy": "conservative",
                    "tool_mode": "full",
                    "codex_agent_enabled": True,
                    "authority_tier": str(model_record.get("authority_tier") or "B"),
                }
            )

        class _NativeKernelDemoRouter:
            def __init__(self, demo_provider_id: str, demo_model_id: str) -> None:
                self.calls = 0
                self.provider_id = demo_provider_id
                self.model_id = demo_model_id

            def complete_response(self, payload: dict[str, object]) -> dict[str, object]:
                self.calls += 1
                if self.calls == 1:
                    return {
                        "profile": {"provider_id": self.provider_id, "model": self.model_id},
                        "adapter": "chat_completions",
                        "normalized": NormalizedResponse(
                            text="",
                            reasoning_summary="Inspect the demo file, apply the smallest safe edit, verify the test, and checkpoint the result.",
                            reasoning_state=None,
                            tool_calls=[
                                ToolCall(id="call-review", name="review_status", arguments_json="{}"),
                                ToolCall(id="call-read", name="read_file", arguments_json='{"path":"native_kernel_scorecard.py"}'),
                                ToolCall(
                                    id="call-edit",
                                    name="edit_apply",
                                    arguments_json='{"path":"native_kernel_scorecard.py","content":"def status():\\n    return \\"ready\\"\\n"}',
                                ),
                                ToolCall(
                                    id="call-tests",
                                    name="run_tests",
                                    arguments_json=json.dumps({"command": NATIVE_KERNEL_DEMO_TEST_COMMAND}),
                                ),
                                ToolCall(
                                    id="call-checkpoint",
                                    name="create_checkpoint",
                                    arguments_json='{"description":"Native kernel demo checkpoint"}',
                                ),
                                ToolCall(
                                    id="call-list-checkpoints",
                                    name="list_checkpoints",
                                    arguments_json='{"limit":5}',
                                ),
                            ],
                            usage=None,
                            finish_reason="tool_calls",
                        ),
                    }
                return {
                    "profile": {"provider_id": self.provider_id, "model": self.model_id},
                    "adapter": "chat_completions",
                    "normalized": NormalizedResponse(
                        text="Native kernel demo completed: reviewed the file, applied a small edit, ran the unit test, and created a checkpoint.",
                        reasoning_summary=None,
                        reasoning_state=None,
                        tool_calls=[],
                        usage=None,
                        finish_reason="stop",
                    ),
                }

        original_router = getattr(self._runtime, "_router", None)
        original_loop = getattr(self._runtime, "_native_turn_loop", None)
        flag_before = os.environ.get("ASTRABRIDGE_ENABLE_NATIVE_KERNEL")
        profile = self._profiles.resolve_runtime_profile(profile_id)
        try:
            os.environ["ASTRABRIDGE_ENABLE_NATIVE_KERNEL"] = "1"
            self._runtime._native_turn_loop = None  # type: ignore[attr-defined]
            self._runtime.attach_router(_NativeKernelDemoRouter(provider_id, model_id))
            turn_result = self._runtime.start_turn(
                profile,
                thread_id=native_thread_id,
                text="Review native_kernel_scorecard.py, apply the smallest safe fix, run the unit test, create a checkpoint, then summarize the result.",
                attachments=[],
                model=model_id,
                effort=reasoning_effort,
                permission_mode=permission_mode,
                collaboration_mode=collaboration_mode,
            )
        finally:
            if flag_before is None:
                os.environ.pop("ASTRABRIDGE_ENABLE_NATIVE_KERNEL", None)
            else:
                os.environ["ASTRABRIDGE_ENABLE_NATIVE_KERNEL"] = flag_before
            self._runtime._native_turn_loop = None  # type: ignore[attr-defined]
            if original_router is not None:
                self._runtime.attach_router(original_router)
            else:
                self._runtime._router = None  # type: ignore[attr-defined]
                self._runtime._native_turn_loop = original_loop  # type: ignore[attr-defined]

        thread = self._runtime.read_thread(profile, native_thread_id).get("thread") or {}
        review_status = self.review_status()
        terminal_history = self.terminal_history(limit=12)
        checkpoints = self.list_checkpoints(limit=10)
        self._projects.reconcile_task_projection(self._tasks.current_task())
        return {
            "ok": True,
            "workspace_root": str(root),
            "baseline_commit": baseline_commit,
            "thread_id": native_thread_id,
            "profile_id": profile_id,
            "provider_id": provider_id,
            "model_id": model_id,
            "turn": turn_result.get("turn"),
            "thread": thread,
            "task": self._tasks.current_task() or task,
            "execution_backend": "native_kernel",
            "review_status": review_status,
            "terminal_history": terminal_history,
            "checkpoints": checkpoints,
            "updated_at": now_iso(),
        }

    def run_command(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        return self._command_operation(payload or {}, test_mode=False)

    def run_tests(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        return self._command_operation(payload or {}, test_mode=True)

    def resolve_model_record(self, provider_id: str | None, model_id: str | None, *, target_exists: bool = False) -> dict[str, Any]:
        return self._resolve_model_record(provider_id, model_id, target_exists=target_exists)

    def edit_preview(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        return self._edit_operation(payload or {}, apply=False)

    def edit_apply(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        return self._edit_operation(payload or {}, apply=True)

    def _workspace_root(self) -> Path:
        return self._projects.require_workspace_root().resolve()

    def tool_action_receipt(self, idempotency_key: str) -> dict[str, Any] | None:
        """Return the durable, secret-free receipt for a side-effect action."""

        return self._tool_action_ledger(self._workspace_root()).receipt(idempotency_key)

    def tool_action_receipts_for_lineage(
        self,
        *,
        task_id: str | None = None,
        visible_thread_id: str | None = None,
        execution_thread_id: str | None = None,
        turn_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Expose the ledger's narrow retry/handoff admission view."""

        return self._tool_action_ledger(self._workspace_root()).receipt_references_for_lineage(
            task_id=task_id,
            visible_thread_id=visible_thread_id,
            execution_thread_id=execution_thread_id,
            turn_id=turn_id,
        )

    def resolve_tool_action_recovery(self, idempotency_key: str, *, resolution: str) -> dict[str, Any]:
        """Record an explicit recovery decision before replaying an interrupted action."""

        return self._tool_action_ledger(self._workspace_root()).resolve_recovery(
            idempotency_key,
            resolution=resolution,
        )

    def _side_effect_arguments(self, tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
        # Context fields such as profile, thread, and permission mode are
        # trusted service metadata, not executable tool arguments. Reject the
        # repair wrapper before selecting the strict action schema fields.
        reject_unvalidated_raw_wrapper(payload, tool_name=tool_name)
        fields_by_tool = {
            "create_checkpoint": ("description",),
            "edit_apply": ("path", "content", "search", "replace", "count", "edits", "operation"),
            "run_command": ("command", "cwd", "timeout_seconds"),
            "run_tests": ("command", "cwd", "timeout_seconds"),
        }
        fields = fields_by_tool.get(tool_name)
        if fields is None:
            raise ValueError(f"Unsupported side-effect tool: {tool_name}")
        arguments = {field: payload[field] for field in fields if field in payload}
        return validate_side_effect_arguments(tool_name, arguments)

    def _materialize_tool_action_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Give one direct request a stable local call id without mutating it."""

        request = dict(payload)
        if not str(request.get("tool_call_id") or request.get("call_id") or "").strip():
            request["tool_call_id"] = str(request.get("idempotency_key") or new_id("ui-action"))
        return request

    def _tool_action_ledger(self, root: Path) -> ToolActionReceiptLedger:
        key = str(root.resolve())
        ledger = self._tool_action_ledgers.get(key)
        if ledger is None:
            ledger = ToolActionReceiptLedger(root)
            self._tool_action_ledgers[key] = ledger
        return ledger

    def _tool_action_envelope(
        self,
        *,
        root: Path,
        tool_name: str,
        action_arguments: dict[str, Any],
        payload: dict[str, Any],
        context: dict[str, Any],
        authority_decision: str | None = None,
        authority_reason: str | None = None,
    ) -> tuple[ToolActionReceiptLedger, dict[str, Any], bool, str]:
        source = self._tool_action_source(payload)
        tier = str((context.get("model_record") or {}).get("authority_tier") or "unknown").strip().upper()
        tier = tier if tier in {"A", "B", "C", "D"} else "unknown"
        authorized = source != "native_model_tool" or tier == "A"
        denied_reason = "" if authorized else "Selected model lacks tier-A native tool authority."
        decision = authority_decision or ("native_tool_authorized" if source == "native_model_tool" else "user_direct_authorized")
        if not authorized:
            decision = "authority_denied"
        authority = {
            "tier": tier,
            "decision": decision,
            "permission_mode": context.get("permission_mode") or payload.get("permission_mode") or "auto",
            "reason": authority_reason or denied_reason or None,
        }
        ledger = self._tool_action_ledger(root)
        envelope = ledger.build_envelope(
            tool_name=tool_name,
            arguments=action_arguments,
            lineage=self._tool_action_lineage(payload, context),
            authority=authority,
            workspace=self._tool_action_workspace(root),
            idempotency_key=str(payload.get("idempotency_key") or "") or None,
            source=source,
        )
        return ledger, envelope, authorized, denied_reason

    def _tool_action_source(self, payload: dict[str, Any]) -> str:
        return "native_model_tool" if str(payload.get("action_source") or "").strip() == "native_model_tool" else "user_direct"

    def _tool_action_lineage(self, payload: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        tool_call_id = str(payload.get("tool_call_id") or payload.get("call_id") or "").strip()
        if not tool_call_id:
            # A direct user/API request is a new intent unless it supplies an
            # explicit idempotency key. Model calls always carry a call id.
            tool_call_id = str(payload.get("idempotency_key") or new_id("ui-action"))
        return {
            "task_id": context.get("task_id"),
            "visible_thread_id": context.get("visible_thread_id") or payload.get("thread_id"),
            "execution_thread_id": context.get("execution_thread_id") or payload.get("thread_id"),
            "turn_id": context.get("turn_id") or payload.get("turn_id"),
            "tool_call_id": tool_call_id,
        }

    def _tool_action_workspace(self, root: Path) -> dict[str, Any]:
        head = self._run(["git", "-C", str(root), "rev-parse", "HEAD"], timeout=5)
        status = self._run(
            ["git", "-C", str(root), "status", "--porcelain=v1", "--untracked-files=all", "--", "."],
            timeout=8,
        )
        # Git output can include file names. Keep only a digest in the receipt.
        workspace_basis = "\n".join(
            [
                str(head.get("stdout") or "").strip(),
                str(status.get("stdout") or ""),
                "head-ok" if head.get("ok") else "head-unavailable",
                "status-ok" if status.get("ok") else "status-unavailable",
            ]
        )
        checkpoint_version = "none"
        if self._checkpoints is not None:
            try:
                saves = list((self._checkpoints.list_saves() or {}).get("saves") or [])
                checkpoint_version = str((saves[0] or {}).get("save_id") or "none") if saves else "none"
            except Exception:
                checkpoint_version = "unavailable"
        return {
            "workspace_version": hashlib.sha256(workspace_basis.encode("utf-8")).hexdigest(),
            "checkpoint_version": checkpoint_version,
        }

    def _blocked_tool_action_result(self, reason: str, receipt: dict[str, Any]) -> dict[str, Any]:
        return {
            "ok": False,
            "status": "blocked",
            "error": reason,
            "tool_event_verified": True,
            "action_receipt": receipt,
        }

    def _admitted_receipt_result(self, admission: dict[str, Any], *, base: dict[str, Any]) -> dict[str, Any]:
        decision = str(admission.get("decision") or "")
        receipt = dict(admission.get("receipt") or {})
        if decision == "recovery_required":
            return {
                **base,
                "ok": False,
                "status": "recovery_required",
                "error": "The previous action outcome is unknown. Resolve its receipt before retrying.",
                "already_executed": False,
                "tool_event_verified": True,
                "action_receipt": receipt,
            }
        result = dict(receipt.get("result") or {})
        return {
            **base,
            "ok": bool(result.get("ok")),
            "status": "duplicate",
            "already_executed": True,
            "tool_event_verified": True,
            "action_receipt": receipt,
            "receipt_result": result,
        }

    def _checkpoint_receipt_result(self, admission: dict[str, Any]) -> dict[str, Any]:
        receipt = dict(admission.get("receipt") or {})
        result = dict(receipt.get("result") or {})
        checkpoint_save_id = result.get("checkpoint_save_id")
        base = {
            "save": {"save_id": checkpoint_save_id} if checkpoint_save_id else {},
            "path": None,
        }
        return self._admitted_receipt_result(admission, base=base)

    def _edit_receipt_result(self, admission: dict[str, Any], *, prepared, decision, executor: EditExecutor) -> dict[str, Any]:
        receipt = dict(admission.get("receipt") or {})
        receipt_result = dict(receipt.get("result") or {})
        checkpoint_save_id = receipt_result.get("checkpoint_save_id")
        base = {
            "mode": "apply",
            "applied": bool(receipt_result.get("applied")),
            "no_op": not bool(receipt_result.get("applied")),
            "path": prepared.relative_path,
            "strategy": decision.to_dict(),
            "preview": prepared.preview_payload(),
            "checkpoint": {"save_id": checkpoint_save_id} if checkpoint_save_id else None,
            "verification": executor.verification_hook(prepared),
        }
        return self._admitted_receipt_result(admission, base=base)

    def _edit_operation(self, payload: dict[str, Any], *, apply: bool) -> dict[str, Any]:
        if apply:
            payload = self._materialize_tool_action_payload(payload)
        root = self._workspace_root()
        action_arguments = self._side_effect_arguments("edit_apply", payload) if apply else None
        request = request_from_payload(payload)
        executor = EditExecutor(root)
        target_exists = executor.target_exists(request.path)
        available_operations = available_operations_for_request(request, target_exists=target_exists)
        context = self._edit_context(payload, target_exists=target_exists)
        estimated_bytes = self._estimate_edit_bytes(request)
        decision = select_edit_strategy(
            model=context["model_record"],
            requested_operation=payload.get("operation"),
            available_operations=available_operations,
            target_exists=target_exists,
            estimated_bytes=estimated_bytes,
            edit_count=len(request.edits),
            profile_id=context["profile_id"],
            provider_id=context["provider_id"],
            model_id=context["model_id"],
        )
        prepared = executor.prepare(request, operation=decision.selected_operation)
        checkpoint = None
        applied = False
        ledger = None
        envelope = None
        if apply:
            ledger, envelope, authorized, authorization_reason = self._tool_action_envelope(
                root=root,
                tool_name="edit_apply",
                action_arguments=action_arguments or {},
                payload=payload,
                context=context,
            )
            if not authorized:
                receipt = ledger.record_terminal(envelope, reason=authorization_reason)
                return {
                    **self._blocked_tool_action_result(authorization_reason, receipt),
                    "mode": "apply",
                    "applied": False,
                    "no_op": not prepared.changed,
                    "path": prepared.relative_path,
                    "strategy": decision.to_dict(),
                    "preview": prepared.preview_payload(),
                    "checkpoint": None,
                    "verification": executor.verification_hook(prepared),
                }
            admission = ledger.admit(envelope)
            if admission["decision"] != "execute":
                return self._edit_receipt_result(admission, prepared=prepared, decision=decision, executor=executor)
            try:
                if prepared.changed and decision.selected_operation != "propose_only":
                    checkpoint = self._create_edit_checkpoint(prepared, context)
                    executor.apply(prepared)
                    applied = True
            except Exception:
                ledger.interrupt(envelope, reason="Edit application was interrupted after action admission; effect status is unknown.")
                raise
        verification = executor.verification_hook(prepared, checkpoint=checkpoint)
        event_payload = {
            "event_id": f"edit:{hashlib.sha1(f'{prepared.relative_path}:{prepared.operation}:{prepared.changed}:{prepared.added_lines}:{prepared.removed_lines}'.encode('utf-8')).hexdigest()[:16]}",
            "timestamp": now_iso(),
            "path": prepared.relative_path,
            "requested_operation": decision.requested_operation,
            "policy_operation": decision.policy_operation,
            "selected_operation": decision.selected_operation,
            "size_class": decision.size_class,
            "authority_tier": decision.authority_tier,
            "changed": prepared.changed,
            "applied": applied,
            "checkpoint_save_id": ((checkpoint or {}).get("save") or {}).get("save_id"),
            "verification": verification,
            "added_lines": prepared.added_lines,
            "removed_lines": prepared.removed_lines,
            "reason": decision.reason,
        }
        event = edit_operation_to_coding_event(
            task_id=context["task_id"],
            visible_thread_id=context["visible_thread_id"],
            execution_thread_id=context["execution_thread_id"],
            provider_id=context["provider_id"],
            model_id=context["model_id"],
            operation=event_payload,
        )
        if self._tasks is not None:
            try:
                self._tasks.record_coding_events([event])
            except Exception:
                pass
        if apply and applied:
            self._record_edit_event(event)
        result = {
            "ok": True,
            "mode": "apply" if apply else "preview",
            "applied": applied,
            "no_op": not prepared.changed,
            "path": prepared.relative_path,
            "strategy": decision.to_dict(),
            "preview": prepared.preview_payload(),
            "checkpoint": (checkpoint or {}).get("save"),
            "verification": verification,
            "event": event,
        }
        if apply and ledger is not None and envelope is not None:
            result["action_receipt"] = ledger.complete(envelope, result=result)
        return result

    def _create_edit_checkpoint(self, prepared, context: dict[str, Any]) -> dict[str, Any] | None:
        if self._checkpoints is None:
            return None
        description = (
            f"Edit {prepared.relative_path} via {prepared.operation} "
            f"({context.get('provider_id') or 'provider'} / {context.get('model_id') or 'model'})"
        )
        payload = {
            "thread_id": context.get("execution_thread_id"),
            "thread_name": f"Edit {prepared.relative_path}",
            "description": description,
            "provider": context.get("provider_id") or "",
            "model": context.get("model_id") or "",
        }
        return self._checkpoints.create(payload, system=True)

    def _record_edit_event(self, event: dict[str, Any]) -> None:
        record = getattr(self._runtime, "record_supervisor_event", None)
        if not callable(record):
            return
        try:
            record({"event": "edit_operation_applied", "coding_event": event, "path": event.get("payload", {}).get("path")})
        except Exception:
            return

    def _command_operation(self, payload: dict[str, Any], *, test_mode: bool) -> dict[str, Any]:
        payload = self._materialize_tool_action_payload(payload)
        context = self._command_context(payload)
        root = self._workspace_root()
        tool_name = "run_tests" if test_mode else "run_command"
        action_arguments = self._side_effect_arguments(tool_name, payload)
        command = str(action_arguments.get("command") or "").strip()
        timeout_seconds = int(action_arguments.get("timeout_seconds") or (120 if test_mode else 60))
        timeout_seconds = max(1, min(timeout_seconds, 300))
        cwd = self._command_cwd(str(action_arguments.get("cwd") or "").strip())
        classification = classify_command(command, str(cwd))
        ledger, pending_envelope, authorized, authorization_reason = self._tool_action_envelope(
            root=root,
            tool_name=tool_name,
            action_arguments=action_arguments,
            payload=payload,
            context=context,
            authority_decision="command_approval_pending",
        )
        base = {
            "approved": False,
            "command": command,
            "cwd": str(cwd),
            "exit_code": None,
            "output": "",
            "classification": classification,
            "test_mode": test_mode,
        }
        if not authorized:
            receipt = ledger.record_terminal(pending_envelope, reason=authorization_reason)
            result = {
                **self._blocked_tool_action_result(authorization_reason, receipt),
                **base,
                "approval": {"decision": "blocked", "reason": "model_authority"},
            }
            self._record_command_event(result, context=context)
            return result
        try:
            approval = self._command_approval(command=command, cwd=cwd, classification=classification, context=context, test_mode=test_mode)
        except Exception:
            receipt = ledger.record_retryable(
                pending_envelope,
                reason="Command approval was unavailable before execution; the action may be retried safely.",
            )
            if str(receipt.get("state") or "") in {"executing", "interrupted", "recovery_required"}:
                result = self._admitted_receipt_result(
                    {"decision": "recovery_required", "receipt": receipt},
                    base={**base, "approval": {"decision": "unavailable"}},
                )
                self._record_command_event(result, context=context)
                return result
            result = {
                **base,
                "ok": False,
                "status": "retryable",
                "error": "Command approval was unavailable before execution.",
                "approval": {"decision": "unavailable"},
                "tool_event_verified": True,
                "action_receipt": receipt,
            }
            self._record_command_event(result, context=context)
            return result
        if approval.get("decision") not in {"accept", "acceptForSession"}:
            _ledger, approval_envelope, _authorized, _reason = self._tool_action_envelope(
                root=root,
                tool_name=tool_name,
                action_arguments=action_arguments,
                payload=payload,
                context=context,
                authority_decision="user_approval_required",
                authority_reason="Command execution requires explicit user approval.",
            )
            receipt = ledger.record_approval_required(
                approval_envelope,
                reason="Command execution requires explicit user approval.",
            )
            if str(receipt.get("state") or "") in {"executing", "interrupted", "recovery_required"}:
                result = self._admitted_receipt_result(
                    {"decision": "recovery_required", "receipt": receipt},
                    base={**base, "approval": approval},
                )
                self._record_command_event(result, context=context)
                return result
            result = {
                **base,
                "ok": False,
                "status": "approval_required",
                "output": "Command execution was declined.",
                "approval": approval,
                "tool_event_verified": True,
                "action_receipt": receipt,
            }
            self._record_command_event(result, context=context)
            return result
        _ledger, accepted_envelope, _authorized, _reason = self._tool_action_envelope(
            root=root,
            tool_name=tool_name,
            action_arguments=action_arguments,
            payload=payload,
            context=context,
            authority_decision="command_approval_accepted",
        )
        admission = ledger.admit(accepted_envelope)
        if admission["decision"] != "execute":
            result = self._admitted_receipt_result(
                admission,
                base={**base, "approval": approval, "approved": True},
            )
            self._record_command_event(result, context=context)
            return result
        try:
            completed = self._run_shell_command(command, cwd=cwd, timeout_seconds=timeout_seconds)
            output = "\n".join(part for part in [completed.get("stdout") or "", completed.get("stderr") or ""] if part).strip()
            timed_out = bool(completed.get("timed_out"))
            status = "timed_out" if timed_out else ("completed" if completed.get("returncode") == 0 else "failed")
            result = {
                "ok": completed.get("returncode") == 0,
                "status": status,
                "approved": True,
                "command": command,
                "cwd": str(cwd),
                "exit_code": completed.get("returncode"),
                "output": redact_sensitive(output)[:20000],
                "timed_out": timed_out,
                "classification": classification,
                "approval": approval,
                "test_mode": test_mode,
                "tool_event_verified": True,
            }
            result["action_receipt"] = ledger.complete(accepted_envelope, result=result)
        except Exception:
            ledger.interrupt(
                accepted_envelope,
                reason="Command execution was interrupted after action admission; effect status is unknown.",
            )
            raise
        self._record_command_event(result, context=context)
        return result

    def _command_context(self, payload: dict[str, Any]) -> dict[str, Any]:
        edit_context = self._edit_context(payload, target_exists=False)
        task = self._tasks.current_task() if self._tasks is not None else None
        active_provider_thread = self._tasks.active_provider_thread(include_missing_fallback=True) if self._tasks is not None else None
        task_settings = dict((task or {}).get("composer_settings") or {}) if isinstance(task, dict) else {}
        permission_mode = str(
            payload.get("permission_mode")
            or (active_provider_thread or {}).get("permission_mode")
            or task_settings.get("permission_mode")
            or ""
        ).strip().lower() or "auto"
        return {
            **edit_context,
            "permission_mode": permission_mode,
        }

    def _command_cwd(self, raw_cwd: str) -> Path:
        root = self._workspace_root()
        if not raw_cwd:
            return root
        return resolve_under(root, raw_cwd)

    def _command_approval(
        self,
        *,
        command: str,
        cwd: Path,
        classification: dict[str, Any],
        context: dict[str, Any],
        test_mode: bool,
    ) -> dict[str, Any]:
        permission_mode = str(context.get("permission_mode") or "auto").strip().lower()
        auto_allowed = bool(test_mode) or str(classification.get("decision") or "") == "allowed_in_sandbox"
        if permission_mode == "full":
            return {"decision": "accept", "reason": "permission_mode_full"}
        if permission_mode == "auto" and auto_allowed:
            return {"decision": "accept", "reason": "auto_allowed"}
        request_approval = getattr(self._runtime, "request_native_command_approval", None)
        if not callable(request_approval):
            raise RuntimeError("Runtime approval bridge is not available for native command execution.")
        decision = request_approval(
            thread_id=str(context.get("execution_thread_id") or context.get("visible_thread_id") or ""),
            turn_id=str(context.get("turn_id") or ""),
            command=command,
            cwd=str(cwd),
            reason=str(classification.get("reason") or ("Native test command" if test_mode else "Native command execution")),
        )
        return dict(decision or {})

    def _run_shell_command(self, command: str, *, cwd: Path, timeout_seconds: int) -> dict[str, Any]:
        launcher = ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", command]
        try:
            completed = subprocess.run(
                launcher,
                cwd=str(cwd),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout_seconds,
                check=False,
            )
            return {
                "returncode": completed.returncode,
                "stdout": completed.stdout,
                "stderr": completed.stderr,
                "timed_out": False,
            }
        except subprocess.TimeoutExpired as exc:
            return {
                "returncode": None,
                "stdout": exc.stdout or "",
                "stderr": exc.stderr or "",
                "timed_out": True,
            }

    def _record_command_event(self, result: dict[str, Any], *, context: dict[str, Any]) -> None:
        record = getattr(self._runtime, "record_supervisor_event", None)
        if not callable(record):
            return
        try:
            record(
                {
                    "event": "native_command_execution",
                    "thread_id": context.get("execution_thread_id") or context.get("visible_thread_id"),
                    "provider_id": context.get("provider_id"),
                    "model_id": context.get("model_id"),
                    "command": result.get("command"),
                    "status": result.get("status"),
                    "exitCode": result.get("exit_code"),
                    "aggregatedOutput": str(result.get("output") or "")[:4000],
                    "test_mode": bool(result.get("test_mode")),
                    "approved": bool(result.get("approved")),
                }
            )
        except Exception:
            return

    def _edit_context(self, payload: dict[str, Any], *, target_exists: bool) -> dict[str, Any]:
        profile = self._resolve_profile(payload)
        provider_id = str(payload.get("provider_id") or profile.get("provider_id") or "").strip() or None
        model_id = str(payload.get("model") or payload.get("model_id") or profile.get("model") or "").strip() or None
        model_record = self._resolve_model_record(provider_id, model_id, target_exists=target_exists)
        task = self._tasks.current_task() if self._tasks is not None else None
        active_provider_thread = self._tasks.active_provider_thread(include_missing_fallback=True) if self._tasks is not None else None
        return {
            "profile_id": str(profile.get("profile_id") or payload.get("profile_id") or "").strip() or None,
            "provider_id": provider_id,
            "model_id": model_id,
            "model_record": model_record,
            "task_id": str((task or {}).get("task_id") or ""),
            "visible_thread_id": str(self._tasks.visible_provider_thread_id(include_missing_fallback=True) if self._tasks is not None else ""),
            "execution_thread_id": str((active_provider_thread or {}).get("thread_id") or "") or None,
            "turn_id": str(payload.get("turn_id") or ""),
        }

    def _resolve_profile(self, payload: dict[str, Any]) -> dict[str, Any]:
        profile_id = str(payload.get("profile_id") or "").strip()
        if profile_id and self._profiles is not None:
            try:
                return dict(self._profiles.resolve_runtime_profile(profile_id))
            except Exception:
                return {"profile_id": profile_id}
        project = self._projects.current_project or {}
        fallback_profile_id = str(project.get("default_profile_id") or "").strip()
        if self._tasks is not None:
            task = self._tasks.current_task() or {}
            active = self._tasks.active_provider_thread(include_missing_fallback=True) or {}
            fallback_profile_id = str(
                payload.get("profile_id")
                or active.get("profile_id")
                or (task.get("composer_settings") or {}).get("profile_id")
                or fallback_profile_id
            ).strip()
        if fallback_profile_id and self._profiles is not None:
            try:
                return dict(self._profiles.resolve_runtime_profile(fallback_profile_id))
            except Exception:
                return {"profile_id": fallback_profile_id}
        return {}

    def _resolve_model_record(self, provider_id: str | None, model_id: str | None, *, target_exists: bool) -> dict[str, Any]:
        if self._router_config is not None and provider_id and model_id:
            full_id = f"{provider_id}/{model_id}"
            for item in self._router_config.models():
                if str(item.get("id") or "") in {model_id, full_id}:
                    return dict(item)
                if str(item.get("provider") or "") == provider_id and str(item.get("native_model") or "") == model_id:
                    return dict(item)
        if provider_id:
            try:
                profile = get_provider_profile(provider_id)
                record = {
                    "id": f"{provider_id}/{model_id or profile.default_model}",
                    "provider": provider_id,
                    "native_model": model_id or profile.default_model,
                    **profile.default_model_config(),
                    "edit_policy": profile.edit_policy_payload(),
                }
                if target_exists:
                    record.setdefault("authority_tier", "B")
                return record
            except Exception:
                pass
        return {
            "id": model_id or "unknown",
            "provider": provider_id or "",
            "native_model": model_id or "",
            "edit_policy": {"small": "patch", "medium": "patch", "large": "replace"},
            "authority_tier": "B",
        }

    def _estimate_edit_bytes(self, request) -> int:
        if request.content is not None:
            return len(request.content.encode("utf-8"))
        return sum(len(item.search.encode("utf-8")) + len(item.replace.encode("utf-8")) for item in request.edits)

    def _release_demo_baseline_files(self) -> dict[str, str]:
        return {
            ".gitignore": ".astrabridge/\n__pycache__/\n*.pyc\n",
            "README.md": (
                "# Provider Switch Scorecard Demo\n\n"
                "This workspace is used for the AstraBridge release workflow demo.\n\n"
                "## Workflow\n"
                "- run `python scorecard.py --checks checks.json`\n"
                "- inspect the diff in AstraBridge review mode\n"
                "- save a checkpoint after recovery is verified\n"
            ),
            "workflow_note.txt": "Baseline release workflow demo workspace.\n",
        }

    def _release_demo_readme_after_recovery(self) -> str:
        return (
            "# Provider Switch Scorecard Demo\n\n"
            "This workspace is used for the AstraBridge release workflow demo.\n\n"
            "## Workflow\n"
            "- run `python scorecard.py --checks checks.json`\n"
            "- inspect the diff in AstraBridge review mode\n"
            "- save a checkpoint after recovery is verified\n\n"
            "## Recovery Result\n"
            "- browser acceptance is now marked pass in `checks.json`\n"
            "- the recovery path was reproduced and cleared in the same task\n"
        )

    def _release_demo_scorecard_source(self) -> str:
        return (
            "#!/usr/bin/env python3\n"
            "\"\"\"Release workflow demo scorecard CLI.\"\"\"\n"
            "import argparse\n"
            "import json\n"
            "import sys\n"
            "from pathlib import Path\n\n"
            "def main(argv=None):\n"
            "    parser = argparse.ArgumentParser()\n"
            "    parser.add_argument('--checks', type=Path, default=Path('checks.json'))\n"
            "    args = parser.parse_args(argv)\n"
            "    checks = json.loads(args.checks.read_text(encoding='utf-8'))\n"
            "    failed = [item for item in checks if item.get('status') != 'pass']\n"
            "    print(json.dumps({'failed': len(failed), 'total': len(checks)}))\n"
            "    return 0 if not failed else 1\n\n"
            "if __name__ == '__main__':\n"
            "    raise SystemExit(main())\n"
        )

    def _release_demo_test_source(self) -> str:
        return (
            "import unittest\n"
            "import scorecard\n\n"
            "class DemoScorecardTests(unittest.TestCase):\n"
            "    def test_import(self):\n"
            "        self.assertTrue(callable(scorecard.main))\n\n"
            "if __name__ == '__main__':\n"
            "    unittest.main()\n"
        )

    def _require_isolated_demo_workspace(self, root: Path) -> None:
        normalized = root.resolve().as_posix().lower()
        if "/private/demo-runs/" not in normalized:
            raise ValueError("Release workflow demo preparation is only allowed inside PRIVATE/demo-runs isolated workspaces.")

    def _ensure_release_demo_git_baseline(self, root: Path) -> str:
        init = self._run(["git", "-C", str(root), "init"], timeout=10)
        if not init["ok"]:
            raise RuntimeError(f"git init failed: {init.get('stderr') or init.get('error') or 'unknown git error'}")
        add = self._run(["git", "-C", str(root), "add", "--all", "--", "."], timeout=10)
        if not add["ok"]:
            raise RuntimeError(f"git add failed: {add.get('stderr') or add.get('error') or 'unknown git error'}")
        has_head = self._run(["git", "-C", str(root), "rev-parse", "--verify", "HEAD"], timeout=5)["ok"]
        status = self._run(["git", "-C", str(root), "status", "--porcelain=v1", "--untracked-files=all", "--", "."], timeout=8)
        if has_head and not str(status.get("stdout") or "").strip():
            return str(self._run(["git", "-C", str(root), "rev-parse", "HEAD"], timeout=5).get("stdout") or "").strip()
        commit = self._run(
            [
                "git",
                "-C",
                str(root),
                "-c",
                "user.email=demo@example.invalid",
                "-c",
                "user.name=AstraBridge Demo",
                "commit",
                "--allow-empty",
                "-m",
                "Release workflow demo baseline",
            ],
            timeout=15,
        )
        if not commit["ok"]:
            raise RuntimeError(f"git commit failed: {commit.get('stderr') or commit.get('error') or 'unknown git error'}")
        return str(self._run(["git", "-C", str(root), "rev-parse", "HEAD"], timeout=5).get("stdout") or "").strip()

    def _full_git_diff(self, root: Path) -> str:
        result = self._run(["git", "-C", str(root), "diff", "--", "."], timeout=10)
        if result["ok"]:
            return str(result.get("stdout") or "")
        return ""

    def _write_release_demo_review_artifact(self, root: Path, diff_text: str) -> str:
        artifact = root / RELEASE_DEMO_REVIEW_ARTIFACT
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_text(diff_text or "No diff available.\n", encoding="utf-8")
        return artifact.relative_to(root).as_posix()

    def _prepare_release_demo_provider_switch(self, *, failed_run: dict[str, Any], recovered_run: dict[str, Any]) -> dict[str, Any] | None:
        if self._tasks is None or self._task_conversation is None:
            return None
        task = self._tasks.ensure_default_task(title="Release workflow demo")
        existing_source = self._tasks.active_provider_thread(include_missing_fallback=True) or {}
        source_thread_id = str(existing_source.get("thread_id") or "").strip() or "thread-demo-deepseek-release"
        target_thread_id = "thread-demo-kimi-review"
        source_settings = {
            "profile_id": "deepseek-default",
            "provider_id": "deepseek",
            "model": "deepseek-v4-pro",
            "reasoning_effort": "high",
            "permission_mode": "auto",
            "name": "DeepSeek implementation lane",
        }
        target_settings = {
            "profile_id": "kimi-default",
            "provider_id": "kimi",
            "model": "kimi-k2.7-code",
            "reasoning_effort": "high",
            "permission_mode": "auto",
            "name": "Kimi review lane",
        }
        self._tasks.bind_thread(thread_id=source_thread_id, settings=source_settings, role="provider", make_active=True)
        self._task_conversation.record_thread_snapshot(
            self._release_demo_source_thread_snapshot(
                thread_id=source_thread_id,
                failed_run=failed_run,
                recovered_run=recovered_run,
            )
        )
        handoff = self._tasks.record_provider_handoff(
            from_thread_id=source_thread_id,
            to_thread_id=target_thread_id,
            settings=target_settings,
            reused_existing=False,
            dropped_artifacts=1,
            repaired_tool_pairs=2,
            replayable_artifact_count=1,
            projection_preview="User: Implement a release readiness scorecard. Assistant: Created scorecard.py and recovered the failing browser check.",
            warnings=["Cross-provider handoff uses AstraBridge task context instead of raw provider-state replay."],
        )
        self._task_conversation.record_thread_snapshot(
            self._release_demo_target_thread_snapshot(
                thread_id=target_thread_id,
                handoff_created_at=str(handoff.get("created_at") or now_iso()),
                recovered_run=recovered_run,
            )
        )
        self._projects.switch_thread(target_thread_id)
        task = self._tasks.current_task() or task
        return {
            "source_thread_id": source_thread_id,
            "target_thread_id": target_thread_id,
            "handoff_event_id": handoff.get("event_id"),
            "lane_count": len(list(task.get("provider_threads") or [])),
            "handoff_count": len(list(task.get("handoff_events") or [])),
            "active_provider_thread_id": task.get("active_provider_thread_id"),
        }

    def _release_demo_source_thread_snapshot(self, *, thread_id: str, failed_run: dict[str, Any], recovered_run: dict[str, Any]) -> dict[str, Any]:
        started_at = now_iso()
        completed_at = now_iso()
        return {
            "id": thread_id,
            "name": "DeepSeek implementation lane",
            "displayName": "DeepSeek implementation lane",
            "status": {"type": "idle"},
            "shellSettings": {
                "profile_id": "deepseek-default",
                "provider_id": "deepseek",
                "model": "deepseek-v4-pro",
                "reasoning_effort": "high",
                "execution_backend": "codex_app_server",
            },
            "turns": [
                {
                    "id": "turn-demo-release-source",
                    "startedAt": started_at,
                    "completedAt": completed_at,
                    "items": [
                        {
                            "type": "userMessage",
                            "id": "user-demo-release",
                            "content": [{"type": "text", "text": "Implement a small release readiness scorecard, then recover one failing check inside the same task."}],
                        },
                        {
                            "type": "agentMessage",
                            "id": "agent-demo-release",
                            "text": "Created scorecard.py, added a baseline test, and reproduced the failing browser check before recovery.",
                        },
                        {
                            "type": "commandExecution",
                            "id": "cmd-demo-failed",
                            "command": RELEASE_DEMO_COMMAND,
                            "status": str(failed_run.get("status") or "failed"),
                            "exitCode": failed_run.get("exit_code"),
                            "aggregatedOutput": str(failed_run.get("output") or ""),
                        },
                        {
                            "type": "commandExecution",
                            "id": "cmd-demo-recovered",
                            "command": RELEASE_DEMO_COMMAND,
                            "status": str(recovered_run.get("status") or "completed"),
                            "exitCode": recovered_run.get("exit_code"),
                            "aggregatedOutput": str(recovered_run.get("output") or ""),
                        },
                        {
                            "type": "fileChange",
                            "id": "file-demo-source",
                            "status": "completed",
                            "changes": [
                                {"path": "scorecard.py", "kind": {"type": "add"}},
                                {"path": "test_scorecard.py", "kind": {"type": "add"}},
                                {"path": "checks.json", "kind": {"type": "add"}},
                            ],
                        },
                    ],
                }
            ],
        }

    def _release_demo_target_thread_snapshot(self, *, thread_id: str, handoff_created_at: str, recovered_run: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": thread_id,
            "name": "Kimi review lane",
            "displayName": "Kimi review lane",
            "status": {"type": "idle"},
            "shellSettings": {
                "profile_id": "kimi-default",
                "provider_id": "kimi",
                "model": "kimi-k2.7-code",
                "reasoning_effort": "high",
                "execution_backend": "codex_app_server",
            },
            "turns": [
                {
                    "id": "turn-demo-release-target",
                    "startedAt": handoff_created_at,
                    "completedAt": handoff_created_at,
                    "items": [
                        {
                            "type": "agentMessage",
                            "id": "agent-demo-review",
                            "text": "Continued the same visible task on Kimi, reviewed the scorecard output, and tightened the README and workflow note for recovery acceptance.",
                        },
                        {
                            "type": "fileChange",
                            "id": "file-demo-target",
                            "status": "completed",
                            "changes": [
                                {"path": "README.md", "kind": {"type": "update"}},
                                {"path": "workflow_note.txt", "kind": {"type": "update"}},
                            ],
                        },
                        {
                            "type": "commandExecution",
                            "id": "cmd-demo-target",
                            "command": RELEASE_DEMO_COMMAND,
                            "status": str(recovered_run.get("status") or "completed"),
                            "exitCode": recovered_run.get("exit_code"),
                            "aggregatedOutput": str(recovered_run.get("output") or ""),
                        },
                    ],
                }
            ],
        }

    def _release_demo_command_event(
        self,
        context: dict[str, Any],
        result: dict[str, Any],
        *,
        event_id: str,
    ) -> dict[str, Any]:
        return {
            "event_id": event_id,
            "task_id": context.get("task_id"),
            "visible_thread_id": context.get("visible_thread_id"),
            "execution_thread_id": context.get("execution_thread_id"),
            "provider_id": context.get("provider_id"),
            "model_id": context.get("model_id"),
            "event_type": "command_execution",
            "timestamp": now_iso(),
            "payload": {
                "command": result.get("command"),
                "status": result.get("status"),
                "exit_code": result.get("exit_code"),
            },
            "redaction_status": "secret_free",
            "source": "sidecar",
        }

    def _release_demo_verification_event(
        self,
        context: dict[str, Any],
        *,
        event_id: str,
        tool: str,
        path: str | None = None,
        review_diff_path: str | None = None,
        files: list[str] | None = None,
        paths: list[str] | None = None,
        save_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        return {
            "event_id": event_id,
            "task_id": context.get("task_id"),
            "visible_thread_id": context.get("visible_thread_id"),
            "execution_thread_id": context.get("execution_thread_id"),
            "provider_id": context.get("provider_id"),
            "model_id": context.get("model_id"),
            "event_type": "verification_result",
            "timestamp": now_iso(),
            "payload": {
                "tool": tool,
                "path": path,
                "review_diff_path": review_diff_path,
                "files": list(files or []),
                "paths": list(paths or []),
                "save_ids": list(save_ids or []),
                "ok": True,
            },
            "redaction_status": "secret_free",
            "source": "sidecar",
        }

    def _release_demo_runtime_transition_event(
        self,
        context: dict[str, Any],
        *,
        event_id: str,
        transition: str,
    ) -> dict[str, Any]:
        return {
            "event_id": event_id,
            "task_id": context.get("task_id"),
            "visible_thread_id": context.get("visible_thread_id"),
            "execution_thread_id": context.get("execution_thread_id"),
            "provider_id": context.get("provider_id"),
            "model_id": context.get("model_id"),
            "event_type": "runtime_transition",
            "timestamp": now_iso(),
            "payload": {"transition": transition},
            "redaction_status": "secret_free",
            "source": "sidecar",
        }

    def _safe_rel_path(self, root: Path, rel_path: str, *, allow_managed_state: bool) -> Path:
        raw = str(rel_path or "").strip()
        if not raw:
            raise ValueError("path is required.")
        normalized = raw.replace("\\", "/")
        host_path = path_for_host(normalized)
        candidate = host_path.resolve() if host_path.is_absolute() else (root / normalized.lstrip("/")).resolve()
        if root not in candidate.parents and candidate != root:
            raise ValueError("Path escapes the workspace.")
        rel = candidate.relative_to(root)
        if self._looks_secret(rel):
            raise ValueError("Refusing to preview secret-like file names.")
        if rel.parts and rel.parts[0] == WORKSPACE_STATE_DIRNAME:
            if not allow_managed_state or not self._is_managed_state_preview_path(rel):
                raise ValueError("Only selected AstraBridge artifact files can be previewed.")
        if not candidate.is_file():
            raise ValueError("File does not exist or is not a regular file.")
        return candidate

    def _skip_dir(self, rel: Path) -> bool:
        if not rel.parts:
            return False
        if rel.parts[0] == WORKSPACE_STATE_DIRNAME:
            if self._looks_secret(rel):
                return True
            return len(rel.parts) > 1 and rel.parts[1] not in MANAGED_STATE_PREVIEW_ALLOWLIST
        name = rel.name
        if name in SKIP_DIRS:
            return True
        return self._looks_secret(rel)

    def _skip_file(self, rel: Path) -> bool:
        if self._looks_secret(rel):
            return True
        if rel.parts and rel.parts[0] == WORKSPACE_STATE_DIRNAME:
            return not self._is_managed_state_preview_path(rel)
        return False

    def _is_managed_state_preview_path(self, rel: Path) -> bool:
        return len(rel.parts) >= 3 and rel.parts[0] == WORKSPACE_STATE_DIRNAME and rel.parts[1] in MANAGED_STATE_PREVIEW_ALLOWLIST

    def _looks_secret(self, rel: Path) -> bool:
        text = rel.as_posix().lower()
        return any(part in text for part in SECRET_NAME_PARTS)

    def _file_kind(self, path: Path) -> str:
        suffix = path.suffix.lower()
        if suffix in MARKDOWN_EXTENSIONS:
            return "markdown"
        if suffix in JSON_EXTENSIONS:
            return "json"
        if suffix in IMAGE_EXTENSIONS:
            return "image"
        if suffix in PDF_EXTENSIONS:
            return "pdf"
        if suffix in AUDIO_EXTENSIONS:
            return "audio"
        if suffix in VIDEO_EXTENSIONS:
            return "video"
        if suffix in TEXT_EXTENSIONS:
            return "text"
        return "binary"

    def _git_summary(self, root: Path) -> dict[str, Any]:
        branch_result = self._run(["git", "-C", str(root), "rev-parse", "--abbrev-ref", "HEAD"], timeout=5)
        if not branch_result["ok"]:
            return {"is_repo": False, "branch": "", "changed_files": 0, "added": 0, "deleted": 0, "files": []}
        top_result = self._run(["git", "-C", str(root), "rev-parse", "--show-toplevel"], timeout=5)
        repo_root = Path(str(top_result.get("stdout") or root).strip()).resolve() if top_result["ok"] else root
        status_result = self._run(["git", "-C", str(root), "status", "--porcelain=v1", "--untracked-files=all", "--", "."], timeout=8)
        numstat_result = self._run(["git", "-C", str(root), "diff", "--numstat", "--", "."], timeout=8)
        files = self._parse_git_status(status_result.get("stdout") or "", root=root, repo_root=repo_root)
        added, deleted = self._parse_numstat(numstat_result.get("stdout") or "")
        return {
            "is_repo": True,
            "branch": str(branch_result["stdout"]).strip(),
            "git_root": str(repo_root),
            "changed_files": len(files),
            "added": added,
            "deleted": deleted,
            "files": files,
        }

    def _parse_git_status(self, text: str, *, root: Path | None = None, repo_root: Path | None = None) -> list[dict[str, Any]]:
        files = []
        for line in text.splitlines():
            if not line.strip() or len(line) < 4:
                continue
            status = line[:2].strip() or "modified"
            path = line[3:].strip()
            if " -> " in path:
                path = path.split(" -> ", 1)[1].strip()
            path = self._workspace_relative_git_path(path, root=root, repo_root=repo_root)
            rel = Path(path) if path else Path()
            if path and not self._skip_file(rel):
                item: dict[str, Any] = {"path": path, "status": status}
                if root is not None:
                    try:
                        item["updated_at"] = (root / rel).stat().st_mtime
                    except OSError:
                        pass
                files.append(item)
        return files

    def _workspace_relative_git_path(self, path: str, *, root: Path | None, repo_root: Path | None) -> str:
        normalized = path.replace("\\", "/").strip().strip('"')
        if not normalized or not root or not repo_root:
            return normalized
        try:
            root_rel = root.resolve().relative_to(repo_root.resolve()).as_posix()
        except ValueError:
            return normalized
        if not root_rel or root_rel == ".":
            return normalized
        prefix = f"{root_rel}/"
        if normalized == root_rel:
            return ""
        if normalized.startswith(prefix):
            return normalized[len(prefix) :]
        return normalized

    def _synthetic_file_diff(self, root: Path, target: Path) -> str:
        try:
            rel = target.relative_to(root).as_posix()
            if self._file_kind(target) != "text":
                return ""
            stat = target.stat()
            if stat.st_size > MAX_TEXT_BYTES:
                return ""
            content = target.read_text(encoding="utf-8-sig", errors="replace")
        except OSError:
            return ""
        lines = content.splitlines()
        output = [
            f"diff --astrabridge a/{rel} b/{rel}",
            "new file mode 100644",
            "--- /dev/null",
            f"+++ b/{rel}",
            f"@@ -0,0 +1,{len(lines)} @@",
        ]
        output.extend(f"+{line}" for line in lines)
        if content.endswith("\n"):
            output.append("")
        return "\n".join(output)

    def _parse_numstat(self, text: str) -> tuple[int, int]:
        added = 0
        deleted = 0
        for line in text.splitlines():
            parts = line.split("\t")
            if len(parts) < 3:
                continue
            try:
                added += int(parts[0]) if parts[0] != "-" else 0
                deleted += int(parts[1]) if parts[1] != "-" else 0
            except ValueError:
                continue
        return added, deleted

    def _recent_files(self, root: Path) -> list[dict[str, Any]]:
        candidates: list[tuple[float, str]] = []
        for current, dirs, files in os.walk(root):
            current_path = Path(current)
            rel_dir = current_path.relative_to(root)
            dirs[:] = [name for name in sorted(dirs) if not self._skip_dir(rel_dir / name)]
            for name in files:
                rel = rel_dir / name
                if self._skip_file(rel):
                    continue
                try:
                    candidates.append(((current_path / name).stat().st_mtime, rel.as_posix()))
                except OSError:
                    continue
        candidates.sort(reverse=True)
        return [{"path": path, "status": "recent", "updated_at": mtime} for mtime, path in candidates[:40]]

    def _run(self, args: list[str], *, timeout: int) -> dict[str, Any]:
        try:
            completed = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout, check=False)
            return {"ok": completed.returncode == 0, "stdout": completed.stdout, "stderr": completed.stderr, "returncode": completed.returncode}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "stdout": "", "stderr": "", "error": str(exc)}

    def _extract_command(self, value: Any) -> str:
        if isinstance(value, dict):
            for key in ("command", "cmd", "launch_command"):
                candidate = value.get(key)
                if isinstance(candidate, str) and candidate.strip():
                    return candidate.strip()
                if isinstance(candidate, list) and candidate:
                    return " ".join(str(part) for part in candidate)
            for item in value.values():
                found = self._extract_command(item)
                if found:
                    return found
        if isinstance(value, list):
            for item in value:
                found = self._extract_command(item)
                if found:
                    return found
        return ""

    def _extract_status(self, value: Any) -> str:
        if isinstance(value, dict):
            status = value.get("status") or value.get("type") or value.get("method")
            if status:
                return str(status)[:80]
        return "event"

