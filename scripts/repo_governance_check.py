from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable
from urllib.parse import unquote


TEXT_SUFFIXES = {
    ".css",
    ".html",
    ".js",
    ".jsx",
    ".json",
    ".md",
    ".mjs",
    ".ps1",
    ".py",
    ".toml",
    ".ts",
    ".tsx",
    ".txt",
    ".yaml",
    ".yml",
}

SKIP_DIRS = {
    ".git",
    ".mypy_cache",
    ".pnpm-store",
    ".pytest_cache",
    ".ruff_cache",
    ".tmp",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
    "playwright-report",
    "target",
    "test-results",
    "tmp",
}

MOJIBAKE_PATTERNS = [
    "Ã",
    "Â",
    "â€™",
    "â€œ",
    "â€",
    "锟斤拷",
    "�",
    "鈥",
    "灏",
    "鐨",
    "绋",
    "鎵",
    "璺",
    "鏄",
    "熸",
    "ˉ",
    "妫€",
    "杩斿洖",
    "浠诲姟",
    "澶瑰",
    "杈撳嚭",
    "鏈€",
    "鍥綻",
    "鏌ュ櫒",
]

LEGACY_PATTERNS = [
    ".lcrproj",
    ".lcr/",
    ".codexproj",
    ".codex-shell",
    "lcr-models",
    "official OpenAI account login",
    "OpenAI account login",
]

LEGACY_REGEXES = [
    re.compile(r"\blcr_[A-Za-z0-9_]*\b"),
]

RETIRED_RUNTIME_SYMBOLS = {
    "ProviderAdapter",
    "QwenResponsesAdapter",
    "ChatCompletionsAdapter",
    "DeepSeekChatAdapter",
    "KimiChatAdapter",
}

SECRET_REGEXES = [
    re.compile(r"Authorization\s*:\s*Bearer\s+(?!\[?REDACTED\]?|<|xxx|example)[A-Za-z0-9._\-]{12,}", re.I),
    re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"),
    re.compile(
        r"\b(api[_-]?key|token|secret|password)\b\s*[:=]\s*[\"']?"
        r"(?!\[?REDACTED\]?|<|xxx|example|dummy|fixture|unit|test|not_available|source|status|reason)"
        r"[A-Za-z0-9_\-./+=]{20,}[\"']",
        re.I,
    ),
]

NEGATIVE_OR_GUARDRAIL_WORDS = {
    "archive",
    "archived",
    "compat",
    "compatibility",
    "does not",
    "do not",
    "do not depend",
    "guardrail",
    "historical",
    "legacy",
    "non-goal",
    "negative",
    "not ",
    "not supported",
    "only",
    "out of scope",
    "preserved",
    "reject",
    "shim",
    "unsupported",
}

ALLOWED_PRIVATE_TRACKED = {"PRIVATE/README.md"}
DOCUMENT_REGISTRY_PATH = "docs/DOCUMENT_REGISTRY.json"
PUBLIC_ROOT_DOCUMENTS = {
    "AGENTS.md",
    "README.md",
    "CONTRIBUTING.md",
    "CODE_OF_CONDUCT.md",
    "SECURITY.md",
}
DOCUMENT_REGISTRY_REQUIRED_FIELDS = {
    "path",
    "status",
    "owner",
    "scope",
    "last_verified",
    "replacement",
    "archive_policy",
}
DOCUMENT_REGISTRY_STATUSES = {"active", "complete", "superseded", "archived", "reference"}
CURRENT_GUIDANCE_STATUSES = {"active", "reference"}
HISTORICAL_DOCUMENT_STATUSES = {"complete", "superseded", "archived"}
MARKDOWN_LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")


@dataclass(frozen=True)
class Finding:
    severity: str
    code: str
    path: str
    line: int
    message: str
    excerpt: str = ""


def normalize_path(path: Path, repo: Path) -> str:
    return path.resolve().relative_to(repo.resolve()).as_posix()


def is_test_path(rel: str) -> bool:
    parts = set(rel.split("/"))
    name = Path(rel).name
    return "tests" in parts or name.startswith("test_") or name.endswith(".test.ts") or name.endswith(".test.tsx")


def is_archive_or_history_path(rel: str) -> bool:
    return (
        rel.startswith("docs/archive/")
        or rel.startswith("PLAN/")
        or rel in {"docs/PROJECT_LOG.md", "docs/LEGACY_CLEANUP_AUDIT.md"}
    )


def is_governance_rule_path(rel: str) -> bool:
    return rel in {
        "scripts/repo_governance_check.py",
        "docs/REPO_GOVERNANCE.md",
    }


def is_interface_inventory_path(rel: str) -> bool:
    return rel in {
        "scripts/interface_registry_audit.py",
        "docs/INTERFACE_GOVERNANCE.md",
    }


def is_allowed_guardrail_code_path(rel: str) -> bool:
    return rel in {
        "apps/astrabridge-sidecar/astrabridge_sidecar/isolation_audit_service.py",
        "apps/astrabridge-sidecar/astrabridge_sidecar/project_context_service.py",
    }


def is_allowed_shim_path(rel: str) -> bool:
    return rel in {
        "apps/astrabridge-sidecar/astrabridge_sidecar/lcr_web_mcp_server.py",
        "apps/astrabridge-sidecar/astrabridge_sidecar/lcr_web_service.py",
    }


def has_guardrail_language(line: str) -> bool:
    lowered = line.lower()
    if lowered.strip().startswith("rg -n"):
        return True
    return any(word in lowered for word in NEGATIVE_OR_GUARDRAIL_WORDS)


def iter_text_files(repo: Path) -> Iterable[Path]:
    for root, dirs, files in os.walk(repo):
        root_path = Path(root)
        rel_parts = root_path.resolve().relative_to(repo.resolve()).parts
        if any(part in SKIP_DIRS for part in rel_parts):
            dirs[:] = []
            continue
        dirs[:] = [
            name
            for name in dirs
            if name not in SKIP_DIRS and name != "PRIVATE" and not name.endswith(".egg-info")
        ]
        for name in files:
            path = root_path / name
            if path.suffix.lower() in TEXT_SUFFIXES:
                yield path


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def expected_document_registry_paths(repo: Path) -> set[str]:
    paths: set[str] = set()
    for rel in PUBLIC_ROOT_DOCUMENTS | {DOCUMENT_REGISTRY_PATH}:
        if (repo / rel).is_file():
            paths.add(rel)
    docs_root = repo / "docs"
    if docs_root.is_dir():
        paths.update(normalize_path(path, repo) for path in docs_root.rglob("*.md") if path.is_file())
    plan_root = repo / "PLAN"
    if plan_root.is_dir():
        paths.update(normalize_path(path, repo) for path in plan_root.iterdir() if path.is_file())
    return paths


def load_document_registry(repo: Path) -> tuple[dict[str, str], list[Finding]]:
    registry_path = repo / DOCUMENT_REGISTRY_PATH
    if not registry_path.is_file():
        return {}, []

    findings: list[Finding] = []
    try:
        payload = json.loads(read_text(registry_path))
    except (OSError, json.JSONDecodeError) as exc:
        return {}, [
            Finding(
                severity="error",
                code="document-registry-invalid",
                path=DOCUMENT_REGISTRY_PATH,
                line=0,
                message=f"Document registry is not valid UTF-8 JSON: {exc}",
            )
        ]

    entries = payload.get("entries")
    if not isinstance(entries, list):
        return {}, [
            Finding(
                severity="error",
                code="document-registry-invalid",
                path=DOCUMENT_REGISTRY_PATH,
                line=0,
                message="Document registry must contain an entries array.",
            )
        ]

    status_by_path: dict[str, str] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            findings.append(
                Finding(
                    severity="error",
                    code="document-registry-entry-invalid",
                    path=DOCUMENT_REGISTRY_PATH,
                    line=0,
                    message="Every document registry entry must be an object.",
                )
            )
            continue
        rel = entry.get("path")
        if not isinstance(rel, str) or not rel:
            findings.append(
                Finding(
                    severity="error",
                    code="document-registry-entry-invalid",
                    path=DOCUMENT_REGISTRY_PATH,
                    line=0,
                    message="Every document registry entry must have a non-empty path.",
                )
            )
            continue
        missing_fields = sorted(DOCUMENT_REGISTRY_REQUIRED_FIELDS - set(entry))
        if missing_fields:
            findings.append(
                Finding(
                    severity="error",
                    code="document-registry-fields",
                    path=rel,
                    line=0,
                    message=f"Registry entry is missing required fields: {', '.join(missing_fields)}.",
                )
            )
        if rel in status_by_path:
            findings.append(
                Finding(
                    severity="error",
                    code="document-registry-duplicate",
                    path=rel,
                    line=0,
                    message="Document registry contains a duplicate path.",
                )
            )
        status = entry.get("status")
        if status not in DOCUMENT_REGISTRY_STATUSES:
            findings.append(
                Finding(
                    severity="error",
                    code="document-registry-status",
                    path=rel,
                    line=0,
                    message=f"Unknown document registry status: {status!r}.",
                )
            )
        else:
            status_by_path[rel] = status
        if not (repo / rel).is_file():
            findings.append(
                Finding(
                    severity="error",
                    code="document-registry-target-missing",
                    path=rel,
                    line=0,
                    message="Registered document or plan does not exist.",
                )
            )
        replacement = entry.get("replacement")
        if status == "superseded" and not replacement:
            findings.append(
                Finding(
                    severity="error",
                    code="document-registry-replacement",
                    path=rel,
                    line=0,
                    message="Superseded registry entry must name a replacement.",
                )
            )
        if replacement and (not isinstance(replacement, str) or not (repo / replacement).is_file()):
            findings.append(
                Finding(
                    severity="error",
                    code="document-registry-replacement",
                    path=rel,
                    line=0,
                    message=f"Registry replacement does not exist: {replacement!r}.",
                )
            )

    expected = expected_document_registry_paths(repo)
    actual = set(status_by_path)
    for rel in sorted(expected - actual):
        findings.append(
            Finding(
                severity="error",
                code="document-registry-unregistered",
                path=rel,
                line=0,
                message="Current documentation or plan file is missing from the registry.",
            )
        )
    for rel in sorted(actual - expected):
        findings.append(
            Finding(
                severity="error",
                code="document-registry-extra",
                path=rel,
                line=0,
                message="Registry path is outside the canonical documentation and plan inventory.",
            )
        )

    current_plan = payload.get("current_execution_plan")
    conditional = payload.get("conditional_execution_plans", [])
    conditional_paths = {
        item.get("path")
        for item in conditional
        if isinstance(item, dict) and isinstance(item.get("path"), str)
    }
    allowed_active_plans = ({current_plan} if isinstance(current_plan, str) else set()) | conditional_paths
    active_plans = {rel for rel, status in status_by_path.items() if rel.startswith("PLAN/") and status == "active"}
    for rel in sorted(active_plans - allowed_active_plans):
        findings.append(
            Finding(
                severity="error",
                code="document-registry-active-plan",
                path=rel,
                line=0,
                message="Active plan is not the current plan or an explicitly conditional plan.",
            )
        )
    for rel in sorted(allowed_active_plans - active_plans):
        findings.append(
            Finding(
                severity="error",
                code="document-registry-active-plan",
                path=str(rel),
                line=0,
                message="Current or conditional execution plan is not registered as active.",
            )
        )
    return status_by_path, findings


def git_ls_files(repo: Path, pattern: str) -> list[str]:
    try:
        result = subprocess.run(
            ["git", "ls-files", pattern],
            cwd=repo,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except OSError:
        return []
    if result.returncode != 0:
        return []
    return [line.strip().replace("\\", "/") for line in result.stdout.splitlines() if line.strip()]


def check_private_tracking(repo: Path) -> list[Finding]:
    findings: list[Finding] = []
    for rel in git_ls_files(repo, "PRIVATE/**"):
        if rel not in ALLOWED_PRIVATE_TRACKED:
            findings.append(
                Finding(
                    severity="error",
                    code="private-tracked",
                    path=rel,
                    line=0,
                    message="PRIVATE artifacts must not be tracked unless explicitly allowed.",
                )
            )
    return findings


def check_mojibake(rel: str, lines: list[str], registry_status: str | None = None) -> list[Finding]:
    findings: list[Finding] = []
    for index, line in enumerate(lines, start=1):
        for marker in MOJIBAKE_PATTERNS:
            if marker in line:
                severity = (
                    "info"
                    if is_test_path(rel)
                    or is_governance_rule_path(rel)
                    or registry_status in HISTORICAL_DOCUMENT_STATUSES
                    else "error"
                )
                findings.append(
                    Finding(
                        severity=severity,
                        code="mojibake",
                        path=rel,
                        line=index,
                        message="Potential mojibake marker found.",
                        excerpt=line.strip()[:180],
                    )
                )
                break
    return findings


def check_secrets(rel: str, lines: list[str]) -> list[Finding]:
    findings: list[Finding] = []
    for index, line in enumerate(lines, start=1):
        for pattern in SECRET_REGEXES:
            if pattern.search(line):
                severity = "info" if is_test_path(rel) else "error"
                findings.append(
                    Finding(
                        severity=severity,
                        code="secret-like",
                        path=rel,
                        line=index,
                        message="Secret-like string found; redact or prove it is a safe fixture.",
                        excerpt=line.strip()[:180],
                    )
                )
                break
    return findings


def line_has_legacy_marker(line: str) -> bool:
    if any(marker in line for marker in LEGACY_PATTERNS):
        return True
    return any(pattern.search(line) for pattern in LEGACY_REGEXES)


def check_legacy(rel: str, lines: list[str], registry_status: str | None = None) -> list[Finding]:
    findings: list[Finding] = []
    history_path_allowed = is_archive_or_history_path(rel)
    if rel.startswith("PLAN/") and registry_status in CURRENT_GUIDANCE_STATUSES:
        history_path_allowed = False
    allowed_context = (
        history_path_allowed
        or is_test_path(rel)
        or is_allowed_shim_path(rel)
        or is_allowed_guardrail_code_path(rel)
        or is_governance_rule_path(rel)
    )
    for index, line in enumerate(lines, start=1):
        if not line_has_legacy_marker(line):
            continue
        nearby_context = " ".join(lines[max(0, index - 5) : index])
        if allowed_context:
            severity = "info"
            message = "Legacy marker appears in archive, completed history, shim, or test context."
        elif has_guardrail_language(nearby_context):
            severity = "info"
            message = "Legacy marker appears with guardrail or compatibility language."
        elif registry_status in CURRENT_GUIDANCE_STATUSES:
            severity = "error"
            message = "Legacy marker appears in registered current guidance without clear guardrail wording."
        elif rel.startswith("apps/") or rel.startswith("scripts/"):
            severity = "error"
            message = "Legacy marker appears in active code outside an allowed shim, test, or guardrail context."
        else:
            severity = "warning"
            message = "Legacy marker appears in active documentation without clear guardrail wording."
        findings.append(
            Finding(
                severity=severity,
                code="legacy-marker",
                path=rel,
                line=index,
                message=message,
                excerpt=line.strip()[:180],
            )
        )
    return findings


def check_retired_runtime_symbols(rel: str, lines: list[str]) -> list[Finding]:
    findings: list[Finding] = []
    allowed_context = (
        is_test_path(rel)
        or is_governance_rule_path(rel)
        or is_interface_inventory_path(rel)
        or is_archive_or_history_path(rel)
    )
    for index, line in enumerate(lines, start=1):
        for symbol in RETIRED_RUNTIME_SYMBOLS:
            if not re.search(rf"\b{re.escape(symbol)}\b", line):
                continue
            if allowed_context:
                severity = "info"
                message = "Retired runtime symbol appears in inventory, history, archive, or test context."
            elif rel.startswith("apps/") or rel.startswith("scripts/"):
                severity = "error"
                message = "Retired runtime symbol appears in current code outside the canonical transport registry."
            else:
                severity = "warning"
                message = "Retired runtime symbol appears in current documentation without an explicit historical context."
            findings.append(
                Finding(
                    severity=severity,
                    code="retired-runtime-symbol",
                    path=rel,
                    line=index,
                    message=message,
                    excerpt=line.strip()[:180],
                )
            )
    return findings


def resolve_markdown_target(repo: Path, source: Path, raw_target: str) -> Path | None:
    target = unquote(raw_target.strip().strip("<>")).split("#", 1)[0]
    if not target or target.startswith("#"):
        return None
    if re.match(r"^[A-Za-z][A-Za-z0-9+.-]*://", target) or target.startswith("mailto:"):
        return None
    if re.match(r"^/[A-Za-z]:[/\\]", target):
        candidate = Path(target[1:])
    elif re.match(r"^[A-Za-z]:[/\\]", target):
        candidate = Path(target)
    else:
        candidate = source.parent / target
    if candidate.exists():
        return candidate
    line_suffix = re.match(r"^(.*?):\d+(?::\d+)?$", str(candidate))
    if line_suffix:
        without_line = Path(line_suffix.group(1))
        if without_line.exists():
            return without_line
    return candidate


def check_markdown_links(repo: Path, rel: str, lines: list[str], registry_status: str | None) -> list[Finding]:
    if registry_status not in CURRENT_GUIDANCE_STATUSES or not rel.endswith(".md"):
        return []
    source = repo / rel
    findings: list[Finding] = []
    in_fence = False
    for index, line in enumerate(lines, start=1):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        for match in MARKDOWN_LINK_RE.finditer(line):
            raw_target = match.group(1)
            target = resolve_markdown_target(repo, source, raw_target)
            if target is None or target.exists():
                continue
            findings.append(
                Finding(
                    severity="error",
                    code="current-doc-link-missing",
                    path=rel,
                    line=index,
                    message=f"Registered current guidance links to a missing local target: {raw_target}.",
                    excerpt=line.strip()[:180],
                )
            )
    return findings


def check_active_plan_language(rel: str, lines: list[str]) -> list[Finding]:
    if rel not in {"AGENTS.md", "README.md", "docs/PROJECT_SUMMARY.md", "docs/HANDOFF.md"}:
        return []
    findings: list[Finding] = []
    for index, line in enumerate(lines, start=1):
        lowered = line.lower()
        misleading_context = any(
            marker in lowered
            for marker in [
                "active source of truth",
                "current execution focus",
                "current source of truth",
                "active plan",
            ]
        )
        if "active_repository_normalization_execution.md" in lowered and misleading_context and "complete" not in lowered and "completed" not in lowered:
            findings.append(
                Finding(
                    severity="warning",
                    code="normalization-active-wording",
                    path=rel,
                    line=index,
                    message="Completed normalization record is referenced without explicit completed wording.",
                    excerpt=line.strip()[:180],
                )
            )
    return findings


def check_repo(repo: Path) -> dict[str, object]:
    repo = repo.resolve()
    findings: list[Finding] = []
    findings.extend(check_private_tracking(repo))
    status_by_path, registry_findings = load_document_registry(repo)
    findings.extend(registry_findings)

    scanned_files = 0
    for path in iter_text_files(repo):
        rel = normalize_path(path, repo)
        text = read_text(path)
        lines = text.splitlines()
        registry_status = status_by_path.get(rel)
        scanned_files += 1
        findings.extend(check_mojibake(rel, lines, registry_status))
        findings.extend(check_secrets(rel, lines))
        findings.extend(check_legacy(rel, lines, registry_status))
        findings.extend(check_retired_runtime_symbols(rel, lines))
        findings.extend(check_markdown_links(repo, rel, lines, registry_status))
        findings.extend(check_active_plan_language(rel, lines))

    counts = {"error": 0, "warning": 0, "info": 0}
    for finding in findings:
        counts[finding.severity] = counts.get(finding.severity, 0) + 1

    return {
        "ok": counts.get("error", 0) == 0,
        "repo": str(repo),
        "scanned_files": scanned_files,
        "counts": counts,
        "findings": [asdict(finding) for finding in findings],
    }


def print_report(report: dict[str, object], *, verbose: bool = False) -> None:
    counts = report["counts"]
    print(
        "AstraBridge governance check: "
        f"{counts['error']} error(s), {counts['warning']} warning(s), {counts['info']} info item(s); "
        f"{report['scanned_files']} text file(s) scanned."
    )
    for finding in report["findings"]:
        if finding["severity"] == "info" and not verbose:
            continue
        location = finding["path"]
        if finding["line"]:
            location = f"{location}:{finding['line']}"
        print(f"[{finding['severity']}] {finding['code']} {location} - {finding['message']}")
        if finding["excerpt"]:
            print(f"  {finding['excerpt']}")


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Run AstraBridge repository governance checks.")
    parser.add_argument("--repo", default=".", help="Repository root to scan.")
    parser.add_argument("--json-out", help="Optional path for a machine-readable JSON report.")
    parser.add_argument("--verbose", action="store_true", help="Print informational findings as well as errors and warnings.")
    args = parser.parse_args(argv)

    repo = Path(args.repo).resolve()
    report = check_repo(repo)
    print_report(report, verbose=args.verbose)

    if args.json_out:
        out_path = Path(args.json_out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
