from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from .common import now_iso


CODEX_KERNEL_MATRIX_VALIDATION_SCHEMA_VERSION = "codex-kernel-matrix-validation-v1"

_ENTRY_HEADER_RE = re.compile(r"^### `(?P<matrix_id>[^`]+)`\s*$")
_FIELD_RE = re.compile(r"^- `(?P<field>[^`]+)`: ?(?P<value>.*)$")
_LIST_ITEM_RE = re.compile(r"^  - (?P<value>.+)$")
_SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+(?:[-+][A-Za-z0-9._-]+)?$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_LIST_FIELDS = {"known_breakages", "required_mitigations", "evidence_paths"}
_REQUIRED_FIELDS = (
    "matrix_id",
    "codex_version",
    "release_anchor",
    "platform",
    "execution_lane",
    "binary_locator",
    "overall_status",
    "probe_result",
    "smoke_result",
    "known_breakages",
    "required_mitigations",
    "evidence_paths",
    "last_reviewed_at",
)
_ALLOWED_OVERALL_STATUSES = {"verified", "probed", "partial", "blocked", "unknown"}
_ALLOWED_SMOKE_RESULTS = {"passed", "failed", "not_run", "not_applicable"}
_FUZZY_BINARY_MARKERS = (" or ", "target line", "unknown", "either ")


def parse_compatibility_matrix(matrix_path: Path) -> list[dict[str, Any]]:
    text = matrix_path.read_text(encoding="utf-8")
    entries: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    pending_list_field: str | None = None

    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        header = _ENTRY_HEADER_RE.match(raw_line)
        if header:
            if current is not None:
                entries.append(current)
            current = {
                "header_matrix_id": header.group("matrix_id"),
                "__line__": line_number,
            }
            pending_list_field = None
            continue

        if current is None:
            continue
        if raw_line.startswith("## "):
            entries.append(current)
            current = None
            pending_list_field = None
            continue

        if pending_list_field is not None:
            item = _LIST_ITEM_RE.match(raw_line)
            if item:
                current.setdefault(pending_list_field, []).append(_clean_value(item.group("value")))
                continue
            if not raw_line.strip():
                continue
            pending_list_field = None

        field = _FIELD_RE.match(raw_line)
        if not field:
            continue
        name = field.group("field")
        value = field.group("value").strip()
        if name in _LIST_FIELDS and not value:
            current.setdefault(name, [])
            pending_list_field = name
            continue
        if name in _LIST_FIELDS:
            current[name] = [_clean_value(value)]
            continue
        current[name] = _clean_value(value)

    if current is not None:
        entries.append(current)
    return entries


def validate_compatibility_matrix(
    *,
    matrix_path: Path,
    repo_root: Path,
    matrix_id: str | None = None,
) -> dict[str, Any]:
    entries = parse_compatibility_matrix(matrix_path)
    if matrix_id:
        entries = [entry for entry in entries if str(entry.get("header_matrix_id") or "") == matrix_id]
    issues: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    entry_summaries: list[dict[str, Any]] = []

    if not entries:
        issues.append(
            _issue(
                matrix_id=matrix_id or "<none>",
                field="matrix",
                message="No compatibility matrix entries were parsed from the matrix file.",
            )
        )

    for entry in entries:
        header_matrix_id = str(entry.get("header_matrix_id") or "").strip()
        if header_matrix_id in seen_ids:
            issues.append(_issue(matrix_id=header_matrix_id, field="matrix_id", message="Duplicate matrix entry header was found."))
        else:
            seen_ids.add(header_matrix_id)
        issues.extend(_validate_entry(entry, repo_root=repo_root))
        entry_summaries.append(
            {
                "matrix_id": header_matrix_id,
                "overall_status": entry.get("overall_status"),
                "smoke_result": entry.get("smoke_result"),
                "verified_gate": _verified_gate_status(entry, repo_root),
            }
        )

    ok = not issues
    return {
        "schema_version": CODEX_KERNEL_MATRIX_VALIDATION_SCHEMA_VERSION,
        "validated_at": now_iso(),
        "ok": ok,
        "matrix_path": str(matrix_path.resolve()),
        "repo_root": str(repo_root.resolve()),
        "entry_count": len(entries),
        "error_count": len(issues),
        "entries": entry_summaries,
        "issues": issues,
    }


def _validate_entry(entry: dict[str, Any], repo_root: Path) -> list[dict[str, Any]]:
    matrix_id = str(entry.get("header_matrix_id") or "<unknown>")
    issues: list[dict[str, Any]] = []
    for field in _REQUIRED_FIELDS:
        if field not in entry:
            issues.append(_issue(matrix_id=matrix_id, field=field, message="Required field is missing from the entry detail block."))
            continue
        value = entry[field]
        if field in _LIST_FIELDS:
            if not isinstance(value, list) or not value:
                issues.append(_issue(matrix_id=matrix_id, field=field, message="Required list field must contain at least one item."))
        elif not str(value or "").strip():
            issues.append(_issue(matrix_id=matrix_id, field=field, message="Required field must not be blank."))

    field_matrix_id = str(entry.get("matrix_id") or "").strip()
    if field_matrix_id and field_matrix_id != matrix_id:
        issues.append(_issue(matrix_id=matrix_id, field="matrix_id", message="Field `matrix_id` does not match the entry header id."))

    overall_status = str(entry.get("overall_status") or "").strip()
    if overall_status and overall_status not in _ALLOWED_OVERALL_STATUSES:
        issues.append(
            _issue(
                matrix_id=matrix_id,
                field="overall_status",
                message=f"Unsupported overall status `{overall_status}`. Expected one of {sorted(_ALLOWED_OVERALL_STATUSES)}.",
            )
        )

    smoke_result = str(entry.get("smoke_result") or "").strip()
    if smoke_result and smoke_result not in _ALLOWED_SMOKE_RESULTS:
        issues.append(
            _issue(
                matrix_id=matrix_id,
                field="smoke_result",
                message=f"Unsupported smoke result `{smoke_result}`. Expected one of {sorted(_ALLOWED_SMOKE_RESULTS)}.",
            )
        )

    last_reviewed_at = str(entry.get("last_reviewed_at") or "").strip()
    if last_reviewed_at and not _DATE_RE.match(last_reviewed_at):
        issues.append(_issue(matrix_id=matrix_id, field="last_reviewed_at", message="`last_reviewed_at` must use YYYY-MM-DD format."))

    evidence_paths = list(entry.get("evidence_paths") or [])
    for evidence_path in evidence_paths:
        resolved = _resolve_evidence_path(repo_root, str(evidence_path))
        if resolved is None or not resolved.exists():
            issues.append(
                _issue(
                    matrix_id=matrix_id,
                    field="evidence_paths",
                    message=f"Evidence reference does not exist: {evidence_path}",
                )
            )

    if overall_status == "verified":
        codex_version = str(entry.get("codex_version") or "").strip()
        if not _SEMVER_RE.match(codex_version):
            issues.append(
                _issue(
                    matrix_id=matrix_id,
                    field="codex_version",
                    message="Verified entries require an exact semver in `codex_version`.",
                )
            )
        binary_locator = str(entry.get("binary_locator") or "").strip().lower()
        if any(marker in binary_locator for marker in _FUZZY_BINARY_MARKERS):
            issues.append(
                _issue(
                    matrix_id=matrix_id,
                    field="binary_locator",
                    message="Verified entries require a non-ambiguous exact binary locator.",
                )
            )
        if smoke_result != "passed":
            issues.append(
                _issue(
                    matrix_id=matrix_id,
                    field="smoke_result",
                    message="Verified entries require `smoke_result` to be `passed`.",
                )
            )
        if not _has_existing_evidence_suffix(repo_root, evidence_paths, "smoke-report.json"):
            issues.append(
                _issue(
                    matrix_id=matrix_id,
                    field="evidence_paths",
                    message="Verified entries require an existing preserved smoke report path.",
                )
            )
        if not _has_existing_evidence_suffix(repo_root, evidence_paths, "kernel-probe-snapshot.json"):
            issues.append(
                _issue(
                    matrix_id=matrix_id,
                    field="evidence_paths",
                    message="Verified entries require an existing preserved kernel probe snapshot path.",
                )
            )

    return issues


def _verified_gate_status(entry: dict[str, Any], repo_root: Path) -> str:
    if str(entry.get("overall_status") or "").strip() != "verified":
        return "not_applicable"
    return "passed" if not _validate_entry(entry, repo_root) else "failed"


def _resolve_evidence_path(repo_root: Path, evidence_path: str) -> Path | None:
    text = str(evidence_path or "").strip().strip("`")
    if not text:
        return None
    if re.match(r"^[A-Za-z]+://", text):
        return None
    candidate = Path(text)
    if candidate.is_absolute():
        return candidate
    return (repo_root / candidate).resolve()


def _has_existing_evidence_suffix(repo_root: Path, evidence_paths: list[str], suffix: str) -> bool:
    for evidence_path in evidence_paths:
        resolved = _resolve_evidence_path(repo_root, str(evidence_path))
        if resolved is not None and resolved.exists() and str(resolved).replace("\\", "/").endswith(suffix):
            return True
    return False


def _clean_value(value: str) -> str:
    text = str(value or "").strip()
    if len(text) >= 2 and text.startswith("`") and text.endswith("`"):
        return text[1:-1]
    return text


def _issue(*, matrix_id: str, field: str, message: str) -> dict[str, Any]:
    return {
        "severity": "error",
        "matrix_id": matrix_id,
        "field": field,
        "message": message,
    }


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate the AstraBridge Codex kernel compatibility matrix.")
    parser.add_argument("--matrix", type=Path, required=True, help="Path to PLAN/CODEX_KERNEL_COMPATIBILITY_MATRIX.md.")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd(), help="Repo root used to resolve evidence references.")
    parser.add_argument("--matrix-id", default=None, help="Optional matrix entry id to validate in isolation.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    report = validate_compatibility_matrix(
        matrix_path=args.matrix,
        repo_root=args.repo_root,
        matrix_id=args.matrix_id,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
