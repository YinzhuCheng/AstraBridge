import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse
import urllib.request

from .common import WORKSPACE_STATE_DIRNAME, now_iso, read_json, slugify, write_json


DOGFOOD_SECRET_VALUE_RE = re.compile(
    r"(?i)(authorization\s*:\s*\S+|bearer\s+[a-z0-9._-]{12,}|"
    r"api[_-]?key\s*[:=]\s*\S+|secret[_-]?key\s*[:=]\s*\S+|"
    r"cookie\s*:\s*\S+|token\s*[:=]\s*\S+|"
    r"BEGIN\s+(RSA|OPENSSH|EC|DSA)\s+PRIVATE\s+KEY)"
)
DOGFOOD_SECRET_FIELD_PARTS = ("api_key", "apikey", "authorization", "cookie", "password", "secret", "token")
MAX_BROWSER_SMOKE_ACTIONS = 80
BROWSER_SMOKE_PRESET_RELEASE_WORKFLOW = "astrabridge_release_workflow_v1"
BROWSER_SMOKE_PRESET_PROVIDER_SWITCH_WORKFLOW = "astrabridge_provider_switch_workflow_v1"


DEFAULT_DOGFOOD_RUN: dict[str, Any] = {
    "enabled": False,
    "goal": "",
    "phase": "not_started",
    "status": "idle",
    "current_provider": "",
    "blocker": "",
    "next_step": "",
    "budgets": {
        "kimi_cny": 50,
        "deepseek_cny": 50,
        "yunwu_gpt_usd": 50,
        "yunwu_images": 200,
        "warn_percent": 80,
    },
    "usage": {
        "kimi_cny": 0,
        "deepseek_cny": 0,
        "yunwu_gpt_usd": 0,
        "yunwu_images": 0,
    },
    "captures": [],
    "browser_smokes": [],
    "milestones": [],
    "notes": [],
}


class DogfoodRunService:
    """Project-local run ledger for long autonomous app dogfooding.

    This deliberately stores only coordination metadata under `.astrabridge`, never
    provider secrets or raw Authorization-bearing request payloads.
    """

    def __init__(self, project_service) -> None:
        self._projects = project_service

    def snapshot(self) -> dict[str, Any]:
        path = self._path()
        payload = self._normalize(read_json(path, {}))
        if not path.exists():
            write_json(path, payload)
        return {"run": payload, "path": str(path)}

    def save(self, patch: dict[str, Any]) -> dict[str, Any]:
        current = self._normalize(read_json(self._path(), {}))
        merged = self._normalize(self._deep_merge(current, self._sanitize_patch(patch)))
        merged["updated_at"] = now_iso()
        write_json(self._path(), merged)
        return {"run": merged, "path": str(self._path())}

    def record_usage(self, delta: dict[str, Any], *, current_provider: str | None = None) -> dict[str, Any]:
        current = self._normalize(read_json(self._path(), {}))
        usage = dict(current.get("usage") or {})
        clean_delta: dict[str, int | float] = {}
        for key, value in dict(delta or {}).items():
            if key not in (current.get("budgets") or {}) and key not in (DEFAULT_DOGFOOD_RUN.get("usage") or {}):
                continue
            if not isinstance(value, (int, float)):
                continue
            clean_delta[str(key)] = value
            usage[str(key)] = usage.get(str(key), 0) + value
        if current_provider:
            current["current_provider"] = str(current_provider).strip()[:80]
        current["usage"] = usage
        current["updated_at"] = now_iso()
        self._reject_secret_like({"usage": usage, "delta": clean_delta, "current_provider": current.get("current_provider")})
        write_json(self._path(), current)
        return {"run": current, "path": str(self._path()), "usage_delta": clean_delta}

    def add_capture(self, payload: dict[str, Any]) -> dict[str, Any]:
        current = self._normalize(read_json(self._path(), {}))
        capture = {
            "path": str(payload.get("path") or "").strip(),
            "label": str(payload.get("label") or "").strip(),
            "provider": str(payload.get("provider") or "").strip(),
            "created_at": now_iso(),
        }
        if not capture["path"]:
            raise ValueError("capture path is required.")
        self._reject_secret_like(capture)
        current["captures"] = [capture, *list(current.get("captures") or [])][:80]
        current["updated_at"] = now_iso()
        write_json(self._path(), current)
        return {"run": current, "path": str(self._path()), "capture": capture}

    def browser_smoke(self, payload: dict[str, Any]) -> dict[str, Any]:
        current = self._normalize(read_json(self._path(), {}))
        url = str(payload.get("url") or "").strip()
        if not url.startswith(("http://127.0.0.1:", "http://localhost:", "file:///")):
            raise ValueError("Browser smoke URL must be local: 127.0.0.1, localhost, or file://.")
        preset = str(payload.get("preset") or "").strip()
        preset_config = self._browser_smoke_preset(preset)
        label = str(payload.get("label") or preset_config.get("label") or "browser smoke").strip()
        raw_actions = [*list(preset_config.get("actions") or []), *list(payload.get("actions") or [])]
        final_assertions = [*list(preset_config.get("final_assertions") or []), *self._browser_final_assertion_actions(payload)]
        actions = self._browser_actions([*raw_actions, *final_assertions])
        record = {
            "label": label,
            "url": url,
            "status": "unknown",
            "http_status": None,
            "console_errors": [str(item)[:300] for item in list(payload.get("console_errors") or [])[:20]],
            "request_failures": list(payload.get("request_failures") or [])[:20],
            "screenshot_path": str(payload.get("screenshot_path") or "").strip(),
            "screenshot_status": "provided" if str(payload.get("screenshot_path") or "").strip() else "pending",
            "created_at": now_iso(),
        }
        if preset:
            record["preset"] = preset
        if actions:
            record["actions"] = actions
        if final_assertions:
            record["final_assertions"] = final_assertions
        record["verification_level"] = "asserted" if final_assertions else "screenshot_only"
        if not final_assertions:
            record["verification_warning"] = (
                "No final assertions were provided; this smoke only verifies navigation, screenshot capture, "
                "and console status. It is not proof that the intended gameplay state is visible."
            )
        if len(raw_actions) + len(final_assertions) > len(actions):
            record["action_warning"] = f"truncated_to_{len(actions)}_actions"
        if record["screenshot_path"]:
            path = Path(record["screenshot_path"])
            if not path.is_file():
                raise FileNotFoundError(f"Screenshot path does not exist: {path}")
        try:
            if url.startswith("file:///"):
                file_path = self._path_from_file_url(url)
                record["http_status"] = 200 if file_path.is_file() else 404
                record["status"] = "pass" if file_path.is_file() and not record["console_errors"] else "fail"
                if file_path.is_file():
                    stylesheet_warnings = self._local_stylesheet_sanity(file_path)
                    if stylesheet_warnings:
                        record["stylesheet_warnings"] = stylesheet_warnings[:20]
                        record["console_errors"] = [
                            *record["console_errors"],
                            *[f"stylesheet: {item}"[:300] for item in stylesheet_warnings[:20]],
                        ][:20]
            else:
                request = urllib.request.Request(url, headers={"User-Agent": "AstraBridge/browser-smoke"})
                with urllib.request.urlopen(request, timeout=8) as response:  # noqa: S310 - local URL only, guarded above.
                    record["http_status"] = int(response.status)
                    record["status"] = "pass" if response.status < 400 and not record["console_errors"] else "fail"
        except Exception as exc:
            record["status"] = "fail"
            record["error"] = str(exc)[:300]

        if not record["screenshot_path"]:
            capture_url = self._browser_navigation_url(url)
            if capture_url != url:
                record["navigation_url"] = capture_url
            self._capture_with_playwright(capture_url, label, record, actions=actions)
        self._finalize_browser_smoke_status(record)
        self._reject_secret_like(record)
        current["browser_smokes"] = [*list(current.get("browser_smokes") or []), record][-40:]
        if record["screenshot_path"]:
            current["captures"] = [
                {
                    "path": record["screenshot_path"],
                    "label": record["label"],
                    "provider": str(current.get("current_provider") or "browser-smoke"),
                    "created_at": record["created_at"],
                },
                *list(current.get("captures") or []),
            ][:80]
        if bool(payload.get("auto_milestone", True)):
            current["milestones"] = [
                *list(current.get("milestones") or []),
                self._browser_smoke_milestone(current, record),
            ][-80:]
        current["updated_at"] = now_iso()
        write_json(self._path(), current)
        response: dict[str, Any] = {
            "path": str(self._path()),
            "browser_smoke": record,
            "run_summary": self._run_summary(current),
        }
        if bool(payload.get("include_run")):
            response["run"] = current
        return response

    def _path_from_file_url(self, url: str) -> Path:
        parsed = urlparse(url)
        raw_path = unquote(parsed.path)
        # Windows Playwright commonly reports file:///D:/... while WSL-oriented
        # agents may emit file:///mnt/d/... . Normalize both to host paths for
        # preflight checks so successful screenshots are not recorded as 404.
        if len(raw_path) >= 4 and raw_path[0] == "/" and raw_path[2] == ":" and raw_path[1].isalpha():
            raw_path = raw_path[1:]
        lower = raw_path.lower()
        if lower.startswith("/mnt/") and len(raw_path) > 7 and raw_path[5].isalpha() and raw_path[6] == "/":
            raw_path = f"{raw_path[5].upper()}:/{raw_path[7:]}"
        return Path(raw_path).resolve()

    def _browser_navigation_url(self, url: str) -> str:
        """Return a URL that the host-side Playwright browser can actually open."""
        if not url.startswith("file:///"):
            return url
        try:
            return self._path_from_file_url(url).as_uri()
        except Exception:
            return url

    def _local_stylesheet_sanity(self, html_path: Path) -> list[str]:
        try:
            html = html_path.read_text(encoding="utf-8", errors="replace")
        except Exception as exc:  # noqa: BLE001
            return [f"could not read html for stylesheet sanity: {str(exc)[:120]}"]
        warnings: list[str] = []
        for href in re.findall(r"<link\b[^>]*\bhref=[\"']([^\"']+)[\"'][^>]*>", html, flags=re.IGNORECASE):
            href_text = str(href or "").strip()
            if not href_text or href_text.startswith(("http://", "https://", "data:", "#")):
                continue
            clean_href = href_text.split("?", 1)[0].split("#", 1)[0]
            if not clean_href.lower().endswith(".css"):
                continue
            css_path = (html_path.parent / unquote(clean_href)).resolve()
            if not css_path.is_file():
                warnings.append(f"missing stylesheet {clean_href}")
                continue
            try:
                css = css_path.read_text(encoding="utf-8", errors="replace")
            except Exception as exc:  # noqa: BLE001
                warnings.append(f"could not read stylesheet {clean_href}: {str(exc)[:120]}")
                continue
            if "\ufffd" in css or "\u9225" in css or "\u951f" in css:
                warnings.append(f"possible mojibake in stylesheet {clean_href}")
            balance = self._css_brace_balance(css)
            if balance.get("extra_closes"):
                warnings.append(f"extra closing brace in stylesheet {clean_href}")
            if balance.get("unclosed_opens"):
                warnings.append(f"unclosed brace in stylesheet {clean_href}")
        return warnings

    def _css_brace_balance(self, css: str) -> dict[str, int]:
        opens = 0
        extra_closes = 0
        quote = ""
        in_comment = False
        escape = False
        i = 0
        while i < len(css):
            ch = css[i]
            nxt = css[i + 1] if i + 1 < len(css) else ""
            if in_comment:
                if ch == "*" and nxt == "/":
                    in_comment = False
                    i += 2
                    continue
                i += 1
                continue
            if quote:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == quote:
                    quote = ""
                i += 1
                continue
            if ch == "/" and nxt == "*":
                in_comment = True
                i += 2
                continue
            if ch in {"'", '"'}:
                quote = ch
            elif ch == "{":
                opens += 1
            elif ch == "}":
                if opens:
                    opens -= 1
                else:
                    extra_closes += 1
            i += 1
        return {"unclosed_opens": opens, "extra_closes": extra_closes}

    def _finalize_browser_smoke_status(self, record: dict[str, Any]) -> None:
        action_results = list(record.get("action_results") or [])
        action_failed = any(isinstance(item, dict) and item.get("ok") is False for item in action_results)
        try:
            http_status = int(record.get("http_status")) if record.get("http_status") is not None else None
        except Exception:
            http_status = None
        screenshot_status = str(record.get("screenshot_status") or "")
        has_blocked_screenshot = screenshot_status.startswith("blocked")
        has_failed_screenshot = screenshot_status in {
            "captured_after_failure",
            "captured_viewport_fallback_after_failure",
        } or bool(record.get("screenshot_error"))
        if (
            record.get("console_errors")
            or record.get("request_failures")
            or action_failed
            or (http_status is not None and http_status >= 400)
            or has_blocked_screenshot
            or has_failed_screenshot
        ):
            record["status"] = "fail"
            return
        if http_status is not None and http_status < 400:
            record["status"] = "pass"
            record.pop("error", None)
        elif screenshot_status in {"captured", "provided"} and record.get("status") == "unknown":
            record["status"] = "pass"

    def _browser_smoke_preset(self, preset: str) -> dict[str, Any]:
        if not preset:
            return {}
        if preset == BROWSER_SMOKE_PRESET_PROVIDER_SWITCH_WORKFLOW:
            return {
                "label": "AstraBridge provider switch workflow smoke",
                "actions": [
                    {"type": "expect_selector", "selector": "[data-testid='app-shell']", "timeout_ms": 12000},
                    {"type": "expect_selector", "selector": "[data-testid='composer']", "timeout_ms": 12000},
                    {"type": "expect_selector", "selector": "[data-testid='composer-profile']", "timeout_ms": 12000},
                    {"type": "expect_selector", "selector": "[data-testid='composer-model']", "timeout_ms": 12000},
                    {"type": "expect_selector", "selector": "[data-testid='task-fact-lanes']", "timeout_ms": 12000},
                    {"type": "expect_selector", "selector": "[data-testid='task-fact-handoffs']", "timeout_ms": 12000},
                    {"type": "click_selector", "selector": "[data-testid='inspector-tab-review']", "timeout_ms": 12000},
                    {"type": "expect_selector", "selector": "[data-testid='review-panel']", "timeout_ms": 12000},
                    {"type": "expect_selector_count_at_least", "selector": "[data-testid='review-file-row']", "count": 1, "timeout_ms": 12000},
                    {"type": "click_selector", "selector": "[data-testid='inspector-tab-terminal']", "timeout_ms": 12000},
                    {"type": "expect_selector", "selector": "[data-testid='terminal-panel']", "timeout_ms": 12000},
                    {"type": "expect_selector_count_at_least", "selector": "[data-testid='terminal-command-row']", "count": 1, "timeout_ms": 12000},
                    {"type": "click_selector", "selector": "[data-testid='inspector-tab-files']", "timeout_ms": 12000},
                    {"type": "expect_selector", "selector": "[data-testid='files-panel']", "timeout_ms": 12000},
                    {"type": "expect_selector_count_at_least", "selector": "[data-testid='project-file-row']", "count": 1, "timeout_ms": 12000},
                    {"type": "click_selector", "selector": "[data-testid='checkpoint-open']", "timeout_ms": 12000},
                    {"type": "expect_selector", "selector": "[data-testid='checkpoint-modal']", "timeout_ms": 12000},
                    {"type": "expect_selector", "selector": "[data-testid='checkpoint-save']", "timeout_ms": 12000},
                    {"type": "click_selector", "selector": "[data-testid='checkpoint-cancel']", "timeout_ms": 12000},
                    {"type": "click_selector", "selector": "[data-testid='inspector-tab-status']", "timeout_ms": 12000},
                    {"type": "expect_selector", "selector": "[data-testid='status-panel-goal']", "timeout_ms": 12000},
                ],
                "final_assertions": [
                    {"type": "expect_selector", "selector": "[data-testid='task-fact-lanes']", "timeout_ms": 12000},
                    {"type": "expect_selector", "selector": "[data-testid='task-fact-handoffs']", "timeout_ms": 12000},
                    {"type": "expect_selector", "selector": "[data-testid='task-fact-backend']", "timeout_ms": 12000},
                    {"type": "expect_selector", "selector": "[data-testid='workflow-evidence-panel']", "timeout_ms": 12000},
                    {"type": "expect_selector", "selector": "[data-testid='workflow-fact-recovery']", "timeout_ms": 12000},
                    {"type": "expect_selector_count_at_least", "selector": "[data-testid='workflow-diagnostic-row']", "count": 1, "timeout_ms": 12000},
                ],
            }
        if preset != BROWSER_SMOKE_PRESET_RELEASE_WORKFLOW:
            raise ValueError(f"Unsupported browser smoke preset: {preset}")
        return {
            "label": "AstraBridge release workflow smoke",
            "actions": [
                {"type": "expect_selector", "selector": "[data-testid='app-shell']", "timeout_ms": 12000},
                {"type": "expect_selector", "selector": "[data-testid='composer']", "timeout_ms": 12000},
                {"type": "expect_selector", "selector": "[data-testid='composer-send']", "timeout_ms": 12000},
                {"type": "expect_selector", "selector": "[data-testid='topbar-compact']", "timeout_ms": 12000},
                {"type": "expect_selector", "selector": "[data-testid='topbar-fork']", "timeout_ms": 12000},
                {"type": "click_selector", "selector": "[data-testid='inspector-tab-review']", "timeout_ms": 12000},
                {"type": "expect_selector", "selector": "[data-testid='review-panel']", "timeout_ms": 12000},
                {"type": "expect_selector_count_at_least", "selector": "[data-testid='review-file-row']", "count": 1, "timeout_ms": 12000},
                {"type": "click_selector", "selector": "[data-testid='inspector-tab-terminal']", "timeout_ms": 12000},
                {"type": "expect_selector", "selector": "[data-testid='terminal-panel']", "timeout_ms": 12000},
                {"type": "expect_selector_count_at_least", "selector": "[data-testid='terminal-command-row']", "count": 1, "timeout_ms": 12000},
                {"type": "click_selector", "selector": "[data-testid='inspector-tab-files']", "timeout_ms": 12000},
                {"type": "expect_selector", "selector": "[data-testid='files-panel']", "timeout_ms": 12000},
                {"type": "expect_selector_count_at_least", "selector": "[data-testid='project-file-row']", "count": 1, "timeout_ms": 12000},
                {"type": "click_selector", "selector": "[data-testid='inspector-tab-status']", "timeout_ms": 12000},
                {"type": "expect_selector", "selector": "[data-testid='status-panel-goal']", "timeout_ms": 12000},
                {"type": "expect_selector_count_at_least", "selector": "[data-testid='workflow-checkpoint-row']", "count": 1, "timeout_ms": 12000},
                {"type": "expect_selector_count_at_least", "selector": "[data-testid='workflow-diagnostic-row']", "count": 1, "timeout_ms": 12000},
                {"type": "expect_selector", "selector": "[data-testid='workflow-fact-recovery']", "timeout_ms": 12000},
                {"type": "click_selector", "selector": "[data-testid='inspector-tab-browser']", "timeout_ms": 12000},
                {"type": "expect_selector", "selector": "[data-testid='browser-panel']", "timeout_ms": 12000},
                {"type": "click_selector", "selector": "[data-testid='inspector-tab-status']", "timeout_ms": 12000},
            ],
            "final_assertions": [
                {"type": "expect_selector", "selector": "[data-testid='app-shell']", "timeout_ms": 12000},
                {"type": "expect_selector", "selector": "[data-testid='composer-send']", "timeout_ms": 12000},
                {"type": "expect_selector", "selector": "[data-testid='status-panel-goal']", "timeout_ms": 12000},
                {"type": "expect_selector_count_at_least", "selector": "[data-testid='workflow-checkpoint-row']", "count": 1, "timeout_ms": 12000},
                {"type": "expect_selector_count_at_least", "selector": "[data-testid='workflow-diagnostic-row']", "count": 1, "timeout_ms": 12000},
                {"type": "expect_selector", "selector": "[data-testid='workflow-fact-recovery']", "timeout_ms": 12000},
            ],
        }

    def _browser_actions(self, raw_actions: Any) -> list[dict[str, Any]]:
        actions: list[dict[str, Any]] = []
        for raw in list(raw_actions or [])[:MAX_BROWSER_SMOKE_ACTIONS]:
            if not isinstance(raw, dict):
                continue
            kind = str(raw.get("type") or "").strip()
            if kind == "click_text":
                text = str(raw.get("text") or "").strip()[:120]
                if text:
                    actions.append({"type": kind, "text": text, "timeout_ms": int(raw.get("timeout_ms") or 3000)})
            elif kind == "click_text_until_absent":
                text = str(raw.get("text") or "").strip()[:120]
                if text:
                    max_clicks = max(1, min(50, int(raw.get("max_clicks") or 20)))
                    settle_ms = max(0, min(2000, int(raw.get("settle_ms") or 250)))
                    actions.append(
                        {
                            "type": kind,
                            "text": text,
                            "timeout_ms": int(raw.get("timeout_ms") or 3000),
                            "max_clicks": max_clicks,
                            "settle_ms": settle_ms,
                        }
                    )
            elif kind in {"click_selector", "expect_selector"}:
                selector = str(raw.get("selector") or "").strip()[:160]
                if selector:
                    actions.append({"type": kind, "selector": selector, "timeout_ms": int(raw.get("timeout_ms") or 3000)})
            elif kind == "expect_selector_count_at_least":
                selector = str(raw.get("selector") or "").strip()[:160]
                count = max(1, min(50, int(raw.get("count") or 1)))
                if selector:
                    actions.append(
                        {
                            "type": kind,
                            "selector": selector,
                            "count": count,
                            "timeout_ms": int(raw.get("timeout_ms") or 3000),
                        }
                    )
            elif kind == "fill_selector":
                selector = str(raw.get("selector") or "").strip()[:160]
                value = str(raw.get("value") or "")[:4000]
                if selector:
                    actions.append(
                        {"type": kind, "selector": selector, "value": value, "timeout_ms": int(raw.get("timeout_ms") or 3000)}
                    )
            elif kind == "select_value":
                selector = str(raw.get("selector") or "").strip()[:160]
                value = str(raw.get("value") or "").strip()[:240]
                if selector and value:
                    actions.append(
                        {"type": kind, "selector": selector, "value": value, "timeout_ms": int(raw.get("timeout_ms") or 3000)}
                    )
            elif kind in {"expect_text", "wait_for_text_absent"}:
                text = str(raw.get("text") or "").strip()[:120]
                if text:
                    actions.append({"type": kind, "text": text, "timeout_ms": int(raw.get("timeout_ms") or 3000)})
            elif kind == "press":
                key = str(raw.get("key") or "").strip()[:40]
                if key:
                    actions.append({"type": kind, "key": key})
            elif kind in {"wait_ms", "wait", "pause"}:
                ms = max(0, min(5000, int(raw.get("ms") or 0)))
                actions.append({"type": "wait_ms", "ms": ms})
            else:
                raise ValueError(f"Unsupported browser smoke action: {kind}")
        self._reject_secret_like({"actions": actions})
        return actions

    def _browser_final_assertion_actions(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        nested = payload.get("final_assertions")
        if nested is None:
            nested = payload.get("finalAssertions")
        if isinstance(nested, dict):
            merged = dict(payload)
            for key in (
                "expect_text",
                "expect_selector",
                "expect_selector_count_at_least",
                "forbidden_text",
                "fail_if_text_visible",
                "assert_timeout_ms",
            ):
                if key in nested and key not in merged:
                    merged[key] = nested.get(key)
            payload = merged
        elif isinstance(nested, list):
            explicit_actions = self._browser_actions(nested)
            self._reject_secret_like({"final_assertions": explicit_actions})
            return explicit_actions

        actions: list[dict[str, Any]] = []
        for text in self._string_list(payload.get("expect_text")):
            actions.append({"type": "expect_text", "text": text, "timeout_ms": int(payload.get("assert_timeout_ms") or 3000)})
        for selector in self._string_list(payload.get("expect_selector")):
            actions.append({"type": "expect_selector", "selector": selector, "timeout_ms": int(payload.get("assert_timeout_ms") or 3000)})
        count_assertions = payload.get("expect_selector_count_at_least")
        if isinstance(count_assertions, dict):
            count_assertions = [count_assertions]
        if isinstance(count_assertions, list):
            for raw in count_assertions[:20]:
                if not isinstance(raw, dict):
                    continue
                selector = str(raw.get("selector") or "").strip()[:160]
                count = max(1, min(50, int(raw.get("count") or 1)))
                if selector:
                    actions.append(
                        {
                            "type": "expect_selector_count_at_least",
                            "selector": selector,
                            "count": count,
                            "timeout_ms": int(raw.get("timeout_ms") or payload.get("assert_timeout_ms") or 3000),
                        }
                    )
        forbidden = [
            *self._string_list(payload.get("forbidden_text")),
            *self._string_list(payload.get("fail_if_text_visible")),
        ]
        for text in forbidden:
            actions.append({"type": "wait_for_text_absent", "text": text, "timeout_ms": int(payload.get("assert_timeout_ms") or 3000)})
        self._reject_secret_like({"final_assertions": actions})
        return actions

    def _string_list(self, value: Any) -> list[str]:
        if value is None:
            return []
        raw_items = value if isinstance(value, list) else [value]
        items: list[str] = []
        for item in raw_items[:20]:
            text = str(item or "").strip()[:120]
            if text:
                items.append(text)
        return items

    def add_milestone(self, payload: dict[str, Any]) -> dict[str, Any]:
        current = self._normalize(read_json(self._path(), {}))
        sync_run_summary = self._should_sync_run_summary(current, payload)
        validation = payload.get("validation")
        validation_result = payload.get("validation_result")
        captures = [self._normalize_capture_ref(item) for item in list(payload.get("captures") or payload.get("capture_paths") or [])[:12]]
        capture_paths = [str(item.get("path") or "").strip() for item in captures if str(item.get("path") or "").strip()]
        if isinstance(validation, dict):
            validation_lines = [f"{key}: {value}" for key, value in validation.items()]
        else:
            validation_lines = [str(item)[:500] for item in list(validation or [])[:20]]
        if isinstance(validation_result, dict):
            validation_result_clean: dict[str, Any] | str = {
                str(key): str(value)[:500] if not isinstance(value, (dict, list)) else value
                for key, value in validation_result.items()
            }
        else:
            validation_result_clean = str(validation_result or "").strip()[:1200]
        milestone = {
            "label": str(payload.get("label") or "").strip(),
            "provider": str(payload.get("provider") or "").strip(),
            "model": str(payload.get("model") or "").strip(),
            "goal": str(payload.get("goal") or current.get("goal") or "").strip()[:1000],
            "plan_step": str(payload.get("plan_step") or "").strip()[:500],
            "status": str(payload.get("status") or "recorded").strip(),
            "captures": captures,
            "capture_paths": capture_paths,
            "validation": validation_lines,
            "validation_result": validation_result_clean,
            "failure_reason": str(payload.get("failure_reason") or "").strip()[:800],
            "next_step": str(payload.get("next_step") or "").strip()[:800],
            "next_action": str(payload.get("next_action") or payload.get("next_step") or "").strip()[:800],
            "created_at": now_iso(),
        }
        if not milestone["label"]:
            raise ValueError("milestone label is required.")
        self._reject_secret_like(milestone)
        if sync_run_summary:
            self._apply_milestone_summary(current, milestone)
        if captures:
            milestone_capture_paths = set(capture_paths)
            current["captures"] = [
                *self._milestone_run_captures(milestone),
                *[
                    item
                    for item in list(current.get("captures") or [])
                    if isinstance(item, dict) and str(item.get("path") or "").strip() not in milestone_capture_paths
                ],
            ][:80]
        current["milestones"] = [*list(current.get("milestones") or []), milestone][-80:]
        current["updated_at"] = now_iso()
        path = self._path()
        write_json(path, current)
        persisted = self._normalize(read_json(path, {}))
        if sync_run_summary and self._run_summary_needs_sync(persisted, milestone):
            self._apply_milestone_summary(persisted, milestone)
            persisted["updated_at"] = current["updated_at"]
            write_json(path, persisted)
        response: dict[str, Any] = {"path": str(path), "milestone": milestone, "run_summary": self._run_summary(persisted)}
        if bool(payload.get("include_run")):
            response["run"] = persisted
        return response

    def _run_summary(self, run: dict[str, Any]) -> dict[str, Any]:
        browser_smokes = list(run.get("browser_smokes") or [])
        captures = list(run.get("captures") or [])
        milestones = list(run.get("milestones") or [])
        return {
            "enabled": bool(run.get("enabled")),
            "goal": str(run.get("goal") or ""),
            "phase": str(run.get("phase") or ""),
            "status": str(run.get("status") or ""),
            "current_provider": str(run.get("current_provider") or ""),
            "blocker": str(run.get("blocker") or ""),
            "next_step": str(run.get("next_step") or ""),
            "usage": run.get("usage") or {},
            "budgets": run.get("budgets") or {},
            "counts": {
                "captures": len(captures),
                "browser_smokes": len(browser_smokes),
                "milestones": len(milestones),
            },
            "latest_capture": captures[0] if captures else None,
            "latest_browser_smoke": browser_smokes[-1] if browser_smokes else None,
            "latest_milestone": milestones[-1] if milestones else None,
            "updated_at": run.get("updated_at"),
        }

    def _normalize_capture_ref(self, item: Any) -> dict[str, str]:
        if isinstance(item, dict):
            capture = {
                "path": str(item.get("path") or "").strip(),
                "label": str(item.get("label") or "").strip(),
                "provider": str(item.get("provider") or "").strip(),
            }
        else:
            capture = {"path": str(item or "").strip(), "label": "", "provider": ""}
        return {key: value for key, value in capture.items() if value}

    def _milestone_run_captures(self, milestone: dict[str, Any]) -> list[dict[str, str]]:
        run_captures: list[dict[str, str]] = []
        created_at = str(milestone.get("created_at") or now_iso())
        fallback_label = str(milestone.get("label") or "").strip()
        fallback_provider = str(milestone.get("provider") or "").strip()
        for item in list(milestone.get("captures") or []):
            if not isinstance(item, dict):
                continue
            path = str(item.get("path") or "").strip()
            if not path:
                continue
            capture = {
                "path": path,
                "label": str(item.get("label") or fallback_label).strip(),
                "provider": str(item.get("provider") or fallback_provider).strip(),
                "created_at": created_at,
            }
            self._reject_secret_like(capture)
            run_captures.append(capture)
        return run_captures

    def _apply_milestone_summary(self, run: dict[str, Any], milestone: dict[str, Any]) -> None:
        if str(milestone.get("goal") or "").strip():
            run["goal"] = str(milestone.get("goal") or "").strip()[:1000]
        if str(milestone.get("provider") or "").strip():
            run["current_provider"] = str(milestone.get("provider") or "").strip()[:80]
        next_summary = str(milestone.get("next_step") or milestone.get("next_action") or "").strip()
        if next_summary:
            run["next_step"] = next_summary[:800]
        if str(milestone.get("failure_reason") or "").strip():
            run["blocker"] = str(milestone.get("failure_reason") or "").strip()[:800]
        elif str(milestone.get("status") or "").strip().lower() in {"pass", "passed", "verified", "complete", "completed"}:
            run["blocker"] = ""

    def _run_summary_needs_sync(self, run: dict[str, Any], milestone: dict[str, Any]) -> bool:
        goal = str(milestone.get("goal") or "").strip()
        provider = str(milestone.get("provider") or "").strip()
        next_summary = str(milestone.get("next_step") or milestone.get("next_action") or "").strip()
        if goal and str(run.get("goal") or "").strip() != goal:
            return True
        if provider and str(run.get("current_provider") or "").strip() != provider[:80]:
            return True
        if next_summary and str(run.get("next_step") or "").strip() != next_summary[:800]:
            return True
        return False

    def _should_sync_run_summary(self, run: dict[str, Any], payload: dict[str, Any]) -> bool:
        if bool(payload.get("sync_run_summary")):
            return True
        return not any(
            str(run.get(key) or "").strip()
            for key in ("goal", "current_provider", "next_step")
        )

    def add_note(self, note: str) -> None:
        current = self._normalize(read_json(self._path(), {}))
        clean = str(note or "").strip()[:800]
        if not clean:
            return
        self._reject_secret_like({"note": clean})
        current["notes"] = [clean, *list(current.get("notes") or [])][:80]
        current["updated_at"] = now_iso()
        write_json(self._path(), current)

    def _path(self) -> Path:
        return self._projects.require_workspace_root() / WORKSPACE_STATE_DIRNAME / "dogfood_run.json"

    def _capture_with_playwright(self, url: str, label: str, record: dict[str, Any], *, actions: list[dict[str, Any]] | None = None) -> None:
        node = self._node_executable()
        if not node:
            record["screenshot_status"] = "blocked_no_node"
            return
        captures_dir = self._projects.require_shell_state_root() / "captures"
        captures_dir.mkdir(parents=True, exist_ok=True)
        target = captures_dir / f"{slugify(label, 'browser-smoke')}-{now_iso().replace(':', '').replace('.', '-')}.png"
        script = """
const fs = require('fs');
const path = require('path');
let playwright;
function tryRequireFromPnpm(baseName) {
  const pnpmRoot = path.join(process.cwd(), 'node_modules', '.pnpm');
  if (!fs.existsSync(pnpmRoot)) return null;
  const match = fs.readdirSync(pnpmRoot).find(name => name.startsWith(baseName + '@'));
  if (!match) return null;
  const target = path.join(pnpmRoot, match, 'node_modules', baseName);
  if (!fs.existsSync(target)) return null;
  return require(target);
}
try {
  playwright = require('playwright');
} catch (error) {
  try {
    playwright = require('playwright-core');
  } catch (coreError) {
    try {
      playwright = tryRequireFromPnpm('playwright') || tryRequireFromPnpm('playwright-core');
      if (!playwright) throw coreError;
    } catch (fallbackError) {
      console.log(JSON.stringify({ ok: false, blocked: 'playwright_missing', error: String(fallbackError.message || fallbackError) }));
      process.exit(0);
    }
  }
}
async function launchBrowser() {
  const candidates = [
    null,
    'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
    'C:/Program Files/Microsoft/Edge/Application/msedge.exe',
    'C:/Program Files/Google/Chrome/Application/chrome.exe',
    'C:/Program Files (x86)/Google/Chrome/Application/chrome.exe'
  ];
  const failures = [];
  for (const candidate of candidates) {
    try {
      if (candidate && !fs.existsSync(candidate)) continue;
      const options = { headless: true };
      if (candidate) options.executablePath = candidate;
      return { browser: await playwright.chromium.launch(options), executable: candidate || 'playwright-chromium' };
    } catch (error) {
      failures.push(`${candidate || 'playwright-chromium'}: ${String(error.message || error).slice(0, 240)}`);
    }
  }
  throw new Error(`No browser runtime available. ${failures.join(' | ')}`);
}
(async () => {
  const launched = await launchBrowser();
  const browser = launched.browser;
  const page = await browser.newPage({ viewport: { width: 1365, height: 900 } });
  const consoleErrors = [];
  const requestFailures = [];
  page.on('console', message => {
    if (['error', 'warning'].includes(message.type())) consoleErrors.push(`${message.type()}: ${message.text()}`.slice(0, 300));
  });
  page.on('pageerror', error => consoleErrors.push(`pageerror: ${String(error.message || error)}`.slice(0, 300)));
  page.on('requestfailed', request => {
    requestFailures.push({
      url: String(request.url() || '').slice(0, 300),
      method: String(request.method() || '').slice(0, 32),
      resource_type: String(request.resourceType() || '').slice(0, 40),
      error_text: String(request.failure()?.errorText || 'request failed').slice(0, 200)
    });
  });
  let status = null;
  const actionResults = [];
  async function captureScreenshot(outputPath) {
    try {
      await page.screenshot({ path: outputPath, fullPage: true });
      return { path: outputPath, status: 'captured' };
    } catch (error) {
      consoleErrors.push(`screenshot-fullpage: ${String(error.message || error)}`.slice(0, 300));
      await page.screenshot({ path: outputPath, fullPage: false });
      return { path: outputPath, status: 'captured_viewport_fallback' };
    }
  }
  async function isVisible(locator, timeoutMs) {
    try {
      await locator.first().waitFor({ state: 'visible', timeout: timeoutMs || 500 });
      return true;
    } catch (_error) {
      return false;
    }
  }
  async function runAction(action) {
    const result = { type: action.type, ok: false };
    if (action.type === 'click_text') {
      await page.getByText(action.text, { exact: false }).first().click({ timeout: action.timeout_ms || 3000 });
      result.text = action.text;
    } else if (action.type === 'click_text_until_absent') {
      const locator = page.getByText(action.text, { exact: false });
      const maxClicks = Math.min(Math.max(action.max_clicks || 20, 1), 50);
      const settleMs = Math.min(Math.max(action.settle_ms || 250, 0), 2000);
      let clicks = 0;
      while (clicks < maxClicks && await isVisible(locator, action.timeout_ms || 3000)) {
        await locator.first().click({ timeout: action.timeout_ms || 3000 });
        clicks += 1;
        await page.waitForTimeout(settleMs);
      }
      result.text = action.text;
      result.clicks = clicks;
      if (await isVisible(locator, 250)) {
        throw new Error(`Text still visible after ${clicks} clicks: ${action.text}`);
      }
    } else if (action.type === 'click_selector') {
      await page.locator(action.selector).first().click({ timeout: action.timeout_ms || 3000 });
      result.selector = action.selector;
    } else if (action.type === 'expect_selector') {
      await page.locator(action.selector).first().waitFor({ state: 'visible', timeout: action.timeout_ms || 3000 });
      result.selector = action.selector;
    } else if (action.type === 'expect_selector_count_at_least') {
      const locator = page.locator(action.selector);
      await locator.first().waitFor({ state: 'visible', timeout: action.timeout_ms || 3000 });
      const count = await locator.count();
      result.selector = action.selector;
      result.count = count;
      result.expected_count = action.count || 1;
      if (count < (action.count || 1)) {
        throw new Error(`Selector count ${count} below expected minimum ${action.count || 1}: ${action.selector}`);
      }
    } else if (action.type === 'fill_selector') {
      await page.locator(action.selector).first().fill(action.value || '', { timeout: action.timeout_ms || 3000 });
      result.selector = action.selector;
      result.value = action.value || '';
    } else if (action.type === 'select_value') {
      await page.locator(action.selector).first().selectOption({ value: action.value || '' }, { timeout: action.timeout_ms || 3000 });
      result.selector = action.selector;
      result.value = action.value || '';
    } else if (action.type === 'expect_text') {
      await page.getByText(action.text, { exact: false }).first().waitFor({ state: 'visible', timeout: action.timeout_ms || 3000 });
      result.text = action.text;
    } else if (action.type === 'wait_for_text_absent') {
      await page.getByText(action.text, { exact: false }).first().waitFor({ state: 'hidden', timeout: action.timeout_ms || 3000 });
      result.text = action.text;
    } else if (action.type === 'press') {
      await page.keyboard.press(action.key);
      result.key = action.key;
    } else if (action.type === 'wait_ms') {
      await page.waitForTimeout(Math.min(Math.max(action.ms || 0, 0), 5000));
      result.ms = action.ms;
    } else {
      throw new Error(`Unsupported browser smoke action: ${action.type}`);
    }
    result.ok = true;
    return result;
  }
  try {
    const response = await page.goto(process.argv[2], { waitUntil: 'domcontentloaded', timeout: 15000 });
    status = response ? response.status() : null;
    await page.waitForTimeout(500);
    const actions = JSON.parse(process.argv[4] || '[]');
    for (const action of actions) {
      try {
        actionResults.push(await runAction(action));
      } catch (error) {
        actionResults.push({
          type: action.type,
          selector: action.selector,
          text: action.text,
          key: action.key,
          ok: false,
          error: String(error.message || error).slice(0, 300)
        });
        throw error;
      }
    }
    await page.waitForTimeout(250);
    const capture = await captureScreenshot(process.argv[3]);
    console.log(JSON.stringify({ ok: true, status, console_errors: consoleErrors.slice(0, 20), request_failures: requestFailures.slice(0, 20), screenshot_path: capture.path, screenshot_status: capture.status, browser_executable: launched.executable, action_results: actionResults }));
  } catch (error) {
    let screenshotPath = null;
    let screenshotStatus = 'blocked_capture_failed';
    try {
      const capture = await captureScreenshot(process.argv[3]);
      screenshotPath = capture.path;
      screenshotStatus = capture.status === 'captured_viewport_fallback' ? 'captured_viewport_fallback_after_failure' : 'captured_after_failure';
    } catch (screenshotError) {
      consoleErrors.push(`screenshot: ${String(screenshotError.message || screenshotError)}`.slice(0, 300));
    }
    console.log(JSON.stringify({
      ok: Boolean(screenshotPath),
      status,
      console_errors: consoleErrors.slice(0, 20),
      request_failures: requestFailures.slice(0, 20),
      error: String(error.message || error),
      screenshot_path: screenshotPath,
      screenshot_status: screenshotStatus,
      action_results: actionResults
    }));
  } finally {
    await browser.close();
  }
})().catch(error => {
  console.log(JSON.stringify({ ok: false, error: String(error.message || error) }));
});
"""
        script_dir = self._scratch_dir("browser-smoke")
        script_path = script_dir / f"{slugify(label, 'browser-smoke')}-{now_iso().replace(':', '').replace('.', '-')}.cjs"
        script_path.write_text(script, encoding="utf-8")
        cwd = self._desktop_root()
        try:
            env = __import__("os").environ.copy()
            node_paths = []
            if cwd and (cwd / "node_modules").exists():
                node_paths.append(str(cwd / "node_modules"))
                pnpm_root = cwd / "node_modules" / ".pnpm"
                if pnpm_root.exists():
                    for pattern in ("playwright-core@*", "playwright@*", "@playwright+test@*"):
                        for candidate in sorted(pnpm_root.glob(pattern)):
                            nested = candidate / "node_modules"
                            if nested.exists():
                                node_paths.append(str(nested))
            bundled_node_modules = Path.home() / ".cache" / "codex-runtimes" / "codex-primary-runtime" / "dependencies" / "node" / "node_modules"
            if bundled_node_modules.exists():
                node_paths.append(str(bundled_node_modules))
            if node_paths:
                env["NODE_PATH"] = __import__("os").pathsep.join(node_paths + ([env["NODE_PATH"]] if env.get("NODE_PATH") else []))
            completed = subprocess.run(
                [node, str(script_path), url, str(target), json.dumps(actions or [], ensure_ascii=False)],
                cwd=str(cwd) if cwd else None,
                env=env,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self._browser_smoke_subprocess_timeout(actions or []),
                check=False,
            )
            raw = (completed.stdout or "").strip().splitlines()[-1] if completed.stdout.strip() else "{}"
            result = json.loads(raw)
        except Exception as exc:
            record["screenshot_status"] = "blocked_capture_failed"
            record["screenshot_error"] = str(exc)[:300]
            return
        finally:
            try:
                script_path.unlink(missing_ok=True)
            except Exception:
                pass
        if result.get("ok") and target.is_file():
            record["screenshot_path"] = str(target)
            record["screenshot_status"] = str(result.get("screenshot_status") or "captured")
            if result.get("action_results"):
                record["action_results"] = result.get("action_results")
            if result.get("status") is not None:
                record["http_status"] = int(result.get("status"))
            if result.get("error"):
                record["screenshot_error"] = str(result.get("error"))[:300]
            merged_errors = [*record.get("console_errors", []), *list(result.get("console_errors") or [])]
            record["console_errors"] = [str(item)[:300] for item in merged_errors[:20]]
            merged_failures = [*list(record.get("request_failures") or []), *list(result.get("request_failures") or [])]
            record["request_failures"] = merged_failures[:20]
            if record["console_errors"]:
                record["status"] = "fail"
            elif record["request_failures"]:
                record["status"] = "fail"
            elif record.get("http_status") and int(record["http_status"]) >= 400:
                record["status"] = "fail"
            elif record["status"] == "unknown":
                record["status"] = "pass"
            return
        record["screenshot_status"] = str(result.get("blocked") or "blocked_capture_failed")
        if result.get("action_results"):
            record["action_results"] = result.get("action_results")
            record["status"] = "fail"
        if result.get("request_failures"):
            record["request_failures"] = list(result.get("request_failures") or [])[:20]
        if result.get("error"):
            record["screenshot_error"] = str(result.get("error"))[:300]

    def _browser_smoke_subprocess_timeout(self, actions: list[dict[str, Any]]) -> float:
        # Keep the outer watchdog slightly above the in-page action budget.
        # Otherwise a legitimate 30s Playwright action can be killed by the
        # Python subprocess timeout before Playwright records screenshot evidence.
        # Leave additional budget for browser startup plus full-page/viewport
        # screenshot fallback on heavy local pages.
        seconds = 35.0
        for action in actions:
            kind = str(action.get("type") or "")
            timeout_sec = max(float(action.get("timeout_ms") or 3000) / 1000.0, 0.1)
            if kind == "wait_ms":
                seconds += max(float(action.get("ms") or 0) / 1000.0, 0.0)
            elif kind == "click_text_until_absent":
                settle_sec = max(float(action.get("settle_ms") or 250) / 1000.0, 0.0)
                max_clicks = max(int(action.get("max_clicks") or 20), 1)
                seconds += timeout_sec + min(max_clicks * settle_sec, 20.0)
            else:
                seconds += timeout_sec
        return min(max(seconds, 25.0), 240.0)

    def _scratch_dir(self, *parts: str) -> Path:
        if hasattr(self._projects, "require_shell_subdir"):
            return self._projects.require_shell_subdir("tmp", *parts)
        root = self._projects.require_shell_state_root() / "tmp"
        path = root.joinpath(*parts) if parts else root
        path.mkdir(parents=True, exist_ok=True)
        return path.resolve()

    def _desktop_root(self) -> Path | None:
        override = __import__("os").environ.get("ASTRABRIDGE_DESKTOP_ROOT")
        if override:
            return Path(override).expanduser().resolve()
        candidate = Path(__file__).resolve().parents[2] / "astrabridge-desktop"
        return candidate if candidate.exists() else None

    def _node_executable(self) -> str | None:
        found = shutil.which("node")
        if found:
            return found
        candidates = [
            Path.home() / ".cache" / "codex-runtimes" / "codex-primary-runtime" / "dependencies" / "node" / "bin" / "node.exe",
            Path.home() / ".cache" / "codex-runtimes" / "codex-primary-runtime" / "dependencies" / "node" / "bin" / "node",
        ]
        for candidate in candidates:
            if candidate.is_file():
                return str(candidate)
        return None

    def _browser_smoke_milestone(self, current: dict[str, Any], record: dict[str, Any]) -> dict[str, Any]:
        validation = [
            f"URL status: {record.get('http_status') or 'n/a'}",
            f"Browser smoke status: {record.get('status')}",
        ]
        if record.get("console_errors"):
            validation.append(f"Console issues: {len(record.get('console_errors') or [])}")
        else:
            validation.append("No console errors were supplied or captured.")
        if record.get("screenshot_path"):
            validation.append("Screenshot captured.")
        else:
            validation.append(f"Screenshot: {record.get('screenshot_status') or 'not captured'}")
        milestone = {
            "label": f"Browser smoke: {record.get('label') or 'local target'}",
            "provider": str(current.get("current_provider") or "local"),
            "model": str(current.get("current_model") or ""),
            "goal": str(current.get("goal") or "")[:1000],
            "plan_step": "browser_smoke",
            "status": str(record.get("status") or "recorded"),
            "captures": [str(record.get("screenshot_path"))] if record.get("screenshot_path") else [],
            "capture_paths": [str(record.get("screenshot_path"))] if record.get("screenshot_path") else [],
            "validation": validation,
            "validation_result": {
                "http_status": record.get("http_status"),
                "console_error_count": len(record.get("console_errors") or []),
                "screenshot_status": record.get("screenshot_status"),
            },
            "failure_reason": str(record.get("error") or record.get("screenshot_error") or "")[:800],
            "next_step": str(current.get("next_step") or "")[:800],
            "next_action": str(current.get("next_step") or "")[:800],
            "created_at": now_iso(),
        }
        self._reject_secret_like(milestone)
        return milestone

    def _normalize(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, dict):
            payload = {}
        merged = self._deep_merge(DEFAULT_DOGFOOD_RUN, payload)
        merged["enabled"] = bool(merged.get("enabled", False))
        merged["captures"] = list(merged.get("captures") or [])[:80]
        merged["browser_smokes"] = list(merged.get("browser_smokes") or [])[-40:]
        merged["milestones"] = list(merged.get("milestones") or [])[-80:]
        merged["notes"] = list(merged.get("notes") or [])[:80]
        merged["updated_at"] = str(merged.get("updated_at") or now_iso())
        self._reject_secret_like(merged)
        return merged

    def _sanitize_patch(self, patch: dict[str, Any]) -> dict[str, Any]:
        allowed = {
            "enabled",
            "goal",
            "phase",
            "status",
            "current_provider",
            "blocker",
            "next_step",
            "budgets",
            "usage",
            "captures",
            "browser_smokes",
            "milestones",
            "notes",
        }
        sanitized = {key: value for key, value in dict(patch or {}).items() if key in allowed}
        self._reject_secret_like(sanitized)
        return sanitized

    def _deep_merge(self, base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
        result = dict(base)
        for key, value in dict(patch or {}).items():
            if isinstance(value, dict) and isinstance(result.get(key), dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    def _reject_secret_like(self, payload: dict[str, Any]) -> None:
        if self._contains_secret_value(payload):
            raise ValueError("Dogfood run metadata cannot contain API keys, tokens, or Authorization-like values.")

    def _contains_secret_value(self, value: Any, key_path: str = "") -> bool:
        if isinstance(value, dict):
            for key, item in value.items():
                lowered = str(key).lower()
                if any(part in lowered for part in DOGFOOD_SECRET_FIELD_PARTS):
                    text = str(item or "")
                    if text and text.lower() not in {"", "none", "n/a", "redacted"}:
                        return True
                if self._contains_secret_value(item, lowered):
                    return True
            return False
        if isinstance(value, list):
            return any(self._contains_secret_value(item, key_path) for item in value)
        if isinstance(value, str):
            if value.startswith("data:image/"):
                return True
            # Allow audit prose such as "No API key was saved"; reject actual
            # credential-bearing values and headers.
            return bool(DOGFOOD_SECRET_VALUE_RE.search(value))
        return False

