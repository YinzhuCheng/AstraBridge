from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from .common import append_jsonl, now_iso, read_json, write_json
from .security import validate_changed_paths


class ArchiveService:
    def __init__(self, project_root_provider) -> None:
        self._project_root_provider = project_root_provider

    def preview(self) -> dict[str, Any]:
        root = self._project_root_provider()
        changed = self._changed_paths(root)
        validate_changed_paths(root, changed)
        return {
            "ok": True,
            "phase": self._phase(root)[0],
            "macro_phase": self._phase(root)[1],
            "git_branch": self._git(root, ["rev-parse", "--abbrev-ref", "HEAD"], required=False).strip() or "unknown",
            "git_commit": self._git(root, ["rev-parse", "HEAD"], required=False).strip() or "none",
            "dirty": bool(changed),
            "changed_paths": changed,
            "private_paths_included": False,
            "secrets_scan": "passed",
            "status": "preview",
        }

    def create(self, description: str, user_free_form: str = "", macro_phase: str | None = None) -> dict[str, Any]:
        if not description.strip():
            raise ValueError("Archive description is required.")
        root = self._project_root_provider()
        preview = self.preview()
        if preview["changed_paths"]:
            self._git(root, ["add", "--all", "--", "."])
            self._git(
                root,
                [
                    "-c",
                    "user.name=AstraBridge Archive",
                    "-c",
                    "user.email=research-os-archive@example.invalid",
                    "commit",
                    "-m",
                    f"archive snapshot: {description[:72]}",
                ],
            )
        archive_id = f"ARCH-{now_iso().replace(':', '').replace('-', '').split('.')[0]}"
        phase, default_macro_phase = self._phase(root)
        record = {
            "archive_id": archive_id,
            "created_at": now_iso(),
            "phase": phase,
            "macro_phase": macro_phase or default_macro_phase or "unknown",
            "git_commit": self._git(root, ["rev-parse", "HEAD"], required=False).strip() or "none",
            "git_branch": self._git(root, ["rev-parse", "--abbrev-ref", "HEAD"], required=False).strip() or "unknown",
            "description": description.strip(),
            "user_free_form": user_free_form,
            "changed_paths": preview["changed_paths"],
            "public_index_path": "PUBLIC/archive_index.json",
            "private_paths_included": False,
            "secrets_scan": "passed",
            "status": "created",
        }
        append_jsonl(root / "PROVENANCE" / "archive_index.jsonl", record)
        self._write_public_index(root)
        self._git(root, ["add", "--", "PROVENANCE/archive_index.jsonl", "PUBLIC/archive_index.json"])
        self._git(
            root,
            [
                "-c",
                "user.name=AstraBridge Archive",
                "-c",
                "user.email=research-os-archive@example.invalid",
                "commit",
                "-m",
                f"archive index: {archive_id}",
            ],
            required=False,
        )
        return record

    def list_archives(self) -> dict[str, Any]:
        root = self._project_root_provider()
        path = root / "PROVENANCE" / "archive_index.jsonl"
        archives = []
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    archives.append(json.loads(line))
        return {"archives": archives}

    def _write_public_index(self, root: Path) -> None:
        public = []
        for item in self.list_archives()["archives"]:
            public.append(
                {
                    "archive_id": item.get("archive_id"),
                    "created_at": item.get("created_at"),
                    "phase": item.get("phase"),
                    "macro_phase": item.get("macro_phase"),
                    "git_commit": item.get("git_commit"),
                    "git_branch": item.get("git_branch"),
                    "description": item.get("description"),
                    "changed_path_count": len(item.get("changed_paths", [])),
                    "status": item.get("status"),
                }
            )
        write_json(root / "PUBLIC" / "archive_index.json", {"archives": public})

    def _changed_paths(self, root: Path) -> list[str]:
        output = self._git(root, ["status", "--porcelain"], required=False)
        paths: list[str] = []
        for line in output.splitlines():
            if not line.strip():
                continue
            path = line[3:].strip()
            if " -> " in path:
                path = path.split(" -> ", 1)[1]
            paths.append(path.replace("\\", "/"))
        return paths

    def _phase(self, root: Path) -> tuple[str, str]:
        project_state = read_json(root / ".research-os" / "project.json", {})
        if project_state.get("current_phase") or project_state.get("current_macro_phase"):
            return (
                str(project_state.get("current_phase") or "unknown"),
                str(project_state.get("current_macro_phase") or "unknown"),
            )
        research_state = read_json(root / "PUBLIC" / "research_state.json", {})
        if research_state.get("internal_phase") or research_state.get("macro_phase"):
            return (
                str(research_state.get("internal_phase") or "unknown"),
                str(research_state.get("macro_phase") or "unknown"),
            )
        project = (root / "config" / "research_project.yaml")
        phase = "unknown"
        macro = "unknown"
        if project.exists():
            for line in project.read_text(encoding="utf-8", errors="replace").splitlines():
                if line.startswith("current_phase:"):
                    phase = line.split(":", 1)[1].strip().strip('"')
                if line.startswith("current_macro_phase:"):
                    macro = line.split(":", 1)[1].strip().strip('"')
        return phase, macro

    def _git(self, root: Path, args: list[str], required: bool = True) -> str:
        result = subprocess.run(["git", *args], cwd=root, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        if required and result.returncode != 0:
            raise RuntimeError((result.stderr or result.stdout).strip())
        return result.stdout

