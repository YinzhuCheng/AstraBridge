from __future__ import annotations

import argparse
import json
import subprocess
import sys
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "apps" / "astrabridge-sidecar"))

from astrabridge_sidecar.security import DESKTOP_KEY_PATH_RE, SECRET_QUERY_RE, redact_sensitive


TEXT_SUFFIXES = {
    ".css",
    ".html",
    ".js",
    ".json",
    ".jsonl",
    ".log",
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

RAW_SUFFIXES = TEXT_SUFFIXES | {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
}

SCREENSHOT_SUFFIXES = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
}

REPORT_SUFFIXES = {
    ".json",
    ".md",
}

VALIDATION_SUFFIXES = {
    ".json",
}

ALLOWED_BUCKETS = {
    "raw",
    "reports",
    "screenshots",
    "validations",
}

DEFAULT_PUBLIC_DOCS = [
    "docs/SECURITY_AND_ISOLATION.md",
    "docs/APP_HARDENING_UI_SCREENSHOT_QA.md",
    "docs/RELEASE_CHECKLIST.md",
]

SECRET_CONTENT_REGEXES = [
    re.compile(r"Authorization\s*:\s*Bearer\s+(?!\[?REDACTED\]?|<|xxx|example)[A-Za-z0-9._~+/=-]{12,}", re.I),
    re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bghp_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bAIza[0-9A-Za-z_-]{20,}\b"),
    re.compile(
        r"\b(api[_-]?key|token|secret|password|cookie|authorization)\b\s*[:=]\s*[\"']?"
        r"(?!\[?REDACTED\]?|<|xxx|example|dummy|fixture|unit|test|not_available|source|status|reason)"
        r"[A-Za-z0-9._~+/=-]{12,}[\"']?",
        re.I,
    ),
]


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


def git_ls_files(repo: Path, pattern: str) -> list[str]:
    try:
        completed = subprocess.run(
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
    if completed.returncode != 0:
        return []
    return [line.strip().replace("\\", "/") for line in completed.stdout.splitlines() if line.strip()]


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def iter_text_files(root: Path) -> Iterable[Path]:
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.suffix.lower() in TEXT_SUFFIXES:
            yield path


def check_artifact_layout(repo: Path, artifact_root: Path) -> list[Finding]:
    findings: list[Finding] = []
    if not artifact_root.exists():
        findings.append(
            Finding(
                severity="error",
                code="artifact-root-missing",
                path=normalize_path(artifact_root, repo) if artifact_root.is_absolute() and artifact_root.exists() else artifact_root.as_posix(),
                line=0,
                message="App-hardening artifact root does not exist.",
            )
        )
        return findings
    for child in sorted(artifact_root.iterdir()):
        if child.name not in ALLOWED_BUCKETS:
            findings.append(
                Finding(
                    severity="error",
                    code="unexpected-artifact-bucket",
                    path=normalize_path(child, repo),
                    line=0,
                    message="App-hardening artifacts must live under raw, reports, screenshots, or validations.",
                )
            )
    for path in sorted(artifact_root.rglob("*")):
        if not path.is_file():
            continue
        rel = normalize_path(path, repo)
        relative = path.relative_to(artifact_root)
        if not relative.parts:
            continue
        bucket = relative.parts[0]
        suffix = path.suffix.lower()
        if bucket == "screenshots" and suffix not in SCREENSHOT_SUFFIXES:
            findings.append(
                Finding(
                    severity="error",
                    code="unexpected-screenshot-file",
                    path=rel,
                    line=0,
                    message="Screenshot bucket should contain only image files.",
                )
            )
        elif bucket == "reports" and suffix not in REPORT_SUFFIXES:
            findings.append(
                Finding(
                    severity="error",
                    code="unexpected-report-file",
                    path=rel,
                    line=0,
                    message="Report bucket should contain only .json or .md files.",
                )
            )
        elif bucket == "validations" and suffix not in VALIDATION_SUFFIXES:
            findings.append(
                Finding(
                    severity="error",
                    code="unexpected-validation-file",
                    path=rel,
                    line=0,
                    message="Validation bucket should contain only .json files.",
                )
            )
        elif bucket == "raw" and suffix not in RAW_SUFFIXES:
            findings.append(
                Finding(
                    severity="warning",
                    code="unexpected-raw-file",
                    path=rel,
                    line=0,
                    message="Raw bucket contains an unexpected file type; confirm the retention rule intentionally allows it.",
                )
            )
    for rel in git_ls_files(repo, f"{artifact_root.relative_to(repo).as_posix()}/**"):
        findings.append(
            Finding(
                severity="error",
                code="tracked-private-artifact",
                path=rel,
                line=0,
                message="PRIVATE app-hardening artifacts must stay untracked.",
            )
        )
    return findings


def _is_redacted_or_placeholder(value: str) -> bool:
    normalized = value.strip().strip("\"'").lower()
    return normalized in {
        "[redacted]",
        "<redacted>",
        "example",
        "dummy",
        "fixture",
        "test",
        "not_available",
    }


def check_text_file(repo: Path, path: Path) -> list[Finding]:
    findings: list[Finding] = []
    rel = normalize_path(path, repo)
    text = read_text(path)
    for index, line in enumerate(text.splitlines(), start=1):
        excerpt = str(redact_sensitive(line)).strip()[:180]
        if DESKTOP_KEY_PATH_RE.search(line):
            findings.append(
                Finding(
                    severity="error",
                    code="desktop-key-path",
                    path=rel,
                    line=index,
                    message="Desktop key-file path leaked into durable evidence or public docs.",
                    excerpt=excerpt,
                )
            )
            continue
        for pattern in SECRET_CONTENT_REGEXES:
            if pattern.search(line):
                findings.append(
                    Finding(
                        severity="error",
                        code="secret-like",
                        path=rel,
                        line=index,
                        message="Secret-like content found; redact it before preserving evidence.",
                        excerpt=excerpt,
                    )
                )
                break
        else:
            for match in SECRET_QUERY_RE.finditer(line):
                if _is_redacted_or_placeholder(match.group(2)):
                    continue
                findings.append(
                    Finding(
                        severity="error",
                        code="secret-query",
                        path=rel,
                        line=index,
                        message="Secret-like query parameter found; redact it before preserving evidence.",
                        excerpt=excerpt,
                    )
                )
                break
    return findings


def check_repo(repo: Path, artifact_root: str | Path = "PRIVATE/app-hardening", public_docs: Iterable[str | Path] | None = None) -> dict[str, object]:
    repo = repo.resolve()
    artifact_root_path = (repo / artifact_root).resolve() if not Path(artifact_root).is_absolute() else Path(artifact_root).resolve()
    docs = [Path(item) for item in (public_docs or [])]
    findings: list[Finding] = []
    findings.extend(check_artifact_layout(repo, artifact_root_path))

    scanned_files = 0
    if artifact_root_path.exists():
        for path in iter_text_files(artifact_root_path):
            scanned_files += 1
            findings.extend(check_text_file(repo, path))
    for item in docs:
        target = (repo / item).resolve() if not item.is_absolute() else item.resolve()
        if not target.exists():
            findings.append(
                Finding(
                    severity="warning",
                    code="missing-public-doc",
                    path=item.as_posix().replace("\\", "/"),
                    line=0,
                    message="Requested public doc was not found and could not be scanned.",
                )
            )
            continue
        scanned_files += 1
        findings.extend(check_text_file(repo, target))

    counts = {"error": 0, "warning": 0, "info": 0}
    for finding in findings:
        counts[finding.severity] = counts.get(finding.severity, 0) + 1
    return {
        "ok": counts["error"] == 0,
        "repo": str(repo),
        "artifact_root": normalize_path(artifact_root_path, repo) if artifact_root_path.exists() else artifact_root_path.as_posix(),
        "public_docs": [item.as_posix().replace("\\", "/") for item in docs],
        "scanned_files": scanned_files,
        "counts": counts,
        "findings": [asdict(item) for item in findings],
    }


def print_report(report: dict[str, object]) -> None:
    counts = report["counts"]
    print(
        "AstraBridge app-hardening secret scan: "
        f"{counts['error']} error(s), {counts['warning']} warning(s), {counts['info']} info item(s); "
        f"{report['scanned_files']} text file(s) scanned."
    )
    for finding in report["findings"]:
        location = finding["path"]
        if finding["line"]:
            location = f"{location}:{finding['line']}"
        print(f"[{finding['severity']}] {finding['code']} {location} - {finding['message']}")
        if finding["excerpt"]:
            print(f"  {finding['excerpt']}")


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Scan AstraBridge app-hardening evidence for secret leakage and retention drift.")
    parser.add_argument("--repo", default=".", help="Repository root to scan.")
    parser.add_argument("--artifact-root", default="PRIVATE/app-hardening", help="Artifact root to audit.")
    parser.add_argument("--public-doc", action="append", default=None, help="Public doc path to include in the scan. May be repeated.")
    parser.add_argument("--json-out", help="Optional JSON report path.")
    args = parser.parse_args(argv)

    report = check_repo(Path(args.repo), artifact_root=args.artifact_root, public_docs=args.public_doc or DEFAULT_PUBLIC_DOCS)
    print_report(report)
    if args.json_out:
        out = Path(args.json_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
