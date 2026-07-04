from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .security import SECRET_RE, SecurityError, redact_sensitive


GENERIC_PROJECT_TITLES = {
    "",
    "untitled",
    "untitled project",
    "new project",
    "default project",
    "project",
    "astrabridge-project",
    "codex-workspace",
}

GENERIC_TASK_TITLES = {
    "",
    "untitled",
    "untitled task",
    "new task",
    "default task",
    "task",
}


class TitleSuggestionService:
    def __init__(self, projects, tasks, router) -> None:
        self._projects = projects
        self._tasks = tasks
        self._router = router

    def suggest_project_title(self, *, force: bool = False) -> dict[str, Any]:
        project = self._projects.current_project
        if not project:
            raise ValueError("No project is open.")
        current_title = str(project.get("name") or "").strip()
        if not force and not self._project_title_is_generic(project):
            return {"title": current_title, "source": "unchanged", "changed": False, "project": project}

        context = self._project_context(project)
        suggested, source, error = self._suggest_title(context=context, fallback=self._heuristic_project_title(project))
        if source in {"llm", "heuristic"} and suggested and suggested != current_title:
            project = self._projects.update_project_title(suggested)
            return {"title": suggested, "source": source, "changed": True, "project": project, "error": error}
        return {"title": current_title or suggested, "source": source if suggested else "failed", "changed": False, "project": project, "error": error}

    def suggest_current_task_title(self, *, force: bool = False) -> dict[str, Any]:
        task = self._tasks.current_task()
        if not task:
            raise ValueError("No current task.")
        project = self._projects.current_project or {}
        current_title = str(task.get("title") or "").strip()
        if not force and not self._task_title_is_generic(task, project):
            return {"title": current_title, "source": "unchanged", "changed": False, "task": task, "project": project}

        context = self._task_context(task, project)
        suggested, source, error = self._suggest_title(context=context, fallback=self._heuristic_task_title(task, project))
        if source in {"llm", "heuristic"} and suggested and suggested != current_title:
            task = self._tasks.update_current_task_title(suggested)
            return {"title": suggested, "source": source, "changed": True, "task": task, "project": self._projects.current_project, "error": error}
        return {"title": current_title or suggested, "source": source if suggested else "failed", "changed": False, "task": task, "project": project, "error": error}

    def _suggest_title(self, *, context: dict[str, Any], fallback: str) -> tuple[str, str, str | None]:
        error: str | None = None
        model = self._model_id(context)
        if model:
            try:
                result = self._router.complete_response(
                    {
                        "model": model,
                        "input": [
                            {
                                "role": "system",
                                "content": [
                                    {
                                        "type": "input_text",
                                        "text": (
                                            "You generate concise UI titles for AstraBridge. "
                                            "Return only one title, no quotes, no markdown, no explanation. "
                                            "Prefer the user's language. Keep Chinese titles under 18 characters and English titles under 8 words."
                                        ),
                                    }
                                ],
                            },
                            {"role": "user", "content": [{"type": "input_text", "text": self._context_text(context)}]},
                        ],
                        "max_output_tokens": 48,
                        "temperature": 0.2,
                        "stream": False,
                    }
                )
                title = self._clean_title(self._normalized_text(result))
                if title:
                    return title, "llm", None
            except Exception as exc:
                error = f"{type(exc).__name__}: {str(exc)[:180]}"

        heuristic = self._clean_title(fallback)
        if heuristic:
            return heuristic, "heuristic", error
        return "", "failed", error

    def _model_id(self, context: dict[str, Any]) -> str:
        provider = str(context.get("provider_id") or "").strip()
        model = str(context.get("model") or "").strip()
        if "/" in model:
            return model
        if provider and model:
            return f"{provider}/{model}"
        project_model = str(context.get("project_default_model") or "").strip()
        if "/" in project_model:
            return project_model
        project_provider = str(context.get("project_default_provider") or "").strip()
        if project_provider and project_model:
            return f"{project_provider}/{project_model}"
        return ""

    def _project_context(self, project: dict[str, Any]) -> dict[str, Any]:
        current_task = self._tasks.current_task()
        active_thread = self._active_thread(current_task)
        return {
            "kind": "project",
            "project_name": redact_sensitive(project.get("name")),
            "workspace_name": Path(str(project.get("workspace_root") or "")).name,
            "project_file_name": Path(str(project.get("project_file") or "")).name,
            "task_title": redact_sensitive((current_task or {}).get("title")),
            "provider_id": (active_thread or {}).get("provider_id"),
            "model": (active_thread or {}).get("model"),
            "project_default_model": project.get("default_model"),
            "project_default_provider": self._provider_from_profile(project.get("default_profile_id")),
        }

    def _task_context(self, task: dict[str, Any], project: dict[str, Any]) -> dict[str, Any]:
        active_thread = self._active_thread(task)
        return {
            "kind": "task",
            "project_name": redact_sensitive(project.get("name")),
            "workspace_name": Path(str(project.get("workspace_root") or "")).name,
            "task_title": redact_sensitive(task.get("title")),
            "goal": redact_sensitive(task.get("goal")),
            "plan": redact_sensitive(task.get("plan")),
            "provider_id": (active_thread or {}).get("provider_id"),
            "model": (active_thread or {}).get("model"),
            "thread_name": redact_sensitive((active_thread or {}).get("name")),
            "project_default_model": project.get("default_model"),
            "project_default_provider": self._provider_from_profile(project.get("default_profile_id")),
        }

    def _context_text(self, context: dict[str, Any]) -> str:
        clean = redact_sensitive(context)
        lines = [f"{key}: {value}" for key, value in clean.items() if not self._context_value_is_empty(value)]
        return "\n".join(lines)[:1600]

    def _context_value_is_empty(self, value: Any) -> bool:
        if value is None:
            return True
        if isinstance(value, str):
            return not value.strip()
        if isinstance(value, (list, tuple, set, dict)):
            return len(value) == 0
        return False

    def _active_thread(self, task: dict[str, Any] | None) -> dict[str, Any] | None:
        if not isinstance(task, dict):
            return None
        active_id = str(task.get("active_provider_thread_id") or "").strip()
        threads = [item for item in list(task.get("provider_threads") or []) if isinstance(item, dict)]
        for item in threads:
            if active_id and str(item.get("thread_id") or "") == active_id:
                return item
        return threads[0] if threads else None

    def _project_title_is_generic(self, project: dict[str, Any]) -> bool:
        title = str(project.get("name") or "").strip()
        if title.lower() in GENERIC_PROJECT_TITLES:
            return True
        if title and title == str(project.get("project_id") or "").strip():
            return True
        return False

    def _task_title_is_generic(self, task: dict[str, Any], project: dict[str, Any]) -> bool:
        title = str(task.get("title") or "").strip()
        if title.lower() in GENERIC_TASK_TITLES:
            return True
        project_title = str(project.get("name") or "").strip()
        return bool(title and project_title and title == project_title)

    def _heuristic_project_title(self, project: dict[str, Any]) -> str:
        workspace = Path(str(project.get("workspace_root") or "")).name
        if workspace:
            return workspace.replace("-", " ").replace("_", " ").strip()
        return Path(str(project.get("project_file") or "")).stem or "AstraBridge Project"

    def _heuristic_task_title(self, task: dict[str, Any], project: dict[str, Any]) -> str:
        active = self._active_thread(task) or {}
        thread_name = str(active.get("name") or "").strip()
        if thread_name and not thread_name.lower().endswith("thread"):
            return thread_name
        provider = str(active.get("provider_id") or active.get("profile_id") or "").strip()
        model = str(active.get("model") or "").strip()
        if provider and model:
            return f"{provider} {model}"
        project_name = str(project.get("name") or "").strip()
        return project_name if project_name and project_name.lower() not in GENERIC_PROJECT_TITLES else "AstraBridge Task"

    def _normalized_text(self, result: Any) -> str:
        if isinstance(result, dict):
            normalized = result.get("normalized")
            if hasattr(normalized, "text"):
                return str(normalized.text or "")
            if isinstance(normalized, dict):
                return str(normalized.get("text") or normalized.get("output_text") or "")
            return str(result.get("output_text") or result.get("text") or "")
        return ""

    def _clean_title(self, value: str) -> str:
        title = str(redact_sensitive(value or "")).replace("\r", "\n").split("\n", 1)[0].strip()
        title = re.sub(r"^[#>*\-\d.\s]+", "", title).strip()
        title = title.strip("`\"'“”‘’[](){}")
        title = re.sub(r"\s+", " ", title).strip()
        if not title:
            return ""
        if SECRET_RE.search(title):
            raise SecurityError("Secret-like content is not allowed in generated titles.")
        return title[:80]

    def _provider_from_profile(self, profile_id: Any) -> str:
        text = str(profile_id or "").strip()
        if not text:
            return ""
        return text.split("-", 1)[0]
