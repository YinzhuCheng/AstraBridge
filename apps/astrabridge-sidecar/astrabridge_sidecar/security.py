from __future__ import annotations

import os
import re
import shutil
import hashlib
import mimetypes
from pathlib import Path
from typing import Any

from .common import new_id, now_iso, read_json, write_json


SECRET_RE = re.compile(
    r"(?i)(authorization\s*:|bearer\s+[a-z0-9._-]{12,}|api[_-]?key|secret[_-]?key|cookie\s*:|token\s*[:=]|ssh-rsa|BEGIN\s+(RSA|OPENSSH|EC|DSA)\s+PRIVATE\s+KEY)"
)
SECRET_PATH_PARTS = {
    ".aws",
    ".azure",
    ".docker",
    ".gnupg",
    ".kube",
    ".ssh",
    "credentials",
    "secrets",
}
SKIP_IMPORT_PATH_PARTS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "__pycache__",
    "node_modules",
    "dist",
    "target",
}
SAFE_GIT_COMMANDS = {
    "status",
    "diff",
    "log",
    "branch",
    "show",
    "add",
    "commit",
}


class SecurityError(ValueError):
    pass


def resolve_under(root: Path, value: str | Path) -> Path:
    root = root.resolve()
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = root / candidate
    resolved = candidate.resolve()
    if resolved != root and root not in resolved.parents:
        raise SecurityError(f"Path escapes project sandbox: {value}")
    return resolved


def relative_to_root(root: Path, value: str | Path) -> str:
    resolved = resolve_under(root, value)
    return resolved.relative_to(root.resolve()).as_posix()


def assert_no_secret_path(path: Path) -> None:
    if _has_secret_path_part(path):
        raise SecurityError(f"Refusing secret-bearing path: {path}")


def _has_secret_path_part(path: Path) -> bool:
    lowered = {part.lower() for part in path.parts}
    return bool(lowered.intersection(SECRET_PATH_PARTS))


def scan_text_for_secrets(path: Path) -> None:
    if not path.is_file():
        return
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return
    if SECRET_RE.search(text):
        raise SecurityError(f"Secret-like content detected in {path}")


def import_file_to_project(source: Path, project_root: Path, target_subdir: str = "INBOX/imports") -> dict[str, Any]:
    source = source.expanduser().resolve()
    if not source.exists() or not source.is_file():
        raise SecurityError(f"Import source is not a file: {source}")
    assert_no_secret_path(source)
    scan_text_for_secrets(source)
    target_dir = resolve_under(project_root, target_subdir)
    _mkdir(target_dir)
    target = target_dir / source.name
    _copy2(source, target)
    return {"source_name": source.name, "target": relative_to_root(project_root, target)}


def import_directory_to_project(source_dir: Path, project_root: Path, target_subdir: str = "INBOX/imports") -> dict[str, Any]:
    source_dir = source_dir.expanduser().resolve()
    if not source_dir.exists() or not source_dir.is_dir():
        raise SecurityError(f"Import source is not a directory: {source_dir}")
    assert_no_secret_path(source_dir)
    target_root = resolve_under(project_root, target_subdir)
    imported: list[dict[str, Any]] = []
    excluded: list[dict[str, str]] = []
    for source in sorted(path for path in source_dir.rglob("*") if path.is_file()):
        relative = source.relative_to(source_dir)
        relative_name = relative.as_posix()
        skip_reason = _skip_import_reason(relative)
        if skip_reason:
            excluded.append({"source_name": relative_name, "reason": skip_reason})
            continue
        try:
            assert_no_secret_path(source)
            scan_text_for_secrets(source)
        except SecurityError as exc:
            excluded.append({"source_name": relative_name, "reason": str(exc)})
            continue
        target = target_root / relative
        _mkdir(target.parent)
        _copy2(source, target)
        role = classify_material_role(relative)
        imported.append(
            {
                "source_name": relative_name,
                "target": relative_to_root(project_root, target),
                "role": role,
                "bytes": source.stat().st_size,
                "sha256": _sha256(source),
                "mime_type": mimetypes.guess_type(source.name)[0] or "application/octet-stream",
            }
        )

    role_counts: dict[str, int] = {}
    for item in imported:
        role = str(item["role"])
        role_counts[role] = role_counts.get(role, 0) + 1

    manifest_id = new_id("MAT")
    warnings = _manifest_warnings(imported, excluded)
    manifest = {
        "schema_version": "research-material-manifest-v1",
        "manifest_id": manifest_id,
        "created_at": now_iso(),
        "source_name": source_dir.name,
        "target_root": relative_to_root(project_root, target_root),
        "file_count": len(imported),
        "excluded_count": len(excluded),
        "role_counts": role_counts,
        "warnings": warnings,
        "imported_files": imported,
        "excluded_files": excluded,
    }
    summary = {
        "schema_version": "research-material-manifest-summary-v1",
        "manifest_id": manifest_id,
        "created_at": manifest["created_at"],
        "source_name": source_dir.name,
        "target_root": manifest["target_root"],
        "file_count": len(imported),
        "excluded_count": len(excluded),
        "role_counts": role_counts,
        "warnings": warnings,
    }
    write_json(project_root / "CONTROL" / "intake_queue" / f"{manifest_id}.material_manifest.json", manifest)
    _write_public_manifest_summary(project_root, summary)
    return manifest


def _write_public_manifest_summary(project_root: Path, current_summary: dict[str, Any]) -> None:
    manifest_dir = project_root / "CONTROL" / "intake_queue"
    manifest_files = sorted(manifest_dir.glob("*.material_manifest.json")) if manifest_dir.exists() else []
    summaries: list[dict[str, Any]] = []
    for manifest_file in manifest_files:
        manifest = read_json(manifest_file, {})
        if not manifest:
            continue
        summaries.append(
            {
                "manifest_id": manifest.get("manifest_id"),
                "created_at": manifest.get("created_at"),
                "source_name": manifest.get("source_name"),
                "target_root": manifest.get("target_root"),
                "file_count": manifest.get("file_count", 0),
                "excluded_count": manifest.get("excluded_count", 0),
                "role_counts": manifest.get("role_counts", {}),
                "warnings": manifest.get("warnings", []),
            }
        )
    if not summaries:
        summaries = [current_summary]

    aggregate_roles: dict[str, int] = {}
    warnings: list[str] = []
    for summary in summaries:
        for role, count in dict(summary.get("role_counts") or {}).items():
            aggregate_roles[str(role)] = aggregate_roles.get(str(role), 0) + int(count)
        for warning in list(summary.get("warnings") or []):
            text = str(warning)
            if text not in warnings:
                warnings.append(text)
    if len(summaries) > 1:
        warnings.insert(0, f"{len(summaries)} material imports are present; research planning must consider every manifest.")

    aggregate = {
        "schema_version": "research-material-manifest-summary-v1",
        "manifest_id": "aggregate",
        "created_at": now_iso(),
        "source_name": summaries[0].get("source_name") if len(summaries) == 1 else f"{len(summaries)} material imports",
        "target_root": summaries[0].get("target_root") if len(summaries) == 1 else "multiple",
        "file_count": sum(int(summary.get("file_count") or 0) for summary in summaries),
        "excluded_count": sum(int(summary.get("excluded_count") or 0) for summary in summaries),
        "role_counts": aggregate_roles,
        "warnings": warnings,
        "imports": summaries,
    }
    write_json(project_root / "PUBLIC" / "material_manifest_summary.json", aggregate)


def classify_material_role(relative_path: Path) -> str:
    lowered = relative_path.as_posix().lower()
    name = relative_path.name.lower()
    suffix = relative_path.suffix.lower()
    stem = relative_path.stem.lower()
    if "template" in lowered or suffix in {".cls", ".bst", ".sty"}:
        return "venue_template"
    if any(marker in lowered for marker in ("guide", "requirement", "instruction", "submission", "author")):
        return "venue_instruction"
    if suffix == ".bib":
        return "bibliography"
    if suffix in {".tex", ".ltx"} and any(marker in stem for marker in ("main", "draft", "paper", "manuscript", "article")):
        return "manuscript_draft"
    if suffix in {".pdf"} and any(marker in lowered for marker in ("reference", "example", "paper")):
        return "example_paper"
    if suffix in {".pdf"}:
        return "pdf_document"
    if suffix in {".ppt", ".pptx"}:
        return "slide_deck"
    if any(marker in lowered for marker in ("proof", "audit")):
        return "proof_audit"
    if any(marker in lowered for marker in ("review", "rebuttal", "response")):
        return "review_record"
    if suffix in {".md", ".txt", ".rst"}:
        return "note"
    if suffix in {".py", ".ipynb", ".js", ".ts", ".tsx", ".rs", ".cpp", ".c", ".h", ".m"}:
        return "code_or_notebook"
    if suffix in {".csv", ".tsv", ".json", ".yaml", ".yml", ".xlsx"}:
        return "data_or_structured_record"
    if suffix in {".png", ".jpg", ".jpeg", ".svg", ".webp"}:
        return "figure_or_screenshot"
    return "other_material"


def _skip_import_reason(relative_path: Path) -> str | None:
    parts = {part.lower() for part in relative_path.parts}
    skipped = parts.intersection(SKIP_IMPORT_PATH_PARTS)
    if skipped:
        return f"Skipped operational or build directory: {sorted(skipped)[0]}"
    return None


def _manifest_warnings(imported: list[dict[str, Any]], excluded: list[dict[str, str]]) -> list[str]:
    roles = [str(item.get("role")) for item in imported]
    warnings: list[str] = []
    if "manuscript_draft" not in roles:
        warnings.append("No manuscript-like .tex draft was detected; ask the researcher which file is the primary draft.")
    if roles.count("manuscript_draft") > 1:
        warnings.append("Multiple manuscript-like drafts were detected; require selection before paper production.")
    if "bibliography" not in roles:
        warnings.append("No bibliography file was detected; citation verification may need manual reference extraction.")
    if not any(role in roles for role in ("venue_template", "venue_instruction")):
        warnings.append("No venue template or author-instruction file was detected; verify the target venue online before writing.")
    if excluded:
        warnings.append(f"{len(excluded)} sensitive or secret-like file(s) were excluded from import.")
    return warnings


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(_windows_long_path(path), "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _copy2(source: Path, target: Path) -> None:
    if os.name == "nt":
        shutil.copy2(_windows_long_path(source), _windows_long_path(target))
        return
    shutil.copy2(source, target)


def _mkdir(path: Path) -> None:
    if os.name == "nt":
        os.makedirs(_windows_long_path(path), exist_ok=True)
        return
    path.mkdir(parents=True, exist_ok=True)


def _windows_long_path(path: Path) -> str:
    resolved = str(path.resolve())
    if resolved.startswith("\\\\?\\"):
        return resolved
    if resolved.startswith("\\\\"):
        return "\\\\?\\UNC\\" + resolved.lstrip("\\")
    return "\\\\?\\" + resolved


def classify_command(command: str, cwd: str | None = None) -> dict[str, Any]:
    stripped = command.strip()
    lowered = stripped.lower()
    risky_markers = [
        " --global",
        "npm install -g",
        "pip install --user",
        "setx ",
        "reg add",
        "sc.exe ",
        "schtasks ",
        "format ",
        "del /s",
        "remove-item -recurse",
        "git push",
        "gh release",
        "curl -x",
    ]
    if any(marker in lowered for marker in risky_markers):
        return {"risk": "high", "decision": "requires_confirmation", "reason": "External, global, or destructive command pattern."}
    if lowered.startswith("git "):
        parts = lowered.split()
        subcommand = parts[1] if len(parts) > 1 else ""
        if subcommand in SAFE_GIT_COMMANDS:
            return {"risk": "low", "decision": "allowed_in_sandbox", "reason": "Safe git operation inside project sandbox."}
        return {"risk": "medium", "decision": "requires_confirmation", "reason": "Git command can affect remotes or history."}
    return {"risk": "medium", "decision": "requires_confirmation", "reason": "Command requires Research OS approval."}


def validate_changed_paths(project_root: Path, paths: list[str]) -> None:
    for path in paths:
        normalized = path.replace("\\", "/")
        if normalized.startswith("PRIVATE/") or "/PRIVATE/" in normalized:
            raise SecurityError(f"Archive refuses PRIVATE path: {path}")
        resolved = resolve_under(project_root, normalized)
        assert_no_secret_path(resolved)
        scan_text_for_secrets(resolved)


def redact_sensitive(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            lowered = str(key).lower()
            if _is_safe_usage_telemetry(lowered, item):
                redacted[key] = redact_sensitive(item)
                continue
            if any(marker in lowered for marker in ("api_key", "apikey", "authorization", "cookie", "password", "secret", "token")):
                redacted[key] = "[REDACTED]"
            else:
                redacted[key] = redact_sensitive(item)
        return redacted
    if isinstance(value, list):
        return [redact_sensitive(item) for item in value]
    if isinstance(value, str) and "data:image/" in value:
        if value.startswith("data:image/"):
            return "[REDACTED_IMAGE_DATA_URL]"
        return re.sub(r"data:image/[^\"'\s<>]+", "[REDACTED_IMAGE_DATA_URL]", value)
    if isinstance(value, str) and SECRET_RE.search(value):
        return "[REDACTED]"
    return value


def _is_safe_usage_telemetry(lowered_key: str, value: Any) -> bool:
    if "authorization" in lowered_key or "password" in lowered_key or "secret" in lowered_key:
        return False
    if lowered_key in {"tokenusage", "token_usage", "usage", "total_usage"} and isinstance(value, (dict, list, int, float)):
        return True
    if isinstance(value, (int, float)) and (
        lowered_key.endswith("tokens")
        or lowered_key.endswith("_tokens")
        or lowered_key.endswith("token_count")
        or lowered_key.endswith("tokencount")
        or lowered_key in {"inputtokens", "outputtokens", "prompttokens", "completiontokens", "reasoningtokens"}
    ):
        return True
    return False

