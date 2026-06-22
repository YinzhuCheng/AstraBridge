from __future__ import annotations

import difflib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .edit_strategy import EditOperation


SECRET_NAME_PARTS = ("secret", "token", "apikey", "api_key", "authorization", "cookie", "password", ".env")
MAX_DIFF_CHARS = 120_000


@dataclass(frozen=True)
class TextEdit:
    search: str
    replace: str
    count: int | None = None


@dataclass(frozen=True)
class EditRequest:
    path: str
    content: str | None
    edits: tuple[TextEdit, ...]


@dataclass
class PreparedEdit:
    operation: EditOperation
    absolute_path: Path
    relative_path: str
    existed: bool
    before_text: str
    after_text: str
    changed: bool
    diff_text: str
    diff_truncated: bool
    added_lines: int
    removed_lines: int

    def preview_payload(self) -> dict[str, Any]:
        return {
            "path": self.relative_path,
            "existed": self.existed,
            "changed": self.changed,
            "selected_operation": self.operation,
            "diff": self.diff_text[:MAX_DIFF_CHARS],
            "truncated": self.diff_truncated,
            "added_lines": self.added_lines,
            "removed_lines": self.removed_lines,
            "synthetic": True,
        }


def request_from_payload(payload: dict[str, Any]) -> EditRequest:
    path = str(payload.get("path") or "").strip().replace("\\", "/")
    if not path:
        raise ValueError("path is required.")
    content = payload.get("content")
    if content is not None and not isinstance(content, str):
        raise ValueError("content must be a string when provided.")
    edits_payload = payload.get("edits")
    edits: list[TextEdit] = []
    if isinstance(edits_payload, list):
        for item in edits_payload:
            if not isinstance(item, dict):
                raise ValueError("Each edit entry must be an object.")
            edits.append(_edit_from_payload(item))
    elif "search" in payload or "replace" in payload:
        edits.append(
            _edit_from_payload(
                {
                    "search": payload.get("search"),
                    "replace": payload.get("replace"),
                    "count": payload.get("count"),
                }
            )
        )
    if content is None and not edits:
        raise ValueError("Either content or text edits are required.")
    return EditRequest(path=path, content=content, edits=tuple(edits))


def available_operations_for_request(request: EditRequest, *, target_exists: bool) -> tuple[EditOperation, ...]:
    operations: list[EditOperation] = []
    if request.edits:
        operations.extend(["apply_patch", "structured_edit"])
    if request.content is not None:
        operations.append("replace_file" if target_exists else "write_file")
        operations.append("write_file")
    operations.append("propose_only")
    deduped: list[EditOperation] = []
    for item in operations:
        if item not in deduped:
            deduped.append(item)
    return tuple(deduped)


class EditExecutor:
    def __init__(self, workspace_root: Path) -> None:
        self._root = workspace_root.resolve()

    def target_exists(self, rel_path: str) -> bool:
        candidate = self._resolve_target(rel_path, allow_missing=True)
        return candidate.is_file()

    def prepare(self, request: EditRequest, *, operation: EditOperation) -> PreparedEdit:
        path = self._resolve_target(request.path, allow_missing=operation in {"write_file", "replace_file", "propose_only"})
        existed = path.is_file()
        if operation == "replace_file" and not existed:
            raise ValueError("replace_file requires an existing target file.")
        if operation in {"apply_patch", "structured_edit"} and not existed:
            raise ValueError(f"{operation} requires an existing target file.")
        before = self._read_text(path) if existed else ""
        after = self._build_after_text(before, request, operation=operation, target_exists=existed)
        diff = self._synthetic_diff(request.path, before, after)
        added, removed = _diff_line_counts(diff)
        return PreparedEdit(
            operation=operation,
            absolute_path=path,
            relative_path=request.path,
            existed=existed,
            before_text=before,
            after_text=after,
            changed=before != after,
            diff_text=diff,
            diff_truncated=len(diff) > MAX_DIFF_CHARS,
            added_lines=added,
            removed_lines=removed,
        )

    def apply(self, prepared: PreparedEdit) -> None:
        prepared.absolute_path.parent.mkdir(parents=True, exist_ok=True)
        with prepared.absolute_path.open("w", encoding="utf-8", newline="") as handle:
            handle.write(prepared.after_text)

    def verification_hook(self, prepared: PreparedEdit, *, checkpoint: dict[str, Any] | None = None) -> dict[str, Any]:
        save = checkpoint.get("save") if isinstance(checkpoint, dict) else None
        return {
            "review_diff_path": prepared.relative_path,
            "review_status_endpoint": "/api/project/review/status",
            "files_tree_endpoint": "/api/project/files/tree",
            "checkpoint_save_id": (save or {}).get("save_id"),
        }

    def _resolve_target(self, rel_path: str, *, allow_missing: bool) -> Path:
        raw = str(rel_path or "").strip().replace("\\", "/").lstrip("/")
        candidate = (self._root / raw).resolve()
        if self._root not in candidate.parents and candidate != self._root:
            raise ValueError("Path escapes the workspace.")
        relative = candidate.relative_to(self._root)
        if relative.parts and relative.parts[0] == ".astrabridge":
            raise ValueError("Edits to raw .astrabridge state are not supported through this API.")
        if _looks_secret(relative):
            raise ValueError("Refusing to edit secret-like file paths.")
        if candidate.exists() and not candidate.is_file():
            raise ValueError("Target path is not a regular file.")
        if not allow_missing and not candidate.exists():
            raise ValueError("Target file does not exist.")
        return candidate

    def _read_text(self, path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8-sig", errors="replace")
        except OSError as exc:
            raise ValueError(f"Could not read file: {path.name}") from exc

    def _build_after_text(self, before: str, request: EditRequest, *, operation: EditOperation, target_exists: bool) -> str:
        if operation in {"replace_file", "write_file"}:
            if request.content is None:
                raise ValueError(f"{operation} requires content.")
            return request.content
        if request.edits:
            return _apply_text_edits(before, request.edits)
        if operation == "propose_only" and request.content is not None:
            return request.content
        if not target_exists:
            raise ValueError("The requested edit operation requires an existing file.")
        raise ValueError("No compatible edit instructions were provided.")

    def _synthetic_diff(self, rel_path: str, before: str, after: str) -> str:
        return "".join(
            difflib.unified_diff(
                before.splitlines(keepends=True),
                after.splitlines(keepends=True),
                fromfile=f"a/{rel_path}",
                tofile=f"b/{rel_path}",
                lineterm="\n",
            )
        )


def _edit_from_payload(payload: dict[str, Any]) -> TextEdit:
    search = payload.get("search")
    replace = payload.get("replace")
    if not isinstance(search, str) or not search:
        raise ValueError("Each text edit requires a non-empty search string.")
    if not isinstance(replace, str):
        raise ValueError("Each text edit requires a string replace value.")
    count_raw = payload.get("count")
    count = None
    if count_raw not in {None, ""}:
        count = int(count_raw)
        if count <= 0:
            raise ValueError("count must be positive when provided.")
    return TextEdit(search=search, replace=replace, count=count)


def _apply_text_edits(text: str, edits: tuple[TextEdit, ...]) -> str:
    current = text
    for edit in edits:
        matches = current.count(edit.search)
        if matches <= 0:
            raise ValueError(f"Patch prevalidation failed: could not find required text `{edit.search[:80]}`.")
        if edit.count is not None and matches < edit.count:
            raise ValueError(
                f"Patch prevalidation failed: expected at least {edit.count} matches for `{edit.search[:80]}`, found {matches}."
            )
        replace_count = edit.count or matches
        current = current.replace(edit.search, edit.replace, replace_count)
    return current


def _looks_secret(relative: Path) -> bool:
    lowered = relative.as_posix().lower()
    return any(part in lowered for part in SECRET_NAME_PARTS)


def _diff_line_counts(diff_text: str) -> tuple[int, int]:
    added = 0
    removed = 0
    for line in diff_text.splitlines():
        if line.startswith("+++") or line.startswith("---") or line.startswith("@@"):
            continue
        if line.startswith("+"):
            added += 1
        elif line.startswith("-"):
            removed += 1
    return added, removed
