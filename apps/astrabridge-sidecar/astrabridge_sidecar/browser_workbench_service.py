from __future__ import annotations

import json
import os
import shutil
import subprocess
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from .common import now_iso


def _normalize_url(raw: str) -> str:
    trimmed = str(raw or "").strip()
    if not trimmed:
        raise ValueError("URL is required.")
    candidate = (
        trimmed
        if "://" in trimmed
        else f"http://{trimmed}"
        if trimmed.startswith(("localhost", "127.0.0.1", "[::1]"))
        else f"https://{trimmed}"
    )
    parsed = urlparse(candidate)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("Only http and https URLs are supported.")
    return parsed.geturl()


def _normalize_layout_mode(raw: str | None) -> str:
    return "mobile" if str(raw or "").strip().lower() == "mobile" else "desktop"


def _desktop_entry_url(url: str) -> str:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if host in {"google.com", "www.google.com"}:
        params = [(key, value) for key, value in parse_qsl(parsed.query, keep_blank_values=True) if key != "igu"]
        path = "/" if parsed.path == "/webhp" and not params else (parsed.path or "/")
        return urlunparse(parsed._replace(netloc="www.google.com", path=path, query=urlencode(params)))
    if host == "m.youtube.com":
        return urlunparse(parsed._replace(netloc="www.youtube.com"))
    if host == "m.facebook.com":
        return urlunparse(parsed._replace(netloc="www.facebook.com"))
    if host.endswith(".m.wikipedia.org"):
        parts = host.split(".")
        if len(parts) == 4:
            return urlunparse(parsed._replace(netloc=f"{parts[0]}.wikipedia.org"))
    return url


def _known_mobile_host(url: str) -> tuple[str, str] | None:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if host in {"google.com", "www.google.com"}:
        params = parse_qsl(parsed.query, keep_blank_values=True)
        params = [(key, value) for key, value in params if key != "igu"]
        params.append(("igu", "1"))
        path = parsed.path or "/"
        if path == "/":
            path = "/webhp"
        return (
            urlunparse(parsed._replace(netloc="www.google.com", path=path, query=urlencode(params))),
            "mobile_host_rewrite_viewport",
        )
    if host in {"m.youtube.com", "m.facebook.com"} or host.endswith(".m.wikipedia.org"):
        return url, "mobile_host_rewrite_viewport"
    if host in {"youtube.com", "www.youtube.com"}:
        return urlunparse(parsed._replace(netloc="m.youtube.com")), "mobile_host_rewrite_viewport"
    if host == "youtu.be":
        video_id = parsed.path.strip("/")
        params = parse_qsl(parsed.query, keep_blank_values=True)
        if video_id and not any(key == "v" for key, _value in params):
            params.insert(0, ("v", video_id))
        return (
            urlunparse(parsed._replace(netloc="m.youtube.com", path="/watch", query=urlencode(params))),
            "mobile_host_rewrite_viewport",
        )
    if host in {"facebook.com", "www.facebook.com"}:
        return urlunparse(parsed._replace(netloc="m.facebook.com")), "mobile_host_rewrite_viewport"
    if host.endswith(".wikipedia.org") and not host.endswith(".m.wikipedia.org"):
        parts = host.split(".")
        if len(parts) == 3 and parts[0] not in {"www", "m"}:
            return urlunparse(parsed._replace(netloc=f"{parts[0]}.m.wikipedia.org")), "mobile_host_rewrite_viewport"
    return None


def _resolve_entry_url(url: str, layout_mode: str | None) -> tuple[str, str]:
    mode = _normalize_layout_mode(layout_mode)
    if mode != "mobile":
        return _desktop_entry_url(url), "desktop_viewport"
    # Product strategy for tall/narrow browser surfaces:
    # 1. Prefer explicit mobile-host entry points for the common sites that still publish them.
    # 2. Otherwise keep the canonical URL and rely on mobile viewport + user-agent responsive rendering.
    #
    # Verified mobile-entry set kept intentionally small so the browser does not guess.
    # Google Search uses the documented-responsive host plus the community-proven `igu=1`
    # embed entry; Google News still falls back to responsive rendering on the canonical host.
    known = _known_mobile_host(url)
    if known is not None:
        return known
    return url, "mobile_user_agent_viewport"


def _role_label(raw: str | None) -> str:
    value = str(raw or "").strip()
    return (value or "Browser")[:40]


def _session_token(raw: str) -> str:
    token = "".join(char.lower() if char.isalnum() else "-" for char in str(raw or "").strip())
    token = "-".join(part for part in token.split("-") if part)[:48]
    return token or "browser"


def _session_id(payload: dict[str, Any]) -> str:
    token = _session_token(str(payload.get("id") or payload.get("role") or "browser"))
    return token if token.startswith("ab-browser-") else f"ab-browser-{token}"


def _desktop_root() -> Path | None:
    override = os.environ.get("ASTRABRIDGE_DESKTOP_ROOT")
    if override:
        return Path(override).expanduser().resolve()
    candidate = Path(__file__).resolve().parents[2] / "astrabridge-desktop"
    return candidate if candidate.exists() else None


def _node_executable() -> str | None:
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


def _bridge_node_path_entries(desktop_root: Path | None) -> list[str]:
    entries: list[str] = []
    if desktop_root and (desktop_root / "node_modules").exists():
        entries.append(str(desktop_root / "node_modules"))
        pnpm_root = desktop_root / "node_modules" / ".pnpm"
        if pnpm_root.exists():
            for pattern in ("playwright-core@*", "playwright@*", "@playwright+test@*"):
                for candidate in sorted(pnpm_root.glob(pattern)):
                    nested = candidate / "node_modules"
                    if nested.exists():
                        entries.append(str(nested))
    bundled = Path.home() / ".cache" / "codex-runtimes" / "codex-primary-runtime" / "dependencies" / "node" / "node_modules"
    if bundled.exists():
        entries.append(str(bundled))
    return entries


@dataclass
class _PendingRequest:
    event: threading.Event = field(default_factory=threading.Event)
    result: dict[str, Any] | None = None
    error: Exception | None = None


class _BridgeSession:
    def __init__(self, session_id: str, role: str, session_dir: Path) -> None:
        self.id = session_id
        self.role = role
        self.title = f"AstraBridge Browser - {role}"
        self.session_dir = session_dir
        self.screenshot_path = self.session_dir / "frame.png"
        self._node = _node_executable()
        self._desktop_root = _desktop_root()
        self._script_path = Path(__file__).with_name("browser_workbench_bridge.cjs")
        self._process: subprocess.Popen[str] | None = None
        self._reader_thread: threading.Thread | None = None
        self._stderr_thread: threading.Thread | None = None
        self._write_lock = threading.Lock()
        self._pending_lock = threading.Lock()
        self._pending: dict[int, _PendingRequest] = {}
        self._request_id = 0
        self._closed = threading.Event()
        self._state_lock = threading.Lock()
        self._state: dict[str, Any] = {
            "id": session_id,
            "role": role,
            "title": self.title,
            "url": "",
            "status": "idle",
            "error": None,
            "preview_mode": "remote",
            "viewport_width": 1365,
            "viewport_height": 900,
            "layout_mode": "desktop",
            "layout_reason": "desktop",
            "mobile_optimized": None,
            "has_viewport_meta": None,
            "horizontal_overflow_ratio": None,
            "wide_element_count": None,
            "mobile_strategy": "desktop_viewport",
            "responsive_fit_score": None,
            "can_go_back": False,
            "can_go_forward": False,
            "loading": False,
            "updated_at": now_iso(),
        }
        self._stderr_tail: list[str] = []

    def snapshot(self) -> dict[str, Any]:
        with self._state_lock:
            return dict(self._state)

    def _set_state(self, patch: dict[str, Any]) -> None:
        with self._state_lock:
            self._state.update(patch)
            self._state["updated_at"] = now_iso()

    def _spawn(self) -> None:
        if not self._node:
            raise RuntimeError("Node.js is not available for the browser workbench.")
        if not self._script_path.is_file():
            raise RuntimeError(f"Browser bridge script is missing: {self._script_path}")
        if self._process and self._process.poll() is None:
            return
        env = os.environ.copy()
        node_entries = _bridge_node_path_entries(self._desktop_root)
        if node_entries:
            existing = [env["NODE_PATH"]] if env.get("NODE_PATH") else []
            env["NODE_PATH"] = os.pathsep.join(node_entries + existing)
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self._closed.clear()
        self._process = subprocess.Popen(
            [self._node, str(self._script_path)],
            cwd=str(self._desktop_root) if self._desktop_root else None,
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
        self._reader_thread = threading.Thread(target=self._reader_loop, name=f"browser-workbench-reader-{self.id}", daemon=True)
        self._stderr_thread = threading.Thread(target=self._stderr_loop, name=f"browser-workbench-stderr-{self.id}", daemon=True)
        self._reader_thread.start()
        self._stderr_thread.start()

    def _next_request_id(self) -> int:
        with self._pending_lock:
            self._request_id += 1
            return self._request_id

    def _send(self, payload: dict[str, Any]) -> None:
        process = self._process
        if process is None or process.stdin is None:
            raise RuntimeError("Browser bridge is not running.")
        line = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        with self._write_lock:
            process.stdin.write(line + "\n")
            process.stdin.flush()

    def _reader_loop(self) -> None:
        process = self._process
        if process is None or process.stdout is None:
            return
        reader_error: Exception | None = None
        try:
            for raw_line in process.stdout:
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    message = json.loads(line)
                except json.JSONDecodeError:
                    continue
                request_id = int(message.get("id") or 0)
                with self._pending_lock:
                    pending = self._pending.pop(request_id, None)
                session = message.get("session")
                if isinstance(session, dict):
                    self._set_state(session)
                if pending is None:
                    continue
                if message.get("ok"):
                    pending.result = message
                else:
                    pending.error = RuntimeError(str(message.get("error") or "Browser bridge request failed."))
                pending.event.set()
        except Exception as exc:  # noqa: BLE001
            reader_error = exc
        finally:
            self._closed.set()
            with self._pending_lock:
                pending_items = list(self._pending.values())
                self._pending.clear()
            for pending in pending_items:
                pending.error = RuntimeError(
                    str(reader_error) if reader_error else "Browser bridge disconnected."
                )
                pending.event.set()
            state_error = self._stderr_tail[-1] if self._stderr_tail else (str(reader_error) if reader_error else "Browser bridge disconnected.")
            self._set_state({"status": "error", "error": state_error[:300], "loading": False})

    def _stderr_loop(self) -> None:
        process = self._process
        if process is None or process.stderr is None:
            return
        for raw_line in process.stderr:
            line = str(raw_line or "").strip()
            if not line:
                continue
            self._stderr_tail = [*self._stderr_tail[-7:], line[:400]]

    def request(self, method: str, params: dict[str, Any], *, timeout: float = 35.0) -> dict[str, Any]:
        self._spawn()
        request_id = self._next_request_id()
        pending = _PendingRequest()
        with self._pending_lock:
            self._pending[request_id] = pending
        try:
            self._send({"id": request_id, "method": method, "params": params})
        except Exception:
            with self._pending_lock:
                self._pending.pop(request_id, None)
            raise
        if not pending.event.wait(timeout):
            with self._pending_lock:
                self._pending.pop(request_id, None)
            raise TimeoutError(f"Timed out waiting for browser bridge response: {method}")
        if pending.error is not None:
            raise pending.error
        if pending.result is None:
            raise RuntimeError("Browser bridge returned no result.")
        session = pending.result.get("session")
        if isinstance(session, dict):
            self._set_state(session)
        return self.snapshot()

    def close(self) -> None:
        try:
            if self._process and self._process.poll() is None:
                try:
                    self.request("close", {}, timeout=10.0)
                except Exception:
                    pass
                if self._process.poll() is None:
                    self._process.kill()
        finally:
            self._closed.set()
            self._process = None


class BrowserWorkbenchService:
    def __init__(self, projects: Any, *, session_factory: type[_BridgeSession] = _BridgeSession) -> None:
        self._projects = projects
        self._session_factory = session_factory
        self._lock = threading.Lock()
        self._sessions: dict[str, _BridgeSession] = {}

    def _session_dir(self, session_id: str) -> Path:
        if hasattr(self._projects, "require_shell_subdir"):
            return self._projects.require_shell_subdir("browser-workbench", session_id)
        root = self._projects.require_shell_state_root() / "browser-workbench" / session_id
        root.mkdir(parents=True, exist_ok=True)
        return root.resolve()

    def _session(self, session_id: str) -> _BridgeSession:
        with self._lock:
            session = self._sessions.get(session_id)
        if session is None:
            raise ValueError(f"Browser window not found: {session_id}")
        return session

    def _decorate_session(self, item: dict[str, Any]) -> dict[str, Any]:
        snapshot = dict(item)
        resolved_url, strategy = _resolve_entry_url(
            str(snapshot.get("url") or ""),
            str(snapshot.get("layout_mode") or "desktop"),
        )
        if resolved_url:
            snapshot["url"] = resolved_url
        snapshot["mobile_strategy"] = strategy
        return snapshot

    def list_sessions(self) -> list[dict[str, Any]]:
        with self._lock:
            sessions = list(self._sessions.values())
        items: list[dict[str, Any]] = []
        for session in sessions:
            try:
                items.append(self._decorate_session(session.request("snapshot", {"screenshot_path": str(session.screenshot_path)}, timeout=12.0)))
            except Exception:
                items.append(self._decorate_session(session.snapshot()))
        items.sort(key=lambda item: str(item.get("role") or "").lower())
        return items

    def create_session(self, payload: dict[str, Any]) -> dict[str, Any]:
        layout_mode = _normalize_layout_mode(str(payload.get("layout_mode") or "desktop"))
        url, strategy = _resolve_entry_url(_normalize_url(str(payload.get("url") or "")), layout_mode)
        role = _role_label(payload.get("role"))
        session_id = _session_id(payload)
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                session = self._session_factory(session_id, role, self._session_dir(session_id))
                self._sessions[session_id] = session
        return self._decorate_session(session.request(
            "create",
            {
                "session_id": session_id,
                "role": role,
                "url": url,
                "screenshot_path": str(session.screenshot_path),
                "layout_mode": layout_mode,
                "layout_reason": str(payload.get("layout_reason") or ""),
                "mobile_strategy": strategy,
            },
            timeout=120.0,
        ))

    def navigate(self, payload: dict[str, Any]) -> dict[str, Any]:
        session_id = str(payload.get("id") or "").strip()
        if not session_id:
            raise ValueError("id is required.")
        layout_mode = _normalize_layout_mode(str(payload.get("layout_mode") or ""))
        raw_url = _normalize_url(str(payload.get("url") or ""))
        url, strategy = _resolve_entry_url(raw_url, layout_mode)
        session = self._session(session_id)
        return self._decorate_session(session.request(
            "navigate",
            {
                "url": url,
                "screenshot_path": str(session.screenshot_path),
                "layout_mode": layout_mode if str(payload.get("layout_mode") or "").strip() else "",
                "layout_reason": str(payload.get("layout_reason") or ""),
                "mobile_strategy": strategy if str(payload.get("layout_mode") or "").strip() else "",
            },
            timeout=120.0,
        ))

    def layout(self, payload: dict[str, Any]) -> dict[str, Any]:
        session_id = str(payload.get("id") or "").strip()
        if not session_id:
            raise ValueError("id is required.")
        session = self._session(session_id)
        layout_mode = _normalize_layout_mode(str(payload.get("layout_mode") or "desktop"))
        current_url = str(session.snapshot().get("url") or "")
        resolved_url, strategy = _resolve_entry_url(current_url, layout_mode)
        if current_url and resolved_url and resolved_url != current_url:
            return self._decorate_session(session.request(
                "navigate",
                {
                    "url": resolved_url,
                    "screenshot_path": str(session.screenshot_path),
                    "layout_mode": layout_mode,
                    "layout_reason": str(payload.get("layout_reason") or ""),
                    "mobile_strategy": strategy,
                },
                timeout=120.0,
            ))
        return self._decorate_session(session.request(
            "layout",
            {
                "layout_mode": layout_mode,
                "layout_reason": str(payload.get("layout_reason") or ""),
                "screenshot_path": str(session.screenshot_path),
                "mobile_strategy": strategy,
            },
            timeout=120.0,
        ))

    def action(self, payload: dict[str, Any]) -> dict[str, Any]:
        session_id = str(payload.get("id") or "").strip()
        if not session_id:
            raise ValueError("id is required.")
        action = str(payload.get("action") or "").strip()
        if not action:
            raise ValueError("action is required.")
        session = self._session(session_id)
        params = {
            "action": action,
            "x": payload.get("x"),
            "y": payload.get("y"),
            "delta_x": payload.get("delta_x"),
            "delta_y": payload.get("delta_y"),
            "key": payload.get("key"),
            "text": payload.get("text"),
            "screenshot_path": str(session.screenshot_path),
        }
        return self._decorate_session(session.request("action", params, timeout=90.0))

    def focus(self, session_id: str) -> dict[str, Any]:
        return self._decorate_session(self._session(session_id).snapshot())

    def close(self, session_id: str) -> list[dict[str, Any]]:
        with self._lock:
            session = self._sessions.pop(session_id, None)
        if session is None:
            raise ValueError(f"Browser window not found: {session_id}")
        session.close()
        return self.list_sessions()

    def tile_two_up(self, _ids: list[str]) -> list[dict[str, Any]]:
        return self.list_sessions()

    def frame_path(self, session_id: str) -> Path:
        session = self._session(session_id)
        path = session.screenshot_path
        if not path.is_file():
            raise FileNotFoundError(f"Browser frame is not available yet for {session_id}.")
        return path
